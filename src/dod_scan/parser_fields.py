# pattern: Functional Core
"""Regex-based field extraction from contract paragraph text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class ParsedContract:
    company_name: str = ""
    company_city: str = ""
    company_state: str = ""
    dollar_amount: float | None = None
    contract_number: str = ""
    mod_code: str = ""
    is_modification: bool = False
    work_locations: str = "[]"
    completion_date: str = ""
    contracting_activity: str = ""


# US state names and abbreviations for boundary detection
US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
    "District of Columbia", "Puerto Rico", "Guam",
}

# Pre-compiled regex for state matching: sorted by length (longest first) for greedy matching
_STATES_SORTED = sorted(US_STATES, key=len, reverse=True)
_STATE_ALTERNATION = "|".join(re.escape(state) for state in _STATES_SORTED)
_COMPANY_STATE_RE = re.compile(
    rf"^([^,]+?),\s*\*?\s*([\w\s.'-]+),\s*({_STATE_ALTERNATION})\s*,",
    re.IGNORECASE,
)
_SIMPLE_LOC_STATE_RE = re.compile(
    rf"({_STATE_ALTERNATION})$",
    re.IGNORECASE,
)

# Dollar amount: $X,XXX,XXX or $X,XXX,XXX,XXX
_DOLLAR_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")

# Modification code: "modification (P00045)" or "modification (P00008 and P00014)"
_MOD_CODE_WITH_WORD_RE = re.compile(
    r"modification\s*\(([A-Z]\d{4,5}(?:\s+and\s+[A-Z]\d{4,5})*)\)",
    re.IGNORECASE,
)

# Standalone mod code in parentheses near "contract": (P00045)
_MOD_CODE_STANDALONE_RE = re.compile(r"\(([A-Z]\d{4,5})\)")

# Contract number patterns — dash-separated: FA8730-23-C-0025, W912UM-26-D-A001
_CONTRACT_NUM_DASH_RE = re.compile(
    r"\b([A-Z]{1,2}\d{3,4}[A-Z]?\d?-\d{2}-[A-Z]-[A-Z0-9]{4,5})\b"
)

# Contract number patterns — continuous (no dashes): N0001926F0220
_CONTRACT_NUM_CONT_RE = re.compile(
    r"\b([A-Z]\d{4,5}\d{2}[A-Z]\d{4,5})\b"
)

# Contract number in parentheses at end: (FA8684-26-D-B001) or (N0001926F0220)
_CONTRACT_NUM_PAREN_RE = re.compile(
    r"\(([A-Z]{1,2}[\dA-Z-]{8,20})\)\s*\.?\s*$"
)

# Work locations with percentages: City, State (XX%)
# Strip leading "and" from the city match by using (?:and\s+)?
_WORK_LOC_PCT_RE = re.compile(
    r"(?:;\s*)?(?:and\s+)?([A-Za-z\s.'-]+?),\s*([A-Za-z\s]+?)\s*\((\d+)%\)"
)

# Simple work location: "Work will be performed at/in ..." — ends at period or "and is"
_WORK_PERFORMED_RE = re.compile(
    r"[Ww]ork\s+(?:will\s+)?(?:be\s+)?performed\s+(?:at|in)\s+([^.]+?)(?:\s+and\s+is|\s*\.)",
    re.DOTALL,
)

# TBD work locations
_WORK_TBD_RE = re.compile(
    r"[Ww]ork\s+locations?\s+and\s+funding\s+will\s+be\s+determined",
    re.IGNORECASE,
)

# Completion date
_COMPLETION_RE = re.compile(
    r"(?:be\s+)?completed\s+(?:by\s+|in\s+)?([A-Za-z].*?\d{4})",
    re.IGNORECASE,
)

# Contracting activity: "The X, Y, is the contracting activity"
# Use a more specific pattern to avoid matching the first "The" in a sentence
_ACTIVITY_RE = re.compile(
    r"(?:.*The\s+)?([^.]*[A-Z][^.]*)(?:\s+is\s+the\s+contracting\s+activity)",
    re.IGNORECASE | re.DOTALL,
)


def parse_contract_fields(text: str) -> ParsedContract:
    result = ParsedContract()

    result.company_name, result.company_city, result.company_state = _extract_company(text)
    result.dollar_amount = _extract_dollar_amount(text)
    result.contract_number = _extract_contract_number(text)
    result.mod_code, result.is_modification = _extract_mod_code(text)
    result.work_locations = _extract_work_locations(text)
    result.completion_date = _extract_completion_date(text)
    result.contracting_activity = _extract_contracting_activity(text)

    return result


def _extract_company(text: str) -> tuple[str, str, str]:
    match = _COMPANY_STATE_RE.match(text)
    if match:
        name = match.group(1).strip().rstrip("*").strip()
        city = match.group(2).strip()
        state = match.group(3)
        return name, city, state
    return "", "", ""


def _extract_dollar_amount(text: str) -> float | None:
    match = _DOLLAR_RE.search(text)
    if match:
        amount_str = match.group(0).replace("$", "").replace(",", "")
        try:
            return float(amount_str)
        except ValueError:
            return None
    return None


def _extract_contract_number(text: str) -> str:
    match = _CONTRACT_NUM_PAREN_RE.search(text)
    if match:
        return match.group(1)
    match = _CONTRACT_NUM_DASH_RE.search(text)
    if match:
        return match.group(1)
    match = _CONTRACT_NUM_CONT_RE.search(text)
    if match:
        return match.group(1)
    return ""


def _extract_mod_code(text: str) -> tuple[str, bool]:
    match = _MOD_CODE_WITH_WORD_RE.search(text)
    if match:
        codes = match.group(1).strip()
        first_code = codes.split()[0] if codes else ""
        return first_code, True
    match = _MOD_CODE_STANDALONE_RE.search(text)
    if match and "modification" in text.lower() and "not a modification" not in text.lower():
        return match.group(1), True
    if "modification" in text.lower() and "not a modification" not in text.lower():
        return "", True
    return "", False


def _extract_work_locations(text: str) -> str:
    if _WORK_TBD_RE.search(text):
        return "[]"

    # Special handling: first check if text contains work location percentages
    # Look for pattern "Work ... City, State (XX%); ... (XX%)" — use greedy matching
    pct_section_pattern = r"[Ww]ork\s+(?:will\s+)?(?:be\s+)?performed\s+(?:at|in)\s+(.+%\))"
    match = re.search(pct_section_pattern, text, re.DOTALL)
    if match:
        loc_text = match.group(1).strip()
        pct_matches = _WORK_LOC_PCT_RE.findall(loc_text)
        if pct_matches:
            locations = [
                {"city": city.strip().lstrip(), "state": state.strip().rstrip(), "pct": int(pct)}
                for city, state, pct in pct_matches
            ]
            return json.dumps(locations)

    # Fall back to simple location extraction
    match = _WORK_PERFORMED_RE.search(text)
    if match:
        loc_text = match.group(1).strip()
        locations = _parse_simple_locations(loc_text)
        if locations:
            return json.dumps(locations)

    return "[]"


def _parse_simple_locations(loc_text: str) -> list[dict]:
    locations = []
    parts = re.split(r";\s*(?:and\s+)?|,\s+and\s+", loc_text)
    for part in parts:
        part = part.strip().rstrip(",").strip()
        if not part:
            continue
        match = _SIMPLE_LOC_STATE_RE.search(part)
        if match:
            state = match.group(1)
            city = part[: match.start()].rstrip().rstrip(",").strip()
            if city:
                locations.append({"city": city, "state": state})
    return locations


def _extract_completion_date(text: str) -> str:
    match = _COMPLETION_RE.search(text)
    if match:
        return match.group(1).strip().rstrip(".")
    return ""


def _extract_contracting_activity(text: str) -> str:
    match = _ACTIVITY_RE.search(text)
    if match:
        return match.group(1).strip().rstrip(",").strip()
    return ""

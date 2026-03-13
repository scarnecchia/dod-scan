# DOD Contract Scanner Implementation Plan — Phase 3

**Goal:** Extract structured contract data from raw HTML stored in SQLite.

**Architecture:** Functional Core for HTML parsing and regex-based field extraction, Imperative Shell for DB reads/writes. Contract paragraphs extracted from `<main>` content, grouped by branch headers (`<p><strong>BRANCH</strong></p>`). Individual fields extracted via regex patterns derived from real contract text samples.

**Tech Stack:** Python 3.10+, BeautifulSoup, regex, SQLite

**Scope:** 8 phases from original design (phase 3 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-2 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC2: Parsing contract entries
- **dod-scan.AC2.1 Success:** Each contract paragraph extracted as a separate row with branch, company name, company city/state, dollar amount, contract number, work locations, completion date, contracting activity
- **dod-scan.AC2.2 Success:** Modification codes (e.g. P00045) extracted and `is_modification` set correctly
- **dod-scan.AC2.3 Success:** Multiple work locations with percentages parsed into JSON array
- **dod-scan.AC2.4 Success:** Raw text preserved verbatim for every contract entry
- **dod-scan.AC2.5 Edge:** Small business asterisk (*) stripped from company name
- **dod-scan.AC2.6 Edge:** "Work locations and funding will be determined with each order" results in empty work_locations (triggers HQ fallback in geocoding)

---

## Real Contract Text Formats (Captured 2026-03-12)

The following patterns were observed in actual war.gov contract text:

**Company + location:** `The Boeing Co. Defense, Tukwila, Washington,` or `Technomics Inc.,* Arlington, Virginia,`

**Dollar amounts:** `$2,335,411,756`, `$850,000,000`, `$9,999,992`

**Contract numbers:** `FA8730-23-C-0025`, `W912UM-26-D-A001`, `N0001926F0220`, `HQ0851-24-C-0001`

**Mod codes:** `(P00045)`, `(P00042)`, `(P00008 and P00014)`

**Work locations (simple):** `Work will be performed at Seattle, Washington`

**Work locations (multiple with %):** `Bloomington, Minnesota (68%); St. Louis Missouri (22%); and Linthicum Heights, Maryland (10%)`

**Work locations (TBD):** `Work locations and funding will be determined with each order`

**Completion dates:** `August 10, 2032`, `March 15, 2033`, `Sept. 30, 2026`, `May 2030`

**Contracting activity:** `The Air Force Lifecycle Management Center, Hanscom Air Force Base, Massachusetts, is the contracting activity`

**Small business asterisk:** `Technomics Inc.,*` — asterisk immediately after comma

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Contract text extraction from HTML (Functional Core)

**Verifies:** dod-scan.AC2.1, dod-scan.AC2.4

**Files:**
- Create: `src/dod_scan/parser_extract.py`

**Implementation:**

Create `src/dod_scan/parser_extract.py` — pure functions for extracting contract paragraphs from article HTML and grouping them by branch.

```python
# pattern: Functional Core
"""Extract contract paragraphs from war.gov article HTML."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

BRANCH_NAMES = frozenset({
    "AIR FORCE",
    "ARMY",
    "NAVY",
    "DEFENSE LOGISTICS AGENCY",
    "MISSILE DEFENSE AGENCY",
    "DEFENSE HEALTH AGENCY",
    "DEFENSE ADVANCED RESEARCH PROJECTS AGENCY",
    "DEFENSE INFORMATION SYSTEMS AGENCY",
    "DEFENSE THREAT REDUCTION AGENCY",
    "UNITED STATES SPECIAL OPERATIONS COMMAND",
    "WASHINGTON HEADQUARTERS SERVICES",
})


@dataclass(frozen=True)
class RawContract:
    branch: str
    raw_text: str


def extract_contracts_from_html(html: str) -> list[RawContract]:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    if not main:
        return []

    contracts: list[RawContract] = []
    current_branch: str | None = None

    for p in main.find_all("p"):
        strong = p.find("strong")
        if strong:
            text = strong.get_text(strip=True).upper()
            if text in BRANCH_NAMES:
                current_branch = text
                continue

        if current_branch is None:
            continue

        text = p.get_text(strip=True)
        if not text or len(text) < 50:
            continue

        contracts.append(RawContract(branch=current_branch, raw_text=text))

    return contracts
```

**Commit:** `feat: add HTML contract extraction with branch grouping`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Field extraction via regex (Functional Core)

**Verifies:** dod-scan.AC2.1, dod-scan.AC2.2, dod-scan.AC2.3, dod-scan.AC2.5, dod-scan.AC2.6

**Files:**
- Create: `src/dod_scan/parser_fields.py`

**Implementation:**

Create `src/dod_scan/parser_fields.py` — pure functions for extracting structured fields from contract paragraph text using regex.

```python
# pattern: Functional Core
"""Regex-based field extraction from contract paragraph text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


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
_WORK_LOC_PCT_RE = re.compile(
    r"([\w\s.'-]+),\s*([\w\s]+?)\s*\((\d+)%\)"
)

# Simple work location: "Work will be performed at/in City, State"
_WORK_PERFORMED_RE = re.compile(
    r"[Ww]ork\s+will\s+be\s+performed\s+(?:at|in)\s+(.+?)(?:,\s+and\s+is|\s+and\s+is|\s+with\s+an)",
    re.DOTALL,
)

# TBD work locations
_WORK_TBD_RE = re.compile(
    r"[Ww]ork\s+locations?\s+and\s+funding\s+will\s+be\s+determined",
    re.IGNORECASE,
)

# Completion date
_COMPLETION_RE = re.compile(
    r"(?:expected\s+to\s+be\s+)?completed?\s+(?:by\s+|in\s+)(\w[\w.,\s]*?\d{4})",
    re.IGNORECASE,
)

# Contracting activity: "The X, Y, is the contracting activity"
_ACTIVITY_RE = re.compile(
    r"(?:The\s+)?(.+?)\s*,?\s+is\s+the\s+contracting\s+activity",
    re.IGNORECASE,
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
    for state in sorted(US_STATES, key=len, reverse=True):
        pattern = re.compile(
            rf"^(.+?),\s*\*?\s*([\w\s.'-]+),\s*({re.escape(state)})\s*,",
            re.IGNORECASE,
        )
        match = pattern.match(text)
        if match:
            name = match.group(1).strip().rstrip(",").rstrip("*").strip()
            city = match.group(2).strip()
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
    if match and "modification" in text.lower():
        return match.group(1), True
    if "modification" in text.lower():
        return "", True
    return "", False


def _extract_work_locations(text: str) -> str:
    if _WORK_TBD_RE.search(text):
        return "[]"

    pct_matches = _WORK_LOC_PCT_RE.findall(text)
    if pct_matches:
        locations = [
            {"city": city.strip(), "state": state.strip(), "pct": int(pct)}
            for city, state, pct in pct_matches
        ]
        return json.dumps(locations)

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
        for state in sorted(US_STATES, key=len, reverse=True):
            if part.lower().endswith(state.lower()):
                city = part[: -len(state)].rstrip().rstrip(",").strip()
                if city:
                    locations.append({"city": city, "state": state})
                    break
    return locations


def _extract_completion_date(text: str) -> str:
    match = _COMPLETION_RE.search(text)
    if match:
        return match.group(1).strip().rstrip(".")
    return ""


def _extract_contracting_activity(text: str) -> str:
    match = _ACTIVITY_RE.search(text)
    if match:
        return match.group(1).strip()
    return ""
```

**Commit:** `feat: add regex-based contract field extraction`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Parser tests

**Verifies:** dod-scan.AC2.1, dod-scan.AC2.2, dod-scan.AC2.3, dod-scan.AC2.4, dod-scan.AC2.5, dod-scan.AC2.6

**Files:**
- Create: `tests/test_parser_extract.py`
- Create: `tests/test_parser_fields.py`
- Create: `tests/fixtures/article_page.html`

**Testing:**

Tests must verify each AC listed above using real contract text samples from war.gov (captured 2026-03-12):

- dod-scan.AC2.1: `extract_contracts_from_html` returns one `RawContract` per contract paragraph with correct branch assignment. `parse_contract_fields` extracts company_name, company_city, company_state, dollar_amount, contract_number, work_locations, completion_date, contracting_activity from real text. Test with:
  - Boeing Air Force contract: company="The Boeing Co. Defense", city="Tukwila", state="Washington", amount=2335411756.0, contract_number="FA8730-23-C-0025"
  - Navy Boeing contract with order number (N0001926F0220 — dashless format): amount=38899972.0, contract_number="N0001926F0220"
  - Army Corps contract: company="Koontz Electric Co. Inc.", city="Morrilton", state="Arkansas"

- dod-scan.AC2.2: Mod code extraction from `"modification (P00045)"` returns mod_code="P00045", is_modification=True. Multi-code `"modification (P00008 and P00014)"` returns mod_code="P00008", is_modification=True. Non-modification contract returns mod_code="", is_modification=False.

- dod-scan.AC2.3: Navy contract with percentages parses to JSON array: `[{"city": "Bloomington", "state": "Minnesota", "pct": 68}, {"city": "St. Louis", "state": "Missouri", "pct": 22}, {"city": "Linthicum Heights", "state": "Maryland", "pct": 10}]`

- dod-scan.AC2.4: Raw text stored verbatim in `RawContract.raw_text`. Verify text matches input exactly.

- dod-scan.AC2.5: `"Technomics Inc.,* Arlington, Virginia,"` extracts company_name="Technomics Inc." (asterisk stripped). Also test `"Singularity Security Group LLC,*"`.

- dod-scan.AC2.6: Text containing "Work locations and funding will be determined with each order" returns work_locations="[]" (empty JSON array).

Create `tests/fixtures/article_page.html` with realistic article HTML using `<main>`, branch `<strong>` headers, and 5-6 contract `<p>` tags covering the variations above.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_parser_extract.py tests/test_parser_fields.py -v`
Expected: All tests pass

**Commit:** `test: add parser extraction and field tests with real contract samples`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_SUBCOMPONENT_B (tasks 4-5) -->
<!-- START_TASK_4 -->
### Task 4: Parser orchestration and DB persistence

**Verifies:** dod-scan.AC2.1, dod-scan.AC2.4

**Files:**
- Create: `src/dod_scan/parser.py`

**Implementation:**

Create `src/dod_scan/parser.py` — orchestration module that reads raw HTML from `pages` table, extracts contracts, and stores in `contracts` table.

```python
# pattern: Imperative Shell
"""Parser orchestration — extracts contracts from stored HTML and persists to DB."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from dod_scan.parser_extract import extract_contracts_from_html
from dod_scan.parser_fields import parse_contract_fields

logger = logging.getLogger(__name__)


def parse_all(conn: sqlite3.Connection) -> int:
    pages = conn.execute(
        """
        SELECT article_id, raw_html FROM pages
        WHERE article_id NOT IN (
            SELECT DISTINCT article_id FROM contracts
        )
        """
    ).fetchall()

    total_contracts = 0

    for page in pages:
        article_id = page["article_id"]
        raw_html = page["raw_html"]

        raw_contracts = extract_contracts_from_html(raw_html)
        logger.info(
            "Extracted %d contracts from article %s", len(raw_contracts), article_id
        )

        for raw in raw_contracts:
            fields = parse_contract_fields(raw.raw_text)
            _store_contract(conn, article_id, raw.branch, fields, raw.raw_text)
            total_contracts += 1

    logger.info("Parse complete: %d contracts extracted", total_contracts)
    return total_contracts


def _store_contract(
    conn: sqlite3.Connection,
    article_id: str,
    branch: str,
    fields,
    raw_text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO contracts (
            article_id, branch, company_name, company_city, company_state,
            dollar_amount, contract_number, mod_code, is_modification,
            work_locations, completion_date, contracting_activity,
            raw_text, parsed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            branch,
            fields.company_name,
            fields.company_city,
            fields.company_state,
            fields.dollar_amount,
            fields.contract_number,
            fields.mod_code,
            fields.is_modification,
            fields.work_locations,
            fields.completion_date,
            fields.contracting_activity,
            raw_text,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
```

**Commit:** `feat: add parser orchestration with DB persistence`
<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Parser orchestration tests

**Verifies:** dod-scan.AC2.1, dod-scan.AC2.4

**Files:**
- Create: `tests/test_parser_orchestration.py`

**Testing:**

Tests must verify the orchestration layer against the DB:
- dod-scan.AC2.1: Insert a `pages` row with real article HTML (from fixture). Call `parse_all()`. Verify `contracts` table has rows with correct branch, company_name, dollar_amount, etc.
- dod-scan.AC2.4: Verify `raw_text` column matches the original paragraph text verbatim.
- Idempotency: Call `parse_all()` twice on same data. Verify no duplicate contracts (second call skips already-parsed articles).

Use `tmp_db` and `db_conn` fixtures from conftest.py. Insert fixture HTML into `pages` table before calling `parse_all()`.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_parser_orchestration.py -v`
Expected: All tests pass

**Commit:** `test: add parser orchestration tests`
<!-- END_TASK_5 -->
<!-- END_SUBCOMPONENT_B -->

<!-- START_TASK_6 -->
### Task 6: Wire parse subcommand in CLI

**Files:**
- Modify: `src/dod_scan/cli.py` — replace `parse` stub with real implementation

**Implementation:**

Update the `parse` command in `cli.py`:

```python
@app.command()
def parse() -> None:
    """Extract structured contract data from raw HTML."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.parser import parse_all
        count = parse_all(conn)
        typer.echo(f"Parse complete: {count} contracts extracted")
    except Exception as exc:
        typer.echo(f"Parse failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan parse --help`
Expected: Shows help text

**Commit:** `feat: wire parse subcommand to parser orchestration`
<!-- END_TASK_6 -->

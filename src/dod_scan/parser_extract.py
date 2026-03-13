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

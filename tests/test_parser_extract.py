"""Tests for contract extraction from HTML."""

import pytest

from dod_scan.parser_extract import extract_contracts_from_html, RawContract


@pytest.fixture
def article_page_html() -> str:
    with open("tests/fixtures/article_page.html") as f:
        return f.read()


def test_extract_contracts_returns_raw_contract_objects(article_page_html: str) -> None:
    """Verify AC2.1: extract_contracts_from_html returns RawContract objects."""
    contracts = extract_contracts_from_html(article_page_html)

    assert len(contracts) > 0
    assert all(isinstance(c, RawContract) for c in contracts)


def test_extract_contracts_branch_assignment(article_page_html: str) -> None:
    """Verify AC2.1: Each contract is assigned correct branch."""
    contracts = extract_contracts_from_html(article_page_html)

    # Should have contracts from multiple branches
    branches = {c.branch for c in contracts}
    assert "AIR FORCE" in branches
    assert "NAVY" in branches
    assert "ARMY" in branches


def test_extract_contracts_from_air_force(article_page_html: str) -> None:
    """Verify AC2.1: Air Force contracts extracted and assigned correctly."""
    contracts = extract_contracts_from_html(article_page_html)
    air_force_contracts = [c for c in contracts if c.branch == "AIR FORCE"]

    assert len(air_force_contracts) == 2
    assert all(c.branch == "AIR FORCE" for c in air_force_contracts)


def test_extract_contracts_preserves_raw_text(article_page_html: str) -> None:
    """Verify AC2.4: Raw text preserved verbatim."""
    contracts = extract_contracts_from_html(article_page_html)

    # Find the Boeing Air Force contract
    boeing_contracts = [c for c in contracts if "Boeing Co. Defense" in c.raw_text]
    assert len(boeing_contracts) > 0

    boeing = boeing_contracts[0]
    assert "The Boeing Co. Defense, Tukwila, Washington" in boeing.raw_text
    assert "$2,335,411,756" in boeing.raw_text
    assert "FA8730-23-C-0025" in boeing.raw_text


def test_extract_contracts_skips_short_paragraphs(article_page_html: str) -> None:
    """Verify short paragraphs (< 50 chars) are skipped."""
    contracts = extract_contracts_from_html(article_page_html)

    # All contracts should have substantial text
    assert all(len(c.raw_text) >= 50 for c in contracts)


def test_extract_contracts_requires_branch_header() -> None:
    """Verify contracts before any branch header are skipped."""
    html = """
    <main>
        <p>Random contract text before any branch header.</p>
        <p><strong>ARMY</strong></p>
        <p>Real Army contract text that should be extracted with substantial content length here.</p>
    </main>
    """
    contracts = extract_contracts_from_html(html)
    assert len(contracts) == 1
    assert contracts[0].branch == "ARMY"


def test_extract_contracts_from_no_main_tag() -> None:
    """Verify empty result when no main tag found."""
    html = "<div><p>Content without main tag</p></div>"
    contracts = extract_contracts_from_html(html)
    assert contracts == []


def test_extract_contracts_empty_html() -> None:
    """Verify empty result for empty HTML."""
    contracts = extract_contracts_from_html("")
    assert contracts == []


def test_extract_contracts_multiple_branches(article_page_html: str) -> None:
    """Verify contracts grouped correctly under multiple branch headers."""
    contracts = extract_contracts_from_html(article_page_html)

    # Count contracts by branch
    branch_counts = {}
    for c in contracts:
        branch_counts[c.branch] = branch_counts.get(c.branch, 0) + 1

    # Navy should have 2 contracts
    assert branch_counts.get("NAVY", 0) == 2
    # DLA should have 1
    assert branch_counts.get("DEFENSE LOGISTICS AGENCY", 0) == 1


def test_extract_contracts_case_insensitive_branch() -> None:
    """Verify branch matching is case-insensitive."""
    html = """
    <main>
        <p><strong>air force</strong></p>
        <p>Test contract with Air Force that is sufficiently long and has enough content details here.</p>
    </main>
    """
    contracts = extract_contracts_from_html(html)
    assert len(contracts) == 1
    assert contracts[0].branch == "AIR FORCE"


def test_raw_contract_is_frozen() -> None:
    """Verify RawContract dataclass is immutable."""
    contract = RawContract(branch="ARMY", raw_text="Test text here")
    with pytest.raises(AttributeError):
        contract.branch = "NAVY"  # type: ignore

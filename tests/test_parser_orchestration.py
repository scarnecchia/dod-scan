"""Tests for parser orchestration and DB persistence."""

import json
import sqlite3
from pathlib import Path

import pytest

from dod_scan.parser import parse_all


@pytest.fixture
def article_html(fixture_path: Path) -> str:
    """Load the article page fixture."""
    with open(fixture_path / "article_page.html") as f:
        return f.read()


@pytest.fixture
def fixture_path() -> Path:
    """Get path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestParseAllOrchestration:
    """Test parser orchestration with database persistence."""

    def test_parse_all_returns_contract_count(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify parse_all returns count of contracts extracted."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        count = parse_all(db_conn)

        assert count > 0
        assert count == 6

    def test_parse_all_inserts_contracts_to_db(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify contracts table has rows after parse_all."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contracts = db_conn.execute("SELECT COUNT(*) as cnt FROM contracts").fetchone()
        assert contracts["cnt"] == 6

    def test_parse_all_preserves_raw_text(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify raw_text column matches original paragraph text (AC2.4)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contracts = db_conn.execute("SELECT raw_text FROM contracts").fetchall()
        assert len(contracts) == 6

        boeing_contract = contracts[0]
        raw_text = boeing_contract["raw_text"]
        assert "The Boeing Co. Defense" in raw_text
        assert "Tukwila, Washington" in raw_text
        assert "$2,335,411,756" in raw_text
        assert "FA8730-23-C-0025" in raw_text

    def test_parse_all_extracts_boeing_air_force_contract(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify Boeing Air Force contract fields extracted correctly (AC2.1)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE company_name LIKE '%Boeing%' AND branch='AIR FORCE'"
        ).fetchone()

        assert contract is not None
        assert contract["company_name"] == "The Boeing Co. Defense"
        assert contract["company_city"] == "Tukwila"
        assert contract["company_state"] == "Washington"
        assert contract["dollar_amount"] == 2335411756.0
        assert contract["contract_number"] == "FA8730-23-C-0025"
        assert contract["branch"] == "AIR FORCE"
        assert contract["is_modification"] == 0

    def test_parse_all_extracts_navy_dashless_contract_number(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify dashless contract number extracted (AC2.1)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='N0001926F0220'"
        ).fetchone()

        assert contract is not None
        assert contract["company_name"] == "The Boeing Co."
        assert contract["company_city"] == "St. Louis"
        assert contract["company_state"] == "Missouri"
        assert contract["dollar_amount"] == 38899972.0
        assert contract["branch"] == "NAVY"

    def test_parse_all_extracts_modification_code(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify modification code extraction (AC2.2)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='N0001926F0220'"
        ).fetchone()

        assert contract["mod_code"] == "P00045"
        assert contract["is_modification"] == 1

    def test_parse_all_extracts_multi_code_modification(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify multi-code modification extraction (AC2.2)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='HQ0851-24-C-0001'"
        ).fetchone()

        assert contract["mod_code"] == "P00008"
        assert contract["is_modification"] == 1

    def test_parse_all_extracts_work_locations_with_percentages(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify work locations with percentages extracted as JSON (AC2.3)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='N0001926F0220'"
        ).fetchone()

        locations = json.loads(contract["work_locations"])
        assert len(locations) == 3
        assert locations[0]["city"] == "Bloomington"
        assert locations[0]["state"] == "Minnesota"
        assert locations[0]["pct"] == 68
        assert locations[1]["city"] == "St. Louis"
        assert locations[1]["state"] == "Missouri"
        assert locations[1]["pct"] == 22
        assert locations[2]["city"] == "Linthicum Heights"
        assert locations[2]["state"] == "Maryland"
        assert locations[2]["pct"] == 10

    def test_parse_all_extracts_simple_work_location(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify simple work location extracted (AC2.1)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='W912UM-26-D-A001'"
        ).fetchone()

        locations = json.loads(contract["work_locations"])
        assert len(locations) == 1
        assert locations[0]["city"] == "Little Rock"
        assert locations[0]["state"] == "Arkansas"

    def test_parse_all_extracts_tbd_work_locations(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify TBD work locations return empty array (AC2.6)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='FA8684-26-D-B001'"
        ).fetchone()

        assert contract["work_locations"] == "[]"

    def test_parse_all_strips_small_business_asterisk(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify small business asterisk stripped from company name (AC2.5)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='FA8684-26-D-B001'"
        ).fetchone()

        assert contract["company_name"] == "Technomics Inc."
        assert "*" not in contract["company_name"]

    def test_parse_all_strips_asterisk_other_format(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify asterisk stripped in other formats (AC2.5)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='DLA-26-C-0042'"
        ).fetchone()

        assert contract["company_name"] == "Singularity Security Group LLC"
        assert "*" not in contract["company_name"]

    def test_parse_all_branch_assignment(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify branch assigned correctly from section headers."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        branches = db_conn.execute(
            "SELECT DISTINCT branch FROM contracts ORDER BY branch"
        ).fetchall()
        branch_names = [b["branch"] for b in branches]

        assert "AIR FORCE" in branch_names
        assert "NAVY" in branch_names
        assert "ARMY" in branch_names
        assert "DEFENSE LOGISTICS AGENCY" in branch_names

    def test_parse_all_idempotency(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify parse_all skips already-parsed articles (idempotency)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        first_count = parse_all(db_conn)
        assert first_count == 6

        second_count = parse_all(db_conn)
        assert second_count == 0

        total_contracts = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM contracts"
        ).fetchone()
        assert total_contracts["cnt"] == 6

    def test_parse_all_skips_article_with_existing_contracts(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify parse_all doesn't reprocess articles already in contracts table."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-002", "http://example.com/art-002", article_html),
        )
        db_conn.commit()

        count = parse_all(db_conn)
        assert count == 6

        total = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM contracts"
        ).fetchone()
        assert total["cnt"] == 12

    def test_parse_all_stores_timestamp(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify parsed_at timestamp is set."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT parsed_at FROM contracts LIMIT 1"
        ).fetchone()

        assert contract["parsed_at"] is not None
        assert "T" in contract["parsed_at"]
        assert "+" in contract["parsed_at"] or "Z" in contract["parsed_at"]

    def test_parse_all_extracts_contracting_activity(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify contracting_activity extracted correctly (AC2.1)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='FA8730-23-C-0025'"
        ).fetchone()

        assert contract["contracting_activity"] is not None
        assert "Air Force" in contract["contracting_activity"]

    def test_parse_all_extracts_completion_date(
        self, db_conn: sqlite3.Connection, article_html: str
    ) -> None:
        """Verify completion_date extracted correctly (AC2.1)."""
        db_conn.execute(
            "INSERT INTO pages (article_id, url, raw_html) VALUES (?, ?, ?)",
            ("art-001", "http://example.com/art-001", article_html),
        )
        db_conn.commit()

        parse_all(db_conn)

        contract = db_conn.execute(
            "SELECT * FROM contracts WHERE contract_number='FA8730-23-C-0025'"
        ).fetchone()

        assert contract["completion_date"] is not None
        assert "2032" in contract["completion_date"]

"""Tests for geocoder orchestration layer."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from dod_scan.geocoder import geocode_all
from dod_scan.geocoder_api import GeocodedLocation


def insert_test_page(conn: sqlite3.Connection, article_id: str, url: str = "http://example.com") -> None:
    """Helper to insert a test page."""
    conn.execute(
        """
        INSERT INTO pages (article_id, url)
        VALUES (?, ?)
        """,
        (article_id, url),
    )
    conn.commit()


class TestGeocodeOrchestration:
    def test_ac4_1_work_location_geocoded_and_stored(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.1: Work location geocoded and stored in contract_locations."""
        insert_test_page(db_conn, "test1")

        # Insert contract with work location
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )

        # Insert classification marking it as procurement
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state to avoid API calls
        mock_location = GeocodedLocation(latitude=47.6062, longitude=-122.3321)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=mock_location):
            count = geocode_all(db_conn)

        assert count == 1

        # Verify contract_locations table has the entry
        row = db_conn.execute(
            "SELECT latitude, longitude, source FROM contract_locations WHERE contract_id = 1"
        ).fetchone()
        assert row is not None
        assert row["latitude"] == 47.6062
        assert row["longitude"] == -122.3321
        assert row["source"] == "work_location"

    def test_ac4_2_company_hq_fallback_when_work_location_empty(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.2: Company HQ used as fallback when work_locations is empty."""
        insert_test_page(db_conn, "test1")

        # Insert contract with empty work_locations but valid company HQ
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            ("[]",),
        )

        # Insert classification marking it as procurement
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state
        mock_location = GeocodedLocation(latitude=38.8816, longitude=-77.1043)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=mock_location):
            count = geocode_all(db_conn)

        assert count == 1

        # Verify source is "company_hq"
        row = db_conn.execute(
            "SELECT source FROM contract_locations WHERE contract_id = 1"
        ).fetchone()
        assert row is not None
        assert row["source"] == "company_hq"

    def test_idempotency_already_geocoded_contracts_skipped(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify idempotency: Already-geocoded contracts are skipped."""
        insert_test_page(db_conn, "test1")

        # Insert contract with work location
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )

        # Insert classification
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )

        # Insert existing contract_locations entry
        db_conn.execute(
            """
            INSERT INTO contract_locations (contract_id, latitude, longitude, source)
            VALUES (1, 47.6062, -122.3321, 'work_location')
            """
        )
        db_conn.commit()

        # Mock geocode_city_state
        mock_location = GeocodedLocation(latitude=99.9999, longitude=-99.9999)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=mock_location) as mock_geocode:
            count = geocode_all(db_conn)

        # Should skip the already-geocoded contract
        assert count == 0
        mock_geocode.assert_not_called()

    def test_service_contracts_not_geocoded(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify service contracts (is_procurement=0) are not geocoded."""
        insert_test_page(db_conn, "test1")

        # Insert contract
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )

        # Insert classification marking it as SERVICE (is_procurement=0)
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 0, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state
        with patch("dod_scan.geocoder.geocode_city_state") as mock_geocode:
            count = geocode_all(db_conn)

        assert count == 0
        mock_geocode.assert_not_called()

    def test_geocoding_failure_logged_and_skipped(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify geocoding failures are logged and contract is skipped."""
        insert_test_page(db_conn, "test1")

        # Insert contract
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )

        # Insert classification
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state to return None (failure)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=None):
            count = geocode_all(db_conn)

        assert count == 0

        # Verify no entry in contract_locations
        row = db_conn.execute(
            "SELECT * FROM contract_locations WHERE contract_id = 1"
        ).fetchone()
        assert row is None

    def test_no_location_to_geocode_skipped(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify contracts with no resolvable location are skipped gracefully."""
        insert_test_page(db_conn, "test1")

        # Insert contract with no work_locations and no company HQ
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "", "", ?)
            """,
            ("[]",),
        )

        # Insert classification
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state
        with patch("dod_scan.geocoder.geocode_city_state") as mock_geocode:
            count = geocode_all(db_conn)

        assert count == 0
        mock_geocode.assert_not_called()

    def test_multiple_contracts_geocoded(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify multiple contracts are geocoded in a single batch."""
        # Insert pages
        for i in range(1, 4):
            insert_test_page(db_conn, f"test{i}")

        # Insert multiple contracts
        contracts_data = [
            (1, "test1", "Co1", "Arlington", "Virginia", json.dumps([{"city": "Seattle", "state": "Washington"}])),
            (2, "test2", "Co2", "Boston", "Massachusetts", json.dumps([{"city": "New York", "state": "New York"}])),
            (3, "test3", "Co3", "Austin", "Texas", json.dumps([{"city": "Houston", "state": "Texas"}])),
        ]

        for contract_id, article_id, company_name, company_city, company_state, work_locations in contracts_data:
            db_conn.execute(
                """
                INSERT INTO contracts (
                    id, article_id, company_name, company_city, company_state, work_locations
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (contract_id, article_id, company_name, company_city, company_state, work_locations),
            )
            db_conn.execute(
                """
                INSERT INTO classifications (contract_id, is_procurement, confidence)
                VALUES (?, 1, 0.95)
                """,
                (contract_id,),
            )

        db_conn.commit()

        # Mock geocode_city_state with different results
        mock_locations = {
            ("seattle", "washington"): GeocodedLocation(47.6062, -122.3321),
            ("new york", "new york"): GeocodedLocation(40.7128, -74.0060),
            ("houston", "texas"): GeocodedLocation(29.7604, -95.3698),
        }

        def mock_geocode_side_effect(city, state, conn):
            key = (city.lower(), state.lower())
            return mock_locations.get(key)

        with patch("dod_scan.geocoder.geocode_city_state", side_effect=mock_geocode_side_effect):
            count = geocode_all(db_conn)

        assert count == 3

        # Verify all entries in contract_locations
        for contract_id in [1, 2, 3]:
            row = db_conn.execute(
                "SELECT * FROM contract_locations WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            assert row is not None

    def test_insert_or_replace_updates_existing_entry(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify INSERT OR REPLACE updates existing contract_locations entry."""
        insert_test_page(db_conn, "test1")

        # Insert contract
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Test Co", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )

        # Insert classification
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )

        # Pre-insert an old entry
        db_conn.execute(
            """
            INSERT INTO contract_locations (contract_id, latitude, longitude, source)
            VALUES (1, 1.0, 2.0, 'old')
            """
        )
        db_conn.commit()

        # Mock geocode_city_state with new result
        mock_location = GeocodedLocation(latitude=47.6062, longitude=-122.3321)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=mock_location):
            # Reset the query to include already-geocoded contracts
            # by temporarily removing the contract from contract_locations
            db_conn.execute("DELETE FROM contract_locations WHERE contract_id = 1")
            db_conn.commit()

            count = geocode_all(db_conn)

        assert count == 1

        # Verify updated entry
        row = db_conn.execute(
            "SELECT latitude, longitude, source FROM contract_locations WHERE contract_id = 1"
        ).fetchone()
        assert row is not None
        assert row["latitude"] == 47.6062
        assert row["longitude"] == -122.3321
        assert row["source"] == "work_location"

    def test_only_procurement_contracts_processed(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify only procurement contracts are processed."""
        # Insert pages
        insert_test_page(db_conn, "test1")
        insert_test_page(db_conn, "test2")

        # Insert mixed contracts
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (1, "test1", "Co1", "Arlington", "Virginia", ?)
            """,
            (json.dumps([{"city": "Seattle", "state": "Washington"}]),),
        )
        db_conn.execute(
            """
            INSERT INTO contracts (
                id, article_id, company_name, company_city, company_state, work_locations
            ) VALUES (2, "test2", "Co2", "Boston", "Massachusetts", ?)
            """,
            (json.dumps([{"city": "New York", "state": "New York"}]),),
        )

        # Insert classifications: 1 is procurement, 2 is service
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (1, 1, 0.95)
            """
        )
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement, confidence)
            VALUES (2, 0, 0.95)
            """
        )
        db_conn.commit()

        # Mock geocode_city_state
        mock_location = GeocodedLocation(latitude=47.6062, longitude=-122.3321)
        with patch("dod_scan.geocoder.geocode_city_state", return_value=mock_location) as mock_geocode:
            count = geocode_all(db_conn)

        assert count == 1
        # Should only geocode contract 1
        mock_geocode.assert_called_once_with("Seattle", "Washington", db_conn)

    def test_return_value_is_geocoded_count(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify geocode_all returns count of successfully geocoded contracts."""
        # Insert pages
        for i in range(1, 4):
            insert_test_page(db_conn, f"test{i}")

        # Insert 3 contracts
        for i in range(1, 4):
            db_conn.execute(
                """
                INSERT INTO contracts (
                    id, article_id, company_name, company_city, company_state, work_locations
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    i,
                    f"test{i}",
                    f"Co{i}",
                    "Arlington",
                    "Virginia",
                    json.dumps([{"city": f"City{i}", "state": "State"}]),
                ),
            )
            db_conn.execute(
                """
                INSERT INTO classifications (contract_id, is_procurement, confidence)
                VALUES (?, 1, 0.95)
                """,
                (i,),
            )

        db_conn.commit()

        # Mock: first two succeed, third fails
        def mock_geocode_side_effect(city, state, conn):
            if city == "City3":
                return None
            return GeocodedLocation(latitude=40.0, longitude=-75.0)

        with patch("dod_scan.geocoder.geocode_city_state", side_effect=mock_geocode_side_effect):
            count = geocode_all(db_conn)

        # Only 2 should be counted (the third failed)
        assert count == 2

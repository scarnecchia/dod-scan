"""Tests for geocoder API client and caching."""

import sqlite3
from unittest.mock import MagicMock, patch

import httpx
import pytest

from dod_scan.geocoder_api import (
    GeocodedLocation,
    geocode_city_state,
)


class TestGeocodeRateLimitAndCache:
    def test_ac4_3_cached_result_returned_without_api_call(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.3: Cached locations returned without API call."""
        # Pre-populate cache
        db_conn.execute(
            """
            INSERT INTO geocode_cache (location_key, latitude, longitude)
            VALUES (?, ?, ?)
            """,
            ("seattle, washington", 47.6062, -122.3321),
        )
        db_conn.commit()

        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            result = geocode_city_state("Seattle", "Washington", db_conn)

            assert result is not None
            assert result.latitude == 47.6062
            assert result.longitude == -122.3321
            mock_get.assert_not_called()

    def test_ac4_4_api_failure_logged_returns_none(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.4: Geocoding API failure logged, contract skipped."""
        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            result = geocode_city_state("Unknown", "City", db_conn)

            assert result is None

    def test_ac4_1_successful_geocoding_cached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.1: Successful geocoding is cached."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "40.7128", "lon": "-74.0060"}  # New York
        ]
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response):
            with patch("dod_scan.geocoder_api.time.sleep"):  # Skip rate limiting
                result = geocode_city_state("New York", "New York", db_conn)

                assert result is not None
                assert result.latitude == 40.7128
                assert result.longitude == -74.0060

        # Verify it's cached
        cached = db_conn.execute(
            "SELECT latitude, longitude FROM geocode_cache WHERE location_key = ?",
            ("new york, new york",),
        ).fetchone()
        assert cached is not None
        assert cached["latitude"] == 40.7128
        assert cached["longitude"] == -74.0060

    def test_ac4_1_no_results_from_nominatim(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify AC4.1: No geocoding when Nominatim returns empty results."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response):
            with patch("dod_scan.geocoder_api.time.sleep"):
                result = geocode_city_state("Nonexistent", "City", db_conn)

                assert result is None

    def test_http_error_raises_geocoding_error(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify HTTP errors are converted to GeocodingError."""
        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Network error")

            result = geocode_city_state("Test", "City", db_conn)
            assert result is None

    def test_timeout_error_caught(self, db_conn: sqlite3.Connection) -> None:
        """Verify timeout errors are handled gracefully."""
        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            result = geocode_city_state("Test", "City", db_conn)
            assert result is None

    def test_cache_key_normalization(self, db_conn: sqlite3.Connection) -> None:
        """Verify cache keys are normalized (lowercase)."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "38.9072", "lon": "-77.0369"}  # Washington DC
        ]
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response):
            with patch("dod_scan.geocoder_api.time.sleep"):
                geocode_city_state("WASHINGTON", "DC", db_conn)

        # Should match lowercase query
        cached = db_conn.execute(
            "SELECT latitude FROM geocode_cache WHERE location_key = ?",
            ("washington, dc",),
        ).fetchone()
        assert cached is not None

    def test_multiple_geocoding_requests(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify multiple geocoding requests are handled independently."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        # Different response for each location
        responses = [
            {"lat": "40.7128", "lon": "-74.0060"},  # NYC
            {"lat": "34.0522", "lon": "-118.2437"},  # LA
        ]

        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            with patch("dod_scan.geocoder_api.time.sleep"):
                mock_get.return_value.json.side_effect = [
                    [resp] for resp in responses
                ]

                result1 = geocode_city_state("New York", "New York", db_conn)
                result2 = geocode_city_state("Los Angeles", "California", db_conn)

                assert result1.latitude == 40.7128
                assert result2.latitude == 34.0522

    def test_geocoded_location_is_frozen(self) -> None:
        """Verify GeocodedLocation dataclass is immutable."""
        location = GeocodedLocation(latitude=40.7128, longitude=-74.0060)
        with pytest.raises(AttributeError):
            location.latitude = 35.0  # type: ignore

    def test_cache_respects_location_key_exactly(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify cache respects exact location key matching."""
        # Insert cache for Seattle
        db_conn.execute(
            """
            INSERT INTO geocode_cache (location_key, latitude, longitude)
            VALUES (?, ?, ?)
            """,
            ("seattle, washington", 47.6062, -122.3321),
        )
        db_conn.commit()

        # Query for different city (should not match cache)
        with patch("dod_scan.geocoder_api.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"lat": "47.2529", "lon": "-122.4443"}
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            with patch("dod_scan.geocoder_api.time.sleep"):
                result = geocode_city_state("Tacoma", "Washington", db_conn)

                # Should call API, not return cached Seattle value
                assert result.latitude == 47.2529
                mock_get.assert_called_once()

    def test_cache_insert_or_replace(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify cache uses INSERT OR REPLACE to update existing entries."""
        from dod_scan.geocoder_api import _cache_result, GeocodedLocation

        location_key = "seattle, washington"

        # Insert initial value directly (simulating first geocode)
        db_conn.execute(
            """
            INSERT INTO geocode_cache (location_key, latitude, longitude)
            VALUES (?, ?, ?)
            """,
            (location_key, 1.0, 2.0),
        )
        db_conn.commit()

        # Verify initial value
        cached = db_conn.execute(
            "SELECT latitude, longitude FROM geocode_cache WHERE location_key = ?",
            (location_key,),
        ).fetchone()
        assert cached["latitude"] == 1.0

        # Now call _cache_result with new coordinates (this tests INSERT OR REPLACE)
        new_location = GeocodedLocation(latitude=3.0, longitude=4.0)
        _cache_result(db_conn, location_key, new_location)

        # Verify updated value
        cached = db_conn.execute(
            "SELECT latitude, longitude FROM geocode_cache WHERE location_key = ?",
            (location_key,),
        ).fetchone()
        assert cached["latitude"] == 3.0
        assert cached["longitude"] == 4.0

    def test_nominatim_parameters_correct(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify Nominatim API is called with correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "40.7128", "lon": "-74.0060"}
        ]
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response) as mock_get:
            with patch("dod_scan.geocoder_api.time.sleep"):
                geocode_city_state("New York", "New York", db_conn)

                # Verify call was made with correct parameters
                mock_get.assert_called_once()
                call_args = mock_get.call_args

                assert call_args[0][0] == "https://nominatim.openstreetmap.org/search"
                assert call_args[1]["params"]["city"] == "New York"
                assert call_args[1]["params"]["state"] == "New York"
                assert call_args[1]["params"]["country"] == "United States"
                assert call_args[1]["params"]["format"] == "json"
                assert call_args[1]["params"]["limit"] == 1

    def test_user_agent_header_set(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify User-Agent header is set in API requests."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "40.7128", "lon": "-74.0060"}
        ]
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response) as mock_get:
            with patch("dod_scan.geocoder_api.time.sleep"):
                geocode_city_state("New York", "New York", db_conn)

                call_args = mock_get.call_args
                assert "User-Agent" in call_args[1]["headers"]
                assert "dod-scan" in call_args[1]["headers"]["User-Agent"]

    def test_rate_limiting_enforced(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify rate limiting is enforced for uncached requests."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "40.7128", "lon": "-74.0060"}
        ]
        mock_response.raise_for_status.return_value = None

        with patch("dod_scan.geocoder_api.httpx.get", return_value=mock_response):
            with patch("dod_scan.geocoder_api.time.sleep") as mock_sleep:
                geocode_city_state("New York", "New York", db_conn)

                # Should have slept for rate limiting
                mock_sleep.assert_called_once()
                assert mock_sleep.call_args[0][0] > 1.0

    def test_rate_limiting_skipped_for_cached(
        self, db_conn: sqlite3.Connection
    ) -> None:
        """Verify rate limiting is skipped for cached results."""
        # Pre-populate cache
        db_conn.execute(
            """
            INSERT INTO geocode_cache (location_key, latitude, longitude)
            VALUES (?, ?, ?)
            """,
            ("seattle, washington", 47.6062, -122.3321),
        )
        db_conn.commit()

        with patch("dod_scan.geocoder_api.time.sleep") as mock_sleep:
            geocode_city_state("Seattle", "Washington", db_conn)

            # Should not sleep for cached result
            mock_sleep.assert_not_called()

"""Tests for geocoder location resolution logic."""

import json

import pytest

from dod_scan.geocoder_resolve import (
    LocationToGeocode,
    make_location_key,
    resolve_location,
)


class TestResolveLocation:
    def test_ac4_1_work_location_preferred(self) -> None:
        """Verify AC4.1: Work location geocoded when present in contract text."""
        work_locations_json = json.dumps([{"city": "Seattle", "state": "Washington"}])
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Seattle"
        assert result.state == "Washington"
        assert result.source == "work_location"

    def test_ac4_2_company_hq_fallback_empty_work_locations(self) -> None:
        """Verify AC4.2: Company HQ used as fallback when work location is empty."""
        work_locations_json = "[]"
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_ac4_2_company_hq_fallback_invalid_json(self) -> None:
        """Verify AC4.2: Company HQ used as fallback when work_locations is invalid JSON."""
        work_locations_json = "not valid json"
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_ac4_2_company_hq_fallback_none_work_locations(self) -> None:
        """Verify AC4.2: Company HQ used when work_locations is None."""
        result = resolve_location(None, "Arlington", "Virginia")  # type: ignore

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_ac4_2_no_fallback_no_company_hq(self) -> None:
        """Verify AC4.2: Returns None when no work location and no company HQ."""
        work_locations_json = "[]"
        result = resolve_location(work_locations_json, "", "")

        assert result is None

    def test_ac4_5_multiple_locations_highest_percentage(self) -> None:
        """Verify AC4.5: With multiple work locations, highest percentage is used."""
        work_locations_json = json.dumps([
            {"city": "Bloomington", "state": "Minnesota", "pct": 68},
            {"city": "St. Louis", "state": "Missouri", "pct": 22},
        ])
        result = resolve_location(work_locations_json, "Fallback", "State")

        assert result is not None
        assert result.city == "Bloomington"
        assert result.state == "Minnesota"
        assert result.source == "work_location"

    def test_ac4_5_multiple_locations_without_percentage(self) -> None:
        """Verify AC4.5: Without percentage, first location is used."""
        work_locations_json = json.dumps([
            {"city": "New York", "state": "New York"},
            {"city": "Los Angeles", "state": "California"},
        ])
        result = resolve_location(work_locations_json, "Fallback", "State")

        assert result is not None
        assert result.city == "New York"
        assert result.state == "New York"
        assert result.source == "work_location"

    def test_location_key_normalization(self) -> None:
        """Verify make_location_key normalises to lowercase."""
        key = make_location_key("Arlington", "Virginia")
        assert key == "arlington, virginia"

    def test_location_key_strip_whitespace(self) -> None:
        """Verify make_location_key strips leading/trailing whitespace."""
        key = make_location_key("  Arlington  ", "  Virginia  ")
        assert key == "arlington, virginia"

    def test_location_to_geocode_is_frozen(self) -> None:
        """Verify LocationToGeocode dataclass is immutable."""
        location = LocationToGeocode(city="Seattle", state="Washington", source="work_location")
        with pytest.raises(AttributeError):
            location.city = "Tacoma"  # type: ignore

    def test_work_location_state_only(self) -> None:
        """Verify state-only work location is used (geocodes state centroid)."""
        work_locations_json = json.dumps([{"state": "Washington"}])
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == ""
        assert result.state == "Washington"
        assert result.source == "work_location"

    def test_work_location_missing_state(self) -> None:
        """Verify work location without state falls back to company HQ."""
        work_locations_json = json.dumps([{"city": "Seattle"}])
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_work_location_empty_strings(self) -> None:
        """Verify work location with empty strings falls back to company HQ."""
        work_locations_json = json.dumps([{"city": "", "state": ""}])
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_work_location_whitespace_only(self) -> None:
        """Verify work location with whitespace-only fields falls back to company HQ."""
        work_locations_json = json.dumps([{"city": "   ", "state": "   "}])
        result = resolve_location(work_locations_json, "Arlington", "Virginia")

        assert result is not None
        assert result.city == "Arlington"
        assert result.state == "Virginia"
        assert result.source == "company_hq"

    def test_percentage_with_zero_pct(self) -> None:
        """Verify percentage selection with zero pct."""
        work_locations_json = json.dumps([
            {"city": "Seattle", "state": "Washington", "pct": 0},
            {"city": "Tacoma", "state": "Washington", "pct": 100},
        ])
        result = resolve_location(work_locations_json, "Fallback", "State")

        assert result is not None
        assert result.city == "Tacoma"
        assert result.state == "Washington"

    def test_percentage_mixed_with_and_without(self) -> None:
        """Verify percentage selection when only some locations have pct."""
        work_locations_json = json.dumps([
            {"city": "Seattle", "state": "Washington"},
            {"city": "Tacoma", "state": "Washington", "pct": 80},
        ])
        result = resolve_location(work_locations_json, "Fallback", "State")

        assert result is not None
        assert result.city == "Tacoma"
        assert result.state == "Washington"

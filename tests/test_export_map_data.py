"""Tests for GeoJSON construction logic."""

import json

import pytest

from dod_scan.export_kml_build import ContractPin
from dod_scan.export_map_data import (
    get_unique_branches,
    pins_to_geojson,
)


class TestPinsToGeojson:
    """Tests for AC6.1 and AC6.2: GeoJSON generation from pins."""

    def test_produces_valid_featurecollection(self) -> None:
        """Output is valid JSON FeatureCollection."""
        pins = [
            ContractPin(
                company_name="Test Co",
                dollar_amount=1e6,
                contract_number="ABC123",
                branch="ARMY",
                raw_text="Contract details here",
                completion_date="2026-03-15",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        assert geojson["type"] == "FeatureCollection"
        assert isinstance(geojson["features"], list)

    def test_correct_number_of_features(self) -> None:
        """Number of features matches number of pins."""
        pins = [
            ContractPin(
                company_name=f"Co {i}",
                dollar_amount=1e6,
                contract_number=f"ABC{i}",
                branch="ARMY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0 + i,
                longitude=-74.0 + i,
                publish_date="2026-03-12",
            )
            for i in range(5)
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        assert len(geojson["features"]) == 5

    def test_feature_has_point_geometry(self) -> None:
        """Each feature has Point geometry."""
        pins = [
            ContractPin(
                company_name="Test Co",
                dollar_amount=1e6,
                contract_number="ABC123",
                branch="ARMY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        feature = geojson["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"

    def test_coordinates_are_lon_lat_order(self) -> None:
        """GeoJSON coordinates are [longitude, latitude] order."""
        pins = [
            ContractPin(
                company_name="Test Co",
                dollar_amount=1e6,
                contract_number="ABC123",
                branch="ARMY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        coords = geojson["features"][0]["geometry"]["coordinates"]
        assert coords == [-74.0060, 40.7128]

    def test_properties_include_all_required_fields(self) -> None:
        """Feature properties include all required contract fields."""
        pins = [
            ContractPin(
                company_name="Acme Corp",
                dollar_amount=1234567.89,
                contract_number="FA8730-23-C-0025",
                branch="AIR FORCE",
                raw_text="Contract description text here",
                completion_date="2026-05-20",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        props = geojson["features"][0]["properties"]

        assert props["company_name"] == "Acme Corp"
        assert props["dollar_amount"] == 1234567.89
        assert props["dollar_display"] == "$1,234,568"
        assert props["contract_number"] == "FA8730-23-C-0025"
        assert props["branch"] == "AIR FORCE"
        assert props["completion_date"] == "2026-05-20"
        assert props["publish_date"] == "2026-03-12"

    def test_description_truncated_to_500_chars(self) -> None:
        """Description property is truncated to first 500 characters."""
        long_text = "x" * 1000
        pins = [
            ContractPin(
                company_name="Test Co",
                dollar_amount=1e6,
                contract_number="ABC123",
                branch="ARMY",
                raw_text=long_text,
                completion_date="2026-03-15",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        description = geojson["features"][0]["properties"]["description"]
        assert len(description) == 500
        assert description == "x" * 500

    def test_empty_pins_list_produces_empty_featurecollection(self) -> None:
        """Empty pins list produces valid FeatureCollection with no features."""
        geojson_str = pins_to_geojson([])
        geojson = json.loads(geojson_str)
        assert geojson["type"] == "FeatureCollection"
        assert geojson["features"] == []

    def test_multiple_pins_with_different_branches(self) -> None:
        """Multiple pins with different branches all included."""
        pins = [
            ContractPin(
                company_name=f"Co {i}",
                dollar_amount=1e6,
                contract_number=f"ABC{i}",
                branch=branch,
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0 + i,
                longitude=-74.0 + i,
                publish_date="2026-03-12",
            )
            for i, branch in enumerate(["ARMY", "NAVY", "AIR FORCE"])
        ]
        geojson_str = pins_to_geojson(pins)
        geojson = json.loads(geojson_str)
        branches = [f["properties"]["branch"] for f in geojson["features"]]
        assert "ARMY" in branches
        assert "NAVY" in branches
        assert "AIR FORCE" in branches


class TestGetUniqueBranches:
    """Tests for AC6.3: unique branch extraction."""

    def test_returns_sorted_unique_branches(self) -> None:
        """Returns unique branch names in sorted order."""
        pins = [
            ContractPin(
                company_name=f"Co {i}",
                dollar_amount=1e6,
                contract_number=f"ABC{i}",
                branch=branch,
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0 + i,
                longitude=-74.0 + i,
                publish_date="2026-03-12",
            )
            for i, branch in enumerate(["NAVY", "ARMY", "AIR FORCE", "ARMY"])
        ]
        branches = get_unique_branches(pins)
        assert branches == ["AIR FORCE", "ARMY", "NAVY"]

    def test_filters_out_empty_branches(self) -> None:
        """Empty branch strings are excluded."""
        pins = [
            ContractPin(
                company_name="Co 1",
                dollar_amount=1e6,
                contract_number="ABC1",
                branch="ARMY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0,
                longitude=-74.0,
                publish_date="2026-03-12",
            ),
            ContractPin(
                company_name="Co 2",
                dollar_amount=1e6,
                contract_number="ABC2",
                branch="",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0,
                longitude=-74.0,
                publish_date="2026-03-12",
            ),
        ]
        branches = get_unique_branches(pins)
        assert branches == ["ARMY"]
        assert "" not in branches

    def test_empty_pins_list_returns_empty_list(self) -> None:
        """Empty pins list returns empty list."""
        branches = get_unique_branches([])
        assert branches == []

    def test_all_pins_with_same_branch(self) -> None:
        """All pins with same branch returns single-element list."""
        pins = [
            ContractPin(
                company_name=f"Co {i}",
                dollar_amount=1e6,
                contract_number=f"ABC{i}",
                branch="ARMY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0 + i,
                longitude=-74.0 + i,
                publish_date="2026-03-12",
            )
            for i in range(3)
        ]
        branches = get_unique_branches(pins)
        assert branches == ["ARMY"]

    def test_single_pin_returns_single_branch(self) -> None:
        """Single pin returns single branch."""
        pins = [
            ContractPin(
                company_name="Test Co",
                dollar_amount=1e6,
                contract_number="ABC123",
                branch="NAVY",
                raw_text="details",
                completion_date="2026-03-15",
                latitude=40.0,
                longitude=-74.0,
                publish_date="2026-03-12",
            ),
        ]
        branches = get_unique_branches(pins)
        assert branches == ["NAVY"]

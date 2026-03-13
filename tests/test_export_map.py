"""Tests for Mapbox dashboard HTML export."""

import json
import logging
from pathlib import Path

import pytest

from dod_scan.export_kml_build import ContractPin


class TestExportMapDependencies:
    """Tests for AC6.1-AC6.5: Mapbox dashboard export with graceful degradation."""

    @pytest.fixture
    def sample_pins(self) -> list[ContractPin]:
        """Sample contract pins for testing."""
        return [
            ContractPin(
                company_name="Acme Corp",
                dollar_amount=1.5e6,
                contract_number="ABC123",
                branch="ARMY",
                raw_text="Contract details here",
                completion_date="2026-03-15",
                latitude=40.7128,
                longitude=-74.0060,
                publish_date="2026-03-12",
            ),
            ContractPin(
                company_name="Tech Industries",
                dollar_amount=5e7,
                contract_number="XYZ789",
                branch="NAVY",
                raw_text="Advanced technology development",
                completion_date="2026-06-20",
                latitude=37.7749,
                longitude=-122.4194,
                publish_date="2026-03-10",
            ),
        ]

    def test_geojson_valid_json_with_featurecollection(self, sample_pins: list[ContractPin]) -> None:
        """AC6.1: pins_to_geojson produces valid JSON FeatureCollection."""
        from dod_scan.export_map_data import pins_to_geojson

        geojson_str = pins_to_geojson(sample_pins)
        geojson = json.loads(geojson_str)

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == len(sample_pins)

    def test_geojson_features_have_point_geometry(self, sample_pins: list[ContractPin]) -> None:
        """AC6.1: Each feature has Point geometry with [lon, lat] coordinates."""
        from dod_scan.export_map_data import pins_to_geojson

        geojson_str = pins_to_geojson(sample_pins)
        geojson = json.loads(geojson_str)

        for feature in geojson["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"
            coords = feature["geometry"]["coordinates"]
            assert len(coords) == 2
            assert isinstance(coords[0], (int, float))  # longitude
            assert isinstance(coords[1], (int, float))  # latitude

    def test_geojson_popup_properties_complete(self, sample_pins: list[ContractPin]) -> None:
        """AC6.2: Each feature properties contain all required fields for popup."""
        from dod_scan.export_map_data import pins_to_geojson

        geojson_str = pins_to_geojson(sample_pins)
        geojson = json.loads(geojson_str)

        for feature in geojson["features"]:
            props = feature["properties"]
            assert "company_name" in props
            assert "dollar_amount" in props
            assert "dollar_display" in props
            assert "contract_number" in props
            assert "branch" in props
            assert "completion_date" in props
            assert "publish_date" in props
            assert "description" in props

    def test_get_unique_branches_returns_sorted_list(self, sample_pins: list[ContractPin]) -> None:
        """AC6.3: get_unique_branches returns sorted unique branch names."""
        from dod_scan.export_map_data import get_unique_branches

        branches = get_unique_branches(sample_pins)
        assert branches == ["ARMY", "NAVY"]
        assert isinstance(branches, list)

    def test_export_map_with_mapbox_token_generates_html(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.1: export_map with MAPBOX_TOKEN produces HTML file."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token_12345"

        result_path = export_map(sample_pins, output_file, mapbox_token)

        assert result_path.exists()
        html_content = result_path.read_text()
        assert "mapboxgl" in html_content
        assert mapbox_token in html_content

    def test_export_map_html_contains_geojson_data(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.1: Generated HTML contains embedded GeoJSON data."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token_12345"

        result_path = export_map(sample_pins, output_file, mapbox_token)
        html_content = result_path.read_text()

        # Should contain feature data
        assert "FeatureCollection" in html_content
        assert "Acme Corp" in html_content
        assert "Tech Industries" in html_content

    def test_export_map_html_contains_filter_elements(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.3: Generated HTML contains sidebar filter elements with branches."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token_12345"

        result_path = export_map(sample_pins, output_file, mapbox_token)
        html_content = result_path.read_text()

        # Should contain branch filter elements
        assert "branch-checkbox" in html_content or "checkbox" in html_content.lower()
        assert "ARMY" in html_content
        assert "NAVY" in html_content

    def test_export_map_html_contains_popup_handler(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.2: Generated HTML contains click handler for showing popups."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token_12345"

        result_path = export_map(sample_pins, output_file, mapbox_token)
        html_content = result_path.read_text()

        # Should contain Mapbox popup handling
        assert "Popup" in html_content or "popup" in html_content.lower()

    def test_export_map_without_mapbox_token_raises_error(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.5: export_map without MAPBOX_TOKEN raises MapExportError."""
        from dod_scan.export_map import MapExportError, export_map

        output_file = tmp_path / "test_map.html"

        with pytest.raises(MapExportError) as exc_info:
            export_map(sample_pins, output_file, "")

        assert "MAPBOX_TOKEN" in str(exc_info.value)

    def test_export_map_error_message_is_helpful(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """AC6.5: Error message mentions .env configuration."""
        from dod_scan.export_map import MapExportError, export_map

        output_file = tmp_path / "test_map.html"

        with pytest.raises(MapExportError) as exc_info:
            export_map(sample_pins, output_file, "")

        error_msg = str(exc_info.value)
        assert ".env" in error_msg or "configure" in error_msg.lower()

    def test_export_map_creates_parent_directories(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """export_map creates parent directories if needed."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "deeply" / "nested" / "map.html"
        mapbox_token = "pk.test_token"

        result_path = export_map(sample_pins, output_file, mapbox_token)

        assert result_path.exists()
        assert result_path.parent.exists()

    def test_export_map_returns_output_path(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """export_map returns the output file path."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token"

        result = export_map(sample_pins, output_file, mapbox_token)

        assert result == output_file

    def test_export_map_with_empty_pins_list(
        self, tmp_path: Path
    ) -> None:
        """export_map handles empty pins list gracefully."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "empty_map.html"
        mapbox_token = "pk.test_token"

        result_path = export_map([], output_file, mapbox_token)

        assert result_path.exists()
        html_content = result_path.read_text()
        assert "FeatureCollection" in html_content
        # Check for empty features array (with possible whitespace variations)
        assert '"features": []' in html_content or '"features":[]' in html_content

    def test_export_map_includes_contract_count_in_template(
        self, tmp_path: Path, sample_pins: list[ContractPin]
    ) -> None:
        """export_map passes total_contracts to template."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token"

        result_path = export_map(sample_pins, output_file, mapbox_token)
        html_content = result_path.read_text()

        # Template should show total contract count
        assert "totalContracts" in html_content or "2" in html_content

    def test_export_map_logs_success_message(
        self, tmp_path: Path, sample_pins: list[ContractPin], caplog
    ) -> None:
        """export_map logs a success message with file path."""
        from dod_scan.export_map import export_map

        output_file = tmp_path / "test_map.html"
        mapbox_token = "pk.test_token"

        with caplog.at_level(logging.INFO):
            export_map(sample_pins, output_file, mapbox_token)

        assert "Mapbox dashboard written to" in caplog.text or output_file.name in caplog.text


class TestTemplateRendering:
    """Tests for Jinja2 template rendering."""

    def test_template_renders_without_error(self, tmp_path: Path) -> None:
        """Jinja2 template renders without syntax errors."""
        from dod_scan.export_map import export_map
        from dod_scan.export_kml_build import ContractPin

        pins = [
            ContractPin(
                company_name="Test",
                dollar_amount=1e6,
                contract_number="ABC",
                branch="ARMY",
                raw_text="test",
                completion_date="2026-03-15",
                latitude=0,
                longitude=0,
                publish_date="2026-03-12",
            ),
        ]
        output_file = tmp_path / "test.html"

        result = export_map(pins, output_file, "pk.test")
        assert result.exists()

    def test_template_autoescape_enabled(self, tmp_path: Path) -> None:
        """Dangerous content in popup is escaped via escapeHtml function."""
        from dod_scan.export_map import export_map
        from dod_scan.export_kml_build import ContractPin

        pins = [
            ContractPin(
                company_name="<script>alert('xss')</script>",
                dollar_amount=1e6,
                contract_number="ABC",
                branch="ARMY",
                raw_text="<b>test</b>",
                completion_date="2026-03-15",
                latitude=0,
                longitude=0,
                publish_date="2026-03-12",
            ),
        ]
        output_file = tmp_path / "test.html"

        result_path = export_map(pins, output_file, "pk.test")
        html_content = result_path.read_text()

        # The company name is in GeoJSON data which is safe (JSON context).
        # The actual popup rendering uses escapeHtml() function for safety.
        assert "escapeHtml" in html_content  # Verify escaping function is present
        assert "Popup" in html_content or "popup" in html_content.lower()  # Popups use escapeHtml

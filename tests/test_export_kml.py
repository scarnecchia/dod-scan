"""Tests for KML export orchestration."""

import sqlite3
from pathlib import Path

import pytest

from dod_scan.export_kml import export_kml, query_contract_pins
from dod_scan.export_kml_build import ContractPin


@pytest.fixture
def populated_db_conn(db_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Insert test data into database."""
    # Insert pages
    db_conn.execute(
        """
        INSERT INTO pages (article_id, url, publish_date)
        VALUES
            ('page1', 'http://example.com/page1', '2026-03-10'),
            ('page2', 'http://example.com/page2', '2026-03-12'),
            ('page3', 'http://example.com/page3', '2026-03-15')
        """
    )

    # Insert contracts
    db_conn.execute(
        """
        INSERT INTO contracts (
            article_id, company_name, dollar_amount, contract_number,
            branch, raw_text, completion_date
        )
        VALUES
            ('page1', 'Acme Corp', 1500000.0, 'FAA001', 'ARMY',
             'Acme Corp contract for supplies and services in Arlington, Virginia.', '2026-06-01'),
            ('page1', 'Boeing Defense', 5000000000.0, 'FAA002', 'AIR FORCE',
             'Boeing Defense contract for aircraft systems and upgrades in Seattle, Washington.', '2026-12-31'),
            ('page2', 'Raytheon Tech', 250000000.0, 'FAA003', 'NAVY',
             'Raytheon Tech contract for missile systems and components in Waltham, Massachusetts.', '2026-09-15'),
            ('page3', 'Lockheed Martin', 3000000000.0, 'FAA004', 'ARMY',
             'Lockheed Martin contract for defense systems in Grand Prairie, Texas.', '2027-03-30')
        """
    )

    # Insert classifications (all are procurement)
    db_conn.execute(
        """
        INSERT INTO classifications (contract_id, is_procurement)
        VALUES (1, 1), (2, 1), (3, 1), (4, 1)
        """
    )

    # Insert contract locations (with realistic coordinates)
    db_conn.execute(
        """
        INSERT INTO contract_locations (contract_id, latitude, longitude, source)
        VALUES
            (1, 38.8816, -77.1043, 'geocoder'),  -- Arlington, VA
            (2, 47.6062, -122.3321, 'geocoder'), -- Seattle, WA
            (3, 42.3868, -71.1221, 'geocoder'),  -- Waltham, MA
            (4, 32.6345, -97.2867, 'geocoder')   -- Grand Prairie, TX
        """
    )

    db_conn.commit()
    return db_conn


class TestQueryContractPins:
    """Tests for query_contract_pins function."""

    def test_returns_list_of_contract_pins(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify query_contract_pins returns list of ContractPin objects."""
        pins = query_contract_pins(populated_db_conn, None, None)

        assert isinstance(pins, list)
        assert len(pins) > 0
        assert all(isinstance(p, ContractPin) for p in pins)

    def test_contract_pin_has_required_fields(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify ContractPin contains all required fields."""
        pins = query_contract_pins(populated_db_conn, None, None)
        assert len(pins) > 0

        pin = pins[0]
        assert pin.company_name
        assert pin.dollar_amount > 0
        assert pin.contract_number
        assert pin.branch
        assert pin.raw_text
        assert pin.completion_date
        assert pin.latitude is not None
        assert pin.longitude is not None
        assert pin.publish_date

    def test_filters_by_publish_date_since(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify --since DATE filters to contracts from that date onward (AC5.4)."""
        # Query with since='2026-03-12'
        pins = query_contract_pins(populated_db_conn, since="2026-03-12", branch=None)

        # Should get 2 contracts (Raytheon on page2, Lockheed on page3)
        assert len(pins) == 2

        # All should have publish_date >= 2026-03-12
        for pin in pins:
            assert pin.publish_date >= "2026-03-12"

    def test_filters_by_branch_case_insensitive(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify --branch ARMY filters to specified branch only (AC5.5)."""
        pins = query_contract_pins(populated_db_conn, since=None, branch="ARMY")

        assert len(pins) == 2
        assert all(p.branch == "ARMY" for p in pins)

    def test_branch_filter_case_insensitive(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify branch filter is case-insensitive."""
        pins_upper = query_contract_pins(populated_db_conn, since=None, branch="ARMY")
        pins_lower = query_contract_pins(populated_db_conn, since=None, branch="army")
        pins_mixed = query_contract_pins(populated_db_conn, since=None, branch="Army")

        assert len(pins_upper) == len(pins_lower) == len(pins_mixed)
        assert all(p.branch == "ARMY" for p in pins_upper)

    def test_filters_by_since_and_branch(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify filters can be combined."""
        # Get ARMY contracts from 2026-03-12 onward
        pins = query_contract_pins(
            populated_db_conn, since="2026-03-12", branch="ARMY"
        )

        # Should get 1 contract (Lockheed Martin from page3)
        assert len(pins) == 1
        assert pins[0].company_name == "Lockheed Martin"
        assert pins[0].publish_date >= "2026-03-12"

    def test_orders_by_dollar_amount_descending(self, populated_db_conn: sqlite3.Connection) -> None:
        """Verify results are ordered by dollar amount (highest first)."""
        pins = query_contract_pins(populated_db_conn, None, None)

        # Should be ordered by dollar_amount DESC
        amounts = [p.dollar_amount for p in pins]
        assert amounts == sorted(amounts, reverse=True)

    def test_excludes_non_procurement_classifications(self, db_conn: sqlite3.Connection) -> None:
        """Verify only procurement contracts are returned."""
        # Insert page and contract
        db_conn.execute(
            """
            INSERT INTO pages (article_id, url, publish_date)
            VALUES ('test_page', 'http://example.com', '2026-03-12')
            """
        )
        db_conn.execute(
            """
            INSERT INTO contracts (
                article_id, company_name, dollar_amount, contract_number,
                branch, raw_text, completion_date
            )
            VALUES ('test_page', 'Test Corp', 1000000, 'TEST001', 'ARMY',
                    'Test contract text here', '2026-06-01')
            """
        )
        db_conn.execute(
            """
            INSERT INTO classifications (contract_id, is_procurement)
            VALUES (1, 0)
            """
        )
        db_conn.execute(
            """
            INSERT INTO contract_locations (contract_id, latitude, longitude, source)
            VALUES (1, 40.0, -74.0, 'geocoder')
            """
        )
        db_conn.commit()

        pins = query_contract_pins(db_conn, None, None)
        # Should be empty since is_procurement=0
        assert len(pins) == 0


class TestExportKml:
    """Tests for export_kml function."""

    def test_creates_kml_file(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify export_kml creates a KML file (AC5.1)."""
        output_path = tmp_path / "test.kml"

        result = export_kml(populated_db_conn, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.suffix == ".kml"

    def test_kml_file_is_valid_xml(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify output is valid XML."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path)

        # Should parse as valid XML
        tree = ET.parse(output_path)
        root = tree.getroot()
        assert root is not None

    def test_contains_placemarks_for_each_contract(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify one placemark per geocoded contract (AC5.1)."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find placemarks (with namespace)
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = root.findall(".//kml:Placemark", ns)

        # Should have 4 placemarks (all 4 contracts are procurement and geocoded)
        assert len(placemarks) == 4

    def test_placemarks_have_colour_from_gradient(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify placemarks are coloured by dollar amount (AC5.2)."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        styles = root.findall(".//kml:Style", ns)

        # Should have IconStyle with color
        assert len(styles) > 0
        for style in styles:
            icon_styles = style.findall("kml:IconStyle", ns)
            for icon_style in icon_styles:
                color_elem = icon_style.find("kml:color", ns)
                if color_elem is not None:
                    # Should be 8-char hex starting with ff
                    assert len(color_elem.text) == 8
                    assert color_elem.text.startswith("ff")

    def test_placemarks_have_popup_descriptions(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify placemarks have popup HTML descriptions (AC5.3)."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = root.findall(".//kml:Placemark", ns)

        for placemark in placemarks:
            description = placemark.find("kml:description", ns)
            assert description is not None
            assert description.text is not None

            # Should contain HTML with contract info
            html = description.text
            assert "<b>" in html
            assert "$" in html  # Dollar amount
            assert "Contract:" in html or "contract:" in html.lower()
            assert "Branch:" in html or "branch:" in html.lower()

    def test_respects_since_filter(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify export respects --since DATE filter (AC5.4)."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path, since="2026-03-15")

        tree = ET.parse(output_path)
        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = root.findall(".//kml:Placemark", ns)

        # Only 1 contract from 2026-03-15 or later (Lockheed Martin)
        assert len(placemarks) == 1

    def test_respects_branch_filter(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify export respects --branch BRANCH filter (AC5.5)."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path, branch="AIR FORCE")

        tree = ET.parse(output_path)
        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = root.findall(".//kml:Placemark", ns)

        # Only 1 AIR FORCE contract (Boeing)
        assert len(placemarks) == 1
        # Verify it's Boeing by checking the placemark name
        name = placemarks[0].find("kml:name", ns)
        assert name is not None
        assert "Boeing" in name.text

    def test_creates_parent_directory(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify export creates parent directories if needed."""
        output_path = tmp_path / "nested" / "dirs" / "test.kml"

        export_kml(populated_db_conn, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_placemark_names_include_company_and_amount(
        self, populated_db_conn: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Verify placemark names show company and dollar amount."""
        import xml.etree.ElementTree as ET

        output_path = tmp_path / "test.kml"
        export_kml(populated_db_conn, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = root.findall(".//kml:Placemark", ns)

        # Check that names include company and amount
        names = [p.find("kml:name", ns).text for p in placemarks]

        # Should have company names and dollar amounts
        assert any("Acme" in name for name in names)
        assert any("Boeing" in name for name in names)
        assert any("$" in name for name in names)

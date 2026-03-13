"""Tests for KML construction logic."""

import pytest

from dod_scan.export_kml_build import (
    ContractPin,
    build_popup_html,
    dollar_to_kml_colour,
    format_dollar_amount,
)


class TestDollarToKmlColour:
    """Tests for AC5.2: dollar amount to colour gradient conversion."""

    def test_small_amount_is_green(self) -> None:
        """Amounts <= $1M map to green-ish."""
        colour = dollar_to_kml_colour(1e6)
        assert colour == "ff00ff00"  # green (aabbggrr format)

    def test_medium_amount_is_yellow(self) -> None:
        """Amounts around $100M map to yellow-ish."""
        colour = dollar_to_kml_colour(100e6)
        assert colour.startswith("ff")  # full opacity
        # Yellow should have high R and G, no B
        r = int(colour[6:8], 16)
        g = int(colour[4:6], 16)
        b = int(colour[2:4], 16)
        assert r > 200
        assert g > 200
        assert b == 0

    def test_large_amount_is_red(self) -> None:
        """Amounts >= $10B map to red-ish."""
        colour = dollar_to_kml_colour(1e10)
        assert colour == "ff0000ff"  # red (aabbggrr format)

    def test_very_small_amount_clamps_to_green(self) -> None:
        """Amounts < $1M clamp to green."""
        colour = dollar_to_kml_colour(100)
        assert colour == "ff00ff00"

    def test_very_large_amount_clamps_to_red(self) -> None:
        """Amounts > $10B clamp to red."""
        colour = dollar_to_kml_colour(1e12)
        assert colour == "ff0000ff"

    def test_colour_is_valid_8_char_hex(self) -> None:
        """All colours are valid 8-char hex strings starting with 'ff'."""
        test_amounts = [1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11]
        for amount in test_amounts:
            colour = dollar_to_kml_colour(amount)
            assert len(colour) == 8
            assert colour.startswith("ff")
            # Verify valid hex
            int(colour, 16)

    def test_logarithmic_gradient_between_bounds(self) -> None:
        """Gradient is logarithmic between min and max."""
        colour_1m = dollar_to_kml_colour(1e6)
        colour_50m = dollar_to_kml_colour(50e6)
        colour_10b = dollar_to_kml_colour(1e10)

        # Green has no red, red has lots of red
        green_r = int(colour_1m[6:8], 16)
        red_r = int(colour_10b[6:8], 16)
        mid_r = int(colour_50m[6:8], 16)

        assert green_r < mid_r < red_r

    def test_custom_min_max_bounds(self) -> None:
        """Supports custom min/max bounds."""
        colour = dollar_to_kml_colour(500e3, min_val=100e3, max_val=1e6)
        assert colour.startswith("ff")
        # Should be somewhere in the middle of the gradient


class TestBuildPopupHtml:
    """Tests for AC5.3: popup HTML generation."""

    def test_includes_company_name(self) -> None:
        """Popup includes company name."""
        pin = ContractPin(
            company_name="Acme Corp",
            dollar_amount=1e6,
            contract_number="ABC123",
            branch="ARMY",
            raw_text="Contract details here",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        assert "Acme Corp" in html
        assert "<b>Acme Corp</b>" in html

    def test_includes_formatted_dollar_amount(self) -> None:
        """Popup includes formatted dollar amount."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1234567.89,
            contract_number="ABC123",
            branch="ARMY",
            raw_text="Contract details here",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        assert "$1,234,568" in html

    def test_includes_contract_number(self) -> None:
        """Popup includes contract number."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1e6,
            contract_number="FA8730-23-C-0025",
            branch="ARMY",
            raw_text="Contract details here",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        assert "FA8730-23-C-0025" in html

    def test_includes_branch(self) -> None:
        """Popup includes branch."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1e6,
            contract_number="ABC123",
            branch="AIR FORCE",
            raw_text="Contract details here",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        assert "AIR FORCE" in html

    def test_includes_completion_date(self) -> None:
        """Popup includes completion date."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1e6,
            contract_number="ABC123",
            branch="ARMY",
            raw_text="Contract details here",
            completion_date="2026-05-20",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        assert "2026-05-20" in html

    def test_includes_truncated_raw_text(self) -> None:
        """Popup includes first 500 chars of raw text."""
        long_text = "First 500 chars " + "x" * 485 + "Middle 500 chars " + "y" * 983
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1e6,
            contract_number="ABC123",
            branch="ARMY",
            raw_text=long_text,
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        # First 500 chars should be in HTML
        assert long_text[:500] in html
        # Char at position 501 (part of "Middle") should not be in the text portion
        assert "Middle 500" not in html

    def test_html_escapes_special_characters(self) -> None:
        """Popup HTML-escapes special characters."""
        pin = ContractPin(
            company_name="<Script> & Co",
            dollar_amount=1e6,
            contract_number="TEST&123",
            branch="ARMY",
            raw_text="<b>raw text</b> & more",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        # Should be escaped
        assert "&lt;Script&gt;" in html or "<Script>" not in html
        assert "&amp;" in html or "Script & Co" not in html

    def test_handles_zero_dollar_amount(self) -> None:
        """Popup handles zero dollar amount."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=0,
            contract_number="ABC123",
            branch="ARMY",
            raw_text="Contract details here",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        html = build_popup_html(pin)
        # Zero is falsy, so should show N/A
        assert "N/A" in html


class TestFormatDollarAmount:
    """Tests for dollar amount formatting."""

    def test_formats_with_comma_thousands_separator(self) -> None:
        """Dollar amounts include comma thousands separators."""
        assert format_dollar_amount(1000) == "$1,000"
        assert format_dollar_amount(1000000) == "$1,000,000"

    def test_rounds_to_nearest_dollar(self) -> None:
        """Dollar amounts are rounded to nearest dollar."""
        assert format_dollar_amount(1234.56) == "$1,235"
        assert format_dollar_amount(1234.49) == "$1,234"

    def test_handles_zero(self) -> None:
        """Zero formats as $0."""
        assert format_dollar_amount(0) == "$0"

    def test_handles_large_amounts(self) -> None:
        """Large amounts format correctly."""
        assert format_dollar_amount(1e9) == "$1,000,000,000"
        assert format_dollar_amount(1.5e9) == "$1,500,000,000"


class TestContractPinDataclass:
    """Tests for ContractPin dataclass."""

    def test_contract_pin_is_frozen(self) -> None:
        """ContractPin is immutable."""
        pin = ContractPin(
            company_name="Test Co",
            dollar_amount=1e6,
            contract_number="ABC123",
            branch="ARMY",
            raw_text="Text",
            completion_date="2026-03-15",
            latitude=40.7128,
            longitude=-74.0060,
            publish_date="2026-03-12",
        )
        with pytest.raises(AttributeError):
            pin.company_name = "New Co"  # type: ignore

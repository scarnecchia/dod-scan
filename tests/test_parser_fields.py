"""Tests for regex-based contract field extraction."""

import json

from dod_scan.parser_fields import parse_contract_fields, ParsedContract


def test_parse_contract_boeing_air_force() -> None:
    """Verify AC2.1: Extract Boeing Air Force contract fields correctly."""
    text = (
        "The Boeing Co. Defense, Tukwila, Washington, has received a $2,335,411,756 "
        "contract for information technology support. Work will be performed at Seattle, Washington "
        "and is expected to be completed by August 10, 2032. The Air Force Lifecycle Management Center, "
        "Hanscom Air Force Base, Massachusetts, is the contracting activity. (FA8730-23-C-0025)"
    )
    contract = parse_contract_fields(text)

    assert contract.company_name == "The Boeing Co. Defense"
    assert contract.company_city == "Tukwila"
    assert contract.company_state == "Washington"
    assert contract.dollar_amount == 2335411756.0
    assert contract.contract_number == "FA8730-23-C-0025"
    assert contract.is_modification is False
    assert contract.completion_date == "August 10, 2032"
    assert contract.contracting_activity == "Air Force Lifecycle Management Center, Hanscom Air Force Base, Massachusetts"


def test_parse_contract_navy_dashless_contract_number() -> None:
    """Verify AC2.1: Extract Navy contract with dashless contract number."""
    text = (
        "The Boeing Co., St. Louis, Missouri, is being awarded a $38,899,972 contract modification. "
        "Work will be performed at Seattle, Washington. This modification is to contract N0001926F0220 "
        "and is expected to be completed in March 15, 2033. The Naval Sea Systems Command, Washington, D.C., "
        "is the contracting activity."
    )
    contract = parse_contract_fields(text)

    assert contract.company_name == "The Boeing Co."
    assert contract.company_city == "St. Louis"
    assert contract.company_state == "Missouri"
    assert contract.dollar_amount == 38899972.0
    assert contract.contract_number == "N0001926F0220"


def test_parse_contract_army_corps() -> None:
    """Verify AC2.1: Extract Army Corps contract fields."""
    text = (
        "Koontz Electric Co. Inc., Morrilton, Arkansas, has been awarded a $9,999,992 "
        "firm fixed-price contract for construction. Work will be performed at Little Rock, Arkansas "
        "and is expected to be completed in May 2030. The U.S. Army Corps of Engineers, Vicksburg, Mississippi, "
        "is the contracting activity. (W912UM-26-D-A001)"
    )
    contract = parse_contract_fields(text)

    assert contract.company_name == "Koontz Electric Co. Inc."
    assert contract.company_city == "Morrilton"
    assert contract.company_state == "Arkansas"
    assert contract.dollar_amount == 9999992.0


def test_parse_contract_modification_with_code_p00045() -> None:
    """Verify AC2.2: Extract modification code P00045 and set is_modification=True."""
    text = (
        "The Boeing Co., St. Louis, Missouri, has received a contract modification (P00045). "
        "Work will be performed at Seattle, Washington and is expected to be completed by August 10, 2032. "
        "This is a modification to an existing contract. The contracting activity is the Naval Sea Systems Command."
    )
    contract = parse_contract_fields(text)

    assert contract.mod_code == "P00045"
    assert contract.is_modification is True


def test_parse_contract_modification_multi_code() -> None:
    """Verify AC2.2: Extract first code from multi-code modification."""
    text = (
        "Acme Defense Systems Inc., San Diego, California, received a modification (P00008 and P00014) "
        "to contract for research. Work will be performed in San Diego. The contracting activity is the "
        "Naval Air Systems Command."
    )
    contract = parse_contract_fields(text)

    assert contract.mod_code == "P00008"
    assert contract.is_modification is True


def test_parse_contract_modification_word_form() -> None:
    """Verify AC2.2: Extract modification code from 'modification (PXXXXX)' form."""
    text = (
        "Prime Systems Corp., Denver, Colorado, has a modification (P00052) to contract. "
        "Work is performed at Denver, Colorado. The contracting activity is appropriate."
    )
    contract = parse_contract_fields(text)

    assert contract.is_modification is True
    assert contract.mod_code == "P00052"


def test_parse_contract_non_modification() -> None:
    """Verify AC2.2: Non-modification contract returns empty mod_code and False."""
    text = (
        "Test Company Inc., Boston, Massachusetts, has received a $500,000 contract. "
        "Work will be performed in Boston. This is a new contract not a modification."
    )
    contract = parse_contract_fields(text)

    assert contract.is_modification is False
    assert contract.mod_code == ""


def test_parse_contract_work_locations_with_percentages() -> None:
    """Verify AC2.3: Parse multiple work locations with percentages to JSON array."""
    text = (
        "The Boeing Co., St. Louis, Missouri, has a contract. Work will be performed at "
        "Bloomington, Minnesota (68%); St. Louis, Missouri (22%); and Linthicum Heights, Maryland (10%). "
        "The contracting activity is NAVSEA."
    )
    contract = parse_contract_fields(text)

    locations = json.loads(contract.work_locations)
    assert len(locations) == 3

    # Verify first location
    assert locations[0]["city"] == "Bloomington"
    assert locations[0]["state"] == "Minnesota"
    assert locations[0]["pct"] == 68

    # Verify second location
    assert locations[1]["city"] == "St. Louis"
    assert locations[1]["state"] == "Missouri"
    assert locations[1]["pct"] == 22

    # Verify third location
    assert locations[2]["city"] == "Linthicum Heights"
    assert locations[2]["state"] == "Maryland"
    assert locations[2]["pct"] == 10


def test_parse_contract_simple_work_location() -> None:
    """Verify AC2.1: Parse simple work location."""
    text = (
        "Test Company, Boston, Massachusetts, has a contract. "
        "Work will be performed at Seattle, Washington and is expected to complete in 2030. "
        "The contracting activity is the Army."
    )
    contract = parse_contract_fields(text)

    locations = json.loads(contract.work_locations)
    assert len(locations) == 1
    assert locations[0]["city"] == "Seattle"
    assert locations[0]["state"] == "Washington"


def test_parse_contract_work_locations_tbd() -> None:
    """Verify AC2.6: 'Work locations and funding will be determined' returns empty array."""
    text = (
        "Technomics Inc., Arlington, Virginia, has a contract for services. "
        "Work locations and funding will be determined with each order. "
        "The contracting activity is the Space Force."
    )
    contract = parse_contract_fields(text)

    assert contract.work_locations == "[]"


def test_parse_contract_small_business_asterisk() -> None:
    """Verify AC2.5: Small business asterisk stripped from company name."""
    text = (
        "Technomics Inc.,* Arlington, Virginia, has a $100,000 contract. "
        "Work will be performed in Arlington. The contracting activity is the Air Force."
    )
    contract = parse_contract_fields(text)

    assert contract.company_name == "Technomics Inc."
    assert "*" not in contract.company_name


def test_parse_contract_small_business_asterisk_other_format() -> None:
    """Verify AC2.5: Asterisk stripped in different format."""
    text = (
        "Singularity Security Group LLC,* Washington, District of Columbia, has a contract. "
        "Work will be performed in DC. The contracting activity is DLA."
    )
    contract = parse_contract_fields(text)

    assert contract.company_name == "Singularity Security Group LLC"
    assert "*" not in contract.company_name


def test_parse_contract_completion_date_by() -> None:
    """Verify completion date extraction with 'by' form."""
    text = (
        "Test Company, Boston, Massachusetts, has a contract. "
        "Work will be performed at Boston and is expected to be completed by August 10, 2032. "
        "The contracting activity is the Army."
    )
    contract = parse_contract_fields(text)

    assert contract.completion_date == "August 10, 2032"


def test_parse_contract_completion_date_in() -> None:
    """Verify completion date extraction with 'in' form."""
    text = (
        "Test Company, Boston, Massachusetts, has a contract. "
        "Work will be performed at Boston and is expected to be completed in May 2030. "
        "The contracting activity is the Army."
    )
    contract = parse_contract_fields(text)

    assert contract.completion_date == "May 2030"


def test_parse_contract_completion_date_abbreviated_month() -> None:
    """Verify completion date with abbreviated month."""
    text = (
        "Test Company, Boston, Massachusetts, has a contract. "
        "Work will be performed at Boston and is expected to be completed Sept. 30, 2026. "
        "The contracting activity is the Army."
    )
    contract = parse_contract_fields(text)

    assert "Sept" in contract.completion_date
    assert "2026" in contract.completion_date


def test_parse_contract_contracting_activity() -> None:
    """Verify contracting activity extraction."""
    text = (
        "Test Company, Boston, Massachusetts, has a contract. "
        "Work will be performed at Boston. "
        "The Air Force Lifecycle Management Center, Hanscom Air Force Base, Massachusetts, is the contracting activity."
    )
    contract = parse_contract_fields(text)

    assert "Air Force Lifecycle Management Center" in contract.contracting_activity
    assert "Hanscom Air Force Base" in contract.contracting_activity


def test_parse_contract_dollar_amount_no_cents() -> None:
    """Verify dollar amount extraction without cents."""
    text = (
        "Test Company, Boston, Massachusetts, received a $850,000,000 contract. "
        "Work performed in Boston. Contracting activity: Army."
    )
    contract = parse_contract_fields(text)

    assert contract.dollar_amount == 850000000.0


def test_parse_contract_dollar_amount_large() -> None:
    """Verify large dollar amounts extracted correctly."""
    text = (
        "Test Company, Boston, Massachusetts, received a $2,335,411,756 contract. "
        "Work performed in Boston. Contracting activity: Air Force."
    )
    contract = parse_contract_fields(text)

    assert contract.dollar_amount == 2335411756.0


def test_parse_contract_contract_number_dash_format() -> None:
    """Verify contract number extraction with dash format."""
    text = (
        "Test Company, Boston, Massachusetts, received contract FA8730-23-C-0025. "
        "Work performed in Boston. Contracting activity: Air Force."
    )
    contract = parse_contract_fields(text)

    assert contract.contract_number == "FA8730-23-C-0025"


def test_parse_contract_contract_number_paren_format() -> None:
    """Verify contract number extraction in parentheses at end."""
    text = (
        "Test Company, Boston, Massachusetts, received a contract. "
        "Work performed in Boston. Contracting activity: Army. (W912UM-26-D-A001)"
    )
    contract = parse_contract_fields(text)

    assert contract.contract_number == "W912UM-26-D-A001"


def test_parse_contract_returns_dataclass() -> None:
    """Verify parse_contract_fields returns ParsedContract instance."""
    text = "Test Company, Boston, Massachusetts, received a contract."
    contract = parse_contract_fields(text)

    assert isinstance(contract, ParsedContract)


def test_parse_contract_empty_text() -> None:
    """Verify parsing empty text returns dataclass with defaults."""
    contract = parse_contract_fields("")

    assert contract.company_name == ""
    assert contract.company_city == ""
    assert contract.company_state == ""
    assert contract.dollar_amount is None
    assert contract.contract_number == ""
    assert contract.is_modification is False
    assert contract.work_locations == "[]"


def test_parse_contract_district_of_columbia() -> None:
    """Verify DC recognized as a state."""
    text = (
        "Test Company, Washington, District of Columbia, received a $100,000 contract. "
        "Work performed in DC. Contracting activity: DLA."
    )
    contract = parse_contract_fields(text)

    assert contract.company_city == "Washington"
    assert contract.company_state == "District of Columbia"

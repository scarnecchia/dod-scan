# pattern: Functional Core
"""KML construction logic — builds placemarks with colours and popups."""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class ContractPin:
    company_name: str
    dollar_amount: float
    contract_number: str
    branch: str
    raw_text: str
    completion_date: str
    latitude: float
    longitude: float
    publish_date: str


def dollar_to_kml_colour(amount: float, min_val: float = 1e6, max_val: float = 1e10) -> str:
    """Map dollar amount to green->yellow->red gradient in KML aabbggrr format."""
    if amount <= min_val:
        t = 0.0
    elif amount >= max_val:
        t = 1.0
    else:
        t = (math.log10(amount) - math.log10(min_val)) / (
            math.log10(max_val) - math.log10(min_val)
        )

    if t < 0.5:
        r = int(255 * (t * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (t - 0.5) * 2))
    b = 0

    return f"ff{b:02x}{g:02x}{r:02x}"


def build_popup_html(pin: ContractPin) -> str:
    """Build HTML description for a KML placemark popup."""
    amount_str = f"${pin.dollar_amount:,.0f}" if pin.dollar_amount else "N/A"
    return (
        f"<b>{escape(pin.company_name)}</b><br/>"
        f"<b>Amount:</b> {amount_str}<br/>"
        f"<b>Contract:</b> {escape(pin.contract_number)}<br/>"
        f"<b>Branch:</b> {escape(pin.branch)}<br/>"
        f"<b>Completion:</b> {escape(pin.completion_date)}<br/>"
        f"<hr/>"
        f"<small>{escape(pin.raw_text[:500])}</small>"
    )


def format_dollar_amount(amount: float) -> str:
    return f"${amount:,.0f}"

# pattern: Functional Core
"""GeoJSON construction for Mapbox dashboard."""

from __future__ import annotations

import json
from html import escape

from dod_scan.export_kml_build import ContractPin, format_dollar_amount


def pins_to_geojson(pins: list[ContractPin]) -> str:
    features = [_pin_to_feature(pin) for pin in pins]
    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    return json.dumps(collection)


def _pin_to_feature(pin: ContractPin) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [pin.longitude, pin.latitude],
        },
        "properties": {
            "company_name": pin.company_name,
            "dollar_amount": pin.dollar_amount,
            "dollar_display": format_dollar_amount(pin.dollar_amount),
            "contract_number": pin.contract_number,
            "branch": pin.branch,
            "completion_date": pin.completion_date,
            "publish_date": pin.publish_date,
            "description": pin.raw_text[:500],
        },
    }


def get_unique_branches(pins: list[ContractPin]) -> list[str]:
    return sorted({pin.branch for pin in pins if pin.branch})

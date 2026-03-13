# pattern: Functional Core
"""Location resolution logic — determines which location to geocode for a contract."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocationToGeocode:
    city: str
    state: str
    source: str  # "work_location" or "company_hq"


def resolve_location(
    work_locations_json: str,
    company_city: str,
    company_state: str,
) -> LocationToGeocode | None:
    location = _resolve_from_work_locations(work_locations_json)
    if location:
        return location

    if company_city and company_state:
        return LocationToGeocode(
            city=company_city,
            state=company_state,
            source="company_hq",
        )

    return None


def _resolve_from_work_locations(work_locations_json: str) -> LocationToGeocode | None:
    try:
        locations = json.loads(work_locations_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not locations:
        return None

    if any("pct" in loc for loc in locations):
        primary = max(locations, key=lambda loc: loc.get("pct", 0))
    else:
        primary = locations[0]

    city = primary.get("city", "").strip()
    state = primary.get("state", "").strip()

    if city and state:
        return LocationToGeocode(city=city, state=state, source="work_location")

    return None


def make_location_key(city: str, state: str) -> str:
    return f"{city.lower().strip()}, {state.lower().strip()}"

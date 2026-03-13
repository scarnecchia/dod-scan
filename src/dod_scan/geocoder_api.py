# pattern: Imperative Shell
"""Nominatim geocoding API client with SQLite cache and rate limiting."""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from dod_scan.geocoder_resolve import make_location_key
from dod_scan.parser_fields import US_STATES

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "dod-scan/1.0 (DOD contract scanner)"
RATE_LIMIT_SECONDS = 1.1


@dataclass(frozen=True)
class GeocodedLocation:
    latitude: float
    longitude: float


class GeocodingError(Exception):
    pass


def geocode_city_state(
    city: str,
    state: str,
    conn: sqlite3.Connection,
) -> GeocodedLocation | None:
    key = make_location_key(city, state)

    cached = _get_cached(conn, key)
    if cached:
        logger.debug("Cache hit for %s", key)
        return cached

    logger.info("Geocoding %s, %s via Nominatim", city, state)
    time.sleep(RATE_LIMIT_SECONDS)

    try:
        result = _call_nominatim(city, state)
    except GeocodingError:
        logger.exception("Geocoding failed for %s, %s", city, state)
        return None

    if result:
        _cache_result(conn, key, result)

    return result


def _get_cached(conn: sqlite3.Connection, key: str) -> GeocodedLocation | None:
    row = conn.execute(
        "SELECT latitude, longitude FROM geocode_cache WHERE location_key = ?",
        (key,),
    ).fetchone()
    if row:
        return GeocodedLocation(latitude=row["latitude"], longitude=row["longitude"])
    return None


def _cache_result(
    conn: sqlite3.Connection, key: str, location: GeocodedLocation
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO geocode_cache (location_key, latitude, longitude, geocoded_at)
        VALUES (?, ?, ?, ?)
        """,
        (key, location.latitude, location.longitude, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _call_nominatim(city: str, state: str) -> GeocodedLocation | None:
    headers = {"User-Agent": USER_AGENT}
    is_us = state.title() in US_STATES

    if is_us:
        params: dict[str, str | int] = {"format": "json", "limit": 1}
        if city:
            params["city"] = city
        params["state"] = state
        params["country"] = "United States"
    else:
        query_parts = [p for p in (city, state) if p]
        params = {"q": ", ".join(query_parts), "format": "json", "limit": 1}

    result = _nominatim_request(params, headers)
    if result:
        return result

    # Fallback for US locations with complex city names (military bases, etc.)
    if is_us and city:
        logger.info("Retrying with free-text query for %s, %s", city, state)
        time.sleep(RATE_LIMIT_SECONDS)
        fallback_params: dict[str, str | int] = {
            "q": f"{city}, {state}",
            "format": "json",
            "limit": 1,
        }
        result = _nominatim_request(fallback_params, headers)
        if result:
            return result

        # Last resort: geocode just the state
        logger.info("Falling back to state-level geocode for %s", state)
        time.sleep(RATE_LIMIT_SECONDS)
        state_params: dict[str, str | int] = {
            "state": state,
            "country": "United States",
            "format": "json",
            "limit": 1,
        }
        result = _nominatim_request(state_params, headers)
        if result:
            return result

    logger.warning("No Nominatim results for %s, %s", city, state)
    return None


def _nominatim_request(
    params: dict[str, str | int], headers: dict[str, str]
) -> GeocodedLocation | None:
    try:
        resp = httpx.get(NOMINATIM_URL, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Nominatim request failed: {exc}") from exc

    results = resp.json()
    if not results:
        return None

    return GeocodedLocation(
        latitude=float(results[0]["lat"]),
        longitude=float(results[0]["lon"]),
    )

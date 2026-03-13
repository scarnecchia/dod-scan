# pattern: Imperative Shell
"""Geocoder orchestration — resolves and geocodes locations for procurement contracts."""

from __future__ import annotations

import logging
import sqlite3

from dod_scan.geocoder_api import geocode_city_state
from dod_scan.geocoder_resolve import resolve_location

logger = logging.getLogger(__name__)


def geocode_all(conn: sqlite3.Connection) -> int:
    contracts = conn.execute(
        """
        SELECT c.id, c.work_locations, c.company_city, c.company_state
        FROM contracts c
        JOIN classifications cl ON cl.contract_id = c.id
        WHERE cl.is_procurement = 1
        AND c.id NOT IN (
            SELECT contract_id FROM contract_locations
        )
        """,
    ).fetchall()

    geocoded_count = 0

    for row in contracts:
        contract_id = row["id"]
        location = resolve_location(
            row["work_locations"], row["company_city"], row["company_state"]
        )

        if location is None:
            logger.warning("No location to geocode for contract %d", contract_id)
            continue

        result = geocode_city_state(location.city, location.state, conn)
        if result is None:
            logger.warning("Geocoding failed for contract %d", contract_id)
            continue

        _store_contract_location(
            conn, contract_id, result.latitude, result.longitude, location.source
        )
        geocoded_count += 1

    logger.info("Geocoding complete: %d contracts geocoded", geocoded_count)
    return geocoded_count


def _store_contract_location(
    conn: sqlite3.Connection,
    contract_id: int,
    latitude: float,
    longitude: float,
    source: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO contract_locations (
            contract_id, latitude, longitude, source
        ) VALUES (?, ?, ?, ?)
        """,
        (contract_id, latitude, longitude, source),
    )
    conn.commit()

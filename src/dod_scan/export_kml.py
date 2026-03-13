# pattern: Imperative Shell
"""KML export — queries geocoded procurement contracts and generates KML file."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import simplekml

from dod_scan.export_kml_build import (
    ContractPin,
    build_popup_html,
    dollar_to_kml_colour,
    format_dollar_amount,
)

logger = logging.getLogger(__name__)


def export_kml(
    conn: sqlite3.Connection,
    output_path: Path,
    since: str | None = None,
    branch: str | None = None,
) -> Path:
    pins = query_contract_pins(conn, since, branch)
    logger.info("Exporting %d contracts to KML", len(pins))

    kml = simplekml.Kml(name="DOD Procurement Contracts")

    for pin in pins:
        name = f"{pin.company_name} — {format_dollar_amount(pin.dollar_amount)}"
        pnt = kml.newpoint(
            name=name,
            description=build_popup_html(pin),
            coords=[(pin.longitude, pin.latitude)],
        )
        pnt.style.iconstyle.color = dollar_to_kml_colour(pin.dollar_amount)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    kml.save(str(output_path))
    logger.info("KML file written to %s", output_path)
    return output_path


def query_contract_pins(
    conn: sqlite3.Connection,
    since: str | None,
    branch: str | None,
) -> list[ContractPin]:
    query = """
        SELECT
            c.company_name, c.dollar_amount, c.contract_number,
            c.branch, c.raw_text, c.completion_date,
            cl2.latitude, cl2.longitude, p.publish_date
        FROM contracts c
        JOIN classifications cl ON cl.contract_id = c.id
        JOIN contract_locations cl2 ON cl2.contract_id = c.id
        JOIN pages p ON p.article_id = c.article_id
        WHERE cl.is_procurement = 1
    """
    params: list = []

    if since:
        query += " AND p.publish_date >= ?"
        params.append(since)
    if branch:
        query += " AND UPPER(c.branch) = UPPER(?)"
        params.append(branch)

    query += " ORDER BY c.dollar_amount DESC"

    rows = conn.execute(query, params).fetchall()
    return [
        ContractPin(
            company_name=row["company_name"] or "",
            dollar_amount=row["dollar_amount"] or 0,
            contract_number=row["contract_number"] or "",
            branch=row["branch"] or "",
            raw_text=row["raw_text"] or "",
            completion_date=row["completion_date"] or "",
            latitude=row["latitude"],
            longitude=row["longitude"],
            publish_date=row["publish_date"] or "",
        )
        for row in rows
    ]

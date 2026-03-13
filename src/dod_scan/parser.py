# pattern: Imperative Shell
"""Parser orchestration — extracts contracts from stored HTML and persists to DB."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from dod_scan.parser_extract import extract_contracts_from_html
from dod_scan.parser_fields import ParsedContract, parse_contract_fields

logger = logging.getLogger(__name__)


def parse_all(conn: sqlite3.Connection) -> int:
    pages = conn.execute(
        """
        SELECT article_id, raw_html FROM pages
        WHERE article_id NOT IN (
            SELECT DISTINCT article_id FROM contracts
        )
        """
    ).fetchall()

    total_contracts = 0

    for page in pages:
        article_id = page["article_id"]
        raw_html = page["raw_html"]

        raw_contracts = extract_contracts_from_html(raw_html)
        logger.info(
            "Extracted %d contracts from article %s", len(raw_contracts), article_id
        )

        for raw in raw_contracts:
            fields = parse_contract_fields(raw.raw_text)
            _store_contract(conn, article_id, raw.branch, fields, raw.raw_text)
            total_contracts += 1

        conn.commit()

    logger.info("Parse complete: %d contracts extracted", total_contracts)
    return total_contracts


def _store_contract(
    conn: sqlite3.Connection,
    article_id: str,
    branch: str,
    fields: ParsedContract,
    raw_text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO contracts (
            article_id, branch, company_name, company_city, company_state,
            dollar_amount, contract_number, mod_code, is_modification,
            work_locations, completion_date, contracting_activity,
            raw_text, parsed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            branch,
            fields.company_name,
            fields.company_city,
            fields.company_state,
            fields.dollar_amount,
            fields.contract_number,
            fields.mod_code,
            fields.is_modification,
            fields.work_locations,
            fields.completion_date,
            fields.contracting_activity,
            raw_text,
            datetime.now(timezone.utc).isoformat(),
        ),
    )

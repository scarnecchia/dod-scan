# pattern: Imperative Shell
"""Classifier orchestration — sends contracts to LLM and stores classifications."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from dod_scan.classifier_prompt import (
    build_classification_prompt,
    parse_classification_response,
)
from dod_scan.classifier_providers import LLMProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = [2.0, 5.0, 10.0]


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


def classify_all(conn: sqlite3.Connection, provider: LLMProvider) -> int:
    unclassified = conn.execute(
        """
        SELECT id, raw_text FROM contracts
        WHERE id NOT IN (SELECT contract_id FROM classifications)
        """
    ).fetchall()

    classified_count = 0

    for row in unclassified:
        contract_id = row["id"]
        raw_text = row["raw_text"]

        prompt = build_classification_prompt(raw_text)

        response_text = None
        for attempt in range(MAX_RETRIES):
            try:
                response_text = provider.classify(prompt)
                break
            except Exception as exc:
                if _is_transient(exc) and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(
                        "Transient error for contract %d (attempt %d/%d), retrying in %.0fs: %s",
                        contract_id, attempt + 1, MAX_RETRIES, wait, exc,
                    )
                    time.sleep(wait)
                    continue
                logger.exception("LLM API error for contract %d", contract_id)
                raise

        result = parse_classification_response(response_text)
        if result is None:
            logger.warning(
                "Malformed LLM response for contract %d, skipping (will retry next run)",
                contract_id,
            )
            continue

        conn.execute(
            """
            INSERT INTO classifications (
                contract_id, is_procurement, confidence, reasoning,
                model_used, classified_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                contract_id,
                result.is_procurement,
                result.confidence,
                result.reasoning,
                provider.model_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        classified_count += 1
        logger.info(
            "Classified contract %d: procurement=%s confidence=%.2f",
            contract_id,
            result.is_procurement,
            result.confidence,
        )

    logger.info("Classification complete: %d contracts classified", classified_count)
    return classified_count

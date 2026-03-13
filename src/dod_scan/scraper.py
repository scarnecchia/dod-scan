# pattern: Imperative Shell
"""Scraper orchestration — fetches contract pages and stores in SQLite."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from dod_scan.scraper_fetch import FetchError, fetch_page
from dod_scan.scraper_parse import (
    ArticleLink,
    build_index_url,
    extract_article_links,
    extract_publish_date_from_title,
)

logger = logging.getLogger(__name__)


def scrape(conn: sqlite3.Connection, backfill: int = 0) -> int:
    """Fetch contract pages from war.gov and store in SQLite.

    Args:
        conn: SQLite database connection.
        backfill: Number of historical pages to fetch (0 = today only).

    Returns:
        Count of newly stored articles.

    Raises:
        FetchError: If any page fetch fails.
    """
    pages_to_fetch = backfill + 1
    total_stored = 0

    for page_num in range(1, pages_to_fetch + 1):
        index_url = build_index_url(page_num)
        logger.info("Fetching index page %d: %s", page_num, index_url)

        try:
            index_html = fetch_page(index_url)
        except FetchError:
            logger.exception("Failed to fetch index page %d", page_num)
            raise

        article_links = extract_article_links(index_html)
        logger.info("Found %d article links on page %d", len(article_links), page_num)

        for link in article_links:
            if _article_exists(conn, link.article_id):
                logger.debug("Skipping already-scraped article %s", link.article_id)
                continue

            try:
                article_html = fetch_page(link.url)
            except FetchError:
                logger.exception("Failed to fetch article %s", link.article_id)
                raise

            publish_date = extract_publish_date_from_title(link.title)
            _store_page(conn, link, article_html, publish_date)
            total_stored += 1
            logger.info("Stored article %s: %s", link.article_id, link.title)

    logger.info("Scrape complete: %d new pages stored", total_stored)
    return total_stored


def _article_exists(conn: sqlite3.Connection, article_id: str) -> bool:
    """Check if article already exists in pages table."""
    row = conn.execute(
        "SELECT 1 FROM pages WHERE article_id = ?", (article_id,)
    ).fetchone()
    return row is not None


def _store_page(
    conn: sqlite3.Connection,
    link: ArticleLink,
    html: str,
    publish_date: str | None,
) -> None:
    """Store article page in database."""
    conn.execute(
        """
        INSERT INTO pages (article_id, url, publish_date, scraped_at, raw_html)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            link.article_id,
            link.url,
            publish_date,
            datetime.now(timezone.utc).isoformat(),
            html,
        ),
    )
    conn.commit()

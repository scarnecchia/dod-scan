"""Shared test fixtures for dod-scan."""

import sqlite3
from pathlib import Path

import pytest

from dod_scan.db import init_db, get_connection


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def db_conn(tmp_db: Path) -> sqlite3.Connection:
    conn = get_connection(tmp_db)
    yield conn
    conn.close()


def insert_test_page(conn: sqlite3.Connection, article_id: str, url: str = "http://example.com") -> None:
    """Helper to insert a test page."""
    conn.execute(
        """
        INSERT INTO pages (article_id, url)
        VALUES (?, ?)
        """,
        (article_id, url),
    )
    conn.commit()

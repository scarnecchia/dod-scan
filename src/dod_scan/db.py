# pattern: Imperative Shell
"""SQLite database schema creation and connection management."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pages (
    article_id       TEXT PRIMARY KEY,
    url              TEXT NOT NULL,
    publish_date     DATE,
    scraped_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_html         TEXT
);

CREATE TABLE IF NOT EXISTS contracts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id       TEXT REFERENCES pages(article_id),
    branch           TEXT,
    company_name     TEXT,
    company_city     TEXT,
    company_state    TEXT,
    dollar_amount    REAL,
    contract_number  TEXT,
    mod_code         TEXT,
    is_modification  BOOLEAN DEFAULT 0,
    work_locations   TEXT,
    completion_date  TEXT,
    contracting_activity TEXT,
    raw_text         TEXT,
    parsed_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classifications (
    contract_id      INTEGER PRIMARY KEY REFERENCES contracts(id),
    is_procurement   BOOLEAN,
    confidence       REAL,
    reasoning        TEXT,
    model_used       TEXT,
    classified_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    location_key     TEXT PRIMARY KEY,
    latitude         REAL,
    longitude        REAL,
    geocoded_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.close()

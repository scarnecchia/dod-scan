# DOD Contract Scanner Implementation Plan — Phase 1

**Goal:** Installable Python package with CLI entry points and SQLite schema.

**Architecture:** Stage-based CLI pipeline using typer for subcommands and SQLite as the coordination layer between stages. Configuration loaded from environment variables via pydantic-settings.

**Tech Stack:** Python 3.10+, typer, pydantic-settings, SQLite (stdlib), setuptools (src-layout)

**Scope:** 8 phases from original design (phase 1 of 8)

**Codebase verified:** 2026-03-12 — true greenfield, only docs/ directory exists

---

## Acceptance Criteria Coverage

This phase is infrastructure scaffolding. Verification is operational (install, CLI help, table creation).

**Verifies: None** — this phase establishes project structure. No acceptance criteria are tested here.

---

<!-- START_TASK_1 -->
### Task 1: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

**Step 1: Create the file**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "dod-scan"
version = "0.1.0"
description = "DOD contract scanner — scrapes, parses, classifies, geocodes, and exports contract awards"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0",
    "simplekml>=1.3.0",
    "jinja2>=3.1.0",
    "anthropic>=0.40.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
browser = ["playwright>=1.40.0"]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5.0",
]

[project.scripts]
dod-scan = "dod_scan.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Verify file is valid TOML**

No operational verification yet — package files don't exist. This is verified in Task 5.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with dependencies and CLI entry point"
```
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Create .env.example and .gitignore

**Files:**
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create .env.example**

```ini
# LLM provider: "openrouter" or "anthropic"
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-...
LLM_MODEL=anthropic/claude-haiku-4-5-20251001

# Optional: Mapbox token for interactive HTML dashboard
MAPBOX_TOKEN=

# Database and output paths
DATABASE_PATH=./dod_scan.db
OUTPUT_DIR=./output
LOG_DIR=./logs
```

**Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.egg

# Virtual environment
.venv/
venv/

# Environment
.env

# Project outputs
*.db
output/
logs/

# IDE
.idea/
.vscode/
*.swp
```

**Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example and .gitignore"
```
<!-- END_TASK_2 -->

<!-- START_SUBCOMPONENT_A (tasks 3-4) -->
<!-- START_TASK_3 -->
### Task 3: Create package structure and config module

**Files:**
- Create: `src/dod_scan/__init__.py`
- Create: `src/dod_scan/config.py`

**Step 1: Create package init**

Create `src/dod_scan/__init__.py`:

```python
"""DOD contract scanner pipeline."""

__version__ = "0.1.0"
```

**Step 2: Create config module**

Create `src/dod_scan/config.py`:

```python
# pattern: Imperative Shell
"""Configuration loaded from environment variables and .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = "anthropic/claude-haiku-4-5-20251001"
    mapbox_token: str = ""
    database_path: Path = Path("./dod_scan.db")
    output_dir: Path = Path("./output")
    log_dir: Path = Path("./logs")


def get_settings() -> Settings:
    return Settings()
```

**Step 3: Commit**

```bash
git add src/
git commit -m "chore: add package init and config module"
```
<!-- END_TASK_3 -->

<!-- START_TASK_4 -->
### Task 4: Create database module

**Files:**
- Create: `src/dod_scan/db.py`

**Step 1: Create database module**

Create `src/dod_scan/db.py`:

```python
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
```

**Step 2: Commit**

```bash
git add src/dod_scan/db.py
git commit -m "chore: add SQLite schema and connection management"
```
<!-- END_TASK_4 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_5 -->
### Task 5: Create CLI with subcommand stubs

**Files:**
- Create: `src/dod_scan/cli.py`

**Step 1: Create CLI module**

Create `src/dod_scan/cli.py`:

```python
# pattern: Imperative Shell
"""CLI entry point with subcommand stubs for each pipeline stage."""

import typer

from dod_scan.config import get_settings
from dod_scan.db import init_db

app = typer.Typer(
    name="dod-scan",
    help="DOD contract scanner — scrapes, parses, classifies, geocodes, and exports contract awards.",
)


@app.command()
def scrape(
    backfill: int = typer.Option(0, "--backfill", "-b", help="Number of historical pages to fetch"),
) -> None:
    """Fetch daily contract pages from war.gov."""
    typer.echo("scrape: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def parse() -> None:
    """Extract structured contract data from raw HTML."""
    typer.echo("parse: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def classify() -> None:
    """Classify contracts as procurement vs service using LLM."""
    typer.echo("classify: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def geocode() -> None:
    """Resolve contract locations to lat/lon coordinates."""
    typer.echo("geocode: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def export(
    format: str = typer.Option("kml", "--format", "-f", help="Export format: kml, map, or all"),
    since: str = typer.Option(None, "--since", help="Filter to contracts from this date onward (YYYY-MM-DD)"),
    branch: str = typer.Option(None, "--branch", help="Filter to specific branch (e.g. ARMY)"),
) -> None:
    """Export geocoded procurement contracts as KML and/or Mapbox dashboard."""
    typer.echo("export: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="run-all")
def run_all() -> None:
    """Execute all pipeline stages in sequence: scrape -> parse -> classify -> geocode -> export."""
    typer.echo("run-all: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="init-db")
def init_database() -> None:
    """Initialize the database schema."""
    settings = get_settings()
    init_db(settings.database_path)
    typer.echo(f"Database initialized at {settings.database_path}")
```
<!-- END_TASK_5 -->

<!-- START_TASK_6 -->
### Task 6: Install package and verify operationally

**Step 1: Create virtual environment and install**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: Installs without errors.

**Step 2: Verify CLI help**

```bash
dod-scan --help
```

Expected: Shows help text with all subcommands (scrape, parse, classify, geocode, export, run-all, init-db).

**Step 3: Verify database initialization**

```bash
dod-scan init-db
```

Expected: Creates `dod_scan.db` file with all four tables. Verify with:

```bash
sqlite3 dod_scan.db ".tables"
```

Expected output includes: `classifications  contracts  geocode_cache  pages`

**Step 4: Clean up test database**

```bash
rm -f dod_scan.db
```

**Step 5: Commit**

```bash
git add src/dod_scan/cli.py
git commit -m "feat: add CLI with subcommand stubs and init-db command"
```
<!-- END_TASK_6 -->

<!-- START_TASK_7 -->
### Task 7: Create test directory structure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create test directory**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
"""Shared test fixtures for dod-scan."""

import sqlite3
import tempfile
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
```

**Step 2: Verify tests run (empty suite)**

```bash
pytest --tb=short
```

Expected: Passes with 0 tests collected (no test files yet, but pytest discovers the test directory).

**Step 3: Commit**

```bash
git add tests/
git commit -m "chore: add test directory with shared fixtures"
```
<!-- END_TASK_7 -->

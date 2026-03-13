# DOD Contract Scanner Implementation Plan — Phase 8

**Goal:** Chain all stages, configure logging, and document setup for cron.

**Architecture:** `run-all` subcommand executes stages sequentially (scrape -> parse -> classify -> geocode -> export), stopping on first failure with non-zero exit. File-based logging configured at module level. README provides complete setup instructions from zero to running scheduled scans.

**Tech Stack:** Python 3.10+ (stdlib logging), cron

**Scope:** 8 phases from original design (phase 8 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-7 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC7: Orchestration and documentation
- **dod-scan.AC7.1 Success:** `run-all` executes scrape -> parse -> classify -> geocode -> export in sequence
- **dod-scan.AC7.2 Failure:** `run-all` stops on first stage failure with non-zero exit code
- **dod-scan.AC7.3 Success:** All stages log to file (configurable path)
- **dod-scan.AC7.4 Success:** README contains venv setup, dependency install, env var configuration, backfill command, daily cron entry, and output file locations
- **dod-scan.AC7.5 Success:** A new user can follow README from zero to running scheduled scans

---

<!-- START_TASK_1 -->
### Task 1: Logging configuration

**Verifies:** dod-scan.AC7.3

**Files:**
- Create: `src/dod_scan/logging_config.py`

**Implementation:**

Create `src/dod_scan/logging_config.py` — configures file and console logging.

```python
# pattern: Imperative Shell
"""Logging configuration for all pipeline stages."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: Path, level: int = logging.INFO) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "dod_scan.log"

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )

    root.addHandler(file_handler)
    root.addHandler(console_handler)
```

**Commit:** `feat: add file-based logging configuration`
<!-- END_TASK_1 -->

<!-- START_SUBCOMPONENT_A (tasks 2-4) -->
<!-- START_TASK_2 -->
### Task 2: run-all command implementation

**Verifies:** dod-scan.AC7.1, dod-scan.AC7.2

**Files:**
- Modify: `src/dod_scan/cli.py` — replace `run_all` stub with real implementation, add logging setup to all commands

**Implementation:**

Update `cli.py` to add logging configuration to a callback and implement `run-all`:

```python
@app.callback()
def main_callback() -> None:
    """DOD contract scanner pipeline."""
    settings = get_settings()
    from dod_scan.logging_config import configure_logging
    configure_logging(settings.log_dir)


@app.command(name="run-all")
def run_all(
    backfill: int = typer.Option(0, "--backfill", "-b", help="Number of historical pages to fetch"),
    format: str = typer.Option("kml", "--format", "-f", help="Export format: kml, map, or all"),
    since: str = typer.Option(None, "--since", help="Filter exports to contracts from this date onward (YYYY-MM-DD)"),
    branch: str = typer.Option(None, "--branch", help="Filter exports to specific branch (e.g. ARMY)"),
) -> None:
    """Execute all pipeline stages in sequence: scrape -> parse -> classify -> geocode -> export."""
    import logging
    logger = logging.getLogger(__name__)

    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)

    stages = [
        ("scrape", lambda: _run_scrape(conn, backfill)),
        ("parse", lambda: _run_parse(conn)),
        ("classify", lambda: _run_classify(conn, settings)),
        ("geocode", lambda: _run_geocode(conn)),
        ("export", lambda: _run_export(conn, settings, format, since, branch)),
    ]

    current_stage = "unknown"
    try:
        for current_stage, stage_fn in stages:
            logger.info("Starting stage: %s", current_stage)
            typer.echo(f"Running {current_stage}...")
            stage_fn()
            logger.info("Completed stage: %s", current_stage)
        typer.echo("All stages completed successfully")
    except Exception as exc:
        logger.exception("Pipeline failed at stage: %s", current_stage)
        typer.echo(f"Pipeline failed at {current_stage}: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

The `_run_scrape`, `_run_parse`, `_run_classify`, `_run_geocode`, `_run_export` helper functions call the respective module functions. They are thin wrappers that handle imports and configuration.

Implementation details for each helper are straightforward — they match the patterns already established in the individual CLI commands from prior phases. Task-implementor should extract the body of each existing CLI command into these helpers.

**Commit:** `feat: implement run-all command with sequential stage execution`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: run-all tests

**Verifies:** dod-scan.AC7.1, dod-scan.AC7.2

**Files:**
- Create: `tests/test_run_all.py`

**Testing:**

Tests must verify each AC listed above:

- dod-scan.AC7.1: Mock all five stage functions (scrape, parse_all, classify_all, geocode_all, export_kml). Call run-all. Verify all five were called in order: scrape first, then parse, then classify, then geocode, then export.

- dod-scan.AC7.2: Mock the second stage (parse) to raise an exception. Call run-all. Verify: scrape was called, parse was called and raised, classify/geocode/export were NOT called. Exit code is non-zero.

- dod-scan.AC7.3 (logging): After calling run-all, verify log file exists at configured log_dir path and contains stage start/complete messages.

Use `tmp_path` for database and log directory. Mock stage functions to avoid real network/LLM calls.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_run_all.py -v`
Expected: All tests pass

**Commit:** `test: add run-all orchestration tests`
<!-- END_TASK_3 -->

<!-- START_TASK_4 -->
### Task 4: Logging integration test

**Verifies:** dod-scan.AC7.3

**Files:**
- Create: `tests/test_logging_config.py`

**Testing:**

- `configure_logging` creates log directory if missing
- After configuration, logging.getLogger("test").info("message") writes to log file
- Log file contains expected format: timestamp, logger name, level, message
- Console handler only shows WARNING and above
- Calling `configure_logging` twice doesn't duplicate handlers

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_logging_config.py -v`
Expected: All tests pass

**Commit:** `test: add logging configuration tests`
<!-- END_TASK_4 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_5 -->
### Task 5: CLI integration test

**Files:**
- Create: `tests/test_cli.py`

**Testing:**

Use `typer.testing.CliRunner` to invoke each subcommand with `--help` and verify it exits with code 0. This catches import errors, argument mismatches, and wiring issues without needing real data or network calls.

Test all subcommands: `scrape`, `parse`, `classify`, `geocode`, `export`, `run-all`, `init-db`.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_cli.py -v`
Expected: All tests pass

**Commit:** `test: add CLI integration test for subcommand wiring`
<!-- END_TASK_5 -->

<!-- START_TASK_6 -->
### Task 6: README

**Verifies:** dod-scan.AC7.4, dod-scan.AC7.5

**Files:**
- Create: `README.md`

**Implementation:**

Create `README.md` with the following sections:

1. **Overview** — one paragraph describing what dod-scan does
2. **Requirements** — Python 3.10+, optional Playwright for bot-protected pages
3. **Installation**
   ```bash
   git clone <repo>
   cd dod-scan
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   # Optional: for Playwright fallback
   pip install -e ".[browser]"
   playwright install chromium
   ```
4. **Configuration** — copy `.env.example` to `.env`, explain each variable (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, MAPBOX_TOKEN, DATABASE_PATH, OUTPUT_DIR, LOG_DIR)
5. **Usage**
   - Initialize database: `dod-scan init-db`
   - Run full pipeline: `dod-scan run-all`
   - Run individual stages: `dod-scan scrape`, `dod-scan parse`, etc.
   - Backfill historical data: `dod-scan scrape --backfill 10`
   - Export with filters: `dod-scan export --format all --since 2026-01-01 --branch NAVY`
6. **Scheduling (Cron)**
   ```
   # Run daily at 6 PM (after DOD publishes at 5 PM)
   0 18 * * 1-5 cd /path/to/dod-scan && .venv/bin/dod-scan run-all >> /path/to/dod-scan/logs/cron.log 2>&1
   ```
7. **Output Files** — where KML and HTML files are written, how to open in Google Earth
8. **Troubleshooting** — common issues (403 errors, missing API keys, geocoding rate limits)

**Commit:** `docs: add README with setup, usage, and cron instructions`
<!-- END_TASK_6 -->

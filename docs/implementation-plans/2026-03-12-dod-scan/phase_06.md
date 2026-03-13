# DOD Contract Scanner Implementation Plan — Phase 6

**Goal:** Generate KML files from geocoded procurement contracts.

**Architecture:** Functional Core for KML construction (building placemarks, colour gradient calculation, popup HTML), Imperative Shell for DB reads and file writing. Uses simplekml library. Placemarks coloured by dollar amount on a green-yellow-red gradient. Supports filtering by date and branch via CLI options.

**Tech Stack:** Python 3.10+, simplekml, SQLite

**Scope:** 8 phases from original design (phase 6 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-5 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC5: KML export
- **dod-scan.AC5.1 Success:** Valid KML file generated with one placemark per geocoded procurement contract
- **dod-scan.AC5.2 Success:** Placemarks coloured by dollar amount (green -> yellow -> red gradient)
- **dod-scan.AC5.3 Success:** Placemark popup contains company name, dollar amount, contract number, branch, description, completion date
- **dod-scan.AC5.4 Success:** `--since DATE` filters to contracts from that date onward
- **dod-scan.AC5.5 Success:** `--branch ARMY` filters to specified branch only

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: KML construction logic (Functional Core)

**Verifies:** dod-scan.AC5.1, dod-scan.AC5.2, dod-scan.AC5.3

**Files:**
- Create: `src/dod_scan/export_kml_build.py`

**Implementation:**

Create `src/dod_scan/export_kml_build.py` — pure functions for building KML content from contract data.

```python
# pattern: Functional Core
"""KML construction logic — builds placemarks with colours and popups."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class ContractPin:
    company_name: str
    dollar_amount: float
    contract_number: str
    branch: str
    raw_text: str
    completion_date: str
    latitude: float
    longitude: float
    publish_date: str


def dollar_to_kml_colour(amount: float, min_val: float = 1e6, max_val: float = 1e10) -> str:
    """Map dollar amount to green->yellow->red gradient in KML aabbggrr format."""
    if amount <= min_val:
        t = 0.0
    elif amount >= max_val:
        t = 1.0
    else:
        import math
        t = (math.log10(amount) - math.log10(min_val)) / (
            math.log10(max_val) - math.log10(min_val)
        )

    if t < 0.5:
        r = int(255 * (t * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (t - 0.5) * 2))
    b = 0

    return f"ff{b:02x}{g:02x}{r:02x}"


def build_popup_html(pin: ContractPin) -> str:
    """Build HTML description for a KML placemark popup."""
    amount_str = f"${pin.dollar_amount:,.0f}" if pin.dollar_amount else "N/A"
    return (
        f"<b>{escape(pin.company_name)}</b><br/>"
        f"<b>Amount:</b> {amount_str}<br/>"
        f"<b>Contract:</b> {escape(pin.contract_number)}<br/>"
        f"<b>Branch:</b> {escape(pin.branch)}<br/>"
        f"<b>Completion:</b> {escape(pin.completion_date)}<br/>"
        f"<hr/>"
        f"<small>{escape(pin.raw_text[:500])}</small>"
    )


def format_dollar_amount(amount: float) -> str:
    return f"${amount:,.0f}"
```

**Commit:** `feat: add KML construction logic with colour gradient`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: KML export orchestration (Imperative Shell)

**Verifies:** dod-scan.AC5.1, dod-scan.AC5.4, dod-scan.AC5.5

**Files:**
- Create: `src/dod_scan/export_kml.py`

**Implementation:**

Create `src/dod_scan/export_kml.py` — orchestration module that queries DB, builds KML, and writes to file.

```python
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
```

**Commit:** `feat: add KML export with colour gradient and filtering`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: KML export tests

**Verifies:** dod-scan.AC5.1, dod-scan.AC5.2, dod-scan.AC5.3, dod-scan.AC5.4, dod-scan.AC5.5

**Files:**
- Create: `tests/test_export_kml_build.py`
- Create: `tests/test_export_kml.py`

**Testing:**

Tests must verify each AC listed above:

- dod-scan.AC5.1: `export_kml` creates a file that is valid KML (can be parsed as XML). File contains one placemark per geocoded contract.

- dod-scan.AC5.2: `dollar_to_kml_colour` returns green-ish for small amounts (~$1M), yellow-ish for medium (~$100M), red-ish for large (~$10B). Verify specific hex values for known inputs. All values are valid 8-char hex strings starting with "ff" (full opacity).

- dod-scan.AC5.3: `build_popup_html` includes company_name, formatted dollar amount, contract_number, branch, completion_date, and truncated raw_text. HTML-escapes special characters.

- dod-scan.AC5.4: Insert contracts with different publish_dates. Export with `since="2026-03-10"`. Verify only contracts from 2026-03-10 onward appear in output.

- dod-scan.AC5.5: Insert contracts for ARMY and NAVY branches. Export with `branch="ARMY"`. Verify only ARMY contracts appear. Case-insensitive filter.

Use `tmp_db` fixture. Insert full test data (pages + contracts + classifications + contract_locations) to test the export pipeline end-to-end.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_export_kml_build.py tests/test_export_kml.py -v`
Expected: All tests pass

**Commit:** `test: add KML export tests`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_4 -->
### Task 4: Wire export subcommand for KML

**Files:**
- Modify: `src/dod_scan/cli.py` — update `export` command to support `--format kml`

**Implementation:**

Update the `export` command in `cli.py`:

```python
@app.command()
def export(
    format: str = typer.Option("kml", "--format", "-f", help="Export format: kml, map, or all"),
    since: str = typer.Option(None, "--since", help="Filter to contracts from this date onward (YYYY-MM-DD)"),
    branch: str = typer.Option(None, "--branch", help="Filter to specific branch (e.g. ARMY)"),
) -> None:
    """Export geocoded procurement contracts as KML and/or Mapbox dashboard."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if format in ("kml", "all"):
            from dod_scan.export_kml import export_kml
            kml_path = settings.output_dir / "dod_contracts.kml"
            export_kml(conn, kml_path, since=since, branch=branch)
            typer.echo(f"KML exported to {kml_path}")

        if format in ("map", "all"):
            typer.echo("map export: not yet implemented (Phase 7)")
            if format == "map":
                raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"Export failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan export --help`
Expected: Shows help with --format, --since, --branch options

**Commit:** `feat: wire export subcommand for KML output`
<!-- END_TASK_4 -->

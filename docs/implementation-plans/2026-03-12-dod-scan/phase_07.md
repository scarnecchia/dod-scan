# DOD Contract Scanner Implementation Plan — Phase 7

**Goal:** Generate interactive HTML map dashboard with graceful degradation.

**Architecture:** Jinja2 template for self-contained HTML with embedded Mapbox GL JS and GeoJSON data. Contract data serialised as GeoJSON features with properties for filtering. Client-side JS handles sidebar filters (date range, branch, dollar amount). Graceful degradation: no MAPBOX_TOKEN + `--format all` produces KML only with log message; `--format map` without token exits with error.

**Tech Stack:** Python 3.10+, Jinja2, Mapbox GL JS v3.20.0 (CDN), SQLite

**Scope:** 8 phases from original design (phase 7 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-6 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC6: Mapbox dashboard export
- **dod-scan.AC6.1 Success:** Self-contained HTML file generated with Mapbox GL JS map when MAPBOX_TOKEN is set
- **dod-scan.AC6.2 Success:** Clicking a pin shows popup with full contract details
- **dod-scan.AC6.3 Success:** Sidebar/panel filters by date range, branch, and dollar amount
- **dod-scan.AC6.4 Failure:** No MAPBOX_TOKEN + `--format all` produces KML only with log message
- **dod-scan.AC6.5 Failure:** No MAPBOX_TOKEN + `--format map` exits with helpful error message

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: GeoJSON data building (Functional Core)

**Verifies:** dod-scan.AC6.1, dod-scan.AC6.2

**Files:**
- Create: `src/dod_scan/export_map_data.py`

**Implementation:**

Create `src/dod_scan/export_map_data.py` — pure functions for building GeoJSON from contract data.

```python
# pattern: Functional Core
"""GeoJSON construction for Mapbox dashboard."""

from __future__ import annotations

import json
from html import escape

from dod_scan.export_kml_build import ContractPin, format_dollar_amount


def pins_to_geojson(pins: list[ContractPin]) -> str:
    features = [_pin_to_feature(pin) for pin in pins]
    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    return json.dumps(collection)


def _pin_to_feature(pin: ContractPin) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [pin.longitude, pin.latitude],
        },
        "properties": {
            "company_name": pin.company_name,
            "dollar_amount": pin.dollar_amount,
            "dollar_display": format_dollar_amount(pin.dollar_amount),
            "contract_number": pin.contract_number,
            "branch": pin.branch,
            "completion_date": pin.completion_date,
            "publish_date": pin.publish_date,
            "description": pin.raw_text[:500],
        },
    }


def get_unique_branches(pins: list[ContractPin]) -> list[str]:
    return sorted({pin.branch for pin in pins if pin.branch})
```

**Commit:** `feat: add GeoJSON construction for Mapbox dashboard`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Jinja2 HTML template

**Verifies:** dod-scan.AC6.1, dod-scan.AC6.2, dod-scan.AC6.3

**Files:**
- Create: `src/dod_scan/templates/map.html`

**Implementation:**

Create `src/dod_scan/templates/map.html` — Jinja2 template for the self-contained Mapbox dashboard. The template receives `mapbox_token`, `geojson_data` (JSON string), and `branches` (list of branch names).

The template should include:
- Mapbox GL JS v3.20.0 via CDN (`<script>` and `<link>` tags)
- Full-page map with sidebar panel
- Sidebar contains:
  - Branch filter: dropdown/checkboxes for each branch
  - Date range filter: two date inputs (from/to)
  - Dollar amount filter: min/max range inputs
  - "Reset Filters" button
  - Summary stats: total contracts, total dollar value
- GeoJSON data embedded as inline `<script>` variable
- Click handler that shows popup with company_name, dollar_amount, contract_number, branch, completion_date, description
- `map.setFilter()` applied on filter changes
- Circle layer with colour based on dollar_amount (matching KML gradient)

The template is a standard Jinja2 HTML file. Implementation details left to task-implementor since the template involves substantial HTML/CSS/JS that should be written at execution time with the full Mapbox GL JS API reference available.

**Commit:** `feat: add Mapbox dashboard Jinja2 template`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Map export tests

**Verifies:** dod-scan.AC6.1, dod-scan.AC6.2, dod-scan.AC6.3, dod-scan.AC6.4, dod-scan.AC6.5

**Files:**
- Create: `tests/test_export_map_data.py`
- Create: `tests/test_export_map.py`

**Testing:**

Tests must verify each AC listed above:

- dod-scan.AC6.1: `pins_to_geojson` produces valid JSON with FeatureCollection type, correct number of features, each feature has Point geometry with [lon, lat] coordinates. `export_map` with a MAPBOX_TOKEN produces an HTML file containing the Mapbox GL JS CDN script tag and the GeoJSON data.

- dod-scan.AC6.2: Each GeoJSON feature's properties contain company_name, dollar_amount, dollar_display, contract_number, branch, completion_date, publish_date, description. Verify popup content will be available (properties are correctly populated).

- dod-scan.AC6.3: `get_unique_branches` returns sorted unique branch names from pins. The HTML output contains filter elements (verify by checking for branch names in the sidebar markup).

- dod-scan.AC6.4: Call `export_map` with `mapbox_token=""` and `format="all"`. Verify it returns without error, logs a message about missing token, and does NOT produce an HTML file.

- dod-scan.AC6.5: Call `export_map` with `mapbox_token=""` and `format="map"`. Verify it raises an error with a helpful message about configuring MAPBOX_TOKEN.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_export_map_data.py tests/test_export_map.py -v`
Expected: All tests pass

**Commit:** `test: add Mapbox dashboard export tests`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_TASK_4 -->
### Task 4: Map export orchestration (Imperative Shell)

**Verifies:** dod-scan.AC6.1, dod-scan.AC6.4, dod-scan.AC6.5

**Files:**
- Create: `src/dod_scan/export_map.py`

**Implementation:**

Create `src/dod_scan/export_map.py` — orchestration module that queries DB, builds GeoJSON, renders Jinja2 template, and writes HTML file.

```python
# pattern: Imperative Shell
"""Mapbox dashboard export — generates self-contained HTML with interactive map."""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from dod_scan.export_map_data import get_unique_branches, pins_to_geojson

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


class MapExportError(Exception):
    pass


def export_map(
    pins: list,
    output_path: Path,
    mapbox_token: str,
) -> Path:
    if not mapbox_token:
        raise MapExportError(
            "MAPBOX_TOKEN not configured. Set it in your .env file to generate the Mapbox dashboard."
        )

    geojson = pins_to_geojson(pins)
    branches = get_unique_branches(pins)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("map.html")

    html = template.render(
        mapbox_token=mapbox_token,
        geojson_data=geojson,
        branches=branches,
        total_contracts=len(pins),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Mapbox dashboard written to %s", output_path)
    return output_path
```

**Commit:** `feat: add Mapbox dashboard export orchestration`
<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Update CLI export command for map support

**Files:**
- Modify: `src/dod_scan/cli.py` — update `export` command to handle `--format map` and `--format all` with graceful degradation

**Implementation:**

Update the `export` command in `cli.py` to support all three formats:

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
            if not settings.mapbox_token:
                if format == "all":
                    typer.echo("MAPBOX_TOKEN not set — skipping map export, KML only")
                else:
                    typer.echo(
                        "Error: MAPBOX_TOKEN not set. Configure in .env file to generate Mapbox dashboard.",
                        err=True,
                    )
                    raise typer.Exit(code=1)
            else:
                from dod_scan.export_kml import query_contract_pins
                from dod_scan.export_map import export_map
                pins = query_contract_pins(conn, since, branch)
                map_path = settings.output_dir / "dod_contracts.html"
                export_map(pins, map_path, settings.mapbox_token)
                typer.echo(f"Mapbox dashboard exported to {map_path}")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Export failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan export --help`
Expected: Shows help with format options including map and all

**Commit:** `feat: wire map export with graceful degradation for missing MAPBOX_TOKEN`
<!-- END_TASK_5 -->

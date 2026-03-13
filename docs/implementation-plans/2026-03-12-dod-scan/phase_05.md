# DOD Contract Scanner Implementation Plan — Phase 5

**Goal:** Resolve contract locations to lat/lon coordinates with caching.

**Architecture:** Functional Core for location resolution logic (choosing work location vs company HQ fallback), Imperative Shell for Nominatim API calls and SQLite cache. Nominatim chosen over Census Bureau because Census requires full street addresses — we only have city/state. Rate limiting at 1 req/sec with time.sleep between uncached requests.

**Tech Stack:** Python 3.10+, httpx, Nominatim API, SQLite

**Scope:** 8 phases from original design (phase 5 of 8)

**Codebase verified:** 2026-03-12 — greenfield, Phase 1-4 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC4: Geocoding locations
- **dod-scan.AC4.1 Success:** Work location geocoded when present in contract text
- **dod-scan.AC4.2 Success:** Company HQ location used as fallback when work location is unspecified or "TBD"
- **dod-scan.AC4.3 Success:** Cached locations returned without API call
- **dod-scan.AC4.4 Failure:** Geocoding API failure logged, contract skipped (doesn't block pipeline)
- **dod-scan.AC4.5 Edge:** Multiple work locations — primary location (highest percentage or first listed) used for pin

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Location resolution logic (Functional Core)

**Verifies:** dod-scan.AC4.1, dod-scan.AC4.2, dod-scan.AC4.5

**Files:**
- Create: `src/dod_scan/geocoder_resolve.py`

**Implementation:**

Create `src/dod_scan/geocoder_resolve.py` — pure functions for determining which location to geocode for a contract.

```python
# pattern: Functional Core
"""Location resolution logic — determines which location to geocode for a contract."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocationToGeocode:
    city: str
    state: str
    source: str  # "work_location" or "company_hq"


def resolve_location(
    work_locations_json: str,
    company_city: str,
    company_state: str,
) -> LocationToGeocode | None:
    location = _resolve_from_work_locations(work_locations_json)
    if location:
        return location

    if company_city and company_state:
        return LocationToGeocode(
            city=company_city,
            state=company_state,
            source="company_hq",
        )

    return None


def _resolve_from_work_locations(work_locations_json: str) -> LocationToGeocode | None:
    try:
        locations = json.loads(work_locations_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not locations:
        return None

    if any("pct" in loc for loc in locations):
        primary = max(locations, key=lambda loc: loc.get("pct", 0))
    else:
        primary = locations[0]

    city = primary.get("city", "").strip()
    state = primary.get("state", "").strip()

    if city and state:
        return LocationToGeocode(city=city, state=state, source="work_location")

    return None


def make_location_key(city: str, state: str) -> str:
    return f"{city.lower().strip()}, {state.lower().strip()}"
```

**Commit:** `feat: add location resolution logic for geocoding`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: Nominatim API client and cache (Imperative Shell)

**Verifies:** dod-scan.AC4.1, dod-scan.AC4.3, dod-scan.AC4.4

**Files:**
- Create: `src/dod_scan/geocoder_api.py`

**Implementation:**

Create `src/dod_scan/geocoder_api.py` — Nominatim API client with SQLite cache and rate limiting.

```python
# pattern: Imperative Shell
"""Nominatim geocoding API client with SQLite cache and rate limiting."""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from dod_scan.geocoder_resolve import make_location_key

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "dod-scan/1.0 (DOD contract scanner)"
RATE_LIMIT_SECONDS = 1.1


@dataclass(frozen=True)
class GeocodedLocation:
    latitude: float
    longitude: float


class GeocodingError(Exception):
    pass


def geocode_city_state(
    city: str,
    state: str,
    conn: sqlite3.Connection,
) -> GeocodedLocation | None:
    key = make_location_key(city, state)

    cached = _get_cached(conn, key)
    if cached:
        logger.debug("Cache hit for %s", key)
        return cached

    logger.info("Geocoding %s, %s via Nominatim", city, state)
    time.sleep(RATE_LIMIT_SECONDS)

    try:
        result = _call_nominatim(city, state)
    except GeocodingError:
        logger.exception("Geocoding failed for %s, %s", city, state)
        return None

    if result:
        _cache_result(conn, key, result)

    return result


def _get_cached(conn: sqlite3.Connection, key: str) -> GeocodedLocation | None:
    row = conn.execute(
        "SELECT latitude, longitude FROM geocode_cache WHERE location_key = ?",
        (key,),
    ).fetchone()
    if row:
        return GeocodedLocation(latitude=row["latitude"], longitude=row["longitude"])
    return None


def _cache_result(
    conn: sqlite3.Connection, key: str, location: GeocodedLocation
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO geocode_cache (location_key, latitude, longitude, geocoded_at)
        VALUES (?, ?, ?, ?)
        """,
        (key, location.latitude, location.longitude, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _call_nominatim(city: str, state: str) -> GeocodedLocation | None:
    params = {
        "city": city,
        "state": state,
        "country": "United States",
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = httpx.get(NOMINATIM_URL, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Nominatim request failed: {exc}") from exc

    results = resp.json()
    if not results:
        logger.warning("No Nominatim results for %s, %s", city, state)
        return None

    return GeocodedLocation(
        latitude=float(results[0]["lat"]),
        longitude=float(results[0]["lon"]),
    )
```

**Commit:** `feat: add Nominatim geocoding client with SQLite cache`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Geocoder tests

**Verifies:** dod-scan.AC4.1, dod-scan.AC4.2, dod-scan.AC4.3, dod-scan.AC4.4, dod-scan.AC4.5

**Files:**
- Create: `tests/test_geocoder_resolve.py`
- Create: `tests/test_geocoder_api.py`

**Testing:**

Tests must verify each AC listed above:

- dod-scan.AC4.1: `resolve_location` with valid work_locations JSON (e.g., `[{"city": "Seattle", "state": "Washington"}]`) returns LocationToGeocode with source="work_location".

- dod-scan.AC4.2: `resolve_location` with empty work_locations (`"[]"`) and valid company_city/state returns LocationToGeocode with source="company_hq". Also test with `None` and invalid JSON for work_locations.

- dod-scan.AC4.3: `geocode_city_state` with a pre-populated `geocode_cache` row returns cached result without calling Nominatim. Mock httpx.get and verify it was NOT called.

- dod-scan.AC4.4: `_call_nominatim` when httpx raises HTTPError, GeocodingError is raised. `geocode_city_state` catches GeocodingError and returns None (doesn't block pipeline).

- dod-scan.AC4.5: `resolve_location` with multiple work locations with percentages (e.g., `[{"city": "Bloomington", "state": "Minnesota", "pct": 68}, {"city": "St. Louis", "state": "Missouri", "pct": 22}]`) returns the one with highest pct (Bloomington). Without pct, returns first listed.

- `make_location_key` normalises to lowercase: `make_location_key("Arlington", "Virginia")` == `"arlington, virginia"`.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_geocoder_resolve.py tests/test_geocoder_api.py -v`
Expected: All tests pass

**Commit:** `test: add geocoder resolution and API tests`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_SUBCOMPONENT_B (tasks 4-5) -->
<!-- START_TASK_4 -->
### Task 4: Geocoder orchestration and DB persistence

**Verifies:** dod-scan.AC4.1, dod-scan.AC4.2

**Files:**
- Create: `src/dod_scan/geocoder.py`

**Implementation:**

Create `src/dod_scan/geocoder.py` — orchestration module that reads procurement contracts, resolves locations, and geocodes them.

```python
# pattern: Imperative Shell
"""Geocoder orchestration — resolves and geocodes locations for procurement contracts."""

from __future__ import annotations

import logging
import sqlite3

from dod_scan.geocoder_api import geocode_city_state
from dod_scan.geocoder_resolve import resolve_location

logger = logging.getLogger(__name__)


def geocode_all(conn: sqlite3.Connection) -> int:
    contracts = conn.execute(
        """
        SELECT c.id, c.work_locations, c.company_city, c.company_state
        FROM contracts c
        JOIN classifications cl ON cl.contract_id = c.id
        WHERE cl.is_procurement = 1
        AND c.id NOT IN (
            SELECT contract_id FROM contract_locations
        )
        """,
    ).fetchall()

    geocoded_count = 0

    for row in contracts:
        contract_id = row["id"]
        location = resolve_location(
            row["work_locations"], row["company_city"], row["company_state"]
        )

        if location is None:
            logger.warning("No location to geocode for contract %d", contract_id)
            continue

        result = geocode_city_state(location.city, location.state, conn)
        if result is None:
            logger.warning("Geocoding failed for contract %d", contract_id)
            continue

        _store_contract_location(
            conn, contract_id, result.latitude, result.longitude, location.source
        )
        geocoded_count += 1

    logger.info("Geocoding complete: %d contracts geocoded", geocoded_count)
    return geocoded_count


def _store_contract_location(
    conn: sqlite3.Connection,
    contract_id: int,
    latitude: float,
    longitude: float,
    source: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO contract_locations (
            contract_id, latitude, longitude, source
        ) VALUES (?, ?, ?, ?)
        """,
        (contract_id, latitude, longitude, source),
    )
    conn.commit()
```

**Note:** This introduces a new `contract_locations` table not in the original schema. Add it to `db.py`'s SCHEMA_SQL:

```sql
CREATE TABLE IF NOT EXISTS contract_locations (
    contract_id      INTEGER PRIMARY KEY REFERENCES contracts(id),
    latitude         REAL NOT NULL,
    longitude        REAL NOT NULL,
    source           TEXT NOT NULL
);
```

**Commit:** `feat: add geocoder orchestration and contract_locations table`
<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Geocoder orchestration tests

**Verifies:** dod-scan.AC4.1, dod-scan.AC4.2

**Files:**
- Create: `tests/test_geocoder_orchestration.py`

**Testing:**

Tests must verify the orchestration layer against the DB:

- dod-scan.AC4.1: Insert contract + classification (procurement) rows. Mock `geocode_city_state` to return a GeocodedLocation. Call `geocode_all()`. Verify `contract_locations` table has row with correct lat/lon.

- dod-scan.AC4.2: Insert contract with empty work_locations and valid company_city/state. Verify geocoding uses company HQ as fallback. Check `source` column in `contract_locations` is "company_hq".

- Idempotency: Call `geocode_all()` twice. Second call should skip already-geocoded contracts.

- Service contracts are not geocoded: Insert contract + classification with is_procurement=0. Verify it's not included in geocoding.

Use `tmp_db` and `db_conn` fixtures. Mock `geocode_city_state` to avoid real API calls.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_geocoder_orchestration.py -v`
Expected: All tests pass

**Commit:** `test: add geocoder orchestration tests`
<!-- END_TASK_5 -->
<!-- END_SUBCOMPONENT_B -->

<!-- START_TASK_6 -->
### Task 6: Wire geocode subcommand in CLI

**Files:**
- Modify: `src/dod_scan/cli.py` — replace `geocode` stub with real implementation
- Modify: `src/dod_scan/db.py` — add `contract_locations` table to SCHEMA_SQL

**Implementation:**

Update the `geocode` command in `cli.py`:

```python
@app.command()
def geocode() -> None:
    """Resolve contract locations to lat/lon coordinates."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.geocoder import geocode_all
        count = geocode_all(conn)
        typer.echo(f"Geocoding complete: {count} contracts geocoded")
    except Exception as exc:
        typer.echo(f"Geocoding failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan geocode --help`
Expected: Shows help text

**Commit:** `feat: wire geocode subcommand to geocoder orchestration`
<!-- END_TASK_6 -->

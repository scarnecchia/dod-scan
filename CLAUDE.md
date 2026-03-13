# DOD Contract Scanner

Last verified: 2026-03-12

## Tech Stack
- Language: Python 3.10+
- CLI: Typer
- Config: pydantic-settings (`.env` file)
- Database: SQLite (WAL mode, foreign keys on)
- HTTP: httpx (Playwright optional fallback for 403s)
- HTML parsing: BeautifulSoup4 + lxml
- LLM: Anthropic SDK or OpenRouter (httpx)
- Geo: Nominatim API (SQLite-cached)
- KML: simplekml
- Map: Mapbox GL JS via Jinja2 template
- Linting: ruff (line-length 100)
- Testing: pytest

## Commands
- `pip install -e ".[dev,browser]"` - Install with all extras
- `pytest` - Run tests
- `ruff check src/ tests/` - Lint
- `dod-scan init-db` - Create/migrate SQLite schema
- `dod-scan run-all` - Full pipeline: scrape -> parse -> classify -> geocode -> export
- `dod-scan scrape`, `parse`, `classify`, `geocode`, `export` - Individual stages

## Architecture: Functional Core / Imperative Shell

Every module is annotated with `# pattern: Functional Core` or `# pattern: Imperative Shell`.

- **Pure functions** (Functional Core): `*_parse.py`, `*_extract.py`, `*_fields.py`, `*_build.py`, `*_data.py`, `*_resolve.py`, `*_prompt.py`
- **Side-effecting orchestrators** (Imperative Shell): `scraper.py`, `parser.py`, `classifier.py`, `geocoder.py`, `export_kml.py`, `export_map.py`, `cli.py`, `db.py`, `config.py`

Domain groupings by file prefix (flat module, no subdirectories):
- `scraper*` - war.gov index + article fetching
- `parser*` - HTML contract extraction, field regex
- `classifier*` - LLM-based procurement vs service classification
- `geocoder*` - Nominatim location resolution with cache
- `export_kml*` - KML file generation with colour gradient
- `export_map*` - Mapbox HTML dashboard generation

## Database Schema (5 tables)
- `pages` - Raw HTML keyed by `article_id`
- `contracts` - Parsed contract fields (FK to pages)
- `classifications` - LLM results (FK to contracts)
- `geocode_cache` - Nominatim response cache by location key
- `contract_locations` - Resolved lat/lon per contract (FK to contracts)

Schema lives in `db.py` as `SCHEMA_SQL`. All tables use `CREATE TABLE IF NOT EXISTS`.

## Key Contracts
- **CLI entry**: `dod_scan.cli:app` (registered in pyproject.toml as `dod-scan`)
- **Pipeline order**: scrape -> parse -> classify -> geocode -> export (enforced by `run-all`)
- **LLMProvider protocol**: `classify(user_prompt: str) -> str` + `model_name` property
- **Config**: `Settings` class reads from `.env`; keys: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `MAPBOX_TOKEN`, `DATABASE_PATH`, `OUTPUT_DIR`, `LOG_DIR`
- **Export filtering**: Both KML and map export accept `--since` (date) and `--branch` filters
- **Mapbox graceful degradation**: `run-all --format=all` skips map if `MAPBOX_TOKEN` unset; standalone `export --format=map` errors

## Conventions
- All DB connections use `sqlite3.Row` row factory
- WAL journal mode and foreign keys enabled on every connection
- Orchestration modules return counts (int) for CLI display
- Lazy imports in CLI commands to keep startup fast
- Logging: file handler (INFO+) to `logs/dod_scan.log`, console (WARNING+)

## Invariants
- `article_id` is the dedup key for scraping (no duplicate fetches)
- Only `is_procurement = 1` contracts appear in exports
- Geocode cache is keyed by normalised location string, never expires
- KML colour gradient maps dollar amounts to a green-yellow-red scale

## Boundaries
- Safe to edit: `src/dod_scan/`, `tests/`
- Do not edit: `docs/implementation-plans/` (historical record)
- Design doc: `docs/design-plans/2026-03-12-dod-scan.md`

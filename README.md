# DOD Contract Scanner

## Overview

dod-scan is a comprehensive pipeline for scraping, parsing, classifying, geocoding, and exporting U.S. Department of Defense contract awards from war.gov. It fetches daily contract announcements, extracts structured data from HTML, uses an LLM to classify contracts as procurement or service contracts, resolves locations to geographic coordinates, and exports results as interactive KML maps and Mapbox dashboards.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** — Fast Python package manager (handles Python, venvs, and dependencies)
- **Mapbox account (optional)** — For interactive HTML map dashboards; KML export works without it
- **LLM API access (required for classification)** — OpenRouter, Anthropic, or compatible provider
- **Playwright (optional)** — For handling bot-protected pages on war.gov

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/scarnecchia/dod-scan.git
cd dod-scan
```

### 2. Install dependencies

```bash
uv sync --extra dev
```

This creates a virtual environment, installs Python 3.10+ if needed, and resolves all dependencies.

### 3. (Optional) Install Playwright for bot-protected pages

```bash
uv sync --all-extras
uv run playwright install chromium
```

## Configuration

### Create a .env file

Copy the example configuration:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```
# LLM Provider Configuration
# Supported providers: "openrouter" or "anthropic"
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-...your-api-key...
LLM_MODEL=anthropic/claude-haiku-4-5-20251001

# Optional: Mapbox token for interactive HTML dashboard
# Leave blank to skip map export
MAPBOX_TOKEN=pk-...your-mapbox-token...

# Database and output paths
# Relative paths are resolved from the dod-scan directory
DATABASE_PATH=./dod_scan.db
OUTPUT_DIR=./output
LOG_DIR=./logs
```

### Configuration variables explained

- **LLM_PROVIDER** — Which LLM service to use for contract classification
- **LLM_API_KEY** — Your API key for the LLM provider (required)
- **LLM_MODEL** — Model identifier (e.g., Anthropic Haiku, GPT-4, etc.)
- **MAPBOX_TOKEN** — Token for Mapbox Services; required only for HTML map export
- **DATABASE_PATH** — SQLite database file location (created if missing)
- **OUTPUT_DIR** — Directory where KML and HTML exports are written
- **LOG_DIR** — Directory for pipeline logs (created if missing)

## Usage

### Initialize the database (first run only)

```bash
uv run dod-scan init-db
```

### Run the full pipeline

Execute all stages in sequence (scrape → parse → classify → geocode → export):

```bash
uv run dod-scan run-all
```

With options:

```bash
# Fetch 10 historical pages during scrape
uv run dod-scan run-all --backfill 10

# Export both KML and Mapbox dashboard
uv run dod-scan run-all --format all

# Filter exports to contracts from January 2026 onward
uv run dod-scan run-all --since 2026-01-01

# Filter to a specific military branch
uv run dod-scan run-all --branch NAVY

# Combine options
uv run dod-scan run-all --backfill 5 --format all --since 2026-01-01 --branch ARMY
```

### Run individual stages

Run only the scraper:

```bash
uv run dod-scan scrape
uv run dod-scan scrape --backfill 5
```

Extract structured data from raw HTML:

```bash
uv run dod-scan parse
```

Classify contracts as procurement vs service:

```bash
uv run dod-scan classify
```

Resolve contract locations to coordinates:

```bash
uv run dod-scan geocode
```

Export contracts to KML and/or Mapbox:

```bash
uv run dod-scan export
uv run dod-scan export --format kml
uv run dod-scan export --format map
uv run dod-scan export --format all
uv run dod-scan export --since 2026-01-01 --branch ARMY
```

## Scheduling (Cron)

### Add a daily cron job

Run the full pipeline daily at 6 PM (assuming DOD publishes at 5 PM):

```bash
crontab -e
```

Add this line:

```
0 18 * * 1-5 cd /path/to/dod-scan && uv run dod-scan run-all >> /path/to/dod-scan/logs/cron.log 2>&1
```

### Cron schedule breakdown

- `0 18` — 6:00 PM
- `* * 1-5` — Every weekday (Monday–Friday)
- `cd /path/to/dod-scan` — Navigate to the project directory
- `uv run dod-scan` — Run the CLI via uv (handles venv automatically)
- `run-all` — Execute the full pipeline
- `>> /path/to/dod-scan/logs/cron.log 2>&1` — Log output to cron.log

Replace `/path/to/dod-scan` with the actual absolute path to your dod-scan directory.

## Output Files

Pipeline outputs are written to the `OUTPUT_DIR` directory (default: `./output`):

- **dod_contracts.kml** — KML file containing all contract locations, importable into Google Earth, ArcGIS, or other GIS tools
- **dod_contracts.html** — Interactive Mapbox dashboard (only created if MAPBOX_TOKEN is configured)

### Viewing KML in Google Earth

1. Open [Google Earth Pro](https://www.google.com/earth/download/gep/agree.html) or [Google Earth Web](https://earth.google.com)
2. Click **File → Open** and select `dod_contracts.kml`
3. Zoom to see contract locations marked on the map
4. Click any marker to view contract details

### Filtering outputs

Use export options to limit results:

```bash
# Only contracts from 2026 onward
dod-scan export --since 2026-01-01

# Only Navy contracts
dod-scan export --branch NAVY

# Both filters combined
dod-scan export --since 2026-01-01 --branch ARMY
```

## Troubleshooting

### 403 Forbidden errors from war.gov

The war.gov site may block aggressive scraping. If you see 403 errors:

1. **Add backoff delays** — The scraper includes delays, but you can reduce backfill to fetch fewer pages per run
2. **Use Playwright fallback** — Install the browser extra: `uv sync --all-extras` and `uv run playwright install chromium`
3. **Reduce frequency** — Run daily instead of hourly; scraper respects rate limits

### Missing LLM_API_KEY

If you see "LLM_API_KEY not set":

1. Check your `.env` file has `LLM_API_KEY=sk-...` (not empty)
2. Verify the key is valid with your LLM provider
3. Test: `uv run dod-scan classify` should not fail on missing credentials

### Geocoding rate limits

If geocoding slows or fails:

1. The geocoder respects rate limits and backs off automatically
2. Resume processing: `uv run dod-scan geocode` will continue where it left off
3. Check logs: `tail -f logs/dod_scan.log` for detailed errors

### MAPBOX_TOKEN not set

If map export fails:

1. Install token: Set `MAPBOX_TOKEN=pk-...` in `.env`
2. Create a token at [mapbox.com/account/tokens](https://account.mapbox.com/tokens)
3. Or skip map export: Use `uv run dod-scan export --format kml` for KML only

### Database locked errors

If you see "database is locked":

1. Ensure only one instance of dod-scan is running
2. Check for stale processes: `ps aux | grep dod-scan`
3. Remove lock file if needed: `rm dod_scan.db-wal dod_scan.db-shm` (after stopping all instances)

### Logs not appearing

Check the log directory:

```bash
ls -la logs/
tail -f logs/dod_scan.log
```

If `LOG_DIR` doesn't exist, it will be created on first run. Verify the directory is writable.

### Common log messages

- **"Starting stage: scrape"** — Normal pipeline progress
- **"403 Forbidden"** — war.gov rejected the request (rate limiting); retries will occur
- **"No contracts to classify"** — All contracts already classified; nothing to do
- **"Geocoding complete: 0 contracts geocoded"** — All contracts already geocoded

## Support

For issues, questions, or contributions, please refer to the project repository or documentation.

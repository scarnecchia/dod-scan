# Test Requirements — DOD Contract Scanner

## Automated Tests

| AC ID | Description | Test Type | Test File | Test Description |
|-------|-------------|-----------|-----------|------------------|
| dod-scan.AC1.1 | Scraper fetches today's contract page and stores raw HTML in SQLite | unit | `tests/test_scraper_parse.py` | `extract_article_links` parses index HTML and returns correct ArticleLink objects with article_id, url, title; `build_index_url` generates correct URL for page 1 |
| dod-scan.AC1.1 | Scraper fetches today's contract page and stores raw HTML in SQLite | integration | `tests/test_scraper_orchestration.py` | `scrape()` with `backfill=0` fetches index page 1, extracts links, fetches each article, stores HTML in `pages` table; verify rows exist with correct article_id, url, raw_html |
| dod-scan.AC1.2 | `--backfill N` paginates through N pages of historical listings | unit | `tests/test_scraper_parse.py` | `build_index_url(page=3)` returns URL with `?Page=3`; article links extracted from multiple fixture pages |
| dod-scan.AC1.2 | `--backfill N` paginates through N pages of historical listings | integration | `tests/test_scraper_orchestration.py` | `scrape()` with `backfill=2` fetches index pages 1, 2, and 3; verify `build_index_url` called for all three pages via mocked `fetch_page` |
| dod-scan.AC1.3 | Already-scraped pages skipped without re-fetching | integration | `tests/test_scraper_orchestration.py` | Pre-insert article_id into `pages` table, call `scrape()`, verify `fetch_page` was NOT called for the duplicate article URL |
| dod-scan.AC1.4 | 403 from httpx triggers Playwright fallback transparently | unit | `tests/test_scraper.py` | Mock httpx to return 403 status; verify `fetch_page` catches it and calls Playwright fallback; mock Playwright to return HTML and verify it is returned |
| dod-scan.AC1.5 | Network errors logged to file, scrape stage exits non-zero | unit | `tests/test_scraper.py` | httpx.TimeoutException and httpx.HTTPError raise FetchError with descriptive message; verify FetchError is raised |
| dod-scan.AC2.1 | Each contract paragraph extracted as separate row with all fields | unit | `tests/test_parser_extract.py` | `extract_contracts_from_html` returns one RawContract per contract paragraph from fixture article HTML with correct branch assignment |
| dod-scan.AC2.1 | Each contract paragraph extracted as separate row with all fields | unit | `tests/test_parser_fields.py` | `parse_contract_fields` extracts company_name, company_city, company_state, dollar_amount, contract_number, work_locations, completion_date, contracting_activity from real Boeing/Navy/Army contract text samples |
| dod-scan.AC2.1 | Each contract paragraph extracted as separate row with all fields | integration | `tests/test_parser_orchestration.py` | Insert `pages` row with fixture HTML, call `parse_all()`, verify `contracts` table has rows with correct branch, company_name, dollar_amount, etc. |
| dod-scan.AC2.2 | Modification codes extracted and `is_modification` set correctly | unit | `tests/test_parser_fields.py` | `"modification (P00045)"` returns mod_code="P00045", is_modification=True; `"modification (P00008 and P00014)"` returns mod_code="P00008", is_modification=True; non-modification returns mod_code="", is_modification=False |
| dod-scan.AC2.3 | Multiple work locations with percentages parsed into JSON array | unit | `tests/test_parser_fields.py` | Navy contract with `"Bloomington, Minnesota (68%); St. Louis Missouri (22%); and Linthicum Heights, Maryland (10%)"` parses to JSON array with correct city, state, pct values |
| dod-scan.AC2.4 | Raw text preserved verbatim for every contract entry | unit | `tests/test_parser_extract.py` | Verify `RawContract.raw_text` matches input paragraph text exactly |
| dod-scan.AC2.4 | Raw text preserved verbatim for every contract entry | integration | `tests/test_parser_orchestration.py` | Verify `raw_text` column in `contracts` table matches original paragraph text verbatim after `parse_all()` |
| dod-scan.AC2.5 | Small business asterisk stripped from company name | unit | `tests/test_parser_fields.py` | `"Technomics Inc.,* Arlington, Virginia,"` extracts company_name="Technomics Inc." (asterisk stripped); also test `"Singularity Security Group LLC,*"` |
| dod-scan.AC2.6 | "Work locations TBD" results in empty work_locations | unit | `tests/test_parser_fields.py` | Text containing "Work locations and funding will be determined with each order" returns work_locations="[]" |
| dod-scan.AC3.1 | Unclassified contracts sent to LLM and result stored | unit | `tests/test_classifier_prompt.py` | `build_classification_prompt` includes contract text; `parse_classification_response` extracts is_procurement, confidence, reasoning from valid JSON |
| dod-scan.AC3.1 | Unclassified contracts sent to LLM and result stored | integration | `tests/test_classifier_orchestration.py` | Insert contract rows, mock LLMProvider returning valid JSON, call `classify_all()`, verify `classifications` table has rows with correct fields |
| dod-scan.AC3.2 | Already-classified contracts skipped on re-run | integration | `tests/test_classifier_orchestration.py` | Insert contract + classification rows, call `classify_all()`, verify mock provider was NOT called for already-classified contract |
| dod-scan.AC3.3 | OpenRouter provider works with `LLM_PROVIDER=openrouter` | unit | `tests/test_classifier_providers.py` | `OpenRouterProvider.classify` sends correct POST to OpenRouter with auth header and payload; mock httpx.post returns valid response |
| dod-scan.AC3.4 | Anthropic provider works with `LLM_PROVIDER=anthropic` | unit | `tests/test_classifier_providers.py` | `AnthropicProvider.classify` calls `client.messages.create` with correct model, system prompt, user message; mock client returns response |
| dod-scan.AC3.5 | LLM API error logged to file, classify stage exits non-zero | unit | `tests/test_classifier_providers.py` | When httpx.post raises HTTPStatusError or Anthropic raises APIError, provider.classify propagates the exception |
| dod-scan.AC3.6 | Malformed LLM JSON handled gracefully | unit | `tests/test_classifier_prompt.py` | `parse_classification_response` with `"not json"` returns None; missing is_procurement returns None; valid JSON returns ClassificationResult |
| dod-scan.AC3.6 | Malformed LLM JSON — contract marked for retry | integration | `tests/test_classifier_orchestration.py` | Mock provider returns malformed JSON for one contract; verify no classification row; other contracts still classified |
| dod-scan.AC4.1 | Work location geocoded when present | unit | `tests/test_geocoder_resolve.py` | `resolve_location` with valid work_locations JSON returns LocationToGeocode with source="work_location" |
| dod-scan.AC4.1 | Work location geocoded when present | integration | `tests/test_geocoder_orchestration.py` | Insert procurement contract with work locations, mock `geocode_city_state`, verify `contract_locations` table has correct lat/lon |
| dod-scan.AC4.2 | Company HQ used as fallback | unit | `tests/test_geocoder_resolve.py` | `resolve_location` with empty work_locations and valid company_city/state returns LocationToGeocode with source="company_hq" |
| dod-scan.AC4.2 | Company HQ used as fallback | integration | `tests/test_geocoder_orchestration.py` | Insert contract with empty work_locations, verify `source` column is "company_hq" |
| dod-scan.AC4.3 | Cached locations returned without API call | unit | `tests/test_geocoder_api.py` | Pre-populate `geocode_cache`, call `geocode_city_state`, verify httpx.get was NOT called; cached result returned |
| dod-scan.AC4.4 | Geocoding API failure logged, contract skipped | unit | `tests/test_geocoder_api.py` | Mock httpx.get to raise HTTPError; `geocode_city_state` returns None (pipeline not blocked) |
| dod-scan.AC4.5 | Multiple work locations — highest pct or first used | unit | `tests/test_geocoder_resolve.py` | Multiple locations with pct: returns highest-pct; without pct: returns first listed |
| dod-scan.AC5.1 | Valid KML file with one placemark per geocoded contract | integration | `tests/test_export_kml.py` | `export_kml` creates parseable XML/KML; one placemark per geocoded contract in test DB |
| dod-scan.AC5.2 | Placemarks coloured by dollar amount gradient | unit | `tests/test_export_kml_build.py` | `dollar_to_kml_colour` returns green-ish for ~$1M, yellow-ish for ~$100M, red-ish for ~$10B; valid 8-char hex starting with "ff" |
| dod-scan.AC5.3 | Placemark popup contains contract details | unit | `tests/test_export_kml_build.py` | `build_popup_html` includes company_name, dollar amount, contract_number, branch, completion_date, raw_text; HTML-escapes special chars |
| dod-scan.AC5.4 | `--since DATE` filters to contracts from date onward | integration | `tests/test_export_kml.py` | Insert contracts with different dates, export with `since="2026-03-10"`, verify only matching contracts in output |
| dod-scan.AC5.5 | `--branch ARMY` filters to specified branch only | integration | `tests/test_export_kml.py` | Insert ARMY and NAVY contracts, export with `branch="ARMY"`, verify only ARMY in output; case-insensitive |
| dod-scan.AC6.1 | Self-contained HTML with Mapbox GL JS map | unit | `tests/test_export_map_data.py` | `pins_to_geojson` produces valid JSON FeatureCollection with correct features |
| dod-scan.AC6.1 | Self-contained HTML with Mapbox GL JS map | integration | `tests/test_export_map.py` | `export_map` with MAPBOX_TOKEN produces HTML containing Mapbox CDN and GeoJSON |
| dod-scan.AC6.2 | Clicking pin shows popup with details | unit | `tests/test_export_map_data.py` | Each GeoJSON feature properties contain company_name, dollar_amount, contract_number, branch, completion_date, description |
| dod-scan.AC6.3 | Sidebar filters by date range, branch, dollar amount | unit | `tests/test_export_map_data.py` | `get_unique_branches` returns sorted unique branch names |
| dod-scan.AC6.3 | Sidebar filters by date range, branch, dollar amount | integration | `tests/test_export_map.py` | Generated HTML contains filter elements with branch names |
| dod-scan.AC6.4 | No MAPBOX_TOKEN + `--format all` = KML only | integration | `tests/test_export_map.py` | Export with empty token and format="all", no HTML produced, log message emitted, no error |
| dod-scan.AC6.5 | No MAPBOX_TOKEN + `--format map` = helpful error | integration | `tests/test_export_map.py` | `export_map` with empty token raises MapExportError with MAPBOX_TOKEN message |
| dod-scan.AC7.1 | `run-all` executes all stages in sequence | integration | `tests/test_run_all.py` | Mock all five stage functions, call run-all, verify all called in order |
| dod-scan.AC7.2 | `run-all` stops on first failure with non-zero exit | integration | `tests/test_run_all.py` | Mock parse to raise, verify scrape called, parse raised, remaining NOT called, exit non-zero |
| dod-scan.AC7.3 | All stages log to file | unit | `tests/test_logging_config.py` | `configure_logging` creates log dir, writes to file, correct format, no handler duplication |
| dod-scan.AC7.3 | All stages log to file | integration | `tests/test_run_all.py` | After run-all, log file exists with stage messages |

## Human Verification

| AC ID | Description | Justification | Verification Approach |
|-------|-------------|---------------|----------------------|
| dod-scan.AC6.2 | Clicking a pin shows popup with full contract details | Popup click is client-side JS in Mapbox GL JS; data presence verified in automated tests, but click-to-popup UX requires a browser | Load generated HTML in browser with valid MAPBOX_TOKEN, click a pin, confirm popup shows company name, dollar amount, contract number, branch, completion date, description |
| dod-scan.AC6.3 | Sidebar/panel filters by date range, branch, and dollar amount | Filter interactivity is client-side JS with `map.setFilter()`; automated tests verify data and filter element presence, but actual filter behaviour requires browser interaction | Load generated HTML, use sidebar controls to filter by branch/date/amount, confirm map pins update accordingly |
| dod-scan.AC7.4 | README contains venv setup, dependency install, env var config, backfill command, cron entry, output locations | Documentation completeness is a qualitative judgment | Review README.md for: (1) venv + pip install commands, (2) .env variable explanations, (3) backfill example, (4) cron entry with correct path, (5) output file locations |
| dod-scan.AC7.5 | A new user can follow README from zero to running scheduled scans | End-to-end usability criterion | Have someone unfamiliar with the project follow the README on a clean machine: clone, install, configure .env, run backfill, set up cron, verify output files appear |

## Coverage Summary

- **Total acceptance criteria:** 33
- **Fully automated:** 29
- **Partially automated + human verification:** 2 (AC6.2, AC6.3)
- **Human verification only:** 2 (AC7.4, AC7.5)

## Test File Index

| Test File | Phase | Tests For |
|-----------|-------|-----------|
| `tests/test_scraper_parse.py` | 2 | AC1.1, AC1.2 (index parsing, URL building, date extraction) |
| `tests/test_scraper.py` | 2 | AC1.4, AC1.5 (403 fallback, network error handling) |
| `tests/test_scraper_orchestration.py` | 2 | AC1.1, AC1.2, AC1.3 (end-to-end scrape with DB, dedup) |
| `tests/test_parser_extract.py` | 3 | AC2.1, AC2.4 (HTML contract extraction, raw text preservation) |
| `tests/test_parser_fields.py` | 3 | AC2.1, AC2.2, AC2.3, AC2.5, AC2.6 (regex field extraction, mods, work locations, asterisk, TBD) |
| `tests/test_parser_orchestration.py` | 3 | AC2.1, AC2.4 (parse-to-DB pipeline, idempotency) |
| `tests/test_classifier_prompt.py` | 4 | AC3.1, AC3.6 (prompt building, response parsing, malformed JSON) |
| `tests/test_classifier_providers.py` | 4 | AC3.3, AC3.4, AC3.5 (OpenRouter, Anthropic, API error propagation) |
| `tests/test_classifier_orchestration.py` | 4 | AC3.1, AC3.2, AC3.6 (classify-to-DB, skip classified, retry on malformed) |
| `tests/test_geocoder_resolve.py` | 5 | AC4.1, AC4.2, AC4.5 (work location, HQ fallback, highest-pct selection) |
| `tests/test_geocoder_api.py` | 5 | AC4.1, AC4.3, AC4.4 (Nominatim call, cache hit, API failure handling) |
| `tests/test_geocoder_orchestration.py` | 5 | AC4.1, AC4.2 (geocode-to-DB, fallback source tracking) |
| `tests/test_export_kml_build.py` | 6 | AC5.1, AC5.2, AC5.3 (placemark count, colour gradient, popup HTML) |
| `tests/test_export_kml.py` | 6 | AC5.1, AC5.4, AC5.5 (valid KML file, date filter, branch filter) |
| `tests/test_export_map_data.py` | 7 | AC6.1, AC6.2, AC6.3 (GeoJSON structure, feature properties, branch list) |
| `tests/test_export_map.py` | 7 | AC6.1, AC6.3, AC6.4, AC6.5 (HTML generation, filter markup, graceful degradation) |
| `tests/test_run_all.py` | 8 | AC7.1, AC7.2, AC7.3 (sequential execution, stop-on-failure, log file) |
| `tests/test_logging_config.py` | 8 | AC7.3 (logging setup, file output, handler dedup) |
| `tests/test_cli.py` | 8 | All subcommands (CliRunner --help smoke tests) |

# DOD Contract Scanner Implementation Plan — Phase 2

**Goal:** Fetch daily contract pages from war.gov and store raw HTML in SQLite.

**Architecture:** Scraper module with httpx as primary transport (realistic browser headers), Playwright headless browser as 403 fallback. Index page parsed with BeautifulSoup to extract article links. Deduplication by article ID against the `pages` table.

**Tech Stack:** Python 3.10+, httpx, Playwright (optional), BeautifulSoup, SQLite

**Scope:** 8 phases from original design (phase 2 of 8)

**Codebase verified:** 2026-03-12 — greenfield project, Phase 1 outputs assumed present

---

## Acceptance Criteria Coverage

This phase implements and tests:

### dod-scan.AC1: Scraping daily contract pages
- **dod-scan.AC1.1 Success:** Scraper fetches today's contract page and stores raw HTML in SQLite
- **dod-scan.AC1.2 Success:** `--backfill N` paginates through N pages of historical listings
- **dod-scan.AC1.3 Success:** Already-scraped pages (by article ID) are skipped without re-fetching
- **dod-scan.AC1.4 Failure:** 403 from httpx triggers Playwright fallback transparently
- **dod-scan.AC1.5 Failure:** Network errors logged to file, scrape stage exits non-zero

---

## war.gov Page Structure (Verified via Playwright 2026-03-12)

**Index page:** `https://www.war.gov/News/Contracts/`
- Articles listed in `<figure>` elements containing `<p class="title">` > `<a href="...">`
- Pagination via `?Page=N` query parameter (~10 articles per page)
- Article URL pattern: `/News/Contracts/Contract/Article/{article_id}/{slug}/`
- Article ID extracted from URL path segment

**Article detail page:**
- Contract content lives inside `<main>` element
- Branch headers: `<p><strong>BRANCH_NAME</strong></p>`
- Contract entries: plain `<p>` tags following branch headers

---

<!-- START_SUBCOMPONENT_A (tasks 1-3) -->
<!-- START_TASK_1 -->
### Task 1: Index page parsing (Functional Core)

**Verifies:** dod-scan.AC1.1, dod-scan.AC1.2

**Files:**
- Create: `src/dod_scan/scraper_parse.py`

**Implementation:**

Create `src/dod_scan/scraper_parse.py` — pure functions for extracting article links and metadata from index page HTML.

```python
# pattern: Functional Core
"""Pure functions for parsing war.gov index and article pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ArticleLink:
    article_id: str
    url: str
    title: str


ARTICLE_URL_PATTERN = re.compile(
    r"/News/Contracts/Contract/Article/(\d+)/([^/]+)/"
)
BASE_URL = "https://www.war.gov"


def extract_article_links(html: str) -> list[ArticleLink]:
    soup = BeautifulSoup(html, "lxml")
    links: list[ArticleLink] = []

    for figure in soup.find_all("figure"):
        title_p = figure.find("p", class_="title")
        if not title_p:
            continue
        anchor = title_p.find("a", href=True)
        if not anchor:
            continue

        href = anchor["href"]
        match = ARTICLE_URL_PATTERN.search(href)
        if not match:
            continue

        article_id = match.group(1)
        full_url = href if href.startswith("http") else BASE_URL + href

        links.append(ArticleLink(
            article_id=article_id,
            url=full_url,
            title=anchor.get_text(strip=True),
        ))

    return links


def build_index_url(page: int = 1) -> str:
    base = f"{BASE_URL}/News/Contracts/"
    if page > 1:
        return f"{base}?Page={page}"
    return base


def extract_publish_date_from_title(title: str) -> str | None:
    match = re.search(
        r"(?:contracts?\s+for\s+)(\w+\s+\d{1,2},?\s+\d{4})",
        title,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).replace(",", "").strip()
    return None
```

**Commit:** `feat: add index page parsing functions for war.gov scraper`
<!-- END_TASK_1 -->

<!-- START_TASK_2 -->
### Task 2: HTTP fetching with Playwright fallback (Imperative Shell)

**Verifies:** dod-scan.AC1.4, dod-scan.AC1.5

**Files:**
- Create: `src/dod_scan/scraper_fetch.py`

**Implementation:**

Create `src/dod_scan/scraper_fetch.py` — I/O module for fetching pages with httpx primary and Playwright fallback.

```python
# pattern: Imperative Shell
"""HTTP fetching with Playwright fallback for war.gov pages."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class FetchError(Exception):
    pass


def fetch_page(url: str, timeout: float = 30.0) -> str:
    try:
        html = _fetch_httpx(url, timeout)
        return html
    except _NeedsFallback:
        logger.warning("httpx got 403, falling back to Playwright for %s", url)
        return _fetch_playwright(url)


def _fetch_httpx(url: str, timeout: float) -> str:
    try:
        with httpx.Client(headers=BROWSER_HEADERS, timeout=timeout) as client:
            resp = client.get(url, follow_redirects=True)

        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 403:
            raise _NeedsFallback()
        raise FetchError(f"HTTP {resp.status_code} from {url}")

    except httpx.TimeoutException as exc:
        raise FetchError(f"Timeout fetching {url}") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"Network error fetching {url}: {exc}") from exc


def _fetch_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError(
            "Playwright not installed. Install with: pip install 'dod-scan[browser]'"
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            content = page.content()
            browser.close()
            return content
    except Exception as exc:
        raise FetchError(f"Playwright failed for {url}: {exc}") from exc


class _NeedsFallback(Exception):
    pass
```

**Commit:** `feat: add HTTP fetching with Playwright 403 fallback`
<!-- END_TASK_2 -->

<!-- START_TASK_3 -->
### Task 3: Scraper tests

**Verifies:** dod-scan.AC1.1, dod-scan.AC1.2, dod-scan.AC1.3, dod-scan.AC1.4, dod-scan.AC1.5

**Files:**
- Create: `tests/test_scraper_parse.py`
- Create: `tests/test_scraper.py`
- Create: `tests/fixtures/` (directory)
- Create: `tests/fixtures/index_page.html`
- Create: `tests/fixtures/index_page_2.html`

**Testing:**

Tests must verify each AC listed above:
- dod-scan.AC1.1: `extract_article_links` parses index HTML and returns correct ArticleLink objects with article_id, url, title. `build_index_url` generates correct URLs for page 1 and page N.
- dod-scan.AC1.2: Backfill pagination generates correct index URLs for pages 1 through N. Article links extracted from multiple pages.
- dod-scan.AC1.3: Scrape orchestration skips article IDs already present in `pages` table (test with pre-populated DB rows).
- dod-scan.AC1.4: When httpx returns 403 status, `fetch_page` catches it and calls Playwright fallback. Test by mocking httpx response to return 403, and mocking Playwright to return HTML.
- dod-scan.AC1.5: Network errors (httpx.TimeoutException, httpx.HTTPError) raise FetchError. Test that FetchError is raised with descriptive message.

Create HTML fixture files with realistic war.gov index page structure:

`tests/fixtures/index_page.html` — minimal index page with 3 article links in the verified `<figure>` > `<p class="title">` > `<a>` structure.

`tests/fixtures/index_page_2.html` — second page with different article links for pagination testing.

Test `extract_publish_date_from_title` with various title formats: "Contracts for March 12, 2026", "Contracts For March 10, 2026" (capitalisation variation).

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_scraper_parse.py tests/test_scraper.py -v`
Expected: All tests pass

**Commit:** `test: add scraper parsing and fetch fallback tests`
<!-- END_TASK_3 -->
<!-- END_SUBCOMPONENT_A -->

<!-- START_SUBCOMPONENT_B (tasks 4-5) -->
<!-- START_TASK_4 -->
### Task 4: Scraper orchestration and DB persistence

**Verifies:** dod-scan.AC1.1, dod-scan.AC1.2, dod-scan.AC1.3

**Files:**
- Create: `src/dod_scan/scraper.py`

**Implementation:**

Create `src/dod_scan/scraper.py` — orchestration module that ties together fetching, parsing, and DB storage.

```python
# pattern: Imperative Shell
"""Scraper orchestration — fetches contract pages and stores in SQLite."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from dod_scan.scraper_fetch import FetchError, fetch_page
from dod_scan.scraper_parse import (
    ArticleLink,
    build_index_url,
    extract_article_links,
    extract_publish_date_from_title,
)

logger = logging.getLogger(__name__)


def scrape(conn: sqlite3.Connection, backfill: int = 0) -> int:
    pages_to_fetch = backfill + 1
    total_stored = 0

    for page_num in range(1, pages_to_fetch + 1):
        index_url = build_index_url(page_num)
        logger.info("Fetching index page %d: %s", page_num, index_url)

        try:
            index_html = fetch_page(index_url)
        except FetchError:
            logger.exception("Failed to fetch index page %d", page_num)
            raise

        article_links = extract_article_links(index_html)
        logger.info("Found %d article links on page %d", len(article_links), page_num)

        for link in article_links:
            if _article_exists(conn, link.article_id):
                logger.debug("Skipping already-scraped article %s", link.article_id)
                continue

            try:
                article_html = fetch_page(link.url)
            except FetchError:
                logger.exception("Failed to fetch article %s", link.article_id)
                raise

            publish_date = extract_publish_date_from_title(link.title)
            _store_page(conn, link, article_html, publish_date)
            total_stored += 1
            logger.info("Stored article %s: %s", link.article_id, link.title)

    logger.info("Scrape complete: %d new pages stored", total_stored)
    return total_stored


def _article_exists(conn: sqlite3.Connection, article_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pages WHERE article_id = ?", (article_id,)
    ).fetchone()
    return row is not None


def _store_page(
    conn: sqlite3.Connection,
    link: ArticleLink,
    html: str,
    publish_date: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO pages (article_id, url, publish_date, scraped_at, raw_html)
        VALUES (?, ?, ?, ?, ?)
        """,
        (link.article_id, link.url, publish_date, datetime.now(timezone.utc).isoformat(), html),
    )
    conn.commit()
```

**Commit:** `feat: add scraper orchestration with deduplication`
<!-- END_TASK_4 -->

<!-- START_TASK_5 -->
### Task 5: Scraper orchestration tests

**Verifies:** dod-scan.AC1.1, dod-scan.AC1.2, dod-scan.AC1.3

**Files:**
- Create: `tests/test_scraper_orchestration.py`

**Testing:**

Tests must verify the orchestration layer against the DB:
- dod-scan.AC1.1: `scrape()` with `backfill=0` fetches index page 1, extracts article links, fetches each article, stores HTML in `pages` table. Verify rows exist with correct article_id, url, raw_html.
- dod-scan.AC1.2: `scrape()` with `backfill=2` fetches index pages 1, 2, and 3. Verify `build_index_url` called for all three pages.
- dod-scan.AC1.3: Pre-insert an article_id into `pages` table. Call `scrape()`. Verify that article's URL was NOT fetched again (mock fetch_page and assert it was not called for the duplicate).

Use `tmp_db` fixture from conftest.py for real SQLite. Mock `fetch_page` to return fixture HTML instead of hitting the network.

Follow project testing patterns. Task-implementor generates actual test code at execution time.

**Verification:**
Run: `pytest tests/test_scraper_orchestration.py -v`
Expected: All tests pass

**Commit:** `test: add scraper orchestration tests with dedup verification`
<!-- END_TASK_5 -->
<!-- END_SUBCOMPONENT_B -->

<!-- START_TASK_6 -->
### Task 6: Wire scrape subcommand in CLI

**Files:**
- Modify: `src/dod_scan/cli.py` — replace `scrape` stub with real implementation

**Implementation:**

Update the `scrape` command in `cli.py` to call the scraper orchestration:

```python
@app.command()
def scrape(
    backfill: int = typer.Option(0, "--backfill", "-b", help="Number of historical pages to fetch"),
) -> None:
    """Fetch daily contract pages from war.gov."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.scraper import scrape as do_scrape
        stored = do_scrape(conn, backfill=backfill)
        typer.echo(f"Scrape complete: {stored} new pages stored")
    except Exception as exc:
        typer.echo(f"Scrape failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()
```

**Verification:**
Run: `dod-scan scrape --help`
Expected: Shows help with `--backfill` option

**Commit:** `feat: wire scrape subcommand to scraper orchestration`
<!-- END_TASK_6 -->

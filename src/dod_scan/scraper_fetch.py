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

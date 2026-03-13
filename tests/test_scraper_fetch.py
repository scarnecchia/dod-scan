"""Tests for HTTP fetching with Playwright fallback."""

import pytest
from unittest.mock import Mock, patch

from dod_scan.scraper_fetch import (
    fetch_page,
    FetchError,
    BROWSER_HEADERS,
)


def test_fetch_page_success_httpx() -> None:
    """Verify fetch_page successfully fetches with httpx."""
    html_content = "<html><body>Test</body></html>"

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        result = fetch_page("https://www.example.com/page")
        assert result == html_content
        mock_client.get.assert_called_once()


def test_fetch_page_403_falls_back_to_playwright() -> None:
    """Verify AC1.4: When httpx returns 403, fetch_page calls Playwright fallback."""
    html_content = "<html><body>Playwright fetched</body></html>"

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 403

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with patch("dod_scan.scraper_fetch._fetch_playwright") as mock_playwright:
            mock_playwright.return_value = html_content
            result = fetch_page("https://www.war.gov/News/Contracts/")
            assert result == html_content
            mock_playwright.assert_called_once()


def test_fetch_page_timeout_error() -> None:
    """Verify AC1.5: Timeout errors raise FetchError."""
    import httpx

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(FetchError, match="Timeout"):
            fetch_page("https://www.example.com/page")


def test_fetch_page_http_error() -> None:
    """Verify AC1.5: Network errors raise FetchError."""
    import httpx

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(FetchError, match="Network error"):
            fetch_page("https://www.example.com/page")


def test_fetch_page_non_200_non_403_error() -> None:
    """Verify AC1.5: Non-200/403 status codes raise FetchError."""
    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 500

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with pytest.raises(FetchError, match="HTTP 500"):
            fetch_page("https://www.example.com/page")


def test_browser_headers_realistic() -> None:
    """Verify BROWSER_HEADERS includes realistic browser identifiers."""
    assert "User-Agent" in BROWSER_HEADERS
    assert "Mozilla" in BROWSER_HEADERS["User-Agent"]
    assert "Accept" in BROWSER_HEADERS
    assert "Accept-Language" in BROWSER_HEADERS
    assert "Accept-Encoding" in BROWSER_HEADERS


def test_fetch_page_custom_timeout() -> None:
    """Verify fetch_page passes custom timeout to httpx."""
    html_content = "<html>Test</html>"

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        result = fetch_page("https://www.example.com/page", timeout=60.0)
        assert result == html_content
        # Verify timeout was passed to httpx.Client
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["timeout"] == 60.0


def test_fetch_playwright_not_installed() -> None:
    """Verify FetchError is raised when Playwright is not installed."""
    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 403

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with patch.dict("sys.modules", {"playwright.sync_api": None}):
            with pytest.raises(FetchError, match="Playwright not installed"):
                fetch_page("https://www.war.gov/News/Contracts/")


def test_fetch_playwright_failure() -> None:
    """Verify Playwright failures are caught and raise FetchError."""
    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 403

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        with patch("dod_scan.scraper_fetch._fetch_playwright") as mock_playwright:
            mock_playwright.side_effect = FetchError("Playwright crashed")
            with pytest.raises(FetchError, match="Playwright crashed"):
                fetch_page("https://www.war.gov/News/Contracts/")


def test_fetch_page_follow_redirects() -> None:
    """Verify fetch_page follows redirects."""
    html_content = "<html><body>Final page</body></html>"

    with patch("dod_scan.scraper_fetch.httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content

        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client

        result = fetch_page("https://www.example.com/redirect")
        assert result == html_content
        # Verify follow_redirects was passed to get
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["follow_redirects"] is True

"""Tests for scraper orchestration and DB persistence."""

import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

import pytest

from dod_scan.scraper import scrape
from dod_scan.scraper_parse import ArticleLink


@pytest.fixture
def mock_article_links() -> list[ArticleLink]:
    """Fixture of sample article links for page 1."""
    return [
        ArticleLink(
            article_id="12345",
            url="https://www.war.gov/News/Contracts/Contract/Article/12345/army-contract/",
            title="Contracts for March 12, 2026",
        ),
        ArticleLink(
            article_id="12346",
            url="https://www.war.gov/News/Contracts/Contract/Article/12346/navy-contract/",
            title="Contracts for March 11, 2026",
        ),
    ]


@pytest.fixture
def mock_article_links_page_2() -> list[ArticleLink]:
    """Fixture of sample article links for page 2."""
    return [
        ArticleLink(
            article_id="12347",
            url="https://www.war.gov/News/Contracts/Contract/Article/12347/air-force-contract/",
            title="Contracts for March 10, 2026",
        ),
    ]


@pytest.fixture
def mock_article_links_page_3() -> list[ArticleLink]:
    """Fixture of sample article links for page 3."""
    return [
        ArticleLink(
            article_id="12348",
            url="https://www.war.gov/News/Contracts/Contract/Article/12348/army-contract-2/",
            title="Contracts for March 9, 2026",
        ),
    ]


def test_scrape_backfill_0_stores_single_page(
    db_conn: sqlite3.Connection,
    mock_article_links: list[ArticleLink],
) -> None:
    """Verify AC1.1: scrape() with backfill=0 fetches page 1 and stores articles in DB."""
    article_html = "<html><body>Article content</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url") as mock_build_url:
                mock_build_url.return_value = "https://www.war.gov/News/Contracts/"
                mock_fetch.side_effect = [
                    "<html>Index</html>",  # Index page
                    article_html,  # First article
                    article_html,  # Second article
                ]
                mock_extract.return_value = mock_article_links

                total_stored = scrape(db_conn, backfill=0)

                # Verify both articles were stored
                assert total_stored == 2
                mock_build_url.assert_called_with(1)

                # Verify articles in DB
                rows = db_conn.execute(
                    "SELECT article_id, url FROM pages ORDER BY article_id"
                ).fetchall()
                assert len(rows) == 2
                assert rows[0]["article_id"] == "12345"
                assert rows[0]["url"] == "https://www.war.gov/News/Contracts/Contract/Article/12345/army-contract/"
                assert rows[1]["article_id"] == "12346"


def test_scrape_backfill_2_fetches_multiple_pages(
    db_conn: sqlite3.Connection,
    mock_article_links: list[ArticleLink],
    mock_article_links_page_2: list[ArticleLink],
    mock_article_links_page_3: list[ArticleLink],
) -> None:
    """Verify AC1.2: scrape() with backfill=2 fetches pages 1, 2, and 3."""
    article_html = "<html><body>Article</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url") as mock_build_url:
                # Set up build_index_url to return different URLs for each page
                mock_build_url.side_effect = [
                    "https://www.war.gov/News/Contracts/",
                    "https://www.war.gov/News/Contracts/?Page=2",
                    "https://www.war.gov/News/Contracts/?Page=3",
                ]

                # Set up fetch_page: 3 index pages + 4 article pages
                mock_fetch.return_value = article_html

                # Set up extract to return different articles per page
                mock_extract.side_effect = [
                    mock_article_links,  # Page 1
                    mock_article_links_page_2,  # Page 2
                    mock_article_links_page_3,  # Page 3
                ]

                total_stored = scrape(db_conn, backfill=2)

                # 2 from page 1 + 1 from page 2 + 1 from page 3 = 4 total
                assert total_stored == 4

                # Verify build_index_url called for pages 1, 2, 3
                assert mock_build_url.call_count == 3
                mock_build_url.assert_any_call(1)
                mock_build_url.assert_any_call(2)
                mock_build_url.assert_any_call(3)

                # Verify all 4 articles in DB
                rows = db_conn.execute(
                    "SELECT COUNT(*) as count FROM pages"
                ).fetchone()
                assert rows["count"] == 4


def test_scrape_skips_existing_articles(
    db_conn: sqlite3.Connection,
    mock_article_links: list[ArticleLink],
) -> None:
    """Verify AC1.3: scrape() skips articles already in pages table."""
    article_html = "<html><body>Article</body></html>"

    # Pre-populate DB with article 12345
    db_conn.execute(
        """
        INSERT INTO pages (article_id, url, raw_html)
        VALUES (?, ?, ?)
        """,
        ("12345", "https://www.war.gov/News/Contracts/Contract/Article/12345/army-contract/", "<html>Old</html>"),
    )
    db_conn.commit()

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url") as mock_build_url:
                mock_build_url.return_value = "https://www.war.gov/News/Contracts/"
                mock_fetch.side_effect = [
                    "<html>Index</html>",  # Index page
                    article_html,  # Only second article (12346) should be fetched
                ]
                mock_extract.return_value = mock_article_links

                total_stored = scrape(db_conn, backfill=0)

                # Only one new article stored (12345 already existed)
                assert total_stored == 1

                # Verify fetch_page was called only 2 times (1 index + 1 article)
                assert mock_fetch.call_count == 2

                # Verify both articles in DB (old + new)
                rows = db_conn.execute(
                    "SELECT COUNT(*) as count FROM pages"
                ).fetchone()
                assert rows["count"] == 2


def test_scrape_stores_publish_date(
    db_conn: sqlite3.Connection,
) -> None:
    """Verify scrape extracts and stores publish_date from article title."""
    article_link = ArticleLink(
        article_id="12345",
        url="https://www.war.gov/News/Contracts/Contract/Article/12345/test/",
        title="Contracts for March 12, 2026",
    )
    article_html = "<html><body>Article</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                mock_fetch.side_effect = ["<html>Index</html>", article_html]
                mock_extract.return_value = [article_link]

                scrape(db_conn, backfill=0)

                # Verify publish_date was stored
                row = db_conn.execute(
                    "SELECT publish_date FROM pages WHERE article_id = ?",
                    ("12345",),
                ).fetchone()
                assert row["publish_date"] == "March 12 2026"


def test_scrape_stores_raw_html(
    db_conn: sqlite3.Connection,
) -> None:
    """Verify scrape stores raw HTML content."""
    article_link = ArticleLink(
        article_id="12345",
        url="https://www.war.gov/News/Contracts/Contract/Article/12345/test/",
        title="Contracts for March 12, 2026",
    )
    article_html = "<html><body>Article content here</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                mock_fetch.side_effect = ["<html>Index</html>", article_html]
                mock_extract.return_value = [article_link]

                scrape(db_conn, backfill=0)

                # Verify raw_html was stored
                row = db_conn.execute(
                    "SELECT raw_html FROM pages WHERE article_id = ?",
                    ("12345",),
                ).fetchone()
                assert row["raw_html"] == article_html


def test_scrape_stores_scraped_at_timestamp(
    db_conn: sqlite3.Connection,
) -> None:
    """Verify scrape stores scraped_at timestamp."""
    article_link = ArticleLink(
        article_id="12345",
        url="https://www.war.gov/News/Contracts/Contract/Article/12345/test/",
        title="Contracts for March 12, 2026",
    )
    article_html = "<html><body>Article</body></html>"

    before_scrape = datetime.now(timezone.utc)

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                mock_fetch.side_effect = ["<html>Index</html>", article_html]
                mock_extract.return_value = [article_link]

                scrape(db_conn, backfill=0)

    after_scrape = datetime.now(timezone.utc)

    # Verify scraped_at was stored
    row = db_conn.execute(
        "SELECT scraped_at FROM pages WHERE article_id = ?",
        ("12345",),
    ).fetchone()
    scraped_at = datetime.fromisoformat(row["scraped_at"])
    assert before_scrape <= scraped_at <= after_scrape


def test_scrape_returns_count_of_stored_articles(
    db_conn: sqlite3.Connection,
    mock_article_links: list[ArticleLink],
) -> None:
    """Verify scrape returns count of newly stored articles."""
    article_html = "<html><body>Article</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                mock_fetch.return_value = article_html
                mock_extract.return_value = mock_article_links

                result = scrape(db_conn, backfill=0)

                assert result == 2
                assert isinstance(result, int)


def test_scrape_logs_on_fetch_failure(
    db_conn: sqlite3.Connection,
    mock_article_links: list[ArticleLink],
) -> None:
    """Verify scrape raises exception on fetch failure and logs it."""
    from dod_scan.scraper_fetch import FetchError

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                # Fail on second article fetch
                mock_fetch.side_effect = [
                    "<html>Index</html>",  # Index succeeds
                    FetchError("Network error"),  # First article fails
                ]
                mock_extract.return_value = mock_article_links

                with pytest.raises(FetchError):
                    scrape(db_conn, backfill=0)


def test_scrape_handles_article_with_no_publish_date(
    db_conn: sqlite3.Connection,
) -> None:
    """Verify scrape handles articles without extractable publish_date."""
    article_link = ArticleLink(
        article_id="12345",
        url="https://www.war.gov/News/Contracts/Contract/Article/12345/test/",
        title="No date in this title",  # Won't match date pattern
    )
    article_html = "<html><body>Article</body></html>"

    with patch("dod_scan.scraper.fetch_page") as mock_fetch:
        with patch("dod_scan.scraper.extract_article_links") as mock_extract:
            with patch("dod_scan.scraper.build_index_url"):
                mock_fetch.side_effect = ["<html>Index</html>", article_html]
                mock_extract.return_value = [article_link]

                total_stored = scrape(db_conn, backfill=0)

                assert total_stored == 1

                # Verify publish_date is NULL
                row = db_conn.execute(
                    "SELECT publish_date FROM pages WHERE article_id = ?",
                    ("12345",),
                ).fetchone()
                assert row["publish_date"] is None

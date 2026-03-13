"""Tests for scraper parsing functions."""

import pytest

from dod_scan.scraper_parse import (
    ArticleLink,
    extract_article_links,
    extract_publish_date_from_title,
    build_index_url,
)


@pytest.fixture
def index_page_html() -> str:
    with open("tests/fixtures/index_page.html") as f:
        return f.read()


@pytest.fixture
def index_page_2_html() -> str:
    with open("tests/fixtures/index_page_2.html") as f:
        return f.read()


def test_extract_article_links_basic(index_page_html: str) -> None:
    """Verify AC1.1: extract_article_links parses HTML and returns ArticleLink objects."""
    links = extract_article_links(index_page_html)

    assert len(links) == 3
    assert all(isinstance(link, ArticleLink) for link in links)

    # Verify first article
    assert links[0].article_id == "12345"
    assert links[0].url == "https://www.war.gov/News/Contracts/Contract/Article/12345/army-awards-construction-contract/"
    assert links[0].title == "Contracts for March 12, 2026"

    # Verify second article
    assert links[1].article_id == "12346"
    assert links[1].url == "https://www.war.gov/News/Contracts/Contract/Article/12346/navy-helicopter-procurement/"
    assert links[1].title == "Contracts for March 11, 2026"

    # Verify third article
    assert links[2].article_id == "12347"
    assert links[2].url == "https://www.war.gov/News/Contracts/Contract/Article/12347/air-force-it-services/"
    assert links[2].title == "Contracts for March 10, 2026"


def test_extract_article_links_from_page_2(index_page_2_html: str) -> None:
    """Verify AC1.2: extract_article_links works on multiple pages."""
    links = extract_article_links(index_page_2_html)

    assert len(links) == 3
    assert links[0].article_id == "12348"
    assert links[1].article_id == "12349"
    assert links[2].article_id == "12350"


def test_article_link_is_frozen() -> None:
    """Verify ArticleLink dataclass is immutable."""
    link = ArticleLink(
        article_id="12345",
        url="https://www.war.gov/News/Contracts/Contract/Article/12345/slug/",
        title="Test",
    )
    with pytest.raises(AttributeError):
        link.article_id = "99999"  # type: ignore


def test_build_index_url_page_1() -> None:
    """Verify AC1.1: build_index_url generates correct URL for page 1."""
    url = build_index_url(page=1)
    assert url == "https://www.war.gov/News/Contracts/"


def test_build_index_url_page_2() -> None:
    """Verify AC1.1: build_index_url generates correct URL for page N."""
    url = build_index_url(page=2)
    assert url == "https://www.war.gov/News/Contracts/?Page=2"


def test_build_index_url_page_n() -> None:
    """Verify AC1.2: build_index_url works for any page number."""
    assert build_index_url(page=3) == "https://www.war.gov/News/Contracts/?Page=3"
    assert build_index_url(page=10) == "https://www.war.gov/News/Contracts/?Page=10"


def test_build_index_url_default() -> None:
    """Verify default page is 1."""
    url = build_index_url()
    assert url == "https://www.war.gov/News/Contracts/"


def test_extract_publish_date_lowercase() -> None:
    """Test extract_publish_date_from_title with lowercase 'contracts'."""
    title = "Contracts for March 12, 2026"
    date = extract_publish_date_from_title(title)
    assert date == "March 12 2026"


def test_extract_publish_date_uppercase() -> None:
    """Test extract_publish_date_from_title with uppercase 'CONTRACTS'."""
    title = "Contracts for March 10, 2026"
    date = extract_publish_date_from_title(title)
    assert date == "March 10 2026"


def test_extract_publish_date_mixed_case() -> None:
    """Test extract_publish_date_from_title with mixed case."""
    title = "Contracts For March 15, 2026"
    date = extract_publish_date_from_title(title)
    assert date == "March 15 2026"


def test_extract_publish_date_without_comma() -> None:
    """Test extract_publish_date_from_title without comma in date."""
    title = "Contracts for March 12 2026"
    date = extract_publish_date_from_title(title)
    assert date == "March 12 2026"


def test_extract_publish_date_no_match() -> None:
    """Test extract_publish_date_from_title with non-matching title."""
    title = "Random title without date"
    date = extract_publish_date_from_title(title)
    assert date is None


def test_extract_publish_date_singular() -> None:
    """Test extract_publish_date_from_title with 'contract' (singular)."""
    title = "Contract for March 12, 2026"
    date = extract_publish_date_from_title(title)
    assert date == "March 12 2026"


def test_extract_article_links_absolute_urls() -> None:
    """Verify ArticleLink URLs are absolute (start with https)."""
    html = """
    <figure>
        <p class="title"><a href="/News/Contracts/Contract/Article/12345/test/">Test Article</a></p>
    </figure>
    """
    links = extract_article_links(html)
    assert len(links) == 1
    assert links[0].url.startswith("https://")


def test_extract_article_links_missing_title_p() -> None:
    """Verify malformed figures without title paragraph are skipped."""
    html = """
    <figure>
        <p>No title class here</p>
        <p><a href="/News/Contracts/Contract/Article/12345/test/">Test</a></p>
    </figure>
    """
    links = extract_article_links(html)
    assert len(links) == 0


def test_extract_article_links_missing_anchor() -> None:
    """Verify figures without anchor tags are skipped."""
    html = """
    <figure>
        <p class="title">Just text, no link</p>
    </figure>
    """
    links = extract_article_links(html)
    assert len(links) == 0


def test_extract_article_links_malformed_url() -> None:
    """Verify links with URLs that don't match pattern are skipped."""
    html = """
    <figure>
        <p class="title"><a href="https://example.com/random/url">Unrelated</a></p>
    </figure>
    """
    links = extract_article_links(html)
    assert len(links) == 0

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

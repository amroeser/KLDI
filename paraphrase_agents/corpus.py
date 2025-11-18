"""Utilities for scraping and storing human-written reference corpora."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Set
import json
import re

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


DEFAULT_HUMAN_SOURCES = [
    # NASA feature article (2016)
    "https://www.nasa.gov/feature/nasa-s-new-imaging-spectrometer-maps-salton-sea",
    # European Commission speech (2018)
    "https://ec.europa.eu/commission/presscorner/detail/en/SPEECH_18_4230",
    # WHO news release (2017)
    "https://www.who.int/news-room/detail/13-10-2017-global-tuberculosis-report-2017",
]


@dataclass
class ScrapedDocument:
    """Container for scraped human text and metadata."""

    url: str
    title: str
    published_at: datetime
    retrieved_at: datetime
    text: str

    def to_json(self) -> dict:
        data = asdict(self)
        data["published_at"] = self.published_at.isoformat()
        data["retrieved_at"] = self.retrieved_at.isoformat()
        return data

    @classmethod
    def from_json(cls, payload: dict) -> "ScrapedDocument":
        return cls(
            url=payload["url"],
            title=payload.get("title", ""),
            published_at=date_parser.isoparse(payload["published_at"]),
            retrieved_at=date_parser.isoparse(payload["retrieved_at"]),
            text=payload.get("text", ""),
        )


class HumanCorpusRepository:
    """Persists scraped human documents for reuse across runs."""

    def __init__(self, storage_dir: str = "data/human_corpus"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def list_documents(self) -> List[ScrapedDocument]:
        documents: List[ScrapedDocument] = []
        for path in sorted(self.storage_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                documents.append(ScrapedDocument.from_json(json.load(handle)))
        return documents

    def has_documents(self) -> bool:
        return any(self.storage_dir.glob("*.json"))

    def existing_urls(self) -> Set[str]:
        return {doc.url for doc in self.list_documents()}

    def save_document(self, document: ScrapedDocument) -> Path:
        slug = re.sub(r"[^a-z0-9]+", "-", document.title.lower()).strip("-") or "document"
        filename = f"{document.published_at:%Y%m%d}_{slug[:60]}.json"
        target = self.storage_dir / filename
        with target.open("w", encoding="utf-8") as handle:
            json.dump(document.to_json(), handle, ensure_ascii=False, indent=2)
        return target

    def load_texts(self) -> List[str]:
        return [doc.text for doc in self.list_documents() if doc.text.strip()]


class HumanCorpusScraper:
    """Scrapes pre-2020 human-written texts for reference corpora."""

    def __init__(
        self,
        max_year: int = 2019,
        user_agent: str = "HumanCorpusScraper/0.1",
        timeout: float = 10.0,
    ):
        self.max_year = max_year
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout

    def scrape(self, urls: Iterable[str]) -> List[ScrapedDocument]:
        documents: List[ScrapedDocument] = []
        for url in urls:
            try:
                doc = self.scrape_url(url)
            except Exception:
                continue
            if doc:
                documents.append(doc)
        return documents

    def scrape_url(self, url: str) -> Optional[ScrapedDocument]:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        published_at = self._extract_publication_date(soup)
        if not published_at or published_at.year > self.max_year:
            return None

        title = self._extract_title(soup)
        text = self._extract_text(soup)
        if not text:
            return None

        return ScrapedDocument(
            url=url,
            title=title,
            published_at=published_at,
            retrieved_at=datetime.utcnow(),
            text=text,
        )

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        if soup.title and soup.title.text:
            return soup.title.text.strip()
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()
        return "Untitled Document"

    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        selectors = [
            ("meta", {"property": "article:published_time"}),
            ("meta", {"name": "pubdate"}),
            ("meta", {"name": "publication_date"}),
            ("meta", {"itemprop": "datePublished"}),
            ("time", {"itemprop": "datePublished"}),
            ("time", {"datetime": True}),
        ]
        for tag, attrs in selectors:
            node = soup.find(tag, attrs=attrs)
            if node:
                raw_value = node.get("content") or node.get("datetime") or node.text
                if raw_value:
                    try:
                        dt = date_parser.parse(raw_value, fuzzy=True)
                        return dt
                    except (ValueError, TypeError):
                        continue
        return None

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        container = soup.find("article") or soup.find("main") or soup.body
        paragraphs = container.find_all("p") if container else soup.find_all("p")
        lines: List[str] = []
        for para in paragraphs:
            text = para.get_text(" ", strip=True)
            if len(text) >= 40:
                lines.append(text)
        return "\n\n".join(lines)


def bootstrap_human_corpus(
    repo: Optional[HumanCorpusRepository] = None,
    scraper: Optional[HumanCorpusScraper] = None,
    urls: Optional[Iterable[str]] = None,
    force: bool = False,
) -> List[ScrapedDocument]:
    """Ensure a local corpus of pre-2019 human texts is available."""

    repo = repo or HumanCorpusRepository()
    existing_docs = repo.list_documents()
    if existing_docs and not force:
        return existing_docs

    scraper = scraper or HumanCorpusScraper()
    targets = list(urls or DEFAULT_HUMAN_SOURCES)
    if not targets:
        return existing_docs

    existing_urls = {doc.url for doc in existing_docs}
    new_docs = []
    for doc in scraper.scrape(targets):
        if not doc or doc.url in existing_urls:
            continue
        repo.save_document(doc)
        existing_urls.add(doc.url)
        new_docs.append(doc)

    if not existing_docs and not new_docs:
        return []
    return repo.list_documents()

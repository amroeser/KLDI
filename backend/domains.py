"""Domain configuration for scraping categories."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DomainConfig:
    name: str
    slug: str
    sources: List[str]


DOMAINS: List[DomainConfig] = [
    DomainConfig(
        name="Lyrik",
        slug="poetry",
        sources=[
            "https://www.gutenberg.org/cache/epub/1065/pg1065-images.html",  # Poe – The Raven
            "https://www.gutenberg.org/cache/epub/985/pg985-images.html",   # Shakespeare Sonnets
            "https://www.gutenberg.org/cache/epub/1041/pg1041-images.html", # Coleridge – Ancient Mariner
            "https://www.gutenberg.org/cache/epub/57137/pg57137-images.html", # German poetry collection
        ],
    ),
    DomainConfig(
        name="Rechtswissenschaft",
        slug="law",
        sources=[
            "https://www.archives.gov/founding-docs/constitution-transcript",
            "https://www.law.cornell.edu/wex/bill_of_rights",
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:12012E/TXT",  # Consolidated TEU
            "https://www.bundestag.de/parlament/aufgaben/rechtsgrundlagen/grundgesetz_en",  # German Basic Law (EN)
        ],
    ),
    DomainConfig(
        name="Medizin",
        slug="medical",
        sources=[
            "https://www.who.int/news-room/detail/13-10-2017-global-tuberculosis-report-2017",
            "https://www.cdc.gov/media/releases/2018/p0116-flu-update-activity.html",
            "https://www.who.int/news-room/detail/17-07-2015-world-malaria-report-2015",
            "https://www.cdc.gov/media/releases/2016/p0120-zika-virus.html",
        ],
    ),
    DomainConfig(
        name="Nachrichten",
        slug="news",
        sources=[
            "https://www.nasa.gov/press-release/nasa-s-next-generation-planetary-mission",
            "https://web.archive.org/web/20181201041400/https://www.bbc.com/news",
            "https://www.nytimes.com/2015/09/29/science/nasa-mars-liquid-water.html",
            "https://web.archive.org/web/20170101000000/https://www.theguardian.com/international",
        ],
    ),
]

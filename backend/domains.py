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
            "https://www.gesetze-im-internet.de/gg/BJNR000010949.html",  # German Basic Law (EN)
        ],
    ),
    DomainConfig(
        name="Medizin",
        slug="medical",
        sources=[
            "https://chlaep.org.uy/wp-content/uploads/2020/11/Reporte-Global-TB-2017.pdf",
            "https://stacks.cdc.gov/view/cdc/84012/cdc_84012_DS1.pdf",
            "https://www.afro.who.int/sites/default/files/2017-06/9789241565158_eng.pdf",
            "https://www.ecdc.europa.eu/sites/default/files/documents/AER_for_2017-Zika-virus-disease.pdf",
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

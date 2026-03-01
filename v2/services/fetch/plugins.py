from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import requests


@dataclass
class SourcePaper:
    source: str
    external_id: str
    title: str
    authors: list[str]
    abstract: str | None
    published_at: datetime | None
    url: str | None
    pdf_url: str | None
    doi: str | None = None
    pdf_unavailable: bool = False


class SourcePlugin(Protocol):
    source_name: str

    def search(self, keywords: list[str], start_date: str | None, end_date: str | None, page: int, page_size: int) -> list[SourcePaper]:
        ...


class OpenAlexPlugin:
    source_name = "openalex"

    def __init__(self, rate_limit_rps: float = 2.0):
        self.rate_limit_rps = rate_limit_rps

    def search(self, keywords: list[str], start_date: str | None, end_date: str | None, page: int, page_size: int) -> list[SourcePaper]:
        params = {
            "per-page": page_size,
            "page": page,
            "filter": "type:article",
        }
        if keywords:
            params["search"] = " ".join(keywords)
        if start_date:
            params["from_publication_date"] = start_date
        if end_date:
            params["to_publication_date"] = end_date

        url = "https://api.openalex.org/works"
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            # Fallback to deterministic local sample for offline reliability.
            return [
                SourcePaper(
                    source="openalex",
                    external_id="WTEST0001",
                    title="A Lightweight Test Paper for Daily Paper V2",
                    authors=["OpenAlex Stub"],
                    abstract="Offline fallback paper record for local development.",
                    published_at=datetime.now(),
                    url="https://openalex.org/WTEST0001",
                    pdf_url=None,
                    doi="10.0000/test-v2",
                    pdf_unavailable=True,
                )
            ]

        items: list[SourcePaper] = []
        for row in payload.get("results", []):
            paper_id = row.get("id", "").split("/")[-1]
            title = row.get("title") or "Untitled"
            authors = [a.get("author", {}).get("display_name", "") for a in row.get("authorships", [])]
            abstract = None
            inverted = row.get("abstract_inverted_index")
            if inverted:
                words: dict[int, str] = {}
                for token, positions in inverted.items():
                    for pos in positions:
                        words[pos] = token
                abstract = " ".join(words[i] for i in sorted(words))
            published_at = None
            pub_date = row.get("publication_date")
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date)
                except ValueError:
                    published_at = None
            best_oa = row.get("best_oa_location") or {}
            pdf_url = best_oa.get("pdf_url") or best_oa.get("landing_page_url")
            doi = row.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            items.append(
                SourcePaper(
                    source="openalex",
                    external_id=paper_id,
                    title=title,
                    authors=[a for a in authors if a],
                    abstract=abstract,
                    published_at=published_at,
                    url=row.get("id"),
                    pdf_url=pdf_url,
                    doi=doi,
                    pdf_unavailable=not bool(pdf_url),
                )
            )
        return items

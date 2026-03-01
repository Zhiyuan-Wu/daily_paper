from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)


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

    def search(
        self,
        keywords: list[str],
        start_date: str | None,
        end_date: str | None,
        page: int,
        page_size: int,
        arxiv_categories: list[str] | None = None,
    ) -> list[SourcePaper]:
        ...


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def _in_date_range(value: datetime | None, start_date: str | None, end_date: str | None) -> bool:
    if value is None:
        return True
    d = value.date()
    if start_date:
        try:
            if d < date.fromisoformat(start_date):
                return False
        except Exception:
            pass
    if end_date:
        try:
            if d > date.fromisoformat(end_date):
                return False
        except Exception:
            pass
    return True


def _pick_str(payload: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class OpenAlexPlugin:
    source_name = "openalex"

    def __init__(self, rate_limit_rps: float = 2.0):
        self.rate_limit_rps = rate_limit_rps

    def search(
        self,
        keywords: list[str],
        start_date: str | None,
        end_date: str | None,
        page: int,
        page_size: int,
        arxiv_categories: list[str] | None = None,
    ) -> list[SourcePaper]:
        filters = ["type:article"]
        if start_date:
            filters.append(f"from_publication_date:{start_date}")
        if end_date:
            filters.append(f"to_publication_date:{end_date}")

        params = {
            "per-page": page_size,
            "page": page,
            "filter": ",".join(filters),
        }
        if keywords:
            params["search"] = " ".join(keywords)

        url = "https://api.openalex.org/works"
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.exception("OpenAlex search failed. params=%s", params)
            raise RuntimeError(f"OPENALEX_SEARCH_FAILED: {e}") from e

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
            published_at = _parse_iso_datetime(row.get("publication_date"))
            pdf_url = self._pick_pdf_url(row)
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

    @staticmethod
    def _pick_pdf_url(row: dict) -> str | None:
        candidates: list[dict] = []
        best_oa = row.get("best_oa_location")
        if isinstance(best_oa, dict):
            candidates.append(best_oa)
        locations = row.get("locations")
        if isinstance(locations, list):
            candidates.extend(loc for loc in locations if isinstance(loc, dict))

        for loc in candidates:
            pdf_url = loc.get("pdf_url")
            if isinstance(pdf_url, str) and pdf_url.startswith(("http://", "https://")):
                return pdf_url

        for loc in candidates:
            landing = loc.get("landing_page_url")
            if not isinstance(landing, str) or not landing.startswith(("http://", "https://")):
                continue
            parsed = urlparse(landing)
            if parsed.path.lower().endswith(".pdf"):
                return landing
        return None


class ArxivPlugin:
    source_name = "arxiv"
    default_ai_categories = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "stat.ML"]

    def search(
        self,
        keywords: list[str],
        start_date: str | None,
        end_date: str | None,
        page: int,
        page_size: int,
        arxiv_categories: list[str] | None = None,
    ) -> list[SourcePaper]:
        categories = [x.strip() for x in (arxiv_categories or self.default_ai_categories) if x and x.strip()]
        cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
        query_parts = [f"({cat_query})"] if cat_query else []

        keyword_query = " OR ".join(f'all:"{k.strip()}"' for k in keywords if k and k.strip())
        if keyword_query:
            query_parts.append(f"({keyword_query})")
        search_query = " AND ".join(query_parts) if query_parts else "all:artificial intelligence"

        params = {
            "search_query": search_query,
            "start": max(0, (page - 1) * page_size),
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = "https://export.arxiv.org/api/query"

        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as e:
            logger.exception("arXiv search failed. params=%s", params)
            raise RuntimeError(f"ARXIV_SEARCH_FAILED: {e}") from e

        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        items: list[SourcePaper] = []
        for entry in root.findall("atom:entry", ns):
            raw_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            external_id = raw_id.rsplit("/", 1)[-1] if raw_id else f"arxiv-{len(items)+1}"
            title = (entry.findtext("atom:title", default="Untitled", namespaces=ns) or "Untitled").strip()
            abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip() or None
            published_at = _parse_iso_datetime(entry.findtext("atom:published", default="", namespaces=ns))
            if not _in_date_range(published_at, start_date, end_date):
                continue

            authors = [a.findtext("atom:name", default="", namespaces=ns).strip() for a in entry.findall("atom:author", ns)]
            authors = [a for a in authors if a]
            doi = (entry.findtext("arxiv:doi", default="", namespaces=ns) or "").strip() or None

            pdf_url: str | None = None
            for link in entry.findall("atom:link", ns):
                if (link.attrib.get("title") or "").lower() == "pdf":
                    pdf_url = link.attrib.get("href")
                    break
                if (link.attrib.get("type") or "").lower() == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break
            if not pdf_url and raw_id and "/abs/" in raw_id:
                pdf_url = f"{raw_id.replace('/abs/', '/pdf/')}.pdf"

            items.append(
                SourcePaper(
                    source="arxiv",
                    external_id=external_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    published_at=published_at,
                    url=raw_id or None,
                    pdf_url=pdf_url,
                    doi=doi,
                    pdf_unavailable=not bool(pdf_url),
                )
            )
        return items


class HuggingFacePlugin:
    source_name = "huggingface"

    def search(
        self,
        keywords: list[str],
        start_date: str | None,
        end_date: str | None,
        page: int,
        page_size: int,
        arxiv_categories: list[str] | None = None,
    ) -> list[SourcePaper]:
        rows = self._fetch_rows(limit=max(page_size * 3, 30))
        items: list[SourcePaper] = []
        for row in rows:
            paper = self._normalize_row(row)
            if paper is None:
                continue

            if keywords:
                corpus = f"{paper.title}\n{paper.abstract or ''}".lower()
                if not any(k.lower() in corpus for k in keywords if k.strip()):
                    continue
            if not _in_date_range(paper.published_at, start_date, end_date):
                continue
            items.append(paper)

        start = max(0, (page - 1) * page_size)
        end = start + page_size
        if items[start:end]:
            return items[start:end]

        logger.warning("Hugging Face paper source returned no usable rows.")
        return []

    def _fetch_rows(self, limit: int) -> list[dict]:
        endpoints = [
            ("https://huggingface.co/api/daily_papers", {"limit": limit}),
            ("https://huggingface.co/api/papers", {"limit": limit}),
        ]
        last_error: Exception | None = None
        for url, params in endpoints:
            try:
                response = requests.get(url, params=params, timeout=20)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    return [x for x in payload if isinstance(x, dict)]
                if isinstance(payload, dict):
                    for key in ("papers", "items", "results"):
                        value = payload.get(key)
                        if isinstance(value, list):
                            return [x for x in value if isinstance(x, dict)]
            except Exception as e:
                last_error = e
                logger.exception("Hugging Face paper API failed: url=%s params=%s", url, params)
        if last_error is not None:
            raise RuntimeError(f"HUGGINGFACE_SEARCH_FAILED: {last_error}") from last_error
        return []

    def _normalize_row(self, row: dict) -> SourcePaper | None:
        title = _pick_str(row, ["title", "paper_title", "name"])
        if not title and isinstance(row.get("paper"), dict):
            title = _pick_str(row["paper"], ["title", "name"])
        if not title:
            return None

        abstract = _pick_str(row, ["summary", "abstract", "description"])
        if abstract is None and isinstance(row.get("paper"), dict):
            abstract = _pick_str(row["paper"], ["summary", "abstract", "description"])

        url = _pick_str(row, ["url", "paper_url", "link"])
        if url is None and isinstance(row.get("paper"), dict):
            url = _pick_str(row["paper"], ["url", "paper_url", "link"])
        if not url:
            slug = _pick_str(row, ["id", "slug"])
            if slug:
                url = f"https://huggingface.co/papers/{slug}"
            else:
                url = "https://huggingface.co/papers"

        external_id = _pick_str(row, ["id", "paper_id", "slug"])
        if external_id is None and isinstance(row.get("paper"), dict):
            external_id = _pick_str(row["paper"], ["id", "paper_id", "slug"])
        if not external_id:
            external_id = hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()[:16]

        raw_authors = row.get("authors")
        if raw_authors is None and isinstance(row.get("paper"), dict):
            raw_authors = row["paper"].get("authors")
        authors: list[str] = []
        if isinstance(raw_authors, list):
            for a in raw_authors:
                if isinstance(a, str) and a.strip():
                    authors.append(a.strip())
                elif isinstance(a, dict):
                    name = _pick_str(a, ["name", "display_name", "full_name"])
                    if name:
                        authors.append(name)

        published_raw = _pick_str(
            row,
            ["published_at", "publishedAt", "created_at", "createdAt", "date", "paper_date"],
        )
        if published_raw is None and isinstance(row.get("paper"), dict):
            published_raw = _pick_str(
                row["paper"],
                ["published_at", "publishedAt", "created_at", "createdAt", "date", "paper_date"],
            )
        published_at = _parse_iso_datetime(published_raw)

        pdf_url = _pick_str(row, ["pdf_url", "pdfUrl"])
        if pdf_url is None and isinstance(row.get("paper"), dict):
            pdf_url = _pick_str(row["paper"], ["pdf_url", "pdfUrl"])

        arxiv_id = _pick_str(row, ["arxiv_id", "arxivId"])
        if arxiv_id is None and isinstance(row.get("paper"), dict):
            arxiv_id = _pick_str(row["paper"], ["arxiv_id", "arxivId"])
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        return SourcePaper(
            source="huggingface",
            external_id=external_id,
            title=title,
            authors=authors,
            abstract=abstract,
            published_at=published_at,
            url=url,
            pdf_url=pdf_url,
            doi=None,
            pdf_unavailable=not bool(pdf_url),
        )

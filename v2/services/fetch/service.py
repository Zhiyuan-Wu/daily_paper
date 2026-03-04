from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from v2.config import V2Config
from v2.contracts.fetch import DownloadRequest
from v2.db.repo import Repo
from v2.foundation.artifact_manager import ArtifactManager
from v2.foundation.lru import apply_pdf_lru
from v2.services.fetch.conflict_log import ConflictLogger
from v2.services.fetch.dedup import find_existing_paper
from v2.services.fetch.plugins import ArxivPlugin, HuggingFacePlugin, OpenAlexPlugin, SourcePaper, SourcePlugin

logger = logging.getLogger(__name__)


class FetchService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config
        self.artifacts = ArtifactManager(config.artifact_root)
        self.conflict_logger = ConflictLogger(config.artifact_root / "logs" / "dedup_conflicts.jsonl")
        profile = self.repo.ensure_profile()
        self.plugins: dict[str, SourcePlugin] = {
            "openalex": OpenAlexPlugin(rate_limit_rps=profile.scholar_rate_limit_rps),
            "arxiv": ArxivPlugin(),
            "huggingface": HuggingFacePlugin(),
        }

    def search(
        self,
        sources: list[str],
        keywords: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
        page: int,
        page_size: int,
        arxiv_categories: Optional[list[str]] = None,
    ) -> list[SourcePaper]:
        safe_page = max(1, int(page))
        safe_page_size = max(1, int(page_size))
        fetch_limit = safe_page * safe_page_size

        all_items: list[SourcePaper] = []
        source_errors: dict[str, str] = {}
        for source in sources:
            plugin = self.plugins.get(source)
            if not plugin:
                source_errors[source] = "SOURCE_PLUGIN_NOT_FOUND"
                continue
            try:
                items = plugin.search(
                    keywords,
                    start_date,
                    end_date,
                    page=1,
                    page_size=fetch_limit,
                    arxiv_categories=arxiv_categories,
                )
                all_items.extend(items)
            except Exception as e:
                logger.exception("source search failed: source=%s", source)
                source_errors[source] = str(e)

        if not all_items and source_errors:
            raise RuntimeError(f"FETCH_ALL_SOURCES_FAILED: {json.dumps(source_errors, ensure_ascii=False)}")
        all_items.sort(key=lambda x: x.published_at or datetime.min, reverse=True)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return all_items[start:end]

    def validate_sources(
        self,
        sources: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
        arxiv_categories: Optional[list[str]] = None,
    ) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for source in sources:
            plugin = self.plugins.get(source)
            if not plugin:
                result[source] = {"ok": False, "reason": "SOURCE_PLUGIN_NOT_FOUND", "count": 0}
                continue
            try:
                rows = plugin.search(
                    keywords=[],
                    start_date=start_date,
                    end_date=end_date,
                    page=1,
                    page_size=5,
                    arxiv_categories=arxiv_categories,
                )
                real_rows = [row for row in rows if self._is_real_source_row(row)]
                result[source] = {
                    "ok": len(real_rows) > 0,
                    "reason": "" if real_rows else "NO_REAL_DATA",
                    "count": len(real_rows),
                    "sample_external_id": real_rows[0].external_id if real_rows else None,
                }
            except Exception as e:
                result[source] = {"ok": False, "reason": str(e), "count": 0}
        return result

    @staticmethod
    def _is_real_source_row(row: SourcePaper) -> bool:
        if row.source == "openalex" and row.external_id == "WTEST0001":
            return False
        if row.source == "arxiv" and row.external_id == "arxiv-test-0001":
            return False
        if row.source == "huggingface" and row.external_id == "hf-paper-test-0001":
            return False
        return bool(row.title and row.external_id and row.url)

    def save_search_items(self, items: list[SourcePaper]) -> list[dict]:
        saved: list[dict] = []
        for item in items:
            paper_uid = self.repo.resolve_paper_uid(item.source, item.external_id) or self.artifacts.paper_uid(item.source, item.external_id)
            existing = find_existing_paper(self.repo.session, item)
            if existing is not None and existing.paper_uid != paper_uid:
                self.conflict_logger.log(
                    incoming={"source": item.source, "external_id": item.external_id, "doi": item.doi, "title": item.title},
                    matched={"paper_uid": existing.paper_uid, "source": existing.source, "external_id": existing.external_id},
                )
                paper_uid = existing.paper_uid

            canonical = self.repo.get_paper(paper_uid)
            preserve_identity = bool(canonical and (canonical.source != item.source or canonical.external_id != item.external_id))
            paper = self.repo.upsert_paper(
                {
                    "paper_uid": paper_uid,
                    "source": item.source,
                    "external_id": item.external_id,
                    "doi": item.doi,
                    "title": item.title,
                    "authors_json": json.dumps(item.authors, ensure_ascii=False),
                    "abstract": item.abstract,
                    "published_at": item.published_at,
                    "source_url": item.url,
                    "pdf_url": item.pdf_url,
                    "pdf_unavailable": item.pdf_unavailable,
                },
                preserve_identity=preserve_identity,
            )
            self.repo.add_source_link(
                paper_uid=paper.paper_uid,
                source=item.source,
                external_id=item.external_id,
                doi=item.doi,
                source_url=item.url,
            )
            saved.append(
                {
                    "paper_uid": paper.paper_uid,
                    "source": item.source,
                    "external_id": item.external_id,
                    "doi": item.doi,
                    "title": item.title,
                    "authors": item.authors,
                    "abstract": item.abstract,
                    "published_at": item.published_at,
                    "url": item.url,
                    "pdf_url": item.pdf_url,
                    "pdf_unavailable": item.pdf_unavailable,
                }
            )
        return saved

    def download(self, req: DownloadRequest) -> dict:
        paper_uid = self.repo.resolve_paper_uid(req.source, req.external_id) or self.artifacts.paper_uid(req.source, req.external_id)
        paper = self.repo.get_paper(paper_uid)
        if paper and paper.pdf_unavailable:
            return {"paper_uid": paper_uid, "pdf_path": None, "deduplicated": True, "pdf_unavailable": True}

        artifact = self.repo.get_artifact(paper_uid, "pdf")
        if artifact and Path(artifact.path).exists():
            artifact.last_accessed_at = datetime.now()
            self.repo.session.commit()
            return {"paper_uid": paper_uid, "pdf_path": artifact.path, "deduplicated": True, "pdf_unavailable": False}

        pdf_url = req.pdf_url or (paper.pdf_url if paper else None)
        if not pdf_url and paper and paper.source_url and paper.source == "openalex":
            # No PDF link available from current record.
            return self._mark_pdf_unavailable(paper_uid, deduplicated=False)

        if not pdf_url:
            return self._mark_pdf_unavailable(paper_uid, deduplicated=False)

        try:
            response = requests.get(
                pdf_url,
                timeout=30,
                headers={"User-Agent": "daily-paper-v2/1.0 (+https://github.com)"},
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("PDF download failed for paper_uid=%s url=%s", paper_uid, pdf_url)
            return self._mark_pdf_unavailable(paper_uid, deduplicated=False)

        content = response.content
        if not self._looks_like_pdf(content, response.headers.get("Content-Type", "")):
            return self._mark_pdf_unavailable(paper_uid, deduplicated=False)

        info = self.artifacts.write_bytes(self.artifacts.pdf_path(paper_uid), content)
        self.repo.upsert_artifact(
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "pdf",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": None,
                "parser_version": None,
            }
        )
        if paper:
            paper.pdf_url = pdf_url
            paper.pdf_unavailable = False
            self.repo.session.commit()

        profile = self.repo.ensure_profile()
        apply_pdf_lru(self.repo.session, profile.pdf_lru_max_bytes, profile.pdf_lru_max_count)

        return {"paper_uid": paper_uid, "pdf_path": str(info.path), "deduplicated": False, "pdf_unavailable": False}

    def _mark_pdf_unavailable(self, paper_uid: str, deduplicated: bool) -> dict:
        paper = self.repo.get_paper(paper_uid)
        if paper:
            paper.pdf_unavailable = True
            self.repo.session.commit()
        return {"paper_uid": paper_uid, "pdf_path": None, "deduplicated": deduplicated, "pdf_unavailable": True}

    @staticmethod
    def _looks_like_pdf(content: bytes, content_type: str) -> bool:
        if "pdf" in content_type.lower():
            return True
        head = content[:2048].lstrip()
        return head.startswith(b"%PDF-")

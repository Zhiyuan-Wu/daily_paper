from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import requests

from v2.config import V2Config
from v2.contracts.fetch import DownloadRequest
from v2.db.repo import Repo
from v2.foundation.artifact_manager import ArtifactManager
from v2.foundation.lru import apply_pdf_lru
from v2.services.fetch.conflict_log import ConflictLogger
from v2.services.fetch.dedup import find_existing_paper
from v2.services.fetch.plugins import OpenAlexPlugin, SourcePaper, SourcePlugin


class FetchService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config
        self.artifacts = ArtifactManager(config.artifact_root)
        self.conflict_logger = ConflictLogger(config.artifact_root / "logs" / "dedup_conflicts.jsonl")
        self.plugins: dict[str, SourcePlugin] = {
            "openalex": OpenAlexPlugin(rate_limit_rps=config.scholar_rate_limit_rps),
        }

    def search(self, sources: list[str], keywords: list[str], start_date: str | None, end_date: str | None, page: int, page_size: int) -> list[SourcePaper]:
        all_items: list[SourcePaper] = []
        for source in sources:
            plugin = self.plugins.get(source)
            if not plugin:
                continue
            all_items.extend(plugin.search(keywords, start_date, end_date, page, page_size))
        return all_items

    def save_search_items(self, items: list[SourcePaper]) -> list[dict]:
        saved: list[dict] = []
        for item in items:
            paper_uid = self.artifacts.paper_uid(item.source, item.external_id)
            existing = find_existing_paper(self.repo.session, item)
            if existing is not None and existing.paper_uid != paper_uid:
                self.conflict_logger.log(
                    incoming={"source": item.source, "external_id": item.external_id, "doi": item.doi, "title": item.title},
                    matched={"paper_uid": existing.paper_uid, "source": existing.source, "external_id": existing.external_id},
                )
                paper_uid = existing.paper_uid

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
                    "pdf_unavailable": item.pdf_unavailable,
                }
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
        paper_uid = self.artifacts.paper_uid(req.source, req.external_id)
        paper = self.repo.get_paper(paper_uid)
        if paper and paper.pdf_unavailable:
            return {"paper_uid": paper_uid, "pdf_path": None, "deduplicated": True, "pdf_unavailable": True}

        artifact = self.repo.get_artifact(paper_uid, "pdf")
        if artifact and Path(artifact.path).exists():
            artifact.last_accessed_at = datetime.now()
            self.repo.session.commit()
            return {"paper_uid": paper_uid, "pdf_path": artifact.path, "deduplicated": True, "pdf_unavailable": False}

        pdf_url = req.pdf_url
        if not pdf_url and paper and paper.source_url and paper.source == "openalex":
            # No PDF link available from current record.
            return {"paper_uid": paper_uid, "pdf_path": None, "deduplicated": False, "pdf_unavailable": True}

        if not pdf_url:
            return {"paper_uid": paper_uid, "pdf_path": None, "deduplicated": False, "pdf_unavailable": True}

        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        info = self.artifacts.write_bytes(self.artifacts.pdf_path(paper_uid), response.content)
        self.repo.upsert_artifact(
            artifact_id=uuid.uuid4().hex,
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "pdf",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": None,
                "parser_version": None,
            },
        )

        profile = self.repo.ensure_profile()
        apply_pdf_lru(self.repo.session, profile.pdf_lru_max_bytes, profile.pdf_lru_max_count)

        return {"paper_uid": paper_uid, "pdf_path": str(info.path), "deduplicated": False, "pdf_unavailable": False}

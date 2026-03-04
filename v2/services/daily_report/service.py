from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from v2.config import V2Config
from v2.contracts.fetch import DownloadRequest
from v2.db.models import DailyReport, DailyReportItem
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService
from v2.services.fetch.service import FetchService
from v2.services.parse.service import ParseService
from v2.services.recommend.service import RecommendService

logger = logging.getLogger(__name__)


class DailyReportService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config
        self.fetch_service = FetchService(repo, config)
        self.parse_service = ParseService(repo, config)
        self.analyze_service = AnalyzeService(repo)
        self.recommend_service = RecommendService(repo)

    def generate(
        self,
        report_date: datetime,
        sources: list[str],
        keywords: list[str],
        top_k: int,
        window_days: int = 1,
        arxiv_categories: Optional[list[str]] = None,
    ) -> dict:
        lookback_days = max(1, int(window_days))
        start_date = report_date.date() - timedelta(days=lookback_days - 1)

        # Step 1: fetch
        papers = self.fetch_service.search(
            sources=sources,
            keywords=keywords,
            start_date=start_date.isoformat(),
            end_date=report_date.date().isoformat(),
            page=1,
            page_size=top_k * 3,
            arxiv_categories=arxiv_categories,
        )
        saved = self.fetch_service.save_search_items(papers)
        if not saved:
            raise RuntimeError("REPORT_FETCH_EMPTY")

        candidate_uids = [p["paper_uid"] for p in saved]

        # Step 2: recommend from metadata + feedback first, then enrich top papers lazily.
        rec = self.recommend_service.recommend(candidate_uids, top_k)
        if not rec["items"]:
            raise RuntimeError("REPORT_RECOMMEND_EMPTY")

        enrich_status: dict[str, str] = {}
        row_by_uid = {row["paper_uid"]: row for row in saved}
        for item in rec["items"]:
            uid = item["paper_uid"]
            row = row_by_uid.get(uid)
            if not row:
                enrich_status[uid] = "metadata_only"
                continue
            enrich_status[uid] = self._ensure_analysis_for_row(row)

        # Step 3: summarize (single provider from env; here deterministic format)
        summary_lines = [f"# Daily Report ({report_date.date().isoformat()})", "", "## Top Recommendations"]
        for item in rec["items"]:
            paper = self.repo.get_paper(item["paper_uid"])
            status = enrich_status.get(item["paper_uid"], "metadata_only")
            summary_lines.append(f"- {paper.title if paper else item['paper_uid']} (score={item['score']}, enrich={status})")
        summary_md = "\n".join(summary_lines)
        profile = self.repo.ensure_profile()

        report_id = uuid.uuid4().hex
        self.repo.session.add(
            DailyReport(
                id=report_id,
                report_date=report_date,
                timezone=profile.timezone,
                summary_md=summary_md,
                meta_json=json.dumps(
                    {
                        "sources": sources,
                        "keywords": keywords,
                        "window_days": lookback_days,
                        "arxiv_categories": arxiv_categories or [],
                    }
                ),
            )
        )
        for row in rec["items"]:
            self.repo.session.add(
                DailyReportItem(
                    id=uuid.uuid4().hex,
                    report_id=report_id,
                    paper_uid=row["paper_uid"],
                    recommend_score=row["score"],
                    rank=row["rank"],
                    analysis_snapshot_json=json.dumps(row["strategy_breakdown"]),
                )
            )
        self.repo.session.commit()
        return {
            "report_id": report_id,
            "report_date": report_date.date().isoformat(),
            "summary_md": summary_md,
            "paper_uids": [x["paper_uid"] for x in rec["items"]],
        }

    def _ensure_analysis_for_row(self, row: dict) -> str:
        paper_uid = row["paper_uid"]
        latest = self.repo.latest_analysis(paper_uid)
        if latest:
            return "analysis_cached"
        try:
            download_out = self.fetch_service.download(
                req=DownloadRequest(
                    source=row["source"],
                    external_id=row["external_id"],
                    pdf_url=row.get("pdf_url"),
                )
            )
            if download_out.get("pdf_unavailable"):
                return "pdf_unavailable"

            parse_out = self.parse_service.parse(download_out["paper_uid"], "simple", False)
            with open(parse_out["text_path"], "r", encoding="utf-8") as f:
                text = f.read()
            paper = self.repo.get_paper(paper_uid)
            if not paper:
                return "paper_missing"
            self.analyze_service.analyze(paper_uid, paper.title, text, paper.abstract)
            return "analysis_generated"
        except Exception:
            logger.exception("Lazy enrichment failed in daily report for paper_uid=%s", paper_uid)
            return "enrich_failed"

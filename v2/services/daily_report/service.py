from __future__ import annotations

import json
import uuid
from datetime import datetime

from v2.config import V2Config
from v2.contracts.fetch import DownloadRequest
from v2.db.models import DailyReport, DailyReportItem
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService
from v2.services.fetch.service import FetchService
from v2.services.parse.service import ParseService
from v2.services.recommend.service import RecommendService


class DailyReportService:
    def __init__(self, repo: Repo, config: V2Config):
        self.repo = repo
        self.config = config
        self.fetch_service = FetchService(repo, config)
        self.parse_service = ParseService(repo, config)
        self.analyze_service = AnalyzeService(repo)
        self.recommend_service = RecommendService(repo)

    def generate(self, report_date: datetime, sources: list[str], keywords: list[str], top_k: int) -> dict:
        # Step 1: fetch
        papers = self.fetch_service.search(sources=sources, keywords=keywords, start_date=None, end_date=None, page=1, page_size=top_k * 3)
        saved = self.fetch_service.save_search_items(papers)
        if not saved:
            raise RuntimeError("REPORT_FETCH_EMPTY")

        # Step 2: parse (must fail if parse fails)
        parsed_uids: list[str] = []
        for p in saved[: top_k * 2]:
            if p.get("pdf_unavailable"):
                continue
            download_out = self.fetch_service.download(
                req=DownloadRequest(
                    source=p["source"],
                    external_id=p["external_id"],
                    pdf_url=p.get("pdf_url"),
                )
            )
            if download_out.get("pdf_unavailable"):
                continue
            parse_out = self.parse_service.parse(download_out["paper_uid"], "simple", False)
            parsed_uids.append(parse_out["paper_uid"])

        if not parsed_uids:
            raise RuntimeError("REPORT_PARSE_EMPTY")

        # Step 3: analyze
        for uid in parsed_uids:
            text_artifact = self.repo.get_artifact(uid, "text", parser_method="simple")
            paper = self.repo.get_paper(uid)
            if not text_artifact or not paper:
                raise RuntimeError("REPORT_ANALYZE_INPUT_MISSING")
            text = open(text_artifact.path, "r", encoding="utf-8").read()
            self.analyze_service.analyze(uid, paper.title, text, paper.abstract)

        # Step 4: recommend
        rec = self.recommend_service.recommend(parsed_uids, top_k)
        if not rec["items"]:
            raise RuntimeError("REPORT_RECOMMEND_EMPTY")

        # Step 5: summarize (single provider from env; here deterministic format)
        summary_lines = [f"# Daily Report ({report_date.date().isoformat()})", "", "## Top Recommendations"]
        for item in rec["items"]:
            paper = self.repo.get_paper(item["paper_uid"])
            summary_lines.append(f"- {paper.title if paper else item['paper_uid']} (score={item['score']})")
        summary_md = "\n".join(summary_lines)

        report_id = uuid.uuid4().hex
        self.repo.session.add(
            DailyReport(
                id=report_id,
                report_date=report_date,
                timezone=self.config.timezone,
                summary_md=summary_md,
                meta_json=json.dumps({"sources": sources, "keywords": keywords}),
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

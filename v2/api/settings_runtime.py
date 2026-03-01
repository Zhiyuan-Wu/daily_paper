from __future__ import annotations

import json

from v2.db.models import AppProfile
from v2.db.repo import Repo


class SettingsRuntime:
    def __init__(self, repo: Repo):
        self.repo = repo

    def get(self) -> dict:
        p = self.repo.ensure_profile()
        return {
            "timezone": p.timezone,
            "interest_keywords": json.loads(p.interest_keywords_json),
            "excluded_keywords": json.loads(p.excluded_keywords_json),
            "default_sources": json.loads(p.default_sources_json),
            "daily_report_sources": json.loads(p.daily_report_sources_json),
            "daily_report_keywords": json.loads(p.daily_report_keywords_json),
            "daily_report_arxiv_categories": json.loads(p.daily_report_arxiv_categories_json),
            "daily_report_top_k": p.daily_report_top_k,
            "daily_report_window_days": p.daily_report_window_days,
            "recommend_strategy_weights": json.loads(p.recommend_strategy_weights_json),
            "scholar_provider": p.scholar_provider,
            "scholar_rate_limit_rps": p.scholar_rate_limit_rps,
            "batch_download_concurrency": p.batch_download_concurrency,
            "batch_parse_concurrency": p.batch_parse_concurrency,
            "batch_analyze_concurrency": p.batch_analyze_concurrency,
            "pdf_lru_max_bytes": p.pdf_lru_max_bytes,
            "pdf_lru_max_count": p.pdf_lru_max_count,
            "ocr_timeout_seconds": p.ocr_timeout_seconds,
            "research_timeout_minutes": p.research_timeout_minutes,
        }

    def update(self, payload: dict) -> dict:
        p = self.repo.ensure_profile()
        if "timezone" in payload:
            p.timezone = payload["timezone"]
        if "interest_keywords" in payload:
            p.interest_keywords_json = json.dumps(payload["interest_keywords"], ensure_ascii=False)
        if "excluded_keywords" in payload:
            p.excluded_keywords_json = json.dumps(payload["excluded_keywords"], ensure_ascii=False)
        if "default_sources" in payload:
            p.default_sources_json = json.dumps(payload["default_sources"], ensure_ascii=False)
        if "daily_report_sources" in payload:
            p.daily_report_sources_json = json.dumps(payload["daily_report_sources"], ensure_ascii=False)
        if "daily_report_keywords" in payload:
            p.daily_report_keywords_json = json.dumps(payload["daily_report_keywords"], ensure_ascii=False)
        if "daily_report_arxiv_categories" in payload:
            p.daily_report_arxiv_categories_json = json.dumps(payload["daily_report_arxiv_categories"], ensure_ascii=False)
        if "daily_report_top_k" in payload:
            p.daily_report_top_k = int(payload["daily_report_top_k"])
        if "daily_report_window_days" in payload:
            p.daily_report_window_days = int(payload["daily_report_window_days"])
        if "recommend_strategy_weights" in payload:
            p.recommend_strategy_weights_json = json.dumps(payload["recommend_strategy_weights"], ensure_ascii=False)
        if "scholar_rate_limit_rps" in payload:
            p.scholar_rate_limit_rps = float(payload["scholar_rate_limit_rps"])
        if "batch_download_concurrency" in payload:
            p.batch_download_concurrency = int(payload["batch_download_concurrency"])
        if "batch_parse_concurrency" in payload:
            p.batch_parse_concurrency = int(payload["batch_parse_concurrency"])
        if "batch_analyze_concurrency" in payload:
            p.batch_analyze_concurrency = int(payload["batch_analyze_concurrency"])
        if "pdf_lru_max_bytes" in payload:
            p.pdf_lru_max_bytes = int(payload["pdf_lru_max_bytes"])
        if "pdf_lru_max_count" in payload:
            p.pdf_lru_max_count = int(payload["pdf_lru_max_count"])
        if "ocr_timeout_seconds" in payload:
            p.ocr_timeout_seconds = int(payload["ocr_timeout_seconds"])
        if "research_timeout_minutes" in payload:
            p.research_timeout_minutes = int(payload["research_timeout_minutes"])
        self.repo.session.commit()
        return self.get()

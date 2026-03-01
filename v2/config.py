from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class V2Config:
    database_url: str = "sqlite:///data/v2_daily_paper.db"
    timezone: str = "Asia/Shanghai"

    api_host: str = "127.0.0.1"
    api_port: int = 8001

    fetch_service_url: str = "http://127.0.0.1:8101"
    parse_service_url: str = "http://127.0.0.1:8102"
    analyze_service_url: str = "http://127.0.0.1:8103"
    recommend_service_url: str = "http://127.0.0.1:8104"
    research_service_url: str = "http://127.0.0.1:8105"
    report_service_url: str = "http://127.0.0.1:8106"

    artifact_root: Path = Path("data/v2_artifacts")
    research_root: Path = Path("data/research_runs")

    scholar_provider: str = "openalex"
    scholar_rate_limit_rps: float = 2.0

    batch_download_concurrency: int = 4
    batch_parse_concurrency: int = 2
    batch_analyze_concurrency: int = 2

    pdf_lru_max_bytes: int = 10 * 1024 * 1024 * 1024
    pdf_lru_max_count: int = 5000

    ocr_timeout_seconds: int = 120
    research_timeout_minutes: int = 45

    evidence_snippet_max_chars: int = 300

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_api_base: str = "https://api.openai.com/v1"

    @classmethod
    def from_env(cls) -> "V2Config":
        cfg = cls(
            database_url=os.getenv("V2_DATABASE_URL", "sqlite:///data/v2_daily_paper.db"),
            timezone=os.getenv("V2_TIMEZONE", "Asia/Shanghai"),
            api_host=os.getenv("V2_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("V2_API_PORT", "8001")),
            fetch_service_url=os.getenv("FETCH_SERVICE_URL", "http://127.0.0.1:8101"),
            parse_service_url=os.getenv("PARSE_SERVICE_URL", "http://127.0.0.1:8102"),
            analyze_service_url=os.getenv("ANALYZE_SERVICE_URL", "http://127.0.0.1:8103"),
            recommend_service_url=os.getenv("RECOMMEND_SERVICE_URL", "http://127.0.0.1:8104"),
            research_service_url=os.getenv("RESEARCH_SERVICE_URL", "http://127.0.0.1:8105"),
            report_service_url=os.getenv("REPORT_SERVICE_URL", "http://127.0.0.1:8106"),
            artifact_root=Path(os.getenv("V2_ARTIFACT_ROOT", "data/v2_artifacts")),
            research_root=Path(os.getenv("V2_RESEARCH_ROOT", "data/research_runs")),
            scholar_provider=os.getenv("V2_SCHOLAR_PROVIDER", "openalex"),
            scholar_rate_limit_rps=float(os.getenv("V2_SCHOLAR_RATE_LIMIT_RPS", "2")),
            batch_download_concurrency=int(os.getenv("V2_BATCH_DOWNLOAD_CONCURRENCY", "4")),
            batch_parse_concurrency=int(os.getenv("V2_BATCH_PARSE_CONCURRENCY", "2")),
            batch_analyze_concurrency=int(os.getenv("V2_BATCH_ANALYZE_CONCURRENCY", "2")),
            pdf_lru_max_bytes=int(os.getenv("V2_PDF_LRU_MAX_BYTES", str(10 * 1024 * 1024 * 1024))),
            pdf_lru_max_count=int(os.getenv("V2_PDF_LRU_MAX_COUNT", "5000")),
            ocr_timeout_seconds=int(os.getenv("V2_OCR_TIMEOUT_SECONDS", "120")),
            research_timeout_minutes=int(os.getenv("V2_RESEARCH_TIMEOUT_MINUTES", "45")),
            evidence_snippet_max_chars=int(os.getenv("V2_EVIDENCE_SNIPPET_MAX_CHARS", "300")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        )
        cfg.artifact_root.mkdir(parents=True, exist_ok=True)
        cfg.research_root.mkdir(parents=True, exist_ok=True)
        return cfg

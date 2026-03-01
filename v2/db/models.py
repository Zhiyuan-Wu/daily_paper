from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class AppProfile(Base):
    __tablename__ = "app_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    interest_keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    excluded_keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    default_sources_json: Mapped[str] = mapped_column(Text, default='["arxiv","huggingface"]')
    daily_report_sources_json: Mapped[str] = mapped_column(Text, default='["arxiv","huggingface"]')
    daily_report_keywords_json: Mapped[str] = mapped_column(Text, default='[]')
    daily_report_arxiv_categories_json: Mapped[str] = mapped_column(Text, default='["cs.AI","cs.LG","cs.CL","cs.CV","cs.RO","stat.ML"]')
    daily_report_top_k: Mapped[int] = mapped_column(Integer, default=5)
    daily_report_window_days: Mapped[int] = mapped_column(Integer, default=7)
    recommend_strategy_weights_json: Mapped[str] = mapped_column(Text, default='{"keyword_semantic":0.2,"interested_semantic":0.2,"repetition_penalty":0.2,"llm_theme":0.2,"recommended_inverse":0.2}')
    scholar_provider: Mapped[str] = mapped_column(String(32), default="openalex")
    scholar_rate_limit_rps: Mapped[float] = mapped_column(Float, default=2.0)
    batch_download_concurrency: Mapped[int] = mapped_column(Integer, default=4)
    batch_parse_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    batch_analyze_concurrency: Mapped[int] = mapped_column(Integer, default=2)
    pdf_lru_max_bytes: Mapped[int] = mapped_column(Integer, default=10 * 1024 * 1024 * 1024)
    pdf_lru_max_count: Mapped[int] = mapped_column(Integer, default=5000)
    ocr_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    research_timeout_minutes: Mapped[int] = mapped_column(Integer, default=45)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())


class Paper(Base):
    __tablename__ = "papers"

    paper_uid: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(String(2000))
    authors_json: Mapped[str] = mapped_column(Text, default="[]")
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    pdf_unavailable: Mapped[bool] = mapped_column(Boolean, default=False)
    recommended_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    __table_args__ = (UniqueConstraint("source", "external_id", name="uniq_source_external"),)


class PaperSourceLink(Base):
    __tablename__ = "paper_source_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())

    __table_args__ = (UniqueConstraint("source", "external_id", name="uniq_source_link"),)


class PaperArtifact(Base):
    __tablename__ = "paper_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str] = mapped_column(String(2000))
    file_hash: Mapped[str] = mapped_column(String(128), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    parser_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evicted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class PaperAnalysis(Base):
    __tablename__ = "paper_analysis"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    pipeline_version: Mapped[str] = mapped_column(String(64), default="v1")
    analysis_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class PaperFeedback(Base):
    __tablename__ = "paper_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), index=True)


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_context_json: Mapped[str] = mapped_column(Text)
    strategy_weights_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("recommendation_runs.id"), index=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    strategy_breakdown_json: Mapped[str] = mapped_column(Text)
    reasons_json: Mapped[str] = mapped_column(Text)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    summary_md: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class DailyReportItem(Base):
    __tablename__ = "daily_report_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("daily_reports.id"), index=True)
    paper_uid: Mapped[str] = mapped_column(ForeignKey("papers.paper_uid"), index=True)
    recommend_score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    analysis_snapshot_json: Mapped[str] = mapped_column(Text)


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(Text)
    constraints_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    workdir_path: Mapped[str] = mapped_column(String(2000))
    task_file_path: Mapped[str] = mapped_column(String(2000))
    report_file_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    report_md: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())


class ServiceCallLog(Base):
    __tablename__ = "service_call_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    service_name: Mapped[str] = mapped_column(String(64), index=True)
    endpoint: Mapped[str] = mapped_column(String(256))
    request_summary_json: Mapped[str] = mapped_column(Text)
    response_summary_json: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


def init_db(database_url: str) -> Session:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return factory()

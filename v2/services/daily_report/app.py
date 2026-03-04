from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.report import DailyReportResponse, DailyReportTaskRequest, DailyReportTaskResponse
from v2.db.models import DailyReport, init_session_factory
from v2.db.repo import Repo
from v2.services.daily_report.service import DailyReportService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Daily Report Service")


def get_repo() -> Generator[Repo, None, None]:
    session = SessionLocal()
    try:
        repo = Repo(session)
        repo.ensure_profile()
        yield repo
    finally:
        session.close()


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "daily_report"}


@app.post("/v1/daily-report/tasks", response_model=DailyReportTaskResponse)
def create_report(req: DailyReportTaskRequest, repo: Repo = Depends(get_repo)) -> DailyReportTaskResponse:
    service = DailyReportService(repo, config)
    try:
        out = service.generate(
            report_date=datetime.combine(req.report_date, datetime.min.time()),
            sources=req.sources,
            keywords=req.keywords,
            top_k=req.top_k,
            window_days=req.window_days,
            arxiv_categories=req.arxiv_categories,
        )
        return DailyReportTaskResponse(task_id=out["report_id"], status="completed")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DAILY_REPORT_FAILED", "message": str(e)})


@app.get("/v1/daily-report/{report_id}", response_model=DailyReportResponse)
def get_report(report_id: str, repo: Repo = Depends(get_repo)) -> DailyReportResponse:
    report = repo.session.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "not found"})
    # items loaded separately to avoid adding complex ORM relationships.
    from v2.db.models import DailyReportItem

    items = repo.session.query(DailyReportItem).filter(DailyReportItem.report_id == report_id).order_by(DailyReportItem.rank.asc()).all()
    return DailyReportResponse(
        report_id=report.id,
        report_date=report.report_date.date().isoformat(),
        summary_md=report.summary_md,
        paper_uids=[x.paper_uid for x in items],
    )

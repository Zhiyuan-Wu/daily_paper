from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.report import DailyReportResponse, DailyReportTaskRequest, DailyReportTaskResponse
from v2.db.models import DailyReport, init_db
from v2.db.repo import Repo
from v2.services.daily_report.service import DailyReportService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = DailyReportService(repo, config)

app = FastAPI(title="V2 Daily Report Service")


@app.post("/v1/daily-report/tasks", response_model=DailyReportTaskResponse)
def create_report(req: DailyReportTaskRequest) -> DailyReportTaskResponse:
    try:
        out = service.generate(
            report_date=datetime.combine(req.report_date, datetime.min.time()),
            sources=req.sources,
            keywords=req.keywords,
            top_k=req.top_k,
        )
        return DailyReportTaskResponse(task_id=out["report_id"], status="completed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/daily-report/{report_id}", response_model=DailyReportResponse)
def get_report(report_id: str) -> DailyReportResponse:
    report = repo.session.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")

    rows = (
        repo.session.query(DailyReport)
        .filter(DailyReport.id == report_id)
        .all()
    )
    # items loaded separately to avoid adding complex ORM relationships.
    from v2.db.models import DailyReportItem

    items = repo.session.query(DailyReportItem).filter(DailyReportItem.report_id == report_id).order_by(DailyReportItem.rank.asc()).all()
    return DailyReportResponse(
        report_id=report.id,
        report_date=report.report_date.date().isoformat(),
        summary_md=report.summary_md,
        paper_uids=[x.paper_uid for x in items],
    )

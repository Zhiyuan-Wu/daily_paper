from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from v2.config import V2Config
from v2.contracts.analyze import AnalyzeRequest
from v2.contracts.fetch import DownloadRequest, SearchRequest
from v2.contracts.parse import ParseRequest
from v2.contracts.recommend import RecommendRequest
from v2.contracts.report import DailyReportTaskRequest
from v2.contracts.research import ResearchTaskRequest
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService
from v2.services.daily_report.service import DailyReportService
from v2.services.fetch.service import FetchService
from v2.services.parse.service import ParseService
from v2.services.recommend.service import RecommendService
from v2.services.research.service import ResearchService
from v2.api.settings_runtime import SettingsRuntime


class FeedbackRequest(BaseModel):
    paper_uid: str
    action: str
    note: str | None = None


config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
repo.ensure_profile()

fetch_service = FetchService(repo, config)
parse_service = ParseService(repo, config)
analyze_service = AnalyzeService(repo)
recommend_service = RecommendService(repo)
research_service = ResearchService(repo, config)
report_service = DailyReportService(repo, config)
settings_runtime = SettingsRuntime(repo)

app = FastAPI(title="Daily Paper V2 API")


def _trace_id(incoming: str | None) -> str:
    return incoming or uuid.uuid4().hex


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "version": "v2"}


@app.post("/api/v1/papers/search")
def papers_search(req: SearchRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("papers_search", req.model_dump(mode="json"), trace)
    items = fetch_service.search(
        sources=req.sources,
        keywords=req.keywords,
        start_date=req.start_date.isoformat() if req.start_date else None,
        end_date=req.end_date.isoformat() if req.end_date else None,
        page=req.page,
        page_size=req.page_size,
    )
    saved = fetch_service.save_search_items(items)
    repo.update_job(job.id, status="completed", progress=100, result_ref=f"papers:{len(saved)}")
    return {"items": saved, "job_id": job.id, "trace_id": trace}


@app.post("/api/v1/papers/import")
def papers_import(req: DownloadRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_import", req.model_dump(), trace)
    try:
        out = fetch_service.download(req)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["paper_uid"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        repo.update_job(job.id, status="failed", error_code="FETCH_DOWNLOAD_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "FETCH_DOWNLOAD_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/papers/{paper_uid}/parse")
def papers_parse(paper_uid: str, req: ParseRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_parse", req.model_dump(), trace)
    try:
        out = parse_service.parse(paper_uid=paper_uid, method=req.method, force_reparse=req.force_reparse)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["text_path"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except FileNotFoundError as e:
        repo.update_job(job.id, status="failed", error_code="PARSE_INPUT_NOT_FOUND", error_message=str(e))
        raise HTTPException(status_code=404, detail={"code": "PARSE_INPUT_NOT_FOUND", "message": str(e), "trace_id": trace})
    except Exception as e:
        repo.update_job(job.id, status="failed", error_code="PARSE_EXEC_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "PARSE_EXEC_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/papers/{paper_uid}/analyze")
def papers_analyze(paper_uid: str, req: AnalyzeRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_analyze", req.model_dump(), trace)
    try:
        out = analyze_service.analyze(paper_uid, req.title, req.full_text, req.abstract)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["analysis_id"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        repo.update_job(job.id, status="failed", error_code="ANALYZE_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "ANALYZE_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/recommendations/generate")
def recommendations_generate(req: RecommendRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("recommend_generate", req.model_dump(), trace)
    try:
        out = recommend_service.recommend(req.paper_uids, req.top_k)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["run_id"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        repo.update_job(job.id, status="failed", error_code="RECOMMEND_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "RECOMMEND_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/interactions")
def interactions(req: FeedbackRequest) -> dict:
    repo.save_feedback(req.paper_uid, req.action, req.note)
    return {"status": "ok"}


@app.post("/api/v1/research/tasks")
def research_task(req: ResearchTaskRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("research_task", req.model_dump(), trace)
    out = research_service.run_task(req.topic, req.constraints)
    if out["status"] == "completed":
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["task_id"])
    else:
        repo.update_job(job.id, status="failed", error_code="RESEARCH_FAILED", error_message=out.get("error", ""))
    return {"job_id": job.id, "trace_id": trace, "result": out}


@app.get("/api/v1/research/tasks/{task_id}")
def research_task_status(task_id: str) -> dict:
    return research_service.get_task(task_id)


@app.get("/api/v1/research/tasks/{task_id}/result")
def research_task_result(task_id: str) -> dict:
    try:
        return research_service.get_result(task_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "RESEARCH_REPORT_NOT_FOUND", "message": str(e)})


@app.post("/api/v1/reports/daily/generate")
def reports_daily_generate(req: DailyReportTaskRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("daily_report", req.model_dump(mode="json"), trace)
    try:
        out = report_service.generate(
            report_date=datetime.combine(req.report_date, datetime.min.time()),
            sources=req.sources,
            keywords=req.keywords,
            top_k=req.top_k,
        )
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["report_id"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        repo.update_job(job.id, status="failed", error_code="DAILY_REPORT_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "DAILY_REPORT_FAILED", "message": str(e), "trace_id": trace})


@app.get("/api/v1/reports/daily/{report_id}")
def reports_daily_get(report_id: str) -> dict:
    from v2.db.models import DailyReport, DailyReportItem

    report = repo.session.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "not found"})
    items = repo.session.query(DailyReportItem).filter(DailyReportItem.report_id == report_id).order_by(DailyReportItem.rank.asc()).all()
    return {
        "report_id": report.id,
        "report_date": report.report_date.date().isoformat(),
        "summary_md": report.summary_md,
        "paper_uids": [i.paper_uid for i in items],
    }


@app.get("/api/v1/settings")
def get_settings() -> dict:
    return settings_runtime.get()


@app.put("/api/v1/settings")
def put_settings(payload: dict) -> dict:
    return settings_runtime.update(payload)


@app.get("/api/v1/tasks/{job_id}")
def get_job(job_id: str) -> dict:
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "not found"})
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "result_ref": job.result_ref,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "trace_id": job.trace_id,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }

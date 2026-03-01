from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, text

from v2.config import V2Config
from v2.contracts.analyze import AnalyzeRequest
from v2.contracts.fetch import DownloadRequest, SearchRequest
from v2.contracts.parse import ParseRequest
from v2.contracts.recommend import RecommendRequest
from v2.contracts.report import DailyReportTaskRequest
from v2.contracts.research import ResearchTaskRequest
from v2.db.models import DailyReport, DailyReportItem, Job, Paper, ResearchTask, init_db
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService
from v2.services.daily_report.service import DailyReportService
from v2.services.fetch.service import FetchService
from v2.services.parse.service import ParseService
from v2.services.recommend.service import RecommendService
from v2.services.research.service import ResearchService
from v2.api.settings_runtime import SettingsRuntime

logging.basicConfig(
    level=getattr(logging, os.getenv("V2_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


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


def _safe_json_loads(payload: str | None, default: object) -> object:
    if not payload:
        return default
    try:
        return json.loads(payload)
    except Exception:
        return default


def _paper_row_payload(paper: Paper, liked_map: dict[str, str]) -> dict:
    latest = repo.latest_analysis(paper.paper_uid)
    analysis_payload = _safe_json_loads(latest.analysis_json if latest else None, {})
    tags = analysis_payload.get("tags", []) if isinstance(analysis_payload, dict) else []
    keywords = [str(x) for x in tags if str(x).strip()]
    pdf_artifact = repo.get_artifact(paper.paper_uid, "pdf")
    has_pdf = bool(pdf_artifact and Path(pdf_artifact.path).exists())
    return {
        "paper_uid": paper.paper_uid,
        "source": paper.source,
        "external_id": paper.external_id,
        "doi": paper.doi,
        "title": paper.title,
        "authors": _safe_json_loads(paper.authors_json, []),
        "abstract": paper.abstract,
        "published_at": paper.published_at.isoformat() if paper.published_at else None,
        "source_url": paper.source_url,
        "pdf_unavailable": bool(paper.pdf_unavailable),
        "recommended_count": int(paper.recommended_count or 0),
        "has_pdf": has_pdf,
        "pdf_url": f"/api/v1/papers/{paper.paper_uid}/pdf",
        "keywords": keywords,
        "liked": liked_map.get(paper.paper_uid) == "like",
    }


def _report_payload(report: DailyReport) -> dict:
    items = (
        repo.session.query(DailyReportItem)
        .filter(DailyReportItem.report_id == report.id)
        .order_by(DailyReportItem.rank.asc())
        .all()
    )
    return {
        "report_id": report.id,
        "report_date": report.report_date.date().isoformat(),
        "summary_md": report.summary_md,
        "paper_uids": [i.paper_uid for i in items],
        "meta": _safe_json_loads(report.meta_json, {}),
        "created_at": report.created_at.isoformat(),
    }


def _check_http_health(url: str) -> bool:
    health_url = f"{url.rstrip('/')}/health"
    try:
        resp = requests.get(health_url, timeout=1.5)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


def _ensure_pdf_for_paper_uid(paper_uid: str) -> str:
    artifact = repo.get_artifact(paper_uid, "pdf")
    if artifact and Path(artifact.path).exists():
        return artifact.path

    paper = repo.get_paper(paper_uid)
    if not paper:
        raise FileNotFoundError("PAPER_NOT_FOUND")

    out = fetch_service.download(
        DownloadRequest(
            source=paper.source,
            external_id=paper.external_id,
            pdf_url=paper.pdf_url,
        )
    )
    if out.get("pdf_unavailable") or not out.get("pdf_path"):
        raise FileNotFoundError("PAPER_PDF_NOT_FOUND")
    return str(out["pdf_path"])


def _ensure_text_for_paper_uid(paper_uid: str, method: str = "simple") -> tuple[str, bool]:
    cached = repo.get_artifact(paper_uid, "text", parser_method=method)
    if cached and Path(cached.path).exists():
        return str(cached.path), True

    _ensure_pdf_for_paper_uid(paper_uid)
    out = parse_service.parse(paper_uid=paper_uid, method=method, force_reparse=False)
    return str(out["text_path"]), bool(out.get("cached", False))


def _ensure_analysis_for_paper_uid(paper_uid: str) -> dict:
    latest = repo.latest_analysis(paper_uid)
    if latest:
        return json.loads(latest.analysis_json)

    paper = repo.get_paper(paper_uid)
    if not paper:
        raise FileNotFoundError("PAPER_NOT_FOUND")

    text_path, _ = _ensure_text_for_paper_uid(paper_uid, method="simple")
    full_text = Path(text_path).read_text(encoding="utf-8")
    out = analyze_service.analyze(paper_uid, paper.title, full_text, paper.abstract)
    return out["result"]


def _run_daily_report_job_async(job_id: str, payload: dict, trace_id: str) -> None:
    local_cfg = V2Config.from_env()
    local_session = init_db(local_cfg.database_url)
    local_repo = Repo(local_session)
    local_report_service = DailyReportService(local_repo, local_cfg)

    try:
        req = DailyReportTaskRequest.model_validate(payload)
        out = local_report_service.generate(
            report_date=datetime.combine(req.report_date, datetime.min.time()),
            sources=req.sources,
            keywords=req.keywords,
            top_k=req.top_k,
            window_days=req.window_days,
            arxiv_categories=req.arxiv_categories,
        )
        local_repo.update_job(job_id, status="completed", progress=100, result_ref=out["report_id"])
    except Exception as e:
        logger.exception("async reports_daily_generate failed trace_id=%s job_id=%s payload=%s", trace_id, job_id, payload)
        local_repo.update_job(job_id, status="failed", error_code="DAILY_REPORT_FAILED", error_message=str(e))
    finally:
        local_session.close()


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
        arxiv_categories=None,
    )
    saved = fetch_service.save_search_items(items)
    repo.update_job(job.id, status="completed", progress=100, result_ref=f"papers:{len(saved)}")
    return {"items": saved, "job_id": job.id, "trace_id": trace}


@app.get("/api/v1/papers")
def papers_list(page: int = 1, page_size: int = 20) -> dict:
    safe_page = max(1, int(page))
    safe_page_size = min(200, max(1, int(page_size)))

    query = repo.session.query(Paper).order_by(Paper.published_at.desc(), Paper.created_at.desc())
    total = query.count()
    rows = query.offset((safe_page - 1) * safe_page_size).limit(safe_page_size).all()
    liked_map = repo.latest_feedback_map()
    return {
        "items": [_paper_row_payload(row, liked_map) for row in rows],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


@app.get("/api/v1/papers/{paper_uid}")
def paper_detail(paper_uid: str) -> dict:
    paper = repo.get_paper(paper_uid)
    if not paper:
        raise HTTPException(status_code=404, detail={"code": "PAPER_NOT_FOUND", "message": "not found"})

    liked_map = repo.latest_feedback_map()
    payload = _paper_row_payload(paper, liked_map)
    latest = repo.latest_analysis(paper_uid)
    if latest:
        payload["analysis"] = _safe_json_loads(latest.analysis_json, None)
        payload["analysis_created_at"] = latest.created_at.isoformat()
        payload["analysis_status"] = "ready"
    else:
        if paper.pdf_unavailable:
            payload["analysis"] = None
            payload["analysis_created_at"] = None
            payload["analysis_status"] = "pdf_unavailable"
        else:
            try:
                payload["analysis"] = _ensure_analysis_for_paper_uid(paper_uid)
                refreshed = repo.latest_analysis(paper_uid)
                payload["analysis_created_at"] = refreshed.created_at.isoformat() if refreshed else None
                payload["analysis_status"] = "ready"
            except FileNotFoundError as e:
                reason = str(e)
                payload["analysis"] = None
                payload["analysis_created_at"] = None
                if reason in {"PAPER_PDF_NOT_FOUND", "PARSE_INPUT_NOT_FOUND"}:
                    payload["analysis_status"] = "pdf_unavailable"
                    logger.info("Skip lazy analyze in paper_detail for paper_uid=%s reason=%s", paper_uid, reason)
                else:
                    payload["analysis_status"] = "failed"
                    logger.exception("Lazy analyze failed in paper_detail for paper_uid=%s", paper_uid)
            except Exception:
                payload["analysis"] = None
                payload["analysis_created_at"] = None
                payload["analysis_status"] = "failed"
                logger.exception("Lazy analyze failed in paper_detail for paper_uid=%s", paper_uid)

    return payload


@app.get("/api/v1/papers/{paper_uid}/pdf")
def paper_pdf(paper_uid: str):
    try:
        pdf_path = _ensure_pdf_for_paper_uid(paper_uid)
        return FileResponse(path=pdf_path, media_type="application/pdf", filename=f"{paper_uid}.pdf")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "PAPER_PDF_NOT_FOUND", "message": "pdf not found"})
    except Exception as e:
        logger.exception("paper_pdf failed for paper_uid=%s", paper_uid)
        raise HTTPException(status_code=500, detail={"code": "PAPER_PDF_FETCH_FAILED", "message": str(e)})


@app.post("/api/v1/papers/import")
def papers_import(req: DownloadRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_import", req.model_dump(), trace)
    try:
        out = fetch_service.download(req)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["paper_uid"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        logger.exception("papers_import failed trace_id=%s payload=%s", trace, req.model_dump())
        repo.update_job(job.id, status="failed", error_code="FETCH_DOWNLOAD_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "FETCH_DOWNLOAD_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/papers/{paper_uid}/parse")
def papers_parse(paper_uid: str, req: ParseRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_parse", req.model_dump(), trace)
    try:
        if req.force_reparse:
            _ensure_pdf_for_paper_uid(paper_uid)
            out = parse_service.parse(paper_uid=paper_uid, method=req.method, force_reparse=True)
        else:
            text_path, cached = _ensure_text_for_paper_uid(paper_uid=paper_uid, method=req.method)
            text = Path(text_path).read_text(encoding="utf-8")
            out = {
                "paper_uid": paper_uid,
                "method": req.method,
                "text_path": text_path,
                "cached": cached,
                "char_count": len(text),
            }
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["text_path"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except FileNotFoundError as e:
        logger.exception("papers_parse input missing trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="PARSE_INPUT_NOT_FOUND", error_message=str(e))
        raise HTTPException(status_code=404, detail={"code": "PARSE_INPUT_NOT_FOUND", "message": str(e), "trace_id": trace})
    except Exception as e:
        logger.exception("papers_parse failed trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="PARSE_EXEC_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "PARSE_EXEC_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/papers/{paper_uid}/analyze")
def papers_analyze(paper_uid: str, req: AnalyzeRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_analyze", req.model_dump(), trace)
    try:
        if req.full_text and req.title:
            out = analyze_service.analyze(paper_uid, req.title, req.full_text, req.abstract)
        else:
            paper = repo.get_paper(paper_uid)
            if not paper:
                raise FileNotFoundError("PAPER_NOT_FOUND")
            text_path, _ = _ensure_text_for_paper_uid(paper_uid=paper_uid, method="simple")
            full_text = Path(text_path).read_text(encoding="utf-8")
            out = analyze_service.analyze(
                paper_uid,
                req.title or paper.title,
                req.full_text or full_text,
                req.abstract if req.abstract is not None else paper.abstract,
            )
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["analysis_id"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except FileNotFoundError as e:
        logger.exception("papers_analyze input missing trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="ANALYZE_INPUT_NOT_FOUND", error_message=str(e))
        raise HTTPException(status_code=404, detail={"code": "ANALYZE_INPUT_NOT_FOUND", "message": str(e), "trace_id": trace})
    except Exception as e:
        logger.exception("papers_analyze failed trace_id=%s paper_uid=%s", trace, paper_uid)
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
        logger.exception("recommendations_generate failed trace_id=%s payload=%s", trace, req.model_dump())
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
        logger.error("research_task failed trace_id=%s result=%s", trace, out)
        repo.update_job(job.id, status="failed", error_code="RESEARCH_FAILED", error_message=out.get("error", ""))
    return {"job_id": job.id, "trace_id": trace, "result": out}


@app.get("/api/v1/research/tasks/{task_id}")
def research_task_status(task_id: str) -> dict:
    try:
        return research_service.get_task(task_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": str(e)})


@app.get("/api/v1/research/tasks")
def research_task_list(limit: int = 50) -> dict:
    safe_limit = min(200, max(1, int(limit)))
    rows = (
        repo.session.query(ResearchTask)
        .order_by(ResearchTask.started_at.desc(), ResearchTask.finished_at.desc())
        .limit(safe_limit)
        .all()
    )
    return {
        "items": [
            {
                "task_id": row.id,
                "topic": row.topic,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "error_message": row.error_message,
            }
            for row in rows
        ]
    }


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
            window_days=req.window_days,
            arxiv_categories=req.arxiv_categories,
        )
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["report_id"])
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        logger.exception("reports_daily_generate failed trace_id=%s payload=%s", trace, req.model_dump(mode="json"))
        repo.update_job(job.id, status="failed", error_code="DAILY_REPORT_FAILED", error_message=str(e))
        raise HTTPException(status_code=500, detail={"code": "DAILY_REPORT_FAILED", "message": str(e), "trace_id": trace})


@app.post("/api/v1/reports/daily/generate-async")
def reports_daily_generate_async(req: DailyReportTaskRequest, x_trace_id: str | None = Header(default=None)) -> dict:
    trace = _trace_id(x_trace_id)
    payload = req.model_dump(mode="json")
    job = repo.create_job("daily_report_async", payload, trace)
    worker = threading.Thread(target=_run_daily_report_job_async, args=(job.id, payload, trace), daemon=True)
    worker.start()
    return {"job_id": job.id, "trace_id": trace, "status": "pending"}


@app.get("/api/v1/reports/daily/{report_id}")
def reports_daily_get(report_id: str) -> dict:
    report = repo.session.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "not found"})
    return _report_payload(report)


@app.get("/api/v1/reports/daily/by-date/{report_date}")
def reports_daily_get_by_date(report_date: date) -> dict:
    report = (
        repo.session.query(DailyReport)
        .filter(func.date(DailyReport.report_date) == report_date.isoformat())
        .order_by(DailyReport.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND", "message": "not found"})
    return _report_payload(report)


@app.get("/api/v1/settings")
def get_settings() -> dict:
    return settings_runtime.get()


@app.put("/api/v1/settings")
def put_settings(payload: dict) -> dict:
    return settings_runtime.update(payload)


@app.get("/api/v1/system/status")
def get_system_status() -> dict:
    db_ok = True
    try:
        repo.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    paper_count = repo.session.query(func.count(Paper.paper_uid)).scalar() or 0
    report_count = repo.session.query(func.count(DailyReport.id)).scalar() or 0
    task_count = repo.session.query(func.count(ResearchTask.id)).scalar() or 0
    job_count = repo.session.query(func.count(Job.id)).scalar() or 0
    liked_count = len(repo.get_feedback_actions("like"))

    service_health = {
        "api": True,
        "database": db_ok,
        "fetch_service": _check_http_health(config.fetch_service_url),
        "parse_service": _check_http_health(config.parse_service_url),
        "analyze_service": _check_http_health(config.analyze_service_url),
        "recommend_service": _check_http_health(config.recommend_service_url),
        "research_service": _check_http_health(config.research_service_url),
        "daily_report_service": _check_http_health(config.report_service_url),
    }

    return {
        "system_time": datetime.now().isoformat(),
        "timezone": config.timezone,
        "paper_count": int(paper_count),
        "daily_report_count": int(report_count),
        "research_task_count": int(task_count),
        "job_count": int(job_count),
        "liked_paper_count": int(liked_count),
        "service_health": service_health,
    }


@app.get("/api/v1/sources/availability")
def get_source_availability(window_days: int = 7) -> dict:
    safe_window = max(1, min(30, int(window_days)))
    end = datetime.now().date()
    start = end - timedelta(days=safe_window - 1)
    sources = ["arxiv", "huggingface", "openalex"]
    status = fetch_service.validate_sources(
        sources=sources,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        arxiv_categories=["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "stat.ML"],
    )
    overall_ok = all(item.get("ok") for item in status.values())
    return {
        "overall_ok": overall_ok,
        "window_days": safe_window,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "sources": status,
    }


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

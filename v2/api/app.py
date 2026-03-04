from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, text

from v2.api.settings_runtime import SettingsRuntime
from v2.config import V2Config
from v2.contracts.analyze import AnalyzeRequest
from v2.contracts.fetch import DownloadRequest, SearchRequest
from v2.contracts.parse import ParseRequest
from v2.contracts.recommend import RecommendRequest
from v2.contracts.report import DailyReportTaskRequest
from v2.contracts.research import ResearchTaskRequest
from v2.db.models import DailyReport, DailyReportItem, Job, Paper, ResearchTask, init_session_factory
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService
from v2.services.daily_report.service import DailyReportService
from v2.services.fetch.service import FetchService
from v2.services.parse.service import ParseService
from v2.services.recommend.service import RecommendService
from v2.services.research.service import ResearchService

logging.basicConfig(
    level=getattr(logging, os.getenv("V2_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    paper_uid: str
    action: str
    note: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    timezone: Optional[str] = None
    interest_keywords: Optional[list[str]] = None
    excluded_keywords: Optional[list[str]] = None
    default_sources: Optional[list[str]] = None
    daily_report_sources: Optional[list[str]] = None
    daily_report_keywords: Optional[list[str]] = None
    daily_report_arxiv_categories: Optional[list[str]] = None
    daily_report_top_k: Optional[int] = Field(default=None, ge=1, le=50)
    daily_report_window_days: Optional[int] = Field(default=None, ge=1, le=30)
    recommend_strategy_weights: Optional[dict[str, float]] = None
    scholar_provider: Optional[str] = None
    scholar_rate_limit_rps: Optional[float] = Field(default=None, ge=0.1, le=100)
    batch_download_concurrency: Optional[int] = Field(default=None, ge=1, le=64)
    batch_parse_concurrency: Optional[int] = Field(default=None, ge=1, le=64)
    batch_analyze_concurrency: Optional[int] = Field(default=None, ge=1, le=64)
    pdf_lru_max_bytes: Optional[int] = Field(default=None, ge=1)
    pdf_lru_max_count: Optional[int] = Field(default=None, ge=1)
    ocr_timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    research_timeout_minutes: Optional[int] = Field(default=None, ge=1, le=180)

    @field_validator("recommend_strategy_weights")
    @classmethod
    def validate_weights(cls, value: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if value is None:
            return None
        allowed = {"keyword_semantic", "interested_semantic", "repetition_penalty", "llm_theme", "recommended_inverse"}
        unknown = [k for k in value.keys() if k not in allowed]
        if unknown:
            raise ValueError(f"unsupported weight keys: {unknown}")
        for k, v in value.items():
            if not 0 <= float(v) <= 1:
                raise ValueError(f"weight out of range for {k}: {v}")
        return value


config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

_worker_lock = threading.Lock()
_worker_threads: dict[str, threading.Thread] = {}


def get_repo() -> Generator[Repo, None, None]:
    session = SessionLocal()
    try:
        repo = Repo(session)
        repo.ensure_profile()
        yield repo
    finally:
        session.close()


def _trace_id(incoming: Optional[str]) -> str:
    return incoming or uuid.uuid4().hex


def _safe_json_loads(payload: Optional[str], default: object) -> object:
    if not payload:
        return default
    try:
        return json.loads(payload)
    except Exception:
        return default


def _duration_ms(start_perf: float) -> int:
    return max(1, int((time.perf_counter() - start_perf) * 1000))


def _record_service_call(
    repo: Repo,
    trace_id: str,
    service_name: str,
    endpoint: str,
    request_summary: dict,
    response_summary: dict,
    status_code: int,
    start_perf: float,
    error_code: Optional[str] = None,
) -> None:
    try:
        repo.log_service_call(
            trace_id=trace_id,
            service_name=service_name,
            endpoint=endpoint,
            request_summary=request_summary,
            response_summary=response_summary,
            status_code=status_code,
            duration_ms=_duration_ms(start_perf),
            error_code=error_code,
        )
    except Exception:
        logger.exception("failed to write service_call_log trace_id=%s service=%s endpoint=%s", trace_id, service_name, endpoint)


def _http_error(status_code: int, code: str, message: str, trace_id: Optional[str] = None, details: Optional[dict[str, Any]] = None) -> HTTPException:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    if trace_id:
        payload["trace_id"] = trace_id
    return HTTPException(status_code=status_code, detail=payload)


def _paper_row_payload(repo: Repo, paper: Paper, liked_map: dict[str, str]) -> dict:
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


def _report_payload(repo: Repo, report: DailyReport) -> dict:
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


def _ensure_pdf_for_paper_uid(repo: Repo, fetch_service: FetchService, paper_uid: str) -> str:
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


def _ensure_text_for_paper_uid(repo: Repo, fetch_service: FetchService, parse_service: ParseService, paper_uid: str, method: str = "simple") -> tuple[str, bool]:
    cached = repo.get_artifact(paper_uid, "text", parser_method=method)
    if cached and Path(cached.path).exists():
        return str(cached.path), True

    _ensure_pdf_for_paper_uid(repo, fetch_service, paper_uid)
    out = parse_service.parse(paper_uid=paper_uid, method=method, force_reparse=False)
    return str(out["text_path"]), bool(out.get("cached", False))


def _ensure_analysis_for_paper_uid(
    repo: Repo,
    fetch_service: FetchService,
    parse_service: ParseService,
    analyze_service: AnalyzeService,
    paper_uid: str,
) -> dict:
    latest = repo.latest_analysis(paper_uid)
    if latest:
        return json.loads(latest.analysis_json)

    paper = repo.get_paper(paper_uid)
    if not paper:
        raise FileNotFoundError("PAPER_NOT_FOUND")

    text_path, _ = _ensure_text_for_paper_uid(repo, fetch_service, parse_service, paper_uid, method="simple")
    full_text = Path(text_path).read_text(encoding="utf-8")
    out = analyze_service.analyze(paper_uid, paper.title, full_text, paper.abstract)
    return out["result"]


def _run_daily_report_job_async(job_id: str, payload: dict, trace_id: str) -> None:
    local_session = SessionLocal()
    local_repo = Repo(local_session)
    local_repo.ensure_profile()
    local_report_service = DailyReportService(local_repo, config)

    try:
        local_repo.update_job(job_id, status="running", progress=10)
        req = DailyReportTaskRequest.model_validate(payload)
        start_perf = time.perf_counter()
        out = local_report_service.generate(
            report_date=datetime.combine(req.report_date, datetime.min.time()),
            sources=req.sources,
            keywords=req.keywords,
            top_k=req.top_k,
            window_days=req.window_days,
            arxiv_categories=req.arxiv_categories,
        )
        local_repo.update_job(job_id, status="completed", progress=100, result_ref=out["report_id"])
        _record_service_call(
            local_repo,
            trace_id,
            "daily_report",
            "/generate",
            payload,
            {"report_id": out["report_id"], "paper_count": len(out.get("paper_uids", []))},
            200,
            start_perf,
        )
    except Exception as e:
        logger.exception("async reports_daily_generate failed trace_id=%s job_id=%s payload=%s", trace_id, job_id, payload)
        local_repo.update_job(job_id, status="failed", error_code="DAILY_REPORT_FAILED", error_message=str(e))
        _record_service_call(
            local_repo,
            trace_id,
            "daily_report",
            "/generate",
            payload,
            {"error": str(e)},
            500,
            time.perf_counter(),
            error_code="DAILY_REPORT_FAILED",
        )
    finally:
        local_session.close()


def _run_research_task_async(job_id: str, payload: dict, trace_id: str) -> None:
    local_session = SessionLocal()
    local_repo = Repo(local_session)
    local_repo.ensure_profile()
    local_research_service = ResearchService(local_repo, config)

    task_id = str(payload.get("task_id", ""))
    try:
        if not task_id:
            raise RuntimeError("TASK_ID_MISSING")
        local_repo.update_job(job_id, status="running", progress=10)
        start_perf = time.perf_counter()
        out = local_research_service.execute_task(task_id)
        if out["status"] == "completed":
            local_repo.update_job(job_id, status="completed", progress=100, result_ref=task_id)
            _record_service_call(
                local_repo,
                trace_id,
                "research",
                "/tasks/execute",
                {"task_id": task_id},
                {"status": "completed"},
                200,
                start_perf,
            )
        else:
            local_repo.update_job(
                job_id,
                status="failed",
                error_code="RESEARCH_FAILED",
                error_message=out.get("error", ""),
            )
            _record_service_call(
                local_repo,
                trace_id,
                "research",
                "/tasks/execute",
                {"task_id": task_id},
                {"status": "failed", "error": out.get("error", "")},
                500,
                start_perf,
                error_code="RESEARCH_FAILED",
            )
    except Exception as e:
        logger.exception("async research task failed trace_id=%s job_id=%s payload=%s", trace_id, job_id, payload)
        local_repo.update_job(job_id, status="failed", error_code="RESEARCH_FAILED", error_message=str(e))
        _record_service_call(
            local_repo,
            trace_id,
            "research",
            "/tasks/execute",
            payload,
            {"error": str(e)},
            500,
            time.perf_counter(),
            error_code="RESEARCH_FAILED",
        )
    finally:
        local_session.close()


def _start_background_job(job_id: str, target, args: tuple) -> None:
    def _runner() -> None:
        try:
            target(*args)
        finally:
            with _worker_lock:
                _worker_threads.pop(job_id, None)

    with _worker_lock:
        running = _worker_threads.get(job_id)
        if running and running.is_alive():
            return
        worker = threading.Thread(target=_runner, daemon=True)
        _worker_threads[job_id] = worker
        worker.start()


def _resume_pending_jobs() -> None:
    session = SessionLocal()
    repo = Repo(session)
    try:
        for job in repo.list_jobs(job_types=["daily_report_async", "research_task_async"], statuses=["pending", "running"]):
            payload = _safe_json_loads(job.payload_json, {})
            if not isinstance(payload, dict):
                payload = {}
            if job.job_type == "daily_report_async":
                _start_background_job(job.id, _run_daily_report_job_async, (job.id, payload, job.trace_id))
            elif job.job_type == "research_task_async":
                _start_background_job(job.id, _run_research_task_async, (job.id, payload, job.trace_id))
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _resume_pending_jobs()
    yield


app = FastAPI(title="Daily Paper V2 API", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "version": "v2"}


@app.post("/api/v1/papers/search")
def papers_search(req: SearchRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("papers_search", req.model_dump(mode="json"), trace)
    fetch_service = FetchService(repo, config)
    start_perf = time.perf_counter()
    try:
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
        _record_service_call(
            repo,
            trace,
            "fetch",
            "/search",
            req.model_dump(mode="json"),
            {"saved_count": len(saved)},
            200,
            start_perf,
        )
        return {"items": saved, "job_id": job.id, "trace_id": trace}
    except Exception as e:
        logger.exception("papers_search failed trace_id=%s payload=%s", trace, req.model_dump(mode="json"))
        repo.update_job(job.id, status="failed", error_code="FETCH_SEARCH_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "fetch",
            "/search",
            req.model_dump(mode="json"),
            {"error": str(e)},
            500,
            start_perf,
            error_code="FETCH_SEARCH_FAILED",
        )
        raise _http_error(500, "FETCH_SEARCH_FAILED", str(e), trace)


@app.get("/api/v1/papers")
def papers_list(page: int = 1, page_size: int = 20, repo: Repo = Depends(get_repo)) -> dict:
    safe_page = max(1, int(page))
    safe_page_size = min(200, max(1, int(page_size)))

    query = repo.session.query(Paper).order_by(Paper.published_at.desc(), Paper.created_at.desc())
    total = query.count()
    rows = query.offset((safe_page - 1) * safe_page_size).limit(safe_page_size).all()
    row_uids = [r.paper_uid for r in rows]
    liked_map = repo.latest_feedback_map(row_uids)
    return {
        "items": [_paper_row_payload(repo, row, liked_map) for row in rows],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


@app.get("/api/v1/papers/{paper_uid}")
def paper_detail(paper_uid: str, repo: Repo = Depends(get_repo)) -> dict:
    paper = repo.get_paper(paper_uid)
    if not paper:
        raise _http_error(404, "PAPER_NOT_FOUND", "not found")

    fetch_service = FetchService(repo, config)
    parse_service = ParseService(repo, config)
    analyze_service = AnalyzeService(repo)

    liked_map = repo.latest_feedback_map([paper_uid])
    payload = _paper_row_payload(repo, paper, liked_map)
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
                payload["analysis"] = _ensure_analysis_for_paper_uid(repo, fetch_service, parse_service, analyze_service, paper_uid)
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
def paper_pdf(paper_uid: str, repo: Repo = Depends(get_repo)):
    fetch_service = FetchService(repo, config)
    try:
        pdf_path = _ensure_pdf_for_paper_uid(repo, fetch_service, paper_uid)
        return FileResponse(path=pdf_path, media_type="application/pdf", filename=f"{paper_uid}.pdf")
    except FileNotFoundError:
        raise _http_error(404, "PAPER_PDF_NOT_FOUND", "pdf not found")
    except Exception as e:
        logger.exception("paper_pdf failed for paper_uid=%s", paper_uid)
        raise _http_error(500, "PAPER_PDF_FETCH_FAILED", str(e))


@app.post("/api/v1/papers/import")
def papers_import(req: DownloadRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_import", req.model_dump(), trace)
    fetch_service = FetchService(repo, config)
    start_perf = time.perf_counter()
    try:
        out = fetch_service.download(req)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["paper_uid"])
        _record_service_call(repo, trace, "fetch", "/download", req.model_dump(), out, 200, start_perf)
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        logger.exception("papers_import failed trace_id=%s payload=%s", trace, req.model_dump())
        repo.update_job(job.id, status="failed", error_code="FETCH_DOWNLOAD_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "fetch",
            "/download",
            req.model_dump(),
            {"error": str(e)},
            500,
            start_perf,
            error_code="FETCH_DOWNLOAD_FAILED",
        )
        raise _http_error(500, "FETCH_DOWNLOAD_FAILED", str(e), trace)


@app.post("/api/v1/papers/{paper_uid}/parse")
def papers_parse(paper_uid: str, req: ParseRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    if req.paper_uid != paper_uid:
        raise _http_error(400, "PAPER_UID_MISMATCH", "path paper_uid and body paper_uid must match")

    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_parse", req.model_dump(), trace)
    fetch_service = FetchService(repo, config)
    parse_service = ParseService(repo, config)
    start_perf = time.perf_counter()
    try:
        if req.force_reparse:
            _ensure_pdf_for_paper_uid(repo, fetch_service, paper_uid)
            out = parse_service.parse(paper_uid=paper_uid, method=req.method, force_reparse=True)
        else:
            text_path, cached = _ensure_text_for_paper_uid(repo, fetch_service, parse_service, paper_uid=paper_uid, method=req.method)
            text = Path(text_path).read_text(encoding="utf-8")
            out = {
                "paper_uid": paper_uid,
                "method": req.method,
                "text_path": text_path,
                "cached": cached,
                "char_count": len(text),
            }
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["text_path"])
        _record_service_call(repo, trace, "parse", "/parse", req.model_dump(), {"text_path": out["text_path"]}, 200, start_perf)
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except FileNotFoundError as e:
        logger.exception("papers_parse input missing trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="PARSE_INPUT_NOT_FOUND", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "parse",
            "/parse",
            req.model_dump(),
            {"error": str(e)},
            404,
            start_perf,
            error_code="PARSE_INPUT_NOT_FOUND",
        )
        raise _http_error(404, "PARSE_INPUT_NOT_FOUND", str(e), trace)
    except Exception as e:
        logger.exception("papers_parse failed trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="PARSE_EXEC_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "parse",
            "/parse",
            req.model_dump(),
            {"error": str(e)},
            500,
            start_perf,
            error_code="PARSE_EXEC_FAILED",
        )
        raise _http_error(500, "PARSE_EXEC_FAILED", str(e), trace)


@app.post("/api/v1/papers/{paper_uid}/analyze")
def papers_analyze(paper_uid: str, req: AnalyzeRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    if req.paper_uid != paper_uid:
        raise _http_error(400, "PAPER_UID_MISMATCH", "path paper_uid and body paper_uid must match")

    trace = _trace_id(x_trace_id)
    job = repo.create_job("paper_analyze", req.model_dump(), trace)
    fetch_service = FetchService(repo, config)
    parse_service = ParseService(repo, config)
    analyze_service = AnalyzeService(repo)
    start_perf = time.perf_counter()
    try:
        if req.full_text and req.title:
            out = analyze_service.analyze(paper_uid, req.title, req.full_text, req.abstract)
        else:
            paper = repo.get_paper(paper_uid)
            if not paper:
                raise FileNotFoundError("PAPER_NOT_FOUND")
            text_path, _ = _ensure_text_for_paper_uid(repo, fetch_service, parse_service, paper_uid=paper_uid, method="simple")
            full_text = Path(text_path).read_text(encoding="utf-8")
            out = analyze_service.analyze(
                paper_uid,
                req.title or paper.title,
                req.full_text or full_text,
                req.abstract if req.abstract is not None else paper.abstract,
            )
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["analysis_id"])
        _record_service_call(repo, trace, "analyze", "/analyze", req.model_dump(), {"analysis_id": out["analysis_id"]}, 200, start_perf)
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except FileNotFoundError as e:
        logger.exception("papers_analyze input missing trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="ANALYZE_INPUT_NOT_FOUND", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "analyze",
            "/analyze",
            req.model_dump(),
            {"error": str(e)},
            404,
            start_perf,
            error_code="ANALYZE_INPUT_NOT_FOUND",
        )
        raise _http_error(404, "ANALYZE_INPUT_NOT_FOUND", str(e), trace)
    except Exception as e:
        logger.exception("papers_analyze failed trace_id=%s paper_uid=%s", trace, paper_uid)
        repo.update_job(job.id, status="failed", error_code="ANALYZE_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "analyze",
            "/analyze",
            req.model_dump(),
            {"error": str(e)},
            500,
            start_perf,
            error_code="ANALYZE_FAILED",
        )
        raise _http_error(500, "ANALYZE_FAILED", str(e), trace)


@app.post("/api/v1/recommendations/generate")
def recommendations_generate(req: RecommendRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("recommend_generate", req.model_dump(), trace)
    recommend_service = RecommendService(repo)
    start_perf = time.perf_counter()
    try:
        out = recommend_service.recommend(req.paper_uids, req.top_k)
        repo.update_job(job.id, status="completed", progress=100, result_ref=out["run_id"])
        _record_service_call(repo, trace, "recommend", "/recommend", req.model_dump(), {"run_id": out["run_id"]}, 200, start_perf)
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        logger.exception("recommendations_generate failed trace_id=%s payload=%s", trace, req.model_dump())
        repo.update_job(job.id, status="failed", error_code="RECOMMEND_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "recommend",
            "/recommend",
            req.model_dump(),
            {"error": str(e)},
            500,
            start_perf,
            error_code="RECOMMEND_FAILED",
        )
        raise _http_error(500, "RECOMMEND_FAILED", str(e), trace)


@app.post("/api/v1/interactions")
def interactions(req: FeedbackRequest, repo: Repo = Depends(get_repo)) -> dict:
    repo.save_feedback(req.paper_uid, req.action, req.note)
    return {"status": "ok"}


@app.post("/api/v1/research/tasks")
def research_task(req: ResearchTaskRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    research_service = ResearchService(repo, config)
    job = repo.create_job("research_task_async", req.model_dump(), trace)
    start_perf = time.perf_counter()
    try:
        created = research_service.create_task(req.topic, req.constraints)
        payload = {"task_id": created["task_id"], **req.model_dump()}
        repo.update_job(job.id, payload_json=json.dumps(payload, ensure_ascii=False), result_ref=created["task_id"])
        _start_background_job(job.id, _run_research_task_async, (job.id, payload, trace))
        _record_service_call(repo, trace, "research", "/tasks/create", payload, {"status": "pending"}, 202, start_perf)
        return {
            "job_id": job.id,
            "trace_id": trace,
            "result": {"task_id": created["task_id"], "status": "pending"},
        }
    except Exception as e:
        logger.exception("research_task failed trace_id=%s payload=%s", trace, req.model_dump())
        repo.update_job(job.id, status="failed", error_code="RESEARCH_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "research",
            "/tasks/create",
            req.model_dump(),
            {"error": str(e)},
            500,
            start_perf,
            error_code="RESEARCH_FAILED",
        )
        raise _http_error(500, "RESEARCH_FAILED", str(e), trace)


@app.get("/api/v1/research/tasks/{task_id}")
def research_task_status(task_id: str, repo: Repo = Depends(get_repo)) -> dict:
    research_service = ResearchService(repo, config)
    try:
        return research_service.get_task(task_id)
    except FileNotFoundError as e:
        raise _http_error(404, "TASK_NOT_FOUND", str(e))


@app.get("/api/v1/research/tasks")
def research_task_list(limit: int = 50, repo: Repo = Depends(get_repo)) -> dict:
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
def research_task_result(task_id: str, repo: Repo = Depends(get_repo)) -> dict:
    research_service = ResearchService(repo, config)
    try:
        return research_service.get_result(task_id)
    except FileNotFoundError as e:
        raise _http_error(404, "RESEARCH_REPORT_NOT_FOUND", str(e))


@app.post("/api/v1/reports/daily/generate")
def reports_daily_generate(req: DailyReportTaskRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    job = repo.create_job("daily_report", req.model_dump(mode="json"), trace)
    report_service = DailyReportService(repo, config)
    start_perf = time.perf_counter()
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
        _record_service_call(repo, trace, "daily_report", "/generate", req.model_dump(mode="json"), {"report_id": out["report_id"]}, 200, start_perf)
        return {"job_id": job.id, "trace_id": trace, "result": out}
    except Exception as e:
        logger.exception("reports_daily_generate failed trace_id=%s payload=%s", trace, req.model_dump(mode="json"))
        repo.update_job(job.id, status="failed", error_code="DAILY_REPORT_FAILED", error_message=str(e))
        _record_service_call(
            repo,
            trace,
            "daily_report",
            "/generate",
            req.model_dump(mode="json"),
            {"error": str(e)},
            500,
            start_perf,
            error_code="DAILY_REPORT_FAILED",
        )
        raise _http_error(500, "DAILY_REPORT_FAILED", str(e), trace)


@app.post("/api/v1/reports/daily/generate-async")
def reports_daily_generate_async(req: DailyReportTaskRequest, x_trace_id: Optional[str] = Header(default=None), repo: Repo = Depends(get_repo)) -> dict:
    trace = _trace_id(x_trace_id)
    payload = req.model_dump(mode="json")
    job = repo.create_job("daily_report_async", payload, trace)
    _start_background_job(job.id, _run_daily_report_job_async, (job.id, payload, trace))
    return {"job_id": job.id, "trace_id": trace, "status": "pending"}


@app.get("/api/v1/reports/daily/{report_id}")
def reports_daily_get(report_id: str, repo: Repo = Depends(get_repo)) -> dict:
    report = repo.session.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise _http_error(404, "REPORT_NOT_FOUND", "not found")
    return _report_payload(repo, report)


@app.get("/api/v1/reports/daily/by-date/{report_date}")
def reports_daily_get_by_date(report_date: date, repo: Repo = Depends(get_repo)) -> dict:
    report = (
        repo.session.query(DailyReport)
        .filter(func.date(DailyReport.report_date) == report_date.isoformat())
        .order_by(DailyReport.created_at.desc())
        .first()
    )
    if not report:
        raise _http_error(404, "REPORT_NOT_FOUND", "not found")
    return _report_payload(repo, report)


@app.get("/api/v1/settings")
def get_settings(repo: Repo = Depends(get_repo)) -> dict:
    return SettingsRuntime(repo).get()


@app.put("/api/v1/settings")
def put_settings(payload: SettingsUpdateRequest, repo: Repo = Depends(get_repo)) -> dict:
    runtime = SettingsRuntime(repo)
    return runtime.update(payload.model_dump(exclude_none=True))


@app.get("/api/v1/system/status")
def get_system_status(repo: Repo = Depends(get_repo)) -> dict:
    db_ok = True
    try:
        repo.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    profile = repo.ensure_profile()
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
        "timezone": profile.timezone,
        "paper_count": int(paper_count),
        "daily_report_count": int(report_count),
        "research_task_count": int(task_count),
        "job_count": int(job_count),
        "liked_paper_count": int(liked_count),
        "service_health": service_health,
    }


@app.get("/api/v1/sources/availability")
def get_source_availability(window_days: int = 7, repo: Repo = Depends(get_repo)) -> dict:
    safe_window = max(1, min(30, int(window_days)))
    end = datetime.now().date()
    start = end - timedelta(days=safe_window - 1)
    fetch_service = FetchService(repo, config)
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
def get_job(job_id: str, repo: Repo = Depends(get_repo)) -> dict:
    job = repo.get_job(job_id)
    if not job:
        raise _http_error(404, "JOB_NOT_FOUND", "not found")
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

"""
Reports router for daily report generation.

Endpoints for generating and viewing daily reports with async background tasks.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_report_generator
from backend.models.report import ReportResponse, ReportGenerateRequest
from backend.models.paper import PaperResponse
from daily_paper.database import Paper, DailyReport, InterestTheme
from daily_paper.config import Config

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory task tracking for report generation
task_status = {}


@router.post("/generate")
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Generate daily report asynchronously.

    Uses background tasks to generate report with recommendations and AI highlights.

    Args:
        request: Report generation request with top_k and optional date
        background_tasks: FastAPI BackgroundTasks
        db: Database session

    Returns:
        Task ID for polling status.
    """
    # Create task ID
    task_id = str(uuid.uuid4())
    task_status[task_id] = {"status": "generating", "progress": 0}

    # Add background task
    background_tasks.add_task(
        _generate_report_task,
        db=db,
        task_id=task_id,
        top_k=request.top_k,
        date=request.date
    )

    return {"task_id": task_id, "status": "generating"}


def _generate_report_task(
    db: Session,
    task_id: str,
    top_k: int,
    date: str = None
):
    """Background task for report generation."""
    try:
        from daily_paper.reports import ReportGenerator

        task_status[task_id]["progress"] = 10
        logger.info(f"Generating report with top_k={top_k}, date={date}")

        config = Config.from_env()
        generator = ReportGenerator(config, db)

        task_status[task_id]["progress"] = 30

        # Generate report
        report_dict = generator.generate(top_k=top_k, save_to_db=True)

        task_status[task_id]["progress"] = 90

        # Check if report was generated successfully
        if not report_dict or 'report_date' not in report_dict:
            task_status[task_id] = {
                "status": "failed",
                "error": "无法生成日报：没有找到推荐的论文。请先配置您的兴趣关键词并标记一些感兴趣的论文。"
            }
            logger.warning(f"Report generation failed: no recommendations available")
            return

        # Extract report ID from database
        report = db.query(DailyReport).filter(
            DailyReport.report_date == report_dict['report_date']
        ).order_by(DailyReport.created_at.desc()).first()

        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "report_id": report.id if report else None
        }

        logger.info(f"Report generation completed: task_id={task_id}, report_id={report.id if report else None}")

    except Exception as e:
        logger.error(f"Report generation failed for task {task_id}: {e}")
        task_status[task_id] = {
            "status": "failed",
            "error": str(e)
        }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Get report generation task status for polling.

    Args:
        task_id: Task ID from generate endpoint

    Returns:
        Task status with progress and error if failed.
    """
    return task_status.get(task_id, {"status": "not_found"})


@router.get("/", response_model=List[ReportResponse])
async def get_reports(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Get recent daily reports.

    Args:
        limit: Maximum number of reports to return

    Returns:
        List of recent daily reports.
    """
    reports = db.query(DailyReport).order_by(
        DailyReport.report_date.desc()
    ).limit(limit).all()

    # Build response list
    result = []
    for report in reports:
        # Get paper IDs from recommendations JSON
        paper_ids = json.loads(report.recommendations) if report.recommendations else []
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()

        # Get themes
        themes = json.loads(report.themes_used) if report.themes_used else []

        result.append(ReportResponse(
            id=report.id,
            report_date=report.report_date,
            highlights=report.highlights,
            papers=[_paper_to_response(p) for p in papers],
            themes_used=themes,
            created_at=report.created_at,
        ))

    return result


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: Session = Depends(get_db)):
    """
    Get report details by ID.

    Args:
        report_id: Report database ID

    Returns:
        Daily report with papers and highlights.
    """
    report = db.query(DailyReport).filter(DailyReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get papers
    paper_ids = json.loads(report.recommendations) if report.recommendations else []
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()

    # Get themes
    themes = json.loads(report.themes_used) if report.themes_used else []

    return ReportResponse(
        id=report.id,
        report_date=report.report_date,
        highlights=report.highlights,
        papers=[_paper_to_response(p) for p in papers],
        themes_used=themes,
        created_at=report.created_at,
    )


@router.get("/by-date/{date_str}")
async def get_report_by_date(date_str: str, db: Session = Depends(get_db)):
    """
    Get report for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Daily report for the specified date, or 404 if not found.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Find report for the date
    report = db.query(DailyReport).filter(
        DailyReport.report_date >= target_date.date(),
        DailyReport.report_date < target_date.replace(day=target_date.day + 1).date() if target_date.day < 31 else target_date.date()
    ).order_by(DailyReport.created_at.desc()).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this date")

    # Get papers
    paper_ids = json.loads(report.recommendations) if report.recommendations else []
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()

    # Get themes
    themes = json.loads(report.themes_used) if report.themes_used else []

    return ReportResponse(
        id=report.id,
        report_date=report.report_date,
        highlights=report.highlights,
        papers=[_paper_to_response(p) for p in papers],
        themes_used=themes,
        created_at=report.created_at,
    )


def _paper_to_response(paper: Paper) -> PaperResponse:
    """Convert Paper model to PaperResponse."""
    return PaperResponse(
        id=paper.id,
        source=paper.source,
        paper_id=paper.paper_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        published_date=paper.published_date,
        url=paper.url,
        has_pdf=bool(paper.pdf_path),
        has_summary=len(paper.summaries) > 0,
        interaction_status=None,
        notes=None,
    )

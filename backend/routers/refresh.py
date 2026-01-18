"""
Refresh router for global paper pipeline operations.

Endpoints for triggering full pipeline: download, parse, summarize, recommend, generate reports.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from daily_paper.config import Config
from daily_paper.database import init_db, TaskHistory, TaskStep, SchedulerConfig
from daily_paper.manager import DownloadManager
from daily_paper.parsers import PDFParser
from daily_paper.summarizers.workflow import PaperSummarizer
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.reports.generator import ReportGenerator
from daily_paper.summarizers.llm_client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter()


def calculate_next_run(schedule_type: str, daily_time: Optional[str] = None,
                      weekly_day: Optional[int] = None, weekly_time: Optional[str] = None) -> Optional[datetime]:
    """
    Calculate the next scheduled run time based on configuration.

    Args:
        schedule_type: Type of schedule ('daily' or 'weekly')
        daily_time: Time for daily schedule (HH:MM format)
        weekly_day: Day of week for weekly schedule (0=Monday, 6=Sunday)
        weekly_time: Time for weekly schedule (HH:MM format)

    Returns:
        Next run datetime, or None if configuration is invalid
    """
    now = datetime.now()

    try:
        if schedule_type == "daily" and daily_time:
            # Parse daily time (HH:MM format)
            hour, minute = map(int, daily_time.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time has passed today, schedule for tomorrow
            if next_run <= now:
                next_run += timedelta(days=1)

            return next_run

        elif schedule_type == "weekly" and weekly_day is not None and weekly_time:
            # Parse weekly time (HH:MM format)
            hour, minute = map(int, weekly_time.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Calculate days until next occurrence of weekly_day
            current_weekday = now.weekday()  # 0=Monday, 6=Sunday
            days_until = (weekly_day - current_weekday) % 7

            # If today is the target day but time has passed, schedule for next week
            if days_until == 0 and next_run <= now:
                days_until = 7

            next_run += timedelta(days=days_until)
            return next_run

    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid scheduler configuration: {e}")

    return None


def create_task_step(session: Session, task_id: str, step_name: str) -> TaskStep:
    """Create a new task step record with start time."""
    step = TaskStep(
        task_id=task_id,
        step_name=step_name,
        status="processing",
        started_at=datetime.now()
    )
    session.add(step)
    session.commit()
    return step


def complete_task_step(session: Session, step: TaskStep, success: bool = True):
    """Mark a task step as completed and calculate duration."""
    step.completed_at = datetime.now()
    step.status = "completed" if success else "failed"

    if step.started_at:
        duration = step.completed_at - step.started_at
        step.duration_ms = int(duration.total_seconds() * 1000)

    session.commit()


def update_task_progress(session: Session, task_id: str, step: str, progress: int,
                         total_papers: int = 0, processed_papers: int = 0):
    """Update task progress in database."""
    task = session.query(TaskHistory).filter_by(task_id=task_id).first()
    if task:
        task.step = step
        task.progress = progress
        task.total_papers = total_papers
        task.processed_papers = processed_papers
        session.commit()


@router.post("/fetch")
async def fetch_papers(
    background_tasks: BackgroundTasks,
    parse: bool = True,
    summarize: bool = True,
    max_results: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch papers from sources (arXiv, HuggingFace) with optional parsing and summarization.

    Args:
        parse: Whether to parse downloaded PDFs
        summarize: Whether to generate summaries
        max_results: Maximum papers per source (default from config)

    Returns:
        Task ID for polling progress.
    """
    task_id = str(uuid.uuid4())

    # Create task record in database
    task = TaskHistory(
        task_id=task_id,
        task_type="fetch_papers",
        status="pending",
        step="initializing",
        progress=0
    )
    db.add(task)
    db.commit()

    background_tasks.add_task(
        _fetch_papers_task,
        task_id=task_id,
        parse=parse,
        summarize=summarize
    )

    return {"task_id": task_id, "status": "pending"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Get status of a refresh task."""
    task = db.query(TaskHistory).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.get("/history")
async def get_task_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get task history list."""
    tasks = db.query(TaskHistory).order_by(
        TaskHistory.started_at.desc()
    ).offset(skip).limit(limit).all()

    return {
        "tasks": [task.to_dict() for task in tasks],
        "count": len(tasks)
    }


@router.get("/history/{task_id}")
async def get_task_detail(task_id: str, db: Session = Depends(get_db)):
    """Get detailed task information including steps."""
    task = db.query(TaskHistory).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    steps = db.query(TaskStep).filter_by(task_id=task_id).order_by(
        TaskStep.started_at.asc()
    ).all()

    return {
        "task": task.to_dict(),
        "steps": [step.to_dict() for step in steps]
    }


@router.get("/scheduler")
async def get_scheduler_status(db: Session = Depends(get_db)):
    """Get current scheduler status and configuration."""
    config = db.query(SchedulerConfig).first()

    if not config:
        # Create default config
        config = SchedulerConfig(
            id=1,
            enabled=False,
            schedule_type="daily",
            daily_time="09:00"
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return config.to_dict()


@router.put("/scheduler")
async def update_scheduler_config(
    enabled: bool = None,
    schedule_type: str = None,
    daily_time: str = None,
    weekly_day: int = None,
    weekly_time: str = None,
    db: Session = Depends(get_db)
):
    """
    Update scheduler configuration.

    Args:
        enabled: Enable or disable the scheduler
        schedule_type: Type of schedule ('daily' or 'weekly')
        daily_time: Time for daily execution (HH:MM format)
        weekly_day: Day of week for weekly execution (0=Monday, 6=Sunday)
        weekly_time: Time for weekly execution (HH:MM format)
    """
    config = db.query(SchedulerConfig).first()

    if not config:
        config = SchedulerConfig(id=1)
        db.add(config)

    if enabled is not None:
        config.enabled = enabled
    if schedule_type is not None:
        config.schedule_type = schedule_type
    if daily_time is not None:
        config.daily_time = daily_time
    if weekly_day is not None:
        config.weekly_day = weekly_day
    if weekly_time is not None:
        config.weekly_time = weekly_time

    # Calculate next run time
    config.next_run_at = calculate_next_run(
        config.schedule_type,
        config.daily_time,
        config.weekly_day,
        config.weekly_time
    )

    db.commit()
    db.refresh(config)

    logger.info(f"Scheduler config updated: {config}")
    return config.to_dict()


def _fetch_papers_task(
    task_id: str,
    parse: bool,
    summarize: bool
):
    """Background task for fetching papers pipeline."""
    config = Config.from_env()
    session = init_db(config.database.url)

    # Get task record
    task = session.query(TaskHistory).filter_by(task_id=task_id).first()
    if not task:
        logger.error(f"Task {task_id} not found in database")
        return

    try:
        # Update task status
        task.status = "processing"
        task.started_at = datetime.now()
        session.commit()

        # Step 1: Fetch paper metadata
        metadata_step = create_task_step(session, task_id, "fetching_metadata")
        update_task_progress(session, task_id, "fetching_metadata", 5)

        manager = DownloadManager(config)
        papers = manager.fetch_papers_by_date(
            target_date=datetime.now().date()
        )

        complete_task_step(session, metadata_step, success=True)
        update_task_progress(session, task_id, "fetching_metadata", 10, len(papers), 0)

        if not papers:
            task.status = "completed"
            task.completed_at = datetime.now()
            task.progress = 100
            session.commit()
            session.close()
            return

        # Step 2: Download actual PDF files
        download_step = create_task_step(session, task_id, "downloading_pdfs")
        update_task_progress(session, task_id, "downloading_pdfs", 15)

        downloaded_count = 0
        failed_downloads = 0

        for paper in papers:
            if not paper.pdf_path:  # Only download if not already downloaded
                try:
                    manager.download_paper(paper)
                    downloaded_count += 1
                    logger.info(f"Downloaded PDF for paper {paper.id}: {paper.title[:50]}")
                except Exception as e:
                    logger.warning(f"Failed to download PDF for {paper.title}: {e}")
                    failed_downloads += 1

        complete_task_step(session, download_step, success=True)
        update_task_progress(session, task_id, "downloading_pdfs", 30, len(papers), downloaded_count)

        logger.info(f"Downloaded {downloaded_count} PDFs, {failed_downloads} failed")

        # Filter papers that have PDFs for subsequent steps
        papers_with_pdfs = [p for p in papers if p.pdf_path]
        if not papers_with_pdfs:
            logger.warning("No PDFs downloaded, cannot proceed with parsing and summarization")
            task.status = "completed"
            task.completed_at = datetime.now()
            task.progress = 100
            task.total_papers = len(papers)
            task.failed_papers = len(papers)
            session.commit()
            session.close()
            return

        # Step 3: Parse PDFs
        parsed_count = 0
        failed_count = 0

        if parse:
            parse_step = create_task_step(session, task_id, "parsing")
            update_task_progress(session, task_id, "parsing", 40)

            parser = PDFParser(config.ocr)

            for paper in papers_with_pdfs:
                if paper.pdf_path and paper.text_path is None:
                    try:
                        # Parser now accepts paper object directly
                        result = parser.parse(paper, auto_save=True)
                        if result.success:
                            parsed_count += 1
                            logger.info(f"Parsed paper {paper.id}: {paper.title[:50]}")
                        else:
                            failed_count += 1
                            logger.warning(f"Parse failed for {paper.title}: {result.error_message}")
                    except Exception as e:
                        logger.warning(f"Failed to parse {paper.title}: {e}")
                        failed_count += 1

            complete_task_step(session, parse_step, success=True)
            update_task_progress(session, task_id, "parsing", 60, len(papers_with_pdfs), parsed_count)

        # Step 4: Generate summaries
        summarized_count = 0

        if summarize:
            summarize_step = create_task_step(session, task_id, "summarizing")
            update_task_progress(session, task_id, "summarizing", 70)

            llm_client = LLMClient(config.llm)
            parser = PDFParser(config.ocr)
            summarizer = PaperSummarizer(config, llm_client, parser)

            for paper in papers_with_pdfs:
                if paper.text_path and not paper.has_summary:
                    try:
                        results = summarizer.summarize_paper(paper)
                        if results:
                            summarized_count += 1
                            logger.info(f"Summarized paper {paper.id}: {paper.title[:50]}")
                    except Exception as e:
                        logger.warning(f"Failed to summarize {paper.title}: {e}")

            complete_task_step(session, summarize_step, success=True)
            update_task_progress(session, task_id, "summarizing", 90, len(papers_with_pdfs), summarized_count)

        # Complete task
        task.status = "completed"
        task.completed_at = datetime.now()
        task.progress = 100
        task.total_papers = len(papers)
        task.processed_papers = parsed_count
        task.failed_papers = failed_count
        session.commit()

        logger.info(f"Task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Fetch papers task {task_id} failed: {e}")
        task.status = "failed"
        task.completed_at = datetime.now()
        task.error_message = str(e)
        session.commit()

    finally:
        session.close()


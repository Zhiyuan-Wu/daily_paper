"""
Refresh router for global paper pipeline operations.

Endpoints for triggering full pipeline: download, parse, summarize, recommend, generate reports.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from daily_paper.config import Config
from daily_paper.database import init_db
from daily_paper.manager import DownloadManager
from daily_paper.parsers import PDFParser
from daily_paper.summarizers.workflow import PaperSummarizer
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.reports.generator import ReportGenerator
from daily_paper.summarizers.llm_client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory task tracking
refresh_tasks = {}

# Global scheduler state
scheduler_config = {
    "enabled": False,
    "last_run": None,
    "next_run": None,
    "interval_hours": 24,
}


@router.post("/fetch")
async def fetch_papers(
    background_tasks: BackgroundTasks,
    parse: bool = True,
    summarize: bool = True,
    max_results: Optional[int] = None,
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
    refresh_tasks[task_id] = {
        "status": "pending",
        "step": "initializing",
        "progress": 0,
        "fetched": 0,
        "parsed": 0,
        "summarized": 0,
        "error": None
    }

    background_tasks.add_task(
        _fetch_papers_task,
        task_id=task_id,
        parse=parse,
        summarize=summarize,
        max_results=max_results
    )

    return {"task_id": task_id, "status": "pending"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a refresh task."""
    task = refresh_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/scheduler")
async def get_scheduler_status():
    """Get current scheduler status and configuration."""
    return scheduler_config


@router.put("/scheduler")
async def update_scheduler_config(
    enabled: bool = None,
    interval_hours: int = None
):
    """
    Update scheduler configuration.

    Args:
        enabled: Enable or disable the scheduler
        interval_hours: Run interval in hours (default: 24)
    """
    if enabled is not None:
        scheduler_config["enabled"] = enabled
    if interval_hours is not None and interval_hours > 0:
        scheduler_config["interval_hours"] = interval_hours

    logger.info(f"Scheduler config updated: {scheduler_config}")
    return scheduler_config


def _fetch_papers_task(
    task_id: str,
    parse: bool,
    summarize: bool,
    max_results: Optional[int]
):
    """Background task for fetching papers pipeline."""
    try:
        config = Config.from_env()
        session = init_db(config.database.url)

        # Step 1: Download papers
        refresh_tasks[task_id]["step"] = "downloading"
        refresh_tasks[task_id]["progress"] = 10

        manager = DownloadManager(config)
        papers = manager.fetch_papers_by_date(
            date=datetime.now().strftime("%Y-%m-%d"),
            max_results=max_results
        )

        refresh_tasks[task_id]["fetched"] = len(papers)
        refresh_tasks[task_id]["progress"] = 30

        if not papers:
            refresh_tasks[task_id] = {
                "status": "completed",
                "step": "completed",
                "progress": 100,
                "fetched": 0,
                "parsed": 0,
                "summarized": 0,
                "message": "没有找到新论文"
            }
            return

        # Step 2: Parse PDFs
        parsed_count = 0
        summarized_count = 0

        if parse:
            refresh_tasks[task_id]["step"] = "parsing"
            refresh_tasks[task_id]["progress"] = 40

            parser = PDFParser(config.ocr)

            for paper in papers:
                if paper.pdf_path and paper.text_path is None:
                    try:
                        result = parser.parse(paper.pdf_path)
                        if result.success:
                            parsed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to parse {paper.title}: {e}")

            refresh_tasks[task_id]["parsed"] = parsed_count
            refresh_tasks[task_id]["progress"] = 60

        # Step 3: Generate summaries
        if summarize:
            refresh_tasks[task_id]["step"] = "summarizing"
            refresh_tasks[task_id]["progress"] = 70

            llm_client = LLMClient(config.llm)
            parser = PDFParser(config.ocr)
            summarizer = PaperSummarizer(config, llm_client, parser)

            for paper in papers:
                if paper.text_path and not paper.has_summary:
                    try:
                        results = summarizer.summarize_paper(paper)
                        if results:
                            summarized_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to summarize {paper.title}: {e}")

            refresh_tasks[task_id]["summarized"] = summarized_count
            refresh_tasks[task_id]["progress"] = 90

        # Complete
        refresh_tasks[task_id] = {
            "status": "completed",
            "step": "completed",
            "progress": 100,
            "fetched": len(papers),
            "parsed": parsed_count,
            "summarized": summarized_count,
            "message": f"成功获取 {len(papers)} 篇论文"
        }

        session.close()

    except Exception as e:
        logger.error(f"Fetch papers task failed: {e}")
        refresh_tasks[task_id] = {
            "status": "failed",
            "step": refresh_tasks[task_id].get("step", "unknown"),
            "progress": refresh_tasks[task_id].get("progress", 0),
            "error": str(e)
        }

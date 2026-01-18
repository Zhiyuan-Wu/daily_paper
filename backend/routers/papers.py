"""
Papers router for paper CRUD operations.

Endpoints for listing, searching, viewing, and downloading papers.
"""

import logging
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from pathlib import Path

from backend.dependencies import get_db, get_paper_summarizer
from backend.models.paper import (
    PaperResponse,
    PaperListResponse,
    SummaryResponse,
)
from daily_paper.database import Paper, PaperInteraction, Summary
from daily_paper.summarizers import PaperSummarizer

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory task tracking for summarization
task_status = {}


@router.get("/", response_model=PaperListResponse)
async def list_papers(
    keyword: Optional[str] = None,
    source: Optional[str] = None,
    interaction_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """
    List papers with pagination, search, and filters.

    Args:
        keyword: Search in title, authors, abstract
        source: Filter by paper source (arxiv, huggingface, etc.)
        interaction_status: Filter by interaction status (interested, not_interested, no_action)
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Paginated list of papers with interaction status.
    """
    # Build base query with eager loading of summaries
    query = db.query(Paper).options(selectinload(Paper.summaries))

    # Apply keyword search
    if keyword:
        search_filter = or_(
            Paper.title.ilike(f"%{keyword}%"),
            Paper.authors.ilike(f"%{keyword}%"),
            Paper.abstract.ilike(f"%{keyword}%")
        )
        query = query.filter(search_filter)

    # Apply source filter
    if source:
        query = query.filter(Paper.source == source)

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    papers = query.order_by(Paper.published_date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # Add interaction status and computed fields
    papers_with_status = []
    for paper in papers:
        # Extract TLDR from summaries
        tldr = None
        for summary in paper.summaries:
            if summary.summary_type == "tldr":
                tldr = summary.content
                break

        paper_dict = {
            "id": paper.id,
            "source": paper.source,
            "paper_id": paper.paper_id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "published_date": paper.published_date,
            "url": paper.url,
            "has_pdf": bool(paper.pdf_path),
            "has_summary": len(paper.summaries) > 0,
            "tldr": tldr,
            "interaction_status": None,
            "notes": None,
        }

        # Get interaction status
        interaction = db.query(PaperInteraction).filter(
            PaperInteraction.paper_id == paper.id
        ).first()

        if interaction:
            paper_dict["interaction_status"] = interaction.action
            paper_dict["notes"] = interaction.notes

        # Filter by interaction status if specified
        if interaction_status:
            if interaction_status == "no_action" and not interaction:
                papers_with_status.append(PaperResponse(**paper_dict))
            elif interaction and interaction.action == interaction_status:
                papers_with_status.append(PaperResponse(**paper_dict))
        else:
            papers_with_status.append(PaperResponse(**paper_dict))

    return PaperListResponse(
        papers=papers_with_status,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """
    Get paper details by ID.

    Args:
        paper_id: Paper database ID

    Returns:
        Paper details with interaction status and TLDR.
    """
    paper = db.query(Paper).options(selectinload(Paper.summaries)).filter(
        Paper.id == paper_id
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Extract TLDR from summaries
    tldr = None
    for summary in paper.summaries:
        if summary.summary_type == "tldr":
            tldr = summary.content
            break

    # Get interaction
    interaction = db.query(PaperInteraction).filter(
        PaperInteraction.paper_id == paper.id
    ).first()

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
        tldr=tldr,
        interaction_status=interaction.action if interaction else None,
        notes=interaction.notes if interaction else None,
    )


@router.get("/{paper_id}/pdf")
async def download_paper_pdf(paper_id: int, db: Session = Depends(get_db)):
    """
    Download paper PDF file.

    Args:
        paper_id: Paper database ID

    Returns:
        PDF file as attachment.
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()

    if not paper or not paper.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not found")

    pdf_path = Path(paper.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(
        path=pdf_path,
        filename=f"{paper.paper_id}.pdf",
        media_type="application/pdf"
    )


@router.get("/{paper_id}/summary", response_model=list[SummaryResponse])
async def get_paper_summaries(paper_id: int, db: Session = Depends(get_db)):
    """
    Get paper summaries.

    Args:
        paper_id: Paper database ID

    Returns:
        List of paper summaries with step names.
    """
    summaries = db.query(Summary).filter(Summary.paper_id == paper_id).all()

    # Map summary types to display names (3-step workflow)
    step_names = {
        "content_summary": "内容摘要",
        "deep_research": "深度研究",
        "tldr": "TLDR总结",
    }

    return [
        SummaryResponse(
            id=s.id,
            paper_id=s.paper_id,
            summary_type=s.summary_type,
            step_name=step_names.get(s.summary_type, s.summary_type),
            content=s.content,
            created_at=s.created_at,
        )
        for s in summaries
    ]


@router.post("/{paper_id}/summarize")
async def summarize_paper(
    paper_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    summarizer: PaperSummarizer = Depends(get_paper_summarizer),
):
    """
    Trigger paper summarization (async background task).

    Args:
        paper_id: Paper database ID
        background_tasks: FastAPI BackgroundTasks
        db: Database session
        summarizer: PaperSummarizer instance

    Returns:
        Task information for polling.
    """
    import uuid

    # Check if paper exists
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Check if paper has PDF or text
    if not paper.pdf_path and not paper.text_path:
        raise HTTPException(
            status_code=400,
            detail="Paper must have PDF or text file to summarize"
        )

    # Create task ID
    task_id = str(uuid.uuid4())
    task_status[task_id] = {"status": "summarizing", "progress": 0}

    # Add background task
    background_tasks.add_task(
        _summarize_paper_task,
        db=db,
        summarizer=summarizer,
        paper_id=paper_id,
        task_id=task_id
    )

    return {"task_id": task_id, "status": "summarizing"}


def _summarize_paper_task(
    db: Session,
    summarizer: PaperSummarizer,
    paper_id: int,
    task_id: str
):
    """Background task for paper summarization."""
    try:
        task_status[task_id]["progress"] = 10

        # Get paper
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            task_status[task_id] = {"status": "failed", "error": "Paper not found"}
            return

        task_status[task_id]["progress"] = 30

        # Run summarization
        results = summarizer.summarize_paper(paper, save_to_db=True)

        task_status[task_id]["progress"] = 90

        # Update task status
        task_status[task_id] = {
            "status": "completed",
            "progress": 100,
            "summary_count": len([r for r in results if r.success])
        }

        logger.info(f"Summarization completed for paper {paper_id}: {len(results)} steps")

    except Exception as e:
        logger.error(f"Summarization failed for paper {paper_id}: {e}")
        task_status[task_id] = {
            "status": "failed",
            "error": str(e)
        }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Get task status for polling.

    Args:
        task_id: Task ID from summarize endpoint

    Returns:
        Task status information.
    """
    return task_status.get(task_id, {"status": "not_found"})


@router.get("/by-date/{target_date}", response_model=list[PaperResponse])
async def get_papers_by_date(
    target_date: str,
    db: Session = Depends(get_db),
):
    """
    Get papers published on a specific date.

    Args:
        target_date: Date string in YYYY-MM-DD format

    Returns:
        List of papers published on the target date.
    """
    try:
        parsed_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    papers = db.query(Paper).filter(
        Paper.published_date >= parsed_date,
        Paper.published_date < parsed_date.replace(day=parsed_date.day + 1) if parsed_date.day < 31 else parsed_date
    ).all()

    # Convert to response models
    return [
        PaperResponse(
            id=p.id,
            source=p.source,
            paper_id=p.paper_id,
            title=p.title,
            authors=p.authors,
            abstract=p.abstract,
            published_date=p.published_date,
            url=p.url,
            has_pdf=bool(p.pdf_path),
            has_summary=len(p.summaries) > 0,
            interaction_status=None,
            notes=None,
        )
        for p in papers
    ]

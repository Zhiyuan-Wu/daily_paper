"""
Users router for user profile and interaction management.

Endpoints for getting/updating user profile and managing paper interactions.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_user_manager
from backend.models.user import (
    UserProfileResponse,
    UserProfileUpdateRequest,
    InteractionCreateRequest,
    InteractionResponse,
)
from daily_paper.database import Paper, PaperInteraction

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_manager = Depends(get_user_manager)
):
    """
    Get user profile.

    Returns:
        User profile with interests and keywords.
    """
    profile = user_manager.get_profile()
    return UserProfileResponse(
        id=profile.id,
        interested_keywords=profile.interested_keywords,
        disinterested_keywords=profile.disinterested_keywords,
        interest_description=profile.interest_description,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request: UserProfileUpdateRequest,
    user_manager = Depends(get_user_manager)
):
    """
    Update user profile interests and keywords.

    Args:
        request: Profile update request with interested/disinterested keywords and description

    Returns:
        Updated user profile.
    """
    profile = user_manager.update_interests(
        interested_keywords=request.interested_keywords,
        disinterested_keywords=request.disinterested_keywords,
        interest_description=request.interest_description,
    )

    return UserProfileResponse(
        id=profile.id,
        interested_keywords=profile.interested_keywords,
        disinterested_keywords=profile.disinterested_keywords,
        interest_description=profile.interest_description,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/interactions", response_model=List[InteractionResponse])
async def get_interactions(
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Get user interactions with papers.

    Args:
        action: Filter by action type (interested, not_interested, no_action)
        limit: Maximum number of interactions to return

    Returns:
        List of paper interactions.
    """
    query = db.query(PaperInteraction)

    if action:
        query = query.filter(PaperInteraction.action == action)

    interactions = query.order_by(
        PaperInteraction.created_at.desc()
    ).limit(limit).all()

    return [
        InteractionResponse(
            id=i.id,
            user_id=i.user_id,
            paper_id=i.paper_id,
            action=i.action,
            notes=i.notes,
            recommendation_count=i.recommendation_count,
            last_recommended_at=i.last_recommended_at,
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in interactions
    ]


@router.post("/interactions/{paper_id}", response_model=InteractionResponse)
async def mark_paper(
    paper_id: int,
    request: InteractionCreateRequest,
    user_manager = Depends(get_user_manager)
):
    """
    Mark a paper as interested or not interested.

    Args:
        paper_id: Paper database ID
        request: Interaction request with action and optional notes

    Returns:
        Updated or created interaction.
    """
    # Verify paper exists
    paper = user_manager.session.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Mark paper
    if request.action == "interested":
        interaction = user_manager.mark_paper_interested(
            paper_id=paper_id,
            notes=request.notes
        )
    elif request.action == "not_interested":
        interaction = user_manager.mark_paper_not_interested(
            paper_id=paper_id,
            notes=request.notes
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {request.action}. Must be 'interested' or 'not_interested'"
        )

    return InteractionResponse(
        id=interaction.id,
        user_id=interaction.user_id,
        paper_id=interaction.paper_id,
        action=interaction.action,
        notes=interaction.notes,
        recommendation_count=interaction.recommendation_count,
        last_recommended_at=interaction.last_recommended_at,
        created_at=interaction.created_at,
        updated_at=interaction.updated_at,
    )


@router.delete("/interactions/{paper_id}")
async def clear_paper_action(
    paper_id: int,
    user_manager = Depends(get_user_manager)
):
    """
    Clear action on a paper (reset to no_action).

    Args:
        paper_id: Paper database ID

    Returns:
        Success message.
    """
    result = user_manager.clear_paper_action(paper_id)

    if not result:
        raise HTTPException(status_code=404, detail="Interaction not found")

    return {"message": "Paper action cleared successfully"}


@router.get("/interested-papers")
async def get_interested_papers(
    limit: int = 50,
    user_manager = Depends(get_user_manager)
):
    """
    Get papers marked as interested.

    Args:
        limit: Maximum number of papers to return

    Returns:
        List of interested papers with details.
    """
    papers = user_manager.get_interested_papers(limit=limit)

    return [
        {
            "id": p.id,
            "source": p.source,
            "paper_id": p.paper_id,
            "title": p.title,
            "authors": p.authors,
            "abstract": p.abstract,
            "published_date": p.published_date.isoformat() if p.published_date else None,
            "url": p.url,
            "has_pdf": bool(p.pdf_path),
            "has_summary": len(p.summaries) > 0,
        }
        for p in papers
    ]

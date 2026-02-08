"""
Recommendations router for recommendation system.

Endpoints for generating and viewing recommendations.
"""

import logging
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db, get_recommendation_manager
from backend.models.recommendation import RecommendationResponse
from backend.models.paper import PaperResponse
from daily_paper.database import Paper, PaperInteraction, InterestTheme
from daily_paper.recommenders.base import RecommendationContext

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_recommendation_context(db: Session) -> RecommendationContext:
    """
    Build RecommendationContext from database.

    Collects all necessary data for recommendation generation.

    Args:
        db: Database session

    Returns:
        RecommendationContext with all required data.
    """
    # Get all papers as candidates
    candidate_papers = db.query(Paper).all()

    # Get interested/disinterested paper IDs
    interested_ids = set(
        db.query(PaperInteraction.paper_id)
        .filter(PaperInteraction.action == 'interested')
        .distinct()
        .all()
    )
    interested_ids = {pid[0] for pid in interested_ids}

    disinterested_ids = set(
        db.query(PaperInteraction.paper_id)
        .filter(PaperInteraction.action == 'not_interested')
        .distinct()
        .all()
    )
    disinterested_ids = {pid[0] for pid in disinterested_ids}

    # Get user keywords from profile (user_id = 1)
    from daily_paper.database import UserProfile
    user_profile = db.query(UserProfile).filter(UserProfile.id == 1).first()

    # Parse interested keywords from comma-separated string
    if user_profile and user_profile.interested_keywords:
        user_keywords = [k.strip() for k in user_profile.interested_keywords.split(',') if k.strip()]
    else:
        user_keywords = []

    # Get recommendation counts and last recommended times
    interactions = db.query(PaperInteraction).all()
    recommendation_counts = {i.paper_id: i.recommendation_count for i in interactions}
    last_recommended_at = {i.paper_id: i.last_recommended_at for i in interactions if i.last_recommended_at}

    return RecommendationContext(
        candidate_papers=candidate_papers,
        interested_paper_ids=interested_ids,
        disinterested_paper_ids=disinterested_ids,
        user_keywords=user_keywords,
        recommendation_counts=recommendation_counts,
        last_recommended_at=last_recommended_at,
    )


@router.post("/generate", response_model=List[RecommendationResponse])
async def generate_recommendations(
    top_k: int = 10,
    record_recommendations: bool = True,
    strategy_weights: Optional[Dict[str, float]] = None,
    db: Session = Depends(get_db),
    recommendation_manager = Depends(get_recommendation_manager),
):
    """
    Generate paper recommendations using multi-strategy fusion.

    Args:
        top_k: Number of recommendations to generate
        record_recommendations: Whether to record recommendations in database
        strategy_weights: Optional custom weights for each strategy
        db: Database session
        recommendation_manager: Recommendation manager instance

    Returns:
        List of recommendation results with scores and reasons.
    """
    try:
        # Build recommendation context from database
        context = _build_recommendation_context(db)

        # Generate recommendations using context
        results = recommendation_manager.recommend(
            context=context,
            top_k=top_k,
            strategy_weights=strategy_weights
        )

        # Record recommendations if requested
        if record_recommendations and results:
            _record_recommendations(db, results)

        return [
            RecommendationResponse(
                paper_id=r.paper_id,
                score=r.score,
                reason=r.reason,
                strategy_name=r.strategy_name,
                paper=None,
            )
            for r in results
        ]

    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[RecommendationResponse])
async def get_recommendations(
    top_k: int = 10,
    include_paper_details: bool = False,
    db: Session = Depends(get_db),
    recommendation_manager = Depends(get_recommendation_manager),
):
    """
    Get current recommendations without regenerating.

    Returns the most recent recommendations based on current user profile.

    Args:
        top_k: Number of recommendations to return
        include_paper_details: Whether to include full paper details in response
        db: Database session
        recommendation_manager: Recommendation manager instance

    Returns:
        List of recommendation results.
    """
    try:
        # Build recommendation context from database
        context = _build_recommendation_context(db)

        # Generate recommendations using context (without recording)
        results = recommendation_manager.recommend(
            context=context,
            top_k=top_k,
        )

        # If no recommendations, return empty list
        if not results:
            return []

        # Get paper IDs
        paper_ids = [r.paper_id for r in results]

        # Fetch papers if requested
        papers = {}
        if include_paper_details:
            papers_query = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
            papers = {p.id: p for p in papers_query}

        return [
            RecommendationResponse(
                paper_id=r.paper_id,
                score=r.score,
                reason=r.reason,
                strategy_name=r.strategy_name,
                paper=_paper_to_response(papers[r.paper_id]) if r.paper_id in papers else None,
            )
            for r in results
        ]

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


def _record_recommendations(db: Session, results: List[RecommendationResponse]) -> None:
    """
    Record recommendations in database.

    Updates PaperInteraction records with recommendation count and timestamp.

    Args:
        db: Database session
        results: List of recommendation results to record
    """
    from datetime import datetime

    try:
        for result in results:
            # Check if interaction exists
            interaction = db.query(PaperInteraction).filter(
                PaperInteraction.paper_id == result.paper_id
            ).first()

            if interaction:
                # Update existing interaction
                interaction.recommendation_count += 1
                interaction.last_recommended_at = datetime.now()
            else:
                # Create new interaction record
                new_interaction = PaperInteraction(
                    user_id=1,
                    paper_id=result.paper_id,
                    action='no_action',
                    recommendation_count=1,
                    last_recommended_at=datetime.now(),
                )
                db.add(new_interaction)

        db.commit()
        logger.info(f"Recorded {len(results)} recommendations in database")

    except Exception as e:
        logger.error(f"Failed to record recommendations: {e}")
        db.rollback()
        raise

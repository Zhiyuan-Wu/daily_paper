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
from daily_paper.database import Paper

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=List[RecommendationResponse])
async def generate_recommendations(
    top_k: int = 10,
    record_recommendations: bool = True,
    strategy_weights: Optional[Dict[str, float]] = None,
    recommendation_manager = Depends(get_recommendation_manager),
):
    """
    Generate paper recommendations using multi-strategy fusion.

    Args:
        top_k: Number of recommendations to generate
        record_recommendations: Whether to record recommendations in database
        strategy_weights: Optional custom weights for each strategy

    Returns:
        List of recommendation results with scores and reasons.
    """
    try:
        results = recommendation_manager.recommend(
            top_k=top_k,
            record_recommendations=record_recommendations,
            strategy_weights=strategy_weights
        )

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
        results = recommendation_manager.recommend(
            top_k=top_k,
            record_recommendations=False
        )

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

"""
Recommendation Pydantic models.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from .paper import PaperResponse


class RecommendationResponse(BaseModel):
    """Recommendation result model for API responses."""

    paper_id: int
    score: float
    reason: str
    strategy_name: str
    paper: Optional[PaperResponse] = None

    class Config:
        from_attributes = True

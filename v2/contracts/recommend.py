from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    paper_uids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=100)


class StrategyBreakdown(BaseModel):
    keyword_semantic: float = 0.0
    interested_semantic: float = 0.0
    repetition_penalty: float = 0.0
    llm_theme: float = 0.0


class RecommendationItem(BaseModel):
    paper_uid: str
    score: float
    rank: int
    strategy_breakdown: StrategyBreakdown
    reasons: list[str] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    items: list[RecommendationItem] = Field(default_factory=list)

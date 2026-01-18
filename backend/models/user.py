"""
User profile and interaction Pydantic models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserProfileResponse(BaseModel):
    """User profile model for API responses."""

    id: int
    interested_keywords: Optional[str] = None
    disinterested_keywords: Optional[str] = None
    interest_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdateRequest(BaseModel):
    """User profile update request."""

    interested_keywords: Optional[str] = Field(None, description="Comma-separated interested keywords")
    disinterested_keywords: Optional[str] = Field(None, description="Comma-separated disinterested keywords")
    interest_description: Optional[str] = Field(None, description="Free-text interest description")


class InteractionCreateRequest(BaseModel):
    """Create/update interaction request."""

    action: str = Field(..., description="Interaction action: 'interested' or 'not_interested'")
    notes: Optional[str] = Field(None, description="Optional user notes")


class InteractionResponse(BaseModel):
    """Interaction model for API responses."""

    id: int
    user_id: int
    paper_id: int
    action: str
    notes: Optional[str] = None
    recommendation_count: int
    last_recommended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

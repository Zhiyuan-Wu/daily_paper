"""
Paper and summary Pydantic models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PaperResponse(BaseModel):
    """Paper model for API responses."""

    id: int
    source: str
    paper_id: str
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    published_date: Optional[datetime] = None
    url: str
    has_pdf: bool = False
    has_summary: bool = False
    interaction_status: Optional[str] = None  # 'interested', 'not_interested', None
    notes: Optional[str] = None  # User notes

    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    """Paginated paper list response."""

    papers: List[PaperResponse]
    total: int
    page: int
    page_size: int


class PaperSearchRequest(BaseModel):
    """Paper search request parameters."""

    keyword: Optional[str] = Field(None, description="Search in title, authors, abstract")
    source: Optional[str] = Field(None, description="Filter by paper source")
    interaction_status: Optional[str] = Field(None, description="Filter by interaction status")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class SummaryResponse(BaseModel):
    """Paper summary model for API responses."""

    id: int
    paper_id: int
    summary_type: str
    step_name: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

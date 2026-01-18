"""
Daily report Pydantic models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from .paper import PaperResponse


class ReportGenerateRequest(BaseModel):
    """Report generation request."""

    top_k: int = Field(10, ge=1, le=50, description="Number of papers to include")
    date: Optional[str] = Field(None, description="Target date in YYYY-MM-DD format")


class ReportResponse(BaseModel):
    """Daily report model for API responses."""

    id: int
    report_date: datetime
    highlights: Optional[str] = None
    papers: List[PaperResponse]
    themes_used: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

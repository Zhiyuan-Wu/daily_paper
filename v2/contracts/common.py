from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None
    trace_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: int = 0
    result_ref: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

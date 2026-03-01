from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DailyReportTaskRequest(BaseModel):
    report_date: date
    sources: list[str] = Field(default_factory=lambda: ["openalex"])
    keywords: list[str] = Field(default_factory=list)
    top_k: int = Field(default=10, ge=1, le=50)


class DailyReportTaskResponse(BaseModel):
    task_id: str
    status: str


class DailyReportResponse(BaseModel):
    report_id: str
    report_date: str
    summary_md: str
    paper_uids: list[str] = Field(default_factory=list)

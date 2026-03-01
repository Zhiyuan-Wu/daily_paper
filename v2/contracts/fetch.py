from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["openalex"])
    keywords: list[str] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PaperItem(BaseModel):
    source: str
    external_id: str
    doi: Optional[str] = None
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    pdf_unavailable: bool = False


class SearchResponse(BaseModel):
    items: list[PaperItem] = Field(default_factory=list)


class DownloadRequest(BaseModel):
    source: str
    external_id: str
    pdf_url: Optional[str] = None


class DownloadResponse(BaseModel):
    paper_uid: str
    pdf_path: Optional[str] = None
    deduplicated: bool = False
    pdf_unavailable: bool = False


class BatchDownloadRequest(BaseModel):
    requests: list[DownloadRequest] = Field(default_factory=list)

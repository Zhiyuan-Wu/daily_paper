from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    paper_uid: str
    full_text: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None


class AnalyzeResult(BaseModel):
    tldr: str
    key_points: list[str] = Field(default_factory=list)
    problem_statement: str
    method_summary: str
    experiment_summary: str
    limitations: str
    tags: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    paper_uid: str
    result: AnalyzeResult

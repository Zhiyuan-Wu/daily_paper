from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchTaskRequest(BaseModel):
    topic: str
    constraints: dict[str, str] = Field(default_factory=dict)


class ResearchTaskResponse(BaseModel):
    task_id: str
    status: str


class SourceEvidence(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    evidence_snippet: str


class ResearchResultResponse(BaseModel):
    task_id: str
    report_md: str
    sources: list[SourceEvidence] = Field(default_factory=list)

from __future__ import annotations

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    paper_uid: str
    method: str = Field(default="simple", pattern="^(simple|ocr)$")
    force_reparse: bool = False


class ParseResponse(BaseModel):
    paper_uid: str
    method: str
    text_path: str
    cached: bool
    char_count: int


class BatchParseRequest(BaseModel):
    items: list[str] = Field(default_factory=list)
    method: str = Field(default="simple", pattern="^(simple|ocr)$")

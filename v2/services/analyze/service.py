from __future__ import annotations

import json
import uuid
from typing import Optional

from v2.contracts.analyze import AnalyzeResult
from v2.db.repo import Repo


class AnalyzeService:
    def __init__(self, repo: Repo):
        self.repo = repo

    def analyze(self, paper_uid: str, title: str, full_text: str, abstract: Optional[str]) -> dict:
        chunks = [line.strip() for line in full_text.splitlines() if line.strip()]
        first = chunks[:8]
        key_points = first[:5]
        if not key_points:
            key_points = [title]

        result = AnalyzeResult(
            tldr=(abstract or " ".join(key_points))[:280],
            key_points=key_points,
            problem_statement=(chunks[0] if chunks else title)[:300],
            method_summary=(chunks[1] if len(chunks) > 1 else "Method details unavailable")[:400],
            experiment_summary=(chunks[2] if len(chunks) > 2 else "Experiment details unavailable")[:400],
            limitations=(chunks[-1] if chunks else "Limitations not found")[:300],
            tags=self._infer_tags(title, abstract, full_text),
        )
        analysis_id = self.repo.save_analysis(paper_uid=paper_uid, analysis_json=result.model_dump_json(), pipeline_version="v1")
        return {"paper_uid": paper_uid, "result": json.loads(result.model_dump_json()), "analysis_id": analysis_id}

    @staticmethod
    def _infer_tags(title: str, abstract: Optional[str], text: str) -> list[str]:
        corpus = f"{title}\n{abstract or ''}\n{text}".lower()
        tags = []
        for tag in ["llm", "transformer", "rag", "agent", "multimodal", "reinforcement learning", "diffusion"]:
            if tag in corpus:
                tags.append(tag)
        return tags[:8]

from __future__ import annotations

import json
import math

from v2.db.models import AppProfile, Paper
from v2.db.repo import Repo


class RecommendService:
    def __init__(self, repo: Repo):
        self.repo = repo

    def recommend(self, paper_uids: list[str], top_k: int) -> dict:
        profile = self.repo.ensure_profile()
        weights = json.loads(profile.recommend_strategy_weights_json)
        feedback = self.repo.latest_feedback_map()

        try:
            interest_keywords = json.loads(profile.interest_keywords_json)
        except Exception:
            interest_keywords = []
        try:
            excluded_keywords = json.loads(profile.excluded_keywords_json)
        except Exception:
            excluded_keywords = []

        papers = self.repo.list_papers(paper_uids)
        scored = []
        for paper in papers:
            breakdown = self._score_paper(paper, interest_keywords, excluded_keywords, feedback)
            total = 0.0
            weight_sum = 0.0
            for key, score in breakdown.items():
                w = float(weights.get(key, 0.25))
                total += w * max(0.0, min(1.0, float(score)))
                weight_sum += w
            fused = total / weight_sum if weight_sum > 0 else 0.0

            if paper.pdf_unavailable:
                fused *= 0.7

            reasons = self._reasons(breakdown, paper.pdf_unavailable)
            scored.append((paper.paper_uid, fused, breakdown, reasons))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        run_id = self.repo.create_recommendation_run(
            query_context={"top_k": top_k},
            strategy_weights=weights,
        )

        items = []
        for idx, (paper_uid, score, breakdown, reasons) in enumerate(top, start=1):
            item = {
                "paper_uid": paper_uid,
                "score": round(score, 6),
                "rank": idx,
                "strategy_breakdown": breakdown,
                "reasons": reasons,
            }
            items.append(item)
        self.repo.save_recommendation_items(run_id, items)
        return {"items": items, "run_id": run_id}

    @staticmethod
    def _score_paper(paper: Paper, interest_keywords: list[str], excluded_keywords: list[str], feedback: dict[str, str]) -> dict:
        corpus = f"{paper.title}\n{paper.abstract or ''}".lower()
        keyword_hits = sum(1 for k in interest_keywords if k.lower() in corpus)
        keyword_semantic = min(1.0, keyword_hits / max(1, len(interest_keywords) or 1))

        # Using liked/read signals as a proxy for semantic interest.
        signal = feedback.get(paper.paper_uid)
        interested_semantic = 1.0 if signal in {"like", "read", "save"} else 0.4

        # Penalize repeated dismiss/dislike.
        repetition_penalty = 1.0
        if signal in {"dismiss", "dislike"}:
            repetition_penalty = 0.2

        # Lightweight theme scorer.
        llm_theme = 0.5 + 0.5 * keyword_semantic
        if any(k.lower() in corpus for k in excluded_keywords):
            llm_theme *= 0.2

        # New-paper preference: lower score as recommendation count increases.
        recommended_inverse = 1.0 / (1.0 + max(0, int(paper.recommended_count or 0)))

        return {
            "keyword_semantic": float(keyword_semantic),
            "interested_semantic": float(interested_semantic),
            "repetition_penalty": float(repetition_penalty),
            "llm_theme": float(min(1.0, llm_theme)),
            "recommended_inverse": float(recommended_inverse),
        }

    @staticmethod
    def _reasons(breakdown: dict, pdf_unavailable: bool) -> list[str]:
        reasons = []
        if breakdown["keyword_semantic"] > 0.5:
            reasons.append("Matches configured interest keywords")
        if breakdown["repetition_penalty"] < 0.5:
            reasons.append("Demoted by prior negative feedback")
        if breakdown.get("recommended_inverse", 1.0) < 0.5:
            reasons.append("Downranked due to frequent prior recommendations")
        if pdf_unavailable:
            reasons.append("No downloadable PDF; score penalized")
        if not reasons:
            reasons.append("Balanced score from default fusion")
        return reasons

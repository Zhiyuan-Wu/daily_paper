from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from v2.db.models import AppProfile, Job, Paper, PaperArtifact, PaperAnalysis, PaperFeedback, PaperSourceLink, RecommendationItem, RecommendationRun


class Repo:
    def __init__(self, session: Session):
        self.session = session

    def ensure_profile(self) -> AppProfile:
        profile = self.session.query(AppProfile).filter(AppProfile.id == 1).first()
        if profile is None:
            profile = AppProfile(id=1)
            self.session.add(profile)
            self.session.commit()
            self.session.refresh(profile)
        return profile

    def upsert_paper(self, data: dict) -> Paper:
        paper_uid = data["paper_uid"]
        paper = self.session.query(Paper).filter(Paper.paper_uid == paper_uid).first()
        if paper is None:
            paper = Paper(**data)
            self.session.add(paper)
        else:
            for key, value in data.items():
                setattr(paper, key, value)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def add_source_link(self, paper_uid: str, source: str, external_id: str, doi: str | None, source_url: str | None) -> None:
        link_id = uuid.uuid4().hex
        existing = self.session.query(PaperSourceLink).filter(
            PaperSourceLink.source == source,
            PaperSourceLink.external_id == external_id,
        ).first()
        if existing:
            return
        self.session.add(
            PaperSourceLink(
                id=link_id,
                paper_uid=paper_uid,
                source=source,
                external_id=external_id,
                doi=doi,
                source_url=source_url,
            )
        )
        self.session.commit()

    def upsert_artifact(self, artifact_id: str, payload: dict) -> None:
        item = self.session.query(PaperArtifact).filter(PaperArtifact.id == artifact_id).first()
        if item is None:
            self.session.add(PaperArtifact(id=artifact_id, **payload))
        else:
            for key, value in payload.items():
                setattr(item, key, value)
            item.last_accessed_at = datetime.now()
        self.session.commit()

    def get_paper(self, paper_uid: str) -> Paper | None:
        return self.session.query(Paper).filter(Paper.paper_uid == paper_uid).first()

    def list_papers(self, paper_uids: list[str] | None = None) -> list[Paper]:
        q = self.session.query(Paper)
        if paper_uids:
            q = q.filter(Paper.paper_uid.in_(paper_uids))
        return q.all()

    def get_artifact(self, paper_uid: str, artifact_type: str, parser_method: str | None = None) -> PaperArtifact | None:
        q = self.session.query(PaperArtifact).filter(
            PaperArtifact.paper_uid == paper_uid,
            PaperArtifact.artifact_type == artifact_type,
            PaperArtifact.evicted == 0,
        )
        if parser_method:
            q = q.filter(PaperArtifact.parser_method == parser_method)
        return q.first()

    def save_analysis(self, paper_uid: str, analysis_json: str, pipeline_version: str = "v1") -> str:
        analysis_id = uuid.uuid4().hex
        self.session.add(
            PaperAnalysis(
                id=analysis_id,
                paper_uid=paper_uid,
                analysis_json=analysis_json,
                pipeline_version=pipeline_version,
            )
        )
        self.session.commit()
        return analysis_id

    def latest_analysis(self, paper_uid: str) -> PaperAnalysis | None:
        return (
            self.session.query(PaperAnalysis)
            .filter(PaperAnalysis.paper_uid == paper_uid)
            .order_by(PaperAnalysis.created_at.desc())
            .first()
        )

    def save_feedback(self, paper_uid: str, action: str, note: str | None = None) -> None:
        self.session.add(PaperFeedback(id=uuid.uuid4().hex, paper_uid=paper_uid, action=action, note=note))
        self.session.commit()

    def get_feedback_actions(self, action: str) -> list[str]:
        rows = self.session.query(PaperFeedback).filter(PaperFeedback.action == action).all()
        return [r.paper_uid for r in rows]

    def latest_feedback_map(self) -> dict[str, str]:
        rows = self.session.query(PaperFeedback).order_by(PaperFeedback.created_at.desc()).all()
        result: dict[str, str] = {}
        for row in rows:
            if row.paper_uid not in result:
                result[row.paper_uid] = row.action
        return result

    def create_recommendation_run(self, query_context: dict, strategy_weights: dict) -> str:
        run_id = uuid.uuid4().hex
        self.session.add(
            RecommendationRun(
                id=run_id,
                query_context_json=json.dumps(query_context, ensure_ascii=False),
                strategy_weights_json=json.dumps(strategy_weights, ensure_ascii=False),
            )
        )
        self.session.commit()
        return run_id

    def save_recommendation_items(self, run_id: str, items: list[dict]) -> None:
        for item in items:
            self.session.add(
                RecommendationItem(
                    id=uuid.uuid4().hex,
                    run_id=run_id,
                    paper_uid=item["paper_uid"],
                    score=item["score"],
                    rank=item["rank"],
                    strategy_breakdown_json=json.dumps(item["strategy_breakdown"], ensure_ascii=False),
                    reasons_json=json.dumps(item["reasons"], ensure_ascii=False),
                )
            )
            paper = self.session.query(Paper).filter(Paper.paper_uid == item["paper_uid"]).first()
            if paper is not None:
                paper.recommended_count = int(paper.recommended_count or 0) + 1
        self.session.commit()

    def create_job(self, job_type: str, payload: dict, trace_id: str) -> Job:
        job = Job(id=uuid.uuid4().hex, job_type=job_type, payload_json=json.dumps(payload), trace_id=trace_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def update_job(self, job_id: str, **kwargs) -> Job | None:
        job = self.session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self.session.query(Job).filter(Job.id == job_id).first()

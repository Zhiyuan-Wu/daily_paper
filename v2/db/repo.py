from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from v2.db.models import (
    AppProfile,
    Job,
    Paper,
    PaperAnalysis,
    PaperArtifact,
    PaperFeedback,
    PaperSourceLink,
    RecommendationItem,
    RecommendationRun,
    ServiceCallLog,
)


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

    def upsert_paper(self, data: dict, preserve_identity: bool = False) -> Paper:
        paper_uid = data["paper_uid"]
        paper = self.session.query(Paper).filter(Paper.paper_uid == paper_uid).first()
        if paper is None:
            paper = Paper(**data)
            self.session.add(paper)
        else:
            locked_fields = {"paper_uid"}
            if preserve_identity:
                locked_fields.update({"source", "external_id"})
            for key, value in data.items():
                if key in locked_fields:
                    continue
                setattr(paper, key, value)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def add_source_link(self, paper_uid: str, source: str, external_id: str, doi: Optional[str], source_url: Optional[str]) -> None:
        link_id = uuid.uuid4().hex
        existing = self.session.query(PaperSourceLink).filter(
            PaperSourceLink.source == source,
            PaperSourceLink.external_id == external_id,
        ).first()
        if existing:
            if existing.paper_uid != paper_uid:
                existing.paper_uid = paper_uid
                existing.doi = doi
                existing.source_url = source_url
                self.session.commit()
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

    def resolve_paper_uid(self, source: str, external_id: str) -> Optional[str]:
        row = (
            self.session.query(PaperSourceLink)
            .filter(
                PaperSourceLink.source == source,
                PaperSourceLink.external_id == external_id,
            )
            .first()
        )
        return row.paper_uid if row else None

    def upsert_artifact(self, payload: dict) -> PaperArtifact:
        item = (
            self.session.query(PaperArtifact)
            .filter(
                PaperArtifact.paper_uid == payload["paper_uid"],
                PaperArtifact.artifact_type == payload["artifact_type"],
                PaperArtifact.parser_method == payload.get("parser_method"),
                PaperArtifact.parser_version == payload.get("parser_version"),
                PaperArtifact.evicted == 0,
            )
            .order_by(PaperArtifact.created_at.desc())
            .first()
        )
        if item is None:
            item = PaperArtifact(id=uuid.uuid4().hex, **payload)
            self.session.add(item)
        else:
            for key, value in payload.items():
                setattr(item, key, value)
            item.last_accessed_at = datetime.now()
        self.session.commit()
        self.session.refresh(item)
        return item

    def get_paper(self, paper_uid: str) -> Optional[Paper]:
        return self.session.query(Paper).filter(Paper.paper_uid == paper_uid).first()

    def list_papers(self, paper_uids: Optional[list[str]] = None) -> list[Paper]:
        q = self.session.query(Paper)
        if paper_uids:
            q = q.filter(Paper.paper_uid.in_(paper_uids))
        return q.all()

    def get_artifact(self, paper_uid: str, artifact_type: str, parser_method: Optional[str] = None) -> Optional[PaperArtifact]:
        q = self.session.query(PaperArtifact).filter(
            PaperArtifact.paper_uid == paper_uid,
            PaperArtifact.artifact_type == artifact_type,
            PaperArtifact.evicted == 0,
        )
        if parser_method:
            q = q.filter(PaperArtifact.parser_method == parser_method)
        return q.order_by(PaperArtifact.last_accessed_at.desc(), PaperArtifact.created_at.desc()).first()

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

    def latest_analysis(self, paper_uid: str) -> Optional[PaperAnalysis]:
        return (
            self.session.query(PaperAnalysis)
            .filter(PaperAnalysis.paper_uid == paper_uid)
            .order_by(PaperAnalysis.created_at.desc())
            .first()
        )

    def save_feedback(self, paper_uid: str, action: str, note: Optional[str] = None) -> None:
        self.session.add(PaperFeedback(id=uuid.uuid4().hex, paper_uid=paper_uid, action=action, note=note))
        self.session.commit()

    def get_feedback_actions(self, action: str) -> list[str]:
        rows = self.session.query(PaperFeedback).filter(PaperFeedback.action == action).all()
        return [r.paper_uid for r in rows]

    def latest_feedback_map(self, paper_uids: Optional[list[str]] = None) -> dict[str, str]:
        base = self.session.query(PaperFeedback.paper_uid, func.max(PaperFeedback.created_at).label("max_created"))
        if paper_uids:
            base = base.filter(PaperFeedback.paper_uid.in_(paper_uids))
        latest_subq = base.group_by(PaperFeedback.paper_uid).subquery()
        rows = (
            self.session.query(PaperFeedback)
            .join(
                latest_subq,
                and_(
                    PaperFeedback.paper_uid == latest_subq.c.paper_uid,
                    PaperFeedback.created_at == latest_subq.c.max_created,
                ),
            )
            .all()
        )
        return {row.paper_uid: row.action for row in rows}

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
        job = Job(id=uuid.uuid4().hex, job_type=job_type, payload_json=json.dumps(payload, ensure_ascii=False), trace_id=trace_id)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def update_job(self, job_id: str, **kwargs) -> Optional[Job]:
        job = self.session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.session.query(Job).filter(Job.id == job_id).first()

    def list_jobs(self, job_types: list[str], statuses: list[str]) -> list[Job]:
        return (
            self.session.query(Job)
            .filter(Job.job_type.in_(job_types), Job.status.in_(statuses))
            .order_by(Job.created_at.asc())
            .all()
        )

    def log_service_call(
        self,
        trace_id: str,
        service_name: str,
        endpoint: str,
        request_summary: dict,
        response_summary: dict,
        status_code: int,
        duration_ms: int,
        error_code: Optional[str] = None,
    ) -> None:
        self.session.add(
            ServiceCallLog(
                id=uuid.uuid4().hex,
                trace_id=trace_id,
                service_name=service_name,
                endpoint=endpoint,
                request_summary_json=json.dumps(request_summary, ensure_ascii=False),
                response_summary_json=json.dumps(response_summary, ensure_ascii=False),
                status_code=status_code,
                duration_ms=duration_ms,
                error_code=error_code,
            )
        )
        self.session.commit()

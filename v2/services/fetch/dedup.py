from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from v2.db.models import Paper
from v2.services.fetch.plugins import SourcePaper


def _norm(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def find_existing_paper(session: Session, incoming: SourcePaper) -> Optional[Paper]:
    if incoming.doi:
        existing_by_doi = session.query(Paper).filter(Paper.doi == incoming.doi).first()
        if existing_by_doi:
            return existing_by_doi

    first_author = _norm(incoming.authors[0] if incoming.authors else "")
    incoming_year = incoming.published_at.year if incoming.published_at else None
    incoming_title = _norm(incoming.title)

    candidates = session.query(Paper).filter(func.lower(Paper.title) == incoming_title)
    if incoming_year is not None:
        start = datetime(incoming_year, 1, 1)
        end = datetime(incoming_year + 1, 1, 1)
        candidates = candidates.filter(Paper.published_at >= start, Paper.published_at < end)
    else:
        candidates = candidates.filter(Paper.published_at.is_(None))

    for paper in candidates.all():
        existing_year = paper.published_at.year if isinstance(paper.published_at, datetime) and paper.published_at else None
        if existing_year != incoming_year:
            continue
        if _norm(paper.title) != incoming_title:
            continue

        try:
            authors = json.loads(paper.authors_json or "[]")
        except Exception:
            authors = []
        existing_first_author = _norm(authors[0] if authors else "")
        if existing_first_author == first_author:
            return paper

    return None

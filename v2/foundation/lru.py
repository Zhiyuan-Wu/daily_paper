from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from v2.db.models import PaperArtifact


def apply_pdf_lru(session: Session, max_bytes: int, max_count: int) -> int:
    raw_rows = (
        session.query(PaperArtifact)
        .filter(PaperArtifact.artifact_type == "pdf", PaperArtifact.evicted == 0)
        .order_by(PaperArtifact.last_accessed_at.asc())
        .all()
    )

    latest_by_path: dict[str, PaperArtifact] = {}
    def _dt(row: PaperArtifact):
        return row.last_accessed_at or row.created_at

    for row in raw_rows:
        current = latest_by_path.get(row.path)
        if current is None or _dt(row) > _dt(current):
            latest_by_path[row.path] = row
    rows = sorted(latest_by_path.values(), key=_dt)

    total_bytes = sum(r.size_bytes or 0 for r in rows)
    total_count = len(rows)
    evicted = 0

    idx = 0
    while (total_bytes > max_bytes or total_count > max_count) and idx < len(rows):
        row = rows[idx]
        idx += 1

        path = Path(row.path)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                # Keep metadata and continue.
                pass

        for linked in raw_rows:
            if linked.path == row.path and linked.evicted == 0:
                linked.evicted = 1
        total_bytes -= row.size_bytes or 0
        total_count -= 1
        evicted += 1

    session.commit()
    return evicted

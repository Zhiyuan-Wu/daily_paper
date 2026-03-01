from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from v2.db.models import PaperArtifact


def apply_pdf_lru(session: Session, max_bytes: int, max_count: int) -> int:
    rows = (
        session.query(PaperArtifact)
        .filter(PaperArtifact.artifact_type == "pdf", PaperArtifact.evicted == 0)
        .order_by(PaperArtifact.last_accessed_at.asc())
        .all()
    )

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

        row.evicted = 1
        total_bytes -= row.size_bytes or 0
        total_count -= 1
        evicted += 1

    session.commit()
    return evicted

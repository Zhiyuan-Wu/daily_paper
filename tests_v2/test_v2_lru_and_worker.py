from __future__ import annotations

import json
from pathlib import Path

from v2.db.models import AppProfile, Paper, PaperArtifact, init_db
from v2.foundation.lru import apply_pdf_lru
from v2.worker.runner import run_cleanup_retry_queue


def test_pdf_lru_dual_threshold(tmp_path: Path):
    session = init_db(f"sqlite:///{tmp_path / 'lru.db'}")
    session.add(AppProfile(id=1, pdf_lru_max_bytes=100, pdf_lru_max_count=2))
    session.add(Paper(paper_uid="p1", source="s", external_id="1", title="t1", authors_json="[]"))
    session.add(Paper(paper_uid="p2", source="s", external_id="2", title="t2", authors_json="[]"))
    session.add(Paper(paper_uid="p3", source="s", external_id="3", title="t3", authors_json="[]"))
    session.commit()

    files = []
    for i, uid in enumerate(["p1", "p2", "p3"], start=1):
        p = tmp_path / f"{uid}.pdf"
        p.write_bytes(b"x" * 60)
        files.append(p)
        session.add(
            PaperArtifact(
                id=f"a{i}",
                paper_uid=uid,
                artifact_type="pdf",
                path=str(p),
                file_hash=f"h{i}",
                size_bytes=60,
            )
        )
    session.commit()

    evicted = apply_pdf_lru(session, max_bytes=100, max_count=2)
    assert evicted >= 1


def test_cleanup_retry_runner(tmp_path: Path):
    queue = tmp_path / "cleanup_retry_queue.jsonl"
    d1 = tmp_path / "run1"
    d2 = tmp_path / "run2"
    d1.mkdir()
    d2.mkdir()
    queue.write_text(
        "\n".join(
            [
                json.dumps({"task_id": "t1", "workdir": str(d1)}),
                json.dumps({"task_id": "t2", "workdir": str(d2)}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cleaned = run_cleanup_retry_queue(queue)
    assert cleaned == 2
    assert not d1.exists()
    assert not d2.exists()
    assert queue.read_text(encoding="utf-8") == ""

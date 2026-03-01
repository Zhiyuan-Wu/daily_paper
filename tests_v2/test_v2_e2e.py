from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from v2.contracts.fetch import DownloadRequest
from v2.services.fetch.plugins import SourcePaper


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'v2.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ["V2_RESEARCH_FAKE"] = "1"

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod


def test_v2_end_to_end(tmp_path: Path, monkeypatch):
    mod = _load_app(tmp_path)

    paper = SourcePaper(
        source="openalex",
        external_id="WTEST-E2E-1",
        title="E2E Test Paper for V2",
        authors=["Tester"],
        abstract="This paper studies e2e delivery.",
        published_at=None,
        url="https://openalex.org/WTEST-E2E-1",
        pdf_url="mock://pdf",
        doi="10.0000/e2e-v2",
        pdf_unavailable=False,
    )

    def fake_search(*args, **kwargs):
        return [paper]

    pdf_bytes = _make_pdf_bytes("This is a test PDF for parsing and downstream analysis.")

    def fake_download(req: DownloadRequest):
        paper_uid = mod.fetch_service.artifacts.paper_uid(req.source, req.external_id)
        info = mod.fetch_service.artifacts.write_bytes(mod.fetch_service.artifacts.pdf_path(paper_uid), pdf_bytes)
        mod.repo.upsert_artifact(
            artifact_id="pdf-artifact-e2e",
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "pdf",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": None,
                "parser_version": None,
            },
        )
        return {"paper_uid": paper_uid, "pdf_path": str(info.path), "deduplicated": False, "pdf_unavailable": False}

    monkeypatch.setattr(mod.fetch_service, "search", fake_search)
    monkeypatch.setattr(mod.fetch_service, "download", fake_download)
    mod.report_service.fetch_service = mod.fetch_service

    client = TestClient(mod.app)

    # 1) search
    resp = client.post(
        "/api/v1/papers/search",
        json={"sources": ["openalex"], "keywords": ["agent"], "page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    paper_uid = items[0]["paper_uid"]

    resp = client.get("/api/v1/papers", params={"page": 1, "page_size": 20})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert any(row["paper_uid"] == paper_uid for row in resp.json()["items"])

    # 2) import/download
    resp = client.post(
        "/api/v1/papers/import",
        json={"source": "openalex", "external_id": "WTEST-E2E-1", "pdf_url": "mock://pdf"},
    )
    assert resp.status_code == 200

    # 3) parse
    resp = client.post(
        f"/api/v1/papers/{paper_uid}/parse",
        json={"paper_uid": paper_uid, "method": "simple", "force_reparse": False},
    )
    assert resp.status_code == 200
    parse_out = resp.json()["result"]
    assert parse_out["char_count"] > 10

    pdf_resp = client.get(f"/api/v1/papers/{paper_uid}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

    text = Path(parse_out["text_path"]).read_text(encoding="utf-8")

    # 4) analyze
    resp = client.post(
        f"/api/v1/papers/{paper_uid}/analyze",
        json={
            "paper_uid": paper_uid,
            "title": "E2E Test Paper for V2",
            "abstract": "This paper studies e2e delivery.",
            "full_text": text,
        },
    )
    assert resp.status_code == 200

    detail_resp = client.get(f"/api/v1/papers/{paper_uid}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["paper_uid"] == paper_uid
    assert detail_resp.json()["analysis"] is not None

    # 5) feedback + recommend
    resp = client.post("/api/v1/interactions", json={"paper_uid": paper_uid, "action": "like"})
    assert resp.status_code == 200
    resp = client.post("/api/v1/recommendations/generate", json={"paper_uids": [paper_uid], "top_k": 5})
    assert resp.status_code == 200
    rec_items = resp.json()["result"]["items"]
    assert rec_items and rec_items[0]["paper_uid"] == paper_uid

    # 6) research task
    resp = client.post("/api/v1/research/tasks", json={"topic": "Test topic", "constraints": {"lang": "zh"}})
    assert resp.status_code == 200
    task_id = resp.json()["result"]["task_id"]

    resp = client.get(f"/api/v1/research/tasks/{task_id}/result")
    assert resp.status_code == 200
    assert "report_md" in resp.json()
    assert isinstance(resp.json()["sources"], list)

    resp = client.get("/api/v1/research/tasks")
    assert resp.status_code == 200
    assert any(row["task_id"] == task_id for row in resp.json()["items"])

    # 7) daily report
    resp = client.post(
        "/api/v1/reports/daily/generate",
        json={"report_date": "2026-03-01", "sources": ["openalex"], "keywords": ["test"], "top_k": 1},
    )
    assert resp.status_code == 200
    report_id = resp.json()["result"]["report_id"]

    resp = client.get(f"/api/v1/reports/daily/{report_id}")
    assert resp.status_code == 200
    assert resp.json()["paper_uids"]

    by_date_resp = client.get("/api/v1/reports/daily/by-date/2026-03-01")
    assert by_date_resp.status_code == 200
    assert by_date_resp.json()["report_id"] == report_id

    # 8) settings immediate effect
    resp = client.put(
        "/api/v1/settings",
        json={
            "ocr_timeout_seconds": 99,
            "daily_report_sources": ["openalex"],
            "daily_report_keywords": ["agent", "benchmark"],
            "daily_report_arxiv_categories": ["cs.AI"],
            "daily_report_top_k": 3,
            "daily_report_window_days": 2,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ocr_timeout_seconds"] == 99
    assert resp.json()["daily_report_top_k"] == 3
    assert resp.json()["daily_report_window_days"] == 2

    # 9) dashboard status
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["paper_count"] >= 1
    assert payload["daily_report_count"] >= 1
    assert payload["research_task_count"] >= 1

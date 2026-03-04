from __future__ import annotations

import importlib
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'async_report.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ["V2_RESEARCH_FAKE"] = "1"

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod, TestClient(mod.app)


def test_daily_report_generate_async_should_create_job_and_complete(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)

    def fake_runner(job_id: str, payload: dict, trace_id: str):
        session = mod.SessionLocal()
        repo = mod.Repo(session)
        repo.update_job(job_id, status="completed", progress=100, result_ref="mock_report_id")
        session.close()

    monkeypatch.setattr(mod, "_run_daily_report_job_async", fake_runner)

    resp = client.post(
        "/api/v1/reports/daily/generate-async",
        json={
            "report_date": "2026-03-01",
            "sources": ["arxiv", "huggingface"],
            "keywords": [],
            "arxiv_categories": ["cs.AI"],
            "window_days": 7,
            "top_k": 5,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "pending"
    job_id = payload["job_id"]

    status = "pending"
    result_ref = None
    for _ in range(20):
        job_resp = client.get(f"/api/v1/tasks/{job_id}")
        assert job_resp.status_code == 200
        status = job_resp.json()["status"]
        result_ref = job_resp.json()["result_ref"]
        if status == "completed":
            break
        time.sleep(0.05)

    assert status == "completed"
    assert result_ref == "mock_report_id"

from __future__ import annotations

import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'dashboard.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ["V2_RESEARCH_FAKE"] = "1"

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod, TestClient(mod.app)


def test_frontend_dashboard_related_endpoints(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)
    monkeypatch.setattr(mod, "_check_http_health", lambda _url: True)

    settings_resp = client.get("/api/v1/settings")
    assert settings_resp.status_code == 200
    payload = settings_resp.json()
    assert "daily_report_sources" in payload
    assert "daily_report_keywords" in payload
    assert "daily_report_top_k" in payload
    assert "daily_report_window_days" in payload
    assert payload["daily_report_sources"] == ["arxiv", "huggingface"]
    assert payload["daily_report_window_days"] == 7
    assert "cs.AI" in payload["daily_report_arxiv_categories"]

    update_resp = client.put(
        "/api/v1/settings",
        json={
            "daily_report_sources": ["openalex"],
            "daily_report_keywords": ["agent"],
            "daily_report_arxiv_categories": ["cs.AI"],
            "daily_report_top_k": 7,
            "daily_report_window_days": 3,
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["daily_report_top_k"] == 7
    assert update_resp.json()["daily_report_window_days"] == 3

    papers_resp = client.get("/api/v1/papers")
    assert papers_resp.status_code == 200
    assert papers_resp.json()["items"] == []
    assert papers_resp.json()["total"] == 0

    report_resp = client.get("/api/v1/reports/daily/by-date/2026-03-01")
    assert report_resp.status_code == 404
    assert report_resp.json()["detail"]["code"] == "REPORT_NOT_FOUND"

    tasks_resp = client.get("/api/v1/research/tasks")
    assert tasks_resp.status_code == 200
    assert tasks_resp.json()["items"] == []

    status_resp = client.get("/api/v1/system/status")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["paper_count"] == 0
    assert status_payload["daily_report_count"] == 0
    assert status_payload["research_task_count"] == 0
    assert status_payload["service_health"]["database"] is True

    monkeypatch.setattr(
        mod.fetch_service,
        "validate_sources",
        lambda **kwargs: {
            "arxiv": {"ok": True, "reason": "", "count": 3, "sample_external_id": "1234.5678"},
            "huggingface": {"ok": False, "reason": "NO_REAL_DATA", "count": 0},
            "openalex": {"ok": True, "reason": "", "count": 2, "sample_external_id": "W123"},
        },
    )
    source_resp = client.get("/api/v1/sources/availability")
    assert source_resp.status_code == 200
    source_payload = source_resp.json()
    assert source_payload["overall_ok"] is False
    assert source_payload["sources"]["huggingface"]["ok"] is False

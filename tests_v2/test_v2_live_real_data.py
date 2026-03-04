from __future__ import annotations

import importlib
import os
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'live_v2.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ.pop("V2_RESEARCH_FAKE", None)
    os.environ.setdefault("V2_RESEARCH_TIMEOUT_MINUTES", "4")

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod, TestClient(mod.app)


def _first_parsable_paper(client: TestClient, items: list[dict]) -> tuple[dict, str, str] | None:
    for item in items:
        if not item.get("pdf_url"):
            continue

        import_resp = client.post(
            "/api/v1/papers/import",
            json={
                "source": item["source"],
                "external_id": item["external_id"],
                "pdf_url": item.get("pdf_url"),
            },
        )
        if import_resp.status_code != 200:
            continue

        import_out = import_resp.json()["result"]
        if import_out.get("pdf_unavailable"):
            continue

        paper_uid = import_out["paper_uid"]
        parse_resp = client.post(
            f"/api/v1/papers/{paper_uid}/parse",
            json={"paper_uid": paper_uid, "method": "simple", "force_reparse": False},
        )
        if parse_resp.status_code != 200:
            continue

        text_path = parse_resp.json()["result"]["text_path"]
        return item, paper_uid, text_path
    return None


@pytest.mark.live
@pytest.mark.integration
def test_live_openalex_fetch_parse_analyze_recommend_daily_report(tmp_path: Path):
    if os.getenv("V2_RUN_LIVE_TESTS") != "1":
        pytest.skip("set V2_RUN_LIVE_TESTS=1 to run real-data integration tests")

    _, client = _load_app(tmp_path)

    search_resp = client.post(
        "/api/v1/papers/search",
        json={"sources": ["openalex"], "keywords": ["arxiv", "transformer"], "page": 1, "page_size": 30},
    )
    assert search_resp.status_code == 200
    items = search_resp.json()["items"]
    assert items

    parsed = _first_parsable_paper(client, items)
    assert parsed is not None, "Could not find any parsable PDF from live OpenAlex results"
    item, paper_uid, text_path = parsed

    full_text = Path(text_path).read_text(encoding="utf-8")
    assert len(full_text) > 100

    analyze_resp = client.post(
        f"/api/v1/papers/{paper_uid}/analyze",
        json={
            "paper_uid": paper_uid,
            "title": item["title"],
            "abstract": item.get("abstract"),
            "full_text": full_text[:30000],
        },
    )
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["result"]["result"]["tldr"]

    feedback_resp = client.post("/api/v1/interactions", json={"paper_uid": paper_uid, "action": "like"})
    assert feedback_resp.status_code == 200

    recommend_resp = client.post(
        "/api/v1/recommendations/generate",
        json={"paper_uids": [paper_uid], "top_k": 1},
    )
    assert recommend_resp.status_code == 200
    rec_items = recommend_resp.json()["result"]["items"]
    assert rec_items
    assert rec_items[0]["paper_uid"] == paper_uid

    daily_scenarios = [
        ["arxiv", "transformer"],
        ["llm", "agent"],
        ["retrieval", "generation"],
    ]
    daily_ok = False
    for keywords in daily_scenarios:
        daily_resp = client.post(
            "/api/v1/reports/daily/generate",
            json={
                "report_date": "2026-03-01",
                "sources": ["openalex"],
                "keywords": keywords,
                "top_k": 1,
            },
        )
        if daily_resp.status_code != 200:
            continue

        report_id = daily_resp.json()["result"]["report_id"]
        get_report_resp = client.get(f"/api/v1/reports/daily/{report_id}")
        assert get_report_resp.status_code == 200
        assert get_report_resp.json()["paper_uids"]
        daily_ok = True
        break

    assert daily_ok, "Live daily report generation failed for all keyword scenarios"


@pytest.mark.live
@pytest.mark.live_research
@pytest.mark.integration
@pytest.mark.slow
def test_live_research_task_with_claude_cli(tmp_path: Path):
    if os.getenv("V2_RUN_LIVE_RESEARCH") != "1":
        pytest.skip("set V2_RUN_LIVE_RESEARCH=1 to run live research test")
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not found")

    _, client = _load_app(tmp_path)

    create_resp = client.post(
        "/api/v1/research/tasks",
        json={
            "topic": "Agentic AI benchmark trends in 2025",
            "constraints": {"lang": "en", "depth": "brief"},
        },
    )
    assert create_resp.status_code == 200

    result = create_resp.json()["result"]
    task_id = result["task_id"]
    assert task_id

    for _ in range(120):
        status_resp = client.get(f"/api/v1/research/tasks/{task_id}")
        assert status_resp.status_code == 200
        status = status_resp.json()["status"]
        if status == "completed":
            break
        if status == "failed":
            assert False, status_resp.json()
        time.sleep(1)

    result_resp = client.get(f"/api/v1/research/tasks/{task_id}/result")
    assert result_resp.status_code == 200
    payload = result_resp.json()
    assert payload["report_md"].strip()
    assert isinstance(payload["sources"], list)

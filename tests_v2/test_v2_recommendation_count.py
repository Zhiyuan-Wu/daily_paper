from __future__ import annotations

import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'recommend_count.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ["V2_RESEARCH_FAKE"] = "1"

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod, TestClient(mod.app)


def test_recommend_should_downrank_frequently_recommended_papers(tmp_path: Path):
    mod, client = _load_app(tmp_path)

    uid_new = mod.fetch_service.artifacts.paper_uid("arxiv", "A-NEW-1")
    uid_old = mod.fetch_service.artifacts.paper_uid("arxiv", "A-OLD-1")

    mod.repo.upsert_paper(
        {
            "paper_uid": uid_new,
            "source": "arxiv",
            "external_id": "A-NEW-1",
            "doi": None,
            "title": "Novel Paper",
            "authors_json": "[]",
            "abstract": "same abstract",
            "published_at": None,
            "source_url": None,
            "pdf_url": None,
            "pdf_unavailable": True,
            "recommended_count": 0,
        }
    )
    mod.repo.upsert_paper(
        {
            "paper_uid": uid_old,
            "source": "arxiv",
            "external_id": "A-OLD-1",
            "doi": None,
            "title": "Old Frequently Recommended Paper",
            "authors_json": "[]",
            "abstract": "same abstract",
            "published_at": None,
            "source_url": None,
            "pdf_url": None,
            "pdf_unavailable": True,
            "recommended_count": 10,
        }
    )

    settings_resp = client.put(
        "/api/v1/settings",
        json={
            "recommend_strategy_weights": {
                "keyword_semantic": 0.0,
                "interested_semantic": 0.0,
                "repetition_penalty": 0.0,
                "llm_theme": 0.0,
                "recommended_inverse": 1.0,
            }
        },
    )
    assert settings_resp.status_code == 200

    rec_resp = client.post(
        "/api/v1/recommendations/generate",
        json={"paper_uids": [uid_old, uid_new], "top_k": 2},
    )
    assert rec_resp.status_code == 200
    items = rec_resp.json()["result"]["items"]
    assert items[0]["paper_uid"] == uid_new
    assert items[1]["paper_uid"] == uid_old

    # recommended_count should be incremented whenever a paper is recommended.
    new_paper = mod.repo.get_paper(uid_new)
    old_paper = mod.repo.get_paper(uid_old)
    assert new_paper is not None and new_paper.recommended_count == 1
    assert old_paper is not None and old_paper.recommended_count == 11

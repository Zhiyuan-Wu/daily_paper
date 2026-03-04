from __future__ import annotations

import importlib
import os
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from v2.contracts.fetch import DownloadRequest
from v2.foundation.artifact_manager import ArtifactManager
from v2.services.fetch.plugins import SourcePaper


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _load_app(tmp_path: Path):
    os.environ["V2_DATABASE_URL"] = f"sqlite:///{tmp_path / 'lazy.db'}"
    os.environ["V2_ARTIFACT_ROOT"] = str(tmp_path / "artifacts")
    os.environ["V2_RESEARCH_ROOT"] = str(tmp_path / "research")
    os.environ["V2_RESEARCH_FAKE"] = "1"

    mod = importlib.import_module("v2.api.app")
    mod = importlib.reload(mod)
    return mod, TestClient(mod.app)


def test_daily_report_should_not_fail_when_lazy_enrichment_fails(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)

    paper = SourcePaper(
        source="openalex",
        external_id="WTEST-LAZY-REPORT-1",
        title="Lazy Report Metadata Only",
        authors=["Tester"],
        abstract="metadata-only paper",
        published_at=None,
        url="https://openalex.org/WTEST-LAZY-REPORT-1",
        pdf_url=None,
        doi="10.0000/lazy-report",
        pdf_unavailable=True,
    )

    monkeypatch.setattr(mod.FetchService, "search", lambda self, *args, **kwargs: [paper])

    resp = client.post(
        "/api/v1/reports/daily/generate",
        json={
            "report_date": "2026-03-01",
            "sources": ["openalex"],
            "keywords": ["lazy"],
            "top_k": 1,
        },
    )
    assert resp.status_code == 200
    report_id = resp.json()["result"]["report_id"]

    get_resp = client.get(f"/api/v1/reports/daily/{report_id}")
    assert get_resp.status_code == 200
    assert "enrich=pdf_unavailable" in get_resp.json()["summary_md"]


def test_pdf_parse_analyze_should_lazy_load_when_artifacts_missing(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)
    pdf_bytes = _make_pdf_bytes("lazy load test pdf content")

    paper = SourcePaper(
        source="openalex",
        external_id="WTEST-LAZY-CHAIN-1",
        title="Lazy Chain Paper",
        authors=["Tester"],
        abstract="lazy chain abstract",
        published_at=None,
        url="https://openalex.org/WTEST-LAZY-CHAIN-1",
        pdf_url="mock://pdf-lazy",
        doi="10.0000/lazy-chain",
        pdf_unavailable=False,
    )
    monkeypatch.setattr(mod.FetchService, "search", lambda self, *args, **kwargs: [paper])

    call_count = {"download": 0}

    def fake_download(self, req: DownloadRequest):
        call_count["download"] += 1
        paper_uid = self.artifacts.paper_uid(req.source, req.external_id)
        info = self.artifacts.write_bytes(self.artifacts.pdf_path(paper_uid), pdf_bytes)
        self.repo.upsert_artifact(
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "pdf",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": None,
                "parser_version": None,
            }
        )
        return {"paper_uid": paper_uid, "pdf_path": str(info.path), "deduplicated": False, "pdf_unavailable": False}

    monkeypatch.setattr(mod.FetchService, "download", fake_download)

    search_resp = client.post(
        "/api/v1/papers/search",
        json={"sources": ["openalex"], "keywords": ["lazy"], "page": 1, "page_size": 5},
    )
    assert search_resp.status_code == 200
    paper_uid = search_resp.json()["items"][0]["paper_uid"]

    pdf_resp = client.get(f"/api/v1/papers/{paper_uid}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")
    assert call_count["download"] == 1

    parse_resp = client.post(
        f"/api/v1/papers/{paper_uid}/parse",
        json={"paper_uid": paper_uid, "method": "simple", "force_reparse": False},
    )
    assert parse_resp.status_code == 200
    assert parse_resp.json()["result"]["char_count"] > 1
    # parse path should reuse local PDF; no second download needed.
    assert call_count["download"] == 1

    analyze_resp = client.post(
        f"/api/v1/papers/{paper_uid}/analyze",
        json={"paper_uid": paper_uid},
    )
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["result"]["analysis_id"]


def test_paper_detail_should_skip_lazy_analyze_when_pdf_marked_unavailable(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)
    paper_uid = ArtifactManager.paper_uid("openalex", "WTEST-PDF-UNAVAILABLE-1")
    session = mod.SessionLocal()
    repo = mod.Repo(session)
    repo.upsert_paper(
        {
            "paper_uid": paper_uid,
            "source": "openalex",
            "external_id": "WTEST-PDF-UNAVAILABLE-1",
            "doi": None,
            "title": "No PDF Paper",
            "authors_json": "[]",
            "abstract": "no pdf",
            "published_at": None,
            "source_url": "https://openalex.org/WTEST-PDF-UNAVAILABLE-1",
            "pdf_url": None,
            "pdf_unavailable": True,
        }
    )
    session.close()

    def fail_if_called(_paper_uid: str):
        raise AssertionError("_ensure_analysis_for_paper_uid should not be called for pdf_unavailable paper")

    monkeypatch.setattr(mod, "_ensure_analysis_for_paper_uid", fail_if_called)

    detail_resp = client.get(f"/api/v1/papers/{paper_uid}")
    assert detail_resp.status_code == 200
    payload = detail_resp.json()
    assert payload["analysis"] is None
    assert payload["analysis_status"] == "pdf_unavailable"

    list_resp = client.get("/api/v1/papers")
    assert list_resp.status_code == 200
    item = next(x for x in list_resp.json()["items"] if x["paper_uid"] == paper_uid)
    assert item["has_pdf"] is False
    assert item["pdf_url"] == f"/api/v1/papers/{paper_uid}/pdf"


def test_parse_endpoint_should_ensure_pdf_before_parse_service(tmp_path: Path, monkeypatch):
    mod, client = _load_app(tmp_path)
    paper_uid = ArtifactManager.paper_uid("openalex", "WTEST-PARSE-ENSURE-PDF-1")
    session = mod.SessionLocal()
    repo = mod.Repo(session)
    repo.upsert_paper(
        {
            "paper_uid": paper_uid,
            "source": "openalex",
            "external_id": "WTEST-PARSE-ENSURE-PDF-1",
            "doi": None,
            "title": "Need Download Before Parse",
            "authors_json": "[]",
            "abstract": "parse chain",
            "published_at": None,
            "source_url": "https://openalex.org/WTEST-PARSE-ENSURE-PDF-1",
            "pdf_url": "mock://parse-ensure-pdf",
            "pdf_unavailable": False,
        }
    )
    session.close()

    pdf_bytes = _make_pdf_bytes("parse ensure pdf")
    calls = {"download": 0, "parse": 0}

    def fake_download(self, req: DownloadRequest):
        calls["download"] += 1
        info = self.artifacts.write_bytes(self.artifacts.pdf_path(paper_uid), pdf_bytes)
        self.repo.upsert_artifact(
            payload={
                "paper_uid": paper_uid,
                "artifact_type": "pdf",
                "path": str(info.path),
                "file_hash": info.file_hash,
                "size_bytes": info.size_bytes,
                "parser_method": None,
                "parser_version": None,
            }
        )
        return {"paper_uid": paper_uid, "pdf_path": str(info.path), "deduplicated": False, "pdf_unavailable": False}

    text_path = tmp_path / "parse_ensure_text.txt"
    text_path.write_text("parsed text content", encoding="utf-8")

    def fake_parse(self, paper_uid: str, method: str, force_reparse: bool):
        calls["parse"] += 1
        session = mod.SessionLocal()
        repo = mod.Repo(session)
        pdf_artifact = repo.get_artifact(paper_uid, "pdf")
        session.close()
        assert pdf_artifact is not None
        assert Path(pdf_artifact.path).exists()
        return {
            "paper_uid": paper_uid,
            "method": method,
            "text_path": str(text_path),
            "cached": False,
            "char_count": 18,
        }

    monkeypatch.setattr(mod.FetchService, "download", fake_download)
    monkeypatch.setattr(mod.ParseService, "parse", fake_parse)

    resp = client.post(
        f"/api/v1/papers/{paper_uid}/parse",
        json={"paper_uid": paper_uid, "method": "simple", "force_reparse": False},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["char_count"] > 0
    assert calls["download"] == 1
    assert calls["parse"] == 1

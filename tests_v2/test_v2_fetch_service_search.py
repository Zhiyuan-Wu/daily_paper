from __future__ import annotations

from datetime import datetime
from pathlib import Path

from v2.config import V2Config
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.fetch.plugins import SourcePaper
from v2.services.fetch.service import FetchService


def test_search_should_tolerate_partial_source_failure(tmp_path: Path):
    cfg = V2Config(
        database_url=f"sqlite:///{tmp_path / 'fetch_search.db'}",
        artifact_root=tmp_path / "artifacts",
        research_root=tmp_path / "research",
    )
    session = init_db(cfg.database_url)
    repo = Repo(session)
    service = FetchService(repo, cfg)

    class _OkPlugin:
        source_name = "ok"

        def search(self, keywords, start_date, end_date, page, page_size, arxiv_categories=None):
            return [
                SourcePaper(
                    source="ok",
                    external_id="ok-1",
                    title="ok paper",
                    authors=["tester"],
                    abstract="ok",
                    published_at=datetime.now(),
                    url="https://example.com/ok-1",
                    pdf_url=None,
                    doi=None,
                    pdf_unavailable=True,
                )
            ]

    class _FailPlugin:
        source_name = "fail"

        def search(self, keywords, start_date, end_date, page, page_size, arxiv_categories=None):
            raise RuntimeError("upstream down")

    service.plugins = {"ok": _OkPlugin(), "fail": _FailPlugin()}

    rows = service.search(
        sources=["ok", "fail"],
        keywords=[],
        start_date=None,
        end_date=None,
        page=1,
        page_size=10,
    )
    assert len(rows) == 1
    assert rows[0].source == "ok"


def test_search_should_fail_when_all_sources_failed(tmp_path: Path):
    cfg = V2Config(
        database_url=f"sqlite:///{tmp_path / 'fetch_search_all_fail.db'}",
        artifact_root=tmp_path / "artifacts2",
        research_root=tmp_path / "research2",
    )
    session = init_db(cfg.database_url)
    repo = Repo(session)
    service = FetchService(repo, cfg)

    class _FailPlugin:
        source_name = "fail"

        def search(self, keywords, start_date, end_date, page, page_size, arxiv_categories=None):
            raise RuntimeError("upstream down")

    service.plugins = {"fail": _FailPlugin()}

    try:
        service.search(
            sources=["fail"],
            keywords=[],
            start_date=None,
            end_date=None,
            page=1,
            page_size=10,
        )
        assert False, "expected failure"
    except RuntimeError as e:
        assert "FETCH_ALL_SOURCES_FAILED" in str(e)


def test_search_should_apply_global_sort_and_pagination_across_sources(tmp_path: Path):
    cfg = V2Config(
        database_url=f"sqlite:///{tmp_path / 'fetch_search_paging.db'}",
        artifact_root=tmp_path / "artifacts3",
        research_root=tmp_path / "research3",
    )
    session = init_db(cfg.database_url)
    repo = Repo(session)
    service = FetchService(repo, cfg)

    class _S1Plugin:
        source_name = "s1"

        def search(self, keywords, start_date, end_date, page, page_size, arxiv_categories=None):
            return [
                SourcePaper(
                    source="s1",
                    external_id="1",
                    title="old",
                    authors=["a"],
                    abstract=None,
                    published_at=datetime(2025, 1, 1),
                    url="https://example.com/1",
                    pdf_url=None,
                    doi=None,
                    pdf_unavailable=True,
                ),
                SourcePaper(
                    source="s1",
                    external_id="2",
                    title="mid",
                    authors=["a"],
                    abstract=None,
                    published_at=datetime(2025, 2, 1),
                    url="https://example.com/2",
                    pdf_url=None,
                    doi=None,
                    pdf_unavailable=True,
                ),
            ]

    class _S2Plugin:
        source_name = "s2"

        def search(self, keywords, start_date, end_date, page, page_size, arxiv_categories=None):
            return [
                SourcePaper(
                    source="s2",
                    external_id="3",
                    title="new",
                    authors=["b"],
                    abstract=None,
                    published_at=datetime(2025, 3, 1),
                    url="https://example.com/3",
                    pdf_url=None,
                    doi=None,
                    pdf_unavailable=True,
                ),
            ]

    service.plugins = {"s1": _S1Plugin(), "s2": _S2Plugin()}

    page1 = service.search(["s1", "s2"], [], None, None, page=1, page_size=2)
    assert [x.external_id for x in page1] == ["3", "2"]

    page2 = service.search(["s1", "s2"], [], None, None, page=2, page_size=2)
    assert [x.external_id for x in page2] == ["1"]

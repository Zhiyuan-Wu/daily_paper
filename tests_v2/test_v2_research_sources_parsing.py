from __future__ import annotations

from pathlib import Path

from v2.config import V2Config
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.research.service import ResearchService


def _service(tmp_path: Path) -> ResearchService:
    session = init_db(f"sqlite:///{tmp_path / 'research_parse.db'}")
    repo = Repo(session)
    cfg = V2Config(artifact_root=tmp_path / "artifacts", research_root=tmp_path / "research")
    cfg.artifact_root.mkdir(parents=True, exist_ok=True)
    cfg.research_root.mkdir(parents=True, exist_ok=True)
    return ResearchService(repo, cfg)


def test_read_sources_accepts_object_wrapper(tmp_path: Path):
    svc = _service(tmp_path)
    p = tmp_path / "sources.json"
    p.write_text(
        '{"sources": [{"title": "A", "url": "https://example.com", "source": "openalex", "published_at": "2026-01-01", "evidence_snippet": "x"}]}',
        encoding="utf-8",
    )

    sources = svc._read_sources_file(p)
    normalized = svc._normalize_sources(sources)

    assert len(normalized) == 1
    assert normalized[0]["title"] == "A"


def test_read_sources_accepts_markdown_json_block(tmp_path: Path):
    svc = _service(tmp_path)
    p = tmp_path / "sources.md"
    p.write_text(
        """Some notes

```json
[{"title": "B", "url": "https://example.org", "source": "blog", "published_at": "2026-02-01", "evidence_snippet": "y"}]
```
""",
        encoding="utf-8",
    )

    sources = svc._read_sources_file(p)
    normalized = svc._normalize_sources(sources)

    assert len(normalized) == 1
    assert normalized[0]["title"] == "B"

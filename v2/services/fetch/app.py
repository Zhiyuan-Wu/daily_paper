from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import Depends, FastAPI

from v2.config import V2Config
from v2.contracts.fetch import BatchDownloadRequest, DownloadRequest, DownloadResponse, SearchRequest, SearchResponse
from v2.db.models import init_session_factory
from v2.db.repo import Repo
from v2.services.fetch.service import FetchService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Fetch Service")


def get_repo() -> Generator[Repo, None, None]:
    session = SessionLocal()
    try:
        repo = Repo(session)
        repo.ensure_profile()
        yield repo
    finally:
        session.close()


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "fetch"}


@app.post("/v1/search", response_model=SearchResponse)
def search(req: SearchRequest, repo: Repo = Depends(get_repo)) -> SearchResponse:
    service = FetchService(repo, config)
    items = service.search(
        sources=req.sources,
        keywords=req.keywords,
        start_date=req.start_date.isoformat() if req.start_date else None,
        end_date=req.end_date.isoformat() if req.end_date else None,
        page=req.page,
        page_size=req.page_size,
    )
    saved = service.save_search_items(items)
    return SearchResponse(items=saved)


@app.post("/v1/download", response_model=DownloadResponse)
def download(req: DownloadRequest, repo: Repo = Depends(get_repo)) -> DownloadResponse:
    service = FetchService(repo, config)
    return DownloadResponse(**service.download(req))


@app.post("/v1/download/batch")
def download_batch(req: BatchDownloadRequest, repo: Repo = Depends(get_repo)) -> dict:
    service = FetchService(repo, config)
    profile = repo.ensure_profile()
    max_workers = max(1, int(profile.batch_download_concurrency))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(service.download, item) for item in req.requests]
        for f in as_completed(futures):
            results.append(f.result())
    return {"status": "completed", "count": len(results), "results": results}

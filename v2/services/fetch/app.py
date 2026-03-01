from __future__ import annotations

from fastapi import FastAPI

from v2.config import V2Config
from v2.contracts.fetch import BatchDownloadRequest, DownloadRequest, DownloadResponse, SearchRequest, SearchResponse
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.fetch.service import FetchService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = FetchService(repo, config)

app = FastAPI(title="V2 Fetch Service")


@app.post("/v1/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
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
def download(req: DownloadRequest) -> DownloadResponse:
    return DownloadResponse(**service.download(req))


@app.post("/v1/download/batch")
def download_batch(req: BatchDownloadRequest) -> dict:
    results = [service.download(item) for item in req.requests]
    return {"status": "completed", "count": len(results), "results": results}

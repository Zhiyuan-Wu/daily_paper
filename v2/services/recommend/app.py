from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.recommend import RecommendRequest, RecommendResponse
from v2.db.models import init_session_factory
from v2.db.repo import Repo
from v2.services.recommend.service import RecommendService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Recommend Service")


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
    return {"status": "healthy", "service": "recommend"}


@app.post("/v1/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest, repo: Repo = Depends(get_repo)) -> RecommendResponse:
    service = RecommendService(repo)
    try:
        out = service.recommend(req.paper_uids, req.top_k)
        return RecommendResponse(items=out["items"])
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "RECOMMEND_FAILED", "message": str(e)})

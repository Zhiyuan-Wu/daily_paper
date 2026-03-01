from __future__ import annotations

from fastapi import FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.recommend import RecommendRequest, RecommendResponse
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.recommend.service import RecommendService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = RecommendService(repo)

app = FastAPI(title="V2 Recommend Service")


@app.post("/v1/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    try:
        out = service.recommend(req.paper_uids, req.top_k)
        return RecommendResponse(items=out["items"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

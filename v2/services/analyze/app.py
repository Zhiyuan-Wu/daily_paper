from __future__ import annotations

from fastapi import FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.analyze import AnalyzeRequest, AnalyzeResponse
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = AnalyzeService(repo)

app = FastAPI(title="V2 Analyze Service")


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        out = service.analyze(req.paper_uid, req.title, req.full_text, req.abstract)
        return AnalyzeResponse(**out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

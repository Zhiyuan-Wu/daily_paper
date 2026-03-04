from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.analyze import AnalyzeRequest, AnalyzeResponse
from v2.db.models import init_session_factory
from v2.db.repo import Repo
from v2.services.analyze.service import AnalyzeService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Analyze Service")


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
    return {"status": "healthy", "service": "analyze"}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, repo: Repo = Depends(get_repo)) -> AnalyzeResponse:
    service = AnalyzeService(repo)
    try:
        out = service.analyze(req.paper_uid, req.title, req.full_text, req.abstract)
        return AnalyzeResponse(**out)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "ANALYZE_FAILED", "message": str(e)})

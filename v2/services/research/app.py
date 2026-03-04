from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.research import ResearchResultResponse, ResearchTaskRequest, ResearchTaskResponse
from v2.db.models import init_session_factory
from v2.db.repo import Repo
from v2.services.research.service import ResearchService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Research Service")


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
    return {"status": "healthy", "service": "research"}


@app.post("/v1/research/tasks", response_model=ResearchTaskResponse)
def create_task(req: ResearchTaskRequest, repo: Repo = Depends(get_repo)) -> ResearchTaskResponse:
    service = ResearchService(repo, config)
    out = service.run_task(req.topic, req.constraints)
    return ResearchTaskResponse(task_id=out["task_id"], status=out["status"])


@app.get("/v1/research/tasks/{task_id}")
def get_task(task_id: str, repo: Repo = Depends(get_repo)) -> dict:
    service = ResearchService(repo, config)
    try:
        return service.get_task(task_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": str(e)})


@app.get("/v1/research/tasks/{task_id}/result", response_model=ResearchResultResponse)
def get_result(task_id: str, repo: Repo = Depends(get_repo)) -> ResearchResultResponse:
    service = ResearchService(repo, config)
    try:
        return ResearchResultResponse(**service.get_result(task_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "RESEARCH_REPORT_NOT_FOUND", "message": str(e)})

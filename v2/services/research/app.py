from __future__ import annotations

from fastapi import FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.research import ResearchResultResponse, ResearchTaskRequest, ResearchTaskResponse
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.research.service import ResearchService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = ResearchService(repo, config)

app = FastAPI(title="V2 Research Service")


@app.post("/v1/research/tasks", response_model=ResearchTaskResponse)
def create_task(req: ResearchTaskRequest) -> ResearchTaskResponse:
    out = service.run_task(req.topic, req.constraints)
    return ResearchTaskResponse(task_id=out["task_id"], status=out["status"])


@app.get("/v1/research/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    try:
        return service.get_task(task_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/v1/research/tasks/{task_id}/result", response_model=ResearchResultResponse)
def get_result(task_id: str) -> ResearchResultResponse:
    try:
        return ResearchResultResponse(**service.get_result(task_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

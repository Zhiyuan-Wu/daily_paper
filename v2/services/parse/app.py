from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import Depends, FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.parse import BatchParseRequest, ParseRequest, ParseResponse
from v2.db.models import init_session_factory
from v2.db.repo import Repo
from v2.services.parse.service import ParseService

config = V2Config.from_env()
SessionLocal = init_session_factory(config.database_url)

app = FastAPI(title="V2 Parse Service")


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
    return {"status": "healthy", "service": "parse"}


@app.post("/v1/parse", response_model=ParseResponse)
def parse(req: ParseRequest, repo: Repo = Depends(get_repo)) -> ParseResponse:
    service = ParseService(repo, config)
    try:
        return ParseResponse(**service.parse(req.paper_uid, req.method, req.force_reparse))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "PARSE_INPUT_NOT_FOUND", "message": str(e)})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "PARSE_METHOD_UNSUPPORTED", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "PARSE_EXEC_FAILED", "message": str(e)})


@app.post("/v1/parse/batch")
def parse_batch(req: BatchParseRequest, repo: Repo = Depends(get_repo)) -> dict:
    profile = repo.ensure_profile()
    max_workers = max(1, int(profile.batch_parse_concurrency))

    def _parse_one(paper_uid: str) -> dict:
        local_session = SessionLocal()
        local_repo = Repo(local_session)
        local_repo.ensure_profile()
        local_service = ParseService(local_repo, config)
        try:
            return local_service.parse(paper_uid, req.method, False)
        except Exception as e:
            return {"paper_uid": paper_uid, "error": str(e)}
        finally:
            local_session.close()

    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_parse_one, paper_uid) for paper_uid in req.items]
        for f in as_completed(futures):
            out.append(f.result())
    return {"status": "completed", "results": out}

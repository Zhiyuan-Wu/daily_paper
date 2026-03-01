from __future__ import annotations

from fastapi import FastAPI, HTTPException

from v2.config import V2Config
from v2.contracts.parse import BatchParseRequest, ParseRequest, ParseResponse
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.services.parse.service import ParseService

config = V2Config.from_env()
session = init_db(config.database_url)
repo = Repo(session)
service = ParseService(repo, config)

app = FastAPI(title="V2 Parse Service")


@app.post("/v1/parse", response_model=ParseResponse)
def parse(req: ParseRequest) -> ParseResponse:
    try:
        return ParseResponse(**service.parse(req.paper_uid, req.method, req.force_reparse))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/parse/batch")
def parse_batch(req: BatchParseRequest) -> dict:
    out = []
    for paper_uid in req.items:
        try:
            out.append(service.parse(paper_uid, req.method, False))
        except Exception as e:
            out.append({"paper_uid": paper_uid, "error": str(e)})
    return {"status": "completed", "results": out}

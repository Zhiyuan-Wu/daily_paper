# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Repository status (2026-03-01):** V2 layered architecture. Authoritative runtime: `v2/`, `frontend/`, `tests_v2/`. Key docs: `docs/V2_RUNBOOK.md`, `docs/V2_DELIVERY.md`, `refactor.md`.

## Project Overview

Daily Paper V2 is an automated paper management and assisted-learning system with a layered architecture: six independent stateless services (fetch/parse/analyze/recommend/research/daily_report), API orchestration (BFF pattern), and React frontend. Single-user, local-first design with SQLite storage.

## Development Commands

### Running the Application
```bash
# Start backend + frontend (defaults: backend on 0.0.0.0:8011, frontend on 0.0.0.0:5183)
./start_server.sh

# Backend only (API defaults to 127.0.0.1:8001)
./scripts/run_v2_api.sh

# Individual services (for development)
python -m uvicorn v2.services.fetch.app:app --host 127.0.0.1 --port 8101
python -m uvicorn v2.services.parse.app:app --host 127.0.0.1 --port 8102
python -m uvicorn v2.services.analyze.app:app --host 127.0.0.1 --port 8103
python -m uvicorn v2.services.recommend.app:app --host 127.0.0.1 --port 8104
python -m uvicorn v2.services.research.app:app --host 127.0.0.1 --port 8105
python -m uvicorn v2.services.daily_report.app:app --host 127.0.0.1 --port 8106
```

### Configuration
Key environment variables (see `v2/config.py`):
- `V2_API_HOST`, `V2_API_PORT` - API binding
- `V2_DATABASE_URL` - SQLite database path (default: `sqlite:///data/v2_daily_paper.db`)
- `V2_ARTIFACT_ROOT` - Artifact storage (default: `data/v2_artifacts`)
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_API_BASE` - LLM configuration
- `V2_RESEARCH_FAKE=1` - Enable fake mode for research tasks (testing)

### Testing
```bash
# Run all V2 tests
pytest tests_v2

# Run specific test
pytest tests_v2/test_v2_e2e.py
```

### Frontend Development
```bash
cd frontend
npm install     # Install dependencies
npm run dev     # Start dev server (Vite)
npm run build   # Production build
```

## V2 Architecture Overview

```
v2/
├── contracts/      # Pydantic schemas for service boundaries
├── foundation/     # Artifact management, LRU eviction
├── db/            # SQLAlchemy models, repository layer
├── services/      # Six stateless services (fetch/parse/analyze/recommend/research/daily_report)
├── api/           # BFF orchestration layer (FastAPI)
└── worker/        # Background job runner
```

### Key Design Principles

1. **Layer Separation**: Data layer only persists, service layer only computes, API layer only orchestrates
2. **Stateless Services**: All state in SQLite + artifacts; services are restartable
3. **Contract-First**: Service boundaries defined by Pydantic schemas in `v2/contracts/`
4. **Tracability**: All jobs have `trace_id`, service calls logged to `service_call_logs`
5. **Local-First**: Single-user, no auth, runs offline-capable

### Service Contracts (`v2/contracts/`)

All service communication uses versioned Pydantic schemas:
- `common.py` - `ErrorResponse`, `JobStatusResponse`, `Pagination`
- `fetch.py` - `SearchRequest`, `DownloadRequest`, `PaperItem`
- `parse.py` - `ParseRequest`, `ParseResponse`
- `analyze.py` - `AnalyzeRequest`, `AnalyzeResponse`
- `recommend.py` - `RecommendRequest`, `RecommendResponse`
- `research.py` - `ResearchTaskRequest`, `ResearchResult`
- `report.py` - `DailyReportTaskRequest`, `DailyReportResponse`

### Foundation Layer

**Artifact Manager** (`v2/foundation/artifact_manager.py`):
- Manages paper files in `data/v2_artifacts/papers/{paper_uid}/`
- `paper_uid(source, external_id)` - deterministic SHA256 ID
- `pdf_path()`, `text_path()` - file path allocation
- `write_bytes()`, `write_text()` - atomic writes with hash tracking

**LRU Eviction** (`v2/foundation/lru.py`):
- Dual-threshold PDF eviction: max bytes OR max count
- Evicts by `last_accessed_at` ascending
- Preserves text/analysis artifacts, only deletes PDFs
- Configurable via settings (default: 10GB, 5000 files)

### Database Models (`v2/db/models.py`)

Key tables:
- `app_profile` - Single-user settings (timezone, keywords, weights, concurrency)
- `papers` - Paper metadata, unique on (source, external_id), `pdf_unavailable` flag
- `paper_source_links` - Cross-source deduplication mapping
- `paper_artifacts` - File references with LRU tracking, `evicted` flag
- `paper_analysis` - Structured LLM outputs (tldr, key_points, etc.)
- `paper_feedback` - User interactions (like/dislike/read/save/dismiss)
- `recommendation_runs`, `recommendation_items` - Recommendation history
- `research_tasks`, `research_reports` - Deep research results
- `daily_reports`, `daily_report_items` - Daily reports
- `jobs` - Async task tracking
- `service_call_logs` - Observability

All datetimes are timezone-aware (default: `Asia/Shanghai`).

### Repository Pattern (`v2/db/repo.py`)

`Repo` class wraps SQLAlchemy session with domain methods:
- `ensure_profile()`, `update_profile()` - Settings management
- `upsert_paper()`, `get_paper()` - Paper CRUD
- `upsert_artifact()`, `get_artifact()` - Artifact tracking
- `save_feedback()`, `create_job()`, `update_job()` - Operations

## Service Layer Details

### Fetch Service (`v2/services/fetch/`)

**Plugin Architecture**:
- `OpenAlexPlugin` - Scholar search via OpenAlex API (default, 2 req/s limit)
- Plugins implement `search(keywords, dates, page)` -> `list[SourcePaper]`
- `SourcePaper` dataclass: `source`, `external_id`, `doi`, `title`, `authors`, `abstract`, `published_at`, `url`, `pdf_url`, `pdf_unavailable`

**Deduplication** (`dedup.py`):
1. Priority by DOI match
2. Fallback to title + first author + year
3. Conflicts logged to `data/v2_artifacts/logs/dedup_conflicts.jsonl`
4. Cross-source links stored in `paper_source_links`

**Behavior**: No PDF available → set `pdf_unavailable=True`, still participates in recommendations with low weight.

### Parse Service (`v2/services/parse/`)

- **Methods**: `simple` (PyMuPDF), `ocr` (OCR service)
- **No automatic fallback**: User-specified method only; failure = failure
- **Caching**: Results keyed by `(paper_uid, method, parser_version)`
- **OCR timeout**: 120s default, no retry on failure

### Analyze Service (`v2/services/analyze/`)

- **Single pipeline**: tldr, key_points, problem_statement, method_summary, experiment_summary, limitations, tags
- **LLM config**: Uses project `.env` OPENAI_* settings
- **Output**: Stored as JSON in `paper_analysis` table

### Recommend Service (`v2/services/recommend/`)

**Strategies** (four default, equal weight 0.25):
- `keyword_semantic` - Semantic similarity to interest keywords
- `interested_semantic` - Similarity to previously liked papers
- `repetition_penalty` - Downweight previously recommended
- `llm_theme` - LLM-generated interest themes

**Fusion**: Score = Σ(w_i * s_i) / Σ(w_i), weights configurable in settings

**PDF unavailable handling**: Papers with `pdf_unavailable=True` get penalty factor (configurable)

### Research Service (`v2/services/research/`)

**Execution**:
- Creates isolated workdir: `data/research_runs/{task_id}/`
- Generates task file with 6-section template (背景、问题拆解、方法对比、关键文献、结论、后续行动)
- Calls: `claude 'Read /absolute/path/to/task_xxx.txt for work details.' --allowedTools 'Bash,Read,Edit,Write,WebFetch'`
- Polls subprocess (default 45min timeout, configurable)
- Parses output: `report.md` + `sources.json`

**Sources protocol** (minimum fields): `title`, `url`, `source`, `published_at`, `evidence_snippet` (max 300 chars)

**Cleanup**: Workdir deleted immediately on completion; cleanup failure triggers async retry, does not fail task

**Fake mode**: `V2_RESEARCH_FAKE=1` for testing without actual CLI calls

### Daily Report Service (`v2/services/daily_report/`)

**Manual trigger only** (no scheduling):
- Pipeline: fetch → parse → analyze → recommend → summarize
- Any step failure = entire report failure (no degraded output)
- Date calculated in user's timezone
- Result: Markdown summary + ranked paper list with analysis snapshots

## API Layer (`v2/api/app.py`)

BFF pattern: orchestrates services, manages jobs, no business logic.

**Key endpoints**:
- `POST /api/v1/papers/search` - Search and save papers
- `POST /api/v1/papers/import` - Download PDF
- `POST /api/v1/papers/{paper_uid}/parse` - Parse paper text
- `POST /api/v1/papers/{paper_uid}/analyze` - Analyze paper
- `POST /api/v1/recommendations/generate` - Generate recommendations
- `POST /api/v1/interactions` - Submit feedback
- `POST /api/v1/research/tasks` - Create research task
- `GET /api/v1/research/tasks/{task_id}/result` - Get research result
- `POST /api/v1/reports/daily/generate` - Generate daily report
- `GET /api/v1/reports/daily/{report_id}` - Get daily report
- `GET/PUT /api/v1/settings` - Application settings
- `GET /api/v1/tasks/{job_id}` - Job status

**Error format**: `{code, message, details?, trace_id}`

**Settings runtime**: Changes via `PUT /api/v1/settings` take effect immediately for new tasks; running tasks not affected.

## Frontend (`frontend/`)

**Stack**: React 19, TypeScript, Vite, Ant Design, TanStack Query, Zustand, React Router

**Pages**:
- Papers (exploration, search, import)
- Recommendations (results with explanations)
- Research (task submission, status, reports)
- Daily Reports (manual trigger, view history)
- Tasks (job status, error debugging)
- Settings (timezone, sources, weights, concurrency)

**API client**: Shared Axios client with error handling

## Important Constraints & Decisions

1. **No auth**: Local-only, single-user
2. **No automatic scheduling**: All manual triggers (reports, research)
3. **Parse method is explicit**: No auto-fallback, user chooses simple/ocr
4. **PDF LRU is strict**: No protected files, dual-threshold eviction
5. **Dedup is automatic**: DOI-based with title+author+year fallback, conflicts logged
6. **Research only uses Claude CLI**: No alternative research methods
7. **Settings apply to new tasks only**: No hot-reload for running jobs
8. **PDF unavailable != excluded**: Papers without PDF can participate with penalty
9. **OpenAlex only**: No other scholar sources in V1
10. **SQLite only**: No Redis, no message queues

## Import Patterns

```python
from v2.config import V2Config
from v2.db.models import init_db
from v2.db.repo import Repo
from v2.contracts.fetch import SearchRequest, DownloadRequest
from v2.services.fetch.service import FetchService
from v2.foundation.artifact_manager import ArtifactManager
```

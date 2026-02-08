# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Paper is an automated research paper recommendation and summarization system. It fetches papers from arXiv and HuggingFace, generates LLM-based summaries, and provides personalized recommendations based on user interests.

## Development Commands

### Running the Application
```bash
# Start the FastAPI server (serves both API and frontend at http://localhost:8000)
./start_server.sh

# Or directly with uvicorn
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m integration  # Integration tests (require network access)
pytest -m slow         # Slow-running tests
```

### API Endpoints
- `/api/papers/` - Paper CRUD operations
- `/api/users/` - User profile management
- `/api/recommendations/` - Get paper recommendations
- `/api/reports/` - Daily reports
- `/api/settings/` - Application settings
- `/api/refresh/` - Refresh paper data
- `/docs` - Interactive API documentation (Swagger UI)

## Architecture

### Plugin-Based Components

The system uses a plugin architecture for several core components:

**Downloaders** (`daily_paper/downloaders/`):
- Base class: `BaseDownloader` with abstract methods `fetch_by_date()` and `download_paper()`
- Implementations: `ArxivDownloader`, `HuggingFaceDownloader`
- Returns: `PaperMetadata` namedtuples with paper details

**Recommenders** (`daily_paper/recommenders/`):
- Base class: `BaseRecommender` with abstract `recommend()` method
- Strategies registered via `StrategyRegistry` (plugin pattern)
- Available strategies:
  - `keyword_filter` - Filter by user keywords
  - `keyword_semantic` - Semantic similarity to keywords
  - `interested_semantic` - Similarity to previously interested papers
  - `llm_themes` - LLM-generated interest themes
  - `disinterested_filter` - Filter out disinterested papers
  - `repetition_filter` - Downweight repeated recommendations
  - `fusion` - Combine multiple strategies using RRF (Reciprocal Rank Fusion)

**Parsers** (`daily_paper/parsers/`):
- `PDFParser` - Extract text from PDFs with OCR fallback
- Returns `ParseResult` namedtuple with `success`, `text`, `method`

**Summarizers** (`daily_paper/summarizers/`):
- `LLMClient` - Configurable OpenAI/Azure client
- `PaperSummarizer` - Multi-step summarization workflow
- Summary types: `detailed`, `tldr`, `highlights`

### Database

**Schema** (`daily_paper/database/models.py`):
- `papers` - Paper metadata with unique constraint on (source, paper_id)
- `summaries` - LLM summaries with different types
- `user_profile` - Single-user profile (designed for personal use)
- `paper_interactions` - Track user actions (interested/not_interested/no_action)
- `interest_themes` - LLM-generated themes for recommendations
- `daily_reports` - Generated daily reports

Uses SQLAlchemy ORM with SQLite. All models use timezone-aware datetimes.

### Configuration

Centralized in `daily_paper/config.py` using dataclasses. Load with `Config.from_env()`.

Key configs:
- `LLMConfig` - OpenAI API key, model, endpoint
- `ArxivConfig` - Categories, max results
- `EmbeddingConfig` - Ollama-compatible embedding service for semantic similarity
- `RecommendationConfig` - Strategy selection, RRF parameters, refresh intervals
- `LogConfig` - Structured logging with file rotation

Environment variables are loaded from `.env` file via python-dotenv.

### Recommendation System Flow

1. User keywords are parsed from `user_profile.interests` field
2. Strategies are instantiated from enabled config via `StrategyRegistry`
3. Each strategy produces ranked paper lists
4. `fusion.py` combines results using Reciprocal Rank Fusion (RRF)
5. Repetition filter downweights previously recommended papers
6. Final ranked list returned

### Logging

Logging is configured in `daily_paper/logging_config.py` and must be set up **before** any other imports (see `backend/main.py`). Uses structured logging with file rotation.

### Import Patterns

The project uses a `daily_paper` package for core logic:
```python
from daily_paper.config import Config
from daily_paper.downloaders import ArxivDownloader
from daily_paper.recommenders import StrategyRegistry
```

FastAPI routers are in `backend/routers/` and import from `daily_paper` modules.

### Key Patterns

**Factory Pattern**: Components like downloaders and recommenders are instantiated dynamically based on config.

**Async/Await**: FastAPI routes use async functions. Database operations use SQLAlchemy sync sessions.

**Type Hints**: Extensive use of type annotations throughout. Use `from __future__ import annotations` for forward references.

**NamedTuples**: Used for data transfer (e.g., `PaperMetadata`, `ParseResult`).

**Relationships**: SQLAlchemy models use proper relationships (e.g., `paper.summaries`, `summary.paper`).

## Important Notes

- **Logging setup must happen first** in any main entry point before other imports
- **Timezone-aware datetimes** are used throughout for all timestamp fields
- **Unique paper constraint**: Papers are unique by (source, paper_id) combination
- **Single-user design**: System is designed for one user, not multi-tenant
- **Embedding service**: Uses local Ollama-compatible API (configurable via env)
- **OCR fallback**: PDF parser falls back to OCR service when PyMuPDF fails

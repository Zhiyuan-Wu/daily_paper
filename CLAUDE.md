# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Paper System is a full-stack web application for automated research paper recommendation. It fetches papers from arXiv and HuggingFace, parses PDFs, generates AI-powered summaries, and provides personalized recommendations through a FastAPI backend with vanilla JavaScript frontend.

## Development Commands

### Starting the Server

```bash
# Start the FastAPI backend server (preferred method)
./start_server.sh

# Or manually:
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API endpoints: http://localhost:8000/api/
- API documentation: http://localhost:8000/docs
- Frontend: http://localhost:8000/static/index.html

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_parser.py

# Run with verbose output
pytest -v tests/
```

### Dependencies

```bash
# Install dependencies (after activating virtual environment)
pip install -r requirements.txt
```

## Architecture

### Module Structure

The project is divided into two main components:

1. **`daily_paper/`** - Core library module containing:
   - `config.py` - Centralized configuration using environment variables
   - `manager.py` - DownloadManager orchestrating paper fetching from multiple sources
   - `database/models.py` - SQLAlchemy ORM models (Paper, Summary, UserProfile, PaperInteraction, InterestTheme, DailyReport)
   - `downloaders/` - Plugin architecture for paper sources (arXiv, HuggingFace)
   - `parsers/` - PDF text extraction with PyMuPDF and OCR fallback
   - `summarizers/` - LLM-based 7-step paper summarization workflow
   - `embeddings/` - Ollama-based embedding generation
   - `recommenders/` - Multi-strategy recommendation system with RRF fusion
   - `reports/` - Daily report generation with AI highlights
   - `users/` - User profile and interaction management

2. **`backend/`** - FastAPI web application:
   - `main.py` - FastAPI app entry point with CORS and router registration
   - `dependencies.py` - Dependency injection for database sessions
   - `models/` - Pydantic models for API requests/responses
   - `routers/` - API route handlers (papers, users, reports, recommendations, settings)
   - `static/frontend/` - Vanilla JavaScript single-page application

### Key Design Patterns

**Plugin Architecture (Downloaders):** New paper sources can be added by implementing `BaseDownloader` interface and registering with `DownloadManager.register_downloader()`.

**Strategy Pattern (LLM Provider):** Runtime selection between OpenAI and Azure OpenAI based on `LLM_PROVIDER` environment variable.

**Repository Pattern (Database):** SQLAlchemy ORM with relationship support between papers, summaries, user interactions, and recommendations.

### Configuration System

All configuration is environment-based through `.env` file. The `Config` class (`daily_paper/config.py`) aggregates all sub-configurations:
- `LLMConfig` - OpenAI/Azure OpenAI settings
- `ArxivConfig` - arXiv categories and max results
- `OCRConfig` - OCR service URL for PDF fallback
- `DatabaseConfig` - SQLite database URL
- `PathConfig` - Download and text extraction directories
- `EmbeddingConfig` - Ollama embedding service settings
- `RecommendationConfig` - Strategy selection and ranking parameters
- `ReportConfig` - Daily report generation settings

### Database Schema

- **papers** - Paper metadata with file references (pdf_path, text_path)
- **summaries** - LLM summaries with different types (basic_info, methods, results, etc.)
- **user_profile** - Single-user profile (id=1) with interests and preferences
- **paper_interactions** - User actions on papers (interested/not_interested) with recommendation tracking
- **interest_themes** - LLM-generated themes from interested papers, regenerated periodically
- **daily_reports** - Generated reports with AI highlights and paper recommendations

### Recommendation System

The recommender uses 7 strategies with Reciprocal Rank Fusion (RRF):
1. **Keyword semantic** (`keyword_semantic`) - Semantic similarity to user keywords
2. **Interested semantic** (`interested_semantic`) - Similarity to previously interested papers
3. **Theme-based** (`llm_themes`) - Matching to LLM-generated interest themes
4. **Disinterested filter** (`disinterested_filter`) - Filter out disinterested keywords
5. **Disinterested semantic** (`disinterested_semantic`) - Dissimilarity to disliked papers
6. **Repetition filter** (`repetition_filter`) - Downweight frequently recommended papers
7. **Fusion engine** (`fusion`) - RRF-based fusion of all strategies

Strategies are registered in `recommenders/strategies/` and can be enabled/disabled via `RECOMMEND_STRATEGIES` env var.

### Async Operations

Long-running operations (report generation, summarization) use background tasks with polling:
1. Client initiates operation via POST endpoint
2. Server returns task_id immediately
3. Client polls `GET /api/reports/tasks/{task_id}` for status
4. Task status transitions: pending → processing → completed/failed

## Important Implementation Notes

- **Single-user system**: User profile always has id=1, hardcoded in dependencies.py
- **PDF parsing quality check**: Parser automatically falls back to OCR when PyMuPDF extraction is below threshold
- **Deduplication**: Papers are uniquely identified by source + paper_id combination
- **Frontend**: No build step required - vanilla JS with modular files in `backend/static/frontend/js/`
- **CORS**: Currently allows all origins (`*`) - should be restricted in production
- **File paths**: PDF and text files are stored locally, paths referenced in database
- **Theme regeneration**: Interest themes are regenerated based on `theme_refresh_days` or `theme_refresh_papers` thresholds

## Common Tasks

### Adding a New Paper Source

1. Create new downloader in `daily_paper/downloaders/` inheriting from `BaseDownloader`
2. Implement `get_papers_by_date()` and `download_paper()` methods
3. Register in `DownloadManager._register_default_downloaders()`
4. Add configuration to relevant Config class if needed

### Modifying Recommendation Strategies

Strategies are in `daily_paper/recommenders/strategies/`. Each strategy:
- Inherits from `BaseRecommendationStrategy`
- Implements `calculate_scores()` method
- Registered in `recommenders/registry.py`
- Enabled via `RECOMMEND_STRATEGIES` env variable

### Adding New API Endpoints

1. Add route handler in `backend/routers/` (or create new router file)
2. Create Pydantic models in `backend/models/` if needed
3. Register router in `backend/main.py` with `app.include_router()`

### Database Migrations

The project uses SQLAlchemy `create_all()` for table creation. For schema changes:
- Modify models in `daily_paper/database/models.py`
- For production data migration, consider using Alembic
- Local development can drop and recreate database at `DATABASE_URL`

## Environment Setup

Copy `.env.example` to `.env` and configure:
- `DATABASE_URL` - SQLite database path (default: sqlite:///data/papers.db)
- `LLM_PROVIDER` - "openai" or "azure"
- `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY` - LLM access
- `EMBEDDING_API_URL` - Ollama embedding service
- `ARXIV_CATEGORIES` - Comma-separated arXiv categories
- `OCR_SERVICE_URL` - Optional OCR fallback service
- `RECOMMEND_STRATEGIES` - Enabled recommendation strategies

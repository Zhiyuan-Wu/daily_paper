"""
Daily Paper FastAPI Application.

Main application entry point with CORS, static files, and router registration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import routers
from backend.routers import (
    papers_router,
    users_router,
    reports_router,
    recommendations_router,
    settings_router,
    refresh_router,
)

# Create FastAPI app
app = FastAPI(
    title="Daily Paper API",
    description="REST API for the daily paper recommendation system",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get static files directory
static_dir = Path(__file__).parent / "static" / "frontend"
if static_dir.exists():
    # Mount static files for frontend
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    # Create placeholder directory if it doesn't exist
    static_dir.mkdir(parents=True, exist_ok=True)

# Include routers
app.include_router(papers_router, prefix="/api/papers", tags=["papers"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(recommendations_router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(refresh_router, prefix="/api/refresh", tags=["refresh"])


@app.get("/")
async def root():
    """Root endpoint - redirect to frontend home page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html", status_code=302)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

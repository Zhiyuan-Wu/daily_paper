"""
FastAPI routers for API endpoints.
"""

from .papers import router as papers_router
from .users import router as users_router
from .reports import router as reports_router
from .recommendations import router as recommendations_router
from .settings import router as settings_router
from .refresh import router as refresh_router

__all__ = [
    "papers_router",
    "users_router",
    "reports_router",
    "recommendations_router",
    "settings_router",
    "refresh_router",
]

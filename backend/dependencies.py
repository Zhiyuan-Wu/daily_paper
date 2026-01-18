"""
Dependency injection for FastAPI backend.

Provides database sessions and manager instances as dependencies.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from daily_paper.database import init_db
from daily_paper.config import Config
from daily_paper.users import UserManager
from daily_paper.recommenders import RecommendationManager
from daily_paper.reports import ReportGenerator
from daily_paper.summarizers import PaperSummarizer


def get_db():
    """
    Get database session.

    Yields a SQLAlchemy session for the request lifecycle.
    Session is properly closed after the request completes.
    """
    database_url = Config.from_env().database.url
    session = init_db(database_url)
    try:
        yield session
    finally:
        session.close()


def get_user_manager(db: Session = Depends(get_db)) -> UserManager:
    """
    Get UserManager instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        UserManager instance for the current request.
    """
    return UserManager(db)


def get_recommendation_manager(
    db: Session = Depends(get_db)
) -> RecommendationManager:
    """
    Get RecommendationManager instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        RecommendationManager instance for the current request.
    """
    config = Config.from_env()
    return RecommendationManager(config, db)


def get_report_generator(db: Session = Depends(get_db)) -> ReportGenerator:
    """
    Get ReportGenerator instance.

    Args:
        db: Database session from dependency injection.

    Returns:
        ReportGenerator instance for the current request.
    """
    config = Config.from_env()
    return ReportGenerator(config, db)


def get_paper_summarizer() -> PaperSummarizer:
    """
    Get PaperSummarizer instance.

    Returns:
        PaperSummarizer instance for the current request.
    """
    config = Config.from_env()
    return PaperSummarizer(config)

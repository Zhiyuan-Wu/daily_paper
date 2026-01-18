"""
pytest configuration and fixtures for Daily Paper tests.

This module provides shared fixtures for all test modules.
"""

import sys
import tempfile
from pathlib import Path
from datetime import date, datetime

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.config import Config
from daily_paper.database import (
    init_db, Paper, Summary, UserProfile, PaperInteraction,
    InterestTheme, DailyReport
)
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.summarizers.llm_client import LLMClient
from daily_paper.users.manager import UserManager
from daily_paper.downloaders.arxiv_downloader import ArxivDownloader


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def config():
    """Create a test configuration."""
    # Use in-memory database for tests
    config = Config.from_env()
    config.database.url = "sqlite:///:memory:"
    return config


@pytest.fixture(scope="function")
def session(config):
    """Create a database session for testing."""
    session = init_db(config.database.url)
    yield session
    session.close()


@pytest.fixture(scope="function")
def embedding_client(config):
    """Create an embedding client for testing."""
    return EmbeddingClient(config.embedding)


@pytest.fixture(scope="function")
def llm_client(config):
    """Create an LLM client for testing."""
    return LLMClient(config.llm)


@pytest.fixture(scope="function")
def user_manager(session):
    """Create a user manager for testing."""
    return UserManager(session)


@pytest.fixture(scope="function")
def user_profile(session):
    """Create a test user profile."""
    profile = UserProfile(
        id=1,
        interested_keywords="transformer, attention, NLP",
        disinterested_keywords="image classification, CNN",
        interest_description="Research on transformer architectures and attention mechanisms for NLP"
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@pytest.fixture(scope="function")
def paper(session):
    """Create a test paper."""
    paper = Paper(
        source="arxiv",
        paper_id="2301.12345",
        title="Test Paper: Attention Is All You Need",
        authors="Author One, Author Two",
        abstract="This is a test abstract about attention mechanisms.",
        published_date=datetime.now(),
        url="https://arxiv.org/abs/2301.12345",
        pdf_path=None,
        text_path=None
    )
    session.add(paper)
    session.commit()
    session.refresh(paper)
    return paper


@pytest.fixture(scope="function")
def papers(session):
    """Create multiple test papers."""
    papers_data = [
        {
            "source": "arxiv",
            "paper_id": "2301.00001",
            "title": "Introduction to Transformers",
            "authors": "Alice, Bob",
            "abstract": "A comprehensive introduction to transformer models.",
            "published_date": datetime.now(),
            "url": "https://arxiv.org/abs/2301.00001"
        },
        {
            "source": "arxiv",
            "paper_id": "2301.00002",
            "title": "Attention Mechanisms Deep Dive",
            "authors": "Charlie, Dave",
            "abstract": "Deep dive into attention mechanisms for NLP.",
            "published_date": datetime.now(),
            "url": "https://arxiv.org/abs/2301.00002"
        },
        {
            "source": "huggingface",
            "paper_id": "2301.00003",
            "title": "Practical Guide to LLMs",
            "authors": "Eve, Frank",
            "abstract": "A practical guide to working with large language models.",
            "published_date": datetime.now(),
            "url": "https://huggingface.co/papers/2301.00003"
        }
    ]

    papers = []
    for data in papers_data:
        paper = Paper(**data)
        session.add(paper)
        papers.append(paper)

    session.commit()
    for paper in papers:
        session.refresh(paper)

    return papers


@pytest.fixture(scope="function")
def arxiv_downloader():
    """Create an arXiv downloader for testing."""
    return ArxivDownloader(
        categories=["cs.AI", "cs.LG"],
        max_results=10
    )

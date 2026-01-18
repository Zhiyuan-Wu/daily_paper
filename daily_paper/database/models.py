"""
SQLAlchemy models for the Daily Paper system.

This module defines the database schema for storing papers, summaries,
user interactions, recommendations, and daily reports. Uses SQLite
with SQLAlchemy ORM for database operations.

The schema consists of multiple tables:
- papers: Stores paper metadata and file references
- summaries: Stores LLM-generated summaries with different types
- user_profile: Single-user profile for preferences and interests
- paper_interactions: Records user actions on papers
- interest_themes: LLM-generated interest themes
- daily_reports: Generated daily paper reports
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Paper(Base):
    """
    Model representing a research paper.

    Stores paper metadata from various sources (arXiv, HuggingFace)
    and references to downloaded files (PDF, extracted text).

    Attributes:
        id: Primary key.
        source: Paper source ('arxiv', 'huggingface', etc.).
        paper_id: Source-specific paper identifier (e.g., arXiv ID).
        title: Paper title.
        authors: Comma-separated list of authors.
        abstract: Paper abstract/description.
        published_date: Publication date.
        url: URL to the paper page.
        pdf_path: Local path to downloaded PDF file.
        text_path: Local path to extracted text file.
        created_at: Database record creation timestamp.
        summaries: Related summary records.
    """

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    paper_id: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    authors: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    url: Mapped[str] = mapped_column(String(1000))
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    text_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    # Unique constraint on source + paper_id combination
    __table_args__ = (UniqueConstraint("source", "paper_id", name="unique_paper"),)

    # Relationship to summaries
    summaries: Mapped[List["Summary"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Paper(source={self.source}, paper_id={self.paper_id}, title={self.title[:50]}...)>"

    def to_dict(self) -> dict:
        """
        Convert paper to dictionary representation.

        Returns:
            Dictionary containing all paper fields.
        """
        return {
            "id": self.id,
            "source": self.source,
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "url": self.url,
            "pdf_path": self.pdf_path,
            "text_path": self.text_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Summary(Base):
    """
    Model representing a paper summary.

    Stores LLM-generated summaries with different types (basic_info,
    background, contributions, methods, results, conclusions, etc.).

    Attributes:
        id: Primary key.
        paper_id: Foreign key to the Paper model.
        summary_type: Type of summary (e.g., 'basic_info', 'methods').
        content: The summary text content.
        created_at: Summary generation timestamp.
        paper: Related Paper object.
    """

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    summary_type: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    # Relationship to paper
    paper: Mapped["Paper"] = relationship(back_populates="summaries")

    # Unique constraint on paper + summary_type (one summary per type per paper)
    __table_args__ = (
        UniqueConstraint("paper_id", "summary_type", name="unique_summary_type"),
    )

    def __repr__(self) -> str:
        return f"<Summary(paper_id={self.paper_id}, type={self.summary_type})>"

    def to_dict(self) -> dict:
        """
        Convert summary to dictionary representation.

        Returns:
            Dictionary containing all summary fields.
        """
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "summary_type": self.summary_type,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserProfile(Base):
    """
    Model representing a single-user profile.

    Stores user preferences, interests, and interaction history.
    Since this is a single-user system, there will be only one record (id=1).

    Attributes:
        id: Primary key (always 1 for single-user system).
        interested_keywords: Comma-separated keywords the user is interested in.
        disinterested_keywords: Comma-separated keywords to exclude.
        interest_description: Free-text description of research interests.
        created_at: Profile creation timestamp.
        updated_at: Last update timestamp.
        interactions: Related PaperInteraction records.
        interest_themes: Related InterestTheme records.
    """

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    interested_keywords: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    disinterested_keywords: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    interest_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    # Relationships
    interactions: Mapped[List["PaperInteraction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interest_themes: Mapped[List["InterestTheme"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id})>"

    def to_dict(self) -> dict:
        """
        Convert user profile to dictionary representation.

        Returns:
            Dictionary containing all profile fields.
        """
        return {
            "id": self.id,
            "interested_keywords": self.interested_keywords,
            "disinterested_keywords": self.disinterested_keywords,
            "interest_description": self.interest_description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PaperInteraction(Base):
    """
    Model representing user interactions with individual papers.

    Tracks how the user has interacted with recommended papers,
    including actions and notes.

    Attributes:
        id: Primary key.
        user_id: Foreign key to UserProfile (always 1).
        paper_id: Foreign key to Paper model.
        action: User action ('interested', 'not_interested', 'no_action').
        notes: User notes after reading the paper.
        recommendation_count: Number of times this paper was recommended.
        last_recommended_at: Timestamp of most recent recommendation.
        created_at: Interaction record creation timestamp.
        updated_at: Last update timestamp.
        user: Related UserProfile.
        paper: Related Paper.
    """

    __tablename__ = "paper_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id"), default=1)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    action: Mapped[str] = mapped_column(
        String(20), default="no_action", index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_recommended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    # Unique constraint: one interaction per paper
    __table_args__ = (
        UniqueConstraint("user_id", "paper_id", name="unique_user_paper"),
    )

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="interactions")
    paper: Mapped["Paper"] = relationship()

    def __repr__(self) -> str:
        return f"<PaperInteraction(paper_id={self.paper_id}, action={self.action})>"

    def to_dict(self) -> dict:
        """
        Convert interaction to dictionary representation.

        Returns:
            Dictionary containing all interaction fields.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "paper_id": self.paper_id,
            "action": self.action,
            "notes": self.notes,
            "recommendation_count": self.recommendation_count,
            "last_recommended_at": self.last_recommended_at.isoformat() if self.last_recommended_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InterestTheme(Base):
    """
    Model representing LLM-generated interest themes.

    Stores evolving interest themes that are periodically regenerated
    by analyzing recent interested papers.

    Attributes:
        id: Primary key.
        user_id: Foreign key to UserProfile (always 1).
        theme: Interest theme description (e.g., "transformer architectures").
        source_papers: JSON array of paper IDs used to generate this theme.
        created_at: Theme generation timestamp.
        is_active: Whether this theme is currently active.
        user: Related UserProfile.
    """

    __tablename__ = "interest_themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id"), default=1)
    theme: Mapped[str] = mapped_column(String(500), index=True)
    source_papers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Relationships
    user: Mapped["UserProfile"] = relationship(back_populates="interest_themes")

    def __repr__(self) -> str:
        return f"<InterestTheme(id={self.id}, theme={self.theme[:50]}..., active={self.is_active})>"

    def to_dict(self) -> dict:
        """
        Convert interest theme to dictionary representation.

        Returns:
            Dictionary containing all theme fields.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "theme": self.theme,
            "source_papers": self.source_papers,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }


class DailyReport(Base):
    """
    Model representing generated daily paper reports.

    Stores manually triggered daily reports containing recommended papers
    and AI-generated highlights.

    Attributes:
        id: Primary key.
        report_date: Date of the report.
        recommendations: JSON array of recommended paper IDs.
        highlights: AI-generated highlights/summary.
        themes_used: JSON array of interest theme IDs used.
        created_at: Report generation timestamp.
    """

    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    recommendations: Mapped[str] = mapped_column(Text)  # JSON array of paper IDs
    highlights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    themes_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    def __repr__(self) -> str:
        return f"<DailyReport(id={self.id}, date={self.report_date})>"

    def to_dict(self) -> dict:
        """
        Convert daily report to dictionary representation.

        Returns:
            Dictionary containing all report fields.
        """
        return {
            "id": self.id,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "recommendations": self.recommendations,
            "highlights": self.highlights,
            "themes_used": self.themes_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db(database_url: str) -> Session:
    """
    Initialize database connection and create tables.

    Creates all tables defined in the Base metadata if they don't exist.
    Returns a SQLAlchemy Session for database operations.

    Args:
        database_url: SQLAlchemy database URL (e.g., 'sqlite:///data/papers.db').

    Returns:
        A configured SQLAlchemy Session instance.

    Examples:
        >>> session = init_db("sqlite:///data/papers.db")
        >>> paper = Paper(source='arxiv', paper_id='2301.12345', ...)
        >>> session.add(paper)
        >>> session.commit()
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return Session(engine)

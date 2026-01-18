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
    Float,
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


class TaskHistory(Base):
    """
    Model representing workflow task execution history.

    Stores records of background task executions (e.g., paper fetching,
    report generation) with status tracking and statistics.

    Attributes:
        id: Primary key.
        task_id: Unique task identifier (UUID).
        task_type: Type of task ('fetch_papers', 'generate_report', etc.).
        status: Task status ('pending', 'processing', 'completed', 'failed').
        step: Current step name.
        progress: Progress percentage (0-100).
        started_at: Task start timestamp.
        completed_at: Task completion timestamp (nullable).
        error_message: Error message if task failed.
        total_papers: Total number of papers to process.
        processed_papers: Number of papers successfully processed.
        failed_papers: Number of papers that failed to process.
        steps: Related TaskStep records.
    """

    __tablename__ = "task_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_papers: Mapped[int] = mapped_column(Integer, default=0)
    processed_papers: Mapped[int] = mapped_column(Integer, default=0)
    failed_papers: Mapped[int] = mapped_column(Integer, default=0)

    # Relationship to task steps
    steps: Mapped[List["TaskStep"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TaskHistory(task_id={self.task_id}, type={self.task_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """
        Convert task history to dictionary representation.

        Returns:
            Dictionary containing all task history fields.
        """
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "step": self.step,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "total_papers": self.total_papers,
            "processed_papers": self.processed_papers,
            "failed_papers": self.failed_papers,
        }


class TaskStep(Base):
    """
    Model representing individual steps within a task execution.

    Tracks timing and status for each step in a workflow task,
    enabling detailed performance analysis.

    Attributes:
        id: Primary key.
        task_id: Foreign key to TaskHistory.
        step_name: Name of the step.
        status: Step status ('pending', 'processing', 'completed', 'failed').
        started_at: Step start timestamp.
        completed_at: Step completion timestamp (nullable).
        duration_ms: Step duration in milliseconds (nullable).
        task: Related TaskHistory object.
    """

    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("task_history.task_id"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship to task history
    task: Mapped["TaskHistory"] = relationship(back_populates="steps")

    def __repr__(self) -> str:
        return f"<TaskStep(task_id={self.task_id}, step={self.step_name}, status={self.status})>"

    def to_dict(self) -> dict:
        """
        Convert task step to dictionary representation.

        Returns:
            Dictionary containing all task step fields.
        """
        return {
            "id": self.id,
            "task_id": self.task_id,
            "step_name": self.step_name,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class SchedulerConfig(Base):
    """
    Model representing automatic task scheduler configuration.

    Stores settings for periodic task execution (daily/weekly).

    Attributes:
        id: Primary key (singleton, always 1).
        enabled: Whether automatic scheduling is enabled.
        schedule_type: Type of schedule ('daily' or 'weekly').
        daily_time: Time for daily execution (HH:MM format).
        weekly_day: Day of week for weekly execution (0=Monday, 6=Sunday).
        weekly_time: Time for weekly execution (HH:MM format).
        last_run_at: Timestamp of last execution.
        next_run_at: Timestamp of next scheduled execution.
        created_at: Configuration creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "scheduler_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_type: Mapped[str] = mapped_column(String(10), default="daily")
    daily_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    weekly_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weekly_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    def __repr__(self) -> str:
        return f"<SchedulerConfig(enabled={self.enabled}, type={self.schedule_type})>"

    def to_dict(self) -> dict:
        """
        Convert scheduler config to dictionary representation.

        Returns:
            Dictionary containing all config fields.
        """
        return {
            "id": self.id,
            "enabled": self.enabled,
            "schedule_type": self.schedule_type,
            "daily_time": self.daily_time,
            "weekly_day": self.weekly_day,
            "weekly_time": self.weekly_time,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
    # Import test utilities to check if we're in test mode
    try:
        from tests.test_utils import is_test_mode, assert_test_db_url

        # If test mode is enabled, validate that we're using a test database
        if is_test_mode():
            assert_test_db_url(database_url, "init_db()")
    except ImportError:
        # test_utils not available (not in test environment)
        pass

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return Session(engine)

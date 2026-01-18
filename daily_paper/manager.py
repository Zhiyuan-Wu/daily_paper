"""
Download manager for orchestrating multiple paper downloaders.

This module provides the DownloadManager class which coordinates
multiple downloaders, manages the database, and handles paper
deduplication.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Type

from sqlalchemy.orm import Session

from daily_paper.config import Config, PathConfig
from daily_paper.database import init_db, Paper
from daily_paper.downloaders.base import BaseDownloader, PaperMetadata

logger = logging.getLogger(__name__)


class DownloadManager:
    """
    Orchestrates multiple downloaders and manages paper database.

    The download manager coordinates paper fetching from multiple sources,
    handles deduplication, and maintains the paper database. It provides
    a unified interface for downloading papers regardless of source.

    Typical usage:
        >>> config = Config.from_env()
        >>> manager = DownloadManager(config)
        >>> papers = manager.fetch_papers_by_date(date(2024, 1, 15))
        >>> for paper in papers:
        ...     manager.download_paper(paper)

    Attributes:
        config: Application configuration.
        downloaders: Registered downloader instances keyed by source name.
        session: SQLAlchemy database session.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the download manager.

        Args:
            config: Application configuration. If None, loads from environment.
        """
        self.config = config or Config.from_env()
        self.session: Session = init_db(self.config.database.url)
        self.downloaders: Dict[str, BaseDownloader] = {}

        # Register default downloaders
        self._register_default_downloaders()

    def _register_default_downloaders(self) -> None:
        """
        Register default downloader instances.

        Instantiates and registers ArxivDownloader and HuggingFaceDownloader
        with their configured categories.
        """
        from daily_paper.downloaders.arxiv_downloader import ArxivDownloader
        from daily_paper.downloaders.huggingface_downloader import HuggingFaceDownloader

        # Register arXiv downloader
        arxiv_downloader = ArxivDownloader(
            categories=self.config.arxiv.categories,
            max_results=self.config.arxiv.max_results,
        )
        self.register_downloader(arxiv_downloader)

        # Register HuggingFace downloader
        hf_downloader = HuggingFaceDownloader()
        self.register_downloader(hf_downloader)

    def register_downloader(self, downloader: BaseDownloader) -> None:
        """
        Register a downloader instance.

        Args:
            downloader: Downloader instance to register.

        Raises:
            ValueError: If a downloader with the same source_name is already registered.
        """
        source_name = downloader.source_name
        if source_name in self.downloaders:
            raise ValueError(f"Downloader for '{source_name}' already registered")

        self.downloaders[source_name] = downloader
        logger.info(f"Registered downloader: {source_name}")

    def get_downloader(self, source: str) -> Optional[BaseDownloader]:
        """
        Get a registered downloader by source name.

        Args:
            source: Source name (e.g., 'arxiv', 'huggingface').

        Returns:
            The downloader instance if found, None otherwise.
        """
        return self.downloaders.get(source)

    def _paper_exists(self, source: str, paper_id: str) -> Optional[Paper]:
        """
        Check if a paper already exists in the database.

        Args:
            source: Paper source.
            paper_id: Paper ID within that source.

        Returns:
            Existing Paper record if found, None otherwise.
        """
        return (
            self.session.query(Paper)
            .filter_by(source=source, paper_id=paper_id)
            .first()
        )

    def _create_paper_record(self, metadata: PaperMetadata) -> Paper:
        """
        Create a new Paper record from metadata.

        Args:
            metadata: Paper metadata from downloader.

        Returns:
            Created Paper record (not yet committed to database).
        """
        paper = Paper(
            source=metadata.source,
            paper_id=metadata.paper_id,
            title=metadata.title,
            authors=", ".join(metadata.authors) if metadata.authors else None,
            abstract=metadata.abstract,
            published_date=metadata.published_date,
            url=metadata.url,
        )
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def fetch_papers_by_date(self, target_date: date, sources: Optional[List[str]] = None) -> List[Paper]:
        """
        Fetch papers for a specific date from configured sources.

        Queries all registered downloaders (or specified sources) for
        papers published on the target date. Creates database records
        for new papers.

        Args:
            target_date: Date to fetch papers for.
            sources: Optional list of source names to query. If None, queries all.

        Returns:
            List of Paper records (both newly created and existing).
        """
        sources_to_query = sources or list(self.downloaders.keys())
        all_papers: List[Paper] = []

        for source in sources_to_query:
            downloader = self.get_downloader(source)
            if not downloader:
                logger.warning(f"No downloader registered for source: {source}")
                continue

            try:
                metadata_list = downloader.get_papers_by_date(target_date)
                logger.info(
                    f"Found {len(metadata_list)} papers from {source} for {target_date}"
                )

                for metadata in metadata_list:
                    # Check if paper already exists
                    existing = self._paper_exists(metadata.source, metadata.paper_id)
                    if existing:
                        all_papers.append(existing)
                    else:
                        # Create new record
                        paper = self._create_paper_record(metadata)
                        all_papers.append(paper)

            except Exception as e:
                logger.error(f"Error fetching papers from {source}: {e}")

        return all_papers

    def download_paper(self, paper: Paper) -> Path:
        """
        Download the PDF for a paper.

        Downloads the PDF using the appropriate downloader and updates
        the paper record with the file path.

        Args:
            paper: Paper record to download PDF for.

        Returns:
            Path to the downloaded PDF file.

        Raises:
            ValueError: If no downloader is registered for the paper's source.
            FileNotFoundError: If the paper cannot be found.
            IOError: If the download fails.
        """
        downloader = self.get_downloader(paper.source)
        if not downloader:
            raise ValueError(f"No downloader registered for source: {paper.source}")

        # Download to configured directory
        dest_dir = self.config.paths.download_dir
        pdf_path = downloader.download_paper(paper.paper_id, dest_dir)

        # Update paper record
        paper.pdf_path = str(pdf_path)
        self.session.commit()

        logger.info(f"Downloaded PDF for {paper.paper_id}: {pdf_path}")
        return pdf_path

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """
        Get a paper by database ID.

        Args:
            paper_id: Database primary key.

        Returns:
            Paper record if found, None otherwise.
        """
        return self.session.query(Paper).filter_by(id=paper_id).first()

    def get_papers_by_source(self, source: str, limit: int = 100) -> List[Paper]:
        """
        Get papers from a specific source.

        Args:
            source: Source name (e.g., 'arxiv', 'huggingface').
            limit: Maximum number of papers to return.

        Returns:
            List of Paper records from the specified source.
        """
        return (
            self.session.query(Paper)
            .filter_by(source=source)
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .all()
        )

    def get_papers_without_pdf(self, limit: int = 100) -> List[Paper]:
        """
        Get papers that don't have a downloaded PDF.

        Args:
            limit: Maximum number of papers to return.

        Returns:
            List of Paper records without PDF files.
        """
        return (
            self.session.query(Paper)
            .filter(Paper.pdf_path.is_(None))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .all()
        )

    def close(self) -> None:
        """Close the database session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

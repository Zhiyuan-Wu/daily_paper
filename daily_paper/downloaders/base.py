"""
Base downloader interface for paper sources.

This module defines the abstract interface that all downloaders must implement.
The plugin architecture allows new paper sources to be added without modifying
the core system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional


@dataclass
class PaperMetadata:
    """
    Metadata about a paper from a source.

    This dataclass encapsulates the core information about a paper that
    is common across all sources. It's used to transfer paper information
    between downloaders and the download manager.

    Attributes:
        source: The paper source identifier (e.g., 'arxiv', 'huggingface').
        paper_id: Source-specific paper identifier.
        title: Paper title.
        authors: List of author names.
        abstract: Paper abstract or description.
        published_date: Publication date.
        url: URL to the paper page.
        pdf_url: Direct URL to download the PDF.
    """

    source: str
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    published_date: Optional[date]
    url: str
    pdf_url: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Convert metadata to dictionary.

        Returns:
            Dictionary representation of the metadata.
        """
        return {
            "source": self.source,
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "url": self.url,
            "pdf_url": self.pdf_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperMetadata":
        """
        Create metadata from dictionary.

        Args:
            data: Dictionary containing metadata fields.

        Returns:
            A PaperMetadata instance.
        """
        return cls(
            source=data["source"],
            paper_id=data["paper_id"],
            title=data["title"],
            authors=data["authors"],
            abstract=data["abstract"],
            published_date=date.fromisoformat(data["published_date"]) if data.get("published_date") else None,
            url=data["url"],
            pdf_url=data.get("pdf_url"),
        )


class BaseDownloader(ABC):
    """
    Abstract base class for paper downloaders.

    All downloader implementations must inherit from this class and
    implement the abstract methods. This interface ensures consistent
    behavior across different paper sources.

    The typical workflow is:
    1. Call get_papers_by_date() to get a list of papers for a specific date
    2. Call download_paper() for each paper to download the PDF

    Example:
        >>> downloader = ArxivDownloader(categories=['cs.AI'])
        >>> papers = downloader.get_papers_by_date(date(2024, 1, 15))
        >>> for paper in papers:
        ...     pdf_path = downloader.download_paper(paper.paper_id, "/data/papers")
    """

    @abstractmethod
    def get_papers_by_date(self, target_date: date) -> List[PaperMetadata]:
        """
        Fetch papers published on a specific date.

        Implementations should query their respective paper sources and
        return a list of papers published on the given date. If the source
        doesn't support precise date filtering, implementations should
        return papers from a reasonable time window.

        Args:
            target_date: The date to fetch papers for.

        Returns:
            List of PaperMetadata objects for papers from the target date.
        """
        pass

    @abstractmethod
    def download_paper(self, paper_id: str, dest_dir: Path) -> Path:
        """
        Download the PDF for a specific paper.

        Downloads the PDF file and saves it to the destination directory.
        The filename should be derived from the paper_id and/or title.

        Args:
            paper_id: Source-specific paper identifier.
            dest_dir: Directory to save the downloaded PDF.

        Returns:
            Path to the downloaded PDF file.

        Raises:
            FileNotFoundError: If the paper cannot be found.
            IOError: If the download fails.
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        Return the name of this paper source.

        Returns:
            String identifier for the source (e.g., 'arxiv', 'huggingface').
        """
        pass

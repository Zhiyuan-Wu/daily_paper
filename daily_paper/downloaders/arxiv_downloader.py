"""
arXiv paper downloader implementation.

This module implements the BaseDownloader interface for fetching papers
from arXiv.org. It uses the arxiv library to query and download papers.

The downloader supports:
- Configurable arXiv categories (e.g., cs.AI, cs.LG)
- Date-based paper filtering
- PDF download with local caching
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import arxiv as arxiv_lib

from daily_paper.downloaders.base import BaseDownloader, PaperMetadata

logger = logging.getLogger(__name__)


class ArxivDownloader(BaseDownloader):
    """
    Downloader for arXiv papers.

    Uses the arxiv library to query and download papers from arXiv.org.
    Supports configurable categories and date-based filtering.

    Typical usage:
        >>> downloader = ArxivDownloader(categories=['cs.AI', 'cs.LG'])
        >>> papers = downloader.get_papers_by_date(date(2024, 1, 15))
        >>> pdf_path = downloader.download_paper('2301.12345', Path('data/papers'))

    Attributes:
        categories: List of arXiv categories to query (e.g., ['cs.AI', 'cs.LG']).
        max_results: Maximum number of papers to fetch per query.
    """

    # Common arXiv category prefixes
    CATEGORY_PREFIXES = {
        "cs": "Computer Science",
        "stat": "Statistics",
        "math": "Mathematics",
        "physics": "Physics",
        "q-bio": "Quantitative Biology",
        "q-fin": "Quantitative Finance",
    }

    def __init__(self, categories: Optional[List[str]] = None, max_results: int = 3):
        """
        Initialize the arXiv downloader.

        Args:
            categories: List of arXiv categories to fetch (e.g., ['cs.AI', 'cs.LG']).
                       If None, defaults to cs.AI.
            max_results: Maximum number of papers to fetch per query.
        """
        self.categories = categories or ["cs.AI"]
        self.max_results = max_results
        self._client = arxiv_lib.Client(
            page_size=100, delay_seconds=3.0, num_retries=3
        )

    @property
    def source_name(self) -> str:
        """Return 'arxiv' as the source identifier."""
        return "arxiv"

    def _build_date_query(self, target_date: date) -> str:
        """
        Build arXiv query string for date filtering.

        arXiv doesn't support direct date filtering in queries. This method
        builds a category query and then filters results by date after fetching.

        Args:
            target_date: The target date for filtering.

        Returns:
            Query string for arXiv API.
        """
        # Build category query: cat:cs.AI OR cat:cs.LG OR ...
        category_query = " OR ".join(f"cat:{cat}" for cat in self.categories)
        return category_query

    def _is_same_date(self, dt: datetime, target_date: date) -> bool:
        """
        Check if a datetime is on the same day as target_date.

        Handles timezone-aware datetimes by converting to date.

        Args:
            dt: DateTime to check.
            target_date: Target date for comparison.

        Returns:
            True if dt is on the same day as target_date.
        """
        if dt is None:
            return False

        # Get date from datetime (handles both timezone-aware and naive datetimes)
        try:
            dt_date = dt.date() if hasattr(dt, "date") else dt
        except AttributeError:
            return False

        return dt_date == target_date

    def _extract_arxiv_id(self, url: str) -> str:
        """
        Extract arXiv ID from a URL.

        Handles both old-style (cs.AI/1234567) and new-style (2301.12345) IDs.

        Args:
            url: arXiv paper URL.

        Returns:
            The extracted arXiv ID.

        Examples:
            >>> downloader._extract_arxiv_id('https://arxiv.org/abs/2301.12345v1')
            '2301.12345v1'
            >>> downloader._extract_arxiv_id('https://arxiv.org/abs/cs.AI/1234567')
            'cs.AI/1234567'
        """
        # Extract ID from URL path (handle both old and new style IDs)
        match = re.search(r"/abs/(.+?)/?$", url)
        if match:
            return match.group(1)
        # Fallback: try to extract from the end of URL
        return url.rstrip("/").split("/")[-1]

    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize a paper title for use as a filename.

        Removes or replaces characters that are not allowed in filenames.

        Args:
            title: The paper title to sanitize.

        Returns:
            A sanitized filename-safe string.
        """
        # Replace invalid characters with underscores
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, "_", title)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(". ")
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        return sanitized

    def get_papers_by_date(self, target_date: date) -> List[PaperMetadata]:
        """
        Fetch arXiv papers published on a specific date.

        Note: arXiv API doesn't support precise date filtering. This method
        fetches recent papers in the configured categories and filters by
        date locally. For more comprehensive results, it queries a range
        around the target date.

        Args:
            target_date: The date to fetch papers for.

        Returns:
            List of PaperMetadata for papers published on target_date.
        """
        logger.info(f"Fetching arXiv papers for {target_date} from categories: {self.categories}")

        query = self._build_date_query(target_date)
        search = arxiv_lib.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv_lib.SortCriterion.SubmittedDate,
            sort_order=arxiv_lib.SortOrder.Descending,
        )

        papers: List[PaperMetadata] = []

        # Fetch results and filter by date
        logger.debug(f"Querying arXiv API with max_results={self.max_results}")
        for result in self._client.results(search):
            published_date = result.published

            # Check if this paper is from the target date
            if self._is_same_date(published_date, target_date):
                arxiv_id = self._extract_arxiv_id(result.entry_id)

                metadata = PaperMetadata(
                    source=self.source_name,
                    paper_id=arxiv_id,
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary.replace("\n", " ").strip(),
                    published_date=published_date.date() if published_date else None,
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                )
                papers.append(metadata)
                logger.debug(f"Matched paper: {arxiv_id} - {result.title[:50]}...")

        logger.info(f"Found {len(papers)} arXiv papers for {target_date}")
        return papers

    def download_paper(self, paper_id: str, dest_dir: Path) -> Path:
        """
        Download the PDF for an arXiv paper.

        Downloads the PDF file and saves it with a filename based on the
        paper ID and title. If the PDF already exists (determined by
        hash comparison), it skips the download.

        Args:
            paper_id: arXiv paper ID (e.g., '2301.12345' or '2301.12345v1').
            dest_dir: Directory to save the downloaded PDF.

        Returns:
            Path to the downloaded PDF file.

        Raises:
            FileNotFoundError: If the paper cannot be found on arXiv.
            IOError: If the download fails.
        """
        logger.info(f"Starting download for arXiv paper {paper_id}")

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Remove version suffix for filename consistency
        base_id = paper_id.split("v")[0]

        # First, query to get paper info for proper filename
        search = arxiv_lib.Search(id_list=[paper_id])
        try:
            result = next(self._client.results(search))
            logger.debug(f"Retrieved metadata for {paper_id}: {result.title[:50]}...")
        except StopIteration:
            logger.error(f"Paper not found on arXiv: {paper_id}")
            raise FileNotFoundError(f"Paper not found on arXiv: {paper_id}")

        # Create filename: ID_sanitized_title.pdf
        title_part = self._sanitize_filename(result.title)
        filename = f"{base_id}_{title_part}.pdf"
        dest_path = dest_dir / filename

        # Check if file already exists
        if dest_path.exists():
            file_size = dest_path.stat().st_size / (1024 * 1024)
            logger.info(f"PDF already exists: {dest_path.name} ({file_size:.2f} MB)")
            return dest_path

        # Download the PDF
        try:
            logger.debug(f"Downloading PDF to {dest_path}")
            downloaded_path = result.download_pdf(dest_dir, filename=filename)
            file_size = Path(downloaded_path).stat().st_size / (1024 * 1024)
            logger.info(
                f"Successfully downloaded arXiv PDF {paper_id}: "
                f"{dest_path.name} ({file_size:.2f} MB)"
            )
            return Path(downloaded_path)
        except Exception as e:
            logger.error(f"Failed to download PDF for {paper_id}: {e}")
            raise IOError(f"Failed to download PDF for {paper_id}: {e}")

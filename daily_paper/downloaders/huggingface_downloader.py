"""
HuggingFace Daily Papers downloader implementation.

This module implements the BaseDownloader interface for fetching papers
from HuggingFace's daily papers page (https://huggingface.co/papers).

The HuggingFace papers page displays papers submitted for a specific date.
Most papers on HuggingFace are actually from arXiv, so this downloader
extracts arXiv IDs and then fetches metadata from arXiv.

Implementation uses web scraping with requests and BeautifulSoup.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import arxiv as arxiv_lib
import requests
from bs4 import BeautifulSoup

from daily_paper.downloaders.base import BaseDownloader, PaperMetadata


@dataclass
class HuggingFacePaper:
    """
    Raw paper data extracted from HuggingFace.

    Attributes:
        paper_id: The paper ID from HuggingFace (usually an arXiv ID).
        title: Paper title.
        url: URL to the HuggingFace paper page.
        thumbnail_url: URL to the paper thumbnail image.
    """

    paper_id: str
    title: str
    url: str
    thumbnail_url: Optional[str] = None


class HuggingFaceDownloader(BaseDownloader):
    """
    Downloader for HuggingFace Daily Papers.

    Scrapes the HuggingFace papers page (https://huggingface.co/papers/date/YYYY-MM-DD)
    to get papers for a specific date. Since most papers are from arXiv, it extracts
    the arXiv IDs and fetches detailed metadata from arXiv API.

    Typical usage:
        >>> downloader = HuggingFaceDownloader()
        >>> papers = downloader.get_papers_by_date(date(2024, 1, 15))
        >>> pdf_path = downloader.download_paper('2301.12345', Path('data/papers'))

    Attributes:
        base_url: Base URL for HuggingFace papers.
        arxiv_client: arXiv client for fetching paper metadata.
        request_timeout: Timeout for HTTP requests in seconds.
    """

    BASE_URL = "https://huggingface.co/papers"

    def __init__(self, request_timeout: int = 30):
        """
        Initialize the HuggingFace downloader.

        Args:
            request_timeout: Timeout for HTTP requests in seconds.
        """
        self.arxiv_client = arxiv_lib.Client(
            page_size=100, delay_seconds=0.3, num_retries=3
        )
        self.request_timeout = request_timeout

        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; DailyPaperBot/1.0)"
        })

    @property
    def source_name(self) -> str:
        """Return 'huggingface' as the source identifier."""
        return "huggingface"

    def _build_date_url(self, target_date: date) -> str:
        """
        Build the URL for papers on a specific date.

        Args:
            target_date: The target date.

        Returns:
            URL to the HuggingFace papers page for that date.
        """
        date_str = target_date.strftime("%Y-%m-%d")
        return f"{self.BASE_URL}/date/{date_str}"

    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize a paper title for use as a filename.

        Args:
            title: The paper title to sanitize.

        Returns:
            A sanitized filename-safe string.
        """
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, "_", title)
        sanitized = sanitized.strip(". ")
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        return sanitized

    def _parse_paper_id(self, paper_id: str) -> str:
        """
        Parse and normalize a paper ID from HuggingFace.

        HuggingFace paper IDs are typically arXiv IDs (e.g., '2301.09668').
        This method normalizes the ID for use with arXiv API.

        Args:
            paper_id: Raw paper ID from HuggingFace.

        Returns:
            Normalized paper ID (typically arXiv ID).
        """
        # Remove any URL prefixes or suffixes
        paper_id = paper_id.strip()

        # Extract just the ID if it's embedded in a URL
        match = re.search(r'(\d{4}\.\d{4,5})', paper_id)
        if match:
            return match.group(1)

        return paper_id

    def _fetch_page(self, url: str) -> str:
        """
        Fetch a web page and return its HTML content.

        Args:
            url: URL to fetch.

        Returns:
            HTML content as string.

        Raises:
            requests.RequestException: If the HTTP request fails.
        """
        response = self._session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        return response.text

    def _parse_papers_page(self, html: str) -> List[HuggingFacePaper]:
        """
        Parse papers from HuggingFace HTML page.

        Extracts paper information from the HuggingFace daily papers page.
        The page structure uses specific CSS classes and data attributes.

        Args:
            html: HTML content of the papers page.

        Returns:
            List of HuggingFacePaper objects extracted from the page.
        """
        soup = BeautifulSoup(html, "html.parser")
        papers: List[HuggingFacePaper] = []
        seen_ids = set()  # Avoid duplicates

        # HuggingFace uses specific elements for paper cards
        # Look for links to paper pages (only actual papers, not navigation links)
        paper_links = soup.find_all("a", href=re.compile(r"^/papers/\d{4}\.\d{4,5}"))

        for link in paper_links:
            href = link.get("href", "")
            # Extract paper ID from URL (e.g., /papers/2301.09668)
            match = re.search(r"/papers/([^/]+)", href)
            if not match:
                continue

            paper_id = match.group(1)

            # Skip duplicates
            if paper_id in seen_ids:
                continue
            seen_ids.add(paper_id)

            # Get title from the link text or nearby element
            title_elem = link.find("span") or link
            title = title_elem.get_text(strip=True)

            # Get thumbnail if available
            thumbnail = None
            img_elem = link.find("img")
            if img_elem:
                thumbnail = img_elem.get("src")

            papers.append(
                HuggingFacePaper(
                    paper_id=paper_id,
                    title=title,
                    url=urljoin(self.BASE_URL, href),
                    thumbnail_url=thumbnail,
                )
            )

        return papers

    def _fetch_arxiv_metadata(self, arxiv_id: str) -> Optional[PaperMetadata]:
        """
        Fetch detailed metadata from arXiv for a paper ID.

        Since HuggingFace only provides basic info (ID, title), we fetch
        full metadata from arXiv API.

        Args:
            arxiv_id: arXiv paper ID.

        Returns:
            PaperMetadata with detailed information, or None if not found.
        """
        search = arxiv_lib.Search(id_list=[arxiv_id])
        try:
            result = next(self.arxiv_client.results(search))
        except StopIteration:
            return None

        return PaperMetadata(
            source=self.source_name,
            paper_id=arxiv_id,
            title=result.title,
            authors=[author.name for author in result.authors],
            abstract=result.summary.replace("\n", " ").strip(),
            published_date=result.published.date() if result.published else None,
            url=result.entry_id,
            pdf_url=result.pdf_url,
        )

    def get_papers_by_date(self, target_date: date) -> List[PaperMetadata]:
        """
        Fetch HuggingFace papers for a specific date.

        Scrapes the HuggingFace daily papers page and fetches detailed
        metadata from arXiv for each paper found.

        Args:
            target_date: The date to fetch papers for.

        Returns:
            List of PaperMetadata for papers from target_date.
        """
        url = self._build_date_url(target_date)

        try:
            html = self._fetch_page(url)
        except requests.RequestException as e:
            # If the page doesn't exist or fails, return empty list
            return []

        hf_papers = self._parse_papers_page(html)
        papers: List[PaperMetadata] = []

        for hf_paper in hf_papers:
            # Parse the paper ID (should be arXiv ID)
            arxiv_id = self._parse_paper_id(hf_paper.paper_id)

            # Fetch detailed metadata from arXiv
            metadata = self._fetch_arxiv_metadata(arxiv_id)
            if metadata:
                # Override source to indicate it came from HuggingFace
                metadata.source = self.source_name
                papers.append(metadata)

        return papers

    def download_paper(self, paper_id: str, dest_dir: Path) -> Path:
        """
        Download the PDF for a HuggingFace paper.

        Since HuggingFace papers are typically from arXiv, this method
        downloads from arXiv using the paper ID.

        Args:
            paper_id: Paper ID (typically arXiv ID like '2301.09668').
            dest_dir: Directory to save the downloaded PDF.

        Returns:
            Path to the downloaded PDF file.

        Raises:
            FileNotFoundError: If the paper cannot be found.
            IOError: If the download fails.
        """
        # Parse paper ID to get arXiv ID
        arxiv_id = self._parse_paper_id(paper_id)

        # Fetch paper info from arXiv
        search = arxiv_lib.Search(id_list=[arxiv_id])
        try:
            result = next(self.arxiv_client.results(search))
        except StopIteration:
            raise FileNotFoundError(f"Paper not found: {paper_id}")

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        title_part = self._sanitize_filename(result.title)
        filename = f"{arxiv_id}_{title_part}.pdf"
        dest_path = dest_dir / filename

        # Download from arXiv
        try:
            downloaded_path = result.download_pdf(dest_dir, filename=filename)
            return Path(downloaded_path)
        except Exception as e:
            raise IOError(f"Failed to download PDF for {paper_id}: {e}")

    def __del__(self):
        """Clean up the HTTP session on deletion."""
        if hasattr(self, "_session"):
            self._session.close()

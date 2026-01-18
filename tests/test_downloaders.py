"""
Unit tests for paper downloaders.

Tests the base downloader interface, arXiv downloader, and HuggingFace
downloader with mocked responses and real API calls.
"""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from daily_paper.downloaders.base import BaseDownloader, PaperMetadata
from daily_paper.downloaders.arxiv_downloader import ArxivDownloader
from daily_paper.downloaders.huggingface_downloader import HuggingFaceDownloader


class TestPaperMetadata:
    """Tests for PaperMetadata dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = PaperMetadata(
            source="arxiv",
            paper_id="2301.12345",
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            abstract="Test abstract",
            published_date=date(2024, 1, 15),
            url="https://arxiv.org/abs/2301.12345",
            pdf_url="https://arxiv.org/pdf/2301.12345.pdf",
        )

        result = metadata.to_dict()

        assert result["source"] == "arxiv"
        assert result["paper_id"] == "2301.12345"
        assert result["title"] == "Test Paper"
        assert result["authors"] == ["Author 1", "Author 2"]
        assert result["abstract"] == "Test abstract"
        assert result["published_date"] == "2024-01-15"
        assert result["url"] == "https://arxiv.org/abs/2301.12345"
        assert result["pdf_url"] == "https://arxiv.org/pdf/2301.12345.pdf"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "source": "arxiv",
            "paper_id": "2301.12345",
            "title": "Test Paper",
            "authors": ["Author 1", "Author 2"],
            "abstract": "Test abstract",
            "published_date": "2024-01-15",
            "url": "https://arxiv.org/abs/2301.12345",
            "pdf_url": "https://arxiv.org/pdf/2301.12345.pdf",
        }

        metadata = PaperMetadata.from_dict(data)

        assert metadata.source == "arxiv"
        assert metadata.paper_id == "2301.12345"
        assert metadata.title == "Test Paper"
        assert metadata.published_date == date(2024, 1, 15)


class TestArxivDownloader:
    """Tests for ArxivDownloader."""

    def test_source_name(self):
        """Test source name property."""
        downloader = ArxivDownloader()
        assert downloader.source_name == "arxiv"

    def test_build_date_query(self):
        """Test date query building."""
        downloader = ArxivDownloader(categories=["cs.AI", "cs.LG"])
        query = downloader._build_date_query(date(2024, 1, 15))
        assert query == "cat:cs.AI OR cat:cs.LG"

    def test_extract_arxiv_id(self):
        """Test arXiv ID extraction from URL."""
        downloader = ArxivDownloader()

        # Test new-style ID
        id1 = downloader._extract_arxiv_id("https://arxiv.org/abs/2301.12345v1")
        assert id1 == "2301.12345v1"

        # Test old-style ID
        id2 = downloader._extract_arxiv_id("https://arxiv.org/abs/cs.AI/1234567")
        assert id2 == "cs.AI/1234567"

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        downloader = ArxivDownloader()

        # Test with invalid characters
        sanitized = downloader._sanitize_filename('Test: Paper/Name\\With|Invalid*Chars')
        assert ":" not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert "|" not in sanitized
        assert "*" not in sanitized

        # Test length limit
        long_title = "A" * 300
        sanitized = downloader._sanitize_filename(long_title)
        assert len(sanitized) <= 200

    @patch("daily_paper.downloaders.arxiv_downloader.arxiv_lib.Client")
    def test_get_papers_by_date_empty(self, mock_client_class):
        """Test get_papers_by_date with no results."""
        mock_client = Mock()
        mock_client.results.return_value = []
        mock_client_class.return_value = mock_client

        downloader = ArxivDownloader()
        papers = downloader.get_papers_by_date(date(2024, 1, 15))

        assert papers == []

    @patch("daily_paper.downloaders.arxiv_downloader.arxiv_lib.Client")
    def test_get_papers_by_date_with_results(self, mock_client_class):
        """Test get_papers_by_date with results."""
        # Create mock result
        mock_result = Mock()
        mock_result.entry_id = "https://arxiv.org/abs/2301.12345v1"
        mock_result.title = "Test Paper"
        mock_result.authors = [Mock(name="Author One"), Mock(name="Author Two")]
        mock_result.summary = "Test abstract"
        mock_result.published = None  # Will be filtered out
        mock_result.pdf_url = "https://arxiv.org/pdf/2301.12345v1.pdf"

        mock_client = Mock()
        mock_client.results.return_value = iter([mock_result])
        mock_client_class.return_value = mock_client

        downloader = ArxivDownloader()
        papers = downloader.get_papers_by_date(date(2024, 1, 15))

        # No papers because published date doesn't match
        assert papers == []


class TestHuggingFaceDownloader:
    """Tests for HuggingFaceDownloader."""

    def test_source_name(self):
        """Test source name property."""
        downloader = HuggingFaceDownloader()
        assert downloader.source_name == "huggingface"

    def test_build_date_url(self):
        """Test date URL building."""
        downloader = HuggingFaceDownloader()
        url = downloader._build_date_url(date(2024, 1, 15))
        assert url == "https://huggingface.co/papers/date/2024-01-15"

    def test_parse_paper_id(self):
        """Test paper ID parsing."""
        downloader = HuggingFaceDownloader()

        # Test arXiv-style ID
        parsed = downloader._parse_paper_id("2301.09668")
        assert parsed == "2301.09668"

        # Test URL-embedded ID
        parsed = downloader._parse_paper_id("https://huggingface.co/papers/2301.09668")
        assert parsed == "2301.09668"

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        downloader = HuggingFaceDownloader()

        sanitized = downloader._sanitize_filename('Test: Paper/Name')
        assert ":" not in sanitized
        assert "/" not in sanitized


@pytest.mark.integration
@pytest.mark.slow
class TestArxivDownloaderReal:
    """Integration tests for ArxivDownloader with real API calls."""

    def test_real_arxiv_fetch_recent_papers(self):
        """Test fetching real papers from arXiv API."""
        downloader = ArxivDownloader(categories=["cs.AI", "cs.LG"], max_results=2)

        # Fetch papers for a recent date
        papers = downloader.get_papers_by_date(date.today())

        # Verify we got a list
        assert isinstance(papers, list)

        # If papers were returned, validate their structure
        for paper in papers:
            assert isinstance(paper, PaperMetadata)
            assert paper.source == "arxiv"
            assert paper.paper_id is not None
            assert len(paper.paper_id) > 0
            assert paper.title is not None
            assert len(paper.title) > 0
            assert paper.url is not None
            assert paper.url.startswith("https://arxiv.org/")
            assert paper.pdf_url is not None
            assert paper.pdf_url.startswith("https://arxiv.org/pdf/")
            assert paper.published_date is not None

            # Verify authors is a list
            assert isinstance(paper.authors, list)
            if len(paper.authors) > 0:
                assert isinstance(paper.authors[0], str)

    def test_real_arxiv_fetch_with_specific_date(self):
        """Test fetching papers for a specific date that should have results."""
        downloader = ArxivDownloader(categories=["cs.AI"], max_results=2)

        # Use a date from 2024 that's likely to have papers
        test_date = date(2024, 1, 15)

        papers = downloader.get_papers_by_date(test_date)

        # Verify structure
        assert isinstance(papers, list)

        # If we got results, verify they match the date
        for paper in papers:
            assert isinstance(paper, PaperMetadata)
            # Note: arXiv might return papers from nearby dates
            assert paper.published_date is not None


@pytest.mark.integration
@pytest.mark.slow
class TestHuggingFaceDownloaderReal:
    """Integration tests for HuggingFaceDownloader with real API calls."""

    def test_real_huggingface_fetch_recent_papers(self):
        """Test fetching real papers from HuggingFace API."""
        downloader = HuggingFaceDownloader()

        # Use a date that's likely to have papers (not today which might be empty)
        # Go back a few days to ensure data exists
        from datetime import timedelta
        test_date = date.today() - timedelta(days=3)

        papers = downloader.get_papers_by_date(test_date)

        # Verify we got a list
        assert isinstance(papers, list)

        # Only validate first few papers to save time
        for paper in papers[:2]:  # Limit to first 2 papers to speed up tests
            assert isinstance(paper, PaperMetadata)
            assert paper.source == "huggingface"
            assert paper.paper_id is not None
            assert len(paper.paper_id) > 0
            assert paper.title is not None
            assert len(paper.title) > 0
            assert paper.url is not None
            # Note: URL may be from arXiv since HuggingFace fetches detailed metadata from arXiv
            assert paper.url.startswith(("https://huggingface.co/", "http://arxiv.org/abs/", "https://arxiv.org/abs/"))
            assert paper.pdf_url is not None
            assert paper.published_date is not None

            # Verify authors is a list
            assert isinstance(paper.authors, list)
            if len(paper.authors) > 0:
                assert isinstance(paper.authors[0], str)

    def test_real_huggingface_fetch_with_specific_date(self):
        """Test fetching papers for a specific date."""
        downloader = HuggingFaceDownloader()

        # Use a date that's likely to have papers
        test_date = date(2024, 1, 15)

        papers = downloader.get_papers_by_date(test_date)

        # Verify structure
        assert isinstance(papers, list)

        # Only validate first paper if any exist
        if len(papers) > 0:
            paper = papers[0]
            assert isinstance(paper, PaperMetadata)
            assert paper.published_date is not None
            assert paper.source == "huggingface"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

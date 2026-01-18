"""
Unit tests for paper downloaders.

Tests the base downloader interface, arXiv downloader, and HuggingFace
downloader with mocked responses.
"""

import pytest
from datetime import date
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Unit tests for PDF parser module.

Tests the PDFParser with mocked PyMuPDF and OCR service.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from daily_paper.parsers.pdf_parser import PDFParser, ParseResult, Section
from daily_paper.config import OCRConfig
from daily_paper.database import Paper


class TestSection:
    """Tests for Section dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        section = Section(
            title="Introduction",
            content="This is the introduction content.",
            page_number=1,
        )

        result = section.to_dict()

        assert result["title"] == "Introduction"
        assert result["content"] == "This is the introduction content."
        assert result["page_number"] == 1


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ParseResult(
            text="Extracted text",
            sections=[
                Section(title="Abstract", content="Abstract content", page_number=1)
            ],
            page_count=5,
            method="pymupdf",
            success=True,
        )

        data = result.to_dict()

        assert data["text"] == "Extracted text"
        assert len(data["sections"]) == 1
        assert data["sections"][0]["title"] == "Abstract"
        assert data["page_count"] == 5
        assert data["method"] == "pymupdf"
        assert data["success"] is True


class TestPDFParser:
    """Tests for PDFParser."""

    def test_init(self):
        """Test parser initialization."""
        ocr_config = OCRConfig(service_url="http://localhost:5000/ocr")
        parser = PDFParser(ocr_config=ocr_config)

        assert parser.ocr_config == ocr_config
        assert parser.min_char_threshold == 500
        assert parser.min_density_threshold == 0.3

    @patch("daily_paper.parsers.pdf_parser.fitz.open")
    def test_extract_with_pymupdf_success(self, mock_fitz_open):
        """Test successful PyMuPDF extraction."""
        # Mock document and page
        mock_page = Mock()
        mock_page.get_text.return_value = "Sample text from page 1"

        mock_doc = Mock()
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.close = Mock()

        mock_fitz_open.return_value = mock_doc

        parser = PDFParser()
        result = parser._extract_with_pymupdf(Path("test.pdf"))

        assert result.success is True
        assert result.method == "pymupdf"
        assert "Sample text" in result.text
        assert result.page_count == 1

    @patch("daily_paper.parsers.pdf_parser.fitz.open")
    def test_extract_with_pymupdf_failure(self, mock_fitz_open):
        """Test PyMuPDF extraction with error."""
        mock_fitz_open.side_effect = IOError("Failed to open PDF")

        parser = PDFParser()
        with pytest.raises(IOError):
            parser._extract_with_pymupdf(Path("test.pdf"))

    def test_clean_text(self):
        """Test text cleaning."""
        parser = PDFParser()

        # Test multiple spaces
        cleaned = parser._clean_text("Hello    world")
        assert "Hello    world" not in cleaned
        assert "Hello world" in cleaned

        # Test multiple newlines
        cleaned = parser._clean_text("Line 1\n\n\n\nLine 2")
        assert "Line 1\n\nLine 2" == cleaned

    def test_check_text_quality_success(self):
        """Test text quality check with good text."""
        parser = PDFParser(min_char_threshold=500, min_density_threshold=0.3)

        # Good quality text
        good_text = "a" * 1000  # High character count and density
        assert parser._check_text_quality(good_text) is True

    def test_check_text_quality_low_char_count(self):
        """Test text quality check with low character count."""
        parser = PDFParser(min_char_threshold=500, min_density_threshold=0.3)

        # Low character count
        short_text = "a" * 100
        assert parser._check_text_quality(short_text) is False

    def test_check_text_quality_low_density(self):
        """Test text quality check with low density."""
        parser = PDFParser(min_char_threshold=500, min_density_threshold=0.3)

        # Low density (lots of whitespace)
        low_density_text = "a" * 100 + " \n" * 1000
        assert parser._check_text_quality(low_density_text) is False

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = PDFParser()

        # Create a Paper object with non-existent PDF path
        test_paper = Paper(
            source="test",
            paper_id="test_not_found",
            title="Test Not Found Paper",
            pdf_path="/nonexistent/file.pdf"
        )

        result = parser.parse(test_paper)

        assert result.success is False
        assert "not found" in result.error_message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

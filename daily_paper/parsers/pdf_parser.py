"""
PDF text parser with PyMuPDF and OCR fallback.

This module provides PDF text extraction using a two-stage approach:
1. First tries PyMuPDF (fitz) for fast direct text extraction
2. Falls back to OCR service if direct extraction yields insufficient content

This approach balances speed and accuracy, using the fast method when
possible while ensuring fallback for scanned documents.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from daily_paper.config import OCRConfig

logger = logging.getLogger(__name__)


@dataclass
class Section:
    """
    A text section extracted from a PDF.

    Represents a logical section of the document with a heading
    and associated content.

    Attributes:
        title: Section heading/title.
        content: Section text content.
        page_number: Page number where section starts (1-indexed).
    """

    title: str
    content: str
    page_number: int

    def to_dict(self) -> dict:
        """Convert section to dictionary."""
        return {
            "title": self.title,
            "content": self.content,
            "page_number": self.page_number,
        }


@dataclass
class ParseResult:
    """
    Result of PDF text extraction.

    Contains all extracted content including full text, sections,
    and metadata about the extraction process.

    Attributes:
        text: Full extracted text (all pages concatenated).
        sections: List of identified sections with headings.
        page_count: Total number of pages in the PDF.
        method: Extraction method used ('pymupdf' or 'ocr').
        success: Whether extraction was successful.
        error_message: Error message if extraction failed.
        text_path: Path to saved text file (if auto_save=True).
    """

    text: str
    sections: List[Section] = field(default_factory=list)
    page_count: int = 0
    method: str = "pymupdf"
    success: bool = True
    error_message: Optional[str] = None
    text_path: Optional[str] = None  # Path to saved text file

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "text": self.text,
            "sections": [s.to_dict() for s in self.sections],
            "page_count": self.page_count,
            "method": self.method,
            "success": self.success,
            "error_message": self.error_message,
        }


class PDFParser:
    """
    PDF text extraction with OCR fallback.

    Uses PyMuPDF for fast direct text extraction. If the extracted text
    quality is below a threshold (character count, density), falls back
    to OCR service for more accurate extraction.

    Typical usage:
        >>> parser = PDFParser(ocr_config)
        >>> paper = Paper(pdf_path="data/papers/paper.pdf")
        >>> result = parser.parse(paper)
        >>> print(result.text)
        >>> print(f"Text saved to: {paper.text_path}")
        >>> for section in result.sections:
        ...     print(f"{section.title}: {section.content[:100]}...")

    Attributes:
        ocr_config: Configuration for OCR service.
        min_char_threshold: Minimum characters to consider extraction successful.
        min_density_threshold: Minimum ratio of non-whitespace characters.
    """

    # Common section headings to identify
    SECTION_PATTERNS = [
        r"^Abstract$",
        r"^Introduction$",
        r"^Related Work$",
        r"^Background$",
        r"^Preliminary$",
        r"^Problem Formulation$",
        r"^Methods?$",
        r"^Methodology$",
        r"^Approaches?$",
        r"^Materials and Methods$",
        r"^Experiment Settings?$",
        r"^Experiments?$",
        r"^Experimental Results?$",
        r"^Evaluation$",
        r"^Results?$",
        r"^Findings?$",
        r"^Data Analysis$",
        r"^Discussion$",
        r"^Results and Discussion$",
        r"^Conclusion$",
        r"^Conclusions$",
        r"^References?$",
    ]

    def __init__(
        self,
        ocr_config: Optional[OCRConfig] = None,
        min_char_threshold: int = 500,
        min_density_threshold: float = 0.3,
    ):
        """
        Initialize the PDF parser.

        Args:
            ocr_config: OCR service configuration. If None, OCR is disabled.
            min_char_threshold: Minimum characters for successful extraction.
            min_density_threshold: Minimum non-whitespace character ratio.
        """
        self.ocr_config = ocr_config
        self.min_char_threshold = min_char_threshold
        self.min_density_threshold = min_density_threshold

        # Compile section patterns for performance
        self.section_patterns = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in self.SECTION_PATTERNS
        ]

    def _extract_with_pymupdf(self, pdf_path: Path) -> ParseResult:
        """
        Extract text using PyMuPDF (fitz).

        Opens the PDF and extracts text from each page. Attempts to
        identify sections based on common heading patterns.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ParseResult with extracted text and sections.

        Raises:
            IOError: If the PDF cannot be opened or read.
        """
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            raise IOError(f"Failed to open PDF {pdf_path}: {e}")

        all_text: List[str] = []
        sections: List[Section] = []
        current_section: Optional[Dict] = None
        current_section_content: List[str] = []

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            all_text.append(page_text)

            # Try to identify sections
            lines = page_text.split("\n")
            for line in lines:
                stripped = line.strip()

                # Check if this line matches a section heading
                is_section = False
                for pattern in self.section_patterns:
                    if pattern.match(stripped):
                        # Save previous section if exists
                        if current_section:
                            sections.append(
                                Section(
                                    title=current_section["title"],
                                    content=" ".join(current_section_content).strip(),
                                    page_number=current_section["page"],
                                )
                            )
                            current_section_content = []

                        # Start new section
                        current_section = {
                            "title": stripped,
                            "page": page_num,
                        }
                        is_section = True
                        break

                # Add non-section lines to current section content
                if not is_section and stripped and current_section:
                    current_section_content.append(stripped)

        # Save final section
        if current_section and current_section_content:
            sections.append(
                Section(
                    title=current_section["title"],
                    content=" ".join(current_section_content).strip(),
                    page_number=current_section["page"],
                )
            )

        doc.close()

        # Combine all text
        full_text = "\n\n".join(all_text)
        full_text = self._clean_text(full_text)

        return ParseResult(
            text=full_text,
            sections=sections,
            page_count=len(all_text),
            method="pymupdf",
            success=True,
        )

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by normalizing whitespace.

        Args:
            text: Raw extracted text.

        Returns:
            Cleaned text with normalized whitespace.
        """
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)
        # Remove hyphens at line breaks
        text = re.sub(r"- \n", "", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def _check_text_quality(self, text: str) -> bool:
        """
        Check if extracted text meets quality thresholds.

        Evaluates both character count and text density to determine
        if extraction was successful.

        Args:
            text: Extracted text to evaluate.

        Returns:
            True if text meets quality thresholds, False otherwise.
        """
        char_count = len(text)
        if char_count < self.min_char_threshold:
            logger.warning(
                f"Text extraction below threshold: {char_count} < {self.min_char_threshold}"
            )
            return False

        # Check density (ratio of non-whitespace characters)
        non_ws = len(re.sub(r"\s", "", text))
        density = non_ws / char_count if char_count > 0 else 0
        if density < self.min_density_threshold:
            logger.warning(
                f"Text density below threshold: {density:.2f} < {self.min_density_threshold}"
            )
            return False

        return True

    def _save_text_to_file(self, pdf_path: Path, result: ParseResult) -> ParseResult:
        """
        Save extracted text to a .txt file.

        Creates a text file with the same name as the PDF in the same directory.
        Updates the result's text_path field with the saved file path.

        Args:
            pdf_path: Path to the PDF file.
            result: ParseResult containing extracted text.

        Returns:
            Updated ParseResult with text_path set.
        """
        try:
            # Create text file path (same location as PDF, .txt extension)
            text_path = pdf_path.with_suffix('.txt')
            text_path.parent.mkdir(parents=True, exist_ok=True)

            # Write text to file
            text_path.write_text(result.text, encoding='utf-8')

            # Update result with text path
            result.text_path = str(text_path)
            logger.info(f"Saved extracted text to {text_path}")

        except Exception as e:
            logger.warning(f"Failed to save text to file: {e}")
            # Don't throw exception, continue with result but text_path remains None

        return result

    def _extract_with_ocr(self, pdf_path: Path) -> ParseResult:
        """
        Extract text using OCR service.

        Converts PDF pages to images and sends them to the configured
        MLX VLM server for text extraction.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ParseResult with OCR-extracted text.

        Raises:
            IOError: If OCR is not configured or the request fails.
        """
        if not self.ocr_config:
            raise IOError("OCR not configured but required for this PDF")

        try:
            import base64
            import requests

            # Pattern to match control tokens: <|ref|>label<|/ref|><|det|>[[coords]]<|/det|>
            control_token_pattern = re.compile(
                r"<\|ref\|>.*?<\|/ref\|><\|det\|>\[\[.*?\]\]<\|/det\|>",
                re.DOTALL
            )

            # Convert PDF to images using PyMuPDF
            doc = fitz.open(str(pdf_path))
            page_count = len(doc)

            markdown_segments = []

            for page_num, page in enumerate(doc, start=1):
                # Render page to image
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")

                # Base64 encode the image
                img_base64 = base64.b64encode(img_data).decode("utf-8")
                img_data_url = f"data:image/png;base64,{img_base64}"

                # Prepare VLM server request
                payload = {
                    "model": self.ocr_config.model,
                    "image": [img_data_url],
                    "prompt": "<|grounding|>Convert the document to markdown.",
                    "max_tokens": 4096,
                    "temperature": 0.0,
                }

                # Send to VLM server
                response = requests.post(
                    self.ocr_config.service_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=120
                )
                response.raise_for_status()
                result = response.json()

                # Extract text from response
                page_text = result.get("text", "")

                # Clean stop tokens if present
                stop_token = "<｜end▁of▁sentence｜>"
                if page_text.endswith(stop_token):
                    page_text = page_text[:-len(stop_token)].strip()

                # Remove control tokens (ref/det markers)
                page_text = control_token_pattern.sub("", page_text)

                # Clean up LaTeX-style quotes and other artifacts
                page_text = page_text.replace("\\coloneqq", ":=").replace("\\eqqcolon", "=:")
                page_text = re.sub(r"\n{3,}", "\n\n", page_text)

                if page_text.strip():
                    markdown_segments.append(page_text.strip())

                logger.info(f"OCR processed page {page_num}/{page_count}")

            doc.close()

            # Combine all pages
            combined_text = "\n\n".join(markdown_segments)

            return ParseResult(
                text=self._clean_text(combined_text),
                sections=[],  # OCR doesn't identify sections
                method="ocr",
                success=True,
                page_count=page_count,
            )

        except Exception as e:
            raise IOError(f"OCR extraction failed: {e}")

    def parse(self, paper, auto_save: bool = True) -> ParseResult:
        """
        Extract text from a PDF with automatic OCR fallback.

        First attempts PyMuPDF extraction. If the extracted text quality
        is below thresholds, falls back to OCR service.

        Args:
            paper: Paper object containing pdf_path. Will be modified to set text_path.
            auto_save: If True, automatically save extracted text to .txt file.

        Returns:
            ParseResult containing extracted text and metadata.
        """
        # Validate paper object
        if not paper.pdf_path:
            logger.warning(f"Paper {paper.id} has no pdf_path")
            return ParseResult(
                text="",
                success=False,
                error_message=f"Paper {paper.id} has no pdf_path",
            )

        pdf_path = Path(paper.pdf_path)
        logger.info(f"Starting PDF parsing for paper {paper.id}: {pdf_path.name}")

        # Validation 1: File existence
        if not pdf_path.exists():
            logger.warning(f"PDF file not found: {pdf_path}")
            return ParseResult(
                text="",
                success=False,
                error_message=f"PDF file not found: {pdf_path}",
            )

        # Validation 2: File readability
        if not os.access(pdf_path, os.R_OK):
            logger.warning(f"PDF file not readable: {pdf_path}")
            return ParseResult(
                text="",
                success=False,
                error_message=f"PDF file not readable: {pdf_path}",
            )

        # Validation 3: File size (avoid empty or corrupted files)
        file_size = pdf_path.stat().st_size
        if file_size < 100:
            logger.warning(f"PDF file too small ({file_size} bytes): {pdf_path}")
            return ParseResult(
                text="",
                success=False,
                error_message=f"PDF file too small: {pdf_path}",
            )

        # Try PyMuPDF extraction first
        try:
            logger.debug(f"Attempting PyMuPDF extraction for {pdf_path.name}")
            result = self._extract_with_pymupdf(pdf_path)
            if self._check_text_quality(result.text):
                logger.info(
                    f"PyMuPDF extraction successful for paper {paper.id}: "
                    f"{result.page_count} pages, {len(result.text)} chars"
                )

                # Auto-save text to file
                if auto_save and result.success:
                    result = self._save_text_to_file(pdf_path, result)
                    # Directly set paper.text_path
                    paper.text_path = result.text_path
                    logger.debug(f"Set paper.text_path: {result.text_path}")

                logger.info(f"PDF parsing complete: {paper.id} (PyMuPDF)")
                return result
            else:
                logger.warning(
                    f"PyMuPDF extraction quality low for paper {paper.id} "
                    f"({len(result.text)} chars), falling back to OCR"
                )
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed for paper {paper.id}: {e}, falling back to OCR")

        # Fall back to OCR
        try:
            logger.info(f"Attempting OCR extraction for paper {paper.id}")
            result = self._extract_with_ocr(pdf_path)

            # Auto-save text to file
            if auto_save and result.success:
                result = self._save_text_to_file(pdf_path, result)
                # Directly set paper.text_path
                paper.text_path = result.text_path
                logger.debug(f"Set paper.text_path: {result.text_path}")

            logger.info(
                f"OCR extraction successful for paper {paper.id}: "
                f"{result.page_count} pages, {len(result.text)} chars"
            )
            logger.info(f"PDF parsing complete: {paper.id} (OCR)")
            return result
        except Exception as e:
            logger.error(f"OCR extraction failed for paper {paper.id}: {e}")
            return ParseResult(
                text="",
                success=False,
                error_message=str(e),
            )

    def save_text(self, pdf_path: str | Path, output_path: str | Path) -> ParseResult:
        """
        Extract text and save to file.

        Convenience method that extracts text and saves it to a file.

        Args:
            pdf_path: Path to the PDF file.
            output_path: Path to save the extracted text.

        Returns:
            ParseResult from the extraction.
        """
        result = self.parse(pdf_path)

        if result.success:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.text, encoding="utf-8")
            logger.info(f"Saved extracted text to {output_path}")

        return result

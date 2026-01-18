"""
Parsers module for extracting text from PDF documents.

This module provides PDF text extraction with OCR fallback support.
"""

from daily_paper.parsers.pdf_parser import (
    ParseResult,
    PDFParser,
)

__all__ = [
    "ParseResult",
    "PDFParser",
]

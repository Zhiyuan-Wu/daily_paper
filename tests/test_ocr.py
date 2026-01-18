#!/usr/bin/env python3
"""
Test OCR functionality with configured OCR service.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.config import Config
from daily_paper.parsers import PDFParser
from daily_paper.database import Paper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_ocr_direct():
    """Test OCR with a PDF file directly."""
    logger.info("=" * 60)
    logger.info("Testing OCR Module")
    logger.info("=" * 60)

    config = Config.from_env()

    logger.info(f"OCR Service URL: {config.ocr.service_url}")

    # Find a PDF file to test with
    pdf_files = list(config.paths.download_dir.glob("*.pdf"))

    if not pdf_files:
        logger.error(f"No PDF files found in {config.paths.download_dir}")
        logger.info("Please download a PDF first using test_integration.py")
        return None

    # Use the first PDF found
    pdf_path = pdf_files[0]
    logger.info(f"Testing with PDF: {pdf_path}")
    logger.info(f"File size: {pdf_path.stat().st_size / 1024 / 1024:.2f} MB")

    parser = PDFParser(config.ocr)

    try:
        logger.info("\nForcing OCR extraction (bypassing PyMuPDF)...")

        # Directly call OCR extraction
        result = parser._extract_with_ocr(pdf_path)

        if result.success:
            logger.info("✓ OCR extraction successful!")
            logger.info(f"  Method: {result.method}")
            logger.info(f"  Text length: {len(result.text)} characters")
            logger.info(f"  First 500 characters:")
            logger.info("  " + "-" * 56)
            logger.info(f"  {result.text[:500]}")
            logger.info("  " + "-" * 56)

            # Save OCR text
            text_path = config.paths.text_dir / f"{pdf_path.stem}_ocr.txt"
            text_path.write_text(result.text, encoding="utf-8")
            logger.info(f"\n✓ OCR text saved to: {text_path}")

            return result
        else:
            logger.error(f"✗ OCR extraction failed: {result.error_message}")
            return None

    except Exception as e:
        logger.error(f"✗ OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_pdf_parser_with_ocr():
    """Test PDF parser with OCR fallback."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing PDF Parser (with OCR fallback)")
    logger.info("=" * 60)

    config = Config.from_env()

    # Find a PDF file
    pdf_files = list(config.paths.download_dir.glob("*.pdf"))

    if not pdf_files:
        logger.error(f"No PDF files found in {config.paths.download_dir}")
        return None

    pdf_path = pdf_files[0]
    logger.info(f"Testing with PDF: {pdf_path}")

    parser = PDFParser(config.ocr)

    # Create a temporary Paper object for parsing
    test_paper = Paper(
        source="test",
        paper_id="test_ocr",
        title="Test OCR Paper",
        pdf_path=str(pdf_path)
    )

    try:
        # Parser now accepts Paper object directly
        result = parser.parse(test_paper)

        if result.success:
            logger.info(f"✓ PDF parsing successful!")
            logger.info(f"  Method: {result.method}")
            logger.info(f"  Pages: {result.page_count}")
            logger.info(f"  Text length: {len(result.text)} characters")
            logger.info(f"  Sections: {len(result.sections)}")

            # Show first few sections if any
            if result.sections:
                logger.info("\n  Detected sections:")
                for section in result.sections[:5]:
                    logger.info(f"    - {section.title} (page {section.page_number})")

            return result
        else:
            logger.error(f"✗ PDF parsing failed: {result.error_message}")
            return None

    except Exception as e:
        logger.error(f"✗ Parser test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run OCR tests."""
    try:
        # Test 1: Direct OCR extraction
        ocr_result = test_ocr_direct()

        # Test 2: PDF parser with OCR fallback
        parser_result = test_pdf_parser_with_ocr()

        if ocr_result or parser_result:
            logger.info("\n✓ OCR tests completed successfully")
            return 0
        else:
            logger.error("\n✗ OCR tests failed")
            return 1

    except Exception as e:
        logger.error(f"\n✗ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

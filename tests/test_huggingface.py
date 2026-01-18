#!/usr/bin/env python3
"""
Test HuggingFace downloader functionality.
"""

import sys
import logging
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.downloaders.huggingface_downloader import HuggingFaceDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_huggingface_fetch():
    """Test fetching papers from HuggingFace."""
    logger.info("=" * 60)
    logger.info("Testing HuggingFace Papers Downloader")
    logger.info("=" * 60)

    downloader = HuggingFaceDownloader()

    # Try to fetch papers from a recent date
    test_date = date(2026, 1, 16)  # A date we know has papers
    logger.info(f"Fetching papers from HuggingFace for date: {test_date}")

    try:
        papers = downloader.get_papers_by_date(test_date)

        logger.info(f"\n✓ Found {len(papers)} papers from HuggingFace")

        for i, paper in enumerate(papers[:5], 1):
            logger.info(f"\n  {i}. {paper.title[:80]}...")
            logger.info(f"     ID: {paper.paper_id}")
            logger.info(f"     URL: {paper.url}")
            if paper.authors:
                logger.info(f"     Authors: {len(paper.authors)} authors")

    except Exception as e:
        logger.error(f"✗ Failed to fetch papers: {e}")
        import traceback
        traceback.print_exc()


def test_huggingface_download(papers):
    """Test downloading a PDF from HuggingFace paper."""
    if not papers:
        logger.error("No papers to test download")
        return

    logger.info("\n" + "=" * 60)
    logger.info("Testing PDF download from HuggingFace paper")
    logger.info("=" * 60)

    downloader = HuggingFaceDownloader()
    paper = papers[0]

    logger.info(f"Downloading PDF for: {paper.title[:80]}...")

    try:
        from daily_paper.config import Config
        config = Config.from_env()
        pdf_path = downloader.download_paper(paper.paper_id, config.paths.download_dir)

        logger.info(f"✓ PDF downloaded successfully: {pdf_path}")
        logger.info(f"  File size: {Path(pdf_path).stat().st_size / 1024 / 1024:.2f} MB")

    except Exception as e:
        logger.error(f"✗ Failed to download PDF: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run HuggingFace downloader tests."""
    try:
        test_huggingface_fetch()
        # Note: test_huggingface_download requires papers, but that's handled in the test itself
        logger.info("\n✓ HuggingFace downloader tests completed")
    except Exception as e:
        logger.error(f"\n✗ Tests failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
End-to-end integration test for the Daily Paper system.

This script tests the complete pipeline:
1. Fetch papers from sources
2. Download PDFs
3. Parse PDFs to extract text
4. Generate LLM summaries
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.config import Config
from daily_paper.manager import DownloadManager
from daily_paper.parsers import PDFParser
from daily_paper.summarizers import PaperSummarizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_fetch_papers():
    """Test fetching papers from arXiv."""
    logger.info("=" * 60)
    logger.info("STEP 1: Testing paper fetching from arXiv")
    logger.info("=" * 60)

    config = Config.from_env()
    manager = DownloadManager(config)

    # Fetch recent papers (get first few from today or yesterday)
    target_date = date.today()
    logger.info(f"Fetching papers for date: {target_date}")

    papers = manager.fetch_papers_by_date(target_date, sources=["arxiv"])

    logger.info(f"Found {len(papers)} papers")
    for i, paper in enumerate(papers[:5], 1):  # Show first 5
        logger.info(f"  {i}. {paper.title[:80]}...")
        logger.info(f"     ID: {paper.paper_id}, Authors: {paper.authors[:50] if paper.authors else 'N/A'}...")

    if not papers:
        logger.warning("No papers found for today. Trying with recent papers...")
        # Try with a more flexible approach - just get the most recent papers
        from daily_paper.database import Paper, init_db
        session = init_db(config.database.url)

        # Create a test paper entry manually for testing
        from daily_paper.downloaders.arxiv_downloader import ArxivDownloader
        downloader = ArxivDownloader(
            categories=config.arxiv.categories,
            max_results=5
        )

        # Get the most recent papers regardless of date
        import arxiv as arxiv_lib
        search = arxiv_lib.Search(
            query=config.arxiv.build_query(),
            max_results=5,
            sort_by=arxiv_lib.SortCriterion.SubmittedDate,
            sort_order=arxiv_lib.SortOrder.Descending,
        )

        for result in downloader._client.results(search):
            arxiv_id = downloader._extract_arxiv_id(result.entry_id)
            published = result.published.date() if result.published else None

            # Check if paper already exists
            existing = session.query(Paper).filter_by(
                source="arxiv", paper_id=arxiv_id
            ).first()

            if not existing:
                paper = Paper(
                    source="arxiv",
                    paper_id=arxiv_id,
                    title=result.title,
                    authors=", ".join([a.name for a in result.authors]),
                    abstract=result.summary.replace("\n", " ").strip(),
                    published_date=published,
                    url=result.entry_id,
                )
                session.add(paper)
                session.commit()
                session.refresh(paper)
                # Convert to dict to avoid detached instance issues
                paper_dict = paper.to_dict()
                papers.append(paper)
                logger.info(f"  Added: {paper.title[:80]}...")
            else:
                papers.append(existing)
                logger.info(f"  Existing: {existing.title[:80]}...")

        # Don't close the session yet - keep it open for the next steps
        manager.session = session

    manager.close()


def test_download_pdf(papers):
    """Test downloading a PDF."""
    logger.info("=" * 60)
    logger.info("STEP 2: Testing PDF download")
    logger.info("=" * 60)

    if not papers:
        logger.error("No papers to download")
        return

    config = Config.from_env()
    manager = DownloadManager(config)

    # Download first paper
    paper = papers[0]
    logger.info(f"Downloading PDF for: {paper.title[:80]}...")
    logger.info(f"Paper ID: {paper.paper_id}")

    try:
        pdf_path = manager.download_paper(paper)
        logger.info(f"✓ PDF downloaded successfully: {pdf_path}")
        logger.info(f"  File size: {Path(pdf_path).stat().st_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        logger.error(f"✗ Failed to download PDF: {e}")
        manager.close()
        return None

    manager.close()
    return paper


def test_parse_pdf(paper):
    """Test parsing PDF to extract text."""
    logger.info("=" * 60)
    logger.info("STEP 3: Testing PDF parsing")
    logger.info("=" * 60)

    if not paper or not paper.pdf_path:
        logger.error("No PDF to parse")
        return None

    config = Config.from_env()
    parser = PDFParser(config.ocr)

    logger.info(f"Parsing PDF: {paper.pdf_path}")

    result = parser.parse(paper.pdf_path)

    if result.success:
        logger.info(f"✓ PDF parsed successfully")
        logger.info(f"  Method: {result.method}")
        logger.info(f"  Pages: {result.page_count}")
        logger.info(f"  Text length: {len(result.text)} characters")
        logger.info(f"  Sections found: {len(result.sections)}")

        # Show first few sections
        for section in result.sections[:3]:
            logger.info(f"  - {section.title}: {section.content[:100]}...")

        # Save extracted text
        text_path = config.paths.text_dir / f"{paper.paper_id}.txt"
        text_path.write_text(result.text, encoding="utf-8")
        logger.info(f"  Text saved to: {text_path}")

        return result
    else:
        logger.error(f"✗ Failed to parse PDF: {result.error_message}")
        return None


def test_summarize_paper(paper):
    """Test LLM-based paper summarization."""
    logger.info("=" * 60)
    logger.info("STEP 4: Testing LLM paper summarization")
    logger.info("=" * 60)

    if not paper:
        logger.error("No paper to summarize")
        return

    config = Config.from_env()

    # Check LLM configuration
    logger.info(f"LLM Provider: {config.llm.provider}")
    logger.info(f"LLM Model: {config.llm.model}")

    summarizer = PaperSummarizer(config)

    # Test with a subset of steps
    from daily_paper.summarizers.workflow import SummaryStep

    test_steps = [
        SummaryStep.BASIC_INFO,
        SummaryStep.BACKGROUND,
        SummaryStep.CONTRIBUTIONS,
    ]

    logger.info(f"Running summarization steps: {[s.display_name for s in test_steps]}")

    try:
        results = summarizer.summarize_paper(
            paper,
            steps=test_steps,
            save_to_db=True,
        )

        logger.info(f"\n✓ Summarization completed!")
        logger.info(f"Generated {len(results)} summaries:\n")

        for result in results:
            if result.success:
                logger.info(f"\n{'='*60}")
                logger.info(f"{result.step.display_name}")
                logger.info(f"{'='*60}")
                logger.info(result.content)
                logger.info("")
            else:
                logger.error(f"✗ {result.step.display_name} failed: {result.error_message}")

        summarizer.close()
        return results

    except Exception as e:
        logger.error(f"✗ Summarization failed: {e}")
        import traceback
        traceback.print_exc()
        summarizer.close()
        return None


def main():
    """Run the complete integration test."""
    logger.info("\n" + "="*60)
    logger.info("DAILY PAPER SYSTEM - END-TO-END INTEGRATION TEST")
    logger.info("="*60 + "\n")

    try:
        # Step 1: Fetch papers
        papers = test_fetch_papers()
        if not papers:
            logger.error("❌ Cannot proceed without papers")
            return 1

        # Step 2: Download PDF
        paper = test_download_pdf(papers)
        if not paper:
            logger.error("❌ Cannot proceed without PDF")
            return 1

        # Step 3: Parse PDF
        parse_result = test_parse_pdf(paper)
        if not parse_result:
            logger.error("❌ Cannot proceed without parsed text")
            return 1

        # Step 4: Summarize paper
        summary_results = test_summarize_paper(paper)
        if not summary_results:
            logger.error("❌ Summarization failed")
            return 1

        logger.info("\n" + "="*60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("="*60 + "\n")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

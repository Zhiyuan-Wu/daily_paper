#!/usr/bin/env python3
"""
Test script to verify arXiv date filtering behavior.

This script tests two scenarios:
1. Get latest papers without date filter (like demo)
2. Get papers filtered by today's date (like refresh)
"""

import logging
from datetime import date, datetime
from daily_paper.config import Config
from daily_paper.downloaders.arxiv_downloader import ArxivDownloader
from daily_paper.manager import DownloadManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_without_date_filter():
    """Test getting latest papers without date filter (like demo)."""
    logger.info("=" * 80)
    logger.info("TEST 1: Get latest papers WITHOUT date filter (like demo)")
    logger.info("=" * 80)

    config = Config.from_env()
    downloader = ArxivDownloader(
        categories=["cs.AI", "cs.LG"],
        max_results=10
    )

    import arxiv as arxiv_lib
    search = arxiv_lib.Search(
        query="cat:cs.AI OR cat:cs.LG",
        max_results=10,
        sort_by=arxiv_lib.SortCriterion.SubmittedDate,
        sort_order=arxiv_lib.SortOrder.Descending
    )

    papers = []
    for result in downloader._client.results(search):
        arxiv_id = downloader._extract_arxiv_id(result.entry_id)
        published = result.published.date() if result.published else None

        logger.info(f"Paper: {arxiv_id}")
        logger.info(f"  Title: {result.title[:80]}...")
        logger.info(f"  Published: {published}")
        logger.info(f"  Today: {date.today()}")
        logger.info(f"  Is today: {published == date.today() if published else 'N/A'}")
        papers.append((arxiv_id, published))

    logger.info(f"\n✓ Got {len(papers)} papers without date filter")
    logger.info(f"  Published dates: {[p[1] for p in papers]}")

    return papers


def test_with_date_filter():
    """Test getting papers WITH date filter (like refresh)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Get papers WITH date filter (like refresh)")
    logger.info("=" * 80)

    config = Config.from_env()
    manager = DownloadManager(config)

    target_date = date.today()
    logger.info(f"Target date: {target_date}")

    # This is what refresh.py calls
    papers = manager.fetch_papers_by_date(target_date=target_date)

    logger.info(f"\n✓ Got {len(papers)} papers with date filter for {target_date}")

    for paper in papers[:5]:
        logger.info(f"  - {paper.paper_id}: {paper.title[:60]}... (published: {paper.published_date})")

    return papers


def test_date_distribution():
    """Test date distribution of recent papers."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Analyze date distribution of recent papers")
    logger.info("=" * 80)

    config = Config.from_env()
    downloader = ArxivDownloader(
        categories=["cs.AI", "cs.LG"],
        max_results=100
    )

    import arxiv as arxiv_lib
    search = arxiv_lib.Search(
        query="cat:cs.AI OR cat:cs.LG",
        max_results=100,
        sort_by=arxiv_lib.SortCriterion.SubmittedDate,
        sort_order=arxiv_lib.SortOrder.Descending
    )

    from collections import Counter
    date_counts = Counter()

    for result in downloader._client.results(search):
        published = result.published.date() if result.published else None
        if published:
            date_counts[published] += 1

    logger.info(f"\nDate distribution of last 100 papers:")
    for pub_date, count in date_counts.most_common(10):
        is_today = " ← TODAY!" if pub_date == date.today() else ""
        logger.info(f"  {pub_date}: {count} papers{is_today}")

    logger.info(f"\nToday ({date.today()}): {date_counts.get(date.today(), 0)} papers")

    return date_counts


if __name__ == "__main__":
    logger.info(f"Current date/time: {datetime.now()}")
    logger.info(f"Today's date: {date.today()}\n")

    # Test 1: Without date filter
    papers_no_filter = test_without_date_filter()

    # Test 2: With date filter
    papers_with_filter = test_with_date_filter()

    # Test 3: Date distribution
    date_counts = test_date_distribution()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Without date filter: {len(papers_no_filter)} papers")
    logger.info(f"With date filter: {len(papers_with_filter)} papers")
    logger.info(f"Today's papers in last 100: {date_counts.get(date.today(), 0)}")

    if len(papers_with_filter) == 0:
        logger.warning("\n⚠️  No papers found for today!")
        logger.warning("   This is why refresh.py returns 0 papers.")
        logger.warning("   Solution: Check if arXiv publishes papers today (weekends often have no papers)")

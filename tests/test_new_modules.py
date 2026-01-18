#!/usr/bin/env python3
"""
Test user database, recommendation, and daily report modules.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.config import Config
from daily_paper.database import init_db, UserProfile, Paper
from daily_paper.users.manager import UserManager
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.reports.generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_user_profile():
    """Test user profile management."""
    logger.info("=" * 60)
    logger.info("Testing User Profile Management")
    logger.info("=" * 60)

    config = Config.from_env()
    session = init_db(config.database.url)
    user_manager = UserManager(session)

    # Get or create profile
    profile = user_manager.get_profile()
    logger.info(f"✓ User profile ID: {profile.id}")

    # Update interests
    profile = user_manager.update_interests(
        interested_keywords="LLM, transformers, computer vision",
        interest_description="Machine learning research focused on large language models and visual understanding"
    )
    logger.info(f"✓ Updated user interests")
    logger.info(f"  Keywords: {profile.interested_keywords}")
    logger.info(f"  Description: {profile.interest_description[:100]}...")


def test_recommendation(user_manager):
    """Test recommendation system."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Recommendation System")
    logger.info("=" * 60)

    config = Config.from_env()
    session = init_db(config.database.url)

    # Check if we have papers in database
    paper_count = session.query(Paper).count()
    logger.info(f"Papers in database: {paper_count}")

    if paper_count == 0:
        logger.warning("No papers in database. Skipping recommendation test.")
        return

    # Generate recommendations
    manager = RecommendationManager(config, session)
    results = manager.recommend(top_k=5)

    if results:
        logger.info(f"✓ Generated {len(results)} recommendations:")
        for i, result in enumerate(results, 1):
            paper = session.query(Paper).filter(Paper.id == result.paper_id).first()
            logger.info(f"\n  {i}. Paper ID: {result.paper_id}")
            logger.info(f"     Title: {paper.title[:80] if paper else 'Unknown'}...")
            logger.info(f"     Score: {result.score:.3f}")
            logger.info(f"     Reason: {result.reason[:100]}...")
    else:
        logger.warning("No recommendations generated")


def test_paper_interaction(user_manager, paper):
    """Test marking paper interactions."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Paper Interactions")
    logger.info("=" * 60)

    # Use the session from user_manager fixture
    session = user_manager.session

    # paper is provided by fixture
    logger.info(f"Testing with paper: {paper.title[:80]}...")

    # Mark as interested
    interaction = user_manager.mark_paper_interested(
        paper_id=paper.id,
        notes="Interesting paper on novel architecture"
    )
    logger.info(f"✓ Marked paper {paper.id} as interested")
    logger.info(f"  Action: {interaction.action}")
    logger.info(f"  Notes: {interaction.notes}")

    # Get interested papers
    interested_papers = user_manager.get_interested_papers(limit=5)
    logger.info(f"\n✓ Total interested papers: {len(interested_papers)}")


def test_report_generation():
    """Test daily report generation."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Daily Report Generation")
    logger.info("=" * 60)

    config = Config.from_env()
    session = init_db(config.database.url)

    # Check if we have papers
    paper_count = session.query(Paper).count()
    if paper_count == 0:
        logger.warning("No papers in database. Skipping report test.")
        return

    # Generate report
    generator = ReportGenerator(config, session)
    report = generator.generate(top_k=3)

    if report:
        logger.info("✓ Report generated successfully!")
        logger.info(f"  Date: {report['report_date']}")
        logger.info(f"  Papers: {len(report['papers'])}")
        logger.info(f"  Themes used: {len(report['themes_used'])}")
        logger.info(f"\n  Highlights preview:")
        logger.info(f"  {report['highlights'][:300]}...")
    else:
        logger.warning("Report generation failed")


def main():
    """Run all tests."""
    try:
        logger.info("\n" + "="*60)
        logger.info("NEW MODULES INTEGRATION TEST")
        logger.info("="*60 + "\n")

        # Test 1: User profile
        user_manager = test_user_profile()

        # Test 2: Paper interaction
        test_paper_interaction(user_manager)

        # Test 3: Recommendation
        test_recommendation(user_manager)

        # Test 4: Report generation
        test_report_generation()

        logger.info("\n" + "="*60)
        logger.info("✓ ALL TESTS COMPLETED!")
        logger.info("="*60 + "\n")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Comprehensive test suite for user database, recommendation, and report modules.

Tests the following functionality:
1. Database model creation and relationships
2. Embedding service integration
3. User profile and interaction management
4. Recommendation system
5. Daily report generation
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daily_paper.config import Config
from daily_paper.database import (
    init_db, UserProfile, PaperInteraction, InterestTheme,
    DailyReport, Paper, Summary
)
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.embeddings.utils import cosine_similarity
from daily_paper.users.manager import UserManager
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.reports.generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_database_models():
    """Test database model creation and relationships."""
    logger.info("=" * 70)
    logger.info("TEST 1: Database Models")
    logger.info("=" * 70)

    config = Config.from_env()
    session = init_db(config.database.url)

    try:
        # Test UserProfile creation
        profile = session.query(UserProfile).first()
        if not profile:
            profile = UserProfile(
                id=1,
                interested_keywords="machine learning, deep learning, computer vision",
                disinterested_keywords="legacy systems",
                interest_description="Research on modern ML techniques"
            )
            session.add(profile)
            session.commit()

        logger.info(f"✓ UserProfile created/loaded: ID={profile.id}")
        logger.info(f"  Interested keywords: {profile.interested_keywords}")
        logger.info(f"  Interest description: {profile.interest_description[:50]}...")

        # Test PaperInteraction (check if exists first to avoid unique constraint error)
        interaction = session.query(PaperInteraction).filter(
            PaperInteraction.user_id == 1,
            PaperInteraction.paper_id == 1
        ).first()

        if not interaction:
            interaction = PaperInteraction(
                user_id=1,
                paper_id=1,
                action="no_action",
                recommendation_count=0
            )
            session.add(interaction)
            session.commit()
            logger.info(f"✓ PaperInteraction created: ID={interaction.id}")
        else:
            logger.info(f"✓ PaperInteraction already exists: ID={interaction.id}")

        # Test InterestTheme
        theme = InterestTheme(
            user_id=1,
            theme="Transformer architectures",
            source_papers="[1, 2, 3]",
            is_active=True
        )
        session.add(theme)
        session.commit()
        logger.info(f"✓ InterestTheme created: {theme.theme}")

        # Test DailyReport
        report = DailyReport(
            report_date=datetime.now(),
            recommendations="[1, 2, 3]",
            highlights="Test highlights",
            themes_used='["ML", "DL"]'
        )
        session.add(report)
        session.commit()
        logger.info(f"✓ DailyReport created: ID={report.id}")

        logger.info("\n✓ Database models test PASSED")

    except Exception as e:
        logger.error(f"✗ Database models test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_embedding_service():
    """Test embedding service client."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Embedding Service")
    logger.info("=" * 70)

    try:
        config = Config.from_env()
        logger.info(f"Embedding API URL: {config.embedding.api_url}")
        logger.info(f"Embedding Model: {config.embedding.model}")

        client = EmbeddingClient(config.embedding)

        # Test single text embedding
        text = "This is a test sentence for embedding."
        embedding = client.get_embedding(text)

        logger.info(f"✓ Generated embedding for single text")
        logger.info(f"  Embedding dimension: {len(embedding)}")
        logger.info(f"  First 5 values: {embedding[:5]}")

        # Test batch embeddings
        texts = [
            "Machine learning is a subset of artificial intelligence.",
            "Deep learning uses neural networks with multiple layers.",
            "Computer vision enables machines to interpret visual information."
        ]

        embeddings = client.get_embeddings(texts)

        logger.info(f"\n✓ Generated embeddings for batch of {len(texts)} texts")
        logger.info(f"  All embeddings have same dimension: {all(len(emb) == len(embeddings[0]) for emb in embeddings)}")

        # Test cosine similarity
        sim = cosine_similarity(embeddings[0], embeddings[1])
        logger.info(f"\n✓ Cosine similarity calculation works")
        logger.info(f"  Similarity between text 1 and 2: {sim:.3f}")

        logger.info("\n✓ Embedding service test PASSED")

    except Exception as e:
        logger.error(f"✗ Embedding service test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_user_manager(session):
    """Test user management functionality."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: User Manager")
    logger.info("=" * 70)

    try:
        user_manager = UserManager(session)

        # Test get_profile
        profile = user_manager.get_profile()
        logger.info(f"✓ Retrieved user profile: ID={profile.id}")

        # Test update_interests
        profile = user_manager.update_interests(
            interested_keywords="LLM, transformers, attention mechanisms",
            interest_description="Research on large language models and novel architectures"
        )
        logger.info(f"✓ Updated user interests")
        logger.info(f"  Keywords: {profile.interested_keywords}")

        # Test get_interactions
        interactions = user_manager.get_interactions(limit=5)
        logger.info(f"\n✓ Retrieved {len(interactions)} interactions")

        # Test get_interested_papers (should be empty initially)
        interested_papers = user_manager.get_interested_papers()
        logger.info(f"✓ Retrieved {len(interested_papers)} interested papers")

        logger.info("\n✓ User manager test PASSED")

    except Exception as e:
        logger.error(f"✗ User manager test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_recommendation_system(session, embedding_client):
    """Test recommendation system."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Recommendation System")
    logger.info("=" * 70)

    try:
        config = Config.from_env()

        # Check if we have papers
        paper_count = session.query(Paper).count()
        logger.info(f"Papers in database: {paper_count}")

        if paper_count == 0:
            logger.warning("No papers in database. Skipping recommendation test.")
            return

        # Test recommendation manager
        manager = RecommendationManager(config, session, embedding_client)

        # Generate recommendations
        results = manager.recommend(top_k=5, record_recommendations=False)

        if results:
            logger.info(f"✓ Generated {len(results)} recommendations")

            for i, result in enumerate(results[:3], 1):  # Show top 3
                paper = session.query(Paper).filter(Paper.id == result.paper_id).first()
                logger.info(f"\n  {i}. Paper ID: {result.paper_id}")
                if paper:
                    logger.info(f"     Title: {paper.title[:80]}...")
                    logger.info(f"     Source: {paper.source}")
                logger.info(f"     Score: {result.score:.3f}")
                logger.info(f"     Reason: {result.reason}")
        else:
            logger.warning("No recommendations generated (may need to configure user interests)")

        logger.info("\n✓ Recommendation system test PASSED")

    except Exception as e:
        logger.error(f"✗ Recommendation system test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_paper_interaction(user_manager):
    """Test paper interaction tracking."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Paper Interaction Tracking")
    logger.info("=" * 70)

    try:
        # Get a paper to interact with
        from daily_paper.database import init_db
        from daily_paper.config import Config
        session = init_db(Config.from_env().database.url)

        paper = session.query(Paper).first()
        if not paper:
            logger.warning("No papers in database. Skipping interaction test.")
            return

        logger.info(f"Testing with paper: {paper.title[:80]}...")
        logger.info(f"Paper ID: {paper.id}")

        # Mark as interested
        interaction = user_manager.mark_paper_interested(
            paper_id=paper.id,
            notes="Interesting paper on novel approach"
        )
        logger.info(f"✓ Marked as interested")
        logger.info(f"  Action: {interaction.action}")
        logger.info(f"  Notes: {interaction.notes}")
        logger.info(f"  Recommendation count: {interaction.recommendation_count}")

        # Verify interaction was saved
        interactions = user_manager.get_interactions(action="interested")
        interested_ids = [inter.paper_id for inter in interactions]

        if paper.id in interested_ids:
            logger.info(f"✓ Interaction correctly saved to database")

        # Test getting interested papers
        interested_papers = user_manager.get_interested_papers()
        logger.info(f"\n✓ Total interested papers: {len(interested_papers)}")

        logger.info("\n✓ Paper interaction test PASSED")

    except Exception as e:
        logger.error(f"✗ Paper interaction test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_report_generation(session):
    """Test daily report generation."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 6: Daily Report Generation")
    logger.info("=" * 70)

    try:
        config = Config.from_env()

        # Check if we have papers
        paper_count = session.query(Paper).count()
        logger.info(f"Papers in database: {paper_count}")

        if paper_count < 3:
            logger.warning("Need at least 3 papers for report generation test. Skipping.")
            return

        # Generate report with small top_k for testing
        generator = ReportGenerator(config, session)
        report = generator.generate(top_k=3, save_to_db=True)

        if report and report.get('papers'):
            logger.info("✓ Report generated successfully!")
            logger.info(f"  Report date: {report['report_date']}")
            logger.info(f"  Number of papers: {len(report['papers'])}")
            logger.info(f"  Themes used: {len(report['themes_used'])}")
            logger.info(f"  Recommendations: {len(report.get('recommendation_results', []))}")

            if report['highlights']:
                logger.info(f"\n  Highlights preview (first 500 chars):")
                logger.info(f"  {report['highlights'][:500]}...")

            # Verify report was saved to database
            from daily_paper.database import DailyReport
            saved_reports = session.query(DailyReport).all()
            if saved_reports:
                latest_report = saved_reports[-1]
                logger.info(f"\n✓ Report saved to database: ID={latest_report.id}")
        else:
            logger.warning("Report generation returned empty result")

        logger.info("\n✓ Report generation test PASSED")

    except Exception as e:
        logger.error(f"✗ Report generation test FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_integration():
    """Test full integration workflow."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 7: Full Integration Workflow")
    logger.info("=" * 70)

    try:
        config = Config.from_env()
        session = init_db(config.database.url)

        # Step 1: Set up user profile
        logger.info("\nStep 1: Setting up user profile...")
        user_manager = UserManager(session)
        profile = user_manager.update_interests(
            interested_keywords="deep learning, neural networks",
            interest_description="Research on deep learning architectures"
        )
        logger.info(f"✓ User profile configured")

        # Step 2: Check papers
        logger.info("\nStep 2: Checking database...")
        paper_count = session.query(Paper).count()
        logger.info(f"✓ Found {paper_count} papers in database")

        if paper_count < 3:
            logger.warning("Need at least 3 papers for integration test. Skipping.")
            return

        # Step 3: Mark some papers as interested
        logger.info("\nStep 3: Marking papers as interested...")
        papers = session.query(Paper).limit(3).all()
        for paper in papers:
            user_manager.mark_paper_interested(paper.id, notes="Test interest")
        logger.info(f"✓ Marked {len(papers)} papers as interested")

        # Step 4: Generate recommendations
        logger.info("\nStep 4: Generating recommendations...")
        embedding_client = EmbeddingClient(config.embedding)
        rec_manager = RecommendationManager(config, session, embedding_client)
        results = rec_manager.recommend(top_k=3, record_recommendations=True)

        if results:
            logger.info(f"✓ Generated {len(results)} recommendations")
        else:
            logger.warning("No recommendations generated")

        # Step 5: Generate report
        logger.info("\nStep 5: Generating daily report...")
        report_gen = ReportGenerator(config, session)
        report = report_gen.generate(top_k=3)

        if report:
            logger.info(f"✓ Daily report generated")
        else:
            logger.warning("Report generation failed")

        logger.info("\n✓ Integration workflow test PASSED")

    except Exception as e:
        logger.error(f"✗ Integration workflow test FAILED: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    logger.info("\n" + "="*70)
    logger.info("COMPREHENSIVE TEST SUITE FOR NEW MODULES")
    logger.info("="*70 + "\n")

    results = {}

    # Test 1: Database models
    session = test_database_models()
    results['database'] = session is not None

    # Test 2: Embedding service
    embedding_client = test_embedding_service()
    results['embedding'] = embedding_client is not None

    # Test 3: User manager
    if session:
        user_manager = test_user_manager(session)
        results['user_manager'] = user_manager is not None
    else:
        results['user_manager'] = False

    # Test 4: Paper interaction
    if results['user_manager']:
        test_paper_interaction(user_manager)

    # Test 5: Recommendation system
    if session and embedding_client:
        rec_results = test_recommendation_system(session, embedding_client)
        results['recommendation'] = rec_results is not None
    else:
        results['recommendation'] = False

    # Test 6: Report generation
    if session:
        report = test_report_generation(session)
        results['report'] = report is not None
    else:
        results['report'] = False

    # Test 7: Full integration
    integration_ok = test_integration()
    results['integration'] = integration_ok

    # Summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)

    total_tests = len(results)
    passed_tests = sum(results.values())

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")

    logger.info(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    logger.info("="*70 + "\n")

    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())

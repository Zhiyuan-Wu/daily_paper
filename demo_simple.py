#!/usr/bin/env python3
"""
Daily Paper System - Complete Workflow Demo (Clean Version)

This script demonstrates the entire paper processing pipeline from scratch:
1. Fetch papers from arXiv (metadata only)
2. Download full PDFs
3. Parse PDFs and extract text
4. Generate 3-step summaries using LLM
5. Generate embeddings
6. Create daily report

Each step shows input, output, and processing time.
"""

import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from daily_paper.config import Config
from daily_paper.logging_config import setup_logging

# Configure logging first
config = Config.from_env()
setup_logging(config.log)
logger = logging.getLogger(__name__)

from daily_paper.database import init_db, Paper, Summary
from daily_paper.manager import DownloadManager
from daily_paper.parsers import PDFParser
from daily_paper.summarizers.workflow import PaperSummarizer, SummaryStep
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.reports.generator import ReportGenerator
from daily_paper.embeddings.client import EmbeddingClient


def print_section(title: str, icon: str = "⚡"):
    """Print a section header."""
    print(f"\n{'=' * 80}")
    print(f"{icon}  {title}")
    print(f"{'=' * 80}\n")


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---\n")


def demo_fetch_and_download(config, num_papers: int = 2):
    """Step 1: Fetch paper metadata and download PDFs from arXiv."""
    print_section("STEP 1: Fetch & Download Papers from arXiv", icon="📥")

    manager = DownloadManager(config)

    print(f"Fetching latest papers from arXiv...")
    print(f"Categories: cs.AI, cs.LG")
    print(f"Max Papers: {num_papers}\n")

    start_time = time.time()

    # Fetch latest papers (no date filter)
    import arxiv as arxiv_lib
    from daily_paper.downloaders.arxiv_downloader import ArxivDownloader

    downloader = ArxivDownloader(
        categories=["cs.AI", "cs.LG"],
        max_results=num_papers
    )

    # Get latest papers
    search = arxiv_lib.Search(
        query="cat:cs.AI OR cat:cs.LG",
        max_results=num_papers,
        sort_by=arxiv_lib.SortCriterion.SubmittedDate,
        sort_order=arxiv_lib.SortOrder.Descending
    )

    papers = []
    for result in downloader._client.results(search):
        # Create Paper object
        from daily_paper.database import Paper
        arxiv_id = downloader._extract_arxiv_id(result.entry_id)
        published = result.published.date() if result.published else None

        # Check if exists
        existing = manager.session.query(Paper).filter_by(
            source="arxiv",
            paper_id=arxiv_id
        ).first()

        if existing:
            papers.append(existing)
        else:
            paper = Paper(
                source="arxiv",
                paper_id=arxiv_id,
                title=result.title,
                authors=", ".join([a.name for a in result.authors]),
                abstract=result.summary.replace("\n", " ").strip(),
                published_date=published,
                url=result.entry_id
            )
            manager.session.add(paper)
            manager.session.commit()
            manager.session.refresh(paper)
            papers.append(paper)

    metadata_time = time.time() - start_time
    print(f"✓ Fetched {len(papers)} paper(s) metadata in {metadata_time:.2f}s")

    # Show first paper metadata
    if papers:
        print_subsection("Example: Paper Metadata")
        paper = papers[0]
        print(f"  Title: {paper.title[:80]}")
        print(f"  Authors: {paper.authors[:60] if paper.authors else 'N/A'}")
        print(f"  Source: {paper.source}")
        print(f"  Paper ID: {paper.paper_id}")
        print(f"  URL: {paper.url}")
        print(f"  Abstract: {paper.abstract[:150]}..." if paper.abstract else "  Abstract: N/A")

    # Download PDFs
    print_subsection("Downloading Full PDFs")
    downloaded_papers = []
    download_start = time.time()

    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}] {paper.title[:60]}...")
        try:
            pdf_path = manager.download_paper(paper)
            paper.pdf_path = str(pdf_path)
            downloaded_papers.append(paper)

            file_size = Path(pdf_path).stat().st_size / 1024 / 1024
            print(f"  ✓ Downloaded: {pdf_path}")
            print(f"  ✓ Size: {file_size:.2f} MB")

        except Exception as e:
            print(f"  ✗ Failed: {e}")

    download_time = time.time() - download_start
    total_time = time.time() - start_time

    print(f"\n✓ Downloaded {len(downloaded_papers)} PDF(s) in {download_time:.2f}s")
    print(f"✓ Total Step 1 Time: {total_time:.2f}s")

    return downloaded_papers


def demo_parse_pdfs(config, papers):
    """Step 2: Parse PDFs and extract text."""
    print_section("STEP 2: Parse PDFs & Extract Text", icon="📄")

    parser = PDFParser(config.ocr)
    parsed_papers = []

    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}] Parsing: {paper.title[:60]}...")

        start_time = time.time()
        # Parser now accepts paper object directly
        result = parser.parse(paper, auto_save=True)
        elapsed = time.time() - start_time

        print(f"  Method: {result.method}")
        print(f"  Time: {elapsed:.2f}s")

        if result.success:
            print(f"  Pages: {result.page_count}")
            print(f"  Text Length: {len(result.text):,} characters")
            print(f"  Sections Found: {len(result.sections)}")
            print(f"  Preview: {result.text[:100].replace(chr(10), ' ')}...")

            # Parser directly sets paper.text_path
            if paper.text_path:
                print(f"  ✓ Text saved to: {paper.text_path}")
            else:
                print(f"  ⚠ Text file not saved (auto-save may have failed)")

            parsed_papers.append(paper)
        else:
            print(f"  ✗ Error: {result.error_message}")

    print(f"\n✓ Successfully parsed {len(parsed_papers)}/{len(papers)} papers")

    return parsed_papers


def demo_generate_summaries(config, papers):
    """Step 3: Generate 3-step summaries using LLM."""
    print_section("STEP 3: Generate 3-Step Summaries (LLM)", icon="🤖")

    summarizer = PaperSummarizer(config)

    for i, paper in enumerate(papers[:1], 1):  # Only 1 paper to save time
        print(f"\n[{i}] Paper: {paper.title[:60]}...")
        print(f"  Workflow: 内容摘要 → 深度研究 → TLDR\n")

        total_start = time.time()
        results = []

        for step in [SummaryStep.CONTENT_SUMMARY, SummaryStep.DEEP_RESEARCH, SummaryStep.TLDR]:
            step_start = time.time()

            step_results = summarizer.summarize_paper(
                paper,
                steps=[step],
                save_to_db=True
            )

            step_elapsed = time.time() - step_start

            if step_results:
                result = step_results[0]
                results.append(result)

                print(f"\n  ✓ {step.display_name}")
                print(f"    Time: {step_elapsed:.2f}s | Length: {len(result.content):,} chars")
                print(f"    Preview: {result.content[:100]}...")

        total_elapsed = time.time() - total_start

        print(f"\n  ✓ Total: {total_elapsed:.2f}s for {len(results)} summaries")

    summarizer.close()


def demo_generate_embeddings(config, papers):
    """Step 4: Generate embeddings for papers."""
    print_section("STEP 4: Generate Embeddings", icon="🔢")

    embedding_client = EmbeddingClient(config.embedding)

    for i, paper in enumerate(papers[:1], 1):
        # Validate: Check if text_path exists
        if not paper.text_path:
            print(f"\n[{i}] No text file path (PDF parsing may have failed)")
            continue

        # Validate: Check if text file actually exists on disk
        from pathlib import Path
        text_path = Path(paper.text_path)
        if not text_path.exists():
            print(f"\n[{i}] Text file not found: {paper.text_path}")
            continue

        print(f"\n[{i}] Generating embeddings: {paper.title[:60]}...")

        # Read text
        with open(paper.text_path, 'r', encoding='utf-8') as f:
            text = f.read()

        print(f"  Text Length: {len(text):,} characters")

        start_time = time.time()
        embedding = embedding_client.get_embedding(text)
        elapsed = time.time() - start_time

        print(f"  ✓ Dimension: {len(embedding)}")
        print(f"  ✓ Time: {elapsed:.2f}s")
        print(f"  ✓ First 5 values: {embedding[:5]}")


def demo_generate_recommendations(config):
    """Step 5: Generate recommendations."""
    print_section("STEP 5: Generate Recommendations", icon="🎯")

    session = init_db(config.database.url)
    recommender = RecommendationManager(config, session)

    print("Generating personalized recommendations...")
    print(f"  Strategies: keyword_semantic, interested_semantic, llm_themes")
    print(f"  Top K: 5\n")

    start_time = time.time()
    recommendations = recommender.recommend(
        top_k=5,
        record_recommendations=False
    )
    elapsed = time.time() - start_time

    print(f"✓ Generated {len(recommendations)} recommendations in {elapsed:.2f}s\n")

    for i, rec in enumerate(recommendations[:3], 1):
        paper = session.query(Paper).filter_by(id=rec.paper_id).first()
        print(f"[{i}] Score: {rec.final_score:.4f}")
        print(f"    Title: {paper.title[:70]}")
        print(f"    Source: {paper.source}")

    session.close()


def demo_generate_report(config):
    """Step 6: Generate daily report."""
    print_section("STEP 6: Generate Daily Report", icon="📊")

    session = init_db(config.database.url)
    generator = ReportGenerator(config, session)

    print("Generating AI-powered daily report...\n")

    start_time = time.time()
    report = generator.generate(
        top_k=5,
        save_to_db=False
    )
    elapsed = time.time() - start_time

    if report:
        print(f"✓ Generated report in {elapsed:.2f}s\n")
        print(f"  Report Date: {report['report_date']}")
        print(f"  Papers: {len(report['papers'])}")
        print(f"  Themes: {len(report['themes_used'])}")

        if report.get('highlights'):
            print_subsection("AI Highlights Preview")
            lines = report['highlights'].strip().split('\n')[:8]
            for line in lines:
                print(f"  {line}")

    session.close()


def main():
    """Run the complete workflow demo."""
    print("\n" + "=" * 80)
    print("  DAILY PAPER SYSTEM - COMPLETE WORKFLOW DEMO")
    print("=" * 80)
    print(f"\n  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  This demo showcases the complete paper processing pipeline\n")

    # Load configuration
    print("Loading configuration...")
    try:
        config = Config.from_env()
        print(f"✓ Configuration loaded")
        print(f"  - LLM: {config.llm.provider} / {config.llm.model}")
        print(f"  - Embedding: {config.embedding.api_url}")
        print(f"  - Database: {config.database.url}\n")
    except Exception as e:
        print(f"✗ Failed to load config: {e}\n")
        sys.exit(1)

    try:
        # Step 1: Fetch & Download
        papers = demo_fetch_and_download(config, num_papers=2)

        if not papers:
            print("\n⚠ No papers downloaded. Demo cannot continue.")
            sys.exit(1)

        # Step 2: Parse PDFs
        parsed_papers = demo_parse_pdfs(config, papers)

        if not parsed_papers:
            print("\n⚠ No papers parsed. Demo cannot continue.")
            sys.exit(1)

        # Step 3: Generate Summaries
        demo_generate_summaries(config, parsed_papers)

        # Step 4: Generate Embeddings
        demo_generate_embeddings(config, parsed_papers)

        # Step 5: Generate Recommendations
        demo_generate_recommendations(config)

        # Step 6: Generate Report
        demo_generate_report(config)

        # Summary
        print_section("✅ DEMO COMPLETED", icon="✅")
        print("\n  Workflow Steps Completed:")
        print(f"    1. ✓ Fetched & Downloaded {len(papers)} papers")
        print(f"    2. ✓ Parsed {len(parsed_papers)} PDFs")
        print(f"    3. ✓ Generated 3-step summaries (内容摘要, 深度研究, TLDR)")
        print(f"    4. ✓ Generated embeddings")
        print(f"    5. ✓ Generated recommendations")
        print(f"    6. ✓ Generated daily report")

        print("\n" + "=" * 80)
        print("  All steps completed successfully!")
        print("=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠ Demo interrupted by user")
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

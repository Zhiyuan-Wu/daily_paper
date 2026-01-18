"""
Daily report generation module.

Generates manual daily reports containing recommended papers
and AI-generated highlights.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from daily_paper.config import Config
from daily_paper.database import DailyReport, InterestTheme, Paper, PaperInteraction, Summary
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.summarizers.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generator for daily paper reports.

    Creates manually triggered reports containing:
    - List of recommended papers
    - AI-generated highlights and summary
    - Interest themes used for recommendations

    Typical usage:
        >>> config = Config.from_env()
        >>> generator = ReportGenerator(config, session)
        >>> report = generator.generate(top_k=10)
        >>> print(report['highlights'])

    Attributes:
        config: Application configuration.
        session: Database session.
        llm_client: LLM service client.
        recommendation_manager: Recommendation system manager.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        session: Optional[Session] = None,
        llm_client: Optional[LLMClient] = None,
        recommendation_manager: Optional[RecommendationManager] = None,
    ):
        """
        Initialize the report generator.

        Args:
            config: Application configuration.
            session: Database session.
            llm_client: LLM service client.
            recommendation_manager: Recommendation manager instance.
        """
        self.config = config or Config.from_env()
        self.session = session
        self.llm_client = llm_client or LLMClient(self.config.llm)
        self.recommendation_manager = recommendation_manager or RecommendationManager(
            self.config, self.session
        )

    def generate(
        self,
        top_k: int = 10,
        save_to_db: bool = True,
    ) -> dict:
        """
        Generate a daily report.

        Args:
            top_k: Number of papers to include in report.
            save_to_db: Whether to save report to database.

        Returns:
            Dictionary containing report data:
            {
                'report_date': datetime,
                'papers': List[Paper objects],
                'highlights': str,
                'themes_used': List[str],
                'recommendation_results': List[RecommendationResult],
            }
        """
        logger.info(f"Starting daily report generation with top-{top_k} papers")

        # Get recommendations
        logger.debug("Fetching recommendations for report")
        recommendation_results = self.recommendation_manager.recommend(
            top_k=top_k,
            record_recommendations=True,
        )

        if not recommendation_results:
            logger.warning("No recommendations available for report, using fallback to recent unread papers")
            # Fallback: Get recently fetched papers that haven't been read yet
            papers = self._get_recent_unread_papers(top_k)
            if not papers:
                logger.error("No papers available for report generation")
                return {}
            recommendation_results = None
            themes_used = []
        else:
            logger.info(f"Got {len(recommendation_results)} recommendations for report")
            # Get paper objects
            paper_ids = [r.paper_id for r in recommendation_results]
            papers = (
                self.session.query(Paper)
                .filter(Paper.id.in_(paper_ids))
                .all()
            )

            # Sort papers by recommendation rank
            paper_rank = {r.paper_id: i for i, r in enumerate(recommendation_results)}
            papers.sort(key=lambda p: paper_rank.get(p.id, float('inf')))

            # Get active interest themes
            active_themes = (
                self.session.query(InterestTheme)
                .filter(InterestTheme.is_active == True)
                .all()
            )
            themes_used = [theme.theme for theme in active_themes]
            logger.debug(f"Using {len(themes_used)} interest themes")

        # Generate highlights
        logger.debug("Generating AI highlights for report")
        highlights = self._generate_highlights(papers, themes_used)
        logger.info(f"Generated highlights: {len(highlights)} chars")

        # Build report
        report = {
            'report_date': datetime.now(),
            'papers': papers,
            'highlights': highlights,
            'themes_used': themes_used,
            'recommendation_results': recommendation_results,
        }

        # Save to database if requested
        if save_to_db:
            logger.debug("Saving report to database")
            self._save_report(report)

        logger.info(
            f"Report generation complete: {len(papers)} papers, "
            f"{len(themes_used)} themes, {len(highlights)} chars highlights"
        )
        return report

    def _get_recent_unread_papers(self, limit: int = 10) -> List[Paper]:
        """
        Get recently fetched papers that haven't been read yet.

        A paper is considered "unread" if:
        - It has no PaperInteraction record, OR
        - It has a PaperInteraction with action='no_action'

        Args:
            limit: Maximum number of papers to return.

        Returns:
            List of Paper objects, sorted by creation date (newest first).
        """
        # Subquery to get IDs of papers that have been marked (interested/not_interested)
        marked_paper_ids = (
            self.session.query(PaperInteraction.paper_id)
            .filter(PaperInteraction.action.in_(['interested', 'not_interested']))
            .distinct()
        )

        # Get recent papers that are NOT marked
        papers = (
            self.session.query(Paper)
            .filter(~Paper.id.in_(marked_paper_ids))
            .order_by(Paper.created_at.desc())
            .limit(limit)
            .all()
        )

        logger.info(f"Found {len(papers)} recent unread papers for fallback")
        return papers

    def _generate_highlights(
        self,
        papers: List[Paper],
        themes: List[str],
    ) -> str:
        """
        Generate highlights using LLM.

        Args:
            papers: List of recommended papers.
            themes: Interest themes used for recommendation.

        Returns:
            Generated highlights text.
        """
        # Validation: Check if papers list is empty
        if not papers:
            logger.warning("No papers provided for highlights generation")
            return "No papers available for highlights generation."

        # Prepare paper summaries
        paper_summaries = []
        for i, paper in enumerate(papers, 1):
            summary_lines = [f"{i}. {paper.title}"]
            summary_lines.append(f"   Authors: {paper.authors or 'Unknown'}")

            # Prioritize using TLDR summary
            tldr = None
            if paper.summaries:
                for summary in paper.summaries:
                    if summary.summary_type == "tldr":
                        tldr = summary.content
                        break
                    elif summary.summary_type == "content_summary" and not tldr:
                        tldr = summary.content

            # Build summary entry
            if tldr:
                summary_lines.append(f"   TLDR: {tldr[:300]}...")
            elif paper.abstract:
                summary_lines.append(f"   Abstract: {paper.abstract[:500]}...")
            else:
                logger.warning(f"Paper {paper.id} has no summary or abstract")
                summary_lines.append(f"   Abstract: N/A")

            paper_summaries.append("\n".join(summary_lines))

        # Build prompt
        system_prompt = """You are a research advisor creating a daily digest of recommended papers.

Your task:
1. Identify 3-5 key highlights from the recommended papers
2. Group related papers together by topic
3. Highlight novel methods, significant results, or emerging trends
4. Keep highlights concise but informative (2-3 sentences each)

Format your response as:
**Key Highlights:**
- Highlight 1
- Highlight 2
...

**Research Trends:**
- Trend 1
- Trend 2
..."""

        user_prompt = f"""Interest themes used for selection:\n" \
            f"{' '.join(f'- {t}' for t in themes)}\n\n" \
            f"Recommended papers:\n\n" \
            f"{'\n\n'.join(paper_summaries)}"""

        try:
            highlights = self.llm_client.chat_with_system(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=self.config.report.temperature,
            )

            logger.info("Generated highlights successfully")
            return highlights

        except Exception as e:
            logger.error(f"Failed to generate highlights: {e}")
            return "Highlights generation failed."

    def _save_report(self, report: dict) -> DailyReport:
        """
        Save report to database.

        Args:
            report: Report dictionary from generate().

        Returns:
            Saved DailyReport object.
        """
        try:
            # Serialize data
            paper_ids = [p.id for p in report['papers']]
            themes_ids_json = json.dumps(report['themes_used'])

            daily_report = DailyReport(
                report_date=report['report_date'],
                recommendations=json.dumps(paper_ids),
                highlights=report['highlights'],
                themes_used=themes_ids_json,
            )

            self.session.add(daily_report)
            self.session.commit()

            logger.info(f"Saved report to database (ID: {daily_report.id})")
            return daily_report

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            self.session.rollback()
            raise

    def get_recent_reports(
        self,
        limit: int = 10,
    ) -> List[DailyReport]:
        """
        Get recent daily reports.

        Args:
            limit: Maximum number of reports to return.

        Returns:
            List of DailyReport objects, most recent first.
        """
        reports = (
            self.session.query(DailyReport)
            .order_by(DailyReport.report_date.desc())
            .limit(limit)
            .all()
        )

        return reports

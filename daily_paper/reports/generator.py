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
from daily_paper.database import DailyReport, InterestTheme, Paper, Summary
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
        logger.info(f"Generating daily report with top-{top_k} papers")

        # Get recommendations
        recommendation_results = self.recommendation_manager.recommend(
            top_k=top_k,
            record_recommendations=True,
        )

        if not recommendation_results:
            logger.warning("No recommendations available for report")
            return {}

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

        # Generate highlights
        highlights = self._generate_highlights(papers, themes_used)

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
            self._save_report(report)

        logger.info(f"Generated report with {len(papers)} papers")
        return report

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
        # Prepare paper summaries
        paper_summaries = []
        for i, paper in enumerate(papers, 1):
            paper_summaries.append(
                f"{i}. {paper.title}\n"
                f"   Authors: {paper.authors or 'Unknown'}\n"
                f"   Abstract: {paper.abstract[:500] if paper.abstract else 'N/A'}..."
            )

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

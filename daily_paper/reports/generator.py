"""
Daily report generation module.

Generates manual daily reports containing recommended papers
and AI-generated highlights.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from daily_paper.config import Config
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.summarizers.llm_client import LLMClient

if TYPE_CHECKING:
    from daily_paper.database.models import Paper

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
        >>> generator = ReportGenerator(config)
        >>> report = generator.generate(papers, themes, top_k=10)
        >>> print(report['highlights'])

    Attributes:
        config: Application configuration.
        llm_client: LLM service client.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize the report generator.

        Args:
            config: Application configuration.
            llm_client: LLM service client.
        """
        self.config = config or Config.from_env()
        self.llm_client = llm_client or LLMClient(self.config.llm)

    def generate(
        self,
        papers: List[Paper],
        themes: List[str],
        top_k: int = 10,
        save_to_db: bool = False,
    ) -> dict:
        """
        Generate a daily report.

        Args:
            papers: List of papers to include in report (already recommended).
            themes: Interest themes used for recommendation.
            top_k: Number of papers to include in report (max).
            save_to_db: DEPRECATED - This parameter is kept for backward compatibility
                        but has no effect. Database saving is handled by the caller.

        Returns:
            Dictionary containing report data:
            {
                'report_date': datetime,
                'papers': List[Paper objects],
                'highlights': str,
                'themes_used': List[str],
            }
        """
        logger.info(f"Starting daily report generation with {len(papers)} papers")

        if not papers:
            logger.warning("No papers provided for report generation")
            return {}

        # Limit to top_k papers
        papers = papers[:top_k]

        # Generate highlights
        logger.debug("Generating AI highlights for report")
        highlights = self._generate_highlights(papers, themes)
        logger.info(f"Generated highlights: {len(highlights)} chars")

        # Build report
        report = {
            'report_date': datetime.now(),
            'papers': papers,
            'highlights': highlights,
            'themes_used': themes,
        }

        logger.info(
            f"Report generation complete: {len(papers)} papers, "
            f"{len(themes)} themes, {len(highlights)} chars highlights"
        )
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

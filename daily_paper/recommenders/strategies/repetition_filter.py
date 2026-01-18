"""
Repetition downweighting filter recommender.

This strategy reduces scores for papers that have been recommended multiple
times without user interaction, preventing repetitive recommendations.
"""

from __future__ import annotations

import logging
from typing import List

from daily_paper.config import Config
from daily_paper.database import Paper, PaperInteraction
from daily_paper.recommenders.base import BaseRecommender, RecommendationResult

logger = logging.getLogger(__name__)


class RepetitionFilterRecommender(BaseRecommender):
    """
    Downweight papers that have been recommended multiple times.

    This strategy:
    1. Retrieves recommendation_count for each candidate paper
    2. Applies downweight formula: score / (1 + factor * (count - 1))
    3. Excludes papers exceeding max_recommendations threshold
    4. Returns adjusted scores (can be used to modify other strategy scores)

    Note: This strategy requires base scores from other strategies to be
    effective. When used in fusion, it modifies the combined scores.

    Typical usage:
        >>> # Use after getting scores from other strategies
        >>> recommender = RepetitionFilterRecommender(session, config)
        >>> adjusted = recommender.adjust_scores(base_results)
        >>>
        >>> # Or use standalone (returns neutral scores with metadata)
        >>> results = recommender.recommend(candidate_papers, top_k=10)

    Attributes:
        session: Database session.
        config: Application configuration.
    """

    def __init__(self, session, config: Config = None):
        """
        Initialize the repetition filter recommender.

        Args:
            session: SQLAlchemy database session.
            config: Application configuration.
        """
        super().__init__(session, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "repetition_filter"

    def recommend(
        self,
        candidate_papers: List[Paper],
        top_k: int = 10,
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Analyze recommendation counts and provide downweighting information.

        Args:
            candidate_papers: List of papers to analyze.
            top_k: Maximum number of results.
            **kwargs: Additional parameters (downweight_factor, max_recommendations).

        Returns:
            List of RecommendationResult with scores representing the
            downweight factor to apply (lower = more downweighting needed).
            Score formula: 1.0 / (1 + factor * (count - 1))

        Implementation details:
            - Retrieves recommendation_count from PaperInteraction table
            - Calculates downweight factor for each paper
            - Papers at max_recommendations get score of 0.0 (should be excluded)
            - Never-recommended papers get score of 1.0 (no downweighting)
        """
        # Get configuration
        downweight_factor = kwargs.get("downweight_factor", self.config.recommendation.downweight_factor)
        max_recommendations = kwargs.get("max_recommendations", self.config.recommendation.max_recommendations)

        logger.info(
            f"Repetition filter: Analyzing {len(candidate_papers)} papers "
            f"(factor={downweight_factor}, max={max_recommendations})"
        )

        # Get recommendation counts for all candidate papers
        paper_ids = [p.id for p in candidate_papers]
        interactions = (
            self.session.query(PaperInteraction.paper_id, PaperInteraction.recommendation_count)
            .filter(PaperInteraction.paper_id.in_(paper_ids))
            .all()
        )

        # Build count mapping
        rec_counts = {paper_id: count for paper_id, count in interactions}

        results = []
        excluded_count = 0

        for paper in candidate_papers:
            count = rec_counts.get(paper.id, 0)

            # Check if paper should be excluded
            if count >= max_recommendations:
                excluded_count += 1
                results.append(
                    RecommendationResult(
                        paper_id=paper.id,
                        score=0.0,
                        reason=f"Exceeded max recommendations ({count} >= {max_recommendations})",
                        strategy_name=self.strategy_name,
                    )
                )
                continue

            # Calculate downweight factor
            # count=0 -> factor=1.0 (no downweighting)
            # count=1 -> factor=1.0 (first recommendation, no downweighting yet)
            # count=2 -> factor=1/(1+factor*1) (second recommendation, slight downweighting)
            if count <= 1:
                downweight = 1.0
                reason = "Not previously recommended" if count == 0 else "First recommendation"
            else:
                downweight = 1.0 / (1.0 + downweight_factor * (count - 1))
                reason = f"Recommended {count} times, downweight factor: {downweight:.3f}"

            results.append(
                RecommendationResult(
                    paper_id=paper.id,
                    score=downweight,
                    reason=f"{reason} (count={count})",
                    strategy_name=self.strategy_name,
                )
            )

        logger.info(
            f"Repetition filter: {excluded_count} papers excluded, "
            f"{len(results) - excluded_count} papers eligible"
        )

        return results[:top_k]

    def adjust_scores(
        self,
        base_results: List[RecommendationResult],
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Adjust recommendation scores using repetition downweighting.

        This is a convenience method to apply repetition filtering to results
        from other strategies.

        Args:
            base_results: Results from other strategies to adjust.
            **kwargs: Additional parameters for downweight calculation.

        Returns:
            New RecommendationResult list with adjusted scores.

        Examples:
            >>> base_results = keyword_recommender.recommend(papers, top_k=10)
            >>> adjusted = repetition_recommender.adjust_scores(base_results)
            >>> # adjusted[i].score = base_results[i].score * downweight_factor
        """
        # Get paper IDs from base results
        paper_ids = [r.paper_id for r in base_results]

        # Get papers for these IDs
        from daily_paper.database import Paper
        papers = self.session.query(Paper).filter(Paper.id.in_(paper_ids)).all()
        paper_map = {p.id: p for p in papers}

        # Get downweight factors
        downweight_results = self.recommend(papers, top_k=len(papers), **kwargs)
        downweight_map = {r.paper_id: r.score for r in downweight_results}

        # Apply downweighting
        adjusted = []
        for base_result in base_results:
            downweight = downweight_map.get(base_result.paper_id, 1.0)

            if downweight == 0.0:
                # Paper should be excluded
                continue

            adjusted_score = base_result.score * downweight

            adjusted.append(
                RecommendationResult(
                    paper_id=base_result.paper_id,
                    score=adjusted_score,
                    reason=f"{base_result.reason} | Downweight: {downweight:.3f}",
                    strategy_name=base_result.strategy_name,
                )
            )

        logger.info(f"Repetition filter: Adjusted {len(adjusted)} scores (excluded {len(base_results) - len(adjusted)})")

        return adjusted

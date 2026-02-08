"""
Repetition downweighting filter recommender.

This strategy reduces scores for papers that have been recommended multiple
times without user interaction, preventing repetitive recommendations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from daily_paper.config import Config
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.recommenders.base import BaseRecommender, RecommendationContext, RecommendationResult

if TYPE_CHECKING:
    from daily_paper.database.models import Paper

logger = logging.getLogger(__name__)


class RepetitionFilterRecommender(BaseRecommender):
    """
    Downweight papers that have been recommended multiple times.

    This strategy:
    1. Retrieves recommendation_count for each candidate paper from context
    2. Applies downweight formula: score / (1 + factor * (count - 1))
    3. Excludes papers exceeding max_recommendations threshold
    4. Returns adjusted scores (can be used to modify other strategy scores)

    Note: This strategy requires base scores from other strategies to be
    effective. When used in fusion, it modifies the combined scores.

    Typical usage:
        >>> # Use standalone (returns neutral scores with metadata)
        >>> recommender = RepetitionFilterRecommender(embedding_client, config)
        >>> context = RecommendationContext(candidate_papers=papers, recommendation_counts={...})
        >>> results = recommender.recommend(context, top_k=10)

    Attributes:
        config: Application configuration.
        embedding_client: Embedding service client.
    """

    def __init__(self, embedding_client: EmbeddingClient, config: Config = None):
        """
        Initialize the repetition filter recommender.

        Args:
            embedding_client: Embedding service client.
            config: Application configuration.
        """
        super().__init__(embedding_client, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "repetition_filter"

    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Analyze recommendation counts and provide downweighting information.

        Args:
            context: RecommendationContext containing candidate papers and recommendation counts.
            top_k: Maximum number of results.

        Returns:
            List of RecommendationResult with scores representing the
            downweight factor to apply (lower = more downweighting needed).
            Score formula: 1.0 / (1 + factor * (count - 1))

        Implementation details:
            - Retrieves recommendation_count from context.recommendation_counts
            - Calculates downweight factor for each paper
            - Papers at max_recommendations get score of 0.0 (should be excluded)
            - Never-recommended papers get score of 1.0 (no downweighting)
        """
        # Get configuration
        downweight_factor = self.config.recommendation.downweight_factor
        max_recommendations = self.config.recommendation.max_recommendations

        logger.info(
            f"Repetition filter: Analyzing {len(context.candidate_papers)} papers "
            f"(factor={downweight_factor}, max={max_recommendations})"
        )

        results = []
        excluded_count = 0

        for paper in context.candidate_papers:
            count = context.get_recommendation_count(paper.id)

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

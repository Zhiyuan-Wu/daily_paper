"""
Disinterested keyword filter recommender.

This strategy filters out papers that match the user's disinterested keywords,
assigning negative scores to papers containing these terms.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, List

from daily_paper.config import Config
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.recommenders.base import BaseRecommender, RecommendationContext, RecommendationResult

if TYPE_CHECKING:
    from daily_paper.database.models import Paper

logger = logging.getLogger(__name__)


class DisinterestedFilterRecommender(BaseRecommender):
    """
    Filter out papers matching disinterested keywords.

    This strategy:
    1. Uses user's disinterested_keywords from context (if available)
    2. Checks each paper's title and abstract for keyword matches
    3. Assigns negative scores to papers containing disinterested terms
    4. Returns all papers with scores (negative for matches, neutral for non-matches)

    In a fusion system, papers with negative scores from this strategy
    will be downweighted in the final ranking.

    Typical usage:
        >>> recommender = DisinterestedFilterRecommender(embedding_client, config)
        >>> context = RecommendationContext(candidate_papers=papers, user_keywords=[...])
        >>> results = recommender.recommend(context, top_k=100)
        >>> # Results will have negative scores for matching papers

    Attributes:
        config: Application configuration.
        embedding_client: Embedding service client.
    """

    def __init__(self, embedding_client: EmbeddingClient, config: Config = None):
        """
        Initialize the disinterested filter recommender.

        Args:
            embedding_client: Embedding service client.
            config: Application configuration.
        """
        super().__init__(embedding_client, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "disinterested_filter"

    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Filter papers based on disinterested keywords.

        Args:
            context: RecommendationContext containing candidate papers and user keywords.
            top_k: Maximum number of results (note: this returns all candidates
                   with scores, not filtered to top_k, for fusion use).

        Returns:
            List of RecommendationResult with negative scores for papers
            matching disinterested keywords. Papers without matches get
            neutral scores (0.0).

        Implementation details:
            - Uses word boundary matching for keywords
            - Checks both title and abstract
            - Case-insensitive matching
            - Assigns -1.0 score for each keyword match (cumulative)
            - Note: context.user_keywords currently contains interested keywords,
              so this strategy returns neutral scores for all papers
        """
        # Get user keywords from context
        # Note: context.user_keywords contains interested keywords, not disinterested
        # Since there's no disinterested_keywords field in the context, we return neutral scores
        logger.info("No disinterested keywords available in context, returning neutral scores")

        # Return all papers with neutral scores
        return [
            RecommendationResult(
                paper_id=paper.id,
                score=0.0,
                reason="No disinterested keywords configured",
                strategy_name=self.strategy_name,
            )
            for paper in context.candidate_papers
        ]

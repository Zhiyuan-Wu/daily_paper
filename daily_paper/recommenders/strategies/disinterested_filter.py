"""
Disinterested papers semantic filter recommender.

This strategy filters out papers that are semantically similar to papers
the user has marked as "not_interested", assigning negative scores.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from daily_paper.config import Config
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.embeddings.utils import cosine_similarity
from daily_paper.recommenders.base import BaseRecommender, RecommendationContext, RecommendationResult

if TYPE_CHECKING:
    from daily_paper.database.models import Paper

logger = logging.getLogger(__name__)


class DisinterestedSemanticRecommender(BaseRecommender):
    """
    Filter out papers similar to disinterested papers.

    This strategy:
    1. Retrieves papers marked as "not_interested"
    2. Calculates semantic similarity between candidates and disinterested papers
    3. Assigns NEGATIVE scores based on similarity (penalizes similar papers)

    This is the inverse of InterestedSemanticRecommender. Papers similar to
    what the user disliked get negative scores, downweighting them in fusion.

    Typical usage:
        >>> recommender = DisinterestedSemanticRecommender(embedding_client, config)
        >>> context = RecommendationContext(candidate_papers=papers, disinterested_paper_ids={...})
        >>> results = recommender.recommend(context, top_k=100)
        >>> # Results will have negative scores for papers similar to dislikes

    Attributes:
        config: Application configuration.
        embedding_client: Embedding service client.
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        config: Config = None,
    ):
        """
        Initialize the disinterested semantic recommender.

        Args:
            embedding_client: Embedding service client.
            config: Application configuration.
        """
        super().__init__(embedding_client, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "disinterested_semantic"

    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Filter papers based on similarity to disinterested papers.

        Args:
            context: RecommendationContext containing candidate papers and disinterested paper IDs.
            top_k: Maximum number of results.

        Returns:
            List of RecommendationResult with negative scores for papers
            similar to disinterested papers. Score magnitude indicates
            degree of similarity (more negative = more similar).

        Implementation details:
            - Gets papers marked "not_interested" from context
            - Calculates mean cosine similarity to disinterested papers
            - Assigns negative score = -avg_similarity
            - Papers with no similarity to disinterested get score 0.0
        """
        # Get disinterested papers from context
        disinterested_papers = context.get_disinterested_papers()

        if not disinterested_papers:
            logger.info("No disinterested papers found, returning neutral scores")
            return [
                RecommendationResult(
                    paper_id=paper.id,
                    score=0.0,
                    reason="No disinterested papers to compare",
                    strategy_name=self.strategy_name,
                )
                for paper in context.candidate_papers
            ]

        logger.info(
            f"Disinterested semantic: Found {len(disinterested_papers)} disinterested papers, "
            f"analyzing {len(context.candidate_papers)} candidates"
        )

        # Generate embeddings for disinterested papers
        try:
            disinterested_texts = []
            for paper in disinterested_papers:
                text_parts = []
                if paper.abstract:
                    text_parts.append(paper.abstract)
                disinterested_texts.append(" ".join(text_parts) if text_parts else "No content")

            disinterested_embeddings = self.embedding_client.get_embeddings(disinterested_texts)

            # Generate embeddings for candidate papers
            paper_texts = []
            for paper in context.candidate_papers:
                text_parts = []
                if paper.abstract:
                    text_parts.append(paper.abstract)
                paper_texts.append(" ".join(text_parts) if text_parts else "No content")

            paper_embeddings = self.embedding_client.get_embeddings(paper_texts)

        except Exception as e:
            logger.error(f"Failed to generate embeddings for disinterested semantic: {e}")
            return []

        # Calculate average similarity to disinterested papers for each candidate
        results = []

        for idx, paper_emb in enumerate(paper_embeddings):
            # Calculate similarity to each disinterested paper
            similarities = []
            for disinterested_emb in disinterested_embeddings:
                sim = cosine_similarity(paper_emb, disinterested_emb)
                similarities.append(sim)

            # Average similarity
            avg_similarity = sum(similarities) / len(similarities)

            # Assign negative score (penalty for being similar to dislikes)
            # Use a default threshold of 0.3
            similarity_threshold = 0.3
            if avg_similarity >= similarity_threshold:
                score = -avg_similarity
                reason = f"Similar to {len(disinterested_papers)} disinterested papers (avg: {avg_similarity:.3f})"
            else:
                score = 0.0
                reason = f"Not similar to disinterested papers (avg: {avg_similarity:.3f})"

            results.append(
                RecommendationResult(
                    paper_id=context.candidate_papers[idx].id,
                    score=score,
                    reason=reason,
                    strategy_name=self.strategy_name,
                )
            )

        logger.info(
            f"Disinterested semantic: {sum(1 for r in results if r.score < 0)} papers "
            f"penalized for similarity to disinterested papers"
        )

        return results

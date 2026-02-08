"""
Interested papers semantic similarity recommender.

This strategy recommends papers that are semantically similar to papers
the user has recently marked as interested.
"""

from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

from daily_paper.config import Config
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.embeddings.utils import cosine_similarity
from daily_paper.recommenders.base import BaseRecommender, RecommendationContext, RecommendationResult

if TYPE_CHECKING:
    from daily_paper.database.models import Paper

logger = logging.getLogger(__name__)


class InterestedSemanticRecommender(BaseRecommender):
    """
    Recommend papers similar to recently interested papers.

    This strategy:
    1. Uses papers marked as "interested" from context
    2. Calculates average semantic similarity between candidates and interested papers
    3. Returns candidates with highest average similarity

    This captures the user's current research interests by finding papers
    similar to what they've recently liked.

    Typical usage:
        >>> recommender = InterestedSemanticRecommender(embedding_client, config)
        >>> context = RecommendationContext(
        ...     candidate_papers=papers,
        ...     interested_paper_ids={1, 2, 3}
        ... )
        >>> results = recommender.recommend(context, top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: similarity={result.score:.3f}")

    Attributes:
        embedding_client: Embedding service client.
        config: Application configuration.
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        config: Config = None,
    ):
        """
        Initialize the interested semantic recommender.

        Args:
            embedding_client: Embedding service client.
            config: Application configuration.
        """
        super().__init__(embedding_client, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "interested_semantic"

    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations based on similarity to interested papers.

        Args:
            context: RecommendationContext with interested paper IDs.
            top_k: Maximum number of recommendations to return.

        Returns:
            List of RecommendationResult sorted by average similarity descending.

        Implementation details:
            - Gets interested papers from context
            - Generates embeddings for interested papers and candidates
            - Calculates mean cosine similarity for each candidate
            - Filters candidates below minimum similarity threshold
        """
        # Get configuration
        min_similarity = self.config.recommendation.min_similarity

        # Get interested papers from context
        interested_papers = context.get_interested_papers()

        if not interested_papers:
            logger.info("No interested papers provided in context")
            return []

        logger.info(
            f"Interested semantic: Found {len(interested_papers)} interested papers, "
            f"analyzing {len(context.candidate_papers)} candidates"
        )

        # Filter out read papers
        papers = self._filter_read_papers(context)
        if not papers:
            logger.warning("No papers after filtering read papers")
            return []

        # Validation: Filter interested papers with summaries or abstracts
        valid_interested = []
        for paper in interested_papers:
            text_parts = []

            # Prioritize using summary
            if paper.summaries:
                for summary in paper.summaries:
                    if summary.summary_type in ["tldr", "content_summary"]:
                        text_parts.append(summary.content)
                        break

            # Fallback to abstract
            if not text_parts and paper.abstract:
                text_parts.append(paper.abstract)

            if not text_parts:
                logger.warning(
                    f"Interested paper {paper.id} has no summary or abstract, skipping"
                )
                continue

            valid_interested.append(paper)

        if not valid_interested:
            logger.warning("No valid interested papers with summaries or abstracts")
            return []

        interested_papers = valid_interested

        # Validation: Filter candidate papers with summaries or abstracts
        valid_papers = []
        for paper in papers:
            text_parts = []

            # Prioritize using summary
            if paper.summaries:
                for summary in paper.summaries:
                    if summary.summary_type in ["tldr", "content_summary"]:
                        text_parts.append(summary.content)
                        break

            if not text_parts and paper.abstract:
                text_parts.append(paper.abstract)

            if not text_parts:
                logger.debug(
                    f"Paper {paper.id} has no summary or abstract, skipping"
                )
                continue

            valid_papers.append(paper)

        if not valid_papers:
            logger.warning("No valid candidate papers with summaries or abstracts")
            return []

        papers = valid_papers

        # Generate embeddings for interested papers
        try:
            interested_texts = []
            for paper in interested_papers:
                text_parts = []
                # Prioritize using summary
                if paper.summaries:
                    for summary in paper.summaries:
                        if summary.summary_type in ["tldr", "content_summary"]:
                            text_parts.append(summary.content)
                            break
                # Fallback to abstract
                if not text_parts and paper.abstract:
                    text_parts.append(paper.abstract)
                interested_texts.append(" ".join(text_parts) if text_parts else "No content")

            interested_embeddings = self.embedding_client.get_embeddings(interested_texts)

            # Generate embeddings for candidate papers
            paper_texts = []
            for paper in papers:
                text_parts = []
                # Prioritize using summary
                if paper.summaries:
                    for summary in paper.summaries:
                        if summary.summary_type in ["tldr", "content_summary"]:
                            text_parts.append(summary.content)
                            break
                if not text_parts and paper.abstract:
                    text_parts.append(paper.abstract)
                paper_texts.append(" ".join(text_parts) if text_parts else "No content")

            paper_embeddings = self.embedding_client.get_embeddings(paper_texts)

        except Exception as e:
            logger.error(f"Failed to generate embeddings for interested semantic: {e}")
            return []

        # Calculate average similarity for each candidate
        results = []
        for idx, paper_emb in enumerate(paper_embeddings):
            # Calculate similarity to each interested paper
            similarities = []
            for interested_emb in interested_embeddings:
                sim = cosine_similarity(paper_emb, interested_emb)
                similarities.append(sim)

            # Average similarity
            avg_similarity = sum(similarities) / len(similarities)

            if avg_similarity >= min_similarity:
                results.append(
                    RecommendationResult(
                        paper_id=papers[idx].id,
                        score=float(avg_similarity),
                        reason=f"Similar to {len(interested_papers)} interested papers (avg similarity: {avg_similarity:.3f})",
                        strategy_name=self.strategy_name,
                    )
                )

        # Sort by score and return top-K
        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(
            f"Interested semantic: Generated {len(results)} recommendations "
            f"(min_similarity={min_similarity:.2f})"
        )

        return results[:top_k]

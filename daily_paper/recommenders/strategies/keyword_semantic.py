"""
Keyword semantic similarity recommender.

This strategy recommends papers based on semantic similarity between
user interest keywords/descriptions and paper abstracts/summaries.
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


class KeywordSemanticRecommender(BaseRecommender):
    """
    Recommend papers based on semantic similarity to user interests.

    This strategy:
    1. Builds a query from user's interested_keywords
    2. Generates embedding for the query
    3. Calculates cosine similarity between query and paper embeddings
    4. Returns top-K papers above minimum similarity threshold

    Typical usage:
        >>> recommender = KeywordSemanticRecommender(embedding_client, config)
        >>> context = RecommendationContext(candidate_papers=papers, user_keywords=keywords)
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
        Initialize the keyword semantic recommender.

        Args:
            embedding_client: Embedding service client.
            config: Application configuration (uses default if None).
        """
        super().__init__(embedding_client, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "keyword_semantic"

    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations based on semantic similarity to user interests.

        Args:
            context: RecommendationContext with user keywords and candidate papers.
            top_k: Maximum number of recommendations to return.

        Returns:
            List of RecommendationResult sorted by similarity score descending.

        Implementation details:
            - Builds query from user profile keywords
            - Uses embedding service to generate vector representations
            - Calculates cosine similarity between query and papers
            - Filters papers below minimum similarity threshold
            - Returns top-K results by similarity score
        """
        # Get user keywords from context
        keywords = context.user_keywords
        if not keywords:
            logger.warning("No user keywords provided for keyword semantic recommendation")
            return []

        query_text = " ".join(keywords) if isinstance(keywords, list) else keywords
        logger.info(f"Keyword semantic: Query length={len(query_text)}, candidates={len(context.candidate_papers)}")

        # Get minimum similarity from config
        min_similarity = self.config.recommendation.min_similarity

        # Filter out read papers
        papers = self._filter_read_papers(context)
        if not papers:
            logger.warning("No papers after filtering read papers")
            return []

        # Validation: Filter papers with summaries or abstracts
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
            logger.warning("No valid papers with summaries or abstracts")
            return []

        papers = valid_papers

        # Generate embeddings
        try:
            query_embedding = self.embedding_client.get_embedding(query_text)

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
                paper_texts.append(" ".join(text_parts) if text_parts else "No content available")

            paper_embeddings = self.embedding_client.get_embeddings(paper_texts)

        except Exception as e:
            logger.error(f"Failed to generate embeddings for keyword semantic: {e}")
            return []

        # Calculate similarities
        results = []
        for idx, paper_emb in enumerate(paper_embeddings):
            similarity = cosine_similarity(query_embedding, paper_emb)

            if similarity >= min_similarity:
                results.append(
                    RecommendationResult(
                        paper_id=papers[idx].id,
                        score=float(similarity),
                        reason=f"Semantic similarity to user interests: {similarity:.3f}",
                        strategy_name=self.strategy_name,
                    )
                )

        # Sort by score and return top-K
        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"Keyword semantic: Generated {len(results)} recommendations (min_similarity={min_similarity:.2f})")

        return results[:top_k]

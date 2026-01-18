"""
Keyword semantic similarity recommender.

This strategy recommends papers based on semantic similarity between
user interest keywords/descriptions and paper abstracts/summaries.
"""

from __future__ import annotations

import logging
from typing import List

from daily_paper.config import Config
from daily_paper.database import Paper, UserProfile
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.embeddings.utils import cosine_similarity
from daily_paper.recommenders.base import BaseRecommender, RecommendationResult

logger = logging.getLogger(__name__)


class KeywordSemanticRecommender(BaseRecommender):
    """
    Recommend papers based on semantic similarity to user interests.

    This strategy:
    1. Builds a query from user's interested_keywords and interest_description
    2. Generates embedding for the query
    3. Calculates cosine similarity between query and paper embeddings
    4. Returns top-K papers above minimum similarity threshold

    Typical usage:
        >>> recommender = KeywordSemanticRecommender(session, config, embedding_client)
        >>> results = recommender.recommend(candidate_papers, top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: similarity={result.score:.3f}")

    Attributes:
        session: Database session.
        config: Application configuration.
        embedding_client: Embedding service client.
    """

    def __init__(
        self,
        session,
        config: Config = None,
        embedding_client: EmbeddingClient = None,
    ):
        """
        Initialize the keyword semantic recommender.

        Args:
            session: SQLAlchemy database session.
            config: Application configuration (uses default if None).
            embedding_client: Embedding service client (creates default if None).
        """
        super().__init__(session, config)
        self.config = config or Config.from_env()
        self.embedding_client = embedding_client or EmbeddingClient(self.config.embedding)

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "keyword_semantic"

    def recommend(
        self,
        candidate_papers: List[Paper],
        top_k: int = 10,
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations based on semantic similarity to user interests.

        Args:
            candidate_papers: List of papers to consider (pre-filtered).
            top_k: Maximum number of recommendations to return.
            **kwargs: Additional parameters (min_similarity can be overridden).

        Returns:
            List of RecommendationResult sorted by similarity score descending.

        Implementation details:
            - Builds query from user profile keywords and description
            - Uses embedding service to generate vector representations
            - Calculates cosine similarity between query and papers
            - Filters papers below minimum similarity threshold
            - Returns top-K results by similarity score
        """
        # Get user profile
        user_profile = self.session.query(UserProfile).first()
        if not user_profile:
            logger.warning("No user profile found for keyword semantic recommendation")
            return []

        # Build query from user interests
        query_parts = []
        if user_profile.interested_keywords:
            query_parts.append(user_profile.interested_keywords)
        if user_profile.interest_description:
            query_parts.append(user_profile.interest_description)

        if not query_parts:
            logger.warning("No user interests configured for keyword semantic recommendation")
            return []

        query_text = " ".join(query_parts)
        logger.info(f"Keyword semantic: Query length={len(query_text)}, candidates={len(candidate_papers)}")

        # Get minimum similarity from config or kwargs
        min_similarity = kwargs.get("min_similarity", self.config.recommendation.min_similarity)

        # Filter out read papers
        papers = self._filter_read_papers(candidate_papers)
        if not papers:
            logger.warning("No papers after filtering read papers")
            return []

        # Generate embeddings
        try:
            query_embedding = self.embedding_client.get_embedding(query_text)

            paper_texts = []
            for paper in papers:
                text_parts = []
                if paper.abstract:
                    text_parts.append(paper.abstract)
                # Could also add summary if available
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

"""
Interested papers semantic similarity recommender.

This strategy recommends papers that are semantically similar to papers
the user has recently marked as interested.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from daily_paper.config import Config
from daily_paper.database import Paper, PaperInteraction
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.embeddings.utils import cosine_similarity
from daily_paper.recommenders.base import BaseRecommender, RecommendationResult

logger = logging.getLogger(__name__)


class InterestedSemanticRecommender(BaseRecommender):
    """
    Recommend papers similar to recently interested papers.

    This strategy:
    1. Retrieves papers marked as "interested" in the last N days
    2. Calculates average semantic similarity between candidates and interested papers
    3. Returns candidates with highest average similarity

    This captures the user's current research interests by finding papers
    similar to what they've recently liked.

    Typical usage:
        >>> recommender = InterestedSemanticRecommender(session, config, embedding_client)
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
        Initialize the interested semantic recommender.

        Args:
            session: SQLAlchemy database session.
            config: Application configuration.
            embedding_client: Embedding service client.
        """
        super().__init__(session, config)
        self.config = config or Config.from_env()
        self.embedding_client = embedding_client or EmbeddingClient(self.config.embedding)

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "interested_semantic"

    def recommend(
        self,
        candidate_papers: List[Paper],
        top_k: int = 10,
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations based on similarity to interested papers.

        Args:
            candidate_papers: List of papers to consider.
            top_k: Maximum number of recommendations to return.
            **kwargs: Additional parameters (interested_days, min_similarity).

        Returns:
            List of RecommendationResult sorted by average similarity descending.

        Implementation details:
            - Gets papers marked "interested" in last interested_days (default 30)
            - Generates embeddings for interested papers and candidates
            - Calculates mean cosine similarity for each candidate
            - Filters candidates below minimum similarity threshold
        """
        # Get configuration
        interested_days = kwargs.get("interested_days", self.config.recommendation.interested_days)
        min_similarity = kwargs.get("min_similarity", self.config.recommendation.min_similarity)

        # Get recently interested papers
        cutoff_date = datetime.now() - timedelta(days=interested_days)

        interested_interactions = (
            self.session.query(PaperInteraction)
            .filter(
                PaperInteraction.action == "interested",
                PaperInteraction.created_at >= cutoff_date,
            )
            .all()
        )

        if not interested_interactions:
            logger.info(f"No interested papers in last {interested_days} days")
            return []

        interested_paper_ids = [i.paper_id for i in interested_interactions]

        # Get interested papers
        interested_papers = (
            self.session.query(Paper)
            .filter(Paper.id.in_(interested_paper_ids))
            .all()
        )

        if not interested_papers:
            logger.warning("Found interested interactions but no papers")
            return []

        logger.info(
            f"Interested semantic: Found {len(interested_papers)} interested papers "
            f"in last {interested_days} days, analyzing {len(candidate_papers)} candidates"
        )

        # Filter out read papers
        papers = self._filter_read_papers(candidate_papers)
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

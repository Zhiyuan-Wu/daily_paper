"""
Disinterested keyword filter recommender.

This strategy filters out papers that match the user's disinterested keywords,
assigning negative scores to papers containing these terms.
"""

from __future__ import annotations

import logging
import re
from typing import List

from daily_paper.config import Config
from daily_paper.database import Paper, UserProfile
from daily_paper.recommenders.base import BaseRecommender, RecommendationResult

logger = logging.getLogger(__name__)


class DisinterestedFilterRecommender(BaseRecommender):
    """
    Filter out papers matching disinterested keywords.

    This strategy:
    1. Retrieves user's disinterested_keywords from profile
    2. Checks each paper's title and abstract for keyword matches
    3. Assigns negative scores to papers containing disinterested terms
    4. Returns papers WITHOUT matches (for use in fusion filtering)

    In a fusion system, papers with negative scores from this strategy
    will be downweighted in the final ranking.

    Typical usage:
        >>> recommender = DisinterestedFilterRecommender(session, config)
        >>> results = recommender.recommend(candidate_papers, top_k=100)
        >>> # Results will have negative scores for matching papers

    Attributes:
        session: Database session.
        config: Application configuration.
    """

    def __init__(self, session, config: Config = None):
        """
        Initialize the disinterested filter recommender.

        Args:
            session: SQLAlchemy database session.
            config: Application configuration.
        """
        super().__init__(session, config)
        self.config = config or Config.from_env()

    @property
    def strategy_name(self) -> str:
        """Return strategy identifier."""
        return "disinterested_filter"

    def recommend(
        self,
        candidate_papers: List[Paper],
        top_k: int = 10,
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Filter papers based on disinterested keywords.

        Args:
            candidate_papers: List of papers to consider.
            top_k: Maximum number of results (note: this returns all candidates
                   with scores, not filtered to top_k, for fusion use).
            **kwargs: Additional parameters (not used).

        Returns:
            List of RecommendationResult with negative scores for papers
            matching disinterested keywords. Papers without matches get
            neutral scores (0.0).

        Implementation details:
            - Uses word boundary matching for keywords
            - Checks both title and abstract
            - Case-insensitive matching
            - Assigns -1.0 score for each keyword match (cumulative)
        """
        # Get user profile
        user_profile = self.session.query(UserProfile).first()
        if not user_profile:
            logger.warning("No user profile found for disinterested filter")
            return []

        # Get disinterested keywords
        disinterested_keywords = user_profile.disinterested_keywords
        if not disinterested_keywords:
            logger.info("No disinterested keywords configured, returning neutral scores")
            # Return all papers with neutral scores
            return [
                RecommendationResult(
                    paper_id=paper.id,
                    score=0.0,
                    reason="No disinterested keywords configured",
                    strategy_name=self.strategy_name,
                )
                for paper in candidate_papers
            ]

        # Parse keywords (comma or space separated)
        keywords = [k.strip().lower() for k in disinterested_keywords.replace(",", " ").split() if k.strip()]
        if not keywords:
            logger.info("No valid disinterested keywords found")
            return []

        logger.info(f"Disinterested filter: Checking {len(candidate_papers)} papers against {len(keywords)} keywords")

        # Compile regex patterns for each keyword (word boundary matching)
        patterns = [re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE) for keyword in keywords]

        results = []
        match_count = 0

        for paper in candidate_papers:
            # Text to search (title + abstract)
            search_text = ""
            if paper.title:
                search_text += paper.title.lower() + " "
            if paper.abstract:
                search_text += paper.abstract.lower()

            # Count keyword matches
            num_matches = 0
            matched_keywords = []
            for idx, pattern in enumerate(patterns):
                if pattern.search(search_text):
                    num_matches += 1
                    matched_keywords.append(keywords[idx])

            # Assign negative score based on number of matches
            # More matches = more negative score
            score = -float(num_matches)

            if num_matches > 0:
                match_count += 1
                reason = f"Contains disinterested keywords: {', '.join(matched_keywords)}"
            else:
                reason = "No disinterested keyword matches"

            results.append(
                RecommendationResult(
                    paper_id=paper.id,
                    score=score,
                    reason=reason,
                    strategy_name=self.strategy_name,
                )
            )

        logger.info(
            f"Disinterested filter: {match_count}/{len(candidate_papers)} papers matched disinterested keywords"
        )

        return results

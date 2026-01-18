"""
Base recommender interface for plugin architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from daily_paper.database.models import Paper


@dataclass
class RecommendationResult:
    """
    Result from a single recommender strategy.

    Attributes:
        paper_id: ID of the recommended paper.
        score: Confidence/relevance score (higher is better).
        reason: Human-readable explanation for the recommendation.
        strategy_name: Name of the strategy that produced this result.
    """

    paper_id: int
    score: float
    reason: str
    strategy_name: str

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "paper_id": self.paper_id,
            "score": self.score,
            "reason": self.reason,
            "strategy_name": self.strategy_name,
        }


class BaseRecommender(ABC):
    """
    Abstract base class for recommendation strategies.

    All recommender plugins must inherit from this class and implement
    the abstract methods. This enables a plugin architecture where new
    strategies can be added without modifying existing code.

    The typical workflow:
    1. RecommendationManager calls recommend() for each enabled strategy
    2. Each strategy returns a list of RecommendationResult
    3. FusionEngine combines all results using Reciprocal Rank Fusion

    Example:
        >>> recommender = KeywordSemanticRecommender(session, config)
        >>> results = recommender.recommend(candidate_papers, top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: {result.score}")
    """

    def __init__(
        self,
        session: Session,
        config: Optional[object] = None,
    ):
        """
        Initialize the recommender.

        Args:
            session: SQLAlchemy database session.
            config: Recommendation configuration object.
        """
        self.session = session
        self.config = config

    @abstractmethod
    def recommend(
        self,
        candidate_papers: List[Paper],
        top_k: int = 10,
        **kwargs,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations from candidate papers.

        Args:
            candidate_papers: List of papers to consider for recommendation.
            top_k: Maximum number of recommendations to return.
            **kwargs: Additional strategy-specific parameters.

        Returns:
            List of RecommendationResult objects, sorted by score descending.
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """
        Return the name of this recommendation strategy.

        Returns:
            Strategy identifier (e.g., 'keyword_semantic', 'interested_semantic').
        """
        pass

    def _filter_read_papers(
        self,
        papers: List[Paper],
    ) -> List[Paper]:
        """
        Filter out papers that have already been read.

        Helper method used by multiple strategies.

        Args:
            papers: List of candidate papers.

        Returns:
            List of papers that haven't been read yet.
        """
        from daily_paper.database.models import PaperInteraction

        read_paper_ids = set(
            self.session.query(PaperInteraction.paper_id)
            .filter(PaperInteraction.action.in_(["interested", "not_interested"]))
            .all()
        )
        read_paper_ids = {pid for (pid,) in read_paper_ids}

        return [p for p in papers if p.id not in read_paper_ids]

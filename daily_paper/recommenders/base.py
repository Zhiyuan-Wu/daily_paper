"""
Base recommender interface for plugin architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Set

if TYPE_CHECKING:
    from daily_paper.database.models import Paper


@dataclass
class RecommendationContext:
    """
    Context data for recommendation (replaces database access).

    This class encapsulates all data that recommenders need from the database,
    enabling recommenders to be database-free and testable.

    Attributes:
        candidate_papers: Papers to consider for recommendation.
        interested_paper_ids: IDs of papers the user is interested in.
        disinterested_paper_ids: IDs of papers the user is not interested in.
        user_keywords: User's interest keywords.
        recommendation_counts: How many times each paper was recommended.
        last_recommended_at: Last recommendation time for each paper.
    """

    candidate_papers: List[Paper]
    interested_paper_ids: Set[int] = field(default_factory=set)
    disinterested_paper_ids: Set[int] = field(default_factory=set)
    user_keywords: List[str] = field(default_factory=list)
    recommendation_counts: Dict[int, int] = field(default_factory=dict)
    last_recommended_at: Dict[int, datetime] = field(default_factory=dict)

    def get_interested_papers(self) -> List[Paper]:
        """Get papers that user is interested in."""
        return [p for p in self.candidate_papers if p.id in self.interested_paper_ids]

    def get_disinterested_papers(self) -> List[Paper]:
        """Get papers that user is not interested in."""
        return [p for p in self.candidate_papers if p.id in self.disinterested_paper_ids]

    def is_interested(self, paper_id: int) -> bool:
        """Check if paper is interested."""
        return paper_id in self.interested_paper_ids

    def is_disinterested(self, paper_id: int) -> bool:
        """Check if paper is disinterested."""
        return paper_id in self.disinterested_paper_ids

    def get_recommendation_count(self, paper_id: int) -> int:
        """Get how many times a paper was recommended."""
        return self.recommendation_counts.get(paper_id, 0)


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
        >>> recommender = KeywordSemanticRecommender(embedding_client, config)
        >>> context = RecommendationContext(candidate_papers=papers, user_keywords=keywords)
        >>> results = recommender.recommend(context, top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: {result.score}")
    """

    def __init__(
        self,
        embedding_client,
        config: Optional[object] = None,
    ):
        """
        Initialize the recommender.

        Args:
            embedding_client: Client for generating embeddings.
            config: Recommendation configuration object.
        """
        self.embedding_client = embedding_client
        self.config = config

    @abstractmethod
    def recommend(
        self,
        context: RecommendationContext,
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Generate recommendations based on context data.

        Args:
            context: RecommendationContext with all necessary data.
            top_k: Maximum number of recommendations to return.

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
        context: RecommendationContext,
    ) -> List[Paper]:
        """
        Filter out papers that have already been read.

        Helper method used by multiple strategies.

        Args:
            context: RecommendationContext containing interaction data.

        Returns:
            List of papers that haven't been read yet.
        """
        read_paper_ids = context.interested_paper_ids | context.disinterested_paper_ids
        return [p for p in context.candidate_papers if p.id not in read_paper_ids]

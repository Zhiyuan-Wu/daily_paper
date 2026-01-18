"""
Recommendation manager for orchestrating recommendation strategies.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from daily_paper.config import Config
from daily_paper.database import Paper, PaperInteraction
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.recommenders.base import RecommendationResult
from daily_paper.recommenders.fusion import FusionEngine
from daily_paper.recommenders.registry import StrategyRegistry
from daily_paper.summarizers.llm_client import LLMClient

# Import all strategies to register them
from daily_paper.recommenders.strategies import (
    DisinterestedFilterRecommender,
    DisinterestedSemanticRecommender,
    InterestedSemanticRecommender,
    KeywordSemanticRecommender,
    LLMThemeRecommender,
    RepetitionFilterRecommender,
)

logger = logging.getLogger(__name__)


class RecommendationManager:
    """
    Manager for recommendation system with multi-strategy fusion.

    Orchestrates multiple recommendation strategies and combines their
    results using Reciprocal Rank Fusion (RRF).

    Typical usage:
        >>> config = Config.from_env()
        >>> manager = RecommendationManager(config, session)
        >>> results = manager.recommend(top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: {result.score:.3f}")

    Attributes:
        config: Application configuration.
        session: Database session.
        embedding_client: Embedding service client.
        llm_client: LLM service client.
        fusion_engine: Fusion engine for combining strategy results.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        session: Optional[Session] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize the recommendation manager.

        Args:
            config: Application configuration.
            session: Database session.
            embedding_client: Embedding service client.
            llm_client: LLM service client.
        """
        self.config = config or Config.from_env()
        self.session = session
        self.embedding_client = embedding_client or EmbeddingClient(self.config.embedding)
        self.llm_client = llm_client or LLMClient(self.config.llm)

        # Register all strategies
        self._register_strategies()

        # Initialize fusion engine
        rrf_k = self.config.recommendation.rrf_k
        self.fusion_engine = FusionEngine(rrf_k=rrf_k)

        logger.info(
            f"Initialized RecommendationManager with {len(StrategyRegistry.list_strategies())} strategies"
        )

    def _register_strategies(self) -> None:
        """Register all available strategies."""
        # Register strategies if not already registered
        strategies = [
            ("keyword_semantic", KeywordSemanticRecommender),
            ("disinterested_filter", DisinterestedFilterRecommender),
            ("interested_semantic", InterestedSemanticRecommender),
            ("disinterested_semantic", DisinterestedSemanticRecommender),
            ("repetition_filter", RepetitionFilterRecommender),
            ("llm_themes", LLMThemeRecommender),
        ]

        for name, strategy_class in strategies:
            if not StrategyRegistry.is_registered(name):
                StrategyRegistry.register(name, strategy_class)

    def recommend(
        self,
        top_k: int = 10,
        candidate_papers: Optional[List[Paper]] = None,
        record_recommendations: bool = True,
        strategy_weights: Optional[Dict[str, float]] = None,
    ) -> List[RecommendationResult]:
        """
        Generate paper recommendations using configured strategies.

        Args:
            top_k: Number of recommendations to return.
            candidate_papers: Papers to consider (None = all unread papers).
            record_recommendations: Whether to record recommendations in database.
            strategy_weights: Optional weight overrides for fusion.

        Returns:
            List of RecommendationResult sorted by fused score.

        Implementation:
            1. Get enabled strategies from config
            2. Run each strategy independently
            3. Filter strategies (disinterested_filter, repetition_filter)
               are applied differently from scoring strategies
            4. Combine results using RRF fusion
            5. Return top-K fused recommendations
        """
        # Get enabled strategies
        enabled_strategies = self.config.recommendation.enabled_strategies
        if not enabled_strategies:
            logger.warning("No strategies enabled in configuration")
            return []

        # Get candidate papers
        if candidate_papers is None:
            logger.debug("Fetching candidate papers from database")
            candidate_papers = self._get_candidate_papers()

        if not candidate_papers:
            logger.warning("No candidate papers available")
            return []

        logger.info(
            f"Generating recommendations with {len(enabled_strategies)} strategies, "
            f"{len(candidate_papers)} candidates, top_k={top_k}"
        )

        # Set strategy weights if provided
        if strategy_weights:
            self.fusion_engine.set_strategy_weights(strategy_weights)

        # Separate filter and scoring strategies
        filter_strategies = ["disinterested_filter", "repetition_filter"]
        scoring_strategies = [s for s in enabled_strategies if s not in filter_strategies]
        active_filters = [s for s in filter_strategies if s in enabled_strategies]

        # Run scoring strategies
        all_results = {}
        for strategy_name in scoring_strategies:
            try:
                # Build kwargs based on strategy requirements
                strategy_kwargs = {
                    "session": self.session,
                    "config": self.config,
                    "embedding_client": self.embedding_client,
                }

                # Only add llm_client for strategies that need it
                if strategy_name == "llm_themes":
                    strategy_kwargs["llm_client"] = self.llm_client

                strategy = StrategyRegistry.get_strategy(strategy_name, **strategy_kwargs)

                results = strategy.recommend(candidate_papers, top_k=top_k * 2)
                all_results[strategy_name] = results
                logger.info(f"Strategy '{strategy_name}': {len(results)} results")

            except Exception as e:
                logger.error(f"Strategy '{strategy_name}' failed: {e}")
                continue

        if not all_results:
            logger.warning("No scoring strategies produced results")
            return []

        # Apply filter strategies if enabled
        filtered_paper_ids = set()
        for filter_name in active_filters:
            try:
                strategy = StrategyRegistry.get_strategy(
                    filter_name,
                    session=self.session,
                    config=self.config,
                    embedding_client=self.embedding_client,
                )

                filter_results = strategy.recommend(candidate_papers, top_k=len(candidate_papers))

                # For disinterested keyword filter: exclude papers with negative scores
                # For repetition filter: exclude papers with score 0.0
                for result in filter_results:
                    if result.score < 0:
                        filtered_paper_ids.add(result.paper_id)

                logger.info(f"Filter '{filter_name}': excluded {len(filtered_paper_ids)} papers")

            except Exception as e:
                logger.error(f"Filter '{filter_name}' failed: {e}")

        # Remove filtered papers from results
        if filtered_paper_ids:
            for strategy_name in all_results:
                all_results[strategy_name] = [
                    r for r in all_results[strategy_name] if r.paper_id not in filtered_paper_ids
                ]

        # Fuse results
        fused = self.fusion_engine.fuse(all_results, top_k=top_k)

        # Record recommendations
        if record_recommendations and fused:
            logger.debug(f"Recording {len(fused)} recommendations to database")
            self._record_recommendations(fused)

        logger.info(
            f"Recommendation generation complete: {len(fused)} recommendations, "
            f"top_score={fused[0].score:.4f if fused else 0:.4f}"
        )
        return fused

    def _get_candidate_papers(self) -> List[Paper]:
        """
        Get candidate papers for recommendation.

        Returns:
            List of papers to consider for recommendation.
        """
        # Get IDs of papers that have been read
        read_paper_ids = set(
            pid
            for (pid,) in self.session.query(PaperInteraction.paper_id)
            .filter(PaperInteraction.action.in_(["interested", "not_interested"]))
            .all()
        )

        # Filter out read papers
        if read_paper_ids:
            candidates = (
                self.session.query(Paper)
                .filter(~Paper.id.in_(read_paper_ids))
                .all()
            )
        else:
            candidates = self.session.query(Paper).all()

        logger.info(f"Found {len(candidates)} candidate papers")
        return candidates

    def _record_recommendations(self, results: List[RecommendationResult]) -> None:
        """
        Record recommendations in database.

        Args:
            results: Recommendation results to record.
        """
        try:
            for result in results:
                # Get or create interaction record
                interaction = (
                    self.session.query(PaperInteraction)
                    .filter(PaperInteraction.paper_id == result.paper_id)
                    .first()
                )

                if interaction:
                    # Update recommendation count
                    interaction.recommendation_count += 1
                    interaction.last_recommended_at = datetime.now()
                else:
                    # Create new interaction record
                    interaction = PaperInteraction(
                        user_id=1,
                        paper_id=result.paper_id,
                        action="no_action",
                        recommendation_count=1,
                        last_recommended_at=datetime.now(),
                    )
                    self.session.add(interaction)

            self.session.commit()
            logger.info(f"Recorded {len(results)} recommendations in database")

        except Exception as e:
            logger.error(f"Failed to record recommendations: {e}")
            self.session.rollback()

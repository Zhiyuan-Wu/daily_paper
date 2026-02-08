"""
Recommendation manager for orchestrating recommendation strategies.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from daily_paper.config import Config
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.recommenders.base import RecommendationContext, RecommendationResult
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
        >>> manager = RecommendationManager(config)
        >>> context = RecommendationContext(
        ...     candidate_papers=papers,
        ...     interested_paper_ids={1, 2},
        ...     user_keywords=["machine learning"],
        ...     recommendation_counts={},
        ... )
        >>> results = manager.recommend(context, top_k=10)
        >>> for result in results:
        ...     print(f"Paper {result.paper_id}: {result.score:.3f}")

    Attributes:
        config: Application configuration.
        embedding_client: Embedding service client.
        llm_client: LLM service client.
        fusion_engine: Fusion engine for combining strategy results.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize the recommendation manager.

        Args:
            config: Application configuration.
            embedding_client: Embedding service client.
            llm_client: LLM service client.
        """
        self.config = config or Config.from_env()
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
        context: RecommendationContext,
        top_k: int = 10,
        strategy_weights: Optional[Dict[str, float]] = None,
    ) -> List[RecommendationResult]:
        """
        Generate paper recommendations using configured strategies.

        Args:
            context: RecommendationContext with all necessary data.
            top_k: Number of recommendations to return.
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

        if not context.candidate_papers:
            logger.warning("No candidate papers provided in context")
            return []

        logger.info(
            f"Generating recommendations with {len(enabled_strategies)} strategies, "
            f"{len(context.candidate_papers)} candidates, top_k={top_k}"
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
                    "embedding_client": self.embedding_client,
                    "config": self.config,
                }

                # Only add llm_client for strategies that need it
                if strategy_name == "llm_themes":
                    strategy_kwargs["llm_client"] = self.llm_client

                strategy = StrategyRegistry.get_strategy(strategy_name, **strategy_kwargs)

                results = strategy.recommend(context, top_k=top_k * 2)
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
                    embedding_client=self.embedding_client,
                    config=self.config,
                )

                filter_results = strategy.recommend(context, top_k=len(context.candidate_papers))

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

        logger.info(
            f"Recommendation generation complete: {len(fused)} recommendations, "
            f"top_score={(fused[0].score if fused else 0):.4f}"
        )
        return fused

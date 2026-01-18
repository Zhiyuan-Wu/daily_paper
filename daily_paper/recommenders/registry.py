"""
Strategy registry for plugin-based recommendation system.

This module provides a central registry for recommendation strategies,
enabling a plugin architecture where new strategies can be added
without modifying existing code.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from daily_paper.recommenders.base import BaseRecommender

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Plugin registry for recommendation strategies.

    The registry maintains a mapping of strategy names to strategy classes,
    allowing dynamic instantiation and orchestration of multiple recommendation
    strategies.

    Typical usage:
        >>> # Register strategies at startup
        >>> StrategyRegistry.register("keyword_semantic", KeywordSemanticRecommender)
        >>> StrategyRegistry.register("interested_semantic", InterestedSemanticRecommender)
        >>>
        >>> # Get strategy instance
        >>> strategy = StrategyRegistry.get_strategy("keyword_semantic", session, config)
        >>> results = strategy.recommend(papers, top_k=10)

    Attributes:
        _strategies: Class-level dict mapping strategy names to classes.
    """

    _strategies: Dict[str, Type[BaseRecommender]] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseRecommender]) -> None:
        """
        Register a recommendation strategy class.

        Args:
            name: Unique identifier for the strategy (e.g., 'keyword_semantic').
            strategy_class: Class inheriting from BaseRecommender.

        Raises:
            ValueError: If strategy name is already registered.
            TypeError: If strategy_class doesn't inherit from BaseRecommender.

        Examples:
            >>> StrategyRegistry.register("my_strategy", MyRecommender)
        """
        if name in cls._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")

        if not issubclass(strategy_class, BaseRecommender):
            raise TypeError(
                f"Strategy class must inherit from BaseRecommender, "
                f"got {strategy_class.__name__}"
            )

        cls._strategies[name] = strategy_class
        logger.info(f"Registered strategy: {name} ({strategy_class.__name__})")

    @classmethod
    def get_strategy(cls, name: str, **kwargs) -> BaseRecommender:
        """
        Instantiate a strategy by name.

        Args:
            name: Strategy identifier.
            **kwargs: Arguments to pass to strategy constructor.

        Returns:
            Instantiated strategy object.

        Raises:
            ValueError: If strategy name is not registered.

        Examples:
            >>> strategy = StrategyRegistry.get_strategy(
            ...     "keyword_semantic",
            ...     session=session,
            ...     config=config,
            ...     embedding_client=embedding_client
            ... )
        """
        if name not in cls._strategies:
            available = ", ".join(cls.list_strategies())
            raise ValueError(
                f"Unknown strategy: '{name}'. Available strategies: {available}"
            )

        strategy_class = cls._strategies[name]
        logger.debug(f"Instantiating strategy: {name}")
        return strategy_class(**kwargs)

    @classmethod
    def list_strategies(cls) -> List[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy identifiers.

        Examples:
            >>> StrategyRegistry.list_strategies()
            ['keyword_semantic', 'interested_semantic', 'llm_themes']
        """
        return list(cls._strategies.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a strategy is registered.

        Args:
            name: Strategy identifier.

        Returns:
            True if strategy is registered, False otherwise.
        """
        return name in cls._strategies

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister a strategy.

        Args:
            name: Strategy identifier to remove.

        Raises:
            ValueError: If strategy name is not registered.

        Note:
            This is primarily useful for testing. In production, strategies
            should remain registered once initialized.
        """
        if name not in cls._strategies:
            raise ValueError(f"Cannot unregister unknown strategy: '{name}'")

        del cls._strategies[name]
        logger.info(f"Unregistered strategy: {name}")

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered strategies.

        Note:
            This is primarily useful for testing. Use with caution.
        """
        cls._strategies.clear()
        logger.warning("Cleared all registered strategies")

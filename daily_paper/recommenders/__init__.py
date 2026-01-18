"""
Recommendation module for plugin-based paper recommendation.

This module provides a plugin architecture where different recommendation
strategies can be plugged in and combined using fusion algorithms.
"""

from daily_paper.recommenders.base import BaseRecommender, RecommendationResult
from daily_paper.recommenders.fusion import FusionEngine
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.recommenders.registry import StrategyRegistry

__all__ = [
    "RecommendationManager",
    "StrategyRegistry",
    "FusionEngine",
    "BaseRecommender",
    "RecommendationResult",
]

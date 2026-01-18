"""
Fusion engine for combining multiple recommendation strategies.

Uses Reciprocal Rank Fusion (RRF) to combine rankings from different
strategies into a single unified ranking.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List

from daily_paper.recommenders.base import RecommendationResult

logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Combine multiple recommendation strategies using Reciprocal Rank Fusion.

    RRF is robust to differences in score scales between strategies and
    only requires rankings (not absolute scores) from each strategy.

    RRF Formula:
        score(paper) = Σ weight_strategy * (1 / (k + rank_strategy(paper)))

    where k is a constant (default 60) that controls the impact of rank.

    Typical usage:
        >>> fusion = FusionEngine(rrf_k=60)
        >>> fusion.set_strategy_weights({"keyword_semantic": 1.5, "interested_semantic": 2.0})
        >>> results = fusion.fuse(strategy_results, top_k=10)

    Attributes:
        rrf_k: RRF constant (higher = rank matters less).
        strategy_weights: Weight multiplier for each strategy.
    """

    def __init__(self, rrf_k: int = 60):
        """
        Initialize the fusion engine.

        Args:
            rrf_k: RRF constant. Default 60 means:
                   - Rank 1: 1/61 ≈ 0.0164
                   - Rank 10: 1/70 ≈ 0.0143
                   - Rank 100: 1/160 ≈ 0.0063
                   Higher k reduces the difference between ranks.
        """
        self.rrf_k = rrf_k
        self.strategy_weights: Dict[str, float] = {}

    def set_strategy_weights(self, weights: Dict[str, float]) -> None:
        """
        Set weight multipliers for strategies.

        Args:
            weights: Dictionary mapping strategy names to weight multipliers.
                     Strategies not in the dict use weight 1.0.

        Examples:
            >>> fusion.set_strategy_weights({"keyword_semantic": 1.5, "llm_themes": 0.5})
        """
        self.strategy_weights = weights.copy()
        logger.info(f"Set strategy weights: {weights}")

    def get_strategy_weight(self, strategy_name: str) -> float:
        """
        Get weight for a strategy.

        Args:
            strategy_name: Name of the strategy.

        Returns:
            Weight multiplier (1.0 if not explicitly set).
        """
        return self.strategy_weights.get(strategy_name, 1.0)

    def fuse(
        self,
        strategy_results: Dict[str, List[RecommendationResult]],
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Fuse multiple strategy rankings using RRF.

        Args:
            strategy_results: Dictionary mapping strategy names to their result lists.
                              Each list should be sorted by score descending.
            top_k: Number of final results to return.

        Returns:
            Fused and ranked RecommendationResult list.

        Implementation details:
            1. For each strategy, calculate RRF contribution: weight * (1 / (k + rank))
            2. Sum contributions across all strategies for each paper
            3. Sort papers by total RRF score descending
            4. Return top-K results

        Note:
            Papers not ranked by a strategy implicitly contribute 0 to that paper's score.
        """
        if not strategy_results:
            logger.warning("No strategy results to fuse")
            return []

        # Accumulate RRF scores for each paper
        paper_scores = defaultdict(float)  # {paper_id: total_rrf_score}
        paper_reasons = defaultdict(list)  # {paper_id: [reasons from strategies]}

        for strategy_name, results in strategy_results.items():
            if not results:
                logger.debug(f"Strategy '{strategy_name}' produced no results")
                continue

            weight = self.get_strategy_weight(strategy_name)
            logger.debug(
                f"Fusing results from '{strategy_name}' (weight={weight}, count={len(results)})"
            )

            for rank, result in enumerate(results, start=1):
                # Calculate RRF score for this ranking
                rrf_score = weight * (1.0 / (self.rrf_k + rank))
                paper_scores[result.paper_id] += rrf_score

                # Track reasons for debugging
                if result.reason:
                    paper_reasons[result.paper_id].append(f"{strategy_name}: {result.reason}")

        # Sort by total RRF score
        sorted_papers = sorted(paper_scores.items(), key=lambda x: x[1], reverse=True)

        # Create final results
        fused_results = []
        for paper_id, rrf_score in sorted_papers[:top_k]:
            # Combine reasons from all strategies
            reasons = paper_reasons.get(paper_id, [])
            if reasons:
                reason_str = " | ".join(reasons)
            else:
                reason_str = f"RRF score: {rrf_score:.4f}"

            fused_results.append(
                RecommendationResult(
                    paper_id=paper_id,
                    score=float(rrf_score),
                    reason=reason_str,
                    strategy_name="fusion",
                )
            )

        logger.info(
            f"Fused {len(strategy_results)} strategies into {len(fused_results)} results "
            f"(rrf_k={self.rrf_k}, top_k={top_k})"
        )

        return fused_results

    def fuse_with_normalization(
        self,
        strategy_results: Dict[str, List[RecommendationResult]],
        top_k: int = 10,
    ) -> List[RecommendationResult]:
        """
        Alternative fusion method using score normalization before fusion.

        This method normalizes scores from each strategy to [0, 1] range before
        combining, which can be useful when strategies have different score scales.

        Args:
            strategy_results: Dictionary mapping strategy names to their result lists.
            top_k: Number of final results to return.

        Returns:
            Fused and ranked RecommendationResult list.

        Note:
            This is an alternative to pure RRF. Use this if you want to consider
            both ranking AND score magnitude from strategies.
        """
        if not strategy_results:
            logger.warning("No strategy results to fuse")
            return []

        # Normalize scores for each strategy
        normalized_results = {}
        for strategy_name, results in strategy_results.items():
            if not results:
                continue

            # Find min/max scores
            scores = [r.score for r in results]
            min_score = min(scores)
            max_score = max(scores)

            # Avoid division by zero
            if max_score == min_score:
                normalized = [RecommendationResult(
                    paper_id=r.paper_id,
                    score=1.0,  # All papers get same score
                    reason=r.reason,
                    strategy_name=r.strategy_name,
                ) for r in results]
            else:
                # Normalize to [0, 1]
                normalized = []
                for r in results:
                    norm_score = (r.score - min_score) / (max_score - min_score)
                    normalized.append(RecommendationResult(
                        paper_id=r.paper_id,
                        score=norm_score,
                        reason=r.reason,
                        strategy_name=r.strategy_name,
                    ))
                normalized.sort(key=lambda x: x.score, reverse=True)

            normalized_results[strategy_name] = normalized

        # Use RRF on normalized rankings
        return self.fuse(normalized_results, top_k)

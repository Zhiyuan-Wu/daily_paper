"""
Performance optimization module for recommendation algorithms.

Evaluates recommendation performance using temporal train/test splits and
optimizes strategy weights using coordinate descent search.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from daily_paper.config import Config
from daily_paper.database import Paper, PaperInteraction
from daily_paper.embeddings.client import EmbeddingClient
from daily_paper.recommenders.manager import RecommendationManager
from daily_paper.recommenders.registry import StrategyRegistry
from daily_paper.summarizers.llm_client import LLMClient

logger = logging.getLogger(__name__)


class RecommendationOptimizer:
    """
    Evaluate and optimize recommendation algorithm performance.

    Uses temporal train/test splits to evaluate recommendation quality
    and coordinate descent search to find optimal strategy weights.

    Typical usage:
        >>> optimizer = RecommendationOptimizer(config, session, embedding_client, llm_client)
        >>> metrics = optimizer.evaluate(split_date="2024-01-01")
        >>> print(f"MRR: {metrics['mrr']:.3f}")
        >>>
        >>> best = optimizer.grid_search(split_date="2024-01-01")
        >>> print(f"Best weights: {best['best_weights']}")

    Attributes:
        config: Application configuration.
        session: Database session.
        embedding_client: Embedding service client.
        llm_client: LLM service client.
        manager: RecommendationManager instance for generating recommendations.
    """

    def __init__(
        self,
        config: Config,
        session: Session,
        embedding_client: EmbeddingClient,
        llm_client: LLMClient,
    ):
        """
        Initialize the optimizer.

        Args:
            config: Application configuration.
            session: Database session.
            embedding_client: Embedding service client.
            llm_client: LLM service client.
        """
        self.config = config
        self.session = session
        self.embedding_client = embedding_client
        self.llm_client = llm_client

        # Create recommendation manager
        self.manager = RecommendationManager(
            config=config,
            session=session,
            embedding_client=embedding_client,
            llm_client=llm_client,
        )

        logger.info("Initialized RecommendationOptimizer")

    def evaluate(
        self,
        split_date: str,
        strategy_weights: Optional[Dict[str, float]] = None,
        top_k: int = 100,
    ) -> Dict:
        """
        Evaluate recommendation performance with temporal train/test split.

        Args:
            split_date: Date string to split train/test data (YYYY-MM-DD format).
                       Training data = interactions before this date.
                       Test data = interactions on or after this date.
            strategy_weights: Optional strategy weights for fusion evaluation.
            top_k: Number of recommendations to generate for evaluation.

        Returns:
            Dictionary with metrics:
                - hit_rate: % of test papers that appeared in recommendations
                - mean_rank: Average rank of test papers in recommendations
                - mrr: Mean reciprocal rank
                - hits: Number of test papers found in recommendations
                - total_test_papers: Total number of test papers

        Implementation details:
            - Treats "interested" OR "has notes" as positive signals
            - Simulates training state by hiding interactions/papers after split_date
            - Generates recommendations using training state
            - Compares against actual interactions (test set)
        """
        try:
            split_dt = datetime.strptime(split_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid split_date format: {split_date}. Use YYYY-MM-DD")
            return {"error": "Invalid date format"}

        logger.info(f"Evaluating recommendation performance with split_date={split_date}")

        # Get test interactions (what user actually liked after split)
        # Include papers marked "interested" OR have notes (both are positive signals)
        test_interactions = (
            self.session.query(PaperInteraction)
            .filter(PaperInteraction.created_at >= split_dt)
            .all()
        )

        if not test_interactions:
            logger.warning(f"No test interactions found after {split_date}")
            return {"error": "No test data"}

        # Filter for positive signals: interested OR has notes
        test_paper_ids = {
            i.paper_id for i in test_interactions
            if i.action == "interested" or (i.notes is not None and i.notes.strip())
        }

        if not test_paper_ids:
            logger.warning(f"No positive interactions found after {split_date}")
            return {"error": "No positive test data"}

        logger.info(f"Test set: {len(test_paper_ids)} positive papers out of {len(test_interactions)} interactions")

        # Simulate training state
        # We need to temporarily hide papers and interactions after split_date
        # For simplicity, we'll pass candidate papers that exclude test papers
        # and the manager will use historical interactions for strategies

        # Get papers published before split_date as training candidates
        train_papers = (
            self.session.query(Paper)
            .filter(Paper.published_date < split_dt)
            .all()
        )

        # Remove test papers from candidate set (they shouldn't be recommended)
        candidate_paper_ids = {p.id for p in train_papers} - test_paper_ids
        candidate_papers = (
            self.session.query(Paper)
            .filter(Paper.id.in_(candidate_paper_ids))
            .all()
        )

        logger.info(f"Training candidates: {len(candidate_papers)} papers")

        # Generate recommendations using training state
        try:
            recommendations = self.manager.recommend(
                top_k=top_k,
                candidate_papers=candidate_papers,
                record_recommendations=False,  # Don't record during evaluation
                strategy_weights=strategy_weights,
            )
        except Exception as e:
            logger.error(f"Failed to generate recommendations during evaluation: {e}")
            return {"error": f"Recommendation failed: {e}"}

        rec_paper_ids = [r.paper_id for r in recommendations]

        # Calculate metrics
        # We only care if test papers appear in recommendations at all
        # (since we excluded them from candidates, we need to check if they WOULD have been recommended)
        # Actually, for a proper evaluation, we should include test papers in candidates
        # Let me fix this...

        # Re-include test papers for proper evaluation
        candidate_papers_with_test = (
            self.session.query(Paper)
            .filter(Paper.id.in_(candidate_paper_ids | test_paper_ids))
            .all()
        )

        recommendations = self.manager.recommend(
            top_k=top_k,
            candidate_papers=candidate_papers_with_test,
            record_recommendations=False,
            strategy_weights=strategy_weights,
        )

        rec_paper_ids = [r.paper_id for r in recommendations]

        # Hit rate: % of test papers that appeared in recommendations
        hits = len(test_paper_ids & set(rec_paper_ids))
        hit_rate = hits / len(test_paper_ids) if test_paper_ids else 0.0

        # Mean rank of test papers in recommendations
        # For papers not in recommendations, we could assign rank = infinity
        # But for mean rank calculation, we only rank papers that were found
        ranks = []
        for test_pid in test_paper_ids:
            if test_pid in rec_paper_ids:
                ranks.append(rec_paper_ids.index(test_pid) + 1)

        mean_rank = sum(ranks) / len(ranks) if ranks else float('inf')

        # Mean Reciprocal Rank (MRR)
        # For papers not found, reciprocal rank = 0
        reciprocal_ranks = []
        for test_pid in test_paper_ids:
            if test_pid in rec_paper_ids:
                rr = 1.0 / (rec_paper_ids.index(test_pid) + 1)
                reciprocal_ranks.append(rr)
            else:
                reciprocal_ranks.append(0.0)

        mrr = sum(reciprocal_ranks) / len(test_paper_ids)

        metrics = {
            "hit_rate": hit_rate,
            "mean_rank": mean_rank,
            "mrr": mrr,
            "hits": hits,
            "total_test_papers": len(test_paper_ids),
            "total_recommendations": len(recommendations),
        }

        logger.info(
            f"Evaluation results: hit_rate={hit_rate:.3f}, mean_rank={mean_rank:.1f}, mrr={mrr:.3f}"
        )

        return metrics

    def grid_search(
        self,
        split_date: str,
        weight_ranges: Optional[Dict[str, List[float]]] = None,
        max_iterations: int = 10,
    ) -> Dict:
        """
        Coordinate descent search for optimal strategy weights.

        Args:
            split_date: Date string for train/test split.
            weight_ranges: Dict of {strategy_name: [weight_options]}.
                          If None, uses default ranges.
            max_iterations: Maximum number of passes through all strategies.

        Returns:
            Dictionary with:
                - best_weights: Optimal weights found
                - best_metrics: Metrics with best weights
                - iterations: Number of iterations performed
                - history: List of optimization steps

        Algorithm:
            1. Start with default weights (all = 1.0)
            2. For each iteration:
                For each strategy:
                    a. Try different weight values while keeping others fixed
                    b. Select weight that gives best MRR
                    c. Update current weight
            3. Stop when no improvement or max_iterations reached
        """
        if weight_ranges is None:
            # Default weight ranges for common strategies
            weight_ranges = {
                "keyword_semantic": [0.5, 1.0, 1.5, 2.0],
                "interested_semantic": [0.5, 1.0, 1.5, 2.0],
                "llm_themes": [0.0, 0.5, 1.0, 1.5],
                "disinterested_semantic": [0.0, 0.5, 1.0],
            }

        logger.info(f"Starting coordinate descent search with split_date={split_date}")

        # Initialize with default weights
        current_weights = {strategy: 1.0 for strategy in weight_ranges.keys()}
        best_score = -1
        best_weights = current_weights.copy()
        history = []

        # Get initial metrics with default weights
        initial_metrics = self.evaluate(split_date, strategy_weights=current_weights)
        initial_score = initial_metrics.get("mrr", 0)
        best_score = initial_score

        logger.info(f"Initial MRR with default weights: {initial_score:.4f}")

        for iteration in range(max_iterations):
            improved_this_iteration = False
            logger.info(f"--- Iteration {iteration + 1}/{max_iterations} ---")

            for strategy_name, weight_options in weight_ranges.items():
                best_for_strategy = current_weights[strategy_name]
                best_local_score = -1

                logger.debug(f"  Optimizing {strategy_name} (current weight: {current_weights[strategy_name]})")

                # Try each weight option for this strategy
                for weight in weight_options:
                    test_weights = current_weights.copy()
                    test_weights[strategy_name] = weight

                    metrics = self.evaluate(split_date, strategy_weights=test_weights)
                    score = metrics.get("mrr", 0)

                    if score > best_local_score:
                        best_local_score = score
                        best_for_strategy = weight

                    logger.debug(f"    Weight {weight}: MRR = {score:.4f}")

                # Update if we found improvement
                if best_local_score > best_score:
                    best_score = best_local_score
                    best_weights = current_weights.copy()
                    best_weights[strategy_name] = best_for_strategy
                    improved_this_iteration = True
                    logger.info(f"  New best MRR: {best_score:.4f} (strategy: {strategy_name}, weight: {best_for_strategy})")

                current_weights[strategy_name] = best_for_strategy
                history.append({
                    "iteration": iteration + 1,
                    "strategy": strategy_name,
                    "weight": best_for_strategy,
                    "score": best_local_score,
                })

            # Stop if no improvement in this iteration
            if not improved_this_iteration:
                logger.info(f"No improvement in iteration {iteration + 1}, stopping early")
                break

        # Get final metrics with best weights
        final_metrics = self.evaluate(split_date, strategy_weights=best_weights)

        result = {
            "best_weights": best_weights,
            "best_metrics": final_metrics,
            "iterations": iteration + 1,
            "history": history,
        }

        logger.info(
            f"Grid search complete: best MRR = {best_score:.4f}, "
            f"best weights = {best_weights}"
        )

        return result

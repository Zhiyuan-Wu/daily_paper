"""
Utility functions for embedding operations.

This module provides functions for calculating similarity metrics
and finding most similar items using embedding vectors.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity score between -1 and 1.

    Examples:
        >>> vec1 = [1.0, 0.0, 0.0]
        >>> vec2 = [1.0, 0.0, 0.0]
        >>> cosine_similarity(vec1, vec2)
        1.0
    """
    try:
        arr1 = np.array(vec1, dtype=np.float32)
        arr2 = np.array(vec2, dtype=np.float32)

        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        return 0.0


def cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine distance between two vectors.

    Distance = 1 - similarity.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine distance between 0 and 2.
    """
    return 1.0 - cosine_similarity(vec1, vec2)


def find_top_k_similar(
    query_embedding: List[float],
    candidate_embeddings: List[List[float]],
    k: int = 10,
) -> List[Tuple[int, float]]:
    """
    Find top-K most similar candidates to query.

    Args:
        query_embedding: Query vector.
        candidate_embeddings: List of candidate vectors.
        k: Number of top results to return.

    Returns:
        List of (index, similarity_score) tuples for top-K results,
        sorted by similarity in descending order.

    Examples:
        >>> query = [1.0, 0.0]
        >>> candidates = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        >>> find_top_k_similar(query, candidates, k=2)
        [(0, 1.0), (2, 0.707...)]
    """
    if not candidate_embeddings:
        return []

    similarities = []
    for idx, candidate_emb in enumerate(candidate_embeddings):
        sim = cosine_similarity(query_embedding, candidate_emb)
        similarities.append((idx, sim))

    # Sort by similarity descending
    similarities.sort(key=lambda x: x[1], reverse=True)

    # Return top-K
    return similarities[:k]

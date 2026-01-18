"""
Embedding service client for Ollama-compatible API.

Provides synchronous interface for generating text embeddings using
Ollama's embedding API. Supports batch processing for efficiency.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from daily_paper.config import EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    Client for Ollama embedding service.

    Generates text embeddings using the configured Ollama model.
    Supports batch processing for efficiency.

    Typical usage:
        >>> config = EmbeddingConfig.from_env()
        >>> client = EmbeddingClient(config)
        >>> embeddings = client.get_embeddings(["text1", "text2"])
        >>> print(len(embeddings[0]))  # Vector dimension

    Attributes:
        config: Embedding service configuration.
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        """
        Initialize the embedding client.

        Args:
            config: Embedding configuration. If None, loads from environment.
        """
        self.config = config or EmbeddingConfig.from_env()
        logger.info(
            f"Initialized embedding client: {self.config.api_url} "
            f"with model {self.config.model}"
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).

        Raises:
            requests.RequestException: If the API request fails.
            ValueError: If response format is invalid.

        Examples:
            >>> client = EmbeddingClient()
            >>> embeddings = client.get_embeddings(["Hello world", "Test"])
            >>> len(embeddings)
            2
        """
        if not texts:
            return []

        # Process in batches to avoid overwhelming the service
        all_embeddings = []
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i : i + self.config.batch_size]
            batch_embeddings = self._get_batch_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Convenience method for single text embedding.

        Args:
            text: Text string to embed.

        Returns:
            Embedding vector (list of floats).
        """
        embeddings = self.get_embeddings([text])
        return embeddings[0] if embeddings else []

    def _get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for a batch of texts.

        Internal method that makes the actual API call.

        Args:
            texts: Batch of text strings.

        Returns:
            List of embedding vectors.

        Raises:
            requests.RequestException: If API request fails.
            ValueError: If response format is invalid.
        """
        payload = {
            "model": self.config.model,
            "input": texts,
        }

        try:
            logger.debug(f"Requesting embeddings for {len(texts)} texts")
            response = requests.post(
                self.config.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.config.timeout,
            )
            response.raise_for_status()

            data = response.json()
            embeddings = data.get("embeddings")

            if not isinstance(embeddings, list):
                raise ValueError("Invalid response format from embedding API")

            if len(embeddings) != len(texts):
                raise ValueError(
                    f"Expected {len(texts)} embeddings, got {len(embeddings)}"
                )

            logger.debug(f"Received {len(embeddings)} embeddings")
            return embeddings

        except requests.RequestException as e:
            logger.error(f"Embedding API request failed: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid embedding response: {e}")
            raise ValueError(f"Invalid response format: {e}")

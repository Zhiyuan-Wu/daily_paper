"""
Embedding service client for Ollama-compatible API.

This module provides a client for generating text embeddings using
Ollama's embedding API. Supports batch processing for efficiency.
"""

from daily_paper.embeddings.client import EmbeddingClient

__all__ = ["EmbeddingClient"]

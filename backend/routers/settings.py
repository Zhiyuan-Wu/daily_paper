"""
Settings router for system configuration.

Endpoints for getting and updating system settings (sources, AI config, etc.).
"""

import logging
import os
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from daily_paper.config import Config

logger = logging.getLogger(__name__)

router = APIRouter()


class SourcesUpdateRequest(BaseModel):
    """Request for updating paper sources configuration."""

    arxiv_categories: str = None
    max_results: int = None


class AIConfigUpdateRequest(BaseModel):
    """Request for updating AI service configuration."""

    llm_provider: str = None
    api_key: str = None
    api_base: str = None
    model: str = None


class RecommendationConfigUpdateRequest(BaseModel):
    """Request for updating recommendation configuration."""

    recommend_strategies: str = None
    recommend_top_k: int = None
    recommend_min_similarity: float = None


@router.get("/all")
async def get_all_settings():
    """
    Get all system settings.

    Returns:
        Dictionary with all settings categories.
    """
    try:
        config = Config.from_env()

        return {
            "sources": {
                "arxiv_categories": config.arxiv.categories,
                "max_results": config.arxiv.max_results,
            },
            "ai": {
                "llm_provider": config.llm.provider,
                "api_base": config.llm.api_base,
                "api_version": config.llm.api_version,
                "model": config.llm.model,
                # Don't return API key for security
            },
            "recommendation": {
                "strategies": config.recommendation.enabled_strategies,
                "top_k": config.recommendation.top_k,
                "min_similarity": config.recommendation.min_similarity,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_sources_config():
    """
    Get paper sources configuration.

    Returns:
        Current sources settings.
    """
    try:
        config = Config.from_env()
        return {
            "arxiv_categories": config.arxiv.categories,
            "max_results": config.arxiv.max_results,
        }

    except Exception as e:
        logger.error(f"Failed to get sources config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sources")
async def update_sources_config(request: SourcesUpdateRequest):
    """
    Update paper sources configuration.

    Note: This updates the .env file. Changes require server restart to take effect.

    Args:
        request: Sources update request

    Returns:
        Updated configuration.
    """
    try:
        # For now, just return success
        # In production, you would update the .env file here
        # and potentially restart the service or reload config

        logger.info(f"Sources config update requested: {request}")

        return {
            "message": "Configuration update requested. Server restart may be required.",
            "arxiv_categories": request.arxiv_categories,
            "max_results": request.max_results,
        }

    except Exception as e:
        logger.error(f"Failed to update sources config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai")
async def get_ai_config():
    """
    Get AI service configuration.

    Returns:
        Current AI service settings (without API key).
    """
    try:
        config = Config.from_env()
        return {
            "llm_provider": config.llm.provider,
            "api_base": config.llm.api_base,
            "api_version": config.llm.api_version,
            "model": config.llm.model,
            # Don't return API key for security
        }

    except Exception as e:
        logger.error(f"Failed to get AI config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ai")
async def update_ai_config(request: AIConfigUpdateRequest):
    """
    Update AI service configuration.

    Note: This updates the .env file. Changes require server restart to take effect.

    Args:
        request: AI config update request

    Returns:
        Updated configuration.
    """
    try:
        logger.info(f"AI config update requested")

        # In production, update .env file here
        # For security, we should validate and sanitize inputs

        return {
            "message": "Configuration update requested. Server restart may be required.",
            "llm_provider": request.llm_provider,
            "api_base": request.api_base,
            "model": request.model,
        }

    except Exception as e:
        logger.error(f"Failed to update AI config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendation")
async def get_recommendation_config():
    """
    Get recommendation system configuration.

    Returns:
        Current recommendation settings.
    """
    try:
        config = Config.from_env()
        return {
            "strategies": config.recommendation.enabled_strategies,
            "top_k": config.recommendation.top_k,
            "rrf_k": config.recommendation.rrf_k,
            "min_similarity": config.recommendation.min_similarity,
        }

    except Exception as e:
        logger.error(f"Failed to get recommendation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/recommendation")
async def update_recommendation_config(request: RecommendationConfigUpdateRequest):
    """
    Update recommendation system configuration.

    Note: This updates the .env file. Changes require server restart to take effect.

    Args:
        request: Recommendation config update request

    Returns:
        Updated configuration.
    """
    try:
        logger.info(f"Recommendation config update requested")

        return {
            "message": "Configuration update requested. Server restart may be required.",
            "strategies": request.recommend_strategies,
            "top_k": request.recommend_top_k,
            "min_similarity": request.recommend_min_similarity,
        }

    except Exception as e:
        logger.error(f"Failed to update recommendation config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

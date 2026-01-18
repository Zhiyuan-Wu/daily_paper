"""
Downloaders module for fetching papers from multiple sources.

This module provides a plugin-based architecture for downloading papers
from different sources. Each downloader implements the BaseDownloader
interface.
"""

from daily_paper.downloaders.base import (
    BaseDownloader,
    PaperMetadata,
)
from daily_paper.downloaders.arxiv_downloader import ArxivDownloader
from daily_paper.downloaders.huggingface_downloader import HuggingFaceDownloader

__all__ = [
    "BaseDownloader",
    "PaperMetadata",
    "ArxivDownloader",
    "HuggingFaceDownloader",
]

"""
Configuration management for the Daily Paper system.

This module provides centralized configuration management using environment
variables and python-dotenv. It supports multiple LLM providers (OpenAI,
Azure OpenAI) and configurable arXiv categories.

Environment variables are loaded from .env file or system environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass
class LLMConfig:
    """
    Configuration for LLM provider.

    Supports both OpenAI and Azure OpenAI providers with configurable
    API keys, endpoints, and model/deployment settings.

    Attributes:
        provider: The LLM provider to use ('openai' or 'azure').
        api_key: The API key for authentication.
        model: Model name (for OpenAI) or deployment name (for Azure).
        api_base: Base URL for API requests.
        api_version: API version (Azure only).
    """

    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4"
    api_base: str = "https://api.openai.com/v1"
    api_version: str = "2024-02-01"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """
        Create LLMConfig from environment variables.

        Returns:
            A configured LLMConfig instance.

        Examples:
            >>> config = LLMConfig.from_env()
            >>> config.provider
            'openai'
        """
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

        if provider == "azure":
            return cls(
                provider=provider,
                api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
                api_base=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            )
        else:
            return cls(
                provider=provider,
                api_key=os.getenv("OPENAI_API_KEY", ""),
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
            )


@dataclass
class ArxivConfig:
    """
    Configuration for arXiv paper fetching.

    Attributes:
        categories: List of arXiv categories to fetch (e.g., ['cs.AI', 'cs.LG']).
        max_results: Maximum number of papers to fetch per query.
    """

    categories: List[str] = field(default_factory=lambda: ["cs.AI", "cs.LG"])
    max_results: int = 30

    @classmethod
    def from_env(cls) -> "ArxivConfig":
        """
        Create ArxivConfig from environment variables.

        Returns:
            A configured ArxivConfig instance.
        """
        categories_str = os.getenv("ARXIV_CATEGORIES", "cs.AI,cs.LG")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()]

        return cls(
            categories=categories,
            max_results=int(os.getenv("ARXIV_MAX_RESULTS", "30")),
        )


    def build_query(self) -> str:
        """
        Build arXiv search query from configured categories.

        Returns:
            A query string for arXiv API (e.g., 'cat:cs.AI OR cat:cs.LG').

        Examples:
            >>> config = ArxivConfig(categories=['cs.AI', 'cs.LG'])
            >>> config.build_query()
            'cat:cs.AI OR cat:cs.LG'
        """
        return " OR ".join(f"cat:{cat}" for cat in self.categories)


@dataclass
class OCRConfig:
    """
    Configuration for OCR service.

    The OCR service is used as a fallback when PyMuPDF text extraction
    fails or produces insufficient content.

    The OCR service is an MLX VLM server that supports raw mode.

    Attributes:
        service_url: URL of the OCR service endpoint (e.g., 'http://192.168.31.101:8000/generate').
        model: Path or name of the VLM model to use.
    """

    service_url: str = "http://localhost:5000/ocr"
    model: str = "/Users/imac/dev/DeepSeek-OCR-8bit"

    @classmethod
    def from_env(cls) -> "OCRConfig":
        """
        Create OCRConfig from environment variables.

        Returns:
            A configured OCRConfig instance.
        """
        return cls(
            service_url=os.getenv("OCR_SERVICE_URL", "http://localhost:5000/ocr"),
            model=os.getenv("OCR_MODEL", "/Users/imac/dev/DeepSeek-OCR-8bit"),
        )


@dataclass
class DatabaseConfig:
    """
    Configuration for database connection.

    Attributes:
        url: Database connection URL (SQLAlchemy format).
    """

    url: str = "sqlite:///data/papers.db"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Create DatabaseConfig from environment variables.

        Returns:
            A configured DatabaseConfig instance.
        """
        return cls(url=os.getenv("DATABASE_URL", "sqlite:///data/papers.db"))


@dataclass
class PathConfig:
    """
    Configuration for file storage paths.

    Attributes:
        download_dir: Directory for storing downloaded PDFs.
        text_dir: Directory for storing extracted text files.
    """

    download_dir: Path = field(default_factory=lambda: Path("data/papers"))
    text_dir: Path = field(default_factory=lambda: Path("data/text"))

    @classmethod
    def from_env(cls) -> "PathConfig":
        """
        Create PathConfig from environment variables.

        Creates directories if they don't exist.

        Returns:
            A configured PathConfig instance.
        """
        download_dir = Path(os.getenv("PAPERS_DOWNLOAD_DIR", "data/papers"))
        text_dir = Path(os.getenv("TEXT_EXTRACT_DIR", "data/text"))

        # Create directories if they don't exist
        download_dir.mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            download_dir=download_dir,
            text_dir=text_dir,
        )


@dataclass
class EmbeddingConfig:
    """
    Configuration for embedding service (Ollama).

    Uses Ollama-compatible API for generating text embeddings.
    The embedding service is used for semantic similarity calculations
    in the recommendation system.

    Attributes:
        api_url: URL of the embedding service endpoint.
        model: Embedding model name.
        batch_size: Number of texts to embed in one request.
        timeout: Request timeout in seconds.
    """

    api_url: str = "http://192.168.31.65:11434/api/embed"
    model: str = "qwen3-embedding:0.6b"
    batch_size: int = 32
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """
        Create EmbeddingConfig from environment variables.

        Returns:
            A configured EmbeddingConfig instance.
        """
        return cls(
            api_url=os.getenv("EMBEDDING_API_URL", "http://192.168.31.65:11434/api/embed"),
            model=os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            timeout=int(os.getenv("EMBEDDING_TIMEOUT", "30")),
        )


@dataclass
class RecommendationConfig:
    """
    Configuration for recommendation system.

    Controls behavior of the recommendation engine including
    which strategies to enable, how many papers to recommend,
    and parameters for filtering and ranking.

    Attributes:
        enabled_strategies: List of strategy names to enable (A-G).
        top_k: Number of papers to recommend.
        rrf_k: Reciprocal Rank Fusion constant (default 60).
        interested_days: Days to look back for interested papers.
        min_similarity: Minimum cosine similarity threshold.
        downweight_factor: Factor to downweight repeated recommendations.
        max_recommendations: Max times to recommend same paper.
        theme_refresh_days: Regenerate LLM themes every N days.
        theme_refresh_papers: Or after N new interested papers.
        optimizer_split_date: Date split for performance evaluation.
        optimizer_metric: Metric to optimize (mrr, hit_rate, mean_rank).
        optimizer_max_iterations: Max iterations for coordinate descent.
    """

    enabled_strategies: List[str] = field(
        default_factory=lambda: ["keyword_semantic", "interested_semantic", "fusion"]
    )
    top_k: int = 10
    rrf_k: int = 60
    interested_days: int = 30
    min_similarity: float = 0.5
    downweight_factor: float = 0.5
    max_recommendations: int = 3
    theme_refresh_days: int = 30
    theme_refresh_papers: int = 20
    optimizer_split_date: str = ""
    optimizer_metric: str = "mrr"
    optimizer_max_iterations: int = 10

    @classmethod
    def from_env(cls) -> "RecommendationConfig":
        """
        Create RecommendationConfig from environment variables.

        Returns:
            A configured RecommendationConfig instance.
        """
        strategies_str = os.getenv("RECOMMEND_STRATEGIES", "keyword_semantic,interested_semantic,fusion")
        strategies = [s.strip() for s in strategies_str.split(",") if s.strip()]

        return cls(
            enabled_strategies=strategies,
            top_k=int(os.getenv("RECOMMEND_TOP_K", "10")),
            rrf_k=int(os.getenv("RECOMMEND_RRF_K", "60")),
            interested_days=int(os.getenv("RECOMMEND_INTERESTED_DAYS", "30")),
            min_similarity=float(os.getenv("RECOMMEND_MIN_SIMILARITY", "0.5")),
            downweight_factor=float(os.getenv("RECOMMEND_DOWNWEIGHT_FACTOR", "0.5")),
            max_recommendations=int(os.getenv("RECOMMEND_MAX_RECOMMENDATIONS", "3")),
            theme_refresh_days=int(os.getenv("RECOMMEND_THEME_REFRESH_DAYS", "30")),
            theme_refresh_papers=int(os.getenv("RECOMMEND_THEME_REFRESH_PAPERS", "20")),
            optimizer_split_date=os.getenv("RECOMMEND_OPTIMIZER_SPLIT_DATE", ""),
            optimizer_metric=os.getenv("RECOMMEND_OPTIMIZER_METRIC", "mrr"),
            optimizer_max_iterations=int(os.getenv("RECOMMEND_OPTIMIZER_MAX_ITERATIONS", "10")),
        )


@dataclass
class LogConfig:
    """
    Configuration for application logging.

    Controls logging behavior including log level, output format,
    and file rotation settings.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files.
        log_file: Name of the log file.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of backup log files to keep.
        format_string: Log message format string.
        date_format: Date format for log timestamps.
        console_output: Whether to also output logs to console.
    """

    level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path("data/logs"))
    log_file: str = "daily_paper.log"
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    console_output: bool = True

    @classmethod
    def from_env(cls) -> "LogConfig":
        """
        Create LogConfig from environment variables.

        Creates log directory if it doesn't exist.

        Returns:
            A configured LogConfig instance.
        """
        log_dir = Path(os.getenv("LOG_DIR", "data/logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_dir=log_dir,
            log_file=os.getenv("LOG_FILE", "daily_paper.log"),
            max_bytes=int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))),  # 10 MB
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            format_string=os.getenv(
                "LOG_FORMAT",
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            date_format=os.getenv("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"),
            console_output=os.getenv("LOG_CONSOLE_OUTPUT", "true").lower() == "true",
        )


@dataclass
class ReportConfig:
    """
    Configuration for daily report generation.

    Controls manual report generation including how many papers
    to include and LLM parameters for highlight generation.

    Attributes:
        max_papers: Maximum number of papers in report.
        highlight_model: LLM model for generating highlights (uses LLM model if empty).
        temperature: Temperature for highlight generation.
        max_highlights: Maximum number of highlight points.
    """

    max_papers: int = 10
    highlight_model: str = ""
    temperature: float = 0.7
    max_highlights: int = 5

    @classmethod
    def from_env(cls) -> "ReportConfig":
        """
        Create ReportConfig from environment variables.

        Returns:
            A configured ReportConfig instance.
        """
        return cls(
            max_papers=int(os.getenv("REPORT_MAX_PAPERS", "10")),
            highlight_model=os.getenv("REPORT_HIGHLIGHT_MODEL", ""),
            temperature=float(os.getenv("REPORT_TEMPERATURE", "0.7")),
            max_highlights=int(os.getenv("REPORT_MAX_HIGHLIGHTS", "5")),
        )


@dataclass
class Config:
    """
    Main configuration container for the Daily Paper system.

    This class aggregates all sub-configurations into a single convenient
    interface. It's typically created once at application startup using
    the from_env() class method.

    Attributes:
        llm: LLM provider configuration.
        arxiv: arXiv fetcher configuration.
        ocr: OCR service configuration.
        database: Database connection configuration.
        paths: File storage path configuration.
        embedding: Embedding service configuration.
        recommendation: Recommendation system configuration.
        report: Daily report generation configuration.
        log: Logging configuration.
    """

    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    arxiv: ArxivConfig = field(default_factory=ArxivConfig.from_env)
    ocr: OCRConfig = field(default_factory=OCRConfig.from_env)
    database: DatabaseConfig = field(default_factory=DatabaseConfig.from_env)
    paths: PathConfig = field(default_factory=PathConfig.from_env)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig.from_env)
    recommendation: RecommendationConfig = field(default_factory=RecommendationConfig.from_env)
    report: ReportConfig = field(default_factory=ReportConfig.from_env)
    log: LogConfig = field(default_factory=LogConfig.from_env)

    @classmethod
    def from_env(cls) -> "Config":
        """
        Create Config from environment variables.

        This is the recommended way to create a Config instance. It reads
        all configuration from environment variables and .env file.

        Returns:
            A fully configured Config instance.

        Examples:
            >>> config = Config.from_env()
            >>> config.llm.provider
            'openai'
        """
        return cls(
            llm=LLMConfig.from_env(),
            arxiv=ArxivConfig.from_env(),
            ocr=OCRConfig.from_env(),
            database=DatabaseConfig.from_env(),
            paths=PathConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            recommendation=RecommendationConfig.from_env(),
            report=ReportConfig.from_env(),
            log=LogConfig.from_env(),
        )

"""
Logging configuration for the Daily Paper system.

This module provides centralized logging configuration using Python's logging
module. It sets up file and console handlers with automatic log rotation.

Usage:
    >>> from daily_paper.config import Config
    >>> from daily_paper.logging_config import setup_logging
    >>> config = Config.from_env()
    >>> setup_logging(config.log)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from daily_paper.config import LogConfig


def setup_logging(
    log_config: Optional[LogConfig] = None,
    log_level_override: Optional[str] = None,
) -> None:
    """
    Configure logging for the entire application.

    This function should be called once at application startup (typically
    in main.py or __init__.py). It configures the root logger with:
    - File handler with rotation
    - Console handler (optional)
    - Consistent formatting

    Args:
        log_config: LogConfig instance. If None, loads from environment.
        log_level_override: Optional log level override (e.g., 'DEBUG').

    Example:
        >>> from daily_paper.config import Config
        >>> from daily_paper.logging_config import setup_logging
        >>> config = Config.from_env()
        >>> setup_logging(config.log)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    if log_config is None:
        log_config = LogConfig.from_env()

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt=log_config.format_string,
        datefmt=log_config.date_format,
    )

    # Setup file handler with rotation
    log_path = log_config.log_dir / log_config.log_file
    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=log_config.max_bytes,
        backupCount=log_config.backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Setup console handler (optional)
    if log_config.console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_config.level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Log configuration info
    logging.info(f"Logging configured: level={log_config.level}, file={log_path}")
    logging.info(f"Log rotation: maxBytes={log_config.max_bytes}, backupCount={log_config.backup_count}")
    logging.info(f"Console output: {log_config.console_output}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    This is a convenience wrapper around logging.getLogger() that ensures
    the logging system has been configured.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A logger instance.

    Example:
        >>> from daily_paper.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Message")
    """
    return logging.getLogger(name)


class ContextualLogger:
    """
    A context manager for temporary log level changes.

    Useful for debugging specific sections of code without
    changing the global log level.

    Example:
        >>> with ContextualLogger('daily_paper.parsers', level='DEBUG'):
        ...     # Debug logging enabled for parsers module
        ...     parse_pdf()
        >>> # Log level restored to original
    """

    def __init__(self, logger_name: str, level: str = 'DEBUG'):
        """
        Initialize the contextual logger.

        Args:
            logger_name: Name of the logger to modify.
            level: Temporary log level.
        """
        self.logger_name = logger_name
        self.level = level
        self.original_level: Optional[int] = None

    def __enter__(self):
        """Set the temporary log level."""
        logger = logging.getLogger(self.logger_name)
        self.original_level = logger.level
        logger.setLevel(getattr(logging, self.level.upper(), logging.DEBUG))
        return logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore the original log level."""
        if self.original_level is not None:
            logger = logging.getLogger(self.logger_name)
            logger.setLevel(self.original_level)
        return False

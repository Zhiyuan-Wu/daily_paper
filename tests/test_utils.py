"""
Test utilities for database isolation and test mode guards.

This module provides utilities to ensure tests use isolated databases
and prevent accidental access to production databases during testing.
"""

import os
from typing import Optional


# Test mode flag
_TEST_MODE_ENABLED = False


def enable_test_mode():
    """
    Enable test mode globally.

    This should be called from test fixtures to ensure all database
    operations use test-specific databases.
    """
    global _TEST_MODE_ENABLED
    _TEST_MODE_ENABLED = True


def disable_test_mode():
    """Disable test mode (mainly for cleanup)."""
    global _TEST_MODE_ENABLED
    _TEST_MODE_ENABLED = False


def is_test_mode() -> bool:
    """Check if test mode is currently enabled."""
    return _TEST_MODE_ENABLED


def get_test_db_url() -> str:
    """
    Get the test database URL.

    Returns:
        In-memory SQLite URL for testing
    """
    return "sqlite:///:memory:"


def assert_test_db_url(db_url: str, context: Optional[str] = None):
    """
    Assert that a database URL is a test database URL.

    Args:
        db_url: The database URL to check
        context: Optional context string for error messages

    Raises:
        AssertionError: If db_url is not a test database URL
    """
    context_msg = f" ({context})" if context else ""

    # Check if this is a test database URL
    is_test_db = (
        db_url.startswith("sqlite:///:memory:") or
        ":memory:" in db_url or
        "test_" in db_url or
        db_url.endswith(".test.db")
    )

    # Check if this is a known production database URL
    is_production_db = (
        "sqlite:///data/papers.db" in db_url or
        "postgresql:" in db_url or
        "mysql:" in db_url
    )

    if is_production_db and not is_test_db:
        raise AssertionError(
            f"Production database URL detected during test mode{context_msg}: {db_url}\n"
            f"Tests should use in-memory SQLite or test-specific databases.\n"
            f"Expected: {get_test_db_url()}"
        )


def validate_test_environment():
    """
    Validate that the current environment is suitable for testing.

    Raises:
        AssertionError: If environment conditions are not suitable for testing
    """
    # Check if running in test mode
    if not is_test_mode():
        raise AssertionError(
            "validate_test_environment() called outside test mode. "
            "This function should only be called from within test fixtures."
        )

    # Check environment variables that might indicate production
    if os.getenv("PRODUCTION") == "true":
        raise AssertionError(
            "PRODUCTION environment variable is set to 'true' during testing"
        )


def setup_test_env():
    """
    Setup test environment variables.

    This ensures that even if Config.from_env() is called directly,
    it will use test database URLs and load test-specific configuration.
    """
    os.environ["DATABASE_URL"] = get_test_db_url()

    # Load .env.test file if it exists
    from pathlib import Path
    env_test_path = Path(__file__).parent.parent / ".env.test"
    if env_test_path.exists():
        with open(env_test_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

    # Ensure we're not in production mode
    if "PRODUCTION" in os.environ:
        del os.environ["PRODUCTION"]


def cleanup_test_env():
    """
    Cleanup test environment variables.

    Removes test-specific environment variables after testing.
    """
    test_vars = ["DATABASE_URL", "PRODUCTION"]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]

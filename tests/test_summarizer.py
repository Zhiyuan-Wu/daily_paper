"""
Unit tests for LLM summarizer modules.

Tests the LLMClient and PaperSummarizer with mocked API responses.
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock

from daily_paper.summarizers.llm_client import LLMClient, LLMMessage, LLMConfig
from daily_paper.summarizers.workflow import (
    PaperSummarizer,
    SummaryStep,
    SummaryResult,
)


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""

    def test_system_message(self):
        """Test creating system message."""
        msg = LLMMessage.system("You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_user_message(self):
        """Test creating user message."""
        msg = LLMMessage.user("Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_assistant_message(self):
        """Test creating assistant message."""
        msg = LLMMessage.assistant("Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        msg = LLMMessage.user("Test message")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Test message"}


class TestLLMClient:
    """Tests for LLMClient."""

    @patch("daily_paper.summarizers.llm_client.OpenAI")
    def test_init_openai(self, mock_openai):
        """Test initialization with OpenAI provider."""
        config = LLMConfig(
            provider="openai",
            api_key="test-key",
            model="gpt-4",
        )

        client = LLMClient(config)

        assert client.provider == "openai"
        assert client.model == "gpt-4"
        mock_openai.assert_called_once()

    @patch("daily_paper.summarizers.llm_client.AzureOpenAI")
    def test_init_azure(self, mock_azure):
        """Test initialization with Azure provider."""
        config = LLMConfig(
            provider="azure",
            api_key="test-key",
            api_base="https://test.openai.azure.com",
            api_version="2024-02-01",
            model="gpt-4",
        )

        client = LLMClient(config)

        assert client.provider == "azure"
        mock_azure.assert_called_once()

    def test_init_invalid_provider(self):
        """Test initialization with invalid provider."""
        config = LLMConfig(provider="invalid", api_key="test")

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMClient(config)

    @patch("daily_paper.summarizers.llm_client.OpenAI")
    def test_chat_with_system(self, mock_openai_class):
        """Test chat_with_system convenience method."""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.usage = None

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = LLMConfig(provider="openai", api_key="test")
        client = LLMClient(config)

        response = client.chat_with_system(
            system_prompt="You are helpful.",
            user_prompt="Explain AI.",
        )

        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once()


class TestSummaryStep:
    """Tests for SummaryStep enum."""

    def test_display_names(self):
        """Test display names for all steps."""
        assert SummaryStep.BASIC_INFO.display_name == "基本信息"
        assert SummaryStep.METHODS.display_name == "技术方法"
        assert SummaryStep.CONCLUSIONS.display_name == "结论与启示"

    def test_prompts_exist(self):
        """Test that all steps have prompts."""
        for step in SummaryStep:
            assert step.prompt
            assert len(step.prompt) > 0


class TestSummaryResult:
    """Tests for SummaryResult dataclass."""

    def test_to_dict_success(self):
        """Test conversion to dictionary for successful result."""
        result = SummaryResult(
            step=SummaryStep.METHODS,
            content="The method uses transformers.",
            success=True,
        )

        data = result.to_dict()

        assert data["step"] == "methods"
        assert data["step_name"] == "技术方法"
        assert data["content"] == "The method uses transformers."
        assert data["success"] is True

    def test_to_dict_failure(self):
        """Test conversion to dictionary for failed result."""
        result = SummaryResult(
            step=SummaryStep.METHODS,
            content="",
            success=False,
            error_message="API error",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error_message"] == "API error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

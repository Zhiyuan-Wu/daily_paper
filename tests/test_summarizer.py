"""
Unit and integration tests for LLM summarizer modules.

Tests the LLMClient and PaperSummarizer with both mocked API responses
and real API calls using actual paper data from the database.
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from daily_paper.summarizers.llm_client import LLMClient, LLMMessage, LLMConfig
from daily_paper.summarizers.workflow import (
    PaperSummarizer,
    SummaryStep,
    SummaryResult,
)
from daily_paper.database import init_db, Paper, Summary
from daily_paper.config import Config


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
    """Tests for SummaryStep enum - 3-step workflow."""

    def test_3_step_workflow_exists(self):
        """Test that the new 3-step workflow steps exist."""
        assert hasattr(SummaryStep, "CONTENT_SUMMARY")
        assert hasattr(SummaryStep, "DEEP_RESEARCH")
        assert hasattr(SummaryStep, "TLDR")

    def test_display_names_3_step(self):
        """Test display names for 3-step workflow."""
        assert SummaryStep.CONTENT_SUMMARY.display_name == "内容摘要"
        assert SummaryStep.DEEP_RESEARCH.display_name == "深度研究"
        assert SummaryStep.TLDR.display_name == "TLDR总结"

    def test_prompts_exist_3_step(self):
        """Test that all 3-step workflow prompts exist."""
        for step in [SummaryStep.CONTENT_SUMMARY, SummaryStep.DEEP_RESEARCH, SummaryStep.TLDR]:
            assert step.prompt
            assert len(step.prompt) > 100  # Prompts should be substantial

    def test_legacy_steps_removed(self):
        """Test that legacy 7-step workflow steps are removed."""
        # These should NOT exist anymore
        assert not hasattr(SummaryStep, "BASIC_INFO")
        assert not hasattr(SummaryStep, "BACKGROUND")
        assert not hasattr(SummaryStep, "CONTRIBUTIONS")
        assert not hasattr(SummaryStep, "PROBLEM")
        assert not hasattr(SummaryStep, "METHODS")
        assert not hasattr(SummaryStep, "RESULTS")
        assert not hasattr(SummaryStep, "CONCLUSIONS")


class TestSummaryResult:
    """Tests for SummaryResult dataclass."""

    def test_to_dict_success(self):
        """Test conversion to dictionary for successful result."""
        result = SummaryResult(
            step=SummaryStep.CONTENT_SUMMARY,
            content="This paper presents a novel approach to...",
            success=True,
        )

        data = result.to_dict()

        assert data["step"] == "content_summary"
        assert data["step_name"] == "内容摘要"
        assert data["content"] == "This paper presents a novel approach to..."
        assert data["success"] is True

    def test_to_dict_failure(self):
        """Test conversion to dictionary for failed result."""
        result = SummaryResult(
            step=SummaryStep.DEEP_RESEARCH,
            content="",
            success=False,
            error_message="API error",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error_message"] == "API error"


@pytest.mark.integration
@pytest.mark.slow
class TestPaperSummarizerIntegration:
    """
    Integration tests for PaperSummarizer with real LLM API and database papers.

    These tests require:
    - Valid LLM API credentials in environment
    - At least one paper with PDF in the database
    - Real API calls to OpenAI/Azure OpenAI
    """

    @pytest.fixture(autouse=True)
    def setup_test_env(self, setup_test_env):
        """Setup test environment before each test."""
        pass

    def test_real_summarization_workflow(self):
        """Test complete 3-step summarization workflow with real API and paper data."""
        config = Config.from_env()
        session = init_db(config.database.url)

        # Find a paper with PDF or text
        paper = (
            session.query(Paper)
            .filter(
                (Paper.pdf_path != None) | (Paper.text_path != None)
            )
            .first()
        )

        if not paper:
            pytest.skip("No papers with PDF or text found in database")

        # Create summarizer
        summarizer = PaperSummarizer(config)

        # Run the 3-step workflow
        results = summarizer.summarize_paper(paper, save_to_db=False)

        # Verify results
        assert len(results) == 3, "Should have 3 summary results"

        # Check CONTENT_SUMMARY
        content_result = next(r for r in results if r.step == SummaryStep.CONTENT_SUMMARY)
        assert content_result.success
        assert len(content_result.content) > 200  # Should be substantial

        # Check DEEP_RESEARCH
        deep_result = next(r for r in results if r.step == SummaryStep.DEEP_RESEARCH)
        assert deep_result.success
        assert len(deep_result.content) > 200

        # Check TLDR
        tldr_result = next(r for r in results if r.step == SummaryStep.TLDR)
        assert tldr_result.success
        assert 50 < len(tldr_result.content) < 500  # TLDR should be concise

        # Verify TLDR is actually a single paragraph
        assert "\n\n" not in tldr_result.content.strip()

        # Verify summaries were saved to database
        session.rollback()  # Clear any pending changes
        summaries = (
            session.query(Summary)
            .filter_by(paper_id=paper.id)
            .all()
        )

        # Should have summaries for all 3 steps
        summary_types = {s.summary_type for s in summaries}
        assert "content_summary" in summary_types
        assert "deep_research" in summary_types
        assert "tldr" in summary_types

        # Clean up test summaries
        for summary in summaries:
            session.delete(summary)
        session.commit()

        session.close()
        summarizer.close()

    def test_summarization_with_text_only(self):
        """Test summarization when only text file is available (no PDF)."""
        config = Config.from_env()
        session = init_db(config.database.url)

        # Find a paper with text but no PDF
        paper = (
            session.query(Paper)
            .filter(
                (Paper.text_path != None) &
                ((Paper.pdf_path == None) | (Paper.pdf_path == ""))
            )
            .first()
        )

        if not paper:
            pytest.skip("No papers with text-only found in database")

        summarizer = PaperSummarizer(config)
        results = summarizer.summarize_paper(paper, save_to_db=False)

        assert len(results) == 3
        assert all(r.success for r in results)

        session.close()
        summarizer.close()

    def test_prepare_paper_text(self):
        """Test paper text preparation with actual paper data."""
        config = Config.from_env()
        session = init_db(config.database.url)

        paper = (
            session.query(Paper)
            .filter(
                (Paper.pdf_path != None) | (Paper.text_path != None)
            )
            .first()
        )

        if not paper:
            pytest.skip("No papers found in database")

        summarizer = PaperSummarizer(config)

        # Prepare text
        paper_text = summarizer._prepare_paper_text(
            title=paper.title,
            abstract=paper.abstract or "",
            full_text=None,  # Test with title and abstract only
        )

        # Verify structure
        assert "Title:" in paper_text
        assert "Abstract:" in paper_text
        assert paper.title in paper_text

        session.close()
        summarizer.close()

    def test_individual_steps(self):
        """Test running individual summary steps."""
        config = Config.from_env()
        session = init_db(config.database.url)

        paper = (
            session.query(Paper)
            .filter(
                (Paper.text_path != None)
            )
            .first()
        )

        if not paper:
            pytest.skip("No papers with text found in database")

        summarizer = PaperSummarizer(config)

        # Test running only CONTENT_SUMMARY
        results = summarizer.summarize_paper(
            paper,
            steps=[SummaryStep.CONTENT_SUMMARY],
            save_to_db=False
        )

        assert len(results) == 1
        assert results[0].step == SummaryStep.CONTENT_SUMMARY
        assert results[0].success
        assert len(results[0].content) > 100

        session.close()
        summarizer.close()


class TestPaperSummarizerUnit:
    """Unit tests for PaperSummarizer without real API calls."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        config = Config.from_env()
        summarizer = PaperSummarizer(config)

        assert summarizer.config == config
        assert summarizer.max_input_length == 15000
        assert summarizer.llm_client is not None
        assert summarizer.pdf_parser is not None

        summarizer.close()

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        config = Config.from_env()

        mock_llm = Mock()
        mock_parser = Mock()

        summarizer = PaperSummarizer(
            config=config,
            llm_client=mock_llm,
            pdf_parser=mock_parser,
            max_input_length=5000,
        )

        assert summarizer.llm_client == mock_llm
        assert summarizer.pdf_parser == mock_parser
        assert summarizer.max_input_length == 5000

        summarizer.close()

    def test_context_manager(self):
        """Test using summarizer as context manager."""
        config = Config.from_env()

        with PaperSummarizer(config) as summarizer:
            assert summarizer is not None

        # Session should be closed after context exit
        # (no exception raised)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

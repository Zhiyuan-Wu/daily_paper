"""
Configurable LLM client supporting OpenAI and Azure OpenAI.

This module provides a unified interface for interacting with LLM providers.
It supports both OpenAI and Azure OpenAI, with configuration determining
which provider to use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI, OpenAI

from daily_paper.config import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """
    A message in an LLM conversation.

    Represents a single message in the chat format used by OpenAI-style APIs.

    Attributes:
        role: Message role ('system', 'user', or 'assistant').
        content: Message content text.
    """

    role: str
    content: str

    def to_dict(self) -> dict:
        """Convert message to dictionary format for API."""
        return {"role": self.role, "content": self.content}

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "LLMMessage":
        """Create an assistant message."""
        return cls(role="assistant", content=content)


class LLMClient:
    """
    Configurable LLM client supporting OpenAI and Azure OpenAI.

    Provides a unified interface for chat completions across different
    LLM providers. The provider is determined by configuration.

    Typical usage:
        >>> config = LLMConfig.from_env()
        >>> client = LLMClient(config)
        >>> messages = [
        ...     LLMMessage.system("You are a helpful assistant."),
        ...     LLMMessage.user("Explain quantum computing."),
        ... ]
        >>> response = client.chat(messages)

    Attributes:
        config: LLM configuration.
        client: OpenAI or Azure OpenAI client instance.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM client.

        Args:
            config: LLM configuration. If None, loads from environment.

        Raises:
            ValueError: If configuration is invalid or provider is unsupported.
        """
        self.config = config or LLMConfig.from_env()

        if self.config.provider == "azure":
            self.client = AzureOpenAI(
                api_key=self.config.api_key,
                azure_endpoint=self.config.api_base,
                api_version=self.config.api_version,
            )
        elif self.config.provider == "openai":
            self.client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.provider}")

        logger.info(f"Initialized LLM client with provider: {self.config.provider}")

    def chat(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Send a chat completion request to the LLM.

        Args:
            messages: List of conversation messages.
            model: Model name to use. If None, uses configured default.
            temperature: Sampling temperature (0-2). Higher = more random.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters to pass to the API.

        Returns:
            Generated response text.

        Raises:
            Exception: If the API request fails.
        """
        model = model or self.config.model

        # Convert messages to API format
        api_messages = [msg.to_dict() for msg in messages]

        # Build request parameters
        params = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if max_tokens:
            params["max_tokens"] = max_tokens

        params.update(kwargs)

        try:
            logger.debug(f"Sending chat request with {len(messages)} messages")
            response = self.client.chat.completions.create(**params)

            # Extract the generated text
            content = response.choices[0].message.content

            # Log token usage
            if hasattr(response, "usage") and response.usage:
                logger.info(
                    f"LLM request completed: "
                    f"{response.usage.prompt_tokens} prompt tokens, "
                    f"{response.usage.completion_tokens} completion tokens"
                )

            return content

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def chat_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Convenience method for system + user message pattern.

        Common pattern for most LLM interactions.

        Args:
            system_prompt: System message setting context.
            user_prompt: User message with actual request.
            model: Model name to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated response text.
        """
        messages = [
            LLMMessage.system(system_prompt),
            LLMMessage.user(user_prompt),
        ]
        return self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    @property
    def provider(self) -> str:
        """Return the LLM provider name."""
        return self.config.provider

    @property
    def model(self) -> str:
        """Return the configured model name."""
        return self.config.model

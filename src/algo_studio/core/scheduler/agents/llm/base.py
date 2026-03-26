"""
LLM Provider interface for Deep Path scheduling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class LLMResponse:
    """Response from LLM provider"""
    content: str
    stop_reason: str
    usage: Dict[str, int]  # input_tokens, output_tokens, prompt_tokens, completion_tokens
    cost_usd: float


class LLMProviderInterface(ABC):
    """
    LLM Provider interface.

    M4 implements actual LLM-based scheduling with function calling support.
    """

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate completion from prompt.

        Args:
            prompt: Input prompt
            **kwargs: Additional provider-specific options

        Returns:
            LLMResponse: LLM response
        """
        pass

    @abstractmethod
    async def messages_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion from messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional provider-specific options

        Returns:
            LLMResponse: LLM response
        """
        pass

    @abstractmethod
    async def messages_complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion with function calling (tools).

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: List of tool definitions for function calling
            **kwargs: Additional provider-specific options

        Returns:
            LLMResponse: LLM response with tool call information
        """
        pass

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost in USD.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            float: Estimated cost in USD
        """
        pass

    def get_token_limit(self) -> int:
        """
        Get the context window size for the current model.

        Returns:
            int: Maximum context tokens (default 100k)
        """
        return 100000


# Cost estimation helper
def estimate_llm_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Estimate LLM cost based on provider and model.

    Args:
        provider: Provider name (openai, anthropic)
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        float: Estimated cost in USD
    """
    # Pricing per 1M tokens (approximate, updated for 2024-2025)
    pricing = {
        "openai": {
            "gpt-4o": {"prompt": 2.50, "completion": 10.0},
            "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
            "gpt-4-turbo": {"prompt": 10.0, "completion": 30.0},
            "gpt-4": {"prompt": 30.0, "completion": 60.0},
        },
        "anthropic": {
            # Claude Sonnet 4.5 - most cost effective for scheduling
            "claude-sonnet-4-5": {"prompt": 3.0, "completion": 15.0},
            # Claude Opus 4.5 - most capable
            "claude-opus-4-5": {"prompt": 15.0, "completion": 75.0},
            # Claude Haiku 3.5 - fastest, cheapest
            "claude-haiku-3-5": {"prompt": 0.80, "completion": 4.0},
        },
    }

    provider_pricing = pricing.get(provider, {}).get(model, {"prompt": 0, "completion": 0})

    prompt_cost = (prompt_tokens / 1_000_000) * provider_pricing["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * provider_pricing["completion"]

    return prompt_cost + completion_cost


def estimate_cost_for_provider(
    provider: str,
    model: str,
    num_messages: int,
    avg_message_tokens: int = 100,
    avg_response_tokens: int = 200,
) -> float:
    """
    Estimate cost for a typical scheduling conversation.

    Args:
        provider: Provider name
        model: Model name
        num_messages: Number of messages in conversation
        avg_message_tokens: Average tokens per message
        avg_response_tokens: Average tokens in response

    Returns:
        float: Estimated cost in USD
    """
    total_prompt_tokens = num_messages * avg_message_tokens
    total_completion_tokens = avg_response_tokens

    return estimate_llm_cost(provider, model, total_prompt_tokens, total_completion_tokens)
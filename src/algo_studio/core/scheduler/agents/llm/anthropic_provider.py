"""
Anthropic Claude provider for Deep Path scheduling (M4)
"""

import os
import json
from typing import List, Dict, Any, Optional, Callable

import anthropic

from algo_studio.core.scheduler.agents.llm.base import LLMProviderInterface, LLMResponse, estimate_llm_cost


class AnthropicProvider(LLMProviderInterface):
    """
    Anthropic Claude provider for Deep Path scheduling.

    M4 implements actual API integration with Claude Sonnet 4.5.
    """

    # Supported models and their context windows
    MODEL_CONFIG = {
        "claude-sonnet-4-5": {
            "max_tokens": 8192,
            "supports_tools": True,
        },
        "claude-opus-4-5": {
            "max_tokens": 8192,
            "supports_tools": True,
        },
        "claude-haiku-3-5": {
            "max_tokens": 8192,
            "supports_tools": True,
        },
    }

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 1024,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: API key. Uses ANTHROPIC_API_KEY env var if None.
            model: Model to use (claude-sonnet-4-5, claude-opus-4-5, claude-haiku-3-5)
            max_tokens: Maximum tokens in response
            timeout_seconds: Request timeout
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable or api_key argument is required")

        self.model = model
        self.max_tokens = min(max_tokens, self.MODEL_CONFIG.get(model, {}).get("max_tokens", 1024))
        self.timeout_seconds = timeout_seconds

        # Initialize client
        self._client = None

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazy initialization of Anthropic client"""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate completion from prompt.

        Args:
            prompt: Input prompt
            **kwargs: Additional options (temperature, system, etc.)

        Returns:
            LLMResponse: LLM response
        """
        system = kwargs.get("system", "")
        temperature = kwargs.get("temperature", 1.0)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

            return self._parse_response(response)

        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                stop_reason="error",
                usage={"prompt_tokens": 0, "completion_tokens": 0},
                cost_usd=0.0,
            )

    async def messages_complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion from messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, system, tools, etc.)

        Returns:
            LLMResponse: LLM response
        """
        system = kwargs.get("system", "")
        temperature = kwargs.get("temperature", 1.0)
        tools = kwargs.get("tools", None)

        try:
            request_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            if system:
                request_params["system"] = system

            if tools:
                request_params["tools"] = tools

            response = self.client.messages.create(**request_params)

            return self._parse_response(response)

        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                stop_reason="error",
                usage={"prompt_tokens": 0, "completion_tokens": 0},
                cost_usd=0.0,
            )

    async def messages_complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: Dict[str, str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion with function calling (tools).

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: List of tool definitions for function calling
            tool_choice: Optional tool choice specification
            **kwargs: Additional options

        Returns:
            LLMResponse: LLM response with tool use information
        """
        system = kwargs.get("system", "")
        temperature = kwargs.get("temperature", 1.0)

        try:
            request_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": temperature,
                "messages": messages,
                "tools": tools,
            }

            if system:
                request_params["system"] = system

            if tool_choice:
                request_params["tool_choice"] = tool_choice

            response = self.client.messages.create(**request_params)

            return self._parse_response_with_tools(response)

        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                stop_reason="error",
                usage={"prompt_tokens": 0, "completion_tokens": 0},
                cost_usd=0.0,
            )

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        """Parse Anthropic response into LLMResponse"""
        # Extract usage information
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
        }

        # Calculate cost
        cost = estimate_llm_cost(
            "anthropic",
            self.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        # Extract content
        if hasattr(response.content, '__iter__') and not isinstance(response.content, str):
            # Handle multiple content blocks
            content_parts = []
            for block in response.content:
                if hasattr(block, 'text'):
                    content_parts.append(block.text)
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    content_parts.append(f"[tool_use: {block.name}]")
            content = "\n".join(content_parts)
        else:
            content = str(response.content)

        return LLMResponse(
            content=content,
            stop_reason=str(response.stop_reason),
            usage=usage,
            cost_usd=cost,
        )

    def _parse_response_with_tools(self, response: anthropic.types.Message) -> LLMResponse:
        """Parse Anthropic response with tool calls"""
        base_response = self._parse_response(response)

        # Check for tool calls
        tool_calls = []
        if hasattr(response.content, '__iter__'):
            for block in response.content:
                if hasattr(block, 'type') and block.type == 'tool_use':
                    tool_calls.append({
                        "name": block.name,
                        "input": block.input,
                        "id": block.id,
                    })

        # Add tool information to content
        if tool_calls:
            base_response.content = json.dumps({
                "text": base_response.content,
                "tool_calls": tool_calls,
            })

        return base_response

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost in USD.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            float: Estimated cost in USD
        """
        return estimate_llm_cost("anthropic", self.model, prompt_tokens, completion_tokens)

    def get_token_limit(self) -> int:
        """
        Get the context window size for the current model.

        Returns:
            int: Maximum context tokens
        """
        # Claude Sonnet 4.5 has 200k context
        limits = {
            "claude-sonnet-4-5": 200000,
            "claude-opus-4-5": 200000,
            "claude-haiku-3-5": 200000,
        }
        return limits.get(self.model, 100000)

    async def close(self):
        """Close provider and cleanup resources"""
        if self._client:
            self._client = None


# Singleton instance for convenience
_default_provider: Optional[AnthropicProvider] = None


def get_anthropic_provider(
    api_key: str = None,
    model: str = "claude-sonnet-4-5",
) -> AnthropicProvider:
    """
    Get or create a singleton Anthropic provider instance.

    Args:
        api_key: API key (uses env var if None)
        model: Model to use

    Returns:
        AnthropicProvider: Provider instance
    """
    global _default_provider

    if _default_provider is None:
        _default_provider = AnthropicProvider(api_key=api_key, model=model)

    return _default_provider


def reset_provider():
    """Reset the singleton provider (useful for testing)"""
    global _default_provider
    _default_provider = None
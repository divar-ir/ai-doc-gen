"""
LiteLLM-based model implementation for pydantic-ai.

This module provides a custom pydantic-ai Model that uses LiteLLM under the hood,
enabling support for 100+ LLM providers with a unified interface.

LiteLLM model format examples:
- OpenAI: "gpt-4o", "gpt-4-turbo"
- Azure OpenAI: "azure/deployment-name"
- Anthropic: "anthropic/claude-3-opus"
- AWS Bedrock: "bedrock/anthropic.claude-3-sonnet"
- Google Vertex: "vertex_ai/gemini-pro"

Environment variables for providers:
- OpenAI: OPENAI_API_KEY
- Azure: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
- Anthropic: ANTHROPIC_API_KEY
- etc.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import litellm
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelResponsePart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RequestUsage

# Suppress LiteLLM's verbose logging by default
litellm.suppress_debug_info = True


@dataclass
class LiteLLMModelSettings:
    """Additional LiteLLM-specific settings beyond standard ModelSettings."""

    api_base: str | None = None
    api_key: str | None = None
    api_version: str | None = None
    drop_params: bool = True  # LiteLLM will drop unsupported params for each provider
    num_retries: int = 5  # LiteLLM built-in retry support


@dataclass
class LiteLLMModel(Model):
    """
    A pydantic-ai Model implementation that uses LiteLLM for provider abstraction.

    This allows using any LLM provider supported by LiteLLM with pydantic-ai agents.
    The model name follows LiteLLM's naming convention (e.g., "azure/gpt-41", "gpt-4o").

    Args:
        model: The model identifier in LiteLLM format
        litellm_settings: Optional LiteLLM-specific settings (api_base, api_key, etc.)
    """

    model: str
    litellm_settings: LiteLLMModelSettings = field(default_factory=LiteLLMModelSettings)

    @property
    def model_name(self) -> str:
        """Return the model name (required abstract property)."""
        return self.model

    @property
    def system(self) -> str:
        """Return the system/provider name (required abstract property)."""
        return "litellm"

    def name(self) -> str:
        """Return the model name for logging/identification."""
        return f"litellm:{self.model}"

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[Any]:
        """Stream responses from the model (not implemented - falls back to non-streaming)."""
        # For simplicity, we don't implement streaming yet
        # This could be enhanced later if needed
        raise NotImplementedError("Streaming not implemented for LiteLLMModel")

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a request to the LLM via LiteLLM."""
        # Convert pydantic-ai messages to LiteLLM format
        litellm_messages = self._convert_messages(messages)

        # Build LiteLLM call kwargs
        kwargs = self._build_kwargs(model_settings, model_request_parameters)

        # Make the async call to LiteLLM
        response = await litellm.acompletion(
            model=self.model_name,
            messages=litellm_messages,
            **kwargs,
        )

        # Convert response back to pydantic-ai format
        return self._convert_response(response)

    def _convert_messages(self, messages: list[ModelMessage]) -> list[dict[str, Any]]:
        """Convert pydantic-ai messages to LiteLLM message format."""
        litellm_messages: list[dict[str, Any]] = []

        for message in messages:
            if isinstance(message, ModelRequest):
                # First, collect tool returns to add them right after the assistant message
                tool_returns = []
                other_parts = []

                for part in message.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_returns.append(
                            {
                                "role": "tool",
                                "tool_call_id": part.tool_call_id,
                                "content": part.content if isinstance(part.content, str) else str(part.content),
                            }
                        )
                    elif isinstance(part, SystemPromptPart):
                        other_parts.append({"role": "system", "content": part.content})
                    elif isinstance(part, UserPromptPart):
                        other_parts.append({"role": "user", "content": part.content})

                # Add tool returns first (they need to follow the previous assistant message)
                litellm_messages.extend(tool_returns)
                # Then add other parts
                litellm_messages.extend(other_parts)

            elif isinstance(message, ModelResponse):
                # Handle assistant responses (for multi-turn conversations)
                content_parts = []
                tool_calls = []

                for part in message.parts:
                    if isinstance(part, TextPart):
                        content_parts.append(part.content)
                    elif isinstance(part, ToolCallPart):
                        tool_calls.append(
                            {
                                "id": part.tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": part.tool_name,
                                    "arguments": part.args_as_json_str(),
                                },
                            }
                        )

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if content_parts:
                    assistant_msg["content"] = "".join(content_parts)
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                    if "content" not in assistant_msg:
                        assistant_msg["content"] = None

                litellm_messages.append(assistant_msg)

        return litellm_messages

        return litellm_messages

    def _build_kwargs(
        self,
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> dict[str, Any]:
        """Build kwargs for LiteLLM acompletion call."""
        kwargs: dict[str, Any] = {
            "drop_params": self.litellm_settings.drop_params,
            "num_retries": self.litellm_settings.num_retries,
        }

        # Add LiteLLM-specific settings
        if self.litellm_settings.api_base:
            kwargs["api_base"] = self.litellm_settings.api_base
        if self.litellm_settings.api_key:
            kwargs["api_key"] = self.litellm_settings.api_key
        if self.litellm_settings.api_version:
            kwargs["api_version"] = self.litellm_settings.api_version

        # Add model settings (ModelSettings is a TypedDict, so use dict access)
        if model_settings:
            if model_settings.get("temperature") is not None:
                kwargs["temperature"] = model_settings["temperature"]
            if model_settings.get("max_tokens") is not None:
                kwargs["max_tokens"] = model_settings["max_tokens"]
            if model_settings.get("timeout") is not None:
                kwargs["timeout"] = model_settings["timeout"]
            if model_settings.get("top_p") is not None:
                kwargs["top_p"] = model_settings["top_p"]

        # Add tools if provided (tool_defs is a dict of name -> ToolDefinition)
        if model_request_parameters.tool_defs:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.parameters_json_schema,
                    },
                }
                for tool in model_request_parameters.tool_defs.values()
            ]

            # Handle parallel tool calls setting
            if model_settings and model_settings.get("parallel_tool_calls") is not None:
                kwargs["parallel_tool_calls"] = model_settings["parallel_tool_calls"]

        return kwargs

    def _convert_response(self, response: Any) -> ModelResponse:
        """Convert LiteLLM response to pydantic-ai format."""
        choice = response.choices[0]
        message = choice.message

        parts: list[ModelResponsePart] = []

        # Handle text content
        if message.content:
            parts.append(TextPart(content=message.content))

        # Handle tool calls
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                parts.append(
                    ToolCallPart(
                        tool_name=tool_call.function.name,
                        args=tool_call.function.arguments,
                        tool_call_id=tool_call.id,
                    )
                )

        # Build usage info
        usage = RequestUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        model_response = ModelResponse(
            parts=parts,
            usage=usage,
            model_name=self.model_name,
            timestamp=datetime.now(timezone.utc),
        )

        return model_response

"""
Factory functions for creating LLM models.

This module provides a unified interface for creating LLM models,
supporting both the legacy pydantic-ai providers and the new LiteLLM integration.
"""

from typing import Tuple

from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from .litellm_model import LiteLLMModel, LiteLLMModelSettings


def create_llm_model(
    model_name: str,
    api_base: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 180,
    parallel_tool_calls: bool = True,
) -> Tuple[Model, ModelSettings]:
    """
    Create an LLM model using LiteLLM.

    LiteLLM automatically handles provider-specific quirks like:
    - max_tokens vs max_completion_tokens for different providers
    - Azure OpenAI URL construction
    - API version handling
    - Token counting differences

    Model name formats (LiteLLM convention):
    - OpenAI: "gpt-4o", "gpt-4-turbo", "o1-preview"
    - Azure OpenAI: "azure/<deployment-name>"
    - Anthropic: "anthropic/claude-3-opus", "claude-3-sonnet"
    - AWS Bedrock: "bedrock/anthropic.claude-3-sonnet"
    - Google Vertex: "vertex_ai/gemini-pro"
    - Ollama: "ollama/llama2"
    - Together AI: "together_ai/mistralai/Mixtral-8x7B"

    Environment variables (provider-specific):
    - OpenAI: OPENAI_API_KEY
    - Azure: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
    - Anthropic: ANTHROPIC_API_KEY
    - AWS Bedrock: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME
    - etc.

    Args:
        model_name: Model identifier in LiteLLM format
        api_base: Optional API base URL (overrides env var)
        api_key: Optional API key (overrides env var)
        api_version: Optional API version (for Azure, overrides env var)
        temperature: Sampling temperature (0.0 = deterministic)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        parallel_tool_calls: Whether to allow parallel tool calls

    Returns:
        Tuple of (Model, ModelSettings) ready for use with pydantic-ai Agent
    """
    litellm_settings = LiteLLMModelSettings(
        api_base=api_base,
        api_key=api_key,
        api_version=api_version,
        drop_params=True,  # Let LiteLLM handle provider-specific params
    )

    model = LiteLLMModel(
        model=model_name,
        litellm_settings=litellm_settings,
    )

    settings = ModelSettings(
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        parallel_tool_calls=parallel_tool_calls,
    )

    return model, settings

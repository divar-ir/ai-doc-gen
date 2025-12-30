import logging
import os
from pathlib import Path
from typing import Optional, Type, TypeVar

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from utils.dict import merge_dicts

load_dotenv()


def str_to_bool(value: str) -> bool:
    if value.lower() in ["true", "1", "yes", "y"]:
        return True
    elif value.lower() in ["false", "0", "no", "n"]:
        return False
    else:
        raise ValueError(f"Invalid boolean value: {value}")


VERSION = os.getenv("APP_VERSION", "1.2.0")

# Analyzer - Model name follows LiteLLM format (e.g., "gpt-4o", "azure/deployment-name", "anthropic/claude-3-opus")
ANALYZER_LLM_MODEL = os.environ["ANALYZER_LLM_MODEL"]
ANALYZER_LLM_BASE_URL = os.getenv("ANALYZER_LLM_BASE_URL")  # Optional: overrides provider default
ANALYZER_LLM_API_KEY = os.getenv("ANALYZER_LLM_API_KEY")  # Optional: overrides env var for provider
ANALYZER_LLM_API_VERSION = os.getenv("ANALYZER_LLM_API_VERSION")  # Optional: for Azure OpenAI
ANALYZER_PARALLEL_TOOL_CALLS = str_to_bool(os.getenv("ANALYZER_PARALLEL_TOOL_CALLS", "true"))

# Analyzer Agent Settings
ANALYZER_AGENT_RETRIES = int(os.getenv("ANALYZER_AGENT_RETRIES", "2"))
ANALYZER_LLM_TIMEOUT = int(os.getenv("ANALYZER_LLM_TIMEOUT", "180"))
ANALYZER_LLM_MAX_TOKENS = int(os.getenv("ANALYZER_LLM_MAX_TOKENS", "8192"))
ANALYZER_LLM_TEMPERATURE = float(os.getenv("ANALYZER_LLM_TEMPERATURE", "0.0"))
ANALYZER_MAX_WORKERS = int(os.getenv("ANALYZER_MAX_WORKERS", "0"))

# Documenter - Model name follows LiteLLM format
DOCUMENTER_LLM_MODEL = os.environ["DOCUMENTER_LLM_MODEL"]
DOCUMENTER_LLM_BASE_URL = os.getenv("DOCUMENTER_LLM_BASE_URL")  # Optional: overrides provider default
DOCUMENTER_LLM_API_KEY = os.getenv("DOCUMENTER_LLM_API_KEY")  # Optional: overrides env var for provider
DOCUMENTER_LLM_API_VERSION = os.getenv("DOCUMENTER_LLM_API_VERSION")  # Optional: for Azure OpenAI
DOCUMENTER_PARALLEL_TOOL_CALLS = str_to_bool(os.getenv("DOCUMENTER_PARALLEL_TOOL_CALLS", "true"))

# Documenter Agent Settings
DOCUMENTER_AGENT_RETRIES = int(os.getenv("DOCUMENTER_AGENT_RETRIES", "2"))
DOCUMENTER_LLM_TIMEOUT = int(os.getenv("DOCUMENTER_LLM_TIMEOUT", "180"))
DOCUMENTER_LLM_MAX_TOKENS = int(os.getenv("DOCUMENTER_LLM_MAX_TOKENS", "8192"))
DOCUMENTER_LLM_TEMPERATURE = float(os.getenv("DOCUMENTER_LLM_TEMPERATURE", "0.0"))

# AI Rules Generator - Model name follows LiteLLM format
AI_RULES_LLM_MODEL = os.environ.get("AI_RULES_LLM_MODEL", DOCUMENTER_LLM_MODEL)
AI_RULES_LLM_BASE_URL = os.getenv("AI_RULES_LLM_BASE_URL", DOCUMENTER_LLM_BASE_URL)
AI_RULES_LLM_API_KEY = os.getenv("AI_RULES_LLM_API_KEY", DOCUMENTER_LLM_API_KEY)
AI_RULES_LLM_API_VERSION = os.getenv("AI_RULES_LLM_API_VERSION", DOCUMENTER_LLM_API_VERSION)
AI_RULES_PARALLEL_TOOL_CALLS = str_to_bool(os.getenv("AI_RULES_PARALLEL_TOOL_CALLS", "true"))

# AI Rules Agent Settings
AI_RULES_AGENT_RETRIES = int(os.getenv("AI_RULES_AGENT_RETRIES", "2"))
AI_RULES_LLM_TIMEOUT = int(os.getenv("AI_RULES_LLM_TIMEOUT", "240"))
AI_RULES_LLM_MAX_TOKENS_MARKDOWN = int(os.getenv("AI_RULES_LLM_MAX_TOKENS_MARKDOWN", "8192"))
AI_RULES_LLM_MAX_TOKENS_CURSOR = int(os.getenv("AI_RULES_LLM_MAX_TOKENS_CURSOR", "16384"))
AI_RULES_LLM_TEMPERATURE = float(os.getenv("AI_RULES_LLM_TEMPERATURE", "0.0"))

# Langfuse
ENABLE_LANGFUSE = str_to_bool(os.getenv("ENABLE_LANGFUSE", "false"))
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

# SCM Provider Configuration (Provider-Agnostic)
# Supported values: "gitlab", "bitbucket_server"
SCM_PROVIDER = os.getenv("SCM_PROVIDER", "gitlab")
SCM_API_URL = os.getenv("SCM_API_URL", os.getenv("GITLAB_API_URL", "https://git.divar.cloud"))
SCM_GIT_USER_NAME = os.getenv("SCM_GIT_USER_NAME", os.getenv("GITLAB_USER_NAME", "AI Analyzer"))
SCM_GIT_USER_USERNAME = os.getenv("SCM_GIT_USER_USERNAME", os.getenv("GITLAB_USER_USERNAME", "agent_doc"))
SCM_GIT_USER_EMAIL = os.getenv("SCM_GIT_USER_EMAIL", os.getenv("GITLAB_USER_EMAIL"))

# GitLab-specific settings (used when SCM_PROVIDER=gitlab)
GITLAB_API_URL = os.getenv("GITLAB_API_URL", "https://git.divar.cloud")  # Deprecated: use SCM_API_URL
GITLAB_USER_NAME = os.getenv("GITLAB_USER_NAME", "AI Analyzer")  # Deprecated: use SCM_GIT_USER_NAME
GITLAB_USER_USERNAME = os.getenv("GITLAB_USER_USERNAME", "agent_doc")  # Deprecated: use SCM_GIT_USER_USERNAME
GITLAB_USER_EMAIL = os.getenv("GITLAB_USER_EMAIL")  # Deprecated: use SCM_GIT_USER_EMAIL
GITLAB_OAUTH_TOKEN = os.getenv("GITLAB_OAUTH_TOKEN")
GITLAB_PRIVATE_TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")

# Bitbucket Server-specific settings (used when SCM_PROVIDER=bitbucket_server)
# Note: This is for Bitbucket SERVER (self-hosted), not Bitbucket Cloud
BITBUCKET_URL = os.getenv("BITBUCKET_URL")  # Alternative to SCM_API_URL for Bitbucket
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")
BITBUCKET_PASSWORD = os.getenv("BITBUCKET_PASSWORD")
BITBUCKET_TOKEN = os.getenv("BITBUCKET_TOKEN")  # Personal access token (alternative to username/password)

# General
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


CONSOLE_LOG_LEVEL = getattr(logging, os.getenv("CONSOLE_LOG_LEVEL", "DEBUG").upper())
FILE_LOG_LEVEL = getattr(logging, os.getenv("FILE_LOG_LEVEL", "INFO").upper())

# Agent Tools Settings
TOOL_FILE_READER_MAX_RETRIES = int(os.getenv("TOOL_FILE_READER_MAX_RETRIES", "2"))
TOOL_LIST_FILES_MAX_RETRIES = int(os.getenv("TOOL_LIST_FILES_MAX_RETRIES", "2"))

# --------------------------
# Helper Function


def load_config_from_file(args, file_key: str = "") -> dict:
    """
    Helper function to load configuration from a YAML file.

    This is a helper function - consider using load_config() instead for full configuration loading.

    Args:
        args: Arguments object containing repo_path, config, or config_path attributes
        file_key: Optional dot-separated key path to extract nested config values (e.g., "section.subsection")

    Returns:
        dict: Configuration dictionary from file, or empty dict if file doesn't exist or key not found
    """

    if repo_path := getattr(args, "repo_path", None):
        config_path = Path(repo_path) / ".ai" / "config.yaml"
    elif config_path := getattr(args, "config", None):
        config_path = Path(config_path)
    elif getattr(args, "config_path", None):
        config_path = Path(config_path)
    else:
        return {}

    if config_path.exists():
        config = yaml.safe_load(config_path.read_text())
        try:
            for key in file_key.split("."):
                config = config[key]
        except KeyError:
            config = {}

        return config

    return {}


def load_config_as_dict(args, handler_config: Type[BaseModel]) -> dict:
    """
    Helper function to extract configuration values from arguments using Pydantic model fields.

    This is a helper function - consider using load_config() instead for full configuration loading.

    Uses the Pydantic model's field definitions to identify which arguments to extract from args.

    Args:
        args: Arguments object containing configuration values as attributes
        handler_config: Pydantic BaseModel class type defining the expected configuration structure

    Returns:
        dict: Configuration dictionary with values from args that match handler_config fields
    """

    config = {}

    for field_name, field_info in handler_config.model_fields.items():
        if issubclass(type(field_info.annotation), BaseModel):
            config[field_name] = load_config_as_dict(args, field_info.annotation)

        elif hasattr(args, field_name) and getattr(args, field_name) is not None:
            arg_value = getattr(args, field_name)
            if field_info.annotation in [Path, Optional[Path]]:
                config[field_name] = Path(arg_value)
            else:
                config[field_name] = arg_value

    return config


T = TypeVar("T", bound=BaseModel)


def load_config(args, handler_config: Type[T], file_key: str = "") -> T:
    """
    Load configuration from multiple sources with precedence order.

    This is the main configuration loading function that combines file-based and CLI configurations.

    Configuration loading order (later sources override earlier ones):
    1. Start with Pydantic model defaults
    2. Override with config file values (if file exists and key is found)
    3. Override with CLI arguments (only if explicitly set, i.e., not None)

    Args:
        args: Arguments object containing repo_path, config paths, and configuration values
        handler_config: Pydantic BaseModel class type defining the expected configuration structure
        file_key: Optional dot-separated key path for nested config file sections

    Returns:
        T: Instantiated Pydantic model with merged configuration values
    """
    file_config = load_config_from_file(args, file_key)
    cli_config = load_config_as_dict(args, handler_config)

    config = merge_dicts(file_config, cli_config)

    return handler_config(**config)

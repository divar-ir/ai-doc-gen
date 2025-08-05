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


# Analyzer
ANALYZER_LLM_MODEL = os.environ["ANALYZER_LLM_MODEL"]
ANALYZER_LLM_BASE_URL = os.environ["ANALYZER_LLM_BASE_URL"]
ANALYZER_LLM_API_KEY = os.environ["ANALYZER_LLM_API_KEY"]
ANALYZER_PARALLEL_TOOL_CALLS = str_to_bool(os.getenv("ANALYZER_PARALLEL_TOOL_CALLS", "true"))

# Documenter
DOCUMENTER_LLM_MODEL = os.environ["DOCUMENTER_LLM_MODEL"]
DOCUMENTER_LLM_BASE_URL = os.environ["DOCUMENTER_LLM_BASE_URL"]
DOCUMENTER_LLM_API_KEY = os.environ["DOCUMENTER_LLM_API_KEY"]
DOCUMENTER_PARALLEL_TOOL_CALLS = str_to_bool(os.getenv("DOCUMENTER_PARALLEL_TOOL_CALLS", "true"))

# Langfuse
ENABLE_LANGFUSE = str_to_bool(os.getenv("ENABLE_LANGFUSE", "false"))
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

# Gitlab
GITLAB_API_URL = os.getenv("GITLAB_API_URL", "https://git.divar.cloud")
GITLAB_USER_NAME = os.getenv("GITLAB_USER_NAME", "AI Analyzer")
GITLAB_USER_USERNAME = os.getenv("GITLAB_USER_USERNAME", "agent_doc")
GITLAB_USER_EMAIL = os.getenv("GITLAB_USER_EMAIL")
GITLAB_OAUTH_TOKEN = os.getenv("GITLAB_OAUTH_TOKEN")

# General
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

VERSION = os.getenv("APP_VERSION", "1.0.0")

CONSOLE_LOG_LEVEL = getattr(logging, os.getenv("CONSOLE_LOG_LEVEL", "DEBUG").upper())
FILE_LOG_LEVEL = getattr(logging, os.getenv("FILE_LOG_LEVEL", "INFO").upper())

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
        if issubclass(field_info.annotation, BaseModel):
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

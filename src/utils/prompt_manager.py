from copy import copy
from pathlib import Path
from typing import Any, Dict, Optional, Union

import jinja2
import yaml


class PromptManager:
    """Manages loading and rendering of prompts from YAML files."""

    def __init__(self, file_path: Union[str, Path], section_path: Optional[str] = None) -> None:
        """Initialize the prompt manager with a YAML file path.

        Args:
            file_path: Path to the YAML file containing prompts
            section_path: Section of the file to load prompts from (supports dot notation for nested keys)

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            yaml.YAMLError: If the YAML file is malformed
            ValueError: If the section is not found in the prompts file
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self._prompt_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML file {file_path}: {e}")

        if section_path:
            self._prompt_data = self._traverse_path(self._prompt_data, section_path)

        # Cache for rendered templates
        self._template_cache: Dict[str, jinja2.Template] = {}

    def _traverse_path(self, data: Any, path: str) -> Any:
        current = data

        try:
            for key in path.split("."):
                current = current[key]
        except (KeyError, TypeError) as e:
            raise ValueError(f"Path '{path}' not found in prompts data") from e

        return current

    def _load_prompt(self, prompt_name: str) -> Union[str, Dict[str, Any]]:
        """Load a prompt from the YAML data.

        Args:
            prompt_name: Key to load prompt from (supports dot notation for nested keys)

        Returns:
            The prompt value (string or dictionary)

        Raises:
            ValueError: If the prompt is not found
        """
        try:
            prompt = self._traverse_path(self._prompt_data, prompt_name)
            return copy(prompt)
        except ValueError as e:
            raise ValueError(f"Prompt '{prompt_name}' not found: {e}") from e

    def render_prompt(self, prompt_name: str, **prompt_args) -> str:
        """Render a prompt template with given parameters.

        Args:
            prompt_name: Name of the prompt to render (supports dot notation for nested keys)
            **prompt_args: Variables to substitute in the template

        Returns:
            Rendered prompt string

        Raises:
            ValueError: If the prompt name is not found
            jinja2.TemplateError: If template rendering fails
        """
        prompt_value = self._load_prompt(prompt_name)
        if not isinstance(prompt_value, str):
            raise ValueError(f"Prompt '{prompt_name}' is not a string")

        return self._render_template(prompt_value, **prompt_args)

    def _render_template(self, template_str: str, **kwargs) -> str:
        # Use template caching for performance
        if template_str not in self._template_cache:
            self._template_cache[template_str] = jinja2.Template(template_str)

        return self._template_cache[template_str].render(**kwargs)

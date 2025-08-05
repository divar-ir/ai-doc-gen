import os
import time
from pathlib import Path
from typing import Tuple

from opentelemetry import trace
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

import config
from utils import Logger, PromptManager
from utils.custom_models.gemini_provider import CustomGeminiGLA

from .tools import FileReadTool


class DocumenterResult(BaseModel):
    markdown_content: str = Field(..., description="The markdown content of the document")


class ReadmeConfig(BaseModel):
    """
    Configuration for README generation controlling which sections to exclude.

    Sections are organized into categories:
    - Essential sections: Overview and basic information
    - Architecture sections: Technical architecture information
    - Implementation sections: Details about code and interfaces
    - Development sections: Information for developers
    """

    # Essential sections
    exclude_project_overview: bool = Field(
        default=False,
        description="Exclude project overview with title, purpose, and features",
    )
    exclude_table_of_contents: bool = Field(default=False, description="Exclude table of contents for navigation")

    # Architecture sections
    exclude_architecture: bool = Field(
        default=False,
        description="Exclude high-level architecture overview with tech stack",
    )
    exclude_c4_model: bool = Field(default=False, description="Exclude C4 model architecture diagrams")
    exclude_repository_structure: bool = Field(default=False, description="Exclude repository directory structure")

    # Implementation sections
    exclude_dependencies_and_integration: bool = Field(
        default=False, description="Exclude service dependencies and integrations"
    )
    exclude_api_documentation: bool = Field(default=False, description="Exclude API endpoint documentation")

    # Development sections
    exclude_development_notes: bool = Field(default=False, description="Exclude development notes and conventions")
    exclude_known_issues_and_limitations: bool = Field(
        default=False, description="Exclude known issues and limitations"
    )
    exclude_additional_documentation: bool = Field(
        default=False, description="Exclude links to additional documentation"
    )
    use_existing_readme: bool = Field(
        default=False,
        description="Use existing README file as context or ignore it and create from scratch",
    )


class DocumenterAgentConfig(BaseModel):
    repo_path: Path = Field(..., description="The path to the repository")
    readme: ReadmeConfig = Field(default_factory=ReadmeConfig, description="The configuration for the README")


class DocumenterAgent:
    def __init__(self, config: DocumenterAgentConfig):
        self._config = config

        self._prompt_manager = PromptManager(file_path=Path(__file__).parent / "prompts" / "documenter.yaml")

    async def run(self):
        Logger.info("Starting documenter agent")
        user_prompt = self._render_prompt("agents.documenter.user_prompt")
        await self._run_agent(
            agent=self._documenter_agent,
            user_prompt=user_prompt,
            file_path=self._config.repo_path / "README.md",
        )

    async def _run_agent(self, agent: Agent, user_prompt: str, file_path: Path):
        trace.get_current_span().add_event(name=f"Running {agent.name}", attributes={"agent_name": agent.name})

        try:
            Logger.info(f"Running {agent.name}")
            start_time = time.time()
            result = await agent.run(
                user_prompt=user_prompt,
                output_type=DocumenterResult,
            )
            total_time = int(time.time() - start_time)
            Logger.info(
                f"{agent.name} run completed",
                data={
                    "total_tokens": result.usage().total_tokens,
                    "request_tokens": result.usage().request_tokens,
                    "response_tokens": result.usage().response_tokens,
                    "total_time": f"{total_time // 60}m {total_time % 60}s",
                    "total_messages": len(result.all_messages()),
                },
            )

            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                Logger.info(f"Writing to {file_path}")
                f.write(result.output.markdown_content)

                trace.get_current_span().set_attribute(f"{agent.name} result", result.output.markdown_content)

        except Exception as e:
            Logger.info(f"Error running agent: {e}")

    @property
    def _llm_model(self) -> Tuple[Model, ModelSettings]:
        model_name = config.DOCUMENTER_LLM_MODEL
        base_url = config.DOCUMENTER_LLM_BASE_URL
        api_key = config.DOCUMENTER_LLM_API_KEY

        if "gemini" in model_name:
            model = GeminiModel(
                model_name=model_name,
                provider=CustomGeminiGLA(api_key=api_key, base_url=base_url),
            )
        else:
            model = OpenAIModel(
                model_name=model_name,
                provider=OpenAIProvider(
                    base_url=base_url,
                    api_key=api_key,
                ),
            )

        settings = ModelSettings(
            temperature=0.0,
            max_tokens=8192,
            timeout=180,
            parallel_tool_calls=config.DOCUMENTER_PARALLEL_TOOL_CALLS,
        )

        return model, settings

    @property
    def _documenter_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="Documenter",
            model=model,
            model_settings=model_settings,
            output_type=DocumenterResult,
            retries=2,
            system_prompt=self._render_prompt("agents.documenter.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
            ],
            instrument=True,
        )

    def validate_succession(self):
        readme_path = self._config.repo_path / "README.md"
        if not readme_path.exists():
            raise ValueError("README file does not exist")

    def _render_prompt(self, prompt_name: str) -> str:
        # Render the template with the config
        available_ai_docs = []

        ai_docs_dir = self._config.repo_path / ".ai" / "docs"
        if ai_docs_dir.exists() and ai_docs_dir.is_dir():
            available_ai_docs = [
                os.path.join(self._config.repo_path, ".ai", "docs", doc.name)
                for doc in ai_docs_dir.iterdir()
                if doc.is_file() and doc.name.endswith(".md")
            ]

        template_vars = {
            "repo_path": str(self._config.repo_path),
            "available_ai_docs": available_ai_docs,
            **self._config.readme.model_dump(),
        }

        return self._prompt_manager.render_prompt(prompt_name, **template_vars)

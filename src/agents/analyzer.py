import asyncio
import time
from pathlib import Path
from typing import List, Tuple

from opentelemetry import trace
from pydantic import BaseModel, Field
from pydantic_ai import Agent, UnexpectedModelBehavior
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

import config
from utils import Logger, PromptManager

from .tools import FileReadTool, ListFilesTool


class AnalyzerAgentConfig(BaseModel):
    repo_path: Path = Field(..., description="The path to the repository")
    exclude_code_structure: bool = Field(default=False, description="Exclude code structure analysis")
    exclude_data_flow: bool = Field(default=False, description="Exclude data flow analysis")
    exclude_dependencies: bool = Field(default=False, description="Exclude dependencies analysis")
    exclude_request_flow: bool = Field(default=False, description="Exclude request flow analysis")
    exclude_api_analysis: bool = Field(default=False, description="Exclude api analysis")


class AnalyzerResult(BaseModel):
    markdown_content: str = Field(..., description="The markdown content of the analysis")


class AnalyzerAgent:
    def __init__(self, cfg: AnalyzerAgentConfig) -> None:
        self._config = cfg

        self._prompt_manager = PromptManager(file_path=Path(__file__).parent / "prompts" / "analyzer.yaml")

        if all(
            [
                self._config.exclude_code_structure,
                self._config.exclude_data_flow,
                self._config.exclude_dependencies,
                self._config.exclude_request_flow,
                self._config.exclude_api_analysis,
            ]
        ):
            raise ValueError("All analysis options are excluded")

    async def run(self):
        Logger.info("Starting analyzer agent")
        tasks = []
        analysis_files = []

        if not self._config.exclude_code_structure:
            analysis_files.append(
                self._config.repo_path / ".ai" / "docs" / "structure_analysis.md",
            )
            tasks.append(
                self._run_agent(
                    agent=self._structure_analyzer_agent,
                    user_prompt=self._render_prompt("agents.structure_analyzer.user_prompt"),
                    file_path=self._config.repo_path / ".ai" / "docs" / "structure_analysis.md",
                )
            )

        if not self._config.exclude_dependencies:
            analysis_files.append(
                self._config.repo_path / ".ai" / "docs" / "dependency_analysis.md",
            )
            tasks.append(
                self._run_agent(
                    agent=self._dependency_analyzer_agent,
                    user_prompt=self._render_prompt("agents.dependency_analyzer.user_prompt"),
                    file_path=self._config.repo_path / ".ai" / "docs" / "dependency_analysis.md",
                )
            )

        if not self._config.exclude_data_flow:
            analysis_files.append(
                self._config.repo_path / ".ai" / "docs" / "data_flow_analysis.md",
            )
            tasks.append(
                self._run_agent(
                    agent=self._data_flow_analyzer_agent,
                    user_prompt=self._render_prompt("agents.data_flow_analyzer.user_prompt"),
                    file_path=self._config.repo_path / ".ai" / "docs" / "data_flow_analysis.md",
                )
            )

        if not self._config.exclude_request_flow:
            analysis_files.append(
                self._config.repo_path / ".ai" / "docs" / "request_flow_analysis.md",
            )
            tasks.append(
                self._run_agent(
                    agent=self._request_flow_analyzer_agent,
                    user_prompt=self._render_prompt("agents.request_flow_analyzer.user_prompt"),
                    file_path=self._config.repo_path / ".ai" / "docs" / "request_flow_analysis.md",
                )
            )

        if not self._config.exclude_api_analysis:
            analysis_files.append(
                self._config.repo_path / ".ai" / "docs" / "api_analysis.md",
            )
            tasks.append(
                self._run_agent(
                    agent=self._api_analyzer_agent,
                    user_prompt=self._render_prompt("agents.api_analyzer.user_prompt"),
                    file_path=self._config.repo_path / ".ai" / "docs" / "api_analysis.md",
                )
            )

        Logger.debug("Running all agents")

        # Run all agents concurrently, continue even if some fail
        results = await asyncio.gather(*tasks, return_exceptions=True)

        Logger.debug("All agents finished")

        # Log results for each agent
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                Logger.error(f"Agent {i} failed: {result}")
            else:
                Logger.info(f"Agent {i} completed successfully")

        self.validate_succession(analysis_files)

    def validate_succession(self, analysis_files: List[Path]):
        missing_files = []
        for file in analysis_files:
            if not file.exists():
                missing_files.append(file)

        if missing_files:
            missing_files_str = ", ".join([str(file) for file in missing_files])
            Logger.warning(f"Some analysis files not found: {missing_files_str}")
            raise ValueError(f"Some analysis files not found: {missing_files_str}")

    async def _run_agent(self, agent: Agent, user_prompt: str, file_path: Path):
        trace.get_current_span().add_event(name=f"Running {agent.name}", attributes={"agent_name": agent.name})

        try:
            Logger.info(f"Running {agent.name}")
            start_time = time.time()
            async with agent:
                result: AgentRunResult = await agent.run(
                    user_prompt=user_prompt,
                    output_type=AnalyzerResult,
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
                output = self._cleanup_output(result.output.markdown_content)
                f.write(output)

                Logger.info(f"{agent.name} result saved to {file_path}")
                trace.get_current_span().set_attribute(f"{agent.name} result", result.output.markdown_content)

        except UnexpectedModelBehavior as e:
            Logger.info(f"Unexpected model behavior: {e}")
            raise e
        except Exception as e:
            Logger.info(f"Error running agent: {e}")
            raise e

    @property
    def _llm_model(self) -> Tuple[Model, ModelSettings]:
        model = OpenAIModel(
            model_name=config.ANALYZER_LLM_MODEL,
            provider=OpenAIProvider(
                base_url=config.ANALYZER_LLM_BASE_URL,
                api_key=config.ANALYZER_LLM_API_KEY,
            ),
        )

        settings = ModelSettings(
            temperature=0.0,
            max_tokens=8192,
            timeout=180,
            parallel_tool_calls=config.ANALYZER_PARALLEL_TOOL_CALLS,
        )

        return model, settings

    @property
    def _structure_analyzer_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="Structure Analyzer",
            model=model,
            model_settings=model_settings,
            output_type=AnalyzerResult,
            retries=2,
            system_prompt=self._render_prompt("agents.structure_analyzer.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
                ListFilesTool().get_tool(),
            ],
            instrument=True,
        )

    @property
    def _data_flow_analyzer_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="Data Flow Analyzer",
            model=model,
            model_settings=model_settings,
            output_type=str,
            retries=2,
            system_prompt=self._render_prompt("agents.data_flow_analyzer.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
                ListFilesTool().get_tool(),
            ],
            instrument=True,
        )

    @property
    def _dependency_analyzer_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="Dependency Analyzer",
            model=model,
            model_settings=model_settings,
            output_type=str,
            retries=2,
            system_prompt=self._render_prompt("agents.dependency_analyzer.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
                ListFilesTool().get_tool(),
            ],
            instrument=True,
        )

    @property
    def _request_flow_analyzer_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="Request Flow Analyzer",
            model=model,
            model_settings=model_settings,
            output_type=str,
            retries=2,
            system_prompt=self._render_prompt("agents.request_flow_analyzer.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
                ListFilesTool().get_tool(),
            ],
            instrument=True,
        )

    @property
    def _api_analyzer_agent(self) -> Agent:
        model, model_settings = self._llm_model

        return Agent(
            name="API Analyzer",
            model=model,
            model_settings=model_settings,
            output_type=AnalyzerResult,
            retries=2,
            system_prompt=self._render_prompt("agents.api_analyzer.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
                ListFilesTool().get_tool(),
            ],
            mcp_servers=[],
            instrument=True,
        )

    def _render_prompt(self, prompt_name: str) -> str:
        template_vars = {
            "repo_path": str(self._config.repo_path),
        }

        return self._prompt_manager.render_prompt(prompt_name, **template_vars)

    def _cleanup_output(self, output: str) -> str:
        # Cleanup absolute paths
        output = output.replace(str(self._config.repo_path), ".")

        return output

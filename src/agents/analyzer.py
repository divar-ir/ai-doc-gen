import asyncio
import time
from pathlib import Path
from typing import List, Tuple

from opentelemetry import trace
from pydantic import BaseModel, Field
from pydantic_ai import Agent, UnexpectedModelBehavior
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

import config
from utils import Logger, PromptManager, create_retrying_client

from .tools import FileReadTool, ListFilesTool


class AnalyzerAgentConfig(BaseModel):
    repo_path: Path = Field(..., description="The path to the repository")
    exclude_code_structure: bool = Field(default=False, description="Exclude code structure analysis")
    exclude_data_flow: bool = Field(default=False, description="Exclude data flow analysis")
    exclude_dependencies: bool = Field(default=False, description="Exclude dependencies analysis")
    exclude_request_flow: bool = Field(default=False, description="Exclude request flow analysis")
    exclude_api_analysis: bool = Field(default=False, description="Exclude api analysis")


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

        analysis_files = []
        agent_tasks = {}

        if not self._config.exclude_code_structure:
            agent = self._structure_analyzer_agent
            analysis_files.append(self._config.repo_path / ".ai" / "docs" / "structure_analysis.md")
            agent_tasks[agent.name] = self._run_agent(
                agent=agent,
                user_prompt=self._render_prompt("agents.structure_analyzer.user_prompt"),
                file_path=self._config.repo_path / ".ai" / "docs" / "structure_analysis.md",
            )

        if not self._config.exclude_dependencies:
            agent = self._dependency_analyzer_agent
            analysis_files.append(self._config.repo_path / ".ai" / "docs" / "dependency_analysis.md")
            agent_tasks[agent.name] = self._run_agent(
                agent=agent,
                user_prompt=self._render_prompt("agents.dependency_analyzer.user_prompt"),
                file_path=self._config.repo_path / ".ai" / "docs" / "dependency_analysis.md",
            )

        if not self._config.exclude_data_flow:
            agent = self._data_flow_analyzer_agent
            analysis_files.append(self._config.repo_path / ".ai" / "docs" / "data_flow_analysis.md")
            agent_tasks[agent.name] = self._run_agent(
                agent=agent,
                user_prompt=self._render_prompt("agents.data_flow_analyzer.user_prompt"),
                file_path=self._config.repo_path / ".ai" / "docs" / "data_flow_analysis.md",
            )

        if not self._config.exclude_request_flow:
            agent = self._request_flow_analyzer_agent
            analysis_files.append(self._config.repo_path / ".ai" / "docs" / "request_flow_analysis.md")
            agent_tasks[agent.name] = self._run_agent(
                agent=agent,
                user_prompt=self._render_prompt("agents.request_flow_analyzer.user_prompt"),
                file_path=self._config.repo_path / ".ai" / "docs" / "request_flow_analysis.md",
            )

        if not self._config.exclude_api_analysis:
            agent = self._api_analyzer_agent
            analysis_files.append(self._config.repo_path / ".ai" / "docs" / "api_analysis.md")
            agent_tasks[agent.name] = self._run_agent(
                agent=agent,
                user_prompt=self._render_prompt("agents.api_analyzer.user_prompt"),
                file_path=self._config.repo_path / ".ai" / "docs" / "api_analysis.md",
            )

        Logger.debug("Running all agents")

        # Run all agents concurrently
        results = await asyncio.gather(*agent_tasks.values(), return_exceptions=True)

        Logger.debug("All agents finished")

        # Log results with agent names
        for agent_name, result in zip(agent_tasks.keys(), results):
            if isinstance(result, Exception):
                Logger.error(f"Agent {agent_name} failed: {result}", exc_info=True)
            else:
                Logger.info(f"Agent {agent_name} completed successfully")

        self.validate_succession(analysis_files)

    def validate_succession(self, analysis_files: List[Path]):
        missing_files = []
        for file in analysis_files:
            if not file.exists():
                missing_files.append(file)

        if not missing_files:
            # All files exist - complete success
            Logger.info(f"All {len(analysis_files)} analysis files generated successfully")
            return

        if len(missing_files) == len(analysis_files):
            # ALL files missing - complete failure
            Logger.error("Complete analysis failure: no analysis files were generated")
            raise ValueError("Complete analysis failure: no analysis files were generated")

        # SOME files missing - partial success, log warning but continue
        missing_files_str = ", ".join([str(file) for file in missing_files])
        successful_count = len(analysis_files) - len(missing_files)
        Logger.warning(
            f"Partial analysis success: {successful_count}/{len(analysis_files)} files generated. Missing: {missing_files_str}"
        )
        # Continue without raising error - partial results are better than no results

    async def _run_agent(self, agent: Agent, user_prompt: str, file_path: Path):
        trace.get_current_span().add_event(name=f"Running {agent.name}", attributes={"agent_name": agent.name})

        try:
            Logger.info(f"Running {agent.name}")
            start_time = time.time()
            async with agent:
                result: AgentRunResult = await agent.run(
                    user_prompt=user_prompt,
                    output_type=str,
                )
            total_time = int(time.time() - start_time)
            Logger.info(
                f"{agent.name} run completed",
                data={
                    "total_tokens": result.usage().total_tokens,
                    "request_tokens": result.usage().input_tokens,
                    "response_tokens": result.usage().output_tokens,
                    "total_time": f"{total_time // 60}m {total_time % 60}s",
                    "total_messages": len(result.all_messages()),
                },
            )

            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                output = self._cleanup_output(result.output)
                f.write(output)

                Logger.info(f"{agent.name} result saved to {file_path}")
                trace.get_current_span().set_attribute(f"{agent.name} result", result.output)

        except UnexpectedModelBehavior as e:
            Logger.info(f"Unexpected model behavior: {e}", exc_info=True)
            raise
        except Exception as e:
            Logger.info(f"Error running agent: {e}", exc_info=True)
            raise

    @property
    def _llm_model(self) -> Tuple[Model, ModelSettings]:
        retrying_http_client = create_retrying_client()

        model = OpenAIChatModel(
            model_name=config.ANALYZER_LLM_MODEL,
            provider=OpenAIProvider(
                base_url=config.ANALYZER_LLM_BASE_URL,
                api_key=config.ANALYZER_LLM_API_KEY,
                http_client=retrying_http_client,
            ),
        )

        settings = ModelSettings(
            temperature=config.ANALYZER_LLM_TEMPERATURE,
            max_tokens=config.ANALYZER_LLM_MAX_TOKENS,
            timeout=config.ANALYZER_LLM_TIMEOUT,
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
            output_type=str,
            retries=config.ANALYZER_AGENT_RETRIES,
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
            retries=config.ANALYZER_AGENT_RETRIES,
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
            retries=config.ANALYZER_AGENT_RETRIES,
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
            retries=config.ANALYZER_AGENT_RETRIES,
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
            output_type=str,
            retries=config.ANALYZER_AGENT_RETRIES,
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

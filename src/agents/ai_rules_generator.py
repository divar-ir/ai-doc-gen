import asyncio
import time
from pathlib import Path
from typing import Literal, Optional, Tuple

from opentelemetry import trace
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

import config
from utils import Logger, PromptManager, create_retrying_client

from .tools import FileReadTool


class CursorRule(BaseModel):
    """Single Cursor MDC rule file."""

    filename: str = Field(..., description="Filename for the .mdc file (e.g., 'project-overview.mdc')")
    description: str = Field(..., description="Brief description of what this rule does")
    globs: list[str] = Field(default_factory=list, description="File patterns this rule applies to")
    always_apply: bool = Field(default=False, description="Whether to always apply this rule")
    content: str = Field(..., description="Markdown content of the rule")


class MarkdownOutput(BaseModel):
    """Output model for markdown files generation (CLAUDE.md and AGENTS.md)."""

    claude_md: Optional[str] = Field(None, description="Generated CLAUDE.md content")
    agents_md: Optional[str] = Field(None, description="Generated AGENTS.md content")


class CursorRulesOutput(BaseModel):
    """Output model for Cursor rules generation."""

    cursor_rules: Optional[list[CursorRule]] = Field(None, description="Generated Cursor .mdc rule files")


class AIRulesOutput(BaseModel):
    """Combined output model for AI rules generation."""

    claude_md: Optional[str] = Field(None, description="Generated CLAUDE.md content")
    agents_md: Optional[str] = Field(None, description="Generated AGENTS.md content")
    cursor_rules: Optional[list[CursorRule]] = Field(None, description="Generated Cursor .mdc rule files")


class AIRulesGeneratorConfig(BaseModel):
    """Configuration for AI rules generation."""

    repo_path: Path = Field(..., description="The path to the repository")

    # Skip existing files (don't overwrite if file exists and this is True)
    skip_existing_claude_md: bool = Field(
        default=False,
        description="Skip CLAUDE.md generation if file already exists (don't overwrite)",
    )
    skip_existing_agents_md: bool = Field(
        default=False,
        description="Skip AGENTS.md generation if file already exists (don't overwrite)",
    )
    skip_existing_cursor_rules: bool = Field(
        default=False,
        description="Skip Cursor rules generation if .cursor/rules/ directory already exists (don't overwrite)",
    )

    # Content customization
    detail_level: Literal["minimal", "standard", "comprehensive"] = Field(
        default="standard",
        description="Level of detail in generated files",
    )
    max_claude_lines: int = Field(default=500, description="Maximum lines for CLAUDE.md")
    max_agents_lines: int = Field(default=150, description="Maximum lines for AGENTS.md (strict)")


class AIRulesGeneratorAgent:
    def __init__(self, cfg: AIRulesGeneratorConfig):
        self._config = cfg
        self._prompt_manager = PromptManager(file_path=Path(__file__).parent / "prompts" / "ai_rules_generator.yaml")

    async def run(self) -> AIRulesOutput:
        Logger.info("Running AI rules generator agent with concurrent generation")

        self._verify_analysis_files()

        skip_files = self._check_skip_files()
        existing_files = self._read_existing_files()

        tasks = []

        if not (skip_files["claude_md"] and skip_files["agents_md"]):
            tasks.append(self._run_markdown_generation(skip_files, existing_files))
        else:
            Logger.info("Skipping markdown generation (both files marked to skip)")

        if not skip_files["cursor_rules"]:
            tasks.append(self._run_cursor_rules_generation(existing_files))
        else:
            Logger.info("Skipping Cursor rules generation")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        markdown_result = None
        cursor_result = None

        for result in results:
            if isinstance(result, Exception):
                Logger.error(f"Error in generation task: {result}")
                raise result
            elif isinstance(result, MarkdownOutput):
                markdown_result = result
            elif isinstance(result, CursorRulesOutput):
                cursor_result = result

        output = AIRulesOutput(
            claude_md=markdown_result.claude_md if markdown_result else None,
            agents_md=markdown_result.agents_md if markdown_result else None,
            cursor_rules=cursor_result.cursor_rules if cursor_result else None,
        )

        self._write_files(output)

        return output

    async def _run_markdown_generation(
        self, skip_files: dict[str, bool], existing_files: dict[str, Optional[str]]
    ) -> MarkdownOutput:
        Logger.info("Generating markdown files (CLAUDE.md and AGENTS.md)")

        user_prompt = self._render_markdown_prompt(
            skip_files=skip_files,
            existing_files=existing_files,
        )

        result = await self._run_agent(
            agent=self._markdown_agent,
            user_prompt=user_prompt,
            output_type=MarkdownOutput,
            agent_name="MarkdownGenerator",
        )

        return result

    async def _run_cursor_rules_generation(self, existing_files: dict[str, Optional[str]]) -> CursorRulesOutput:
        Logger.info("Generating Cursor rules (.cursor/rules/*.mdc)")

        user_prompt = self._render_cursor_rules_prompt(existing_files=existing_files)

        result = await self._run_agent(
            agent=self._cursor_rules_agent,
            user_prompt=user_prompt,
            output_type=CursorRulesOutput,
            agent_name="CursorRulesGenerator",
        )

        if result.cursor_rules is None:
            Logger.warning("LLM returned cursor_rules=None")
        elif len(result.cursor_rules) == 0:
            Logger.warning("LLM returned empty cursor_rules list")
        else:
            Logger.info(f"Generated {len(result.cursor_rules)} cursor rule files")

        return result

    def _check_skip_files(self) -> dict[str, bool]:
        skip_files = {
            "claude_md": False,
            "agents_md": False,
            "cursor_rules": False,
        }

        if self._config.skip_existing_claude_md:
            claude_path = self._config.repo_path / "CLAUDE.md"
            if claude_path.exists():
                Logger.info("Skipping CLAUDE.md - file exists and skip_existing_claude_md=True")
                skip_files["claude_md"] = True

        if self._config.skip_existing_agents_md:
            agents_path = self._config.repo_path / "AGENTS.md"
            if agents_path.exists():
                Logger.info("Skipping AGENTS.md - file exists and skip_existing_agents_md=True")
                skip_files["agents_md"] = True

        if self._config.skip_existing_cursor_rules:
            cursor_rules_path = self._config.repo_path / ".cursor" / "rules"
            if cursor_rules_path.exists() and any(cursor_rules_path.glob("*.mdc")):
                Logger.info("Skipping Cursor rules - directory exists and skip_existing_cursor_rules=True")
                skip_files["cursor_rules"] = True

        return skip_files

    def _read_existing_files(self) -> dict[str, Optional[str]]:
        existing_files = {
            "claude_md": None,
            "agents_md": None,
            "cursor_rules": None,
        }

        if not self._config.skip_existing_claude_md:
            claude_path = self._config.repo_path / "CLAUDE.md"
            if claude_path.exists():
                existing_files["claude_md"] = claude_path.read_text()
                Logger.info("Using existing CLAUDE.md as reference")

        # Read AGENTS.md (unless skipping)
        if not self._config.skip_existing_agents_md:
            agents_path = self._config.repo_path / "AGENTS.md"
            if agents_path.exists():
                existing_files["agents_md"] = agents_path.read_text()
                Logger.info("Using existing AGENTS.md as reference")

        # Read Cursor rules (unless skipping) - support both new and legacy formats
        if not self._config.skip_existing_cursor_rules:
            cursor_rules_content = []

            # Check new format: .cursor/rules/*.mdc
            cursor_rules_path = self._config.repo_path / ".cursor" / "rules"
            if cursor_rules_path.exists():
                mdc_files = list(cursor_rules_path.glob("*.mdc"))
                if mdc_files:
                    Logger.info(f"Found {len(mdc_files)} existing .mdc rule files")
                    for mdc_file in mdc_files:
                        cursor_rules_content.append(f"## {mdc_file.name}\n{mdc_file.read_text()}")

            # Check legacy format: .cursorrules (for backward compatibility)
            legacy_cursor_rules = self._config.repo_path / ".cursorrules"
            if legacy_cursor_rules.exists():
                Logger.info("Found legacy .cursorrules file - using as reference")
                cursor_rules_content.append(f"## Legacy .cursorrules\n{legacy_cursor_rules.read_text()}")

            if cursor_rules_content:
                existing_files["cursor_rules"] = "\n\n".join(cursor_rules_content)
                Logger.info("Using existing Cursor rules as reference")

        return existing_files

    async def _run_agent(self, agent: Agent, user_prompt: str, output_type: type, agent_name: str):
        """Run an agent with the given prompt and output type."""
        trace.get_current_span().add_event(name=f"Running {agent_name}", attributes={"agent_name": agent_name})

        try:
            Logger.info(f"Running {agent_name}")
            start_time = time.time()

            result = await agent.run(
                user_prompt=user_prompt,
                output_type=output_type,
            )

            total_time = int(time.time() - start_time)
            Logger.info(
                f"{agent_name} run completed",
                data={
                    "total_tokens": result.usage().total_tokens,
                    "request_tokens": result.usage().input_tokens,
                    "response_tokens": result.usage().output_tokens,
                    "total_time": f"{total_time // 60}m {total_time % 60}s",
                    "total_messages": len(result.all_messages()),
                },
            )

            return result.output

        except Exception as e:
            Logger.error(
                f"Error running {agent_name}",
                data={
                    "error": str(e),
                },
                exc_info=True,
            )
            raise e

    @property
    def _markdown_llm_model(self) -> Tuple[Model, ModelSettings]:
        model = OpenAIChatModel(
            model_name=config.AI_RULES_LLM_MODEL,
            provider=OpenAIProvider(
                base_url=config.AI_RULES_LLM_BASE_URL,
                api_key=config.AI_RULES_LLM_API_KEY,
                http_client=create_retrying_client(),
            ),
        )

        settings = ModelSettings(
            temperature=config.AI_RULES_LLM_TEMPERATURE,
            max_tokens=config.AI_RULES_LLM_MAX_TOKENS_MARKDOWN,
            timeout=config.AI_RULES_LLM_TIMEOUT,
            parallel_tool_calls=config.AI_RULES_PARALLEL_TOOL_CALLS,
        )

        return model, settings

    @property
    def _cursor_rules_llm_model(self) -> Tuple[Model, ModelSettings]:
        model = OpenAIChatModel(
            model_name=config.AI_RULES_LLM_MODEL,
            provider=OpenAIProvider(
                base_url=config.AI_RULES_LLM_BASE_URL,
                api_key=config.AI_RULES_LLM_API_KEY,
                http_client=create_retrying_client(),
            ),
        )

        settings = ModelSettings(
            temperature=config.AI_RULES_LLM_TEMPERATURE,
            max_tokens=config.AI_RULES_LLM_MAX_TOKENS_CURSOR,
            timeout=config.AI_RULES_LLM_TIMEOUT,
            parallel_tool_calls=config.AI_RULES_PARALLEL_TOOL_CALLS,
        )

        return model, settings

    @property
    def _markdown_agent(self) -> Agent:
        model, model_settings = self._markdown_llm_model

        return Agent(
            name="MarkdownGenerator",
            model=model,
            model_settings=model_settings,
            output_type=MarkdownOutput,
            retries=config.AI_RULES_AGENT_RETRIES,
            system_prompt=self._prompt_manager.render_prompt("agents.markdown_generator.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
            ],
            instrument=True,
        )

    @property
    def _cursor_rules_agent(self) -> Agent:
        model, model_settings = self._cursor_rules_llm_model

        return Agent(
            name="CursorRulesGenerator",
            model=model,
            model_settings=model_settings,
            output_type=CursorRulesOutput,
            retries=config.AI_RULES_AGENT_RETRIES,
            system_prompt=self._prompt_manager.render_prompt("agents.cursor_rules_generator.system_prompt"),
            tools=[
                FileReadTool().get_tool(),
            ],
            instrument=True,
        )

    def _render_markdown_prompt(
        self,
        skip_files: dict[str, bool],
        existing_files: dict[str, Optional[str]],
    ) -> str:
        # Read analysis files
        analysis_files = self._read_analysis_files()

        # Determine which files to generate
        generate_claude_md = not skip_files["claude_md"]
        generate_agents_md = not skip_files["agents_md"]

        # Prepare template variables
        template_vars = {
            "repo_path": str(self._config.repo_path),
            "generate_claude_md": generate_claude_md,
            "generate_agents_md": generate_agents_md,
            "detail_level": self._config.detail_level,
            "max_claude_lines": self._config.max_claude_lines,
            "max_agents_lines": self._config.max_agents_lines,
            "existing_claude_md": existing_files.get("claude_md"),
            "existing_agents_md": existing_files.get("agents_md"),
            **analysis_files,
        }

        return self._prompt_manager.render_prompt("agents.markdown_generator.user_prompt", **template_vars)

    def _render_cursor_rules_prompt(self, existing_files: dict[str, Optional[str]]) -> str:
        # Read analysis files
        analysis_files = self._read_analysis_files()

        # Prepare template variables
        template_vars = {
            "repo_path": str(self._config.repo_path),
            "detail_level": self._config.detail_level,
            "existing_cursor_rules": existing_files.get("cursor_rules"),
            **analysis_files,
        }

        return self._prompt_manager.render_prompt("agents.cursor_rules_generator.user_prompt", **template_vars)

    def _read_analysis_files(self) -> dict[str, Optional[str]]:
        analysis_files = {}
        docs_path = self._config.repo_path / ".ai" / "docs"

        # Required analysis files
        for analysis_type in ["structure_analysis", "dependency_analysis", "data_flow_analysis"]:
            file_path = docs_path / f"{analysis_type}.md"
            if file_path.exists():
                analysis_files[analysis_type] = file_path.read_text()
            else:
                Logger.warning(f"Analysis file {file_path} not found")
                analysis_files[analysis_type] = ""

        # Optional analysis files
        for analysis_type in ["request_flow_analysis", "api_analysis"]:
            file_path = docs_path / f"{analysis_type}.md"
            if file_path.exists():
                analysis_files[analysis_type] = file_path.read_text()
            else:
                analysis_files[analysis_type] = None

        return analysis_files

    def _verify_analysis_files(self):
        docs_path = self._config.repo_path / ".ai" / "docs"

        if not docs_path.exists():
            raise ValueError(
                f"Analysis directory not found at {docs_path}. "
                f"Please run 'analyze' command first before generating AI rules."
            )

        # Check for required analysis files
        required_files = ["structure_analysis.md", "dependency_analysis.md", "data_flow_analysis.md"]

        missing_files = []
        for file_name in required_files:
            file_path = docs_path / file_name
            if not file_path.exists():
                missing_files.append(file_name)

        if missing_files:
            raise ValueError(
                f"Required analysis files not found: {', '.join(missing_files)}. "
                f"Please run 'analyze' command first before generating AI rules."
            )

        Logger.info("All required analysis files found")

    def _write_files(self, output: AIRulesOutput):
        """Write generated files to disk."""
        files_written = []
        files_skipped = []

        # Write CLAUDE.md
        if output.claude_md is not None:
            claude_path = self._config.repo_path / "CLAUDE.md"
            claude_path.write_text(output.claude_md)
            files_written.append("CLAUDE.md")
            Logger.info(f"Generated CLAUDE.md at {claude_path}")
        else:
            files_skipped.append("CLAUDE.md")
            Logger.info("CLAUDE.md generation skipped")

        # Write AGENTS.md
        if output.agents_md is not None:
            agents_path = self._config.repo_path / "AGENTS.md"
            agents_path.write_text(output.agents_md)
            files_written.append("AGENTS.md")

            # Validate line count
            line_count = len(output.agents_md.splitlines())
            if line_count > self._config.max_agents_lines:
                Logger.warning(
                    f"AGENTS.md has {line_count} lines, exceeding the maximum of {self._config.max_agents_lines}"
                )
            else:
                Logger.info(f"Generated AGENTS.md at {agents_path} ({line_count} lines)")
        else:
            files_skipped.append("AGENTS.md")
            Logger.info("AGENTS.md generation skipped")

        # Write Cursor rules (.cursor/rules/*.mdc)
        if output.cursor_rules is not None and len(output.cursor_rules) > 0:
            cursor_rules_dir = self._config.repo_path / ".cursor" / "rules"
            cursor_rules_dir.mkdir(parents=True, exist_ok=True)

            for rule in output.cursor_rules:
                # Create YAML frontmatter
                globs_yaml = "\n".join(f'  - "{glob}"' for glob in rule.globs)
                frontmatter = f"""---
description: {rule.description}
globs:
{globs_yaml}
alwaysApply: {str(rule.always_apply).lower()}
---

"""
                # Write file with frontmatter + content
                rule_path = cursor_rules_dir / rule.filename
                rule_path.write_text(frontmatter + rule.content)
                files_written.append(f".cursor/rules/{rule.filename}")

            Logger.info(f"Generated {len(output.cursor_rules)} Cursor rule files in {cursor_rules_dir}")
        else:
            files_skipped.append(".cursor/rules/")
            Logger.info("Cursor rules generation skipped")

        # Log summary
        Logger.info(
            "AI rules generation completed",
            data={
                "files_written": files_written,
                "files_skipped": files_skipped,
            },
        )

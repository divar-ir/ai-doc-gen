# Code Structure Analysis

## Architectural Overview

The repository is a Python 3.13 CLI application ("ai-doc-gen") that performs multi-agent AI analysis of codebases and generates documentation (README.md, CLAUDE.md, AGENTS.md, `.cursor/rules/*.mdc`). It is organized as a layered pipeline:

```
CLI (src/main.py, argparse)
  -> Handlers (src/handlers/) — command orchestration, config, tracing
    -> Agents (src/agents/) — pydantic-ai LLM agents with tools
      -> Tools (src/agents/tools/) — file reading, directory listing
      -> Prompts (src/agents/prompts/*.yaml) — Jinja2 templates in YAML
  -> Utilities (src/utils/) — logging, prompt management, HTTP retry, worker pool, git helpers
```

Key architectural characteristics:

- **Multi-agent concurrency**: `AnalyzerAgent` (src/agents/analyzer.py) runs up to 5 specialized analysis agents concurrently via a semaphore-bounded `WorkerPool` (src/utils/worker_pool.py); `AIRulesGeneratorAgent` (src/agents/ai_rules_generator.py) runs 2 generators concurrently via `asyncio.gather(return_exceptions=True)`.
- **Configuration layering**: Pydantic model defaults < YAML file (`.ai/config.yaml`) < CLI arguments, merged in `load_config()` (src/config.py) with `merge_dicts` (src/utils/dict.py). Environment variables (loaded via `python-dotenv` in src/config.py) supply LLM credentials and tuning knobs as module-level constants.
- **Error isolation / graceful degradation**: individual agent failures are captured (exceptions returned from the worker pool / gather) and logged; the analyze run only fails if all output files are missing (`AnalyzerAgent.validate_succession`).
- **Observability**: optional Langfuse via OpenTelemetry/logfire (`configure_langfuse` in src/main.py); handlers open tracing spans and record repo path, version, and config flags.
- **Delivery surfaces**: a Dockerfile, a Helm chart under `k8s/helm/` (CronJob-based deployment for the GitLab automation), and a Claude Code plugin/skills packaging (`.claude-plugin/`, `skills/`) that re-expresses the same three workflows (analyze, generate-readme, generate-ai-rules) as agent skills.

There is no persistent state, database, or server: each run is a stateless batch process whose outputs are files written into the target repository (`.ai/docs/*.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/*.mdc`).

## Core Components

| Component | Location | Responsibility |
|---|---|---|
| CLI entry point | `src/main.py` | `parse_args()` builds argparse subcommands (`analyze`, `generate readme`, `generate ai-rules`, `cronjob analyze`) auto-derived from Pydantic config models via `add_handler_args`/`_add_field_arg`; dispatches to async command functions; configures logging and optional Langfuse. Entry: `cli_main()` / `main()`. |
| Configuration | `src/config.py` | Environment constants (`ANALYZER_LLM_*`, `DOCUMENTER_LLM_*`, `AI_RULES_LLM_*`, `GITLAB_*`, HTTP retry and tool settings) and config loading (`load_config`, `load_config_from_file`, `load_config_as_dict`). |
| Handler base | `src/handlers/base_handler.py` | `AbstractHandler` (abstract `handle()`), `BaseHandler`, `BaseHandlerConfig` (validates `repo_path`, auto-resolves `.ai/config.yaml`/`.yml` via `resolve_default_config_path`). |
| Analyze handler | `src/handlers/analyze.py` | `AnalyzeHandler` + `AnalyzeHandlerConfig(BaseHandlerConfig, AnalyzerAgentConfig)`; wraps `AnalyzerAgent.run()` in an OTel span. |
| README handler | `src/handlers/readme.py` | `ReadmeHandler` + `ReadmeHandlerConfig(BaseHandlerConfig, DocumenterAgentConfig)`; wraps `DocumenterAgent.run()`. |
| AI rules handler | `src/handlers/ai_rules.py` | `AIRulesHandler` + `AIRulesHandlerConfig(BaseHandlerConfig, AIRulesGeneratorConfig)`; wraps `AIRulesGeneratorAgent.run()`. |
| Cronjob handler | `src/handlers/cronjob.py` | `JobAnalyzeHandler` + `JobAnalyzeHandlerConfig`; GitLab batch automation: discovers group projects, filters applicability, clones, runs `AnalyzeHandler`, commits to `ai-analyzer-{YYYY-MM-DD}` branch, opens MR, cleans up (try/finally). |
| Analyzer agent | `src/agents/analyzer.py` | `AnalyzerAgent` + `AnalyzerAgentConfig`; builds 5 pydantic-ai agents (Structure, Dependency, Data Flow, Request Flow, API analyzers) and runs them through `WorkerPool`; writes `.ai/docs/{structure,dependency,data_flow,request_flow,api}_analysis.md`; `_cleanup_output` rewrites absolute repo paths to `.`. |
| Documenter agent | `src/agents/documenter.py` | `DocumenterAgent` + `DocumenterAgentConfig` + `ReadmeConfig` (per-section `exclude_*` flags, `use_existing_readme`); single agent producing structured `DocumenterResult.markdown_content`, written to `README.md`. |
| AI rules agent | `src/agents/ai_rules_generator.py` | `AIRulesGeneratorAgent` + `AIRulesGeneratorConfig` (skip flags, `detail_level`, line limits); verifies required analysis files exist, runs `MarkdownGenerator` (CLAUDE.md + AGENTS.md) and `CursorRulesGenerator` (`.mdc` files with YAML frontmatter) concurrently; `_write_files` persists outputs. |
| Agent tools | `src/agents/tools/file_tool/file_reader.py`, `src/agents/tools/dir_tool/list_files.py` | `FileReadTool` (`Read-File`: ranged file reads, default 200 lines) and `ListFilesTool` (`List-Files-Tool`: recursive listing with a large `DEFAULT_IGNORED_DIRS`/extensions filter). Both raise `ModelRetry` on recoverable errors. |
| Prompt templates | `src/agents/prompts/analyzer.yaml`, `src/agents/prompts/documenter.yaml`, `src/agents/prompts/ai_rules_generator.yaml` | Per-agent `system_prompt`/`user_prompt` Jinja2 templates keyed under `agents.<name>.<prompt>`. |
| Utilities | `src/utils/` | `Logger` (singleton, file+console), `PromptManager` (YAML + Jinja2 with template cache), `create_retrying_client` (httpx + tenacity), `WorkerPool`, `get_repo_version` (`{branch}@{commit}`), `merge_dicts`. |
| Skills packaging | `skills/analyze-codebase/`, `skills/generate-readme/`, `skills/generate-ai-rules/`, `.claude-plugin/` | Claude Code plugin variant of the same workflows; `skills/analyze-codebase/references/*.md` mirror the analyzer system prompts as subagent instructions. |
| Deployment | `Dockerfile`, `k8s/helm/` (Chart, values, `templates/cronjob.yaml`, `configmap.yaml`, `service.yaml`, `servicemonitor.yaml`) | Container image and Kubernetes CronJob deployment for the GitLab automation. |

## Service Definitions

This is a CLI batch tool, not a network service; "services" are the four command workflows exposed by `src/main.py`:

1. **analyze** (`AnalyzeHandler`, src/handlers/analyze.py): runs up to 5 concurrent analysis agents against `repo_path`, producing `.ai/docs/structure_analysis.md`, `dependency_analysis.md`, `data_flow_analysis.md`, `request_flow_analysis.md`, `api_analysis.md`. Exclusion flags: `exclude_code_structure`, `exclude_data_flow`, `exclude_dependencies`, `exclude_request_flow`, `exclude_api_analysis`; concurrency via `max_workers` (0 = CPU count). Raises `ValueError` if all analyses are excluded or all fail.
2. **generate readme** (`ReadmeHandler`, src/handlers/readme.py): single `Documenter` agent consumes `.ai/docs/*.md` (paths injected into the prompt) and writes `README.md`; section inclusion controlled by `ReadmeConfig` `exclude_*` flags.
3. **generate ai-rules** (`AIRulesHandler`, src/handlers/ai_rules.py): requires `structure_analysis.md`, `dependency_analysis.md`, `data_flow_analysis.md` in `.ai/docs/` (hard precondition in `_verify_analysis_files`; `request_flow_analysis.md` and `api_analysis.md` are optional); writes `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/*.mdc`.
4. **cronjob analyze** (`JobAnalyzeHandler`, src/handlers/cronjob.py): sequential GitLab batch pipeline — group discovery (`group_project_id`, default 3), applicability filtering (`_is_applicable_project`: archived, ignored subgroups/projects, last-commit age vs `max_days_since_last_commit`, prior analysis commit `[AI] Analyzer-Agent: Create/Update AI Analysis`, existing branch/MR), clone into `working_path` (default `/tmp/cronjob/projects`), analyze, commit/push, open MR with `[skip ci]`.

External integrations: OpenAI-compatible LLM endpoints (via `pydantic_ai.models.openai.OpenAIChatModel` + `OpenAIProvider`; separate model/base-url/key per agent family: `ANALYZER_LLM_*`, `DOCUMENTER_LLM_*`, `AI_RULES_LLM_*` with the latter defaulting to documenter values), GitLab (python-gitlab + GitPython), and optional Langfuse OTLP export.

## Interface Contracts

- **`AbstractHandler`** (src/handlers/base_handler.py): abstract `async handle()` — the single command-execution contract. `BaseHandler` adds construction from a `BaseHandlerConfig`. Three handlers extend `BaseHandler`; `JobAnalyzeHandler` extends `AbstractHandler` directly (it takes a GitLab client plus its own config, not a repo path).
- **`BaseHandlerConfig`** (src/handlers/base_handler.py): Pydantic model requiring `repo_path`, optional `config`; `@model_validator(mode="after") resolve_config_path` validates repo existence and resolves the default config path. Handler configs are formed by multiple inheritance: `HandlerConfig = BaseHandlerConfig + AgentConfig` (e.g. `AnalyzeHandlerConfig(BaseHandlerConfig, AnalyzerAgentConfig)`), which also drives automatic CLI flag generation in `src/main.py`.
- **Tool contract** (pydantic-ai `Tool`): each tool class exposes `get_tool()` returning `Tool(self._run, name=..., takes_ctx=False, max_retries=...)`; `_run` is a plain function whose signature/docstring defines the LLM-visible schema; recoverable failures raise `pydantic_ai.ModelRetry`.
- **Agent output contracts** (Pydantic output models): analyzer agents output `str` (raw markdown); `DocumenterAgent` outputs `DocumenterResult{markdown_content}`; AI rules agents output `MarkdownOutput{claude_md, agents_md}` and `CursorRulesOutput{cursor_rules: list[CursorRule]}`, combined into `AIRulesOutput`. `CursorRule{filename, description, globs, always_apply, content}` maps 1:1 to an `.mdc` file with generated YAML frontmatter.
- **WorkerPool contract** (src/utils/worker_pool.py): `run(tasks: List[Callable[[], Awaitable[T]]]) -> List[T | Exception]` — takes zero-arg async callables (built with `functools.partial` in `AnalyzerAgent.run`), preserves order, returns exceptions in-place instead of raising.
- **PromptManager contract** (src/utils/prompt_manager.py): `render_prompt(prompt_name, **vars) -> str` with dot-notation lookup into YAML (e.g. `agents.structure_analyzer.system_prompt`) and Jinja2 rendering with a per-instance template cache.
- **Config file contract**: `.ai/config.yaml` sections keyed by `file_key` passed to `load_config` — `analyzer`, `generate.readme`, `generate.ai_rules`, `cronjob.analyze` (see `config_example.yaml`).

## Design Patterns Identified

- **Handler / Command pattern**: each CLI subcommand maps to a handler implementing `AbstractHandler.handle()` (src/handlers/).
- **Multi-agent fan-out with bounded concurrency**: `WorkerPool` (semaphore + `asyncio.gather(return_exceptions=True)`) in `AnalyzerAgent.run`; plain `asyncio.gather` in `AIRulesGeneratorAgent.run`.
- **Factory-style lazy construction via properties**: agents and models are built on access (`AnalyzerAgent._structure_analyzer_agent`, `_llm_model`, `AIRulesGeneratorAgent._markdown_agent`, etc.) — each access produces a fresh configured `Agent`/model pair.
- **Template Method-like agent execution**: a shared `_run_agent(...)` in each agent class encapsulates run/measure/log/persist; per-agent variation lives in prompts and output types.
- **Mixin configuration composition**: handler configs multiply-inherit Pydantic models to fuse CLI/base concerns with agent concerns; the CLI parser is generated reflectively from `model_fields`.
- **Singleton (class-level) logger**: `Logger` (src/utils/logger.py) with `init()` then class-method `info/debug/warning/error/critical` accepting a structured `data` dict.
- **Retry layering**: HTTP-level (tenacity transport in `create_retrying_client`: retries 429/502/503/504 and connection errors, `Retry-After`-aware, 5 attempts, max 60s per wait, 300s total), agent-level (`retries=config.*_AGENT_RETRIES`, default 2), tool-level (`ModelRetry` + `max_retries`, default 2).
- **Graceful degradation / partial success**: `AnalyzerAgent.validate_succession` distinguishes complete failure (raise `ValueError`) from partial success (warn and continue); cronjob isolates per-project failures.
- **Externalized prompts (strategy-as-data)**: all agent behavior differences are YAML/Jinja2 prompt templates, not code branches.
- **Guaranteed cleanup**: try/finally around clone→analyze→MR→cleanup in `JobAnalyzeHandler._handle_project`.

## Component Relationships

```
src/main.py
  ├── load_config (src/config.py) ── merge_dicts (src/utils/dict.py)
  ├── Logger.init (src/utils/logger.py)
  ├── configure_langfuse (logfire → OTLP/Langfuse)
  ├── AnalyzeHandler ─────── AnalyzerAgent ──┬── 5 × pydantic-ai Agent
  ├── ReadmeHandler ──────── DocumenterAgent ┤       tools: FileReadTool + ListFilesTool (analyzers);
  ├── AIRulesHandler ─────── AIRulesGeneratorAgent ──┘  FileReadTool only (documenter, ai-rules)
  └── JobAnalyzeHandler ──┬─ Gitlab client (python-gitlab)
                          ├─ git.Repo (GitPython clone/commit/push)
                          └─ AnalyzeHandler (reused per project)

Agents ── PromptManager (src/utils/prompt_manager.py) ── src/agents/prompts/*.yaml
Agents ── OpenAIChatModel + OpenAIProvider ── create_retrying_client (src/utils/retry_client.py)
AnalyzerAgent ── WorkerPool (src/utils/worker_pool.py)
Handlers ── get_repo_version (src/utils/repo.py) ── OTel span attributes
```

Data dependencies between workflows: `analyze` produces `.ai/docs/*.md`; `generate readme` consumes them as prompt context (paths listed by `DocumenterAgent._render_prompt`, contents read by the agent's `FileReadTool`); `generate ai-rules` reads their full contents (`_read_analysis_files`) and fails fast if the three required files are absent. The `skills/` directory replicates the same pipeline for Claude Code (analyze-codebase → generate-readme / generate-ai-rules).

## Key Methods & Functions

- `src/main.py:main()` / `cli_main()` — async entry, command dispatch via `match`.
- `src/main.py:parse_args()`, `add_handler_args()`, `_add_field_arg()` — reflective CLI generation from Pydantic `model_fields` (booleans become `store_true` with `default=None` so "not specified" is distinguishable and YAML values are not clobbered).
- `src/config.py:load_config(args, handler_config, file_key)` — defaults → YAML → CLI merge; `load_config_from_file()` (dot-key section extraction), `load_config_as_dict()` (recursive nested-model extraction).
- `src/handlers/base_handler.py:resolve_default_config_path()`, `BaseHandlerConfig.resolve_config_path()` — repo validation and config discovery.
- `src/agents/analyzer.py:AnalyzerAgent.run()` — builds a task dict of `partial(self._run_agent, ...)`, executes through `WorkerPool`, logs per-agent outcome, then `validate_succession()`.
- `src/agents/analyzer.py:AnalyzerAgent._run_agent()` — runs a pydantic-ai agent, logs token usage/timing, writes the output file; `_cleanup_output()` strips absolute paths for portability.
- `src/agents/analyzer.py:AnalyzerAgent._render_prompt()` — injects `repo_path` and a pre-computed repo tree (direct `ListFilesTool()._run(...)` call) into prompt templates.
- `src/agents/documenter.py:DocumenterAgent.run()` / `_render_prompt()` — README generation; injects the `available_ai_docs` list and `ReadmeConfig` flags into the Jinja2 template.
- `src/agents/ai_rules_generator.py:AIRulesGeneratorAgent.run()` — skip/read existing files (including legacy `.cursorrules`), concurrent markdown+cursor generation, `_write_files()`; `_verify_analysis_files()` enforces the analyze-first precondition; `_write_files()` synthesizes `.mdc` frontmatter and validates the `AGENTS.md` line count against `max_agents_lines`.
- `src/agents/tools/file_tool/file_reader.py:FileReadTool._run(file_path, line_number=0, line_count=200)` — ranged file reads; `ModelRetry` on missing file / permission errors.
- `src/agents/tools/dir_tool/list_files.py:ListFilesTool._run(directory)` — recursive listing filtered by `DEFAULT_IGNORED_DIRS` and ignored extensions; also invoked directly (non-LLM) in `AnalyzerAgent._render_prompt`.
- `src/utils/worker_pool.py:WorkerPool.run(tasks)` — semaphore-bounded concurrent execution returning results or exceptions in input order.
- `src/utils/retry_client.py:create_retrying_client()` — httpx `AsyncClient` with `AsyncTenacityTransport` retry logic.
- `src/utils/prompt_manager.py:PromptManager.render_prompt()` — dot-notation YAML prompt lookup + cached Jinja2 rendering.
- `src/utils/repo.py:get_repo_version()` — `{branch}@{short_commit}` for tracing.
- `src/handlers/cronjob.py:JobAnalyzeHandler._is_applicable_project()`, `_handle_project()`, `_clone_project()`, `_analyze_project()`, `_create_merge_request()`, `_cleanup_project()`, `_get_branch_name()` — the full GitLab automation pipeline.

## Available Documentation

- `README.md` — comprehensive project README: features, architecture, usage, configuration. High quality; reflects the current CLI surface.
- `CLAUDE.md` — detailed AI-assistant guide: commands, code style, architecture overview, gotchas, known limitations. High quality, but its directory listing references `src/utils/custom_models/` (custom Gemini provider) which does not exist in this checkout — the current code constructs models exclusively via `OpenAIChatModel`/`OpenAIProvider` (src/agents/analyzer.py, documenter.py, ai_rules_generator.py).
- `AGENTS.md` — condensed agent-facing conventions file. Accurate and concise.
- `.cursor/rules/project-overview.mdc`, `.cursor/rules/code-patterns.mdc`, `.cursor/rules/agent-development.mdc` — Cursor rules (self-generated by this tool); good summaries of patterns and agent-development workflow.
- `.ai/docs/structure_analysis.md` (this file), `.ai/docs/dependency_analysis.md`, `.ai/docs/data_flow_analysis.md`, `.ai/docs/request_flow_analysis.md`, `.ai/docs/api_analysis.md` — machine-readable analysis documents consumed by the documenter and AI-rules generators.
- `skills/analyze-codebase/SKILL.md` (+ `references/structure-analyzer.md`, `dependency-analyzer.md`, `data-flow-analyzer.md`, `request-flow-analyzer.md`, `api-analyzer.md`), `skills/generate-readme/SKILL.md`, `skills/generate-ai-rules/SKILL.md` — Claude Code skill instructions mirroring the agent prompts; authoritative descriptions of each analysis type's expected output format.
- `config_example.yaml`, `.env.sample` — configuration references for YAML sections (`analyzer`, `generate.readme`, `generate.ai_rules`, `cronjob.analyze`) and required environment variables.
- `k8s/helm/values.yaml`, `k8s/helm/templates/cronjob.yaml` — deployment configuration for the scheduled GitLab automation.

Overall documentation quality is high and largely self-generated by the tool; the only notable drift is the `custom_models`/Gemini references in `CLAUDE.md` versus the OpenAI-provider-only code present in this repository.

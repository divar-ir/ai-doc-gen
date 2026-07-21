# AI Documentation Generator

Multi-agent Python CLI tool that analyzes codebases and generates documentation: `.ai/docs/*.md` analyses, README.md, and AI assistant config files (CLAUDE.md, AGENTS.md, .cursor/rules/).

## Build & Test

```bash
# Install dependencies (Python 3.13 required, <3.14)
uv sync

# Run analysis (writes .ai/docs/*.md)
uv run src/main.py analyze --repo-path .

# Generate README
uv run src/main.py generate readme --repo-path .

# Generate AI assistant config files (CLAUDE.md, AGENTS.md, .cursor/rules/)
uv run src/main.py generate ai-rules --repo-path .

# GitLab batch mode
uv run src/main.py cronjob analyze --max-days-since-last-commit 14

# Format and lint (run both before submitting)
uv run ruff format src/
uv run ruff check src/
```

Setup: `cp .env.sample .env` (fill in LLM keys), optionally `cp config_example.yaml .ai/config.yaml`.

## Architecture

- **Multi-agent system**: 5 analysis agents (structure, dependencies, data flow, request flow, API) run through a `WorkerPool` (`src/utils/worker_pool.py`, concurrency from `ANALYZER_MAX_WORKERS`, 0 = CPU count); 2 AI-rules generators (markdown + cursor) run via `asyncio.gather(return_exceptions=True)`.
- **Handler pattern**: each CLI command maps to a handler in `src/handlers/` implementing `AbstractHandler.handle()`; handler configs subclass `BaseHandlerConfig` + the agent config (e.g., `AnalyzeHandlerConfig(BaseHandlerConfig, AnalyzerAgentConfig)`).
- **Tool-based agents**: pydantic-ai agents with `FileReadTool` and `ListFilesTool` (`src/agents/tools/`); prompts are Jinja2 templates in `src/agents/prompts/*.yaml`.
- **Configuration hierarchy**: Pydantic defaults → `.ai/config.yaml` → CLI arguments (`merge_dicts()`); secrets come from `.env` via module-level constants in `src/config.py`.
- **LLM providers**: OpenAI-compatible only (`OpenAIChatModel` + `OpenAIProvider` with base URL override). Three env config sets: `ANALYZER_LLM_*`, `DOCUMENTER_LLM_*`, `AI_RULES_LLM_*` (AI_RULES falls back to DOCUMENTER values).

**Tech stack**: Python 3.13, pydantic-ai, GitPython, python-gitlab, logfire/OpenTelemetry, Jinja2.

Also in this repo: `skills/` (Claude Code skills mirroring the agents: analyze-codebase, generate-readme, generate-ai-rules) and `.claude-plugin/` (plugin manifest). Keep skill instructions in sync with agent prompt changes.

## Code Style

- **Formatter/linter**: Ruff (120-char lines, 4-space indent, `target-version = "py313"`, import sorting enabled)
- **Type hints**: Pydantic models for all config/data structures; config classes end in `Config`
- **Async/await**: all agent operations are async
- **Naming**: snake_case files/functions, PascalCase classes, `_private` methods, UPPER_SNAKE constants
- **Error handling**: graceful degradation — partial success is acceptable; raise `ModelRetry` inside tools to trigger pydantic-ai retries; log errors with `exc_info=True`

## Testing

No automated tests. Verify changes manually:
```bash
uv run src/main.py analyze --repo-path /path/to/test/repo
uv run src/main.py analyze --repo-path . --exclude-data-flow --exclude-api-analysis
uv run src/main.py generate readme --repo-path . --use-existing-readme
uv run src/main.py generate ai-rules --repo-path . --skip-existing-claude-md
```

## Git Workflow

- **Branches**: `main` (production), `feature/*`, `fix/*`, `ai-analysis-YYYY-MM-DD` (automated)
- **Commits**: `[Category] Brief description` — categories: `[Feature]`, `[Fix]`/`[BUGFIX]`, `[Refactor]`, `[Docs]`, `[Config]`, `[AI]`
- **PRs**: feature branch → main, run ruff format + check first, squash merge

## Key Conventions & Gotchas

**Configuration**:
- Required env vars (import fails without them): `ANALYZER_LLM_MODEL/BASE_URL/API_KEY`, `DOCUMENTER_LLM_MODEL/BASE_URL/API_KEY`
- Config path resolution: `--config` flag, else `.ai/config.yaml`, else `.ai/config.yml`; missing config returns empty dict (no failure)
- Nested YAML keys per command section (e.g., `readme.exclude_architecture`); CLI flags are `--exclude-*` store_true

**Agent execution**:
- Individual agent failures are logged but don't stop others; run fails only if ALL agents fail (ValueError)
- Retries: `*_AGENT_RETRIES` (default 2) per agent + 5 HTTP retries with exponential backoff (`src/utils/retry_client.py`, honors Retry-After, retries 429)
- Temperature 0.0, max tokens 8192 (16384 for cursor rules), timeouts 180s (240s for ai-rules)
- Absolute paths in agent output are replaced with `.` for portability

**Tools**:
- `FileReadTool._run()`: reads 200 lines by default, `line_number`/`line_count` for ranges; raises `ModelRetry` on missing files/permission errors
- `ListFilesTool`: recursive listing with 100+ ignore patterns

**GitLab cronjob**:
- Branch `ai-analysis-{YYYY-MM-DD}`, commit `[AI] Analyzer-Agent: Create/Update AI Analysis [skip ci]`
- Skips archived projects, stale repos, and projects with existing branch/MR; processes projects sequentially; cleanup in try-finally

**Observability**:
- Langfuse optional (`ENABLE_LANGFUSE=false` to disable); OpenTelemetry instruments pydantic-ai + httpx
- Logs: `.logs/{repo_name}/{YYYY_MM_DD}/{timestamp}.log` (file INFO, console WARNING); `Logger.init()` must run before use (singleton)

## Common Issues

- Import errors → `uv sync`; KeyError on startup → missing required env vars in `.env`
- Timeouts → raise `ANALYZER_LLM_TIMEOUT` / `DOCUMENTER_LLM_TIMEOUT` / `AI_RULES_LLM_TIMEOUT`
- Rate limiting → handled automatically (backoff + Retry-After); partial analysis → check logs, rerun

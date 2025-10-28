# AI Documentation Generator

Multi-agent Python CLI tool that analyzes codebases and generates comprehensive documentation using specialized AI agents.

## Build & Test

```bash
# Install dependencies
uv sync

# Run analysis
uv run src/main.py analyze --repo-path .

# Generate README
uv run src/main.py generate readme --repo-path .

# Generate AI assistant config files (CLAUDE.md, AGENTS.md, .cursor/rules/)
uv run src/main.py generate ai-rules --repo-path .

# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/
```

## Architecture

- **Multi-Agent System**:
  - 5 concurrent analysis agents (structure, dependencies, data flow, request flow, API)
  - 2 concurrent generation agents (markdown generator, cursor rules generator)
- **Handler Pattern**: Commands implement `AbstractHandler` with `handle()` method
- **Tool-Based Agents**: Pydantic-AI agents with `FileReadTool` and `ListFilesTool`
- **Configuration Hierarchy**: Pydantic defaults → YAML file → CLI arguments
- **Async Execution**: `asyncio.gather()` for concurrent agent execution with error isolation

**Tech Stack**: Python 3.13, pydantic-ai, OpenAI-compatible APIs, GitPython, python-gitlab, OpenTelemetry

## Code Style

- **Formatter**: Ruff (120 char lines, 4-space indent)
- **Type Hints**: Pydantic models for all config/data structures
- **Async/Await**: All agent operations are async
- **Naming**: Snake case files/functions, Pascal case classes, `_private` methods
- **Error Handling**: Graceful degradation, partial success acceptable, `ModelRetry` for tool errors

## Testing

No automated tests currently. Manual testing:
```bash
# Test analysis
uv run src/main.py analyze --repo-path /path/to/test/repo

# Test with exclusions
uv run src/main.py analyze --repo-path . --exclude-data-flow

# Test README generation
uv run src/main.py generate readme --repo-path . --use-existing-readme

# Test AI rules generation (skip existing files)
uv run src/main.py generate ai-rules --repo-path . --skip-existing-claude-md

# Test GitLab integration
uv run src/main.py cronjob analyze --max-days-since-last-commit 7
```

## Git Workflow

**Branches**: `main` (production), `feature/*`, `fix/*`, `ai-analysis-YYYY-MM-DD` (automated)

**Commits**: `[Category] Brief description` (Categories: Feature, Fix, Refactor, Docs, Config, AI)

**PRs**: Feature branch → main, squash merge, run ruff before submitting

## Key Conventions

**Configuration**:
- Environment variables in `.env` (API keys, tokens)
- Project config in `.ai/config.yaml` (analysis settings)
- CLI args override YAML, YAML overrides env defaults

**File Structure**:
- `src/handlers/` - Command handlers (analyze, readme, ai_rules, cronjob)
- `src/agents/` - AI agents (analyzer, documenter, ai_rules_generator) + prompts + tools
- `src/utils/` - Shared utilities (logger, retry client, prompt manager)

**Agent Execution**:
- 5 agents run concurrently via `asyncio.gather(return_exceptions=True)`
- Individual failures logged but don't stop others
- Partial success valid if ≥1 agent succeeds
- Output: `.ai/docs/*.md` (structure, dependencies, data flow, request flow, API)

**Tools**:
- `FileReadTool`: Read files with line ranges (default 200 lines)
- `ListFilesTool`: Recursive listing with 100+ ignore patterns
- Both retry 2 times on `ModelRetry` exceptions

**LLM Settings**:
- Temperature: 0.0 (deterministic)
- Max tokens: 8192
- Timeout: 180s
- Retries: 2 per agent + 5 HTTP retries with exponential backoff

**GitLab Integration**:
- Branch: `ai-analysis-{YYYY-MM-DD}`
- Commit: `[AI] Analyzer-Agent: Create/Update AI Analysis [skip ci]`
- Filters: Not archived, recent activity, no existing branch/MR
- Error isolation: Individual project failures don't stop batch

**Logging**:
- Location: `.logs/{repo_name}/{YYYY_MM_DD}/{timestamp}.log`
- File: INFO level, Console: WARNING level
- Structured data via ujson

## Common Issues

- **Import errors**: Run `uv sync`
- **API key errors**: Check `.env` has correct keys (no quotes)
- **Config not found**: Ensure `.ai/config.yaml` exists or use `--config`
- **Permission denied**: Check write permissions for `.ai/docs/` and `README.md`
- **Timeout errors**: Increase `*_LLM_TIMEOUT` in `.env`
- **Partial analysis**: Check logs for agent failures, rerun to retry
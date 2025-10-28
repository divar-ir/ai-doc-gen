# CLAUDE.md - AI Documentation Generator

## Project Overview

The AI Documentation Generator is a Python CLI tool that uses multi-agent AI to automatically analyze codebases and generate comprehensive documentation. It employs 5 specialized AI agents running concurrently to analyze code structure, dependencies, data flow, request flow, and APIs, then synthesizes results into professional README files and AI assistant configuration files (CLAUDE.md, AGENTS.md, .cursor/rules/). The system integrates with GitLab for automated project discovery and merge request creation.

## Common Commands

### Development & Testing
```bash
# Install dependencies with uv (recommended)
uv sync

# Run analysis on current repository
uv run src/main.py analyze --repo-path .

# Generate README documentation
uv run src/main.py generate readme --repo-path .

# Generate AI assistant configuration files (CLAUDE.md, AGENTS.md, .cursor/rules/)
uv run src/main.py generate ai-rules --repo-path .

# Run with specific exclusions
uv run src/main.py analyze --repo-path . --exclude-data-flow --exclude-api-analysis

# Generate README with custom sections
uv run src/main.py generate readme --repo-path . --exclude-c4-model --use-existing-readme

# Generate AI rules with skip flags
uv run src/main.py generate ai-rules --repo-path . --skip-existing-claude-md --skip-existing-agents-md

# GitLab cronjob (automated batch processing)
uv run src/main.py cronjob analyze --max-days-since-last-commit 14

# Run with custom config
uv run src/main.py analyze --repo-path /path/to/project --config /path/to/config.yaml

# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/

# Interactive Python shell with project context
uv run ipython
```

### Configuration Setup
```bash
# Copy environment template
cp .env.sample .env

# Edit environment variables (LLM API keys, GitLab tokens, etc.)
vim .env

# Copy configuration template
mkdir -p .ai
cp config_example.yaml .ai/config.yaml

# Edit configuration (analysis exclusions, README sections, AI rules options, etc.)
vim .ai/config.yaml
```

## Code Style & Conventions

### Python Style
- **Python Version**: 3.13 (strict requirement)
- **Formatter**: Ruff with 120 character line length, 4-space indentation
- **Type Hints**: Use Pydantic models for all configuration and data structures
- **Async/Await**: All agent operations are async - use `await` consistently
- **Imports**: Ruff auto-sorts imports (I rule enabled)

### Naming Conventions
- **Files**: Snake case (`analyzer.py`, `file_reader.py`)
- **Classes**: Pascal case (`AnalyzerAgent`, `FileReadTool`)
- **Functions/Methods**: Snake case (`load_config()`, `_run_agent()`)
- **Private Methods**: Prefix with underscore (`_cleanup_output()`, `_render_prompt()`)
- **Constants**: Upper snake case (`ANALYZER_LLM_MODEL`, `COMMIT_MESSAGE_TITLE`)
- **Config Classes**: Suffix with `Config` (`AnalyzerAgentConfig`, `ReadmeConfig`)

### Architecture Patterns
- **Handler Pattern**: All commands implement `AbstractHandler` with `handle()` method
- **Multi-Agent Pattern**: Concurrent execution via `asyncio.gather(return_exceptions=True)`
- **Tool Pattern**: Pydantic-AI tools with `_run()` method and `ModelRetry` for errors
- **Configuration Pattern**: Hierarchical merging (defaults → YAML → CLI args)
- **Singleton Logger**: Class-level `Logger` with `init()` before use

### Error Handling
- **Graceful Degradation**: Partial success is acceptable (log warnings, continue)
- **Error Isolation**: Individual agent failures don't stop others
- **Retry Logic**: 2 retries per agent, 5 retries for HTTP with exponential backoff
- **ModelRetry**: Use `ModelRetry` exception in tools to trigger pydantic-ai retries
- **Logging**: Always log errors with `exc_info=True` for stack traces

### Configuration Management
- **Environment Variables**: All sensitive data (API keys, tokens) in `.env`
- **YAML Config**: Project-specific settings in `.ai/config.yaml`
- **Precedence**: Pydantic defaults < YAML file < CLI arguments
- **Validation**: Pydantic models validate all configuration with custom validators
- **Path Resolution**: `BaseHandlerConfig` auto-resolves config paths

## Repository Conventions

### Branch Strategy
- **Main Branch**: `main` - production-ready code
- **Feature Branches**: `feature/description` - new features
- **Fix Branches**: `fix/description` - bug fixes
- **Analysis Branches**: `ai-analysis-YYYY-MM-DD` - automated analysis results

### Commit Messages
- **Format**: `[Category] Brief description`
- **Categories**: `[Feature]`, `[Fix]`, `[Refactor]`, `[Docs]`, `[Config]`, `[AI]`
- **AI Commits**: `[AI] Analyzer-Agent: Create/Update AI Analysis [skip ci]`
- **Examples**:
  - `[Feature] Add Gemini provider support`
  - `[Fix] Handle missing config files gracefully`
  - `[Refactor] Extract retry logic to utility`

### Pull Request Process
1. Create feature branch from `main`
2. Implement changes with tests
3. Run `ruff format` and `ruff check`
4. Update documentation if needed
5. Create PR with clear description
6. Address review comments
7. Squash merge to `main`

### Directory Structure
```
src/
├── main.py                    # CLI entry point
├── config.py                  # Configuration management
├── handlers/                  # Command handlers
│   ├── base_handler.py       # Abstract handler interface
│   ├── analyze.py            # Analysis orchestration
│   ├── readme.py             # README generation
│   ├── ai_rules.py           # AI rules generation (CLAUDE.md, AGENTS.md, .cursor/rules/)
│   └── cronjob.py            # GitLab automation
├── agents/                    # AI agents
│   ├── analyzer.py           # Multi-agent analyzer (5 concurrent agents)
│   ├── documenter.py         # README generator
│   ├── ai_rules_generator.py # AI rules generator (concurrent markdown + cursor)
│   ├── prompts/              # YAML prompt templates
│   │   ├── analyzer.yaml     # Analyzer prompts
│   │   ├── documenter.yaml   # README generation prompts
│   │   └── ai_rules_generator.yaml  # AI rules generation prompts
│   └── tools/                # Agent tools
│       ├── file_tool/        # File reading
│       └── dir_tool/         # Directory listing
└── utils/                     # Shared utilities
    ├── logger.py             # Structured logging
    ├── prompt_manager.py     # Template management
    ├── retry_client.py       # HTTP retry logic
    ├── repo.py               # Git utilities
    └── custom_models/        # Custom LLM providers
```

## Architecture Overview

### Multi-Agent System
The core architecture uses **multiple specialized AI agents** running concurrently:

**Analysis Agents (5 concurrent):**
1. **Structure Analyzer**: Architectural patterns, components, design decisions
2. **Dependency Analyzer**: Internal/external dependencies, service integrations
3. **Data Flow Analyzer**: Data transformations, persistence patterns
4. **Request Flow Analyzer**: Request handling, routing, middleware
5. **API Analyzer**: Endpoints, integrations, protocols

**Generation Agents:**
- **README Generator**: Single agent for comprehensive README.md
- **AI Rules Generators (2 concurrent)**:
  - **Markdown Generator**: Creates CLAUDE.md and AGENTS.md in one pass
  - **Cursor Rules Generator**: Creates .cursor/rules/*.mdc files

Each agent:
- Runs independently with error isolation
- Has access to `FileReadTool` and `ListFilesTool`
- Uses same LLM model but different system prompts
- Writes output to appropriate location (.ai/docs/, root, .cursor/rules/)
- Retries up to 2 times on failure

### Request Flow
```
CLI Command (analyze, generate {readme|ai-rules}, cronjob)
    ↓
main.py (parse_args, configure_logging, configure_langfuse)
    ↓
Handler (AnalyzeHandler, ReadmeHandler, AIRulesHandler, JobAnalyzeHandler)
    ↓
Agent (AnalyzerAgent, DocumenterAgent, AIRulesGeneratorAgent)
    ↓
LLM Provider (OpenAI/Gemini) + Tools (FileReadTool, ListFilesTool)
    ↓
Result Files (.ai/docs/*.md, README.md, CLAUDE.md, AGENTS.md, .cursor/rules/*.mdc)
```

### Configuration Flow
```
Environment Variables (.env)
    ↓
YAML Config (.ai/config.yaml)
    ↓
CLI Arguments (--flag-name)
    ↓
merge_dicts() (CLI overrides YAML overrides env)
    ↓
Pydantic Validation
    ↓
Handler Config Object
```

### Key Components

**Handlers** (`src/handlers/`):
- Implement `AbstractHandler` interface with `handle()` method
- Create and execute agents with OpenTelemetry tracing
- Handle configuration loading and validation
- Manage file output and cleanup

**Agents** (`src/agents/`):
- `AnalyzerAgent`: Coordinates 5 concurrent analysis agents
- `DocumenterAgent`: Generates README from analysis results
- `AIRulesGeneratorAgent`: Coordinates 2 concurrent AI rules generators (markdown + cursor)
- All use pydantic-ai framework with tool registration
- Temperature 0.0 for deterministic output
- Configurable max tokens and timeout per agent type

**Tools** (`src/agents/tools/`):
- `FileReadTool`: Read files with line range support (default 200 lines)
- `ListFilesTool`: Recursive directory listing with 100+ ignore patterns
- Both implement retry logic with `ModelRetry` exceptions
- Registered with agents during initialization

**Utilities** (`src/utils/`):
- `Logger`: Singleton with file + console handlers, structured logging
- `PromptManager`: YAML-based Jinja2 template management with caching
- `retry_client`: HTTP client with exponential backoff (5 attempts, 60s max)
- `repo.py`: Git version detection (`{branch}@{commit}`)

## Development Gotchas

### Environment Setup
- **Python 3.13 Required**: Project uses `requires-python = ">=3.13,<3.14"`
- **uv Recommended**: Use `uv sync` instead of pip for faster installs
- **Environment Variables**: Copy `.env.sample` to `.env` and fill in API keys
- **LLM API Keys**: Need both `ANALYZER_LLM_API_KEY` and `DOCUMENTER_LLM_API_KEY`
- **GitLab Token**: Required for cronjob command (`GITLAB_OAUTH_TOKEN`)

### Configuration Pitfalls
- **Config Path Resolution**: If no `--config` specified, looks for `.ai/config.yaml` then `.ai/config.yml`
- **Nested Config Keys**: Use dot notation in YAML (e.g., `readme.exclude_architecture`)
- **Boolean Flags**: CLI flags use `--exclude-*` format (store_true action)
- **Path Fields**: Automatically converted to `Path` objects by Pydantic
- **Missing Config**: Returns empty dict (graceful), doesn't fail

### Agent Execution
- **Concurrent Execution**: Agents run in parallel via `asyncio.gather()`
- **Error Isolation**: Individual agent failures logged but don't stop others
- **Partial Success**: Valid if at least one agent succeeds (logs warning)
- **Complete Failure**: Only fails if ALL agents fail (raises ValueError)
- **Output Cleanup**: Absolute paths replaced with "." for portability

### Tool Usage
- **File Reading**: Default 200 lines per read, use `line_number` and `line_count` for ranges
- **Directory Listing**: Automatically filters 100+ ignored dirs/extensions
- **Retry Behavior**: Tools retry 2 times on `ModelRetry` exceptions
- **Permission Errors**: Raise `ModelRetry` to trigger automatic retry
- **File Not Found**: Also raises `ModelRetry` for retry

### LLM Integration
- **OpenAI-Compatible**: Works with OpenAI, OpenRouter, local models, etc.
- **Gemini Support**: Custom provider with base URL override
- **Provider Selection**: Automatic based on model name (contains "gemini")
- **Retry Logic**: 2 agent-level retries + 5 HTTP-level retries
- **Timeout**: 180s per request (configurable)
- **Rate Limiting**: Respects Retry-After headers, exponential backoff

### GitLab Integration
- **Project Filtering**: Checks archived status, subgroups, commit history, existing branches/MRs
- **Branch Naming**: `ai-analysis-{YYYY-MM-DD}` format
- **Commit Message**: `[AI] Analyzer-Agent: Create/Update AI Analysis [skip ci]`
- **Skip CI**: Always includes `[skip ci]` to avoid triggering pipelines
- **Cleanup**: Guaranteed via try-finally blocks
- **Error Isolation**: Individual project failures don't stop batch

### Observability
- **Langfuse Optional**: Set `ENABLE_LANGFUSE=false` to disable
- **OpenTelemetry**: Automatic instrumentation of pydantic-ai and httpx
- **Span Attributes**: Include repo_path, version, config flags, token usage
- **Logging**: Separate file (INFO) and console (WARNING) handlers
- **Log Location**: `.logs/{repo_name}/{YYYY_MM_DD}/{timestamp}.log`

### Common Issues
- **Import Errors**: Run `uv sync` to ensure all dependencies installed
- **API Key Errors**: Check `.env` file has correct keys (no quotes needed)
- **Config Not Found**: Ensure `.ai/config.yaml` exists or use `--config` flag
- **Permission Denied**: Check write permissions for `.ai/docs/` and `README.md`
- **Timeout Errors**: Increase `ANALYZER_LLM_TIMEOUT` or `DOCUMENTER_LLM_TIMEOUT`
- **Rate Limiting**: Automatic retry with exponential backoff, but may need to wait
- **Partial Analysis**: Check logs for individual agent failures, may need to rerun

## Known Issues

### Current Limitations
- **No Database**: All state is ephemeral, no persistence between runs
- **No Caching**: Analysis results not cached, full reanalysis each run
- **Sequential Cronjob**: Projects processed one at a time (no parallelization)
- **No Incremental Analysis**: Always analyzes entire repository
- **Limited Language Support**: Optimized for Python, may need prompt tuning for other languages
- **Token Limits**: 8192 max tokens may be insufficient for very large files
- **No Diff Analysis**: Doesn't analyze only changed files

### Workarounds
- **Large Repositories**: Use exclusion flags to skip unnecessary analyses
- **Token Limits**: Tools read 200 lines at a time, agents can make multiple calls
- **Rate Limiting**: Automatic retry with exponential backoff handles most cases
- **GitLab Timeouts**: Cronjob processes projects sequentially to avoid overwhelming API
- **Missing Analysis**: Partial success is acceptable, rerun to retry failed agents

### Future Improvements
- Incremental analysis (only changed files)
- Result caching for faster reruns
- Parallel cronjob processing
- Support for more LLM providers
- Custom prompt templates per language
- Diff-based analysis for PRs
- Web UI for configuration and monitoring
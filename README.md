# AI Documentation Generator

An AI-powered code documentation generator that automatically analyzes repositories and creates comprehensive documentation using large language models. The system employs a multi-agent architecture: five specialized analysis agents run concurrently to map a codebase's structure, dependencies, data flow, request flow, and APIs, and generation agents turn those analyses into a polished `README.md` and AI assistant configuration files (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/`). A GitLab cronjob mode discovers active projects and opens merge requests with fresh analysis automatically.

## 📝 Blog Posts

Read the full story behind this project:
- 🇺🇸 [English: Docs That Don’t Rot: How Multi-Agent AI Rewrote Our Workflow](https://medium.com/@milad.noroozi/docs-that-dont-rot-how-multi-agent-ai-rewrote-our-workflow-6e0c911658d6)
- 🇮🇷 [از دستیار کدنویس تا همکار هوشمند؛ گام اول: کابوس مستندسازی](https://virgool.io/@divar/%D8%A7%D8%B2-%D8%AF%D8%B3%D8%AA%DB%8C%D8%A7%D8%B1-%DA%A9%D8%AF%D9%86%D9%88%DB%8C%D8%B3-%D8%AA%D8%A7-%D9%87%D9%85%DA%A9%D8%A7%D8%B1-%D9%87%D9%88%D8%B4%D9%85%D9%86%D8%AF-%DA%AF%D8%A7%D9%85-%D8%A7%D9%88%D9%84-%DA%A9%D8%A7%D8%A8%D9%88%D8%B3-%D9%85%D8%B3%D8%AA%D9%86%D8%AF%D8%B3%D8%A7%D8%B2%DB%8C-jx7vhznchc9w)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [License](#license)

## Features

- **Multi-Agent Analysis**: Five specialized AI agents for code structure, data flow, dependency, request flow, and API analysis, writing reusable analysis documents to `.ai/docs/`
- **Automated Documentation**: Generates comprehensive README files with configurable sections
- **AI Assistant Configuration**: Generates `CLAUDE.md`, `AGENTS.md`, and `.cursor/rules/*.mdc` files for AI coding assistants
- **Claude Code Plugin & Skills**: Ships as an installable Claude Code plugin with `analyze-codebase`, `generate-readme`, and `generate-ai-rules` skills (`.claude-plugin/`, `skills/`)
- **GitLab Integration**: Cronjob mode discovers recently active GitLab projects, runs analysis, and opens merge requests
- **Concurrent Processing**: Parallel agent execution with a configurable worker pool (`ANALYZER_MAX_WORKERS`, 0 = auto-detect CPU count)
- **Flexible Configuration**: Layered configuration — Pydantic defaults, `.ai/config.yaml`, then CLI flags
- **Multiple LLM Support**: Works with any OpenAI-compatible API (OpenAI, Anthropic-compatible gateways, OpenRouter, local models, etc.), with per-agent model/endpoint settings
- **Resilience**: Agent-level retries plus an HTTP retry client with exponential backoff and `Retry-After` support (handles 429s)
- **Observability**: OpenTelemetry tracing via logfire with optional Langfuse integration

## Installation

### Using Skills (Claude Code)

This repository doubles as a Claude Code plugin — the easiest way to use it, no API keys or Python setup required. Install it from within Claude Code:

```
/plugin marketplace add divar-ir/ai-doc-gen
/plugin install ai-doc-gen@divar
```

This adds three skills that Claude Code invokes directly:

- `analyze-codebase` — multi-agent analysis producing `.ai/docs/` documents
- `generate-readme` — README generation from analysis or direct exploration
- `generate-ai-rules` — `CLAUDE.md`, `AGENTS.md`, and Cursor rules generation

### Prerequisites

- Python 3.13
- Git
- API access to an OpenAI-compatible LLM provider

1. Clone the repository:
```bash
git clone https://github.com/divar-ir/ai-doc-gen.git
cd ai-doc-gen
```

2. Install using uv (recommended):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

3. Or install with pip:
```bash
pip install -e .
```

A `Dockerfile` and a Helm chart (`k8s/helm/`) are also provided for containerized and scheduled (Kubernetes CronJob) deployments.

## Quick Start

1. Set up your environment and configuration:
```bash
# Copy and edit environment variables (LLM API keys, base URLs, etc.)
cp .env.sample .env

# Copy and edit configuration
mkdir -p .ai
cp config_example.yaml .ai/config.yaml
```

2. Run analysis and generate documentation:
```bash
# Analyze your repository
uv run src/main.py analyze --repo-path .

# Generate README documentation
uv run src/main.py generate readme --repo-path .

# Generate AI assistant configuration files (CLAUDE.md, AGENTS.md, .cursor/rules/)
uv run src/main.py generate ai-rules --repo-path .
```

Analysis documents are saved to `.ai/docs/`, and generated documentation and AI configuration files are placed in your repository root.

## Usage

### Available Commands

```bash
# Analyze codebase (structure, data flow, dependencies, request flow, APIs)
uv run src/main.py analyze --repo-path <path>

# Generate README documentation
uv run src/main.py generate readme --repo-path <path>

# Generate AI assistant configuration files
uv run src/main.py generate ai-rules --repo-path <path>

# Run cronjob (GitLab batch analysis)
uv run src/main.py cronjob analyze
```

The package also installs an `ai-doc-gen` console script exposing the same CLI.

### Advanced Options

**Analysis Options:**
```bash
# Analyze with specific exclusions
uv run src/main.py analyze --repo-path . --exclude-code-structure --exclude-data-flow

# Limit concurrent analyzer agents
uv run src/main.py analyze --repo-path . --max-workers 2

# Use custom configuration file
uv run src/main.py analyze --repo-path . --config /path/to/config.yaml
```

**README Generation Options:**
```bash
# Generate with specific section exclusions
uv run src/main.py generate readme --repo-path . --exclude-architecture --exclude-c4-model

# Use existing README as context
uv run src/main.py generate readme --repo-path . --use-existing-readme
```

**AI Rules Generation Options:**
```bash
# Skip overwriting existing files
uv run src/main.py generate ai-rules --repo-path . \
    --skip-existing-claude-md \
    --skip-existing-agents-md \
    --skip-existing-cursor-rules

# Customize detail level and line limits
uv run src/main.py generate ai-rules --repo-path . \
    --detail-level comprehensive \
    --max-claude-lines 600 \
    --max-agents-lines 150
```

**Cronjob Options:**
```bash
# Only process projects with commits in the last N days
uv run src/main.py cronjob analyze --max-days-since-last-commit 14
```

## Configuration

The tool automatically looks for configuration in `.ai/config.yaml` or `.ai/config.yml` in your repository. Precedence: Pydantic defaults < YAML file < CLI flags.

### Configuration Options

- **Exclude specific analyses**: Skip code structure, data flow, dependencies, request flow, or API analysis
- **Tune concurrency**: `analyzer.max_workers` caps concurrent analyzer agents (0 = auto-detect CPU count)
- **Customize README sections**: Control which sections appear in generated documentation
- **AI rules behavior**: Skip existing files, choose detail level (`minimal`/`standard`/`comprehensive`), set line limits
- **Configure cronjob settings**: Working path and commit recency filter

See [`config_example.yaml`](config_example.yaml) for all available options and [`.env.sample`](.env.sample) for environment variables (per-agent LLM models, timeouts, retry behavior, GitLab credentials, Langfuse keys).

## Architecture

The system uses a **multi-agent architecture** with specialized AI agents for different types of code analysis and generation:

- **CLI Layer** (`src/main.py`): argparse-based entry point; CLI flags are auto-generated from Pydantic config models
- **Handler Layer** (`src/handlers/`): command-specific orchestration implementing an `AbstractHandler` interface (analyze, generate readme, generate ai-rules, cronjob analyze)
- **Agent Layer** (`src/agents/`): pydantic-ai agents with YAML/Jinja2 prompt templates
  - `AnalyzerAgent`: coordinates 5 analysis agents through a worker pool
  - `DocumenterAgent`: generates README.md from analysis documents
  - `AIRulesGeneratorAgent`: generates markdown rules (CLAUDE.md + AGENTS.md) and Cursor rules concurrently
- **Tool Layer** (`src/agents/tools/`): `FileReadTool` (ranged file reading) and `ListFilesTool` (filtered recursive listing) registered with every agent

### Technology Stack

- **Python 3.13** with [pydantic-ai](https://ai.pydantic.dev/) for AI agent orchestration
- **OpenAI-compatible APIs** for LLM access (`OpenAIChatModel` + `OpenAIProvider` with configurable base URL)
- **GitPython & python-gitlab** for repository operations and GitLab automation
- **logfire / OpenTelemetry & Langfuse** for observability
- **YAML + Jinja2 + Pydantic** for prompts and configuration management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [pydantic-ai](https://ai.pydantic.dev/) for AI agent orchestration
- Supports multiple LLM providers through OpenAI-compatible APIs (including OpenRouter)
- Uses [Langfuse](https://langfuse.com/) for LLM observability

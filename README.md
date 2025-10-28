# AI Documentation Generator

An AI-powered code documentation generator that automatically analyzes repositories and creates comprehensive documentation using advanced language models. The system employs a multi-agent architecture to perform specialized code analysis and generate structured documentation.

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

- **Multi-Agent Analysis**: Specialized AI agents for code structure, data flow, dependency, request flow, and API analysis
- **Automated Documentation**: Generates comprehensive README files with configurable sections
- **AI Assistant Configuration**: Automatically generates CLAUDE.md, AGENTS.md, and .cursor/rules/ files for AI coding assistants
- **GitLab Integration**: Automated analysis for GitLab projects with merge request creation
- **Concurrent Processing**: Parallel execution of analysis agents for improved performance
- **Flexible Configuration**: YAML-based configuration with environment variable overrides
- **Multiple LLM Support**: Works with any OpenAI-compatible API (OpenAI, OpenRouter, local models, etc.)
- **Observability**: Built-in monitoring with OpenTelemetry tracing and Langfuse integration

## Installation

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

## Quick Start

1. Set up your environment and configuration:
```bash
# Copy and edit environment variables
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

Generated documentation will be saved to `.ai/docs/` directory, and AI configuration files will be placed in your repository root.

## Usage

### Available Commands

```bash
# Analyze codebase
uv run src/main.py analyze --repo-path <path>

# Generate README documentation
uv run src/main.py generate readme --repo-path <path>

# Generate AI assistant configuration files
uv run src/main.py generate ai-rules --repo-path <path>

# Run cronjob (GitLab integration)
uv run src/main.py cronjob analyze
```

### Advanced Options

**Analysis Options:**
```bash
# Analyze with specific exclusions
uv run src/main.py analyze --repo-path . --exclude-code-structure --exclude-data-flow

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

## Configuration

The tool automatically looks for configuration in `.ai/config.yaml` or `.ai/config.yml` in your repository.

### Configuration Options

- **Exclude specific analyses**: Skip code structure, data flow, dependencies, request flow, or API analysis
- **Customize README sections**: Control which sections appear in generated documentation  
- **Configure cronjob settings**: Set working paths and commit recency filters

You can use CLI flags for quick configuration overrides. See [`config_example.yaml`](config_example.yaml) for all available options and [`.env.sample`](.env.sample) for environment variables.

## Architecture

The system uses a **multi-agent architecture** with specialized AI agents for different types of code analysis and generation:

- **CLI Layer**: Entry point with command parsing and subcommand routing
- **Handler Layer**: Command-specific business logic (analyze, generate, cronjob)
- **Agent Layer**: AI-powered analysis and documentation generation
  - Analyzer agents: Structure, data flow, dependencies, request flow, API analysis
  - Documentation agent: README generation
  - AI Rules generator: CLAUDE.md, AGENTS.md, and Cursor rules generation
- **Tool Layer**: File system operations and utilities

### Technology Stack

- **Python 3.13** with pydantic-ai for AI agent orchestration
- **OpenAI-compatible APIs** for LLM access (OpenAI, OpenRouter, etc.)
- **GitPython & python-gitlab** for repository operations
- **OpenTelemetry & Langfuse** for observability
- **YAML + Pydantic** for configuration management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [pydantic-ai](https://ai.pydantic.dev/) for AI agent orchestration
- Supports multiple LLM providers through OpenAI-compatible APIs (including OpenRouter)
- Uses [Langfuse](https://langfuse.com/) for LLM observability

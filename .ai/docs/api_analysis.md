# API Documentation

## APIs Served by This Project

### Endpoints

**This project exposes no network APIs.** It is a Python CLI application (entry point: `src/main.py`, console script `cli_main()` defined in `pyproject.toml`). There are no HTTP servers, REST/GraphQL/gRPC/WebSocket endpoints, or listening sockets anywhere in `src/`. The only "served" interface is the command-line interface, documented here because it is the sole entry contract.

#### CLI Commands (argparse subcommands, `src/main.py:parse_args()`)

| Command | Handler | Purpose |
|---|---|---|
| `analyze` | `AnalyzeHandler` (`src/handlers/analyze.py`) | Run up to 5 concurrent analysis agents; writes `.ai/docs/{structure,dependency,data_flow,request_flow,api}_analysis.md` |
| `generate readme` | `ReadmeHandler` (`src/handlers/readme.py`) | Generate `README.md` from analysis docs |
| `generate ai-rules` | `AIRulesHandler` (`src/handlers/ai_rules.py`) | Generate `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/*.mdc` |
| `cronjob analyze` | `JobAnalyzeHandler` (`src/handlers/cronjob.py`) | Batch-analyze GitLab group projects and open merge requests |

CLI flags are auto-generated from Pydantic config models via `add_handler_args()` in `src/main.py` (e.g. `--repo-path`, `--exclude-api-analysis`, `--max-workers`, `--use-existing-readme`, `--skip-existing-claude-md`, `--max-days-since-last-commit`, `--working-path`, `--group-project-id`). Configuration precedence (`src/config.py:load_config()`): Pydantic defaults < `.ai/config.yaml` (see `config_example.yaml`) < CLI arguments.

Outputs (the "response contract"): markdown files written to the target repository — `.ai/docs/*.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/*.mdc`. Absolute paths are replaced with `.` for portability (`AnalyzerAgent._cleanup_output()` in `src/agents/analyzer.py`).

Note: `k8s/helm/templates/service.yaml` and `servicemonitor.yaml` define a Kubernetes Service/ServiceMonitor scaffold, but no code in this repository serves a metrics or HTTP port; the workload actually deployed is a CronJob (`k8s/helm/templates/cronjob.yaml`).

### Authentication & Security

Not applicable for inbound traffic (no served endpoints). Secrets are consumed, not issued:

- All credentials are loaded from environment variables via `python-dotenv` in `src/config.py` (`.env`, template in `.env.sample`).
- Required: `ANALYZER_LLM_API_KEY`, `ANALYZER_LLM_BASE_URL`, `ANALYZER_LLM_MODEL`, and `DOCUMENTER_LLM_*` equivalents (hard failures via `os.environ[...]` if unset).
- Optional: `AI_RULES_LLM_*` (falls back to documenter values), `GITLAB_OAUTH_TOKEN`, `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`.

### Rate Limiting & Constraints

The project imposes no rate limits of its own; it defends against upstream limits:

- HTTP 429/502/503/504 retried with `Retry-After` support (`src/utils/retry_client.py`).
- LLM request constraints (env-tunable, `src/config.py`): timeout 180s (analyzer/documenter) / 240s (ai-rules), max tokens 8192 (16384 for cursor rules), temperature 0.0.
- Analyzer concurrency capped by `ANALYZER_MAX_WORKERS` / `--max-workers` via `src/utils/worker_pool.py` (0 = auto-detect CPU count).
- Cronjob processes GitLab projects sequentially (one at a time) to avoid overwhelming the GitLab API.

## External API Dependencies

### Services Consumed

#### 1. LLM Provider APIs (OpenAI-compatible Chat Completions)

- **Purpose**: All agent reasoning — code analysis, README generation, AI-rules generation.
- **Client**: `pydantic-ai` `OpenAIChatModel` + `OpenAIProvider` over a retrying `httpx.AsyncClient`. Three independent provider configurations, all OpenAI-compatible (works with OpenAI, OpenRouter, gateways, local models):
  - Analyzer: `src/agents/analyzer.py` (`AnalyzerAgent._llm_model`) — `ANALYZER_LLM_MODEL` / `ANALYZER_LLM_BASE_URL` / `ANALYZER_LLM_API_KEY`.
  - Documenter: `src/agents/documenter.py` — `DOCUMENTER_LLM_*`.
  - AI Rules: `src/agents/ai_rules_generator.py` (two model instances: markdown + cursor rules) — `AI_RULES_LLM_*`, defaulting to documenter values.
- **Endpoints used**: OpenAI-style `POST {base_url}/chat/completions` (issued internally by pydantic-ai; no hand-written HTTP calls).
- **Authentication**: Bearer API key per provider config.
- **Error handling / retries** (layered):
  1. HTTP layer (`src/utils/retry_client.py:create_retrying_client()`): tenacity-based `AsyncTenacityTransport`; retries `HTTPStatusError` (429 handled via `Retry-After`/`wait_retry_after`, plus explicit 502/503/504 response validation) and `ConnectionError`; exponential backoff (multiplier 1, max 60s per attempt), total wait cap 300s, 5 attempts, reraises last error. `HTTP_RETRY_*` env vars are defined in `src/config.py` and documented in `.env.sample`, but `create_retrying_client()` currently uses hardcoded constants matching the defaults.
  2. Agent layer: `retries=ANALYZER_AGENT_RETRIES` (default 2; same pattern for documenter/ai-rules) on each `pydantic_ai.Agent`.
  3. Tool layer: `FileReadTool` (`src/agents/tools/file_tool/file_reader.py`) and `ListFilesTool` (`src/agents/tools/dir_tool/list_files.py`) raise `ModelRetry` on missing files/permission errors; max retries `TOOL_FILE_READER_MAX_RETRIES` / `TOOL_LIST_FILES_MAX_RETRIES` (default 2).
  4. Orchestration layer: analyzer agents run through `WorkerPool` (`src/utils/worker_pool.py`) with exception isolation; partial success is accepted (`AnalyzerAgent.validate_succession()` in `src/agents/analyzer.py` raises `ValueError` only when ALL analysis files are missing).

#### 2. GitLab REST API (v4)

- **Purpose**: Automated batch analysis — project discovery, applicability checks, merge request creation (cronjob mode only).
- **Client**: `python-gitlab` `Gitlab(url=config.GITLAB_API_URL, oauth_token=config.GITLAB_OAUTH_TOKEN)` constructed in `src/main.py:cronjob_analyze()`; consumed by `JobAnalyzeHandler` in `src/handlers/cronjob.py`.
- **Base URL**: `GITLAB_API_URL` (default `https://git.divar.cloud`).
- **Operations used** (all wrapped by python-gitlab):
  - `groups.get(id)` and `group.projects.list(iterator=True, include_subgroups=True)` — enumerate projects in group `group_project_id` (default 3).
  - `projects.get(id)`, `project.branches.get(default_branch)`, `project.branches.list(search=...)` — applicability checks in `_is_applicable_project()`: archived flag, ignored subgroups/project IDs, last-commit age vs `max_days_since_last_commit` (default 30), existing `ai-analyzer-{YYYY-MM-DD}` branch, prior `[AI] Analyzer-Agent` commit on default branch.
  - `project.mergerequests.list(state="opened", author_username=..., search=...)` — dedupe existing MRs.
  - `project.mergerequests.create({...})` — open MR titled `[AI] Analyzer-Agent: Create/Update AI Analysis for {name} - {date} [skip ci]`.
- **Authentication**: OAuth token (`GITLAB_OAUTH_TOKEN`); requires `api`, `read_repository`, `write_repository` scopes (documented in `.env.sample`).
- **Error handling**: per-project try/except in `JobAnalyzeHandler.handle()` — one project's failure never stops the batch; clone/analyze/MR wrapped in try/finally with guaranteed workspace cleanup (`_cleanup_project()` removes the clone under `working_path`, default `/tmp/cronjob/projects`).

#### 3. Git over HTTPS (GitPython)

- **Purpose**: Clone target repositories, create branch `ai-analyzer-{YYYY-MM-DD}`, commit results with `[skip ci]`, force-push (`src/handlers/cronjob.py:_clone_project()`, `_create_merge_request()`).
- **Endpoint**: `project.http_url_to_repo` returned by the GitLab API.
- Also used read-only by `src/utils/repo.py` to derive the repo version string `{branch}@{commit}` for tracing attributes.

#### 4. Langfuse / OpenTelemetry Collector (optional)

- **Purpose**: LLM observability — traces of pydantic-ai runs and all httpx calls.
- **Configuration**: enabled by `ENABLE_LANGFUSE=true`; `src/main.py:configure_langfuse()` sets `OTEL_EXPORTER_OTLP_HEADERS` to `Authorization=Basic base64(LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY)` and relies on `OTEL_EXPORTER_OTLP_ENDPOINT` (see `.env.sample`).
- **Protocol**: OTLP export via the `logfire` SDK (`send_to_logfire=False`, `service_name="ai-doc-gen"`), with `logfire.instrument_pydantic_ai()` and `logfire.instrument_httpx(capture_all=True)`.
- **Error handling**: fully optional; disabled by default (`ENABLE_LANGFUSE=false`).

### Integration Patterns

- **Provider abstraction**: every LLM integration goes through pydantic-ai's `OpenAIProvider` with an injected retrying `httpx.AsyncClient` — no raw HTTP calls exist in the codebase.
- **Layered resilience**: HTTP retries (tenacity) → tool retries (`ModelRetry`) → agent retries → orchestration-level error isolation with partial-success semantics.
- **Concurrency with isolation**: `WorkerPool` (`src/utils/worker_pool.py`) runs the 5 analyzer agents concurrently and returns exceptions as values; `src/agents/ai_rules_generator.py` runs the markdown and cursor generators concurrently the same way.
- **Deterministic outputs**: temperature 0.0 everywhere; prompts are Jinja2 templates in YAML (`src/agents/prompts/analyzer.yaml`, `documenter.yaml`, `ai_rules_generator.yaml`) rendered by `src/utils/prompt_manager.py`.
- **Idempotent automation**: cronjob skips projects already analyzed (branch/MR/commit-message checks) and always tags commits/MRs with `[skip ci]` to avoid triggering CI pipelines.
- **Tracing**: handlers create OpenTelemetry spans with repo path, version, and config flags (`src/handlers/analyze.py`, `src/handlers/readme.py`, `src/handlers/ai_rules.py`).

## Available Documentation

- `README.md` — project overview, CLI usage, configuration.
- `CLAUDE.md`, `AGENTS.md` — AI-assistant oriented codebase guides (commands, architecture, gotchas).
- `.env.sample` — exhaustive, well-commented catalog of every environment variable, including retry tuning and required GitLab token scopes; the de facto external-integration reference.
- `config_example.yaml` — YAML schema for `.ai/config.yaml` (analyzer exclusions, README sections, AI-rules options, cronjob settings).
- `.ai/docs/` — generated analyses (`structure_analysis.md`, `dependency_analysis.md`, `data_flow_analysis.md`, `request_flow_analysis.md`, `api_analysis.md`).
- No OpenAPI/Swagger, protobuf, or GraphQL schema files exist — consistent with the absence of served network APIs.

**Documentation quality**: high for a CLI tool. Configuration and integration surfaces are thoroughly documented in `.env.sample` and `config_example.yaml`. Main gap: `HTTP_RETRY_*` env vars exist in `src/config.py` but are not wired into `src/utils/retry_client.py`, which uses hardcoded equivalents — the docs imply tunability the code doesn't yet honor.

---
name: analyze-codebase
description: Run a multi-agent deep analysis of a codebase, producing AI-readable analysis documents in .ai/docs/ covering structure, dependencies, data flow, request flow, and APIs. Use whenever the user asks to analyze a repository, generate codebase analysis, understand an unfamiliar codebase in depth, or before generating documentation (README, CLAUDE.md, AGENTS.md) so the generators have analysis data to work from. Also use when the user mentions ".ai/docs", "ai analysis", or wants a structured architectural map of a project.
---

# Analyze Codebase

Produce five AI-readable analysis documents by running specialized analyzers **in parallel**, each writing to `.ai/docs/` in the target repository. These documents are the input for the `generate-readme` and `generate-ai-rules` skills, and are valuable on their own as machine-readable architecture maps.

## Workflow

### 1. Determine scope

- Target repository: the current working directory unless the user names another path.
- Which analyses to run: all five by default. The user may exclude some (e.g., "skip the data flow analysis"). For projects with no meaningful API surface or request handling (pure libraries, simple scripts), suggest skipping the API and request-flow analyzers, but let the user decide.

| Analyzer | Reference file | Output file |
|---|---|---|
| Structure | `references/structure-analyzer.md` | `.ai/docs/structure_analysis.md` |
| Dependencies | `references/dependency-analyzer.md` | `.ai/docs/dependency_analysis.md` |
| Data flow | `references/data-flow-analyzer.md` | `.ai/docs/data_flow_analysis.md` |
| Request flow | `references/request-flow-analyzer.md` | `.ai/docs/request_flow_analysis.md` |
| API | `references/api-analyzer.md` | `.ai/docs/api_analysis.md` |

### 2. Run the analyzers in parallel

Create `.ai/docs/` in the target repo if it doesn't exist. Then spawn one subagent per selected analyzer, **all in a single message** so they run concurrently. Each subagent prompt should say:

> Read the instructions at `<absolute path to this skill's references/<analyzer>.md>` and follow them exactly for the repository at `<absolute repo path>`. Explore the codebase with your file tools as needed. Write your complete analysis to `<absolute repo path>/.ai/docs/<output file>`, following the exact output format in the instructions. In the written file, refer to files by repo-relative paths (e.g. `src/main.py`, not absolute paths) so the document is portable. Return a one-paragraph summary of what you found.

Failures are isolated: if one analyzer fails, the others' results still count. Retry a failed analyzer once; if it fails again, note it in the final report and move on. Only treat the run as failed if every analyzer fails.

### 3. Verify and report

After all subagents finish:

1. Confirm each expected output file exists and is non-trivial (has content under its section headings, not just the skeleton).
2. Check that no absolute local paths leaked into the documents; replace any with repo-relative paths.
3. Report to the user: which analyses succeeded, where the files are, and a short synthesis of the most important findings. Suggest `generate-readme` or `generate-ai-rules` as natural next steps.

## Notes

- Analysis documents are optimized for AI consumption, not human reading — that's intentional. Human-facing output comes from the generator skills.
- Recommend adding `.ai/docs/` to the repo (committed, not ignored) so future AI sessions and teammates benefit; but respect the project's existing convention if `.ai/` is gitignored.

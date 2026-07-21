---
name: generate-ai-rules
description: Generate AI assistant configuration files for a repository — CLAUDE.md, AGENTS.md, and Cursor rules (.cursor/rules/*.mdc) — from codebase analysis. Use whenever the user wants to create or update CLAUDE.md, AGENTS.md, agent rules, Cursor rules, AI coding assistant configuration, or "onboard AI tools" to a project, even if they only mention one of the file types.
---

# Generate AI Rules

Generate configuration files that help AI coding assistants work effectively with a codebase. Three targets, generated from the same analysis so they stay consistent:

1. **AGENTS.md** — the cross-tool standard (agents.md), read by most AI coding tools including Claude Code, Cursor, Codex, and Gemini CLI.
2. **CLAUDE.md** — Claude Code's project instructions file.
3. **.cursor/rules/*.mdc** — Cursor's scoped project rules.

## Workflow

### 1. Determine targets and gather data

- Generate all three targets by default; the user may skip any (e.g., "skip cursor rules", "keep my existing CLAUDE.md").
- If a target file already exists and the user didn't say to regenerate it, ask whether to update it or leave it alone.
- Check `<repo>/.ai/docs/` for analysis documents from the `analyze-codebase` skill. If present, use them as the primary source (spot-check against the code — they may be stale). If absent, offer to run `analyze-codebase` first, or explore the codebase directly for a quicker pass.

### 2. Generate the files

Shared principles for all targets:

- **Accuracy**: every command, path, and convention must come from the actual project. Test that commands at least look right against the manifest files (e.g., scripts in package.json, tasks in Makefile, `uv run` vs `pip`).
- **Actionability**: specific, executable instructions beat vague guidance. "Run `uv run ruff format src/`" beats "format your code".
- **Conciseness**: these files are loaded into every AI session — every line costs context. Only include what the AI cannot cheaply discover by reading the code: commands, non-obvious conventions, gotchas, things that have gone wrong before. Do not restate what the code structure makes obvious.
- **Consistency**: same terminology and architecture descriptions across all generated files.

#### AGENTS.md

The primary file — write it first, and write it best. Target well under 150 lines.

- Project overview (1–2 sentences)
- Build, test, run, lint commands (in backticks, copy-pasteable)
- Architecture overview (3–5 bullets)
- Code style conventions
- Testing instructions
- Git workflow (commit format, PR process)
- Key project-specific conventions and gotchas

#### CLAUDE.md

Claude Code reads AGENTS.md natively, so avoid duplicating content between the two files. Pick based on what exists and what the user wants:

- **If AGENTS.md is generated/present** (recommended): make CLAUDE.md a thin complement — a single line `See AGENTS.md for project instructions.` plus only Claude-specific additions if any (e.g., skill/subagent usage preferences, permission notes). If there is nothing Claude-specific, ask the user whether they want CLAUDE.md at all.
- **If the user wants a standalone CLAUDE.md** (no AGENTS.md): include the full content — overview, commands, style, architecture, key components, gotchas, known issues. Target under 300 lines; long CLAUDE.md files degrade rather than improve AI performance.

#### .cursor/rules/*.mdc

Generate 2–3 focused, composable rule files in MDC format (markdown with YAML frontmatter):

```markdown
---
description: Brief description of what this rule covers
globs:
  - "src/**/*.py"
alwaysApply: false
---

# Rule Title

Content...
```

- `project-overview.mdc` — project context, architecture, conventions (`alwaysApply: true`, no globs needed)
- `code-patterns.mdc` — code style, testing patterns, anti-patterns to avoid (globbed to source files)
- `api-conventions.mdc` — only if the project has a significant API surface (globbed to API/handler files)

Keep each file to 50–100 lines. Rules should be prescriptive and project-specific, with short code examples from the actual codebase. Reference files with `@path` syntax where helpful. If a legacy `.cursorrules` file exists, migrate its still-valid content into the new files and tell the user the legacy file can be removed.

### 3. When existing files are provided

When updating rather than creating:

- Preserve the existing structure, tone, and any manually added sections not derivable from analysis (they usually encode hard-won knowledge).
- Refresh outdated information: stale commands, renamed paths, removed components.
- Tell the user specifically what you changed and why.

### 4. Report

List the files written, their line counts, and anything you left out or couldn't verify. If the repo's docs and reality diverged notably, mention it — that's a signal the team should know.

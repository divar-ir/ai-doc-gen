---
name: generate-readme
description: Generate or refresh a comprehensive, professional README.md for a repository, with architecture overview, mermaid and optional C4 diagrams, repository structure, dependencies, and API documentation. Use whenever the user asks to create, write, update, improve, or regenerate a README, project documentation, or a project overview page — even if they just say "document this project" or "this repo needs docs".
---

# Generate README

Transform codebase analysis into a clear, welcoming README.md that helps engineers quickly understand the project.

## Workflow

### 1. Gather analysis data

Check for existing analysis documents in `<repo>/.ai/docs/` (structure, dependency, data-flow, request-flow, API analyses). They may have been produced by the `analyze-codebase` skill.

- **If they exist**: use them as your primary source, but spot-check key claims against the code — they may be stale.
- **If they don't exist**: offer to run the `analyze-codebase` skill first (better results, reusable artifacts). If the user declines or wants it quick, explore the codebase directly yourself before writing.

### 2. Handle the existing README

Ask the user (or infer from their request) whether to incorporate the existing README:

- **Incorporate** (default when a README exists): read it first; keep useful, still-accurate information — especially manually written content like setup quirks, badges, links, and licensing. Verify claims against the code; the old README may be outdated.
- **From scratch**: ignore the existing file entirely.

### 3. Write the README

Include the following sections, in this order, unless the user excludes some. Only use these headlines plus any carried over from the existing README — don't invent extra sections.

- **Project Overview** — title, concise description, purpose, key features, likely use cases.
- **Table of Contents** — for READMEs long enough to need one.
- **Architecture** — high-level overview, technology stack, component relationships with a mermaid diagram, key design patterns.
- **C4 Model Architecture** (optional, skip unless the project's complexity warrants it or the user asks) — context and container diagrams as mermaid, wrapped in `<details>`/`<summary>` tags. Only include levels that can be reasonably deduced from the codebase.
- **Repository Structure** — important directories and key files with their roles. Keep minimal and concise.
- **Dependencies and Integration** — internal/external *service* dependencies, message queues, event streams. Do **not** list ordinary libraries here.
- **API Documentation** — endpoints and request/response formats in an easy-to-read form (tables work well). No raw proto/schema dumps.
- **Development Notes** — project-specific conventions, how to run/test, performance considerations.
- **Known Issues and Limitations** — TODOs/FIXMEs found in code, incomplete features, technical debt.
- **Additional Documentation** — markdown links to other docs in the repository.

### Writing guidelines

1. Use only information that can be reasonably inferred from the code and repository structure — never invent capabilities, and describe existing code, not hypothetical code.
2. Do not include or reference any file from the `.ai/docs/` directory — those are internal AI artifacts.
3. Format with proper Markdown: headings, syntax-highlighted code blocks, lists, and tables.
4. Make the README welcoming and clear for developers new to the project.
5. For mermaid diagrams: group by logical boundaries, use meaningful relationship labels with descriptive verbs, keep visual hierarchy clean, and prefer several small focused diagrams over one giant one.
6. Note (in your report to the user, not the README) any areas where additional documentation would help.

### 4. Report

Write the file to `<repo>/README.md`, then summarize for the user what changed versus the previous README (if any) and flag anything you couldn't verify from the code.

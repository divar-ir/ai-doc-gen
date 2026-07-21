# CLAUDE.md

See AGENTS.md for project instructions (commands, architecture, conventions, gotchas).

Claude-specific notes:

- This repo ships its own Claude Code skills in `skills/` (analyze-codebase, generate-readme, generate-ai-rules) and a plugin manifest in `.claude-plugin/`. When changing agent behavior or prompts in `src/agents/`, update the corresponding skill's SKILL.md so they stay consistent.
- Detailed codebase analyses live in `.ai/docs/*.md`; consult them before broad exploration, but spot-check against the code — they are regenerated snapshots and can be stale.

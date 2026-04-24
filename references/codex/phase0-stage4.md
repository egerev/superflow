# Phase 0 Stage 4: Documentation & Environment — Codex Dispatch Overlay

> For workflow logic (execution matrix, file ownership, validation), read the main file: `references/phase0/stage4-setup.md`.

## Branch Dispatch (3 parallel agents)

### Branch A — Documentation (deep-doc-writer)

Use spawn_agent to dispatch "deep-doc-writer" with task:
```
You are Branch A of Phase 0 setup. Your ONLY job: audit and create/update llms.txt and CLAUDE.md.
[Same prompt body as main doc Branch A section]
```

### Branch B — Permissions & Hooks (fast-implementer)

Use spawn_agent to dispatch "fast-implementer" with task:

**CRITICAL: Codex-specific adaptations for Branch B:**

Permissions go to `~/.codex/config.toml` (NOT `~/.claude/settings.json`):
```toml
[permissions.default]
# Stack-specific permission profiles
```

Hooks go to `~/.codex/hooks.json` (NOT `.claude/settings.json`):
- PostToolUse formatter hooks → Codex hooks.json format:
  ```json
  {"hooks":{"PostToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"formatter-command"}]}]}}
  ```
- Desktop notification → Codex notification mechanism
- PostCompact/SessionStart hooks → already configured in `codex/hooks.json`

Enforcement rules → verify `~/.codex/AGENTS.md` exists (NOT `~/.claude/rules/`). If missing, copy `codex/AGENTS.md` to `~/.codex/AGENTS.md`.

### Branch C — Scaffolding (fast-implementer)

Use spawn_agent to dispatch "fast-implementer" with task:
```
You are Branch C of Phase 0 setup. Your ONLY job: create verify skill, CLAUDE.local.md, and check .gitignore.
[Same prompt body as main doc Branch C section]
```

Additional for Codex: also create symlink for Codex skill discovery:
```bash
mkdir -p ~/.agents/skills
if [ -d ~/.codex/skills/superflow ]; then
  ln -sf ~/.codex/skills/superflow ~/.agents/skills/superflow 2>/dev/null || true
elif [ -d ~/.claude/skills/superflow ]; then
  ln -sf ~/.claude/skills/superflow ~/.agents/skills/superflow 2>/dev/null || true
fi
```

## TaskCreate Replacement

```bash
printf "Phase 0 Stage 4: dispatching 3 setup branches...\n"
printf "Phase 0 Stage 4: all branches complete, validating...\n"
```

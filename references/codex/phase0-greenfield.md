# Phase 0: Greenfield — Codex Dispatch Overlay

> For workflow logic (G1-G6 stages, stack selection, scaffolding), read the main file: `references/phase0/greenfield.md`.

## Dispatch Adaptations

### G3: Scaffold Generation

Use spawn_agent to dispatch "fast-implementer" with the scaffolding task. Include the appropriate template from `templates/greenfield/` (nextjs.md, python.md, or generic.md).

### G4: Documentation Generation

Use spawn_agent to dispatch "deep-doc-writer" with:
- `prompts/llms-txt-writer.md` for llms.txt
- `prompts/claude-md-writer.md` for CLAUDE.md

### G5: Environment Setup

Use spawn_agent to dispatch "fast-implementer" for permissions and hooks setup.

**Codex-specific:** Install to `~/.codex/config.toml` and `~/.codex/hooks.json` instead of `~/.claude/settings.json`. See `references/codex/phase0-stage4.md` Branch B for details.

### G6: Verification

Use spawn_agent to dispatch "fast-implementer" to create `.claude/skills/verify/SKILL.md` with stack-appropriate health checks.

## TaskCreate Replacement

```bash
printf "Greenfield: Stage G%d — %s\n" $STAGE "$DESCRIPTION"
```

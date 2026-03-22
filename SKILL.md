---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Four phases: (0) project onboarding & CLAUDE.md bootstrap, (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, dual-model reviews, max parallelism, and verification discipline, (3) merge with documentation update."
---

# Superflow

Four phases: onboarding, discovery, execution, merge.

Phase 0 (auto, first run only): Detect markers > Analyze codebase (4 parallel agents) > Health report > Audit llms.txt & CLAUDE.md > Permissions > Markers > Checklist
Phase 1 (with user, 12 steps): Context > Research (parallel agents) > Present findings > Brainstorm (STOP GATE) > Approaches > Product Summary (APPROVAL) > Brief > Spec > Spec Review (dual-model) > Plan > Plan Review (dual-model) > User Approval (FINAL GATE)
Phase 2 (autonomous, 11 steps per sprint): Re-read > Telegram > Worktree > Baseline tests > Dispatch implementers > Internal review > Test verification > PAR > Push+PR > Cleanup > Telegram
Phase 3 (user-initiated): Pre-merge checklist > Doc update > Sequential rebase merge (with CI failure handling) > Post-merge report

Durable rules live in `.claude/rules/superflow-enforcement.md` (survives compaction).

## Startup Checklist

1. Read `.claude/rules/superflow-enforcement.md`
2. Detect secondary provider (see below)
3. Detect timeout: `gtimeout` > `timeout` > perl fallback
4. Detect Telegram MCP: `mcp__plugin_telegram_telegram__reply`
5. Detect supervisor: `python3 -c "import sys; print(sys.version)" 2>/dev/null`
6. Detect mode: existing code = Enhancement, empty repo = Greenfield
7. **Run Phase 0** if first run (see detection in `references/phase0-onboarding.md`)
8. Read CLAUDE.md and project docs

## Secondary Provider Detection

```bash
codex --version 2>/dev/null && SECONDARY_PROVIDER="codex"
[ -z "$SECONDARY_PROVIDER" ] && gemini --version 2>/dev/null && SECONDARY_PROVIDER="gemini"
[ -z "$SECONDARY_PROVIDER" ] && aider --version 2>/dev/null && SECONDARY_PROVIDER="aider"
# If none found -> split-focus Claude (two agents, different lenses)
```

Use detected provider silently. No warnings about missing providers.

## Timeout Helper

```bash
if command -v gtimeout &>/dev/null; then TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then TIMEOUT_CMD="timeout"
else timeout_fallback() { perl -e 'alarm shift; exec @ARGV' "$@"; }; TIMEOUT_CMD="timeout_fallback"
fi
```

## Phase References

- Phase 0: `references/phase0-onboarding.md` (first run only)
- Phase 1: `references/phase1-discovery.md`
- Phase 2: `references/phase2-execution.md`
- Phase 3: `references/phase3-merge.md`
- Prompts: `prompts/implementer.md`, `prompts/spec-reviewer.md`, `prompts/code-quality-reviewer.md`, `prompts/product-reviewer.md`
- Documentation: `prompts/llms-txt-writer.md`, `prompts/claude-md-writer.md`
- Testing: `prompts/testing-guidelines.md`

Re-read phase docs at every phase/sprint boundary (compaction erases skill content).

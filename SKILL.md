---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Two phases: (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, dual-model reviews, max parallelism, and verification discipline."
---

# Superflow

Two phases: collaborative discovery, then autonomous execution.

Phase 1 (with user): Context > Research > Brainstorm > Product Summary (approval) > Spec > Plan
Phase 2 (autonomous): Sprint N (subagent + worktree) > PAR > PR #N > repeat > Report

Durable rules live in `.claude/rules/superflow-enforcement.md` (survives compaction).

## Startup Checklist

1. Read `.claude/rules/superflow-enforcement.md`
2. Detect secondary provider (see below)
3. Detect timeout: `gtimeout` > `timeout` > perl fallback
4. Detect Telegram MCP: `mcp__plugin_telegram_telegram__reply`
5. Detect mode: existing code = Enhancement, empty repo = Greenfield
6. Read CLAUDE.md and project docs

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

- Phase 1: `references/phase1-discovery.md`
- Phase 2: `references/phase2-execution.md`
- Prompts: `prompts/implementer.md`, `prompts/spec-reviewer.md`, `prompts/code-quality-reviewer.md`, `prompts/product-reviewer.md`
- Testing: `prompts/testing-guidelines.md`

Re-read phase docs at every phase/sprint boundary (compaction erases skill content).

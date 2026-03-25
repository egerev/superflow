---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Four phases: (0) project onboarding & CLAUDE.md bootstrap, (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, dual-model reviews, max parallelism, and verification discipline, (3) merge with documentation update."
---

# Superflow

Four phases: onboarding, discovery, execution, merge.

Phase 0 (auto, first run only): Detect markers > Auto-detect + confirm > Analyze codebase (5 parallel agents) > Health report > Proposal (approval gate) > Docs + Environment (3 parallel branches) > Markers > Restart instruction
Phase 1 (with user, 11 steps): Context > Research (parallel agents) > Present findings > Brainstorm (STOP GATE) > Approaches > Product Approval (MERGED GATE) > Spec > Spec Review (dual-model) > Plan > Plan Review (dual-model) > User Approval (FINAL GATE)
Phase 2 (autonomous, 10 steps per sprint + wave-based parallel dispatch): Re-read > Telegram > Worktree > Baseline tests > Dispatch implementers (parallel waves) > Unified Review (4 agents) > Test verification > Push+PR > Cleanup > Telegram
Phase 3 (user-initiated): Pre-merge checklist > Doc update > Sequential rebase merge (with CI failure handling) > Post-merge report

Durable rules live in `.claude/rules/superflow-enforcement.md` (survives compaction).

This is a hybrid project: markdown prompts + Python companion CLI (supervisor).

## Architecture

```
superflow/
  SKILL.md              — Skill entry point, startup checklist
  superflow-enforcement.md — Durable rules for ~/.claude/rules/
  bin/
    superflow-supervisor — Python CLI for autonomous sprint orchestration
  lib/
    supervisor.py        — Core: worktree lifecycle, execution, run loop, completion report
    queue.py             — Sprint queue with DAG dependency resolution
    planner.py           — Plan-to-queue generator, shared heading parser
    launcher.py          — Launch/stop/status/restart supervisor
    checkpoint.py        — Checkpoint save/load for crash recovery
    parallel.py          — Parallel execution via ThreadPoolExecutor
    replanner.py         — Adaptive replanner (adjusts remaining sprints)
    notifications.py     — Telegram/stdout notifications
  templates/
    supervisor-sprint-prompt.md — Sprint execution prompt template
    replan-prompt.md     — Replanner prompt template
    superflow-state-schema.json — JSON Schema for .superflow-state.json
    greenfield/              — Stack-specific scaffolding templates
      nextjs.md              — Next.js project template
      python.md              — Python project template
      generic.md             — Generic fallback template
    ci/                      — CI workflow templates
      github-actions-node.yml    — GitHub Actions for Node.js
      github-actions-python.yml  — GitHub Actions for Python
  agents/                — Agent definitions with effort frontmatter (12 definitions)
  # Phase 0 creates <project>/.claude/skills/verify/SKILL.md during onboarding
  prompts/               — Agent prompt templates (7 prompts)
    codex/               — Codex-specific prompts (3 prompts)
  references/            — Phase documentation (phases 0-3)
    phase0-onboarding.md — Phase 0 router (detection, recovery matrix, stage loading)
    phase0/
      stage1-detect.md   — Parallel preflight, auto-detection, confirmation
      stage2-analysis.md — 5 parallel agents, tiered model usage
      stage3-report.md   — Health report, summary, approval
      stage4-setup.md    — 3 concurrent branches, strict file ownership
      stage5-completion.md — Markers, tech debt, restart
      greenfield.md      — Empty project path, G1-G6
  tests/                 — Unit and integration tests (140+ tests)
```

## Startup Checklist

1. Read `.claude/rules/superflow-enforcement.md`
2. **Session recovery check** (only on `feat/*` branches): `git status --short`. If uncommitted changes exist from a crashed previous session:
   a. `git stash` → run tests on clean HEAD → note results
   b. `git stash pop` → run tests again → compare
   c. If working tree tests fail but HEAD tests pass, the stashed changes have bugs — fix before proceeding
   d. If both pass, commit the stashed changes with appropriate message
3. Detect secondary provider (see below)
4. Detect timeout: `gtimeout` > `timeout` > perl fallback
5. Detect Telegram MCP: `mcp__plugin_telegram_telegram__reply`
6. Detect supervisor: `python3 -c "import sys; print(sys.version)" 2>/dev/null`
7. Detect mode: existing code = Enhancement, empty repo = Greenfield
8. **Deploy agent definitions** (if missing): `test -f ~/.claude/agents/deep-analyst.md || cp ~/.claude/skills/superflow/agents/*.md ~/.claude/agents/ 2>/dev/null`
9. **Run Phase 0** if first run (see detection in `references/phase0-onboarding.md`)
10. Check `.superflow-state.json` for resume context (crash recovery, session restore)
11. **Detect running supervisor**: check `launcher.get_status()`. If alive=True, enter dashboard mode. If crashed=True, offer restart.
12. Read CLAUDE.md and project docs

## Secondary Provider Detection

```bash
codex --version 2>/dev/null && SECONDARY_PROVIDER="codex"
[ -z "$SECONDARY_PROVIDER" ] && gemini --version 2>/dev/null && SECONDARY_PROVIDER="gemini"
[ -z "$SECONDARY_PROVIDER" ] && aider --version 2>/dev/null && SECONDARY_PROVIDER="aider"
# If none found -> split-focus Claude (two agents, different lenses)
```

Use detected provider silently. No warnings about missing providers.

## State Management

`.superflow-state.json` in the project root tracks current phase, sprint, and stage. It is:
- **Read-only projection** during Phase 2 with supervisor (generated from queue/checkpoint data)
- **Directly written** during Phases 0, 1, 3 (interactive, single session)
- **Gitignored** (added during Phase 0 Stage 4 Branch C)
- **Schema**: `templates/superflow-state-schema.json`

Hooks read state for context restoration:
- **PostCompact hook** (`~/.claude/settings.json`): after context compaction, injects current phase/stage so the LLM can re-read the right phase doc
- **SessionStart hook** (`~/.claude/settings.json`): on `claude --resume`, restores Superflow context from state file

## Dashboard Commands

When supervisor is running in background (auto-launched from Phase 1 or manually), these commands are available:

| Command | Action |
|---------|--------|
| `status` | Show supervisor status (PID, sprint, heartbeat) |
| `log` | Show last 50 lines of supervisor log |
| `stop` | Stop supervisor (SIGTERM to process group) |
| `restart` | Stop + resume crashed sprints + relaunch |
| `skip N` | Skip sprint N (writes sidecar request) |
| `merge` | Transition to Phase 3 (all sprints must be complete) |

## Timeout Helper

```bash
if command -v gtimeout &>/dev/null; then TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then TIMEOUT_CMD="timeout"
else timeout_fallback() { perl -e 'alarm shift; exec @ARGV' "$@"; }; TIMEOUT_CMD="timeout_fallback"
fi
```

## Phase References

- Phase 0: `references/phase0-onboarding.md` (router — first run only); stages: `references/phase0/stage1-detect.md`, `references/phase0/stage2-analysis.md`, `references/phase0/stage3-report.md`, `references/phase0/stage4-setup.md`, `references/phase0/stage5-completion.md`, `references/phase0/greenfield.md`
- Phase 1: `references/phase1-discovery.md`
- Phase 2: `references/phase2-execution.md`
- Phase 3: `references/phase3-merge.md`
- Prompts: `prompts/implementer.md`, `prompts/spec-reviewer.md`, `prompts/code-quality-reviewer.md`, `prompts/product-reviewer.md`
- Documentation: `prompts/llms-txt-writer.md`, `prompts/claude-md-writer.md`
- Testing: `prompts/testing-guidelines.md`
- Agent definitions: `agents/deep-implementer.md`, `agents/standard-implementer.md`, `agents/fast-implementer.md`, `agents/deep-code-reviewer.md`, `agents/standard-code-reviewer.md`, `agents/deep-product-reviewer.md`, `agents/standard-product-reviewer.md`, `agents/deep-spec-reviewer.md`, `agents/standard-spec-reviewer.md`, `agents/deep-doc-writer.md`, `agents/standard-doc-writer.md`, `agents/deep-analyst.md`
- Codex prompts: `prompts/codex/code-reviewer.md`, `prompts/codex/product-reviewer.md`, `prompts/codex/audit.md`
- Supervisor: `bin/superflow-supervisor`, `lib/supervisor.py`, `lib/queue.py`, `lib/checkpoint.py`, `lib/parallel.py`, `lib/replanner.py`, `lib/notifications.py`
- Templates: `templates/supervisor-sprint-prompt.md`, `templates/replan-prompt.md`
- State: `templates/superflow-state-schema.json` (schema), `.superflow-state.json` (runtime, gitignored)

Re-read phase docs at every phase/sprint boundary (compaction erases skill content).

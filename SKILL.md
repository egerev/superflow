---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Four phases: (0) project onboarding & CLAUDE.md bootstrap, (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, dual-model reviews, max parallelism, and verification discipline, (3) merge with documentation update."
---

# Superflow

Four phases: onboarding, discovery, execution, merge.

Phase 0 (auto, first run only): Detect markers > Auto-detect + confirm > Analyze codebase (5 parallel agents) > Health report > Proposal (approval gate) > Docs + Environment (3 parallel branches) > Markers > Restart instruction
Phase 1 (with user, 13 steps): Context > Governance Mode (light/standard/critical) > Research (parallel agents, skip in light) > Present findings > Brainstorm (STOP GATE) > Approaches > Product Approval (MERGED GATE) > Spec > Spec Review (dual-model, skip in light) > Plan > Plan Review (dual-model) > User Approval (FINAL GATE) > Charter
Phase 2 (autonomous, 10 steps per sprint + wave-based parallel dispatch): Re-read > Telegram > Worktree > Baseline tests > Dispatch implementers (parallel waves) > Unified Review (2 agents) > Test verification > Push+PR > Cleanup > Telegram
Phase 3 (user-initiated): Pre-merge checklist > Doc update > Sequential rebase merge (with CI failure handling) > Post-merge report

Durable rules live in `.claude/rules/superflow-enforcement.md` (survives compaction).

## Architecture

```
superflow/
  SKILL.md              — Skill entry point, startup checklist
  superflow-enforcement.md — Durable rules for ~/.claude/rules/
  templates/
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
  prompts/               — Agent prompt templates (8 prompts, incl. expert-panel.md)
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
```

## Startup Checklist

1. Read `.claude/rules/superflow-enforcement.md`
2. **Session recovery check** (only on `feat/*` branches): `git status --short`. If uncommitted changes exist from a crashed previous session:
   a. `git stash` → run tests on clean HEAD → note results
   b. `git stash pop` → run tests again → compare
   c. If working tree tests fail but HEAD tests pass, the stashed changes have bugs — fix before proceeding
   d. If both pass, commit the stashed changes with appropriate message
3. **Detect environment** (single bash call + context check):
   ```bash
   # All detection in one command
   codex --version 2>/dev/null && echo "PROVIDER:codex" || { gemini --version 2>/dev/null && echo "PROVIDER:gemini" || { aider --version 2>/dev/null && echo "PROVIDER:aider" || echo "PROVIDER:none"; }; }
   command -v gtimeout &>/dev/null && echo "TIMEOUT:gtimeout" || { command -v timeout &>/dev/null && echo "TIMEOUT:timeout" || echo "TIMEOUT:perl_fallback"; }
   test -e .git && echo "MODE:enhancement" || echo "MODE:greenfield"
   test -f ~/.claude/agents/deep-analyst.md || cp ~/.claude/skills/superflow/agents/*.md ~/.claude/agents/ 2>/dev/null
   ```
   Telegram: check deferred tools list for `mcp__plugin_telegram_telegram__reply`. **Only mention Telegram updates if detected.** Do NOT promise Telegram without the plugin.
4. **Check `.superflow-state.json`** for resume context:
   - If `phase = 2` AND current branch is `main`:
     - If `context.charter_file` exists on disk → valid resume (handoff, mid-execution, or completed)
     - Else → state is stale from a previous run. Reset: write fresh state with phase=1
   - If `phase = 3` AND current branch is `main` → valid Phase 3 resume (merge in progress)
   - If `phase >= 2` AND on `feat/*` branch → valid resume, proceed with session recovery
   - If `phase = 1` → resume Phase 1 from saved stage
   - **Do NOT read old briefs, plans, or sprint queues from previous runs**
5. **Phase 0 gate** (inline — do NOT read phase0-onboarding.md unless needed):
   - If `.superflow-state.json` exists AND `phase > 0` → skip Phase 0
   - If `.superflow-state.json` exists AND `phase = 0` → read `references/phase0-onboarding.md` for crash recovery
   - If `.superflow-state.json` does not exist → **check main branch for markers before triggering Phase 0**:
     ```bash
     grep -q "updated-by-superflow\|superflow:onboarded" CLAUDE.md 2>/dev/null && echo "MARKER_LOCAL" || \
       (git show main:CLAUDE.md 2>/dev/null | grep -q "updated-by-superflow\|superflow:onboarded" && echo "MARKER_ON_MAIN" || echo "NO_MARKER")
     ```
     - `MARKER_LOCAL` or `MARKER_ON_MAIN` → skip Phase 0, write fresh state with phase=1
     - `NO_MARKER` → read `references/phase0-onboarding.md` for full Phase 0
5a. **Anti-regression settings check** (inline — runs once per machine, do NOT read `references/anti-regression-check.md` unless needed):
   ```bash
   if [ -f ~/.claude/.superflow-anti-regression-checked ]; then echo "DISMISSED"; \
   elif [ ! -r ~/.claude/settings.json ]; then echo "NO_SETTINGS"; \
   else MISSING=(); \
     jq -e '.env.CLAUDE_CODE_EFFORT_LEVEL == "max"' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_EFFORT_LEVEL"); \
     jq -e '.env.CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING == "1"' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"); \
     jq -e '.env.MAX_THINKING_TOKENS' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("MAX_THINKING_TOKENS"); \
     jq -e '.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_AUTO_COMPACT_WINDOW"); \
     jq -e '.showThinkingSummaries == true' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("showThinkingSummaries"); \
     jq -e '[.hooks.PreCompact? // [] | select(type == "array") | .[]?.hooks[]?.command? // empty] | any(endswith("/precompact-state-externalization.sh"))' ~/.claude/settings.json >/dev/null 2>&1 || MISSING+=("PreCompactHook"); \
     [ ${#MISSING[@]} -eq 0 ] && echo "ALL_SET" || printf "MISSING:%s\n" "$(IFS=,; echo "${MISSING[*]}")"; \
   fi
   ```
   - `DISMISSED` / `ALL_SET` / `NO_SETTINGS` → silent, continue to step 6
   - `MISSING:...` → read `references/anti-regression-check.md` and follow it (conversational: show user the diff, ask y/n/skip-permanently, apply via jq if user agrees, write marker file). After the user decision, continue to step 6.
6. **Display startup banner** — output immediately after detection, before any phase routing:
   ```
   ╔═══════════════════════════════════╗
   ║  ⚡ SUPERFLOW v4.2.0              ║
   ║  Autonomous Dev Workflow          ║
   ╚═══════════════════════════════════╝
   ```
   IMPORTANT: The `║` characters on the right side MUST align vertically. Count characters carefully — each line between `║` markers must be the same width. Test by verifying all `║` on the right are in the same column.

   Then list detected status using checkmarks/warnings:
   - `✅` / `—` for: secondary provider (name + version), timeout command, Telegram
   - `⚠️` for: missing state file, Phase 0 required, stale state detected
   - Final line: `Mode: enhancement/greenfield | Phase: N | Governance: mode/—`
   Keep it compact (banner + 4-6 status lines). Do not repeat detection details already shown.
7. Read project-specific docs if needed (CLAUDE.md is already loaded as project instructions — do not re-read)

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
- **Directly written** by Claude during all phases
- **Gitignored** (added during Phase 0 Stage 4 Branch C)
- **Schema**: `templates/superflow-state-schema.json`

Hooks read state for context restoration:
- **PostCompact hook** (`~/.claude/settings.json`): after context compaction, injects current phase/stage so the LLM can re-read the right phase doc
- **SessionStart hook** (`~/.claude/settings.json`): on `claude --resume`, restores Superflow context from state file

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
- Prompts: `prompts/implementer.md`, `prompts/expert-panel.md`, `prompts/spec-reviewer.md`, `prompts/code-quality-reviewer.md`, `prompts/product-reviewer.md`
- Documentation: `prompts/llms-txt-writer.md`, `prompts/claude-md-writer.md`
- Testing: `prompts/testing-guidelines.md`
- Agent definitions: `agents/deep-implementer.md`, `agents/standard-implementer.md`, `agents/fast-implementer.md`, `agents/deep-code-reviewer.md`, `agents/standard-code-reviewer.md`, `agents/deep-product-reviewer.md`, `agents/standard-product-reviewer.md`, `agents/deep-spec-reviewer.md`, `agents/standard-spec-reviewer.md`, `agents/deep-doc-writer.md`, `agents/standard-doc-writer.md`, `agents/deep-analyst.md`
- Codex prompts: `prompts/codex/code-reviewer.md`, `prompts/codex/product-reviewer.md`, `prompts/codex/audit.md`
- State: `templates/superflow-state-schema.json` (schema), `.superflow-state.json` (runtime, gitignored)

Re-read phase docs at every phase/sprint boundary (compaction erases skill content).

---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Four phases: (0) project onboarding & CLAUDE.md bootstrap, (1) collaborative Product Discovery with multi-expert brainstorming and git workflow selection, (2) fully autonomous execution with selected PR/branch strategy, git worktrees, dual-model reviews, max parallelism, and verification discipline, (3) merge with documentation update."
---

# Superflow

Four phases: onboarding, discovery, execution, merge.

Phase 0 (auto, first run only): Detect markers > Auto-detect + confirm > Analyze codebase (5 parallel agents) > Health report > Proposal (approval gate) > Docs + Environment (3 parallel branches) > Markers > Restart instruction
Phase 1 (with user, 13 steps): Context > Governance Mode (light/standard/critical) + Git Workflow Mode > Research (parallel agents, skip in light) > Present findings > Brainstorm (STOP GATE) > Approaches > Product Approval (MERGED GATE) > Spec > Spec Review (dual-model, skip in light) > Plan > Plan Review (dual-model) > User Approval (FINAL GATE) > Charter
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

1. **Detect runtime** (before anything else):
   ```bash
   # Runtime detection — detect Claude positively, default to Codex
   [ -n "$CLAUDE_CODE_SESSION_ID" ] && echo "RUNTIME:claude" || echo "RUNTIME:codex"
   ```
   Store the result. All subsequent steps branch on `RUNTIME`.
2. **Locate skill root + read durable rules:**
   ```bash
   SUPERFLOW_SKILL_ROOT=""
   for d in \
       "$HOME/.codex/skills/superflow" \
       "$HOME/.claude/skills/superflow" \
       "$HOME/.agents/skills/superflow" \
       "./"; do
     if [ -f "$d/SKILL.md" ] && [ -f "$d/superflow-enforcement.md" ]; then
       SUPERFLOW_SKILL_ROOT="$(cd "$d" && pwd)"
       break
     fi
   done
   export SUPERFLOW_SKILL_ROOT
   ```
   - `RUNTIME:claude` → Read `.claude/rules/superflow-enforcement.md` (or `$SUPERFLOW_SKILL_ROOT/superflow-enforcement.md` during setup)
   - `RUNTIME:codex` → Read `$SUPERFLOW_SKILL_ROOT/codex/AGENTS.md`
3. **Session recovery check** (only on `feat/*` branches): `git status --short`. If uncommitted changes exist from a crashed previous session:
   a. `git stash` → run tests on clean HEAD → note results
   b. `git stash pop` → run tests again → compare
   c. If working tree tests fail but HEAD tests pass, the stashed changes have bugs — fix before proceeding
   d. If both pass, commit the stashed changes with appropriate message
4. **Detect environment** (single bash call + context check):
   ```bash
   # All detection in one command — secondary provider detection
   if [ "$RUNTIME" = "codex" ]; then
     # Codex is primary → detect Claude as secondary
     claude --version 2>/dev/null && echo "SECONDARY:claude" || echo "SECONDARY:none"
   else
     # Claude is primary → detect Codex as secondary
     codex --version 2>/dev/null && echo "SECONDARY:codex" || { gemini --version 2>/dev/null && echo "SECONDARY:gemini" || { aider --version 2>/dev/null && echo "SECONDARY:aider" || echo "SECONDARY:none"; }; }
   fi
   command -v gtimeout &>/dev/null && echo "TIMEOUT:gtimeout" || { command -v timeout &>/dev/null && echo "TIMEOUT:timeout" || echo "TIMEOUT:perl_fallback"; }
   test -e .git && echo "MODE:enhancement" || echo "MODE:greenfield"
   # Deploy agent definitions for the detected runtime
   if [ "$RUNTIME" = "codex" ]; then
     mkdir -p ~/.codex/agents
     test -f ~/.codex/agents/deep-analyst.toml || cp "$SUPERFLOW_SKILL_ROOT"/codex/agents/*.toml ~/.codex/agents/ 2>/dev/null
   else
     test -f ~/.claude/agents/deep-analyst.md || cp ~/.claude/skills/superflow/agents/*.md ~/.claude/agents/ 2>/dev/null
   fi
   ```
   Telegram: check deferred tools list for `mcp__plugin_telegram_telegram__reply`. **Only mention Telegram updates if detected.** Do NOT promise Telegram without the plugin.
   **Codex runtime:** also persist runtime to state: `context.runtime = "codex"` when writing `.superflow-state.json`.
4b. **Event log setup** — initialize the run's event log:
    ```bash
    # Restore or generate SUPERFLOW_RUN_ID — preserve across resumes
    if [ -z "${SUPERFLOW_RUN_ID:-}" ]; then
      SUPERFLOW_RUN_ID=$(jq -r '.context.run_id // empty' .superflow-state.json 2>/dev/null || true)
      if [ -z "$SUPERFLOW_RUN_ID" ]; then
        SUPERFLOW_RUN_ID="$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)"
      fi
      export SUPERFLOW_RUN_ID
    fi
    # Persist run_id into state — always, even on first run (creates minimal state if absent)
    mkdir -p .superflow
    if [ -f .superflow-state.json ]; then
      tmp=$(mktemp .superflow-state.XXXXXX)
      jq --arg rid "$SUPERFLOW_RUN_ID" '.context = (.context // {}) | .context.run_id = $rid' .superflow-state.json > "$tmp" && mv "$tmp" .superflow-state.json
    else
      jq -n --arg rid "$SUPERFLOW_RUN_ID" '{"context":{"run_id":$rid}}' > .superflow-state.json
    fi
    # Derive current phase from persisted state (0 = onboarding/first-time, which is correct)
    CURRENT_PHASE=$(jq -r '.phase // 0' .superflow-state.json 2>/dev/null || echo 0)
    export CURRENT_PHASE
    # Runtime-aware path discovery — try Claude, Codex, agents, then repo-local
    _SF_EMIT_FOUND=""
    for p in \
        "$SUPERFLOW_SKILL_ROOT/tools/sf-emit.sh" \
        "$HOME/.codex/skills/superflow/tools/sf-emit.sh" \
        "$HOME/.claude/skills/superflow/tools/sf-emit.sh" \
        "$HOME/.agents/skills/superflow/tools/sf-emit.sh" \
        "./tools/sf-emit.sh"; do
      if [ -f "$p" ]; then source "$p"; _SF_EMIT_FOUND=1; break; fi
    done
    if [ -z "${_SF_EMIT_FOUND:-}" ]; then
      echo "⚠️  sf-emit.sh not found — event telemetry disabled (see superflow v5 Run 2)" >&2
      sf_emit() { return 0; }
    fi
    sf_emit run.start runtime="${RUNTIME:-claude}" phase:int="$CURRENT_PHASE" || true
    ```
    Persist `SUPERFLOW_RUN_ID` into `.superflow-state.json` under `context.run_id` for recovery after `/clear`.

    Note: If `tools/sf-emit.sh` is missing (v4.x installs without Run 2), log a one-line warning and continue — event log is telemetry, not required for execution.
5. **Check `.superflow-state.json`** for resume context:
   - If `phase = 2` AND current branch is `main`:
     - If `context.charter_file` exists on disk → valid resume (handoff, mid-execution, or completed)
     - Else → state is stale from a previous run. Reset: write fresh state with phase=1
   - If `phase = 3` AND current branch is `main` → valid Phase 3 resume (merge in progress)
   - If `phase >= 2` AND on `feat/*` branch → valid resume, proceed with session recovery
   - If `phase = 1` → resume Phase 1 from saved stage
   - **Do NOT read old briefs, plans, or sprint queues from previous runs**
4a. **Heartbeat validation** — if `.superflow-state.json` has a `heartbeat` block, check `heartbeat.must_reread`. For each path: if already read in this session → skip. If not in context → Read it (only short orchestration files belong here; Rule 12 guarantees they are <300 lines). If a listed file does not exist on disk, skip silently and emit a one-line warning. See enforcement Rule 12 for the full, compaction-surviving version of this check.
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
6. **Display startup banner** — output immediately after detection, before any phase routing:
   ```
   ╔═══════════════════════════════════╗
   ║  ⚡ SUPERFLOW v5.2.1              ║
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

**When RUNTIME=claude** (Claude is orchestrator):
```bash
codex --version 2>/dev/null && SECONDARY_PROVIDER="codex"
[ -z "$SECONDARY_PROVIDER" ] && gemini --version 2>/dev/null && SECONDARY_PROVIDER="gemini"
[ -z "$SECONDARY_PROVIDER" ] && aider --version 2>/dev/null && SECONDARY_PROVIDER="aider"
# If none found -> split-focus Claude (two agents, different lenses)
```

**When RUNTIME=codex** (Codex is orchestrator):
```bash
claude --version 2>/dev/null && SECONDARY_PROVIDER="claude"
# If none found -> split-focus Codex (two agents, different lenses)
```

Use detected provider silently. No warnings about missing providers.

## Codex Runtime Specifics

When RUNTIME=codex, the following differences apply throughout all phases:

- **Dispatch**: use spawn_agent tool with agent name from .toml definitions in `~/.codex/agents/`
- **Parallelism**: implicit (max_threads=6), no run_in_background needed. Recommended `max_depth=2` enables sprint supervisors to spawn per-sprint implement/review/doc agents.
- **Claude product/research secondary**: Claude CLI — `$TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "PROMPT" 2>&1`
- **Durable rules**: `codex/AGENTS.md` — re-read after ANY `/compact`
- **Progress tracking**: printf (no TaskCreate/TaskUpdate available)
- **Hooks**: `~/.codex/hooks.json` (SessionStart + Stop), no PreCompact/PostCompact
- **Context budget**: ~258K — use `/compact` between sequential sprints or completed sprint waves, session-per-wave for 4+ sprints
- **Phase docs routing**: read `references/codex/<phase>.md` for dispatch, main `references/<phase>.md` for logic
- **Sprint execution**: sprint-level parallelism is enabled when `max_depth>=2` and `context.git_workflow_mode` permits independent waves; fall back to sequential if configured with `max_depth=1`
- **Skill discovery**: install/symlink the skill at `~/.codex/skills/superflow`; optionally mirror to `~/.agents/skills/superflow` for older launchers

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

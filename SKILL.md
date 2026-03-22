---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Two phases: (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, dual-model reviews, max parallelism, and verification discipline."
---

# Superflow — Product-to-Production Workflow

Two distinct phases: collaborative discovery, then autonomous execution.

```
Phase 1: COLLABORATIVE (with user)
  Context → Research → Brainstorm → Product Summary (user approves) → Spec → Plan

Phase 2: AUTONOMOUS (separate sessions, no stops)
  Sprint 1 (subagent + worktree) → PR #1
  Sprint 2 (subagent + worktree) → PR #2
  ...
  Sprint N → PR #N → Report to user
```

---

## Architecture

Skill content gets lost during context compaction. Critical rules live in
`.claude/rules/superflow-enforcement.md` — read it at session start. It survives compaction.

The orchestrator (you) coordinates work: reads files, creates plans, dispatches reviewers.
Implementation code is written by subagents via the Agent tool, because subagents get
isolated context windows — preventing overflow and ensuring each sprint gets full attention.

---

## Startup Checklist

At session start, before anything else:

1. Read `.claude/rules/superflow-enforcement.md`
2. Detect secondary providers (see [Secondary Provider Detection](#secondary-provider-detection))
3. Detect timeout command (see [Timeout Helper](#timeout-helper))
4. Detect Telegram: check if `mcp__plugin_telegram_telegram__reply` is available
5. Detect mode: existing code = Enhancement, empty repo = Greenfield
6. Read CLAUDE.md and project docs

---

## Rules

1. **Dispatch subagents for implementation** — the orchestrator coordinates, subagents write code.
   Writing code directly in the main context fills the window and causes drift.

2. **Use git worktrees for sprint isolation** — `git worktree add .worktrees/sprint-N`.
   Worktrees prevent file conflicts and enable clean rollback.

3. **Run Product Acceptance Review before every PR** — dispatch Claude + secondary provider reviewers.
   Code can be technically clean but productively wrong; this catches intent mismatches.

4. **Run tests and paste output before claiming done.** "Should work" is not evidence.

5. **Re-read reference files at each phase transition** — use the Read tool on the relevant
   file. After compaction, the skill content is gone; re-reading restores it.

6. **Use dual-model reviews** — Codex preferred, other providers as fallback, split-focus Claude
   as last resort. Two different models catch different bugs.

7. **One PR per sprint.** Smaller PRs are easier to review and safer to deploy.

8. **Execute silently in Phase 2.** After plan approval, work without pausing or asking.

9. **Get user "ок" on Product Summary before writing spec.** This is the product approval gate.

---

## Self-Check (at every phase transition)

Before proceeding to the next phase or sprint, verify:

- Am I following Superflow, or have I started improvising?
- Am I about to write code directly? → Dispatch a subagent instead.
- Did I create a git worktree for this sprint? → Create one if not.
- Did I run tests and see passing output? → Run them if not.
- Did I run Product Acceptance Review? → Launch it if not.
- Did I use dual-model review? → Codex if available, other provider, or split-focus fallback.

---

## Phase 1: Product Discovery (collaborative)

Read `references/phase1-discovery.md` for full details.

Summary:

1. **Context Exploration** — read CLAUDE.md, git history, understand architecture
2. **Research** — dispatch background agents for best practices, libraries, competitors
3. **Independent Product Expert** — dispatch secondary provider as product expert (parallel with brainstorming)
4. **Brainstorming** — freeflow with product focus, questions → proposals → questions
5. **Product Summary** — present features, problems solved, scope → **user approves**
6. **Spec Document** — `mkdir -p docs/superpowers/specs` then write to `docs/superpowers/specs/`
7. **Spec Review** — Claude + secondary provider in parallel
8. **Implementation Plan** — `mkdir -p docs/superpowers/plans` then write to `docs/superpowers/plans/`
9. **Plan Review** — Claude + secondary provider in parallel
10. **User Approval** — last interaction before autonomous execution

Step 5 (Product Summary) is the gate — proceed to spec only after user confirms.

---

## Phase 2: Autonomous Execution

Read `references/phase2-execution.md` for full details.

After plan approval, end the current session. Execute each sprint in a separate session
because a single session with multiple sprints fills the context window, triggers compaction,
and erases the skill instructions.

- Each sprint = new `claude -p` session or Agent with `isolation: "worktree"`
- The plan file (`docs/superpowers/plans/...`) is the handoff artifact
- Each sprint starts with full 1M context — zero drift

### Per-Sprint Flow

```
Sprint N:
  1. Re-read references/phase2-execution.md
  2. Create worktree: git worktree add .worktrees/sprint-N
  3. Dispatch implementation subagents (Agent tool, mode: bypassPermissions)
  4. Run tests → Product Acceptance Review (Claude + secondary provider)
  5. Create PR targeting main
  6. Clean up worktree
  7. Send Telegram progress (if connected)
  8. Next sprint
```

### Sprint Completion Checklist (verify before creating PR)

```
[ ] Tests pass with evidence (actual output pasted)
[ ] Lint clean
[ ] TypeCheck clean
[ ] Product Acceptance Review launched (Claude + secondary provider or split-focus)
[ ] Product Acceptance approved
[ ] Only then → create PR
```

---

## Secondary Provider Integration

Dual-model reviews use two different AI models for independent review. Codex is the preferred
secondary provider, but any CLI-based LLM works.

**Fallback chain** (use the first available):
1. **Codex** (preferred) — `$TIMEOUT_CMD 600 codex exec --full-auto "PROMPT" 2>&1`
2. **Other CLI provider** (Gemini CLI, Aider, etc.) — `$TIMEOUT_CMD 600 <provider> <flags> "PROMPT" 2>&1`
3. **Split-focus Claude** (last resort) — two Claude agents with different review lenses

**When NO secondary provider is available**, do NOT skip reviews. Dispatch **two Claude agents**
with split focus:
- **Agent A (Technical):** security, architecture, performance, correctness
- **Agent B (Product):** spec compliance, UX gaps, edge cases, data integrity

Two agents with different prompts catch more than one generalist reviewer.

### Secondary Provider Detection

Detect at startup with a smoke test (not just `which` — binary can exist without API keys):

```bash
# Preferred: Codex
codex --version 2>/dev/null && SECONDARY_PROVIDER="codex"
# Fallback: other providers
[ -z "$SECONDARY_PROVIDER" ] && gemini --version 2>/dev/null && SECONDARY_PROVIDER="gemini"
[ -z "$SECONDARY_PROVIDER" ] && aider --version 2>/dev/null && SECONDARY_PROVIDER="aider"
# If none found → split-focus Claude (no SECONDARY_PROVIDER set)
```

Use the detected provider silently. Never warn about missing providers.

---

## Timeout Helper

Detect once at startup and set `TIMEOUT_CMD`:

```bash
if command -v gtimeout &>/dev/null; then
  TIMEOUT_CMD="gtimeout"
elif command -v timeout &>/dev/null; then
  TIMEOUT_CMD="timeout"
else
  # Universal fallback — works on any system with Perl (including macOS)
  timeout_fallback() { perl -e 'alarm shift; exec @ARGV' "$@"; }
  TIMEOUT_CMD="timeout_fallback"
fi
```

Use `$TIMEOUT_CMD 600 codex exec ...` everywhere instead of hardcoding `gtimeout` or `timeout`.

---

## Telegram Progress

When Telegram MCP is connected, send short updates at key transitions:
sprint started, PR created, errors/blockers, final completion report.

When launching background work, acknowledge receipt first:
"Принял, делаю X. Отпишусь через N минут."

---

## Rationalization Prevention

If you catch yourself thinking any of these, course-correct:

| Thought | What to do instead |
|---|---|
| "I'll just write the code directly" | Dispatch a subagent — it gets a clean context window |
| "Too simple for a worktree" | Create the worktree — it takes 5 seconds |
| "Skip review, it's trivial" | Run the review — trivial changes break production |
| "Second reviewer isn't needed" | Two reviewers catch more bugs. Use Codex, other provider, or split-focus |
| "Let me ask the user" | After plan approval, execute silently |
| "Tests are green so it works" | Verify behavior, not just test output |
| "One big PR is fine" | Split into one PR per sprint |

---

## Documentation Update

After the last sprint's PR, before the completion report:
1. Update CLAUDE.md with new modules and files
2. Update BACKLOG.md with completed and discovered items
3. Commit documentation to the last sprint's branch

---

## References

- `references/phase1-discovery.md` — full Phase 1 steps
- `references/phase2-execution.md` — full Phase 2 flow, agent dispatch, debugging
- `prompts/implementer.md` — implementation agent prompt template
- `prompts/spec-reviewer.md` — spec review prompt
- `prompts/code-quality-reviewer.md` — code quality review prompt
- `prompts/product-reviewer.md` — product acceptance review prompt

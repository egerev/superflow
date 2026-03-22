# Superflow Enforcement

Survives context compaction. SKILL.md does not.

## Hard Rules

1. **Subagents write all code.** Orchestrator reads, plans, reviews, dispatches.
2. **Git worktrees per sprint.** `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. Verify `.worktrees/` is in `.gitignore` before creating (`git check-ignore -q .worktrees`).
3. **PAR before every PR** (2 reviewers, both receive SPEC):
   1. Dispatch Claude reviewer (spec compliance, security, architecture). `run_in_background: true`
   2. Dispatch secondary provider (product fit, UX gaps, edge cases). `$TIMEOUT_CMD 600`
   3. Wait for both. Fix NEEDS_FIXES. Re-review after fixes.
   4. Write `.par-evidence.json`: `{"sprint":N,"claude":"ACCEPTED","secondary":"ACCEPTED","ts":"..."}`
   5. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists.
4. **Tests with evidence.** Paste actual output before claiming done.
5. **Re-read phase docs** at each sprint boundary via Read tool.
6. **Dual-model reviews mandatory.** Use secondary provider for spec review, plan review, and PAR.
7. **No secondary provider = split-focus Claude.** Two agents (Technical + Product). Never skip the second reviewer.
8. **One PR per sprint.** Execute silently after plan approval.

## Secondary Provider Invocation

```bash
# Codex:  $TIMEOUT_CMD 600 codex exec --full-auto "PROMPT_HERE" 2>&1
# Gemini: $TIMEOUT_CMD 600 gemini "PROMPT_HERE" 2>&1
# Other:  $TIMEOUT_CMD 600 $SECONDARY_PROVIDER <non-interactive-flag> "PROMPT_HERE" 2>&1
# None:   dispatch two Claude agents with split focus (Technical + Product)
```

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent
- "Too simple for a worktree" → create worktree
- "One reviewer is enough" → dispatch second reviewer
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → one PR per sprint
- "This sprint is too small for PAR" → run PAR

## Product Approval Gate

Before writing a spec, present Product Summary (features, problems solved, out of scope). Wait for user approval.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory. Do not skip to Phase 1 without completing onboarding. See `references/phase0-onboarding.md`.

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж". Merge follows strict order: sequential, rebase, CI green, docs updated. See `references/phase3-merge.md`.

## Telegram Progress

When MCP connected: send short updates at sprint start, PR created, errors/blockers, completion. Acknowledge receipt before background work.

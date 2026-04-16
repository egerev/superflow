# Superflow Enforcement (Codex Runtime)

Survives as long as session. Re-read after ANY /compact command.

## COMPACTION RECOVERY (CRITICAL — read this first after any compaction)

After ANY compaction or `/compact` command, IMMEDIATELY:
1. Re-read this file (`codex/AGENTS.md` or `~/.codex/AGENTS.md`)
2. Re-read `.superflow-state.json`
3. Re-read the latest dump from `.superflow/compact-log/` (if exists): `ls -t .superflow/compact-log/ 2>/dev/null | head -1`
Only then resume work.

## Hard Rules

1. **Subagents write all code.** Orchestrator reads, plans, reviews, dispatches via `spawn_agent` tool. Orchestrator never writes implementation code directly.
2. **Git worktrees per sprint.** `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. Verify `.worktrees/` is in `.gitignore` before creating.
3. **Flat dispatch only.** Codex `max_depth=1` — subagents cannot spawn sub-subagents. Orchestrator dispatches ALL agents directly. No sprint-level delegation. Sprints execute sequentially.
4. **Unified Review before every PR** (2 agents for standard/critical sprints; single Technical reviewer for light-mode sprints):
   1. Use spawn_agent tool to dispatch product reviewer (agent: "standard-product-reviewer")
   2. Dispatch Claude as secondary technical reviewer: `$TIMEOUT_CMD 600 claude -p "REVIEW_PROMPT" 2>&1`
   3. Wait for both. Fix confirmed issues (NEEDS_FIXES, REQUEST_CHANGES, or FAIL). Re-review only flagging agent.
   4. Write `.par-evidence.json`: `{"sprint":N,"codex_product":"ACCEPTED","technical_review":"APPROVE","provider":"claude|split-focus","ts":"..."}`
   5. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists with both verdicts passing.
   6. Pass verdicts: APPROVE, ACCEPTED, PASS. Fail verdicts: REQUEST_CHANGES, NEEDS_FIXES, FAIL.
5. **Tests with evidence.** Paste actual output before claiming done.
6. **Re-read phase docs** at each sprint boundary. Read `references/codex/<phase>.md` for dispatch patterns, main `references/<phase>.md` for workflow logic.
7. **Dual-model reviews: specialize, don't duplicate.** Codex (orchestrator) = Product lens (spec fit, user scenarios, data integrity). Claude (secondary) = Technical lens (correctness, security, architecture). No overlapping roles.
8. **No secondary provider = two Codex agents.** Product (product-reviewer) + Technical (code-reviewer) via spawn_agent.
9. **One PR per sprint.** Execute silently after plan approval.
9a. **NEVER `gh pr merge --admin`.** If CI is red, fix CI first.
10. **Final Holistic Review — conditional.** Required when: ≥4 sprints, parallel execution, or governance_mode="critical". Skip for ≤3 linear sequential sprints in light/standard mode.
11. **Governance mode fixed for the run.**
12. **Orchestrator delegates investigation to subagents.** In Phase 2, orchestrator does NOT read source files >50 lines directly. Dispatch "deep-analyst" via spawn_agent and require a <2k-token summary. Exceptions: files <50 lines, state files, single-line status outputs.

## Secondary Provider Invocation (Claude as secondary)

```bash
$TIMEOUT_CMD 600 claude -p "PROMPT" 2>&1                                    # general
$TIMEOUT_CMD 600 claude -p "$(cat prompts/claude/code-reviewer.md)" 2>&1     # code review
$TIMEOUT_CMD 600 claude -p "$(cat prompts/claude/audit.md)" 2>&1             # security audit
# No secondary → two Codex agents with split focus (Product + Technical)
```

## Reasoning Tiers

| Tier | Codex Agent (spawn_agent) | Claude (secondary) | When |
|------|---------------------------|---------------------|------|
| **deep** | deep-* agents (gpt-5.4, high) | `claude -p` with prompts/claude/ | Phase 0 audit, Phase 1 spec review, Phase 2 holistic |
| **standard** | standard-* agents (gpt-5.4, high) | `claude -p` with prompts/claude/ | Phase 1 plan review, Phase 2 unified review, Phase 3 docs |
| **fast** | fast-implementer (gpt-5.4-mini, medium) | N/A | Simple implementation tasks |

## Phase Doc Routing

For each phase, read TWO files:
1. **Workflow logic**: `references/phase<N>*.md` (shared, Claude-native — ignore Agent() syntax)
2. **Dispatch patterns**: `references/codex/phase<N>*.md` (Codex-native — use these for actual dispatch)

## Test & Process Discipline

1. **One test process at a time.** Never run tests in parallel.
2. **Always wrap tests with timeout:** `$TIMEOUT_CMD 120 <test-command>`.
3. **Hanging test = unmocked external call.** Read the test, find the real call.
4. **Commit fixes before external review.** Claude secondary sees only committed HEAD.
5. **Exit worktree before merge.** `cd` to main repo root, remove worktree, THEN merge.

## Context Management (258K budget)

- Use `/compact` between sprints in Phase 2
- For 4+ sprints: consider session-per-sprint (`/clear` then `$superflow`)
- After compaction: ALWAYS re-read this file + `.superflow-state.json`
- Subagent contexts are discarded after return — use them to avoid bloating orchestrator context

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent via spawn_agent
- "Too simple for a worktree" → create worktree
- "One reviewer is enough" → check governance+complexity table
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → one PR per sprint
- "I'll just git merge locally" → use `gh pr merge --rebase --delete-branch`
- "I'll just quickly Read this file myself" → dispatch "deep-analyst" via spawn_agent

## Product Approval Gate

Before writing a spec, present Product Summary + Brief inline in the chat. The user must SEE full content before approving.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory.

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж".

**Phase 3 merge method:** Always `gh pr merge <number> --rebase --delete-branch`. NEVER local `git merge`.

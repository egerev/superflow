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
2. **Honor selected git workflow mode.** Read `context.git_workflow_mode` from `.superflow-state.json` before Phase 2 work. If missing, default to `sprint_pr_queue`. Valid modes: `solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, `trunk_based`. See `references/git-workflow-modes.md`.
2a. **Use isolated branches/worktrees.** For sprint-based modes, use `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. For `solo_single_pr`, use one `feat/<feature>` branch/worktree for the run. Verify `.worktrees/` is in `.gitignore` before creating.
3. **Hierarchical dispatch is allowed when configured.** Recommended Codex config is `[agents] max_threads=6, max_depth=2`. With `max_depth>=2`, the orchestrator may dispatch independent sprint supervisors in parallel; each sprint supervisor may spawn implement/review/doc agents for that sprint. If the runtime is still `max_depth=1`, fall back to flat sequential sprints and report that config upgrade is needed for sprint-level parallelism.
4. **Unified Review before every PR** (2 agents for standard/critical sprints; single Technical reviewer for light-mode sprints):
   1. Dispatch Claude Opus 4.7 as product reviewer: `$TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "PRODUCT_REVIEW_PROMPT" 2>&1`
   2. Use spawn_agent tool to dispatch Codex technical reviewer (agent: "standard-code-reviewer")
   3. Wait for both. Fix confirmed issues (NEEDS_FIXES, REQUEST_CHANGES, or FAIL). Re-review only flagging agent.
   4. Run mandatory sprint documentation update (`CLAUDE.md` + `llms.txt`) before PR creation. `llms.txt` must be explicitly checked on every sprint, even if unchanged.
   5. Run documentation review after the update/unchanged decision. It must verify `llms.txt` and `CLAUDE.md` reflect the sprint diff and contain no stale paths/commands.
   6. Write `.par-evidence.json`: `{"sprint":N,"claude_product":"ACCEPTED","technical_review":"APPROVE","docs_update":"UPDATED|UNCHANGED","docs_review":"PASS","provider":"claude-opus-4-7|split-focus","ts":"..."}`
   7. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists with review verdicts passing, `docs_update` set, and `docs_review` = `PASS`.
   8. Pass verdicts: APPROVE, ACCEPTED, PASS. Fail verdicts: REQUEST_CHANGES, NEEDS_FIXES, FAIL.
5. **Tests with evidence.** Paste actual output before claiming done.
6. **Re-read phase docs** at each sprint boundary. Read `references/codex/<phase>.md` for dispatch patterns, main `references/<phase>.md` for workflow logic.
7. **Dual-model reviews: specialize, don't duplicate.** Claude Opus 4.7 = Product lens (spec fit, user scenarios, data integrity). Codex = Technical lens (correctness, security, architecture). No overlapping roles.
8. **No secondary provider = two Codex agents.** Product (product-reviewer) + Technical (code-reviewer) via spawn_agent.
9. **PR policy follows git workflow mode.** `solo_single_pr` creates one final PR; `sprint_pr_queue`, `stacked_prs`, and `parallel_wave_prs` create PRs per sprint; `trunk_based` creates short-lived PRs per deployable slice. Execute silently after plan approval.
9a. **NEVER `gh pr merge --admin`.** If CI is red, fix CI first.
10. **Final Holistic Review — conditional.** Required when: ≥4 sprints, parallel execution, `git_workflow_mode` is `parallel_wave_prs` or `stacked_prs`, or governance_mode="critical". Skip for ≤3 linear sequential sprints in light/standard mode.
11. **Governance mode fixed for the run.**
12. **Orchestrator delegates investigation to subagents.** In Phase 2, orchestrator does NOT read source files >50 lines directly. Dispatch "deep-analyst" via spawn_agent and require a <2k-token summary. Exceptions: files <50 lines, state files, single-line status outputs.
13. **Event emission on state transition.** Call `sf_emit <event> [key=value...]` at every meaningful state change: `phase.start`, `stage.start`, `stage.complete`, `sprint.start`, `sprint.complete`, `compact.pre`, `compact.post`. Run the preloader block at the top of every phase doc bash usage before calling `sf_emit`. If `sf_emit` is unavailable after the preloader, events are silently dropped (no-op fallback) — this is intentional and must never cause a script error.

## Claude Product Reviewer Invocation

```bash
$TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "PROMPT" 2>&1
# No secondary → two Codex agents with split focus (Product + Technical)
```

## Reasoning Tiers

| Tier | Codex Agent (spawn_agent) | Claude (secondary) | When |
|------|---------------------------|---------------------|------|
| **deep** | deep analyst/implementer/reviewer agents (gpt-5.5, xhigh); deep-doc-writer (gpt-5.5, high) | `claude --model claude-opus-4-7 --effort xhigh -p` for product lens | Phase 0 audit, Phase 1 spec review, Phase 2 holistic |
| **standard** | standard-* agents (gpt-5.5, high) | `claude --model claude-opus-4-7 --effort xhigh -p` for product lens | Phase 1 plan review, Phase 2 unified review, Phase 3 docs |
| **fast** | fast-implementer (gpt-5.5, medium) | N/A | Simple implementation tasks |

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

- Use `/compact` between sequential sprints or after each completed sprint wave in Phase 2
- For 4+ sprints: consider session-per-wave (`/clear` then `$superflow`) when using sprint-level parallelism
- After compaction: ALWAYS re-read this file + `.superflow-state.json`
- Subagent contexts are discarded after return — use them to avoid bloating orchestrator context

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent via spawn_agent
- "Too simple for a worktree" → create worktree
- "One reviewer is enough" → check governance+complexity table
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → follow `context.git_workflow_mode`; one big PR is allowed only in `solo_single_pr`
- "I'll just git merge locally" → use `gh pr merge --rebase --delete-branch`
- "I'll just quickly Read this file myself" → dispatch "deep-analyst" via spawn_agent

## Product Approval Gate

Before writing a spec, present Product Summary + Brief inline in the chat. The user must SEE full content before approving.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory.

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж".

**Phase 3 merge method:** Always `gh pr merge <number> --rebase --delete-branch`. NEVER local `git merge`.

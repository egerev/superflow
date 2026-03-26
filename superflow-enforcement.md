# Superflow Enforcement

Survives context compaction. SKILL.md does not.

## Hard Rules

1. **Subagents write all code.** Orchestrator reads, plans, reviews, dispatches.
2. **Git worktrees per sprint.** `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. Verify `.worktrees/` is in `.gitignore` before creating (`git check-ignore -q .worktrees`).
3. **Unified Review before every PR** (2 agents, specialized: Claude=Product, Secondary=Technical):
   1. Dispatch Claude product reviewer (subagent_type: standard-product-reviewer). `run_in_background: true`
   2. Dispatch secondary technical reviewer: `$TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=high --ephemeral` (or Claude code-quality if no secondary)
   3. Wait for both. Fix confirmed issues (NEEDS_FIXES, REQUEST_CHANGES, or FAIL). Re-review only flagging agent.
   4. Write `.par-evidence.json`: `{"sprint":N,"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex|split-focus","ts":"..."}`
   5. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists with both verdicts passing.
   6. Pass verdicts: APPROVE, ACCEPTED, PASS. Fail verdicts: REQUEST_CHANGES, NEEDS_FIXES, FAIL.
4. **Tests with evidence.** Paste actual output before claiming done.
5. **Re-read phase docs** at each sprint boundary via Read tool.
6. **Dual-model reviews: specialize, don't duplicate.** Claude = Product lens (spec fit, user scenarios, data integrity). Secondary provider = Technical lens (correctness, security, architecture). Each model reviews what it's best at — no overlapping roles.
7. **No secondary provider = two Claude agents.** Product (product-reviewer) + Technical (code-quality-reviewer). Same split, same coverage, just both Claude.
8. **One PR per sprint.** Execute silently after plan approval.
9. **Final Holistic Review — conditional.** Required when: ≥4 sprints, parallel execution was used, or governance_mode="critical". Skip for ≤3 linear sequential sprints in light/standard mode. When required: two reviewers (Claude deep-product + Codex high technical, or 2 split-focus Claude) review ALL code as a unified system. Fix CRITICAL/HIGH before Completion Report. Per-sprint review misses cross-module issues.

## Secondary Provider Invocation

```bash
# Codex general (product review, audit, spec review):
$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=<LEVEL> "PROMPT_HERE" 2>&1

# Codex code review (uses built-in review mode + custom prompt):
$TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=<LEVEL> --ephemeral "CUSTOM_PROMPT" 2>&1

# Gemini: $TIMEOUT_CMD 600 gemini "PROMPT_HERE" 2>&1
# Other:  $TIMEOUT_CMD 600 $SECONDARY_PROVIDER <non-interactive-flag> "PROMPT_HERE" 2>&1
# None:   dispatch two Claude agents with split focus (Product + Technical)
```

## Reasoning Tiers

| Tier | Claude Agent (subagent_type) | Codex | When |
|------|-------------------------------|-------|------|
| **deep** | `deep-spec-reviewer`, `deep-code-reviewer`, `deep-product-reviewer`, `deep-analyst`, `deep-doc-writer`, `deep-implementer` (opus, effort: high) | `-c model_reasoning_effort=high` + `prompts/codex/` | Phase 0 audit+security, Phase 1 spec review, Phase 2 final holistic, llms.txt/CLAUDE.md generation |
| **standard** | `standard-spec-reviewer`, `standard-code-reviewer`, `standard-product-reviewer`, `standard-doc-writer`, `standard-implementer` (opus, effort: medium) | `-c model_reasoning_effort=high` + `prompts/codex/` | Phase 1 plan review, Phase 2 unified review, Phase 3 doc updates |
| **fast** | `fast-implementer` (sonnet, effort: low) | `-c model_reasoning_effort=medium` | Simple implementation tasks |

Agent definitions with effort frontmatter are deployed to `~/.claude/agents/` during SKILL.md startup checklist (step 8). The Agent() tool does NOT accept an inline `effort` parameter — effort is controlled via agent definition files only.

## Test & Process Discipline

1. **One test process at a time.** Never run tests in parallel or retry without killing the previous run.
2. **Always wrap tests with timeout:** `timeout 120 python3 -m unittest ...`. If timeout fires, investigate — don't retry.
3. **Hanging test = unmocked subprocess.** Read the test, find the real call. Re-running won't fix it.
4. **Commit fixes before external review.** Codex/secondary providers see only committed HEAD. Uncommitted fixes are invisible to them — they'll flag already-fixed issues.
5. **Exit worktree before merge.** `cd` to main repo root, remove worktree, THEN merge. CWD inside a worktree dies when branch is deleted.

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent
- "Too simple for a worktree" → create worktree
- "One reviewer is enough" → check governance+complexity table (light/simple = 1 reviewer, others = 2)
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → one PR per sprint
- "This sprint is too small for PAR" → run PAR
- "Per-sprint PAR is enough" → check if holistic is required (Rule 9 conditions)

## Product Approval Gate

Before writing a spec, present Product Summary (features, problems solved, out of scope). Wait for user approval.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory. Do not skip to Phase 1 without completing onboarding. See `references/phase0-onboarding.md`.

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж". Merge follows strict order: sequential, rebase, CI green, docs updated. See `references/phase3-merge.md`.

## Telegram Progress

When MCP connected: send short updates at sprint start, PR created, errors/blockers, completion. Acknowledge receipt before background work.

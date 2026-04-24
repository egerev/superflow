# Superflow Enforcement

Survives context compaction. SKILL.md does not.

## Hard Rules

1. **Subagents write all code.** Orchestrator reads, plans, reviews, dispatches.
2. **Honor selected git workflow mode.** Read `context.git_workflow_mode` from `.superflow-state.json` before Phase 2 work. If missing, default to `sprint_pr_queue`. Valid modes: `solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, `trunk_based`. See `references/git-workflow-modes.md`.
2a. **Use isolated branches/worktrees.** For sprint-based modes, use `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. For `solo_single_pr`, use one `feat/<feature>` branch/worktree for the run. Verify `.worktrees/` is in `.gitignore` before creating (`git check-ignore -q .worktrees`).
3. **Unified Review before every PR** (2 agents for standard/critical sprints; single Technical reviewer for light-mode sprints):
   1. Dispatch Claude product reviewer (subagent_type: standard-product-reviewer). `run_in_background: true`
   2. Dispatch secondary technical reviewer: `$TIMEOUT_CMD 600 codex exec review --base main -m gpt-5.5 -c model_reasoning_effort=high --ephemeral` (or Claude code-quality if no secondary)
   3. Wait for both. Fix confirmed issues (NEEDS_FIXES, REQUEST_CHANGES, or FAIL). Re-review only flagging agent.
   4. Run mandatory sprint documentation update (`CLAUDE.md` + `llms.txt`) before PR creation. `llms.txt` must be explicitly checked on every sprint, even if unchanged.
   5. Run documentation review after the update/unchanged decision. It must verify `llms.txt` and `CLAUDE.md` reflect the sprint diff and contain no stale paths/commands.
   6. Write `.par-evidence.json`: `{"sprint":N,"claude_product":"ACCEPTED","technical_review":"APPROVE","docs_update":"UPDATED|UNCHANGED","docs_review":"PASS","provider":"codex|split-focus","ts":"..."}`
   7. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists with review verdicts passing, `docs_update` set, and `docs_review` = `PASS`.
   8. Pass verdicts: APPROVE, ACCEPTED, PASS. Fail verdicts: REQUEST_CHANGES, NEEDS_FIXES, FAIL.
4. **Tests with evidence.** Paste actual output before claiming done.
5. **Re-read phase docs** at each sprint boundary via Read tool.
6. **Dual-model reviews: specialize, don't duplicate.** Claude = Product lens (spec fit, user scenarios, data integrity). Secondary = Technical lens (correctness, security, architecture). No overlapping roles.
7. **No secondary provider = two Claude agents.** Product (product-reviewer) + Technical (code-quality-reviewer).
8. **PR policy follows git workflow mode.** `solo_single_pr` creates one final PR; `sprint_pr_queue`, `stacked_prs`, and `parallel_wave_prs` create PRs per sprint; `trunk_based` creates short-lived PRs per deployable slice. Execute silently after plan approval.
8a. **NEVER `gh pr merge --admin`.** If CI is red, fix CI first. After every `gh pr create`, run `gh run list` and wait for CI green before merging. If CI fails, investigate with `gh run view <id> --log-failed`, fix, push, wait for green.
9. **Final Holistic Review — conditional.** Required when: ≥4 sprints, parallel execution, `git_workflow_mode` is `parallel_wave_prs` or `stacked_prs`, or governance_mode="critical". Skip for ≤3 linear sequential sprints in light/standard mode. When required: two reviewers (Claude deep-product + Codex high technical, or 2 split-focus Claude) review ALL code as a unified system. Fix CRITICAL/HIGH before Completion Report.
10. **Governance mode fixed for the run.** Replanner adjusts sprint scope, not governance mode. Once selected in Phase 1 Step 2, the mode persists through all sprints in the run.
11. **Orchestrator delegates investigation to subagents.** In Phase 2 the orchestrator does NOT use Read/Grep/Glob directly on source files larger than 50 lines, and does NOT use Bash for anything beyond: status checks (`git status`, `gh run list`, `gh pr view`, `ls`, `pwd`, `which`, `date`), state I/O (`.superflow-state.json`, `.par-evidence.json`, CHANGELOG appends), and short `echo`/`printf` for user-visible progress. Any code reading, codebase exploration, research, or investigation → dispatch `deep-analyst` (or `standard-implementer` for lighter work) and require a <2k-token summary in response. Raw file contents do not belong in the orchestrator's context. See `references/phase2-execution.md` § Orchestrator Tool Budget. **In Codex runtime:** `spawn_agent` replaces `Agent()`. Same budget rules apply. See `references/codex-dispatch-patterns.md`.
13. **Event emission on state transition.** Every state transition (stage change, sprint boundary, phase boundary, review verdict, PR create/merge, test run) emits a matching event via `sf_emit <type> key=value...`. See `tools/sf-emit.sh` (library) and `templates/event-schema.json` (schema contract). `.superflow-state.json` remains authoritative; events are derived telemetry. sf-emit rejects unknown types at the library layer — do not invent types outside the schema.
12. **Heartbeat check every orchestrator turn.** If a `heartbeat` block exists in `.superflow-state.json`, check `heartbeat.must_reread` before any tool call that advances work. "In current context" means the file was Read earlier in this conversation/session and its content is visible in the current transcript. For each listed path: if already in context → skip; if missing from context → Read it immediately (short rule/charter files are always allowed under Rule 11 exceptions). If a listed file does not exist on disk, skip it silently and emit a one-line warning. If `heartbeat.updated_at` is >30 min old, emit a fresh heartbeat snapshot. Heartbeat is defense against compaction drift — skipping it defeats Rule 5 (re-read phase docs at sprint boundaries). **`must_reread` MUST contain ONLY short orchestration files** (enforcement rules, charter, the phase2 router — all <300 lines, always allowed under Rule 11). Long source files MUST NEVER appear in `must_reread` — if code understanding is needed post-compaction, dispatch `deep-analyst`, not a direct Read.

## Secondary Provider Invocation

**When Claude is orchestrator (RUNTIME:claude):**
```bash
$TIMEOUT_CMD 600 codex exec --full-auto -m gpt-5.5 -c model_reasoning_effort=<LEVEL> "PROMPT" 2>&1          # general
$TIMEOUT_CMD 600 codex exec review --base main -m gpt-5.5 -c model_reasoning_effort=<LEVEL> --ephemeral "PROMPT" 2>&1  # code review
$TIMEOUT_CMD 600 gemini "PROMPT" 2>&1                                                             # Gemini
$TIMEOUT_CMD 600 $SECONDARY_PROVIDER <non-interactive-flag> "PROMPT" 2>&1                        # Other
# No secondary → two Claude agents with split focus (Product + Technical)
```

**When Codex is orchestrator (RUNTIME:codex):**
```bash
$TIMEOUT_CMD 600 claude -p "PROMPT" 2>&1                                                          # general
$TIMEOUT_CMD 600 claude -p "$(cat prompts/claude/code-reviewer.md) DIFF_CONTEXT" 2>&1             # code review
# No secondary → two Codex agents with split focus via spawn_agent (Product + Technical)
```
See `references/codex-dispatch-patterns.md` for the complete dispatch mapping.

## Reasoning Tiers

| Tier | Claude Agent (subagent_type) | Codex | When |
|------|-------------------------------|-------|------|
| **deep** | `deep-spec-reviewer`, `deep-code-reviewer`, `deep-product-reviewer`, `deep-analyst`, `deep-doc-writer` (opus, effort: high); `deep-implementer` (sonnet, effort: high) | `-m gpt-5.5 -c model_reasoning_effort=high` + `prompts/codex/` | Phase 0 audit+security, Phase 1 spec review, Phase 2 final holistic, llms.txt/CLAUDE.md generation |
| **standard** | `standard-spec-reviewer`, `standard-code-reviewer`, `standard-product-reviewer`, `standard-doc-writer` (opus, effort: medium); `standard-implementer` (sonnet, effort: medium) | `-m gpt-5.5 -c model_reasoning_effort=high` + `prompts/codex/` | Phase 1 plan review, Phase 2 unified review, Phase 3 doc updates |
| **fast** | `fast-implementer` (sonnet, effort: low) | `-m gpt-5.5 -c model_reasoning_effort=medium` | Simple implementation tasks |

Agent definitions with effort frontmatter are deployed to `~/.claude/agents/` during SKILL.md startup (step 3). Agent() does NOT accept inline `effort` — controlled via agent definition files only.

**CRITICAL: Always pass `model:` explicitly in every Agent() call.** Frontmatter `model:` in agent definitions is NOT reliably inherited — without explicit `model:`, subagents inherit the parent's model (Opus), burning expensive tokens on implementation tasks. Rule: implementers and doc-writers → `model: "sonnet"`, reviewers and analysts → `model: "opus"`.

## Test & Process Discipline

1. **One test process at a time.** Never run tests in parallel or retry without killing the previous run.
2. **Always wrap tests with timeout:** `timeout 120 <test-command>`. If timeout fires, investigate — don't retry.
3. **Hanging test = unmocked external call.** Read the test, find the real call. Re-running won't fix it.
4. **Commit fixes before external review.** Secondary providers see only committed HEAD — uncommitted fixes are invisible.
5. **Exit worktree before merge.** `cd` to main repo root, remove worktree, THEN merge. CWD inside a worktree dies when branch is deleted.

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent
- "Too simple for a worktree" → create worktree
- "One reviewer is enough" → check governance+complexity table (light/simple = 1 reviewer, others = 2)
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → follow `context.git_workflow_mode`; one big PR is allowed only in `solo_single_pr`
- "This sprint is too small for PAR" → run PAR
- "Per-sprint PAR is enough" → check if holistic is required (Rule 9 conditions)
- "I'll just git merge locally" → use `gh pr merge --rebase --delete-branch`
- "CI is broken but my tests pass locally" → fix CI first, then merge
- "I'll use --admin to bypass CI" → NEVER. Fix the CI failure. Branch protection is there for a reason.
- "I'll emit the event later" → emit immediately on the transition, before the next tool call
- "I'll just quickly Read this file myself" → dispatch `deep-analyst` with the specific question; take the summary back
- "It's just one Grep" → if the result could be >50 lines or context is already >60% of budget, dispatch instead

## Product Approval Gate

Before writing a spec, present Product Summary + Brief **inline in the chat** (not just save to file). The user must SEE full content before approving — this is the last meaningful gate before autonomous execution. Same rule applies to Step 12 (plan approval): display full plan summary inline. Never ask for approval on content the user hasn't seen.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory. Do not skip to Phase 1 without completing onboarding. `references/phase0-onboarding.md`

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж". Merge follows strict order: sequential, rebase, CI green, docs updated. `references/phase3-merge.md`

**Phase 3 merge method:** Always `gh pr merge <number> --rebase --delete-branch`. NEVER use local `git merge` — it leaves GitHub PRs open and creates merge commits instead of linear history. Re-read `references/phase3-merge.md` before each PR merge if context was compacted.

## Telegram Progress

When MCP connected: send short updates at sprint start, PR created, errors/blockers, completion. Acknowledge receipt before background work.

# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.

## Per-Sprint Flow

1. **Re-read** this file (`references/phase2-execution.md`) and the current sprint's SPEC (from the plan in `docs/superflow/specs/` or `docs/superflow/plans/`)
2. **Telegram update** (if MCP connected): "Starting sprint N: [title]"
3. **Worktree**: verify `.worktrees/` is gitignored (`git check-ignore -q .worktrees || echo '.worktrees/' >> .gitignore`), then `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`
4. **Baseline tests** in worktree: run full test suite, record output. If tests fail on baseline, stop and report — do not build on a broken base.
5. **Dispatch implementers** — model from plan's sprint complexity tag:
   - `simple` → `Agent(subagent_type: "fast-implementer")` (sonnet, effort: low)
   - `medium` → `Agent(subagent_type: "standard-implementer")` (sonnet, effort: medium). Orchestrator may escalate to `deep-implementer` (opus) on 2+ failures.
   - `complex` → `Agent(subagent_type: "deep-implementer")` (opus, effort: high)
   - If `complexity` is absent in plan, default to `medium`.
   Include `llms.txt` content in agent context (if exists) — this gives implementers project architecture understanding.
   Parallelize independent tasks, sequentialize dependent ones.
6. **Unified Review** (4 agents parallel, Reasoning: Standard tier):
   All agents receive: the SPEC, the product brief, and the relevant git diff.

   First, check Codex availability: `codex --version 2>/dev/null`

   If Codex available:
   a. Claude code-quality reviewer: `Agent(subagent_type: "standard-code-reviewer", run_in_background: true, prompt: "[SPEC + diff context]")`
   b. Claude product reviewer: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "[SPEC + brief + diff context]")`
   c. Codex code reviewer: `$TIMEOUT_CMD 600 codex exec review -c model_reasoning_effort=high --ephemeral - < <(echo "SPEC_CONTEXT" | cat - prompts/codex/code-reviewer.md) 2>&1` (run_in_background)
   d. Codex product reviewer: `$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=high --ephemeral "$(cat prompts/codex/product-reviewer.md) SPEC: [spec content]" 2>&1` (run_in_background)

   If Codex NOT available (split-focus fallback):
   a. Claude code-quality: `Agent(subagent_type: "standard-code-reviewer", run_in_background: true)`
   b. Claude product: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true)`
   c. Claude architecture: `Agent(subagent_type: "standard-spec-reviewer", run_in_background: true, prompt: "Focus: spec compliance, architecture")`
   d. Claude UX: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "Focus: user scenarios, edge cases")`
   Record `"provider": "split-focus"` in .par-evidence.json.

   Wait for all 4. Aggregate findings:
   - CRITICAL/REQUEST_CHANGES from any agent = fix required
   - Deduplicate: if multiple agents flag the same file:line, keep the most severe, note consensus
   - Fix confirmed issues. Re-run only the agents that flagged issues.
   - If a finding is incorrect (reviewer lacked context), record disagreement with reasoning and skip.
7. **Post-review test verification + PAR evidence**:
   Run full test suite after all review fixes. Paste actual output as evidence (enforcement rule 4).
   Write `.par-evidence.json` in worktree root:
   ```json
   {
     "sprint": N,
     "claude_code": "APPROVE",
     "claude_product": "ACCEPTED",
     "codex_code": "APPROVE",
     "codex_product": "ACCEPTED",
     "provider": "codex",
     "ts": "ISO-8601"
   }
   ```
   All 4 verdicts must be APPROVE/ACCEPTED/PASS. If any agent returned issues, they must be fixed and the agent re-run before evidence is written.
8. **Push + PR**: verify `.par-evidence.json` exists with 4 passing verdicts. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
9. **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
10. **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

## Sprint Completion Checklist

Before creating the PR, verify ALL:
- [ ] Worktree created and work done in isolation
- [ ] Implementation dispatched to subagents (not written by orchestrator)
- [ ] Unified review completed: 4 agents, all APPROVE/ACCEPTED
- [ ] Full test suite passes with pasted evidence
- [ ] `.par-evidence.json` written with 4 passing verdicts
- [ ] PR created with `--base main`
- [ ] Worktree cleaned up

## Adaptive Implementation Model

Sprint complexity drives model selection. Tag each sprint in the plan:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | medium | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | opus | high | 5+ files, new architecture, security-sensitive |

## Review Optimization (Unified Review)

All sprints receive the full 4-agent unified review. The agent count is always 4.
What changes by sprint complexity is the SCOPE each reviewer examines:

- Simple (1-2 files, <50 lines): reviewers check only changed files + their tests
- Medium (2-5 files): reviewers check changed files + integration points with unchanged code
- Complex (5+ files): reviewers check changed files + cross-module impact + architectural fit

## No Secondary Provider

When Codex/secondary is unavailable, dispatch 4 Claude agents with split focus:
- Agent A (Technical): `subagent_type: "standard-code-reviewer"` — correctness, security, performance
- Agent B (Product): `subagent_type: "standard-product-reviewer"` — spec fit, user scenarios, data integrity
- Agent C (Architecture): `subagent_type: "standard-spec-reviewer"` — spec compliance, architecture, cross-module consistency
- Agent D (UX): `subagent_type: "standard-product-reviewer"` — focus prompt on user scenarios, edge states, error handling

Record: `{"provider":"split-focus","claude_code":"APPROVE","claude_product":"ACCEPTED","claude_architecture":"PASS","claude_ux":"ACCEPTED","ts":"..."}`

## Failure & Debugging

1. Read failure output. Identify the failing assertion or error.
2. Form a hypothesis before touching code.
3. Targeted fix, then verify with the specific test, then the full suite.
4. 3+ failed attempts on the same issue: likely architectural problem. Report BLOCKED with evidence, suggest rethinking approach.
5. Agent blocked: re-dispatch with more context. 2 fails on same agent task = implement manually.
6. Never stop to ask the user. Accumulate issues, report at end.

## Handling NEEDS_FIXES from Unified Review

- Verify each finding against the codebase before implementing (reviewer may lack context)
- If a finding is incorrect (reviewer lacked context), record disagreement with technical reasoning in the PR description and skip that fix
- Fix confirmed issues one at a time, test each
- Re-run only the agents that flagged issues, not all 4

## Final Holistic Review (after all sprints)

After all sprint PRs created, before Completion Report. Reasoning: Deep tier.
All agents review ALL code across ALL sprints as a unified system.

Check Codex availability first. If available:
a. Claude Technical: `Agent(subagent_type: "deep-code-reviewer", run_in_background: true, prompt: "Review ALL sprint changes. Focus: cross-module dependencies, architectural consistency, security across the full feature.")`
b. Claude Product: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review ALL sprint changes. Focus: end-to-end user flows, data integrity across sprints.")`
c. Codex Technical: `$TIMEOUT_CMD 900 codex exec review -c model_reasoning_effort=xhigh --ephemeral "Review all changes across all sprints for cross-module issues, architecture, security." 2>&1`
d. Codex Product: `$TIMEOUT_CMD 900 codex exec --full-auto -c model_reasoning_effort=xhigh --ephemeral "Product review all changes. Check end-to-end flows, data integrity, UX across all sprints." 2>&1`

If no Codex: 4 split-focus Claude agents (Technical-Architecture, Technical-Security, Product-UX, Product-Data), all using deep-tier agent definitions.

Fix CRITICAL/HIGH issues before Completion Report.

## Supervisor Mode (Long-Running)

For tasks with 3+ sprints that should run unattended (overnight, multi-hour):

1. Phase 1 creates the sprint queue: `docs/superflow/sprint-queue.json`
2. User launches supervisor in a separate terminal: `./bin/superflow-supervisor run --queue docs/superflow/sprint-queue.json --plan docs/superflow/plans/<plan-file>.md`
3. Supervisor executes each sprint as a fresh Claude Code session (no context degradation)
4. Each sprint follows the same Per-Sprint Flow above (the 10-step flow), but orchestrated by the supervisor
5. Supervisor handles: retries, parallel execution, adaptive replanning, checkpoint/resume

**When to use supervisor vs single-session:**
- 1-2 sprints → single-session (this file's normal flow)
- 3+ sprints → supervisor recommended
- Overnight/unattended → supervisor required

**Key difference:** In supervisor mode, the supervisor creates the worktree and sets the working directory. The Claude session inside does NOT create its own worktree.

## Completion Report (Demo Day Format)

Present a product-oriented summary — like a demo day, not a tech log. For each sprint:

### Per-Sprint Block
- **Sprint N: [Product-level title]** (e.g., "Inline Transaction Editing")
  - What it does for the user (1-2 sentences, product language)
  - Key changes: bullet list of user-visible features/improvements
  - PR: `#NNN` — link, status (open/merged), CI status
  - Unified Review: all 4 agents APPROVE/ACCEPTED (if issues: reason + evidence)
  - Tests: count (passed/failed/skipped)

### Summary Section
- Total PRs: N
- All tests passing: yes/no
- Blocked sprints: N (with reasons, if any)
- Known issues or follow-ups (if any)
- **Merge order** (sequential, with dependencies noted)
- Suggested next action: "Ready to merge — say 'merge' to start Phase 3"

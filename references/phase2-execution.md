# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.

## Per-Sprint Flow

1. **Re-read** this file (`references/phase2-execution.md`) and the current sprint's SPEC (from the plan in `docs/superflow/specs/` or `docs/superflow/plans/`)
2. **Telegram update** (if MCP connected): "Starting sprint N: [title]"
3. **Worktree**: verify `.worktrees/` is gitignored (`git check-ignore -q .worktrees || echo '.worktrees/' >> .gitignore`), then `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`
4. **Baseline tests** in worktree: run full test suite, record output. If tests fail on baseline, stop and report — do not build on a broken base.
5. **Dispatch implementers** via Agent tool (`model: sonnet` for mechanical tasks; permissions are handled by `settings.json` from Phase 0 Step 7). Use `prompts/implementer.md`. Include `llms.txt` content in agent context (if exists) — this gives implementers project architecture understanding.
   - **Parallelize** when tasks are independent (different files, no shared state, no dependencies)
   - **Sequentialize** when tasks share files, state, or depend on each other's output
6. **Internal review** (pre-PAR, scale by complexity — see Review Optimization below):
   - Dispatch spec reviewer (`prompts/spec-reviewer.md`, `run_in_background: true`)
   - Dispatch code quality reviewer (`prompts/code-quality-reviewer.md`, `run_in_background: true`) — skip for Simple sprints
   - Both run in parallel. Wait for both. Fix any FAIL/REQUEST_CHANGES findings before proceeding.
   - Verify tests still pass after fixes.
7. **Post-review test verification**: run full test suite after all review fixes are applied. Paste actual output as evidence (enforcement rule 4). All tests must pass before proceeding to PAR.
8. **PAR** (see enforcement rules for algorithm):
   - Claude reviewer: use `prompts/spec-reviewer.md` focus (spec compliance, security, architecture). `run_in_background: true`
   - Secondary provider: use `prompts/product-reviewer.md` focus (product fit, UX gaps, edge cases). `$TIMEOUT_CMD 600`
   - Both receive the SPEC. Wait for both. Fix NEEDS_FIXES, re-review.
   - Write `.par-evidence.json` in the worktree root after both ACCEPTED.
9. **Push + PR**: verify `.par-evidence.json` exists. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
10. **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
11. **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

## Sprint Completion Checklist

Before creating the PR, verify ALL:
- [ ] Worktree created and work done in isolation
- [ ] Implementation dispatched to subagents (not written by orchestrator)
- [ ] Internal review completed (per Review Optimization tier)
- [ ] Full test suite passes with pasted evidence
- [ ] PAR completed: `.par-evidence.json` written with both ACCEPTED
- [ ] PR created with `--base main`
- [ ] Worktree cleaned up

## Review Optimization (Pre-PAR)

This controls the internal review chain BEFORE PAR. **PAR itself is always mandatory** (see enforcement rules).

- Simple (1-2 files, <50 lines): spec review only, then PAR
- Medium (2-5 files): spec review + code quality review, then PAR
- Complex (5+ files): spec review + code quality review + product review, then PAR

## No Secondary Provider

Dispatch two Claude agents (enforcement rule 7):
- Agent A (Technical): spec compliance, security, architecture, correctness (`prompts/spec-reviewer.md`, `run_in_background: true`)
- Agent B (Product): product fit, UX gaps, edge cases, data integrity (`prompts/product-reviewer.md`, `run_in_background: true`)
Record: `{"provider":"split-focus","claude_technical":"ACCEPTED","claude_product":"ACCEPTED","ts":"..."}`

## Failure & Debugging

1. Read failure output. Identify the failing assertion or error.
2. Form a hypothesis before touching code.
3. Targeted fix, then verify with the specific test, then the full suite.
4. 3+ failed attempts on the same issue: likely architectural problem. Report BLOCKED with evidence, suggest rethinking approach.
5. Agent blocked: re-dispatch with more context. 2 fails on same agent task = implement manually.
6. Never stop to ask the user. Accumulate issues, report at end.

## Handling NEEDS_FIXES from PAR

- Verify each finding against the codebase before implementing (reviewer may lack context)
- If a finding is incorrect (reviewer lacked context), record disagreement with technical reasoning in the PR description and skip that fix
- Fix confirmed issues one at a time, test each
- Re-run PAR after fixes

## Completion Report (Demo Day Format)

Present a product-oriented summary — like a demo day, not a tech log. For each sprint:

### Per-Sprint Block
- **Sprint N: [Product-level title]** (e.g., "Inline Transaction Editing")
  - What it does for the user (1-2 sentences, product language)
  - Key changes: bullet list of user-visible features/improvements
  - PR: `#NNN` — link, status (open/merged), CI status
  - PAR: ACCEPTED/NEEDS_FIXES/BLOCKED (if blocked: reason + evidence)
  - Tests: count (passed/failed/skipped)

### Summary Section
- Total PRs: N
- All tests passing: yes/no
- Blocked sprints: N (with reasons, if any)
- Known issues or follow-ups (if any)
- **Merge order** (sequential, with dependencies noted)
- Suggested next action: "Ready to merge — say 'merge' to start Phase 3"

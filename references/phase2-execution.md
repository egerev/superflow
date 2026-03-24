# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.

## Stage Structure (Per Sprint)

Each sprint passes through 5 stages. Use TaskCreate at sprint start, TaskUpdate as todos complete.

```
Stage 1: "Setup"
  Todos:
  - "Re-read phase docs"
  - "Send Telegram update"
  - "Create worktree"
  - "Run baseline tests"

Stage 2: "Implementation"
  Todos:
  - "Dispatch implementer(s)"
  - "Collect results"

Stage 3: "Review"
  Todos:
  - "Internal review (spec + code quality)"
  - "Fix review findings"
  - "Post-review test verification"

Stage 4: "PAR"
  Todos:
  - "Dispatch Claude reviewer"
  - "Dispatch secondary provider reviewer"
  - "Fix NEEDS_FIXES (if any)"
  - "Write .par-evidence.json"

Stage 5: "Ship"
  Todos:
  - "Push and create PR"
  - "Verify PR created"
  - "Cleanup worktree"
  - "Send Telegram update"
```

### State Management

During Phase 2 with supervisor, the supervisor writes `.superflow-state.json` — the Claude session does NOT write it directly. During Phase 2 without supervisor (single-session), initialize state at the start of Phase 2:

```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":2,"phase_label":"Autonomous Execution","stage":"setup","stage_index":0,"sprint":1,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
```

Then update at each stage transition:

```bash
python3 -c "import json,datetime,sys; s=json.load(open('.superflow-state.json')); s['stage']='implementation'; s['stage_index']=1; s['sprint']=int(sys.argv[1]); s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)" "$SPRINT_NUM"
# Replace $SPRINT_NUM with the actual sprint number (e.g., 1, 2, 3)
```

### TaskCreate/TaskUpdate Pattern

```
# At sprint start:
TaskCreate(
  title: "Sprint N: [title] — Setup",
  description: "Prepare worktree and baseline",
  todos: [
    "Re-read phase docs",
    "Send Telegram update",
    "Create worktree",
    "Run baseline tests"
  ]
)

# As each todo completes:
TaskUpdate(id: <task_id>, todo_updates: [
  {index: 0, status: "completed"}
])

# When stage completes, create next stage task:
TaskUpdate(id: <task_id>, status: "completed")
TaskCreate(
  title: "Sprint N: [title] — Implementation",
  ...
)
```

---

## Parallel Dispatch within a Sprint

When a sprint has multiple tasks, analyze them for parallelism before dispatching.

**Independence criteria** (ALL must hold for parallel dispatch):
1. Tasks modify different files (no overlapping file paths)
2. No data dependency (Task B doesn't read output of Task A)
3. No shared state (no common database table, config, or global variable)
4. No ordering constraint (either can complete first)

**Wave analysis:**
1. List files each task modifies
2. Build dependency graph from file overlaps and explicit `depends_on`
3. Group tasks into waves — tasks in the same wave are independent
4. Dispatch each wave: all tasks in wave via `Agent(run_in_background: true)`
5. Wait for wave to complete before dispatching next wave

**Example:** 6 tasks → Wave 1: tasks 1,2,3 (independent files) → Wave 2: task 4 (depends on 1) → Wave 3: tasks 5,6 (independent)

**Fallback:** If ≤3 tasks in the sprint, skip wave analysis and dispatch sequentially. The overhead of parallelism isn't worth it for small task counts.

**After all waves:** Verify no file conflicts by checking `git status` — if two agents modified the same file, resolve manually.

---

## Per-Sprint Flow

1. <!-- Stage 1: Setup, Todo 1 --> **Re-read** this file (`references/phase2-execution.md`) and the current sprint's SPEC (from the plan in `docs/superflow/specs/` or `docs/superflow/plans/`)
2. <!-- Stage 1: Setup, Todo 2 --> **Telegram update** (if MCP connected): "Starting sprint N: [title]"
3. <!-- Stage 1: Setup, Todo 3 --> **Worktree**: verify `.worktrees/` is gitignored (`git check-ignore -q .worktrees || echo '.worktrees/' >> .gitignore`), then `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`
4. <!-- Stage 1: Setup, Todo 4 --> **Baseline tests** in worktree: run full test suite, record output. If tests fail on baseline, stop and report — do not build on a broken base.
5. <!-- Stage 2: Implementation, Todos 1-2 --> **Dispatch implementers** — see Parallel Dispatch section above for wave analysis.
   - 5a. Analyze task list — identify independent tasks (see Parallel Dispatch above)
   - 5b. Group into waves
   - 5c. For Wave 1: dispatch each as `Agent(run_in_background: true, model: sonnet)`. Use `prompts/implementer.md`. Include `llms.txt` content in agent context.
   - 5d. For subsequent waves: same pattern
   - 5e. After all waves: verify no file conflicts with `git status`
6. <!-- Stage 3: Review, Todo 1 --> **Internal review** (pre-PAR, scale by complexity — see Review Optimization below):
   - Dispatch spec reviewer (`prompts/spec-reviewer.md`, `run_in_background: true`)
   - Dispatch code quality reviewer (`prompts/code-quality-reviewer.md`, `run_in_background: true`) — skip for Simple sprints
   - Both run in parallel. Wait for both. Fix any FAIL/REQUEST_CHANGES findings before proceeding.
   - Verify tests still pass after fixes.
7. <!-- Stage 3: Review, Todos 2-3 --> **Post-review test verification**: run full test suite after all review fixes are applied. Paste actual output as evidence (enforcement rule 4). All tests must pass before proceeding to PAR.
8. <!-- Stage 4: PAR, Todos 1-4 --> **PAR** (see enforcement rules for algorithm):
   - Claude reviewer: use `prompts/spec-reviewer.md` focus (spec compliance, security, architecture). `run_in_background: true`
   - Secondary provider: use `prompts/product-reviewer.md` focus (product fit, UX gaps, edge cases). `$TIMEOUT_CMD 600`
   - Both receive the SPEC. Wait for both. Fix NEEDS_FIXES, re-review.
   - Write `.par-evidence.json` in the worktree root after both ACCEPTED.
9. <!-- Stage 5: Ship, Todos 1-2 --> **Push + PR**: verify `.par-evidence.json` exists. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
10. <!-- Stage 5: Ship, Todo 3 --> **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
11. <!-- Stage 5: Ship, Todo 4 --> **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

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

## Supervisor Mode (Long-Running)

For tasks with 3+ sprints that should run unattended (overnight, multi-hour):

1. Phase 1 creates the sprint queue: `docs/superflow/sprint-queue.json`
2. User launches supervisor in a separate terminal: `./bin/superflow-supervisor run --queue docs/superflow/sprint-queue.json --plan docs/superflow/plans/<plan-file>.md`
3. Supervisor executes each sprint as a fresh Claude Code session (no context degradation)
4. Each sprint follows the same Per-Sprint Flow above, but orchestrated by the supervisor
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
  - PAR: ACCEPTED/NEEDS_FIXES/BLOCKED (if blocked: reason + evidence)
  - Tests: count (passed/failed/skipped)

### Summary Section
- Total PRs: N
- All tests passing: yes/no
- Blocked sprints: N (with reasons, if any)
- Known issues or follow-ups (if any)
- **Merge order** (sequential, with dependencies noted)
- Suggested next action: "Ready to merge — say 'merge' to start Phase 3"

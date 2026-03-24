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
5. <!-- Stage 2: Implementation, Todos 1-2 --> **Dispatch implementers** — model from plan's sprint complexity tag (see Adaptive Implementation Model below), wave analysis for parallelism (see Parallel Dispatch above).
   - 5a. Analyze task list — identify independent tasks
   - 5b. Group into waves
   - 5c. For Wave 1: dispatch each as `Agent(run_in_background: true)` with appropriate implementer tier
   - 5d. For subsequent waves: same pattern
   - 5e. After all waves: verify no file conflicts with `git status`
   Include `llms.txt` content in agent context (if exists).
6. <!-- Stage 3: Review, Todos 1-3 --> **Unified Review** (4 agents parallel, Reasoning: Standard tier):
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
7. <!-- Stage 4: PAR, Todos 1-4 --> **Post-review test verification + PAR evidence**:
   Run full test suite after all review fixes. Paste actual output as evidence (enforcement rule 4).
   Write `.par-evidence.json` in worktree root:
   ```json
   {
     "sprint": N,
     "claude_code_quality": "APPROVE",
     "claude_product": "ACCEPTED",
     "codex_code_review": "APPROVE",
     "codex_product": "ACCEPTED",
     "provider": "codex",
     "ts": "ISO-8601"
   }
   ```
   All 4 verdicts must be APPROVE/ACCEPTED/PASS. If any agent returned issues, they must be fixed and the agent re-run before evidence is written.
8. <!-- Stage 5: Ship, Todos 1-2 --> **Push + PR**: verify `.par-evidence.json` exists with 4 passing verdicts. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
9. <!-- Stage 5: Ship, Todo 3 --> **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
10. <!-- Stage 5: Ship, Todo 4 --> **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

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

Record: `{"provider":"split-focus","claude_code_quality":"APPROVE","claude_product":"ACCEPTED","codex_code_review":"APPROVE","codex_product":"ACCEPTED","ts":"..."}`

Agent-to-key mapping: Agent A (Technical) -> `claude_code_quality`, Agent B (Product) -> `claude_product`, Agent C (Architecture) -> `codex_code_review`, Agent D (UX) -> `codex_product`. This ensures the gate always checks the same 4 keys regardless of provider.

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

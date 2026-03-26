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
6. <!-- Stage 3: Review, Todos 1-3 --> **Unified Review** (2 specialized agents parallel, Reasoning: Standard tier):
   Both agents receive: the SPEC, the product brief, and the relevant git diff.
   Principle: **specialize, don't duplicate** — Claude = Product lens, secondary = Technical lens.

   First, check Codex availability: `codex --version 2>/dev/null`

   If Codex available:
   a. Claude product reviewer: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "[SPEC + brief + diff context]")`
   b. Codex technical reviewer: `$TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=high --ephemeral - < <(echo "SPEC_CONTEXT" | cat - prompts/codex/code-reviewer.md) 2>&1` (run_in_background)

   If Codex NOT available (split-focus fallback — 2 Claude agents):
   a. Claude product: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "Focus: spec fit, user scenarios, data integrity")`
   b. Claude technical: `Agent(subagent_type: "standard-code-reviewer", run_in_background: true, prompt: "Focus: correctness, security, architecture, performance")`
   Record `"provider": "split-focus"` in .par-evidence.json.

   Wait for both. Aggregate findings:
   - CRITICAL/REQUEST_CHANGES from either agent = fix required
   - Fix confirmed issues. Re-run only the agent that flagged issues.
   - If a finding is incorrect (reviewer lacked context), record disagreement with reasoning and skip.
7. <!-- Stage 4: PAR, Todos 1-4 --> **Post-review test verification + PAR evidence**:
   Run full test suite after all review fixes. Paste actual output as evidence (enforcement rule 4).
   Write `.par-evidence.json` in worktree root:
   ```json
   {
     "sprint": N,
     "claude_product": "ACCEPTED",
     "technical_review": "APPROVE",
     "provider": "codex",
     "ts": "ISO-8601"
   }
   ```
   Both verdicts must be APPROVE/ACCEPTED/PASS. If either agent returned issues, they must be fixed and the agent re-run before evidence is written.
8. <!-- Stage 5: Ship, Todos 1-2 --> **Push + PR**: verify `.par-evidence.json` exists with both verdicts passing. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
9. <!-- Stage 5: Ship, Todo 3 --> **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
10. <!-- Stage 5: Ship, Todo 4 --> **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

## Sprint Completion Checklist

Before creating the PR, verify ALL:
- [ ] Worktree created and work done in isolation
- [ ] Implementation dispatched to subagents (not written by orchestrator)
- [ ] Unified review completed: 2 agents (Product + Technical), both APPROVE/ACCEPTED
- [ ] Full test suite passes with pasted evidence
- [ ] `.par-evidence.json` written with both verdicts passing
- [ ] PR created with `--base main`
- [ ] Worktree cleaned up

## Adaptive Implementation Model

Sprint complexity drives model selection. Tag each sprint in the plan:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | medium | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | opus | high | 5+ files, new architecture, security-sensitive |

## Review Tiering by Governance Mode

Reviewer count depends on governance mode and sprint complexity:

| Governance | Complexity | Reviewers |
|-----------|-----------|-----------|
| light | any | 1 (Technical only) |
| standard | simple | 1 (Technical only) |
| standard | medium/complex | 2 (Product + Technical) |
| critical | any | 2 (Product + Technical) |

**Review scope** by sprint complexity (applies regardless of governance mode):
- Simple (1-2 files, <50 lines): reviewers check only changed files + their tests
- Medium (2-5 files): reviewers check changed files + integration points with unchanged code
- Complex (5+ files): reviewers check changed files + cross-module impact + architectural fit

For light-mode sprints, record PAR as: `{"claude_product":"SKIPPED","technical_review":"APPROVE","provider":"...","governance":"light"}`

## No Secondary Provider

When Codex/secondary is unavailable, dispatch 2 Claude agents with split focus:
- Agent A (Product): `subagent_type: "standard-product-reviewer"` — spec fit, user scenarios, data integrity
- Agent B (Technical): `subagent_type: "standard-code-reviewer"` — correctness, security, architecture, performance

Record: `{"provider":"split-focus","claude_product":"ACCEPTED","technical_review":"APPROVE","ts":"..."}`

## Test Execution Discipline

**One test process at a time.** Never run tests in parallel or spawn a new run before the previous one finishes.

1. Always wrap test commands with timeout: `$TIMEOUT_CMD 120 python3 -m unittest discover -s tests`
2. If tests hang: `pkill -f unittest` FIRST, then investigate WHY (read the test, find the unmocked call)
3. **Never retry a hanging test without understanding the cause.** Hanging = a real `subprocess.run()` is being called without a mock. Re-running won't help.
4. If a test passes individually but fails in the full suite, suspect leaked global state (threading events, shared mocks, file artifacts)
5. **Never use `run_in_background` for test commands.** Tests must run in the foreground with an explicit timeout.

## Commit Before Review

Codex and other external reviewers see only committed code (they extract HEAD into a temp dir). Uncommitted working tree changes are invisible to them.

- **Commit fixes BEFORE dispatching Codex/secondary provider reviews.** Otherwise reviewers will flag already-fixed issues.
- If you must review uncommitted code, note that Codex findings need cross-checking against the working tree.

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
- Re-run only the agent that flagged issues, not both

## Final Holistic Review (after all sprints)

After all sprint PRs created, before Completion Report. Reasoning: Deep tier.

### When Holistic Review is Required

| Condition | Required? |
|-----------|-----------|
| 4+ sprints | Yes |
| Parallel execution used | Yes |
| Governance mode = critical | Yes |
| ≤3 linear sprints + light/standard | Skip |

When required, both agents review ALL code across ALL sprints as a unified system. Same principle: Claude = Product, secondary = Technical.

Check Codex availability first. If available:
a. Claude Product: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review ALL sprint changes. Focus: end-to-end user flows, data integrity across sprints, spec compliance.")`
b. Codex Technical: `$TIMEOUT_CMD 900 codex exec review -c model_reasoning_effort=high --ephemeral "Review all changes across all sprints for cross-module issues, architecture, security." 2>&1`

If no Codex: 2 split-focus Claude agents (Product: deep-product-reviewer, Technical: deep-code-reviewer), both using deep-tier agent definitions.

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
- Auto-launch from Phase 1 → dashboard mode recommended for all multi-sprint features

**Key difference:** In supervisor mode, the supervisor creates the worktree and sets the working directory. The Claude session inside does NOT create its own worktree.

## Dashboard Mode (Auto-Launch)

When the supervisor is launched automatically from Phase 1 Step 11, the Claude session enters dashboard mode. The session monitors the background supervisor and provides interactive commands.

### Sprint Transition Monitoring

Poll both `.superflow-state.json` and launcher status every 30 seconds via background command:
```bash
while true; do
  cat .superflow-state.json 2>/dev/null
  python3 -c "from lib.launcher import get_status; s=get_status('.'); print(f'alive={s.alive} crashed={s.crashed} heartbeat={s.heartbeat_age_seconds}')" 2>/dev/null
  sleep 30
done
```

On state change (sprint number or stage changed), display update:
```
Sprint 2/4 completed: "API endpoints" — PR #46 created
Sprint 3/4 in progress: "Frontend components"
```

On supervisor death (`alive=False`):
- If `crashed=True`: display crash notice, offer `restart`
- If all sprints complete: display summary, offer `merge`
- Otherwise: display unexpected stop, offer `restart` or `log`

### Interactive Commands

| Command | Implementation |
|---------|----------------|
| `status` | `python3 -c "from lib.launcher import get_status; ..."` → formatted status |
| `log` | `tail -50 .superflow/supervisor.log` |
| `stop` | `python3 -c "from lib.launcher import stop; ..."` → confirm, then SIGTERM |
| `restart` | `python3 -c "from lib.launcher import restart; ..."` → resume + relaunch |
| `skip N` | `python3 -c "from lib.launcher import write_skip_request; ..."` → write sidecar file |
| `merge` | Only if all sprints complete. Transition to Phase 3 (read `references/phase3-merge.md`). |

### Reconnection Scenarios

**New session while supervisor running:**
1. Read `.superflow-state.json` — phase=2
2. Check `launcher.get_status()` — alive=True
3. Enter dashboard mode automatically
4. Display current progress

**Supervisor has finished:**
1. Read state — phase=2, stage="ship"
2. Check `get_status()` — alive=False, crashed=False
3. Display completion summary
4. Offer merge

**Supervisor has crashed:**
1. Read state — phase=2, mid-sprint
2. Check `get_status()` — alive=False, crashed=True
3. Offer restart (resume + relaunch)

## Completion Report (Product Release Format)

Present as a **product release report** — what the team built for users, not a sprint log. Think "release notes for stakeholders", not "git log for developers".

### Structure

**1. What's New** — the headline features, grouped by user value (not by sprint):

For each feature group:
- **Feature name** — what it does in 1-2 sentences, user language
- Concrete capabilities: bullet list of what the user can now do that they couldn't before
- How it works: brief explanation of the mechanism (1-2 sentences max)

**2. How It Works Together** — explain how the features connect as a system. This is the "architecture for humans" section: what happens when a user runs the tool end-to-end.

**3. Technical Summary** (collapsed/brief):
- PRs: list with links and status
- Tests: total count, all passing
- Review: holistic review verdict
- Known limitations or follow-ups

**4. What's Next** — suggested next action: "Ready to merge — say 'merge' to start Phase 3"

### Tone
- Write for someone who will USE the product, not someone who reviewed the PRs
- Lead with user value, not implementation details
- Group by what changed for the user, not by sprint boundaries
- Concrete examples > abstract descriptions
- Skip internal process details (PAR, worktrees, review rounds) — those are for the PR descriptions

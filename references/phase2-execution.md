# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.

## Stage Structure (Per Sprint)

Each sprint passes through 6 stages. Use TaskCreate at sprint start, TaskUpdate as todos complete.

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
  - "Run mandatory docs audit"
  - "Write .par-evidence.json"

Stage 5: "Docs"
  Todos:
  - "Dispatch doc-update agent"
  - "Commit doc changes"
  - "Dispatch doc-review agent"
  - "Fix doc review findings"

Stage 6: "Ship"
  Todos:
  - "Push and create PR"
  - "Verify PR created"
  - "Cleanup worktree"
  - "Send Telegram update"
```

### State Management

Initialize state at the start of Phase 2:

```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":2,"phase_label":"Autonomous Execution","stage":"setup","stage_index":0,"sprint":1,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
sf_emit phase.start phase:int=2 label="Autonomous Execution"
```

### Heartbeat Writes

**At sprint start** (immediately after Step 1 re-read of phase docs, before any other work):

```bash
python3 -c "
import json, datetime, sys, os, tempfile
state_file = '.superflow-state.json'
s = json.load(open(state_file))
hb = s.get('heartbeat', {})
hb['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
hb['current_sprint'] = int(s.get('sprint') or 1)
hb['sprint_goal'] = sys.argv[1]
hb['merge_method'] = 'rebase'
hb['active_worktree'] = sys.argv[2]
hb['active_branch'] = sys.argv[3]
must_reread = [p for p in [
    os.path.expanduser('~/.claude/rules/superflow-enforcement.md'),
    'references/phase2-execution.md',
    s.get('context', {}).get('charter_file') or None,
    'references/phase3-merge.md',
    # must_reread: only short (<300 line) orchestration files. Plan file excluded
    # (read per-sprint section only, via Step 1 re-read).
] if p]
hb['must_reread'] = must_reread
hb['last_review_verdict'] = hb.get('last_review_verdict', None)
hb['phase2_step'] = 'setup'
s['heartbeat'] = hb
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(state_file) or '.', prefix='.superflow-state.', suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(s, f, indent=2)
os.replace(tmp, state_file)
" \"\$SPRINT_GOAL\" \"\$WORKTREE_PATH\" \"\$BRANCH_NAME\" \"\$CHARTER_FILE\"
sf_emit heartbeat phase2_step="setup" sprint:int=$SPRINT_NUM
# SPRINT_GOAL: one-line sprint description from plan
# WORKTREE_PATH: e.g. .worktrees/sprint-1
# BRANCH_NAME: e.g. feat/feature-sprint-1
# CHARTER_FILE: kept for backward compat; charter path comes from state context.charter_file
# Plan file is NOT in must_reread — it can be unbounded in size. Read only the specific sprint section via Step 1.
```

**At each stage transition** — single atomic write that updates `state.stage`, `state.stage_index`, `state.last_updated`, AND `heartbeat.phase2_step` in one `json.dump` + `os.replace`. Do NOT use the old two-step pattern (separate stage update then heartbeat update) — a crash between those two writes leaves state inconsistent:

```bash
python3 -c "
import json, datetime, sys, os, tempfile
# stage_name  stage_index  sprint_num (sys.argv[1..3])
STAGE_INDEXES = {'setup':0,'implementation':1,'review':2,'par':3,'docs':4,'ship':5}
state_file = '.superflow-state.json'
s = json.load(open(state_file))
stage = sys.argv[1]
s['stage'] = stage
s['stage_index'] = STAGE_INDEXES.get(stage, s.get('stage_index', 0))
s['sprint'] = int(sys.argv[2]) if len(sys.argv) > 2 else s.get('sprint', 1)
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
hb = s.get('heartbeat', {})
hb['updated_at'] = s['last_updated']
hb['phase2_step'] = stage
s['heartbeat'] = hb
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(state_file) or '.', prefix='.superflow-state.', suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(s, f, indent=2)
os.replace(tmp, state_file)
" \"\$NEXT_STAGE\" \"\$SPRINT_NUM\"
sf_emit heartbeat phase2_step="$NEXT_STAGE" sprint:int=$SPRINT_NUM
# NEXT_STAGE: one of setup | implementation | review | par | docs | ship
# SPRINT_NUM: current sprint number (e.g., 1, 2, 3)
# On resume: heartbeat.phase2_step is the authoritative source of current stage.
# state.stage is kept in sync for backward compat with v4.8 readers.
```

**Backward compatibility:** All snippets use `.get('heartbeat', {})` — if `.superflow-state.json` was written by v4.8 and has no `heartbeat` key, the field is created fresh. The rest of the state is untouched.

**Resume semantics:** Heartbeat `phase2_step` marks stage START — it is written as the orchestrator enters a stage, not when it exits. On post-compaction resume, read `phase2_step` and re-enter that stage from its first todo. Idempotency: each stage's todos are safe to re-run — worktree re-check is a no-op if it already exists, re-running tests is harmless. The one exception is PR creation in the Ship stage: always run `gh pr view` before `gh pr create` to avoid duplicate PRs.

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

## Orchestrator Tool Budget

In Phase 2 the orchestrator coordinates; it does not investigate or read code itself. The orchestrator's allowed direct tools are:

- **Bash for status:** `git status`, `git log --oneline -N`, `git diff --stat`, `gh run list`, `gh pr view`, `ls`, `pwd`, `which`, `date`, short `echo` / `printf` for progress
- **Bash for state I/O:** writing/reading `.superflow-state.json`, `.par-evidence.json`, CHANGELOG appends, `.superflow/compact-log/` listings
- **Read for short config/state files (<50 lines):** `package.json`, `.superflow-state.json`, `.par-evidence.json`, the specific sprint section of the plan
- **TaskCreate / TaskUpdate** for per-sprint stage tracking
- **Agent (Task) tool** to dispatch subagents

Anything else — and **especially** reading source code, exploring directories, running test suites, parsing JSON outputs longer than a few lines — belongs in a `deep-analyst` subagent that returns a <2k-token summary. Give the subagent the question, not a list of files to read.

**Why this matters.** Orchestrator context grows monotonically through Phase 2. Every Read of a 500-line file adds 500 lines to a context that is already holding plan, charter, sprint state, PAR evidence, dual-model review output, and accumulated turn-history. Subagents return summaries; their own contexts are discarded when they exit. On a 6-8h autonomous run, the difference between "read files directly" and "route through analysts" is the difference between hitting the auto-compact threshold 10x vs. 2x.

**Examples of correct delegation:**

- *"What does module X do?"* → dispatch `deep-analyst` with the question; expect a bulleted summary back.
- *"Does the codebase already have a function that does Y?"* → dispatch analyst to Grep + Read candidates + return a single-line answer (name/path or "no").
- *"Why is test Z failing?"* → dispatch analyst to read the test, failure output, and suspected source files; return the root cause in 2-3 sentences.

Exceptions to the budget, when a direct read is cheaper than a dispatch round-trip:

- Files the orchestrator has already Read in the current sprint (still in context).
- Files < 50 lines where the full content is the answer (e.g. confirming a PR's `.par-evidence.json` format).
- Single-line status outputs (`git status --short`, `gh run list --limit 3`).

See enforcement Rule 11 for the durable, compaction-surviving version of this budget.

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

## Sprint-Level Parallel Dispatch

Read `context.git_workflow_mode` from `.superflow-state.json` before building the sprint execution loop. If the field is missing, default to `sprint_pr_queue` for backward compatibility. The selected mode controls branch bases, PR count, and whether sprint-level parallelism is allowed:

- `solo_single_pr`: run sprints sequentially on one feature branch; task-level parallelism inside a sprint is still allowed.
- `sprint_pr_queue`: run dependent sprints sequentially; independent sprint waves may run in parallel only if their PRs are independently reviewable from `main`.
- `stacked_prs`: run dependent sprints as a stack; do not parallelize dependent stack segments.
- `parallel_wave_prs`: run independent sprint waves in parallel; each sprint branch starts from `origin/main`.
- `trunk_based`: keep branches short-lived and sequential unless the plan explicitly identifies independent deployable slices.

Before the execution loop, analyze the plan for sprint-level parallelism. Independent sprints run concurrently — each in its own worktree.

**Sprint wave analysis (runs once at Phase 2 start):**

1. Parse the plan for each sprint's `files:` and `depends_on:` metadata
2. Build a dependency graph:
   - Explicit dependencies from `depends_on:` field
   - Implicit dependencies: if Sprint A and Sprint B modify any of the same files, B depends on A (or vice versa — lower sprint number goes first)
3. Group sprints into waves using topological sort:
   - Wave 1: all sprints with no dependencies (in-degree = 0)
   - Wave 2: sprints whose dependencies are all in Wave 1
   - Wave N: sprints whose dependencies are all in Waves 1..(N-1)
4. Store the wave plan in `.superflow-state.json` under `context.sprint_waves`

**Example:**
```
Plan: 6 sprints
Sprint 1: files=[src/api/], depends_on=[]
Sprint 2: files=[src/ui/], depends_on=[]
Sprint 3: files=[src/api/], depends_on=[1]
Sprint 4: files=[src/ui/], depends_on=[2]
Sprint 5: files=[tests/], depends_on=[1,2]
Sprint 6: files=[docs/], depends_on=[]

Graph → Waves:
  Wave 1: [Sprint 1, Sprint 2, Sprint 6]  — all independent
  Wave 2: [Sprint 3, Sprint 4, Sprint 5]  — dependencies satisfied

6 sprints → 2 waves → ~2x speedup
```

**Execution loop (replaces sequential sprint-by-sprint):**

```
for each wave in sprint_waves:
  if wave has 1 sprint:
    run sprint sequentially (normal Per-Sprint Flow)
  else:
    for each sprint in wave:
      dispatch sprint as Agent(run_in_background: true) with full Per-Sprint Flow
    wait for all sprints in wave to complete

    # Post-wave merge check
    for each pair of sprints in wave:
      check for file conflicts between their branches
    if conflicts found:
      resolve conflicts manually on the later sprint's branch

    # Do not merge during Phase 2 unless the user explicitly approved auto-merge in Phase 1.
    # If later work must see earlier merged code, use stacked_prs or run dependent sprints sequentially.
```

**Each parallel sprint runs the full Per-Sprint Flow** (Setup → Implementation → Review → PAR → Docs → Ship) independently in its own worktree. The orchestrator dispatches them as background agents and waits.

**Parallel sprint agent dispatch:**
```
Agent(
  subagent_type: "standard-implementer",  # or appropriate tier
  model: "sonnet",  # ALWAYS explicit — frontmatter model is not reliably inherited
  run_in_background: true,
  prompt: "
Execute Sprint N: [title] — full Per-Sprint Flow.

Read references/phase2-execution.md for the complete flow.
Read the plan at [plan_path] for Sprint N details.
Charter: [charter_content]

Your worktree: .worktrees/sprint-N on branch feat/<feature>-sprint-N

Execute all 6 stages: Setup → Implementation → Review → PAR → Docs → Ship.
Create the PR at the end. Report back with PR URL or BLOCKED status.
"
)
```

**Fallback:** If ≤3 total sprints or all sprints are in a single wave chain (each depends on the previous), skip wave analysis and run sequentially. The overhead of parallel orchestration isn't worth it.

**Holistic review trigger:** When `max_parallel > 1` (any wave had 2+ sprints), holistic review is mandatory (enforcement rule 9).

## Branch and PR Policy by Git Workflow Mode

Use the selected `context.git_workflow_mode`:

- `solo_single_pr`: create/reuse `.worktrees/solo` on `feat/<feature>` from `origin/main`. Each sprint commits to the same branch. Run PR-gated docs update/review and create one PR only after the final sprint.
- `sprint_pr_queue`: create `.worktrees/sprint-N` on `feat/<feature>-sprint-N` from `origin/main`. Create one PR per sprint with base `main`.
- `stacked_prs`: Sprint 1 starts from `origin/main`; Sprint N starts from `feat/<feature>-sprint-(N-1)`. Create one PR per sprint; PR base is the previous sprint branch until Phase 3 retargets/rebases.
- `parallel_wave_prs`: create every sprint branch from `origin/main`. Only independent sprints may run in the same wave. Create one PR per sprint with base `main`.
- `trunk_based`: create short-lived branches per deployable slice. Keep incomplete work behind flags or disabled paths.

Never silently switch modes during Phase 2. If the selected mode becomes unsafe because the plan has unexpected dependencies or conflicts, stop the parallel path and continue sequentially within the same mode, then report the fallback in the Completion Report.

---

## Per-Sprint Flow

```bash
# Backward-compat guard: if sf-emit.sh wasn't sourced at session start, define a no-op fallback.
# This ensures sessions without events.jsonl still work (charter non-negotiable).
command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
```

1. <!-- Stage 1: Setup, Todo 1 --> **Re-read** this file (`references/phase2-execution.md`), the **charter** (from `context.charter_file` in `.superflow-state.json`), AND the **specific sprint section** from the plan. Extract and paste the exact task list for this sprint into the implementer prompt — do NOT rely on LLM memory of the plan. The implementer must see every task, every file path, every expected behavior verbatim.
   **Immediately after re-reading:** emit `sprint.start` and `stage.start`, then emit heartbeat (see "Heartbeat Writes → At sprint start" above). Use the charter path from `context.charter_file` in state as `$CHARTER_FILE`.
   ```bash
   sf_emit sprint.start sprint:int=$SPRINT_NUM total_sprints:int=$TOTAL_SPRINTS goal="$SPRINT_GOAL" complexity="$COMPLEXITY"
   sf_emit stage.start stage=setup phase:int=2
   # COMPLEXITY: one of simple, medium, complex — from plan's sprint tag
   ```
2. <!-- Stage 1: Setup, Todo 2 --> **Telegram update** (if MCP connected): "Starting sprint N: [title]"
3. <!-- Stage 1: Setup, Todo 3 --> **Worktree/branch**: verify `.worktrees/` is gitignored (`git check-ignore -q .worktrees || echo '.worktrees/' >> .gitignore`), then create the branch/worktree according to "Branch and PR Policy by Git Workflow Mode" above.
4. <!-- Stage 1: Setup, Todo 4 --> **Baseline tests** in worktree: run full test suite, record output. If tests fail on baseline, stop and report — do not build on a broken base.
   ```bash
   sf_emit test.run command="$TEST_CMD"
   # ... run tests ...
   # STATUS: one of pass, fail
   sf_emit test.result status="$STATUS"
   sf_emit stage.end stage=setup phase:int=2
   ```
5. <!-- Stage 2: Implementation, Todos 1-2 --> **Emit unified stage transition** (`$NEXT_STAGE=implementation`, `$SPRINT_NUM=N`). **Dispatch implementers** — model from plan's sprint complexity tag (see Adaptive Implementation Model below), wave analysis for parallelism (see Parallel Dispatch above).
   ```bash
   sf_emit stage.start stage=implementation phase:int=2
   ```
   - 5a. Analyze task list — identify independent tasks
   - 5b. Group into waves
   - 5c. For Wave 1: dispatch each as `Agent(run_in_background: true)` with appropriate implementer tier. Before/after dispatch:
     ```bash
     sf_emit agent.dispatch agent_type=implementer task="Sprint N: <task-title>" model=sonnet
     # After agent returns (repeat per agent in wave):
     sf_emit agent.complete role=implementer
     # On failure instead:
     sf_emit agent.fail role=implementer summary="<failure summary>"
     ```
   - 5d. For subsequent waves: same pattern
   - 5e. After all waves: verify no file conflicts with `git status`
   ```bash
   sf_emit stage.end stage=implementation phase:int=2
   ```
   Include `llms.txt` content in agent context (if exists).
6. <!-- Stage 3: Review, Todos 1-3 --> **Emit unified stage transition** (`$NEXT_STAGE=review`, `$SPRINT_NUM=N`). **Unified Review** (2 specialized agents parallel, Reasoning: Standard tier):
   Both agents receive: the SPEC, the product brief, and the relevant git diff.
   Principle: **specialize, don't duplicate** — Claude = Product lens, secondary = Technical lens.
   ```bash
   sf_emit stage.start stage=review phase:int=2
   ```

   First, check Codex availability: `codex --version 2>/dev/null`

   If Codex available:
   a. Claude product reviewer:
      ```bash
      sf_emit review.start reviewer=product target="Sprint $SPRINT_NUM diff"
      sf_emit agent.dispatch agent_type=standard-product-reviewer task="Sprint N: product review" model=opus
      ```
      `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "[SPEC + brief + diff context]")`
   b. Codex technical reviewer:
      ```bash
      sf_emit review.start reviewer=technical target="Sprint $SPRINT_NUM diff"
      ```
      `$TIMEOUT_CMD 600 codex exec review --base main -m gpt-5.5 -c model_reasoning_effort=high --ephemeral - < <(echo "SPEC_CONTEXT" | cat - prompts/codex/code-reviewer.md) 2>&1` (run_in_background)

   If Codex NOT available (split-focus fallback — 2 Claude agents):
   a. Claude product:
      ```bash
      sf_emit review.start reviewer=product target="Sprint $SPRINT_NUM diff"
      sf_emit agent.dispatch agent_type=standard-product-reviewer task="Sprint N: product review" model=opus
      ```
      `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "Focus: spec fit, user scenarios, data integrity")`
   b. Claude technical:
      ```bash
      sf_emit review.start reviewer=technical target="Sprint $SPRINT_NUM diff"
      sf_emit agent.dispatch agent_type=standard-code-reviewer task="Sprint N: technical review" model=opus
      ```
      `Agent(subagent_type: "standard-code-reviewer", run_in_background: true, prompt: "Focus: correctness, security, architecture, performance")`
   Record `"provider": "split-focus"` in .par-evidence.json.

   Wait for both. After each reviewer returns:
   ```bash
   # VERDICT: one of APPROVE, ACCEPTED, REQUEST_CHANGES, NEEDS_FIXES, PASS, FAIL
   sf_emit agent.complete role=product-reviewer
   sf_emit review.verdict reviewer=product verdict="$VERDICT"
   sf_emit agent.complete role=code-reviewer
   sf_emit review.verdict reviewer=technical verdict="$VERDICT"
   ```
   Aggregate findings:
   - CRITICAL/REQUEST_CHANGES from either agent = fix required
   - Fix confirmed issues. Re-run only the agent that flagged issues.
   - If a finding is incorrect (reviewer lacked context), record disagreement with reasoning and skip.
   ```bash
   sf_emit stage.end stage=review phase:int=2
   ```
7. <!-- Stage 4: PAR, Todos 1-4 --> **Emit unified stage transition** (`$NEXT_STAGE=par`, `$SPRINT_NUM=N`). **Post-review test verification + PAR evidence**:
   ```bash
   sf_emit stage.start stage=par phase:int=2
   sf_emit test.run command="$TEST_CMD"
   ```
   Run full test suite after all review fixes. Paste actual output as evidence (enforcement rule 4).
   ```bash
   # STATUS: one of pass, fail
   sf_emit test.result status="$STATUS"
   ```
   Write `.par-evidence.json` in worktree root:
   ```json
   {
     "sprint": N,
     "claude_product": "ACCEPTED",
     "technical_review": "APPROVE",
    "docs_update": "PENDING",
    "docs_review": "PENDING",
    "provider": "codex",
     "ts": "ISO-8601"
   }
   ```
   Both verdicts must be APPROVE/ACCEPTED/PASS. If either agent returned issues, they must be fixed and the agent re-run before evidence is written.
   ```bash
   sf_emit stage.end stage=par phase:int=2
   ```
8. <!-- Stage 5: Docs, Todos 1-4 --> **Emit unified stage transition** (`$NEXT_STAGE=docs`, `$SPRINT_NUM=N`). **Mandatory documentation update + documentation review before PR** — first dispatch `standard-doc-writer` to audit/update CLAUDE.md and llms.txt based on sprint changes, then dispatch a review-only doc pass. This is a gate before every PR. In `solo_single_pr`, run it before the final PR (and optionally at checkpoints if docs drift would make later review harder); in per-sprint PR modes, run it every sprint. `llms.txt` is always checked; it may be committed as unchanged only after the doc update agent explicitly confirms no material update is needed:
   ```bash
   sf_emit stage.start stage=docs phase:int=2
   sf_emit agent.dispatch agent_type=standard-doc-writer task="Sprint N: docs update" model=sonnet
   ```
   ```
   Agent(
     subagent_type: "standard-doc-writer",
     model: "sonnet",  # explicit — frontmatter not reliably inherited
     prompt: "
   Audit and update project documentation for Sprint N before PR creation.

   **Read first:**
   - `git diff main...HEAD` to see what this sprint changed
   - Current `CLAUDE.md` and `llms.txt`
   - `prompts/claude-md-writer.md` and `prompts/llms-txt-writer.md` for standards

   **CLAUDE.md — update if any of these changed:**
   - New key files or modules added → add to Key Files table
   - New conventions introduced → add to Conventions
   - New commands or workflows → add to relevant section
   - Architecture changed → update Architecture section
   If nothing materially changed, report `CLAUDE.md: UNCHANGED` with the reason.

   **llms.txt — ALWAYS AUDIT, update if any of these changed:**
   - New API endpoints or features → add to relevant section
   - New dependencies or integrations → document
   - Removed functionality → remove from docs
   - Public commands, setup, architecture, key modules, or workflows changed → update
   If nothing materially changed, report `llms.txt: UNCHANGED` with the reason.

   **Rules:**
   - Minimal edits only — update what changed, don't rewrite
   - Verify every path/command you document actually exists
   - Keep CLAUDE.md under 200 lines
   - Preserve existing markers (<!-- updated-by-superflow:... -->)

   **Required output:** `docs_update: UPDATED` if either file changed, otherwise `docs_update: UNCHANGED`, plus a short reason for each file.
   "
   )
   ```
   ```bash
   sf_emit agent.complete role=doc-writer
   ```
   After agent completes, commit doc changes: `git add CLAUDE.md llms.txt && git commit -m "docs: update project documentation for sprint N" || true` (the `|| true` handles the case where nothing changed).
   Update `.par-evidence.json` with `"docs_update":"UPDATED"` or `"docs_update":"UNCHANGED"`.

   **Documentation review (mandatory, review-only):** dispatch `standard-doc-writer` with a review-only prompt:
   ```bash
   sf_emit agent.dispatch agent_type=standard-doc-writer task="Sprint N: docs review" model=sonnet
   ```
   ```
   Agent(
     subagent_type: "standard-doc-writer",
     model: "sonnet",
     prompt: "
   Review Sprint N documentation changes before PR creation. Do not edit files.

   **Read first:**
   - `git diff main...HEAD`
   - Current `CLAUDE.md` and `llms.txt`

   **Verify:**
   - `llms.txt` was explicitly audited and is accurate for current project structure
   - `CLAUDE.md` and `llms.txt` reflect user-facing features, commands, architecture, and changed key modules from this sprint
   - No stale paths, deleted modules, nonexistent commands, or overbroad claims were introduced
   - If docs_update is UNCHANGED, that decision is justified by the sprint diff

   Output exactly: `docs_review: PASS` or `docs_review: NEEDS_FIXES`, with findings if fixes are needed.
   "
   )
   ```
   ```bash
   sf_emit agent.complete role=doc-writer
   ```
   Fix any `NEEDS_FIXES`, commit doc fixes if any, then re-run the documentation review. Update `.par-evidence.json` with `"docs_review":"PASS"`.
   ```bash
   sf_emit stage.end stage=docs phase:int=2
   ```
9. <!-- Stage 6: Ship, Todos 1-2 --> **Emit unified stage transition** (`$NEXT_STAGE=ship`, `$SPRINT_NUM=N`). **Push + PR/checkpoint**: verify `.par-evidence.json` exists with review verdicts passing. If this sprint creates a PR under the selected git workflow mode, `docs_update` must be `UPDATED` or `UNCHANGED` and `docs_review` must be `PASS`; push the mode-specific branch and create the mode-specific PR. In `solo_single_pr`, non-final sprints push checkpoint commits to the shared feature branch without creating a PR; the final sprint creates one PR after docs gates pass.
   ```bash
   sf_emit stage.start stage=ship phase:int=2
   # After gh pr create succeeds:
   sf_emit pr.create pr_number:int=$PR_NUM title="$PR_TITLE" branch=$BRANCH_NAME sprint:int=$SPRINT_NUM
   sf_emit sprint.end sprint:int=$SPRINT_NUM total_sprints:int=$TOTAL_SPRINTS goal="$SPRINT_GOAL" complexity="$COMPLEXITY"
   sf_emit stage.end stage=ship phase:int=2
   ```
10. <!-- Stage 6: Ship, Todo 3 --> **Cleanup**: if a PR was created, verify it successfully (`gh pr view` returns data), then remove only the worktree for completed per-sprint branches. In `solo_single_pr`, keep the shared worktree until the final PR is created.
11. <!-- Stage 6: Ship, Todo 4 --> **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." For non-final `solo_single_pr` checkpoints, say "Sprint N checkpoint pushed." Then next sprint.

## Sprint Completion Checklist

Before creating the PR, verify ALL:
- [ ] Worktree created and work done in isolation
- [ ] Implementation dispatched to subagents (not written by orchestrator)
- [ ] Unified review completed: 2 agents (Product + Technical), both APPROVE/ACCEPTED
- [ ] Full test suite passes with pasted evidence
- [ ] `.par-evidence.json` written with review verdicts passing, `docs_update` set, and `docs_review` = `PASS`
- [ ] Documentation update completed before PR; `llms.txt` explicitly updated or confirmed unchanged
- [ ] Documentation review completed before PR and passed
- [ ] PR created with the base branch required by `context.git_workflow_mode`
- [ ] Worktree cleaned up

## Adaptive Implementation Model

Sprint complexity drives model selection. Tag each sprint in the plan:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | medium | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | sonnet | high | 5+ files, new architecture, security-sensitive |

**IMPORTANT: Always pass `model: "sonnet"` explicitly in Agent() calls for ALL implementers and doc-writers.** Agent definition frontmatter `model:` is NOT reliably inherited — without explicit `model:`, subagents inherit the parent's model (Opus), wasting tokens on implementation tasks that Sonnet handles equally well.

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

For light-mode sprints, record PAR as: `{"claude_product":"SKIPPED","technical_review":"APPROVE","docs_update":"UPDATED|UNCHANGED","docs_review":"PASS","provider":"...","governance":"light"}`

## No Secondary Provider

When Codex/secondary is unavailable, dispatch 2 Claude agents with split focus:
- Agent A (Product): `subagent_type: "standard-product-reviewer"` — spec fit, user scenarios, data integrity
- Agent B (Technical): `subagent_type: "standard-code-reviewer"` — correctness, security, architecture, performance

Record: `{"provider":"split-focus","claude_product":"ACCEPTED","technical_review":"APPROVE","docs_update":"UPDATED|UNCHANGED","docs_review":"PASS","ts":"..."}`

## Test Execution Discipline

**One test process at a time.** Never run tests in parallel or spawn a new run before the previous one finishes.

1. Always wrap test commands with timeout: `$TIMEOUT_CMD 120 python3 -m unittest discover -s tests`
2. If tests hang: `pkill -f unittest` FIRST, then investigate WHY (read the test, find the unmocked call)
3. **Never retry a hanging test without understanding the cause.** Hanging = a real `subprocess.run()` is being called without a mock. Re-running won't help.
4. If a test passes individually but fails in the full suite, suspect leaked global state (threading events, shared mocks, file artifacts)
5. **Never use `run_in_background` for test commands.** Tests must run in the foreground with an explicit timeout.

## Frontend Testing (when applicable)

When a sprint modifies frontend code (HTML, CSS, JS, React components, templates):

1. After implementation and before review, run visual verification using `/webapp-testing` or Playwright MCP
2. Open the affected page(s) in browser
3. Take screenshot as evidence
4. If visual regression detected, fix before proceeding to review
5. Include screenshot URL in PR description

**Detection:** Sprint plan should tag frontend sprints with `frontend: true`. The sprint prompt includes `{frontend_instructions}` — when frontend=true, it instructs the agent to verify UI visually.

**Skill required:** `/webapp-testing` (Playwright-based). Installed during Phase 0 onboarding for projects with frontend stack.

## Commit Before Review

Codex and other external reviewers see only committed code (they extract HEAD into a temp dir). Uncommitted working tree changes are invisible to them.

- **Commit fixes BEFORE dispatching Codex/secondary provider reviews.** Otherwise reviewers will flag already-fixed issues.
- If you must review uncommitted code, note that Codex findings need cross-checking against the working tree.

## Compaction Recovery

Phase 2 runs for hours — context compaction will fire at least once on any non-trivial run. The `PostCompact` hook re-injects SuperFlow rules, but in-progress sprint details, recent review output, and the current task queue can still be summarized away during compaction itself.

To hydrate cleanly after compaction:

1. Re-read `~/.claude/rules/superflow-enforcement.md` and `references/phase2-execution.md` (enforcement rule 5). Not optional.
2. Re-read `.superflow-state.json` for current sprint / stage / stage_index.
3. Then: `ls -t .superflow/compact-log/ 2>/dev/null | head -1` — if a dump exists, read it with the Read tool. That is the PreCompact snapshot saved by `hooks/precompact-state-externalization.sh` (see `hooks/README.md`). It contains the pre-compaction state file, the last 40 transcript entries, and any active sprint context that the summarizer might have dropped.
4. Only after hydrating should you resume work. Resuming without reading the latest dump risks repeating a step that already ran or skipping one that didn't finish.

If `.superflow/compact-log/` does not exist, the PreCompact hook isn't installed — continue without hydration and note it for the next onboarding cycle.

**Event log note:** `compact.pre` is emitted by `hooks/precompact-state-externalization.sh` immediately before writing the dump file; `compact.post` is emitted immediately after the dump write succeeds. Both carry `dump_path` so consumers can locate the state snapshot.

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

**Conditional — run only when any of the following apply:**
- Total sprints ≥ 4
- Parallel execution was used (max_parallel > 1)
- Governance mode is "critical"

For ≤3 linear sequential sprints in light/standard mode, holistic review is skipped and the Completion Report proceeds without holistic evidence.

When holistic IS required: after all mode-specific PRs/checkpoints are created, before Completion Report. Reasoning: Deep tier.
Both agents review ALL code across ALL sprints as a unified system. Same principle: Claude = Product, secondary = Technical.

Check Codex availability first. If available:
a. Claude Product: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review ALL sprint changes. Focus: end-to-end user flows, data integrity across sprints, spec compliance.")`
b. Codex Technical: `$TIMEOUT_CMD 900 codex exec review -m gpt-5.5 -c model_reasoning_effort=high --ephemeral "Review all changes across all sprints for cross-module issues, architecture, security." 2>&1`

If no Codex: 2 split-focus Claude agents (Product: deep-product-reviewer, Technical: deep-code-reviewer), both using deep-tier agent definitions.

**Cross-sprint codebase hygiene (MANDATORY in holistic review):**
Both reviewers must explicitly check for these three issues across ALL sprint changes combined:
1. **Code duplication across sprints** — different sprints may have independently implemented similar logic. Search for similar function names, shared patterns, repeated validation/transformation code across sprint boundaries.
2. **Type redefinition across sprints** — later sprints may redefine types that earlier sprints already created, or that exist in auto-generated files. Check for `as unknown as`, `as any` casts bridging between sprint-local types.
3. **Dead code from incremental refactoring** — when sprint N refactors code from sprint N-1, old code paths may remain. Trace call chains for functions/components that lost all callers across the combined diff.

These issues are invisible in per-sprint review but become apparent when viewing all changes as a unified system. Flag as HIGH severity — they compound over time.

Fix CRITICAL/HIGH issues before Completion Report.

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
- Git workflow: selected mode, PR count, and any sequential fallback from planned parallelism
- Tests: total count, all passing
- Review: holistic review verdict
- Known limitations or follow-ups

**4. What's Next** — suggested next action: "Ready to merge — say 'merge' to start Phase 3"

```bash
sf_emit phase.end phase:int=2 label="Autonomous Execution"
```

### Tone
- Write for someone who will USE the product, not someone who reviewed the PRs
- Lead with user value, not implementation details
- Group by what changed for the user, not by sprint boundaries
- Concrete examples > abstract descriptions
- Skip internal process details (PAR, worktrees, review rounds) — those are for the PR descriptions

**Note on `pr.merge`:** The `pr.merge` event is emitted during Phase 3 merge, not Phase 2. See `references/phase3-merge.md` for placement.

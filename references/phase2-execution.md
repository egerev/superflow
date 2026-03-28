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
  - "Write .par-evidence.json"

Stage 5: "Docs"
  Todos:
  - "Dispatch doc-update agent"
  - "Commit doc changes"

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
8. <!-- Stage 5: Docs, Todos 1-2 --> **Documentation update** — dispatch `standard-doc-writer` to update CLAUDE.md and llms.txt based on sprint changes:
   ```
   Agent(
     subagent_type: "standard-doc-writer",
     prompt: "
   Update project documentation to reflect changes from Sprint N.

   **Read first:**
   - `git diff main...HEAD` to see what this sprint changed
   - Current `CLAUDE.md` and `llms.txt`
   - `prompts/claude-md-writer.md` and `prompts/llms-txt-writer.md` for standards

   **CLAUDE.md — update if any of these changed:**
   - New key files or modules added → add to Key Files table
   - New conventions introduced → add to Conventions
   - New commands or workflows → add to relevant section
   - Architecture changed → update Architecture section
   If nothing materially changed, skip CLAUDE.md.

   **llms.txt — update if any of these changed:**
   - New API endpoints or features → add to relevant section
   - New dependencies or integrations → document
   - Removed functionality → remove from docs
   If nothing materially changed, skip llms.txt.

   **Rules:**
   - Minimal edits only — update what changed, don't rewrite
   - Verify every path/command you document actually exists
   - Keep CLAUDE.md under 200 lines
   - Preserve existing markers (<!-- updated-by-superflow:... -->)
   "
   )
   ```
   After agent completes, commit doc changes: `git add CLAUDE.md llms.txt && git commit -m "docs: update project documentation for sprint N" || true` (the `|| true` handles the case where nothing changed).
9. <!-- Stage 6: Ship, Todos 1-2 --> **Push + PR**: verify `.par-evidence.json` exists with both verdicts passing. `git push -u origin feat/<feature>-sprint-N`, then `gh pr create --base main`
10. <!-- Stage 6: Ship, Todo 3 --> **Cleanup**: verify PR was created successfully (`gh pr view` returns data), then `git worktree remove .worktrees/sprint-N`
11. <!-- Stage 6: Ship, Todo 4 --> **Telegram update** (if MCP connected): "Sprint N complete. PR #NNN created." Then next sprint.

## Sprint Completion Checklist

Before creating the PR, verify ALL:
- [ ] Worktree created and work done in isolation
- [ ] Implementation dispatched to subagents (not written by orchestrator)
- [ ] Unified review completed: 2 agents (Product + Technical), both APPROVE/ACCEPTED
- [ ] Full test suite passes with pasted evidence
- [ ] `.par-evidence.json` written with both verdicts passing
- [ ] Documentation updated (CLAUDE.md, llms.txt) or confirmed unchanged
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

When holistic IS required: After all sprint PRs created, before Completion Report. Reasoning: Deep tier.
Both agents review ALL code across ALL sprints as a unified system. Same principle: Claude = Product, secondary = Technical.

Check Codex availability first. If available:
a. Claude Product: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review ALL sprint changes. Focus: end-to-end user flows, data integrity across sprints, spec compliance.")`
b. Codex Technical: `$TIMEOUT_CMD 900 codex exec review -c model_reasoning_effort=high --ephemeral "Review all changes across all sprints for cross-module issues, architecture, security." 2>&1`

If no Codex: 2 split-focus Claude agents (Product: deep-product-reviewer, Technical: deep-code-reviewer), both using deep-tier agent definitions.

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

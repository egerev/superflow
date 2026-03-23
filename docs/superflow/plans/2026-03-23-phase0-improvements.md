# Phase 0 Improvements + Parallelism + Stability — Implementation Plan

**Spec:** [2026-03-23-phase0-improvements-design.md](../specs/2026-03-23-phase0-improvements-design.md)
**Brief:** [2026-03-23-phase0-improvements-brief.md](../specs/2026-03-23-phase0-improvements-brief.md)
**Date:** 2026-03-23

---

## Dependency Graph

```
Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4
(strictly sequential — overlapping files: phase0-onboarding.md, SKILL.md)
```

> **Branch base rule:** Each sprint branches from the MERGED result of the previous sprint. Sprint 2 starts only after Sprint 1's PR is merged. Use `git checkout main && git pull` before starting each sprint.

## Existing Work

Branch `feat/phase0-interactive-onboarding` has 2 commits:
1. `cd138a2` — Mini-interview (3 text questions), hooks setup, skills recommendation, expanded permissions
2. `a8806f2` — Further expanded core permissions list

**What exists:** `references/phase0-onboarding.md` already has Steps 1-10 with mini-interview, hooks setup (Step 7.5), skills recommendation (Step 7.7), stack-specific permissions (Step 7), and completion checklist (Step 9). Text-based questions, no AskUserQuestion, no proposal step, no empty-project detection, no CLAUDE.local.md, no hook verification pipeline, no plugin recommendations, no restart instruction.

**What this plan adds on top:** AskUserQuestion conversion, Step 1.5 (empty detection), Step 2.5 (proposal), Step 5.5 (CLAUDE.local.md), hook verification (4-stage pipeline), Step 7.7 update (/verify skill), Step 9.5 (plugin recommendations), Step 10 update (restart instruction), SKILL.md architecture update.

---

## Sprint 1 — Phase 0: Interactive Onboarding (Existing Project)

**Branch:** `feat/phase0-interactive-onboarding` (continue existing branch)
**PR target:** `main`
**Depends on:** nothing (first sprint)

### Task 1.1: Convert Step 1 to AskUserQuestion

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. In Step 1 ("Greet, Announce & Mini-Interview"), replace the 3 text-based questions with AskUserQuestion tool calls. Current text at roughly lines 37-58 says "Ask the user 3 short questions" with plain text format.
2. Replace with the spec's AskUserQuestion format — 3 calls with predefined options:
   - Q1: team size (solo / small_team / large_team)
   - Q2: experience with detected stack (beginner / intermediate / advanced)
   - Q3: CI/CD status (yes / no / not_sure)
3. Add fallback logic block: "If AskUserQuestion is unavailable (non-interactive mode, older Claude Code version), fall back to text-based questions as currently implemented."
4. Add "just go" edge case: if user dismisses or says "just go" / "просто начинай", use defaults `{team: "solo", experience: "intermediate", ci: "no"}`.
5. Add `$USER_CONTEXT` JSON object definition with the 4 fields (team, experience, ci, dismissed).
6. Keep the existing prose about how context affects analysis (beginner/solo/no-CI sections) — it's already there.

**Commit:** `feat: convert Phase 0 mini-interview to AskUserQuestion with fallback`

**Dependencies:** none

### Task 1.2: Add Step 1.5 — Empty Project Detection

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. Insert a new "## Step 1.5: Detect Empty Project vs Existing" section between Step 1 and Step 2.
2. Include the detection logic from the spec:
   - `FILE_COUNT` — git ls-files excluding config-only files
   - `SOURCE_COUNT` — find for source extensions, excluding node_modules/.git
   - `COMMIT_COUNT` — git rev-list --count HEAD
   - `HAS_SOURCE` — git ls-files grep for source extensions
3. Include the decision matrix table (5 rows: greenfield vs existing).
4. Include the edge case: empty project with deleted source history check via `git log --diff-filter=A`.
5. Add the routing message: greenfield detected → "This looks like a new project!" → route to Sprint 3 path. Existing → proceed to Step 2.

**Commit:** `feat: add Step 1.5 — detect empty vs existing project for greenfield routing`

**Dependencies:** none

### Task 1.3: Add Step 2.5 — Proposal Before Execution

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. Insert a new "## Step 2.5: Proposal — Review Before Execution" section after Step 3 (Health Report), before Step 4 (llms.txt). The spec says "Insert after Step 3, before Step 4" — the proposal shows what Phase 0 will do after analysis is complete.
2. Include the full proposal format from the spec with all sections: Documentation, Development Environment (permissions preview, hooks preview, notifications), Infrastructure (enforcement rules, .gitignore, supervisor), Recommendations (skills, plugins), CLAUDE.local.md.
3. Include the AskUserQuestion approval gate with 4 options: approve, skip_hooks, skip_all_optional, edit.
4. Include handling for each option: "edit" asks free text then rebuilds; approve options proceed with appropriate subset.
5. Add note: "Skip individual AskUserQuestion calls for hooks/permissions/skills that the user already approved or declined in the proposal."

**Commit:** `feat: add Step 2.5 — proposal step with approval gate before execution`

**Dependencies:** none

### Task 1.4: Add Step 5.5 — CLAUDE.local.md Creation

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. Insert a new "## Step 5.5: CLAUDE.local.md Creation" section after Step 5 (CLAUDE.md audit), before Step 6 (enforcement rules).
2. Include detection logic: check if file exists, check if gitignored.
3. Include template content from spec: User Context (from $USER_CONTEXT), Import Project Instructions stub, Personal Notes stub.
4. Include .gitignore addition: `grep -q 'CLAUDE.local.md' .gitignore || echo "CLAUDE.local.md" >> .gitignore`
5. Include the explanation about worktrees: CLAUDE.local.md is gitignored, absent in worktrees, intentional for automated sessions.

**Commit:** `feat: add Step 5.5 — CLAUDE.local.md for personal preferences`

**Dependencies:** none

### Task 1.5: Update Step 7.5 — Hook Verification Pipeline

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. The existing Step 7.5 (lines ~350-450 on the feature branch) has hook templates but no verification. Add a "### Hook Verification Pipeline" subsection at the end of Step 7.5.
2. Include 4-stage verification from the spec:
   - Stage 1: Pipe test (echo JSON | jq parse)
   - Stage 2: jq validate (.claude/settings.json integrity)
   - Stage 3: Live proof (formatter available — prettier/ruff/gofmt test)
   - Stage 4: End-to-end smoke test (full pipeline with real event payload)
3. Include the verification report format (PASS/FAIL/SKIP table).
4. Include experience-based messaging: beginner gets "Want me to add it?", advanced gets "Hook will no-op until installed."
5. Include jq-not-found fallback message.

**Commit:** `feat: add 4-stage hook verification pipeline to Step 7.5`

**Dependencies:** none

### Task 1.6a: Add Step 7.7 — Create /verify Skill + Update Step 9.5 + Step 10

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. **Step 7.7 update** — after the existing skills recommendation content in Step 7.7, add a subsection "### Create /verify Skill". Include:
   - Instruction to create `<project>/.claude/skills/verify/SKILL.md` (NOT in Superflow's prompts/)
   - Full SKILL.md content from spec: frontmatter, detection logic, checks by stack (Node.js/TypeScript, Python, Go, Ruby), output format table
2. **New Step 9.5** — insert "## Step 9.5: Plugin Recommendations" after Step 9 (completion checklist), before Step 10:
   - Detection logic: check for `mcp__plugin_` tool names in session
   - Recommendation map table: context7, telegram, web-fetch
   - Experience-based presentation: verbose for beginners, terse for advanced
   - Rule: only recommend plugins actually detected in session
3. **Step 10 update** — replace the current Step 10 text with the spec's restart instruction:
   - "Important: Restart Claude Code to activate permissions and hooks."
   - Exact restart steps (exit, run claude or claude --resume)
   - Explain why: settings.json read at startup
   - Edge case: if no permissions/hooks set up, skip restart instruction, proceed to Phase 1

**Commit:** `feat: add /verify skill creation, plugin recommendations, restart instruction`

**Dependencies:** Task 1.5 (Step 7.7 comes after hook verification in the document flow)

### Task 1.6b: Update SKILL.md for /verify Skill

**Files:** `SKILL.md`
**Steps:**
1. Add `/verify` to the Architecture tree. In the `superflow/` tree under `prompts/`, add a comment or note: "Creates `<project>/.claude/skills/verify/SKILL.md` during Phase 0"

**Commit:** `docs: add /verify skill reference to SKILL.md architecture tree`

**Dependencies:** Task 1.6a

### Task 1.7: Update Completion Checklist (Step 9)

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. Update the Step 9 completion checklist to include all new steps. Add items for:
   - `- [ ] Empty vs existing project detected (Step 1.5)`
   - `- [ ] Proposal presented and approved (Step 2.5)`
   - `- [ ] CLAUDE.local.md created and gitignored (Step 5.5)`
   - `- [ ] Hook verification passed (pipe-test + jq + live proof + e2e) (Step 7.5)`
   - `- [ ] /verify skill created in project (Step 7.7)`
   - `- [ ] Plugin recommendations shown (Step 9.5)`
2. Update `.gitignore` checklist item to also mention CLAUDE.local.md and .superflow-state.json.

**Commit:** `feat: update Phase 0 completion checklist for all new steps`

**Dependencies:** Tasks 1.1-1.6b (checklist references all new steps)

---

## Sprint 2 — All Phases: Stages + Todos + State + Hooks

**Branch:** `feat/stages-state-hooks`
**PR target:** `main`
**Depends on:** Sprint 1

### Task 2.1: Create State Schema Template

**Files:** `templates/superflow-state-schema.json` (new)
**Steps:**
1. Create `templates/superflow-state-schema.json` with the JSON Schema from the spec:
   - `$schema`, `title`, `type: object`
   - Required fields: version, phase, last_updated
   - Properties: version (const 1), phase (0-3), phase_label, sprint (int|null), stage, stage_index (min 0), tasks_done (array of int), tasks_total, last_updated (date-time format)
   - context object: user_context, detected_stack, secondary_provider, supervisor_available, plan_file, spec_file, queue_file
   - history array: objects with phase, sprint, completed_at, pr

**Commit:** `feat: add .superflow-state.json schema template`

**Dependencies:** none

### Task 2.2a: Add Stage/Todo Structure to Phase 0

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. At the very top of the file (after the Detection section, before Step 1), add a "## Stage Structure" section that defines all 6 Phase 0 stages with their todos, exactly as specified:
   - Stage 1: Interview (4 todos)
   - Stage 2: Analysis (5 todos)
   - Stage 3: Proposal (2 todos)
   - Stage 4: Documentation (3 todos)
   - Stage 5: Environment Setup (8 todos)
   - Stage 6: Completion (3 todos)
2. Add the TaskCreate/TaskUpdate pattern example showing how to create a task at stage start and update todos as they complete.
3. Add state management instructions: "At the start of Phase 0, write `.superflow-state.json`" with the bash cat heredoc. After each stage transition, update via python3 one-liner (with fallback to full file overwrite if python3 unavailable).
4. At Step 1, add: before the interview, `TaskCreate(title: "Phase 0: Interview", ...)`.
5. At each subsequent step boundary (Step 2/3/4/5/6/7/8/9/10), add the appropriate TaskUpdate and state update calls.

**Commit:** `feat: add stage/todo progress tracking and state management to Phase 0`

**Dependencies:** Task 2.1 (references the schema)

### Task 2.2b: Cross-reference Other Phases from Phase 0

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. In the Phase 0 Stage Structure section, add a "### Phase Cross-Reference" note explaining that Phases 1-3 have their own stage structures (see Tasks 2.3a-2.3c) and that the state file transitions between them.
2. Add a brief routing note at the end of Phase 0's Stage Structure: "After Phase 0 completion, `.superflow-state.json` transitions to `phase: 1`."

**Commit:** `feat: add cross-phase state transition reference to Phase 0`

**Dependencies:** Task 2.2a

### Task 2.3a: Add Stage/Todo Structure to Phase 1 + Merge Steps 6+7

**Files:** `references/phase1-discovery.md`
**Steps:**
1. Add a "## Stage Structure" section at the top with 5 Phase 1 stages:
   - Stage 1: Research (4 todos)
   - Stage 2: Brainstorming (2 todos)
   - Stage 3: Product Approval — MERGED (2 todos)
   - Stage 4: Specification (3 todos)
   - Stage 5: Planning (4 todos)
2. **Merge Steps 6+7:** Replace the current Step 6 (Product Summary) and Step 7 (Product Brief) with a single "## Step 6: Product Approval (MERGED GATE)". Include:
   - Present Product Summary + Brief together in one message
   - Single AskUserQuestion approval gate with 3 options (approve, changes, restart)
   - Save brief to `docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md`
   - Handling for each option
3. **Renumber:** Old Steps 8-12 become Steps 7-11. Update all internal cross-references within the file (e.g., "proceed to Step 8" becomes "proceed to Step 7").
4. **Add AskUserQuestion to brainstorming:** In Step 5 (Approaches), add AskUserQuestion example for approach selection with options A/B/C/details. Add note: "Use AskUserQuestion when options are enumerable, free text for open-ended exploration."
5. Add TaskCreate/TaskUpdate calls at each stage boundary.
6. Add state management block: write/update `.superflow-state.json` at phase start and each stage transition.

**Commit:** `feat: add stages to Phase 1, merge Steps 6+7, add AskUserQuestion`

**Dependencies:** Task 2.1

### Task 2.3b: Add Stage/Todo Structure to Phase 2

**Files:** `references/phase2-execution.md`
**Steps:**
1. Add a "## Stage Structure (Per Sprint)" section at the top with 5 stages:
   - Stage 1: Setup (4 todos)
   - Stage 2: Implementation (2 todos)
   - Stage 3: Review (3 todos)
   - Stage 4: PAR (4 todos)
   - Stage 5: Ship (4 todos)
2. Add TaskCreate/TaskUpdate pattern for per-sprint tracking.
3. Add state management note: "During Phase 2 with supervisor, the supervisor writes `.superflow-state.json` — the Claude session does NOT write it directly. During Phase 2 without supervisor (single-session), the Claude session writes state at each stage transition."
4. At each step in the Per-Sprint Flow (Steps 1-11), annotate with the corresponding stage and todo update.

**Commit:** `feat: add stage/todo structure and state management to Phase 2`

**Dependencies:** Task 2.1

### Task 2.3c: Add Stage/Todo Structure to Phase 3

**Files:** `references/phase3-merge.md`
**Steps:**
1. Add a "## Stage Structure" section at the top with 3 stages:
   - Stage 1: Pre-merge (4 todos)
   - Stage 2: Merge (dynamic — one todo per PR)
   - Stage 3: Post-merge (5 todos)
2. Add TaskCreate/TaskUpdate pattern.
3. Add state management block for Phase 3.
4. Annotate existing merge steps with stage/todo references.

**Commit:** `feat: add stage/todo structure and state management to Phase 3`

**Dependencies:** Task 2.1

### Task 2.4: Document Hooks in SKILL.md + Phase 0

**Files:** `SKILL.md`, `references/phase0-onboarding.md`
**Steps:**
1. **SKILL.md** — add a "## State Management" section after the Startup Checklist:
   - Describe `.superflow-state.json` purpose: crash recovery, hook context injection
   - Add to startup checklist: "9. Check `.superflow-state.json` for resume context"
   - Document PostCompact hook behavior
   - Document SessionStart hook behavior
2. **SKILL.md** — add hook configuration patterns to the Architecture tree:
   - `templates/superflow-state-schema.json` — State file JSON Schema
3. **Phase 0** (`references/phase0-onboarding.md`) — in the proposal step (Step 2.5, added by Sprint 1 Task 1.3), add PostCompact and SessionStart hooks to the proposal's "Development Environment" section. These go to `~/.claude/settings.json` (user-level), unlike formatter hooks which go to `.claude/settings.json` (project-level).
4. In Step 7.5 (hooks setup), add the PostCompact and SessionStart hook JSON configurations from the spec, with the jq-based and no-jq fallback versions.
5. Add `.superflow-state.json` to the list of files to add to `.gitignore` during Phase 0 Step 6.

**Commit:** `feat: document state hooks (PostCompact, SessionStart) in SKILL.md and Phase 0`

**Dependencies:** Tasks 2.2a, 2.1

### Task 2.5: Add .gitignore entries for state file

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. In Step 6 (enforcement rules & gitignore), add `.superflow-state.json` to the gitignore check:
   ```
   grep -q '.superflow-state.json' .gitignore || echo ".superflow-state.json" >> .gitignore
   ```
2. Verify the existing `.worktrees/` gitignore check is still present.
3. Ensure `CLAUDE.local.md` gitignore entry is mentioned (cross-reference to Sprint 1 Task 1.4 which adds Step 5.5).

**Commit:** `feat: add .superflow-state.json to gitignore setup in Phase 0`

**Dependencies:** none

---

## Sprint 3 — Phase 0: Greenfield Path

**Branch:** `feat/phase0-greenfield`
**PR target:** `main`
**Depends on:** Sprint 2 (sequential; overlapping files with Sprints 1-2)

### Task 3.1: Create Greenfield Stack Templates

**Files:** `templates/greenfield/nextjs.md` (new), `templates/greenfield/python.md` (new), `templates/greenfield/generic.md` (new)
**Steps:**
1. Create `templates/greenfield/` directory.
2. Create `templates/greenfield/nextjs.md` with full content from spec:
   - Directory structure tree (src/app/, components/, lib/, public/, tests/)
   - package.json with Next.js 15, React 19, TypeScript 5, vitest, prettier, eslint
   - .gitignore (node_modules, .next, .env, .worktrees/, .superflow-state.json, CLAUDE.local.md)
   - tsconfig.json note (strict mode)
   - README.md template with {project_name}, {project_description} placeholders
3. Create `templates/greenfield/python.md` with full content from spec:
   - Directory structure tree (src/{project_name}/, tests/)
   - pyproject.toml with requires-python >=3.11, dev deps (pytest, ruff, mypy)
   - .gitignore (pycache, .env, .venv, .worktrees/, .superflow-state.json, CLAUDE.local.md)
4. Create `templates/greenfield/generic.md` with full content from spec:
   - Minimal structure (src/, tests/, docs/)
   - .gitkeep files

**Commit:** `feat: add greenfield stack templates (Next.js, Python, generic)`

**Dependencies:** none

### Task 3.2: Create CI Workflow Templates

**Files:** `templates/ci/github-actions-node.yml` (new), `templates/ci/github-actions-python.yml` (new)
**Steps:**
1. Create `templates/ci/` directory.
2. Create `templates/ci/github-actions-node.yml` from spec: checkout, setup-node 22, npm ci, lint, test, build.
3. Create `templates/ci/github-actions-python.yml` from spec: checkout, setup-python 3.12, pip install -e ".[dev]", ruff check, ruff format --check, pytest.

**Commit:** `feat: add GitHub Actions CI templates for Node.js and Python`

**Dependencies:** none

### Task 3.3: Add Greenfield Path to Phase 0 (Steps G1-G4)

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. After Step 1.5 (empty project detection, from Sprint 1), add a new major section: "## Greenfield Path (Steps G1-G6)".
2. Add a routing note: "If Step 1.5 detected greenfield, skip Steps 2-3 and enter this path. After G6, rejoin at Step 6."
3. **Step G1: Project Vision Interview** — AskUserQuestion for project type (webapp/api/cli/library/other), then free-text one-liner. Store as `$PROJECT_VISION`.
4. **Step G2: Stack Selection** — conditional AskUserQuestion based on project type:
   - webapp: nextjs / react_vite / python / other
   - api: express / fastapi / other
   - cli: python_click / go_cobra / node_commander / rust_clap / other
   - Follow-up: TypeScript vs JavaScript (if Node.js), database choice (if webapp/api)
5. **Step G2.5: Scaffolding Proposal** — after stack selection, present a proposal listing all files that will be created. Format: "I'll create: README.md, CLAUDE.md, .gitignore, CI workflow, package.json/pyproject.toml, src/ structure." Use AskUserQuestion with options (approve / edit / cancel). Only proceed to scaffolding after approval. This prevents unexpected file creation in the user's project.
6. **Step G3: Scaffolding** — instructions to read the appropriate template from `templates/greenfield/<stack>.md`, replace `{project_name}` and `{project_description}`, create all files. Include `npm install` / `pip install` / etc. after scaffolding. Emphasize: do NOT use create-next-app or similar generators.
7. **Step G4: CI Setup** — AskUserQuestion (yes/no/advanced). If yes, copy from `templates/ci/github-actions-<stack>.yml` to `.github/workflows/ci.yml`.

**Commit:** `feat: add greenfield path Steps G1-G4 to Phase 0 (incl. scaffolding proposal gate)`

**Dependencies:** Sprint 1 Task 1.2 (Step 1.5 must exist), Sprint 2 (sequential ordering)

### Task 3.4: Add Greenfield Path Steps G5-G6 + SKILL.md Update

**Files:** `references/phase0-onboarding.md`, `SKILL.md`
**Steps:**
1. **Step G5: CLAUDE.md + llms.txt for New Projects** — generate CLAUDE.md from stack knowledge (not analysis, since no existing code). Include: project overview with stack, key files table, commands (dev/test/lint/build), conventions. Generate minimal llms.txt: project description, src/ entry, config files, docs.
2. **Step G6: Connect to Shared Setup** — strict scaffolding order:
   1. Write .gitignore FIRST
   2. Scaffold all other files
   3. `git add` by specific file names (NOT `git add -A`)
   4. Initial commit with message template
   5. Rejoin shared Phase 0 from Step 6 (enforcement rules). Skip Steps 2-5 (analysis/report/llms.txt/CLAUDE.md already done).
   6. Transition message: "Project scaffolded! Now let's plan what to build."
3. **SKILL.md** — update Architecture tree to include:
   - `templates/greenfield/` directory with nextjs.md, python.md, generic.md
   - `templates/ci/` directory with github-actions-node.yml, github-actions-python.yml

**Commit:** `feat: add greenfield Steps G5-G6, update SKILL.md architecture`

**Dependencies:** Task 3.3

### Task 3.5: Add Greenfield Stages to Phase 0 Stage Structure

**Files:** `references/phase0-onboarding.md`
**Steps:**
1. In the Stage Structure section (added by Sprint 2 Task 2.2), add a parallel greenfield stage set:
   ```
   Greenfield Stage 1: "Vision" — Ask project type, description
   Greenfield Stage 2: "Stack" — Stack selection, follow-up questions
   Greenfield Stage 3: "Scaffold" — Create files, install deps
   Greenfield Stage 4: "CI" — GitHub Actions setup
   Greenfield Stage 5: "Documentation" — CLAUDE.md + llms.txt for new project
   Greenfield Stage 6: "Connect" — Initial commit, rejoin shared setup
   ```
2. Add TaskCreate/TaskUpdate calls for greenfield path stages.
3. Add state management: write `.superflow-state.json` with greenfield-specific stage names.

**Commit:** `feat: add greenfield stage structure with progress tracking`

**Dependencies:** Sprint 2 Task 2.2a, Task 3.4

---

## Sprint 4 — Phase 2: Parallelism + Supervisor

**Branch:** `feat/phase2-parallelism`
**PR target:** `main`
**Depends on:** Sprint 3 (sequential; uses state management from Sprint 2)

### Task 4.1: Add `_write_state()` to supervisor.py

**Files:** `lib/supervisor.py`
**Steps:**
1. Add a new function `_write_state()` after the existing `_now_iso()` function (line 187). Signature:
   ```python
   def _write_state(repo_root: str, phase: int, sprint: int | None,
                    stage: str, queue) -> None:
   ```
2. Implementation from the spec:
   - Build state dict with version, phase, phase_label (map from int), sprint, stage, stage_index (map from stage name), tasks_done (completed sprint IDs from queue), tasks_total (len of queue.sprints), last_updated
   - Write to `repo_root/.superflow-state.json` using tmp+rename atomic pattern (same pattern as queue.save())
3. Add call sites in `execute_sprint()` (line 225):
   - After marking in_progress (line 240): `_write_state(repo_root, phase=2, sprint=sid, stage="setup", queue=queue)`
4. Add call sites in `_attempt_sprint()` (line 268):
   - Before subprocess.run (line 281): `_write_state(repo_root, phase=2, sprint=sid, stage="implementation", queue=queue)`
   - After successful PR verification (line 312-313): `_write_state(repo_root, phase=2, sprint=sid, stage="ship", queue=queue)`
5. Guard: only call `_write_state` when `queue_lock is None` (sequential mode). When `queue_lock` is not None (parallel mode), skip these calls — `parallel.py` writes state under `queue_lock` at each sprint transition instead (see Task 4.5).

**Commit:** `feat: add _write_state() for .superflow-state.json projection in supervisor`

**Dependencies:** Sprint 2 Task 2.1 (schema)

### Task 4.2: Add Step Verification to supervisor.py

**Files:** `lib/supervisor.py`
**Steps:**
1. Add `REQUIRED_STEPS` constant and `_verify_steps()` function after `_parse_json_summary()` (line 209):
   ```python
   REQUIRED_STEPS = {"baseline_tests", "implementation", "par", "pr_created"}

   def _verify_steps(summary: dict) -> list[str]:
       """Check if all required steps were completed. Returns list of missing steps."""
       completed = set(summary.get("steps_completed", []))
       return list(REQUIRED_STEPS - completed)
   ```
2. In `_attempt_sprint()`, after `summary = _parse_json_summary(...)` (line 299), add:
   ```python
   if summary:
       missing = _verify_steps(summary)
       if missing:
           logger.warning("Sprint %d missing steps: %s", sid, missing)
   ```
3. This is backward compatible — if `steps_completed` is absent from the summary, `_verify_steps` returns all REQUIRED_STEPS as missing (just a warning, does not block).

**Commit:** `feat: add step verification with warning for skipped steps`

**Dependencies:** none

### Task 4.3: Add Parallel Dispatch Instructions to phase2-execution.md

**Files:** `references/phase2-execution.md`
**Steps:**
1. After the existing "## Per-Sprint Flow" section and before the current Step 5, add a new section "## Parallel Dispatch within a Sprint" with:
   - Independence criteria (4 rules: different files, no data dependency, no shared state, no order constraint)
   - Wave analysis algorithm: list files per task, build dependency graph, group into waves
   - Wave dispatch pattern: each wave dispatches agents with `run_in_background: true`, wait for all before next wave
   - Example: 6 tasks → 4 waves
   - Fallback: if ≤3 tasks, skip wave analysis and dispatch sequentially
2. Update Step 5 in the Per-Sprint Flow to reference the parallel dispatch section:
   - "5a. Analyze task list — identify independent tasks (see Parallel Dispatch above)"
   - "5b. Group into waves"
   - "5c. For Wave 1: dispatch each as Agent(run_in_background: true, model: sonnet)"
   - "5d. For subsequent waves: same pattern"
   - "5e. After all waves: verify no file conflicts"

**Commit:** `feat: add wave-based parallel dispatch instructions to Phase 2`

**Dependencies:** none

### Task 4.4: Update Sprint Prompt Template

**Files:** `templates/supervisor-sprint-prompt.md`
**Steps:**
1. Add a "## Step Verification" section after the Instructions section. Content from spec:
   - After worktree setup: verify branch with `git branch --show-current`
   - After baseline tests: paste test output
   - After implementation: verify all tasks DONE, list changed files
   - After internal review: paste reviewer verdicts
   - After PAR: verify .par-evidence.json exists
   - After PR creation: verify PR URL with `gh pr view`
   - If any step skipped (e.g., after compaction), go back and complete it
   - Check `.superflow-state.json` if unsure of progress
2. Add a "## Parallel Task Dispatch" section:
   - If sprint plan has multiple tasks, analyze for independence
   - Different files + no data dependency = parallel
   - Group into waves, dispatch with Agent(run_in_background: true)
   - If ≤3 tasks, dispatch sequentially
3. Update the JSON summary format in Instruction #4 to include `steps_completed`:
   ```json
   {"status":"completed","pr_url":"...","tests":{"passed":0,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"},"steps_completed":["baseline_tests","implementation","internal_review","test_verification","par","pr_created"]}
   ```

**Commit:** `feat: add step verification and parallel dispatch to sprint prompt template`

**Dependencies:** none

### Task 4.5: Add State Writes to parallel.py

**Files:** `lib/parallel.py`
**Steps:**
1. Import `_write_state` from `lib.supervisor`.
2. In `_worker()`, after each sprint completes (after `on_sprint_done` callback), write state **under `queue_lock`** to avoid race conditions:
   ```python
   with queue_lock:
       _write_state(repo_root, phase=2, sprint=sid, stage="ship", queue=queue)
   ```
   This writes state at each sprint transition during parallel mode, not just at the end.
3. Remove the Task 4.1 guard that skips `_write_state` when `queue_lock is not None`. Instead, the parallel.py code handles locking explicitly so the supervisor's own `_write_state` calls in `execute_sprint` are still skipped (no double-write), but parallel.py writes state per-sprint under lock.
4. After `execute_parallel()` completes (all futures resolved), write a final state snapshot:
   ```python
   _write_state(repo_root, phase=2, sprint=None, stage="ship", queue=queue)
   ```
5. Add test: `test_parallel_writes_state_at_each_sprint_transition` — mock `_write_state`, run `execute_parallel` with 3 sprints, verify `_write_state` called once per sprint (under lock) + once at end = 4 calls total. Verify no `.tmp` files remain (atomic write).

**Commit:** `feat: add per-sprint state writes under queue_lock in parallel mode`

**Dependencies:** Task 4.1

### Task 4.6: Add Task-Level Fields to Queue Schema

**Files:** `lib/queue.py`
**Steps:**
1. This is a documentation/schema task. The sprint dict already accepts arbitrary keys (it's a plain dict). No code changes needed in queue.py — just verify that `save()` and `load()` preserve extra fields.
2. Add a docstring update to `SprintQueue.__init__` documenting the optional `tasks` field:
   ```python
   """Manages a queue of sprints with dependency tracking.

   Sprint dict fields:
       id, title, status, plan_file, branch, depends_on, pr, retries, max_retries, error_log
       Optional: tasks (list of task dicts for intra-sprint tracking)
   """
   ```
3. The existing save/load passes through `data["sprints"]` as-is, so any extra fields (including `tasks`) are preserved automatically.

**Commit:** `docs: document optional tasks field in sprint queue schema`

**Dependencies:** none

### Task 4.7a: Unit Tests for New Functionality

**Files:** `tests/test_supervisor.py`, `tests/test_queue.py`
**Steps:**

**test_supervisor.py** — add after existing tests:
1. `test_write_state_creates_file` — call `_write_state()` with a mock queue, verify `.superflow-state.json` exists with correct keys (version, phase, sprint, stage, tasks_done, tasks_total, last_updated).
2. `test_write_state_atomic` — call `_write_state()`, verify no `.tmp` file remains after write.
3. `test_write_state_updates_on_sprint_transition` — call `_write_state()` twice with different stages, verify file content reflects the second call.
4. `test_verify_steps_all_present` — call `_verify_steps()` with all required steps, verify returns empty list.
5. `test_verify_steps_missing` — call `_verify_steps()` with some steps missing, verify returns the missing ones.
6. `test_verify_steps_backward_compatible` — call `_verify_steps()` with empty dict (no `steps_completed` key), verify returns all REQUIRED_STEPS without error.

**test_queue.py** — add after existing tests:
7. `test_sprint_with_tasks_field` — create a queue with sprints that have a `tasks` field, save/load, verify tasks preserved.
8. `test_sprint_without_tasks_field` — create a queue without tasks field, save/load, verify no error (backward compat).

**Commit:** `test: add unit tests for _write_state, _verify_steps, queue tasks`

**Dependencies:** Tasks 4.1, 4.2, 4.6

### Task 4.7b: Integration Tests for Parallel State Writes

**Files:** `tests/test_parallel.py`
**Steps:**
1. `test_parallel_writes_state_at_each_sprint_transition` — mock `_write_state`, run `execute_parallel` with 3 sprints, verify `_write_state` called once per sprint (under lock) + once at end = 4 calls total.
2. `test_parallel_state_write_no_tmp_files` — run `execute_parallel`, verify no `.tmp` files remain after completion (atomic write integrity).
3. `test_parallel_state_mid_batch_reflects_progress` — run `execute_parallel` with 3 sprints, mock `_write_state` to capture args, verify that mid-batch calls show incrementally increasing `tasks_done`.

**Commit:** `test: add integration tests for parallel state writes`

**Dependencies:** Tasks 4.1, 4.5

### Task 4.8: Update SKILL.md for Parallelism

**Files:** `SKILL.md`
**Steps:**
1. In the Phase 2 description line (currently: "Phase 2 (autonomous, 11 steps per sprint): ..."), add mention of parallel dispatch.
2. In the Architecture tree, confirm `templates/superflow-state-schema.json` is listed (added by Sprint 2 Task 2.4).
3. Add a note in the Phase References section: "State: `templates/superflow-state-schema.json`, `.superflow-state.json` (runtime)"

**Commit:** `docs: update SKILL.md with parallelism and state management references`

**Dependencies:** none

### Task 4.9: Final Doc Consistency Pass

**Files:** `SKILL.md`, `CLAUDE.md`
**Steps:**
1. Update SKILL.md phase summaries to reflect all changes from Sprints 1-4: step counts, new steps (1.5, 2.5, 5.5, 7.5 pipeline, 9.5, G1-G6), architecture tree entries (templates/greenfield/, templates/ci/, templates/superflow-state-schema.json, .superflow-state.json).
2. Update SKILL.md architecture tree to include all new files and directories added across all sprints.
3. Update CLAUDE.md Key Files table if any line counts or purposes changed significantly.
4. Verify all cross-references between phase docs are consistent (step numbers, stage counts).

**Commit:** `docs: final consistency pass — SKILL.md summaries, architecture tree, CLAUDE.md`

**Dependencies:** Tasks 4.1-4.8 (runs after all other Sprint 4 tasks to capture final state)

---

## Sprint Queue File

For the supervisor, the corresponding `sprint-queue.json` would be:

```json
{
  "feature": "phase0-improvements",
  "created": "2026-03-23T00:00:00Z",
  "sprints": [
    {
      "id": 1,
      "title": "Phase 0: Interactive Onboarding",
      "status": "pending",
      "plan_file": "docs/superflow/plans/2026-03-23-phase0-improvements.md#sprint-1",
      "branch": "feat/phase0-interactive-onboarding",
      "depends_on": [],
      "pr": null,
      "retries": 0,
      "max_retries": 2,
      "error_log": null
    },
    {
      "id": 2,
      "title": "All Phases: Stages + State + Hooks",
      "status": "pending",
      "plan_file": "docs/superflow/plans/2026-03-23-phase0-improvements.md#sprint-2",
      "branch": "feat/stages-state-hooks",
      "depends_on": [1],
      "pr": null,
      "retries": 0,
      "max_retries": 2,
      "error_log": null
    },
    {
      "id": 3,
      "title": "Phase 0: Greenfield Path",
      "status": "pending",
      "plan_file": "docs/superflow/plans/2026-03-23-phase0-improvements.md#sprint-3",
      "branch": "feat/phase0-greenfield",
      "depends_on": [2],
      "pr": null,
      "retries": 0,
      "max_retries": 2,
      "error_log": null
    },
    {
      "id": 4,
      "title": "Phase 2: Parallelism + Supervisor",
      "status": "pending",
      "plan_file": "docs/superflow/plans/2026-03-23-phase0-improvements.md#sprint-4",
      "branch": "feat/phase2-parallelism",
      "depends_on": [3],
      "pr": null,
      "retries": 0,
      "max_retries": 2,
      "error_log": null
    }
  ]
}
```

## Estimated Effort

| Sprint | Tasks | Type | Est. Time |
|--------|-------|------|-----------|
| 1 | 8 tasks (1.1-1.5, 1.6a, 1.6b, 1.7) | Markdown | ~30 min |
| 2 | 8 tasks (2.1, 2.2a, 2.2b, 2.3a, 2.3b, 2.3c, 2.4, 2.5) | Markdown + light JSON | ~35 min |
| 3 | 5 tasks (3.1-3.5) | Markdown + YAML | ~25 min |
| 4 | 10 tasks (4.1-4.6, 4.7a, 4.7b, 4.8, 4.9) | Python + Markdown + tests | ~45 min |
| **Total** | **31 tasks** | | **~135 min** |

All sprints are strictly sequential (overlapping files: phase0-onboarding.md, SKILL.md). Each sprint branches from the merged result of the previous one. Total wall time = ~135 min.

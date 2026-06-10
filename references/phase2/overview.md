# Phase 2: Autonomous Execution — Overview

**DAG:** `references/phase2/workflow.json` | **Steps:** `references/phase2/steps/`

Load this file once at Phase 2 start. Load `workflow.json` to get stage structure and decision matrix.
Load individual step files only when entering that step.

---

## Phase 2 in One Paragraph

Phase 2 is an autonomous sprint execution loop. The orchestrator reads the plan, groups sprints into
parallel waves (if independent), and runs each sprint through 6 stages: Setup → Implementation →
Review → Docs → PAR → Ship. The orchestrator never writes code directly — it dispatches subagents
for all implementation, review, and documentation work, then coordinates results. It runs
continuously without asking the user. Each sprint produces a PR; Phase 2 ends with a Completion
Report when all sprints are done.

---

## Wave Analysis

Independent tasks within a sprint are dispatched in parallel waves:

1. List files each task modifies.
2. Build dependency graph from file overlaps and explicit `depends_on` fields.
3. Group tasks into waves — tasks in the same wave have no overlapping files or data dependencies.
4. Dispatch each wave: all tasks via `Agent(run_in_background: true)`.
5. Wait for wave to complete before dispatching the next.

Sprint-level parallelism works the same way: independent sprints run in separate worktrees
concurrently. `max_parallel` is derived from `git_workflow_mode` (parallel_wave_prs enables it).
Fallback: if ≤3 tasks or all sprints form a single dependency chain, skip wave analysis and run
sequentially — parallelism overhead isn't worth it for small counts.

See `steps/impl-dispatch.md` for the full wave analysis procedure and model selection table.

---

## Adaptive Model Selection

Sprint complexity tag in the plan drives implementer tier:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | high | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | sonnet | max | 5+ files, new architecture, security-sensitive |

**ALWAYS pass `model:` explicitly in every Agent() call** — agent definition frontmatter `model:`
is NOT reliably inherited. Dispatch rule: implementers → `model: "sonnet"` (haiku permitted for
mechanical Phase 0 file/config checks); standard reviewers + doc-writers → `model: "opus"`; deep
reviewers + `deep-analyst` → `"fable"` (model_profile=frontier, default) or `"opus"` (model_profile=balanced
— read `context.model_profile` from `.superflow-state.json`). A forgotten `model:` now silently inherits
the parent frontier model (Fable) — the cost of forgetting went UP.

---

## Orchestrator Tool Budget (Rule 11 Reminder)

The orchestrator does NOT Read/Grep/Glob source files larger than 50 lines. Allowed direct tools:
- **Bash for status:** `git status`, `git log`, `gh run list`, `gh pr view`, `ls`, `pwd`, `date`
- **Bash for state I/O:** `.superflow-state.json`, `.par-evidence.json`, CHANGELOG appends
- **Bash for testcontainer hygiene:** `bash $SUPERFLOW_SKILL_ROOT/tools/cleanup-testcontainers.sh`
  — this exact helper invocation only; raw `docker` commands stay outside the budget
- **Read for short files (<50 lines):** state files, `package.json`, the current sprint plan section
- **TaskCreate / TaskUpdate** for stage tracking
- **Agent (Task) tool** to dispatch subagents

Exceptions (always allowed under Rule 11): this file (`overview.md`), `workflow.json`, charter,
and `superflow-enforcement.md` — these are orchestration files, not source files.

For everything else — code reading, test failure diagnosis, directory exploration — dispatch
`deep-analyst` and take a <2k-token summary back.

## Testcontainers Cleanup Discipline

- **Ryuk gated on CI — implementer duty.** Testcontainers' Ryuk reaper must stay enabled locally;
  `TESTCONTAINERS_RYUK_DISABLED=true` is set only when `process.env.CI === 'true'`. This hygiene
  duty lives in the implementer agent definitions (`agents/*-implementer.md`) — that is what
  Phase 2 actually dispatches. Never set the variable globally in shell profiles or `.env` —
  stale containers accumulate silently.
- **After every integration test run** (`pnpm test:integration` or equivalent), the orchestrator
  runs ONLY the helper:
  ```bash
  bash $SUPERFLOW_SKILL_ROOT/tools/cleanup-testcontainers.sh
  ```
  The helper is label-based: `docker ps -aq --filter "label=org.testcontainers=true"` —
  testcontainers stamps this label on every container it starts. An optional image-filter argument
  narrows the match further. Name-regex matching is FORBIDDEN: default docker names
  (`adjective_surname` style) match any unrelated container.
- Raw `docker` commands stay outside the orchestrator budget (Rule 11) — the helper invocation
  above is the only allowed form. The script lives at `tools/cleanup-testcontainers.sh` in the
  Superflow skill root.

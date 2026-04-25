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
| medium | standard-implementer | sonnet | medium | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | sonnet | high | 5+ files, new architecture, security-sensitive |

**ALWAYS pass `model: "sonnet"` explicitly** in Agent() calls for implementers and doc-writers.
Agent definition frontmatter `model:` is NOT reliably inherited — without it, subagents inherit
the parent's model (Opus), wasting tokens on tasks Sonnet handles equally well.

---

## Orchestrator Tool Budget (Rule 11 Reminder)

The orchestrator does NOT Read/Grep/Glob source files larger than 50 lines. Allowed direct tools:
- **Bash for status:** `git status`, `git log`, `gh run list`, `gh pr view`, `ls`, `pwd`, `date`
- **Bash for state I/O:** `.superflow-state.json`, `.par-evidence.json`, CHANGELOG appends
- **Read for short files (<50 lines):** state files, `package.json`, the current sprint plan section
- **TaskCreate / TaskUpdate** for stage tracking
- **Agent (Task) tool** to dispatch subagents

Exceptions (always allowed under Rule 11): this file (`overview.md`), `workflow.json`, charter,
and `superflow-enforcement.md` — these are orchestration files, not source files.

For everything else — code reading, test failure diagnosis, directory exploration — dispatch
`deep-analyst` and take a <2k-token summary back.

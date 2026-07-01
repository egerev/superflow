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

## Phase 2 Launch

At Phase 2 launch — right after plan approval, before the first sprint — PRINT this ready-to-paste
`/goal` suggestion for the user. `/goal` is a user-only command: the model CANNOT set it; never
pretend otherwise.

> Optional watchdog for this run — paste:
> `/goal Superflow Phase 2 complete: all <N> sprints implemented, unified-reviewed, PRs created and CI-green, Completion Report delivered.`

Replace `<N>` with the actual sprint count. Note: the evaluator (Haiku, prompt-based Stop hook)
judges only what is visible in the transcript, so the orchestrator must keep narrating sprint
completions (it already does); one goal per session; survives `--resume`; the user clears it with
`/goal clear`. Subagents do NOT inherit goals — per-sprint goal-direction remains the Autonomy
Charter injection (already shipped).

For everything Workflow-tool related (saved `/superflow-review` and `/superflow-wave` workflows,
the `context.use_workflows` opt-in, availability checks, fallbacks), see
`references/workflow-orchestration.md` — the single authority on Workflow usage inside Superflow.

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
reviewers + `deep-analyst` → `model: "opus"` (Fable is blocked — depth comes from effort: deep = max,
standard = high, set in agent frontmatter). A forgotten `model:` silently inherits the orchestrator's
session model (Opus), which is wrong for implementers — more expensive than the intended Sonnet.

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

## Post-Sprint-Loop: Release Gate

After ALL sprints are done and the optional Holistic Review completes, BEFORE the Completion
Report and Phase 3:

1. **Read `references/phase2/steps/release-gate.md`** — full stage instructions.
2. **Run the release gate** (`phase_gates.release_gate` in `workflow.json`): boot the assembled
   app, run integration + headless E2E, extract per-journey outcomes, call `tools/release-gate.sh`
   to compute and persist the verdict.
3. **`.superflow/release-gate/verdict.json` is the Phase 3 gate key.** Phase 3 refuses merge
   unless `verdict=PASS` (or `verdict=SKIPPED` for library projects). FAIL → fix and re-run.
4. **No-vacuous-pass invariant:** a web project with charter journeys and `specs_ran=false` →
   verdict=FAIL regardless of other results. Zero execution is not zero failures.

**Ordering (canonical):**
```
sprint loop → holistic review (if required) → RELEASE GATE → Completion Report → Phase 3
```

Declaring the gate in `workflow.json` alone is insufficient — the orchestrator must explicitly
load and execute `references/phase2/steps/release-gate.md` at this stage boundary.

---

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

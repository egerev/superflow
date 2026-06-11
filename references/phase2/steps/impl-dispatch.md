# Step: impl-dispatch

**Stage:** implementation
**Loaded by orchestrator:** when entering the implementation stage
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Wave Analysis (Task-Level Parallelism)

Before dispatching, analyze sprint tasks for independence:

**Independence criteria** — ALL must hold for parallel dispatch:
1. Tasks modify different files (no overlapping paths)
2. No data dependency (Task B doesn't read output of Task A)
3. No shared state (no common DB table, config, or global variable)
4. No ordering constraint (either can complete first)

**Wave analysis procedure:**
1. List files each task modifies
2. Build dependency graph from file overlaps and explicit `depends_on`
3. Group tasks into waves — tasks in the same wave are fully independent
4. Dispatch each wave: all tasks via `Agent(run_in_background: true)`
5. Wait for wave to complete before dispatching next wave

Example: 6 tasks → Wave 1: tasks 1,2,3 (independent) → Wave 2: task 4 (depends on 1) → Wave 3: tasks 5,6

Fallback: if ≤3 tasks in the sprint, skip wave analysis and dispatch sequentially.

After all waves: `git status` to verify no file conflicts between agents.

## Sprint-Level Parallelism

Independent sprints (non-overlapping files, no `depends_on` links) run concurrently in separate
worktrees. Parse all sprint `files:` and `depends_on:` metadata, build dependency graph, group into
waves by topological sort. Store wave plan in `.superflow-state.json` under `context.sprint_waves`.

**Preferred when available — saved /superflow-wave workflow (Claude runtime, opt-in).** When
RUNTIME:claude, `context.use_workflows=true` in `.superflow-state.json`, and workflows are
available, PREFER invoking the saved `/superflow-wave` workflow for the wave instead of N manual
`Agent()` calls:

```
/superflow-wave  args: {sprints: [{id, branch, worktree, task}], charter_path: "<charter file>"}
```

It fans out one implementer per sprint in parallel (implementation ONLY — code, tests, commit
inside the given worktree) and returns a per-sprint status array; failed or unparseable results
are treated as implementation-failed (fail closed). REVIEW IS NOT IN THE WORKFLOW — exactly as
with manual dispatch, the ORCHESTRATOR runs review → docs → PAR → ship per sprint afterwards.
Details and availability checks: `references/workflow-orchestration.md`.

**Fallback:** Codex runtime, `use_workflows=false`, or workflows unavailable → the existing
parallel Agent dispatch below, unchanged.

**Claude runtime — implementation-only parallelism.** Subagents CANNOT dispatch further subagents
via the Agent tool, so a sprint agent can never run reviews or create PRs itself. A parallel wave
is N implementers dispatched in parallel — one per sprint, each in its own worktree:

```
# One call per sprint in the wave — implementation ONLY:
Agent(
  subagent_type: "standard-implementer",  # tier per complexity table below
  model: "sonnet",                        # ALWAYS explicit
  run_in_background: true,
  prompt: "Implement Sprint N: [title] in worktree .worktrees/sprint-N — tasks, code, tests only.
           Do NOT review, update docs, write PAR evidence, or create PRs."
)
```

As each implementer finishes, the ORCHESTRATOR runs the remaining stages for that sprint
sequentially: review → docs → PAR → ship. FORBIDDEN on Claude runtime: dispatching one
implementer to "execute the full Per-Sprint Flow" — reviews and PR creation inside an implementer
are impossible (no nested Agent dispatch), so that pattern silently skips every gate.

**Codex runtime exception.** With `[agents] max_threads=6, max_depth=2`, sprint supervisors
spawned via `spawn_agent` CAN spawn their own per-sprint implement/review/doc agents — the full
per-sprint flow inside a supervisor is allowed there. Old `max_depth=1` configs fall back to
sequential sprints. See `references/codex-dispatch-patterns.md`.

Fallback: if ≤3 total sprints or all sprints form a single dependency chain, run sequentially.
Holistic review is mandatory when `max_parallel > 1` (enforcement rule 9).

## Adaptive Model Selection

Sprint complexity tag in the plan drives implementer tier:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | high | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | sonnet | max | 5+ files, new architecture, security-sensitive |

**ALWAYS pass `model: "sonnet"` explicitly for implementers** — frontmatter `model:` is NOT
reliably inherited. A forgotten `model:` now silently inherits the parent frontier model (Fable) —
the cost of forgetting went UP.

Include `llms.txt` content in agent context (if file exists).
Extract and paste the exact task list, file paths, and expected behaviors verbatim into the
implementer prompt — do NOT rely on LLM memory of the plan.

If `frontend: true` is set on the sprint, also load `frontend-testing.md` and follow its
visual verification protocol after implementation completes.

## Failure Handling

1. Read failure output. Identify the failing assertion or error.
2. Form a hypothesis before touching code.
3. Targeted fix, then verify with the specific test, then the full suite.
4. 3+ failed attempts on the same issue: likely architectural problem. Report BLOCKED with
   evidence, suggest rethinking approach.
5. Agent BLOCKED: re-dispatch with more context. 2 fails on same agent task → orchestrator
   implements the specific task manually as a last resort.
6. Never stop to ask the user during Phase 2. Accumulate issues and report at end.

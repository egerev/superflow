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

Each parallel sprint agent runs the FULL 6-stage Per-Sprint Flow independently:
```
Agent(
  subagent_type: "standard-implementer",
  model: "sonnet",  # ALWAYS explicit
  run_in_background: true,
  prompt: "Execute Sprint N: [title] — full Per-Sprint Flow. ..."
)
```

Fallback: if ≤3 total sprints or all sprints form a single dependency chain, run sequentially.
Holistic review is mandatory when `max_parallel > 1` (enforcement rule 9).

## Adaptive Model Selection

Sprint complexity tag in the plan drives implementer tier:

| Complexity | Agent | Model | Effort | When |
|-----------|-------|-------|--------|------|
| simple | fast-implementer | sonnet | low | 1-2 files, CRUD/template, <50 lines |
| medium | standard-implementer | sonnet | medium | 2-5 files, some new logic. Default if untagged. |
| complex | deep-implementer | sonnet | high | 5+ files, new architecture, security-sensitive |

**ALWAYS pass `model: "sonnet"` explicitly** — frontmatter `model:` is NOT reliably inherited.
Without it, subagents inherit the parent's model (Opus), wasting tokens.

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

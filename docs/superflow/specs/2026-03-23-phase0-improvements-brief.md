# Phase 0 Improvements + Parallelism + Stability — Product Brief

## Problem Statement

Superflow Phase 0 gives identical experience to everyone — beginner web developer or experienced architect. Doesn't adapt to user, doesn't configure working environment (hooks, skills), doesn't help with empty projects. Phase 2 runs sequentially — one implementer at a time. Superflow context is lost on compaction/restart. Steps within phases aren't visualized — user can't see progress, LLM may skip substeps.

## Jobs to Be Done

1. **Existing project onboarding**: When I run Superflow on an existing project for the first time, I want it to ask who I am and adapt, so I don't get a 5-page report as a solo-founder, or miss important recommendations as a beginner.

2. **Proposal before action**: When Phase 0 finishes analysis, I want to see a plan of what it's about to do (CLAUDE.md, hooks, skills, permissions) and approve it — not receive a fait accompli.

3. **Hook reliability**: When Phase 0 sets up hooks (auto-format, lint), I want to be sure they actually work, not silently do nothing.

4. **Greenfield support**: When starting a new project from scratch, I want Superflow to help pick stack, set up CI, create initial structure — not say "no codebase, nothing to analyze".

5. **Parallel execution**: When Phase 2 runs a sprint with 6 independent tasks, I want the orchestrator to launch multiple implementers in parallel, not wait for each one to finish.

6. **Context persistence**: When context compacts or I restart the session, I want Superflow to automatically restore where it was — which phase, sprint, step — and continue.

7. **Progress visualization**: When Superflow works, I want to see a visual checklist that updates in real-time, not just text "doing Step 5".

## User Stories

**US-1 (Phase 0, existing project):** Solo developer with Next.js project runs `/superflow`. Phase 0 asks "Solo or team?", "Experience with stack?", "Have CI?" via AskUserQuestion buttons. After analysis (4 agents), shows proposal with preview. User clicks "Ok". Phase 0 executes, verifies hooks (pipe-test → jq → live proof), says: "Done. Restart Claude Code to pick up permissions and hooks."

**US-2 (Phase 0, greenfield):** User creates empty folder, `git init`, runs `/superflow`. Phase 0 detects empty project, asks: "New project! What are we building?" → stack choice, solo/team, CI needed. Generates initial structure: README, CLAUDE.md, .gitignore, CI workflow. Proceeds to Phase 1.

**US-3 (Phase 2, parallelism):** Plan has Sprint 1 with 6 tasks, 3 independent. Orchestrator detects this and launches 3 implementers in parallel (Agent with run_in_background). When all 3 finish, launches remaining 3 (dependent). Review covers the full sprint.

**US-4 (stability):** During Phase 2, compaction occurs. PostCompact hook reads `.superflow-state.json`: `{phase: 2, sprint: 3, step: "implementation", tasks_done: [1,2,3]}`. SessionStart hook on resume injects: "You are in Phase 2, Sprint 3. Tasks 1-3 done. Re-read phase2-execution.md."

**US-5 (progress visualization):** In Phase 0, after proposal approval, user sees TaskCreate checklist updating in real-time as each step completes.

## Success Criteria

1. Phase 0 on existing project asks ≤5 questions via AskUserQuestion and shows proposal before execution
2. Hooks pass pipe-test + jq validation — if they fail, user is informed
3. Phase 0 on empty project creates working initial structure (git init, README, CI, CLAUDE.md)
4. Phase 2 with ≥3 independent tasks launches them in parallel
5. After compaction/restart, Superflow restores context from `.superflow-state.json`
6. Every phase shows TaskCreate progress — user sees updating checklist

## Edge Cases

- User refuses interview ("just go") → use defaults (solo, intermediate, no CI)
- Hook pipe-test fails (formatter not installed) → inform, offer to install, don't block
- Empty project but has .git with history → not greenfield, treat as existing
- Supervisor unavailable (no python3) → parallelism via Agent tool, not supervisor
- AskUserQuestion unavailable (non-interactive mode) → fallback to text questions

## Sprint Breakdown

| Sprint | Scope | Type | Depends on |
|--------|-------|------|-----------|
| 1 | Phase 0: Interactive Onboarding (existing) | Markdown | — |
| 2 | All Phases: Stages + Todos + State + Hooks | Markdown + light Python | — |
| 3 | Phase 0: Greenfield path | Markdown | Sprint 1 |
| 4 | Phase 2: Parallelism + Supervisor | Python + tests | Sprint 2 |

Sprint 1 and 2 are independent — can run in parallel. Sprint 3 depends on 1 (extends Phase 0). Sprint 4 depends on 2 (uses state management).

## Process Improvement (meta)

Product Summary + Brief should be merged into a single approval gate in Phase 1 (Steps 6+7 combined). This is the last user touchpoint before autonomous execution — it must be thorough enough for the user to verify understanding.

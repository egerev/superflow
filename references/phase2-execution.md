# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.
Each sprint runs in a fresh isolated session (`claude -p` or Agent with `isolation: "worktree"`) for full context — zero drift.

## Per-Sprint Flow

1. **Re-read** this file (`references/phase2-execution.md`)
2. **Worktree**: `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`
3. **Baseline tests** in worktree
4. **Dispatch implementers** via Agent tool (`mode: bypassPermissions`, `model: sonnet` for mechanical tasks). Use `prompts/implementer.md`.
   - **Parallelize** when tasks are independent (different files, no shared state, no dependencies)
   - **Sequentialize** when tasks share files, state, or depend on each other's output
5. **Review chain**: spec reviewer (background) > code quality reviewer (background) > verify tests
6. **Full test suite** with pasted output
7. **PAR** (see `~/.claude/rules/superflow-enforcement.md` for algorithm): Claude reviewer + secondary provider, both receive SPEC. Write `.par-evidence.json` after ACCEPTED.
8. **Push + PR**: verify `.par-evidence.json` exists. `gh pr create --base main`
9. **Cleanup**: `git worktree remove .worktrees/sprint-N`
10. **Telegram update** (if MCP connected), then next sprint

## Review Optimization
- Simple (1-2 files, <50 lines): spec review only
- Medium (2-5 files): spec + Claude code quality
- Complex (5+ files): full cycle (spec + dual-model + product)

## No Secondary Provider
Dispatch two Claude agents with split focus:
- Agent A (Technical): security, architecture, performance, correctness
- Agent B (Product): spec compliance, UX gaps, edge cases, data integrity
Record: `{"provider":"split-focus",...}`

## Debugging
1. Read failure output, identify failing assertion
2. Form hypothesis before touching code
3. Targeted fix, verify with specific test then full suite
4. 3+ failed attempts on same issue = likely architectural problem. Report BLOCKED with evidence, suggest rethinking approach

## Handling NEEDS_FIXES from PAR
- Verify each finding against the codebase before implementing (reviewer may lack context)
- Push back with technical reasoning if finding is incorrect
- Fix confirmed issues one at a time, test each
- Re-run PAR after fixes

## Failure Handling
- Test/build failure: investigate root cause first (read errors, check recent changes, trace data flow). No guessing.
- 3+ failed fix attempts on same issue: likely architectural problem — report BLOCKED, suggest rethinking approach
- Agent blocked: re-dispatch with more context. 2 fails = implement manually
- Never stop to ask the user. Accumulate issues, report at end.

## Documentation Update (after last sprint's PR)
1. Update CLAUDE.md with new modules/files
2. Update BACKLOG.md with completed and discovered items
3. Commit documentation to the last sprint's branch

## Completion Report
PRs created (with numbers), verification evidence (test counts, PAR status), known issues, merge order.

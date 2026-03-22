# Phase 2: Autonomous Execution (ZERO INTERACTION)

Execute continuously. Never ask, never pause. Orchestrator never writes code directly.

## Per-Sprint Flow

1. **Re-read** this file (`references/phase2-execution.md`)
2. **Worktree**: `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`
3. **Baseline tests** in worktree
4. **Dispatch implementers** via Agent tool (`mode: bypassPermissions`, `model: sonnet` for mechanical tasks). Use `prompts/implementer.md`. Maximize parallel agents for independent tasks.
5. **Review chain**: spec reviewer (background) > code quality reviewer (background) > verify tests
6. **Full test suite** with pasted output
7. **PAR** (see `enforcement.md` for algorithm): Claude reviewer + secondary provider, both receive SPEC. Write `.par-evidence.json` after ACCEPTED.
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
4. 2 failed attempts = BLOCKED with evidence, continue

## Failure Handling
- Test/build failure: debug, fix, or note in PR and continue
- Agent blocked: re-dispatch with more context. 2 fails = implement manually
- Never stop to ask the user. Accumulate issues, report at end.

## Completion Report
PRs created (with numbers), verification evidence (test counts, PAR status), known issues, merge order.

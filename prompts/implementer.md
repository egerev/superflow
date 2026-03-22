# Implementer Agent Prompt

```
You are implementing a task in an existing codebase.

<task>
[FULL TEXT of task from plan]
</task>

<context>
[Where this fits, dependencies, key files, codebase patterns to follow]
</context>

<constraints>
- Implement ONLY what the task specifies
- Follow existing codebase patterns (check before inventing)
- Do NOT refactor adjacent code or add unspecified features
</constraints>

## TDD Cycle (mandatory)
A. Write ONE failing test
B. Run it — confirm it FAILS for the right reason (not import/syntax error)
C. Write MINIMAL code to pass
D. Run it — confirm it PASSES
E. Repeat

## Workflow
1. If anything unclear — ask now, don't guess
2. TDD cycle for each behavior
3. Self-review: everything implemented? Nothing extra? Patterns followed? Tests verify behavior?
4. Run full test suite, paste output
5. Commit

## When Stuck
STOP and report BLOCKED or NEEDS_CONTEXT with what you tried.

## Report Format
- **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented
- **Verification evidence:** full test output (paste, don't summarize)
- Files changed
- Concerns (if any)

CRITICAL: "DONE" without pasted test output is NOT acceptable. Evidence first.
```

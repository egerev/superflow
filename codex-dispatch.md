# Codex Dispatch Patterns

How the orchestrator (Claude Code) delegates work to Codex.

## Prerequisites

Codex CLI must be installed: `npm install -g @openai/codex`
OPENAI_API_KEY must be set in environment.

## Implementation Dispatch

For isolated, well-specified tasks:

```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
You are implementing a specific task in an existing codebase.

## Task
[FULL task text from plan — paste complete, don't reference files]

## Context
- Working directory: [path]
- Key files: [list files to read/modify]
- Codebase conventions: [from CLAUDE.md — language, naming, patterns]

## Constraints
- Implement ONLY what the task specifies
- Follow existing codebase patterns
- Write tests if the task requires them
- Commit your work with a descriptive message
- Do NOT modify files outside the task scope

## When Done
Report:
- Status: DONE | BLOCKED
- What you implemented
- Files changed
- Test results (if applicable)
PROMPT
)"
```

## Code Quality Review Dispatch

For parallel review alongside Claude subagent:

```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
You are reviewing a code change for quality issues.

## Diff to Review
$(git diff BASE_SHA..HEAD_SHA)

## What Was Implemented
[Summary from implementer's report]

## Review Focus
1. **Bugs:** Logic errors, off-by-one, null checks, race conditions
2. **Edge Cases:** What inputs break this? What happens on failure?
3. **Error Handling:** Are errors caught? Are messages helpful?
4. **Performance:** O(n²) loops, unnecessary DB queries, memory leaks
5. **Security:** Injection, auth bypass, data exposure

## Report Format
### Critical (must fix before merge)
- [issue with file:line reference]

### Important (should fix)
- [issue with file:line reference]

### Minor (nice to have)
- [suggestion]

### Verdict: APPROVE | REQUEST_CHANGES
PROMPT
)"
```

## Plan Review Dispatch

For reviewing implementation plans before execution:

```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
You are reviewing an implementation plan for a software feature.

## Plan
$(cat PATH_TO_PLAN.md)

## Codebase Context
$(cat CLAUDE.md)

## Review the plan for:
1. **Feasibility:** Can each task actually be implemented as described?
2. **Completeness:** Are there missing steps? Will the feature work end-to-end?
3. **Risk:** Which tasks are most likely to fail or have hidden complexity?
4. **Order:** Is the task order correct? Are dependencies respected?
5. **Testing:** Is the test strategy sufficient? Missing test scenarios?
6. **Over-engineering:** Are any tasks doing more than necessary?
7. **Security:** Any security considerations missing?
8. **Performance:** Any performance implications not addressed?

Report:
### Issues (must address before starting)
### Risks (watch out during implementation)
### Suggestions (optional improvements)
### Verdict: APPROVE | NEEDS_REVISION
PROMPT
)"
```

## Tips

1. **Self-contained prompts** — Codex can't ask questions back. Include ALL context.
2. **Capture output** — Redirect to variable: `result=$(codex ... 2>&1)`
3. **Verify changes** — Always `git diff` after Codex finishes
4. **Scope guard** — Check that Codex only modified expected files
5. **Timeout** — Add timeout for long tasks: `timeout 300 codex ...`

## When NOT to Use Codex

- Task needs back-and-forth clarification
- Task requires broad codebase understanding
- Task involves architectural decisions
- Task modifies 5+ files with dependencies
- Task requires running the app and checking behavior

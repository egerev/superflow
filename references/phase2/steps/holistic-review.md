# Step: holistic-review

**Stage:** review (post-all-sprints, before Completion Report)
**Loaded by orchestrator:** after all sprint PRs created, when holistic review is required
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Conditional Trigger

Evaluate `decision_matrix.holistic_required` from `workflow.json`:
```
governance_mode == 'critical' OR sprint_count >= 4 OR max_parallel > 1
```

If **none** of these apply (≤3 linear sequential sprints, light or standard mode), skip holistic
review entirely and proceed directly to Completion Report.

## When Holistic IS Required

Both agents review ALL code across ALL sprints as a unified system. Reasoning: **Deep tier**.
Same principle: Claude = Product lens, secondary = Technical lens.

**With Codex available:**
```
a. Agent(subagent_type: "deep-product-reviewer", run_in_background: true,
         prompt: "Review ALL sprint changes. Focus: end-to-end user flows, data integrity
                  across sprints, spec compliance.")
b. $TIMEOUT_CMD 900 codex exec review -c model_reasoning_effort=high --ephemeral \
     "Review all changes across all sprints for cross-module issues, architecture, security." 2>&1
```

**Without Codex (split-focus fallback):**
```
a. Agent(subagent_type: "deep-product-reviewer", run_in_background: true, ...)
b. Agent(subagent_type: "deep-code-reviewer", run_in_background: true, ...)
```

## Mandatory Cross-Sprint Hygiene Checks

Both reviewers MUST explicitly check these three issues across ALL combined sprint changes:

1. **Code duplication across sprints** — different sprints may have independently implemented
   similar logic. Search for similar function names, shared patterns, repeated validation or
   transformation code across sprint boundaries.

2. **Type redefinition across sprints** — later sprints may redefine types that earlier sprints
   already created or that exist in auto-generated files. Check for `as unknown as`, `as any` casts
   bridging between sprint-local types.

3. **Dead code from incremental refactoring** — when sprint N refactors sprint N-1 code, old code
   paths may remain. Trace call chains for functions/components that lost all callers across the
   combined diff.

These issues are invisible in per-sprint review but compound over time. Flag as **HIGH severity**.

## Fix Threshold

Fix CRITICAL and HIGH issues before Completion Report. Medium/Low: document in Known Limitations.

# Phase 2: Autonomous Execution — Codex Dispatch Overlay

> For workflow logic (stage structure, sprint checklist, PAR evidence, test discipline, failure handling), read the main file: `references/phase2-execution.md`.

## Critical Codex Differences

1. **Flat dispatch only.** max_depth=1 — orchestrator dispatches ALL agents directly. No sprint-level delegation.
2. **Sequential sprints.** No wave-based parallel sprint execution. Sprint 1 → Sprint 2 → Sprint 3.
3. **Context budget:** ~258K. Use `/compact` between sprints. For 4+ sprints, consider session-per-sprint.
4. **No TaskCreate/TaskUpdate.** Use printf for progress tracking.

## Per-Sprint Dispatch Patterns

### Stage 1: Setup
Same as main doc (re-read phase docs, Telegram, worktree, baseline tests). No dispatch changes.

### Stage 2: Implementation

**Task-level parallelism within a sprint:**

For each task in the sprint plan:
- Analyze file dependencies (same as main doc wave analysis)
- Independent tasks: dispatch via spawn_agent in parallel (up to 6)
- Dependent tasks: dispatch sequentially

Use spawn_agent to dispatch implementer with appropriate tier:
- Simple tasks: spawn_agent("fast-implementer") with task prompt
- Medium tasks: spawn_agent("standard-implementer") with task prompt
- Complex tasks: spawn_agent("deep-implementer") with task prompt

Include in every implementer prompt:
- Full task text from plan (verbatim)
- Charter non-negotiables
- llms.txt content (if exists)
- Codebase context (key files, patterns)

### Stage 3: Unified Review (dual-model)

Check Claude availability: `claude --version 2>/dev/null`

**If Claude available:**
1. Claude Opus 4.7 product reviewer:
   ```bash
   $TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "Review the following sprint for product fit, user scenarios, data integrity, and charter compliance. $(cat prompts/claude/product-reviewer.md)

   SPEC: [spec text]
   PRODUCT BRIEF: [brief text]
   DIFF: $(git diff main...HEAD)" 2>&1
   ```
2. Codex technical reviewer: spawn_agent("standard-code-reviewer") with prompt containing SPEC + brief + diff

**If Claude NOT available (split-focus):**
1. spawn_agent("standard-product-reviewer") — spec fit, user scenarios, data integrity
2. spawn_agent("standard-code-reviewer") — correctness, security, architecture
Record `"provider": "split-focus"` in .par-evidence.json.

Wait for both. Fix confirmed issues. Re-run only the flagging agent.

### Stage 4: PAR Evidence

Same format as main doc:
```json
{
  "sprint": N,
  "claude_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "docs_update": "UPDATED|UNCHANGED",
  "docs_review": "PASS",
  "provider": "claude-opus-4-7|split-focus",
  "ts": "ISO-8601"
}
```

### Stage 5: Documentation Update + Review

Use spawn_agent to dispatch "standard-doc-writer" with prompt:
```
Audit and update project documentation for Sprint N before PR creation.
[Same prompt body as main doc Stage 5 section]
```

Then dispatch a second review-only "standard-doc-writer":
```
Review Sprint N documentation changes before PR creation. Do not edit files.
Verify llms.txt was explicitly audited, CLAUDE.md/llms.txt match the sprint diff, and no stale paths or commands were introduced.
Return docs_review: PASS or docs_review: NEEDS_FIXES.
```

Fix any NEEDS_FIXES and re-run the doc review. Before shipping, `.par-evidence.json` must include `docs_update` (`UPDATED` or `UNCHANGED`) and `docs_review` (`PASS`).

### Stage 6: Ship

Same as main doc (push, PR, cleanup, Telegram). PR creation is blocked until docs update and docs review gates pass.

## Holistic Review (after all sprints, conditional)

**Required when:** ≥4 sprints, or governance_mode="critical".
Note: parallel execution trigger doesn't apply — Codex runs sprints sequentially.

1. Claude Opus 4.7 product reviewer:
   ```bash
   $TIMEOUT_CMD 900 claude --model claude-opus-4-7 --effort xhigh -p "Holistic product review of all sprint changes. Focus: end-to-end user flows, data integrity across sprints, spec compliance, and charter compliance. $(cat prompts/claude/product-reviewer.md)" 2>&1
   ```

2. Codex technical: spawn_agent("deep-code-reviewer") with:
   "Holistic review of all sprint changes. Check cross-module issues, architecture, security, performance, tests, and codebase hygiene."

No Claude → split-focus: spawn_agent("deep-product-reviewer") + spawn_agent("deep-code-reviewer").

Cross-sprint codebase hygiene checks are mandatory (same as main doc):
1. Code duplication across sprints
2. Type redefinition across sprints
3. Dead code from incremental refactoring

## Compaction Recovery (Codex-specific)

When context feels thin or after `/compact`:
1. Re-read `codex/AGENTS.md` (durable rules)
2. Re-read `.superflow-state.json` for current sprint/stage
3. Check for Stop hook dump: `ls -t .superflow/compact-log/ 2>/dev/null | head -1`
   - If dump exists, read it for pre-compaction context
4. Re-read the current sprint section from the plan
5. Re-read the charter

No PreCompact hook exists in Codex — rely on Stop hook dumps + SessionStart re-injection.

## Completion Report

Same format as main doc (product release format, not sprint log). No changes needed.

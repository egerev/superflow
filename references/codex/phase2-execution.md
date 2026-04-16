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
1. Codex product reviewer: spawn_agent("standard-product-reviewer") with prompt containing SPEC + brief + diff
2. Claude technical reviewer:
   ```bash
   $TIMEOUT_CMD 600 claude -p "Review the following diff for correctness, security, performance. $(cat prompts/claude/code-reviewer.md)

   SPEC: [spec text]
   DIFF: $(git diff main...HEAD)" 2>&1
   ```

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
  "codex_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "provider": "claude|split-focus",
  "ts": "ISO-8601"
}
```

### Stage 5: Documentation Update

Use spawn_agent to dispatch "standard-doc-writer" with prompt:
```
Update project documentation to reflect changes from Sprint N.
[Same prompt body as main doc Stage 5 section]
```

### Stage 6: Ship

Same as main doc (push, PR, cleanup, Telegram). No dispatch changes.

## Holistic Review (after all sprints, conditional)

**Required when:** ≥4 sprints, or governance_mode="critical".
Note: parallel execution trigger doesn't apply — Codex runs sprints sequentially.

1. Codex product: spawn_agent("deep-product-reviewer") with:
   "Review ALL sprint changes. Focus: end-to-end user flows, data integrity across sprints, spec compliance."

2. Claude technical:
   ```bash
   $TIMEOUT_CMD 900 claude -p "Holistic review of all sprint changes. Check cross-module issues, architecture, security. $(cat prompts/claude/code-reviewer.md)" 2>&1
   ```

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

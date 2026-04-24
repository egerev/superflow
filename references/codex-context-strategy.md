# Codex Context Management Strategy

Codex CLI has ~258K token context (vs Claude's ~1M). This guide covers how to manage the budget across Superflow phases.

## Context Budget Per Phase

| Phase | Estimated Usage | Fits in 258K? | Strategy |
|-------|----------------|---------------|----------|
| Phase 0 | ~80-120K | Yes | No special handling |
| Phase 1 | ~100-180K | Yes | `/compact` before Step 9 if expert panel output is large |
| Phase 2 (per sprint or wave) | ~140-190K per active supervisor | Yes | `/compact` between sequential sprints or completed sprint waves |
| Phase 3 | ~50-80K | Yes | No special handling |

## Phase 2 Budget Breakdown (per sprint)

| Component | Tokens | Notes |
|-----------|--------|-------|
| AGENTS.md (durable rules) | ~2K | Re-read after compaction |
| .superflow-state.json | ~1K | Always small |
| Charter | ~2K | Injected into every sprint |
| Sprint plan section | ~2-4K | Only current sprint |
| Phase 2 overlay doc | ~5K | Dispatch patterns |
| Subagent round-trips | ~100-150K | Discarded after return |
| Review output | ~10-20K | Summarize to <5K before storing |
| Accumulated history | ~20-40K | Grows across stages |
| **Total** | **~140-190K** | Within 258K |

## Strategies

### 1. `/compact` Between Sprints or Waves

After each sequential sprint's PR/checkpoint is created, run `/compact` before starting the next sprint. When `context.git_workflow_mode` enables sprint-level parallelism, run `/compact` after the entire wave completes and the parent orchestrator has recorded the wave summary.

**After `/compact`, always:**
1. Re-read `codex/AGENTS.md`
2. Re-read `.superflow-state.json`
3. Re-read latest `.superflow/compact-log/` dump (if exists)

### 2. Session-Per-Wave (for 4+ sprints)

For long runs (4+ sprints), use one Codex session per sprint or per wave:
1. Complete sprint N or wave K, create PRs/checkpoints
2. Update `.superflow-state.json` to the next sprint/wave
3. `/clear` then `$superflow`
4. Superflow detects phase=2 and resumes automatically

### 3. Subagent Context Isolation

Subagent contexts are discarded after they return. This is the primary mechanism for staying within budget:
- Implementation code reading → subagent (context discarded)
- Review diffs → subagent (context discarded)
- Codebase exploration → subagent (context discarded)

The orchestrator only keeps summaries, not raw content.

### 4. Auto-Compact Configuration

Recommended setting in `~/.codex/config.toml`:
```toml
[agents]
max_threads = 6
max_depth = 2

model_auto_compact_token_limit = 200000
```

`max_depth=2` enables sprint supervisors to spawn per-sprint implement/review/doc agents. The auto-compact limit triggers automatic compaction at ~200K tokens, leaving ~58K headroom for the current operation to complete.

### 5. Review Output Compression

After receiving review results, compress to essentials before proceeding:
- Keep: verdict, critical/high findings with file:line, fix suggestions
- Discard: minor findings, strengths section, verbose explanations
- Target: <5K tokens per review result stored in orchestrator context

## Warning Signs

- Context feels "thin" (model seems to have forgotten earlier decisions) → compaction happened silently. Re-read durable files.
- `/compact` takes unusually long → context was very large. Consider session-per-wave.
- Sprint 4+ and feeling slow → auto-compact firing frequently. Switch to session-per-wave.

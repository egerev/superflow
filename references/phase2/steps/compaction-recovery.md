# Step: compaction-recovery

**Stage:** setup (triggered after PostCompact hook fires)
**Loaded by orchestrator:** immediately after context compaction is detected
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Why This Matters

Phase 2 runs for hours — compaction fires at least once on any non-trivial run. The `PostCompact`
hook re-injects enforcement rules, but in-progress sprint details, recent review output, and the
current task queue can still be summarized away during compaction itself. Resuming without hydration
risks repeating a step that already ran or skipping one that didn't finish.

## Hydration Protocol

After compaction fires, execute in order:

1. **Re-read enforcement rules:**
   `~/.claude/rules/superflow-enforcement.md` — only if NOT already visible in current transcript.

2. **Re-read current state:**
   `.superflow-state.json` — sprint number, stage, stage_index, charter_file path.

3. **Check compact log:**
   ```bash
   ls -t .superflow/compact-log/ 2>/dev/null | head -1
   ```
   If a dump exists, Read it. This is the PreCompact snapshot from
   `hooks/precompact-state-externalization.sh` — contains pre-compaction state, last 40 transcript
   entries, and active sprint context the summarizer may have dropped.

4. **Only after hydrating:** resume work from the current `stage` / `stage_index` in state.

## Skip Files Already in Context

If a file appears in the current (post-compaction) transcript, do NOT re-read it. Check before
each Read. "In context" = content is visible in this conversation, not just "was read earlier."

## If compact-log Doesn't Exist

The PreCompact hook isn't installed. Continue without the dump. Note it for the next onboarding
cycle. Rely on `.superflow-state.json` alone to determine current position.

## Heartbeat Check (post-compaction)

After hydrating from state, check `heartbeat.must_reread` for any additional files the
orchestrator declared it needs after compaction. Read each missing file. Skip non-existent paths.

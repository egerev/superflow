# SuperFlow Hooks

Reference scripts for Claude Code hooks that improve SuperFlow's behavior on
long-running autonomous sessions. These files are **not** installed automatically
— the Phase 0 anti-regression check (`references/anti-regression-check.md`)
detects missing hooks and offers to install them with user consent.

## `precompact-state-externalization.sh`

**Event:** `PreCompact` (runs immediately before context compaction).

**What it does:**

1. Reads the hook payload (JSON on stdin; env-var fallback for older Claude Code).
2. Dumps the current `.superflow-state.json` (if present) and the last 40
   transcript entries to `<project>/.superflow/compact-log/precompact-<ts>.md`
   (or `~/.superflow/compact-log/` outside of a SuperFlow project).
3. Emits `hookSpecificOutput.additionalContext` pointing the model at the dump
   path so it can hydrate after compaction via the `Read` tool.

**Why:** compaction is lossy by definition. A pre-compact snapshot lets the
orchestrator restore recent sprint state, in-progress work, and the most
recent subagent results that would otherwise be summarized away. See the
"Compaction recovery" section in `references/phase2-execution.md`.

## Manual installation

Add to `~/.claude/settings.json` under `hooks.PreCompact`:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/skills/superflow/hooks/precompact-state-externalization.sh"
          }
        ]
      }
    ]
  }
}
```

Preserve any existing `PreCompact` entries — append this one to the array.

## Design notes

- **Idempotent and non-destructive.** The hook only appends new files; it never
  overwrites or deletes existing dumps.
- **Gitignored by default.** `.superflow/` is in SuperFlow's recommended
  `.gitignore`, so dumps never leak into commits.
- **Fail-safe.** If transcript lookup fails, the dump still contains the state
  file and a header; the hook never blocks compaction.
- **Path discovery.** The hook prefers the `transcript_path` from the PreCompact
  payload (Claude Code 2.x); it falls back to a glob under
  `~/.claude/projects/<encoded-cwd>/<session_id>.jsonl` for older versions.

Reference implementation: [mvara-ai/precompact-hook](https://github.com/mvara-ai/precompact-hook).

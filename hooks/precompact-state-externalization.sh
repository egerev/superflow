#!/usr/bin/env bash
# SuperFlow PreCompact hook.
# Runs immediately before context compaction, dumps recent transcript + state
# to disk so PostCompact / the orchestrator can hydrate from the dump afterwards.
# Output: hookSpecificOutput.additionalContext pointing the model at the dump path.

set -e

# Claude Code sends hook payload as JSON on stdin; env vars are a fallback
# for older versions or manual invocation.
INPUT=""
if [ ! -t 0 ]; then
  INPUT="$(cat 2>/dev/null || true)"
fi

SESSION_ID=""
CWD=""
TRANSCRIPT_FILE=""
if command -v jq >/dev/null 2>&1 && [ -n "$INPUT" ] && printf '%s' "$INPUT" | jq -e . >/dev/null 2>&1; then
  SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty')"
  CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // empty')"
  TRANSCRIPT_FILE="$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty')"
fi
SESSION_ID="${SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-unknown}}"
CWD="${CWD:-${CLAUDE_PROJECT_DIR:-${CLAUDE_CODE_CWD:-$PWD}}}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Project-local dump for SuperFlow runs; home fallback otherwise.
if [ -f "$CWD/.superflow-state.json" ]; then
  DUMP_DIR="$CWD/.superflow/compact-log"
else
  DUMP_DIR="$HOME/.superflow/compact-log"
fi
mkdir -p "$DUMP_DIR"

DUMP_FILE="$DUMP_DIR/precompact-${TS}.md"

{
  echo "# Pre-Compact State Dump"
  echo ""
  echo "- Session: ${SESSION_ID}"
  echo "- CWD: ${CWD}"
  echo "- Timestamp: ${TS}"
  echo ""
  if [ -f "$CWD/.superflow-state.json" ]; then
    echo "## SuperFlow state at compact time"
    echo ""
    echo '```json'
    cat "$CWD/.superflow-state.json"
    echo '```'
    echo ""
    if command -v jq >/dev/null 2>&1 && jq -e '.heartbeat' "$CWD/.superflow-state.json" >/dev/null 2>&1; then
      echo "## Heartbeat (at compaction time)"
      echo ""
      echo '```json'
      jq '.heartbeat' "$CWD/.superflow-state.json"
      echo '```'
      echo ""
    fi
  fi
  # Transcript tail: prefer explicit path from hook payload; fall back to the
  # Claude Code encoded project dir. Encoding maps both `/` and `.` to `-`,
  # with the leading dash preserved (e.g. `/Users/x/.claude/y` becomes
  # `-Users-x--claude-y`). Verified against `~/.claude/projects/`.
  if [ -z "$TRANSCRIPT_FILE" ] || [ ! -r "$TRANSCRIPT_FILE" ]; then
    TRANSCRIPT_DIR="$HOME/.claude/projects"
    ENCODED_CWD="$(printf '%s' "$CWD" | sed 's|/|-|g; s|\.|-|g')"
    TRANSCRIPT_FILE="$(ls -t "$TRANSCRIPT_DIR/$ENCODED_CWD/$SESSION_ID".jsonl 2>/dev/null | head -1 || true)"
  fi
  if [ -n "$TRANSCRIPT_FILE" ] && [ -r "$TRANSCRIPT_FILE" ]; then
    echo "## Recent transcript (last 40 entries from $TRANSCRIPT_FILE)"
    echo ""
    echo '```jsonl'
    tail -40 "$TRANSCRIPT_FILE"
    echo '```'
  fi
} > "$DUMP_FILE"

# Emit hookSpecificOutput so the orchestrator can find the dump after compaction.
if command -v jq >/dev/null 2>&1; then
  jq -n --arg path "$DUMP_FILE" '{
    hookSpecificOutput: {
      hookEventName: "PreCompact",
      additionalContext: ("Pre-compact state dump saved to: " + $path + ". After compaction, read this file with the Read tool to restore recent sprint context, current state, and in-progress work.")
    }
  }'
else
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "Pre-compact state dump saved to: ${DUMP_FILE}. After compaction, read this file with the Read tool to restore recent sprint context, current state, and in-progress work."
  }
}
EOF
fi

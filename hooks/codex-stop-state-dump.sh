#!/usr/bin/env bash
# Superflow Codex Stop hook.
# Runs when a Codex session stops; dumps current state + recent transcript
# to disk so the next session can hydrate from the dump.
# Output: none (Codex Stop hook ignores output).

set -e

# Codex sends hook payload as JSON on stdin; env vars are a fallback
# for older versions or manual invocation.
INPUT=""
if [ ! -t 0 ]; then
  INPUT="$(cat 2>/dev/null || true)"
fi

SESSION_ID=""
CWD=""
if command -v jq >/dev/null 2>&1 && [ -n "$INPUT" ] && printf '%s' "$INPUT" | jq -e . >/dev/null 2>&1; then
  SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty')"
  CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // empty')"
fi
# Fallback: check Codex-style env vars, then Claude-style, then PWD
SESSION_ID="${SESSION_ID:-${CODEX_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-unknown}}}"
CWD="${CWD:-${CODEX_CWD:-${CLAUDE_PROJECT_DIR:-${CLAUDE_CODE_CWD:-$PWD}}}}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Only dump when inside a Superflow project; skip otherwise.
if [ ! -f "$CWD/.superflow-state.json" ]; then
  exit 0
fi

DUMP_DIR="$CWD/.superflow/compact-log"
mkdir -p "$DUMP_DIR"

DUMP_FILE="$DUMP_DIR/stop-${TS}.md"

{
  echo "# Codex Stop State Dump"
  echo ""
  echo "- Session: ${SESSION_ID}"
  echo "- CWD: ${CWD}"
  echo "- Timestamp: ${TS}"
  echo ""
  echo "## Superflow state at stop time"
  echo ""
  echo '```json'
  cat "$CWD/.superflow-state.json"
  echo '```'
  echo ""
  # Codex transcript: look in ~/.codex/sessions/ using the session ID.
  CODEX_SESSION_DIR="$HOME/.codex/sessions"
  TRANSCRIPT_FILE=""
  if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "unknown" ] && [ -d "$CODEX_SESSION_DIR" ]; then
    TRANSCRIPT_FILE="$(ls -t "$CODEX_SESSION_DIR/${SESSION_ID}"* 2>/dev/null | head -1 || true)"
  fi
  if [ -n "$TRANSCRIPT_FILE" ] && [ -r "$TRANSCRIPT_FILE" ]; then
    echo "## Recent Codex transcript (last 40 lines from $TRANSCRIPT_FILE)"
    echo ""
    echo '```'
    tail -40 "$TRANSCRIPT_FILE"
    echo '```'
  fi
} > "$DUMP_FILE"

# Stop hook ignores output — exit silently.
exit 0

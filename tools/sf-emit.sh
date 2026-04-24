# sf-emit.sh — Superflow event emission library
# Source-safe: shell options are scoped to sf_emit() only; sourcing this file does not alter caller shell state.
# Log rotation: threshold-based, triggered every _SF_ROTATION_CHECK_INTERVAL calls inside sf_emit.
#
# Usage:
#   source tools/sf-emit.sh        # once per session
#   sf_emit <type> [key=value ...]  # emit an event
#
# Key/value typed syntax:
#   key=value        → always string (--arg)
#   key:int=123      → integer (--argjson)
#   key:bool=true    → boolean (--argjson)
#   key:json={"a":1} → raw JSON (--argjson)
# Key names must match ^[a-zA-Z_][a-zA-Z0-9_]*$
#
# Examples:
#   sf_emit run.start runtime=claude phase:int=2
#   sf_emit agent.dispatch agent_type=implementer task="Sprint 1" model=sonnet
#   sf_emit sprint.end sprint:int=1 total_sprints:int=3 goal="Event log contract" complexity=medium
#
# SUPERFLOW_RUN_ID must be set before calling sf_emit (UUID string).
# Output file: ${SUPERFLOW_EVENTS_FILE:-.superflow/events.jsonl} (one JSON line per event).
#
# Supported event types (must match templates/event-schema.json):
#   run.start, run.end,
#   phase.start, phase.end,
#   stage.start, stage.end,
#   sprint.start, sprint.end,
#   agent.dispatch, agent.complete, agent.fail,
#   review.start, review.verdict,
#   test.run, test.result,
#   pr.create, pr.merge,
#   compact.pre, compact.post,
#   heartbeat

# Allowlist of known event types — must stay in sync with templates/event-schema.json
_SF_KNOWN_TYPES=(
  run.start
  run.end
  phase.start
  phase.end
  stage.start
  stage.end
  sprint.start
  sprint.end
  agent.dispatch
  agent.complete
  agent.fail
  review.start
  review.verdict
  test.run
  test.result
  pr.create
  pr.merge
  compact.pre
  compact.post
  heartbeat
)

# ---------------------------------------------------------------------------
# Log rotation configuration
# ---------------------------------------------------------------------------
# Maximum number of lines in events.jsonl before rotation triggers.
# Default 5000. Set to 0 or negative to disable rotation entirely.
: "${SUPERFLOW_EVENT_LOG_MAX_LINES:=5000}"

# How often (in sf_emit calls) to check the line count.
# 1 = check every call (useful for testing); 100 = production default.
: "${_SF_ROTATION_CHECK_INTERVAL:=100}"

# Per-shell call counter — not exported, not shared across processes.
_SF_EMIT_CALL_COUNT=0

# _sf_rotate_log <out_file>
# Rotates out_file to archive/events-<YYYYMMDD-HHMMSS>-<PID>-<N>.jsonl.
# Uses flock(1) non-blocking advisory lock to prevent concurrent rotation.
# If flock is unavailable, falls back to a best-effort mv (safe because
# POSIX append is atomic up to PIPE_BUF; two shells rotating simultaneously
# is harmless — the later one will see a file below threshold and skip).
_sf_rotate_log() {
  local out_file="$1"
  local archive_dir
  archive_dir="$(dirname "$out_file")/archive"
  local stamp
  stamp="$(date -u +%Y%m%d-%H%M%S)"
  # Base name: timestamp + PID for human readability
  local archive_base="events-${stamp}-${$}"
  local archive_file="${archive_dir}/${archive_base}.jsonl"
  # Collision-proof: if file already exists (same second, same PID), append -N suffix
  local _n=0
  while [ -e "$archive_file" ]; do
    _n=$((_n + 1))
    archive_file="${archive_dir}/${archive_base}-${_n}.jsonl"
  done

  # Ensure archive directory exists
  mkdir -p "$archive_dir" || {
    echo "sf_emit: log rotation failed: cannot create archive dir '$archive_dir'" >&2
    return 0  # non-fatal
  }

  # Acquire non-blocking advisory lock to prevent concurrent rotation.
  # Pattern: redirect fd 9 to lock file, flock -n on it. If flock is not
  # available or lock is held, skip rotation (another shell is handling it).
  local lock_file="${out_file}.lock"

  _sf_do_rotate() {
    mv "$out_file" "$archive_file" || {
      echo "sf_emit: log rotation failed: mv '$out_file' → '$archive_file'" >&2
      return 0  # non-fatal; do not block emissions
    }
    # out_file is now absent; next sf_emit will re-create it via mkdir+printf
  }

  # Try flock (Linux, macOS with /usr/bin/flock or Homebrew)
  if command -v flock &>/dev/null; then
    (
      exec 9>"$lock_file"
      if flock -n 9; then
        _sf_do_rotate
      fi
      # lock released on subshell exit
    )
  else
    # No flock available: best-effort (rotation may race, but append is safe)
    _sf_do_rotate
  fi
}

# _sf_check_rotation <out_file>
# Called after append. Checks line count and triggers _sf_rotate_log if needed.
_sf_check_rotation() {
  local out_file="$1"

  # Rotation disabled when threshold is 0 or negative
  if [ "${SUPERFLOW_EVENT_LOG_MAX_LINES:-5000}" -le 0 ] 2>/dev/null; then
    return 0
  fi

  local line_count
  line_count="$(wc -l < "$out_file" 2>/dev/null)" || return 0

  if [ "$line_count" -ge "${SUPERFLOW_EVENT_LOG_MAX_LINES}" ]; then
    _sf_rotate_log "$out_file"
  fi
}

# ---------------------------------------------------------------------------

# _sf_uuid — emit a UUID using platform-appropriate method
_sf_uuid() {
  if command -v uuidgen &>/dev/null; then
    uuidgen | tr '[:upper:]' '[:lower:]'
  elif [ -r /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid
  else
    echo "sf_emit: cannot generate UUID — uuidgen not found and /proc/sys/kernel/random/uuid not readable" >&2
    return 1
  fi
}

# sf_emit <type> [key=value ...]
# Constructs a JSON event object and appends it to the events file.
# All JSON construction done via jq -cn (compact, null-input) with --arg/--argjson — no shell interpolation.
sf_emit() {
  local type="${1:-}"
  if [ -z "$type" ]; then
    echo "sf_emit: event type is required" >&2
    return 1
  fi
  shift

  # Validate SUPERFLOW_RUN_ID is set
  if [ -z "${SUPERFLOW_RUN_ID:-}" ]; then
    echo "sf_emit: SUPERFLOW_RUN_ID is not set. Set it before sourcing: export SUPERFLOW_RUN_ID=\"\$(uuidgen)\"" >&2
    echo "  Hint: in SKILL.md startup, run: export SUPERFLOW_RUN_ID=\"\$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)\"" >&2
    return 1
  fi

  # Validate type against allowlist
  local known=0
  local t
  for t in "${_SF_KNOWN_TYPES[@]}"; do
    if [ "$t" = "$type" ]; then
      known=1
      break
    fi
  done
  if [ "$known" -eq 0 ]; then
    echo "sf_emit: unknown type '$type'" >&2
    return 1
  fi

  # Parse key=value pairs into a jq-compatible data object.
  # Typed syntax: key=value (string), key:int=N (integer), key:bool=true/false, key:json={...}
  # Key names must match ^[a-zA-Z_][a-zA-Z0-9_]*$ — anything else is rejected with an error.
  # Use a counter to generate unique, sequential jq variable names (sfv0, sfv1, ...).
  local jq_data_filter="{}"
  local -a jq_args=()
  local pair key_typed key type_hint val
  local _sf_counter=0

  for pair in "$@"; do
    # Split on first '=' only
    key_typed="${pair%%=*}"
    val="${pair#*=}"

    if [ -z "$key_typed" ] || [ "$key_typed" = "$pair" ]; then
      echo "sf_emit: malformed argument '$pair' (expected key=value or key:type=value)" >&2
      return 1
    fi

    # Parse optional type hint from key_typed (e.g. "phase:int" → key=phase, type_hint=int)
    if [[ "$key_typed" == *:* ]]; then
      key="${key_typed%%:*}"
      type_hint="${key_typed#*:}"
    else
      key="$key_typed"
      type_hint="string"
    fi

    # Validate key name format: must match ^[a-zA-Z_][a-zA-Z0-9_]*$
    if ! [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
      echo "sf_emit: invalid key '$key' — keys must match ^[a-zA-Z_][a-zA-Z0-9_]*\$" >&2
      return 1
    fi

    local varname="sfv${_sf_counter}"
    _sf_counter=$(( _sf_counter + 1 ))

    case "$type_hint" in
      int|integer)
        # Integer value — use --argjson so jq treats it as a number
        jq_args+=("--argjson" "$varname" "$val")
        ;;
      bool|boolean)
        # Boolean value — use --argjson
        jq_args+=("--argjson" "$varname" "$val")
        ;;
      json)
        # Raw JSON — use --argjson
        jq_args+=("--argjson" "$varname" "$val")
        ;;
      string|*)
        # String (default) — use --arg
        jq_args+=("--arg" "$varname" "$val")
        ;;
    esac

    jq_data_filter="${jq_data_filter} | . + {\"${key}\": \$${varname}}"
  done

  # Generate event fields
  local event_id ts instance_id
  event_id="$(_sf_uuid)" || return 1
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  instance_id="${SUPERFLOW_INSTANCE_ID:-default}"

  # Build complete event JSON via jq — no shell interpolation of user values
  local event_json
  local jq_filter='{ v: 1, id: $id, ts: $ts, run_id: $run_id, instance_id: $instance_id, type: $type, data: ('"${jq_data_filter}"') }'
  # Optionally include parent_id if SF_PARENT_ID is set
  if [ -n "${SF_PARENT_ID:-}" ]; then
    jq_filter='{ v: 1, id: $id, ts: $ts, run_id: $run_id, instance_id: $instance_id, parent_id: $parent_id, type: $type, data: ('"${jq_data_filter}"') }'
    event_json="$(jq -cn \
      --arg id          "$event_id" \
      --arg ts          "$ts" \
      --arg run_id      "$SUPERFLOW_RUN_ID" \
      --arg instance_id "$instance_id" \
      --arg parent_id   "$SF_PARENT_ID" \
      --arg type        "$type" \
      "${jq_args[@]}" \
      "$jq_filter")" || {
      echo "sf_emit: jq failed to build event JSON" >&2
      return 1
    }
  else
    event_json="$(jq -cn \
      --arg id          "$event_id" \
      --arg ts          "$ts" \
      --arg run_id      "$SUPERFLOW_RUN_ID" \
      --arg instance_id "$instance_id" \
      --arg type        "$type" \
      "${jq_args[@]}" \
      "$jq_filter")" || {
      echo "sf_emit: jq failed to build event JSON" >&2
      return 1
    }
  fi

  # Determine output file and ensure directory exists
  local out_file="${SUPERFLOW_EVENTS_FILE:-.superflow/events.jsonl}"
  mkdir -p "$(dirname "$out_file")"

  # Append event as a single line
  printf '%s\n' "$event_json" >> "$out_file" || return 1

  # Rotation check: runs on every emission. Cost: one wc -l per emission — cheap.
  # File-state check ensures rotation triggers even in short-lived single-emit invocations.
  _sf_check_rotation "$out_file"
}

# ---------------------------------------------------------------------------
# _sf_rotation_self_test
# Manual smoke test for log rotation. Invoke as:
#   source tools/sf-emit.sh && _sf_rotation_self_test
# Writes 5500 lines at threshold 5000, checks archive, reports line counts.
# ---------------------------------------------------------------------------
_sf_rotation_self_test() {
  local test_dir
  test_dir="$(mktemp -d)"
  echo "sf_rotation_self_test: using temp dir $test_dir"

  local old_events_file="${SUPERFLOW_EVENTS_FILE:-}"
  local old_run_id="${SUPERFLOW_RUN_ID:-}"
  local old_max="${SUPERFLOW_EVENT_LOG_MAX_LINES:-5000}"
  local old_interval="${_SF_ROTATION_CHECK_INTERVAL:-100}"

  export SUPERFLOW_EVENTS_FILE="$test_dir/events.jsonl"
  export SUPERFLOW_RUN_ID="00000000-0000-4000-8000-000000000099"
  export SUPERFLOW_EVENT_LOG_MAX_LINES=5000
  _SF_ROTATION_CHECK_INTERVAL=100
  _SF_EMIT_CALL_COUNT=0

  echo "sf_rotation_self_test: emitting 5500 heartbeats (threshold=5000, check every 100)..."
  local i=1
  while [ $i -le 5500 ]; do
    sf_emit heartbeat phase2_step=self_test
    i=$(( i + 1 ))
  done

  echo ""
  echo "sf_rotation_self_test: results:"
  echo "  archive dir contents:"
  ls -la "$test_dir/archive/" 2>/dev/null || echo "  (archive dir not found)"
  echo "  line counts:"
  wc -l "$test_dir/events.jsonl" "$test_dir/archive/"*.jsonl 2>/dev/null || true

  # Restore state
  if [ -n "$old_events_file" ]; then
    export SUPERFLOW_EVENTS_FILE="$old_events_file"
  else
    unset SUPERFLOW_EVENTS_FILE
  fi
  if [ -n "$old_run_id" ]; then
    export SUPERFLOW_RUN_ID="$old_run_id"
  else
    unset SUPERFLOW_RUN_ID
  fi
  export SUPERFLOW_EVENT_LOG_MAX_LINES="$old_max"
  _SF_ROTATION_CHECK_INTERVAL="$old_interval"
  _SF_EMIT_CALL_COUNT=0

  rm -rf "$test_dir"
  echo "sf_rotation_self_test: done."
}

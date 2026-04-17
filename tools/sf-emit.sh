# sf-emit.sh — Superflow event emission library
# Log rotation: see tools/sf-emit.sh Sprint 3 hardening (not yet implemented).
#
# Usage:
#   source tools/sf-emit.sh        # once per session
#   sf_emit <type> [key=value ...]  # emit an event
#
# Examples:
#   sf_emit run.start runtime=claude phase=2
#   sf_emit agent.dispatch agent_type=implementer task="Sprint 1" model=sonnet
#   sf_emit sprint.end sprint=1 total_sprints=3 goal="Event log contract" complexity=medium
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

# Guard: apply strict mode only when this file is being sourced directly
# (avoids overriding the caller's own error handling in interactive shells)
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  # Being sourced — enable strict mode safely
  set -euo pipefail 2>/dev/null || true
fi

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
# All JSON construction done via jq -n with --arg/--argjson — no shell interpolation.
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
  # Use a counter to generate unique, sequential jq variable names (sfv0, sfv1, ...).
  # Each field maps to: --arg sfv<N> <val> or --argjson sfv<N> <val>
  # and the data filter references $sfv<N>.
  local jq_data_filter="{}"
  local -a jq_args=()
  local pair key val
  local _sf_counter=0

  for pair in "$@"; do
    # Split on first '=' only
    key="${pair%%=*}"
    val="${pair#*=}"

    if [ -z "$key" ] || [ "$key" = "$pair" ]; then
      echo "sf_emit: malformed argument '$pair' (expected key=value)" >&2
      return 1
    fi

    local varname="sfv${_sf_counter}"
    _sf_counter=$(( _sf_counter + 1 ))

    # Determine if value looks like an integer (no quotes needed in JSON)
    if [[ "$val" =~ ^-?[0-9]+$ ]]; then
      # Integer value — use --argjson so jq treats it as a number
      jq_args+=("--argjson" "$varname" "$val")
    else
      # String value — use --arg
      jq_args+=("--arg" "$varname" "$val")
    fi

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
  printf '%s\n' "$event_json" >> "$out_file"
}

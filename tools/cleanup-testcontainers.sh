#!/usr/bin/env bash
# Remove testcontainers leftovers from a crashed test run.
#
# Selection is label-based: testcontainers libraries stamp the label
# org.testcontainers=true on every container they start. Never match by
# container name — docker's default names (adjective_surname) collide with
# unrelated containers.
#
# Usage: bash $SUPERFLOW_SKILL_ROOT/tools/cleanup-testcontainers.sh [image-pattern]
#   image-pattern (optional): ADDITIONAL ancestor filter, e.g. postgres:16
#
# Idempotent: re-running after a successful cleanup is a no-op (exit 0).

set -euo pipefail

if ! command -v docker &>/dev/null; then
  echo "OK: docker not found — nothing to clean."
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "WARN: Docker daemon not reachable — skipping testcontainers cleanup."
  exit 0
fi

FILTERS=(--filter "label=org.testcontainers=true")
if [ -n "${1:-}" ]; then
  FILTERS+=(--filter "ancestor=$1")
fi

# -a includes stopped containers; -q emits IDs only
LEFTOVERS=$(docker ps -aq "${FILTERS[@]}")
if [ -z "$LEFTOVERS" ]; then
  echo "OK: no testcontainers leftovers${1:+ for image '$1'}."
  exit 0
fi

COUNT=$(printf '%s\n' "$LEFTOVERS" | grep -c .)
echo "Removing ${COUNT} testcontainers leftover(s)${1:+ (image filter: $1)}:"
docker ps -a "${FILTERS[@]}" --format '  {{.ID}}  {{.Image}}  {{.Names}}  ({{.Status}})'
printf '%s\n' "$LEFTOVERS" | xargs docker rm -f >/dev/null
echo "OK: removed ${COUNT} container(s)."

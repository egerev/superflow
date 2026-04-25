#!/usr/bin/env bash
# measure-phase2-context.sh — Quantify Phase 2 per-turn context savings (pre vs post Run 3)
#
# Usage: tools/measure-phase2-context.sh [--repo-root /path]
# Dependencies: bash/zsh, git, wc
# Exit: 0 always (measurement-only, non-blocking)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Last commit BEFORE the Run-3 refactor of phase2-execution.md.
# "refactor: reduce Phase 2 doc to DAG router" at 09d10e1 is the Run-3 refactor;
# its parent (09d10e1^) is the last pre-Run-3 state.
PRE_RUN3_COMMIT="09d10e1cea22802e99f976a95f8a90497bc81100^"

PRE_FILE="references/phase2-execution.md"

# Post-Run-3 files that compose the new Phase 2 docs
POST_ROUTER="${REPO_ROOT}/references/phase2-execution.md"
POST_WORKFLOW="${REPO_ROOT}/references/phase2/workflow.json"
POST_OVERVIEW="${REPO_ROOT}/references/phase2/overview.md"
STEPS_DIR="${REPO_ROOT}/references/phase2/steps"

# Tokens per character heuristic (industry standard approximation)
CHARS_PER_TOKEN=4

# ---------------------------------------------------------------------------
# Helper: line count for a file
# ---------------------------------------------------------------------------
count_lines() {
  local f="$1"
  wc -l < "$f" | tr -d ' '
}

count_chars() {
  local f="$1"
  wc -c < "$f" | tr -d ' '
}

to_tokens() {
  local chars="$1"
  echo $(( chars / CHARS_PER_TOKEN ))
}

echo "================================================================"
echo "measure-phase2-context.sh — Phase 2 per-turn context savings"
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Pre-Run-3: old phase2-execution.md (always fully loaded per sprint)
# ---------------------------------------------------------------------------
echo "[ PRE-RUN-3: references/phase2-execution.md (fully loaded per sprint) ]"

PRE_LINES="$(git -C "$REPO_ROOT" show "${PRE_RUN3_COMMIT}:${PRE_FILE}" 2>/dev/null | wc -l | tr -d ' ')"
PRE_CHARS="$(git -C "$REPO_ROOT" show "${PRE_RUN3_COMMIT}:${PRE_FILE}" 2>/dev/null | wc -c | tr -d ' ')"
PRE_TOKENS="$(to_tokens "$PRE_CHARS")"

echo "  File:   ${PRE_FILE} (at commit 65a90db — last pre-Run-3)"
echo "  Lines:  ${PRE_LINES}"
echo "  Chars:  ${PRE_CHARS}"
echo "  Tokens: ~${PRE_TOKENS}"
echo ""

# ---------------------------------------------------------------------------
# 2. Post-Run-3: worst case — all files combined
# ---------------------------------------------------------------------------
echo "[ POST-RUN-3 (WORST CASE): all post-Run-3 Phase 2 files loaded ]"

# Count all step files
STEP_FILES_TOTAL_LINES=0
STEP_FILES_TOTAL_CHARS=0
STEP_FILE_COUNT=0
STEP_FILES_LIST=""
for f in "$STEPS_DIR"/*.md; do
  [ -f "$f" ] || continue
  STEP_FILES_TOTAL_LINES=$(( STEP_FILES_TOTAL_LINES + $(count_lines "$f") ))
  STEP_FILES_TOTAL_CHARS=$(( STEP_FILES_TOTAL_CHARS + $(count_chars "$f") ))
  STEP_FILE_COUNT=$(( STEP_FILE_COUNT + 1 ))
  STEP_FILES_LIST="${STEP_FILES_LIST} $(basename "$f")"
done

ROUTER_LINES="$(count_lines "$POST_ROUTER")"
WORKFLOW_LINES="$(count_lines "$POST_WORKFLOW")"
OVERVIEW_LINES="$(count_lines "$POST_OVERVIEW")"
ROUTER_CHARS="$(count_chars "$POST_ROUTER")"
WORKFLOW_CHARS="$(count_chars "$POST_WORKFLOW")"
OVERVIEW_CHARS="$(count_chars "$POST_OVERVIEW")"

WORST_LINES=$(( ROUTER_LINES + WORKFLOW_LINES + OVERVIEW_LINES + STEP_FILES_TOTAL_LINES ))
WORST_CHARS=$(( ROUTER_CHARS + WORKFLOW_CHARS + OVERVIEW_CHARS + STEP_FILES_TOTAL_CHARS ))
WORST_TOKENS="$(to_tokens "$WORST_CHARS")"

echo "  phase2-execution.md (router stub):  ${ROUTER_LINES} lines / ${ROUTER_CHARS} chars"
echo "  workflow.json:                       ${WORKFLOW_LINES} lines / ${WORKFLOW_CHARS} chars"
echo "  overview.md:                         ${OVERVIEW_LINES} lines / ${OVERVIEW_CHARS} chars"
echo "  Step files (${STEP_FILE_COUNT} files):               ${STEP_FILES_TOTAL_LINES} lines / ${STEP_FILES_TOTAL_CHARS} chars"
echo "  -------"
echo "  TOTAL (worst case):                  ${WORST_LINES} lines / ${WORST_CHARS} chars / ~${WORST_TOKENS} tokens"
echo ""

# ---------------------------------------------------------------------------
# 3. Post-Run-3: typical per-turn load (workflow.json + overview.md + 1 step file)
# ---------------------------------------------------------------------------
echo "[ POST-RUN-3 (TYPICAL PER-TURN): workflow.json + overview.md + 1 step file ]"

# Find the median-sized step file as representative single step
STEP_FILE_AVG_CHARS=$(( STEP_FILES_TOTAL_CHARS / (STEP_FILE_COUNT > 0 ? STEP_FILE_COUNT : 1) ))
STEP_FILE_AVG_LINES=$(( STEP_FILES_TOTAL_LINES / (STEP_FILE_COUNT > 0 ? STEP_FILE_COUNT : 1) ))

TYPICAL_CHARS=$(( WORKFLOW_CHARS + OVERVIEW_CHARS + STEP_FILE_AVG_CHARS ))
TYPICAL_LINES=$(( WORKFLOW_LINES + OVERVIEW_LINES + STEP_FILE_AVG_LINES ))
TYPICAL_TOKENS="$(to_tokens "$TYPICAL_CHARS")"

echo "  workflow.json:      ${WORKFLOW_LINES} lines / ${WORKFLOW_CHARS} chars"
echo "  overview.md:        ${OVERVIEW_LINES} lines / ${OVERVIEW_CHARS} chars"
echo "  1 avg step file:    ${STEP_FILE_AVG_LINES} lines / ${STEP_FILE_AVG_CHARS} chars (avg of ${STEP_FILE_COUNT} step files)"
echo "  -------"
echo "  TOTAL (typical):    ${TYPICAL_LINES} lines / ${TYPICAL_CHARS} chars / ~${TYPICAL_TOKENS} tokens"
echo ""

# ---------------------------------------------------------------------------
# 4. Savings calculation
# ---------------------------------------------------------------------------
echo "[ SAVINGS ANALYSIS ]"

# Savings: typical-per-turn vs pre-Run-3
if [ "$PRE_CHARS" -gt 0 ]; then
  # Use python3 for float arithmetic
  SAVINGS_PCT="$(python3 -c "print(f'{(1 - $TYPICAL_CHARS / $PRE_CHARS) * 100:.1f}')")"
  WORST_SAVINGS_PCT="$(python3 -c "print(f'{(1 - $WORST_CHARS / $PRE_CHARS) * 100:.1f}')")"
else
  SAVINGS_PCT="N/A"
  WORST_SAVINGS_PCT="N/A"
fi

echo "  Pre-Run-3 (always loaded):     ${PRE_LINES} lines / ${PRE_CHARS} chars / ~${PRE_TOKENS} tokens"
echo "  Post-Run-3 worst case:         ${WORST_LINES} lines / ${WORST_CHARS} chars / ~${WORST_TOKENS} tokens"
echo "  Post-Run-3 typical per-turn:   ${TYPICAL_LINES} lines / ${TYPICAL_CHARS} chars / ~${TYPICAL_TOKENS} tokens"
echo ""
echo "  Savings (typical vs pre):      ${SAVINGS_PCT}% reduction in chars / tokens per turn"
echo "  Savings (worst vs pre):        ${WORST_SAVINGS_PCT}% reduction even when all files are loaded"
echo ""

# ---------------------------------------------------------------------------
# Summary line (machine-parseable)
# ---------------------------------------------------------------------------
echo "================================================================"
echo "SUMMARY"
echo "================================================================"
echo "Pre: ${PRE_LINES} lines (~${PRE_TOKENS} tokens) | Post-typical: ${TYPICAL_LINES} lines (~${TYPICAL_TOKENS} tokens) | Savings: ${SAVINGS_PCT}%"
echo ""
exit 0

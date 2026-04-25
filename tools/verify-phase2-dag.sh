#!/usr/bin/env bash
# verify-phase2-dag.sh — Static verification of Phase 2 DAG (workflow.json + step files)
#
# Usage: tools/verify-phase2-dag.sh [--repo-root /path]
# Dependencies: bash/zsh, python3, jq
# Exit: 0 if all checks pass; 1 if any check fails

set -euo pipefail

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      [[ -z "${2:-}" ]] && { echo "Error: --repo-root requires a path" >&2; exit 2; }
      REPO_ROOT="$2"
      shift 2
      ;;
    --repo-root=*)
      REPO_ROOT="${1#--repo-root=}"
      shift
      ;;
    -h|--help)
      sed -n '/^# Usage:/,/^[^#]/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Error: unknown argument '$1'" >&2
      exit 2
      ;;
  esac
done
[[ -d "$REPO_ROOT" ]] || { echo "Error: REPO_ROOT '$REPO_ROOT' not a directory" >&2; exit 2; }

WORKFLOW_JSON="${REPO_ROOT}/references/phase2/workflow.json"
STEPS_DIR="${REPO_ROOT}/references/phase2/steps"

PASS=0
FAIL=0
ERRORS=()

pass() { echo "  PASS: $*"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $*" >&2; ERRORS+=("$*"); FAIL=$(( FAIL + 1 )); }
info() { echo "  INFO: $*"; }

echo "================================================================"
echo "verify-phase2-dag.sh — Phase 2 DAG static verification"
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# Pre-check: jq and python3 available
# ---------------------------------------------------------------------------
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required but not found in PATH" >&2
  exit 1
fi
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is required but not found in PATH" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Check 1: workflow.json exists and is valid JSON
# ---------------------------------------------------------------------------
echo "[ Check 1: workflow.json existence and validity ]"
if [ ! -f "$WORKFLOW_JSON" ]; then
  echo "FATAL: workflow.json not found at $WORKFLOW_JSON" >&2
  exit 1
fi
if ! jq empty "$WORKFLOW_JSON" 2>/dev/null; then
  echo "FATAL: workflow.json is not valid JSON" >&2
  exit 1
fi
pass "workflow.json exists and is valid JSON"
echo ""

# ---------------------------------------------------------------------------
# Check 2: decision_matrix.review_config — all 9 cells exist with correct shape
# ---------------------------------------------------------------------------
echo "[ Check 2: decision_matrix.review_config — 9 cells ]"

GOVERNANCE_MODES=("light" "standard" "critical")
COMPLEXITY_LEVELS=("simple" "medium" "complex")
VALID_TIERS=("standard" "deep")

echo ""
echo "  Per-cell report:"
for gov in "${GOVERNANCE_MODES[@]}"; do
  for cplx in "${COMPLEXITY_LEVELS[@]}"; do
    key="${gov}+${cplx}"
    cell="$(jq -r --arg k "$key" '.decision_matrix.review_config[$k] // empty' "$WORKFLOW_JSON")"
    if [ -z "$cell" ]; then
      fail "Missing cell: $key"
      continue
    fi

    reviewers="$(echo "$cell" | jq -r '.reviewers')"
    tier="$(echo "$cell" | jq -r '.tier')"
    par_skip="$(echo "$cell" | jq -r '.par_skip_product')"

    # Validate reviewers ∈ {1, 2}
    if [[ "$reviewers" != "1" && "$reviewers" != "2" ]]; then
      fail "$key: reviewers=$reviewers (expected 1 or 2)"
    fi

    # Validate tier ∈ {standard, deep}
    tier_valid=0
    for t in "${VALID_TIERS[@]}"; do
      [[ "$t" == "$tier" ]] && tier_valid=1
    done
    if [ "$tier_valid" -eq 0 ]; then
      fail "$key: tier=$tier (expected standard or deep)"
    fi

    # Validate par_skip_product ∈ {true, false}
    if [[ "$par_skip" != "true" && "$par_skip" != "false" ]]; then
      fail "$key: par_skip_product=$par_skip (expected true or false)"
    fi

    echo "  ${key}: reviewers=${reviewers}, tier=${tier}, par_skip_product=${par_skip}"
    pass "$key cell has correct shape"
  done
done
echo ""

# ---------------------------------------------------------------------------
# Check 3: 7 stages in expected order
# ---------------------------------------------------------------------------
echo "[ Check 3: Stage sequence — 7 stages in correct order ]"

EXPECTED_STAGES=("setup" "implementation" "review" "docs" "par" "ship" "completion")
ACTUAL_STAGES=()
while IFS= read -r stage_id; do
  ACTUAL_STAGES+=("$stage_id")
done < <(jq -r '.stages[].id' "$WORKFLOW_JSON")

if [ "${#ACTUAL_STAGES[@]}" -ne "${#EXPECTED_STAGES[@]}" ]; then
  fail "Expected ${#EXPECTED_STAGES[@]} stages, found ${#ACTUAL_STAGES[@]}: ${ACTUAL_STAGES[*]}"
else
  all_ok=1
  for i in "${!EXPECTED_STAGES[@]}"; do
    if [ "${ACTUAL_STAGES[$i]}" != "${EXPECTED_STAGES[$i]}" ]; then
      fail "Stage[$i]: expected '${EXPECTED_STAGES[$i]}', found '${ACTUAL_STAGES[$i]}'"
      all_ok=0
    fi
  done
  if [ "$all_ok" -eq 1 ]; then
    pass "7 stages in correct order: $(IFS=' → '; echo "${EXPECTED_STAGES[*]}")"
  fi
fi
echo ""

# ---------------------------------------------------------------------------
# Check 4: Every step in stages[*].steps has an entry in step_files
# ---------------------------------------------------------------------------
echo "[ Check 4: Every stage step has an entry in step_files ]"

# Collect all step_files keys
STEP_FILE_KEYS=()
while IFS= read -r k; do
  STEP_FILE_KEYS+=("$k")
done < <(jq -r '.step_files | keys[]' "$WORKFLOW_JSON")

# Collect all steps from stages
STAGE_STEPS=()
while IFS= read -r step; do
  STAGE_STEPS+=("$step")
done < <(jq -r '.stages[].steps[]' "$WORKFLOW_JSON")

for step in "${STAGE_STEPS[@]}"; do
  found=0
  for k in "${STEP_FILE_KEYS[@]}"; do
    [[ "$k" == "$step" ]] && found=1 && break
  done
  if [ "$found" -eq 0 ]; then
    fail "Step '$step' in stages but missing from step_files"
  else
    pass "Stage step '$step' has step_files entry"
  fi
done
echo ""

# ---------------------------------------------------------------------------
# Check 5: Cross-cutting steps in step_files but not in any stage's steps — print as INFO
# ---------------------------------------------------------------------------
echo "[ Check 5: Cross-cutting steps (in step_files but not in any stage) ]"

STAGE_STEPS_SET="$(jq -r '.stages[].steps[]' "$WORKFLOW_JSON" | sort -u)"
for k in "${STEP_FILE_KEYS[@]}"; do
  if ! echo "$STAGE_STEPS_SET" | grep -qx "$k"; then
    info "Cross-cutting step (not in any stage): '$k'"
  fi
done
echo ""

# ---------------------------------------------------------------------------
# Check 6: For each non-null step file in step_files, verify file exists on disk
# ---------------------------------------------------------------------------
echo "[ Check 6: Step files exist on disk ]"

# Use python3 to parse the step_files object and check non-null values
if _WORKFLOW_JSON="$WORKFLOW_JSON" _STEPS_DIR="$STEPS_DIR" python3 - <<'PYTHON'
import json, os, sys

workflow_path = os.environ["_WORKFLOW_JSON"]
steps_dir = os.environ["_STEPS_DIR"]

with open(workflow_path) as f:
    data = json.load(f)

step_files = data.get("step_files", {})
checked = set()
failures = []

for step_id, filename in step_files.items():
    if filename is None:
        continue
    if filename in checked:
        continue
    checked.add(filename)
    full_path = os.path.join(steps_dir, filename)
    if not os.path.isfile(full_path):
        failures.append(f"  FAIL: step file not found on disk: {filename} (for step '{step_id}')")
        print(failures[-1])
    else:
        print(f"  PASS: step file exists: {filename}")

if failures:
    sys.exit(1)
PYTHON
then
  PASS=$(( PASS + 1 ))
else
  FAIL=$(( FAIL + 1 ))
  ERRORS+=("Check 6: step files on disk — see python output above")
fi
echo ""

# ---------------------------------------------------------------------------
# Section: Per-combination step sequences (9 cells × walkthrough)
# ---------------------------------------------------------------------------
echo "================================================================"
echo "Per-combination step sequence walkthrough (all 9 cells)"
echo "================================================================"
echo ""

STAGE_SEQUENCE="setup → implementation → review → docs → par → ship → completion"

for gov in "${GOVERNANCE_MODES[@]}"; do
  for cplx in "${COMPLEXITY_LEVELS[@]}"; do
    key="${gov}+${cplx}"
    cell="$(jq -r --arg k "$key" '.decision_matrix.review_config[$k] // empty' "$WORKFLOW_JSON")"
    reviewers="$(echo "$cell" | jq -r '.reviewers')"
    tier="$(echo "$cell" | jq -r '.tier')"
    par_skip="$(echo "$cell" | jq -r '.par_skip_product')"

    # Holistic required: governance=critical OR sprint_count >= 4 OR max_parallel > 1
    # For static check, sprint_count and max_parallel are unknowns.
    # governance=critical → always required; others → conditional on runtime values.
    if [[ "$gov" == "critical" ]]; then
      holistic="YES (governance=critical)"
    else
      holistic="CONDITIONAL (sprint_count>=4 or max_parallel>1)"
    fi

    echo "  ${key}:"
    echo "    Stages: ${STAGE_SEQUENCE}"
    echo "    Reviewers: ${reviewers}. Tier: ${tier}. Skip product: ${par_skip}. Holistic required: ${holistic}"
    echo ""
  done
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "================================================================"
echo "Verification Summary"
echo "================================================================"
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "FAILURES:" >&2
  for err in "${ERRORS[@]}"; do
    echo "  - $err" >&2
  done
  echo ""
  echo "Result: FAIL (${FAIL} check(s) failed)" >&2
  exit 1
else
  echo "Result: ALL CHECKS PASSED"
  exit 0
fi

#!/usr/bin/env bash
# shellcheck shell=bash
# release-gate.sh — Compute and persist the Phase 2→3 Release Gate verdict
#
# Reads from pre-assembled JSON inputs (orchestrator extracts these after running
# integration + E2E suites). Writes .superflow/release-gate/verdict.json atomically.
# This script is pure computation — it does NOT boot apps or drive browsers itself.
#
# Exit 0 = PASS or SKIPPED (safe to proceed to Phase 3).
# Exit 1 = FAIL (merge blocked; fix failing journeys / integration first).
# Exit 2 = usage error (bad flags or missing input files).
#
# Usage:
#   bash tools/release-gate.sh \
#     --project-type  <web|backend-only|library>        \
#     --journeys      <path/to/journeys.json>           \
#     --results       <path/to/results.json>            \
#     [--evidence-dir <path/to/evidence/directory>]
#
# --journeys format (JSON array — orchestrator extracts from charter test_strategy.journeys):
#   [{"id":"J1-login","spec_tag":"J1-login","spec_path":"e2e/auth.spec.ts",
#     "spec_title":"user can sign in @J1-login","owning_sprint":2}, ...]
#   Required keys: id, spec_tag. Pass [] for library/backend-only projects.
#
# --results format:
#   {
#     "specs_ran":         bool,    # false = zero specs executed (no-vacuous-pass trigger)
#     "integration":       string,  # "pass" | "fail" | "skipped"
#     "e2e_covered_tags":  [str],   # spec_tags of journeys whose spec ran and passed green
#     "e2e_failed_tags":   [str],   # spec_tags of journeys whose spec ran but failed
#     "browsers_present":  bool,    # false = playwright browser binaries not installed
#     "docker_present":    bool     # false = Docker unavailable (integration degrades)
#   }
#
# Verdict matrix:
#   library     → SKIPPED, exit 0 (E2E gate not applicable; coverage threshold substitutes)
#   web         → FAIL when: browsers absent | specs_ran=false + journeys defined |
#                            any journey missing from covered or present in failed |
#                            integration=fail.
#                 docker absent on web = LOUD note in reason, non-blocking when all E2E passed.
#                 PASS when all journeys green + integration not failing.
#   backend-only → FAIL when: docker absent | integration=fail | integration=skipped (conservative).
#                  PASS when integration=pass.
#
# Output (.superflow/release-gate/verdict.json — always written, even on FAIL):
#   {
#     "verdict":           "PASS" | "FAIL" | "SKIPPED",
#     "reason":            string,
#     "journeys_covered":  [str],  # spec_tags confirmed green (web only)
#     "journeys_missing":  [str],  # spec_tags uncovered or failed (web only)
#     "evidence_paths":    [str]   # files under --evidence-dir (empty if not provided)
#   }
#
# Requires: bash, jq
# Optional: gtimeout / timeout / perl (for probe timeouts)

set -euo pipefail

# ── Timeout helper (mirrors tools/detect-test-env.sh) ─────────────────────────
# Priority: gtimeout (macOS coreutils) → timeout (GNU) → perl alarm → fail-closed.
_TIMEOUT_CMD=""
if command -v gtimeout >/dev/null 2>&1; then
  _TIMEOUT_CMD="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  _TIMEOUT_CMD="timeout"
fi

# _timeout SECS CMD [ARGS...]
# Runs CMD with a wall-clock limit. Returns non-zero on timeout or when no
# timeout utility is available (fail-closed — never run unbounded probes).
_timeout() {
  local secs="$1"; shift
  if [ -n "${_TIMEOUT_CMD}" ]; then
    "${_TIMEOUT_CMD}" "${secs}" "$@"
  elif command -v perl >/dev/null 2>&1; then
    perl -e 'alarm shift; exec @ARGV' "${secs}" "$@"
  else
    return 1
  fi
}

# ── Cleanup helper ─────────────────────────────────────────────────────────────
_TMP_FILE=""
_cleanup() {
  if [ -n "${_TMP_FILE}" ]; then
    rm -f "${_TMP_FILE}"
  fi
}
trap '_cleanup' EXIT

# ── Flag parsing ───────────────────────────────────────────────────────────────
_PROJECT_TYPE=""
_JOURNEYS_FILE=""
_RESULTS_FILE=""
_EVIDENCE_DIR=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project-type)  _PROJECT_TYPE="$2";  shift 2 ;;
    --journeys)      _JOURNEYS_FILE="$2"; shift 2 ;;
    --results)       _RESULTS_FILE="$2";  shift 2 ;;
    --evidence-dir)  _EVIDENCE_DIR="$2";  shift 2 ;;
    *)
      printf 'release-gate: unknown flag: %s\n' "$1" >&2
      printf 'Usage: release-gate.sh --project-type <type> --journeys <f> --results <f> [--evidence-dir <d>]\n' >&2
      exit 2
      ;;
  esac
done

# ── Validate required args ─────────────────────────────────────────────────────
if [ -z "${_PROJECT_TYPE}" ] || [ -z "${_JOURNEYS_FILE}" ] || [ -z "${_RESULTS_FILE}" ]; then
  printf 'release-gate: --project-type, --journeys, and --results are required\n' >&2
  exit 2
fi

case "${_PROJECT_TYPE}" in
  web|backend-only|library) ;;
  *)
    printf 'release-gate: unknown project-type: %s (must be: web | backend-only | library)\n' \
      "${_PROJECT_TYPE}" >&2
    exit 2
    ;;
esac

if [ ! -f "${_JOURNEYS_FILE}" ]; then
  printf 'release-gate: journeys file not found: %s\n' "${_JOURNEYS_FILE}" >&2
  exit 2
fi

if [ ! -f "${_RESULTS_FILE}" ]; then
  printf 'release-gate: results file not found: %s\n' "${_RESULTS_FILE}" >&2
  exit 2
fi

# ── Read results manifest ──────────────────────────────────────────────────────
_SPECS_RAN=$(      jq -r '.specs_ran          // false'    "${_RESULTS_FILE}")
_INTEGRATION=$(    jq -r '.integration        // "skipped"' "${_RESULTS_FILE}")
_BROWSERS_PRESENT=$(jq -r '.browsers_present  // false'    "${_RESULTS_FILE}")
_DOCKER_PRESENT=$( jq -r '.docker_present     // false'    "${_RESULTS_FILE}")
_E2E_COVERED=$(    jq -c '.e2e_covered_tags   // []'       "${_RESULTS_FILE}")
_E2E_FAILED=$(     jq -c '.e2e_failed_tags    // []'       "${_RESULTS_FILE}")

# ── Collect evidence paths ─────────────────────────────────────────────────────
# Timeout-wrapped: a slow/networked evidence directory must not block verdict write.
_collect_evidence_paths() {
  local ev_dir="$1"
  if [ ! -d "${ev_dir}" ]; then
    printf '%s' "[]"
    return 0
  fi

  local _ev_out _ev_rc
  _ev_out=""
  _ev_rc=0
  _ev_out=$(_timeout 10 find "${ev_dir}" -maxdepth 3 -type f -print 2>/dev/null) || _ev_rc=$?

  if [ "${_ev_rc}" -ne 0 ] || [ -z "${_ev_out}" ]; then
    printf '%s' "[]"
    return 0
  fi

  # One path per line from find; jq -Rn '[inputs]' reads them into a JSON array.
  printf '%s' "${_ev_out}" | jq -Rn '[inputs]' 2>/dev/null || printf '%s' "[]"
}

_EVIDENCE_PATHS_JSON="[]"
if [ -n "${_EVIDENCE_DIR}" ]; then
  _EVIDENCE_PATHS_JSON=$(_collect_evidence_paths "${_EVIDENCE_DIR}")
fi

# ── Verdict state (set by _compute_verdict_* functions) ───────────────────────
_VERDICT=""
_REASON=""
_JOURNEYS_COVERED_JSON="[]"
_JOURNEYS_MISSING_JSON="[]"

# ── Library verdict ────────────────────────────────────────────────────────────
# E2E gate is not applicable; P2 coverage threshold substitutes as the quality gate.
_compute_verdict_library() {
  _VERDICT="SKIPPED"
  _REASON="library — E2E gate skipped; coverage threshold substitutes"
}

# ── Web verdict ────────────────────────────────────────────────────────────────
# Per-journey coverage by spec_tag is the primary gate. Integration is secondary.
# Docker absent = LOUD note in reason but non-blocking when all E2E journeys pass.
_compute_verdict_web() {
  local journey_count
  journey_count=$(jq 'length' "${_JOURNEYS_FILE}")

  # 1. Browsers absent → FAIL immediately (E2E is mandatory for web projects).
  if [ "${_BROWSERS_PRESENT}" = "false" ]; then
    _VERDICT="FAIL"
    _REASON="browsers absent — E2E cannot run on a web project; install Playwright browsers: npx playwright install chromium"
    if [ "${journey_count}" -gt 0 ]; then
      _JOURNEYS_MISSING_JSON=$(jq -c '[.[].spec_tag]' "${_JOURNEYS_FILE}")
    fi
    return
  fi

  # 2. No-vacuous-pass: journeys are defined but zero specs ran.
  #    "Nothing ran, nothing failed" is NOT a pass when journeys exist.
  if [ "${_SPECS_RAN}" = "false" ] && [ "${journey_count}" -gt 0 ]; then
    _VERDICT="FAIL"
    _REASON="no-vacuous-pass: specs_ran=false — per-journey coverage cannot be verified (${journey_count} journey(s) defined but no specs executed)"
    _JOURNEYS_MISSING_JSON=$(jq -c '[.[].spec_tag]' "${_JOURNEYS_FILE}")
    return
  fi

  # 3. Per-journey coverage: every journey spec_tag must appear in e2e_covered_tags
  #    AND must NOT appear in e2e_failed_tags. Coverage is per stable ID, not by count.
  _JOURNEYS_COVERED_JSON=$(jq -c \
    --argjson covered "${_E2E_COVERED}" \
    --argjson failed  "${_E2E_FAILED}" \
    '[.[] |
      .spec_tag as $t |
      select(
        (($covered | index($t)) != null) and
        (($failed  | index($t)) == null)
      ) | .spec_tag]' \
    "${_JOURNEYS_FILE}")

  _JOURNEYS_MISSING_JSON=$(jq -c \
    --argjson covered "${_E2E_COVERED}" \
    --argjson failed  "${_E2E_FAILED}" \
    '[.[] |
      .spec_tag as $t |
      select(
        (($covered | index($t)) == null) or
        (($failed  | index($t)) != null)
      ) | .spec_tag]' \
    "${_JOURNEYS_FILE}")

  local missing_count
  missing_count=$(printf '%s' "${_JOURNEYS_MISSING_JSON}" | jq 'length')

  if [ "${missing_count}" -gt 0 ]; then
    _VERDICT="FAIL"
    local missing_list
    missing_list=$(printf '%s' "${_JOURNEYS_MISSING_JSON}" | jq -r 'join(", ")')
    _REASON="per-journey coverage FAIL: ${missing_count} journey(s) uncovered or failed: ${missing_list}"
    return
  fi

  # 4. Integration failure blocks even when all E2E journeys pass.
  if [ "${_INTEGRATION}" = "fail" ]; then
    _VERDICT="FAIL"
    _REASON="integration tests FAILED (E2E journeys all passed)"
    return
  fi

  # 5. Docker absent = LOUD note in reason (non-blocking for web when E2E passed).
  #    Integration tests simply didn't run — this is surfaced prominently but does
  #    not override a green E2E gate for web projects (integration is a secondary gate).
  local covered_count
  covered_count=$(printf '%s' "${_JOURNEYS_COVERED_JSON}" | jq 'length')
  local docker_note=""
  if [ "${_DOCKER_PRESENT}" = "false" ]; then
    docker_note=" [LOUD: integration skipped — docker absent; no integration tests ran]"
  fi

  _VERDICT="PASS"
  _REASON="all ${covered_count} journey(s) covered green; integration=${_INTEGRATION}${docker_note}"
}

# ── Backend-only verdict ───────────────────────────────────────────────────────
# Integration is the sole gate — no browser journeys required.
# Conservative on ambiguous states: docker absent → FAIL (can't verify without Docker).
_compute_verdict_backend_only() {
  _JOURNEYS_COVERED_JSON="[]"
  _JOURNEYS_MISSING_JSON="[]"

  # Docker absent: integration cannot run → conservative FAIL.
  # Rule: PASS only if there was genuinely nothing runnable. Since the project_type
  # is backend-only, integration tests ARE expected — their absence without Docker is
  # a FAIL, not a silent skip.
  if [ "${_DOCKER_PRESENT}" = "false" ]; then
    _VERDICT="FAIL"
    _REASON="[LOUD: INTEGRATION SKIPPED — docker absent] backend-only project requires integration tests; conservative FAIL (Docker needed to verify)"
    return
  fi

  case "${_INTEGRATION}" in
    pass)
      _VERDICT="PASS"
      _REASON="integration tests passed; no browser journeys required for backend-only"
      ;;
    fail)
      _VERDICT="FAIL"
      _REASON="integration tests FAILED"
      ;;
    skipped)
      # Docker is present but no integration tests ran — something is misconfigured.
      _VERDICT="FAIL"
      _REASON="integration tests skipped (docker present but integration suite did not run) — conservative FAIL; add integration tests or investigate"
      ;;
    *)
      _VERDICT="FAIL"
      _REASON="integration result unrecognised: '${_INTEGRATION}' — conservative FAIL"
      ;;
  esac
}

# ── Dispatch ───────────────────────────────────────────────────────────────────
case "${_PROJECT_TYPE}" in
  library)      _compute_verdict_library ;;
  web)          _compute_verdict_web ;;
  backend-only) _compute_verdict_backend_only ;;
esac

# ── Write verdict.json atomically ──────────────────────────────────────────────
# mkdir -p + mktemp + mv: a partial write never lands at the final path.
_OUT_DIR=".superflow/release-gate"
mkdir -p "${_OUT_DIR}"
_TMP_FILE=$(mktemp "${_OUT_DIR}/.verdict.XXXXXX.json.tmp")

jq -cn \
  --arg     verdict           "${_VERDICT}" \
  --arg     reason            "${_REASON}" \
  --argjson journeys_covered  "${_JOURNEYS_COVERED_JSON}" \
  --argjson journeys_missing  "${_JOURNEYS_MISSING_JSON}" \
  --argjson evidence_paths    "${_EVIDENCE_PATHS_JSON}" \
  '{
    "verdict":          $verdict,
    "reason":           $reason,
    "journeys_covered": $journeys_covered,
    "journeys_missing": $journeys_missing,
    "evidence_paths":   $evidence_paths
  }' > "${_TMP_FILE}"

mv "${_TMP_FILE}" "${_OUT_DIR}/verdict.json"
_TMP_FILE=""   # prevent cleanup from removing the successfully written file

printf 'release-gate: verdict=%s → %s\n' "${_VERDICT}" "${_OUT_DIR}/verdict.json" >&2

# Exit 0 = PASS or SKIPPED (proceed to Phase 3); exit 1 = FAIL (merge blocked).
case "${_VERDICT}" in
  PASS|SKIPPED) exit 0 ;;
  FAIL)         exit 1 ;;
  *)            exit 1 ;;   # defensive: unknown verdict → fail closed
esac

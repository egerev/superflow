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
# --journeys format (JSON array — orchestrator emits from charter test_strategy.journeys):
#   [{"id":"J1-login","spec_tag":"J1-login","spec_path":"e2e/auth.spec.ts",
#     "spec_title":"user can sign in @J1-login","owning_sprint":2}, ...]
#   Required keys per element: id (string), spec_tag (non-empty string).
#   Pass [] for library and backend-only projects (no journeys expected).
#   Web projects MUST supply ≥1 journey — [] on web → FAIL (no-vacuous-pass).
#
# --results format:
#   {
#     "specs_ran":         bool,    # false = zero specs executed (no-vacuous-pass trigger)
#     "integration":       string,  # "pass" | "skipped" | anything else = FAIL
#     "e2e_covered_tags":  [str],   # spec_tags of journeys whose spec passed green
#     "e2e_failed_tags":   [str],   # spec_tags of journeys whose spec ran but failed
#     "browsers_present":  bool,    # false = playwright browser binaries not installed
#     "docker_present":    bool     # false = Docker unavailable (integration degrades)
#   }
#   e2e_covered_tags and e2e_failed_tags MUST be JSON arrays of strings.
#   Any other type (e.g. a comma-separated string) → FAIL (fail-closed, never PASS).
#
# Verdict matrix:
#   library     → SKIPPED, exit 0 (E2E gate not applicable; coverage threshold substitutes)
#   web         → FAIL when: zero journeys supplied | browsers absent |
#                            specs_ran=false | any journey not in covered or in failed |
#                            integration not in {pass, skipped} (fail-closed on unknown).
#                 integration=skipped on web = LOUD note in reason, non-blocking
#                 (E2E journey coverage is the primary gate for web projects).
#                 PASS when all journeys green + integration in {pass, skipped}.
#   backend-only → FAIL when: docker absent | integration=fail | integration=skipped
#                             (conservative: cannot verify without running tests).
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

# ── Input schema validation (FIX 2) ───────────────────────────────────────────
# Fail-closed: malformed JSON types must never produce a false PASS.
# Any field with the wrong type → FAIL verdict (see dispatch section).
_validate_inputs() {
  # journeys file must be a JSON array
  if ! jq -e 'type == "array"' "${_JOURNEYS_FILE}" >/dev/null 2>&1; then
    printf 'release-gate: --journeys must be a JSON array\n' >&2
    return 1
  fi

  # Every journey element must have a non-empty string spec_tag
  local _bad
  _bad=$(jq -r '
    .[] | select(
      (.spec_tag // "") | (type != "string" or length == 0)
    ) | .id // "(unknown id)"
  ' "${_JOURNEYS_FILE}" 2>/dev/null) || _bad=""
  if [ -n "${_bad}" ]; then
    printf 'release-gate: journey(s) missing non-empty spec_tag: %s\n' "${_bad}" >&2
    return 1
  fi

  # e2e_covered_tags must be a JSON array of strings (not a comma-joined string etc.)
  if ! printf '%s' "${_E2E_COVERED}" | \
       jq -e 'type == "array" and all(.[]; type == "string")' >/dev/null 2>&1; then
    printf 'release-gate: results.e2e_covered_tags must be a JSON array of strings (got type=%s)\n' \
      "$(printf '%s' "${_E2E_COVERED}" | jq -r 'type' 2>/dev/null || echo '?')" >&2
    return 1
  fi

  # e2e_failed_tags must be a JSON array of strings
  if ! printf '%s' "${_E2E_FAILED}" | \
       jq -e 'type == "array" and all(.[]; type == "string")' >/dev/null 2>&1; then
    printf 'release-gate: results.e2e_failed_tags must be a JSON array of strings (got type=%s)\n' \
      "$(printf '%s' "${_E2E_FAILED}" | jq -r 'type' 2>/dev/null || echo '?')" >&2
    return 1
  fi
}

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
# Fail-closed on: zero journeys, absent browsers, zero specs ran, uncovered journeys,
# and unrecognized integration values.
_compute_verdict_web() {
  local journey_count
  journey_count=$(jq 'length' "${_JOURNEYS_FILE}")

  # FIX 1: Web must supply ≥1 journey — empty journeys array → FAIL.
  # A web charter without journeys has no coverage definition; the gate cannot verify
  # anything and must never pass vacuously. Ensure charter defines journeys before
  # running the gate.
  if [ "${journey_count}" -eq 0 ]; then
    _VERDICT="FAIL"
    _REASON="web project but zero journeys supplied — charter must define ≥1 journey; per-journey coverage requires at least one journey to verify"
    return
  fi

  # Browsers absent → FAIL immediately (E2E is mandatory for web projects).
  if [ "${_BROWSERS_PRESENT}" = "false" ]; then
    _VERDICT="FAIL"
    _REASON="browsers absent — E2E cannot run on a web project; install Playwright browsers: npx playwright install chromium"
    _JOURNEYS_MISSING_JSON=$(jq -c '[.[].spec_tag]' "${_JOURNEYS_FILE}")
    return
  fi

  # No-vacuous-pass: specs must have executed. journey_count > 0 guaranteed above.
  # "Nothing ran, nothing failed" is NOT a pass when journeys exist.
  if [ "${_SPECS_RAN}" = "false" ]; then
    _VERDICT="FAIL"
    _REASON="no-vacuous-pass: specs_ran=false — per-journey coverage cannot be verified (${journey_count} journey(s) defined but no specs executed)"
    _JOURNEYS_MISSING_JSON=$(jq -c '[.[].spec_tag]' "${_JOURNEYS_FILE}")
    return
  fi

  # Per-journey coverage: EXACT set-membership (FIX 2).
  # any($arr[]; . == $t) uses strict element equality — never substring matching.
  # A journey is covered iff its spec_tag is an exact element of e2e_covered_tags
  # AND is NOT an exact element of e2e_failed_tags.
  _JOURNEYS_COVERED_JSON=$(jq -c \
    --argjson covered "${_E2E_COVERED}" \
    --argjson failed  "${_E2E_FAILED}" \
    '[.[] |
      .spec_tag as $t |
      select(
        any($covered[]; . == $t) and
        (any($failed[]; . == $t) | not)
      ) | .spec_tag]' \
    "${_JOURNEYS_FILE}")

  _JOURNEYS_MISSING_JSON=$(jq -c \
    --argjson covered "${_E2E_COVERED}" \
    --argjson failed  "${_E2E_FAILED}" \
    '[.[] |
      .spec_tag as $t |
      select(
        (any($covered[]; . == $t) | not) or
        any($failed[]; . == $t)
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

  # Integration gate — fail-closed on unrecognised values (FIX 3).
  # Whitelist: {pass, skipped}. Anything else (fail, failed, error, fatal, unknown) → FAIL.
  # Rationale: "skipped" is the only legitimate non-pass: docker absent or no integration
  # suite. On web, E2E journey coverage is the primary gate so a LOUD skipped is
  # non-blocking. Any other value that is not "pass" must be treated as a failure —
  # never let an unknown string silently pass the gate.
  local docker_note=""
  case "${_INTEGRATION}" in
    pass)
      # Integration ran and passed cleanly — no additional note needed.
      ;;
    skipped)
      # Legitimate degrade: docker absent or no integration suite configured.
      # Non-blocking for web (E2E is the primary gate) but surfaced loudly in reason.
      if [ "${_DOCKER_PRESENT}" = "false" ]; then
        docker_note=" [LOUD: integration skipped — docker absent; no integration tests ran]"
      else
        docker_note=" [LOUD: integration skipped — docker present but suite did not run; confirm expected]"
      fi
      ;;
    *)
      # Fail-closed: "fail", "failed", "error", "fatal", or any unrecognised value.
      # Only "pass" and "skipped" are recognised non-failure values.
      _VERDICT="FAIL"
      _REASON="integration result '${_INTEGRATION}' treated as failure (fail-closed: only 'pass' and 'skipped' are recognised non-failure values)"
      return
      ;;
  esac

  local covered_count
  covered_count=$(printf '%s' "${_JOURNEYS_COVERED_JSON}" | jq 'length')
  _VERDICT="PASS"
  _REASON="all ${covered_count} journey(s) covered green; integration=${_INTEGRATION}${docker_note}"
}

# ── Backend-only verdict ───────────────────────────────────────────────────────
# Integration is the sole gate — no browser journeys required.
# Conservative: docker absent or non-pass result → FAIL (cannot verify without running).
_compute_verdict_backend_only() {
  _JOURNEYS_COVERED_JSON="[]"
  _JOURNEYS_MISSING_JSON="[]"

  # Docker absent: integration cannot run → conservative FAIL.
  # Backend-only projects depend entirely on integration tests; Docker is required.
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
      # Unlike web, backend-only has no E2E fallback gate. Docker present but tests
      # didn't run = conservative FAIL (something is misconfigured or missing).
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
# Run input validation first; a malformed input must never produce PASS.
if _validate_inputs; then
  case "${_PROJECT_TYPE}" in
    library)      _compute_verdict_library ;;
    web)          _compute_verdict_web ;;
    backend-only) _compute_verdict_backend_only ;;
  esac
else
  # Schema validation failed — fail closed. Reason surfaced in stderr by _validate_inputs.
  _VERDICT="FAIL"
  _REASON="malformed results/journeys input — schema validation failed (see stderr for details)"
fi

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

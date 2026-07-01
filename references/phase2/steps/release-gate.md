# Release Gate Stage

**When:** Once per Phase 2 run — AFTER the sprint loop and optional Holistic Review, BEFORE the
Completion Report and Phase 3. Not a per-sprint stage.

**Purpose:** Boot the assembled app, run integration + headless E2E autonomously, compute a
persisted verdict. Phase 3 refuses merge unless `.superflow/release-gate/verdict.json` holds
`verdict=PASS` (or `verdict=SKIPPED` for library projects).

**Reference:** `phase_gates.release_gate` in `references/phase2/workflow.json`.

---

## Journeys → Scenarios Handoff (end-to-end chain)

This gate is the **receiving end** of the Phase 1 test strategy:

1. **Phase 1** assigned each journey a `spec_tag` and `owning_sprint` (see `references/phase1-discovery.md` Step 13a).
2. **Each owning sprint** authored the executable spec at `spec_path`, annotating the test with `spec_tag` (e.g. `@J1-login`). No other sprint authors that spec.
3. **This gate (Step 8)** reads the charter's `test_strategy.journeys`, emits `journeys.json` keyed by `spec_tag`, runs Playwright, and checks that every journey appears in the covered (green) set.

**Who authors what:** the owning sprint's implementer writes the spec. The gate only verifies it ran green. Ambiguity → fail fast (FAIL verdict surfaces the missing journey `spec_tag`).

---

---

## Step 1 — Assembly

| Git workflow mode | Assembly action |
|---|---|
| `solo_single_pr` | Single branch — no-op; working tree is already the assembled app. |
| `sprint_pr_queue` / `stacked_prs` / `parallel_wave_prs` | Merge all sprint branches onto an integration branch before booting. **NOT YET VALIDATED** — the integration-branch assembly path was not exercised by the solo_single_pr Wave A run. The first real use of these modes with the release gate must validate and document this path. Flag any failures as a defect against this file. |
| `trunk_based` | Same as `solo_single_pr`. |

---

## Step 2 — Read `test-env.json`

```bash
jq '.' .superflow/test-env.json   # re-read; project_type + readiness flags may have changed
```

Extract:
- `project_type` → gates which layers run (web / backend-only / library)
- `readiness.e2e_tooling` → `true` means playwright + browser binaries are present
- `readiness.integration` → `true` means Docker is available for Testcontainers
- `docker.ryuk_forced_disabled` → `true` when rootless Podman is active (skip Ryuk)
- `node.playwright.browsers[]` → list of installed browsers (pick `chromium` first)

If `test-env.json` is absent, default `project_type=web` and all readiness flags to `false`
(triggers loud FAIL for web, library skips, backend-only conservative FAIL).

---

## Step 3 — Image-version pinning (web + Python E2E)

Derive the Playwright version from the project's installed package — never hard-code a version.

**Node / npm:**
```bash
PW_VERSION=$(jq -r '.devDependencies["@playwright/test"] // .dependencies["@playwright/test"] // empty' package.json 2>/dev/null | tr -d '^~')
# Node image:
NODE_IMAGE="mcr.microsoft.com/playwright:v${PW_VERSION}-noble"
```

**Python:**
```bash
PW_VERSION=$(pip show playwright 2>/dev/null | awk '/^Version:/{print $2}')
PYTHON_IMAGE="mcr.microsoft.com/playwright/python:v${PW_VERSION}-noble"
```

If the version cannot be resolved, fall back to the project's locked version (package-lock.json
`packages["node_modules/@playwright/test"].version` or `uv.lock`) rather than `latest`.

---

## Step 4 — Boot app (web projects only)

Use Playwright `webServer` config in `playwright.config.ts`:

```typescript
webServer: {
  command: 'npm run start',   // production start, not dev (or the project's start command)
  url: 'http://localhost:3000',
  timeout: 120_000,
  reuseExistingServer: false,   // always start fresh at gate time
}
```

**Health-route caveat (Playwright ≥ 1.42):** `webServer.url` probe changed from HEAD to GET in
1.42 to handle servers that reject HEAD. If the app does not expose a health route that returns
2xx/3xx/40x on GET, add `GET /healthz` (or a project-appropriate route) before running the gate.
Non-2xx/3xx/40x responses hang `webServer` until timeout.

Timeout-wrap the boot sequence: if startup times out, the gate verdict is FAIL (app not bootable),
not a hang.

---

## Step 5 — Run Testcontainers integration (web + backend-only)

**Before AND after** integration tests, run the cleanup backstop:
```bash
bash $SUPERFLOW_SKILL_ROOT/tools/cleanup-testcontainers.sh
```

**Ryuk precedence:**
- Enabled by default (Ryuk reaps containers automatically).
- Disabled ONLY when `CI=true` (GitHub Actions / CI environment) OR when
  `docker.ryuk_forced_disabled=true` in `test-env.json` (rootless Podman path).
- Never disable globally; never set the env var unconditionally.

```bash
# Implementer agent sets this — reproduced here for gate context only
if [ "${CI:-false}" = "true" ] || \
   [ "$(jq -r '.docker.ryuk_forced_disabled // false' .superflow/test-env.json)" = "true" ]; then
  export TESTCONTAINERS_RYUK_DISABLED=true
fi
```

Run tests with timeout — capture the command exit code, not the `tee` exit (FIX 4):
```bash
# Write to file first, then cat separately — avoids pipeline masking the test exit code.
# A pipeline of `cmd | tee` captures tee's exit (always 0), hiding a failing test suite.
timeout 300 npm run test:integration \
  > .superflow/release-gate/integration.log 2>&1
INTEGRATION_EXIT=$?
cat .superflow/release-gate/integration.log   # stream to terminal for live visibility
```

`INTEGRATION_EXIT=0` → `integration=pass`. Non-zero → `integration=fail`.
If Docker is absent (`readiness.integration=false`) → `integration=skipped` (noted loudly).

---

## Step 6 — Run Playwright E2E headless (web only)

Tag-based execution: run the E2E suite and capture per-journey outcomes by `spec_tag`.

```bash
# Use workers=1 for determinism at gate time (parallelism during dev is fine).
# PLAYWRIGHT_JSON_OUTPUT_NAME directs JSON reporter output to a file.
# NOTE: Playwright has NO --output-file flag — using it silently drops the flag
# and leaves pw-results.json unwritten.  Use the env var instead.
# Same redirect pattern as integration: file redirect preserves E2E_EXIT.
PLAYWRIGHT_JSON_OUTPUT_NAME=.superflow/release-gate/pw-results.json \
  timeout 300 npx playwright test --workers=1 --reporter=json \
  > .superflow/release-gate/e2e.log 2>&1
E2E_EXIT=$?
cat .superflow/release-gate/e2e.log   # stream for live visibility
```

**Trace + artefact capture:**
```bash
# playwright.config.ts at gate time
use: {
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
outputDir: '.superflow/release-gate/pw-artifacts',
```

Reference the `webapp-testing` skill for browser driving where it fits.

---

## Step 7 — Extract per-journey results + build `results.json`

### Playwright JSON reporter schema (FIX 5)

Playwright JSON reporter (`--reporter=json`) has these key fields:
- `spec.ok: bool` — `true` when the spec passed (all tests ran as `expectedStatus`). Use this; do NOT use `.tests[].status` (that field holds `expected|unexpected|flaky|skipped`, not `passed|failed`).
- `spec.tags: [str]` — native tag array (Playwright ≥ 1.42), e.g. `["@J1-login"]` (note the `@` prefix in the JSON).
- Suites are nested: `suite.suites[].specs[]` (file → describe → describe → spec). `.suites[].specs[]` is **not recursive** and misses nested describes. Recurse with `.. | objects | select(has("specs")) | .specs[]`.

### Tag extraction (FIX 6)

Prefer `spec.tags[]` (strip leading `@`); fall back to a regex capture from the spec title.
The fallback regex uses `[A-Za-z][A-Za-z0-9_-]*` — permissive enough to preserve full stable
IDs like `J2-checkoutV2` or `J1-sign_in` (the old `J[0-9]+-[a-z-]+` pattern truncated them).

**Constraint (FIX C):** the title-fallback regex `[A-Za-z][A-Za-z0-9_-]*` matches only
alphanumeric, hyphen, and underscore characters. Charter `spec_tag` values containing `.`,
`:`, `/`, or other punctuation (e.g. `J1.login/v2`) will NOT be matched by the title
fallback and will be silently missed. If your spec_tags include those characters, native
`spec.tags[]` (Playwright ≥ 1.42) is required. To ensure both extraction paths work, charter
authors should use kebab-slug IDs (`J<N>-<slug>`, e.g. `J1-login`, `J2-checkout-v2`).

```bash
# Covered: specs where ok=true
E2E_COVERED=$(jq -c '
  [
    .. | objects | select(has("specs")) | .specs[] |
    select(.ok == true) |
    (
      if ((.tags // []) | length) > 0 then
        .tags[] | ltrimstr("@")
      else
        .title | capture("@(?<tag>[A-Za-z][A-Za-z0-9_-]*)") | .tag // empty
      end
    )
  ] | unique
' .superflow/release-gate/pw-results.json 2>/dev/null || echo "[]")

# Failed: specs where ok=false (or null/missing — defensive)
E2E_FAILED=$(jq -c '
  [
    .. | objects | select(has("specs")) | .specs[] |
    select(.ok == false or .ok == null) |
    (
      if ((.tags // []) | length) > 0 then
        .tags[] | ltrimstr("@")
      else
        .title | capture("@(?<tag>[A-Za-z][A-Za-z0-9_-]*)") | .tag // empty
      end
    )
  ] | unique
' .superflow/release-gate/pw-results.json 2>/dev/null || echo "[]")
```

**Proof (mini Playwright JSON sample):**
```json
{"suites":[{"title":"auth.spec.ts","suites":[{"title":"Login","specs":[
  {"title":"user can sign in @J1-login","ok":true,"tags":["@J1-login"]},
  {"title":"checkout flow @J2-checkout","ok":false,"tags":["@J2-checkout"]}
]}]}]}
```
Running the covered jq above on this sample → `["J1-login"]`. A green suite now yields
covered tags (A1 pass path is operable). Failed jq → `["J2-checkout"]`.

### Determine `specs_ran` (FIX 7)

`timeout` exit code 124 (SIGTERM) or 137 (SIGKILL from kill -9) means the process was killed
before specs could finish — treat as `specs_ran=false` to avoid misleading evidence:

```bash
if [ "${E2E_EXIT}" -eq 124 ] || [ "${E2E_EXIT}" -eq 137 ]; then
  SPECS_RAN=false   # timed out — evidence is incomplete
elif [ "${E2E_EXIT}" -eq 0 ]; then
  SPECS_RAN=true
else
  # Non-zero, non-timeout: Playwright itself ran but tests failed
  SPECS_RAN=true
fi
```

### Build `results.json`

```bash
jq -cn \
  --argjson specs_ran        "${SPECS_RAN}" \
  --arg     integration      "${INTEGRATION_RESULT:-skipped}" \
  --argjson e2e_covered_tags "${E2E_COVERED}" \
  --argjson e2e_failed_tags  "${E2E_FAILED}" \
  --argjson browsers_present "$(jq '.readiness.e2e_tooling' .superflow/test-env.json)" \
  --argjson docker_present   "$(jq '.docker.present' .superflow/test-env.json)" \
  '{specs_ran:$specs_ran, integration:$integration,
    e2e_covered_tags:$e2e_covered_tags, e2e_failed_tags:$e2e_failed_tags,
    browsers_present:$browsers_present, docker_present:$docker_present}' \
  > .superflow/release-gate/results.json
```

---

## Step 8 — Build journeys.json + compute verdict (FIX 8)

### Build `journeys.json` — NO yq (orchestrator emits JSON directly)

`yq` is a FORBIDDEN dependency — only bash and jq are permitted. The orchestrator (the
Phase-2 LLM) reads the charter file (short file, always allowed under Rule 11), extracts the
`test_strategy.journeys` YAML block by reading it, and emits `journeys.json` as a direct
JSON array — no YAML parser needed.

**Orchestrator procedure:**

1. Read the charter: `docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`
2. From the charter's `test_strategy.journeys:` block, collect every journey's fields.
3. Write `.superflow/release-gate/journeys.json` using `jq -n` inline — one object per journey:

```bash
# The orchestrator constructs this; each journey comes from the charter YAML it read.
# Every journey MUST include spec_tag (non-empty string); if any is missing → gate FAILS.
jq -cn '
[
  {"id":"J1-login",    "spec_tag":"J1-login",    "spec_path":"e2e/auth.spec.ts",
   "spec_title":"user can sign in @J1-login",    "owning_sprint":2},
  {"id":"J2-checkout", "spec_tag":"J2-checkout", "spec_path":"e2e/checkout.spec.ts",
   "spec_title":"guest user completes checkout @J2-checkout", "owning_sprint":3}
]
' > .superflow/release-gate/journeys.json
```

For library and backend-only projects: write `[]` (empty array):
```bash
echo '[]' > .superflow/release-gate/journeys.json
```

If the charter has no `test_strategy` block (e.g. Phase 1 pre-dates A2), the orchestrator
injects the journeys from memory/conversation context. If none exist, the gate FAILS for web
(zero-journey guard, FIX 1), which surfaces the gap so the charter can be updated.

### Call the gate helper

```bash
bash tools/release-gate.sh \
  --project-type "$(jq -r '.project_type' .superflow/test-env.json)" \
  --journeys     .superflow/release-gate/journeys.json \
  --results      .superflow/release-gate/results.json \
  --evidence-dir .superflow/release-gate/pw-artifacts \
  ; GATE_EXIT=$?
```

The helper writes `.superflow/release-gate/verdict.json` atomically.

---

## Step 9 — Interpret verdict + proceed

Read the verdict:
```bash
jq '.' .superflow/release-gate/verdict.json
VERDICT=$(jq -r '.verdict' .superflow/release-gate/verdict.json)
```

| Verdict | Action |
|---|---|
| `PASS` | Proceed to Completion Report, then Phase 3. |
| `SKIPPED` | Project is a library; coverage threshold is the gate. Proceed to Completion Report. |
| `FAIL` | **STOP.** Surface `reason`, `journeys_missing`, and trace/screenshot artefacts. Fix the failing journeys or integration tests in the current branch, then re-run the gate (Steps 4–9). Do NOT proceed to Phase 3 with a FAIL verdict. |

---

## Conditional matrix

| Project type | Integration | E2E | Gate verdict trigger |
|---|---|---|---|
| `web` | Required (loud skip if docker absent) | Required; per-journey by `spec_tag` | All journeys green + integration not failing |
| `backend-only` | Required; sole gate | Not run | `integration=pass` |
| `library` | Not run | Not run | Always SKIPPED; coverage threshold from Phase 2 |
| Any + `docker_present=false` | Loudly skipped | Continues (web) or gate FAIL (backend-only) | See matrix above |
| Any + `browsers_present=false` | Continues (if applicable) | FAIL immediately on web | Install browsers first |

---

## Artefact paths

All artefacts land under `.superflow/release-gate/` (gitignored):

| Path | Contents |
|---|---|
| `verdict.json` | Gate verdict — machine-checkable by Phase 3 |
| `journeys.json` | Journey list extracted from charter |
| `results.json` | Assembled execution manifest |
| `integration.log` | Integration test stdout |
| `e2e.log` | Playwright CLI stdout |
| `pw-results.json` | Playwright JSON reporter output |
| `pw-artifacts/` | Traces, screenshots, videos (on failure) |

# Release Gate Stage

**When:** Once per Phase 2 run — AFTER the sprint loop and optional Holistic Review, BEFORE the
Completion Report and Phase 3. Not a per-sprint stage.

**Purpose:** Boot the assembled app, run integration + headless E2E autonomously, compute a
persisted verdict. Phase 3 refuses merge unless `.superflow/release-gate/verdict.json` holds
`verdict=PASS` (or `verdict=SKIPPED` for library projects).

**Reference:** `phase_gates.release_gate` in `references/phase2/workflow.json`.

---

## Step 1 — Assembly

| Git workflow mode | Assembly action |
|---|---|
| `solo_single_pr` | Single branch — no-op; working tree is already the assembled app. |
| `sprint_pr_queue` / `stacked_prs` / `parallel_wave_prs` | Merge all sprint branches onto an integration branch before booting. **NOT YET VALIDATED** for those modes — treat as a flag for A4 work. |
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

Run tests with timeout:
```bash
timeout 300 npm run test:integration 2>&1 | tee .superflow/release-gate/integration.log
INTEGRATION_EXIT=$?
```

`INTEGRATION_EXIT=0` → `integration=pass`. Non-zero → `integration=fail`.
If Docker is absent (`readiness.integration=false`) → `integration=skipped` (noted loudly).

---

## Step 6 — Run Playwright E2E headless (web only)

Tag-based execution: run the E2E suite and capture per-journey outcomes by `spec_tag`.

```bash
# Use workers=1 for determinism at gate time (parallelism during dev is fine)
timeout 300 npx playwright test --workers=1 \
  --reporter=json --output=.superflow/release-gate/pw-results.json \
  2>&1 | tee .superflow/release-gate/e2e.log
E2E_EXIT=$?
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

Parse `pw-results.json` to determine which journey `spec_tag`s passed or failed.
Journey tags appear in test titles as `@<spec_tag>` (e.g. `"user can sign in @J1-login"`).

```bash
# Extract covered (passed) spec_tags
E2E_COVERED=$(jq -c '
  [.suites[].specs[] |
    select(.tests[].status == "passed") |
    .title |
    capture("@(?P<tag>J[0-9]+-[a-z-]+)") |
    .tag // empty]
' .superflow/release-gate/pw-results.json 2>/dev/null || echo "[]")

# Extract failed spec_tags
E2E_FAILED=$(jq -c '
  [.suites[].specs[] |
    select(.tests[].status == "failed" or .tests[].status == "unexpected") |
    .title |
    capture("@(?P<tag>J[0-9]+-[a-z-]+)") |
    .tag // empty]
' .superflow/release-gate/pw-results.json 2>/dev/null || echo "[]")
```

Build `results.json` and pass it to `release-gate.sh`:
```bash
jq -cn \
  --argjson specs_ran        "$( [ "${E2E_EXIT:-1}" -lt 125 ] && echo true || echo false )" \
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

## Step 8 — Compute + persist verdict

Extract journeys from the charter `test_strategy.journeys` block and pass to the gate helper:

```bash
# Orchestrator extracts charter journeys as JSON (no YAML parsing in the helper)
CHARTER_FILE="docs/superflow/specs/$(ls docs/superflow/specs/*-charter.md 2>/dev/null | head -1)"
# journeys.json is a JSON array of {id,spec_tag,spec_path,spec_title,owning_sprint}
# Build it from the charter's YAML block using yq or paste it inline as static JSON.
# The release-gate helper receives only JSON — YAML stays in the orchestrator layer.

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

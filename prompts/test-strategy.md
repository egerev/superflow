# Test Strategy Guidance

Use this prompt to build the `test_strategy:` block for the Autonomy Charter (Phase 1, Step 13a). This block is the machine-checkable P2→P3 contract: the Phase 3 Release Gate verifies every journey ID ran green. A charter with unowned journeys, missing spec mappings, or a library project with no coverage threshold is incomplete.

---

## Inputs

| Source | Fields used |
|--------|-------------|
| `.superflow/test-env.json` | `project_type`, `readiness.unit`, `readiness.integration`, `readiness.e2e_tooling`, `readiness.recommendations` |
| Sprint plan (Step 10) | Sprint numbers for `owning_sprint` assignment |
| Product brief (Step 7) | Major user-facing flows to cover with journeys |

If `.superflow/test-env.json` is absent, default `project_type=web`, all readiness flags to `false`, and note "test-env detection not run" in the strategy narrative.

---

## Step 1 — Derive Active Levels

| `project_type` | Unit | Integration | E2E |
|---|---|---|---|
| `web` | always | when `readiness.integration=true` | when `readiness.e2e_tooling=true` |
| `backend-only` | always | when `readiness.integration=true` | never |
| `library` | always | never | never |

**Always emit all three level keys** — never omit a key regardless of project type. Use these value conventions:
- **Type-INACTIVE level** (e.g. `e2e` for library or backend-only; `integration` for library): value = `"N/A — <project_type>; <reason>"` — e.g. `"N/A — library; no browser"` or `"N/A — backend-only; no browser"`.
- **Type-APPLICABLE but not-yet-configured level** (e.g. `e2e_tooling=false` on a web project): value = `"not configured — <install command from readiness.recommendations>"`.

---

## Step 2 — Write Journeys (web projects only)

A journey captures one complete user flow from the browser's perspective.

### When to write journeys

- `project_type=web`: required. Write ≥1 journey per major user-facing flow (login, onboarding, checkout, dashboard, etc.). Identify flows from the Product Brief's "User stories" and "Jobs to be Done" sections.
- `project_type=backend-only`: set `journeys: []`. Write a concise integration acceptance note in `per_sprint_acceptance` instead.
- `project_type=library`: set `journeys: []`. Use the library path (Step 3) instead.

### Journey ID convention

- Format: `J<N>-<kebab-slug>` where N is a 1-based sequence (`J1-login`, `J2-checkout`).
- **NEVER rename a journey ID after assignment.** The Phase 3 Release Gate matches coverage reports by ID — a rename breaks the gate.
- Use verbs that name the user's goal, not the UI: `J1-create-account`, not `J1-click-signup-button`.

### Required journey fields

```yaml
- id: "J1-login"                  # stable kebab ID
  title: "Registered user signs in"  # short imperative phrase
  steps:
    - "Navigate to /login"
    - "Enter valid email and password"
    - "Click 'Sign in'"
    - "Verify redirect to /dashboard"
  expected_outcome: "User lands on /dashboard; nav shows their display name"
  spec_path: "e2e/auth.spec.ts"              # relative path from repo root
  spec_title: "registered user can sign in @J1-login"  # test title incl. spec_tag annotation
  spec_tag: "J1-login"           # equals the journey id; implementer tags the spec with this value; Release Gate matches per-journey coverage by spec_tag
  owning_sprint: 2               # positive integer (>=1) matching an existing sprint in the Step 10 plan
```

- **`steps`**: 3–7 ordered plain-English browser actions. Each step should name what the user sees or does.
- **`expected_outcome`**: one sentence; observable state after the last step.
- **`spec_path`**: the file that will contain the E2E test; may not exist yet (it is created by `owning_sprint`).
- **`spec_title`**: the `describe` block or `test` name inside `spec_path`. Include the `spec_tag` annotation in the title (e.g. `"user signs in @J1-login"`) so the Release Gate can grep per-journey coverage.
- **`spec_tag`**: equals the journey `id`. The implementer annotates the executable spec with this tag (e.g. Playwright: `test('user signs in @J1-login', ...)` or a `@J1-login` describe tag). The Release Gate matches per-journey coverage output by `spec_tag` — never by position or test count.
- **`owning_sprint`**: positive integer (≥1) matching an existing sprint in the Step 10 plan. That sprint **must** author `spec_path`. If no sprint in the plan implements this flow, the charter is incomplete — add a spec-authoring task to the plan before finalising.

### Sprint ownership rule

Each journey must be owned by exactly one sprint. The sprint's plan acceptance entry must include: `"Author <spec_path> covering journey <id>"`. A journey without this clause means the gate will report FAIL the first time it runs.

When two journeys share the same feature sprint, assign the same `owning_sprint` to both and list both spec requirements in that sprint's acceptance.

---

## Step 3 — Library Path (library projects)

Set `journeys: []` (empty, always present) and add `coverage` and `runtime_matrix`:

```yaml
coverage:
  threshold: 80                       # minimum line coverage %; adjust to project standard
  tool: "vitest --coverage (v8 provider) / pytest-cov"
runtime_matrix:
  - label: "Node 18 LTS"
    version: "18"
  - label: "Node 20 LTS"
    version: "20"
```

Derive `runtime_matrix` from:
1. The project's CI matrix (`.github/workflows/*.yml`) — use whatever is already tested.
2. `engines` field in `package.json` or `python_requires` in `pyproject.toml` — use minimum + current LTS.
3. Fallback: two most recent Node LTS versions OR Python 3.10 + 3.12.

---

## Step 4 — Write `per_sprint_acceptance`

Write a single string that tells implementers exactly what evidence to paste at sprint completion. Tailor it to the active levels and journeys:

**Web example:**
```
Sprint 1 (unit): paste vitest output — all green, no skipped tests.
Sprint 2 (integration + journey J1-login): paste Testcontainers Docker lines + playwright test e2e/auth.spec.ts output — 1 passed; confirm spec_tag "J1-login" appears in the test output.
Sprint 3 (journey J2-checkout): paste playwright test e2e/checkout.spec.ts output — 1 passed; confirm spec_tag "J2-checkout" appears in the test output.
```

**Backend-only example:**
```
Sprint 1 (unit): paste pytest output — all green.
Sprint 2 (integration): paste pytest output with Testcontainers startup lines and DB assertion logs.
```

**Library example:**
```
Each sprint: paste `vitest run --coverage` output — all green, line coverage ≥ 80%.
Final sprint: confirm CI matrix passes on Node 18 and Node 20 (link to GitHub Actions run or paste summary).
```

---

## Complete Example — Web Project

```yaml
test_strategy:
  levels:
    unit: "vitest (tests/unit/) — fast, no I/O"
    integration: "vitest + Testcontainers (tests/integration/) — requires Docker"
    e2e: "Playwright headless Chromium (e2e/) — requires app running on localhost"
  journeys:
    - id: "J1-login"
      title: "Registered user signs in"
      steps:
        - "Navigate to /login"
        - "Enter valid email and password"
        - "Click 'Sign in'"
        - "Verify redirect to /dashboard"
      expected_outcome: "User lands on /dashboard; nav shows their display name"
      spec_path: "e2e/auth.spec.ts"
      spec_title: "registered user can sign in @J1-login"
      spec_tag: "J1-login"
      owning_sprint: 2
    - id: "J2-checkout"
      title: "Guest user completes checkout"
      steps:
        - "Navigate to /shop, add one item to cart"
        - "Click 'Checkout', fill in email and card details"
        - "Click 'Place Order'"
        - "Verify order confirmation page"
      expected_outcome: "Order confirmation page shown with valid order reference"
      spec_path: "e2e/checkout.spec.ts"
      spec_title: "guest user can complete checkout @J2-checkout"
      spec_tag: "J2-checkout"
      owning_sprint: 3
  per_sprint_acceptance: "Sprint 1 (unit): paste vitest output — all green. Sprint 2 (integration + J1-login): paste Testcontainers startup lines + playwright test e2e/auth.spec.ts output — 1 passed; confirm spec_tag 'J1-login' in output. Sprint 3 (J2-checkout): paste playwright test e2e/checkout.spec.ts output — 1 passed; confirm spec_tag 'J2-checkout' in output."
```

## Complete Example — Library Project

```yaml
test_strategy:
  levels:
    unit: "vitest (src/**/*.test.ts) — all public API functions tested"
    integration: "N/A — library; no external services"
    e2e: "N/A — library; no browser"
  journeys: []
  coverage:
    threshold: 80
    tool: "vitest --coverage (v8 provider)"
  runtime_matrix:
    - label: "Node 18 LTS"
      version: "18"
    - label: "Node 20 LTS"
      version: "20"
  per_sprint_acceptance: "Each sprint: paste vitest run --coverage output — all green, line coverage >= 80%. Final sprint: confirm CI matrix runs green on Node 18 and Node 20."
```

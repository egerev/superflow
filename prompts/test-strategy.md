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
| `web` | always | when `readiness.integration=true` (`docker.present=true`) | when `readiness.e2e_tooling=true` |
| `backend-only` | always | when `readiness.integration=true` | never |
| `library` | always | never | never |

For any missing layer (e.g. `e2e_tooling=false` on a web project), write "not yet configured — [install command from `readiness.recommendations`]" as the level value. Do NOT silently skip it; document the gap so implementers know what to install.

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
- id: "J1-checkout"               # stable kebab ID
  title: "Guest user completes checkout"  # short imperative phrase
  steps:
    - "Navigate to /shop, add one item to cart"
    - "Click 'Checkout', fill in email and card details"
    - "Click 'Place Order'"
    - "Verify order confirmation page and reference number"
  expected_outcome: "Order confirmation page shown with a valid order reference"
  spec_path: "e2e/checkout.spec.ts"          # relative path from repo root
  spec_title: "guest user can complete checkout"  # test/describe title inside that file
  owning_sprint: 3                           # sprint from Step 10 that authors spec_path
```

- **`steps`**: 3–7 ordered plain-English browser actions. Each step should name what the user sees or does.
- **`expected_outcome`**: one sentence; observable state after the last step.
- **`spec_path`**: the file that will contain the E2E test; may not exist yet (it is created by `owning_sprint`).
- **`spec_title`**: the `describe` block or `test` name inside `spec_path` that covers this journey. Used by the Release Gate to match coverage output.
- **`owning_sprint`**: the sprint that **must** author `spec_path`. If no sprint in the plan implements this flow, the charter is incomplete — add a spec-authoring task to the plan before finalising.

### Sprint ownership rule

Each journey must be owned by exactly one sprint. The sprint's plan acceptance entry must include: `"Author <spec_path> covering journey <id>"`. A journey without this clause means the gate will report FAIL the first time it runs.

When two journeys share the same feature sprint, assign the same `owning_sprint` to both and list both spec requirements in that sprint's acceptance.

---

## Step 3 — Library Path (library projects)

Replace the `journeys` list with `coverage` and `runtime_matrix`:

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
Sprint 2 (integration): paste vitest output with Testcontainers Docker lines visible.
Sprint 3 (journey J1-checkout): paste `playwright test e2e/checkout.spec.ts` output — 1 passed; confirm "J1-checkout" appears in the test title or tag.
Sprint 3 (journey J2-login): paste `playwright test e2e/auth.spec.ts` output — 1 passed; confirm "J2-login" appears in the test title or tag.
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
      expected_outcome: "User lands on /dashboard; nav shows their name"
      spec_path: "e2e/auth.spec.ts"
      spec_title: "registered user can sign in"
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
      spec_title: "guest user can complete checkout"
      owning_sprint: 3
  per_sprint_acceptance: "Sprint 1 (unit): paste vitest output — all green. Sprint 2 (integration + J1-login): paste Testcontainers startup lines + playwright test e2e/auth.spec.ts output — 1 passed. Sprint 3 (J2-checkout): paste playwright test e2e/checkout.spec.ts output — 1 passed."
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

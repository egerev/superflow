# Roadmap — Testing Infrastructure + Release Gate + Architecture Review

- **Status:** PLANNING (roadmap drafted, awaiting Wave A kickoff)
- **Created:** 2026-06-30
- **Owner:** egerev
- **Source of truth:** this file. Update the Status Tracker (§7) as stages complete so progress survives `/clear` and context compaction.

---

## 1. Why

Cut post-implementation bugs by hardening **both ends** of the Superflow pipeline:
- **Design-time rigor** — decide *how it will be tested* and *whether the architecture holds* before code is written.
- **Release-time verification** — spin up the *assembled* system and actually run integration + browser E2E, autonomously, before the final merge.

Today testing lives only inside individual sprints (TDD + per-sprint evidence). There is no upfront test strategy, no whole-system runtime gate, and no dedicated architecture review. This roadmap adds those.

## 2. Pillars (scope)

| # | Pillar | Where it plugs in | Wave |
|---|--------|-------------------|------|
| **P0** | Test-infra **detection & setup** + readiness gate | Phase 0 (onboarding) | A |
| **P2** | Design-time **Test Strategy** artifact | Phase 1 (discovery) → Charter | A |
| **P3** | **Release Gate** — Docker integration + headless browser E2E on the assembled system | new stage between Phase 2 and Phase 3 | A |
| **P1** | **Architecture big-picture review** gate with rework loop | Phase 1 (after plan review) | B |

The pillars connect: P2's critical user journeys **become** P3's E2E scenarios; P0 guarantees the infra P3 needs exists; P1 keeps the design testable.

## 3. Research synthesis (verified 2026-06-30)

Deep-research run: 6 angles → 27 sources → 128 claims → 25 adversarially verified (22 confirmed, 3 killed). Tier-1 sources: `playwright.dev`, `nextjs.org`, `node.testcontainers.org`, `testcontainers.com`, Docker Hub (Microsoft). **Preserve this — it is the factual basis for the design.**

**Default stack (Superflow's engineering choice, not an upstream mandate):**
- **Browser/E2E → Playwright.** Headless by default (no Xvfb/flag on Linux), official versioned Docker images for Node *and* Python, built-in `webServer` app-startup, one API across Chromium/Firefox/WebKit. **Detect & respect an existing Cypress setup — do not override it.**
- **Containerized integration → Testcontainers** (Node out-of-the-box; Python `pip install pytest testcontainers[postgres] <driver>`).
- **Unit/integration runners → pytest** (Python), **Vitest/Jest** (JS/TS).

**Phase-0 install (idempotent):**
- JS: `npx playwright install --with-deps chromium`
- Python: `pip install playwright && playwright install --with-deps`
- ⚠️ `--with-deps` OS-dependency part is **Debian/Ubuntu + sudo only** — no-op/fails on macOS/Alpine/RHEL → fall back to `playwright install` (binaries only). Detect distro + sudo first.
- **Readiness probe (machine-checkable, no download):** `npx playwright install --list` → exit 0 + lists browsers.

**Release-gate app startup (headless, autonomous):** Playwright `webServer` — `command: "npm run build && npm run start"`, polls `url` until it returns 2xx/3xx/400/401/402/403. Since v1.42 the probe is **HEAD** → may need a health endpoint. `reuseExistingServer: !process.env.CI`.

**Apple Silicon / "Apple Docker":** only **Docker Desktop** is zero-config. **Colima / Rancher / Podman** need `export DOCKER_HOST=…` **and** `export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (Colima: `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`; rootless Podman also `TESTCONTAINERS_RYUK_DISABLED=true`). Phase-0 must **detect the runtime and emit these exports**.

**Cleanup / flake / determinism:**
- **Ryuk** reaper auto-removes containers at process shutdown (incl. Python). Keep our canon: `TESTCONTAINERS_RYUK_DISABLED` only when `CI===true`; prefer Ryuk **enabled** + our label-based `cleanup-testcontainers.sh` as backstop.
- Autonomous runs: **`workers: 1`** (CI docs recommend 1 for stability/reproducibility); scale via **sharding**, not raw workers.
- **Docker image pinning is HARD:** `mcr.microsoft.com/playwright:v<X>-noble` (Node) / `mcr.microsoft.com/playwright/python:v<X>-noble` (Python) — the tag MUST equal the project's Playwright version or browsers aren't found. The image bundles browsers+deps+Xvfb, NOT the `@playwright/test`/pip package (install separately at the same version).

**Per-project minimal stack:**
- **JS/TS web:** Vitest/Jest (unit) + Playwright (E2E via `webServer`) + Testcontainers-node (integration).
- **Python web:** pytest (unit/integration) + Testcontainers-python + Playwright-python (E2E).
- **Library (no UI):** unit runner only — **no browser/E2E, no Docker**; release-gate browser phase skipped.

**3 myths the research killed (do NOT bake in):**
1. Next.js does *not* officially mandate Playwright over Cypress — both are documented equally (our default is a choice).
2. `--ipc=host` for Chromium-in-Docker is a *recommended reliability flag*, not a hard requirement.
3. Python Testcontainers *does* have Ryuk auto-cleanup — no mandatory manual `stop()`.

## 4. Locked decisions

- First wave = **P0 + P2 + P3**; architecture review (P1) = **Wave B**.
- Default E2E = **Playwright**; detect & respect existing Cypress.
- **Contract/API testing** (Pact / schemathesis): **detect-only** for now (use if already present); not imposed.
- **Libraries** in the release gate: **skip browser/Docker**; require a **coverage threshold + runtime-version matrix** instead.
- **Non-Debian / no-sudo sandboxes:** rely on the **official Playwright Docker image** (no per-distro package map).
- **Priority target stacks:** **Next.js** + **FastAPI** (others auto-detected, but optimize docs/templates for these two).

## 5. Execution plan

### Wave A — Testing system (P0 + P2 + P3) — one superflow run
- **Sprint A1 — Phase-0 test-env detection & readiness gate.** Detect docker + runtime (Desktop/Colima/Podman → emit env exports), node + JS runners, python + pytest, Playwright + `install --list`; write `.superflow/test-env.json`; readiness probe (tools present + browsers listed + smoke `webServer` start); recommendations into CLAUDE.md. Debian/sudo branch for `--with-deps`.
- **Sprint A2 — Design-time Test Strategy artifact.** Phase 1 produces a Test Strategy (levels: unit/integration/E2E; **critical user journeys**; per-sprint acceptance criteria) into the Charter/spec. Library path = coverage targets + version matrix. These journeys are the contract for A3.
- **Sprint A3 — Release Gate stage (between Phase 2 and Phase 3).** Assemble all sprints onto an integration branch; `webServer` boots the prod build and waits on a health URL; run integration (Testcontainers) + E2E (Playwright headless, `workers:1`); capture trace/video/screenshots as machine-checkable evidence; conditional by project type (library → skip browser/Docker); Docker-image version pinning; timeout/cleanup hygiene.
- **Sprint A4 — Wiring + enforcement + docs.** Connect A2 journeys → A3 scenarios; enforcement rules (new gate is mandatory when runnable); update `webapp-testing` skill integration; CHANGELOG / llms.txt / CLAUDE.md; tests + evidence.

### Wave B — Architecture review (P1) — second superflow run
- **Sprint B1 — Architecture reviewer role + gate.** New deep "architecture-lens" reviewer (big-picture: module boundaries, data flow, integration points, scalability, testability, tech-debt) in Phase 1 after plan review, with a **rework loop** back to the replanner when it flags structural issues.
- **Sprint B2 — Wiring + docs.** Governance thresholds (when the gate is required), enforcement rules, dispatch patterns (Claude + Codex), CHANGELOG / docs.

## 6. Open questions / deferred (from research `openQuestions`)

1. **Non-Debian OS-dependency fallback** beyond "use the Docker image" — per-distro package recipe if ever needed.
2. **Ryuk substitute on `kill -9`** for rootless Podman/Colima (where Ryuk is disabled) — is the label-based helper enough across crashes?
3. **Contract testing depth** (Pact / schemathesis / consumer-driven) — if/when to add a layer between unit and full E2E.
4. **Library-type release-gate evidence** — exact coverage threshold and version matrix to require in place of E2E.

## 7. Status Tracker

- [x] Roadmap approved
- [x] Wave A — Phase 1 discovery + spec/charter (governance=standard, git=solo_single_pr; spec+plan passed 2-round dual-model review, vacuous-gate blocker closed; charter generated)
- [ ] Wave A — Sprint A1 (Phase-0 detection)  ← in progress
- [ ] Wave A — Sprint A2 (Test Strategy artifact)
- [ ] Wave A — Sprint A3 (Release Gate)
- [ ] Wave A — Sprint A4 (wiring + docs)
- [ ] Wave A — merged
- [ ] Wave B — Phase 1 discovery + spec/charter
- [ ] Wave B — Sprint B1 (architecture reviewer + gate)
- [ ] Wave B — Sprint B2 (wiring + docs)
- [ ] Wave B — merged

<!-- updated-by-superflow:2026-06-30 -->

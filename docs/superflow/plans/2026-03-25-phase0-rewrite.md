# Phase 0 Rewrite — Implementation Plan

References: [Brief](../specs/2026-03-25-phase0-rewrite-brief.md) | [Spec](../specs/2026-03-25-phase0-rewrite-design.md)

## Summary

Split `references/phase0-onboarding.md` (1,395 lines) into a thin router + 5 stage files + greenfield file. Update all cross-references. No behavior changes to Phase 1/2/3 or supervisor.

## Sprint Breakdown

### Sprint 1: All Stage Files + Greenfield + Schema

**Branch:** `feat/phase0-rewrite-sprint-1`
**Deliverables:** 5 stage files, greenfield file, updated state schema
**Dependencies:** None (all new files, additive — old router remains functional)

| # | Task | Files | Details |
|---|------|-------|---------|
| 1 | Create `references/phase0/` directory | `references/phase0/` | — |
| 2 | Write `stage1-detect.md` | `references/phase0/stage1-detect.md` (~100 lines) | Parallel preflight ($PREFLIGHT dict), auto-detection (stack, team size, CI, PM, formatters), confirmation flow (Confirm / Correct / Skip Phase 0), greenfield routing → load `greenfield.md`, state init with $PREFLIGHT persistence |
| 3 | Write `stage2-analysis.md` | `references/phase0/stage2-analysis.md` (~100 lines) | 5 parallel agents: Architecture=Opus deep-analyst, Code Quality=Opus deep-analyst, Security=Opus deep-analyst or Codex, DevOps=Sonnet fast-implementer (mechanical checks), Documentation=Opus deep-analyst (prevents framework hallucination). All receive $PREFLIGHT. Output: internal evidence bundle |
| 4 | Write `stage3-report.md` | `references/phase0/stage3-report.md` (~100 lines) | Health report → `docs/superflow/project-health-report.md`. Informative summary (~15 lines): stack + evidence, ALL security issues, top 3 other findings, tech debt, setup preview. Permission preview with tradeoff explanation. 3-path approval: Approve all / Customize (checklist) / Skip setup. **Approval persists to state** as `context.approval` = {mode: "all"\|"custom"\|"skip", items: [...]} for Stage 4 consumption |
| 5 | Write `stage4-setup.md` | `references/phase0/stage4-setup.md` (~140 lines) | 3 concurrent branches with strict file ownership: Branch A (Opus deep-doc-writer) = llms.txt + CLAUDE.md; Branch B (Sonnet) = permissions + hooks (2-stage verification: binary exists + single-file test); Branch C (Sonnet) = /verify + CLAUDE.local.md + enforcement + .gitignore. **Execution matrix by approval mode:** "Approve all" → all 3 branches; "Customize" → Branch A always + user-selected from B/C; "Skip setup" → Branch A only (docs), skip B+C; "Greenfield rejoin" → skip Branch A (docs created in G5), run B+C. **Idempotency:** each branch checks if its artifacts exist before writing — safe to rerun on crash recovery |
| 6 | Write `stage5-completion.md` | `references/phase0/stage5-completion.md` (~50 lines) | Write markers in all touched files, persist tech_debt to `.superflow-state.json` context, update state to phase=1 stage=research, informative summary (5-8 lines), clear restart instruction: "/clear then /superflow" |
| 7 | Extract greenfield path | `references/phase0/greenfield.md` (~280 lines) | Extract from `phase0-onboarding.md` section "## Greenfield Path (Steps G1-G6)" through end of G6 (before "## Step 2"). Add header: loaded by Stage 1 when empty/near-empty project detected. Specify rejoin: after G6 → Stage 4 (skipping Branch A). Verify extracted content matches original — diff line counts |
| 8 | Update state schema | `templates/superflow-state-schema.json` | Add to `context.properties`: `preflight` object (stack, team_size, ci, python3, pm, formatters — all strings), `tech_debt` object (total_todos: integer, files_over_500_loc: array of strings, untested_modules: array of strings, security_issues: integer, generated_at: date-time string) |

**Commit:** `feat: add Phase 0 stage files, greenfield extraction, and schema update`

---

### Sprint 2: Router Rewrite + Reference Updates + Verification

**Branch:** `feat/phase0-rewrite-sprint-2`
**Deliverables:** Rewritten router, all references updated, verification complete
**Dependencies:** Sprint 1 (all stage files must exist)

| # | Task | Files | Details |
|---|------|-------|---------|
| 1 | Rewrite `phase0-onboarding.md` as thin router | `references/phase0-onboarding.md` (1395 → ~80 lines) | Detection logic (markers + partial completion), stage→file mapping table, state-based resume (read stage_index → load correct stage file). **Recovery matrix:** (a) no markers + no state → full Phase 0 from Stage 1; (b) no markers + state.stage_index=N → resume from Stage N+1; (c) markers in CLAUDE.md only + no llms.txt marker → partial: Stage 4 Branch A only; (d) all markers + no health report → partial: Stage 3 only; (e) all markers + all artifacts → skip Phase 0; (f) markers exist + state.stage_index=3 (Stage 4 crash) → rerun Stage 4 (idempotent branches). Keep same path for backward compat |
| 2 | Update `SKILL.md` | `SKILL.md` | Phase 0 summary: replace "Mini-interview (AskUserQuestion)" with "Auto-detect + confirm". Architecture tree: add `phase0/` subtree (6 files). Phase references: add stage file paths |
| 3 | Update `CLAUDE.md` | `CLAUDE.md` | Architecture diagram: add `phase0/` directory with files. File table: add new files, update phase0-onboarding.md line count (1395 → ~80). Update overview description |
| 4 | Update `llms.txt` | `llms.txt` | Phase 0 file structure entry: add stage files, update description |
| 5 | Update `README.md` | `README.md` | Phase 0 description: "Auto-detection + parallel agents" instead of "Mini-interview". Verify no broken anchors to old step numbers |
| 6 | Verify `superflow-enforcement.md` | `superflow-enforcement.md` | Confirm Phase 0 Gate ref (`references/phase0-onboarding.md`) still valid (router keeps same path). No changes expected — verification only |
| 7 | Cross-reference verification | — | `grep -r 'phase0-onboarding' .` — verify all hits are updated or router-compatible. `grep -r 'Step 1.5\|Step 2:\|Step 3.5' .` — verify old step numbers removed from non-spec files. Verify each stage file is loadable (Read each, confirm no broken refs) |

**Commit:** `feat: rewrite Phase 0 router and update all cross-references`

---

## Merge Order

```
Sprint 1 → Sprint 2
```

Sprint 1 is additive (new files alongside working old router). Sprint 2 flips the switch.

## Verification Matrix

After Sprint 2, manually verify these paths work correctly:

| Path | What to check |
|------|---------------|
| Fresh project (no markers) | Router detects first run → loads stage1-detect → proceeds through all 5 stages |
| Partial completion (markers in CLAUDE.md only) | Router detects partial → resumes at correct stage |
| State-based resume (stage_index=2, crash recovery) | Router reads state → loads stage3-report |
| Skip Phase 0 (user chooses "Skip" at Stage 1) | Writes markers with defaults → proceeds to Phase 1 |
| Greenfield (empty repo) | Stage 1 detects → loads greenfield.md → after G6 rejoins Stage 4 (skips Branch A) |
| Customize approval (Stage 3) | User selects items → Stage 4 only executes approved items per execution matrix |
| Skip setup approval (Stage 3) | Only Branch A runs (docs), B+C skipped. Permissions/hooks not configured |
| Stage 4 partial crash (Branch A done, C failed) | Router reruns Stage 4 — idempotent branches skip existing artifacts, retry failed ones |
| Markers exist but no state file | Router uses artifact-based detection (existing behavior), not stage_index |
| All markers present | Router skips Phase 0 → proceeds to Phase 1 |

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Old router stays functional during Sprint 1 | New files are additive; router unchanged until Sprint 2 |
| Greenfield extraction misses content | Diff original section vs extracted file; verify G1-G6 all present |
| Cross-references broken after Sprint 2 | Grep for old step numbers and phase0-onboarding refs; verification task #7 |
| Stage files inconsistent with spec | Each stage file content reviewed against corresponding spec section during PR review |
| Greenfield overwrites docs at Stage 4 | Stage 4 file explicitly notes: greenfield path skips Branch A |
| State schema drift | Schema includes typed fields for preflight + tech_debt; matches spec examples |

## Total

- **2 sprints**, **15 tasks**
- **2 PRs** (one per sprint)
- **~7 new files**, **~6 modified files**, **1 rewritten file**

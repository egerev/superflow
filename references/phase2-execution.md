# Phase 2: Autonomous Execution — DAG Router

> **Source of truth:** `references/phase2/workflow.json` (DAG + decision matrix)
> **Always-loaded context:** `references/phase2/overview.md`
> **Step details:** `references/phase2/steps/*.md` (load on-demand per stage)
>
> **Backward compat:** If `references/phase2/` is missing, restore this file from git history
> (pre-Sprint-2 commits contain the full prose-driven flow).

---

## Orchestrator Loading Procedure (per sprint)

1. **Read `references/phase2/workflow.json` once** — parse stage sequence, step-file map, and
   `decision_matrix.review_config[governance_mode+"+"+complexity]` to get reviewer count, tier,
   and `par_skip_product` for this sprint.
2. **Read `references/phase2/overview.md` once** — wave analysis rules, model selection table,
   orchestrator tool budget reminder.
3. **Determine current stage** from `heartbeat.phase2_step` in `.superflow-state.json`
   (falls back to `state.stage` for backward compat with v4.8 state files).
4. **Load step detail files on-demand** — use `workflow.json` → `step_files[step_id]` to find
   the right file in `references/phase2/steps/`. Read it only when entering that step.

## Stage Sequence

`setup` → `implementation` → `review` → `docs` → `par` → `ship`

Defined in full in `workflow.json` → `stages[]`. Step files (all in `references/phase2/steps/`):

| Step | File |
|------|------|
| Re-read / heartbeat | `setup-reread.md` |
| Worktree creation | `setup-worktree.md` |
| Implementer dispatch + wave analysis | `impl-dispatch.md` |
| Unified review (product + technical) | `review-unified.md` |
| PAR evidence gate | `par-evidence.md` |
| Push, PR creation, CI wait, cleanup | `ship-pr.md` |
| Compaction recovery | `compaction-recovery.md` |
| Holistic review (conditional) | `holistic-review.md` |

# Step: setup-worktree

**Stage:** setup
**Loaded by orchestrator:** when entering the worktree creation step
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Verify Gitignore First

Before creating any worktree, confirm `.worktrees/` is gitignored:

```bash
git check-ignore -q .worktrees || echo '.worktrees/' >> .gitignore
```

If `.gitignore` was updated, commit it before continuing.

## Worktree Creation by git_workflow_mode

Read `context.git_workflow_mode` from `.superflow-state.json`.

**`sprint_pr_queue` (default) / `stacked_prs` / `parallel_wave_prs`:**
```bash
git worktree add .worktrees/sprint-N feat/<feature>-sprint-N
```
One worktree per sprint. Branch name: `feat/<feature>-sprint-N`.

**`solo_single_pr`:**
```bash
git worktree add .worktrees/feat-<feature> feat/<feature>
```
One worktree for the entire run. All sprints commit to the same branch.

**`trunk_based`:**
```bash
git worktree add .worktrees/sprint-N feat/<feature>-sprint-N
```
Short-lived branch per deployable slice; merge frequently. Same creation command as `sprint_pr_queue`.

**`parallel_wave_prs`:**
Multiple worktrees created concurrently — one per sprint in the current wave:
```bash
git worktree add .worktrees/sprint-1 feat/<feature>-sprint-1
git worktree add .worktrees/sprint-2 feat/<feature>-sprint-2
# ... dispatched simultaneously for parallel sprint agents
```

## After Creation

Verify the worktree exists: `ls .worktrees/`
All implementation work happens inside the worktree directory — never in the main repo root.

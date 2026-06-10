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

Read `context.git_workflow_mode` from `.superflow-state.json`, then use the matching command:

### `solo_single_pr` — one branch for the entire run
```bash
# Sprint 1 only — create the single feature branch from main:
git worktree add -b feat/<feature> .worktrees/<feature> origin/main
# Subsequent sprints: worktree already exists; commit directly to feat/<feature>.
```
Branch name: `feat/<feature>`. Base: `origin/main`. One PR at end of run.

### `sprint_pr_queue` — independent sprints off main, sequential PRs
```bash
git worktree add -b feat/<feature>-sprint-N .worktrees/sprint-N origin/main
```
Branch name: `feat/<feature>-sprint-N`. Base: `origin/main`. One PR per sprint.

### `stacked_prs` — each sprint branches from the previous sprint's branch
```bash
# Sprint 1 — base is main:
git worktree add -b feat/<feature>-sprint-1 .worktrees/sprint-1 origin/main

# Sprint 2 — base is Sprint 1's branch:
git worktree add -b feat/<feature>-sprint-2 .worktrees/sprint-2 feat/<feature>-sprint-1

# Sprint 3 — base is Sprint 2's branch:
git worktree add -b feat/<feature>-sprint-3 .worktrees/sprint-3 feat/<feature>-sprint-2
```
Branch base: previous sprint's local branch (not `origin/main`). One PR per sprint.
Stacked PRs do NOT auto-retarget — see `ship-pr.md` § "Stack rebase and retarget after parent merges" for the explicit `git rebase origin/main` + `gh pr edit --base main` procedure that must run after each parent sprint merges.

### `parallel_wave_prs` — independent branches off main, dispatched in parallel waves
```bash
# All wave sprints created simultaneously:
git worktree add -b feat/<feature>-sprint-N .worktrees/sprint-N origin/main
```
Branch name: `feat/<feature>-sprint-N`. Base: `origin/main`. One PR per sprint, merged in order.

### `trunk_based` — short-lived slice branches off main
```bash
git worktree add -b feat/<feature>-slice-N .worktrees/slice-N origin/main
```
Branch name: `feat/<feature>-slice-N`. Base: `origin/main`. Merge each slice frequently.

## Opt-In Alternative: `Agent(isolation: "worktree")` — Claude Runtime Only

The bash choreography above is the DEFAULT (Codex parity — both runtimes share the same commands).
On Claude runtime, `Agent(isolation: "worktree")` may be used as an opt-in alternative: the
harness creates a disposable worktree for the subagent automatically.

**Caveat:** the auto-created branch name and base are harness-chosen. Before relying on such a
worktree for push/PR flows, verify the branch name and base match the `git_workflow_mode` contract
above (e.g. `feat/<feature>-sprint-N` off `origin/main` for `sprint_pr_queue`). If they don't
match, fall back to the bash choreography.

## After Creation

Verify the worktree exists: `ls .worktrees/`

All implementation work happens inside the worktree directory — never in the main repo root.

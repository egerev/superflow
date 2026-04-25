# Step: ship-pr

**Stage:** ship
**Loaded by orchestrator:** when entering the ship stage
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Pre-Ship Gate

Verify `.par-evidence.json` exists with all verdicts passing before proceeding.
`gh pr create` is BLOCKED until evidence is confirmed (see `par-evidence.md`).

## PR Policy by git_workflow_mode

| Mode | Branch pushed | PR `--base` | When to open PR |
|------|--------------|------------|-----------------|
| `solo_single_pr` | `feat/<feature>` | `main` | Once, after final sprint |
| `sprint_pr_queue` | `feat/<feature>-sprint-N` | `main` | Each sprint |
| `stacked_prs` | `feat/<feature>-sprint-N` | `feat/<feature>-sprint-(N-1)` (Sprint 1 → `main`) | Each sprint; retargets to `main` when prior sprint merges |
| `parallel_wave_prs` | `feat/<feature>-sprint-N` | `main` | Each sprint |
| `trunk_based` | `feat/<feature>-slice-N` | `main` | Each slice |

## Push and Create PR

### `solo_single_pr`
```bash
# Only after ALL sprints complete:
git push -u origin feat/<feature>
gh pr create --base main --title "<feature>: [summary]" --body "..."
```

### `sprint_pr_queue` / `parallel_wave_prs`
```bash
git push -u origin feat/<feature>-sprint-N
gh pr create --base main --title "Sprint N: [title]" --body "..."
```

### `stacked_prs`
```bash
# Sprint 1 — base is main:
git push -u origin feat/<feature>-sprint-1
gh pr create --base main --title "Sprint 1: [title]" --body "..."

# Sprint N (N > 1) — base is previous sprint's branch:
git push -u origin feat/<feature>-sprint-N
gh pr create --base feat/<feature>-sprint-$(( N - 1 )) --title "Sprint N: [title]" --body "..."
# Note: GitHub auto-retargets this PR to main once the prior sprint merges.
```

### `trunk_based`
```bash
git push -u origin feat/<feature>-slice-N
gh pr create --base main --title "Slice N: [title]" --body "..."
```

Include in every PR body: description, link to `.par-evidence.json` verdicts, test evidence summary.

## Wait for CI Green

After `gh pr create`, run:
```bash
gh run list --limit 5
```

Wait for CI to go green. If CI fails:
1. `gh run view <id> --log-failed` — read the failure
2. Fix the issue, push, wait for green
3. NEVER use `gh pr merge --admin` to bypass CI

**Branch protection is there for a reason. Fix CI first, then merge.**

## Verify PR Created

```bash
gh pr view <branch-name>
```

Must return PR data (number, URL, status). If command errors, PR was not created — retry `gh pr create`.

## Cleanup Worktree

Only after the PR is created AND verified:
```bash
git worktree remove .worktrees/sprint-N   # or slice-N / feat-<feature>
```

Do NOT remove the worktree before the PR is created — the branch must exist to push to.
Do NOT remove the worktree before merging if still making fixes.

## Telegram Update

If MCP connected: `"Sprint N complete. PR #NNN created."` Then proceed to next sprint.

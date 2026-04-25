# Step: ship-pr

**Stage:** ship
**Loaded by orchestrator:** when entering the ship stage
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Pre-Ship Gate

Verify `.par-evidence.json` exists with both verdicts passing before proceeding.
`gh pr create` is blocked until evidence is confirmed (see `par-evidence.md`).

## Push and Create PR

```bash
git push -u origin feat/<feature>-sprint-N
gh pr create --base main --title "Sprint N: [title]" --body "..."
```

Include in PR body: PR description, link to `.par-evidence.json` verdicts, test evidence summary.

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
gh pr view feat/<feature>-sprint-N
```

Must return PR data (number, URL, status). If command errors, PR was not created — retry `gh pr create`.

## Cleanup Worktree

Only after the PR is created AND verified:
```bash
git worktree remove .worktrees/sprint-N
```

Do NOT remove the worktree before the PR is created — the branch must exist to push to.
Do NOT remove the worktree before merging if still making fixes.

## Telegram Update

If MCP connected: `"Sprint N complete. PR #NNN created."` Then proceed to next sprint.

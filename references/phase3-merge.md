# Phase 3: Merge (USER-INITIATED)

Triggered when user says "merge", "мёрдж", or approves merge after the Completion Report.

## Pre-Merge Checklist

Before merging any PR:
1. **CI must pass** on all PRs — check with `gh pr checks <number>`
2. **No unresolved review comments** — check with `gh pr view <number>`
3. **CLAUDE.md is up to date** — update with new modules, files, conventions from this session
4. **BACKLOG.md is up to date** — mark completed items, add discovered items

## Merge Order

PRs merge sequentially in sprint order (Sprint 1 first, then Sprint 2, etc.):

```
for each PR in sprint order:
  1. gh pr checks <number> — verify CI green
  2. git checkout main && git pull
  3. gh pr merge <number> --rebase --delete-branch
  4. If conflict:
     a. git checkout <branch>
     b. git rebase main
     c. Fix conflicts
     d. git push --force-with-lease
     e. Wait for CI, then merge
  5. Verify merge succeeded
```

## Rules

- **Rebase strategy**: always `--rebase` to keep linear history
- **Delete branch after merge**: `--delete-branch`
- **One at a time**: merge sequentially, never parallel
- **CI gate**: never merge with failing checks — fix first
- **Conflict resolution**: rebase onto latest main, fix conflicts, force-push with lease, wait for CI
- **Worktree cleanup**: after all PRs merged, `git worktree prune`

## Documentation Update (pre-merge)

Before the first merge, commit documentation updates to the last sprint branch:
1. Update `CLAUDE.md` with new/changed modules, files, conventions
2. Update `BACKLOG.md` with completed and discovered items
3. Push the doc update, wait for CI

## Post-Merge Report

After all PRs are merged:

```
## Merge Complete

- Merged: PR #X, #Y, #Z (in order)
- All CI checks: passed
- Documentation: updated
- Branches: cleaned up
- Worktrees: pruned
```

Send via Telegram if MCP connected.

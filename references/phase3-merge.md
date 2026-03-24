# Phase 3: Merge (USER-INITIATED)

Triggered when user says "merge", "мёрдж", "мерж", or gives clear affirmative response (e.g., "go ahead", "do it", "yes") after the Completion Report.

## Stage Structure

Phase 3 has 3 stages. Use TaskCreate at each stage start, TaskUpdate as todos complete.

```
Stage 1: "Pre-merge"
  Todos:
  - "CI check on all PRs"
  - "Review comments check"
  - "Update CLAUDE.md"
  - "Update llms.txt"

Stage 2: "Merge"
  Todos (one per PR, dynamic):
  - "Merge PR #N (Sprint K: [title])"

Stage 3: "Post-merge"
  Todos:
  - "Sync local main"
  - "Prune worktrees"
  - "Clean artifacts"
  - "Generate post-merge report"
  - "Send Telegram report"
```

### State Management

At the start of Phase 3, write `.superflow-state.json`:
```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":3,"phase_label":"Merge","stage":"pre-merge","stage_index":0,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
```

After each stage transition, update via python3:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s['stage']='merge'; s['stage_index']=1; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```

### TaskCreate/TaskUpdate Pattern

```
# At the beginning of Stage 1:
TaskCreate(
  title: "Phase 3: Pre-merge",
  description: "CI checks, review comments, doc updates",
  todos: [
    "CI check on all PRs",
    "Review comments check",
    "Update CLAUDE.md",
    "Update llms.txt"
  ]
)

# As each todo completes:
TaskUpdate(id: <task_id>, todo_updates: [
  {index: 0, status: "completed"}
])

# When stage completes:
TaskUpdate(id: <task_id>, status: "completed")

# Stage 2 — dynamic todos based on PR count:
TaskCreate(
  title: "Phase 3: Merge",
  description: "Sequential rebase merge of all PRs",
  todos: [
    "Merge PR #42 (Sprint 1: Interactive Onboarding)",
    "Merge PR #43 (Sprint 2: Stages + State)",
    ...
  ]
)
```

---

## Pre-Merge Checklist
<!-- Stage 1: Pre-merge -->

Before merging any PR:
1. **CI must pass** on all PRs — check with `gh pr checks <number>`
2. **No unresolved review comments** — check with `gh pr view <number>`
3. **CLAUDE.md is up to date** — audit against current codebase:
   - New files/modules added during this session are documented
   - New commands (build/test/lint) are listed
   - Removed or renamed files are cleaned up
   - Use `prompts/claude-md-writer.md` for conventions

## Documentation Update (pre-merge)
<!-- Stage 1: Pre-merge, Todos 3-4 -->

Before the first merge, create a dedicated documentation commit on the last sprint branch:
1. Update `CLAUDE.md` with new/changed modules, files, conventions
2. Update `llms.txt` if project structure changed
3. Push the doc update, wait for CI to pass again

> **Reasoning:** Dispatch doc update agents with `subagent_type: "standard-doc-writer"` (opus, effort: medium). Lower than Phase 0's deep tier because Phase 3 is incremental update, not first-time generation.

## Pre-Merge: Exit Worktree

**CRITICAL:** Merge MUST happen from the main repo root, NOT from a worktree. Worktree CWD dies when the branch is deleted.

```
# 1. Exit worktree BEFORE merging
cd <main-repo-root>  # e.g., cd /path/to/project (NOT .worktrees/sprint-N)

# 2. Remove worktrees for branches about to be merged
git worktree remove .worktrees/sprint-N 2>/dev/null
git worktree prune
```

If CWD is already inside a worktree, ALL subsequent commands will fail with "Path does not exist" after `--delete-branch` removes the branch. This is unrecoverable within the same shell.

## Merge Order
<!-- Stage 2: Merge -->

Use the PR list and merge order from the Phase 2 Completion Report. If the report is unavailable (context compaction), enumerate open PRs: `gh pr list --state open --author @me --json number,title,headRefName --jq 'sort_by(.number)'`

PRs merge sequentially in sprint order (Sprint 1 first, then Sprint 2, etc.):

```
for each PR in sprint order:
  0. Check PR state: `gh pr view <number> --json state -q '.state'`
     - If "MERGED": skip, log as already merged
     - If "CLOSED": warn user, skip
     - If "OPEN": proceed with merge
  1. gh pr checks <number> — verify CI green
  2. gh pr merge <number> --rebase --delete-branch
  3. If merge fails due to conflict:
     a. git fetch origin main
     b. git checkout <branch>
     c. git rebase origin/main
     d. Fix conflicts, commit
     e. git push --force-with-lease  # Safe: required after rebase
     f. Wait for CI, then retry step 2
  4. Verify: `gh pr view <number> --json state -q '.state'` must return "MERGED"
  5. git pull origin main  # sync local main
```

## Rules

- **Rebase strategy**: always `--rebase` to keep linear history
- **Delete branch after merge**: `--delete-branch`
- **One at a time**: merge sequentially, never parallel
- **CI gate**: never merge with failing checks — fix first (see CI Failure below)
- **Force-push after rebase is approved**: `git push --force-with-lease` is the standard post-rebase push and is explicitly permitted in Phase 3 conflict resolution
- **Worktree cleanup**: BEFORE merge, not after. Remove worktrees for branches about to be merged, then `git worktree prune`
- **Artifact cleanup**: after all PRs merged, remove `.par-evidence.json` from the working directory (if present). Do NOT commit removal — these are ephemeral gate artifacts.

## CI Failure During Merge

If `gh pr checks <number>` shows failing checks:
1. Identify the failing check: `gh pr checks <number>`
2. Check out the branch: `git checkout <branch>`
3. Diagnose: read CI logs, reproduce locally if possible
4. Fix, commit, push
5. Wait for CI to pass (poll `gh pr checks <number>`, max 5 minutes)
6. If CI still fails after 2 fix attempts: stop and report to user with error details
7. Resume merge sequence from the failed PR

## Post-Merge Report
<!-- Stage 3: Post-merge -->

After all PRs are merged:

```
## Merge Complete

- Merged: PR #X (Sprint 1: [title]), #Y (Sprint 2: [title]), #Z (Sprint 3: [title])
- All CI checks: passed
- Tests: [total passed/failed/skipped across all sprints]
- Documentation: updated (CLAUDE.md, llms.txt)
- Branches: cleaned up
- Worktrees: pruned
- Known issues / follow-ups: [from Completion Report, or "none"]
```

Sync local main: `git checkout main && git pull origin main`

Send via Telegram if MCP connected (detected by availability of `mcp__plugin_telegram_telegram__reply` tool — see SKILL.md Startup Checklist).

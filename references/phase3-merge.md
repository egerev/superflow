# Phase 3: Merge (USER-INITIATED)

```bash
# Event emission preloader — idempotent, runs at top of every phase doc bash usage.
# Tries (in order): already-sourced sf_emit → local tools/sf-emit.sh → runtime-aware paths → no-op.
# Also restores SUPERFLOW_RUN_ID from state if unset.
if ! command -v sf_emit >/dev/null 2>&1; then
  for _sf_path in \
      "./tools/sf-emit.sh" \
      "$HOME/.claude/skills/superflow/tools/sf-emit.sh" \
      "$HOME/.codex/skills/superflow/tools/sf-emit.sh" \
      "$HOME/.agents/skills/superflow/tools/sf-emit.sh"; do
    if [ -f "$_sf_path" ]; then source "$_sf_path"; break; fi
  done
  command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
fi
if [ -z "${SUPERFLOW_RUN_ID:-}" ] && [ -f .superflow-state.json ]; then
  SUPERFLOW_RUN_ID=$(python3 -c 'import json; print(json.load(open(".superflow-state.json")).get("context",{}).get("run_id",""))' 2>/dev/null)
  [ -n "$SUPERFLOW_RUN_ID" ] && export SUPERFLOW_RUN_ID
fi
```

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
  - "Clean artifacts and branches"
  - "Generate post-merge report"
  - "Send Telegram report"
```

### Phase 3 Entry After Compaction

On Phase 3 entry, check for a heartbeat block in `.superflow-state.json`. If `heartbeat.phase2_step == 'ship'`, the previous Phase 2 run ended cleanly and all mode-specific PRs/checkpoints were created. Re-read this file (`references/phase3-merge.md`) before every PR merge — it is already included in `heartbeat.must_reread` via the Phase 2 heartbeat writer, so compaction-triggered rehydration will pull the exact merge procedure into context automatically.

### State Management

At the start of Phase 3, merge-update `.superflow-state.json` (preserves `context.*`):
```bash
python3 -c "
import json, datetime, os
p = '.superflow-state.json'
s = json.load(open(p)) if os.path.exists(p) else {}
s.update({'version':1,'phase':3,'phase_label':'Merge','stage':'pre-merge','stage_index':0,'last_updated':datetime.datetime.now(datetime.timezone.utc).isoformat()})
json.dump(s, open(p,'w'), indent=2)
"
sf_emit phase.start phase:int=3 label="Merge"
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

```bash
sf_emit stage.start stage=pre-merge phase:int=3
```

## Pre-Merge Checklist
<!-- Stage 1: Pre-merge -->

Before merging any PR:
0. **Read completion data** — load `context.completion_data_file` from `.superflow-state.json`:
   ```bash
   python3 -c "import json; s=json.load(open('.superflow-state.json')); p=s.get('context',{}).get('completion_data_file'); print(open(p).read() if p else 'No completion data')"
   ```
   Fallback: if file missing or no path, enumerate PRs with `gh pr list --state open --author @me --json number,title,headRefName --jq 'sort_by(.number)'`
1. **CI must pass** on all PRs — check with `gh pr checks <number>`
2. **No unresolved review comments** — check with `gh pr view <number>`
3. **CLAUDE.md is up to date** — audit against current codebase:
   - New files/modules added during this session are documented
   - New commands (build/test/lint) are listed
   - Removed or renamed files are cleaned up
   - Use `prompts/claude-md-writer.md` for conventions

## Documentation Update (pre-merge)
<!-- Stage 1: Pre-merge, Todos 3-4 -->

Before the first merge, verify the PR-level docs gate for the selected git workflow mode. For per-sprint PR modes, docs should already be updated/reviewed on each PR. For `solo_single_pr`, the final PR must include the docs update/review. If the audit finds drift, create a dedicated documentation commit on the last branch/PR that will be merged:
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

```bash
sf_emit stage.end stage=pre-merge phase:int=3
sf_emit stage.start stage=merge phase:int=3
```

## Merge Order
<!-- Stage 2: Merge -->

Use the PR list and merge order from the Phase 2 Completion Report. If the report is unavailable (context compaction), enumerate open PRs: `gh pr list --state open --author @me --json number,title,headRefName --jq 'sort_by(.number)'`

Read `context.git_workflow_mode` from `.superflow-state.json`; if missing, default to `sprint_pr_queue`.

Merge policy by mode:
- `solo_single_pr`: merge the single final PR after CI, docs, and review checks pass.
- `sprint_pr_queue`: merge PRs sequentially in sprint order.
- `parallel_wave_prs`: merge PRs sequentially in wave order, then sprint order inside each wave. Never merge in parallel.
- `stacked_prs`: merge Sprint 1 first. Before each later sprint merge, fetch `origin/main`, check out the sprint branch, rebase it onto `origin/main`, push with `--force-with-lease`, retarget the PR base to `main` (`gh pr edit <number> --base main`), wait for CI, then merge.
- `trunk_based`: merge short-lived PRs in dependency order from the completion data.

At merge start, if Telegram MCP available:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Merging N PRs...")
```
(Replace N with actual PR count.)

PRs merge sequentially in the order required by the selected git workflow mode:

```
for each PR in sprint order:
  0. Check PR state: `gh pr view <number> --json state -q '.state'`
     - If "MERGED": skip, log as already merged
     - If "CLOSED": warn user, skip
     - If "OPEN": proceed with merge
  1. gh pr checks <number> — verify CI green
     - If CI failing, send Telegram (if MCP available):
       mcp__plugin_telegram_telegram__reply(chat_id: <chat_id>, text: "PR #N CI failed, investigating...")
     # NOTE: no event emitted on CI failure/abandon — pr.merge is reserved for successful merges.
     # Failed-merge telemetry is TBD (see CHANGELOG deferred).
  2. gh pr merge <number> --rebase --delete-branch
     sf_emit pr.merge number:int=NNN method=rebase  # replace NNN with actual PR number
  3. If merge fails due to conflict:
     a. git fetch origin main
     b. git checkout <branch>
     c. git rebase origin/main
     d. Fix conflicts, commit
     e. git push --force-with-lease  # Safe: required after rebase
     f. Wait for CI, then retry step 2
  4. Verify: `gh pr view <number> --json state -q '.state'` must return "MERGED"
  5. git pull origin main  # sync local main
  6. Send Telegram (if MCP available):
     mcp__plugin_telegram_telegram__reply(chat_id: <chat_id>, text: "Merged PR #N (K/total)")
     (Replace N with PR number, K with current count, total with total PR count.)
```

## Rules

- **Rebase strategy**: always `--rebase` to keep linear history
- **Delete branch after merge**: `--delete-branch`
- **One at a time**: merge sequentially, never parallel
- **CI gate**: never merge with failing checks — fix first (see CI Failure below)
- **Force-push after rebase is approved**: `git push --force-with-lease` is the standard post-rebase push and is explicitly permitted in Phase 3 conflict resolution
- **Worktree cleanup**: BEFORE merge, not after. Remove worktrees for branches about to be merged, then `git worktree prune`
- **Artifact cleanup**: after all PRs merged, remove `.par-evidence.json` from the working directory (if present). Do NOT commit removal — these are ephemeral gate artifacts.
- **Branch cleanup**: after all PRs merged, prune stale remote refs and delete merged local branches:
  ```bash
  git remote prune origin
  git branch --merged main | grep -v '^\*' | grep -v 'main$' | xargs git branch -d 2>/dev/null
  ```

## CI Failure During Merge

If `gh pr checks <number>` shows failing checks:
1. Identify the failing check: `gh pr checks <number>`
2. Check out the branch: `git checkout <branch>`
3. Diagnose: read CI logs, reproduce locally if possible
4. Fix, commit, push
5. Wait for CI to pass (poll `gh pr checks <number>`, max 5 minutes)
6. If CI still fails after 2 fix attempts: stop and report to user with error details
7. Resume merge sequence from the failed PR

```bash
sf_emit stage.end stage=merge phase:int=3
sf_emit stage.start stage=post-merge phase:int=3
```

## Post-Merge Verification
<!-- Stage 2: Merge (final step) -->

After all PRs are merged, run the full test suite on main to verify integration:
```bash
git checkout main && git pull origin main
python3 -c "import json; q=json.load(open('docs/superflow/sprint-queue.json')); print(q.get('baseline_cmd','No baseline command found'))"
```
Execute the baseline test command. If tests fail: warn the user with specific failures before ending the session. Do NOT proceed to Post-Merge Report until tests pass or user acknowledges failures.

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

Send the post-merge report via Telegram if MCP connected (detected by availability of `mcp__plugin_telegram_telegram__reply` tool — see SKILL.md Startup Checklist):
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "<post-merge report summary>")
```
Include merged PR numbers, CI status, test results, and branch cleanup status in the summary.

```bash
sf_emit stage.end stage=post-merge phase:int=3
sf_emit phase.end phase:int=3 label="Merge"
sf_emit run.end status=completed
```

## Known Issues

### Post-compaction merge method regression
**Severity:** High — PRs left open on GitHub, branches not cleaned up
**Trigger:** Context compaction during Phase 3 erases the phase3-merge.md instructions. The agent then falls back to local `git merge` instead of `gh pr merge --rebase --delete-branch`.
**Symptoms:**
- Merge commits in history instead of linear rebase
- GitHub PRs remain OPEN despite code being in main
- Remote branches not deleted
**Root cause:** Phase 3 merge loop runs over multiple sprints. If compaction occurs mid-loop, the agent loses the `gh pr merge` instruction and improvises with `git merge`.
**Mitigation (current):** superflow-enforcement.md rule 5 says "Re-read phase docs at each sprint boundary." But merge loop is within a single stage, not across sprint boundaries.
**Fix needed:** Add a compaction guard — either:
1. Re-read `phase3-merge.md` before EACH PR merge (not just at stage start), or
2. Add merge method rule to `superflow-enforcement.md` (survives compaction): "Phase 3 merges use `gh pr merge --rebase --delete-branch`, NEVER local `git merge`"

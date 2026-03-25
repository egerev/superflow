# Auto-Supervisor: Design Specification

**Version:** v3.5.0
**Date:** 2026-03-25
**Brief:** [2026-03-25-auto-supervisor-brief.md](2026-03-25-auto-supervisor-brief.md)

---

## 1. Plan-to-Queue Generator

### Module: `lib/planner.py` (new)

**Purpose:** Parse an approved markdown plan into `sprint-queue.json`.

#### Function: `plan_to_queue(plan_path, feature, base_branch="feat")`

**Input:** Path to plan markdown file (e.g., `docs/superflow/plans/2026-03-25-auto-supervisor.md`).

**Parsing rules:**
- Match sprint headings (multiple formats supported):
  - `## Sprint N: Title` (colon separator)
  - `## Sprint N — Title` (em-dash separator)
  - `## Sprint N - Title` (hyphen separator)
  - `## Sprint N` (no title — uses "Sprint N" as title)
  - Regex: `^##\s+Sprint\s+(\d+)\s*(?:[:—\-]\s*(.+))?$` (multiline)
- **Shared parser:** Extract into `lib/planner.py:_parse_sprint_headings()`, reuse in `lib/supervisor.py:_extract_plan_section()` to guarantee format compatibility. Both must agree on what constitutes a sprint heading.
- Extract section content between heading and next same-level heading
- From each section extract:
  - `complexity`: match `complexity:\s*(\w+)` (default: `medium`)
  - `depends_on`: match `depends.on|Dependencies:\s*Sprint\s+(\d+(?:,\s*\d+)*)` (default: `[]`)
- Generate `branch`: `{base_branch}/{slug}-sprint-{id}` where slug = title lowercased, non-alphanum replaced with `-`
- Generate `plan_file`: `{plan_path}#sprint-{id}` (fragment format, compatible with `_extract_plan_section()`)

**Output:** Dict matching `sprint-queue.json` schema:
```json
{
  "feature": "auto-supervisor",
  "created": "2026-03-25T12:00:00+00:00",
  "generated_from": {
    "plan_file": "docs/superflow/plans/2026-03-25-auto-supervisor.md",
    "content_hash": "sha256:abc123...",
    "generated_at": "2026-03-25T12:00:00+00:00"
  },
  "sprints": [
    {
      "id": 1,
      "title": "Plan-to-queue generator + security hardening",
      "status": "pending",
      "complexity": "medium",
      "plan_file": "docs/superflow/plans/2026-03-25-auto-supervisor.md#sprint-1",
      "branch": "feat/auto-supervisor-sprint-1",
      "depends_on": [],
      "pr": null,
      "retries": 0,
      "max_retries": 2,
      "error_log": null
    }
  ]
}
```

**Validation:**
- Sprint IDs must be unique
- `depends_on` references must exist
- No circular dependencies (topological sort check)
- Plan file must exist and be readable

**Content hash:** SHA-256 of plan file content. Stored in `generated_from.content_hash`. Used by launcher to detect plan drift before launch.

**Atomic save:** Write to `.tmp` file, then `os.replace()`.

**Save location:** `docs/superflow/sprint-queue.json` (same as current convention).

#### Function: `validate_queue_freshness(queue_path, plan_path) -> (bool, str)`

Compare `generated_from.content_hash` in queue file against current plan file hash. Returns `(is_fresh, reason)`.

---

## 2. Launcher Module

### Module: `lib/launcher.py` (new)

**Purpose:** Launch, monitor, and stop the supervisor as a detached background process.

#### Infrastructure directory: `.superflow/`

Created in project root (gitignored). Contains:
- `supervisor.pid` — PID file (permissions `0o600`)
- `supervisor.log` — stdout/stderr of supervisor process
- `heartbeat` — timestamp of last supervisor loop iteration

#### Function: `launch(queue_path, plan_path, repo_root, **kwargs) -> LaunchResult`

**Steps:**
1. Check for already-running supervisor via `read_pid()` → if alive, return existing status
2. Run `preflight()` from `lib/supervisor` — abort on critical failures, show warnings
3. Validate queue freshness via `validate_queue_freshness()` — abort if stale, offer regeneration
4. Create `.superflow/` directory with `os.makedirs(exist_ok=True)`
5. Open log file (**append** mode — preserves diagnostic history from previous runs)
6. Build command (v3.5.0 scoped to sequential execution only — `--parallel` not exposed):
   ```python
   cmd = [
       sys.executable,  # Use same Python that launched us
       os.path.join(repo_root, "bin", "superflow-supervisor"),
       "run",
       "--queue", queue_path,
       "--plan", plan_path,
       "--timeout", str(kwargs.get("timeout", 1800)),
   ]
   ```
7. Launch via `subprocess.Popen`:
   ```python
   proc = subprocess.Popen(
       cmd,
       stdout=log_file,
       stderr=subprocess.STDOUT,
       stdin=subprocess.DEVNULL,
       start_new_session=True,
       cwd=repo_root,
       env=_launch_env(),
   )
   ```
8. Write PID file atomically (`write .tmp` + `os.replace()`, permissions `0o600`)
9. Verify process is alive after 2 seconds (`os.kill(pid, 0)`)
10. Return `LaunchResult(pid, log_path, queue_path, sprint_count)`

**Note:** Launcher does NOT write `.superflow-state.json`. The supervisor is the single writer to this file via `_write_state()`. The launcher's `get_status()` reads the PID file directly from `.superflow/supervisor.pid`.

**`_launch_env()`:** Two-tier environment policy (see Security section 7.2).

**`LaunchResult`:** Named tuple with `pid`, `log_path`, `queue_path`, `sprint_count`.

#### Function: `read_pid(pid_path) -> int | None`

Read PID from file. Verify process alive via `os.kill(pid, 0)`. Return PID if alive, `None` if dead/missing. Clean stale PID file on dead process.

#### Function: `stop(repo_root, wait_timeout=60) -> bool`

Send `SIGTERM` to the **process group** (not just the parent PID) via `os.killpg(pid, signal.SIGTERM)`. This ensures child `claude -p` processes are also terminated, preventing orphaned worktree mutations.

Poll `os.kill(pid, 0)` every second for `wait_timeout`. If parent still alive after timeout, escalate to `os.killpg(pid, signal.SIGKILL)`. Clean PID file only after confirming the group is gone. Return success.

**Why `killpg`:** `start_new_session=True` makes the supervisor a session leader. Its PID equals the process group ID. `SIGTERM` to just the parent leaves `claude -p` children alive, which may continue mutating worktrees while a new supervisor starts.

#### Function: `get_status(repo_root) -> SupervisorStatus`

Read PID file, state file, and heartbeat. Return structured status:
```python
@dataclass
class SupervisorStatus:
    alive: bool
    pid: int | None
    phase: int | None
    sprint: int | None
    stage: str | None
    tasks_done: list[int]
    tasks_total: int | None
    heartbeat_age_seconds: float | None
    crashed: bool  # alive=False but state shows mid-execution
    log_path: str | None
```

#### Function: `restart(repo_root, queue_path, plan_path) -> LaunchResult`

1. Call `stop()` if supervisor is alive
2. Run `resume()` from `lib/supervisor` to recover crashed sprints
3. Call `launch()` to restart

---

## 3. Heartbeat

### Changes to: `lib/supervisor.py`

Add heartbeat writes to the main run loop.

**Location:** Top of `while not queue.is_done()` loop (after line 1350).

```python
# Write heartbeat
heartbeat_path = os.path.join(repo_root, ".superflow", "heartbeat")
try:
    os.makedirs(os.path.dirname(heartbeat_path), exist_ok=True)
    with open(heartbeat_path, 'w') as f:
        f.write(str(time.time()))
except OSError:
    pass
```

**Staleness threshold:** `sprint_timeout + 300` seconds (default: 2100s = 35 minutes). A single sprint can block the main loop for up to `--timeout` seconds (default 1800s) during `subprocess.run()`. The heartbeat is written at the top of the loop, before the blocking sprint call. Setting threshold below the sprint timeout would cause false crash detection on healthy sprints.

**Dashboard crash detection:** `get_status()` reports `crashed=True` only when `alive=False` AND `heartbeat_age > threshold`. While `alive=True`, the supervisor is healthy regardless of heartbeat age.

---

## 4. CLI Subcommand

### Changes to: `bin/superflow-supervisor`

Add `launch` subcommand:

```
superflow-supervisor launch --queue Q --plan P [--parallel N] [--timeout T]
```

**Behavior:** Calls `launcher.launch()` and prints launch receipt:
```
Supervisor launched (PID 12345)
  Queue:  docs/superflow/sprint-queue.json (4 sprints)
  Log:    .superflow/supervisor.log
  Status: superflow-supervisor status --queue Q
  Stop:   superflow-supervisor stop
```

Add `stop` subcommand:
```
superflow-supervisor stop
```

**Behavior:** Calls `launcher.stop()`.

Existing `status` subcommand: Enhanced to use `launcher.get_status()` for richer output (heartbeat age, PID, crash detection).

---

## 5. Phase 1 Step 11 Changes

### Changes to: `references/phase1-discovery.md`

Replace the current context reset instruction (lines 240-245) with auto-launch flow:

**After user says "go":**

1. Generate sprint queue: call `plan_to_queue()` logic (via subagent writing `docs/superflow/sprint-queue.json`)
2. Run preflight checks (via Bash: `python3 -c "from lib.supervisor import preflight; ..."`)
3. Show preflight report to user
4. If preflight passes: ask "Start supervisor? It will run sprints in background. You'll see progress here."
5. On confirmation: launch via Bash: `python3 -c "from lib.launcher import launch; ..."`
6. Show launch receipt (PID, log path, sprint count)
7. Transition session to Phase 2 dashboard mode

**If preflight fails:** Show failures, offer manual fixes, re-run preflight.

**If user declines supervisor:** Fall back to current flow — context reset instruction (`/clear` + `/superflow`).

---

## 6. Session-as-Dashboard (Phase 2)

### Changes to: `references/phase2-execution.md`, `SKILL.md`

When supervisor is running, the Claude session enters **dashboard mode**:

#### Sprint transition notifications

Poll `.superflow-state.json` via Bash `run_in_background` on a loop:
```bash
while true; do
  cat .superflow-state.json 2>/dev/null
  sleep 30
done
```

On state change (sprint number changed or stage changed): display update:
```
Sprint 2/4 completed: "API endpoints" — PR #46 created
Sprint 3/4 in progress: "Frontend components"
```

On supervisor completion (all sprints done or supervisor PID gone): display final summary and offer merge.

#### Interactive commands

Claude session recognizes these commands from the user during dashboard mode:

| Command | Implementation |
|---------|----------------|
| `status` | `python3 -c "from lib.launcher import get_status; ..."` → display formatted status |
| `log` | `tail -50 .superflow/supervisor.log` |
| `stop` | `python3 -c "from lib.launcher import stop; ..."` → confirm, then SIGTERM |
| `restart` | `python3 -c "from lib.launcher import restart; ..."` → resume + relaunch |
| `skip N` | Write skip request to `.superflow/skip-requests.json` sidecar file. Supervisor reads sidecar before each scheduling decision and applies skips to its in-memory queue. No direct queue file edits (avoids race with supervisor's in-memory state). |
| `merge` | Only if all sprints complete. Transition to Phase 3 (read `references/phase3-merge.md`). |

#### Reconnection

If user starts a new session (`/superflow`) while supervisor is running:
1. Read `.superflow-state.json` — phase=2
2. Check `launcher.get_status()` — alive=True
3. Enter dashboard mode automatically
4. Display current progress

If supervisor has finished:
1. Read state — phase=2, stage="ship"
2. Check `get_status()` — alive=False, crashed=False
3. Display completion summary
4. Offer merge

If supervisor has crashed:
1. Read state — phase=2, mid-sprint
2. Check `get_status()` — alive=False, crashed=True
3. Offer restart (resume + relaunch)

---

## 7. Security Hardening

### 7.1 Path Traversal Fix

**Files:** `lib/supervisor.py:build_prompt()`, `lib/queue.py`

**Fix in `build_prompt()`** (supervisor.py lines 163-170):
```python
plan_path = os.path.join(repo_root, file_part)
# Security: validate path stays within repo
real_plan = os.path.realpath(plan_path)
real_repo = os.path.realpath(repo_root)
if not real_plan.startswith(real_repo + os.sep):
    raise ValueError(f"Path traversal detected: {plan_file} resolves outside repo")
```

**Fix in `SprintQueue.load()`** (queue.py):
Add same validation for `plan_file` field when loading queue.

**Fix in `plan_to_queue()`** (planner.py):
Reject plan files containing `..` or absolute paths.

### 7.2 Two-Tier Environment Policy

**Problem (from review):** A single deny-list is contradictory. `TELEGRAM_BOT_TOKEN` must be available to the supervisor (for notifications) but should not leak to sprint subprocesses. `ANTHROPIC_API_KEY` must reach `claude -p` sessions.

**Solution: Two distinct env policies.**

#### Tier 1: Launcher → Supervisor (`_launch_env()` in `lib/launcher.py`)

Pass **full environment** to the supervisor process. The supervisor is trusted code (our own Python script). It needs:
- `ANTHROPIC_API_KEY` — passed through to `claude -p` sprint sessions
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — for notifications
- `PATH` — to find `claude`, `git`, `gh` binaries

Only filter truly dangerous keys that the supervisor never needs:
```python
_LAUNCH_DENY_LIST = {
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "DATABASE_URL", "DB_PASSWORD",
    "STRIPE_SECRET_KEY", "STRIPE_API_KEY",
    "DOCKER_PASSWORD",
    "HEROKU_API_KEY",
}
```

#### Tier 2: Supervisor → Sprint Subprocess (`_filtered_env()` in `lib/supervisor.py`)

Existing function, expanded. Sprint `claude -p` sessions run arbitrary code and should have minimal secrets:
```python
_SPRINT_DENY_LIST = {
    # Existing
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "DATABASE_URL", "DB_PASSWORD",
    "OPENAI_API_KEY", "SECRET_KEY",
    # New additions
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "SLACK_TOKEN", "SLACK_BOT_TOKEN",
    "STRIPE_SECRET_KEY", "STRIPE_API_KEY",
    "SSH_AUTH_SOCK", "SSH_AGENT_PID",
    "NPM_TOKEN",
    "DOCKER_PASSWORD",
    "HEROKU_API_KEY",
    "SENTRY_DSN",
}
```

**Explicitly preserved** in sprint env (required for `claude -p`):
- `ANTHROPIC_API_KEY` — Claude authentication
- `GITHUB_TOKEN` / `GH_TOKEN` — needed for `gh pr create`
- `PATH` — binary resolution

### 7.3 Skip-Request Sidecar (Control Channel)

**Problem (from review):** The supervisor holds the queue in memory and writes it back after each sprint. External edits to the queue file get overwritten. Direct file editing for `skip N` causes data loss.

**Solution:** Sidecar file `.superflow/skip-requests.json`:
```json
[{"sprint_id": 3, "reason": "user requested skip", "ts": "2026-03-25T12:00:00Z"}]
```

**Writer:** Dashboard `skip N` command appends to this file.
**Reader:** Supervisor checks the sidecar at the top of each main loop iteration (before `next_runnable()`). If skip requests exist, apply them to the in-memory queue, save queue, and truncate the sidecar file.

This avoids race conditions: the sidecar is append-only from the dashboard side, and read-then-truncate from the supervisor side.

### 7.4 Content Hash for Queue Integrity

**File:** `lib/planner.py` (new)

Queue file includes `generated_from.content_hash` (SHA-256 of plan content). `validate_queue_freshness()` compares before launch. Note: freshness check is primarily for reconnection scenarios (user generated queue, went away, came back with stale queue). On fresh launch from Phase 1, the queue is just generated — freshness is guaranteed.

### 7.5 PID File Permissions

**File:** `lib/launcher.py` (new)

PID file created with `0o600` permissions:
```python
fd = os.open(tmp_pid, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(str(proc.pid))
os.replace(tmp_pid, pid_path)
```

### 7.6 Telegram Token via Env Only

**File:** `bin/superflow-supervisor` (lines 112, 128)

Remove `--telegram-token` and `--telegram-chat` CLI flags. Read exclusively from env vars `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. This prevents leaking tokens in shell history and `/proc` listings.

Update `lib/notifications.py` constructor to read from env if not passed as args.

---

## 8. Scoping Decisions

| Decision | Rationale |
|----------|-----------|
| **Sequential execution only** (no `--parallel` in auto-launch) | Parallel execution complicates status display (multiple active sprints), heartbeat, and skip-request handling. Existing `--parallel` flag still works for manual CLI users. v3.6.0 scope. |
| **State file single-writer** (supervisor only) | Launcher does not write state. `get_status()` combines PID file + state file + heartbeat. Avoids race conditions. |
| **Polling interval 30s** (not 2s) | Sprint transitions happen every 5-30 minutes. 30s polling is sufficient and avoids unnecessary reads. |

---

## 9. Files Changed Summary

| File | Type | Changes |
|------|------|---------|
| `lib/planner.py` | **New** | `plan_to_queue()`, `validate_queue_freshness()` |
| `lib/launcher.py` | **New** | `launch()`, `read_pid()`, `stop()`, `get_status()`, `restart()`, `LaunchResult`, `SupervisorStatus` |
| `lib/supervisor.py` | Modify | Heartbeat in run loop, skip-request sidecar check before scheduling, path traversal fix in `build_prompt()`, expanded `_filtered_env()` |
| `lib/queue.py` | Modify | Path validation in `load()`, preserve `generated_from` field in load/save |
| `lib/notifications.py` | Modify | Read Telegram credentials from env vars (fallback) |
| `bin/superflow-supervisor` | Modify | Add `launch` and `stop` subcommands, remove `--telegram-token`/`--telegram-chat` CLI flags |
| `references/phase1-discovery.md` | Modify | Step 11: auto-launch flow replaces context reset |
| `references/phase2-execution.md` | Modify | Document dashboard mode and commands |
| `SKILL.md` | Modify | Add dashboard mode documentation, commands |
| `templates/superflow-state-schema.json` | Modify | Add `context.supervisor_pid_file` field |
| `tests/test_planner.py` | **New** | Tests for plan_to_queue, validation, edge cases |
| `tests/test_launcher.py` | **New** | Tests for launch, stop, status, restart, PID management |
| `tests/test_security.py` | **New** | Tests for path traversal rejection, env filtering |

---

## 10. Testing Strategy

### Unit tests (new files)

**`tests/test_planner.py`:**
- Parse valid plan with 4 sprints
- Extract complexity and depends_on
- Handle missing complexity (default medium)
- Handle missing depends_on (default [])
- Reject duplicate sprint IDs
- Reject circular dependencies
- Reject plan with no sprints
- Content hash generation and validation
- Stale queue detection

**`tests/test_launcher.py`:**
- Launch supervisor (mocked Popen)
- Detect already-running supervisor
- Read valid/stale/missing PID file
- Stop supervisor via killpg (SIGTERM path)
- Stop supervisor via killpg (SIGKILL fallback)
- Get status with heartbeat
- Crash detection (dead PID + mid-execution state)
- Restart flow (stop + resume + launch)
- PID file permissions
- Skip-request sidecar write and read
- Skip-request applied to in-memory queue

**`tests/test_security.py`:**
- Path traversal: `../../etc/passwd` rejected in build_prompt
- Path traversal: absolute path rejected
- Path traversal: symlink outside repo rejected
- Env deny-list: sensitive keys filtered
- Env allow-list: ANTHROPIC_API_KEY preserved
- Queue with traversal path rejected on load

### Existing tests

All 228 existing tests must continue to pass. Security changes to `build_prompt()` and `_filtered_env()` are backward-compatible (existing valid paths still work, new validation only rejects malicious inputs).

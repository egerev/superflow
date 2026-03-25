# Implementation Plan: Auto-Supervisor (v3.5.0)

**Spec:** [2026-03-25-auto-supervisor-design.md](../specs/2026-03-25-auto-supervisor-design.md)
**Brief:** [2026-03-25-auto-supervisor-brief.md](../specs/2026-03-25-auto-supervisor-brief.md)

---

## Sprint 1: Security Hardening + Shared Parser

**Complexity:** medium
**Dependencies:** none

Foundation sprint. Fix P0 security issues and create the shared heading parser that both planner and supervisor will use.

### Task 1.1: Path traversal fix in `build_prompt()`

**Files:** `lib/supervisor.py`
**Steps:**
1. Add `_validate_repo_path(repo_root, file_path)` helper that resolves both paths via `os.path.realpath()` and checks `real_path.startswith(real_repo + os.sep)`
2. Call it in `build_prompt()` before `open(plan_path)` (after line 170)
3. Raise `ValueError` on traversal attempt

**Commit:** `fix: add path traversal validation in build_prompt()`

### Task 1.2: Path validation in `SprintQueue.load()`

**Files:** `lib/queue.py`
**Steps:**
1. After loading JSON, validate each sprint's `plan_file` field:
   - Reject absolute paths (`os.path.isabs()`)
   - Reject `..` components
2. Raise `ValueError` with clear message

**Commit:** `fix: reject path traversal in queue plan_file fields`

### Task 1.3: Expand environment deny-list (two-tier)

**Files:** `lib/supervisor.py`
**Steps:**
1. Rename `_DENIED_ENV_KEYS` to `_SPRINT_ENV_DENY_LIST`
2. Add new keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SLACK_TOKEN`, `SLACK_BOT_TOKEN`, `STRIPE_SECRET_KEY`, `STRIPE_API_KEY`, `SSH_AUTH_SOCK`, `SSH_AGENT_PID`, `NPM_TOKEN`, `DOCKER_PASSWORD`, `HEROKU_API_KEY`, `SENTRY_DSN`
3. Keep `ANTHROPIC_API_KEY` and `GITHUB_TOKEN`/`GH_TOKEN` explicitly out of deny-list (add comment explaining why)
4. Keep existing `GOOGLE_API_KEY` and `HCLOUD_TOKEN` in deny-list (no security regression)

**Commit:** `fix: expand sprint env deny-list, preserve auth keys`

### Task 1.4: Remove Telegram CLI flags

**Files:** `bin/superflow-supervisor`, `lib/notifications.py`
**Steps:**
1. Remove `--telegram-token` and `--telegram-chat` from `run_parser` and `resume_parser`
2. Update `_make_notifier()` to read exclusively from env vars
3. Update `Notifier.__init__()` to accept `bot_token=None` and fall back to `os.environ.get('TELEGRAM_BOT_TOKEN')`

**Commit:** `fix: read Telegram credentials from env only, remove CLI flags`

### Task 1.5: Shared sprint heading parser

**Files:** `lib/planner.py` (new), `lib/supervisor.py`
**Steps:**
1. Create `lib/planner.py` with `_parse_sprint_headings(content) -> list[dict]`
   - Regex: `^##\s+Sprint\s+(\d+)\s*(?:[:—\-]\s*(.+))?$`
   - Returns list of `{"id": int, "title": str, "start_line": int, "end_line": int}`
2. Refactor `_extract_plan_section()` in supervisor.py to use `_parse_sprint_headings()` for sprint-type fragments
3. Ensure backward compatibility: non-sprint fragments still use the existing normalize+match logic

**Commit:** `refactor: extract shared sprint heading parser to lib/planner.py`

### Task 1.6: Add `.superflow/` to .gitignore

**Files:** `.gitignore`
**Steps:**
1. Add `.superflow/` to root .gitignore (alongside `.worktrees/` and `.superflow-state.json`)
2. Update Phase 0 `references/phase0/stage4-setup.md` Branch C to include `.superflow/` in the gitignore template

**Commit:** `chore: add .superflow/ to .gitignore`

### Task 1.7: Security tests + existing test updates

**Files:** `tests/test_security.py` (new), `tests/test_cli.py`, `tests/test_notifications.py`, `tests/test_supervisor.py`
**Steps:**
1. New `test_security.py`: path traversal rejection, env deny-list, queue load rejection, Telegram token not in sprint env
2. Update `test_cli.py`: verify `--telegram-token` flag removed, `launch` and `stop` subcommands (stubs for Sprint 3)
3. Update `test_notifications.py`: verify env-var fallback in Notifier init
4. Update `test_supervisor.py`: add heading format compatibility tests (shared parser drives `build_prompt()` correctly for `Sprint 1:`, `Sprint 1 —`, `Sprint 1 -`)

**Commit:** `test: add security tests and update existing test suites`

---

## Sprint 2: Plan-to-Queue Generator

**Complexity:** medium
**Dependencies:** Sprint 1

Build the plan→queue conversion using the shared parser from Sprint 1.

### Task 2.1: `plan_to_queue()` function

**Files:** `lib/planner.py`
**Steps:**
1. Implement `plan_to_queue(plan_path, feature, base_branch="feat")`:
   - Use `_parse_sprint_headings()` to find sprints
   - Extract `complexity` and `depends_on` from each section
   - Generate branch names: `{base_branch}/{slug}-sprint-{id}`
   - Generate `plan_file`: relative path with `#sprint-{id}` fragment
   - Validate: unique IDs, valid depends_on references, no cycles (topological sort)
   - Reject empty plans (no sprints found)
2. Return dict matching queue schema including `generated_from` with SHA-256 content hash

**Commit:** `feat: add plan_to_queue() in lib/planner.py`

### Task 2.2: `validate_queue_freshness()`

**Files:** `lib/planner.py`
**Steps:**
1. Implement `validate_queue_freshness(queue_path, plan_path) -> (bool, str)`
2. Load queue file, read `generated_from.content_hash`
3. Compute current plan file SHA-256, compare
4. Return `(True, "")` or `(False, "plan modified since queue was generated")`

**Commit:** `feat: add queue freshness validation`

### Task 2.3: Extend `SprintQueue` to preserve `generated_from`

**Files:** `lib/queue.py`
**Steps:**
1. Add `generated_from` parameter to `__init__()` (default `None`)
2. Load it in `load()`: `data.get("generated_from")`
3. Save it in `save()`: include in output dict if not None
4. Ensure backward compatibility: old queue files without `generated_from` still load fine

**Commit:** `feat: preserve generated_from metadata in SprintQueue`

### Task 2.4: Planner tests

**Files:** `tests/test_planner.py` (new)
**Steps:**
1. Parse valid plan with 4 sprints (various heading formats)
2. Extract complexity and depends_on
3. Default values when not specified
4. Reject duplicate sprint IDs
5. Reject circular dependencies
6. Reject empty plan
7. Content hash generation
8. Stale queue detection via `validate_queue_freshness()`
9. Test `generated_from` preservation in SprintQueue load/save round-trip

**Commit:** `test: add planner and queue freshness tests`

---

## Sprint 3: Launcher + Supervisor Integration

**Complexity:** complex
**Dependencies:** Sprint 2

Core launcher module and supervisor modifications (heartbeat, skip-request sidecar).

### Task 3.1: `lib/launcher.py` — launch and PID management

**Files:** `lib/launcher.py` (new)
**Steps:**
1. Implement `LaunchResult` (named tuple: `pid`, `log_path`, `queue_path`, `sprint_count`)
2. Implement `_launch_env()` with tier-1 deny-list
3. Implement `read_pid(pid_path) -> int | None` with `os.kill(pid, 0)` liveness check
4. Implement `launch(queue_path, plan_path, repo_root, **kwargs) -> LaunchResult`:
   - Check existing PID — if alive, return existing status (no double-launch)
   - Do NOT run preflight here (supervisor's `run()` already runs it; avoids duplicate work)
   - Validate queue freshness
   - Open log file (append mode)
   - Popen with `start_new_session=True`, `stdin=DEVNULL`
   - Write PID file with `0o600` permissions
   - Verify alive after 2 seconds — if dead, read first 20 lines of log and raise with error context
5. Write `.superflow/launch.json` atomically with: `queue_path`, `plan_path`, `timeout`, `log_path`, `pid`, `launched_at`
   - `get_status()` and `restart()` read this file to know paths without requiring CLI args

**Commit:** `feat: add launcher module with launch() and PID management`

### Task 3.2: `lib/launcher.py` — stop, status, restart

**Files:** `lib/launcher.py`
**Steps:**
1. Implement `SupervisorStatus` dataclass
2. Implement `stop(repo_root, wait_timeout=60)` using `os.killpg()` for process group
3. Implement `get_status(repo_root)` reading PID file + state file + heartbeat
4. Implement `restart(repo_root, queue_path, plan_path)` — stop + resume + launch

**Commit:** `feat: add stop/status/restart to launcher`

### Task 3.3: Heartbeat in supervisor run loop

**Files:** `lib/supervisor.py`
**Steps:**
1. Add heartbeat write at top of `while not queue.is_done()` loop (after line 1350)
2. Write timestamp to `.superflow/heartbeat`
3. Create `.superflow/` dir with `exist_ok=True`

**Commit:** `feat: add heartbeat writes to supervisor run loop`

### Task 3.4: Skip-request sidecar in supervisor

**Files:** `lib/supervisor.py`, `lib/launcher.py`
**Steps:**
1. Skip-request uses one-file-per-request pattern (race-safe):
   - Dashboard writes: `.superflow/skip-requests/skip-{sprint_id}-{timestamp}.json`
   - Each file: `{"sprint_id": N, "reason": "user requested"}`
   - No read-modify-write on writer side — just create a new file
2. Add `_check_skip_requests(repo_root, queue)` in supervisor:
   - Glob `.superflow/skip-requests/*.json`
   - For each file: parse, validate sprint_id exists in queue (catch `KeyError`), call `queue.mark_skipped()`
   - Delete processed files via `os.unlink()`
3. Call at top of main loop, before `next_runnable()`
4. Add `write_skip_request(repo_root, sprint_id, reason)` in launcher.py for dashboard use
   - Validate sprint_id against queue before writing (prevent typo-crashes)

**Commit:** `feat: add skip-request sidecar channel for dashboard control`

### Task 3.5: CLI subcommands (launch, stop)

**Files:** `bin/superflow-supervisor`
**Steps:**
1. Add `launch` subparser with `--queue`, `--plan`, `--timeout`
2. Add `stop` subparser (no args, reads PID from `.superflow/supervisor.pid`)
3. Enhance `status` to use `get_status()` for richer output
4. Remove unused `generate_completion_report` import

**Commit:** `feat: add launch/stop CLI subcommands`

### Task 3.6: Launcher + supervisor tests

**Files:** `tests/test_launcher.py` (new)
**Steps:**
1. Launch with mocked Popen
2. Detect already-running supervisor
3. Read valid/stale/missing PID
4. Stop via killpg (SIGTERM + SIGKILL paths)
5. Status with heartbeat age
6. Crash detection
7. Restart flow
8. PID file permissions
9. Skip-request sidecar write and read
10. Skip-request applied to in-memory queue

**Commit:** `test: add launcher and skip-request tests`

---

## Sprint 4: Phase Docs + Dashboard Mode

**Complexity:** medium
**Dependencies:** Sprint 3

Update markdown phase docs and SKILL.md for the new auto-launch flow and dashboard mode.

### Task 4.1: Update Phase 1 Step 11

**Files:** `references/phase1-discovery.md`
**Steps:**
1. Replace context reset instruction (lines 240-245) with auto-launch flow:
   - **First:** check if supervisor is already running via PID (prevents overwriting queue while supervisor consumes it)
   - Generate queue via `plan_to_queue()`
   - Ask "Start supervisor? It will run N sprints in background."
   - On yes: launch, show receipt, enter dashboard mode
   - If launch fails (2s liveness check): show error + first 20 lines of log
   - On no: fall back to `/clear` + `/superflow`
2. Keep existing fallback path for users who prefer manual flow

**Commit:** `docs: replace context reset with auto-launch in Phase 1 Step 11`

### Task 4.2: Document dashboard mode in Phase 2

**Files:** `references/phase2-execution.md`
**Steps:**
1. Add "Dashboard Mode" section after existing "Supervisor Mode" section
2. Document polling behavior (30s interval, sprint transition updates)
3. Document all 6 commands with examples
4. Document reconnection scenarios (running, finished, crashed)
5. Update "When to use supervisor vs single-session" to mention auto-launch

**Commit:** `docs: document dashboard mode and commands in Phase 2`

### Task 4.3: Update SKILL.md

**Files:** `SKILL.md`
**Steps:**
1. Add dashboard mode to startup checklist (detect running supervisor on session start)
2. Add commands section (status, log, stop, restart, skip, merge)
3. Update architecture diagram to include `lib/planner.py` and `lib/launcher.py`

**Commit:** `docs: update SKILL.md with dashboard mode and new modules`

### Task 4.4: Update state schema

**Files:** `templates/superflow-state-schema.json`
**Steps:**
1. No changes needed for `context.supervisor_pid_file` (launcher doesn't write state)
2. Verify schema still validates existing state writes from supervisor
3. Add `queue_file` and `plan_file` to context properties (documentation-only, supervisor already writes these)

**Commit:** `chore: update state schema documentation`

### Task 4.5: Update CLAUDE.md

**Files:** `CLAUDE.md`
**Steps:**
1. Add `lib/planner.py` and `lib/launcher.py` to architecture and key files tables
2. Update test count
3. Add auto-supervisor to Key Rules if needed
4. Update Known Issues (remove resolved ones)

**Commit:** `docs: update CLAUDE.md with new modules and test counts`

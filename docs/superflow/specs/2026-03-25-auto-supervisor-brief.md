# Auto-Supervisor: Product Summary + Brief

## Product Summary

### What we're building

**Auto-launch supervisor from Phase 1 with terminal-native progress tracking.**

Features:
1. **Plan-to-queue generator** — parse approved plan markdown into `sprint-queue.json` (DAG with dependencies, complexity, branch names)
2. **Detached supervisor launch** — `subprocess.Popen(start_new_session=True)` after user says "go", with PID file and log file management
3. **Session-as-dashboard** — Claude session stays alive, polls `.superflow-state.json`, shows progress on sprint transitions (hybrid mode: auto-update on events, silent between)
4. **Interactive commands** during Phase 2:
   - `status` — current sprint, progress, done/remaining
   - `log` — tail last 50 lines of supervisor.log
   - `stop` — SIGTERM → supervisor finishes current sprint and stops
   - `restart` — resume() + relaunch supervisor
   - `skip N` — mark sprint N as skipped
   - `merge` — Phase 3 (only after all sprints complete)
5. **Security hardening** — fix path traversal in `build_prompt()`, expand env filtering, content hash for queue integrity, PID file permissions

### Problems solved

- **UX cliff eliminated**: users no longer need to know CLI commands or open a second terminal
- **Overnight-ready without Telegram**: terminal-native progress tracking via state file polling
- **Single session flow**: approve → execute → merge without restarting
- **Security debt cleared**: P0 path traversal fix from project health report

### NOT in scope

- Remote server deployment (e.g., running supervisor on a VPS)
- macOS sleep prevention (`caffeinate` integration)
- Web dashboard or GUI
- Changes to supervisor's core sprint execution logic (already works)
- Parallel sprint execution improvements (existing `--parallel` flag is sufficient)

### Key decisions + rationale

| Decision | Rationale |
|----------|-----------|
| Variant A (detached supervisor + session dashboard) | Crash-safe: supervisor survives terminal close. Session stays alive for merge. |
| `--dangerously-skip-permissions` for subprocess claude | Background `claude -p` hangs on permission prompts. No alternative for unattended execution. |
| Polling state file (2s interval) over kqueue/fswatch | Sprint transitions happen every 5-30 min. Polling is simpler and sufficient. |
| Show updates on sprint transitions only (hybrid mode) | Avoids noise. User gets notified when something meaningful happens. |
| All commands in English | Consistency with codebase and documentation. |
| Security sprint included | Path traversal is P0 from health report. Auto-launch amplifies the risk since the flow is now automated. |

---

## Product Brief

### Problem statement

After Phase 1 plan approval, users face a broken UX: they must manually create a sprint queue JSON file, open a separate terminal, and run CLI commands to start execution. This defeats the "describe a feature — get reviewed PRs" promise. Without Telegram, there's no progress feedback at all.

### Jobs to be Done

When **I approve a plan in Phase 1**, I want to **have execution start automatically in the background**, so I can **walk away and come back to completed PRs**.

When **the supervisor is running**, I want to **see sprint progress in my terminal**, so I can **know what's happening without Telegram**.

When **all sprints are done**, I want to **merge from the same session**, so I can **complete the entire workflow without context switching**.

### User stories

1. As a developer, I want Phase 1 "go" to auto-generate the sprint queue and launch the supervisor, so that I don't need to know CLI commands.
2. As a developer without Telegram, I want to see sprint completion updates in my terminal, so that I have progress visibility.
3. As a developer, I want to type "status" during execution to see current progress, so that I can check in when I want.
4. As a developer, I want to type "stop" to gracefully halt execution, so that I can pause work without data loss.
5. As a developer, I want the supervisor to survive if my Claude session crashes, so that hours of work aren't lost.

### Success criteria

- "go" in Phase 1 → supervisor running within 10 seconds (no manual steps)
- Sprint transition updates visible in terminal without Telegram
- All 6 commands (`status`, `log`, `stop`, `restart`, `skip N`, `merge`) functional
- Path traversal vulnerability fixed and tested
- Existing 228 tests still pass + new tests for planner, launcher, security

### Edge cases

| Scenario | Expected behavior |
|----------|-------------------|
| User says "go" twice | Detect running supervisor via PID, show status instead of double-launch |
| Supervisor crashes mid-sprint | Session detects via stale PID, offers "restart" which runs resume() + relaunch |
| User closes terminal, reopens later | New `/superflow` session reads state file, detects running supervisor, becomes dashboard |
| Plan file modified after queue generation | Content hash mismatch detected on launch, force regeneration |
| No test runner detected | Baseline tests skipped (existing behavior), sprint continues |
| Laptop sleeps | Supervisor suspends, resumes on wake. No data loss. |

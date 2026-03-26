# superflow v4.0.0

Autonomous dev workflow for Claude Code. Describe a feature — get reviewed PRs.

## Why

The more autonomous AI coding gets, the less you see what's happening. Telegram integrations, remote sessions, overnight runs — you're no longer watching every line. That's powerful, but it needs structure.

Superflow gives that structure: a 4-phase workflow that takes a feature from idea to merged PRs. You brainstorm together, approve a plan, then walk away. The agent executes sprints, writes tests, runs cross-model reviews, creates PRs. You come back to reviewed code ready to merge.

Built after testing Telegram + Claude Code integration and realizing: unstructured autonomy produces unstructured results. Superflow is the structured alternative.

## How It Works

```
You: "superflow — upgrade analytics"
Agent: [Phase 0: skip — already onboarded]
Agent: [Phase 1: research → brainstorm → spec → plan] "4 sprints. Go?"
You: "go"
Agent: → generates queue → launches supervisor in background
Agent: "Supervisor running (PID 12345). 4 sprints queued."
  [Sprint 1 done → PR #51]
  [Sprint 2 done → PR #52]
  [Sprint 3 done → PR #53]
  [Sprint 4 done → PR #54]
Agent: "All sprints complete. Say 'merge'."
You: "merge"
Agent: [Phase 3: docs → merge → cleanup]
```

**Phase 0 — Onboarding.** Auto-detects your stack, runs 5 parallel audit agents, sets up docs and permissions. Once per project.

**Phase 1 — Discovery.** Expert panel brainstorming (parallel persona agents produce a Board Memo), governance mode selection, spec and plan with dual-model review. Generates an Autonomy Charter before launch.

**Phase 2 — Execution.** Fully autonomous. Governance-aware review tiering (light/standard/critical), charter compliance checks, Popen-based execution with live progress polling, blocker escalation, periodic digest. PR per sprint.

**Phase 3 — Merge.** You say "merge" — sequential rebase merge with CI checks, structured completion data, and doc updates.

## Overnight Run

The main use case: charge up a task before bed, wake up to finished PRs.

```bash
# 1. Plan together (Phase 1)
claude
> superflow — implement payment webhooks

# 2. Say "go" — supervisor launches automatically
> go
# Supervisor launched (PID 12345). 4 sprints queued.
# Dashboard mode: type "status", "log", "stop", "skip N", or "merge"

# 3. Get Telegram updates while you sleep
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat"
```

The supervisor runs each sprint as a fresh Claude session (no context degradation), handles retries, crash recovery, and adaptive replanning. Dashboard mode for monitoring, Telegram for remote control.

## When to Use

**Good fit:** Multi-file features, new subsystems, refactors — anything that benefits from a plan and review cycle.

**Not a good fit:** Quick fixes, single-file changes. Just use Claude Code directly.

## Install

```bash
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow
```

Phase 0 runs automatically on first `/superflow` — sets up permissions, hooks, and documentation.

### Permissions

Add to `~/.claude/settings.json` for autonomous execution without `--dangerously-skip-permissions`:

```json
{
  "permissions": {
    "allow": [
      "Bash(git *)", "Bash(gh *)",
      "Bash(npm *)", "Bash(codex *)", "Bash(timeout *)"
    ]
  }
}
```

Minimal example. Phase 0 generates the full list for your stack — [see Stage 4 Setup](references/phase0/stage4-setup.md).

## Requirements

- **Claude Code CLI**
- **Python 3.10+** (supervisor)
- **GitHub CLI** (`gh`)
- **Secondary provider** (optional): Codex, Gemini CLI, or other
- **macOS**: `brew install coreutils` for `gtimeout`

## Supervisor CLI

| Command | What |
|---------|------|
| `run --queue Q` | Execute sprint queue |
| `launch --queue Q` | Launch supervisor in background |
| `stop` | Stop running supervisor |
| `status --queue Q` | Show queue status + supervisor info |
| `resume --queue Q` | Resume after crash |
| `reset --queue Q --sprint N` | Reset sprint to pending |

Options: `--parallel N`, `--timeout S`, `--plan FILE`. Telegram credentials via env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## What's New in v4.0

**Expert Panel Brainstorming.** Phase 1 replaces sequential Q&A with 3-4 parallel expert persona agents (Product GM, Staff Engineer, UX/Workflow, Domain Expert). Their outputs are synthesized into a Board Memo with consensus, disagreements, and decisions needed. One message instead of 5 questions.

**Adaptive Governance.** Three modes -- light, standard, critical -- auto-suggested based on task complexity, risk, and team familiarity. Controls review depth (single vs. dual reviewer), holistic review threshold, and plan structure. Light mode generates sprint plans inline in the charter via `charter_to_queue()`.

**Autonomy Charter.** Generated at end of Phase 1, before supervisor launch. Contains goal, non-negotiables, success criteria, and governance mode. Injected into every sprint prompt, reviewer context, and replanner -- the single source of truth for what the autonomous executor can and cannot do.

**Telegram Control Plane.** Full-coverage notifications across all 4 phases. Document attachments, hold-request sidecar for pausing execution, merge reminder after completion. 20 event types (up from 16).

**Observability.** `subprocess.Popen` replaces `subprocess.run` for sprint execution, enabling live heartbeat writes and intra-sprint progress tracking. Periodic digest notifications every N sprints. Blocker escalation when retries are exhausted.

**Cross-Phase Data Flow.** State schema extended with `brief_file`, `charter_file`, `completion_data_file`, `governance_mode`. Structured `completion-data.json` written at end of Phase 2 for Phase 3 merge context. Queue metadata carries charter and brief references across supervisor restarts.

## Architecture

```
SKILL.md                        — Entry point, startup checklist
superflow-enforcement.md        — Durable rules (→ ~/.claude/rules/)
references/
  phase0-onboarding.md          — Router (detection + stage loading)
  phase0/                       — 5 modular stage files + greenfield path
  phase1-discovery.md           — Expert panel, governance, charter, auto-launch
  phase2-execution.md           — Governance-aware execution + observability
  phase3-merge.md               — Sequential rebase merge
prompts/                        — Agent templates (8 prompts: implementer, expert-panel, reviewers, doc writers)
agents/                         — 12 agent definitions (deep/standard/fast tiers)
bin/superflow-supervisor        — Supervisor CLI
lib/                            — supervisor.py, queue.py, planner.py, launcher.py, checkpoint.py, parallel.py, replanner.py, notifications.py
tests/                          — 362+ tests
```

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent). MIT License.

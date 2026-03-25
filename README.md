# superflow v3.4.0

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
Agent: [Phase 2: Sprint 1 → PR → Sprint 2 → PR → Sprint 3 → PR → Sprint 4 → PR]
Agent: "4 PRs ready. Say 'merge'."
You: "merge"
Agent: [Phase 3: docs → merge → cleanup]
```

**Phase 0 — Onboarding.** Auto-detects your stack, runs 5 parallel audit agents, sets up docs and permissions. Once per project.

**Phase 1 — Discovery.** Interactive brainstorming, then spec and plan with dual-model review (Claude + Codex). You approve before anything gets built.

**Phase 2 — Execution.** Fully autonomous. PR per sprint, git worktrees, TDD, 2-agent specialized review on every PR. No questions asked.

**Phase 3 — Merge.** You say "merge" — sequential rebase merge with CI checks and doc updates.

## Overnight Run

The main use case: charge up a task before bed, wake up to finished PRs.

```bash
# 1. Plan together (Phase 1)
claude
> superflow — implement payment webhooks

# 2. Approve the plan, then let the supervisor handle execution overnight
./bin/superflow-supervisor run \
  --queue sprint-queue.json \
  --plan plans/payment-webhooks.md \
  --parallel 2 \
  --timeout 3600

# 3. Get Telegram updates while you sleep
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat"
```

The supervisor runs each sprint as a fresh Claude session (no context degradation), handles retries, crash recovery, and adaptive replanning.

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
| `status --queue Q` | Show queue status |
| `resume --queue Q` | Resume after crash |
| `reset --queue Q --sprint N` | Reset sprint to pending |

Options: `--parallel N`, `--timeout S`, `--plan FILE`, `--telegram-token`, `--telegram-chat`.

## Architecture

```
SKILL.md                        — Entry point, startup checklist
superflow-enforcement.md        — Durable rules (→ ~/.claude/rules/)
references/
  phase0-onboarding.md          — Router (detection + stage loading)
  phase0/                       — 5 modular stage files + greenfield path
  phase1-discovery.md           — Interactive brainstorming + spec + plan
  phase2-execution.md           — Autonomous sprint execution
  phase3-merge.md               — Sequential rebase merge
prompts/                        — Agent templates (implementer, reviewers, doc writers)
agents/                         — 12 agent definitions (deep/standard/fast tiers)
bin/superflow-supervisor        — Supervisor CLI
lib/                            — supervisor.py, queue.py, checkpoint.py, parallel.py, replanner.py, notifications.py
tests/                          — 235 tests
```

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent). MIT License.

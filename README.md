# superflow v4.1.1

Autonomous dev workflow for Claude Code. Describe a feature — get reviewed PRs.

## Why

The more autonomous AI coding gets, the less you see what's happening. Telegram integrations, remote sessions — you're no longer watching every line. That's powerful, but it needs structure.

Superflow gives that structure: a 4-phase workflow that takes a feature from idea to merged PRs. You brainstorm together, approve a plan, then walk away. The agent executes sprints, writes tests, runs cross-model reviews, creates PRs. You come back to reviewed code ready to merge.

## How It Works

```
You: "superflow — upgrade analytics"
Agent: [Phase 0: skip — already onboarded]
Agent: [Phase 1: research → brainstorm → spec → plan] "4 sprints. Go?"
You: "go"
Agent: [Phase 2: autonomous execution via subagents]
  [Sprint 1 done → PR #51]
  [Sprint 2 done → PR #52]
  [Sprint 3 done → PR #53]
  [Sprint 4 done → PR #54]
Agent: "All sprints complete. Say 'merge'."
You: "merge"
Agent: [Phase 3: docs → merge → cleanup]
```

**Phase 0 — Onboarding.** Auto-detects your stack, runs 5 parallel audit agents, sets up docs and permissions. Once per project.

**Phase 1 — Discovery.** Expert panel brainstorming (parallel persona agents produce a Board Memo), governance mode selection, spec and plan with dual-model review. Generates an Autonomy Charter before execution.

**Phase 2 — Execution.** Fully autonomous. Governance-aware review tiering (light/standard/critical), charter compliance checks, wave-based parallel dispatch, PR per sprint.

**Phase 3 — Merge.** You say "merge" — sequential rebase merge with CI checks and doc updates.

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
- **GitHub CLI** (`gh`)
- **Secondary provider** (optional): Codex, Gemini CLI, or other
- **macOS**: `brew install coreutils` for `gtimeout`

## Architecture

```
SKILL.md                        — Entry point, startup checklist
superflow-enforcement.md        — Durable rules (→ ~/.claude/rules/)
references/
  phase0-onboarding.md          — Router (detection + stage loading)
  phase0/                       — 5 modular stage files + greenfield path
  phase1-discovery.md           — Expert panel, governance, charter
  phase2-execution.md           — Governance-aware execution
  phase3-merge.md               — Sequential rebase merge
prompts/                        — Agent templates (8 prompts)
agents/                         — 12 agent definitions (deep/standard/fast tiers)
```

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent). MIT License.

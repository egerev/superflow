# superflow v5.2.2

Autonomous dev workflow for Claude Code. Describe a feature — get reviewed PRs.

## Why

The more autonomous AI coding gets, the less you see what's happening. Telegram integrations, remote sessions — you're no longer watching every line. That's powerful, but it needs structure.

Superflow gives that structure: a 4-phase workflow that takes a feature from idea to merged PRs. You brainstorm together, choose the right governance and git workflow, approve a plan, then walk away. The agent executes sprints, writes tests, runs cross-model reviews, creates PRs according to the selected branch/PR strategy. You come back to reviewed code ready to merge.

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

**Phase 1 — Discovery.** Expert panel brainstorming (parallel persona agents produce a Board Memo), governance mode selection, git workflow mode selection, Product Vision alignment with recommendations/tradeoffs and a "do what you recommend" shortcut, spec and plan with dual-model review. Generates an Autonomy Charter before execution.

**Phase 2 — Execution.** Fully autonomous. Governance-aware review tiering (light/standard/critical), selected git workflow mode (`solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, or `trunk_based`), charter compliance checks, wave-based parallel dispatch, per-PR documentation updates, codebase hygiene checks (duplication, type redefinition, dead code).

**Phase 3 — Merge.** You say "merge" — sequential rebase merge with CI checks and doc updates.

## When to Use

**Good fit:** Multi-file features, new subsystems, refactors — anything that benefits from a plan and review cycle.

**Not a good fit:** Quick fixes, single-file changes. Just use Claude Code directly.

## Install

**Option A — Git (recommended, auto-updates with `git pull`):**
```bash
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow
```

**Option B — [Download .skill package](https://github.com/egerev/superflow/releases/latest/download/superflow.skill):**
```bash
curl -LO https://github.com/egerev/superflow/releases/latest/download/superflow.skill
unzip superflow.skill -d ~/.claude/skills/
```

Phase 0 runs automatically on first `/superflow` — sets up permissions, hooks, and documentation.

### Permissions

Phase 0 auto-generates the full permission list for your stack. To set up manually, add to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(git *)", "Bash(gh *)", "Bash(ls *)", "Bash(cat *)",
      "Bash(find *)", "Bash(jq *)", "Bash(sed *)", "Bash(awk *)",
      "Bash(mkdir *)", "Bash(cp *)", "Bash(mv *)",
      "Bash(codex *)", "Bash(timeout *)", "Bash(gtimeout *)",
      "Bash(python3 *)", "Bash(node *)",
      "Bash(npm *)", "Bash(pip *)", "Bash(pytest *)", "Bash(ruff *)"
    ]
  }
}
```

Core permissions (git, gh, shell utils, codex, timeout) are always needed. Stack-specific ones (npm/pip/pytest/ruff/bundle/cargo/docker) are added based on detected stack — [see Stage 4 Setup](references/phase0/stage4-setup.md).

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

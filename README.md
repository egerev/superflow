# superflow v3.3.0

Lightweight Claude Code skill for autonomous product-to-production development. Designed for modern models (Opus 4.6+) — minimal instructions, maximum autonomy.

**Philosophy:** Many AI coding skills are heavyweight — hundreds of rules that fill context and degrade quality. Superflow trusts the model and keeps instructions minimal. Instead of preventing errors with verbose rules, it catches them through cross-model reviews (Claude + secondary provider). Less context overhead, better output.

## How It Works

**Phase 0 — Onboarding** (interactive, first run only). Mini-interview via AskUserQuestion, 5 parallel agents (4 Claude + Codex security audit or Claude security fallback), greenfield scaffolding for empty repos, health report, audit/create llms.txt + CLAUDE.md, propose permissions and hooks.

**Phase 1 — Discovery** (interactive, 12 steps). Research with parallel agents, brainstorming (STOP GATE), approaches, product summary (APPROVAL GATE), product brief, spec, specialized dual-model spec review (Claude=Product, Codex=Technical), plan, dual-model plan review, user approval (FINAL GATE).

**Phase 2 — Execution** (autonomous, zero interaction, 10 steps per sprint). PR per sprint, git worktrees, baseline test gate, specialized 2-agent review (Claude Product + Codex Technical — no duplication), PAR evidence validation with retry, milestone checkpoints, holistic review gate before completion report. Reports results in Demo Day format.

**Phase 3 — Merge** (interactive, user-initiated). 3-stage process: pre-merge checklist with doc updates, sequential rebase merges with CI failure recovery, post-merge report with cleanup.

```
You: "superflow — upgrade analytics"
Agent: [Phase 0: skip — already onboarded]
Agent: [Phase 1: research → brainstorm → brief → spec → plan] "4 sprints, 28 steps. Go?"
You: "go"
Agent: [Phase 2: Sprint 1 → PR #1 → Sprint 2 → PR #2 → Sprint 3 → PR #3 → Sprint 4 → PR #4]
Agent: "Done. 4 PRs ready. Say 'merge' to start Phase 3."
You: "merge"
Agent: [Phase 3: update docs → merge PRs → cleanup]
```

## When to Use

**Good fit:** Multi-file features, new subsystems, architectural refactors (5+ files, needs a plan).

**Not a good fit:** Quick fixes, config tweaks, single-file changes. Just use Claude Code directly.

## Key Behaviors

- **PR per sprint** — small, reviewable, deployable
- **Git worktrees** — isolated workspace per sprint
- **TDD** — write failing test → verify fail → implement → verify pass
- **2-agent specialized review** — Claude Product + Codex Technical (specialize, don't duplicate), or 2 Claude split-focus fallback
- **Review gate** — unified review before every push, `.par-evidence.json` required
- **llms.txt** — standard project documentation for all LLMs (llmstxt.org)
- **Product brief** — Jobs to be Done + user stories before technical spec
- **Verification discipline** — no claims without pasted test output
- **Max parallelism** — parallelize independent tasks, sequentialize dependent ones
- **Agent definitions with effort frontmatter** — CLAUDE.md and llms.txt audits use deep-doc-writer agent tier to prevent hallucinated documentation

## Install

```bash
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow
```

Phase 0 will automatically verify that `superflow-enforcement.md` is copied to `~/.claude/rules/` on first run. If missing, it copies it for you.

### Recommended Permissions

Add to `~/.claude/settings.json` for fully autonomous Phase 2 execution **without** `--dangerously-skip-permissions`:

```json
{
  "permissions": {
    "allow": [
      "Bash(git worktree *)", "Bash(git checkout *)", "Bash(git add *)",
      "Bash(git commit *)", "Bash(git push *)", "Bash(git push --force-with-lease *)",
      "Bash(git rebase *)", "Bash(git pull *)", "Bash(git check-ignore *)",
      "Bash(git log *)", "Bash(git diff *)",
      "Bash(gh pr *)",
      "Bash(npm test *)", "Bash(npm run *)",
      "Bash(codex *)", "Bash(gemini *)", "Bash(aider *)",
      "Bash(gtimeout *)", "Bash(timeout *)"
    ]
  }
}
```

Adapt to your toolchain — replace `npm` with `yarn`/`bun`/`pnpm` as needed. Phase 0 will propose these permissions automatically on first run.

This is the **safer alternative** to `--dangerously-skip-permissions` — Superflow gets autonomy for exactly the commands it needs, nothing more.

### Alternative: Full Skip Permissions

If you prefer zero prompts and accept the risk:

```bash
claude --dangerously-skip-permissions
```

**Safety:** Only use inside an isolated environment — Docker container or VPS. Never on a machine with sensitive data outside the project directory.

```bash
# Docker example
docker run -it --rm -v $(pwd):/workspace -w /workspace node:22 bash
# install claude, then: claude --dangerously-skip-permissions
```

## Requirements

- **Python 3.10+** (for supervisor features)
- **Claude Code CLI**
- **Secondary provider** (optional): Codex (`npm i -g @openai/codex`), Gemini CLI, or other
- **GitHub CLI** (`gh`)
- **macOS**: `brew install coreutils` for `gtimeout`

## Supervisor

The Supervisor is a Python companion CLI that orchestrates autonomous multi-sprint execution. It manages a sprint queue with DAG-based dependency resolution, creates isolated git worktrees per sprint, invokes Claude Code for each sprint, handles retries and failure recovery, and generates completion reports. Supports parallel execution of independent sprints and adaptive replanning between sprints.

### Quick Start

```bash
./bin/superflow-supervisor run --queue path/to/sprint-queue.json
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `run --queue Q` | Execute the full sprint queue |
| `status --queue Q` | Show current queue status table |
| `resume --queue Q` | Resume after crash (detects PRs, resets stale sprints) |
| `reset --queue Q --sprint N` | Reset sprint N to pending |

Options: `--parallel N` (max concurrent sprints), `--timeout S` (seconds per sprint), `--plan FILE` (enable replanning), `--no-replan`, `--telegram-token`, `--telegram-chat`.

### Example: Overnight Run with Telegram

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

./bin/superflow-supervisor run \
  --queue sprint-queue.json \
  --plan plans/feature-plan.md \
  --parallel 2 \
  --timeout 3600
```

You will receive Telegram notifications for sprint starts, completions, failures, and the final completion report.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Thin router — startup checklist, phase references |
| `references/phase0-onboarding.md` | First-run onboarding (interactive) |
| `references/phase1-discovery.md` | Product discovery (interactive) |
| `references/phase2-execution.md` | Sprint execution (autonomous) |
| `references/phase3-merge.md` | Merge flow (user-initiated) |
| `prompts/*.md` | Agent templates (implementer, reviewers, doc writers) |
| `templates/*.md` | Supervisor prompt templates (sprint execution, replanning) |
| `superflow-enforcement.md` | Durable rules (copy to `~/.claude/rules/`) |
| `bin/superflow-supervisor` | Supervisor CLI entry point |
| `lib/supervisor.py` | Core supervisor: worktree lifecycle, sprint execution, run loop |
| `lib/queue.py` | Sprint queue with DAG-based dependency resolution |
| `lib/checkpoint.py` | Checkpoint save/load for crash recovery |
| `lib/parallel.py` | Parallel sprint execution via ThreadPoolExecutor |
| `lib/replanner.py` | Adaptive replanner (adjusts remaining sprints after completion) |
| `lib/notifications.py` | Telegram/stdout notification system |
| `tests/` | Unit and integration tests (228 tests) |

## Origin

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent, MIT). Superflow has evolved into an independent skill optimized for autonomous execution with modern models.

## License

MIT

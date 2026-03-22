# superflow

Lightweight Claude Code skill for autonomous product-to-production development. Designed for modern models (Opus 4.6+) — minimal instructions, maximum autonomy.

**Philosophy:** Many AI coding skills are heavyweight — hundreds of rules that fill context and degrade quality. Superflow trusts the model and keeps instructions minimal. Instead of preventing errors with verbose rules, it catches them through cross-model reviews (Claude + secondary provider). Less context overhead, better output.

## How It Works

**Phase 1 — You talk, agent proposes.** Collaborative product discovery: research, brainstorming, spec, plan. ~15-20 min.

**Phase 2 — Agent executes autonomously.** PR per sprint, git worktrees, dual-model reviews, TDD. Zero interaction until done.

```
You: "superflow — upgrade analytics"
Agent: [research → brainstorm → spec → plan] "4 sprints, 28 steps. Go?"
You: "go"
Agent: [Sprint 1 → PR #1] [Sprint 2 → PR #2] [Sprint 3 → PR #3] [Sprint 4 → PR #4]
Agent: "Done. 4 PRs ready, merge in order."
```

## When to Use

**Good fit:** Multi-file features, new subsystems, architectural refactors (5+ files, needs a plan).

**Not a good fit:** Quick fixes, config tweaks, single-file changes. Just use Claude Code directly.

## Key Behaviors

- **PR per sprint** — small, reviewable, deployable
- **Git worktrees** — isolated workspace per sprint
- **TDD** — write failing test → verify fail → implement → verify pass
- **Dual-model reviews** — Claude + secondary provider (Codex/Gemini/other); split-focus Claude fallback
- **PAR gate** — Product Acceptance Review before every push, `.par-evidence.json` required
- **Verification discipline** — no claims without pasted test output
- **Root cause debugging** — investigate before fixing; 3+ failed fixes = question architecture
- **Max parallelism** — parallelize independent tasks, sequentialize dependent ones

## Install

```bash
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow
```

Copy `superflow-enforcement.md` to `~/.claude/rules/` (survives context compaction).

## Requirements

- **Claude Code CLI**
- **Secondary provider** (optional): Codex (`npm i -g @openai/codex`), Gemini CLI, or other
- **GitHub CLI** (`gh`)
- **macOS**: `brew install coreutils` for `gtimeout`

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Thin router — startup checklist, phase references |
| `references/phase1-discovery.md` | 10-step discovery checklist |
| `references/phase2-execution.md` | Sprint execution flow |
| `prompts/*.md` | Agent templates (implementer, 3 reviewers, testing) |
| `~/.claude/rules/superflow-enforcement.md` | Durable rules (survives compaction) |

## Origin

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent, MIT). Superflow has evolved into an independent skill optimized for autonomous execution with modern models.

## License

MIT

# SuperFlow

A Claude Code skill for product-to-production development workflow with autonomous execution.

## What it does

Two-phase workflow:

**Phase 1 — Product Discovery (collaborative with user):**
- Best practices research (parallel agents)
- Multi-expert brainstorming (product + architecture + domain lenses)
- Proactive suggestions, not just questions
- Spec and plan with dual-provider review (Claude + Codex in parallel)

**Phase 2 — Autonomous Execution (zero interaction until done):**
- PR per sprint (not one giant PR)
- Maximum parallel agents
- Per-task: spec review → code quality review (Claude + Codex)
- Per-sprint: product acceptance review (Claude + Codex)
- Fixes issues autonomously, reports when all PRs are ready

## Install

```bash
# Add to Claude Code
claude skill add /path/to/superflow
# or symlink
ln -s /path/to/superflow ~/.claude/skills/superflow
```

## Usage

Say `superflow` or `суперфлоу` in Claude Code to activate.

## Key Rules

1. **NEVER pause** during autonomous execution
2. **ALWAYS use Codex** for reviews (parallel with Claude)
3. **PR per sprint** — never accumulate 20 commits in one PR
4. **Maximum parallelism** — 5 agents if 5 tasks are independent
5. **Proactive product thinking** — propose ideas, don't just ask questions

## Requirements

- Claude Code CLI
- Codex CLI (`npm install -g @openai/codex`) — optional but recommended for dual-provider reviews
- `OPENAI_API_KEY` env var (for Codex)

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill definition (loaded by Claude Code) |
| `product-reviewer-prompt.md` | Product review agent template |
| `codex-dispatch.md` | Codex invocation patterns |

## Born from real usage

This skill was developed during a real session building a financial analytics engine (16 tasks, 4 sprints, 488 tests). Every rule exists because something went wrong without it:

- "Never pause" — user had to ask 3 times to stop confirming
- "PR per sprint" — 20-commit PR was too big to review
- "Always use Codex" — rule existed but wasn't enforced, so it was never used
- "Proactive product thinking" — brainstorming was one-sided (questions only, no suggestions)
- "Product acceptance review" — code passed technical review but missed product intent

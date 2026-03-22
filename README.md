# superflow v2.1.0

Lightweight Claude Code skill for autonomous product-to-production development. Designed for modern models (Opus 4.6+) — minimal instructions, maximum autonomy.

**Philosophy:** Many AI coding skills are heavyweight — hundreds of rules that fill context and degrade quality. Superflow trusts the model and keeps instructions minimal. Instead of preventing errors with verbose rules, it catches them through cross-model reviews (Claude + secondary provider). Less context overhead, better output.

## How It Works

**Phase 0 — Onboarding** (interactive, first run only, 10 steps). 4 parallel Opus agents analyze the project, audit/create `llms.txt` + `CLAUDE.md` (Opus + ultrathink), produce health report, propose permissions. Skipped on subsequent runs (marker detection with backwards compatibility).

**Phase 1 — Discovery** (interactive, 12 steps). Research with parallel agents, brainstorming (STOP GATE), approaches, product summary (APPROVAL GATE), product brief, spec, dual-model spec review, plan, dual-model plan review, user approval (FINAL GATE).

**Phase 2 — Execution** (autonomous, zero interaction, 11 steps per sprint). PR per sprint, git worktrees, internal review + mandatory PAR, sprint completion checklist. Reports results in Demo Day format.

**Phase 3 — Merge** (interactive, user-initiated). Pre-merge checklist, doc update, sequential rebase merges with CI failure recovery, post-merge report.

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
- **Dual-model reviews** — Claude + secondary provider (Codex/Gemini/other); split-focus Claude fallback
- **PAR gate** — Product Acceptance Review before every push, `.par-evidence.json` required
- **llms.txt** — standard project documentation for all LLMs (llmstxt.org)
- **Product brief** — Jobs to be Done + user stories before technical spec
- **Verification discipline** — no claims without pasted test output
- **Max parallelism** — parallelize independent tasks, sequentialize dependent ones
- **Opus + ultrathink for docs** — CLAUDE.md and llms.txt audits use highest quality models to prevent hallucinated documentation

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

- **Claude Code CLI**
- **Secondary provider** (optional): Codex (`npm i -g @openai/codex`), Gemini CLI, or other
- **GitHub CLI** (`gh`)
- **macOS**: `brew install coreutils` for `gtimeout`

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Thin router — startup checklist, phase references |
| `references/phase0-onboarding.md` | First-run onboarding (interactive) |
| `references/phase1-discovery.md` | Product discovery (interactive) |
| `references/phase2-execution.md` | Sprint execution (autonomous) |
| `references/phase3-merge.md` | Merge flow (user-initiated) |
| `prompts/*.md` | Agent templates (implementer, reviewers, doc writers) |
| `superflow-enforcement.md` | Durable rules (copy to `~/.claude/rules/`) |

## Origin

Originally inspired by [Superpowers](https://github.com/obra/superpowers) (Jesse Vincent, MIT). Superflow has evolved into an independent skill optimized for autonomous execution with modern models.

## License

MIT

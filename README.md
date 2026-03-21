# SuperFlow

A Claude Code skill for autonomous product-to-production development. Combines collaborative product discovery with fully autonomous execution — you discuss what to build, then the agent builds it end-to-end without stopping.

## The Idea

Most AI coding workflows are either too hands-on (you babysit every step) or too hands-off (agent builds the wrong thing). SuperFlow splits the work into two phases:

**Phase 1 — You talk, agent listens and proposes.** Freeflow product conversation with research, expert lenses, and proactive suggestions. The agent doesn't just ask questions — it proposes ideas, challenges assumptions, and brings best practices from the domain. This phase takes time, and that's intentional.

**Phase 2 — You say "go", agent executes autonomously.** Zero interaction until done. The agent creates a PR per sprint, uses parallel subagents for implementation, runs dual-provider reviews (Claude + Codex), and does product acceptance testing. You get a report with ready-to-merge PRs at the end.

## What a Session Looks Like

```
You: "суперфлоу — хочу прокачать аналитику в финтрекере"

Agent: [silently reads codebase, launches research agents]
Agent: [asks about your vision, proposes ideas from competitor analysis]
Agent: [presents 2-3 approaches, recommends one]
Agent: [presents design section by section]
Agent: [writes spec, reviews with Claude + Codex in parallel, fixes issues]
Agent: [writes implementation plan, reviews, fixes]
Agent: "Plan ready — 4 sprints, 16 tasks, ~4 PRs. Go?"

You: "давай"

Agent: [executes Sprint 1 → creates PR #1]
        [executes Sprint 2 → creates PR #2]
        [executes Sprint 3 → creates PR #3]
        [executes Sprint 4 → creates PR #4]

Agent: "Done. 4 PRs ready:
        #169 — Balance Engine (488 tests passing)
        #170 — Analytics API
        #171 — Bot Tools v3
        #172 — Dashboard Overhaul
        Merge in order: #169 → #170 → #171 → #172"
```

## Phase 1: Product Discovery (10 steps)

| # | Step | You involved? |
|---|------|:---:|
| 1 | Context exploration (code, docs, git) | No |
| 2 | Best practices research (parallel agents) | No |
| 3 | Multi-expert brainstorming | **Yes — dialog** |
| 4 | Approaches + recommendation | **Yes — choice** |
| 5 | Design presentation | **Yes — discussion** |
| 6 | Write spec document | No |
| 7 | Spec review (Claude + Codex parallel) | No |
| 8 | Write implementation plan | No |
| 9 | Plan review (Claude + Codex parallel) | No |
| 10 | Your approval to start | **Yes — "go"** |

4 interactive steps, 6 autonomous. Your involvement is one continuous conversation (steps 3-5) plus one "go" (step 10).

### Brainstorming Style

Freeflow with product focus — not a rigid checklist. The agent:
- Asks about your **vision** before technical details (WHY before HOW)
- Requests **references** (apps, screenshots, competitors)
- Uses a **question → proposal → question** rhythm: asks a few questions, then proposes ideas based on answers + research, then follows up on your reactions
- Adapts depth to complexity: 1 cycle for a simple feature, 3-4 for a major overhaul
- Weaves in three expert lenses naturally: product, architecture, domain

## Phase 2: Autonomous Execution

After "go", the agent runs continuously without interaction:

```
For each Sprint:
├── Create branch: feat/<feature>-sprint-N
├── Implement tasks (maximum parallel agents)
│   ├── Per task: implement → spec review → code quality review (Claude + Codex)
│   └── Fix issues autonomously
├── Product Acceptance Review (Claude + Codex parallel)
│   └── Verify implementation matches spec intent, not just technical requirements
├── Run tests, push, create PR
└── Start next sprint immediately
```

### Key Behaviors

- **PR per sprint** — never one giant PR. Each is reviewable and deployable independently
- **Max parallelism** — 5 agents if 5 tasks are independent. Never serialize independent work
- **Dual-provider reviews** — Claude + Codex review in parallel. Different models catch different bugs
- **Product acceptance** — after code review passes, product agents verify the implementation matches the *intent* of the spec, not just the letter. Code can be technically clean but productively wrong
- **Never stops** — accumulates issues and reports at the end. Never asks "should I continue?"

## 5 Rules

1. **NEVER pause** during autonomous execution
2. **ALWAYS use Codex** for reviews (parallel with Claude)
3. **PR per sprint** — smaller PRs, easier to review
4. **Maximum parallelism** — use all available agents
5. **Proactive product thinking** — propose ideas, don't just ask questions

## Install

```bash
# Option 1: Clone and symlink
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow

# Option 2: Just copy files
mkdir -p ~/.claude/skills/superflow
cp superflow/SKILL.md ~/.claude/skills/superflow/
cp superflow/product-reviewer-prompt.md ~/.claude/skills/superflow/
cp superflow/codex-dispatch.md ~/.claude/skills/superflow/
```

## Requirements

- **Claude Code CLI** — the host environment
- **Codex CLI** (optional but recommended) — `npm install -g @openai/codex` + `OPENAI_API_KEY` env var. Enables dual-provider reviews. Without it, reviews are Claude-only
- **GitHub CLI** (`gh`) — for PR creation

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill definition — loaded by Claude Code |
| `product-reviewer-prompt.md` | Product review agent template |
| `codex-dispatch.md` | Codex CLI invocation patterns |

## Origin

Built during a real session: analytics engine for a family finance tracker. 16 tasks, 4 sprints, 20 commits, 488 tests — in one conversation. Every rule exists because something went wrong without it:

| Rule | Why it exists |
|------|--------------|
| Never pause | User had to ask 3 times to stop confirming |
| PR per sprint | 20-commit PR was too big to review |
| Always use Codex | Rule existed but wasn't enforced — Codex was never invoked |
| Proactive thinking | Brainstorming was one-sided — only questions, no proposals |
| Product acceptance | Code passed technical review but missed product intent |

## License

MIT

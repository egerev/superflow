# SuperFlow

A Claude Code skill for autonomous product-to-production development. Combines collaborative product discovery with fully autonomous execution — you discuss what to build, then the agent builds it end-to-end without stopping.

## The Idea

Most AI coding workflows are either too hands-on (you babysit every step) or too hands-off (agent builds the wrong thing). SuperFlow splits the work into two phases:

**Phase 1 — You talk, agent listens and proposes.** Freeflow product conversation with research, expert lenses, and proactive suggestions. The agent doesn't just ask questions — it proposes ideas, challenges assumptions, and brings best practices from the domain. This phase takes time, and that's intentional.

**Phase 2 — You say "go", agent executes autonomously.** Zero interaction until done. The agent creates a PR per sprint using git worktrees for isolation, uses parallel subagents for implementation, runs dual-provider reviews (Claude + Codex), enforces test-first development, requires verification evidence before any completion claim, and does product acceptance testing. You get a report with ready-to-merge PRs at the end.

## What a Session Looks Like

```
You: "superflow — I want to upgrade analytics in fintracker"

Agent: [silently reads codebase, launches research agents]
Agent: [asks about your vision, proposes ideas from competitor analysis]
Agent: [presents 2-3 approaches, recommends one]
Agent: [presents design section by section]
Agent: [writes spec, reviews with Claude + Codex in parallel, fixes issues]
Agent: [writes implementation plan with bite-sized steps, reviews, fixes]
Agent: "Plan ready — 4 sprints, 28 steps, ~4 PRs. Go?"

You: "go"

Agent: [creates worktree, executes Sprint 1 → verifies tests → creates PR #1]
        [creates worktree, executes Sprint 2 → verifies tests → creates PR #2]
        [creates worktree, executes Sprint 3 → verifies tests → creates PR #3]
        [creates worktree, executes Sprint 4 → verifies tests → creates PR #4]

Agent: "Done. 4 PRs ready:
        #169 — Balance Engine (488 tests passing — verified)
        #170 — Analytics API (all green — verified)
        #171 — Bot Tools v3 (all green — verified)
        #172 — Dashboard Overhaul (all green — verified)
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
| 8 | Write implementation plan (bite-sized steps) | No |
| 9 | Plan review (Claude + Codex parallel) | No |
| 10 | Your approval to start | **Yes — "go"** |

4 interactive steps, 6 autonomous. Your involvement is one continuous conversation (steps 3-5) plus one "go" (step 10).

### Brainstorming Style

Freeflow with product focus — not a rigid checklist. The agent:
- Asks about your **vision** before technical details (WHY before HOW)
- Requests **references** (apps, screenshots, competitors)
- Uses a **question -> proposal -> question** rhythm: asks a few questions, then proposes ideas based on answers + research, then follows up on your reactions
- Adapts depth to complexity: 1 cycle for a simple feature, 3-4 for a major overhaul
- Weaves in three expert lenses naturally: product, architecture, domain

## Phase 2: Autonomous Execution

After "go", the agent runs continuously without interaction:

```
For each Sprint:
+-- Create git worktree: .worktrees/sprint-N (isolated environment)
+-- Run baseline tests (verify clean starting state)
+-- Implement tasks (maximum parallel agents, TDD cycle)
|   +-- Per task: write failing test -> verify fail -> implement -> verify pass
|   +-- Spec review -> code quality review (Claude + Codex)
|   +-- Verify: run tests, paste output as evidence
+-- Product Acceptance Review (Claude + Codex parallel)
|   +-- Verify implementation matches spec intent
+-- Run full test suite, push, create PR
+-- Clean up worktree
+-- Start next sprint immediately
```

### Key Behaviors

- **PR per sprint** — never one giant PR. Each is reviewable and deployable independently
- **Git worktrees** — each sprint runs in an isolated worktree for safety
- **Test-first development** — write failing test, verify failure, implement, verify pass. Never skip steps
- **Verification discipline** — no completion claims without actual test output as evidence
- **Max parallelism** — 5 agents if 5 tasks are independent. Never serialize independent work
- **Dual-provider reviews** — Claude + Codex review in parallel. Different models catch different bugs
- **Product acceptance** — after code review passes, product agents verify the implementation matches the *intent* of the spec
- **Systematic debugging** — when tests fail, investigate root cause before attempting fixes
- **Never stops** — accumulates issues and reports at the end. Never asks "should I continue?"

## 6 Rules

1. **NEVER pause** during autonomous execution
2. **ALWAYS use Codex** for reviews (parallel with Claude)
3. **PR per sprint** — smaller PRs, easier to review
4. **Maximum parallelism** — use all available agents
5. **Proactive product thinking** — propose ideas, don't just ask questions
6. **No claims without evidence** — verification output required for every completion

## Install

```bash
# Option 1: Clone and symlink
git clone https://github.com/egerev/superflow.git
ln -s $(pwd)/superflow ~/.claude/skills/superflow

# Option 2: Just copy files
mkdir -p ~/.claude/skills/superflow/prompts
cp superflow/SKILL.md ~/.claude/skills/superflow/
cp superflow/prompts/*.md ~/.claude/skills/superflow/prompts/
```

## Requirements

- **Claude Code CLI** — the host environment
- **Codex CLI** (optional but recommended) — `npm install -g @openai/codex` + `OPENAI_API_KEY` env var. Enables dual-provider reviews. Without it, reviews are Claude-only
- **GitHub CLI** (`gh`) — for PR creation

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill definition — orchestrator loaded by Claude Code |
| `prompts/implementer.md` | Implementation agent template with TDD enforcement |
| `prompts/spec-reviewer.md` | Spec compliance reviewer with calibration rules |
| `prompts/code-quality-reviewer.md` | Code quality reviewer with anti-noise rules + Codex template |
| `prompts/product-reviewer.md` | Product acceptance reviewer + Codex template |
| `prompts/testing-guidelines.md` | Testing anti-patterns and best practices reference |

## Acknowledgements

SuperFlow is built on top of [Superpowers](https://github.com/obra/superpowers) — a community-built Claude Code skill framework ([info](https://claude.com/plugins/superpowers)). Many core patterns come directly from Superpowers:

- **Brainstorming flow** (question-driven design exploration)
- **Subagent-driven development** (fresh agent per task + review stages)
- **Test-driven development** (Red-Green-Refactor cycle)
- **Verification discipline** ("evidence before claims" iron law)
- **Git worktrees** (sprint isolation)
- **Systematic debugging** (root cause before fix)
- **Plan document structure** (bite-sized tasks, TDD steps)

SuperFlow extends and overrides Superpowers with: autonomous execution (zero pauses), PR-per-sprint, Codex dual-provider reviews, product acceptance gates, best practices research, proactive product suggestions, and context drift prevention.

## Origin

Built during a real session: analytics engine for a family finance tracker. 16 tasks, 4 sprints, 20 commits, 488 tests — in one conversation. Every rule exists because something went wrong without it:

| Rule | Why it exists |
|------|--------------|
| Never pause | User had to ask 3 times to stop confirming |
| PR per sprint | 20-commit PR was too big to review |
| Always use Codex | Rule existed but wasn't enforced — Codex was never invoked |
| Proactive thinking | Brainstorming was one-sided — only questions, no proposals |
| Product acceptance | Code passed technical review but missed product intent |
| Verification evidence | Agent claimed "tests pass" without running them |
| Git worktrees | Sprint branches interfered with each other during parallel work |
| Systematic debugging | Agent tried random fixes instead of investigating root cause |

## License

MIT

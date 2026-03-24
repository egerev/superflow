# Superflow — Claude Instructions

## Project Overview
Superflow is a Claude Code skill (hybrid: Markdown prompts + Python companion CLI) that orchestrates a 4-phase dev workflow: onboarding, product discovery, autonomous execution, merge. The Python supervisor enables multi-hour autonomous sprint execution outside Claude's context window. v3.3.1, MIT License.

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, ~118 lines)
  ├── superflow-enforcement.md (durable rules → ~/.claude/rules/)
  ├── references/
  │   ├── phase0-onboarding.md (router — detection, recovery matrix, stage loading)
  │   ├── phase0/
  │   │   ├── stage1-detect.md (parallel preflight, auto-detection, confirmation)
  │   │   ├── stage2-analysis.md (5 parallel agents, tiered model usage)
  │   │   ├── stage3-report.md (health report, informative summary, approval)
  │   │   ├── stage4-setup.md (3 concurrent branches, strict file ownership)
  │   │   ├── stage5-completion.md (markers, tech debt persistence, restart)
  │   │   └── greenfield.md (empty project path, G1-G6)
  │   ├── phase1-discovery.md (interactive, 11 steps, merged approval gate)
  │   ├── phase2-execution.md (autonomous, 11 steps/sprint + wave-based parallel dispatch + holistic review)
  │   └── phase3-merge.md (user-initiated merge, 3 stages)
  ├── prompts/
  │   ├── implementer.md (TDD code agent)
  │   ├── spec-reviewer.md (spec compliance)
  │   ├── code-quality-reviewer.md (correctness/security)
  │   ├── product-reviewer.md (user perspective)
  │   ├── llms-txt-writer.md (llms.txt generation)
  │   ├── claude-md-writer.md (CLAUDE.md generation)
  │   ├── testing-guidelines.md (TDD reference)
  │   ├── security-audit.md (Claude security fallback for Phase 0)
  │   └── codex/ (Codex-specific prompts: code-reviewer, product-reviewer, audit)
  ├── agents/ (12 agent definitions — deep/standard/fast tiers with effort frontmatter)
  ├── bin/
  │   └── superflow-supervisor (CLI entry point)
  ├── lib/
  │   ├── supervisor.py (core: worktree lifecycle, sprint execution, run loop, state projection)
  │   ├── queue.py (DAG-based sprint queue)
  │   ├── checkpoint.py (crash recovery)
  │   ├── parallel.py (ThreadPoolExecutor concurrency + state writes)
  │   ├── replanner.py (adaptive LLM-powered replanning)
  │   └── notifications.py (Telegram + stdout)
  ├── templates/
  │   ├── supervisor-sprint-prompt.md (sprint execution template + step verification)
  │   ├── replan-prompt.md (replanner template)
  │   ├── superflow-state-schema.json (state file JSON Schema)
  │   ├── greenfield/ (stack scaffolding: nextjs.md, python.md, generic.md)
  │   └── ci/ (CI workflows: github-actions-node.yml, github-actions-python.yml)
  ├── examples/
  │   └── sprint-queue-example.json (queue template)
  └── tests/
      ├── test_supervisor.py, test_queue.py, test_replanner.py, ...
      └── test_integration.py (138 tests total)
```

Hybrid project: Markdown prompts drive Claude Code sessions; Python supervisor orchestrates multi-sprint execution with crash recovery, parallel execution, and adaptive replanning. Enforcement rules survive context compaction via `~/.claude/rules/`.

## Key Files
| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | ~126 | Entry point — startup checklist, provider detection, state management, phase routing |
| `superflow-enforcement.md` | 80 | 9 hard rules, specialized 2-agent reviews (Claude=Product, secondary=Technical), rationalization prevention, phase gates |
| `references/phase0-onboarding.md` | ~80 | Router — detection, recovery matrix, stage loading |
| `references/phase0/stage1-detect.md` | ~214 | Parallel preflight, auto-detection, confirmation |
| `references/phase0/stage2-analysis.md` | ~256 | 5 parallel agents, tiered model usage |
| `references/phase0/stage3-report.md` | ~179 | Health report, informative summary, approval |
| `references/phase0/stage4-setup.md` | ~238 | 3 concurrent branches, strict file ownership |
| `references/phase0/stage5-completion.md` | ~163 | Markers, tech debt persistence, restart |
| `references/phase0/greenfield.md` | ~350 | Greenfield path G1-G6 |
| `references/phase1-discovery.md` | 263 | 11 steps, 5 stages, merged Product Approval gate, specialized reviews (Claude=Product, Codex=Technical) |
| `references/phase2-execution.md` | 293 | Per-sprint stages, 2-agent specialized review (Claude Product + Codex Technical), holistic review |
| `references/phase3-merge.md` | 184 | 3 stages, sequential rebase merge with CI gate |
| `prompts/implementer.md` | 81 | Red-Green-Refactor TDD cycle for code agents |
| `prompts/llms-txt-writer.md` | 154 | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | 148 | Verified paths/commands, <200 lines target |
| `bin/superflow-supervisor` | 148 | CLI: run, status, resume, reset commands |
| `lib/supervisor.py` | 1749 (~1370 LOC) | Core supervisor: worktree lifecycle, sprint execution, run loop, validation gates, holistic review |
| `lib/queue.py` | 122 (~105 LOC) | Sprint queue with DAG dependency resolution, atomic saves, baseline_cmd |
| `lib/checkpoint.py` | 52 (~44 LOC) | Checkpoint save/load for crash recovery, string IDs, named checkpoints |
| `lib/parallel.py` | 61 (~50 LOC) | ThreadPoolExecutor concurrency with queue_lock |
| `lib/replanner.py` | 212 (~168 LOC) | Adaptive replanner — adjusts remaining sprints via Claude |
| `lib/notifications.py` | 159 (~130 LOC) | Telegram Bot API + stdout fallback, 16 event types |
| `templates/supervisor-sprint-prompt.md` | 58 | Sprint execution prompt + baseline_status, frontend_instructions, enforcement |
| `templates/replan-prompt.md` | 26 | Replanner prompt with placeholders |
| `templates/superflow-state-schema.json` | ~70 | JSON Schema for .superflow-state.json |
| `examples/sprint-queue-example.json` | 45 | Queue file template for new users |
| `tests/` | ~5134 | 228 tests: unit (all modules) + integration (happy path, crash, retry) |

## Conventions
- Hybrid project: Markdown skill files (no dependencies) + Python supervisor (stdlib only, no pip install)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding
- All phases use stage/todo structure with TaskCreate for progress tracking
- `.superflow-state.json` persists phase/stage for crash recovery (gitignored)

## Known Issues & Tech Debt
- TDD cycle duplicated in `implementer.md:23-31` and `testing-guidelines.md:13-21` (agent sees it twice since implementer includes testing-guidelines)
- Permissions JSON: single-sourced in `references/phase0/stage4-setup.md` (Branch B); `README.md` has a short example with a link to the canonical source
- Greenfield templates (nextjs.md, python.md) provide config files but not source file contents — LLM generates those
- `_verify_steps()` is advisory-only (warns but does not block incomplete sprints)

<!-- updated-by-superflow:2026-03-24 -->

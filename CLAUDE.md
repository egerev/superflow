# Superflow — Claude Instructions

## Project Overview
Superflow is a Claude Code skill (hybrid: Markdown prompts + Python companion CLI) that orchestrates a 4-phase dev workflow: onboarding, product discovery, autonomous execution, merge. The Python supervisor enables multi-hour autonomous sprint execution outside Claude's context window. v4.0.0, MIT License.

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, ~142 lines)
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
  │   ├── phase1-discovery.md (interactive, expert panel brainstorming, governance mode selection, charter generation)
  │   ├── phase2-execution.md (autonomous, governance-aware review tiering, Popen-based execution, holistic review)
  │   └── phase3-merge.md (user-initiated merge, 3 stages)
  ├── prompts/
  │   ├── implementer.md (TDD code agent)
  │   ├── expert-panel.md (expert persona prompt for brainstorming)
  │   ├── spec-reviewer.md (spec compliance)
  │   ├── code-quality-reviewer.md (correctness/security + charter compliance)
  │   ├── product-reviewer.md (user perspective + charter compliance)
  │   ├── llms-txt-writer.md (llms.txt generation)
  │   ├── claude-md-writer.md (CLAUDE.md generation)
  │   ├── testing-guidelines.md (TDD reference)
  │   ├── security-audit.md (Claude security fallback for Phase 0)
  │   └── codex/ (Codex-specific prompts: code-reviewer, product-reviewer, audit)
  ├── agents/ (12 agent definitions — deep/standard/fast tiers with effort frontmatter)
  ├── bin/
  │   └── superflow-supervisor (CLI entry point)
  ├── lib/
  │   ├── supervisor.py (core: worktree lifecycle, Popen execution, charter injection, progress polling, digest)
  │   ├── queue.py (DAG-based sprint queue + metadata dict)
  │   ├── planner.py (plan-to-queue + charter-to-queue generator)
  │   ├── launcher.py (launch/stop/status/restart supervisor as background process)
  │   ├── checkpoint.py (crash recovery)
  │   ├── parallel.py (ThreadPoolExecutor concurrency + state writes)
  │   ├── replanner.py (adaptive LLM-powered replanning + charter context)
  │   └── notifications.py (Telegram + stdout, 20 event types)
  ├── templates/
  │   ├── supervisor-sprint-prompt.md (sprint template + charter, governance, progress placeholders)
  │   ├── replan-prompt.md (replanner template + charter placeholder)
  │   ├── superflow-state-schema.json (state file JSON Schema)
  │   ├── greenfield/ (stack scaffolding: nextjs.md, python.md, generic.md)
  │   └── ci/ (CI workflows: github-actions-node.yml, github-actions-python.yml)
  ├── examples/
  │   └── sprint-queue-example.json (queue template with metadata)
  └── tests/
      ├── test_supervisor.py, test_queue.py, test_replanner.py, ...
      └── test_integration.py (362+ tests total)
```

Hybrid project: Markdown prompts drive Claude Code sessions; Python supervisor orchestrates multi-sprint execution with crash recovery, parallel execution, and adaptive replanning. Enforcement rules survive context compaction via `~/.claude/rules/`.

**Key v4.0 artifacts:**
- **Autonomy Charter** (`docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`): generated at end of Phase 1, injected into every sprint prompt, reviewer, and replanner. Contains goal, non-negotiables, success criteria, governance mode.
- **completion-data.json** (`.superflow/completion-data.json`): structured completion data written by `_write_completion_data()` for Phase 3 merge context.

## Key Files
| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | ~142 | Entry point — startup checklist, provider detection, state management, dashboard commands, phase routing |
| `superflow-enforcement.md` | 80 | 9 hard rules, specialized 2-agent reviews (Claude=Product, secondary=Technical), rationalization prevention, phase gates |
| `references/phase0-onboarding.md` | ~80 | Router — detection, recovery matrix, stage loading |
| `references/phase0/stage1-detect.md` | ~214 | Parallel preflight, auto-detection, confirmation |
| `references/phase0/stage2-analysis.md` | ~256 | 5 parallel agents, tiered model usage |
| `references/phase0/stage3-report.md` | ~179 | Health report, informative summary, approval |
| `references/phase0/stage4-setup.md` | ~238 | 3 concurrent branches, strict file ownership |
| `references/phase0/stage5-completion.md` | ~163 | Markers, tech debt persistence, restart |
| `references/phase0/greenfield.md` | ~350 | Greenfield path G1-G6 |
| `references/phase1-discovery.md` | ~374 | Expert panel brainstorming, Board Memo, governance mode selection, charter generation, auto-launch |
| `references/phase2-execution.md` | ~350 | Governance-aware review tiering, Popen execution, progress polling, dashboard mode, holistic review |
| `references/phase3-merge.md` | 184 | 3 stages, sequential rebase merge with CI gate, completion-data.json |
| `prompts/implementer.md` | 81 | Red-Green-Refactor TDD cycle for code agents |
| `prompts/expert-panel.md` | 44 | Expert persona prompt — proposals, challenge, recommendation |
| `prompts/llms-txt-writer.md` | 154 | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | 148 | Verified paths/commands, <200 lines target |
| `bin/superflow-supervisor` | 213 | CLI: run, status, resume, reset, launch, stop commands |
| `lib/supervisor.py` | ~1970 (~1580 LOC) | Core: Popen execution with progress polling, charter injection, digest, blocker escalation, governance-aware review tiering |
| `lib/queue.py` | 137 (~120 LOC) | Sprint queue with DAG resolution, metadata dict (charter_file, governance_mode), atomic saves |
| `lib/planner.py` | ~336 (~280 LOC) | Plan-to-queue + charter-to-queue generator, shared heading parser |
| `lib/launcher.py` | 334 (~280 LOC) | Launch/stop/status/restart supervisor, PID management, skip-request writer |
| `lib/checkpoint.py` | 52 (~44 LOC) | Checkpoint save/load for crash recovery, string IDs, named checkpoints |
| `lib/parallel.py` | 61 (~50 LOC) | ThreadPoolExecutor concurrency with queue_lock |
| `lib/replanner.py` | 225 (~180 LOC) | Adaptive replanner — adjusts remaining sprints via Claude, charter-aware |
| `lib/notifications.py` | 196 (~160 LOC) | Telegram Bot API + stdout fallback, 20 event types (added progress, digest, blocker, merge_reminder) |
| `templates/supervisor-sprint-prompt.md` | 69 | Sprint template + charter, governance_mode, governance_instructions placeholders |
| `templates/replan-prompt.md` | 29 | Replanner prompt with charter placeholder |
| `templates/superflow-state-schema.json` | ~70 | JSON Schema for .superflow-state.json |
| `examples/sprint-queue-example.json` | 56 | Queue file template with metadata example |
| `tests/` | ~7100 | 362+ tests: unit (all modules) + integration (charter, governance, observability) |

## Conventions
- Hybrid project: Markdown skill files (no dependencies) + Python supervisor (stdlib only, no pip install)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding
- All phases use stage/todo structure with TaskCreate for progress tracking
- `.superflow-state.json` persists phase/stage for crash recovery (gitignored); extended with `brief_file`, `charter_file`, `completion_data_file`, `governance_mode`
- **Governance modes** (light/standard/critical): auto-suggested at Phase 1 start, stored in state and charter. Controls review depth, holistic review threshold, and plan complexity
- **Autonomy Charter**: durable intent artifact generated at end of Phase 1. Injected into sprint prompts, reviewers, and replanner as single source of truth for autonomous execution boundaries
- **Queue metadata**: `metadata` dict in sprint queue carries `charter_file`, `governance_mode`, `brief_file` across supervisor restarts

## Known Issues & Tech Debt
- TDD cycle duplicated in `implementer.md:23-31` and `testing-guidelines.md:13-21` (agent sees it twice since implementer includes testing-guidelines)
- Permissions JSON: single-sourced in `references/phase0/stage4-setup.md` (Branch B); `README.md` has a short example with a link to the canonical source
- Greenfield templates (nextjs.md, python.md) provide config files but not source file contents — LLM generates those

<!-- updated-by-superflow:2026-03-26 -->

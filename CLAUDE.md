# Superflow — Claude Instructions

## Project Overview
Superflow is a Claude Code skill (hybrid: Markdown prompts + Python companion CLI) that orchestrates a 4-phase dev workflow: onboarding, product discovery, autonomous execution, merge. The Python supervisor enables multi-hour autonomous sprint execution outside Claude's context window. v3.0.0, MIT License.

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, 90 lines)
  ├── superflow-enforcement.md (durable rules → ~/.claude/rules/)
  ├── references/
  │   ├── phase0-onboarding.md (first-run, 11 steps)
  │   ├── phase1-discovery.md (interactive, 12 steps)
  │   ├── phase2-execution.md (autonomous, 10 steps/sprint + unified review + holistic review)
  │   └── phase3-merge.md (user-initiated merge)
  ├── agents/ (12 agent definitions — deep/standard/fast tiers with effort frontmatter)
  ├── prompts/
  │   ├── implementer.md (TDD code agent)
  │   ├── spec-reviewer.md (spec compliance)
  │   ├── code-quality-reviewer.md (correctness/security)
  │   ├── product-reviewer.md (user perspective)
  │   ├── llms-txt-writer.md (llms.txt generation)
  │   ├── claude-md-writer.md (CLAUDE.md generation)
  │   ├── testing-guidelines.md (TDD reference)
  │   └── codex/ (3 Codex-specific prompts: code-reviewer, product-reviewer, audit)
  ├── bin/
  │   └── superflow-supervisor (CLI entry point)
  ├── lib/
  │   ├── supervisor.py (core: worktree lifecycle, sprint execution, run loop)
  │   ├── queue.py (DAG-based sprint queue)
  │   ├── checkpoint.py (crash recovery)
  │   ├── parallel.py (ThreadPoolExecutor concurrency)
  │   ├── replanner.py (adaptive LLM-powered replanning)
  │   └── notifications.py (Telegram + stdout)
  ├── templates/
  │   ├── supervisor-sprint-prompt.md (sprint execution template)
  │   └── replan-prompt.md (replanner template)
  ├── examples/
  │   └── sprint-queue-example.json (queue template)
  └── tests/
      ├── test_supervisor.py, test_queue.py, test_replanner.py, ...
      └── test_integration.py (132 tests total)
```

Hybrid project: Markdown prompts drive Claude Code sessions; Python supervisor orchestrates multi-sprint execution with crash recovery, parallel execution, and adaptive replanning. Enforcement rules survive context compaction via `~/.claude/rules/`.

## Key Files
| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | 90 | Entry point — startup checklist, provider detection, supervisor detection, phase routing |
| `superflow-enforcement.md` | 74 | 9 hard rules, rationalization prevention, phase gates, holistic review |
| `references/phase0-onboarding.md` | ~323 | First-run: 5 parallel agents (4 Claude + 1 Codex), health report, doc audit, python3 check |
| `references/phase1-discovery.md` | 138 | Brainstorm, spec, plan with dual-model review |
| `references/phase2-execution.md` | 168 | Sprint loop: worktree, TDD, unified 4-agent review, PR + Final Holistic Review |
| `references/phase3-merge.md` | 89 | Sequential rebase merge with CI gate |
| `prompts/implementer.md` | 81 | Red-Green-Refactor TDD cycle for code agents |
| `prompts/llms-txt-writer.md` | 154 | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | 148 | Verified paths/commands, <200 lines target |
| `agents/*.md` | 12 files | Agent definitions — deep/standard/fast tiers with effort frontmatter |
| `prompts/codex/*.md` | 3 files | Codex-specific prompts: code-reviewer, product-reviewer, audit |
| `bin/superflow-supervisor` | 143 | CLI: run, status, resume, reset commands |
| `lib/supervisor.py` | 763 (~590 LOC) | Core supervisor: worktree lifecycle, sprint execution, run loop, reports |
| `lib/queue.py` | 114 (~98 LOC) | Sprint queue with DAG dependency resolution, atomic saves |
| `lib/checkpoint.py` | 37 (~31 LOC) | Checkpoint save/load for crash recovery |
| `lib/parallel.py` | 38 (~31 LOC) | ThreadPoolExecutor-based concurrent sprint execution |
| `lib/replanner.py` | 212 (~168 LOC) | Adaptive replanner — adjusts remaining sprints via Claude |
| `lib/notifications.py` | 111 (~90 LOC) | Telegram Bot API + stdout fallback, 8 event types |
| `templates/supervisor-sprint-prompt.md` | 33 | Sprint execution prompt with placeholders |
| `templates/replan-prompt.md` | 26 | Replanner prompt with placeholders |
| `examples/sprint-queue-example.json` | 45 | Queue file template for new users |
| `tests/` | 2759 | 132 tests: unit (all modules) + integration (happy path, crash, retry) |

## Release Process
After Phase 3 merge, always:
1. Bump version in `README.md` header (`# superflow vX.Y.Z`)
2. Add CHANGELOG.md entry with Added/Changed/Removed sections
3. Commit: `Bump to vX.Y.Z: <one-line summary>`
4. Push to main
5. Create GitHub release: `gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(changelog entry)"`

## Conventions
- Hybrid project: Markdown skill files (no dependencies) + Python supervisor (stdlib only, no pip install)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding

## Known Issues & Tech Debt
- Agent definition bodies duplicated across deep/standard tiers (maintenance burden — changing review criteria requires edits in multiple files)
- TDD cycle duplicated in `implementer.md:23-31` and `testing-guidelines.md:13-21` (agent sees it twice since implementer includes testing-guidelines)
- Permissions JSON maintained in two places: compact subset in README.md and expanded version in references/phase0-onboarding.md (intentional divergence — README is quickstart, phase0 is full setup)

<!-- updated-by-superflow:2026-03-23 -->

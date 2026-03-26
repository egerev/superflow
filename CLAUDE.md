# Superflow — Claude Instructions

## Project Overview
Superflow is a pure Markdown Claude Code skill that orchestrates a 4-phase dev workflow: onboarding, product discovery with expert panel brainstorming, autonomous execution with PR-per-sprint, and merge. v4.1.1, MIT License.

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, ~120 lines)
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
  │   ├── phase2-execution.md (autonomous, governance-aware review tiering, holistic review)
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
  ├── templates/
  │   ├── superflow-state-schema.json (state file JSON Schema)
  │   ├── greenfield/ (stack scaffolding: nextjs.md, python.md, generic.md)
  │   └── ci/ (CI workflows: github-actions-node.yml, github-actions-python.yml)
```

**Key v4.0 artifacts:**
- **Autonomy Charter** (`docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`): generated at end of Phase 1, injected into every sprint prompt and reviewer. Contains goal, non-negotiables, success criteria, governance mode.
- **completion-data.json** (`.superflow/completion-data.json`): structured completion data for Phase 3 merge context.

## Key Files
| File | Purpose |
|------|---------|
| `SKILL.md` | Entry point — startup checklist, provider detection, state management, phase routing |
| `superflow-enforcement.md` | 10 hard rules, specialized 2-agent reviews, rationalization prevention, phase gates |
| `references/phase0-onboarding.md` | Router — detection, recovery matrix, stage loading |
| `references/phase0/stage1-detect.md` | Parallel preflight, auto-detection, confirmation |
| `references/phase0/stage2-analysis.md` | 5 parallel agents, tiered model usage |
| `references/phase0/stage3-report.md` | Health report, informative summary, approval |
| `references/phase0/stage4-setup.md` | 3 concurrent branches, strict file ownership |
| `references/phase0/stage5-completion.md` | Markers, tech debt persistence, restart |
| `references/phase0/greenfield.md` | Greenfield path G1-G6 |
| `references/phase1-discovery.md` | Expert panel brainstorming, Board Memo, governance mode, charter generation |
| `references/phase2-execution.md` | Governance-aware review tiering, holistic review, subagent execution |
| `references/phase3-merge.md` | 3 stages, sequential rebase merge with CI gate |
| `prompts/implementer.md` | Red-Green-Refactor TDD cycle for code agents |
| `prompts/expert-panel.md` | Expert persona prompt — proposals, challenge, recommendation |
| `prompts/llms-txt-writer.md` | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | Verified paths/commands, <200 lines target |

## Conventions
- Pure Markdown skill (no Python, no pip dependencies)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding
- All phases use stage/todo structure with TaskCreate for progress tracking
- `.superflow-state.json` persists phase/stage for crash recovery (gitignored); extended with `brief_file`, `charter_file`, `completion_data_file`, `governance_mode`
- **Governance modes** (light/standard/critical): auto-suggested at Phase 1 start, stored in state and charter. Controls review depth, holistic review threshold, and plan complexity
- **Autonomy Charter**: durable intent artifact generated at end of Phase 1. Injected into sprint prompts and reviewers as single source of truth for autonomous execution boundaries

## Known Issues & Tech Debt
- TDD cycle duplicated in `implementer.md:23-31` and `testing-guidelines.md:13-21` (agent sees it twice since implementer includes testing-guidelines)
- Permissions JSON: single-sourced in `references/phase0/stage4-setup.md` (Branch B); `README.md` has a short example with a link to the canonical source
- Greenfield templates (nextjs.md, python.md) provide config files but not source file contents — LLM generates those

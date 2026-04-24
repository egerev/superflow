# Superflow — Claude Instructions

## Project Overview
Superflow is a pure Markdown skill that orchestrates a 4-phase dev workflow: onboarding, product discovery with expert panel brainstorming and git workflow selection, autonomous execution with a selected branch/PR strategy, and merge. v5.0.0, MIT License. Supports both **Claude Code** and **Codex CLI** as primary orchestrator (auto-detected at startup via `$CLAUDE_CODE_SESSION_ID`).

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, ~240 lines, auto-detects Claude/Codex runtime)
  ├── superflow-enforcement.md (durable rules → ~/.claude/rules/)
  ├── codex/
  │   ├── AGENTS.md (durable rules for Codex → ~/.codex/AGENTS.md)
  │   ├── agents/*.toml (12 Codex agent definitions → ~/.codex/agents/)
  │   ├── hooks.json (SessionStart + Stop hooks → ~/.codex/hooks.json)
  │   └── config-fragment.toml (reference config for ~/.codex/config.toml)
  ├── references/
  │   ├── codex/ (Codex dispatch overlays — one per phase)
  │   ├── codex-dispatch-patterns.md (complete Agent→spawn_agent mapping table)
  │   ├── codex-context-strategy.md (258K context budget guide)
  │   ├── git-workflow-modes.md (git workflow mode selection and branch base policy)
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
- **Autonomy Charter** (`docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`): generated at end of Phase 1, injected into every sprint prompt and reviewer. Contains goal, non-negotiables, success criteria, governance mode, and git workflow mode.
- **completion-data.json** (`.superflow/completion-data.json`): structured completion data for Phase 3 merge context.
- **Heartbeat block** (optional field in `.superflow-state.json`): compaction-recovery snapshot written at sprint start and each stage transition. 9 fields: `updated_at`, `current_sprint`, `sprint_goal`, `merge_method`, `active_worktree`, `active_branch`, `must_reread`, `last_review_verdict`, `phase2_step`. Enforced by Rule 12; PreCompact hook surfaces it in the dump.
- **Event log** (`.superflow/events.jsonl`): append-only JSONL telemetry stream. Each line is a compact JSON object conforming to `templates/event-schema.json` (JSON Schema 2020-12, 524 lines, 20 event types). Emitted via `tools/sf-emit.sh`. `SUPERFLOW_RUN_ID` (UUID) groups all events for a run; persisted to `.superflow-state.json` under `context.run_id` for recovery after `/clear`.

## Key Files
| File | Purpose |
|------|---------|
| `SKILL.md` | Entry point — startup checklist, provider detection, state management, phase routing |
| `superflow-enforcement.md` | 13 hard rules, specialized 2-agent reviews, rationalization prevention, phase gates |
| `references/phase0-onboarding.md` | Router — detection, recovery matrix, stage loading |
| `references/phase0/stage1-detect.md` | Parallel preflight, auto-detection, confirmation |
| `references/phase0/stage2-analysis.md` | 5 parallel agents, tiered model usage |
| `references/phase0/stage3-report.md` | Health report, informative summary, approval |
| `references/phase0/stage4-setup.md` | 3 concurrent branches, strict file ownership |
| `references/phase0/stage5-completion.md` | Markers, tech debt persistence, restart |
| `references/phase0/greenfield.md` | Greenfield path G1-G6 |
| `references/git-workflow-modes.md` | Git workflow modes, selection heuristic, branch base policy |
| `references/phase1-discovery.md` | Expert panel brainstorming, Board Memo, governance mode, charter generation |
| `references/phase2-execution.md` | Governance-aware review tiering, holistic review, per-PR docs update/review gate, subagent execution |
| `references/phase3-merge.md` | 3 stages, sequential rebase merge with CI gate |
| `prompts/implementer.md` | Red-Green-Refactor TDD cycle for code agents |
| `prompts/expert-panel.md` | Expert persona prompt — proposals, challenge, recommendation |
| `prompts/llms-txt-writer.md` | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | Verified paths/commands, <200 lines target |
| `tools/sf-emit.sh` | Source-safe bash library for emitting JSONL events; usage: `source tools/sf-emit.sh && sf_emit <type> key=val key:int=N key:bool=true` (207 lines) |
| `templates/event-schema.json` | JSON Schema 2020-12 for all event types — envelope fields + 20 per-type data schemas, additive evolution policy (524 lines) |

## Conventions
- Pure Markdown skill (no Python, no pip dependencies)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding
- All phases use stage/todo structure with TaskCreate for progress tracking
- `.superflow-state.json` persists phase/stage for crash recovery (gitignored); extended with `brief_file`, `charter_file`, `completion_data_file`, `governance_mode`, `git_workflow_mode`, and optional `heartbeat` block for compaction drift defense
- **Governance modes** (light/standard/critical): auto-suggested at Phase 1 start, stored in state and charter. Controls review depth, holistic review threshold, and plan complexity
- **Git workflow modes** (`solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, `trunk_based`): selected in Phase 1, stored in state and charter, and controls branch base, PR count, sprint parallelism, and merge order
- **Autonomy Charter**: durable intent artifact generated at end of Phase 1. Injected into sprint prompts and reviewers as single source of truth for autonomous execution boundaries
- **Event emission**: `source tools/sf-emit.sh && sf_emit <type> key=val key:int=N key:bool=true key:json='{"x":1}'`. Typed key syntax: bare `=` → string, `:int=` → number, `:bool=` → boolean, `:json=` → raw JSON. jq-only construction; validates type against allowlist and key names against identifier regex before emitting one compact JSONL line.
- **Codex model policy**: Codex subagents and Claude-runtime `codex exec` secondary calls use `gpt-5.5`; deep analyst/implementer/reviewer roles use `xhigh`, standard roles use `high`, and fast implementer uses `medium`. Codex-runtime Claude product/research secondary calls use exact model `claude-opus-4-7` with `--effort xhigh`.
- **Per-PR docs gate**: every PR must run documentation update and separate documentation review before `gh pr create`. In per-sprint PR modes this happens every sprint; in `solo_single_pr` it happens before the final PR. `.par-evidence.json` must include `docs_update` (`UPDATED` or `UNCHANGED`) and `docs_review: PASS`; `llms.txt` is explicitly audited for every PR.

## Known Issues & Tech Debt
- TDD cycle duplicated in `implementer.md:23-31` and `testing-guidelines.md:13-21` (agent sees it twice since implementer includes testing-guidelines)
- Permissions JSON: single-sourced in `references/phase0/stage4-setup.md` (Branch B); `README.md` has a short example with a link to the canonical source
- Greenfield templates (nextjs.md, python.md) provide config files but not source file contents — LLM generates those
- **Phase 3 post-compaction merge regression**: context compaction during Phase 3 merge loop can cause agent to fall back to local `git merge` instead of `gh pr merge --rebase --delete-branch`, leaving GitHub PRs open and creating non-linear history. Mitigated by: (1) merge method rule in `superflow-enforcement.md` (survives compaction); (2) heartbeat `must_reread` includes `references/phase3-merge.md` starting at Sprint 1 end — compaction-triggered rehydration pulls the exact Phase 3 merge procedure into context automatically. Full fix: re-read `phase3-merge.md` before each PR merge (already in must_reread via Phase 2 heartbeat).
- **Codex sprint-level parallelism**: recommended config is `[agents] max_threads=6, max_depth=2`. This allows sprint supervisors to spawn per-sprint implement/review/doc agents, enabling sprint-level parallel waves in Codex when `git_workflow_mode` permits. Old `max_depth=1` configs fall back to sequential sprints.
- **Codex no PreCompact/PostCompact**: compaction recovery relies on Stop hook dumps + SessionStart re-injection + self-referential rule in AGENTS.md. Less reliable than Claude's hook-based recovery.
- **Codex context ~258K**: 4x smaller than Claude's 1M. Long Phase 2 runs (4+ sprints) require session-per-wave/session-per-sprint strategy or aggressive /compact usage.
- **Per-event-type key allowlist**: `sf_emit` validates key names against an identifier regex and the event type against a global allowlist, but does not yet validate which keys are legal per event type. Practical injection is blocked; semantic key validation deferred to a future sprint.
- **flock/size cap for sf-emit.sh**: `O_APPEND` is atomic only up to `PIPE_BUF` (~4KB on Linux). Large events or concurrent writes could corrupt `.superflow/events.jsonl`. Fix: add `flock` or enforce a per-event size cap in `sf-emit.sh`.
<!-- updated-by-superflow:2026-04-20 -->

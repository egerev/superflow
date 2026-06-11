# Superflow — Claude Instructions

## Project Overview
Superflow is a pure Markdown skill that orchestrates a 4-phase dev workflow: onboarding, product discovery with expert panel brainstorming, Product Vision alignment, and git workflow selection, autonomous execution with a selected branch/PR strategy, and merge. v5.5.0, MIT License. Supports both **Claude Code** and **Codex CLI** as primary orchestrator (auto-detected at startup via `$CLAUDE_CODE_SESSION_ID`).

## Key Rules
- All documentation output in English — user communication follows their language preference
- Dispatch subagents for all code/analysis — orchestrator reads, plans, reviews, dispatches
- Use `subagent_type: deep-doc-writer` for documentation agents — effort controlled via agent definition frontmatter, not prompt keywords
- Verify framework names by reading actual `import` statements, never guess from directory names
- Every claim in generated docs needs evidence (file path, count, command output)

## Architecture
```
SKILL.md (entry point, ~280 lines, 10-step startup checklist, auto-detects Claude/Codex runtime)
  ├── superflow-enforcement.md (durable rules → ~/.claude/rules/, checksum-synced at startup)
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
  │   ├── phase1-discovery.md (interactive, expert panel brainstorming, Product Vision alignment, governance mode selection, charter generation)
  │   ├── phase2-execution.md (legacy router — Sprint 2 reduced to ~39 lines pointing at phase2/)
  │   ├── phase2/ (Run 3 — DAG-driven Phase 2; integration in Run 3 Sprint 2)
  │   │   ├── workflow.json (DAG: 9-cell governance×complexity decision matrix + 7 stages + step_files map)
  │   │   ├── overview.md (Phase 2 high-level context, wave analysis, model selection)
  │   │   └── steps/ (10 step detail files: setup-reread, setup-worktree, impl-dispatch, review-unified, par-evidence, ship-pr, compaction-recovery, holistic-review, frontend-testing, completion-report)
  │   ├── phase3-merge.md (user-initiated merge, 3 stages)
  │   └── workflow-orchestration.md (single Workflow authority — opt-in policy, permission gates, limits, saved workflow specs, /goal watchdog, fallbacks)
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
  │   ├── claude/ (Claude secondary prompts for Codex runtime: audit, code-reviewer, product-reviewer)
  │   └── codex/ (Codex-specific prompts: code-reviewer, product-reviewer, audit)
  ├── agents/ (12 agent definitions — deep/standard/fast tiers with model+effort frontmatter)
  ├── workflows/
  │   ├── superflow-review.js (saved workflow: parallel product + technical review fan-out → ~/.claude/workflows/)
  │   └── superflow-wave.js (saved workflow: implementation-only parallel sprint wave → ~/.claude/workflows/)
  ├── tools/
  │   ├── sf-emit.sh (JSONL event emission library)
  │   ├── verify-phase2-dag.sh (static DAG verifier)
  │   ├── measure-phase2-context.sh (context savings quantifier)
  │   └── cleanup-testcontainers.sh (label-based testcontainers cleanup — only docker command in orchestrator budget)
  ├── templates/
  │   ├── superflow-state-schema.json (state file JSON Schema)
  │   ├── event-schema.json (event log JSON Schema — 21 event types)
  │   ├── greenfield/ (stack scaffolding: nextjs.md, python.md, generic.md)
  │   └── ci/ (CI workflows: github-actions-node.yml, github-actions-python.yml)
  └── .github/workflows/ci.yml (repo CI: shellcheck, DAG verify, JSON validation, forbidden-token gate)
```

**Key v4.0 artifacts:**
- **Autonomy Charter** (`docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`): generated at end of Phase 1, injected into every sprint prompt and reviewer. Contains goal, non-negotiables, success criteria, governance mode, git workflow mode, and model profile.
- **completion-data.json** (`.superflow/completion-data.json`): structured completion data for Phase 3 merge context.
- **Heartbeat block** (optional field in `.superflow-state.json`): compaction-recovery snapshot written at sprint start and each stage transition. 9 fields: `updated_at`, `current_sprint`, `sprint_goal`, `merge_method`, `active_worktree`, `active_branch`, `must_reread`, `last_review_verdict`, `phase2_step`. Enforced by Rule 12; PreCompact hook surfaces it in the dump.
- **Event log** (`.superflow/events.jsonl`): append-only JSONL telemetry stream. Each line is a compact JSON object conforming to `templates/event-schema.json` (JSON Schema 2020-12, 549 lines, 21 event types incl. `pr.fail`). Emitted via `tools/sf-emit.sh`. `SUPERFLOW_RUN_ID` (lowercase UUID — uuidgen output is piped through `tr '[:upper:]' '[:lower:]'`) groups all events for a run; persisted to `.superflow-state.json` under `context.run_id` for recovery after `/clear`.

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
| `references/phase1-discovery.md` | Expert panel brainstorming, Board Memo, Product Vision alignment, governance mode, charter generation |
| `references/phase2-execution.md` | Legacy router (~39 lines) — points at `references/phase2/workflow.json`, `overview.md`, and `steps/`; full prose preserved in git history (pre-Sprint-2) |
| `references/phase2/workflow.json` | Phase 2 lifecycle DAG with governance×complexity decision matrix |
| `references/phase3-merge.md` | 3 stages, sequential rebase merge with CI gate |
| `references/workflow-orchestration.md` | Single authority on Workflow-tool usage — documented API surface, opt-in policy, permission gates by mode, limits, saved workflow specs, UNDOCUMENTED-API warning, /goal watchdog, Codex/fallback chain (178 lines) |
| `workflows/superflow-review.js` | Saved `/superflow-review` workflow — parallel product + technical reviewers (technical applies the codex-or-Claude fallback chain itself via Bash); returns `{product, technical, pass}`, fail-closed fenced-JSON parsing (112 lines) |
| `workflows/superflow-wave.js` | Saved `/superflow-wave` workflow — one implementer per sprint (worktree-isolated, implementation only, no review/docs/PAR/PR); returns position-bound `[{sprint, status, summary, test_evidence}]`, fail-closed (97 lines) |
| `prompts/implementer.md` | Red-Green-Refactor TDD cycle for code agents |
| `prompts/expert-panel.md` | Expert persona prompt — proposals, challenge, recommendation |
| `prompts/llms-txt-writer.md` | llmstxt.org standard, no hard size limit |
| `prompts/claude-md-writer.md` | Verified paths/commands, <200 lines target |
| `tools/sf-emit.sh` | Source-safe bash library for emitting JSONL events; usage: `source tools/sf-emit.sh && sf_emit <type> key=val key:int=N key:bool=true` (360 lines) |
| `tools/verify-phase2-dag.sh` | Static DAG verifier — validates all 9 governance×complexity cells, 7-stage sequence, step_files coverage, and on-disk step file existence; exits 0 on full pass |
| `tools/measure-phase2-context.sh` | Context savings quantifier — computes pre-Run-3 vs post-Run-3 per-turn token load using git history; outputs a one-line summary (Savings: 76.4%) |
| `tools/cleanup-testcontainers.sh` | Testcontainers cleanup helper — label-based selection (`docker ps -aq --filter "label=org.testcontainers=true"`), optional ancestor filter, idempotent; the ONLY docker-touching command in the orchestrator's Rule 11 budget (37 lines) |
| `hooks/precompact-state-externalization.sh` | PreCompact hook — sources sf-emit, emits `compact.pre`/`compact.post` events with absolute path to the dump file |
| `templates/event-schema.json` | JSON Schema 2020-12 for all event types — envelope fields + 21 per-type data schemas incl. `pr.fail`, additive evolution policy (549 lines) |
| `.github/workflows/ci.yml` | Repo CI on push/PR to main — `shellcheck -S error` over `tools/*.sh hooks/*.sh`, `verify-phase2-dag.sh`, `jq empty` over tracked JSON, forbidden-token gate (stale Opus-4.7 model pin; Ryuk env var without the `TESTCONTAINERS_` prefix) (46 lines) |

## Conventions
- Pure Markdown skill (no Python, no pip dependencies)
- File references use relative paths from project root
- Phase docs are re-read at every phase/sprint boundary (compaction erases skill content)
- Markers: `<!-- updated-by-superflow:YYYY-MM-DD -->` appended to generated files
- Both `<!-- updated-by-superflow:` and `<!-- superflow:onboarded` are valid markers (backwards compat)
- Breakage scenario required for every review finding — no scenario = not a finding
- All phases use stage/todo structure with TaskCreate for progress tracking
- `.superflow-state.json` persists phase/stage for crash recovery (gitignored); extended with `brief_file`, `charter_file`, `completion_data_file`, `governance_mode`, `git_workflow_mode`, `model_profile`, `use_workflows`, and optional `heartbeat` block for compaction drift defense
- **Governance modes** (light/standard/critical): auto-suggested at Phase 1 start, stored in state and charter. Controls review depth, holistic review threshold, and plan complexity
- **Git workflow modes** (`solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, `trunk_based`): selected in Phase 1, stored in state and charter, and controls branch base, PR count, sprint parallelism, and merge order
- **Model profiles** (`frontier` default / `balanced`): selected in Phase 1 Step 2c, stored in state and charter. Controls the model passed at dispatch for deep judgment roles — `frontier`=fable, `balanced`=opus-4.8. All other roles (standard reviewers/doc-writers→opus, implementers→sonnet) are unaffected by profile
- **Product Vision alignment**: Phase 1 uses a single recommendation-led decision brief with options, tradeoffs, reversibility, safe defaults, and support for "do what you recommend", one-message, or audio-transcript answers. It replaces the old design-tree grilling pattern.
- **Autonomy Charter**: durable intent artifact generated at end of Phase 1. Injected into sprint prompts and reviewers as single source of truth for autonomous execution boundaries
- **Event emission**: `source tools/sf-emit.sh && sf_emit <type> key=val key:int=N key:bool=true key:json='{"x":1}'`. Typed key syntax: bare `=` → string, `:int=` → number, `:bool=` → boolean, `:json=` → raw JSON. jq-only construction; validates type against allowlist and key names against identifier regex before emitting one compact JSONL line. `pr.fail` (added in 5.4.0) is emitted when a PR CI run concludes red or a PR is abandoned: `pr_number` (int, required), `reason` (string, required), `ci_run_id` (string, optional).
- **Model tier policy**: agent frontmatter is the frontier default — deep-spec/code/product-reviewer + deep-analyst = `fable`/max; deep-doc-writer = `opus`/max; deep-implementer = `sonnet`/max; standard reviewers + standard-doc-writer = `opus`/high; standard-implementer = `sonnet`/high; fast-implementer = `sonnet`/low. Always pass `model:` explicitly in Agent() calls; for deep reviewers + deep-analyst the explicit `model:` is what the profile controls: `"fable"` (frontier, default) or `"opus"` (balanced — read `context.model_profile`). A forgotten `model:` silently inherits Fable regardless of profile.
- **Reviewer verdict contract**: every reviewer ends its final message with a fenced `json` block — `{"verdict": ..., "findings": [{severity, file, line, scenario, description}], "summary": ...}`. The orchestrator extracts the fence (awk → jq) and assembles `.par-evidence.json` mechanically — no prose parsing. Re-review goes to the SAME named background reviewer via SendMessage (cold re-dispatch as fallback).
- **Workflow acceleration (hybrid, opt-in)**: Phase 2 may use saved multi-agent workflows for exactly two spots — `/superflow-review` (unified review fan-out) and `/superflow-wave` (parallel implementation wave). Gated on Claude runtime + `context.use_workflows=true` (recorded at Phase 1 Step 12 plan approval; "no-workflows" opts out; always false on Codex) + availability (CLI ≥ 2.1.154, not `disableWorkflows`/`CLAUDE_CODE_DISABLE_WORKFLOWS=1`); every other case falls back to the Agent-based v5.4.0 paths with no behavior change. Shipped scripts use ONLY the documented API surface (`agent`, `parallel`, `phase`, `log`, `args`) — never undocumented fields (`schema`, `agentType`, `isolation`, `resume-run-id`); structured data returns via the fenced-JSON verdict contract with fail-closed parsing; PAR evidence from this path records `provider: "workflow-review"`. At Phase 2 launch the orchestrator prints a ready-to-paste `/goal` watchdog suggestion (user-only command — the model cannot set it). Single authority: `references/workflow-orchestration.md`
- **Deploy checksum sync**: SKILL.md startup (step 4) syncs deployed copies via `cmp -s` + overwrite-on-mismatch — `superflow-enforcement.md` → `~/.claude/rules/`, `agents/*.md` → `~/.claude/agents/`, and `workflows/*.js` → `~/.claude/workflows/` (Claude runtime); `codex/agents/*.toml` → `~/.codex/agents/` and `codex/AGENTS.md` → `~/.codex/AGENTS.md` (Codex runtime). Exception: `~/.codex/hooks.json` is installed only if missing, never overwritten (one-line warning asks to merge manually).
- **Testcontainers canon**: the only env var is `TESTCONTAINERS_RYUK_DISABLED`, set exclusively when `process.env.CI === "true"` — the duty lives in `agents/*-implementer.md` definitions. Orchestrator cleanup runs ONLY `bash $SUPERFLOW_SKILL_ROOT/tools/cleanup-testcontainers.sh` (label-based `label=org.testcontainers=true`); name-regex matching and raw `docker` commands are forbidden.
- **Heartbeat cadence**: Claude runtime checks heartbeat/`must_reread` at sprint boundaries, stage transitions, and immediately after compaction/summarization; Codex runtime keeps every-turn discipline (no PreCompact hook, 258K context).
- **Codex model policy**: Codex subagents and Claude-runtime `codex exec` secondary calls use `gpt-5.5`; deep analyst/implementer/reviewer roles use `xhigh`, standard roles use `high`, and fast implementer uses `medium`. Codex-runtime Claude product/research secondary calls use `--effort xhigh` with model from `context.model_profile`: `claude-fable-5` (frontier, default) or `claude-opus-4-8` (balanced).
- **Per-PR docs gate**: every PR must run documentation update and separate documentation review before `gh pr create`. In per-sprint PR modes this happens every sprint; in `solo_single_pr` it happens before the final PR. `.par-evidence.json` must include `docs_update` (`UPDATED` or `UNCHANGED`) and `docs_review: PASS`; `llms.txt` is explicitly audited for every PR.

## Known Issues & Tech Debt
- Greenfield templates (nextjs.md, python.md) provide config files but not source file contents — LLM generates those
- **Phase 3 post-compaction merge regression**: context compaction during Phase 3 merge loop can cause agent to fall back to local `git merge` instead of `gh pr merge --rebase --delete-branch`. Mitigated by: (1) merge method rule in `superflow-enforcement.md` (survives compaction); (2) heartbeat `must_reread` includes `references/phase3-merge.md`; (3) since 5.4.0 — Claude runtime waits for PR checks via the native Monitor tool (no manual polling drift) and post-merge verification reads `baseline_test_cmd` from `.superflow/completion-data.json` via jq with Autonomy Charter fallback (the fragile `sprint-queue.json` python one-liner is gone). Residual risk: re-read `phase3-merge.md` before each PR merge after compaction.
- **Codex sprint-level parallelism**: recommended config is `[agents] max_threads=6, max_depth=2`. This allows sprint supervisors to spawn per-sprint implement/review/doc agents, enabling sprint-level parallel waves in Codex when `git_workflow_mode` permits. Old `max_depth=1` configs fall back to sequential sprints.
- **Codex no PreCompact/PostCompact**: compaction recovery relies on Stop hook dumps + SessionStart re-injection + self-referential rule in AGENTS.md. Less reliable than Claude's hook-based recovery.
- **Codex context ~258K**: 4x smaller than Claude's 1M. Long Phase 2 runs (4+ sprints) require session-per-wave/session-per-sprint strategy or aggressive /compact usage.
- **Per-event-type key allowlist**: `sf_emit` validates key names against an identifier regex and the event type against a global allowlist (21 types), but does not yet validate which keys are legal per event type. Practical injection is blocked; semantic key validation deferred to a future sprint.
<!-- updated-by-superflow:2026-06-11 -->

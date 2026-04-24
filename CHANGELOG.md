# Changelog

All notable changes to superflow will be documented in this file.

## Deferred (Sprint 3 → future)

MEDIUM/LOW event-log gaps identified in Sprint 3 coverage audit; not in scope for this sprint:

- **MEDIUM:** `agent_id` correlation for parallel waves — H5 adds the dispatch/complete pair pattern with `SF_PARENT_ID`, but systematic propagation of agent IDs across wave boundaries (parent→child agent chains) is not yet implemented
- **LOW:** Phase 3 failed-merge telemetry — `pr.merge` emission on CI failure/abandon is now suppressed (fixed in Sprint 3 fix-pass); a dedicated `pr.abandon` or `pr.fail` event type for failed-merge telemetry is deferred to a future schema extension
- **MEDIUM:** Phase 3 post-merge `test.run`/`test.result` emissions — the post-merge integration test run on `main` (after all PRs merged) lacks `sf_emit test.run` / `sf_emit test.result` instrumentation
- **LOW:** Enforce complexity/verdict enums at emitter layer — `sf_emit` currently accepts any string value for `complexity` and `verdict`; validation is deferred to consumers; adding allowlist checks inside `sf_emit` would catch typos at source
- **LOW:** Normalize shell var quoting for typed args (`sprint:int="$VAR"`) — some phase docs use unquoted `$VAR` in typed-arg position; safe in practice but inconsistent; a style pass would standardize to `sprint:int=$VAR` (no quotes needed for numeric vars) uniformly
- **LOW:** `run.start` charter field population on Phase 1→2 boundary — `run.start` schema allows an optional `charter` field (path to Autonomy Charter); currently emitted without it since the charter is generated at end of Phase 1 after `run.start` fires; fix requires either a `run.update` event type or re-emitting `run.start` at Phase 2 entry with charter path

## [5.2.0] - 2026-04-24

### Added — Git Workflow Modes + Codex Sprint Parallelism
- **Phase 1 git workflow selection**: Superflow now selects and stores `context.git_workflow_mode` alongside governance mode. Supported modes: `solo_single_pr`, `sprint_pr_queue`, `stacked_prs`, `parallel_wave_prs`, and `trunk_based`
- **New reference**: `references/git-workflow-modes.md` documents selection heuristics, branch base policy, PR count, and Phase 2 merge boundaries. Classic Git Flow remains opt-in only for projects that already use release trains
- **Mode-aware Phase 2/3**: branch creation, PR creation, docs gate timing, holistic review requirements, and merge order now follow the selected git workflow mode instead of hardcoding "one PR per sprint"
- **Codex sprint-level parallelism**: recommended Codex config is now `[agents] max_threads=6, max_depth=2`. With `max_depth>=2`, Codex can run independent sprint supervisors in parallel; each supervisor can spawn per-sprint implement/review/doc agents. Older `max_depth=1` configs fall back to sequential sprints with an explicit warning
- **Codex model policy**: Codex agents and Claude-runtime `codex exec` calls are pinned to `gpt-5.5` with tiered reasoning (`xhigh` deep, `high` standard, `medium` fast). Codex-runtime product/research reviews use exact Claude model `claude-opus-4-7 --effort xhigh`
- **Per-PR docs gate**: every PR path now requires a docs update decision and separate docs review before PR creation, with `llms.txt` explicitly audited. In `solo_single_pr`, this applies to the final PR; in per-sprint modes, it applies to every sprint PR

## [5.1.0] - 2026-04-17

### Removed — Phase 0 Anti-Regression Settings Check (reverts 4.6.0)
- **Removed `references/anti-regression-check.md`** entirely
- **Removed SKILL.md step 5a** (the inline `jq`-based settings detection and conversational apply flow)
- **Why**: the forced `CLAUDE_CODE_EFFORT_LEVEL=max` env var overrode the newer `effortLevel` setting in `~/.claude/settings.json`, making the `/effort` slash command ineffective (it kept announcing `CLAUDE_CODE_EFFORT_LEVEL=max overrides this session`). More broadly, a skill should not push opinionated env vars into the user's global settings — users who want the 4.5.0 env var recommendations can apply them manually from the 4.5.0 CHANGELOG entry
- **Also reverted**: the PreCompactHook detection that 4.7.0 added into anti-regression-check.md. The `hooks/precompact-state-externalization.sh` script itself remains — install instructions are in `hooks/README.md`
- **Marker cleanup**: `~/.claude/.superflow-anti-regression-checked` is no longer created or read by SuperFlow; safe to delete

## [4.8.0] - 2026-04-15

### Added — Orchestrator Tool Budget (Rule 11)
- **New enforcement Rule 11** in `superflow-enforcement.md`: in Phase 2 the orchestrator does NOT use Read/Grep/Glob directly on source files larger than 50 lines, and does NOT use Bash for anything beyond status checks, state I/O, and short progress output. All code reading, codebase exploration, research, and investigation route to `deep-analyst` (or `standard-implementer` for lighter work) with a <2k-token summary expected in response
- **New section in `references/phase2-execution.md`**: "Orchestrator Tool Budget" enumerates allowed direct tools (Bash status/state, Read <50 lines, TaskCreate/TaskUpdate, Agent), lists correct-delegation examples, and calls out the rare exceptions where a direct read beats a dispatch round-trip
- **Two new rationalizations** in the prevention list: "I'll just quickly Read this file myself" → dispatch analyst; "It's just one Grep" → dispatch if result could be >50 lines or context is already >60% of budget
- **Why**: orchestrator context grows monotonically through Phase 2. Every directly-Read 500-line file adds 500 lines to a context already holding plan, charter, state, PAR evidence, review output, and turn history. Subagents return summaries and discard their own context on exit. On a 6-8h autonomous run, consistent delegation is the difference between hitting auto-compact ~2x versus ~10x — and the quality of the final holistic review depends on the orchestrator still being coherent at sprint N

## [4.7.0] - 2026-04-15

### Added — PreCompact State Externalization
- **New hook script**: `hooks/precompact-state-externalization.sh` — runs immediately before context compaction, dumps `.superflow-state.json` plus the last 40 transcript entries to `<project>/.superflow/compact-log/precompact-<ts>.md` (or `~/.superflow/compact-log/` outside a SuperFlow project), and emits `hookSpecificOutput.additionalContext` pointing the orchestrator at the dump path. Reads the Claude Code hook payload from stdin with env-var fallback for older versions
- **New reference**: `hooks/README.md` — describes the hook, install instructions, design notes (idempotent, gitignored by default, fail-safe), and credits the [mvara-ai/precompact-hook](https://github.com/mvara-ai/precompact-hook) reference implementation
- **New section in `references/phase2-execution.md`**: "Compaction Recovery" instructs the orchestrator to `ls -t .superflow/compact-log/` after a PostCompact rules re-read and hydrate from the most recent dump before resuming work
- **Rationale**: compaction is lossy by design. `PostCompact` restores rules, but in-progress sprint context, review output, and subagent summaries can be dropped. A PreCompact snapshot on disk gives the orchestrator a deterministic recovery path without depending on the compactor preserving task state

## [4.6.0] - 2026-04-15

### Added — Phase 0 Anti-Regression Settings Check

> **Removed in 5.1.0.** See the 5.1.0 entry for context. The entry below is preserved for historical reference only.

- Inline detection in SKILL.md (step 5a, between Phase 0 gate and startup banner): at the start of every session, run a `jq`-based bash check against `~/.claude/settings.json` for the four recommended env vars introduced in 4.5.0 (`CLAUDE_CODE_EFFORT_LEVEL=max`, `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1`, `MAX_THINKING_TOKENS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`) plus `showThinkingSummaries: true`
- New reference: `references/anti-regression-check.md` — full detection script, user prompt template, `jq`-based apply script with auto-backup, marker file format, edge case handling
- Marker file: `~/.claude/.superflow-anti-regression-checked` prevented re-prompting after the user's decision
- Conversational, never auto-applied: three options — `[y]es apply` / `[n]o defer` / `[s]kip-permanently`
- Fail-safe: silent skip if `jq` missing, `settings.json` malformed, or settings file absent

## [4.5.0] - 2026-04-15

### Changed — Anti-Regression Effort Bumps
- **Context**: Anthropic confirmed two regression-causing changes to Claude Code in Feb-Mar 2026: (1) adaptive thinking made the model self-pace reasoning length per turn, sometimes producing zero-thinking turns even at `effort=high`; (2) the default effort level was lowered from `high` to `medium`. See [issue #42796](https://github.com/anthropics/claude-code/issues/42796) and the [bcherny HN reply](https://news.ycombinator.com/item?id=47664442). Independent benchmarks (@Frisch12) show `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` covers only 1 of 5 adaptive code-paths in the cli — subagent paths via `V9H()` still ignore the env var. The legal lever for subagents is the `effort:` frontmatter in `~/.claude/agents/*.md` files
- **deep-* agents**: `effort: high` → `effort: max`. Affects `deep-analyst`, `deep-code-reviewer`, `deep-doc-writer`, `deep-implementer`, `deep-product-reviewer`, `deep-spec-reviewer`. Used in Phase 0 audit, Phase 1 spec review, Phase 2 final holistic review, and llms.txt/CLAUDE.md generation
- **standard-* agents**: `effort: medium` → `effort: high`. Affects `standard-code-reviewer`, `standard-doc-writer`, `standard-implementer`, `standard-product-reviewer`, `standard-spec-reviewer`. Used in per-sprint unified review, plan review, and Phase 3 doc updates
- **fast-implementer**: unchanged at `effort: low` (intentionally cheap for CRUD/config/file-move tasks)
- **Trade-off**: higher token spend per sprint and higher latency in exchange for guaranteed reasoning depth. Particularly important for SuperFlow because subagents (where most code is written and reviewed) cannot fall back to keyword triggers like `ultrathink` — those are detected only on the main user prompt

### Added — Anti-Bypass CI Rule (8a)
- **Rule 8a**: NEVER use `gh pr merge --admin`. After every `gh pr create`, run `gh run list` and wait for CI green before merging. If CI fails, investigate via `gh run view <id> --log-failed`, fix, push, wait for green
- **Rationale**: branch protection exists for a reason. Bypassing CI with `--admin` defeats the entire dual-model review and verification discipline that PAR is built on
- **Rationalization Prevention**: added two new traps to the prevention list — "CI is broken but my tests pass locally" → fix CI first; "I'll use --admin to bypass CI" → NEVER

### Recommended — settings.json env vars
For users running SuperFlow on Claude Code 2.1.108+, add to `~/.claude/settings.json`:
```json
{ "env": {
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
    "MAX_THINKING_TOKENS": "63999",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "400000"
}, "showThinkingSummaries": true }
```
`MAX_THINKING_TOKENS` is only honored when `DISABLE_ADAPTIVE_THINKING=1` is set (adaptive nullifies it — see [claude-agent-sdk#168](https://github.com/anthropics/claude-agent-sdk-typescript/issues/168)). `AUTO_COMPACT_WINDOW=400000` keeps the working context tight enough that CLAUDE.md and SuperFlow rules don't get drowned out in 1M-context sessions.

## [4.4.0] - 2026-03-29

### Added — Sprint-Level Parallel Execution
- **Wave-based sprint dispatch**: Plan now requires `files:` and `depends_on:` per sprint. Phase 2 builds a dependency graph (topological sort) and groups independent sprints into waves. Sprints in the same wave run concurrently in separate worktrees. 6 sprints with partial dependencies → 2-3 waves → ~2x speedup
- **Two-level parallelism**: Sprint-level (wave dispatch) + task-level (within each sprint). Both work together
- **Wave plan shown at approval**: Step 12 (User Approval) now displays the sprint wave breakdown and estimated speedup

### Added — Actionable Phase 0 Summary
- **"Needs Attention Now" section**: Critical/high findings highlighted with concrete fix suggestions. If nothing critical: "codebase is in good shape"
- **Project Health metrics**: Includes duplication, type hygiene, dead code alongside test coverage and tech debt counts
- **Tech Debt Strategy explanation**: Tells the user that findings are saved and will be progressively addressed when future features touch affected modules (via Phase 1 Step 8 cross-reference)
- **Sprint 0 offer**: If critical issues found, offers to create a fix plan before feature work

### Fixed — Stub Sprint Prevention (postmortem: alaya-os Company Intelligence Pipeline)
- **Root cause**: Sprint 5 plan specified 5 tasks (daily briefs, cross-day dedup, LLM report, service storage, TaskIQ emission) but implementer delivered a 60-line stub doing only 1. Reviewers approved because code compiled and tests passed
- **Plan completeness validation** (code-quality-reviewer): New focus area #11 — reviewer compares implementation against sprint plan tasks. Flags stubs, checks implementation depth matches similar components (60 lines vs sibling's 400 = red flag)
- **Product reviewer completeness**: Now validates plan-to-code coverage, not just user-flow dead ends. "Method should do 5 things but only does 1 = blocker"
- **Verbatim plan injection**: Per-Sprint Flow now requires re-reading charter AND pasting exact sprint task list into implementer prompt — prevents context compaction from erasing plan details by later sprints

## [4.3.0] - 2026-03-28

### Added — Codebase Hygiene Pipeline
- **Per-sprint documentation updates**: New Stage 5 "Docs" between PAR and Ship. Dispatches `standard-doc-writer` to update CLAUDE.md and llms.txt based on sprint diff. Skips if nothing materially changed. Phase 2 sprints now have 6 stages (was 5)
- **Code duplication checks**: Implementer searches for existing similar code before writing new. Reviewer checks new code against unchanged files across the codebase — not just within the diff
- **Type redefinition checks**: Implementer searches auto-generated types (`*.generated.ts`, Prisma, GraphQL, OpenAPI) before defining new ones. Reviewer flags `as unknown as` / `as any` casts bridging between duplicate types
- **Dead code checks**: Implementer traces all callers and removes unreachable code after refactoring. Reviewer traces call chains 2-3 levels deep for orphaned functions, handlers, and components
- **Holistic cross-sprint hygiene**: Final holistic review now mandates cross-sprint checks for all three issues — duplication, type redefinition, and dead code that spans sprint boundaries
- **Phase 0 type redefinition diagnosis**: Code Quality agent (Stage 2) now checks for types that duplicate auto-generated ones as part of initial project audit

### Fixed — Phase 0 Re-trigger Loop
- **zsh shell compatibility**: Phase 0 marker detection command used `{ }` brace grouping which breaks in zsh — replaced with `( )` subshell. The broken syntax caused `NO_MARKER` to always appear in output alongside `MARKER_LOCAL`, confusing the LLM into re-triggering Phase 0 every session
- **Auto-commit onboarding artifacts**: Stage 5 no longer asks for user confirmation — commits automatically. Previously, if the session ended before the user said "yes", artifacts were never committed
- **Propagate artifacts to main**: When Phase 0 runs on a feature branch, artifacts (CLAUDE.md, llms.txt, health report) are now copied to main via `git checkout <branch> -- <files>`. Previously, artifacts stayed on the feature branch and every new branch from main re-triggered Phase 0

## [4.2.0] - 2026-03-27

### Added
- **Tech debt cross-reference at spec writing**: After writing the spec (Step 8), cross-references `context.tech_debt` and CLAUDE.md Known Issues with files in the spec. Surfaces relevant tech debt to user: "This spec modifies [module X], there's planned refactoring — include in scope?" Accepted items get a dedicated "Tech Debt Resolution" section and separate plan tasks

### Fixed — Phase 0 Reliability
- **Phase 0 marker detection checks main branch**: When markers not found locally, falls back to `git show main:CLAUDE.md` before triggering Phase 0. Fixes repeated Phase 0 runs on already-onboarded projects when starting from feature branches
- **Phase 0 completion prompts to commit artifacts**: After onboarding, asks user to commit CLAUDE.md, llms.txt, health report so other sessions/branches detect onboarding was done

### Fixed — Approval Gate Visibility
- **Brief and plan displayed inline at approval gates**: Step 7 (Product Brief) and Step 12 (Plan Approval) now explicitly require full content displayed in chat before asking for approval — no more blind "go?" prompts
- **Enforcement rule (compaction-safe)**: "Never ask for approval on content the user hasn't seen"

## [4.1.2] - 2026-03-27

### Fixed — Reasoning Tier Alignment
- **Implementers are sonnet across all tiers**: `deep-implementer` changed from opus to sonnet — all implementation agents now use sonnet (code execution on pre-sliced tasks doesn't need opus)
- **Enforcement table corrected**: reasoning tiers table now accurately reflects implementers as sonnet, reviewers/analysts/doc-writers as opus
- **Expert panel effort: high**: Phase 1 brainstorming agents now explicitly set `effort: high` for deeper creative analysis
- **Phase 3 compaction-safe merge rule**: added `gh pr merge --rebase --delete-branch` to enforcement (survives compaction), preventing fallback to local `git merge` that leaves PRs open
- **Rationalization prevention**: added "I'll just git merge locally" guard

### Known Issues Documented
- Phase 3 post-compaction merge regression: context compaction during merge loop can cause agent to use local `git merge` instead of `gh pr merge`. Mitigated by enforcement rule; full fix requires re-reading phase3-merge.md before each PR merge

## [4.1.1] - 2026-03-27

### Changed — Startup Optimization
- **SKILL.md startup checklist**: 10 steps → 6 steps. Batched 5 detection commands into 1, inlined Phase 0 gate, added stale state detection with `charter_file` check, removed redundant CLAUDE.md re-read
- **superflow-enforcement.md**: compressed Secondary Provider Invocation (13→5 lines), generalized Python-specific test references to `<test-command>`, tightened wording throughout (82→77 lines). All 10 hard rules preserved

### Fixed
- `test -e .git` instead of `test -d .git` for worktree compatibility (`.git` is a file in worktrees)
- Phase 3 resume on main correctly preserved (not treated as stale)
- Phase 1→2 handoff preserved via `charter_file` existence check

## [4.1.0] - 2026-03-26

### Removed — Python Supervisor
- **Deleted `bin/superflow-supervisor`** (213 lines) — CLI entry point
- **Deleted `lib/supervisor.py`** (~1970 lines) — core Popen execution, charter injection, digest, blocker escalation
- **Deleted `lib/launcher.py`** (334 lines) — launch/stop/status/restart
- **Deleted `lib/checkpoint.py`** (52 lines) — checkpoint save/load
- **Deleted `lib/parallel.py`** (61 lines) — ThreadPoolExecutor concurrency
- **Deleted `lib/replanner.py`** (225 lines) — adaptive replanner
- **Deleted `lib/notifications.py`** (196 lines) — Telegram/stdout notifications
- **Deleted `templates/supervisor-sprint-prompt.md`** (69 lines) — sprint prompt template
- **Deleted `templates/replan-prompt.md`** (29 lines) — replanner prompt template
- **Deleted all supervisor tests** — test_supervisor.py, test_launcher.py, test_checkpoint.py, test_parallel.py, test_replanner.py, test_notifications.py, test_integration.py, test_cli.py, mock_claude.sh (~7000 lines of tests)
- **Total: ~10,000 lines removed**

### Why
Subagent-based Phase 2 (Claude orchestrates directly via Agent() calls) works perfectly — proven on 9+ sprints across v4.0 sessions. The Python supervisor was fragile, required Python 3.10+, and added complexity without proportional value.

### Changed
- `SKILL.md`: removed supervisor detection (step 6), dashboard commands, dashboard mode
- `references/phase2-execution.md`: removed Supervisor Mode, Telegram Commands, Dashboard Mode sections
- `references/phase1-discovery.md`: removed auto-launch flow, replaced with clean `/clear` + `/superflow` handoff
- `superflow-enforcement.md`: no changes needed (rules were already subagent-focused)
- `templates/superflow-state-schema.json`: removed `supervisor_available` field
- `README.md`: removed Python 3.10+ requirement, Supervisor CLI section, Overnight Run section
- `CLAUDE.md`, `llms.txt`: updated to reflect new architecture without supervisor
- Deleted remaining Python: `lib/queue.py`, `lib/planner.py`, `tests/`, `examples/` — superflow is now pure Markdown, zero Python dependencies

## [4.0.0] - 2026-03-26

### Added — Expert Panel Brainstorming
- **Expert panel replaces sequential Q&A**: Phase 1 Steps 4-6 dispatch 3-4 parallel expert persona agents (Product GM, Staff Engineer, UX/Workflow, Domain Expert) using `prompts/expert-panel.md`
- **Board Memo synthesis**: orchestrator combines expert outputs into a single message with consensus, disagreements, risks, and decisions needed — replaces 3-5 sequential questions
- **Devil's Advocate**: optional challenge of chosen direction after user reacts to Board Memo

### Added — Autonomy Charter
- **Charter artifact**: generated at end of Phase 1 (Step 12), saved to `docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`. Contains goal, non-negotiables, success criteria, governance mode
- **Charter injection**: injected into sprint prompts (`{charter}` placeholder), replanner context, and reviewer context — single source of truth for autonomous execution boundaries
- **Charter compliance check**: all reviewer agents (code-quality, product) and agent definitions (deep/standard code/product reviewers) now include charter compliance as a review focus area
- **Queue metadata**: `SprintQueue.metadata` dict carries `charter_file`, `governance_mode`, `brief_file` across supervisor restarts

### Added — Adaptive Governance
- **Three governance modes**: light, standard, critical — auto-suggested in Phase 1 based on task complexity, risk, and team familiarity
- **`_required_par_keys()`**: returns governance-aware set of required review evidence keys (light = single reviewer, standard+simple = single, else dual)
- **`_should_run_holistic()`**: conditional holistic review based on governance mode and sprint count (always for critical, never for single-sprint light)
- **`charter_to_queue()`**: new function in `lib/planner.py` for light mode — generates sprint queue directly from charter body without separate plan file

### Added — Cross-Phase Data Flow
- **State schema extensions**: `brief_file`, `charter_file`, `completion_data_file`, `governance_mode` fields in `.superflow-state.json`
- **`_write_completion_data()`**: writes structured `completion-data.json` at end of Phase 2 for Phase 3 merge context
- **Product brief injection**: brief content injected into sprint sessions and reviewer context via queue metadata
- **Merge-update context preservation**: state writes preserve accumulated context across phase transitions

### Added — Observability
- **Popen-based execution**: `subprocess.Popen` replaces `subprocess.run` for sprint execution, enabling live heartbeat writes and progress polling during sprint runtime
- **Intra-sprint progress**: supervisor reads `.superflow/sprint-progress.json` during polling loop, sends `notify_sprint_progress()` on step changes
- **Progress digest**: `_send_digest()` sends periodic summary every N completed sprints (configurable via `digest_interval` parameter) with PR URLs and next sprint info
- **Blocker escalation**: `notify_blocker_escalation()` sends prominent notification when sprint exhausts all retries (MAX_RETRIES_EXCEEDED)
- **Merge reminder**: `notify_merge_reminder()` sent after all sprints complete to prompt Phase 3

### Added — Telegram Full Coverage
- **4 new notification methods**: `notify_sprint_progress()`, `notify_progress_digest()`, `notify_blocker_escalation()`, `notify_merge_reminder()` — total 20 event types (up from 16)

### Changed
- `lib/supervisor.py`: ~1970 lines (up from 1822) — Popen execution, charter injection, governance-aware review, digest, blocker escalation
- `lib/queue.py`: 137 lines (up from 133) — metadata dict support in constructor, load, save
- `lib/planner.py`: ~336 lines (up from 220) — `charter_to_queue()` for light governance mode
- `lib/replanner.py`: 225 lines (up from 212) — reads charter from queue metadata, injects into replan prompt
- `lib/notifications.py`: 196 lines (up from 159) — 4 new methods (progress, digest, blocker, merge_reminder)
- `references/phase1-discovery.md`: ~374 lines (up from ~287) — expert panel, governance mode, charter generation
- `templates/supervisor-sprint-prompt.md`: 69 lines (up from 58) — charter, governance_mode, governance_instructions placeholders
- `templates/replan-prompt.md`: 29 lines (up from 26) — charter placeholder
- `examples/sprint-queue-example.json`: 56 lines (up from 45) — metadata section with charter_file and governance_mode
- `prompts/code-quality-reviewer.md`: 82 lines (up from 77) — charter compliance focus area (#8)
- `prompts/product-reviewer.md`: 76 lines (up from 72) — charter compliance focus area (#5)
- Agent definitions (4 files): deep/standard code/product reviewers now include charter compliance
- Tests: 362+ (up from 333) — new tests for charter injection, Popen execution, governance tiering, digest, blocker escalation, notification methods

## [3.4.0] - 2026-03-25

### Changed — Phase 0 Modular Rewrite
- **Monolith → modular stages**: `phase0-onboarding.md` split from 1,395 lines into 96-line router + 6 stage files loaded on demand. Each stage file is self-contained and survives context compaction
- **Auto-detection replaces interview**: parallel preflight detects stack, team size, CI, formatters, package manager automatically. User confirms with one click instead of answering 3 questions
- **Tiered model usage**: Opus for analysis/security/documentation (deep reasoning), Sonnet for permissions/hooks/scaffolding (mechanical tasks)
- **3 parallel setup branches**: Stage 4 runs documentation, permissions/hooks, and scaffolding concurrently with strict file ownership
- **Informative summary**: ~15 line summary shown to user instead of full health report wall. Full details saved to `docs/superflow/project-health-report.md`
- **State schema expanded**: `context.preflight`, `context.tech_debt`, `context.approval` objects for cross-stage data flow and crash recovery

### Added
- `references/phase0/stage1-detect.md` — parallel preflight, auto-detection, confirmation flow
- `references/phase0/stage2-analysis.md` — 5 parallel agents with tiered model usage
- `references/phase0/stage3-report.md` — health report, informative summary, 3-path approval
- `references/phase0/stage4-setup.md` — 3 concurrent branches, execution matrix by approval mode
- `references/phase0/stage5-completion.md` — markers, tech debt persistence, restart instruction
- `references/phase0/greenfield.md` — extracted greenfield path (G1-G6) with Stage 4 rejoin
- Recovery matrix in router: 5 explicit crash recovery paths, state-based priority over markers

### Fixed
- Greenfield path now populates `context.preflight` for Stage 4 Branch B (permissions need stack info)
- "Skip Phase 0" writes markers in all 3 detection files (prevents re-entry on next run)
- Near-empty repos with manifest files (package.json) treated as existing projects, not greenfield
- `.gitignore` update moved to Stage 5 (always runs, regardless of approval mode)

## [3.3.1] - 2026-03-25

### Fixed — Audit Findings
- **Deep agent prompt differentiation**: deep-tier reviewers/implementers now include additional analysis areas (cross-module side effects, concurrency safety, data migration, threat model, architectural consistency) that justify higher reasoning effort vs standard tier
- **Completion report tests**: 7 new unit tests for `generate_completion_report()` — report structure, PR URLs, test counts, PAR verdicts, holistic gate, missing checkpoints, file output
- **Single-source permissions**: full permissions list now lives only in `phase0-onboarding.md`; README has short example with link to canonical source
- **CLAUDE.md LOC counts**: updated 15 stale line counts in Key Files table

## [3.3.0] - 2026-03-24

### Changed — Review Deduplication & Speed Optimization
- **Unified Review 4→2 agents**: specialize, don't duplicate — Claude handles Product lens (spec fit, user scenarios, data integrity), secondary provider handles Technical lens (correctness, security, architecture). Halves review time and token cost with the same coverage
- **Holistic Review 4→2 agents**: same specialization principle — Claude deep-product + Codex technical (or 2 split-focus Claude)
- **Spec review reasoning xhigh→high**: spec review is high-stakes but xhigh was overkill — `model_reasoning_effort=high` is sufficient
- **Split-focus fallback simplified**: no secondary provider = 2 Claude agents (Product + Technical) instead of 4 with overlapping roles
- **.par-evidence.json new format**: 2 keys (`claude_product`, `technical_review`) + `provider` field, replaces 4-key format
- **Holistic evidence**: separate `REQUIRED_HOLISTIC_KEYS` constant, flat JSON with `claude_product` + `technical_review`

### Added
- **Phase 0 Codex security audit**: 5th agent in onboarding — Codex runs `prompts/codex/audit.md` security section
- **Claude security fallback**: new `prompts/security-audit.md` — when Codex unavailable, Claude deep-analyst runs security audit instead of skipping
- **Phase 0 agent focus separation**: Architecture (code structure, module boundaries, data model) vs DevOps (CI/CD, Docker, deployment, infrastructure) — no overlap

### Removed
- Duplicated Claude code-quality + Codex code reviewer in per-sprint PAR (replaced by single technical reviewer)
- Duplicated Claude product + Codex product reviewer in per-sprint PAR (replaced by single product reviewer)
- `codex_code_review` and `codex_product` PAR evidence keys (replaced by `technical_review`)

## [3.2.0] - 2026-03-24

### Added — Supervisor Enforcement Hardening
- **Validation gates**: PAR evidence validation (`_validate_par_evidence`), sprint summary validation (`_validate_sprint_summary`), evidence verdict validation with configurable pass/fail verdicts
- **Baseline test gate**: heuristic detection for Python (pytest.ini, pyproject.toml), JavaScript (package.json with npm placeholder filter), Ruby (Gemfile), Go (go.mod), Elixir (mix.exs). Fails fast on broken baseline
- **PAR retry gate**: separate retry counter from general sprint retries, prevents wasting retries on review failures
- **Holistic review dispatch**: `run_holistic_review()` with 4 parallel reviewers (2 Claude + 2 Codex, split-focus fallback), retry/fix cycle, evidence emission, cached evidence with `sprint_prs` validation
- **Milestone checkpoints**: `baseline_passed`, `implemented`, `par_validated`, `pr_created` — enables fine-grained crash recovery
- **16 notification event types**: holistic review start/complete, PAR validation failed, baseline failed, resume recovery (up from 11)
- **Milestone-aware resume**: `resume()` checks for existing PRs and milestone state, annotates resume context
- **Preflight checks**: gitignore verification, Claude CLI availability, disk space, queue validation
- **PR verification**: 3-attempt retry with `gh pr view` after push
- **Default branch detection**: `_detect_default_branch()` via `git symbolic-ref` — no longer hardcoded to `main`

### Added — Phase 0 Improvements (PR #37)
- **Interactive onboarding**: mini-interview via AskUserQuestion (project type, stack, goals) before agent dispatch
- **Greenfield path**: G1-G6 steps for empty repos — stack scaffolding templates (Next.js, Python, generic), CI workflow generation
- **State management**: `.superflow-state.json` persists phase/stage for crash recovery across all phases
- **Stage/todo structure**: all phases now use TaskCreate/TaskUpdate for progress tracking
- **Proposal gate**: agents propose changes, user approves before execution
- **Hooks and verification**: `/verify` skill, plugin detection, expanded permissions

### Added — Workflow Discipline (PR #36)
- **Session recovery check**: startup checklist detects uncommitted changes from crashed sessions (stash → test → compare)
- **Test execution discipline**: one process at a time, mandatory timeout, hanging test = unmocked subprocess
- **Commit before review**: Codex sees only committed HEAD — commit fixes before dispatching external reviewers
- **Worktree-before-merge**: exit worktree and remove it BEFORE merge — prevents CWD death when branch is deleted

### Changed
- Supervisor: `lib/supervisor.py` grew from 743 to 1733 lines (enforcement gates, holistic review, validation)
- Tests: 228 tests (up from 149), 4780 lines
- Notifications: 16 event types (up from 11)
- Checkpoint: supports string IDs and named checkpoints (e.g., "holistic")
- Template: conditional `{baseline_status}` placeholder, enforcement section, frontend verification
- Phase 3: worktree cleanup moved from post-merge to pre-merge
- `shell=True` replaced with `shlex.split` + `shell=False` in baseline test runner (security)

## [3.1.0] - 2026-03-23

### Added — Reasoning Tiers & Unified Review
- **Reasoning Tier System** — three tiers (deep/standard/fast) with explicit `effort` frontmatter for Claude agents and `-c model_reasoning_effort` for Codex
- **12 agent definition files** (`agents/`) — native Claude Code subagent `.md` files with YAML frontmatter (name, description, model, effort)
- **3 Codex-optimized prompts** (`prompts/codex/`) — OpenAI Markdown+XML style for code-reviewer, product-reviewer, audit
- **Unified Review** — merged Internal Review + PAR into single 4-agent parallel review (2 Claude + 2 Codex)
- **Adaptive Implementation** — sprint complexity tags (simple/medium/complex) drive model selection (sonnet/opus)
- **Codex audit agent** in Phase 0 — 5th parallel agent alongside 4 Claude analysts
- **Final Holistic Review** expanded to 4 agents (was 2)
- **Agent deployment** in SKILL.md startup checklist — handles pre-v3.1 projects
- **Verdict vocabulary mapping** in enforcement rules — APPROVE/ACCEPTED/PASS all valid

### Changed
- Phase 2: 11 steps → 10 steps (Internal Review + PAR collapsed into Unified Review)
- Phase 0: 10 steps → 11 steps (new Step 1: deploy agent definitions)
- Enforcement Rule 3: 2-reviewer PAR → 4-agent Unified Review with `.par-evidence.json` 4-verdict schema
- Enforcement Rule 9: 2 Opus reviewers → 4 reviewers (2 Claude + 2 Codex) for Final Holistic
- Supervisor: 4-verdict PAR parsing, complexity extraction, reasoning tier template placeholders
- All docs updated: SKILL.md, CLAUDE.md, README.md, llms.txt

### Removed
- `ultrathink` keyword from all subagent prompts (confirmed no-op in subagents via testing)

### Research Findings
- `ultrathink` in Agent tool prompts does NOT trigger high reasoning — it's a CLI-level keyword only
- Agent tool does NOT have `effort` parameter — effort controlled via `.md` frontmatter files in `~/.claude/agents/`
- `codex exec review` cannot combine `--base`/`--uncommitted` with `[PROMPT]` — use stdin for prompt injection
- Codex `-c model_reasoning_effort` works per-invocation (verified: xhigh=435 tokens vs low=207 tokens output)

## [3.0.0] - 2026-03-23

### Added — Supervisor System (Long-Running Autonomy)
- **Python supervisor CLI** (`bin/superflow-supervisor`): orchestrates multi-hour autonomous sprint execution. Each sprint runs as a fresh Claude Code session — no context degradation
- **Sprint Queue** (`lib/queue.py`): DAG-based dependency resolution, atomic file persistence, concurrent-safe with threading.Lock
- **Checkpoint System** (`lib/checkpoint.py`): crash recovery via per-sprint checkpoints with atomic writes
- **Parallel Execution** (`lib/parallel.py`): ThreadPoolExecutor for independent sprints with thread-safe queue access
- **Adaptive Replanner** (`lib/replanner.py`): LLM-powered replanning after each sprint — adjusts remaining work based on what was learned
- **Telegram Notifications** (`lib/notifications.py`): 11 event types (start, complete, fail, retry, skip, block, timeout, replan, resume, all_done, preflight) with phone-friendly formatting
- **Prompt Templates** (`templates/`): supervisor-sprint-prompt.md and replan-prompt.md for supervised Claude sessions
- **Example queue file** (`examples/sprint-queue-example.json`): template for new users
- **149 tests**: unit tests for all modules + integration tests for happy path, crash recovery, blocked sprints, retry scenarios
- **CLI commands**: `run`, `status`, `resume`, `reset` with Telegram integration and adaptive replanning

### Added — Process Improvements
- **Final Holistic Review** (Phase 2): mandatory full-system review after all sprints — catches cross-module issues that per-sprint PAR misses. Two Opus reviewers (Technical + Product) review ALL code together
- **Breakage Scenario requirement**: every review finding must include a concrete, realistic scenario where the issue causes a real problem. No scenario = not a finding. Prevents over-engineering fixes
- **Enforcement rule 9**: holistic review mandatory, with rationalization prevention

### Changed
- **Project architecture**: evolved from pure Markdown skill to hybrid (Markdown prompts + Python companion CLI)
- **Phase 0**: added python3 availability check for supervisor features
- **Phase 2**: added supervisor mode documentation, Final Holistic Review step, breakage scenario test in NEEDS_FIXES handling
- **SKILL.md**: added supervisor detection to startup checklist
- **Env handling**: deny-list approach (block known sensitive keys) instead of whitelist
- **Signal handling**: SIGTERM/SIGINT graceful shutdown with threading.Event
- **All reviewer prompts**: breakage scenario required for every finding

### Fixed (from Final Holistic Review)
- Race condition in parallel mode: queue_lock now passed through _attempt_sprint
- Notification method wiring: correct API calls (notify_sprint_complete vs notify_completed)
- Resume logic: PR existence alone is sufficient for marking completed (worktree may be cleaned up)
- Template substitution: str.replace() instead of str.format() (JSON braces in templates)
- Repo root detection: git rev-parse --show-toplevel with fallback
- Replanner guards: skip/modify only for pending sprints
- Checkpoint atomic writes: tmp+rename pattern matching queue.py
- JSON parser: ANSI escape stripping, scans last 5 lines
- Plan section extraction: exact heading match (prevents "sprint 1" matching "sprint 12")

## [2.1.2] - 2026-03-23

### Changed
- **llms.txt writer**: removed artificial 10KB size limit — per llmstxt.org spec there is no hard cap. For large projects (50k+ LOC), 15-25KB is normal. Completeness over brevity.
- **All 7 prompts**: rewritten following Anthropic Claude 4.6 best practices
  - XML tags for all sections (`<role>`, `<context>`, `<instructions>`, `<constraints>`, `<verification>`)
  - Removed aggressive language ("CRITICAL", "YOU MUST", "NEVER") — Claude 4.6 overtriggers on forceful tone
  - Added WHY for every non-obvious rule
  - Positive framing ("Do Y" instead of "Don't do X")
  - Context at top, instructions at bottom (~30% quality improvement per Anthropic)
  - Self-verification checklist at end of each prompt
  - `<anti_overengineering>` block in Opus prompts (writers)
  - `ultrathink` trigger in writer prompts

## [2.1.1] - 2026-03-23

### Fixed
- **Phase 0 audit depth**: agents were rubber-stamping instead of finding real issues
- Step 2: each analysis agent now has 6-7 mandatory checks with required evidence output
  - Architecture: top 10 largest files, architecture violations with file:line, framework verification via imports
  - Code quality: ALL files >500 LOC listed, TODO/FIXME count, test coverage ratio, files without tests
  - DevOps: Docker `latest` tags, deploy script completeness, security scanning, backup strategy
  - Documentation: path verification with counts, freshness check via git log dates
- Step 3: Health Report template expanded with mandatory quantitative sections (Large Files table, Architecture Violations table, DevOps & Infrastructure checklist, Documentation Freshness table)
- Step 3: anti rubber-stamp rule: "the absence of findings requires proof"
- Step 4 (llms.txt): quantitative audit — coverage % (entries vs source dirs), git log since last marker for new modules
- Step 5 (CLAUDE.md): quantitative audit — path validity count, command verification, new files since last audit

## [2.1.0] - 2026-03-23

### Fixed — Phase 0
- **Critical**: detection table checked old marker `superflow:onboarded` but Step 8 wrote `updated-by-superflow:` — caused infinite re-onboarding loop
- Model was skipping permissions proposal (Step 6.5) and CLAUDE.md/llms.txt audit
- Renumbered all steps 1-10 (no more "Step 6.5")
- Steps 4-5: "Audit & Update" — model must check quality, not just add marker
- Step 7: **"Do NOT skip"** + restart note + "adapt to project toolchain"
- Step 9: Completion Checklist with step references
- Detection: if/else chain, accepts both old and new markers
- Step 2: concrete Agent tool dispatch with `run_in_background: true`
- Step 6: `.worktrees/` gitignore check + enforcement file path
- Step 3: "do not invent problems to fill the template"
- Step 2: analysis agents must use Opus (not Sonnet) — Sonnet hallucinated LangGraph from directory name `graph/` when actual framework was pydantic_graph
- Steps 4-5: doc audit agents must use Opus + `ultrathink` — wrong docs compound errors across all future sessions
- Steps 4-5: "verify framework names by checking imports, not directory names"

### Fixed — Phase 1
- **Critical**: Steps 2.5 and 5.5 fractional numbering → model skipped them (same root cause as Phase 0)
- Renumbered to clean 12 steps: merged research + product expert into Step 2, added Step 3 (Present Research Findings)
- All dispatch steps now have concrete Agent tool / secondary provider invocation patterns
- Steps 9, 11 (reviews): explicit dual-model mechanism with prompts and collection
- Step 4 (Brainstorming): STOP GATE formatting matches Phase 0 pattern
- Step 6 (Product Summary): explicit APPROVAL GATE with accept/change/block paths
- Step 8 (Spec): expanded from 2 lines to full section list
- Step 12: FINAL GATE with re-read instruction before Phase 2
- Directory creation instructions for `docs/superflow/specs/` and `docs/superflow/plans/`

### Fixed — Phase 2
- **Critical**: Review Optimization contradicted enforcement rules — "Simple: spec review only" vs "PAR before every PR". Now clarified as pre-PAR internal review; PAR always mandatory
- Step 5 (review chain): disambiguated from PAR, added prompt references, parallel vs sequential clarified
- Step 3: `.worktrees/` gitignore guard before worktree creation
- Step 4: baseline tests now have actionable instructions (run, record, fail-fast)
- Step 7: post-review test verification separated from baseline
- Step 8 (PAR): explicit prompt references for both reviewers
- Step 9: push command added before `gh pr create`
- Step 10: cleanup only after PR verified
- Added Sprint Completion Checklist (7 items)
- Merged Debugging + Failure Handling into single "Failure & Debugging" section
- No Secondary Provider: lens assignments aligned with PAR definitions
- "Push back" → record disagreement (Phase 2 is autonomous)
- Telegram updates at sprint start and end
- Added BLOCKED status to Completion Report template

### Fixed — Phase 3
- **Critical**: BACKLOG.md referenced but never created — removed (out of scope)
- CI failure handling: explicit 7-step recovery procedure
- Force-push after rebase: explicitly approved in context
- Doc update: dedicated commit on last sprint branch (not separate PR)
- Merge loop: check PR state before attempting merge (skip MERGED/CLOSED)
- Merge verification: concrete `gh pr view --json state` check
- Post-merge report: enriched with sprint titles, test counts, follow-ups
- Trigger phrases expanded: "мерж", affirmative responses
- PR list source: from Completion Report, with fallback `gh pr list`
- Local main sync after all merges
- `.par-evidence.json` cleanup
- Telegram detection method specified

## [2.0.2] - 2026-03-23

### Fixed
- Phase 0 detection: explicit `<!-- superflow:onboarded:YYYY-MM-DD -->` marker instead of weak string matching
- Three-artifact check (CLAUDE.md, llms.txt, health report) with partial onboarding for missing pieces
- Rename `docs/superpowers/` → `docs/superflow/` in all paths

## [2.0.1] - 2026-03-23

### Added
- **Phase 0: Onboarding** — interactive first-run analysis: project health report, tech debt audit, DevOps/CI check
- **Phase 3: Merge** — user-initiated sequential rebase merges with CI gate, doc update, cleanup
- **llms.txt support** — standard project documentation for all LLMs (llmstxt.org); #1 recommendation in health report if missing
- **Product Brief** (Phase 1, Step 5.5) — Jobs to be Done + user stories before technical spec
- **Demo Day completion report** — product-oriented sprint summaries instead of tech log
- **Auto-enforcement check** — Phase 0 verifies `superflow-enforcement.md` is in `~/.claude/rules/`
- **New prompts**: `llms-txt-writer.md`, `claude-md-writer.md` with best practices

### Changed
- **Fully independent from Superpowers**: v1.0.0 loaded 7 Superpowers skills (~113KB) + own SKILL.md (~19KB) = ~132KB total context. v2.0.0 is ~30KB with 2x more features — **77% context reduction** while doubling capability (4 phases, 8 prompts, 4 references vs 2 phases, 5 prompts, 2 references). Superpowers dependency removed in v1.4.0 (PR #4).
- Phase 0: CLAUDE.md auto-updates silently (no approval needed)
- Phase 0: all generated documentation must be in English
- Phase 0: 4 parallel analysis agents (architecture, code quality, DevOps, documentation)
- Phase 2: implementers read `llms.txt` as first step for project context
- Phase 2: documentation update moved to Phase 3 (pre-merge)
- README: complete overhaul with all 4 phases, interaction labels, permissions guide

## [1.4.0] - 2026-03-22

### Changed
- **Context weight reduced by 68%** (41KB → 13KB): monolithic SKILL.md split into modular references + prompts (#4)
- **Provider-agnostic reviews**: replaced Codex-specific logic with generic secondary provider detection (Codex > Gemini > Aider > split-focus Claude) (#3)
- **Slim README**: condensed to essentials, moved best practices to separate reference (#5)
- **Fully decoupled from Superpowers**: removed all direct references to obra/superpowers skill files. Superflow now stands alone — origin acknowledged in README only.

### Added
- Compaction-resilient architecture: durable rules in `~/.claude/rules/`, thin SKILL.md router
- "When to Use" scope guidance
- PAR enforcement with concrete 6-step algorithm + `.par-evidence.json` gate

## [1.3.0] - 2026-03-22

### Fixed
- Codex detection: replaced `which codex` with `codex --version 2>/dev/null` smoke test (binary can exist without API keys)
- Heredoc templates in code-quality-reviewer.md and product-reviewer.md: changed `<<'PROMPT'` (quoted, blocks variable expansion) to `<<PROMPT` (unquoted, allows `$(git diff ...)` to expand)

### Added
- Provider-agnostic review fallback: when Codex is unavailable, dispatch TWO Claude agents with split focus (technical + product) instead of skipping reviews
- macOS timeout fallback: `perl -e 'alarm N; exec @ARGV'` as universal fallback when neither `timeout` nor `gtimeout` is available. All timeout references now use `$TIMEOUT_CMD` variable
- Timeout Helper section in SKILL.md with startup detection snippet (gtimeout > timeout > perl fallback)
- `mkdir -p` for spec and plan directories before writing files (prevents failure on first run)

## [1.2.0] - 2026-03-21

### Added
- **ultrathink reasoning**: spec review, plan review, and product acceptance prompts now use `ultrathink` for extended thinking, regardless of user's default reasoning effort
- **Codex in brainstorming**: Codex dispatched as Product Expert during Phase 1 brainstorming (parallel with Claude conversation) — two AI models produce more diverse ideas
- **Recommended launch section**: `claude --dangerously-skip-permissions` for autonomous execution, reasoning effort guidance (high/max + ultrathink)
- **Model strategy table**: detailed per-task model and reasoning recommendations (Opus for planning/review, Sonnet for implementation)

## [1.1.0] - 2026-03-21

### Fixed
- Codex CLI invocation: updated from `codex --approval-mode full-auto --quiet -p` to `codex exec --full-auto` (new Codex CLI API)
- macOS compatibility: use `gtimeout` from coreutils instead of `timeout`
- PR base strategy: all PRs now target `main` to prevent auto-close on squash merge
- Superpowers attribution: corrected to community project (obra/superpowers), not official Anthropic

### Added
- Product Acceptance Review enforcement: marked as NON-NEGOTIABLE with 6-step checklist
- Mandatory self-reminder loop: sprint completion checklist before PR creation
- Checkpoint re-read after each sprint completion

## [1.0.0] - 2026-03-19

### Added
- Initial release
- Two-phase workflow: collaborative product discovery + autonomous execution
- PR-per-sprint with git worktrees
- Dual-model reviews (Claude + Codex)
- Product acceptance review stage
- Context drift prevention
- 5 prompt templates (implementer, spec-reviewer, code-quality-reviewer, product-reviewer, testing-guidelines)

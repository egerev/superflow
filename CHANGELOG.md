# Changelog

All notable changes to superflow will be documented in this file.

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

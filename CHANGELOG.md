# Changelog

All notable changes to superflow will be documented in this file.

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

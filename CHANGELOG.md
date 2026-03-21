# Changelog

All notable changes to superflow will be documented in this file.

## [2.0.0] - 2026-03-21

### Changed
- **BREAKING: Remove Codex CLI dependency** — replaced all Codex-specific invocations with provider-agnostic parallel Agent dispatch. The skill now works with Claude Code alone, no OpenAI API key or Codex CLI required
- **Parallel review strategy** — instead of "Claude + Codex" dual-provider pattern, use two independent Claude agents with split review focus (correctness vs architecture, spec-fit vs user-scenarios). Two reviewers with different lenses catch more bugs than one, regardless of provider
- Removed `coreutils`/`gtimeout` macOS requirement (was only needed for Codex timeout)
- Updated all prompt templates: replaced Codex invocation blocks with parallel focus split instructions
- Simplified requirements: only Claude Code CLI + GitHub CLI needed

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

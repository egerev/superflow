# Phase 0 Rewrite — Product Brief

## Problem Statement
Phase 0 is a 1,395-line monolith that loads entirely into context, executes sequentially, asks questions it could auto-detect, and uses Opus for tasks Sonnet can handle. It needs restructuring into modular stage files with parallel execution and tiered model usage.

## Jobs to be Done
When I first run Superflow on a project, I want a fast, informative audit + documentation setup, so I can efficiently work with Phase 1 on real tasks.

## User Stories
1. As a user, I want Phase 0 to auto-detect project properties instead of asking questions I can infer from the filesystem
2. As a user, I want informative but concise output — not a wall of text, but enough to understand what happened and why
3. As a vibe coder, I want security issues highlighted immediately so I don't ship vulnerabilities
4. As a user, I want Phase 0 to run fast (parallel tasks, Sonnet where appropriate, Opus for deep analysis)
5. As a user, after Phase 0 I want a clear "clear + restart" instruction for a clean Phase 1 start

## Success Criteria
- phase0-onboarding.md split into ~7 stage files, each <200 lines
- Zero mandatory questions for existing projects (only 1 confirmation)
- Phase 0 wall-clock time reduced via parallelism
- Sonnet for docs audit, permissions, hooks; Opus only for analysis + security
- Greenfield path in separate file (same logic, better organization)
- Tech debt captured in health report and persisted for Phase 1

## Edge Cases
- No git repo → greenfield path (separate file)
- No python3 → skip supervisor prerequisites
- Context compaction mid-Phase 0 → stage files are small, re-read current one
- User says "skip" → mark Phase 0 as done with defaults, proceed to Phase 1

## Not in Scope
- Supervisor integration for Phase 0
- Greenfield path rewrite (moves to separate file as-is)
- Phase 1/2/3 changes
- New features (restructuring only + UX improvements)

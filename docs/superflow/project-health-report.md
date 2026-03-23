# Project Health Report

## Overview
- **Project:** Superflow v3.0.0 — Claude Code skill (hybrid: Markdown prompts + Python companion CLI)
- **Stack:** Python 3.10+ (stdlib only, zero third-party dependencies), Markdown skill files
- **Size:** 45 non-cache files, ~4,000 LOC Python, ~5,100 LOC Markdown
- **Tests:** 130 test functions across 8 test files, all passing (0.869s)
- **Test coverage ratio:** 1.94x (2,182 test LOC / 1,126 source LOC)
- **License:** MIT (with Superpowers attribution)

## Large Files (>500 LOC) -- Refactoring Candidates

| File | LOC | Role | Recommendation |
|------|-----|------|----------------|
| `tests/test_supervisor.py` | 907 | Test file (37 tests) | Acceptable for test files |
| `references/phase0-onboarding.md` | 888 | Phase 0 documentation | Acceptable for reference docs |
| `lib/supervisor.py` | 743 | Core supervisor module | **Primary refactoring target** -- 9 distinct responsibilities (worktree lifecycle, prompt building, utilities, sprint execution, notifications, preflight, reporting, run loop, crash recovery). Natural split: `worktree.py` (55 LOC), `prompt_builder.py` (92 LOC), `report.py` (237 LOC), `preflight.py` (78 LOC), leaving ~280 LOC core |
| `tests/test_integration.py` | 565 | Integration tests (8 tests) | Acceptable for test files |

## Architecture Violations

### Circular Dependencies (resolved via deferred imports)

| Cycle | Evidence | Impact |
|-------|----------|--------|
| supervisor <-> parallel | `supervisor.py:495` imports `parallel.execute_parallel`; `parallel.py:36` imports `supervisor.execute_sprint` | Works at runtime via deferred imports; design coupling |
| supervisor <-> replanner | `supervisor.py:474` imports `replanner.replan`; `replanner.py:8` imports `supervisor._filtered_env` | Asymmetric: replanner has top-level import of supervisor's private function |

### Private API Leakage

`_filtered_env` (prefixed `_`, defined at `supervisor.py:220`) is imported cross-module by `replanner.py:8`. Should be promoted to public or extracted to a shared utility module.

### No prompt-to-code violations detected. Markdown prompts use generic placeholders, no implementation details.

## Security Findings

| Priority | Issue | Location | Evidence |
|----------|-------|----------|----------|
| P0 | **Env deny-list too narrow** | `lib/supervisor.py:212-222` | `_filtered_env()` blocks only 7 keys. Missing: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `SLACK_TOKEN`, `STRIPE_SECRET_KEY`, SSH agent vars. All unblocked secrets pass to child `claude` subprocesses. |
| P0 | **Path traversal in queue** | `lib/queue.py:17`, `lib/supervisor.py:155-164` | `build_prompt()` does `os.path.join(repo_root, plan_file)` then `open()` without validating the path stays within repo. A queue entry with `../../etc/passwd` could read arbitrary files. |
| P1 | **Secret-bearing CLI flags** | `bin/superflow-supervisor:112,128` | `--telegram-token` passed as CLI arg leaks via shell history and `/proc` process listings. Env vars are safer. |

## Technical Debt

| Priority | Issue | Location | Evidence | Recommendation |
|----------|-------|----------|----------|----------------|
| P0 | Stale test count in docs | CLAUDE.md:73, llms.txt:57, README.md:160 | Claims 149 tests; actual: 130 `def test_` functions | Update all docs to 130 |
| P0 | Stale line counts in llms.txt | llms.txt:25 | phase0-onboarding.md: 288 claimed vs 888 actual; test_notifications.py: 337 vs 112; CLAUDE.md: 75 vs 87 | Regenerate llms.txt line counts |
| P1 | 3 dead notification methods | `lib/notifications.py:93,113,125` | `notify_sprint_retry`, `notify_timeout`, `notify_crash_resume` -- defined but never called anywhere in codebase | Wire into supervisor or remove |
| P1 | Unused import in CLI | `bin/superflow-supervisor:12` | `generate_completion_report` imported but never used (called internally by `run()`) | Remove from import |
| P1 | JSON parsing duplication | `supervisor.py:190-209`, `replanner.py:104-123` | Same "parse JSON from last line" pattern duplicated; supervisor strips ANSI but replanner does not | Extract shared utility |
| P1 | CLI argument duplication | `bin/superflow-supervisor:106-114,122-130` | 7 identical `add_argument` calls for `run` and `resume` subparsers | Use shared parent parser |
| P2 | Duplicate .gitignore entry | `.gitignore:1,8` | `.worktrees/` appears twice | Remove duplicate |
| P2 | Missing `.env` in .gitignore | `.gitignore` | Users following README's `TELEGRAM_BOT_TOKEN` pattern may create `.env` which is not gitignored | Add `.env` to .gitignore |
| P2 | Duplicate step numbering | `lib/supervisor.py:249,254` | Two comments labeled `# 3.`, then jumps to `# 13.` | Fix numbering |
| P2 | CLAUDE.md Known Issue #2 stale | `CLAUDE.md:85` | Claims permissions "duplicated verbatim" at specific line numbers; blocks have diverged significantly | Update or remove |
| P2 | TDD cycle duplication | `implementer.md:23-31`, `testing-guidelines.md:13-21` | Same concept (different wording) seen twice by agent since implementer includes testing-guidelines | Already documented in CLAUDE.md |

## Code Quality

| Metric | Value | Assessment |
|--------|-------|------------|
| TODO/FIXME/HACK/XXX comments | 0 | Clean |
| Source files without test file | 0/7 | Full coverage |
| Test:Source LOC ratio | 1.94x | Good |
| All tests passing | 130/130 (0.869s) | Green |
| Linter config | None | No static analysis enforcement |
| Pre-commit hooks | None | No automated quality gates |
| Dead code items | 4 (1 unused import, 3 dead methods) | Minor |

### Weak Test Coverage Areas

- `lib/notifications.py`: 10 tests cover only `__init__`/`is_configured`/`_format_progress`/`notify` (stdout fallback). None of the 11 event-type methods are directly tested. No Telegram-send coverage.
- `tests/test_integration.py`: Mock-heavy at top level -- patches subprocess/worktree/disk/parallel. Lower-level suites (queue, checkpoint, cli) do real file I/O.

## DevOps & Infrastructure

| Area | Status | Details |
|------|--------|---------|
| Docker | N/A | Not applicable for a Claude Code skill |
| CI/CD | **Missing** | No `.github/workflows/`, no pipeline. 130 tests run locally only. Phase 3 docs assume CI gates via `gh pr checks` but no pipeline exists. |
| Deploy | Manual | `git clone` + `ln -s` per README. No package registry. |
| Security scanning | **Missing** | No dependabot, no SAST tools. Mitigated by zero third-party deps. |
| Backups | N/A | Dev tool; persistence is sprint queue JSON + checkpoints (gitignored, local-only) |
| .gitignore | Adequate | Covers `.worktrees/`, `.par-evidence.json`, `__pycache__/`, `*.pyc`, `*.swp`, `.DS_Store`, checkpoints. Missing: `.env`, `CLAUDE.local.md` |
| LICENSE | Present | MIT, Superpowers attribution included |
| CHANGELOG | Current | 11 versions (1.0.0-3.0.0), follows Keep a Changelog format |
| Versioning | Manual | Version in README + CHANGELOG only, no `__version__` or tags |
| bin/superflow-supervisor | Correct | `#!/usr/bin/env python3`, mode 755, portable sys.path setup |

## Documentation Freshness

| Doc | Last Updated | Status | Issues |
|-----|-------------|--------|--------|
| README.md | 2026-03-23 | Current | Test count "140+" is stale (actual: 130). Permissions block diverged from Phase 0. |
| CLAUDE.md | 2026-03-23 | Mostly current | Test count/LOC stale. Known Issue #2 line numbers wrong. All 19 Key Files paths valid. |
| llms.txt | 2026-03-23 | **Stale** | All 32 paths valid. 5 critical line count discrepancies (phase0: 288->888, test_notifications: 337->112, CLAUDE.md: 75->87). Test count 149->130. |
| CHANGELOG.md | 2026-03-23 | Current | All versions documented. Jump from 1.4.0 to 2.0.1 (no 2.0.0). |
| SKILL.md | 2026-03-23 | Current | Minor: 85->86 lines in self-reference |
| superflow-enforcement.md | 2026-03-23 | Current | Identical to deployed ~/.claude/rules/ copy |
| Phase references (4 files) | 2026-03-23 | Current | All exist and are referenced correctly |
| Prompts (7 files) | 2026-03-23 | Current | All exist and are referenced correctly |

## Supervisor Status

- Python 3.14.3 available
- Supervisor: operational (`bin/superflow-supervisor` with 4 CLI commands: run, status, resume, reset)
- Crash recovery: checkpoint-based (`lib/checkpoint.py`)
- Parallel execution: ThreadPoolExecutor (`lib/parallel.py`)
- Adaptive replanning: Claude-powered (`lib/replanner.py`)

## Recommendations

1. **[Security] Replace env deny-list with allowlist** in `_filtered_env()` -- current approach leaves credentials exposed. Expand deny-list immediately; consider allowlist long-term.
2. **[Security] Add path validation** in `build_prompt()` -- reject absolute paths and `..` traversal in `plan_file`.
3. **[Docs] Update stale metrics** -- fix test count (130), line counts in llms.txt and CLAUDE.md. Regenerate llms.txt.
4. **[Quality] Add CI pipeline** -- GitHub Actions for `python3 -m pytest tests/` at minimum. Phase 3 already assumes CI gates.
5. **[Quality] Wire or remove dead notification methods** -- 3 methods in notifications.py are never called.
6. **[Architecture] Consider splitting supervisor.py** -- 743 LOC with 9 responsibilities. Natural extraction points identified.
7. **[DevOps] Add `.env` to .gitignore** -- prevent accidental secret commits.

<!-- updated-by-superflow:2026-03-24 -->

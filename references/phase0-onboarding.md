# Phase 0: Onboarding (FIRST RUN — INTERACTIVE)

Runs once per project. Skip if Superflow artifacts already exist (see detection below).
This phase is **conversational** — talk to the user, don't just execute silently.

**All documentation output MUST be in English.** If the user communicates in another language, the LLM translates — but all generated files (llms.txt, CLAUDE.md, reports) are English.

## Detection: Is This a First Run?

Phase 0 leaves an **exact marker** in each file it touches:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

**Detection logic** (check in order, stop at first match):

1. If `CLAUDE.md` does NOT contain `<!-- updated-by-superflow:` or `<!-- superflow:onboarded` → **full Phase 0** (first run)
2. If `llms.txt` does NOT contain `<!-- updated-by-superflow:` or `<!-- superflow:onboarded` → **partial**: audit/create llms.txt only
3. If `docs/superflow/project-health-report.md` does NOT exist → **partial**: generate health report only
4. All present → **skip Phase 0**, proceed to Phase 1

> Both `<!-- updated-by-superflow:` (v2.0.3+) and `<!-- superflow:onboarded` (v2.0.2) are valid markers. New runs always write the new format.

**NOT valid markers** (these can exist without Superflow):
- The word "superflow" in CLAUDE.md (could be mentioned casually)
- `docs/superflow/` directory alone (could be created by user)
- `.par-evidence.json` (created by Phase 2, not Phase 0)

---

## Step 1: Deploy Agent Definitions

This must run BEFORE any agent dispatches.

1. Create the agents directory if missing:
```bash
mkdir -p ~/.claude/agents/
```

2. Copy agent definitions from the skill:
```bash
cp ~/.claude/skills/superflow/agents/*.md ~/.claude/agents/
```

3. Verify deployment:
```bash
ls ~/.claude/agents/ | grep -c "\.md$"
```
Expected result: 12+ agent definition files.

## Step 2: Greet & Announce

Tell the user (in their language):
> "This is the first Superflow run on this project. Give me a moment — I'll explore the codebase."

Then proceed to analysis.

## Step 3: Project Analysis (background)

Dispatch **5 parallel agents** — 4 Claude deep-analyst agents and 1 Codex audit agent (`run_in_background: true` for each).

**Critical: use deep-analyst agents for analysis, not default agents.** Wrong documentation is worse than no documentation — a default agent may hallucinate framework names based on directory structure (e.g., calling pydantic_graph "LangGraph" because the directory is named `graph/`). Analysis agents must verify by reading actual imports and code, not guessing from names.

Each agent prompt MUST include the **mandatory checks** below. Agents must show evidence (file paths, counts, code snippets) for every finding — no unsupported claims.

```
Agent(subagent_type: "deep-analyst", run_in_background: true, prompt: "Architecture analysis. Mandatory checks — show evidence for each:
  1. List all top-level directories with file counts and total LOC per directory
  2. Identify frameworks/libraries by reading actual `import` statements (NOT by guessing from directory names)
  3. Map the data model: list all DB models/schemas with field counts
  4. Find architecture violations: does business logic import from adapters/infrastructure? List every violation with file:line
  5. Identify the top 10 largest files by LOC — these are refactoring candidates
  6. Map key entry points (API routes, CLI commands, event handlers)")

Agent(subagent_type: "deep-analyst", run_in_background: true, prompt: "Code quality analysis. Mandatory checks — show evidence for each:
  1. List ALL files >500 LOC with exact line counts (use `wc -l` or count lines)
  2. Find all TODO/FIXME/HACK/XXX comments — count and list top 10
  3. Count test files vs source files — calculate coverage ratio
  4. Find source files with NO corresponding test file
  5. Check for code duplication: similar function signatures across files
  6. Check linter config exists and is enforced (pre-commit hooks, CI checks)
  7. Find dead code: unused imports, unreachable functions (if tooling available)")

Agent(subagent_type: "deep-analyst", run_in_background: true, prompt: "DevOps analysis. Mandatory checks — show evidence for each:
  1. Docker Compose: count services, check for `latest` tags (non-deterministic), check volume mounts
  2. CI/CD: list all GitHub Actions workflows, check what they actually test/deploy
  3. Deploy script: does it run migrations? Does it have rollback? Health checks?
  4. Security scanning: is dependabot/renovate configured? CodeQL or similar?
  5. Backup strategy: is there one for databases/persistent storage?
  6. Environment management: .env.example exists? Secrets management?
  7. .gitignore completeness: check for common misses (.env, __pycache__, node_modules, .worktrees/)")

Agent(subagent_type: "deep-analyst", run_in_background: true, prompt: "Documentation analysis. Mandatory checks — show evidence for each:
  1. List all documentation files with last-modified dates (git log)
  2. Compare README claims against actual project state (commands, setup steps)
  3. If llms.txt exists: count entries vs actual source directories — coverage %
  4. If CLAUDE.md exists: check every documented path exists, check commands work
  5. Check for stale references: grep for file paths in docs, verify each exists
  6. API documentation: is it auto-generated or manual? Is it current?")
```

**5th agent — Codex audit:**
```bash
$TIMEOUT_CMD 900 codex exec --full-auto -c model_reasoning_effort=xhigh --ephemeral "$(cat ~/.claude/skills/superflow/prompts/codex/audit.md)" 2>&1
```
Run with `run_in_background: true`.

> **No Codex?** If Codex is not installed or `$TIMEOUT_CMD` is unavailable, skip the Codex audit. The 4 Claude agents provide sufficient coverage. Log: "Codex audit skipped — codex CLI not found."

All 5 agents run in parallel. Wait for all to complete, then synthesize into a concise project profile.

**After synthesis, cross-check**: do framework/library names in the profile match actual `import` statements in code? Do file counts match across agents? Resolve discrepancies before proceeding.

## Step 4: Present Project Health Report

Show the user the results conversationally — like a colleague who just explored the codebase. **Every claim must have evidence** (file path, count, command output).

```
## Project Health Report

### Overview
- Stack: [detected — verify by checking imports, not directory names]
- Size: [source files count] source files, [total LOC] LOC
- Tests: [test files count] test files, [test functions count] test functions
- Test coverage ratio: [test files / source files]%

### Large Files (>500 LOC) — Refactoring Candidates
| File | LOC | Role | Recommendation |
|------|-----|------|----------------|
| path/to/file.py | 1,675 | description | Split into X, Y |
| ... | ... | ... | ... |

### Architecture Violations
| Violation | File:Line | Details |
|-----------|-----------|---------|
| Business imports adapter | file.py:42 | `from adapters.x import Y` |
| ... | ... | ... |

(If no violations found, state: "No architecture violations detected — [layer structure description]")

### Technical Debt
| Priority | Issue | Location | Evidence | Recommendation |
|----------|-------|----------|----------|----------------|
| P0       | ...   | file:line | what was found | fix suggestion |
| P1       | ...   | ...      | ...      | ...            |
| P2       | ...   | ...      | ...      | ...            |

### DevOps & Infrastructure
- Docker: [N services, any `latest` tags?, volumes?]
- CI/CD: [what's configured, what's missing]
- Deploy: [migrations included?, rollback?, health checks?]
- Security: [dependabot?, CodeQL?, scanning?]
- Backups: [strategy or "none detected"]

### Documentation Freshness
| Doc | Last Updated | Status |
|-----|-------------|--------|
| README.md | YYYY-MM-DD | [current/stale] |
| CLAUDE.md | YYYY-MM-DD | [current/stale] |
| llms.txt | YYYY-MM-DD | [current/stale — N entries vs M source dirs] |

### Recommendations
1. [actionable improvement with specific file/location]
2. [actionable improvement with specific file/location]
3. ...
```

If a section has no issues, state that explicitly with evidence — "No files >500 LOC" or "All 17 documented paths verified to exist". Do not invent problems, but do not rubber-stamp either — **the absence of findings requires proof**.

Save report to `docs/superflow/project-health-report.md` (in English).

## Step 5: Audit & Update llms.txt

`llms.txt` is a standard (llmstxt.org) that helps any LLM understand a project. **Always audit, even if it exists.**

**Use deep-doc-writer agents for this step.** Wrong documentation actively misleads all future LLM interactions — it is worse than no documentation.

Dispatch with:
```
Agent(subagent_type: "deep-doc-writer", prompt: "...")
```

### If llms.txt doesn't exist:
**This MUST be the #1 recommendation in the Health Report.**

> "This project has no llms.txt — must-have documentation for LLMs. I recommend creating it."

Use `prompts/llms-txt-writer.md` for best practices. Verify every framework/library name by checking actual imports in the code — never guess from directory names.

### If llms.txt exists:
**Quantitative audit** — produce numbers, not just "looks good":
1. Count source directories → count llms.txt entries → report coverage: "llms.txt covers X of Y source directories (Z%)"
2. Check every linked path exists: `for each path in llms.txt: verify file/dir exists`
3. List stale entries (path doesn't exist or description is wrong)
4. List missing entries (key source dirs not in llms.txt)
5. Check `git log --since="last marker date"` — were new modules added since last audit?
6. **Verify framework names**: check actual `import` statements, not directory names
7. Report: "llms.txt covers N/M dirs (X%). Found K stale entries, J missing entries."

## Step 6: Audit & Update CLAUDE.md

**Always audit, even if it exists.** Use `prompts/claude-md-writer.md` for best practices.

**Use deep-doc-writer agents for this step.** CLAUDE.md is the foundation for every future Claude interaction with this project. Errors here compound across all sessions.

Dispatch with:
```
Agent(subagent_type: "deep-doc-writer", prompt: "...")
```

### If CLAUDE.md doesn't exist:
Create it automatically (in English) with:
- Project overview (stack, purpose, architecture)
- Key files table (file → purpose)
- Commands (dev, build, test, lint)
- Conventions discovered (naming, language, patterns)
- Architecture notes (data flow, key modules)

Tell user: > "Created CLAUDE.md with project description."

### If CLAUDE.md exists:
**Quantitative audit** — produce numbers, not just "looks good":
1. Check every documented file path exists: count valid / total → "X/Y paths valid (Z%)"
2. Run every documented command (dev, test, lint) — do they work?
3. Check `git log --since="last marker date"` — list new files/modules added since last audit
4. Cross-reference architecture description with actual imports — is the described structure current?
5. List what's missing: new key files not documented, new commands not listed
6. Preserve user's custom sections — only touch factual parts
7. Fix silently if stale, tell user what changed

Tell user: > "Audited CLAUDE.md — [X/Y paths valid, N new modules since last audit, fixed K issues: brief list]."

## Step 7: Verify Enforcement Rules & Gitignore

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version at `~/.claude/skills/superflow/superflow-enforcement.md`)

Check `.worktrees/` is in `.gitignore`:
```bash
git check-ignore -q .worktrees || echo ".worktrees/" >> .gitignore
```

This file survives context compaction and is critical for Phase 2 discipline.

## Step 7.5: Check Supervisor Prerequisites

Check if the supervisor system is available:

```bash
python3 --version 2>/dev/null && echo "SUPERVISOR_AVAILABLE" || echo "SUPERVISOR_UNAVAILABLE"
```

- If python3 is available: note "Supervisor: available" in the health report
- If python3 is missing: note "Supervisor: unavailable (python3 not found). Long-running autonomous mode requires python3." No error — single-session mode still works.

## Step 8: Permissions Setup for Autonomous Execution

**Do NOT skip this step.** Check if `~/.claude/settings.json` has the required allow permissions for Superflow.

If missing, propose to the user:
> "Phase 2 runs autonomously — dozens of commands without human approval. To enable this, I need to add permissions for git, GitHub CLI, and secondary providers to your settings. Without this, you'll get prompted on every command. Add permissions?"

If user agrees, add to `~/.claude/settings.json` (merge with existing, don't overwrite). **Adapt to this project's toolchain** — use npm/yarn/bun/pnpm as appropriate:

```json
{
  "permissions": {
    "allow": [
      "Bash(git worktree *)", "Bash(git checkout *)", "Bash(git add *)",
      "Bash(git commit *)", "Bash(git push *)", "Bash(git push --force-with-lease *)",
      "Bash(git rebase *)", "Bash(git pull *)", "Bash(git check-ignore *)",
      "Bash(git log *)", "Bash(git diff *)",
      "Bash(gh pr *)",
      "Bash(npm test *)", "Bash(npm run *)",
      "Bash(codex *)", "Bash(gemini *)", "Bash(aider *)",
      "Bash(gtimeout *)", "Bash(timeout *)"
    ]
  }
}
```

If user declines: continue, but warn that Phase 2 will require manual approval for each command.

> **Note on restart:** Permissions changes in `settings.json` may require restarting Claude Code to take effect. If so, tell the user: "Permissions added. Please restart Claude Code and run `/superflow` again — Phase 0 will detect the markers and skip straight to Phase 1."

## Step 9: Leave Markers

After all steps above, write the **same marker** in every file you touched:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

1. **CLAUDE.md**: append at the very end
2. **llms.txt** (if created/updated): append at the very end
3. **docs/superflow/project-health-report.md**: created as part of Step 4

All three must exist for Phase 0 to be fully skipped on next run.

## Step 10: Completion Checklist

**Walk through each item below. For each, verify it was completed. If not, go back to the relevant step.**

- [ ] Agent definitions deployed to `~/.claude/agents/` (Step 1)
- [ ] Health report saved to `docs/superflow/project-health-report.md` (Step 4)
- [ ] llms.txt audited — created if missing, updated if stale (Step 5)
- [ ] CLAUDE.md audited — created if missing, updated if stale (Step 6)
- [ ] Enforcement rules verified in `~/.claude/rules/` (Step 7)
- [ ] `.worktrees/` is in `.gitignore` (Step 7)
- [ ] Python3 availability checked (Step 7.5)
- [ ] **Permissions proposed to user** — accepted or declined, but MUST be asked (Step 8)
- [ ] Markers `<!-- updated-by-superflow:YYYY-MM-DD -->` written in CLAUDE.md, llms.txt, and health report (Step 9)

If any item is unchecked, go back to the referenced step and complete it before proceeding.

## Step 11: Hand Off to Phase 1

Ask the user:
> "Done! I've explored the project. What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

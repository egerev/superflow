# Phase 0: Onboarding (FIRST RUN — INTERACTIVE)

Runs once per project. Skip if Superflow artifacts already exist (see detection below).
This phase is **conversational** — talk to the user, don't just execute silently.

**All documentation output MUST be in English.** If the user communicates in another language, the LLM translates — but all generated files (llms.txt, CLAUDE.md, reports) are English.

## Detection: Is This a First Run?

Phase 0 leaves an **exact marker** in each file it touches:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

Check three artifacts:

| # | Check | If missing |
|---|-------|-----------|
| 1 | `CLAUDE.md` contains `<!-- superflow:onboarded` | Run full Phase 0 |
| 2 | `llms.txt` contains `<!-- superflow:onboarded` | Partial: audit/create llms.txt only |
| 3 | `docs/superflow/project-health-report.md` exists | Partial: generate health report only |

**Decision logic:**
- **All 3 present** → skip Phase 0, go to Phase 1
- **CLAUDE.md marker missing** → full Phase 0 (first run)
- **CLAUDE.md marker present, but llms.txt or health report missing** → partial onboarding (only the missing pieces)

**NOT valid markers** (these can exist without Superflow):
- The word "superflow" in CLAUDE.md (could be mentioned casually)
- `docs/superflow/` directory alone (could be created by user)
- `.par-evidence.json` (created by Phase 2, not Phase 0)

---

## Step 1: Greet & Announce

Tell the user (in their language):
> "This is the first Superflow run on this project. Give me a moment — I'll explore the codebase."

Then proceed to analysis.

## Step 2: Project Analysis (background)

Dispatch parallel background agents:
- **Architecture agent**: directory structure, key files, frameworks, dependencies, data model
- **Code quality agent**: hotspots, complexity, test coverage, linting setup
- **DevOps agent**: CI/CD pipeline, .gitignore completeness, env management, deployment setup
- **Documentation agent**: existing docs (README, CLAUDE.md, llms.txt, comments density, API docs)

Synthesize into a concise project profile.

## Step 3: Present Project Health Report

Show the user the results conversationally — like a colleague who just explored the codebase:

```
## Project Health Report

### Overview
- Stack: [detected]
- Size: [files, LOC]
- Test coverage: [detected or "no tests found"]

### Strengths
- [what's well-structured]

### Technical Debt
| Priority | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| P0       | ...   | ...      | ...            |
| P1       | ...   | ...      | ...            |
| P2       | ...   | ...      | ...            |

### Recommendations
1. [actionable improvement]
2. [actionable improvement]
3. ...
```

Save report to `docs/superflow/project-health-report.md` (in English).

## Step 4: Audit & Update llms.txt

`llms.txt` is a standard (llmstxt.org) that helps any LLM understand a project. **Always audit, even if it exists.**

### If llms.txt doesn't exist:
**This MUST be the #1 recommendation in the Health Report.**

> "This project has no llms.txt — must-have documentation for LLMs. I recommend creating it."

Use `prompts/llms-txt-writer.md` for best practices.

### If llms.txt exists:
**Audit it against the codebase** — don't just skip:
- Cross-reference every linked path — do they still exist?
- Are key modules missing from the listing?
- Is the description still accurate?
- Report findings: "llms.txt is up to date" or "llms.txt has N stale entries, propose update?"

## Step 5: Audit & Update CLAUDE.md

**Always audit, even if it exists.** Use `prompts/claude-md-writer.md` for best practices.

### If CLAUDE.md doesn't exist:
Create it automatically (in English) with:
- Project overview (stack, purpose, architecture)
- Key files table (file → purpose)
- Commands (dev, build, test, lint)
- Conventions discovered (naming, language, patterns)
- Architecture notes (data flow, key modules)

Tell user: > "Created CLAUDE.md with project description."

### If CLAUDE.md exists:
**Audit it against the codebase** — don't just add a marker:
- Cross-reference documented files/paths — do they still exist?
- Are key files/commands missing?
- Are there outdated sections (removed files, renamed modules)?
- Preserve user's custom sections — only touch factual parts
- Fix silently if stale, tell user what changed

Tell user: > "Audited CLAUDE.md — [all good / fixed N issues: brief list]."

## Step 6: Verify Enforcement Rules

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version)

This file survives context compaction and is critical for Phase 2 discipline.

## Step 7: Permissions Setup for Autonomous Execution

**Do NOT skip this step.** Check if `~/.claude/settings.json` has the required allow permissions for Superflow.

If missing, propose to the user:
> "Phase 2 runs autonomously — dozens of commands without human approval. To enable this, I need to add permissions for git, GitHub CLI, npm, and secondary providers to your settings. Without this, you'll get prompted on every command. Add permissions?"

If user agrees, add to `~/.claude/settings.json` (merge with existing, don't overwrite):
```json
{
  "permissions": {
    "allow": [
      "Bash(git worktree *)", "Bash(git checkout *)", "Bash(git add *)",
      "Bash(git commit *)", "Bash(git push *)", "Bash(git push --force-with-lease *)",
      "Bash(git rebase *)", "Bash(git pull *)", "Bash(git check-ignore *)",
      "Bash(git log *)", "Bash(git diff *)",
      "Bash(gh pr *)", "Bash(gh pr create *)", "Bash(gh pr checks *)",
      "Bash(gh pr merge *)", "Bash(gh pr view *)",
      "Bash(npm test *)", "Bash(npm run *)", "Bash(npx *)",
      "Bash(codex *)", "Bash(gemini *)", "Bash(aider *)",
      "Bash(gtimeout *)", "Bash(timeout *)"
    ]
  }
}
```

If user declines: continue, but warn that Phase 2 will require manual approval for each command.

## Step 8: Leave Markers

After all steps above, write the **same marker** in every file you touched:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

1. **CLAUDE.md**: append at the very end
2. **llms.txt** (if created/updated): append at the very end
3. **docs/superflow/project-health-report.md**: created as part of Step 3

All three must exist for Phase 0 to be fully skipped on next run.

## Step 9: Completion Checklist

**Before handing off to Phase 1, verify ALL of these:**

- [ ] Health report saved to `docs/superflow/project-health-report.md`
- [ ] llms.txt audited (created if missing, updated if stale)
- [ ] CLAUDE.md audited (created if missing, updated if stale)
- [ ] Enforcement rules verified in `~/.claude/rules/`
- [ ] **Permissions proposed to user** (accepted or declined — but MUST be asked)
- [ ] Markers written in CLAUDE.md, llms.txt, and health report
- [ ] .worktrees/ in .gitignore

If any item is unchecked, go back and complete it before proceeding.

## Step 10: Hand Off to Phase 1

Ask the user:
> "Done! I've explored the project. What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

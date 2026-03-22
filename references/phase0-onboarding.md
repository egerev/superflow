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

## Step 1: Greet & Announce

Tell the user (in their language):
> "This is the first Superflow run on this project. Give me a moment — I'll explore the codebase."

Then proceed to analysis.

## Step 2: Project Analysis (background)

Dispatch **4 parallel agents** using the Agent tool (`run_in_background: true`, `model: opus` for each).

**Critical: use Opus for analysis, not Sonnet.** Wrong documentation is worse than no documentation — a Sonnet agent may hallucinate framework names based on directory structure (e.g., calling pydantic_graph "LangGraph" because the directory is named `graph/`). Analysis agents must verify by reading actual imports and code, not guessing from names.

```
Agent(description: "Architecture analysis", run_in_background: true, model: opus)
  → directory structure, key files, frameworks (verify by checking imports!), dependencies, data model

Agent(description: "Code quality analysis", run_in_background: true, model: opus)
  → hotspots, complexity, test coverage, linting setup

Agent(description: "DevOps analysis", run_in_background: true, model: opus)
  → CI/CD pipeline, .gitignore completeness, env management, deployment setup

Agent(description: "Documentation analysis", run_in_background: true, model: opus)
  → existing docs (README, CLAUDE.md, llms.txt, comments density, API docs)
```

All 4 agents run in parallel. Wait for all to complete, then synthesize into a concise project profile.

**After synthesis, cross-check**: do framework/library names in the profile match actual `import` statements in code? If any look wrong, verify before proceeding.

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

If a section has no issues (e.g., no technical debt), state that explicitly — do not invent problems to fill the template.

Save report to `docs/superflow/project-health-report.md` (in English).

## Step 4: Audit & Update llms.txt

`llms.txt` is a standard (llmstxt.org) that helps any LLM understand a project. **Always audit, even if it exists.**

**Use high-quality agents for this step.** Dispatch with `model: opus` and include `ultrathink` in the agent prompt. Wrong documentation actively misleads all future LLM interactions — it is worse than no documentation.

### If llms.txt doesn't exist:
**This MUST be the #1 recommendation in the Health Report.**

> "This project has no llms.txt — must-have documentation for LLMs. I recommend creating it."

Use `prompts/llms-txt-writer.md` for best practices. Verify every framework/library name by checking actual imports in the code — never guess from directory names.

### If llms.txt exists:
**Audit it against the codebase** — don't just skip:
- Cross-reference every linked path — do they still exist?
- Are key modules missing from the listing?
- Is the description still accurate?
- **Verify framework names**: check actual `import` statements, not just directory names (e.g., `agents/graph/` might be pydantic_graph, not LangGraph)
- Report findings: "llms.txt is up to date" or "llms.txt has N stale entries, propose update?"

## Step 5: Audit & Update CLAUDE.md

**Always audit, even if it exists.** Use `prompts/claude-md-writer.md` for best practices.

**Use high-quality agents for this step.** Same as Step 4 — dispatch with `model: opus` and include `ultrathink` in the agent prompt. CLAUDE.md is the foundation for every future Claude interaction with this project. Errors here compound across all sessions.

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

## Step 6: Verify Enforcement Rules & Gitignore

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version at `~/.claude/skills/superflow/superflow-enforcement.md`)

Check `.worktrees/` is in `.gitignore`:
```bash
git check-ignore -q .worktrees || echo ".worktrees/" >> .gitignore
```

This file survives context compaction and is critical for Phase 2 discipline.

## Step 7: Permissions Setup for Autonomous Execution

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

**Walk through each item below. For each, verify it was completed. If not, go back to the relevant step.**

- [ ] Health report saved to `docs/superflow/project-health-report.md` (Step 3)
- [ ] llms.txt audited — created if missing, updated if stale (Step 4)
- [ ] CLAUDE.md audited — created if missing, updated if stale (Step 5)
- [ ] Enforcement rules verified in `~/.claude/rules/` (Step 6)
- [ ] `.worktrees/` is in `.gitignore` (Step 6)
- [ ] **Permissions proposed to user** — accepted or declined, but MUST be asked (Step 7)
- [ ] Markers `<!-- updated-by-superflow:YYYY-MM-DD -->` written in CLAUDE.md, llms.txt, and health report (Step 8)

If any item is unchecked, go back to the referenced step and complete it before proceeding.

## Step 10: Hand Off to Phase 1

Ask the user:
> "Done! I've explored the project. What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

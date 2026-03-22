# Phase 0: Onboarding (FIRST RUN — INTERACTIVE)

Runs once per project. Skip if Superflow artifacts already exist (see detection below).
This phase is **conversational** — talk to the user, don't just execute silently.

**All documentation output MUST be in English.** If the user communicates in another language, the LLM translates — but all generated files (llms.txt, CLAUDE.md, reports) are English.

## Detection: Is This a First Run?

Check for Superflow markers:
1. `CLAUDE.md` exists AND contains `superflow` mention → **skip Phase 0**
2. `docs/superpowers/` directory exists with specs/plans → **skip Phase 0**
3. `.par-evidence.json` exists → **skip Phase 0**

If none found → first run. Begin onboarding.

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

Save report to `docs/superpowers/project-health-report.md` (in English).

## Step 4: llms.txt — Project Documentation for All LLMs

`llms.txt` is a standard (llmstxt.org) that helps any LLM understand a project — not just Claude. This is especially valuable since Superflow uses multiple AI providers.

**If llms.txt doesn't exist, this MUST be the #1 recommendation in the Health Report.**

> "This project has no llms.txt — this is must-have documentation for LLMs (llmstxt.org). Without it, subagents work blind. I recommend creating it — this will significantly improve implementation quality."

Use `prompts/llms-txt-writer.md` for best practices. Generate following the spec:
```markdown
# Project Name

> One-line project description

## Docs
- [README](./README.md): Project overview and setup
- [Architecture](./docs/architecture.md): System design (if exists)

## Source
- [Key Module](./src/path): Description
- [API Routes](./src/api): Description

## Config
- [Schema](./prisma/schema.prisma): Database schema (if exists)
- [Package](./package.json): Dependencies and scripts
```

### If llms.txt exists:
Cross-reference against actual project structure, propose updates if stale.

## Step 5: CLAUDE.md — Auto-Update (No Approval Needed)

CLAUDE.md is a working tool, not a deliverable. Update it silently:

### If CLAUDE.md doesn't exist:
Create it automatically (in English) with:
- Project overview (stack, purpose, architecture)
- Key files table (file → purpose)
- Commands (dev, build, test, lint)
- Conventions discovered (naming, language, patterns)
- Architecture notes (data flow, key modules)
- Superflow marker (so future runs detect it)

Tell user: > "Created CLAUDE.md with project description."

### If CLAUDE.md exists but is stale:
Fix silently:
- Cross-reference documented files/paths against actual codebase
- Update outdated sections (removed files, renamed modules, new patterns)
- Preserve user's custom sections — only touch factual parts
- Add Superflow marker if missing

Tell user: > "Updated CLAUDE.md — fixed [brief list]."

### If CLAUDE.md is up to date:
No action needed.

## Step 6: Verify Enforcement Rules

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version)

This file survives context compaction and is critical for Phase 2 discipline.

## Step 6.5: Permissions Setup for Autonomous Execution

Check if `~/.claude/settings.json` has the required allow permissions for Superflow. If missing, propose:

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

## Step 7: Leave Markers

After Phase 0 completes:
1. Ensure CLAUDE.md mentions Superflow (so future runs detect it)
2. The `docs/superpowers/` directory serves as the primary artifact marker

## Step 8: Hand Off to Phase 1

Ask the user:
> "Done! I've explored the project. What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

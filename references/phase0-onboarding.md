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

## Step 1: Greet, Announce & Mini-Interview

Tell the user (in their language):
> "This is the first Superflow run on this project. Before I dive in — a couple of quick questions so I can tailor the setup."

Ask the user **3 short questions** (adapt wording to their language):

1. **"Working solo or in a team?"**
   → Affects: CI/hooks recommendations, review process emphasis
2. **"How comfortable are you with [detected stack]?"** (beginner / intermediate / advanced)
   → Affects: report detail level, how much to explain recommendations
3. **"Do you have CI/CD set up?"** (yes / no / not sure)
   → Affects: DevOps analysis depth, hook recommendations

Store answers as `$USER_CONTEXT` — pass to analysis agents in Step 2 so they adjust focus:
- **Beginner**: more explanation, flag basics (missing linter, no tests), recommend learning resources
- **Solo**: skip team-oriented suggestions (branch protection, code owners)
- **No CI**: flag as P1 recommendation, suggest simple GitHub Actions starter

> **Keep it lightweight.** If the user seems impatient or says "just go", skip remaining questions and use sensible defaults (solo, intermediate, no CI). The interview must not feel like a blocker.

Then proceed to analysis.

## Step 2: Project Analysis (background)

Dispatch **4 parallel agents** using the Agent tool (`run_in_background: true`, `model: opus` for each).

**Critical: use Opus for analysis, not Sonnet.** Wrong documentation is worse than no documentation — a Sonnet agent may hallucinate framework names based on directory structure (e.g., calling pydantic_graph "LangGraph" because the directory is named `graph/`). Analysis agents must verify by reading actual imports and code, not guessing from names.

Each agent prompt MUST include `ultrathink`, the **mandatory checks** below, AND the `$USER_CONTEXT` from Step 1 (experience level, solo/team, CI status). Agents must show evidence (file paths, counts, code snippets) for every finding — no unsupported claims. Agents should adjust depth based on user context — for beginners, flag basics that experts wouldn't need called out.

```
Agent(description: "Architecture analysis", run_in_background: true, model: opus)
  ultrathink. Mandatory checks — show evidence for each:
  1. List all top-level directories with file counts and total LOC per directory
  2. Identify frameworks/libraries by reading actual `import` statements (NOT by guessing from directory names)
  3. Map the data model: list all DB models/schemas with field counts
  4. Find architecture violations: does business logic import from adapters/infrastructure? List every violation with file:line
  5. Identify the top 10 largest files by LOC — these are refactoring candidates
  6. Map key entry points (API routes, CLI commands, event handlers)

Agent(description: "Code quality analysis", run_in_background: true, model: opus)
  ultrathink. Mandatory checks — show evidence for each:
  1. List ALL files >500 LOC with exact line counts (use `wc -l` or count lines)
  2. Find all TODO/FIXME/HACK/XXX comments — count and list top 10
  3. Count test files vs source files — calculate coverage ratio
  4. Find source files with NO corresponding test file
  5. Check for code duplication: similar function signatures across files
  6. Check linter config exists and is enforced (pre-commit hooks, CI checks)
  7. Find dead code: unused imports, unreachable functions (if tooling available)

Agent(description: "DevOps analysis", run_in_background: true, model: opus)
  ultrathink. Mandatory checks — show evidence for each:
  1. Docker Compose: count services, check for `latest` tags (non-deterministic), check volume mounts
  2. CI/CD: list all GitHub Actions workflows, check what they actually test/deploy
  3. Deploy script: does it run migrations? Does it have rollback? Health checks?
  4. Security scanning: is dependabot/renovate configured? CodeQL or similar?
  5. Backup strategy: is there one for databases/persistent storage?
  6. Environment management: .env.example exists? Secrets management?
  7. .gitignore completeness: check for common misses (.env, __pycache__, node_modules, .worktrees/)

Agent(description: "Documentation analysis", run_in_background: true, model: opus)
  ultrathink. Mandatory checks — show evidence for each:
  1. List all documentation files with last-modified dates (git log)
  2. Compare README claims against actual project state (commands, setup steps)
  3. If llms.txt exists: count entries vs actual source directories — coverage %
  4. If CLAUDE.md exists: check every documented path exists, check commands work
  5. Check for stale references: grep for file paths in docs, verify each exists
  6. API documentation: is it auto-generated or manual? Is it current?
```

All 4 agents run in parallel. Wait for all to complete, then synthesize into a concise project profile.

**After synthesis, cross-check**: do framework/library names in the profile match actual `import` statements in code? Do file counts match across agents? Resolve discrepancies before proceeding.

## Step 3: Present Project Health Report

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

## Step 4: Audit & Update llms.txt

`llms.txt` is a standard (llmstxt.org) that helps any LLM understand a project. **Always audit, even if it exists.**

**Use high-quality agents for this step.** Dispatch with `model: opus` and include `ultrathink` in the agent prompt. Wrong documentation actively misleads all future LLM interactions — it is worse than no documentation.

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
**Quantitative audit** — produce numbers, not just "looks good":
1. Check every documented file path exists: count valid / total → "X/Y paths valid (Z%)"
2. Run every documented command (dev, test, lint) — do they work?
3. Check `git log --since="last marker date"` — list new files/modules added since last audit
4. Cross-reference architecture description with actual imports — is the described structure current?
5. List what's missing: new key files not documented, new commands not listed
6. Preserve user's custom sections — only touch factual parts
7. Fix silently if stale, tell user what changed

Tell user: > "Audited CLAUDE.md — [X/Y paths valid, N new modules since last audit, fixed K issues: brief list]."

## Step 6: Verify Enforcement Rules & Gitignore

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version at `~/.claude/skills/superflow/superflow-enforcement.md`)

Check `.worktrees/` is in `.gitignore`:
```bash
git check-ignore -q .worktrees || echo ".worktrees/" >> .gitignore
```

This file survives context compaction and is critical for Phase 2 discipline.

## Step 6.5: Check Supervisor Prerequisites

Check if the supervisor system is available:

```bash
python3 --version 2>/dev/null && echo "SUPERVISOR_AVAILABLE" || echo "SUPERVISOR_UNAVAILABLE"
```

- If python3 is available: note "Supervisor: available" in the health report
- If python3 is missing: note "Supervisor: unavailable (python3 not found). Long-running autonomous mode requires python3." No error — single-session mode still works.

## Step 7: Permissions Setup for Autonomous Execution

**Do NOT skip this step.** Check if `~/.claude/settings.json` has the required allow permissions for Superflow.

If missing, propose to the user:
> "Phase 2 runs autonomously — dozens of commands without human approval. To enable this, I need to add broad permissions for git, GitHub CLI, build tools, and secondary providers. Without this, you'll get prompted constantly. Add permissions?"

**Explain the safety model** (especially for beginners):
> "These permissions only apply inside Claude Code sessions. They allow Claude to run git, tests, and build commands without asking each time. Destructive commands like `rm -rf` or `git push --force` are NOT included."

If user agrees, add to `~/.claude/settings.json` (merge with existing, don't overwrite). **Adapt to this project's toolchain** — detect package manager and test runner, then build the permissions list:

### Core Permissions (always include)
```json
{
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(ls *)", "Bash(pwd)", "Bash(cat *)", "Bash(less *)",
      "Bash(wc *)", "Bash(head *)", "Bash(tail *)", "Bash(sort *)", "Bash(uniq *)",
      "Bash(find *)", "Bash(xargs *)", "Bash(jq *)", "Bash(sed *)", "Bash(awk *)",
      "Bash(diff *)", "Bash(comm *)", "Bash(grep *)",
      "Bash(mkdir *)", "Bash(cp *)", "Bash(mv *)", "Bash(touch *)", "Bash(chmod *)",
      "Bash(which *)", "Bash(command *)", "Bash(type *)",
      "Bash(dirname *)", "Bash(basename *)", "Bash(realpath *)",
      "Bash(echo *)", "Bash(printf *)", "Bash(tee *)",
      "Bash(date *)", "Bash(env *)", "Bash(tr *)", "Bash(cut *)",
      "Bash(python3 *)", "Bash(python *)", "Bash(node *)",
      "Bash(codex *)", "Bash(gemini *)", "Bash(aider *)",
      "Bash(gtimeout *)", "Bash(timeout *)"
    ]
  }
}
```

### Stack-Specific Permissions (add based on detection)

**Node.js / npm:**
```json
"Bash(npm *)", "Bash(npx *)"
```

**Node.js / yarn:**
```json
"Bash(yarn *)"
```

**Node.js / pnpm:**
```json
"Bash(pnpm *)", "Bash(pnpx *)"
```

**Node.js / bun:**
```json
"Bash(bun *)", "Bash(bunx *)"
```

**Python:**
```json
"Bash(pip *)", "Bash(pip3 *)", "Bash(uv *)",
"Bash(pytest *)", "Bash(ruff *)", "Bash(black *)", "Bash(mypy *)",
"Bash(poetry *)", "Bash(pdm *)"
```

**Ruby / Rails:**
```json
"Bash(bundle *)", "Bash(rake *)", "Bash(rails *)", "Bash(ruby *)",
"Bash(rubocop *)", "Bash(rspec *)"
```

**Go:**
```json
"Bash(go *)", "Bash(gofmt *)", "Bash(golint *)", "Bash(golangci-lint *)"
```

**Rust:**
```json
"Bash(cargo *)", "Bash(rustfmt *)", "Bash(clippy *)"
```

**Docker (if detected):**
```json
"Bash(docker *)", "Bash(docker-compose *)"
```

### Detection Logic
```bash
# Detect package manager
[ -f "package-lock.json" ] && PM="npm"
[ -f "yarn.lock" ] && PM="yarn"
[ -f "pnpm-lock.yaml" ] && PM="pnpm"
[ -f "bun.lockb" ] && PM="bun"
[ -f "Gemfile.lock" ] && PM="bundler"
[ -f "requirements.txt" ] || [ -f "pyproject.toml" ] && PM="python"
[ -f "go.mod" ] && PM="go"
[ -f "Cargo.toml" ] && PM="rust"
[ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ] && HAS_DOCKER=true
```

Build the final permissions array by combining Core + detected Stack-Specific. **Do not add permissions for stacks not present in the project.**

If user declines: continue, but warn that Phase 2 will require manual approval for each command.

> **Note on restart:** Permissions changes in `settings.json` may require restarting Claude Code to take effect. If so, tell the user: "Permissions added. Please restart Claude Code and run `/superflow` again — Phase 0 will detect the markers and skip straight to Phase 1."

## Step 7.5: Hooks Setup

**Hooks automate quality checks** — especially valuable for beginners who forget to format/lint. Based on the detected stack from Step 2, propose a hooks configuration.

Tell the user (in their language):
> "I can set up auto-formatting and quality hooks so Claude automatically formats code after every edit. This catches style issues instantly. Set up hooks?"

If user agrees, add to `.claude/settings.json` (project-level, shareable via git). **Choose hooks based on detected stack:**

### JavaScript / TypeScript (prettier detected)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path // empty' | grep -E '\\.(js|ts|jsx|tsx|json|css|md)$' | xargs -I{} npx prettier --write '{}' 2>/dev/null || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### JavaScript / TypeScript (eslint detected, no prettier)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path // empty' | grep -E '\\.(js|ts|jsx|tsx)$' | xargs -I{} npx eslint --fix '{}' 2>/dev/null || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Python (ruff or black detected)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path // empty' | grep -E '\\.py$' | xargs -I{} ruff format '{}' 2>/dev/null || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Ruby (rubocop detected)
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path // empty' | grep -E '\\.rb$' | xargs -I{} rubocop -a '{}' 2>/dev/null || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Go
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path // empty' | grep -E '\\.go$' | xargs -I{} gofmt -w '{}' 2>/dev/null || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Desktop Notification (all platforms — useful for autonomous Phase 2)
```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt|idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude needs your attention\" with title \"Superflow\"' 2>/dev/null || notify-send 'Superflow' 'Claude needs your attention' 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

**Detection logic** — check for formatter presence before proposing:
```bash
# JS/TS: check package.json for prettier/eslint
jq -r '.devDependencies // {} | keys[]' package.json 2>/dev/null | grep -E 'prettier|eslint'
# Python: check for ruff.toml, pyproject.toml [tool.ruff], or .flake8
ls ruff.toml pyproject.toml .flake8 2>/dev/null
# Ruby: check for .rubocop.yml
ls .rubocop.yml 2>/dev/null
# Go: always available with Go toolchain
go version 2>/dev/null
```

If no formatter is detected and user is a **beginner**, recommend installing one:
> "No code formatter detected. For [stack], I recommend [prettier/ruff/rubocop]. Want me to add it to the project?"

If user declines hooks: continue without them. Not a blocker.

## Step 7.7: Skills Recommendation

Based on detected stack and user experience level from Step 1, recommend relevant Claude Code skills. **Show only skills that match the project's stack** — don't overwhelm with the full list.

Tell the user (in their language):
> "Based on your stack, these skills could be useful. They're already available — just use the slash command when needed:"

### Recommendation Map

| Stack | Skills | When to Use |
|-------|--------|-------------|
| React / Next.js | `/review-react-best-practices` | After writing React components — catches waterfalls, re-renders, bundle issues |
| React / Next.js | `/webapp-testing` | Test UI with Playwright — take screenshots, fill forms, check behavior |
| TypeScript | `kieran-typescript-reviewer` (via CE review) | Type safety, modern patterns, maintainability review |
| Python | `kieran-python-reviewer` (via CE review) | Pythonic patterns, type hints, best practices |
| Rails / Ruby | `dhh-rails-style` (via CE review) | REST purity, fat models, Hotwire patterns |
| Any web project | `/frontend-design` | Generate polished, non-generic UI components |
| Any project | `/tool-systematic-debugging` | Structured approach to any bug — before guessing fixes |
| Any project | `/webapp-testing` | Browser automation for testing web UIs |

### For Beginners (experience = beginner)
Add extra context:
> "As you're getting started with [stack], I especially recommend:
> - `/review-react-best-practices` — it catches common mistakes that are hard to spot as a beginner
> - `/tool-systematic-debugging` — when something breaks, this gives you a step-by-step method instead of guessing
> - `/webapp-testing` — lets you test your app in a real browser automatically"

### For Advanced Users
Keep it brief — just list the slash commands without explanation. They know what they need.

> **Note:** Skills don't require installation — they're built into Claude Code. Just mention them so the user knows they exist.

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

- [ ] Mini-interview completed — user context captured (Step 1)
- [ ] Health report saved to `docs/superflow/project-health-report.md` (Step 3)
- [ ] llms.txt audited — created if missing, updated if stale (Step 4)
- [ ] CLAUDE.md audited — created if missing, updated if stale (Step 5)
- [ ] Enforcement rules verified in `~/.claude/rules/` (Step 6)
- [ ] `.worktrees/` is in `.gitignore` (Step 6)
- [ ] Python3 availability checked (Step 6.5)
- [ ] **Permissions proposed to user** — accepted or declined, but MUST be asked (Step 7)
- [ ] **Hooks proposed to user** — set up or declined, but MUST be asked (Step 7.5)
- [ ] **Skills recommended** based on detected stack (Step 7.7)
- [ ] Markers `<!-- updated-by-superflow:YYYY-MM-DD -->` written in CLAUDE.md, llms.txt, and health report (Step 8)

If any item is unchecked, go back to the referenced step and complete it before proceeding.

## Step 10: Hand Off to Phase 1

Ask the user:
> "Done! I've explored the project. What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

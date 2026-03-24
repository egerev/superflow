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

## Stage Structure

Phase 0 has 6 stages. Use TaskCreate at each stage start, TaskUpdate as todos complete.

```
Stage 1: "Interview"
  Todos:
  - "Ask team size"
  - "Ask experience level"
  - "Ask CI status"
  - "Detect project type (empty/existing)"

Stage 2: "Analysis"
  Todos:
  - "Dispatch architecture agent"
  - "Dispatch code quality agent"
  - "Dispatch DevOps agent"
  - "Dispatch documentation agent"
  - "Synthesize health report"

Stage 3: "Proposal"
  Todos:
  - "Generate proposal"
  - "Get user approval"

Stage 4: "Documentation"
  Todos:
  - "Audit/create llms.txt"
  - "Audit/create CLAUDE.md"
  - "Create CLAUDE.local.md"

Stage 5: "Environment Setup"
  Todos:
  - "Verify enforcement rules"
  - "Check .gitignore"
  - "Check supervisor prerequisites"
  - "Set up permissions"
  - "Set up hooks"
  - "Verify hooks"
  - "Recommend skills"
  - "Recommend plugins"

Stage 6: "Completion"
  Todos:
  - "Write markers"
  - "Run completion checklist"
  - "Show restart instruction"
```

### State Management

At the start of Phase 0, write `.superflow-state.json`:
```bash
cat > .superflow-state.json << 'STATEEOF'
{"version":1,"phase":0,"phase_label":"Onboarding","stage":"interview","stage_index":0,"last_updated":"..."}
STATEEOF
```

After each stage transition, update via python3:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s['stage']='analysis'; s['stage_index']=1; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```

If python3 is unavailable (checked in Step 6.5), overwrite the full file with updated JSON.

### TaskCreate/TaskUpdate Pattern

```
# At the beginning of Stage 1:
TaskCreate(
  title: "Phase 0: Interview",
  description: "Ask 3 questions, detect project type",
  todos: [
    "Ask team size",
    "Ask experience level",
    "Ask CI status",
    "Detect project type"
  ]
)

# As each todo completes:
TaskUpdate(id: <task_id>, todo_updates: [
  {index: 0, status: "completed"}
])

# When stage completes:
TaskUpdate(id: <task_id>, status: "completed")
```

### Phase Cross-Reference

Phases 1-3 have their own stage structures defined in their respective reference docs:
- Phase 1: `references/phase1-discovery.md` — 5 stages (Research, Brainstorming, Product Approval, Specification, Planning)
- Phase 2: `references/phase2-execution.md` — 5 stages per sprint (Setup, Implementation, Review, PAR, Ship)
- Phase 3: `references/phase3-merge.md` — 3 stages (Pre-merge, Merge, Post-merge)

After Phase 0 completion, `.superflow-state.json` transitions to `phase: 1`.

---

## Step 1: Greet, Announce & Mini-Interview
<!-- Stage 1: Interview, Todos 1-3 -->

Tell the user (in their language):
> "This is the first Superflow run on this project. Before I dive in — a couple of quick questions so I can tailor the setup."

Ask the user using AskUserQuestion (structured UI). If AskUserQuestion is unavailable (non-interactive mode), fall back to text-based questions.

**Question 1:**
```
AskUserQuestion(
  question: "Working solo or in a team?",
  options: [
    {"value": "solo", "label": "Solo — just me"},
    {"value": "small_team", "label": "Small team (2-5)"},
    {"value": "large_team", "label": "Large team (6+)"}
  ]
)
```

**Question 2:**
```
AskUserQuestion(
  question: "How comfortable are you with [detected stack]?",
  options: [
    {"value": "beginner", "label": "Beginner — still learning"},
    {"value": "intermediate", "label": "Intermediate — comfortable"},
    {"value": "advanced", "label": "Advanced — expert level"}
  ]
)
```

**Question 3:**
```
AskUserQuestion(
  question: "Do you have CI/CD set up?",
  options: [
    {"value": "yes", "label": "Yes — CI is configured"},
    {"value": "no", "label": "No CI yet"},
    {"value": "not_sure", "label": "Not sure"}
  ]
)
```

**Fallback (non-interactive mode):** If AskUserQuestion is unavailable, ask the same questions as plain text and parse the response. The existing text-based format works as fallback.

**Edge case — "just go":** If user dismisses any question or says "just go" / "просто начинай", use defaults: `{team: "solo", experience: "intermediate", ci: "no"}`. Proceed immediately.

Store answers as `$USER_CONTEXT`:
```json
{
  "team": "solo" | "small_team" | "large_team",
  "experience": "beginner" | "intermediate" | "advanced",
  "ci": "yes" | "no" | "not_sure",
  "dismissed": false
}
```

Pass `$USER_CONTEXT` to analysis agents in Step 2 so they adjust focus:
- **Beginner**: more explanation, flag basics (missing linter, no tests), recommend learning resources
- **Solo**: skip team-oriented suggestions (branch protection, code owners)
- **No CI**: flag as P1 recommendation, suggest simple GitHub Actions starter

> **Keep it lightweight.** The interview must not feel like a blocker — the "just go" edge case ensures impatient users skip straight to analysis.

Then proceed to analysis.

## Step 1.5: Detect Empty Project vs Existing
<!-- Stage 1: Interview, Todo 4 -->

Insert after the interview, before analysis. Determines which onboarding path to follow.

**Detection logic:**

```bash
# Count tracked files (excluding config-only)
FILE_COUNT=$(git ls-files | grep -v -E '^\.gitignore$|^\.github/|^\.gitlab/|^README|^LICENSE|^CHANGELOG' | wc -l | tr -d ' ')

# Count source files on disk (catches untracked files too)
SOURCE_COUNT=$(find . -maxdepth 3 \( -name '*.js' -o -name '*.ts' -o -name '*.py' -o -name '*.rb' -o -name '*.go' -o -name '*.rs' \) -not -path '*/node_modules/*' -not -path '*/.git/*' | wc -l | tr -d ' ')

# Check git history depth
COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")

# Check for any source code files in git
HAS_SOURCE=$(git ls-files | grep -E '\.(js|ts|jsx|tsx|py|rb|go|rs|java|c|cpp|cs|php|swift|kt|luau|lua)$' | head -1)
```

**Decision matrix:**

| FILE_COUNT | COMMIT_COUNT | SOURCE_COUNT | HAS_SOURCE | Result |
|-----------|-------------|-------------|------------|--------|
| 0 | 0 | 0 | empty | **Greenfield** → route to greenfield path (Sprint 3) |
| ≤5 | ≤2 | 0 | empty | **Near-empty** → treat as greenfield |
| >5 | any | any | non-empty | **Existing project** → proceed to Step 2 |
| ≤5 | any | >0 | any | **Existing (untracked)** → proceed to Step 2 |
| ≤5 | >2 | 0 | empty | **Config-heavy** → ask user: "This repo has config files but no source code. New project or existing?" |

**Edge case:** A repo that once had source code but it was deleted:
```bash
git log --diff-filter=A --name-only --pretty=format: 2>/dev/null | grep -E '\.(js|ts|py|rb|go|rs)$' | head -1
```
If this returns results → treat as existing project (it had source code before).

**Routing:**
- **Greenfield detected:** Tell user: "This looks like a new project! I'll help set up the foundation." → Route to greenfield path (defined in Sprint 3). For now, add placeholder: "Greenfield path: see Sprint 3 implementation."
- **Existing project:** Proceed to Step 2 as normal.

## Step 2: Project Analysis (background)
<!-- Stage 2: Analysis, Todos 1-4 -->

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
<!-- Stage 2: Analysis, Todo 5 -->

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

## Step 3.5: Proposal — Review Before Execution
<!-- Stage 3: Proposal, Todos 1-2 -->

After analysis (Step 2) and health report (Step 3), present a proposal of ALL planned actions before executing them. This is the user's last approval checkpoint.

**Show the proposal using AskUserQuestion** with preview. The proposal covers everything Phase 0 will do next:

```markdown
## Phase 0 Proposal

Based on the analysis, here's what I'm planning to do. Review and approve before I proceed.

### Documentation
- [ ] **llms.txt**: [Create from scratch | Update — N stale entries, M missing modules]
- [ ] **CLAUDE.md**: [Create from scratch | Update — X/Y paths valid, add Z new modules]

### Personal Settings
- [ ] **CLAUDE.local.md**: Create with role ([solo/team]), experience level, communication preferences

### Development Environment
- [ ] **Permissions** (`~/.claude/settings.json`): Add [N] permissions for [detected stack]
  - Preview: `Bash(npm *)`, `Bash(npx *)`, `Bash(git *)`, ...
- [ ] **Hooks** (`.claude/settings.json`): [prettier on Edit/Write | ruff format on Edit/Write | none detected]
  - Preview: `jq -r '.tool_input.file_path' | ...`
- [ ] **Desktop notifications**: [Add Notification hook for permission_prompt/idle_prompt]

### Infrastructure
- [ ] **Workflow guardrails**: Install persistent coding discipline rules (ensures reviews, tests, proper git workflow)
- [ ] **.gitignore**: [Add .worktrees/, CLAUDE.local.md, .superflow-state.json | Already present]
- [ ] **Supervisor**: [python3 available | python3 not found — single-session only]

### Recommendations
- [ ] **/verify skill**: Create `<project>/.claude/skills/verify/SKILL.md` for [detected stack]
- [ ] **Plugins**: [list relevant plugins based on stack]
```

**Approval gate:**

```
AskUserQuestion(
  question: "Does this plan look right?",
  options: [
    {"value": "approve", "label": "Looks good — proceed with everything"},
    {"value": "skip_hooks", "label": "Skip hooks and notifications"},
    {"value": "skip_optional", "label": "Only documentation (skip hooks, skills, plugins)"},
    {"value": "edit", "label": "I want to change something"}
  ]
)
```

**Handling each option:**
- **approve**: proceed with all items
- **skip_hooks**: skip Steps 7.5, Notification hook. Proceed with everything else
- **skip_optional**: only Steps 4-5 (llms.txt + CLAUDE.md). Skip Steps 5.5, 7, 7.5, 7.7, 8.5
- **edit**: ask free text "What would you like to change?", adjust plan, re-present

**Express path:** If `$USER_CONTEXT.dismissed == true` (user said "just go" in Step 1), auto-approve the proposal with all defaults and skip the AskUserQuestion gate. Log: "Auto-approved proposal (express mode)." Proceed directly to Step 4.

**Skip individual confirmations:** Items approved in this proposal do NOT need individual AskUserQuestion calls later. The proposal replaces per-step approval.

## Step 4: Audit & Update llms.txt
<!-- Stage 4: Documentation, Todo 1 -->

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
<!-- Stage 4: Documentation, Todo 2 -->

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

## Step 5.5: Create CLAUDE.local.md
<!-- Stage 4: Documentation, Todo 3 -->

Create a personal preferences file that is gitignored. This stores user-specific settings from the interview.

**Check if it already exists:**
```bash
[ -f CLAUDE.local.md ] && echo "EXISTS" || echo "CREATE"
```

If it doesn't exist, create `CLAUDE.local.md` with content based on `$USER_CONTEXT`:

```markdown
# Personal Preferences

## Role
- [Solo founder | Team member of N] — [experience level] with [detected stack]

## Communication
- [Based on interview: explain tradeoffs / be terse / detailed explanations]

## Workflow
- Using Superflow for feature development
- [If worktrees detected: worktree-aware setup]
```

**Gitignore it:**
```bash
grep -q 'CLAUDE.local.md' .gitignore || echo "CLAUDE.local.md" >> .gitignore
```

**Worktree handling:** `CLAUDE.local.md` is gitignored and will be absent in worktrees. This is intentional — automated sprint sessions should use project-level CLAUDE.md only. If the user uses sibling worktrees (detected via `git worktree list`), suggest creating `~/.claude/<project>-instructions.md` and making CLAUDE.local.md a one-line stub: `@~/.claude/<project>-instructions.md`.

Tell user: > "Created CLAUDE.local.md with your preferences. It's gitignored — personal to you."

## Step 6: Verify Enforcement Rules & Gitignore
<!-- Stage 5: Environment Setup, Todos 1-2 -->

Check if `~/.claude/rules/superflow-enforcement.md` exists:
- If missing: copy from the skill directory (`superflow-enforcement.md` → `~/.claude/rules/`)
- If exists: verify it's up to date (compare with skill's version at `~/.claude/skills/superflow/superflow-enforcement.md`)

Check `.worktrees/` is in `.gitignore`:
```bash
git check-ignore -q .worktrees || echo ".worktrees/" >> .gitignore
git check-ignore -q .superflow-state.json || echo ".superflow-state.json" >> .gitignore
```

This file survives context compaction and is critical for Phase 2 discipline.

## Step 6.5: Check Supervisor Prerequisites
<!-- Stage 5: Environment Setup, Todo 3 -->

Check if the supervisor system is available:

```bash
python3 --version 2>/dev/null && echo "SUPERVISOR_AVAILABLE" || echo "SUPERVISOR_UNAVAILABLE"
```

- If python3 is available: note "Supervisor: available" in the health report
- If python3 is missing: note "Supervisor: unavailable (python3 not found). Long-running autonomous mode requires python3." No error — single-session mode still works.

## Step 7: Permissions Setup for Autonomous Execution
<!-- Stage 5: Environment Setup, Todo 4 -->

**Do NOT skip this step.** Check if `~/.claude/settings.json` has the required allow permissions for Superflow.

**If the user already approved permissions in the proposal (Step 3.5), skip this prompt and proceed to setup.** Only ask if the proposal was skipped or the user chose 'edit'.

If missing, propose to the user:
> "Phase 2 runs autonomously — dozens of commands without human approval. To enable this, I need to add broad permissions for git, GitHub CLI, build tools, and secondary providers. Without this, you'll get prompted constantly. Add permissions?"

**Explain the safety model** (especially for beginners):
> "These permissions only apply inside Claude Code sessions. They allow Claude to run git, tests, and build commands without asking each time. These are broad wildcards (e.g., `Bash(git *)` covers ALL git subcommands including `git push --force`). The tradeoff is autonomy vs safety — Phase 2 needs these to work without interruption. If you prefer tighter control, ask Claude to use explicit subcommands instead."

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
{ [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; } && PM="python"
[ -f "go.mod" ] && PM="go"
[ -f "Cargo.toml" ] && PM="rust"
{ [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]; } && HAS_DOCKER=true
```

Build the final permissions array by combining Core + detected Stack-Specific. **Do not add permissions for stacks not present in the project.**

If user declines: continue, but warn that Phase 2 will require manual approval for each command.

> **Note on restart:** Permissions changes in `settings.json` may require restarting Claude Code to take effect. If so, tell the user: "Permissions added. Please restart Claude Code and run `/superflow` again — Phase 0 will detect the markers and skip straight to Phase 1."

## Step 7.5: Hooks Setup
<!-- Stage 5: Environment Setup, Todos 5-6 -->

**Hooks automate quality checks** — especially valuable for beginners who forget to format/lint. Based on the detected stack from Step 2, propose a hooks configuration.

**If the user already approved hooks in the proposal (Step 3.5), skip this prompt.** Only ask if proposal was skipped or user chose 'skip_hooks'.

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

### Hook Verification Pipeline

After writing hooks to `.claude/settings.json`, verify they actually work. A hook that silently does nothing is worse than no hook.

**Stage 1: Pipe test** — verify the hook command parses input correctly:
```bash
# Example for prettier:
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/index.ts"}}' | jq -r '.tool_input.file_path' | { read -r f; echo "$f" | grep -qE '\.(ts|tsx)$' && npx prettier --write "$f"; }
```
Check: exit code 0, no errors. If fails: wrong jq path, missing tool, bad quoting.

**Stage 2: Settings validation** — verify the JSON is well-formed:
```bash
jq -e '.hooks.PostToolUse[] | select(.matcher == "Edit|Write") | .hooks[] | select(.type == "command") | .command' .claude/settings.json
```
Check: exit 0 + prints the command string. Exit 4/5 = malformed JSON. A broken settings.json silently disables ALL settings from that file.

**Stage 3: Live proof** — verify the formatter is available:
```bash
# For prettier:
echo "test" | npx prettier --check --parser typescript 2>/dev/null && echo "AVAILABLE" || echo "NOT_FOUND"
# For ruff:
ruff --version 2>/dev/null && echo "AVAILABLE" || echo "NOT_FOUND"
# For gofmt:
gofmt -e /dev/null 2>/dev/null && echo "AVAILABLE" || echo "NOT_FOUND"
```

**Stage 4: End-to-end smoke test** — verify the full pipeline works:
```bash
# Create a test file with a known formatting issue
echo "const   x   =   1" > /tmp/superflow-hook-test.ts
# Feed the hook command a real event payload
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/superflow-hook-test.ts"}}' | jq -r '.tool_input.file_path' | { read -r f; echo "$f" | grep -qE '\.(ts|tsx)$' && npx prettier --write "$f"; } 2>/dev/null || true
# Verify the file was formatted
cat /tmp/superflow-hook-test.ts  # Should show formatted output
rm -f /tmp/superflow-hook-test.ts
```

**Verification report:**

| Stage | Result | Details |
|-------|--------|---------|
| Pipe test | PASS/FAIL | Exit code, any errors |
| Settings validation | PASS/FAIL | jq output |
| Live proof | PASS/FAIL/SKIP | Formatter availability |
| End-to-end | PASS/FAIL/SKIP | File actually formatted |

**If any stage fails:**
- **Beginner** ($USER_CONTEXT.experience == "beginner"): "The [formatter] hook couldn't be verified — [formatter] might not be installed. Want me to add it to the project? (`npm install -D prettier`)"
- **Advanced**: "Hook written but [formatter] not available. Hook will no-op until installed. Run `npm install -D prettier` when ready."

**If jq is not available:** Skip Stages 1-2. Log: "jq not found — skipping hook validation. Verify manually by editing a file and checking if formatting is applied."

### Superflow Hooks (PostCompact + SessionStart)

In addition to formatter hooks (project-level, `.claude/settings.json`), set up Superflow-specific hooks at user-level (`~/.claude/settings.json`). These provide crash recovery and context restoration.

**Include these in the proposal (Step 3.5) under "Development Environment > Hooks".** If user approved hooks in the proposal, install both without asking again.

**Hook 1: PostCompact** — when context compacts, inject Superflow state so the LLM knows where it was:

```json
{
  "hooks": {
    "PostCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -f .superflow-state.json ]; then echo '--- SUPERFLOW STATE ---'; cat .superflow-state.json; echo '--- Re-read the phase doc for your current phase. State file: .superflow-state.json ---'; fi",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Hook 2: SessionStart** — when a session starts (including `claude --resume`), restore Superflow context:

jq-based version (extracts phase and stage for a readable message):
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -f .superflow-state.json ]; then PHASE=$(jq -r '.phase' .superflow-state.json 2>/dev/null); STAGE=$(jq -r '.stage // \"unknown\"' .superflow-state.json 2>/dev/null); echo \"--- SUPERFLOW RESUME: Phase $PHASE, stage: $STAGE. Re-read references/ phase doc and continue. State: $(cat .superflow-state.json) ---\"; fi",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

No-jq fallback:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cat .superflow-state.json 2>/dev/null || echo 'No Superflow state found'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Location:** Both hooks go to `~/.claude/settings.json` (user-level). They reference `.superflow-state.json` which is gitignored, so the hooks only make sense for users who have Superflow installed. Formatter hooks remain in `.claude/settings.json` (project-level).

**Installation:** Use `jq` to merge into existing settings, or create the file if it doesn't exist:
```bash
# Check if user-level settings exist
if [ -f ~/.claude/settings.json ]; then
  # Merge hooks into existing settings using jq
  jq '.hooks.PostCompact = (.hooks.PostCompact // []) + [HOOK_OBJECT] | .hooks.SessionStart = (.hooks.SessionStart // []) + [HOOK_OBJECT]' ~/.claude/settings.json > /tmp/claude-settings.tmp && mv /tmp/claude-settings.tmp ~/.claude/settings.json
else
  # Create new settings file with hooks
  cat > ~/.claude/settings.json << 'HOOKEOF'
  { "hooks": { ... } }
  HOOKEOF
fi
```

## Step 7.7: Skills Recommendation
<!-- Stage 5: Environment Setup, Todo 7 -->

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

### Create /verify Skill

In addition to recommending skills, create a project-specific `/verify` skill that runs the full local verification pipeline.

Create `<project>/.claude/skills/verify/SKILL.md` (NOT in Superflow's prompts/ directory — this goes in the user's project):

```yaml
---
name: verify
description: Run full local verification (lint + typecheck + tests). Use before committing or creating PRs.
---
```

The SKILL.md body (below the frontmatter) should contain the actual verification instructions:

```
Run the full verification pipeline for this project:

```bash
[detected verify command from table above]
```

If any step fails:
1. Show the error output
2. Fix the issue
3. Re-run the full pipeline

Report results as:
| Check | Result | Details |
|-------|--------|---------|
| Lint | PASS/FAIL | ... |
| Type check | PASS/FAIL/SKIP | ... |
| Tests | PASS (N passed) / FAIL | ... |
```

**Detection logic** — build the verification command based on detected stack:

| Stack | Verify Command |
|-------|---------------|
| Node.js (npm) | `npm run lint && npx tsc --noEmit && npm test` |
| Node.js (yarn) | `yarn lint && yarn tsc --noEmit && yarn test` |
| Node.js (pnpm) | `pnpm lint && pnpm tsc --noEmit && pnpm test` |
| Python (ruff + pytest) | `ruff check src/ tests/ && ruff format --check src/ tests/ && pytest` |
| Python (ruff + pyright) | `ruff check src/ tests/ && pyright src/ && pytest` |
| Go | `go vet ./... && go test ./...` |
| Ruby (rubocop + rspec) | `rubocop && rspec` |
| Luau (stylua + selene) | `stylua --check src && selene src` |

**Output format** — the skill should report results as:

| Check | Result | Details |
|-------|--------|---------|
| Lint | PASS/FAIL | ... |
| Type check | PASS/FAIL/SKIP | ... |
| Tests | PASS (N passed) / FAIL (N failed) | ... |

If any check fails, fix the issue and re-run. Report all results before marking done.

Tell user: > "Created /verify skill — run `/verify` anytime to check your code before committing."

## Step 8: Leave Markers
<!-- Stage 6: Completion, Todo 1 -->

After all steps above, write the **same marker** in every file you touched:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

1. **CLAUDE.md**: append at the very end
2. **llms.txt** (if created/updated): append at the very end
3. **docs/superflow/project-health-report.md**: created as part of Step 3

All three must exist for Phase 0 to be fully skipped on next run.

## Step 8.5: Plugin Recommendations
<!-- Stage 5: Environment Setup, Todo 8 -->

Based on detected stack and available MCP tools, recommend relevant Claude Code plugins.

**Always recommend:**
- `/plugin install skill-creator@claude-plugins-official` — create and optimize skills with evals

**Stack-specific:**

| Detected | Plugin | Why |
|----------|--------|-----|
| React / Next.js / Vue / Svelte | `/plugin install frontend-design@claude-plugins-official` | Design principles, component patterns, polished UI |
| Any web project | `/plugin install playwright@claude-plugins-official` | Browser automation, screenshot verification, visual bug detection |

**Presentation:**
- **Beginner**: explain what each plugin does, show example use case
- **Advanced**: one-liner per plugin, no explanation needed

> Only recommend plugins that are relevant to the detected stack. Don't overwhelm with the full list.

## Step 9: Completion Checklist
<!-- Stage 6: Completion, Todo 2 -->

**Walk through each item below. For each, verify it was completed. If not, go back to the relevant step.**

- [ ] Mini-interview completed — user context captured via AskUserQuestion (Step 1)
- [ ] Empty vs existing project detected (Step 1.5)
- [ ] Health report saved to `docs/superflow/project-health-report.md` (Step 3)
- [ ] Proposal presented and approved by user (Step 3.5)
- [ ] llms.txt audited — created if missing, updated if stale (Step 4)
- [ ] CLAUDE.md audited — created if missing, updated if stale (Step 5)
- [ ] CLAUDE.local.md created and gitignored (Step 5.5)
- [ ] Enforcement rules verified in `~/.claude/rules/` (Step 6)
- [ ] `.worktrees/`, `CLAUDE.local.md`, `.superflow-state.json` in `.gitignore` (Step 6)
- [ ] Python3 availability checked (Step 6.5)
- [ ] **Permissions proposed to user** — accepted or declined, but MUST be asked (Step 7)
- [ ] **Hooks set up and verified** — 4-stage pipeline passed (pipe-test + jq + live proof + e2e) (Step 7.5)
- [ ] **/verify skill created** in `<project>/.claude/skills/verify/SKILL.md` (Step 7.7)
- [ ] **Skills recommended** based on detected stack (Step 7.7)
- [ ] **Plugin recommendations shown** (Step 8.5)
- [ ] Markers `<!-- updated-by-superflow:YYYY-MM-DD -->` written in CLAUDE.md, llms.txt, and health report (Step 8)

If any item is unchecked, go back to the referenced step and complete it before proceeding.

## Step 10: Complete & Restart
<!-- Stage 6: Completion, Todo 3 -->

**If permissions or hooks were configured (Steps 7-7.5):**

> "Phase 0 complete! To activate the new permissions and hooks, restart Claude Code:
> 1. Exit this session (type `exit` or press Ctrl+C)
> 2. Run `claude` (or `claude --resume` to continue where you left off)
>
> Permissions and hooks are read at startup — they won't take effect until restart."

**If nothing was configured** (user declined everything in the proposal):

> "Phase 0 complete! What would you like to work on?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

# Phase 0 Improvements + Parallelism + Stability — Technical Design Spec

**References:** [Product Brief](2026-03-23-phase0-improvements-brief.md)

**Date:** 2026-03-23

---

## Sprint 1 — Phase 0: Interactive Onboarding (Existing Project)

### Overview

Transform Phase 0 from a text-based questionnaire into a structured interactive experience with AskUserQuestion buttons, a proposal step before execution, hook verification, skill creation, and plugin recommendations. All changes are in Markdown prompt files — no Python.

### File-Level Changes

| File | Action | Description |
|------|--------|-------------|
| `references/phase0-onboarding.md` | Modify | Rewrite Steps 1, add 1.5, 2.5, 5.5, update 7.5, 7.7, add 9.5, update 10 |
| `<project>/.claude/skills/verify/SKILL.md` | Create (in user's project) | `/verify` skill for stack-specific verification |
| `SKILL.md` | Modify | Add `/verify` to the skill's Architecture section |

### Detailed Changes

#### Step 1: Replace Text Questions with AskUserQuestion

**Current behavior:** Free-text questions ("Working solo or in a team?"), user types an answer, LLM interprets it.

**New behavior:** Use the `AskUserQuestion` tool with predefined options. Each question has a fallback for non-interactive environments.

```
AskUserQuestion(
  question: "Working solo or in a team?",
  options: [
    {"value": "solo", "label": "Solo — just me"},
    {"value": "small_team", "label": "Small team (2-5)"},
    {"value": "large_team", "label": "Large team (6+)"}
  ]
)

AskUserQuestion(
  question: "How comfortable are you with [detected stack]?",
  options: [
    {"value": "beginner", "label": "Beginner — still learning"},
    {"value": "intermediate", "label": "Intermediate — comfortable"},
    {"value": "advanced", "label": "Advanced — expert level"}
  ]
)

AskUserQuestion(
  question: "Do you have CI/CD set up?",
  options: [
    {"value": "yes", "label": "Yes — CI is configured"},
    {"value": "no", "label": "No CI yet"},
    {"value": "not_sure", "label": "Not sure"}
  ]
)
```

**Fallback logic:** If `AskUserQuestion` is unavailable (non-interactive mode, older Claude Code version), fall back to text-based questions as currently implemented. Detection:

```
# AskUserQuestion is available if the tool exists in the current session.
# If unavailable, ask the same questions as plain text and parse the response.
```

**Edge case — "just go":** If user dismisses any question or says "just go" / "просто начинай", use defaults: `{team: "solo", experience: "intermediate", ci: "no"}`. Proceed immediately without remaining questions.

Store all answers as `$USER_CONTEXT` object:

```json
{
  "team": "solo" | "small_team" | "large_team",
  "experience": "beginner" | "intermediate" | "advanced",
  "ci": "yes" | "no" | "not_sure",
  "dismissed": false
}
```

#### New Step 1.5: Detect Empty Project vs Existing

Insert after Step 1, before Step 2. This step determines which onboarding path to follow.

**Detection logic:**

```bash
# Count tracked files (excluding config-only files)
FILE_COUNT=$(git ls-files | grep -v -E '^\.gitignore$|^\.github/|^\.gitlab/|^README|^LICENSE|^CHANGELOG' | wc -l | tr -d ' ')

# Count source files on disk (catches untracked files too)
SOURCE_COUNT=$(find . -maxdepth 3 \( -name '*.js' -o -name '*.ts' -o -name '*.py' -o -name '*.rb' -o -name '*.go' -o -name '*.rs' \) -not -path '*/node_modules/*' -not -path '*/.git/*' | wc -l | tr -d ' ')

# Check git history depth
COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")

# Check for any source code files in git
HAS_SOURCE=$(git ls-files | grep -E '\.(js|ts|jsx|tsx|py|rb|go|rs|java|c|cpp|cs|php|swift|kt)$' | head -1)
```

**Decision matrix:**

| FILE_COUNT | SOURCE_COUNT | COMMIT_COUNT | HAS_SOURCE | Result |
|-----------|-------------|-------------|------------|--------|
| 0 | 0 | 0 | no | **Greenfield** — route to Sprint 3 path |
| 0-2 | 0 | 0-1 | no | **Greenfield** — route to Sprint 3 path |
| any | >0 | any | yes | **Existing project** — continue Phase 0 normally |
| any | >0 | any | no | **Existing project** (untracked source files on disk) — continue normally |
| >5 | 0 | any | no | **Existing project** (config-heavy, e.g., IaC) — continue normally |

**Edge case:** Empty project but `.git` has history with source code that was deleted → count commits with source files: `git log --diff-filter=A --name-only --pretty=format: | grep -E '\.(js|ts|py|rb|go)$' | head -1`. If found, treat as existing (recovering/restructuring project).

If greenfield detected, tell the user: "This looks like a new project! I'll help you set it up from scratch." Then route to the greenfield path (Sprint 3). If existing, proceed to Step 2 as before.

#### New Step 2.5: Proposal Step — After Analysis, Before Execution

Insert after Step 3 (Health Report), before Step 4 (llms.txt). After analysis is complete and the health report is shown, present a proposal of what Phase 0 will do, and wait for approval.

**Proposal format:**

```markdown
## Phase 0 Proposal

Based on the analysis, here's what I'm planning to do. Review and approve before I proceed.

### Documentation
- [ ] **llms.txt**: [Create from scratch | Update — 3 stale entries, 2 missing modules]
- [ ] **CLAUDE.md**: [Create from scratch | Update — 5/12 paths valid, add 3 new modules]

### Development Environment
- [ ] **Permissions** (`~/.claude/settings.json`): Add [N] permissions for [detected stack]
  - Preview: `Bash(npm *)`, `Bash(npx *)`, `Bash(pytest *)`, ...
- [ ] **Hooks** (`.claude/settings.json`): [prettier on Edit/Write | ruff format on Edit/Write | none detected]
  - Preview: `jq -r '.tool_input.file_path // empty' | grep -E '\.(ts|tsx)$' | xargs -I{} npx prettier --write '{}' ...`
- [ ] **Desktop notifications**: [Add Notification hook for permission_prompt/idle_prompt]

### Infrastructure
- [ ] **Enforcement rules**: [Install to ~/.claude/rules/ | Already up to date]
- [ ] **.gitignore**: [Add .worktrees/ | Already present]
- [ ] **Supervisor**: [python3 available | python3 not found — single-session only]

### Recommendations
- [ ] **Skills**: [/review-react-best-practices, /webapp-testing — matched to your Next.js stack]
- [ ] **Plugins**: [context7 — library docs lookup | telegram — progress notifications]

### CLAUDE.local.md
- [ ] Create `CLAUDE.local.md` with personal preferences stub (gitignored)
```

**Approval gate:**

```
AskUserQuestion(
  question: "Approve this plan? I'll execute everything checked above.",
  options: [
    {"value": "approve", "label": "Approve — go ahead"},
    {"value": "skip_hooks", "label": "Approve without hooks"},
    {"value": "skip_all_optional", "label": "Just docs — skip hooks, permissions, plugins"},
    {"value": "edit", "label": "Let me adjust..."}
  ]
)
```

If user selects "edit", ask what to change in free text. Rebuild the proposal, re-present. If user selects one of the approve options, proceed with the appropriate subset. Skip individual `AskUserQuestion` calls for hooks/permissions/skills that the user already approved or declined in the proposal.

#### New Step 5.5: CLAUDE.local.md Creation

Insert after Step 5 (CLAUDE.md audit), before Step 6 (enforcement rules).

**Purpose:** `CLAUDE.local.md` stores personal preferences that are gitignored. It also serves as the import mechanism for sibling worktrees — worktrees share the same `.claude/` directory but `CLAUDE.local.md` in the project root gives them per-worktree context.

**Detection:**

```bash
# Check if CLAUDE.local.md exists
[ -f "CLAUDE.local.md" ] && echo "EXISTS" || echo "MISSING"

# Check if it's gitignored
grep -q 'CLAUDE.local.md' .gitignore && echo "IGNORED" || echo "NOT_IGNORED"
```

**If missing, create:**

```markdown
# CLAUDE.local.md — Personal Preferences (gitignored)

## User Context
- Team: [solo|small_team|large_team]
- Experience: [beginner|intermediate|advanced]
- Language preference: [detected from conversation]

## Import Project Instructions
<!-- Stub: when working in a worktree, this file imports the main CLAUDE.md -->
<!-- The main CLAUDE.md is at the repo root. Worktrees at .worktrees/sprint-N/ -->
<!-- share the same git repo, so CLAUDE.md is accessible via ../../../CLAUDE.md -->

## Personal Notes
<!-- Add your own notes, shortcuts, preferences here -->
```

**Add to `.gitignore` if not already present:**

```bash
grep -q 'CLAUDE.local.md' .gitignore || echo "CLAUDE.local.md" >> .gitignore
```

**Stub-import pattern for worktrees:** When the supervisor creates a worktree at `.worktrees/sprint-N/`, that worktree has its own working directory but shares the git repo. Claude Code reads `CLAUDE.md` from the working directory. The worktree gets the repo-root `CLAUDE.md` automatically (worktrees share the repo content), but `CLAUDE.local.md` is gitignored and therefore absent in worktrees. This is intentional — worktree sessions are automated and don't need personal preferences.

#### Step 7.5 Update: Hook Verification Pipeline

**Current behavior:** Hooks are templates. Written to `.claude/settings.json` and assumed to work. No verification.

**New behavior:** After writing hooks, run a 3-stage verification pipeline:

**Stage 1 — Pipe test (syntax check):**

```bash
# Test that the hook command parses correctly
echo '{"tool_input":{"file_path":"test.ts"}}' | jq -r '.tool_input.file_path // empty'
# Expected: "test.ts"
```

If `jq` is not installed, report: "jq not found — hook command syntax depends on jq. Install with: `brew install jq` (macOS) or `apt install jq` (Linux)." Do not block — hooks will silently fail without jq, but this is better than blocking onboarding.

**Stage 2 — jq validate (settings file integrity):**

```bash
# Validate the settings file is valid JSON after writing hooks
jq empty .claude/settings.json 2>&1
# Expected: no output (valid JSON)
# If error: report "settings.json has invalid JSON after hook setup", attempt to fix
```

**Stage 3 — Live proof (formatter available):**

```bash
# For prettier:
echo "const   x=1" > /tmp/superflow-hook-test.ts
npx prettier --write /tmp/superflow-hook-test.ts 2>/dev/null
cat /tmp/superflow-hook-test.ts  # Should be formatted
rm /tmp/superflow-hook-test.ts

# For ruff:
echo "x=1" > /tmp/superflow-hook-test.py
ruff format /tmp/superflow-hook-test.py 2>/dev/null
cat /tmp/superflow-hook-test.py
rm /tmp/superflow-hook-test.py

# For gofmt:
echo "package main\nfunc main()  {}" > /tmp/superflow-hook-test.go
gofmt -w /tmp/superflow-hook-test.go 2>/dev/null
cat /tmp/superflow-hook-test.go
rm /tmp/superflow-hook-test.go
```

If the formatter is not installed:
- **Beginner:** "Prettier is not installed. Want me to add it? `npm install --save-dev prettier`"
- **Advanced:** "Prettier not found. Hook will silently no-op until installed."

**Stage 4 — End-to-end smoke test (full pipeline):**

After writing the hook JSON, feed the exact configured command a real event payload from stdin and check the side effect (file was actually formatted, test actually ran). This proves the hook works as a complete pipeline, not just individual stages.

```bash
# For prettier hook — create a real file, pipe a real event, check formatting happened:
echo "const   x=1" > /tmp/superflow-e2e-test.ts
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/superflow-e2e-test.ts"}}' | \
  jq -r '.tool_input.file_path // empty' | xargs -I{} npx prettier --write '{}'
# Verify the file was formatted:
grep -q "const x = 1" /tmp/superflow-e2e-test.ts && echo "E2E PASS" || echo "E2E FAIL"
rm /tmp/superflow-e2e-test.ts

# For ruff hook:
echo "x=1" > /tmp/superflow-e2e-test.py
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/superflow-e2e-test.py"}}' | \
  jq -r '.tool_input.file_path // empty' | xargs -I{} ruff format '{}'
rm /tmp/superflow-e2e-test.py
```

This is what Phase 0's hook verification does: pipe-test then live proof as an end-to-end chain.

**Verification report (shown to user):**

```
Hook Verification:
  [PASS] Pipe test — jq parses hook command correctly
  [PASS] Settings validation — .claude/settings.json is valid JSON
  [PASS] Live proof — prettier formatted test file successfully
  [PASS] End-to-end — full hook pipeline processed a real event correctly
```

or

```
Hook Verification:
  [PASS] Pipe test — jq parses hook command correctly
  [PASS] Settings validation — .claude/settings.json is valid JSON
  [FAIL] Live proof — prettier not found. Hook will no-op. Install: npm i -D prettier
  [SKIP] End-to-end — skipped (formatter not available)
```

#### Step 7.7 Update: Create `/verify` Skill

**Current behavior:** Recommends skills as text. User must remember them.

**New behavior:** Create a `/verify` skill in the user's project. Claude Code registers skills from `.claude/skills/` directories — this is how slash commands work. The skill file goes to `<project>/.claude/skills/verify/SKILL.md` (NOT in Superflow's prompts/ directory).

**Create `<project>/.claude/skills/verify/SKILL.md`:**

```markdown
---
name: verify
description: "Run verification checks on the current project. Detects stack and runs appropriate linters, type checkers, and test suites."
---

# /verify — Project Verification

Run all verification checks appropriate for the detected stack.

## Detection
Detect the stack by checking for marker files (same logic as Phase 0 Step 7):
- `package.json` → Node.js (check for TypeScript: `tsconfig.json`)
- `pyproject.toml` / `requirements.txt` → Python
- `Gemfile` → Ruby
- `go.mod` → Go
- `Cargo.toml` → Rust

## Checks by Stack

### Node.js / TypeScript
1. **Type check**: `npx tsc --noEmit` (if tsconfig.json exists)
2. **Lint**: `npx eslint .` (if .eslintrc* exists)
3. **Format check**: `npx prettier --check .` (if prettier in devDependencies)
4. **Tests**: `npm test` or `npx jest` or `npx vitest run`
5. **Build**: `npm run build` (if build script exists)

### Python
1. **Type check**: `mypy .` or `pyright .` (if configured)
2. **Lint**: `ruff check .` (if ruff.toml/pyproject.toml) or `flake8 .`
3. **Format check**: `ruff format --check .` or `black --check .`
4. **Tests**: `pytest` or `python -m pytest`
5. **Import sort**: `isort --check .` (if configured)

### Go
1. **Vet**: `go vet ./...`
2. **Lint**: `golangci-lint run` (if installed)
3. **Format check**: `gofmt -l .` (non-empty output = unformatted)
4. **Tests**: `go test ./...`
5. **Build**: `go build ./...`

### Ruby / Rails
1. **Lint**: `rubocop` (if .rubocop.yml exists)
2. **Tests**: `bundle exec rspec` or `bundle exec rails test`
3. **Security**: `bundle audit` (if installed)

## Output Format
```
## Verification Results

| Check | Status | Details |
|-------|--------|---------|
| Type check | PASS/FAIL/SKIP | ... |
| Lint | PASS/FAIL/SKIP | ... |
| Format | PASS/FAIL/SKIP | ... |
| Tests | PASS (42 passed) / FAIL (3 failed) | ... |
| Build | PASS/FAIL/SKIP | ... |

Overall: X/Y checks passed
```

If a check tool is not installed, report SKIP with install instructions.
```

**Update `SKILL.md`:** Add `/verify` to the Architecture tree.

#### New Step 9.5: Plugin Recommendations Based on Stack

Insert after Step 9 (completion checklist), before Step 10 (hand off).

Based on detected stack and available MCP plugins, recommend relevant plugins.

**Detection logic — check which MCP plugins are available:**

```
# Check for available MCP tools in the session
# These are detected by the presence of tool names starting with 'mcp__plugin_'
```

**Recommendation map:**

| Stack / Need | Plugin | Why |
|-------------|--------|-----|
| Any with dependencies | `context7` (`mcp__plugin_compound-engineering_context7__query-docs`) | Look up library documentation without leaving Claude Code |
| Any, team communication | `telegram` (`mcp__plugin_telegram_telegram__reply`) | Get progress notifications during autonomous Phase 2 |
| Any with API | `web-fetch` | Test API endpoints, fetch external resources |

**Presentation:**

For beginners:
```
I noticed you have the context7 plugin connected. This lets me look up
documentation for any library while working — really useful when writing
code with unfamiliar APIs. I'll use it automatically when relevant.

You also have the Telegram plugin. During Phase 2 (autonomous execution),
I'll send you progress updates there so you don't need to watch the terminal.
```

For advanced users:
```
Available plugins: context7 (lib docs), telegram (notifications).
Will use automatically.
```

Only recommend plugins that are actually detected in the session (tool names starting with `mcp__plugin_`). Do not recommend plugins that aren't connected.

#### Step 10 Update: Restart Instruction

**Current behavior:** "Done! I've explored the project. What would you like to work on?"

**New behavior:** Explain that a restart is needed for permissions and hooks to take effect, provide the exact command, and explain why.

```
Phase 0 complete!

**Important: Restart Claude Code to activate permissions and hooks.**
Permissions and hooks are read from settings.json at startup — they won't
take effect in this session.

To restart:
1. Exit this session (Ctrl+C or type /exit)
2. Run: `claude` (or `claude --resume` to continue from where we left off)

When you return, Phase 0 will detect the markers and skip straight to Phase 1.
I'll ask: "What would you like to work on?"
```

If no permissions or hooks were set up (user declined everything), skip the restart instruction and proceed directly to Phase 1:

```
Phase 0 complete! What would you like to work on?
```

### Testing Strategy

Since Sprint 1 is Markdown-only, testing is manual verification:

1. **AskUserQuestion rendering:** Verify options render as clickable buttons in Claude Code desktop app
2. **Fallback path:** Test in non-interactive mode (pipe mode) — questions should fall back to text
3. **"Just go" path:** Verify defaults are applied when user dismisses
4. **Empty project detection:** Test with: (a) truly empty repo, (b) repo with only .gitignore, (c) repo with source files, (d) repo with deleted source history
5. **Proposal approval:** Test each approval option (approve, skip_hooks, skip_all_optional, edit)
6. **Hook verification pipeline:** Test with formatter installed and without
7. **`/verify` skill:** Run on a real project, confirm output format
8. **Plugin detection:** Test with and without MCP plugins connected

### Out of Scope for Sprint 1

- Greenfield path (Sprint 3)
- State persistence / `.superflow-state.json` (Sprint 2)
- TaskCreate progress visualization (Sprint 2)
- Parallel dispatch in Phase 2 (Sprint 4)
- Changes to Phase 1, 2, or 3

---

## Sprint 2 — All Phases: Stages + Todos + State + Hooks

### Overview

Add structured progress tracking to all four phases via TaskCreate todos, persist Superflow state to `.superflow-state.json` for crash recovery, and implement Claude Code hooks for automatic context restoration. Also merge Phase 1 Steps 6+7 into a single approval gate and add AskUserQuestion to Phase 1 brainstorming.

### File-Level Changes

| File | Action | Description |
|------|--------|-------------|
| `references/phase0-onboarding.md` | Modify | Wrap steps in stage/todo structure |
| `references/phase1-discovery.md` | Modify | Add stages, merge Steps 6+7, add AskUserQuestion to brainstorming |
| `references/phase2-execution.md` | Modify | Add stages per sprint, state write instructions |
| `references/phase3-merge.md` | Modify | Add stages for merge sequence |
| `SKILL.md` | Modify | Add state management to startup checklist, add hook documentation |
| `templates/superflow-state-schema.json` | Create | JSON Schema for `.superflow-state.json` |
| `.claude/hooks.json` | Document | Hook configuration patterns (documented in phase0, user installs) |

### Detailed Changes

#### Stage/Todo Structure

Each phase is broken into **stages**. Each stage has **todos** created via `TaskCreate`. This provides:
1. Visual progress for the user (checklist updates in real-time)
2. Structure for the LLM (prevents step-skipping after compaction)
3. State persistence (current stage/todo written to `.superflow-state.json`)

**Phase 0 stages:**

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

**Phase 1 stages:**

```
Stage 1: "Research"
  Todos:
  - "Read project context (CLAUDE.md, llms.txt, docs)"
  - "Dispatch best practices research"
  - "Dispatch product expert research"
  - "Present research findings"

Stage 2: "Brainstorming"
  Todos:
  - "Conduct multi-expert brainstorming (3-5 questions)"
  - "Present approaches with trade-offs"

Stage 3: "Product Approval"   ← MERGED Steps 6+7
  Todos:
  - "Present Product Summary + Brief for approval"
  - "Get user approval"

Stage 4: "Specification"
  Todos:
  - "Write technical spec"
  - "Dual-model spec review"
  - "Fix review findings"

Stage 5: "Planning"
  Todos:
  - "Write implementation plan"
  - "Dual-model plan review"
  - "Fix review findings"
  - "Get user final approval"
```

**Phase 2 stages (per sprint):**

```
Stage 1: "Setup"
  Todos:
  - "Re-read phase docs"
  - "Send Telegram update"
  - "Create worktree"
  - "Run baseline tests"

Stage 2: "Implementation"
  Todos:
  - "Dispatch implementer(s)"
  - "Collect results"

Stage 3: "Review"
  Todos:
  - "Internal review (spec + code quality)"
  - "Fix review findings"
  - "Post-review test verification"

Stage 4: "PAR"
  Todos:
  - "Dispatch Claude reviewer"
  - "Dispatch secondary provider reviewer"
  - "Fix NEEDS_FIXES (if any)"
  - "Write .par-evidence.json"

Stage 5: "Ship"
  Todos:
  - "Push and create PR"
  - "Verify PR created"
  - "Cleanup worktree"
  - "Send Telegram update"
```

**Phase 3 stages:**

```
Stage 1: "Pre-merge"
  Todos:
  - "CI check on all PRs"
  - "Review comments check"
  - "Update CLAUDE.md"
  - "Update llms.txt"

Stage 2: "Merge"
  Todos (one per PR):
  - "Merge PR #N (Sprint K: [title])"

Stage 3: "Post-merge"
  Todos:
  - "Sync local main"
  - "Prune worktrees"
  - "Clean artifacts"
  - "Generate post-merge report"
  - "Send Telegram report"
```

**Implementation pattern** — at the start of each stage, create todos:

```
# At the beginning of Phase 0, Stage 1:
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

#### `.superflow-state.json` Schema

**Location:** Project root (`.superflow-state.json`). Gitignored (added during Phase 0).

**Source of truth:** The queue file (`sprint-queue.json`) and checkpoint file are the single source of truth. `.superflow-state.json` is a **read-only projection** — it is generated (projected) from queue/checkpoint data, never written independently. The supervisor's `_write_state()` reads the queue file and checkpoint, then generates the state JSON. Hooks read the state JSON but never write to it. This ensures no dual-write consistency issues.

```json
{
  "$schema": "templates/superflow-state-schema.json",
  "version": 1,
  "phase": 2,
  "phase_label": "Autonomous Execution",
  "sprint": 3,
  "stage": "implementation",
  "stage_index": 2,
  "tasks_done": [1, 2, 3],
  "tasks_total": 6,
  "last_updated": "2026-03-23T14:30:00Z",
  "context": {
    "user_context": {
      "team": "solo",
      "experience": "intermediate",
      "ci": "no"
    },
    "detected_stack": "nextjs",
    "secondary_provider": "codex",
    "supervisor_available": true,
    "plan_file": "docs/superflow/plans/2026-03-23-phase0-improvements.md",
    "spec_file": "docs/superflow/specs/2026-03-23-phase0-improvements-design.md",
    "queue_file": "docs/superflow/sprint-queue.json"
  },
  "history": [
    {"phase": 0, "completed_at": "2026-03-23T10:00:00Z"},
    {"phase": 1, "completed_at": "2026-03-23T12:00:00Z"},
    {"phase": 2, "sprint": 1, "completed_at": "2026-03-23T13:00:00Z", "pr": "#42"},
    {"phase": 2, "sprint": 2, "completed_at": "2026-03-23T13:45:00Z", "pr": "#43"}
  ]
}
```

**JSON Schema (`templates/superflow-state-schema.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Superflow State",
  "type": "object",
  "required": ["version", "phase", "last_updated"],
  "properties": {
    "version": {"type": "integer", "const": 1},
    "phase": {"type": "integer", "minimum": 0, "maximum": 3},
    "phase_label": {"type": "string"},
    "sprint": {"type": ["integer", "null"]},
    "stage": {"type": "string"},
    "stage_index": {"type": "integer", "minimum": 0},
    "tasks_done": {"type": "array", "items": {"type": "integer"}},
    "tasks_total": {"type": "integer"},
    "last_updated": {"type": "string", "format": "date-time"},
    "context": {
      "type": "object",
      "properties": {
        "user_context": {"type": "object"},
        "detected_stack": {"type": "string"},
        "secondary_provider": {"type": ["string", "null"]},
        "supervisor_available": {"type": "boolean"},
        "plan_file": {"type": ["string", "null"]},
        "spec_file": {"type": ["string", "null"]},
        "queue_file": {"type": ["string", "null"]}
      }
    },
    "history": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["phase", "completed_at"],
        "properties": {
          "phase": {"type": "integer"},
          "sprint": {"type": "integer"},
          "completed_at": {"type": "string"},
          "pr": {"type": "string"}
        }
      }
    }
  }
}
```

**Read/write logic:**

During **Phase 2** (supervisor-managed), the supervisor's `_write_state()` generates this file as a projection from queue/checkpoint data. The Claude session never writes it directly.

During **Phases 0, 1, 3** (no supervisor), the Claude session writes this file directly since there is no queue/checkpoint to project from. This is acceptable because these phases are interactive (single session, no parallel execution, no crash recovery concern). The file serves as context for hooks only.

```markdown
## State Management (Phases 0, 1, 3 — no supervisor)

At the start of this phase, write `.superflow-state.json`:
```bash
cat > .superflow-state.json << 'STATEEOF'
{"version":1,"phase":N,"phase_label":"...","stage":"...","stage_index":0,"last_updated":"..."}
STATEEOF
```

After each stage transition, update via python3 (available since Phase 0 Step 6.5 checks it):
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s['stage']='implementation'; s['stage_index']=2; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```

If python3 is unavailable, overwrite the full file with updated JSON.
```

During **Phase 2** (supervisor-managed), the state file is generated by the supervisor — the Claude session does NOT write it directly. See Sprint 4 for `_write_state()` details.

**Add to `.gitignore` during Phase 0:**

```bash
grep -q '.superflow-state.json' .gitignore || echo ".superflow-state.json" >> .gitignore
```

#### Superflow Hooks

Three hook types that Claude Code natively supports, documented in the phase docs for user installation during Phase 0.

**Hook 1: PostCompact (state injection)**

When context compacts, Claude Code fires the `PostCompact` event. A hook reads `.superflow-state.json` and injects context.

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

**How it works:** After compaction, the hook output is injected into the conversation context. The LLM sees the current phase, sprint, stage, and a reminder to re-read the phase doc. This replaces the lost context.

**Hook 2: SessionStart (context restore on resume)**

When a session starts (including `claude --resume`), restore Superflow context if state exists.

jq-based version (reads phase and stage from state file):

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

**No-jq fallback:** If jq is not available, use a simpler version:

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

**Hook 3: Notification (desktop alert) — already exists in Phase 0 Step 7.5**

The existing Notification hook from Phase 0 Step 7.5 handles desktop alerts. No changes needed — just ensure it's included in the proposal (Sprint 1, Step 2.5).

**Hook installation:** All three hooks are proposed during Phase 0 Step 2.5 (proposal step).

**Location by hook type:**
- **PostCompact and SessionStart hooks** → `~/.claude/settings.json` (user-level). Superflow hooks are user-specific and should not be committed to git. They reference `.superflow-state.json` which is gitignored, so the hooks only make sense for users who have Superflow installed.
- **Formatter hooks** (prettier, ruff, gofmt) → `.claude/settings.json` (project-level). These are project-specific and should be shared via git so all team members get consistent formatting.
- **Notification hooks** → `~/.claude/settings.json` (user-level). Desktop notification preferences are personal.

#### Phase 1: Merge Steps 6+7 into Single Approval Gate

**Current behavior:** Step 6 presents Product Summary, asks for approval. Step 7 writes the Product Brief after approval. Two separate steps, two separate user interactions.

**New behavior:** Merge into a single "Product Approval" stage. The LLM presents both the Product Summary and the Brief together, in one message, with a single approval gate.

**Updated Step 6 (replaces old Steps 6+7):**

```markdown
## Step 6: Product Approval (MERGED GATE)

Present Product Summary + Product Brief together as a single document for approval:

### Product Summary
- What we're building (feature list)
- Problems solved
- NOT in scope
- Key decisions + rationale

### Product Brief
- Problem statement (1-2 sentences)
- Jobs to be Done
- User stories (3-5)
- Success criteria
- Edge cases

Save to `docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md`.

**APPROVAL GATE:**
AskUserQuestion(
  question: "Does this capture what we're building? Approve to proceed to technical spec.",
  options: [
    {"value": "approve", "label": "Approve — write the spec"},
    {"value": "changes", "label": "Needs changes"},
    {"value": "restart", "label": "Start over — wrong direction"}
  ]
)

- "approve" → proceed to Step 7 (now the Spec step, renumbered from old Step 8)
- "changes" → ask what to change, update, re-present
- "restart" → go back to Step 4 (brainstorming)
```

**Renumbering:** Old Steps 8-12 become Steps 7-11. Update all internal references in phase1-discovery.md.

#### Phase 1: AskUserQuestion in Brainstorming

**Current behavior:** Step 4 says "ask 3-5 questions, one at a time." Questions are free-text.

**New behavior:** Use AskUserQuestion when the question has clear options. Free-text questions remain as text.

**Pattern — when to use AskUserQuestion vs free text:**

- Questions with enumerable options → AskUserQuestion
- Open-ended exploration → free text

**Example for approach selection (Step 5):**

```
AskUserQuestion(
  question: "I see three approaches. Which direction appeals to you?",
  options: [
    {"value": "a", "label": "Approach A: [name] — [1-line tradeoff]"},
    {"value": "b", "label": "Approach B: [name] — [1-line tradeoff]"},
    {"value": "c", "label": "Approach C: [name] — [1-line tradeoff]"},
    {"value": "details", "label": "Tell me more about each"}
  ]
)
```

**Example for priority question during brainstorming:**

```
AskUserQuestion(
  question: "What matters most for this feature?",
  options: [
    {"value": "speed", "label": "Ship fast — MVP first"},
    {"value": "quality", "label": "Get it right — thorough implementation"},
    {"value": "flexibility", "label": "Keep options open — extensible design"}
  ]
)
```

Do not force AskUserQuestion on every brainstorming question. Use it when the LLM can predict the option space. For exploratory questions ("What problem are you trying to solve?"), keep free text.

### Testing Strategy

1. **TaskCreate rendering:** Verify todos appear as a checklist in Claude Code UI, updates are visible in real-time
2. **State persistence:** Write `.superflow-state.json`, simulate compaction (restart session), verify state is read back
3. **PostCompact hook:** Manually trigger compaction in a long session, verify hook output appears in context
4. **SessionStart hook:** Start a new session with `claude --resume`, verify Superflow context is restored
5. **Merged approval gate (Phase 1):** Run Phase 1 through brainstorming, verify Product Summary + Brief appear together
6. **AskUserQuestion in Phase 1:** Verify options render correctly, free text fallback works
7. **State schema validation:** Validate sample `.superflow-state.json` against the JSON Schema

### Out of Scope for Sprint 2

- Greenfield path (Sprint 3)
- Parallel dispatch changes in Phase 2 (Sprint 4)
- Supervisor Python code changes (Sprint 4)
- Any changes to the Python supervisor's checkpoint system (Sprint 2 state is Markdown-level, not Python-level)

---

## Sprint 3 — Phase 0: Greenfield Path

### Overview

When Phase 0 detects an empty project (via Step 1.5 from Sprint 1), route to a greenfield onboarding path that helps the user pick a stack, scaffolds initial structure, sets up CI, generates CLAUDE.md, and connects to Phase 1.

### File-Level Changes

| File | Action | Description |
|------|--------|-------------|
| `references/phase0-onboarding.md` | Modify | Add greenfield path (Steps G1-G6) after detection step |
| `templates/greenfield/` | Create (dir) | Stack-specific scaffolding templates |
| `templates/greenfield/nextjs.md` | Create | Next.js project structure template |
| `templates/greenfield/python.md` | Create | Python project structure template |
| `templates/greenfield/generic.md` | Create | Generic fallback project structure template |
| `templates/ci/github-actions-node.yml` | Create | GitHub Actions template for Node.js |
| `templates/ci/github-actions-python.yml` | Create | GitHub Actions template for Python |
| `SKILL.md` | Modify | Add greenfield templates to Architecture tree |

### Detailed Changes

#### Detection Logic (Connects to Sprint 1 Step 1.5)

Sprint 1 adds detection in Step 1.5. If greenfield is detected, the flow branches here. The existing project path continues with Steps 2-10 as before.

```
Step 1.5 result == "greenfield"
  → Skip Steps 2-3 (no codebase to analyze)
  → Enter Greenfield Path (Steps G1-G6)
  → After G6, rejoin at Step 6 (enforcement rules) for shared setup
```

#### Step G1: Project Vision Interview

```
AskUserQuestion(
  question: "What are you building?",
  options: [
    {"value": "webapp", "label": "Web application"},
    {"value": "api", "label": "API / Backend service"},
    {"value": "cli", "label": "CLI tool"},
    {"value": "library", "label": "Library / Package"},
    {"value": "other", "label": "Something else..."}
  ]
)
```

If "other" → free text follow-up: "Describe what you're building in a sentence or two."

Then:

```
AskUserQuestion(
  question: "One more — give me a one-liner for the project. What does it do?",
  options: []  // Free text input
)
```

Store as `$PROJECT_VISION`:

```json
{
  "type": "webapp" | "api" | "cli" | "library" | "other",
  "description": "User's one-liner description",
  "name": "project-name"  // Derived from directory name or asked
}
```

#### Step G2: Stack Selection

Present stack options based on project type. Use AskUserQuestion with relevant options.

**For webapp:**

```
AskUserQuestion(
  question: "Which stack do you want to use?",
  options: [
    {"value": "nextjs", "label": "Next.js (React + SSR + API routes)"},
    {"value": "react_vite", "label": "React + Vite (SPA)"},
    {"value": "python", "label": "Python (FastAPI / Flask / Django)"},
    {"value": "other", "label": "Other — I'll describe the stack"}
  ]
)
```

**For API:**

```
AskUserQuestion(
  question: "Which stack for the API?",
  options: [
    {"value": "express", "label": "Express.js / Node.js"},
    {"value": "fastapi", "label": "FastAPI / Python"},
    {"value": "other", "label": "Other — I'll describe the stack"}
  ]
)
```

**For CLI:**

```
AskUserQuestion(
  question: "Which language for the CLI?",
  options: [
    {"value": "python_click", "label": "Python (Click/Typer)"},
    {"value": "go_cobra", "label": "Go (Cobra)"},
    {"value": "node_commander", "label": "Node.js (Commander)"},
    {"value": "rust_clap", "label": "Rust (Clap)"},
    {"value": "other", "label": "Other — I'll specify"}
  ]
)
```

If "other" → free text: "What stack/language do you want to use?"

Store as `$STACK_CHOICE`.

**Follow-up questions (conditional):**

```
AskUserQuestion(
  question: "TypeScript or JavaScript?",
  options: [
    {"value": "typescript", "label": "TypeScript (recommended)"},
    {"value": "javascript", "label": "JavaScript"}
  ]
)
// Only asked if stack is Node.js-based

AskUserQuestion(
  question: "Do you want a database?",
  options: [
    {"value": "postgres", "label": "PostgreSQL"},
    {"value": "sqlite", "label": "SQLite (simple, no server)"},
    {"value": "mongo", "label": "MongoDB"},
    {"value": "none", "label": "No database yet"},
    {"value": "other", "label": "Other"}
  ]
)
// Only asked for webapp/api types
```

#### Step G3: Scaffolding

Based on `$STACK_CHOICE`, generate the initial project structure. Do NOT use `create-next-app` or similar generators — they produce too much boilerplate and make non-standard choices. Instead, create a minimal, clean structure.

**Each stack template (`templates/greenfield/<stack>.md`) defines:**

1. Directory structure
2. Essential files with content
3. Package/dependency declarations
4. Configuration files

**Next.js example (`templates/greenfield/nextjs.md`):**

```markdown
# Next.js Greenfield Template

## Directory Structure
```
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   └── .gitkeep
│   └── lib/
│       └── .gitkeep
├── public/
│   └── .gitkeep
├── tests/
│   └── example.test.ts
├── .gitignore
├── .env.example
├── package.json
├── tsconfig.json
├── next.config.ts
├── README.md
└── CLAUDE.md
```

## package.json
```json
{
  "name": "{project_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "next lint",
    "format": "prettier --write ."
  },
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "react-dom": "^19"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^19",
    "typescript": "^5",
    "vitest": "^3",
    "prettier": "^3",
    "eslint": "^9",
    "eslint-config-next": "^15"
  }
}
```

## .gitignore
```
node_modules/
.next/
out/
.env
.env.local
*.tsbuildinfo
.worktrees/
.superflow-state.json
CLAUDE.local.md
```

## tsconfig.json
Standard Next.js tsconfig with strict mode enabled.

## README.md template
```markdown
# {project_name}

{project_description}

## Getting Started

npm install
npm run dev

Open http://localhost:3000.

## Development

- `npm run dev` — development server
- `npm run build` — production build
- `npm test` — run tests
- `npm run lint` — lint code
- `npm run format` — format code
```
```

**Python example (`templates/greenfield/python.md`):**

```markdown
# Python Greenfield Template

## Directory Structure
```
├── src/
│   └── {project_name}/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── .gitignore
├── .env.example
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## pyproject.toml
```toml
[project]
name = "{project_name}"
version = "0.1.0"
description = "{project_description}"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "ruff", "mypy"]

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## .gitignore
```
__pycache__/
*.pyc
.env
.venv/
dist/
*.egg-info/
.worktrees/
.superflow-state.json
CLAUDE.local.md
```
```

**Generic template (`templates/greenfield/generic.md`):**

For stacks without a specific template, create a minimal structure:

```markdown
# Generic Greenfield Template

## Directory Structure
```
├── src/
│   └── .gitkeep
├── tests/
│   └── .gitkeep
├── docs/
│   └── .gitkeep
├── .gitignore
├── README.md
└── CLAUDE.md
```
```

**Scaffolding execution:** The LLM reads the appropriate template, replaces `{project_name}` and `{project_description}` from `$PROJECT_VISION`, and creates all files using the Write tool. For Rails, it runs the generator command instead.

After scaffolding:

```bash
# Install dependencies
npm install      # Node.js
pip install -e ".[dev]"  # Python
go mod tidy      # Go
bundle install   # Rails
```

#### Step G4: CI Workflow Templates

Present CI setup option:

```
AskUserQuestion(
  question: "Set up GitHub Actions CI?",
  options: [
    {"value": "yes", "label": "Yes — basic CI (lint + test + build)"},
    {"value": "no", "label": "No CI for now"},
    {"value": "advanced", "label": "Yes — with preview deployments"}
  ]
)
```

**GitHub Actions template for Node.js (`templates/ci/github-actions-node.yml`):**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

**GitHub Actions template for Python (`templates/ci/github-actions-python.yml`):**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest
```

If user selected CI, write the template to `.github/workflows/ci.yml`. For stacks without a CI template (Go, Rails, etc.), generate a basic CI workflow based on the stack's standard tooling.

> **Note:** Additional stack templates (Rails, Go, Rust) and their CI workflows can be added in future sprints.

#### Step G5: CLAUDE.md Generation for New Projects

Generate CLAUDE.md tailored to the scaffolded project. Since there's no existing code to analyze, generate from the template and stack knowledge.

```markdown
# {Project Name}

## Project Overview
{project_description}
Stack: {stack}. Started with Superflow greenfield scaffolding.

## Key Files
| File | Purpose |
|------|---------|
| {stack-specific file list} | ... |

## Commands
- `{dev_command}` — start development server
- `{test_command}` — run tests
- `{lint_command}` — lint code
- `{build_command}` — production build

## Conventions
- {stack-specific conventions}

<!-- updated-by-superflow:YYYY-MM-DD -->
```

Also generate a minimal `llms.txt`:

```
# {Project Name}

> {project_description}

## Source
- src/: Application source code

## Configuration
- {config files based on stack}

## Documentation
- README.md: Project readme
- CLAUDE.md: Claude Code instructions
```

#### Step G6: Connect to Shared Setup + Phase 1

After greenfield scaffolding is complete:

1. **Scaffolding order (strict):**
   1. Write `.gitignore` FIRST (ensures node_modules/, .env, etc. are excluded before any git operations)
   2. Then scaffold all other files (package.json, tsconfig.json, source files, etc.)
   3. Then `git add` by name — list specific files, NOT `git add -A` (prevents accidentally staging unintended files)
   4. Then commit:
   ```bash
   git add .gitignore package.json tsconfig.json src/ tests/ README.md CLAUDE.md ...
   git commit -m "Initial project setup with Superflow

   Stack: {stack}
   CI: {yes/no}
   Scaffolded by Superflow Phase 0 greenfield path"
   ```

2. **Rejoin shared Phase 0 steps:** Continue from Step 6 (enforcement rules) through Step 10. The detection (Step 1.5) already set the path, so Steps 2-5 (analysis, health report, llms.txt, CLAUDE.md) are skipped since we just created those files.

3. **Transition to Phase 1:** After Phase 0 completes, transition to Phase 1 with the greenfield context:
   ```
   "Project scaffolded! Now let's plan what to build. What's the first
   feature you want to implement?"
   ```
   Phase 1 proceeds normally — the user describes what they want, brainstorming happens, spec is written against the freshly scaffolded project.

### Testing Strategy

1. **Empty repo detection:** Create `git init` repos with various states:
   - Truly empty (no commits)
   - `.gitignore` only
   - README only
   - Source files present (should NOT be greenfield)
   - Deleted history (had source, deleted — should NOT be greenfield)
2. **Stack selection flow:** Walk through each project type + stack combination
3. **Scaffolding output:** For each stack template, verify:
   - All files are created
   - `{project_name}` placeholders are replaced
   - Dependencies install successfully (`npm install`, `pip install`, etc.)
   - Dev server starts
   - Tests run (even if empty)
4. **CI template:** Push to a test repo, verify GitHub Actions runs and passes
5. **CLAUDE.md quality:** Verify generated CLAUDE.md has correct paths, commands work
6. **Full flow:** Empty repo → greenfield detection → stack selection → scaffold → shared setup → Phase 1 transition

### Out of Scope for Sprint 3

- Additional stack templates beyond Next.js, Python, and generic (Rails, Go, Rust can be added in future sprints)
- Advanced scaffolding (monorepo, microservices, Docker setup)
- Database schema generation
- Preview deployment setup (Vercel, Netlify, Fly.io)
- Stack-specific starter templates beyond basic structure
- Updating existing project templates (Sprint 1 handles existing projects)
- Supervisor changes (Sprint 4)

---

## Sprint 4 — Phase 2: Parallelism + Supervisor

### Overview

Enable the Claude session (orchestrator) to detect independent tasks within a sprint and dispatch multiple implementers in parallel via wave dispatch. The Claude session owns intra-sprint parallelism (it has the context to analyze task dependencies). The Python supervisor only manages inter-sprint parallelism (already works). Add supervisor state file writes and step tracking. Design notes for supervisor managing other phases.

### File-Level Changes

| File | Action | Description |
|------|--------|-------------|
| `references/phase2-execution.md` | Modify | Add parallel dispatch instructions, step verification |
| `lib/supervisor.py` | Modify | Add state write, step tracking |
| `lib/parallel.py` | Modify | Add state file writes during parallel sprint execution |
| `lib/queue.py` | Modify | Add task-level tracking fields to sprint schema |
| `templates/supervisor-sprint-prompt.md` | Modify | Add parallel dispatch instructions, state update instructions |
| `tests/test_supervisor.py` | Modify | Add tests for parallel task detection, state management |
| `tests/test_parallel.py` | Modify | Add tests for state file skipping during parallel execution |
| `tests/test_queue.py` | Modify | Add tests for task-level fields |
| `SKILL.md` | Modify | Document parallelism in Architecture section |

### Detailed Changes

#### How Orchestrator Detects Independent Tasks

The orchestrator (Claude session inside a sprint) receives the sprint plan which lists tasks. To detect which tasks can run in parallel, it applies these rules:

**Independence criteria (all must be true for two tasks to be parallel):**

1. **Different files:** Tasks modify different files (no shared file paths)
2. **No data dependency:** Task B doesn't need Task A's output
3. **No shared state:** Tasks don't modify the same database table, config, or global state
4. **No order constraint:** The plan doesn't specify an order between them

**Detection logic (added to `references/phase2-execution.md`):**

```markdown
## Parallel Dispatch within a Sprint

Before dispatching implementers, analyze the task list:

1. For each task, list the files it will modify (from the plan's file-level changes)
2. Build a dependency graph:
   - If Task B's files overlap with Task A's files → B depends on A
   - If Task B references Task A's output → B depends on A
   - Otherwise → independent
3. Group into waves:
   - Wave 1: all tasks with no dependencies
   - Wave 2: tasks depending only on Wave 1 tasks
   - Wave 3: tasks depending on Wave 2 tasks
   - etc.
4. Dispatch each wave in parallel:

### Wave Dispatch

For each wave with >1 task:
- Dispatch each task as a separate Agent with `run_in_background: true`
- All agents in a wave run simultaneously
- Wait for ALL agents in the wave to complete before starting the next wave

For waves with 1 task: dispatch normally (no background).

### Example

Sprint has 6 tasks:
- Task 1: Create `lib/auth.py` — no deps
- Task 2: Create `lib/storage.py` — no deps
- Task 3: Create `lib/cache.py` — no deps
- Task 4: Update `lib/api.py` to use auth — depends on Task 1
- Task 5: Update `lib/api.py` to use storage — depends on Task 2, shares file with Task 4
- Task 6: Integration test — depends on Tasks 4, 5

Wave 1: [Task 1, Task 2, Task 3] → parallel (3 agents)
Wave 2: [Task 4] → sequential (Task 5 shares api.py with Task 4)
Wave 3: [Task 5] → sequential (after Task 4 finishes with api.py)
Wave 4: [Task 6] → sequential (depends on 4+5)

Total: 4 waves instead of 6 sequential tasks. Tasks 1-3 save ~2x time.
```

#### Parallel Dispatch Logic

**Changes to `references/phase2-execution.md` Step 5:**

Update the implementer dispatch step to include wave analysis:

```markdown
5. **Dispatch implementers** via Agent tool:
   a. Analyze task list — identify independent tasks (see Parallel Dispatch above)
   b. Group into waves
   c. For Wave 1 (independent tasks):
      - Dispatch each task as Agent(run_in_background: true, model: sonnet)
      - Each agent gets: task description, prompts/implementer.md, llms.txt context
      - Wait for all Wave 1 agents to complete
      - Verify all tasks reported DONE (not BLOCKED)
      - If any BLOCKED: handle before next wave
   d. For subsequent waves: same pattern, but only start after previous wave completes
   e. After all waves: verify no file conflicts (git status shows clean merges)
```

**Fallback:** If wave analysis is complex or the sprint has ≤3 tasks, skip wave analysis and dispatch sequentially. Parallelism adds overhead (merging, conflict resolution) that isn't worth it for small sprints.

#### Supervisor Changes in `supervisor.py`

**1. Task-level tracking in sprint execution:**

Add task tracking to the sprint schema in `queue.py`. Each sprint can optionally have a `tasks` field:

```python
# In queue.py — extend sprint schema
# Current sprint fields:
# id, title, status, plan_file, branch, depends_on, pr, retries, max_retries, error_log

# New optional fields:
# tasks: list of task objects for intra-sprint tracking
# Example:
# "tasks": [
#   {"id": 1, "title": "Create auth module", "status": "pending", "files": ["lib/auth.py"]},
#   {"id": 2, "title": "Create storage module", "status": "pending", "files": ["lib/storage.py"]},
# ]
```

This is informational — the supervisor doesn't execute tasks directly (Claude does), but it can read task status from the sprint output for reporting.

**2. State file writing in `supervisor.py`:**

Add `.superflow-state.json` writes to the supervisor's run loop so the state file stays current even when the supervisor is orchestrating.

```python
# New function in supervisor.py
def _write_state(repo_root: str, phase: int, sprint: int | None,
                 stage: str, queue: "SprintQueue") -> None:
    """Project .superflow-state.json from queue/checkpoint data.

    This is a read-only projection — the queue file is the source of truth.
    The state JSON is generated for hooks and crash recovery context.
    """
    state = {
        "version": 1,
        "phase": phase,
        "phase_label": {0: "Onboarding", 1: "Discovery", 2: "Autonomous Execution", 3: "Merge"}[phase],
        "sprint": sprint,
        "stage": stage,
        "stage_index": {"setup": 0, "implementation": 1, "review": 2, "par": 3, "ship": 4}.get(stage, 0),
        "tasks_done": [s["id"] for s in queue.sprints if s["status"] == "completed"],
        "tasks_total": len(queue.sprints),
        "last_updated": _now_iso(),
    }
    state_path = os.path.join(repo_root, ".superflow-state.json")
    tmp_path = state_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.rename(tmp_path, state_path)
```

**Call sites in `supervisor.py`:**

- `execute_sprint()`: Write state at sprint start (`stage: "setup"`)
- `_attempt_sprint()`: Write state before claude invocation (`stage: "implementation"`)
- After PR creation: Write state (`stage: "ship"`)
- After sprint completion: Update `tasks_done`

**Race condition guard:** `_write_state()` is only called when `max_parallel == 1` (sequential execution). When parallel sprints run (`max_parallel > 1`), state is NOT written per-sprint because multiple sprints would race on the same file. The queue file already tracks parallel progress correctly. State is written once after all parallel sprints in a batch complete.

```python
# In execute_sprint(), after marking in_progress:
_write_state(repo_root, phase=2, sprint=sid, stage="setup", queue=queue)

# In _attempt_sprint(), before subprocess.run:
_write_state(repo_root, phase=2, sprint=sid, stage="implementation", queue=queue)

# In _attempt_sprint(), after successful PR verification:
_write_state(repo_root, phase=2, sprint=sid, stage="ship", queue=queue)
```

**3. Step verification in sprint prompt:**

Update `templates/supervisor-sprint-prompt.md` to include step verification instructions:

```markdown
## Step Verification

After completing each phase of your sprint execution, verify the step was not skipped:

1. After worktree setup: verify you're on branch `{branch}` with `git branch --show-current`
2. After baseline tests: paste test output (enforcement rule 4)
3. After implementation: verify all tasks report DONE, list changed files
4. After internal review: paste reviewer verdicts
5. After PAR: verify .par-evidence.json exists with both ACCEPTED
6. After PR creation: verify PR URL is accessible with `gh pr view`

If any step was skipped (e.g., after compaction), go back and complete it.
Check `.superflow-state.json` if you're unsure of current progress.
```

**4. Sprint prompt update for parallel awareness:**

The Claude session inside the sprint owns intra-sprint parallelism (wave dispatch). The supervisor does NOT do intra-sprint parallelism — it only manages inter-sprint parallelism (already works via `parallel.py`). The supervisor still launches one Claude session per sprint. The sprint prompt tells Claude about parallelism:

Add to `templates/supervisor-sprint-prompt.md`:

```markdown
## Parallel Task Dispatch

If the sprint plan has multiple tasks, analyze them for independence:
- Different files + no data dependency = can run in parallel
- Group into waves, dispatch each wave with Agent(run_in_background: true)
- Wait for each wave to complete before starting the next
- If ≤3 tasks, skip wave analysis and dispatch sequentially
```

#### Supervisor Managing Main Session (Step Verification)

The supervisor currently manages sprint-level execution. Add awareness of whether the Claude session inside a sprint follows the correct steps.

**Approach: Output parsing.**

The sprint prompt (Step 4 in `supervisor-sprint-prompt.md`) already requires a JSON summary on the last line. Extend this to include step completion markers:

```json
{
  "status": "completed",
  "pr_url": "https://github.com/...",
  "tests": {"passed": 42, "failed": 0},
  "par": {"claude": "ACCEPTED", "secondary": "ACCEPTED"},
  "steps_completed": [
    "baseline_tests",
    "implementation",
    "internal_review",
    "test_verification",
    "par",
    "pr_created"
  ]
}
```

In `_attempt_sprint`, after parsing the JSON summary, verify required steps:

```python
REQUIRED_STEPS = {"baseline_tests", "implementation", "par", "pr_created"}

def _verify_steps(summary: dict) -> list[str]:
    """Check if all required steps were completed. Returns list of missing steps."""
    completed = set(summary.get("steps_completed", []))
    return list(REQUIRED_STEPS - completed)
```

If steps are missing, log a warning. The sprint still counts as successful if the PR exists (backward compatible), but the warning helps identify sessions that skip steps.

#### Supervisor Managing Other Phases (Design Notes)

This section is design exploration for future sprints — not implemented in Sprint 4.

**Phase 0 via supervisor:**

Phase 0 is interactive — it requires user input (interview, proposal approval). The supervisor could manage Phase 0 by:
1. Running Claude with the Phase 0 prompt
2. Detecting when Claude needs user input (the session pauses)
3. Forwarding the question to the user via Telegram or stdout
4. Passing the user's response back

**Challenge:** The supervisor currently uses `claude -p` (pipe mode) which is non-interactive. Phase 0 needs `claude` (interactive mode). This would require a fundamentally different execution model — the supervisor would need to manage a PTY or use Claude Code's API.

**Recommendation:** Phase 0 stays interactive (user runs `/superflow` in their Claude Code session). The supervisor is for Phase 2 only.

**Phase 1 via supervisor:**

Similar challenge — Phase 1 is collaborative (brainstorming, approval gates). Not suitable for supervisor pipe mode.

**Recommendation:** Phase 1 stays interactive. However, the background research (Step 2) could be dispatched by the supervisor as a pre-computation step: "Run research agents before the user arrives." This is a future optimization.

**Phase 3 via supervisor:**

Phase 3 (merge) is semi-automated — it needs user approval to start, but the merge sequence itself is autonomous. The supervisor could:
1. Wait for user to say "merge" (via Telegram or CLI)
2. Execute the merge sequence: CI check → merge → rebase conflicts → re-check
3. Report back via Telegram

**Feasibility:** High. Phase 3's merge loop is deterministic and doesn't need interactive input once started. Would require:
- New supervisor command: `superflow-supervisor merge --queue <path>`
- Merge logic extracted from Phase 3 markdown into Python
- CI polling (already have `gh pr checks` parsing)
- Conflict resolution (rebase, push)

**Recommendation:** Design the interface now, implement in a future sprint after Sprint 4 proves the supervisor+state integration works.

**Shared state bridge:** All phase supervisors would project `.superflow-state.json` from queue/checkpoint data. The queue + checkpoint files are the single source of truth. The state JSON is a read-only view that hooks and crash recovery use to restore context.

### Testing Strategy

**Unit tests (`tests/test_supervisor.py`):**

1. `test_write_state_creates_file` — verify `.superflow-state.json` is created with correct schema
2. `test_write_state_atomic` — verify tmp+rename pattern (no partial writes)
3. `test_write_state_updates_on_sprint_transition` — verify state changes as sprints progress
4. `test_verify_steps_all_present` — verify no warnings when all steps completed
5. `test_verify_steps_missing` — verify missing steps are reported
6. `test_verify_steps_backward_compatible` — verify old format (no `steps_completed`) doesn't crash
**Unit tests (`tests/test_parallel.py`):**

7. `test_parallel_skips_state_writes` — verify `_write_state` is NOT called when `max_parallel > 1`
8. `test_parallel_batch_writes_state_after_completion` — verify state is written once after all parallel sprints complete

**Unit tests (`tests/test_queue.py`):**

9. `test_sprint_with_tasks_field` — verify tasks field is preserved through save/load
10. `test_sprint_without_tasks_field` — verify backward compatibility (no tasks field)

**Integration tests:**

11. `test_full_sprint_with_state` — end-to-end sprint with state file verification
12. `test_resume_from_state` — crash during sprint, resume reads state, continues correctly
13. `test_parallel_sprints_with_state` — multiple sprints in parallel, state reflects current

**Manual tests:**

14. Run a sprint with the updated prompt, verify parallel dispatch happens when tasks are independent
15. Verify `.superflow-state.json` is updated throughout execution
16. Simulate compaction during a sprint, verify PostCompact hook restores context

### Out of Scope for Sprint 4

- Supervisor managing Phase 0 or Phase 1 (design notes only)
- Supervisor managing Phase 3 merge (design notes only)
- Automatic conflict resolution between parallel tasks (handled by Claude session)
- Supervisor API mode (currently CLI only)
- Changes to replanner for parallel awareness
- Intra-sprint parallelism in the supervisor — the Claude session owns wave dispatch, not the supervisor

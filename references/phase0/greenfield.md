# Phase 0 — Greenfield Path

Loaded by Stage 1 when an empty or near-empty project is detected.
After completing G6, rejoin at Stage 4 (skip Branch A — docs already created in G5).
Run Branch B (permissions/hooks) and Branch C (scaffolding) only.

This file is re-read after context compaction. Re-read it if you lose context.

---

## When This Path Is Active

Stage 1 detects greenfield when:
- Fewer than 5 source files exist (excluding dotfiles and config)
- No `src/`, `lib/`, or `app/` directory with actual code
- No package.json, pyproject.toml, go.mod, or Cargo.toml present

If detected, skip Stage 2 (analysis), Stage 3 (proposal), and Stage 4 Branch A (docs).
Enter at Step G1 below. After G6, rejoin at Stage 4 Branch B.

---

## Step G1: Project Vision Interview
<!-- Greenfield Stage 1: Vision -->

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

Then ask for a one-liner description (free text):
> "One more — give me a one-liner for the project. What does it do?"

Store as `$PROJECT_VISION`:
```json
{
  "type": "webapp" | "api" | "cli" | "library" | "other",
  "description": "User's one-liner description",
  "name": "project-name"
}
```

The `name` is derived from the current directory name, or asked if the directory name is generic
(e.g., "project", "app", "temp").

---

## Step G2: Stack Selection
<!-- Greenfield Stage 2: Stack -->

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

**For library:**
```
AskUserQuestion(
  question: "Which language for the library?",
  options: [
    {"value": "python", "label": "Python (PyPI package)"},
    {"value": "node", "label": "Node.js / TypeScript (npm package)"},
    {"value": "go", "label": "Go module"},
    {"value": "rust", "label": "Rust crate"},
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

---

## Step G2.5: Scaffolding Proposal
<!-- Greenfield Stage 2: Stack (continued) -->

After stack selection, present a proposal listing all files that will be created. This prevents
unexpected file creation.

```
AskUserQuestion(
  question: "I'll create these files to set up your project. Approve to proceed.",
  options: [
    {"value": "approve", "label": "Approve — create the project"},
    {"value": "edit", "label": "Let me adjust..."},
    {"value": "cancel", "label": "Cancel — I'll set up manually"}
  ]
)
```

Show the file list from the selected template (e.g., for Next.js: package.json, tsconfig.json,
src/app/layout.tsx, etc.). Only proceed to scaffolding after approval.

---

## Step G3: Scaffolding
<!-- Greenfield Stage 3: Scaffold -->

Based on `$STACK_CHOICE`, generate the initial project structure. **Do NOT use `create-next-app`
or similar generators** — they produce too much boilerplate and make non-standard choices. Instead,
read the appropriate template and create a minimal, clean structure.

**Template selection:**
- Next.js (specifically `nextjs` stack choice) → `templates/greenfield/nextjs.md`
- Python (any framework) → `templates/greenfield/python.md`
- React + Vite, Express, Go, Rust, or other stacks → use `templates/greenfield/generic.md` as a
  base, but generate stack-appropriate files (e.g., for React+Vite: package.json with vite/react,
  vite.config.ts, src/App.tsx; for Express: package.json with express, src/index.ts; for Go:
  go.mod, main.go; for Rust: Cargo.toml, src/main.rs). The generic template provides the directory
  skeleton; the LLM fills in stack-specific content.

Read the selected template, replace `{project_name}` and `{project_description}` from
`$PROJECT_VISION`, and create all files using the Write tool. For Python templates, convert
`{project_name}` to a valid Python identifier by replacing hyphens with underscores (e.g.,
"my-cool-app" → "my_cool_app") for the package directory name.

**Scaffolding order (strict):**
1. Write `.gitignore` FIRST (ensures node_modules/, .env, etc. are excluded)
2. Scaffold all other files
3. `git add` by specific file names (NOT `git add -A`)

After scaffolding, install dependencies:
```bash
npm install      # Node.js
pip install -e ".[dev]"  # Python
go mod tidy      # Go
bundle install   # Rails
```

---

## Step G4: CI Setup
<!-- Greenfield Stage 4: CI -->

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

If yes, copy from `templates/ci/github-actions-<stack>.yml` to `.github/workflows/ci.yml`:
- Node.js → `templates/ci/github-actions-node.yml`
- Python → `templates/ci/github-actions-python.yml`
- Other stacks → generate a basic CI workflow based on the stack's standard tooling

If "advanced" → add the basic CI plus a deploy step (discuss with user what platform).

---

## Step G5: CLAUDE.md + llms.txt for New Projects
<!-- Greenfield Stage 5: Documentation -->

Generate CLAUDE.md tailored to the scaffolded project. Since there's no existing code to analyze,
generate from the template and stack knowledge.

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

<!-- updated-by-superflow:YYYY-MM-DD -->
```

Also create a minimal `docs/superflow/project-health-report.md` so Phase 0 detection markers work
correctly on next run:

```markdown
# Project Health Report

**Generated:** YYYY-MM-DD (greenfield scaffolding)
**Status:** New project — no existing code to analyze.

Stack: {stack}
Type: {project_type}

<!-- updated-by-superflow:YYYY-MM-DD -->
```

---

## Step G6: Connect to Shared Setup
<!-- Greenfield Stage 6: Connect -->

After greenfield scaffolding is complete:

1. **Initial commit:**
   ```bash
   git add .gitignore package.json package-lock.json tsconfig.json src/ tests/ README.md CLAUDE.md llms.txt docs/ ...
   git commit -m "Initial project setup with Superflow

   Stack: {stack}
   CI: {yes/no}
   Scaffolded by Superflow Phase 0 greenfield path"
   ```

2. **Rejoin Stage 4 (Branch B and C only):**
   - **Skip Branch A** (llms.txt + CLAUDE.md + CLAUDE.local.md) — these were just created in G5.
     Stage 4 Branch A would overwrite the freshly generated docs with no gain.
   - **Run Branch B** (permissions/hooks — Stage 4, steps 7 and 7.5 in original):
     Read `references/phase0/stage4-setup.md` and execute Branch B from there.
   - **Run Branch C** (skills recommendation, /verify skill, plugins):
     Read `references/phase0/stage4-setup.md` and execute Branch C from there.

3. **Transition message:**
   > "Project scaffolded! Now let's configure your development environment."

4. **After Stage 4 Branch B+C:** proceed to Stage 5 (references/phase0/stage5-completion.md).

Phase 1 proceeds normally — the user describes what they want to build against the freshly
scaffolded project.

---

## State Management

On entry to greenfield path, update state:
```json
{
  "phase": 0,
  "stage": "greenfield",
  "stage_index": 0,
  "context": {
    "greenfield": true
  }
}
```

After each step, update `stage_index` to reflect progress (G1=0, G2=1, G2.5=2, G3=3, G4=4,
G5=5, G6=6). This enables crash recovery — if the session dies mid-scaffolding, the next run
reads the state and resumes from the last completed step.

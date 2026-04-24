# Phase 0 — Greenfield Path

```bash
# Backward-compat guard: if sf-emit.sh wasn't sourced at session start, define a no-op fallback.
# This ensures sessions without events.jsonl still work (charter non-negotiable).
command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
```

Loaded by Stage 1 when an empty or near-empty project is detected.
After completing G6, rejoin at Stage 4 (skip Branch A — docs already created in G5).
Run Branch B (permissions/hooks) and Branch C (scaffolding) only.

This file is re-read after context compaction. Re-read it if you lose context.

---

## When This Path Is Active

Stage 1 detects greenfield when:
- Zero source files exist (`.js`, `.ts`, `.py`, `.rb`, `.go`, `.rs`)
- No manifest files present (package.json, pyproject.toml, go.mod, Cargo.toml, Gemfile)

A repo may have docs, CI configs, issue templates, and many commits — it is still greenfield if there is no application code and no manifest.

If detected, skip Stage 2 (analysis), Stage 3 (proposal), and Stage 4 Branch A (docs).
Enter at Step G1 below. After G6, rejoin at Stage 4 Branch B.

---

## Step G1: Project Vision Interview
<!-- Greenfield Stage 1: Vision -->

Ask as plain text (remote-friendly):

> "What are you building? (a) Web application, (b) API / Backend service, (c) CLI tool, (d) Library / Package, (e) Something else"

If "something else" → follow up: "Describe what you're building in a sentence or two."

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

Present stack options based on project type. Ask as plain text (remote-friendly):

**For webapp:**
> "Which stack? (a) Next.js (React + SSR + API routes), (b) React + Vite (SPA), (c) Python (FastAPI / Flask / Django), (d) Other"

**For API:**
> "Which stack for the API? (a) Express.js / Node.js, (b) FastAPI / Python, (c) Other"

**For CLI:**
> "Which language for the CLI? (a) Python (Click/Typer), (b) Go (Cobra), (c) Node.js (Commander), (d) Rust (Clap), (e) Other"

**For library:**
> "Which language? (a) Python (PyPI), (b) Node.js / TypeScript (npm), (c) Go module, (d) Rust crate, (e) Other"

If "other" → free text: "What stack/language do you want to use?"

Store as `$STACK_CHOICE`.

**Follow-up questions (conditional, plain text):**

If Node.js-based:
> "TypeScript or JavaScript? (TypeScript recommended)"

If webapp/api:
> "Database? (a) PostgreSQL, (b) SQLite, (c) MongoDB, (d) No database yet, (e) Other"

---

## Step G2.5: Scaffolding Proposal
<!-- Greenfield Stage 2: Stack (continued) -->

After stack selection, present a proposal listing all files that will be created. This prevents
unexpected file creation.

Show the file list from the selected template, then ask:

> "I'll create these files. Reply **'go'** to proceed, **'edit ...'** to adjust, or **'cancel'** to set up manually."

Only proceed to scaffolding after approval.

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

Ask as plain text:

> "Set up GitHub Actions CI? (a) Yes — basic CI (lint + test + build), (b) No CI for now, (c) Yes — with preview deployments"

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

2. **Write preflight + approval state** before entering Stage 4 — greenfield needs `context.preflight` for Branch B (permissions/hooks depend on stack):
   ```bash
   python3 -c "
   import json, datetime
   s = json.load(open('.superflow-state.json'))
   # Preflight from greenfield selections
   s['context']['preflight'] = {
       'stack': '$STACK_CHOICE',    # e.g., 'nextjs', 'python', 'react_vite'
       'team_size': '1',
       'ci': '$CI_CHOICE',          # 'yes' or 'no'
       'python3': 'yes' if '$HAS_PYTHON' else 'no',
       'pm': '$PM',                 # e.g., 'npm', 'pip'
       'formatters': ['$FORMATTER'] # e.g., ['prettier'], ['ruff']
   }
   s['context']['approval'] = {'mode': 'all', 'items': ['permissions', 'hooks', 'verify_skill', 'claude_local', 'gitignore', 'enforcement']}
   s['context']['greenfield'] = True
   s['stage'] = 'setup'
   s['stage_index'] = 3
   s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
   json.dump(s, open('.superflow-state.json', 'w'), indent=2)
   "
   ```
   Replace `$STACK_CHOICE`, `$CI_CHOICE`, `$PM`, `$FORMATTER` with actual values from G2-G4.

3. **Rejoin Stage 4 (Branch B and C only):**
   - **Skip Branch A** (llms.txt + CLAUDE.md) — these were just created in G5.
     Stage 4 Branch A would overwrite the freshly generated docs with no gain.
   - **Run Branch B** (permissions/hooks — Stage 4):
     Read `references/phase0/stage4-setup.md` and execute Branch B from there.
   - **Run Branch C** (skills recommendation, /verify skill, scaffolding):
     Read `references/phase0/stage4-setup.md` and execute Branch C from there.

4. **Transition message:**
   > "Project scaffolded! Now let's configure your development environment."

5. **After Stage 4 Branch B+C:** proceed to Stage 5 (references/phase0/stage5-completion.md).

```bash
sf_emit stage.end stage=greenfield phase:int=0
```

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

```bash
sf_emit stage.start stage=greenfield phase:int=0
```

After each step, update `stage_index` to reflect progress (G1=0, G2=1, G2.5=2, G3=3, G4=4,
G5=5, G6=6). This enables crash recovery — if the session dies mid-scaffolding, the next run
reads the state and resumes from the last completed step.

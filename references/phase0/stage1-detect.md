# Phase 0 — Stage 1: Detect & Confirm
<!-- Stage 1, Todos: parallel preflight, present confirmation, handle response -->

```bash
# Backward-compat guard: if sf-emit.sh wasn't sourced at session start, define a no-op fallback.
# This ensures sessions without events.jsonl still work (charter non-negotiable).
command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
```

Runs at Phase 0 entry. Detects project state automatically, presents a one-line summary for user confirmation, and routes to the correct path (existing project, greenfield, or skip).

**All documentation output in English.** Communicate with the user in their language.

---

## Stage Structure

```
Stage 1: "Detect & Confirm"
  Todos:
  - "Run parallel preflight detection"
  - "Compose $PREFLIGHT dict"
  - "Present confirmation to user"
  - "Handle user response (confirm / correct / skip)"
  - "Init state file"
```

TaskCreate at stage start:
```
TaskCreate(
  title: "Phase 0 — Stage 1: Detect & Confirm",
  todos: [
    "Run parallel preflight detection",
    "Compose $PREFLIGHT dict",
    "Present confirmation to user",
    "Handle user response (confirm / correct / skip)",
    "Init state file"
  ]
)
```

---

## Step 1: Init State File

Before any detection, write `.superflow-state.json`:

```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":0,"phase_label":"Onboarding","stage":"detect","stage_index":0,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
sf_emit stage.start stage=detect phase:int=0
```

---

## Step 2: Parallel Preflight Detection

Run ALL detection commands simultaneously via Bash (no sequential waits):

```bash
# Markers (check local first, then main branch as fallback)
grep -l "updated-by-superflow\|superflow:onboarded" CLAUDE.md llms.txt 2>/dev/null
git show main:CLAUDE.md 2>/dev/null | grep -q "updated-by-superflow\|superflow:onboarded" && echo "MARKER_ON_MAIN:CLAUDE.md"
git show main:llms.txt 2>/dev/null | grep -q "updated-by-superflow\|superflow:onboarded" && echo "MARKER_ON_MAIN:llms.txt"

# File count (tracked, excluding config/infra only)
git ls-files | grep -v -E '^\\.gitignore$|^\\.github/' | wc -l | tr -d ' '

# Source file count (untracked too)
find . -maxdepth 3 \( -name '*.js' -o -name '*.ts' -o -name '*.py' -o -name '*.rb' -o -name '*.go' -o -name '*.rs' \) -not -path '*/node_modules/*' -not -path '*/.git/*' | wc -l | tr -d ' '

# Commit count
git rev-list --count HEAD 2>/dev/null || echo "0"

# Unique authors (team size signal)
git log --format='%ae' | sort -u | wc -l | tr -d ' '

# CI present
test -d .github/workflows && echo "yes" || echo "no"

# Python available
python3 --version 2>/dev/null && echo "yes" || echo "no"

# Stack manifests
ls package.json pyproject.toml go.mod Cargo.toml Gemfile 2>/dev/null

# Package manager
which npm yarn pnpm bun pip go cargo bundle 2>/dev/null | head -1

# Formatter/linter configs
ls .prettierrc .eslintrc* ruff.toml .ruff.toml pyproject.toml .rubocop.yml .golangci.yml 2>/dev/null

# Existing docs
ls llms.txt CLAUDE.md docs/superflow/project-health-report.md 2>/dev/null
```

---

## Step 3: Compose $PREFLIGHT

Compile results into a dict. Example shape:

```json
{
  "markers_found": ["CLAUDE.md"],
  "file_count": 42,
  "source_count": 18,
  "commit_count": 37,
  "team_size": "2",
  "ci": "yes",
  "python3": "yes",
  "stack": "Python",
  "framework": "FastAPI",
  "pm": "pip",
  "formatters": ["ruff"],
  "has_llms_txt": false,
  "has_claude_md": true,
  "has_health_report": false
}
```

**Stack detection** — read manifest files, then verify by checking actual imports:
- `package.json` present → Node.js; inspect `dependencies` for react/next/express/fastify/vue/svelte
- `pyproject.toml` / `requirements.txt` → Python; grep imports for fastapi/django/flask/pydantic
- `go.mod` → Go
- `Cargo.toml` → Rust
- `Gemfile` → Ruby

> Never guess framework from directory names. Always read actual `import`/`require` statements.

---

## Step 4: Greenfield Routing

Check for manifest files: `ls package.json pyproject.toml go.mod Cargo.toml Gemfile 2>/dev/null`

If `source_count=0` AND no manifest files:

This is a greenfield project — there is no application code regardless of how many docs, CI configs, or commits exist. Tell the user: "This looks like a new project! I'll help set up the foundation." → load and follow `references/phase0/greenfield.md`. Do not proceed with the steps below.

> **Not greenfield:** A repo with manifest files (package.json, pyproject.toml, etc.) but no source code is treated as an existing project — the user already chose a stack and scaffolding is partially done.

---

## Step 5: Present Confirmation

Compose a one-line summary and ask as plain text (remote-friendly — works via Telegram):

> "Detected: [stack] + [framework], [team_size] developer(s), CI: [ci].
> I'll run: security audit, code quality analysis, permissions + hooks setup, and create project docs. ~2 min.
> Reply **'go'** to start or **'fix ...'** to correct something."

**Do NOT offer 'skip' in the message.** Phase 0 runs once per project and sets up critical infrastructure (security audit, permissions, hooks, docs). Skipping it means no security findings, no permissions for autonomous execution, no hooks, no health report.

If the user explicitly asks to skip (unprompted), handle it via Step 6 "skip" path — but never suggest it.

If no response within a reasonable time (non-interactive mode), proceed with `confirm` automatically.

---

## Step 6: Handle Response

### "confirm" (or auto)
Persist `$PREFLIGHT` to state and advance stage:

```bash
python3 -c "
import json, datetime
s = json.load(open('.superflow-state.json'))
s['stage'] = 'detect'
pf = $PREFLIGHT_JSON
s['context'] = {
    'preflight': pf,
    'user_context': {
        'team': 'solo' if int(pf.get('team_size','1')) <= 1 else 'small_team',
        'experience': 'intermediate',
        'ci': pf.get('ci','no'),
        'dismissed': False
    }
}
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s, open('.superflow-state.json', 'w'), indent=2)
"
```

Then proceed to Stage 2 (`references/phase0/stage2-analysis.md`).

### "fix ..." / "correct"
User provides correction inline (e.g., "fix: stack is Next.js, team is 3 people"). Parse the correction from their message.

Update `$PREFLIGHT` with the correction, re-display the confirmation (Step 5), repeat.

### "skip"
Write markers in ALL required files so next run detects Phase 0 as complete. Transition state to phase=1:

```bash
# Write markers in all 3 detection files
MARKER="<!-- updated-by-superflow:$(date +%Y-%m-%d) -->"

# CLAUDE.md — create minimal if absent, append marker
[ ! -f CLAUDE.md ] && echo "# Project" > CLAUDE.md
echo "" >> CLAUDE.md && echo "$MARKER" >> CLAUDE.md

# llms.txt — create minimal if absent, append marker
[ ! -f llms.txt ] && echo "# Project" > llms.txt
echo "" >> llms.txt && echo "$MARKER" >> llms.txt

# Health report — create minimal, append marker
mkdir -p docs/superflow
echo "# Project Health Report" > docs/superflow/project-health-report.md
echo "Skipped — Phase 0 was skipped by user." >> docs/superflow/project-health-report.md
echo "$MARKER" >> docs/superflow/project-health-report.md

# Ensure .gitignore
git check-ignore -q .worktrees 2>/dev/null || echo ".worktrees/" >> .gitignore
git check-ignore -q .superflow-state.json 2>/dev/null || echo ".superflow-state.json" >> .gitignore

# Update state
python3 -c "
import json, datetime
s = json.load(open('.superflow-state.json'))
s['phase'] = 1
s['phase_label'] = 'Product Discovery'
s['stage'] = 'research'
s['stage_index'] = 0
s['context'] = {'preflight': {'skipped': True}, 'skip_phase0': True}
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s, open('.superflow-state.json', 'w'), indent=2)
"
```bash
sf_emit stage.end stage=detect phase:int=0
sf_emit phase.end phase:int=0 label="Onboarding"
```

Tell user Phase 0 was skipped, then re-read `references/phase1-discovery.md` and begin Phase 1.

---

## Completion

Mark stage done. State now has `context.preflight` populated. Stage 2 reads from there.

```
TaskUpdate(id: <task_id>, status: "completed")
```

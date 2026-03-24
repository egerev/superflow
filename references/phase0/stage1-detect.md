# Phase 0 — Stage 1: Detect & Confirm
<!-- Stage 1, Todos: parallel preflight, present confirmation, handle response -->

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
```

---

## Step 2: Parallel Preflight Detection

Run ALL detection commands simultaneously via Bash (no sequential waits):

```bash
# Markers
grep -l "updated-by-superflow\|superflow:onboarded" CLAUDE.md llms.txt 2>/dev/null

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

If (`file_count=0` AND `source_count=0`) OR (`file_count≤5` AND `commit_count≤2` AND `source_count=0`):

This is a greenfield or near-empty project (e.g., only README.md + LICENSE). Tell the user: "This looks like a new project! I'll help set up the foundation." → load and follow `references/phase0/greenfield.md`. Do not proceed with the steps below.

---

## Step 5: Present Confirmation

Compose a one-line summary and ask with AskUserQuestion:

```
AskUserQuestion(
  question: "Detected: [stack] + [framework], [team_size] developer(s), CI: [ci]. I'll audit docs, code quality, and security. ~2 min.",
  options: [
    {"value": "confirm",  "label": "Looks right — start Phase 0"},
    {"value": "correct",  "label": "Correct something first"},
    {"value": "skip",     "label": "Skip Phase 0 — go straight to Phase 1"}
  ]
)
```

If AskUserQuestion is unavailable (non-interactive), proceed with `confirm` automatically.

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

### "correct"
Ask for free-text correction:

```
AskUserQuestion(
  question: "What should I correct?",
  placeholder: "e.g. stack is Next.js, team is 3 people"
)
```

Update `$PREFLIGHT` with the correction, re-display the confirmation (Step 5), repeat.

### "skip"
Write markers with defaults, transition state to phase=1, proceed to Phase 1 immediately:

```bash
# Append marker to CLAUDE.md (create minimal if absent)
echo "" >> CLAUDE.md
echo "<!-- updated-by-superflow:$(date +%Y-%m-%d) -->" >> CLAUDE.md

python3 -c "
import json, datetime
s = json.load(open('.superflow-state.json'))
s['phase'] = 1
s['phase_label'] = 'Discovery'
s['stage'] = 'research'
s['stage_index'] = 0
s['context'] = {'preflight': {'skipped': True}, 'skip_phase0': True}
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s, open('.superflow-state.json', 'w'), indent=2)
"
```

Tell user Phase 0 was skipped, then re-read `references/phase1-discovery.md` and begin Phase 1.

---

## Completion

Mark stage done. State now has `context.preflight` populated. Stage 2 reads from there.

```
TaskUpdate(id: <task_id>, status: "completed")
```

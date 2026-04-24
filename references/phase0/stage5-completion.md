# Phase 0 — Stage 5: Completion
<!-- Stage 5, Todos: write markers, persist tech debt, update state, show summary -->

```bash
# Backward-compat guard: if sf-emit.sh wasn't sourced at session start, define a no-op fallback.
# This ensures sessions without events.jsonl still work (charter non-negotiable).
command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
```

This file is re-read after context compaction. Re-read it if you lose context.

**State at entry:** phase=0, stage="completion", stage_index=4
**State at exit:** phase=1, stage="research", stage_index=0

---

## TaskCreate at Stage Start

```
TaskCreate(
  title: "Stage 5: Completion",
  todos: [
    "Write markers in CLAUDE.md, llms.txt, health report",
    "Persist tech_debt to .superflow-state.json",
    "Update state to phase=1",
    "Show completion summary to user"
  ]
)
```

```bash
sf_emit stage.start stage=completion phase:int=0
```

---

## Todo 0: Ensure .gitignore (always runs, regardless of approval mode)

```bash
git check-ignore -q .worktrees 2>/dev/null || echo ".worktrees/" >> .gitignore
git check-ignore -q .superflow-state.json 2>/dev/null || echo ".superflow-state.json" >> .gitignore
git check-ignore -q CLAUDE.local.md 2>/dev/null || echo "CLAUDE.local.md" >> .gitignore
```

This runs in Stage 5 (not Stage 4 Branch C) to guarantee execution even if Branch C was skipped via "skip" or "custom" approval modes.

---

## Todo 1: Write Markers

Append the exact marker to every file Phase 0 touched. Use today's date (ISO 8601).

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

Files that must receive the marker:

1. **CLAUDE.md** — append at the very end of the file
2. **llms.txt** — append at the very end of the file
3. **docs/superflow/project-health-report.md** — already created in Stage 3; append marker if not already present

All three must exist and have the marker for Phase 0 to be fully skipped on the next run.
Detection logic (from SKILL.md): checks CLAUDE.md → llms.txt → health report in order.

**Verify after writing:**
```bash
grep -l "updated-by-superflow" CLAUDE.md llms.txt docs/superflow/project-health-report.md
```
Expected: all three paths printed. If any is missing, add the marker before proceeding.

TaskUpdate: "Write markers in CLAUDE.md, llms.txt, health report" → done

---

## Todo 2: Persist tech_debt to State

Read the findings from Stage 2 (code quality agent output) and write a `tech_debt` summary to
`.superflow-state.json` under `context.tech_debt`. Phase 1 reads this to suggest including
relevant tech debt when tasks touch affected modules.

**Structure to write:**
```json
{
  "total_todos": 23,
  "files_over_500_loc": ["services/billing.py", "models/user.py"],
  "untested_modules": ["payments/", "notifications/"],
  "security_issues": 2,
  "generated_at": "2026-03-25T12:00:00Z"
}
```

Use values from the actual Stage 2 analysis. If an agent didn't find any issues for a field,
use 0 (integer) or [] (array) — never omit the field.

**Merge into state (do NOT overwrite the whole file):**
```bash
python3 -c "
import json, datetime
with open('.superflow-state.json') as f:
    state = json.load(f)
state.setdefault('context', {})['tech_debt'] = {
    'total_todos': REPLACE_ME,
    'files_over_500_loc': REPLACE_ME,
    'untested_modules': REPLACE_ME,
    'security_issues': REPLACE_ME,
    'generated_at': datetime.datetime.utcnow().isoformat() + 'Z'
}
with open('.superflow-state.json', 'w') as f:
    json.dump(state, f, indent=2)
"
```

TaskUpdate: "Persist tech_debt to .superflow-state.json" → done

---

## Todo 3: Update State to Phase 1

Write the final Phase 0 state, advancing to Phase 1:

```bash
python3 -c "
import json, datetime
with open('.superflow-state.json') as f:
    state = json.load(f)
state['phase'] = 1
state['phase_label'] = 'Product Discovery'
state['stage'] = 'research'
state['stage_index'] = 0
state['last_updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
with open('.superflow-state.json', 'w') as f:
    json.dump(state, f, indent=2)
"
```

**Verify state:**
```bash
python3 -c "import json; s=json.load(open('.superflow-state.json')); print(s['phase'], s['stage'])"
```
Expected output: `1 research`

TaskUpdate: "Update state to phase=1" → done

---

## Todo 4: Completion Summary

Show the user a 5-8 line summary of what Phase 0 accomplished. Use actual values from this session
(not the placeholders below).

```
## Phase 0 Complete

Created: CLAUDE.md, llms.txt, health report, /verify skill
Configured: permissions (28 commands), hooks (ruff format on save)
Security: 2 issues flagged in health report — review before deploying

**Next step:** Run `/clear` then `/superflow` to start working on your project.
Phase 1 will use the documentation and audit results from this session.
```

**If permissions or hooks were configured**, add the restart note:
> "To activate permissions and hooks, restart Claude Code:
> 1. Exit this session (Ctrl+C or `exit`)
> 2. Run `claude` or `claude --resume`"

**If nothing was configured** (user declined everything):
> "Phase 0 complete! Run `/clear` then `/superflow` to start Phase 1."

**Commit onboarding results (AUTOMATIC — do not ask):**
Phase 0 artifacts must be committed to **main** so ALL future branches/worktrees inherit them. Without this, Phase 0 re-triggers every session on every new branch.

```bash
# 1. Commit on current branch
git add CLAUDE.md llms.txt docs/superflow/project-health-report.md .claude/
git commit -m "chore: superflow Phase 0 onboarding"

# 2. Propagate to main (so new branches inherit artifacts)
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
  git checkout main
  git checkout "$CURRENT_BRANCH" -- CLAUDE.md llms.txt docs/superflow/project-health-report.md
  git add CLAUDE.md llms.txt docs/superflow/project-health-report.md
  git commit -m "chore: superflow Phase 0 onboarding"
  git checkout "$CURRENT_BRANCH"
fi
```

If on main directly or after propagating: push so remote branches also inherit (`git push origin main`).

TaskUpdate: "Show completion summary to user" → done

If Telegram MCP available (`mcp__plugin_telegram_telegram__reply` tool is present), send at completion:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Phase 0 complete. Run /superflow to continue.")
```

---

## Completion Checklist

Walk through each item. If any is unchecked, go back to the relevant stage and complete it.

- [ ] CLAUDE.md has `<!-- updated-by-superflow:YYYY-MM-DD -->` marker
- [ ] llms.txt has `<!-- updated-by-superflow:YYYY-MM-DD -->` marker
- [ ] `docs/superflow/project-health-report.md` exists and has marker
- [ ] `.superflow-state.json` `phase` = 1, `stage` = "research"
- [ ] `context.tech_debt` populated with values from Stage 2 analysis

All items checked → Phase 0 is complete.

```bash
sf_emit stage.end stage=completion phase:int=0
sf_emit phase.end phase:int=0 label="Onboarding"
```

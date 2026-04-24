# Phase 0 — Stage 3: Report & Proposal
<!-- Stage 3, Todos: generate health report, show summary, get approval -->

```bash
# Event emission preloader — idempotent, runs at top of every phase doc bash usage.
# Tries (in order): already-sourced sf_emit → local tools/sf-emit.sh → runtime-aware paths → no-op.
# Also restores SUPERFLOW_RUN_ID from state if unset.
if ! command -v sf_emit >/dev/null 2>&1; then
  for _sf_path in \
      "./tools/sf-emit.sh" \
      "$HOME/.claude/skills/superflow/tools/sf-emit.sh" \
      "$HOME/.codex/skills/superflow/tools/sf-emit.sh" \
      "$HOME/.agents/skills/superflow/tools/sf-emit.sh"; do
    if [ -f "$_sf_path" ]; then source "$_sf_path"; break; fi
  done
  command -v sf_emit >/dev/null 2>&1 || sf_emit() { return 0; }
fi
if [ -z "${SUPERFLOW_RUN_ID:-}" ] && [ -f .superflow-state.json ]; then
  SUPERFLOW_RUN_ID=$(python3 -c 'import json; print(json.load(open(".superflow-state.json")).get("context",{}).get("run_id",""))' 2>/dev/null)
  [ -n "$SUPERFLOW_RUN_ID" ] && export SUPERFLOW_RUN_ID
fi
# If run_id still unavailable after best-effort restore, install no-op to avoid set -e aborts
if [ -z "${SUPERFLOW_RUN_ID:-}" ]; then
  sf_emit() { return 0; }
fi
```

Re-read this file at the start of Stage 3. Context compaction during Stage 2 analysis erases prior content.

**State source of truth:** Read `.superflow-state.json` — do not rely on LLM context for `$PREFLIGHT` or agent results.

---

## Stage Entry

If Telegram MCP available (`mcp__plugin_telegram_telegram__reply` tool is present), send at stage start:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Analysis complete, preparing report...")
```

Update state to Stage 3:
```bash
python3 -c "
import json,datetime
s=json.load(open('.superflow-state.json'))
s['stage']='report'; s['stage_index']=2
s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s,open('.superflow-state.json','w'),indent=2)
"
sf_emit stage.start stage=report phase:int=0
```

TaskCreate:
```
title: "Phase 0: Report & Proposal"
todos: ["Generate health report", "Save to docs/", "Show summary to user", "Present permissions tradeoff", "Get approval"]
```

---

## Step 3.1 — Generate & Save Health Report

Synthesize results from Stage 2 agents into a full report. Save to `docs/superflow/project-health-report.md` (create directory if needed). **All claims must have evidence** (file path, count, line number).

```markdown
# Project Health Report
<!-- updated-by-superflow:YYYY-MM-DD -->

## Overview
- **Stack:** [detected from imports — never guess from directory names]
- **Size:** [N] source files, [LOC] total LOC across [M] modules
- **Tests:** [N] test files / [M] source files ([ratio]%). Functions: [count]
- **Python / Node / etc version:** [detected]

## Large Files (>500 LOC) — Refactoring Candidates
| File | LOC | Role | Recommendation |
|------|-----|------|----------------|
| path/to/file.py | 1,675 | description | Split into X, Y |

(If none: "No files >500 LOC detected.")

## Architecture Violations
| Violation | File:Line | Details |
|-----------|-----------|---------|
| Business imports adapter | file.py:42 | `from adapters.x import Y` |

(If none: "No architecture violations detected — [describe actual layer structure]")

## Technical Debt (Prioritized)
| Priority | Issue | Location | Evidence | Recommendation |
|----------|-------|----------|----------|----------------|
| P0 | ... | file:line | what was found | fix suggestion |
| P1 | ... | ... | ... | ... |
| P2 | ... | ... | ... | ... |

## DevOps & Infrastructure
- Docker: [N services, any `latest` tags?, volumes?]
- CI/CD: [what's configured, what's missing]
- Deploy: [migrations?, rollback?, health checks?]
- Security scanning: [dependabot?, CodeQL?]
- Backups: [strategy or "none detected"]

## Documentation Freshness
| Doc | Last Updated | Status |
|-----|-------------|--------|
| README.md | YYYY-MM-DD | current/stale |
| CLAUDE.md | — | missing/present |
| llms.txt | — | missing/present |

## Security Issues (ALL findings — do not summarize or truncate)
| Severity | Issue | Location | Evidence |
|----------|-------|----------|----------|
| HIGH | hardcoded DB password | config.py:42 | literal `password="..."` |
| MED | no rate limiting | routes/auth.py | no middleware detected |
```

**Absence of findings requires proof** — write "No [category] found — verified by [method]", not just silence.

---

## Step 3.2 — Show Actionable Summary

Do NOT show the full report inline. Show a focused summary in the user's language that highlights what matters NOW vs what will be addressed over time:

```
## Project Audit Complete

**Stack:** [e.g. Python 3.11 + FastAPI + PostgreSQL (detected from imports in src/)]
**Size:** [N] source files, [LOC] LOC across [M] modules

### 🔴 Needs Attention Now
[Only include this section if there are CRITICAL/HIGH findings. List 1-3 most urgent issues:]
- **[Security/Architecture/etc]:** [concrete issue with file:line] — [1-sentence fix suggestion]
- **[Issue 2]:** ...

[If nothing critical: "No critical issues found — the codebase is in good shape for feature work."]

### 📊 Project Health
- **Test coverage**: [N test files] / [M source files] ([ratio]%). [Untested: module1, module2]
- **Code duplication**: [N instances found / none detected]
- **Type hygiene**: [N redefined types / clean]
- **Dead code**: [N unreachable functions / clean]
- **Tech debt**: [N] TODO/FIXME, [N] files >500 LOC

### 🔄 Tech Debt Strategy
The findings above are saved and will be addressed progressively:
when you work on new features, Superflow cross-references your changes
with known tech debt. If a feature touches a module with issues,
it suggests bundling the fix into the same sprint — closing gaps
gradually without dedicated refactoring sprints.

### What I'll Set Up
- Create CLAUDE.md + llms.txt (project documentation for AI agents)
- Configure permissions for autonomous execution
- [Set up auto-formatting hooks — [formatter] detected] (if applicable)
- Create /verify skill (quick health check command)

Full report: docs/superflow/project-health-report.md
```

**If critical findings exist**, after the summary add:
> "I recommend fixing the critical issues before starting feature work. Want me to create a fix plan? (yes/skip)"
If yes: note the issues — they'll become Sprint 0 in Phase 1 planning.

---

## Step 3.3 — Present Permissions Tradeoff

Before the approval gate, explain what broad permissions mean. Show this once, concisely:

```
These broad permissions (git *, gh *, npm *, etc.) allow Phase 2 to run
autonomously — dozens of commands without prompts. They cover all subcommands
including destructive ones (git push --force, etc.).

Tradeoff: autonomy vs safety. Decline to keep manual approval for each command.
```

---

## Step 3.4 — 3-Path Approval Gate

Ask as plain text (remote-friendly — works via Telegram):

> "Does this plan look right?
> Reply **'go'** to approve all, **'customize'** to choose what to set up, or **'docs only'** to skip permissions and hooks."

**"Customize" sub-flow** — show checklist and ask for toggles (free text acceptable):
```
- [x] CLAUDE.md + llms.txt   (always included)
- [x] Permissions (~/.claude/settings.json)
- [x] Auto-formatting hooks  (.claude/settings.json)
- [x] /verify skill
- [x] CLAUDE.local.md
- [ ] Desktop notifications
```
Ask: "Which items would you like to include/exclude?" Then build `items` list from response.

**Express path:** If `context.user_context.dismissed == true` (user said "just go" in Stage 1), auto-approve with mode "all". Log: "Auto-approved proposal (express mode)."

---

If the user explicitly declines the proposal (no setup wanted, abandon onboarding):
```bash
sf_emit run.end status=blocked
```

## Step 3.5 — Persist Approval to State

```bash
python3 -c "
import json,datetime
s=json.load(open('.superflow-state.json'))
# Replace MODE and ITEMS with actual values from Step 3.4
s['context']['approval'] = {
  'mode': 'all',          # 'all' | 'custom' | 'skip'
  'items': [              # for 'custom' mode; empty = all for 'all' mode
    'docs', 'permissions', 'hooks', 'verify_skill', 'claude_local', 'notifications'
  ]
}
s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s,open('.superflow-state.json','w'),indent=2)
"
```

Stage 4 reads `context.approval` from the state file — not from LLM context.

```bash
sf_emit stage.end stage=report phase:int=0
```

TaskUpdate: mark all todos complete, status="completed". Proceed to Stage 4.

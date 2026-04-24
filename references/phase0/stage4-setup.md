# Phase 0 — Stage 4: Documentation & Environment
<!-- Stage 4, Todos: dispatch 3 branches, wait, validate, recommend skills/plugins -->

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
```

Re-read this file at the start of Stage 4. Context compaction during Stage 3 erases prior content.

**State source of truth:** Read `context.approval` from `.superflow-state.json` before dispatching any branch. Do not rely on LLM context.

```bash
python3 -c "import json; s=json.load(open('.superflow-state.json')); print(json.dumps(s.get('context',{}), indent=2))"
```

---

## Stage Entry

Update state to Stage 4:
```bash
python3 -c "
import json,datetime
s=json.load(open('.superflow-state.json'))
s['stage']='setup'; s['stage_index']=3
s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s,open('.superflow-state.json','w'),indent=2)
"
sf_emit stage.start stage=setup phase:int=0
```

TaskCreate:
```
title: "Phase 0: Documentation & Environment"
todos: ["Dispatch branches per approval", "Wait for all branches", "Validate no file conflicts", "Recommend skills/plugins"]
```

---

## Execution Matrix

Determine which branches to dispatch based on `context.approval.mode`:

| Approval Mode | Branch A (Docs) | Branch B (Permissions & Hooks) | Branch C (Scaffolding) |
|---------------|-----------------|--------------------------------|------------------------|
| `all`         | Yes             | Yes                            | Yes                    |
| `custom`      | Always          | If in `items`                  | If in `items`          |
| `skip`        | Yes             | No                             | No                     |
| `greenfield`  | No (done in G5) | Yes                            | Yes                    |

For `custom` mode, check `context.approval.items`:
- `"permissions"` in items → run Branch B (permissions portion)
- `"hooks"` in items → run Branch B (hooks portion)
- Branch B runs if either `"permissions"` or `"hooks"` is selected
- `"verify_skill"`, `"claude_local"` in items → run Branch C

---

## File Ownership (STRICT — branches must not write each other's files)

| Branch | Owns | Must NOT touch |
|--------|------|----------------|
| A — Documentation | `llms.txt`, `CLAUDE.md` (project root) | settings.json, .gitignore |
| B — Permissions & Hooks | `~/.claude/settings.json`, `.claude/settings.json` | llms.txt, CLAUDE.md |
| C — Scaffolding | `.claude/skills/verify/SKILL.md`, `CLAUDE.local.md`, `.gitignore` | settings.json, llms.txt |

---

## Branch Dispatch

Dispatch approved branches in parallel using `run_in_background: true`. Each branch is self-contained — read from state file, not from orchestrator context.

### Branch A — Documentation (deep-doc-writer, Opus required)

```
Agent(
  subagent_type: "deep-doc-writer",
  run_in_background: true,
  prompt: "
You are Branch A of Phase 0 setup. Your ONLY job: audit and create/update llms.txt and CLAUDE.md.

**Read first:** `.superflow-state.json` for $PREFLIGHT.stack and $PREFLIGHT.formatters.
Read `prompts/llms-txt-writer.md` and `prompts/claude-md-writer.md` for writing standards.

FILE OWNERSHIP: You write llms.txt and CLAUDE.md only. Touch nothing else.

IDEMPOTENCY: Check if each file exists before writing. If it exists, audit it. If missing, create it.

**llms.txt:**
- Verify every framework/library name by reading actual import statements — never guess from directory names
- Audit: count source directories vs llms.txt entries, check all linked paths exist
- Create/update per prompts/llms-txt-writer.md
- Append marker: <!-- updated-by-superflow:YYYY-MM-DD -->

**CLAUDE.md:**
- Audit: check every documented file path exists (X/Y paths valid), run documented commands
- Check git log --since last marker date — list new modules added
- Create/update per prompts/claude-md-writer.md (<200 lines target)
- Append marker: <!-- updated-by-superflow:YYYY-MM-DD -->

**Quality bar:** Opus is required here. Every claim needs evidence (file path, count, command output). Wrong documentation misleads all future sessions — it is worse than no documentation.

**CRITICAL — Verify markers before reporting:**
```bash
grep -c 'updated-by-superflow' CLAUDE.md llms.txt
```
Both must return ≥1. If either returns 0, append the marker NOW: `echo '<!-- updated-by-superflow:YYYY-MM-DD -->' >> CLAUDE.md`

Report: 'Branch A complete — llms.txt: [created|updated, N entries, marker: yes], CLAUDE.md: [created|updated, X/Y paths valid, marker: yes]'
"
)
```

### Branch B — Permissions & Hooks (fast-implementer, Sonnet)

Only dispatch if approved. Check `context.approval` before proceeding.

```
Agent(
  subagent_type: "fast-implementer",
  run_in_background: true,
  prompt: "
You are Branch B of Phase 0 setup. Your ONLY job: set up permissions and hooks.

**Read first:** `.superflow-state.json` for context.approval (items list) and context.preflight.stack/formatters.

FILE OWNERSHIP: You write ~/.claude/settings.json and .claude/settings.json only. Touch nothing else.

IDEMPOTENCY: Merge into existing files — never overwrite. If permissions already exist, skip adding duplicates.

**Permissions (~/.claude/settings.json):**
Only if 'permissions' in context.approval.items (or mode='all'):
- Build permission list: Core permissions always + stack-specific based on preflight.stack
- Core: git *, gh *, ls *, cat *, find *, jq *, sed *, awk *, mkdir *, cp *, mv *, python3 *, node *, codex *, timeout *, etc.
- Stack-specific: npm/yarn/pnpm/bun (Node), pip/pytest/ruff (Python), bundle/rake (Ruby), go/* (Go), cargo/* (Rust), docker/* (if detected)
- Merge into ~/.claude/settings.json — use python3 to read, update .permissions.allow array, write back
- Do NOT add permissions for stacks not present in the project

**Hooks (.claude/settings.json):**
Only if 'hooks' in context.approval.items (or mode='all'):
- Select hook template based on preflight.formatters:
  - prettier → PostToolUse on Edit|Write for .js/.ts/.jsx/.tsx/.json/.css/.md files
  - ruff/black → PostToolUse on Edit|Write for .py files
  - rubocop → PostToolUse on Edit|Write for .rb files
  - gofmt → PostToolUse on Edit|Write for .go files
- 2-stage verification:
  1. Check binary exists: `which ruff` / `which prettier` / etc.
  2. Run on a test file: `ruff format --check <test_file> 2>/dev/null`
  If binary missing → write hook anyway but warn: '[tool] not found — hook inactive until installed'
- Add desktop notification hook to ~/.claude/settings.json (Notification matcher: permission_prompt|idle_prompt)
- Add PostCompact + SessionStart hooks to ~/.claude/settings.json if not present

Report: 'Branch B complete — permissions: [added N / skipped], hooks: [formatter added | binary missing: ruff not found]'
"
)
```

### Branch C — Scaffolding (fast-implementer, Sonnet)

Only dispatch if approved. Check `context.approval` before proceeding.

```
Agent(
  subagent_type: "fast-implementer",
  run_in_background: true,
  prompt: "
You are Branch C of Phase 0 setup. Your ONLY job: create /verify skill, CLAUDE.local.md, and check .gitignore.

**Read first:** `.superflow-state.json` for context.approval (items list), context.user_context, context.preflight.stack.

FILE OWNERSHIP: You write .claude/skills/verify/SKILL.md, CLAUDE.local.md, .gitignore only. Touch nothing else.

IDEMPOTENCY: Check if each file exists before writing. Skip if already present and valid.

**Enforcement rules:**
Check ~/.claude/rules/superflow-enforcement.md exists. If missing, copy from skill directory.

**/.gitignore:**
Ensure these entries exist (append if missing, never remove existing lines):
  .worktrees/
  .superflow/
  # Explicit entries for event log artifacts (redundant with .superflow/ above, kept for self-documentation).
  .superflow/events.jsonl
  .superflow/archive/
  .superflow-state.json
  CLAUDE.local.md

**CLAUDE.local.md (if 'claude_local' in items or mode='all'):**
Create personal preferences file (gitignored) based on context.user_context:
  # Personal Preferences
  ## Role
  - [Solo founder | Team member] — [experience] with [stack]
  ## Communication
  - [Based on experience: explain tradeoffs / be terse]
  ## Workflow
  - Using Superflow for feature development

**Verify skill (if 'verify_skill' in items or mode='all'):**
Create .claude/skills/verify/SKILL.md with stack-appropriate health check commands:
  - Python: pytest --tb=short, ruff check ., mypy . (if configured)
  - Node: npm test, npm run lint, tsc --noEmit (if TypeScript)
  - Go: go test ./..., go vet ./...
  - Ruby: bundle exec rspec, rubocop
  - Generic: git status, [detected test command]

Report: 'Branch C complete — .gitignore: [updated|ok], CLAUDE.local.md: [created|skipped], verify skill: [created|skipped], enforcement rules: [present|copied]'
"
)
```

---

## Orchestrator: Wait & Validate

After dispatching, wait for all background agents to complete. Then validate:

1. **No file conflicts** — check file ownership rules above were respected
2. **Markers present** — llms.txt and CLAUDE.md contain `<!-- updated-by-superflow:` marker
3. **Settings valid** — if Branch B ran, verify `~/.claude/settings.json` is valid JSON:
   ```bash
   python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))" 2>&1
   ```
4. **Report branch results** to user (brief, one line per branch)

If a branch failed: note the failure, continue with what succeeded. Do not block Phase 0 completion on optional branches.

---

## Skills & Plugins Recommendations

After branches complete, show brief stack-relevant suggestions (orchestrator, not a subagent):

**Python projects:** `/webapp-testing` for integration tests, black/ruff if not configured
**Node/React:** `/canvas-design` for UI work, `/webapp-testing` for Playwright
**All projects:** Claude Code extensions for VS Code/Cursor if not detected

Keep this to 3-5 bullets max. Do not list everything — only what's relevant to the detected stack.

---

## Stage Exit

```bash
python3 -c "
import json,datetime
s=json.load(open('.superflow-state.json'))
s['stage']='completion'; s['stage_index']=4
s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s,open('.superflow-state.json','w'),indent=2)
"
sf_emit stage.end stage=setup phase:int=0
```

TaskUpdate: mark all todos complete, status="completed". Proceed to Stage 5 (Completion).

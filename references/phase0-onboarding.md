# Phase 0: Onboarding (FIRST RUN — INTERACTIVE)

Runs once per project. Detects project state, routes to the correct stage file, and loads it via the Read tool.
This phase is **conversational** — talk to the user, don't just execute silently.

**All documentation output MUST be in English.** User communication follows their language preference; generated files (llms.txt, CLAUDE.md, reports) are always English.

---

## Stage → File Mapping

| Stage | File | What |
|-------|------|------|
| 1 | references/phase0/stage1-detect.md | Detect & Confirm |
| 2 | references/phase0/stage2-analysis.md | Analysis (5 agents) |
| 3 | references/phase0/stage3-report.md | Report & Proposal |
| 4 | references/phase0/stage4-setup.md | Documentation & Environment |
| 5 | references/phase0/stage5-completion.md | Completion |
| G | references/phase0/greenfield.md | Empty project path |

---

## Detection Logic

Phase 0 leaves an **exact marker** in each file it touches:

```
<!-- updated-by-superflow:YYYY-MM-DD -->
```

Both `<!-- updated-by-superflow:` (v2.0.3+) and `<!-- superflow:onboarded` (v2.0.2) are valid markers.

**Priority 1: Check state file for in-progress Phase 0** (crash recovery):

If `.superflow-state.json` exists AND `phase=0` AND `stage_index < 5`:
- Resume from Stage at `stage_index` (NOT stage_index+1 — stage_index is set at stage START, so the stage may be incomplete)
- This takes priority over marker-based detection

**Priority 2: Marker-based detection** (check in order, stop at first match):

Check markers on the current branch first. **If not found AND current branch ≠ main, also check main:**
```bash
# Check current branch
grep -q "updated-by-superflow\|superflow:onboarded" CLAUDE.md 2>/dev/null && echo "LOCAL" || \
  git show main:CLAUDE.md 2>/dev/null | grep -q "updated-by-superflow\|superflow:onboarded" && echo "ON_MAIN"
```
If markers exist on main but not locally → the current branch was created before Phase 0 completed. **Skip Phase 0** (markers are in main, they'll arrive after merge/rebase).

1. `CLAUDE.md` does NOT contain either marker (neither locally nor on main) → **full Phase 0** from Stage 1
2. `llms.txt` does NOT contain either marker (neither locally nor on main) → **partial**: Stage 1 (repopulate preflight) → write `context.approval = {mode: "skip", items: []}` → Stage 4 Branch A only (create llms.txt)
3. `docs/superflow/project-health-report.md` does NOT exist → **partial**: Stage 1 → Stage 2 → Stage 3 → Stage 5
4. All present → **skip Phase 0**, proceed to Phase 1

> **Note:** Partial paths always start with Stage 1 (fast — just detection, no analysis) to populate `context.preflight` needed by downstream stages. Stage 1 is idempotent. For path #2, the router writes `context.approval` directly (no Stage 3 needed).

**NOT valid markers** (these can exist without Superflow):
- The word "superflow" in CLAUDE.md (could be mentioned casually)
- `docs/superflow/` directory alone (could be created by user)
- `.par-evidence.json` (created by Phase 2, not Phase 0)

---

## Recovery Matrix

| Scenario | Action |
|----------|--------|
| (a) No markers + no `.superflow-state.json` | Full Phase 0 from Stage 1 |
| (b) State file: phase=0, stage_index=N, N<5 | Resume from Stage at index N (stage may be incomplete) |
| (c) CLAUDE.md marker only, no llms.txt marker | Partial: Stage 1 → inject approval(skip) → Stage 4 Branch A only |
| (d) All markers + health report missing | Partial: Stage 1 → Stage 2 → Stage 3 → Stage 5 |
| (e) All markers + all artifacts present | Skip Phase 0, proceed to Phase 1 |

> **State-based recovery (b) takes priority over marker-based detection (c-e).** A Stage 4 crash after Branch A writes markers would be caught by (b) since stage_index=3 < 5, not misclassified by (e).

---

## State Management

At Phase 0 start, write `.superflow-state.json`:

```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":0,"phase_label":"Onboarding","stage":"detect","stage_index":0,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
```

Update after each stage transition:

```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s['stage']='analysis'; s['stage_index']=1; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```

If python3 is unavailable, overwrite the full file with updated JSON manually.

---

## Execution

1. Run detection logic above to determine which path applies.
2. Read the appropriate stage file using the Read tool.
3. Follow the instructions in that stage file exactly — it owns TaskCreate/TaskUpdate for its stage.

**Start here:** Read `references/phase0/stage1-detect.md` (or the specific stage file identified by detection/recovery).

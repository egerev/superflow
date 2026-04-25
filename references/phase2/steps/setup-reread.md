# Step: setup-reread

**Stage:** setup
**Loaded by orchestrator:** when entering the setup stage of each sprint
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## What to Re-read at Sprint Start

Re-read in this order:

1. `~/.claude/rules/superflow-enforcement.md` — durable hard rules (survives compaction).
2. `references/phase2/workflow.json` — DAG + decision matrix. Look up
   `decision_matrix.review_config[governance_mode+"+"+complexity]` to get reviewer count, tier,
   and `par_skip_product` for this sprint.
3. The **charter** — path from `context.charter_file` in `.superflow-state.json`.
4. The **specific sprint section** of the plan — extract and paste the exact task list, file paths,
   and expected behaviors verbatim into the implementer prompt. Do NOT rely on LLM memory.
5. This step file and any other step files for the current sprint's stages as needed.

## Skip Files Already in Context

Do NOT re-read a file whose content is visible in the current transcript. Redundant reads burn
context budget monotonically.

## Heartbeat Check

Before any tool call that advances work, check `.superflow-state.json` for a `heartbeat` block.
If `heartbeat.must_reread` lists paths missing from context, Read them immediately (skip missing
paths, warn with one line). If `heartbeat.updated_at` is >30 min old, emit a fresh snapshot.

## Heartbeat Writes

**At sprint start** (immediately after re-reading phase docs, before any other work):

```bash
python3 -c "
import json, datetime, sys, os, tempfile
state_file = '.superflow-state.json'
s = json.load(open(state_file))
hb = s.get('heartbeat', {})
hb['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
hb['current_sprint'] = int(s.get('sprint') or 1)
hb['sprint_goal'] = sys.argv[1]
hb['merge_method'] = 'rebase'
hb['active_worktree'] = sys.argv[2]
hb['active_branch'] = sys.argv[3]
must_reread = [p for p in [
    os.path.expanduser('~/.claude/rules/superflow-enforcement.md'),
    'references/phase2-execution.md',
    s.get('context', {}).get('charter_file') or None,
    'references/phase3-merge.md',
    # only short (<300 line) orchestration files — plan file excluded
] if p]
hb['must_reread'] = must_reread
hb['last_review_verdict'] = hb.get('last_review_verdict', None)
hb['phase2_step'] = 'setup'
s['heartbeat'] = hb
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(state_file) or '.', prefix='.superflow-state.', suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(s, f, indent=2)
os.replace(tmp, state_file)
" \"\$SPRINT_GOAL\" \"\$WORKTREE_PATH\" \"\$BRANCH_NAME\"
# SPRINT_GOAL: one-line sprint description from plan
# WORKTREE_PATH: e.g. .worktrees/sprint-1
# BRANCH_NAME: e.g. feat/feature-sprint-1
```

**At each stage transition** — single atomic write (one `json.dump + os.replace`). Do NOT split into two writes — a crash between them leaves state inconsistent:

```bash
python3 -c "
import json, datetime, sys, os, tempfile
STAGE_INDEXES = {'setup':0,'implementation':1,'review':2,'par':3,'docs':4,'ship':5}
state_file = '.superflow-state.json'
s = json.load(open(state_file))
stage = sys.argv[1]
s['stage'] = stage
s['stage_index'] = STAGE_INDEXES.get(stage, s.get('stage_index', 0))
s['sprint'] = int(sys.argv[2]) if len(sys.argv) > 2 else s.get('sprint', 1)
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
hb = s.get('heartbeat', {})
hb['updated_at'] = s['last_updated']
hb['phase2_step'] = stage
s['heartbeat'] = hb
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(state_file) or '.', prefix='.superflow-state.', suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(s, f, indent=2)
os.replace(tmp, state_file)
" \"\$NEXT_STAGE\" \"\$SPRINT_NUM\"
# NEXT_STAGE: one of setup | implementation | review | par | docs | ship
# SPRINT_NUM: current sprint number (e.g., 1, 2, 3)
# heartbeat.phase2_step is the authoritative source of current stage on resume.
```

**Backward compat:** `.get('heartbeat', {})` creates the key fresh if absent (v4.8 compatibility).

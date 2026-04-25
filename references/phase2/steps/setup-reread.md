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

If a file was Read earlier in this conversation and its content is still visible in the transcript,
do NOT re-read it. Redundant reads burn context budget monotonically. "Already in context" means
the file content appears in the current transcript — not merely that it was read in a prior session.

## Heartbeat Check

Before any tool call that advances work, check `.superflow-state.json` for a `heartbeat` block.
If `heartbeat.must_reread` exists, verify each listed path is already in context. If any are
missing, Read them immediately. Skip paths that do not exist on disk (warn with one line).
If `heartbeat.updated_at` is >30 min old, emit a fresh heartbeat snapshot.

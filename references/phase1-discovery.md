# Phase 1: Product Discovery (COLLABORATIVE)

## Stage Structure

Phase 1 has 5 stages. Use TaskCreate at each stage start, TaskUpdate as todos complete.

```
Stage 1: "Research"
  Todos:
  - "Read project context (CLAUDE.md, llms.txt, docs)"
  - "Dispatch best practices research"
  - "Dispatch product expert research"
  - "Present research findings"

Stage 2: "Brainstorming"
  Todos:
  - "Conduct multi-expert brainstorming (3-5 questions)"
  - "Present approaches with trade-offs"

Stage 3: "Product Approval"
  Todos:
  - "Present Product Summary + Brief for approval"
  - "Get user approval"

Stage 4: "Specification"
  Todos:
  - "Write technical spec"
  - "Dual-model spec review"
  - "Fix review findings"

Stage 5: "Planning"
  Todos:
  - "Write implementation plan"
  - "Dual-model plan review"
  - "Fix review findings"
  - "Get user final approval"
  - "Generate Autonomy Charter"
```

### State Management

At the start of Phase 1, write `.superflow-state.json`:
```bash
cat > .superflow-state.json << STATEEOF
{"version":1,"phase":1,"phase_label":"Product Discovery","stage":"research","stage_index":0,"last_updated":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
STATEEOF
```

After each stage transition, update via python3:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s['stage']='brainstorming'; s['stage_index']=1; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```

### TaskCreate/TaskUpdate Pattern

```
# At the beginning of Stage 1:
TaskCreate(
  title: "Phase 1: Research",
  description: "Read context, dispatch research agents, present findings",
  todos: [
    "Read project context",
    "Dispatch best practices research",
    "Dispatch product expert research",
    "Present research findings"
  ]
)

# As each todo completes:
TaskUpdate(id: <task_id>, todo_updates: [
  {index: 0, status: "completed"}
])

# When stage completes:
TaskUpdate(id: <task_id>, status: "completed")
```

---

## Step 1: Context Exploration
<!-- Stage 1: Research, Todo 1 -->

Read CLAUDE.md, llms.txt, project docs, git history. Understand architecture, data model, existing features. Identify gaps.

## Step 2: Best Practices & Product Research
<!-- Stage 1: Research, Todos 2-3 -->

Dispatch **parallel background research** using the Agent tool (`run_in_background: true` for each):

```
Agent(description: "Domain best practices research", run_in_background: true)
  → domain best practices, relevant libraries, competitor approaches, design patterns

Agent(description: "Independent product expert", run_in_background: true)
  → "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how."
```

If secondary provider is available, use it for the product expert instead:
```bash
$TIMEOUT_CMD 600 $SECONDARY_PROVIDER "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how." 2>&1
```

Wait for all background tasks to complete. If research yields insufficient results for a domain, note the gap — rely on codebase analysis and user input during brainstorming.

> **Reasoning:** Research agents use inline `Agent(model: opus)` dispatch. No `subagent_type` or `effort` — research tasks are ad-hoc and don't require deep reasoning tier.

**NOT optional.** Synthesize findings before proceeding.

## Step 3: Present Research Findings
<!-- Stage 1: Research, Todo 4 -->

Present a brief summary of research results to the user before brainstorming. Include product expert proposals. This ensures the user sees what was discovered and can steer the conversation.

## Step 4: Multi-Expert Brainstorming
<!-- Stage 2: Brainstorming, Todo 1 -->

**STOP GATE — Do NOT proceed past this step without user interaction.**
Your next action MUST be a question or proposal to the user. Do NOT jump to Product Summary.

- Understand WHY and FOR WHOM before WHAT and HOW
- Rhythm: ask 3-5 questions total (one at a time), then concrete proposals, then follow-up questions
- One question per message — wait for answer before the next
- Proposals must be genuinely new (not rephrasing user's own words)
- Three lenses: Product ("users expect X"), Architecture ("data model supports X"), Domain ("best practice is Y")

Use plain text questions (remote-friendly — works via Telegram). List options inline when they're enumerable.

**For priority questions:**
> "What matters most for this feature? (a) Ship fast — MVP first, (b) Get it right — thorough implementation, (c) Keep options open — extensible design"

## Step 5: Approaches + Recommendation
<!-- Stage 2: Brainstorming, Todo 2 -->

Present 2-3 approaches with trade-offs. Lead with recommendation.
For each approach: strengths, risks, effort level.
**Mandatory step** — even if one approach seems obvious, present alternatives. The user must see options before Product Summary.

**For approach selection, ask as plain text:**
> "I see three approaches:
> (a) Approach A: [name] — [1-line tradeoff]
> (b) Approach B: [name] — [1-line tradeoff]
> (c) Approach C: [name] — [1-line tradeoff]
> Which direction? Reply a/b/c or 'details' for more on each."

## Step 6: Product Approval (MERGED GATE)
<!-- Stage 3: Product Approval, Todos 1-2 -->

Present Product Summary + Product Brief together as a single document for approval.

### Product Summary
- What we're building (feature list)
- Problems solved
- NOT in scope
- Key decisions + rationale

### Product Brief
- **Problem statement**: What user pain are we solving? (1-2 sentences)
- **Jobs to be Done**: When [situation], I want to [motivation], so I can [outcome]
- **User stories**: As a [role], I want [action] so that [benefit] (3-5 key stories)
- **Success criteria**: How do we know this worked? (measurable outcomes)
- **Edge cases**: What happens when things go wrong? (happy path + 2-3 failure modes)

Save to `docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md`. Create `docs/superflow/specs/` if it doesn't exist.

This brief is shared with:
1. Spec writers (basis for technical spec)
2. Implementers (context for why, not just what)
3. Reviewers (spec compliance = brief compliance)

Keep it short (< 1 page). No frameworks — just clarity about what we're building and for whom.

If Telegram MCP available, send the Product Summary + Brief as a file attachment before asking for approval:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Product Summary + Brief for approval:", files: ["/abs/path/to/docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md"])
```

**APPROVAL GATE** (plain text — remote-friendly):

> "Does this capture what we're building? Reply **'go'** to proceed to spec, **'fix ...'** to request changes, or **'restart'** to go back to brainstorming."

- "go" / "approve" → proceed to Step 7 (Spec)
- "fix ..." / "changes" → ask what to change, update, re-present
- "restart" → go back to Step 4 (brainstorming)

## Step 7: Spec Document
<!-- Stage 4: Specification, Todo 1 -->

Write to `docs/superflow/specs/YYYY-MM-DD-<topic>-design.md`. Reference the product brief.

Include:
- **Overview**: what is being built (reference brief)
- **Technical design**: architecture, data model changes, API contracts
- **File-level changes**: which files are modified/created
- **Edge cases and error handling**: from the brief's edge cases
- **Testing strategy**: what tests validate correctness
- **Out of scope**: explicit boundaries

Create `docs/superflow/specs/` if it doesn't exist.

## Step 8: Spec Review (dual-model parallel)
<!-- Stage 4: Specification, Todos 2-3 -->

Run two reviewers in parallel. Both reviewers receive the product brief AND the spec.

1. **Claude reviewer (PRODUCT lens)**: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review this spec for product completeness, scope alignment, user story coverage. Spec: [SPEC TEXT]")`. Focus: product completeness, scope alignment, user story coverage.
2. **Secondary provider (TECHNICAL lens)**: `$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=high --ephemeral "Spec review. Check completeness, security, architecture against: [SPEC TEXT]" 2>&1` via Bash (`run_in_background: true`).
   No secondary provider = split-focus Claude: Product (`deep-product-reviewer`) + Technical (`deep-spec-reviewer`).

> **Reasoning:** Spec review is high-stakes but `xhigh` reasoning was overkill — `high` is sufficient for catching real issues without excessive latency.

Wait for both. If either returns NEEDS_REVISION: fix issues, re-run both reviews.
Both must return PASS to proceed.

## Step 9: Implementation Plan
<!-- Stage 5: Planning, Todo 1 -->

Write to `docs/superflow/plans/YYYY-MM-DD-<topic>.md`. Create `docs/superflow/plans/` if it doesn't exist.

Break into sprints (independently deployable), 3-8 tasks each, each task 2-5 min. Include: files, steps, commit message.

## Step 10: Plan Review (dual-model parallel)
<!-- Stage 5: Planning, Todos 2-3 -->

Run two reviewers in parallel (same mechanism as Step 8):

1. **Claude reviewer (PRODUCT lens)**: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "Review this plan for product feasibility, scope correctness, user value alignment. Plan: [PLAN TEXT]")`. Does the plan deliver user value? Is scope correct? Are priorities aligned with the brief?
2. **Secondary provider (TECHNICAL lens)**: `$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=high --ephemeral "Plan review. Check achievability, scoping, dependencies against: [PLAN TEXT]" 2>&1` via Bash (`run_in_background: true`). Are there missing tasks? Over-engineering? Does sprint ordering make sense?
   No secondary provider = split-focus Claude: Product (`standard-product-reviewer`) + Technical (`standard-spec-reviewer`).

> **Reasoning:** Standard tier — plan review checks structure and feasibility, not deep architectural decisions.

Both must APPROVE. If either returns NEEDS_REVISION: fix, re-review.

## Step 11: User Approval (FINAL GATE)
<!-- Stage 5: Planning, Todo 4 -->

Present:
- Sprint breakdown with task counts
- Estimated PR count (1 per sprint)
- Merge order and dependencies

If Telegram MCP available, send the implementation plan as a file attachment before asking for final approval:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Implementation plan for final approval:", files: ["/abs/path/to/docs/superflow/plans/YYYY-MM-DD-<topic>.md"])
```

**FINAL GATE:** Ask the user: "Ready to start autonomous execution? Say 'go' when ready."
- User says "go" / "start" / "давай" / affirmative → proceed to auto-launch flow below
- User requests changes → update plan, re-present

## Step 12: Generate Autonomy Charter
<!-- Stage 5: Planning, Todo 5 -->

After user approval and before auto-launch, generate an Autonomy Charter from the brief, spec, and plan:

**Charter structure** (YAML frontmatter + Markdown body):

```yaml
---
goal: "One-sentence Goal from the brief"
non_negotiables:
  - "Hard constraint 1 (from spec/plan boundaries)"
  - "Hard constraint 2"
success_criteria:
  - "Measurable outcome 1 (from brief success criteria)"
  - "Measurable outcome 2"
governance_mode: "supervised"
---
```

**Body:** Free-form notes on scope boundaries, forbidden approaches, or risk areas.

Save to `docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`. Update `.superflow-state.json` context with `charter_file` path. Also set `charter_file` in the sprint queue's `metadata` dict so the supervisor can inject it into sprint prompts.

The charter is injected into every sprint prompt, reviewer context, and replanner prompt — serving as the single source of truth for what the autonomous executor is and isn’t allowed to do.

**Auto-launch flow (primary path):**

**1. Pre-launch check** — verify supervisor is not already running or crashed:
```bash
python3 -c "from lib.launcher import get_status; s=get_status('.'); print(f'alive={s.alive} crashed={s.crashed} sprint={s.sprint}')"
```
- If alive: show current status and enter dashboard mode. Do not re-launch.
- If crashed: offer restart (`restart()` calls `resume()` to recover in-progress sprints, then relaunches). Do NOT regenerate the queue — it would overwrite completed sprint state.

**2. Generate sprint queue** from the approved plan:
```bash
python3 -c "
from lib.planner import plan_to_queue, save_queue
q = plan_to_queue('PLAN_PATH', 'FEATURE')
save_queue(q, 'docs/superflow/sprint-queue.json')
print(f'{len(q[\"sprints\"])} sprints queued')
"
```
Replace `PLAN_PATH` with the actual plan file path (e.g. `docs/superflow/plans/YYYY-MM-DD-feature.md`) and `FEATURE` with the feature name.

**3. Confirm launch** — ask the user (plain text, remote-friendly):
> "Ready to start. N sprints queued. Launch supervisor in background? (yes/no)"

**4. On yes — launch supervisor:**
```bash
python3 -c "
from lib.launcher import launch
r = launch('docs/superflow/sprint-queue.json', 'PLAN_PATH', '.')
print(f'PID {r.pid}, log: {r.log_path}')
"
```
Show launch receipt: PID, log path, sprint count. Update `.superflow-state.json` to phase=2.

**5. If launch fails** — show the error message and first 20 lines of the log file, then offer:
> "Launch failed. Check the log above. Fix the issue and say 'retry', or say 'manual' to fall back to the manual path."

**6. Enter dashboard mode** — transition to Phase 2 dashboard: poll supervisor status every 30 seconds, surface sprint transitions and errors as they happen.

---

**Fallback path (if user says "no" to launch, or on repeated launch failure):**

After Phase 1 the context window is heavily loaded with brainstorming history, review findings, and intermediate drafts. Phase 2 is a different mode (autonomous manager) and benefits from a clean start.

1. Verify `.superflow-state.json` has phase=2 and plan/spec file paths in context
2. Tell the user:
   > "Plan approved. Phase 2 needs a fresh context for best quality.
   > Run `/clear` then `/superflow` — it will pick up from Phase 2 automatically."
3. Do NOT proceed to Phase 2 in the same session

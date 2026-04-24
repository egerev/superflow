# Phase 1: Product Discovery (COLLABORATIVE)

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

## Stage Structure

Phase 1 has 5 stages. Use TaskCreate at each stage start, TaskUpdate as todos complete.

```
Stage 1: "Research"
  Todos:
  - "Read project context (CLAUDE.md, llms.txt, docs)"
  - "Governance mode selection"
  - "Dispatch best practices research (skip in light mode)"
  - "Dispatch product expert research (skip in light mode)"
  - "Present research findings"

Stage 2: "Brainstorming"
  Todos:
  - "Dispatch expert panel, synthesize Board Memo"
  - "User reaction + direction lock"
  - "Design-tree grilling (critical by default, standard opt-in, light skip)"

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

At the start of Phase 1, merge-update `.superflow-state.json` (preserves `context.*` from Phase 0):
```bash
python3 -c "
import json, datetime, os
p = '.superflow-state.json'
s = json.load(open(p)) if os.path.exists(p) else {}
s.update({'version':1,'phase':1,'phase_label':'Product Discovery','stage':'research','stage_index':0,'last_updated':datetime.datetime.now(datetime.timezone.utc).isoformat()})
json.dump(s, open(p,'w'), indent=2)
"
sf_emit phase.start phase:int=1 label="Discovery"
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

```bash
sf_emit stage.start stage=research phase:int=1
```

## Step 1: Context Exploration
<!-- Stage 1: Research, Todo 1 -->

Read CLAUDE.md, llms.txt, project docs, git history. Understand architecture, data model, existing features. Identify gaps.

Read `context.tech_debt` from `.superflow-state.json` (if present). Surface: files >500 LOC, security issues, untested modules. Use these as inputs for brainstorming and spec — they represent known weaknesses from Phase 0 analysis.

## Step 2: Governance Mode Selection
<!-- Stage 1: Research, Todo 2 -->

Assess the task along three dimensions and auto-suggest a governance mode:

| Dimension | Low | Medium | High |
|-----------|-----|--------|------|
| **Novelty** | Bug fix, config change, well-understood pattern | New feature using existing patterns | New architecture, unfamiliar domain |
| **Blast radius** | 1-2 files | 3-10 files | 10+ files, cross-module |
| **Ambiguity** | Clear requirements, obvious solution | Some open questions | Significant unknowns, multiple valid approaches |

**Scoring:**
- All low → **light**
- Any high → **critical**
- Otherwise → **standard**

Present the assessment with reasoning:
> "This looks like a **[light/standard/critical]** task because [reasoning based on dimensions]. Use this mode? (yes / override to light/standard/critical)"

Wait for confirmation. Store the selected mode in `.superflow-state.json`:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s.setdefault('context',{})['governance_mode']='MODE'; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```
Replace `MODE` with `light`, `standard`, or `critical`.

### Mode Behavior Reference

| Aspect | Light | Standard | Critical |
|--------|-------|----------|----------|
| **Research agents** | Skip (Step 3) | Full (2 parallel agents) | Full + security research agent |
| **Brainstorming** | 1 round-trip max | 3-5 questions | 3-5 questions + extended debate round |
| **Design-tree grilling** (Step 6a) | Skip | Opt-in (user says yes) | On by default |
| **Spec** | Inline in charter (brief + spec + plan in one doc) | Separate spec file | Separate spec + threat model section |
| **Spec review** | Skip | Dual-model (Product + Technical) | Dual-model (Product + Technical) |
| **Plan review** | Single Claude reviewer | Dual-model (Product + Technical) | Deep-tier dual-model review |
| **Charter** | Includes inline spec + plan (generated via `charter_to_queue()`) | Separate file, references spec/plan | Separate file, references spec/plan |

## Step 2b: Git Workflow Mode Selection
<!-- Stage 1: Research, Todo 2 -->

Read `references/git-workflow-modes.md`. Select a git workflow based on task shape, repo practices, team context, CI maturity, sprint dependency graph, and user preference. Do not assume solo always means one PR; disjoint solo work can still benefit from `parallel_wave_prs`, and dependent team work can benefit from `stacked_prs`.

Available modes:
- `solo_single_pr` — one feature branch, one final PR; default for small-to-medium coherent solo/vibe-coding work.
- `sprint_pr_queue` — one branch/PR per sprint from `main`; default for team, critical, or audit-heavy work.
- `stacked_prs` — sprint branches stack on previous sprint branches; best for dependent multi-sprint changes.
- `parallel_wave_prs` — independent sprint branches from `main`; best for disjoint files/modules and parallel agent/team work.
- `trunk_based` — short-lived branches and feature flags; use when the project already works this way.

Present the recommendation with reasoning:
> "Recommended git workflow: **[mode]** because [dependency/PR/CI/team reasoning]. Use this mode? (yes / override to solo_single_pr/sprint_pr_queue/stacked_prs/parallel_wave_prs/trunk_based)"

Wait for confirmation. Store the selected mode in `.superflow-state.json`:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s.setdefault('context',{})['git_workflow_mode']='MODE'; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```
Replace `MODE` with the selected git workflow mode.

### Conditional Flow by Mode

- **Light mode**: Skip Step 3 (research) → 1 round-trip brainstorm (Step 5) → Skip Step 6a (grilling) → Product Approval (Step 7) → Write inline charter with brief+spec+plan (Step 13) → Skip spec review (Step 9) → Single Claude plan reviewer (Step 11) → User Approval (Step 12) → Generate queue via `charter_to_queue()` from charter body
- **Standard mode**: Full flow as documented. Step 6a (design-tree grilling) offered as opt-in after direction lock.
- **Critical mode**: Full flow + dispatch security research agent in Step 3 + run Step 6a (design-tree grilling) by default + add threat model section to spec in Step 8 + use deep-tier reviewers in Steps 9 and 11

### Light Mode Sprint Breakdown

In light mode, the charter body contains the sprint breakdown directly. Charter sprint headings use the format: `## Sprint N: Title [complexity: X]`. The sprint plan is derived from the charter — no separate plan file needed.

## Step 3: Best Practices & Product Research
<!-- Stage 1: Research, Todos 3-4 -->

**Skip this step in light mode** — proceed directly to Step 5 (Brainstorming).

Dispatch **parallel background research** using the Agent tool (`run_in_background: true` for each).
Emit dispatch/complete pairs around each agent (repeat per agent, substituting role/task/model):

```bash
# Pattern for research agents (repeat per agent):
AGENT_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
SF_PARENT_ID="$AGENT_ID" sf_emit agent.dispatch agent_type=research-agent task="Phase 1: domain best practices research" model=opus
# Agent() call here (run_in_background: true)
# After agent returns:
sf_emit agent.complete role=research-agent agent_id="$AGENT_ID"
```

```
Agent(model: opus, description: "Domain best practices research", run_in_background: true)
  → domain best practices, relevant libraries, competitor approaches, design patterns

Agent(model: opus, description: "Independent product expert", run_in_background: true)
  → "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how."
```

If secondary provider is available, use it for the product expert instead:
```bash
$TIMEOUT_CMD 600 $SECONDARY_PROVIDER "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how." 2>&1
```

Wait for all background tasks to complete. If research yields insufficient results for a domain, note the gap — rely on codebase analysis and user input during brainstorming.

> **Reasoning:** Research agents use inline `Agent(model: opus)` dispatch with no `subagent_type`. Effort is not specified — inherits session default (medium). Sufficient for fact-gathering; deep reasoning not needed here.

**NOT optional.** Synthesize findings before proceeding.

## Step 4: Present Research Findings
<!-- Stage 1: Research, Todo 5 -->

Present a brief summary of research results to the user before brainstorming. Include product expert proposals. This ensures the user sees what was discovered and can steer the conversation.

```bash
sf_emit stage.end stage=research phase:int=1
sf_emit stage.start stage=brainstorming phase:int=1
```

## Step 5: Multi-Expert Brainstorming
<!-- Stage 2: Brainstorming, Todo 1 -->

Dispatch 3-4 parallel background agents, each with a distinct expert persona. Use the prompt template from `prompts/expert-panel.md`, filling in `{project_context}` (CLAUDE.md + llms.txt content), `{tech_debt}` (Phase 0 tech_debt findings), `{user_problem}` (user's initial description), and `{research}` (Step 2-3 findings).

| Agent | Persona | Focus |
|-------|---------|-------|
| Product GM | "What would users love?" | User pain, adoption, competitive edge |
| Staff Engineer | "What's the right technical foundation?" | Architecture, scalability, maintenance |
| UX/Workflow Expert | "How does this feel to use?" | Interaction flow, remote UX, cognitive load |
| Domain Expert | "What does the industry do?" | Best practices, standards, prior art |

Dispatch all in parallel. Emit dispatch/complete pairs around each agent (repeat per agent, substituting persona/focus):

```bash
# Pattern for expert panel agents (repeat per agent):
AGENT_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
SF_PARENT_ID="$AGENT_ID" sf_emit agent.dispatch agent_type=expert-panel task="Phase 1: Product GM brainstorm" model=opus
# Agent() call here (run_in_background: true)
# After agent returns:
sf_emit agent.complete role=expert-panel agent_id="$AGENT_ID"
```

```
Agent(model: opus, effort: high, description: "Product GM expert panel", run_in_background: true)
  → use prompts/expert-panel.md with persona="Product GM", focus="User pain, adoption, competitive edge"

Agent(model: opus, effort: high, description: "Staff Engineer expert panel", run_in_background: true)
  → use prompts/expert-panel.md with persona="Staff Engineer", focus="Architecture, scalability, maintenance"

Agent(model: opus, effort: high, description: "UX/Workflow Expert expert panel", run_in_background: true)
  → use prompts/expert-panel.md with persona="UX/Workflow Expert", focus="Interaction flow, remote UX, cognitive load"
```

If secondary provider is available, use it for the Domain Expert instead of a fourth Agent:
```bash
$TIMEOUT_CMD 600 $SECONDARY_PROVIDER "[paste expert-panel.md with persona=Domain Expert filled in]" 2>&1
```

Otherwise dispatch as a fourth Agent:
```
Agent(model: opus, effort: high, description: "Domain Expert expert panel", run_in_background: true)
  → use prompts/expert-panel.md with persona="Domain Expert", focus="Best practices, standards, prior art"
```

Wait for all agents to complete before proceeding.

## Step 5: Synthesize Board Memo
<!-- Stage 2: Brainstorming, Todo 1 (continued) -->

Orchestrator synthesizes all expert outputs into a single Board Memo. Present to the user as one message:

```
## Board Memo: [Feature Name]

### Consensus — where all experts agree
[Points all experts converged on]

### Disagreements — where experts diverge
[Each expert's distinct position on contested points]

### Risks Identified
[Challenges each expert raised, especially "challenge" sections]

### Recommended Direction
[Synthesized recommendation based on expert consensus + disagreements]

### Decisions Needed From You
[1-2 questions requiring human judgment — direction choices the experts couldn't resolve]
```

This replaces 3-5 sequential questions. The user gets the full picture in one message and can react once.

**STOP GATE — Do NOT proceed to Step 6 without user reaction.**

## Step 6: User Reaction + Direction Lock
<!-- Stage 2: Brainstorming, Todo 2 -->

After user reacts to the Board Memo:

- **User picks a direction** → offer optional Devil's Advocate: "Want me to challenge this direction? (yes/skip)"
  - If yes: argue against the chosen direction — steelman the alternatives. Then confirm direction.
  - If skip: lock the direction and proceed.
- **User has questions** → answer, re-present the relevant Board Memo section, confirm direction.
- **User has their own ideas** → integrate into the proposal, update Recommended Direction, confirm.

Target: 2-3 round-trips for direction lock. Deep design-tree resolution happens in Step 6a, not here — don't extend Step 6 into a 7-question interview.

**Approaches presentation:**

- If expert panel converged on one approach: present as recommendation with "Alternatives Considered" sidebar.
- If experts genuinely disagreed: present full multi-approach comparison (2-3 options, strengths/risks/effort each), ask for direction.

**For approach selection, ask as plain text:**
> "I see three approaches:
> (a) Approach A: [name] — [1-line tradeoff]
> (b) Approach B: [name] — [1-line tradeoff]
> (c) Approach C: [name] — [1-line tradeoff]
> Which direction? Reply a/b/c or 'details' for more on each."

## Step 6a: Design-Tree Grilling (AskUserQuestion)
<!-- Stage 2: Brainstorming, Todo 3 -->

After direction is locked, walk down the design tree and resolve contested decisions one-by-one using `AskUserQuestion`. Each answer unlocks the next branch — don't batch unrelated questions into one Board-Memo-style message.

### When to run

| Mode | Behavior |
|----------|----------|
| **light** | Skip entirely — proceed to Step 7. |
| **standard** | Offer: *"Want me to grill you on the open design decisions? (yes/skip)"* — run only on yes. Mirrors the Devil's Advocate opt-in pattern. |
| **critical** | Run by default. Announce: *"Running design-tree grilling — I'll ask one decision at a time until the tree is resolved."* User can interrupt with "skip" / "хватит" at any point. |

### How to run

1. Enumerate open decisions from the Board Memo's **Disagreements** + **Risks** sections. List them as a dependency tree: prerequisite decisions first (e.g. storage before schema, transport before auth).
2. Walk the tree depth-first. For each decision, fire a single `AskUserQuestion` with 2-4 concrete options + short tradeoff per option. Never ask more than one decision per turn.
3. After each answer: update the in-memory decision log, prune downstream branches that became moot, pick the next unresolved node.
4. Stop when: the tree is fully resolved, or user says "enough" / "skip rest" / "хватит". Record unresolved nodes as open questions carried into the spec.

### Output

Before proceeding to Step 7, summarize resolved decisions inline:

```
### Design decisions locked
- [Decision]: [chosen option] — [one-line rationale]
- ...
### Carried to spec as open questions
- [Unresolved node, if any]
```

This summary is merged into the Product Summary in Step 7, so the user sees every locked decision before the Product Approval gate.

> **Reasoning:** Board Memo gives the panoramic view; grilling gives the depth. Running it by default in critical mode reduces spec-review churn because contested technical decisions are already resolved with user input before the spec writer starts.

```bash
sf_emit stage.end stage=brainstorming phase:int=1
sf_emit stage.start stage=product-approval phase:int=1
```

## Step 7: Product Approval (MERGED GATE)
<!-- Stage 3: Product Approval, Todos 1-2 -->

**CRITICAL: Display the full content inline in the chat before asking for approval.** The user must SEE what they're approving — this is the last meaningful approval gate before autonomous execution.

Write the Product Summary + Product Brief, then **output it in full as a chat message** (not just save to file). Structure:

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

After displaying, save to `docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md`. Create `docs/superflow/specs/` if it doesn't exist.

After saving the brief, persist its path to state:
```bash
python3 -c "import json,datetime; s=json.load(open('.superflow-state.json')); s.setdefault('context',{})['brief_file']='docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md'; s['last_updated']=datetime.datetime.now(datetime.timezone.utc).isoformat(); json.dump(s,open('.superflow-state.json','w'),indent=2)"
```
Replace `YYYY-MM-DD-<topic>` with the actual filename used above.

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

- "go" / "approve" → proceed to Step 8 (Spec)
- "fix ..." / "changes" → ask what to change, update, re-present
- "restart" → go back to Step 5 (brainstorming)
- User abandons / explicitly cancels Phase 1:
  ```bash
  sf_emit run.end status=blocked
  ```

```bash
sf_emit stage.end stage=product-approval phase:int=1
sf_emit stage.start stage=spec phase:int=1
```

## Step 8: Spec Document
<!-- Stage 4: Specification, Todo 1 -->

Write to `docs/superflow/specs/YYYY-MM-DD-<topic>-design.md`. Reference the product brief.

Include:
- **Overview**: what is being built (reference brief)
- **Technical design**: architecture, data model changes, API contracts
- **File-level changes**: which files are modified/created
- **Edge cases and error handling**: from the brief's edge cases
- **Testing strategy**: what tests validate correctness
- **Out of scope**: explicit boundaries

**Tech debt cross-reference (after writing the spec):** Once file-level changes are defined, re-read `context.tech_debt` from `.superflow-state.json` and the project's CLAUDE.md "Known Issues & Tech Debt" section. Cross-reference with the files listed in the spec. If any tech debt item touches the same modules/files:
- Surface it to the user: "This spec modifies [module X]. There's planned tech debt: [description]. Including it now would be efficient since we're already changing these files. Add to scope?"
- Wait for user decision before finalizing
- If accepted, add a **Tech debt resolution** section to the spec with the accepted items

Create `docs/superflow/specs/` if it doesn't exist.

## Step 9: Spec Review (dual-model parallel)
<!-- Stage 4: Specification, Todos 2-3 -->

Run two reviewers in parallel. Both reviewers receive the product brief AND the spec.

```bash
sf_emit review.start reviewer=product target="spec"
sf_emit review.start reviewer=technical target="spec"
```

1. **Claude reviewer (PRODUCT lens)**: `Agent(subagent_type: "deep-product-reviewer", run_in_background: true, prompt: "Review this spec for product completeness, scope alignment, user story coverage. Spec: [SPEC TEXT]")`. Focus: product completeness, scope alignment, user story coverage.
2. **Secondary provider (TECHNICAL lens)**: `$TIMEOUT_CMD 600 codex exec --full-auto -m gpt-5.5 -c model_reasoning_effort=high --ephemeral "Spec review. Check completeness, security, architecture against: [SPEC TEXT]" 2>&1` via Bash (`run_in_background: true`).
   No secondary provider = split-focus Claude: Product (`deep-product-reviewer`) + Technical (`deep-spec-reviewer`).

> **Reasoning:** Spec review is high-stakes but `xhigh` reasoning was overkill — `high` is sufficient for catching real issues without excessive latency.

Wait for both. If either returns NEEDS_REVISION: fix issues, re-run both reviews.
Both must return PASS to proceed.

```bash
# VERDICT: one of APPROVE, ACCEPTED, PASS, FAIL, NEEDS_FIXES, REQUEST_CHANGES
sf_emit review.verdict reviewer=product verdict="$VERDICT"
sf_emit review.verdict reviewer=technical verdict="$VERDICT"
```

```bash
sf_emit stage.end stage=spec phase:int=1
sf_emit stage.start stage=plan phase:int=1
```

## Step 10: Implementation Plan
<!-- Stage 5: Planning, Todo 1 -->

Write to `docs/superflow/plans/YYYY-MM-DD-<topic>.md`. Create `docs/superflow/plans/` if it doesn't exist.

If the spec includes a "Tech Debt Resolution" section, allocate a dedicated sprint (or tasks within a sprint) for the tech debt work. Don't silently mix tech debt fixes into feature tasks — keep them traceable.

Break into sprints (independently deployable), 3-8 tasks each, each task 2-5 min. Include: files, steps, commit message.

Read `context.git_workflow_mode` from `.superflow-state.json` and shape the plan for that mode:
- `solo_single_pr`: keep sprint boundaries as internal checkpoints; estimated PR count is 1.
- `sprint_pr_queue`: each sprint must be independently reviewable and mergeable into `main`.
- `stacked_prs`: each sprint may depend on earlier sprint branches; call out stack order explicitly.
- `parallel_wave_prs`: only place sprints in the same wave when they have no file overlap, state dependency, or ordering dependency.
- `trunk_based`: keep slices small and note any feature flags or disabled-by-default paths.

**Sprint parallelism metadata (required):** For each sprint, include:
- `files:` — list of files this sprint modifies/creates
- `depends_on:` — list of sprint numbers this sprint depends on (empty = independent)

Example:
```
## Sprint 1: Backend API [complexity: medium]
files: src/api/routes.py, src/api/handlers.py, tests/test_api.py
depends_on: []

## Sprint 2: Frontend UI [complexity: medium]
files: src/components/Dashboard.tsx, src/hooks/useApi.ts
depends_on: []

## Sprint 3: Integration tests [complexity: simple]
files: tests/test_integration.py
depends_on: [1, 2]
```

The orchestrator uses this to build a sprint dependency graph and dispatch independent sprints in parallel waves. Sprints with no file overlap and no `depends_on` run concurrently in the same wave.

## Step 11: Plan Review (dual-model parallel)
<!-- Stage 5: Planning, Todos 2-3 -->

Run two reviewers in parallel (same mechanism as Step 8):

```bash
sf_emit review.start reviewer=product target="plan"
sf_emit review.start reviewer=technical target="plan"
```

1. **Claude reviewer (PRODUCT lens)**: `Agent(subagent_type: "standard-product-reviewer", run_in_background: true, prompt: "Review this plan for product feasibility, scope correctness, user value alignment. Plan: [PLAN TEXT]")`. Does the plan deliver user value? Is scope correct? Are priorities aligned with the brief?
2. **Secondary provider (TECHNICAL lens)**: `$TIMEOUT_CMD 600 codex exec --full-auto -m gpt-5.5 -c model_reasoning_effort=high --ephemeral "Plan review. Check achievability, scoping, dependencies against: [PLAN TEXT]" 2>&1` via Bash (`run_in_background: true`). Are there missing tasks? Over-engineering? Does sprint ordering make sense?
   No secondary provider = split-focus Claude: Product (`standard-product-reviewer`) + Technical (`standard-spec-reviewer`).

> **Reasoning:** Standard tier — plan review checks structure and feasibility, not deep architectural decisions.

Both must APPROVE. If either returns NEEDS_REVISION: fix, re-review.

```bash
# VERDICT: one of APPROVE, ACCEPTED, PASS, FAIL, NEEDS_FIXES, REQUEST_CHANGES
sf_emit review.verdict reviewer=product verdict="$VERDICT"
sf_emit review.verdict reviewer=technical verdict="$VERDICT"
```

```bash
sf_emit stage.end stage=plan phase:int=1
sf_emit stage.start stage=user-approval phase:int=1
```

## Step 12: User Approval (FINAL GATE)
<!-- Stage 5: Planning, Todo 4 -->

**CRITICAL: Display the full plan summary inline in the chat.** The user must see what they're approving before autonomous execution begins.

Present the complete plan overview:
- Sprint breakdown with task counts and complexity tags
- Key files touched per sprint
- Selected git workflow mode and why it fits this task
- **Sprint wave plan** — show which sprints run in parallel:
  ```
  Wave 1: [Sprint 1, Sprint 2, Sprint 6] — parallel (independent files)
  Wave 2: [Sprint 3, Sprint 4, Sprint 5] — parallel (depends on Wave 1)
  Estimated speedup: 6 sprints → 2 waves
  ```
- Estimated PR count based on git workflow mode
- Merge order and dependencies
- Total scope (number of sprints, number of waves, estimated changes)

If Telegram MCP available, send the implementation plan as a file attachment before asking for final approval:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Implementation plan for final approval:", files: ["/abs/path/to/docs/superflow/plans/YYYY-MM-DD-<topic>.md"])
```

**FINAL GATE:** Ask the user: "Ready to start autonomous execution? Say 'go' when ready."
- User says "go" / "start" / "давай" / affirmative → proceed to auto-launch flow below
- User requests changes → update plan, re-present

```bash
sf_emit stage.end stage=user-approval phase:int=1
sf_emit stage.start stage=charter phase:int=1
```

## Step 13: Generate Autonomy Charter
<!-- Stage 5: Planning, Todo 5 -->

After user approval and before auto-launch, generate an Autonomy Charter from the brief, spec, and plan. Include the selected governance mode from Step 2 and git workflow mode from Step 2b:

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
governance_mode: "light|standard|critical"  # from Step 2 selection
git_workflow_mode: "solo_single_pr|sprint_pr_queue|stacked_prs|parallel_wave_prs|trunk_based"  # from Step 2b selection
---
```

**Body:** Free-form notes on scope boundaries, forbidden approaches, risk areas, and branch/PR policy for the selected git workflow mode.

Save to `docs/superflow/specs/YYYY-MM-DD-<topic>-charter.md`. Update `.superflow-state.json` context with `charter_file` path.

**CRITICAL: Display the charter inline in the chat.** This is the final summary of everything decided in Phase 1 — the user must see exactly what constraints will govern autonomous execution. Show the full charter (goal, non-negotiables, success criteria, governance mode, and body notes).

The charter is injected into every sprint prompt and reviewer context — serving as the single source of truth for what the autonomous executor is and isn’t allowed to do.

After displaying the charter and confirming with the user, transition to Phase 2. The context window is heavily loaded with brainstorming history, review findings, and intermediate drafts. Phase 2 is a different mode (autonomous manager) and benefits from a clean start.

1. Update `.superflow-state.json` to phase=2, verify plan/spec/charter file paths in context
2. Tell the user:
   > "Plan approved. Phase 2 needs a fresh context for best quality.
   > Run `/clear` then `/superflow` — it will pick up from Phase 2 automatically."
```bash
sf_emit stage.end stage=charter phase:int=1
sf_emit phase.end phase:int=1 label="Discovery"
```

3. Do NOT proceed to Phase 2 in the same session

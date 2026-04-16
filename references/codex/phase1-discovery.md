# Phase 1: Product Discovery — Codex Dispatch Overlay

> For workflow logic (stages, gates, governance modes, charter generation), read the main file: `references/phase1-discovery.md`.

## Dispatch Points

### Step 3: Best Practices & Product Research (skip in light mode)

Two parallel research agents:

1. Use spawn_agent to dispatch "deep-analyst" with task: "Domain best practices research for [project]. Research relevant libraries, competitor approaches, design patterns."

2. **Claude as secondary** for product expert:
   ```bash
   $TIMEOUT_CMD 600 claude -p "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how." 2>&1
   ```

   If Claude unavailable, use spawn_agent to dispatch a second "deep-analyst" for product expert research.

### Step 5: Multi-Expert Brainstorming (3-4 parallel agents)

Use spawn_agent for each expert persona (read `prompts/expert-panel.md` for the prompt template):

1. spawn_agent("deep-analyst") — Product GM persona
2. spawn_agent("deep-analyst") — Staff Engineer persona
3. spawn_agent("deep-analyst") — UX/Workflow Expert persona

**Claude as secondary** for Domain Expert:
```bash
$TIMEOUT_CMD 600 claude -p "[expert-panel.md with persona=Domain Expert filled in]" 2>&1
```

If Claude unavailable, dispatch 4th spawn_agent("deep-analyst") for Domain Expert.

Wait for all agents before synthesizing Board Memo.

### Step 9: Spec Review (dual-model, skip in light mode)

Two reviewers in parallel:

1. **Codex product reviewer:** Use spawn_agent to dispatch "deep-product-reviewer" with:
   "Review this spec for product completeness, scope alignment, user story coverage. Spec: [SPEC TEXT]"

2. **Claude technical reviewer:**
   ```bash
   $TIMEOUT_CMD 600 claude -p "Spec review. Check completeness, security, architecture against: [SPEC TEXT]. $(cat prompts/claude/code-reviewer.md)" 2>&1
   ```

No Claude → split-focus: spawn_agent("deep-product-reviewer") + spawn_agent("deep-spec-reviewer").

### Step 11: Plan Review (dual-model)

1. **Codex product reviewer:** spawn_agent("standard-product-reviewer") — feasibility, scope, user value
2. **Claude technical reviewer:**
   ```bash
   $TIMEOUT_CMD 600 claude -p "Plan review. Check achievability, scoping, dependencies against: [PLAN TEXT]. $(cat prompts/claude/code-reviewer.md)" 2>&1
   ```

No Claude → split-focus: spawn_agent("standard-product-reviewer") + spawn_agent("standard-spec-reviewer").

## TaskCreate Replacement

```bash
printf "Phase 1 Stage N: [description]...\n"
```

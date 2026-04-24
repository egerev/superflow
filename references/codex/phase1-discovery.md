# Phase 1: Product Discovery — Codex Dispatch Overlay

> For workflow logic (stages, gates, governance modes, git workflow modes, charter generation), read the main file: `references/phase1-discovery.md`.

## Dispatch Points

### Step 2b: Git Workflow Mode Selection

No dispatch change. Read `references/git-workflow-modes.md`, recommend a mode, wait for user confirmation, and persist `context.git_workflow_mode` exactly as the main Phase 1 doc specifies.

### Step 3: Best Practices & Product Research (skip in light mode)

Two parallel research agents:

1. Use spawn_agent to dispatch "deep-analyst" with task: "Domain best practices research for [project]. Research relevant libraries, competitor approaches, design patterns."

2. **Claude as secondary** for product expert:
   ```bash
   $TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "Analyze [project]. Propose 3-5 concrete product improvements. For each: what, why, how." 2>&1
   ```

   If Claude unavailable, use spawn_agent to dispatch a second "deep-analyst" for product expert research.

### Step 5: Multi-Expert Brainstorming (3-4 parallel agents)

Use spawn_agent for each expert persona (read `prompts/expert-panel.md` for the prompt template):

1. spawn_agent("deep-analyst") — Product GM persona
2. spawn_agent("deep-analyst") — Staff Engineer persona
3. spawn_agent("deep-analyst") — UX/Workflow Expert persona

**Claude as secondary** for Domain Expert:
```bash
$TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "[expert-panel.md with persona=Domain Expert filled in]" 2>&1
```

If Claude unavailable, dispatch 4th spawn_agent("deep-analyst") for Domain Expert.

Wait for all agents before synthesizing Board Memo.

### Step 9: Spec Review (dual-model, skip in light mode)

Two reviewers in parallel:

1. **Claude Opus 4.7 product reviewer:**
   ```bash
   $TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "Review this spec for product completeness, scope alignment, user story coverage. $(cat prompts/claude/product-reviewer.md)

   PRODUCT BRIEF: [BRIEF TEXT]
   SPEC: [SPEC TEXT]" 2>&1
   ```

2. **Codex technical reviewer:** Use spawn_agent to dispatch "deep-spec-reviewer" with:
   "Spec review. Check completeness, security, architecture against: [SPEC TEXT]."

No Claude → split-focus: spawn_agent("deep-product-reviewer") + spawn_agent("deep-spec-reviewer").

### Step 11: Plan Review (dual-model)

1. **Claude Opus 4.7 product reviewer:**
   ```bash
   $TIMEOUT_CMD 600 claude --model claude-opus-4-7 --effort xhigh -p "Review this plan for product feasibility, scope correctness, user value alignment. $(cat prompts/claude/product-reviewer.md)

   PRODUCT BRIEF: [BRIEF TEXT]
   PLAN: [PLAN TEXT]" 2>&1
   ```

2. **Codex technical reviewer:** spawn_agent("standard-spec-reviewer") — achievability, scoping, dependencies, sprint ordering

No Claude → split-focus: spawn_agent("standard-product-reviewer") + spawn_agent("standard-spec-reviewer").

## TaskCreate Replacement

```bash
printf "Phase 1 Stage N: [description]...\n"
```

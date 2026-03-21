---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Two phases: (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, Codex reviews, max parallelism."
---

# SuperFlow — Product-to-Production Workflow

Two distinct phases: collaborative discovery, then autonomous execution.

```
Phase 1: COLLABORATIVE (with user)
  Product Discovery → Multi-Expert Brainstorming → Spec → Plan

Phase 2: AUTONOMOUS (no stops until done)
  Sprint 1 → PR #1
  Sprint 2 → PR #2
  ...
  Sprint N → PR #N
  → Report to user: "Done. N PRs ready for review."
```

---

## CRITICAL RULES

### Rule 1: NEVER pause during autonomous execution
After user says "go" / "ок" / "давай" on the approved plan — ZERO stops, ZERO questions, ZERO "should I continue?". Execute all sprints, create all PRs, report when fully done.

### Rule 2: ALWAYS use Codex for reviews
Every spec review, every plan review, every code quality review MUST include Codex in parallel with Claude. This is not optional. If Codex is unavailable, note it and proceed with Claude-only, but always TRY Codex first.

### Rule 3: PR per sprint
Each sprint/logical chunk = separate git branch + PR. Never accumulate 20 commits in one PR. Smaller PRs are easier to review, safer to merge, and can be deployed independently.

### Rule 4: Maximum parallelism
Always dispatch the maximum number of independent agents simultaneously. If 5 tasks are independent — launch 5 agents. Never serialize independent work.

### Rule 5: Proactive product thinking
Don't just ask questions — PROPOSE ideas. "Have you considered X?" is better than "What do you want?". Research best practices, suggest features from analogous products, challenge assumptions.

---

## Phase 1: Product Discovery (COLLABORATIVE)

This phase is a conversation with the user. Take your time here — rushing discovery leads to building the wrong thing.

### Step 1: Context Exploration

Before any questions, silently explore:
- Read CLAUDE.md, project docs, recent git history
- Understand current architecture, data model, existing features
- Identify gaps between what exists and what the user is describing

### Step 2: Best Practices Research

Before brainstorming, launch parallel research agents to gather external context:

**What to research (dispatch as background agents):**
- Best practices in the domain (e.g., "financial analytics dashboard best practices")
- Existing libraries/packages that solve parts of the problem (don't reinvent wheels)
- MCP servers that could provide useful integrations
- How analogous products solve the same problem (competitors, open-source alternatives)
- Relevant design patterns, data models, algorithms

**Format:** Each research agent returns a brief summary. Orchestrator synthesizes into context for brainstorming. Share key findings with user: "Я нашёл несколько интересных вещей: [findings]. Это влияет на наш подход так: [insight]."

**This is NOT optional.** Even for seemingly simple features, 5 minutes of research prevents hours of reinventing.

### Step 3: Multi-Expert Brainstorming

Run brainstorming with THREE expert lenses (all in the same conversation, not separate agents), informed by research:

**Product Expert lens:**
- "Users of similar apps (Mint, YNAB, Copilot Money) typically expect X — should we include that?"
- "This feature solves problem A, but I notice problem B is related — addressing both would be more impactful"
- "From a UX perspective, the simplest flow would be..."
- Challenge: "Do users actually need X, or is Y the real problem?"

**Architecture Expert lens:**
- "The current data model already supports X, so we can leverage that"
- "There's a performance opportunity here: by doing X, we avoid Y"
- "This could be implemented as Z, which would also unlock future features A, B"

**Domain Expert lens (for the specific domain — finance, crypto, etc.):**
- "In financial apps, best practice for X is Y"
- "Edge case to consider: multi-currency households typically face Z"
- "Regulatory/compliance consideration: W"

### How to ask questions:
- One question at a time
- Prefer multiple choice
- BUT: combine each question with a proactive suggestion or insight
- Example: "Где чаще смотришь аналитику — бот или веб? Кстати, в Copilot Money и Monarch они решили это через deeplinks из бота прямо в конкретный график — может быть интересно для нас тоже."

### Step 4: Approaches + Recommendation

Propose 2-3 approaches with trade-offs. Lead with your recommendation and explain why. Be opinionated.

### Step 5: Design Presentation

Present design section by section. Scale depth to complexity.

### Step 6: Spec Document

Write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.

### Step 7: Spec Review (Claude + Codex PARALLEL)

Launch BOTH in parallel:

**Claude subagent** — spec-document-reviewer (architecture, completeness, feasibility)

**Codex** — spec review focused on technical correctness:
```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
Review this design spec for a software feature.

## Spec
$(cat docs/superpowers/specs/SPEC_FILE.md)

## Project context
$(cat CLAUDE.md)

Review for:
1. Technical feasibility — can this be built as described?
2. Missing pieces — what's not covered that should be?
3. Contradictions — does anything conflict with the project context?
4. Over-engineering — is anything unnecessary?

Report:
### Issues (must fix)
### Suggestions
### Verdict: APPROVE | NEEDS_REVISION
PROMPT
)" 2>&1
```

Fix issues from both reviewers. Re-review if NEEDS_REVISION.

### Step 8: Implementation Plan

Write plan to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.

**Plan structure:**
- Break into sprints (logical chunks, each deployable independently)
- Each sprint = 3-8 tasks
- Each task has: files, steps, code, tests, commit message
- Tasks within a sprint can be parallelized where independent

### Step 9: Plan Review (Claude + Codex PARALLEL)

Same pattern as spec review. Both must APPROVE.

### Step 10: User Approval

Present the plan summary to user. This is the LAST interaction point before autonomous execution. Show:
- Sprint breakdown with scope
- Estimated PR count
- "After approval, I'll execute all sprints autonomously and report when done."

User says "go" → Phase 2 begins. No more questions.

---

## Phase 2: Autonomous Execution (ZERO INTERACTION)

After user approves, execute continuously until all sprints are complete. Never ask, never pause, never summarize between sprints.

### Per-Sprint Flow

```
For each Sprint N:
│
├─ 1. Create branch: feat/<feature>-sprint-N
│
├─ 2. For each task (maximize parallel agents):
│   ├─ Dispatch implementer (Claude Agent, background)
│   ├─ On completion: spec review (Claude subagent)
│   ├─ On spec pass: code quality review (Claude + Codex PARALLEL)
│   └─ On quality pass: mark task complete
│
├─ 3. After all tasks in sprint: PRODUCT ACCEPTANCE REVIEW
│   ├─ Run full test suite
│   ├─ Launch Product Acceptance (Claude + Codex PARALLEL):
│   │   ├─ Claude Product Agent: verify spec compliance from product perspective
│   │   └─ Codex Product Agent: independent product review
│   │   Both check: does the implementation match the original spec intent?
│   │   Are there product gaps the code reviews missed?
│   ├─ Fix any product issues found (auto, no user interaction)
│   ├─ Push branch
│   └─ Create PR with sprint summary + acceptance results
│
└─ 4. Start next sprint immediately (branch from previous)
```

### Agent Dispatch Rules

**Implementation agents:**
- Use `run_in_background: true` for independent tasks
- Use `mode: bypassPermissions` for all implementation agents
- Use `model: sonnet` for mechanical tasks (1-2 files, clear spec)
- Use default model for complex integration tasks
- Maximum concurrent agents: limited only by task independence

**Review optimization:**
- For simple tasks (1-2 files, <50 lines changed): spec review only, skip code quality review
- For medium tasks (2-5 files): spec review + Claude code quality (skip Codex)
- For complex tasks (5+ files, new architecture): full review cycle (spec + Claude + Codex + product)
- Product review: only for user-facing changes (UI, bot responses, API behavior)

### Codex for Code Quality Review

MANDATORY for complex tasks. Launch in parallel with Claude reviewer:

```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
You are reviewing code changes for quality.

## Diff
$(git diff BASE_SHA..HEAD_SHA)

## What was implemented
[Summary]

## Review for:
1. Bugs, logic errors, null safety
2. Edge cases and failure modes
3. Performance (N+1, O(n²), unnecessary queries)
4. Security (injection, auth, data exposure)
5. Test coverage and test quality

Be specific — file:line references.

### Critical (must fix)
### Important (should fix)
### Minor
### Verdict: APPROVE | REQUEST_CHANGES
PROMPT
)" 2>&1
```

### Product Acceptance Review (MANDATORY per sprint)

After all tasks in a sprint pass code review, run Product Acceptance. This is the **most important review stage** — it verifies that what was built actually matches the spec INTENT, not just the technical requirements. Code can be technically clean but productively wrong.

**Launch Claude + Codex product reviewers IN PARALLEL:**

**Claude Product Agent:**
```
Agent tool (general-purpose):
  description: "Product acceptance review for Sprint N"
  prompt: |
    You are a Product Owner reviewing delivered work against the original specification.

    ## Original Spec (what was promised)
    [Full text of relevant spec sections]

    ## What Was Built (sprint diff)
    [git diff or file list with descriptions]

    ## Review for PRODUCT FIT:
    1. Does this implementation deliver what the spec described?
    2. Are there spec requirements that were skipped or simplified?
    3. Would the user be satisfied with this? What would confuse them?
    4. Are there functional gaps — things that technically work but don't serve the user?
    5. Data correctness: are amounts, dates, categories right for real-world use?

    Report:
    ### Spec Gaps (implemented differently or missing vs spec)
    ### UX Concerns (user would be confused or frustrated)
    ### Data Integrity Issues (wrong amounts, dates, categories)
    ### Verdict: ACCEPTED | NEEDS_FIXES
```

**Codex Product Agent** (launched IN PARALLEL):
```bash
codex --approval-mode full-auto --quiet \
  -p "$(cat <<'PROMPT'
You are a Product Owner reviewing delivered software against its specification.

## Spec
$(cat docs/superpowers/specs/SPEC_FILE.md)

## Changes delivered
$(git diff SPRINT_BASE..HEAD --stat)
$(git log SPRINT_BASE..HEAD --oneline)

## Review for product fit:
1. Does the code deliver what the spec promised?
2. Are there gaps between spec intent and implementation?
3. Would a real user be satisfied?
4. Are there edge cases the spec covered but code doesn't handle?

### Spec Gaps
### UX Concerns
### Verdict: ACCEPTED | NEEDS_FIXES
PROMPT
)" 2>&1
```

**Merge results from both.** If either says NEEDS_FIXES → fix autonomously → re-review. Only create PR after BOTH accept.

### PR Creation Pattern

Each sprint creates its own PR:

```bash
# Branch naming
git checkout -b feat/<feature>-sprint-1
# ... do work ...
git push -u origin feat/<feature>-sprint-1
gh pr create --title "Sprint 1: <scope>" --body "..."

# Next sprint branches from previous
git checkout -b feat/<feature>-sprint-2
# ... do work ...
```

PR body format:
```markdown
## Sprint N: [Scope Description]

### Changes
- [bullet points of what was built]

### New files
- [list]

### Tests
- X/Y tests passing
- [coverage notes]

### Dependencies
- Depends on: PR #NNN (Sprint N-1) — merge that first
- or: Independent — can merge standalone
```

### Handling Failures During Autonomous Execution

**Test failure:** Fix in-place, don't stop sprint. If unfixable after 2 attempts, note in PR description and continue.

**Build failure:** Check if it's pre-existing (ignore) or new (fix). If new and unfixable, note and continue.

**Agent blocked:** Re-dispatch with more context or different model. If still blocked after 2 attempts, implement manually and continue.

**NEVER** stop the sprint pipeline to ask the user. Accumulate issues and report them all at the end.

### Completion Report

When ALL sprints are done, report to user:

```
## SuperFlow Complete

### PRs Created
1. #NNN — Sprint 1: [scope] — [status: ready for review]
2. #NNN — Sprint 2: [scope] — [status: ready for review]
...

### Test Results
- Total: X/Y passing
- New tests added: Z

### Known Issues
- [any accumulated issues/notes]

### Merge Order
1. Merge PR #NNN first (no dependencies)
2. Then PR #NNN (depends on #1)
...
```

---

## Codex Integration Rules

### When Codex is MANDATORY
- Spec review (parallel with Claude)
- Plan review (parallel with Claude)
- Code quality review for complex tasks (parallel with Claude)

### When Codex is OPTIONAL
- Implementation of isolated tasks (alternative to Claude subagent)
- Quick checks (lint, type-check output analysis)

### Codex Invocation Pattern

Always via Bash tool:
```bash
codex --approval-mode full-auto --quiet -p "PROMPT" 2>&1
```

Key rules:
- Self-contained prompt (Codex can't ask questions)
- Include ALL context (file paths, project conventions, constraints)
- Always `git diff` after Codex implementations to verify scope
- Timeout: `timeout 300 codex ...` for long tasks

### If Codex is Unavailable

If `codex` CLI is not installed or OPENAI_API_KEY is not set:
1. Log: "Codex unavailable — proceeding with Claude-only reviews"
2. Continue with Claude subagents for all review stages
3. Note in completion report: "Codex was unavailable for dual-provider reviews"

---

## Red Flags — Things That Must NEVER Happen

1. **Pausing to ask "should I continue?"** — After plan approval, execute silently
2. **Offering visual companion** — Just use it if relevant
3. **Asking "want to review the spec?"** — If review passed, move on
4. **Pausing between sprints** — Start next sprint immediately
5. **One giant PR** — Always PR per sprint
6. **Skipping Codex reviews** — Always try Codex first
7. **2 agents when 5 could run** — Maximize parallelism
8. **Only asking questions, no suggestions** — Always propose ideas alongside questions
9. **Committing directly to main** — Always feature branches
10. **Force-pushing without user consent** — Never destructive git ops

---

## Integration with Superpowers

SuperFlow uses these superpowers skills internally:
- `superpowers:brainstorming` — base flow, extended with multi-expert lenses
- `superpowers:writing-plans` — plan structure and review templates
- `superpowers:subagent-driven-development` — agent dispatch patterns
- `superpowers:test-driven-development` — TDD within tasks
- `superpowers:verification-before-completion` — run tests before PRs

SuperFlow OVERRIDES these superpowers behaviors:
- Brainstorming: adds proactive product suggestions (not just questions)
- Plan execution: PR per sprint (not one PR for everything)
- Review: mandatory Codex parallel review (not Claude-only)
- Pacing: zero pauses after plan approval (not "check with user between tasks")

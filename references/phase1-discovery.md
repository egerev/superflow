# Phase 1: Product Discovery (COLLABORATIVE)

This phase is a conversation with the user. Take your time — rushing discovery leads to building the wrong thing.

## Step 1: Context Exploration

Before any questions, silently explore:
- Read CLAUDE.md, project docs, recent git history
- Understand current architecture, data model, existing features
- Identify gaps between what exists and what the user is describing

## Step 2: Best Practices Research

Before brainstorming, launch parallel research agents to gather external context:

**What to research (dispatch as background agents):**
- Best practices in the domain (e.g., "financial analytics dashboard best practices")
- Existing libraries/packages that solve parts of the problem
- How analogous products solve the same problem (competitors, open-source alternatives)
- Relevant design patterns, data models, algorithms

**Format:** Each research agent returns a brief summary. Orchestrator synthesizes into context for brainstorming. Share key findings with user.

**This is NOT optional.** 5 minutes of research prevents hours of reinventing.

## Step 2.5: Independent Product Expert (parallel with brainstorming)

Dispatch an independent product expert to generate ideas in parallel.

**If secondary provider is available** (Codex preferred):
```bash
$TIMEOUT_CMD 600 codex exec --full-auto "You are a Product Expert. Given this context about [project] and [research], propose 3-5 concrete product improvements. For each: what, why it matters, how it could work." 2>&1
```

**If no secondary provider** — dispatch a background Claude Agent with the same prompt.
An independent agent produces different ideas because it has no conversational anchoring bias.

Run IN PARALLEL with brainstorming. Two models (or two independent agents) produce different ideas.

## Step 3: Multi-Expert Brainstorming

**STOP GATE:** After research completes, your NEXT action MUST be a question or proposal
to the user. Do NOT jump to Product Summary. Do NOT synthesize research into a ready plan.
The point of brainstorming is to discover things the research DIDN'T cover.

**Format:** Freeflow conversation with product focus.

**Product vision focus (most important):**
- Understand the WHY and FOR WHOM before the WHAT and HOW
- Pull the user's vision: what does "done" look like?
- Ask for references: apps, screenshots, examples
- Understand scope: personal tool vs service? MVP vs long-term?

**Rhythm: questions → proposals → questions**
After gathering context (3-5 questions), make concrete product proposals. Let user react. This generates requirements you wouldn't have found by asking.

**Proposals must be GENUINELY NEW ideas** — not rephrasing what the user already wrote in
BACKLOG.md or told you earlier. If you can trace an idea back to the user's own words,
it's not a brainstorm contribution. Bring ideas from: research findings, analogous products,
architectural opportunities the user hasn't considered, or cross-domain patterns.

**Three expert lenses** (weave into freeflow):
- **Product:** "Users of similar apps typically expect X — should we include that?"
- **Architecture:** "The current data model already supports X, we can leverage it"
- **Domain:** "In [domain] apps, best practice for X is Y"

**One question at a time.** Don't overload.

## Step 4: Approaches + Recommendation

**DO NOT SKIP THIS STEP.** Even if you're confident in one approach, present at least 2
alternatives with trade-offs. This forces you to consider options the user may prefer.

Propose 2-3 approaches with trade-offs. Lead with your recommendation. Be opinionated.
For each approach: what's good, what's risky, what's the effort level.

## Step 5: Product Summary (USER APPROVAL GATE)

**BEFORE writing a detailed spec**, present a Product Summary:

```
## Product Summary: [Feature Name]

### What we're building
- [Feature 1]: [one-line description]
- [Feature 2]: [one-line description]
...

### Problems solved
- [Problem 1]
- [Problem 2]

### NOT in scope
- [Excluded item 1]
- [Excluded item 2]

### Key decisions
- [Decision 1]: [rationale]
- [Decision 2]: [rationale]
```

**Wait for user "ок" before proceeding.** This is the product approval gate.

## Step 6: Spec Document

```bash
mkdir -p docs/superpowers/specs
```

Write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.

## Step 7: Spec Review (dual-model PARALLEL)

Launch Claude + secondary provider in parallel. Use `prompts/spec-reviewer.md`.
If no secondary provider, use split-focus: two Claude agents — one checks completeness/consistency,
the other checks scope/YAGNI.
Fix issues. Re-review if NEEDS_REVISION.

## Step 8: Implementation Plan

```bash
mkdir -p docs/superpowers/plans
```

Write plan to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.

**Plan structure:**
- Break into sprints (logical chunks, each deployable independently)
- Each sprint = 3-8 tasks
- Each step = 2-5 minutes of work (atomic operations)
- Each task has: files, steps, commit message

## Step 9: Plan Review (dual-model PARALLEL)

Same as spec review. Both reviewers must APPROVE.

## Step 10: User Approval

Present plan summary. This is the LAST interaction before autonomous execution:
- Sprint breakdown with scope
- Estimated PR count
- "After approval, I'll execute all sprints and report when done."

User says "go" → Phase 2 begins. No more questions.

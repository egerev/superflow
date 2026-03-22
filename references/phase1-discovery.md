# Phase 1: Product Discovery (COLLABORATIVE)

## Step 1: Context Exploration
Read CLAUDE.md, llms.txt, project docs, git history. Understand architecture, data model, existing features. Identify gaps.

## Step 2: Best Practices & Product Research

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

**NOT optional.** Synthesize findings before proceeding.

## Step 3: Present Research Findings

Present a brief summary of research results to the user before brainstorming. Include product expert proposals. This ensures the user sees what was discovered and can steer the conversation.

## Step 4: Multi-Expert Brainstorming

**STOP GATE — Do NOT proceed past this step without user interaction.**
Your next action MUST be a question or proposal to the user. Do NOT jump to Product Summary.

- Understand WHY and FOR WHOM before WHAT and HOW
- Rhythm: ask 3-5 questions total (one at a time), then concrete proposals, then follow-up questions
- One question per message — wait for answer before the next
- Proposals must be genuinely new (not rephrasing user's own words)
- Three lenses: Product ("users expect X"), Architecture ("data model supports X"), Domain ("best practice is Y")

## Step 5: Approaches + Recommendation

Present 2-3 approaches with trade-offs. Lead with recommendation.
For each approach: strengths, risks, effort level.
**Mandatory step** — even if one approach seems obvious, present alternatives. The user must see options before Product Summary.

## Step 6: Product Summary (APPROVAL GATE)

Present to the user:
- What we're building (feature list)
- Problems solved
- NOT in scope
- Key decisions + rationale

**APPROVAL GATE:** Ask the user: "Approve this scope? I'll write the spec next."
- User says "yes" / "go" / "approve" / approving phrase → proceed to Product Brief
- User requests changes → update summary, re-present, ask again
- Do NOT proceed to Step 7 without explicit approval

## Step 7: Product Brief

After approval, before the technical spec, write a lightweight product brief. This bridges product thinking and technical implementation. Include:

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

## Step 8: Spec Document

Write to `docs/superflow/specs/YYYY-MM-DD-<topic>-design.md`. Reference the product brief.

Include:
- **Overview**: what is being built (reference brief)
- **Technical design**: architecture, data model changes, API contracts
- **File-level changes**: which files are modified/created
- **Edge cases and error handling**: from the brief's edge cases
- **Testing strategy**: what tests validate correctness
- **Out of scope**: explicit boundaries

Create `docs/superflow/specs/` if it doesn't exist.

## Step 9: Spec Review (dual-model parallel)

Run two reviewers in parallel using `prompts/spec-reviewer.md`:

1. **Claude reviewer**: dispatch via Agent tool (`run_in_background: true`). Focus: spec completeness, security, architecture.
2. **Secondary provider**: `$TIMEOUT_CMD 600 $SECONDARY_PROVIDER "REVIEW_PROMPT" 2>&1` via Bash (`run_in_background: true`).
   No secondary provider = split-focus Claude: dispatch two background agents (Technical: completeness + security; Product: scope + YAGNI).

Wait for both. If either returns NEEDS_REVISION: fix issues, re-run both reviews.
Both must return PASS to proceed.

## Step 10: Implementation Plan

Write to `docs/superflow/plans/YYYY-MM-DD-<topic>.md`. Create `docs/superflow/plans/` if it doesn't exist.

Break into sprints (independently deployable), 3-8 tasks each, each task 2-5 min. Include: files, steps, commit message.

## Step 11: Plan Review (dual-model parallel)

Run two reviewers in parallel (same mechanism as Step 9):

1. **Claude reviewer** (background): Is the plan achievable? Are sprints properly scoped? Are task estimates realistic? Dependencies correct?
2. **Secondary provider** (background): Are there missing tasks? Over-engineering? Does sprint ordering make sense?
   No secondary provider = split-focus Claude (Technical + Product lenses).

Both must APPROVE. If either returns NEEDS_REVISION: fix, re-review.

## Step 12: User Approval (FINAL GATE)

Present:
- Sprint breakdown with task counts
- Estimated PR count (1 per sprint)
- Merge order and dependencies

**FINAL GATE:** Ask the user: "Ready to start autonomous execution? Say 'go' when ready."
- User says "go" / "start" / "давай" / affirmative → proceed to Phase 2
- User requests changes → update plan, re-present

Before entering Phase 2: re-read `references/phase2-execution.md` and verify worktree prerequisites.

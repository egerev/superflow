# Phase 1: Product Discovery (COLLABORATIVE)

## Step 1: Context Exploration
Read CLAUDE.md, project docs, git history. Understand architecture, data model, existing features. Identify gaps.

## Step 2: Best Practices Research
Dispatch parallel background agents for: domain best practices, relevant libraries, competitor approaches, design patterns. Synthesize findings for brainstorming. NOT optional.

## Step 2.5: Independent Product Expert (parallel with brainstorming)
Dispatch secondary provider (or background Claude agent) as product expert: "Propose 3-5 concrete product improvements. For each: what, why, how."
Run in parallel with brainstorming. Two independent models produce different ideas.

## Step 3: Multi-Expert Brainstorming
STOP GATE: After research, your next action MUST be a question/proposal to the user. Do NOT jump to Product Summary.

- Understand WHY and FOR WHOM before WHAT and HOW
- Rhythm: questions > proposals > questions (3-5 Qs, then concrete proposals)
- Proposals must be genuinely new (not rephrasing user's own words)
- Three lenses: Product ("users expect X"), Architecture ("data model supports X"), Domain ("best practice is Y")
- One question at a time

## Step 4: Approaches + Recommendation
Present 2-3 approaches with trade-offs. Lead with recommendation. For each: good, risky, effort level. Do NOT skip.

## Step 5: Product Summary (APPROVAL GATE)
Present before writing spec:
- What we're building (feature list)
- Problems solved
- NOT in scope
- Key decisions + rationale

Wait for user approval before proceeding.

## Step 5.5: Product Brief

After approval, before the technical spec, write a lightweight product brief. This bridges product thinking and technical implementation. Include:

- **Problem statement**: What user pain are we solving? (1-2 sentences)
- **Jobs to be Done**: When [situation], I want to [motivation], so I can [outcome]
- **User stories**: As a [role], I want [action] so that [benefit] (3-5 key stories)
- **Success criteria**: How do we know this worked? (measurable outcomes)
- **Edge cases**: What happens when things go wrong? (happy path + 2-3 failure modes)

Save to `docs/superflow/specs/YYYY-MM-DD-<topic>-brief.md`.

This brief is shared with:
1. Spec writers (basis for technical spec)
2. Implementers (context for why, not just what)
3. Reviewers (spec compliance = brief compliance)

Keep it short (< 1 page). No frameworks — just clarity about what we're building and for whom.

## Step 6: Spec Document
Write to `docs/superflow/specs/YYYY-MM-DD-<topic>-design.md`. Reference the product brief.

## Step 7: Spec Review (dual-model parallel)
Claude + secondary provider in parallel using `prompts/spec-reviewer.md`. No secondary provider = split-focus (completeness vs scope/YAGNI). Fix issues, re-review if NEEDS_REVISION.

## Step 8: Implementation Plan
Write to `docs/superflow/plans/YYYY-MM-DD-<topic>.md`. Break into sprints (independently deployable), 3-8 tasks each, each task 2-5 min. Include: files, steps, commit message.

## Step 9: Plan Review (dual-model parallel)
Same as spec review. Both must APPROVE.

## Step 10: User Approval
Present sprint breakdown + estimated PR count. Last interaction before autonomous execution. User says "go" = Phase 2 begins.

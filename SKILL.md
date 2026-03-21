---
name: superflow
description: "Use when user says 'superflow', 'суперфлоу', or asks for full dev workflow. Two phases: (1) collaborative Product Discovery with multi-expert brainstorming, (2) fully autonomous execution with PR-per-sprint, git worktrees, parallel reviews, max parallelism, and verification discipline."
---

# SuperFlow — Product-to-Production Workflow

Two distinct phases: collaborative discovery, then autonomous execution.

```
Phase 1: COLLABORATIVE (with user)
  Product Discovery → Multi-Expert Brainstorming → Spec → Plan

Phase 2: AUTONOMOUS (no stops until done)
  Sprint 1 (worktree) → PR #1
  Sprint 2 (worktree) → PR #2
  ...
  Sprint N (worktree) → PR #N
  → Report to user: "Done. N PRs ready for review."
```

---

## CONTEXT DRIFT PREVENTION

The #1 failure mode: skill loads at start, agent "forgets" it after 30+ messages and improvises.

**Checkpoint re-reads:** Before each major phase transition, RE-READ this skill file:
- Before starting Phase 2 (after user says "go") → re-read SKILL.md Phase 2 section
- Before each sprint → re-read Per-Sprint Flow section
- Before dispatching reviewers → re-read the relevant prompt template from `prompts/`
- After each sprint completes → re-read Product Acceptance Review section before creating PR

**How to re-read:** Use the Read tool on the skill file. Don't rely on memory of what it said. The skill may have been updated since you last read it.

**Self-check questions at phase transitions:**
- "Am I following the SuperFlow process, or my own improvised version?"
- "Did I use git worktrees for this sprint?" (if no → stop, create one)
- "Did I run parallel review agents?" (if no → do it now)
- "Did I verify test output before claiming done?" (if no → run tests now)
- "Am I about to pause and ask the user something?" (if yes → DON'T, just execute)
- "Did I run Product Acceptance Review?" (if no → DO IT NOW, before creating PR)

**Mandatory self-reminder loop:** After completing each sprint's tasks, BEFORE creating the PR, output this checklist to yourself:
```
SPRINT COMPLETION CHECKLIST:
[ ] Tests pass with evidence (actual output pasted)
[ ] Lint clean
[ ] TypeCheck clean
[ ] Product Acceptance Review launched (parallel agents)
[ ] Product Acceptance APPROVED
[ ] Only then → create PR
```
If any box is unchecked, complete that step before proceeding.

---

## REASONING DEPTH

Use `ultrathink` keyword in prompts for tasks requiring deep reasoning. This triggers extended thinking mode regardless of the user's default reasoning effort setting.

**Always use ultrathink for:**
- Spec review prompts (dispatched to Claude agents)
- Plan review prompts (dispatched to Claude agents)
- Product Acceptance review prompts
- Architecture decisions during brainstorming

**Standard reasoning for:**
- Implementation agents (plan is already detailed)
- Simple file operations, commits, pushes

**How:** Prepend "ultrathink:" to the agent prompt. Example:
```
"ultrathink: You are reviewing this spec for completeness..."
```

---

## CRITICAL RULES

### Rule 1: NEVER pause during autonomous execution
After user says "go" / "ok" / "давай" on the approved plan — ZERO stops, ZERO questions, ZERO "should I continue?". Execute all sprints, create all PRs, report when fully done.

### Rule 2: Parallel reviews with independent agents
Dispatch TWO independent review agents in parallel for every review stage. Each agent gets a different review focus (see prompt templates). Two independent reviewers catch more bugs than one — regardless of provider.

### Rule 3: PR per sprint
Each sprint/logical chunk = separate git branch + PR. Never accumulate 20 commits in one PR. Smaller PRs are easier to review, safer to merge, and can be deployed independently.

### Rule 4: Maximum parallelism
Always dispatch the maximum number of independent agents simultaneously. If 5 tasks are independent — launch 5 agents. Never serialize independent work.

### Rule 5: Proactive product thinking
Don't just ask questions — PROPOSE ideas. "Have you considered X?" is better than "What do you want?". Research best practices, suggest features from analogous products, challenge assumptions.

### Rule 6: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
Before marking ANY task complete: run tests, read output, THEN claim done.
Before creating ANY PR: run full test suite, verify clean output.

**Red flags that indicate rule violation:**
- "should work" — NOT evidence
- "probably passes" — NOT evidence
- "seems fine" — NOT evidence
- "I believe this is correct" — NOT evidence

**Evidence** = actual command output showing pass/success, pasted in full.

---

## Rationalization Prevention

Agents rationalize skipping quality steps. Recognize and reject these:

| Rationalization | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing about your code. |
| "Skip review, it's trivial" | Trivial changes break production. Review anyway. |
| "One big PR is fine" | 20-commit PRs don't get reviewed. Split into sprints. |
| "One reviewer is enough" | Two independent reviewers catch more bugs. Always use parallel review. |
| "Let me ask the user" | After plan approval, execute silently. |
| "This task is too hard" | Escalate with BLOCKED, don't silently produce bad work. |
| "Tests are green so it works" | Green tests prove tests pass, not that the feature works. Verify behavior. |

---

## Mode Detection

At the start, detect which mode applies based on context:

**Enhancement mode** (existing codebase):
- Deeper codebase exploration: read key files, understand patterns, find reusable code
- Step 1 (Context Exploration) is heavier — understand what exists before proposing changes
- Brainstorming references existing architecture: "The current data model already has X, we can extend it"
- Plan preserves backward compatibility

**Greenfield mode** (new project / new major subsystem):
- Focus on stack selection, project structure, CI/CD setup
- Research phase includes framework comparison, starter templates, infrastructure options
- Brainstorming is more open-ended — no existing patterns to follow
- First sprint often includes project scaffolding + CI/CD

The mode is auto-detected from context (existing code = enhancement, empty repo = greenfield). No need to ask the user.

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

**Format:** Each research agent returns a brief summary. Orchestrator synthesizes into context for brainstorming. Share key findings with user.

**This is NOT optional.** Even for seemingly simple features, 5 minutes of research prevents hours of reinventing.

### Step 2.5: Independent Product Expert (parallel with brainstorming)

After research completes and before/during brainstorming, dispatch a background Agent with the gathered context to generate product ideas independently:

```
Dispatch a background Agent with prompt:
"You are a Product Expert. Given this context about [project description] and [research findings], propose 3-5 concrete product improvements or features. For each: what it is, why it matters for the user, and how it could work. Be specific and creative — suggest things the user might not have thought of."
```

Run this IN PARALLEL with the main brainstorming conversation. An independent agent produces different ideas because it has no conversational anchoring bias — synthesize the best from both.

### Step 3: Multi-Expert Brainstorming

**Format:** Freeflow conversation with product focus. No rigid checklist — adapt to the task context. But ensure sufficient depth before moving to design.

**Product vision focus (most important):**
- Understand the WHY and FOR WHOM before the WHAT and HOW
- Pull the user's vision: what does "done" look like? What experience do they want?
- Ask for references: apps, screenshots, examples, competitors — anything that shows intent
- Understand scope ambition: personal tool vs service for others? MVP vs long-term?

**Rhythm: questions -> proposals -> questions**
Don't just ask. After gathering enough context (3-5 questions), make concrete product proposals based on what you've heard + research findings. Let the user react — "yes / no / interesting but..." — this generates new requirements you wouldn't have found by asking.

Example cycle:
1. Ask 3-4 questions to understand the vision
2. Present 2-3 product ideas/suggestions based on answers + research
3. User reacts -> new requirements emerge
4. Ask 1-2 follow-up questions on the new requirements
5. Repeat until the picture is clear

**Depth calibration:** The number of cycles depends on task complexity. A simple feature may need 1 cycle (5 min). A major system overhaul may need 3-4 cycles (20 min). The sign that you're done: you can describe back to the user what they want to build, and they say "yes, exactly."

**Three expert lenses** (weave into the freeflow, not separate blocks):
- **Product lens:** "Users of similar apps typically expect X — should we include that?"
- **Architecture lens:** "The current data model already supports X, so we can leverage that"
- **Domain lens:** "In [domain] apps, best practice for X is Y"

**One question at a time.** Combine questions with insights when natural, but don't overload.

### Step 4: Approaches + Recommendation

Propose 2-3 approaches with trade-offs. Lead with your recommendation and explain why. Be opinionated.

### Step 5: Design Presentation

Present design section by section. Scale depth to complexity.

### Step 6: Spec Document

Write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.

### Step 7: Spec Review (parallel agents)

Launch TWO independent review agents in parallel. Use prompt template from `prompts/spec-reviewer.md`. Give each agent a different review focus — one checks completeness/consistency, the other checks scope/YAGNI.

**Calibration:** Only flag issues that would cause real problems during planning or implementation. Check: Completeness, Consistency, Clarity, Scope, YAGNI. Do NOT flag style or formatting issues in specs.

Fix issues from both review agents. Re-review if NEEDS_REVISION.

### Step 8: Implementation Plan

Write plan to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.

**Plan structure:**
- Break into sprints (logical chunks, each deployable independently)
- Each sprint = 3-8 tasks

**Bite-sized task granularity (CRITICAL):**
Each step = 2-5 minutes of work. Break tasks down to atomic operations:
- "Write the failing test for X behavior" — one step
- "Run it to verify failure" — one step
- "Implement minimal code to pass" — one step
- "Run tests to verify pass" — one step
- "Commit" — one step

A medium feature plan should have 20-30+ steps, NOT 5-10 large tasks. If a step takes more than 5 minutes, it's too big — split it.

**Each task has:** files, steps, code, tests, commit message
**Tasks within a sprint can be parallelized where independent**

### Step 9: Plan Review (parallel agents)

Same pattern as spec review. Both agents must APPROVE.

### Step 10: User Approval

Present the plan summary to user. This is the LAST interaction point before autonomous execution. Show:
- Sprint breakdown with scope
- Estimated PR count
- "After approval, I'll execute all sprints autonomously and report when done."

User says "go" -> Phase 2 begins. No more questions.

---

## Phase 2: Autonomous Execution (ZERO INTERACTION)

After user approves, execute continuously until all sprints are complete. Never ask, never pause, never summarize between sprints.

### Per-Sprint Flow

```
For each Sprint N:
|
+-- 1. Create git worktree for isolation:
|      git worktree add .worktrees/sprint-N feat/<feature>-sprint-N
|      (Verify .worktrees/ is in .gitignore — add if missing)
|
+-- 2. Run baseline tests in worktree before starting work
|      (If baseline fails, note pre-existing failures and continue)
|
+-- 3. For each task (maximize parallel agents):
|      +-- Dispatch implementer (see prompts/implementer.md)
|      +-- On completion: spec review (see prompts/spec-reviewer.md)
|      +-- On spec pass: code quality review (see prompts/code-quality-reviewer.md)
|      +-- On quality pass: VERIFY — run tests, read output, confirm pass
|      +-- Mark task complete only with verification evidence
|
+-- 4. After all tasks in sprint: PRODUCT ACCEPTANCE REVIEW
|      +-- Run full test suite — paste output as evidence
|      +-- Launch Product Acceptance (parallel agents)
|      |      (see prompts/product-reviewer.md)
|      +-- Fix any product issues found (auto, no user interaction)
|      +-- Run tests AGAIN after fixes — verify still green
|      +-- Push branch, create PR with sprint summary + acceptance results
|
+-- 5. Clean up worktree:
|      git worktree remove .worktrees/sprint-N
|
+-- 6. Start next sprint immediately (next worktree from updated base)
```

### Git Worktree Rules

Worktrees provide sprint isolation — each sprint works in its own directory.

**Setup (once per session):**
```bash
# Ensure .worktrees/ is gitignored
grep -q '.worktrees/' .gitignore 2>/dev/null || echo '.worktrees/' >> .gitignore
```

**Per sprint:**
```bash
# Create worktree for sprint
git worktree add .worktrees/sprint-N feat/<feature>-sprint-N

# Work happens inside .worktrees/sprint-N/
# All file paths in agent dispatches use this directory

# After PR creation, clean up
git worktree remove .worktrees/sprint-N
```

**Fallback:** If worktrees are unavailable (e.g., bare repo, permission issues), fall back to regular branch checkout. Note this in the completion report.

### Agent Dispatch Rules

**Implementation agents:**
- Use `run_in_background: true` for independent tasks
- Use `mode: bypassPermissions` for all implementation agents
- Use `model: sonnet` for mechanical tasks (1-2 files, clear spec)
- Use default model for complex integration tasks
- Maximum concurrent agents: limited only by task independence
- All agents use prompt from `prompts/implementer.md`

**Review optimization:**
- For simple tasks (1-2 files, <50 lines changed): spec review only, skip code quality review
- For medium tasks (2-5 files): spec review + single code quality agent
- For complex tasks (5+ files, new architecture): full review cycle (spec + 2 parallel code quality agents + product)
- Product review: only for user-facing changes (UI, bot responses, API behavior)

### Systematic Debugging

When a test fails during execution, follow this protocol — never do "try random fixes until tests pass":

1. **Investigate** — read the failure output, identify the failing assertion
2. **Identify pattern** — is it a data issue, logic error, integration mismatch, or environment problem?
3. **Form hypothesis** — state what you think is wrong and why, before touching code
4. **Diagnostic instrumentation** — if unclear, add logging at component boundaries to trace data flow
5. **Implement fix** — targeted fix based on the hypothesis
6. **Verify** — run the specific failing test, confirm it passes, then run full suite

If unfixable after 2 targeted attempts, mark as BLOCKED with diagnostic evidence and continue.

### Parallel Code Quality Review

MANDATORY for complex tasks. Launch TWO independent review agents in parallel.
Use prompt template from `prompts/code-quality-reviewer.md`.

Give each agent a different focus:
- **Agent A (correctness focus):** logic errors, edge cases, error handling, security
- **Agent B (architecture focus):** performance, pattern compliance, test quality, maintainability

Two agents with different lenses catch more issues than one agent checking everything.

### Product Acceptance Review (MANDATORY per sprint — DO NOT SKIP)

After all tasks pass code review, run Product Acceptance. This is the **most important review stage** — it verifies that what was built matches the spec INTENT, not just the technical requirements. Code can be technically clean but productively wrong.

**This step is NON-NEGOTIABLE.** Do not rationalize skipping it ("tests pass so it's fine", "sprint is simple enough"). Every sprint gets a product acceptance review before PR creation.

Launch TWO independent product review agents IN PARALLEL using `prompts/product-reviewer.md`.

**Steps:**
1. After all sprint tasks complete and tests pass
2. Launch Agent A with product-reviewer prompt — focus on spec-to-implementation fit (background)
3. Launch Agent B with product-reviewer prompt — focus on user scenarios and edge cases (background)
4. Wait for both to complete
5. Merge results — if EITHER says NEEDS_FIXES → fix autonomously → re-review
6. Only create PR after BOTH accept

### PR Creation Pattern

**IMPORTANT: All PRs must target `main` (or the project's default branch).** Do NOT create PRs targeting other sprint branches. When Sprint 1 is squash-merged, GitHub deletes its branch and auto-closes any PRs that used it as a base — forcing a rebase + PR recreation cycle. Always target `main` and merge sprints in order.

Each sprint creates its own PR:

```bash
git push -u origin feat/<feature>-sprint-N
gh pr create --base main --title "Sprint N: <scope>" --body "..."
```

PR body format:
```markdown
## Sprint N: [Scope Description]

### Changes
- [bullet points of what was built]

### Verification Evidence
- Test suite: X/Y passing (full output reviewed)
- Product acceptance: ACCEPTED by parallel review agents

### Dependencies
- Depends on: PR #NNN (Sprint N-1) — merge that first
- or: Independent — can merge standalone
```

### Handling Failures During Autonomous Execution

**Test failure:** Investigate root cause using systematic debugging protocol. Fix in-place, don't stop sprint. If unfixable after 2 targeted attempts, note in PR description with diagnostic evidence and continue.

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

### Verification Evidence
- Full test suite: X/Y passing
- New tests added: Z
- All PRs passed product acceptance review

### Known Issues
- [any accumulated issues with diagnostic evidence]

### Merge Order
1. Merge PR #NNN first (no dependencies)
2. Then PR #NNN (depends on #1)
```

---

## Parallel Review Strategy

The core principle: **two independent reviewers catch more bugs than one.** This works because each reviewer brings a different focus, reducing blind spots.

### How it works
- Dispatch TWO Agent tool calls in parallel (`run_in_background: true`)
- Each agent gets the same base prompt but a **different review focus**
- Merge findings from both agents before proceeding

### Review focus split

**Spec review:**
- Agent A: completeness + consistency (are all requirements implemented?)
- Agent B: scope + YAGNI (is anything extra or over-engineered?)

**Code quality review:**
- Agent A: correctness, edge cases, error handling, security
- Agent B: performance, pattern compliance, test quality, maintainability

**Product acceptance review:**
- Agent A: spec-to-implementation fit, data correctness
- Agent B: user scenarios, edge cases, error UX

### When to use parallel review
- Complex tasks (5+ files, new architecture): always parallel
- Medium tasks (2-5 files): single reviewer is sufficient
- Simple tasks (1-2 files): spec review only

---

## Red Flags — Things That Must NEVER Happen

1. **Pausing to ask "should I continue?"** — After plan approval, execute silently
2. **Claiming done without test output** — Paste evidence or it didn't happen
3. **Skipping the "verify fail" step in TDD** — A test that never failed proves nothing
4. **One giant PR** — Always PR per sprint
5. **Single reviewer for complex tasks** — Always use parallel review agents for complex work
6. **2 agents when 5 could run** — Maximize parallelism
7. **Only asking questions, no suggestions** — Always propose ideas alongside questions
8. **Committing directly to main** — Always feature branches
9. **Random fix attempts** — Investigate before fixing. Hypothesis before code.
10. **"Should work" without evidence** — Run it. Read output. Then claim.

---

## Documentation Update (after all sprints)

After the last sprint's PR is created, before the completion report:

1. **Update CLAUDE.md** — add new modules, files, conventions introduced by this work
2. **Update README** (if project has one) — add new features, API endpoints, commands
3. **Update BACKLOG.md** (if exists) — mark completed items, add new items discovered
4. **Commit documentation updates** to the last sprint's branch

---

## Integration with Superpowers

SuperFlow uses these superpowers skills internally:
- `superpowers:brainstorming` — base flow, extended with multi-expert lenses
- `superpowers:writing-plans` — plan structure, bite-sized granularity
- `superpowers:subagent-driven-development` — agent dispatch patterns
- `superpowers:test-driven-development` — TDD within tasks (see `prompts/implementer.md`)
- `superpowers:verification-before-completion` — Rule 6, evidence-based completion
- `superpowers:using-git-worktrees` — sprint isolation via worktrees
- `superpowers:debugging` — systematic debugging protocol

SuperFlow OVERRIDES these superpowers behaviors:
- Brainstorming: adds proactive product suggestions (not just questions)
- Plan execution: PR per sprint (not one PR for everything)
- Plan granularity: 2-5 minute steps, 20-30+ per feature (not 5-10 big tasks)
- Review: mandatory parallel review with split focus (not single-pass)
- Completion: requires verification evidence (not self-reported status)
- Pacing: zero pauses after plan approval (not "check with user between tasks")

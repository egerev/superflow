You are executing Sprint {sprint_id}: {sprint_title} of the Superflow workflow autonomously.

## Your Task
{sprint_plan}

## Project Context

### CLAUDE.md
{claude_md}

### llms.txt
{llms_txt}

### Autonomy Charter
{charter}

## Reasoning Tier

- **Complexity:** {complexity}
- **Implementation tier:** {implementation_tier}
- **Implementation model:** {impl_model}
- **Implementation effort:** {impl_effort}

## Pre-verified
- {baseline_status}

## Instructions
1. Read the enforcement rules at ~/.claude/rules/superflow-enforcement.md
2. You are already in the sprint worktree on branch `{branch}`. Do NOT create another worktree.
3. Follow Phase 2 execution steps (implementer dispatch, review, PAR, PR)
4. Use the reasoning tier above to select the correct implementer agent and effort level.
5. You MUST write `.par-evidence.json` to the worktree root with these verdict keys:
   `claude_product`, `technical_review`. Also include `provider` ("codex" or "split-focus").
   Each verdict must be one of: APPROVE, ACCEPTED, PASS.
   The supervisor validates this file — if missing or invalid, the sprint FAILS and retries.
{frontend_instructions}
6. Output a JSON summary as the LAST line of your response:
   {"status":"completed","pr_url":"...","tests":{"passed":0,"failed":0},"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"},"steps_completed":["baseline_tests","implementation","internal_review","test_verification","par","pr_created"]}

## Intra-Sprint Progress

After completing each major step, write progress to `.superflow/sprint-progress.json`:
```json
{"sprint_id": 1, "step": "review", "steps_completed": ["baseline_tests", "implementation"], "ts": "ISO-8601"}
```
Steps: baseline_tests, implementation, internal_review, test_verification, par, pr_created

## Step Verification
After each step, verify completion before proceeding:
- After worktree setup: verify branch with `git branch --show-current`
- After baseline tests: paste test output as evidence
- After implementation: verify all tasks DONE, list changed files
- After internal review: paste reviewer verdicts
- After PAR: verify .par-evidence.json exists
- After PR creation: verify PR URL with `gh pr view`
- If any step skipped (e.g., after compaction), go back and complete it
- Check `.superflow-state.json` if unsure of progress

## Parallel Task Dispatch
If this sprint has multiple tasks, analyze for independence:
- Different files + no data dependency = parallel
- Group into waves, dispatch with Agent(run_in_background: true)
- If ≤3 tasks, dispatch sequentially

## Enforcement
- Dispatch subagents for all code (never write directly)
- TDD cycle mandatory
- PAR with 2-agent specialized review before PR (Claude=Product, secondary=Technical)
- One PR for this sprint

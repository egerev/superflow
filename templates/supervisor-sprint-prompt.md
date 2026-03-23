You are executing Sprint {sprint_id}: {sprint_title} of the Superflow workflow autonomously.

## Your Task
{sprint_plan}

## Project Context

### CLAUDE.md
{claude_md}

### llms.txt
{llms_txt}

## Reasoning Tier

- **Complexity:** {complexity}
- **Implementation tier:** {implementation_tier}
- **Implementation model:** {impl_model}
- **Implementation effort:** {impl_effort}

## Instructions
1. Read the enforcement rules at ~/.claude/rules/superflow-enforcement.md
2. You are already in the sprint worktree on branch `{branch}`. Do NOT create another worktree.
3. Follow Phase 2 execution steps (implementer dispatch, review, PAR, PR)
4. Use the reasoning tier above to select the correct implementer agent and effort level.
5. Output a JSON summary as the LAST line of your response:
   {"status":"completed","pr_url":"...","tests":{"passed":0,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}

## Enforcement
- Dispatch subagents for all code (never write directly)
- TDD cycle mandatory
- PAR with dual-model review before PR
- One PR for this sprint

You are executing Sprint {sprint_id}: {sprint_title} of the Superflow workflow autonomously.

## Your Task
{sprint_plan}

## Project Context

### CLAUDE.md
{claude_md}

### llms.txt
{llms_txt}

## Instructions
1. Read the enforcement rules at ~/.claude/rules/superflow-enforcement.md
2. You are already in the sprint worktree on branch `{branch}`. Do NOT create another worktree.
3. Follow Phase 2 execution steps (implementer dispatch, review, PAR, PR)
4. Output a JSON summary as the LAST line of your response:
   {"status":"completed","pr_url":"...","tests":{"passed":0,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"}}

## Enforcement
- Dispatch subagents for all code (never write directly)
- TDD cycle mandatory
- PAR with dual-model review before PR
- One PR for this sprint

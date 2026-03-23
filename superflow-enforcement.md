# Superflow Enforcement

Survives context compaction. SKILL.md does not.

## Hard Rules

1. **Subagents write all code.** Orchestrator reads, plans, reviews, dispatches.
2. **Git worktrees per sprint.** `git worktree add .worktrees/sprint-N feat/<feature>-sprint-N`. Verify `.worktrees/` is in `.gitignore` before creating (`git check-ignore -q .worktrees`).
3. **Unified Review before every PR** (4 agents, all receive SPEC + brief):
   1. Dispatch Claude code-quality reviewer (subagent_type: standard-code-reviewer). `run_in_background: true`
   2. Dispatch Claude product reviewer (subagent_type: standard-product-reviewer). `run_in_background: true`
   3. Dispatch Codex code reviewer: `$TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=high --ephemeral`
   4. Dispatch Codex product reviewer: `$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=high`
   5. Wait for all 4. Fix confirmed issues (NEEDS_FIXES, REQUEST_CHANGES, or FAIL). Re-review only flagging agents.
   6. Write `.par-evidence.json`: `{"sprint":N,"claude_code":"APPROVE","claude_product":"ACCEPTED","codex_code":"APPROVE","codex_product":"ACCEPTED","ts":"..."}`
   7. GATE: `git push` / `gh pr create` blocked until `.par-evidence.json` exists with all 4 verdicts passing.
4. **Tests with evidence.** Paste actual output before claiming done.
5. **Re-read phase docs** at each sprint boundary via Read tool.
6. **Dual-model reviews mandatory.** Use secondary provider for spec review, plan review, and PAR.
7. **No secondary provider = four split-focus Claude agents.** Technical (code-quality-reviewer), Product (product-reviewer), Architecture (spec compliance), UX (user scenarios). Never skip the second pair.
8. **One PR per sprint.** Execute silently after plan approval.
9. **Final Holistic Review after all sprints.** Two Opus reviewers (Technical + Product) review ALL code as a unified system. Fix CRITICAL/HIGH before Completion Report. Per-sprint PAR misses cross-module issues.

## Secondary Provider Invocation

```bash
# Codex general (product review, audit, spec review):
$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=<LEVEL> "PROMPT_HERE" 2>&1

# Codex code review (uses built-in review mode + custom prompt):
$TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=<LEVEL> --ephemeral "CUSTOM_PROMPT" 2>&1

# Gemini: $TIMEOUT_CMD 600 gemini "PROMPT_HERE" 2>&1
# Other:  $TIMEOUT_CMD 600 $SECONDARY_PROVIDER <non-interactive-flag> "PROMPT_HERE" 2>&1
# None:   dispatch four Claude agents with split focus (Technical, Product, Architecture, UX)
```

## Reasoning Tiers

| Tier | Claude Agent (subagent_type) | Codex | When |
|------|-------------------------------|-------|------|
| **deep** | `deep-spec-reviewer`, `deep-code-reviewer`, `deep-product-reviewer`, `deep-analyst`, `deep-doc-writer`, `deep-implementer` (opus, effort: high) | `-c model_reasoning_effort=xhigh` + `prompts/codex/` | Phase 0 audit, Phase 1 spec review, Phase 2 final holistic, llms.txt/CLAUDE.md generation |
| **standard** | `standard-spec-reviewer`, `standard-code-reviewer`, `standard-product-reviewer`, `standard-doc-writer`, `standard-implementer` (opus, effort: medium) | `-c model_reasoning_effort=high` + `prompts/codex/` | Phase 1 plan review, Phase 2 unified review, Phase 3 doc updates |
| **fast** | `fast-implementer` (sonnet, effort: low) | `-c model_reasoning_effort=medium` | Simple implementation tasks |

Agent definitions with effort frontmatter are deployed to `~/.claude/agents/` during Phase 0 Step 1. The Agent() tool does NOT accept an inline `effort` parameter — effort is controlled via agent definition files only.

## Rationalization Prevention

If you think any of these, STOP and do the thing:
- "I'll write the code directly" → dispatch subagent
- "Too simple for a worktree" → create worktree
- "Two reviewers is enough" → dispatch all 4 reviewers
- "I'll ask the user during Phase 2" → Phase 2 is autonomous
- "One big PR is easier" → one PR per sprint
- "This sprint is too small for PAR" → run PAR
- "Per-sprint PAR is enough" → run Final Holistic Review

## Product Approval Gate

Before writing a spec, present Product Summary (features, problems solved, out of scope). Wait for user approval.

## Phase 0 Gate

On first run (no Superflow artifacts detected), Phase 0 is mandatory. Do not skip to Phase 1 without completing onboarding. See `references/phase0-onboarding.md`.

## Phase 3 Gate

After Phase 2 Completion Report, do not merge without user saying "merge" / "мёрдж". Merge follows strict order: sequential, rebase, CI green, docs updated. See `references/phase3-merge.md`.

## Telegram Progress

When MCP connected: send short updates at sprint start, PR created, errors/blockers, completion. Acknowledge receipt before background work.

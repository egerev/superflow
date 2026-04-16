# Codex Dispatch Patterns — Complete Reference

Lookup table mapping every Agent() dispatch in Superflow to its Codex spawn_agent equivalent.

## Agent Dispatch Mapping

| Phase | Step | Agent Definition | Codex Dispatch |
|-------|------|------------------|----------------|
| P0 S2 | Architecture analysis | deep-analyst | spawn_agent("deep-analyst") |
| P0 S2 | Code quality analysis | deep-analyst | spawn_agent("deep-analyst") |
| P0 S2 | Security audit | deep-analyst | spawn_agent("deep-analyst") + `claude -p` secondary |
| P0 S2 | DevOps analysis | fast-implementer | spawn_agent("fast-implementer") |
| P0 S2 | Documentation analysis | deep-analyst | spawn_agent("deep-analyst") |
| P0 S4 | Branch A (docs) | deep-doc-writer | spawn_agent("deep-doc-writer") |
| P0 S4 | Branch B (permissions) | fast-implementer | spawn_agent("fast-implementer") |
| P0 S4 | Branch C (scaffolding) | fast-implementer | spawn_agent("fast-implementer") |
| P0 GF | G3 scaffold | fast-implementer | spawn_agent("fast-implementer") |
| P0 GF | G4 docs | deep-doc-writer | spawn_agent("deep-doc-writer") |
| P0 GF | G5 env setup | fast-implementer | spawn_agent("fast-implementer") |
| P1 S3 | Domain research | deep-analyst | spawn_agent("deep-analyst") |
| P1 S3 | Product research | deep-analyst | `claude -p` (secondary) or spawn_agent |
| P1 S5 | Expert: Product GM | deep-analyst | spawn_agent("deep-analyst") |
| P1 S5 | Expert: Staff Engineer | deep-analyst | spawn_agent("deep-analyst") |
| P1 S5 | Expert: UX/Workflow | deep-analyst | spawn_agent("deep-analyst") |
| P1 S5 | Expert: Domain | deep-analyst | `claude -p` (secondary) or spawn_agent |
| P1 S9 | Spec review (product) | deep-product-reviewer | spawn_agent("deep-product-reviewer") |
| P1 S9 | Spec review (tech) | — | `claude -p` + prompts/claude/code-reviewer.md |
| P1 S11 | Plan review (product) | standard-product-reviewer | spawn_agent("standard-product-reviewer") |
| P1 S11 | Plan review (tech) | — | `claude -p` + prompts/claude/code-reviewer.md |
| P2 | Implementer (simple) | fast-implementer | spawn_agent("fast-implementer") |
| P2 | Implementer (medium) | standard-implementer | spawn_agent("standard-implementer") |
| P2 | Implementer (complex) | deep-implementer | spawn_agent("deep-implementer") |
| P2 | Unified review (product) | standard-product-reviewer | spawn_agent("standard-product-reviewer") |
| P2 | Unified review (tech) | — | `claude -p` + prompts/claude/code-reviewer.md |
| P2 | Doc update | standard-doc-writer | spawn_agent("standard-doc-writer") |
| P2 | Holistic (product) | deep-product-reviewer | spawn_agent("deep-product-reviewer") |
| P2 | Holistic (tech) | — | `claude -p` + prompts/claude/code-reviewer.md |

## Secondary Provider Inversion

| Context | Claude orchestrator (Codex secondary) | Codex orchestrator (Claude secondary) |
|---------|---------------------------------------|---------------------------------------|
| Security audit | `codex exec --full-auto` + `prompts/codex/audit.md` | `claude -p` + `prompts/claude/audit.md` |
| Code review | `codex exec review --base main --ephemeral` | `claude -p` + `prompts/claude/code-reviewer.md` |
| Product review | `codex exec` + `prompts/codex/product-reviewer.md` | `claude -p` + `prompts/claude/product-reviewer.md` |
| Spec review | `codex exec --full-auto --ephemeral` | `claude -p` + `prompts/claude/code-reviewer.md` |
| Plan review | `codex exec --full-auto --ephemeral` | `claude -p` + `prompts/claude/code-reviewer.md` |

## Split-Focus Fallback (no secondary provider)

| Context | Agent A (Product) | Agent B (Technical) |
|---------|-------------------|---------------------|
| Spec review | deep-product-reviewer | deep-spec-reviewer |
| Plan review | standard-product-reviewer | standard-spec-reviewer |
| Unified review | standard-product-reviewer | standard-code-reviewer |
| Holistic review | deep-product-reviewer | deep-code-reviewer |

Record `"provider": "split-focus"` in .par-evidence.json.

## Model Tier Mapping

| Claude Tier | Claude Model | Claude Effort | Codex Model | Codex Reasoning |
|-------------|-------------|---------------|-------------|-----------------|
| deep | opus | max | gpt-5.4 | high |
| standard | opus | high | gpt-5.4 | high |
| fast | sonnet | low | gpt-5.4-mini | medium |
| implementer (deep) | sonnet | max | gpt-5.4-mini | high |
| implementer (std) | sonnet | high | gpt-5.4-mini | high |
| implementer (fast) | sonnet | low | gpt-5.4-mini | medium |

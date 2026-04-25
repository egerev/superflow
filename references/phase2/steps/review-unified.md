# Step: review-unified

**Stage:** review
**Loaded by orchestrator:** when entering the review stage
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Two-Reviewer Protocol

Principle: **specialize, don't duplicate** — Claude = Product lens, secondary = Technical lens.

First, look up `decision_matrix.review_config[governance_mode+"+"+complexity]` in `workflow.json`:
- `reviewers: 1` → Technical only (skip product reviewer)
- `reviewers: 2` → Both Product + Technical in parallel
- `tier` → `standard` or `deep` agent definitions

Both agents receive: the SPEC, the product brief, and the relevant git diff.

## With Codex Available (`codex --version 2>/dev/null` exits 0)

```
a. Agent(subagent_type: "standard-product-reviewer", run_in_background: true,
         prompt: "[SPEC + brief + diff context]")
b. $TIMEOUT_CMD 600 codex exec review --base main -c model_reasoning_effort=high --ephemeral \
     - < <(echo "SPEC_CONTEXT" | cat - prompts/codex/code-reviewer.md) 2>&1  [run_in_background]
```
For deep tier, use `deep-product-reviewer` and `model_reasoning_effort=high`.

## Without Codex (Split-Focus Fallback — 2 Claude Agents)

```
a. Agent(subagent_type: "standard-product-reviewer", run_in_background: true,
         prompt: "Focus: spec fit, user scenarios, data integrity")
b. Agent(subagent_type: "standard-code-reviewer", run_in_background: true,
         prompt: "Focus: correctness, security, architecture, performance")
```
Record `"provider": "split-focus"` in `.par-evidence.json`.

## Wait, Aggregate, Fix

Wait for both agents. Aggregate findings:
- CRITICAL / REQUEST_CHANGES from either agent = fix required
- Fix confirmed issues one at a time. Re-run ONLY the agent that flagged issues.
- If a finding is incorrect (reviewer lacked context), record disagreement with technical reasoning
  in the PR description and skip that fix. Do NOT fix based on incorrect context.

After all fixes: run full test suite. Paste actual output as evidence (enforcement rule 4).

## Light Mode (par_skip_product: true)

When `par_skip_product=true` (light governance), run Technical reviewer only.
PAR evidence: `{"claude_product":"SKIPPED","technical_review":"APPROVE","governance":"light",...}`

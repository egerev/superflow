# Step: review-unified

**Stage:** review
**Loaded by orchestrator:** when entering the review stage
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## Preferred Path — Saved /superflow-review Workflow (Claude runtime, opt-in)

When ALL hold — RUNTIME:claude, `context.use_workflows=true` in `.superflow-state.json`, and
workflows available (not `disableWorkflows`, not `CLAUDE_CODE_DISABLE_WORKFLOWS=1`, CLI version
≥ 2.1.154) — PREFER invoking the saved `/superflow-review` workflow over manual two-agent dispatch:

```
/superflow-review  args: {sprint: <N>, branch: "<branch>", base: "<base>",
                          charter_path: "<charter file>",
                          workdir: "<abs path to sprint worktree>",
                          spec_path: "<sprint spec/plan file>",   (optional but STRONGLY recommended — enables spec-fit + plan-completeness)
                          plan_path: "<sprint plan tasks file>",  (optional — reviewers verify each task is implemented, not stubbed)
                          brief_path: "<product brief file>",     (optional — product lens)
                          product: <true|false>,   (false for light-governance cells)
                          diff_hint: "<optional scope hint>"}
```

Light-governance cells (`par_skip_product: true`): pass `product: false` — the workflow runs
only the technical thunk and returns `{product: null, technical, pass}`. Standard and critical
cells: pass `product: true` (the default).

The workflow runs the product reviewer and the technical reviewer (which applies the codex-CLI
fallback chain itself) in parallel and returns `{product, technical, pass}` — verdicts already
extracted from the fenced JSON blocks, failing closed (REQUEST_CHANGES) on parse failure. Consume
the returned verdicts directly and assemble `.par-evidence.json` from them with
`provider: "workflow-review"` (see `par-evidence.md`). If verdicts fail: fix confirmed issues,
commit, then re-invoke `/superflow-review` (fresh run) or re-review only the flagging lens via the
Agent-based flow below. Do not re-explain workflow internals here — the single authority is
`references/workflow-orchestration.md`.

**Fallback:** in every other case (Codex runtime, `use_workflows=false`, workflows disabled or
unavailable) run the existing Agent-based flow below verbatim — no behavior change.

## Two-Reviewer Protocol

Principle: **specialize, don't duplicate** — Claude = Product lens, secondary = Technical lens.

First, look up `decision_matrix.review_config[governance_mode+"+"+complexity]` in `workflow.json`:
- `reviewers: 1` → Technical only (skip product reviewer)
- `reviewers: 2` → Both Product + Technical in parallel
- `tier` → `standard` or `deep` agent definitions

Both agents receive a COMPLETE context bundle — never just the diff:
- the SPEC / sprint plan tasks (for spec fit AND the plan-completeness check — the **technical** reviewer
  needs this too, not only the product reviewer; a diff without the plan cannot reveal a stub),
- the Autonomy Charter (non-negotiables, success criteria),
- the Product Brief (product lens),
- the relevant git diff.

Paste these into the dispatch `prompt:` verbatim — do NOT rely on the agent recalling the plan. The agent
definitions reserve `<spec_or_plan>` + `<autonomy_charter>` (code reviewer) and
`<original_spec>` + `<product_brief>` + `<autonomy_charter>` (product reviewer) context slots for exactly this.

**Dispatch Claude reviewers as NAMED background agents** so they can be re-engaged after fixes
with their original context intact:

```
Agent(
  subagent_type: "standard-product-reviewer",  # deep-product-reviewer for deep tier
  model: "opus",                               # standard tier; deep tier also "opus" (effort: max via agent definition; Fable blocked)
  name: "sprint-<N>-product-reviewer",
  run_in_background: true,
  prompt: "[SPEC/plan tasks + Product Brief + Autonomy Charter + git diff — fill the agent's <original_spec>/<product_brief>/<autonomy_charter> slots verbatim]"
)
```

## Technical Lens — Fallback Chain

1. **Primary — Codex** (`codex --version 2>/dev/null` exits 0):
   ```
   $TIMEOUT_CMD 600 codex exec review --base main -m gpt-5.5 -c model_reasoning_effort=high --ephemeral \
        - < <(echo "SPEC_CONTEXT" | cat - prompts/codex/code-reviewer.md) 2>&1  [run_in_background]
   ```
   For deep tier, use `model_reasoning_effort=xhigh` (and `deep-product-reviewer` on the product
   side). Record `"provider": "codex"`.
2. **Fallback — native `/code-review` skill**: invoke via the Skill tool at high effort. Record
   `"provider": "code-review-skill"`. Note: `/code-review ultra` CANNOT be launched by the agent
   (user-triggered, billed) — it is only ever SUGGESTED to the user as an optional extra gate at
   Phase 3 pre-merge.
3. **Last resort — split-focus, 2 Claude agents:**
   ```
   a. Agent(subagent_type: "standard-product-reviewer", model: "opus",
            name: "sprint-<N>-product-reviewer", run_in_background: true,
            prompt: "Focus: spec fit, user scenarios, data integrity. Context (fill the agent's slots verbatim): SPEC/plan tasks + Product Brief + Autonomy Charter + git diff")
   b. Agent(subagent_type: "standard-code-reviewer", model: "opus",
            name: "sprint-<N>-technical-reviewer", run_in_background: true,
            prompt: "Focus: correctness, security, architecture, performance. Context (fill <spec_or_plan>/<autonomy_charter> verbatim): SPEC/plan tasks + Autonomy Charter + git diff")
   ```
   Record `"provider": "split-focus"` in `.par-evidence.json`.

## Verdict Contract (Mechanical Extraction)

Every reviewer agent ends its final message with a fenced `json` block:

```json
{
  "verdict": "APPROVE|ACCEPTED|PASS|REQUEST_CHANGES|NEEDS_FIXES|FAIL",
  "findings": [
    {"severity": "critical|high|medium|low", "file": "...", "line": 0,
     "scenario": "breakage scenario", "description": "..."}
  ],
  "summary": "..."
}
```

The orchestrator extracts it mechanically — no prose parsing:

```bash
# review-output.txt holds the reviewer's final message:
awk '/^```json$/{f=1; buf=""; next} /^```/{f=0; next} f{buf=buf $0 ORS} END{printf "%s", buf}' \
  review-output.txt | jq -r '.verdict'
```

`.par-evidence.json` is assembled from these verdict fields — see `par-evidence.md`. A reviewer
reply without a parseable verdict block is not a verdict: re-engage that reviewer and ask for the
block.

## Wait, Aggregate, Fix

Wait for both agents. Aggregate the JSON `findings` arrays:
- Any REQUEST_CHANGES / NEEDS_FIXES / FAIL verdict, or any critical finding = fix required
- Fix confirmed issues one at a time. Re-review ONLY the agent that flagged issues.
- If a finding is incorrect (reviewer lacked context), record disagreement with technical reasoning
  in the PR description and skip that fix. Do NOT fix based on incorrect context.

**Re-review via SendMessage.** After fixes, re-engage the SAME named background reviewer — its
original context is intact — scoped to the fix diff plus its original findings:

```
SendMessage(
  to: "sprint-<N>-product-reviewer",
  message: "Fixes applied. Re-review scoped to this diff: [fix diff].
            Your original findings: [findings JSON from the verdict block].
            Reply with an updated verdict block."
)
```

Cold re-dispatch (fresh Agent call with the fix diff + original findings) is the fallback if the
agent is gone. For Codex technical reviews, commit the fixes first (secondary providers see only
committed HEAD), then re-run `codex exec review` against the updated HEAD.

After all fixes: run full test suite. Paste actual output as evidence (enforcement rule 4).

## Light Mode (par_skip_product: true)

When `par_skip_product=true` (light governance), run Technical reviewer only.
PAR evidence: `{"claude_product":"SKIPPED","technical_review":"APPROVE","governance":"light",...}`

## Frontend Sprints

If frontend changes shipped in this sprint, verify visual evidence per `frontend-testing.md`
before issuing a review verdict. APPROVE is blocked without screenshot or recording evidence.

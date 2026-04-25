# Step: par-evidence

**Stage:** par
**Loaded by orchestrator:** when entering the PAR evidence step
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## PAR Evidence Schema

Write `.par-evidence.json` in the worktree root **after docs review passes** (docs stage must
complete before this stage). Required fields:

- `sprint` — sprint number
- `governance` — `"light"`, `"standard"`, or `"critical"` (mandatory)
- `complexity` — `"simple"`, `"medium"`, or `"complex"` (mandatory; from the plan section)
- `par_skip_product` — `true` or `false` (mandatory; copied from decision_matrix lookup)
- `claude_product` — product review verdict
- `technical_review` — technical review verdict
- `docs_update` — `"UPDATED"` or `"UNCHANGED"`
- `docs_review` — `"PASS"`
- `provider` — `"codex"`, `"split-focus"`, etc.
- `ts` — ISO timestamp

Standard/critical sprint example:

```json
{
  "sprint": 1,
  "governance": "standard",
  "complexity": "medium",
  "par_skip_product": false,
  "claude_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "docs_update": "UPDATED",
  "docs_review": "PASS",
  "provider": "codex",
  "ts": "2026-01-01T00:00:00Z"
}
```

Light governance sprint example (`par_skip_product: true`):

```json
{
  "sprint": 1,
  "governance": "light",
  "complexity": "simple",
  "par_skip_product": true,
  "claude_product": "SKIPPED",
  "technical_review": "APPROVE",
  "docs_update": "UNCHANGED",
  "docs_review": "PASS",
  "provider": "split-focus",
  "ts": "2026-01-01T00:00:00Z"
}
```

`claude_product: "SKIPPED"` is ONLY valid when `par_skip_product: true` AND `governance: "light"`.
For standard or critical sprints, regardless of complexity, `claude_product` MUST be `"ACCEPTED"`.

## Verdict Mapping

| Verdict from agent | Meaning | Action |
|--------------------|---------|--------|
| APPROVE / ACCEPTED / PASS | Pass | Record in evidence, continue |
| REQUEST_CHANGES / NEEDS_FIXES / FAIL | Fail | Fix confirmed issues, re-run that agent |

Both verdicts must be APPROVE/ACCEPTED/PASS before writing evidence.
If any agent returned issues, fix and re-run that agent before writing `.par-evidence.json`.

## No Secondary Provider

When Codex/secondary unavailable, split-focus fallback:
- Agent A (Product): `standard-product-reviewer` — spec fit, user scenarios, data integrity
- Agent B (Technical): `standard-code-reviewer` — correctness, security, architecture

Record: `{"provider":"split-focus","claude_product":"ACCEPTED","technical_review":"APPROVE",...}`

## Gate Before `gh pr create`

**`gh pr create` is BLOCKED until `.par-evidence.json` exists** with all required fields passing.

Verify with:
```bash
jq -e '
  # technical reviewer always required
  (.technical_review == "APPROVE") and
  # docs gate
  ((.docs_update == "UPDATED") or (.docs_update == "UNCHANGED")) and
  (.docs_review == "PASS") and
  # product verdict policy
  (
    if (.par_skip_product == true) then
      # only valid in light governance
      (.governance == "light") and (.claude_product == "SKIPPED" or .claude_product == "ACCEPTED")
    else
      # standard or critical: product verdict must pass
      (.claude_product == "ACCEPTED")
    end
  )
' .par-evidence.json && echo "PAR gate: PASS"
```

`claude_product: "SKIPPED"` is valid ONLY when `par_skip_product == true` AND `governance == "light"`.
For standard or critical sprints, regardless of complexity, `claude_product` must be `"ACCEPTED"`.

# Step: par-evidence

**Stage:** par
**Loaded by orchestrator:** when entering the PAR evidence step
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## PAR Evidence Schema

Write `.par-evidence.json` in the worktree root after all review fixes are confirmed:

```json
{
  "sprint": 1,
  "claude_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "docs_update": "UPDATED",
  "docs_review": "PASS",
  "provider": "codex",
  "ts": "2026-01-01T00:00:00Z"
}
```

When governance mode is light (`par_skip_product: true`), set `claude_product` to `"SKIPPED"`:

```json
{
  "sprint": 1,
  "claude_product": "SKIPPED",
  "technical_review": "APPROVE",
  "docs_update": "UNCHANGED",
  "docs_review": "PASS",
  "governance": "light",
  "provider": "split-focus",
  "ts": "2026-01-01T00:00:00Z"
}
```

`claude_product: "SKIPPED"` is only valid when the decision matrix lookup for the current sprint
returned `par_skip_product: true`. In all other cases `claude_product` must be `"ACCEPTED"`.

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
  (.technical_review == "APPROVE") and
  (.docs_update == "UPDATED" or .docs_update == "UNCHANGED") and
  (.docs_review == "PASS") and
  (
    (.claude_product == "ACCEPTED") or
    (.claude_product == "SKIPPED")
  )
' .par-evidence.json && echo "PAR gate: PASS"
```

Note: `claude_product: "SKIPPED"` is accepted by the verifier but is only legitimate when
`par_skip_product: true` was set by the decision matrix for this sprint's governance+complexity.

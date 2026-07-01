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
- `provider` — `"codex"`, `"code-review-skill"`, `"split-focus"`, or `"workflow-review"`
- `ts` — ISO timestamp
- `release_gate` — (optional per sprint; **required in the final pre-Phase-3 evidence**) — `"PASS"`, `"SKIPPED"`, or `"FAIL"`. Copied from `.superflow/release-gate/verdict.json` after the gate runs (post-sprint-loop, pre-completion-report). Per-sprint PAR may omit this field; the Phase 3 gate reads `verdict.json` directly (authoritative) and expects `release_gate` in the final `.par-evidence.json` as an audit trail.

Standard/critical sprint example (mid-run — no release_gate yet):

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

Final pre-Phase-3 evidence (after release gate runs — `release_gate` required):

```json
{
  "sprint": 3,
  "governance": "standard",
  "complexity": "medium",
  "par_skip_product": false,
  "claude_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "docs_update": "UPDATED",
  "docs_review": "PASS",
  "provider": "codex",
  "release_gate": "PASS",
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

## Mechanical Assembly from Verdict Blocks

`.par-evidence.json` is assembled mechanically from the reviewers' fenced JSON verdict blocks
(see `review-unified.md` § Verdict Contract) — never from prose. Extract each verdict, then build
the file with jq:

```bash
extract_verdict() {  # $1 = file holding the reviewer's final message
  awk '/^```json$/{f=1; buf=""; next} /^```/{f=0; next} f{buf=buf $0 ORS} END{printf "%s", buf}' \
    "$1" | jq -r '.verdict'
}

PRODUCT=$(extract_verdict product-review.txt)   # use "SKIPPED" when par_skip_product+light
TECH=$(extract_verdict technical-review.txt)

jq -n \
  --argjson sprint "$SPRINT_NUM" \
  --arg governance "$GOVERNANCE" \
  --arg complexity "$COMPLEXITY" \
  --argjson skip "$PAR_SKIP_PRODUCT" \
  --arg product "$PRODUCT" \
  --arg tech "$TECH" \
  --arg docs_update "$DOCS_UPDATE" \
  --arg docs_review "$DOCS_REVIEW" \
  --arg provider "$PROVIDER" \
  '{sprint: $sprint, governance: $governance, complexity: $complexity,
    par_skip_product: $skip, claude_product: $product, technical_review: $tech,
    docs_update: $docs_update, docs_review: $docs_review, provider: $provider,
    ts: (now | todate)}' > .par-evidence.json
```

If a reviewer's message has no parseable verdict block, that is not a verdict — re-engage the
reviewer (SendMessage, see `review-unified.md`) for the block instead of inferring one from prose.

Workflow path: when review ran via the saved `/superflow-review` workflow, `product` and
`technical` in the return value are full verdict objects (same shape as the fenced-JSON block).
Evidence fields take the `.verdict` string — e.g. `PRODUCT=$(jq -r '.product.verdict' <<<"$WF_RESULT")`,
`TECH=$(jq -r '.technical.verdict' <<<"$WF_RESULT")`. Skip `extract_verdict` and record
`provider: "workflow-review"`. When `product:false` was passed, `product` is `null` — set
`PRODUCT="SKIPPED"` directly.

## Verdict Mapping

| Verdict from agent | Meaning | Action |
|--------------------|---------|--------|
| APPROVE / ACCEPTED / PASS | Pass | Record in evidence, continue |
| REQUEST_CHANGES / NEEDS_FIXES / FAIL | Fail | Fix confirmed issues, re-run that agent |

Both verdicts must be APPROVE/ACCEPTED/PASS before writing evidence.
If any agent returned issues, fix and re-run that agent before writing `.par-evidence.json`.

## No Secondary Provider

Technical-lens fallback chain when `codex exec review` is unavailable:

1. **Native `/code-review` skill** — invoke via the Skill tool at `high` effort (technical lens only). Record `provider: "code-review-skill"`.
2. **Split-focus Claude agents** (last resort when Skill tool also unavailable):
   - Agent A (Product): `standard-product-reviewer` — spec fit, user scenarios, data integrity
   - Agent B (Technical): `standard-code-reviewer` — correctness, security, architecture
   Record `provider: "split-focus"`.

Examples:
- Codex → `{"provider":"codex","claude_product":"ACCEPTED","technical_review":"APPROVE",...}`
- /code-review skill → `{"provider":"code-review-skill","claude_product":"ACCEPTED","technical_review":"APPROVE",...}`
- Split-focus → `{"provider":"split-focus","claude_product":"ACCEPTED","technical_review":"APPROVE",...}`
- /superflow-review workflow → `{"provider":"workflow-review","claude_product":"ACCEPTED","technical_review":"APPROVE",...}`

## Gate Before `gh pr create`

**`gh pr create` is BLOCKED until `.par-evidence.json` exists** with all required fields passing.

Verify with:
```bash
jq -e '
  # required fields presence + types
  (has("sprint") and (.sprint | type) == "number") and
  (has("governance") and (.governance | IN("light", "standard", "critical"))) and
  (has("complexity") and (.complexity | IN("simple", "medium", "complex"))) and
  (has("par_skip_product") and (.par_skip_product | type) == "boolean") and
  (has("technical_review") and (.technical_review == "APPROVE")) and
  (has("docs_update") and (.docs_update | IN("UPDATED", "UNCHANGED"))) and
  (has("docs_review") and (.docs_review == "PASS")) and
  (has("claude_product") and (.claude_product | type) == "string") and
  (has("provider") and (.provider | type) == "string") and
  (has("ts") and (.ts | type) == "string") and
  # product verdict policy
  (
    if (.par_skip_product == true) then
      (.governance == "light") and (.claude_product | IN("SKIPPED", "ACCEPTED"))
    else
      (.claude_product == "ACCEPTED")
    end
  )
' .par-evidence.json && echo "PAR gate: PASS"
```

`claude_product: "SKIPPED"` is valid ONLY when `par_skip_product == true` AND `governance == "light"`.
For standard or critical sprints, regardless of complexity, `claude_product` must be `"ACCEPTED"`.

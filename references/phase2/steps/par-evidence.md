# Step: par-evidence

**Stage:** par
**Loaded by orchestrator:** when entering the PAR evidence step
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 1)

---

## PAR Evidence Schema

Write `.par-evidence.json` in the worktree root after all review fixes are confirmed:

```json
{
  "sprint": N,
  "claude_product": "ACCEPTED",
  "technical_review": "APPROVE",
  "provider": "codex",
  "ts": "ISO-8601"
}
```

Optional fields:
- `"docs_update": "UPDATED"` or `"UNCHANGED"` — set by doc-update agent
- `"docs_review": "PASS"` — set after documentation review
- `"governance": "light"` — add when governance mode is light

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

Record: `{"provider":"split-focus","claude_product":"ACCEPTED","technical_review":"APPROVE","ts":"..."}`

## Gate Before `gh pr create`

**`gh pr create` is BLOCKED until `.par-evidence.json` exists** with:
- Both verdicts passing (APPROVE/ACCEPTED/PASS)
- `docs_update` field set (UPDATED or UNCHANGED)
- `docs_review` = PASS

Verify with: `python3 -c "import json; e=json.load(open('.par-evidence.json')); assert e['technical_review'] in ('APPROVE','PASS')"`

# Step: frontend-testing

**Stage:** implementation + review (cross-cutting)
**Loaded by orchestrator:** when `frontend: true` is set in the sprint plan
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 2 content restoration)

---

## When This Applies

When a sprint modifies frontend code (HTML, CSS, JS, React components, templates) and the sprint
plan tags it with `frontend: true`, this protocol is mandatory.

## Implementation Phase: Visual Verification

After implementation and before review, run visual verification:

1. Use `/webapp-testing` skill (Playwright MCP) — installed during Phase 0 for frontend projects
2. Open the affected page(s) in a browser session
3. Interact with changed components to confirm behavior
4. Take a screenshot (or recording) as evidence of the UI state
5. If a visual regression is detected, fix it before proceeding to review

**Detection:** The sprint prompt includes `{frontend_instructions}` when `frontend: true` — this
tells the implementer agent to verify UI changes visually using Playwright before finishing.

## Review Phase: Visual Evidence Check

When reviewing a frontend sprint, the reviewer must verify:
- Screenshot or recording is attached to the PR description (or linked)
- The evidence matches the spec's expected UI behavior
- No visual regressions introduced (compare to baseline if available)

A review verdict of APPROVE is blocked if no visual evidence is present for a `frontend: true`
sprint.

## Skill Required

`/webapp-testing` (Playwright-based). Must be installed during Phase 0 onboarding for projects
with a frontend stack. If not installed, run Phase 0 or install manually before this sprint.

## PR Description Requirement

Include in the PR body:
- Screenshot URL or inline image (GitHub supports drag-and-drop PNG)
- Which pages/components were verified
- Any known visual limitations or deferred polish items

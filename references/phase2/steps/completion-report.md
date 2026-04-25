# Step: completion-report

**Stage:** completion
**Loaded by orchestrator:** when writing the final Phase 2 completion report
**Source extracted from:** references/phase2-execution.md (during Run 3 Sprint 2 content restoration)

---

## Product Release Format

Present as a **product release report** — what the team built for users, not a sprint log. Think
"release notes for stakeholders", not "git log for developers".

### Structure

**1. What's New** — the headline features, grouped by user value (not by sprint):

For each feature group:
- **Feature name** — what it does in 1-2 sentences, user language
- Concrete capabilities: bullet list of what the user can now do that they couldn't before
- How it works: brief explanation of the mechanism (1-2 sentences max)

**2. How It Works Together** — explain how the features connect as a system. This is the
"architecture for humans" section: what happens when a user runs the tool end-to-end.

**3. Technical Summary** (collapsed/brief):
- PRs: list with links and status
- Git workflow: selected mode, PR count, and any sequential fallback from planned parallelism
- Tests: total count, all passing
- Review: holistic review verdict
- Known limitations or follow-ups

**4. What's Next** — suggested next action: "Ready to merge — say 'merge' to start Phase 3"

```bash
sf_emit phase.end phase:int=2 label="Autonomous Execution"
```

### Tone

- Write for someone who will USE the product, not someone who reviewed the PRs
- Lead with user value, not implementation details
- Group by what changed for the user, not by sprint boundaries
- Concrete examples > abstract descriptions
- Skip internal process details (PAR, worktrees, review rounds) — those are for PR descriptions

**Note on `pr.merge`:** The `pr.merge` event is emitted during Phase 3 merge, not Phase 2.
See `references/phase3-merge.md` for placement.

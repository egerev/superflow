# Phase 0 Rewrite — Technical Design

References: [Product Brief](2026-03-25-phase0-rewrite-brief.md)

## Overview

Restructure Phase 0 from a 1,395-line monolith (`references/phase0-onboarding.md`) into ~7 modular stage files loaded on demand. Add parallel preflight, delegate mechanical tasks to Sonnet (permissions, hooks, scaffolding — NOT documentation), and simplify user interaction to a lightweight confirmation with auto-detected values.

## New Stage Structure

Current 6 stages with mixed numbering (Steps 1, 1.5, 2, 3, 3.5, 4, 5, 5.5, 6, 6.5, 7, 7.5, 7.7, 8, 8.5, 9, 10) → clean 5 stages with sequential numbering.

### Proposed Stages

```
Stage 1: "Detect & Confirm" (~100 lines)
  - Parallel preflight: markers, partial completion, empty/existing, stack, PM, CI, python3, formatters, existing docs
  - Auto-detect: team size (git log authors), CI (.github/workflows/), stack (imports + manifests)
  - Present detected values to user for confirmation:
    "Detected: Python + FastAPI, solo developer, no CI. I'll audit docs, code quality, security. ~2 min."
    [Confirm / Correct something / Skip Phase 0]
  - "Correct something" → free text, update $PREFLIGHT, re-confirm
  - "Skip" → write markers with defaults, proceed to Phase 1 immediately
  - Persist $PREFLIGHT + user corrections to .superflow-state.json
  - If greenfield detected → load phase0/greenfield.md, exit this flow
  - Write .superflow-state.json at Phase 0 start, update at each stage transition

Stage 2: "Analysis" (~100 lines)
  - 5 parallel agents: Architecture, Code Quality, DevOps, Documentation, Security
  - Architecture + Code Quality + Security = Opus deep-analyst (requires import verification, pattern detection)
  - DevOps = Sonnet fast-implementer (file existence checks, config reading — mechanical)
  - Documentation = Opus deep-analyst (doc quality requires framework verification — Sonnet hallucinates names)
  - All agents receive $PREFLIGHT (detected stack, team size, experience) for context-aware analysis
  - Cross-check synthesis after all complete
  - Output: internal evidence bundle (not shown to user yet)

Stage 3: "Report & Proposal" (~100 lines)
  - Generate health report → save to docs/superflow/project-health-report.md
  - Show user INFORMATIVE summary (not wall of text, not 2 words):
    - Stack detected + evidence
    - ALL security issues (highlighted prominently, not just top 3)
    - Top 3 other findings (code quality, architecture, tests)
    - Tech debt summary (saved for Phase 1)
    - What will be created/updated (CLAUDE.md, llms.txt)
    - Permissions to be added (list specific wildcards: git *, gh *, npm *, etc.)
    - Hooks to be configured (formatter name + trigger)
  - Approval with explicit permissions preview:
    "These broad permissions (git *, gh *, npm *) allow autonomous execution without prompts.
     Tradeoff: autonomy vs safety. Decline to keep manual approval."
    [Approve all / Customize / Skip setup]
  - "Customize" → show checklist of items, user toggles each
  - "Skip setup" → write docs only, skip permissions/hooks/plugins

Stage 4: "Documentation & Environment" (~140 lines)
  - Parallel with STRICT FILE OWNERSHIP (no two branches write same file):
    - Branch A (Opus deep-doc-writer): llms.txt audit/create + CLAUDE.md audit/create
      Writes: llms.txt, CLAUDE.md (project root)
      Requires Opus — doc quality is foundation for all future sessions
    - Branch B (Sonnet): permissions → ~/.claude/settings.json + hooks → .claude/settings.json
      Writes: ~/.claude/settings.json (user-level), .claude/settings.json (project-level)
      Only executes items approved in Stage 3 proposal
      No user interaction — approval already obtained in Stage 3
    - Branch C (Sonnet): /verify skill + CLAUDE.local.md + enforcement rules + .gitignore
      Writes: .claude/skills/verify/SKILL.md, CLAUDE.local.md, .gitignore
  - All three branches run concurrently via background agents
  - Orchestrator waits for all, validates results
  - Skills + plugins recommendations (brief, stack-relevant) — shown by orchestrator, not branch

Stage 5: "Completion" (~50 lines)
  - Write markers in all touched files
  - Persist tech debt to .superflow-state.json under .context.tech_debt (matches existing schema pattern)
  - Update .superflow-state.json: phase=1, stage="research" (ready for Phase 1)
  - Summary of what was done (informative, 5-8 lines)
  - Clear instruction: "Run /clear, then /superflow to start Phase 1"
```

**Target: ~490 lines** (aspiration, not constraint; vs 1,395 current for existing project path)

### Greenfield Path

Moves to `references/phase0/greenfield.md` (under same directory as other stage files). Stage 1 routes to it when empty project detected. After greenfield completes, it rejoins at Stage 4 (Documentation & Environment).

## File Structure

### New Files
```
references/
  phase0-onboarding.md          — Router: detection + partial completion check + stage loading (~80 lines)
                                   Keeps same path as before (no broken references)
  phase0/
    stage1-detect.md             — Preflight + confirmation (~100 lines)
    stage2-analysis.md           — 5 parallel agents (~100 lines)
    stage3-report.md             — Health report + proposal + approval flows (~100 lines)
    stage4-setup.md              — Docs + environment (parallel, strict file ownership) (~140 lines)
    stage5-completion.md         — Markers + state persist + restart instruction (~50 lines)
    greenfield.md                — Greenfield path (moved from phase0-onboarding.md, ~280 lines)
```

### Kept Files (rewritten)
```
references/phase0-onboarding.md  — Rewritten as thin router (~80 lines, was 1,395)
```

### Modified Files
```
SKILL.md                         — Update phase0 reference path
CLAUDE.md                        — Update architecture diagram, file table
superflow-enforcement.md         — Update Phase 0 Gate reference
llms.txt                         — Update phase0 entry
README.md                        — Update if phase0 is mentioned
```

## Detailed Changes

### 1. Parallel Preflight (Stage 1)

Replace sequential detection across Steps 1, 1.5, 6, 6.5, 7-detect, 7.5-detect with a single parallel block:

```bash
# All run in parallel while composing the confirmation message
MARKERS=$(grep -l "updated-by-superflow\|superflow:onboarded" CLAUDE.md llms.txt 2>/dev/null)
FILE_COUNT=$(git ls-files | grep -v -E '^\.gitignore$|^\.github/' | wc -l | tr -d ' ')
TEAM_SIZE=$(git log --format='%ae' | sort -u | wc -l | tr -d ' ')
HAS_CI=$(test -d .github/workflows && echo "yes" || echo "no")
HAS_PYTHON=$(python3 --version 2>/dev/null && echo "yes" || echo "no")
STACK=$(detect_from_manifests_and_imports)
PM=$(detect_package_manager)
FORMATTERS=$(detect_formatters)
```

Result cached as `$PREFLIGHT` dict, passed to all subsequent stages.

### 2. Agent Tier Assignment (Stage 2)

| Agent | Current | Proposed | Rationale |
|-------|---------|----------|-----------|
| Architecture | Opus + ultrathink | Opus (deep-analyst) | Needs import verification, pattern detection |
| Code Quality | Opus + ultrathink | Opus (deep-analyst) | Needs dead code detection, duplication analysis |
| Security | Opus/Codex | Opus (deep-analyst) or Codex | Security requires deep reasoning |
| DevOps | Opus + ultrathink | **Sonnet** (fast-implementer) | File existence checks, config reading — mechanical |
| Documentation | Opus + ultrathink | **Opus** (deep-analyst) | Doc quality requires framework verification — Sonnet hallucinates names (recorded feedback) |

**Cost reduction**: 1 of 5 agents downgraded to Sonnet (DevOps only). Documentation stays Opus because wrong documentation is worse than no documentation — this is recorded project feedback that Sonnet hallucinated "LangGraph" from a directory name.

**Note**: Stage 4 Branch A (doc GENERATION) also uses Opus (deep-doc-writer). The analysis agent gathers evidence; the doc writer consumes it. Both need Opus for accuracy.

### 3. Report Format (Stage 3)

Replace the full health report template (50+ lines in terminal) with an informative summary:

```
## Project Audit Complete

**Stack:** Python 3.14 + FastAPI + PostgreSQL (detected from imports in src/)
**Size:** 47 source files, 3,200 LOC across 8 modules

### Key Findings
1. **Security** (2 issues): hardcoded DB password in config.py:42, no rate limiting on /api/auth
2. **Test coverage**: 12 test files / 47 source files (26%). Missing tests for: payments/, notifications/
3. **Tech debt**: 23 TODO/FIXME comments, 3 files >500 LOC (largest: services/billing.py at 847 lines)

### What I'll Set Up
- Create CLAUDE.md + llms.txt (project documentation for AI assistants)
- Configure permissions for autonomous execution
- Set up auto-formatting hooks (ruff detected)
- Create /verify skill (ruff check + pytest)

Full report: docs/superflow/project-health-report.md
```

This is ~15 lines — informative but not overwhelming. Full details in the saved report file.

### 4. Parallel Documentation & Environment (Stage 4)

Three concurrent branches via `Agent(run_in_background: true)`:

**Branch A — Documentation (Opus deep-doc-writer):**
- Read evidence from Stage 2 analysis
- Audit/create llms.txt (using prompts/llms-txt-writer.md)
- Audit/create CLAUDE.md (using prompts/claude-md-writer.md)

**Branch B — Permissions & Hooks (Sonnet):**
- Use $PREFLIGHT.stack to build permission array
- Use $PREFLIGHT.formatters to select hook template
- Write to settings.json (merge, not overwrite)
- Verify hooks with simple pipe test (not 4-stage verification)

**Branch C — Scaffolding (Sonnet):**
- Create /verify skill from detection table
- Create CLAUDE.local.md
- Verify enforcement rules in ~/.claude/rules/
- Check .gitignore completeness

### 5. Tech Debt Persistence (Stage 5)

Write tech debt findings to `.superflow-state.json` under `.context.tech_debt` (matches existing schema pattern where `.context` holds interview answers, detected stack, etc.):

```json
{
  "version": 1,
  "phase": 1,
  "phase_label": "Product Discovery",
  "stage": "research",
  "stage_index": 0,
  "last_updated": "2026-03-25T12:00:00Z",
  "context": {
    "detected_stack": "python-fastapi",
    "team_size": "solo",
    "experience": "intermediate",
    "ci": "no",
    "tech_debt": {
      "total_todos": 23,
      "files_over_500_loc": ["services/billing.py", "models/user.py", "api/routes.py"],
      "untested_modules": ["payments/", "notifications/"],
      "security_issues": 2,
      "generated_at": "2026-03-25T12:00:00Z"
    }
  }
}
```

**State management**: `.superflow-state.json` is written at Phase 0 start and updated at each stage transition (same as current). The `context` object accumulates data through stages — preflight results in Stage 1, analysis results in Stage 2, tech debt in Stage 5. Phase 1 reads `.context.tech_debt` and suggests including relevant tech debt when tasks touch affected modules.

**Partial completion recovery**: Router checks markers + state file. If state says `stage_index: 2` but markers are missing, resume from Stage 3 (skip re-analysis). Schema in `templates/superflow-state-schema.json` must be updated to include `context.tech_debt`.

### 6. Hooks Verification Simplification

Current: 4-stage pipeline (pipe test → settings validation → live proof → e2e smoke test) = ~52 lines.

Proposed: 2-stage verification — (1) check formatter binary exists (`which ruff` / `which prettier`), (2) run formatter on a single test file and verify output changed or passed clean. If binary missing → warn user explicitly ("ruff not found — hook will be inactive until installed"). No silent `|| true` masking. If formatter exists but errors → show error, skip hook with explanation.

### 7. Completion & Restart (Stage 5)

```
## Phase 0 Complete

Created: CLAUDE.md, llms.txt, health report, /verify skill
Configured: permissions (28 commands), hooks (ruff format on save)
Security: 2 issues flagged in health report — review before deploying

**Next step:** Run `/clear` then `/superflow` to start working on your project.
Phase 1 will use the documentation and audit results from this session.
```

## Numbering Convention

All stages use sequential integers. No more X.5 steps.

| Old | New | What |
|-----|-----|------|
| Step 1 + 1.5 | Stage 1 | Detect & Confirm |
| Step 2 + 3 | Stage 2 | Analysis |
| Step 3.5 | Stage 3 | Report & Proposal |
| Steps 4 + 5 + 5.5 + 6 + 6.5 + 7 + 7.5 + 7.7 | Stage 4 | Documentation & Environment |
| Steps 8 + 8.5 + 9 + 10 | Stage 5 | Completion |

## Testing Strategy

- **Existing tests**: `test_supervisor.py` — unaffected (supervisor doesn't orchestrate Phase 0)
- **Manual testing**: Run `/superflow` on a project without markers, verify full flow
- **Verification points**:
  - Stage files load correctly when referenced
  - Preflight detects stack/PM/CI correctly
  - Sonnet agents produce correct docs (compare with Opus baseline)
  - Parallel branches complete without conflicts
  - .superflow-state.json has tech_debt after Phase 0
  - Markers written in all files
  - Greenfield routing works

## Migration

1. Create `references/phase0/` directory with 5 stage files
2. Create `references/phase0/greenfield.md` from existing greenfield sections
3. Replace `references/phase0-onboarding.md` with router (~60 lines)
4. Update all references in SKILL.md, CLAUDE.md, llms.txt, enforcement
5. Test greenfield detection still routes correctly

## Out of Scope

- Supervisor changes
- Phase 1/2/3 changes
- New analysis agents
- Greenfield content changes (just file relocation)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sonnet quality for DevOps agent | Could miss findings Opus catches | DevOps checks are mechanical (file exists/doesn't). Compare on 2-3 real projects |
| Stage file loading adds indirection | Harder to debug flow | Router has clear stage→file mapping, same base path |
| Parallel branch file conflicts | Race conditions if two branches write same file | Strict file ownership — each branch has exclusive write list |
| Context compaction mid-Phase 0 | Stage files small (~100 lines), easy to re-read | State persisted in .superflow-state.json with stage_index |
| Auto-detection wrong (e.g., team size from fork) | Wrong context for agents | User can correct at confirmation step ("Correct something") |
| Permissions approval less explicit | User doesn't understand what they're allowing | Stage 3 lists specific wildcards + tradeoff explanation |

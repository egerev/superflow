# Phase 0: Onboarding (FIRST RUN ONLY)

Runs once per project. Skip if Superflow artifacts already exist (see detection below).

## Detection: Is This a First Run?

Check for Superflow markers:
1. `CLAUDE.md` exists AND contains a `## Superflow` section or `superflow` mention → **skip Phase 0**
2. `docs/superpowers/` directory exists with specs/plans → **skip Phase 0**
3. `.par-evidence.json` exists → **skip Phase 0**

If none found → this is a first run. Announce: "This looks like a new project for Superflow. Let me analyze the codebase first."

## Step 1: Project Analysis

Dispatch parallel background agents:
- **Architecture agent**: scan directory structure, key files, frameworks, dependencies, data model
- **Code quality agent**: identify hotspots, complexity, test coverage, linting setup
- **Documentation agent**: check existing docs (README, CLAUDE.md, comments density, API docs)

Synthesize into a concise project profile.

## Step 2: CLAUDE.md Bootstrap or Update

### If CLAUDE.md doesn't exist:
Create it with:
- Project overview (stack, purpose, architecture)
- Key files table (file → purpose)
- Commands (dev, build, test, lint)
- Conventions discovered (naming, language, patterns)
- Architecture notes (data flow, key modules)

### If CLAUDE.md exists but is stale:
- Cross-reference documented files/paths against actual codebase
- Flag outdated sections (removed files, renamed modules, new patterns)
- Update with corrections, additions, and removals
- Preserve user's custom sections — only touch factual parts

## Step 3: Project Health Report

Present to user:

```
## Project Health Report

### Overview
- Stack: [detected]
- Size: [files, LOC]
- Test coverage: [detected or "no tests found"]

### Strengths
- [what's well-structured]

### Technical Debt
| Priority | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| P0       | ...   | ...      | ...            |
| P1       | ...   | ...      | ...            |
| P2       | ...   | ...      | ...            |

### Recommendations
1. [actionable improvement]
2. [actionable improvement]
3. ...
```

Save report to `docs/superpowers/project-health-report.md`.

## Step 4: Leave Markers

After Phase 0 completes:
1. Ensure CLAUDE.md mentions Superflow (so future runs detect it)
2. The `docs/superpowers/` directory serves as the primary artifact marker

## Then Continue

After Phase 0, proceed to Phase 1 (Product Discovery) as normal.

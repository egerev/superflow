# Phase 0: Onboarding (FIRST RUN — INTERACTIVE)

Runs once per project. Skip if Superflow artifacts already exist (see detection below).
This phase is **conversational** — talk to the user, don't just execute silently.

## Detection: Is This a First Run?

Check for Superflow markers:
1. `CLAUDE.md` exists AND contains `superflow` mention → **skip Phase 0**
2. `docs/superpowers/` directory exists with specs/plans → **skip Phase 0**
3. `.par-evidence.json` exists → **skip Phase 0**

If none found → first run. Begin onboarding.

## Step 1: Greet & Announce

Tell the user:
> "Привет! Это первый запуск Superflow в этом проекте. Дай мне минуту — познакомлюсь с кодовой базой."

Then proceed to analysis.

## Step 2: Project Analysis (background)

Dispatch parallel background agents:
- **Architecture agent**: directory structure, key files, frameworks, dependencies, data model
- **Code quality agent**: hotspots, complexity, test coverage, linting setup
- **Documentation agent**: existing docs (README, CLAUDE.md, comments density, API docs)

Synthesize into a concise project profile.

## Step 3: Present Project Health Report

Show the user the results conversationally — like a colleague who just explored the codebase:

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

## Step 4: CLAUDE.md — Propose, Don't Force

### If CLAUDE.md doesn't exist:
Propose to the user:
> "У проекта нет CLAUDE.md — это файл с инструкциями, который помогает мне (и будущим сессиям) лучше работать с кодом. Предлагаю создать его сейчас — это займёт минуту. Создать?"

If user agrees, create with:
- Project overview (stack, purpose, architecture)
- Key files table (file → purpose)
- Commands (dev, build, test, lint)
- Conventions discovered (naming, language, patterns)
- Architecture notes (data flow, key modules)

### If CLAUDE.md exists but is stale:
Propose updates:
> "CLAUDE.md есть, но я нашёл несколько неточностей: [list]. Обновить?"

- Cross-reference documented files/paths against actual codebase
- Flag outdated sections (removed files, renamed modules, new patterns)
- Preserve user's custom sections — only touch factual parts

### If CLAUDE.md is up to date:
> "CLAUDE.md в порядке, всё актуально."

## Step 5: Leave Markers

After Phase 0 completes:
1. Ensure CLAUDE.md mentions Superflow (so future runs detect it)
2. The `docs/superpowers/` directory serves as the primary artifact marker

## Step 6: Hand Off to Phase 1

Ask the user:
> "Готово! Я познакомился с проектом. Что хочешь сделать?"

Then proceed to Phase 1 (Product Discovery) based on user's answer.

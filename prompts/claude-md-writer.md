# CLAUDE.md Writer Prompt

Best practices for generating high-quality `CLAUDE.md` files — instructions for Claude Code.

```
ultrathink. You are writing a CLAUDE.md file for a software project. This file tells Claude Code
how to work effectively in this codebase. It is NOT documentation for humans — it is
an instruction manual for an AI assistant.

## Purpose

CLAUDE.md answers: "If a new Claude session opens this project, what does it need
to know to be productive immediately?" A great CLAUDE.md saves 5-10 minutes of
context-gathering on every session. A bad one wastes context window on useless info.

## Mandatory Process — Do NOT Skip

Before writing or auditing CLAUDE.md, run these checks and include the results:

### 1. Discovery Phase (run these commands, record output)
- `find . -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.rb" -o -name "*.go" | head -5` — detect primary language
- `cat package.json 2>/dev/null | head -20` or equivalent — detect framework/dependencies
- `ls -la` — top-level structure
- `git log --oneline -10` — recent activity context
- Check for existing config: `ls Makefile justfile Dockerfile docker-compose* .github/workflows/ 2>/dev/null`

### 2. Verify Every Claim
- **Every file path** you include → verify it exists with `ls` or `test -f`
- **Every command** you include → verify it works (or note if untested)
- **Every framework name** → verify by checking actual `import`/`require` statements, NOT directory names
- **Every convention claim** → show evidence (grep for the pattern)

### 3. Quantitative Checks
- Count source files vs test files → include ratio
- List top 5 largest files by LOC → these are the ones the AI will most likely need to work on
- Check for `.env.example` or equivalent → document required env vars

## Structure Template

# {Project Name} — Claude Instructions

## Project Overview
{What this project does, in 1-2 sentences. Exact stack with versions if discoverable.
Key constraints that affect implementation decisions.}

## Key Rules
{Non-obvious rules. Each rule MUST have WHY.}
- `Convention: reason` format
- Example: "All API responses use { data, error } shape — because frontend error handling depends on this"
- Example: "Never import from adapters/ in business/ — hexagonal architecture boundary"

## Architecture
{How the system fits together. Focus on DECISION-RELEVANT info:}
- Layer structure with dependency direction (which layer imports which)
- Entry points: where requests come in
- Data flow: how a typical request moves through the system
- Key abstractions: patterns the AI must follow when adding code
- Module boundaries: what goes where when creating new files

## Key Files (verify each path exists!)
| File | LOC | Purpose |
|------|-----|---------|
| `path/to/file` | ~N | What it does and WHY it matters |
| ... | ... | ... |

Focus on files the AI is most likely to modify. Include LOC to signal complexity.

## Commands
```bash
# Development
{actual command}    # {what it does}

# Testing
{actual command}    # {what it does}

# Linting
{actual command}    # {what it does}

# Build/Deploy
{actual command}    # {what it does}
```

Each command MUST be verified to work. If a command has prerequisites, note them.

## Conventions (with evidence)
{Each convention must be backed by a grep or file reference:}
- "Files use snake_case" (evidence: `ls src/` shows all snake_case)
- "Error handling uses Result pattern" (evidence: `grep -r "Result\[" src/ | head -3`)
- "Tests are co-located with source" (evidence: `ls src/module/ shows module.py + test_module.py`)

## Known Issues & Tech Debt
{Current problems. Each must reference a specific file:line or pattern:}
- "file.py:1675 LOC — needs splitting into X and Y" (evidence: `wc -l file.py`)
- "No tests for module Z" (evidence: `find tests/ -name "*z*"` returns nothing)

## What NOT to Include
- Generic advice ("write clean code") — be project-specific
- README content (link to it: "See README.md for setup instructions")
- Every file in the project (focus on KEY files that AI will actually touch)
- Aspirational architecture (document what IS, not what should be)
- Stale information (verify every claim against current code)

## Quality Gate

Before finalizing, verify:
- [ ] Every file path in the document exists (test -f each one)
- [ ] Every command in the document works (or is marked as untested)
- [ ] Every framework/library name was verified via import statements
- [ ] No section is just a rewrite of README
- [ ] Total length is under 200 lines (concise = actually read by AI)
- [ ] Each convention has evidence (grep output, file listing)
- [ ] Known issues reference specific files, not vague areas
```

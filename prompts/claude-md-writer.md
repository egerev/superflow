# CLAUDE.md Writer Prompt

Best practices for generating high-quality `CLAUDE.md` files — instructions for Claude Code.

```
You are writing a CLAUDE.md file for a software project. This file tells Claude Code
how to work effectively in this codebase. It is NOT documentation for humans — it is
an instruction manual for an AI assistant.

## Purpose

CLAUDE.md answers: "If a new Claude session opens this project, what does it need
to know to be productive immediately?"

## Structure Template

# {Project Name} — Claude Instructions

## Project Overview
{What this project does, in 1-2 sentences. Stack. Key constraints.}

## Key Rules
{Non-obvious rules that affect how code should be written:}
- Naming conventions
- Language rules (e.g., "user-facing text in Russian, code in English")
- Import patterns
- Error handling approach
- Testing requirements

## Architecture
{Brief description of how the system fits together:}
- Entry points
- Data flow
- Key abstractions
- Module boundaries

## Key Files
| File | Purpose |
|------|---------|
| `path/to/file` | What it does |
| ... | ... |

## Commands
```bash
npm run dev        # Development server
npm run build      # Production build
npm run test       # Run tests
npm run lint       # Lint check
```

## Conventions
{Patterns the AI should follow when writing code:}
- How to name files, functions, variables
- Where to put new code
- How to handle errors
- Testing patterns

## Known Issues
{Current problems the AI should be aware of:}
- Known bugs
- Technical debt
- Things that look wrong but are intentional

## Best Practices

1. **Be actionable.** Every line should help the AI make a decision.
   Bad: "We use React" — Good: "React 19 with Server Components, no client-side state management"
2. **Be specific.** Vague rules get ignored.
   Bad: "Follow conventions" — Good: "All API routes return { data, error } shape"
3. **Include the WHY.** Rules without reasons get broken.
   Bad: "Don't use console.log" — Good: "Use logger.ts instead of console.log — structured JSON for production"
4. **Key files table is critical.** This is the #1 thing that helps AI navigate.
5. **Commands must be copy-pasteable.** Include actual commands, not descriptions.
6. **Update regularly.** Stale CLAUDE.md is worse than no CLAUDE.md.
7. **Keep it under 200 lines.** Longer = AI skims and misses things.

## Anti-Patterns

- Duplicating README content (link to README, don't copy)
- Generic advice ("write clean code") — be project-specific
- Listing every file (focus on key files, not all files)
- Outdated commands or paths (verify before writing)
- Over-engineering with complex section hierarchies
```

# llms.txt Writer Prompt

Best practices for generating high-quality `llms.txt` files following the llmstxt.org standard.

```
You are writing an llms.txt file for a software project. This file helps any LLM
(Claude, GPT, Gemini, Codex, etc.) quickly understand the project structure and
find the right documentation.

## Format Rules (llmstxt.org spec)

- Plain Markdown, UTF-8
- Max ~10KB (fit in a single LLM context load)
- H1: Project name (required, exactly one)
- Blockquote after H1: One-line project summary
- H2 sections: Categorize resources
- List items: `- [Name](path): Description`
- "Optional" H2 section: lower-priority resources that can be skipped

## Structure Template

# {Project Name}

> {One-line description: what it does, who it's for}

## Overview
- [README](./README.md): Project setup and overview
- [Architecture](./docs/architecture.md): System design and data flow
- [CHANGELOG](./CHANGELOG.md): Version history

## Core Source
- [Entry Point](./src/index.ts): Application bootstrap
- [Data Model](./prisma/schema.prisma): Database schema
- [API Routes](./src/app/api/): REST/GraphQL endpoints
- [Business Logic](./src/lib/): Core modules

## Configuration
- [Package](./package.json): Dependencies and scripts
- [TypeScript](./tsconfig.json): TS configuration
- [Environment](./.env.example): Required env vars

## Testing
- [Test Setup](./vitest.config.ts): Test configuration
- [Tests](./src/__tests__/): Test suites

## Optional
- [CI/CD](./.github/workflows/): GitHub Actions
- [Docker](./Dockerfile): Container setup
- [Docs](./docs/): Extended documentation

## Best Practices

1. **Link only what exists.** Verify every path before including it.
2. **Descriptions matter.** Don't just list files — explain what an LLM would
   need to know to work with them effectively.
3. **Prioritize.** Core source and data model first. CI/CD and Docker last.
4. **Be specific.** Instead of "src/" → link the actual key modules with purpose.
5. **Keep it fresh.** Update llms.txt when adding major new modules or changing architecture.
6. **Think like an LLM.** What would you need to read first to implement a feature?
   That's the order.
7. **Avoid noise.** Don't list every file. Focus on entry points, interfaces, and
   high-value documentation.

## Anti-Patterns

- Listing 50+ files (defeats the purpose — be selective)
- Missing descriptions (just links are useless without context)
- Stale paths (broken links waste LLM context)
- Duplicating README content (link to it, don't copy it)
```

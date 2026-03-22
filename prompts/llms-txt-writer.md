# llms.txt Writer Prompt

Best practices for generating high-quality `llms.txt` files following the llmstxt.org standard.

```
ultrathink. You are writing an llms.txt file for a software project. This file helps any LLM
(Claude, GPT, Gemini, Codex, etc.) quickly understand the project structure and
find the right documentation. A great llms.txt is a map — it tells the LLM exactly
where to look for what. A bad one is noise that wastes context.

## Format Rules (llmstxt.org spec)

- Plain Markdown, UTF-8
- Max ~10KB (fit in a single LLM context load)
- H1: Project name (required, exactly one)
- Blockquote after H1: One-line project summary
- H2 sections: Categorize resources
- List items: `- [Name](path): Description`
- "Optional" H2 section: lower-priority resources that can be skipped

## Mandatory Process — Do NOT Skip

### 1. Inventory Phase
Before writing, build a complete inventory:
```bash
# Count source directories
find . -type d -not -path './.git/*' -not -path './node_modules/*' -not -path './.venv/*' -maxdepth 3 | sort

# Count source files by type
find . -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.rb" -o -name "*.go" | wc -l

# List all documentation files
find . -name "*.md" -not -path './node_modules/*' | sort

# Check for key config files
ls -la Makefile justfile Dockerfile docker-compose* .env.example pyproject.toml package.json Cargo.toml go.mod 2>/dev/null
```

### 2. Coverage Check
After writing, verify coverage:
- Count source directories → count llms.txt entries → calculate %
- Target: >80% of key source directories should be referenced
- Every path in llms.txt MUST exist (verify with `test -f` or `test -d`)

### 3. Framework Verification
- Every framework/library name → verify via actual `import`/`require` statements
- NEVER guess from directory names (e.g., `graph/` could be pydantic_graph, not LangGraph)

## Structure Template

# {Project Name}

> {One-line: what it does, primary language/framework (verified via imports), who it's for}

## Overview
- [README](./README.md): Project setup and overview
- [Architecture](./docs/architecture.md): System design and data flow
- [CLAUDE.md](./CLAUDE.md): AI assistant instructions
- [CHANGELOG](./CHANGELOG.md): Version history

## Core Source
{Group by logical domain, not by directory. Each entry must:
 1. Link to actual file/dir (verified to exist)
 2. Include LOC or file count for context
 3. Describe WHAT and WHY — not just the name}

- [Entry Point](./src/main.py): Application bootstrap, dependency injection (~200 LOC)
- [Data Model](./src/models/): Database models and schemas (15 files, ~3,000 LOC)
- [API Layer](./src/api/): REST endpoints, request validation (8 files)
- [Business Logic](./src/services/): Core domain logic, orchestration (12 files, ~5,000 LOC)
- [Agent Pipeline](./src/agents/graph/): Pydantic-graph agent orchestration — NOT LangGraph (5 files, ~2,500 LOC)

## Key Modules (most-modified, highest-impact)
{These are the files an LLM is most likely to need to read or modify.
 Prioritize by: frequency of changes (git log), size, and criticality.}

- [User Service](./src/services/user_service.py): User CRUD, auth logic (~800 LOC)
- [Chat Node](./src/agents/graph/chat_node.py): Main agent loop, tool dispatch (~1,400 LOC — refactoring candidate)

## Configuration
- [Package](./package.json): Dependencies and scripts
- [Environment](./.env.example): Required env vars (DB, API keys, feature flags)
- [Docker](./docker-compose.yml): Local development stack ({N} services)

## Testing
- [Test Config](./pytest.ini): Test configuration
- [Tests](./tests/): {N} test files, {M} test functions, ~{X}% source coverage

## Infrastructure
- [CI/CD](./.github/workflows/): {list actual workflow names}
- [Deploy](./deploy.sh): Deployment script
- [Monitoring](./docker-compose.yml): Observability stack (if present)

## Optional
- [Docs](./docs/): Extended documentation ({N} files)
- [Scripts](./scripts/): Utility scripts
- [Migrations](./alembic/): Database migrations ({N} revisions)

## Quality Gate

Before finalizing, verify:
- [ ] Every path exists (test -f / test -d for each entry)
- [ ] Coverage: llms.txt covers N of M source directories (>80%)
- [ ] Every framework name verified via import statements (not directory names)
- [ ] Descriptions are specific (not just repeating the file name)
- [ ] LOC/file counts are accurate (verified with wc -l or find | wc -l)
- [ ] Recent modules included (check git log for files added in last 30 days)
- [ ] No stale entries (paths that were renamed or deleted)
- [ ] Total size under 10KB

## Anti-Patterns

- Listing 50+ files (defeats the purpose — be selective, focus on high-impact)
- Missing descriptions (just links are useless without context)
- Stale paths (broken links waste LLM context)
- Guessing framework names from directories (ALWAYS check imports)
- Duplicating README content (link to it, don't copy it)
- Round numbers for counts (say "248 test files" not "~250 test files" — precision builds trust)
- Describing what SHOULD be there instead of what IS there
```

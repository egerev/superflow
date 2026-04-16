# Phase 0 Stage 2: Analysis — Codex Dispatch Overlay

> This file contains Codex-specific dispatch patterns for Phase 0 Stage 2.
> For workflow logic (state management, cross-check synthesis, evidence bundle), read the main file: `references/phase0/stage2-analysis.md`.

## Agent Dispatch (5 parallel agents)

All 5 agents launch via spawn_agent. Codex parallelizes up to max_threads=6.

### Agent 1 — Architecture

Use the spawn_agent tool to dispatch agent "deep-analyst" with task:
```
You are auditing the architecture of this project.
Context from preflight: $PREFLIGHT

Mandatory checks — show evidence for every finding:
1. List all top-level directories with file counts and total LOC per directory.
2. Identify frameworks/libraries by reading actual import/require statements.
3. Map the data model: list all DB models/schemas with field counts.
4. Find architecture violations: business logic importing from adapters/infrastructure.
5. Identify top 10 largest files by LOC.
6. Map key entry points (API routes, CLI commands, event handlers).

Return structured JSON evidence bundle.
```

### Agent 2 — Code Quality

Use spawn_agent to dispatch "deep-analyst" with task: code quality analysis (same prompt as main doc, section Agent 2).

### Agent 3 — Security

**Primary (Codex-native):** Use spawn_agent to dispatch "deep-analyst" with the security audit prompt from `prompts/security-audit.md`.

**Claude as secondary (optional, for cross-validation):**
```bash
$TIMEOUT_CMD 600 claude -p "$(cat prompts/claude/audit.md)" 2>&1
```

### Agent 4 — DevOps

Use spawn_agent to dispatch "fast-implementer" with task: DevOps analysis (same prompt as main doc, section Agent 4).

### Agent 5 — Documentation

Use spawn_agent to dispatch "deep-analyst" with task: documentation analysis (same prompt as main doc, section Agent 5).

## Wait & Proceed

Wait for all 5 agents to complete. Then follow the main doc's Steps 4-6 (cross-check synthesis, save evidence bundle).

## TaskCreate Replacement

Codex does not have TaskCreate/TaskUpdate. Use printf for progress:
```bash
printf "Phase 0 Stage 2: dispatching 5 analysis agents...\n"
printf "Phase 0 Stage 2: all agents complete, synthesizing...\n"
```

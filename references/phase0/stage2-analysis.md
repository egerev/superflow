# Phase 0 — Stage 2: Analysis
<!-- Stage 2, Todos: dispatch 5 agents, wait, cross-check synthesis -->

Runs after Stage 1 confirms `$PREFLIGHT`. Dispatches 5 parallel specialized agents to audit the codebase, then cross-checks findings for consistency. Output is an internal evidence bundle saved to state for Stage 3.

**All documentation output in English.** Communicate with the user in their language.

---

## Stage Structure

```
Stage 2: "Analysis"
  Todos:
  - "Read $PREFLIGHT from state file"
  - "Dispatch architecture agent"
  - "Dispatch code quality agent"
  - "Dispatch security agent (Codex or Claude)"
  - "Dispatch DevOps agent"
  - "Dispatch documentation agent"
  - "Wait for all agents"
  - "Cross-check synthesis"
  - "Save evidence bundle to state"
```

If Telegram MCP available (`mcp__plugin_telegram_telegram__reply` tool is present), send at stage start:
```
mcp__plugin_telegram_telegram__reply(chat_id: <chat_id from context>, text: "Analyzing your project...")
```

TaskCreate at stage start:
```
TaskCreate(
  title: "Phase 0 — Stage 2: Analysis",
  todos: [
    "Read $PREFLIGHT from state file",
    "Dispatch architecture agent",
    "Dispatch code quality agent",
    "Dispatch security agent (Codex or Claude)",
    "Dispatch DevOps agent",
    "Dispatch documentation agent",
    "Wait for all agents",
    "Cross-check synthesis",
    "Save evidence bundle to state"
  ]
)
```

---

## Step 1: Read $PREFLIGHT from State File

Context compaction may have erased earlier variables. Always reload from disk:

```bash
python3 -c "import json; s=json.load(open('.superflow-state.json')); print(json.dumps(s.get('context',{}).get('preflight',{}), indent=2))"
```

This gives `$PREFLIGHT` with: stack, framework, team_size, ci, experience, formatters, etc.

---

## Step 2: Update Stage in State

```bash
python3 -c "
import json, datetime
s = json.load(open('.superflow-state.json'))
s['stage'] = 'analysis'
s['stage_index'] = 1
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s, open('.superflow-state.json', 'w'), indent=2)
"
```

---

## Step 3: Dispatch 5 Parallel Agents

All five agents launch simultaneously with `run_in_background: true`. Include `$PREFLIGHT` in every prompt so agents adjust depth to the project's stack and team context.

### Agent 1 — Architecture (deep-analyst)

```
Agent(
  subagent_type: "deep-analyst",
  run_in_background: true,
  description: "Architecture analysis",
  prompt: """
ultrathink. You are auditing the architecture of this project.
Context from preflight: $PREFLIGHT

Mandatory checks — show evidence (file path, line count, code snippet) for every finding:
1. List all top-level directories with file counts and total LOC per directory.
2. Identify frameworks/libraries by reading actual `import`/`require` statements.
   NEVER guess from directory names — grep for imports explicitly.
3. Map the data model: list all DB models/schemas with field counts.
4. Find architecture violations: does business logic import from adapters/infrastructure?
   List every violation as file:line with the offending import.
5. Identify the top 10 largest files by LOC — these are refactoring candidates.
6. Map key entry points (API routes, CLI commands, event handlers).

Return a structured evidence bundle in JSON:
{"stack":"...","framework":"...","top_dirs":[...],"violations":[...],"largest_files":[...],"entry_points":[...]}
"""
)
```

### Agent 2 — Code Quality (deep-analyst)

```
Agent(
  subagent_type: "deep-analyst",
  run_in_background: true,
  description: "Code quality analysis",
  prompt: """
ultrathink. You are auditing code quality.
Context from preflight: $PREFLIGHT

Mandatory checks — show evidence for every finding:
1. List ALL files >500 LOC with exact line counts.
2. Find all TODO/FIXME/HACK/XXX comments — total count and top 10 locations.
3. Count test files vs source files — calculate the ratio.
4. Find source files with NO corresponding test file.
5. Check for code duplication: similar function signatures across modules.
6. Check linter config exists and is enforced (pre-commit hooks, CI checks).
7. Find dead code: unused imports, unreachable functions (use available tooling).

Adjust depth for team context: if solo+beginner flag basics (missing linter, zero tests);
if team, flag shared conventions and coverage gaps.

Return structured JSON evidence bundle.
"""
)
```

### Agent 3 — Security (Codex preferred, Claude fallback)

**If Codex is available** (check by running `which codex 2>/dev/null`):

```bash
$TIMEOUT_CMD 600 codex exec --full-auto -c model_reasoning_effort=high "$(cat prompts/codex/audit.md)" 2>&1
```

Run in background (shell background: append `&`, capture PID). Codex focus: hardcoded secrets, injection vectors, dependency CVEs, CI/CD security gaps.

**If Codex is NOT available**, dispatch Claude instead:

```
Agent(
  subagent_type: "deep-analyst",
  run_in_background: true,
  description: "Security audit",
  prompt: """
ultrathink. [Read and follow prompts/security-audit.md]
Context from preflight: $PREFLIGHT
Perform a full security audit. Focus: hardcoded secrets, injection risks,
dependency vulnerabilities, .env exposure, insecure defaults.
Show evidence (file:line) for every finding. Severity: CRITICAL/HIGH/MEDIUM/LOW.
Return structured JSON evidence bundle.
"""
)
```

### Agent 4 — DevOps (fast-implementer)

DevOps checks are mechanical — file existence, config patterns. Sonnet is sufficient.

```
Agent(
  subagent_type: "fast-implementer",
  run_in_background: true,
  description: "DevOps analysis",
  prompt: """
You are auditing DevOps and infrastructure configuration.
Context from preflight: $PREFLIGHT

Mandatory checks — show evidence for every finding:
1. Docker Compose: count services, flag `latest` image tags, check volume mounts.
2. CI/CD: list all .github/workflows/*.yml files and what each tests/deploys.
3. Deploy script: does it run migrations? Rollback steps? Health checks?
4. Security scanning: is dependabot/renovate/CodeQL configured?
5. Backup strategy: any evidence of DB backup procedures?
6. Environment management: .env.example exists? Secrets in .env committed?
7. .gitignore completeness: check for common misses (.env, __pycache__,
   node_modules, .worktrees/, *.log, dist/, build/).

Return structured JSON evidence bundle.
"""
)
```

### Agent 5 — Documentation (deep-analyst)

```
Agent(
  subagent_type: "deep-analyst",
  run_in_background: true,
  description: "Documentation analysis",
  prompt: """
ultrathink. You are auditing documentation quality and freshness.
Context from preflight: $PREFLIGHT

Mandatory checks — show evidence for every finding:
1. List all documentation files with last-modified dates (use git log).
2. Compare README claims against actual project state (verify commands, setup steps).
3. If llms.txt exists: count entries vs actual source directories — coverage %.
4. If CLAUDE.md exists: verify every documented path exists; test commands are runnable.
5. Check for stale references: grep for file paths in docs, verify each exists on disk.
6. API documentation: auto-generated or manual? Is it current?

IMPORTANT: Verify framework names match what you see in actual import statements —
never accept a name that is only in a directory name or comment.

Return structured JSON evidence bundle.
"""
)
```

---

## Step 4: Wait for All Agents

Do not proceed until all 5 agents complete. If a Codex background process was launched, wait for its PID with `wait $CODEX_PID`.

---

## Step 5: Cross-Check Synthesis

After all agents complete:

1. **Framework name consistency** — do Architecture, Documentation, and Code Quality agents agree on the stack/framework? If any agent named the framework differently, re-read the relevant source file imports to resolve.
2. **File count consistency** — do LOC counts and file lists align across agents? Note discrepancies.
3. **Security deduplication** — if both Codex and a Claude security agent ran, merge findings (keep highest severity per finding, deduplicate).
4. **Compose evidence bundle** — a single dict with keys: `architecture`, `code_quality`, `security`, `devops`, `documentation`, plus a `discrepancies` list (empty if none).

---

## Step 6: Save Evidence Bundle to State

```bash
python3 -c "
import json, datetime
s = json.load(open('.superflow-state.json'))
s['context']['analysis'] = $EVIDENCE_BUNDLE_JSON
s['last_updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(s, open('.superflow-state.json', 'w'), indent=2)
"
```

The bundle is **not shown to the user yet** — Stage 3 (Proposal) reads it and composes the health report.

---

## Completion

```
TaskUpdate(id: <task_id>, status: "completed")
```

Proceed to Stage 3: re-read `references/phase0/stage3-report.md`.

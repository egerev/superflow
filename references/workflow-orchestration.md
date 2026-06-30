# Workflow Orchestration

Single authority for using Claude Code dynamic workflows inside Superflow. Step files
(`references/phase2/steps/review-unified.md`, `references/phase2/steps/impl-dispatch.md`)
point here instead of re-explaining. Workflows are an OPT-IN acceleration for exactly two
Phase 2 spots — unified review fan-out and parallel implementation waves. The markdown DAG
and Agent-based dispatch remain the default path, and the only path on Codex runtime.

Official docs: <https://code.claude.com/docs/en/workflows>,
<https://code.claude.com/docs/en/goal>, <https://code.claude.com/docs/en/sub-agents>.

## What the Workflow Tool Is

Documented facts only (per the workflows doc):

- A dynamic workflow is a JavaScript script that orchestrates subagents at scale. A runtime
  executes it in the background, in an isolated environment, while the session stays responsive.
- Requires Claude Code v2.1.154 or later (paid plans; Anthropic API, Bedrock, Vertex, Foundry).
- Intermediate results live in script variables, NOT in the orchestrator's context — only the
  script's final result lands in the session. This is the context win: N reviewer/implementer
  transcripts never enter the orchestrator's window.
- Script API (signatures verified by smoke run 2026-06-11; the official docs do not publish
  the script API — re-verify after CLI upgrades):
  - Script body runs **top-level** in an async context — no `export default async function run()`
    wrapper; `await` and `return <value>` happen at the top level of the script.
  - `export const meta = { name, description, phases }` where `phases` is an array of objects:
    `[{ title: "..." }]` — not bare strings. `meta` must be a pure literal — no
    concatenation/template literals/computed values (runtime rejects the script otherwise).
  - `phase("Title")` is a **statement** that opens a phase group. It does NOT take a callback
    and returns nothing.
  - `parallel(thunks)` takes an array of **thunks**: `parallel(items.map((s) => () => agent(...)))`.
    Passing bare promises is wrong. A thunk that fails resolves to null (never rejects) — keep
    null handling.
  - `agent(prompt)` returns the agent's final response text (string) or null.
  - `args`, `log(message)` as documented. `args` may be delivered as a JSON string depending
    on the invocation path — scripts must normalize with
    `typeof args === "string" ? JSON.parse(args) : args` (fail closed on parse errors).
- Runs are resumable within the same session; exiting Claude Code starts the workflow fresh.

## Opt-In Policy

A workflow run requires user opt-in. Documented opt-in mechanisms:

| Mechanism | Effect |
|-----------|--------|
| `ultracode` keyword in the prompt | That one task runs as a workflow |
| Own-words request ("use a workflow", "run a workflow") | Same as the keyword |
| `/effort ultracode` | Claude plans a workflow for every substantive task in the session |
| Invoking a saved workflow (`/<name>`) | Runs that saved script |

**Superflow records the opt-in at Phase 1 Step 12 (plan approval).** The plan-approval
summary states:

> Autonomous execution will use saved multi-agent workflows for review fan-out and parallel
> waves (recommended). Heads-up: depending on permission mode, the FIRST workflow launch may
> show one approval prompt (Auto mode: first launch only; default mode: every launch —
> consider switching to Auto for Phase 2). Say no-workflows to use plain subagent dispatch.

User objection → `context.use_workflows = false`. The decision is stored in
`.superflow-state.json` (`context.use_workflows`) and in the
Autonomy Charter. Workflow invocation by the orchestrator during Phase 2 is justified by this
recorded user opt-in — per docs, a direct user request is the opt-in mechanism, and plan
approval captures it.

## Permission Gates by Mode

Whether a launch prompt appears depends on permission mode (documented behavior):

| Permission mode | Launch prompt |
|-----------------|---------------|
| Default, accept edits | Every run, unless "don't ask again for `<name>` in this project" was selected |
| Auto | First launch only — any Yes records consent in user settings; skipped entirely when ultracode is on |
| Bypass permissions, `claude -p`, Agent SDK | Never — the run starts immediately |

Practical recommendation for Phase 2: have the user switch to Auto mode before launch so the
entire autonomous run pays at most one approval prompt. The permission mode controls only the
launch prompt — subagents spawned by a workflow always run in `acceptEdits` mode and inherit
the session tool allowlist regardless of session mode. Shell commands, web fetches, and MCP
tools outside the allowlist can still prompt mid-run; add the commands agents need (git, test
runners, `codex`) to the allowlist before a long run.

## Limits

| Constraint | Consequence for Superflow |
|------------|---------------------------|
| Up to 16 concurrent agents (fewer on machines with limited CPU cores) | Cap wave width at 16; Superflow waves stay far below this |
| 1,000 agents total per run | Not a practical limit for the review/wave scripts |
| No mid-run user input | Workflows fit Phase 2 only (autonomous); never use them for Phase 1 gates |
| No direct filesystem or shell access from the script | Agents do ALL I/O; the script only coordinates and parses response text |

## Saved Workflows

- `.claude/workflows/` in a project — shared with everyone who clones the repo.
- `~/.claude/workflows/` — personal, available in every project. Superflow's deploy-sync
  (SKILL.md startup step 4, Claude runtime only) checksums `workflows/*.js` from the skill
  root into `~/.claude/workflows/`, so `/superflow-review` and `/superflow-wave` are
  invocable in any project.
- A saved workflow runs as `/<name>`. On a name collision, the project copy wins.
- Input arrives through `args`: the script reads it as a global, already structured
  (arrays/objects usable directly, no parsing). If omitted, `args` is `undefined`.

## The Two Superflow Saved Workflows

Both scripts use ONLY the documented API surface and stay deterministic — no clock or
randomness calls (the runtime forbids them); the orchestrator stamps timestamps when it
assembles `.par-evidence.json`. Structured data returns via the v5.4.0 fenced-JSON contract:
each script extracts the LAST fenced `json` block from the agent's response with a regex and
`JSON.parse` in try/catch. On any parse failure it FAILS CLOSED — a review verdict degrades
to `REQUEST_CHANGES`, an implementation result to `status: "failed"`. A malformed agent
reply can never pass a gate.

### /superflow-review — unified review fan-out

`workflows/superflow-review.js`. Accelerates the review-unified step
(`references/phase2/steps/review-unified.md`).

- **args:** `{sprint, branch, base, charter_path, workdir, spec_path, plan_path, brief_path, product, diff_hint}`
  - `workdir` (required): absolute path to the sprint worktree (or repo root for
    `solo_single_pr`). The technical reviewer cds into workdir before running `codex exec
    review`; the product reviewer uses `git -C workdir diff` — without this, both would diff
    the wrong checkout.
  - `spec_path`, `plan_path`, `brief_path` (optional, strongly recommended): file paths the
    reviewers Read for context. `spec_path`/`plan_path` feed the spec-fit and plan-completeness
    checks for BOTH lenses (a diff alone cannot reveal a stub); `brief_path` feeds the product
    lens. When absent, the prompts instruct the reviewer to flag the check as unverifiable
    rather than pass silently.
  - `product` (boolean, default `true`): pass `false` for light-governance sprints (single
    technical reviewer only). Returns `{product: null, technical, pass}` when false.
  - Returns `{product: null, technical: null, pass: false, error: "missing required args: ..."}` if
    `sprint`, `branch`, `charter_path`, or `workdir` is missing — fails closed instead of
    interpolating "undefined" into prompts.
- Runs in parallel: a product reviewer (follows `~/.claude/agents/standard-product-reviewer.md`,
  reads the charter at `charter_path`, reviews `branch` vs `base` via `git -C workdir diff`)
  and a technical reviewer (cds into `workdir`, applies the fallback chain itself via Bash: if
  the Codex CLI exists, `$TIMEOUT_CMD 600 codex exec review --base <base> -m gpt-5.5 -c model_reasoning_effort=high --ephemeral`;
  else it acts as the Claude technical reviewer per `~/.claude/agents/standard-code-reviewer.md`).
  When `product:false`, only the technical thunk runs.
- **returns:** `{product, technical, pass}` — `pass` is true only when passing verdicts hold for
  all active reviewers (APPROVE/ACCEPTED/PASS); REQUEST_CHANGES/NEEDS_FIXES/FAIL and anything
  unparseable fail. `product` is `null` when `product:false`.
- The orchestrator assembles `.par-evidence.json` from the returned verdicts with
  `"provider": "workflow-review"`, then runs the docs gate and the fix/re-review loop per
  the step file. Fixes are orchestrator work — re-run the workflow only if both reviewers
  must look again; otherwise re-engage the single flagging lens via plain Agent dispatch.

### /superflow-wave — implementation-only wave

`workflows/superflow-wave.js`. Accelerates the v5.4.0 parallel-wave dispatch rule:
implementation-only fan-out; orchestrator runs review/docs/PAR/ship per sprint.
REVIEW IS NOT IN THIS SCRIPT.

- **args:** `{sprints: [{id, branch, worktree, task}], charter_path}`
- `parallel()` dispatches one implementer agent per sprint. Each prompt: follow
  `~/.claude/agents/standard-implementer.md`, read the charter, work ONLY inside the given
  worktree on the given branch, implement the task, run tests, commit — no reviews, no docs,
  no PAR evidence, no PRs.
- **returns:** array of `{sprint, status: "done"|"failed", summary, test_evidence}` — one
  entry per input sprint, position-bound (null agent results fail closed to `"failed"`).
- Afterwards the ORCHESTRATOR runs review → docs → PAR → ship per sprint, exactly as in
  `references/phase2/steps/impl-dispatch.md`. The sequencing (review/docs/PAR/ship per sprint)
  is unchanged; only the implementation fan-out is accelerated.

## UNDOCUMENTED-API Warning

> **⚠️ Do not use undocumented script fields.** Fields like `schema`, `agentType`,
> `isolation`, and `resume-run-id` have been observed in some builds but appear nowhere in
> the official workflows doc. Shipped Superflow scripts MUST NOT rely on them — they can
> change or vanish in any release. The guaranteed surface is `agent(prompt)` → final
> response text, `parallel()`, `phase()`, `log()`, `args`. Structured data comes back ONLY
> through the fenced-JSON contract with fail-closed parsing.

## /goal Watchdog

`/goal` sets a session-level objective watchdog (see the goal doc). **It is a USER-ONLY
command — the model CANNOT set it.** Superflow never claims to have set a goal; it only
suggests one. At Phase 2 launch (right after plan approval, before the first sprint), the
orchestrator PRINTS a ready-to-paste suggestion:

```text
/goal Superflow Phase 2 complete: all <N> sprints implemented, unified-reviewed, PRs created and CI-green, Completion Report delivered.
```

Mechanics worth knowing:

- The evaluator is Haiku, running as a prompt-based Stop hook: it judges ONLY what is
  visible in the transcript. The orchestrator must keep narrating sprint completions (it
  already does) so the evaluator can see progress.
- One goal per session; survives `--resume`; the user clears it with `/goal clear`.
- Subagents do NOT inherit goals. Per-sprint goal-direction remains the Autonomy Charter
  injection into every implementer and reviewer prompt (already shipped) — the charter, not
  `/goal`, is what keeps subagents aligned.

## Codex Runtime and Fallbacks

Codex runtime has NO Workflow tool and NO `/goal`. On `RUNTIME:codex` the markdown DAG with
`spawn_agent` dispatch is the only path — skip everything in this doc except the
charter-injection note above.

The Agent-based v5.4.0 path is also the fallback on Claude runtime whenever ANY of:

- `context.use_workflows = false` (user said no-workflows at plan approval)
- workflows disabled: `"disableWorkflows": true` in settings, or `CLAUDE_CODE_DISABLE_WORKFLOWS=1`
- Claude Code version < 2.1.154

Fallback means NO behavior change: `review-unified.md` and `impl-dispatch.md` describe the
Workflow path as PREFERRED-WHEN-AVAILABLE and keep the full Agent dispatch procedure. When
in doubt, fall back — the workflow path is an acceleration, never a requirement.

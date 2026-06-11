// /superflow-wave — Superflow parallel implementation wave (Phase 2, step impl-dispatch).
//
// OPT-IN acceleration of the v5.4.0 parallel-wave dispatch rule:
// implementation-only fan-out; orchestrator runs review/docs/PAR/ship per sprint.
// Authority: references/workflow-orchestration.md
//
// Documented API surface ONLY: agent(prompt) -> final response text, parallel(),
// phase(), log(), args. Structured data comes back via the fenced-JSON contract;
// any parse failure FAILS CLOSED as status "failed". Deterministic by design: no
// clock or randomness calls — the orchestrator stamps timestamps.
//
// args:    { sprints: [{ id, branch, worktree, task }], charter_path }
// returns: [{ sprint, status: "done"|"failed", summary, test_evidence }] —
//          one entry per input sprint, position-bound.

export const meta = {
  name: "superflow-wave",
  description: "Superflow Phase 2 implementation wave: one implementer agent per sprint in its own worktree; returns fenced-JSON results, fail-closed. Review/docs/PAR/ship stay with the orchestrator.",
  phases: [{ title: "Implementation" }],
};

// Fenced-JSON extraction: take the LAST fenced json block, JSON.parse in try/catch.
// Null agent results, missing fences, bad JSON, or an invalid status FAIL CLOSED.
// (Helper duplicated in superflow-review.js — workflow scripts cannot import.)
function parseResult(text, sprintId) {
  const failClosed = {
    sprint: sprintId,
    status: "failed",
    summary: "implementer returned no parseable fenced-JSON result (fail closed)",
    test_evidence: "",
  };
  if (typeof text !== "string") return failClosed;
  const fences = [...text.matchAll(/```json\s*([\s\S]*?)```/g)];
  if (fences.length === 0) return failClosed;
  try {
    const parsed = JSON.parse(fences[fences.length - 1][1]);
    if (!parsed || (parsed.status !== "done" && parsed.status !== "failed")) return failClosed;
    // Bind to the wave's sprint id — the orchestrator keys results positionally.
    return {
      sprint: sprintId,
      status: parsed.status,
      summary: typeof parsed.summary === "string" ? parsed.summary : "",
      test_evidence: typeof parsed.test_evidence === "string" ? parsed.test_evidence : "",
    };
  } catch {
    return failClosed;
  }
}

function implementerPrompt(s, charterPath) {
  return (
    "You are the implementer for Superflow sprint " + s.id + ".\n" +
    "1. Read ~/.claude/agents/standard-implementer.md and FOLLOW it (TDD discipline, verification).\n" +
    "2. Read the Autonomy Charter at " + charterPath + " — goal, non-negotiables, and success criteria bind you.\n" +
    "3. Work ONLY inside the worktree at " + s.worktree + " on branch " + s.branch + ". Never touch files outside it.\n" +
    "4. Implement this task:\n" + s.task + "\n" +
    "5. Run the test suite (wrap with a 120s timeout), then commit your work on " + s.branch + " with a descriptive message.\n" +
    "Do NOT review, update docs, write PAR evidence, or create PRs — the orchestrator does that per sprint afterwards.\n" +
    "End your final message with a fenced json block and NOTHING after it:\n" +
    "```json\n" +
    '{"sprint": ' + JSON.stringify(s.id) + ', "status": "done|failed", "summary": "", "test_evidence": ""}\n' +
    "```\n" +
    'Use status "done" only if tests pass and the commit exists; otherwise "failed" with the reason in summary.'
  );
}

// Normalize args: depending on the invocation path, args may arrive as a JSON
// string instead of a parsed object. Parse errors leave an empty object, which
// fails closed via the "no sprints" early return below.
let a = {};
try { a = typeof args === "string" ? JSON.parse(args) : (args || {}); } catch { a = {}; }

const sprints = Array.isArray(a.sprints) ? a.sprints : [];
const charterPath = a.charter_path || "";
if (sprints.length === 0) {
  log("superflow-wave: no sprints in args — nothing to dispatch");
  return [];
}
log(
  "superflow-wave: dispatching " + sprints.length + " implementer(s): " +
  sprints.map((s) => s.id).join(", ")
);

phase("Implementation");
const texts = await parallel(sprints.map((s) => () => agent(implementerPrompt(s, charterPath))));

// Position-bound parsing; null/missing results fail closed inside parseResult.
const results = sprints.map((s, i) =>
  parseResult(texts && texts[i] != null ? texts[i] : null, s.id)
);
const done = results.filter((r) => r.status === "done").length;
log(
  "superflow-wave: " + done + "/" + results.length + " sprint(s) done — " +
  "orchestrator now runs review/docs/PAR/ship per sprint"
);
return results;

// /superflow-review — Superflow unified review fan-out (Phase 2, step review-unified).
//
// OPT-IN acceleration of the two-reviewer protocol. The Agent-based dispatch in
// references/phase2/steps/review-unified.md remains the default and the fallback.
// Authority: references/workflow-orchestration.md
//
// Documented API surface ONLY: agent(prompt) -> final response text, parallel(),
// phase(), log(), args. Structured data comes back via the v5.4.0 fenced-JSON
// verdict contract; any parse failure FAILS CLOSED as REQUEST_CHANGES.
// Deterministic by design: no clock or randomness calls — the orchestrator stamps
// timestamps when it assembles .par-evidence.json (provider: "workflow-review").
//
// args:    { sprint: N, branch: "feat/x-sprint-N", base: "main",
//            charter_path: "docs/superflow/specs/...-charter.md",
//            workdir: "/abs/path/to/sprint-worktree",
//            product: true,            (default true; pass false for light-governance)
//            diff_hint: "..." }
// returns: { product: <verdict>|null, technical: <verdict>, pass: <bool> }
//          on missing required args: { product: null, technical: null, pass: false, error: "..." }

export const meta = {
  name: "superflow-review",
  description: "Superflow Phase 2 unified review: product + technical reviewers in parallel over a sprint branch diff; returns fenced-JSON verdicts, fail-closed.",
  phases: [{ title: "Review" }],
};

const PASS_VERDICTS = ["APPROVE", "ACCEPTED", "PASS"];

// v5.4.0 verdict contract: extract the LAST fenced json block, JSON.parse in
// try/catch. Null agent results, missing fences, bad JSON, or a missing verdict
// field all FAIL CLOSED — a malformed reviewer reply can never pass the gate.
// (Helper duplicated in superflow-wave.js — workflow scripts cannot import.)
function parseVerdict(text, lens) {
  const failClosed = {
    verdict: "REQUEST_CHANGES",
    findings: [],
    summary: lens + " reviewer returned no parseable fenced-JSON verdict (fail closed)",
  };
  if (typeof text !== "string") return failClosed;
  const fences = [...text.matchAll(/```json\s*([\s\S]*?)```/g)];
  if (fences.length === 0) return failClosed;
  try {
    const parsed = JSON.parse(fences[fences.length - 1][1]);
    if (!parsed || typeof parsed.verdict !== "string") return failClosed;
    return parsed;
  } catch {
    return failClosed;
  }
}

function isPass(verdict) {
  return PASS_VERDICTS.includes(String(verdict).trim().toUpperCase());
}

const VERDICT_BLOCK =
  "End your final message with a fenced json block and NOTHING after it:\n" +
  "```json\n" +
  '{"verdict": "...", "findings": [{"severity": "critical|high|medium|low", ' +
  '"file": "", "line": 0, "scenario": "", "description": ""}], "summary": ""}\n' +
  "```";

function productPrompt(a) {
  return (
    "You are the PRODUCT reviewer for Superflow sprint " + a.sprint + ".\n" +
    "1. Read ~/.claude/agents/standard-product-reviewer.md and FOLLOW it (role, checks, output format).\n" +
    "2. Read the Autonomy Charter at " + a.charter_path + " — source of truth for goal, non-negotiables, success criteria.\n" +
    "3. Review the diff of " + a.branch + " against " + a.base + " (git -C " + a.workdir + " diff " + a.base + "..." + a.branch + ") " +
    "through the product lens ONLY: spec fit, user scenarios, data integrity. " +
    "Every finding needs a realistic breakage scenario.\n" +
    (a.diff_hint ? "Diff hint from the orchestrator: " + a.diff_hint + "\n" : "") +
    "Allowed verdicts: ACCEPTED or NEEDS_FIXES.\n" +
    VERDICT_BLOCK
  );
}

function technicalPrompt(a) {
  return (
    "You are the TECHNICAL reviewer for Superflow sprint " + a.sprint + ". Apply the fallback chain YOURSELF via Bash:\n" +
    "1. Run: command -v codex. If the Codex CLI exists, resolve TIMEOUT_CMD (gtimeout, else timeout).\n" +
    "   cd into " + a.workdir + " (the sprint worktree) so the sprint branch checkout is visible, then run:\n" +
    "   $TIMEOUT_CMD 600 codex exec review --base " + a.base + " -m gpt-5.5 -c model_reasoning_effort=high --ephemeral 2>&1\n" +
    "   Wrap its findings honestly into the verdict block below (verdict APPROVE or REQUEST_CHANGES).\n" +
    "2. If codex is absent: act as the Claude technical reviewer — Read ~/.claude/agents/standard-code-reviewer.md and FOLLOW it " +
    "over the diff of " + a.branch + " vs " + a.base + " (git -C " + a.workdir + " diff " + a.base + "..." + a.branch + "; correctness, security, architecture, performance).\n" +
    "Also read the Autonomy Charter at " + a.charter_path + " for non-negotiables.\n" +
    (a.diff_hint ? "Diff hint from the orchestrator: " + a.diff_hint + "\n" : "") +
    VERDICT_BLOCK
  );
}

// Normalize args: depending on the invocation path, args may arrive as a JSON
// string instead of a parsed object. Parse errors leave an empty object, which
// fails closed via the missing-required-args path below.
let _args = {};
try { _args = typeof args === "string" ? JSON.parse(args) : (args || {}); } catch { _args = {}; }

const a = {
  sprint: _args.sprint,
  branch: _args.branch,
  base: _args.base || "main",
  charter_path: _args.charter_path,
  workdir: _args.workdir || "",
  diff_hint: _args.diff_hint || "",
  product: !(_args.product === false),
};

// Required-args validation — fail closed instead of interpolating "undefined" into prompts.
const _missing = [];
if (a.sprint == null || a.sprint === "") _missing.push("sprint");
if (!a.branch) _missing.push("branch");
if (!a.charter_path) _missing.push("charter_path");
if (!a.workdir) _missing.push("workdir");
if (_missing.length > 0) {
  const _errMsg = "missing required args: " + _missing.join(", ");
  log("superflow-review: " + _errMsg);
  return { product: null, technical: null, pass: false, error: _errMsg };
}

log("superflow-review: sprint " + a.sprint + " — reviewing " + a.branch + " vs " + a.base +
    (a.product ? "" : " (technical-only, product skipped)"));

phase("Review");
let _productText = null;
let _technicalText = null;

if (a.product) {
  const _texts = (await parallel([() => agent(productPrompt(a)), () => agent(technicalPrompt(a))])) || [];
  _productText = _texts[0] != null ? _texts[0] : null;
  _technicalText = _texts[1] != null ? _texts[1] : null;
} else {
  const _texts = (await parallel([() => agent(technicalPrompt(a))])) || [];
  _technicalText = _texts[0] != null ? _texts[0] : null;
}

const product = a.product ? parseVerdict(_productText, "product") : null;
const technical = parseVerdict(_technicalText, "technical");
const pass = (!a.product || isPass(product.verdict)) && isPass(technical.verdict);

log(
  "superflow-review: product=" + (product ? product.verdict : "SKIPPED") +
  " technical=" + technical.verdict + " pass=" + pass
);
return { product, technical, pass };

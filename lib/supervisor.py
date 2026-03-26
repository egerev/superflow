"""Supervisor: worktree lifecycle, prompt building, sprint execution, and run loop."""
import glob
import json
import logging
import os
import re
import shlex
import signal
import shutil
import threading
import subprocess
import time
from contextlib import nullcontext
from datetime import datetime, timezone

from lib.checkpoint import save_checkpoint

logger = logging.getLogger(__name__)

# Global shutdown event — set by signal handler
_shutdown_event = threading.Event()

# --- Validation constants ---
VALID_PASS_VERDICTS = {"APPROVE", "ACCEPTED", "PASS"}
REQUIRED_PAR_KEYS = {"claude_product", "technical_review"}
REQUIRED_HOLISTIC_KEYS = {"claude_product", "technical_review"}
REQUIRED_SUMMARY_KEYS = {"status", "pr_url", "tests", "par"}


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT by setting the shutdown event."""
    _shutdown_event.set()
    logger.info("Shutdown requested (signal %d). Will stop after current sprint.", signum)


def install_signal_handlers():
    """Install signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


def create_worktree(sprint: dict, repo_root: str) -> str:
    """Create a git worktree for the sprint.

    Handles branch-already-exists (retries without -b) and
    worktree-already-exists (removes and recreates).
    Returns the worktree path.
    """
    wt_path = os.path.join(repo_root, ".worktrees", f"sprint-{sprint['id']}")
    branch = sprint["branch"]

    # Try with -b (create new branch)
    result = subprocess.run(
        ["git", "worktree", "add", wt_path, "-b", branch],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return wt_path

    stderr = result.stderr.lower()

    # Branch already exists — try without -b
    if "already exists" in stderr:
        result2 = subprocess.run(
            ["git", "worktree", "add", wt_path, branch],
            cwd=repo_root, capture_output=True, text=True,
        )
        if result2.returncode == 0:
            return wt_path
        stderr = result2.stderr.lower()

    # Worktree already locked/exists — remove and recreate
    if "already" in stderr or "locked" in stderr:
        subprocess.run(
            ["git", "worktree", "remove", "--force", wt_path],
            cwd=repo_root, capture_output=True, text=True,
        )
        result3 = subprocess.run(
            ["git", "worktree", "add", wt_path, branch],
            cwd=repo_root, capture_output=True, text=True,
        )
        if result3.returncode == 0:
            return wt_path
        raise RuntimeError(f"Failed to create worktree: {result3.stderr}")

    raise RuntimeError(f"Failed to create worktree: {result.stderr}")


def cleanup_worktree(sprint: dict, repo_root: str) -> None:
    """Remove the worktree for a sprint. Uses --force to handle uncommitted changes."""
    wt_path = os.path.join(repo_root, ".worktrees", f"sprint-{sprint['id']}")
    result = subprocess.run(
        ["git", "worktree", "remove", "--force", wt_path],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("Failed to remove worktree %s: %s", wt_path, result.stderr)


def _extract_plan_section(content: str, fragment: str) -> str:
    """Extract a section from markdown content matching the fragment.

    Uses shared sprint heading parser for sprint-type fragments (e.g., 'sprint-1').
    Falls back to generic heading matching for other fragment types.
    """
    from lib.planner import _parse_sprint_headings

    # Check if this is a sprint-type fragment
    sprint_match = re.match(r'^sprint[- ](\d+)$', fragment.lower())
    if sprint_match:
        sprint_id = int(sprint_match.group(1))
        headings = _parse_sprint_headings(content)
        for h in headings:
            if h["id"] == sprint_id:
                lines = content.split("\n")
                return "\n".join(lines[h["start_line"]:h["end_line"]]).strip()
        # Sprint not found — fall through to generic logic
        return content

    # Generic heading matching (non-sprint fragments)
    normalized = fragment.replace("-", " ").lower()
    lines = content.split("\n")
    start_idx = None
    heading_level = None

    for i, line in enumerate(lines):
        match = re.match(r"^(#+)\s+(.*)", line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip().lower()
            # Normalize title for comparison
            title_normalized = re.sub(r"[:\-—_]", " ", title).strip()
            if normalized == title_normalized or normalized == title_normalized.rstrip(':'):
                start_idx = i
                heading_level = level
                break

    if start_idx is None:
        return content  # Fragment not found, return full content

    # Find next heading at same or higher level
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        match = re.match(r"^(#+)\s+", lines[i])
        if match and len(match.group(1)) <= heading_level:
            end_idx = i
            break

    return "\n".join(lines[start_idx:end_idx]).strip()


def build_prompt(sprint: dict, repo_root: str, queue_metadata: dict | None = None) -> str:
    """Build the sprint execution prompt from the template.

    Reads template, CLAUDE.md, llms.txt, and the sprint plan section.
    Fills all placeholders and returns the completed prompt.
    """
    template_path = os.path.join(repo_root, "templates", "supervisor-sprint-prompt.md")
    with open(template_path) as f:
        template = f.read()

    # Read optional files
    claude_md = ""
    claude_md_path = os.path.join(repo_root, "CLAUDE.md")
    if os.path.exists(claude_md_path):
        with open(claude_md_path) as f:
            claude_md = f.read()

    llms_txt = ""
    llms_txt_path = os.path.join(repo_root, "llms.txt")
    if os.path.exists(llms_txt_path):
        with open(llms_txt_path) as f:
            llms_txt = f.read()


    # Read charter file from queue metadata
    charter = ""
    meta = queue_metadata or {}
    charter_file = meta.get("charter_file", "")
    if charter_file:
        charter_path = os.path.join(repo_root, charter_file)
        if os.path.exists(charter_path):
            with open(charter_path) as f:
                charter = f.read()
        else:
            logger.warning("Charter file not found: %s", charter_path)
    if not charter:
        charter = "<!-- No Autonomy Charter provided for this sprint -->"

    # Extract plan section
    plan_file = sprint["plan_file"]
    if "#" in plan_file:
        file_part, fragment = plan_file.rsplit("#", 1)
    else:
        file_part = plan_file
        fragment = None

    plan_path = os.path.join(repo_root, file_part)
    # Security: validate path stays within repo
    real_plan = os.path.realpath(plan_path)
    real_repo = os.path.realpath(repo_root)
    if not real_plan.startswith(real_repo + os.sep) and real_plan != real_repo:
        raise ValueError(f"Path traversal detected: {plan_file} resolves outside repo")
    if os.path.exists(plan_path):
        with open(plan_path) as f:
            plan_content = f.read()
        if fragment:
            sprint_plan = _extract_plan_section(plan_content, fragment)
        else:
            sprint_plan = plan_content
    else:
        sprint_plan = f"(plan file not found: {plan_file})"

    # Extract complexity and derive implementation tier
    complexity = sprint.get("complexity", "medium")
    tier_map = {
        "simple": ("fast-implementer", "sonnet", "low"),
        "medium": ("standard-implementer", "sonnet", "medium"),
        "complex": ("deep-implementer", "opus", "high"),
    }
    implementation_tier, impl_model, impl_effort = tier_map.get(
        complexity, tier_map["medium"]
    )

    # Fill placeholders using str.replace() instead of str.format()
    # because templates contain literal JSON braces
    result = template
    result = result.replace("{sprint_id}", str(sprint["id"]))
    result = result.replace("{sprint_title}", sprint["title"])
    result = result.replace("{sprint_plan}", sprint_plan)
    result = result.replace("{claude_md}", claude_md)
    result = result.replace("{llms_txt}", llms_txt)
    result = result.replace("{charter}", charter)
    result = result.replace("{branch}", sprint["branch"])
    result = result.replace("{complexity}", complexity)
    result = result.replace("{implementation_tier}", implementation_tier)
    result = result.replace("{impl_model}", impl_model)
    result = result.replace("{impl_effort}", impl_effort)

    # Baseline status injection
    baseline_skipped = sprint.get("baseline_skipped", False)
    if baseline_skipped:
        baseline_status = (
            "Baseline tests were not available — exercise caution with test failures "
            "(they may be pre-existing, not from your changes)."
        )
    else:
        baseline_status = (
            "Baseline tests passed in this worktree (verified by supervisor before your session). "
            "If you encounter test failures, they are from YOUR changes, not pre-existing."
        )
    result = result.replace("{baseline_status}", baseline_status)

    # Frontend instructions injection
    frontend_instructions = ""
    if sprint.get("has_frontend", False):
        frontend_instructions = (
            "7. FRONTEND VERIFICATION (MANDATORY — this sprint has frontend changes):\n"
            "   After unified review and post-review tests, use webapp-testing skill (Playwright)\n"
            "   to walk user flows from the spec. Take screenshots, capture console errors.\n"
            "   Write `frontend_verification` key in .par-evidence.json (PASS/FAIL).\n"
            "   If FAIL → fix → re-verify. Include `frontend_evidence` dict with screenshots and error count.\n"
        )
        if "{frontend_instructions}" not in result:
            logger.warning(
                "has_frontend=True but template lacks {frontend_instructions} placeholder"
            )
    result = result.replace("{frontend_instructions}", frontend_instructions)
    return result


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


_PHASE_LABELS = {0: "Onboarding", 1: "Product Discovery", 2: "Autonomous Execution", 3: "Merge"}
_STAGE_INDICES = {"setup": 0, "implementation": 1, "review": 2, "par": 3, "ship": 4, "failed": -1}


def _write_state(repo_root: str, phase: int, sprint: int | None,
                 stage: str, queue) -> None:
    state_path = os.path.join(repo_root, ".superflow-state.json")
    existing = {}
    try:
        with open(state_path) as _f:
            existing = json.load(_f)
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, json.JSONDecodeError):
        existing = {}
    completed = [s["id"] for s in queue.sprints if s.get("status") == "completed"]
    existing.update({
        "version": 1,
        "phase": phase,
        "phase_label": _PHASE_LABELS.get(phase, "Unknown"),
        "sprint": sprint,
        "stage": stage,
        "stage_index": _STAGE_INDICES.get(stage, 0),
        "tasks_done": completed,
        "tasks_total": len(queue.sprints),
        "last_updated": _now_iso(),
    })
    tmp_path = state_path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(existing, f, indent=2)
        os.replace(tmp_path, state_path)
    except OSError as e:
        logger.warning("Failed to write state file: %s", e)


REQUIRED_STEPS = {"baseline_tests", "implementation", "par", "pr_created"}


def _verify_steps(summary: dict) -> list[str]:
    """Check if all required steps were completed. Returns list of missing steps."""
    completed = set(summary.get("steps_completed", []))
    return sorted(REQUIRED_STEPS - completed)


def _parse_json_summary(output: str) -> dict | None:
    """Parse a trailing JSON object from model output.

    Supports both sprint summaries (`status`) and reviewer verdict payloads
    (`verdict`) because both are emitted as the final line of model output.
    """
    if not output:
        return None
    # Strip ANSI escape sequences
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    output = ansi_escape.sub('', output)
    lines = output.strip().splitlines()
    # Try last 5 lines (in case of trailing whitespace/logs)
    for line in reversed(lines[-5:]):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and ("status" in data or "verdict" in data):
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


# Tier 2: sprint subprocess deny-list. ANTHROPIC_API_KEY and GITHUB_TOKEN intentionally excluded (required by claude -p and gh).
_SPRINT_ENV_DENY_LIST = {
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "DATABASE_URL", "DB_PASSWORD",
    "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "HCLOUD_TOKEN", "SECRET_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "SLACK_TOKEN", "SLACK_BOT_TOKEN",
    "STRIPE_SECRET_KEY", "STRIPE_API_KEY",
    "SSH_AUTH_SOCK", "SSH_AGENT_PID",
    "NPM_TOKEN",
    "DOCKER_PASSWORD",
    "HEROKU_API_KEY",
    "SENTRY_DSN",
}


def _filtered_env():
    """Filter env vars: pass everything except known sensitive keys."""
    return {k: v for k, v in os.environ.items() if k not in _SPRINT_ENV_DENY_LIST}


def _validate_evidence_verdicts(data, required_keys, context="PAR"):
    """Validate evidence dict has required keys with valid pass verdicts.

    Shared by PAR validation and holistic review validation.
    Returns (valid: bool, errors: list[str]).
    """
    errors = []
    for key in required_keys:
        if key not in data:
            errors.append(f"{context}: missing key '{key}'")
        elif data[key] not in VALID_PASS_VERDICTS:
            errors.append(f"{context}: invalid verdict '{data[key]}' for key '{key}'")
    return (len(errors) == 0, errors)


def _validate_par_evidence(wt_path, require_frontend=False):
    """Read and validate .par-evidence.json from worktree.

    Args:
        wt_path: Path to worktree root.
        require_frontend: If True, 'frontend_verification' key is mandatory.

    Returns (valid: bool, data: dict, errors: list[str]).
    """
    evidence_path = os.path.join(wt_path, ".par-evidence.json")
    if not os.path.exists(evidence_path):
        return (False, {}, ["File .par-evidence.json not found in worktree"])

    try:
        with open(evidence_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return (False, {}, [f"Failed to parse .par-evidence.json: {e}"])

    if not isinstance(data, dict):
        return (False, {}, [f"PAR evidence must be a JSON object, got {type(data).__name__}"])

    required = set(REQUIRED_PAR_KEYS)
    if require_frontend:
        required.add("frontend_verification")

    valid, errors = _validate_evidence_verdicts(data, required, context="PAR")
    return (valid, data, errors)


def _validate_sprint_summary(summary):
    """Validate sprint JSON summary has required keys and valid types.

    Returns (valid: bool, errors: list[str]).
    """
    errors = []

    # Key presence
    missing = REQUIRED_SUMMARY_KEYS - set(summary.keys())
    if missing:
        errors.append(f"Missing keys: {missing}")

    # Type checks
    if "status" in summary and summary["status"] != "completed":
        errors.append(f"Status is '{summary['status']}', expected 'completed'")
    if "pr_url" in summary and not isinstance(summary["pr_url"], str):
        errors.append("pr_url must be a string")
    if "tests" in summary and not isinstance(summary["tests"], dict):
        errors.append("tests must be a dict")
    if "par" in summary and not isinstance(summary["par"], dict):
        errors.append("par must be a dict")

    return (len(errors) == 0, errors)


def _resolve_baseline_cmd(wt_path, sprint, queue):
    """Resolve baseline test command by priority.

    Priority: sprint config > queue config > heuristic > None.
    Heuristic: conservative, NO auto-install.
    Returns command string or None.
    """
    # 1. Sprint-level override
    cmd = sprint.get("baseline_cmd")
    if cmd:
        return cmd

    # 2. Queue-level default
    cmd = getattr(queue, "baseline_cmd", None)
    if cmd:
        return cmd

    # 3. Heuristic detection
    # Python: pytest.ini
    if os.path.exists(os.path.join(wt_path, "pytest.ini")):
        return "python -m pytest --tb=short -q"

    # Python: pyproject.toml with [tool.pytest] section
    pyproject_path = os.path.join(wt_path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path) as f:
                content = f.read()
            if "[tool.pytest" in content:
                return "python -m pytest --tb=short -q"
        except (IOError, OSError):
            pass

    # JavaScript: package.json with "test" script (skip npm placeholder)
    package_json_path = os.path.join(wt_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path) as f:
                pkg = json.load(f)
            test_script = pkg.get("scripts", {}).get("test", "")
            if test_script and "no test specified" not in test_script and "Error: no test" not in test_script:
                return "npm test"
        except (json.JSONDecodeError, IOError, OSError):
            pass

    # Ruby: Gemfile
    if os.path.exists(os.path.join(wt_path, "Gemfile")):
        return "bundle exec rspec"

    # Go: go.mod
    if os.path.exists(os.path.join(wt_path, "go.mod")):
        return "go test ./..."

    # Elixir: mix.exs
    if os.path.exists(os.path.join(wt_path, "mix.exs")):
        return "mix test"

    return None  # No runner found


def run_baseline_tests(wt_path, sprint, queue, timeout=300):
    """Run baseline test suite in worktree.

    Returns (passed: bool, output: str, skipped: bool).
    """
    cmd = _resolve_baseline_cmd(wt_path, sprint, queue)
    if cmd is None:
        return (True, "No test runner detected — skipped", True)

    try:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        result = subprocess.run(
            cmd, shell=False, cwd=wt_path, timeout=timeout,
            capture_output=True, text=True,
        )
        output = result.stdout + "\n" + result.stderr
        return (result.returncode == 0, output, False)
    except subprocess.TimeoutExpired:
        return (False, f"Baseline tests timed out after {timeout}s", False)


def _detect_codex():
    """Detect if Codex CLI is available. Returns True if available."""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _build_holistic_prompt(role, focus, diffs, plan_content):
    """Build a holistic review prompt for a specific reviewer role.

    Args:
        role: Reviewer role name (e.g., 'Technical', 'Product').
        focus: Focus description for the reviewer.
        diffs: Combined diff string from all sprint branches.
        plan_content: The plan/spec content for reference.

    Returns:
        Prompt string for the reviewer.
    """
    return (
        f"You are a {role} reviewer performing a Final Holistic Review of ALL sprint changes.\n\n"
        f"## Focus\n{focus}\n\n"
        f"## Plan/Spec\n{plan_content}\n\n"
        f"## Combined Diffs (all sprints)\n```diff\n{diffs}\n```\n\n"
        f"## Instructions\n"
        f"Review ALL changes as a unified system. Per-sprint reviews already passed — "
        f"you are looking for cross-module issues that individual reviews missed.\n\n"
        f"Focus areas:\n"
        f"- Cross-module integration issues\n"
        f"- Inconsistent patterns across sprints\n"
        f"- Missing error handling at module boundaries\n"
        f"- Security issues that only appear when modules interact\n"
        f"- Performance issues from combined changes\n\n"
        f"## Output\n"
        f"Output your review, then on the LAST LINE output exactly one JSON object:\n"
        f'{{"verdict": "APPROVE"}} or {{"verdict": "REQUEST_CHANGES", '
        f'"findings": [{{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "description": "..."}}]}}\n'
    )


def _run_single_reviewer(name, cmd, prompt, env, timeout, is_codex=False, cwd=None):
    """Run a single reviewer subprocess and parse its verdict.

    Args:
        name: Reviewer name (for logging/identification).
        cmd: Command list (e.g., ["claude", "-p", "--verbose"]).
        prompt: Prompt string to send.
        env: Environment dict.
        timeout: Timeout in seconds.
        is_codex: If True, prompt is passed as last argument, not via stdin.
        cwd: Working directory for the reviewer subprocess.

    Returns:
        dict with keys: name, verdict, findings, raw_output, error.
    """
    result_dict = {"name": name, "verdict": None, "findings": [], "raw_output": "", "error": None}
    try:
        if is_codex:
            proc = subprocess.run(
                cmd + [prompt],
                capture_output=True, text=True, env=env, timeout=timeout, cwd=cwd,
            )
        else:
            proc = subprocess.run(
                cmd,
                input=prompt, capture_output=True, text=True, env=env,
                timeout=timeout, cwd=cwd,
            )
        result_dict["raw_output"] = proc.stdout or ""

        # Parse verdict from last line
        parsed = _parse_json_summary(proc.stdout or "")
        if parsed and "verdict" in parsed:
            result_dict["verdict"] = parsed["verdict"]
            result_dict["findings"] = parsed.get("findings", [])
        else:
            # Try to extract verdict from output text as fallback
            output_text = proc.stdout or ""
            if "APPROVE" in output_text and "REQUEST_CHANGES" not in output_text:
                result_dict["verdict"] = "APPROVE"
            elif "REQUEST_CHANGES" in output_text:
                result_dict["verdict"] = "REQUEST_CHANGES"
            else:
                result_dict["error"] = "Could not parse verdict from reviewer output"

    except subprocess.TimeoutExpired:
        result_dict["error"] = f"Reviewer {name} timed out after {timeout}s"
    except Exception as e:
        result_dict["error"] = f"Reviewer {name} failed: {str(e)[:200]}"

    return result_dict


def _detect_default_branch(repo_root):
    """Detect the default branch of the repo via git symbolic-ref.

    Returns the branch name (e.g. 'main', 'master', 'develop').
    Falls back to 'main' if detection fails.
    """
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output is like "refs/remotes/origin/main"
            ref = result.stdout.strip()
            return ref.split("/")[-1]
    except Exception:
        pass
    return "main"


def run_holistic_review(queue, queue_path, repo_root, plan_path, checkpoints_dir,
                        timeout=1800, notifier=None, max_retries=2):
    """Execute Final Holistic Review — 2 parallel reviewers on all sprint diffs.

    Dispatches 2 reviewer sessions:
      1. Product Acceptance (claude_product)
      2. Technical Review (technical_review — Codex or split-focus Claude)

    Each returns {"verdict": "APPROVE|REQUEST_CHANGES", "findings": [...]}.
    Aggregates verdicts into .holistic-review-evidence.json.
    Returns True if both pass, False after max_retries.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Save holistic checkpoint: in_progress
    save_checkpoint(checkpoints_dir, "holistic", {
        "phase": "holistic_review",
        "status": "in_progress",
        "started_at": _now_iso(),
    })

    # 1. Collect completed sprint branches and PR URLs
    completed_sprints = [s for s in queue.sprints if s["status"] == "completed"]
    sprint_prs = [s.get("pr", "") for s in completed_sprints if s.get("pr")]

    # 2. Generate combined diffs
    default_branch = _detect_default_branch(repo_root)
    diffs_parts = []
    for sprint in completed_sprints:
        branch = sprint.get("branch", "")
        if not branch:
            continue
        try:
            diff_result = subprocess.run(
                ["git", "diff", f"{default_branch}...{branch}"],
                capture_output=True, text=True, cwd=repo_root, timeout=60,
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                diffs_parts.append(
                    f"# Sprint {sprint['id']}: {sprint.get('title', '')}\n"
                    f"{diff_result.stdout}"
                )
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.warning("Failed to get diff for branch %s: %s", branch, e)
    combined_diffs = "\n".join(diffs_parts) if diffs_parts else "(no diffs available)"

    # 3. Read plan content
    plan_content = ""
    if plan_path and os.path.exists(plan_path):
        try:
            with open(plan_path) as f:
                plan_content = f.read()
        except IOError:
            plan_content = "(plan file not readable)"

    # 4. Detect Codex availability
    has_codex = _detect_codex()
    env = _filtered_env()

    # 5. Define reviewer configurations
    if has_codex:
        reviewers = [
            {
                "name": "claude_product",
                "cmd": ["claude", "-p", "--verbose"],
                "is_codex": False,
                "role": "Product Acceptance",
                "focus": (
                    "Spec compliance, user scenarios, data correctness, completeness. "
                    "Focus on cross-sprint user flow gaps."
                ),
            },
            {
                "name": "technical_review",
                "cmd": ["codex", "exec", "--full-auto"],
                "is_codex": True,
                "role": "Technical Review",
                "focus": (
                    "Correctness, security, error handling, performance, "
                    "architecture patterns, API consistency, module boundaries. "
                    "Focus on cross-module integration bugs, race conditions, "
                    "and design debt introduced across sprints."
                ),
            },
        ]
    else:
        # Split-focus: 2 Claude sessions with different perspectives
        reviewers = [
            {
                "name": "claude_product",
                "cmd": ["claude", "-p", "--verbose"],
                "is_codex": False,
                "role": "Product Acceptance",
                "focus": (
                    "Spec compliance, user scenarios, data correctness, completeness. "
                    "Focus on cross-sprint user flow gaps."
                ),
            },
            {
                "name": "technical_review",
                "cmd": ["claude", "-p", "--verbose"],
                "is_codex": False,
                "role": "Technical Review (split-focus)",
                "focus": (
                    "Correctness, security, error handling, performance, "
                    "architecture patterns, API consistency, module boundaries. "
                    "Focus on cross-module integration bugs, race conditions, "
                    "and design debt introduced across sprints."
                ),
            },
        ]

    # 6. Run review-fix cycles
    findings_resolved = 0
    evidence_path = os.path.join(
        os.path.dirname(checkpoints_dir),
        ".holistic-review-evidence.json",
    )

    reviewer_results = {}
    failing_reviewers = [rev["name"] for rev in reviewers]

    for attempt in range(max_retries + 1):
        # Build prompts and dispatch all reviewers in parallel
        attempt_results = dict(reviewer_results)

        # On retry, only re-run failing reviewers
        reviewers_to_run = reviewers if attempt == 0 else [
            r for r in reviewers if r["name"] in failing_reviewers
        ]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for rev in reviewers_to_run:
                prompt = _build_holistic_prompt(
                    rev["role"], rev["focus"], combined_diffs, plan_content
                )
                future = executor.submit(
                    _run_single_reviewer,
                    rev["name"], rev["cmd"], prompt, env, timeout,
                    is_codex=rev["is_codex"], cwd=repo_root,
                )
                futures[future] = rev["name"]

            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    attempt_results[name] = result
                except Exception as e:
                    attempt_results[name] = {
                        "name": name, "verdict": None, "findings": [],
                        "raw_output": "", "error": str(e)[:200],
                    }

        # 7. Evaluate verdicts
        all_approve = True
        next_failing_reviewers = []
        for rev in reviewers:
            name = rev["name"]
            res = attempt_results.get(name)
            if not res or res.get("error") or res.get("verdict") not in VALID_PASS_VERDICTS:
                all_approve = False
                next_failing_reviewers.append(name)
                # Check if findings have CRITICAL/HIGH severity
                if res and res.get("findings"):
                    for f in res["findings"]:
                        sev = f.get("severity", "").upper()
                        if sev in ("CRITICAL", "HIGH"):
                            logger.warning(
                                "Holistic review %s: %s finding: %s",
                                name, sev, f.get("description", "")[:100]
                            )

        if all_approve:
            # Write evidence file
            evidence = {
                "timestamp": _now_iso(),
                "verdict": "APPROVE",
                "claude_product": attempt_results.get("claude_product", {}).get("verdict", "UNKNOWN"),
                "technical_review": attempt_results.get("technical_review", {}).get("verdict", "UNKNOWN"),
                "provider": "codex" if has_codex else "split-focus",
                "sprint_prs": sprint_prs,
                "findings_resolved": findings_resolved,
            }
            with open(evidence_path, "w") as f:
                json.dump(evidence, f, indent=2)

            # Update checkpoint
            save_checkpoint(checkpoints_dir, "holistic", {
                "phase": "holistic_review",
                "status": "completed",
                "completed_at": _now_iso(),
                "verdict": "APPROVE",
            })
            return True

        # Not all approved — attempt fix cycle if not last attempt
        if attempt < max_retries:
            logger.info(
                "Holistic review attempt %d/%d: %d reviewers need fixes: %s",
                attempt + 1, max_retries + 1, len(next_failing_reviewers), next_failing_reviewers
            )

            # Collect findings from failing reviewers for the fixer
            all_findings = []
            for name in next_failing_reviewers:
                res = attempt_results.get(name, {})
                for f in res.get("findings", []):
                    all_findings.append(f"[{name}] {f.get('severity', 'UNKNOWN')}: {f.get('description', '')}")

            findings_resolved += len(all_findings)

            # Launch fixer session
            if all_findings:
                fixer_prompt = (
                    "Fix the following issues found during holistic review:\n\n"
                    + "\n".join(f"- {f}" for f in all_findings)
                    + "\n\nApply minimal targeted fixes. Do NOT refactor unrelated code."
                )
                try:
                    subprocess.run(
                        ["claude", "-p", "--verbose"],
                        input=fixer_prompt, capture_output=True, text=True,
                        env=env, timeout=timeout, cwd=repo_root,
                    )
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.warning("Fixer session failed: %s", e)
        else:
            logger.error(
                "Holistic review failed after %d attempts. Failing reviewers: %s",
                max_retries + 1, next_failing_reviewers
            )

        reviewer_results = attempt_results
        failing_reviewers = next_failing_reviewers

    # Max retries exceeded — collect last round's findings for diagnostics
    last_findings = []
    for name in failing_reviewers:
        res = reviewer_results.get(name, {})
        for finding in res.get("findings", []):
            last_findings.append({
                "reviewer": name,
                "severity": finding.get("severity", "UNKNOWN"),
                "description": finding.get("description", ""),
            })
        if res.get("error"):
            last_findings.append({
                "reviewer": name,
                "severity": "ERROR",
                "description": res["error"],
            })

    save_checkpoint(checkpoints_dir, "holistic", {
        "phase": "holistic_review",
        "status": "failed",
        "failed_at": _now_iso(),
        "verdict": "REQUEST_CHANGES",
        "failing_reviewers": failing_reviewers,
        "last_findings": last_findings,
    })
    return False


def execute_sprint(sprint, queue, queue_path, checkpoints_dir, repo_root,
                   timeout=1800, notifier=None, queue_lock=None):
    """Execute a single sprint: worktree, claude invocation, result handling.

    Returns the checkpoint dict for this sprint.
    """
    sid = sprint["id"]

    # 1. Mark in_progress
    if queue_lock:
        with queue_lock:
            queue.mark_in_progress(sid)
            queue.save(queue_path)
    else:
        queue.mark_in_progress(sid)
        queue.save(queue_path)

    # 2. Notify sprint start
    if notifier:
        try:
            notifier.notify_sprint_start(sid, sprint.get("title", f"Sprint {sid}"))
        except Exception as e:
            logger.warning("Notifier error: %s", e)

    # 3. Save initial checkpoint
    save_checkpoint(checkpoints_dir, sid, {
        "sprint_id": sid, "status": "in_progress", "started_at": _now_iso(),
    })

    # 4. Create worktree
    wt_path = create_worktree(sprint, repo_root)

    # 5. Write state AFTER worktree creation (sequential mode only)
    if not queue_lock:
        _write_state(repo_root, phase=2, sprint=sid, stage="setup", queue=queue)

    try:
        # 5. Baseline test gate
        baseline_passed, baseline_output, baseline_skipped = run_baseline_tests(
            wt_path, sprint, queue, timeout=300
        )
        if not baseline_passed:
            logger.warning("Baseline tests failed for sprint %s", sid)
            if notifier:
                notifier.notify_baseline_failed(sid, sprint.get("title", f"Sprint {sid}"))
            if queue_lock:
                with queue_lock:
                    queue.mark_failed(sid, f"Baseline tests failed: {baseline_output[:500]}")
                    queue.save(queue_path)
            else:
                queue.mark_failed(sid, f"Baseline tests failed: {baseline_output[:500]}")
                queue.save(queue_path)
            cp = {
                "sprint_id": sid, "status": "failed",
                "failed_at": _now_iso(), "error": "baseline_tests_failed",
                "baseline_output": baseline_output[:2000],
            }
            save_checkpoint(checkpoints_dir, sid, cp)
            return cp

        # 6. Save baseline milestone in checkpoint
        # Also store baseline_skipped on sprint dict so build_prompt can use it
        sprint["baseline_skipped"] = baseline_skipped
        save_checkpoint(checkpoints_dir, sid, {
            "sprint_id": sid, "status": "in_progress", "started_at": _now_iso(),
            "milestones": {"baseline_passed": True, "baseline_skipped": baseline_skipped},
        })

        # 7. Execute sprint with Claude
        result = _attempt_sprint(sprint, queue, queue_path, checkpoints_dir,
                                 repo_root, wt_path, timeout, queue_lock,
                                 notifier=notifier)
        return result
    finally:
        # Always cleanup worktree
        cleanup_worktree(sprint, repo_root)
        if notifier:
            _notify_sprint_result(notifier, sprint)


def _attempt_sprint(sprint, queue, queue_path, checkpoints_dir, repo_root,
                    wt_path, timeout, queue_lock=None, notifier=None):
    """Run claude for a sprint, with retry logic.

    Integrates:
    - Summary validation (treated as JSON parse error on failure)
    - PAR evidence validation (separate retry counter, max 2)
    - Milestone writes at each transition
    - PR verification retry (3 attempts, 5s delay, separate from Claude retry)
    """
    sid = sprint["id"]
    lock = queue_lock or nullcontext()
    par_retries = 0
    max_par_retries = 2
    attempt_counter = 0
    last_par_errors = None
    last_summary_errors = None

    while True:
        attempt_counter += 1

        # Rebuild prompt fresh each iteration to avoid unbounded growth
        prompt = build_prompt(sprint, repo_root, queue_metadata=queue.metadata)

        # Append retry-specific instructions based on PREVIOUS iteration errors
        if last_par_errors:
            prompt += (
                "\n\nIMPORTANT: PAR evidence validation FAILED. Errors: "
                + "; ".join(last_par_errors)
                + ". You MUST write a valid .par-evidence.json with all 4 verdict keys."
            )
            last_par_errors = None

        if last_summary_errors:
            prompt += (
                "\n\nIMPORTANT: Your JSON summary had validation errors: "
                + "; ".join(last_summary_errors)
                + ". Fix the summary and output it as the LAST line."
            )
            last_summary_errors = None

        # Filter environment
        env = _filtered_env()

        # Write state before implementation
        if not queue_lock:
            _write_state(repo_root, phase=2, sprint=sid, stage="implementation", queue=queue)

        # Launch claude subprocess
        try:
            result = subprocess.run(
                ["claude", "-p", "--verbose"],
                input=prompt, cwd=wt_path, timeout=timeout,
                capture_output=True, text=True, env=env,
            )
        except subprocess.TimeoutExpired:
            result = type("Result", (), {
                "returncode": 1, "stdout": "Timeout expired", "stderr": ""
            })()

        # Save output log (per attempt, not overwritten on retry)
        os.makedirs(checkpoints_dir, exist_ok=True)
        log_path = os.path.join(checkpoints_dir, f"sprint-{sid}-attempt-{attempt_counter}-output.log")
        with open(log_path, "w") as f:
            f.write(result.stdout or "")

        # Parse JSON from last line
        summary = _parse_json_summary(result.stdout or "")
        json_parse_error = (result.returncode == 0 and summary is None)

        # Summary validation: if parsed but invalid, treat as json_parse_error
        if summary is not None:
            summary_valid, summary_errors = _validate_sprint_summary(summary)
            if not summary_valid:
                logger.warning("Summary validation failed: %s", summary_errors)
                summary = None
                json_parse_error = True
                last_summary_errors = summary_errors

        success = (result.returncode == 0 and summary is not None)

        if summary:
            missing = _verify_steps(summary)
            if missing:
                logger.warning("Sprint %d missing steps: %s", sid, missing)

        if success:
            # Milestone: implemented
            save_checkpoint(checkpoints_dir, sid, {
                "sprint_id": sid, "status": "in_progress",
                "milestones": {"baseline_passed": True, "implemented": True},
            })

            # PAR evidence validation
            require_frontend = sprint.get("has_frontend", False)
            par_valid, par_data, par_errors = _validate_par_evidence(
                wt_path, require_frontend=require_frontend
            )
            if not par_valid:
                logger.warning("PAR evidence validation failed: %s", par_errors)
                if notifier:
                    notifier.notify_par_validation_failed(
                        sid, sprint.get("title", ""), par_errors)
                par_retries += 1
                if par_retries >= max_par_retries:
                    error_msg = f"PAR evidence invalid after {par_retries} retries: {'; '.join(par_errors)}"
                    with lock:
                        queue.mark_failed(sid, error_msg[:500])
                        queue.save(queue_path)
                    cp = {
                        "sprint_id": sid, "status": "failed",
                        "failed_at": _now_iso(), "error": error_msg[:500],
                        "par_retries": par_retries,
                        "milestones": {"baseline_passed": True, "implemented": True},
                    }
                    save_checkpoint(checkpoints_dir, sid, cp)
                    return cp
                # Set flag for next iteration's prompt rebuild
                last_par_errors = par_errors
                logger.info("PAR retry %d/%d for sprint %d", par_retries, max_par_retries, sid)
                continue  # Re-invoke Claude

            # Milestone: par_validated
            save_checkpoint(checkpoints_dir, sid, {
                "sprint_id": sid, "status": "in_progress",
                "milestones": {"baseline_passed": True, "implemented": True,
                               "par_validated": True},
            })

            # Write ship state (sequential mode only)
            if not queue_lock:
                _write_state(repo_root, phase=2, sprint=sid, stage="ship", queue=queue)

            # PR verification with retry (separate from Claude retry)
            pr_url = summary.get("pr_url", "")
            pr_verified = False
            if pr_url:
                for pr_attempt in range(3):
                    pr_check = subprocess.run(
                        ["gh", "pr", "view", pr_url],
                        capture_output=True, text=True, cwd=repo_root,
                    )
                    if pr_check.returncode == 0:
                        pr_verified = True
                        break
                    if pr_attempt < 2:
                        time.sleep(5)

                if not pr_verified:
                    logger.error("PR verification failed after 3 attempts: %s", pr_url)
                    error_msg = f"PR created but verification failed: {pr_url}"
                    with lock:
                        queue.mark_failed(sid, error_msg[:500])
                        queue.save(queue_path)
                    cp = {
                        "sprint_id": sid, "status": "failed",
                        "failed_at": _now_iso(), "error": error_msg[:500],
                        "milestones": {"baseline_passed": True, "implemented": True,
                                       "par_validated": True},
                    }
                    save_checkpoint(checkpoints_dir, sid, cp)
                    return cp
            else:
                # No PR URL — treat as summary error, retry Claude
                sprint["retries"] = sprint.get("retries", 0) + 1
                if sprint["retries"] >= sprint.get("max_retries", 2):
                    error_msg = "Sprint completed but no PR URL"
                    with lock:
                        queue.mark_failed(sid, error_msg)
                        queue.save(queue_path)
                    cp = {
                        "sprint_id": sid, "status": "failed",
                        "failed_at": _now_iso(), "error": error_msg,
                        "milestones": {"baseline_passed": True, "implemented": True,
                                       "par_validated": True},
                    }
                    save_checkpoint(checkpoints_dir, sid, cp)
                    return cp
                last_summary_errors = [
                    "Your output had an empty or missing pr_url. "
                    "You MUST create a PR and include the URL in the JSON summary."
                ]
                continue

            # Milestone: pr_created
            save_checkpoint(checkpoints_dir, sid, {
                "sprint_id": sid, "status": "in_progress",
                "milestones": {"baseline_passed": True, "implemented": True,
                               "par_validated": True, "pr_created": True},
            })

            # Mark completed
            with lock:
                queue.mark_completed(sid, pr_url)
                queue.save(queue_path)
            cp = {
                "sprint_id": sid, "status": "completed",
                "completed_at": _now_iso(), "pr_url": pr_url,
                "summary": summary,
                "milestones": {"baseline_passed": True, "implemented": True,
                               "par_validated": True, "pr_created": True},
            }
            save_checkpoint(checkpoints_dir, sid, cp)
            return cp

        # Failure path — check retries
        sprint["retries"] = sprint.get("retries", 0) + 1
        if sprint["retries"] >= sprint.get("max_retries", 2):
            # Max retries reached — mark failed
            error_msg = result.stderr or result.stdout or "Unknown error"
            with lock:
                queue.mark_failed(sid, error_msg[:500])
                queue.save(queue_path)
            cp = {
                "sprint_id": sid, "status": "failed",
                "failed_at": _now_iso(), "error": error_msg[:500],
                "retries": sprint["retries"],
                "milestones": {"baseline_passed": True},
            }
            save_checkpoint(checkpoints_dir, sid, cp)
            return cp

        # Retry — if JSON parse error, set flag for next iteration's prompt rebuild
        if json_parse_error:
            last_summary_errors = [
                "Your previous output did not include the required JSON summary "
                "as the LAST line. You MUST output a JSON summary as the very "
                "last line of your response."
            ]
        logger.info("Retrying sprint %d (attempt %d)", sid, sprint["retries"] + 1)


def _notify_sprint_result(notifier, sprint):
    """Call the notifier with the sprint result."""
    try:
        sid = sprint["id"]
        title = sprint.get("title", f"Sprint {sid}")
        if sprint["status"] == "completed":
            notifier.notify_sprint_complete(sid, title, sprint.get("pr", ""))
        elif sprint["status"] == "failed":
            notifier.notify_sprint_failed(
                sid, title, sprint.get("error_log", "unknown"),
                sprint.get("retries", 0), sprint.get("max_retries", 2),
            )
        elif sprint["status"] == "skipped":
            notifier.notify_sprint_skipped(sid, title, sprint.get("error_log", "dependency failed"))
    except Exception as e:
        logger.warning("Notifier error: %s", e)


def preflight(queue, repo_root, notifier=None):
    """Run preflight validation checks before sprint execution.

    Returns (passed: bool, issues: list[str]).
    Issues include both errors (which cause failure) and warnings.
    """
    issues = []
    critical = False

    # Check claude CLI
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.returncode != 0:
            issues.append("claude CLI returned non-zero exit code")
            critical = True
    except FileNotFoundError:
        issues.append("claude CLI not found in PATH")
        critical = True

    # Check git status (warn if dirty, don't abort)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.stdout.strip():
            issues.append("WARNING: git working directory is dirty (uncommitted changes)")
    except FileNotFoundError:
        issues.append("git not found in PATH")
        critical = True

    # Check gh auth
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.returncode != 0:
            issues.append("gh auth failed — not logged in to GitHub CLI")
            critical = True
    except FileNotFoundError:
        issues.append("gh CLI not found in PATH")
        critical = True

    # Validate all plan files exist
    for sprint in queue.sprints:
        plan_file = sprint.get("plan_file", "")
        if "#" in plan_file:
            file_part = plan_file.rsplit("#", 1)[0]
        else:
            file_part = plan_file
        plan_path = os.path.join(repo_root, file_part)
        if not os.path.exists(plan_path):
            issues.append(f"Plan file not found: {file_part}")
            critical = True

    # Check .worktrees is gitignored
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".worktrees"],
            capture_output=True, text=True, cwd=repo_root,
        )
        if result.returncode != 0:
            issues.append(".worktrees/ is not in .gitignore — worktrees could be committed")
            critical = True
    except FileNotFoundError:
        pass  # git not found — already caught above

    # Check disk space
    try:
        usage = shutil.disk_usage("/")
        if usage.free < 1024**3:  # Less than 1GB
            issues.append(
                f"WARNING: Low disk space ({usage.free // (1024**2)}MB free)"
            )
    except Exception as e:
        issues.append(f"WARNING: Could not check disk space: {e}")

    passed = not critical

    if notifier:
        try:
            notifier.notify_preflight(passed, issues)
        except Exception as e:
            logger.warning("Notifier error during preflight: %s", e)

    return passed, issues


def print_summary(queue):
    """Print a formatted summary table of sprint statuses."""
    print("\n" + "=" * 70)
    print(f"{'ID':<5} {'Title':<30} {'Status':<12} {'PR':<15} {'Retries':<7}")
    print("-" * 70)
    for s in queue.sprints:
        pr = s.get("pr") or ""
        if pr and len(pr) > 14:
            pr = "..." + pr[-11:]
        retries = s.get("retries", 0)
        print(f"{s['id']:<5} {s['title'][:29]:<30} {s['status']:<12} {pr:<15} {retries:<7}")
    print("=" * 70)

    summary = queue.summary()
    parts = []
    for status, count in summary.items():
        if count > 0:
            parts.append(f"{status}: {count}")
    print("Summary: " + ", ".join(parts))
    print()


def _run_replan(queue, queue_path, plan_path, repo_root, checkpoints_dir, notifier):
    """Run the adaptive replanner and notify if changes were made."""
    from lib.replanner import replan
    changes = replan(queue, queue_path, plan_path, repo_root, checkpoints_dir)
    if changes and notifier:
        summary = ", ".join(
            f"{c['type']} sprint {c.get('sprint_id', '?')}" for c in changes
        )
        notifier.notify_replan(summary)
    return changes


def _check_skip_requests(repo_root, queue, queue_path=None):
    """Check and apply skip requests from the sidecar directory.

    If queue_path is provided, saves the queue to disk after applying skips
    to prevent skip loss on crash.
    """
    skip_dir = os.path.join(repo_root, ".superflow", "skip-requests")
    if not os.path.isdir(skip_dir):
        return

    applied = False
    for filepath in glob.glob(os.path.join(skip_dir, "*.json")):
        try:
            with open(filepath) as f:
                data = json.load(f)
            sprint_id = data.get("sprint_id")
            reason = data.get("reason", "skip requested")
            if sprint_id is not None:
                queue.mark_skipped(int(sprint_id), reason)
                applied = True
                logger.info("Applied skip request for sprint %s: %s", sprint_id, reason)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Invalid skip request %s: %s", filepath, e)
        finally:
            try:
                os.unlink(filepath)
            except OSError:
                pass

    # Persist skips to prevent loss on crash
    if applied and queue_path:
        queue.save(queue_path)


def run(queue_path, plan_path=None, max_parallel=1, timeout=1800,
        no_replan=False, notifier=None, repo_root=None):
    """Main supervisor run loop.

    Loads the queue, runs preflight, then executes sprints.
    When max_parallel > 1 and multiple sprints are runnable, uses parallel
    execution via ThreadPoolExecutor. After each sprint (or batch), runs
    the adaptive replanner unless no_replan is set.
    Checks _shutdown_event after each sprint for graceful shutdown.
    """
    from lib.queue import SprintQueue
    from lib.parallel import execute_parallel

    install_signal_handlers()
    queue = SprintQueue.load(queue_path)

    if repo_root is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(queue_path)),
            )
            repo_root = result.stdout.strip()
        except Exception:
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(queue_path)))

    # Determine checkpoints dir
    checkpoints_dir = os.path.join(os.path.dirname(queue_path), "checkpoints")

    # Run preflight
    passed, issues = preflight(queue, repo_root, notifier=notifier)
    if issues:
        for issue in issues:
            print(f"  {'[WARN]' if 'WARNING' in issue else '[FAIL]'} {issue}")
    if not passed:
        print("Preflight failed. Aborting.")
        return

    # Main loop
    while not queue.is_done():
        if _shutdown_event.is_set():
            print("Shutdown requested. Saving state and exiting.")
            queue.save(queue_path)
            break

        # Write heartbeat
        heartbeat_path = os.path.join(repo_root, ".superflow", "heartbeat")
        try:
            os.makedirs(os.path.dirname(heartbeat_path), exist_ok=True)
            with open(heartbeat_path, 'w') as f:
                f.write(str(time.time()))
        except OSError:
            pass

        # Check skip requests from sidecar
        _check_skip_requests(repo_root, queue, queue_path)

        runnable = queue.next_runnable(max_parallel=max_parallel)
        if not runnable:
            queue.skip_blocked_sprints()
            queue.save(queue_path)
            if notifier:
                try:
                    notifier.notify_blocked("All remaining sprints depend on failed dependencies")
                except Exception:
                    pass
            break

        # Parallel execution when multiple runnable sprints and max_parallel > 1
        if max_parallel > 1 and len(runnable) > 1:
            execute_parallel(
                runnable, queue, queue_path, checkpoints_dir, repo_root,
                timeout=timeout, notifier=notifier, max_workers=max_parallel,
            )
            queue = SprintQueue.load(queue_path)

            # Run replanner after parallel batch
            if not no_replan and plan_path:
                _run_replan(queue, queue_path, plan_path, repo_root,
                            checkpoints_dir, notifier)
        else:
            # Sequential execution
            for sprint in runnable:
                print(f"\n{'='*60}")
                print(f"Sprint {sprint['id']}/{len(queue.sprints)}: {sprint.get('title', '')}")
                print(f"{'='*60}")
                execute_sprint(
                    sprint, queue, queue_path, checkpoints_dir, repo_root,
                    timeout=timeout, notifier=notifier,
                )
                queue.save(queue_path)

                # Run replanner after each sprint
                if not no_replan and plan_path:
                    _run_replan(queue, queue_path, plan_path, repo_root,
                                checkpoints_dir, notifier)

                if _shutdown_event.is_set():
                    print("Shutdown requested after sprint. Saving state and exiting.")
                    queue.save(queue_path)
                    break

    print_summary(queue)

    if not queue.is_done():
        logger.info(
            "Queue not complete (%s) — skipping holistic review and completion report.",
            queue.summary(),
        )
        return

    # Final Holistic Review gate (mandatory before completion report)
    completed_count = queue.summary().get("completed", 0)
    if completed_count > 0:
        evidence_path = os.path.join(
            os.path.dirname(checkpoints_dir),
            ".holistic-review-evidence.json",
        )

        # Save holistic checkpoint: pending
        save_checkpoint(checkpoints_dir, "holistic", {
            "phase": "holistic_review",
            "status": "pending",
            "started_at": _now_iso(),
        })

        if notifier:
            try:
                notifier.notify_holistic_review_start()
            except Exception as e:
                logger.warning("Notifier error: %s", e)

        # Check if evidence already exists and is valid (skip re-run)
        holistic_valid = False
        holistic_verdict = None
        # Compute current sprint PRs for cache comparison
        current_sprint_prs = sorted(
            s.get("pr", "") for s in queue.sprints
            if s["status"] == "completed" and s.get("pr")
        )
        if os.path.exists(evidence_path):
            try:
                with open(evidence_path) as f:
                    holistic_data = json.load(f)
                reviewers_data = holistic_data.get("reviewers", holistic_data)
                valid, errors = _validate_evidence_verdicts(
                    reviewers_data, REQUIRED_HOLISTIC_KEYS, context="Holistic"
                )
                if not valid:
                    holistic_valid = False
                    logger.warning("Holistic evidence invalid, will re-run: %s", errors)
                else:
                    # Validate sprint_prs match current queue's completed PRs
                    evidence_prs = sorted(holistic_data.get("sprint_prs", []))
                    if evidence_prs != current_sprint_prs:
                        holistic_valid = False
                        logger.warning(
                            "Holistic evidence sprint_prs mismatch (cached=%s, current=%s) — re-running.",
                            evidence_prs, current_sprint_prs,
                        )
                    else:
                        holistic_valid = True
                        holistic_verdict = holistic_data.get("verdict", "APPROVE")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to parse holistic evidence, will re-run: %s", e)

        if not holistic_valid:
            # Dispatch actual holistic review
            holistic_passed = run_holistic_review(
                queue, queue_path, repo_root, plan_path, checkpoints_dir,
                timeout=timeout, notifier=notifier,
            )

            if not holistic_passed:
                print("BLOCKED: Holistic review failed. Cannot generate completion report.")
                if notifier:
                    try:
                        notifier.notify_holistic_review_complete("BLOCKED")
                    except Exception as e:
                        logger.warning("Notifier error: %s", e)
                return
        else:
            save_checkpoint(checkpoints_dir, "holistic", {
                "phase": "holistic_review",
                "status": "completed",
                "completed_at": _now_iso(),
                "verdict": holistic_verdict or "APPROVE",
            })

        if notifier:
            try:
                notifier.notify_holistic_review_complete("APPROVE")
            except Exception as e:
                logger.warning("Notifier error: %s", e)

    # Notify all_done AFTER holistic review passes (not before)
    if notifier:
        try:
            summary_data = queue.summary()
            summary_text = ", ".join(f"{k}: {v}" for k, v in summary_data.items() if v > 0)
            notifier.notify_all_done(summary_text)
        except Exception as e:
            logger.warning("Notifier error: %s", e)

    # Write completion data JSON (for dashboard / external consumers)
    _write_completion_data(queue, checkpoints_dir, repo_root)

    # Generate completion report (only if there were completed sprints)
    if completed_count > 0:
        report = generate_completion_report(queue, checkpoints_dir)
        if report:
            print(report)
    else:
        # No completed sprints — skip report generation entirely
        # (generate_completion_report would raise RuntimeError without evidence)
        logger.info("No completed sprints — skipping completion report.")


def generate_completion_report(queue, checkpoints_dir, output_path=None):
    """Generate Demo Day style completion report from queue and checkpoints.

    Reads all checkpoints and formats a markdown report with per-sprint blocks
    (title, status, PR, tests, PAR) and a summary section.

    GATE: Unconditionally requires .holistic-review-evidence.json in the
    parent directory of checkpoints_dir. Raises RuntimeError if not found.

    Args:
        queue: SprintQueue instance with current sprint states.
        checkpoints_dir: Path to directory containing sprint checkpoint files.
        output_path: If provided, write the report to this file path.

    Returns:
        The report as a markdown string.

    Raises:
        RuntimeError: If .holistic-review-evidence.json does not exist.
    """
    # GATE: unconditional holistic review evidence check (existence + verdict validation)
    evidence_path = os.path.join(
        os.path.dirname(checkpoints_dir),
        ".holistic-review-evidence.json",
    )
    if not os.path.exists(evidence_path):
        raise RuntimeError(
            "Completion report blocked: .holistic-review-evidence.json not found. "
            "Run Final Holistic Review first."
        )
    # Validate evidence contents — all reviewer verdicts must pass
    try:
        with open(evidence_path) as f:
            holistic_data = json.load(f)
        reviewers = holistic_data.get("reviewers", holistic_data)
        valid, errors = _validate_evidence_verdicts(reviewers, REQUIRED_HOLISTIC_KEYS,
                                                     context="Holistic")
        if not valid:
            raise RuntimeError(
                "Completion report blocked: holistic review evidence has invalid verdicts. "
                f"Errors: {'; '.join(errors)}"
            )
    except (json.JSONDecodeError, IOError) as e:
        raise RuntimeError(
            f"Completion report blocked: failed to parse holistic evidence: {e}"
        )

    from lib.checkpoint import load_all_checkpoints

    checkpoints = load_all_checkpoints(checkpoints_dir)
    cp_map = {cp["sprint_id"]: cp for cp in checkpoints}

    lines = []
    lines.append("# Completion Report")
    lines.append("")
    lines.append(f"**Feature:** {queue.feature}")
    lines.append("")

    # Per-sprint blocks
    for sprint in queue.sprints:
        sid = sprint["id"]
        title = sprint["title"]
        status = sprint["status"]
        pr = sprint.get("pr") or "N/A"
        retries = sprint.get("retries", 0)

        lines.append(f"## Sprint {sid}: {title}")
        lines.append("")
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **PR:** {pr}")

        # Extract test and PAR info from checkpoint summary
        cp = cp_map.get(sid, {})
        summary = cp.get("summary", {})

        tests = summary.get("tests")
        if tests:
            passed = tests.get("passed", 0)
            failed = tests.get("failed", 0)
            lines.append(f"- **Tests:** {passed} passed, {failed} failed")
        else:
            lines.append("- **Tests:** N/A")

        par = summary.get("par")
        if par:
            claude_pr = par.get("claude_product", "N/A")
            tech_rev = par.get("technical_review", "N/A")
            provider = par.get("provider", "unknown")
            lines.append(
                f"- **PAR:** Claude-Product={claude_pr}, "
                f"Technical-Review={tech_rev} (provider: {provider})"
            )
        else:
            lines.append("- **PAR:** N/A")

        if retries > 0:
            lines.append(f"- **Retries:** {retries}")

        if status == "failed":
            error = sprint.get("error_log") or cp.get("error", "Unknown")
            lines.append(f"- **Error:** {error[:200]}")

        if status == "skipped":
            reason = sprint.get("error_log") or "dependency failed"
            lines.append(f"- **Reason:** {reason}")

        lines.append("")

    # Summary section
    summary_counts = queue.summary()
    lines.append("## Summary")
    lines.append("")
    total = len(queue.sprints)
    completed = summary_counts.get("completed", 0)
    failed = summary_counts.get("failed", 0)
    skipped = summary_counts.get("skipped", 0)
    lines.append(f"- **Total sprints:** {total}")
    lines.append(f"- **Completed:** {completed}")
    if failed:
        lines.append(f"- **Failed:** {failed}")
    if skipped:
        lines.append(f"- **Skipped:** {skipped}")

    success_rate = (completed / total * 100) if total > 0 else 0
    lines.append(f"- **Success rate:** {success_rate:.0f}%")
    lines.append("")

    report = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)

    return report


def _write_completion_data(queue, checkpoints_dir, repo_root):
    from lib.checkpoint import load_all_checkpoints
    evidence_path = os.path.join(os.path.dirname(checkpoints_dir), ".holistic-review-evidence.json")
    holistic_data = None
    try:
        with open(evidence_path) as _ef: holistic_data = json.load(_ef)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("completion_data: cannot read holistic evidence: %s", e)
        return None
    checkpoints = load_all_checkpoints(checkpoints_dir)
    cp_map = {cp["sprint_id"]: cp for cp in checkpoints}
    sprints_data = []
    for sprint in queue.sprints:
        sid = sprint["id"]
        cp = cp_map.get(sid, {})
        summary = cp.get("summary", {})
        sprints_data.append({
            "id": sid,
            "title": sprint["title"],
            "status": sprint["status"],
            "pr": sprint.get("pr"),
            "tests": summary.get("tests"),
            "par": summary.get("par"),
        })
    known_issues = None
    if isinstance(holistic_data, dict):
        known_issues = holistic_data.get("known_issues")
    completion_data = {
        "feature": queue.feature,
        "generated_at": _now_iso(),
        "sprints": sprints_data,
        "holistic_verdict": holistic_data,
        "known_issues": known_issues,
    }
    out_path = os.path.join(repo_root, "docs", "superflow", "completion-data.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp_path = out_path + ".tmp"
    try:
        with open(tmp_path, "w") as _tf:
            json.dump(completion_data, _tf, indent=2)
        os.replace(tmp_path, out_path)
    except OSError as e:
        logger.warning("completion_data: write failed: %s", e)
        return None
    state_path = os.path.join(repo_root, ".superflow-state.json")
    existing_state = {}
    try:
        with open(state_path) as _sf:
            existing_state = json.load(_sf)
        if not isinstance(existing_state, dict):
            existing_state = {}
    except (OSError, json.JSONDecodeError):
        existing_state = {}
    ctx = existing_state.setdefault("context", {})
    ctx["completion_data_file"] = out_path
    state_tmp = state_path + ".tmp"
    try:
        with open(state_tmp, "w") as _stf:
            json.dump(existing_state, _stf, indent=2)
        os.replace(state_tmp, state_path)
    except OSError as e:
        logger.warning("completion_data: state merge failed: %s", e)
    return out_path


def _check_pr_exists(branch, repo_root):
    """Check if a PR exists for a branch via gh CLI.

    Returns (has_pr: bool, pr_url: str).
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--json", "url",
             "--limit", "1"],
            capture_output=True, text=True, cwd=repo_root,
        )
        pr_output = result.stdout.strip()
        try:
            pr_data = json.loads(pr_output)
            has_pr = bool(pr_data)  # empty list = no PR
        except (json.JSONDecodeError, TypeError):
            has_pr = False
            pr_data = []
    except Exception:
        return (False, "")

    if not has_pr:
        return (False, "")

    try:
        pr_url = pr_data[0]["url"]
    except (IndexError, KeyError, TypeError):
        pr_url = ""

    return (bool(pr_url), pr_url)


def resume(queue_path, repo_root, notifier=None):
    """Resume execution after a crash with milestone-aware recovery.

    Reads checkpoints and milestones for in_progress sprints.
    If a PR exists, marks completed. Otherwise resets to pending with
    resume_context annotation in checkpoint.
    Handles holistic review in_progress checkpoint.
    Cleans up orphaned worktrees.
    Returns the updated queue.
    """
    from lib.queue import SprintQueue
    from lib.checkpoint import load_all_checkpoints, load_checkpoint_by_name

    queue = SprintQueue.load(queue_path)
    checkpoints_dir = os.path.join(os.path.dirname(queue_path), "checkpoints")
    checkpoints = load_all_checkpoints(checkpoints_dir)
    cp_map = {cp["sprint_id"]: cp for cp in checkpoints}

    recovered = 0
    reset_count = 0

    for sprint in queue.sprints:
        if sprint["status"] != "in_progress":
            continue

        sid = sprint["id"]
        cp = cp_map.get(sid, {})
        milestones = cp.get("milestones", {})

        # Check if PR exists on GitHub
        has_pr, pr_url = _check_pr_exists(sprint["branch"], repo_root)

        if has_pr:
            queue.mark_completed(sid, pr_url)
            recovered += 1
            logger.info("Sprint %s: found PR, marked completed", sid)
        else:
            # Reset to pending — annotate checkpoint for sprint prompt
            sprint["status"] = "pending"
            sprint["retries"] = 0
            reset_count += 1
            # Save resume context so sprint prompt can skip completed steps
            save_checkpoint(checkpoints_dir, sid, {
                "sprint_id": sid, "status": "resumed",
                "resumed_at": _now_iso(),
                "resume_context": {
                    "baseline_was_passing": milestones.get("baseline_passed", False),
                    "par_was_validated": milestones.get("par_validated", False),
                },
            })
            logger.info("Sprint %s: no PR found, reset to pending", sid)

        # Cleanup orphaned worktree
        wt_path = os.path.join(repo_root, ".worktrees", f"sprint-{sid}")
        if os.path.isdir(wt_path):
            cleanup_worktree(sprint, repo_root)

    # Holistic review recovery
    holistic_cp = load_checkpoint_by_name(checkpoints_dir, "holistic")
    if holistic_cp and holistic_cp.get("status") == "in_progress":
        logger.info("Holistic review was in progress — will re-run")

    if notifier:
        notifier.notify_resume_recovery(recovered, reset_count, len(queue.sprints))

    queue.save(queue_path)
    return queue

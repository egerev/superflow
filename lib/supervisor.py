"""Supervisor: worktree lifecycle, prompt building, sprint execution, and run loop."""
import json
import logging
import os
import re
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
REQUIRED_PAR_KEYS = {"claude_code_quality", "claude_product", "codex_code_review", "codex_product"}
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

    The fragment (e.g. 'sprint-1') matches a heading like '## Sprint 1'.
    Extracts from that heading until the next same-level heading or EOF.
    """
    # Normalize fragment: 'sprint-1' -> 'sprint 1'
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
            title_normalized = re.sub(r"[:\-_]", " ", title).strip()
            # Match exact heading (avoid "sprint 1" matching "sprint 12")
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


def build_prompt(sprint: dict, repo_root: str) -> str:
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

    # Extract plan section
    plan_file = sprint["plan_file"]
    if "#" in plan_file:
        file_part, fragment = plan_file.rsplit("#", 1)
    else:
        file_part = plan_file
        fragment = None

    plan_path = os.path.join(repo_root, file_part)
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
    result = result.replace("{branch}", sprint["branch"])
    result = result.replace("{complexity}", complexity)
    result = result.replace("{implementation_tier}", implementation_tier)
    result = result.replace("{impl_model}", impl_model)
    result = result.replace("{impl_effort}", impl_effort)

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


def _parse_json_summary(output: str) -> dict | None:
    """Parse JSON summary from the last lines of claude output."""
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
            if isinstance(data, dict) and "status" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


_DENIED_ENV_KEYS = {
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "DATABASE_URL", "DB_PASSWORD",
    "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "HCLOUD_TOKEN",
}


def _filtered_env():
    """Filter env vars: pass everything except known sensitive keys."""
    return {k: v for k, v in os.environ.items() if k not in _DENIED_ENV_KEYS}


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

    # JavaScript: package.json with "test" script
    package_json_path = os.path.join(wt_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path) as f:
                pkg = json.load(f)
            if "test" in pkg.get("scripts", {}):
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
        result = subprocess.run(
            cmd, shell=True, cwd=wt_path, timeout=timeout,
            capture_output=True, text=True,
        )
        output = result.stdout + "\n" + result.stderr
        return (result.returncode == 0, output, False)
    except subprocess.TimeoutExpired:
        return (False, f"Baseline tests timed out after {timeout}s", False)


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

    try:
        # 5. Baseline test gate
        baseline_passed, baseline_output, baseline_skipped = run_baseline_tests(
            wt_path, sprint, queue, timeout=300
        )
        if not baseline_passed:
            logger.warning("Baseline tests failed for sprint %s", sid)
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
        save_checkpoint(checkpoints_dir, sid, {
            "sprint_id": sid, "status": "in_progress", "started_at": _now_iso(),
            "milestones": {"baseline_passed": True, "baseline_skipped": baseline_skipped},
        })

        # 7. Execute sprint with Claude
        result = _attempt_sprint(sprint, queue, queue_path, checkpoints_dir,
                                 repo_root, wt_path, timeout, queue_lock)
        return result
    finally:
        # Always cleanup worktree
        cleanup_worktree(sprint, repo_root)
        if notifier:
            _notify_sprint_result(notifier, sprint)


def _attempt_sprint(sprint, queue, queue_path, checkpoints_dir, repo_root,
                    wt_path, timeout, queue_lock=None):
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
        prompt = build_prompt(sprint, repo_root)

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

    if notifier:
        try:
            summary_data = queue.summary()
            summary_text = ", ".join(f"{k}: {v}" for k, v in summary_data.items() if v > 0)
            notifier.notify_all_done(summary_text)
        except Exception as e:
            logger.warning("Notifier error: %s", e)

    # Generate completion report
    report = generate_completion_report(queue, checkpoints_dir)
    if report:
        print(report)


def generate_completion_report(queue, checkpoints_dir, output_path=None):
    """Generate Demo Day style completion report from queue and checkpoints.

    Reads all checkpoints and formats a markdown report with per-sprint blocks
    (title, status, PR, tests, PAR) and a summary section.

    Args:
        queue: SprintQueue instance with current sprint states.
        checkpoints_dir: Path to directory containing sprint checkpoint files.
        output_path: If provided, write the report to this file path.

    Returns:
        The report as a markdown string.
    """
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
            claude_cq = par.get("claude_code_quality", par.get("claude", "N/A"))
            claude_pr = par.get("claude_product", "N/A")
            codex_cr = par.get("codex_code_review", par.get("secondary", "N/A"))
            codex_pr = par.get("codex_product", "N/A")
            lines.append(
                f"- **PAR:** Claude-CQ={claude_cq}, Claude-Product={claude_pr}, "
                f"Codex-CR={codex_cr}, Codex-Product={codex_pr}"
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


def resume(queue_path, repo_root):
    """Resume execution after a crash.

    Finds in_progress sprints and either marks them completed (if PR exists)
    or resets them to pending.
    Returns the updated queue.
    """
    from lib.queue import SprintQueue

    queue = SprintQueue.load(queue_path)

    for sprint in queue.sprints:
        if sprint["status"] != "in_progress":
            continue

        sid = sprint["id"]
        branch = sprint["branch"]
        wt_path = os.path.join(repo_root, ".worktrees", f"sprint-{sid}")
        has_worktree = os.path.isdir(wt_path)

        # Check if a PR exists for this branch
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--head", branch, "--json", "url",
                 "--limit", "1"],
                capture_output=True, text=True, cwd=repo_root,
            )
            pr_output = result.stdout.strip()
            has_pr = bool(pr_output and pr_output != "[]")
        except Exception:
            has_pr = False

        if has_pr:
            # PR exists — sprint was completed (worktree may already be cleaned up)
            try:
                pr_data = json.loads(pr_output)
                pr_url = pr_data[0]["url"] if pr_data else ""
            except (json.JSONDecodeError, IndexError, KeyError):
                pr_url = pr_output.split("\t")[0] if pr_output else ""
            queue.mark_completed(sid, pr_url)
            logger.info("Sprint %d: found PR, marked completed", sid)
            # Clean up orphaned worktree if still exists
            if has_worktree:
                cleanup_worktree(sprint, repo_root)
        else:
            sprint["status"] = "pending"
            sprint["retries"] = 0
            logger.info("Sprint %d: no PR found, reset to pending", sid)
            # Clean up orphaned worktree if still exists
            if has_worktree:
                cleanup_worktree(sprint, repo_root)

    queue.save(queue_path)
    return queue

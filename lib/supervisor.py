"""Supervisor: worktree lifecycle, prompt building, sprint execution, and run loop."""
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone

from lib.checkpoint import save_checkpoint

logger = logging.getLogger(__name__)


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
            if normalized in title_normalized or title_normalized in normalized:
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

    # Fill placeholders
    result = template.format(
        sprint_id=sprint["id"],
        sprint_title=sprint["title"],
        sprint_plan=sprint_plan,
        claude_md=claude_md,
        llms_txt=llms_txt,
        branch=sprint["branch"],
    )
    return result


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_json_summary(output: str) -> dict | None:
    """Parse JSON summary from the last non-empty line of output."""
    lines = output.strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return None
    return None


_FILTERED_ENV_KEYS = {
    "ANTHROPIC_API_KEY", "PATH", "HOME", "LANG",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
}


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

    # 2. Save initial checkpoint
    save_checkpoint(checkpoints_dir, sid, {
        "sprint_id": sid, "status": "in_progress", "started_at": _now_iso(),
    })

    # 3. Create worktree
    wt_path = create_worktree(sprint, repo_root)

    try:
        result = _attempt_sprint(sprint, queue, queue_path, checkpoints_dir,
                                 repo_root, wt_path, timeout)
        return result
    finally:
        # 13. Always cleanup worktree
        cleanup_worktree(sprint, repo_root)
        if notifier:
            _notify_sprint_result(notifier, sprint)


def _attempt_sprint(sprint, queue, queue_path, checkpoints_dir, repo_root,
                    wt_path, timeout):
    """Run claude for a sprint, with retry logic."""
    sid = sprint["id"]
    prompt = build_prompt(sprint, repo_root)

    while True:
        # Filter environment
        env = {k: v for k, v in os.environ.items() if k in _FILTERED_ENV_KEYS}

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

        # Save output log
        os.makedirs(checkpoints_dir, exist_ok=True)
        log_path = os.path.join(checkpoints_dir, f"sprint-{sid}-output.log")
        with open(log_path, "w") as f:
            f.write(result.stdout or "")

        # Parse JSON from last line
        summary = _parse_json_summary(result.stdout or "")
        json_parse_error = (result.returncode == 0 and summary is None)
        success = (result.returncode == 0 and summary is not None)

        if success:
            # Verify PR
            pr_url = summary.get("pr_url", "")
            if pr_url:
                pr_check = subprocess.run(
                    ["gh", "pr", "view", pr_url],
                    capture_output=True, text=True, cwd=repo_root,
                )
                if pr_check.returncode != 0:
                    logger.warning("PR verification failed for %s", pr_url)

            # Mark completed
            queue.mark_completed(sid, pr_url)
            queue.save(queue_path)
            cp = {
                "sprint_id": sid, "status": "completed",
                "completed_at": _now_iso(), "pr_url": pr_url,
                "summary": summary,
            }
            save_checkpoint(checkpoints_dir, sid, cp)
            return cp

        # Failure path — check retries
        sprint["retries"] = sprint.get("retries", 0) + 1
        if sprint["retries"] >= sprint.get("max_retries", 2):
            # Max retries reached — mark failed
            error_msg = result.stderr or result.stdout or "Unknown error"
            queue.mark_failed(sid, error_msg[:500])
            queue.save(queue_path)
            cp = {
                "sprint_id": sid, "status": "failed",
                "failed_at": _now_iso(), "error": error_msg[:500],
                "retries": sprint["retries"],
            }
            save_checkpoint(checkpoints_dir, sid, cp)
            return cp

        # Retry — if JSON parse error, append instruction to prompt
        if json_parse_error:
            prompt += (
                "\n\nIMPORTANT: Your previous output did not include the required "
                "JSON summary as the LAST line. You MUST output a JSON summary as "
                "the very last line of your response."
            )
        logger.info("Retrying sprint %d (attempt %d)", sid, sprint["retries"] + 1)


def _notify_sprint_result(notifier, sprint):
    """Call the notifier with the sprint result."""
    try:
        if sprint["status"] == "completed":
            notifier.notify_completed(sprint)
        elif sprint["status"] == "failed":
            notifier.notify_failed(sprint)
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


def run(queue_path, plan_path=None, max_parallel=1, timeout=1800,
        no_replan=False, notifier=None, repo_root=None):
    """Main supervisor run loop.

    Loads the queue, runs preflight, then executes sprints sequentially.
    """
    from lib.queue import SprintQueue

    queue = SprintQueue.load(queue_path)

    if repo_root is None:
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
        runnable = queue.next_runnable(max_parallel=1)  # Sequential for now
        if not runnable:
            queue.skip_blocked_sprints()
            queue.save(queue_path)
            break

        for sprint in runnable:
            execute_sprint(
                sprint, queue, queue_path, checkpoints_dir, repo_root,
                timeout=timeout, notifier=notifier,
            )
            queue.save(queue_path)

    print_summary(queue)

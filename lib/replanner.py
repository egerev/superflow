"""Adaptive replanner: analyzes completed sprints and adjusts remaining plans."""
import json
import logging
import os
import subprocess

from lib.checkpoint import load_all_checkpoints
from lib.supervisor import _filtered_env

logger = logging.getLogger(__name__)

VALID_CHANGE_TYPES = {"reorder", "modify", "add", "skip"}


def replan(queue, queue_path, plan_path, repo_root, checkpoints_dir):
    """Run adaptive replanning after sprint completion.

    1. Collect completed sprint summaries from checkpoints
    2. Collect remaining sprint plans
    3. Read templates/replan-prompt.md, fill placeholders
    4. Launch: subprocess claude -p --verbose with replan prompt
    5. Parse JSON from last line: {"changes": [...]}
    6. Validate each change (type must be reorder/modify/add/skip)
    7. Apply valid changes to queue
    8. Handle invalid JSON: log warning, skip (don't crash)
    9. Save queue
    Return list of changes applied.
    """
    # 1. Collect completed sprint summaries
    checkpoints = load_all_checkpoints(checkpoints_dir)
    completed_summaries = [
        cp for cp in checkpoints if cp.get("status") == "completed"
    ]

    # 2. Collect remaining sprints
    remaining = [s for s in queue.sprints if s["status"] == "pending"]

    if not remaining:
        return []

    # 3. Read template and fill
    template_path = os.path.join(repo_root, "templates", "replan-prompt.md")
    if not os.path.exists(template_path):
        logger.warning("Replan template not found: %s", template_path)
        return []

    with open(template_path) as f:
        template = f.read()

    # Read original plan
    plan_content = ""
    if plan_path and os.path.exists(plan_path):
        with open(plan_path) as f:
            plan_content = f.read()

    # Use string replacement instead of str.format() because the template
    # contains literal JSON braces that conflict with Python format strings
    prompt = template
    prompt = prompt.replace("{completed_sprints}", json.dumps(completed_summaries, indent=2))
    prompt = prompt.replace("{remaining_sprints}", json.dumps(
        [{"id": s["id"], "title": s["title"], "depends_on": s["depends_on"]}
         for s in remaining],
        indent=2,
    ))
    prompt = prompt.replace("{plan_content}", plan_content)

    # 4. Launch claude subprocess
    try:
        result = subprocess.run(
            ["claude", "-p", "--verbose"],
            input=prompt, capture_output=True, text=True,
            timeout=300, cwd=repo_root, env=_filtered_env(),
        )
    except subprocess.TimeoutExpired:
        logger.warning("Replan subprocess timed out")
        return []
    except FileNotFoundError:
        logger.warning("claude CLI not found for replanning")
        return []

    # 5. Parse JSON from last line
    output = result.stdout or ""
    changes_data = _parse_changes(output)
    if changes_data is None:
        logger.warning("Replan: no valid JSON in output, skipping")
        return []

    # 6. Validate and apply changes
    applied = []
    for change in changes_data:
        if not _validate_change(change):
            logger.warning("Replan: invalid change skipped: %s", change)
            continue
        if _apply_change(queue, change):
            applied.append(change)

    # 9. Save queue
    if applied:
        queue.save(queue_path)

    return applied


def _parse_changes(output):
    """Parse changes list from the last non-empty line of output.

    Returns list of changes or None if parsing fails.
    """
    lines = output.strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and "changes" in data:
                changes = data["changes"]
                if isinstance(changes, list):
                    return changes
            return None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _validate_change(change):
    """Validate a single change object."""
    if not isinstance(change, dict):
        return False
    change_type = change.get("type")
    if change_type not in VALID_CHANGE_TYPES:
        return False
    # skip and modify need sprint_id
    if change_type in ("skip", "modify", "reorder") and "sprint_id" not in change:
        return False
    return True


def _apply_change(queue, change):
    """Apply a single validated change to the queue. Returns True if applied."""
    change_type = change["type"]

    # For skip and modify, only apply to pending sprints
    if change_type in ("skip", "modify"):
        sid = change["sprint_id"]
        try:
            sprint = queue._find_sprint(sid)
            if sprint["status"] != "pending":
                logger.warning("Skipping %s on sprint %d: status is %s, not pending",
                               change_type, sid, sprint["status"])
                return False
        except KeyError:
            pass  # Will be caught in the specific handler below

    if change_type == "skip":
        sid = change["sprint_id"]
        reason = change.get("reason", "replanner decision")
        try:
            queue.mark_skipped(sid, reason)
            logger.info("Replan: skipped sprint %d: %s", sid, reason)
            return True
        except KeyError:
            logger.warning("Replan: sprint %d not found for skip", sid)
            return False

    if change_type == "modify":
        sid = change["sprint_id"]
        try:
            sprint = queue._find_sprint(sid)
            if "new_plan" in change:
                sprint["plan_file"] = change.get("new_plan", sprint["plan_file"])
            if "title" in change:
                sprint["title"] = change["title"]
            logger.info("Replan: modified sprint %d", sid)
            return True
        except KeyError:
            logger.warning("Replan: sprint %d not found for modify", sid)
            return False

    if change_type == "reorder":
        # Reorder changes dependencies — simplified: just log it
        sid = change["sprint_id"]
        try:
            sprint = queue._find_sprint(sid)
            if "depends_on" in change:
                sprint["depends_on"] = change["depends_on"]
            logger.info("Replan: reordered sprint %d", sid)
            return True
        except KeyError:
            logger.warning("Replan: sprint %d not found for reorder", sid)
            return False

    if change_type == "add":
        # Add a new sprint — needs at minimum id, title, branch
        new_sprint = {
            "id": change.get("sprint_id", max(s["id"] for s in queue.sprints) + 1),
            "title": change.get("title", "Added by replanner"),
            "status": "pending",
            "plan_file": change.get("plan_file", ""),
            "branch": change.get("branch", f"feat/replan-sprint-{change.get('sprint_id', 'new')}"),
            "depends_on": change.get("depends_on", []),
            "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
        }
        queue.sprints.append(new_sprint)
        logger.info("Replan: added sprint %d: %s", new_sprint["id"], new_sprint["title"])
        return True

    return False

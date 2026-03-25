"""Launcher module — launch, monitor, and stop the supervisor as a background process."""
import json
import os
import signal
import subprocess
import sys
import time
from collections import namedtuple
from dataclasses import dataclass


LaunchResult = namedtuple("LaunchResult", ["pid", "log_path", "queue_path", "sprint_count"])


# Tier 1: launcher → supervisor deny-list. Only truly dangerous keys the supervisor never needs.
_LAUNCH_DENY_LIST = {
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "DATABASE_URL", "DB_PASSWORD",
    "STRIPE_SECRET_KEY", "STRIPE_API_KEY",
    "DOCKER_PASSWORD",
    "HEROKU_API_KEY",
}


def _launch_env():
    """Build environment for supervisor process. Tier 1: pass almost everything."""
    return {k: v for k, v in os.environ.items() if k not in _LAUNCH_DENY_LIST}


def _superflow_dir(repo_root):
    """Return path to .superflow/ infrastructure directory."""
    return os.path.join(repo_root, ".superflow")


def read_pid(pid_path):
    """Read PID from file, verify alive. Return PID if alive, None otherwise."""
    if not os.path.exists(pid_path):
        return None
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if alive
        return pid
    except (ValueError, OSError, ProcessLookupError):
        # Dead or invalid — clean stale PID file
        try:
            os.unlink(pid_path)
        except OSError:
            pass
        return None


def launch(queue_path, plan_path, repo_root, timeout=1800):
    """Launch supervisor as a detached background process.

    Returns LaunchResult on success. Raises RuntimeError on failure.
    """
    from lib.planner import validate_queue_freshness
    from lib.queue import SprintQueue

    sf_dir = _superflow_dir(repo_root)
    pid_path = os.path.join(sf_dir, "supervisor.pid")
    log_path = os.path.join(sf_dir, "supervisor.log")
    launch_json = os.path.join(sf_dir, "launch.json")

    # Check for already-running supervisor
    existing_pid = read_pid(pid_path)
    if existing_pid is not None:
        queue = SprintQueue.load(queue_path)
        return LaunchResult(
            pid=existing_pid,
            log_path=log_path,
            queue_path=queue_path,
            sprint_count=len(queue.sprints),
        )

    # Validate queue freshness (skip if no plan_path)
    if plan_path:
        fresh, reason = validate_queue_freshness(queue_path, plan_path)
        if not fresh:
            raise RuntimeError(f"Queue is stale: {reason}. Regenerate with plan_to_queue().")

    # Load queue to count sprints
    queue = SprintQueue.load(queue_path)

    # Create infrastructure directory
    os.makedirs(sf_dir, exist_ok=True)

    # Open log file (append mode)
    log_file = open(log_path, "a")

    # Build command
    cmd = [
        sys.executable,
        os.path.join(repo_root, "bin", "superflow-supervisor"),
        "run",
        "--queue", queue_path,
        "--timeout", str(timeout),
    ]
    if plan_path:
        cmd.extend(["--plan", plan_path])

    # Launch
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=repo_root,
        env=_launch_env(),
    )
    log_file.close()

    # Write PID file atomically with 0o600 permissions
    tmp_pid = pid_path + ".tmp"
    fd = os.open(tmp_pid, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(str(proc.pid))
    os.replace(tmp_pid, pid_path)

    # Write launch.json
    launch_data = {
        "queue_path": queue_path,
        "plan_path": plan_path,
        "timeout": timeout,
        "log_path": log_path,
        "pid": proc.pid,
        "launched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    tmp_launch = launch_json + ".tmp"
    with open(tmp_launch, "w") as f:
        json.dump(launch_data, f, indent=2)
    os.replace(tmp_launch, launch_json)

    # Verify alive after 2 seconds
    time.sleep(2)
    try:
        os.kill(proc.pid, 0)
    except (OSError, ProcessLookupError):
        # Dead — read first 20 lines of log
        lines = []
        try:
            with open(log_path) as f:
                lines = f.readlines()[-20:]
        except OSError:
            pass
        error_context = "".join(lines)
        # Clean PID file
        try:
            os.unlink(pid_path)
        except OSError:
            pass
        raise RuntimeError(f"Supervisor died within 2s. Log:\n{error_context}")

    return LaunchResult(
        pid=proc.pid,
        log_path=log_path,
        queue_path=queue_path,
        sprint_count=len(queue.sprints),
    )

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

    # Resolve paths to absolute before spawning (child runs with cwd=repo_root)
    abs_queue = os.path.abspath(queue_path)
    abs_plan = os.path.abspath(plan_path) if plan_path else None

    # Build command
    cmd = [
        sys.executable,
        os.path.join(repo_root, "bin", "superflow-supervisor"),
        "run",
        "--queue", abs_queue,
        "--timeout", str(timeout),
    ]
    if abs_plan:
        cmd.extend(["--plan", abs_plan])

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

    # Write launch.json (absolute paths for cross-directory access)
    launch_data = {
        "queue_path": abs_queue,
        "plan_path": abs_plan,
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


@dataclass
class SupervisorStatus:
    alive: bool
    pid: int | None = None
    phase: int | None = None
    sprint: int | None = None
    stage: str | None = None
    tasks_done: list = None
    tasks_total: int | None = None
    heartbeat_age_seconds: float | None = None
    crashed: bool = False
    log_path: str | None = None

    def __post_init__(self):
        if self.tasks_done is None:
            self.tasks_done = []


def stop(repo_root, wait_timeout=60):
    """Stop supervisor by sending SIGTERM to process group, then SIGKILL if needed."""
    sf_dir = _superflow_dir(repo_root)
    pid_path = os.path.join(sf_dir, "supervisor.pid")

    pid = read_pid(pid_path)
    if pid is None:
        return True  # Already stopped

    # Send SIGTERM to process group
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        # Already dead
        try:
            os.unlink(pid_path)
        except OSError:
            pass
        return True

    # Wait for process to die
    for _ in range(wait_timeout):
        try:
            os.kill(pid, 0)
            time.sleep(1)
        except (OSError, ProcessLookupError):
            break
    else:
        # Still alive — escalate to SIGKILL
        try:
            os.killpg(pid, signal.SIGKILL)
            time.sleep(1)
        except (ProcessLookupError, PermissionError):
            pass

    # Clean PID file
    try:
        os.unlink(pid_path)
    except OSError:
        pass

    return True


def get_status(repo_root):
    """Get supervisor status from PID file, state file, and heartbeat."""
    sf_dir = _superflow_dir(repo_root)
    pid_path = os.path.join(sf_dir, "supervisor.pid")
    heartbeat_path = os.path.join(sf_dir, "heartbeat")
    state_path = os.path.join(repo_root, ".superflow-state.json")
    log_path = os.path.join(sf_dir, "supervisor.log")

    pid = read_pid(pid_path)
    alive = pid is not None

    # Read heartbeat
    heartbeat_age = None
    if os.path.exists(heartbeat_path):
        try:
            with open(heartbeat_path) as f:
                ts = float(f.read().strip())
            heartbeat_age = time.time() - ts
        except (ValueError, OSError):
            pass

    # Read state
    phase = sprint = stage = None
    tasks_done = []
    tasks_total = None
    if os.path.exists(state_path):
        try:
            with open(state_path) as f:
                state = json.load(f)
            phase = state.get("phase")
            sprint = state.get("sprint")
            stage = state.get("stage")
        except (json.JSONDecodeError, OSError):
            pass

    # Read queue for task counts
    launch_json = os.path.join(sf_dir, "launch.json")
    if os.path.exists(launch_json):
        try:
            with open(launch_json) as f:
                ldata = json.load(f)
            qpath = ldata.get("queue_path")
            if qpath and os.path.exists(qpath):
                from lib.queue import SprintQueue
                queue = SprintQueue.load(qpath)
                tasks_done = [s["id"] for s in queue.sprints if s["status"] == "completed"]
                tasks_total = len(queue.sprints)
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    # Crash detection: dead but state shows mid-execution
    crashed = not alive and stage is not None and stage not in ("ship", "done")

    return SupervisorStatus(
        alive=alive,
        pid=pid,
        phase=phase,
        sprint=sprint,
        stage=stage,
        tasks_done=tasks_done,
        tasks_total=tasks_total,
        heartbeat_age_seconds=heartbeat_age,
        crashed=crashed,
        log_path=log_path if os.path.exists(log_path) else None,
    )


def restart(repo_root, queue_path=None, plan_path=None, timeout=1800):
    """Stop supervisor, resume crashed sprints, then relaunch."""
    stop(repo_root)

    # Read paths from launch.json if not provided
    if queue_path is None or plan_path is None:
        launch_json = os.path.join(_superflow_dir(repo_root), "launch.json")
        if os.path.exists(launch_json):
            with open(launch_json) as f:
                ldata = json.load(f)
            queue_path = queue_path or ldata.get("queue_path")
            plan_path = plan_path or ldata.get("plan_path")
            timeout = ldata.get("timeout", timeout)

    if not queue_path:
        raise RuntimeError("No queue_path provided and launch.json not found")

    # Resume crashed sprints (reset in_progress → pending)
    from lib.supervisor import resume
    resume(queue_path, repo_root)

    return launch(queue_path, plan_path, repo_root, timeout=timeout)


def write_hold_request(repo_root):
    """Write a hold request for the supervisor to pause between sprints."""
    import datetime
    sf_dir = _superflow_dir(repo_root)
    os.makedirs(sf_dir, exist_ok=True)
    hold_path = os.path.join(sf_dir, "hold-request.json")
    data = {
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "dashboard",
    }
    tmp = hold_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, hold_path)


def clear_hold_request(repo_root):
    """Remove the hold request file to resume supervisor execution."""
    sf_dir = _superflow_dir(repo_root)
    hold_path = os.path.join(sf_dir, "hold-request.json")
    try:
        os.unlink(hold_path)
    except FileNotFoundError:
        pass


def write_skip_request(repo_root, sprint_id, reason="user requested"):
    """Write a skip request for the supervisor to pick up."""
    sf_dir = _superflow_dir(repo_root)
    skip_dir = os.path.join(sf_dir, "skip-requests")
    os.makedirs(skip_dir, exist_ok=True)

    filename = f"skip-{sprint_id}-{int(time.time())}.json"
    filepath = os.path.join(skip_dir, filename)

    data = {"sprint_id": sprint_id, "reason": reason}
    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, filepath)

"""Tests for launcher module — launch, stop, status, restart, skip requests."""
import json
import os
import shutil
import signal
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.launcher import (
    read_pid, launch, stop, get_status, restart, write_skip_request,
    write_hold_request, clear_hold_request,
    LaunchResult, SupervisorStatus, _superflow_dir,
)


def _make_queue_file(tmpdir, sprints=None):
    """Create a minimal queue.json and return its path."""
    if sprints is None:
        sprints = [
            {"id": 1, "title": "Sprint 1", "status": "pending",
             "plan_file": "plans/plan.md#sprint-1", "branch": "feat/test-sprint-1",
             "depends_on": [], "pr": None, "retries": 0, "max_retries": 2, "error_log": None},
        ]
    queue_data = {
        "feature": "test",
        "created": "2026-01-01T00:00:00Z",
        "sprints": sprints,
    }
    path = os.path.join(tmpdir, "queue.json")
    with open(path, "w") as f:
        json.dump(queue_data, f)
    return path


class TestReadPid(unittest.TestCase):
    """Tests for read_pid() — PID file reading and liveness check."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pid_path = os.path.join(self.tmpdir, "supervisor.pid")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("os.kill")
    def test_valid_pid_alive_returns_pid(self, mock_kill):
        """Valid PID file with alive process returns the PID."""
        mock_kill.return_value = None  # os.kill(pid, 0) succeeds
        with open(self.pid_path, "w") as f:
            f.write("12345")
        result = read_pid(self.pid_path)
        self.assertEqual(result, 12345)
        mock_kill.assert_called_once_with(12345, 0)

    @patch("os.kill", side_effect=ProcessLookupError)
    def test_valid_pid_dead_returns_none_and_cleans(self, mock_kill):
        """Valid PID file with dead process returns None and removes file."""
        with open(self.pid_path, "w") as f:
            f.write("99999")
        result = read_pid(self.pid_path)
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.pid_path))

    def test_missing_pid_file_returns_none(self):
        """Missing PID file returns None."""
        result = read_pid(self.pid_path)
        self.assertIsNone(result)

    @patch("os.kill")
    def test_invalid_content_returns_none(self, mock_kill):
        """PID file with invalid content returns None."""
        with open(self.pid_path, "w") as f:
            f.write("not-a-number")
        result = read_pid(self.pid_path)
        self.assertIsNone(result)
        mock_kill.assert_not_called()


class TestLaunch(unittest.TestCase):
    """Tests for launch() — supervisor background launch."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.sf_dir = os.path.join(self.repo_root, ".superflow")
        os.makedirs(self.sf_dir, exist_ok=True)
        self.queue_path = _make_queue_file(self.tmpdir)
        # Create bin directory structure for the command
        bin_dir = os.path.join(self.repo_root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        with open(os.path.join(bin_dir, "superflow-supervisor"), "w") as f:
            f.write("#!/usr/bin/env python3\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("time.sleep")
    @patch("os.kill")
    @patch("subprocess.Popen")
    def test_successful_launch_returns_result(self, mock_popen, mock_kill, mock_sleep):
        """Successful launch with mocked Popen returns LaunchResult."""
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_popen.return_value = mock_proc
        mock_kill.return_value = None  # Process is alive after 2s

        result = launch(
            queue_path=self.queue_path,
            plan_path=None,
            repo_root=self.repo_root,
            timeout=1800,
        )

        self.assertIsInstance(result, LaunchResult)
        self.assertEqual(result.pid, 42)
        self.assertEqual(result.queue_path, self.queue_path)
        self.assertEqual(result.sprint_count, 1)
        self.assertTrue(result.log_path.endswith("supervisor.log"))

    @patch("time.sleep")
    @patch("os.kill")
    @patch("subprocess.Popen")
    def test_already_running_returns_existing(self, mock_popen, mock_kill, mock_sleep):
        """Already-running supervisor returns existing LaunchResult without spawning."""
        # Write a PID file for an "existing" process
        pid_path = os.path.join(self.sf_dir, "supervisor.pid")
        with open(pid_path, "w") as f:
            f.write("99")
        mock_kill.return_value = None  # PID 99 is alive

        result = launch(
            queue_path=self.queue_path,
            plan_path=None,
            repo_root=self.repo_root,
        )

        self.assertEqual(result.pid, 99)
        mock_popen.assert_not_called()

    @patch("time.sleep")
    @patch("os.kill")
    @patch("subprocess.Popen")
    def test_stale_queue_raises(self, mock_popen, mock_kill, mock_sleep):
        """Stale queue raises RuntimeError."""
        # Create a plan file
        plan_path = os.path.join(self.tmpdir, "plan.md")
        with open(plan_path, "w") as f:
            f.write("## Sprint 1: Test\n")

        # Queue was generated from a different plan content
        queue_data = {
            "feature": "test",
            "created": "2026-01-01T00:00:00Z",
            "generated_from": {
                "plan_file": plan_path,
                "content_hash": "sha256:0000000000000000",
                "generated_at": "2026-01-01T00:00:00Z",
            },
            "sprints": [
                {"id": 1, "title": "Sprint 1", "status": "pending",
                 "plan_file": "plans/plan.md#sprint-1", "branch": "feat/test-sprint-1",
                 "depends_on": [], "pr": None, "retries": 0, "max_retries": 2, "error_log": None},
            ],
        }
        with open(self.queue_path, "w") as f:
            json.dump(queue_data, f)

        with self.assertRaises(RuntimeError) as ctx:
            launch(
                queue_path=self.queue_path,
                plan_path=plan_path,
                repo_root=self.repo_root,
            )
        self.assertIn("stale", str(ctx.exception).lower())

    @patch("time.sleep")
    @patch("os.kill", side_effect=ProcessLookupError)
    @patch("subprocess.Popen")
    def test_dead_within_2s_raises_with_log(self, mock_popen, mock_kill, mock_sleep):
        """Supervisor dying within 2s raises RuntimeError with log context."""
        mock_proc = MagicMock()
        mock_proc.pid = 555
        mock_popen.return_value = mock_proc

        # Write some log content that would exist
        log_path = os.path.join(self.sf_dir, "supervisor.log")
        with open(log_path, "w") as f:
            f.write("Error: something went wrong\n")

        with self.assertRaises(RuntimeError) as ctx:
            launch(
                queue_path=self.queue_path,
                plan_path=None,
                repo_root=self.repo_root,
            )
        self.assertIn("died within 2s", str(ctx.exception))

    @patch("time.sleep")
    @patch("os.kill")
    @patch("subprocess.Popen")
    def test_pid_file_has_restricted_permissions(self, mock_popen, mock_kill, mock_sleep):
        """PID file should have 0o600 permissions."""
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_popen.return_value = mock_proc
        mock_kill.return_value = None

        launch(
            queue_path=self.queue_path,
            plan_path=None,
            repo_root=self.repo_root,
        )

        pid_path = os.path.join(self.sf_dir, "supervisor.pid")
        mode = os.stat(pid_path).st_mode & 0o777
        self.assertEqual(mode, 0o600)


class TestStop(unittest.TestCase):
    """Tests for stop() — stopping supervisor process."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.sf_dir = os.path.join(self.repo_root, ".superflow")
        os.makedirs(self.sf_dir, exist_ok=True)
        self.pid_path = os.path.join(self.sf_dir, "supervisor.pid")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("time.sleep")
    @patch("os.kill")
    @patch("os.killpg")
    def test_stop_running_supervisor(self, mock_killpg, mock_kill, mock_sleep):
        """Stop sends SIGTERM to process group and cleans PID file."""
        with open(self.pid_path, "w") as f:
            f.write("100")
        # First os.kill call is read_pid liveness check (succeeds),
        # second is the wait loop check (fails = process died)
        mock_kill.side_effect = [None, ProcessLookupError]
        mock_killpg.return_value = None

        result = stop(self.repo_root, wait_timeout=5)

        self.assertTrue(result)
        mock_killpg.assert_called_once_with(100, signal.SIGTERM)
        self.assertFalse(os.path.exists(self.pid_path))

    def test_already_stopped_returns_true(self):
        """Stop when no PID file exists returns True."""
        result = stop(self.repo_root)
        self.assertTrue(result)

    @patch("time.sleep")
    @patch("os.kill")
    @patch("os.killpg")
    def test_sigterm_timeout_escalates_to_sigkill(self, mock_killpg, mock_kill, mock_sleep):
        """If SIGTERM doesn't kill within timeout, SIGKILL is sent."""
        with open(self.pid_path, "w") as f:
            f.write("200")
        # read_pid liveness check succeeds, then wait loop checks always succeed (process alive)
        mock_kill.return_value = None  # Process stays alive
        mock_killpg.return_value = None

        result = stop(self.repo_root, wait_timeout=3)

        self.assertTrue(result)
        # Should have called killpg twice: SIGTERM then SIGKILL
        killpg_calls = mock_killpg.call_args_list
        self.assertEqual(killpg_calls[0], call(200, signal.SIGTERM))
        self.assertEqual(killpg_calls[1], call(200, signal.SIGKILL))

    @patch("time.sleep")
    @patch("os.kill")
    @patch("os.killpg", side_effect=ProcessLookupError)
    def test_cleans_pid_file_after_stop(self, mock_killpg, mock_kill, mock_sleep):
        """PID file is cleaned after stop even if process already died."""
        with open(self.pid_path, "w") as f:
            f.write("300")
        mock_kill.return_value = None  # read_pid succeeds

        result = stop(self.repo_root)

        self.assertTrue(result)
        self.assertFalse(os.path.exists(self.pid_path))


class TestGetStatus(unittest.TestCase):
    """Tests for get_status() — supervisor status detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.sf_dir = os.path.join(self.repo_root, ".superflow")
        os.makedirs(self.sf_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("os.kill")
    def test_alive_supervisor_returns_correct_status(self, mock_kill):
        """Alive supervisor returns alive=True with PID."""
        pid_path = os.path.join(self.sf_dir, "supervisor.pid")
        with open(pid_path, "w") as f:
            f.write("500")
        mock_kill.return_value = None

        status = get_status(self.repo_root)

        self.assertTrue(status.alive)
        self.assertEqual(status.pid, 500)
        self.assertFalse(status.crashed)

    def test_dead_supervisor_mid_execution_shows_crashed(self):
        """Dead supervisor with mid-execution state shows crashed=True."""
        # No PID file (dead), but state shows mid-execution
        state_path = os.path.join(self.repo_root, ".superflow-state.json")
        with open(state_path, "w") as f:
            json.dump({"phase": 2, "sprint": 3, "stage": "implement"}, f)

        status = get_status(self.repo_root)

        self.assertFalse(status.alive)
        self.assertTrue(status.crashed)
        self.assertEqual(status.sprint, 3)
        self.assertEqual(status.stage, "implement")

    def test_no_supervisor_running(self):
        """No supervisor running returns alive=False, crashed=False."""
        status = get_status(self.repo_root)

        self.assertFalse(status.alive)
        self.assertFalse(status.crashed)
        self.assertIsNone(status.pid)

    @patch("os.kill")
    def test_heartbeat_age_calculation(self, mock_kill):
        """Heartbeat age is calculated correctly."""
        pid_path = os.path.join(self.sf_dir, "supervisor.pid")
        with open(pid_path, "w") as f:
            f.write("600")
        mock_kill.return_value = None

        heartbeat_path = os.path.join(self.sf_dir, "heartbeat")
        with open(heartbeat_path, "w") as f:
            f.write(str(time.time() - 10))  # 10 seconds ago

        status = get_status(self.repo_root)

        self.assertIsNotNone(status.heartbeat_age_seconds)
        # Should be approximately 10 seconds (with tolerance for test execution)
        self.assertGreater(status.heartbeat_age_seconds, 8)
        self.assertLess(status.heartbeat_age_seconds, 15)


class TestRestart(unittest.TestCase):
    """Tests for restart() — stop + launch."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.sf_dir = os.path.join(self.repo_root, ".superflow")
        os.makedirs(self.sf_dir, exist_ok=True)
        self.queue_path = _make_queue_file(self.tmpdir)
        bin_dir = os.path.join(self.repo_root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        with open(os.path.join(bin_dir, "superflow-supervisor"), "w") as f:
            f.write("#!/usr/bin/env python3\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("lib.launcher.launch")
    @patch("lib.launcher.stop")
    def test_restart_calls_stop_then_launch(self, mock_stop, mock_launch):
        """restart calls stop then launch."""
        mock_launch.return_value = LaunchResult(
            pid=42, log_path="/tmp/log", queue_path=self.queue_path, sprint_count=1,
        )

        result = restart(self.repo_root, queue_path=self.queue_path)

        mock_stop.assert_called_once_with(self.repo_root)
        mock_launch.assert_called_once()
        self.assertEqual(result.pid, 42)

    @patch("lib.launcher.launch")
    @patch("lib.launcher.stop")
    def test_restart_reads_paths_from_launch_json(self, mock_stop, mock_launch):
        """restart reads paths from launch.json when not provided."""
        launch_json = os.path.join(self.sf_dir, "launch.json")
        with open(launch_json, "w") as f:
            json.dump({
                "queue_path": self.queue_path,
                "plan_path": "/tmp/plan.md",
                "timeout": 900,
            }, f)

        mock_launch.return_value = LaunchResult(
            pid=55, log_path="/tmp/log", queue_path=self.queue_path, sprint_count=1,
        )

        result = restart(self.repo_root)

        mock_launch.assert_called_once_with(
            self.queue_path, "/tmp/plan.md", self.repo_root, timeout=900,
        )


class TestWriteSkipRequest(unittest.TestCase):
    """Tests for write_skip_request() — skip request file creation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_file_in_correct_directory(self):
        """Skip request file is created in .superflow/skip-requests/."""
        write_skip_request(self.repo_root, sprint_id=3, reason="test skip")

        skip_dir = os.path.join(self.repo_root, ".superflow", "skip-requests")
        self.assertTrue(os.path.isdir(skip_dir))
        files = os.listdir(skip_dir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].startswith("skip-3-"))
        self.assertTrue(files[0].endswith(".json"))

    def test_file_contains_valid_json_with_sprint_id(self):
        """Skip request file contains valid JSON with sprint_id."""
        write_skip_request(self.repo_root, sprint_id=5, reason="user abort")

        skip_dir = os.path.join(self.repo_root, ".superflow", "skip-requests")
        files = os.listdir(skip_dir)
        filepath = os.path.join(skip_dir, files[0])
        with open(filepath) as f:
            data = json.load(f)
        self.assertEqual(data["sprint_id"], 5)
        self.assertEqual(data["reason"], "user abort")


class TestWriteHoldRequest(unittest.TestCase):
    """Tests for write_hold_request() — hold request file creation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_hold_request_file(self):
        """write_hold_request creates .superflow/hold-request.json."""
        write_hold_request(self.repo_root)

        hold_path = os.path.join(self.repo_root, ".superflow", "hold-request.json")
        self.assertTrue(os.path.exists(hold_path))

    def test_file_contains_valid_json_with_requested_at_and_source(self):
        """hold-request.json contains requested_at and source fields."""
        write_hold_request(self.repo_root)

        hold_path = os.path.join(self.repo_root, ".superflow", "hold-request.json")
        with open(hold_path) as f:
            data = json.load(f)
        self.assertIn("requested_at", data)
        self.assertEqual(data["source"], "dashboard")

    def test_requested_at_is_iso8601(self):
        """requested_at value is a parseable ISO-8601 timestamp."""
        import datetime
        write_hold_request(self.repo_root)

        hold_path = os.path.join(self.repo_root, ".superflow", "hold-request.json")
        with open(hold_path) as f:
            data = json.load(f)
        # Should not raise
        datetime.datetime.fromisoformat(data["requested_at"].replace("Z", "+00:00"))


class TestClearHoldRequest(unittest.TestCase):
    """Tests for clear_hold_request() — hold request file removal."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.sf_dir = os.path.join(self.repo_root, ".superflow")
        os.makedirs(self.sf_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_removes_existing_hold_request_file(self):
        """clear_hold_request removes an existing hold-request.json."""
        hold_path = os.path.join(self.sf_dir, "hold-request.json")
        with open(hold_path, "w") as f:
            json.dump({"requested_at": "2026-01-01T00:00:00Z", "source": "dashboard"}, f)

        clear_hold_request(self.repo_root)

        self.assertFalse(os.path.exists(hold_path))

    def test_no_error_when_file_absent(self):
        """clear_hold_request does not raise when file does not exist."""
        # Should not raise
        clear_hold_request(self.repo_root)


if __name__ == "__main__":
    unittest.main()

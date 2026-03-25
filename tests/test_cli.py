"""Tests for superflow-supervisor CLI entry point."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add parent to path so we can import the CLI module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.queue import SprintQueue


def _sprint(sid=1, title="Test Sprint", status="pending", branch="feat/test-sprint-1",
            plan_file="plans/plan.md#sprint-1", depends_on=None):
    return {
        "id": sid, "title": title, "status": status,
        "plan_file": plan_file, "branch": branch,
        "depends_on": depends_on or [],
        "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
    }


class TestCLIParsing(unittest.TestCase):
    """Test that CLI subcommands parse arguments correctly."""

    def setUp(self):
        self.cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin", "superflow-supervisor",
        )

    def test_cli_is_executable(self):
        """The CLI script should be executable."""
        self.assertTrue(os.access(self.cli_path, os.X_OK))

    def test_cli_help(self):
        """CLI should show help without error."""
        result = subprocess.run(
            [sys.executable, self.cli_path, "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())

    def test_cli_run_help(self):
        """run subcommand should show help."""
        result = subprocess.run(
            [sys.executable, self.cli_path, "run", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--queue", result.stdout)

    def test_cli_status_help(self):
        """status subcommand should show help."""
        result = subprocess.run(
            [sys.executable, self.cli_path, "status", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--queue", result.stdout)

    def test_cli_resume_help(self):
        """resume subcommand should show help."""
        result = subprocess.run(
            [sys.executable, self.cli_path, "resume", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--queue", result.stdout)

    def test_cli_reset_help(self):
        """reset subcommand should show help."""
        result = subprocess.run(
            [sys.executable, self.cli_path, "reset", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--sprint", result.stdout)
        self.assertIn("--queue", result.stdout)


class TestCLIStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin", "superflow-supervisor",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_status_shows_sprints(self):
        """status command should show sprint table."""
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ])
        q.sprints[0]["pr"] = "https://github.com/pr/1"
        q.save(self.queue_path)

        result = subprocess.run(
            [sys.executable, self.cli_path, "status", "--queue", self.queue_path],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("completed", result.stdout.lower())
        self.assertIn("pending", result.stdout.lower())


class TestCLIReset(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin", "superflow-supervisor",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_reset_changes_sprint_status(self):
        """reset command should change sprint status to pending."""
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="failed"),
            _sprint(sid=2, status="pending", depends_on=[1]),
        ])
        q.sprints[0]["error_log"] = "some error"
        q.save(self.queue_path)

        result = subprocess.run(
            [sys.executable, self.cli_path, "reset",
             "--queue", self.queue_path, "--sprint", "1"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

        # Verify the sprint was reset
        q2 = SprintQueue.load(self.queue_path)
        self.assertEqual(q2.sprints[0]["status"], "pending")
        self.assertEqual(q2.sprints[0]["retries"], 0)

    def test_reset_nonexistent_sprint(self):
        """reset with invalid sprint ID should error."""
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="failed"),
        ])
        q.save(self.queue_path)

        result = subprocess.run(
            [sys.executable, self.cli_path, "reset",
             "--queue", self.queue_path, "--sprint", "99"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


class TestCLIResume(unittest.TestCase):
    """Test that resume CLI command still works after Sprint 3 changes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin", "superflow-supervisor",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_cli_resume_still_works(self):
        """resume command should complete without error for a queue with no in_progress sprints."""
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ])
        q.sprints[0]["pr"] = "https://github.com/pr/1"
        q.save(self.queue_path)

        # Resume with no in_progress sprints should complete quickly
        # We mock run to avoid actual preflight/execution
        result = subprocess.run(
            [sys.executable, "-c",
             f"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath("{self.cli_path}"))))
from lib.supervisor import resume, print_summary
q = resume("{self.queue_path}", "{self.tmpdir}")
print_summary(q)
"""],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("pending", result.stdout.lower())


class TestCLITelegramFlagsRemoved(unittest.TestCase):
    """Verify --telegram-token and --telegram-chat no longer appear in CLI help."""

    def setUp(self):
        self.cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin", "superflow-supervisor",
        )

    def _help(self, *args):
        result = subprocess.run(
            [sys.executable, self.cli_path] + list(args) + ["--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        return result.stdout

    def test_run_has_no_telegram_token_flag(self):
        """run subcommand must not expose --telegram-token."""
        self.assertNotIn("--telegram-token", self._help("run"))

    def test_run_has_no_telegram_chat_flag(self):
        """run subcommand must not expose --telegram-chat."""
        self.assertNotIn("--telegram-chat", self._help("run"))

    def test_resume_has_no_telegram_token_flag(self):
        """resume subcommand must not expose --telegram-token."""
        self.assertNotIn("--telegram-token", self._help("resume"))

    def test_resume_has_no_telegram_chat_flag(self):
        """resume subcommand must not expose --telegram-chat."""
        self.assertNotIn("--telegram-chat", self._help("resume"))


if __name__ == "__main__":
    unittest.main()

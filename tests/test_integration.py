"""Integration tests — end-to-end happy path."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from lib.queue import SprintQueue
from lib.checkpoint import load_checkpoint, save_checkpoint, load_all_checkpoints
from lib.supervisor import run, resume, print_summary
import lib.supervisor as supervisor_module


def _make_sprint(sid, title, branch, plan_file, depends_on=None, max_retries=2):
    return {
        "id": sid,
        "title": title,
        "status": "pending",
        "plan_file": plan_file,
        "branch": branch,
        "depends_on": depends_on or [],
        "pr": None,
        "retries": 0,
        "max_retries": max_retries,
        "error_log": None,
    }


def _claude_success_output(pr_num=1):
    """Return mock claude stdout with valid JSON summary on last line."""
    return (
        "Working on sprint implementation...\n"
        "Created branch, made changes, pushed.\n"
        f'{{"status":"completed","pr_url":"https://github.com/test/repo/pull/{pr_num}",'
        f'"tests":{{"passed":5,"failed":0}},"par":{{"claude":"ACCEPTED","secondary":"ACCEPTED"}}}}'
    )


def _claude_fail_output():
    """Return mock claude stdout for a failed run."""
    return "Error: something went wrong\nCould not complete sprint."


class IntegrationBase(unittest.TestCase):
    """Base class with common setup for integration tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "sprint-queue.json")
        self.checkpoints_dir = os.path.join(self.tmpdir, "checkpoints")

        # Create templates directory with template file
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n"
                "Plan: {sprint_plan}\n"
                "Context: {claude_md}\n"
                "LLMs: {llms_txt}\n"
                "Branch: {branch}\n"
            )

        # Create plan file with 3 sprint sections
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write(
                "# Feature Plan\n\n"
                "## Sprint 1\n"
                "Implement the foundation module.\n\n"
                "## Sprint 2\n"
                "Add the API layer.\n\n"
                "## Sprint 3\n"
                "Integration and testing.\n"
            )

    def tearDown(self):
        # Reset shutdown flag
        supervisor_module._shutdown_requested = False
        shutil.rmtree(self.tmpdir)

    def _create_queue(self, sprints):
        """Create and save a sprint queue with given sprints."""
        q = SprintQueue("integration-test-feature", "2026-03-23T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q


def _preflight_subproc_effect(cmd, **kwargs):
    """Common subprocess mock for preflight checks."""
    cmd_list = cmd if isinstance(cmd, list) else [cmd]
    if "claude" in cmd_list and "--version" in cmd_list:
        return MagicMock(returncode=0, stdout="claude 1.0", stderr="")
    if "git" in cmd_list and "status" in cmd_list:
        return MagicMock(returncode=0, stdout="", stderr="")
    if "gh" in cmd_list and "auth" in cmd_list:
        return MagicMock(returncode=0, stdout="Logged in", stderr="")
    return None


class TestHappyPath(IntegrationBase):
    """End-to-end test — 3 sprints, sprint 1+2 independent, sprint 3 depends on 1."""

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor.shutil.disk_usage")
    def test_e2e_three_sprints_with_dependencies(
        self, mock_disk, mock_subproc, mock_create_wt, mock_cleanup_wt
    ):
        """Full run: sprints 1+2 independent, sprint 3 depends on 1.

        Uses max_parallel=2. Sprints 1 and 2 are independent and can run
        in parallel; sprint 3 depends on sprint 1.
        All should end as completed with checkpoints saved.

        Note: parallel threading tested in detail in test_parallel.py.
        Here we mock execute_parallel to ensure deterministic execution.
        """
        sprints = [
            _make_sprint(1, "Foundation", "feat/foundation-1",
                         "plans/plan.md#sprint-1"),
            _make_sprint(2, "API Layer", "feat/api-2",
                         "plans/plan.md#sprint-2"),
            _make_sprint(3, "Integration", "feat/integration-3",
                         "plans/plan.md#sprint-3", depends_on=[1]),
        ]
        self._create_queue(sprints)

        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        mock_create_wt.side_effect = lambda sprint, root: os.path.join(
            root, ".worktrees", f"sprint-{sprint['id']}"
        )

        def subproc_side_effect(cmd, **kwargs):
            result = _preflight_subproc_effect(cmd, **kwargs)
            if result is not None:
                return result
            if "claude" in cmd and "-p" in cmd:
                inp = kwargs.get("input", "")
                if "Sprint 1" in inp:
                    return MagicMock(returncode=0, stdout=_claude_success_output(1), stderr="")
                elif "Sprint 2" in inp:
                    return MagicMock(returncode=0, stdout=_claude_success_output(2), stderr="")
                elif "Sprint 3" in inp:
                    return MagicMock(returncode=0, stdout=_claude_success_output(3), stderr="")
                return MagicMock(returncode=0, stdout=_claude_success_output(99), stderr="")
            if "gh" in cmd and "pr" in cmd and "view" in cmd:
                return MagicMock(returncode=0, stdout="OPEN", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = subproc_side_effect

        # Mock execute_parallel to run sprints sequentially, avoiding
        # thread-safety issues in queue.save() (concurrent atomic renames).
        # Parallel threading correctness is tested in test_parallel.py.
        def mock_execute_parallel(sprints_list, queue, queue_path, cp_dir,
                                  repo_root, timeout=1800, notifier=None,
                                  max_workers=2, on_sprint_done=None):
            from lib.supervisor import execute_sprint
            for sprint in sprints_list:
                execute_sprint(sprint, queue, queue_path, cp_dir, repo_root,
                               timeout=timeout, notifier=notifier)

        with patch("lib.parallel.execute_parallel", side_effect=mock_execute_parallel):
            run(
                queue_path=self.queue_path,
                max_parallel=2,
                timeout=60,
                no_replan=True,
                repo_root=self.tmpdir,
            )

        # Verify: all sprints completed
        q = SprintQueue.load(self.queue_path)
        self.assertTrue(q.is_done(), "Queue should be done")
        for s in q.sprints:
            self.assertEqual(s["status"], "completed",
                             f"Sprint {s['id']} should be completed, got {s['status']}")

        # Verify: checkpoints saved for all sprints
        for sid in [1, 2, 3]:
            cp = load_checkpoint(self.checkpoints_dir, sid)
            self.assertIsNotNone(cp, f"Checkpoint for sprint {sid} should exist")
            self.assertEqual(cp["status"], "completed",
                             f"Checkpoint for sprint {sid} should show completed")

        # Verify: print_summary runs without error
        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            print_summary(q)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn("completed", output.lower())

        # Verify: cleanup was called for each sprint
        self.assertEqual(mock_cleanup_wt.call_count, 3)

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor.shutil.disk_usage")
    def test_e2e_sequential_all_complete(
        self, mock_disk, mock_subproc, mock_create_wt, mock_cleanup_wt
    ):
        """Sequential execution (max_parallel=1): all 3 sprints complete in order."""
        sprints = [
            _make_sprint(1, "Foundation", "feat/foundation-1",
                         "plans/plan.md#sprint-1"),
            _make_sprint(2, "API Layer", "feat/api-2",
                         "plans/plan.md#sprint-2"),
            _make_sprint(3, "Integration", "feat/integration-3",
                         "plans/plan.md#sprint-3", depends_on=[1]),
        ]
        self._create_queue(sprints)

        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        mock_create_wt.side_effect = lambda sprint, root: os.path.join(
            root, ".worktrees", f"sprint-{sprint['id']}"
        )

        pr_counter = [0]

        def subproc_side_effect(cmd, **kwargs):
            result = _preflight_subproc_effect(cmd, **kwargs)
            if result is not None:
                return result
            cmd_list = cmd if isinstance(cmd, list) else [cmd]
            if "claude" in cmd_list and "-p" in cmd_list:
                pr_counter[0] += 1
                return MagicMock(
                    returncode=0,
                    stdout=_claude_success_output(pr_counter[0]),
                    stderr=""
                )
            if "gh" in cmd_list and "pr" in cmd_list and "view" in cmd_list:
                return MagicMock(returncode=0, stdout="OPEN", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = subproc_side_effect

        run(
            queue_path=self.queue_path,
            max_parallel=1,
            timeout=60,
            no_replan=True,
            repo_root=self.tmpdir,
        )

        q = SprintQueue.load(self.queue_path)
        self.assertTrue(q.is_done())
        for s in q.sprints:
            self.assertEqual(s["status"], "completed")

        # Verify PR URLs are set
        for s in q.sprints:
            self.assertIsNotNone(s["pr"])
            self.assertIn("github.com", s["pr"])


if __name__ == "__main__":
    unittest.main()

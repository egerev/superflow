"""Tests for supervisor — TDD approach."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from lib.supervisor import create_worktree, cleanup_worktree, build_prompt


def _sprint(sid=1, title="Test Sprint", status="pending", branch="feat/test-sprint-1",
            plan_file="plans/plan.md#sprint-1", depends_on=None):
    return {
        "id": sid, "title": title, "status": status,
        "plan_file": plan_file, "branch": branch,
        "depends_on": depends_on or [],
        "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
    }


class TestCreateWorktree(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("lib.supervisor.subprocess.run")
    def test_create_worktree_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        sprint = _sprint(sid=1, branch="feat/test-sprint-1")
        path = create_worktree(sprint, self.tmpdir)
        expected = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        self.assertEqual(path, expected)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("git", args)
        self.assertIn("worktree", args)
        self.assertIn("-b", args)
        self.assertIn("feat/test-sprint-1", args)

    @patch("lib.supervisor.subprocess.run")
    def test_create_worktree_branch_exists_retries_without_b(self, mock_run):
        """If branch already exists, retry without -b flag."""
        fail = MagicMock(returncode=128, stderr="already exists")
        success = MagicMock(returncode=0, stderr="")
        mock_run.side_effect = [fail, success]
        sprint = _sprint(sid=2, branch="feat/test-sprint-2")
        path = create_worktree(sprint, self.tmpdir)
        expected = os.path.join(self.tmpdir, ".worktrees", "sprint-2")
        self.assertEqual(path, expected)
        self.assertEqual(mock_run.call_count, 2)
        # Second call should not have -b
        second_args = mock_run.call_args_list[1][0][0]
        self.assertNotIn("-b", second_args)

    @patch("lib.supervisor.subprocess.run")
    def test_create_worktree_already_exists_removes_and_recreates(self, mock_run):
        """If worktree already exists, remove it and recreate."""
        fail_worktree = MagicMock(returncode=128, stderr="already locked")
        remove_ok = MagicMock(returncode=0, stderr="")
        create_ok = MagicMock(returncode=0, stderr="")
        mock_run.side_effect = [fail_worktree, remove_ok, create_ok]
        sprint = _sprint(sid=3, branch="feat/test-sprint-3")
        path = create_worktree(sprint, self.tmpdir)
        expected = os.path.join(self.tmpdir, ".worktrees", "sprint-3")
        self.assertEqual(path, expected)
        self.assertEqual(mock_run.call_count, 3)
        # Second call should be worktree remove
        remove_args = mock_run.call_args_list[1][0][0]
        self.assertIn("remove", remove_args)


class TestCleanupWorktree(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("lib.supervisor.subprocess.run")
    def test_cleanup_worktree_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        sprint = _sprint(sid=1)
        cleanup_worktree(sprint, self.tmpdir)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("remove", args)
        self.assertIn("--force", args)

    @patch("lib.supervisor.subprocess.run")
    def test_cleanup_worktree_failure_logged(self, mock_run):
        """Cleanup should not raise even if removal fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        sprint = _sprint(sid=1)
        # Should not raise
        cleanup_worktree(sprint, self.tmpdir)


class TestBuildPrompt(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create templates directory
        self.templates_dir = os.path.join(self.tmpdir, "templates")
        os.makedirs(self.templates_dir)
        # Write the template
        with open(os.path.join(self.templates_dir, "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n"
                "Plan: {sprint_plan}\n"
                "Claude: {claude_md}\n"
                "LLMs: {llms_txt}\n"
                "Branch: {branch}\n"
            )
        # Create a plan file with sections
        self.plans_dir = os.path.join(self.tmpdir, "plans")
        os.makedirs(self.plans_dir)
        with open(os.path.join(self.plans_dir, "plan.md"), "w") as f:
            f.write(
                "# Feature Plan\n\n"
                "## Sprint 1\n"
                "Do the first thing.\n"
                "Details here.\n\n"
                "## Sprint 2\n"
                "Do the second thing.\n"
            )
        # Create CLAUDE.md
        with open(os.path.join(self.tmpdir, "CLAUDE.md"), "w") as f:
            f.write("Project rules here.")
        # Create llms.txt
        with open(os.path.join(self.tmpdir, "llms.txt"), "w") as f:
            f.write("LLM context here.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_build_prompt_fills_placeholders(self):
        sprint = _sprint(sid=1, title="First Sprint", branch="feat/test-sprint-1",
                         plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Sprint 1: First Sprint", result)
        self.assertIn("Do the first thing.", result)
        self.assertIn("Details here.", result)
        self.assertIn("Project rules here.", result)
        self.assertIn("LLM context here.", result)
        self.assertIn("feat/test-sprint-1", result)
        # Should NOT contain sprint 2 content
        self.assertNotIn("Do the second thing.", result)

    def test_build_prompt_extracts_correct_section(self):
        sprint = _sprint(sid=2, title="Second Sprint", branch="feat/test-sprint-2",
                         plan_file="plans/plan.md#sprint-2")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Do the second thing.", result)
        self.assertNotIn("Do the first thing.", result)

    def test_build_prompt_missing_claude_md(self):
        os.remove(os.path.join(self.tmpdir, "CLAUDE.md"))
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        # Should still work, with empty claude_md
        self.assertIn("Sprint 1", result)

    def test_build_prompt_missing_llms_txt(self):
        os.remove(os.path.join(self.tmpdir, "llms.txt"))
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Sprint 1", result)

    def test_build_prompt_plan_no_fragment(self):
        """If plan_file has no #fragment, use the entire file."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Do the first thing.", result)
        self.assertIn("Do the second thing.", result)


if __name__ == "__main__":
    unittest.main()

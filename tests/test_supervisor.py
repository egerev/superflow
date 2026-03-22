"""Tests for supervisor — TDD approach."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from lib.supervisor import (
    create_worktree, cleanup_worktree, build_prompt, execute_sprint,
    preflight, run, print_summary, resume, _shutdown_requested,
)
import lib.supervisor as supervisor_module
from lib.queue import SprintQueue
from lib.checkpoint import load_checkpoint


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


class TestExecuteSprint(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        # Create templates
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n")
        # Create plan file
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints=None):
        if sprints is None:
            sprints = [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")]
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_success(self, mock_run, mock_create_wt, mock_cleanup_wt):
        """Successful execution: claude returns JSON, exit 0, PR verified."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path

        # Claude subprocess
        claude_output = (
            "Working on sprint...\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":5,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"}}'
        )
        claude_result = MagicMock(returncode=0, stdout=claude_output, stderr="")
        # gh pr view subprocess
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [claude_result, gh_result]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["status"], "completed")
        self.assertEqual(sprint["pr"], "https://github.com/test/repo/pull/1")
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_failure_marks_failed(self, mock_run, mock_create_wt, mock_cleanup_wt):
        """After max_retries failures, sprint is marked failed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 1
        sprint_data["retries"] = 1  # Already at max
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path

        # Claude subprocess fails
        claude_result = MagicMock(returncode=1, stdout="Error occurred", stderr="crash")
        mock_run.return_value = claude_result

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertEqual(sprint["status"], "failed")
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_retry_on_failure(self, mock_run, mock_create_wt, mock_cleanup_wt):
        """On failure with retries left, should retry and eventually succeed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path

        # First attempt fails (exit 1), retry succeeds
        fail_result = MagicMock(returncode=1, stdout="Error", stderr="")
        success_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/2",'
            '"tests":{"passed":3,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"}}'
        )
        success_result = MagicMock(returncode=0, stdout=success_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [fail_result, success_result, gh_result]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_json_parse_error_retries(self, mock_run, mock_create_wt, mock_cleanup_wt):
        """Exit 0 but no valid JSON on last line should retry with appended instruction."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path

        # First: exit 0 but no JSON
        no_json = MagicMock(returncode=0, stdout="Done but forgot JSON", stderr="")
        # Retry: exit 0 with proper JSON
        good_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/3",'
            '"tests":{"passed":1,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"}}'
        )
        good_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [no_json, good_result, gh_result]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_saves_output_log(self, mock_run, mock_create_wt, mock_cleanup_wt):
        """Output should be saved to sprint-{id}-output.log."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path

        claude_output = (
            "Log line 1\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":1,"failed":0},"par":{"claude":"ACCEPTED","secondary":"ACCEPTED"}}'
        )
        claude_result = MagicMock(returncode=0, stdout=claude_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [claude_result, gh_result]

        execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        log_path = os.path.join(self.cp_dir, "sprint-1-output.log")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path) as f:
            content = f.read()
        self.assertIn("Log line 1", content)


class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create plan files for queue validation
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nStuff\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints=None):
        if sprints is None:
            sprints = [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")]
        return SprintQueue("test", "2026-01-01T00:00:00Z", sprints)

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_all_pass(self, mock_run, mock_disk):
        """All checks pass."""
        def side_effect(cmd, **kwargs):
            if "claude" in cmd:
                return MagicMock(returncode=0, stdout="claude 1.0\n", stderr="")
            if "status" in cmd and "--porcelain" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")  # Clean
            if "auth" in cmd:
                return MagicMock(returncode=0, stdout="Logged in\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = side_effect
        mock_disk.return_value = MagicMock(free=10 * 1024**3)  # 10GB free
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        self.assertTrue(passed)
        self.assertEqual(issues, [])

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_claude_missing(self, mock_run, mock_disk):
        """Claude CLI not found should fail preflight."""
        mock_run.side_effect = FileNotFoundError("claude not found")
        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        self.assertFalse(passed)
        self.assertTrue(any("claude" in i.lower() for i in issues))

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_dirty_git_warns(self, mock_run, mock_disk):
        """Dirty git status should warn but not fail."""
        def side_effect(cmd, **kwargs):
            if "claude" in cmd:
                return MagicMock(returncode=0, stdout="claude 1.0\n", stderr="")
            if "status" in cmd:
                return MagicMock(returncode=0, stdout="M file.py\n", stderr="")
            if "auth" in cmd:
                return MagicMock(returncode=0, stdout="Logged in\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = side_effect
        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        # Dirty git is a warning, not a failure
        self.assertTrue(passed)
        self.assertTrue(any("dirty" in i.lower() or "uncommitted" in i.lower() for i in issues))

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_gh_auth_fails(self, mock_run, mock_disk):
        """gh auth failure should fail preflight."""
        def side_effect(cmd, **kwargs):
            if "claude" in cmd:
                return MagicMock(returncode=0, stdout="claude 1.0\n", stderr="")
            if "status" in cmd and "--porcelain" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "auth" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="not logged in")
            return MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = side_effect
        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        self.assertFalse(passed)
        self.assertTrue(any("gh" in i.lower() for i in issues))

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_missing_plan_file(self, mock_run, mock_disk):
        """Missing plan file should fail preflight."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        q = self._make_queue([_sprint(sid=1, plan_file="nonexistent/plan.md#sprint-1")])
        passed, issues = preflight(q, self.tmpdir)
        self.assertFalse(passed)
        self.assertTrue(any("plan" in i.lower() for i in issues))

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_low_disk_warns(self, mock_run, mock_disk):
        """Low disk space should warn but not fail."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        mock_disk.return_value = MagicMock(free=500 * 1024**2)  # 500MB
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        # Low disk is a warning, should still pass
        self.assertTrue(passed)
        self.assertTrue(any("disk" in i.lower() for i in issues))


class TestRunLoop(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        # Create templates
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n")
        # Create plan file
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff 1.\n\n## Sprint 2\nDo stuff 2.\n\n## Sprint 3\nDo stuff 3.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_three_sprints(self, mock_preflight, mock_execute):
        """Run loop processes 3 sequential sprints."""
        sprints = [
            _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
            _sprint(sid=2, plan_file="plans/plan.md#sprint-2", depends_on=[1]),
            _sprint(sid=3, plan_file="plans/plan.md#sprint-3", depends_on=[2]),
        ]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        def execute_side_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
            queue.mark_completed(sprint["id"], f"https://github.com/pr/{sprint['id']}")
            queue.save(queue_path)
            return {"sprint_id": sprint["id"], "status": "completed"}

        mock_execute.side_effect = execute_side_effect

        run(self.queue_path, repo_root=self.tmpdir)

        self.assertEqual(mock_execute.call_count, 3)
        # Verify queue is all completed
        q = SprintQueue.load(self.queue_path)
        self.assertTrue(q.is_done())
        for s in q.sprints:
            self.assertEqual(s["status"], "completed")

    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_blocked_sprints_skipped(self, mock_preflight, mock_execute):
        """When sprint 1 fails, sprint 2 depending on it should be skipped."""
        sprints = [
            _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
            _sprint(sid=2, plan_file="plans/plan.md#sprint-2", depends_on=[1]),
        ]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        def execute_side_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
            queue.mark_failed(sprint["id"], "failed")
            queue.save(queue_path)
            return {"sprint_id": sprint["id"], "status": "failed"}

        mock_execute.side_effect = execute_side_effect

        run(self.queue_path, repo_root=self.tmpdir)

        q = SprintQueue.load(self.queue_path)
        self.assertEqual(q.sprints[0]["status"], "failed")
        self.assertEqual(q.sprints[1]["status"], "skipped")

    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_preflight_fails_aborts(self, mock_preflight, mock_execute):
        """If preflight fails, run should not execute any sprints."""
        sprints = [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")]
        self._make_queue(sprints)
        mock_preflight.return_value = (False, ["claude CLI not found"])

        run(self.queue_path, repo_root=self.tmpdir)

        mock_execute.assert_not_called()


class TestPrintSummary(unittest.TestCase):
    def test_print_summary_formats_output(self):
        """print_summary should not raise and should produce output."""
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="failed"),
            _sprint(sid=3, status="skipped"),
        ])
        q.sprints[0]["pr"] = "https://github.com/pr/1"
        q.sprints[1]["error_log"] = "crash"
        # Should not raise
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
        self.assertIn("failed", output.lower())


class TestResume(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.subprocess.run")
    def test_resume_in_progress_no_worktree_resets_pending(self, mock_run):
        """In-progress sprint with no worktree and no PR should reset to pending."""
        sprints = [
            _sprint(sid=1, status="in_progress", branch="feat/test-sprint-1"),
            _sprint(sid=2, status="pending", depends_on=[1]),
        ]
        self._make_queue(sprints)
        # gh pr list returns empty (no PR for this branch)
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        q = resume(self.queue_path, self.tmpdir)

        self.assertEqual(q.sprints[0]["status"], "pending")

    @patch("lib.supervisor.subprocess.run")
    def test_resume_in_progress_with_pr_marks_completed(self, mock_run):
        """In-progress sprint with existing PR should be marked completed."""
        sprints = [
            _sprint(sid=1, status="in_progress", branch="feat/test-sprint-1"),
        ]
        self._make_queue(sprints)
        # Worktree exists
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        os.makedirs(wt_path)
        # gh pr list returns a PR
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/test/repo/pull/1\tOPEN\tTest PR\n",
            stderr="",
        )

        q = resume(self.queue_path, self.tmpdir)

        self.assertEqual(q.sprints[0]["status"], "completed")
        self.assertIn("github.com", q.sprints[0]["pr"])


class TestShutdownFlag(unittest.TestCase):
    def test_shutdown_flag_stops_run_loop(self):
        """Setting _shutdown_requested should stop the run loop after current sprint."""
        tmpdir = tempfile.mkdtemp()
        try:
            queue_path = os.path.join(tmpdir, "queue.json")
            os.makedirs(os.path.join(tmpdir, "templates"))
            with open(os.path.join(tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
                f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n")
            os.makedirs(os.path.join(tmpdir, "plans"))
            with open(os.path.join(tmpdir, "plans", "plan.md"), "w") as f:
                f.write("## Sprint 1\nStuff 1.\n\n## Sprint 2\nStuff 2.\n")

            sprints = [
                _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
                _sprint(sid=2, plan_file="plans/plan.md#sprint-2", depends_on=[1]),
            ]
            q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
            q.save(queue_path)

            call_count = [0]

            def execute_side_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
                call_count[0] += 1
                queue.mark_completed(sprint["id"], f"https://github.com/pr/{sprint['id']}")
                queue.save(queue_path)
                # Set shutdown after first sprint
                supervisor_module._shutdown_requested = True
                return {"sprint_id": sprint["id"], "status": "completed"}

            with patch("lib.supervisor.preflight", return_value=(True, [])):
                with patch("lib.supervisor.execute_sprint", side_effect=execute_side_effect):
                    run(queue_path, repo_root=tmpdir)

            # Only 1 sprint should have executed (shutdown after first)
            self.assertEqual(call_count[0], 1)
        finally:
            supervisor_module._shutdown_requested = False
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()

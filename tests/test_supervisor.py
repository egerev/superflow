"""Tests for supervisor — TDD approach."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

from lib.supervisor import (
    create_worktree, cleanup_worktree, build_prompt, execute_sprint,
    preflight, run, print_summary, resume, _shutdown_event,
    generate_completion_report, _check_pr_exists,
    _validate_evidence_verdicts, _validate_par_evidence,
    _validate_sprint_summary,
    _resolve_baseline_cmd, run_baseline_tests,
    VALID_PASS_VERDICTS, REQUIRED_PAR_KEYS, REQUIRED_SUMMARY_KEYS,
)
import lib.supervisor as supervisor_module
from lib.queue import SprintQueue
from lib.checkpoint import load_checkpoint, save_checkpoint


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
                "Complexity: {complexity}\n"
                "Tier: {implementation_tier}\n"
                "Model: {impl_model}\n"
                "Effort: {impl_effort}\n"
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
        # Default complexity (medium) when not specified
        self.assertIn("Complexity: medium", result)
        self.assertIn("Tier: standard-implementer", result)
        self.assertIn("Model: sonnet", result)
        self.assertIn("Effort: medium", result)

    def test_build_prompt_complexity_simple(self):
        """Simple complexity maps to fast-implementer, sonnet, low."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["complexity"] = "simple"
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Complexity: simple", result)
        self.assertIn("Tier: fast-implementer", result)
        self.assertIn("Model: sonnet", result)
        self.assertIn("Effort: low", result)

    def test_build_prompt_complexity_complex(self):
        """Complex complexity maps to deep-implementer, opus, high."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["complexity"] = "complex"
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Complexity: complex", result)
        self.assertIn("Tier: deep-implementer", result)
        self.assertIn("Model: opus", result)
        self.assertIn("Effort: high", result)

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
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n")
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

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_success(self, mock_run, mock_create_wt, mock_cleanup_wt,
                                     mock_baseline, mock_par, mock_sleep):
        """Successful execution: claude returns JSON, exit 0, PR verified."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        # Claude subprocess
        claude_output = (
            "Working on sprint...\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":5,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
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

    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_failure_marks_failed(self, mock_run, mock_create_wt,
                                                  mock_cleanup_wt, mock_baseline):
        """After max_retries failures, sprint is marked failed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 1
        sprint_data["retries"] = 1  # Already at max
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)

        # Claude subprocess fails
        claude_result = MagicMock(returncode=1, stdout="Error occurred", stderr="crash")
        mock_run.return_value = claude_result

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertEqual(sprint["status"], "failed")
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_retry_on_failure(self, mock_run, mock_create_wt, mock_cleanup_wt,
                                              mock_baseline, mock_par, mock_sleep):
        """On failure with retries left, should retry and eventually succeed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        # First attempt fails (exit 1), retry succeeds
        fail_result = MagicMock(returncode=1, stdout="Error", stderr="")
        success_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/2",'
            '"tests":{"passed":3,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )
        success_result = MagicMock(returncode=0, stdout=success_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [fail_result, success_result, gh_result]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_json_parse_error_retries(self, mock_run, mock_create_wt,
                                                      mock_cleanup_wt, mock_baseline,
                                                      mock_par, mock_sleep):
        """Exit 0 but no valid JSON on last line should retry with appended instruction."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        # First: exit 0 but no JSON
        no_json = MagicMock(returncode=0, stdout="Done but forgot JSON", stderr="")
        # Retry: exit 0 with proper JSON
        good_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/3",'
            '"tests":{"passed":1,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )
        good_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [no_json, good_result, gh_result]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_saves_output_log(self, mock_run, mock_create_wt, mock_cleanup_wt,
                                              mock_baseline, mock_par, mock_sleep):
        """Output should be saved to sprint-{id}-output.log."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        claude_output = (
            "Log line 1\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":1,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )
        claude_result = MagicMock(returncode=0, stdout=claude_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [claude_result, gh_result]

        execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        log_path = os.path.join(self.cp_dir, "sprint-1-attempt-1-output.log")
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
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n")
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


class TestRunLoopParallel(unittest.TestCase):
    """Tests for parallel execution and replanner integration in run()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n")
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nStuff 1.\n\n## Sprint 2\nStuff 2.\n\n## Sprint 3\nStuff 3.\n")
        self.plan_path = os.path.join(self.tmpdir, "plans", "plan.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor._run_replan")
    @patch("lib.parallel._worker")
    @patch("lib.supervisor.preflight")
    def test_run_loop_parallel_two_independent(self, mock_preflight, mock_worker, mock_replan):
        """With max_parallel=2 and 2 independent sprints, execute_parallel is used."""
        sprints = [
            _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
            _sprint(sid=2, plan_file="plans/plan.md#sprint-2"),
        ]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])
        mock_replan.return_value = []

        def worker_effect(sprint, queue, queue_path, cp_dir, repo_root,
                          timeout, notifier, queue_lock):
            with queue_lock:
                queue.mark_completed(sprint["id"], f"https://pr/{sprint['id']}")
                queue.save(queue_path)

        mock_worker.side_effect = worker_effect

        run(self.queue_path, plan_path=self.plan_path,
            max_parallel=2, repo_root=self.tmpdir)

        # Both sprints should be completed
        q = SprintQueue.load(self.queue_path)
        self.assertTrue(q.is_done())
        for s in q.sprints:
            self.assertEqual(s["status"], "completed")
        # Worker should have been called for both
        self.assertEqual(mock_worker.call_count, 2)

    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_replan_called_after_sprint(self, mock_preflight, mock_execute, mock_replan):
        """Replanner should be called after each sprint when plan_path is set."""
        sprints = [
            _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
            _sprint(sid=2, plan_file="plans/plan.md#sprint-2", depends_on=[1]),
        ]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])
        mock_replan.return_value = []

        def execute_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
            queue.mark_completed(sprint["id"], f"https://pr/{sprint['id']}")
            queue.save(queue_path)
            return {"sprint_id": sprint["id"], "status": "completed"}

        mock_execute.side_effect = execute_effect

        run(self.queue_path, plan_path=self.plan_path,
            max_parallel=1, repo_root=self.tmpdir)

        # Replan should be called after each sprint
        self.assertEqual(mock_replan.call_count, 2)

    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_no_replan_flag(self, mock_preflight, mock_execute, mock_replan):
        """With no_replan=True, replanner should not be called."""
        sprints = [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        def execute_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
            queue.mark_completed(sprint["id"], "https://pr/1")
            queue.save(queue_path)
            return {"sprint_id": sprint["id"], "status": "completed"}

        mock_execute.side_effect = execute_effect

        run(self.queue_path, plan_path=self.plan_path,
            max_parallel=1, no_replan=True, repo_root=self.tmpdir)

        mock_replan.assert_not_called()

    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_no_plan_path_skips_replan(self, mock_preflight, mock_execute, mock_replan):
        """Without plan_path, replanner should not be called."""
        sprints = [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")]
        self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        def execute_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
            queue.mark_completed(sprint["id"], "https://pr/1")
            queue.save(queue_path)
            return {"sprint_id": sprint["id"], "status": "completed"}

        mock_execute.side_effect = execute_effect

        run(self.queue_path, plan_path=None,
            max_parallel=1, repo_root=self.tmpdir)

        mock_replan.assert_not_called()


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
        # gh pr list returns a PR (JSON format)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"url":"https://github.com/test/repo/pull/1"}]\n',
            stderr="",
        )

        q = resume(self.queue_path, self.tmpdir)

        self.assertEqual(q.sprints[0]["status"], "completed")
        self.assertIn("github.com", q.sprints[0]["pr"])


class TestResumeMilestoneAware(unittest.TestCase):
    """Test milestone-aware resume recovery (Sprint 3)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(self.cp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.subprocess.run")
    def test_resume_with_milestones(self, mock_run):
        """Resume reads milestones from checkpoint and saves resume_context."""
        sprints = [
            _sprint(sid=1, status="in_progress", branch="feat/s1"),
            _sprint(sid=2, status="in_progress", branch="feat/s2"),
        ]
        self._make_queue(sprints)

        # Sprint 1: has checkpoint with milestones (baseline + implemented)
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "in_progress",
            "milestones": {"baseline_passed": True, "implemented": True},
        })
        # Sprint 2: has checkpoint with only baseline
        save_checkpoint(self.cp_dir, 2, {
            "sprint_id": 2, "status": "in_progress",
            "milestones": {"baseline_passed": True},
        })

        # gh pr list returns empty for both (no PRs)
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")

        q = resume(self.queue_path, self.tmpdir)

        # Both should be reset to pending
        self.assertEqual(q.sprints[0]["status"], "pending")
        self.assertEqual(q.sprints[1]["status"], "pending")
        self.assertEqual(q.sprints[0]["retries"], 0)
        self.assertEqual(q.sprints[1]["retries"], 0)

        # Check resume_context was written in checkpoints
        cp1 = load_checkpoint(self.cp_dir, 1)
        self.assertEqual(cp1["status"], "resumed")
        self.assertTrue(cp1["resume_context"]["baseline_was_passing"])
        self.assertFalse(cp1["resume_context"]["par_was_validated"])

        cp2 = load_checkpoint(self.cp_dir, 2)
        self.assertEqual(cp2["status"], "resumed")
        self.assertTrue(cp2["resume_context"]["baseline_was_passing"])
        self.assertFalse(cp2["resume_context"]["par_was_validated"])

    @patch("lib.supervisor.subprocess.run")
    def test_resume_holistic_in_progress(self, mock_run):
        """Resume detects holistic review in_progress checkpoint."""
        sprints = [
            _sprint(sid=1, status="completed", branch="feat/s1"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        self._make_queue(sprints)

        # Save holistic checkpoint as in_progress
        save_checkpoint(self.cp_dir, "holistic", {
            "phase": "holistic_review", "status": "in_progress",
        })

        # No in_progress sprints, so subprocess.run won't be called for gh pr list
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")

        q = resume(self.queue_path, self.tmpdir)

        # Queue unchanged (no in_progress sprints)
        self.assertEqual(q.sprints[0]["status"], "completed")
        # Holistic checkpoint still exists (resume just logs it, doesn't modify)
        from lib.checkpoint import load_checkpoint_by_name
        holistic_cp = load_checkpoint_by_name(self.cp_dir, "holistic")
        self.assertIsNotNone(holistic_cp)
        self.assertEqual(holistic_cp["status"], "in_progress")

    @patch("lib.supervisor.subprocess.run")
    def test_resume_with_notifier(self, mock_run):
        """Resume calls notify_resume_recovery when notifier provided."""
        sprints = [
            _sprint(sid=1, status="in_progress", branch="feat/s1"),
            _sprint(sid=2, status="in_progress", branch="feat/s2"),
        ]
        self._make_queue(sprints)

        # Sprint 1 has PR, Sprint 2 doesn't
        def gh_side_effect(*args, **kwargs):
            cmd = args[0]
            if isinstance(cmd, list) and "feat/s1" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout='[{"url": "https://github.com/pr/1"}]',
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="[]", stderr="")

        mock_run.side_effect = gh_side_effect

        notifier = MagicMock()
        q = resume(self.queue_path, self.tmpdir, notifier=notifier)

        # Should be called with 1 recovered, 1 reset, 2 total
        notifier.notify_resume_recovery.assert_called_once_with(1, 1, 2)


class TestShutdownFlag(unittest.TestCase):
    def test_shutdown_flag_stops_run_loop(self):
        """Setting _shutdown_event should stop the run loop after current sprint."""
        tmpdir = tempfile.mkdtemp()
        try:
            queue_path = os.path.join(tmpdir, "queue.json")
            os.makedirs(os.path.join(tmpdir, "templates"))
            with open(os.path.join(tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
                f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n")
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
                supervisor_module._shutdown_event.set()
                return {"sprint_id": sprint["id"], "status": "completed"}

            with patch("lib.supervisor.preflight", return_value=(True, [])):
                with patch("lib.supervisor.execute_sprint", side_effect=execute_side_effect):
                    run(queue_path, repo_root=tmpdir)

            # Only 1 sprint should have executed (shutdown after first)
            self.assertEqual(call_count[0], 1)
        finally:
            supervisor_module._shutdown_event.clear()
            shutil.rmtree(tmpdir)


class TestCompletionReport(unittest.TestCase):
    """Tests for generate_completion_report()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        # Create holistic review evidence file (required by unconditional gate)
        self._create_holistic_evidence()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_holistic_evidence(self):
        """Create a .holistic-review-evidence.json in the parent of cp_dir."""
        evidence_path = os.path.join(
            os.path.dirname(self.cp_dir),
            ".holistic-review-evidence.json",
        )
        evidence = {
            "timestamp": "2026-01-01T00:00:00Z",
            "verdict": "APPROVE",
            "reviewers": {
                "claude_code_quality": "APPROVE",
                "claude_product": "APPROVE",
                "codex_code_review": "APPROVE",
                "codex_product": "APPROVE",
            },
        }
        with open(evidence_path, "w") as f:
            json.dump(evidence, f)

    def _make_queue(self, sprints):
        return SprintQueue("test-feature", "2026-01-01T00:00:00Z", sprints)

    def test_report_all_completed(self):
        """Report for all-completed queue includes each sprint with status and PR."""
        sprints = [
            _sprint(sid=1, title="Setup", status="completed"),
            _sprint(sid=2, title="Build", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        sprints[1]["pr"] = "https://github.com/test/repo/pull/2"
        q = self._make_queue(sprints)

        # Create checkpoints with summary data
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {
                "tests": {"passed": 5, "failed": 0},
                "par": {"claude_code_quality": "ACCEPTED", "claude_product": "ACCEPTED",
                        "codex_code_review": "ACCEPTED", "codex_product": "ACCEPTED"},
            },
        })
        save_checkpoint(self.cp_dir, 2, {
            "sprint_id": 2, "status": "completed",
            "summary": {
                "tests": {"passed": 10, "failed": 0},
                "par": {"claude_code_quality": "ACCEPTED", "claude_product": "ACCEPTED",
                        "codex_code_review": "ACCEPTED", "codex_product": "ACCEPTED"},
            },
        })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("# Completion Report", report)
        self.assertIn("test-feature", report)
        self.assertIn("Sprint 1: Setup", report)
        self.assertIn("Sprint 2: Build", report)
        self.assertIn("completed", report)
        self.assertIn("https://github.com/test/repo/pull/1", report)
        self.assertIn("5 passed, 0 failed", report)
        self.assertIn("Claude-CQ=ACCEPTED", report)
        self.assertIn("Codex-CR=ACCEPTED", report)
        self.assertIn("100%", report)

    def test_report_with_failures(self):
        """Report includes failed sprint info with error messages."""
        sprints = [
            _sprint(sid=1, title="Setup", status="completed"),
            _sprint(sid=2, title="Build", status="failed"),
            _sprint(sid=3, title="Deploy", status="skipped"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        sprints[1]["error_log"] = "crash during build"
        sprints[1]["retries"] = 2
        sprints[2]["error_log"] = "dependency failed"
        q = self._make_queue(sprints)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {"tests": {"passed": 3, "failed": 0}, "par": {"claude_code_quality": "ACCEPTED", "claude_product": "ACCEPTED", "codex_code_review": "ACCEPTED", "codex_product": "ACCEPTED"}},
        })
        save_checkpoint(self.cp_dir, 2, {
            "sprint_id": 2, "status": "failed",
            "error": "crash during build", "retries": 2,
        })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("failed", report.lower())
        self.assertIn("crash during build", report)
        self.assertIn("skipped", report.lower())
        self.assertIn("dependency failed", report)
        self.assertIn("Retries", report)
        self.assertIn("33%", report)  # 1 out of 3

    def test_report_no_checkpoints(self):
        """Report works even with no checkpoint files."""
        sprints = [_sprint(sid=1, title="Sprint 1", status="pending")]
        q = self._make_queue(sprints)

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("# Completion Report", report)
        self.assertIn("Sprint 1", report)
        self.assertIn("N/A", report)  # No test/PAR data

    def test_report_writes_to_file(self):
        """When output_path is provided, report is written to file."""
        sprints = [_sprint(sid=1, title="Sprint 1", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        output_path = os.path.join(self.tmpdir, "reports", "report.md")
        report = generate_completion_report(q, self.cp_dir, output_path=output_path)

        # File should exist
        self.assertTrue(os.path.exists(output_path))
        with open(output_path) as f:
            file_content = f.read()
        self.assertEqual(report, file_content)

    def test_report_returns_string(self):
        """Report always returns a string, even without output_path."""
        sprints = [_sprint(sid=1, title="Sprint 1", status="completed")]
        q = self._make_queue(sprints)

        report = generate_completion_report(q, self.cp_dir)

        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)


class TestValidateEvidenceVerdicts(unittest.TestCase):
    """Sprint 1: _validate_evidence_verdicts and _validate_par_evidence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_validate_evidence_valid(self):
        """Valid 4-key PAR with APPROVE/ACCEPTED/PASS verdicts passes."""
        data = {
            "claude_code_quality": "APPROVE",
            "claude_product": "ACCEPTED",
            "codex_code_review": "PASS",
            "codex_product": "APPROVE",
        }
        valid, errors = _validate_evidence_verdicts(data, REQUIRED_PAR_KEYS)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_validate_evidence_missing_file(self):
        """Missing .par-evidence.json returns invalid with error."""
        valid, data, errors = _validate_par_evidence(self.tmpdir)
        self.assertFalse(valid)
        self.assertEqual(data, {})
        self.assertTrue(any("not found" in e for e in errors))

    def test_validate_evidence_missing_keys(self):
        """PAR evidence with missing keys returns errors."""
        data = {
            "claude_code_quality": "APPROVE",
            # missing claude_product, codex_code_review, codex_product
        }
        valid, errors = _validate_evidence_verdicts(data, REQUIRED_PAR_KEYS)
        self.assertFalse(valid)
        self.assertEqual(len(errors), 3)  # 3 missing keys

    def test_validate_evidence_invalid_verdict(self):
        """PAR evidence with invalid verdict value returns error."""
        data = {
            "claude_code_quality": "APPROVE",
            "claude_product": "MAYBE",
            "codex_code_review": "APPROVE",
            "codex_product": "APPROVE",
        }
        valid, errors = _validate_evidence_verdicts(data, REQUIRED_PAR_KEYS)
        self.assertFalse(valid)
        self.assertTrue(any("MAYBE" in e for e in errors))

    def test_validate_evidence_frontend_required(self):
        """With require_frontend=True and all 5 keys present, passes."""
        evidence = {
            "claude_code_quality": "APPROVE",
            "claude_product": "ACCEPTED",
            "codex_code_review": "PASS",
            "codex_product": "APPROVE",
            "frontend_verification": "PASS",
        }
        evidence_path = os.path.join(self.tmpdir, ".par-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump(evidence, f)
        valid, data, errors = _validate_par_evidence(self.tmpdir, require_frontend=True)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_validate_evidence_frontend_missing(self):
        """With require_frontend=True and missing frontend_verification, fails."""
        evidence = {
            "claude_code_quality": "APPROVE",
            "claude_product": "ACCEPTED",
            "codex_code_review": "PASS",
            "codex_product": "APPROVE",
        }
        evidence_path = os.path.join(self.tmpdir, ".par-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump(evidence, f)
        valid, data, errors = _validate_par_evidence(self.tmpdir, require_frontend=True)
        self.assertFalse(valid)
        self.assertTrue(any("frontend_verification" in e for e in errors))


class TestValidateSprintSummary(unittest.TestCase):
    """Sprint 1: _validate_sprint_summary."""

    def test_summary_validation_missing_keys(self):
        """Summary missing required keys returns errors."""
        summary = {"status": "completed"}  # missing pr_url, tests, par
        valid, errors = _validate_sprint_summary(summary)
        self.assertFalse(valid)
        self.assertTrue(any("Missing" in e for e in errors))

    def test_summary_validation_wrong_types(self):
        """Summary with wrong types returns errors."""
        summary = {
            "status": "in_progress",  # wrong — should be "completed"
            "pr_url": 12345,          # wrong — should be str
            "tests": "none",          # wrong — should be dict
            "par": "none",            # wrong — should be dict
        }
        valid, errors = _validate_sprint_summary(summary)
        self.assertFalse(valid)
        # Should have errors for status, pr_url, tests, par
        self.assertGreaterEqual(len(errors), 4)

    def test_summary_validation_valid(self):
        """Valid summary passes all checks."""
        summary = {
            "status": "completed",
            "pr_url": "https://github.com/test/repo/pull/1",
            "tests": {"passed": 5, "failed": 0},
            "par": {"claude_code_quality": "ACCEPTED"},
        }
        valid, errors = _validate_sprint_summary(summary)
        self.assertTrue(valid)
        self.assertEqual(errors, [])


class TestPreflightWorktreesGitignore(unittest.TestCase):
    """Sprint 1: .worktrees gitignore check in preflight()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nStuff\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self):
        return SprintQueue("test", "2026-01-01T00:00:00Z",
                           [_sprint(sid=1, plan_file="plans/plan.md#sprint-1")])

    @patch("lib.supervisor.shutil.disk_usage")
    @patch("lib.supervisor.subprocess.run")
    def test_preflight_worktrees_gitignore(self, mock_run, mock_disk):
        """If .worktrees is not gitignored, preflight should fail with critical issue."""
        def side_effect(cmd, **kwargs):
            if "claude" in cmd:
                return MagicMock(returncode=0, stdout="claude 1.0\n", stderr="")
            if "status" in cmd and "--porcelain" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "auth" in cmd:
                return MagicMock(returncode=0, stdout="Logged in\n", stderr="")
            if "check-ignore" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="")  # NOT ignored
            return MagicMock(returncode=0, stdout="", stderr="")
        mock_run.side_effect = side_effect
        mock_disk.return_value = MagicMock(free=10 * 1024**3)
        q = self._make_queue()
        passed, issues = preflight(q, self.tmpdir)
        self.assertFalse(passed)
        self.assertTrue(any(".worktrees" in i for i in issues))


class TestBuildPromptFrontend(unittest.TestCase):
    """Sprint 1: build_prompt() frontend_instructions injection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.tmpdir, "templates")
        os.makedirs(self.templates_dir)
        # Write the updated template with {frontend_instructions} placeholder
        with open(os.path.join(self.templates_dir, "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n"
                "Plan: {sprint_plan}\n"
                "Claude: {claude_md}\n"
                "LLMs: {llms_txt}\n"
                "Branch: {branch}\n"
                "Complexity: {complexity}\n"
                "Tier: {implementation_tier}\n"
                "Model: {impl_model}\n"
                "Effort: {impl_effort}\n"
                "{frontend_instructions}\n"
                "JSON output here\n"
            )
        self.plans_dir = os.path.join(self.tmpdir, "plans")
        os.makedirs(self.plans_dir)
        with open(os.path.join(self.plans_dir, "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_build_prompt_frontend_placeholder_no_frontend(self):
        """When has_frontend is not set, placeholder is replaced with empty string."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        self.assertNotIn("{frontend_instructions}", result)
        self.assertNotIn("FRONTEND VERIFICATION", result)

    def test_build_prompt_frontend_placeholder_with_frontend(self):
        """When has_frontend=True, placeholder is replaced with frontend instructions."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["has_frontend"] = True
        result = build_prompt(sprint, self.tmpdir)
        self.assertNotIn("{frontend_instructions}", result)
        self.assertIn("FRONTEND VERIFICATION", result)
        self.assertIn("webapp-testing", result)

    @patch("lib.supervisor.logger")
    def test_build_prompt_frontend_missing_placeholder_warns(self, mock_logger):
        """When has_frontend=True but template lacks placeholder, log warning."""
        # Write template WITHOUT {frontend_instructions}
        with open(os.path.join(self.templates_dir, "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n"
                "Plan: {sprint_plan}\n"
                "Claude: {claude_md}\n"
                "LLMs: {llms_txt}\n"
                "Branch: {branch}\n"
                "Complexity: {complexity}\n"
                "Tier: {implementation_tier}\n"
                "Model: {impl_model}\n"
                "Effort: {impl_effort}\n"
            )
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["has_frontend"] = True
        result = build_prompt(sprint, self.tmpdir)
        # Should log a warning
        mock_logger.warning.assert_called()


# =====================================================================
# Sprint 2: Baseline Tests + PAR Gate + Milestone Writes
# =====================================================================


class TestResolveBaselineCmd(unittest.TestCase):
    """Sprint 2: _resolve_baseline_cmd priority and heuristic detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, baseline_cmd=None):
        return SprintQueue("test", "2026-01-01T00:00:00Z", [], baseline_cmd=baseline_cmd)

    def test_baseline_cmd_from_sprint(self):
        """Sprint-level baseline_cmd takes highest priority."""
        sprint = {"baseline_cmd": "make test"}
        q = self._make_queue(baseline_cmd="pytest")
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "make test")

    def test_baseline_cmd_from_queue(self):
        """Queue-level baseline_cmd used when sprint has none."""
        sprint = {}
        q = self._make_queue(baseline_cmd="pytest --tb=short")
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "pytest --tb=short")

    def test_baseline_heuristic_pytest_ini(self):
        """Heuristic detects pytest.ini."""
        with open(os.path.join(self.tmpdir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "python -m pytest --tb=short -q")

    def test_baseline_heuristic_pyproject_toml_with_pytest(self):
        """Heuristic detects pyproject.toml with [tool.pytest] section."""
        with open(os.path.join(self.tmpdir, "pyproject.toml"), "w") as f:
            f.write("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "python -m pytest --tb=short -q")

    def test_baseline_heuristic_pyproject_toml_without_pytest(self):
        """Heuristic skips pyproject.toml without [tool.pytest] section."""
        with open(os.path.join(self.tmpdir, "pyproject.toml"), "w") as f:
            f.write("[build-system]\nrequires = ['setuptools']\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertIsNone(cmd)

    def test_baseline_heuristic_package_json(self):
        """Heuristic detects package.json with 'test' script."""
        with open(os.path.join(self.tmpdir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "jest"}}, f)
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "npm test")

    def test_baseline_heuristic_package_json_no_test_script(self):
        """Heuristic skips package.json without 'test' script."""
        with open(os.path.join(self.tmpdir, "package.json"), "w") as f:
            json.dump({"scripts": {"build": "tsc"}}, f)
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertIsNone(cmd)

    def test_baseline_heuristic_gemfile(self):
        """Heuristic detects Gemfile."""
        with open(os.path.join(self.tmpdir, "Gemfile"), "w") as f:
            f.write("source 'https://rubygems.org'\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "bundle exec rspec")

    def test_baseline_heuristic_go_mod(self):
        """Heuristic detects go.mod."""
        with open(os.path.join(self.tmpdir, "go.mod"), "w") as f:
            f.write("module example.com/project\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "go test ./...")

    def test_baseline_heuristic_mix_exs(self):
        """Heuristic detects mix.exs."""
        with open(os.path.join(self.tmpdir, "mix.exs"), "w") as f:
            f.write("defmodule MyApp.MixProject do\nend\n")
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "mix test")

    def test_baseline_no_runner_returns_none(self):
        """No test runner detected returns None."""
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertIsNone(cmd)


class TestRunBaselineTests(unittest.TestCase):
    """Sprint 2: run_baseline_tests()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, baseline_cmd=None):
        return SprintQueue("test", "2026-01-01T00:00:00Z", [], baseline_cmd=baseline_cmd)

    @patch("lib.supervisor.subprocess.run")
    def test_baseline_pass(self, mock_run):
        """Baseline cmd returns 0 -> passed=True, skipped=False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="3 passed\n", stderr="")
        sprint = {"baseline_cmd": "pytest"}
        q = self._make_queue()
        passed, output, skipped = run_baseline_tests(self.tmpdir, sprint, q)
        self.assertTrue(passed)
        self.assertFalse(skipped)
        self.assertIn("3 passed", output)

    @patch("lib.supervisor.subprocess.run")
    def test_baseline_fail(self, mock_run):
        """Baseline cmd returns non-0 -> passed=False."""
        mock_run.return_value = MagicMock(returncode=1, stdout="1 failed\n", stderr="ERRORS")
        sprint = {"baseline_cmd": "pytest"}
        q = self._make_queue()
        passed, output, skipped = run_baseline_tests(self.tmpdir, sprint, q)
        self.assertFalse(passed)
        self.assertFalse(skipped)

    def test_baseline_no_runner_skips(self):
        """No test runner detected -> passed=True, skipped=True."""
        sprint = {}
        q = self._make_queue()
        passed, output, skipped = run_baseline_tests(self.tmpdir, sprint, q)
        self.assertTrue(passed)
        self.assertTrue(skipped)
        self.assertIn("skipped", output.lower())

    @patch("lib.supervisor.subprocess.run")
    def test_baseline_timeout(self, mock_run):
        """Timeout -> passed=False."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        sprint = {"baseline_cmd": "pytest"}
        q = self._make_queue()
        passed, output, skipped = run_baseline_tests(self.tmpdir, sprint, q)
        self.assertFalse(passed)
        self.assertFalse(skipped)
        self.assertIn("timed out", output.lower())

    @patch("lib.supervisor.subprocess.run")
    def test_baseline_cmd_from_queue_used(self, mock_run):
        """Queue-level baseline_cmd is used when sprint has none."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        sprint = {}
        q = self._make_queue(baseline_cmd="make test")
        passed, output, skipped = run_baseline_tests(self.tmpdir, sprint, q)
        self.assertTrue(passed)
        self.assertFalse(skipped)
        # Verify subprocess.run was called with the queue baseline_cmd
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][0], "make test")
        self.assertTrue(call_args[1].get("shell", False))


class TestBaselineGateInExecuteSprint(unittest.TestCase):
    """Sprint 2: Baseline gate integration in execute_sprint()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n{frontend_instructions}\n")
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
    @patch("lib.supervisor.run_baseline_tests")
    def test_baseline_fail_marks_failed(self, mock_baseline, mock_create_wt, mock_cleanup_wt):
        """Baseline failure -> mark_failed + checkpoint, no Claude invocation."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (False, "2 tests failed\nERROR in test_foo", False)

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(sprint["status"], "failed")
        self.assertIn("Baseline tests failed", sprint.get("error_log", ""))
        # Checkpoint should record baseline failure
        saved_cp = load_checkpoint(self.cp_dir, 1)
        self.assertIsNotNone(saved_cp)
        self.assertEqual(saved_cp["error"], "baseline_tests_failed")
        self.assertIn("baseline_output", saved_cp)
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor._attempt_sprint")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    def test_baseline_pass_proceeds_to_attempt(self, mock_baseline, mock_create_wt,
                                                mock_cleanup_wt, mock_attempt):
        """Baseline pass -> proceed to _attempt_sprint, milestone saved."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "5 tests passed", False)
        mock_attempt.return_value = {"sprint_id": 1, "status": "completed"}

        execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        mock_attempt.assert_called_once()
        # Check baseline milestone was saved
        saved_cp = load_checkpoint(self.cp_dir, 1)
        self.assertIsNotNone(saved_cp)
        milestones = saved_cp.get("milestones", {})
        self.assertTrue(milestones.get("baseline_passed"))

    @patch("lib.supervisor._attempt_sprint")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    def test_baseline_no_runner_skips(self, mock_baseline, mock_create_wt,
                                      mock_cleanup_wt, mock_attempt):
        """No test runner -> skip baseline, proceed to _attempt_sprint."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "No test runner detected — skipped", True)
        mock_attempt.return_value = {"sprint_id": 1, "status": "completed"}

        execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        mock_attempt.assert_called_once()
        saved_cp = load_checkpoint(self.cp_dir, 1)
        milestones = saved_cp.get("milestones", {})
        self.assertTrue(milestones.get("baseline_passed"))
        self.assertTrue(milestones.get("baseline_skipped"))


class TestPARIntegration(unittest.TestCase):
    """Sprint 2: PAR validation + summary validation in _attempt_sprint()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n{frontend_instructions}\n")
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

    def _good_summary_json(self, pr_url="https://github.com/test/repo/pull/1"):
        return (
            '{"status":"completed","pr_url":"' + pr_url + '",'
            '"tests":{"passed":5,"failed":0},'
            '"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED",'
            '"codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_par_integration_retry_separate_counter(self, mock_par, mock_run, mock_baseline,
                                                     mock_create_wt, mock_cleanup_wt, mock_sleep):
        """PAR retry uses separate counter from Claude retry. PAR fail doesn't consume Claude retries."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)

        good_output = "Done.\n" + self._good_summary_json()
        claude_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        # Claude calls: 1st success, 2nd success (PAR retry re-invokes Claude),
        # then gh pr view
        mock_run.side_effect = [claude_result, claude_result, gh_result]

        # First PAR call fails, second PAR call passes
        mock_par.side_effect = [
            (False, {}, ["PAR: missing key 'claude_code_quality'"]),
            (True, {"claude_code_quality": "APPROVE", "claude_product": "APPROVE",
                     "codex_code_review": "APPROVE", "codex_product": "APPROVE"}, []),
        ]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        # Claude retry counter should still be 0 — PAR retries are separate
        # The sprint should have succeeded after 1 PAR retry

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_par_integration_max_retries_fails(self, mock_par, mock_run, mock_baseline,
                                                mock_create_wt, mock_cleanup_wt, mock_sleep):
        """2 PAR retries exceeded -> mark_failed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 5  # High Claude retries — PAR should fail first
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)

        good_output = "Done.\n" + self._good_summary_json()
        claude_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        # 3 Claude invocations (initial + 2 PAR retries)
        mock_run.side_effect = [claude_result, claude_result, claude_result]

        # PAR always fails
        mock_par.return_value = (False, {}, ["PAR: missing .par-evidence.json"])

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertIn("PAR", sprint.get("error_log", ""))


class TestPRValidationRetry(unittest.TestCase):
    """Sprint 2: PR verification retry with separate counter."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n{frontend_instructions}\n")
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

    def _good_summary_json(self, pr_url="https://github.com/test/repo/pull/1"):
        return (
            '{"status":"completed","pr_url":"' + pr_url + '",'
            '"tests":{"passed":5,"failed":0},'
            '"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED",'
            '"codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_pr_validation_retry_3_times(self, mock_par, mock_run, mock_baseline,
                                          mock_create_wt, mock_cleanup_wt, mock_sleep):
        """Transient gh pr view failure retried up to 3 times, then succeeds."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        claude_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_fail = MagicMock(returncode=1, stdout="", stderr="network error")
        gh_ok = MagicMock(returncode=0, stdout="OPEN")
        # Claude, then 2 gh fails, 1 gh success
        mock_run.side_effect = [claude_result, gh_fail, gh_fail, gh_ok]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_pr_validation_hard_fail_after_retries(self, mock_par, mock_run, mock_baseline,
                                                    mock_create_wt, mock_cleanup_wt, mock_sleep):
        """3 gh pr view failures -> mark_failed (NOT re-invoke Claude)."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        claude_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_fail = MagicMock(returncode=1, stdout="", stderr="network error")
        # Claude once, then 3 gh failures
        mock_run.side_effect = [claude_result, gh_fail, gh_fail, gh_fail]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertIn("PR", sprint.get("error_log", ""))
        # Claude should only be called ONCE — no re-invocation
        claude_calls = [c for c in mock_run.call_args_list if "claude" in str(c)]
        self.assertEqual(len(claude_calls), 1)


class TestMilestoneWrites(unittest.TestCase):
    """Sprint 2: Milestone writes in checkpoint at each transition."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n{frontend_instructions}\n")
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

    def _good_summary_json(self, pr_url="https://github.com/test/repo/pull/1"):
        return (
            '{"status":"completed","pr_url":"' + pr_url + '",'
            '"tests":{"passed":5,"failed":0},'
            '"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED",'
            '"codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_milestone_writes_in_checkpoint(self, mock_par, mock_run, mock_baseline,
                                             mock_create_wt, mock_cleanup_wt, mock_sleep):
        """Full success path writes all milestones to checkpoint."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_code_quality": "APPROVE",
                                         "claude_product": "APPROVE",
                                         "codex_code_review": "APPROVE",
                                         "codex_product": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        claude_result = MagicMock(returncode=0, stdout=good_output, stderr="")
        gh_ok = MagicMock(returncode=0, stdout="OPEN")
        mock_run.side_effect = [claude_result, gh_ok]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        # Check final checkpoint has milestones
        saved_cp = load_checkpoint(self.cp_dir, 1)
        self.assertIsNotNone(saved_cp)
        # The completed checkpoint should have milestone info
        # (milestones may be in intermediate checkpoint or final — we check both)
        # The key property: baseline_passed, implemented, par_validated, pr_created
        # should all have been written at some point.
        # Final completed checkpoint should reflect the full path.
        self.assertEqual(saved_cp["status"], "completed")
        milestones = saved_cp.get("milestones", {})
        self.assertTrue(milestones.get("baseline_passed", False))
        self.assertTrue(milestones.get("implemented", False))
        self.assertTrue(milestones.get("par_validated", False))
        self.assertTrue(milestones.get("pr_created", False))


# =====================================================================
# Sprint 4a: Holistic Review Evidence Gate + Report Blocking
# =====================================================================


class TestHolisticGate(unittest.TestCase):
    """Sprint 4a: Holistic review evidence gate in generate_completion_report()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        return SprintQueue("test-feature", "2026-01-01T00:00:00Z", sprints)

    def _create_holistic_evidence(self):
        """Create holistic evidence file in parent of cp_dir."""
        evidence_path = os.path.join(
            os.path.dirname(self.cp_dir),
            ".holistic-review-evidence.json",
        )
        evidence = {
            "timestamp": "2026-01-01T00:00:00Z",
            "verdict": "APPROVE",
            "reviewers": {
                "claude_code_quality": "APPROVE",
                "claude_product": "APPROVE",
                "codex_code_review": "APPROVE",
                "codex_product": "APPROVE",
            },
        }
        with open(evidence_path, "w") as f:
            json.dump(evidence, f)

    def test_holistic_gate_blocks_without_evidence(self):
        """generate_completion_report() raises RuntimeError without evidence file."""
        sprints = [_sprint(sid=1, title="Sprint 1", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        # No holistic evidence file -> RuntimeError
        with self.assertRaises(RuntimeError) as ctx:
            generate_completion_report(q, self.cp_dir)
        self.assertIn("holistic-review-evidence.json", str(ctx.exception))
        self.assertIn("blocked", str(ctx.exception).lower())

    def test_holistic_gate_passes_with_evidence(self):
        """generate_completion_report() succeeds when evidence file exists."""
        sprints = [_sprint(sid=1, title="Sprint 1", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        # Create evidence file
        self._create_holistic_evidence()

        report = generate_completion_report(q, self.cp_dir)
        self.assertIn("# Completion Report", report)
        self.assertIn("Sprint 1", report)


class TestHolisticGateInRun(unittest.TestCase):
    """Sprint 4a: Holistic gate wiring in run() and checkpoint writes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n"
                "{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n"
                "{impl_model}\n{impl_effort}\n{frontend_instructions}\n"
            )
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_skips_holistic_when_no_completed_sprints(self, mock_execute, mock_preflight):
        """run() does not block when all sprints are failed/skipped (no completed)."""
        sprints = [
            _sprint(sid=1, title="Sprint 1", status="failed"),
            _sprint(sid=2, title="Sprint 2", status="skipped"),
        ]
        sprints[0]["error_log"] = "crashed"
        sprints[1]["error_log"] = "dependency failed"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        # Should not block — no completed sprints, queue.is_done() is True
        # No holistic evidence needed, no report generated
        run(self.queue_path, repo_root=self.tmpdir)

        # Should not have called execute_sprint (all done already)
        mock_execute.assert_not_called()
        # No holistic checkpoint should exist
        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        holistic_path = os.path.join(cp_dir, "sprint-holistic.json")
        self.assertFalse(os.path.exists(holistic_path))

    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_blocks_report_on_holistic_failure(self, mock_execute, mock_preflight):
        """Integration: completed sprints but no evidence -> BLOCKED, no report."""
        sprints = [
            _sprint(sid=1, title="Setup", status="completed"),
            _sprint(sid=2, title="Build", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        sprints[1]["pr"] = "https://github.com/test/repo/pull/2"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        # Capture stdout to check for BLOCKED message
        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            run(self.queue_path, repo_root=self.tmpdir)
            output = mock_stdout.getvalue()

        self.assertIn("BLOCKED", output)
        self.assertNotIn("# Completion Report", output)

        # Holistic checkpoint should exist with pending status
        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        holistic_path = os.path.join(cp_dir, "sprint-holistic.json")
        self.assertTrue(os.path.exists(holistic_path))
        with open(holistic_path) as f:
            holistic_cp = json.load(f)
        self.assertEqual(holistic_cp["phase"], "holistic_review")
        self.assertEqual(holistic_cp["status"], "pending")

    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_generates_report_with_holistic_evidence(self, mock_execute, mock_preflight):
        """Integration: completed sprints + evidence -> report generated, checkpoint updated."""
        sprints = [
            _sprint(sid=1, title="Setup", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        # Create holistic evidence
        evidence_path = os.path.join(self.tmpdir, ".holistic-review-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump({"verdict": "APPROVE", "timestamp": "2026-01-01T00:00:00Z", "reviewers": {"claude_code_quality": "APPROVE", "claude_product": "APPROVE", "codex_code_review": "APPROVE", "codex_product": "APPROVE"}}, f)

        # Create checkpoint for the sprint (so report can read it)
        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        save_checkpoint(cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            run(self.queue_path, repo_root=self.tmpdir)
            output = mock_stdout.getvalue()

        self.assertNotIn("BLOCKED", output)
        self.assertIn("# Completion Report", output)

        # Holistic checkpoint should be completed
        holistic_path = os.path.join(cp_dir, "sprint-holistic.json")
        self.assertTrue(os.path.exists(holistic_path))
        with open(holistic_path) as f:
            holistic_cp = json.load(f)
        self.assertEqual(holistic_cp["status"], "completed")
        self.assertEqual(holistic_cp["verdict"], "APPROVE")

    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_holistic_notifies_start_and_complete(self, mock_execute, mock_preflight):
        """run() notifies holistic_review_start and holistic_review_complete."""
        sprints = [_sprint(sid=1, title="Setup", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        # Create evidence so it passes (must have valid reviewer verdicts)
        evidence_path = os.path.join(self.tmpdir, ".holistic-review-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump({"verdict": "APPROVE", "reviewers": {"claude_code_quality": "APPROVE", "claude_product": "APPROVE", "codex_code_review": "APPROVE", "codex_product": "APPROVE"}}, f)

        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        save_checkpoint(cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        notifier = MagicMock()

        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO):
            run(self.queue_path, repo_root=self.tmpdir, notifier=notifier)

        notifier.notify_holistic_review_start.assert_called_once()
        notifier.notify_holistic_review_complete.assert_called_once_with("APPROVE")
        notifier.notify_all_done.assert_called_once()


if __name__ == "__main__":
    unittest.main()

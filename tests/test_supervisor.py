"""Tests for supervisor — TDD approach."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, call

from lib.supervisor import (
    create_worktree, cleanup_worktree, build_prompt, execute_sprint,
    preflight, run, print_summary, resume, _shutdown_event,
    generate_completion_report, _check_pr_exists,
    _validate_evidence_verdicts, _validate_par_evidence,
    _validate_sprint_summary, _write_state, _verify_steps, REQUIRED_STEPS,
    _resolve_baseline_cmd, run_baseline_tests,
    run_holistic_review, _detect_codex, _run_single_reviewer,
    _build_holistic_prompt,
    _check_skip_requests,
    _read_sprint_progress,
    VALID_PASS_VERDICTS, REQUIRED_PAR_KEYS, REQUIRED_HOLISTIC_KEYS, REQUIRED_SUMMARY_KEYS,
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


def _make_popen_mock(returncode=0, stdout="", stderr=""):
    """Build a subprocess.Popen mock compatible with the polling loop in _attempt_sprint.

    poll() returns None once (loop body runs), then returncode (loop exits).
    communicate() returns (stdout, stderr).
    stdin supports write/close.
    """
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, returncode]
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.returncode = returncode
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.close = MagicMock()
    return mock_proc


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




class TestBuildPromptCharter(unittest.TestCase):
    """Tests for charter injection in build_prompt."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
            f.write(
                "Sprint {sprint_id}: {sprint_title}\n"
                "Plan: {sprint_plan}\n"
                "Claude: {claude_md}\n"
                "LLMs: {llms_txt}\n"
                "Charter: {charter}\n"
                "Branch: {branch}\n"
                "Complexity: {complexity}\n"
                "Tier: {implementation_tier}\n"
                "Model: {impl_model}\n"
                "Effort: {impl_effort}\n"
            )
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(os.path.join(self.tmpdir, "plans", "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff.\n")
        with open(os.path.join(self.tmpdir, "CLAUDE.md"), "w") as f:
            f.write("Rules")
        with open(os.path.join(self.tmpdir, "llms.txt"), "w") as f:
            f.write("Context")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_charter_injected_from_file(self):
        """Charter file contents should be injected into prompt."""
        os.makedirs(os.path.join(self.tmpdir, "docs"))
        charter_path = os.path.join(self.tmpdir, "docs", "charter.md")
        with open(charter_path, "w") as f:
            f.write("goal: Build X\nnon_negotiables:\n  - No hacks")
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        meta = {"charter_file": "docs/charter.md"}
        result = build_prompt(sprint, self.tmpdir, queue_metadata=meta)
        self.assertIn("goal: Build X", result)
        self.assertIn("No hacks", result)

    def test_charter_missing_file_fallback(self):
        """Missing charter file should inject comment placeholder."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        meta = {"charter_file": "docs/nonexistent-charter.md"}
        result = build_prompt(sprint, self.tmpdir, queue_metadata=meta)
        self.assertIn("No Autonomy Charter provided", result)

    def test_charter_no_metadata(self):
        """No metadata should inject comment placeholder."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("No Autonomy Charter provided", result)

    def test_charter_empty_metadata(self):
        """Empty metadata dict should inject comment placeholder."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir, queue_metadata={})
        self.assertIn("No Autonomy Charter provided", result)


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
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_success(self, mock_run, mock_popen, mock_create_wt, mock_cleanup_wt,
                                     mock_baseline, mock_par, mock_sleep):
        """Successful execution: claude returns JSON, exit 0, PR verified."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        # Claude subprocess via Popen
        claude_output = (
            "Working on sprint...\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":5,"failed":0},"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )
        mock_popen.return_value = _make_popen_mock(returncode=0, stdout=claude_output, stderr="")
        # gh pr view subprocess (still uses subprocess.run)
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_result

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["status"], "completed")
        self.assertEqual(sprint["pr"], "https://github.com/test/repo/pull/1")
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_failure_marks_failed(self, mock_run, mock_popen, mock_create_wt,
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

        # Claude subprocess fails via Popen
        mock_popen.return_value = _make_popen_mock(returncode=1, stdout="Error occurred", stderr="crash")

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertEqual(sprint["status"], "failed")
        mock_cleanup_wt.assert_called_once()

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_retry_on_failure(self, mock_run, mock_popen, mock_create_wt,
                                              mock_cleanup_wt, mock_baseline, mock_par,
                                              mock_sleep):
        """On failure with retries left, should retry and eventually succeed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        # First attempt fails (exit 1), retry succeeds
        success_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/2",'
            '"tests":{"passed":3,"failed":0},"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )
        mock_popen.side_effect = [
            _make_popen_mock(returncode=1, stdout="Error", stderr=""),
            _make_popen_mock(returncode=0, stdout=success_output, stderr=""),
        ]
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_result

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_json_parse_error_retries(self, mock_run, mock_popen,
                                                      mock_create_wt, mock_cleanup_wt,
                                                      mock_baseline, mock_par, mock_sleep):
        """Exit 0 but no valid JSON on last line should retry with appended instruction."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        sprint_data["retries"] = 0
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        # First: exit 0 but no JSON; Retry: exit 0 with proper JSON
        good_output = (
            "Done.\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/3",'
            '"tests":{"passed":1,"failed":0},"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )
        mock_popen.side_effect = [
            _make_popen_mock(returncode=0, stdout="Done but forgot JSON", stderr=""),
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
        ]
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_result

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        self.assertEqual(sprint["retries"], 1)

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor._validate_par_evidence")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    def test_execute_sprint_saves_output_log(self, mock_run, mock_popen, mock_create_wt,
                                              mock_cleanup_wt, mock_baseline, mock_par,
                                              mock_sleep):
        """Output should be saved to sprint-{id}-output.log."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        claude_output = (
            "Log line 1\n"
            '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1",'
            '"tests":{"passed":1,"failed":0},"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )
        mock_popen.return_value = _make_popen_mock(returncode=0, stdout=claude_output, stderr="")
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_result

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
        with open(os.path.join(self.tmpdir, ".holistic-review-evidence.json"), "w") as f:
            json.dump({
                "verdict": "APPROVE",
                "claude_product": "APPROVE",
                "technical_review": "APPROVE",
                "provider": "split-focus",
            }, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_three_sprints(self, mock_preflight, mock_execute, mock_holistic):
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
        with open(os.path.join(self.tmpdir, ".holistic-review-evidence.json"), "w") as f:
            json.dump({
                "verdict": "APPROVE",
                "claude_product": "APPROVE",
                "technical_review": "APPROVE",
                "provider": "split-focus",
            }, f)
        self.plan_path = os.path.join(self.tmpdir, "plans", "plan.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor._run_replan")
    @patch("lib.parallel._worker")
    @patch("lib.supervisor.preflight")
    def test_run_loop_parallel_two_independent(self, mock_preflight, mock_worker, mock_replan, mock_holistic):
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

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_replan_called_after_sprint(self, mock_preflight, mock_execute, mock_replan, mock_holistic):
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

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_no_replan_flag(self, mock_preflight, mock_execute, mock_replan, mock_holistic):
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

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor._run_replan")
    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight")
    def test_run_loop_no_plan_path_skips_replan(self, mock_preflight, mock_execute, mock_replan, mock_holistic):
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
            with open(os.path.join(tmpdir, ".holistic-review-evidence.json"), "w") as f:
                json.dump({
                    "verdict": "APPROVE",
                    "claude_product": "APPROVE",
                    "technical_review": "APPROVE",
                    "provider": "split-focus",
                }, f)

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

    def test_shutdown_skips_holistic_and_report_when_queue_incomplete(self):
        """Shutdown with pending sprints must not emit all_done or a completion report."""
        tmpdir = tempfile.mkdtemp()
        try:
            queue_path = os.path.join(tmpdir, "queue.json")
            os.makedirs(os.path.join(tmpdir, "templates"))
            with open(os.path.join(tmpdir, "templates", "supervisor-sprint-prompt.md"), "w") as f:
                f.write("Sprint {sprint_id}: {sprint_title}\n{sprint_plan}\n{claude_md}\n{llms_txt}\n{branch}\n{complexity}\n{implementation_tier}\n{impl_model}\n{impl_effort}\n")
            os.makedirs(os.path.join(tmpdir, "plans"))
            with open(os.path.join(tmpdir, "plans", "plan.md"), "w") as f:
                f.write("## Sprint 1\nStuff 1.\n\n## Sprint 2\nStuff 2.\n")
            with open(os.path.join(tmpdir, ".holistic-review-evidence.json"), "w") as f:
                json.dump({
                    "verdict": "APPROVE",
                    "claude_product": "APPROVE",
                    "technical_review": "APPROVE",
                    "provider": "split-focus",
                }, f)

            sprints = [
                _sprint(sid=1, plan_file="plans/plan.md#sprint-1"),
                _sprint(sid=2, plan_file="plans/plan.md#sprint-2", depends_on=[1]),
            ]
            q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
            q.save(queue_path)

            def execute_side_effect(sprint, queue, queue_path, cp_dir, repo_root, **kwargs):
                queue.mark_completed(sprint["id"], f"https://github.com/pr/{sprint['id']}")
                queue.save(queue_path)
                supervisor_module._shutdown_event.set()
                return {"sprint_id": sprint["id"], "status": "completed"}

            notifier = MagicMock()

            import io
            from unittest.mock import patch as _patch
            with patch("lib.supervisor.preflight", return_value=(True, [])):
                with patch("lib.supervisor.execute_sprint", side_effect=execute_side_effect):
                    with _patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                        run(queue_path, repo_root=tmpdir, notifier=notifier)
                        output = mock_stdout.getvalue()

            self.assertNotIn("# Completion Report", output)
            notifier.notify_holistic_review_start.assert_not_called()
            notifier.notify_holistic_review_complete.assert_not_called()
            notifier.notify_all_done.assert_not_called()
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
            "claude_product": "APPROVE",
            "technical_review": "APPROVE",
            "provider": "split-focus",
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
                "par": {"claude_product": "ACCEPTED", "technical_review": "APPROVE", "provider": "codex"},
            },
        })
        save_checkpoint(self.cp_dir, 2, {
            "sprint_id": 2, "status": "completed",
            "summary": {
                "tests": {"passed": 10, "failed": 0},
                "par": {"claude_product": "ACCEPTED", "technical_review": "APPROVE", "provider": "codex"},
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
        self.assertIn("Claude-Product=ACCEPTED", report)
        self.assertIn("Technical-Review=APPROVE", report)
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
            "summary": {"tests": {"passed": 3, "failed": 0}, "par": {"claude_product": "ACCEPTED", "technical_review": "APPROVE", "provider": "codex"}},
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
        """Valid 2-key PAR with APPROVE/ACCEPTED verdicts passes."""
        data = {
            "claude_product": "ACCEPTED",
            "technical_review": "APPROVE",
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
            "claude_product": "APPROVE",
            # missing technical_review
        }
        valid, errors = _validate_evidence_verdicts(data, REQUIRED_PAR_KEYS)
        self.assertFalse(valid)
        self.assertEqual(len(errors), 1)  # 1 missing key

    def test_validate_evidence_invalid_verdict(self):
        """PAR evidence with invalid verdict value returns error."""
        data = {
            "claude_product": "MAYBE",
            "technical_review": "APPROVE",
        }
        valid, errors = _validate_evidence_verdicts(data, REQUIRED_PAR_KEYS)
        self.assertFalse(valid)
        self.assertTrue(any("MAYBE" in e for e in errors))

    def test_validate_evidence_frontend_required(self):
        """With require_frontend=True and all 3 keys present, passes."""
        evidence = {
            "claude_product": "ACCEPTED",
            "technical_review": "APPROVE",
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
            "claude_product": "ACCEPTED",
            "technical_review": "APPROVE",
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
            "par": {"claude_product": "ACCEPTED", "technical_review": "APPROVE"},
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
        # Verify subprocess.run was called with the queue baseline_cmd split as list
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][0], ["make", "test"])
        self.assertFalse(call_args[1].get("shell", True))


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
            '"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_par_integration_retry_separate_counter(self, mock_par, mock_run, mock_popen,
                                                     mock_baseline, mock_create_wt,
                                                     mock_cleanup_wt, mock_sleep):
        """PAR retry uses separate counter from Claude retry. PAR fail doesn't consume Claude retries."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 2
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)

        good_output = "Done.\n" + self._good_summary_json()
        # Claude calls: 1st success, 2nd success (PAR retry re-invokes Claude)
        mock_popen.side_effect = [
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
        ]
        gh_result = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_result

        # First PAR call fails, second PAR call passes
        mock_par.side_effect = [
            (False, {}, ["PAR: missing key 'technical_review'"]),
            (True, {"claude_product": "APPROVE",
                     "technical_review": "APPROVE"}, []),
        ]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")
        # Claude retry counter should still be 0 — PAR retries are separate
        # The sprint should have succeeded after 1 PAR retry

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_par_integration_max_retries_fails(self, mock_par, mock_run, mock_popen,
                                                mock_baseline, mock_create_wt,
                                                mock_cleanup_wt, mock_sleep):
        """2 PAR retries exceeded -> mark_failed."""
        sprint_data = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint_data["max_retries"] = 5  # High Claude retries — PAR should fail first
        q = self._make_queue([sprint_data])
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)

        good_output = "Done.\n" + self._good_summary_json()
        # 3 Claude invocations (initial + 2 PAR retries)
        mock_popen.side_effect = [
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
            _make_popen_mock(returncode=0, stdout=good_output, stderr=""),
        ]

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
            '"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_pr_validation_retry_3_times(self, mock_par, mock_run, mock_popen, mock_baseline,
                                          mock_create_wt, mock_cleanup_wt, mock_sleep):
        """Transient gh pr view failure retried up to 3 times, then succeeds."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        mock_popen.return_value = _make_popen_mock(returncode=0, stdout=good_output, stderr="")
        gh_fail = MagicMock(returncode=1, stdout="", stderr="network error")
        gh_ok = MagicMock(returncode=0, stdout="OPEN")
        # 2 gh fails, 1 gh success
        mock_run.side_effect = [gh_fail, gh_fail, gh_ok]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "completed")

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_pr_validation_hard_fail_after_retries(self, mock_par, mock_run, mock_popen,
                                                    mock_baseline, mock_create_wt,
                                                    mock_cleanup_wt, mock_sleep):
        """3 gh pr view failures -> mark_failed (NOT re-invoke Claude)."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        mock_popen.return_value = _make_popen_mock(returncode=0, stdout=good_output, stderr="")
        gh_fail = MagicMock(returncode=1, stdout="", stderr="network error")
        # 3 gh failures
        mock_run.side_effect = [gh_fail, gh_fail, gh_fail]

        cp = execute_sprint(sprint, q, self.queue_path, self.cp_dir, self.tmpdir)

        self.assertEqual(cp["status"], "failed")
        self.assertIn("PR", sprint.get("error_log", ""))
        # Popen should only be called ONCE — no re-invocation for gh failures
        self.assertEqual(mock_popen.call_count, 1)


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
            '"par":{"claude_product":"ACCEPTED","technical_review":"APPROVE","provider":"codex"}}'
        )

    @patch("lib.supervisor.time.sleep")
    @patch("lib.supervisor.cleanup_worktree")
    @patch("lib.supervisor.create_worktree")
    @patch("lib.supervisor.run_baseline_tests")
    @patch("lib.supervisor.subprocess.Popen")
    @patch("lib.supervisor.subprocess.run")
    @patch("lib.supervisor._validate_par_evidence")
    def test_milestone_writes_in_checkpoint(self, mock_par, mock_run, mock_popen,
                                             mock_baseline, mock_create_wt,
                                             mock_cleanup_wt, mock_sleep):
        """Full success path writes all milestones to checkpoint."""
        q = self._make_queue()
        sprint = q.sprints[0]
        wt_path = os.path.join(self.tmpdir, ".worktrees", "sprint-1")
        mock_create_wt.return_value = wt_path
        mock_baseline.return_value = (True, "ok", False)
        mock_par.return_value = (True, {"claude_product": "APPROVE",
                                         "technical_review": "APPROVE"}, [])

        good_output = "Done.\n" + self._good_summary_json()
        mock_popen.return_value = _make_popen_mock(returncode=0, stdout=good_output, stderr="")
        gh_ok = MagicMock(returncode=0, stdout="OPEN")
        mock_run.return_value = gh_ok

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
            "claude_product": "APPROVE",
            "technical_review": "APPROVE",
            "provider": "split-focus",
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

    @patch("lib.supervisor.run_holistic_review", return_value=False)
    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_blocks_report_on_holistic_failure(self, mock_execute, mock_preflight, mock_holistic):
        """Integration: failed holistic review -> BLOCKED, no report."""
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
        mock_holistic.assert_called_once()

        # Holistic checkpoint should exist with pending status before review dispatch.
        # The mocked review does not overwrite it with a final checkpoint.
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
            json.dump({"verdict": "APPROVE", "timestamp": "2026-01-01T00:00:00Z", "sprint_prs": ["https://github.com/test/repo/pull/1"], "claude_product": "APPROVE", "technical_review": "APPROVE", "provider": "split-focus"}, f)

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
            json.dump({"verdict": "APPROVE", "sprint_prs": ["https://github.com/test/repo/pull/1"], "claude_product": "APPROVE", "technical_review": "APPROVE", "provider": "split-focus"}, f)

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


class TestHolisticReviewDispatch(unittest.TestCase):
    """Sprint 4b: run_holistic_review() — 2 parallel reviewers, fix cycle, evidence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(self.cp_dir, exist_ok=True)
        self.plan_path = os.path.join(self.tmpdir, "plan.md")
        with open(self.plan_path, "w") as f:
            f.write("# Plan\n## Sprint 1\nDo stuff.")
        self.evidence_path = os.path.join(self.tmpdir, ".holistic-review-evidence.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints=None):
        if sprints is None:
            sprints = [
                _sprint(sid=1, title="Setup", status="completed", branch="feat/setup-sprint-1"),
                _sprint(sid=2, title="Build", status="completed", branch="feat/build-sprint-2"),
            ]
            sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
            sprints[1]["pr"] = "https://github.com/test/repo/pull/2"
        q = SprintQueue("test-feature", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    def _mock_approve_result(self, *args, **kwargs):
        """Return a subprocess result that looks like APPROVE."""
        return MagicMock(
            returncode=0,
            stdout='Review looks good.\n{"verdict": "APPROVE"}',
            stderr="",
        )

    def _mock_request_changes_result(self, *args, **kwargs):
        """Return a subprocess result that looks like REQUEST_CHANGES."""
        return MagicMock(
            returncode=0,
            stdout=(
                'Issues found.\n'
                '{"verdict": "REQUEST_CHANGES", "findings": '
                '[{"severity": "HIGH", "description": "Missing error handling"}]}'
            ),
            stderr="",
        )

    @patch("lib.supervisor.subprocess.run")
    def test_single_reviewer_parses_verdict_and_findings_json(self, mock_run):
        """Reviewer JSON payloads should preserve verdict and findings."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                'Issues found.\n'
                '{"verdict": "REQUEST_CHANGES", "findings": '
                '[{"severity": "HIGH", "description": "Missing error handling"}]}'
            ),
            stderr="",
        )

        result = _run_single_reviewer(
            "technical_review",
            ["claude", "-p", "--verbose"],
            "review prompt",
            {},
            60,
        )

        self.assertEqual(result["verdict"], "REQUEST_CHANGES")
        self.assertEqual(
            result["findings"],
            [{"severity": "HIGH", "description": "Missing error handling"}],
        )
        self.assertIsNone(result["error"])
        self.assertEqual(mock_run.call_args.kwargs["cwd"], None)

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_reviewer_subprocesses_run_from_repo_root(self, mock_run, mock_codex, mock_branch):
        """Reviewer sessions should run with cwd=repo_root so they inspect the right repo."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff --git a/f.py\n+line", stderr="")
        approve_result = MagicMock(
            returncode=0,
            stdout='Review OK.\n{"verdict": "APPROVE"}',
            stderr="",
        )
        mock_run.side_effect = [diff_result, diff_result,
                                approve_result, approve_result]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60,
        )

        self.assertTrue(result)
        for call in mock_run.call_args_list[2:]:
            self.assertEqual(call.kwargs.get("cwd"), self.tmpdir)

    def _mock_diff_result(self, *args, **kwargs):
        """Return a subprocess result for git diff."""
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and "diff" in cmd:
            return MagicMock(returncode=0, stdout="diff --git a/file.py b/file.py\n+line", stderr="")
        # codex --version check
        if isinstance(cmd, list) and "codex" in cmd:
            return MagicMock(returncode=1, stdout="", stderr="not found")
        return MagicMock(returncode=0, stdout="", stderr="")

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=True)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_dispatches_2_reviewers_with_codex(self, mock_run, mock_codex, mock_branch):
        """With Codex available: 1 claude -p (product) + 1 codex exec (technical) calls."""
        q = self._make_queue()

        # Set up side_effect: first calls are git diff (2 sprints), then 2 reviewers
        diff_result = MagicMock(returncode=0, stdout="diff --git a/f.py\n+line", stderr="")
        approve_result = MagicMock(
            returncode=0,
            stdout='Review OK.\n{"verdict": "APPROVE"}',
            stderr="",
        )
        # 2 git diffs + 2 reviewers
        mock_run.side_effect = [diff_result, diff_result,
                                approve_result, approve_result]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60,
        )

        self.assertTrue(result)
        # Count subprocess calls: 2 git diff + 2 reviewers = 4
        self.assertEqual(mock_run.call_count, 4)

        # Verify the evidence file was written
        self.assertTrue(os.path.exists(self.evidence_path))

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_dispatches_2_splitfocus_without_codex(self, mock_run, mock_codex, mock_branch):
        """Without Codex: 2 claude -p calls (split-focus)."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff --git a/f.py\n+line", stderr="")
        approve_result = MagicMock(
            returncode=0,
            stdout='Review OK.\n{"verdict": "APPROVE"}',
            stderr="",
        )
        mock_run.side_effect = [diff_result, diff_result,
                                approve_result, approve_result]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60,
        )

        self.assertTrue(result)
        # 2 git diff + 2 reviewers = 4
        self.assertEqual(mock_run.call_count, 4)

        # All 2 reviewer calls should be claude (no codex)
        reviewer_calls = mock_run.call_args_list[2:]
        for c in reviewer_calls:
            cmd = c[0][0] if c[0] else c[1].get("args", [])
            self.assertEqual(cmd[0], "claude",
                             f"Expected claude but got {cmd[0]} — all should be claude without Codex")

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_writes_evidence_on_approve(self, mock_run, mock_codex, mock_branch):
        """All 2 APPROVE -> evidence file created with correct format."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff content", stderr="")
        approve_result = MagicMock(
            returncode=0,
            stdout='All good.\n{"verdict": "APPROVE"}',
            stderr="",
        )
        mock_run.side_effect = [diff_result, diff_result,
                                approve_result, approve_result]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60,
        )

        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.evidence_path))

        with open(self.evidence_path) as f:
            evidence = json.load(f)

        # Verify structure
        self.assertEqual(evidence["verdict"], "APPROVE")
        self.assertIn("timestamp", evidence)
        self.assertIn("claude_product", evidence)
        self.assertIn("technical_review", evidence)
        self.assertIn("provider", evidence)
        self.assertIn("sprint_prs", evidence)
        self.assertIn("findings_resolved", evidence)

        # Verify both reviewer keys present with APPROVE
        for key in REQUIRED_HOLISTIC_KEYS:
            self.assertIn(key, evidence)
            self.assertEqual(evidence[key], "APPROVE")

        # Verify sprint PRs
        self.assertEqual(len(evidence["sprint_prs"]), 2)
        self.assertIn("https://github.com/test/repo/pull/1", evidence["sprint_prs"])

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_retries_on_request_changes(self, mock_run, mock_codex, mock_branch):
        """1 reviewer returns REQUEST_CHANGES -> retry triggered."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff content", stderr="")
        approve = MagicMock(returncode=0, stdout='OK\n{"verdict": "APPROVE"}', stderr="")
        request_changes = MagicMock(
            returncode=0,
            stdout='Bad\n{"verdict": "REQUEST_CHANGES", "findings": [{"severity": "HIGH", "description": "bug"}]}',
            stderr="",
        )

        # Attempt 1: 2 diffs + 1 approve + 1 request_changes
        # Then fixer session (1 call)
        # Attempt 2: 1 re-run reviewer (approve this time)
        mock_run.side_effect = [
            # git diffs
            diff_result, diff_result,
            # 2 reviewers (attempt 1) — one fails
            approve, request_changes,
            # fixer session
            MagicMock(returncode=0, stdout="Fixed.", stderr=""),
            # re-run failing reviewer (attempt 2)
            approve,
        ]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60, max_retries=2,
        )

        self.assertTrue(result)
        # Should have more calls than initial 4 (2 diffs + 2 reviewers)
        self.assertGreater(mock_run.call_count, 4)

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_returns_false_on_max_retries(self, mock_run, mock_codex, mock_branch):
        """Max retries exceeded -> returns False."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff content", stderr="")
        approve = MagicMock(returncode=0, stdout='OK\n{"verdict": "APPROVE"}', stderr="")
        request_changes = MagicMock(
            returncode=0,
            stdout='Bad\n{"verdict": "REQUEST_CHANGES", "findings": [{"severity": "CRITICAL", "description": "major bug"}]}',
            stderr="",
        )
        fixer_ok = MagicMock(returncode=0, stdout="Attempted fix.", stderr="")

        # max_retries=1 means: attempt 0 (initial) + attempt 1 (retry) = 2 total
        # Attempt 0: 2 diffs + 2 reviewers (1 fails)
        # Fixer + Attempt 1: re-run 1 reviewer (still fails)
        mock_run.side_effect = [
            # git diffs
            diff_result, diff_result,
            # 2 reviewers (attempt 0) — one always fails
            approve, request_changes,
            # fixer
            fixer_ok,
            # re-run failing reviewer (attempt 1) — still fails
            request_changes,
        ]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60, max_retries=1,
        )

        self.assertFalse(result)
        # Evidence file should NOT exist
        self.assertFalse(os.path.exists(self.evidence_path))

        # Checkpoint should show failed
        holistic_cp_path = os.path.join(self.cp_dir, "sprint-holistic.json")
        self.assertTrue(os.path.exists(holistic_cp_path))
        with open(holistic_cp_path) as f:
            cp = json.load(f)
        self.assertEqual(cp["status"], "failed")

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_fix_cycle_reruns_only_failing(self, mock_run, mock_codex, mock_branch):
        """Only failing reviewers re-run in retry, not all 2."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff content", stderr="")
        approve = MagicMock(returncode=0, stdout='OK\n{"verdict": "APPROVE"}', stderr="")
        request_changes = MagicMock(
            returncode=0,
            stdout='Bad\n{"verdict": "REQUEST_CHANGES", "findings": [{"severity": "HIGH", "description": "issue"}]}',
            stderr="",
        )
        fixer_ok = MagicMock(returncode=0, stdout="Fixed.", stderr="")

        # Track calls to identify which reviewers were re-run
        call_log = []
        original_run = subprocess.run

        def tracking_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            call_log.append(cmd)
            # Return results in order
            return mock_run(*args, **kwargs)

        # Attempt 0: 2 diffs + 2 reviewers (last one fails = technical_review)
        # Fixer session
        # Attempt 1: only the failing reviewer re-runs (1 call, not 2)
        mock_run.side_effect = [
            # git diffs
            diff_result, diff_result,
            # 2 reviewers attempt 0
            approve, request_changes,
            # fixer session
            fixer_ok,
            # Only 1 re-run (the failing reviewer)
            approve,
        ]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60, max_retries=2,
        )

        self.assertTrue(result)

        # Total calls: 2 (diffs) + 2 (initial reviewers) + 1 (fixer) + 1 (re-run) = 6
        # NOT 2 + 2 + 1 + 2 = 7 (if all were re-run)
        self.assertEqual(mock_run.call_count, 6,
                         f"Expected 6 subprocess calls (2 diff + 2 initial + 1 fixer + 1 re-run), "
                         f"got {mock_run.call_count}")

    @patch("lib.supervisor.run_holistic_review")
    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_run_full_flow_with_all_gates(self, mock_execute, mock_preflight, mock_holistic):
        """Integration: run() dispatches holistic review and generates report on success."""
        sprints = [
            _sprint(sid=1, title="Setup", status="completed"),
            _sprint(sid=2, title="Build", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        sprints[1]["pr"] = "https://github.com/test/repo/pull/2"
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)

        mock_preflight.return_value = (True, [])

        # Holistic review writes evidence and returns True
        def holistic_side_effect(queue, queue_path, repo_root, plan_path,
                                  checkpoints_dir, timeout=1800, notifier=None,
                                  max_retries=2):
            evidence = {
                "timestamp": "2026-01-01T00:00:00Z",
                "verdict": "APPROVE",
                "claude_product": "APPROVE",
                "technical_review": "APPROVE",
                "provider": "split-focus",
                "sprint_prs": [],
                "findings_resolved": 0,
            }
            ev_path = os.path.join(
                os.path.dirname(checkpoints_dir),
                ".holistic-review-evidence.json",
            )
            with open(ev_path, "w") as f:
                json.dump(evidence, f)
            return True

        mock_holistic.side_effect = holistic_side_effect

        # Create checkpoints for sprints so report can read them
        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        save_checkpoint(cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })
        save_checkpoint(cp_dir, 2, {
            "sprint_id": 2, "status": "completed", "summary": {},
        })

        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            run(self.queue_path, repo_root=self.tmpdir)
            output = mock_stdout.getvalue()

        # Holistic review should have been called
        mock_holistic.assert_called_once()

        # Report should be generated (not blocked)
        self.assertNotIn("BLOCKED", output)
        self.assertIn("# Completion Report", output)
        self.assertIn("Setup", output)
        self.assertIn("Build", output)


class TestFix1StaleHolisticEvidence(unittest.TestCase):
    """Fix 1: Stale holistic evidence reuse — sprint_prs validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(self.cp_dir, exist_ok=True)
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

    @patch("lib.supervisor.run_holistic_review", return_value=True)
    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_stale_evidence_triggers_fresh_review(
        self, mock_execute, mock_preflight, mock_holistic
    ):
        """Cached evidence with mismatched sprint_prs is invalidated and fresh review runs."""
        sprints = [_sprint(sid=1, title="Setup", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        # Evidence has sprint_prs that do NOT match current queue's PR
        evidence_path = os.path.join(self.tmpdir, ".holistic-review-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump({
                "verdict": "APPROVE",
                "timestamp": "2026-01-01T00:00:00Z",
                "sprint_prs": ["https://github.com/test/repo/pull/STALE"],
                "claude_product": "APPROVE",
                "technical_review": "APPROVE",
                "provider": "split-focus",
            }, f)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO):
            run(self.queue_path, repo_root=self.tmpdir)

        # Fresh holistic review should have been dispatched
        mock_holistic.assert_called_once()

    @patch("lib.supervisor.run_holistic_review")
    @patch("lib.supervisor.preflight")
    @patch("lib.supervisor.execute_sprint")
    def test_valid_evidence_with_matching_sprint_prs_skips_review(
        self, mock_execute, mock_preflight, mock_holistic
    ):
        """Cached evidence matching current sprint_prs is accepted — no fresh review."""
        sprints = [_sprint(sid=1, title="Setup", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = self._make_queue(sprints)
        mock_preflight.return_value = (True, [])

        evidence_path = os.path.join(self.tmpdir, ".holistic-review-evidence.json")
        with open(evidence_path, "w") as f:
            json.dump({
                "verdict": "APPROVE",
                "timestamp": "2026-01-01T00:00:00Z",
                "sprint_prs": ["https://github.com/test/repo/pull/1"],
                "claude_product": "APPROVE",
                "technical_review": "APPROVE",
                "provider": "split-focus",
            }, f)

        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        import io
        from unittest.mock import patch as _patch
        with _patch("sys.stdout", new_callable=io.StringIO):
            run(self.queue_path, repo_root=self.tmpdir)

        # Should NOT dispatch a fresh review (evidence was valid and matched)
        mock_holistic.assert_not_called()


class TestFix2DetectDefaultBranch(unittest.TestCase):
    """Fix 2: _detect_default_branch() helper and use in run_holistic_review."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("lib.supervisor.subprocess.run")
    def test_detect_default_branch_from_origin_head(self, mock_run):
        """Parses branch name from git symbolic-ref output."""
        from lib.supervisor import _detect_default_branch
        mock_run.return_value = MagicMock(
            returncode=0, stdout="refs/remotes/origin/main\n"
        )
        branch = _detect_default_branch(self.tmpdir)
        self.assertEqual(branch, "main")

    @patch("lib.supervisor.subprocess.run")
    def test_detect_default_branch_master(self, mock_run):
        """Returns 'master' when origin HEAD points to master."""
        from lib.supervisor import _detect_default_branch
        mock_run.return_value = MagicMock(
            returncode=0, stdout="refs/remotes/origin/master\n"
        )
        branch = _detect_default_branch(self.tmpdir)
        self.assertEqual(branch, "master")

    @patch("lib.supervisor.subprocess.run")
    def test_detect_default_branch_develop(self, mock_run):
        """Returns 'develop' when origin HEAD points to develop."""
        from lib.supervisor import _detect_default_branch
        mock_run.return_value = MagicMock(
            returncode=0, stdout="refs/remotes/origin/develop\n"
        )
        branch = _detect_default_branch(self.tmpdir)
        self.assertEqual(branch, "develop")

    @patch("lib.supervisor.subprocess.run")
    def test_detect_default_branch_falls_back_to_main_on_error(self, mock_run):
        """Falls back to 'main' when git command fails."""
        from lib.supervisor import _detect_default_branch
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        branch = _detect_default_branch(self.tmpdir)
        self.assertEqual(branch, "main")

    @patch("lib.supervisor.subprocess.run")
    def test_detect_default_branch_falls_back_on_exception(self, mock_run):
        """Falls back to 'main' on subprocess exception."""
        from lib.supervisor import _detect_default_branch
        mock_run.side_effect = Exception("git not found")
        branch = _detect_default_branch(self.tmpdir)
        self.assertEqual(branch, "main")

    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor._detect_default_branch", return_value="develop")
    @patch("lib.supervisor.subprocess.run")
    def test_holistic_review_uses_detected_branch_in_diff(
        self, mock_run, mock_branch, mock_codex
    ):
        """run_holistic_review uses _detect_default_branch for git diff."""
        cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(cp_dir, exist_ok=True)
        sprints = [_sprint(sid=1, status="completed", branch="feat/s1")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = SprintQueue("t", "2026-01-01T00:00:00Z", sprints)
        queue_path = os.path.join(self.tmpdir, "queue.json")
        q.save(queue_path)

        approve_output = '{"verdict": "APPROVE"}'
        approve = MagicMock(returncode=0, stdout=approve_output, stderr="")
        diff = MagicMock(returncode=0, stdout="diff", stderr="")
        mock_run.side_effect = [diff, approve, approve]

        run_holistic_review(q, queue_path, self.tmpdir, None, cp_dir, timeout=60)

        # First subprocess call should be git diff with "develop...feat/s1"
        first_call_args = mock_run.call_args_list[0][0][0]
        self.assertIn("git", first_call_args)
        self.assertIn("diff", first_call_args)
        self.assertIn("develop...feat/s1", first_call_args)


class TestFix3ShellFalseBaselineCmd(unittest.TestCase):
    """Fix 3: run_baseline_tests uses shlex.split + shell=False for user-supplied commands."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, baseline_cmd=None):
        return SprintQueue("test", "2026-01-01T00:00:00Z", [], baseline_cmd=baseline_cmd)

    @patch("lib.supervisor.subprocess.run")
    def test_string_cmd_split_as_list_shell_false(self, mock_run):
        """String baseline_cmd is split with shlex and passed as list with shell=False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        sprint = {"baseline_cmd": "python -m pytest --tb=short -q"}
        q = self._make_queue()
        run_baseline_tests(self.tmpdir, sprint, q)
        call_args = mock_run.call_args
        cmd_arg = call_args[0][0]
        self.assertIsInstance(cmd_arg, list, "Command should be a list, not a string")
        self.assertEqual(cmd_arg, ["python", "-m", "pytest", "--tb=short", "-q"])
        self.assertFalse(call_args[1].get("shell", True), "shell should be False")

    @patch("lib.supervisor.subprocess.run")
    def test_list_cmd_passed_directly_shell_false(self, mock_run):
        """List baseline_cmd is passed as-is with shell=False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        sprint = {"baseline_cmd": ["python", "-m", "pytest"]}
        q = self._make_queue()
        run_baseline_tests(self.tmpdir, sprint, q)
        call_args = mock_run.call_args
        cmd_arg = call_args[0][0]
        self.assertIsInstance(cmd_arg, list)
        self.assertEqual(cmd_arg, ["python", "-m", "pytest"])
        self.assertFalse(call_args[1].get("shell", True), "shell should be False")

    @patch("lib.supervisor.subprocess.run")
    def test_npm_test_command_split_correctly(self, mock_run):
        """'npm test' heuristic produces ['npm', 'test'] with shell=False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        sprint = {"baseline_cmd": "npm test"}
        q = self._make_queue()
        run_baseline_tests(self.tmpdir, sprint, q)
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][0], ["npm", "test"])
        self.assertFalse(call_args[1].get("shell", True))


class TestFix4NpmPlaceholderFilter(unittest.TestCase):
    """Fix 4: _resolve_baseline_cmd filters npm placeholder test script."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self):
        return SprintQueue("test", "2026-01-01T00:00:00Z", [])

    def test_npm_placeholder_no_test_specified_returns_none(self):
        """npm default 'echo Error: no test specified && exit 1' is treated as no runner."""
        with open(os.path.join(self.tmpdir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}, f)
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertIsNone(cmd)

    def test_npm_placeholder_variant_error_no_test_returns_none(self):
        """Another common variant of npm placeholder is filtered."""
        with open(os.path.join(self.tmpdir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "Error: no test"}}, f)
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertIsNone(cmd)

    def test_real_test_script_not_filtered(self):
        """A real test script ('jest', 'mocha', etc.) is NOT filtered."""
        with open(os.path.join(self.tmpdir, "package.json"), "w") as f:
            json.dump({"scripts": {"test": "jest --coverage"}}, f)
        sprint = {}
        q = self._make_queue()
        cmd = _resolve_baseline_cmd(self.tmpdir, sprint, q)
        self.assertEqual(cmd, "npm test")


class TestFix5HolisticFailurePersistsFindings(unittest.TestCase):
    """Fix 5: Failed holistic review checkpoint includes last_findings."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(self.cp_dir, exist_ok=True)
        self.plan_path = os.path.join(self.tmpdir, "plan.md")
        with open(self.plan_path, "w") as f:
            f.write("# Plan\n## Sprint 1\nDo stuff.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self):
        sprints = [_sprint(sid=1, status="completed", branch="feat/setup-sprint-1")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/1"
        q = SprintQueue("test-feature", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.supervisor._detect_default_branch", return_value="main")
    @patch("lib.supervisor._detect_codex", return_value=False)
    @patch("lib.supervisor.subprocess.run")
    def test_failed_holistic_checkpoint_has_last_findings(self, mock_run, mock_codex, mock_branch):
        """When holistic review fails after max retries, checkpoint includes last_findings."""
        q = self._make_queue()

        diff_result = MagicMock(returncode=0, stdout="diff content", stderr="")
        approve = MagicMock(returncode=0, stdout='OK\n{"verdict": "APPROVE"}', stderr="")
        request_changes = MagicMock(
            returncode=0,
            stdout='Bad\n{"verdict": "REQUEST_CHANGES", "findings": [{"severity": "HIGH", "description": "cross-module data race"}]}',
            stderr="",
        )
        fixer_ok = MagicMock(returncode=0, stdout="Fixed.", stderr="")

        mock_run.side_effect = [
            diff_result,
            approve, request_changes,
            fixer_ok,
            request_changes,
        ]

        result = run_holistic_review(
            q, self.queue_path, self.tmpdir, self.plan_path, self.cp_dir,
            timeout=60, max_retries=1,
        )

        self.assertFalse(result)

        holistic_cp_path = os.path.join(self.cp_dir, "sprint-holistic.json")
        with open(holistic_cp_path) as f:
            cp = json.load(f)

        self.assertEqual(cp["status"], "failed")
        self.assertIn("last_findings", cp)
        self.assertIsInstance(cp["last_findings"], list)
        self.assertTrue(len(cp["last_findings"]) > 0)
        # Check finding content is included
        findings_text = json.dumps(cp["last_findings"])
        self.assertIn("cross-module data race", findings_text)


class TestFix6BaselineStatusInPrompt(unittest.TestCase):
    """Fix 6: build_prompt uses {baseline_status} placeholder from template."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.tmpdir, "templates")
        os.makedirs(self.templates_dir)
        self.plans_dir = os.path.join(self.tmpdir, "plans")
        os.makedirs(self.plans_dir)
        with open(os.path.join(self.plans_dir, "plan.md"), "w") as f:
            f.write("## Sprint 1\nDo stuff.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_template(self, content):
        with open(os.path.join(self.templates_dir, "supervisor-sprint-prompt.md"), "w") as f:
            f.write(content)

    def test_baseline_status_passed_inserted_when_run(self):
        """When baseline ran and passed, build_prompt inserts 'passed' status text."""
        self._write_template(
            "Sprint {sprint_id}: {sprint_title}\n"
            "{baseline_status}\n"
        )
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["baseline_skipped"] = False
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Baseline tests passed", result)
        self.assertNotIn("{baseline_status}", result)

    def test_baseline_status_skipped_inserted_when_not_run(self):
        """When baseline was skipped, build_prompt inserts caution text."""
        self._write_template(
            "Sprint {sprint_id}: {sprint_title}\n"
            "{baseline_status}\n"
        )
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        sprint["baseline_skipped"] = True
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Baseline tests were not available", result)
        self.assertNotIn("{baseline_status}", result)

    def test_baseline_status_default_when_key_absent(self):
        """When sprint has no baseline_skipped key, default to 'passed' text."""
        self._write_template(
            "Sprint {sprint_id}: {sprint_title}\n"
            "{baseline_status}\n"
        )
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        # No baseline_skipped key set
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Baseline tests passed", result)

    def test_template_without_baseline_status_placeholder_still_works(self):
        """Template without {baseline_status} still renders without error."""
        self._write_template(
            "Sprint {sprint_id}: {sprint_title}\n"
        )
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Sprint 1", result)


class TestWriteState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints=None):
        if sprints is None:
            sprints = [_sprint(1, status="completed"), _sprint(2, status="in_progress")]
        return SprintQueue("test", "2026-01-01", sprints)

    def test_write_state_creates_file(self):
        q = self._make_queue()
        _write_state(self.tmpdir, phase=2, sprint=1, stage="setup", queue=q)
        state_path = os.path.join(self.tmpdir, ".superflow-state.json")
        self.assertTrue(os.path.exists(state_path))
        with open(state_path) as f:
            state = json.load(f)
        self.assertEqual(state["version"], 1)
        self.assertEqual(state["phase"], 2)
        self.assertEqual(state["sprint"], 1)
        self.assertEqual(state["stage"], "setup")
        self.assertEqual(state["tasks_done"], [1])
        self.assertEqual(state["tasks_total"], 2)

    def test_write_state_atomic(self):
        q = self._make_queue()
        _write_state(self.tmpdir, phase=2, sprint=1, stage="setup", queue=q)
        tmp_path = os.path.join(self.tmpdir, ".superflow-state.json.tmp")
        self.assertFalse(os.path.exists(tmp_path))

    def test_write_state_updates_on_transition(self):
        q = self._make_queue()
        _write_state(self.tmpdir, phase=2, sprint=1, stage="setup", queue=q)
        _write_state(self.tmpdir, phase=2, sprint=1, stage="implementation", queue=q)
        with open(os.path.join(self.tmpdir, ".superflow-state.json")) as f:
            state = json.load(f)
        self.assertEqual(state["stage"], "implementation")
        self.assertEqual(state["stage_index"], 1)


class TestVerifySteps(unittest.TestCase):
    def test_all_present(self):
        summary = {"steps_completed": list(REQUIRED_STEPS)}
        self.assertEqual(_verify_steps(summary), [])

    def test_missing(self):
        summary = {"steps_completed": ["baseline_tests", "implementation"]}
        missing = _verify_steps(summary)
        self.assertIn("par", missing)
        self.assertIn("pr_created", missing)

    def test_backward_compatible(self):
        summary = {}
        missing = _verify_steps(summary)
        self.assertEqual(sorted(missing), sorted(REQUIRED_STEPS))


class TestGenerateCompletionReport(unittest.TestCase):
    """Focused tests for generate_completion_report() covering sprint blocks,
    PR URLs, test counts, PAR verdicts, holistic verdicts, missing checkpoints,
    and file output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        self._create_holistic_evidence()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_holistic_evidence(self, verdicts=None):
        """Create .holistic-review-evidence.json in parent of cp_dir."""
        evidence_path = os.path.join(
            os.path.dirname(self.cp_dir),
            ".holistic-review-evidence.json",
        )
        evidence = verdicts or {
            "timestamp": "2026-01-01T00:00:00Z",
            "claude_product": "APPROVE",
            "technical_review": "APPROVE",
            "provider": "split-focus",
        }
        with open(evidence_path, "w") as f:
            json.dump(evidence, f)

    def _make_queue(self, sprints):
        return SprintQueue("test-feature", "2026-01-01T00:00:00Z", sprints)

    def test_report_contains_all_sprint_blocks(self):
        """Each completed sprint appears as its own '## Sprint N: Title' block."""
        sprints = [
            _sprint(sid=1, title="Auth Module", status="completed"),
            _sprint(sid=2, title="API Layer", status="completed"),
            _sprint(sid=3, title="Frontend", status="completed"),
        ]
        q = self._make_queue(sprints)
        # Create minimal checkpoints for each sprint
        for s in sprints:
            save_checkpoint(self.cp_dir, s["id"], {
                "sprint_id": s["id"], "status": "completed", "summary": {},
            })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("## Sprint 1: Auth Module", report)
        self.assertIn("## Sprint 2: API Layer", report)
        self.assertIn("## Sprint 3: Frontend", report)
        # Verify all three blocks are separate (count occurrences of "## Sprint")
        self.assertEqual(report.count("## Sprint"), 3)

    def test_report_includes_pr_urls(self):
        """PR URLs from sprint data appear in the report output."""
        sprints = [
            _sprint(sid=1, title="Sprint A", status="completed"),
            _sprint(sid=2, title="Sprint B", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/org/repo/pull/42"
        sprints[1]["pr"] = "https://github.com/org/repo/pull/43"
        q = self._make_queue(sprints)
        for s in sprints:
            save_checkpoint(self.cp_dir, s["id"], {
                "sprint_id": s["id"], "status": "completed", "summary": {},
            })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("https://github.com/org/repo/pull/42", report)
        self.assertIn("https://github.com/org/repo/pull/43", report)

    def test_report_includes_test_counts(self):
        """Test pass/fail counts from checkpoint summaries appear in the report."""
        sprints = [
            _sprint(sid=1, title="Core", status="completed"),
            _sprint(sid=2, title="Extensions", status="completed"),
        ]
        q = self._make_queue(sprints)
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {"tests": {"passed": 12, "failed": 1}},
        })
        save_checkpoint(self.cp_dir, 2, {
            "sprint_id": 2, "status": "completed",
            "summary": {"tests": {"passed": 25, "failed": 0}},
        })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("12 passed, 1 failed", report)
        self.assertIn("25 passed, 0 failed", report)

    def test_report_includes_par_verdicts(self):
        """PAR evidence (claude_product, technical_review, provider) appears in the report."""
        sprints = [_sprint(sid=1, title="Main", status="completed")]
        q = self._make_queue(sprints)
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {
                "tests": {"passed": 5, "failed": 0},
                "par": {
                    "claude_product": "ACCEPTED",
                    "technical_review": "APPROVE",
                    "provider": "codex",
                },
            },
        })

        report = generate_completion_report(q, self.cp_dir)

        self.assertIn("Claude-Product=ACCEPTED", report)
        self.assertIn("Technical-Review=APPROVE", report)
        self.assertIn("provider: codex", report)

    def test_report_includes_holistic_verdict(self):
        """When holistic review evidence has specific verdicts, the report generates
        successfully (the gate validates the verdicts). Non-passing verdicts block."""
        # Passing case: holistic evidence already created in setUp with APPROVE verdicts
        sprints = [_sprint(sid=1, title="Sprint X", status="completed")]
        q = self._make_queue(sprints)
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed", "summary": {},
        })

        # Should succeed (holistic evidence passes gate)
        report = generate_completion_report(q, self.cp_dir)
        self.assertIn("# Completion Report", report)

        # Now overwrite with a failing holistic verdict
        self._create_holistic_evidence({
            "claude_product": "NEEDS_FIXES",
            "technical_review": "APPROVE",
        })

        with self.assertRaises(RuntimeError) as ctx:
            generate_completion_report(q, self.cp_dir)
        self.assertIn("invalid verdicts", str(ctx.exception))

    def test_report_handles_missing_checkpoints(self):
        """Report works gracefully when checkpoint data is missing for a sprint."""
        sprints = [
            _sprint(sid=1, title="With CP", status="completed"),
            _sprint(sid=2, title="Without CP", status="completed"),
        ]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/10"
        sprints[1]["pr"] = "https://github.com/test/repo/pull/11"
        q = self._make_queue(sprints)

        # Only create checkpoint for sprint 1; sprint 2 has none
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {
                "tests": {"passed": 8, "failed": 0},
                "par": {"claude_product": "ACCEPTED", "technical_review": "APPROVE", "provider": "codex"},
            },
        })

        report = generate_completion_report(q, self.cp_dir)

        # Sprint 1 has full data
        self.assertIn("8 passed, 0 failed", report)
        self.assertIn("Claude-Product=ACCEPTED", report)
        # Sprint 2 falls back to N/A for tests and PAR
        # Count "Tests:** N/A" — should appear for sprint 2
        self.assertIn("## Sprint 2: Without CP", report)
        # The sprint without checkpoint should show N/A for tests and PAR
        lines = report.split("\n")
        sprint2_section = False
        sprint2_tests_na = False
        sprint2_par_na = False
        for line in lines:
            if "## Sprint 2" in line:
                sprint2_section = True
            elif line.startswith("## Sprint") and sprint2_section:
                break
            elif sprint2_section and "**Tests:** N/A" in line:
                sprint2_tests_na = True
            elif sprint2_section and "**PAR:** N/A" in line:
                sprint2_par_na = True
        self.assertTrue(sprint2_tests_na, "Sprint 2 should show Tests: N/A")
        self.assertTrue(sprint2_par_na, "Sprint 2 should show PAR: N/A")

    def test_report_output_to_file(self):
        """Report is written to the specified output path and content matches return value."""
        sprints = [_sprint(sid=1, title="File Test", status="completed")]
        sprints[0]["pr"] = "https://github.com/test/repo/pull/99"
        q = self._make_queue(sprints)
        save_checkpoint(self.cp_dir, 1, {
            "sprint_id": 1, "status": "completed",
            "summary": {"tests": {"passed": 3, "failed": 0}},
        })

        output_path = os.path.join(self.tmpdir, "output", "completion.md")
        report = generate_completion_report(q, self.cp_dir, output_path=output_path)

        # File must exist
        self.assertTrue(os.path.exists(output_path))
        # File content must match returned string
        with open(output_path) as f:
            file_content = f.read()
        self.assertEqual(report, file_content)
        # Verify it's valid markdown with expected header
        self.assertTrue(file_content.startswith("# Completion Report"))


class TestBuildPromptPathTraversal(unittest.TestCase):
    """Task 1.1: path traversal validation in build_prompt()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        templates_dir = os.path.join(self.tmpdir, "templates")
        os.makedirs(templates_dir)
        with open(os.path.join(templates_dir, "supervisor-sprint-prompt.md"), "w") as f:
            f.write("Sprint {sprint_id}: {sprint_plan}\n")
        plans_dir = os.path.join(self.tmpdir, "plans")
        os.makedirs(plans_dir)
        with open(os.path.join(plans_dir, "plan.md"), "w") as f:
            f.write("# Plan\n## Sprint 1\nDo the thing.\n")
        with open(os.path.join(self.tmpdir, "CLAUDE.md"), "w") as f:
            f.write("")
        with open(os.path.join(self.tmpdir, "llms.txt"), "w") as f:
            f.write("")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_path_traversal_raises_value_error(self):
        """plan_file with ../ that escapes repo_root raises ValueError."""
        sprint = _sprint(sid=1, plan_file="../outside_repo/evil.md")
        with self.assertRaises(ValueError) as ctx:
            build_prompt(sprint, self.tmpdir)
        self.assertIn("Path traversal detected", str(ctx.exception))

    def test_normal_plan_path_does_not_raise(self):
        """A legitimate plan_file within repo_root does not raise."""
        sprint = _sprint(sid=1, plan_file="plans/plan.md#sprint-1")
        # Should not raise
        result = build_prompt(sprint, self.tmpdir)
        self.assertIn("Sprint 1", result)

    def test_absolute_path_outside_repo_raises(self):
        """An absolute path pointing outside the repo raises ValueError."""
        sprint = _sprint(sid=1, plan_file="/etc/passwd")
        with self.assertRaises(ValueError) as ctx:
            build_prompt(sprint, self.tmpdir)
        self.assertIn("Path traversal detected", str(ctx.exception))


class TestSprintEnvDenyList(unittest.TestCase):
    """Task 1.3: _SPRINT_ENV_DENY_LIST rename and expansion."""

    def test_deny_list_name_exists(self):
        """_SPRINT_ENV_DENY_LIST must exist on the module."""
        import lib.supervisor as sv
        self.assertTrue(hasattr(sv, "_SPRINT_ENV_DENY_LIST"),
                        "_SPRINT_ENV_DENY_LIST not found on supervisor module")

    def test_old_name_removed(self):
        """_DENIED_ENV_KEYS must NOT exist — it has been renamed."""
        import lib.supervisor as sv
        self.assertFalse(hasattr(sv, "_DENIED_ENV_KEYS"),
                         "_DENIED_ENV_KEYS should have been renamed to _SPRINT_ENV_DENY_LIST")

    def test_existing_keys_preserved(self):
        """Original keys are still present in the new deny-list."""
        import lib.supervisor as sv
        for key in ("AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                    "DATABASE_URL", "DB_PASSWORD",
                    "OPENAI_API_KEY", "GOOGLE_API_KEY", "HCLOUD_TOKEN"):
            self.assertIn(key, sv._SPRINT_ENV_DENY_LIST,
                          f"{key} missing from _SPRINT_ENV_DENY_LIST")

    def test_new_keys_added(self):
        """Newly added keys are present in the expanded deny-list."""
        import lib.supervisor as sv
        new_keys = [
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
            "SLACK_TOKEN", "SLACK_BOT_TOKEN",
            "STRIPE_SECRET_KEY", "STRIPE_API_KEY",
            "SSH_AUTH_SOCK", "SSH_AGENT_PID",
            "NPM_TOKEN", "DOCKER_PASSWORD",
            "HEROKU_API_KEY", "SENTRY_DSN",
        ]
        for key in new_keys:
            self.assertIn(key, sv._SPRINT_ENV_DENY_LIST,
                          f"{key} missing from _SPRINT_ENV_DENY_LIST")

    def test_auth_keys_not_in_deny_list(self):
        """ANTHROPIC_API_KEY and GITHUB_TOKEN are intentionally excluded."""
        import lib.supervisor as sv
        self.assertNotIn("ANTHROPIC_API_KEY", sv._SPRINT_ENV_DENY_LIST)
        self.assertNotIn("GITHUB_TOKEN", sv._SPRINT_ENV_DENY_LIST)

    def test_filtered_env_uses_deny_list(self):
        """_filtered_env() strips keys from _SPRINT_ENV_DENY_LIST."""
        import lib.supervisor as sv
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "secret-tg",
            "STRIPE_SECRET_KEY": "sk_live_abc",
            "ANTHROPIC_API_KEY": "sk-ant-keep-me",
            "SOME_NORMAL_VAR": "keep-me",
        }):
            env = sv._filtered_env()
        self.assertNotIn("TELEGRAM_BOT_TOKEN", env)
        self.assertNotIn("STRIPE_SECRET_KEY", env)
        self.assertIn("ANTHROPIC_API_KEY", env)
        self.assertIn("SOME_NORMAL_VAR", env)


class TestCheckSkipRequests(unittest.TestCase):
    """Tests for _check_skip_requests() — applying skip requests from sidecar dir."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = self.tmpdir
        self.skip_dir = os.path.join(self.repo_root, ".superflow", "skip-requests")
        self.queue = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="pending"),
            _sprint(sid=2, status="pending"),
        ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_valid_skip_request_applied(self):
        """Valid skip request marks sprint as skipped."""
        os.makedirs(self.skip_dir, exist_ok=True)
        filepath = os.path.join(self.skip_dir, "skip-1-1234.json")
        with open(filepath, "w") as f:
            json.dump({"sprint_id": 1, "reason": "user abort"}, f)

        _check_skip_requests(self.repo_root, self.queue)

        self.assertEqual(self.queue.sprints[0]["status"], "skipped")
        self.assertEqual(self.queue.sprints[0]["error_log"], "user abort")
        # File should be deleted after processing
        self.assertFalse(os.path.exists(filepath))

    def test_invalid_json_ignored_and_deleted(self):
        """Invalid JSON in skip request is ignored and file deleted."""
        os.makedirs(self.skip_dir, exist_ok=True)
        filepath = os.path.join(self.skip_dir, "skip-bad-1234.json")
        with open(filepath, "w") as f:
            f.write("not valid json{{{")

        _check_skip_requests(self.repo_root, self.queue)

        # No sprints should be affected
        self.assertEqual(self.queue.sprints[0]["status"], "pending")
        self.assertEqual(self.queue.sprints[1]["status"], "pending")
        # File should be deleted even if invalid
        self.assertFalse(os.path.exists(filepath))

    def test_nonexistent_sprint_id_handled(self):
        """Skip request with non-existent sprint_id is handled gracefully."""
        os.makedirs(self.skip_dir, exist_ok=True)
        filepath = os.path.join(self.skip_dir, "skip-99-1234.json")
        with open(filepath, "w") as f:
            json.dump({"sprint_id": 99, "reason": "nope"}, f)

        # Should not raise
        _check_skip_requests(self.repo_root, self.queue)

        # No sprints should be affected
        self.assertEqual(self.queue.sprints[0]["status"], "pending")
        self.assertEqual(self.queue.sprints[1]["status"], "pending")
        # File should still be deleted
        self.assertFalse(os.path.exists(filepath))

    def test_empty_skip_dir_noop(self):
        """Empty skip-requests directory is a no-op."""
        os.makedirs(self.skip_dir, exist_ok=True)

        _check_skip_requests(self.repo_root, self.queue)

        self.assertEqual(self.queue.sprints[0]["status"], "pending")
        self.assertEqual(self.queue.sprints[1]["status"], "pending")

    def test_missing_skip_dir_noop(self):
        """Missing skip-requests directory is a no-op (no error)."""
        _check_skip_requests(self.repo_root, self.queue)

        self.assertEqual(self.queue.sprints[0]["status"], "pending")


class TestHeartbeat(unittest.TestCase):
    """Tests for heartbeat writing during run loop."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.repo_root = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("lib.supervisor.execute_sprint")
    @patch("lib.supervisor.preflight", return_value=(True, []))
    @patch("lib.supervisor.subprocess.run")
    def test_heartbeat_written_during_run_loop(self, mock_subproc, mock_preflight, mock_exec):
        """Heartbeat file is written during the run loop."""
        # Create queue with one sprint that becomes completed after execute
        q = SprintQueue("test", "2026-01-01T00:00:00Z", [
            _sprint(sid=1, status="pending"),
        ])
        q.save(self.queue_path)

        mock_subproc.return_value = MagicMock(returncode=0, stdout=self.repo_root)

        def fake_execute(sprint, queue, qpath, ckdir, repo, timeout=1800, notifier=None):
            sprint["status"] = "completed"
            sprint["pr"] = "https://github.com/test/pr/1"
            queue.save(qpath)

        mock_exec.side_effect = fake_execute

        # Suppress holistic review / completion report paths
        with patch("lib.supervisor.run_holistic_review", return_value=True), \
             patch("lib.supervisor.generate_completion_report", return_value=None):
            run(
                queue_path=self.queue_path,
                plan_path=None,
                max_parallel=1,
                timeout=1800,
                no_replan=True,
                repo_root=self.repo_root,
            )

        heartbeat_path = os.path.join(self.repo_root, ".superflow", "heartbeat")
        self.assertTrue(os.path.exists(heartbeat_path))
        with open(heartbeat_path) as f:
            ts = float(f.read().strip())
        # Heartbeat should be recent (within 10 seconds)
        self.assertLess(time.time() - ts, 10)


class TestReadSprintProgress(unittest.TestCase):
    """Tests for _read_sprint_progress()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_returns_none_when_file_missing(self):
        """_read_sprint_progress returns None when file doesn't exist."""
        from lib.supervisor import _read_sprint_progress
        result = _read_sprint_progress(self.tmpdir)
        self.assertIsNone(result)

    def test_returns_dict_when_file_exists(self):
        """_read_sprint_progress returns parsed dict when file exists."""
        from lib.supervisor import _read_sprint_progress
        progress_data = {
            "sprint_id": 1,
            "step": "implementation",
            "steps_completed": ["baseline_tests"],
            "ts": "2026-01-01T00:00:00Z",
        }
        infra = os.path.join(self.tmpdir, ".superflow")
        os.makedirs(infra)
        with open(os.path.join(infra, "sprint-progress.json"), "w") as f:
            json.dump(progress_data, f)
        result = _read_sprint_progress(self.tmpdir)
        self.assertIsNotNone(result)
        self.assertEqual(result["sprint_id"], 1)
        self.assertEqual(result["step"], "implementation")

    def test_returns_none_when_file_invalid_json(self):
        """_read_sprint_progress returns None when file contains invalid JSON."""
        from lib.supervisor import _read_sprint_progress
        infra = os.path.join(self.tmpdir, ".superflow")
        os.makedirs(infra)
        with open(os.path.join(infra, "sprint-progress.json"), "w") as f:
            f.write("not-json")
        result = _read_sprint_progress(self.tmpdir)
        self.assertIsNone(result)

    def test_reads_steps_completed_list(self):
        """_read_sprint_progress preserves steps_completed list."""
        from lib.supervisor import _read_sprint_progress
        progress_data = {
            "sprint_id": 2,
            "step": "par",
            "steps_completed": ["baseline_tests", "implementation", "internal_review"],
            "ts": "2026-01-01T00:00:00Z",
        }
        infra = os.path.join(self.tmpdir, ".superflow")
        os.makedirs(infra)
        with open(os.path.join(infra, "sprint-progress.json"), "w") as f:
            json.dump(progress_data, f)
        result = _read_sprint_progress(self.tmpdir)
        self.assertEqual(result["steps_completed"],
                         ["baseline_tests", "implementation", "internal_review"])


if __name__ == "__main__":
    unittest.main()

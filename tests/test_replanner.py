"""Tests for adaptive replanner."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from lib.replanner import replan, _parse_changes, _validate_change, _apply_change
from lib.queue import SprintQueue


def _sprint(sid=1, title="Test Sprint", status="pending", branch="feat/test",
            plan_file="plans/plan.md#sprint-1", depends_on=None):
    return {
        "id": sid, "title": title, "status": status,
        "plan_file": plan_file, "branch": branch,
        "depends_on": depends_on or [],
        "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
    }


class TestParseChanges(unittest.TestCase):
    def test_no_changes(self):
        output = 'Some reasoning here.\n{"changes": []}'
        result = _parse_changes(output)
        self.assertEqual(result, [])

    def test_with_changes(self):
        output = (
            'Analysis...\n'
            '{"changes": [{"type": "skip", "sprint_id": 3, "reason": "not needed"}]}'
        )
        result = _parse_changes(output)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "skip")

    def test_malformed_json(self):
        output = "Some text\nnot valid json at all"
        result = _parse_changes(output)
        self.assertIsNone(result)

    def test_json_without_changes_key(self):
        output = '{"result": "ok"}'
        result = _parse_changes(output)
        self.assertIsNone(result)

    def test_empty_output(self):
        result = _parse_changes("")
        self.assertIsNone(result)

    def test_changes_not_list(self):
        output = '{"changes": "not a list"}'
        result = _parse_changes(output)
        self.assertIsNone(result)


class TestValidateChange(unittest.TestCase):
    def test_valid_skip(self):
        self.assertTrue(_validate_change({"type": "skip", "sprint_id": 3, "reason": "done"}))

    def test_valid_modify(self):
        self.assertTrue(_validate_change({"type": "modify", "sprint_id": 2, "new_plan": "x"}))

    def test_valid_reorder(self):
        self.assertTrue(_validate_change({"type": "reorder", "sprint_id": 2, "depends_on": [1]}))

    def test_valid_add(self):
        self.assertTrue(_validate_change({"type": "add", "title": "New sprint"}))

    def test_invalid_type(self):
        self.assertFalse(_validate_change({"type": "delete", "sprint_id": 1}))

    def test_missing_type(self):
        self.assertFalse(_validate_change({"sprint_id": 1}))

    def test_not_a_dict(self):
        self.assertFalse(_validate_change("skip sprint 3"))
        self.assertFalse(_validate_change(42))
        self.assertFalse(_validate_change(None))

    def test_skip_without_sprint_id(self):
        self.assertFalse(_validate_change({"type": "skip"}))

    def test_modify_without_sprint_id(self):
        self.assertFalse(_validate_change({"type": "modify", "new_plan": "x"}))

    def test_adversarial_type_injection(self):
        """Type values that look similar but are wrong should be rejected."""
        self.assertFalse(_validate_change({"type": "SKIP", "sprint_id": 1}))
        self.assertFalse(_validate_change({"type": "Skip", "sprint_id": 1}))
        self.assertFalse(_validate_change({"type": " skip", "sprint_id": 1}))
        self.assertFalse(_validate_change({"type": "skip ", "sprint_id": 1}))
        self.assertFalse(_validate_change({"type": "remove", "sprint_id": 1}))
        self.assertFalse(_validate_change({"type": "", "sprint_id": 1}))


class TestApplyChange(unittest.TestCase):
    def _make_queue(self, sprints):
        return SprintQueue("test", "2026-01-01T00:00:00Z", sprints)

    def test_apply_skip(self):
        q = self._make_queue([_sprint(sid=3, status="pending")])
        result = _apply_change(q, {"type": "skip", "sprint_id": 3, "reason": "not needed"})
        self.assertTrue(result)
        self.assertEqual(q.sprints[0]["status"], "skipped")

    def test_apply_skip_nonexistent(self):
        q = self._make_queue([_sprint(sid=1)])
        result = _apply_change(q, {"type": "skip", "sprint_id": 99})
        self.assertFalse(result)

    def test_apply_modify(self):
        q = self._make_queue([_sprint(sid=2, title="Old Title")])
        result = _apply_change(q, {"type": "modify", "sprint_id": 2, "title": "New Title"})
        self.assertTrue(result)
        self.assertEqual(q.sprints[0]["title"], "New Title")

    def test_apply_reorder(self):
        q = self._make_queue([_sprint(sid=2, depends_on=[1])])
        result = _apply_change(q, {"type": "reorder", "sprint_id": 2, "depends_on": []})
        self.assertTrue(result)
        self.assertEqual(q.sprints[0]["depends_on"], [])

    def test_apply_add(self):
        q = self._make_queue([_sprint(sid=1)])
        result = _apply_change(q, {
            "type": "add", "sprint_id": 4, "title": "New Sprint",
            "branch": "feat/new", "plan_file": "plans/new.md",
        })
        self.assertTrue(result)
        self.assertEqual(len(q.sprints), 2)
        self.assertEqual(q.sprints[1]["id"], 4)
        self.assertEqual(q.sprints[1]["title"], "New Sprint")
        self.assertEqual(q.sprints[1]["status"], "pending")


class TestReplanIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")
        os.makedirs(self.cp_dir)
        # Create template
        os.makedirs(os.path.join(self.tmpdir, "templates"))
        with open(os.path.join(self.tmpdir, "templates", "replan-prompt.md"), "w") as f:
            f.write(
                "Completed: {completed_sprints}\n"
                "Remaining: {remaining_sprints}\n"
                "Plan: {plan_content}\n"
            )
        # Create plan
        self.plan_path = os.path.join(self.tmpdir, "plans", "plan.md")
        os.makedirs(os.path.join(self.tmpdir, "plans"))
        with open(self.plan_path, "w") as f:
            f.write("## Sprint 1\nStuff\n## Sprint 2\nMore stuff\n")
        # Create a completed checkpoint
        with open(os.path.join(self.cp_dir, "sprint-1.json"), "w") as f:
            json.dump({"sprint_id": 1, "status": "completed", "summary": {"pr_url": "x"}}, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.replanner.subprocess.run")
    def test_no_changes_output(self, mock_run):
        """Claude returns no changes — queue unchanged."""
        sprints = [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ]
        q = self._make_queue(sprints)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Analysis complete.\n{"changes": []}',
            stderr="",
        )

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        self.assertEqual(changes, [])
        # Sprint 2 should still be pending
        loaded = SprintQueue.load(self.queue_path)
        self.assertEqual(loaded.sprints[1]["status"], "pending")

    @patch("lib.replanner.subprocess.run")
    def test_skip_operation(self, mock_run):
        """Claude recommends skipping sprint 2."""
        sprints = [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ]
        q = self._make_queue(sprints)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Sprint 2 is redundant.\n{"changes": [{"type": "skip", "sprint_id": 2, "reason": "redundant"}]}',
            stderr="",
        )

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "skip")
        loaded = SprintQueue.load(self.queue_path)
        self.assertEqual(loaded.sprints[1]["status"], "skipped")

    @patch("lib.replanner.subprocess.run")
    def test_malformed_json_graceful_skip(self, mock_run):
        """Invalid JSON output should be handled gracefully."""
        sprints = [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ]
        q = self._make_queue(sprints)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="I think we should skip sprint 2 but I forgot the JSON",
            stderr="",
        )

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        self.assertEqual(changes, [])
        # Queue should be unchanged
        loaded = SprintQueue.load(self.queue_path)
        self.assertEqual(loaded.sprints[1]["status"], "pending")

    @patch("lib.replanner.subprocess.run")
    def test_adversarial_invalid_change_type_rejected(self, mock_run):
        """Invalid change types should be rejected, valid ones applied."""
        sprints = [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
            _sprint(sid=3, status="pending"),
        ]
        q = self._make_queue(sprints)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                'Changes needed.\n'
                '{"changes": ['
                '{"type": "delete", "sprint_id": 2, "reason": "bad type"}, '
                '{"type": "skip", "sprint_id": 3, "reason": "valid skip"}'
                ']}'
            ),
            stderr="",
        )

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        # Only the skip should be applied
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "skip")
        self.assertEqual(changes[0]["sprint_id"], 3)
        loaded = SprintQueue.load(self.queue_path)
        self.assertEqual(loaded.sprints[1]["status"], "pending")  # sid=2 unchanged
        self.assertEqual(loaded.sprints[2]["status"], "skipped")  # sid=3 skipped

    @patch("lib.replanner.subprocess.run")
    def test_no_remaining_sprints_skips_replan(self, mock_run):
        """If all sprints are done, replan should return empty list."""
        sprints = [_sprint(sid=1, status="completed")]
        q = self._make_queue(sprints)

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        self.assertEqual(changes, [])
        mock_run.assert_not_called()

    @patch("lib.replanner.subprocess.run")
    def test_subprocess_timeout(self, mock_run):
        """Subprocess timeout should be handled gracefully."""
        sprints = [
            _sprint(sid=1, status="completed"),
            _sprint(sid=2, status="pending"),
        ]
        q = self._make_queue(sprints)

        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="claude", timeout=300)

        changes = replan(q, self.queue_path, self.plan_path, self.tmpdir, self.cp_dir)

        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()

"""Tests for SprintQueue — TDD approach."""
import json
import os
import tempfile
import unittest

from lib.queue import SprintQueue


def _make_queue_data(sprints=None):
    """Helper to build a minimal queue dict."""
    return {
        "feature": "test-feature",
        "created": "2026-03-23T12:00:00Z",
        "sprints": sprints or [
            {
                "id": 1, "title": "First sprint", "status": "pending",
                "plan_file": "docs/superflow/plans/plan.md#sprint-1",
                "branch": "feat/test-sprint-1", "depends_on": [],
                "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
            }
        ],
    }


class TestSprintQueueLoadSave(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "queue.json")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        tmp = self.path + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        os.rmdir(self.tmpdir)

    def test_load_and_save_roundtrip(self):
        data = _make_queue_data()
        with open(self.path, "w") as f:
            json.dump(data, f)
        q = SprintQueue.load(self.path)
        self.assertEqual(q.feature, "test-feature")
        self.assertEqual(len(q.sprints), 1)
        self.assertEqual(q.sprints[0]["status"], "pending")

        # Save and reload
        q.save(self.path)
        q2 = SprintQueue.load(self.path)
        self.assertEqual(q2.feature, q.feature)
        self.assertEqual(q2.sprints, q.sprints)

    def test_save_is_atomic(self):
        """Save writes to .tmp first then renames — no partial writes."""
        data = _make_queue_data()
        with open(self.path, "w") as f:
            json.dump(data, f)
        q = SprintQueue.load(self.path)
        q.save(self.path)
        # .tmp must not linger
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        # File must exist and be valid JSON
        with open(self.path) as f:
            reloaded = json.load(f)
        self.assertEqual(reloaded["feature"], "test-feature")


class TestNextRunnable(unittest.TestCase):
    def _make_q(self, sprints):
        return SprintQueue("f", "2026-01-01T00:00:00Z", sprints)

    def _sprint(self, sid, status="pending", depends_on=None):
        return {
            "id": sid, "title": f"Sprint {sid}", "status": status,
            "plan_file": f"plan.md#sprint-{sid}",
            "branch": f"feat/s-{sid}", "depends_on": depends_on or [],
            "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
        }

    def test_no_deps_returns_pending(self):
        q = self._make_q([self._sprint(1), self._sprint(2)])
        runnable = q.next_runnable(max_parallel=2)
        self.assertEqual([s["id"] for s in runnable], [1, 2])

    def test_respects_max_parallel(self):
        q = self._make_q([self._sprint(1), self._sprint(2), self._sprint(3)])
        runnable = q.next_runnable(max_parallel=1)
        self.assertEqual(len(runnable), 1)

    def test_deps_block_until_completed(self):
        q = self._make_q([
            self._sprint(1, status="pending"),
            self._sprint(2, status="pending", depends_on=[1]),
        ])
        runnable = q.next_runnable(max_parallel=10)
        self.assertEqual([s["id"] for s in runnable], [1])

    def test_deps_resolved_when_completed(self):
        q = self._make_q([
            self._sprint(1, status="completed"),
            self._sprint(2, status="pending", depends_on=[1]),
        ])
        runnable = q.next_runnable(max_parallel=10)
        self.assertEqual([s["id"] for s in runnable], [2])

    def test_in_progress_not_returned(self):
        q = self._make_q([self._sprint(1, status="in_progress")])
        runnable = q.next_runnable(max_parallel=10)
        self.assertEqual(runnable, [])

    def test_diamond_dag(self):
        """DAG: 1 -> 2, 1 -> 3, 2+3 -> 4."""
        q = self._make_q([
            self._sprint(1, status="completed"),
            self._sprint(2, status="completed", depends_on=[1]),
            self._sprint(3, status="pending", depends_on=[1]),
            self._sprint(4, status="pending", depends_on=[2, 3]),
        ])
        runnable = q.next_runnable(max_parallel=10)
        # Only 3 is runnable (deps met); 4 still blocked by 3
        self.assertEqual([s["id"] for s in runnable], [3])


class TestMarkOperations(unittest.TestCase):
    def _make_q(self, sprints):
        return SprintQueue("f", "2026-01-01T00:00:00Z", sprints)

    def _sprint(self, sid, status="pending", depends_on=None):
        return {
            "id": sid, "title": f"Sprint {sid}", "status": status,
            "plan_file": f"plan.md#sprint-{sid}",
            "branch": f"feat/s-{sid}", "depends_on": depends_on or [],
            "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
        }

    def test_mark_in_progress(self):
        q = self._make_q([self._sprint(1)])
        q.mark_in_progress(1)
        self.assertEqual(q.sprints[0]["status"], "in_progress")

    def test_mark_completed(self):
        q = self._make_q([self._sprint(1, status="in_progress")])
        q.mark_completed(1, "https://github.com/pr/1")
        self.assertEqual(q.sprints[0]["status"], "completed")
        self.assertEqual(q.sprints[0]["pr"], "https://github.com/pr/1")

    def test_mark_failed(self):
        q = self._make_q([self._sprint(1, status="in_progress")])
        q.mark_failed(1, "build broke")
        self.assertEqual(q.sprints[0]["status"], "failed")
        self.assertEqual(q.sprints[0]["error_log"], "build broke")

    def test_mark_skipped(self):
        q = self._make_q([self._sprint(1)])
        q.mark_skipped(1, "not needed")
        self.assertEqual(q.sprints[0]["status"], "skipped")

    def test_mark_nonexistent_sprint_raises(self):
        q = self._make_q([self._sprint(1)])
        with self.assertRaises(KeyError):
            q.mark_in_progress(99)


class TestIsDoneAndSummary(unittest.TestCase):
    def _make_q(self, sprints):
        return SprintQueue("f", "2026-01-01T00:00:00Z", sprints)

    def _sprint(self, sid, status="pending"):
        return {
            "id": sid, "title": f"Sprint {sid}", "status": status,
            "plan_file": f"plan.md#sprint-{sid}",
            "branch": f"feat/s-{sid}", "depends_on": [],
            "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
        }

    def test_is_done_all_completed(self):
        q = self._make_q([
            self._sprint(1, "completed"),
            self._sprint(2, "completed"),
        ])
        self.assertTrue(q.is_done())

    def test_is_done_mixed_terminal(self):
        q = self._make_q([
            self._sprint(1, "completed"),
            self._sprint(2, "failed"),
            self._sprint(3, "skipped"),
        ])
        self.assertTrue(q.is_done())

    def test_not_done_with_pending(self):
        q = self._make_q([
            self._sprint(1, "completed"),
            self._sprint(2, "pending"),
        ])
        self.assertFalse(q.is_done())

    def test_not_done_with_in_progress(self):
        q = self._make_q([self._sprint(1, "in_progress")])
        self.assertFalse(q.is_done())

    def test_summary(self):
        q = self._make_q([
            self._sprint(1, "completed"),
            self._sprint(2, "pending"),
            self._sprint(3, "failed"),
            self._sprint(4, "in_progress"),
        ])
        s = q.summary()
        self.assertEqual(s, {
            "completed": 1, "pending": 1, "failed": 1,
            "in_progress": 1, "skipped": 0,
        })


class TestSkipBlockedSprints(unittest.TestCase):
    def _sprint(self, sid, status="pending", depends_on=None):
        return {
            "id": sid, "title": f"Sprint {sid}", "status": status,
            "plan_file": f"plan.md#sprint-{sid}",
            "branch": f"feat/s-{sid}", "depends_on": depends_on or [],
            "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
        }

    def test_skip_direct_dependency_on_failed(self):
        q = SprintQueue("f", "2026-01-01T00:00:00Z", [
            self._sprint(1, "failed"),
            self._sprint(2, "pending", depends_on=[1]),
        ])
        q.skip_blocked_sprints()
        self.assertEqual(q.sprints[1]["status"], "skipped")

    def test_skip_transitive_dependency_on_failed(self):
        """1 failed -> 2 skipped -> 3 should also be skipped."""
        q = SprintQueue("f", "2026-01-01T00:00:00Z", [
            self._sprint(1, "failed"),
            self._sprint(2, "pending", depends_on=[1]),
            self._sprint(3, "pending", depends_on=[2]),
        ])
        q.skip_blocked_sprints()
        self.assertEqual(q.sprints[1]["status"], "skipped")
        self.assertEqual(q.sprints[2]["status"], "skipped")

    def test_no_skip_when_no_failures(self):
        q = SprintQueue("f", "2026-01-01T00:00:00Z", [
            self._sprint(1, "completed"),
            self._sprint(2, "pending", depends_on=[1]),
        ])
        q.skip_blocked_sprints()
        self.assertEqual(q.sprints[1]["status"], "pending")


if __name__ == "__main__":
    unittest.main()

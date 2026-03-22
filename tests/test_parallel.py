"""Tests for parallel sprint execution."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from lib.parallel import execute_parallel
from lib.queue import SprintQueue


def _sprint(sid=1, title="Test Sprint", status="pending", branch="feat/test-sprint",
            plan_file="plans/plan.md#sprint-1", depends_on=None):
    return {
        "id": sid, "title": title, "status": status,
        "plan_file": plan_file, "branch": branch,
        "depends_on": depends_on or [],
        "pr": None, "retries": 0, "max_retries": 2, "error_log": None,
    }


class TestExecuteParallel(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.json")
        self.cp_dir = os.path.join(self.tmpdir, "checkpoints")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_queue(self, sprints):
        q = SprintQueue("test", "2026-01-01T00:00:00Z", sprints)
        q.save(self.queue_path)
        return q

    @patch("lib.parallel._worker")
    def test_three_independent_sprints_all_execute(self, mock_worker):
        """All 3 independent sprints should be submitted and executed."""
        sprints = [
            _sprint(sid=1, title="Sprint 1"),
            _sprint(sid=2, title="Sprint 2"),
            _sprint(sid=3, title="Sprint 3"),
        ]
        q = self._make_queue(sprints)

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=3)

        self.assertEqual(mock_worker.call_count, 3)
        called_ids = {call.args[0]["id"] for call in mock_worker.call_args_list}
        self.assertEqual(called_ids, {1, 2, 3})

    @patch("lib.parallel._worker")
    def test_concurrent_execution_timestamps(self, mock_worker):
        """Verify sprints run concurrently by checking they overlap in time."""
        timestamps = {}
        barrier = threading.Barrier(3, timeout=5)

        def side_effect(sprint, *args, **kwargs):
            timestamps[sprint["id"]] = {"start": time.monotonic()}
            barrier.wait()  # All threads must reach here before proceeding
            time.sleep(0.05)
            timestamps[sprint["id"]]["end"] = time.monotonic()

        mock_worker.side_effect = side_effect

        sprints = [
            _sprint(sid=1), _sprint(sid=2), _sprint(sid=3),
        ]
        q = self._make_queue(sprints)

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=3)

        # If truly concurrent, all starts should happen before all ends
        all_starts = [ts["start"] for ts in timestamps.values()]
        all_ends = [ts["end"] for ts in timestamps.values()]
        self.assertTrue(max(all_starts) < min(all_ends),
                        "Sprints did not run concurrently")

    @patch("lib.parallel._worker")
    def test_queue_lock_prevents_corruption(self, mock_worker):
        """Multiple workers writing to queue with lock should not corrupt it."""
        sprints = [
            _sprint(sid=1), _sprint(sid=2), _sprint(sid=3),
        ]
        q = self._make_queue(sprints)

        write_count = {"n": 0}
        original_save = q.save

        def tracked_save(path):
            write_count["n"] += 1
            original_save(path)

        q.save = tracked_save

        def side_effect(sprint, queue, queue_path, cp_dir, repo_root,
                        timeout, notifier, queue_lock):
            with queue_lock:
                queue.mark_completed(sprint["id"], f"https://pr/{sprint['id']}")
                queue.save(queue_path)

        mock_worker.side_effect = side_effect

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=3)

        # Verify queue file is valid JSON and all sprints completed
        loaded = SprintQueue.load(self.queue_path)
        for s in loaded.sprints:
            self.assertEqual(s["status"], "completed")

    @patch("lib.parallel._worker")
    def test_worker_exception_marks_failed(self, mock_worker):
        """If a worker raises, the sprint should be marked failed."""
        sprints = [
            _sprint(sid=1), _sprint(sid=2),
        ]
        q = self._make_queue(sprints)

        def side_effect(sprint, queue, queue_path, cp_dir, repo_root,
                        timeout, notifier, queue_lock):
            if sprint["id"] == 2:
                raise RuntimeError("Worker crashed")
            with queue_lock:
                queue.mark_completed(sprint["id"], "https://pr/1")
                queue.save(queue_path)

        mock_worker.side_effect = side_effect

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=2)

        loaded = SprintQueue.load(self.queue_path)
        s1 = next(s for s in loaded.sprints if s["id"] == 1)
        s2 = next(s for s in loaded.sprints if s["id"] == 2)
        self.assertEqual(s1["status"], "completed")
        self.assertEqual(s2["status"], "failed")
        self.assertIn("Worker crashed", s2["error_log"])

    @patch("lib.parallel._worker")
    def test_on_sprint_done_callback(self, mock_worker):
        """on_sprint_done callback should be called for each completed sprint."""
        sprints = [_sprint(sid=1), _sprint(sid=2)]
        q = self._make_queue(sprints)
        callback_count = {"n": 0}

        def callback():
            callback_count["n"] += 1

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=2, on_sprint_done=callback)

        self.assertEqual(callback_count["n"], 2)

    @patch("lib.parallel._worker")
    def test_max_workers_limits_concurrency(self, mock_worker):
        """With max_workers=1, sprints should run sequentially."""
        execution_order = []
        lock = threading.Lock()

        def side_effect(sprint, *args, **kwargs):
            with lock:
                execution_order.append(("start", sprint["id"]))
            time.sleep(0.02)
            with lock:
                execution_order.append(("end", sprint["id"]))

        mock_worker.side_effect = side_effect

        sprints = [_sprint(sid=1), _sprint(sid=2)]
        q = self._make_queue(sprints)

        execute_parallel(sprints, q, self.queue_path, self.cp_dir, self.tmpdir,
                         max_workers=1)

        # With max_workers=1, second sprint should start after first ends
        # Find index of end of first sprint and start of second
        first_end = None
        second_start = None
        for i, (event, sid) in enumerate(execution_order):
            if event == "end" and first_end is None:
                first_end = i
            if event == "start" and i > 0 and second_start is None:
                second_start = i

        self.assertIsNotNone(first_end)
        self.assertIsNotNone(second_start)
        self.assertGreater(second_start, first_end - 1,
                           "With max_workers=1, second sprint should not start before first ends")


class TestWorkerIntegration(unittest.TestCase):
    """Test that _worker correctly calls execute_sprint."""

    @patch("lib.supervisor.execute_sprint")
    def test_worker_calls_execute_sprint(self, mock_execute):
        """_worker should call execute_sprint with the right arguments."""
        from lib.parallel import _worker

        sprint = _sprint(sid=1)
        queue = MagicMock()
        queue_lock = threading.Lock()

        _worker(sprint, queue, "/tmp/q.json", "/tmp/cp", "/tmp/repo",
                1800, None, queue_lock)

        mock_execute.assert_called_once_with(
            sprint, queue, "/tmp/q.json", "/tmp/cp", "/tmp/repo",
            timeout=1800, notifier=None, queue_lock=queue_lock,
        )


if __name__ == "__main__":
    unittest.main()

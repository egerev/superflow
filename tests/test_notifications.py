"""Tests for the Notifier class."""

import unittest

from lib.notifications import Notifier


class TestNotifierInit(unittest.TestCase):
    """Test Notifier initialization."""

    def test_init_with_token_and_chat_id(self):
        """Notifier stores bot_token, chat_id, and total_sprints."""
        n = Notifier(bot_token="tok123", chat_id="456", total_sprints=5)
        self.assertEqual(n.bot_token, "tok123")
        self.assertEqual(n.chat_id, "456")
        self.assertEqual(n.total_sprints, 5)

    def test_init_without_token(self):
        """Notifier defaults to stdout-only mode when no token given."""
        n = Notifier()
        self.assertIsNone(n.bot_token)
        self.assertIsNone(n.chat_id)
        self.assertEqual(n.total_sprints, 0)

    def test_is_configured_true(self):
        """is_configured returns True when both bot_token and chat_id set."""
        n = Notifier(bot_token="tok", chat_id="123")
        self.assertTrue(n.is_configured)

    def test_is_configured_false_no_token(self):
        """is_configured returns False when bot_token is missing."""
        n = Notifier(chat_id="123")
        self.assertFalse(n.is_configured)

    def test_is_configured_false_no_chat_id(self):
        """is_configured returns False when chat_id is missing."""
        n = Notifier(bot_token="tok")
        self.assertFalse(n.is_configured)


class TestNotifierStdout(unittest.TestCase):
    """Test stdout fallback when Telegram is not configured."""

    def test_notify_prints_to_stdout(self):
        """notify() prints to stdout when not configured for Telegram."""
        from io import StringIO
        import sys

        n = Notifier()
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            n.notify("test_event", "hello world")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        self.assertIn("[test_event]", output)
        self.assertIn("hello world", output)

    def test_notify_with_sprint_id_includes_progress(self):
        """notify() includes sprint progress prefix when sprint_id given."""
        from io import StringIO
        import sys

        n = Notifier(total_sprints=5)
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            n.notify("info", "doing stuff", sprint_id=2)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        self.assertIn("Sprint 2/5", output)
        self.assertIn("doing stuff", output)

    def test_notify_without_sprint_id_no_progress(self):
        """notify() omits progress prefix when sprint_id is None."""
        from io import StringIO
        import sys

        n = Notifier()
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            n.notify("info", "general message")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue().strip()
        self.assertNotIn("Sprint", output)
        self.assertIn("general message", output)


class TestFormatProgress(unittest.TestCase):
    """Test _format_progress helper."""

    def test_with_sprint_id(self):
        n = Notifier(total_sprints=10)
        self.assertEqual(n._format_progress(sprint_id=3), "Sprint 3/10")

    def test_without_sprint_id(self):
        n = Notifier(total_sprints=10)
        self.assertEqual(n._format_progress(), "")


class TestEventTypes(unittest.TestCase):
    """Test all 11 event type methods produce correct message format."""

    def _capture_stdout(self, func, *args, **kwargs):
        """Helper: call func, return captured stdout text."""
        from io import StringIO
        import sys

        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            func(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def setUp(self):
        self.n = Notifier(total_sprints=5)

    def test_notify_preflight_passed(self):
        output = self._capture_stdout(self.n.notify_preflight, passed=True)
        self.assertIn("Preflight passed", output)
        self.assertIn("[preflight]", output)

    def test_notify_preflight_failed_with_issues(self):
        output = self._capture_stdout(
            self.n.notify_preflight, passed=False, issues="missing config"
        )
        self.assertIn("Preflight FAILED", output)
        self.assertIn("missing config", output)

    def test_notify_sprint_start(self):
        output = self._capture_stdout(
            self.n.notify_sprint_start, sprint_id=1, title="Setup"
        )
        self.assertIn("Sprint 1/5", output)
        self.assertIn("Starting", output)
        self.assertIn("Setup", output)
        self.assertIn("[sprint_start]", output)

    def test_notify_sprint_complete(self):
        output = self._capture_stdout(
            self.n.notify_sprint_complete,
            sprint_id=2,
            title="API",
            pr_url="https://github.com/pr/1",
        )
        self.assertIn("Sprint 2/5", output)
        self.assertIn("complete", output)
        self.assertIn("https://github.com/pr/1", output)
        self.assertIn("[sprint_complete]", output)

    def test_notify_sprint_failed(self):
        output = self._capture_stdout(
            self.n.notify_sprint_failed,
            sprint_id=3,
            title="DB",
            error="timeout",
            retry_count=1,
            max_retries=3,
        )
        self.assertIn("Sprint 3/5", output)
        self.assertIn("FAILED", output)
        self.assertIn("timeout", output)
        self.assertIn("[sprint_failed]", output)

    def test_notify_sprint_retry(self):
        output = self._capture_stdout(
            self.n.notify_sprint_retry,
            sprint_id=3,
            title="DB",
            attempt=2,
            max_retries=3,
        )
        self.assertIn("Sprint 3/5", output)
        self.assertIn("retrying", output)
        self.assertIn("2/3", output)
        self.assertIn("[sprint_retry]", output)

    def test_notify_sprint_skipped(self):
        output = self._capture_stdout(
            self.n.notify_sprint_skipped,
            sprint_id=4,
            title="Cache",
            reason="dependency failed",
        )
        self.assertIn("Sprint 4/5", output)
        self.assertIn("skipped", output)
        self.assertIn("dependency failed", output)
        self.assertIn("[sprint_skipped]", output)

    def test_notify_blocked(self):
        output = self._capture_stdout(
            self.n.notify_blocked, message="waiting for approval"
        )
        self.assertIn("Queue blocked", output)
        self.assertIn("waiting for approval", output)
        self.assertIn("[blocked]", output)

    def test_notify_timeout(self):
        output = self._capture_stdout(
            self.n.notify_timeout,
            sprint_id=2,
            title="Build",
            timeout_seconds=600,
        )
        self.assertIn("Sprint 2/5", output)
        self.assertIn("timed out", output)
        self.assertIn("600s", output)
        self.assertIn("[timeout]", output)

    def test_notify_replan(self):
        output = self._capture_stdout(
            self.n.notify_replan, changes_summary="removed sprint 4, added sprint 6"
        )
        self.assertIn("Replanner updated queue", output)
        self.assertIn("removed sprint 4, added sprint 6", output)
        self.assertIn("[replan]", output)

    def test_notify_crash_resume(self):
        output = self._capture_stdout(
            self.n.notify_crash_resume, completed=3, remaining=2
        )
        self.assertIn("Supervisor resumed", output)
        self.assertIn("3", output)
        self.assertIn("2", output)
        self.assertIn("[crash_resume]", output)

    def test_notify_all_done(self):
        output = self._capture_stdout(
            self.n.notify_all_done, summary="5/5 merged"
        )
        self.assertIn("All sprints complete", output)
        self.assertIn("5/5 merged", output)
        self.assertIn("[all_done]", output)


if __name__ == "__main__":
    unittest.main()

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


class TestNewNotificationMethods(unittest.TestCase):
    """Test Sprint 3 notification methods."""

    def _capture(self, func):
        """Helper to capture stdout output from a notifier call."""
        from io import StringIO
        import sys
        n = Notifier(total_sprints=5)
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            func(n)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def test_notify_holistic_start(self):
        """notify_holistic_review_start prints correct event and message."""
        output = self._capture(lambda n: n.notify_holistic_review_start())
        self.assertIn("[holistic_review_start]", output)
        self.assertIn("Starting Final Holistic Review (all sprints)", output)

    def test_notify_holistic_complete(self):
        """notify_holistic_review_complete prints verdict."""
        output = self._capture(lambda n: n.notify_holistic_review_complete("APPROVE"))
        self.assertIn("[holistic_review_complete]", output)
        self.assertIn("Holistic Review: APPROVE", output)

    def test_notify_par_failed(self):
        """notify_par_validation_failed prints sprint progress and errors."""
        output = self._capture(
            lambda n: n.notify_par_validation_failed(
                2, "Validation Sprint", ["missing key 'claude_product'", "invalid verdict"]
            )
        )
        self.assertIn("[par_validation_failed]", output)
        self.assertIn("Sprint 2/5", output)
        self.assertIn("Validation Sprint", output)
        self.assertIn("PAR evidence invalid", output)
        self.assertIn("missing key 'claude_product'", output)

    def test_notify_baseline_failed(self):
        """notify_baseline_failed prints sprint progress and failure message."""
        output = self._capture(
            lambda n: n.notify_baseline_failed(1, "Foundation Sprint")
        )
        self.assertIn("[baseline_failed]", output)
        self.assertIn("Sprint 1/5", output)
        self.assertIn("Foundation Sprint", output)
        self.assertIn("Baseline tests FAILED", output)

    def test_notify_resume_recovery(self):
        """notify_resume_recovery prints recovery counts."""
        output = self._capture(
            lambda n: n.notify_resume_recovery(3, 1, 6)
        )
        self.assertIn("[resume_recovery]", output)
        self.assertIn("Recovered 3 sprints", output)
        self.assertIn("reset 1 to pending", output)
        self.assertIn("6 total", output)


if __name__ == "__main__":
    unittest.main()

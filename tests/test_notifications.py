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


if __name__ == "__main__":
    unittest.main()

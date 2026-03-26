"""Tests for the Notifier class."""

import unittest
import unittest.mock

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


class TestNotifierEnvFallback(unittest.TestCase):
    """Test Notifier falls back to env vars when no args given."""

    def test_init_reads_token_from_env(self):
        """Notifier picks up TELEGRAM_BOT_TOKEN from environment."""
        import os
        env = {"TELEGRAM_BOT_TOKEN": "envtok", "TELEGRAM_CHAT_ID": "envchat"}
        with unittest.mock.patch.dict(os.environ, env, clear=False):
            n = Notifier()
        self.assertEqual(n.bot_token, "envtok")
        self.assertEqual(n.chat_id, "envchat")

    def test_explicit_args_take_precedence_over_env(self):
        """Explicit bot_token/chat_id win over env vars."""
        import os
        env = {"TELEGRAM_BOT_TOKEN": "envtok", "TELEGRAM_CHAT_ID": "envchat"}
        with unittest.mock.patch.dict(os.environ, env, clear=False):
            n = Notifier(bot_token="explicit", chat_id="000")
        self.assertEqual(n.bot_token, "explicit")
        self.assertEqual(n.chat_id, "000")

    def test_init_without_env_stays_none(self):
        """Notifier stays None when env vars absent and no args given."""
        import os
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with unittest.mock.patch.dict(os.environ, env_clean, clear=True):
            n = Notifier()
        self.assertIsNone(n.bot_token)
        self.assertIsNone(n.chat_id)


class TestNotifySprintProgress(unittest.TestCase):
    """Test notify_sprint_progress() formatting."""

    def _capture(self, notifier, *args, **kwargs):
        from io import StringIO
        import sys
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            notifier.notify_sprint_progress(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def test_format_contains_progress_tag(self):
        """notify_sprint_progress output contains [progress] tag."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=2, title="Auth Module", step="implementation")
        self.assertIn("[progress]", output)

    def test_format_contains_sprint_id_and_total(self):
        """notify_sprint_progress output contains sprint id and total."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=2, title="Auth Module", step="implementation")
        self.assertIn("2/5", output)

    def test_format_contains_step(self):
        """notify_sprint_progress output contains the step name."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=2, title="Auth Module", step="implementation")
        self.assertIn("implementation", output)

    def test_format_contains_started(self):
        """notify_sprint_progress message indicates step started."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=2, title="Auth Module", step="review")
        self.assertIn("started", output)


class TestNotifyProgressDigest(unittest.TestCase):
    """Test notify_progress_digest() formatting."""

    def _capture(self, notifier, *args, **kwargs):
        from io import StringIO
        import sys
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            notifier.notify_progress_digest(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def test_format_contains_digest_tag(self):
        """notify_progress_digest output contains [digest] tag."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, completed=2, remaining=3, elapsed_minutes=45, pr_urls=[])
        self.assertIn("[digest]", output)

    def test_format_contains_completed_and_total(self):
        """notify_progress_digest output shows completed/total."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, completed=2, remaining=3, elapsed_minutes=45, pr_urls=[])
        self.assertIn("2/5", output)

    def test_format_contains_elapsed_minutes(self):
        """notify_progress_digest output shows elapsed minutes."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, completed=2, remaining=3, elapsed_minutes=45, pr_urls=[])
        self.assertIn("45", output)

    def test_format_contains_pr_urls(self):
        """notify_progress_digest output shows PR URLs."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, completed=2, remaining=3, elapsed_minutes=45,
                               pr_urls=["https://github.com/foo/bar/pull/1"])
        self.assertIn("https://github.com/foo/bar/pull/1", output)

    def test_format_contains_next_sprint_info(self):
        """notify_progress_digest output shows next sprint info when provided."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, completed=2, remaining=3, elapsed_minutes=45,
                               pr_urls=[], next_id=3, next_title="API Layer")
        self.assertIn("3", output)
        self.assertIn("API Layer", output)


class TestNotifyBlockerEscalation(unittest.TestCase):
    """Test notify_blocker_escalation() formatting."""

    def _capture(self, notifier, *args, **kwargs):
        from io import StringIO
        import sys
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            notifier.notify_blocker_escalation(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def test_format_contains_blocker_tag(self):
        """notify_blocker_escalation output contains [BLOCKER] tag."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=3, blocker_type="PAR_FAILED",
                               description="Review failed twice.", recommended_action="Fix tests")
        self.assertIn("[BLOCKER]", output)

    def test_format_contains_sprint_id(self):
        """notify_blocker_escalation output contains sprint id."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=3, blocker_type="PAR_FAILED",
                               description="Review failed twice.", recommended_action="Fix tests")
        self.assertIn("3", output)

    def test_format_contains_blocker_type(self):
        """notify_blocker_escalation output contains blocker_type."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=3, blocker_type="PAR_FAILED",
                               description="Review failed twice.", recommended_action="Fix tests")
        self.assertIn("PAR_FAILED", output)

    def test_format_contains_description(self):
        """notify_blocker_escalation output contains description."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=3, blocker_type="PAR_FAILED",
                               description="Review failed twice.", recommended_action="Fix tests")
        self.assertIn("Review failed twice.", output)

    def test_format_contains_recommended_action(self):
        """notify_blocker_escalation output contains recommended action."""
        n = Notifier(total_sprints=5)
        output = self._capture(n, sprint_id=3, blocker_type="PAR_FAILED",
                               description="Review failed twice.", recommended_action="Fix tests")
        self.assertIn("Fix tests", output)


class TestNotifyMergeReminder(unittest.TestCase):
    """Test notify_merge_reminder() formatting."""

    def _capture(self, notifier, *args, **kwargs):
        from io import StringIO
        import sys
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            notifier.notify_merge_reminder(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue().strip()

    def test_format_contains_all_sprints_complete(self):
        """notify_merge_reminder message mentions all sprints complete."""
        n = Notifier()
        output = self._capture(n)
        self.assertIn("sprints complete", output.lower())

    def test_format_contains_merge_instruction(self):
        """notify_merge_reminder message contains /merge instruction."""
        n = Notifier()
        output = self._capture(n)
        self.assertIn("/merge", output)


if __name__ == "__main__":
    unittest.main()

"""Notification system for Superflow supervisor.

Sends messages via Telegram when configured, falls back to stdout.
"""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class Notifier:
    """Sends supervisor notifications via Telegram or stdout."""

    def __init__(self, bot_token=None, chat_id=None, total_sprints=0):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.total_sprints = total_sprints

    @property
    def is_configured(self):
        """Return True if Telegram credentials are set."""
        return bool(self.bot_token and self.chat_id)

    def _format_progress(self, sprint_id=None):
        """Return 'Sprint {id}/{total}' prefix or empty string."""
        if sprint_id is None:
            return ""
        return f"Sprint {sprint_id}/{self.total_sprints}"

    def _send_telegram(self, text):
        """POST message to Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            logger.warning("Telegram send failed: %s", exc)
            return None

    def notify(self, event_type, message, sprint_id=None, **kwargs):
        """Format and send a notification."""
        prefix = self._format_progress(sprint_id)
        full_message = f"[{event_type}] {prefix + ': ' if prefix else ''}{message}"

        if self.is_configured:
            self._send_telegram(full_message)
        else:
            print(full_message)

    # ── Event type methods ──────────────────────────────────────────

    def notify_preflight(self, passed, issues=None):
        """Preflight check result."""
        status = "passed" if passed else "FAILED"
        msg = f"Preflight {status}."
        if issues:
            msg += f" {issues}"
        self.notify("preflight", msg)

    def notify_sprint_start(self, sprint_id, title):
        """Sprint is starting."""
        self.notify("sprint_start", f"Starting: {title}", sprint_id=sprint_id)

    def notify_sprint_complete(self, sprint_id, title, pr_url):
        """Sprint finished successfully."""
        self.notify(
            "sprint_complete",
            f"{title} complete. PR: {pr_url}",
            sprint_id=sprint_id,
        )

    def notify_sprint_failed(self, sprint_id, title, error, retry_count, max_retries):
        """Sprint failed."""
        self.notify(
            "sprint_failed",
            f"{title} FAILED: {error} (retry {retry_count}/{max_retries})",
            sprint_id=sprint_id,
        )

    def notify_sprint_retry(self, sprint_id, title, attempt, max_retries):
        """Sprint failed, retrying."""
        self.notify(
            "sprint_retry",
            f"{title} failed, retrying (attempt {attempt}/{max_retries})",
            sprint_id=sprint_id,
        )

    def notify_sprint_skipped(self, sprint_id, title, reason):
        """Sprint skipped."""
        self.notify(
            "sprint_skipped",
            f"{title} skipped: {reason}",
            sprint_id=sprint_id,
        )

    def notify_blocked(self, message):
        """Queue is blocked, needs user attention."""
        self.notify("blocked", f"Queue blocked: {message}")

    def notify_timeout(self, sprint_id, title, timeout_seconds):
        """Sprint timed out."""
        self.notify(
            "timeout",
            f"{title} timed out after {timeout_seconds}s",
            sprint_id=sprint_id,
        )

    def notify_replan(self, changes_summary):
        """Replanner changed the queue."""
        self.notify("replan", f"Replanner updated queue: {changes_summary}")

    def notify_crash_resume(self, completed, remaining):
        """Supervisor resumed after crash."""
        self.notify(
            "crash_resume",
            f"Supervisor resumed. Completed: {completed}, remaining: {remaining}",
        )

    def notify_all_done(self, summary):
        """All sprints finished."""
        self.notify("all_done", f"All sprints complete. {summary}")

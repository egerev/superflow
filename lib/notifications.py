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

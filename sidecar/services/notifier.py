"""Simple notification emitter that writes events to stderr for Tauri to pick up."""

import json
import logging
import sys

logger = logging.getLogger(__name__)


def emit_notification(title: str, body: str, urgency: str = "normal") -> None:
    """Emit a notification event on stderr.

    Tauri's sidecar stdout/stderr reader is expected to parse lines prefixed
    with ``NOTIFY:`` and forward them as system notifications.

    Args:
        title:   Short notification heading.
        body:    Notification detail text.
        urgency: One of "low", "normal", "critical".  Tauri can use this to
                 decide whether to show a banner, badge, or alert dialog.
    """
    event = {
        "type": "notification",
        "title": title,
        "body": body,
        "urgency": urgency,
    }
    sys.stderr.write("NOTIFY:" + json.dumps(event, ensure_ascii=False) + "\n")
    sys.stderr.flush()
    logger.info("Notification: %s — %s", title, body)

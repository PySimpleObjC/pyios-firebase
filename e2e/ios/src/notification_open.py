"""Notifications tapped while the app is closed: the app records what ``on_open``
gets, and ``run_ios_e2e.sh`` checks it.

A notification tapped while the app is not running launches the app with no
environment variables, so ``install()`` runs at every launch, before
``App.run()``, as a real app's ``set_handlers`` call would.

The ``notification-permission`` phase asks for full permission (alert, badge,
sound), so that banners show on the home screen; the script taps "Allow".
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from pyios_firebase.messaging import notifications
from pyios_firebase.messaging.notifications import AuthorizationOptions

DOCUMENTS = os.path.expanduser("~/Documents")
OPENED = os.path.join(DOCUMENTS, "pyios-e2e-notification-open.json")
PERMISSION = os.path.join(DOCUMENTS, "pyios-e2e-notification-permission.json")

LAUNCHED_AT = time.time()


def _write(path: str, value: dict[str, Any]) -> None:
    with open(path + ".tmp", "w") as f:
        json.dump(value, f)
    os.replace(path + ".tmp", path)  # the host polls for this file


def record_open(notification: notifications.Notification, action: str) -> None:
    """``on_open``: write what the tap delivered, for the script to check."""
    _write(OPENED, {
        "title": notification.title,
        "body": notification.body,
        "data": {k: v for k, v in notification.data.items() if k != "aps"},
        "message_id": notification.message_id,
        "action": action,
        "seconds_after_launch": round(time.time() - LAUNCHED_AT, 2),
    })
    print(f"PYIOS-E2E OPENED {notification.title!r} action={action}", flush=True)


def install(**handlers: Any) -> None:
    """``set_handlers`` with the recorder as ``on_open``.

    Args:
        **handlers: other handlers (for example ``on_foreground``).
    """
    notifications.set_handlers(on_open=record_open, **handlers)


def ask_permission() -> None:
    """The ``notification-permission`` phase: ask for full permission."""

    def answered(granted: bool, error: Any) -> None:
        _write(PERMISSION, {"granted": bool(granted), "error": None if error is None else str(error)})
        print(f"PYIOS-E2E PERMISSION granted={granted}", flush=True)

    notifications.request_permission(
        AuthorizationOptions.ALERT | AuthorizationOptions.BADGE | AuthorizationOptions.SOUND,
        answered,
    )

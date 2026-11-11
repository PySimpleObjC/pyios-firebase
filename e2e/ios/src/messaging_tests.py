"""Cloud Messaging and notification end-to-end tests.

FCM cannot reach the Simulator, and the demo project is not a real one, so the
FCM backend calls only have to answer (with an error). Notifications are real:
the test writes a payload to ``Documents/pyios-e2e-push.json`` and
``run_ios_e2e.sh`` delivers it with ``xcrun simctl push``.
"""

from __future__ import annotations

import json
import os

from firestore_tests import RUN_ID
from kivy.clock import Clock
from runner import TestContext, expect, expect_equal

from pyios_firebase.messaging import APNSTokenType, Messaging, MessagingMessageStatus, notifications
from pyios_firebase.messaging.notifications import (
    AuthorizationOptions,
    AuthorizationStatus,
    PresentationOptions,
)

PUSH_REQUEST = os.path.join(os.path.expanduser("~/Documents"), "pyios-e2e-push.json")


def on_main(t: TestContext, fn):
    """A callback the SDK runs on a background thread, run on Kivy's thread."""

    def call(*args) -> None:
        Clock.schedule_once(lambda dt: t.step(fn)(*args), 0)

    return call


def test_messaging_settings_and_topics(t: TestContext) -> None:
    messaging = Messaging.messaging()
    auto_init = messaging.auto_init_enabled
    messaging.auto_init_enabled = not auto_init
    expect_equal(messaging.auto_init_enabled, not auto_init, "auto-init toggled")
    messaging.auto_init_enabled = auto_init
    expect_equal(messaging.installation_id_enabled, False, "installation ID mode off")

    token = bytes(range(32))
    messaging.set_apns_token(token, APNSTokenType.SANDBOX)
    expect_equal(messaging.apns_token, token, "APNs token")
    expect(messaging.fcm_token is None or isinstance(messaging.fcm_token, str), "FCM token")

    for bad in ("", "a b", "a/b"):
        try:
            messaging.subscribe_to_topic(bad)
        except ValueError:
            continue
        raise AssertionError(f"topic {bad!r} accepted")

    message = {"gcm.message_id": f"e2e-{RUN_ID}", "aps": {"content-available": 1}}
    expect_equal(messaging.app_did_receive_message(message), MessagingMessageStatus.NEW, "status")
    expect_equal(messaging.app_did_receive_message({}), MessagingMessageStatus.UNKNOWN, "empty")
    t.passed()


def test_messaging_token_answers(t: TestContext) -> None:
    messaging = Messaging.messaging()
    remove = messaging.add_token_listener(lambda token: None)
    expect(messaging.native.delegate is not None, "the Python delegate is installed")
    state = {"done": False}

    def got(token, error) -> None:
        if state["done"]:
            return
        state["done"] = True
        remove()
        # a demo project has no FCM backend: an error is the expected answer
        expect((token is None) != (error is None), f"token={token!r} error={error!r}")
        if error is not None:
            expect(isinstance(error.name, str) and error.description, error)
        t.passed()

    def too_slow(dt) -> None:
        if not state["done"]:
            state["done"] = True
            remove()
            t.skipped("FCM did not answer within 15 s (the demo project is offline)")

    messaging.token(t.step(got))
    Clock.schedule_once(too_slow, 15)


def test_notifications_permission(t: TestContext) -> None:
    def status(value) -> None:
        expect(
            value in (AuthorizationStatus.PROVISIONAL, AuthorizationStatus.AUTHORIZED),
            f"status {value}",
        )
        t.passed()

    def answered(granted, error) -> None:
        expect(error is None, error)
        expect(granted, "provisional permission is granted without asking")
        notifications.authorization_status(on_main(t, status))

    # provisional: granted without a prompt, so the test needs no tap
    notifications.request_permission(
        AuthorizationOptions.PROVISIONAL | AuthorizationOptions.ALERT | AuthorizationOptions.SOUND,
        on_main(t, answered),
    )


def test_notifications_foreground_push(t: TestContext) -> None:
    received = []
    message_id = f"e2e-push-{RUN_ID}"

    def on_foreground(notification):
        received.append(notification)
        Clock.schedule_once(lambda dt: t.step(check)(), 0)
        return PresentationOptions.BANNER | PresentationOptions.LIST

    def check() -> None:
        notification = received[0]
        expect_equal(notification.title, "Sale", "title")
        expect_equal(notification.body, "50% off today", "body")
        expect_equal(notification.badge, 3, "badge")
        expect_equal(notification.message_id, message_id, "FCM message ID")
        expect_equal(notification.data.get("screen"), "shop", "data keys")
        expect(notification.date is not None, "date")
        t.passed()

    notifications.set_handlers(on_foreground=on_foreground)
    payload = {
        "aps": {"alert": {"title": "Sale", "body": "50% off today"}, "badge": 3},
        "gcm.message_id": message_id,
        "screen": "shop",
    }
    with open(PUSH_REQUEST + ".tmp", "w") as f:
        json.dump(payload, f)
    os.replace(PUSH_REQUEST + ".tmp", PUSH_REQUEST)  # run_ios_e2e.sh pushes it


TESTS = [
    ("test_messaging_settings_and_topics", test_messaging_settings_and_topics),
    ("test_messaging_token_answers", test_messaging_token_answers),
    ("test_notifications_permission", test_notifications_permission),
    ("test_notifications_foreground_push", test_notifications_foreground_push),
]

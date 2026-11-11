"""Google Analytics end-to-end tests (no emulator exists: the SDK runs for
real and keeps its events on the device, as the project is not a real one)."""

from __future__ import annotations

from ctypes import CDLL

from kivy.clock import Clock
from rubicon.objc.runtime import objc_id
from runner import TestContext, expect, expect_equal

from pyios_firebase.analytics import Analytics, ConsentStatus, ConsentType, Event, Param
from pyios_firebase.util import objc_instance


def test_analytics_logging(t: TestContext) -> None:
    Analytics.log_event(Event.LOGIN, {Param.METHOD: "e2e"})
    Analytics.log_event(
        Event.PURCHASE,
        {
            Param.CURRENCY: "EUR",
            Param.VALUE: 12.5,
            Param.ITEMS: [{Param.ITEM_ID: "sku-1", Param.QUANTITY: 2}],
        },
    )
    Analytics.log_screen_view("E2E", "E2EScreen")
    Analytics.set_user_property("e2e", "plan")
    Analytics.set_user_id("e2e-user")
    Analytics.set_default_event_parameters({"build": "e2e", "old": None})
    Analytics.set_session_timeout_interval(1800)
    for name, call, error in [
        ("reserved event", lambda: Analytics.log_event("first_open"), ValueError),
        ("reserved prefix", lambda: Analytics.log_event("firebase_x"), ValueError),
        ("bool value", lambda: Analytics.log_event("ok", {"flag": True}), TypeError),
        ("long property", lambda: Analytics.set_user_property("x" * 37, "plan"), ValueError),
    ]:
        try:
            call()
        except error:
            continue
        raise AssertionError(f"{name}: no {error.__name__}")
    t.passed()


def test_analytics_ids_and_consent(t: TestContext) -> None:
    # the consent names must be the SDK's own constants
    process = CDLL(None)
    for name, expected in [
        ("FIRConsentTypeAdStorage", ConsentType.AD_STORAGE),
        ("FIRConsentTypeAnalyticsStorage", ConsentType.ANALYTICS_STORAGE),
        ("FIRConsentTypeAdUserData", ConsentType.AD_USER_DATA),
        ("FIRConsentTypeAdPersonalization", ConsentType.AD_PERSONALIZATION),
        ("FIRConsentStatusGranted", ConsentStatus.GRANTED),
        ("FIRConsentStatusDenied", ConsentStatus.DENIED),
    ]:
        try:
            value = str(objc_instance(objc_id.in_dll(process, name)))
        except ValueError:
            continue  # not exported from the app binary: nothing to compare
        expect_equal(value, expected, name)

    Analytics.set_consent({ConsentType.ANALYTICS_STORAGE: ConsentStatus.GRANTED})
    instance_id = Analytics.app_instance_id()
    expect(instance_id is None or len(instance_id) >= 16, f"app instance ID {instance_id!r}")

    def got_session(session_id, error) -> None:
        # the callback runs on a background thread: check on the main one
        Clock.schedule_once(lambda dt: t.step(check)(session_id, error), 0)

    def check(session_id, error) -> None:
        expect(
            (session_id is not None and error is None) or (session_id is None and error),
            f"session: {session_id!r} {error!r}",
        )
        if session_id is not None:
            expect(session_id > 0, f"session ID {session_id}")
        t.passed()

    Analytics.session_id(got_session)


TESTS = [(name, fn) for name, fn in globals().items() if name.startswith("test_analytics")]

"""Crashlytics end-to-end tests.

The app has ``FirebaseCrashlyticsCollectionEnabled`` = ``NO`` (pyproject.toml):
reports stay on the device, where the unsent-report API can read them.

``run_ios_e2e.sh`` launches the app twice. The first launch runs every suite,
then ``crash_now`` records a non-fatal Python exception and aborts the app.
The second launch (``E2E_PHASE=after-crash``) runs ``AFTER_CRASH_TESTS``: the
crash and the report from the first launch must be there.
"""

from __future__ import annotations

import os
import sys

from kivy.clock import Clock
from runner import TestContext, expect, expect_equal

from pyios_firebase.crashlytics import Crashlytics, ExceptionModel, StackFrame

CRASH_MARKER = "pyios-e2e-crash"


class E2EPaymentError(Exception):
    pass


def _pay() -> None:
    raise E2EPaymentError("card declined (e2e)")


def test_crashlytics_context_and_non_fatals(t: TestContext) -> None:
    crashlytics = Crashlytics.crashlytics()
    expect_equal(crashlytics.collection_enabled, False, "collection off (Info.plist)")
    crashlytics.log("e2e: context test")
    crashlytics.set_custom_value("e2e_run", 1)
    crashlytics.set_custom_keys({"screen": "e2e", "items": 3, "pro": True})
    crashlytics.set_user_id("e2e-user")
    try:
        _pay()
    except E2EPaymentError as e:
        model = ExceptionModel.from_exception(e)
        crashlytics.record_exception(e)
    expect_equal(model.name, "crashlytics_tests.E2EPaymentError", "issue name")
    expect_equal(model.stack_trace[0].symbol, "_pay", "Python frames, newest first")
    crashlytics.record_exception_model(
        ExceptionModel("LuaError", "nil value", [StackFrame("main", "game.lua", 3)])
    )
    from pyios_firebase.util import objc_class

    crashlytics.record_error(
        objc_class("NSError").errorWithDomain_code_userInfo_("e2e", 7, None), {"k": "v"}
    )
    expect(crashlytics.did_crash_during_previous_execution() in (True, False), "bool")
    t.passed()


def test_crashlytics_excepthook(t: TestContext) -> None:
    crashlytics = Crashlytics.crashlytics()
    seen = []
    previous = sys.excepthook
    sys.excepthook = lambda *args: seen.append(args[0])
    try:
        crashlytics.install_excepthook()
        try:
            _pay()
        except E2EPaymentError as e:
            sys.excepthook(type(e), e, e.__traceback__)  # as Python does for an uncaught one
        expect_equal(seen, [E2EPaymentError], "the previous hook still runs")
    finally:
        crashlytics.uninstall_excepthook()
        sys.excepthook = previous
    t.passed()


def crash_now() -> None:
    """End the first launch with a native crash, after a non-fatal issue."""
    crashlytics = Crashlytics.crashlytics()
    crashlytics.log(CRASH_MARKER)
    crashlytics.set_custom_value("marker", CRASH_MARKER)
    try:
        _pay()
    except E2EPaymentError as e:
        crashlytics.record_exception(e)
    print("PYIOS-E2E CRASHING on purpose (Crashlytics test)", flush=True)
    # give Crashlytics a moment to write the non-fatal issue to disk
    Clock.schedule_once(lambda dt: os.abort(), 1.0)


def test_crashlytics_after_crash(t: TestContext) -> None:
    crashlytics = Crashlytics.crashlytics()
    expect(crashlytics.did_crash_during_previous_execution(), "the crash was recorded")

    def got_report(report) -> None:
        expect(report is not None, "an unsent report is waiting")
        expect(report.has_crash, "the report has the crash")
        expect(report.report_id, "report ID")
        expect(report.date_created is not None, "date created")
        report.log("e2e: added after the crash")
        report.set_custom_keys({"checked": True})
        crashlytics.delete_unsent_reports()
        try:
            crashlytics.check_for_unsent_reports(lambda found: None)
        except RuntimeError:
            t.passed()
            return
        t.fail("a second check in one launch must raise")

    # the SDK answers on a background queue
    crashlytics.check_and_update_unsent_reports(
        lambda report: Clock.schedule_once(lambda dt: t.step(got_report)(report), 0)
    )


TESTS = [
    ("test_crashlytics_context_and_non_fatals", test_crashlytics_context_and_non_fatals),
    ("test_crashlytics_excepthook", test_crashlytics_excepthook),
]
AFTER_CRASH_TESTS = [("test_crashlytics_after_crash", test_crashlytics_after_crash)]

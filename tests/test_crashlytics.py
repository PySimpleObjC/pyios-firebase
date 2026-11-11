import sys
import threading
from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error

from pyios_firebase.crashlytics import (
    Crashlytics,
    CrashlyticsReport,
    ExceptionModel,
    StackFrame,
)
from pyios_firebase.types import FirebaseError
from pyios_firebase.util import to_python


class CheckoutError(Exception):
    pass


def pay():
    raise CheckoutError("card declined")


def checkout():
    try:
        pay()
    except CheckoutError as e:
        raise RuntimeError("checkout failed") from e


@pytest.fixture
def crashlytics():
    native = Recorder(
        returns={
            "isCrashlyticsCollectionEnabled": lambda: True,
            "didCrashDuringPreviousExecution": lambda: False,
        }
    )
    yield Crashlytics(native), native
    Crashlytics(native).uninstall_excepthook()


def test_exception_model_from_a_python_exception():
    try:
        checkout()
    except RuntimeError as e:
        model = ExceptionModel.from_exception(e)
    assert model.name == "RuntimeError"
    assert model.reason == "checkout failed (caused by CheckoutError: card declined)"
    assert model.stack_trace[0].symbol == "checkout"  # most recent call first
    assert model.stack_trace[0].file.endswith("test_crashlytics.py")
    assert (
        model.stack_trace[-1].symbol == "test_exception_model_from_a_python_exception"
    )

    try:
        pay()
    except CheckoutError as e:
        assert ExceptionModel.from_exception(e).name == "test_crashlytics.CheckoutError"


def test_record_exception_sends_a_native_model(crashlytics):
    crashlytics, native = crashlytics
    try:
        pay()
    except CheckoutError as e:
        crashlytics.record_exception(e)
    (model,) = native.last("recordExceptionModel_")
    assert str(model.name) == "test_crashlytics.CheckoutError"
    assert str(model.reason) == "card declined"
    frames = list(model.stackTrace)
    assert [str(f.symbol) for f in frames] == [
        "pay",
        "test_record_exception_sends_a_native_model",
    ]
    assert int(frames[0].line) > 0


def test_custom_model():
    model = ExceptionModel("LuaError", "nil value", [StackFrame("main", "game.lua", 3)])
    native = model.to_native()
    assert str(native.name) == "LuaError"
    assert int(next(iter(native.stackTrace)).line) == 3


def test_context(crashlytics):
    crashlytics, native = crashlytics
    crashlytics.log("opened checkout")
    crashlytics.set_custom_value("cart_items", 3)
    crashlytics.set_custom_value("plan", None)
    crashlytics.set_custom_value("when", SimpleNamespace(x=1))
    crashlytics.set_custom_keys({"a": 1, "b": "x", "gone": None})
    crashlytics.set_user_id("u1")
    assert native.calls[:3] == [
        ("log_", ("opened checkout",)),
        ("setCustomValue_forKey_", (3, "cart_items")),
        ("setCustomValue_forKey_", (None, "plan")),
    ]
    assert native.calls[3][1][0] == "namespace(x=1)"
    assert to_python(native.calls[4][1][0]) == {"a": 1, "b": "x"}


def test_record_error(crashlytics):
    crashlytics, native = crashlytics
    error = make_error("boom", 7, "com.example")
    crashlytics.record_error(error, {"screen": "home"})
    assert native.last("recordError_userInfo_")[0] is error
    crashlytics.record_error(FirebaseError(code=3, description="no", domain="d"))
    sent, info = native.last("recordError_userInfo_")
    assert (int(sent.code), str(sent.domain), info) == (3, "d", None)
    with pytest.raises(TypeError, match="record_exception"):
        crashlytics.record_error(ValueError("x"))


def test_excepthook_reports_and_chains(crashlytics, monkeypatch):
    crashlytics, native = crashlytics
    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: seen.append(a[0]))
    monkeypatch.setattr(threading, "excepthook", lambda args: seen.append("thread"))
    crashlytics.install_excepthook()
    crashlytics.install_excepthook()  # safe twice
    try:
        pay()
    except CheckoutError as e:
        sys.excepthook(type(e), e, e.__traceback__)
    assert seen == [CheckoutError]
    assert native.last("log_") == ("uncaught CheckoutError: card declined",)
    assert native.last("recordExceptionModel_")

    thread = threading.Thread(target=pay)
    thread.start()
    thread.join()
    assert seen[-1] == "thread"
    assert len([c for c in native.calls if c[0] == "recordExceptionModel_"]) == 2

    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert len([c for c in native.calls if c[0] == "recordExceptionModel_"]) == 2

    crashlytics.uninstall_excepthook()
    assert sys.excepthook.__name__ == "<lambda>"


def test_reports(crashlytics, blocks):
    crashlytics, native = crashlytics
    assert crashlytics.collection_enabled is True
    crashlytics.collection_enabled = False
    assert native.last("setCrashlyticsCollectionEnabled_") == (False,)
    assert crashlytics.did_crash_during_previous_execution() is False

    found = []
    Crashlytics._unsent_checked = False
    crashlytics.check_for_unsent_reports(found.append)
    fire(native.block(), True)
    with pytest.raises(RuntimeError, match="once per launch"):
        crashlytics.check_and_update_unsent_reports(found.append)
    Crashlytics._unsent_checked = False
    crashlytics.check_and_update_unsent_reports(found.append)
    fire(native.block(), None)
    assert found == [True, None]
    assert not blocks
    Crashlytics._unsent_checked = False

    report_native = Recorder()
    report_native.reportID = "r1"
    report_native.hasCrash = True
    report_native.dateCreated = None

    report = CrashlyticsReport(report_native)
    assert (report.report_id, report.has_crash) == ("r1", True)
    report.log("x")
    report.set_custom_keys({"k": 1})
    crashlytics.send_unsent_reports()
    crashlytics.delete_unsent_reports()
    assert native.calls[-2:] == [("sendUnsentReports", ()), ("deleteUnsentReports", ())]

"""End-to-end Cloud Functions tests: the real SDK against the Functions emulator
(e2e/functions/index.js)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pyios_firebase.auth import Auth
from pyios_firebase.functions import Functions, FunctionsErrorCode
from runner import TestContext, expect, expect_equal

EMULATOR_URL = "http://127.0.0.1:5001/demo-pyios-firebase/us-central1"


def functions() -> Functions:
    return Functions.functions()


def test_functions_round_trip_json(t: TestContext) -> None:
    data = {"text": "héllo ✓", "n": 42, "f": 1.5, "yes": True, "no": False, "none": None,
            "list": [1, "two", None, {"deep": [True]}], "tuple": (1, 2), "empty": {}}

    def done(result, error) -> None:
        expect(error is None, error)
        got = result["data"]
        expected = dict(data, tuple=[1, 2])
        expect_equal(got, expected, "echo")
        expect(type(got["yes"]) is bool and type(got["n"]) is int, f"types: {type(got['yes'])}, {type(got['n'])}")
        t.passed()

    functions().https_callable("echo").call(t.step(done), data)


def test_functions_call_without_data(t: TestContext) -> None:
    def done(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"data": None}, "no data")
        t.passed()

    functions().https_callable("echo").call(t.step(done))


def test_functions_https_error_details(t: TestContext) -> None:
    def done(result, error) -> None:
        expect(result is None, "no result on error")
        expect_equal(error.code, FunctionsErrorCode.INVALID_ARGUMENT, "code")
        expect_equal(error.name, "INVALID_ARGUMENT", "name")
        expect_equal(error.description, "bad input", "message")
        expect_equal(error.details, {"field": "text", "hint": "x"}, "details")
        t.passed()

    functions().https_callable("fail").call(t.step(done), "x")


def test_functions_unexpected_error_is_internal(t: TestContext) -> None:
    def done(result, error) -> None:
        expect_equal(error.code, FunctionsErrorCode.INTERNAL, "code")
        expect("secret server detail" not in error.description, "the server's message is not leaked")
        t.passed()

    functions().https_callable("crash").call(t.step(done))


def test_functions_unknown_function(t: TestContext) -> None:
    def done(result, error) -> None:
        expect(error is not None, "calling a missing function fails")
        expect(error.code in (FunctionsErrorCode.NOT_FOUND, FunctionsErrorCode.INTERNAL), error)
        t.passed()

    functions().https_callable("doesNotExist").call(t.step(done))


def test_functions_timeout(t: TestContext) -> None:
    callable_ = functions().https_callable("slow")
    callable_.timeout_interval = 1
    expect_equal(callable_.timeout_interval, 1.0, "timeout")

    def done(result, error) -> None:
        expect(error is not None and error.code == FunctionsErrorCode.DEADLINE_EXCEEDED, f"timeout: {error}")
        t.passed()

    callable_.call(t.step(done), {"ms": 5000})


def test_functions_auth_context(t: TestContext) -> None:
    auth = Auth.auth()
    state: dict[str, Any] = {}

    def signed_out(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"uid": None}, "no auth context when signed out")
        t.passed()

    def as_user(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"uid": state["uid"]}, "the function sees the signed-in user")
        auth.sign_out()
        functions().https_callable("whoAmI").call(t.step(signed_out))

    def signed_in(result, error) -> None:
        expect(error is None, error)
        state["uid"] = result.user.uid
        functions().https_callable("whoAmI").call(t.step(as_user))

    auth.sign_out()
    auth.sign_in_anonymously(t.step(signed_in))


def test_functions_region_and_url(t: TestContext) -> None:
    def by_url(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"data": "by url"}, "callable by URL")
        t.passed()

    def regional(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"region": "europe-west1"}, "regional function")
        functions().https_callable_from_url(f"{EMULATOR_URL}/echo").call(t.step(by_url), "by url")

    Functions.functions("europe-west1").https_callable("regional").call(t.step(regional))


def test_functions_send_app_check_tokens(t: TestContext) -> None:
    def limited(result, error) -> None:
        expect(error is None, error)
        header = result["header"]
        expect(header and header.startswith("e2e-limited-"), f"limited-use token sent: {header}")
        t.passed()

    def normal(result, error) -> None:
        expect(error is None, error)
        header = result["header"]
        expect(header and header.startswith("e2e-app-check-"), f"App Check token sent: {header}")
        functions().https_callable("appCheckToken", require_limited_use_app_check_tokens=True).call(t.step(limited))

    functions().https_callable("appCheckToken").call(t.step(normal))


def test_functions_refuse_non_json_data(t: TestContext) -> None:
    try:
        functions().https_callable("echo").call(lambda r, e: None, {"at": datetime.now(UTC)})
    except TypeError as e:
        expect("datetime" in str(e), str(e))
        t.passed()
    else:
        t.fail("a datetime must raise TypeError before anything is sent")


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

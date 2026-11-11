from datetime import UTC, datetime

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import NSObject, ObjCClass, ns_from_py, objc_property

import pyios_firebase.functions as functions_module
from pyios_firebase.functions import Functions, FunctionsErrorCode, HTTPSCallable
from pyios_firebase.util import to_python


class FakeCallableResult(NSObject):
    """Stands in for FIRHTTPSCallableResult: only has ``data``."""

    data = objc_property()


def test_call_sends_json_and_gives_python(blocks):
    native, out = Recorder(), []
    HTTPSCallable(native).call(
        lambda d, e: out.append((d, e)), {"text": "hi", "n": None, "t": (1, 2)}
    )
    name, args = native.calls[-1]
    assert name == "callWithObject_completion_"
    assert to_python(args[0]) == {"text": "hi", "n": None, "t": [1, 2]}
    result = FakeCallableResult.new()
    result.data = ns_from_py({"ok": True, "items": [1, 2]})
    fire(args[-1], result, None)
    assert out == [({"ok": True, "items": [1, 2]}, None)]
    assert type(out[0][0]["ok"]) is bool
    assert not blocks


def test_call_without_data(blocks):
    native = Recorder()
    HTTPSCallable(native).call(lambda d, e: None)
    assert native.calls[-1][0] == "callWithCompletion_"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (
            {"at": datetime.now(UTC)},
            r"at: a callable function takes JSON values; cannot send a datetime",
        ),
        ({"s": {1, 2}}, "cannot send a set"),
        ({1: "x"}, "keys must be str"),
    ],
)
def test_call_refuses_non_json_data(data, message):
    with pytest.raises(TypeError, match=message):
        HTTPSCallable(Recorder()).call(lambda d, e: None, data)


def test_errors_have_names_and_details(blocks):
    native, out = Recorder(), []
    HTTPSCallable(native).call(lambda d, e: out.append((d, e)))
    error = make_error(
        "bad input",
        FunctionsErrorCode.INVALID_ARGUMENT,
        "com.firebase.functions",
        details=ns_from_py({"field": "text", "ok": False}),
    )
    fire(native.block(), None, error)
    data, err = out[0]
    assert (
        data is None
        and err.name == "INVALID_ARGUMENT"
        and err.details == {"field": "text", "ok": False}
    )
    assert err.code == 3 and err.domain == "com.firebase.functions"


def test_functions_instances(monkeypatch):
    fake = Recorder(
        {
            "functions": "default",
            "functionsForRegion_": lambda: "regional",
            "functionsForCustomDomain_": lambda: "domain",
        }
    )
    monkeypatch.setattr(functions_module, "objc_class", lambda name: fake)
    monkeypatch.setattr(Functions, "_instances", {})
    assert Functions.functions() is Functions.functions()
    assert Functions.functions("europe-west1") is not Functions.functions()
    Functions.functions(custom_domain="https://example.com")
    assert [c[0] for c in fake.calls] == [
        "functions",
        "functionsForRegion_",
        "functionsForCustomDomain_",
    ]
    with pytest.raises(ValueError, match="not both"):
        Functions.functions("europe-west1", custom_domain="https://example.com")


def test_callable_options_and_urls(monkeypatch):
    options = Recorder({"initWithRequireLimitedUseAppCheckTokens_": "OPTIONS"})
    fake = Recorder({"alloc": lambda: options, "URLWithString_": "URL"})
    monkeypatch.setattr(functions_module, "objc_class", lambda name: fake)
    native = Recorder()
    functions = Functions(native)
    functions.https_callable("a")
    functions.https_callable("a", require_limited_use_app_check_tokens=True)
    functions.https_callable_from_url("https://x/f")
    functions.https_callable_from_url(
        "https://x/f", require_limited_use_app_check_tokens=True
    )
    assert [(c[0], c[1][-1]) for c in native.calls] == [
        ("HTTPSCallableWithName_", "a"),
        ("HTTPSCallableWithName_options_", "OPTIONS"),
        ("HTTPSCallableWithURL_", "URL"),
        ("HTTPSCallableWithURL_options_", "OPTIONS"),
    ]
    assert options.calls == [("initWithRequireLimitedUseAppCheckTokens_", (True,))] * 2


def test_error_code_values_match_the_sdk():
    assert (
        FunctionsErrorCode.INTERNAL == 13 and FunctionsErrorCode.UNAUTHENTICATED == 16
    )
    assert ObjCClass("NSNull")  # Foundation is there

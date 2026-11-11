from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import Block, NSObject, ObjCClass, ObjCInstance, ns_from_py, objc_id

import pyios_firebase.app_check as app_check_module
from pyios_firebase.app_check import (
    AppCheck,
    AppCheckErrorCode,
    AppCheckProvider,
    AppCheckToken,
    use_custom_provider,
    use_debug_provider,
)

EXPIRES = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)


def _firebase(monkeypatch, configured=False):
    """objc_class with a fake FIRApp / FIRAppCheck; the rest are real (or test fakes)."""
    app_check = Recorder()
    fir_app = SimpleNamespace(defaultApp=lambda: object() if configured else None)

    def lookup(name):
        if name == "FIRApp":
            return fir_app
        if name == "FIRAppCheck":
            return app_check
        if name == "FIRAppCheckDebugProviderFactory":
            return Recorder({"alloc": lambda: Recorder({"init": "DEBUG_FACTORY"})})
        return ObjCClass(name)

    monkeypatch.setattr(app_check_module, "objc_class", lookup)
    return app_check


def test_providers_must_be_set_before_configure(monkeypatch):
    _firebase(monkeypatch, configured=True)
    with pytest.raises(RuntimeError, match="before core.configure"):
        use_debug_provider()


def test_debug_provider(monkeypatch):
    app_check = _firebase(monkeypatch)
    use_debug_provider()
    assert app_check.calls == [("setAppCheckProviderFactory_", ("DEBUG_FACTORY",))]


class Provider(AppCheckProvider):
    def __init__(self):
        self.calls = 0

    def get_token(self, callback):
        self.calls += 1
        callback(AppCheckToken(f"token-{self.calls}", EXPIRES), None)


class Failing(AppCheckProvider):
    def get_token(self, callback):
        raise ValueError("attestation service down")


def _ask(bridge, selector):
    got = []

    def done(token_ptr, error_ptr):
        got.append(
            (
                ObjCInstance(token_ptr) if token_ptr else None,
                ObjCInstance(error_ptr) if error_ptr else None,
            )
        )

    getattr(bridge, selector)(
        Block(done, None, objc_id, objc_id)
    )  # through the ObjC runtime
    return got


def test_custom_provider_answers_firebase(monkeypatch):
    app_check = _firebase(monkeypatch)
    provider = Provider()
    use_custom_provider(provider)
    factory = app_check.calls[-1][1][0]
    bridge = factory.createProviderWithApp_(NSObject.new())  # what Firebase does
    ((token, error),) = _ask(bridge, "getTokenWithCompletion_")
    assert error is None and str(token.token) == "token-1"
    assert AppCheckToken.from_native(token) == AppCheckToken("token-1", EXPIRES)
    ((token, error),) = _ask(
        bridge, "getLimitedUseTokenWithCompletion_"
    )  # defaults to get_token
    assert str(token.token) == "token-2"


def test_custom_provider_errors_reach_firebase(monkeypatch):
    app_check = _firebase(monkeypatch)
    use_custom_provider(lambda app: Failing())  # a factory function per app
    bridge = app_check.calls[-1][1][0].createProviderWithApp_(NSObject.new())
    ((token, error),) = _ask(bridge, "getTokenWithCompletion_")
    assert token is None and "attestation service down" in str(
        error.localizedDescription
    )


def test_token_and_limited_use_token(blocks):
    native, out = Recorder(), []
    app_check = AppCheck(native)
    app_check.token(lambda t, e: out.append((t, e)), force_refresh=True)
    assert native.last("tokenForcingRefresh_completion_")[0] is True
    from conftest import FIRAppCheckToken

    nsdate = ObjCClass("NSDate").dateWithTimeIntervalSince1970_(EXPIRES.timestamp())
    fire(
        native.block("tokenForcingRefresh_completion_"),
        FIRAppCheckToken.alloc().initWithToken_expirationDate_("t", nsdate),
        None,
    )
    app_check.limited_use_token(lambda t, e: out.append((t, e)))
    fire(
        native.block("limitedUseTokenWithCompletion_"),
        None,
        make_error(
            "no network", AppCheckErrorCode.SERVER_UNREACHABLE, "com.firebase.appCheck"
        ),
    )
    assert out[0] == (AppCheckToken("t", EXPIRES), None)
    assert out[1][0] is None and out[1][1].code == AppCheckErrorCode.SERVER_UNREACHABLE
    assert not blocks


def test_token_listener_gets_notifications(blocks):
    seen = []
    listener = AppCheck(Recorder()).add_token_listener(seen.append)
    center = ObjCClass("NSNotificationCenter").defaultCenter
    center.postNotificationName_object_userInfo_(
        "FIRAppCheckAppCheckTokenDidChangeNotification",
        None,
        ns_from_py({"FIRAppCheckTokenNotificationKey": "new-token"}),
    )
    listener.remove()
    listener.remove()
    center.postNotificationName_object_userInfo_(
        "FIRAppCheckAppCheckTokenDidChangeNotification",
        None,
        ns_from_py({"FIRAppCheckTokenNotificationKey": "late"}),
    )
    assert seen == ["new-token"]
    assert not blocks


def test_auto_refresh_flag():
    native = SimpleNamespace(isTokenAutoRefreshEnabled=True)
    app_check = AppCheck(native)
    assert app_check.is_token_auto_refresh_enabled is True
    app_check.is_token_auto_refresh_enabled = False
    assert native.isTokenAutoRefreshEnabled is False

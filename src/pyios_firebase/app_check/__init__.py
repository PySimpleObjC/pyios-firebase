"""Firebase App Check: prove requests come from your real app.

Choose a provider **before** ``core.configure()``::

    from pyios_firebase import app_check, core

    if app_check.running_in_simulator():
        app_check.use_debug_provider()      # register the debug token in the console
    else:
        app_check.use_app_attest_provider() # or use_device_check_provider()
    core.configure()

Firestore, Functions, Storage, Auth and the other Firebase SDKs then attach App
Check tokens by themselves. For your own backend, get a token with
``AppCheck.app_check().token(...)``.

Needs the ``FirebaseAppCheck`` framework. App Attest also needs the App Attest
capability (``com.apple.developer.devicecheck.appattest-environment``).
"""

from __future__ import annotations

__all__ = (
    "APP_CHECK_ERROR_DOMAIN",
    "DEBUG_TOKEN_ENVIRONMENT_VARIABLE",
    "AppCheck",
    "AppCheckErrorCode",
    "AppCheckProvider",
    "AppCheckToken",
    "AppCheckTokenListener",
    "TokenCallback",
    "initialize_debug_appcheck",
    "running_in_simulator",
    "use_app_attest_provider",
    "use_custom_provider",
    "use_debug_provider",
    "use_device_check_provider",
    "use_recaptcha_provider",
)

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar, Final, cast

from rubicon.objc import NSObject, objc_method
from rubicon.objc.runtime import objc_block, objc_id

from ..types import FirebaseError, ObjCObject
from ..util import (
    error_from_pointer,
    listener_block,
    nsdate_to_datetime,
    objc_class,
    objc_instance,
    objc_protocols,
    one_shot_block,
)

APP_CHECK_ERROR_DOMAIN: Final = "com.firebase.appCheck"
"""The ``error.domain`` of App Check errors."""
DEBUG_TOKEN_ENVIRONMENT_VARIABLE: Final = "FIRAAppCheckDebugToken"
"""Set it (for example in CI) to make the debug provider use that token
instead of a random one. ``AppCheckDebugToken`` also works."""

_TOKEN_CHANGED: Final = "FIRAppCheckAppCheckTokenDidChangeNotification"
_TOKEN_KEY: Final = "FIRAppCheckTokenNotificationKey"
_PROVIDER_ERROR_DOMAIN: Final = "PyiOSFirebaseAppCheckProvider"


class AppCheckErrorCode:
    """The ``error.code`` values of App Check errors (``FIRAppCheckErrorCode``)."""

    UNKNOWN: Final = 0
    SERVER_UNREACHABLE: Final = 1
    """No network, or the App Check server did not answer."""
    INVALID_CONFIGURATION: Final = 2
    """The provider or the Firebase project is not set up right."""
    KEYCHAIN: Final = 3
    """The keychain could not store the token."""
    UNSUPPORTED: Final = 4
    """The provider does not work here (for example App Attest in the Simulator)."""


@dataclass(frozen=True)
class AppCheckToken:
    """An App Check token."""

    token: str
    """The token: send it in the ``X-Firebase-AppCheck`` header to your backend."""
    expiration_date: datetime
    """When it expires (UTC)."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> AppCheckToken:
        """Copy a native ``FIRAppCheckToken``.

        Args:
            native: the ``FIRAppCheckToken``.
        """
        expiration = nsdate_to_datetime(native.expirationDate)
        return cls(str(native.token), expiration or datetime.fromtimestamp(0, UTC))

    def to_native(self) -> ObjCObject:
        """Make the native ``FIRAppCheckToken``."""
        date = objc_class("NSDate").dateWithTimeIntervalSince1970_(
            self.expiration_date.timestamp()
        )
        return (
            objc_class("FIRAppCheckToken")
            .alloc()
            .initWithToken_expirationDate_(self.token, date)
        )


def running_in_simulator() -> bool:
    """True in the iOS Simulator, where App Attest and DeviceCheck do not work
    (use the debug provider there)."""
    return "SIMULATOR_DEVICE_NAME" in os.environ or "SIMULATOR_UDID" in os.environ


def _before_configure() -> None:
    if objc_class("FIRApp").defaultApp() is not None:
        raise RuntimeError(
            "set the App Check provider before core.configure(): "
            "Firebase reads it once, when the app is configured"
        )


def _set_factory(factory: ObjCObject) -> None:
    _before_configure()
    _factory_holder["factory"] = factory  # Firebase keeps it too; this makes sure
    objc_class("FIRAppCheck").setAppCheckProviderFactory_(factory)


_factory_holder: dict[str, ObjCObject] = {}


def use_debug_provider() -> None:
    """Use the debug provider: for the Simulator, development and CI.

    On first run it prints ``Firebase App Check debug token: '...'`` in the
    Xcode console; add that token in the Firebase console (App Check, your app,
    Manage debug tokens). In CI, set ``DEBUG_TOKEN_ENVIRONMENT_VARIABLE`` to a
    registered token. Never ship it: anyone with the token passes App Check.

    Raises:
        RuntimeError: ``core.configure()`` was already called.
    """
    _set_factory(objc_class("FIRAppCheckDebugProviderFactory").alloc().init())


def initialize_debug_appcheck() -> None:
    """The 0.1 name of ``use_debug_provider``."""
    use_debug_provider()


def use_device_check_provider() -> None:
    """Use Apple's DeviceCheck (the default provider). Works on real devices
    with iOS 11+; not in the Simulator.

    Raises:
        RuntimeError: ``core.configure()`` was already called.
    """
    _set_factory(objc_class("FIRDeviceCheckProviderFactory").alloc().init())


def use_app_attest_provider() -> None:
    """Use Apple's App Attest: the strongest attestation, on real devices with
    iOS 14+. Needs the App Attest capability; not in the Simulator.

    Raises:
        RuntimeError: ``core.configure()`` was already called.
    """
    _set_factory(objc_class("FIRAppAttestProviderFactory").alloc().init())


def use_recaptcha_provider(site_key: str) -> None:
    """Use reCAPTCHA Enterprise. Needs the reCAPTCHA Enterprise SDK in the app.

    Args:
        site_key: the reCAPTCHA Enterprise site key for iOS.

    Raises:
        RuntimeError: ``core.configure()`` was already called.
    """
    _set_factory(
        objc_class("FIRRecaptchaProviderFactory").alloc().initWithSiteKey_(site_key)
    )


# ---- custom providers, written in Python -----------------------------------------

TokenCallback = Callable[[AppCheckToken | None, str | None], None]
"""``(token, None)`` or ``(None, error_message)``."""


class AppCheckProvider(ABC):
    """A custom App Check provider, written in Python: for example tokens from
    your own attestation service. Pass it to ``use_custom_provider``.

    ::

        class MyProvider(AppCheckProvider):
            def get_token(self, callback):
                my_service.fetch(lambda token, expires: callback(AppCheckToken(token, expires), None))

    Firebase may call these methods on a background thread.
    """

    @abstractmethod
    def get_token(self, callback: TokenCallback) -> None:
        """Make a token, then call ``callback`` exactly once.

        Args:
            callback: call it with ``(AppCheckToken, None)``, or
                ``(None, "what went wrong")``.
        """

    def get_limited_use_token(self, callback: TokenCallback) -> None:
        """Make a single-use token (for replay protection). By default, the
        same as ``get_token``.

        Args:
            callback: call it with ``(AppCheckToken, None)``, or
                ``(None, "what went wrong")``.
        """
        self.get_token(callback)


def _answer(handler: Any) -> TokenCallback:
    """A Python callback that answers Firebase's completion block once."""
    state = {"done": False}

    def callback(token: AppCheckToken | None, error: str | None) -> None:
        if state["done"]:
            return
        state["done"] = True
        if token is not None:
            handler(token.to_native(), None)
            return
        nserror = objc_class("NSError").errorWithDomain_code_userInfo_(
            _PROVIDER_ERROR_DOMAIN,
            AppCheckErrorCode.UNKNOWN,
            {"NSLocalizedDescription": error or "the App Check provider gave no token"},
        )
        handler(None, nserror)

    return callback


# the Python providers, by the address of their Objective-C bridge
_providers: dict[int, AppCheckProvider] = {}


def _key(obj: ObjCObject) -> int:
    return int(obj.ptr.value or 0)


def _bridge_call(bridge: ObjCObject, method: str, handler: Any) -> None:
    """Run the Python provider's ``method`` for a call Firebase made on ``bridge``."""
    callback = _answer(handler)
    provider = _providers.get(_key(bridge))
    if provider is None:
        callback(None, "the App Check provider is gone")
        return
    try:
        getattr(provider, method)(callback)
    except Exception as e:  # noqa: BLE001 - Firebase must always get an answer
        callback(None, f"{type(e).__name__}: {e}")


class PyAppCheckProviderBridge(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("FIRAppCheckProvider")
):
    """Lets Firebase call a Python ``AppCheckProvider``.

    Rubicon reads these methods' annotations to build their Objective-C
    signatures: parameters must be annotated with ctypes types.
    """

    @objc_method
    def getTokenWithCompletion_(self, handler: objc_block) -> None:
        """Firebase asks for a token."""
        _bridge_call(self, "get_token", handler)

    @objc_method
    def getLimitedUseTokenWithCompletion_(self, handler: objc_block) -> None:
        """Firebase asks for a limited-use token."""
        _bridge_call(self, "get_limited_use_token", handler)


class PyAppCheckProviderFactory(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("FIRAppCheckProviderFactory")
):
    """Lets Firebase ask Python for a provider for each Firebase app."""

    @objc_method
    def createProviderWithApp_(self, app: objc_id) -> objc_id:
        """Firebase asks for the provider of ``app``."""
        make = _factories.get(_key(self))
        if make is None:
            return cast("objc_id", None)
        bridge = PyAppCheckProviderBridge.alloc().init()
        _providers[_key(bridge)] = make(objc_instance(app))
        _bridges.append(bridge)  # Firebase holds it; keep the Python side alive too
        return cast("objc_id", bridge)


_factories: dict[int, Callable[[ObjCObject], AppCheckProvider]] = {}
_bridges: list[ObjCObject] = []


def use_custom_provider(
    provider: AppCheckProvider | Callable[[ObjCObject], AppCheckProvider],
) -> None:
    """Use a custom provider written in Python.

    Args:
        provider: an ``AppCheckProvider`` for every Firebase app, or a function
            that gets the native ``FIRApp`` and returns the provider for it.

    Raises:
        RuntimeError: ``core.configure()`` was already called.
    """
    factory = PyAppCheckProviderFactory.alloc().init()
    if isinstance(provider, AppCheckProvider):
        instance = provider
        _factories[_key(factory)] = lambda _app: instance
    else:
        _factories[_key(factory)] = provider
    _set_factory(factory)


# ---- tokens ---------------------------------------------------------------------


class AppCheckTokenListener:
    """Given back by ``AppCheck.add_token_listener``. Call ``remove()`` to stop.

    Args:
        observer: the native ``NSNotificationCenter`` observer.
        release: releases the listener's callback block.
    """

    def __init__(self, observer: ObjCObject, release: Callable[[], None]) -> None:
        self._observer: ObjCObject | None = observer
        self._release = release

    def remove(self) -> None:
        """Stop the updates. Safe to call more than once."""
        if self._observer is None:
            return
        objc_class("NSNotificationCenter").defaultCenter.removeObserver_(self._observer)
        self._observer = None
        self._release()


class AppCheck:
    """App Check for the default Firebase app. Get it with ``AppCheck.app_check()``.

    Args:
        native: the native ``FIRAppCheck``.
    """

    _instance: ClassVar[AppCheck | None] = None

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def app_check(cls) -> AppCheck:
        """The shared instance (after ``core.configure()``)."""
        if cls._instance is None:
            cls._instance = cls(objc_class("FIRAppCheck").appCheck())
        return cls._instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRAppCheck``."""
        return self._native

    @property
    def is_token_auto_refresh_enabled(self) -> bool:
        """Whether App Check refreshes the token before it expires (the default
        comes from ``FirebaseAppCheckTokenAutoRefreshEnabled`` in Info.plist,
        else Firebase's data collection setting)."""
        value = self._native.isTokenAutoRefreshEnabled
        return bool(value() if callable(value) else value)

    @is_token_auto_refresh_enabled.setter
    def is_token_auto_refresh_enabled(self, enabled: bool) -> None:
        self._native.isTokenAutoRefreshEnabled = bool(enabled)

    def token(
        self,
        callback: Callable[[AppCheckToken | None, FirebaseError | None], None],
        force_refresh: bool = False,
    ) -> None:
        """Get an App Check token, for example to call your own backend.

        The token is cached, also across app launches, until it is about to
        expire: the provider is only asked again then, or with ``force_refresh``.

        Args:
            callback: gets ``(AppCheckToken, None)``, or ``(None, error)``.
            force_refresh: get a new token even if the cached one is valid.
        """

        def done(token_ptr: Any, error_ptr: Any) -> None:
            if error_ptr or not token_ptr:
                callback(None, error_from_pointer(error_ptr))
                return
            callback(AppCheckToken.from_native(objc_instance(token_ptr)), None)

        self._native.tokenForcingRefresh_completion_(
            bool(force_refresh), one_shot_block(done, objc_id, objc_id)
        )

    def limited_use_token(
        self, callback: Callable[[AppCheckToken | None, FirebaseError | None], None]
    ) -> None:
        """Get a limited-use (single-use) token, for backends with replay
        protection. It is not cached and does not affect ``token``.

        Args:
            callback: gets ``(AppCheckToken, None)``, or ``(None, error)``.
        """

        def done(token_ptr: Any, error_ptr: Any) -> None:
            if error_ptr or not token_ptr:
                callback(None, error_from_pointer(error_ptr))
                return
            callback(AppCheckToken.from_native(objc_instance(token_ptr)), None)

        self._native.limitedUseTokenWithCompletion_(
            one_shot_block(done, objc_id, objc_id)
        )

    def add_token_listener(
        self, listener: Callable[[str], None]
    ) -> AppCheckTokenListener:
        """Listen for new App Check tokens (each refresh), on the main thread.

        Args:
            listener: gets the new token string.

        Returns:
            An ``AppCheckTokenListener``. Call ``.remove()`` to stop.
        """

        def on_notification(notification_ptr: Any) -> None:
            notification = objc_instance(notification_ptr)
            user_info = notification.userInfo
            token = None if user_info is None else user_info.objectForKey_(_TOKEN_KEY)
            if token is not None:
                listener(str(token))

        block, release = listener_block(on_notification, objc_id)
        observer = objc_class(
            "NSNotificationCenter"
        ).defaultCenter.addObserverForName_object_queue_usingBlock_(
            _TOKEN_CHANGED, None, objc_class("NSOperationQueue").mainQueue, block
        )
        return AppCheckTokenListener(observer, release)

    @staticmethod
    def debug_token() -> str:
        """The debug provider's token: the ``DEBUG_TOKEN_ENVIRONMENT_VARIABLE``
        token if set, else this device's local one. Register it in the Firebase
        console. Works whichever provider is in use (after ``core.configure()``).

        Returns:
            The token.
        """
        provider = (
            objc_class("FIRAppCheckDebugProvider")
            .alloc()
            .initWithApp_(objc_class("FIRApp").defaultApp())
        )
        return str(provider.currentDebugToken())

"""Cloud Functions for Firebase: call HTTPS callable functions.

    from pyios_firebase.functions import Functions

    def on_result(data, error):
        if error is not None:
            print(error.name, error.description, error.details)
            return
        print(data)

    Functions.functions().https_callable("addMessage").call(on_result, {"text": "Hello"})

``data`` is what the function returned, as Python values. Auth and App Check
tokens are attached by the SDK when those products are in the app.

Streaming callables (``stream()``) are Swift-only in the Firebase SDK, so they
are not available from Python.

Needs the ``FirebaseFunctions`` framework.
"""

from __future__ import annotations

__all__ = (
    "FUNCTIONS_ERROR_DETAILS_KEY",
    "FUNCTIONS_ERROR_DOMAIN",
    "CallCallback",
    "Functions",
    "FunctionsError",
    "FunctionsErrorCode",
    "HTTPSCallable",
)

import math
from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Final

from rubicon.objc import ns_from_py, objc_id

from ..types import FirebaseError, ObjCObject
from ..util import nserror_to_dict, objc_class, objc_instance, one_shot_block, to_python

FUNCTIONS_ERROR_DOMAIN: Final = "com.firebase.functions"
"""The ``error.domain`` of errors from function calls."""
FUNCTIONS_ERROR_DETAILS_KEY: Final = "details"
"""The ``userInfo`` key the SDK uses for an ``HttpsError``'s ``details``."""


class FunctionsErrorCode:
    """The ``error.code`` values of function call errors (``FIRFunctionsErrorCode``).

    They match the ``HttpsError`` codes a function throws (``"invalid-argument"``
    is ``INVALID_ARGUMENT``, and so on).
    """

    OK: Final = 0
    CANCELLED: Final = 1
    UNKNOWN: Final = 2
    INVALID_ARGUMENT: Final = 3
    DEADLINE_EXCEEDED: Final = 4
    """No answer within ``HTTPSCallable.timeout_interval``."""
    NOT_FOUND: Final = 5
    """No function with that name (or URL, or region)."""
    ALREADY_EXISTS: Final = 6
    PERMISSION_DENIED: Final = 7
    RESOURCE_EXHAUSTED: Final = 8
    FAILED_PRECONDITION: Final = 9
    ABORTED: Final = 10
    OUT_OF_RANGE: Final = 11
    UNIMPLEMENTED: Final = 12
    INTERNAL: Final = 13
    """The function failed with an unexpected error (or threw a plain Error)."""
    UNAVAILABLE: Final = 14
    DATA_LOSS: Final = 15
    UNAUTHENTICATED: Final = 16


_CODE_NAMES: Final[dict[int, str]] = {
    value: name
    for name, value in vars(FunctionsErrorCode).items()
    if isinstance(value, int)
}


class FunctionsError(FirebaseError):
    """An error from a function call."""

    name: str
    """The ``FunctionsErrorCode`` name of ``code`` (for example
    ``"INVALID_ARGUMENT"``), or ``""`` for errors from other domains."""
    details: Any
    """What the function attached to its ``HttpsError`` (as Python values), or ``None``."""


def _error_to_python(error: ObjCObject) -> FunctionsError:
    result = FunctionsError(nserror_to_dict(error) or {})
    result.name = (
        _CODE_NAMES.get(result.code, "")
        if result.domain == FUNCTIONS_ERROR_DOMAIN
        else ""
    )
    details = error.userInfo.objectForKey_(FUNCTIONS_ERROR_DETAILS_KEY)
    result.details = to_python(details) if details is not None else None
    return result


_INT32: Final = 2**31
_EXACT_DOUBLE: Final = 2**53


def _int_to_number(value: int) -> Any:
    """An ``NSNumber`` the SDK sends as a plain JSON number when it can.

    Rubicon makes every ``int`` a ``long long``, and the SDK sends those as an
    ``Int64Value`` object (``{"@type": ..., "value": "5"}``) that some servers
    (the Python Functions SDK) do not unwrap. Ints that fit a 32-bit int, or a
    double exactly, go as plain numbers; bigger ones keep the wrapper so they
    arrive exactly.
    """
    number = objc_class("NSNumber")
    if -_INT32 <= value < _INT32:
        return number.numberWithInt_(value)
    if -_EXACT_DOUBLE <= value <= _EXACT_DOUBLE:
        return number.numberWithDouble_(float(value))  # JSON writes it with no ".0"
    return value


def _to_json_value(value: Any, path: str) -> Any:
    """Python data for a callable: JSON values only (the protocol is JSON)."""
    if value is None:
        return objc_class("NSNull").null()  # NSDictionary/NSArray cannot hold nil
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return _int_to_number(value)
    if isinstance(value, float) and not math.isfinite(value):
        # the SDK's JSONSerialization raises an Objective-C exception on these,
        # which aborts the app
        raise TypeError(f"{path or 'data'}: JSON cannot carry {value!r}")
    if isinstance(value, str | float):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{path or 'data'}: keys must be str, not {type(key).__name__} ({key!r})"
                )
            result[key] = _to_json_value(item, f"{path}.{key}" if path else key)
        return result
    if isinstance(value, list | tuple):
        return [_to_json_value(item, f"{path}[{i}]") for i, item in enumerate(value)]
    raise TypeError(
        f"{path or 'data'}: a callable function takes JSON values; cannot send a "
        f"{type(value).__name__} ({value!r})"
    )


CallCallback = Callable[[Any, FunctionsError | None], None]
"""``(data, error)``: the function's return value (``None`` on error), and the error."""


class HTTPSCallable:
    """One callable function. Get it with ``Functions.https_callable``.

    Args:
        callable_: the native ``FIRHTTPSCallable``.
    """

    def __init__(self, callable_: ObjCObject) -> None:
        self._callable = callable_

    @property
    def timeout_interval(self) -> float:
        """Seconds before a call fails with ``DEADLINE_EXCEEDED`` (default 70)."""
        return float(self._callable.timeoutInterval)

    @timeout_interval.setter
    def timeout_interval(self, seconds: float) -> None:
        self._callable.timeoutInterval = float(seconds)

    def call(self, callback: CallCallback, data: Any = None) -> None:
        """Call the function.

        Args:
            callback: gets ``(result, None)``, or ``(None, FunctionsError)``.
                ``result`` is what the function returned, as Python values.
            data: what to send: JSON-like Python values (dict, list, tuple,
                str, number, bool, ``None``), or nothing.

        Raises:
            TypeError: ``data`` holds a value JSON cannot carry (for example a
                ``datetime``, a ``set``, ``nan`` or ``inf``). Nothing is sent.
        """

        def on_done(result_ptr: Any, error_ptr: Any) -> None:
            if error_ptr:
                callback(None, _error_to_python(objc_instance(error_ptr)))
                return
            raw = objc_instance(result_ptr).data if result_ptr else None
            callback(to_python(raw) if raw is not None else None, None)

        if data is None:
            self._callable.callWithCompletion_(
                one_shot_block(on_done, objc_id, objc_id)
            )
        else:
            payload = ns_from_py(_to_json_value(data, ""))
            self._callable.callWithObject_completion_(
                payload, one_shot_block(on_done, objc_id, objc_id)
            )


class Functions:
    """Cloud Functions for one region (or custom domain). Get it with
    ``Functions.functions()``.

    Args:
        functions: the native ``FIRFunctions``.
    """

    # shared instances, by region or custom domain (None = the default region)
    _instances: ClassVar[dict[tuple[str, str | None], Functions]] = {}

    def __init__(self, functions: ObjCObject) -> None:
        self._functions = functions

    @classmethod
    def functions(
        cls, region: str | None = None, custom_domain: str | None = None
    ) -> Functions:
        """The shared ``Functions`` for a region or a custom domain.

        Args:
            region: the region the functions are deployed to, for example
                ``"europe-west1"``. ``None`` means ``us-central1``.
            custom_domain: a custom domain the functions are served from (Firebase
                Hosting rewrites), for example ``"https://example.com"``. Not
                together with ``region``.

        Returns:
            The same ``Functions`` for the same arguments.

        Raises:
            ValueError: both ``region`` and ``custom_domain`` are given.
        """
        if region is not None and custom_domain is not None:
            raise ValueError("give a region or a custom_domain, not both")
        key = (
            ("domain", custom_domain)
            if custom_domain is not None
            else ("region", region)
        )
        instance = cls._instances.get(key)
        if instance is None:
            fir = objc_class("FIRFunctions")
            if custom_domain is not None:
                native = fir.functionsForCustomDomain_(custom_domain)
            elif region is not None:
                native = fir.functionsForRegion_(region)
            else:
                native = fir.functions()
            instance = cls._instances[key] = cls(native)
        return instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRFunctions``."""
        return self._functions

    def use_emulator(self, host: str = "127.0.0.1", port: int = 5001) -> None:
        """Send this instance's calls to the local Functions emulator. Call it
        before any call; use it only in development and test builds.

        Args:
            host: the emulator's host. ``"127.0.0.1"`` works in the iOS Simulator;
                on a device, use the Mac's LAN address.
            port: the emulator's port (``firebase emulators:start`` uses 5001).
        """
        self._functions.useEmulatorWithHost_port_(host, int(port))

    def https_callable(
        self, name: str, require_limited_use_app_check_tokens: bool = False
    ) -> HTTPSCallable:
        """A callable function, by name.

        Args:
            name: the function's exported name, for example ``"addMessage"``.
            require_limited_use_app_check_tokens: send a single-use App Check
                token, for functions with ``enforceAppCheck`` and
                ``consumeAppCheckToken`` (replay protection).

        Returns:
            An ``HTTPSCallable``. Run it with ``call``.
        """
        if require_limited_use_app_check_tokens:
            options = (
                objc_class("FIRHTTPSCallableOptions")
                .alloc()
                .initWithRequireLimitedUseAppCheckTokens_(True)
            )
            return HTTPSCallable(
                self._functions.HTTPSCallableWithName_options_(name, options)
            )
        return HTTPSCallable(self._functions.HTTPSCallableWithName_(name))

    def https_callable_from_url(
        self, url: str, require_limited_use_app_check_tokens: bool = False
    ) -> HTTPSCallable:
        """A callable function, by its full URL (for example a Cloud Run URL).

        Args:
            url: the function's URL.
            require_limited_use_app_check_tokens: send a single-use App Check token.

        Returns:
            An ``HTTPSCallable``.
        """
        native_url = objc_class("NSURL").URLWithString_(url)
        if require_limited_use_app_check_tokens:
            options = (
                objc_class("FIRHTTPSCallableOptions")
                .alloc()
                .initWithRequireLimitedUseAppCheckTokens_(True)
            )
            return HTTPSCallable(
                self._functions.HTTPSCallableWithURL_options_(native_url, options)
            )
        return HTTPSCallable(self._functions.HTTPSCallableWithURL_(native_url))

"""Helpers shared by the auth modules: block builders and value readers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from rubicon.objc import Block, objc_id

from ..types import ObjCObject
from ..util import objc_class, objc_instance, one_shot_block, to_python
from .errors import AuthError, auth_error_from_pointer, simple_auth_error

T = TypeVar("T")


def flag(obj: ObjCObject, name: str) -> bool:
    """Read a Swift ``Bool`` property, whichever way Rubicon exposes it.

    A plain getter is an attribute; a custom getter (``getter=isX``) is a
    method, and reading it without calling it would always be truthy.
    """
    value = getattr(obj, name)
    return bool(value() if callable(value) else value)


def text(value: object) -> str | None:
    """``str(value)``, or ``None`` for ``None``."""
    return None if value is None else str(value)


def url_text(url: ObjCObject | None) -> str | None:
    """An ``NSURL`` as a string, or ``None``."""
    return None if url is None else str(url.absoluteString)


def result_block(
    callback: Callable[[T | None, AuthError | None], None] | None,
    wrap: Callable[[ObjCObject], T],
) -> Block:
    """Completion block for ``(result, NSError)``: ``callback(wrap(result), error)``."""

    def done(result_ptr: Any, error_ptr: Any) -> None:
        if callback is None:
            return
        error = auth_error_from_pointer(error_ptr)
        if error is not None or not result_ptr:
            callback(None, error)
            return
        try:
            result = wrap(objc_instance(result_ptr))
        except Exception as e:  # noqa: BLE001 - must always answer the caller
            # an exception here would be swallowed by the SDK's block, and the
            # caller would wait forever
            callback(None, simple_auth_error(f"could not read the result: {e!r}"))
            return
        callback(result, None)

    return one_shot_block(done, objc_id, objc_id)


def error_block(callback: Callable[[AuthError | None], None] | None) -> Block:
    """Completion block for ``(NSError)``: ``callback(error)``."""

    def done(error_ptr: Any) -> None:
        if callback is not None:
            callback(auth_error_from_pointer(error_ptr))

    return one_shot_block(done, objc_id)


def string_block(callback: Callable[[str | None, AuthError | None], None]) -> Block:
    """Completion block for ``(NSString, NSError)``."""
    return result_block(callback, lambda value: str(value))


def registered_url_schemes() -> set[str]:
    """The URL schemes in the app's ``Info.plist`` (``CFBundleURLTypes``), lower case."""
    url_types = objc_class("NSBundle").mainBundle.objectForInfoDictionaryKey_(
        "CFBundleURLTypes"
    )
    schemes: set[str] = set()
    for url_type in to_python(url_types) or []:
        for scheme in (
            url_type.get("CFBundleURLSchemes", []) if isinstance(url_type, dict) else []
        ):
            schemes.add(str(scheme).lower())
    return schemes


def missing_callback_scheme(auth_native: ObjCObject) -> str | None:
    """Why phone and web sign-in cannot start, or ``None`` if they can.

    The Firebase SDK stops the whole app (``fatalError``) when the callback URL
    scheme is not in ``Info.plist``. This checks the same thing first: the
    reversed client ID if it is registered, else ``app-<GOOGLE_APP_ID>``.
    """
    app = auth_native.app
    options = app.options if app is not None else None
    if options is None:
        return "Firebase is not configured: call core.configure() first"
    schemes = registered_url_schemes()
    reversed_client_id = None
    if options.clientID is not None:
        reversed_client_id = ".".join(reversed(str(options.clientID).split(".")))
        if reversed_client_id.lower() in schemes:
            return None
    if options.googleAppID is None:
        return "the Firebase options have no GOOGLE_APP_ID"
    app_scheme = "app-" + str(options.googleAppID).replace(":", "-")
    if app_scheme.lower() in schemes:
        return None
    wanted = (
        app_scheme
        if reversed_client_id is None
        else f"{reversed_client_id} (or {app_scheme})"
    )
    return (
        f"add the URL scheme {wanted} to CFBundleURLTypes in Info.plist: Firebase Auth "
        "needs it for phone and web sign-in, and stops the app without it"
    )

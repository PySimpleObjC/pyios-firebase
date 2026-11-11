"""Sign in with Apple, then Firebase Auth.

    from pyios_firebase.auth.apple import start_apple_sign_in

    def on_signed_in(result, error):
        if error is not None:
            if not error.cancelled:
                print(error.message or error.description)
            return
        print("Signed in:", result.user.uid, result.first_name)

    start_apple_sign_in(on_signed_in)

Apple shares the name (and a real or relay email) only the FIRST time a user
signs in to the app; later sign-ins give ``""`` for those. The name is kept on
the device until a Firebase sign-in carries it.

Needs the ``com.apple.developer.applesignin`` entitlement and the Apple
provider enabled in the Firebase console (Authentication, Sign-in method).
"""

from __future__ import annotations

__all__ = (
    "AUTHORIZATION_ERROR_CANCELED",
    "AUTHORIZATION_ERROR_DOMAIN",
    "AUTHORIZATION_ERROR_UNKNOWN",
    "AppleCredential",
    "AppleSignInResult",
    "get_apple_credential",
    "start_apple_sign_in",
)

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, cast

from rubicon.objc import NSObject, ObjCInstance, ObjCProtocol, ns_from_py, objc_method
from rubicon.objc.runtime import load_library, objc_id

from ..types import ObjCObject
from ..util import objc_class
from ._apple_name_cache import AppleNameCache
from ._ui import key_window
from .auth import Auth
from .credentials import OAuthCredential, OAuthProvider
from .errors import AuthError, auth_error_from_nserror, simple_auth_error
from .results import AuthDataResult

_auth_services = load_library("AuthenticationServices")


def _string_constant(name: str, fallback: str) -> str:
    """An NSString constant exported by AuthenticationServices."""
    try:
        value = objc_id.in_dll(_auth_services, name)
    except ValueError:
        return fallback
    return str(ObjCInstance(value)) if value.value else fallback


SCOPE_FULL_NAME: Final = _string_constant("ASAuthorizationScopeFullName", "full_name")
SCOPE_EMAIL: Final = _string_constant("ASAuthorizationScopeEmail", "email")
AUTHORIZATION_ERROR_DOMAIN: Final = _string_constant(
    "ASAuthorizationErrorDomain", "com.apple.AuthenticationServices.AuthorizationError"
)
"""The error domain of Apple's sign-in errors."""
AUTHORIZATION_ERROR_UNKNOWN: Final = 1000
"""Set-up problems, or no Apple Account on the device (also: the user closed
iOS's "sign in to your Apple Account" alert)."""
AUTHORIZATION_ERROR_CANCELED: Final = 1001
"""``ASAuthorizationErrorCanceled``: the user closed the Apple sheet."""

NOT_SIGNED_IN_MESSAGE: Final = (
    "Sign in with Apple didn't finish. Check that you're signed in to your "
    "Apple Account in Settings, then try again"
)

NSUTF8StringEncoding: Final = 4


@dataclass(frozen=True)
class AppleCredential:
    """What Sign in with Apple gave, ready for Firebase."""

    credential: OAuthCredential
    """The Firebase credential (provider ``"apple.com"``)."""
    apple_user: str
    """Apple's stable ID for the user in this app."""
    first_name: str
    """The given name: only on the first sign-in to the app, else ``""``
    (or the name kept from an earlier, failed attempt)."""
    last_name: str
    """The family name: same rules as ``first_name``."""
    email: str
    """The email (real or private relay): only on the first sign-in, else ``""``."""
    authorization_code: str
    """A short-lived code: pass it to ``Auth.revoke_token`` before deleting the
    account (App Store rule)."""


class AppleSignInResult(AuthDataResult):
    """A Firebase sign-in with Apple: an ``AuthDataResult`` plus what Apple shared.

    Args:
        native: the native ``FIRAuthDataResult``.
        apple: what Apple gave for this sign-in.
    """

    def __init__(self, native: ObjCObject, apple: AppleCredential) -> None:
        super().__init__(native)
        self.apple = apple
        """What Apple gave (names, email, authorization code)."""

    @property
    def first_name(self) -> str:
        """The given name Apple shared (first sign-in only), else ``""``."""
        return self.apple.first_name

    @property
    def last_name(self) -> str:
        """The family name Apple shared (first sign-in only), else ``""``."""
        return self.apple.last_name


AppleCredentialCallback = Callable[[AppleCredential | None, AuthError | None], None]
AppleSignInCallback = Callable[[AppleSignInResult | None, AuthError | None], None]

_names: AppleNameCache | None = None  # made on first use (NSUserDefaults)
# the sign-ins in progress, by delegate: UIKit keeps the delegate only weakly
_pending: dict[int, dict[str, Any]] = {}


def _key(delegate: ObjCObject) -> int:
    """The delegate's address: the key of its sign-in in ``_pending``."""
    return int(delegate.ptr.value or 0)


def _name_cache() -> AppleNameCache:
    global _names
    if _names is None:
        _names = AppleNameCache()
    return _names


def _protocols(*names: str) -> list[ObjCProtocol]:
    found = []
    for name in names:
        try:
            found.append(ObjCProtocol(name))
        except NameError:
            pass
    return found


def _apple_error(error: ObjCObject) -> AuthError:
    result = auth_error_from_nserror(error)
    apple = result.domain == AUTHORIZATION_ERROR_DOMAIN
    result.cancelled = result.cancelled or (
        apple and result.code == AUTHORIZATION_ERROR_CANCELED
    )
    # 1000 covers "no Apple Account on this device" (and set-up problems):
    # not a network failure, so don't let the app say it is
    if apple and result.code == AUTHORIZATION_ERROR_UNKNOWN:
        result.message = NOT_SIGNED_IN_MESSAGE
    return result


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _utf8(data: ObjCObject | None) -> str:
    if data is None:
        return ""
    return str(
        objc_class("NSString")
        .alloc()
        .initWithData_encoding_(data, NSUTF8StringEncoding)
    )


class PyAppleSignInDelegate(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject,
    protocols=_protocols(
        "ASAuthorizationControllerDelegate",
        "ASAuthorizationControllerPresentationContextProviding",
    ),
):
    """The ``ASAuthorizationController`` delegate and presentation context.

    Rubicon reads these methods' annotations to build their Objective-C
    signatures: parameters must be annotated with ctypes types (``objc_id``),
    not Python types.
    """

    @objc_method
    def presentationAnchorForAuthorizationController_(
        self, controller: objc_id
    ) -> objc_id:
        """The window the Apple sheet is shown over: the key window."""
        # objc_id is what Rubicon needs for the signature; the value is an object
        return cast("objc_id", key_window())

    @objc_method
    def authorizationController_didCompleteWithAuthorization_(
        self, controller: objc_id, authorization: objc_id
    ) -> None:
        """Apple signed the user in: turn the identity token into a credential."""
        state = _pending.pop(_key(self), None)
        if state is None:
            return
        callback: AppleCredentialCallback = state["callback"]
        auth: ObjCObject = (
            authorization  # an object at runtime (see the class docstring)
        )
        try:
            credential = auth.credential
            if not credential.isKindOfClass(
                objc_class("ASAuthorizationAppleIDCredential")
            ):
                callback(None, simple_auth_error("Unexpected credential type"))
                return
            id_token = _utf8(credential.identityToken)
            if not id_token:
                callback(None, simple_auth_error("Apple returned no identity token"))
                return
            apple_user = _text(credential.user)
            name = credential.fullName
            sent_first = _text(name.givenName) if name is not None else ""
            sent_last = _text(name.familyName) if name is not None else ""
            # Apple sends the name only once: reuse the one an earlier,
            # failed attempt saved
            first, last = _name_cache().resolve(apple_user, sent_first, sent_last)
            result = AppleCredential(
                credential=OAuthProvider.apple_credential(
                    id_token, state["raw_nonce"], first, last
                ),
                apple_user=apple_user,
                first_name=first,
                last_name=last,
                email=_text(credential.email),
                authorization_code=_utf8(credential.authorizationCode),
            )
        except Exception as e:  # noqa: BLE001 - must always answer the caller
            callback(None, simple_auth_error(str(e)))
            return
        callback(result, None)

    @objc_method
    def authorizationController_didCompleteWithError_(
        self, controller: objc_id, error: objc_id
    ) -> None:
        """Apple sign-in failed or was cancelled: report it."""
        state = _pending.pop(_key(self), None)
        if state is not None:
            state["callback"](None, _apple_error(error))


def get_apple_credential(callback: AppleCredentialCallback) -> None:
    """Show the Sign in with Apple sheet and give back a Firebase credential,
    without signing in to Firebase (for example to link Apple to the current
    user, or to re-authenticate before deleting the account).

    Args:
        callback: gets ``(AppleCredential, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user closed the sheet;
            ``error.message``, when not ``""``, is a sentence for the user.
    """
    # Apple signs SHA-256(nonce); Firebase checks it against the raw nonce
    raw_nonce = secrets.token_urlsafe(32)
    request = (
        objc_class("ASAuthorizationAppleIDProvider").alloc().init().createRequest()
    )
    request.requestedScopes = ns_from_py([SCOPE_FULL_NAME, SCOPE_EMAIL])
    request.nonce = hashlib.sha256(raw_nonce.encode()).hexdigest()

    delegate = PyAppleSignInDelegate.alloc().init()
    controller = (
        objc_class("ASAuthorizationController")
        .alloc()
        .initWithAuthorizationRequests_(ns_from_py([request]))
    )
    controller.delegate = delegate  # weak in UIKit: _pending keeps both alive
    controller.presentationContextProvider = delegate
    _pending[_key(delegate)] = {
        "callback": callback,
        "raw_nonce": raw_nonce,
        "delegate": delegate,
        "controller": controller,
    }
    controller.performRequests()


def start_apple_sign_in(
    callback: AppleSignInCallback, auth: Auth | None = None
) -> None:
    """Show the Sign in with Apple sheet, then sign in to Firebase.

    Args:
        callback: gets ``(AppleSignInResult, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user closed the sheet: not a
            failure to report. ``error.message``, when not ``""``, is a
            sentence to show to the user.
        auth: the ``Auth`` to sign in to (default: ``Auth.auth()``).
    """

    def got_credential(apple: AppleCredential | None, error: AuthError | None) -> None:
        if apple is None:
            callback(None, error)
            return

        def signed_in(
            result: AuthDataResult | None, sign_in_error: AuthError | None
        ) -> None:
            if result is None:
                callback(None, sign_in_error)
                return
            _name_cache().forget(apple.apple_user)  # Firebase has the name now
            callback(AppleSignInResult(result._native, apple), None)

        (auth or Auth.auth()).sign_in_with_credential(apple.credential, signed_in)

    get_apple_credential(got_credential)

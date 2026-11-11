"""Facebook Login, then Firebase Auth.

    from pyios_firebase.auth import facebook

    facebook.initialize_facebook()          # once, at app start

    def on_signed_in(result, error):
        if error is not None:
            if not error.cancelled:
                print("Sign-in failed:", error.description)
            return
        print("Signed in:", result.user.uid)

    facebook.start_facebook_sign_in(on_signed_in)

Both of Facebook's login modes work:

- classic login gives an access token (also usable with the Graph API);
- Limited Login (``limited=True``, and what iOS falls back to when the user
  has not allowed tracking) gives an OpenID Connect token, checked with a
  nonce.

Needs the ``FacebookLogin`` framework (Swift package
``https://github.com/facebook/facebook-ios-sdk``, product ``FacebookLogin``),
the Facebook provider enabled in the Firebase console, and in ``Info.plist``:
``FacebookAppID``, ``FacebookClientToken``, ``FacebookDisplayName``, the URL
scheme ``fb<APP_ID>``, and ``LSApplicationQueriesSchemes`` with ``fbapi`` and
``fb-messenger-share-api``.
"""

from __future__ import annotations

__all__ = (
    "FACEBOOK_LOGIN_TRACKING_ENABLED",
    "FACEBOOK_LOGIN_TRACKING_LIMITED",
    "get_facebook_credential",
    "initialize_facebook",
    "on_facebook_handle_url",
    "on_facebook_handle_url_kivy",
    "sign_out_of_facebook",
    "start_facebook_sign_in",
)

import hashlib
import secrets
from collections.abc import Callable, Sequence
from typing import Any, Final

from rubicon.objc import ns_from_py, objc_id

from ..types import ObjCObject
from ..util import objc_class, objc_instance, one_shot_block
from ._common import flag
from ._ui import root_view_controller
from .auth import Auth
from .credentials import AuthCredential, FacebookAuthProvider, OAuthProvider
from .errors import AuthError, auth_error_from_nserror, simple_auth_error
from .results import AuthDataResult

FACEBOOK_LOGIN_TRACKING_ENABLED: Final = 0
"""``FBSDKLoginTrackingEnabled``: classic login (an access token)."""
FACEBOOK_LOGIN_TRACKING_LIMITED: Final = 1
"""``FBSDKLoginTrackingLimited``: Limited Login (an OpenID Connect token)."""

DEFAULT_PERMISSIONS: Final = ("public_profile", "email")

CredentialCallback = Callable[[AuthCredential | None, AuthError | None], None]
DataResultCallback = Callable[[AuthDataResult | None, AuthError | None], None]

# each login keeps its LoginManager alive until Facebook answers
_pending: set[ObjCObject] = set()


def _application() -> ObjCObject:
    return objc_class("UIApplication").sharedApplication


def initialize_facebook() -> bool:
    """Start the Facebook SDK. Call it once, at app start (Facebook's
    ``application(_:didFinishLaunchingWithOptions:)`` step).

    Returns:
        What the Facebook SDK returns (True when it started).
    """
    delegate = objc_class("FBSDKApplicationDelegate").sharedInstance
    return bool(
        delegate.application_didFinishLaunchingWithOptions_(_application(), None)
    )


def on_facebook_handle_url(url_string: str) -> bool:
    """Give a URL the app was opened with to the Facebook SDK (the login
    redirect back from the Facebook app or Safari).

    Args:
        url_string: the URL.

    Returns:
        True if the Facebook SDK handled it.
    """
    url = objc_class("NSURL").URLWithString_(url_string)
    delegate = objc_class("FBSDKApplicationDelegate").sharedInstance
    return bool(
        delegate.application_openURL_options_(_application(), url, ns_from_py({}))
    )


def on_facebook_handle_url_kivy(
    _window: Any, filename: str | bytes, *_args: Any
) -> None:
    """Kivy handler: ``Window.bind(on_drop_file=on_facebook_handle_url_kivy)``.

    Kivy (SDL) passes URLs the app was opened with as "dropped files"; this
    forwards them to ``on_facebook_handle_url``.

    Args:
        filename: the URL, as Kivy passes it (``bytes`` or ``str``). The
            other arguments Kivy passes (the window, the position) are ignored.
    """
    url_string = filename.decode("utf-8") if isinstance(filename, bytes) else filename
    on_facebook_handle_url(url_string)


def _credential_from_result(
    result: ObjCObject, raw_nonce: str
) -> AuthCredential | AuthError:
    if flag(result, "isCancelled"):
        return simple_auth_error("Facebook login was cancelled", cancelled=True)
    if result.token is not None:
        return FacebookAuthProvider.credential(str(result.token.tokenString))
    if result.authenticationToken is not None:
        return OAuthProvider.credential(
            FacebookAuthProvider.PROVIDER_ID,
            id_token=str(result.authenticationToken.tokenString),
            raw_nonce=raw_nonce,
        )
    return simple_auth_error("Facebook login gave no token")


def get_facebook_credential(
    callback: CredentialCallback,
    permissions: Sequence[str] = DEFAULT_PERMISSIONS,
    limited: bool = False,
) -> None:
    """Show Facebook Login and give back a Firebase credential, without signing
    in to Firebase (for example to link Facebook to the current user).

    Args:
        callback: gets ``(credential, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user cancelled.
        permissions: the Facebook permissions to ask for.
        limited: True for Limited Login (no tracking). Facebook may also use
            Limited Login on its own when the user has not allowed tracking;
            both give a working credential.
    """
    raw_nonce = secrets.token_urlsafe(32)
    try:
        # Firebase checks the token against SHA-256(raw nonce), as for Apple
        configuration = (
            objc_class("FBSDKLoginConfiguration")
            .alloc()
            .initWithPermissions_tracking_nonce_(
                ns_from_py(list(permissions)),
                FACEBOOK_LOGIN_TRACKING_LIMITED
                if limited
                else FACEBOOK_LOGIN_TRACKING_ENABLED,
                hashlib.sha256(raw_nonce.encode()).hexdigest(),
            )
        )
        if configuration is None:
            raise ValueError(
                f"Facebook rejected the login configuration (permissions {list(permissions)})"
            )
        manager = objc_class("FBSDKLoginManager").alloc().init()
        presenter = root_view_controller()
    except Exception as e:  # noqa: BLE001 - must always answer the caller
        callback(None, simple_auth_error(str(e)))
        return

    def done(result_ptr: Any, error_ptr: Any) -> None:
        _pending.discard(manager)
        if error_ptr:
            callback(None, auth_error_from_nserror(objc_instance(error_ptr)))
            return
        if not result_ptr:
            callback(None, simple_auth_error("Facebook login gave no result"))
            return
        try:
            outcome = _credential_from_result(objc_instance(result_ptr), raw_nonce)
        except Exception as e:  # noqa: BLE001
            callback(
                None, simple_auth_error(f"could not read the Facebook result: {e!r}")
            )
            return
        if isinstance(outcome, AuthCredential):
            callback(outcome, None)
        else:
            callback(None, outcome)

    _pending.add(manager)
    manager.logInFromViewController_configuration_completion_(
        presenter, configuration, one_shot_block(done, objc_id, objc_id)
    )


def start_facebook_sign_in(
    callback: DataResultCallback,
    permissions: Sequence[str] = DEFAULT_PERMISSIONS,
    limited: bool = False,
    auth: Auth | None = None,
) -> None:
    """Show Facebook Login, then sign in to Firebase.

    Args:
        callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user cancelled: not a failure
            to report. ``ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`` means the
            email already has an account with another provider.
        permissions: the Facebook permissions to ask for.
        limited: True for Limited Login (see ``get_facebook_credential``).
        auth: the ``Auth`` to sign in to (default: ``Auth.auth()``).
    """

    def got_credential(
        credential: AuthCredential | None, error: AuthError | None
    ) -> None:
        if credential is None:
            callback(None, error)
            return
        (auth or Auth.auth()).sign_in_with_credential(credential, callback)

    get_facebook_credential(got_credential, permissions, limited)


def sign_out_of_facebook() -> None:
    """Log out of Facebook Login (the next login asks again).

    Call it with ``Auth.sign_out()``, which signs out of Firebase only.
    """
    objc_class("FBSDKLoginManager").alloc().init().logOut()

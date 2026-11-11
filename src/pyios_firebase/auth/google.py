"""Google Sign-In, then Firebase Auth.

    from pyios_firebase.auth.google import start_google_sign_in

    def on_signed_in(result, error):
        if error is not None:
            if not error.cancelled:  # cancelled: the user closed the sheet
                print("Sign-in failed:", error.description)
            return
        print("Signed in:", result.user.uid)

    start_google_sign_in(on_signed_in)

Needs the ``GoogleSignIn`` framework, and the reversed client ID URL scheme
(``com.googleusercontent.apps.YOUR-CLIENT-ID``) in ``CFBundleURLTypes``.
"""

from __future__ import annotations

__all__ = (
    "GOOGLE_SIGN_IN_CANCELED",
    "GOOGLE_SIGN_IN_DOMAIN",
    "get_google_credential",
    "on_gid_signin_handle_url",
    "on_gid_signin_handle_url_kivy",
    "sign_out_of_google",
    "start_google_sign_in",
)

from collections.abc import Callable
from typing import Any, Final

from rubicon.objc import objc_id

from ..util import objc_class, objc_instance, one_shot_block
from ._ui import root_view_controller
from .auth import Auth
from .credentials import AuthCredential, GoogleAuthProvider
from .errors import AuthError, auth_error_from_nserror, simple_auth_error
from .results import AuthDataResult

GOOGLE_SIGN_IN_CANCELED: Final = -5
"""``GIDSignInErrorCode.canceled``: the user closed the Google sheet."""
GOOGLE_SIGN_IN_DOMAIN: Final = "com.google.GIDSignIn"
"""The error domain of Google Sign-In errors."""

CredentialCallback = Callable[[AuthCredential | None, AuthError | None], None]
DataResultCallback = Callable[[AuthDataResult | None, AuthError | None], None]


def _google_error(error: Any) -> AuthError:
    result = auth_error_from_nserror(error)
    if (
        result.domain == GOOGLE_SIGN_IN_DOMAIN
        and result.code == GOOGLE_SIGN_IN_CANCELED
    ):
        result.cancelled = True
    return result


def get_google_credential(callback: CredentialCallback) -> None:
    """Show the Google sign-in sheet and give back a Firebase credential,
    without signing in to Firebase (for example to link Google to the
    current user, or to re-authenticate).

    Args:
        callback: gets ``(credential, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user closed the sheet.
    """

    def done(result_ptr: Any, error_ptr: Any) -> None:
        if error_ptr:
            callback(None, _google_error(objc_instance(error_ptr)))
            return
        try:
            google_user = objc_instance(result_ptr).user
            credential = GoogleAuthProvider.credential(
                str(google_user.idToken.tokenString),
                str(google_user.accessToken.tokenString),
            )
        except Exception as e:  # noqa: BLE001 - must always answer the caller
            callback(
                None, simple_auth_error(f"Google sign-in gave no usable tokens: {e}")
            )
            return
        callback(credential, None)

    try:
        client_id = objc_class("FIRApp").defaultApp().options.clientID
        if client_id is None:
            raise ValueError(
                "GoogleService-Info.plist has no CLIENT_ID (enable Google sign-in first)"
            )
        sign_in = objc_class("GIDSignIn").sharedInstance
        sign_in.configuration = (
            objc_class("GIDConfiguration").alloc().initWithClientID_(client_id)
        )
        presenter = root_view_controller()
    except Exception as e:  # noqa: BLE001
        callback(None, simple_auth_error(str(e)))
        return
    sign_in.signInWithPresentingViewController_completion_(
        presenter, one_shot_block(done, objc_id, objc_id)
    )


def start_google_sign_in(
    callback: DataResultCallback, auth: Auth | None = None
) -> None:
    """Show the Google sign-in sheet, then sign in to Firebase.

    Args:
        callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
            ``error.cancelled`` is True when the user closed the sheet: not a
            failure to report.
        auth: the ``Auth`` to sign in to (default: ``Auth.auth()``).
    """

    def got_credential(
        credential: AuthCredential | None, error: AuthError | None
    ) -> None:
        if credential is None:
            callback(None, error)
            return
        (auth or Auth.auth()).sign_in_with_credential(credential, callback)

    get_google_credential(got_credential)


def sign_out_of_google() -> None:
    """Sign out of Google Sign-In, so the next sign-in shows the account picker.

    Call it with ``Auth.sign_out()``, which signs out of Firebase only.
    """
    objc_class("GIDSignIn").sharedInstance.signOut()


def on_gid_signin_handle_url(url_string: str) -> bool:
    """Give a URL the app was opened with to Google Sign-In.

    Call it from your app's "open URL" handler. Newer Google Sign-In versions
    finish without it, so it is a safe backup.

    Args:
        url_string: the URL.

    Returns:
        True if Google Sign-In handled the URL; False if it is not a sign-in URL.
    """
    url = objc_class("NSURL").URLWithString_(url_string)
    return bool(objc_class("GIDSignIn").sharedInstance.handleURL_(url))


def on_gid_signin_handle_url_kivy(
    _window: Any, filename: str | bytes, *_args: Any
) -> None:
    """Kivy handler: ``Window.bind(on_drop_file=on_gid_signin_handle_url_kivy)``.

    Kivy (SDL) passes URLs the app was opened with as "dropped files"; this
    forwards them to ``on_gid_signin_handle_url``.

    Args:
        filename: the URL, as Kivy passes it (``bytes`` or ``str``). The
            other arguments Kivy passes (the window, the position) are ignored.
    """
    url_string = filename.decode("utf-8") if isinstance(filename, bytes) else filename
    on_gid_signin_handle_url(url_string)

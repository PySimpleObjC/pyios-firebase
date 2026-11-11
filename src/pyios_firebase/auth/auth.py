"""``Auth``: Firebase Authentication for the app. Sign-in, sign-out, listeners,
password reset and email links."""

from __future__ import annotations

__all__ = ("Auth", "AuthStateListener")

from collections.abc import Callable
from ctypes import byref
from typing import Any, ClassVar, Final

from rubicon.objc import ns_from_py, objc_id

from ..types import ObjCObject
from ..util import listener_block, objc_class, objc_instance
from ._common import (
    error_block,
    flag,
    missing_callback_scheme,
    result_block,
    string_block,
    text,
)
from .credentials import AuthCredential, OAuthProvider
from .errors import AuthError, auth_error_from_nserror, simple_auth_error
from .results import ActionCodeInfo, ActionCodeSettings, AuthDataResult
from .user import User

ErrorCallback = Callable[[AuthError | None], None]
DataResultCallback = Callable[[AuthDataResult | None, AuthError | None], None]
UserListener = Callable[[User | None], None]

APNS_TOKEN_TYPE_UNKNOWN: Final = 0
"""``set_apns_token`` type: let Firebase find out (sandbox or production)."""
APNS_TOKEN_TYPE_SANDBOX: Final = 1
"""``set_apns_token`` type: a development (sandbox) APNs token."""
APNS_TOKEN_TYPE_PRODUCTION: Final = 2
"""``set_apns_token`` type: a production APNs token."""


class AuthStateListener:
    """Given back by ``add_state_did_change_listener`` and
    ``add_id_token_did_change_listener``. Call ``remove()`` to stop.

    Args:
        handle: the native listener handle.
        remove: removes the handle from Firebase.
        release: releases the listener's callback block.
    """

    def __init__(
        self,
        handle: ObjCObject,
        remove: Callable[[ObjCObject], None],
        release: Callable[[], None],
    ) -> None:
        self._handle: ObjCObject | None = handle
        self._remove = remove
        self._release = release

    def remove(self) -> None:
        """Stop the updates. Safe to call more than once."""
        if self._handle is None:
            return
        self._remove(self._handle)
        self._handle = None
        self._release()


def _throwing(call: Callable[[Any], Any]) -> AuthError | None:
    """Run a Swift ``throws`` method (an ``NSError **`` argument): its error, or ``None``."""
    error = objc_id()
    ok = call(byref(error))
    if ok or not error.value:
        return None
    return auth_error_from_nserror(objc_instance(error))


class Auth:
    """Firebase Authentication. Get it with ``Auth.auth()``.

    ::

        auth = Auth.auth()
        auth.sign_in_with_email_password("ada@example.com", "s3cret!", on_signed_in)

    Every callback gets ``(result, error)`` (or just ``(error)``), where
    ``error`` is an ``AuthError`` or ``None``.

    Args:
        native: the native ``FIRAuth``. Leave it out for the default app's.
    """

    _instance: ClassVar[Auth | None] = None
    # native FIRAuth addresses that use the emulator (the SDK does not expose it)
    _emulated: ClassVar[set[int]] = set()

    def __init__(self, native: ObjCObject | None = None) -> None:
        self._native: ObjCObject = (
            native if native is not None else objc_class("FIRAuth").auth()
        )

    @classmethod
    def auth(cls) -> Auth:
        """The shared ``Auth`` for the default Firebase app."""
        if cls._instance is None:
            cls._instance = cls(objc_class("FIRAuth").auth())
        return cls._instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRAuth``, for SDK calls this wrapper does not cover."""
        return self._native

    # ---- the current user ---------------------------------------------------------

    @property
    def current_user(self) -> User | None:
        """The signed-in user, or ``None``.

        Right after app start this can be ``None`` for a moment while Firebase
        restores the saved user; use ``add_state_did_change_listener`` to know
        for sure.
        """
        user = self._native.currentUser
        return None if user is None else User(user)

    def update_current_user(
        self, user: User, callback: ErrorCallback | None = None
    ) -> None:
        """Make ``user`` the signed-in user (for example one from another
        ``Auth`` instance or a shared keychain).

        Args:
            user: the user to sign in as.
            callback: gets ``None`` or the error.
        """
        self._native.updateCurrentUser_completion_(user.user, error_block(callback))

    def sign_out(self) -> AuthError | None:
        """Sign the current user out of Firebase (Google, Apple and other
        providers keep their own sessions).

        Returns:
            ``None``, or the error (for example a keychain error).
        """
        return _throwing(self._native.signOut_)

    # ---- sign-in ----------------------------------------------------------------

    def sign_in_with_email_password(
        self, email: str, password: str, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in with an email address and password.

        Args:
            email: the email address.
            password: the password.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
                With email enumeration protection (the default), a wrong email
                or password both give ``INVALID_CREDENTIAL``.
        """
        self._native.signInWithEmail_password_completion_(
            email, password, result_block(callback, AuthDataResult)
        )

    def create_user_with_email_password(
        self, email: str, password: str, callback: DataResultCallback | None = None
    ) -> None:
        """Create an account with an email address and password, and sign in.

        Args:
            email: the email address.
            password: the password (at least 6 characters, or your project's
                password policy).
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``
                (``EMAIL_ALREADY_IN_USE``, ``WEAK_PASSWORD``, ``INVALID_EMAIL``...).
        """
        self._native.createUserWithEmail_password_completion_(
            email, password, result_block(callback, AuthDataResult)
        )

    def sign_in_anonymously(self, callback: DataResultCallback | None = None) -> None:
        """Sign in as a new anonymous user (or the current anonymous one).

        Link a credential later (``User.link_with_credential``) to keep the
        account when the user signs up.

        Args:
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
        """
        self._native.signInAnonymouslyWithCompletion_(
            result_block(callback, AuthDataResult)
        )

    def sign_in_with_custom_token(
        self, token: str, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in with a custom token made by your backend (Admin SDK
        ``create_custom_token``).

        Args:
            token: the custom token.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``
                (``INVALID_CUSTOM_TOKEN``, ``CUSTOM_TOKEN_MISMATCH``).
        """
        self._native.signInWithCustomToken_completion_(
            token, result_block(callback, AuthDataResult)
        )

    def sign_in_with_credential(
        self, credential: AuthCredential, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in with a credential from any provider.

        Args:
            credential: the credential, from one of the provider classes.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
                ``ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`` means the email is
                already used with another provider: sign in with that one, then
                link this credential.
        """
        self._native.signInWithCredential_completion_(
            credential.native, result_block(callback, AuthDataResult)
        )

    def sign_in_with_provider(
        self, provider: OAuthProvider, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in through an OAuth provider's web flow (Microsoft, Yahoo,
        GitHub, OIDC, SAML), in an in-app browser.

        Args:
            provider: the provider, for example ``OAuthProvider("yahoo.com")``.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
                ``error.cancelled`` is True when the user closed the browser.
                If the callback URL scheme is missing from ``Info.plist``, the
                error says which one to add (the SDK itself would stop the app).
        """
        problem = missing_callback_scheme(self._native)
        if problem is not None:
            if callback is not None:
                callback(None, simple_auth_error(problem))
            return
        self._native.signInWithProvider_UIDelegate_completion_(
            provider.native, None, result_block(callback, AuthDataResult)
        )

    # ---- email links ------------------------------------------------------------------

    def send_sign_in_link(
        self,
        email: str,
        action_code_settings: ActionCodeSettings,
        callback: ErrorCallback | None = None,
    ) -> None:
        """Email a passwordless sign-in link.

        Save ``email`` on the device: you need it again in
        ``sign_in_with_email_link``.

        Args:
            email: where to send the link.
            action_code_settings: where the link leads; ``handle_code_in_app``
                must be True.
            callback: gets ``None`` once the email is sent, or the error.
        """
        self._native.sendSignInLinkToEmail_actionCodeSettings_completion_(
            email, action_code_settings.to_native(), error_block(callback)
        )

    def is_sign_in_with_email_link(self, link: str) -> bool:
        """Whether ``link`` (a URL the app was opened with) is a sign-in link.

        Args:
            link: the full URL.

        Returns:
            True if it can be passed to ``sign_in_with_email_link``.
        """
        return bool(self._native.isSignInWithEmailLink_(link))

    def sign_in_with_email_link(
        self, email: str, link: str, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in with an email link from ``send_sign_in_link``.

        Args:
            email: the address the link was sent to.
            link: the full link the user opened.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``
                (``INVALID_ACTION_CODE`` / ``EXPIRED_ACTION_CODE``).
        """
        self._native.signInWithEmail_link_completion_(
            email, link, result_block(callback, AuthDataResult)
        )

    # ---- password reset and action codes --------------------------------------

    def send_password_reset(
        self,
        email: str,
        callback: ErrorCallback | None = None,
        action_code_settings: ActionCodeSettings | None = None,
    ) -> None:
        """Email a password reset link.

        Args:
            email: the account's email address.
            callback: gets ``None`` once the email is sent, or the error. With
                email enumeration protection on, an unknown address is not an
                error.
            action_code_settings: where the link leads, or ``None`` for the
                Firebase default page.
        """
        settings = (
            None if action_code_settings is None else action_code_settings.to_native()
        )
        self._native.sendPasswordResetWithEmail_actionCodeSettings_completion_(
            email, settings, error_block(callback)
        )

    def verify_password_reset_code(
        self, code: str, callback: Callable[[str | None, AuthError | None], None]
    ) -> None:
        """Check a password reset code (the ``oobCode`` of the link).

        Args:
            code: the code.
            callback: gets ``(email, None)`` with the account's address, or
                ``(None, error)``.
        """
        self._native.verifyPasswordResetCode_completion_(code, string_block(callback))

    def confirm_password_reset(
        self, code: str, new_password: str, callback: ErrorCallback | None = None
    ) -> None:
        """Set a new password with a password reset code.

        Args:
            code: the ``oobCode`` of the reset link.
            new_password: the new password.
            callback: gets ``None`` or the error.
        """
        self._native.confirmPasswordResetWithCode_newPassword_completion_(
            code, new_password, error_block(callback)
        )

    def check_action_code(
        self,
        code: str,
        callback: Callable[[ActionCodeInfo | None, AuthError | None], None],
    ) -> None:
        """Find out what an email action code is for, without using it.

        Args:
            code: the ``oobCode`` of the link.
            callback: gets ``(ActionCodeInfo, None)``, or ``(None, error)``.
        """
        self._native.checkActionCode_completion_(
            code, result_block(callback, ActionCodeInfo.from_native)
        )

    def apply_action_code(
        self, code: str, callback: ErrorCallback | None = None
    ) -> None:
        """Use an email action code: verify an email address, or recover / change one.

        Args:
            code: the ``oobCode`` of the link.
            callback: gets ``None`` or the error.
        """
        self._native.applyActionCode_completion_(code, error_block(callback))

    def fetch_sign_in_methods(
        self, email: str, callback: Callable[[list[str] | None, AuthError | None], None]
    ) -> None:
        """The sign-in methods used with ``email``.

        Deprecated by Firebase: with email enumeration protection on (the
        default), the list is always empty.

        Args:
            email: the email address.
            callback: gets ``(methods, None)``, for example ``["password"]``, or
                ``(None, error)``.
        """
        self._native.fetchSignInMethodsForEmail_completion_(
            email, result_block(callback, lambda methods: [str(m) for m in methods])
        )

    def revoke_token(
        self, authorization_code: str, callback: ErrorCallback | None = None
    ) -> None:
        """Revoke a Sign in with Apple token, before deleting an Apple user
        (App Store rule).

        Args:
            authorization_code: the ``authorizationCode`` Apple gave on a recent
                sign-in.
            callback: gets ``None`` or the error.
        """
        self._native.revokeTokenWithAuthorizationCode_completion_(
            authorization_code, error_block(callback)
        )

    # ---- listeners ----------------------------------------------------------------

    def _listen(
        self, add: str, remove: str, listener: UserListener
    ) -> AuthStateListener:
        def on_change(_auth_ptr: Any, user_ptr: Any) -> None:
            listener(User(objc_instance(user_ptr)) if user_ptr else None)

        block, release = listener_block(on_change, objc_id, objc_id)
        handle = getattr(self._native, add)(block)
        return AuthStateListener(handle, getattr(self._native, remove), release)

    def add_state_did_change_listener(
        self, listener: UserListener
    ) -> AuthStateListener:
        """Listen to sign-in and sign-out.

        ``listener`` runs now with the current user (or ``None``), then each
        time a user signs in or out.

        Args:
            listener: gets the ``User``, or ``None`` when signed out.

        Returns:
            An ``AuthStateListener``. Call ``.remove()`` to stop.
        """
        return self._listen(
            "addAuthStateDidChangeListener_",
            "removeAuthStateDidChangeListener_",
            listener,
        )

    def add_id_token_did_change_listener(
        self, listener: UserListener
    ) -> AuthStateListener:
        """Listen to sign-in, sign-out and ID token refreshes (about once an
        hour), for example to keep your backend's copy of the token fresh.

        Args:
            listener: gets the ``User``, or ``None`` when signed out.

        Returns:
            An ``AuthStateListener``. Call ``.remove()`` to stop.
        """
        return self._listen(
            "addIDTokenDidChangeListener_", "removeIDTokenDidChangeListener_", listener
        )

    # ---- settings -----------------------------------------------------------------

    def use_emulator(self, host: str = "127.0.0.1", port: int = 9099) -> None:
        """Send this app's Auth calls to the local Auth emulator.

        Call it right after ``core.configure()``, before any other Auth call.
        Use it only in development and test builds. It also turns app
        verification off, so phone sign-in works without APNs or reCAPTCHA.

        Args:
            host: the emulator's host. ``"127.0.0.1"`` works in the iOS
                Simulator; on a device, use the Mac's LAN address.
            port: the emulator's port (``firebase emulators:start`` uses 9099).
        """
        self._native.useEmulatorWithHost_port_(host, int(port))
        Auth._emulated.add(int(self._native.ptr.value or 0))

    @property
    def is_using_emulator(self) -> bool:
        """True after ``use_emulator``."""
        return int(self._native.ptr.value or 0) in Auth._emulated

    @property
    def language_code(self) -> str | None:
        """The language of emails, SMS and web flows Firebase sends, for
        example ``"fr"``; ``None`` for the project default."""
        return text(self._native.languageCode)

    @language_code.setter
    def language_code(self, code: str | None) -> None:
        self._native.languageCode = code

    def use_app_language(self) -> None:
        """Set ``language_code`` to the app's current language."""
        self._native.useAppLanguage()

    @property
    def tenant_id(self) -> str | None:
        """The tenant users sign in to (multi-tenancy with Identity Platform),
        or ``None``."""
        return text(self._native.tenantID)

    @tenant_id.setter
    def tenant_id(self, tenant_id: str | None) -> None:
        self._native.tenantID = tenant_id

    @property
    def app_verification_disabled_for_testing(self) -> bool:
        """Skip app verification for phone sign-in with test numbers (set in
        the Firebase console). For tests only."""
        settings = self._native.settings
        return settings is not None and flag(
            settings, "isAppVerificationDisabledForTesting"
        )

    @app_verification_disabled_for_testing.setter
    def app_verification_disabled_for_testing(self, disabled: bool) -> None:
        settings = self._native.settings.copy()
        settings.appVerificationDisabledForTesting = bool(disabled)
        self._native.settings = settings

    def use_user_access_group(self, access_group: str | None) -> AuthError | None:
        """Share the signed-in user with other apps (and extensions) through a
        keychain access group.

        Args:
            access_group: the keychain group (with your team ID prefix), or
                ``None`` to stop sharing.

        Returns:
            ``None``, or the error (for example a keychain error).
        """
        return _throwing(
            lambda error: self._native.useUserAccessGroup_error_(access_group, error)
        )

    def get_stored_user(
        self, access_group: str | None
    ) -> tuple[User | None, AuthError | None]:
        """The user saved in a keychain access group, without switching to it
        (for example the user signed in to your other app).

        Sign in as them with ``update_current_user``.

        Args:
            access_group: the keychain access group (with your team ID
                prefix), or ``None`` for the app's own keychain.

        Returns:
            ``(user, None)``, ``(None, None)`` if no user is saved there, or
            ``(None, error)`` (for example without the Keychain Sharing
            capability).
        """
        error = objc_id()
        user = self._native.getStoredUserForAccessGroup_error_(
            access_group, byref(error)
        )
        if error.value:
            return None, auth_error_from_nserror(objc_instance(error))
        return (None if user is None else User(user)), None

    # ---- app delegate hooks (phone and OAuth sign-in) ---------------------------

    def can_handle_url(self, url: str) -> bool:
        """Give a URL the app was opened with to Firebase Auth (reCAPTCHA and
        OAuth redirects).

        Args:
            url: the URL.

        Returns:
            True if Firebase Auth handled it.
        """
        return bool(self._native.canHandleURL_(objc_class("NSURL").URLWithString_(url)))

    def can_handle_notification(self, user_info: dict[str, Any]) -> bool:
        """Give a remote notification to Firebase Auth (silent push for phone
        sign-in).

        Args:
            user_info: the notification's ``userInfo``.

        Returns:
            True if it was for Firebase Auth.
        """
        return bool(self._native.canHandleNotification_(ns_from_py(user_info)))

    def set_apns_token(
        self, token: bytes, token_type: int = APNS_TOKEN_TYPE_UNKNOWN
    ) -> None:
        """Give Firebase Auth the app's APNs device token (phone sign-in).

        Args:
            token: the device token from
                ``didRegisterForRemoteNotificationsWithDeviceToken``.
            token_type: ``APNS_TOKEN_TYPE_UNKNOWN`` / ``SANDBOX`` / ``PRODUCTION``.
        """
        self._native.setAPNSToken_type_(ns_from_py(bytes(token)), int(token_type))

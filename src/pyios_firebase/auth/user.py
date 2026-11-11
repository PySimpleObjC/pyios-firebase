"""``User``: a Firebase user, with their profile, tokens and account actions."""

from __future__ import annotations

__all__ = ("User",)

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from ..types import ObjCObject
from ..util import objc_class
from . import results  # module import: results imports us back
from ._common import (
    error_block,
    flag,
    missing_callback_scheme,
    result_block,
    string_block,
    text,
    url_text,
)
from .errors import AuthError, simple_auth_error

if TYPE_CHECKING:
    from .credentials import AuthCredential, OAuthProvider
    from .multi_factor import MultiFactor

ErrorCallback = Callable[[AuthError | None], None]
DataResultCallback = Callable[["results.AuthDataResult | None", AuthError | None], None]


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _Unset()
"""Leave this profile field as it is (``update_profile``)."""


class User:
    """A Firebase user: the signed-in one by default.

    ``User()`` reads the user who is signed in now. When nobody is,
    ``is_signed_in`` is False and the profile properties are ``None``; the
    account methods need a signed-in user.

    Get users from ``Auth.current_user``, sign-in results and auth state
    listeners.

    Args:
        user: a native ``FIRUser`` to wrap. Leave it out for the user who is
            signed in now.
    """

    def __init__(self, user: ObjCObject | None = None) -> None:
        self.auth: ObjCObject = objc_class("FIRAuth").auth()
        """The native ``FIRAuth``."""
        self.user: ObjCObject | None = (
            user if user is not None else self.auth.currentUser
        )
        """The native ``FIRUser``, or ``None``."""

    def _signed_in(self) -> ObjCObject:
        if self.user is None:
            raise RuntimeError("no user is signed in")
        return self.user

    # ---- profile ----------------------------------------------------------------

    @property
    def is_signed_in(self) -> bool:
        """True if this ``User`` holds a user."""
        return self.user is not None

    @property
    def uid(self) -> str | None:
        """The user's Firebase ID: unique and stable. Use it as your database key."""
        return text(self.user.uid) if self.user is not None else None

    @property
    def email(self) -> str | None:
        """The email address, or ``None``."""
        return text(self.user.email) if self.user is not None else None

    @property
    def display_name(self) -> str | None:
        """The display name, or ``None``."""
        return text(self.user.displayName) if self.user is not None else None

    @property
    def phone_number(self) -> str | None:
        """The phone number (E.164), or ``None``."""
        return text(self.user.phoneNumber) if self.user is not None else None

    @property
    def photo_url(self) -> str | None:
        """The profile photo URL, or ``None``."""
        return url_text(self.user.photoURL) if self.user is not None else None

    @property
    def provider_id(self) -> str | None:
        """Always ``"firebase"`` for a Firebase user."""
        return text(self.user.providerID) if self.user is not None else None

    @property
    def is_anonymous(self) -> bool:
        """True for an anonymous user (``Auth.sign_in_anonymously``)."""
        return self.user is not None and flag(self.user, "isAnonymous")

    @property
    def is_email_verified(self) -> bool:
        """True once the user has verified their email address."""
        return self.user is not None and flag(self.user, "isEmailVerified")

    @property
    def provider_data(self) -> list[results.UserInfo]:
        """The user's profile at each linked provider (email, Google, ...)."""
        if self.user is None:
            return []
        return [results.UserInfo(info) for info in self.user.providerData]

    @property
    def metadata(self) -> results.UserMetadata | None:
        """When the account was created and last signed in, or ``None``."""
        return (
            None
            if self.user is None
            else results.UserMetadata.from_native(self.user.metadata)
        )

    @property
    def multi_factor(self) -> MultiFactor:
        """The user's second factors: list, enroll, unenroll.

        Raises:
            RuntimeError: no user is signed in.
        """
        from .multi_factor import MultiFactor

        return MultiFactor(self._signed_in().multiFactor)

    @property
    def tenant_id(self) -> str | None:
        """The tenant the user belongs to (multi-tenancy), or ``None``."""
        return text(self.user.tenantID) if self.user is not None else None

    @property
    def refresh_token(self) -> str | None:
        """The refresh token. Keep it secret; you rarely need it."""
        return text(self.user.refreshToken) if self.user is not None else None

    # ---- tokens -----------------------------------------------------------------

    def get_id_token(
        self,
        callback: Callable[[str | None, AuthError | None], None],
        force_refresh: bool = False,
    ) -> None:
        """Get a Firebase ID token, to prove who the user is to your backend.

        Args:
            callback: gets ``(token, None)``, or ``(None, error)``.
            force_refresh: get a new token from the server even if the cached
                one is still valid (for example after custom claims changed).

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().getIDTokenForcingRefresh_completion_(
            bool(force_refresh), string_block(callback)
        )

    def get_id_token_result(
        self,
        callback: Callable[[results.IDTokenResult | None, AuthError | None], None],
        force_refresh: bool = False,
    ) -> None:
        """Get a Firebase ID token and its claims (including custom claims).

        Args:
            callback: gets ``(IDTokenResult, None)``, or ``(None, error)``.
            force_refresh: get a new token from the server, for example after
                your backend changed the user's custom claims.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().getIDTokenResultForcingRefresh_completion_(
            bool(force_refresh),
            result_block(callback, results.IDTokenResult.from_native),
        )

    # ---- account ------------------------------------------------------------------

    def reload(self, callback: ErrorCallback | None = None) -> None:
        """Fetch the user's latest profile from the server (for example to see
        ``is_email_verified`` change after they clicked the link).

        Args:
            callback: gets ``None`` or the error. Read the properties again
                after it.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().reloadWithCompletion_(error_block(callback))

    def delete(self, callback: ErrorCallback | None = None) -> None:
        """Delete the account and sign the user out.

        Args:
            callback: gets ``None`` or the error. ``REQUIRES_RECENT_LOGIN`` means
                the user must re-authenticate first.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().deleteWithCompletion_(error_block(callback))

    def update_password(
        self, password: str, callback: ErrorCallback | None = None
    ) -> None:
        """Change the password.

        Args:
            password: the new password.
            callback: gets ``None`` or the error (``WEAK_PASSWORD``,
                ``REQUIRES_RECENT_LOGIN``, ...).

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().updatePassword_completion_(password, error_block(callback))

    def update_email(self, email: str, callback: ErrorCallback | None = None) -> None:
        """Change the email address right away, without verifying it.

        Firebase rejects this when email enumeration protection is on (the
        default for new projects); use ``send_email_verification_before_updating_email``.

        Args:
            email: the new email address.
            callback: gets ``None`` or the error.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().updateEmail_completion_(email, error_block(callback))

    def update_profile(
        self,
        callback: ErrorCallback | None = None,
        *,
        display_name: str | None | _Unset = UNSET,
        photo_url: str | None | _Unset = UNSET,
    ) -> None:
        """Change the display name and/or photo URL.

        ::

            user.update_profile(on_done, display_name="Ada Lovelace")

        Args:
            callback: gets ``None`` or the error.
            display_name: the new display name; ``None`` removes it; leave it
                out to keep it.
            photo_url: the new photo URL; ``None`` removes it; leave it out to
                keep it.

        Raises:
            RuntimeError: no user is signed in.
        """
        request = self._signed_in().profileChangeRequest()
        if not isinstance(display_name, _Unset):
            request.displayName = display_name
        if not isinstance(photo_url, _Unset):
            request.photoURL = (
                None
                if photo_url is None
                else objc_class("NSURL").URLWithString_(photo_url)
            )
        request.commitChangesWithCompletion_(error_block(callback))

    def update_phone_number(
        self, credential: AuthCredential, callback: ErrorCallback | None = None
    ) -> None:
        """Change the phone number, with a credential from ``PhoneAuthProvider``.

        Args:
            credential: a phone credential for the new number.
            callback: gets ``None`` or the error.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().updatePhoneNumberCredential_completion_(
            credential.native, error_block(callback)
        )

    def send_email_verification(
        self,
        callback: ErrorCallback | None = None,
        action_code_settings: results.ActionCodeSettings | None = None,
    ) -> None:
        """Email the user a link to verify their address.

        Args:
            callback: gets ``None`` once the email is sent, or the error.
            action_code_settings: where the link leads, or ``None`` for the
                Firebase default page.

        Raises:
            RuntimeError: no user is signed in.
        """
        settings = (
            None if action_code_settings is None else action_code_settings.to_native()
        )
        self._signed_in().sendEmailVerificationWithActionCodeSettings_completion_(
            settings, error_block(callback)
        )

    def send_email_verification_before_updating_email(
        self,
        email: str,
        callback: ErrorCallback | None = None,
        action_code_settings: results.ActionCodeSettings | None = None,
    ) -> None:
        """Email a link to ``email``; the address changes once the user opens it.

        Args:
            email: the new email address.
            callback: gets ``None`` once the email is sent, or the error.
            action_code_settings: where the link leads, or ``None``.

        Raises:
            RuntimeError: no user is signed in.
        """
        settings = (
            None if action_code_settings is None else action_code_settings.to_native()
        )
        self._signed_in().sendEmailVerificationBeforeUpdatingEmail_actionCodeSettings_completion_(
            email, settings, error_block(callback)
        )

    # ---- providers ------------------------------------------------------------------

    def link_with_credential(
        self, credential: AuthCredential, callback: DataResultCallback | None = None
    ) -> None:
        """Add a sign-in method to this account (for example turn an anonymous
        user into an email/password one).

        Args:
            credential: the credential to link.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.
                ``CREDENTIAL_ALREADY_IN_USE`` means another account has it;
                ``error.updated_credential`` can sign in to that account.

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().linkWithCredential_completion_(
            credential.native, result_block(callback, results.AuthDataResult)
        )

    def link_with_provider(
        self, provider: OAuthProvider, callback: DataResultCallback | None = None
    ) -> None:
        """Link an OAuth provider through its web sign-in flow.

        Args:
            provider: the provider, for example ``OAuthProvider("microsoft.com")``.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.

        Raises:
            RuntimeError: no user is signed in.
        """
        problem = missing_callback_scheme(self.auth)
        if problem is not None:
            if callback is not None:
                callback(None, simple_auth_error(problem))
            return
        self._signed_in().linkWithProvider_UIDelegate_completion_(
            provider.native, None, result_block(callback, results.AuthDataResult)
        )

    def unlink(
        self,
        provider_id: str,
        callback: Callable[[User | None, AuthError | None], None] | None = None,
    ) -> None:
        """Remove a sign-in method from this account.

        Args:
            provider_id: the provider to unlink, for example ``"google.com"``.
            callback: gets ``(User, None)`` with the updated user, or
                ``(None, error)`` (``NO_SUCH_PROVIDER`` if it was not linked).

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().unlinkFromProvider_completion_(
            provider_id, result_block(callback, User)
        )

    def reauthenticate_with_credential(
        self, credential: AuthCredential, callback: DataResultCallback | None = None
    ) -> None:
        """Sign in again with a fresh credential, before sensitive actions
        (``delete``, ``update_password``) that need a recent sign-in.

        Args:
            credential: a credential for this same user.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``
                (``USER_MISMATCH`` for another user's credential).

        Raises:
            RuntimeError: no user is signed in.
        """
        self._signed_in().reauthenticateWithCredential_completion_(
            credential.native, result_block(callback, results.AuthDataResult)
        )

    def reauthenticate_with_provider(
        self, provider: OAuthProvider, callback: DataResultCallback | None = None
    ) -> None:
        """Re-authenticate through an OAuth provider's web sign-in flow.

        Args:
            provider: the provider the user signed in with.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``.

        Raises:
            RuntimeError: no user is signed in.
        """
        problem = missing_callback_scheme(self.auth)
        if problem is not None:
            if callback is not None:
                callback(None, simple_auth_error(problem))
            return
        self._signed_in().reauthenticateWithProvider_UIDelegate_completion_(
            provider.native, None, result_block(callback, results.AuthDataResult)
        )

    # ---- comparing ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, User) and self.uid is not None and self.uid == other.uid
        )

    def __hash__(self) -> int:
        return hash(self.uid)

    def __repr__(self) -> str:
        return f"User(uid={self.uid!r}, email={self.email!r})"

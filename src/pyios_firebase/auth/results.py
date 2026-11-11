"""What Firebase Authentication calls give back, as plain Python values."""

from __future__ import annotations

__all__ = (
    "ActionCodeInfo",
    "ActionCodeOperation",
    "ActionCodeSettings",
    "ActionCodeURL",
    "AdditionalUserInfo",
    "AuthDataResult",
    "IDTokenResult",
    "UserInfo",
    "UserMetadata",
)

import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from ..types import ObjCObject
from ..util import nsdate_to_datetime, objc_class, to_python
from . import user as user_module  # module import: user imports us back
from ._common import flag, text, url_text
from .credentials import OAuthCredential


def _required_date(value: ObjCObject) -> datetime:
    """An ``NSDate`` the SDK always provides, as a ``datetime``."""
    result = nsdate_to_datetime(value)
    if result is None:
        raise ValueError("Firebase gave no date where one is required")
    return result


class UserInfo:
    """A user's profile at one provider (an entry of ``User.provider_data``).

    Args:
        native: the native ``FIRUserInfo``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def provider_id(self) -> str:
        """The provider ID, for example ``"password"`` or ``"google.com"``."""
        return str(self._native.providerID)

    @property
    def uid(self) -> str:
        """The user's ID at that provider (not the Firebase uid)."""
        return str(self._native.uid)

    @property
    def display_name(self) -> str | None:
        """The name at that provider, or ``None``."""
        return text(self._native.displayName)

    @property
    def email(self) -> str | None:
        """The email address at that provider, or ``None``."""
        return text(self._native.email)

    @property
    def phone_number(self) -> str | None:
        """The phone number at that provider, or ``None``."""
        return text(self._native.phoneNumber)

    @property
    def photo_url(self) -> str | None:
        """The profile photo URL at that provider, or ``None``."""
        return url_text(self._native.photoURL)

    def __repr__(self) -> str:
        return f"UserInfo(provider_id={self.provider_id!r}, uid={self.uid!r})"


@dataclass(frozen=True)
class UserMetadata:
    """When the user was created and last signed in."""

    creation_date: datetime | None
    """When the account was created (UTC)."""
    last_sign_in_date: datetime | None
    """When the user last signed in (UTC)."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> UserMetadata:
        """Copy a native ``FIRUserMetadata``.

        Args:
            native: the ``FIRUserMetadata``.
        """
        return cls(
            nsdate_to_datetime(native.creationDate),
            nsdate_to_datetime(native.lastSignInDate),
        )


@dataclass(frozen=True)
class AdditionalUserInfo:
    """Provider details from one sign-in."""

    provider_id: str
    """The provider used for this sign-in."""
    is_new_user: bool
    """True if this sign-in created the account."""
    username: str | None
    """The username at the provider (GitHub, Twitter), or ``None``."""
    profile: dict[str, Any]
    """The provider's profile data (for example Google's ``given_name``)."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> AdditionalUserInfo:
        """Copy a native ``FIRAdditionalUserInfo``.

        Args:
            native: the ``FIRAdditionalUserInfo``.
        """
        profile = native.profile
        return cls(
            provider_id=str(native.providerID),
            is_new_user=flag(native, "isNewUser"),
            username=text(native.username),
            profile={} if profile is None else to_python(profile),
        )


class AuthDataResult:
    """The result of a sign-in, link or re-authentication.

    Args:
        native: the native ``FIRAuthDataResult``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def user(self) -> user_module.User:
        """The signed-in (or linked) user."""
        return user_module.User(self._native.user)

    @property
    def additional_user_info(self) -> AdditionalUserInfo | None:
        """Provider details from this sign-in, or ``None``."""
        info = self._native.additionalUserInfo
        return None if info is None else AdditionalUserInfo.from_native(info)

    @property
    def credential(self) -> OAuthCredential | None:
        """The OAuth credential the provider gave (OAuth providers only), or
        ``None``. Holds the provider's own access / ID tokens."""
        credential = self._native.credential
        return None if credential is None else OAuthCredential(credential)

    def __repr__(self) -> str:
        return f"AuthDataResult(user={self.user!r})"


@dataclass(frozen=True)
class IDTokenResult:
    """A Firebase ID token and what it says."""

    token: str
    """The ID token (a JWT). Send it to your backend to prove who the user is."""
    claims: dict[str, Any]
    """All the token's claims, including custom claims set by your backend."""
    expiration_date: datetime
    """When the token expires (UTC)."""
    issued_at_date: datetime
    """When the token was issued (UTC)."""
    auth_date: datetime
    """When the user signed in (UTC)."""
    sign_in_provider: str
    """The provider used to sign in, for example ``"password"`` or ``"anonymous"``."""
    sign_in_second_factor: str | None
    """The second factor used, for multi-factor sign-in, or ``None``."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> IDTokenResult:
        """Copy a native ``FIRAuthTokenResult``.

        Args:
            native: the ``FIRAuthTokenResult``.
        """
        second = text(native.signInSecondFactor)
        return cls(
            token=str(native.token),
            claims=to_python(native.claims),
            expiration_date=_required_date(native.expirationDate),
            issued_at_date=_required_date(native.issuedAtDate),
            auth_date=_required_date(native.authDate),
            sign_in_provider=str(native.signInProvider),
            sign_in_second_factor=second or None,
        )


class ActionCodeOperation:
    """What an email action code (link) is for. The values of
    ``ActionCodeInfo.operation``."""

    UNKNOWN: Final = 0
    PASSWORD_RESET: Final = 1
    VERIFY_EMAIL: Final = 2
    RECOVER_EMAIL: Final = 3
    EMAIL_LINK: Final = 4
    VERIFY_AND_CHANGE_EMAIL: Final = 5
    REVERT_SECOND_FACTOR_ADDITION: Final = 6


@dataclass(frozen=True)
class ActionCodeInfo:
    """What ``Auth.check_action_code`` learned about an email action code."""

    operation: int
    """An ``ActionCodeOperation`` value.

    Firebase iOS SDK 13.1.1 only recognises request types in camel case
    (``"resetPassword"``); a server that sends ``"PASSWORD_RESET"``, as the
    Auth emulator does, gives ``UNKNOWN``. Do not rely on it alone."""
    email: str
    """The email address the code is for."""
    previous_email: str | None
    """For ``RECOVER_EMAIL`` / ``VERIFY_AND_CHANGE_EMAIL``: the old address."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> ActionCodeInfo:
        """Copy a native ``FIRActionCodeInfo``.

        Args:
            native: the ``FIRActionCodeInfo``.
        """
        return cls(int(native.operation), str(native.email), text(native.previousEmail))


@dataclass
class ActionCodeSettings:
    """Where email links (password reset, verification, sign-in) lead.

    ::

        ActionCodeSettings(
            url="https://example.com/finish-sign-in",
            handle_code_in_app=True,
            ios_bundle_id="com.example.app",
        )
    """

    url: str | None = None
    """The continue URL: where the user lands after the action. Its domain must
    be authorized in the Firebase console."""
    handle_code_in_app: bool = False
    """True to open the link in the app (required for email link sign-in)."""
    ios_bundle_id: str | None = None
    """The iOS app to open the link in."""
    android_package_name: str | None = None
    """The Android app to open the link in."""
    android_install_if_not_available: bool = False
    """Offer to install the Android app if it is missing."""
    android_minimum_version: str | None = None
    """The minimum Android app version that can handle the link."""
    link_domain: str | None = None
    """A custom Firebase Hosting domain for the link."""

    def to_native(self) -> ObjCObject:
        """Make the native ``FIRActionCodeSettings``."""
        native = objc_class("FIRActionCodeSettings").alloc().init()
        if self.url is not None:
            native.URL = objc_class("NSURL").URLWithString_(self.url)
        native.handleCodeInApp = bool(self.handle_code_in_app)
        if self.ios_bundle_id is not None:
            native.iOSBundleID = self.ios_bundle_id
        if self.android_package_name is not None:
            native.setAndroidPackageName_installIfNotAvailable_minimumVersion_(
                self.android_package_name,
                bool(self.android_install_if_not_available),
                self.android_minimum_version,
            )
        if self.link_domain is not None:
            native.linkDomain = self.link_domain
        return native


_LINK_MODES: Final = {
    "resetPassword": 1,
    "verifyEmail": 2,
    "recoverEmail": 3,
    "signIn": 4,
    "verifyAndChangeEmail": 5,
    "revertSecondFactorAddition": 6,
}


def _query_params(url: str) -> dict[str, str]:
    """The first value of each query parameter, percent-decoded once."""
    query = urllib.parse.urlsplit(url).query
    return {
        k: v[0] for k, v in urllib.parse.parse_qs(query, keep_blank_values=True).items()
    }


@dataclass(frozen=True)
class ActionCodeURL:
    """The parts of an email action link (password reset, verification,
    sign-in), read without calling the server.

    Use it to get the ``continue_url`` back, with the state you put in it
    ("Passing State in Email Actions")::

        info = ActionCodeURL.from_link(link)
        if info is not None and info.continue_url:
            state = urllib.parse.parse_qs(urllib.parse.urlsplit(info.continue_url).query)

    Parsed in Python: Firebase iOS SDK 13.1.1 decodes the link's query before
    splitting it, which cuts a continue URL at its own ``&`` and loses state.
    """

    operation: int
    """An ``ActionCodeOperation`` value, from the link's ``mode``."""
    code: str | None
    """The action code (``oobCode``): pass it to ``apply_action_code``,
    ``confirm_password_reset``, ..."""
    continue_url: str | None
    """The continue URL given in ``ActionCodeSettings.url``, with its state."""
    api_key: str | None
    """The Firebase API key in the link."""
    language_code: str | None
    """The language of the email, or ``None``."""

    @classmethod
    def from_link(cls, link: str) -> ActionCodeURL | None:
        """Parse an action link.

        Links wrapped in another link's ``link`` parameter (as Firebase Hosting
        and Dynamic Links deliver them) are unwrapped.

        Args:
            link: the full link from the email (or the URL the app was opened with).

        Returns:
            An ``ActionCodeURL``, or ``None`` if ``link`` has no ``mode`` or
            ``oobCode`` (it is not an action link).
        """
        params = _query_params(link)
        if "oobCode" not in params and "mode" not in params and "link" in params:
            params = _query_params(params["link"])
        if "oobCode" not in params and "mode" not in params:
            return None
        return cls(
            operation=_LINK_MODES.get(
                params.get("mode", ""), ActionCodeOperation.UNKNOWN
            ),
            code=params.get("oobCode"),
            continue_url=params.get("continueUrl"),
            api_key=params.get("apiKey"),
            language_code=params.get("lang"),
        )

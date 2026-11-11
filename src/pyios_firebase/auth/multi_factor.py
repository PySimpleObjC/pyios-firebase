"""Multi-factor authentication: SMS and TOTP (authenticator app) second factors.

Enroll a second factor for the signed-in user::

    mfa = auth.current_user.multi_factor
    mfa.get_session(on_session)                       # 1. a session
    PhoneAuthProvider().verify_phone_number(           # 2. SMS for enrollment
        "+15555550100", on_code_sent, multi_factor_session=session)
    assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, code))
    mfa.enroll(assertion, "My phone", on_enrolled)     # 3. enroll

Sign in when a second factor is required::

    def on_signed_in(result, error):
        if error is not None and error.code == AuthErrorCode.SECOND_FACTOR_REQUIRED:
            resolver = error.resolver                  # hints: the user's factors
            ...                                        # verify one, then:
            resolver.resolve_sign_in(assertion, on_signed_in)

Multi-factor needs Identity Platform (Firebase Authentication with Identity
Platform) and the factor enabled in the console. Enrolling needs a verified
email address.
"""

from __future__ import annotations

__all__ = (
    "PHONE_FACTOR_ID",
    "TOTP_FACTOR_ID",
    "MultiFactor",
    "MultiFactorAssertion",
    "MultiFactorInfo",
    "MultiFactorResolver",
    "MultiFactorSession",
    "PhoneMultiFactorGenerator",
    "PhoneMultiFactorInfo",
    "TOTPMultiFactorGenerator",
    "TOTPSecret",
)

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Final

from ..types import ObjCObject
from ..util import nsdate_to_datetime, objc_class
from ._common import error_block, result_block, text
from .errors import AuthError

if TYPE_CHECKING:
    from .credentials import AuthCredential
    from .results import AuthDataResult

PHONE_FACTOR_ID: Final = "phone"
"""The ``factor_id`` of SMS second factors."""
TOTP_FACTOR_ID: Final = "totp"
"""The ``factor_id`` of TOTP (authenticator app) second factors."""

ErrorCallback = Callable[[AuthError | None], None]


class MultiFactorSession:
    """Proves the first factor was just completed (or that the user is signed
    in, for enrollment). Pass it to SMS verification or ``generate_secret``.

    Args:
        native: the native ``FIRMultiFactorSession``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRMultiFactorSession``."""
        return self._native


class MultiFactorInfo:
    """One enrolled second factor.

    Args:
        native: the native ``FIRMultiFactorInfo``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRMultiFactorInfo``."""
        return self._native

    @property
    def uid(self) -> str:
        """The factor's ID (its enrollment ID for TOTP sign-in)."""
        return str(self._native.UID)

    @property
    def factor_id(self) -> str:
        """``PHONE_FACTOR_ID`` or ``TOTP_FACTOR_ID``."""
        return str(self._native.factorID)

    @property
    def display_name(self) -> str | None:
        """The name given at enrollment, or ``None``."""
        return text(self._native.displayName)

    @property
    def enrollment_date(self) -> datetime | None:
        """When the factor was enrolled (UTC)."""
        return nsdate_to_datetime(self._native.enrollmentDate)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(factor_id={self.factor_id!r}, uid={self.uid!r})"


class PhoneMultiFactorInfo(MultiFactorInfo):
    """An enrolled SMS second factor.

    Args:
        native: the native ``FIRPhoneMultiFactorInfo``.
    """

    @property
    def phone_number(self) -> str:
        """The phone number, usually masked in sign-in hints (``+*******0100``)."""
        return str(self._native.phoneNumber)


def _wrap_info(native: ObjCObject) -> MultiFactorInfo:
    if str(native.factorID) == PHONE_FACTOR_ID:
        return PhoneMultiFactorInfo(native)
    return MultiFactorInfo(native)


class MultiFactorAssertion:
    """Proof of a second factor, for ``MultiFactor.enroll`` or
    ``MultiFactorResolver.resolve_sign_in``. Make it with
    ``PhoneMultiFactorGenerator`` or ``TOTPMultiFactorGenerator``.

    Args:
        native: the native ``FIRMultiFactorAssertion``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRMultiFactorAssertion``."""
        return self._native

    @property
    def factor_id(self) -> str:
        """``PHONE_FACTOR_ID`` or ``TOTP_FACTOR_ID``."""
        return str(self._native.factorID)


class PhoneMultiFactorGenerator:
    """Make SMS second-factor assertions."""

    @staticmethod
    def assertion(credential: AuthCredential) -> MultiFactorAssertion:
        """An assertion from a phone credential.

        Args:
            credential: from ``PhoneAuthProvider.credential`` after
                ``verify_phone_number`` (enrollment) or
                ``verify_phone_number_for_sign_in`` (sign-in).

        Returns:
            A ``MultiFactorAssertion`` with ``factor_id`` ``"phone"``.
        """
        return MultiFactorAssertion(
            objc_class("FIRPhoneMultiFactorGenerator").assertionWithCredential_(
                credential.native
            )
        )


class TOTPSecret:
    """A new TOTP secret, to show to the user while they set up their
    authenticator app.

    Args:
        native: the native ``FIRTOTPSecret``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRTOTPSecret``."""
        return self._native

    def shared_secret_key(self) -> str:
        """The secret, to type into an authenticator app by hand."""
        return str(self._native.sharedSecretKey())

    def generate_qr_code_url(self, account_name: str, issuer: str) -> str:
        """An ``otpauth://`` URL, to show as a QR code for an authenticator app.

        Args:
            account_name: shown in the authenticator app, usually the email.
            issuer: your app's name, shown in the authenticator app.

        Returns:
            The URL.
        """
        return str(
            self._native.generateQRCodeURLWithAccountName_issuer_(account_name, issuer)
        )

    def open_in_otp_app(self, qr_code_url: str) -> None:
        """Open the URL in an installed authenticator app (if there is one).

        Args:
            qr_code_url: from ``generate_qr_code_url``.
        """
        self._native.openInOTPAppWithQRCodeURL_(qr_code_url)


class TOTPMultiFactorGenerator:
    """Make TOTP (authenticator app) secrets and assertions."""

    @staticmethod
    def generate_secret(
        session: MultiFactorSession,
        callback: Callable[[TOTPSecret | None, AuthError | None], None],
    ) -> None:
        """Make a new TOTP secret for enrollment.

        Args:
            session: from ``MultiFactor.get_session``.
            callback: gets ``(TOTPSecret, None)``, or ``(None, error)``.
        """
        objc_class(
            "FIRTOTPMultiFactorGenerator"
        ).generateSecretWithMultiFactorSession_completion_(
            session.native, result_block(callback, TOTPSecret)
        )

    @staticmethod
    def assertion_for_enrollment(
        secret: TOTPSecret, one_time_password: str
    ) -> MultiFactorAssertion:
        """An assertion to enroll the authenticator app.

        Args:
            secret: from ``generate_secret``.
            one_time_password: the 6-digit code the app shows now.

        Returns:
            A ``MultiFactorAssertion`` with ``factor_id`` ``"totp"``.
        """
        return MultiFactorAssertion(
            objc_class(
                "FIRTOTPMultiFactorGenerator"
            ).assertionForEnrollmentWithSecret_oneTimePassword_(
                secret.native, one_time_password
            )
        )

    @staticmethod
    def assertion_for_sign_in(
        enrollment_id: str, one_time_password: str
    ) -> MultiFactorAssertion:
        """An assertion to finish a sign-in with the authenticator app.

        Args:
            enrollment_id: the ``uid`` of the TOTP hint in ``MultiFactorResolver.hints``.
            one_time_password: the 6-digit code the app shows now.

        Returns:
            A ``MultiFactorAssertion`` with ``factor_id`` ``"totp"``.
        """
        return MultiFactorAssertion(
            objc_class(
                "FIRTOTPMultiFactorGenerator"
            ).assertionForSignInWithEnrollmentID_oneTimePassword_(
                enrollment_id, one_time_password
            )
        )


class MultiFactor:
    """A user's second factors. Get it with ``User.multi_factor``.

    Args:
        native: the native ``FIRMultiFactor``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def enrolled_factors(self) -> list[MultiFactorInfo]:
        """The enrolled second factors (``PhoneMultiFactorInfo`` for SMS)."""
        return [_wrap_info(info) for info in self._native.enrolledFactors]

    def get_session(
        self, callback: Callable[[MultiFactorSession | None, AuthError | None], None]
    ) -> None:
        """Start an enrollment: get a session for SMS verification or a TOTP secret.

        Args:
            callback: gets ``(MultiFactorSession, None)``, or ``(None, error)``
                (``REQUIRES_RECENT_LOGIN`` if the sign-in is old).
        """
        self._native.getSessionWithCompletion_(
            result_block(callback, MultiFactorSession)
        )

    def enroll(
        self,
        assertion: MultiFactorAssertion,
        display_name: str | None = None,
        callback: ErrorCallback | None = None,
    ) -> None:
        """Enroll a second factor.

        Args:
            assertion: from ``PhoneMultiFactorGenerator`` or
                ``TOTPMultiFactorGenerator.assertion_for_enrollment``.
            display_name: a name to show in sign-in hints, for example "Work phone".
            callback: gets ``None`` or the error (``UNVERIFIED_EMAIL`` if the
                email address is not verified yet).
        """
        self._native.enrollWithAssertion_displayName_completion_(
            assertion.native, display_name, error_block(callback)
        )

    def unenroll(
        self, factor: MultiFactorInfo | str, callback: ErrorCallback | None = None
    ) -> None:
        """Remove a second factor.

        Args:
            factor: the factor, or its ``uid``.
            callback: gets ``None`` or the error. Removing the factor used to
                sign in signs the user out.
        """
        if isinstance(factor, MultiFactorInfo):
            self._native.unenrollWithInfo_completion_(
                factor.native, error_block(callback)
            )
        else:
            self._native.unenrollWithFactorUID_completion_(
                factor, error_block(callback)
            )


class MultiFactorResolver:
    """Finishes a sign-in that needs a second factor. Get it from
    ``AuthError.resolver`` when ``error.code == AuthErrorCode.SECOND_FACTOR_REQUIRED``.

    Args:
        native: the native ``FIRMultiFactorResolver``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def hints(self) -> list[MultiFactorInfo]:
        """The user's enrolled factors: let them choose one."""
        return [_wrap_info(info) for info in self._native.hints]

    @property
    def session(self) -> MultiFactorSession:
        """The session proving the first factor: pass it to SMS verification."""
        return MultiFactorSession(self._native.session)

    def resolve_sign_in(
        self,
        assertion: MultiFactorAssertion,
        callback: Callable[[AuthDataResult | None, AuthError | None], None]
        | None = None,
    ) -> None:
        """Finish the sign-in with a second factor.

        Args:
            assertion: from ``PhoneMultiFactorGenerator.assertion`` or
                ``TOTPMultiFactorGenerator.assertion_for_sign_in``.
            callback: gets ``(AuthDataResult, None)``, or ``(None, error)``
                (``INVALID_VERIFICATION_CODE`` for a wrong code).
        """
        from .results import AuthDataResult

        self._native.resolveSignInWithAssertion_completion_(
            assertion.native, result_block(callback, AuthDataResult)
        )

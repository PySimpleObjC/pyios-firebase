"""Firebase Authentication errors.

Every auth callback's ``error`` is an ``AuthError``: a ``FirebaseError`` with
extra keys. Compare ``error.code`` with ``AuthErrorCode``::

    def on_signed_in(result, error):
        if error is not None:
            if error.code == AuthErrorCode.WRONG_PASSWORD:
                ...
"""

from __future__ import annotations

__all__ = ("AUTH_ERROR_DOMAIN", "AuthError", "AuthErrorCode", "auth_error_from_pointer")

from typing import TYPE_CHECKING, Any, Final

from ..types import FirebaseError, ObjCObject
from ..util import nserror_to_dict, objc_instance

if TYPE_CHECKING:
    from .credentials import AuthCredential
    from .multi_factor import MultiFactorResolver

AUTH_ERROR_DOMAIN: Final = "FIRAuthErrorDomain"
"""The ``error.domain`` of Firebase Authentication errors."""

_NAME_KEY: Final = "FIRAuthErrorUserInfoNameKey"
_EMAIL_KEY: Final = "FIRAuthErrorUserInfoEmailKey"
_UPDATED_CREDENTIAL_KEY: Final = "FIRAuthErrorUserInfoUpdatedCredentialKey"
_RESOLVER_KEY: Final = "FIRAuthErrorUserInfoMultiFactorResolverKey"


class AuthErrorCode:
    """The ``error.code`` values of Firebase Authentication errors.

    Generated from ``FIRAuthErrorCode`` in the Firebase iOS SDK (13.1.1). The
    numbers are fixed in the SDK; check them when you update it.
    """

    INVALID_CUSTOM_TOKEN: Final = 17000
    """Indicates a validation error with the custom token."""
    CUSTOM_TOKEN_MISMATCH: Final = 17002
    """Indicates the service account and the API key belong to different projects."""
    INVALID_CREDENTIAL: Final = 17004
    """Indicates the IDP token or requestUri is invalid."""
    USER_DISABLED: Final = 17005
    """Indicates the user's account is disabled on the server."""
    OPERATION_NOT_ALLOWED: Final = 17006
    """Indicates the administrator disabled sign in with the specified identity provider."""
    EMAIL_ALREADY_IN_USE: Final = 17007
    """Indicates the email used to attempt a sign up is already in use."""
    INVALID_EMAIL: Final = 17008
    """Indicates the email is invalid."""
    WRONG_PASSWORD: Final = 17009
    """Indicates the user attempted sign in with a wrong password."""
    TOO_MANY_REQUESTS: Final = 17010
    """Indicates that too many requests were made to a server method."""
    USER_NOT_FOUND: Final = 17011
    """Indicates the user account was not found."""
    ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL: Final = 17012
    """Indicates account linking is required."""
    REQUIRES_RECENT_LOGIN: Final = 17014
    """Indicates the user has attempted to change email or password more than 5 minutes after signing in."""
    PROVIDER_ALREADY_LINKED: Final = 17015
    """Indicates an attempt to link a provider to which the account is already linked."""
    NO_SUCH_PROVIDER: Final = 17016
    """Indicates an attempt to unlink a provider that is not linked."""
    INVALID_USER_TOKEN: Final = 17017
    """Indicates user's saved auth credential is invalid the user needs to sign in again."""
    NETWORK_ERROR: Final = 17020
    """Indicates a network error occurred (such as a timeout interrupted connection or unreachable host)."""
    USER_TOKEN_EXPIRED: Final = 17021
    """Indicates the saved token has expired for example the user may have changed account password on another device."""
    INVALID_API_KEY: Final = 17023
    """Indicates an invalid API key was supplied in the request."""
    USER_MISMATCH: Final = 17024
    """Indicates that an attempt was made to reauthenticate with a user which is not the current user."""
    CREDENTIAL_ALREADY_IN_USE: Final = 17025
    """Indicates an attempt to link with a credential that has already been linked with a different Firebase account."""
    WEAK_PASSWORD: Final = 17026
    """Indicates an attempt to set a password that is considered too weak."""
    APP_NOT_AUTHORIZED: Final = 17028
    """Indicates the App is not authorized to use Firebase Authentication with the provided API Key."""
    EXPIRED_ACTION_CODE: Final = 17029
    """Indicates the OOB code is expired."""
    INVALID_ACTION_CODE: Final = 17030
    """Indicates the OOB code is invalid."""
    INVALID_MESSAGE_PAYLOAD: Final = 17031
    """Indicates that there are invalid parameters in the payload during a 'send password reset email' attempt."""
    INVALID_SENDER: Final = 17032
    """Indicates that the sender email is invalid during a 'send password reset email' attempt."""
    INVALID_RECIPIENT_EMAIL: Final = 17033
    """Indicates that the recipient email is invalid."""
    MISSING_EMAIL: Final = 17034
    """Indicates that an email address was expected but one was not provided."""
    MISSING_IOS_BUNDLE_ID: Final = 17036
    """Indicates that the iOS bundle ID is missing when a iOS App Store ID is provided."""
    MISSING_ANDROID_PACKAGE_NAME: Final = 17037
    """Indicates that the android package name is missing when the `androidInstallApp` flag is set to `true`."""
    UNAUTHORIZED_DOMAIN: Final = 17038
    """Indicates that the domain specified in the continue URL is not allowlisted in the Firebase console."""
    INVALID_CONTINUE_URI: Final = 17039
    """Indicates that the domain specified in the continue URI is not valid."""
    MISSING_CONTINUE_URI: Final = 17040
    """Indicates that a continue URI was not provided in a request to the backend which requires one."""
    MISSING_PHONE_NUMBER: Final = 17041
    """Indicates that a phone number was not provided in a call to `verifyPhoneNumber:completion:`."""
    INVALID_PHONE_NUMBER: Final = 17042
    """Indicates that an invalid phone number was provided in a call to `verifyPhoneNumber:completion:`."""
    MISSING_VERIFICATION_CODE: Final = 17043
    """Indicates that the phone auth credential was created with an empty verification code."""
    INVALID_VERIFICATION_CODE: Final = 17044
    """Indicates that an invalid verification code was used in the verifyPhoneNumber request."""
    MISSING_VERIFICATION_ID: Final = 17045
    """Indicates that the phone auth credential was created with an empty verification ID."""
    INVALID_VERIFICATION_ID: Final = 17046
    """Indicates that an invalid verification ID was used in the verifyPhoneNumber request."""
    MISSING_APP_CREDENTIAL: Final = 17047
    """Indicates that the APNS device token is missing in the verifyClient request."""
    INVALID_APP_CREDENTIAL: Final = 17048
    """Indicates that an invalid APNS device token was used in the verifyClient request."""
    SESSION_EXPIRED: Final = 17051
    """Indicates that the SMS code has expired."""
    QUOTA_EXCEEDED: Final = 17052
    """Indicates that the quota of SMS messages for a given project has been exceeded."""
    MISSING_APP_TOKEN: Final = 17053
    """Indicates that the APNs device token could not be obtained."""
    NOTIFICATION_NOT_FORWARDED: Final = 17054
    """Indicates that the app fails to forward remote notification to FIRAuth."""
    APP_NOT_VERIFIED: Final = 17055
    """Indicates that the app could not be verified by Firebase during phone number authentication."""
    CAPTCHA_CHECK_FAILED: Final = 17056
    """Indicates that the reCAPTCHA token is not valid."""
    WEB_CONTEXT_ALREADY_PRESENTED: Final = 17057
    """Indicates that an attempt was made to present a new web context while one was already being presented."""
    WEB_CONTEXT_CANCELLED: Final = 17058
    """Indicates that the URL presentation was cancelled prematurely by the user."""
    APP_VERIFICATION_USER_INTERACTION_FAILURE: Final = 17059
    """Indicates a general failure during the app verification flow."""
    INVALID_CLIENT_ID: Final = 17060
    """Indicates that the clientID used to invoke a web flow is invalid."""
    WEB_NETWORK_REQUEST_FAILED: Final = 17061
    """Indicates that a network request within a SFSafariViewController or WKWebView failed."""
    WEB_INTERNAL_ERROR: Final = 17062
    """Indicates that an internal error occurred within a SFSafariViewController or WKWebView."""
    WEB_SIGN_IN_USER_INTERACTION_FAILURE: Final = 17063
    """Indicates a general failure during a web sign-in flow."""
    LOCAL_PLAYER_NOT_AUTHENTICATED: Final = 17066
    """Indicates that the local player was not authenticated prior to attempting Game Center signin."""
    NULL_USER: Final = 17067
    """Indicates that a non-null user was expected as an argument to the operation but a null user was provided."""
    INVALID_PROVIDER_ID: Final = 17071
    """Represents the error code for when the given provider id for a web operation is invalid."""
    TENANT_ID_MISMATCH: Final = 17072
    """Represents the error code for when an attempt is made to update the current user with a tenantId that differs from the current FirebaseAuth instance's tenantId."""
    UNSUPPORTED_TENANT_OPERATION: Final = 17073
    """Represents the error code for when a request is made to the backend with an associated tenant ID for an operation that does not support multi-tenancy."""
    INVALID_HOSTING_LINK_DOMAIN: Final = 17214
    """Indicates that the provided Firebase Hosting Link domain is not owned by the current project."""
    REJECTED_CREDENTIAL: Final = 17075
    """Indicates that the credential is rejected because it's malformed or mismatching."""
    GAME_KIT_NOT_LINKED: Final = 17076
    """Indicates that the GameKit framework is not linked prior to attempting Game Center signin."""
    SECOND_FACTOR_REQUIRED: Final = 17078
    """Indicates that the second factor is required for signin."""
    MISSING_MULTI_FACTOR_SESSION: Final = 17081
    """Indicates that the multi factor session is missing."""
    MISSING_MULTI_FACTOR_INFO: Final = 17082
    """Indicates that the multi factor info is missing."""
    INVALID_MULTI_FACTOR_SESSION: Final = 17083
    """Indicates that the multi factor session is invalid."""
    MULTI_FACTOR_INFO_NOT_FOUND: Final = 17084
    """Indicates that the multi factor info is not found."""
    ADMIN_RESTRICTED_OPERATION: Final = 17085
    """Indicates that the operation is admin restricted."""
    UNVERIFIED_EMAIL: Final = 17086
    """Indicates that the email is required for verification."""
    SECOND_FACTOR_ALREADY_ENROLLED: Final = 17087
    """Indicates that the second factor is already enrolled."""
    MAXIMUM_SECOND_FACTOR_COUNT_EXCEEDED: Final = 17088
    """Indicates that the maximum second factor count is exceeded."""
    UNSUPPORTED_FIRST_FACTOR: Final = 17089
    """Indicates that the first factor is not supported."""
    EMAIL_CHANGE_NEEDS_VERIFICATION: Final = 17090
    """Indicates that the a verified email is required to changed to."""
    MISSING_CLIENT_IDENTIFIER: Final = 17093
    """Indicates that the request does not contain a client identifier."""
    MISSING_OR_INVALID_NONCE: Final = 17094
    """Indicates that the nonce is missing or invalid."""
    BLOCKING_CLOUD_FUNCTION_ERROR: Final = 17105
    """Raised when a Cloud Function returns a blocking error."""
    RECAPTCHA_NOT_ENABLED: Final = 17200
    """Indicates that reCAPTCHA Enterprise integration is not enabled for this project."""
    MISSING_RECAPTCHA_TOKEN: Final = 17201
    """Indicates that the reCAPTCHA token is missing from the backend request."""
    INVALID_RECAPTCHA_TOKEN: Final = 17202
    """Indicates that the reCAPTCHA token sent with the backend request is invalid."""
    INVALID_RECAPTCHA_ACTION: Final = 17203
    """Indicates that the requested reCAPTCHA action is invalid."""
    MISSING_CLIENT_TYPE: Final = 17204
    """Indicates that the client type is missing from the request."""
    MISSING_RECAPTCHA_VERSION: Final = 17205
    """Indicates that the reCAPTCHA version is missing from the request."""
    INVALID_RECAPTCHA_VERSION: Final = 17206
    """Indicates that the reCAPTCHA version sent to the backend is invalid."""
    INVALID_REQ_TYPE: Final = 17207
    """Indicates that the request type sent to the backend is invalid."""
    RECAPTCHA_SDK_NOT_LINKED: Final = 17208
    """Indicates that the reCAPTCHA SDK is not linked to the app."""
    RECAPTCHA_SITE_KEY_MISSING: Final = 17209
    """Indicates that the reCAPTCHA SDK site key wasn't found."""
    RECAPTCHA_ACTION_CREATION_FAILED: Final = 17210
    """Indicates that the reCAPTCHA SDK actions class failed to create."""
    PASSWORD_DOES_NOT_MEET_REQUIREMENTS: Final = 17211
    """Indicates that the password does not meet the project's password policy."""
    KEYCHAIN_ERROR: Final = 17995
    """Indicates an error occurred while attempting to access the keychain."""
    INTERNAL_ERROR: Final = 17999
    """Indicates an internal error occurred."""
    MALFORMED_JWT: Final = 18000
    """Raised when a JWT fails to parse correctly."""


_CODE_NAMES: Final[dict[int, str]] = {
    value: name for name, value in vars(AuthErrorCode).items() if isinstance(value, int)
}


class AuthError(FirebaseError):
    """An error from Firebase Authentication (or from a sign-in sheet)."""

    name: str
    """The ``AuthErrorCode`` name of ``code`` (for example ``"WRONG_PASSWORD"``),
    or ``""`` for errors from other domains."""
    email: str | None
    """The email address the error is about, when Firebase gives one (for
    example with ``ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL``)."""
    updated_credential: AuthCredential | None
    """With ``ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`` and
    ``CREDENTIAL_ALREADY_IN_USE``: a credential to sign in with instead."""
    resolver: MultiFactorResolver | None
    """With ``SECOND_FACTOR_REQUIRED``: finishes the sign-in with a second
    factor (see ``pyios_firebase.auth.multi_factor``)."""
    cancelled: bool
    """True when the user closed a sign-in sheet (Google, Apple, web
    providers): not a failure to report."""
    message: str
    """A sentence to show to the user, when the library has a better one than
    ``description`` (Apple sign-in); otherwise ``""``."""


def auth_error_from_nserror(error: ObjCObject) -> AuthError:
    """Turn an ``NSError`` from Firebase Auth into an ``AuthError``.

    Args:
        error: the ``NSError``.

    Returns:
        An ``AuthError`` with the ``FirebaseError`` keys, plus ``name``,
        ``email``, ``updated_credential``, ``resolver``, ``cancelled``
        (False) and ``message`` (``""``).
    """
    from .credentials import AuthCredential
    from .multi_factor import MultiFactorResolver

    result = AuthError(nserror_to_dict(error) or {})
    is_auth = result.domain == AUTH_ERROR_DOMAIN
    result.name = _CODE_NAMES.get(result.code, "") if is_auth else ""
    user_info = error.userInfo
    email = user_info.objectForKey_(_EMAIL_KEY)
    result.email = None if email is None else str(email)
    credential = user_info.objectForKey_(_UPDATED_CREDENTIAL_KEY)
    result.updated_credential = (
        None if credential is None else AuthCredential(credential)
    )
    resolver = user_info.objectForKey_(_RESOLVER_KEY)
    result.resolver = None if resolver is None else MultiFactorResolver(resolver)
    result.cancelled = is_auth and result.code == AuthErrorCode.WEB_CONTEXT_CANCELLED
    result.message = ""
    return result


def auth_error_from_pointer(error_ptr: Any) -> AuthError | None:
    """``auth_error_from_nserror`` for a raw block argument.

    Args:
        error_ptr: the ``NSError *`` a completion block received, or a null
            pointer / ``None`` when there was no error.

    Returns:
        An ``AuthError``, or ``None`` when there was no error.
    """
    return auth_error_from_nserror(objc_instance(error_ptr)) if error_ptr else None


def simple_auth_error(
    description: str, code: int = 0, *, cancelled: bool = False
) -> AuthError:
    """An ``AuthError`` made in Python, for failures before Firebase is called.

    Args:
        description: what went wrong.
        code: the error code; 0 when there is none.
        cancelled: True when the user cancelled.

    Returns:
        An ``AuthError`` with an empty ``domain``.
    """
    return AuthError(
        code=code,
        description=description,
        domain="",
        underlying_error=None,
        name="",
        email=None,
        updated_credential=None,
        resolver=None,
        cancelled=cancelled,
        message="",
    )

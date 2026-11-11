"""Firebase Authentication.

    from pyios_firebase.auth import Auth

    auth = Auth.auth()
    auth.create_user_with_email_password("ada@example.com", "s3cret!", on_signed_in)
    listener = auth.add_state_did_change_listener(lambda user: print("user:", user))

- ``Auth``: sign-in (email/password, email link, anonymous, custom token,
  credentials, OAuth web flows), sign-out, listeners, password reset and
  action codes, the emulator
- ``User``: profile, ID tokens and claims, account changes, email
  verification, linking and re-authentication
- credentials: ``EmailAuthProvider``, ``GoogleAuthProvider``,
  ``OAuthProvider`` (Apple, Microsoft, Yahoo, GitHub, OIDC, SAML),
  ``PhoneAuthProvider``, ``FacebookAuthProvider``, ``GitHubAuthProvider``,
  ``TwitterAuthProvider``, ``GameCenterAuthProvider``
- ``pyios_firebase.auth.google`` / ``pyios_firebase.auth.apple``: the Google and
  Apple sign-in sheets
- multi-factor (``pyios_firebase.auth.multi_factor``): SMS and TOTP second factors
- ``AuthError`` / ``AuthErrorCode``: what failed

Needs the ``FirebaseAuth`` framework. Google sign-in also needs
``GoogleSignIn``; Apple sign-in needs the ``com.apple.developer.applesignin``
entitlement.
"""

from .auth import (
    APNS_TOKEN_TYPE_PRODUCTION,
    APNS_TOKEN_TYPE_SANDBOX,
    APNS_TOKEN_TYPE_UNKNOWN,
    Auth,
    AuthStateListener,
)
from .credentials import (
    AuthCredential,
    EmailAuthProvider,
    FacebookAuthProvider,
    GameCenterAuthProvider,
    GitHubAuthProvider,
    GoogleAuthProvider,
    OAuthCredential,
    OAuthProvider,
    PhoneAuthProvider,
    TwitterAuthProvider,
)
from .errors import AUTH_ERROR_DOMAIN, AuthError, AuthErrorCode
from .multi_factor import (
    PHONE_FACTOR_ID,
    TOTP_FACTOR_ID,
    MultiFactor,
    MultiFactorAssertion,
    MultiFactorInfo,
    MultiFactorResolver,
    MultiFactorSession,
    PhoneMultiFactorGenerator,
    PhoneMultiFactorInfo,
    TOTPMultiFactorGenerator,
    TOTPSecret,
)
from .results import (
    ActionCodeInfo,
    ActionCodeOperation,
    ActionCodeSettings,
    ActionCodeURL,
    AdditionalUserInfo,
    AuthDataResult,
    IDTokenResult,
    UserInfo,
    UserMetadata,
)
from .user import UNSET, User

__all__ = (
    "APNS_TOKEN_TYPE_PRODUCTION",
    "APNS_TOKEN_TYPE_SANDBOX",
    "APNS_TOKEN_TYPE_UNKNOWN",
    "AUTH_ERROR_DOMAIN",
    "PHONE_FACTOR_ID",
    "TOTP_FACTOR_ID",
    "UNSET",
    "ActionCodeInfo",
    "ActionCodeOperation",
    "ActionCodeSettings",
    "ActionCodeURL",
    "AdditionalUserInfo",
    "Auth",
    "AuthCredential",
    "AuthDataResult",
    "AuthError",
    "AuthErrorCode",
    "AuthStateListener",
    "EmailAuthProvider",
    "FacebookAuthProvider",
    "GameCenterAuthProvider",
    "GitHubAuthProvider",
    "GoogleAuthProvider",
    "IDTokenResult",
    "MultiFactor",
    "MultiFactorAssertion",
    "MultiFactorInfo",
    "MultiFactorResolver",
    "MultiFactorSession",
    "OAuthCredential",
    "OAuthProvider",
    "PhoneAuthProvider",
    "PhoneMultiFactorGenerator",
    "PhoneMultiFactorInfo",
    "TOTPMultiFactorGenerator",
    "TOTPSecret",
    "TwitterAuthProvider",
    "User",
    "UserInfo",
    "UserMetadata",
    "current_user",
    "sign_out",
)


def current_user() -> User | None:
    """The signed-in ``User``, or ``None``. Same as ``Auth.auth().current_user``."""
    return Auth.auth().current_user


def sign_out() -> AuthError | None:
    """Sign the current user out of Firebase. Same as ``Auth.auth().sign_out()``.

    Returns:
        ``None``, or the error.
    """
    return Auth.auth().sign_out()

"""Sign-in credentials and the providers that make them.

A credential proves who the user is to one provider. Pass it to
``Auth.sign_in_with_credential``, ``User.link_with_credential`` or
``User.reauthenticate_with_credential``::

    credential = EmailAuthProvider.credential("ada@example.com", "s3cret!")
    Auth.auth().sign_in_with_credential(credential, on_signed_in)
"""

from __future__ import annotations

__all__ = (
    "AuthCredential",
    "EmailAuthProvider",
    "FacebookAuthProvider",
    "GameCenterAuthProvider",
    "GitHubAuthProvider",
    "GoogleAuthProvider",
    "OAuthCredential",
    "OAuthProvider",
    "PhoneAuthProvider",
    "TwitterAuthProvider",
)

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Final

from rubicon.objc import ns_from_py

from ..types import ObjCObject
from ..util import objc_class, to_python
from ._common import missing_callback_scheme, result_block, string_block, text
from .errors import AuthError, simple_auth_error

if TYPE_CHECKING:
    from .auth import Auth
    from .multi_factor import MultiFactorSession, PhoneMultiFactorInfo

CredentialCallback = Callable[["AuthCredential | None", AuthError | None], None]
"""``(credential, error)``: exactly one of them is ``None``."""


class AuthCredential:
    """A sign-in credential for one provider.

    Make credentials with the provider classes (``EmailAuthProvider``,
    ``GoogleAuthProvider``, ...); you do not create them yourself.

    Args:
        native: the native ``FIRAuthCredential``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRAuthCredential``, for SDK calls this wrapper does not cover."""
        return self._native

    @property
    def provider(self) -> str:
        """The provider ID, for example ``"password"`` or ``"google.com"``."""
        return str(self._native.provider)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(provider={self.provider!r})"


class OAuthCredential(AuthCredential):
    """A credential from an OAuth provider (Apple, Microsoft, Yahoo, ...).

    Args:
        native: the native ``FIROAuthCredential``.
    """

    @property
    def id_token(self) -> str | None:
        """The OpenID Connect ID token, if the provider gave one."""
        return text(self._native.IDToken)

    @property
    def access_token(self) -> str | None:
        """The OAuth access token, if the provider gave one."""
        return text(self._native.accessToken)

    @property
    def secret(self) -> str | None:
        """The OAuth 1.0 token secret, if the provider gave one."""
        return text(self._native.secret)


def _wrap_credential(native: ObjCObject) -> AuthCredential:
    if native.isKindOfClass(objc_class("FIROAuthCredential")):
        return OAuthCredential(native)
    return AuthCredential(native)


# ---- providers ------------------------------------------------------------------


class EmailAuthProvider:
    """Credentials for email and password, or email link, sign-in."""

    PROVIDER_ID: Final = "password"
    """The provider ID of email sign-in (both password and link)."""

    @staticmethod
    def credential(email: str, password: str) -> AuthCredential:
        """A credential for an email address and password.

        Args:
            email: the email address.
            password: the password.

        Returns:
            An ``AuthCredential`` for ``"password"``.
        """
        return AuthCredential(
            objc_class("FIREmailAuthProvider").credentialWithEmail_password_(
                email, password
            )
        )

    @staticmethod
    def credential_with_link(email: str, link: str) -> AuthCredential:
        """A credential for an email address and a sign-in link sent to it.

        Args:
            email: the email address the link was sent to.
            link: the full sign-in link the user opened.

        Returns:
            An ``AuthCredential`` for ``"password"``.
        """
        return AuthCredential(
            objc_class("FIREmailAuthProvider").credentialWithEmail_link_(email, link)
        )


class GoogleAuthProvider:
    """Credentials from Google Sign-In tokens. For the whole flow, see
    ``pyios_firebase.auth.google``."""

    PROVIDER_ID: Final = "google.com"
    """The provider ID of Google sign-in."""

    @staticmethod
    def credential(id_token: str, access_token: str) -> AuthCredential:
        """A credential from the tokens Google Sign-In gives.

        Args:
            id_token: the Google ID token (``GIDGoogleUser.idToken.tokenString``).
            access_token: the Google access token
                (``GIDGoogleUser.accessToken.tokenString``).

        Returns:
            An ``AuthCredential`` for ``"google.com"``.
        """
        return AuthCredential(
            objc_class("FIRGoogleAuthProvider").credentialWithIDToken_accessToken_(
                id_token, access_token
            )
        )


class FacebookAuthProvider:
    """Credentials from Facebook Login access tokens."""

    PROVIDER_ID: Final = "facebook.com"
    """The provider ID of Facebook sign-in."""

    @staticmethod
    def credential(access_token: str) -> AuthCredential:
        """A credential from a Facebook access token.

        Args:
            access_token: the access token Facebook Login gave.

        Returns:
            An ``AuthCredential`` for ``"facebook.com"``.
        """
        return AuthCredential(
            objc_class("FIRFacebookAuthProvider").credentialWithAccessToken_(
                access_token
            )
        )


class GitHubAuthProvider:
    """Credentials from GitHub OAuth access tokens (for the web flow, use
    ``OAuthProvider("github.com")``)."""

    PROVIDER_ID: Final = "github.com"
    """The provider ID of GitHub sign-in."""

    @staticmethod
    def credential(token: str) -> AuthCredential:
        """A credential from a GitHub OAuth access token.

        Args:
            token: the GitHub access token.

        Returns:
            An ``AuthCredential`` for ``"github.com"``.
        """
        return AuthCredential(
            objc_class("FIRGitHubAuthProvider").credentialWithToken_(token)
        )


class TwitterAuthProvider:
    """Credentials from Twitter (X) OAuth 1.0 tokens."""

    PROVIDER_ID: Final = "twitter.com"
    """The provider ID of Twitter sign-in."""

    @staticmethod
    def credential(token: str, secret: str) -> AuthCredential:
        """A credential from a Twitter OAuth token and secret.

        Args:
            token: the OAuth token.
            secret: the OAuth token secret.

        Returns:
            An ``AuthCredential`` for ``"twitter.com"``.
        """
        return AuthCredential(
            objc_class("FIRTwitterAuthProvider").credentialWithToken_secret_(
                token, secret
            )
        )


_NOT_GENERIC: Final = {
    "facebook.com": "Facebook sign-in needs the Facebook SDK: pass its access token to "
    "FacebookAuthProvider.credential",
    "apple.com": "Sign in with Apple needs Apple's sheet: use pyios_firebase.auth.apple, "
    "or OAuthProvider.apple_credential with Apple's identity token",
}


class OAuthProvider:
    """A generic OAuth provider: Apple, Microsoft, Yahoo, GitHub, or any OIDC /
    SAML provider set up in the Firebase console.

    As an object, it runs the provider's web sign-in flow
    (``Auth.sign_in_with_provider``, ``get_credential``). The static methods
    make credentials from tokens you already have.

    ::

        microsoft = OAuthProvider("microsoft.com", scopes=["mail.read"])
        Auth.auth().sign_in_with_provider(microsoft, on_signed_in)

    Args:
        provider_id: the provider ID, for example ``"microsoft.com"``,
            ``"yahoo.com"``, ``"github.com"``, ``"oidc.my-provider"``. Not
            ``"facebook.com"`` or ``"apple.com"`` (except on the emulator):
            those need their own SDKs.
        scopes: OAuth scopes to ask for, beyond the provider's defaults.
        custom_parameters: extra OAuth parameters, for example
            ``{"prompt": "consent"}`` or ``{"tenant": "my-tenant-id"}``.
        auth: the ``Auth`` instance to use (default: ``Auth.auth()``).

    Raises:
        ValueError: ``provider_id`` is ``"facebook.com"`` or ``"apple.com"``
            outside the emulator (the SDK would stop the app).
    """

    APPLE_PROVIDER_ID: Final = "apple.com"
    """The provider ID of Sign in with Apple."""

    def __init__(
        self,
        provider_id: str,
        scopes: Sequence[str] | None = None,
        custom_parameters: Mapping[str, str] | None = None,
        auth: Auth | None = None,
    ) -> None:
        from .auth import Auth

        self._auth = auth if auth is not None else Auth.auth()
        if provider_id in _NOT_GENERIC and not self._auth.is_using_emulator:
            # the SDK stops the app for these: say what to use instead
            raise ValueError(_NOT_GENERIC[provider_id])
        fir = objc_class("FIROAuthProvider")
        if auth is None:
            self._native: ObjCObject = fir.providerWithProviderID_(provider_id)
        else:
            self._native = fir.providerWithProviderID_auth_(provider_id, auth.native)
        if scopes is not None:
            self.scopes = list(scopes)
        if custom_parameters is not None:
            self.custom_parameters = dict(custom_parameters)

    @property
    def native(self) -> ObjCObject:
        """The ``FIROAuthProvider``."""
        return self._native

    @property
    def provider_id(self) -> str:
        """The provider ID."""
        return str(self._native.providerID)

    @property
    def scopes(self) -> list[str]:
        """The OAuth scopes asked for (beyond the provider's defaults)."""
        scopes = self._native.scopes
        return [] if scopes is None else [str(scope) for scope in scopes]

    @scopes.setter
    def scopes(self, scopes: Sequence[str]) -> None:
        self._native.scopes = ns_from_py(list(scopes))

    @property
    def custom_parameters(self) -> dict[str, str]:
        """Extra OAuth parameters sent to the provider."""
        params = self._native.customParameters
        return (
            {}
            if params is None
            else {str(k): str(v) for k, v in to_python(params).items()}
        )

    @custom_parameters.setter
    def custom_parameters(self, params: Mapping[str, str]) -> None:
        self._native.customParameters = ns_from_py(dict(params))

    def get_credential(self, callback: CredentialCallback) -> None:
        """Run the provider's web sign-in flow and give back the credential,
        without signing in (for example to link it to the current user).

        Shows the provider's page in an in-app browser. The app's
        ``Info.plist`` needs the URL scheme Firebase documents for the provider.

        Args:
            callback: gets ``(credential, None)``, or ``(None, error)``.
                ``error.cancelled`` is True when the user closed the browser.
                If the callback URL scheme is missing from ``Info.plist``, the
                error says which one to add (the SDK itself would stop the app).
        """
        problem = missing_callback_scheme(self._auth.native)
        if problem is not None:
            callback(None, simple_auth_error(problem))
            return
        self._native.getCredentialWithUIDelegate_completion_(
            None, result_block(callback, _wrap_credential)
        )

    @staticmethod
    def credential(
        provider_id: str,
        id_token: str | None = None,
        access_token: str | None = None,
        raw_nonce: str | None = None,
    ) -> OAuthCredential:
        """A credential from tokens you already have.

        Args:
            provider_id: the provider ID, for example ``"microsoft.com"``.
            id_token: the OpenID Connect ID token, if any.
            access_token: the OAuth access token, if any.
            raw_nonce: the raw (unhashed) nonce the ID token was made for, if any.

        Returns:
            An ``OAuthCredential``.

        Raises:
            ValueError: neither ``id_token`` nor ``access_token`` is given, or
                ``raw_nonce`` is given without ``id_token``.
        """
        # check the arguments before touching the SDK
        if id_token is None and access_token is None:
            raise ValueError("give an id_token, an access_token, or both")
        if raw_nonce is not None and id_token is None:
            raise ValueError("raw_nonce needs an id_token")
        fir = objc_class("FIROAuthProvider")
        if id_token is not None and raw_nonce is not None:
            if access_token is not None:
                native = fir.credentialWithProviderID_IDToken_rawNonce_accessToken_(
                    provider_id, id_token, raw_nonce, access_token
                )
            else:
                native = fir.credentialWithProviderID_IDToken_rawNonce_(
                    provider_id, id_token, raw_nonce
                )
        elif id_token is not None:
            native = fir.credentialWithProviderID_IDToken_accessToken_(
                provider_id, id_token, access_token
            )
        else:
            native = fir.credentialWithProviderID_accessToken_(
                provider_id, access_token
            )
        return OAuthCredential(native)

    @staticmethod
    def apple_credential(
        id_token: str,
        raw_nonce: str | None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> OAuthCredential:
        """A Sign in with Apple credential. For the whole flow, see
        ``pyios_firebase.auth.apple``.

        Args:
            id_token: the identity token Apple gave (as a string).
            raw_nonce: the raw nonce whose SHA-256 was sent to Apple, or ``None``.
            given_name: the user's given name, which Apple shares only on the
                first sign-in. Passing it saves it in Firebase.
            family_name: the user's family name (same as ``given_name``).

        Returns:
            An ``OAuthCredential`` for ``"apple.com"``.
        """
        full_name = None
        if given_name or family_name:
            full_name = objc_class("NSPersonNameComponents").alloc().init()
            full_name.givenName = given_name or None
            full_name.familyName = family_name or None
        return OAuthCredential(
            objc_class(
                "FIROAuthProvider"
            ).appleCredentialWithIDToken_rawNonce_fullName_(
                id_token, raw_nonce, full_name
            )
        )


class PhoneAuthProvider:
    """Phone number sign-in: send a code by SMS, then make a credential from it.

    ::

        phone = PhoneAuthProvider()
        phone.verify_phone_number("+15555550100", on_code_sent)
        # later, with the code the user typed:
        credential = phone.credential(verification_id, "123456")

    Real phone sign-in needs push notifications (APNs) or reCAPTCHA set up; see
    Firebase's phone auth guide. With ``Auth.use_emulator`` it works without
    them. Either way, the app's ``Info.plist`` needs the callback URL scheme:
    the reversed client ID, or ``app-`` + the GOOGLE_APP_ID with ``-`` for ``:``.

    Args:
        auth: the ``Auth`` instance to use (default: ``Auth.auth()``).
    """

    PROVIDER_ID: Final = "phone"
    """The provider ID of phone sign-in."""

    def __init__(self, auth: Auth | None = None) -> None:
        fir = objc_class("FIRPhoneAuthProvider")
        self._native: ObjCObject = (
            fir.provider() if auth is None else fir.providerWithAuth_(auth.native)
        )
        self._auth_native: ObjCObject = (
            objc_class("FIRAuth").auth() if auth is None else auth.native
        )

    def verify_phone_number(
        self,
        phone_number: str,
        callback: Callable[[str | None, AuthError | None], None],
        multi_factor_session: MultiFactorSession | None = None,
    ) -> None:
        """Send a verification code to ``phone_number`` by SMS.

        Args:
            phone_number: the number in E.164 format, for example ``"+15555550100"``.
            callback: gets ``(verification_id, None)``, or ``(None, error)``.
                Keep ``verification_id`` for ``credential``. If the callback
                URL scheme is missing from ``Info.plist``, the error says which
                one to add (the SDK itself would stop the app).
            multi_factor_session: to enroll the number as a second factor: the
                session from ``MultiFactor.get_session``. ``None`` for sign-in
                with the number.
        """
        problem = missing_callback_scheme(self._auth_native)
        if problem is not None:
            callback(None, simple_auth_error(problem))
            return
        session = None if multi_factor_session is None else multi_factor_session.native
        self._native.verifyPhoneNumber_UIDelegate_multiFactorSession_completion_(
            phone_number, None, session, string_block(callback)
        )

    def verify_phone_number_for_sign_in(
        self,
        hint: PhoneMultiFactorInfo,
        session: MultiFactorSession,
        callback: Callable[[str | None, AuthError | None], None],
    ) -> None:
        """Send the SMS code of an enrolled second factor, to finish a sign-in.

        Args:
            hint: the phone factor chosen from ``MultiFactorResolver.hints``.
            session: ``MultiFactorResolver.session``.
            callback: gets ``(verification_id, None)``, or ``(None, error)``.
        """
        problem = missing_callback_scheme(self._auth_native)
        if problem is not None:
            callback(None, simple_auth_error(problem))
            return
        self._native.verifyPhoneNumberWithMultiFactorInfo_UIDelegate_multiFactorSession_completion_(
            hint.native, None, session.native, string_block(callback)
        )

    def credential(
        self, verification_id: str, verification_code: str
    ) -> AuthCredential:
        """A credential from the code the user received.

        Args:
            verification_id: what ``verify_phone_number`` gave.
            verification_code: the code from the SMS.

        Returns:
            An ``AuthCredential`` for ``"phone"``.
        """
        return AuthCredential(
            self._native.credentialWithVerificationID_verificationCode_(
                verification_id, verification_code
            )
        )


class GameCenterAuthProvider:
    """Credentials for the Game Center player signed in on the device."""

    PROVIDER_ID: Final = "gc.apple.com"
    """The provider ID of Game Center sign-in."""

    @staticmethod
    def get_credential(callback: CredentialCallback) -> None:
        """A credential for the local Game Center player.

        The player must already be signed in to Game Center (``GKLocalPlayer``).

        Args:
            callback: gets ``(credential, None)``, or ``(None, error)``
                (``LOCAL_PLAYER_NOT_AUTHENTICATED`` if nobody is signed in).
        """
        objc_class("FIRGameCenterAuthProvider").getCredentialWithCompletion_(
            result_block(callback, _wrap_credential)
        )

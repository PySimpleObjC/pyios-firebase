from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import NSObject, ns_from_py

import pyios_firebase.auth.credentials as credentials_module
import pyios_firebase.auth.results as results_module
import pyios_firebase.auth.user as user_module
from pyios_firebase.auth import (
    ActionCodeSettings,
    Auth,
    AuthDataResult,
    AuthErrorCode,
    OAuthProvider,
    User,
)
from pyios_firebase.auth._common import flag
from pyios_firebase.auth.errors import AUTH_ERROR_DOMAIN, auth_error_from_nserror


def auth_error(code, **info):
    return make_error("boom", code, AUTH_ERROR_DOMAIN, **info)


# ---- errors ---------------------------------------------------------------------


def test_auth_error_names_and_extra_keys():
    credential = NSObject.new()
    error = auth_error_from_nserror(
        auth_error(
            AuthErrorCode.ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL,
            FIRAuthErrorUserInfoEmailKey="ada@example.com",
            FIRAuthErrorUserInfoUpdatedCredentialKey=credential,
        )
    )
    assert (
        error.code == 17012 and error.name == "ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL"
    )
    assert error.email == "ada@example.com"
    assert (
        error.updated_credential is not None
        and error.updated_credential.native == credential
    )
    assert error.cancelled is False and error.message == ""


def test_web_context_cancelled_is_a_cancel():
    error = auth_error_from_nserror(auth_error(AuthErrorCode.WEB_CONTEXT_CANCELLED))
    assert error.cancelled is True


def test_non_auth_errors_have_no_name():
    error = auth_error_from_nserror(make_error("x", 17007, "SomeOtherDomain"))
    assert error.name == "" and error.email is None and error.updated_credential is None


def test_error_codes_are_unique_and_match_the_sdk():
    codes = {k: v for k, v in vars(AuthErrorCode).items() if isinstance(v, int)}
    assert len(codes) == len(set(codes.values())) > 80
    assert codes["EMAIL_ALREADY_IN_USE"] == 17007
    assert codes["INVALID_API_KEY"] == 17023
    assert codes["RECAPTCHA_SDK_NOT_LINKED"] == 17208
    assert codes["MALFORMED_JWT"] == 18000


# ---- Swift Bool properties ------------------------------------------------------------


@pytest.mark.parametrize("value", [True, False])
def test_flag_reads_attributes_and_custom_getters(value):
    assert flag(SimpleNamespace(isAnonymous=value), "isAnonymous") is value
    assert flag(SimpleNamespace(isAnonymous=lambda: value), "isAnonymous") is value


# ---- Auth calls ------------------------------------------------------------------


def test_sign_in_with_email_password_success_and_error(blocks):
    native, out = Recorder(), []
    Auth(native).sign_in_with_email_password(
        "a@b.c", "pw", lambda r, e: out.append((r, e))
    )
    name, args = native.calls[-1]
    assert name == "signInWithEmail_password_completion_" and args[:2] == (
        "a@b.c",
        "pw",
    )
    fire(args[-1], NSObject.new(), None)
    assert isinstance(out[0][0], AuthDataResult) and out[0][1] is None

    Auth(native).create_user_with_email_password(
        "a@b.c", "pw", lambda r, e: out.append((r, e))
    )
    assert native.calls[-1][0] == "createUserWithEmail_password_completion_"
    fire(native.block(), None, auth_error(AuthErrorCode.EMAIL_ALREADY_IN_USE))
    assert out[1][0] is None and out[1][1].name == "EMAIL_ALREADY_IN_USE"
    assert not blocks


@pytest.mark.parametrize(
    ("call", "selector"),
    [
        (lambda a, cb: a.sign_in_anonymously(cb), "signInAnonymouslyWithCompletion_"),
        (
            lambda a, cb: a.sign_in_with_custom_token("t", cb),
            "signInWithCustomToken_completion_",
        ),
        (
            lambda a, cb: a.sign_in_with_email_link("e", "l", cb),
            "signInWithEmail_link_completion_",
        ),
        (
            lambda a, cb: a.send_password_reset("e", cb),
            "sendPasswordResetWithEmail_actionCodeSettings_completion_",
        ),
        (
            lambda a, cb: a.confirm_password_reset("c", "p", cb),
            "confirmPasswordResetWithCode_newPassword_completion_",
        ),
        (
            lambda a, cb: a.verify_password_reset_code("c", cb),
            "verifyPasswordResetCode_completion_",
        ),
        (lambda a, cb: a.apply_action_code("c", cb), "applyActionCode_completion_"),
        (
            lambda a, cb: a.revoke_token("c", cb),
            "revokeTokenWithAuthorizationCode_completion_",
        ),
    ],
)
def test_auth_methods_use_the_sdk_selectors(blocks, call, selector):
    native = Recorder()
    call(Auth(native), lambda *args: None)
    assert native.calls[-1][0] == selector
    assert len(blocks) == 1


def test_verify_password_reset_code_gives_the_email(blocks):
    native, out = Recorder(), []
    Auth(native).verify_password_reset_code(
        "code", lambda email, e: out.append((email, e))
    )
    fire(native.block(), ns_from_py("ada@example.com"), None)
    assert out == [("ada@example.com", None)]


def test_current_user(monkeypatch):
    monkeypatch.setattr(user_module, "objc_class", lambda name: Recorder())
    assert Auth(SimpleNamespace(currentUser=None)).current_user is None
    native_user = SimpleNamespace(uid="u1", email=None)
    user = Auth(SimpleNamespace(currentUser=native_user)).current_user
    assert user is not None and user.uid == "u1" and user.email is None


def test_state_listener_add_and_remove(blocks, monkeypatch):
    monkeypatch.setattr(user_module, "objc_class", lambda name: Recorder())
    handle = NSObject.new()
    native, seen = Recorder({"addAuthStateDidChangeListener_": handle}), []
    listener = Auth(native).add_state_did_change_listener(seen.append)
    block = native.block("addAuthStateDidChangeListener_")
    fire(block, NSObject.new(), None)  # signed out
    fire(block, NSObject.new(), NSObject.new())  # signed in
    assert seen[0] is None and isinstance(seen[1], User)
    assert block in blocks
    listener.remove()
    listener.remove()  # safe twice
    assert native.calls.count(("removeAuthStateDidChangeListener_", (handle,))) == 1
    assert not blocks


# ---- User ------------------------------------------------------------------------


def test_signed_out_user(monkeypatch):
    monkeypatch.setattr(
        user_module,
        "objc_class",
        lambda name: SimpleNamespace(auth=lambda: SimpleNamespace(currentUser=None)),
    )
    user = User()
    assert not user.is_signed_in and user.uid is None and not user.is_anonymous
    assert user.provider_data == [] and user.metadata is None
    with pytest.raises(RuntimeError, match="no user is signed in"):
        user.reload()


def test_update_profile_leaves_unset_fields(monkeypatch):
    request = Recorder()
    native = Recorder({"profileChangeRequest": request})
    monkeypatch.setattr(user_module, "objc_class", lambda name: Recorder())
    User(native).update_profile(display_name="Ada")
    assert request.displayName == "Ada" and "photoURL" not in vars(request)
    assert request.calls[-1][0] == "commitChangesWithCompletion_"
    User(native).update_profile(photo_url=None)
    assert request.photoURL is None


# ---- credentials and settings ------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "selector"),
    [
        ({"id_token": "i"}, "credentialWithProviderID_IDToken_accessToken_"),
        ({"access_token": "a"}, "credentialWithProviderID_accessToken_"),
        (
            {"id_token": "i", "raw_nonce": "n"},
            "credentialWithProviderID_IDToken_rawNonce_",
        ),
        (
            {"id_token": "i", "raw_nonce": "n", "access_token": "a"},
            "credentialWithProviderID_IDToken_rawNonce_accessToken_",
        ),
    ],
)
def test_oauth_credential_picks_the_selector(monkeypatch, kwargs, selector):
    fake = Recorder()
    monkeypatch.setattr(credentials_module, "objc_class", lambda name: fake)
    OAuthProvider.credential("microsoft.com", **kwargs)
    assert fake.calls[-1][0] == selector


def test_oauth_credential_needs_a_token():
    with pytest.raises(ValueError, match="id_token"):
        OAuthProvider.credential("microsoft.com")
    with pytest.raises(ValueError, match="raw_nonce"):
        OAuthProvider.credential("microsoft.com", access_token="a", raw_nonce="n")


def test_action_code_settings_to_native(monkeypatch):
    native = Recorder()
    monkeypatch.setattr(
        results_module,
        "objc_class",
        lambda name: Recorder(
            {"alloc": lambda: Recorder({"init": native}), "URLWithString_": "URL"}
        ),
    )
    ActionCodeSettings(
        url="https://x",
        handle_code_in_app=True,
        ios_bundle_id="b",
        android_package_name="p",
    ).to_native()
    assert (
        native.URL == "URL"
        and native.handleCodeInApp is True
        and native.iOSBundleID == "b"
    )
    assert native.calls[-1] == (
        "setAndroidPackageName_installIfNotAvailable_minimumVersion_",
        ("p", False, None),
    )


def test_a_result_that_cannot_be_read_still_answers(blocks):
    def broken(_native):
        raise ValueError("unexpected shape")

    from pyios_firebase.auth._common import result_block

    out = []
    block = result_block(lambda r, e: out.append((r, e)), broken)
    fire(block, NSObject.new(), None)
    assert out[0][0] is None and "unexpected shape" in out[0][1].description
    assert not blocks


# ---- guards against the SDK stopping the app (fatalError) --------------------------

import pyios_firebase.auth._common as common_module

APP_ID = "1:1234567890:ios:0123456789abcdef"
APP_SCHEME = "app-1-1234567890-ios-0123456789abcdef"


def _auth_native(client_id=None, app_id=APP_ID):
    options = SimpleNamespace(clientID=client_id, googleAppID=app_id)
    return SimpleNamespace(
        app=SimpleNamespace(options=options), ptr=SimpleNamespace(value=4242)
    )


def _with_url_schemes(monkeypatch, *schemes):
    url_types = ns_from_py([{"CFBundleURLSchemes": list(schemes)}]) if schemes else None
    bundle = SimpleNamespace(objectForInfoDictionaryKey_=lambda key: url_types)
    monkeypatch.setattr(
        common_module, "objc_class", lambda name: SimpleNamespace(mainBundle=bundle)
    )


@pytest.mark.parametrize(
    ("client_id", "schemes", "ok"),
    [
        (None, (), False),
        (None, (APP_SCHEME,), True),
        (None, (APP_SCHEME.upper(),), True),  # the SDK compares case-insensitively
        (
            "123-abc.apps.googleusercontent.com",
            ("com.googleusercontent.apps.123-abc",),
            True,
        ),
        ("123-abc.apps.googleusercontent.com", (APP_SCHEME,), True),
        ("123-abc.apps.googleusercontent.com", ("something.else",), False),
    ],
)
def test_missing_callback_scheme(monkeypatch, client_id, schemes, ok):
    _with_url_schemes(monkeypatch, *schemes)
    problem = common_module.missing_callback_scheme(_auth_native(client_id))
    if ok:
        assert problem is None
    else:
        assert problem is not None and APP_SCHEME in problem and "Info.plist" in problem


def test_missing_callback_scheme_without_firebase():
    assert "configure" in common_module.missing_callback_scheme(
        SimpleNamespace(app=None)
    )


def test_phone_verification_reports_instead_of_crashing(monkeypatch):
    _with_url_schemes(monkeypatch)
    native = Recorder()
    phone = credentials_module.PhoneAuthProvider.__new__(
        credentials_module.PhoneAuthProvider
    )
    phone._native, phone._auth_native = native, _auth_native()
    out = []
    phone.verify_phone_number("+15555550100", lambda vid, e: out.append((vid, e)))
    assert out[0][0] is None and APP_SCHEME in out[0][1].description
    assert native.calls == []  # never reached the SDK's fatalError


@pytest.mark.parametrize("provider_id", ["facebook.com", "apple.com"])
def test_oauth_provider_refuses_providers_that_need_their_own_sdk(
    monkeypatch, provider_id
):
    monkeypatch.setattr(Auth, "_instance", Auth(_auth_native()))
    monkeypatch.setattr(Auth, "_emulated", set())
    with pytest.raises(ValueError, match="needs"):
        OAuthProvider(provider_id)


def test_oauth_provider_allows_them_on_the_emulator(monkeypatch):
    fake = Recorder()
    monkeypatch.setattr(credentials_module, "objc_class", lambda name: fake)
    monkeypatch.setattr(Auth, "_instance", Auth(_auth_native()))
    monkeypatch.setattr(Auth, "_emulated", {4242})
    OAuthProvider("facebook.com")
    assert fake.calls[-1] == ("providerWithProviderID_", ("facebook.com",))


# ---- multi-factor -------------------------------------------------------------------

import pyios_firebase.auth.facebook as facebook_module
import pyios_firebase.auth.multi_factor as mfa_module
from pyios_firebase.auth import (
    MultiFactor,
    MultiFactorResolver,
    PhoneMultiFactorInfo,
    TOTPMultiFactorGenerator,
)


def _factor(factor_id, **extra):
    return SimpleNamespace(
        UID="f1", factorID=factor_id, displayName="Work", enrollmentDate=None, **extra
    )


def test_multi_factor_lists_and_wraps_factors(blocks):
    native = Recorder()
    native.enrolledFactors = [_factor("phone", phoneNumber="+1555"), _factor("totp")]
    mfa = MultiFactor(native)
    phone, totp = mfa.enrolled_factors
    assert isinstance(phone, PhoneMultiFactorInfo) and phone.phone_number == "+1555"
    assert type(totp).__name__ == "MultiFactorInfo" and totp.factor_id == "totp"
    assert phone.uid == "f1" and phone.display_name == "Work"


def test_multi_factor_calls(blocks):
    native = Recorder()
    mfa = MultiFactor(native)
    mfa.get_session(lambda s, e: None)
    mfa.enroll(SimpleNamespace(native="assertion"), "Phone")
    mfa.unenroll("uid-1")
    mfa.unenroll(mfa_module.MultiFactorInfo(_factor("phone")))
    assert [c[0] for c in native.calls] == [
        "getSessionWithCompletion_",
        "enrollWithAssertion_displayName_completion_",
        "unenrollWithFactorUID_completion_",
        "unenrollWithInfo_completion_",
    ]


def test_second_factor_required_error_has_a_resolver():
    resolver = NSObject.new()
    error = auth_error_from_nserror(
        auth_error(
            AuthErrorCode.SECOND_FACTOR_REQUIRED,
            FIRAuthErrorUserInfoMultiFactorResolverKey=resolver,
        )
    )
    assert error.name == "SECOND_FACTOR_REQUIRED"
    assert (
        isinstance(error.resolver, MultiFactorResolver)
        and error.resolver._native == resolver
    )
    assert (
        auth_error_from_nserror(auth_error(AuthErrorCode.WRONG_PASSWORD)).resolver
        is None
    )


def test_resolver_hints_and_resolve(blocks):
    native = Recorder()
    native.hints = [_factor("phone", phoneNumber="+*******0100")]
    native.session = "session"
    resolver = MultiFactorResolver(native)
    assert resolver.hints[0].phone_number == "+*******0100"
    assert resolver.session.native == "session"
    resolver.resolve_sign_in(SimpleNamespace(native="assertion"), lambda r, e: None)
    assert native.calls[-1][0] == "resolveSignInWithAssertion_completion_"


def test_totp_generator_selectors(monkeypatch, blocks):
    fake = Recorder()
    monkeypatch.setattr(mfa_module, "objc_class", lambda name: fake)
    TOTPMultiFactorGenerator.generate_secret(
        SimpleNamespace(native="s"), lambda secret, e: None
    )
    TOTPMultiFactorGenerator.assertion_for_enrollment(
        SimpleNamespace(native="secret"), "123456"
    )
    TOTPMultiFactorGenerator.assertion_for_sign_in("enrollment-1", "123456")
    assert [c[0] for c in fake.calls] == [
        "generateSecretWithMultiFactorSession_completion_",
        "assertionForEnrollmentWithSecret_oneTimePassword_",
        "assertionForSignInWithEnrollmentID_oneTimePassword_",
    ]


def test_phone_verification_for_enrollment_and_sign_in(monkeypatch):
    _with_url_schemes(monkeypatch, APP_SCHEME)
    native = Recorder()
    phone = credentials_module.PhoneAuthProvider.__new__(
        credentials_module.PhoneAuthProvider
    )
    phone._native, phone._auth_native = native, _auth_native()
    phone.verify_phone_number("+1555", lambda v, e: None)
    phone.verify_phone_number(
        "+1555", lambda v, e: None, multi_factor_session=SimpleNamespace(native="s")
    )
    phone.verify_phone_number_for_sign_in(
        SimpleNamespace(native="hint"), SimpleNamespace(native="s"), lambda v, e: None
    )
    names_and_sessions = [(c[0], c[1][2]) for c in native.calls]
    assert names_and_sessions == [
        ("verifyPhoneNumber_UIDelegate_multiFactorSession_completion_", None),
        ("verifyPhoneNumber_UIDelegate_multiFactorSession_completion_", "s"),
        (
            "verifyPhoneNumberWithMultiFactorInfo_UIDelegate_multiFactorSession_completion_",
            "s",
        ),
    ]


# ---- shared keychain ------------------------------------------------------------------


def test_get_stored_user(monkeypatch):
    monkeypatch.setattr(user_module, "objc_class", lambda name: Recorder())
    stored = SimpleNamespace(uid="u1", email=None)
    native = SimpleNamespace(
        getStoredUserForAccessGroup_error_=lambda group, error: stored
    )
    user, error = Auth(native).get_stored_user("TEAM.group")
    assert error is None and user is not None and user.uid == "u1"
    native.getStoredUserForAccessGroup_error_ = lambda group, error: None
    assert Auth(native).get_stored_user(None) == (None, None)


# ---- Facebook ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            SimpleNamespace(isCancelled=True, token=None, authenticationToken=None),
            "cancelled",
        ),
        (
            SimpleNamespace(
                isCancelled=False,
                token=SimpleNamespace(tokenString="access"),
                authenticationToken=None,
            ),
            "classic",
        ),
        (
            SimpleNamespace(
                isCancelled=False,
                token=None,
                authenticationToken=SimpleNamespace(tokenString="oidc"),
            ),
            "limited",
        ),
        (
            SimpleNamespace(isCancelled=False, token=None, authenticationToken=None),
            "no token",
        ),
    ],
)
def test_facebook_result_to_credential(monkeypatch, result, expected):
    made = []
    monkeypatch.setattr(
        credentials_module.FacebookAuthProvider,
        "credential",
        staticmethod(lambda token: made.append(("classic", token)) or "C"),
    )
    monkeypatch.setattr(
        credentials_module.OAuthProvider,
        "credential",
        staticmethod(
            lambda pid, id_token=None, access_token=None, raw_nonce=None: (
                made.append(("limited", pid, id_token, raw_nonce)) or "L"
            )
        ),
    )
    outcome = facebook_module._credential_from_result(result, "raw-nonce")
    if expected == "cancelled":
        assert outcome.cancelled is True and made == []
    elif expected == "classic":
        assert outcome == "C" and made == [("classic", "access")]
    elif expected == "limited":
        assert outcome == "L" and made == [
            ("limited", "facebook.com", "oidc", "raw-nonce")
        ]
    else:
        assert "no token" in outcome.description


# ---- ActionCodeURL (parsed in Python: the SDK loses continue URL state) ----------------

from pyios_firebase.auth import ActionCodeOperation, ActionCodeURL

EMULATOR_LINK = (
    "http://127.0.0.1:9099/emulator/action?mode=signIn&lang=en&oobCode=CODE&apiKey=fake-api-key"
    "&continueUrl=https%3A%2F%2Fpyios-e2e.example.com%2Ffinish%3Fcart%3D42%26run%3Dabc"
)


def test_action_code_url_keeps_continue_url_state():
    info = ActionCodeURL.from_link(EMULATOR_LINK)
    assert info == ActionCodeURL(
        operation=ActionCodeOperation.EMAIL_LINK,
        code="CODE",
        continue_url="https://pyios-e2e.example.com/finish?cart=42&run=abc",
        api_key="fake-api-key",
        language_code="en",
    )


def test_action_code_url_unwraps_nested_links_and_rejects_others():
    import urllib.parse

    wrapped = "https://example.page.link/?link=" + urllib.parse.quote(
        EMULATOR_LINK, safe=""
    )
    assert ActionCodeURL.from_link(wrapped).code == "CODE"
    assert ActionCodeURL.from_link("https://example.com/other?x=1") is None
    assert (
        ActionCodeURL.from_link("https://x/a?mode=resetPassword&oobCode=c").operation
        == ActionCodeOperation.PASSWORD_RESET
    )

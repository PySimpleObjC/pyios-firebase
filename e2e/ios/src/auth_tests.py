"""End-to-end Auth tests: the real Firebase iOS SDK against the Auth emulator.

The emulator does not send email or SMS: the codes it would have sent are
read from its REST API (``/emulator/v1/projects/{id}/oobCodes`` and
``/verificationCodes``). Every test ends signed out.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from pyios_firebase.auth import (
    ActionCodeOperation,
    ActionCodeSettings,
    Auth,
    AuthErrorCode,
    EmailAuthProvider,
    GoogleAuthProvider,
    PhoneAuthProvider,
)
from runner import TestContext, expect, expect_equal

from firestore_tests import RUN_ID

PROJECT_ID = "demo-pyios-firebase"
AUTH_EMULATOR = "http://127.0.0.1:9099"
BUNDLE_ID = "io.github.pysimpleobjc.pyiosfirebase.e2e"
PASSWORD = "first-password-1"


def auth() -> Auth:
    return Auth.auth()


def email(name: str) -> str:
    return f"{name}.{RUN_ID}@example.com"


def _emulator_get(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{AUTH_EMULATOR}/emulator/v1/projects/{PROJECT_ID}/{path}", timeout=5) as r:
        return json.loads(r.read())


def oob_code(address: str, request_type: str) -> dict[str, Any]:
    """The newest email action the emulator 'sent' to ``address``."""
    codes = [c for c in _emulator_get("oobCodes")["oobCodes"]
             if c["email"] == address and c["requestType"] == request_type]
    expect(codes, f"no {request_type} email for {address}")
    return codes[-1]


def sms_code(phone: str) -> str:
    codes = [c for c in _emulator_get("verificationCodes")["verificationCodes"] if c["phoneNumber"] == phone]
    expect(codes, f"no SMS code for {phone}")
    return str(codes[-1]["code"])


def unsigned_jwt(payload: dict[str, Any]) -> str:
    """A JWT with no signature: the emulator accepts these as custom tokens
    and as identity-provider ID tokens."""

    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(payload)}."


def signed_out_first(t: TestContext, then) -> None:
    error = auth().sign_out()
    expect(error is None, error)
    expect(auth().current_user is None, "signed out")
    then()


def finish_signed_out(t: TestContext) -> None:
    expect(auth().sign_out() is None, "sign out at the end")
    t.passed()


# ---- email and password -----------------------------------------------------------


def test_auth_create_sign_out_sign_in(t: TestContext) -> None:
    address = email("ada")
    state: dict[str, Any] = {}

    def signed_in_again(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.uid, state["uid"], "same user")
        expect(result.additional_user_info is not None and not result.additional_user_info.is_new_user, "not new")
        finish_signed_out(t)

    def created(result, error) -> None:
        expect(error is None, error)
        user = result.user
        expect_equal(user.email, address, "email")
        expect(result.additional_user_info.is_new_user, "is_new_user on sign-up")
        expect_equal(result.additional_user_info.provider_id, "password", "provider")
        expect(not user.is_anonymous and not user.is_email_verified, "flags")
        expect_equal(auth().current_user.uid, user.uid, "current_user")
        expect(abs(user.metadata.creation_date - datetime.now(UTC)) < timedelta(minutes=5), "creation date")
        state["uid"] = user.uid
        expect(auth().sign_out() is None, "sign out")
        expect(auth().current_user is None, "current_user after sign out")
        auth().sign_in_with_email_password(address, PASSWORD, t.step(signed_in_again))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_errors_have_codes(t: TestContext) -> None:
    address = email("taken")
    cases = [
        ("existing email", lambda cb: auth().create_user_with_email_password(address, PASSWORD, cb),
         {AuthErrorCode.EMAIL_ALREADY_IN_USE}),
        ("wrong password", lambda cb: auth().sign_in_with_email_password(address, "not-it-999", cb),
         {AuthErrorCode.WRONG_PASSWORD, AuthErrorCode.INVALID_CREDENTIAL}),
        ("weak password", lambda cb: auth().create_user_with_email_password(email("weak"), "123", cb),
         {AuthErrorCode.WEAK_PASSWORD}),
        ("invalid email", lambda cb: auth().create_user_with_email_password("not-an-email", PASSWORD, cb),
         {AuthErrorCode.INVALID_EMAIL}),
    ]

    def next_case() -> None:
        if not cases:
            finish_signed_out(t)
            return
        what, call, codes = cases.pop(0)

        def answered(result, error) -> None:
            expect(result is None, f"{what}: no result on error")
            expect(error is not None, f"{what}: should fail")
            expect(error.code in codes, f"{what}: code {error.code} ({error.name}) not in {codes}")
            expect(error.name and error.domain == "FIRAuthErrorDomain", f"{what}: {error}")
            expect(error.cancelled is False, f"{what}: not cancelled")
            next_case()

        call(t.step(answered))

    def created(result, error) -> None:
        expect(error is None, error)
        auth().sign_out()
        next_case()

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


# ---- listeners --------------------------------------------------------------------


def test_auth_state_listener(t: TestContext) -> None:
    seen: list[str | None] = []
    holder: dict[str, Any] = {}

    def on_change(user) -> None:
        seen.append(None if user is None else ("anonymous" if user.is_anonymous else user.uid))
        if seen == [None]:
            auth().sign_in_anonymously()
        elif len(seen) == 2:
            expect_equal(seen[1], "anonymous", "signed in anonymously")
            expect(auth().sign_out() is None, "sign out")
        elif len(seen) == 3:
            expect_equal(seen[2], None, "signed out")
            holder["listener"].remove()
            holder["listener"].remove()  # safe twice
            auth().sign_in_anonymously(t.step(after_removed))

    def after_removed(result, error) -> None:
        expect(error is None, error)
        expect_equal(len(seen), 3, f"no calls after remove(): {seen}")
        finish_signed_out(t)

    signed_out_first(t, lambda: holder.update(listener=auth().add_state_did_change_listener(t.step(on_change))))


def test_auth_id_token_listener(t: TestContext) -> None:
    from kivy.clock import Clock

    calls: list[bool] = []
    holder: dict[str, Any] = {}

    def on_token(user) -> None:
        calls.append(user is not None)
        if calls == [False]:
            auth().sign_in_anonymously(t.step(signed_in))

    def signed_in(result, error) -> None:
        expect(error is None, error)
        result.user.get_id_token(t.step(first_token))

    def first_token(token, error) -> None:
        expect(error is None, error)
        holder["token"] = token
        # tokens carry their issue time in seconds: refresh in a later second,
        # or the "new" token is identical and listeners are (rightly) not told
        Clock.schedule_once(t.step(lambda dt: auth().current_user.get_id_token(
            t.step(refreshed), force_refresh=True)), 1.5)

    def refreshed(token, error) -> None:
        expect(error is None, error)
        expect(token != holder["token"], "a forced refresh gives a new token")
        Clock.schedule_once(t.step(check_listener), 1)

    def check_listener(_dt) -> None:
        expect(calls[:2] == [False, True], f"signed out, then signed in: {calls}")
        expect(len(calls) >= 3, f"fires on a token refresh: {calls}")
        holder["listener"].remove()
        finish_signed_out(t)

    signed_out_first(t, lambda: holder.update(listener=auth().add_id_token_did_change_listener(t.step(on_token))))


# ---- anonymous, linking, providers ----------------------------------------------------


def test_auth_anonymous_upgrade_by_linking(t: TestContext) -> None:
    address = email("upgraded")
    state: dict[str, Any] = {}

    def linked(result, error) -> None:
        expect(error is None, error)
        user = result.user
        expect_equal(user.uid, state["uid"], "same uid after linking")
        expect(not user.is_anonymous, "no longer anonymous")
        expect_equal(user.email, address, "email")
        expect_equal([p.provider_id for p in user.provider_data], ["password"], "provider data")
        finish_signed_out(t)

    def anonymous(result, error) -> None:
        expect(error is None, error)
        expect(result.user.is_anonymous, "anonymous")
        expect_equal(result.user.provider_data, [], "no providers yet")
        state["uid"] = result.user.uid
        result.user.link_with_credential(EmailAuthProvider.credential(address, PASSWORD), t.step(linked))

    signed_out_first(t, lambda: auth().sign_in_anonymously(t.step(anonymous)))


def test_auth_identity_provider_link_and_unlink(t: TestContext) -> None:
    address = email("google")
    now = int(time.time())
    google_token = unsigned_jwt({
        "iss": "https://accounts.google.com", "aud": "e2e", "iat": now, "exp": now + 3600,
        "sub": f"google-{RUN_ID}", "email": address, "email_verified": True, "name": "Grace Hopper",
    })
    credential = GoogleAuthProvider.credential(google_token, "fake-access-token")
    expect_equal(credential.provider, "google.com", "credential provider")

    def unlinked(user, error) -> None:
        expect(error is None, error)
        expect_equal([p.provider_id for p in user.provider_data], ["password"], "after unlink")
        user.unlink("google.com", t.step(unlink_again))

    def unlink_again(user, error) -> None:
        expect(error is not None and error.code == AuthErrorCode.NO_SUCH_PROVIDER, f"unlink twice: {error}")
        finish_signed_out(t)

    def linked(result, error) -> None:
        expect(error is None, error)
        providers = sorted(p.provider_id for p in result.user.provider_data)
        expect_equal(providers, ["google.com", "password"], "linked providers")
        google = next(p for p in result.user.provider_data if p.provider_id == "google.com")
        expect_equal(google.email, address, "provider email")
        result.user.unlink("google.com", t.step(unlinked))

    def created(result, error) -> None:
        expect(error is None, error)
        result.user.link_with_credential(credential, t.step(linked))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_custom_token_and_claims(t: TestContext) -> None:
    uid = f"custom-{RUN_ID}"
    now = int(time.time())
    token = unsigned_jwt({
        "aud": "https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit",
        "iss": "e2e@example.com", "sub": "e2e@example.com", "iat": now, "exp": now + 3600,
        "uid": uid, "claims": {"role": "admin", "level": 3},
    })

    def got_token(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.claims.get("role"), "admin", "custom claim")
        expect_equal(result.claims.get("level"), 3, "custom claim (number)")
        expect_equal(result.sign_in_provider, "custom", "sign-in provider")
        expect(result.expiration_date > datetime.now(UTC), "expires in the future")
        expect(result.issued_at_date <= result.expiration_date, "issued before it expires")
        finish_signed_out(t)

    def signed_in(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.uid, uid, "uid from the custom token")
        result.user.get_id_token_result(t.step(got_token))

    signed_out_first(t, lambda: auth().sign_in_with_custom_token(token, t.step(signed_in)))


def test_auth_phone_number_sign_in(t: TestContext) -> None:
    phone_number = "+1555" + str(int(RUN_ID[:6], 16) % 10_000_000).zfill(7)
    phone = PhoneAuthProvider()

    def signed_in(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.phone_number, phone_number, "phone number")
        expect_equal([p.provider_id for p in result.user.provider_data], ["phone"], "provider")
        finish_signed_out(t)

    def code_sent(verification_id, error) -> None:
        expect(error is None, error)
        credential = phone.credential(verification_id, sms_code(phone_number))
        auth().sign_in_with_credential(credential, t.step(signed_in))

    signed_out_first(t, lambda: phone.verify_phone_number(phone_number, t.step(code_sent)))


# ---- profile, tokens, account changes ----------------------------------------------


def test_auth_profile_and_id_token(t: TestContext) -> None:
    address = email("profile")

    def reloaded(error) -> None:
        expect(error is None, error)
        user = auth().current_user
        expect_equal(user.display_name, "Ada Lovelace", "display name")
        expect_equal(user.photo_url, "https://example.com/ada.png", "photo url")
        user.update_profile(t.step(cleared), photo_url=None)

    def cleared(error) -> None:
        expect(error is None, error)
        user = auth().current_user
        expect(user.photo_url is None, "photo url removed")
        expect_equal(user.display_name, "Ada Lovelace", "display name kept (UNSET)")
        # the cached token was issued before the profile change: refresh it
        user.get_id_token(t.step(got_token), force_refresh=True)

    def got_token(token, error) -> None:
        expect(error is None, error)
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        expect_equal(payload["email"], address, "token email")
        expect_equal(payload["name"], "Ada Lovelace", "token name")
        finish_signed_out(t)

    def created(result, error) -> None:
        expect(error is None, error)
        result.user.update_profile(
            t.step(lambda e: (expect(e is None, e), auth().current_user.reload(t.step(reloaded)))),
            display_name="Ada Lovelace",
            photo_url="https://example.com/ada.png",
        )

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_reauthenticate_change_password_delete(t: TestContext) -> None:
    address = email("delete")
    new_password = "second-password-2"

    def after_delete_sign_in(result, error) -> None:
        expect(error is not None, "a deleted user cannot sign in")
        expect(error.code in {AuthErrorCode.USER_NOT_FOUND, AuthErrorCode.INVALID_CREDENTIAL}, error.name)
        finish_signed_out(t)

    def deleted(error) -> None:
        expect(error is None, error)
        expect(auth().current_user is None, "signed out by delete()")
        auth().sign_in_with_email_password(address, new_password, t.step(after_delete_sign_in))

    def signed_in_new(result, error) -> None:
        expect(error is None, error)
        result.user.delete(t.step(deleted))

    def password_changed(error) -> None:
        expect(error is None, error)
        auth().sign_out()
        auth().sign_in_with_email_password(address, new_password, t.step(signed_in_new))

    def reauthenticated(result, error) -> None:
        expect(error is None, error)
        result.user.update_password(new_password, t.step(password_changed))

    def mismatch(result, error) -> None:
        expect(error is not None, "re-authenticating as someone else must fail")
        expect(error.code in {AuthErrorCode.USER_MISMATCH, AuthErrorCode.INVALID_CREDENTIAL, AuthErrorCode.USER_NOT_FOUND}, error.name)
        auth().current_user.reauthenticate_with_credential(
            EmailAuthProvider.credential(address, PASSWORD), t.step(reauthenticated))

    def created(result, error) -> None:
        expect(error is None, error)
        result.user.reauthenticate_with_credential(
            EmailAuthProvider.credential(email("nobody"), PASSWORD), t.step(mismatch))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


# ---- email actions ------------------------------------------------------------------


def test_auth_password_reset_flow(t: TestContext) -> None:
    address = email("reset")
    new_password = "reset-password-3"
    state: dict[str, Any] = {}

    def signed_in(result, error) -> None:
        expect(error is None, f"sign in with the new password: {error}")
        finish_signed_out(t)

    def reset_done(error) -> None:
        expect(error is None, error)
        auth().sign_in_with_email_password(address, new_password, t.step(signed_in))

    def code_checked(info, error) -> None:
        expect(error is None, error)
        # SDK 13.1.1 maps "resetPassword"; the emulator sends "PASSWORD_RESET",
        # so the SDK says UNKNOWN (documented on ActionCodeInfo.operation)
        expect(info.operation in (ActionCodeOperation.PASSWORD_RESET, ActionCodeOperation.UNKNOWN), info)
        expect_equal(info.email, address, "email")
        auth().confirm_password_reset(state["code"], new_password, t.step(reset_done))

    def code_verified(found_email, error) -> None:
        expect(error is None, error)
        expect_equal(found_email, address, "verify_password_reset_code email")
        auth().check_action_code(state["code"], t.step(code_checked))

    def sent(error) -> None:
        expect(error is None, error)
        state["code"] = oob_code(address, "PASSWORD_RESET")["oobCode"]
        auth().verify_password_reset_code(state["code"], t.step(code_verified))

    def created(result, error) -> None:
        expect(error is None, error)
        auth().sign_out()
        auth().send_password_reset(address, t.step(sent))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_email_verification(t: TestContext) -> None:
    address = email("verify")

    def reloaded(error) -> None:
        expect(error is None, error)
        expect(auth().current_user.is_email_verified, "verified after apply_action_code + reload")
        finish_signed_out(t)

    def applied(error) -> None:
        expect(error is None, error)
        auth().current_user.reload(t.step(reloaded))

    def sent(error) -> None:
        expect(error is None, error)
        auth().apply_action_code(oob_code(address, "VERIFY_EMAIL")["oobCode"], t.step(applied))

    def created(result, error) -> None:
        expect(error is None, error)
        expect(not result.user.is_email_verified, "not verified yet")
        result.user.send_email_verification(t.step(sent))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_email_link_sign_in(t: TestContext) -> None:
    address = email("link")
    settings = ActionCodeSettings(
        url="https://pyios-e2e.example.com/finish", handle_code_in_app=True, ios_bundle_id=BUNDLE_ID
    )

    def signed_in(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.email, address, "email")
        expect(result.additional_user_info.is_new_user, "the link created the account")
        finish_signed_out(t)

    def sent(error) -> None:
        expect(error is None, error)
        link = oob_code(address, "EMAIL_SIGNIN")["oobLink"]
        expect(auth().is_sign_in_with_email_link(link), f"a sign-in link: {link}")
        expect(not auth().is_sign_in_with_email_link("https://example.com/other"), "not a sign-in link")
        auth().sign_in_with_email_link(address, link, t.step(signed_in))

    signed_out_first(t, lambda: auth().send_sign_in_link(address, settings, t.step(sent)))


def test_auth_settings(t: TestContext) -> None:
    a = auth()
    a.language_code = "fr"
    expect_equal(a.language_code, "fr", "language code")
    a.use_app_language()
    expect(a.language_code is None or isinstance(a.language_code, str), "app language")
    expect(a.app_verification_disabled_for_testing, "use_emulator turns app verification off")
    expect(a.tenant_id is None, "no tenant")
    t.passed()


# ---- multi-factor ---------------------------------------------------------------------


def totp(secret: str, at: float | None = None) -> str:
    """RFC 6238 TOTP (HMAC-SHA1, 30 s, 6 digits), as an authenticator app computes it."""
    import hashlib
    import hmac
    import struct

    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verified_user(t: TestContext, address: str, then) -> None:
    """A new email/password user with a verified email (needed to enroll a factor)."""

    def reloaded(error) -> None:
        expect(error is None, error)
        expect(auth().current_user.is_email_verified, "verified")
        then(auth().current_user)

    def sent(error) -> None:
        expect(error is None, error)
        auth().apply_action_code(oob_code(address, "VERIFY_EMAIL")["oobCode"],
                                 t.step(lambda e: (expect(e is None, e), auth().current_user.reload(t.step(reloaded)))))

    def created(result, error) -> None:
        expect(error is None, error)
        result.user.send_email_verification(t.step(sent))

    signed_out_first(t, lambda: auth().create_user_with_email_password(address, PASSWORD, t.step(created)))


def test_auth_sms_multi_factor(t: TestContext) -> None:
    from pyios_firebase.auth import PhoneMultiFactorGenerator, PhoneMultiFactorInfo

    address = email("mfa-sms")
    phone_number = "+1666" + str(int(RUN_ID[:6], 16) % 10_000_000).zfill(7)
    phone = PhoneAuthProvider()
    state: dict[str, Any] = {}

    def signed_in_without_mfa(result, error) -> None:
        expect(error is None, f"no second factor needed after unenroll: {error}")
        finish_signed_out(t)

    def unenrolled(error) -> None:
        expect(error is None, error)
        auth().sign_out()
        auth().sign_in_with_email_password(address, PASSWORD, t.step(signed_in_without_mfa))

    def resolved(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.uid, state["uid"], "signed in with the second factor")
        factors = result.user.multi_factor.enrolled_factors
        result.user.multi_factor.unenroll(factors[0], t.step(unenrolled))

    def sign_in_code_sent(verification_id, error) -> None:
        expect(error is None, error)
        assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, sms_code(phone_number)))
        expect_equal(assertion.factor_id, "phone", "assertion factor")
        state["resolver"].resolve_sign_in(assertion, t.step(resolved))

    def needs_second_factor(result, error) -> None:
        expect(result is None and error is not None, "sign-in must stop at the second factor")
        expect_equal(error.code, AuthErrorCode.SECOND_FACTOR_REQUIRED, "error code")
        resolver = error.resolver
        expect(resolver is not None, "error.resolver")
        hint = resolver.hints[0]
        expect(isinstance(hint, PhoneMultiFactorInfo), f"phone hint: {hint!r}")
        expect_equal(hint.display_name, "Test phone", "hint display name")
        state["resolver"] = resolver
        phone.verify_phone_number_for_sign_in(hint, resolver.session, t.step(sign_in_code_sent))

    def enrolled(error) -> None:
        expect(error is None, error)
        factors = auth().current_user.multi_factor.enrolled_factors
        expect_equal(len(factors), 1, "one factor")
        expect(isinstance(factors[0], PhoneMultiFactorInfo), repr(factors[0]))
        expect_equal(factors[0].factor_id, "phone", "factor id")
        expect(factors[0].enrollment_date is not None, "enrollment date")
        auth().sign_out()
        auth().sign_in_with_email_password(address, PASSWORD, t.step(needs_second_factor))

    def enrollment_code_sent(verification_id, error) -> None:
        expect(error is None, error)
        assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, sms_code(phone_number)))
        auth().current_user.multi_factor.enroll(assertion, "Test phone", t.step(enrolled))

    def got_session(session, error) -> None:
        expect(error is None, error)
        phone.verify_phone_number(phone_number, t.step(enrollment_code_sent), multi_factor_session=session)

    def ready(user) -> None:
        state["uid"] = user.uid
        expect_equal(user.multi_factor.enrolled_factors, [], "no factors yet")
        user.multi_factor.get_session(t.step(got_session))

    verified_user(t, address, ready)


def test_auth_totp_multi_factor(t: TestContext) -> None:
    from pyios_firebase.auth import TOTPMultiFactorGenerator

    address = email("mfa-totp")
    state: dict[str, Any] = {}

    def resolved(result, error) -> None:
        expect(error is None, error)
        expect_equal(result.user.uid, state["uid"], "signed in with TOTP")
        finish_signed_out(t)

    def needs_second_factor(result, error) -> None:
        expect(error is not None and error.code == AuthErrorCode.SECOND_FACTOR_REQUIRED, f"second factor: {error}")
        hint = error.resolver.hints[0]
        expect_equal(hint.factor_id, "totp", "TOTP hint")
        assertion = TOTPMultiFactorGenerator.assertion_for_sign_in(hint.uid, totp(state["secret"]))
        error.resolver.resolve_sign_in(assertion, t.step(resolved))

    def enrolled(error) -> None:
        expect(error is None, error)
        expect_equal([f.factor_id for f in auth().current_user.multi_factor.enrolled_factors], ["totp"], "factors")
        auth().sign_out()
        auth().sign_in_with_email_password(address, PASSWORD, t.step(needs_second_factor))

    def got_secret(secret, error) -> None:
        if error is not None and auth().is_using_emulator and "phoneEnrollmentInfo" in str(error.underlying_error):
            # the Auth emulator only supports SMS second factors
            t.skipped("the Auth emulator does not support TOTP (it asks for phoneEnrollmentInfo)")
            auth().sign_out()
            return
        expect(error is None, f"generate_secret: {error}")
        key = secret.shared_secret_key()
        url = secret.generate_qr_code_url(address, "pyios e2e")
        expect(url.startswith("otpauth://totp/") and f"secret={key}" in url, url)
        state["secret"] = key
        assertion = TOTPMultiFactorGenerator.assertion_for_enrollment(secret, totp(key))
        auth().current_user.multi_factor.enroll(assertion, "Authenticator", t.step(enrolled))

    def got_session(session, error) -> None:
        expect(error is None, error)
        TOTPMultiFactorGenerator.generate_secret(session, t.step(got_secret))

    def ready(user) -> None:
        state["uid"] = user.uid
        user.multi_factor.get_session(t.step(got_session))

    verified_user(t, address, ready)


# ---- email action state, keychain, providers ----------------------------------------


def test_auth_action_code_url_keeps_state(t: TestContext) -> None:
    from pyios_firebase.auth import ActionCodeURL

    address = email("state")
    settings = ActionCodeSettings(
        url=f"https://pyios-e2e.example.com/finish?cart=42&run={RUN_ID}",
        handle_code_in_app=True,
        ios_bundle_id=BUNDLE_ID,
    )

    def sent(error) -> None:
        expect(error is None, error)
        sent_email = oob_code(address, "EMAIL_SIGNIN")
        info = ActionCodeURL.from_link(sent_email["oobLink"])
        expect(info is not None, "an action link")
        expect_equal(info.code, sent_email["oobCode"], "code")
        expect_equal(info.continue_url, settings.url, "the continue URL, with all its state")
        expect(ActionCodeURL.from_link("https://example.com/not-an-action") is None, "not an action link")
        finish_signed_out(t)

    signed_out_first(t, lambda: auth().send_sign_in_link(address, settings, t.step(sent)))


def test_auth_get_stored_user(t: TestContext) -> None:
    def signed_in(result, error) -> None:
        expect(error is None, error)
        user, stored_error = auth().get_stored_user(None)
        expect(stored_error is None, stored_error)
        expect(user is not None and user.uid == result.user.uid, f"the app's stored user: {user}")
        finish_signed_out(t)

    signed_out_first(t, lambda: auth().sign_in_anonymously(t.step(signed_in)))


def test_auth_oauth_providers(t: TestContext) -> None:
    from pyios_firebase.auth import OAuthProvider

    microsoft = OAuthProvider("microsoft.com", scopes=["mail.read", "calendars.read"],
                              custom_parameters={"tenant": "contoso.onmicrosoft.com", "prompt": "consent"})
    expect_equal(microsoft.provider_id, "microsoft.com", "provider id")
    expect_equal(microsoft.scopes, ["mail.read", "calendars.read"], "scopes")
    expect_equal(microsoft.custom_parameters, {"tenant": "contoso.onmicrosoft.com", "prompt": "consent"}, "params")
    for provider_id in ("yahoo.com", "github.com", "twitter.com", "oidc.e2e-provider", "saml.e2e-provider"):
        expect_equal(OAuthProvider(provider_id).provider_id, provider_id, provider_id)
    # the SDK refuses these outside the emulator (we raise instead); on it, they work
    expect_equal(OAuthProvider("facebook.com").provider_id, "facebook.com", "facebook on the emulator")
    credential = OAuthProvider.credential("oidc.e2e-provider", id_token="id", raw_nonce="n")
    expect_equal(credential.provider, "oidc.e2e-provider", "OIDC credential")
    t.passed()


def test_auth_facebook_sdk_bridge(t: TestContext) -> None:
    """The Facebook SDK classes and selectors facebook.py uses exist at runtime.
    (Logging in needs a real Facebook app; this checks the bridge.)"""
    from rubicon.objc.runtime import SEL

    from pyios_firebase.auth.facebook import FACEBOOK_LOGIN_TRACKING_LIMITED
    from pyios_firebase.util import objc_class

    manager = objc_class("FBSDKLoginManager")
    for selector in ("logInFromViewController:configuration:completion:", "logOut"):
        expect(manager.instancesRespondToSelector_(SEL(selector)), f"FBSDKLoginManager {selector}")
    expect(objc_class("FBSDKApplicationDelegate").respondsToSelector_(SEL("sharedInstance")), "sharedInstance")
    configuration = objc_class("FBSDKLoginConfiguration").alloc().initWithPermissions_tracking_nonce_(
        ["public_profile", "email"], FACEBOOK_LOGIN_TRACKING_LIMITED, "a" * 64)
    expect(configuration is not None, "LoginConfiguration with a nonce")
    expect_equal(int(configuration.tracking), FACEBOOK_LOGIN_TRACKING_LIMITED, "tracking")
    t.passed()


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

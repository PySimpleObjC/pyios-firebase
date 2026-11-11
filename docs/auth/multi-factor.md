# Multi-factor authentication

Add a second step to sign-in: a code by **SMS**, or from an **authenticator
app** (TOTP: Google Authenticator, 1Password, Authy...).

**Needs:** Firebase Authentication with **Identity Platform** (an upgrade in
the console), the factors enabled under **Authentication > Sign-in method >
Multi-factor authentication**, and a **verified email** on the user's account.

```python
from pyios_firebase.auth import (
    AuthErrorCode,
    PhoneAuthProvider,
    PhoneMultiFactorGenerator,
    TOTPMultiFactorGenerator,
)
```

## Enroll an SMS factor

```python
user = auth.current_user
phone = PhoneAuthProvider()


def on_session(session, error):
    phone.verify_phone_number("+15555550100", on_code_sent, multi_factor_session=session)


def on_code_sent(verification_id, error):
    code = ask_user_for_code()
    assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, code))
    user.multi_factor.enroll(assertion, "My phone", on_enrolled)


user.multi_factor.get_session(on_session)
```

## Enroll an authenticator app (TOTP)

```python
def on_session(session, error):
    TOTPMultiFactorGenerator.generate_secret(session, on_secret)


def on_secret(secret, error):
    url = secret.generate_qr_code_url(user.email, "My App")
    show_qr_code(url)                      # or secret.open_in_otp_app(url) on the same device
    code = ask_user_for_code()             # the 6 digits the app shows
    assertion = TOTPMultiFactorGenerator.assertion_for_enrollment(secret, code)
    user.multi_factor.enroll(assertion, "Authenticator", on_enrolled)


user.multi_factor.get_session(on_session)
```

## Sign in with a second factor

After the first factor (a password, a provider...), the sign-in fails with
`SECOND_FACTOR_REQUIRED`, and the error carries a **resolver**:

```python
def on_signed_in(result, error):
    if error is None:
        return show_home()
    if error.code != AuthErrorCode.SECOND_FACTOR_REQUIRED:
        return show(error.description)

    resolver = error.resolver
    hint = choose_factor(resolver.hints)          # the user's factors: factor_id, display_name...

    if hint.factor_id == "phone":
        def on_code_sent(verification_id, error):
            code = ask_user_for_code()
            assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, code))
            resolver.resolve_sign_in(assertion, on_signed_in)

        phone.verify_phone_number_for_sign_in(hint, resolver.session, on_code_sent)
    else:                                         # "totp"
        code = ask_user_for_code()
        assertion = TOTPMultiFactorGenerator.assertion_for_sign_in(hint.uid, code)
        resolver.resolve_sign_in(assertion, on_signed_in)


auth.sign_in_with_email_password(email, password, on_signed_in)
```

A phone hint's `phone_number` is masked (`+*******0100`), to show the user
which phone gets the code.

## Manage the factors

```python
for factor in user.multi_factor.enrolled_factors:
    print(factor.factor_id, factor.display_name, factor.enrollment_date)

user.multi_factor.unenroll(factor, on_removed)
```

Enrolling and removing factors may need a
[recent sign-in](users.md#re-authenticate).

## Testing

The Auth emulator supports SMS second factors, with the codes on its REST
API ([Phone](phone.md#testing)). It does not support TOTP: test that against
a real project.

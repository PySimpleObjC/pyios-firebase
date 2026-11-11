# Email and password

Enable **Email/Password** in the console (**Authentication > Sign-in
method**). Enable **Email link** under it for passwordless sign-in.

## Create an account and sign in

```python
from pyios_firebase.auth import Auth, AuthErrorCode

auth = Auth.auth()


def on_signed_in(result, error):
    if error is not None:
        if error.code == AuthErrorCode.EMAIL_ALREADY_IN_USE:
            show("That email has an account: sign in instead")
        elif error.code == AuthErrorCode.WEAK_PASSWORD:
            show("Choose a longer password")
        else:
            show(error.description)
        return
    show(f"Signed in as {result.user.email}")


auth.create_user_with_email_password("ada@example.com", "s3cret-pass", on_signed_in)
auth.sign_in_with_email_password("ada@example.com", "s3cret-pass", on_signed_in)
```

Creating the account signs the user in too.

!!! note "Email enumeration protection"
    New projects protect against email enumeration: a wrong email and a wrong
    password both give `INVALID_CREDENTIAL`, and `fetch_sign_in_methods` returns
    an empty list. That stops attackers from finding which emails have
    accounts. Show one message for both: "Wrong email or password".

## Password reset

```python
auth.send_password_reset("ada@example.com", lambda error: show("Check your inbox"))
```

The email links to a Firebase page where the user picks a new password. To
finish the reset **in your app**, see [Handle the links in the app](#handle-the-links-in-the-app).

## Verify the email address

```python
user = auth.current_user
user.send_email_verification(lambda error: show("Verification email sent"))

# later, after the user opened the link:
user.reload(lambda error: show_verified(auth.current_user.is_email_verified))
```

`is_email_verified` is cached: `reload` reads it again from the server. You
can require a verified email in your security rules
(`request.auth.token.email_verified`).

## Change the email address

With email enumeration protection on, a new email must be verified before it
is used:

```python
user.send_email_verification_before_updating_email("ada@new.example.com", on_sent)
```

The address changes when the user opens the link sent to the **new** address.
Without the protection, `user.update_email(email, callback)` changes it at
once. Both may need a [recent sign-in](users.md#re-authenticate).

## Email link sign-in

Passwordless: Firebase emails a link, and opening it signs the user in.

```python
from pyios_firebase.auth import ActionCodeSettings

settings = ActionCodeSettings(
    url="https://example.com/finish-sign-in",   # where the link goes; must be an authorized domain
    handle_code_in_app=True,                    # required for email links
    ios_bundle_id="com.example.app",
)


def send_link(email):
    def on_sent(error):
        if error is None:
            save_on_device("pending_email", email)  # needed to finish
            show("Check your email")

    auth.send_sign_in_link(email, settings, on_sent)
```

When the app is opened with the link:

```python
def on_open_url(link):
    if auth.is_sign_in_with_email_link(link):
        email = load_from_device("pending_email") or ask_user_for_email()
        auth.sign_in_with_email_link(email, link, on_signed_in)
```

The link must open your app: set up
[universal links](https://developer.apple.com/documentation/xcode/supporting-universal-links-in-your-app)
for the domain, or use a Firebase Hosting domain with
`ActionCodeSettings(link_domain="my-app.firebaseapp.com")` or your custom
Hosting domain (this replaces Dynamic Links, which shut down in 2025). In Kivy, opened URLs arrive through
`Window.bind(on_drop_file=...)`.

To link an email (with or without a password) to an existing account, see
[Link providers](users.md#link-providers): `EmailAuthProvider.credential(email,
password)` or `EmailAuthProvider.credential_with_link(email, link)`.

## `ActionCodeSettings`

| Field | |
|---|---|
| `url` | The continue URL: where the link leads after the action, and where you can [pass state](#passing-state-in-email-actions) |
| `handle_code_in_app` | `True` to open the link in the app (required for email links) |
| `ios_bundle_id` | The iOS app to open |
| `android_package_name`, `android_install_if_not_available`, `android_minimum_version` | The same for Android |
| `link_domain` | A custom Firebase Hosting domain for the link |

Use it with `send_sign_in_link`, `send_password_reset` and
`send_email_verification`.

## Handle the links in the app

Every email link carries an action code (`oobCode`). With
`handle_code_in_app=True`, the app gets the link and finishes the action
itself:

```python
from pyios_firebase.auth import ActionCodeURL

info = ActionCodeURL.from_link(opened_link)     # operation, code, continue_url...

# password reset
auth.verify_password_reset_code(info.code, lambda email, error: ask_new_password(email))
auth.confirm_password_reset(info.code, new_password, on_reset)

# email verification, or the change of email
auth.apply_action_code(info.code, on_applied)

# what a code is for
auth.check_action_code(info.code, lambda action, error: print(action.operation, action.email))
```

## Passing state in email actions

Put the state in the continue URL, and read it back from the link the app is
opened with:

```python
import urllib.parse
from pyios_firebase.auth import ActionCodeSettings, ActionCodeURL

settings = ActionCodeSettings(
    url="https://example.com/checkout?cart=42&coupon=WINTER",
    handle_code_in_app=True,
    ios_bundle_id="com.example.app",
)
auth.send_sign_in_link(email, settings, on_sent)

# when the app is opened with the link
info = ActionCodeURL.from_link(opened_link)
state = urllib.parse.parse_qs(urllib.parse.urlsplit(info.continue_url).query)
cart, coupon = state["cart"][0], state["coupon"][0]
```

!!! bug "Why `ActionCodeURL` parses in Python"
    Firebase iOS SDK 13.1.1's own parser cuts a continue URL at its first `&`,
    so `coupon` above would be lost. `ActionCodeURL.from_link` parses the link
    in Python and keeps the whole URL.

## Testing with the emulator

The Auth emulator sends no emails. The links it would have sent are listed by
its REST API, so a test can open them:

```bash
curl "http://127.0.0.1:9099/emulator/v1/projects/demo-my-app/oobCodes"
```

# Phone number

Sign in with a code sent by SMS. Enable **Phone** in the console
(**Authentication > Sign-in method**).

## Before you start

Firebase checks that requests come from your app before it sends an SMS:

1. **Silent push** (on a device): upload your APNs key in the console
   (**Project settings > Cloud Messaging**), and give the app the *Push
   Notifications* capability. Firebase then verifies the app with an invisible
   notification.
2. **reCAPTCHA** (the fallback, and the Simulator): Firebase shows a web page.
   It needs a **callback URL scheme** in `CFBundleURLTypes`: the
   `REVERSED_CLIENT_ID` from `GoogleService-Info.plist`, or, without one,
   `app-` + your `GOOGLE_APP_ID` with `-` for `:`:

    ```toml title="pyproject.toml (kivyforge)"
    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    CFBundleURLSchemes = ["app-1-1234567890-ios-0123456789abcdef"]
    ```

!!! warning "Without the URL scheme"
    The Firebase SDK stops the app (`NSException`) when the scheme is missing.
    pyios-firebase checks the scheme first, and gives an `AuthError` naming
    the exact scheme to add.

## Send the code, then sign in

```python
from pyios_firebase.auth import Auth, PhoneAuthProvider

auth = Auth.auth()
phone = PhoneAuthProvider()


def send_code(number):                       # E.164: "+15555550100"
    def on_code_sent(verification_id, error):
        if error is not None:
            return show(error.description)
        save_on_device("verification_id", verification_id)  # survives an app restart
        show_code_field()

    phone.verify_phone_number(number, on_code_sent)


def finish(code):                            # what the user typed
    credential = phone.credential(load_from_device("verification_id"), code)
    auth.sign_in_with_credential(credential, on_signed_in)
```

| Error | Means |
|---|---|
| `INVALID_PHONE_NUMBER` | Not a valid number (use the E.164 format, with `+` and the country code) |
| `INVALID_VERIFICATION_CODE` | The code is wrong |
| `SESSION_EXPIRED` | The code expired: send a new one |
| `QUOTA_EXCEEDED` | The project's SMS quota is used up |
| `TOO_MANY_REQUESTS` | Too many codes for this device |

## Change a user's phone number

```python
def on_code_sent(verification_id, error):
    credential = phone.credential(verification_id, code)
    auth.current_user.update_phone_number(credential, on_updated)
```

## Testing

- **Test numbers**: in the console (**Phone > Phone numbers for testing**),
  add numbers with a fixed code. No SMS is sent and no quota is used.
- **The emulator** sends no SMS, and needs no app verification. The codes it
  would have sent are on its REST API:

    ```bash
    curl "http://127.0.0.1:9099/emulator/v1/projects/demo-my-app/verificationCodes"
    ```

- `auth.app_verification_disabled_for_testing = True` skips app verification
  for test numbers, against a real project.

## When Firebase app delegate swizzling is off

With `FirebaseAppDelegateProxyEnabled` = `NO` in `Info.plist`, forward the
APNs token, notifications and URLs to Auth yourself:

```python
auth.set_apns_token(device_token)                 # from didRegisterForRemoteNotifications
auth.can_handle_notification(user_info)           # True if it was Auth's silent push
auth.can_handle_url(url)                          # True if it was the reCAPTCHA callback
```

# Authentication

[Firebase Authentication](https://firebase.google.com/docs/auth) signs users
in with a password, an email link, a phone number, an identity provider
(Google, Apple, Facebook...), or your own system, and gives each user a
stable `uid` that Firestore, Storage and the Realtime Database security rules
can check.

```python
from pyios_firebase.auth import Auth

auth = Auth.auth()


def on_user(user):
    if user is None:
        show_sign_in()
    else:
        show_home(user.uid)


auth.add_state_did_change_listener(on_user)
```

## Installation

1. Add the **`FirebaseAuth`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. In the Firebase console, open **Authentication > Sign-in method** and
   enable the providers you use.
3. Some methods need more in the app:

| Method | Also needs |
|---|---|
| Google | The `GoogleSignIn` package, and its reversed client ID URL scheme |
| Apple | The *Sign in with Apple* capability (`com.apple.developer.applesignin`) |
| Facebook | The `FacebookLogin` package and its `Info.plist` keys ([Social providers](social.md#facebook)) |
| Phone, web providers (Microsoft, GitHub...) | A callback URL scheme ([Phone](phone.md#before-you-start)) |
| Shared keychain | The *Keychain Sharing* capability |
| Multi-factor | Identity Platform enabled on the project |

### App configuration

What the app's build needs for this product. To combine several products, list
them all in one `products`; see [App configuration](../getting-started/configuration.md).

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist"]

    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = ["FirebaseAuth"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"

    # phone and web sign-in (Microsoft, GitHub, OIDC...): a callback URL scheme,
    # the REVERSED_CLIENT_ID, or "app-" + GOOGLE_APP_ID with "-" for ":"
    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    CFBundleURLSchemes = ["app-1-1234567890-ios-0123456789abcdef"]

    # Google Sign-In (pyios_firebase.auth.google)
    [tool.kivy.ios.native.swift_packages.GoogleSignIn-iOS]
    url = "https://github.com/google/GoogleSignIn-iOS"
    requirement = { from = "10.1.0" }
    products = ["GoogleSignIn"]

    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    # the REVERSED_CLIENT_ID
    CFBundleURLSchemes = ["com.googleusercontent.apps.1234567890-abcdef"]

    # Facebook Login (pyios_firebase.auth.facebook)
    [tool.kivy.ios.native.swift_packages.facebook-ios-sdk]
    url = "https://github.com/facebook/facebook-ios-sdk.git"
    requirement = { from = "19.0.1" }
    products = ["FacebookLogin"]

    [tool.kivy.ios.info_plist]
    FacebookAppID = "1234567890"
    FacebookClientToken = "your-client-token"
    FacebookDisplayName = "My App"
    LSApplicationQueriesSchemes = ["fbapi", "fb-messenger-share-api"]

    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    # fb + FacebookAppID
    CFBundleURLSchemes = ["fb1234567890"]

    # Sign in with Apple, Game Center, a shared keychain
    [tool.kivy.ios.entitlements]
    "com.apple.developer.applesignin" = ["Default"]
    "com.apple.developer.game-center" = true
    "keychain-access-groups" = ["$(AppIdentifierPrefix)com.example.shared"]
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseAuth`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.
    4. **Info > URL Types**: add the callback scheme (the `REVERSED_CLIENT_ID`, or `app-` + `GOOGLE_APP_ID` with `-` for `:`).
    5. Google: add the `GoogleSignIn-iOS` package (`https://github.com/google/GoogleSignIn-iOS`), and its `REVERSED_CLIENT_ID` as a URL scheme.
    6. Facebook: add the `facebook-ios-sdk` package (product `FacebookLogin`); in **Info**, `FacebookAppID`, `FacebookClientToken`, `FacebookDisplayName`, `LSApplicationQueriesSchemes`, and the URL scheme `fb<APP_ID>`.
    7. **Signing & Capabilities**: *Sign in with Apple*, *Game Center*, *Keychain Sharing*, for the methods you use.

!!! note
    Keep only the parts for the sign-in methods you use: email, anonymous and custom tokens need nothing beyond `FirebaseAuth`.

!!! note
    Google Sign-In's `REVERSED_CLIENT_ID` is in `GoogleService-Info.plist` once the Google provider is enabled (download the file again after enabling it).


## Guides

<div class="grid cards" markdown>

-   :material-email-outline: **[Email and password](email.md)**: accounts, password reset, verification, email links.
-   :material-google: **[Social providers](social.md)**: Google, Apple, Facebook, Microsoft, GitHub, OIDC, SAML, Game Center.
-   :material-cellphone-message: **[Phone number](phone.md)**: SMS codes, testing numbers.
-   :material-incognito: **[Anonymous and custom](anonymous.md)**: guests who sign up later, your own auth system.
-   :material-two-factor-authentication: **[Multi-factor](multi-factor.md)**: SMS and authenticator-app second factors.
-   :material-account-cog-outline: **[Users and accounts](users.md)**: profiles, linking, tokens for your backend, shared keychain, deleting.

</div>

## Who is signed in

```python
listener = auth.add_state_did_change_listener(on_user)   # runs now, then on each change
...
listener.remove()
```

The state listener is the reliable way to know: `auth.current_user` gives
the user at once, but it can be `None` for a moment at app start while
Firebase restores the saved user from the keychain.

| Listener | Called when |
|---|---|
| `add_state_did_change_listener(callback)` | A user signs in or out |
| `add_id_token_did_change_listener(callback)` | The same, and every time the ID token is refreshed (about hourly) |

The user stays signed in across launches (in the keychain) until you call:

```python
error = auth.sign_out()        # None, or an AuthError
```

## The `User`

| Property | |
|---|---|
| `uid` | The user's ID, the same for every provider linked to the account |
| `email`, `phone_number`, `display_name`, `photo_url` | From the providers, or set by you |
| `is_email_verified`, `is_anonymous` | |
| `provider_data` | One `UserInfo` per linked provider (`provider_id`, `uid`, `email`...) |
| `metadata` | `creation_date`, `last_sign_in_date` (UTC `datetime`) |
| `multi_factor` | The enrolled second factors ([Multi-factor](multi-factor.md)) |
| `tenant_id` | The Identity Platform tenant, if any |

The user's data is cached: call `user.reload(callback)` to read the latest
(after the user verified their email in a browser, for example).

## Sign-in results

Every sign-in callback gets `(result, error)`. `result` is an
`AuthDataResult`:

| Field | |
|---|---|
| `result.user` | The signed-in `User` |
| `result.additional_user_info.is_new_user` | `True` on the first sign-in: create the user's profile document then |
| `result.additional_user_info.provider_id` | `"password"`, `"google.com"`, `"apple.com"`... |
| `result.additional_user_info.profile` | What the provider sent about the user (a `dict`) |
| `result.credential` | The provider's credential (OAuth tokens), when there is one |

```python
def on_signed_in(result, error):
    if error is not None:
        return show_error(error)
    info = result.additional_user_info
    if info is not None and info.is_new_user:
        db.document_with_path(f"users/{result.user.uid}").set_data({"created": datetime.now(UTC)})
```

## Errors

Errors are `AuthError`s: a `FirebaseError` with `name` (the `AuthErrorCode`
name), and more keys for some codes ([Errors](../getting-started/errors.md)).

| `AuthErrorCode` | Means | Do |
|---|---|---|
| `INVALID_CREDENTIAL` | Wrong email or password (with email enumeration protection, both look the same) | Ask again |
| `EMAIL_ALREADY_IN_USE` | An account has that email | Offer to sign in |
| `WEAK_PASSWORD` | Under 6 characters, or the project's password policy | Ask for a stronger one |
| `INVALID_EMAIL` | Not an email address | |
| `USER_DISABLED` | Disabled in the console | |
| `TOO_MANY_REQUESTS` | Too many attempts from this device | Wait |
| `NETWORK_ERROR` | No connection | Retry |
| `REQUIRES_RECENT_LOGIN` | A sensitive change (password, email, delete) after an old sign-in | [Re-authenticate](users.md#re-authenticate), then retry |
| `ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL` | The email has an account with another provider | Sign in with that one, then [link](users.md#link-providers) (`error.email`, `error.updated_credential`) |
| `CREDENTIAL_ALREADY_IN_USE` | Linking a credential another account uses | `error.updated_credential` signs in to that account |
| `SECOND_FACTOR_REQUIRED` | The account has multi-factor | `error.resolver` ([Multi-factor](multi-factor.md#sign-in-with-a-second-factor)) |
| `OPERATION_NOT_ALLOWED` | The provider is not enabled in the console | |
| `KEYCHAIN_ERROR` | The keychain is not reachable (Keychain Sharing set up wrong) | |

`error.cancelled` is `True` when the user closed a Google, Apple or web
sign-in sheet: that is not a failure to report.

## Language

Emails, SMS and the reCAPTCHA page use the project's language. Change it:

```python
auth.language_code = "fr"
auth.use_app_language()        # or the device's language
```

## Use the local emulator

```python
core.configure()
Auth.auth().use_emulator("127.0.0.1", 9099)
```

The emulator signs anything in without email or SMS: its REST API lists the
codes it would have sent, so tests can finish every flow:

```bash
curl "http://127.0.0.1:9099/emulator/v1/projects/demo-my-app/oobCodes"           # email links
curl "http://127.0.0.1:9099/emulator/v1/projects/demo-my-app/verificationCodes"  # SMS codes
```

It also turns app verification off, so phone sign-in works without APNs or
reCAPTCHA. The Auth emulator supports SMS second factors, but not TOTP.

## Firebase's iOS guide, page by page

| Guide page | In pyios-firebase |
|---|---|
| Sign in with a pre-built UI | Not available: FirebaseUI is SwiftUI-only (unreachable from Rubicon), or CocoaPods-only for UIKit. Build the screens with your UI toolkit |
| Get Started, Manage Users | `Auth`, `User` ([Users and accounts](users.md)) |
| Password Authentication | [Email and password](email.md) |
| Email Link Authentication | [Email links](email.md#email-link-sign-in) |
| Sign in with Google / Apple / Facebook | [Social providers](social.md) |
| Twitter, GitHub, Microsoft, Yahoo, OpenID Connect, SAML | [Web providers](social.md#web-providers) |
| Game Center | [Game Center](social.md#game-center) |
| Phone Number | [Phone number](phone.md) |
| Custom Auth System, Anonymous | [Anonymous and custom](anonymous.md) |
| Cross-app auth with shared Keychain | [Shared keychain](users.md#shared-keychain) |
| Link Multiple Auth Providers | [Link providers](users.md#link-providers) |
| SMS / TOTP Multi-factor | [Multi-factor](multi-factor.md) |
| Passing State in Email Actions | [Passing state](email.md#passing-state-in-email-actions) |
| Handle Errors | [Errors](#errors) |

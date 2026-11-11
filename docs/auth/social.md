# Social providers

Every provider signs in the same way: show the provider's sheet, get a
credential, sign in to Firebase with it. pyios-firebase does all three in one
call, and gives the `(result, error)` callback every sign-in has.

```python
def on_signed_in(result, error):
    if error is not None:
        if not error.cancelled:          # the user closed the sheet: not an error to show
            show(error.message or error.description)
        return
    show(f"Welcome, {result.user.display_name}")
```

## Google

```python
from pyios_firebase.auth.google import start_google_sign_in

start_google_sign_in(on_signed_in)
```

**Needs:**

1. The **`GoogleSignIn`** Swift package
   (`https://github.com/google/GoogleSignIn-iOS`).
2. The Google provider enabled in the console. Download
   `GoogleService-Info.plist` **again** after enabling it: it then has the
   `CLIENT_ID` and `REVERSED_CLIENT_ID` Google Sign-In needs.
3. The `REVERSED_CLIENT_ID` as a URL scheme in `CFBundleURLTypes`:

    ```toml title="pyproject.toml (kivyforge)"
    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    CFBundleURLSchemes = ["com.googleusercontent.apps.1234567890-abcdef"]
    ```

4. In Kivy, a backup URL handler:
   `Window.bind(on_drop_file=google.on_gid_signin_handle_url_kivy)`
   ([Setup](../getting-started/setup.md#5-optional-google-sign-in-url-handling)).

`sign_out_of_google()` also signs out of Google Sign-In, so the next sign-in
lets the user choose another account.

## Apple

```python
from pyios_firebase.auth.apple import start_apple_sign_in


def on_apple(result, error):
    if error is not None:
        if not error.cancelled:
            show(error.message or error.description)
        return
    if result.first_name:                # only on the first sign-in to the app
        save_name(result.user.uid, result.first_name, result.last_name)


start_apple_sign_in(on_apple)
```

**Needs** the *Sign in with Apple* capability
(`com.apple.developer.applesignin`), and the Apple provider enabled in the
console.

- Apple shares the user's **name and email only on the first sign-in** to the
  app. Save them then. If that first Firebase sign-in fails (no network), the
  name is kept on the device for the next try.
- The user may hide their email: `result.user.email` is then an
  `@privaterelay.appleid.com` address that forwards to them.
- **Deleting an account** (an App Store rule): first revoke the Apple token
  with the authorization code of a recent sign-in.

    ```python
    def delete_account(apple_result):
        auth.revoke_token(apple_result.apple.authorization_code, lambda error: auth.current_user.delete(on_deleted))
    ```

`error.message` holds a sentence for the user when Apple's own error is not
clear (for example *"Sign in with Apple is not set up for this app"*).

## Facebook

```python
from pyios_firebase.auth import facebook

facebook.initialize_facebook()                     # once, at app start
facebook.start_facebook_sign_in(on_signed_in)      # or limited=True for Limited Login
```

**Needs:**

1. The **`FacebookLogin`** Swift package
   (`https://github.com/facebook/facebook-ios-sdk`).
2. A Facebook app, and the Facebook provider enabled in the Firebase console
   with its app ID and secret.
3. In `Info.plist`: `FacebookAppID`, `FacebookClientToken`,
   `FacebookDisplayName`, the URL scheme `fb<APP_ID>`, and
   `LSApplicationQueriesSchemes` with `fbapi` and `fb-messenger-share-api`.
4. The opened URLs routed to Facebook: `facebook.on_facebook_handle_url(url)`,
   or in Kivy `Window.bind(on_drop_file=facebook.on_facebook_handle_url_kivy)`.

| Mode | Gives | When |
|---|---|---|
| Classic (`limited=False`) | An access token | The user allowed tracking (App Tracking Transparency) |
| Limited Login (`limited=True`) | An OpenID token | Always available; iOS falls back to it when tracking is not allowed |

Both sign in to Firebase. Pass `permissions=["public_profile", "email"]` to
ask for more.

## Web providers

Microsoft, Yahoo, GitHub, Twitter (X), and your own OpenID Connect or SAML
providers sign in through a web page, in an in-app browser:

```python
from pyios_firebase.auth import OAuthProvider

auth.sign_in_with_provider(
    OAuthProvider("microsoft.com", scopes=["mail.read"], custom_parameters={"tenant": "contoso.com"}),
    on_signed_in,
)
```

| Provider | `provider_id` |
|---|---|
| Microsoft | `"microsoft.com"` |
| Yahoo | `"yahoo.com"` |
| GitHub | `"github.com"` |
| Twitter (X) | `"twitter.com"` |
| OpenID Connect | `"oidc.<your provider ID>"` |
| SAML | `"saml.<your provider ID>"` |

**Needs** a callback URL scheme: the `REVERSED_CLIENT_ID`, or, without one,
`app-` + your `GOOGLE_APP_ID` with `-` for `:` (for example
`app-1-1234567890-ios-0123456789abcdef`). Without it, the Firebase SDK stops
the app; pyios-firebase checks first and gives an `AuthError` that names the
scheme to add.

`result.credential` holds the provider's OAuth access token (and ID token),
to call the provider's own API (Microsoft Graph, GitHub's API...).

### With tokens you already have

If another SDK signed the user in, make a credential from its tokens:

```python
from pyios_firebase.auth import (
    FacebookAuthProvider,
    GitHubAuthProvider,
    GoogleAuthProvider,
    OAuthProvider,
    TwitterAuthProvider,
)

auth.sign_in_with_credential(GoogleAuthProvider.credential(id_token, access_token), on_signed_in)
auth.sign_in_with_credential(FacebookAuthProvider.credential(access_token), on_signed_in)
auth.sign_in_with_credential(GitHubAuthProvider.credential(token), on_signed_in)
auth.sign_in_with_credential(TwitterAuthProvider.credential(token, secret), on_signed_in)
auth.sign_in_with_credential(
    OAuthProvider.credential("oidc.my-idp", id_token=id_token, raw_nonce=nonce), on_signed_in
)
```

## Game Center

```python
from pyios_firebase.auth import GameCenterAuthProvider


def on_credential(credential, error):
    if error is None:
        auth.sign_in_with_credential(credential, on_signed_in)


GameCenterAuthProvider.get_credential(on_credential)
```

The local player must be signed in to Game Center first (GameKit's
`GKLocalPlayer`), and the app needs the *Game Center* capability.

## Credentials without signing in

`get_google_credential`, `get_apple_credential` and `get_facebook_credential`
show the sheet and give the credential **without** signing in. Use them to
[link](users.md#link-providers) the provider to the current user, or to
[re-authenticate](users.md#re-authenticate).

## One email, several providers

By default, one email address has one account. When a user who signed up
with Google tries Facebook with the same email, sign-in fails with
`ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`:

```python
def on_facebook(result, error):
    if error is not None and error.code == AuthErrorCode.ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL:
        pending = error.updated_credential              # the Facebook credential
        show(f"{error.email} already signs in with Google")

        def on_google(result, error):
            if error is None:
                result.user.link_with_credential(pending, on_linked)   # now both work

        start_google_sign_in(on_google)
```

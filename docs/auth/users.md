# Users and accounts

## Profile

```python
user = auth.current_user

user.update_profile(on_done, display_name="Ada Lovelace", photo_url="https://example.com/ada.png")
user.update_profile(on_done, photo_url=None)      # None removes it; a field left out is kept
```

`display_name` and `photo_url` are for your app to show; they are also in the
ID token, so your backend can read them.

## Link providers

One account can sign in with several providers: link more credentials to the
signed-in user. The `uid` stays the same.

```python
from pyios_firebase.auth import EmailAuthProvider, OAuthProvider
from pyios_firebase.auth.google import get_google_credential

user = auth.current_user

# a password
user.link_with_credential(EmailAuthProvider.credential("ada@example.com", "s3cret-pass"), on_linked)

# Google, without signing in again
get_google_credential(lambda credential, error: user.link_with_credential(credential, on_linked))

# a web provider
user.link_with_provider(OAuthProvider("github.com"), on_linked)

# and back
user.unlink("google.com", on_unlinked)
```

`user.provider_data` lists the linked providers. Linking a credential that
another account uses fails with `CREDENTIAL_ALREADY_IN_USE`;
`error.updated_credential` signs in to that other account, if you want to
merge.

## Re-authenticate

Changing the password or the email, and deleting the account, need a
**recent** sign-in. Otherwise they fail with `REQUIRES_RECENT_LOGIN`: ask the
user to sign in again, then retry.

```python
def change_password(current, new):
    credential = EmailAuthProvider.credential(auth.current_user.email, current)

    def on_reauthenticated(result, error):
        if error is None:
            auth.current_user.update_password(new, on_changed)

    auth.current_user.reauthenticate_with_credential(credential, on_reauthenticated)
```

For web providers: `user.reauthenticate_with_provider(OAuthProvider(...), callback)`.

## Delete an account

```python
auth.current_user.delete(on_deleted)
```

Delete the user's data too (Firestore, Storage): from the app before
`delete`, or with the [Delete User Data](https://extensions.dev/extensions/firebase/delete-user-data)
extension. Users who signed in with Apple must have their token revoked first
([Apple](social.md#apple)).

## Tokens for your backend

The **ID token** proves to your own server who the user is. Send it with
each request; the server checks it with the Admin SDK.

=== "App"

    ```python
    def call_backend():
        def on_token(token, error):
            if error is None:
                post("https://api.example.com/orders", headers={"Authorization": f"Bearer {token}"})

        auth.current_user.get_id_token(on_token)
    ```

=== "Server (Python, Admin SDK)"

    ```python
    from firebase_admin import auth

    decoded = auth.verify_id_token(token)
    uid = decoded["uid"]
    ```

`get_id_token_result` gives the token with its **custom claims** (set on the
server with `auth.set_custom_user_claims(uid, {...})`):

```python
def on_result(result, error):
    if error is None and result.claims.get("admin"):
        show_admin_tools()


auth.current_user.get_id_token_result(on_result, force_refresh=True)
```

The token lasts an hour and is refreshed by the SDK. `force_refresh=True`
gets a new one now: needed after the server changed the claims.
`add_id_token_did_change_listener` is called on every refresh.

## Shared keychain

Apps from the same team can share the signed-in user, with the **Keychain
Sharing** capability and the same access group in each:

```python
GROUP = "TEAMID.com.example.shared"

error = auth.use_user_access_group(GROUP)          # store the user in the shared group
user, error = auth.get_stored_user(GROUP)          # read it, without switching to it
if user is not None:
    auth.update_current_user(user, on_done)        # sign in as that user here
```

`use_user_access_group(None)` goes back to the app's own keychain.
`KEYCHAIN_ERROR` means the group is not in the app's entitlements.

## Sign-in methods of an email

```python
auth.fetch_sign_in_methods("ada@example.com", lambda methods, error: print(methods))
```

With email enumeration protection on (the default for new projects), this
always gives an empty list.

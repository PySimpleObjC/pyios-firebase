# Anonymous and custom

## Anonymous users

Let people use the app before they make an account. An anonymous user has a
real `uid`, so their data can be saved and protected by security rules from
the start. Enable **Anonymous** in the console.

```python
auth.sign_in_anonymously(on_signed_in)
```

Calling it again while an anonymous user is signed in keeps the same user.
`user.is_anonymous` is `True`.

### Keep the data when they sign up

Link a real credential to the anonymous user: the `uid` stays the same, so
everything saved under it stays theirs.

```python
from pyios_firebase.auth import AuthErrorCode, EmailAuthProvider


def sign_up(email, password):
    credential = EmailAuthProvider.credential(email, password)

    def on_linked(result, error):
        if error is None:
            show("Account created")          # same uid, now with an email
        elif error.code == AuthErrorCode.CREDENTIAL_ALREADY_IN_USE:
            show("That email has an account: sign in instead")

    auth.current_user.link_with_credential(credential, on_linked)
```

Any provider works: `link_with_provider(OAuthProvider(...))`, or the
credential from `get_google_credential` / `get_apple_credential`
([Social providers](social.md#credentials-without-signing-in)).

!!! note
    If the user signs in to an **existing** account instead, the anonymous
    account's data is not moved over. Copy what you need first, while the
    anonymous user is still signed in.

Anonymous accounts are never deleted automatically unless you enable
automatic cleanup (Identity Platform) in the console.

## Your own auth system

Sign in users your server already knows: the server makes a Firebase custom
token with the Admin SDK, and the app signs in with it.

=== "Server (Python, Admin SDK)"

    ```python
    import firebase_admin
    from firebase_admin import auth

    firebase_admin.initialize_app()


    def login(username, password):
        user = check_password(username, password)          # your system
        token = auth.create_custom_token(user.id, {"plan": user.plan})
        return token.decode()
    ```

=== "App"

    ```python
    def on_token_from_server(token):
        Auth.auth().sign_in_with_custom_token(token, on_signed_in)
    ```

The second argument of `create_custom_token` becomes custom claims, readable
in security rules (`request.auth.token.plan`) and in the app
([ID token claims](users.md#tokens-for-your-backend)). Custom tokens expire
after one hour; the Firebase session they start does not.

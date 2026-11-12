# Cloud Functions

[Callable functions](https://firebase.google.com/docs/functions/callable) run
your code on Google's servers, called from the app like a local function. The
SDK sends the signed-in user's ID token and the App Check token with each
call, and the function gets them already verified.

```python
from pyios_firebase.functions import Functions


def on_result(data, error):
    if error is not None:
        print(error.name, error.description, error.details)
        return
    print(data)                     # what the function returned, as Python values


Functions.functions().https_callable("addMessage").call(on_result, {"text": "Hello"})
```

## Installation

Add the **`FirebaseFunctions`** Swift package product
([Installation](../getting-started/installation.md)), and deploy your
functions with the Firebase CLI.

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
    products = ["FirebaseFunctions"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseFunctions`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.


## Write the function

Callable functions can be written in Python or Node.js. In Python:

```python title="functions/main.py"
from firebase_admin import initialize_app
from firebase_functions import https_fn

initialize_app()


@https_fn.on_call()
def addMessage(req: https_fn.CallableRequest) -> dict:
    if req.auth is None:
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.UNAUTHENTICATED, "Sign in first")
    text = req.data.get("text", "")
    if not text:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INVALID_ARGUMENT, "text is required", {"field": "text"}
        )
    return {"text": text.upper(), "uid": req.auth.uid}
```

`req.auth` is the signed-in user (`None` when signed out), and `req.app` the
App Check token, both verified by the framework.

## Call it

```python
functions = Functions.functions()                    # us-central1
functions = Functions.functions("europe-west1")      # another region
functions = Functions.functions(custom_domain="https://example.com")   # Hosting rewrites

add_message = functions.https_callable("addMessage")
add_message.call(on_result, {"text": "Hello"})
add_message.call(on_result)                          # no data

# by URL (Cloud Run, or a function in another project)
functions.https_callable_from_url("https://addmessage-abc123-ew.a.run.app").call(on_result)
```

### Data

`data` goes as JSON: dicts, lists, tuples, `str`, `int`, `float`, `bool` and
`None`, nested as deep as you like. The result comes back as the same Python
types.

| Python | Sent as |
|---|---|
| `int` | A JSON number. Only beyond ±2^53 does the SDK wrap it (`Int64Value`) to keep it exact; the Python Functions SDK does not unwrap that wrapper |
| `datetime` | Not allowed: send `dt.isoformat()` or a timestamp |
| `bytes` | Not allowed: send base64 text |
| `nan`, `inf` | Not allowed |

Values JSON cannot carry raise `TypeError` before anything is sent (the SDK
would abort the app on `nan`).

### Timeouts

```python
add_message.timeout_interval = 10      # seconds; the default is 70
```

A call that takes longer fails with `DEADLINE_EXCEEDED`. The function may
still finish on the server.

## Errors

Errors are `FunctionsError`s: `name` (from `FunctionsErrorCode`) and
`details`.

| What the function did | The app gets |
|---|---|
| `raise https_fn.HttpsError(code, message, details)` | That `code` (as `name`), the `message` (as `description`), and `details` as Python values |
| Raised any other exception | `INTERNAL`, **without** the message (so server details do not leak) |
| Does not exist (name, region or URL) | `NOT_FOUND` |
| Took longer than `timeout_interval` | `DEADLINE_EXCEEDED` |

```python
def on_result(data, error):
    if error is None:
        show(data["text"])
    elif error.name == "INVALID_ARGUMENT":
        highlight(error.details["field"])
    elif error.name == "UNAUTHENTICATED":
        show_sign_in()
    else:
        show("Something went wrong")
```

## App Check and replay protection

With [App Check](../app-check/index.md) set up, the SDK sends an App Check
token with every call. Enforce it in the function with
`@https_fn.on_call(enforce_app_check=True)`.

For sensitive functions, ask for a **limited-use** token that the function
consumes, so a captured request cannot be replayed:

```python
functions.https_callable("redeemCoupon", require_limited_use_app_check_tokens=True).call(on_result, data)
```

The function must consume the token. That option exists in the Node.js SDK
(`onCall({ enforceAppCheck: true, consumeAppCheckToken: true }, ...)`); the
Python Functions SDK has `enforce_app_check` but no replay protection yet.

## Use the local emulator

```python
Functions.functions().use_emulator("127.0.0.1", 5001)
Functions.functions("europe-west1").use_emulator("127.0.0.1", 5001)   # each region you call
```

```bash
firebase emulators:start --only functions
```

## Not available

Streaming callables (`stream()`) are Swift-only in the Firebase SDK (they use
Swift's `AsyncThrowingStream`), so Python cannot reach them.

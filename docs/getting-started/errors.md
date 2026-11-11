# Errors

There are two kinds of errors, and they reach you in two different ways:

| | When | How |
|---|---|---|
| **Firebase errors** | The server (or the SDK) says no: wrong password, permission denied, no network... | The `error` argument of your callback |
| **Python exceptions** | Your call cannot work at all: a bad path, a value Firebase cannot store, a call in the wrong order | Raised at once, by the method you called; nothing is sent |

## Firebase errors

Every callback `error` is a `FirebaseError` (or a subclass): a `dict` you can
also read with dots.

| Key | Type | What |
|---|---|---|
| `code` | `int` | The error code (`NSError.code`). Its meaning depends on `domain` |
| `description` | `str` | A human-readable message (`localizedDescription`) |
| `domain` | `str` | Where it comes from, for example `"FIRAuthErrorDomain"` |
| `underlying_error` | `NSError` or `None` | The lower-level error that caused it, for debugging |

```python
def on_done(error):
    if error is not None:
        print(error.domain, error.code, error.description)
        # the same, as a dict:
        print(error["domain"], error["code"])
```

### Per product

Most products add a **`name`**: the code's name in the product's error-code
class, so you can compare names instead of numbers, and log something
readable.

| Product | Error class | Codes | Domain | Extra keys |
|---|---|---|---|---|
| Authentication | `AuthError` | `AuthErrorCode` | `AUTH_ERROR_DOMAIN` | `name`, `email`, `updated_credential`, `resolver`, `cancelled`, `message` |
| Cloud Functions | `FunctionsError` | `FunctionsErrorCode` | `FUNCTIONS_ERROR_DOMAIN` | `name`, `details` |
| Cloud Storage | `StorageError` | `StorageErrorCode` | `STORAGE_ERROR_DOMAIN` | `name` |
| Realtime Database | `DatabaseError` | `DatabaseErrorCode` | `DATABASE_ERROR_DOMAIN` | `name` |
| Cloud Messaging | `MessagingError` | `MessagingErrorCode` | `MESSAGING_ERROR_DOMAIN` | `name` |
| Remote Config | `FirebaseError` | `RemoteConfigErrorCode` | `REMOTE_CONFIG_ERROR_DOMAIN` | |
| App Check | `FirebaseError` | `AppCheckErrorCode` | `APP_CHECK_ERROR_DOMAIN` | |
| Firestore | `FirebaseError` | The gRPC status codes ([Firestore errors](../firestore/index.md#errors)) | `"FIRFirestoreErrorDomain"` | |

`name` is `""` when the error comes from another domain (for example a network
error from the system, wrapped by Firebase).

```python
from pyios_firebase.storage import StorageErrorCode


def on_downloaded(data, error):
    if error is None:
        show_image(data)
    elif error.code == StorageErrorCode.OBJECT_NOT_FOUND:
        show_placeholder()
    else:
        log(f"storage: {error.name or error.domain} {error.description}")
```

### Errors that are not failures

| Error | Meaning |
|---|---|
| `AuthError` with `cancelled=True` | The user closed a Google, Apple or web sign-in sheet |
| `StorageErrorCode.CANCELLED` | You cancelled the upload or download |
| `RemoteConfigFetchStatus.THROTTLED` | Fetched too often: the cached values are still used |

### Errors that carry what you need next

| Error | Use |
|---|---|
| `AuthErrorCode.SECOND_FACTOR_REQUIRED` | `error.resolver` finishes the sign-in with a second factor ([Multi-factor](../auth/multi-factor.md#sign-in-with-a-second-factor)) |
| `AuthErrorCode.ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL` | `error.email` and `error.updated_credential`: sign in with the existing provider, then link |
| `FunctionsError` from an `HttpsError` | `error.details`: what the function attached, as Python values |

## Python exceptions

The Firebase SDK raises an **Objective-C exception** for some mistakes. Python
cannot catch those: the whole app aborts, with no traceback. pyios-firebase
checks these cases before calling the SDK and raises a normal Python
exception instead:

| Product | Raises | For example |
|---|---|---|
| Firestore | `TypeError`, `ValueError` | A value Firestore cannot store (a `set`, a `date` without a time, a non-`str` key); an empty `in` / `not-in` / `array-contains-any` list, or one with too many values |
| Realtime Database | `ValueError`, `TypeError` | A key with `. # $ [ ] /`, `nan`, a `datetime`, ordering a query twice, a limit of 0, update paths inside each other |
| Cloud Functions | `TypeError` | Data JSON cannot carry: a `datetime`, a `set`, `nan`, `inf` |
| Analytics | `ValueError`, `TypeError` | A reserved or invalid event name, a `bool` parameter, more than 25 parameters |
| Performance | `ValueError`, `RuntimeError` | A name starting with `_`, a sixth attribute; a trace before `core.configure()`, starting a trace twice |
| Crashlytics | `RuntimeError` | A second unsent-report check in one launch (the SDK would answer "no report") |
| App Check | `RuntimeError` | Choosing a provider after `core.configure()` |
| Messaging | `ValueError` | An invalid topic name |

Some of these the SDK would not abort on, but silently drop (an Analytics
event, a Performance attribute): an exception tells you while you develop,
instead of the data being missing in the console weeks later.

```python
try:
    ref.child(user_input).set_value(data)
except ValueError as e:     # for example a "." in the user's input
    show(f"Invalid name: {e}")
```

## Reporting errors to Crashlytics

Send unexpected Firebase errors and Python exceptions to Crashlytics, to see
them as issues in the console:

```python
from pyios_firebase.crashlytics import Crashlytics

crashlytics = Crashlytics.crashlytics()


def on_saved(error):
    if error is not None:
        crashlytics.record_error(error, {"screen": "checkout"})   # a FirebaseError works
```

See [Crashlytics](../crashlytics/index.md).

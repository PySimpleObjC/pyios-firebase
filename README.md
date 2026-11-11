# pyios-firebase

Use Firebase from Python on iOS. It is built on
[Rubicon-ObjC](https://github.com/beeware/rubicon-objc), so you write **pure Python**
and no Objective-C (`.m`) code.

It works with [Kivy](https://kivy.org), [BeeWare](https://beeware.org), and any other Python-on-iOS
framework that works with Rubicon-ObjC. It gives you Python-style names for the
Firebase iOS SDK, for example:

```python
db.collection_with_path("cities").document_with_path("SF")
```

> **Replaces [pyobjus-firebase](https://github.com/PySimpleObjC/pyobjus-firebase),
> which is now archived.**

---

## Table of contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Package layout](#package-layout)
5. [Setup](#setup)
6. [Type hints](#type-hints)
7. [How callbacks work](#how-callbacks-work)
8. [Cloud Firestore](#cloud-firestore)
9. [Authentication](#authentication)
10. [Cloud Functions](#cloud-functions)
11. [Cloud Storage](#cloud-storage)
12. [Remote Config](#remote-config)
13. [App Check](#app-check)
14. [API reference](#api-reference)
15. [Good to know](#good-to-know)
16. [Troubleshooting](#troubleshooting)
17. [Migrating](#migrating)
18. [Development](#development)
19. [Licenses](#licenses)

---

## Features

- **Core**: start Firebase
- **Cloud Firestore**
  - Add, get, set, update, and delete documents
  - Queries: filters, ordering, limits, start and end points, paging
  - OR and AND filters
  - Collection group queries
  - Live updates with snapshot listeners, with the list of changes
  - Count, sum, and average queries
  - Write batches and transactions
  - Field values: delete, server timestamp, array union, array remove, increment
  - Plain Python values in and out, including `datetime`, `None` and nested data
  - The local Firestore emulator, for development and tests
- **Authentication**
  - Email and password, email link (passwordless), anonymous, custom token, phone
  - Google, Apple and Facebook Login; Microsoft, Yahoo, GitHub, Twitter, OIDC and
    SAML web flows; Game Center
  - Multi-factor: SMS and TOTP (authenticator app) second factors
  - Shared keychain (cross-app sign-in), passing state in email actions
  - Sign-in state and ID token listeners
  - ID tokens and custom claims, for your backend
  - Profile and account changes, email verification, password reset, action codes
  - Linking and unlinking providers, re-authentication, anonymous upgrade
  - Typed errors (`AuthError`, `AuthErrorCode`)
  - The local Auth emulator, for development and tests
- **Cloud Functions**: callables by name, URL, region or custom domain; JSON data in
  and out; error codes and `details`; timeouts; limited-use App Check tokens; the
  emulator
- **Cloud Storage**: upload (bytes or files) and download (memory or file) with
  progress, pause, resume and cancel; metadata and custom metadata; listing with
  pages; download URLs; several buckets; retry settings; the emulator
- **Remote Config**: in-app defaults (plist, dict, Android XML); fetch, activate,
  fetch-and-activate; typed values with their source; real-time updates; custom
  signals
- **App Check**: DeviceCheck, App Attest, reCAPTCHA, the debug provider (with a CI
  token), custom providers written in Python; tokens, limited-use tokens, token
  listeners
- Pure Python. No `.m` or `.h` files.
- Callback blocks are kept alive for you, so they are not deleted too early.
- Each product is its own subpackage. You only need the Firebase frameworks of
  the products you import.
- Fully typed (PEP 561), with docstrings on every public class and method, so
  editors autocomplete and type checkers (mypy, pyright / Pylance) check your calls.

---

## Requirements

- iOS app built with Python (BeeWare, Kivy, or similar)
- Python 3.11 or newer
- [`rubicon-objc`](https://github.com/beeware/rubicon-objc)
- The Firebase iOS SDK frameworks you use, added to your iOS build:

  | Module | Framework |
  |---|---|
  | `core` | `FirebaseCore` (always) |
  | `firestore` | `FirebaseFirestore` |
  | `auth` | `FirebaseAuth` (+ `GoogleSignIn` for `auth.google`, `FacebookLogin` for `auth.facebook`) |
  | `functions` | `FirebaseFunctions` |
  | `storage` | `FirebaseStorage` |
  | `remote_config` | `FirebaseRemoteConfig` |
  | `app_check` | `FirebaseAppCheck` |

- A `GoogleService-Info.plist` file from your Firebase project, added to the app

---

## Installation

```bash
pip install pyios-firebase
```

Then add `pyios-firebase` to the requirements of your app (for example, in
`pyproject.toml` for BeeWare, or in `requirements` in `buildozer.spec` / kivy-ios
for Kivy).

> Adding the Firebase iOS frameworks to the Xcode project is different in each
> framework. See [Setup](#setup).

---

## Package layout

```
pyios_firebase/
├── types.py             FirebaseError, callback types, QueryDict
├── util.py              value and error conversion, block keep-alive
├── core/                configure(), default_app()
├── firestore/           Firestore, CollectionReference, DocumentReference,
│                        DocumentSnapshot, Query, QuerySnapshot, WriteBatch,
│                        Transaction, FieldValue, Filter, aggregates, enums
├── auth/                Auth, User, credentials and providers, AuthError
│   ├── google.py        start_google_sign_in(), get_google_credential()
│   ├── apple.py         start_apple_sign_in(), get_apple_credential()
│   ├── facebook.py      start_facebook_sign_in(), get_facebook_credential()
│   └── multi_factor.py  SMS and TOTP second factors
├── functions/           Functions, HTTPSCallable, FunctionsError
├── storage/             Storage, StorageReference, StorageMetadata, tasks, errors
├── remote_config/       RemoteConfig, RemoteConfigValue, ConfigUpdate
└── app_check/           providers, AppCheck, AppCheckToken, AppCheckProvider
```

Import from the subpackage:

```python
from pyios_firebase import core
from pyios_firebase.auth import Auth
from pyios_firebase.firestore import Firestore, FieldValue, Filter
```

In `core`, `auth` and `firestore`, Objective-C classes are looked up the first time
they are used, not on import.

---

## Setup

### 1. Add `GoogleService-Info.plist`

Download it from the Firebase console (Project settings, then your iOS app) and add
it to your app. Its `BUNDLE_ID` must match your app's bundle ID exactly.

### 2. Add the Firebase frameworks

Add the Firebase iOS SDK to your Xcode project (Swift Package Manager or CocoaPods).
Make sure the frameworks listed in [Requirements](#requirements) are linked.

If you see `class not found` errors later, a framework is missing from the build.

If you are building with [kivyforge](https://github.com/ElliotGarbus/kivyforge):

```toml
[[tool.kivy.ios.include_files]]
dest = "."
sources = ["GoogleService-Info.plist"]

[tool.kivy.ios.native.swift_packages.Firebase]
url = "https://github.com/firebase/firebase-ios-sdk.git"
requirement = { from = "13.1.1" } # or latest version
products = ["FirebaseAuth", "FirebaseAppCheck", "FirebaseFirestore"]

[tool.kivy.ios.native.swift_packages.GoogleSignIn-iOS]
url = "https://github.com/google/GoogleSignIn-iOS"
requirement = { from = "10.1.0" } # or latest version
products = ["GoogleSignIn"]

[tool.kivy.ios.xcode.build_settings]
OTHER_LDFLAGS = "$(inherited) -ObjC"

[[tool.kivy.ios.info_plist.CFBundleURLTypes]]
CFBundleTypeRole = "Editor"
CFBundleURLSchemes = ["com.googleusercontent.apps.YOUR_GOOGLE_REVERSE_CLIENT_ID_FROM_Info.plist"]
```

### 3. Start Firebase

Call this once, when the app starts, before you use any Firebase feature:

```python
from pyios_firebase import core

core.configure()
```

### 4. (Optional) App Check

Choose the App Check provider **before** `core.configure()` (see [App Check](#app-check)).
For testing, use the debug provider:

```python
from pyios_firebase import app_check, core

app_check.use_debug_provider()     # or use_app_attest_provider() / use_device_check_provider()
core.configure()
```

Run the app, find the line `Firebase App Check Debug Token: ...` in the Xcode
console, and add that token in the Firebase console (App Check, then your app,
then "Manage debug tokens").

Use the debug provider only for testing. For release builds, use App Attest or
DeviceCheck.

### 5. (Optional) Google Sign-In URL handling

In Kivy, SDL passes opened URLs to Python as a "drop file" event. You can send the
URL to Google Sign-In like this:

```python
from kivy.core.window import Window
from pyios_firebase.auth import google

Window.bind(on_drop_file=google.on_gid_signin_handle_url_kivy)
```

Your app must own the Google reversed client ID URL scheme
(`com.googleusercontent.apps.YOUR-CLIENT-ID`) in `CFBundleURLTypes` in `Info.plist`.
On newer versions of Google Sign-In, this handler may never be called, because the
result goes straight to your completion block. It is a safe backup.

---

## Type hints

Every public function and method is typed, and `pyios_firebase.types` has the
shapes to annotate your own callbacks with:

```python
from pyios_firebase.firestore import QuerySnapshot
from pyios_firebase.types import FirebaseError


def on_cities(snapshot: QuerySnapshot | None, error: FirebaseError | None) -> None:
    if error is not None:
        print(error.code, error.description)  # int, str
        return
    assert snapshot is not None
    for doc in snapshot:                       # DocumentSnapshot
        print(doc.document_id, doc.data)       # str, dict[str, Any]
```

| Type | What it is |
|---|---|
| `FirebaseError` | Every callback error: `code`, `description`, `domain`, `underlying_error` |
| `auth.AuthError` | An Auth error: adds `name`, `email`, `updated_credential`, `cancelled`, `message` |
| `ResultCallback[T]` | `Callable[[T \| None, FirebaseError \| None], None]` |
| `ErrorCallback` | `Callable[[FirebaseError \| None], None]`, for writes |
| `FirestoreData` | `Mapping[str, Any]`: data you write |
| `ObjCObject` | An Objective-C object from Rubicon (typed `Any`) |

Errors and results are still dicts (`QueryDict`), so `error["code"]` and
`error.code` both work. The classes only tell the type checker which keys exist.

Type checkers also catch mistakes such as a callback with the wrong number of
arguments, a `DocumentReference` where a `DocumentSnapshot` is needed (query
cursors), or a transaction function whose return type does not match its
callback.

Rubicon itself has no type information, so Objective-C objects the library does
not wrap are typed `Any` (the `ObjCObject` alias).

---

## How callbacks work

Firebase calls your code later, when the server answers. So most methods take a
**callback**: a normal Python function.

| Kind of method | Callback arguments |
|---|---|
| Firestore writes (`set_data`, `update_data`, `delete_document`, `commit`) | `(error)` |
| `add_document_with_data` | `(document_reference, error)` |
| `get_document`, document `add_snapshot_listener` | `(document_snapshot, error)` |
| `get_documents`, query `add_snapshot_listener` | `(query_snapshot, error)` |
| Aggregate queries | `(aggregate_snapshot, error)` |
| `run_transaction` | `(result, error)` |
| Auth sign-in, link, re-authenticate, Google / Apple sheets | `(auth_data_result, error)` |
| Auth writes (`send_password_reset`, `reload`, `delete`, `update_*`) | `(error)` |
| `add_state_did_change_listener` | `(user)` (`None` when signed out) |
| `HTTPSCallable.call` | `(data, error)` |
| Storage uploads / `get_metadata` / `update_metadata` | `(storage_metadata, error)` |
| `get_data`, `download_url`, `write_to_file`, `list` | `(bytes / url / path / list_result, error)` |
| `RemoteConfig.fetch_and_activate` / `fetch` / `activate` | `(status, error)` / `(status, error)` / `(changed, error)` |
| `AppCheck.token` / `limited_use_token` | `(app_check_token, error)` |

The rules are the same everywhere:

- `error` is `None` when it worked. Otherwise it is a `QueryDict` with `code`
  (`int`), `description` (`str`), `domain` (`str`) and `underlying_error`.
  A `QueryDict` is a dict you can also read with dots: `error.description`.
- When there is an error, the result is `None`.
- For write methods, the callback is optional.

```python
def on_cities(snapshot, error):
    if error:
        print("Error getting documents:", error.description)
        return
    for doc in snapshot:
        print(doc.document_id, "=>", doc.data)
```

---

## Cloud Firestore

```python
from pyios_firebase.firestore import Firestore

db = Firestore.firestore()
```

### Use the local emulator

For development and tests, point Firestore at the
[Firestore emulator](https://firebase.google.com/docs/emulator-suite) right after
`core.configure()`, before any other Firestore call:

```python
core.configure()
Firestore.firestore().use_emulator("127.0.0.1", 8080)
```

`use_emulator` sets the host and turns TLS off (the emulator speaks plain
HTTP/2; the SDK's own `useEmulator` only sets the host). The iOS Simulator
shares the Mac's network, so `127.0.0.1` works there. On a device, use the
Mac's LAN address and start the emulator with `"host": "0.0.0.0"`.

### Add a document with a generated ID

```python
def on_added(ref, error):
    if error:
        print("Error adding document:", error.description)
    else:
        print("Document added with ID:", ref.document_id)


db.collection_with_path("users").add_document_with_data(
    {"first": "Ada", "last": "Lovelace", "born": 1815},
    on_added,
)
```

`add_document_with_data` also gives back the `DocumentReference` right away.
To get an ID before saving, use `collection.document_with_auto_id()`.

### Set, update, and delete a document

```python
doc = db.collection_with_path("cities").document_with_path("DC")

doc.set_data({"name": "Washington", "capital": False}, callback=on_done)  # replaces everything
doc.set_data({"capital": True}, merge=True, callback=on_done)             # keeps the other fields
doc.update_data({"capital": True}, on_done)                               # only these fields
doc.delete_document(on_done)
```

You can also use the full path from the database:

```python
db.document_with_path("cities/DC").update_data({"capital": True}, on_done)
```

### Read one document

```python
def on_city(snapshot, error):
    if error:
        print("Error getting document:", error.description)
        return
    if snapshot.exists:
        print("Document data:", snapshot.data)
        print("Name:", snapshot.get("name"), snapshot["address.city"])
    else:
        print("Document does not exist")


db.collection_with_path("cities").document_with_path("SF").get_document(on_city)
```

Read from the cache or the server only with
`get_document(on_city, source=FIRFirestoreSource.Cache)`.

### Read many documents

```python
# All documents in a collection
db.collection_with_path("cities").get_documents(on_cities)

# Only some of them
db.collection_with_path("cities") \
    .query_where_field_is_equal_to("capital", True) \
    .get_documents(on_cities)
```

A `QuerySnapshot` works like a list of `DocumentSnapshot`: `len(snapshot)`,
`snapshot[0]`, `for doc in snapshot`. It also has `is_empty`, `documents`,
`document_changes` and `metadata`.

### Filter, order, and limit

Each method gives a **new** query, so you can chain them:

```python
db.collection_with_path("cities") \
    .query_where_field_is_equal_to("state", "CA") \
    .query_ordered_by_field("population", descending=True) \
    .query_limited_to(10) \
    .get_documents(on_cities)
```

### OR and AND filters

```python
from pyios_firebase.firestore import Filter

query = db.collection_with_path("cities").query_where_filter(
    Filter.or_filter_with_filters([
        Filter.filter_where_field_is_equal_to("capital", True),
        Filter.filter_where_field_is_greater_than_or_equal_to("population", 1000000),
    ])
)
query.get_documents(on_cities)
```

Filters can be nested, for example an `and_filter_with_filters` inside an
`or_filter_with_filters`.

### Start and end points

```python
# Population of one million or more, from small to big
db.collection_with_path("cities") \
    .query_ordered_by_field("population") \
    .query_starting_at_values([1000000]) \
    .get_documents(on_cities)
```

You can also start or end at a document (useful for paging):

```python
query = db.collection_with_path("cities") \
    .query_ordered_by_field("population") \
    .query_starting_after_document(last_doc) \
    .query_limited_to(25)
```

`last_doc` must be a `DocumentSnapshot` from a callback (for example
`snapshot[-1]`), because it needs the data that was loaded.

### Collection group queries

Search every collection with the same name, wherever it is:

```python
db.collection_group_with_id("landmarks") \
    .query_where_field_is_equal_to("type", "museum") \
    .get_documents(on_landmarks)
```

Pass only the collection name, not a path.

### Live updates (snapshot listeners)

```python
# One document: callback gets (DocumentSnapshot, error)
listener = db.collection_with_path("cities").document_with_path("SF") \
    .add_snapshot_listener(on_city_changed)

# A query or a whole collection: callback gets (QuerySnapshot, error)
listener = db.collection_with_path("cities") \
    .query_where_field_is_equal_to("state", "CA") \
    .add_snapshot_listener(on_cities_changed)

# Stop listening
listener.remove()
```

The callback runs once at the start, and then again every time the data changes.
To see **only what changed**, use `snapshot.document_changes`:

```python
from pyios_firebase.firestore import DocumentChange


def on_cities_changed(snapshot, error):
    if error:
        print("Error fetching documents:", error.description)
        return
    for diff in snapshot.document_changes:
        if diff.type == DocumentChange.ADDED:
            print("New city:", diff.document.data)
        if diff.type == DocumentChange.MODIFIED:
            print("Modified city:", diff.document.data)
        if diff.type == DocumentChange.REMOVED:
            print("Removed city:", diff.document.data)
```

Pass `include_metadata_changes=True`, or
`options=SnapshotListenOptions(include_metadata_changes=True, source=FIRListenSource.Cache)`,
for more control.

### Field values

```python
from pyios_firebase.firestore import FieldValue

region_ref = db.collection_with_path("cities").document_with_path("DC")

region_ref.update_data({"regions": FieldValue.field_value_for_array_union(["greater_virginia"])})
region_ref.update_data({"regions": FieldValue.field_value_for_array_remove(["east_coast"])})
region_ref.update_data({"population": FieldValue.field_value_for_integer_increment(1)})
region_ref.update_data({"updated": FieldValue.field_value_for_server_timestamp()})
region_ref.update_data({"old_field": FieldValue.field_value_for_delete()})
```

### Write batches

A batch saves many writes together. **All of them work, or none of them do.**

```python
cities = db.collection_with_path("cities")

batch = db.batch()
batch.set_data({}, cities.document_with_path("NYC"))
batch.update_data({"population": 1000000}, cities.document_with_path("SF"))
batch.delete_document(cities.document_with_path("LA"))
batch.commit(on_committed)
```

A batch can hold up to 500 writes. Use a batch only once.

### Transactions

A transaction reads first and then writes, safely.

```python
from pyios_firebase.firestore import TransactionException

sf_reference = db.collection_with_path("cities").document_with_path("SF")


def update_population(transaction):
    sf_document = transaction.get_document(sf_reference)
    population = sf_document.get("population")
    if not isinstance(population, (int, float)):
        raise TransactionException("Unable to read population from snapshot")

    population = int(population) + 1
    if population >= 1000000:
        raise TransactionException("Population too big")

    transaction.update_data({"population": population}, sf_reference)
    return population   # passed out to the callback


def on_transaction_done(result, error):
    if error:
        print("Transaction failed:", error.description)
    else:
        print("Population increased to", result)


db.run_transaction(update_population, on_transaction_done)
```

Important rules:

- Raise an exception to stop the transaction. Its message becomes
  `error.description`.
- The function can run **more than once**, so only read and write data inside it.
  Do not print, change the screen, or change your app's state there.
- Do all reads (`get_document`) before any write (`set_data`, `update_data`,
  `delete_document`).
- Pass what you need **out** of the transaction by returning it. Any Python value
  works.

### Count, sum, and average

```python
from pyios_firebase.firestore import AggregateField, FIRAggregateSource

# Count only
def on_count(snapshot, error):
    if error:
        print("Error fetching count:", error.description)
    else:
        print("Cities count:", snapshot.count)


db.collection_with_path("cities").count.aggregation_with_source(
    FIRAggregateSource.Server, on_count
)

# Count, sum, and average in one request
count_field = AggregateField.aggregate_field_for_count()
sum_field = AggregateField.aggregate_field_for_sum_of_field("population")
avg_field = AggregateField.aggregate_field_for_average_of_field("population")


def on_stats(snapshot, error):
    if error:
        print("Error fetching aggregate:", error.description)
        return
    print("Count:", snapshot.value_for_aggregate_field(count_field))
    print("Sum:", snapshot.value_for_aggregate_field(sum_field))
    print("Avg:", snapshot.value_for_aggregate_field(avg_field))


db.collection_with_path("cities") \
    .aggregate([count_field, sum_field, avg_field]) \
    .aggregation_with_source(FIRAggregateSource.Server, on_stats)
```

These are calculated on the server. They do not download the documents.

### Python values and Firestore types

You write and read plain Python values. They are converted for you everywhere a
value goes in or comes out: `set_data`, `update_data`, `add_document_with_data`,
batches, transactions, query filters and cursors, `Filter`, array `FieldValue`s,
`snapshot.data` and `snapshot.get(...)`. Nested dicts and lists are converted too.

| Python | Firestore | Read back as |
|---|---|---|
| `str` | string | `str` |
| `int` | integer (64-bit) | `int` |
| `float` | double | `float` |
| `bool` | boolean | `bool` |
| `None` | null | `None` |
| `datetime` | timestamp | `datetime`, timezone-aware, in UTC |
| `bytes` | bytes | `bytes` |
| `dict` (`str` keys) | map | `dict` |
| `list`, `tuple` | array | `list` |
| `DocumentReference` | reference | `DocumentReference` |
| `FieldValue.*` | special write operations | (not stored as a value) |

```python
from datetime import UTC, datetime

doc.set_data({
    "title": "Launch",
    "starts_at": datetime(2026, 12, 1, 9, 30, tzinfo=UTC),
    "cancelled_at": None,
    "owner": db.document_with_path("users/ada"),
})

db.collection_with_path("events") \
    .query_where_field_is_greater_than("starts_at", datetime.now(UTC)) \
    .get_documents(on_events)
```

About dates and times:

- Timestamps keep **microseconds**, both ways. Firestore stores nanoseconds, but
  a Python `datetime` cannot hold them, so the extra digits are dropped on read.
- A **naive** `datetime` (no `tzinfo`) is read as **UTC**, like the Firebase Admin
  SDK for Python does. Use aware datetimes (`datetime.now(UTC)`) to be explicit.
- Values you read are always in UTC. Use `.astimezone()` to show local time.
- A plain `date` is refused, because Firestore has no date-only type. Pass a
  `datetime`, for example `datetime.combine(d, time(), tzinfo=UTC)`, or store the
  date as an ISO string.

Values Firestore cannot store (for example a `set`, a `date`, or a field name
that is not a `str`) raise a `TypeError` in Python, with the path of the bad field
(`"events[0].at: ..."`), before anything is sent. Other special Firestore types
(for example `FIRGeoPoint`) pass through as Objective-C objects in both
directions.

---

## Authentication

```python
from pyios_firebase.auth import Auth

auth = Auth.auth()
```

Every Auth callback gets `(result, error)` or `(error)`. `error` is an `AuthError`:
a `FirebaseError` plus `name` (the `AuthErrorCode` name), `email`,
`updated_credential`, `cancelled` and `message`.

### Know who is signed in

```python
def on_user(user):
    if user is None:
        show_sign_in_screen()
    else:
        show_home(user.uid, user.email)


listener = auth.add_state_did_change_listener(on_user)  # runs now, then on each change
...
listener.remove()
```

`auth.current_user` gives the user right away, but it can be `None` for a moment
at app start while Firebase restores the saved user; the listener is reliable.

### Email and password

```python
from pyios_firebase.auth import AuthErrorCode


def on_signed_in(result, error):
    if error is not None:
        if error.code == AuthErrorCode.EMAIL_ALREADY_IN_USE:
            print("That email has an account: sign in instead")
        else:
            print("Sign-in failed:", error.name, error.description)
        return
    print("Signed in:", result.user.uid, "new account:", result.additional_user_info.is_new_user)


auth.create_user_with_email_password("ada@example.com", "s3cret-pass", on_signed_in)
auth.sign_in_with_email_password("ada@example.com", "s3cret-pass", on_signed_in)
auth.sign_out()  # None, or an AuthError
```

With email enumeration protection (the default for new projects), a wrong email
and a wrong password both give `INVALID_CREDENTIAL`.

### Password reset and email verification

```python
auth.send_password_reset("ada@example.com", on_sent)
auth.current_user.send_email_verification(on_sent)

# after the user opened the link (or in your own handler for it):
auth.current_user.reload(lambda error: print(auth.current_user.is_email_verified))
```

To handle the links in the app, pass `ActionCodeSettings(url=..., handle_code_in_app=True,
ios_bundle_id=...)` and use `verify_password_reset_code`, `confirm_password_reset`,
`check_action_code` and `apply_action_code` with the link's `oobCode`.

### Email link (passwordless)

```python
from pyios_firebase.auth import ActionCodeSettings

settings = ActionCodeSettings(
    url="https://example.com/finish-sign-in",
    handle_code_in_app=True,
    ios_bundle_id="com.example.app",
)
auth.send_sign_in_link("ada@example.com", settings, on_sent)  # save the email on the device

# when the app is opened with the link:
if auth.is_sign_in_with_email_link(link):
    auth.sign_in_with_email_link(saved_email, link, on_signed_in)
```

### Anonymous users, and keeping their data when they sign up

```python
from pyios_firebase.auth import EmailAuthProvider

auth.sign_in_anonymously(on_signed_in)
...
credential = EmailAuthProvider.credential("ada@example.com", "s3cret-pass")
auth.current_user.link_with_credential(credential, on_linked)  # same uid, now with email
```

### Google and Apple

```python
from pyios_firebase.auth.apple import start_apple_sign_in
from pyios_firebase.auth.google import start_google_sign_in


def on_signed_in(result, error):
    if error is not None:
        if not error.cancelled:          # cancelled: the user closed the sheet
            print(error.message or error.description)
        return
    print("Signed in:", result.user.uid)


start_google_sign_in(on_signed_in)
start_apple_sign_in(on_signed_in)         # result.first_name / last_name: first sign-in only
```

- Google needs the `GoogleSignIn` framework and its URL scheme (see [Setup](#5-optional-google-sign-in-url-handling)).
- Apple needs the `com.apple.developer.applesignin` entitlement. Apple shares the
  user's name and email only on the **first** sign-in to the app; if that first
  Firebase sign-in fails, the name is kept on the device for the next try.
- `get_google_credential` / `get_apple_credential` show the sheet and give the
  credential without signing in: use them to link the provider to the current
  user, or to re-authenticate.
- Before deleting an Apple user, pass `result.apple.authorization_code` (from a
  recent sign-in) to `auth.revoke_token` (App Store rule).

### Other providers

```python
from pyios_firebase.auth import OAuthProvider, PhoneAuthProvider

# web flows (Microsoft, Yahoo, GitHub, OIDC, SAML), in an in-app browser
auth.sign_in_with_provider(OAuthProvider("microsoft.com", scopes=["mail.read"]), on_signed_in)

# phone: send a code, then sign in with what the user typed
phone = PhoneAuthProvider()
phone.verify_phone_number("+15555550100", on_code_sent)   # gives a verification_id
auth.sign_in_with_credential(phone.credential(verification_id, code), on_signed_in)

# tokens from other SDKs
from pyios_firebase.auth import FacebookAuthProvider, GitHubAuthProvider, TwitterAuthProvider
auth.sign_in_with_credential(FacebookAuthProvider.credential(access_token), on_signed_in)
```

Phone and web sign-in need a callback URL scheme in `Info.plist` (the reversed
client ID, or `app-` + your `GOOGLE_APP_ID` with `-` for `:`). Without it the
Firebase SDK stops the app; pyios-firebase checks first and gives an `AuthError`
that names the scheme to add.

### Facebook Login

```python
from pyios_firebase.auth import facebook

facebook.initialize_facebook()                      # once, at app start
facebook.start_facebook_sign_in(on_signed_in)       # or limited=True for Limited Login
```

Needs the `FacebookLogin` Swift package (`https://github.com/facebook/facebook-ios-sdk`),
the Facebook provider enabled in the Firebase console, and in `Info.plist`:
`FacebookAppID`, `FacebookClientToken`, `FacebookDisplayName`, the URL scheme
`fb<APP_ID>`, and `LSApplicationQueriesSchemes` with `fbapi` and
`fb-messenger-share-api`. Route opened URLs to `facebook.on_facebook_handle_url`
(Kivy: `Window.bind(on_drop_file=facebook.on_facebook_handle_url_kivy)`). Classic
login gives an access token; Limited Login (also what iOS falls back to when the
user has not allowed tracking) gives an OpenID token; both sign in.

### Multi-factor authentication (SMS and TOTP)

Needs Identity Platform, the factor enabled in the console, and a verified email.

```python
from pyios_firebase.auth import (
    AuthErrorCode, PhoneAuthProvider, PhoneMultiFactorGenerator, TOTPMultiFactorGenerator,
)

# enroll an SMS factor
user = auth.current_user
phone = PhoneAuthProvider()
def on_session(session, error):
    phone.verify_phone_number("+15555550100", on_code_sent, multi_factor_session=session)
def on_code_sent(verification_id, error):
    assertion = PhoneMultiFactorGenerator.assertion(phone.credential(verification_id, code))
    user.multi_factor.enroll(assertion, "My phone", on_enrolled)
user.multi_factor.get_session(on_session)

# enroll a TOTP factor (authenticator app)
def on_secret(secret, error):
    show_qr_code(secret.generate_qr_code_url(user.email, "My App"))
    ...  # when the user types the code from the app:
    user.multi_factor.enroll(TOTPMultiFactorGenerator.assertion_for_enrollment(secret, code), "Authenticator")
user.multi_factor.get_session(lambda session, error: TOTPMultiFactorGenerator.generate_secret(session, on_secret))

# sign in when a second factor is needed
def on_signed_in(result, error):
    if error is not None and error.code == AuthErrorCode.SECOND_FACTOR_REQUIRED:
        resolver = error.resolver
        hint = resolver.hints[0]                       # let the user choose
        if hint.factor_id == "phone":
            phone.verify_phone_number_for_sign_in(hint, resolver.session, on_sign_in_code_sent)
        else:                                          # "totp"
            resolver.resolve_sign_in(TOTPMultiFactorGenerator.assertion_for_sign_in(hint.uid, code), on_signed_in)
```

`user.multi_factor.enrolled_factors` lists the factors; `unenroll(factor)` removes one.

### Shared keychain (cross-app sign-in)

With the Keychain Sharing capability and the same access group in both apps:

```python
error = auth.use_user_access_group("TEAMID.com.example.shared")
user, error = auth.get_stored_user("TEAMID.com.example.shared")  # without switching to it
if user is not None:
    auth.update_current_user(user, on_done)
```

### Passing state in email actions

Put the state in the continue URL, and read it back from the link the app is opened with:

```python
import urllib.parse
from pyios_firebase.auth import ActionCodeSettings, ActionCodeURL

settings = ActionCodeSettings(url="https://example.com/checkout?cart=42", handle_code_in_app=True,
                              ios_bundle_id="com.example.app")
auth.send_sign_in_link(email, settings, on_sent)

info = ActionCodeURL.from_link(opened_link)
cart = urllib.parse.parse_qs(urllib.parse.urlsplit(info.continue_url).query)["cart"][0]
```

`ActionCodeURL` parses links in Python: Firebase iOS SDK 13.1.1's own parser cuts
a continue URL at its first `&`, losing the rest of the state.

### Tokens for your backend

```python
def on_token(result, error):
    send_to_backend(result.token)            # verify it with the Admin SDK
    print(result.claims.get("role"))         # custom claims set by your backend


auth.current_user.get_id_token_result(on_token, force_refresh=True)
```

`add_id_token_did_change_listener` also fires when the token is refreshed
(about once an hour).

### Profile and account

```python
user = auth.current_user
user.update_profile(on_done, display_name="Ada Lovelace", photo_url=None)  # None removes it
user.update_password("new-pass-123", on_done)
user.reauthenticate_with_credential(credential, on_done)  # before sensitive changes
user.delete(on_done)
user.unlink("google.com", on_unlinked)
```

`REQUIRES_RECENT_LOGIN` means: re-authenticate, then try again.

### Firebase's iOS Authentication guide, page by page

| Guide page | In pyios-firebase |
|---|---|
| Sign in with a pre-built UI | Not available: FirebaseUI's Swift package is SwiftUI-only, which Rubicon cannot reach, and its UIKit version is CocoaPods-only. Build the screens with your UI toolkit and the methods below |
| Get Started, Manage Users | `Auth`, `User` (profile, `update_*`, `delete`, `reload`, `send_email_verification`, `provider_data`, `metadata`) |
| Password Authentication | `create_user_with_email_password`, `sign_in_with_email_password`, `send_password_reset`, `confirm_password_reset` |
| Email Link Authentication, Email Link Migration | `send_sign_in_link`, `is_sign_in_with_email_link`, `sign_in_with_email_link`; `ActionCodeSettings.link_domain` for the Hosting domain that replaces Dynamic Links |
| Sign in with Google | `auth.google.start_google_sign_in` / `get_google_credential` |
| Facebook Login | `auth.facebook.start_facebook_sign_in` (classic and Limited Login) / `get_facebook_credential` |
| Sign in with Apple | `auth.apple.start_apple_sign_in` / `get_apple_credential`, `Auth.revoke_token` |
| Twitter, GitHub, Microsoft, Yahoo | `sign_in_with_provider(OAuthProvider("twitter.com" / "github.com" / "microsoft.com" / "yahoo.com"))`, or a credential from tokens you have |
| Game Center Sign-in | `GameCenterAuthProvider.get_credential` |
| Phone Number | `PhoneAuthProvider.verify_phone_number` + `credential`; `set_apns_token`, `can_handle_notification`, `can_handle_url` |
| OpenID Connect | `OAuthProvider("oidc.<id>")` web flow, or `OAuthProvider.credential("oidc.<id>", id_token=...)`; SAML with `"saml.<id>"` |
| Use a Custom Auth System | `sign_in_with_custom_token` |
| Anonymous Authentication | `sign_in_anonymously`, then `link_with_credential` |
| Cross-app auth with shared Keychain | `use_user_access_group`, `get_stored_user`, `update_current_user` |
| Link Multiple Auth Providers | `link_with_credential`, `link_with_provider`, `unlink`, `AuthError.updated_credential` |
| SMS Multi-factor Auth, TOTP Multi-factor Auth | `pyios_firebase.auth.multi_factor` (below) |
| Passing State in Email Actions | `ActionCodeSettings(url=...)` and `ActionCodeURL.from_link(link).continue_url` |
| Handle Errors | `AuthError` / `AuthErrorCode` |

### Use the local emulator

```python
core.configure()
Auth.auth().use_emulator("127.0.0.1", 9099)
```

The emulator also turns app verification off, so phone sign-in works without
APNs or reCAPTCHA. Its REST API shows the emails and SMS codes it "sent"
(`/emulator/v1/projects/<project>/oobCodes` and `/verificationCodes`).

---

## Cloud Functions

```python
from pyios_firebase.functions import Functions, FunctionsErrorCode


def on_result(data, error):
    if error is not None:
        if error.code == FunctionsErrorCode.INVALID_ARGUMENT:
            print("Bad input:", error.description, error.details)
        return
    print("The function returned:", data)


add_message = Functions.functions().https_callable("addMessage")
add_message.timeout_interval = 30
add_message.call(on_result, {"text": "Hello", "tags": ["a", "b"]})
```

- `data` goes as JSON: dicts, lists, tuples, strings, numbers, bools and `None`.
  Anything else (a `datetime`, a `set`, `nan`, `inf`) raises `TypeError` before
  anything is sent. Ints go as plain JSON numbers, so Python and Node.js functions
  both get an `int`. Only ints beyond ±2^53 use the SDK's `Int64Value` wrapper,
  which keeps them exact; the Python Functions SDK does not unwrap it.
- `error` is a `FunctionsError`: `code` (`FunctionsErrorCode`), `name`, `description`
  and `details` (what the function put in its `HttpsError`). An unexpected error in
  the function is `INTERNAL`, without its message.
- The signed-in user's ID token and the App Check token are sent for you.

| Guide page | In pyios-firebase |
|---|---|
| Call functions from your app | `Functions.functions(region)`, `https_callable(name)`, `call(callback, data)` |
| Handle errors | `FunctionsError`, `FunctionsErrorCode`, `error.details` |
| Call functions via URL / custom domain | `https_callable_from_url(url)`, `Functions.functions(custom_domain=...)` |
| Enforce App Check / replay protection | sent automatically; `https_callable(name, require_limited_use_app_check_tokens=True)` |
| Timeouts | `HTTPSCallable.timeout_interval` |
| Connect to the emulator | `Functions.functions().use_emulator("127.0.0.1", 5001)` (per region) |
| Streaming callables | Not available: `stream()` is Swift-only in the Firebase SDK |

---

## Cloud Storage

```python
from pyios_firebase.storage import Storage, StorageMetadata, StorageTaskStatus

ref = Storage.storage().reference().child(f"users/{uid}/avatar.jpg")

metadata = StorageMetadata(content_type="image/jpeg", custom_metadata={"owner": uid})
task = ref.put_file("/path/to/avatar.jpg", callback=on_uploaded, metadata=metadata)
task.observe(StorageTaskStatus.PROGRESS, lambda s: print(f"{s.fraction_completed:.0%}"))
# task.pause() / task.resume() / task.cancel()

ref.get_data(5 * 1024 * 1024, lambda data, error: ...)         # into memory
ref.write_to_file("/path/to/local.jpg", lambda path, error: ...)  # large files
ref.download_url(lambda url, error: ...)
```

| Guide page | In pyios-firebase |
|---|---|
| Create a reference | `Storage.storage()`, `reference()`, `child(path)`, `parent()`, `root()`, `reference_with_path`, `reference_for_url` |
| Upload files | `put_data(bytes)`, `put_file(path)`, with `metadata=`; the returned `StorageUploadTask` |
| Download files | `get_data(max_size)`, `write_to_file(path)`, `download_url()` |
| Use file metadata | `get_metadata`, `update_metadata` (set a field to `None` to delete it), `StorageMetadata` |
| Delete files | `delete()` |
| List files | `list_all()`, `list(max_results, page_token=)` → `StorageListResult` |
| Monitor, pause, resume, cancel | `task.observe(status, handler)`, `remove_observer`, `pause`, `resume`, `cancel`, `task.snapshot` |
| Handle errors | `StorageError` (`name`), `StorageErrorCode` |
| Use multiple buckets | `Storage.storage("gs://other-bucket")` |
| Retry settings | `max_upload_retry_time`, `max_download_retry_time`, `max_operation_retry_time` |
| Connect to the emulator | `Storage.storage().use_emulator("127.0.0.1", 9199)` |

---

## Remote Config

```python
from pyios_firebase.remote_config import RemoteConfig

config = RemoteConfig.setup(defaults_plist="RemoteConfigDefaults", minimum_fetch_interval=3600)
config.get_string("welcome_message")
config.get_boolean("new_checkout")


def on_update(update, error):            # real-time: published values arrive within seconds
    if update is not None and "welcome_message" in update.updated_keys:
        config.activate(lambda changed, error: refresh_screen())


listener = config.add_on_config_update_listener(on_update)
```

| Guide page | In pyios-firebase |
|---|---|
| Get started: defaults | `setup(defaults=, defaults_plist=, defaults_file=)`, `set_defaults`, `set_defaults_from_plist`, `default_value` |
| Get values | `get_string`, `get_boolean`, `get_number`, `get_long`, `get_json`, `get_data`, `get_value(key, source=)` |
| Fetch and activate | `fetch_and_activate`, `fetch(expiration_duration=)`, `activate`, `ensure_initialized`, `last_fetch_time`, `last_fetch_status` |
| Throttling | `minimum_fetch_interval`, `fetch_timeout`, `RemoteConfigFetchStatus.THROTTLED` |
| Real-time updates | `add_on_config_update_listener` → `ConfigUpdate.updated_keys`; `.remove()` |
| Custom signal conditions | `set_custom_signals({...})` |
| Keys and sources | `all_keys(source)`, `keys_with_prefix`, `RemoteConfigSource` |
| A/B Testing, personalization, rollouts | Set up in the console; the app only reads values |

Remote Config has no emulator. Lower `minimum_fetch_interval` only while developing:
Firebase throttles apps that fetch too often.

---

## App Check

Choose the provider **before** `core.configure()`:

```python
from pyios_firebase import app_check, core

if app_check.running_in_simulator():
    app_check.use_debug_provider()       # prints a debug token to register in the console
else:
    app_check.use_app_attest_provider()  # or use_device_check_provider(), use_recaptcha_provider(key)
core.configure()
```

Firestore, Functions, Storage, Auth and Remote Config then send App Check tokens by
themselves. For your own backend:

```python
from pyios_firebase.app_check import AppCheck

AppCheck.app_check().token(lambda token, error: call_backend(token.token))
AppCheck.app_check().limited_use_token(on_token)         # for replay protection
listener = AppCheck.app_check().add_token_listener(lambda token: ...)
```

A custom provider, written in Python:

```python
from pyios_firebase.app_check import AppCheckProvider, AppCheckToken


class MyProvider(AppCheckProvider):
    def get_token(self, callback):
        my_attestation_service.fetch(
            lambda token, expires: callback(AppCheckToken(token, expires), None),
            lambda message: callback(None, message),
        )


app_check.use_custom_provider(MyProvider())
```

| Guide page | In pyios-firebase |
|---|---|
| Get started with App Attest / DeviceCheck | `use_app_attest_provider()`, `use_device_check_provider()` |
| reCAPTCHA Enterprise | `use_recaptcha_provider(site_key)` (needs the reCAPTCHA SDK) |
| Use the debug provider | `use_debug_provider()`, `AppCheck.debug_token()`; CI: the `FIRAAppCheckDebugToken` environment variable |
| Implement a custom provider | `AppCheckProvider` + `use_custom_provider(provider or factory)` |
| Protect your own backend | `AppCheck.token(...)`, `limited_use_token(...)`, `add_token_listener` |
| Replay protection | `limited_use_token`; Functions: `require_limited_use_app_check_tokens=True` |
| Token auto-refresh | `is_token_auto_refresh_enabled` |

Setting a provider after `core.configure()` raises `RuntimeError`: Firebase only
reads it when the app is configured. The emulators do not check App Check tokens.

---

## API reference

### Firestore

#### `Firestore`

| Method | Gives back | Notes |
|---|---|---|
| `Firestore.firestore()` | `Firestore` | The shared client |
| `collection_with_path(path)` | `CollectionReference` | |
| `document_with_path(path)` | `DocumentReference` | Full path, like `"cities/LA"` |
| `collection_group_with_id(id)` | `Query` | Pass only the collection name |
| `use_emulator(host="127.0.0.1", port=8080)` | nothing | Before any other call; development only |
| `batch()` | `WriteBatch` | |
| `run_transaction(update_fn, callback=None)` | nothing | Callback gets `(result, error)` |

#### `CollectionReference` (also a `Query`)

| Member | Notes |
|---|---|
| `collection_id`, `path`, `parent` | `parent` is a `DocumentReference` or `None` |
| `document_with_path(path)` | Short path, like `"LA"` |
| `document_with_auto_id()` | New reference with a generated ID. Nothing is saved |
| `add_document_with_data(data, callback=None)` | Callback gets `(document_reference, error)` |

#### `Query`

**Filters** (each gives a new `Query`):

- `query_where_field_is_equal_to(field, value)`
- `query_where_field_is_not_equal_to(field, value)`
- `query_where_field_is_less_than(field, value)`
- `query_where_field_is_less_than_or_equal_to(field, value)`
- `query_where_field_is_greater_than(field, value)`
- `query_where_field_is_greater_than_or_equal_to(field, value)`
- `query_where_field_array_contains(field, value)`
- `query_where_field_array_contains_any(field, values)`
- `query_where_field_in(field, values)`
- `query_where_field_not_in(field, values)`
- `query_where_filter(filter)`

**Order and limit** (each gives a new `Query`):

- `query_ordered_by_field(field, descending=False)`
- `query_limited_to(limit)`, `query_limited_to_last(limit)`
- `query_starting_at_values(values)`, `query_starting_after_values(values)`
- `query_ending_at_values(values)`, `query_ending_before_values(values)`
- `query_starting_at_document(snapshot)`, `query_starting_after_document(snapshot)`
- `query_ending_at_document(snapshot)`, `query_ending_before_document(snapshot)`

**Run the query:**

| Method | Callback |
|---|---|
| `get_documents(callback, source=None)` | `(QuerySnapshot, error)` |
| `add_snapshot_listener(callback, include_metadata_changes=False, options=None)` | `(QuerySnapshot, error)`, returns `ListenerRegistration` |

**Aggregates:** `count` (property) and `aggregate(fields)` give an `AggregateQuery`.

#### `QuerySnapshot`

- `documents`: list of `DocumentSnapshot` (also `len()`, `[i]`, `for ... in`)
- `document_changes`: list of `DocumentChange`
- `document_changes_with_include_metadata_changes(bool)`
- `is_empty`, `count`, `metadata`, `query`

#### `DocumentReference`

| Member | Notes |
|---|---|
| `document_id`, `path`, `parent`, `firestore` | `parent` is a `CollectionReference` |
| `collection_with_path(path)` | A sub collection |
| `get_document(callback, source=None)` | Callback gets `(DocumentSnapshot, error)` |
| `set_data(data, merge=False, callback=None)` | Callback gets `(error)` |
| `set_data_merge_fields(data, fields, callback=None)` | Callback gets `(error)` |
| `update_data(data, callback=None)` | The document must exist. Callback gets `(error)` |
| `delete_document(callback=None)` | Callback gets `(error)` |
| `add_snapshot_listener(callback, include_metadata_changes=False, options=None)` | Callback gets `(DocumentSnapshot, error)`. Returns `ListenerRegistration` |

#### `DocumentSnapshot`

- `document_id`, `exists`, `reference`, `metadata`
- `data`: a dict of Python values (`{}` if the document does not exist)
- `data_with_server_timestamp_behavior(behavior)`
- `get(field)` / `snapshot[field]`: one field, dotted names allowed

#### `DocumentChange`

- `type`: one of `DocumentChange.ADDED`, `DocumentChange.MODIFIED`, `DocumentChange.REMOVED`
- `document`: a `DocumentSnapshot`
- `old_index`, `new_index`

#### `ListenerRegistration` and `SnapshotListenOptions`

- `remove()`: stops the updates. It is safe to call twice.
- `SnapshotListenOptions(include_metadata_changes=False, source=None)`

#### `SnapshotMetadata`

- `is_from_cache`, `has_pending_writes`

#### `WriteBatch`

- `set_data(data, document, merge=False)`
- `set_data_merge_fields(data, document, fields)`
- `update_data(data, document)`
- `delete_document(document)`
- `commit(callback=None)`: callback gets `(error)`

All except `commit` give back the batch, so you can chain them.

#### `Transaction`

Given to your function inside `run_transaction`.

- `get_document(document)` gives a `DocumentSnapshot`
- `set_data(data, document, merge=False)`
- `update_data(data, document)`
- `delete_document(document)`

#### `FieldValue`

- `field_value_for_delete()`
- `field_value_for_server_timestamp()`
- `field_value_for_array_union(elements)`
- `field_value_for_array_remove(elements)`
- `field_value_for_integer_increment(value)`
- `field_value_for_double_increment(value)`

#### `Filter`

- `filter_where_field_is_equal_to(field, value)`
- `filter_where_field_is_not_equal_to(field, value)`
- `filter_where_field_is_less_than(field, value)`
- `filter_where_field_is_less_than_or_equal_to(field, value)`
- `filter_where_field_is_greater_than(field, value)`
- `filter_where_field_is_greater_than_or_equal_to(field, value)`
- `filter_where_field_array_contains(field, value)`
- `filter_where_field_array_contains_any(field, values)`
- `filter_where_field_in(field, values)`
- `filter_where_field_not_in(field, values)`
- `or_filter_with_filters(filters)`
- `and_filter_with_filters(filters)`

#### `AggregateField`, `AggregateQuery`, `AggregateQuerySnapshot`

- `AggregateField.aggregate_field_for_count()`
- `AggregateField.aggregate_field_for_sum_of_field(field)`
- `AggregateField.aggregate_field_for_average_of_field(field)`
- `AggregateQuery.aggregation_with_source(source, callback)`: callback gets `(snapshot, error)`
- `snapshot.count`: the count, as an `int`
- `snapshot.value_for_aggregate_field(field)`: an `int`, a `float`, or `None`

#### Enum values

Some Firebase names are fixed numbers in the compiled SDK, and Python cannot look
them up by name. They are kept in `pyios_firebase/firestore/enums.py`:

| Class | Values |
|---|---|
| `FIRFirestoreSource` | `Default`, `Server`, `Cache` |
| `FIRServerTimestampBehavior` | `None_`, `Estimate`, `Previous` |
| `FIRAggregateSource` | `Server` |
| `FIRListenSource` | `Default`, `Cache` |
| `FIRDocumentChangeType` | `Added`, `Modified`, `Removed` |

If you update the Firebase SDK, check these values in the SDK header files.

### Auth

#### `Auth`

| Member | Notes |
|---|---|
| `Auth.auth()` | The shared instance |
| `current_user` | A `User`, or `None` |
| `add_state_did_change_listener(listener)` / `add_id_token_did_change_listener(listener)` | `listener(user)`; returns an `AuthStateListener` (`.remove()`) |
| `sign_in_with_email_password(email, password, cb)` / `create_user_with_email_password(...)` | `cb(AuthDataResult, error)` |
| `sign_in_anonymously(cb)`, `sign_in_with_custom_token(token, cb)` | |
| `sign_in_with_credential(credential, cb)`, `sign_in_with_provider(OAuthProvider, cb)` | |
| `send_sign_in_link(email, settings, cb)`, `is_sign_in_with_email_link(link)`, `sign_in_with_email_link(email, link, cb)` | Passwordless |
| `send_password_reset(email, cb, settings)`, `verify_password_reset_code(code, cb)`, `confirm_password_reset(code, password, cb)` | |
| `check_action_code(code, cb)`, `apply_action_code(code, cb)` | `cb(ActionCodeInfo, error)` / `cb(error)` |
| `sign_out()`, `update_current_user(user, cb)`, `revoke_token(code, cb)` | |
| `get_stored_user(access_group)` | `(user, error)`: the user in a shared keychain |
| `use_emulator(host, port)`, `is_using_emulator`, `language_code`, `use_app_language()`, `tenant_id`, `app_verification_disabled_for_testing`, `use_user_access_group(group)` | Settings |
| `can_handle_url(url)`, `can_handle_notification(user_info)`, `set_apns_token(token, type)` | App delegate hooks (phone, OAuth) |

#### `User`

- Profile: `uid`, `email`, `display_name`, `phone_number`, `photo_url`, `provider_id`,
  `is_anonymous`, `is_email_verified`, `provider_data` (list of `UserInfo`),
  `metadata` (`UserMetadata`: `creation_date`, `last_sign_in_date`), `tenant_id`,
  `refresh_token`, `is_signed_in`
- Tokens: `get_id_token(cb, force_refresh=False)`, `get_id_token_result(cb, force_refresh=False)` → `IDTokenResult` (`token`, `claims`, `expiration_date`, `issued_at_date`, `auth_date`, `sign_in_provider`, `sign_in_second_factor`)
- Account: `reload`, `delete`, `update_password`, `update_email`, `update_profile(cb, *, display_name, photo_url)`, `update_phone_number`, `send_email_verification`, `send_email_verification_before_updating_email`
- Providers: `link_with_credential`, `link_with_provider`, `unlink`, `reauthenticate_with_credential`, `reauthenticate_with_provider`

#### Credentials and providers

| Provider | Make a credential |
|---|---|
| `EmailAuthProvider` | `credential(email, password)`, `credential_with_link(email, link)` |
| `GoogleAuthProvider` | `credential(id_token, access_token)` (or `auth.google`) |
| `OAuthProvider` | `OAuthProvider(id, scopes, custom_parameters)` for web flows; `credential(id, id_token, access_token, raw_nonce)`; `apple_credential(id_token, raw_nonce, given_name, family_name)` (or `auth.apple`) |
| `PhoneAuthProvider` | `verify_phone_number(number, cb)`, then `credential(verification_id, code)` |
| `FacebookAuthProvider` | `credential(access_token)` |
| `GitHubAuthProvider` | `credential(token)` |
| `TwitterAuthProvider` | `credential(token, secret)` |
| `GameCenterAuthProvider` | `get_credential(cb)` |

Each has a `PROVIDER_ID`. `AuthDataResult` has `user`, `additional_user_info`
(`provider_id`, `is_new_user`, `username`, `profile`) and `credential`.

#### Multi-factor

- `User.multi_factor` → `MultiFactor`: `enrolled_factors`, `get_session(cb)`, `enroll(assertion, display_name, cb)`, `unenroll(factor_or_uid, cb)`
- `MultiFactorInfo` (`uid`, `factor_id`, `display_name`, `enrollment_date`), `PhoneMultiFactorInfo` (+ `phone_number`)
- `PhoneMultiFactorGenerator.assertion(credential)`; `PhoneAuthProvider.verify_phone_number(..., multi_factor_session=)`, `verify_phone_number_for_sign_in(hint, session, cb)`
- `TOTPMultiFactorGenerator.generate_secret(session, cb)`, `assertion_for_enrollment(secret, code)`, `assertion_for_sign_in(enrollment_id, code)`; `TOTPSecret.shared_secret_key()`, `generate_qr_code_url(account, issuer)`, `open_in_otp_app(url)`
- `MultiFactorResolver` (from `AuthError.resolver`): `hints`, `session`, `resolve_sign_in(assertion, cb)`

#### Facebook (`pyios_firebase.auth.facebook`)

`initialize_facebook()`, `start_facebook_sign_in(cb, permissions, limited)`, `get_facebook_credential(cb, permissions, limited)`, `sign_out_of_facebook()`, `on_facebook_handle_url(url)`, `on_facebook_handle_url_kivy(...)`

#### Errors

`AuthError` (keys above, plus `resolver` for `SECOND_FACTOR_REQUIRED`) and `AuthErrorCode`: every `FIRAuthErrorCode` of the SDK,
by name (`EMAIL_ALREADY_IN_USE`, `WRONG_PASSWORD`, `REQUIRES_RECENT_LOGIN`,
`ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL`, ...).

### Functions

- `Functions.functions(region=None, custom_domain=None)`, `use_emulator(host, port)`
- `https_callable(name, require_limited_use_app_check_tokens=False)`, `https_callable_from_url(url, ...)`
- `HTTPSCallable.call(callback, data=None)`, `timeout_interval`
- `FunctionsError` (`code`, `name`, `description`, `details`), `FunctionsErrorCode`

### Storage

- `Storage.storage(url=None)`: `reference()`, `reference_with_path(path)`, `reference_for_url(url)`, `use_emulator(host, port)`, `max_upload_retry_time`, `max_download_retry_time`, `max_operation_retry_time`
- `StorageReference`: `full_path`, `name`, `bucket`, `gs_url`, `storage`, `root()`, `parent()`, `child(path)`; `put_data(data, content_type, callback, *, metadata)`, `put_file(path, ...)` → `StorageUploadTask`; `get_data(max_size, cb)`, `write_to_file(path, cb)` → `StorageDownloadTask`; `download_url(cb)`, `get_metadata(cb)`, `update_metadata(metadata, cb)`, `list_all(cb)`, `list(max_results, cb, page_token)`, `delete(cb)`
- `StorageMetadata(content_type, cache_control, content_disposition, content_encoding, content_language, custom_metadata)`; read-only `bucket`, `path`, `name`, `size`, `md5_hash`, `generation`, `metageneration`, `time_created`, `updated`, `is_file`, `gs_url`
- `StorageTask` (`StorageUploadTask`, `StorageDownloadTask`): `observe(status, handler)`, `remove_observer(handle)`, `pause()`, `resume()`, `cancel()`, `snapshot`
- `StorageTaskSnapshot`: `status`, `bytes_transferred`, `total_bytes`, `fraction_completed`, `metadata`, `error`, `reference`; `StorageTaskStatus`
- `StorageListResult` (`items`, `prefixes`, `page_token`), `StorageError` (`name`), `StorageErrorCode`

### Remote Config

- `RemoteConfig.remote_config()`, `RemoteConfig.setup(defaults, defaults_file, defaults_plist, minimum_fetch_interval, callback)`
- Settings: `minimum_fetch_interval`, `fetch_timeout`, `last_fetch_time`, `last_fetch_status`
- Defaults: `set_defaults(dict)`, `set_defaults_from_plist(name)`, `default_value(key)`, `load_defaults(path)`, `load_plist_defaults(name)`
- Fetch: `ensure_initialized(cb)`, `fetch(cb, expiration_duration)`, `activate(cb)`, `fetch_and_activate(cb)`
- Values: `get_value(key, source)` → `RemoteConfigValue` (`string`, `number`, `boolean`, `data`, `source`, `json()`); `get_string`, `get_boolean`, `get_number`, `get_long`, `get_data`, `get_json`; `all_keys(source)`, `keys_with_prefix(prefix)`
- Real-time: `add_on_config_update_listener(listener)` → `ConfigUpdateListener` (`remove()`); `ConfigUpdate.updated_keys`
- `set_custom_signals(signals, cb)`; `RemoteConfigSource`, `RemoteConfigFetchStatus`, `RemoteConfigErrorCode`

### App Check

- Providers (before `core.configure()`): `use_debug_provider()`, `use_device_check_provider()`, `use_app_attest_provider()`, `use_recaptcha_provider(site_key)`, `use_custom_provider(provider)`; `running_in_simulator()`; `initialize_debug_appcheck()` (0.1 name)
- `AppCheckProvider` (`get_token(callback)`, `get_limited_use_token(callback)`), `AppCheckToken(token, expiration_date)`
- `AppCheck.app_check()`: `token(cb, force_refresh)`, `limited_use_token(cb)`, `add_token_listener(listener)` → `AppCheckTokenListener`, `is_token_auto_refresh_enabled`, `debug_token()`
- `AppCheckErrorCode`, `DEBUG_TOKEN_ENVIRONMENT_VARIABLE`

---

## Good to know

- **Keep your listener.** Save the object that `add_snapshot_listener` gives back,
  and call `remove()` when you leave the screen. A listener keeps using the network
  and counts reads in your Firebase bill until you remove it.
- **Main thread.** If a callback changes widgets (for example, in Kivy) and you are
  not sure it runs on the main thread, use `Clock.schedule_once`:

  ```python
  from kivy.clock import Clock

  def on_cities(snapshot, error):
      Clock.schedule_once(lambda dt: update_screen(snapshot))
  ```
- **Blocks stay alive for you.** Every callback block is kept in memory until
  Firebase is done with it (listener blocks: until `remove()`). You do not need
  module-level variables.
- **Security rules.** If your Firestore rules need a signed-in user, call these
  methods only after sign-in works. Otherwise you get "permission denied".
- **Indexes.** Some queries need an index (many filters, or a filter plus an order
  on different fields, or collection group queries). The error message has a link
  to create it.
- **Reads cost money.** Reading a whole collection counts every document as a read.
  Use `query_limited_to` or an aggregate query when you can.
- **`update_data` needs an existing document.** To create it if it is missing, use
  `set_data`.
- **`set_data` replaces the whole document.** Old fields are lost, unless you pass
  `merge=True`.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| `NameError: ... FIRFirestore` (or another `FIR...` class) | That Firebase framework is not part of your iOS build |
| `Firebase sign-in error: An internal error has occurred` | Print `error.code`, `error.domain` and `error.underlying_error`. Common causes: missing Keychain Sharing, wrong `GoogleService-Info.plist`, sign-in provider not enabled, API key limits, App Check enforcement without a registered debug token |
| `permission denied` | Your Firestore rules need a signed-in user, or the rules do not allow this read or write |
| The app stops with "Please register custom URL scheme" | Phone or web sign-in without the callback URL scheme in `Info.plist`. Use pyios-firebase's methods: they give an `AuthError` naming the scheme instead |
| `NOT_FOUND` / `INVALID_CREDENTIAL` on sign-in with the emulator | The emulator starts empty each run: create the account first |
| `core.default_app()` is `None` | `core.configure()` was not called, or it was called too late |
| App Check blocks requests | Choose the provider **before** `core.configure()` (after it, the `use_*` functions raise `RuntimeError`), and register the debug token in the Firebase console |
| A function call fails with `INTERNAL` | The function threw an unexpected error: check its logs (the message is not sent to the app) |
| Storage `UNAUTHORIZED` / `UNAUTHENTICATED` | The Storage security rules do not allow it, or need a signed-in user |
| With the Storage emulator, `get_metadata` still finds a deleted file | The emulator sends the file's own `Cache-Control` on metadata responses, so iOS caches them. Use a non-cacheable `cache_control` (for example `"no-cache"`) on emulator test files |
| Remote Config values never change | `minimum_fetch_interval` (12 h by default) has not passed, or you fetched but did not `activate` |
| A query fails with an index error | Open the link in the error message and create the index |
| `snapshot.data` has odd types | Some Firestore values stay Objective-C objects (see [Python values and Firestore types](#python-values-and-firestore-types)). Open an issue and tell us the Rubicon version and what `type(...)` prints |

---

## Migrating

### From the flat 0.1 modules

Every product is now a subpackage:

| Before | Now |
|---|---|
| `pyios_firebase.firapp.configure()` | `pyios_firebase.core.configure()` |
| `pyios_firebase.firfirestore`, `firfieldvalue`, `firfilter` | `pyios_firebase.firestore` |
| `pyios_firebase.firuser.User` | `pyios_firebase.auth.User` (also `Auth.auth().current_user`) |
| `pyios_firebase.firgoogleauth` | `pyios_firebase.auth.google` |
| `pyios_firebase.firappcheck.initialize_debug_appcheck()` | `pyios_firebase.app_check.use_debug_provider()` (the old name still works) |

Auth changes:

- Sign-in callbacks get `(result, error)` like the rest of the library, instead
  of `(data, is_error)`: `result` is an `AuthDataResult` (`result.user.uid`), and
  `error` is an `AuthError` (still with `cancelled`).
- `User().uid`, `.email` and `.display_name` are `str` or `None` (not Objective-C
  strings); `User().user` and `User().auth` are still the native objects.
- Several sign-ins can run at once: each keeps its own callback.

Firestore changes:

- Reads give snapshots: `get_document` gives a `DocumentSnapshot`, and
  `get_documents` / query listeners give a `QuerySnapshot` (iterate it like the
  old list).
- `add_snapshot_listener_for_changes` is gone: use `snapshot.document_changes`.
- `DocumentReference.set_data(data, callback)` is now
  `set_data(data, merge=False, callback=None)`. The old `set_data(data, callback)` still works.
- `FIRAggregateSource` and the other enums are in `pyios_firebase.firestore`.
- Any exception raised in a transaction function now stops the transaction, and
  the callback gets the Python value you returned (not an Objective-C object).
- Errors also have a `domain` key.
- Booleans are now read as `True` / `False`. Before, they came back as `1` / `0`.
- `None` in data you write is stored as `null`. Before, it crashed the app.
- `datetime` values can be written and used in queries.
- Unsupported values raise `TypeError` in Python instead of failing inside the SDK.
- `snapshot.metadata.is_from_cache`, `snapshot.metadata.has_pending_writes` and
  `query_snapshot.is_empty` were always `True` (they read Objective-C custom
  getters without calling them). They now give the real value; code that relied
  on them, for example to skip pending local writes, behaves differently.

### From pyobjus-firebase

1. Install `pyios-firebase` and follow [Setup](#setup).
2. Replace the `pyobjus-firebase` imports in your code with the new ones.
3. Delete any `.m` or `.h` files you added only for `pyobjus-firebase`.
4. If something does not work, open an issue in this repository.

---

## Development

```bash
uv sync --group dev
uv run pytest      # tests
uv run mypy        # strict type check of the package and of tests/typing
uv run pyright     # the checker behind VS Code's Pylance
uv run ruff check
```

### End-to-end tests on the iOS Simulator

```bash
e2e/run_ios_e2e.sh
```

This builds a small Kivy app (`e2e/ios/`) with the wheel from your checkout and
the real Firebase iOS SDK, runs it in the iOS Simulator against the local
Firestore, Auth, Functions and Storage emulators, and exits non-zero if any test
fails.

- Firestore: every value type, writes and field values, merges, queries and
  cursors, OR/AND filters, collection groups, aggregates, listeners and their
  change types, batches, transactions, and read sources.
- Auth: email/password, errors and their codes, state and ID token listeners,
  anonymous upgrade, linking and unlinking a provider, custom tokens and claims,
  phone sign-in, profile and tokens, re-authentication, password change and
  account deletion, password reset, email verification, email link sign-in,
  SMS multi-factor enrollment and sign-in, passing state in email links, the
  shared keychain, OAuth providers, and the Facebook SDK bridge. The emails and
  SMS codes are read from the Auth emulator's REST API. TOTP is skipped: the Auth
  emulator supports only SMS second factors.
- Functions: JSON round trip, `HttpsError` codes and details, unexpected errors,
  unknown functions, timeouts, the Auth context, regions, calls by URL, App
  Check tokens (normal and limited-use), and non-JSON data. The functions are
  Python Cloud Functions (`firebase_functions`) in `e2e/functions/main.py`.
- Storage: references, upload with metadata, metadata update and delete, download
  URL, download to memory and to a file, file upload, listing and paging, upload
  progress, cancel, and errors.
- Remote Config (no emulator exists): plist defaults, values and their sources,
  merged defaults, settings, a fetch failing cleanly offline, custom signals and
  the update listener.
- App Check: a Python custom provider serving the whole app, tokens and
  limited-use tokens, the token listener, settings, and the debug token from
  `FIRAAppCheckDebugToken`.

It needs Xcode with an iOS simulator, [uv](https://docs.astral.sh/uv/),
`firebase-tools` and Java 21+ for the emulators. The first run creates a Python
3.13 venv for the e2e functions with uv. It
uses the offline `demo-pyios-firebase` project: no Firebase account or
credentials. `E2E_DEVICE` picks the simulator (default `iPhone 17`). The first
build takes a few minutes; results, the app log and a screenshot land in
`e2e/ios/build/e2e/`.

Unit tests run fake Firebase objects; the end-to-end suite is what catches
mismatches with the real SDK. It found bugs the unit tests could not: Objective-C
getters Rubicon exposes as methods (`is_from_cache`, `NSDate` values), TLS left on
for the Firestore emulator, and the SDK stopping the app for a missing URL scheme.

`tests/test_docs.py` fails if a public function or method has a parameter its
`Args:` docs do not describe (or describes one it does not have).

`tests/typing/check_public_api.py` is type-checked, never run: it uses the
public API the way an app does, asserts what the checker infers, and lists
mistakes the types must keep catching.

The tests run on macOS: Rubicon works there, and fake Firebase objects call
the real callback blocks. They check callbacks, errors, block lifetimes,
transactions, and value conversion. They do not replace testing on a device
with the real Firebase SDK.

---

## Licenses

`pyios-firebase` is licensed under the MIT License (see `LICENSE`).

It depends on [Rubicon-ObjC](https://github.com/beeware/rubicon-objc) (BSD 3-Clause).
The Firebase iOS SDK and Google Sign-In have their own licenses, and they apply
when you add those frameworks to your app.

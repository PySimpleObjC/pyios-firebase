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
9. [API reference](#api-reference)
10. [Good to know](#good-to-know)
11. [Troubleshooting](#troubleshooting)
12. [Migrating](#migrating)
13. [Development](#development)
14. [Licenses](#licenses)

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
- **App Check** debug provider and **Google Sign-In**: still the 0.1 modules
  (`firappcheck`, `firgoogleauth`, `firuser`); they move to their own
  subpackages in a later release
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
  | `firappcheck` | `FirebaseAppCheck` |
  | `firuser`, `firgoogleauth` | `FirebaseAuth` (+ `GoogleSignIn` for `firgoogleauth`) |

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
├── firappcheck.py       initialize_debug_appcheck()          (0.1 module)
├── firuser.py           User                                 (0.1 module)
└── firgoogleauth.py     start_google_sign_in()               (0.1 module)
```

Import from the subpackage:

```python
from pyios_firebase import core
from pyios_firebase.firestore import Firestore, FieldValue, Filter
```

In `core` and `firestore`, Objective-C classes are looked up the first time
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

### 4. (Optional) App Check debug provider

For testing, you can use the App Check debug provider. It must be set **before**
`core.configure()`:

```python
from pyios_firebase import core, firappcheck

firappcheck.initialize_debug_appcheck()
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
from pyios_firebase import firgoogleauth

Window.bind(on_drop_file=firgoogleauth.on_gid_signin_handle_url_kivy)
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
| `core.default_app()` is `None` | `core.configure()` was not called, or it was called too late |
| App Check blocks requests | Call `initialize_debug_appcheck()` **before** `core.configure()`, and add the debug token in the Firebase console |
| A query fails with an index error | Open the link in the error message and create the index |
| `snapshot.data` has odd types | Some Firestore values stay Objective-C objects (see [Python values and Firestore types](#python-values-and-firestore-types)). Open an issue and tell us the Rubicon version and what `type(...)` prints |

---

## Migrating

### From the flat 0.1 modules

Firebase Core and Firestore are now subpackages:

| Before | Now |
|---|---|
| `pyios_firebase.firapp.configure()` | `pyios_firebase.core.configure()` |
| `pyios_firebase.firfirestore`, `firfieldvalue`, `firfilter` | `pyios_firebase.firestore` |
| `pyios_firebase.firappcheck`, `firuser`, `firgoogleauth` | unchanged in this release |

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
Firestore emulator, and exits non-zero if any test fails. It covers every value
type, writes and field values, merges, queries and cursors, OR/AND filters,
collection groups, aggregates, listeners and their change types, batches,
transactions, and read sources.

It needs Xcode with an iOS simulator, [uv](https://docs.astral.sh/uv/),
`firebase-tools` (`npm i -g firebase-tools`) and Java 21+ for the emulator. It
uses the offline `demo-pyios-firebase` project: no Firebase account or
credentials. `E2E_DEVICE` picks the simulator (default `iPhone 17`). The first
build takes a few minutes; results, the app log and a screenshot land in
`e2e/ios/build/e2e/`.

Unit tests run fake Firebase objects; the end-to-end suite is what catches
mismatches with the real SDK. It found three bugs the unit tests could not.

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

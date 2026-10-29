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
4. [Setup](#setup)
5. [Quick start](#quick-start)
6. [How callbacks work](#how-callbacks-work)
7. [Usage guide](#usage-guide)
8. [API reference](#api-reference)
9. [Good to know](#good-to-know)
10. [Troubleshooting](#troubleshooting)
11. [Migrating from pyobjus-firebase](#migrating-from-pyobjus-firebase)
12. [Licenses](#licenses)

---

## Features

- **Cloud Firestore**
  - Add, get, set, update, and delete documents
  - Queries: filters, ordering, limits, start and end points, paging
  - OR and AND filters
  - Collection group queries
  - Live updates with snapshot listeners (full list or only the changes)
  - Count, sum, and average queries
  - Write batches
  - Transactions
  - Field values: delete, server timestamp, array union, array remove, increment
- Pure Python. No `.m` or `.h` files.
- Blocks (callbacks) are kept alive for you, so they are not deleted too early.

---

## Requirements

- iOS app built with Python (BeeWare, Kivy, or similar)
- [`rubicon-objc`](https://github.com/beeware/rubicon-objc)
- The Firebase iOS SDK frameworks added to your iOS build:
  - `FirebaseCore`
  - `FirebaseFirestore`
  - `FirebaseAuth` (if you use sign-in)
  - `FirebaseAppCheck` (if you use App Check)
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

## Setup

### 1. Add `GoogleService-Info.plist`

Download it from the Firebase console (Project settings, then your iOS app) and add
it to your app. Its `BUNDLE_ID` must match your app's bundle ID exactly.

### 2. Add the Firebase frameworks

Add the Firebase iOS SDK to your Xcode project (Swift Package Manager or CocoaPods).
Make sure the frameworks listed in [Requirements](#requirements) are linked.

If you see `class not found` errors later, a framework is missing from the build.

### 3. Start Firebase

Call this once, when the app starts, before you use any Firebase feature:

```python
from pyros_firebase import firapp

firapp.configure()
```

### 4. (Optional) App Check debug provider

For testing, you can use the App Check debug provider. It must be set **before**
`firapp.configure()`:

```python
from pyios_firebase import firapp, firappcheck

firappcheck.initialize_debug_appcheck()
firapp.configure()
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

If you are building with `[kivyforge](https://github.com/ElliotGarbus/kivyforge)`
```toml
[[tool.kivy.ios.include_files]]
dest = "."
sources = ["GoogleService-Info.plist"]

[tool.kivy.ios.native.swift_packages.Firebase]
url = "https://github.com/firebase/firebase-ios-sdk.git"
requirement = { from = "13.1.1" } # or latest version
products = ["FirebaseAuth", "FirebaseAnalytics", "FirebaseAppCheck", "FirebaseFirestore"]

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
---

## Quick start

```python
from pyios_firebase.firfirestore import Firestore

db = Firestore()


def on_saved(error):
    if error:
        print("Error writing document:", error)
    else:
        print("Document successfully written!")


db.collection_with_path("cities").document_with_path("LA").set_data(
    {"name": "Los Angeles", "state": "CA", "country": "USA"},
    on_saved,
)
```

> The import path above is an example. Use the real module name of the package.

---

## How callbacks work

Firebase calls your code later, when the server answers. So most methods take a
**callback**: a normal Python function.

| Kind of method | Callback arguments |
|---|---|
| Write methods (`set_data`, `update_data`, `delete_document`, `commit`) | `(error)` |
| Methods that give back one result (`add_document_with_data`, `get_document`) | `(doc, error)` |
| Methods that give back many results (`get_documents`, `add_snapshot_listener`) | `(docs, error)` |
| `add_snapshot_listener_for_changes` | `(changes, error)` |
| Aggregate queries | `(snapshot, error)` |
| `run_transaction` | `(result, error)` |

The rules are always the same:

- `error` is `None` when it worked. Otherwise it is the error text (a string).
- When there is an error, the result is `None`.
- For write methods, the callback is optional.

Example:

```python
def on_cities(docs, error):
    if error:
        print("Error getting documents:", error)
        return
    for doc in docs:
        print(doc.document_id, "=>", doc.data)
```

---

## Usage guide

### Add a document with a generated ID

```python
def on_added(doc, error):
    if error:
        print("Error adding document:", error)
    else:
        print("Document added with ID:", doc.document_id)


db.collection_with_path("users").add_document_with_data(
    {"first": "Ada", "last": "Lovelace", "born": 1815},
    on_added,
)
```

### Set, update, and delete a document

```python
doc = db.collection_with_path("cities").document_with_path("DC")

doc.set_data({"name": "Washington", "capital": False}, on_done)   # replaces everything
doc.update_data({"capital": True}, on_done)                       # changes only these fields
doc.delete_document(on_done)
```

You can also use the full path from the database:

```python
db.document_with_path("cities/DC").update_data({"capital": True}, on_done)
```

### Read one document

```python
def on_city(doc, error):
    if error:
        print("Error getting document:", error)
        return
    if doc.exists:
        print("Document data:", doc.data)
    else:
        print("Document does not exist")


db.collection_with_path("cities").document_with_path("SF").get_document(on_city)
```

### Read many documents

```python
# All documents in a collection
db.collection_with_path("cities").get_documents(on_cities)

# Only some of them
db.collection_with_path("cities") \
    .query_where_field_is_equal_to("capital", True) \
    .get_documents(on_cities)
```

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
from pyios_firebase.firfilter import Filter

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

`last_doc` must come from a callback (for example, the last item of `docs`),
because it needs the data that was loaded.

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
# One document
listener = db.collection_with_path("cities").document_with_path("SF") \
    .add_snapshot_listener(on_city_changed)

# A query or a whole collection
listener = db.collection_with_path("cities") \
    .query_where_field_is_equal_to("state", "CA") \
    .add_snapshot_listener(on_cities_changed)

# Stop listening
listener.remove()
```

The callback runs once at the start, and then again every time the data changes.
Each call gives the **full** current list.

To get **only what changed**, use `add_snapshot_listener_for_changes`:

```python
from pyios_firebase.firfirestore import DocumentChange


def on_changes(changes, error):
    if error:
        print("Error fetching documents:", error)
        return
    for diff in changes:
        if diff.type == DocumentChange.ADDED:
            print("New city:", diff.document.data)
        if diff.type == DocumentChange.MODIFIED:
            print("Modified city:", diff.document.data)
        if diff.type == DocumentChange.REMOVED:
            print("Removed city:", diff.document.data)


listener = db.collection_with_path("cities") \
    .query_where_field_is_equal_to("state", "CA") \
    .add_snapshot_listener_for_changes(on_changes)
```

### Field values

```python
from pyios_firebase.firfieldvalue import FieldValue

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
sf_reference = db.collection_with_path("cities").document_with_path("SF")


def update_population(transaction):
    sf_document = transaction.get_document(sf_reference)
    population = sf_document.data.get("population")
    if not isinstance(population, (int, float)):
        raise ValueError("Unable to retreive population from snapshot")

    population = int(population) + 1
    if population >= 1000000:
        raise ValueError("Population too big")

    transaction.update_data({"population": population}, sf_reference)
    return population   # passed out to the callback


def on_transaction_done(result, error):
    if error:
        print("Transaction failed:", error)
    else:
        print("Population increased to", result)


db.run_transaction(update_population, on_transaction_done)
```

Important rules:

- Raise a Python error to fail the transaction.
- The function can run **more than once**, so only read and write data inside it.
  Do not print, change the screen, or change your app's state there.
- Pass what you need **out** of the transaction by returning it.

### Count, sum, and average

```python
from pyios_firebase.firfirestore import AggregateField, FIRAggregateSource

# Count only
def on_count(snapshot, error):
    if error:
        print("Error fetching count:", error)
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
        print("Error fetching aggregate:", error)
        return
    print("Count:", snapshot.value_for_aggregate_field(count_field))
    print("Sum:", snapshot.value_for_aggregate_field(sum_field))
    print("Avg:", snapshot.value_for_aggregate_field(avg_field))


db.collection_with_path("cities") \
    .aggregate([count_field, sum_field, avg_field]) \
    .aggregation_with_source(FIRAggregateSource.Server, on_stats)
```

These are calculated on the server. They do not download the documents.

---

## API reference

### `Firestore`

| Method | Gives back | Notes |
|---|---|---|
| `collection_with_path(path)` | `CollectionReference` | |
| `document_with_path(path)` | `DocumentReference` | Full path, like `"cities/LA"` |
| `collection_group_with_id(id)` | `Query` | Pass only the collection name |
| `batch()` | `WriteBatch` | |
| `run_transaction(update_fn, callback=None)` | nothing | Callback gets `(result, error)` |

### `CollectionReference` (also a `Query`)

| Method | Callback | Notes |
|---|---|---|
| `add_document_with_data(data, callback=None)` | `(doc, error)` | Creates a document with a generated ID |
| `document_with_path(path)` | | Short path, like `"LA"` |

It also has every method of `Query`.

### `Query`

**Filters** (each gives a new `Query`):

- `query_where_field_is_equal_to(field, value)`
- `query_where_field_is_not_equal_to(field, value)`
- `query_where_field_is_less_than(field, value)`
- `query_where_field_is_less_than_or_equal_to(field, value)`
- `query_where_field_is_greater_than(field, value)`
- `query_where_field_is_greater_than_or_equal_to(field, value)`
- `query_where_field_array_contains(field, value)`
- `query_where_field_in(field, values)`
- `query_where_field_not_in(field, values)`
- `query_where_filter(filter)`

**Order and limit** (each gives a new `Query`):

- `query_ordered_by_field(field, descending=False)`
- `query_limited_to(limit)`
- `query_starting_at_values(values)`, `query_starting_after_values(values)`
- `query_ending_at_values(values)`, `query_ending_before_values(values)`
- `query_starting_at_document(doc)`, `query_starting_after_document(doc)`
- `query_ending_at_document(doc)`, `query_ending_before_document(doc)`

**Run the query:**

| Method | Callback |
|---|---|
| `get_documents(callback)` | `(docs, error)` |
| `add_snapshot_listener(callback)` | `(docs, error)`, returns `ListenerRegistration` |
| `add_snapshot_listener_for_changes(callback)` | `(changes, error)`, returns `ListenerRegistration` |

**Aggregates:**

- `count` (property) gives an `AggregateQuery`
- `aggregate(fields)` gives an `AggregateQuery`

### `DocumentReference`

| Member | Notes |
|---|---|
| `document_id` | The ID of the document |
| `exists` | `True` or `False`. `None` if no data was loaded |
| `data` | A dict. `None` if no data was loaded, or the document has no fields |
| `get_document(callback)` | Callback gets `(doc, error)` |
| `set_data(data, callback=None)` | Replaces the whole document. Callback gets `(error)` |
| `update_data(data, callback=None)` | Changes only the given fields. The document must exist. Callback gets `(error)` |
| `delete_document(callback=None)` | Callback gets `(error)` |
| `add_snapshot_listener(callback)` | Callback gets `(doc, error)`. Returns `ListenerRegistration` |

### `ListenerRegistration`

- `remove()`: stops the updates. It is safe to call twice.

### `DocumentChange`

- `type`: one of `DocumentChange.ADDED`, `DocumentChange.MODIFIED`, `DocumentChange.REMOVED`
- `document`: a `DocumentReference` with the data

### `WriteBatch`

- `set_data(data, document, merge=False)`
- `set_data_merge_fields(data, document, fields)`
- `update_data(data, document)`
- `delete_document(document)`
- `commit(callback=None)`: callback gets `(error)`

All except `commit` give back the batch, so you can chain them.

### `Transaction`

Given to your function inside `run_transaction`.

- `get_document(document)` gives a `DocumentReference` with the data
- `update_data(data, document)`

### `FieldValue`

- `field_value_for_delete()`
- `field_value_for_server_timestamp()`
- `field_value_for_array_union(elements)`
- `field_value_for_array_remove(elements)`
- `field_value_for_integer_increment(value)`
- `field_value_for_double_increment(value)`

### `Filter`

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

### `AggregateField`

- `aggregate_field_for_count()`
- `aggregate_field_for_sum_of_field(field)`
- `aggregate_field_for_average_of_field(field)`

### `AggregateQuery` and `AggregateQuerySnapshot`

- `AggregateQuery.aggregation_with_source(source, callback)`: callback gets `(snapshot, error)`
- `snapshot.count`: the count, as an `int`
- `snapshot.value_for_aggregate_field(field)`: an `int`, a `float`, or `None`

### Enum values

Some Firebase names are fixed numbers in the compiled SDK, and Python cannot look
them up by name. This project keeps them in one place:

```python
class FIRAggregateSource:
    Server = 0
```

If you update the Firebase SDK, check these values in the SDK header files
(`FIRDocumentChange.h` and `FIRAggregateSource.h`).

---

## Good to know

- **Keep your listener.** Save the object that `add_snapshot_listener` gives back,
  and call `remove()` when you leave the screen. A listener keeps using the network
  and counts reads in your Firebase bill until you remove it.
- **Main thread.** Callbacks may not run on the main thread. If you change widgets
  (for example, in Kivy), use `Clock.schedule_once`:

  ```python
  from kivy.clock import Clock

  def on_cities(docs, error):
      Clock.schedule_once(lambda dt: update_screen(docs))
  ```
- **Blocks stay alive for you.** The wrapper keeps each callback block in memory
  until Firebase is done with it. You do not need module-level variables.
- **Security rules.** If your Firestore rules need a signed-in user, call these
  methods only after sign-in works. Otherwise you get "permission denied".
- **Indexes.** Some queries need an index (many filters, or a filter plus an order
  on different fields, or collection group queries). The error message has a link
  to create it.
- **Reads cost money.** Reading a whole collection counts every document as a read.
  Use `query_limited_to` or an aggregate query when you can.
- **`update_data` needs an existing document.** To create it if it is missing, use
  `set_data`.
- **`set_data` replaces the whole document.** Old fields are lost.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| `class not found` (for example `FIRFirestore`) | The Firebase framework is not part of your iOS build |
| `Firebase sign-in error: An internal error has occurred` | Print `error.code`, `error.userInfo`, and the underlying error. Common causes: missing Keychain Sharing, wrong `GoogleService-Info.plist`, Google sign-in not enabled, API key limits, App Check enforcement without a registered debug token |
| `permission denied` | Your Firestore rules need a signed-in user, or the rules do not allow this read or write |
| `FIRApp.defaultApp` is `None` | `FIRApp.configure()` was not called, or it was called too late |
| App Check blocks requests | Set the provider factory **before** `FIRApp.configure()`, and add the debug token in the Firebase console |
| The app crashes when a callback runs | The callback block was deleted too early. Use the wrapper methods, or keep your own blocks in a module-level variable |
| A query fails with an index error | Open the link in the error message and create the index |
| `document.data` has odd types | Values from Firestore may be Objective-C objects. Open an issue and tell us the Rubicon version and what `type(...)` prints |

---

## Migrating from pyobjus-firebase

1. Install `pyios-firebase` and follow [Setup](#setup).
2. Replace the `pyobjus-firebase` imports in your code with the new ones.
3. Delete any `.m` or `.h` files you added only for `pyobjus-firebase`.
4. If something does not work, open an issue in this repository.

---

## Licenses

`pyios-firebase` is licensed under the MIT License (see `LICENSE`).

It depends on [Rubicon-ObjC](https://github.com/beeware/rubicon-objc) (BSD 3-Clause).
The Firebase iOS SDK and Google Sign-In have their own licenses, and they apply
when you add those frameworks to your app.

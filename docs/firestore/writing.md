# Writing data

Every write takes an optional callback, `(error)`, called when the **server**
has the write. Locally the write applies at once: listeners see it straight
away, and it is sent when the device is online.

```python
def on_done(error):
    if error is not None:
        print("Write failed:", error.description)
```

## Add a document with a generated ID

```python
def on_added(ref, error):
    if error is None:
        print("Added with ID", ref.document_id)


db.collection_with_path("users").add_document_with_data(
    {"first": "Ada", "last": "Lovelace", "born": 1815},
    on_added,
)
```

`add_document_with_data` also returns the `DocumentReference` at once, before
the server answers. To know the ID before writing (for example to store it
in the document itself), make the reference first:

```python
ref = db.collection_with_path("users").document_with_auto_id()
ref.set_data({"id": ref.document_id, "first": "Ada"})
```

Generated IDs are random, not ordered by time: to sort by creation, store a
timestamp field.

## Set a document

`set_data` creates the document, or **replaces all of it**:

```python
city = db.collection_with_path("cities").document_with_path("LA")

city.set_data({"name": "Los Angeles", "state": "CA", "country": "USA"}, callback=on_done)
```

### Merge into a document

Keep the fields you do not write, and create the document if it is missing:

```python
city.set_data({"capital": False}, merge=True, callback=on_done)
```

Or write only some fields of the data you pass:

```python
city.set_data_merge_fields(
    {"name": "LA", "population": 3_800_000, "ignored": "not written"},
    ["name", "population"],
    on_done,
)
```

## Update fields

`update_data` changes only the given fields. The document **must exist**
(otherwise the error is `NOT_FOUND`):

```python
city.update_data({"population": 3_900_000}, on_done)
```

Use dots for nested fields, so the other fields of the map stay:

```python
db.document_with_path("users/ada").update_data({
    "address.city": "London",          # only this key of "address"
    "settings.theme": "dark",
})
```

| Method | Document missing | Other fields |
|---|---|---|
| `set_data(data)` | Created | **Removed** |
| `set_data(data, merge=True)` | Created | Kept |
| `set_data_merge_fields(data, fields)` | Created | Kept |
| `update_data(data)` | Error `NOT_FOUND` | Kept |

## Field values

`FieldValue` sentinels ask the server to change a field from its current value,
without reading it first:

```python
from pyios_firebase.firestore import FieldValue

city = db.document_with_path("cities/DC")

city.update_data({
    "regions": FieldValue.field_value_for_array_union(["greater_virginia"]),   # add if missing
    "tags": FieldValue.field_value_for_array_remove(["old"]),                  # remove every "old"
    "population": FieldValue.field_value_for_integer_increment(1),             # atomic +1
    "rating": FieldValue.field_value_for_double_increment(0.5),
    "updated_at": FieldValue.field_value_for_server_timestamp(),               # the server's time
    "legacy_field": FieldValue.field_value_for_delete(),                       # remove the field
})
```

| Field value | Effect |
|---|---|
| `field_value_for_server_timestamp()` | The server's time when it applies the write |
| `field_value_for_delete()` | Removes the field (`update_data`, or `set_data` with `merge=True`) |
| `field_value_for_integer_increment(n)` / `field_value_for_double_increment(x)` | Adds to the number (a missing field counts as 0) |
| `field_value_for_array_union([...])` | Adds the values that are not in the array yet |
| `field_value_for_array_remove([...])` | Removes every copy of the values |

Increments are atomic, so many clients can add to a counter at once. A single
document takes about one sustained write per second: for busy counters, spread
them over several documents ([distributed counters](https://firebase.google.com/docs/firestore/solutions/counters)).

## Delete

```python
db.document_with_path("cities/DC").delete_document(on_done)
```

Deleting a document **does not delete its sub-collections**: their documents
stay, at the same paths. Delete them one by one, or from a server (the Firebase
CLI, or a Cloud Function).

Deleting a field: `update_data({"field": FieldValue.field_value_for_delete()})`.

## Write several documents at once

To write several documents **atomically** (all or nothing), use a
[batch](transactions.md#write-batches). To write from the current value, use a
[transaction](transactions.md#transactions).

## Data that cannot be stored

Values Firestore cannot store raise `TypeError` before anything is sent; see
[Python values](data-types.md#values-firestore-cannot-store).

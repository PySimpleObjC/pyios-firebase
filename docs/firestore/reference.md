# Firestore reference

## At a glance

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

## `pyios_firebase.firestore`

::: pyios_firebase.firestore

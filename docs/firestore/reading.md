# Reading and querying

There are two ways to read:

- **once**: `get_document` / `get_documents`, on this page;
- **live**: `add_snapshot_listener`, called again on every change
  ([Realtime updates](listeners.md)).

## Read one document

```python
def on_city(snapshot, error):
    if error is not None:
        print("Read failed:", error.description)
        return
    if snapshot.exists:
        print(snapshot.document_id, snapshot.data)
        print(snapshot.get("name"), snapshot["address.city"])
    else:
        print("No such document")


db.document_with_path("cities/SF").get_document(on_city)
```

A missing document is **not** an error: `snapshot.exists` is `False` and
`snapshot.data` is `{}`.

### From the cache or the server

```python
from pyios_firebase.firestore import FIRFirestoreSource

doc.get_document(on_city, source=FIRFirestoreSource.Cache)    # only the device's cache
doc.get_document(on_city, source=FIRFirestoreSource.Server)   # only the server (fails offline)
```

`Default` (the default) asks the server, and falls back to the cache when
offline. `snapshot.metadata.is_from_cache` tells which one answered.

## Read many documents

```python
def on_cities(snapshot, error):
    if error is not None:
        return
    print(len(snapshot), "cities")
    for doc in snapshot:
        print(doc.document_id, doc.data)


db.collection_with_path("cities").get_documents(on_cities)
```

A `QuerySnapshot` works like a list of `DocumentSnapshot`: `len(snapshot)`,
`snapshot[0]`, `snapshot[-1]`, `for doc in snapshot`. It also has `is_empty`,
`documents`, `document_changes`, `metadata` and `query`.

!!! warning "Every document is a read"
    Reading a whole collection counts each of its documents on your bill. Filter
    and limit, or count on the server with [aggregation](aggregation.md).

## Filters

Each method returns a **new** query, so you can chain them:

```python
cities = db.collection_with_path("cities")

cities.query_where_field_is_equal_to("state", "CA")
cities.query_where_field_is_not_equal_to("country", "USA")
cities.query_where_field_is_less_than("population", 100_000)
cities.query_where_field_is_greater_than_or_equal_to("population", 1_000_000)
cities.query_where_field_array_contains("regions", "west_coast")
cities.query_where_field_array_contains_any("regions", ["west_coast", "east_coast"])
cities.query_where_field_in("country", ["USA", "Japan"])
cities.query_where_field_not_in("country", ["USA", "Japan"])
```

| Method | Matches documents where the field... |
|---|---|
| `query_where_field_is_equal_to` / `is_not_equal_to` | is (not) equal to the value |
| `query_where_field_is_less_than` / `..._or_equal_to` | is smaller |
| `query_where_field_is_greater_than` / `..._or_equal_to` | is bigger |
| `query_where_field_array_contains` | is an array holding the value |
| `query_where_field_array_contains_any` | is an array holding any of the values (up to 30) |
| `query_where_field_in` | is one of the values (up to 30) |
| `query_where_field_not_in` | is none of the values (up to 10) |

An empty list, a list with more values than the limit, or a `str` instead of a
list raises `ValueError` / `TypeError` before the query is made. The SDK would
abort the app on an empty list, and the server would reject a long one.

Several filters are joined with **AND**. Filter values are converted like any
value: compare timestamps with a `datetime`, references with a
`DocumentReference`.

### OR and AND filters

```python
from pyios_firebase.firestore import Filter

cities.query_where_filter(
    Filter.or_filter_with_filters([
        Filter.filter_where_field_is_equal_to("capital", True),
        Filter.filter_where_field_is_greater_than_or_equal_to("population", 1_000_000),
    ])
).get_documents(on_cities)
```

Filters nest: an `and_filter_with_filters` inside an `or_filter_with_filters`,
and the other way round.

## Order and limit

```python
cities \
    .query_where_field_is_equal_to("state", "CA") \
    .query_ordered_by_field("population", descending=True) \
    .query_limited_to(10) \
    .get_documents(on_cities)

# the last 3, in the query's order
cities.query_ordered_by_field("name").query_limited_to_last(3)
```

- Ordering by a field leaves out the documents that do not have it.
- A range filter (`<`, `>`, `!=`, `not-in`) and an order on a different field
  need a [composite index](https://firebase.google.com/docs/firestore/query-data/indexing).
  The query fails with `FAILED_PRECONDITION`, and the error's description
  holds a link that creates the index in the console.

## Paging with cursors

Start or end at values of the ordered fields...

```python
cities.query_ordered_by_field("population") \
    .query_starting_at_values([1_000_000]) \
    .query_ending_before_values([5_000_000])
```

...or at a document you read, which is how pages work:

```python
class CityPages:
    PAGE = 25

    def __init__(self, db):
        self.query = db.collection_with_path("cities").query_ordered_by_field("population")
        self.last = None

    def next_page(self, on_page):
        query = self.query.query_limited_to(self.PAGE)
        if self.last is not None:
            query = query.query_starting_after_document(self.last)

        def on_snapshot(snapshot, error):
            if error is None and not snapshot.is_empty:
                self.last = snapshot[-1]          # the cursor for the next page
            on_page(snapshot, error)

        query.get_documents(on_snapshot)
```

| Cursor | Includes the cursor? |
|---|---|
| `query_starting_at_values` / `query_starting_at_document` | Yes |
| `query_starting_after_values` / `query_starting_after_document` | No |
| `query_ending_at_values` / `query_ending_at_document` | Yes |
| `query_ending_before_values` / `query_ending_before_document` | No |

A document cursor must be a `DocumentSnapshot` from a callback: it carries the
values of the ordered fields.

## Collection group queries

Query every collection with the same ID, wherever it is in the database:

```python
db.collection_group_with_id("landmarks") \
    .query_where_field_is_equal_to("type", "museum") \
    .get_documents(on_museums)
```

Pass only the collection ID, not a path. Collection group queries with
filters need an index, and the security rules must allow them
(`match /{path=**}/landmarks/{id}`).

## Sub-collections

```python
landmarks = db.collection_with_path("cities/SF/landmarks")
# the same:
landmarks = db.document_with_path("cities/SF").collection_with_path("landmarks")

landmarks.get_documents(on_landmarks)
```

Reading a document does **not** read its sub-collections.

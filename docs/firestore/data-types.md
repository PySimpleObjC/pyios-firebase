# Python values

You write and read plain Python values. They are converted for you everywhere
a value goes in or comes out: `set_data`, `update_data`,
`add_document_with_data`, batches, transactions, query filters and cursors,
`Filter`, array `FieldValue`s, `snapshot.data` and `snapshot.get(...)`.
Nested dicts and lists are converted too.

| Python | Firestore | Read back as |
|---|---|---|
| `str` | string | `str` |
| `int` | integer (64-bit) | `int` |
| `float` | double | `float` |
| `bool` | boolean | `bool` (never `1` / `0`) |
| `None` | null | `None` |
| `datetime` | timestamp | `datetime`, timezone-aware, in UTC |
| `bytes` | bytes | `bytes` |
| `dict` (`str` keys) | map | `dict` |
| `list`, `tuple` | array | `list` |
| `DocumentReference` | reference | `DocumentReference` |
| `FieldValue.*` | a write operation | (not a stored value) |
| Other Objective-C objects (`FIRGeoPoint`...) | passed through | the Objective-C object |

```python
from datetime import UTC, datetime

db.collection_with_path("events").document_with_path("launch").set_data({
    "title": "Launch",
    "starts_at": datetime(2026, 12, 1, 9, 30, tzinfo=UTC),
    "cancelled_at": None,
    "tags": ("product", "news"),          # stored as an array
    "owner": db.document_with_path("users/ada"),
    "venue": {"name": "Hall 1", "seats": 300},
})
```

## Dates and times

- Timestamps keep **microseconds**, both ways. Firestore stores nanoseconds,
  but a Python `datetime` cannot hold them, so the extra digits are dropped on
  read.
- A **naive** `datetime` (no `tzinfo`) is read as **UTC**, like the Firebase
  Admin SDK for Python does. Use aware datetimes (`datetime.now(UTC)`) to be
  explicit.
- Values you read are always in UTC. Use `.astimezone()` to show local time.
- A plain `date` is refused: Firestore has no date-only type. Pass a
  `datetime`, for example `datetime.combine(d, time(), tzinfo=UTC)`, or store
  the date as an ISO string.

```python
from datetime import UTC, datetime, timedelta

next_week = datetime.now(UTC) + timedelta(days=7)
db.collection_with_path("events") \
    .query_where_field_is_less_than("starts_at", next_week) \
    .query_ordered_by_field("starts_at") \
    .get_documents(on_events)


def on_events(snapshot, error):
    for event in snapshot:
        local = event.get("starts_at").astimezone()      # the device's time zone
        print(event.get("title"), local.strftime("%a %d %b, %H:%M"))
```

### Server timestamps

`FieldValue.field_value_for_server_timestamp()` lets the server write its own
time. Until the server answers, a listener sees the field as `None`. To see an
estimate instead:

```python
from pyios_firebase.firestore import FIRServerTimestampBehavior


def on_message(snapshot, error):
    data = snapshot.data_with_server_timestamp_behavior(
        FIRServerTimestampBehavior.Estimate      # or Previous, or None_
    )
```

## Numbers

`int` is stored as a 64-bit integer and `float` as a double: they stay
different types when read back, even `1` and `1.0`. A Python `int` beyond 64
bits cannot be stored.

`bool` is checked before `int` (in Python, `True` is an `int`), so booleans
stay booleans both ways.

## References

A `DocumentReference` stored in a field comes back as a `DocumentReference`,
ready to read:

```python
def on_order(snapshot, error):
    snapshot.get("customer").get_document(on_customer)
```

## Reading fields

```python
snapshot.data                      # the whole document, a dict ({} if it does not exist)
snapshot.get("venue")              # one field
snapshot.get("venue.seats")        # a nested field, with dots
snapshot["venue.seats"]            # the same
```

## Values Firestore cannot store

These raise a `TypeError` in Python, with the path of the bad field
(`"venue.opened: ..."`), **before anything is sent**:

- a `set`, a `frozenset`, or any object that is not in the table above;
- a `date` without a time;
- a dict key that is not a `str`.

```python
try:
    doc.set_data({"days": {"mon", "tue"}})
except TypeError as e:
    print(e)        # days: cannot store a set in Firestore ({'mon', 'tue'})
```

## Converting yourself

The conversion functions are public, for values you pass to the SDK yourself
(through `.native`):

```python
from pyios_firebase.util import to_firestore, to_python

native = to_firestore({"at": datetime.now(UTC)})   # NSDictionary with a FIRTimestamp
back = to_python(native)                            # {"at": datetime(...)}
```

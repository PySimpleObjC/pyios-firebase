# Lists and queries

## Add to a list

```python
messages = db.reference("rooms/general/messages")

ref = messages.child_by_auto_id()            # a new, unique key; nothing written yet
ref.set_value({"from": uid, "text": "Hello", "sent_at": ServerValue.timestamp()})
print(ref.key)                               # "-NqA1x..."
```

Auto IDs sort by creation time, and two clients never make the same one.
Avoid `list` values for collections that change: the database stores them as
objects with keys `"0"`, `"1"`..., and two clients appending at once overwrite
each other.

## Child events

For lists, listen to the children one by one instead of the whole list:

| `DataEventType` | Called |
|---|---|
| `CHILD_ADDED` | Once for each existing child at the start, then for each new one |
| `CHILD_CHANGED` | When a child (or anything below it) changes |
| `CHILD_REMOVED` | When a child is removed |
| `CHILD_MOVED` | When a child moves in the query's order |
| `VALUE` | With the whole list, at the start and on every change |

```python
def on_added(snapshot, previous_key):
    chat.insert_after(previous_key, snapshot.key, snapshot.value)


def on_changed(snapshot, previous_key):
    chat.update(snapshot.key, snapshot.value)


def on_removed(snapshot, previous_key):
    chat.remove(snapshot.key)


recent = messages.order_by_child("sent_at").limit_to_last(50)
observers = [
    recent.observe(DataEventType.CHILD_ADDED, on_added),
    recent.observe(DataEventType.CHILD_CHANGED, on_changed),
    recent.observe(DataEventType.CHILD_REMOVED, on_removed),
]
...
for observer in observers:
    observer.remove()
```

`previous_key` is the key of the child **before** this one in the query's
order (`None` for the first), so you can put it in the right place.

## Sort

A query can be ordered **once**:

| Method | Orders by |
|---|---|
| `order_by_child("sent_at")` | The value of a child of each child (a path works: `"stats/score"`) |
| `order_by_key()` | The keys |
| `order_by_value()` | The children's values |
| `order_by_priority()` | The children's priorities |

Children without the ordered child come first. Iterating a snapshot, and
child events, follow the query's order.

!!! tip "Index what you order by"
    Add `.indexOn` to the security rules for every child you order by, so the
    server sorts instead of sending everything:

    ```json
    { "rules": { "scores": { ".indexOn": ["score", "team"] } } }
    ```

## Filter and limit

Each method returns a new query; a query can have one start, one end and one
limit:

```python
scores = db.reference("scores").order_by_child("score")

scores.limit_to_last(10)                       # the top ten
scores.start_at(50).end_at(100)                # 50 to 100, both included
scores.start_after(70).end_before(90)          # 70 to 90, both excluded
scores.equal_to(100)                           # exactly 100

db.reference("users").order_by_key().start_at("b").end_before("c")    # keys starting with "b"
```

| Method | Keeps children |
|---|---|
| `start_at(value)` / `start_after(value)` | At / after the value |
| `end_at(value)` / `end_before(value)` | At / before the value |
| `equal_to(value)` | Equal to the value |
| `limit_to_first(n)` / `limit_to_last(n)` | The first / last n (1 to 2,147,483,647) |

Values are `None`, `bool`, numbers or `str` (only `str` with `order_by_key()`).
Among children with the same value, `start_at(70, "cy")` starts at the key
`"cy"`: that is how pages work.

## Paging

```python
PAGE = 20


def load_page(last_score=None, last_key=None):
    query = db.reference("scores").order_by_child("score")
    if last_score is not None:
        query = query.start_after(last_score, last_key)
    query.limit_to_first(PAGE).get_data(on_page)


def on_page(snapshot, error):
    rows = list(snapshot)
    show(rows)
    if len(rows) == PAGE:
        last = rows[-1]
        next_button.on_press = lambda: load_page(last.value["score"], last.key)
```

## Mistakes that would abort the app

Two orderings, two starts, two limits, a limit of 0, `order_by_key()` with a
number, or a `$` / `.` path in `order_by_child` all raise `ValueError` or
`TypeError` in Python. The SDK would raise an Objective-C exception, which
cannot be caught and ends the app.

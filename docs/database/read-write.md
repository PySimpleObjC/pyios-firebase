# Reading and writing

## Write

Every write takes an optional callback `(error)`, called once the **server**
has the write. Locally, the write applies at once: listeners on this device see
it immediately, even offline.

```python
ref = db.reference("users/ada")

ref.set_value({"name": "Ada Lovelace", "born": 1815})          # replaces everything here
ref.child("born").set_value(1816)                               # one child
ref.update_child_values({"name": "Ada", "country": "UK"})       # only these children
ref.child("country").remove_value()                             # delete (or set_value(None))
```

| Method | Children not written |
|---|---|
| `set_value(value)` | **Removed** |
| `update_child_values(values)` | Kept |
| `remove_value()` | (everything here is removed) |

```python
def on_saved(error):
    if error is not None:
        print(error.name, error.description)      # for example PERMISSION_DENIED


ref.set_value({"name": "Ada"}, on_saved)
```

### Update several locations at once

`update_child_values` keys can be **paths**, to write to many places
atomically: either every path is written, or none.

```python
key = db.reference("posts").child_by_auto_id().key
post = {"author": uid, "title": title, "created": ServerValue.timestamp()}

db.reference().update_child_values({
    f"posts/{key}": post,
    f"user-posts/{uid}/{key}": post,
    f"users/{uid}/post_count": ServerValue.increment(1),
})
```

Paths cannot be inside each other (`"posts/p1"` and `"posts/p1/title"`): that
raises `ValueError` (the SDK would abort the app). Put the inner value in the
outer one instead.

## Read once

```python
def on_user(snapshot, error):
    if error is not None:
        return show(error.description)
    if snapshot.exists():
        print(snapshot.value)              # {"name": "Ada", "born": 1815}


db.reference("users/ada").get_data(on_user)
```

`get_data` asks the server, and falls back to the cache when offline. To use
the cache when there is one (and the server otherwise), read one event:

```python
db.reference("users/ada").observe_once(DataEventType.VALUE, lambda snapshot, _: show(snapshot.value))
```

## Listen

```python
def on_value(snapshot, previous_key):
    show_profile(snapshot.value)


observer = db.reference("users/ada").observe(DataEventType.VALUE, on_value)
...
observer.remove()
```

The callback runs at once with the current data, then on every change to the
location **or anything below it**. It gets `(snapshot, previous_child_key)`;
for `VALUE` events the key is always `None`.

!!! warning "Listening downloads the whole location"
    A `VALUE` listener on `rooms/general` downloads every message of the room.
    Listen to the smallest location you need, and use
    [child events and limits](lists.md) for lists.

`ref.remove_all_observers()` removes every observer of that location (not of
its children). When the server stops a listener (for example
`PERMISSION_DENIED` after sign-out), the optional `cancel_callback` gets the
error, and the observer is already removed:

```python
ref.observe(DataEventType.VALUE, on_value, cancel_callback=lambda error: show(error.name))
```

## Snapshots

| | |
|---|---|
| `snapshot.value` | The data as Python values, or `None` |
| `snapshot.key` | The location's key |
| `snapshot.exists()`, `snapshot.has_children()`, `snapshot.children_count` | |
| `snapshot.child("address/city")`, `snapshot.has_child("address")` | Data below |
| `for child in snapshot` | The children, in the query's order |
| `snapshot.priority`, `snapshot.export_value()` | Priorities, and the data with them (`".value"` / `".priority"`) |
| `snapshot.ref` | Where it was read from |

## Transactions

Change a value from its current value, safely when many clients write at
once:

```python
from pyios_firebase.database import TransactionResult


def add_star(data):
    post = data.value
    if post is None:
        return TransactionResult.success(data)   # see the note below
    stars = post.get("stars", {})
    if uid in stars:
        post["star_count"] -= 1
        del stars[uid]
    else:
        post["star_count"] = post.get("star_count", 0) + 1
        stars[uid] = True
    post["stars"] = stars
    data.value = post
    return TransactionResult.success(data)


def on_done(error, committed, snapshot):
    if error is not None:
        print("Failed:", error.description)
    elif committed:
        print("Stars:", snapshot.value["star_count"])


db.reference(f"posts/{post_id}").run_transaction(add_star, on_done)
```

- The function gets a `MutableData` (`value`, `priority`, `child(path)`,
  `children`) and returns `TransactionResult.success(data)` to write, or
  `TransactionResult.abort()` to write nothing.
- **It may run several times**, on a background thread: whenever the server
  has other data, it runs again with that data. No side effects in it.
- **The first run may see `None`** while the server has data: the SDK has
  nothing cached yet. Return `success` anyway; the SDK runs it again with the
  server's value.
- If the function raises, the transaction is aborted and the callback's
  `error` has the exception (`domain` `TRANSACTION_ERROR_DOMAIN`).
- `local_events=False` shows only the committed value to local listeners,
  not each attempt.

For a plain counter, `ServerValue.increment(1)` is simpler, and works offline.

## Priorities

Each value can carry a priority (a number or a string), for
`order_by_priority()`:

```python
ref.set_value("first", priority=2)
ref.set_priority(1)
```

Most apps order by a child instead ([Lists and queries](lists.md)).

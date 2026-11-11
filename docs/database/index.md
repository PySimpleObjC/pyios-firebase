# Realtime Database

The [Realtime Database](https://firebase.google.com/docs/database) is one big
JSON tree, synced live to every connected client. It answers in milliseconds
and is billed by data downloaded, which suits presence, chat, live cursors and
game state. For rich queries over many documents, Firestore is usually the
better fit.

```python
from pyios_firebase.database import DataEventType, Database, ServerValue

db = Database.database()
messages = db.reference("rooms/general/messages")

messages.child_by_auto_id().set_value({"text": "Hello", "sent_at": ServerValue.timestamp()})


def on_message(snapshot, previous_key):
    print(snapshot.key, snapshot.value)


observer = messages.order_by_child("sent_at").limit_to_last(50).observe(
    DataEventType.CHILD_ADDED, on_message
)
```

## Installation

1. Add the **`FirebaseDatabase`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. In the console, open **Realtime Database** and create the database. Pick
   its location: the URL depends on it
   (`https://<project>-default-rtdb.firebaseio.com`, or
   `https://<name>.<region>.firebasedatabase.app`).
3. Download `GoogleService-Info.plist` again: it then has the `DATABASE_URL`.

## Guides

<div class="grid cards" markdown>

-   :material-pencil-outline: **[Reading and writing](read-write.md)**: values, updates, listeners, transactions.
-   :material-format-list-bulleted: **[Lists and queries](lists.md)**: child events, sorting, filtering, paging.
-   :material-wifi-off: **[Offline and presence](offline.md)**: persistence, `on_disconnect`, connection state.

</div>

## The data model

Everything is one JSON tree; a `DatabaseReference` points to a location in it:

```json
{
  "users": {
    "ada": { "name": "Ada Lovelace", "rooms": { "general": true } }
  },
  "rooms": {
    "general": {
      "messages": {
        "-NqA1...": { "from": "ada", "text": "Hello", "sent_at": 1767225600000 }
      }
    }
  }
}
```

```python
db.reference()                          # the root
db.reference("users/ada")               # a location
db.reference("users").child("ada")      # the same
ref.parent, ref.root, ref.key, ref.path, ref.url
```

### Structuring the data

- **Keep it flat.** Reading a location downloads **everything below it**:
  store messages apart from the room list, not inside it.
- **Index relationships both ways** (`users/ada/rooms/general: true` and
  `rooms/general/members/ada: true`), and write both at once with a
  [multi-path update](read-write.md#update-several-locations-at-once).
- **Use `child_by_auto_id()` for lists**: its keys sort by creation time and
  never collide between clients.

## Values

| Python | Stored | Read back as |
|---|---|---|
| `str`, `int`, `float`, `bool` | the same | the same (`bool` stays `bool`) |
| `None` | deletes the value | (absent: `None`) |
| `dict` (`str` keys) | an object | `dict` |
| `list`, `tuple` | an object with keys `"0"`, `"1"`... | `list` (when the keys are mostly sequential), else `dict` |
| `ServerValue.timestamp()` | the server's time, in ms since 1970 | `int` |
| `ServerValue.increment(n)` | the stored number + n | `int` / `float` |

The database has **no date type**: store `ServerValue.timestamp()` or
milliseconds since 1970 (`int(dt.timestamp() * 1000)`), or an ISO string.

## Mistakes raise in Python

The SDK raises an **Objective-C exception**, which aborts the whole app, for
a bad path, value or query. pyios-firebase checks first and raises a Python
exception instead:

| Mistake | Raises |
|---|---|
| A key with `.` `#` `$` `[` `]` or `/` (or an empty key) | `ValueError` |
| A path with `.` `#` `$` `[` `]` | `ValueError` |
| `nan`, `inf`, a string over 10 MB | `ValueError` |
| A `datetime`, `bytes`, a `set`, a non-`str` key | `TypeError` |
| Writing under `.info` | `ValueError` |
| Update paths at or below each other (`"a"` and `"a/b"`) | `ValueError` |
| Ordering a query twice, two starts, two ends, two limits, a limit of 0 | `ValueError` |
| `order_by_key()` with non-`str` start / end values, or a child key | `TypeError` / `ValueError` |

```python
name = user_input.strip()
try:
    db.reference("usernames").child(name).set_value(uid)
except ValueError:
    show("A name cannot contain . # $ [ ] or /")
```

## Several databases

```python
eu = Database.database("https://my-app-eu.europe-west1.firebasedatabase.app")
```

## Use the local emulator

```python
core.configure()
Database.database().use_emulator("127.0.0.1", 9000)
```

Call it before the first reference. See [Emulator Suite](../getting-started/emulators.md).

## Errors

Database errors are `DatabaseError`s (`name` from `DatabaseErrorCode`):

| `DatabaseErrorCode` | Means |
|---|---|
| `PERMISSION_DENIED` | The security rules do not allow this read or write |
| `UNAVAILABLE` | The server is unavailable |
| `WRITE_CANCELED` | The write was dropped (`purge_outstanding_writes`) |
| `OTHER` | Another status, in `description` (for example `"maxretry"` for a transaction) |

`get_data` offline, with nothing cached, fails with an error from another
domain (`name` is `""`).

Turn on the SDK's logs while debugging: `Database.set_logging_enabled(True)`.

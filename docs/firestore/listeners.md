# Realtime updates

A **snapshot listener** calls your function with the current data at once,
then again on every change: from this device (immediately, even offline) and
from others (as soon as the server sends it).

```python
def on_city(snapshot, error):
    if error is not None:
        print("Listen failed:", error.description)
        return
    print("Current data:", snapshot.data)


listener = db.document_with_path("cities/SF").add_snapshot_listener(on_city)
...
listener.remove()        # stop
```

| Listen to | Callback gets |
|---|---|
| A document: `doc.add_snapshot_listener(callback)` | `(DocumentSnapshot, error)` |
| A query or collection: `query.add_snapshot_listener(callback)` | `(QuerySnapshot, error)` |

!!! warning "Remove what you add"
    A listener keeps the connection busy and counts a read for every document
    sent to it, until you call `remove()`. Remove it when its screen closes.
    `remove()` is safe to call more than once.

## What changed

`snapshot.document_changes` lists the changes since the last call (all the
documents as `ADDED` the first time):

```python
from pyios_firebase.firestore import DocumentChange


def on_messages(snapshot, error):
    if error is not None:
        return
    for change in snapshot.document_changes:
        if change.type == DocumentChange.ADDED:
            chat.insert(change.new_index, change.document.data)
        elif change.type == DocumentChange.MODIFIED:
            chat.move(change.old_index, change.new_index, change.document.data)
        elif change.type == DocumentChange.REMOVED:
            chat.remove(change.old_index)


db.collection_with_path("rooms/general/messages") \
    .query_ordered_by_field("sent_at") \
    .query_limited_to_last(50) \
    .add_snapshot_listener(on_messages)
```

`old_index` and `new_index` are the positions in the previous and the new
results, so a list on screen can be updated in place instead of redrawn. For
`ADDED` there is no old position and for `REMOVED` no new one: those are
`NSNotFound` (a very large number), so use only the index that applies.

## Pending writes and the cache

Every snapshot has `metadata`:

| Field | `True` when |
|---|---|
| `snapshot.metadata.has_pending_writes` | The data includes local writes the server has not confirmed yet |
| `snapshot.metadata.is_from_cache` | The data comes from the device's cache (offline, or not synced yet) |

```python
def on_profile(snapshot, error):
    if error is None:
        saving.visible = snapshot.metadata.has_pending_writes   # "Saving..."
        show(snapshot.data)
```

By default a listener is not called when **only** the metadata changes (for
example when the server confirms your write). Ask for those calls too:

```python
listener = doc.add_snapshot_listener(on_profile, include_metadata_changes=True)
```

## Listen options

```python
from pyios_firebase.firestore import FIRListenSource, SnapshotListenOptions

options = SnapshotListenOptions(
    include_metadata_changes=True,
    source=FIRListenSource.Cache,       # only the device's cache, no server traffic
)
query.add_snapshot_listener(on_cities, options=options)
```

## In a Kivy screen

Listener callbacks run on the main thread, so they can change widgets:

```python
from kivy.uix.screenmanager import Screen


class CitiesScreen(Screen):
    def on_enter(self):
        query = Firestore.firestore().collection_with_path("cities") \
            .query_where_field_is_equal_to("state", "CA")
        self.listener = query.add_snapshot_listener(self.on_cities)

    def on_cities(self, snapshot, error):
        if error is None:
            self.ids.list.data = [{"text": doc.get("name")} for doc in snapshot]

    def on_leave(self):
        self.listener.remove()
```

## Errors

A listener that fails (for example `PERMISSION_DENIED` after the user signs
out) is called once with the error and then **stops**: add it again after
fixing the cause.

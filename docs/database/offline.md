# Offline and presence

## Offline writes

The SDK keeps writes in a queue while offline, shows them to local listeners
at once, and sends them when the connection is back. Their callbacks run
then. Without persistence, the queue is lost if the app is killed.

## Persistence

Keep the cached data **and the queued writes** on disk, so they survive a
restart:

```python
db = Database.database()
db.persistence_enabled = True                      # before any other use
db.persistence_cache_size_bytes = 50 * 1024 * 1024  # 1 MB to 100 MB; default 10 MB
```

Both must be set before the first reference. With persistence, keep a
location fresh in the cache even with no listener:

```python
db.reference("users/ada/settings").keep_synced(True)
```

After a long time offline, drop writes that no longer make sense:

```python
db.purge_outstanding_writes()      # their callbacks get WRITE_CANCELED
```

## Connection state

`.info/connected` is `True` while the client is connected to the server:

```python
def on_connected(snapshot, _):
    banner.text = "" if snapshot.value else "Offline: changes will sync later"


db.reference(".info/connected").observe(DataEventType.VALUE, on_connected)
```

Other `.info` values: `.info/serverTimeOffset` (milliseconds to add to the
device's clock to get the server's). `.info` is local and read-only: writing
to it raises `ValueError`.

Turn the connection off and on yourself (for example to save battery, or in
tests):

```python
db.go_offline()
db.go_online()
```

## Presence

`on_disconnect()` writes that the **server** makes when the client goes away:
the app closes, crashes, or loses the network. They are queued on the server
now, so they run even if the app is killed.

```python
def track_presence(uid):
    status = db.reference(f"status/{uid}")

    def on_connected(snapshot, _):
        if not snapshot.value:
            return
        # 1. what the server writes if we disappear
        status.on_disconnect().set_value({"state": "offline", "last_changed": ServerValue.timestamp()})
        # 2. then: we are here
        status.set_value({"state": "online", "last_changed": ServerValue.timestamp()})

    db.reference(".info/connected").observe(DataEventType.VALUE, on_connected)
```

Set the disconnect write **before** writing "online", and again on every
reconnection: the server forgets it once it ran.

| `on_disconnect()` method | The server, on disconnect |
|---|---|
| `set_value(value, callback, priority=)` | Writes the value |
| `update_child_values(values, callback)` | Updates the children (paths work) |
| `remove_value(callback)` | Deletes the location |
| `cancel(callback)` | Cancels the disconnect writes set here (and below) |

The callbacks say when the server has queued the write, not when it ran.

## Server timestamps and the clock

`ServerValue.timestamp()` stores the server's time. Before the server
answers, local listeners see an **estimate** from the device's clock and
`.info/serverTimeOffset`, then the real value (one more change event).

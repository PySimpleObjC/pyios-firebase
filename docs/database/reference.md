# Realtime Database reference

## At a glance

- `Database.database(url=None)`: `reference(path)`, `reference_from_url(url)`, `use_emulator(host, port)`, `persistence_enabled`, `persistence_cache_size_bytes`, `go_offline()`, `go_online()`, `purge_outstanding_writes()`, `set_logging_enabled(enabled)`, `sdk_version()`
- `DatabaseQuery`: `order_by_child(path)`, `order_by_key()`, `order_by_value()`, `order_by_priority()`, `start_at(value, child_key)`, `start_after`, `end_at`, `end_before`, `equal_to`, `limit_to_first(n)`, `limit_to_last(n)`; `observe(event_type, callback, cancel_callback)` → `DatabaseObserver` (`remove()`), `observe_once(...)`, `get_data(cb)`, `remove_all_observers()`, `keep_synced(bool)`, `ref`
- `DatabaseReference(DatabaseQuery)`: `key`, `url`, `path`, `parent`, `root`, `database`, `child(path)`, `child_by_auto_id()`; `set_value(value, cb, *, priority)`, `update_child_values(values, cb)`, `remove_value(cb)`, `set_priority(priority, cb)`, `run_transaction(update, cb, *, local_events)`, `on_disconnect()` → `OnDisconnect` (`set_value`, `update_child_values`, `remove_value`, `cancel`)
- `DataSnapshot`: `key`, `value`, `priority`, `export_value()`, `exists()`, `child(path)`, `has_child(path)`, `has_children()`, `children_count`, iteration over the children, `ref`
- `MutableData`: `key`, `value` (settable), `priority` (settable), `child(path)`, `has_child`, `has_children`, `children_count`, `children`; `TransactionResult.success(data)`, `TransactionResult.abort()`
- `ServerValue.timestamp()`, `ServerValue.increment(delta)`, `to_database(value)`; `DataEventType`; `DatabaseError` (`name`), `DatabaseErrorCode`, `DATABASE_ERROR_DOMAIN`, `TRANSACTION_ERROR_DOMAIN`

## `pyios_firebase.database`

::: pyios_firebase.database

# Migrating

## From the flat 0.1 modules

Every product is now a subpackage:

| Before | Now |
|---|---|
| `pyios_firebase.firapp.configure()` | `pyios_firebase.core.configure()` |
| `pyios_firebase.firfirestore`, `firfieldvalue`, `firfilter` | `pyios_firebase.firestore` |
| `pyios_firebase.firuser.User` | `pyios_firebase.auth.User` (also `Auth.auth().current_user`) |
| `pyios_firebase.firgoogleauth` | `pyios_firebase.auth.google` |
| `pyios_firebase.firappcheck.initialize_debug_appcheck()` | `pyios_firebase.app_check.use_debug_provider()` (the old name still works) |

Auth changes:

- Sign-in callbacks get `(result, error)` like the rest of the library, instead
  of `(data, is_error)`: `result` is an `AuthDataResult` (`result.user.uid`), and
  `error` is an `AuthError` (still with `cancelled`).
- `User().uid`, `.email` and `.display_name` are `str` or `None` (not Objective-C
  strings); `User().user` and `User().auth` are still the native objects.
- Several sign-ins can run at once: each keeps its own callback.

Firestore changes:

- Reads give snapshots: `get_document` gives a `DocumentSnapshot`, and
  `get_documents` / query listeners give a `QuerySnapshot` (iterate it like the
  old list).
- `add_snapshot_listener_for_changes` is gone: use `snapshot.document_changes`.
- `DocumentReference.set_data(data, callback)` is now
  `set_data(data, merge=False, callback=None)`. The old `set_data(data, callback)` still works.
- `FIRAggregateSource` and the other enums are in `pyios_firebase.firestore`.
- Any exception raised in a transaction function now stops the transaction, and
  the callback gets the Python value you returned (not an Objective-C object).
- Errors also have a `domain` key.
- Booleans are now read as `True` / `False`. Before, they came back as `1` / `0`.
- `None` in data you write is stored as `null`. Before, it crashed the app.
- `datetime` values can be written and used in queries.
- Unsupported values raise `TypeError` in Python instead of failing inside the SDK.
- `snapshot.metadata.is_from_cache`, `snapshot.metadata.has_pending_writes` and
  `query_snapshot.is_empty` were always `True` (they read Objective-C custom
  getters without calling them). They now give the real value; code that relied
  on them, for example to skip pending local writes, behaves differently.

## From pyobjus-firebase

1. Install `pyios-firebase` and follow [Setup](../getting-started/setup.md#setup).
2. Replace the `pyobjus-firebase` imports in your code with the new ones.
3. Delete any `.m` or `.h` files you added only for `pyobjus-firebase`.
4. If something does not work, open an issue in this repository.


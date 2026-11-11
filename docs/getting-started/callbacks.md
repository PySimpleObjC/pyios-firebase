# Callbacks and threads

Firebase calls your code later, when the server answers. So most methods take a
**callback**: a normal Python function.

| Kind of method | Callback arguments |
|---|---|
| Firestore writes (`set_data`, `update_data`, `delete_document`, `commit`) | `(error)` |
| `add_document_with_data` | `(document_reference, error)` |
| `get_document`, document `add_snapshot_listener` | `(document_snapshot, error)` |
| `get_documents`, query `add_snapshot_listener` | `(query_snapshot, error)` |
| Aggregate queries | `(aggregate_snapshot, error)` |
| `run_transaction` | `(result, error)` |
| Auth sign-in, link, re-authenticate, Google / Apple sheets | `(auth_data_result, error)` |
| Auth writes (`send_password_reset`, `reload`, `delete`, `update_*`) | `(error)` |
| `add_state_did_change_listener` | `(user)` (`None` when signed out) |
| `HTTPSCallable.call` | `(data, error)` |
| Storage uploads / `get_metadata` / `update_metadata` | `(storage_metadata, error)` |
| `get_data`, `download_url`, `write_to_file`, `list` | `(bytes / url / path / list_result, error)` |
| `RemoteConfig.fetch_and_activate` / `fetch` / `activate` | `(status, error)` / `(status, error)` / `(changed, error)` |
| `AppCheck.token` / `limited_use_token` | `(app_check_token, error)` |
| Realtime Database writes (`set_value`, `update_child_values`, `remove_value`, `on_disconnect()...`) | `(error)` |
| Realtime Database `observe` / `observe_once` | `(snapshot, previous_child_key)`; `cancel_callback(error)` |
| Realtime Database `get_data` | `(snapshot, error)` |
| Realtime Database `run_transaction` | `(error, committed, snapshot)` |
| `Analytics.session_id` | `(session_id, error)` (background thread) |
| `Crashlytics.check_for_unsent_reports` / `check_and_update_unsent_reports` | `(found)` / `(report)` (background thread) |
| `Messaging.token` / `retrieve_fcm_token` | `(token, error)` |
| Messaging topics, `register`, `delete_token`, `delete_data` | `(error)` |
| `notifications.request_permission` / `authorization_status` | `(granted, error)` / `(status)` (background thread) |

The rules are the same everywhere:

- `error` is `None` when it worked. Otherwise it is a `QueryDict` with `code`
  (`int`), `description` (`str`), `domain` (`str`) and `underlying_error`.
  A `QueryDict` is a dict you can also read with dots: `error.description`.
- When there is an error, the result is `None`.
- For write methods, the callback is optional.

```python
def on_cities(snapshot, error):
    if error:
        print("Error getting documents:", error.description)
        return
    for doc in snapshot:
        print(doc.document_id, "=>", doc.data)
```

## Handling errors

Check `error` first, then use the result:

```python
from pyios_firebase.auth import AuthErrorCode


def on_signed_in(result, error):
    if error is not None:
        if error.code == AuthErrorCode.WRONG_PASSWORD:
            show("Wrong password")
        elif error.cancelled:            # the user closed a sign-in sheet
            pass
        else:
            show(error.description)
        return
    show(f"Welcome, {result.user.display_name}")
```

Each product has its own error class, with the code's **name** next to the
number: see [Errors](errors.md).

## Which thread a callback runs on

Most callbacks run on the **main thread**: Firebase calls them on the main
dispatch queue, which is Kivy's and Toga's thread. You can change widgets in
them directly.

A few run on a **background thread**, because the SDK calls them there:

| Callback | Thread |
|---|---|
| `Analytics.session_id` | A background queue |
| `Crashlytics.check_for_unsent_reports`, `check_and_update_unsent_reports` | A background queue |
| `notifications.request_permission`, `notifications.authorization_status` | A background queue |
| The `update` function of a Realtime Database `run_transaction` | The database's own thread (it can run several times) |
| An `AppCheckProvider`'s `get_token` | Whichever thread App Check asks from |

From these, move to the main thread before touching the UI:

=== "Kivy"

    ```python
    from kivy.clock import mainthread


    @mainthread
    def show_status(status):
        label.text = f"Notifications: {status}"


    notifications.authorization_status(show_status)
    ```

    Or one call at a time: `Clock.schedule_once(lambda dt: show_status(status))`.

=== "BeeWare (Toga)"

    ```python
    def show_status(status):
        label.text = f"Notifications: {status}"


    def on_status(status):
        app.loop.call_soon_threadsafe(show_status, status)


    notifications.authorization_status(on_status)
    ```

!!! danger "Do not block the main thread"
    Never wait for a callback in a loop (`while result is None: sleep(...)`)
    on the main thread: Firebase delivers callbacks on that same thread, so
    the loop never ends and the app freezes. Start the call and return; do
    the rest in the callback.

## Callback lifetime

Firebase keeps only a C pointer to a callback, so a Python function handed to
Objective-C could be freed before Firebase calls it, and the app would crash.
pyios-firebase keeps every callback alive for you:

- **one-time callbacks** (a read, a write, a sign-in) until Firebase calls them;
- **listeners** (snapshot listeners, auth state listeners, database
  observers, Storage task observers) until you remove them.

You do not need to keep references yourself. But do keep the object a
listener gives back, and remove it when you are done:

```python
class CitiesScreen(Screen):
    def on_enter(self):
        self.listener = cities.add_snapshot_listener(self.on_cities)

    def on_leave(self):
        self.listener.remove()   # stops the reads, and frees the callback
```

A listener keeps using the network (and counts reads on your bill) until it is
removed.

## Chaining calls

Each step starts the next one from its callback:

```python
def sign_in_then_load(email, password):
    def on_signed_in(result, error):
        if error is not None:
            return show(error.description)
        profile = db.document_with_path(f"users/{result.user.uid}")
        profile.get_document(on_profile)

    def on_profile(snapshot, error):
        if error is None and snapshot.exists:
            show_profile(snapshot.data)

    Auth.auth().sign_in_with_email_password(email, password, on_signed_in)
```

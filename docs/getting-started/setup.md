# Setup

## 1. Register the app in Firebase

In the [Firebase console](https://console.firebase.google.com), open your
project (or create one), then **Add app > iOS**. The **bundle ID** must be
exactly your app's (for example the `bundle_id` in kivyforge's
`pyproject.toml`, or Briefcase's `bundle` + app name).

Download **`GoogleService-Info.plist`** and add it to the app (see
[Installation](installation.md#2-the-firebase-packages)). It tells the SDK
which project to use: the API key, the project ID, the app ID, the storage
bucket and the database URL.

!!! note "Is the file in the app?"
    If `core.configure()` stops the app with *"`FirebaseApp.configure()` could
    not find a valid GoogleService-Info.plist"*, the file is not in the app
    bundle: check its target membership, or `include_files` in kivyforge.

## 2. Start Firebase

Call `core.configure()` **once**, when the app starts, before any other
product:

=== "Kivy"

    ```python title="main.py"
    from kivy.app import App
    from pyios_firebase import core


    class MyApp(App):
        def build(self):
            core.configure()
            ...


    MyApp().run()
    ```

=== "BeeWare (Toga)"

    ```python title="app.py"
    import toga
    from pyios_firebase import core


    class MyApp(toga.App):
        def startup(self):
            core.configure()
            ...
    ```

`core.default_app()` returns the configured `FIRApp`, or `None` before
`configure()`.

### What must come before `configure()`

Some settings are read only when Firebase starts:

| Setting | Why |
|---|---|
| The App Check provider (`app_check.use_*_provider()`) | Firebase creates App Check with the app; after it, the `use_*` functions raise `RuntimeError` |
| `notifications.set_handlers(...)` (Messaging) | Not required before `configure()`, but early: a tap that launched the app is delivered right after start-up |

And some are read only **before the first use** of their product:

| Setting | Before |
|---|---|
| `Firestore.firestore().use_emulator(...)` | The first Firestore read or write |
| `Database.database().persistence_enabled`, `use_emulator(...)` | The first database reference |
| `Storage.storage().use_emulator(...)`, `Functions...use_emulator(...)` | The first call |

## 3. Info.plist settings

Firebase reads these keys from the app's `Info.plist`. All are optional.

| Key | Product | Effect |
|---|---|---|
| `FirebaseAppDelegateProxyEnabled` | Messaging, Analytics, Auth | `NO` turns off app delegate swizzling: forward the APNs token, notifications and URLs yourself |
| `FIREBASE_ANALYTICS_COLLECTION_ENABLED` | Analytics | `NO` starts with collection off (for consent) |
| `FirebaseCrashlyticsCollectionEnabled` | Crashlytics | `NO` keeps reports on the device until you send them |
| `FirebaseMessagingAutoInitEnabled` | Messaging | `NO` makes no FCM token at start-up |
| `FirebaseMessagingInstallationIdEnabled` | Messaging | `YES` registers through the installation ID instead of a token |
| `firebase_performance_collection_enabled` | Performance | `NO` starts with collection off |
| `firebase_performance_instrumentation_enabled` | Performance | `NO` turns off automatic traces |
| `FirebaseAppCheckTokenAutoRefreshEnabled` | App Check | `NO` stops refreshing tokens in the background |
| `CFBundleURLTypes` | Auth | URL schemes for Google Sign-In and for phone / web sign-in ([Authentication](../auth/index.md)) |

=== "Kivy (kivyforge)"

    ```toml title="pyproject.toml"
    [tool.kivy.ios.info_plist]
    FirebaseCrashlyticsCollectionEnabled = false
    FIREBASE_ANALYTICS_COLLECTION_ENABLED = false
    ```

=== "Xcode"

    Open the target's **Info** tab and add the keys (type *Boolean*).

## 4. Optional: App Check

App Check proves to Firebase that requests come from your app. Choose the
provider **before** `core.configure()`:

```python
from pyios_firebase import app_check, core

if app_check.running_in_simulator():
    app_check.use_debug_provider()       # prints a token to register in the console
else:
    app_check.use_app_attest_provider()
core.configure()
```

Details: [App Check](../app-check/index.md).

## 5. Optional: Google Sign-In URL handling

In Kivy, SDL passes the URLs the app is opened with to Python as a "drop file"
event. Send them to Google Sign-In:

```python
from kivy.core.window import Window
from pyios_firebase.auth import google

Window.bind(on_drop_file=google.on_gid_signin_handle_url_kivy)
```

The app must own the reversed client ID URL scheme
(`com.googleusercontent.apps.YOUR-CLIENT-ID`, from `GoogleService-Info.plist`)
in `CFBundleURLTypes`. Recent Google Sign-In versions deliver the result
straight to the sign-in callback, so this handler may never be called: it is a
safe backup.

## Next steps

- [Use the emulators](emulators.md) while you develop.
- Read [Callbacks and threads](callbacks.md): every Firebase call answers later.
- Pick a product: [Firestore](../firestore/index.md),
  [Authentication](../auth/index.md), [Storage](../storage/index.md)...

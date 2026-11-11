# Troubleshooting

| Problem | What to check |
|---|---|
| `NameError: ... FIRFirestore` (or another `FIR...` class) | That Firebase framework is not part of your iOS build |
| `Firebase sign-in error: An internal error has occurred` | Print `error.code`, `error.domain` and `error.underlying_error`. Common causes: missing Keychain Sharing, wrong `GoogleService-Info.plist`, sign-in provider not enabled, API key limits, App Check enforcement without a registered debug token |
| `permission denied` | Your Firestore rules need a signed-in user, or the rules do not allow this read or write |
| The app stops with "Please register custom URL scheme" | Phone or web sign-in without the callback URL scheme in `Info.plist`. Use pyios-firebase's methods: they give an `AuthError` naming the scheme instead |
| `NOT_FOUND` / `INVALID_CREDENTIAL` on sign-in with the emulator | The emulator starts empty each run: create the account first |
| `core.default_app()` is `None` | `core.configure()` was not called, or it was called too late |
| App Check blocks requests | Choose the provider **before** `core.configure()` (after it, the `use_*` functions raise `RuntimeError`), and register the debug token in the Firebase console |
| A function call fails with `INTERNAL` | The function threw an unexpected error: check its logs (the message is not sent to the app) |
| Storage `UNAUTHORIZED` / `UNAUTHENTICATED` | The Storage security rules do not allow it, or need a signed-in user |
| With the Storage emulator, `get_metadata` still finds a deleted file | The emulator sends the file's own `Cache-Control` on metadata responses, so iOS caches them. Use a non-cacheable `cache_control` (for example `"no-cache"`) on emulator test files |
| The app aborts with `InvalidPathValidation` or `InvalidFirebaseData` | A Realtime Database call made through `native` with a bad path or value. Through pyios-firebase it is a `ValueError` / `TypeError` |
| Realtime Database writes never call back | The app is offline: writes wait in the queue, and the callback runs once the server has them. Local listeners already show the write |
| An Analytics event does not show up | It may take up to a day in reports: use DebugView (`-FIRDebugEnabled`) to see events at once |
| Crashlytics shows no crash | Crashlytics does not report while the debugger is attached: launch the app from the Home screen, crash, then launch it again to send |
| Performance traces or HTTP metrics do nothing | `trace.active` is `False`: data collection is off (`data_collection_enabled`, or `firebase_performance_collection_enabled` in `Info.plist`) |
| No FCM token | On a device: the push capability and an APNs key in the console are needed. FCM does not work in the Simulator |
| Remote Config values never change | `minimum_fetch_interval` (12 h by default) has not passed, or you fetched but did not `activate` |
| A query fails with an index error | Open the link in the error message and create the index |
| `snapshot.data` has odd types | Some Firestore values stay Objective-C objects (see [Python values and Firestore types](../firestore/data-types.md)). Open an issue and tell us the Rubicon version and what `type(...)` prints |


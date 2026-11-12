# Firebase Emulator Suite

The [Emulator Suite](https://firebase.google.com/docs/emulator-suite) runs
Firestore, Authentication, the Realtime Database, Cloud Functions and Cloud
Storage on your Mac. Develop and test against it: nothing is billed, no real
user data is touched, and the data is wiped when it stops.

pyios-firebase's own end-to-end tests run against these emulators in the iOS
Simulator (see [Development and testing](../guides/development.md)).

## Start the emulators

You need [`firebase-tools`](https://firebase.google.com/docs/cli) and Java 21
or newer.

```json title="firebase.json"
{
  "emulators": {
    "firestore": { "host": "127.0.0.1", "port": 8080 },
    "auth":      { "host": "127.0.0.1", "port": 9099 },
    "database":  { "host": "127.0.0.1", "port": 9000 },
    "functions": { "host": "127.0.0.1", "port": 5001 },
    "storage":   { "host": "127.0.0.1", "port": 9199 },
    "ui":        { "enabled": true, "port": 4000 },
    "singleProjectMode": true
  },
  "storage":  { "rules": "storage.rules" },
  "database": { "rules": "database.rules.json" }
}
```

```bash
firebase emulators:start --project demo-my-app
```

A project ID that starts with **`demo-`** is a *demo project*: the emulators
serve it without a real Firebase project or any credentials, and nothing can
reach production by mistake.

Open the Emulator UI at <http://127.0.0.1:4000> to watch the reads and writes,
the users and the files as your app makes them.

## Connect the app

Call `use_emulator` on each product **right after `core.configure()`**, before
any other use of that product:

```python
from pyios_firebase import core
from pyios_firebase.auth import Auth
from pyios_firebase.database import Database
from pyios_firebase.firestore import Firestore
from pyios_firebase.functions import Functions
from pyios_firebase.storage import Storage

core.configure()

if USE_EMULATORS:
    Firestore.firestore().use_emulator("127.0.0.1", 8080)
    Auth.auth().use_emulator("127.0.0.1", 9099)
    Database.database().use_emulator("127.0.0.1", 9000)
    Functions.functions().use_emulator("127.0.0.1", 5001)
    Storage.storage().use_emulator("127.0.0.1", 9199)
```

| Product | Call | Default port |
|---|---|---|
| Firestore | `Firestore.firestore().use_emulator(host, port)` | 8080 |
| Authentication | `Auth.auth().use_emulator(host, port)` | 9099 |
| Realtime Database | `Database.database().use_emulator(host, port)` | 9000 |
| Cloud Functions | `Functions.functions(region).use_emulator(host, port)`, for each region you call | 5001 |
| Cloud Storage | `Storage.storage().use_emulator(host, port)` | 9199 |

!!! tip "Simulator or device"
    The iOS Simulator shares the Mac's network, so `127.0.0.1` works there. On
    a device, use the Mac's LAN address (for example `192.168.1.20`), and start
    the emulators with `"host": "0.0.0.0"` so they accept connections from the
    network.

!!! note "Firestore and TLS"
    The Firestore SDK's own `useEmulator` sets the host but leaves TLS on, and
    the emulator speaks plain HTTP/2. pyios-firebase's `use_emulator` also
    turns TLS off, so it works out of the box.

## Without a `GoogleService-Info.plist`

For tests, configure Firebase in code with the demo project instead of a
plist. This is how the end-to-end test app does it:

```python
from pyios_firebase.util import objc_class

options = objc_class("FIROptions").alloc().initWithGoogleAppID_GCMSenderID_(
    "1:1234567890:ios:0123456789abcdef", "1234567890"
)
options.projectID = "demo-my-app"
options.APIKey = "AIzaSyD-emulator-only-not-a-real-key-00"   # 39 characters
options.storageBucket = "demo-my-app.appspot.com"
options.databaseURL = "https://demo-my-app-default-rtdb.firebaseio.com"
objc_class("FIRApp").configureWithOptions_(options)
```

!!! warning "The API key must look real"
    Firebase Installations (used by Remote Config, Messaging and Analytics)
    checks the API key's format, even with the emulators: it must be 39
    characters and start with `AIza`. A short fake key stops the app at
    launch.

## Products without an emulator

| Product | What to do in development |
|---|---|
| Remote Config | Use in-app defaults (`set_defaults`, a defaults plist); lower `minimum_fetch_interval` against a real project |
| App Check | The emulators do not check App Check tokens; use the debug provider against a real project |
| Analytics | Run with `-FIRDebugEnabled` and watch DebugView in the console |
| Crashlytics | Crash without the debugger attached, then launch again to send |
| Cloud Messaging | FCM does not reach the Simulator; `xcrun simctl push` delivers a test payload |
| Performance Monitoring | Run with `-FIRDebugEnabled` to see the traces sent |
| In-App Messaging | Send a test message to the device's installation ID ([how](../in-app-messaging/index.md#test-a-campaign-on-your-device)) |

## Clear the data between runs

```bash
# Firestore: every document
curl -X DELETE "http://127.0.0.1:8080/emulator/v1/projects/demo-my-app/databases/(default)/documents"
# Authentication: every account
curl -X DELETE "http://127.0.0.1:9099/emulator/v1/projects/demo-my-app/accounts"
# Realtime Database ("Bearer owner" goes past the security rules)
curl -X DELETE -H "Authorization: Bearer owner" \
  "http://127.0.0.1:9000/.json?ns=demo-my-app-default-rtdb"
```

The Auth emulator also exposes the codes it "sends" (email links, SMS codes)
over REST, so tests can finish email and phone sign-in without a real inbox
or phone. See [Authentication](../auth/index.md).

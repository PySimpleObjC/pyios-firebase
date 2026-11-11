# Installation

Two things go into your app:

1. **the Python package**, `pyios-firebase` (pure Python, with `rubicon-objc`);
2. **the Firebase iOS SDK packages** of the products you use, linked into the
   Xcode build like in any native app.

## 1. The Python package

```bash
pip install pyios-firebase
```

Add it to your app's requirements so the iOS build includes it:

=== "Kivy (kivyforge)"

    ```toml title="pyproject.toml"
    [project]
    dependencies = [
        "kivy",
        "pyios-firebase",
    ]
    ```

=== "Kivy (kivy-ios)"

    ```bash
    toolchain pip install pyios-firebase
    ```

=== "BeeWare (Briefcase)"

    ```toml title="pyproject.toml"
    [tool.briefcase.app.myapp]
    requires = [
        "pyios-firebase",
    ]
    ```

## 2. The Firebase packages

Add [firebase-ios-sdk](https://github.com/firebase/firebase-ios-sdk) with Swift
Package Manager, and choose the products you use:

| Module | Swift package product | Also needs |
|---|---|---|
| `core` | `FirebaseCore` (comes with every product) | `GoogleService-Info.plist` |
| `firestore` | `FirebaseFirestore` | |
| `auth` | `FirebaseAuth` | `GoogleSignIn` for `auth.google`, `FacebookLogin` for `auth.facebook`; URL schemes ([Authentication](../auth/index.md)) |
| `database` | `FirebaseDatabase` | |
| `functions` | `FirebaseFunctions` | |
| `storage` | `FirebaseStorage` | |
| `remote_config` | `FirebaseRemoteConfig` | |
| `app_check` | `FirebaseAppCheck` | The App Attest capability for App Attest |
| `analytics` | `FirebaseAnalytics` | |
| `crashlytics` | `FirebaseCrashlytics` | The dSYM upload run script |
| `messaging` | `FirebaseMessaging` | The Push Notifications capability, an APNs key in the console |
| `performance` | `FirebasePerformance` | |

The app must also link with **`-ObjC`** (`OTHER_LDFLAGS`): the Firebase
packages are static libraries, and without the flag the linker drops the
Objective-C classes that nothing in the native code refers to by name. Python
finds those classes at runtime, so it needs all of them.

=== "Kivy (kivyforge)"

    [kivyforge](https://github.com/ElliotGarbus/kivyforge) adds the packages
    and the settings from `pyproject.toml`:

    ```toml title="pyproject.toml"
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist"]

    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = [
        "FirebaseAuth",
        "FirebaseFirestore",
        "FirebaseStorage",
    ]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"
    ```

    This is how the library's own end-to-end test app is built
    ([`e2e/ios/pyproject.toml`](https://github.com/PySimpleObjC/pyios-firebase/blob/main/e2e/ios/pyproject.toml)).

=== "Kivy (kivy-ios)"

    1. Create the Xcode project: `toolchain create MyApp ~/code/myapp`.
    2. Open `myapp-ios/myapp.xcodeproj` in Xcode.
    3. **File > Add Package Dependencies...**, enter
       `https://github.com/firebase/firebase-ios-sdk.git`, and pick the
       products you use.
    4. In the target's **Build Settings**, add `-ObjC` to
       **Other Linker Flags**.
    5. Drag `GoogleService-Info.plist` into the project (target membership:
       your app).

=== "BeeWare (Briefcase)"

    1. Generate the Xcode project: `briefcase create iOS`.
    2. Open the project under `build/<app>/ios/xcode/` in Xcode.
    3. **File > Add Package Dependencies...**, enter
       `https://github.com/firebase/firebase-ios-sdk.git`, and pick the
       products you use.
    4. In the target's **Build Settings**, add `-ObjC` to
       **Other Linker Flags**.
    5. Add `GoogleService-Info.plist` to the app target.

    !!! warning
        `briefcase create` makes the Xcode project again from its template:
        changes made in Xcode are lost. Run it once, then use
        `briefcase update` and `briefcase build`.

!!! tip "A class is missing?"
    `NameError: ... FIRFirestore` (or another `FIR...` class) when you call a
    product means its package is not in the build, or `-ObjC` is missing.
    Importing a module never fails for this: classes are looked up the first
    time they are used.

## Package layout

```
pyios_firebase/
├── core/                configure(), default_app()
├── types.py             FirebaseError, callback types, QueryDict
├── util.py              value and error conversion, block keep-alive
├── firestore/           Firestore, references, snapshots, queries, FieldValue, Filter...
├── auth/                Auth, User, credentials and providers, AuthError
│   ├── google.py        Google Sign-In
│   ├── apple.py         Sign in with Apple
│   ├── facebook.py      Facebook Login
│   └── multi_factor.py  SMS and TOTP second factors
├── database/            Database, DatabaseReference, DatabaseQuery, DataSnapshot...
├── functions/           Functions, HTTPSCallable, FunctionsError
├── storage/             Storage, StorageReference, StorageMetadata, tasks
├── remote_config/       RemoteConfig, RemoteConfigValue, ConfigUpdate
├── app_check/           providers, AppCheck, AppCheckToken, AppCheckProvider
├── analytics/           Analytics, Event, Param, UserProperty, consent
├── crashlytics/         Crashlytics, ExceptionModel, StackFrame, CrashlyticsReport
├── messaging/           Messaging, MessagingError
│   └── notifications.py permission, handlers, Notification
└── performance/         Performance, Trace, HTTPMetric
```

Import from the product's subpackage:

```python
from pyios_firebase import core
from pyios_firebase.auth import Auth
from pyios_firebase.firestore import FieldValue, Filter, Firestore
```

## Next step

[Set up](setup.md) Firebase in your app.

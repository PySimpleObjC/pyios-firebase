# App configuration

Every product page has an **App configuration** section with what that product
needs in the app's build. This page puts them together: one app, every
product.

## What each product adds

Every app needs the base: `GoogleService-Info.plist` in the bundle, the
`firebase-ios-sdk` Swift package with the products you use, and `-ObjC` in
`OTHER_LDFLAGS`.

| Product | Swift package product | Also needs |
|---|---|---|
| [Firestore](../firestore/index.md#app-configuration) | `FirebaseFirestore` | |
| [Authentication](../auth/index.md#app-configuration) | `FirebaseAuth` | URL schemes; `GoogleSignIn` / `FacebookLogin` packages; entitlements for Apple, Game Center, Keychain Sharing |
| [Realtime Database](../database/index.md#app-configuration) | `FirebaseDatabase` | |
| [Cloud Functions](../functions/index.md#app-configuration) | `FirebaseFunctions` | |
| [Cloud Storage](../storage/index.md#app-configuration) | `FirebaseStorage` | |
| [Remote Config](../remote-config/index.md#app-configuration) | `FirebaseRemoteConfig` | `RemoteConfigDefaults.plist` in the bundle (optional) |
| [App Check](../app-check/index.md#app-configuration) | `FirebaseAppCheck` | The App Attest entitlement |
| [Analytics](../analytics/index.md#app-configuration) | `FirebaseAnalytics` | |
| [Crashlytics](../crashlytics/index.md#app-configuration) | `FirebaseCrashlytics` | The dSYM upload (Release builds make them; kivyforge: `upload-symbols` from the archive) |
| [Cloud Messaging](../messaging/index.md#app-configuration) | `FirebaseMessaging` | The `aps-environment` entitlement, `UIBackgroundModes` |
| [Performance Monitoring](../performance/index.md#app-configuration) | `FirebasePerformance` | |

## Everything together

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    # --- files in the app bundle ----------------------------------------------
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist", "RemoteConfigDefaults.plist"]

    # --- the Firebase iOS SDK: only the products you import ---------------------
    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = [
        "FirebaseAnalytics",
        "FirebaseAppCheck",
        "FirebaseAuth",
        "FirebaseCrashlytics",
        "FirebaseDatabase",
        "FirebaseFirestore",
        "FirebaseFunctions",
        "FirebaseMessaging",
        "FirebasePerformance",
        "FirebaseRemoteConfig",
        "FirebaseStorage",
    ]

    # --- Auth: Google Sign-In and Facebook Login --------------------------------
    [tool.kivy.ios.native.swift_packages.GoogleSignIn-iOS]
    url = "https://github.com/google/GoogleSignIn-iOS"
    requirement = { from = "10.1.0" }
    products = ["GoogleSignIn"]

    [tool.kivy.ios.native.swift_packages.facebook-ios-sdk]
    url = "https://github.com/facebook/facebook-ios-sdk.git"
    requirement = { from = "19.0.1" }
    products = ["FacebookLogin"]

    # --- build settings ---------------------------------------------------------
    [tool.kivy.ios.xcode.build_settings]
    # Python finds the SDK's classes at runtime
    OTHER_LDFLAGS = "$(inherited) -ObjC"

    # --- Info.plist -------------------------------------------------------------
    [tool.kivy.ios.info_plist]
    UIBackgroundModes = ["remote-notification"]      # Messaging
    FacebookAppID = "1234567890"                     # Facebook Login
    FacebookClientToken = "your-client-token"
    FacebookDisplayName = "My App"
    LSApplicationQueriesSchemes = ["fbapi", "fb-messenger-share-api"]
    # optional, to start with data collection off until the user agrees:
    # FIREBASE_ANALYTICS_COLLECTION_ENABLED = false
    # FirebaseCrashlyticsCollectionEnabled = false
    # firebase_performance_collection_enabled = false

    # URL schemes: Auth's callback (phone and web sign-in), Google Sign-In, Facebook
    [[tool.kivy.ios.info_plist.CFBundleURLTypes]]
    CFBundleTypeRole = "Editor"
    CFBundleURLSchemes = [
        "com.googleusercontent.apps.1234567890-abcdef",   # REVERSED_CLIENT_ID
        "fb1234567890",                                    # fb + FacebookAppID
    ]

    # --- entitlements (the provisioning profile must grant them) ---------------
    [tool.kivy.ios.entitlements]
    # Messaging ("production" to ship)
    "aps-environment" = "development"
    # Sign in with Apple
    "com.apple.developer.applesignin" = ["Default"]
    # App Check: App Attest
    "com.apple.developer.devicecheck.appattest-environment" = "production"
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**:
        - `https://github.com/firebase/firebase-ios-sdk.git`: pick the products you use;
        - `https://github.com/google/GoogleSignIn-iOS`: `GoogleSignIn` (Google Sign-In);
        - `https://github.com/facebook/facebook-ios-sdk.git`: `FacebookLogin` (Facebook Login).
    2. **Build Settings**: add `-ObjC` to *Other Linker Flags*; set *Debug Information Format* to *DWARF with dSYM File*.
    3. Add `GoogleService-Info.plist` (and `RemoteConfigDefaults.plist`) to the app target.
    4. **Info**: the URL types (the `REVERSED_CLIENT_ID`, `fb<APP_ID>`), the Facebook keys, `UIBackgroundModes` with `remote-notification`, and any optional keys.
    5. **Signing & Capabilities**: *Push Notifications*, *Background Modes > Remote notifications*, *Sign in with Apple*, *App Attest*.
    6. **Build Phases**: the Crashlytics run script ([Crashlytics](../crashlytics/index.md#app-configuration)).

    With Briefcase, run `briefcase create iOS` once, then change the generated
    Xcode project: running `create` again makes a new one.

## Good to know

- **Only what you import.** Each product you leave out of `products` makes
  the app smaller. Importing a pyios-firebase module never needs a framework
  you do not use.
- **The `REVERSED_CLIENT_ID` is the callback scheme too.** With Google
  Sign-In set up, phone and web sign-in use the same scheme. Without a client
  ID, use `app-` + your `GOOGLE_APP_ID` with `-` for `:`.
- **Entitlements need a matching profile.** Signing fails when the app asks
  for an entitlement its provisioning profile does not grant: turn the
  capabilities on for the App ID in the Apple Developer account first.
  kivyforge checks the profile before building.
- **Simulator builds** need no signing, so entitlements do not stop them, but
  the features behind them (push, App Attest) need a device.

## A tested configuration

pyios-firebase's end-to-end test app builds with kivyforge and runs about 80
tests in the iOS Simulator against the Firebase emulators. Its configuration is
a working starting point:
[`e2e/ios/pyproject.toml`](https://github.com/PySimpleObjC/pyios-firebase/blob/main/e2e/ios/pyproject.toml).
It has no `GoogleService-Info.plist` (it configures the demo project in code,
see [Emulator Suite](emulators.md#without-a-googleservice-infoplist)), and no
entitlements (the Simulator needs none).

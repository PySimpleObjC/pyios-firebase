# App Check

[App Check](https://firebase.google.com/docs/app-check) proves to Firebase
(and to your own backend) that a request comes from **your genuine app** on a
genuine device, not from a script that copied your API key. Firestore, the
Realtime Database, Storage, Functions, Auth and Remote Config can then refuse
requests without a valid token.

## Installation

1. Add the **`FirebaseAppCheck`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. In the console, open **App Check**, register the iOS app with **App
   Attest** (and/or **DeviceCheck**).
3. Choose the provider in the app, **before** `core.configure()`.
4. Watch the metrics in the console, then turn **enforcement** on for each
   product once the traffic is verified.

## Choose a provider

```python
from pyios_firebase import app_check, core

if app_check.running_in_simulator():
    app_check.use_debug_provider()         # the Simulator cannot attest
else:
    app_check.use_app_attest_provider()
core.configure()
```

| Provider | Function | Works on | Needs |
|---|---|---|---|
| App Attest | `use_app_attest_provider()` | Devices, iOS 14+ | The *App Attest* capability (`com.apple.developer.devicecheck.appattest-environment`) |
| DeviceCheck | `use_device_check_provider()` | Devices | Your DeviceCheck key in the console |
| reCAPTCHA Enterprise | `use_recaptcha_provider(site_key)` | Devices and the Simulator | The reCAPTCHA Enterprise SDK, a site key |
| Debug | `use_debug_provider()` | The Simulator, CI, development devices | A debug token registered in the console |
| Custom | `use_custom_provider(provider)` | Anywhere | Your own attestation service |

Setting a provider after `core.configure()` raises `RuntimeError`: Firebase
reads it only when the app is configured.

!!! tip "App Attest in production"
    App Attest has a development and a production environment, set by the
    entitlement. TestFlight and App Store builds must use `production`.

## The debug provider

For the Simulator and development builds:

1. Run the app with `use_debug_provider()`.
2. Copy the token from the console log:
   `Firebase App Check debug token: <token>`
   (or read `AppCheck.debug_token()` in the app).
3. In the console: **App Check > Apps > your app > Manage debug tokens**, add
   it.

In CI, set the token yourself, so it is the same on every run: pass the
environment variable **`FIRAAppCheckDebugToken`** to the app (with
`xcrun simctl launch`, as `SIMCTL_CHILD_FIRAAppCheckDebugToken=...`).

!!! danger
    Never ship the debug provider: anyone with the token passes App Check.

## Tokens for your own backend

```python
from pyios_firebase.app_check import AppCheck


def call_backend():
    def on_token(token, error):
        if error is None:
            post(url, headers={"X-Firebase-AppCheck": token.token})

    AppCheck.app_check().token(on_token)
```

Verify it on the server with the Admin SDK (`firebase_admin.app_check.verify_token`).

| Call | Gives |
|---|---|
| `token(callback, force_refresh=False)` | The cached token, or a new one when it expires |
| `limited_use_token(callback)` | A single-use token, for replay protection: the server consumes it |
| `add_token_listener(listener)` | Calls `listener(token)` on every refresh; `.remove()` stops |

Tokens are **cached across launches**: `force_refresh=True` asks the provider
for a new one. `token.expiration_date` is a UTC `datetime`.

## A custom provider in Python

For your own attestation (a device-integrity service, a hardware key...):

```python
from datetime import UTC, datetime, timedelta

from pyios_firebase.app_check import AppCheckProvider, AppCheckToken


class MyProvider(AppCheckProvider):
    def get_token(self, callback):
        def on_response(response, error):
            if error is not None:
                callback(None, str(error))          # a message: App Check reports it
                return
            expires = datetime.now(UTC) + timedelta(seconds=response["ttl"])
            callback(AppCheckToken(response["token"], expires), None)

        my_attestation_service.request_token(on_response)

    # optional: by default, limited-use tokens come from get_token
    def get_limited_use_token(self, callback):
        ...


app_check.use_custom_provider(MyProvider())
```

Your server makes the token: a JWT signed with a key you registered as a
custom provider in the console. `callback` must be called exactly once; if
`get_token` raises, App Check gets an error instead. To make one provider per
Firebase app, pass a factory: `use_custom_provider(lambda app: MyProvider())`.

## Settings

```python
AppCheck.app_check().is_token_auto_refresh_enabled = False   # stop refreshing in the background
```

`FirebaseAppCheckTokenAutoRefreshEnabled` = `NO` in `Info.plist` sets it at
build time.

## Errors

| `AppCheckErrorCode` | Means |
|---|---|
| `SERVER_UNREACHABLE` | No network, or the App Check server is down |
| `INVALID_CONFIGURATION` | The app is not registered for this provider, or the debug token is unknown |
| `KEYCHAIN` | The keychain is not reachable |
| `UNSUPPORTED` | The provider does not work here (App Attest in the Simulator) |
| `UNKNOWN` | Anything else, including errors from a custom provider |

## The emulators

The Firebase emulators do not check App Check tokens, so any provider works
against them.

---
title: Firebase for Python on iOS
hide:
  - navigation
  - toc
  - feedback
---

<div class="pf-hero" markdown>

![pyios-firebase](assets/logo.svg)

# pyios-firebase

<p class="pf-tagline">Firebase for Python apps on iOS: Kivy, BeeWare and any framework that runs Rubicon-ObjC. Pure Python, fully typed, tested on the iOS Simulator.</p>

[Get started](getting-started/index.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/PySimpleObjC/pyios-firebase){ .md-button }

<div class="pf-install" markdown>

```bash
pip install pyios-firebase
```

</div>

</div>

```python
from pyios_firebase import core
from pyios_firebase.firestore import Firestore

core.configure()

def on_city(snapshot, error):
    if error is None:
        print(snapshot.data)            # plain Python: dict, datetime, list...

Firestore.firestore().document_with_path("cities/SF").get_document(on_city)
```

## Products

<div class="grid cards" markdown>

-   :material-database-outline:{ .lg .middle } **Cloud Firestore**

    ---

    Documents and queries, live listeners, batches, transactions and aggregates, with Python values in and out.

    [:octicons-arrow-right-24: Usage](firestore/index.md) · [Reference](firestore/reference.md)

-   :material-account-key-outline:{ .lg .middle } **Authentication**

    ---

    Every iOS sign-in method: email, phone, Google, Apple, Facebook, OAuth providers, multi-factor.

    [:octicons-arrow-right-24: Usage](auth/index.md) · [Reference](auth/reference.md)

-   :material-file-tree-outline:{ .lg .middle } **Realtime Database**

    ---

    A JSON tree synced live: listeners, queries, transactions, presence and offline persistence.

    [:octicons-arrow-right-24: Usage](database/index.md) · [Reference](database/reference.md)

-   :material-function-variant:{ .lg .middle } **Cloud Functions**

    ---

    Call HTTPS callable functions by name, URL or region, with typed errors and their details.

    [:octicons-arrow-right-24: Usage](functions/index.md) · [Reference](functions/reference.md)

-   :material-folder-image:{ .lg .middle } **Cloud Storage**

    ---

    Uploads and downloads with progress, pause and resume; metadata, listing and download URLs.

    [:octicons-arrow-right-24: Usage](storage/index.md) · [Reference](storage/reference.md)

-   :material-tune-variant:{ .lg .middle } **Remote Config**

    ---

    In-app defaults, fetch and activate, typed values, real-time updates and custom signals.

    [:octicons-arrow-right-24: Usage](remote-config/index.md) · [Reference](remote-config/reference.md)

-   :material-shield-check-outline:{ .lg .middle } **App Check**

    ---

    App Attest, DeviceCheck, reCAPTCHA, the debug provider, and custom providers written in Python.

    [:octicons-arrow-right-24: Usage](app-check/index.md) · [Reference](app-check/reference.md)

-   :material-chart-line:{ .lg .middle } **Analytics**

    ---

    Events with every SDK name, screen views, e-commerce, user properties and consent mode.

    [:octicons-arrow-right-24: Usage](analytics/index.md) · [Reference](analytics/reference.md)

-   :material-bug-outline:{ .lg .middle } **Crashlytics**

    ---

    Crash reports, and Python exceptions as issues with their Python stack frames.

    [:octicons-arrow-right-24: Usage](crashlytics/index.md) · [Reference](crashlytics/reference.md)

-   :material-bell-ring-outline:{ .lg .middle } **Cloud Messaging**

    ---

    The FCM token, topics, notification permission, and notifications handled in Python.

    [:octicons-arrow-right-24: Usage](messaging/index.md) · [Reference](messaging/reference.md)

-   :material-message-badge-outline:{ .lg .middle } **In-App Messaging**

    ---

    Firebase's messages inside the app, their clicks and dismissals in Python, or drawn with your own UI.

    [:octicons-arrow-right-24: Usage](in-app-messaging/index.md) · [Reference](in-app-messaging/reference.md)

-   :material-speedometer:{ .lg .middle } **Performance Monitoring**

    ---

    Custom traces with metrics and attributes, and HTTP metrics for requests made from Python.

    [:octicons-arrow-right-24: Usage](performance/index.md) · [Reference](performance/reference.md)

-   :material-cog-outline:{ .lg .middle } **Core and helpers**

    ---

    Start Firebase, the shared error and callback types, and the value conversion helpers.

    [:octicons-arrow-right-24: Setup](getting-started/setup.md) · [Reference](reference/core.md)

</div>

## Why pyios-firebase

<div class="grid cards" markdown>

-   :material-language-python:{ .lg .middle } **Pure Python**

    ---

    No Objective-C or Swift to write. It talks to the Firebase iOS SDK through Rubicon-ObjC, and keeps callback blocks alive for you.

-   :material-check-decagram-outline:{ .lg .middle } **Fully typed**

    ---

    Type hints and docstrings on every public class and method, so editors autocomplete and mypy or pyright check your calls.

-   :material-shield-alert-outline:{ .lg .middle } **No surprise aborts**

    ---

    Where the SDK would abort the whole app (a bad database path, a non-JSON value), you get a Python exception instead.

-   :material-cellphone-check:{ .lg .middle } **Tested on iOS**

    ---

    Every product runs end to end in the iOS Simulator against the real SDK and the Firebase emulators.

</div>

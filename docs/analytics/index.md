# Analytics

[Google Analytics for Firebase](https://firebase.google.com/docs/analytics)
counts what users do in the app: events you log, screens they see, and
properties that describe them. Other products build on it: Remote Config and
Messaging can target audiences, Crashlytics shows crash-free users.

```python
from pyios_firebase.analytics import Analytics, Event, Param

Analytics.log_event(Event.SELECT_CONTENT, {Param.CONTENT_TYPE: "image", Param.ITEM_ID: "P12453"})
Analytics.log_screen_view("Checkout", "CheckoutScreen")
Analytics.set_user_property("premium", "plan")
```

## Installation

1. Add the **`FirebaseAnalytics`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. Link the project to Google Analytics in the console (**Project settings >
   Integrations**).

The SDK logs some events by itself: `first_open`, `session_start`,
`app_update`, `os_update`, `screen_view` for native screens, and in-app
purchases.

### App configuration

What the app's build needs for this product. To combine several products, list
them all in one `products`; see [App configuration](../getting-started/configuration.md).

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist"]

    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = ["FirebaseAnalytics"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"

    # optional: start with collection off, until the user agrees
    [tool.kivy.ios.info_plist]
    FIREBASE_ANALYTICS_COLLECTION_ENABLED = false
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseAnalytics`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.
    4. Optional, in **Info**: `FIREBASE_ANALYTICS_COLLECTION_ENABLED` = `NO`.
    5. To see events in DebugView: **Product > Scheme > Edit Scheme > Run > Arguments**, add `-FIRDebugEnabled`.

!!! note
    `-FIRDebugEnabled` is a launch argument: with `xcrun simctl launch`, pass it after the bundle ID.


## Log events

```python
Analytics.log_event(Event.LOGIN, {Param.METHOD: "google"})
Analytics.log_event("level_up", {"level": 3, "character": "wizard"})     # your own
```

`Event`, `Param` and `UserProperty` hold **every name the SDK defines** (112,
generated from its headers): use them when one fits, so reports understand
the event.

| Rule | |
|---|---|
| Event names | 1 to 40 letters, digits and `_`, starting with a letter |
| Reserved | Prefixes `firebase_`, `google_`, `ga_`; names the SDK logs itself (`first_open`, `session_start`, `app_update`...) |
| Parameters | Up to 25 per event; names like event names |
| Values | `str` (up to 100 characters), `int`, `float`; a list of item dicts for `Param.ITEMS` |

The SDK **drops** a bad event and only logs a line in the console.
pyios-firebase raises `ValueError` (a bad or reserved name, too many
parameters) or `TypeError` (a `bool`, `None` or other value) instead, so
mistakes show while you develop.

!!! tip "No `bool` parameters"
    Analytics has no boolean type. Send `1` / `0`, or `"true"` / `"false"`.

## Screen views

Screen views are not logged by themselves for Kivy or Toga screens: the SDK
sees only the one `UIViewController` behind them. Log them when a screen opens:

```python
from kivy.uix.screenmanager import Screen


class CheckoutScreen(Screen):
    def on_enter(self):
        Analytics.log_screen_view("Checkout", type(self).__name__)
```

## E-commerce

Pass the products in `Param.ITEMS`, a list of item dicts:

```python
item = {
    Param.ITEM_ID: "SKU_123",
    Param.ITEM_NAME: "Jeggings",
    Param.ITEM_CATEGORY: "pants",
    Param.PRICE: 9.99,
    Param.QUANTITY: 2,
}

Analytics.log_event(Event.ADD_TO_CART, {Param.CURRENCY: "USD", Param.VALUE: 19.98, Param.ITEMS: [item]})
Analytics.log_event(
    Event.PURCHASE,
    {
        Param.TRANSACTION_ID: "T_12345",
        Param.CURRENCY: "USD",
        Param.VALUE: 19.98,
        Param.TAX: 1.60,
        Param.SHIPPING: 0.0,
        Param.ITEMS: [item],
    },
)
```

The usual funnel: `VIEW_ITEM_LIST`, `SELECT_ITEM`, `VIEW_ITEM`, `ADD_TO_CART`,
`BEGIN_CHECKOUT`, `ADD_SHIPPING_INFO`, `ADD_PAYMENT_INFO`, `PURCHASE`,
`REFUND`.

## User properties and the user ID

```python
Analytics.set_user_property("premium", "plan")       # value, then name
Analytics.set_user_property(None, "plan")            # remove
Analytics.set_user_id(uid)                           # your ID for the user; never an email
```

User property names are up to 24 characters, values up to 36. Register a
property in the console (**Custom definitions**) to see it in reports.

## Default event parameters

Parameters added to every event from now on (kept across launches):

```python
Analytics.set_default_event_parameters({"app_flavor": "pro", "experiment": "b"})
Analytics.set_default_event_parameters({"experiment": None})     # remove one
Analytics.set_default_event_parameters(None)                     # remove all
```

## Consent and collection

```python
from pyios_firebase.analytics import ConsentStatus, ConsentType

Analytics.set_consent({
    ConsentType.ANALYTICS_STORAGE: ConsentStatus.GRANTED,
    ConsentType.AD_STORAGE: ConsentStatus.DENIED,
    ConsentType.AD_USER_DATA: ConsentStatus.DENIED,
    ConsentType.AD_PERSONALIZATION: ConsentStatus.DENIED,
})

Analytics.set_analytics_collection_enabled(False)    # stop collecting (kept across launches)
Analytics.reset_analytics_data()                     # clear this device's data and ID
```

To start with collection **off** until the user agrees, set
`FIREBASE_ANALYTICS_COLLECTION_ENABLED` = `NO` in `Info.plist`, then turn it on
with `set_analytics_collection_enabled(True)`.

## Sessions and IDs

```python
Analytics.set_session_timeout_interval(1800)         # seconds of inactivity (the default)
Analytics.app_instance_id()                          # this install's ID (None without consent)


def on_session(session_id, error):
    print(session_id)                                 # runs on a background thread


Analytics.session_id(on_session)
```

## See your events

Reports take up to a day. To see events as they are logged:

1. Run the app with the argument **`-FIRDebugEnabled`** (Xcode: **Product >
   Scheme > Edit Scheme > Run > Arguments**).
2. Open **DebugView** in the console.

`-FIRDebugDisabled` turns it off again.

## On-device conversion measurement

For Google Ads, from data the user agreed to share (needs the
`GoogleAdsOnDeviceConversion` package; otherwise it does nothing):

```python
Analytics.initiate_on_device_conversion_measurement(email_address="ada@example.com")
# or phone_number="+15555550100", hashed_email_address=sha256_bytes, hashed_phone_number=sha256_bytes
```

## When app delegate swizzling is off

With `FirebaseAppDelegateProxyEnabled` = `NO`, tell Analytics about the URLs
the app is opened with: `Analytics.handle_open_url(url)` and
`Analytics.handle_user_activity(activity)`.

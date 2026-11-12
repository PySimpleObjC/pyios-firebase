# In-App Messaging

[Firebase In-App Messaging](https://firebase.google.com/docs/in-app-messaging)
shows messages **inside the app while it is open**: a banner, a dialog, a
card or an image, made as campaigns in the Firebase console (**Engage >
Messaging**, *In-app message*). Firebase fetches the campaigns and shows their
messages by itself, with its own screens: the app only has to include the
framework.

```python
from pyios_firebase.in_app_messaging import InAppMessaging

iam = InAppMessaging.in_app_messaging()
iam.add_click_listener(lambda message, action: open_screen(action.url))
iam.trigger_event("level_done")          # show the campaigns of this event
```

!!! note "Not the same product as Cloud Messaging"
    [Cloud Messaging](../messaging/index.md) (FCM) sends **push
    notifications**, which arrive even when the app is closed. In-App
    Messaging shows messages **only while the app is in use**, and needs no
    push setup, permission or APNs key.

## Installation

Add the **`FirebaseInAppMessaging-Beta`** Swift package product
([Installation](../getting-started/installation.md)). Add
**`FirebaseAnalytics`** too: campaigns triggered by Analytics events, and the
impression and click statistics in the console, need it.

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
    products = ["FirebaseInAppMessaging-Beta", "FirebaseAnalytics"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"

    # optional: fetch no messages until the user agrees
    [tool.kivy.ios.info_plist]
    FirebaseInAppMessagingAutomaticDataCollectionEnabled = false
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseInAppMessaging-Beta`** and **`FirebaseAnalytics`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.
    4. Optional, in **Info**: `FirebaseInAppMessagingAutomaticDataCollectionEnabled` = `NO`.

!!! tip "The \"-Beta\" in the name"
    It is only the Swift package product's name: the API is stable, and
    Firebase has shipped the product for years under it.

## When messages show

| Trigger (set on the campaign) | When |
|---|---|
| **On app foreground** (`TriggerType.ON_APP_FOREGROUND`) | The app opens, or comes back to the foreground |
| **On an Analytics event** (`TriggerType.ON_ANALYTICS_EVENT`) | The app logs that event, or calls `trigger_event` with its name |

```python
from pyios_firebase.analytics import Analytics

Analytics.log_event("purchase", {"value": 9.99})   # an Analytics event triggers campaigns
iam.trigger_event("level_done")                    # or trigger them without logging an event
```

Firebase shows **one message at a time**, at most one *on app foreground*
message every 24 hours, and each campaign as often as its frequency limit
(set in the console) allows. Messages show over every window, the Kivy or
Toga one included.

### Not now

Stop messages during a payment, a video or a game level:

```python
iam.message_display_suppressed = True
...
iam.message_display_suppressed = False
```

It is `False` at every launch: the setting is not kept.

## What the user does with a message

```python
from pyios_firebase.in_app_messaging import DismissType, InAppMessaging

iam = InAppMessaging.in_app_messaging()


def on_click(message, action):
    # action.text: the button's text (None for a tap on a banner or an image)
    # action.url: the URL set on the campaign, or None
    print("tapped", message.campaign.campaign_name, action.url)


def on_dismiss(message, dismiss_type):
    if dismiss_type == DismissType.USER_SWIPE:
        print("swiped away")


iam.add_impression_listener(lambda message: print("seen", message.campaign.message_id))
iam.add_click_listener(on_click)
iam.add_dismiss_listener(on_dismiss)
iam.add_error_listener(lambda message, error: print("not shown:", error.description))
```

Each `add_*_listener` returns a function that removes the listener. Listeners
run on the main thread (Kivy's).

An **impression** is counted after the message was on screen for 3 seconds.
After a click, Firebase opens the action's URL by itself: a web page in
Safari, or a link to the app.

!!! tip "Deep links to a screen of the app"
    Give the campaign an action URL such as `myapp://shop`, and open the
    screen from the click listener with `action.url`. A Kivy app's Python
    does not get URLs the app delegate receives, so do not rely on the
    opened URL reaching it.

### Custom data

Key-value pairs set on the campaign (**Additional options > Custom data**)
are in `message.app_data`:

```python
def on_click(message, action):
    if message.app_data.get("coupon"):
        apply_coupon(message.app_data["coupon"])
```

## The messages

Listeners and [custom displays](#show-messages-your-way) get one of these:

| Class | Layout | Fields |
|---|---|---|
| `ModalMessage` | A dialog | `title`, `body`, `image`, `action_button`, `action_url`, `text_color`, `background_color` |
| `BannerMessage` | A strip at the top | `title`, `body`, `image`, `action_url`, `text_color`, `background_color` |
| `CardMessage` | A card | `title`, `body`, `portrait_image`, `landscape_image`, `primary_button`, `primary_action_url`, `secondary_button`, `secondary_action_url`, `text_color`, `background_color` |
| `ImageOnlyMessage` | Only an image | `image`, `action_url` |

All of them have `campaign` (`message_id`, `campaign_name`,
`render_as_test_message`), `type` (a `MessageType`), `trigger_type` and
`app_data`. Colors are `"#RRGGBB"` strings (`"#RRGGBBAA"` when not opaque).
An `ImageData` has the `image_url` and the downloaded file (`image_data`,
bytes). An `ActionButton` has `text`, `text_color` and `background_color`.

## Show messages your way

Firebase's screens are UIKit views. To draw the messages with your own UI (a
Kivy popup, a Toga window), give a **display handler**:

```python
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from pyios_firebase.in_app_messaging import DismissType, InAppMessaging, ModalMessage


def show(message, delegate):
    if not isinstance(message, ModalMessage):
        delegate.failed(description="this app only shows dialogs")
        return
    content = BoxLayout(orientation="vertical")
    content.add_widget(Label(text=message.body or ""))
    popup = Popup(title=message.title, content=content, auto_dismiss=False)
    if message.action_button:
        button = Button(text=message.action_button.text)

        def tapped(_button):
            popup.dismiss()
            delegate.clicked()  # the button's text and the message's URL

        button.bind(on_release=tapped)
        content.add_widget(button)
    close = Button(text="Close")

    def closed(_button):
        popup.dismiss()
        delegate.dismissed(DismissType.USER_TAP_CLOSE)

    close.bind(on_release=closed)
    content.add_widget(close)
    popup.open()
    delegate.impression()  # count it as seen


InAppMessaging.in_app_messaging().set_display(show)
```

The handler runs on the main thread. Tell Firebase what happened through the
`DisplayDelegate`:

| Call | When |
|---|---|
| `delegate.impression()` | The message is on screen (counted once) |
| `delegate.clicked(action=None)` | The user tapped the action. Without `action`: the message's main action (its button, or a card's primary one, and its URL) |
| `delegate.dismissed(dismiss_type)` | The user closed it, or it timed out (`DismissType.AUTO`) |
| `delegate.failed(code, description)` | It could not be shown |

Call **exactly one** of `clicked`, `dismissed` or `failed` per message:
until then Firebase shows no other message. A second one raises
`RuntimeError`. If the handler raises, the message counts as failed.

The listeners get the same events, from either display.

```python
iam.use_default_display()   # Firebase's screens again
iam.set_display(None)       # show nothing at all (messages are not counted)
```

## Privacy

```python
iam.automatic_data_collection_enabled = False   # kept across launches
```

While it is off, Firebase fetches no messages (and sends no data for them).
To start with it off, set `FirebaseInAppMessagingAutomaticDataCollectionEnabled`
to `NO` in `Info.plist`, and turn it on once the user agrees. Without either,
it follows Firebase's global setting (`FirebaseDataCollectionDefaultEnabled`
in `Info.plist`), read once at start-up.

## Test a campaign on your device

1. Run the app with **`-FIRDebugEnabled`** (Xcode: **Product > Scheme >
   Edit Scheme > Run > Arguments**), and find this line in the log:
   `[Firebase/InAppMessaging][I-IAM180017] Starting InAppMessaging runtime with Firebase Installation ID ...`
2. In the console, open the campaign and choose **Test on device**; paste
   that installation ID.
3. Put the app in the background and open it again: the test message shows
   (`message.campaign.render_as_test_message` is `True`; it does not count in
   the campaign's statistics).

Campaigns are fetched at most once every 24 hours, so a new campaign can
take a day to reach a device. The exceptions: a newly installed app fetches
at each of its first 5 launches or foregrounds, and a device that got a
test message fetches at every foreground from then on.

## Mistakes

| Mistake | Raises |
|---|---|
| `trigger_event("")`, a name that is not a `str` | `ValueError`, `TypeError` |
| A second `clicked` / `dismissed` / `failed` for one message | `RuntimeError` |
| `InAppMessaging.in_app_messaging()` before `core.configure()` | `RuntimeError` (the SDK gives nothing) |
| `InAppMessaging.in_app_messaging()` without the `FirebaseInAppMessaging-Beta` framework | `NameError` |

## No emulator

The Firebase emulators do not serve In-App Messaging. Use test messages on a
device or the Simulator against a real project (see above). The
end-to-end tests of this repository check Firebase's default display with a
message built in the test, over the Kivy window.

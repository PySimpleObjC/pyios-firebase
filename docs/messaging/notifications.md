# Notifications

`pyios_firebase.messaging.notifications` asks for permission, registers with
APNs, and calls your Python code when a notification arrives with the app
open, or when the user taps one. It uses Apple's notification center
(`UserNotifications`), so it works for any push, from FCM or not.

```python
from pyios_firebase.messaging import notifications
from pyios_firebase.messaging.notifications import AuthorizationOptions, PresentationOptions
```

## Set the handlers first

Set them **early**, before `App.run()`. In a Kivy app, also add the
[launch hook](#when-the-app-is-closed) to get the tap that opens a closed app.

```python
def on_foreground(notification):
    """A notification arrived while the app is open."""
    if notification.data.get("screen") == current_screen():
        refresh()
        return None                                       # do not show it
    return PresentationOptions.BANNER | PresentationOptions.SOUND


def on_open(notification, action):
    """The user tapped it (action is DEFAULT_ACTION), or one of its buttons."""
    go_to(notification.data.get("screen"), notification.data.get("order_id"))


notifications.set_handlers(on_foreground=on_foreground, on_open=on_open)
```

| Handler | Called | Returns |
|---|---|---|
| `on_foreground(notification)` | A notification arrives with the app in the foreground | `PresentationOptions` to show it, or `None` / `0` to keep it quiet |
| `on_open(notification, action)` | The user taps the notification or an action button | Nothing |

Without an `on_foreground`, foreground notifications use
`default_presentation` (`set_handlers(default_presentation=PresentationOptions.BANNER)`),
and are not shown by default. The handlers run on the main thread.

`set_handlers` makes pyios-firebase the notification center's delegate,
replacing any other.

## When the app is closed

What `on_open` gets depends on whether the app was running when the user
tapped:

| The app was... | The tap opens the app | `on_open` gets the notification |
|---|---|---|
| Open (in front) | (it is open) | Yes |
| In the background | Yes | Yes |
| **Closed** (not running), BeeWare / Toga | Yes | Expected, with `set_handlers` in `startup()`: Python starts before launch there (not tested yet) |
| **Closed** (not running), **Kivy** | Yes | **Only with the launch hook below** |

**Why Kivy needs a hook.** When a tap launches the app, iOS delivers it
*during* launch. A Kivy app's Python starts only *after* launch (SDL starts the
interpreter), so no handler exists yet: iOS drops the tap
(`response-not-possible` in the system log). The app opens, but cannot know
which notification was tapped. No Python code can run early enough to catch
it.

### The launch hook

[pyios-firebase-notifications-hook](https://github.com/PySimpleObjC/pyios-firebase-notifications-hook)
is a tiny optional Swift package (one Objective-C file). It starts before
Python, sets a notification handler before launch ends, and keeps the tap.
`set_handlers(on_open=...)` then passes it to your `on_open`, as soon as the
app's event loop runs. **You write no new code**: add the package, and keep
calling `set_handlers`.

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    [tool.kivy.ios.native.swift_packages.PyiosFirebaseNotificationsHook]
    url = "https://github.com/PySimpleObjC/pyios-firebase-notifications-hook.git"
    requirement = { from = "0.1.0" }
    products = ["PyiosFirebaseNotificationsHook"]
    ```

=== "Xcode (kivy-ios)"

    **File > Add Package Dependencies...**, enter
    `https://github.com/PySimpleObjC/pyios-firebase-notifications-hook.git`, and
    add the `PyiosFirebaseNotificationsHook` product to the app target.

```python
from pyios_firebase.messaging import notifications

notifications.set_handlers(on_open=on_open)       # before App.run(), as always
print(notifications.launch_hook_status())          # "ok: SDLUIKitSceneDelegate"
```

| `launch_hook_status()` | Means |
|---|---|
| `None` | The hook is not in the app: a tap that launches a Kivy app does not reach `on_open` |
| `"ok: SDLUIKitSceneDelegate"` (or another class) | The hook is keeping launch taps |

Good to know:

- The `Notification` is the same as for any other tap: title, body, data, FCM
  message ID, identifier and date.
- Without `on_open` yet, the tap stays in the hook until a `set_handlers` call
  with one.
- For taps the hook kept, pyios-firebase also tells Firebase Messaging the
  notification was opened (for its statistics), once Firebase is configured.
- The hook never replaces a notification handler your app set itself. Toga
  apps should not need it (see the table).
- Tested end to end in the iOS Simulator: the app is closed, a notification is
  pushed, the banner is tapped, and `on_open` gets its data.

## Ask permission

```python
def on_answer(granted, error):          # on a background thread
    if granted:
        Clock.schedule_once(lambda dt: notifications.register_for_remote_notifications())


notifications.request_permission(
    AuthorizationOptions.ALERT | AuthorizationOptions.BADGE | AuthorizationOptions.SOUND,
    on_answer,
)
```

iOS asks the user **once**; later calls give the first answer without asking.
Ask when the user sees why (after they subscribed to something), not at the
first launch.

Call `register_for_remote_notifications()` at **every** launch, on the main
thread: it gets the APNs token, which Firebase forwards to FCM.

| `AuthorizationOptions` | |
|---|---|
| `ALERT`, `BADGE`, `SOUND` | The usual ones |
| `PROVISIONAL` | Granted **without asking**: notifications go quietly to Notification Center until the user chooses |
| `CRITICAL_ALERT` | Sounds even in Do Not Disturb (needs an entitlement from Apple) |
| `PROVIDES_APP_NOTIFICATION_SETTINGS` | Adds a link to your settings screen in the system settings |

The current permission:

```python
from pyios_firebase.messaging.notifications import AuthorizationStatus


def on_status(status):                  # on a background thread
    if status == AuthorizationStatus.DENIED:
        Clock.schedule_once(lambda dt: show_hint("Turn notifications on in Settings"))


notifications.authorization_status(on_status)
```

## What a notification holds

| `Notification` field | |
|---|---|
| `title`, `subtitle`, `body` | The alert's text |
| `badge` | The badge number, or `None` |
| `data` | The whole payload: the `aps` dictionary and the message's data keys |
| `message_id` | The FCM message ID (`"gcm.message_id"`), or `None` for pushes from elsewhere |
| `identifier`, `category`, `thread_id` | The request's identifier, category and thread |
| `date` | When it was delivered (UTC) |

Data sent with `data={...}` from the server arrives as keys of
`notification.data`, as strings.

## Kinds of messages

| Message | App in the foreground | App in the background or closed |
|---|---|---|
| **Notification** (`notification=...`, with or without `data`) | `on_foreground`, then shown as you return | Shown by iOS; `on_open` when tapped |
| **Data only** (`data=...`, `content_available=True`) | Delivered to the app delegate | Delivered to the app delegate, if iOS lets the app run |

!!! warning "Data-only messages"
    Data-only (silent) messages go to the app delegate's
    `application:didReceiveRemoteNotification:fetchCompletionHandler:`,
    which belongs to the app's native code (SDL's in a Kivy app), not to
    Python. Send data **with** a notification, or read it when the user opens
    the app.

Images in notifications need a *Notification Service Extension*, a separate
native target (Swift or Objective-C): not something Python can provide.

## Test on the Simulator

FCM does not deliver to the Simulator, but `xcrun simctl push` does deliver
a payload, to the same handlers:

```json title="push.json"
{
  "aps": { "alert": { "title": "Sale", "body": "50% off today" }, "badge": 3 },
  "gcm.message_id": "test-1",
  "screen": "shop"
}
```

```bash
xcrun simctl push booted com.example.myapp push.json
```

Use `PROVISIONAL` permission in automated tests: it needs no tap on the
permission dialog. pyios-firebase's end-to-end tests deliver a notification
this way and check that it reaches `on_foreground`.

## Delivery analytics

Firebase records what arrives and what is opened for the console's reports,
by itself. With `FirebaseAppDelegateProxyEnabled` = `NO`, tell it yourself:

```python
Messaging.messaging().app_did_receive_message(notification.data)
```

FCM counts each message once, even if this is called twice.

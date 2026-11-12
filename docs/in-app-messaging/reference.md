# In-App Messaging reference

## At a glance

- `InAppMessaging.in_app_messaging()`: `message_display_suppressed`, `automatic_data_collection_enabled`, `trigger_event(name)`
- Listeners: `add_impression_listener(fn(message))`, `add_click_listener(fn(message, action))`, `add_dismiss_listener(fn(message, dismiss_type))`, `add_error_listener(fn(message, error))`; each returns a function that removes it
- Your own display: `set_display(handler(message, delegate))`, `use_default_display()`; `DisplayDelegate`: `impression()`, `clicked(action=None)`, `dismissed(dismiss_type)`, `failed(code, description)`, `finished`
- Messages: `ModalMessage`, `BannerMessage`, `CardMessage`, `ImageOnlyMessage` (all `InAppMessage`: `campaign`, `type`, `trigger_type`, `app_data`); `CampaignInfo`, `ImageData`, `ActionButton`, `Action`, `default_action(message)`
- Constants: `MessageType`, `TriggerType`, `DismissType`, `InAppMessagingErrorCode`; errors are `InAppMessagingError`


## `pyios_firebase.in_app_messaging`

::: pyios_firebase.in_app_messaging

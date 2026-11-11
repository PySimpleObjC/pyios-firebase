# Cloud Messaging reference

## At a glance

- `Messaging.messaging()`: `add_token_listener(listener)`, `add_registration_listener`, `add_unregistration_listener` (each returns a remove function); `token(cb)`, `fcm_token`, `delete_token(cb)`, `retrieve_fcm_token(sender_id, cb)`, `delete_fcm_token(sender_id, cb)`, `auto_init_enabled`, `installation_id_enabled`, `register(cb)`, `unregister(cb)`, `delete_data(cb)`, `subscribe_to_topic(topic, cb)`, `unsubscribe_from_topic(topic, cb)`, `apns_token`, `set_apns_token(token, type)`, `app_did_receive_message(user_info)`
- `MessagingError` (`name`), `MessagingErrorCode`, `APNSTokenType`, `MessagingMessageStatus`, `MESSAGING_ERROR_DOMAIN`
- `notifications`: `request_permission(options, cb)`, `authorization_status(cb)`, `register_for_remote_notifications()`, `set_handlers(on_foreground, on_open, *, default_presentation)`; `Notification` (`identifier`, `title`, `subtitle`, `body`, `badge`, `data`, `category`, `thread_id`, `date`, `message_id`); `AuthorizationOptions`, `AuthorizationStatus`, `PresentationOptions`, `DEFAULT_ACTION`, `DISMISS_ACTION`

## `pyios_firebase.messaging`

::: pyios_firebase.messaging

## `pyios_firebase.messaging.notifications`

::: pyios_firebase.messaging.notifications

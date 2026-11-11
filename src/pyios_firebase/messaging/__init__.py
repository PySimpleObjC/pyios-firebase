"""Firebase Cloud Messaging: push notifications and messages to this device.

    from pyios_firebase.messaging import Messaging

    messaging = Messaging.messaging()
    messaging.add_token_listener(lambda token: send_to_my_server(token))
    messaging.subscribe_to_topic("news", lambda error: ...)

To ask for permission and handle the notifications that arrive, see
``pyios_firebase.messaging.notifications``.

The app needs the Push Notifications capability, and an APNs key uploaded in
the Firebase console. Messages do not reach the iOS Simulator from FCM (only
``xcrun simctl push`` test payloads do).

Needs the ``FirebaseMessaging`` framework.
"""

from . import notifications
from .messaging import (
    MESSAGING_ERROR_DOMAIN,
    APNSTokenType,
    Messaging,
    MessagingError,
    MessagingErrorCode,
    MessagingMessageStatus,
)

__all__ = (
    "MESSAGING_ERROR_DOMAIN",
    "APNSTokenType",
    "Messaging",
    "MessagingError",
    "MessagingErrorCode",
    "MessagingMessageStatus",
    "notifications",
)

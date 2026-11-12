"""Firebase In-App Messaging: messages shown inside the app, from campaigns
made in the Firebase console.

Not the same product as Cloud Messaging (``pyios_firebase.messaging``): these
messages are not push notifications; they show while the app is open.

Firebase fetches the campaigns and shows their messages by itself, with its
own screens, when the app comes to the foreground or on an Analytics event::

    from pyios_firebase.in_app_messaging import InAppMessaging

    iam = InAppMessaging.in_app_messaging()
    iam.add_click_listener(lambda message, action: open_screen(action.url))
    iam.trigger_event("level_done")          # show the campaigns of this event
    iam.message_display_suppressed = True    # not now (for example mid-game)

To draw the messages yourself (a Kivy popup...), see
``InAppMessaging.set_display``.

Needs the ``FirebaseInAppMessaging-Beta`` Swift package product.
"""

from .in_app_messaging import (
    IN_APP_MESSAGING_ERROR_DOMAIN,
    DisplayDelegate,
    DisplayHandler,
    InAppMessaging,
    InAppMessagingError,
    InAppMessagingErrorCode,
    default_action,
)
from .messages import (
    Action,
    ActionButton,
    BannerMessage,
    CampaignInfo,
    CardMessage,
    DismissType,
    ImageData,
    ImageOnlyMessage,
    InAppMessage,
    MessageType,
    ModalMessage,
    TriggerType,
)

__all__ = (
    "IN_APP_MESSAGING_ERROR_DOMAIN",
    "Action",
    "ActionButton",
    "BannerMessage",
    "CampaignInfo",
    "CardMessage",
    "DismissType",
    "DisplayDelegate",
    "DisplayHandler",
    "ImageData",
    "ImageOnlyMessage",
    "InAppMessage",
    "InAppMessaging",
    "InAppMessagingError",
    "InAppMessagingErrorCode",
    "MessageType",
    "ModalMessage",
    "TriggerType",
    "default_action",
)

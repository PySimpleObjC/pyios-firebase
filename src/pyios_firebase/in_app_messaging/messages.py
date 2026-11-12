"""The in-app messages Firebase shows, as plain Python (from the SDK's
``FIRInAppMessagingDisplayMessage`` classes).

Listeners and custom displays get one of ``ModalMessage``, ``BannerMessage``,
``CardMessage`` or ``ImageOnlyMessage``. Every one has the campaign
(``campaign``), the type, what triggered it, and the custom data set in the
Firebase console (``app_data``). Colors are ``"#RRGGBB"`` strings
(``"#RRGGBBAA"`` when not opaque).
"""

from __future__ import annotations

__all__ = (
    "Action",
    "ActionButton",
    "BannerMessage",
    "CampaignInfo",
    "CardMessage",
    "DismissType",
    "ImageData",
    "ImageOnlyMessage",
    "InAppMessage",
    "MessageType",
    "ModalMessage",
    "TriggerType",
    "action_from_native",
    "color_to_hex",
    "message_from_native",
)

import math
from ctypes import byref, c_double
from dataclasses import dataclass, field
from typing import Any, Final

from ..types import ObjCObject
from ..util import to_python


class MessageType:
    """The layout of a message (``FIRInAppMessagingDisplayMessageType``)."""

    MODAL: Final = 0
    """A dialog in the middle of the screen."""
    BANNER: Final = 1
    """A strip at the top of the screen."""
    IMAGE_ONLY: Final = 2
    """Only an image."""
    CARD: Final = 3
    """A card with one or two buttons, and images for portrait and landscape."""


class TriggerType:
    """What made the message show (``FIRInAppMessagingDisplayTriggerType``)."""

    ON_APP_FOREGROUND: Final = 0
    """The app came to the foreground."""
    ON_ANALYTICS_EVENT: Final = 1
    """An Analytics event, or ``InAppMessaging.trigger_event``."""


class DismissType:
    """How the user closed a message (``FIRInAppMessagingDismissType``)."""

    USER_SWIPE: Final = 0
    USER_TAP_CLOSE: Final = 1
    AUTO: Final = 2
    """Closed by itself (a banner times out)."""
    UNSPECIFIED: Final = 3


@dataclass(frozen=True)
class CampaignInfo:
    """The campaign a message belongs to (``FIRInAppMessagingCampaignInfo``)."""

    message_id: str
    campaign_name: str
    render_as_test_message: bool = False
    """A test message sent from the console to this device: it is not counted
    in the campaign's statistics."""


@dataclass(frozen=True)
class ImageData:
    """An image of a message (``FIRInAppMessagingImageData``)."""

    image_url: str
    image_data: bytes | None = field(default=None, repr=False)
    """The image file (PNG, JPEG, ...), already downloaded by Firebase."""


@dataclass(frozen=True)
class ActionButton:
    """A button of a message (``FIRInAppMessagingActionButton``)."""

    text: str
    text_color: str | None = None
    background_color: str | None = None


@dataclass(frozen=True)
class Action:
    """What the user tapped (``FIRInAppMessagingAction``): a button's text
    (``None`` for a tap on the message itself, or on an image), and the URL
    the message opens (``None`` when it has none)."""

    text: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class InAppMessage:
    """What every message has (``FIRInAppMessagingDisplayMessage``)."""

    campaign: CampaignInfo
    type: int
    """A ``MessageType``."""
    trigger_type: int
    """A ``TriggerType``."""
    app_data: dict[str, Any] = field(default_factory=dict)
    """The custom data (key-value pairs) set on the campaign in the console."""


@dataclass(frozen=True)
class ModalMessage(InAppMessage):
    """A dialog: title, body, an optional image and an optional button."""

    title: str = ""
    body: str | None = None
    text_color: str | None = None
    background_color: str | None = None
    image: ImageData | None = None
    action_button: ActionButton | None = None
    action_url: str | None = None


@dataclass(frozen=True)
class BannerMessage(InAppMessage):
    """A banner at the top: title, body and an optional image. Tapping it
    opens ``action_url``."""

    title: str = ""
    body: str | None = None
    text_color: str | None = None
    background_color: str | None = None
    image: ImageData | None = None
    action_url: str | None = None


@dataclass(frozen=True)
class CardMessage(InAppMessage):
    """A card: title, body, images, a primary and an optional secondary button."""

    title: str = ""
    body: str | None = None
    text_color: str | None = None
    background_color: str | None = None
    portrait_image: ImageData | None = None
    landscape_image: ImageData | None = None
    primary_button: ActionButton | None = None
    primary_action_url: str | None = None
    secondary_button: ActionButton | None = None
    secondary_action_url: str | None = None


@dataclass(frozen=True)
class ImageOnlyMessage(InAppMessage):
    """Only an image. Tapping it opens ``action_url``."""

    image: ImageData | None = None
    action_url: str | None = None


# ---- from the SDK's objects ---------------------------------------------------


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _url(url: ObjCObject | None) -> str | None:
    return None if url is None else str(url.absoluteString)


def color_to_hex(color: ObjCObject | None) -> str | None:
    """A ``UIColor`` as ``"#RRGGBB"``, or ``"#RRGGBBAA"`` when it is not opaque.

    Args:
        color: the ``UIColor``.

    Returns:
        The color, or ``None`` (no color, or not an RGB color).
    """
    if color is None:
        return None
    nan = float("nan")
    parts = [c_double(nan), c_double(nan), c_double(nan), c_double(nan)]
    # UIKit returns NO for a color it cannot give as RGB (AppKit's returns
    # nothing); the parts stay NaN then
    converted = color.getRed_green_blue_alpha_(*(byref(p) for p in parts))
    if converted is False or any(math.isnan(p.value) for p in parts):
        return None
    *rgb, alpha = (round(min(max(p.value, 0.0), 1.0) * 255) for p in parts)
    text = "#" + "".join(f"{c:02X}" for c in rgb)
    return text if alpha == 255 else f"{text}{alpha:02X}"


def _image(image: ObjCObject | None) -> ImageData | None:
    if image is None:
        return None
    raw = image.imageRawData
    return ImageData(
        image_url=str(image.imageURL or ""),
        image_data=None if raw is None else bytes(to_python(raw)),
    )


def _button(button: ObjCObject | None) -> ActionButton | None:
    if button is None:
        return None
    return ActionButton(
        text=str(button.buttonText or ""),
        text_color=color_to_hex(button.buttonTextColor),
        background_color=color_to_hex(button.buttonBackgroundColor),
    )


def action_from_native(action: ObjCObject | None) -> Action:
    """Copy a native ``FIRInAppMessagingAction``.

    Args:
        action: the ``FIRInAppMessagingAction`` (``None`` gives an empty
            ``Action``).
    """
    if action is None:
        return Action()
    return Action(text=_str(action.actionText), url=_url(action.actionURL))


def message_from_native(message: ObjCObject) -> InAppMessage:
    """Copy a native ``FIRInAppMessagingDisplayMessage``.

    Args:
        message: the message the SDK gave.

    Returns:
        A ``ModalMessage``, ``BannerMessage``, ``CardMessage`` or
        ``ImageOnlyMessage`` (a plain ``InAppMessage`` for a type this version
        does not know).
    """
    info = message.campaignInfo
    common: dict[str, Any] = {
        "campaign": CampaignInfo(
            message_id=str(info.messageID),
            campaign_name=str(info.campaignName),
            render_as_test_message=bool(info.renderAsTestMessage),
        ),
        "type": int(message.type),
        "trigger_type": int(message.triggerType),
        "app_data": {str(k): v for k, v in (to_python(message.appData) or {}).items()},
    }
    kind = common["type"]
    if kind == MessageType.MODAL:
        return ModalMessage(
            **common,
            title=str(message.title or ""),
            body=_str(message.bodyText),
            text_color=color_to_hex(message.textColor),
            background_color=color_to_hex(message.displayBackgroundColor),
            image=_image(message.imageData),
            action_button=_button(message.actionButton),
            action_url=_url(message.actionURL),
        )
    if kind == MessageType.BANNER:
        return BannerMessage(
            **common,
            title=str(message.title or ""),
            body=_str(message.bodyText),
            text_color=color_to_hex(message.textColor),
            background_color=color_to_hex(message.displayBackgroundColor),
            image=_image(message.imageData),
            action_url=_url(message.actionURL),
        )
    if kind == MessageType.CARD:
        return CardMessage(
            **common,
            title=str(message.title or ""),
            body=_str(message.body),
            text_color=color_to_hex(message.textColor),
            background_color=color_to_hex(message.displayBackgroundColor),
            portrait_image=_image(message.portraitImageData),
            landscape_image=_image(message.landscapeImageData),
            primary_button=_button(message.primaryActionButton),
            primary_action_url=_url(message.primaryActionURL),
            secondary_button=_button(message.secondaryActionButton),
            secondary_action_url=_url(message.secondaryActionURL),
        )
    if kind == MessageType.IMAGE_ONLY:
        return ImageOnlyMessage(
            **common,
            image=_image(message.imageData),
            action_url=_url(message.actionURL),
        )
    return InAppMessage(**common)

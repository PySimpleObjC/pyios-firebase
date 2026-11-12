"""``InAppMessaging``: settings, events, listeners, and showing messages your way."""

from __future__ import annotations

__all__ = (
    "IN_APP_MESSAGING_ERROR_DOMAIN",
    "DisplayDelegate",
    "DisplayHandler",
    "InAppMessaging",
    "InAppMessagingError",
    "InAppMessagingErrorCode",
    "PyInAppMessagingDelegate",
    "PyInAppMessagingDisplay",
    "default_action",
)

from collections.abc import Callable
from ctypes import c_long
from typing import Any, ClassVar, Final

from rubicon.objc import NSObject, objc_id, objc_method

from ..types import FirebaseError, ObjCObject
from ..util import (
    nserror_to_dict,
    objc_class,
    objc_instance,
    objc_protocols,
    one_shot_block,
)
from .messages import (
    Action,
    BannerMessage,
    CardMessage,
    DismissType,
    ImageOnlyMessage,
    InAppMessage,
    ModalMessage,
    action_from_native,
    message_from_native,
)

IN_APP_MESSAGING_ERROR_DOMAIN: Final = "com.firebase.inappmessaging"
"""The ``error.domain`` of the errors a message display reports."""


class InAppMessagingErrorCode:
    """The ``error.code`` values of display errors (``FIAMDisplayRenderErrorType``)."""

    IMAGE_DATA_INVALID: Final = 0
    """The message's image could not be loaded or read."""
    UNSPECIFIED: Final = 1


_CODE_NAMES: Final[dict[int, str]] = {
    value: name
    for name, value in vars(InAppMessagingErrorCode).items()
    if isinstance(value, int)
}


class InAppMessagingError(FirebaseError):
    """A message that could not be shown."""

    name: str
    """The ``InAppMessagingErrorCode`` name of ``code``, or ``""`` for errors
    from other domains (for example a failed image download)."""


def _error(error: ObjCObject | None) -> InAppMessagingError:
    result = InAppMessagingError(nserror_to_dict(error) or {})
    result.setdefault("code", InAppMessagingErrorCode.UNSPECIFIED)
    result.setdefault("domain", IN_APP_MESSAGING_ERROR_DOMAIN)
    result.setdefault("description", "")
    result.name = (
        _CODE_NAMES.get(result.code, "")
        if result.domain == IN_APP_MESSAGING_ERROR_DOMAIN
        else ""
    )
    return result


ImpressionListener = Callable[[InAppMessage], None]
ClickListener = Callable[[InAppMessage, Action], None]
DismissListener = Callable[[InAppMessage, int], None]
ErrorListener = Callable[[InAppMessage, InAppMessagingError], None]


class PyInAppMessagingDelegate(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("FIRInAppMessagingDisplayDelegate")
):
    """Lets Firebase In-App Messaging call the Python listeners."""

    @objc_method
    def impressionDetectedForMessage_(self, message: objc_id) -> None:
        """A message was seen."""
        InAppMessaging._emit("impression", message_from_native(objc_instance(message)))

    @objc_method
    def messageClicked_withAction_(self, message: objc_id, action: objc_id) -> None:
        """The user tapped a message, or one of its buttons."""
        InAppMessaging._emit(
            "click",
            message_from_native(objc_instance(message)),
            action_from_native(objc_instance(action) if action else None),
        )

    @objc_method
    def messageDismissed_dismissType_(
        self, message: objc_id, dismiss_type: c_long
    ) -> None:
        """A message was closed without a tap on its action."""
        InAppMessaging._emit(
            "dismiss", message_from_native(objc_instance(message)), int(dismiss_type)
        )

    @objc_method
    def displayErrorForMessage_error_(self, message: objc_id, error: objc_id) -> None:
        """A message could not be shown."""
        InAppMessaging._emit(
            "error",
            message_from_native(objc_instance(message)),
            _error(objc_instance(error) if error else None),
        )


class DisplayDelegate:
    """What a custom display tells Firebase about the message it shows.

    Call ``impression()`` once the message is on screen, then exactly one of
    ``clicked()``, ``dismissed()`` or ``failed()`` when it goes away: until
    then, Firebase shows no other message.

    Args:
        message: the message, as Python.
        native_message: the ``FIRInAppMessagingDisplayMessage``.
        native_delegate: the ``FIRInAppMessagingDisplayDelegate`` Firebase gave.
    """

    def __init__(
        self,
        message: InAppMessage,
        native_message: ObjCObject,
        native_delegate: ObjCObject,
    ) -> None:
        self.message = message
        self._native_message = native_message
        self._native_delegate = native_delegate
        self._impression = False
        self._finished = False

    @property
    def finished(self) -> bool:
        """Whether ``clicked``, ``dismissed`` or ``failed`` was called."""
        return self._finished

    def _finish(self) -> None:
        if self._finished:
            raise RuntimeError("this message was already clicked, dismissed or failed")
        self._finished = True

    def impression(self) -> None:
        """The message is on screen: Firebase counts an impression (once; later
        calls do nothing)."""
        if self._impression:
            return
        self._impression = True
        self._native_delegate.impressionDetectedForMessage_(self._native_message)

    def clicked(self, action: Action | None = None) -> None:
        """The user tapped the message's action. Firebase opens the action's
        URL, if it has one (a web link, or a deep link to the app).

        Args:
            action: what was tapped. By default, the message's main action
                (its button, or the primary one of a card, with its URL).

        Raises:
            RuntimeError: the message already finished.
        """
        if action is None:
            action = default_action(self.message)
        self._finish()
        url = None
        if action.url is not None:
            url = objc_class("NSURL").URLWithString_(action.url)
        native = objc_class("FIRInAppMessagingAction").alloc()
        native = native.initWithActionText_actionURL_(action.text, url)
        self._native_delegate.messageClicked_withAction_(self._native_message, native)

    def dismissed(self, dismiss_type: int = DismissType.USER_TAP_CLOSE) -> None:
        """The user closed the message (or it timed out).

        Args:
            dismiss_type: a ``DismissType``.

        Raises:
            RuntimeError: the message already finished.
        """
        self._finish()
        self._native_delegate.messageDismissed_dismissType_(
            self._native_message, int(dismiss_type)
        )

    def failed(
        self,
        code: int = InAppMessagingErrorCode.UNSPECIFIED,
        description: str = "the message could not be shown",
    ) -> None:
        """The message could not be shown.

        Args:
            code: an ``InAppMessagingErrorCode``.
            description: why.

        Raises:
            RuntimeError: the message already finished.
        """
        self._finish()
        error = objc_class("NSError").errorWithDomain_code_userInfo_(
            IN_APP_MESSAGING_ERROR_DOMAIN,
            int(code),
            {"NSLocalizedDescription": description},
        )
        self._native_delegate.displayErrorForMessage_error_(self._native_message, error)


def default_action(message: InAppMessage) -> Action:
    """The main action of a message: its button (the primary one of a card)
    and its URL.

    Args:
        message: the message.
    """
    if isinstance(message, ModalMessage):
        button = message.action_button
        return Action(button.text if button else None, message.action_url)
    if isinstance(message, CardMessage):
        button = message.primary_button
        return Action(button.text if button else None, message.primary_action_url)
    if isinstance(message, BannerMessage | ImageOnlyMessage):
        return Action(None, message.action_url)
    return Action()


DisplayHandler = Callable[[InAppMessage, DisplayDelegate], None]
"""Gets the message and its ``DisplayDelegate``; shows the message (for
example in a Kivy popup)."""


def _is_main_thread() -> bool:
    value = objc_class("NSThread").isMainThread
    return bool(value() if callable(value) else value)


def _on_main_thread(function: Callable[[], None]) -> None:
    """Run ``function`` now on the main thread, or on its next turn from
    another thread."""
    if _is_main_thread():
        function()
        return
    queue: ObjCObject = objc_class("NSOperationQueue").mainQueue
    if callable(queue):  # a class property: Rubicon may give it as a method
        queue = queue()
    queue.addOperationWithBlock_(one_shot_block(function))


class PyInAppMessagingDisplay(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("FIRInAppMessagingDisplay")
):
    """Lets Firebase In-App Messaging call a Python display."""

    @objc_method
    def displayMessage_displayDelegate_(
        self, message: objc_id, delegate: objc_id
    ) -> None:
        """Firebase has a message to show."""
        native_message = objc_instance(message)
        native_delegate = objc_instance(delegate)

        def show() -> None:
            handler = InAppMessaging._display_handler
            display = DisplayDelegate(
                message_from_native(native_message), native_message, native_delegate
            )
            if handler is None:
                display.failed(description="no Python display handler")
                return
            try:
                handler(display.message, display)
            except BaseException:
                if not display.finished:  # else Firebase waits for it forever
                    display.failed(description="the Python display handler raised")
                raise

        _on_main_thread(show)


class InAppMessaging:
    """Firebase In-App Messaging. Get it with ``InAppMessaging.in_app_messaging()``.

    Messages come from campaigns made in the Firebase console. Firebase
    fetches them and shows them by itself (with its own screens) when the app
    comes to the foreground, or on an Analytics event. Nothing has to be
    called for that: linking the framework is enough.

    Args:
        native: the native ``FIRInAppMessaging``.
    """

    _shared: ClassVar[InAppMessaging | None] = None
    _listeners: ClassVar[dict[str, list[Callable[..., None]]]] = {
        "impression": [],
        "click": [],
        "dismiss": [],
        "error": [],
    }
    _delegate: ClassVar[ObjCObject | None] = None  # Firebase only holds it weakly
    _display: ClassVar[ObjCObject | None] = None
    _display_handler: ClassVar[DisplayHandler | None] = None

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def in_app_messaging(cls) -> InAppMessaging:
        """The shared ``InAppMessaging``, of the default app.

        Raises:
            RuntimeError: Firebase is not configured yet (call
                ``core.configure()`` first).
        """
        if cls._shared is None:
            native = objc_class("FIRInAppMessaging").inAppMessaging()
            if native is None:  # the SDK gives nil before configure
                raise RuntimeError(
                    "In-App Messaging needs Firebase configured: call "
                    "core.configure() first"
                )
            cls._shared = cls(native)
        return cls._shared

    @property
    def native(self) -> ObjCObject:
        """The ``FIRInAppMessaging``."""
        return self._native

    # ---- settings ------------------------------------------------------------------

    @property
    def message_display_suppressed(self) -> bool:
        """Stop showing messages while ``True`` (for example during a payment
        or a game level). Off at every launch; not kept."""
        value = self._native.messageDisplaySuppressed
        return bool(value() if callable(value) else value)

    @message_display_suppressed.setter
    def message_display_suppressed(self, suppressed: bool) -> None:
        self._native.messageDisplaySuppressed = bool(suppressed)

    @property
    def automatic_data_collection_enabled(self) -> bool:
        """Fetch messages (and send the data that needs) at start-up. Setting
        it is kept across launches; to start with it off, set
        ``FirebaseInAppMessagingAutomaticDataCollectionEnabled`` to ``NO`` in
        ``Info.plist``, then turn it on once the user agrees."""
        value = self._native.automaticDataCollectionEnabled
        return bool(value() if callable(value) else value)

    @automatic_data_collection_enabled.setter
    def automatic_data_collection_enabled(self, enabled: bool) -> None:
        self._native.automaticDataCollectionEnabled = bool(enabled)

    def trigger_event(self, name: str) -> None:
        """Show the messages of campaigns triggered by this event, without
        logging an Analytics event. (An Analytics event with the same name
        triggers them too.)

        Args:
            name: the event name set on the campaign.

        Raises:
            TypeError: a name that is not a ``str``.
            ValueError: an empty name.
        """
        if not isinstance(name, str):
            raise TypeError(f"an event name must be a str, not {type(name).__name__}")
        if not name:
            raise ValueError("an event name must not be empty")
        self._native.triggerEvent_(name)

    # ---- listeners -----------------------------------------------------------------

    @classmethod
    def _emit(cls, kind: str, *args: Any) -> None:
        for listener in list(cls._listeners[kind]):
            listener(*args)

    def _listen(self, kind: str, listener: Callable[..., None]) -> Callable[[], None]:
        if InAppMessaging._delegate is None:
            InAppMessaging._delegate = PyInAppMessagingDelegate.alloc().init()
            self._native.delegate = InAppMessaging._delegate
        InAppMessaging._listeners[kind].append(listener)

        def remove() -> None:
            if listener in InAppMessaging._listeners[kind]:
                InAppMessaging._listeners[kind].remove(listener)

        return remove

    def add_impression_listener(
        self, listener: ImpressionListener
    ) -> Callable[[], None]:
        """Call ``listener(message)`` when a message is seen.

        Args:
            listener: gets the ``InAppMessage``.

        Returns:
            A function that removes the listener.
        """
        return self._listen("impression", listener)

    def add_click_listener(self, listener: ClickListener) -> Callable[[], None]:
        """Call ``listener(message, action)`` when the user taps a message's
        action. Firebase opens ``action.url`` itself afterwards: a deep link
        reaches the app as an opened URL.

        Args:
            listener: gets the ``InAppMessage`` and the ``Action``.

        Returns:
            A function that removes the listener.
        """
        return self._listen("click", listener)

    def add_dismiss_listener(self, listener: DismissListener) -> Callable[[], None]:
        """Call ``listener(message, dismiss_type)`` when a message is closed
        without a tap on its action.

        Args:
            listener: gets the ``InAppMessage`` and a ``DismissType``.

        Returns:
            A function that removes the listener.
        """
        return self._listen("dismiss", listener)

    def add_error_listener(self, listener: ErrorListener) -> Callable[[], None]:
        """Call ``listener(message, error)`` when a message could not be shown.

        Args:
            listener: gets the ``InAppMessage`` and the ``InAppMessagingError``.

        Returns:
            A function that removes the listener.
        """
        return self._listen("error", listener)

    # ---- the display ---------------------------------------------------------------

    def set_display(self, handler: DisplayHandler | None) -> None:
        """Show messages with Python instead of Firebase's screens.

        ``handler(message, delegate)`` runs on the main thread. It shows the
        message (a Kivy popup, a Toga window...), calls
        ``delegate.impression()`` once it is visible, and later exactly one of
        ``delegate.clicked()``, ``delegate.dismissed()`` or
        ``delegate.failed()``. If the handler raises, the message counts as
        failed.

        Args:
            handler: the display, or ``None`` to show no message at all (they
                are not counted as seen).
        """
        InAppMessaging._display_handler = handler
        if handler is None:
            InAppMessaging._display = None
            self._native.messageDisplayComponent = None
            return
        if InAppMessaging._display is None:
            InAppMessaging._display = PyInAppMessagingDisplay.alloc().init()
        self._native.messageDisplayComponent = InAppMessaging._display

    def use_default_display(self) -> None:
        """Show messages with Firebase's own screens again (the default)."""
        InAppMessaging._display_handler = None
        InAppMessaging._display = None
        self._native.messageDisplayComponent = (
            objc_class("FIRIAMDefaultDisplayImpl").alloc().init()
        )

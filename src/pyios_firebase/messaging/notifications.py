"""Notification permission, and notifications that arrive (``UserNotifications``).

Push notifications from FCM arrive through Apple's notification center. This
module asks for permission, registers with APNs, and calls Python when a
notification arrives with the app open, or when the user taps one::

    from pyios_firebase.messaging import notifications
    from pyios_firebase.messaging.notifications import AuthorizationOptions, PresentationOptions

    def on_foreground(notification):
        print("got", notification.title, notification.data)
        return PresentationOptions.BANNER | PresentationOptions.SOUND  # show it

    def on_open(notification, action):
        open_screen(notification.data.get("screen"))

    # early, before App.run(): a tap that launched the app is delivered then
    notifications.set_handlers(on_foreground=on_foreground, on_open=on_open)
    notifications.request_permission(
        AuthorizationOptions.ALERT | AuthorizationOptions.BADGE | AuthorizationOptions.SOUND,
        lambda granted, error: notifications.register_for_remote_notifications(),
    )

Firebase forwards the APNs token to Messaging by itself (app delegate
swizzling), and records what arrives for delivery analytics.

Data-only (silent) messages are delivered to the app delegate
(``application:didReceiveRemoteNotification:fetchCompletionHandler:``), which
Python does not own in a Kivy app: send the data in a notification instead, or
read it when the user opens the app.
"""

from __future__ import annotations

__all__ = (
    "HOOK_CLASS_NAME",
    "AuthorizationOptions",
    "AuthorizationStatus",
    "Notification",
    "PresentationOptions",
    "PyNotificationCenterDelegate",
    "authorization_status",
    "launch_hook_status",
    "register_for_remote_notifications",
    "request_permission",
    "set_handlers",
)

from collections.abc import Callable
from ctypes import c_bool
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from typing import Any, ClassVar, Final

from rubicon.objc import NSObject, objc_method
from rubicon.objc.runtime import load_library, objc_block, objc_id

from ..types import FirebaseError, ObjCObject
from ..util import (
    error_from_pointer,
    nsdate_to_datetime,
    objc_class,
    objc_instance,
    objc_protocols,
    one_shot_block,
    to_python,
)

HOOK_CLASS_NAME: Final = "PyiosFirebaseNotificationsHook"
"""The class of the optional launch hook package (pyios-firebase-notifications-hook),
which keeps the tap that launches a Kivy app until ``set_handlers`` runs."""

DEFAULT_ACTION: Final = "com.apple.UNNotificationDefaultActionIdentifier"
"""The ``action`` of ``on_open`` when the user tapped the notification itself."""
DISMISS_ACTION: Final = "com.apple.UNNotificationDismissActionIdentifier"
"""The ``action`` when the user dismissed it (only for categories that ask)."""


class AuthorizationOptions:
    """What to ask permission for (``UNAuthorizationOptions``). Combine with ``|``."""

    BADGE: Final = 1 << 0
    SOUND: Final = 1 << 1
    ALERT: Final = 1 << 2
    CAR_PLAY: Final = 1 << 3
    CRITICAL_ALERT: Final = 1 << 4
    """Needs an entitlement from Apple."""
    PROVIDES_APP_NOTIFICATION_SETTINGS: Final = 1 << 5
    PROVISIONAL: Final = 1 << 6
    """Granted without asking: notifications are delivered quietly, to
    Notification Center only, until the user chooses."""


class AuthorizationStatus:
    """The permission the user gave (``UNAuthorizationStatus``)."""

    NOT_DETERMINED: Final = 0
    """Not asked yet."""
    DENIED: Final = 1
    AUTHORIZED: Final = 2
    PROVISIONAL: Final = 3
    EPHEMERAL: Final = 4
    """App Clips only."""


class PresentationOptions:
    """How to show a notification that arrives with the app open
    (``UNNotificationPresentationOptions``). Combine with ``|``; 0 shows nothing.
    """

    NONE: Final = 0
    BADGE: Final = 1 << 0
    SOUND: Final = 1 << 1
    LIST: Final = 1 << 3
    """In Notification Center."""
    BANNER: Final = 1 << 4
    """As a banner."""


@dataclass(frozen=True)
class Notification:
    """A notification that arrived (from ``UNNotification``)."""

    identifier: str
    """The request's identifier."""
    title: str
    subtitle: str
    body: str
    badge: int | None
    data: dict[str, Any] = field(default_factory=dict)
    """The whole payload (``userInfo``): the ``aps`` dictionary, and the FCM
    message's data keys."""
    category: str = ""
    thread_id: str = ""
    date: datetime | None = None
    """When it was delivered (UTC)."""

    @property
    def message_id(self) -> str | None:
        """The FCM message ID (``"gcm.message_id"``), or ``None`` if the
        notification did not come from FCM."""
        value = self.data.get("gcm.message_id")
        return None if value is None else str(value)

    @classmethod
    def from_native(cls, notification: ObjCObject) -> Notification:
        """Copy a native ``UNNotification``.

        Args:
            notification: the ``UNNotification``.
        """
        request = notification.request
        content = request.content
        badge = content.badge
        return cls(
            identifier=str(request.identifier),
            title=str(content.title or ""),
            subtitle=str(content.subtitle or ""),
            body=str(content.body or ""),
            badge=None if badge is None else int(badge.integerValue),
            data=to_python(content.userInfo) or {},
            category=str(content.categoryIdentifier or ""),
            thread_id=str(content.threadIdentifier or ""),
            date=nsdate_to_datetime(notification.date),
        )


ForegroundHandler = Callable[[Notification], "int | None"]
"""Gets the ``Notification``; returns ``PresentationOptions`` (or ``None``:
show nothing)."""
OpenHandler = Callable[[Notification, str], None]
"""Gets the ``Notification`` and the action (``DEFAULT_ACTION`` for a tap)."""


@cache
def _center() -> ObjCObject:
    load_library("UserNotifications")
    return objc_class("UNUserNotificationCenter").currentNotificationCenter()


def request_permission(
    options: int, callback: Callable[[bool, FirebaseError | None], None] | None = None
) -> None:
    """Ask the user for permission to show notifications. iOS asks only once;
    later calls give the earlier answer without asking.

    Args:
        options: ``AuthorizationOptions``, combined with ``|``.
        callback: gets ``(granted, error)``. It runs on a background thread.
    """

    def done(granted: Any, error_ptr: Any) -> None:
        if callback is not None:
            callback(bool(granted), error_from_pointer(error_ptr))

    _center().requestAuthorizationWithOptions_completionHandler_(
        int(options), one_shot_block(done, c_bool, objc_id)
    )


def authorization_status(callback: Callable[[int], None]) -> None:
    """The current permission.

    Args:
        callback: gets an ``AuthorizationStatus``. It runs on a background thread.
    """

    def done(settings_ptr: Any) -> None:
        callback(int(objc_instance(settings_ptr).authorizationStatus))

    _center().getNotificationSettingsWithCompletionHandler_(
        one_shot_block(done, objc_id)
    )


def register_for_remote_notifications() -> None:
    """Register with APNs, to get the device token FCM needs. Call it on the
    main thread (Kivy's), at each launch. Needs the Push Notifications
    capability (``aps-environment`` entitlement)."""
    objc_class("UIApplication").sharedApplication.registerForRemoteNotifications()


class PyNotificationCenterDelegate(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("UNUserNotificationCenterDelegate")
):
    """Lets iOS call the Python handlers."""

    @objc_method
    def userNotificationCenter_willPresentNotification_withCompletionHandler_(
        self, center: objc_id, notification: objc_id, handler: objc_block
    ) -> None:
        """A notification arrived with the app open."""
        options = PresentationOptions.NONE
        try:
            on_foreground = _Handlers.on_foreground
            if on_foreground is not None:
                result = on_foreground(
                    Notification.from_native(objc_instance(notification))
                )
                options = int(result or 0)
            else:
                options = _Handlers.default_presentation
        finally:
            complete: Any = handler  # a Rubicon ObjCBlock, callable at runtime
            complete(options)

    @objc_method
    def userNotificationCenter_didReceiveNotificationResponse_withCompletionHandler_(
        self, center: objc_id, response: objc_id, handler: objc_block
    ) -> None:
        """The user tapped a notification (or one of its actions)."""
        try:
            on_open = _Handlers.on_open
            if on_open is not None:
                native = objc_instance(response)
                on_open(
                    Notification.from_native(native.notification),
                    str(native.actionIdentifier),
                )
        finally:
            complete: Any = handler  # a Rubicon ObjCBlock, callable at runtime
            complete()


class _Handlers:
    on_foreground: ClassVar[ForegroundHandler | None] = None
    on_open: ClassVar[OpenHandler | None] = None
    default_presentation: ClassVar[int] = PresentationOptions.NONE
    delegate: ClassVar[ObjCObject | None] = None  # the center only holds it weakly


def _hook() -> ObjCObject | None:
    try:
        return objc_class(HOOK_CLASS_NAME)
    except NameError:
        return None


def launch_hook_status() -> str | None:
    """Whether the launch hook package is in the app, and working.

    Returns:
        ``None`` when the app does not include pyios-firebase-notifications-hook;
        otherwise the hook's status, which starts with ``"ok"`` when it is
        keeping launch taps (for example ``"ok: SDLUIKitSceneDelegate"``).
    """
    hook = _hook()
    return None if hook is None else str(hook.status())


def _on_main_thread(function: Callable[[], None]) -> None:
    """Run ``function`` on the main thread's next turn (once the app's event
    loop runs), not now."""
    queue: ObjCObject = objc_class("NSOperationQueue").mainQueue
    if callable(queue):  # a class property: Rubicon may give it as a method
        queue = queue()
    queue.addOperationWithBlock_(one_shot_block(function))


def _report_open(notification: Notification) -> None:
    """Tell Firebase Messaging a notification was opened (its "opened"
    statistics), for taps the hook kept: Firebase did not see those."""
    try:
        app = objc_class("FIRApp").defaultApp()
        messaging = objc_class("FIRMessaging")
    except NameError:
        return
    if app is None:  # Messaging before configure() would stop the app
        return
    from rubicon.objc import ns_from_py

    messaging.messaging().appDidReceiveMessage_(ns_from_py(notification.data))


def _deliver_launch_taps() -> None:
    """Pass the taps the launch hook kept to ``on_open``."""
    on_open = _Handlers.on_open
    hook = _hook()
    if on_open is None or hook is None:
        return  # without on_open, the taps stay in the hook for a later call
    for response in hook.takeResponses():
        notification = Notification.from_native(response.notification)
        _report_open(notification)
        on_open(notification, str(response.actionIdentifier))


def set_handlers(
    on_foreground: ForegroundHandler | None = None,
    on_open: OpenHandler | None = None,
    *,
    default_presentation: int = PresentationOptions.NONE,
) -> None:
    """Call Python when a notification arrives with the app open, and when the
    user taps one. Call it early (before ``App.run()``).

    This makes pyios-firebase the notification center's delegate (replacing
    any other).

    A tap that **launches** the app (it was not running) is delivered by iOS
    before a Kivy app's Python starts. With the optional
    pyios-firebase-notifications-hook package in the app, that tap is kept and
    passed to ``on_open`` here, once the app's event loop runs. Without the
    hook, a Kivy app does not get it. See ``launch_hook_status``.

    Args:
        on_foreground: gets the ``Notification``; returns the
            ``PresentationOptions`` to show it with (``None`` or 0: do not show).
        on_open: gets the ``Notification`` and the action identifier
            (``DEFAULT_ACTION`` for a tap on the notification).
        default_presentation: the options when there is no ``on_foreground``.
    """
    _Handlers.on_foreground = on_foreground
    _Handlers.on_open = on_open
    _Handlers.default_presentation = int(default_presentation)
    if _Handlers.delegate is None:
        _Handlers.delegate = PyNotificationCenterDelegate.alloc().init()
    _center().delegate = _Handlers.delegate
    if on_open is not None and _hook() is not None:
        _on_main_thread(_deliver_launch_taps)

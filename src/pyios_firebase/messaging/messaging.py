"""``Messaging``: the FCM registration token, topics and registration."""

from __future__ import annotations

__all__ = (
    "MESSAGING_ERROR_DOMAIN",
    "APNSTokenType",
    "Messaging",
    "MessagingError",
    "MessagingErrorCode",
    "MessagingMessageStatus",
    "PyMessagingDelegate",
)

import re
from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Final

from rubicon.objc import NSObject, ns_from_py, objc_id, objc_method

from ..types import FirebaseError, ObjCObject
from ..util import (
    nserror_to_dict,
    objc_class,
    objc_instance,
    objc_protocols,
    one_shot_block,
    to_python,
)

MESSAGING_ERROR_DOMAIN: Final = "com.google.fcm"
"""The ``error.domain`` of Messaging errors."""

_TOPIC: Final = re.compile(r"[a-zA-Z0-9\-_.~%]{1,900}\Z")
_TOPICS_PREFIX: Final = "/topics/"


class MessagingErrorCode:
    """The ``error.code`` values of Messaging errors (``FIRMessagingError``)."""

    UNKNOWN: Final = 0
    AUTHENTICATION: Final = 1
    """The FCM backend could not validate the request (check the API key and
    ``GoogleService-Info.plist``)."""
    NO_ACCESS: Final = 2
    TIMEOUT: Final = 3
    NETWORK: Final = 4
    """No network."""
    OPERATION_IN_PROGRESS: Final = 5
    INVALID_REQUEST: Final = 7
    INVALID_TOPIC_NAME: Final = 8


_CODE_NAMES: Final[dict[int, str]] = {
    value: name
    for name, value in vars(MessagingErrorCode).items()
    if isinstance(value, int)
}


class MessagingError(FirebaseError):
    """An error from Firebase Cloud Messaging."""

    name: str
    """The ``MessagingErrorCode`` name of ``code``, or ``""`` for errors from
    other domains (for example Firebase Installations)."""


def _error(error_ptr: Any) -> MessagingError | None:
    if not error_ptr:
        return None
    result = MessagingError(nserror_to_dict(objc_instance(error_ptr)) or {})
    result.name = (
        _CODE_NAMES.get(result.code, "")
        if result.domain == MESSAGING_ERROR_DOMAIN
        else ""
    )
    return result


class APNSTokenType:
    """The APNs environment of a token (``FIRMessagingAPNSTokenType``)."""

    UNKNOWN: Final = 0
    """Found from the provisioning profile (the usual choice)."""
    SANDBOX: Final = 1
    """Development builds."""
    PROD: Final = 2
    """App Store, TestFlight and ad hoc builds."""


class MessagingMessageStatus:
    """What ``app_did_receive_message`` found (``FIRMessagingMessageStatus``)."""

    UNKNOWN: Final = 0
    NEW: Final = 1


TokenCallback = Callable[[str | None, MessagingError | None], None]
ErrorCallback = Callable[[MessagingError | None], None]


def _token_block(callback: TokenCallback) -> Any:
    def done(token_ptr: Any, error_ptr: Any) -> None:
        error = _error(error_ptr)
        token = str(objc_instance(token_ptr)) if token_ptr and error is None else None
        callback(token, error)

    return one_shot_block(done, objc_id, objc_id)


def _error_block(callback: ErrorCallback | None) -> Any:
    def done(error_ptr: Any) -> None:
        if callback is not None:
            callback(_error(error_ptr))

    return one_shot_block(done, objc_id)


def _topic(topic: str) -> str:
    if not isinstance(topic, str):
        raise TypeError(f"a topic must be a str, not {type(topic).__name__}")
    name = topic.removeprefix(_TOPICS_PREFIX)
    if not _TOPIC.match(name):
        raise ValueError(
            f"invalid topic {topic!r}: 1 to 900 letters, digits and - _ . ~ %"
        )
    return name


class PyMessagingDelegate(  # type: ignore[call-arg]  # Rubicon's class keyword
    NSObject, protocols=objc_protocols("FIRMessagingDelegate")
):
    """Lets Firebase Messaging call the Python listeners."""

    @objc_method
    def messaging_didReceiveRegistrationToken_(
        self, messaging: objc_id, token: objc_id
    ) -> None:
        """A new (or refreshed) FCM registration token."""
        Messaging._emit("token", str(objc_instance(token)) if token else None)

    @objc_method
    def messaging_didReceiveRegistration_(
        self, messaging: objc_id, installation_id: objc_id
    ) -> None:
        """Registered with FCM through the Firebase installation ID."""
        Messaging._emit(
            "registration",
            str(objc_instance(installation_id)) if installation_id else None,
        )

    @objc_method
    def messaging_didUnregister_(
        self, messaging: objc_id, installation_id: objc_id
    ) -> None:
        """Unregistered from FCM."""
        Messaging._emit(
            "unregistration",
            str(objc_instance(installation_id)) if installation_id else None,
        )


class Messaging:
    """Firebase Cloud Messaging. Get it with ``Messaging.messaging()``.

    Notifications need the push entitlement and an APNs key in the Firebase
    console; see ``pyios_firebase.messaging.notifications`` to ask permission
    and handle what arrives.

    Args:
        native: the native ``FIRMessaging``.
    """

    _shared: ClassVar[Messaging | None] = None
    _listeners: ClassVar[dict[str, list[Callable[[str | None], None]]]] = {
        "token": [],
        "registration": [],
        "unregistration": [],
    }
    _delegate: ClassVar[ObjCObject | None] = None  # Messaging only holds it weakly

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def messaging(cls) -> Messaging:
        """The shared ``Messaging``."""
        if cls._shared is None:
            cls._shared = cls(objc_class("FIRMessaging").messaging())
        return cls._shared

    @property
    def native(self) -> ObjCObject:
        """The ``FIRMessaging``."""
        return self._native

    # ---- listeners -----------------------------------------------------------------

    @classmethod
    def _emit(cls, kind: str, value: str | None) -> None:
        for listener in list(cls._listeners[kind]):
            listener(value)

    def _listen(
        self, kind: str, listener: Callable[[str | None], None]
    ) -> Callable[[], None]:
        if Messaging._delegate is None:
            Messaging._delegate = PyMessagingDelegate.alloc().init()
            self._native.delegate = Messaging._delegate
        Messaging._listeners[kind].append(listener)

        def remove() -> None:
            if listener in Messaging._listeners[kind]:
                Messaging._listeners[kind].remove(listener)

        return remove

    def add_token_listener(
        self, listener: Callable[[str | None], None]
    ) -> Callable[[], None]:
        """Call ``listener(token)`` with each new FCM registration token: at
        start-up (when auto-init is on) and whenever it changes. Send it to
        your server to target this device.

        Args:
            listener: gets the token (``str``).

        Returns:
            A function that removes the listener.
        """
        return self._listen("token", listener)

    def add_registration_listener(
        self, listener: Callable[[str | None], None]
    ) -> Callable[[], None]:
        """Call ``listener(installation_id)`` when the app registers with FCM
        through its Firebase installation ID (with
        ``FirebaseMessagingInstallationIdEnabled`` in ``Info.plist``).

        Args:
            listener: gets the installation ID.

        Returns:
            A function that removes the listener.
        """
        return self._listen("registration", listener)

    def add_unregistration_listener(
        self, listener: Callable[[str | None], None]
    ) -> Callable[[], None]:
        """Call ``listener(installation_id)`` after ``unregister`` worked.

        Args:
            listener: gets the installation ID that was unregistered.

        Returns:
            A function that removes the listener.
        """
        return self._listen("unregistration", listener)

    # ---- the APNs token ------------------------------------------------------------

    @property
    def apns_token(self) -> bytes | None:
        """The APNs device token. Firebase sets it for you (app delegate
        swizzling); set it yourself when ``FirebaseAppDelegateProxyEnabled`` is
        ``NO``."""
        token = self._native.APNSToken
        return None if token is None else bytes(to_python(token))

    @apns_token.setter
    def apns_token(self, token: bytes | None) -> None:
        self._native.APNSToken = None if token is None else ns_from_py(bytes(token))

    def set_apns_token(
        self, token: bytes, token_type: int = APNSTokenType.UNKNOWN
    ) -> None:
        """Set the APNs device token, with its environment.

        Args:
            token: the token from
                ``application:didRegisterForRemoteNotificationsWithDeviceToken:``.
            token_type: an ``APNSTokenType``.
        """
        self._native.setAPNSToken_type_(ns_from_py(bytes(token)), int(token_type))

    # ---- the FCM token -------------------------------------------------------------

    @property
    def fcm_token(self) -> str | None:
        """The FCM registration token, if there is one yet (else use ``token``)."""
        token = self._native.FCMToken
        return None if token is None else str(token)

    @property
    def auto_init_enabled(self) -> bool:
        """Make a token automatically at start-up (on by default). Setting it is
        kept across launches; to start with it off, set
        ``FirebaseMessagingAutoInitEnabled`` to ``NO`` in ``Info.plist``."""
        value = self._native.isAutoInitEnabled
        return bool(value() if callable(value) else value)

    @auto_init_enabled.setter
    def auto_init_enabled(self, enabled: bool) -> None:
        self._native.setAutoInitEnabled_(bool(enabled))

    @property
    def installation_id_enabled(self) -> bool:
        """Whether the app registers through its Firebase installation ID
        instead of a token (``FirebaseMessagingInstallationIdEnabled`` in
        ``Info.plist``). Then the token methods fail: use ``register``."""
        value = self._native.isInstallationIdEnabled
        return bool(value() if callable(value) else value)

    def token(self, callback: TokenCallback) -> None:
        """Get the FCM registration token (made if needed; needs the APNs token
        on a device, and the network).

        Args:
            callback: gets ``(token, None)``, or ``(None, error)``.
        """
        self._native.tokenWithCompletion_(_token_block(callback))

    def delete_token(self, callback: ErrorCallback | None = None) -> None:
        """Delete the FCM registration token: the device stops getting messages
        until a new token is made.

        Args:
            callback: gets ``None`` or the error.
        """
        self._native.deleteTokenWithCompletion_(_error_block(callback))

    def retrieve_fcm_token(self, sender_id: str, callback: TokenCallback) -> None:
        """Get a token for another sender (another Firebase project's sender ID).

        Args:
            sender_id: the other project's sender ID.
            callback: gets ``(token, None)``, or ``(None, error)``.
        """
        self._native.retrieveFCMTokenForSenderID_completion_(
            sender_id, _token_block(callback)
        )

    def delete_fcm_token(
        self, sender_id: str, callback: ErrorCallback | None = None
    ) -> None:
        """Delete the token of another sender.

        Args:
            sender_id: the other project's sender ID.
            callback: gets ``None`` or the error.
        """
        self._native.deleteFCMTokenForSenderID_completion_(
            sender_id, _error_block(callback)
        )

    # ---- registration with the installation ID ------------------------------------

    def register(self, callback: ErrorCallback | None = None) -> None:
        """Register with FCM through the Firebase installation ID (with
        ``FirebaseMessagingInstallationIdEnabled``). Registration listeners
        get the installation ID.

        Args:
            callback: gets ``None`` or the error.
        """
        self._native.registerWithCompletion_(_error_block(callback))

    def unregister(self, callback: ErrorCallback | None = None) -> None:
        """Stop getting messages through the installation ID.

        Args:
            callback: gets ``None`` or the error.
        """
        self._native.unregisterWithCompletion_(_error_block(callback))

    def delete_data(self, callback: ErrorCallback | None = None) -> None:
        """Delete this app instance's FCM registrations, here and on the server.
        It does not delete the Firebase installation ID; turn auto-init off to
        stop a new registration at the next start-up.

        Args:
            callback: gets ``None`` or the error.
        """
        self._native.deleteDataWithCompletion_(_error_block(callback))

    # ---- topics --------------------------------------------------------------------

    def subscribe_to_topic(
        self, topic: str, callback: ErrorCallback | None = None
    ) -> None:
        """Get the messages sent to a topic.

        Args:
            topic: the topic, for example ``"news"`` (1 to 900 letters, digits
                and ``- _ . ~ %``).
            callback: gets ``None`` once subscribed, or the error.

        Raises:
            ValueError: an invalid topic name.
        """
        self._native.subscribeToTopic_completion_(_topic(topic), _error_block(callback))

    def unsubscribe_from_topic(
        self, topic: str, callback: ErrorCallback | None = None
    ) -> None:
        """Stop getting a topic's messages.

        Args:
            topic: the topic.
            callback: gets ``None`` once unsubscribed, or the error.

        Raises:
            ValueError: an invalid topic name.
        """
        self._native.unsubscribeFromTopic_completion_(
            _topic(topic), _error_block(callback)
        )

    # ---- messages ------------------------------------------------------------------

    def app_did_receive_message(self, message: Mapping[str, Any]) -> int:
        """Tell FCM a message arrived (for delivery analytics). Only needed when
        ``FirebaseAppDelegateProxyEnabled`` is ``NO``; Firebase does it for you
        otherwise.

        Args:
            message: the notification's ``user_info`` (the APNs payload).

        Returns:
            A ``MessagingMessageStatus``.
        """
        info = self._native.appDidReceiveMessage_(ns_from_py(dict(message)))
        return int(info.status)

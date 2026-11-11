"""Google Analytics for Firebase: log events and user properties.

    from pyios_firebase.analytics import Analytics, Event, Param

    Analytics.log_event(Event.SELECT_CONTENT, {
        Param.CONTENT_TYPE: "image",
        Param.ITEM_ID: "P12453",
    })
    Analytics.log_screen_view("Checkout", "CheckoutScreen")
    Analytics.set_user_property("premium", "plan")

Screen views are not logged automatically for Kivy screens (the SDK only sees
the one ``UIViewController``): call ``log_screen_view`` when a screen opens.

Names and values are checked first: a bad one raises ``ValueError`` or
``TypeError`` instead of being dropped quietly by the SDK.

To see events as they are logged, run the app with ``-FIRDebugEnabled`` (in
Xcode: Product > Scheme > Edit Scheme > Arguments) and open DebugView in the
Firebase console.

Needs the ``FirebaseAnalytics`` framework.
"""

from __future__ import annotations

__all__ = (
    "Analytics",
    "ConsentStatus",
    "ConsentType",
    "Event",
    "Param",
    "UserProperty",
)

import math
import re
from collections.abc import Callable, Mapping
from ctypes import c_int64
from typing import Any, Final

from rubicon.objc import ns_from_py, objc_id

from ..types import FirebaseError, ObjCObject
from ..util import error_from_pointer, objc_class, one_shot_block
from .names import Event, Param, UserProperty


class ConsentType:
    """What a consent covers (``FIRConsentType``)."""

    AD_STORAGE: Final = "ad_storage"
    """Storage (such as device identifiers) for advertising."""
    ANALYTICS_STORAGE: Final = "analytics_storage"
    """Storage (such as app identifiers) for analytics."""
    AD_USER_DATA: Final = "ad_user_data"
    """Sending user data to Google for advertising."""
    AD_PERSONALIZATION: Final = "ad_personalization"
    """Personalized advertising (remarketing)."""


class ConsentStatus:
    """A consent's status (``FIRConsentStatus``)."""

    GRANTED: Final = "granted"
    DENIED: Final = "denied"


_NAME: Final = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_RESERVED_PREFIXES: Final = ("firebase_", "google_", "ga_")
_RESERVED_EVENTS: Final = frozenset(
    [
        "ad_activeview",
        "ad_click",
        "ad_exposure",
        "ad_query",
        "ad_reward",
        "adunit_exposure",
        "app_clear_data",
        "app_exception",
        "app_remove",
        "app_store_refund",
        "app_store_subscription_cancel",
        "app_store_subscription_convert",
        "app_store_subscription_renew",
        "app_update",
        "app_upgrade",
        "dynamic_link_app_open",
        "dynamic_link_app_update",
        "dynamic_link_first_open",
        "error",
        "firebase_campaign",
        "first_open",
        "first_visit",
        "notification_dismiss",
        "notification_foreground",
        "notification_open",
        "notification_receive",
        "os_update",
        "session_start",
        "session_start_with_rollout",
        "user_engagement",
    ]
)
_RESERVED_USER_PROPERTIES: Final = frozenset(
    {"first_open_time", "last_deep_link_referrer", "user_id"}
)
_MAX_PARAMETERS: Final = 25
_CONSENT_TYPES: Final = frozenset(
    v for k, v in vars(ConsentType).items() if not k.startswith("_")
)
_CONSENT_STATUSES: Final = frozenset({ConsentStatus.GRANTED, ConsentStatus.DENIED})


def _check_name(name: str, what: str, max_length: int) -> None:
    if not isinstance(name, str):
        raise TypeError(f"{what} must be a str, not {type(name).__name__}")
    if not 0 < len(name) <= max_length or not _NAME.match(name):
        raise ValueError(
            f"invalid {what} {name!r}: 1 to {max_length} letters, digits and "
            "underscores, starting with a letter"
        )
    if name.startswith(_RESERVED_PREFIXES):
        raise ValueError(
            f"invalid {what} {name!r}: the prefixes firebase_, google_ and ga_ "
            "are reserved"
        )


def _parameter_value(value: Any, path: str) -> Any:
    if isinstance(value, bool):
        raise TypeError(f"{path}: Analytics has no bool parameters; use 1 / 0 or a str")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path}: cannot log {value!r}")
    if isinstance(value, str | int | float):
        return value
    if isinstance(value, list | tuple):  # Param.ITEMS: a list of item dicts
        items = []
        for i, item in enumerate(value):
            if not isinstance(item, Mapping):
                raise TypeError(f"{path}[{i}]: items must be dicts")
            items.append(_parameters(item, f"{path}[{i}]", limit=False))
        return items
    raise TypeError(
        f"{path}: parameter values must be str, int or float (or a list of "
        f"item dicts), not {type(value).__name__}"
    )


def _parameters(
    parameters: Mapping[str, Any], path: str = "", *, limit: bool = True
) -> dict[str, Any]:
    if not isinstance(parameters, Mapping):
        raise TypeError(f"parameters must be a dict, not {type(parameters).__name__}")
    if limit and len(parameters) > _MAX_PARAMETERS:
        raise ValueError(
            f"an event can have at most {_MAX_PARAMETERS} parameters, "
            f"not {len(parameters)}"
        )
    result: dict[str, Any] = {}
    for key, value in parameters.items():
        _check_name(key, "parameter name", 40)
        result[key] = _parameter_value(value, f"{path}.{key}" if path else key)
    return result


def _analytics() -> ObjCObject:
    return objc_class("FIRAnalytics")


class Analytics:
    """Google Analytics. Every method is a static method, as in the SDK::

    Analytics.log_event("level_up", {"level": 3})
    """

    @staticmethod
    def log_event(name: str, parameters: Mapping[str, Any] | None = None) -> None:
        """Log an event.

        Args:
            name: the event name: an ``Event`` constant, or your own (1 to 40
                letters, digits and underscores, starting with a letter).
            parameters: up to 25 parameters: ``Param`` constants or your own
                names, to ``str``, ``int`` or ``float`` values. ``Param.ITEMS``
                takes a list of item dicts. String values over 100 characters
                are cut by Analytics.

        Raises:
            ValueError: an invalid or reserved name, or too many parameters.
            TypeError: a value of another type (``bool`` too: use 1 / 0).
        """
        _check_name(name, "event name", 40)
        if name in _RESERVED_EVENTS:
            raise ValueError(f"{name!r} is a reserved event name (Analytics drops it)")
        native = None if parameters is None else ns_from_py(_parameters(parameters))
        _analytics().logEventWithName_parameters_(name, native)

    @staticmethod
    def log_screen_view(
        screen_name: str,
        screen_class: str | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Log that a screen was shown (the ``screen_view`` event).

        Args:
            screen_name: the screen's name, for example ``"Checkout"``.
            screen_class: the screen's class, for example the Kivy ``Screen``
                class name.
            parameters: more parameters for the event.

        Raises:
            ValueError: an invalid parameter name.
            TypeError: a parameter value of another type.
        """
        params: dict[str, Any] = {Param.SCREEN_NAME: screen_name}
        if screen_class is not None:
            params[Param.SCREEN_CLASS] = screen_class
        params.update(parameters or {})
        Analytics.log_event(Event.SCREEN_VIEW, params)

    @staticmethod
    def set_user_property(value: str | None, name: str) -> None:
        """Set a user property, to filter and compare users in reports. Register
        it in the Firebase console (Custom definitions) to see it there.

        Args:
            value: the value (up to 36 characters), or ``None`` to remove it.
            name: the property name (1 to 24 letters, digits and underscores,
                starting with a letter).

        Raises:
            ValueError: an invalid or reserved name, or a value over 36 characters.
            TypeError: ``value`` is not a ``str`` or ``None``.
        """
        _check_name(name, "user property name", 24)
        if name in _RESERVED_USER_PROPERTIES:
            raise ValueError(f"{name!r} is a reserved user property name")
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(
                    f"user property values are str, not {type(value).__name__}"
                )
            if len(value) > 36:
                raise ValueError("a user property value can be at most 36 characters")
        _analytics().setUserPropertyString_forName_(value, name)

    @staticmethod
    def set_user_id(user_id: str | None) -> None:
        """Set the user ID (your own ID for the user; never personal data such
        as an email address).

        Args:
            user_id: up to 256 characters, or ``None`` to remove it.

        Raises:
            ValueError: an empty ID or one over 256 characters.
        """
        if user_id is not None and not 0 < len(user_id) <= 256:
            raise ValueError("a user ID must be 1 to 256 characters")
        _analytics().setUserID_(user_id)

    @staticmethod
    def set_analytics_collection_enabled(enabled: bool) -> None:
        """Turn collection on or off. The setting is kept across launches. To
        start the app with it off, set ``FIREBASE_ANALYTICS_COLLECTION_ENABLED``
        to ``NO`` in ``Info.plist``.

        Args:
            enabled: ``False`` to stop collecting.
        """
        _analytics().setAnalyticsCollectionEnabled_(bool(enabled))

    @staticmethod
    def set_session_timeout_interval(seconds: float) -> None:
        """How long the app can be inactive before the session ends (default
        1800 s).

        Args:
            seconds: the timeout.
        """
        _analytics().setSessionTimeoutInterval_(float(seconds))

    @staticmethod
    def session_id(
        callback: Callable[[int | None, FirebaseError | None], None],
    ) -> None:
        """The current session's ID.

        Args:
            callback: gets ``(session_id, None)``, or ``(None, error)`` (for
                example with collection off). It runs on a background thread.
        """

        def done(session: int, error_ptr: Any) -> None:
            error = error_from_pointer(error_ptr)
            callback(None if error is not None else int(session), error)

        _analytics().sessionIDWithCompletion_(one_shot_block(done, c_int64, objc_id))

    @staticmethod
    def app_instance_id() -> str | None:
        """This app install's ID, or ``None`` when ``ANALYTICS_STORAGE``
        consent is denied."""
        value = _analytics().appInstanceID()
        return None if value is None else str(value)

    @staticmethod
    def reset_analytics_data() -> None:
        """Clear the data on this device and make a new app instance ID."""
        _analytics().resetAnalyticsData()

    @staticmethod
    def set_default_event_parameters(parameters: Mapping[str, Any] | None) -> None:
        """Parameters added to every event logged from now on (kept across
        launches).

        Args:
            parameters: parameter names to values (a ``None`` value removes
                that default), or ``None`` to remove all defaults.

        Raises:
            ValueError: an invalid name.
            TypeError: a value of another type.
        """
        if parameters is None:
            _analytics().setDefaultEventParameters_(None)
            return
        checked = _parameters(
            {k: v for k, v in parameters.items() if v is not None}, limit=False
        )
        native = objc_class("NSMutableDictionary").dictionary()
        for key, value in parameters.items():
            if value is None:
                _check_name(key, "parameter name", 40)
                native.setObject_forKey_(objc_class("NSNull").null(), key)
            else:
                native.setObject_forKey_(ns_from_py(checked[key]), key)
        _analytics().setDefaultEventParameters_(native)

    @staticmethod
    def set_consent(consent: Mapping[str, str]) -> None:
        """Set the user's consent (Google consent mode). Types left out keep
        their status.

        ::

            Analytics.set_consent({
                ConsentType.ANALYTICS_STORAGE: ConsentStatus.GRANTED,
                ConsentType.AD_STORAGE: ConsentStatus.DENIED,
            })

        Args:
            consent: ``ConsentType`` to ``ConsentStatus``.

        Raises:
            ValueError: an unknown type or status.
        """
        for kind, status in consent.items():
            if kind not in _CONSENT_TYPES:
                raise ValueError(f"unknown consent type {kind!r}: use ConsentType")
            if status not in _CONSENT_STATUSES:
                raise ValueError(
                    f"unknown consent status {status!r}: use ConsentStatus"
                )
        _analytics().setConsent_(ns_from_py(dict(consent)))

    @staticmethod
    def initiate_on_device_conversion_measurement(
        *,
        email_address: str | None = None,
        phone_number: str | None = None,
        hashed_email_address: bytes | None = None,
        hashed_phone_number: bytes | None = None,
    ) -> None:
        """Google Ads on-device conversion measurement, from what the user
        consented to share. Give exactly one argument. Needs the
        ``GoogleAdsOnDeviceConversion`` package in the app (otherwise it does
        nothing).

        Args:
            email_address: the email address.
            phone_number: the phone number in E.164 format (``"+15555550100"``).
            hashed_email_address: the SHA-256 of the normalized email address.
            hashed_phone_number: the SHA-256 of the phone number in E.164 format.

        Raises:
            ValueError: not exactly one argument.
        """
        given = [
            email_address,
            phone_number,
            hashed_email_address,
            hashed_phone_number,
        ]
        if sum(value is not None for value in given) != 1:
            raise ValueError(
                "give exactly one of email_address, phone_number, "
                "hashed_email_address, hashed_phone_number"
            )
        fir = _analytics()
        if email_address is not None:
            fir.initiateOnDeviceConversionMeasurementWithEmailAddress_(email_address)
        elif phone_number is not None:
            fir.initiateOnDeviceConversionMeasurementWithPhoneNumber_(phone_number)
        elif hashed_email_address is not None:
            fir.initiateOnDeviceConversionMeasurementWithHashedEmailAddress_(
                ns_from_py(bytes(hashed_email_address))
            )
        elif hashed_phone_number is not None:
            fir.initiateOnDeviceConversionMeasurementWithHashedPhoneNumber_(
                ns_from_py(bytes(hashed_phone_number))
            )

    @staticmethod
    def handle_open_url(url: str) -> None:
        """Tell Analytics the app was opened from a URL (campaign attribution).
        Only needed when ``FirebaseAppDelegateProxyEnabled`` is ``NO``.

        Args:
            url: the URL the app was opened with.
        """
        _analytics().handleOpenURL_(objc_class("NSURL").URLWithString_(url))

    @staticmethod
    def handle_user_activity(user_activity: ObjCObject) -> None:
        """Tell Analytics about a universal link the app was opened with. Only
        needed when ``FirebaseAppDelegateProxyEnabled`` is ``NO``.

        Args:
            user_activity: the ``NSUserActivity``.
        """
        _analytics().handleUserActivity_(user_activity)

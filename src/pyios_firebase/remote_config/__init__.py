"""Firebase Remote Config: change your app's behavior without an update.

    from pyios_firebase.remote_config import RemoteConfig

    config = RemoteConfig.setup(defaults_plist="RemoteConfigDefaults")  # once, at app start
    config.get_string("welcome_message")

    # real-time updates: activate new values as soon as they are published
    config.add_on_config_update_listener(
        lambda update, error: config.activate() if update else None
    )

The ``get_*`` methods never wait for the network: they answer from the last
activated values, then the in-app defaults, then an empty value.

In-app defaults can come from any mix of:

- a ``.plist`` file in the app bundle (``defaults_plist=``), the usual iOS way
- a dict (``defaults=``)
- an Android-format ``remote_config_defaults.xml`` file (``defaults_file=``),
  for teams that share one defaults file with an Android app

Needs the ``FirebaseRemoteConfig`` framework.
"""

from __future__ import annotations

__all__ = (
    "REMOTE_CONFIG_ERROR_DOMAIN",
    "STATUS_NAMES",
    "ActivateCallback",
    "ConfigUpdate",
    "ConfigUpdateListener",
    "FetchCallback",
    "FetchStatus",
    "RemoteConfig",
    "RemoteConfigErrorCode",
    "RemoteConfigFetchStatus",
    "RemoteConfigSource",
    "RemoteConfigValue",
    "load_defaults",
    "load_plist_defaults",
)

import json
import os
from collections.abc import Callable, Mapping
from ctypes import c_bool, c_long
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Final, Literal
from xml.etree import ElementTree

from rubicon.objc import ns_from_py, objc_id

from ..types import ErrorCallback, FirebaseError, ObjCObject
from ..util import (
    error_from_pointer,
    listener_block,
    nsdate_to_datetime,
    objc_class,
    objc_instance,
    one_shot_block,
    to_python,
)

REMOTE_CONFIG_ERROR_DOMAIN: Final = "com.google.remoteconfig.ErrorDomain"
"""The ``error.domain`` of fetch and activate errors."""

FetchStatus = Literal[
    "success_fetched_from_remote", "success_using_pre_fetched_data", "error"
]
"""The result of ``fetch_and_activate``."""

FetchCallback = Callable[[FetchStatus, FirebaseError | None], None]
"""``(status, error)`` for ``fetch_and_activate``."""

ActivateCallback = Callable[[bool, FirebaseError | None], None]
"""``(changed, error)``: whether activating changed any value, and the error."""

STATUS_NAMES: Final[dict[int, FetchStatus]] = {
    0: "success_fetched_from_remote",
    1: "success_using_pre_fetched_data",
    2: "error",
}
"""``FIRRemoteConfigFetchAndActivateStatus`` values, by number."""


class RemoteConfigSource:
    """Where a value comes from (``RemoteConfigValue.source``)."""

    REMOTE: Final = 0
    """Fetched from the server and activated."""
    DEFAULT: Final = 1
    """An in-app default."""
    STATIC: Final = 2
    """Neither: the empty / zero / False value."""


class RemoteConfigFetchStatus:
    """``RemoteConfig.last_fetch_status`` values."""

    NO_FETCH_YET: Final = 0
    SUCCESS: Final = 1
    FAILURE: Final = 2
    THROTTLED: Final = 3
    """Too many fetches: wait, or lower ``minimum_fetch_interval`` only while developing."""


class RemoteConfigErrorCode:
    """The ``error.code`` values of Remote Config errors."""

    UNKNOWN: Final = 8001
    THROTTLED: Final = 8002
    """Fetched too often (see ``RemoteConfigFetchStatus.THROTTLED``)."""
    INTERNAL_ERROR: Final = 8003


def load_defaults(path: str | os.PathLike[str]) -> dict[str, str]:
    """Read an Android-format defaults XML file into a dict.

    The format is Android's ``res/xml/remote_config_defaults.xml``::

        <defaults>
          <entry><key>welcome_message</key><value>Hello</value></entry>
        </defaults>

    Args:
        path: the file's path.

    Returns:
        ``{key: value}``, all values as strings. Entries without a key are
        skipped; a missing value is ``""``.

    Raises:
        OSError: the file cannot be read.
        xml.etree.ElementTree.ParseError: the file is not valid XML.
    """
    root = ElementTree.parse(path).getroot()
    result: dict[str, str] = {}
    for entry in root.iter("entry"):
        key = entry.findtext("key")
        if key:
            result[key] = entry.findtext("value") or ""
    return result


def load_plist_defaults(file_name: str) -> dict[str, Any]:
    """Read a dictionary plist from the app bundle into a dict.

    Args:
        file_name: the plist's name in the bundle, for example
            ``"RemoteConfigDefaults"`` (``".plist"`` is optional).

    Returns:
        The plist's keys and values, as Python values.

    Raises:
        FileNotFoundError: the bundle has no such plist.
        ValueError: the plist is not a dictionary.
    """
    file_name = file_name.removesuffix(".plist")
    path = objc_class("NSBundle").mainBundle.pathForResource_ofType_(file_name, "plist")
    if path is None:
        raise FileNotFoundError(f"{file_name}.plist is not in the app bundle")
    data = objc_class("NSDictionary").dictionaryWithContentsOfFile_(path)
    if data is None:
        raise ValueError(f"{file_name}.plist is not a dictionary plist")
    result: dict[str, Any] = to_python(data)
    return result


@dataclass(frozen=True)
class RemoteConfigValue:
    """One parameter's value, read in every type at once."""

    string: str
    """The value as a string (``""`` if none)."""
    number: float
    """The value as a number (``0.0`` if it is not one)."""
    boolean: bool
    """The value as a bool (``"true"``, ``"1"``, ``"yes"``... are True)."""
    data: bytes
    """The value's UTF-8 bytes."""
    source: int
    """A ``RemoteConfigSource`` value."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> RemoteConfigValue:
        """Copy a native ``FIRRemoteConfigValue``.

        Args:
            native: the ``FIRRemoteConfigValue``.
        """
        data = to_python(native.dataValue)
        return cls(
            string=str(native.stringValue or ""),
            number=float(native.numberValue.doubleValue),
            boolean=bool(native.boolValue),
            data=bytes(data) if data is not None else b"",
            source=int(native.source),
        )

    def json(self, default: Any = None) -> Any:
        """The value parsed as JSON, or ``default`` if it is empty or not JSON.

        Args:
            default: what to give back when the value is not JSON.
        """
        try:
            return json.loads(self.string) if self.string else default
        except ValueError:
            return default


@dataclass(frozen=True)
class ConfigUpdate:
    """What a real-time update changed."""

    updated_keys: frozenset[str]
    """The parameters whose values changed on the server (added, removed or
    changed): call ``activate`` to use the new values."""


class ConfigUpdateListener:
    """Given back by ``add_on_config_update_listener``. Call ``remove()`` to stop.

    Args:
        registration: the native ``FIRConfigUpdateListenerRegistration``.
        release: releases the listener's callback block.
    """

    def __init__(self, registration: ObjCObject, release: Callable[[], None]) -> None:
        self._registration: ObjCObject | None = registration
        self._release = release

    def remove(self) -> None:
        """Stop the updates (and the real-time connection, if it was the last
        listener). Safe to call more than once."""
        if self._registration is None:
            return
        self._registration.remove()
        self._registration = None
        self._release()


class RemoteConfig:
    """The app's Remote Config. Get it with ``RemoteConfig.remote_config()``,
    or set it up with ``RemoteConfig.setup(...)``.

    Args:
        native: the native ``FIRRemoteConfig``.
    """

    _instance: ClassVar[RemoteConfig | None] = None

    def __init__(self, native: ObjCObject) -> None:
        self._config = native

    @classmethod
    def remote_config(cls) -> RemoteConfig:
        """The shared instance for the default Firebase app."""
        if cls._instance is None:
            cls._instance = cls(objc_class("FIRRemoteConfig").remoteConfig())
        return cls._instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRRemoteConfig``."""
        return self._config

    @classmethod
    def setup(
        cls,
        defaults: Mapping[str, Any] | None = None,
        defaults_file: str | os.PathLike[str] | None = None,
        defaults_plist: str | None = None,
        minimum_fetch_interval: float = 3600,
        callback: FetchCallback | None = None,
    ) -> RemoteConfig:
        """Install the in-app defaults, then fetch and activate in the background.

        Call it once, at app start. When several sources give the same key,
        ``defaults`` wins, then ``defaults_file``, then ``defaults_plist``.

        Args:
            defaults: default values.
            defaults_file: path to an Android-format defaults XML file.
            defaults_plist: name of a plist in the app bundle.
            minimum_fetch_interval: seconds between fetches. Lower it only while
                developing: Firebase throttles apps that fetch too often.
            callback: see ``fetch_and_activate``.

        Returns:
            The shared ``RemoteConfig``.
        """
        config = cls.remote_config()
        config.minimum_fetch_interval = minimum_fetch_interval
        # merged here, because the SDK's setDefaults replaces earlier defaults
        values = (
            load_plist_defaults(defaults_plist) if defaults_plist is not None else {}
        )
        if defaults_file is not None:
            values.update(load_defaults(defaults_file))
        values.update(defaults or {})
        if values:
            config.set_defaults(values)
        config.fetch_and_activate(callback)
        return config

    # ---- settings ----------------------------------------------------------------

    def _settings(self) -> ObjCObject:
        return self._config.configSettings

    def _change_settings(
        self, minimum: float | None = None, timeout: float | None = None
    ) -> None:
        # a new settings object: the SDK reads settings when they are assigned
        settings = objc_class("FIRRemoteConfigSettings").alloc().init()
        current = self._settings()
        settings.minimumFetchInterval = float(
            current.minimumFetchInterval if minimum is None else minimum
        )
        settings.fetchTimeout = float(
            current.fetchTimeout if timeout is None else timeout
        )
        self._config.configSettings = settings

    @property
    def minimum_fetch_interval(self) -> float:
        """Seconds that must pass before a fetch reaches the server again
        (Firebase's default is 12 hours)."""
        return float(self._settings().minimumFetchInterval)

    @minimum_fetch_interval.setter
    def minimum_fetch_interval(self, seconds: float) -> None:
        self._change_settings(minimum=seconds)

    def set_minimum_fetch_interval(self, seconds: float) -> None:
        """Set ``minimum_fetch_interval``.

        Args:
            seconds: the interval. Use 0 only while developing.
        """
        self.minimum_fetch_interval = seconds

    @property
    def fetch_timeout(self) -> float:
        """Seconds a fetch may take before it fails (default 60)."""
        return float(self._settings().fetchTimeout)

    @fetch_timeout.setter
    def fetch_timeout(self, seconds: float) -> None:
        self._change_settings(timeout=seconds)

    @property
    def last_fetch_time(self) -> datetime | None:
        """When the last successful fetch finished (UTC), or ``None``."""
        return nsdate_to_datetime(self._config.lastFetchTime)

    @property
    def last_fetch_status(self) -> int:
        """A ``RemoteConfigFetchStatus`` value."""
        return int(self._config.lastFetchStatus)

    # ---- defaults ----------------------------------------------------------------

    def set_defaults(self, defaults: Mapping[str, Any]) -> None:
        """Set the in-app defaults: what ``get_*`` gives before any fetch.

        Replaces earlier defaults (use ``setup`` to merge several sources).

        Args:
            defaults: ``{key: value}``. Values can be strings, numbers or bools.
        """
        self._config.setDefaults_(ns_from_py(dict(defaults)))

    def set_defaults_from_plist(self, file_name: str) -> None:
        """Set the in-app defaults from a plist in the app bundle.

        Replaces earlier defaults.

        Args:
            file_name: the plist's name, for example ``"RemoteConfigDefaults"``
                (``".plist"`` is optional).

        Raises:
            FileNotFoundError: the bundle has no such plist.
            ValueError: the plist is not a dictionary.
        """
        self.set_defaults(load_plist_defaults(file_name))

    def default_value(self, key: str) -> RemoteConfigValue | None:
        """A parameter's in-app default.

        Args:
            key: the parameter's name.

        Returns:
            The default, or ``None`` if it has none.
        """
        native = self._config.defaultValueForKey_(key)
        return None if native is None else RemoteConfigValue.from_native(native)

    # ---- fetching ----------------------------------------------------------------

    def ensure_initialized(self, callback: ErrorCallback | None = None) -> None:
        """Wait until the values saved by the last run are loaded (before reading
        values very early at app start).

        Args:
            callback: gets ``None`` once loaded, or the error.
        """

        def done(error_ptr: Any) -> None:
            if callback is not None:
                callback(error_from_pointer(error_ptr))

        self._config.ensureInitializedWithCompletionHandler_(
            one_shot_block(done, objc_id)
        )

    def fetch(
        self,
        callback: Callable[[int, FirebaseError | None], None] | None = None,
        expiration_duration: float | None = None,
    ) -> None:
        """Fetch values from the server, without activating them.

        Args:
            callback: gets ``(RemoteConfigFetchStatus, error)``.
            expiration_duration: use cached values younger than this many
                seconds instead of ``minimum_fetch_interval``; 0 always fetches
                (only while developing).
        """

        def done(status: int, error_ptr: Any) -> None:
            if callback is not None:
                callback(int(status), error_from_pointer(error_ptr))

        block = one_shot_block(done, c_long, objc_id)
        if expiration_duration is None:
            self._config.fetchWithCompletionHandler_(block)
        else:
            self._config.fetchWithExpirationDuration_completionHandler_(
                float(expiration_duration), block
            )

    def activate(self, callback: ActivateCallback | None = None) -> None:
        """Make the last fetched values the ones ``get_*`` returns.

        Args:
            callback: gets ``(changed, error)``.
        """

        def done(changed: bool, error_ptr: Any) -> None:
            if callback is not None:
                callback(bool(changed), error_from_pointer(error_ptr))

        self._config.activateWithCompletion_(one_shot_block(done, c_bool, objc_id))

    def fetch_and_activate(self, callback: FetchCallback | None = None) -> None:
        """Fetch values from the server and activate them.

        Args:
            callback: gets ``(status, error)``; ``status`` is a ``FetchStatus``.
                Offline it gives an error, and the defaults or the last
                activated values keep being used.
        """

        def on_done(status: int, error_ptr: Any) -> None:
            if callback is not None:
                callback(
                    STATUS_NAMES.get(int(status), "error"),
                    error_from_pointer(error_ptr),
                )

        self._config.fetchAndActivateWithCompletionHandler_(
            one_shot_block(on_done, c_long, objc_id)
        )

    # ---- real-time updates ----------------------------------------------------------

    def add_on_config_update_listener(
        self, listener: Callable[[ConfigUpdate | None, FirebaseError | None], None]
    ) -> ConfigUpdateListener:
        """Listen for new values published on the server, in real time.

        The first listener opens a connection to the server. New values are
        fetched for you, but not activated: call ``activate`` in the listener.

        Args:
            listener: gets ``(ConfigUpdate, None)`` for each update, or
                ``(None, error)``.

        Returns:
            A ``ConfigUpdateListener``. Call ``.remove()`` to stop.
        """

        def on_update(update_ptr: Any, error_ptr: Any) -> None:
            if error_ptr or not update_ptr:
                listener(None, error_from_pointer(error_ptr))
                return
            keys = to_python(objc_instance(update_ptr).updatedKeys.allObjects())
            listener(ConfigUpdate(frozenset(str(k) for k in keys)), None)

        block, release = listener_block(on_update, objc_id, objc_id)
        return ConfigUpdateListener(
            self._config.addOnConfigUpdateListener_(block), release
        )

    # ---- custom signals (targeting) ------------------------------------------------

    def set_custom_signals(
        self,
        signals: Mapping[str, str | int | float | None],
        callback: ErrorCallback | None = None,
    ) -> None:
        """Set custom signals: values your Remote Config conditions can target.

        Args:
            signals: ``{name: value}``. Values are strings or numbers; ``None``
                removes the signal.
            callback: gets ``None`` once saved, or the error.

        Raises:
            TypeError: a value is not a string, number or ``None``.
        """
        payload: dict[str, Any] = {}
        for name, value in signals.items():
            if value is None:
                payload[name] = objc_class("NSNull").null()
            elif isinstance(value, str | int | float) and not isinstance(value, bool):
                payload[name] = value
            else:
                raise TypeError(
                    f"custom signal {name!r}: give a string or a number, not {type(value).__name__}"
                )

        def done(error_ptr: Any) -> None:
            if callback is not None:
                callback(error_from_pointer(error_ptr))

        self._config.setCustomSignals_withCompletion_(
            ns_from_py(payload), one_shot_block(done, objc_id)
        )

    # ---- reading values ----------------------------------------------------------------

    def get_value(self, key: str, source: int | None = None) -> RemoteConfigValue:
        """A parameter's value, in every type, with where it came from.

        Args:
            key: the parameter's name.
            source: read only from this ``RemoteConfigSource``, or ``None`` for
                the active value (remote, else default, else static).

        Returns:
            A ``RemoteConfigValue``.
        """
        if source is None:
            native = self._config.configValueForKey_(key)
        else:
            native = self._config.configValueForKey_source_(key, int(source))
        return RemoteConfigValue.from_native(native)

    def _value(self, key: str) -> ObjCObject:
        return self._config.configValueForKey_(key)

    def get_string(self, key: str) -> str:
        """A parameter's value as a string.

        Args:
            key: the parameter's name, as in the Firebase console.

        Returns:
            The active value, else the default, else ``""``.
        """
        return str(self._value(key).stringValue or "")

    def get_boolean(self, key: str) -> bool:
        """A parameter's value as a bool.

        Args:
            key: the parameter's name, as in the Firebase console.

        Returns:
            True for values like ``"true"``, ``"1"`` or ``"yes"``; False otherwise,
            and when the key has no value.
        """
        return bool(self._value(key).boolValue)

    def get_number(self, key: str) -> float:
        """A parameter's value as a float.

        Args:
            key: the parameter's name, as in the Firebase console.

        Returns:
            The value as a float; ``0.0`` if it is missing or not a number.
        """
        return float(self._value(key).numberValue.doubleValue)

    def get_long(self, key: str) -> int:
        """A parameter's value as an int.

        Args:
            key: the parameter's name, as in the Firebase console.

        Returns:
            The value as an int; ``0`` if it is missing or not a number.
        """
        return int(self._value(key).numberValue.longLongValue)

    def get_data(self, key: str) -> bytes:
        """A parameter's value as bytes (its UTF-8 encoding).

        Args:
            key: the parameter's name, as in the Firebase console.
        """
        return self.get_value(key).data

    def get_json(self, key: str, default: Any = None) -> Any:
        """A parameter's value parsed as JSON.

        Args:
            key: the parameter's name, as in the Firebase console.
            default: what to give when the value is empty or not valid JSON.

        Returns:
            The parsed value (dict, list, str, number, bool or ``None``), or
            ``default``.
        """
        return self.get_value(key).json(default)

    def all_keys(self, source: int = RemoteConfigSource.REMOTE) -> list[str]:
        """The parameter names a source has.

        Args:
            source: ``RemoteConfigSource.REMOTE`` (activated values, the
                default), ``DEFAULT`` (in-app defaults) or ``STATIC``.

        Returns:
            The names.
        """
        return [str(k) for k in to_python(self._config.allKeysFromSource_(int(source)))]

    def keys_with_prefix(self, prefix: str | None) -> set[str]:
        """The activated parameter names that start with ``prefix``.

        Args:
            prefix: the start of the names, or ``None`` for all of them.

        Returns:
            The names.
        """
        return {
            str(k) for k in to_python(self._config.keysWithPrefix_(prefix).allObjects())
        }

"""Python values and paths for the Realtime Database.

The SDK raises an Objective-C exception (which aborts the app) for a bad path,
key, value or query. These checks run first and raise a Python exception
instead, with the same rules as the SDK (``FValidation``).
"""

from __future__ import annotations

__all__ = (
    "ServerValue",
    "to_database",
    "to_priority",
    "to_query_value",
    "validate_key",
    "validate_path",
    "validate_root_path",
)

import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Any, Final

from rubicon.objc import ObjCInstance, ns_from_py

from ..util import objc_class

_BAD_PATH_CHARS: Final = frozenset("[].#$")
_BAD_KEY_CHARS: Final = _BAD_PATH_CHARS | {"/"}
_INFO_PREFIX: Final = re.compile(r"^/*\.info(/|$)")
_MAX_LEAF_BYTES: Final = 10 * 1024 * 1024
_SERVER_VALUE_KEY: Final = ".sv"
# keys that may start a dict key with "." (the SDK's export format)
_SPECIAL_KEYS: Final = frozenset({".priority", ".value", _SERVER_VALUE_KEY})


class ServerValue:
    """Values the server fills in when it applies the write.

    ::

        ref.set_value({"text": "hi", "sent_at": ServerValue.timestamp()})
        ref.child("likes").set_value(ServerValue.increment(1))
    """

    @staticmethod
    def timestamp() -> dict[str, Any]:
        """The server's time, in milliseconds since 1970, when it writes the value.

        Returns:
            The placeholder to write (``{".sv": "timestamp"}``).
        """
        return {_SERVER_VALUE_KEY: "timestamp"}

    @staticmethod
    def increment(delta: float) -> dict[str, Any]:
        """Add ``delta`` to the number stored on the server (atomically; a
        missing or non-number value counts as 0).

        Args:
            delta: the amount to add (negative to subtract).

        Returns:
            The placeholder to write (``{".sv": {"increment": delta}}``).

        Raises:
            TypeError: ``delta`` is not an ``int`` or ``float`` (or is a ``bool``).
            ValueError: ``delta`` is ``nan`` or infinite.
        """
        if isinstance(delta, bool) or not isinstance(delta, int | float):
            raise TypeError(f"increment takes a number, not {type(delta).__name__}")
        if isinstance(delta, float) and not math.isfinite(delta):
            raise ValueError(f"cannot increment by {delta!r}")
        return {_SERVER_VALUE_KEY: {"increment": delta}}


def validate_key(key: str, what: str = "key") -> None:
    """Check a single path segment (a child name).

    Args:
        key: the key.
        what: how to name it in the error message.

    Raises:
        TypeError: ``key`` is not a ``str``.
        ValueError: ``key`` is empty or holds ``/ . # $ [ ]``.
    """
    if not isinstance(key, str):
        raise TypeError(f"{what} must be a str, not {type(key).__name__}")
    if not key or _BAD_KEY_CHARS.intersection(key):
        raise ValueError(
            f"invalid {what} {key!r}: must be non-empty and not contain "
            "'/' '.' '#' '$' '[' or ']'"
        )


def validate_path(path: str, what: str = "path") -> None:
    """Check a relative path, for example ``"users/ada"``.

    Args:
        path: the path.
        what: how to name it in the error message.

    Raises:
        TypeError: ``path`` is not a ``str``.
        ValueError: ``path`` is empty or holds ``. # $ [ ]``.
    """
    if not isinstance(path, str):
        raise TypeError(f"{what} must be a str, not {type(path).__name__}")
    if not path or _BAD_PATH_CHARS.intersection(path):
        raise ValueError(
            f"invalid {what} {path!r}: must be non-empty and not contain "
            "'.' '#' '$' '[' or ']'"
        )


def validate_root_path(path: str) -> None:
    """Check a path from the root. Like ``validate_path``, but a leading
    ``.info`` (the read-only connection info) is allowed.

    Args:
        path: the path.

    Raises:
        TypeError: ``path`` is not a ``str``.
        ValueError: the path is not valid.
    """
    if not isinstance(path, str):
        raise TypeError(f"path must be a str, not {type(path).__name__}")
    validate_path(_INFO_PREFIX.sub("/", path) if ".info" in path else path)


def _path_name(parts: list[str]) -> str:
    return ".".join(parts) or "value"


def _check_leaf(value: Any, parts: list[str]) -> Any:
    if value is None:
        return objc_class("NSNull").null()  # NSDictionary/NSArray cannot hold nil
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{_path_name(parts)}: cannot store {value!r}")
        return value
    if isinstance(value, str):
        if len(value) * 4 > _MAX_LEAF_BYTES and len(value.encode()) > _MAX_LEAF_BYTES:
            raise ValueError(
                f"{_path_name(parts)}: a string can be at most 10 MB of UTF-8"
            )
        return value
    if isinstance(value, ObjCInstance):
        return value  # already native: the SDK checks it
    if isinstance(value, date):
        raise TypeError(
            f"{_path_name(parts)}: the Realtime Database has no date type. Store "
            "milliseconds since 1970 (int(dt.timestamp() * 1000)), an ISO string, "
            "or ServerValue.timestamp()"
        )
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError(
            f"{_path_name(parts)}: the Realtime Database has no bytes type. "
            "Store a base64 str, or the file in Cloud Storage"
        )
    raise TypeError(
        f"{_path_name(parts)}: cannot store a {type(value).__name__} ({value!r})"
    )


def _tree(value: Any, parts: list[str]) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{_path_name(parts)}: keys must be str, not "
                    f"{type(key).__name__} ({key!r})"
                )
            if key not in _SPECIAL_KEYS:
                validate_key(key, f"key at {_path_name([*parts, key])}")
            result[key] = _tree(item, [*parts, key])
        if _SERVER_VALUE_KEY in result and len(result) > 1:
            raise ValueError(
                f"{_path_name(parts)}: a server value cannot have other keys"
            )
        return result
    if isinstance(value, list | tuple):
        return [_tree(item, [*parts, str(i)]) for i, item in enumerate(value)]
    return _check_leaf(value, parts)


def to_database(value: Any) -> Any:
    """Turn a Python value into what the database SDK writes.

    Args:
        value: ``None``, ``bool``, ``int``, ``float``, ``str``, a
            ``ServerValue`` placeholder, or a dict (``str`` keys), list or
            tuple of those. ``None`` deletes the value. Lists are stored as
            objects with keys ``"0"``, ``"1"``...

    Returns:
        The Objective-C value.

    Raises:
        TypeError: a value the database cannot store (``datetime``, ``bytes``,
            ``set``...) or a key that is not a ``str``. The message names the
            path of the bad value.
        ValueError: an invalid key, ``nan`` / ``inf``, or a string over 10 MB.
    """
    return ns_from_py(_tree(value, []))


def to_priority(priority: Any) -> Any:
    """Check and convert a priority: ``None``, a number, a ``str`` or
    ``ServerValue.timestamp()``.

    Args:
        priority: the priority.

    Returns:
        The Objective-C value.

    Raises:
        TypeError: any other type (``bool`` too).
        ValueError: ``nan`` / ``inf``.
    """
    if isinstance(priority, Mapping):
        if set(priority) != {_SERVER_VALUE_KEY}:
            raise TypeError("a priority cannot be a dict (only a ServerValue)")
        return ns_from_py(dict(priority))
    if isinstance(priority, bool) or not (
        priority is None or isinstance(priority, int | float | str)
    ):
        raise TypeError(
            f"a priority must be None, a number or a str, not {type(priority).__name__}"
        )
    return to_database(priority)


def to_query_value(value: Any, *, strings_only: bool, priority: bool) -> Any:
    """Check and convert a ``start_at`` / ``end_at`` / ``equal_to`` value.

    Args:
        value: ``None``, ``bool``, a number or a ``str``.
        strings_only: the query is ordered by key: only ``str`` is allowed.
        priority: the query is ordered by priority: ``bool`` is not allowed.

    Returns:
        The Objective-C value, or ``None``.

    Raises:
        TypeError: a type the query cannot use.
        ValueError: ``nan`` / ``inf``.
    """
    if strings_only and not isinstance(value, str):
        raise TypeError(
            "with order_by_key, start/end/equal values must be str (the keys), "
            f"not {type(value).__name__}"
        )
    if priority and isinstance(value, bool):
        raise TypeError("with order_by_priority, values cannot be bool")
    if not (value is None or isinstance(value, bool | int | float | str)):
        raise TypeError(
            "query values must be None, bool, a number or a str, "
            f"not {type(value).__name__}"
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"cannot query by {value!r}")
    return None if value is None else ns_from_py(value)

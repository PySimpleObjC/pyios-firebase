"""Helpers shared by every Firebase product wrapper.

Most apps never need this module. It is public for advanced use:

- ``to_firestore`` / ``to_python``: the value conversion every Firestore call
  uses, for values you pass to the SDK yourself.
- ``nserror_to_dict``: turns an ``NSError`` into a ``FirebaseError``.
- ``objc_class``: looks up an Objective-C class the first time it is used, so
  importing a module never needs a framework you do not use.
- ``one_shot_block`` / ``listener_block``: keep a callback block alive until
  Firebase is done with it.
"""

from __future__ import annotations

__all__ = (
    "QueryDict",
    "datetime_to_timestamp",
    "error_from_pointer",
    "listener_block",
    "nsdate_to_datetime",
    "nserror_to_dict",
    "objc_class",
    "objc_instance",
    "one_shot_block",
    "timestamp_to_datetime",
    "to_firestore",
    "to_python",
)

from collections.abc import Callable, Mapping
from ctypes import CDLL, c_ulong
from datetime import UTC, date, datetime, timedelta
from functools import cache
from typing import Any

from rubicon.objc import Block, ObjCClass, ObjCInstance, ns_from_py, py_from_ns
from rubicon.objc.runtime import Foundation, load_library, objc_id

from .types import FirebaseError, ObjCObject, QueryDict

# ---- Objective-C classes ----------------------------------------------------


def objc_instance(pointer: Any) -> ObjCObject:
    """Wrap a raw Objective-C pointer (for example a block argument) as an object.

    Args:
        pointer: an ``objc_id`` (or an address) that points to a live
            Objective-C object.

    Returns:
        A Rubicon object whose attributes are the Objective-C object's
        properties and methods.
    """
    return ObjCInstance(pointer)


@cache
def objc_class(name: str) -> ObjCObject:
    """An Objective-C class, looked up by name on first use and then cached.

    Args:
        name: the class name, for example ``"FIRFirestore"``.

    Returns:
        The class, as a Rubicon object.

    Raises:
        NameError: the app does not have the class (its framework is not
            linked).
    """
    return ObjCClass(name)


def _optional_class(name: str) -> ObjCObject | None:
    """``objc_class(name)``, or ``None`` when the app does not have it."""
    try:
        return objc_class(name)
    except NameError:
        return None


# ---- keeping blocks alive ---------------------------------------------------

# Firebase keeps only a C pointer to a block's code. If Python deletes the
# Block object first, the app crashes when Firebase calls it. Every block
# stays in this set until it is no longer needed.
_blocks: set[Block] = set()


def one_shot_block(function: Callable[..., Any], *argtypes: Any) -> Block:
    """Make a block that Firebase calls once, for a completion handler.

    The block is kept alive until that call, then released.

    Args:
        function: called with the block's arguments (raw ``objc_id`` pointers
            for objects).
        *argtypes: the ctypes type of each block argument, for example
            ``objc_id``.
    """
    holder: dict[str, Block] = {}

    def call(*args: Any) -> Any:
        _blocks.discard(holder["block"])
        return function(*args)

    holder["block"] = block = Block(call, None, *argtypes)
    _blocks.add(block)
    return block


def listener_block(
    function: Callable[..., Any], *argtypes: Any, restype: Any = None
) -> tuple[Block, Callable[[], None]]:
    """Make a block that Firebase may call many times (snapshot listeners,
    transaction functions).

    Args:
        function: called with the block's arguments on every call.
        *argtypes: the ctypes type of each block argument.
        restype: the ctypes type the block returns, or ``None`` for void.

    Returns:
        ``(block, release)``. Call ``release()`` once Firebase is done with the
        block; until then it is kept alive.
    """
    block = Block(function, restype, *argtypes)
    _blocks.add(block)
    return block, lambda: _blocks.discard(block)


# ---- NSError conversion -----------------------------------------------------


@cache
def _underlying_error_key() -> str:
    # Apple's NSUnderlyingErrorKey constant, read from Foundation itself
    return str(objc_instance(objc_id.in_dll(Foundation, "NSUnderlyingErrorKey")))


def nserror_to_dict(error: ObjCObject | None) -> FirebaseError | None:
    """Turn an ``NSError`` into a ``FirebaseError``.

    Args:
        error: the ``NSError``, or ``None``.

    Returns:
        A ``FirebaseError`` with ``code``, ``description`` and ``domain`` as
        plain ``int`` / ``str`` and ``underlying_error`` as the nested
        ``NSError`` (or ``None``); ``None`` when ``error`` is ``None``.
    """
    if error is None:
        return None
    underlying = error.userInfo.objectForKey_(_underlying_error_key())
    return FirebaseError(
        {
            "code": int(error.code),
            "description": str(error.localizedDescription),
            "domain": str(error.domain),
            "underlying_error": underlying,
        }
    )


def error_from_pointer(error_ptr: Any) -> FirebaseError | None:
    """``nserror_to_dict`` for a raw block argument.

    Args:
        error_ptr: the ``NSError *`` a completion block received: an
            ``objc_id``, or ``None`` / a null pointer when there was no error.

    Returns:
        A ``FirebaseError``, or ``None`` when there was no error.
    """
    return nserror_to_dict(objc_instance(error_ptr)) if error_ptr else None


# ---- Firestore value conversion ---------------------------------------------

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def timestamp_to_datetime(ts: Any) -> datetime:
    """Turn a ``FIRTimestamp`` into an aware ``datetime`` in UTC.

    Integer math, so no microseconds are lost to float rounding (that happens
    for dates far from 1970). Nanoseconds below a microsecond are dropped:
    ``datetime`` cannot hold them.

    Args:
        ts: a ``FIRTimestamp``, or anything with ``seconds`` and
            ``nanoseconds`` attributes.

    Returns:
        The same instant, with ``tzinfo=UTC``.
    """
    return _EPOCH + timedelta(
        seconds=int(ts.seconds), microseconds=int(ts.nanoseconds) // 1000
    )


def nsdate_to_datetime(value: ObjCObject | None) -> datetime | None:
    """Turn an ``NSDate`` into an aware ``datetime`` in UTC.

    Args:
        value: the ``NSDate``, or ``None``.

    Returns:
        The same instant with ``tzinfo=UTC`` (to the microsecond), or ``None``.
    """
    if value is None:
        return None
    # a property in Apple's headers, but Rubicon exposes it as a method
    interval: ObjCObject = value.timeIntervalSince1970
    if callable(interval):
        interval = interval()
    seconds = float(interval)
    whole = int(seconds // 1)
    return _EPOCH + timedelta(
        seconds=whole, microseconds=round((seconds - whole) * 1_000_000)
    )


def datetime_to_timestamp(value: datetime) -> ObjCObject:
    """Turn a ``datetime`` into a ``FIRTimestamp``, to the microsecond.

    Args:
        value: the date and time. A naive datetime (no ``tzinfo``) is read as
            UTC, like the Firebase Admin SDK for Python does; pass an aware
            datetime to be explicit.

    Returns:
        A ``FIRTimestamp`` for the same instant.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    # integer math on the timedelta: a float timestamp would lose microseconds
    delta = value - _EPOCH
    seconds = delta.days * 86_400 + delta.seconds
    return objc_class("FIRTimestamp").timestampWithSeconds_nanoseconds_(
        seconds, delta.microseconds * 1000
    )


def _to_firestore_tree(value: Any, path: str) -> Any:
    if value is None:
        return objc_class("NSNull").null()  # NSDictionary/NSArray cannot hold nil
    if isinstance(value, ObjCInstance | str | bool | int | float | bytes):
        return value
    if isinstance(value, datetime):
        return datetime_to_timestamp(value)
    if isinstance(value, date):
        raise TypeError(
            f"{path or 'value'}: Firestore has no date-only type. Pass a datetime, "
            "for example datetime.combine(d, time(), tzinfo=UTC)"
        )
    if isinstance(value, Mapping):  # dict, MappingProxyType, ChainMap, ...
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{path or 'data'}: field names must be str, "
                    f"not {type(key).__name__} ({key!r})"
                )
            result[key] = _to_firestore_tree(item, f"{path}.{key}" if path else key)
        return result
    if isinstance(value, list | tuple):
        return [
            _to_firestore_tree(item, f"{path}[{i}]") for i, item in enumerate(value)
        ]

    from .firestore.document_reference import DocumentReference

    if isinstance(value, DocumentReference):
        return value._ref
    raise TypeError(
        f"{path or 'value'}: cannot store a {type(value).__name__} "
        f"in Firestore ({value!r})"
    )


def to_firestore(value: Any) -> Any:
    """Turn a Python value into what the Firestore SDK expects.

    Converts inside dicts, lists and tuples too. The opposite of
    ``to_python``.

    - ``datetime`` becomes a ``FIRTimestamp`` (naive datetimes are read as UTC)
    - ``None`` becomes ``NSNull`` (Firestore ``null``)
    - tuples become arrays
    - ``DocumentReference`` becomes the native reference
    - ``FieldValue`` sentinels and other Objective-C objects pass through

    Args:
        value: the value: ``str``, ``int``, ``float``, ``bool``, ``None``,
            ``bytes``, ``datetime``, ``DocumentReference``, a ``FieldValue``,
            or a dict (with ``str`` keys), list or tuple of those.

    Returns:
        The Objective-C value (``NSDictionary``, ``NSArray``, ...).

    Raises:
        TypeError: the value cannot be stored in Firestore (for example a
            ``date``, a ``set``, or a field name that is not a ``str``). The
            message starts with the path of the bad field, for example
            ``"events[0].at"``. Nothing is sent to Firestore.
    """
    return ns_from_py(_to_firestore_tree(value, ""))


@cache
def _cf_boolean_type_id() -> tuple[CDLL, int]:
    core_foundation = load_library("CoreFoundation")
    core_foundation.CFBooleanGetTypeID.restype = c_ulong
    core_foundation.CFBooleanGetTypeID.argtypes = []
    core_foundation.CFGetTypeID.restype = c_ulong
    core_foundation.CFGetTypeID.argtypes = [objc_id]
    return core_foundation, int(core_foundation.CFBooleanGetTypeID())


def _is_boolean(number: ObjCObject) -> bool:
    # NSNumber booleans are CFBoolean; py_from_ns would turn them into 1 / 0
    core_foundation, boolean_type_id = _cf_boolean_type_id()
    return bool(core_foundation.CFGetTypeID(number.ptr) == boolean_type_id)


def to_python(value: Any) -> Any:
    """Turn a value from the Firebase SDK into plain Python.

    Converts inside dictionaries and arrays too. The opposite of
    ``to_firestore``.

    - ``NSDictionary`` / ``NSArray`` become ``dict`` / ``list``
    - ``NSString`` becomes ``str``, ``NSData`` becomes ``bytes``
    - ``NSNumber`` becomes ``bool``, ``int`` or ``float`` (booleans stay ``bool``)
    - ``NSNull`` becomes ``None``
    - ``NSDate`` and ``FIRTimestamp`` become an aware ``datetime`` (UTC)
    - ``FIRDocumentReference`` becomes a ``DocumentReference``
    - anything else that is still Objective-C (for example ``FIRGeoPoint``) is
      left as it is

    Args:
        value: an Objective-C object, or a Python value (dict, list, ...)
            that may still hold some.

    Returns:
        The value as plain Python.
    """
    if isinstance(value, dict):
        return {key: to_python(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_python(item) for item in value]
    if not isinstance(value, ObjCInstance):
        return value

    if value.isKindOfClass(objc_class("NSDictionary")):
        return {
            str(key): to_python(value.objectForKey_(key)) for key in value.allKeys()
        }
    if value.isKindOfClass(objc_class("NSArray")):
        array: ObjCObject = value  # Rubicon's NSArray wrapper supports len()
        return [to_python(array.objectAtIndex_(i)) for i in range(len(array))]
    if value.isKindOfClass(objc_class("NSNumber")):
        if _is_boolean(value):
            return bool(value.boolValue)
        return py_from_ns(value)
    if value.isKindOfClass(objc_class("NSString")) or value.isKindOfClass(
        objc_class("NSData")
    ):
        return py_from_ns(value)
    if value.isKindOfClass(objc_class("NSNull")):
        return None
    if value.isKindOfClass(objc_class("NSDate")):
        return nsdate_to_datetime(value)
    # optional: Functions results come through here too, in apps that may not
    # link FirebaseFirestore
    timestamp_class = _optional_class("FIRTimestamp")
    if timestamp_class is not None and value.isKindOfClass(timestamp_class):
        return timestamp_to_datetime(value)
    reference_class = _optional_class("FIRDocumentReference")
    if reference_class is not None and value.isKindOfClass(reference_class):
        from .firestore.document_reference import DocumentReference

        return DocumentReference(value)
    return value

"""Realtime Database errors."""

from __future__ import annotations

__all__ = (
    "DATABASE_ERROR_DOMAIN",
    "DatabaseError",
    "DatabaseErrorCode",
    "database_error",
    "database_error_from_pointer",
)

from typing import Any, Final

from ..types import FirebaseError, ObjCObject
from ..util import nserror_to_dict, objc_instance

DATABASE_ERROR_DOMAIN: Final = "com.firebase"
"""The ``error.domain`` of errors from the database server."""


class DatabaseErrorCode:
    """The ``error.code`` values of database errors (``DATABASE_ERROR_DOMAIN``)."""

    PERMISSION_DENIED: Final = 1
    """The security rules do not allow this read or write."""
    UNAVAILABLE: Final = 2
    """The server is unavailable."""
    WRITE_CANCELED: Final = 3
    """The write was cancelled (for example by ``purge_outstanding_writes``)."""
    OTHER: Final = 9999
    """Any other server status. ``description`` has the status (for example
    ``"datastale"`` or ``"maxretry"`` for a transaction)."""


_CODE_NAMES: Final[dict[int, str]] = {
    value: name
    for name, value in vars(DatabaseErrorCode).items()
    if isinstance(value, int)
}


class DatabaseError(FirebaseError):
    """An error from the Realtime Database."""

    name: str
    """The ``DatabaseErrorCode`` name of ``code`` (for example
    ``"PERMISSION_DENIED"``), or ``""`` for errors from other domains (such as
    ``get_data`` failing offline)."""


def database_error(error: ObjCObject | None) -> DatabaseError | None:
    """Turn an ``NSError`` from the database into a ``DatabaseError``.

    Args:
        error: the ``NSError``, or ``None``.

    Returns:
        A ``DatabaseError``, or ``None`` when ``error`` is ``None``.
    """
    base = nserror_to_dict(error)
    if base is None:
        return None
    result = DatabaseError(base)
    result.name = (
        _CODE_NAMES.get(result.code, "")
        if result.domain == DATABASE_ERROR_DOMAIN
        else ""
    )
    return result


def database_error_from_pointer(error_ptr: Any) -> DatabaseError | None:
    """``database_error`` for a raw block argument.

    Args:
        error_ptr: the ``NSError *`` a block received (``objc_id``), or a null
            pointer.
    """
    return database_error(objc_instance(error_ptr)) if error_ptr else None

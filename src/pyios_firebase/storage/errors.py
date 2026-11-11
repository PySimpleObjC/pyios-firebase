"""Cloud Storage errors."""

from __future__ import annotations

__all__ = (
    "STORAGE_ERROR_DOMAIN",
    "StorageError",
    "StorageErrorCode",
    "size_exceeded_error",
    "storage_error_from_pointer",
)

from typing import Any, Final

from ..types import FirebaseError, ObjCObject
from ..util import nserror_to_dict, objc_instance

STORAGE_ERROR_DOMAIN: Final = "FIRStorageErrorDomain"
"""The ``error.domain`` of Cloud Storage errors."""


class StorageErrorCode:
    """The ``error.code`` values of Cloud Storage errors (``FIRStorageErrorCode``)."""

    UNKNOWN: Final = -13000
    OBJECT_NOT_FOUND: Final = -13010
    """No file at that path."""
    BUCKET_NOT_FOUND: Final = -13011
    PROJECT_NOT_FOUND: Final = -13012
    QUOTA_EXCEEDED: Final = -13013
    UNAUTHENTICATED: Final = -13020
    """The rules need a signed-in user."""
    UNAUTHORIZED: Final = -13021
    """The security rules do not allow this."""
    RETRY_LIMIT_EXCEEDED: Final = -13030
    """The operation kept failing for longer than the max retry time."""
    NON_MATCHING_CHECKSUM: Final = -13031
    DOWNLOAD_SIZE_EXCEEDED: Final = -13032
    """The file is bigger than ``max_size`` in ``get_data``."""
    CANCELLED: Final = -13040
    """The task was cancelled."""
    INVALID_ARGUMENT: Final = -13050
    BUCKET_MISMATCH: Final = -13051
    INTERNAL_ERROR: Final = -13052
    PATH_ERROR: Final = -13053


_CODE_NAMES: Final[dict[int, str]] = {
    value: name
    for name, value in vars(StorageErrorCode).items()
    if isinstance(value, int)
}


class StorageError(FirebaseError):
    """An error from Cloud Storage."""

    name: str
    """The ``StorageErrorCode`` name of ``code`` (for example
    ``"OBJECT_NOT_FOUND"``), or ``""`` for errors from other domains."""


def storage_error(error: ObjCObject) -> StorageError:
    """Turn an ``NSError`` from Cloud Storage into a ``StorageError``.

    Args:
        error: the ``NSError``.
    """
    result = StorageError(nserror_to_dict(error) or {})
    result.name = (
        _CODE_NAMES.get(result.code, "")
        if result.domain == STORAGE_ERROR_DOMAIN
        else ""
    )
    return result


def storage_error_from_pointer(error_ptr: Any) -> StorageError | None:
    """``storage_error`` for a raw block argument.

    Args:
        error_ptr: the ``NSError *`` a block received, or a null pointer / ``None``.

    Returns:
        A ``StorageError``, or ``None`` when there was no error.
    """
    return storage_error(objc_instance(error_ptr)) if error_ptr else None


def size_exceeded_error(size: int, max_size: int) -> StorageError:
    """A ``DOWNLOAD_SIZE_EXCEEDED`` error made in Python.

    Args:
        size: the bytes received.
        max_size: the limit that was asked for.
    """
    return StorageError(
        code=StorageErrorCode.DOWNLOAD_SIZE_EXCEEDED,
        description=f"the file is {size} bytes, more than max_size ({max_size})",
        domain=STORAGE_ERROR_DOMAIN,
        underlying_error=None,
        name="DOWNLOAD_SIZE_EXCEEDED",
    )

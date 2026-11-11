"""Firestore enum values.

These are fixed numbers in the compiled SDK and cannot be looked up by name
from Python. If you update the Firebase SDK, check them against the headers
(FIRFirestoreSource.h, FIRDocumentSnapshot.h, FIRAggregateSource.h,
FIRSnapshotListenOptions.h, FIRDocumentChange.h).
"""

from __future__ import annotations

__all__ = (
    "FIRAggregateSource",
    "FIRDocumentChangeType",
    "FIRFirestoreSource",
    "FIRListenSource",
    "FIRServerTimestampBehavior",
)

from typing import Final


class FIRFirestoreSource:
    """Where ``get_document`` / ``get_documents`` read from."""

    Default: Final = 0
    """The server when online, else the cache."""
    Server: Final = 1
    """Only the server. Fails when offline."""
    Cache: Final = 2
    """Only the local cache. Fails if the data is not cached."""


class FIRServerTimestampBehavior:
    """What a server timestamp that is still pending reads as, before the
    server has set it."""

    None_: Final = 0
    """``None`` (named ``None_`` because ``None`` is a Python keyword)."""
    Estimate: Final = 1
    """An estimate from the local clock."""
    Previous: Final = 2
    """The field's previous value."""


class FIRAggregateSource:
    """Where aggregate queries (count, sum, average) are calculated."""

    Server: Final = 0
    """On the server. The only option the SDK offers."""


class FIRListenSource:
    """Where a snapshot listener gets its data."""

    Default: Final = 0
    """The server and the cache."""
    Cache: Final = 1
    """Only the local cache."""


class FIRDocumentChangeType:
    """The raw values behind ``DocumentChange.type``."""

    Added: Final = 0
    Modified: Final = 1
    Removed: Final = 2

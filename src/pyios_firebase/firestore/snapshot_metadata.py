"""``SnapshotMetadata``: whether a snapshot came from the cache."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("SnapshotMetadata",)


class SnapshotMetadata:
    """Where a snapshot's data came from.

    Args:
        metadata: the native ``FIRSnapshotMetadata``.
    """

    def __init__(self, metadata: ObjCObject) -> None:
        self._metadata = metadata

    @property
    def is_from_cache(self) -> bool:
        """True if the data came from the local cache, not the server."""
        # custom getters (getter=isFromCache / hasPendingWrites) are methods in
        # Rubicon: without the call, bool() of the bound method is always True
        return bool(self._metadata.isFromCache())

    @property
    def has_pending_writes(self) -> bool:
        """True if the data has local writes that the server has not confirmed yet."""
        return bool(self._metadata.hasPendingWrites())

    def __repr__(self) -> str:
        return (
            f"SnapshotMetadata(is_from_cache={self.is_from_cache}, "
            f"has_pending_writes={self.has_pending_writes})"
        )

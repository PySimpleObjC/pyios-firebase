"""Snapshot listener handles (``ListenerRegistration``) and options."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("ListenerRegistration", "SnapshotListenOptions")

from collections.abc import Callable

from ..util import objc_class


class ListenerRegistration:
    """Given back by every ``add_snapshot_listener``. Call ``remove()`` to stop.

    A listener keeps using the network (and counts reads) until it is removed.

    Args:
        registration: the native ``FIRListenerRegistration``.
        on_remove: called once, when the listener is removed (releases the
            listener's callback block).
    """

    def __init__(self, registration: ObjCObject, on_remove: Callable[[], None]) -> None:
        self._registration: ObjCObject | None = registration
        self._on_remove = on_remove

    def remove(self) -> None:
        """Stop the updates. Safe to call more than once."""
        if self._registration is None:
            return
        self._registration.remove()
        self._registration = None
        self._on_remove()


class SnapshotListenOptions:
    """Options for ``add_snapshot_listener(options=...)``.

    Args:
        include_metadata_changes: also call back when only the metadata
            changes (for example ``has_pending_writes`` becoming False).
        source: ``FIRListenSource.Default`` or ``FIRListenSource.Cache``.
    """

    def __init__(
        self, include_metadata_changes: bool = False, source: int | None = None
    ) -> None:
        options = objc_class("FIRSnapshotListenOptions").alloc().init()
        if include_metadata_changes:
            options = options.optionsWithIncludeMetadataChanges_(True)
        if source is not None:
            options = options.optionsWithSource_(source)
        self._options: ObjCObject = options

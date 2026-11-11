"""``DocumentSnapshot``: the data of one document, as read at one moment."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("DocumentSnapshot",)

from typing import Any

from ..util import to_python
from . import document_reference  # module import: document_reference imports us back
from .snapshot_metadata import SnapshotMetadata


def _dict(raw: ObjCObject | None) -> dict[str, Any]:
    if raw is None:
        return {}
    data: dict[str, Any] = to_python(raw)
    return data


class DocumentSnapshot:
    """The data of one document, as read at one moment.

    Values are plain Python (see ``to_python``): timestamps are ``datetime``,
    ``null`` is ``None``, references are ``DocumentReference``.

    Snapshots come from callbacks; you do not make them yourself.

    Args:
        snapshot: the native ``FIRDocumentSnapshot``.
    """

    def __init__(self, snapshot: ObjCObject) -> None:
        self._snapshot = snapshot

    @property
    def document_id(self) -> str:
        """The document's ID (the last part of its path)."""
        return str(self._snapshot.documentID)

    @property
    def exists(self) -> bool:
        """True if the document exists. When False, ``data`` is ``{}``."""
        return bool(self._snapshot.exists)

    @property
    def reference(self) -> document_reference.DocumentReference:
        """The ``DocumentReference`` this snapshot was read from."""
        return document_reference.DocumentReference(self._snapshot.reference)

    @property
    def metadata(self) -> SnapshotMetadata:
        """Whether the data came from the cache, and has pending writes."""
        return SnapshotMetadata(self._snapshot.metadata)

    @property
    def data(self) -> dict[str, Any]:
        """All fields as a dict. ``{}`` when the document does not exist.

        Pending server timestamps read as ``None``; see
        ``data_with_server_timestamp_behavior``.
        """
        return _dict(self._snapshot.data())

    def data_with_server_timestamp_behavior(self, behavior: int) -> dict[str, Any]:
        """All fields, choosing how pending server timestamps read.

        Args:
            behavior: ``FIRServerTimestampBehavior.None_`` / ``Estimate`` /
                ``Previous``.
        """
        return _dict(self._snapshot.dataWithServerTimestampBehavior_(behavior))

    def get(self, field: str) -> Any:
        """One field's value.

        ::

            snapshot.get("name")
            snapshot.get("address.city")  # a nested field
            snapshot["name"]              # the same as get("name")

        Args:
            field: the field name. Use a dotted name for a nested field.

        Returns:
            The value as Python (see ``to_python``), or ``None`` if the field (or
            the document) does not exist.
        """
        raw = self._snapshot.valueForField_(field)
        if raw is None:
            return None
        return to_python(raw)

    def __getitem__(self, field: str) -> Any:
        """``snapshot["name"]``: the same as ``snapshot.get("name")``."""
        return self.get(field)

    def __repr__(self) -> str:
        return f"DocumentSnapshot({self.document_id!r}, exists={self.exists})"

"""``DocumentChange``: one change between two snapshots of a query."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("DocumentChange",)

from typing import ClassVar, Final, Literal

from .document_snapshot import DocumentSnapshot
from .enums import FIRDocumentChangeType

ChangeType = Literal["added", "modified", "removed"]


class DocumentChange:
    """One change in a ``QuerySnapshot``: a document was added, modified or
    removed since the previous snapshot.

    Changes come from ``QuerySnapshot.document_changes``; you do not make
    them yourself.

    Args:
        change: the native ``FIRDocumentChange``.
    """

    ADDED: Final = "added"
    MODIFIED: Final = "modified"
    REMOVED: Final = "removed"

    _TYPES: ClassVar[dict[int, ChangeType]] = {
        FIRDocumentChangeType.Added: "added",
        FIRDocumentChangeType.Modified: "modified",
        FIRDocumentChangeType.Removed: "removed",
    }

    def __init__(self, change: ObjCObject) -> None:
        self._change = change

    @property
    def type(self) -> ChangeType:
        """``DocumentChange.ADDED``, ``MODIFIED`` or ``REMOVED``."""
        return self._TYPES[int(self._change.type)]

    @property
    def document(self) -> DocumentSnapshot:
        """The document after the change (before it, for ``REMOVED``)."""
        return DocumentSnapshot(self._change.document)

    @property
    def old_index(self) -> int:
        """The document's position in the previous snapshot (a very large
        number, ``NSNotFound``, for ``ADDED``)."""
        return int(self._change.oldIndex)

    @property
    def new_index(self) -> int:
        """The document's position in this snapshot (``NSNotFound`` for ``REMOVED``)."""
        return int(self._change.newIndex)

    def __repr__(self) -> str:
        return f"DocumentChange({self.type!r}, {self.document!r})"

"""``QuerySnapshot``: the result of a query, usable like a list."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("QuerySnapshot",)

from collections.abc import Iterator
from typing import overload

from . import query  # module import: query imports us back
from .document_change import DocumentChange
from .document_snapshot import DocumentSnapshot
from .snapshot_metadata import SnapshotMetadata


class QuerySnapshot:
    """The result of a query. You can use it like a list of ``DocumentSnapshot``::

        for doc in snapshot: ...
        len(snapshot), snapshot[0], snapshot[-1], snapshot[1:3]

    Snapshots come from callbacks; you do not make them yourself.

    Args:
        snapshot: the native ``FIRQuerySnapshot``.
    """

    def __init__(self, snapshot: ObjCObject) -> None:
        self._snapshot = snapshot
        self._documents: list[DocumentSnapshot] | None = None  # made on first use

    @property
    def query(self) -> query.Query:
        """The query that made this snapshot."""
        return query.Query(self._snapshot.query)

    @property
    def metadata(self) -> SnapshotMetadata:
        """Whether the data came from the cache, and has pending writes."""
        return SnapshotMetadata(self._snapshot.metadata)

    @property
    def is_empty(self) -> bool:
        """True if no documents matched."""
        # a custom getter (getter=isEmpty): Rubicon exposes it as a method
        return bool(self._snapshot.isEmpty())

    @property
    def count(self) -> int:
        """The number of documents. The same as ``len(snapshot)``."""
        return int(self._snapshot.count)

    @property
    def documents(self) -> list[DocumentSnapshot]:
        """The documents, in query order."""
        if self._documents is None:
            self._documents = [DocumentSnapshot(d) for d in self._snapshot.documents]
        return self._documents

    @property
    def document_changes(self) -> list[DocumentChange]:
        """What changed since the previous snapshot of a listener. For the
        first snapshot (and for ``get_documents``) every document is ``ADDED``."""
        return [DocumentChange(diff) for diff in self._snapshot.documentChanges]

    def document_changes_with_include_metadata_changes(
        self, include_metadata_changes: bool
    ) -> list[DocumentChange]:
        """What changed since the previous snapshot, optionally with metadata-only changes.

        Args:
            include_metadata_changes: ``True`` to also list documents whose only
                change is their metadata (for example a pending write the server
                has now confirmed). ``False`` gives the same as
                ``document_changes``.

        Returns:
            A list of ``DocumentChange``.
        """
        changes = self._snapshot.documentChangesWithIncludeMetadataChanges_(
            include_metadata_changes
        )
        return [DocumentChange(diff) for diff in changes]

    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[DocumentSnapshot]:
        return iter(self.documents)

    @overload
    def __getitem__(self, index: int) -> DocumentSnapshot: ...
    @overload
    def __getitem__(self, index: slice) -> list[DocumentSnapshot]: ...
    def __getitem__(
        self, index: int | slice
    ) -> DocumentSnapshot | list[DocumentSnapshot]:
        return self.documents[index]

    def __repr__(self) -> str:
        return f"QuerySnapshot({len(self)} documents)"

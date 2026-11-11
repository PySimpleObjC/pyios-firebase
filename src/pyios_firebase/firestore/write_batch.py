"""``WriteBatch``: many writes that all succeed or all fail."""

from __future__ import annotations

from ..types import ObjCObject

__all__ = ("WriteBatch",)

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..types import ErrorCallback, FirestoreData
from ..util import to_firestore
from ._write import write_block

if TYPE_CHECKING:
    from .document_reference import DocumentReference


class WriteBatch:
    """Many writes saved together: all of them work, or none do.

    Up to 500 writes. Use a batch only once. Every method except ``commit``
    gives back the batch, so you can chain them::

        db.batch().set_data({"a": 1}, doc_a).delete_document(doc_b).commit(on_done)

    Get a batch with ``Firestore.batch()``.

    Args:
        batch: the native ``FIRWriteBatch``.
    """

    def __init__(self, batch: ObjCObject) -> None:
        self._batch = batch

    def set_data(
        self, data: FirestoreData, document: DocumentReference, merge: bool = False
    ) -> WriteBatch:
        """Write a document, creating it if needed.

        Args:
            data: the fields, as Python values (see ``to_firestore``).
            document: the document to write.
            merge: ``False`` replaces the whole document; ``True`` keeps the
                fields not in ``data``.

        Returns:
            This batch, for chaining.

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        if merge:
            self._batch.setData_forDocument_merge_(
                to_firestore(data), document._ref, True
            )
        else:
            self._batch.setData_forDocument_(to_firestore(data), document._ref)
        return self

    def set_data_merge_fields(
        self, data: FirestoreData, document: DocumentReference, fields: Sequence[str]
    ) -> WriteBatch:
        """Write only some fields of ``data`` to a document, keeping the others.

        Args:
            data: the fields, as Python values (see ``to_firestore``).
            document: the document to write.
            fields: the field names to write (dotted for nested fields). Fields
                of ``data`` not listed here are ignored.

        Returns:
            This batch, for chaining.

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        self._batch.setData_forDocument_mergeFields_(
            to_firestore(data), document._ref, list(fields)
        )
        return self

    def update_data(
        self, data: FirestoreData, document: DocumentReference
    ) -> WriteBatch:
        """Change only the given fields of a document.

        The document must exist when the batch is committed, or the whole batch
        fails.

        Args:
            data: the fields, as Python values (see ``to_firestore``).
                Dotted names change one nested field.
            document: the document to change.

        Returns:
            This batch, for chaining.

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        self._batch.updateData_forDocument_(to_firestore(data), document._ref)
        return self

    def delete_document(self, document: DocumentReference) -> WriteBatch:
        """Delete a document. Its sub collections are not deleted.

        Args:
            document: the document to delete. A missing document is not an error.

        Returns:
            This batch, for chaining.
        """
        self._batch.deleteDocument_(document._ref)
        return self

    def commit(self, callback: ErrorCallback | None = None) -> None:
        """Send all the writes.

        Args:
            callback: gets ``None`` once all the writes are saved, or the error
                (then none of them is saved).
        """
        self._batch.commitWithCompletion_(write_block(callback))

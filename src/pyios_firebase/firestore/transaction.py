"""``Transaction``: atomic reads and writes inside ``Firestore.run_transaction``."""

from __future__ import annotations

from ..types import ObjCObject
from ..util import objc_instance

__all__ = ("Transaction", "TransactionException")

from typing import TYPE_CHECKING, Any

from ..types import FirestoreData
from ..util import nserror_to_dict, to_firestore
from .document_snapshot import DocumentSnapshot

if TYPE_CHECKING:
    from .document_reference import DocumentReference


class TransactionException(Exception):
    """Raise inside a ``run_transaction`` function to stop the transaction.
    Its message becomes the callback's ``error.description``. (Any other
    exception stops the transaction too.)"""


class Transaction:
    """Given to your function inside ``Firestore.run_transaction``.

    Do all reads before any write. The write methods give back the
    transaction, so you can chain them.

    Args:
        transaction: the native ``FIRTransaction``.
        error_pointer: where Firestore expects an error, as an
            ``NSError **`` pointer.
    """

    def __init__(self, transaction: ObjCObject, error_pointer: Any) -> None:
        self._transaction = transaction
        self._error_pointer = error_pointer

    def get_document(self, document_reference: DocumentReference) -> DocumentSnapshot:
        """Read a document inside the transaction.

        Reads must come before any write in the same transaction.

        Args:
            document_reference: the document to read.

        Returns:
            A ``DocumentSnapshot`` (``exists`` is False for a missing document).

        Raises:
            TransactionException: the read failed. Let it propagate: the
                transaction stops with Firestore's error.
        """
        snapshot = self._transaction.getDocument_error_(
            document_reference._ref, self._error_pointer
        )
        error = self._error_pointer[0]
        if error.value is not None:
            # Firestore's error stays in the pointer; run_transaction keeps it
            nserror = nserror_to_dict(objc_instance(error))
            raise TransactionException(
                nserror.description if nserror else "read failed"
            )
        return DocumentSnapshot(snapshot)

    def set_data(
        self,
        data: FirestoreData,
        document_reference: DocumentReference,
        merge: bool = False,
    ) -> Transaction:
        """Write a document, creating it if needed.

        Args:
            data: the fields, as Python values (see ``to_firestore``).
            document_reference: the document to write.
            merge: ``False`` replaces the whole document; ``True`` keeps the
                fields not in ``data``.

        Returns:
            This transaction, for chaining.

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        if merge:
            self._transaction.setData_forDocument_merge_(
                to_firestore(data), document_reference._ref, True
            )
        else:
            self._transaction.setData_forDocument_(
                to_firestore(data), document_reference._ref
            )
        return self

    def update_data(
        self, data: FirestoreData, document_reference: DocumentReference
    ) -> Transaction:
        """Change only the given fields of a document. The document must exist.

        Args:
            data: the fields, as Python values (see ``to_firestore``).
                Dotted names change one nested field.
            document_reference: the document to change.

        Returns:
            This transaction, for chaining.

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        self._transaction.updateData_forDocument_(
            to_firestore(data), document_reference._ref
        )
        return self

    def delete_document(self, document_reference: DocumentReference) -> Transaction:
        """Delete a document.

        Args:
            document_reference: the document to delete.

        Returns:
            This transaction, for chaining.
        """
        self._transaction.deleteDocument_(document_reference._ref)
        return self

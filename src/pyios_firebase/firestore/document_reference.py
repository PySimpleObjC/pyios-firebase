"""``DocumentReference``: points to one document; reads, writes and listens to it."""

from __future__ import annotations

__all__ = ("DocumentReference",)

from collections.abc import Callable, Sequence
from typing import Any

from rubicon.objc import objc_id

from ..types import ErrorCallback, FirestoreData, ObjCObject, ResultCallback
from ..util import (
    error_from_pointer,
    listener_block,
    objc_instance,
    one_shot_block,
    to_firestore,
)
from . import (  # circular: module imports
    collection_reference,
    document_snapshot,
    firestore,
)
from ._write import write_block
from .listener_registration import ListenerRegistration, SnapshotListenOptions


def _snapshot_handler(
    callback: ResultCallback[document_snapshot.DocumentSnapshot],
) -> Callable[[Any, Any], None]:
    """Block body for (FIRDocumentSnapshot, NSError): callback(DocumentSnapshot, error)."""

    def on_snapshot(snapshot_ptr: Any, error_ptr: Any) -> None:
        if not snapshot_ptr:
            callback(None, error_from_pointer(error_ptr))
            return
        callback(document_snapshot.DocumentSnapshot(objc_instance(snapshot_ptr)), None)

    return on_snapshot


class DocumentReference:
    """Points to one document. It holds no data: read it with ``get_document``.

    Data you write is converted with ``to_firestore`` (``datetime``, ``None``,
    nested dicts and lists all work). A value Firestore cannot store raises
    ``TypeError`` before anything is sent.

    You get references from ``Firestore``, ``CollectionReference`` and
    snapshots; you do not make them yourself.

    Args:
        ref: the native ``FIRDocumentReference``.
    """

    def __init__(self, ref: ObjCObject) -> None:
        self._ref = ref

    # ---- properties ----

    @property
    def document_id(self) -> str:
        """The document's ID (the last part of its path)."""
        return str(self._ref.documentID)

    @property
    def path(self) -> str:
        """The full path, for example ``"cities/SF"``."""
        return str(self._ref.path)

    @property
    def parent(self) -> collection_reference.CollectionReference:
        """The collection this document is in."""
        return collection_reference.CollectionReference(self._ref.parent)

    @property
    def firestore(self) -> firestore.Firestore:
        """The ``Firestore`` client."""
        return firestore.Firestore.firestore()

    def collection_with_path(
        self, path: str
    ) -> collection_reference.CollectionReference:
        """A sub collection of this document.

        Args:
            path: the collection's name (``"landmarks"``), or a path below this
                document with an odd number of parts.

        Returns:
            A ``CollectionReference``. Nothing is read yet.
        """
        return collection_reference.CollectionReference(
            self._ref.collectionWithPath_(path)
        )

    # ---- writing ----

    def set_data(
        self,
        data: FirestoreData,
        merge: bool | ErrorCallback = False,
        callback: ErrorCallback | None = None,
    ) -> None:
        """Write the document, creating it if needed.

        Args:
            data: the fields.
            merge: ``False`` replaces the whole document; ``True`` keeps the
                fields not in ``data``. (A callback here is also accepted, for
                the old ``set_data(data, callback)`` form.)
            callback: gets ``None`` once the server has the write, or the error.
        """
        if callable(merge):  # the old set_data(data, callback) form
            callback = merge
            merge = False
        if merge:
            self._ref.setData_merge_completion_(
                to_firestore(data), True, write_block(callback)
            )
        else:
            self._ref.setData_completion_(to_firestore(data), write_block(callback))

    def set_data_merge_fields(
        self,
        data: FirestoreData,
        fields: Sequence[str],
        callback: ErrorCallback | None = None,
    ) -> None:
        """Write only ``fields`` from ``data``, keeping every other field.

        Args:
            data: the fields.
            fields: the field names to write (dotted names for nested fields).
            callback: gets ``None`` or the error.
        """
        self._ref.setData_mergeFields_completion_(
            to_firestore(data), list(fields), write_block(callback)
        )

    def update_data(
        self, data: FirestoreData, callback: ErrorCallback | None = None
    ) -> None:
        """Change only the given fields. The document must exist (use
        ``set_data(..., merge=True)`` to create it if missing).

        Args:
            data: the fields to change. Dotted names (``"address.city"``)
                change one nested field.
            callback: gets ``None`` or the error (``NOT_FOUND`` if the
                document does not exist).
        """
        self._ref.updateData_completion_(to_firestore(data), write_block(callback))

    def delete_document(self, callback: ErrorCallback | None = None) -> None:
        """Delete the document. Its sub collections are NOT deleted.

        Args:
            callback: gets ``None`` or the error. Deleting a missing document
                is not an error.
        """
        self._ref.deleteDocumentWithCompletion_(write_block(callback))

    # ---- reading ----

    def get_document(
        self,
        callback: ResultCallback[document_snapshot.DocumentSnapshot],
        source: int | None = None,
    ) -> None:
        """Read the document once.

        Args:
            callback: gets ``(DocumentSnapshot, None)`` or ``(None, error)``.
                A missing document is not an error: ``snapshot.exists`` is False.
            source: ``FIRFirestoreSource.Default`` (default) / ``Server`` / ``Cache``.
        """
        block = one_shot_block(_snapshot_handler(callback), objc_id, objc_id)
        if source is None:
            self._ref.getDocumentWithCompletion_(block)
        else:
            self._ref.getDocumentWithSource_completion_(source, block)

    def add_snapshot_listener(
        self,
        callback: ResultCallback[document_snapshot.DocumentSnapshot],
        include_metadata_changes: bool = False,
        options: SnapshotListenOptions | None = None,
    ) -> ListenerRegistration:
        """Listen to the document: ``callback`` runs now, then on every change.

        Args:
            callback: gets ``(DocumentSnapshot, None)`` or ``(None, error)``.
                After an error, the listener stops.
            include_metadata_changes: also call back on metadata-only changes.
            options: ``SnapshotListenOptions``; overrides
                ``include_metadata_changes``.

        Returns:
            A ``ListenerRegistration``. Call ``.remove()`` to stop listening.
        """
        block, release = listener_block(_snapshot_handler(callback), objc_id, objc_id)
        if options is not None:
            registration = self._ref.addSnapshotListenerWithOptions_listener_(
                options._options, block
            )
        elif include_metadata_changes:
            registration = (
                self._ref.addSnapshotListenerWithIncludeMetadataChanges_listener_(
                    True, block
                )
            )
        else:
            registration = self._ref.addSnapshotListener_(block)
        return ListenerRegistration(registration, release)

    # ---- comparing ----

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DocumentReference) and bool(
            self._ref.isEqual_(other._ref)
        )

    def __hash__(self) -> int:
        return hash(self.path)

    def __repr__(self) -> str:
        return f"DocumentReference({self.path!r})"

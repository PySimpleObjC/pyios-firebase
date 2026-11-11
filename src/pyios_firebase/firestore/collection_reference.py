"""``CollectionReference``: a collection, and a query over all its documents."""

from __future__ import annotations

__all__ = ("CollectionReference",)

from typing import Any

from rubicon.objc import objc_id

from ..types import FirestoreData, ResultCallback
from ..util import error_from_pointer, one_shot_block, to_firestore
from . import document_reference  # module import: document_reference imports us back
from .query import Query


class CollectionReference(Query):
    """A collection. It is also a ``Query`` for all of its documents."""

    _fresh = True  # a new query: the SDK's checks are mirrored from here

    @property
    def collection_id(self) -> str:
        """The last part of the path. For ``"cities/SF/landmarks"`` it is ``"landmarks"``."""
        return str(self._ref.collectionID)

    @property
    def path(self) -> str:
        """The full path, for example ``"cities"`` or ``"cities/SF/landmarks"``."""
        return str(self._ref.path)

    @property
    def parent(self) -> document_reference.DocumentReference | None:
        """The document that holds this collection, or ``None`` at the top level."""
        parent = self._ref.parent
        return (
            document_reference.DocumentReference(parent) if parent is not None else None
        )

    def document_with_path(self, path: str) -> document_reference.DocumentReference:
        """A document in this collection.

        Args:
            path: the document's ID (``"SF"``), or a path below this collection
                with an odd number of parts (``"SF/landmarks/griffith"``).

        Returns:
            A ``DocumentReference``. Nothing is read yet.
        """
        return document_reference.DocumentReference(self._ref.documentWithPath_(path))

    def document_with_auto_id(self) -> document_reference.DocumentReference:
        """A new ``DocumentReference`` with a generated ID. Nothing is saved yet."""
        return document_reference.DocumentReference(self._ref.documentWithAutoID())

    def add_document_with_data(
        self,
        data: FirestoreData,
        callback: ResultCallback[document_reference.DocumentReference] | None = None,
    ) -> document_reference.DocumentReference:
        """Create a document with a generated ID.

        Args:
            data: the fields (Python values; see ``to_firestore``).
            callback: gets ``(DocumentReference, None)`` once the server has
                the write, or ``(None, error)``.

        Returns:
            The new ``DocumentReference``, right away (before the write ends).

        Raises:
            TypeError: ``data`` holds a value Firestore cannot store.
        """
        holder: dict[str, document_reference.DocumentReference] = {}

        def on_done(error_ptr: Any) -> None:
            if callback is None:
                return
            error = error_from_pointer(error_ptr)
            if error is not None:
                callback(None, error)
            else:
                callback(holder["ref"], None)

        native = self._ref.addDocumentWithData_completion_(
            to_firestore(data), one_shot_block(on_done, objc_id)
        )
        holder["ref"] = document_reference.DocumentReference(native)
        return holder["ref"]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CollectionReference) and bool(
            self._ref.isEqual_(other._ref)
        )

    def __hash__(self) -> int:
        return hash(self.path)

    def __repr__(self) -> str:
        return f"CollectionReference({self.path!r})"

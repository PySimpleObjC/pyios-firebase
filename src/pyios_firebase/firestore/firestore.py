"""``Firestore``: the Cloud Firestore client; entry point for everything else."""

from __future__ import annotations

__all__ = ("Firestore",)

from collections.abc import Callable
from ctypes import POINTER
from typing import Any, ClassVar, TypeVar

from rubicon.objc import objc_id

from ..types import ObjCObject, ResultCallback
from ..util import (
    error_from_pointer,
    listener_block,
    objc_class,
    objc_instance,
    one_shot_block,
)
from . import (
    collection_reference,
    document_reference,
    query,
)  # circular: module imports
from .transaction import Transaction
from .write_batch import WriteBatch

T = TypeVar("T")

TRANSACTION_ERROR_DOMAIN = "PyiOSFirebaseTransaction"
"""The ``error.domain`` when your transaction function raised."""


class Firestore:
    """The app's Cloud Firestore client. Get it with ``Firestore.firestore()``.

    ::

        db = Firestore.firestore()
        db.collection_with_path("cities").document_with_path("LA").set_data({"name": "LA"})

    Args:
        db: the native ``FIRFirestore``. Leave it out: ``Firestore()`` gives the
            same client as ``Firestore.firestore()``.
    """

    _instance: ClassVar[Firestore | None] = None

    def __init__(self, db: ObjCObject | None = None) -> None:
        # Firestore() still works and gives the same client as Firestore.firestore()
        self._db = db if db is not None else objc_class("FIRFirestore").firestore()

    @classmethod
    def firestore(cls) -> Firestore:
        """The shared client for the default Firebase app."""
        if cls._instance is None:
            cls._instance = cls(objc_class("FIRFirestore").firestore())
        return cls._instance

    def use_emulator(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Send this client's reads and writes to the local Firestore emulator.

        Points the client at ``host:port`` and turns TLS off, since the
        emulator speaks plain HTTP/2. Call it once, right after
        ``core.configure()`` and before any other use of Firestore (the SDK
        fixes its settings on first use). Use it only in development and test
        builds.

        ::

            core.configure()
            Firestore.firestore().use_emulator("127.0.0.1", 8080)

        Args:
            host: the emulator's host. ``"127.0.0.1"`` works in the iOS
                Simulator, which shares the Mac's network; on a device, use the
                Mac's LAN address and start the emulator with ``"host": "0.0.0.0"``.
            port: the emulator's port (``firebase emulators:start`` uses 8080).
        """
        self._db.useEmulatorWithHost_port_(host, int(port))
        # the SDK only changes the host: the emulator speaks plain HTTP/2, so
        # TLS must be turned off too (as Firebase's Apple guide says)
        settings = self._db.settings.copy()
        settings.sslEnabled = False
        self._db.settings = settings

    def batch(self) -> WriteBatch:
        """A new ``WriteBatch``."""
        return WriteBatch(self._db.batch())  # a method in ObjC: must be called

    def collection_with_path(
        self, path: str
    ) -> collection_reference.CollectionReference:
        """A collection, by path.

        Args:
            path: a slash-separated path with an odd number of parts, for example
                ``"cities"`` or ``"cities/SF/landmarks"``.

        Returns:
            A ``CollectionReference``. Nothing is read yet.
        """
        return collection_reference.CollectionReference(
            self._db.collectionWithPath_(path)
        )

    def collection_group_with_id(self, collection_id: str) -> query.Query:
        """Every collection named ``collection_id``, wherever it is in the database.

        Collection group queries often need an index; the error message has a
        link that creates it.

        Args:
            collection_id: the collection's name only (``"landmarks"``), not a
                path. It must not contain ``/``.

        Returns:
            A ``Query`` over all the documents of those collections.
        """
        return query.Query(self._db.collectionGroupWithID_(collection_id))

    def document_with_path(self, path: str) -> document_reference.DocumentReference:
        """A document, by its full path.

        Args:
            path: a slash-separated path with an even number of parts, for
                example ``"cities/LA"`` or ``"cities/LA/landmarks/griffith"``.

        Returns:
            A ``DocumentReference``. Nothing is read yet.
        """
        return document_reference.DocumentReference(self._db.documentWithPath_(path))

    def run_transaction(
        self,
        update_fn: Callable[[Transaction], T],
        callback: ResultCallback[T] | None = None,
    ) -> None:
        """Read and write documents atomically.

        ``update_fn(transaction)`` may run more than once (when the data it
        read changed before the commit), so it must only read and write
        through ``transaction``: no other side effects.

        Args:
            update_fn: reads with ``transaction.get_document`` first, then
                writes. Raise an exception to stop the transaction. What it
                returns (any Python value) is given to ``callback``.
            callback: gets ``(result, None)`` after the commit, or
                ``(None, error)``.
        """
        holder: dict[str, Any] = {}  # the Python result stays here, not in ObjC

        def on_update(transaction_ptr: Any, error_pointer: Any) -> None:
            transaction = Transaction(objc_instance(transaction_ptr), error_pointer)
            holder.pop("result", None)
            try:
                holder["result"] = update_fn(transaction)
            except Exception as e:  # noqa: BLE001 - every failure must reach Firestore
                if error_pointer[0].value is None:  # keep Firestore's own error
                    error = objc_class("NSError").errorWithDomain_code_userInfo_(
                        TRANSACTION_ERROR_DOMAIN, -1, {"NSLocalizedDescription": str(e)}
                    )
                    error_pointer[0] = error.ptr

        def on_done(_result_ptr: Any, error_ptr: Any) -> None:
            release_update()
            if callback is None:
                return
            error = error_from_pointer(error_ptr)
            if error is not None:
                callback(None, error)
            else:
                callback(holder.get("result"), None)

        # the update block can run many times: it lives until on_done
        update_block, release_update = listener_block(
            on_update, objc_id, POINTER(objc_id), restype=objc_id
        )
        done_block = one_shot_block(on_done, objc_id, objc_id)
        self._db.runTransactionWithBlock_completion_(update_block, done_block)

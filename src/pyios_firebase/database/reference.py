"""``DatabaseReference``: a location in the database, and writes to it."""

from __future__ import annotations

__all__ = (
    "TRANSACTION_ERROR_DOMAIN",
    "DatabaseReference",
    "OnDisconnect",
    "TransactionCallback",
    "TransactionResult",
    "WriteCallback",
)

from collections.abc import Callable, Mapping
from ctypes import c_bool
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import unquote, urlsplit

from rubicon.objc import ObjCInstance, objc_id

from ..types import ObjCObject
from ..util import listener_block, objc_class, objc_instance, one_shot_block
from .errors import DatabaseError, database_error, database_error_from_pointer
from .query import DatabaseQuery, _Spec
from .snapshot import DataSnapshot, MutableData
from .values import to_database, to_priority, validate_path

if TYPE_CHECKING:
    from .database import Database

WriteCallback = Callable[[DatabaseError | None], None]
"""``(error)``: ``None`` once the server has the write, or the error."""

TransactionCallback = Callable[[DatabaseError | None, bool, DataSnapshot | None], None]
"""``(error, committed, snapshot)``. ``committed`` is ``False`` when the
transaction was aborted (or failed); ``snapshot`` is the data after it."""

TRANSACTION_ERROR_DOMAIN: Final = "pyios_firebase.database.transaction"
"""The ``error.domain`` when the Python transaction function raised."""


def _write_block(callback: WriteCallback | None) -> Any:
    def done(error_ptr: Any, _ref_ptr: Any) -> None:
        if callback is not None:
            callback(database_error_from_pointer(error_ptr))

    return one_shot_block(done, objc_id, objc_id)


def _child_values(values: Mapping[str, Any]) -> Any:
    """``update_child_values`` data: keys are paths."""
    if not isinstance(values, Mapping):
        raise TypeError(
            f"update_child_values takes a dict, not {type(values).__name__}"
        )
    checked: dict[str, Any] = {}
    for path, value in values.items():
        validate_path(path, "update path")
        checked[path] = value
    # the SDK aborts the app when one path is at or below another
    parts = sorted(tuple(part for part in path.split("/") if part) for path in checked)
    for previous, current in pairwise(parts):
        if current[: len(previous)] == previous:
            raise ValueError(
                f"update path {'/'.join(current)!r} is at or below "
                f"{'/'.join(previous) or '/'!r}: write it inside that value instead"
            )
    native = objc_class("NSMutableDictionary").dictionary()
    for path, value in checked.items():
        native.setObject_forKey_(to_database(value), path)
    return native


class TransactionResult:
    """What a transaction function returns: ``success`` (write the data) or
    ``abort`` (write nothing).

    Args:
        native: the native ``FIRTransactionResult``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRTransactionResult``."""
        return self._native

    @classmethod
    def success(cls, data: MutableData) -> TransactionResult:
        """Write ``data`` (the ``MutableData`` the function got, changed).

        Args:
            data: the new data.
        """
        return cls(objc_class("FIRTransactionResult").successWithValue_(data.native))

    @classmethod
    def abort(cls) -> TransactionResult:
        """Write nothing. The callback gets ``committed=False``."""
        return cls(objc_class("FIRTransactionResult").abort())


class OnDisconnect:
    """Writes the server makes when this client disconnects (closes the app,
    loses the network...). Get it with ``ref.on_disconnect()``.

    The writes are queued on the server now, and run even if the app is
    killed. The callbacks say when the server has queued them.

    Args:
        ref: the native ``FIRDatabaseReference``.
    """

    def __init__(self, ref: ObjCObject) -> None:
        self._ref = ref

    def set_value(
        self,
        value: Any,
        callback: WriteCallback | None = None,
        *,
        priority: Any = None,
    ) -> None:
        """Write ``value`` on disconnect.

        Args:
            value: as for ``DatabaseReference.set_value``.
            callback: gets ``(error)`` once the server has queued the write.
            priority: also set this priority (``None``: leave it).
        """
        native = to_database(value)
        if priority is None:
            self._ref.onDisconnectSetValue_withCompletionBlock_(
                native, _write_block(callback)
            )
        else:
            self._ref.onDisconnectSetValue_andPriority_withCompletionBlock_(
                native, to_priority(priority), _write_block(callback)
            )

    def update_child_values(
        self, values: Mapping[str, Any], callback: WriteCallback | None = None
    ) -> None:
        """Update children on disconnect.

        Args:
            values: as for ``DatabaseReference.update_child_values``.
            callback: gets ``(error)`` once the server has queued the write.
        """
        self._ref.onDisconnectUpdateChildValues_withCompletionBlock_(
            _child_values(values), _write_block(callback)
        )

    def remove_value(self, callback: WriteCallback | None = None) -> None:
        """Delete the data on disconnect.

        Args:
            callback: gets ``(error)`` once the server has queued the delete.
        """
        self._ref.onDisconnectRemoveValueWithCompletionBlock_(_write_block(callback))

    def cancel(self, callback: WriteCallback | None = None) -> None:
        """Cancel the disconnect writes queued at this location (and below).

        Args:
            callback: gets ``(error)`` once the server has cancelled them.
        """
        self._ref.cancelDisconnectOperationsWithCompletionBlock_(_write_block(callback))


class DatabaseReference(DatabaseQuery):
    """A location in the database. Read and listen with the query methods, and
    write with ``set_value``, ``update_child_values``... Nothing happens until
    you call a method.

    Writes show in local listeners at once, and work offline: the SDK sends
    them when it is back online. The callbacks run when the server has them.

    Args:
        native: the native ``FIRDatabaseReference``.
    """

    def __init__(self, native: ObjCObject, _spec: _Spec | None = None) -> None:
        super().__init__(native, _spec)

    # ---- where it points -----------------------------------------------------------

    @property
    def key(self) -> str | None:
        """The last part of the path (``None`` for the root)."""
        key = self._native.key
        return None if key is None else str(key)

    @property
    def url(self) -> str:
        """The full URL of the location."""
        return str(self._native.URL)

    @property
    def path(self) -> str:
        """The path from the root, for example ``"/users/ada"`` (``"/"`` for
        the root)."""
        return unquote(urlsplit(self.url).path) or "/"

    @property
    def database(self) -> Database:
        """The ``Database`` this reference belongs to."""
        from .database import Database

        return Database(self._native.database)

    @property
    def parent(self) -> DatabaseReference | None:
        """The location above this one, or ``None`` at the root."""
        parent = self._native.parent
        return None if parent is None else DatabaseReference(parent)

    @property
    def root(self) -> DatabaseReference:
        """The root of the database."""
        return DatabaseReference(self._native.root)

    def child(self, path: str) -> DatabaseReference:
        """A location below this one.

        Args:
            path: a relative path, for example ``"ada"`` or ``"ada/scores"``.

        Returns:
            A new ``DatabaseReference``.

        Raises:
            ValueError: the path is empty or holds ``. # $ [ ]``.
        """
        validate_path(path)
        return DatabaseReference(self._native.child_(path))

    def child_by_auto_id(self) -> DatabaseReference:
        """A new child with a unique key that sorts by creation time (like
        ``push()`` in other SDKs). Nothing is written until you write to it."""
        return DatabaseReference(self._native.childByAutoId())

    def on_disconnect(self) -> OnDisconnect:
        """Writes to make at this location when this client disconnects."""
        return OnDisconnect(self._native)

    # ---- writes --------------------------------------------------------------------

    def _check_writable(self) -> None:
        if self.path.lstrip("/").split("/")[0] == ".info":
            raise ValueError("cannot write under .info (it is read-only)")

    def set_value(
        self,
        value: Any,
        callback: WriteCallback | None = None,
        *,
        priority: Any = None,
    ) -> None:
        """Replace the data at this location (and everything below it).

        Args:
            value: ``None`` (delete), ``bool``, ``int``, ``float``, ``str``, a
                ``ServerValue``, or a dict (``str`` keys), list or tuple of
                those.
            callback: gets ``(error)`` once the server has the write.
            priority: also set this priority (a number or ``str``).

        Raises:
            TypeError: a value the database cannot store (``datetime``,
                ``bytes``...).
            ValueError: an invalid key or value, or a location under ``.info``.
        """
        self._check_writable()
        native = to_database(value)
        if priority is None:
            self._native.setValue_withCompletionBlock_(native, _write_block(callback))
        else:
            self._native.setValue_andPriority_withCompletionBlock_(
                native, to_priority(priority), _write_block(callback)
            )

    def update_child_values(
        self, values: Mapping[str, Any], callback: WriteCallback | None = None
    ) -> None:
        """Write some children, leaving the others. Keys can be paths, to write
        to several locations at once (atomically)::

            root.update_child_values({
                f"posts/{key}": post,
                f"user-posts/{uid}/{key}": post,
            })

        Args:
            values: paths (relative to here) to values. ``None`` deletes.
            callback: gets ``(error)`` once the server has the write.

        Raises:
            TypeError: a value the database cannot store.
            ValueError: an invalid path or value, a path at or below another
                one, or a location under ``.info``.
        """
        self._check_writable()
        self._native.updateChildValues_withCompletionBlock_(
            _child_values(values), _write_block(callback)
        )

    def remove_value(self, callback: WriteCallback | None = None) -> None:
        """Delete the data at this location (and everything below it).

        Args:
            callback: gets ``(error)`` once the server has the delete.

        Raises:
            ValueError: a location under ``.info``.
        """
        self._check_writable()
        self._native.removeValueWithCompletionBlock_(_write_block(callback))

    def set_priority(
        self, priority: str | float | None, callback: WriteCallback | None = None
    ) -> None:
        """Set the priority of the data here (used by ``order_by_priority``).

        Args:
            priority: a number, a ``str``, or ``None`` to remove it.
            callback: gets ``(error)`` once the server has the write.

        Raises:
            TypeError: another type (``bool`` too).
            ValueError: a location under ``.info``.
        """
        self._check_writable()
        self._native.setPriority_withCompletionBlock_(
            to_priority(priority), _write_block(callback)
        )

    def run_transaction(
        self,
        update: Callable[[MutableData], TransactionResult],
        callback: TransactionCallback | None = None,
        *,
        local_events: bool = True,
    ) -> None:
        """Change the data atomically, from its current value::

            def add_like(data):
                data.value = (data.value or 0) + 1
                return TransactionResult.success(data)

            ref.child("likes").run_transaction(add_like)

        ``update`` may run several times (on a background thread): whenever
        another client changed the data first, it runs again with the new
        data. It must not have side effects.

        Args:
            update: gets the current ``MutableData`` and returns
                ``TransactionResult.success(data)`` or
                ``TransactionResult.abort()``. If it raises, the transaction is
                aborted and ``callback`` gets the error.
            callback: gets ``(error, committed, snapshot)`` at the end.
            local_events: show the intermediate values in local listeners.
                ``False`` shows only the committed value.

        Raises:
            ValueError: a location under ``.info``.
        """
        self._check_writable()
        state: dict[str, Any] = {}

        def on_update(data_ptr: Any) -> Any:
            state.pop("error", None)
            try:
                result = update(MutableData(objc_instance(data_ptr)))
                if not isinstance(result, TransactionResult):
                    raise TypeError(
                        "the transaction function must return "
                        "TransactionResult.success(data) or TransactionResult.abort(), "
                        f"not {type(result).__name__}"
                    )
            except Exception as e:  # noqa: BLE001 - the SDK must always get a result
                state["error"] = e
                result = TransactionResult.abort()
            state["result"] = result  # alive until the SDK has taken it
            native: ObjCInstance = result.native
            return native.ptr.value

        def on_done(error_ptr: Any, committed: Any, snapshot_ptr: Any) -> None:
            release_update()
            if callback is None:
                return
            error = database_error_from_pointer(error_ptr)
            raised = state.get("error")
            if error is None and raised is not None:
                error = database_error(
                    objc_class("NSError").errorWithDomain_code_userInfo_(
                        TRANSACTION_ERROR_DOMAIN,
                        -1,
                        {
                            "NSLocalizedDescription": f"{type(raised).__name__}: {raised}"
                        },
                    )
                )
            snapshot = (
                DataSnapshot(objc_instance(snapshot_ptr)) if snapshot_ptr else None
            )
            callback(error, bool(committed), snapshot)

        update_block, release_update = listener_block(
            on_update, objc_id, restype=objc_id
        )
        done_block = one_shot_block(on_done, objc_id, c_bool, objc_id)
        self._native.runTransactionBlock_andCompletionBlock_withLocalEvents_(
            update_block, done_block, bool(local_events)
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DatabaseReference) and self.url == other.url

    def __hash__(self) -> int:
        return hash(self.url)

    def __repr__(self) -> str:
        return f"DatabaseReference({self.url!r})"

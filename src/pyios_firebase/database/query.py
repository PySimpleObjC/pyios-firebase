"""``DatabaseQuery``: sorting, filtering and listening to data."""

from __future__ import annotations

__all__ = (
    "DataEventType",
    "DatabaseObserver",
    "DatabaseQuery",
    "EventCallback",
)

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Final

from rubicon.objc import objc_id

from ..types import ObjCObject
from ..util import listener_block, objc_instance, one_shot_block
from .errors import DatabaseError, database_error_from_pointer
from .snapshot import DataSnapshot
from .values import to_query_value, validate_key, validate_path

if TYPE_CHECKING:
    from .reference import DatabaseReference


class DataEventType:
    """What to listen to (``FIRDataEventType``)."""

    CHILD_ADDED: Final = 0
    """A child was added (and once for each existing child, at the start)."""
    CHILD_REMOVED: Final = 1
    """A child was removed."""
    CHILD_CHANGED: Final = 2
    """A child (or anything below it) changed."""
    CHILD_MOVED: Final = 3
    """A child moved in the query's order."""
    VALUE: Final = 4
    """The data at the location (or anything below it) changed. Called once
    with the current data at the start."""


_EVENT_TYPES: Final = frozenset(range(5))

EventCallback = Callable[[DataSnapshot, "str | None"], None]
"""``(snapshot, previous_child_key)``. For child events, ``previous_child_key``
is the key of the child before this one in the query's order (``None`` for the
first); for ``VALUE`` it is ``None``."""

CancelCallback = Callable[[DatabaseError], None]


def _check_event(event_type: int) -> None:
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"unknown event type {event_type!r}: use DataEventType")


class DatabaseObserver:
    """Given back by ``observe``. Call ``remove()`` to stop listening.

    Args:
        query: the native query the observer was added to.
        handle: the SDK's handle for the observer.
        release: releases the observer's blocks.
    """

    def __init__(
        self, query: ObjCObject, handle: int, release: Callable[[], None]
    ) -> None:
        self._query: ObjCObject | None = query
        self._handle = handle
        self._release = release

    @property
    def handle(self) -> int:
        """The SDK's ``FIRDatabaseHandle``."""
        return self._handle

    def remove(self) -> None:
        """Stop the updates. Safe to call more than once."""
        if self._query is None:
            return
        self._query.removeObserverWithHandle_(self._handle)
        self._query = None
        self._release()


class _Spec:
    """What the query asked for, mirrored in Python: the SDK raises an
    Objective-C exception (aborting the app) on a misuse, so we check first."""

    def __init__(self) -> None:
        self.order: str | None = None  # "child:<path>", "key", "value", "priority"
        self.start: tuple[Any, ...] | None = None
        self.end: tuple[Any, ...] | None = None
        self.limit: tuple[str, int] | None = None

    def copy(self, **changes: Any) -> _Spec:
        spec = _Spec()
        spec.__dict__.update(self.__dict__)
        spec.__dict__.update(changes)
        return spec

    def key(self) -> tuple[Any, ...]:
        return (self.order, self.start, self.end, self.limit)


class DatabaseQuery:
    """A sorted and filtered view of the data at a location. Every method that
    narrows the query returns a new query; nothing is read until you
    ``observe`` or ``get_data``.

    ::

        top = ref.child("scores").order_by_value().limit_to_last(10)
        observer = top.observe(DataEventType.CHILD_ADDED, on_score)

    Each query can be ordered once, and have one start, one end and one limit.

    Args:
        native: the native ``FIRDatabaseQuery`` (or ``FIRDatabaseReference``).
    """

    # the observers' release functions, by (location URL, query spec): the SDK
    # removes all of them on remove_all_observers
    _observers: ClassVar[dict[tuple[Any, ...], dict[int, Callable[[], None]]]] = {}

    def __init__(self, native: ObjCObject, _spec: _Spec | None = None) -> None:
        self._native = native
        self._spec = _spec or _Spec()

    @property
    def native(self) -> ObjCObject:
        """The ``FIRDatabaseQuery``."""
        return self._native

    @property
    def ref(self) -> DatabaseReference:
        """The location this query reads from."""
        from .reference import DatabaseReference

        return DatabaseReference(self._native.ref)

    def _query(self, native: ObjCObject, spec: _Spec) -> DatabaseQuery:
        return DatabaseQuery(native, spec)

    # ---- ordering ------------------------------------------------------------------

    def _check_order(self) -> None:
        if self._spec.order is not None:
            raise ValueError("a query can be ordered only once")

    def _check_endpoints(self, spec: _Spec) -> None:
        for point in (spec.start, spec.end):
            if point is None:
                continue
            _kind, value, child_key = point
            if spec.order == "key":
                if child_key is not None:
                    raise ValueError("with order_by_key, do not pass a child key")
                to_query_value(value, strings_only=True, priority=False)
            elif spec.order == "priority":
                to_query_value(value, strings_only=False, priority=True)

    def order_by_child(self, path: str) -> DatabaseQuery:
        """Sort by the value of a child of each child.

        Args:
            path: the child's path in each child, for example ``"age"`` or
                ``"stats/score"``.

        Returns:
            The new query.

        Raises:
            ValueError: the query is already ordered, or ``path`` is invalid
                (``"$key"`` / ``"$value"`` / ``"$priority"``: use
                ``order_by_key`` / ``order_by_value`` / ``order_by_priority``).
        """
        for special, method in (
            ("key", "order_by_key"),
            ("priority", "order_by_priority"),
            ("value", "order_by_value"),
        ):
            if path in (f"${special}", f".{special}"):
                raise ValueError(f"order_by_child({path!r}) is invalid: use {method}()")
        self._check_order()
        validate_path(path)
        if not path.strip("/"):
            raise ValueError("order_by_child needs a path: use order_by_value()")
        spec = self._spec.copy(order=f"child:{path}")
        self._check_endpoints(spec)
        return self._query(self._native.queryOrderedByChild_(path), spec)

    def order_by_key(self) -> DatabaseQuery:
        """Sort by the children's keys.

        Raises:
            ValueError: the query is already ordered, or has a non-``str``
                start or end value or a child key.
            TypeError: a start or end value is not a ``str``.
        """
        self._check_order()
        spec = self._spec.copy(order="key")
        self._check_endpoints(spec)
        return self._query(self._native.queryOrderedByKey(), spec)

    def order_by_value(self) -> DatabaseQuery:
        """Sort by the children's values.

        Raises:
            ValueError: the query is already ordered.
        """
        self._check_order()
        spec = self._spec.copy(order="value")
        return self._query(self._native.queryOrderedByValue(), spec)

    def order_by_priority(self) -> DatabaseQuery:
        """Sort by the children's priorities.

        Raises:
            ValueError: the query is already ordered.
            TypeError: a start or end value is a ``bool``.
        """
        self._check_order()
        spec = self._spec.copy(order="priority")
        self._check_endpoints(spec)
        return self._query(self._native.queryOrderedByPriority(), spec)

    # ---- filtering -----------------------------------------------------------------

    def _value(self, value: Any) -> Any:
        return to_query_value(
            value,
            strings_only=self._spec.order == "key",
            priority=self._spec.order == "priority",
        )

    def _child_key(self, child_key: str | None) -> None:
        if child_key is None:
            return
        if self._spec.order == "key":
            raise ValueError("with order_by_key, do not pass a child key")
        validate_key(child_key, "child key")

    def _start(
        self, kind: str, value: Any, child_key: str | None, selector: str
    ) -> DatabaseQuery:
        if self._spec.start is not None:
            raise ValueError(f"{kind}: the query already has a start (or equal_to)")
        native_value = self._value(value)
        self._child_key(child_key)
        spec = self._spec.copy(start=(kind, value, child_key))
        if child_key is None:
            native = getattr(self._native, f"{selector}_")(native_value)
        else:
            native = getattr(self._native, f"{selector}_childKey_")(
                native_value, child_key
            )
        return self._query(native, spec)

    def _end(
        self, kind: str, value: Any, child_key: str | None, selector: str
    ) -> DatabaseQuery:
        if self._spec.end is not None:
            raise ValueError(f"{kind}: the query already has an end (or equal_to)")
        native_value = self._value(value)
        self._child_key(child_key)
        spec = self._spec.copy(end=(kind, value, child_key))
        if child_key is None:
            native = getattr(self._native, f"{selector}_")(native_value)
        else:
            native = getattr(self._native, f"{selector}_childKey_")(
                native_value, child_key
            )
        return self._query(native, spec)

    def start_at(self, value: Any, child_key: str | None = None) -> DatabaseQuery:
        """Only children at or after ``value`` in the query's order.

        Args:
            value: ``None``, ``bool``, a number or a ``str`` (a ``str`` key
                with ``order_by_key``).
            child_key: among children with exactly ``value``, start at this
                key. Not with ``order_by_key``.

        Returns:
            The new query.

        Raises:
            ValueError: the query already has a start, or a bad ``child_key``.
            TypeError: a ``value`` type the query cannot use.
        """
        return self._start("start_at", value, child_key, "queryStartingAtValue")

    def start_after(self, value: Any, child_key: str | None = None) -> DatabaseQuery:
        """Only children after ``value`` (excluded) in the query's order.

        Args:
            value: as for ``start_at``.
            child_key: among children with exactly ``value``, start after this key.

        Returns:
            The new query.

        Raises:
            ValueError: the query already has a start, or a bad ``child_key``.
            TypeError: a ``value`` type the query cannot use.
        """
        return self._start("start_after", value, child_key, "queryStartingAfterValue")

    def end_at(self, value: Any, child_key: str | None = None) -> DatabaseQuery:
        """Only children at or before ``value`` in the query's order.

        Args:
            value: as for ``start_at``.
            child_key: among children with exactly ``value``, end at this key.

        Returns:
            The new query.

        Raises:
            ValueError: the query already has an end, or a bad ``child_key``.
            TypeError: a ``value`` type the query cannot use.
        """
        return self._end("end_at", value, child_key, "queryEndingAtValue")

    def end_before(self, value: Any, child_key: str | None = None) -> DatabaseQuery:
        """Only children before ``value`` (excluded) in the query's order.

        Args:
            value: as for ``start_at``.
            child_key: among children with exactly ``value``, end before this key.

        Returns:
            The new query.

        Raises:
            ValueError: the query already has an end, or a bad ``child_key``.
            TypeError: a ``value`` type the query cannot use.
        """
        return self._end("end_before", value, child_key, "queryEndingBeforeValue")

    def equal_to(self, value: Any, child_key: str | None = None) -> DatabaseQuery:
        """Only children equal to ``value`` in the query's order.

        Args:
            value: as for ``start_at``.
            child_key: only the child with this key (among those equal to ``value``).

        Returns:
            The new query.

        Raises:
            ValueError: the query already has a start or an end, or a bad
                ``child_key``.
            TypeError: a ``value`` type the query cannot use.
        """
        if self._spec.start is not None or self._spec.end is not None:
            raise ValueError("equal_to: the query already has a start or an end")
        native_value = self._value(value)
        self._child_key(child_key)
        point = ("equal_to", value, child_key)
        spec = self._spec.copy(start=point, end=point)
        if child_key is None:
            native = self._native.queryEqualToValue_(native_value)
        else:
            native = self._native.queryEqualToValue_childKey_(native_value, child_key)
        return self._query(native, spec)

    def _limit(self, kind: str, limit: int) -> _Spec:
        if self._spec.limit is not None:
            raise ValueError(f"{kind}: the query already has a limit")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError(f"{kind} takes an int, not {type(limit).__name__}")
        if not 0 < limit < 2**31:
            raise ValueError(f"{kind}: the limit must be 1 to 2,147,483,647")
        return self._spec.copy(limit=(kind, limit))

    def limit_to_first(self, limit: int) -> DatabaseQuery:
        """Only the first ``limit`` children in the query's order.

        Args:
            limit: how many (1 to 2,147,483,647).

        Returns:
            The new query.

        Raises:
            ValueError: the query already has a limit, or ``limit`` is out of range.
        """
        spec = self._limit("limit_to_first", limit)
        return self._query(self._native.queryLimitedToFirst_(limit), spec)

    def limit_to_last(self, limit: int) -> DatabaseQuery:
        """Only the last ``limit`` children in the query's order.

        Args:
            limit: how many (1 to 2,147,483,647).

        Returns:
            The new query.

        Raises:
            ValueError: the query already has a limit, or ``limit`` is out of range.
        """
        spec = self._limit("limit_to_last", limit)
        return self._query(self._native.queryLimitedToLast_(limit), spec)

    # ---- reading -------------------------------------------------------------------

    def _observers_key(self) -> tuple[Any, ...]:
        return (str(self._native.ref.URL), self._spec.key())

    def observe(
        self,
        event_type: int,
        callback: EventCallback,
        cancel_callback: CancelCallback | None = None,
    ) -> DatabaseObserver:
        """Listen to changes. ``callback`` runs on the main thread, at the start
        and on every change, until you ``remove()`` the observer.

        Args:
            event_type: a ``DataEventType``.
            callback: gets ``(snapshot, previous_child_key)``.
            cancel_callback: gets a ``DatabaseError`` if the server stops the
                listener (for example ``PERMISSION_DENIED``). The observer is
                then already removed.

        Returns:
            A ``DatabaseObserver``.

        Raises:
            ValueError: an unknown ``event_type``.
        """
        _check_event(event_type)
        releases: list[Callable[[], None]] = []
        key = self._observers_key()
        holder: dict[str, int] = {}

        def release() -> None:
            self._observers.get(key, {}).pop(holder.get("handle", -1), None)
            for release_block in releases:
                release_block()

        def on_event(snapshot_ptr: Any, previous_ptr: Any = None) -> None:
            previous = str(objc_instance(previous_ptr)) if previous_ptr else None
            callback(DataSnapshot(objc_instance(snapshot_ptr)), previous)

        def on_cancel(error_ptr: Any) -> None:
            release()
            if cancel_callback is not None:
                error = database_error_from_pointer(error_ptr)
                assert error is not None
                cancel_callback(error)

        cancel_block, release_cancel = listener_block(on_cancel, objc_id)
        releases.append(release_cancel)
        if event_type == DataEventType.VALUE:
            block, release_event = listener_block(on_event, objc_id)
            releases.append(release_event)
            handle = self._native.observeEventType_withBlock_withCancelBlock_(
                event_type, block, cancel_block
            )
        else:
            block, release_event = listener_block(on_event, objc_id, objc_id)
            releases.append(release_event)
            handle = self._native.observeEventType_andPreviousSiblingKeyWithBlock_withCancelBlock_(
                event_type, block, cancel_block
            )
        holder["handle"] = int(handle)
        self._observers.setdefault(key, {})[int(handle)] = release
        return DatabaseObserver(self._native, int(handle), release)

    def observe_once(
        self,
        event_type: int,
        callback: EventCallback,
        cancel_callback: CancelCallback | None = None,
    ) -> None:
        """Get the next event once (for ``VALUE``: the data now, from the cache
        if the SDK has it).

        Prefer ``get_data`` to read fresh data from the server.

        Args:
            event_type: a ``DataEventType``.
            callback: gets ``(snapshot, previous_child_key)``, once.
            cancel_callback: gets a ``DatabaseError`` instead, if the read is
                not allowed.

        Raises:
            ValueError: an unknown ``event_type``.
        """
        _check_event(event_type)
        releases: list[Callable[[], None]] = []

        def release() -> None:
            for release_block in releases:
                release_block()

        def on_event(snapshot_ptr: Any, previous_ptr: Any = None) -> None:
            release()
            previous = str(objc_instance(previous_ptr)) if previous_ptr else None
            callback(DataSnapshot(objc_instance(snapshot_ptr)), previous)

        def on_cancel(error_ptr: Any) -> None:
            release()
            if cancel_callback is not None:
                error = database_error_from_pointer(error_ptr)
                assert error is not None
                cancel_callback(error)

        cancel_block, release_cancel = listener_block(on_cancel, objc_id)
        releases.append(release_cancel)
        if event_type == DataEventType.VALUE:
            block, release_event = listener_block(on_event, objc_id)
            releases.append(release_event)
            self._native.observeSingleEventOfType_withBlock_withCancelBlock_(
                event_type, block, cancel_block
            )
        else:
            block, release_event = listener_block(on_event, objc_id, objc_id)
            releases.append(release_event)
            self._native.observeSingleEventOfType_andPreviousSiblingKeyWithBlock_withCancelBlock_(
                event_type, block, cancel_block
            )

    def get_data(
        self, callback: Callable[[DataSnapshot | None, DatabaseError | None], None]
    ) -> None:
        """Read the data from the server (or from the cache when offline and
        the SDK has it).

        Args:
            callback: gets ``(snapshot, None)``, or ``(None, error)`` (for
                example when offline with nothing cached).
        """

        def done(error_ptr: Any, snapshot_ptr: Any) -> None:
            error = database_error_from_pointer(error_ptr)
            if error is not None or not snapshot_ptr:
                callback(None, error)
                return
            callback(DataSnapshot(objc_instance(snapshot_ptr)), None)

        self._native.getDataWithCompletionBlock_(one_shot_block(done, objc_id, objc_id))

    def remove_all_observers(self) -> None:
        """Remove every observer of this query (and, on a reference, of the
        location without filters). Observers of child locations stay."""
        self._native.removeAllObservers()
        for release in list(self._observers.pop(self._observers_key(), {}).values()):
            release()

    def keep_synced(self, keep_synced: bool) -> None:
        """Keep this query's data in the cache and up to date, even without
        observers (useful with persistence, for offline use).

        Args:
            keep_synced: ``True`` to start, ``False`` to stop.

        Raises:
            ValueError: the query is on ``.info``.
        """
        if "/.info" in str(self._native.ref.URL).split("?")[0]:
            raise ValueError("cannot keep .info synced (it is always local)")
        self._native.keepSynced_(bool(keep_synced))

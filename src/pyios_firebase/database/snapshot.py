"""``DataSnapshot`` (data read from the database) and ``MutableData`` (data in
a transaction)."""

from __future__ import annotations

__all__ = ("DataSnapshot", "MutableData")

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from ..types import ObjCObject
from ..util import to_python
from .values import to_database, to_priority, validate_path

if TYPE_CHECKING:
    from .reference import DatabaseReference


def _children(enumerator: ObjCObject) -> Iterator[ObjCObject]:
    while True:
        child = enumerator.nextObject()
        if child is None:
            return
        yield child


class DataSnapshot:
    """The data at a location, at the time it was read. It does not change.

    ``value`` is the data as Python values. Iterating a snapshot gives its
    children, in the query's order::

        for child in snapshot:
            print(child.key, child.value)

    Args:
        native: the native ``FIRDataSnapshot``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRDataSnapshot``."""
        return self._native

    @property
    def key(self) -> str | None:
        """The last part of the location's path (``None`` for the root)."""
        key = self._native.key
        return None if key is None else str(key)

    @property
    def value(self) -> Any:
        """The data, as Python values: ``dict``, ``list``, ``str``, ``int``,
        ``float``, ``bool``, or ``None`` when there is no data.

        Objects whose keys are ``"0"``, ``"1"``... (mostly) come back as a
        ``list``, as the SDK reads them.
        """
        return to_python(self._native.value)

    @property
    def priority(self) -> str | float | None:
        """The priority of the data, or ``None``."""
        priority: str | float | None = to_python(self._native.priority)
        return priority

    def export_value(self) -> Any:
        """The data with priorities included (``".value"`` / ``".priority"``
        keys), as Python values. Write it back with ``set_value`` to copy the
        data with its priorities.
        """
        return to_python(self._native.valueInExportFormat())

    @property
    def ref(self) -> DatabaseReference:
        """The location this data was read from."""
        from .reference import DatabaseReference

        return DatabaseReference(self._native.ref)

    def exists(self) -> bool:
        """``True`` if there is data (``value`` is not ``None``)."""
        return bool(self._native.exists())

    def child(self, path: str) -> DataSnapshot:
        """The data at a path below this one (an empty snapshot if none).

        Args:
            path: a relative path, for example ``"name"`` or ``"address/city"``.

        Raises:
            ValueError: an invalid path.
        """
        validate_path(path)
        return DataSnapshot(self._native.childSnapshotForPath_(path))

    def has_child(self, path: str) -> bool:
        """``True`` if there is data at a path below this one.

        Args:
            path: a relative path.

        Raises:
            ValueError: an invalid path.
        """
        validate_path(path)
        return bool(self._native.hasChild_(path))

    def has_children(self) -> bool:
        """``True`` if the data has children (it is an object, not a leaf)."""
        return bool(self._native.hasChildren())

    @property
    def children_count(self) -> int:
        """How many children the data has."""
        return int(self._native.childrenCount)

    def __iter__(self) -> Iterator[DataSnapshot]:
        for child in _children(self._native.children):
            yield DataSnapshot(child)

    def __len__(self) -> int:
        return self.children_count

    def __repr__(self) -> str:
        return f"DataSnapshot(key={self.key!r}, value={self.value!r})"


class MutableData:
    """The current data at a location, inside a transaction. Change ``value``
    (or a child's) and return ``TransactionResult.success(data)``.

    Args:
        native: the native ``FIRMutableData``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRMutableData``."""
        return self._native

    @property
    def key(self) -> str | None:
        """The last part of the location's path."""
        key = self._native.key
        return None if key is None else str(key)

    @property
    def value(self) -> Any:
        """The data, as Python values (``None`` when there is none). Setting it
        replaces the data; ``None`` deletes it.

        The first time a transaction runs, this may be ``None`` while the
        server has data: the SDK has nothing cached yet. Return a value
        anyway; the SDK runs the transaction again with the server's data.
        """
        return to_python(self._native.value)

    @value.setter
    def value(self, value: Any) -> None:
        self._native.value = to_database(value)

    @property
    def priority(self) -> str | float | None:
        """The priority (``None``, a number or a ``str``). Settable."""
        priority: str | float | None = to_python(self._native.priority)
        return priority

    @priority.setter
    def priority(self, priority: str | float | None) -> None:
        self._native.priority = to_priority(priority)

    def child(self, path: str) -> MutableData:
        """The data at a path below this one. Changing it changes this data.

        Args:
            path: a relative path.

        Raises:
            ValueError: an invalid path.
        """
        validate_path(path)
        return MutableData(self._native.childDataByAppendingPath_(path))

    def has_child(self, path: str) -> bool:
        """``True`` if there is data at a path below this one.

        Args:
            path: a relative path.

        Raises:
            ValueError: an invalid path.
        """
        validate_path(path)
        return bool(self._native.hasChildAtPath_(path))

    def has_children(self) -> bool:
        """``True`` if the data has children."""
        return bool(self._native.hasChildren())

    @property
    def children_count(self) -> int:
        """How many children the data has."""
        return int(self._native.childrenCount)

    @property
    def children(self) -> list[MutableData]:
        """The children, each as ``MutableData``."""
        return [MutableData(child) for child in _children(self._native.children)]

    def __repr__(self) -> str:
        return f"MutableData(key={self.key!r}, value={self.value!r})"

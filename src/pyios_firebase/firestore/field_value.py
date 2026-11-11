"""``FieldValue``: special values the server applies (increment, delete, ...)."""

from __future__ import annotations

__all__ = ("FieldValue",)

from collections.abc import Iterable
from typing import Any

from rubicon.objc import ObjCClass

from ..types import ObjCObject
from ..util import objc_class, to_firestore


def _fir_field_value() -> ObjCClass:
    return objc_class("FIRFieldValue")


class FieldValue:
    """Special values for ``set_data`` / ``update_data``: the server applies
    them, instead of storing them as they are.

    ::

        doc.update_data({"visits": FieldValue.field_value_for_integer_increment(1)})
    """

    @staticmethod
    def field_value_for_delete() -> ObjCObject:
        """Delete the field (``update_data``, or ``set_data`` with merge)."""
        return _fir_field_value().fieldValueForDelete()

    @staticmethod
    def field_value_for_server_timestamp() -> ObjCObject:
        """The time the server receives the write."""
        return _fir_field_value().fieldValueForServerTimestamp()

    @staticmethod
    def field_value_for_array_union(elements: Iterable[Any]) -> ObjCObject:
        """Add elements to an array field, skipping those already in it.

        If the field is missing or not an array, it becomes an array of
        ``elements``.

        Args:
            elements: the elements to add. Converted with ``to_firestore``.

        Returns:
            A sentinel to use as a field value in ``set_data`` / ``update_data``.
        """
        return _fir_field_value().fieldValueForArrayUnion_(to_firestore(list(elements)))

    @staticmethod
    def field_value_for_array_remove(elements: Iterable[Any]) -> ObjCObject:
        """Remove every instance of each element from an array field.

        Args:
            elements: the elements to remove. Converted with ``to_firestore``.

        Returns:
            A sentinel to use as a field value in ``set_data`` / ``update_data``.
        """
        return _fir_field_value().fieldValueForArrayRemove_(
            to_firestore(list(elements))
        )

    @staticmethod
    def field_value_for_integer_increment(value: int) -> ObjCObject:
        """Add an integer to a number field, on the server.

        Safe when several devices increment at once. A missing field starts at 0.

        Args:
            value: the amount to add. Negative to subtract.

        Returns:
            A sentinel to use as a field value in ``set_data`` / ``update_data``.
        """
        return _fir_field_value().fieldValueForIntegerIncrement_(int(value))

    @staticmethod
    def field_value_for_double_increment(value: float) -> ObjCObject:
        """Add a float to a number field, on the server.

        Safe when several devices increment at once. A missing field starts at 0.

        Args:
            value: the amount to add. Negative to subtract.

        Returns:
            A sentinel to use as a field value in ``set_data`` / ``update_data``.
        """
        return _fir_field_value().fieldValueForDoubleIncrement_(float(value))

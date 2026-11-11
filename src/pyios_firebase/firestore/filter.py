"""``Filter``: conditions for queries, which can be combined with OR and AND."""

from __future__ import annotations

__all__ = ("Filter",)

from collections.abc import Iterable, Sequence
from typing import Any

from rubicon.objc import ObjCClass

from ..types import ObjCObject
from ..util import objc_class, to_firestore


def _fir_filter() -> ObjCClass:
    return objc_class("FIRFilter")


class Filter:
    """A condition for ``Query.query_where_filter``.

    Filters can be combined with ``or_filter_with_filters`` and
    ``and_filter_with_filters``, and nested::

        Filter.or_filter_with_filters([
            Filter.filter_where_field_is_equal_to("capital", True),
            Filter.filter_where_field_is_greater_than("population", 1_000_000),
        ])

    Make filters with the static methods; you do not call ``Filter(...)``
    yourself.

    Args:
        filter_: the native ``FIRFilter``.
    """

    def __init__(self, filter_: ObjCObject) -> None:
        self._filter = filter_

    # ---- single-field filters ----

    @staticmethod
    def filter_where_field_is_equal_to(field: str, value: Any) -> Filter:
        """Match documents where ``field == value``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. ``None`` matches Firestore ``null``. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isEqualTo_(field, to_firestore(value))
        )

    @staticmethod
    def filter_where_field_is_not_equal_to(field: str, value: Any) -> Filter:
        """Match documents where ``field != value``.

        Documents that do not have ``field`` do not match.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isNotEqualTo_(field, to_firestore(value))
        )

    @staticmethod
    def filter_where_field_is_less_than(field: str, value: Any) -> Filter:
        """Match documents where ``field < value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isLessThan_(field, to_firestore(value))
        )

    @staticmethod
    def filter_where_field_is_less_than_or_equal_to(field: str, value: Any) -> Filter:
        """Match documents where ``field <= value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isLessThanOrEqualTo_(
                field, to_firestore(value)
            )
        )

    @staticmethod
    def filter_where_field_is_greater_than(field: str, value: Any) -> Filter:
        """Match documents where ``field > value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isGreaterThan_(field, to_firestore(value))
        )

    @staticmethod
    def filter_where_field_is_greater_than_or_equal_to(
        field: str, value: Any
    ) -> Filter:
        """Match documents where ``field >= value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_isGreaterThanOrEqualTo_(
                field, to_firestore(value)
            )
        )

    @staticmethod
    def filter_where_field_array_contains(field: str, value: Any) -> Filter:
        """Match documents whose array ``field`` contains ``value``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the element to look for. Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_arrayContains_(field, to_firestore(value))
        )

    @staticmethod
    def filter_where_field_array_contains_any(
        field: str, values: Sequence[Any]
    ) -> Filter:
        """Match documents whose array ``field`` contains at least one of ``values``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the elements to look for (up to 30). Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``values`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_arrayContainsAny_(
                field, to_firestore(values)
            )
        )

    @staticmethod
    def filter_where_field_in(field: str, values: Sequence[Any]) -> Filter:
        """Match documents where ``field`` is equal to one of ``values``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the allowed values (up to 30). Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``values`` holds a value Firestore cannot store.
        """
        return Filter(_fir_filter().filterWhereField_in_(field, to_firestore(values)))

    @staticmethod
    def filter_where_field_not_in(field: str, values: Sequence[Any]) -> Filter:
        """Match documents where ``field`` is none of ``values``.

        Documents that do not have ``field`` do not match.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the values to exclude (up to 10). Converted with ``to_firestore``.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.

        Raises:
            TypeError: ``values`` holds a value Firestore cannot store.
        """
        return Filter(
            _fir_filter().filterWhereField_notIn_(field, to_firestore(values))
        )

    # ---- combine filters ----

    @staticmethod
    def or_filter_with_filters(filters: Iterable[Filter]) -> Filter:
        """A filter that matches if ANY of ``filters`` matches.

        Args:
            filters: the filters to combine. They can be combined filters too.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.
        """
        return Filter(_fir_filter().orFilterWithFilters_([f._filter for f in filters]))

    @staticmethod
    def and_filter_with_filters(filters: Iterable[Filter]) -> Filter:
        """A filter that matches if ALL of ``filters`` match.

        Args:
            filters: the filters to combine. They can be combined filters too.

        Returns:
            A ``Filter`` for ``Query.query_where_filter``.
        """
        return Filter(_fir_filter().andFilterWithFilters_([f._filter for f in filters]))

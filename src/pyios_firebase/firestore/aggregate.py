"""Aggregate queries: count, sum and average, calculated on the server."""

from __future__ import annotations

__all__ = ("AggregateField", "AggregateQuery", "AggregateQuerySnapshot")

from rubicon.objc import objc_id

from ..types import ObjCObject, ResultCallback
from ..util import (
    error_from_pointer,
    objc_class,
    objc_instance,
    one_shot_block,
    to_python,
)


class AggregateField:
    """One value to calculate in ``Query.aggregate``: a count, a sum or an average.

    Make them with the static methods; you do not call ``AggregateField(...)``
    yourself.

    Args:
        field: the native ``FIRAggregateField``.
    """

    def __init__(self, field: ObjCObject) -> None:
        self._field = field

    @staticmethod
    def aggregate_field_for_count() -> AggregateField:
        """The number of documents."""
        return AggregateField(objc_class("FIRAggregateField").aggregateFieldForCount())

    @staticmethod
    def aggregate_field_for_sum_of_field(field: str) -> AggregateField:
        """The sum of a number field over the matching documents.

        Documents without the field, or with a value that is not a number, are
        skipped.

        Args:
            field: the field name (dotted for a nested field).

        Returns:
            An ``AggregateField`` for ``Query.aggregate``.
        """
        return AggregateField(
            objc_class("FIRAggregateField").aggregateFieldForSumOfField_(field)
        )

    @staticmethod
    def aggregate_field_for_average_of_field(field: str) -> AggregateField:
        """The average of a number field over the matching documents.

        Documents without the field, or with a value that is not a number, are
        skipped. With no such documents the average is ``None``.

        Args:
            field: the field name (dotted for a nested field).

        Returns:
            An ``AggregateField`` for ``Query.aggregate``.
        """
        return AggregateField(
            objc_class("FIRAggregateField").aggregateFieldForAverageOfField_(field)
        )


class AggregateQuerySnapshot:
    """The result of an aggregate query.

    Args:
        snapshot: the native ``FIRAggregateQuerySnapshot``.
    """

    def __init__(self, snapshot: ObjCObject) -> None:
        self._snapshot = snapshot

    @property
    def count(self) -> int:
        """The number of documents (for ``Query.count``)."""
        return int(self._snapshot.count.integerValue)

    def value_for_aggregate_field(
        self, aggregate_field: AggregateField
    ) -> int | float | None:
        """The value calculated for one of the query's fields.

        Args:
            aggregate_field: one of the ``AggregateField`` objects given to
                ``Query.aggregate`` (the same object, or an equal one).

        Returns:
            An ``int`` (counts, sums of integers), a ``float``, or ``None`` (for
            example the average of no documents).
        """
        value = self._snapshot.valueForAggregateField_(aggregate_field._field)
        if value is None:
            return None
        result: int | float | None = to_python(value)
        return result


class AggregateQuery:
    """A count, sum or average, calculated on the server without downloading
    the documents. Made by ``Query.count`` or ``Query.aggregate``.

    Args:
        ref: the native ``FIRAggregateQuery``.
    """

    def __init__(self, ref: ObjCObject) -> None:
        self._ref = ref

    def aggregation_with_source(
        self, source: int, callback: ResultCallback[AggregateQuerySnapshot]
    ) -> None:
        """Run the aggregation.

        Args:
            source: ``FIRAggregateSource.Server``.
            callback: gets ``(AggregateQuerySnapshot, None)`` or ``(None, error)``.
        """

        def on_done(snapshot_ptr: object, error_ptr: object) -> None:
            error = error_from_pointer(error_ptr)
            if error is not None:
                callback(None, error)
                return
            callback(AggregateQuerySnapshot(objc_instance(snapshot_ptr)), None)

        self._ref.aggregationWithSource_completion_(
            source, one_shot_block(on_done, objc_id, objc_id)
        )

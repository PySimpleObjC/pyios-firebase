"""``Query``: filters, order, limits and cursors, then reads or listens."""

from __future__ import annotations

__all__ = ("Query",)

from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from rubicon.objc import objc_id

from ..types import ObjCObject, ResultCallback
from ..util import (
    error_from_pointer,
    listener_block,
    objc_instance,
    one_shot_block,
    to_firestore,
)
from . import query_snapshot  # module import: query_snapshot imports us back
from ._limits import MAX_ARRAY_CONTAINS_ANY, MAX_IN, MAX_NOT_IN, filter_values
from .aggregate import AggregateField, AggregateQuery
from .listener_registration import ListenerRegistration, SnapshotListenOptions

if TYPE_CHECKING:
    from .document_snapshot import DocumentSnapshot
    from .filter import Filter


def _snapshot_handler(
    callback: ResultCallback[query_snapshot.QuerySnapshot],
) -> Callable[[Any, Any], None]:
    """Block body for (FIRQuerySnapshot, NSError): callback(QuerySnapshot, error)."""

    def on_snapshot(snapshot_ptr: Any, error_ptr: Any) -> None:
        if not snapshot_ptr:
            callback(None, error_from_pointer(error_ptr))
            return
        callback(query_snapshot.QuerySnapshot(objc_instance(snapshot_ptr)), None)

    return on_snapshot


class Query:
    """A query over a collection (or a collection group).

    Every ``query_*`` method gives a NEW ``Query``, so you can chain them::

        db.collection_with_path("cities") \\
            .query_where_field_is_equal_to("state", "CA") \\
            .query_ordered_by_field("population", descending=True) \\
            .query_limited_to(10) \\
            .get_documents(on_cities)

    Values are converted with ``to_firestore``, so ``datetime`` and ``None``
    work in filters and cursors.

    You get queries from ``CollectionReference``, ``Firestore`` and the
    ``query_*`` methods; you do not make them yourself.

    Args:
        ref: the native ``FIRQuery``.
    """

    def __init__(self, ref: ObjCObject) -> None:
        self._ref = ref

    # ---- start and end points ----

    @staticmethod
    def _snapshot_of(document: DocumentSnapshot) -> ObjCObject:
        snapshot = getattr(document, "_snapshot", None)
        if snapshot is None:
            raise ValueError(
                "Pass a DocumentSnapshot (from a callback), not a DocumentReference."
            )
        return snapshot

    def query_starting_at_document(self, document: DocumentSnapshot) -> Query:
        """Start the results at ``document``, including it.

        The query needs a ``query_ordered_by_field``; the cursor uses the
        document's values for those fields.

        Args:
            document: a ``DocumentSnapshot`` from a callback (for example
                ``snapshot[-1]`` of the previous page). A ``DocumentReference`` is
                not enough: the cursor needs the document's data.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            ValueError: ``document`` is not a ``DocumentSnapshot``.
        """
        return Query(self._ref.queryStartingAtDocument_(self._snapshot_of(document)))

    def query_starting_after_document(self, document: DocumentSnapshot) -> Query:
        """Start the results right after ``document``, for the next page.

        Args:
            document: a ``DocumentSnapshot`` from a callback (for example
                ``snapshot[-1]`` of the previous page). A ``DocumentReference`` is
                not enough: the cursor needs the document's data.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            ValueError: ``document`` is not a ``DocumentSnapshot``.
        """
        return Query(self._ref.queryStartingAfterDocument_(self._snapshot_of(document)))

    def query_ending_at_document(self, document: DocumentSnapshot) -> Query:
        """End the results at ``document``, including it.

        Args:
            document: a ``DocumentSnapshot`` from a callback (for example
                ``snapshot[-1]`` of the previous page). A ``DocumentReference`` is
                not enough: the cursor needs the document's data.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            ValueError: ``document`` is not a ``DocumentSnapshot``.
        """
        return Query(self._ref.queryEndingAtDocument_(self._snapshot_of(document)))

    def query_ending_before_document(self, document: DocumentSnapshot) -> Query:
        """End the results right before ``document``.

        Args:
            document: a ``DocumentSnapshot`` from a callback (for example
                ``snapshot[-1]`` of the previous page). A ``DocumentReference`` is
                not enough: the cursor needs the document's data.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            ValueError: ``document`` is not a ``DocumentSnapshot``.
        """
        return Query(self._ref.queryEndingBeforeDocument_(self._snapshot_of(document)))

    def query_starting_at_values(self, values: Sequence[Any]) -> Query:
        """Start the results at these order-by values, including them.

        ::

            cities.query_ordered_by_field("population").query_starting_at_values([1_000_000])

        Args:
            values: one value per ``query_ordered_by_field`` call, in the same
                order. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryStartingAtValues_(to_firestore(values)))

    def query_starting_after_values(self, values: Sequence[Any]) -> Query:
        """Start the results right after these order-by values.

        Args:
            values: one value per ``query_ordered_by_field`` call, in the same
                order. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryStartingAfterValues_(to_firestore(values)))

    def query_ending_at_values(self, values: Sequence[Any]) -> Query:
        """End the results at these order-by values, including them.

        Args:
            values: one value per ``query_ordered_by_field`` call, in the same
                order. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryEndingAtValues_(to_firestore(values)))

    def query_ending_before_values(self, values: Sequence[Any]) -> Query:
        """End the results right before these order-by values.

        Args:
            values: one value per ``query_ordered_by_field`` call, in the same
                order. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryEndingBeforeValues_(to_firestore(values)))

    # ---- filters ----

    def query_where_field_is_equal_to(self, field: str, value: Any) -> Query:
        """Match documents where ``field == value``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. ``None`` matches Firestore ``null``. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(self._ref.queryWhereField_isEqualTo_(field, to_firestore(value)))

    def query_where_field_is_not_equal_to(self, field: str, value: Any) -> Query:
        """Match documents where ``field != value``.

        Documents that do not have ``field`` do not match.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(
            self._ref.queryWhereField_isNotEqualTo_(field, to_firestore(value))
        )

    def query_where_field_is_less_than(self, field: str, value: Any) -> Query:
        """Match documents where ``field < value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(self._ref.queryWhereField_isLessThan_(field, to_firestore(value)))

    def query_where_field_is_less_than_or_equal_to(
        self, field: str, value: Any
    ) -> Query:
        """Match documents where ``field <= value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(
            self._ref.queryWhereField_isLessThanOrEqualTo_(field, to_firestore(value))
        )

    def query_where_field_is_greater_than(self, field: str, value: Any) -> Query:
        """Match documents where ``field > value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(
            self._ref.queryWhereField_isGreaterThan_(field, to_firestore(value))
        )

    def query_where_field_is_greater_than_or_equal_to(
        self, field: str, value: Any
    ) -> Query:
        """Match documents where ``field >= value``.

        Values are compared by Firestore's type ordering, so ``datetime``, numbers
        and strings each only match values of the same type.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the value to compare with. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(
            self._ref.queryWhereField_isGreaterThanOrEqualTo_(
                field, to_firestore(value)
            )
        )

    def query_where_field_array_contains(self, field: str, value: Any) -> Query:
        """Match documents whose array ``field`` contains ``value``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            value: the element to look for. Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``value`` holds a value Firestore cannot store.
        """
        return Query(
            self._ref.queryWhereField_arrayContains_(field, to_firestore(value))
        )

    def query_where_field_array_contains_any(
        self, field: str, values: Sequence[Any]
    ) -> Query:
        """Match documents whose array ``field`` contains at least one of ``values``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the elements to look for (up to 30). Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``values`` is not a list or tuple, or holds a value
                Firestore cannot store.
            ValueError: ``values`` is empty, or has more than 30 values (an
                empty list would abort the app in the SDK).
        """
        return Query(
            self._ref.queryWhereField_arrayContainsAny_(
                field,
                filter_values(values, "array-contains-any", MAX_ARRAY_CONTAINS_ANY),
            )
        )

    def query_where_field_in(self, field: str, values: Sequence[Any]) -> Query:
        """Match documents where ``field`` is equal to one of ``values``.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the allowed values (up to 30). Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``values`` is not a list or tuple, or holds a value
                Firestore cannot store.
            ValueError: ``values`` is empty, or has more than 30 values (an
                empty list would abort the app in the SDK).
        """
        return Query(
            self._ref.queryWhereField_in_(field, filter_values(values, "in", MAX_IN))
        )

    def query_where_field_not_in(self, field: str, values: Sequence[Any]) -> Query:
        """Match documents where ``field`` is none of ``values``.

        Documents that do not have ``field`` do not match.

        Args:
            field: the field name. Use a dotted name (``"address.city"``) for a
                nested field.
            values: the values to exclude (up to 10). Converted with ``to_firestore``.

        Returns:
            A new ``Query``; this one is unchanged.

        Raises:
            TypeError: ``values`` is not a list or tuple, or holds a value
                Firestore cannot store.
            ValueError: ``values`` is empty, or has more than 10 values (an
                empty list would abort the app in the SDK).
        """
        return Query(
            self._ref.queryWhereField_notIn_(
                field, filter_values(values, "not-in", MAX_NOT_IN)
            )
        )

    def query_where_filter(self, filter_: Filter) -> Query:
        """Filter with a ``Filter``, for OR conditions and nested AND/OR.

        Args:
            filter_: the filter, for example
                ``Filter.or_filter_with_filters([...])``.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryWhereFilter_(filter_._filter))

    # ---- order and limit ----

    def query_limited_to(self, limit: int) -> Query:
        """Return at most ``limit`` documents, from the start of the order.

        Args:
            limit: the most documents to return. Must be positive.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryLimitedTo_(limit))

    def query_limited_to_last(self, limit: int) -> Query:
        """Return at most ``limit`` documents, from the end of the order.

        The query must have a ``query_ordered_by_field``. Documents still come
        back in the query's order.

        Args:
            limit: the most documents to return. Must be positive.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        return Query(self._ref.queryLimitedToLast_(limit))

    def query_ordered_by_field(self, field: str, descending: bool = False) -> Query:
        """Order the results by ``field``.

        Call it more than once to order by several fields. Documents that do not
        have ``field`` are left out of the results.

        Args:
            field: the field name (dotted for a nested field).
            descending: ``True`` for largest first; ``False`` (the default) for
                smallest first.

        Returns:
            A new ``Query``; this one is unchanged.
        """
        if descending:
            return Query(self._ref.queryOrderedByField_descending_(field, True))
        return Query(self._ref.queryOrderedByField_(field))

    # ---- aggregates ----

    @property
    def count(self) -> AggregateQuery:
        """An aggregate query for the number of matching documents."""
        return AggregateQuery(self._ref.count)

    def aggregate(self, fields: Iterable[AggregateField]) -> AggregateQuery:
        """An aggregate query for several values in one request.

        ::

            query.aggregate([
                AggregateField.aggregate_field_for_count(),
                AggregateField.aggregate_field_for_sum_of_field("population"),
            ])

        Args:
            fields: the values to calculate.

        Returns:
            An ``AggregateQuery``. Run it with ``aggregation_with_source``.
        """
        return AggregateQuery(self._ref.aggregate_([f._field for f in fields]))

    # ---- run the query ----

    def get_documents(
        self,
        callback: ResultCallback[query_snapshot.QuerySnapshot],
        source: int | None = None,
    ) -> None:
        """Read the matching documents once.

        Args:
            callback: gets ``(QuerySnapshot, None)`` or ``(None, error)``.
            source: ``FIRFirestoreSource.Default`` (default) / ``Server`` / ``Cache``.
        """
        block = one_shot_block(_snapshot_handler(callback), objc_id, objc_id)
        if source is None:
            self._ref.getDocumentsWithCompletion_(block)
        else:
            self._ref.getDocumentsWithSource_completion_(source, block)

    def add_snapshot_listener(
        self,
        callback: ResultCallback[query_snapshot.QuerySnapshot],
        include_metadata_changes: bool = False,
        options: SnapshotListenOptions | None = None,
    ) -> ListenerRegistration:
        """Listen to the matching documents: ``callback`` runs now, then on
        every change. Use ``snapshot.document_changes`` for only what changed.

        Args:
            callback: gets ``(QuerySnapshot, None)`` or ``(None, error)``.
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

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Query) and bool(self._ref.isEqual_(other._ref))

    def __hash__(self) -> int:
        return int(self._ref.hash)

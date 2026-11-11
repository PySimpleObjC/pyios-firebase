"""What a query is made of, mirrored in Python, to check it like the SDK does.

The Firestore SDK checks a query as it is built, and raises an Objective-C
exception on a mistake, which aborts the app (Python cannot catch it). These
checks run first and raise a ``ValueError`` instead, with the SDK's own rules
(``firestore/core/src/api/query_core.cc`` and ``FIRQuery.mm``, SDK 13):

- operators that cannot be combined (two ``not-in``, ``not-in`` with ``in``...)
- a limit that is not positive
- an order added after a start or end point
- ``limit_to_last`` without an order, when the query runs
- more cursor values than ordered fields
- a document cursor that does not exist, or lacks an ordered field

The state is only **known** for queries built from a ``CollectionReference``
or a collection group through this library. A ``Query`` made from a native
query (``QuerySnapshot.query``) has an unknown state: it is not checked, so a
check can never refuse a query the SDK would accept.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

Part = tuple[str, str]
"""One field filter: ``(operator, field)``, for example ``("not-in", "country")``."""

INEQUALITY: Final = frozenset({"<", "<=", ">", ">=", "!=", "not-in"})
DOCUMENT_ID: Final = "__name__"
_INT32_MAX: Final = 2**31 - 1

# operator -> the operators a query must not already have (ConflictingOps)
_CONFLICTS: Final[Mapping[str, frozenset[str]]] = {
    "!=": frozenset({"!=", "not-in"}),
    "array-contains-any": frozenset({"not-in"}),
    "in": frozenset({"not-in"}),
    "not-in": frozenset({"array-contains-any", "in", "not-in", "!="}),
}


def check_limit(limit: int) -> int:
    """A query limit, as the SDK takes it (a positive 32-bit integer).

    Args:
        limit: the limit.

    Returns:
        The limit.

    Raises:
        TypeError: not an ``int`` (a ``bool`` neither).
        ValueError: not 1 to 2,147,483,647.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(f"a query limit is an int, not {type(limit).__name__}")
    if not 0 < limit <= _INT32_MAX:
        raise ValueError(f"a query limit must be 1 to {_INT32_MAX:,}, not {limit}")
    return limit


@dataclass(frozen=True)
class QueryState:
    """The parts of a query that the SDK's checks look at."""

    known: bool = True
    parts: tuple[Part, ...] = ()
    orders: tuple[str, ...] = ()
    has_start: bool = False
    has_end: bool = False
    limit_to_last: bool = False

    def with_filters(self, parts: Sequence[Part]) -> QueryState:
        """The state after adding filters (one, or the flattened parts of a
        composite ``Filter``), checking each against those before it.

        Args:
            parts: the new field filters, in order.

        Raises:
            ValueError: two operators that cannot be used together.
        """
        if not self.known:
            return self
        existing = [op for op, _field in self.parts]
        for op, _field in parts:
            for conflicting in _CONFLICTS.get(op, ()):
                if conflicting in existing:
                    if conflicting == op:
                        raise ValueError(
                            f"a query cannot have more than one '{op}' filter"
                        )
                    raise ValueError(
                        f"a query cannot combine '{op}' and '{conflicting}' filters"
                    )
            existing.append(op)
        return replace(self, parts=(*self.parts, *parts))

    def with_order(self, field: str) -> QueryState:
        """The state after ``query_ordered_by_field``.

        Args:
            field: the ordered field.

        Raises:
            ValueError: the query already has a start or an end point.
        """
        if not self.known:
            return self
        if self.has_start or self.has_end:
            point = "a start" if self.has_start else "an end"
            raise ValueError(
                f"order the query before giving it {point} point "
                "(query_ordered_by_field, then query_starting_... / query_ending_...)"
            )
        return replace(self, orders=(*self.orders, field))

    def with_values_cursor(self, values: Sequence[Any], start: bool) -> QueryState:
        """The state after a ``..._values`` cursor.

        Args:
            values: the cursor's values.
            start: ``True`` for a start point, ``False`` for an end point.

        Raises:
            ValueError: more values than ordered fields.
        """
        if not self.known:
            return self
        if len(values) > len(self.orders):
            raise ValueError(
                f"a cursor can have one value per ordered field: {len(values)} "
                f"values for {len(self.orders)} order(s) "
                "(add query_ordered_by_field first)"
            )
        return self._with_point(start)

    def normalized_orders(self) -> list[str]:
        """The fields a document cursor takes values from: the explicit orders,
        then the other inequality-filtered fields (sorted), then the document
        ID, as the SDK orders them."""
        orders = list(self.orders)
        inequality = sorted(
            {field for op, field in self.parts if op in INEQUALITY} - set(orders)
        )
        orders.extend(inequality)
        if DOCUMENT_ID not in orders:
            orders.append(DOCUMENT_ID)
        return orders

    def with_document_cursor(
        self,
        exists: bool,
        data: Mapping[str, Any],
        estimated: Mapping[str, Any],
        start: bool,
    ) -> QueryState:
        """The state after a ``..._document`` cursor.

        Args:
            exists: whether the document exists.
            data: the document's data.
            estimated: the data with pending server timestamps estimated (a
                field that is ``None`` in ``data`` but not here is one).
            start: ``True`` for a start point, ``False`` for an end point.

        Raises:
            ValueError: the document does not exist, lacks an ordered field, or
                has a server timestamp not written yet in one.
        """
        if not self.known:
            return self
        if not exists:
            raise ValueError(
                "a query cannot start or end at a document that does not exist"
            )
        for field in self.normalized_orders():
            if field == DOCUMENT_ID:
                continue
            found, value = _lookup(data, field)
            if not found:
                raise ValueError(
                    f"the cursor document has no '{field}' field, which the query "
                    "orders by"
                )
            if value is None and _lookup(estimated, field)[1] is not None:
                raise ValueError(
                    f"the cursor document's '{field}' is a server timestamp not written "
                    "yet: wait for the write (has_pending_writes) before paging from it"
                )
        return self._with_point(start)

    def _with_point(self, start: bool) -> QueryState:
        return replace(self, has_start=True) if start else replace(self, has_end=True)

    def check_runnable(self) -> None:
        """Before ``get_documents`` / ``add_snapshot_listener``.

        Raises:
            ValueError: ``limit_to_last`` without an order.
        """
        if self.known and self.limit_to_last and not self.orders:
            raise ValueError(
                "a query with query_limited_to_last needs a query_ordered_by_field"
            )


def _lookup(data: Mapping[str, Any], field: str) -> tuple[bool, Any]:
    """``(found, value)`` for a dotted field path."""
    value: Any = data
    for key in field.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return False, None
        value = value[key]
    return True, value


EMPTY: Final = QueryState()
"""A new query of a collection or collection group."""
UNKNOWN: Final = QueryState(known=False)
"""A query made from a native query: not checked."""

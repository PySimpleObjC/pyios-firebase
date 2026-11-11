"""Checks on the value lists of ``in``, ``not-in`` and ``array-contains-any``.

The SDK aborts the app (an Objective-C exception, or a failed assertion) on an
empty list, or on a value that is not a list. The server rejects too many
values with ``INVALID_ARGUMENT``, after a round trip. Both are caught here, as
a Python ``ValueError`` / ``TypeError`` before anything is sent.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from ..util import to_firestore

# the most values Firestore takes in one filter
MAX_IN: Final = 30
MAX_ARRAY_CONTAINS_ANY: Final = 30
MAX_NOT_IN: Final = 10


def filter_values(values: Sequence[Any], operator: str, limit: int) -> Any:
    """``values`` for an ``in`` / ``not-in`` / ``array-contains-any`` filter.

    Args:
        values: the list (or tuple) of values.
        operator: the filter's name, for the error message (``"not-in"``).
        limit: the most values the filter takes.

    Returns:
        The values as a native array (see ``to_firestore``).

    Raises:
        TypeError: ``values`` is not a list or tuple (a ``str`` is not a list of
            values), or holds a value Firestore cannot store.
        ValueError: ``values`` is empty, or has more than ``limit`` values.
    """
    if isinstance(values, str | bytes | bytearray) or not isinstance(values, Sequence):
        raise TypeError(
            f"'{operator}' filters take a list of values, not {type(values).__name__}"
        )
    if not values:
        raise ValueError(f"'{operator}' filters need at least one value")
    if len(values) > limit:
        raise ValueError(
            f"'{operator}' filters take at most {limit} values, not {len(values)}"
        )
    return to_firestore(list(values))

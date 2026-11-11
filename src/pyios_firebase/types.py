"""Types shared by the whole package, for your own annotations.

Errors are dicts you can also read with dots
(``error.code`` or ``error["code"]``). The classes below only tell editors and
type checkers which keys they have::

    from pyios_firebase.firestore import QuerySnapshot
    from pyios_firebase.types import FirebaseError


    def on_cities(snapshot: QuerySnapshot | None, error: FirebaseError | None) -> None:
        if error is not None:
            print(error.code, error.description)
            return
        assert snapshot is not None
        for doc in snapshot:
            print(doc.document_id, doc.data)

Callback aliases:

- ``ErrorCallback``: ``(error)`` for writes
- ``ResultCallback[T]``: ``(result, error)``; exactly one of them is ``None``
"""

from __future__ import annotations

__all__ = (
    "ErrorCallback",
    "FirebaseError",
    "FirestoreData",
    "ObjCObject",
    "QueryDict",
    "ResultCallback",
)

from collections.abc import Callable, Mapping
from typing import Any, TypeAlias, TypeVar

T = TypeVar("T")

ObjCObject: TypeAlias = Any
"""An Objective-C object, as Rubicon gives it (a ``rubicon.objc.ObjCInstance``).

Typed as ``Any`` because Rubicon has no type information: its attributes are
the Objective-C object's properties and methods, found at runtime.
"""


class QueryDict(dict[str, Any]):
    """A ``dict`` that can also be read and written with dots.

    ::

        d = QueryDict(code=1)
        d.description = "x"  # same as d["description"] = "x"
        d.code               # same as d["code"]

    Reading a missing key with a dot raises ``AttributeError``.
    """

    def __getattr__(self, attr: str) -> Any:
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {attr!r}"
            ) from None

    def __setattr__(self, attr: str, value: Any) -> None:
        self[attr] = value


class FirebaseError(QueryDict):
    """An error from Firebase. Every callback ``error`` has these keys."""

    code: int
    """The error code (``NSError.code``). Its meaning depends on ``domain``."""
    description: str
    """A human-readable description (``NSError.localizedDescription``)."""
    domain: str
    """The error domain, for example ``"FIRFirestoreErrorDomain"``."""
    underlying_error: ObjCObject
    """The nested ``NSError`` that caused this one, or ``None``. For debugging."""


FirestoreData: TypeAlias = Mapping[str, Any]
"""Data you write to a document: a mapping of field names to Python values."""

ErrorCallback: TypeAlias = Callable[[FirebaseError | None], None]
"""A callback for writes: gets the error, or ``None`` when it worked."""

ResultCallback: TypeAlias = Callable[[T | None, FirebaseError | None], None]
"""A callback that gets ``(result, error)``. Exactly one of them is ``None``."""

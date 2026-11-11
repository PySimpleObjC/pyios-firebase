"""Firebase Realtime Database: a JSON tree, synced live to every client.

    from pyios_firebase.database import DataEventType, Database, ServerValue

    db = Database.database()
    messages = db.reference("rooms/general/messages")

    messages.child_by_auto_id().set_value(
        {"text": "Hello", "sent_at": ServerValue.timestamp()}
    )

    def on_message(snapshot, previous_key):
        print(snapshot.key, snapshot.value)

    observer = messages.order_by_child("sent_at").limit_to_last(50).observe(
        DataEventType.CHILD_ADDED, on_message
    )
    ...
    observer.remove()

Values are Python values: ``dict``, ``list``, ``str``, ``int``, ``float``,
``bool`` and ``None``. Bad paths, keys, values and queries raise ``ValueError``
or ``TypeError`` (the SDK would raise an Objective-C exception, which aborts
the app).

Needs the ``FirebaseDatabase`` framework.
"""

from .database import Database  # noqa: I001 - first: the others import it lazily
from .errors import DATABASE_ERROR_DOMAIN, DatabaseError, DatabaseErrorCode
from .query import DataEventType, DatabaseObserver, DatabaseQuery, EventCallback
from .reference import (
    TRANSACTION_ERROR_DOMAIN,
    DatabaseReference,
    OnDisconnect,
    TransactionCallback,
    TransactionResult,
    WriteCallback,
)
from .snapshot import DataSnapshot, MutableData
from .values import ServerValue, to_database

__all__ = (
    "DATABASE_ERROR_DOMAIN",
    "TRANSACTION_ERROR_DOMAIN",
    "DataEventType",
    "DataSnapshot",
    "Database",
    "DatabaseError",
    "DatabaseErrorCode",
    "DatabaseObserver",
    "DatabaseQuery",
    "DatabaseReference",
    "EventCallback",
    "MutableData",
    "OnDisconnect",
    "ServerValue",
    "TransactionCallback",
    "TransactionResult",
    "WriteCallback",
    "to_database",
)

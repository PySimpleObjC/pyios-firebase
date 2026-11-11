"""Cloud Firestore.

    from pyios_firebase.firestore import Firestore

    db = Firestore.firestore()
    db.collection_with_path("cities").document_with_path("LA").set_data({"name": "Los Angeles"})

Needs the ``FirebaseFirestore`` framework.
"""

# firestore first: it pulls in the rest in an order that works with the
# circular imports between references and snapshots
from .firestore import Firestore  # noqa: I001
from .aggregate import AggregateField, AggregateQuery, AggregateQuerySnapshot
from .collection_reference import CollectionReference
from .document_change import DocumentChange
from .document_reference import DocumentReference
from .document_snapshot import DocumentSnapshot
from .enums import (
    FIRAggregateSource,
    FIRDocumentChangeType,
    FIRFirestoreSource,
    FIRListenSource,
    FIRServerTimestampBehavior,
)
from .field_value import FieldValue
from .filter import Filter
from .listener_registration import ListenerRegistration, SnapshotListenOptions
from .query import Query
from .query_snapshot import QuerySnapshot
from .snapshot_metadata import SnapshotMetadata
from .transaction import Transaction, TransactionException
from .write_batch import WriteBatch

__all__ = (
    "AggregateField",
    "AggregateQuery",
    "AggregateQuerySnapshot",
    "CollectionReference",
    "DocumentChange",
    "DocumentReference",
    "DocumentSnapshot",
    "FIRAggregateSource",
    "FIRDocumentChangeType",
    "FIRFirestoreSource",
    "FIRListenSource",
    "FIRServerTimestampBehavior",
    "FieldValue",
    "Filter",
    "Firestore",
    "ListenerRegistration",
    "Query",
    "QuerySnapshot",
    "SnapshotListenOptions",
    "SnapshotMetadata",
    "Transaction",
    "TransactionException",
    "WriteBatch",
)

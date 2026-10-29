from ctypes import POINTER

from rubicon.objc import Block, ObjCClass, ObjCInstance, at
from rubicon.objc.runtime import objc_id

from .util import QueryDict

FIRFirestore = ObjCClass("FIRFirestore")
NSError = ObjCClass("NSError")
FIRAggregateField = ObjCClass("FIRAggregateField")
NSNumber = ObjCClass("NSNumber")


class ListenerRegistration:
    def __init__(self, registration, on_remove):
        self._registration = registration
        self._on_remove = on_remove

    def remove(self):
        if self._registration is None:
            return  # already removed
        self._registration.remove()
        self._registration = None
        self._on_remove()


class DocumentReference:
    def __init__(self, ref, snapshot=None):
        self._ref = ref
        self._snapshot = snapshot  # only set when the document was read
        self._blocks = set()  # keeps blocks alive until Firestore calls them

    def add_snapshot_listener(self, callback):
        def on_snapshot(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None

            if snapshot is None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return
            callback(DocumentReference(self._ref, snapshot), None)

        block = Block(on_snapshot, None, objc_id, objc_id)
        self._blocks.add(block)  # stays here until remove() is called

        registration = self._ref.addSnapshotListener_(block)
        return ListenerRegistration(registration, lambda: self._blocks.discard(block))

    @property
    def document_id(self):
        return str(self._ref.documentID)

    @property
    def data(self):
        if self._snapshot is None:
            return None  # no data was loaded for this reference
        return self._snapshot.data

    @property
    def exists(self):
        if self._snapshot is None:
            return None  # no data was loaded for this reference
        return self._snapshot.exists

    def delete_document(self, callback=None):
        holder = {}

        def on_done(error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if callback is None:
                return
            if error:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
            callback(error)

        block = Block(on_done, None, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.deleteDocumentWithCompletion_(block)

    def get_document(self, callback):
        holder = {}

        def on_done(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if error is not None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return
            callback(DocumentReference(self._ref, snapshot), None)

        block = Block(on_done, None, objc_id, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.getDocumentWithCompletion_(block)

    def set_data(self, data, callback=None):
        holder = {}

        def on_done(error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if callback is None:
                return
            if error:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
            callback(error)

        block = Block(on_done, None, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.setData_completion_(data, block)

    def update_data(self, data, callback=None):
        holder = {}

        def on_done(error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if callback is None:
                return
            if error:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
            callback(error)

        block = Block(on_done, None, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.updateData_completion_(data, block)


class DocumentChange:
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"

    _TYPES = {0: ADDED, 1: MODIFIED, 2: REMOVED}

    def __init__(self, change):
        self._change = change

    @property
    def type(self):
        return self._TYPES.get(self._change.type)

    @property
    def document(self):
        doc = self._change.document
        return DocumentReference(doc.reference, doc)


class Transaction:
    def __init__(self, transaction, error_pointer):
        self._transaction = transaction
        self._error_pointer = error_pointer

    def get_document(self, document_reference):
        snapshot = self._transaction.getDocument_error_(
            document_reference._ref, self._error_pointer
        )
        if self._error_pointer[0].value is not None:
            raise RuntimeError("Could not get document")
        return DocumentReference(document_reference._ref, snapshot)

    def update_data(self, data, document_reference):
        self._transaction.updateData_forDocument_(data, document_reference._ref)


class TransactionException(Exception):
    pass


class WriteBatch:
    def __init__(self, batch):
        self._batch = batch
        self._blocks = set()  # keeps blocks alive until Firestore calls them

    def set_data(self, data, document, merge=False):
        if merge:
            self._batch.setData_forDocument_merge_(data, document._ref, True)
        else:
            self._batch.setData_forDocument_(data, document._ref)
        return self

    def set_data_merge_fields(self, data, document, fields):
        self._batch.setData_forDocument_mergeFields_(data, document._ref, fields)
        return self

    def update_data(self, data, document):
        self._batch.updateData_forDocument_(data, document._ref)
        return self

    def delete_document(self, document):
        self._batch.deleteDocument_(document._ref)
        return self

    def commit(self, callback=None):
        holder = {}

        def on_done(error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if callback is None:
                return
            if error:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
            callback(error)

        block = Block(on_done, None, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._batch.commitWithCompletion_(block)


class AggregateField:
    def __init__(self, field):
        self._field = field

    @staticmethod
    def aggregate_field_for_count():
        return AggregateField(FIRAggregateField.aggregateFieldForCount())

    @staticmethod
    def aggregate_field_for_sum_of_field(field):
        return AggregateField(FIRAggregateField.aggregateFieldForSumOfField_(field))

    @staticmethod
    def aggregate_field_for_average_of_field(field):
        return AggregateField(FIRAggregateField.aggregateFieldForAverageOfField_(field))


class AggregateQuerySnapshot:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    @property
    def count(self):
        return int(self._snapshot.count.integerValue)

    def value_for_aggregate_field(self, aggregate_field):
        value = self._snapshot.valueForAggregateField_(aggregate_field._field)
        if value is None:
            return None
        return ObjCInstance(value)


class FIRAggregateSource:
    Server = 0


class AggregateQuery:
    def __init__(self, ref):
        self._ref = ref
        self._blocks = set()  # keeps blocks alive until Firestore calls them

    def aggregation_with_source(self, source, callback):
        holder = {}

        def on_done(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if error is not None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return
            callback(AggregateQuerySnapshot(snapshot), None)

        block = Block(on_done, None, objc_id, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.aggregationWithSource_completion_(source, block)


class Query:
    def __init__(self, ref):
        self._ref = ref
        self._blocks = set()  # keeps blocks alive until Firestore calls them

    # ---- filters: each one returns a new Query ----

    @staticmethod
    def _snapshot_of(document):
        if document._snapshot is None:
            raise ValueError(
                "This document has no data loaded. Use a document from a callback."
            )
        return document._snapshot

    def query_starting_at_document(self, document):
        return Query(self._ref.queryStartingAtDocument_(self._snapshot_of(document)))

    def query_starting_after_document(self, document):
        return Query(self._ref.queryStartingAfterDocument_(self._snapshot_of(document)))

    def query_ending_at_document(self, document):
        return Query(self._ref.queryEndingAtDocument_(self._snapshot_of(document)))

    def query_ending_before_document(self, document):
        return Query(self._ref.queryEndingBeforeDocument_(self._snapshot_of(document)))

    def query_starting_at_values(self, values):
        return Query(self._ref.queryStartingAtValues_(values))

    def query_starting_after_values(self, values):
        return Query(self._ref.queryStartingAfterValues_(values))

    def query_ending_at_values(self, values):
        return Query(self._ref.queryEndingAtValues_(values))

    def query_ending_before_values(self, values):
        return Query(self._ref.queryEndingBeforeValues_(values))

    def query_where_field_is_equal_to(self, field, value):
        return Query(self._ref.queryWhereField_isEqualTo_(field, value))

    def query_where_field_is_not_equal_to(self, field, value):
        return Query(self._ref.queryWhereField_isNotEqualTo_(field, value))

    def query_where_field_is_less_than(self, field, value):
        return Query(self._ref.queryWhereField_isLessThan_(field, value))

    def query_where_field_is_less_than_or_equal_to(self, field, value):
        return Query(self._ref.queryWhereField_isLessThanOrEqualTo_(field, value))

    def query_where_field_is_greater_than(self, field, value):
        return Query(self._ref.queryWhereField_isGreaterThan_(field, value))

    def query_where_field_is_greater_than_or_equal_to(self, field, value):
        return Query(self._ref.queryWhereField_isGreaterThanOrEqualTo_(field, value))

    def query_where_field_array_contains(self, field, value):
        return Query(self._ref.queryWhereField_arrayContains_(field, value))

    def query_where_field_in(self, field, values):
        return Query(self._ref.queryWhereField_in_(field, values))

    def query_where_field_not_in(self, field, values):
        return Query(self._ref.queryWhereField_notIn_(field, values))

    def query_where_filter(self, filter_):
        return Query(self._ref.queryWhereFilter_(filter_._filter))

    def query_limited_to(self, limit):
        return Query(self._ref.queryLimitedTo_(limit))

    def query_ordered_by_field(self, field, descending=False):
        if descending:
            return Query(self._ref.queryOrderedByField_descending_(field, True))
        return Query(self._ref.queryOrderedByField_(field))

    @property
    def count(self):
        return AggregateQuery(self._ref.count)

    def aggregate(self, fields):
        return AggregateQuery(self._ref.aggregate_([f._field for f in fields]))

    # ---- run the query ----

    def add_snapshot_listener(self, callback):
        def on_snapshot(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None

            if snapshot is None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return

            docs = [
                DocumentReference(document.reference, document)
                for document in snapshot.documents
            ]
            callback(docs, None)

        block = Block(on_snapshot, None, objc_id, objc_id)
        self._blocks.add(block)  # stays here until remove() is called

        registration = self._ref.addSnapshotListener_(block)
        return ListenerRegistration(registration, lambda: self._blocks.discard(block))

    def add_snapshot_listener_for_changes(self, callback):
        def on_snapshot(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None

            if snapshot is None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return

            changes = [DocumentChange(diff) for diff in snapshot.documentChanges]
            callback(changes, None)

        block = Block(on_snapshot, None, objc_id, objc_id)
        self._blocks.add(block)  # stays here until remove() is called

        registration = self._ref.addSnapshotListener_(block)
        return ListenerRegistration(registration, lambda: self._blocks.discard(block))

    def get_documents(self, callback):
        holder = {}

        def on_done(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if error is not None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return

            docs = [
                DocumentReference(document.reference, document)
                for document in snapshot.documents
            ]
            callback(docs, None)

        block = Block(on_done, None, objc_id, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.getDocumentsWithCompletion_(block)


class CollectionReference(Query):
    def add_document_with_data(self, data, callback=None):
        holder = {}

        def on_done(error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if callback is None:
                return
            if error:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
            else:
                callback(DocumentReference(holder["ref"]), None)

        block = Block(on_done, None, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        holder["ref"] = self._ref.addDocumentWithData_completion_(data, block)
        return DocumentReference(holder["ref"])

    def document_with_path(self, path):
        return DocumentReference(self._ref.documentWithPath_(path))

    def get_documents(self, callback):
        holder = {}

        def on_done(snapshot_ptr, error_ptr):
            snapshot = ObjCInstance(snapshot_ptr) if snapshot_ptr else None
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["block"])

            if error is not None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return

            docs = [
                DocumentReference(document.reference, document)
                for document in snapshot.documents
            ]
            callback(docs, None)

        block = Block(on_done, None, objc_id, objc_id)
        holder["block"] = block
        self._blocks.add(block)

        self._ref.getDocumentsWithCompletion_(block)


class Firestore:
    def __init__(self):
        self._db = FIRFirestore.firestore()
        self._blocks = set()

    def batch(self):
        return WriteBatch(self._db.batch)

    def collection_with_path(self, path):
        return CollectionReference(self._db.collectionWithPath_(path))

    def collection_group_with_id(self, collection_id):
        return Query(self._db.collectionGroupWithID_(collection_id))

    def document_with_path(self, path):
        return DocumentReference(self._db.documentWithPath_(path))

    def run_transaction(self, update_fn, callback=None):
        holder = {}

        def on_update(transaction_ptr, error_pointer):
            transaction = Transaction(ObjCInstance(transaction_ptr), error_pointer)
            try:
                result = update_fn(transaction)
            except TransactionException as e:
                if error_pointer[0].value is None:
                    error = NSError.errorWithDomain_code_userInfo_(
                        "AppErrorDomain",
                        -1,
                        {"NSLocalizedDescription": str(e)},
                    )
                    error_pointer[0] = error.ptr
                return None

            if result is None:
                return None
            holder["result"] = at(result)  # keep it alive
            return holder["result"].ptr

        def on_done(result_ptr, error_ptr):
            error = ObjCInstance(error_ptr) if error_ptr else None
            self._blocks.discard(holder["update"])
            self._blocks.discard(holder["done"])

            if callback is None:
                return
            if error is not None:
                underlying = error.userInfo.objectForKey_("NSUnderlyingError")
                if underlying is not None:
                    print("Underlying error:", underlying)
                error_msg = QueryDict(
                    {
                        "code": error.code,
                        "description": error.localizedDescription,
                        "underlying_error": underlying,
                    }
                )
                callback(None, error_msg)
                return
            result = ObjCInstance(result_ptr) if result_ptr else None
            callback(result, None)

        holder["update"] = Block(on_update, objc_id, objc_id, POINTER(objc_id))
        holder["done"] = Block(on_done, None, objc_id, objc_id)
        self._blocks.update([holder["update"], holder["done"]])

        self._db.runTransactionWithBlock_completion_(holder["update"], holder["done"])

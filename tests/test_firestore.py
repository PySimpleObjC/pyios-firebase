from ctypes import pointer

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import NSObject, ObjCInstance, objc_id

from pyios_firebase.firestore import (
    CollectionReference,
    DocumentReference,
    DocumentSnapshot,
    Firestore,
    Query,
    QuerySnapshot,
    TransactionException,
    WriteBatch,
)


def test_get_documents_success_and_error(blocks):
    ref, out = Recorder(), []
    Query(ref).get_documents(lambda s, e: out.append((s, e)))
    assert (
        len(blocks) == 1
    )  # alive until Firestore answers, even with no other reference

    fire(ref.block("getDocumentsWithCompletion_"), NSObject.new(), None)
    snapshot, error = out[-1]
    assert isinstance(snapshot, QuerySnapshot) and error is None
    assert not blocks

    Query(ref).get_documents(lambda s, e: out.append((s, e)))
    fire(ref.block(), None, make_error())
    assert out[-1][0] is None and out[-1][1].description == "permission denied"
    assert not blocks


def test_get_documents_with_source():
    ref = Recorder()
    Query(ref).get_documents(lambda s, e: None, source=2)
    assert (
        ref.calls[-1][0] == "getDocumentsWithSource_completion_" and ref.last()[0] == 2
    )


def test_document_get_gives_snapshot(blocks):
    ref, out = Recorder(), []
    DocumentReference(ref).get_document(lambda s, e: out.append((s, e)))
    fire(ref.block("getDocumentWithCompletion_"), NSObject.new(), None)
    assert isinstance(out[-1][0], DocumentSnapshot)
    assert not blocks


@pytest.mark.parametrize("callback", [None, "record"])
def test_writes_call_back_with_error(blocks, callback):
    ref, out = Recorder(), []
    cb = out.append if callback else None
    doc = DocumentReference(ref)
    doc.update_data({"a": 1}, cb)
    fire(ref.block("updateData_completion_"), None)
    doc.delete_document(cb)
    fire(ref.block("deleteDocumentWithCompletion_"), make_error())
    if callback:
        assert out[0] is None and out[1].code == 7
    assert not blocks


def test_set_data_forms():
    ref, out = Recorder(), []
    doc = DocumentReference(ref)

    doc.set_data({"a": 1})
    assert ref.calls[-1][0] == "setData_completion_"

    doc.set_data({"a": 1}, merge=True, callback=out.append)
    assert ref.calls[-1][0] == "setData_merge_completion_"

    # the 0.1 form: set_data(data, callback) must not turn into merge=True
    doc.set_data({"a": 1}, out.append)
    assert ref.calls[-1][0] == "setData_completion_"
    fire(ref.block(), None)
    assert out == [None]


def test_snapshot_listener_lifetime(blocks):
    registration = Recorder()
    ref, out = Recorder({"addSnapshotListener_": registration}), []
    listener = Query(ref).add_snapshot_listener(lambda s, e: out.append(e))
    block = ref.block("addSnapshotListener_")
    fire(block, None, make_error())
    fire(block, None, make_error())
    assert len(out) == 2 and block in blocks  # still alive between calls

    listener.remove()
    listener.remove()  # safe twice
    assert [c[0] for c in registration.calls] == ["remove"]
    assert not blocks


def test_snapshot_listener_options():
    ref = Recorder()
    DocumentReference(ref).add_snapshot_listener(
        lambda s, e: None, include_metadata_changes=True
    )
    assert ref.calls[-1][0] == "addSnapshotListenerWithIncludeMetadataChanges_listener_"


def test_add_document_gives_reference(blocks):
    new_ref = Recorder()
    ref, out = Recorder({"addDocumentWithData_completion_": new_ref}), []
    returned = CollectionReference(ref).add_document_with_data(
        {"a": 1}, lambda r, e: out.append((r, e))
    )
    fire(ref.block(), None)
    assert out[0][0] is returned and returned._ref is new_ref and out[0][1] is None
    assert not blocks


def test_start_after_document_needs_a_snapshot():
    with pytest.raises(ValueError, match="DocumentSnapshot"):
        Query(Recorder()).query_starting_after_document(DocumentReference(Recorder()))


def test_write_batch_chains():
    native = Recorder()
    a, b = DocumentReference(Recorder()), DocumentReference(Recorder())
    batch = WriteBatch(native)
    assert batch.set_data({}, a).update_data({"x": 1}, b).delete_document(a) is batch
    assert [c[0] for c in native.calls] == [
        "setData_forDocument_",
        "updateData_forDocument_",
        "deleteDocument_",
    ]


def _run_transaction(update_fn):
    db_native, out = Recorder(), []
    Firestore(db_native).run_transaction(update_fn, lambda r, e: out.append((r, e)))
    update_block, done_block = db_native.last("runTransactionWithBlock_completion_")
    return update_block, done_block, out


def test_transaction_passes_python_result(blocks):
    runs = []
    update, done, out = _run_transaction(
        lambda t: runs.append(1) or {"runs": len(runs)}
    )
    error_pointer = pointer(objc_id())
    fire(update, NSObject.new(), error_pointer)
    fire(update, NSObject.new(), error_pointer)  # Firestore retried
    assert blocks  # the update block lives until the end
    fire(done, None, None)
    assert out == [({"runs": 2}, None)]
    assert not blocks


@pytest.mark.parametrize(
    "exc", [TransactionException("too big"), ValueError("too big")]
)
def test_transaction_exception_sets_error(blocks, exc):
    def update_fn(transaction):
        raise exc

    update, done, out = _run_transaction(update_fn)
    error_pointer = pointer(objc_id())
    fire(update, NSObject.new(), error_pointer)
    assert str(ObjCInstance(error_pointer[0]).localizedDescription) == "too big"
    fire(done, None, ObjCInstance(error_pointer[0]))
    assert out[0][0] is None and out[0][1].description == "too big"
    assert not blocks


def test_transaction_keeps_firestore_error():
    firestore_error = make_error("aborted", 10)

    def update_fn(transaction):
        raise ValueError("mine")

    update, _, _ = _run_transaction(update_fn)
    error_pointer = pointer(objc_id(firestore_error.ptr.value))
    fire(update, NSObject.new(), error_pointer)
    assert str(ObjCInstance(error_pointer[0]).localizedDescription) == "aborted"


def test_use_emulator_sets_host_and_turns_tls_off():
    class Settings:
        sslEnabled = True

        def copy(self):
            copied = Settings()
            copied.sslEnabled = self.sslEnabled
            return copied

    class FakeDb:
        def __init__(self):
            self.settings = Settings()
            self.emulator = None

        def useEmulatorWithHost_port_(self, host, port):
            self.emulator = (host, port)

    db = FakeDb()
    original = db.settings
    Firestore(db).use_emulator("127.0.0.1", 8080)
    assert db.emulator == ("127.0.0.1", 8080)
    assert db.settings.sslEnabled is False
    # a new settings object is assigned: the SDK only applies settings on assignment
    assert db.settings is not original


class _CustomGetters:
    """Like Rubicon: Objective-C custom getters (getter=isX) are methods, so
    reading them without calling gives a bound method, which is truthy."""

    def __init__(self, **values):
        for name, value in values.items():
            setattr(self, name, lambda value=value: value)


@pytest.mark.parametrize("value", [True, False])
def test_snapshot_metadata_calls_custom_getters(value):
    from pyios_firebase.firestore import SnapshotMetadata

    metadata = SnapshotMetadata(
        _CustomGetters(isFromCache=value, hasPendingWrites=value)
    )
    assert metadata.is_from_cache is value
    assert metadata.has_pending_writes is value


@pytest.mark.parametrize("value", [True, False])
def test_query_snapshot_is_empty_calls_custom_getter(value):
    assert QuerySnapshot(_CustomGetters(isEmpty=value)).is_empty is value


# Objective-C properties with a custom getter in the SDK headers the package
# wraps. Rubicon only exposes them as methods: they must always be called.
CUSTOM_GETTERS = (
    "isFromCache",
    "hasPendingWrites",
    "isEmpty",
    "isSSLEnabled",
    "isKeyWindow",
)


def test_custom_getters_are_always_called():
    import pathlib
    import re

    package = pathlib.Path(__file__).parent.parent / "src" / "pyios_firebase"
    uncalled = re.compile(r"\.(" + "|".join(CUSTOM_GETTERS) + r")\b(?!\s*\()")
    offenders = [
        f"{path.relative_to(package)}:{number}: {line.strip()}"
        for path in package.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if uncalled.search(line.split("#", 1)[0])
    ]
    assert not offenders, "custom getters read without calling them:\n" + "\n".join(
        offenders
    )


# ---- in / not-in / array-contains-any value lists ---------------------------------

LIST_FILTERS = [
    ("query_where_field_in", "queryWhereField_in_", 30),
    ("query_where_field_array_contains_any", "queryWhereField_arrayContainsAny_", 30),
    ("query_where_field_not_in", "queryWhereField_notIn_", 10),
]


@pytest.mark.parametrize(("method", "selector", "limit"), LIST_FILTERS)
def test_list_filters_send_up_to_their_limit(method, selector, limit):
    ref = Recorder()
    getattr(Query(ref), method)("country", ["v"] * limit)
    name, (field, values) = ref.calls[-1]
    assert (name, field, len(values)) == (selector, "country", limit)
    getattr(Query(ref), method)("country", ("USA", "Japan"))  # a tuple is a list too
    assert len(ref.calls[-1][1][1]) == 2


@pytest.mark.parametrize(("method", "selector", "limit"), LIST_FILTERS)
def test_list_filters_raise_instead_of_aborting(method, selector, limit):
    ref = Recorder()
    query = getattr(Query(ref), method)
    with pytest.raises(ValueError, match="need at least one value"):
        query("country", [])  # the SDK raises an Objective-C exception: the app aborts
    with pytest.raises(ValueError, match=f"at most {limit} values, not {limit + 1}"):
        query("country", ["v"] * (limit + 1))
    with pytest.raises(TypeError, match="take a list of values, not str"):
        query("country", "USA")  # the SDK asserts the value is an array
    with pytest.raises(TypeError, match="take a list of values, not int"):
        query("country", 3)
    assert not ref.calls  # nothing reached the SDK


@pytest.mark.parametrize(
    ("method", "selector", "limit"),
    [
        ("filter_where_field_in", "filterWhereField_in_", 30),
        (
            "filter_where_field_array_contains_any",
            "filterWhereField_arrayContainsAny_",
            30,
        ),
        ("filter_where_field_not_in", "filterWhereField_notIn_", 10),
    ],
)
def test_filter_lists_are_checked_too(monkeypatch, method, selector, limit):
    from pyios_firebase.firestore import Filter

    fake = Recorder()
    monkeypatch.setattr("pyios_firebase.firestore.filter._fir_filter", lambda: fake)
    getattr(Filter, method)("country", ["v"] * limit)
    assert fake.calls[-1][0] == selector
    for bad in ([], ["v"] * (limit + 1)):
        with pytest.raises(ValueError):
            getattr(Filter, method)("country", bad)
    with pytest.raises(TypeError):
        getattr(Filter, method)("country", "USA")
    assert len(fake.calls) == 1


# ---- query checks the SDK would abort the app on -----------------------------------


class FakeQueryNative(Recorder):
    """A native FIRQuery: records calls, and every query... call returns itself."""

    def __getattr__(self, name):
        method = super().__getattr__(name)
        if not name.startswith("query"):
            return method

        def query_method(*args):
            method(*args)
            return self

        return query_method


def cities():
    from pyios_firebase.firestore import CollectionReference

    return CollectionReference(FakeQueryNative())


class FakeDocumentSnapshot(DocumentSnapshot):
    """A DocumentSnapshot with the data a cursor reads."""

    def __init__(self, data, exists=True, estimated=None, pending=False):
        self._snapshot = object()  # what _snapshot_of checks
        self._data, self._exists = data, exists
        self._estimated = estimated if estimated is not None else data
        self._pending = pending

    @property
    def exists(self):
        return self._exists

    @property
    def data(self):
        return self._data

    def data_with_server_timestamp_behavior(self, behavior):
        return self._estimated

    @property
    def metadata(self):
        from types import SimpleNamespace

        return SimpleNamespace(has_pending_writes=self._pending)


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (
            lambda q: q.query_where_field_not_in("a", [1]).query_where_field_not_in(
                "b", [2]
            ),
            "more than one 'not-in'",
        ),
        (
            lambda q: q.query_where_field_in("a", [1]).query_where_field_not_in(
                "b", [2]
            ),
            "combine 'not-in' and 'in'",
        ),
        (
            lambda q: q.query_where_field_not_in(
                "a", [1]
            ).query_where_field_array_contains_any("b", [2]),
            "combine 'array-contains-any' and 'not-in'",
        ),
        (
            lambda q: q.query_where_field_is_not_equal_to(
                "a", 1
            ).query_where_field_not_in("b", [2]),
            "combine 'not-in' and '!='",
        ),
        (
            lambda q: q.query_where_field_is_not_equal_to(
                "a", 1
            ).query_where_field_is_not_equal_to("b", 2),
            "more than one '!='",
        ),
        (lambda q: q.query_limited_to(0), "at least 1, not 0"),
        (lambda q: q.query_limited_to_last(-5), "at least 1, not -5"),
        (
            lambda q: (
                q.query_ordered_by_field("a")
                .query_starting_at_values([1])
                .query_ordered_by_field("b")
            ),
            "order the query before giving it a start point",
        ),
        (
            lambda q: (
                q.query_ordered_by_field("a")
                .query_ending_before_values([1])
                .query_ordered_by_field("b")
            ),
            "before giving it an end point",
        ),
        (
            lambda q: q.query_starting_at_values([1]),
            "one value per ordered field: 1 values for 0",
        ),
        (
            lambda q: q.query_ordered_by_field("a").query_ending_at_values([1, 2]),
            "2 values for 1",
        ),
    ],
)
def test_query_mistakes_raise_instead_of_aborting(build, message):
    with pytest.raises(ValueError, match=message):
        build(cities())


def test_conflicts_inside_composite_filters_are_found(monkeypatch):
    from pyios_firebase.firestore import Filter

    monkeypatch.setattr(
        "pyios_firebase.firestore.filter._fir_filter", lambda: FakeQueryNative()
    )
    either = Filter.or_filter_with_filters(
        [
            Filter.filter_where_field_not_in("a", [1]),
            Filter.filter_where_field_is_equal_to("b", 2),
        ]
    )
    assert [op for op, _ in either._parts] == ["not-in", "=="]
    with pytest.raises(ValueError, match="combine 'not-in' and 'in'"):
        cities().query_where_field_in("c", [3]).query_where_filter(either)
    with pytest.raises(ValueError, match="more than one 'not-in'"):
        cities().query_where_filter(
            Filter.and_filter_with_filters(
                [either, Filter.filter_where_field_not_in("d", [4])]
            )
        )


def test_what_the_sdk_allows_still_works():
    q = cities()
    q.query_where_field_in("a", [1]).query_where_field_in("b", [2])  # two "in"
    q.query_where_field_array_contains_any("a", [1]).query_where_field_in("b", [2])
    q.query_where_field_is_less_than("a", 1).query_where_field_is_greater_than("b", 2)
    q.query_ordered_by_field("a").query_ordered_by_field("b").query_starting_at_values(
        [1, 2]
    )
    q.query_ordered_by_field("a").query_starting_after_values(
        [1]
    ).query_ending_before_values([5])
    q.query_limited_to(1).query_limited_to_last(2_147_483_647)


def test_limit_to_last_needs_an_order_when_it_runs(blocks):
    with pytest.raises(ValueError, match="needs a query_ordered_by_field"):
        cities().query_limited_to_last(3).get_documents(lambda s, e: None)
    with pytest.raises(ValueError, match="needs a query_ordered_by_field"):
        cities().query_limited_to_last(3).add_snapshot_listener(lambda s, e: None)
    assert not blocks  # nothing was started
    q = (
        cities().query_limited_to_last(3).query_ordered_by_field("a")
    )  # order after: fine
    q.get_documents(lambda s, e: None)
    cities().query_limited_to_last(3).query_limited_to(3).get_documents(
        lambda s, e: None
    )
    blocks.clear()


def test_document_cursors_check_the_document():
    ordered = cities().query_ordered_by_field("population")
    ordered.query_starting_after_document(FakeDocumentSnapshot({"population": 10}))
    with pytest.raises(ValueError, match="does not exist"):
        ordered.query_starting_at_document(FakeDocumentSnapshot({}, exists=False))
    with pytest.raises(ValueError, match="no 'population' field"):
        ordered.query_ending_at_document(FakeDocumentSnapshot({"name": "x"}))
    with pytest.raises(ValueError, match="server timestamp not written yet"):
        cities().query_ordered_by_field("updated").query_starting_after_document(
            FakeDocumentSnapshot(
                {"updated": None}, estimated={"updated": 1}, pending=True
            )
        )
    # an inequality filter's field is ordered too (the SDK's normalized order)
    with pytest.raises(ValueError, match="no 'age' field"):
        cities().query_where_field_is_greater_than(
            "age", 3
        ).query_starting_after_document(FakeDocumentSnapshot({"name": "x"}))
    nested = cities().query_ordered_by_field("stats.score")
    nested.query_starting_after_document(
        FakeDocumentSnapshot({"stats": {"score": None}})
    )


def test_huge_limits_mean_no_limit_as_in_the_sdk(blocks):
    # the SDK saturates limits >= INT32_MAX to "no limit" (SaturatedLimitValue)
    for huge in (2**31 - 1, 3_000_000_000, 2**80):
        native = FakeQueryNative()
        from pyios_firebase.firestore import CollectionReference

        CollectionReference(native).query_limited_to(huge)
        assert native.calls[-1] == ("queryLimitedTo_", (2**31 - 1,))  # fits NSInteger
    # a "no limit" limit_to_last needs no order, as in the SDK
    cities().query_limited_to_last(2**31 - 1).get_documents(lambda s, e: None)
    cities().query_limited_to_last(2**40).add_snapshot_listener(lambda s, e: None)
    blocks.clear()


def test_queries_from_native_ones_are_not_checked():
    # QuerySnapshot.query has no history: nothing must be refused there
    q = Query(FakeQueryNative())
    q.query_starting_at_values([1, 2, 3]).query_ordered_by_field("a")
    q.query_where_field_not_in("a", [1]).query_where_field_not_in("b", [2])
    with pytest.raises(ValueError):
        q.query_limited_to(0)  # a bad limit is bad everywhere

import math
from datetime import UTC, datetime

import pytest
from conftest import FIRMutableData, fire, make_error
from rubicon.objc import ObjCClass, ns_from_py

from pyios_firebase.database import (
    DATABASE_ERROR_DOMAIN,
    TRANSACTION_ERROR_DOMAIN,
    DatabaseErrorCode,
    DatabaseQuery,
    DatabaseReference,
    DataEventType,
    DataSnapshot,
    MutableData,
    ServerValue,
    TransactionResult,
    to_database,
)
from pyios_firebase.database.values import (
    to_priority,
    validate_key,
    validate_path,
    validate_root_path,
)
from pyios_firebase.util import to_python

URL = "http://127.0.0.1:9000/rooms/general?ns=demo"


class FakeRef:
    """A native query or reference: records calls; narrowing returns itself."""

    def __init__(self, url=URL):
        self.calls = []
        self.URL = url
        self.key = url.split("?")[0].rsplit("/", 1)[-1]
        self.ref = self
        self.next_handle = 6

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args):
            self.calls.append((name, args))
            if name.startswith("query"):
                return self
            if name.startswith("observeEventType"):
                self.next_handle += 1
                return self.next_handle
            if name == "child_":
                return FakeRef(URL.replace("?", f"/{args[0]}?"))
            return None

        return method

    def names(self):
        return [name for name, _ in self.calls]


def snapshot_native(value, key="k"):
    class Native:
        pass

    native = Native()
    native.value = to_database(value)
    native.key = key
    return native


# ---- values -----------------------------------------------------------------------


def test_to_database_converts_python_values():
    value = {
        "s": "hi",
        "n": 3,
        "f": 1.5,
        "b": True,
        "none": None,
        "list": [1, (2, 3)],
        "sent": ServerValue.timestamp(),
        ".priority": 2,
    }
    back = to_python(to_database(value))
    assert back == {**value, "list": [1, [2, 3]]}
    assert back["b"] is True


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        (
            {"at": datetime.now(UTC)},
            TypeError,
            r"at: the Realtime Database has no date",
        ),
        ({"blob": b"x"}, TypeError, "no bytes type"),
        ({"s": {1}}, TypeError, "cannot store a set"),
        ({1: "x"}, TypeError, "keys must be str"),
        ({"a.b": 1}, ValueError, r"invalid key at a\.b"),
        ({"x": {"a/b": 1}}, ValueError, "invalid key"),
        ({"": 1}, ValueError, "invalid key"),
        ({"n": math.nan}, ValueError, "n: cannot store nan"),
        ([1, math.inf], ValueError, r"1: cannot store inf"),
        ({".sv": "timestamp", "other": 1}, ValueError, "server value cannot have"),
    ],
)
def test_to_database_refuses_what_would_abort_the_app(value, error, message):
    with pytest.raises(error, match=message):
        to_database(value)


def test_server_values():
    assert ServerValue.timestamp() == {".sv": "timestamp"}
    assert ServerValue.increment(2) == {".sv": {"increment": 2}}
    with pytest.raises(TypeError):
        ServerValue.increment(True)
    with pytest.raises(ValueError):
        ServerValue.increment(math.nan)


def test_paths_and_keys():
    validate_path("users/ada")
    validate_key("ada")
    validate_root_path(".info/connected")
    validate_root_path("/.info")
    for bad in ("", "a.b", "a#", "a$", "a[0]"):
        with pytest.raises(ValueError):
            validate_path(bad)
    with pytest.raises(ValueError):
        validate_key("a/b")
    with pytest.raises(ValueError):
        validate_root_path("x/.info")
    with pytest.raises(TypeError):
        validate_path(3)


def test_priorities():
    assert to_python(to_priority(2)) == 2
    assert to_python(to_priority("a")) == "a"
    assert to_python(to_priority(ServerValue.timestamp())) == {".sv": "timestamp"}
    with pytest.raises(TypeError):
        to_priority(True)
    with pytest.raises(TypeError):
        to_priority({"a": 1})


# ---- queries ----------------------------------------------------------------------


def test_query_methods_call_the_sdk():
    native = FakeRef()
    query = (
        DatabaseQuery(native)
        .order_by_child("stats/score")
        .start_at(10, "k1")
        .end_before(100)
        .limit_to_last(5)
    )
    assert isinstance(query, DatabaseQuery)
    assert native.names() == [
        "queryOrderedByChild_",
        "queryStartingAtValue_childKey_",
        "queryEndingBeforeValue_",
        "queryLimitedToLast_",
    ]
    assert native.calls[1][1][1] == "k1"


@pytest.mark.parametrize(
    ("build", "error", "message"),
    [
        (lambda q: q.order_by_key().order_by_value(), ValueError, "ordered only once"),
        (lambda q: q.order_by_child("$key"), ValueError, "use order_by_key"),
        (lambda q: q.order_by_child("/"), ValueError, "needs a path"),
        (lambda q: q.limit_to_first(0), ValueError, "1 to"),
        (lambda q: q.limit_to_last(2**31), ValueError, "1 to"),
        (lambda q: q.limit_to_first(True), TypeError, "takes an int"),
        (
            lambda q: q.limit_to_first(1).limit_to_last(1),
            ValueError,
            "already has a limit",
        ),
        (lambda q: q.start_at(1).start_after(2), ValueError, "already has a start"),
        (lambda q: q.end_at(1).end_before(2), ValueError, "already has an end"),
        (lambda q: q.start_at(1).equal_to(2), ValueError, "already has a start"),
        (lambda q: q.order_by_key().start_at(1), TypeError, "must be str"),
        (lambda q: q.start_at(1).order_by_key(), TypeError, "must be str"),
        (lambda q: q.order_by_key().equal_to("a", "k"), ValueError, "child key"),
        (lambda q: q.start_at("a", "k").order_by_key(), ValueError, "child key"),
        (lambda q: q.order_by_priority().start_at(True), TypeError, "cannot be bool"),
        (lambda q: q.start_at(1, "a/b"), ValueError, "invalid child key"),
        (lambda q: q.start_at([1]), TypeError, "query values must be"),
        (lambda q: q.equal_to(math.nan), ValueError, "cannot query by nan"),
    ],
)
def test_query_misuse_raises_instead_of_aborting(build, error, message):
    native = FakeRef()
    with pytest.raises(error, match=message):
        build(DatabaseQuery(native))


def test_observe_value_and_child_events(blocks):
    native, events = FakeRef(), []
    query = DatabaseQuery(native)
    observer = query.observe(DataEventType.VALUE, lambda s, p: events.append((s, p)))
    assert native.calls[-1][0] == "observeEventType_withBlock_withCancelBlock_"
    event_type, block, _cancel = native.calls[-1][1]
    assert event_type == DataEventType.VALUE
    fire(block, ns_from_py("ignored"))
    snapshot, previous = events[-1]
    assert isinstance(snapshot, DataSnapshot) and previous is None

    query.observe(DataEventType.CHILD_ADDED, lambda s, p: events.append((s, p)))
    name, (event_type, block, _cancel) = native.calls[-1]
    assert name == "observeEventType_andPreviousSiblingKeyWithBlock_withCancelBlock_"
    fire(block, ns_from_py("x"), ns_from_py("before"))
    assert events[-1][1] == "before"
    assert len(blocks) == 4  # two observers: event and cancel blocks each

    observer.remove()
    observer.remove()  # safe twice
    assert native.calls[-1] == ("removeObserverWithHandle_", (7,))
    assert len(blocks) == 2
    query.remove_all_observers()
    assert not blocks
    with pytest.raises(ValueError):
        query.observe(9, lambda s, p: None)


def test_cancelled_observer_releases_its_blocks(blocks):
    native, errors = FakeRef(), []
    DatabaseQuery(native).observe(DataEventType.VALUE, lambda s, p: None, errors.append)
    _type, _block, cancel = native.calls[-1][1]
    fire(cancel, make_error("Permission Denied", 1, DATABASE_ERROR_DOMAIN))
    assert errors[0].name == "PERMISSION_DENIED"
    assert errors[0].code == DatabaseErrorCode.PERMISSION_DENIED
    assert not blocks


def test_observe_once_and_get_data(blocks):
    native, got = FakeRef(), []
    query = DatabaseQuery(native)
    query.observe_once(DataEventType.VALUE, lambda s, p: got.append(s))
    fire(native.calls[-1][1][1], ns_from_py("v"))
    assert len(got) == 1 and not blocks

    query.get_data(lambda s, e: got.append((s, e)))
    fire(native.calls[-1][1][-1], make_error("offline", 2, "com.firebase.core"), None)
    snapshot, error = got[-1]
    assert snapshot is None and error.name == "" and not blocks


def test_snapshots_give_python_values():
    snapshot = DataSnapshot(snapshot_native({"a": 1, "b": [True, None]}))
    assert snapshot.value == {"a": 1, "b": [True, None]}
    assert snapshot.key == "k"


def test_keep_synced_refuses_info():
    with pytest.raises(ValueError, match=r"\.info"):
        DatabaseQuery(FakeRef("http://h/.info/connected?ns=x")).keep_synced(True)


# ---- references and writes -----------------------------------------------------------


def test_reference_paths_and_children():
    native = FakeRef()
    ref = DatabaseReference(native)
    assert ref.path == "/rooms/general"
    assert ref.key == "general"
    assert ref.child("messages").path == "/rooms/general/messages"
    with pytest.raises(ValueError):
        ref.child("a.b")
    assert ref == DatabaseReference(FakeRef())


def test_writes(blocks):
    native, errors = FakeRef(), []
    ref = DatabaseReference(native)
    ref.set_value({"text": "hi"}, errors.append)
    name, (value, block) = native.calls[-1]
    assert name == "setValue_withCompletionBlock_"
    assert to_python(value) == {"text": "hi"}
    fire(block, None, None)
    assert errors == [None] and not blocks

    ref.set_value(1, priority=2)
    assert native.calls[-1][0] == "setValue_andPriority_withCompletionBlock_"
    ref.update_child_values({"a/b": 1, "c": None})
    name, (values, _block) = native.calls[-1]
    assert name == "updateChildValues_withCompletionBlock_"
    assert to_python(values) == {"a/b": 1, "c": None}
    with pytest.raises(ValueError):
        ref.update_child_values({"a.b": 1})
    ref.remove_value()
    ref.set_priority("p")
    assert native.names()[-2:] == [
        "removeValueWithCompletionBlock_",
        "setPriority_withCompletionBlock_",
    ]
    blocks.clear()


@pytest.mark.parametrize(
    "values",
    [
        {"posts/p1": {"t": 1}, "posts/p1/updated_at": 2},
        {"a": 1, "/a": 2},
        {"a": 1, "a/": 2},
        {"/": {"a": 1}, "b": 2},
    ],
)
def test_update_paths_cannot_overlap(values, blocks):
    native = FakeRef()
    with pytest.raises(ValueError, match="at or below"):
        DatabaseReference(native).update_child_values(values)
    with pytest.raises(ValueError, match="at or below"):
        DatabaseReference(native).on_disconnect().update_child_values(values)
    assert not native.calls
    DatabaseReference(native).update_child_values({"posts/p1": 1, "posts/p10": 2})
    blocks.clear()


def test_writes_under_info_raise():
    ref = DatabaseReference(FakeRef("http://h/.info/connected?ns=x"))
    for write in (
        lambda: ref.set_value(1),
        ref.remove_value,
        lambda: ref.update_child_values({"a": 1}),
        lambda: ref.run_transaction(TransactionResult.success),
    ):
        with pytest.raises(ValueError, match="read-only"):
            write()


def test_on_disconnect(blocks):
    native = FakeRef()
    disconnect = DatabaseReference(native).on_disconnect()
    disconnect.set_value("offline")
    disconnect.set_value("offline", priority=1)
    disconnect.update_child_values({"state": "offline"})
    disconnect.remove_value()
    disconnect.cancel()
    assert native.names() == [
        "onDisconnectSetValue_withCompletionBlock_",
        "onDisconnectSetValue_andPriority_withCompletionBlock_",
        "onDisconnectUpdateChildValues_withCompletionBlock_",
        "onDisconnectRemoveValueWithCompletionBlock_",
        "cancelDisconnectOperationsWithCompletionBlock_",
    ]
    blocks.clear()


def _transaction(update):
    native, out = FakeRef(), []
    DatabaseReference(native).run_transaction(update, lambda *a: out.append(a))
    name, (update_block, done_block, local) = native.calls[-1]
    assert name == "runTransactionBlock_andCompletionBlock_withLocalEvents_"
    assert local is True
    return update_block, done_block, out


def test_transaction_success(blocks):
    def add_one(data):
        data.value = (data.value or 0) + 1
        return TransactionResult.success(data)

    update_block, done_block, out = _transaction(add_one)
    data = FIRMutableData.alloc().init()
    data.value = ns_from_py(41)
    result_ptr = fire(update_block, data)
    result = ObjCClass("FIRTransactionResult")(result_ptr)
    assert result.aborted == 0 and result.value.value == data.value
    assert to_python(data.value) == 42
    fire(done_block, None, True, data)
    error, committed, snapshot = out[0]
    assert error is None and committed is True and isinstance(snapshot, DataSnapshot)
    assert not blocks


def test_transaction_that_raises_is_aborted_with_the_error(blocks):
    def broken(data):
        raise RuntimeError("bad data")

    update_block, done_block, out = _transaction(broken)
    data = FIRMutableData.alloc().init()
    result = ObjCClass("FIRTransactionResult")(fire(update_block, data))
    assert result.aborted == 1
    fire(done_block, None, False, None)
    error, committed, snapshot = out[0]
    assert committed is False and snapshot is None
    assert error.domain == TRANSACTION_ERROR_DOMAIN
    assert "RuntimeError: bad data" in error.description
    assert not blocks


def test_transaction_must_return_a_result(blocks):
    update_block, done_block, out = _transaction(lambda data: data)
    fire(update_block, FIRMutableData.alloc().init())
    fire(done_block, None, False, None)
    assert "must return TransactionResult" in out[0][0].description
    blocks.clear()


def test_mutable_data_checks_values():
    data = MutableData(FIRMutableData.alloc().init())
    data.value = {"a": [1, 2]}
    assert data.value == {"a": [1, 2]}
    with pytest.raises(TypeError):
        data.value = {"at": datetime.now(UTC)}
    with pytest.raises(TypeError):
        data.priority = True

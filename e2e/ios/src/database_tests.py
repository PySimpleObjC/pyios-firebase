"""Realtime Database end-to-end tests, against the Database emulator.

Every test writes under ``e2e/<run id>/``. ``e2e_private`` is closed by the
rules (e2e/database.rules.json), for the permission tests.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from firestore_tests import RUN_ID
from kivy.clock import Clock
from runner import TestContext, expect, expect_equal

from pyios_firebase.database import (
    DataEventType,
    Database,
    DatabaseErrorCode,
    ServerValue,
    TransactionResult,
)


def root():
    return Database.database().reference(f"e2e/{RUN_ID}")


def test_database_values_round_trip(t: TestContext) -> None:
    ref = root().child("values")
    value = {
        "text": "héllo ✓",
        "int": 42,
        "big": 2**40,
        "float": 1.25,
        "yes": True,
        "no": False,
        "list": ["a", "b", {"c": 1}],
        "nested": {"deep": {"er": "x"}},
    }

    def read(snapshot, error) -> None:
        expect(error is None, error)
        got = snapshot.value
        expect_equal(got, value, "the same values back")
        expect(got["yes"] is True and got["no"] is False, "bools stay bools")
        expect(type(got["int"]) is int and type(got["float"]) is float, "number types")
        expect_equal(snapshot.key, "values", "key")
        expect_equal(snapshot.children_count, len(value), "children")
        expect(snapshot.has_child("nested/deep/er"), "has_child with a path")
        expect_equal(snapshot.child("nested/deep").value, {"er": "x"}, "child snapshot")
        expect_equal(sorted(child.key for child in snapshot), sorted(value), "iteration")
        t.passed()

    def written(error) -> None:
        expect(error is None, error)
        ref.get_data(t.step(read))

    ref.set_value(value, t.step(written))


def test_database_listeners(t: TestContext) -> None:
    messages = root().child("messages")
    added: list[tuple[str, Any, str | None]] = []
    changed: list[Any] = []
    removed: list[str] = []
    values: list[Any] = []
    keys: list[str] = []
    observers = []

    def on_added(snapshot, previous) -> None:
        added.append((snapshot.key, snapshot.value["n"], previous))
        if len(added) == 3:
            expect_equal([a[1] for a in added], [1, 2, 3], "in order")
            expect_equal(added[1][2], added[0][0], "previous key")
            messages.child(keys[1]).update_child_values({"n": 20})

    def on_changed(snapshot, previous) -> None:
        changed.append(snapshot.value["n"])
        messages.child(keys[0]).remove_value()

    def on_removed(snapshot, previous) -> None:
        removed.append(snapshot.key)
        Clock.schedule_once(lambda dt: check(), 0.2)

    def on_value(snapshot, previous) -> None:
        values.append(snapshot.children_count)

    def check() -> None:
        expect_equal(changed, [20], "child changed")
        expect_equal(removed, [keys[0]], "child removed")
        expect(values and values[-1] == 2, f"value events, last count: {values}")
        for observer in observers:
            observer.remove()
        before = len(values)
        messages.child_by_auto_id().set_value({"n": 4}, t.step(lambda e: after(before)))

    def after(before: int) -> None:
        Clock.schedule_once(t.step(lambda dt: finish(before)), 0.3)

    def finish(before: int) -> None:
        expect_equal(len(values), before, "no events after remove()")
        t.passed()

    ordered = messages.order_by_child("n")
    observers.append(ordered.observe(DataEventType.CHILD_ADDED, t.step(on_added)))
    observers.append(messages.observe(DataEventType.CHILD_CHANGED, t.step(on_changed)))
    observers.append(messages.observe(DataEventType.CHILD_REMOVED, t.step(on_removed)))
    observers.append(messages.observe(DataEventType.VALUE, t.step(on_value)))
    for n in (1, 2, 3):
        child = messages.child_by_auto_id()
        keys.append(child.key)
        # no server timestamp here: resolving it would be one more change event
        child.set_value({"n": n})
    expect(keys == sorted(keys), "auto IDs sort by creation time")


def test_database_queries(t: TestContext) -> None:
    scores = root().child("scores")
    data = {
        "ada": {"score": 90, "team": "red"},
        "bob": {"score": 50, "team": "blue"},
        "cy": {"score": 70, "team": "red"},
        "dee": {"score": 70, "team": "blue"},
        "eve": {"score": 10, "team": "red"},
    }
    checks = [
        ("top two by score", scores.order_by_child("score").limit_to_last(2), ["dee", "ada"]),
        ("50 to 70", scores.order_by_child("score").start_at(50).end_at(70), ["bob", "cy", "dee"]),
        ("after 70/cy", scores.order_by_child("score").start_after(70, "cy"), ["dee", "ada"]),
        ("before 50", scores.order_by_child("score").end_before(50), ["eve"]),
        ("equal 70", scores.order_by_child("score").equal_to(70), ["cy", "dee"]),
        ("keys b..d", scores.order_by_key().start_at("b").end_at("d"), ["bob", "cy"]),
        ("first two keys", scores.order_by_key().limit_to_first(2), ["ada", "bob"]),
        ("team red", scores.order_by_child("team").equal_to("red"), ["ada", "cy", "eve"]),
    ]
    pending = list(checks)

    def next_check() -> None:
        if not pending:
            t.passed()
            return
        name, query, expected = pending.pop(0)

        def got(snapshot, error) -> None:
            expect(error is None, f"{name}: {error}")
            expect_equal([child.key for child in snapshot], expected, name)
            next_check()

        query.get_data(t.step(got))

    def written(error) -> None:
        expect(error is None, error)
        next_check()

    scores.set_value(data, t.step(written))


def test_database_updates_and_server_values(t: TestContext) -> None:
    base = root().child("fanout")
    before = int(time.time() * 1000)

    def read(snapshot, error) -> None:
        expect(error is None, error)
        value = snapshot.value
        expect_equal(value["posts"]["p1"]["title"], "Hi", "first path")
        expect_equal(value["user-posts"]["ada"]["p1"]["title"], "Hi", "second path")
        expect("old" not in value["posts"], "None deletes")
        stamp = value["posts"]["p1"]["at"]
        expect(type(stamp) is int and abs(stamp - before) < 60_000, f"timestamp {stamp}")
        expect_equal(value["likes"], 3, "increments")
        t.passed()

    def updated(error) -> None:
        expect(error is None, error)
        likes = base.child("likes")
        likes.set_value(ServerValue.increment(2), t.step(
            lambda e: likes.set_value(ServerValue.increment(1), t.step(
                lambda e2: base.get_data(t.step(read))))))

    def seeded(error) -> None:
        expect(error is None, error)
        post = {"title": "Hi", "at": ServerValue.timestamp()}
        base.update_child_values(
            {"posts/p1": post, "user-posts/ada/p1": post, "posts/old": None},
            t.step(updated),
        )

    base.set_value({"posts": {"old": {"title": "gone"}}}, t.step(seeded))


def test_database_transactions(t: TestContext) -> None:
    counter = root().child("counter")
    done: list[bool] = []

    def add_one(data):
        data.value = (data.value or 0) + 1
        return TransactionResult.success(data)

    def check() -> None:
        def read(snapshot, error) -> None:
            expect_equal(snapshot.value, 2, "both increments applied")
            abort_test()

        counter.get_data(t.step(read))

    def committed(error, ok, snapshot) -> None:
        expect(error is None and ok, f"committed: {error}")
        done.append(ok)
        if len(done) == 2:
            check()

    def abort_test() -> None:
        def aborted(error, ok, snapshot) -> None:
            expect(error is None and not ok, f"aborted: {error} {ok}")
            # an abort on the first run reports the local data: with no listener
            # on the counter, the SDK has none cached yet
            expect(snapshot is None or snapshot.value in (None, 2), f"snapshot {snapshot}")
            raising_test()

        counter.run_transaction(lambda data: TransactionResult.abort(), t.step(aborted))

    def raising_test() -> None:
        def broken(data):
            raise ValueError("bad state")

        def failed(error, ok, snapshot) -> None:
            expect(not ok and error is not None, "the error reaches the callback")
            expect("ValueError: bad state" in error.description, error.description)
            t.passed()

        counter.run_transaction(broken, t.step(failed))

    counter.run_transaction(add_one, t.step(committed))
    counter.run_transaction(add_one, t.step(committed), local_events=False)


def test_database_priorities_and_export(t: TestContext) -> None:
    ref = root().child("prio")

    def read(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal([child.key for child in snapshot], ["b", "a"], "ordered by priority")
        expect_equal(snapshot.child("a").priority, 2, "priority")
        exported = snapshot.export_value()
        expect_equal(exported["a"], {".value": "first", ".priority": 2}, "export format")
        t.passed()

    def written(error) -> None:
        expect(error is None, error)
        ref.child("b").set_priority(1, t.step(
            lambda e: ref.order_by_priority().get_data(t.step(read))))

    ref.set_value({"a": "first", "b": "second"}, t.step(
        lambda e: ref.child("a").set_priority(2, t.step(written))))


def test_database_permission_denied(t: TestContext) -> None:
    private = Database.database().reference("e2e_private/secret")

    def cancelled(error) -> None:
        expect_equal(error.code, DatabaseErrorCode.PERMISSION_DENIED, "listener cancelled")
        expect_equal(error.name, "PERMISSION_DENIED", "name")
        t.passed()

    def written(error) -> None:
        expect(error is not None, "the write is refused")
        expect_equal(error.name, "PERMISSION_DENIED", "write error")
        private.observe(DataEventType.VALUE, t.step(lambda s, p: t.fail("read allowed")),
                        t.step(cancelled))

    private.set_value("x", t.step(written))


def test_database_validation_raises_instead_of_aborting(t: TestContext) -> None:
    ref = root().child("validation")
    for name, call, error in [
        ("bad key", lambda: ref.set_value({"a.b": 1}), ValueError),
        ("bad path", lambda: ref.child("a#b"), ValueError),
        ("datetime", lambda: ref.set_value({"at": datetime.now(UTC)}), TypeError),
        ("nan", lambda: ref.set_value(float("nan")), ValueError),
        ("two orders", lambda: ref.order_by_key().order_by_value(), ValueError),
        ("limit 0", lambda: ref.limit_to_first(0), ValueError),
        ("key + int", lambda: ref.order_by_key().start_at(1), TypeError),
        ("info write", lambda: Database.database().reference(".info/x").set_value(1), ValueError),
    ]:
        try:
            call()
        except error:
            continue
        raise AssertionError(f"{name}: no {error.__name__}")
    t.passed()


def test_database_connection_and_on_disconnect(t: TestContext) -> None:
    db = Database.database()
    presence = root().child("presence")
    states: list[bool] = []
    observer = db.reference(".info/connected").observe(
        DataEventType.VALUE, t.step(lambda s, p: states.append(bool(s.value)))
    )

    def queued(error) -> None:
        expect(error is None, error)
        db.go_offline()
        Clock.schedule_once(t.step(lambda dt: reconnect()), 0.5)

    def reconnect() -> None:
        db.go_online()
        Clock.schedule_once(t.step(lambda dt: presence.get_data(t.step(read))), 1.0)

    def read(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal(snapshot.value, "offline", "the server ran the on-disconnect write")
        expect(True in states and False in states, f".info/connected changed: {states}")
        observer.remove()
        t.passed()

    def online(error) -> None:
        expect(error is None, error)
        presence.on_disconnect().set_value("offline", t.step(queued))

    presence.set_value("online", t.step(online))


TESTS = [
    (name, fn) for name, fn in globals().items() if name.startswith("test_database")
]

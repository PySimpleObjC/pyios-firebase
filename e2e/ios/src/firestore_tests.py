"""End-to-end Firestore tests: the real Firebase iOS SDK against the emulator.

Every run writes under ``e2e_runs/{RUN_ID}``, so runs never see each other's data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from pyios_firebase.firestore import (
    AggregateField,
    DocumentChange,
    FieldValue,
    Filter,
    FIRAggregateSource,
    FIRFirestoreSource,
    Firestore,
    TransactionException,
)
from runner import TestContext, expect, expect_equal

RUN_ID = uuid.uuid4().hex[:12]
WHEN = datetime(2026, 11, 11, 9, 30, 15, 123456, tzinfo=UTC)


def db() -> Firestore:
    return Firestore.firestore()


def run_doc():
    return db().document_with_path(f"e2e_runs/{RUN_ID}")


def col(name: str):
    return run_doc().collection_with_path(name)


# ---- values -------------------------------------------------------------------


def test_round_trip_every_value_type(t: TestContext) -> None:
    other = col("refs").document_with_path("target")
    data = {
        "text": "héllo ✓",
        "int": 9_007_199_254_740_993,  # above 2**53: must stay exact
        "negative": -42,
        "float": 3.25,
        "true": True,
        "false": False,
        "null": None,
        "when": WHEN,
        "when_naive": datetime(2026, 1, 2, 3, 4, 5, 6),  # read as UTC
        "when_offset": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=2))),
        "before_1970": datetime(1969, 7, 20, 20, 17, 40, 500000, tzinfo=UTC),
        "bytes": b"\x00\x01\xffbinary",
        "list": [1, "two", None, True, WHEN],
        "tuple": (1, 2),
        "map": {"nested": {"deep": True, "at": WHEN, "none": None}, "n": 1},
        "ref": other,
        "empty_map": {},
        "empty_list": [],
    }
    doc = col("values").document_with_path("all")

    def after_read(snapshot, error) -> None:
        expect(error is None, error)
        expect(snapshot.exists, "document should exist")
        got = snapshot.data
        for key in ("text", "int", "negative", "float", "true", "false", "null", "when", "bytes",
                    "empty_map", "empty_list"):
            expect_equal(got[key], data[key], key)
        expect(type(got["true"]) is bool and type(got["false"]) is bool, f"bools came back as {type(got['true'])}")
        expect(type(got["int"]) is int, f"int came back as {type(got['int'])}")
        expect_equal(got["when_naive"], datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC), "naive datetime")
        expect_equal(got["when_offset"], datetime(2026, 1, 2, 1, 4, 5, tzinfo=UTC), "offset datetime")
        expect_equal(got["before_1970"], data["before_1970"], "pre-1970 datetime")
        expect_equal(got["list"], [1, "two", None, True, WHEN], "list")
        expect_equal(got["tuple"], [1, 2], "tuple -> list")
        expect_equal(got["map"], {"nested": {"deep": True, "at": WHEN, "none": None}, "n": 1}, "nested map")
        expect_equal(got["ref"], other, "document reference")
        expect_equal(got["ref"].path, other.path, "reference path")
        expect_equal(snapshot.get("map.nested.at"), WHEN, "dotted get")
        expect_equal(snapshot["map.n"], 1, "getitem")
        t.passed()

    def after_write(error) -> None:
        expect(error is None, error)
        doc.get_document(t.step(after_read), source=FIRFirestoreSource.Server)

    doc.set_data(data, callback=t.step(after_write))


def test_unsupported_values_raise_before_sending(t: TestContext) -> None:
    doc = col("values").document_with_path("bad")
    for bad, message in [({"a": {1, 2}}, "a: cannot store a set"), ({1: "x"}, "field names must be str"),
                         ({"d": datetime.now(UTC).date()}, "no date-only type")]:
        try:
            doc.set_data(bad)
        except TypeError as e:
            expect(message in str(e), f"wrong message: {e}")
        else:
            t.fail(f"no TypeError for {bad!r}")
            return
    t.passed()


# ---- writes -------------------------------------------------------------------


def test_update_with_field_values(t: TestContext) -> None:
    doc = col("counters").document_with_path("c1")

    def after_read(snapshot, error) -> None:
        expect(error is None, error)
        got = snapshot.data
        expect_equal(got["count"], 15, "integer increment")
        expect_equal(got["ratio"], 1.0, "double increment")
        expect_equal(got["tags"], ["a", "c", "d"], "array union then remove")
        expect("obsolete" not in got, "field_value_for_delete")
        expect(isinstance(got["updated"], datetime), f"server timestamp: {got['updated']!r}")
        expect(abs(got["updated"] - datetime.now(UTC)) < timedelta(minutes=5), "server timestamp is now")
        t.passed()

    def after_update(error) -> None:
        expect(error is None, error)
        doc.get_document(t.step(after_read))

    def after_set(error) -> None:
        expect(error is None, error)
        doc.update_data(
            {
                "count": FieldValue.field_value_for_integer_increment(5),
                "ratio": FieldValue.field_value_for_double_increment(0.5),
                "tags": FieldValue.field_value_for_array_union(["c", "d", "a"]),
                "obsolete": FieldValue.field_value_for_delete(),
                "updated": FieldValue.field_value_for_server_timestamp(),
            },
            t.step(lambda e: (expect(e is None, e), doc.update_data(
                {"tags": FieldValue.field_value_for_array_remove(["b"])}, t.step(after_update)))),
        )

    doc.set_data({"count": 10, "ratio": 0.5, "tags": ["a", "b"], "obsolete": 1}, callback=t.step(after_set))


def test_merge_and_merge_fields(t: TestContext) -> None:
    doc = col("merge").document_with_path("m1")

    def check(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal(snapshot.data, {"a": 1, "b": 20, "c": 3, "nested": {"x": 1, "y": 2}}, "merged data")
        t.passed()

    def after_merge_fields(error) -> None:
        expect(error is None, error)
        doc.get_document(t.step(check))

    def after_merge(error) -> None:
        expect(error is None, error)
        # only "c" and "nested.y" are written; "a" and "b" here are ignored
        doc.set_data_merge_fields({"a": 999, "c": 3, "nested": {"y": 2}}, ["c", "nested.y"], t.step(after_merge_fields))

    def after_set(error) -> None:
        expect(error is None, error)
        doc.set_data({"b": 20}, merge=True, callback=t.step(after_merge))

    doc.set_data({"a": 1, "b": 2, "nested": {"x": 1}}, callback=t.step(after_set))


def test_old_set_data_callback_form(t: TestContext) -> None:
    doc = col("compat").document_with_path("old")

    def after_read(snapshot, error) -> None:
        expect_equal(snapshot.data, {"only": True}, "not merged: the old form replaces")
        t.passed()

    def after_set(error) -> None:
        expect(error is None, error)
        doc.get_document(t.step(after_read))

    def after_first(error) -> None:
        expect(error is None, error)
        doc.set_data({"only": True}, t.step(after_set))  # callback passed positionally

    doc.set_data({"stale": 1}, callback=t.step(after_first))


def test_add_document_and_auto_id(t: TestContext) -> None:
    items = col("items")
    auto = items.document_with_auto_id()
    expect_equal(len(auto.document_id), 20, "auto id length")
    returned = {}

    def after_add(ref, error) -> None:
        expect(error is None, error)
        expect(ref == returned["ref"], "callback gives the returned reference")
        expect_equal(ref.parent, items, "parent collection")
        ref.get_document(t.step(lambda s, e: (expect_equal(s.data, {"n": 1}, "added data"), t.passed())))

    returned["ref"] = items.add_document_with_data({"n": 1}, t.step(after_add))
    expect(returned["ref"].path.startswith(items.path + "/"), returned["ref"].path)


def test_missing_document_and_delete(t: TestContext) -> None:
    doc = col("deletes").document_with_path("d1")

    def after_delete_read(snapshot, error) -> None:
        expect(error is None, error)
        expect(not snapshot.exists, "deleted document should not exist")
        expect_equal(snapshot.data, {}, "missing document data")
        expect(snapshot.get("x") is None, "missing field")
        t.passed()

    def after_delete(error) -> None:
        expect(error is None, error)
        doc.get_document(t.step(after_delete_read))

    doc.set_data({"x": 1}, callback=t.step(lambda e: doc.delete_document(t.step(after_delete))))


def test_update_missing_document_fails(t: TestContext) -> None:
    def after(error) -> None:
        expect(error is not None, "updating a missing document should fail")
        expect_equal(error.code, 5, "error code (NOT_FOUND)")
        expect(error.domain == "FIRFirestoreErrorDomain", error.domain)
        expect(isinstance(error.description, str) and error.description, "description")
        t.passed()

    col("missing").document_with_path("nope").update_data({"a": 1}, t.step(after))


# ---- queries ------------------------------------------------------------------

CITIES = {
    "SF": {"name": "San Francisco", "state": "CA", "population": 860_000, "capital": False,
           "regions": ["west_coast", "norcal"], "founded": datetime(1776, 6, 29, tzinfo=UTC)},
    "LA": {"name": "Los Angeles", "state": "CA", "population": 3_900_000, "capital": False,
           "regions": ["west_coast", "socal"], "founded": datetime(1781, 9, 4, tzinfo=UTC)},
    "DC": {"name": "Washington", "state": None, "population": 680_000, "capital": True,
           "regions": ["east_coast"], "founded": datetime(1790, 7, 16, tzinfo=UTC)},
    "TOK": {"name": "Tokyo", "state": None, "population": 9_000_000, "capital": True,
            "regions": ["kanto", "honshu"], "founded": datetime(1457, 1, 1, tzinfo=UTC)},
    "BJ": {"name": "Beijing", "state": None, "population": 21_500_000, "capital": True,
           "regions": ["jingjinji", "hebei"], "founded": datetime(1045, 1, 1, tzinfo=UTC)},
}


def _seed_cities(t: TestContext, then) -> None:
    cities = col("cities")
    batch = db().batch()
    for key, data in CITIES.items():
        batch.set_data(data, cities.document_with_path(key))
    batch.commit(t.step(lambda error: (expect(error is None, error), then(cities))))


def _ids(snapshot) -> list[str]:
    return [doc.document_id for doc in snapshot]


def test_queries(t: TestContext) -> None:
    checks: list[tuple[str, Any, list[str], bool]] = []  # (what, query, expected ids, ordered)

    def run(cities) -> None:
        checks.extend([
            ("== state", cities.query_where_field_is_equal_to("state", "CA"), ["LA", "SF"], False),
            ("== None", cities.query_where_field_is_equal_to("state", None), ["BJ", "DC", "TOK"], False),
            ("> population ordered", cities.query_where_field_is_greater_than("population", 1_000_000)
                .query_ordered_by_field("population", descending=True), ["BJ", "TOK", "LA"], True),
            ("in", cities.query_where_field_in("name", ["Tokyo", "Washington", "Paris"]), ["DC", "TOK"], False),
            ("not in", cities.query_where_field_not_in("name", ["Tokyo", "Washington"]), ["BJ", "LA", "SF"], False),
            ("array contains", cities.query_where_field_array_contains("regions", "west_coast"), ["LA", "SF"], False),
            ("array contains any", cities.query_where_field_array_contains_any("regions", ["socal", "kanto"]),
             ["LA", "TOK"], False),
            ("datetime <", cities.query_where_field_is_less_than("founded", datetime(1500, 1, 1, tzinfo=UTC)),
             ["BJ", "TOK"], False),
            ("limit", cities.query_ordered_by_field("population").query_limited_to(2), ["DC", "SF"], True),
            ("limit to last", cities.query_ordered_by_field("population").query_limited_to_last(2), ["TOK", "BJ"], True),
            ("start at values", cities.query_ordered_by_field("population").query_starting_at_values([3_900_000]),
             ["LA", "TOK", "BJ"], True),
            ("end before values", cities.query_ordered_by_field("population").query_ending_before_values([860_000]),
             ["DC"], True),
            ("OR filter", cities.query_where_filter(Filter.or_filter_with_filters([
                Filter.filter_where_field_is_equal_to("capital", False),
                Filter.filter_where_field_is_greater_than_or_equal_to("population", 20_000_000),
            ])), ["BJ", "LA", "SF"], False),
            ("AND inside OR", cities.query_where_filter(Filter.or_filter_with_filters([
                Filter.and_filter_with_filters([
                    Filter.filter_where_field_is_equal_to("capital", True),
                    Filter.filter_where_field_is_less_than("population", 1_000_000),
                ]),
                Filter.filter_where_field_is_equal_to("name", "Tokyo"),
            ])), ["DC", "TOK"], False),
        ])
        next_check()

    def next_check() -> None:
        if not checks:
            cursor_paging()
            return
        what, query, expected, ordered = checks.pop(0)

        def got(snapshot, error) -> None:
            expect(error is None, f"{what}: {error}")
            ids = _ids(snapshot)
            expect_equal(ids if ordered else sorted(ids), expected, what)
            next_check()

        query.get_documents(t.step(got))

    def cursor_paging() -> None:
        ordered = col("cities").query_ordered_by_field("population")

        def second_page(snapshot, error) -> None:
            expect(error is None, error)
            expect_equal(_ids(snapshot), ["LA", "TOK"], "page 2 (start after document)")
            t.passed()

        def first_page(snapshot, error) -> None:
            expect(error is None, error)
            expect_equal(_ids(snapshot), ["DC", "SF"], "page 1")
            expect_equal(len(snapshot), 2, "len")
            expect(not snapshot.is_empty, "is_empty")
            expect_equal(snapshot[-1].document_id, "SF", "negative index")
            ordered.query_starting_after_document(snapshot[-1]).query_limited_to(2).get_documents(
                t.step(second_page)
            )

        ordered.query_limited_to(2).get_documents(t.step(first_page))

    _seed_cities(t, t.step(run))


def test_collection_group(t: TestContext) -> None:
    group = f"landmarks_{RUN_ID}"
    batch = db().batch()
    batch.set_data({"type": "bridge"}, col("cities").document_with_path("SF").collection_with_path(group).document_with_path("golden_gate"))
    batch.set_data({"type": "museum"}, col("cities").document_with_path("SF").collection_with_path(group).document_with_path("legion"))
    batch.set_data({"type": "museum"}, col("cities").document_with_path("TOK").collection_with_path(group).document_with_path("national"))

    def got(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal(sorted(_ids(snapshot)), ["legion", "national"], "museums across cities")
        parents = sorted(doc.reference.parent.parent.document_id for doc in snapshot)
        expect_equal(parents, ["SF", "TOK"], "parent documents")
        t.passed()

    batch.commit(t.step(lambda error: (expect(error is None, error),
        db().collection_group_with_id(group).query_where_field_is_equal_to("type", "museum").get_documents(t.step(got)))))


def test_aggregates(t: TestContext) -> None:
    count = AggregateField.aggregate_field_for_count()
    total = AggregateField.aggregate_field_for_sum_of_field("population")
    average = AggregateField.aggregate_field_for_average_of_field("population")
    expected_total = sum(c["population"] for c in CITIES.values())

    def got_all(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal(snapshot.value_for_aggregate_field(count), 5, "count")
        expect_equal(snapshot.value_for_aggregate_field(total), expected_total, "sum")
        expect(abs(snapshot.value_for_aggregate_field(average) - expected_total / 5) < 1e-6, "average")
        expect(isinstance(snapshot.value_for_aggregate_field(count), int), "count is int")
        t.passed()

    def got_count(snapshot, error) -> None:
        expect(error is None, error)
        expect_equal(snapshot.count, 2, "count of CA cities")
        col("cities").aggregate([count, total, average]).aggregation_with_source(
            FIRAggregateSource.Server, t.step(got_all)
        )

    def seeded(cities) -> None:
        cities.query_where_field_is_equal_to("state", "CA").count.aggregation_with_source(
            FIRAggregateSource.Server, t.step(got_count)
        )

    _seed_cities(t, t.step(seeded))


# ---- listeners ----------------------------------------------------------------


def test_document_listener(t: TestContext) -> None:
    from kivy.clock import Clock

    doc = col("listen").document_with_path("doc")
    seen: list[Any] = []
    holder: dict[str, Any] = {}

    def no_more_events(_dt) -> None:
        expect_equal(seen, [1, 2], "values seen (none after remove())")
        t.passed()

    def on_snapshot(snapshot, error) -> None:
        expect(error is None, error)
        # a default listener fires once per data change: a local write fires
        # right away (has_pending_writes=True); the server's confirmation only
        # changes metadata, which default listeners do not report
        seen.append(snapshot.data.get("v"))
        if seen == [1]:
            doc.update_data({"v": 2})
        elif seen == [1, 2]:
            expect(snapshot.metadata.has_pending_writes, "a local write is pending first")
            holder["registration"].remove()
            holder["registration"].remove()  # safe twice
            doc.update_data({"v": 3}, t.step(lambda e: Clock.schedule_once(t.step(no_more_events), 0.5)))
        else:
            t.fail(f"listener called after remove(): {seen}")

    def after_set(error) -> None:
        expect(error is None, error)
        holder["registration"] = doc.add_snapshot_listener(t.step(on_snapshot))

    doc.set_data({"v": 1}, callback=t.step(after_set))


def test_listener_metadata_changes(t: TestContext) -> None:
    doc = col("listen").document_with_path("meta")
    states: list[tuple[Any, bool]] = []
    holder: dict[str, Any] = {}

    def on_snapshot(snapshot, error) -> None:
        expect(error is None, error)
        state = (snapshot.data.get("v"), snapshot.metadata.has_pending_writes)
        if states and states[-1] == state:
            return  # e.g. a from-cache -> from-server change
        states.append(state)
        if state == (1, False) and len(states) == 1:
            doc.update_data({"v": 2})
        elif state == (2, False):
            expect((2, True) in states, f"the pending local write was reported first: {states}")
            holder["registration"].remove()
            t.passed()

    def after_set(error) -> None:
        expect(error is None, error)
        holder["registration"] = doc.add_snapshot_listener(
            t.step(on_snapshot), include_metadata_changes=True
        )

    doc.set_data({"v": 1}, callback=t.step(after_set))


def test_query_listener_document_changes(t: TestContext) -> None:
    room = col("rooms").document_with_path("r1").collection_with_path("messages")
    events: list[list[tuple[str, str]]] = []
    holder: dict[str, Any] = {}

    def on_snapshot(snapshot, error) -> None:
        expect(error is None, error)
        changes = [(c.type, c.document.document_id) for c in snapshot.document_changes]
        if not changes:
            return
        events.append(changes)
        step = len(events)
        if step == 1:
            expect_equal(sorted(changes), [(DocumentChange.ADDED, "m1")], "initial snapshot")
            room.document_with_path("m2").set_data({"text": "two", "n": 2})
        elif step == 2:
            expect_equal(changes, [(DocumentChange.ADDED, "m2")], "added")
            room.document_with_path("m1").update_data({"text": "one (edited)"})
        elif step == 3:
            expect_equal(changes, [(DocumentChange.MODIFIED, "m1")], "modified")
            expect_equal(snapshot.document_changes[0].document.data["text"], "one (edited)", "modified data")
            room.document_with_path("m2").delete_document()
        elif step == 4:
            expect_equal(changes, [(DocumentChange.REMOVED, "m2")], "removed")
            expect_equal(_ids(snapshot), ["m1"], "remaining documents")
            holder["registration"].remove()
            t.passed()

    def after_seed(error) -> None:
        expect(error is None, error)
        holder["registration"] = room.query_ordered_by_field("n").add_snapshot_listener(t.step(on_snapshot))

    room.document_with_path("m1").set_data({"text": "one", "n": 1}, callback=t.step(after_seed))


# ---- transactions -------------------------------------------------------------


def test_transaction_returns_python_value(t: TestContext) -> None:
    account = col("accounts").document_with_path("a1")
    log = col("accounts").document_with_path("log")

    def update(transaction):
        snapshot = transaction.get_document(account)
        balance = snapshot.get("balance")
        transaction.update_data({"balance": balance - 30}, account)
        transaction.set_data({"last": {"amount": 30, "at": WHEN}}, log)
        return {"old": balance, "new": balance - 30, "when": WHEN}

    def after_read(snapshot, error) -> None:
        expect_equal(snapshot.get("balance"), 70, "balance after transaction")
        log.get_document(t.step(lambda s, e: (expect_equal(s.get("last.at"), WHEN, "write inside transaction"), t.passed())))

    def done(result, error) -> None:
        expect(error is None, error)
        expect_equal(result, {"old": 100, "new": 70, "when": WHEN}, "the Python value returned by update_fn")
        account.get_document(t.step(after_read))

    account.set_data({"balance": 100}, callback=t.step(lambda e: db().run_transaction(update, t.step(done))))


def test_transaction_failure_writes_nothing(t: TestContext) -> None:
    account = col("accounts").document_with_path("a2")

    def update(transaction):
        balance = transaction.get_document(account).get("balance")
        transaction.update_data({"balance": balance - 500}, account)
        if balance - 500 < 0:
            raise TransactionException("insufficient funds")
        return balance

    def after_read(snapshot, error) -> None:
        expect_equal(snapshot.get("balance"), 100, "balance unchanged after a failed transaction")
        t.passed()

    def done(result, error) -> None:
        expect(result is None, f"result on failure: {result!r}")
        expect(error is not None, "a raised exception must fail the transaction")
        expect_equal(error.description, "insufficient funds", "error description")
        account.get_document(t.step(after_read))

    account.set_data({"balance": 100}, callback=t.step(lambda e: db().run_transaction(update, t.step(done))))


# ---- read sources -------------------------------------------------------------


def test_cache_source_after_server_read(t: TestContext) -> None:
    doc = col("sources").document_with_path("s1")

    def from_cache(snapshot, error) -> None:
        expect(error is None, error)
        expect(snapshot.metadata.is_from_cache, "Cache source must read the cache")
        expect_equal(snapshot.data, {"cached": True}, "cached data")
        t.passed()

    def from_server(snapshot, error) -> None:
        expect(error is None, error)
        expect(not snapshot.metadata.is_from_cache, "Server source must not read the cache")
        doc.get_document(t.step(from_cache), source=FIRFirestoreSource.Cache)

    doc.set_data({"cached": True}, callback=t.step(
        lambda e: doc.get_document(t.step(from_server), source=FIRFirestoreSource.Server)))


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

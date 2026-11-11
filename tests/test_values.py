"""Python values written to Firestore, and read back."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from conftest import FIRDocumentReference, Recorder
from rubicon.objc import ObjCClass, ObjCInstance

from pyios_firebase.firestore import (
    CollectionReference,
    DocumentReference,
    FieldValue,
    Filter,
    Query,
    WriteBatch,
)
from pyios_firebase.firestore.transaction import Transaction
from pyios_firebase.util import (
    datetime_to_timestamp,
    timestamp_to_datetime,
    to_firestore,
    to_python,
)


def round_trip(value):
    """Write conversion, then read conversion, as a Firestore round trip does."""
    return to_python(to_firestore(value))


# ---- datetime ----


@pytest.mark.parametrize(
    ("value", "seconds", "nanoseconds"),
    [
        (datetime(1970, 1, 1, tzinfo=UTC), 0, 0),
        (
            datetime(2023, 11, 14, 22, 13, 20, 123456, tzinfo=UTC),
            1_700_000_000,
            123_456_000,
        ),
        # before 1970: seconds go negative, nanoseconds stay in [0, 1e9)
        (datetime(1969, 12, 31, 23, 59, 59, 500000, tzinfo=UTC), -1, 500_000_000),
        # another timezone: the same instant
        (
            datetime(2023, 11, 14, 23, 13, 20, tzinfo=timezone(timedelta(hours=1))),
            1_700_000_000,
            0,
        ),
        # naive: read as UTC
        (datetime(2023, 11, 14, 22, 13, 20), 1_700_000_000, 0),  # noqa: DTZ001
    ],
)
def test_datetime_to_timestamp(value, seconds, nanoseconds):
    timestamp = datetime_to_timestamp(value)
    assert (timestamp.seconds, timestamp.nanoseconds) == (seconds, nanoseconds)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 11, 11, 9, 30, 15, 999999, tzinfo=UTC),
        datetime(1, 1, 1, tzinfo=UTC),
        datetime(
            9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC
        ),  # float math would lose µs here
        datetime(1900, 6, 1, 0, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_datetime_round_trip_keeps_microseconds(value):
    assert round_trip({"at": value}) == {"at": value}


def test_read_drops_sub_microsecond_nanoseconds():
    timestamp = ObjCClass("FIRTimestamp").timestampWithSeconds_nanoseconds_(0, 1_999)
    assert timestamp_to_datetime(timestamp) == datetime(
        1970, 1, 1, 0, 0, 0, 1, tzinfo=UTC
    )


def test_date_only_is_refused_with_a_clear_message():
    with pytest.raises(TypeError, match=r"born: Firestore has no date-only type"):
        to_firestore({"born": date(1815, 12, 10)})


# ---- None, containers, keys ----


def test_none_becomes_null_instead_of_crashing():
    # plain ns_from_py({"a": None}) raises an ObjC exception that ends the app
    converted = to_firestore({"a": None, "b": [None, 1]})
    null = ObjCClass("NSNull").null()
    assert converted.objectForKey_("a") == null
    assert round_trip({"a": None, "b": [None, 1]}) == {"a": None, "b": [None, 1]}


def test_nested_structures_and_tuples():
    value = {
        "name": "Ada",
        "born": 1815,
        "ratio": 0.5,
        "active": True,
        "tags": ("math", "poetry"),
        "events": [{"at": datetime(1843, 1, 1, tzinfo=UTC), "what": "notes"}],
    }
    expected = dict(value, tags=["math", "poetry"])
    assert round_trip(value) == expected


def test_bool_stays_bool():
    assert round_trip({"a": True, "b": 1}) == {"a": True, "b": 1}
    assert type(round_trip({"a": True})["a"]) is bool


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({1: "x"}, r"data: field names must be str, not int"),
        ({"a": {2: "x"}}, r"a: field names must be str"),
        ({"a": {1, 2}}, r"a: cannot store a set"),
        ({"a": [object()]}, r"a\[0\]: cannot store a object"),
    ],
)
def test_unsupported_values_raise_in_python(value, message):
    with pytest.raises(TypeError, match=message):
        to_firestore(value)


# ---- references and sentinels ----


def test_document_reference_round_trip():
    native = FIRDocumentReference.new()
    converted = to_firestore({"owner": DocumentReference(native)})
    assert converted.objectForKey_("owner") == native
    read = round_trip({"owner": DocumentReference(native)})["owner"]
    assert isinstance(read, DocumentReference) and read._ref == native


def test_objc_values_pass_through():
    sentinel = ObjCClass("NSObject").new()  # e.g. a FieldValue sentinel
    assert to_firestore({"x": sentinel}).objectForKey_("x") == sentinel


# ---- every write and query path converts ----

WHEN = datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC)


def _sent_datetime(ns_value, key="at"):
    """The datetime inside an NSDictionary that was given to the SDK."""
    return timestamp_to_datetime(ns_value.objectForKey_(key))


def test_document_reference_writes_convert():
    ref = Recorder()
    doc = DocumentReference(ref)
    doc.set_data({"at": WHEN})
    doc.set_data({"at": WHEN}, merge=True)
    doc.set_data_merge_fields({"at": WHEN}, ["at"])
    doc.update_data({"at": WHEN, "gone": None})
    assert [_sent_datetime(args[0]) for _, args in ref.calls] == [WHEN] * 4


def test_add_document_converts():
    ref = Recorder({"addDocumentWithData_completion_": Recorder()})
    CollectionReference(ref).add_document_with_data({"at": WHEN})
    assert _sent_datetime(ref.last()[0]) == WHEN


def test_batch_and_transaction_writes_convert():
    native, doc = Recorder(), DocumentReference(Recorder())
    WriteBatch(native).set_data({"at": WHEN}, doc).set_data(
        {"at": WHEN}, doc, merge=True
    ).update_data({"at": WHEN}, doc).set_data_merge_fields({"at": WHEN}, doc, ["at"])
    native_tx = Recorder()
    Transaction(native_tx, None).set_data({"at": WHEN}, doc).set_data(
        {"at": WHEN}, doc, merge=True
    ).update_data({"at": WHEN}, doc)
    sent = [args[0] for _, args in native.calls + native_tx.calls]
    assert [_sent_datetime(v) for v in sent] == [WHEN] * 7


def test_query_values_convert():
    ref = Recorder(
        {
            "queryWhereField_isGreaterThan_": Recorder(),
            "queryStartingAfterValues_": Recorder(),
        }
    )
    Query(ref).query_where_field_is_greater_than("at", WHEN)
    Query(ref).query_starting_after_values([WHEN])
    (field, value), (values,) = ref.calls[0][1], ref.calls[1][1]
    assert field == "at" and timestamp_to_datetime(value) == WHEN
    assert timestamp_to_datetime(values.objectAtIndex_(0)) == WHEN


def test_query_where_equal_to_none_is_null():
    ref = Recorder({"queryWhereField_isEqualTo_": Recorder()})
    Query(ref).query_where_field_is_equal_to("deleted_at", None)
    assert ref.last()[1] == ObjCClass("NSNull").null()


def test_filter_and_field_value_convert(monkeypatch):
    fake = Recorder()
    monkeypatch.setattr("pyios_firebase.firestore.filter._fir_filter", lambda: fake)
    monkeypatch.setattr(
        "pyios_firebase.firestore.field_value._fir_field_value", lambda: fake
    )
    Filter.filter_where_field_is_less_than("at", WHEN)
    FieldValue.field_value_for_array_union([WHEN, None])
    assert timestamp_to_datetime(fake.calls[0][1][1]) == WHEN
    elements = fake.calls[1][1][0]
    assert timestamp_to_datetime(elements.objectAtIndex_(0)) == WHEN
    assert ObjCInstance(elements.objectAtIndex_(1)) == ObjCClass("NSNull").null()


def test_any_mapping_can_be_written():
    """FirestoreData is a Mapping: non-dict mappings must convert like dicts."""
    from collections import ChainMap
    from types import MappingProxyType

    defaults = {"theme": "dark", "at": WHEN}
    value = ChainMap(
        {"theme": "light"}, {"nested": MappingProxyType(defaults)}, defaults
    )
    assert round_trip(value) == {"theme": "light", "nested": defaults, "at": WHEN}
    assert round_trip(MappingProxyType(defaults)) == defaults
    with pytest.raises(TypeError, match="field names must be str"):
        to_firestore(MappingProxyType({1: "x"}))

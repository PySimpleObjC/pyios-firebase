from ctypes import c_int
from datetime import UTC, datetime

import pytest
from conftest import make_error
from rubicon.objc import ObjCClass

from pyios_firebase.util import (
    QueryDict,
    listener_block,
    nserror_to_dict,
    one_shot_block,
    to_python,
)


def test_query_dict_dot_access():
    d = QueryDict(code=1)
    d.description = "x"
    assert d.code == 1 and d["description"] == "x"
    with pytest.raises(AttributeError, match="missing"):
        _ = d.missing


def test_nserror_to_dict():
    underlying = make_error("socket closed", 2, "NSPOSIXErrorDomain")
    error = nserror_to_dict(make_error(NSUnderlyingError=underlying))
    assert error == {
        "code": 7,
        "description": "permission denied",
        "domain": "FIRFirestoreErrorDomain",
        "underlying_error": underlying,
    }
    assert isinstance(error.code, int) and isinstance(error.description, str)
    assert nserror_to_dict(None) is None


def test_to_python_nested():
    null = ObjCClass("NSNull").null()
    assert to_python({"a": [1, null, {"b": null}], "c": "x"}) == {
        "a": [1, None, {"b": None}],
        "c": "x",
    }


def test_timestamp_to_datetime():
    from pyios_firebase.util import timestamp_to_datetime

    class Ts:
        seconds = 1_700_000_000
        nanoseconds = 500_000_000

    assert timestamp_to_datetime(Ts()) == datetime(
        2023, 11, 14, 22, 13, 20, 500000, tzinfo=UTC
    )


def test_one_shot_block_is_released_after_call(blocks):
    seen = []
    block = one_shot_block(seen.append, c_int)
    assert block in blocks
    block.func(5)
    assert seen == [5] and block not in blocks


def test_listener_block_lives_until_release(blocks):
    block, release = listener_block(lambda x: None, c_int)
    block.func(1)
    block.func(2)
    assert block in blocks
    release()
    assert block not in blocks


def test_nsdate_to_datetime_with_a_real_nsdate():
    from pyios_firebase.util import nsdate_to_datetime

    nsdate = ObjCClass("NSDate").dateWithTimeIntervalSince1970_(1_700_000_000.25)
    assert nsdate_to_datetime(nsdate) == datetime(
        2023, 11, 14, 22, 13, 20, 250000, tzinfo=UTC
    )
    assert nsdate_to_datetime(None) is None
    # NSDate values from the SDK also convert inside to_python
    assert to_python({"at": nsdate}) == {
        "at": datetime(2023, 11, 14, 22, 13, 20, 250000, tzinfo=UTC)
    }

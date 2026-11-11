"""Tests run on macOS: Rubicon works there, the Firebase classes do not exist.

Fakes stand in for the Firebase objects. They keep the blocks the wrappers
give them, and ``fire`` calls a block the way Firebase would.
"""

import sys

import pytest

if sys.platform != "darwin":
    pytest.skip("needs the Objective-C runtime (macOS or iOS)", allow_module_level=True)

from rubicon.objc import ObjCClass, ObjCInstance

from pyios_firebase import util


def fire(block, *args):
    """Call a block's Python function with raw pointers, as Firebase does."""
    return block.func(*[a.ptr if isinstance(a, ObjCInstance) else a for a in args])


def make_error(
    description="permission denied", code=7, domain="FIRFirestoreErrorDomain", **info
):
    user_info = {"NSLocalizedDescription": description, **info}
    return ObjCClass("NSError").errorWithDomain_code_userInfo_(domain, code, user_info)


class Recorder:
    """A fake Firebase object: every method call is saved in ``calls``."""

    def __init__(self, returns=None):
        self.calls = []
        self._returns = returns or {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args):
            self.calls.append((name, args))
            value = self._returns.get(name)
            return value() if callable(value) else value

        return method

    def last(self, name=None):
        for call_name, args in reversed(self.calls):
            if name is None or call_name == name:
                return args
        raise AssertionError(f"{name} was not called")

    def block(self, name=None):
        """The block given in the last call (it is always the last argument)."""
        return self.last(name)[-1]


@pytest.fixture
def blocks():
    """The set of blocks the package keeps alive. Must be empty after each test."""
    util._blocks.clear()
    yield util._blocks
    util._blocks.clear()


# ---- stand-ins for Firestore value classes ----------------------------------
# Same class names and selectors as the SDK, so the package finds them with
# objc_class() exactly as it would on iOS.

from ctypes import c_int32, c_int64

from rubicon.objc import (
    NSObject,
    objc_classmethod,
    objc_id,
    objc_property,
)

_alive = []  # the SDK returns autoreleased objects; the fakes just keep theirs


class FIRTimestamp(NSObject):
    seconds = objc_property(c_int64)
    nanoseconds = objc_property(c_int32)

    @objc_classmethod
    def timestampWithSeconds_nanoseconds_(
        cls, seconds: c_int64, nanoseconds: c_int32
    ) -> objc_id:
        if not 0 <= nanoseconds < 1_000_000_000:
            raise ValueError("nanoseconds out of range")  # the SDK asserts this too
        timestamp = cls.alloc().init()
        timestamp.seconds = seconds
        timestamp.nanoseconds = nanoseconds
        _alive.append(timestamp)
        return timestamp


class FIRDocumentReference(NSObject):
    path = objc_property()

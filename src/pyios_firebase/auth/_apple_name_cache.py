"""Keeps the name Apple shares at a user's FIRST authorization until Firebase
has it.

Sign in with Apple sends the name once per user per app. If the Firebase
sign-in that should carry it fails (for example a flaky network), every retry
gets no name. So the name is saved here, keyed by Apple's stable user ID
(``credential.user``), as soon as Apple sends it, reused by a retry that gets
none, and deleted once Firebase sign-in works.

The store is NSUserDefaults on iOS; tests can pass a dict.
"""

from __future__ import annotations

__all__ = ("AppleNameCache", "NameStore", "UserDefaultsStore")

from collections.abc import Sequence
from typing import Any, Final, Protocol

DEFAULTS_KEY: Final = "pyios_firebase.apple_sign_in.pending_names"


class NameStore(Protocol):
    """Where names are kept: ``{apple_user: [given, family]}``. A ``dict`` works."""

    def get(self, apple_user: str, default: Any = None, /) -> Any: ...
    def __setitem__(self, apple_user: str, value: list[str], /) -> None: ...
    def pop(self, apple_user: str, default: Any = None, /) -> Any: ...


class UserDefaultsStore:
    """A ``NameStore`` kept in one NSUserDefaults entry, so it survives restarts."""

    def __init__(self, key: str = DEFAULTS_KEY) -> None:
        from rubicon.objc import ns_from_py

        from ..util import objc_class, to_python

        self._key = key
        self._defaults = objc_class("NSUserDefaults").standardUserDefaults
        self._ns, self._py = ns_from_py, to_python

    def _load(self) -> dict[str, list[str]]:
        value = self._defaults.objectForKey_(self._key)
        return dict(self._py(value)) if value is not None else {}

    def _save(self, data: dict[str, list[str]]) -> None:
        if data:
            self._defaults.setObject_forKey_(self._ns(data), self._key)
        else:
            self._defaults.removeObjectForKey_(self._key)

    def get(self, apple_user: str, default: Any = None, /) -> Any:
        return self._load().get(apple_user, default)

    def __setitem__(self, apple_user: str, value: list[str], /) -> None:
        data = self._load()
        data[apple_user] = list(value)
        self._save(data)

    def pop(self, apple_user: str, default: Any = None, /) -> Any:
        data = self._load()
        value = data.pop(apple_user, default)
        self._save(data)
        return value


class AppleNameCache:
    """Remembers the name Apple sent until a Firebase sign-in carries it."""

    def __init__(self, store: NameStore | None = None) -> None:
        self._store: NameStore = store if store is not None else UserDefaultsStore()

    def resolve(
        self, apple_user: str, first: str | None, last: str | None
    ) -> tuple[str, str]:
        """The name to use for this authorization: Apple's when it sent one
        (which is then saved), else the one saved by an earlier attempt.

        Returns:
            ``(first_name, last_name)``; ``""`` for parts nobody knows.
        """
        first, last = first or "", last or ""
        if not apple_user:
            return first, last
        if first or last:
            self._store[apple_user] = [first, last]
            return first, last
        saved: Sequence[str | None] | None = self._store.get(apple_user)
        if saved:
            return str(saved[0] or ""), str(saved[1] or "")
        return "", ""

    def forget(self, apple_user: str | None) -> None:
        """Drop the saved name: Firebase has it now (call after sign-in works)."""
        if apple_user:
            self._store.pop(apple_user, None)

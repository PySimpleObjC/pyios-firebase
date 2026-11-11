"""End-to-end App Check tests: a Python custom provider, through the real SDK.

main.py installs ``E2EAppCheckProvider`` before ``core.configure()``, so every
Firebase SDK in the app (Functions, Storage, Firestore, Auth) asks it for tokens.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pyios_firebase.app_check import AppCheck, AppCheckProvider, AppCheckToken
from runner import TestContext, expect, expect_equal

DEBUG_TOKEN = os.environ.get("FIRAAppCheckDebugToken")
# App Check keeps tokens across launches: name tokens per launch to tell them apart
LAUNCH = uuid.uuid4().hex[:6]


class E2EAppCheckProvider(AppCheckProvider):
    """Numbered tokens: ``e2e-app-check-<launch>-<n>`` and ``e2e-limited-<launch>-<n>``."""

    _shared: E2EAppCheckProvider | None = None

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.issued = 0
        self.limited = 0
        self.threads: set[str] = set()

    @classmethod
    def shared(cls) -> E2EAppCheckProvider:
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def get_token(self, callback) -> None:
        with self.lock:
            self.issued += 1
            n = self.issued
            self.threads.add(threading.current_thread().name)
        callback(AppCheckToken(f"e2e-app-check-{LAUNCH}-{n}", datetime.now(UTC) + timedelta(hours=1)), None)

    def get_limited_use_token(self, callback) -> None:
        with self.lock:
            self.limited += 1
            n = self.limited
        callback(AppCheckToken(f"e2e-limited-{LAUNCH}-{n}", datetime.now(UTC) + timedelta(minutes=5)), None)


def test_app_check_custom_provider_tokens(t: TestContext) -> None:
    app_check = AppCheck.app_check()
    provider = E2EAppCheckProvider.shared()
    state: dict[str, Any] = {}

    def limited(token, error) -> None:
        expect(error is None, error)
        expect(token.token.startswith("e2e-limited-"), f"limited-use token from our provider: {token}")
        t.passed()

    def refreshed(token, error) -> None:
        expect(error is None, error)
        expect(provider.issued > state["issued"], "force_refresh called our provider")
        expect(token.token != state["first"], f"force_refresh gives a new token: {token.token}")
        expect(token.expiration_date > datetime.now(UTC), "expires in the future")
        app_check.limited_use_token(t.step(limited))

    def first(token, error) -> None:
        expect(error is None, error)
        # possibly cached by an earlier launch: App Check keeps tokens across launches
        expect(token.token.startswith("e2e-app-check-"), f"token from our Python provider: {token}")
        state["first"] = token.token
        state["issued"] = provider.issued
        app_check.token(t.step(refreshed), force_refresh=True)

    app_check.token(t.step(first))


def test_app_check_token_listener(t: TestContext) -> None:
    app_check = AppCheck.app_check()
    seen: list[str] = []
    holder: dict[str, Any] = {}

    def refreshed(token, error) -> None:
        expect(error is None, error)
        from kivy.clock import Clock

        def check(_dt) -> None:
            expect(token.token in seen, f"the listener got the new token: {seen} / {token.token}")
            holder["listener"].remove()
            holder["listener"].remove()  # safe twice
            t.passed()

        Clock.schedule_once(t.step(check), 0.5)

    holder["listener"] = app_check.add_token_listener(seen.append)
    app_check.token(t.step(refreshed), force_refresh=True)


def test_app_check_settings_and_rules(t: TestContext) -> None:
    from pyios_firebase import app_check

    checker = AppCheck.app_check()
    original = checker.is_token_auto_refresh_enabled
    checker.is_token_auto_refresh_enabled = not original
    expect_equal(checker.is_token_auto_refresh_enabled, not original, "auto refresh toggled")
    checker.is_token_auto_refresh_enabled = original
    try:
        app_check.use_debug_provider()
    except RuntimeError as e:
        expect("before core.configure" in str(e), str(e))
    else:
        t.fail("setting a provider after configure must raise")
        return
    expect(app_check.running_in_simulator(), "running in the Simulator")
    token = AppCheck.debug_token()
    expect(token, "a debug token")
    if DEBUG_TOKEN:
        expect_equal(token, DEBUG_TOKEN, "the debug token from FIRAAppCheckDebugToken")
    t.passed()


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

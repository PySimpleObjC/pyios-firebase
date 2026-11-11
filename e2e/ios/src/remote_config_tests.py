"""End-to-end Remote Config tests, through the real SDK.

There is no Remote Config emulator: these cover what works offline (defaults
from the app bundle's plist, values and their sources, settings, signals,
listeners) and that a fetch fails cleanly for the offline demo project.
"""

from __future__ import annotations

from pyios_firebase.remote_config import (
    RemoteConfig,
    RemoteConfigFetchStatus,
    RemoteConfigSource,
    load_plist_defaults,
)
from runner import TestContext, expect, expect_equal


def config() -> RemoteConfig:
    return RemoteConfig.remote_config()


def test_remote_config_defaults_from_plist(t: TestContext) -> None:
    expect_equal(load_plist_defaults("RemoteConfigDefaults")["max_items"], 25, "plist read from the bundle")
    c = config()
    c.set_defaults_from_plist("RemoteConfigDefaults.plist")
    expect_equal(c.get_string("welcome_message"), "Hello from the plist", "string")
    expect_equal(c.get_long("max_items"), 25, "int")
    expect(abs(c.get_number("discount") - 0.15) < 1e-9, "number")
    expect_equal(c.get_boolean("new_checkout"), True, "bool")
    expect_equal(c.get_json("ui_theme"), {"color": "green", "dark": False}, "JSON")
    value = c.get_value("welcome_message")
    expect_equal(value.source, RemoteConfigSource.DEFAULT, "source")
    expect_equal(value.data, b"Hello from the plist", "data")
    expect_equal(c.default_value("max_items").string, "25", "default value")
    expect(c.default_value("missing") is None, "no default")
    expect_equal(sorted(c.all_keys(RemoteConfigSource.DEFAULT)),
                 ["discount", "max_items", "new_checkout", "ui_theme", "welcome_message"], "default keys")
    t.passed()


def test_remote_config_missing_and_merged_values(t: TestContext) -> None:
    c = config()
    missing = c.get_value("does_not_exist")
    expect_equal(missing.source, RemoteConfigSource.STATIC, "static source")
    expect_equal((missing.string, missing.number, missing.boolean), ("", 0.0, False), "static values")
    expect_equal(c.get_json("does_not_exist", default={"d": 1}), {"d": 1}, "JSON default")
    RemoteConfig.setup(defaults={"welcome_message": "dict wins", "extra": "x"},
                       defaults_plist="RemoteConfigDefaults", minimum_fetch_interval=3600)
    expect_equal(c.get_string("welcome_message"), "dict wins", "dict over plist")
    expect_equal(c.get_long("max_items"), 25, "plist kept")
    expect_equal(c.get_string("extra"), "x", "dict-only key")
    t.passed()


def test_remote_config_settings(t: TestContext) -> None:
    c = config()
    c.minimum_fetch_interval = 120
    c.fetch_timeout = 7
    expect_equal(c.minimum_fetch_interval, 120.0, "minimum fetch interval")
    expect_equal(c.fetch_timeout, 7.0, "fetch timeout kept with the interval change")
    c.set_minimum_fetch_interval(3600)
    expect_equal((c.minimum_fetch_interval, c.fetch_timeout), (3600.0, 7.0), "both settings")
    c.ensure_initialized(t.step(lambda error: (expect(error is None, error), t.passed())))


def test_remote_config_fetch_fails_cleanly_offline(t: TestContext) -> None:
    c = config()
    c.fetch_timeout = 10

    def activated(changed, error) -> None:
        expect(changed is False, "nothing fetched, nothing changed")
        expect_equal(c.get_long("max_items"), 25, "defaults still served")
        t.passed()

    def fetched(status, error) -> None:
        # the demo project has no Remote Config backend: the fetch must fail,
        # not hang, and the app keeps working on defaults
        expect(error is not None, "no backend for the demo project")
        expect(status in (RemoteConfigFetchStatus.FAILURE, RemoteConfigFetchStatus.THROTTLED), status)
        # NO_FETCH_YET when it failed before reaching a server (the demo
        # project's installation cannot be registered)
        expect(c.last_fetch_status in (RemoteConfigFetchStatus.NO_FETCH_YET, RemoteConfigFetchStatus.FAILURE,
                                       RemoteConfigFetchStatus.THROTTLED), c.last_fetch_status)
        c.activate(t.step(activated))

    c.fetch(t.step(fetched), expiration_duration=0)


def test_remote_config_custom_signals_and_listener(t: TestContext) -> None:
    c = config()

    def signals_set(error) -> None:
        expect(error is None, error)
        listener = c.add_on_config_update_listener(lambda update, error: None)
        listener.remove()
        listener.remove()  # safe twice
        try:
            c.set_custom_signals({"flag": True})  # type: ignore[dict-item]
        except TypeError:
            t.passed()
        else:
            t.fail("a bool custom signal must raise TypeError")

    c.set_custom_signals({"plan": "pro", "level": 3, "removed": None}, t.step(signals_set))


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

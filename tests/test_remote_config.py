from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import NSObject, ObjCClass, ns_from_py, objc_property, py_from_ns

import pyios_firebase.remote_config as rc_module
from pyios_firebase.remote_config import (
    ConfigUpdate,
    RemoteConfig,
    RemoteConfigFetchStatus,
    RemoteConfigSource,
    RemoteConfigValue,
    load_defaults,
)

XML = """<?xml version="1.0" encoding="utf-8"?>
<defaults>
  <entry><key>welcome</key><value>Hello</value></entry>
  <entry><key>empty</key></entry>
  <entry><value>no key</value></entry>
</defaults>
"""


def native_value(string, source=RemoteConfigSource.DEFAULT):
    return SimpleNamespace(
        stringValue=string,
        numberValue=SimpleNamespace(
            doubleValue=float(string) if string.replace(".", "").isdigit() else 0.0,
            longLongValue=int(float(string))
            if string.replace(".", "").isdigit()
            else 0,
        ),
        boolValue=string in ("true", "1", "yes"),
        dataValue=ns_from_py(string.encode()),
        source=source,
    )


def test_load_defaults(tmp_path):
    path = tmp_path / "defaults.xml"
    path.write_text(XML)
    assert load_defaults(path) == {"welcome": "Hello", "empty": ""}


def test_setup_merges_defaults_and_fetches(tmp_path, monkeypatch, blocks):
    path = tmp_path / "defaults.xml"
    path.write_text(XML)
    monkeypatch.setattr(
        rc_module,
        "load_plist_defaults",
        lambda name: {"welcome": "plist", "only_plist": "1"},
    )
    settings = SimpleNamespace(minimumFetchInterval=43200.0, fetchTimeout=60.0)
    monkeypatch.setattr(
        rc_module,
        "objc_class",
        lambda name: Recorder(
            {"alloc": lambda: Recorder({"init": lambda: SimpleNamespace()})}
        ),
    )
    native = Recorder()
    native.configSettings = settings
    monkeypatch.setattr(RemoteConfig, "_instance", RemoteConfig(native))
    statuses = []
    RemoteConfig.setup(
        defaults={"empty": "dict"},
        defaults_file=path,
        defaults_plist="Defaults",
        minimum_fetch_interval=10,
        callback=lambda s, e: statuses.append((s, e)),
    )
    assert native.configSettings.minimumFetchInterval == 10.0
    assert native.configSettings.fetchTimeout == 60.0  # kept
    (ns_defaults,) = native.last("setDefaults_")
    assert py_from_ns(ns_defaults) == {
        "welcome": "Hello",
        "empty": "dict",
        "only_plist": "1",
    }
    fire(native.block("fetchAndActivateWithCompletionHandler_"), 0, None)
    assert statuses == [("success_fetched_from_remote", None)]
    assert not blocks


def test_fetch_activate_and_initialize(blocks):
    native, out = Recorder(), []
    config = RemoteConfig(native)
    config.fetch(lambda s, e: out.append(("fetch", s, e)))
    fire(
        native.block("fetchWithCompletionHandler_"),
        RemoteConfigFetchStatus.THROTTLED,
        make_error("slow down", 8002),
    )
    config.fetch(expiration_duration=0)
    assert native.last("fetchWithExpirationDuration_completionHandler_")[0] == 0.0
    config.activate(lambda changed, e: out.append(("activate", changed, e)))
    fire(native.block("activateWithCompletion_"), True, None)
    config.ensure_initialized(lambda e: out.append(("init", e)))
    fire(native.block("ensureInitializedWithCompletionHandler_"), None)
    assert out[0][:2] == ("fetch", 3) and out[0][2].code == 8002
    assert out[1] == ("activate", True, None)
    assert out[2] == ("init", None)


def test_values_and_keys():
    native = Recorder(
        {
            "configValueForKey_": lambda: native_value("42"),
            "configValueForKey_source_": lambda: native_value(
                "7", RemoteConfigSource.REMOTE
            ),
            "allKeysFromSource_": lambda: ns_from_py(["a", "b"]),
            "keysWithPrefix_": lambda: ObjCClass("NSSet").setWithArray_(
                ns_from_py(["ui_a", "ui_b"])
            ),
            "defaultValueForKey_": None,
        }
    )
    config = RemoteConfig(native)
    value = config.get_value("answer")
    assert value == RemoteConfigValue(
        string="42",
        number=42.0,
        boolean=False,
        data=b"42",
        source=RemoteConfigSource.DEFAULT,
    )
    assert config.get_value("x", source=RemoteConfigSource.REMOTE).string == "7"
    assert config.get_long("answer") == 42 and config.get_number("answer") == 42.0
    assert config.get_data("answer") == b"42"
    assert config.all_keys(RemoteConfigSource.DEFAULT) == ["a", "b"]
    assert config.keys_with_prefix("ui_") == {"ui_a", "ui_b"}
    assert config.default_value("missing") is None


def test_value_json():
    for text, expected in [('{"a": 1}', {"a": 1}), ("", "dflt"), ("not json", "dflt")]:
        value = RemoteConfigValue(
            string=text, number=0.0, boolean=False, data=text.encode(), source=0
        )
        assert value.json(default="dflt") == expected


class FakeConfigUpdate(NSObject):
    """Stands in for FIRRemoteConfigUpdate: only has ``updatedKeys``."""

    updatedKeys = objc_property()


def test_update_listener(blocks):
    registration = Recorder()
    native, seen = Recorder({"addOnConfigUpdateListener_": registration}), []
    listener = RemoteConfig(native).add_on_config_update_listener(
        lambda u, e: seen.append((u, e))
    )
    block = native.block("addOnConfigUpdateListener_")
    update = FakeConfigUpdate.new()
    update.updatedKeys = ObjCClass("NSSet").setWithArray_(ns_from_py(["a", "b"]))
    fire(block, update, None)
    fire(block, None, make_error("stream closed", 8001))
    assert seen[0] == (ConfigUpdate(frozenset({"a", "b"})), None)
    assert seen[1][0] is None and seen[1][1].description == "stream closed"
    assert block in blocks  # alive between updates
    listener.remove()
    listener.remove()
    assert registration.calls == [("remove", ())]
    assert not blocks


def test_custom_signals(monkeypatch, blocks):
    monkeypatch.setattr(rc_module, "objc_class", lambda name: ObjCClass(name))
    native = Recorder()
    RemoteConfig(native).set_custom_signals({"plan": "pro", "level": 3, "old": None})
    sent = native.last("setCustomSignals_withCompletion_")[0]
    assert (
        py_from_ns(sent.objectForKey_("plan")) == "pro"
        and py_from_ns(sent.objectForKey_("level")) == 3
    )
    assert sent.objectForKey_("old") == ObjCClass("NSNull").null()
    with pytest.raises(TypeError, match="give a string or a number"):
        RemoteConfig(native).set_custom_signals({"flag": True})

import pytest

import pyios_firebase.performance as performance_module
from pyios_firebase.performance import HTTPMethod, HTTPMetric, Performance, Trace


class FakeNative:
    """A FIRTrace / FIRHTTPMetric: records calls, keeps metrics and attributes."""

    def __init__(self):
        self.calls = []
        self.metrics = {}
        self.attributes = {}
        self.responseCode = 0
        self.requestPayloadSize = 0
        self.responsePayloadSize = 0
        self.responseContentType = None

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def incrementMetric_byInt_(self, name, by):
        self.metrics[name] = self.metrics.get(name, 0) + by

    def setIntValue_forMetric_(self, value, name):
        self.metrics[name] = value

    def valueForIntMetric_(self, name):
        return self.metrics.get(name, 0)

    def setValue_forAttribute_(self, value, name):
        self.attributes[name] = value

    def valueForAttribute_(self, name):
        return self.attributes.get(name)

    def removeAttribute_(self, name):
        self.attributes.pop(name, None)


class FakeClass:
    def __init__(self, make):
        self.make = make
        self.args = None

    def __getattr__(self, name):
        def method(*args):
            self.args = (name, args)
            return self.make() if name != "alloc" else self

        return method


@pytest.fixture
def sdk(monkeypatch):
    state = {"configured": True, "enabled": True, "metric": None}

    class SharedPerformance:
        isDataCollectionEnabled = staticmethod(lambda: state["enabled"])
        isInstrumentationEnabled = True
        calls = []

        def traceWithName_(self, name):
            self.calls.append(name)
            return FakeNative() if state["enabled"] else None

        def setDataCollectionEnabled_(self, enabled):
            state["enabled"] = enabled

    shared = SharedPerformance()

    def make_metric():
        state["metric"] = FakeNative() if state["enabled"] else None
        return state["metric"]

    classes = {
        "FIRPerformance": FakeClass(lambda: shared),
        "FIRApp": FakeClass(lambda: object() if state["configured"] else None),
        "NSURL": FakeClass(lambda: "url"),
        "FIRHTTPMetric": FakeClass(make_metric),
    }
    monkeypatch.setattr(performance_module, "objc_class", classes.__getitem__)
    monkeypatch.setattr(Performance, "_shared", None)
    return state, shared, classes


def test_trace_with_metrics_and_attributes(sdk):
    _state, shared, _classes = sdk
    with Performance.performance().trace("  load_feed ") as trace:
        assert isinstance(trace, Trace) and trace.running and trace.active
        assert trace.name == "load_feed" and shared.calls == ["load_feed"]
        trace.increment_metric("items", 3)
        trace.increment_metric("items")
        trace.set_metric("bytes", 2048)
        trace.put_attribute("source", "cache")
        assert trace.get_metric("items") == 4
        assert trace.get_attribute("source") == "cache"
        assert trace.attributes == {"source": "cache"}
        trace.remove_attribute("source")
    assert trace.native.calls == ["start", "stop"]
    assert not trace.running
    with pytest.raises(RuntimeError, match="already started"):
        trace.start()
    with pytest.raises(RuntimeError, match="not running"):
        trace.stop()
    with pytest.raises(RuntimeError, match="before changing its metrics"):
        trace.increment_metric("items")


@pytest.mark.parametrize(
    ("call", "error", "message"),
    [
        (lambda p: p.trace(""), ValueError, "cannot be empty"),
        (lambda p: p.trace("_internal"), ValueError, "reserved"),
        (lambda p: p.trace("x" * 101), ValueError, "at most 100"),
        (lambda p: p.trace(3), TypeError, "must be a str"),
        (lambda p: p.start_trace("t").increment_metric("_m"), ValueError, "reserved"),
        (lambda p: p.start_trace("t").set_metric("m", 1.5), TypeError, "int"),
        (lambda p: p.start_trace("t").set_metric("m", 2**63), ValueError, "64 bits"),
        (
            lambda p: p.trace("t").put_attribute("firebase_x", "v"),
            ValueError,
            "reserved",
        ),
        (lambda p: p.trace("t").put_attribute("a-b", "v"), ValueError, "letters"),
        (lambda p: p.trace("t").put_attribute("a" * 41, "v"), ValueError, "at most 40"),
        (lambda p: p.trace("t").put_attribute("a", ""), ValueError, "cannot be empty"),
        (
            lambda p: p.trace("t").put_attribute("a", "v" * 101),
            ValueError,
            "at most 100",
        ),
    ],
)
def test_bad_names_raise_instead_of_being_dropped(sdk, call, error, message):
    with pytest.raises(error, match=message):
        call(Performance.performance())


def test_at_most_five_attributes(sdk):
    trace = Performance.performance().trace("t")
    for i in range(5):
        trace.put_attribute(f"a{i}", "v")
    trace.put_attribute("a0", "changed")  # replacing one is fine
    with pytest.raises(ValueError, match="at most 5"):
        trace.put_attribute("a5", "v")


def test_trace_before_configure_raises(sdk):
    state, shared, _classes = sdk
    state["configured"] = False
    with pytest.raises(RuntimeError, match="configure Firebase"):
        Performance.performance().trace("t")
    assert not shared.calls  # the SDK would have aborted the app


def test_inactive_when_collection_is_off(sdk):
    state, _shared, _classes = sdk
    performance = Performance.performance()
    performance.data_collection_enabled = False
    assert performance.data_collection_enabled is False
    with performance.trace("t") as trace:
        assert not trace.active
        trace.increment_metric("m", 2)
        trace.put_attribute("a", "b")
        assert trace.get_metric("m") == 0 and trace.attributes == {}
    metric = HTTPMetric("https://example.com")
    assert not metric.active and metric.response_code == 0
    metric.response_code = 200
    state["enabled"] = True


def test_http_metric(sdk):
    state, _shared, classes = sdk
    with HTTPMetric("https://api.example.com/feed?x=1", HTTPMethod.POST) as metric:
        metric.request_payload_size = 12
        metric.response_code = 201
        metric.response_payload_size = 3400
        metric.response_content_type = "application/json"
        metric.put_attribute("api", "feed")
    native = state["metric"]
    assert classes["FIRHTTPMetric"].args == ("initWithURL_HTTPMethod_", ("url", 2))
    assert native.calls == ["start", "stop"]
    assert (native.responseCode, native.requestPayloadSize) == (201, 12)
    assert metric.response_payload_size == 3400
    assert metric.response_content_type == "application/json"
    assert metric.attributes == {"api": "feed"}
    for bad in ("ftp://x", "example.com", "https://"):
        with pytest.raises(ValueError, match="http"):
            HTTPMetric(bad)
    with pytest.raises(ValueError, match="unknown HTTP method"):
        HTTPMetric("https://x.com", 42)

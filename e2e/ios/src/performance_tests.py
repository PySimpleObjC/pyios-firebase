"""Performance Monitoring end-to-end tests (no emulator exists: the SDK runs
for real; nothing reaches a console for the demo project)."""

from __future__ import annotations

import time
import urllib.request

from runner import TestContext, expect, expect_equal

from pyios_firebase.performance import HTTPMethod, HTTPMetric, Performance


def test_performance_traces(t: TestContext) -> None:
    performance = Performance.performance()
    expect(performance.data_collection_enabled, "collection on by default")
    with performance.trace("e2e_load") as trace:
        if not trace.active:
            t.skipped("the SDK made no trace (Performance Monitoring disabled)")
            return
        expect(trace.running, "started by the with statement")
        trace.increment_metric("items", 3)
        trace.increment_metric("items", 2)
        trace.set_metric("bytes", 2048)
        trace.put_attribute("source", "cache")
        trace.put_attribute("screen", "feed")
        expect_equal(trace.get_metric("items"), 5, "incremented metric")
        expect_equal(trace.get_metric("bytes"), 2048, "set metric")
        expect_equal(trace.attributes, {"source": "cache", "screen": "feed"}, "attributes")
        trace.remove_attribute("screen")
        expect_equal(trace.get_attribute("screen"), None, "removed")
        time.sleep(0.05)
    expect(not trace.running, "stopped by the with statement")

    started = performance.start_trace("e2e_manual")
    expect(started.running, "start_trace starts it")
    started.stop()
    for name, call, error in [
        ("reserved trace name", lambda: performance.trace("_x"), ValueError),
        ("metric when stopped", lambda: started.increment_metric("m"), RuntimeError),
        ("stop twice", started.stop, RuntimeError),
        ("bad attribute", lambda: performance.trace("t").put_attribute("ga_x", "v"), ValueError),
    ]:
        try:
            call()
        except error:
            continue
        raise AssertionError(f"{name}: no {error.__name__}")
    t.passed()


def test_performance_http_metric(t: TestContext) -> None:
    # a request made from Python, which the SDK cannot see by itself: the
    # Firestore emulator answers plain HTTP on its root
    url = "http://127.0.0.1:8080/"
    with HTTPMetric(url, HTTPMethod.GET) as metric:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read()
            metric.response_code = response.status
            metric.response_content_type = response.headers.get_content_type()
        metric.response_payload_size = len(body)
        metric.request_payload_size = 0
        metric.put_attribute("api", "emulator")
    if not metric.active:
        t.skipped("the SDK made no HTTP metric (Performance Monitoring disabled)")
        return
    expect_equal(metric.response_code, 200, "status")
    expect_equal(metric.response_payload_size, len(body), "payload size")
    expect(metric.response_content_type, "content type")
    expect_equal(metric.attributes, {"api": "emulator"}, "attributes")
    try:
        HTTPMetric("ftp://example.com")
    except ValueError:
        t.passed()
        return
    t.fail("a non-HTTP URL was accepted")


def test_performance_settings(t: TestContext) -> None:
    performance = Performance.performance()
    expect(isinstance(performance.instrumentation_enabled, bool), "instrumentation flag")
    performance.data_collection_enabled = False
    try:
        expect_equal(performance.data_collection_enabled, False, "collection off")
        with performance.trace("e2e_off") as trace:
            expect(not trace.active, "no trace while collection is off")
            trace.increment_metric("m")  # does nothing, does not fail
        expect(not HTTPMetric("https://example.com").active, "no HTTP metric either")
    finally:
        performance.data_collection_enabled = True
    expect(performance.data_collection_enabled, "collection back on")
    t.passed()


TESTS = [(name, fn) for name, fn in globals().items() if name.startswith("test_performance")]

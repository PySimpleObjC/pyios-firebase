# Performance Monitoring

[Performance Monitoring](https://firebase.google.com/docs/perf-mon) measures
how fast the app is for real users: app start, screen rendering and network
requests by itself, and your own code with **traces**.

```python
from pyios_firebase.performance import Performance

with Performance.performance().trace("load_feed") as trace:
    items = load_feed()
    trace.increment_metric("items", len(items))
```

## Installation

Add the **`FirebasePerformance`** Swift package product
([Installation](../getting-started/installation.md)). Data shows in the
console under **Performance** within a few hours (a day for the first data).

## What is measured by itself

| Trace | Measures |
|---|---|
| App start (`_app_start`) | From launch to the first frame |
| App in foreground / background | Time spent in each |
| Screen rendering | Slow and frozen frames, per native screen |
| Network requests | Every `NSURLSession` request: time, size, status |

!!! note "Python's network requests are not seen"
    `urllib`, `requests`, `httpx` and `aiohttp` use their own sockets, not
    `NSURLSession`, so the SDK does not see them. Measure them with
    [`HTTPMetric`](#measure-a-network-request). Firebase's own requests are
    native, and are measured.

## Custom code traces

A trace measures the time between its start and its stop:

```python
performance = Performance.performance()

with performance.trace("load_feed") as trace:      # started and stopped for you
    feed = load_feed()

trace = performance.start_trace("checkout")          # or by hand
...
trace.stop()
```

Traces are **asynchronous-friendly**: start one before a Firebase call and
stop it in the callback.

```python
def open_profile(uid):
    trace = performance.start_trace("open_profile")

    def on_profile(snapshot, error):
        trace.put_attribute("found", "yes" if snapshot and snapshot.exists else "no")
        trace.stop()
        show(snapshot)

    db.document_with_path(f"users/{uid}").get_document(on_profile)
```

### Metrics

Counters inside a trace, for example items loaded or cache hits:

```python
trace.increment_metric("cache_hits")          # +1
trace.increment_metric("items", 25)
trace.set_metric("bytes", len(payload))
trace.get_metric("items")                     # 25
```

Metrics change only while the trace is running: otherwise `RuntimeError`.

### Attributes

Up to 5 per trace, to filter the data in the console:

```python
trace.put_attribute("source", "cache")
trace.put_attribute("tier", "premium")
trace.get_attribute("source"), trace.attributes
trace.remove_attribute("tier")
```

## Measure a network request

```python
import httpx

from pyios_firebase.performance import HTTPMethod, HTTPMetric

with HTTPMetric("https://api.example.com/feed", HTTPMethod.GET) as metric:
    response = httpx.get("https://api.example.com/feed")
    metric.response_code = response.status_code
    metric.response_payload_size = len(response.content)
    metric.response_content_type = response.headers.get("content-type")
```

Set `request_payload_size` for uploads. An HTTP metric takes attributes
like a trace.

## Names

| | Rule |
|---|---|
| Trace and metric names | 1 to 100 characters, not starting with `_`, no spaces at the ends |
| Attribute names | Up to 40 letters, digits and `_`; prefixes `firebase_`, `google_`, `ga_` are reserved |
| Attribute values | 1 to 100 characters |
| Attributes per trace | 5 |

The SDK drops a trace, metric or attribute that breaks these rules quietly.
pyios-firebase raises `ValueError` instead.

## Mistakes

| Mistake | Raises |
|---|---|
| A trace before `core.configure()` | `RuntimeError` (the SDK would abort the app) |
| `start()` twice, `stop()` before `start()` | `RuntimeError` |
| Changing a metric of a trace that is not running | `RuntimeError` |
| A bad name, a sixth attribute | `ValueError` |
| An `HTTPMetric` with a non-`http(s)` URL | `ValueError` |

## Turn it off

```python
performance.data_collection_enabled = False         # kept across launches
performance.instrumentation_enabled = False         # the automatic traces, from the next launch
```

`firebase_performance_collection_enabled` and
`firebase_performance_instrumentation_enabled` = `NO` in `Info.plist` set them
at build time. While collection is off, traces and HTTP metrics are
**inactive** (`trace.active` is `False`): every method does nothing, so the
code needs no `if`.

## Debugging

Run the app with `-FIRDebugEnabled` to see each trace in the console log as
it is sent.

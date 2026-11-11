"""Firebase Performance Monitoring: custom code traces and network requests.

    from pyios_firebase.performance import HTTPMethod, HTTPMetric, Performance

    with Performance.performance().trace("load_feed") as trace:
        items = load_feed()
        trace.increment_metric("items", len(items))
        trace.put_attribute("source", "cache")

    metric = HTTPMetric("https://api.example.com/feed", HTTPMethod.GET)
    metric.start()
    ...                                   # make the request
    metric.response_code = 200
    metric.response_payload_size = len(body)
    metric.stop()

The SDK measures app start, screen rendering and the requests made with
``NSURLSession`` by itself. Requests made from Python (``urllib``,
``requests``, ``httpx``...) do not use ``NSURLSession``: measure them with
``HTTPMetric``.

Bad names and values raise ``ValueError`` (the SDK would drop the trace,
metric or attribute quietly). While data collection is off, traces and HTTP
metrics are inactive (``active`` is ``False``) and do nothing.

Needs the ``FirebasePerformance`` framework.
"""

from __future__ import annotations

__all__ = (
    "HTTPMethod",
    "HTTPMetric",
    "Performance",
    "Trace",
)

import re
from types import TracebackType
from typing import Any, ClassVar, Final, Self
from urllib.parse import urlsplit

from ..types import ObjCObject
from ..util import objc_class, to_python

_MAX_NAME: Final = 100
_MAX_ATTRIBUTE_NAME: Final = 40
_MAX_ATTRIBUTE_VALUE: Final = 100
_MAX_ATTRIBUTES: Final = 5
_MAX_URL: Final = 2000
_ATTRIBUTE_NAME: Final = re.compile(r"[A-Za-z0-9_]*\Z")
_RESERVED_ATTRIBUTE_PREFIXES: Final = ("firebase_", "google_", "ga_")
_INT64: Final = 2**63


class HTTPMethod:
    """The method of an ``HTTPMetric``'s request (``FIRHTTPMethod``)."""

    GET: Final = 0
    PUT: Final = 1
    POST: Final = 2
    DELETE: Final = 3
    HEAD: Final = 4
    PATCH: Final = 5
    OPTIONS: Final = 6
    TRACE: Final = 7
    CONNECT: Final = 8


_METHODS: Final = {
    name: value for name, value in vars(HTTPMethod).items() if isinstance(value, int)
}


def _name(name: str, what: str) -> str:
    """A trace or metric name, as the SDK checks it (``FPRReservableName``)."""
    if not isinstance(name, str):
        raise TypeError(f"a {what} name must be a str, not {type(name).__name__}")
    stripped = name.strip(" \t")
    if not stripped:
        raise ValueError(f"a {what} name cannot be empty")
    if stripped.startswith("_"):
        raise ValueError(f"invalid {what} name {name!r}: the '_' prefix is reserved")
    if len(stripped) > _MAX_NAME:
        raise ValueError(f"a {what} name can be at most {_MAX_NAME} characters")
    return stripped


def _attribute(name: str, value: str) -> tuple[str, str]:
    """An attribute, as the SDK checks it (``FPRReservableAttributeName``)."""
    if not isinstance(name, str) or not isinstance(value, str):
        raise TypeError("attribute names and values are str")
    stripped = name.strip(" \t")
    if stripped.startswith(_RESERVED_ATTRIBUTE_PREFIXES):
        raise ValueError(
            f"invalid attribute name {name!r}: the prefixes firebase_, google_ and "
            "ga_ are reserved"
        )
    if not stripped:
        raise ValueError("an attribute name cannot be empty")
    if not _ATTRIBUTE_NAME.match(stripped):
        raise ValueError(
            f"invalid attribute name {name!r}: letters, digits and underscores only"
        )
    if len(stripped) > _MAX_ATTRIBUTE_NAME:
        raise ValueError(
            f"an attribute name can be at most {_MAX_ATTRIBUTE_NAME} characters"
        )
    if not value:
        raise ValueError("an attribute value cannot be empty")
    if len(value) > _MAX_ATTRIBUTE_VALUE:
        raise ValueError(
            f"an attribute value can be at most {_MAX_ATTRIBUTE_VALUE} characters"
        )
    return stripped, value


class _Attributable:
    """Custom attributes, shared by ``Trace`` and ``HTTPMetric``."""

    _native: ObjCObject | None

    @property
    def active(self) -> bool:
        """``False`` when the SDK made nothing (data collection is off): then
        every method does nothing."""
        return self._native is not None

    @property
    def native(self) -> ObjCObject | None:
        """The native object, or ``None`` when inactive."""
        return self._native

    @property
    def attributes(self) -> dict[str, str]:
        """The custom attributes."""
        if self._native is None:
            return {}
        return dict(to_python(self._native.attributes) or {})

    def put_attribute(self, name: str, value: str) -> None:
        """Set a custom attribute (at most 5), to filter by in the console.

        Args:
            name: up to 40 letters, digits and underscores (the prefixes
                ``firebase_``, ``google_`` and ``ga_`` are reserved).
            value: 1 to 100 characters.

        Raises:
            ValueError: an invalid name or value, or a sixth attribute.
        """
        name, value = _attribute(name, value)
        if self._native is None:
            return
        attributes = self.attributes
        if name not in attributes and len(attributes) >= _MAX_ATTRIBUTES:
            raise ValueError(f"at most {_MAX_ATTRIBUTES} custom attributes")
        self._native.setValue_forAttribute_(value, name)

    def get_attribute(self, name: str) -> str | None:
        """A custom attribute's value, or ``None``.

        Args:
            name: the attribute's name.
        """
        if self._native is None:
            return None
        value = self._native.valueForAttribute_(name)
        return None if value is None else str(value)

    def remove_attribute(self, name: str) -> None:
        """Remove a custom attribute.

        Args:
            name: the attribute's name.
        """
        if self._native is not None:
            self._native.removeAttribute_(name)


class _Timed(_Attributable):
    """Start and stop, once each, and the ``with`` statement."""

    _state: str = "new"  # "new", "started", "stopped"

    def _what(self) -> str:
        raise NotImplementedError

    def start(self) -> None:
        """Start measuring.

        Raises:
            RuntimeError: it was already started.
        """
        if self._state != "new":
            raise RuntimeError(f"the {self._what()} was already started")
        self._state = "started"
        if self._native is not None:
            self._native.start()

    def stop(self) -> None:
        """Stop measuring, and send it.

        Raises:
            RuntimeError: it is not running.
        """
        if self._state != "started":
            raise RuntimeError(f"the {self._what()} is not running")
        self._state = "stopped"
        if self._native is not None:
            self._native.stop()

    @property
    def running(self) -> bool:
        """``True`` between ``start`` and ``stop``."""
        return self._state == "started"

    def __enter__(self) -> Self:
        if self._state == "new":
            self.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        exception: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._state == "started":
            self.stop()


class Trace(_Timed):
    """A custom code trace: the time between ``start`` and ``stop``, with your
    own metrics (counters) and attributes. Get it from ``Performance``.

    Use it with ``with`` to start and stop it::

        with Performance.performance().trace("checkout") as trace:
            trace.increment_metric("items", 3)

    Args:
        native: the native ``FIRTrace``, or ``None`` (inactive).
        name: the trace's name.
    """

    def __init__(self, native: ObjCObject | None, name: str) -> None:
        self._native = native
        self._name = name
        self._state = "new"

    def _what(self) -> str:
        return f"trace {self._name!r}"

    @property
    def name(self) -> str:
        """The trace's name."""
        return self._name

    def _metric(self, name: str) -> str:
        metric = _name(name, "metric")
        if self._state != "started":
            raise RuntimeError(f"start the {self._what()} before changing its metrics")
        return metric

    def increment_metric(self, name: str, by: int = 1) -> None:
        """Add to a metric (a metric starts at 0).

        Args:
            name: the metric's name (as for trace names).
            by: the amount to add (negative to subtract).

        Raises:
            ValueError: an invalid name.
            RuntimeError: the trace is not running.
        """
        metric = self._metric(name)
        if self._native is not None:
            self._native.incrementMetric_byInt_(metric, _int64(by))

    def set_metric(self, name: str, value: int) -> None:
        """Set a metric.

        Args:
            name: the metric's name.
            value: the value.

        Raises:
            ValueError: an invalid name.
            RuntimeError: the trace is not running.
        """
        metric = self._metric(name)
        if self._native is not None:
            self._native.setIntValue_forMetric_(_int64(value), metric)

    def get_metric(self, name: str) -> int:
        """A metric's value (0 if it was never set).

        Args:
            name: the metric's name.
        """
        if self._native is None:
            return 0
        return int(self._native.valueForIntMetric_(name.strip(" \t")))

    def __repr__(self) -> str:
        return f"Trace({self._name!r}, {self._state})"


def _int64(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"metric values are int, not {type(value).__name__}")
    if not -_INT64 <= value < _INT64:
        raise ValueError("metric values must fit in 64 bits")
    return value


class HTTPMetric(_Timed):
    """A network request you measure yourself (for requests made from Python,
    which the SDK does not see). Start it before sending the request, set the
    response fields, then stop it.

    Args:
        url: the request's ``http`` or ``https`` URL.
        method: an ``HTTPMethod``.

    Raises:
        ValueError: not an ``http(s)`` URL, or an unknown method.
    """

    def __init__(self, url: str, method: int = HTTPMethod.GET) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"an HTTP metric needs an http(s) URL, not {url!r}")
        if method not in _METHODS.values():
            raise ValueError(f"unknown HTTP method {method!r}: use HTTPMethod")
        self._url = url
        self._state = "new"
        native_url = objc_class("NSURL").URLWithString_(url[:_MAX_URL])
        self._native = (
            objc_class("FIRHTTPMetric")
            .alloc()
            .initWithURL_HTTPMethod_(native_url, method)
        )

    def _what(self) -> str:
        return f"HTTP metric for {self._url!r}"

    @property
    def url(self) -> str:
        """The request's URL."""
        return self._url

    def _get(self, name: str, default: Any) -> Any:
        return default if self._native is None else getattr(self._native, name)

    def _set(self, name: str, value: Any) -> None:
        if self._native is not None:
            setattr(self._native, name, value)

    @property
    def response_code(self) -> int:
        """The HTTP status code (set it before ``stop``)."""
        return int(self._get("responseCode", 0))

    @response_code.setter
    def response_code(self, code: int) -> None:
        self._set("responseCode", int(code))

    @property
    def request_payload_size(self) -> int:
        """The request body's size in bytes."""
        return int(self._get("requestPayloadSize", 0))

    @request_payload_size.setter
    def request_payload_size(self, size: int) -> None:
        self._set("requestPayloadSize", int(size))

    @property
    def response_payload_size(self) -> int:
        """The response body's size in bytes."""
        return int(self._get("responsePayloadSize", 0))

    @response_payload_size.setter
    def response_payload_size(self, size: int) -> None:
        self._set("responsePayloadSize", int(size))

    @property
    def response_content_type(self) -> str | None:
        """The response's ``Content-Type``, for example ``"application/json"``."""
        value = self._get("responseContentType", None)
        return None if value is None else str(value)

    @response_content_type.setter
    def response_content_type(self, content_type: str | None) -> None:
        self._set("responseContentType", content_type)

    def __repr__(self) -> str:
        return f"HTTPMetric({self._url!r}, {self._state})"


class Performance:
    """Performance Monitoring. Get it with ``Performance.performance()``.

    Args:
        native: the native ``FIRPerformance``.
    """

    _shared: ClassVar[Performance | None] = None

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def performance(cls) -> Performance:
        """The shared ``Performance``."""
        if cls._shared is None:
            cls._shared = cls(objc_class("FIRPerformance").sharedInstance())
        return cls._shared

    @property
    def native(self) -> ObjCObject:
        """The ``FIRPerformance``."""
        return self._native

    @property
    def data_collection_enabled(self) -> bool:
        """Collect and send data (custom traces too). Setting it is kept across
        launches; to start with it off, set
        ``firebase_performance_collection_enabled`` to ``NO`` in ``Info.plist``."""
        value = self._native.isDataCollectionEnabled
        return bool(value() if callable(value) else value)

    @data_collection_enabled.setter
    def data_collection_enabled(self, enabled: bool) -> None:
        self._native.setDataCollectionEnabled_(bool(enabled))

    @property
    def instrumentation_enabled(self) -> bool:
        """Measure app start, screens and ``NSURLSession`` requests automatically.
        Takes effect at the next launch; ``firebase_performance_instrumentation_enabled``
        in ``Info.plist`` sets it at build time."""
        value = self._native.isInstrumentationEnabled
        return bool(value() if callable(value) else value)

    @instrumentation_enabled.setter
    def instrumentation_enabled(self, enabled: bool) -> None:
        self._native.setInstrumentationEnabled_(bool(enabled))

    def trace(self, name: str) -> Trace:
        """A new trace, not started (use ``with``, or ``start()`` / ``stop()``).

        Args:
            name: 1 to 100 characters, not starting with ``_``.

        Returns:
            A ``Trace`` (inactive when data collection is off).

        Raises:
            ValueError: an invalid name.
            RuntimeError: Firebase is not configured yet (the SDK would abort
                the app).
        """
        checked = _name(name, "trace")
        if objc_class("FIRApp").defaultApp() is None:
            raise RuntimeError(
                "configure Firebase (core.configure()) before making traces"
            )
        return Trace(self._native.traceWithName_(checked), checked)

    def start_trace(self, name: str) -> Trace:
        """A new trace, already started.

        Args:
            name: as for ``trace``.

        Returns:
            The running ``Trace``.

        Raises:
            ValueError: an invalid name.
            RuntimeError: Firebase is not configured yet.
        """
        trace = self.trace(name)
        trace.start()
        return trace

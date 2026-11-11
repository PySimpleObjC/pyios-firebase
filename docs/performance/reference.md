# Performance Monitoring reference

## At a glance

- `Performance.performance()`: `trace(name)`, `start_trace(name)`, `data_collection_enabled`, `instrumentation_enabled`
- `Trace`: `name`, `start()`, `stop()`, `running`, `active`, `increment_metric(name, by=1)`, `set_metric(name, value)`, `get_metric(name)`, `put_attribute(name, value)`, `get_attribute(name)`, `remove_attribute(name)`, `attributes`; a context manager
- `HTTPMetric(url, method)`: `start()`, `stop()`, `running`, `active`, `response_code`, `request_payload_size`, `response_payload_size`, `response_content_type`, the attribute methods; a context manager; `HTTPMethod`


## `pyios_firebase.performance`

::: pyios_firebase.performance

# Cloud Functions reference

## At a glance

- `Functions.functions(region=None, custom_domain=None)`, `use_emulator(host, port)`
- `https_callable(name, require_limited_use_app_check_tokens=False)`, `https_callable_from_url(url, ...)`
- `HTTPSCallable.call(callback, data=None)`, `timeout_interval`
- `FunctionsError` (`code`, `name`, `description`, `details`), `FunctionsErrorCode`

## `pyios_firebase.functions`

::: pyios_firebase.functions

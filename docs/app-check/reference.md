# App Check reference

## At a glance

- Providers (before `core.configure()`): `use_debug_provider()`, `use_device_check_provider()`, `use_app_attest_provider()`, `use_recaptcha_provider(site_key)`, `use_custom_provider(provider)`; `running_in_simulator()`; `initialize_debug_appcheck()` (0.1 name)
- `AppCheckProvider` (`get_token(callback)`, `get_limited_use_token(callback)`), `AppCheckToken(token, expiration_date)`
- `AppCheck.app_check()`: `token(cb, force_refresh)`, `limited_use_token(cb)`, `add_token_listener(listener)` → `AppCheckTokenListener`, `is_token_auto_refresh_enabled`, `debug_token()`
- `AppCheckErrorCode`, `DEBUG_TOKEN_ENVIRONMENT_VARIABLE`

## `pyios_firebase.app_check`

::: pyios_firebase.app_check

# Remote Config reference

## At a glance

- `RemoteConfig.remote_config()`, `RemoteConfig.setup(defaults, defaults_file, defaults_plist, minimum_fetch_interval, callback)`
- Settings: `minimum_fetch_interval`, `fetch_timeout`, `last_fetch_time`, `last_fetch_status`
- Defaults: `set_defaults(dict)`, `set_defaults_from_plist(name)`, `default_value(key)`, `load_defaults(path)`, `load_plist_defaults(name)`
- Fetch: `ensure_initialized(cb)`, `fetch(cb, expiration_duration)`, `activate(cb)`, `fetch_and_activate(cb)`
- Values: `get_value(key, source)` → `RemoteConfigValue` (`string`, `number`, `boolean`, `data`, `source`, `json()`); `get_string`, `get_boolean`, `get_number`, `get_long`, `get_data`, `get_json`; `all_keys(source)`, `keys_with_prefix(prefix)`
- Real-time: `add_on_config_update_listener(listener)` → `ConfigUpdateListener` (`remove()`); `ConfigUpdate.updated_keys`
- `set_custom_signals(signals, cb)`; `RemoteConfigSource`, `RemoteConfigFetchStatus`, `RemoteConfigErrorCode`

## `pyios_firebase.remote_config`

::: pyios_firebase.remote_config

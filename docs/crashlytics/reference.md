# Crashlytics reference

## At a glance

- `Crashlytics.crashlytics()`: `log(message)`, `set_custom_value(key, value)`, `set_custom_keys(values)`, `set_user_id(id)`, `record_exception(exception)`, `record_exception_model(model)`, `record_error(error, user_info)`, `install_excepthook(*, threads)`, `uninstall_excepthook()`, `did_crash_during_previous_execution()`, `collection_enabled`, `check_for_unsent_reports(cb)`, `check_and_update_unsent_reports(cb)`, `send_unsent_reports()`, `delete_unsent_reports()`
- `ExceptionModel(name, reason, stack_trace)`, `ExceptionModel.from_exception(exception)`, `StackFrame(symbol, file, line)`, `CrashlyticsReport` (`report_id`, `date_created`, `has_crash`, `log`, `set_custom_value`, `set_custom_keys`, `set_user_id`)

## `pyios_firebase.crashlytics`

::: pyios_firebase.crashlytics

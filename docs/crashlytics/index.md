# Crashlytics

[Crashlytics](https://firebase.google.com/docs/crashlytics) collects crash
reports, groups them into issues, and shows which ones hurt the most users.
pyios-firebase adds what a Python app needs most: **Python exceptions as
issues, with their Python stack frames**.

```python
from pyios_firebase.crashlytics import Crashlytics

crashlytics = Crashlytics.crashlytics()
crashlytics.install_excepthook()          # uncaught Python exceptions become issues
crashlytics.set_user_id(uid)
```

## Installation

1. Add the **`FirebaseCrashlytics`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. Add the **dSYM upload run script**, so native stack traces are readable.
   In Xcode: the target's **Build Phases > + > New Run Script Phase**:

    ```bash
    "${BUILD_DIR%/Build/*}/SourcePackages/checkouts/firebase-ios-sdk/Crashlytics/run"
    ```

    with the input files
    `${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}` and
    `${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}/Contents/Resources/DWARF/${PRODUCT_NAME}`,
    and **Debug Information Format** set to *DWARF with dSYM File*.

3. Open **Crashlytics** in the console.

### App configuration

What the app's build needs for this product. To combine several products, list
them all in one `products`; see [App configuration](../getting-started/configuration.md).

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist"]

    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = ["FirebaseCrashlytics"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"
    # readable stack traces
    DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym"

    # optional: keep reports on the device until the user agrees
    [tool.kivy.ios.info_plist]
    FirebaseCrashlyticsCollectionEnabled = false
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseCrashlytics`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.
    4. **Build Settings > Debug Information Format**: *DWARF with dSYM File*.
    5. **Build Phases > + > New Run Script Phase**: `"${BUILD_DIR%/Build/*}/SourcePackages/checkouts/firebase-ios-sdk/Crashlytics/run"`, with the input files `${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}` and `${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}/Contents/Resources/DWARF/${PRODUCT_NAME}`.
    6. Optional, in **Info**: `FirebaseCrashlyticsCollectionEnabled` = `NO`.

!!! note
    kivyforge has no setting for a custom build phase. Upload the dSYMs after an archive instead: `<DerivedData>/SourcePackages/checkouts/firebase-ios-sdk/Crashlytics/upload-symbols -gsp GoogleService-Info.plist -p ios <path to the .dSYM files>`.


## Python exceptions

A Python exception does not crash the app by itself: Kivy or Toga catches
it, or it ends a thread. The native SDK never sees it. Report it:

```python
try:
    pay(order)
except PaymentError as e:
    crashlytics.record_exception(e)       # a non-fatal issue
    show("Payment failed")
```

The issue is named after the exception's class (`checkout.PaymentError`),
with its message, the chained cause (`raise ... from ...`), and the **Python
stack frames** (function, file, line), newest first.

### Uncaught exceptions

```python
crashlytics.install_excepthook()               # threads too, by default
crashlytics.install_excepthook(threads=False)  # only the main thread
```

Every uncaught exception (`sys.excepthook`, and `threading.excepthook`) is
then recorded, with a log line, before the previous hook runs as usual.
`KeyboardInterrupt` and `SystemExit` are not reported. Safe to call more than
once; `uninstall_excepthook()` undoes it.

!!! tip "Kivy"
    Kivy catches exceptions in event handlers with its `ExceptionManager`, so
    they never reach `sys.excepthook`. To report them too:

    ```python
    from kivy.base import ExceptionHandler, ExceptionManager


    class ReportToCrashlytics(ExceptionHandler):
        def handle_exception(self, exception):
            Crashlytics.crashlytics().record_exception(exception)
            return ExceptionManager.RAISE          # or PASS, to keep the app running


    ExceptionManager.add_handler(ReportToCrashlytics())
    ```

### Other errors

```python
crashlytics.record_error(error, {"screen": "checkout"})      # a FirebaseError from a callback, or an NSError

from pyios_firebase.crashlytics import ExceptionModel, StackFrame

crashlytics.record_exception_model(                          # from another runtime (Lua, JS...)
    ExceptionModel("LuaError", "attempt to index a nil value", [StackFrame("update", "game.lua", 42)])
)
```

`NSError`s are grouped by domain and code.

## Context for the reports

```python
crashlytics.log("Opened checkout")                     # the last 64 kB are kept
crashlytics.set_custom_value("cart_items", 3)
crashlytics.set_custom_keys({"screen": "checkout", "plan": "pro", "beta": True})
crashlytics.set_user_id(uid)                           # your ID; never personal data
```

Custom keys (up to 64) and logs are sent with the next crash or non-fatal
issue. Values are `str`, numbers or `bool`; anything else is sent as its
`str`.

## Test it

Crashlytics **does not report while the debugger is attached**:

1. Build and run, then **stop** the app in Xcode.
2. Open it from the Home screen (no debugger).
3. Crash it on purpose:

    ```python
    import os

    os.abort()
    ```

4. Open the app again: the report is sent at launch. It appears in the
   console within minutes.

`did_crash_during_previous_execution()` is `True` at the launch after a crash.

## Opt-in reporting

To send reports only when the user agrees, start with collection off:
`FirebaseCrashlyticsCollectionEnabled` = `NO` in `Info.plist`. Reports then
wait on the device:

```python
def on_reports(found):
    if found and ask_user("Send crash reports?"):
        crashlytics.send_unsent_reports()
    elif found:
        crashlytics.delete_unsent_reports()


crashlytics.check_for_unsent_reports(on_reports)      # runs on a background thread
```

Or get the newest report, to add keys and logs before sending:

```python
def on_report(report):
    if report is not None:
        print(report.report_id, report.date_created, report.has_crash)
        report.set_custom_keys({"consented": True})
        crashlytics.send_unsent_reports()


crashlytics.check_and_update_unsent_reports(on_report)
```

!!! warning "Once per launch"
    The SDK answers only the **first** check of a launch; later ones get "no
    report" whatever is waiting. pyios-firebase raises `RuntimeError` on a
    second check instead of giving a misleading answer.

`crashlytics.collection_enabled = True` turns automatic sending on (kept
across launches).

## Kivy and Python crashes

A crash in native code (an Objective-C exception, a segmentation fault) is a
real crash, reported with native frames. A Python exception that nobody
handles is not a crash: report it with `install_excepthook` or
`record_exception`, as above.

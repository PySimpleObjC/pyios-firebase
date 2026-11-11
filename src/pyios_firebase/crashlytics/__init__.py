"""Firebase Crashlytics: crash reports, and Python exceptions as non-fatal issues.

    from pyios_firebase.crashlytics import Crashlytics

    crashlytics = Crashlytics.crashlytics()
    crashlytics.install_excepthook()      # uncaught Python exceptions are reported
    crashlytics.set_user_id(uid)
    crashlytics.log("opened the checkout")

    try:
        pay()
    except PaymentError as e:
        crashlytics.record_exception(e)   # a non-fatal issue, with the Python stack

Native crashes are caught by the SDK itself. A Python exception that nobody
catches does not crash the app by itself, so it would never be reported:
``install_excepthook`` reports it (with its Python stack frames) before the
usual handling runs.

Reports are sent on the next launch. To see readable native stack traces,
upload the dSYMs (the Crashlytics run script in Xcode). Crashlytics does not
report while a debugger is attached.

Needs the ``FirebaseCrashlytics`` framework.
"""

from __future__ import annotations

__all__ = (
    "Crashlytics",
    "CrashlyticsReport",
    "ExceptionModel",
    "StackFrame",
)

import sys
import threading
import traceback
from collections.abc import Callable, Mapping
from ctypes import c_bool
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Any, ClassVar

from rubicon.objc import ObjCInstance, ns_from_py, objc_id

from ..types import FirebaseError, ObjCObject
from ..util import nsdate_to_datetime, objc_class, objc_instance, one_shot_block


def _custom_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str | bool | int | float):
        return value
    return str(value)  # Crashlytics shows custom values as text anyway


@dataclass(frozen=True)
class StackFrame:
    """One frame of an ``ExceptionModel``'s stack trace."""

    symbol: str
    """The function, for example ``"checkout.pay"``."""
    file: str
    """The source file."""
    line: int
    """The line number."""

    def to_native(self) -> ObjCObject:
        """A ``FIRStackFrame``."""
        return (
            objc_class("FIRStackFrame")
            .alloc()
            .initWithSymbol_file_line_(self.symbol, self.file, int(self.line))
        )


@dataclass
class ExceptionModel:
    """A non-fatal issue to record: a name, a reason and a stack trace (most
    recent call first). ``record_exception`` builds one from a Python exception.
    """

    name: str
    """The issue's title, for example the exception class name."""
    reason: str
    """The message."""
    stack_trace: list[StackFrame] = field(default_factory=list)
    """The frames, most recent call first."""

    @classmethod
    def from_exception(cls, exception: BaseException) -> ExceptionModel:
        """An ``ExceptionModel`` from a Python exception and its traceback.

        Chained exceptions (``raise ... from ...``) are added to the reason.

        Args:
            exception: the exception.
        """
        frames = traceback.extract_tb(exception.__traceback__)
        stack = [
            StackFrame(
                symbol=frame.name,
                file=frame.filename,
                line=frame.lineno or 0,
            )
            for frame in reversed(frames)
        ]
        kind = type(exception)
        name = (
            kind.__qualname__
            if kind.__module__ == "builtins"
            else f"{kind.__module__}.{kind.__qualname__}"
        )
        reason = str(exception)
        cause = exception.__cause__ or exception.__context__
        if cause is not None:
            reason += f" (caused by {type(cause).__name__}: {cause})"
        return cls(name=name, reason=reason, stack_trace=stack)

    def to_native(self) -> ObjCObject:
        """A ``FIRExceptionModel``."""
        model = (
            objc_class("FIRExceptionModel")
            .alloc()
            .initWithName_reason_(self.name, self.reason)
        )
        model.stackTrace = ns_from_py([frame.to_native() for frame in self.stack_trace])
        return model


class CrashlyticsReport:
    """An unsent report, from ``check_and_update_unsent_reports``. Add logs
    and keys to it before sending.

    Args:
        native: the native ``FIRCrashlyticsReport``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRCrashlyticsReport``."""
        return self._native

    @property
    def report_id(self) -> str:
        """The report's ID."""
        return str(self._native.reportID)

    @property
    def date_created(self) -> datetime | None:
        """When the report was made (UTC)."""
        return nsdate_to_datetime(self._native.dateCreated)

    @property
    def has_crash(self) -> bool:
        """``True`` if the report has a crash (not only non-fatal issues)."""
        return bool(self._native.hasCrash)

    def log(self, message: str) -> None:
        """Add a log line to the report.

        Args:
            message: the text.
        """
        self._native.log_(message)

    def set_custom_value(self, key: str, value: Any) -> None:
        """Set a key on the report.

        Args:
            key: the key.
            value: a ``str``, number or ``bool`` (anything else is shown as
                its ``str``); ``None`` removes it.
        """
        self._native.setCustomValue_forKey_(_custom_value(value), key)

    def set_custom_keys(self, values: Mapping[str, Any]) -> None:
        """Set several keys on the report.

        Args:
            values: keys to values (as for ``set_custom_value``).
        """
        self._native.setCustomKeysAndValues_(
            ns_from_py(
                {k: _custom_value(v) for k, v in values.items() if v is not None}
            )
        )

    def set_user_id(self, user_id: str | None) -> None:
        """Set the user ID on the report.

        Args:
            user_id: the ID, or ``None``.
        """
        self._native.setUserID_(user_id)


def _to_nserror(error: Any) -> ObjCObject:
    if isinstance(error, ObjCInstance):
        return error
    if isinstance(error, FirebaseError):
        info = {"NSLocalizedDescription": str(error.get("description", ""))}
        return objc_class("NSError").errorWithDomain_code_userInfo_(
            str(error.get("domain", "")), int(error.get("code", 0)), info
        )
    raise TypeError(
        "record_error takes an NSError or a FirebaseError (use record_exception "
        f"for Python exceptions), not {type(error).__name__}"
    )


class Crashlytics:
    """Crashlytics. Get it with ``Crashlytics.crashlytics()``.

    Args:
        native: the native ``FIRCrashlytics``.
    """

    _shared: ClassVar[Crashlytics | None] = None
    _hooks: ClassVar[dict[str, Any] | None] = None
    _unsent_checked: ClassVar[bool] = False

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def crashlytics(cls) -> Crashlytics:
        """The shared ``Crashlytics``."""
        if cls._shared is None:
            cls._shared = cls(objc_class("FIRCrashlytics").crashlytics())
        return cls._shared

    @property
    def native(self) -> ObjCObject:
        """The ``FIRCrashlytics``."""
        return self._native

    # ---- context for the reports ----------------------------------------------------

    def log(self, message: str) -> None:
        """Add a line to the logs sent with the next crash or non-fatal issue
        (the last 64 kB are kept).

        Args:
            message: the text.
        """
        self._native.log_(message)

    def set_custom_value(self, key: str, value: Any) -> None:
        """Set a key shown with the reports (up to 64 keys).

        Args:
            key: the key.
            value: a ``str``, number or ``bool`` (anything else is shown as
                its ``str``); ``None`` removes it.
        """
        self._native.setCustomValue_forKey_(_custom_value(value), key)

    def set_custom_keys(self, values: Mapping[str, Any]) -> None:
        """Set several keys at once.

        Args:
            values: keys to values (as for ``set_custom_value``).
        """
        self._native.setCustomKeysAndValues_(
            ns_from_py(
                {k: _custom_value(v) for k, v in values.items() if v is not None}
            )
        )

    def set_user_id(self, user_id: str | None) -> None:
        """Set the user ID shown with the reports (your own ID; never personal
        data).

        Args:
            user_id: the ID, or ``None`` to remove it.
        """
        self._native.setUserID_(user_id)

    # ---- non-fatal issues ----------------------------------------------------------

    def record_exception(self, exception: BaseException) -> None:
        """Record a Python exception as a non-fatal issue, with its Python
        stack frames.

        Args:
            exception: the exception (usually the one you caught).
        """
        self.record_exception_model(ExceptionModel.from_exception(exception))

    def record_exception_model(self, model: ExceptionModel) -> None:
        """Record a non-fatal issue you built yourself (for example an error
        from another language runtime).

        Args:
            model: the issue.
        """
        self._native.recordExceptionModel_(model.to_native())

    def record_error(
        self, error: Any, user_info: Mapping[str, Any] | None = None
    ) -> None:
        """Record an ``NSError`` (or a Firebase error from a callback) as a
        non-fatal issue. Issues are grouped by domain and code.

        Args:
            error: an ``NSError``, or a ``FirebaseError`` from a callback.
            user_info: more information to attach.

        Raises:
            TypeError: ``error`` is a Python exception (use ``record_exception``)
                or another type.
        """
        native = _to_nserror(error)
        info = (
            None
            if user_info is None
            else ns_from_py({k: _custom_value(v) for k, v in user_info.items()})
        )
        self._native.recordError_userInfo_(native, info)

    def install_excepthook(self, *, threads: bool = True) -> None:
        """Report Python exceptions that nobody catches, as non-fatal issues.

        The previous ``sys.excepthook`` (and ``threading.excepthook``) still
        run after the report. Safe to call more than once.

        Args:
            threads: also report exceptions that end a ``threading.Thread``.
        """
        if Crashlytics._hooks is not None:
            return
        previous_sys = sys.excepthook
        previous_threading = threading.excepthook

        def sys_hook(
            kind: type[BaseException],
            exception: BaseException,
            tb: TracebackType | None,
        ) -> None:
            if not isinstance(exception, KeyboardInterrupt | SystemExit):
                self._report_uncaught(exception, tb)
            previous_sys(kind, exception, tb)

        def threading_hook(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None and not isinstance(
                args.exc_value, SystemExit
            ):
                self._report_uncaught(args.exc_value, args.exc_traceback)
            previous_threading(args)

        sys.excepthook = sys_hook
        if threads:
            threading.excepthook = threading_hook
        Crashlytics._hooks = {
            "sys": previous_sys,
            "threading": previous_threading,
            "installed_sys": sys_hook,
            "installed_threading": threading_hook if threads else None,
        }

    def uninstall_excepthook(self) -> None:
        """Undo ``install_excepthook`` (if nothing replaced the hooks since)."""
        hooks = Crashlytics._hooks
        if hooks is None:
            return
        if sys.excepthook is hooks["installed_sys"]:
            sys.excepthook = hooks["sys"]
        if threading.excepthook is hooks["installed_threading"]:
            threading.excepthook = hooks["threading"]
        Crashlytics._hooks = None

    def _report_uncaught(
        self, exception: BaseException, tb: TracebackType | None
    ) -> None:
        try:
            if exception.__traceback__ is None and tb is not None:
                exception = exception.with_traceback(tb)
            self.log(f"uncaught {type(exception).__name__}: {exception}")
            self.record_exception(exception)
        except Exception:  # noqa: BLE001, S110 - reporting must never hide the error
            pass

    # ---- crashes and sending -------------------------------------------------------

    def did_crash_during_previous_execution(self) -> bool:
        """``True`` if the app crashed (natively) the last time it ran."""
        return bool(self._native.didCrashDuringPreviousExecution())

    @property
    def collection_enabled(self) -> bool:
        """Whether reports are sent automatically. Setting it is kept across
        launches. To start with it off (for example until the user agrees),
        set ``FirebaseCrashlyticsCollectionEnabled`` to ``NO`` in
        ``Info.plist`` and send with ``send_unsent_reports``."""
        return bool(self._native.isCrashlyticsCollectionEnabled())

    @collection_enabled.setter
    def collection_enabled(self, enabled: bool) -> None:
        self._native.setCrashlyticsCollectionEnabled_(bool(enabled))

    def _check_once(self) -> None:
        # the SDK answers only the first check of a launch; later ones get
        # "no reports" whatever is waiting
        if Crashlytics._unsent_checked:
            raise RuntimeError(
                "check_for_unsent_reports / check_and_update_unsent_reports can be "
                "called once per launch (the SDK answers later calls with no report)"
            )
        Crashlytics._unsent_checked = True

    def check_for_unsent_reports(self, callback: Callable[[bool], None]) -> None:
        """Whether there are reports waiting (with collection off). Call this
        or ``check_and_update_unsent_reports`` once per launch, then
        ``send_unsent_reports`` or ``delete_unsent_reports``.

        Args:
            callback: gets ``True`` if there are.

        Raises:
            RuntimeError: a check was already made in this launch.
        """
        self._check_once()
        self._native.checkForUnsentReportsWithCompletion_(
            one_shot_block(lambda found: callback(bool(found)), c_bool)
        )

    def check_and_update_unsent_reports(
        self, callback: Callable[[CrashlyticsReport | None], None]
    ) -> None:
        """The newest unsent report, to add keys and logs before sending (with
        collection off). Once per launch, like ``check_for_unsent_reports``.

        Args:
            callback: gets a ``CrashlyticsReport``, or ``None`` if there is none.

        Raises:
            RuntimeError: a check was already made in this launch.
        """
        self._check_once()

        def done(report_ptr: Any) -> None:
            callback(
                CrashlyticsReport(objc_instance(report_ptr)) if report_ptr else None
            )

        self._native.checkAndUpdateUnsentReportsWithCompletion_(
            one_shot_block(done, objc_id)
        )

    def send_unsent_reports(self) -> None:
        """Send the waiting reports (with collection off, after the user agreed)."""
        self._native.sendUnsentReports()

    def delete_unsent_reports(self) -> None:
        """Delete the waiting reports (with collection off, if the user declined)."""
        self._native.deleteUnsentReports()

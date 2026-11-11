"""A tiny asynchronous test runner for code that answers through callbacks.

Each test is ``def test_x(t): ...``. It starts Firebase calls and wraps their
callbacks with ``t.step(fn)``; a failed ``expect`` or any exception inside a
step fails the test. The test ends with ``t.passed()``. Tests run one at a
time, each with a timeout.
"""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import Callable
from typing import Any

from kivy.clock import Clock

TIMEOUT_SECONDS = 20
SKIP = "SKIP: "  # a finish message starting with this is a skip, not a failure


class Failure(Exception):
    pass


def expect(condition: object, message: object = "expectation failed") -> None:
    """Like ``assert``, but never stripped by ``python -O``."""
    if not condition:
        raise Failure(str(message))


def expect_equal(actual: object, expected: object, what: str = "value") -> None:
    if actual != expected:
        raise Failure(f"{what}: expected {expected!r}, got {actual!r}")


class TestContext:
    def __init__(self, finish: Callable[[str | None], None]) -> None:
        self._finish = finish

    def step(self, fn: Callable[..., Any]) -> Callable[..., None]:
        """Wrap a callback: an exception in it fails the test."""

        def run(*args: Any) -> None:
            try:
                fn(*args)
            except Exception:  # noqa: BLE001
                self._finish(traceback.format_exc(limit=4))

        return run

    def passed(self) -> None:
        self._finish(None)

    def skipped(self, reason: str) -> None:
        """The test cannot run here (for example the emulator lacks a feature)."""
        self._finish(SKIP + reason)

    def fail(self, message: str) -> None:
        self._finish(message)


class Runner:
    def __init__(
        self,
        tests: list[tuple[str, Callable[[TestContext], None]]],
        on_progress: Callable[[str], None],
        on_finish: Callable[[dict[str, Any]], None],
        on_test_start: Callable[[str], None] | None = None,
    ) -> None:
        self._on_test_start = on_test_start
        self._tests = list(tests)
        self._results: list[dict[str, Any]] = []
        self._on_progress = on_progress
        self._on_finish = on_finish
        self._started = time.monotonic()

    def start(self) -> None:
        Clock.schedule_once(lambda dt: self._next(), 0)

    def _next(self) -> None:
        if not self._tests:
            passed = sum(r["ok"] and not r["skipped"] for r in self._results)
            skipped = sum(r["skipped"] for r in self._results)
            self._on_finish(
                {
                    "passed": passed,
                    "skipped": skipped,
                    "failed": len(self._results) - passed - skipped,
                    "seconds": round(time.monotonic() - self._started, 2),
                    "results": self._results,
                }
            )
            return
        name, test = self._tests.pop(0)
        state = {"done": False, "start": time.monotonic()}

        def finish(error: str | None) -> None:
            if state["done"]:
                return  # a late callback after a timeout or a failure
            state["done"] = True
            timeout.cancel()
            skipped = error is not None and error.startswith(SKIP)
            result = {
                "name": name,
                "ok": error is None or skipped,
                "skipped": skipped,
                "detail": (error or "").removeprefix(SKIP),
                "seconds": round(time.monotonic() - state["start"], 3),
            }
            self._results.append(result)
            status = "SKIP" if skipped else ("PASS" if error is None else "FAIL")
            line = f"PYIOS-E2E {status} {name} ({result['seconds']}s)"
            print(line + (f"\n{result['detail']}" if error else ""), flush=True)
            self._on_progress(line)
            Clock.schedule_once(lambda dt: self._next(), 0)

        timeout = Clock.schedule_once(
            lambda dt: finish(f"timeout: no answer within {TIMEOUT_SECONDS}s"), TIMEOUT_SECONDS
        )
        print(f"PYIOS-E2E RUN {name}", flush=True)
        if self._on_test_start is not None:
            self._on_test_start(name)
        try:
            test(TestContext(finish))
        except Exception:  # noqa: BLE001
            finish(traceback.format_exc(limit=4))


def dumps(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2)

"""Callable functions for the iOS e2e suite (e2e/ios/src/functions_tests.py).

They only run in the Functions emulator, for the offline demo project.
"""

import time
from typing import Any

from firebase_admin import initialize_app
from firebase_functions import https_fn

# verifies the Auth ID tokens callables receive (the emulator's, here)
initialize_app()

Request = https_fn.CallableRequest[Any]


@https_fn.on_call()
def echo(req: Request) -> Any:
    """Returns what it gets, so the test can compare types both ways."""
    return {"data": req.data}


@https_fn.on_call()
def fail(req: Request) -> Any:
    """An HttpsError with details: the client gets the code, message and details."""
    raise https_fn.HttpsError(
        https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
        "bad input",
        {"field": "text", "hint": req.data},
    )


@https_fn.on_call()
def crash(req: Request) -> Any:
    """An unexpected error: the client gets INTERNAL, without the message."""
    raise RuntimeError("secret server detail")


@https_fn.on_call()
def slow(req: Request) -> Any:
    """Sleeps, for the timeout test."""
    time.sleep(req.data["ms"] / 1000)
    return "done"


@https_fn.on_call()
def whoAmI(req: Request) -> Any:  # noqa: N802 - the name the app calls
    """The Auth user the emulator verified from the ID token the SDK sent."""
    return {"uid": req.auth.uid if req.auth else None}


@https_fn.on_call()
def appCheckToken(req: Request) -> Any:  # noqa: N802
    """The App Check token the SDK sent (the emulator does not verify it)."""
    return {"header": req.raw_request.headers.get("X-Firebase-AppCheck")}


@https_fn.on_call(region="europe-west1")
def regional(req: Request) -> Any:
    """A function in another region."""
    return {"region": "europe-west1"}

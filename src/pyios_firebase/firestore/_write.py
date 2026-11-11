from __future__ import annotations

from typing import Any

from rubicon.objc import Block, objc_id

from ..types import ErrorCallback
from ..util import error_from_pointer, one_shot_block


def write_block(callback: ErrorCallback | None) -> Block:
    """Completion block for writes: ``callback(error)``, or nothing if ``None``."""

    def on_done(error_ptr: Any) -> None:
        if callback is not None:
            callback(error_from_pointer(error_ptr))

    return one_shot_block(on_done, objc_id)

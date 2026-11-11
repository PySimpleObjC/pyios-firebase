"""Upload and download tasks: progress, pause, resume and cancel."""

from __future__ import annotations

__all__ = (
    "StorageDownloadTask",
    "StorageTask",
    "StorageTaskSnapshot",
    "StorageTaskStatus",
    "StorageUploadTask",
)

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from rubicon.objc import objc_id

from ..types import ObjCObject
from ..util import listener_block, objc_instance
from .errors import StorageError, storage_error
from .metadata import StorageMetadata

if TYPE_CHECKING:
    from .reference import StorageReference


class StorageTaskStatus:
    """What happened to a task: pass one to ``StorageTask.observe``."""

    UNKNOWN: Final = 0
    RESUME: Final = 1
    """The task started or resumed."""
    PROGRESS: Final = 2
    """More bytes were sent or received."""
    PAUSE: Final = 3
    """The task was paused."""
    SUCCESS: Final = 4
    """The task finished."""
    FAILURE: Final = 5
    """The task failed or was cancelled (see ``snapshot.error``)."""


_TERMINAL: Final = (StorageTaskStatus.SUCCESS, StorageTaskStatus.FAILURE)


class StorageTaskSnapshot:
    """A task's state at one moment.

    Args:
        native: the native ``FIRStorageTaskSnapshot``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def status(self) -> int:
        """A ``StorageTaskStatus`` value."""
        return int(self._native.status)

    @property
    def bytes_transferred(self) -> int:
        """Bytes sent (uploads) or received (downloads) so far."""
        progress = self._native.progress
        return 0 if progress is None else int(progress.completedUnitCount)

    @property
    def total_bytes(self) -> int:
        """The total size, or -1 if not known yet."""
        progress = self._native.progress
        return -1 if progress is None else int(progress.totalUnitCount)

    @property
    def fraction_completed(self) -> float:
        """From 0.0 to 1.0."""
        progress = self._native.progress
        return 0.0 if progress is None else float(progress.fractionCompleted)

    @property
    def metadata(self) -> StorageMetadata | None:
        """The file's metadata, once known (uploads: after success)."""
        metadata = self._native.metadata
        return None if metadata is None else StorageMetadata(native=metadata)

    @property
    def error(self) -> StorageError | None:
        """Why the task failed (``FAILURE``), or ``None``."""
        error = self._native.error
        return None if error is None else storage_error(error)

    @property
    def reference(self) -> StorageReference:
        """The file the task is for."""
        from .reference import StorageReference

        return StorageReference(self._native.reference)

    def __repr__(self) -> str:
        return (
            f"StorageTaskSnapshot(status={self.status}, "
            f"{self.bytes_transferred}/{self.total_bytes} bytes)"
        )


class StorageTask:
    """A running upload or download. Upload and download methods give one back.

    Observer callbacks stay alive until you remove them or the task finishes.

    Args:
        native: the native ``FIRStorageUploadTask`` / ``FIRStorageDownloadTask``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native
        self._releases: dict[str, Callable[[], None]] = {}
        self._finished = False
        # release every observer block once the task is done
        self._observe_native(StorageTaskStatus.SUCCESS, self._on_finished)
        self._observe_native(StorageTaskStatus.FAILURE, self._on_finished)

    @property
    def native(self) -> ObjCObject:
        """The native task."""
        return self._native

    @property
    def snapshot(self) -> StorageTaskSnapshot:
        """The task's current state."""
        return StorageTaskSnapshot(self._native.snapshot)

    def _observe_native(
        self, status: int, handler: Callable[[StorageTaskSnapshot], None]
    ) -> str:
        def on_snapshot(snapshot_ptr: Any) -> None:
            handler(StorageTaskSnapshot(objc_instance(snapshot_ptr)))

        block, release = listener_block(on_snapshot, objc_id)
        handle = str(self._native.observeStatus_handler_(int(status), block))
        self._releases[handle] = release
        return handle

    def _on_finished(self, _snapshot: StorageTaskSnapshot) -> None:
        if self._finished:
            return
        self._finished = True
        releases, self._releases = self._releases, {}
        for release in releases.values():
            release()

    def observe(
        self, status: int, handler: Callable[[StorageTaskSnapshot], None]
    ) -> str:
        """Call ``handler`` each time the task reaches ``status``.

        ::

            task.observe(StorageTaskStatus.PROGRESS, lambda s: bar.set(s.fraction_completed))

        Args:
            status: a ``StorageTaskStatus`` value.
            handler: gets a ``StorageTaskSnapshot``.

        Returns:
            A handle for ``remove_observer``.
        """
        return self._observe_native(status, handler)

    def remove_observer(self, handle: str) -> None:
        """Stop one observer.

        Args:
            handle: what ``observe`` returned.
        """
        self._native.removeObserverWithHandle_(handle)
        release = self._releases.pop(handle, None)
        if release is not None:
            release()

    def pause(self) -> None:
        """Pause the task (``resume`` continues it)."""
        self._native.pause()

    def resume(self) -> None:
        """Continue a paused task."""
        self._native.resume()

    def cancel(self) -> None:
        """Stop the task. Its completion gets a ``CANCELLED`` error."""
        self._native.cancel()


class StorageUploadTask(StorageTask):
    """A running upload."""


class StorageDownloadTask(StorageTask):
    """A running download."""

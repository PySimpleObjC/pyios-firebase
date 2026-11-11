"""``Storage``: a Cloud Storage bucket, its settings and the emulator."""

from __future__ import annotations

__all__ = ("Storage",)

from typing import ClassVar

from ..types import ObjCObject
from ..util import objc_class
from .reference import StorageReference


class Storage:
    """Cloud Storage for one bucket. Get it with ``Storage.storage()``.

    Args:
        native: the native ``FIRStorage``.
    """

    # shared instances, by bucket URL (None = the default bucket)
    _instances: ClassVar[dict[str | None, Storage]] = {}

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def storage(cls, url: str | None = None) -> Storage:
        """The shared ``Storage`` for a bucket.

        Args:
            url: a bucket URL such as ``"gs://my-other-bucket"``, or ``None`` for
                the app's default bucket (``STORAGE_BUCKET`` in
                ``GoogleService-Info.plist``).

        Returns:
            The same ``Storage`` for the same bucket.
        """
        instance = cls._instances.get(url)
        if instance is None:
            fir = objc_class("FIRStorage")
            native = fir.storage() if url is None else fir.storageWithURL_(url)
            instance = cls._instances[url] = cls(native)
        return instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRStorage``."""
        return self._native

    def reference(self) -> StorageReference:
        """The root of the bucket."""
        return StorageReference(self._native.reference())

    def reference_with_path(self, path: str) -> StorageReference:
        """A reference by path in this bucket.

        Args:
            path: the path, for example ``"users/ada/avatar.jpg"``.

        Returns:
            A ``StorageReference``. Nothing is read or written.
        """
        return StorageReference(self._native.referenceWithPath_(path))

    def reference_for_url(self, url: str) -> StorageReference:
        """A reference from a file's URL.

        Args:
            url: a ``gs://bucket/path`` URL, or an ``https://`` Firebase Storage
                download URL. Its bucket must be this ``Storage``'s bucket.

        Returns:
            A ``StorageReference``.
        """
        return StorageReference(self._native.referenceForURL_(url))

    def use_emulator(self, host: str = "127.0.0.1", port: int = 9199) -> None:
        """Send this bucket's requests to the local Storage emulator. Call it
        before any other use; only in development and test builds.

        Args:
            host: the emulator's host. ``"127.0.0.1"`` works in the iOS Simulator;
                on a device, use the Mac's LAN address.
            port: the emulator's port (``firebase emulators:start`` uses 9199).
        """
        self._native.useEmulatorWithHost_port_(host, int(port))

    @property
    def max_upload_retry_time(self) -> float:
        """Seconds an upload keeps retrying before it fails (default 600)."""
        return float(self._native.maxUploadRetryTime)

    @max_upload_retry_time.setter
    def max_upload_retry_time(self, seconds: float) -> None:
        self._native.maxUploadRetryTime = float(seconds)

    @property
    def max_download_retry_time(self) -> float:
        """Seconds a download keeps retrying before it fails (default 600)."""
        return float(self._native.maxDownloadRetryTime)

    @max_download_retry_time.setter
    def max_download_retry_time(self, seconds: float) -> None:
        self._native.maxDownloadRetryTime = float(seconds)

    @property
    def max_operation_retry_time(self) -> float:
        """Seconds other operations (metadata, delete, list) keep retrying (default 120)."""
        return float(self._native.maxOperationRetryTime)

    @max_operation_retry_time.setter
    def max_operation_retry_time(self, seconds: float) -> None:
        self._native.maxOperationRetryTime = float(seconds)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Storage) and bool(self._native.isEqual_(other._native))

    def __hash__(self) -> int:
        return int(self._native.hash)

"""``Database``: the entry point of the Realtime Database."""

from __future__ import annotations

__all__ = ("Database",)

from typing import ClassVar

from ..types import ObjCObject
from ..util import objc_class
from .reference import DatabaseReference
from .values import validate_root_path


class Database:
    """A Realtime Database. Get it with ``Database.database()``.

    Args:
        native: the native ``FIRDatabase``.
    """

    # shared instances, by URL (None = the app's default database)
    _instances: ClassVar[dict[str | None, Database]] = {}

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @classmethod
    def database(cls, url: str | None = None) -> Database:
        """The shared ``Database`` of the default Firebase app.

        Args:
            url: the database URL, for example
                ``"https://my-db.europe-west1.firebasedatabase.app"``. ``None``
                means the app's default database (``DATABASE_URL`` in
                ``GoogleService-Info.plist``).

        Returns:
            The same ``Database`` for the same URL.
        """
        instance = cls._instances.get(url)
        if instance is None:
            fir = objc_class("FIRDatabase")
            native = fir.database() if url is None else fir.databaseWithURL_(url)
            instance = cls._instances[url] = cls(native)
        return instance

    @property
    def native(self) -> ObjCObject:
        """The ``FIRDatabase``."""
        return self._native

    def reference(self, path: str | None = None) -> DatabaseReference:
        """A location in the database.

        Args:
            path: the path from the root, for example ``"users/ada"``.
                ``None`` or ``""`` means the root. ``".info/connected"`` is
                ``True`` while the client is connected.

        Returns:
            A ``DatabaseReference``.

        Raises:
            ValueError: the path holds ``. # $ [ ]``.
        """
        if not path or not path.strip("/"):
            return DatabaseReference(self._native.reference())
        validate_root_path(path)
        return DatabaseReference(self._native.referenceWithPath_(path))

    def reference_from_url(self, url: str) -> DatabaseReference:
        """A location, from its full URL.

        Args:
            url: for example ``"https://my-db.firebaseio.com/users/ada"``. It
                must be in this database.

        Returns:
            A ``DatabaseReference``.
        """
        return DatabaseReference(self._native.referenceFromURL_(url))

    def use_emulator(self, host: str = "127.0.0.1", port: int = 9000) -> None:
        """Use the local Realtime Database emulator. Call it before any other
        use of this database; use it only in development and test builds.

        Args:
            host: the emulator's host. ``"127.0.0.1"`` works in the iOS
                Simulator; on a device, use the Mac's LAN address.
            port: the emulator's port (``firebase emulators:start`` uses 9000).
        """
        self._native.useEmulatorWithHost_port_(host, int(port))

    @property
    def persistence_enabled(self) -> bool:
        """Keep the data and the pending writes on disk, so they survive app
        restarts (off by default). Set it before any other use of this database.
        """
        return bool(self._native.persistenceEnabled)

    @persistence_enabled.setter
    def persistence_enabled(self, enabled: bool) -> None:
        self._native.persistenceEnabled = bool(enabled)

    @property
    def persistence_cache_size_bytes(self) -> int:
        """The most disk the cache may use (1 MB to 100 MB; default 10 MB). Set
        it before any other use of this database."""
        return int(self._native.persistenceCacheSizeBytes)

    @persistence_cache_size_bytes.setter
    def persistence_cache_size_bytes(self, size: int) -> None:
        if not 1024 * 1024 <= size <= 100 * 1024 * 1024:
            raise ValueError("the cache size must be 1 MB to 100 MB")
        self._native.persistenceCacheSizeBytes = int(size)

    def go_offline(self) -> None:
        """Disconnect from the server. Reads come from the cache and writes
        are queued until ``go_online``."""
        self._native.goOffline()

    def go_online(self) -> None:
        """Reconnect after ``go_offline``."""
        self._native.goOnline()

    def purge_outstanding_writes(self) -> None:
        """Drop the writes not yet sent to the server (their callbacks get
        ``WRITE_CANCELED``). Useful after a long time offline."""
        self._native.purgeOutstandingWrites()

    @staticmethod
    def set_logging_enabled(enabled: bool) -> None:
        """Log the SDK's debug messages to the console.

        Args:
            enabled: ``True`` to log.
        """
        objc_class("FIRDatabase").setLoggingEnabled_(bool(enabled))

    @staticmethod
    def sdk_version() -> str:
        """The Firebase Database SDK version."""
        return str(objc_class("FIRDatabase").sdkVersion())

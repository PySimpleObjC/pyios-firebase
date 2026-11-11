"""``StorageReference``: a file or folder in Cloud Storage, and what you can do with it."""

from __future__ import annotations

__all__ = ("StorageListResult", "StorageReference")

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rubicon.objc import ns_from_py, objc_id

from ..types import ObjCObject
from ..util import objc_class, objc_instance, one_shot_block, to_python
from .errors import StorageError, size_exceeded_error, storage_error_from_pointer
from .metadata import StorageMetadata
from .task import StorageDownloadTask, StorageUploadTask

if TYPE_CHECKING:
    from .storage import Storage

MetadataCallback = Callable[[StorageMetadata | None, StorageError | None], None]
ErrorCallback = Callable[[StorageError | None], None]


@dataclass(frozen=True)
class StorageListResult:
    """One page of ``StorageReference.list`` / ``list_all``."""

    items: list[StorageReference]
    """The files directly in the folder."""
    prefixes: list[StorageReference]
    """The sub-folders directly in the folder."""
    page_token: str | None
    """Pass it to ``list`` for the next page; ``None`` on the last page."""

    @classmethod
    def from_native(cls, native: ObjCObject) -> StorageListResult:
        """Copy a native ``FIRStorageListResult``.

        Args:
            native: the ``FIRStorageListResult``.
        """
        token = native.pageToken
        return cls(
            items=[StorageReference(item) for item in native.items],
            prefixes=[StorageReference(prefix) for prefix in native.prefixes],
            page_token=None if token is None else str(token),
        )


def _metadata(
    metadata: StorageMetadata | None, content_type: str | None
) -> ObjCObject | None:
    if metadata is None and content_type is None:
        return None
    metadata = metadata or StorageMetadata()
    if content_type is not None:
        metadata.content_type = content_type
    return metadata.native


def _metadata_block(callback: MetadataCallback | None) -> Any:
    def done(metadata_ptr: Any, error_ptr: Any) -> None:
        if callback is None:
            return
        error = storage_error_from_pointer(error_ptr)
        if error is not None or not metadata_ptr:
            callback(None, error)
            return
        callback(StorageMetadata(native=objc_instance(metadata_ptr)), None)

    return one_shot_block(done, objc_id, objc_id)


class StorageReference:
    """Points to a file or folder in Cloud Storage. Nothing is read or written
    until you call a method.

    Get references from ``Storage`` or ``child``; you do not make them yourself.

    Args:
        native: the native ``FIRStorageReference``.
    """

    def __init__(self, native: ObjCObject) -> None:
        self._native = native

    @property
    def native(self) -> ObjCObject:
        """The ``FIRStorageReference``, for SDK calls this wrapper does not cover."""
        return self._native

    # ---- where it points -----------------------------------------------------------

    @property
    def full_path(self) -> str:
        """The path in the bucket, for example ``"users/ada/avatar.jpg"`` (``""``
        for the root)."""
        return str(self._native.fullPath)

    @property
    def name(self) -> str:
        """The last part of the path."""
        return str(self._native.name)

    @property
    def bucket(self) -> str:
        """The bucket name."""
        return str(self._native.bucket)

    @property
    def storage(self) -> Storage:
        """The ``Storage`` this reference belongs to."""
        from .storage import Storage

        return Storage(self._native.storage)

    @property
    def gs_url(self) -> str:
        """The ``gs://bucket/path`` URL."""
        return f"gs://{self.bucket}/{self.full_path}"

    def root(self) -> StorageReference:
        """The root of the bucket."""
        return StorageReference(self._native.root())

    def parent(self) -> StorageReference | None:
        """The folder this is in, or ``None`` at the root."""
        parent = self._native.parent()
        return None if parent is None else StorageReference(parent)

    def child(self, path: str) -> StorageReference:
        """A reference below this one.

        Args:
            path: a relative path, for example ``"avatar.jpg"`` or
                ``"images/2026/a.jpg"``. Leading, trailing and repeated ``/``
                are ignored.

        Returns:
            A new ``StorageReference``.
        """
        return StorageReference(self._native.child_(path))

    # ---- upload --------------------------------------------------------------------

    def put_data(
        self,
        data: bytes | bytearray | memoryview,
        content_type: str | None = None,
        callback: MetadataCallback | None = None,
        *,
        metadata: StorageMetadata | None = None,
    ) -> StorageUploadTask:
        """Upload bytes, replacing the file if it exists.

        Args:
            data: the bytes.
            content_type: the MIME type, for example ``"text/plain"`` (a shortcut
                for ``metadata.content_type``).
            callback: gets ``(StorageMetadata, None)`` when done, or ``(None, error)``.
            metadata: metadata to upload with (content type, cache control,
                custom metadata...).

        Returns:
            A ``StorageUploadTask``: observe progress, pause, resume or cancel.
        """
        native = self._native.putData_metadata_completion_(
            ns_from_py(bytes(data)),
            _metadata(metadata, content_type),
            _metadata_block(callback),
        )
        return StorageUploadTask(native)

    def put_file(
        self,
        local_path: str,
        content_type: str | None = None,
        callback: MetadataCallback | None = None,
        *,
        metadata: StorageMetadata | None = None,
    ) -> StorageUploadTask:
        """Upload a local file, replacing the file in Storage if it exists.

        Large files are uploaded in chunks and survive network changes.

        Args:
            local_path: the file's path on the device.
            content_type: the MIME type, for example ``"image/jpeg"``. Without
                it, Storage guesses from the file extension.
            callback: gets ``(StorageMetadata, None)`` when done, or ``(None, error)``.
            metadata: metadata to upload with.

        Returns:
            A ``StorageUploadTask``.
        """
        native = self._native.putFile_metadata_completion_(
            objc_class("NSURL").fileURLWithPath_(local_path),
            _metadata(metadata, content_type),
            _metadata_block(callback),
        )
        return StorageUploadTask(native)

    # ---- download ------------------------------------------------------------------

    def get_data(
        self,
        max_size: int,
        callback: Callable[[bytes | None, StorageError | None], None],
    ) -> StorageDownloadTask:
        """Download the file into memory.

        Args:
            max_size: the most bytes to accept. A bigger file fails with
                ``DOWNLOAD_SIZE_EXCEEDED`` (checked by the SDK while
                downloading, and again on the bytes received).
            callback: gets ``(bytes, None)``, or ``(None, error)``.

        Returns:
            A ``StorageDownloadTask``.
        """

        def done(data_ptr: Any, error_ptr: Any) -> None:
            error = storage_error_from_pointer(error_ptr)
            if error is not None or not data_ptr:
                callback(None, error)
                return
            data = bytes(to_python(objc_instance(data_ptr)))
            if len(data) > max_size:
                # the SDK checks max_size only from download progress, which a
                # small download may never report
                callback(None, size_exceeded_error(len(data), max_size))
                return
            callback(data, None)

        native = self._native.dataWithMaxSize_completion_(
            int(max_size), one_shot_block(done, objc_id, objc_id)
        )
        return StorageDownloadTask(native)

    def write_to_file(
        self,
        local_path: str,
        callback: Callable[[str | None, StorageError | None], None] | None = None,
    ) -> StorageDownloadTask:
        """Download the file to a local file (for large files).

        Args:
            local_path: where to save it on the device. Its folder must exist.
            callback: gets ``(local_path, None)``, or ``(None, error)``.

        Returns:
            A ``StorageDownloadTask``.
        """

        def done(url_ptr: Any, error_ptr: Any) -> None:
            if callback is None:
                return
            error = storage_error_from_pointer(error_ptr)
            if error is not None or not url_ptr:
                callback(None, error)
                return
            callback(str(objc_instance(url_ptr).path), None)

        native = self._native.writeToFile_completion_(
            objc_class("NSURL").fileURLWithPath_(local_path),
            one_shot_block(done, objc_id, objc_id),
        )
        return StorageDownloadTask(native)

    def download_url(
        self, callback: Callable[[str | None, StorageError | None], None]
    ) -> None:
        """Get a long-lived ``https://`` download URL for the file.

        Args:
            callback: gets ``(url, None)``, or ``(None, error)``.
        """

        def done(url_ptr: Any, error_ptr: Any) -> None:
            error = storage_error_from_pointer(error_ptr)
            url = (
                str(objc_instance(url_ptr).absoluteString)
                if url_ptr and error is None
                else None
            )
            callback(url, error)

        self._native.downloadURLWithCompletion_(one_shot_block(done, objc_id, objc_id))

    # ---- metadata, list, delete -------------------------------------------------------

    def get_metadata(self, callback: MetadataCallback) -> None:
        """Get the file's metadata.

        Args:
            callback: gets ``(StorageMetadata, None)``, or ``(None, error)``.
        """
        self._native.metadataWithCompletion_(_metadata_block(callback))

    def update_metadata(
        self, metadata: StorageMetadata, callback: MetadataCallback | None = None
    ) -> None:
        """Change the file's metadata. Only the fields changed on ``metadata``
        are sent; set one to ``None`` to delete it.

        ::

            def got(metadata, error):
                metadata.cache_control = "public, max-age=300"
                metadata.content_language = None          # delete it
                ref.update_metadata(metadata, on_updated)

            ref.get_metadata(got)

        Args:
            metadata: new metadata (``StorageMetadata(...)``), or one from
                ``get_metadata`` with fields changed.
            callback: gets ``(StorageMetadata, None)`` with the result, or
                ``(None, error)``.
        """
        self._native.updateMetadata_completion_(
            metadata.native, _metadata_block(callback)
        )

    def list_all(
        self, callback: Callable[[StorageListResult | None, StorageError | None], None]
    ) -> None:
        """Everything directly in this folder (files and sub-folders).

        Needs rules version 2. For big folders, prefer ``list`` with pages.

        Args:
            callback: gets ``(StorageListResult, None)``, or ``(None, error)``.
        """

        def done(result_ptr: Any, error_ptr: Any) -> None:
            error = storage_error_from_pointer(error_ptr)
            if error is not None or not result_ptr:
                callback(None, error)
                return
            callback(StorageListResult.from_native(objc_instance(result_ptr)), None)

        self._native.listAllWithCompletion_(one_shot_block(done, objc_id, objc_id))

    def list(
        self,
        max_results: int,
        callback: Callable[[StorageListResult | None, StorageError | None], None],
        page_token: str | None = None,
    ) -> None:
        """One page of what is directly in this folder.

        Args:
            max_results: the most results in the page (1 to 1000).
            callback: gets ``(StorageListResult, None)``, or ``(None, error)``.
            page_token: the previous page's ``page_token``, or ``None`` for
                the first page.
        """

        def done(result_ptr: Any, error_ptr: Any) -> None:
            error = storage_error_from_pointer(error_ptr)
            if error is not None or not result_ptr:
                callback(None, error)
                return
            callback(StorageListResult.from_native(objc_instance(result_ptr)), None)

        block = one_shot_block(done, objc_id, objc_id)
        if page_token is None:
            self._native.listWithMaxResults_completion_(int(max_results), block)
        else:
            self._native.listWithMaxResults_pageToken_completion_(
                int(max_results), page_token, block
            )

    def delete(self, callback: ErrorCallback | None = None) -> None:
        """Delete the file.

        Args:
            callback: gets ``None`` or the error (``OBJECT_NOT_FOUND`` if there
                is no file).
        """

        def done(error_ptr: Any) -> None:
            if callback is not None:
                callback(storage_error_from_pointer(error_ptr))

        self._native.deleteWithCompletion_(one_shot_block(done, objc_id))

    # ---- comparing -----------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StorageReference) and bool(
            self._native.isEqual_(other._native)
        )

    def __hash__(self) -> int:
        return hash(self.gs_url)

    def __repr__(self) -> str:
        return f"StorageReference({self.gs_url!r})"

"""Cloud Storage for Firebase: upload and download files.

    from pyios_firebase.storage import Storage, StorageMetadata, StorageTaskStatus

    ref = Storage.storage().reference().child(f"users/{uid}/avatar.jpg")
    task = ref.put_file("/path/to/avatar.jpg", "image/jpeg", callback=on_uploaded)
    task.observe(StorageTaskStatus.PROGRESS, lambda s: print(f"{s.fraction_completed:.0%}"))

    ref.download_url(lambda url, error: ...)

Callbacks get Python values and a ``StorageError`` (or ``None``).

Needs the ``FirebaseStorage`` framework.
"""

from .storage import Storage  # noqa: I001 - first: the others import it lazily
from .errors import STORAGE_ERROR_DOMAIN, StorageError, StorageErrorCode
from .metadata import StorageMetadata
from .reference import StorageListResult, StorageReference
from .task import (
    StorageDownloadTask,
    StorageTask,
    StorageTaskSnapshot,
    StorageTaskStatus,
    StorageUploadTask,
)

__all__ = (
    "STORAGE_ERROR_DOMAIN",
    "Storage",
    "StorageDownloadTask",
    "StorageError",
    "StorageErrorCode",
    "StorageListResult",
    "StorageMetadata",
    "StorageReference",
    "StorageTask",
    "StorageTaskSnapshot",
    "StorageTaskStatus",
    "StorageUploadTask",
)

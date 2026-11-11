"""``StorageMetadata``: a file's content type, cache settings and custom metadata."""

from __future__ import annotations

__all__ = ("StorageMetadata",)

from collections.abc import Mapping
from datetime import datetime

from rubicon.objc import ns_from_py

from ..types import ObjCObject
from ..util import nsdate_to_datetime, objc_class, to_python


def _text(value: object) -> str | None:
    return None if value is None else str(value)


class StorageMetadata:
    """A file's metadata.

    Make one to upload with, or get one from an upload, ``get_metadata`` or
    ``update_metadata``. The settable fields can be changed and passed to
    ``StorageReference.update_metadata``; set one to ``None`` to delete it.

    ::

        metadata = StorageMetadata(content_type="image/jpeg", custom_metadata={"owner": uid})
        ref.put_data(jpeg_bytes, metadata=metadata)

    Args:
        content_type: the MIME type, for example ``"image/jpeg"``.
        cache_control: the ``Cache-Control`` header, for example
            ``"public, max-age=3600"``.
        content_disposition: the ``Content-Disposition`` header.
        content_encoding: the ``Content-Encoding`` header, for example ``"gzip"``.
        content_language: the ``Content-Language`` header, for example ``"en"``.
        custom_metadata: your own string keys and values.
        native: a native ``FIRStorageMetadata`` to wrap (instead of the
            fields above).
    """

    def __init__(
        self,
        content_type: str | None = None,
        cache_control: str | None = None,
        content_disposition: str | None = None,
        content_encoding: str | None = None,
        content_language: str | None = None,
        custom_metadata: Mapping[str, str] | None = None,
        *,
        native: ObjCObject | None = None,
    ) -> None:
        self._native: ObjCObject = (
            native
            if native is not None
            else objc_class("FIRStorageMetadata").alloc().init()
        )
        if native is None:
            for name, value in (
                ("content_type", content_type),
                ("cache_control", cache_control),
                ("content_disposition", content_disposition),
                ("content_encoding", content_encoding),
                ("content_language", content_language),
            ):
                if value is not None:
                    setattr(self, name, value)
            if custom_metadata is not None:
                self.custom_metadata = custom_metadata

    @property
    def native(self) -> ObjCObject:
        """The ``FIRStorageMetadata``."""
        return self._native

    # ---- settable -----------------------------------------------------------------

    @property
    def content_type(self) -> str | None:
        """The MIME type, for example ``"image/jpeg"``."""
        return _text(self._native.contentType)

    @content_type.setter
    def content_type(self, value: str | None) -> None:
        self._native.contentType = value

    @property
    def cache_control(self) -> str | None:
        """The ``Cache-Control`` header served with the file."""
        return _text(self._native.cacheControl)

    @cache_control.setter
    def cache_control(self, value: str | None) -> None:
        self._native.cacheControl = value

    @property
    def content_disposition(self) -> str | None:
        """The ``Content-Disposition`` header served with the file."""
        return _text(self._native.contentDisposition)

    @content_disposition.setter
    def content_disposition(self, value: str | None) -> None:
        self._native.contentDisposition = value

    @property
    def content_encoding(self) -> str | None:
        """The ``Content-Encoding`` header served with the file."""
        return _text(self._native.contentEncoding)

    @content_encoding.setter
    def content_encoding(self, value: str | None) -> None:
        self._native.contentEncoding = value

    @property
    def content_language(self) -> str | None:
        """The ``Content-Language`` header served with the file."""
        return _text(self._native.contentLanguage)

    @content_language.setter
    def content_language(self, value: str | None) -> None:
        self._native.contentLanguage = value

    @property
    def custom_metadata(self) -> dict[str, str]:
        """Your own string keys and values (a copy: assign a new dict to change it)."""
        custom = self._native.customMetadata
        return (
            {}
            if custom is None
            else {str(k): str(v) for k, v in to_python(custom).items()}
        )

    @custom_metadata.setter
    def custom_metadata(self, value: Mapping[str, str] | None) -> None:
        self._native.customMetadata = (
            None
            if value is None
            else ns_from_py({str(k): str(v) for k, v in value.items()})
        )

    # ---- read-only ----------------------------------------------------------------

    @property
    def bucket(self) -> str | None:
        """The bucket, for example ``"my-app.appspot.com"``."""
        return _text(self._native.bucket)

    @property
    def path(self) -> str | None:
        """The file's full path in the bucket."""
        return _text(self._native.path)

    @property
    def name(self) -> str | None:
        """The last part of the path."""
        return _text(self._native.name)

    @property
    def size(self) -> int:
        """The size in bytes."""
        return int(self._native.size)

    @property
    def md5_hash(self) -> str | None:
        """The MD5 hash of the content (base64), or ``None``."""
        return _text(self._native.md5Hash)

    @property
    def generation(self) -> int:
        """The content's version: changes each time the file is replaced."""
        return int(self._native.generation)

    @property
    def metageneration(self) -> int:
        """The metadata's version: changes each time the metadata is updated."""
        return int(self._native.metageneration)

    @property
    def time_created(self) -> datetime | None:
        """When the file was created (UTC)."""
        return nsdate_to_datetime(self._native.timeCreated)

    @property
    def updated(self) -> datetime | None:
        """When the file or its metadata last changed (UTC)."""
        return nsdate_to_datetime(self._native.updated)

    @property
    def is_file(self) -> bool:
        """True for a file."""
        value = self._native.isFile
        return bool(value() if callable(value) else value)

    @property
    def gs_url(self) -> str:
        """The ``gs://bucket/path`` URL of the file."""
        return f"gs://{self.bucket}/{self.path}"

    def __repr__(self) -> str:
        return f"<StorageMetadata {self.gs_url} {self.content_type} {self.size}B>"

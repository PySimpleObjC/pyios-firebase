# Cloud Storage reference

## At a glance

- `Storage.storage(url=None)`: `reference()`, `reference_with_path(path)`, `reference_for_url(url)`, `use_emulator(host, port)`, `max_upload_retry_time`, `max_download_retry_time`, `max_operation_retry_time`
- `StorageReference`: `full_path`, `name`, `bucket`, `gs_url`, `storage`, `root()`, `parent()`, `child(path)`; `put_data(data, content_type, callback, *, metadata)`, `put_file(path, ...)` → `StorageUploadTask`; `get_data(max_size, cb)`, `write_to_file(path, cb)` → `StorageDownloadTask`; `download_url(cb)`, `get_metadata(cb)`, `update_metadata(metadata, cb)`, `list_all(cb)`, `list(max_results, cb, page_token)`, `delete(cb)`
- `StorageMetadata(content_type, cache_control, content_disposition, content_encoding, content_language, custom_metadata)`; read-only `bucket`, `path`, `name`, `size`, `md5_hash`, `generation`, `metageneration`, `time_created`, `updated`, `is_file`, `gs_url`
- `StorageTask` (`StorageUploadTask`, `StorageDownloadTask`): `observe(status, handler)`, `remove_observer(handle)`, `pause()`, `resume()`, `cancel()`, `snapshot`
- `StorageTaskSnapshot`: `status`, `bytes_transferred`, `total_bytes`, `fraction_completed`, `metadata`, `error`, `reference`; `StorageTaskStatus`
- `StorageListResult` (`items`, `prefixes`, `page_token`), `StorageError` (`name`), `StorageErrorCode`

## `pyios_firebase.storage`

::: pyios_firebase.storage

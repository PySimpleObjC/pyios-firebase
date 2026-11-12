# Cloud Storage

[Cloud Storage for Firebase](https://firebase.google.com/docs/storage) keeps
user files (photos, videos, documents) in a Google Cloud Storage bucket, with
uploads that survive bad networks and access controlled by security rules.

```python
from pyios_firebase.storage import Storage

ref = Storage.storage().reference().child(f"users/{uid}/avatar.jpg")
ref.put_file("/path/to/avatar.jpg", "image/jpeg", callback=on_uploaded)
ref.download_url(lambda url, error: show_image(url))
```

## Installation

1. Add the **`FirebaseStorage`** Swift package product
   ([Installation](../getting-started/installation.md)).
2. In the console, open **Storage** and create the default bucket.
3. Write [security rules](https://firebase.google.com/docs/storage/security):

    ```js title="storage.rules"
    rules_version = '2';
    service firebase.storage {
      match /b/{bucket}/o {
        match /users/{uid}/{file=**} {
          allow read, write: if request.auth != null && request.auth.uid == uid
                             && request.resource.size < 10 * 1024 * 1024;
        }
      }
    }
    ```

### App configuration

What the app's build needs for this product. To combine several products, list
them all in one `products`; see [App configuration](../getting-started/configuration.md).

=== "kivyforge (pyproject.toml)"

    ```toml title="pyproject.toml"
    [[tool.kivy.ios.include_files]]
    dest = "."
    sources = ["GoogleService-Info.plist"]

    [tool.kivy.ios.native.swift_packages.Firebase]
    url = "https://github.com/firebase/firebase-ios-sdk.git"
    requirement = { from = "13.1.1" }
    products = ["FirebaseStorage"]

    [tool.kivy.ios.xcode.build_settings]
    OTHER_LDFLAGS = "$(inherited) -ObjC"
    ```

=== "Xcode (kivy-ios, Briefcase)"

    1. **File > Add Package Dependencies...**, `https://github.com/firebase/firebase-ios-sdk.git`, and pick **`FirebaseStorage`**.
    2. **Build Settings > Other Linker Flags**: add `-ObjC`.
    3. Add `GoogleService-Info.plist` to the app target.


## References

```python
storage = Storage.storage()

root = storage.reference()
avatar = root.child("users/ada/avatar.jpg")       # or storage.reference_with_path("users/ada/avatar.jpg")
same = storage.reference_for_url("gs://my-app.appspot.com/users/ada/avatar.jpg")

avatar.name, avatar.full_path, avatar.bucket, avatar.gs_url
avatar.parent(), avatar.root()
```

A reference is only a path: making one does nothing on the server.

## Upload

```python
from pyios_firebase.storage import StorageMetadata, StorageTaskStatus


def on_uploaded(metadata, error):
    if error is not None:
        return show(error.name)
    print("Uploaded", metadata.size, "bytes")


# from memory
task = avatar.put_data(jpeg_bytes, "image/jpeg", on_uploaded)

# from a file: large files go in chunks, and resume after a network change
task = avatar.put_file("/path/to/avatar.jpg", callback=on_uploaded)

# with metadata
metadata = StorageMetadata(
    content_type="image/jpeg",
    cache_control="public, max-age=3600",
    custom_metadata={"owner": uid},
)
task = avatar.put_file(path, callback=on_uploaded, metadata=metadata)
```

Uploading to an existing path replaces the file. Without a `content_type`,
`put_file` guesses it from the extension.

## Progress, pause, resume, cancel

Uploads and downloads return a task:

```python
def on_progress(snapshot):
    bar.value = snapshot.fraction_completed            # 0.0 to 1.0


handle = task.observe(StorageTaskStatus.PROGRESS, on_progress)
task.observe(StorageTaskStatus.SUCCESS, lambda snapshot: show("Done"))
task.observe(StorageTaskStatus.FAILURE, lambda snapshot: show(snapshot.error.name))

task.pause()
task.resume()
task.cancel()                       # the callback gets CANCELLED
task.remove_observer(handle)
```

| `StorageTaskStatus` | When |
|---|---|
| `RESUME` | The task starts or resumes |
| `PROGRESS` | More bytes went through |
| `PAUSE` | It was paused |
| `SUCCESS` | It finished |
| `FAILURE` | It failed (`snapshot.error`) |

A snapshot has `bytes_transferred`, `total_bytes`, `fraction_completed`,
`status`, `metadata`, `error` and `reference`. Observers are released when the
task ends.

## Download

```python
# into memory: max_size guards against huge files
avatar.get_data(5 * 1024 * 1024, lambda data, error: show_image_bytes(data))

# to a file (large files)
avatar.write_to_file("/path/to/cache/avatar.jpg", lambda path, error: show_image_file(path))

# a long-lived https:// URL, for an image widget or to share
avatar.download_url(lambda url, error: setattr(image, "source", url))
```

A file bigger than `max_size` fails with `DOWNLOAD_SIZE_EXCEEDED`.
pyios-firebase checks the bytes received as well: the SDK checks only from
download progress, which a small download may never report.

!!! note "Download URLs are public"
    Anyone with a download URL can read the file, whatever the rules say. It
    stays valid until you revoke it in the console. Use `get_data` or
    `write_to_file` for files only the user may read.

## Metadata

```python
def on_metadata(metadata, error):
    print(metadata.content_type, metadata.size, metadata.updated, metadata.custom_metadata)
    metadata.cache_control = "public, max-age=300"
    metadata.content_language = None                    # delete this field
    metadata.custom_metadata = {**metadata.custom_metadata, "reviewed": "yes"}
    avatar.update_metadata(metadata, on_updated)


avatar.get_metadata(on_metadata)
```

Settable: `content_type`, `cache_control`, `content_disposition`,
`content_encoding`, `content_language`, `custom_metadata`. Read-only:
`bucket`, `path`, `name`, `size`, `md5_hash`, `generation`, `metageneration`,
`time_created`, `updated`. Only the fields you change are sent.

## List files

```python
def on_list(result, error):
    for item in result.items:            # files
        print(item.full_path)
    for prefix in result.prefixes:       # "folders"
        print(prefix.full_path + "/")
    if result.page_token is not None:
        folder.list(100, on_list, result.page_token)   # the next page


folder = Storage.storage().reference().child(f"users/{uid}")
folder.list(100, on_list)
folder.list_all(on_list)                 # everything at once: only for small folders
```

Listing needs `rules_version = '2'`.

## Delete

```python
avatar.delete(lambda error: print("Deleted" if error is None else error.name))
```

Deleting a missing file gives `OBJECT_NOT_FOUND`.

## Several buckets

```python
archive = Storage.storage("gs://my-app-archive")
```

## Retries

```python
storage = Storage.storage()
storage.max_upload_retry_time = 60          # seconds (default 600)
storage.max_download_retry_time = 60
storage.max_operation_retry_time = 30       # metadata, delete, list (default 120)
```

## Errors

Errors are `StorageError`s (`name` from `StorageErrorCode`):

| `StorageErrorCode` | Means |
|---|---|
| `OBJECT_NOT_FOUND` | No file at that path |
| `UNAUTHENTICATED` | The rules need a signed-in user |
| `UNAUTHORIZED` | The rules do not allow it |
| `QUOTA_EXCEEDED` | The project's quota is used up |
| `RETRY_LIMIT_EXCEEDED` | It kept failing for longer than the retry time |
| `DOWNLOAD_SIZE_EXCEEDED` | The file is bigger than `max_size` |
| `CANCELLED` | You cancelled the task |
| `NON_MATCHING_CHECKSUM` | The file was corrupted on the way |

## Use the local emulator

```python
Storage.storage().use_emulator("127.0.0.1", 9199)
```

!!! warning "Emulator quirk: stale metadata after delete"
    The Storage emulator sends the file's own `Cache-Control` on metadata
    responses, so iOS can cache them: with a cacheable `cache_control` (say
    `"public, max-age=300"`), `get_metadata` may still find a file you just
    deleted. Use `"no-cache"` on test files. Production is not affected.

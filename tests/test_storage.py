from types import SimpleNamespace

import pytest
from conftest import Recorder, fire, make_error
from rubicon.objc import NSObject, ObjCClass, ns_from_py, objc_property

import pyios_firebase.storage.reference as reference_module
from pyios_firebase.storage import (
    Storage,
    StorageErrorCode,
    StorageListResult,
    StorageMetadata,
    StorageReference,
    StorageTaskStatus,
    StorageUploadTask,
)


def storage_error(code=StorageErrorCode.OBJECT_NOT_FOUND):
    return make_error("Object does not exist", code, "FIRStorageErrorDomain")


# ---- metadata ---------------------------------------------------------------------------


def test_metadata_fields_round_trip():
    native = SimpleNamespace(
        contentType=None,
        cacheControl=None,
        contentDisposition=None,
        contentEncoding=None,
        contentLanguage=None,
        customMetadata=None,
    )
    metadata = StorageMetadata(native=native)
    metadata.content_type = "image/jpeg"
    metadata.cache_control = "max-age=60"
    metadata.custom_metadata = {"owner": "ada", "n": 1}
    assert native.contentType == "image/jpeg" and native.cacheControl == "max-age=60"
    assert metadata.custom_metadata == {"owner": "ada", "n": "1"}  # values are strings
    metadata.cache_control = None  # delete it
    assert native.cacheControl is None and metadata.cache_control is None


def test_metadata_read_only_fields():
    nsdate = ObjCClass("NSDate").dateWithTimeIntervalSince1970_(0)
    native = SimpleNamespace(
        bucket="b",
        path="a/b.txt",
        name="b.txt",
        size=12,
        md5Hash="h",
        generation=3,
        metageneration=1,
        timeCreated=nsdate,
        updated=None,
        isFile=lambda: True,
        contentType="text/plain",
    )
    metadata = StorageMetadata(native=native)
    assert (metadata.bucket, metadata.path, metadata.name, metadata.size) == (
        "b",
        "a/b.txt",
        "b.txt",
        12,
    )
    assert metadata.gs_url == "gs://b/a/b.txt" and metadata.is_file is True
    assert metadata.time_created.year == 1970 and metadata.updated is None
    assert (metadata.generation, metadata.metageneration, metadata.md5_hash) == (
        3,
        1,
        "h",
    )


# ---- references -----------------------------------------------------------------------


class FakeListResult(NSObject):
    items = objc_property()
    prefixes = objc_property()
    pageToken = objc_property()


def test_reference_navigation():
    root = SimpleNamespace(fullPath="", name="", bucket="b")
    native = Recorder(
        {
            "root": root,
            "parent": None,
            "child_": lambda: SimpleNamespace(fullPath="a/b", name="b", bucket="b"),
        }
    )
    native.fullPath, native.name, native.bucket = "a", "a", "b"
    ref = StorageReference(native)
    assert ref.gs_url == "gs://b/a" and ref.child("b").full_path == "a/b"
    assert ref.root().full_path == "" and ref.parent() is None


def test_list_and_errors(blocks):
    native, out = Recorder(), []
    ref = StorageReference(native)
    ref.list(2, lambda r, e: out.append((r, e)))
    result = FakeListResult.new()
    result.items = ns_from_py([])
    result.prefixes = ns_from_py([])
    result.pageToken = "next"
    fire(native.block("listWithMaxResults_completion_"), result, None)
    ref.list(2, lambda r, e: out.append((r, e)), page_token="next")
    assert native.last("listWithMaxResults_pageToken_completion_")[:2] == (2, "next")
    ref.list_all(lambda r, e: out.append((r, e)))
    fire(
        native.block("listAllWithCompletion_"),
        None,
        storage_error(StorageErrorCode.UNAUTHORIZED),
    )
    assert out[0] == (StorageListResult(items=[], prefixes=[], page_token="next"), None)
    assert out[1][0] is None and out[1][1].name == "UNAUTHORIZED"


def test_get_data_gives_bytes_and_named_errors(blocks):
    # the SDK always returns a task
    native, out = Recorder({"dataWithMaxSize_completion_": Recorder}), []
    ref = StorageReference(native)
    ref.get_data(10, lambda d, e: out.append((d, e)))
    fire(native.block("dataWithMaxSize_completion_"), ns_from_py(b"\x00hello"), None)
    ref.get_data(1, lambda d, e: out.append((d, e)))
    fire(
        native.block("dataWithMaxSize_completion_"),
        None,
        storage_error(StorageErrorCode.DOWNLOAD_SIZE_EXCEEDED),
    )
    assert out[0] == (b"\x00hello", None)
    assert out[1][1].name == "DOWNLOAD_SIZE_EXCEEDED" and out[1][1].code == -13032


def test_put_data_with_metadata_shortcut(monkeypatch):
    made = []

    class FakeMetadata:
        def __init__(self):
            self.native = "META"
            self.content_type = None
            made.append(self)

    monkeypatch.setattr(reference_module, "StorageMetadata", FakeMetadata)
    native = Recorder({"putData_metadata_completion_": Recorder()})
    task = StorageReference(native).put_data(b"x", "text/plain")
    assert isinstance(task, StorageUploadTask)
    assert (
        native.last("putData_metadata_completion_")[1] == "META"
        and made[0].content_type == "text/plain"
    )
    StorageReference(native).put_data(b"x")
    assert native.last("putData_metadata_completion_")[1] is None


def test_storage_instances_and_settings(monkeypatch):
    import pyios_firebase.storage.storage as storage_module

    fake = Recorder(
        {"storage": lambda: Recorder(), "storageWithURL_": lambda: Recorder()}
    )
    monkeypatch.setattr(storage_module, "objc_class", lambda name: fake)
    monkeypatch.setattr(Storage, "_instances", {})
    assert Storage.storage() is Storage.storage()
    other = Storage.storage("gs://other-bucket")
    assert other is not Storage.storage() and fake.calls[-1] == (
        "storageWithURL_",
        ("gs://other-bucket",),
    )
    other.max_upload_retry_time = 30
    assert other.native.maxUploadRetryTime == 30.0


# ---- tasks ------------------------------------------------------------------------------


class FakeSnapshot(NSObject):
    status = objc_property(int)
    progress = objc_property()
    metadata = objc_property()
    error = objc_property()
    reference = objc_property()


def test_task_observers_live_until_the_task_ends(blocks):
    handles = iter(f"h{i}" for i in range(10))
    native = Recorder({"observeStatus_handler_": lambda: next(handles)})
    task = StorageUploadTask(native)
    seen = []
    handle = task.observe(StorageTaskStatus.PROGRESS, lambda s: seen.append(s.status))
    assert len(blocks) == 3  # the two internal end observers and ours
    progress_block = native.calls[-1][1][1]
    snapshot = FakeSnapshot.new()
    snapshot.status = StorageTaskStatus.PROGRESS
    fire(progress_block, snapshot)
    assert seen == [StorageTaskStatus.PROGRESS]
    task.remove_observer(handle)
    assert native.last("removeObserverWithHandle_") == (handle,) and len(blocks) == 2
    success_block = native.calls[0][1][1]
    snapshot.status = StorageTaskStatus.SUCCESS
    fire(success_block, snapshot)
    assert not blocks  # everything released when the task finished


def test_task_controls():
    native = Recorder({"observeStatus_handler_": "h"})
    task = StorageUploadTask(native)
    task.pause()
    task.resume()
    task.cancel()
    assert [c[0] for c in native.calls[-3:]] == ["pause", "resume", "cancel"]


def test_error_codes():
    assert (
        StorageErrorCode.OBJECT_NOT_FOUND == -13010
        and StorageErrorCode.CANCELLED == -13040
    )


@pytest.mark.parametrize(
    "status", [StorageTaskStatus.SUCCESS, StorageTaskStatus.FAILURE]
)
def test_status_values(status):
    assert status in (4, 5)


def test_get_data_enforces_max_size_on_the_bytes(blocks):
    """The SDK checks max_size only from download progress; small downloads may skip it."""
    native, out = Recorder({"dataWithMaxSize_completion_": Recorder}), []
    StorageReference(native).get_data(5, lambda d, e: out.append((d, e)))
    fire(native.block("dataWithMaxSize_completion_"), ns_from_py(b"0123456789"), None)
    data, error = out[0]
    assert data is None and error.name == "DOWNLOAD_SIZE_EXCEEDED"
    assert (
        error.code == StorageErrorCode.DOWNLOAD_SIZE_EXCEEDED
        and "10 bytes" in error.description
    )

"""End-to-end Cloud Storage tests: the real SDK against the Storage emulator.

Every run works under ``e2e/{RUN_ID}/`` in the bucket.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from firestore_tests import RUN_ID
from pyios_firebase.storage import (
    Storage,
    StorageErrorCode,
    StorageMetadata,
    StorageTaskStatus,
)
from runner import TestContext, expect, expect_equal

BUCKET = "demo-pyios-firebase.appspot.com"


def folder():
    return Storage.storage().reference().child(f"e2e/{RUN_ID}")


def test_storage_references(t: TestContext) -> None:
    ref = Storage.storage().reference_with_path(f"e2e/{RUN_ID}/a/b.txt")
    expect_equal(ref.full_path, f"e2e/{RUN_ID}/a/b.txt", "full path")
    expect_equal(ref.name, "b.txt", "name")
    expect_equal(ref.bucket, BUCKET, "bucket")
    expect_equal(ref.parent().full_path, f"e2e/{RUN_ID}/a", "parent")
    expect_equal(ref.root().full_path, "", "root")
    expect(ref.root().parent() is None, "the root has no parent")
    expect_equal(folder().child("a//b.txt/"), ref, "child normalizes slashes; references compare equal")
    expect_equal(Storage.storage().reference_for_url(f"gs://{BUCKET}/e2e/{RUN_ID}/a/b.txt"), ref, "from a gs:// URL")
    t.passed()


def test_storage_upload_download_and_metadata(t: TestContext) -> None:
    ref = folder().child("hello.txt")
    content = "héllo storage ✓\n".encode() * 3

    def deleted(error) -> None:
        expect(error is None, error)

        def check(metadata, get_error) -> None:
            expect(metadata is None and get_error is not None, "deleted")
            expect_equal(get_error.name, "OBJECT_NOT_FOUND", "error name")
            expect_equal(get_error.code, StorageErrorCode.OBJECT_NOT_FOUND, "error code")
            t.passed()

        ref.get_metadata(t.step(check))

    def too_big(data, error) -> None:
        expect(data is None and error is not None, "max_size is enforced")
        expect_equal(error.code, StorageErrorCode.DOWNLOAD_SIZE_EXCEEDED, "code")
        ref.delete(t.step(deleted))

    def downloaded(data, error) -> None:
        expect(error is None, error)
        expect_equal(data, content, "the same bytes back")
        ref.get_data(5, t.step(too_big))

    def got_url(url, error) -> None:
        expect(error is None, error)
        expect(url.startswith("http://127.0.0.1:9199/") and "hello.txt" in url, url)
        ref.get_data(1024 * 1024, t.step(downloaded))

    def updated(metadata, error) -> None:
        expect(error is None, error)
        expect_equal(metadata.cache_control, "no-cache", "updated cache control")
        expect_equal(metadata.custom_metadata, {"owner": "ada", "run": RUN_ID, "reviewed": "yes"}, "custom metadata")
        expect(metadata.content_language is None, "content language deleted")
        expect(metadata.metageneration >= 2, f"metageneration grows: {metadata.metageneration}")
        ref.download_url(t.step(got_url))

    def got_metadata(metadata, error) -> None:
        expect(error is None, error)
        expect_equal(metadata.content_language, "en", "content language")
        # not a cacheable value: the emulator sends the object's Cache-Control on
        # metadata responses too, and iOS would then serve them stale after delete
        metadata.cache_control = "no-cache"
        metadata.content_language = None  # delete it
        metadata.custom_metadata = {**metadata.custom_metadata, "reviewed": "yes"}
        ref.update_metadata(metadata, t.step(updated))

    def uploaded(metadata, error) -> None:
        expect(error is None, error)
        expect_equal(metadata.size, len(content), "size")
        expect_equal(metadata.content_type, "text/plain; charset=utf-8", "content type")
        expect_equal(metadata.custom_metadata, {"owner": "ada", "run": RUN_ID}, "custom metadata")
        expect_equal(metadata.path, ref.full_path, "path")
        expect(metadata.time_created is not None and metadata.md5_hash, "server fields")
        ref.get_metadata(t.step(got_metadata))

    metadata = StorageMetadata(content_type="text/plain; charset=utf-8", content_language="en",
                               custom_metadata={"owner": "ada", "run": RUN_ID})
    ref.put_data(content, callback=t.step(uploaded), metadata=metadata)


def test_storage_files_and_listing(t: TestContext) -> None:
    base = folder().child("listing")
    tmp = tempfile.mkdtemp()
    source = os.path.join(tmp, "upload.bin")
    with open(source, "wb") as f:
        f.write(os.urandom(4096))
    names = ["a.bin", "b.bin", "c.bin", "sub/d.bin"]
    pending = list(names)

    def second_page(result, error) -> None:
        expect(error is None, error)
        expect_equal([r.name for r in result.items], ["c.bin"], "page 2")
        expect(result.page_token is None, "last page")
        t.passed()

    def first_page(result, error) -> None:
        expect(error is None, error)
        expect_equal([r.name for r in result.items], ["a.bin", "b.bin"], "page 1")
        expect(result.page_token, "a token for the next page")
        base.list(2, t.step(second_page), page_token=result.page_token)

    def listed_all(result, error) -> None:
        expect(error is None, error)
        expect_equal(sorted(r.name for r in result.items), ["a.bin", "b.bin", "c.bin"], "files")
        expect_equal([p.name for p in result.prefixes], ["sub"], "sub-folders")
        base.list(2, t.step(first_page))

    def written(path, error) -> None:
        expect(error is None, error)
        with open(path, "rb") as f, open(source, "rb") as g:
            expect_equal(f.read(), g.read(), "write_to_file gives the uploaded file")
        base.list_all(t.step(listed_all))

    def uploaded(metadata, error) -> None:
        expect(error is None, error)
        if pending:
            base.child(pending.pop(0)).put_file(source, callback=t.step(uploaded))
            return
        base.child("a.bin").write_to_file(os.path.join(tmp, "download.bin"), t.step(written))

    uploaded(None, None)


def test_storage_upload_task_progress(t: TestContext) -> None:
    ref = folder().child("big.bin")
    data = os.urandom(3 * 1024 * 1024)
    seen: dict[str, Any] = {"progress": [], "statuses": []}

    def on_success(snapshot) -> None:
        seen["statuses"].append("success")
        expect_equal(snapshot.status, StorageTaskStatus.SUCCESS, "status")
        expect(seen["progress"], "progress was reported")
        # the counts are of the request body: the file plus the multipart framing
        expect(seen["progress"][-1] >= len(data), f"all bytes sent: {seen['progress'][-1:]} / {len(data)}")
        expect(seen["progress"] == sorted(seen["progress"]), "progress only grows")
        expect_equal(snapshot.metadata.size, len(data), "metadata in the success snapshot")

    def done(metadata, error) -> None:
        expect(error is None, error)
        from kivy.clock import Clock

        Clock.schedule_once(t.step(lambda dt: (expect("success" in seen["statuses"], seen), t.passed())), 0.2)

    task = ref.put_data(data, "application/octet-stream", callback=t.step(done))
    task.observe(StorageTaskStatus.PROGRESS, lambda s: seen["progress"].append(s.bytes_transferred))
    task.observe(StorageTaskStatus.SUCCESS, t.step(on_success))


def test_storage_cancel_upload(t: TestContext) -> None:
    ref = folder().child("cancelled.bin")
    failures: list[Any] = []

    def done(metadata, error) -> None:
        expect(metadata is None and error is not None, "a cancelled upload fails")
        expect_equal(error.code, StorageErrorCode.CANCELLED, f"code ({error.name})")
        t.passed()

    task = ref.put_data(os.urandom(8 * 1024 * 1024), callback=t.step(done))
    task.observe(StorageTaskStatus.FAILURE, lambda s: failures.append(s.error))
    task.cancel()


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]

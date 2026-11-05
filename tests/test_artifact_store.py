import hashlib
import multiprocessing as mp
from pathlib import Path
import pytest
from gcode.runtime.artifacts import ArtifactStore


def _put_worker(directory, gate, output):
    store = ArtifactStore(directory)
    gate.wait()
    for _ in range(10):
        rec = store.put("并发内容", source_tool_call_id="call-shared")
        assert store.get(rec["artifact_id"]) == "并发内容".encode()
    output.put(rec["artifact_id"])


def test_multiprocess_dedup_and_private_storage(tmp_path):
    directory = str(tmp_path / "session")
    gate = mp.Event()
    output = mp.Queue()
    workers = [
        mp.Process(target=_put_worker, args=(directory, gate, output)) for _ in range(4)
    ]
    for worker in workers:
        worker.start()
    gate.set()
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0
    ids = [output.get(timeout=2) for _ in workers]
    assert (
        len(set(ids)) == 1 and ids[0] == hashlib.sha256("并发内容".encode()).hexdigest()
    )
    store = ArtifactStore(directory)
    assert store.get(ids[0]) == "并发内容".encode()
    root = Path(directory) / "artifact-store"
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / "index.sqlite3").stat().st_mode & 0o777 == 0o600
    assert (root / "objects" / ids[0]).stat().st_mode & 0o777 == 0o600
    assert store.plan_gc() == []  # A durable call binding is also a reference.


def test_two_owners_retain_release_and_plan_is_dry_run(tmp_path):
    store = ArtifactStore(tmp_path / "s")
    rec = store.put("payload")
    aid = rec["artifact_id"]
    assert store.plan_gc() == [rec]
    store.retain(aid, "owner1", "ref")
    store.retain(aid, "owner2", "ref")
    store.retain(aid, "owner1", "ref")
    assert ArtifactStore(tmp_path / "s").plan_gc() == []
    assert store.release(aid, "owner1", "ref")
    assert not store.release(aid, "owner1", "ref")
    assert store.plan_gc() == []
    assert store.release(aid, "owner2", "ref")
    assert store.plan_gc() == [rec] and Path(rec["path"]).exists()
    assert store.get(aid) == b"payload"


def test_call_bindings_are_immutable_and_content_deduped(tmp_path):
    store = ArtifactStore(tmp_path / "s")
    a = store.put("same", source_tool_call_id="a")
    b = store.put(b"same", source_tool_call_id="b")
    assert a == b and store.bind_call("a", a["artifact_id"]) == a["artifact_id"]
    other = store.put("different")
    with pytest.raises(ValueError):
        store.bind_call("a", other["artifact_id"])
    with pytest.raises(ValueError):
        store.put("different", source_tool_call_id="b")
    assert store.get(a["artifact_id"]) == b"same"
    assert a["artifact_id"] not in {r["artifact_id"] for r in store.plan_gc()}


def test_wrong_id_corruption_and_unknown_files_fail_closed(tmp_path):
    store = ArtifactStore(tmp_path / "s")
    rec = store.put("original")
    aid = rec["artifact_id"]
    for bad in ("../outside", "X" * 64, "a" * 63, "a" * 64 + "/x"):
        with pytest.raises(ValueError):
            store.get(bad)
    with pytest.raises(KeyError):
        store.get("a" * 64)
    path = Path(rec["path"])
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="hash"):
        store.get(aid)
    with pytest.raises(ValueError, match="hash"):
        store.put("original")
    with pytest.raises(ValueError, match="hash"):
        store.plan_gc()
    orphan = path.parent / "unknown"
    orphan.write_text("keep")
    assert orphan.read_text() == "keep"


def test_same_bytes_multiple_mime_and_symlink_object_not_followed(tmp_path):
    store = ArtifactStore(tmp_path / "s")
    rec = store.put(b"x", mime="text/plain")
    alternative = store.put(b"x", mime="application/octet-stream")
    assert (
        alternative["artifact_id"] == rec["artifact_id"]
        and alternative["path"] == rec["path"]
    )
    assert (
        alternative["mime"] == "application/octet-stream"
        and rec["mime"] == "text/plain"
    )
    target = Path(rec["path"])
    target.unlink()
    outside = tmp_path / "outside"
    outside.write_bytes(b"x")
    target.symlink_to(outside)
    with pytest.raises((OSError, ValueError)):
        store.get(rec["artifact_id"])
    assert outside.read_bytes() == b"x"


def test_symlink_index_rejected_without_touching_target(tmp_path):
    root = tmp_path / "s" / "artifact-store"
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    (root / "index.sqlite3").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        ArtifactStore(tmp_path / "s")
    assert outside.read_text() == "untouched"

import asyncio
import hashlib
import os
import shlex
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from gcode.runtime.artifacts import ArtifactStore
from gcode.tools.bash import Bash, Params


def command(code):
    return shlex.quote(sys.executable) + " -c " + shlex.quote(code)


def context(tmp_path):
    return SimpleNamespace(
        cwd=tmp_path, artifact_dir=tmp_path / "artifacts", tool_call_id="call-1"
    )


def hash_file(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


@pytest.mark.asyncio
async def test_multimegabyte_stdout_and_stderr_preserved_with_bounded_render(tmp_path):
    size = 5 * 1024 * 1024 + 123
    source = f"import os; os.write(1,b'A'*{size}); os.write(2,b'B'*{size})"
    result = await Bash().invoke(Params(command=command(source)), context(tmp_path))
    assert not result.is_error and len(result.output) <= 10000
    assert "STDOUT:" in result.output and "STDERR:" in result.output
    assert (
        result.details["process_state"] == "exited" and result.details["exit_code"] == 0
    )
    assert result.details["business_outcome"] == "unverified"
    assert result.details["stdout_bytes"] == result.details["stderr_bytes"] == size
    assert len(result.details["artifacts"]) == 2
    for rec, byte in zip(result.details["artifacts"], (b"A", b"B")):
        digest, n = hash_file(rec["path"])
        expected = hashlib.sha256()
        left = size
        while left:
            chunk = byte * min(65536, left)
            expected.update(chunk)
            left -= len(chunk)
        assert (
            digest == rec["artifact_id"] == expected.hexdigest()
            and n == size
            and rec["complete"]
        )
    print(
        {
            "stdout_bytes": size,
            "stderr_bytes": size,
            "rendered_chars": len(result.output),
            "artifact_count": 2,
        }
    )


@pytest.mark.asyncio
async def test_timeout_keeps_partial_artifact_and_unknown_effect(tmp_path):
    source = "import os,time; os.write(1,b'X'*20000); time.sleep(30)"
    result = await Bash().invoke(
        Params(command=command(source), timeout=1), context(tmp_path)
    )
    assert result.is_error and "timed out" in result.output
    assert result.details["delivery_state"] == "delivery_unknown"
    assert (
        result.details["process_state"] == "exited"
        and result.details["business_outcome"] == "unverified"
    )
    rec = result.details["artifacts"][0]
    assert not rec["complete"] and rec["size"] == 20000
    assert hash_file(rec["path"])[0] == rec["artifact_id"]
    assert not list((tmp_path / "artifacts").rglob(".pending-*"))


@pytest.mark.asyncio
async def test_small_output_and_nonzero_exit_are_not_false_business_failure(tmp_path):
    result = await Bash().invoke(
        Params(
            command=command(
                "import sys; print('ok'); print('err',file=sys.stderr); sys.exit(3)"
            )
        ),
        context(tmp_path),
    )
    assert result.is_error and result.output == "STDOUT:\nok\n\nSTDERR:\nerr\n"
    assert (
        result.details["exit_code"] == 3
        and result.details["business_outcome"] == "unverified"
    )
    assert result.details["artifacts"] == []


@pytest.mark.asyncio
async def test_reader_failure_terminates_process_and_is_unknown(tmp_path, monkeypatch):
    async def fail(reader, capture):
        transport = getattr(reader, "_transport", None)
        if transport:
            transport.close()
        raise OSError("injected reader failure")

    monkeypatch.setattr(Bash, "_pump", staticmethod(fail))
    result = await asyncio.wait_for(
        Bash().invoke(
            Params(command=command("import time; time.sleep(30)")), context(tmp_path)
        ),
        5,
    )
    assert result.is_error and "injected reader failure" in result.output
    assert result.details["delivery_state"] == "delivery_unknown"
    assert result.details["process_state"] == "exited"
    assert not list(tmp_path.rglob(".pending-*"))


def test_stream_import_bounded_reads_and_same_content_dedup(tmp_path):
    class Stream:
        def __init__(self):
            self.remaining = 5 * 1024 * 1024
            self.calls = 0

        def read(self, n):
            assert n <= 65536
            self.calls += 1
            count = min(n, self.remaining)
            self.remaining -= count
            return b"K" * count

    store = ArtifactStore(tmp_path / "s")
    stream = Stream()
    first = store.put_stream(stream, source_tool_call_id="one")
    other = tmp_path / "source"
    other.write_bytes(b"K" * (5 * 1024 * 1024))
    second = store.put_file(other, source_tool_call_id="two")
    assert stream.calls > 1 and first["artifact_id"] == second["artifact_id"]
    assert (
        first["size"] == other.stat().st_size
        and hash_file(first["path"])[0] == first["artifact_id"]
    )


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="process group requires POSIX")
async def test_cancel_large_output_kills_grandchild_and_leaves_no_spool(tmp_path):
    pidfile = tmp_path / "child.pid"
    source = (
        "import os,signal,time,pathlib; child=os.fork(); "
        "\nif child==0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30); os._exit(0)\n"
        f"os.write(1,b'Z'*30000); pathlib.Path({str(pidfile)!r}).write_text(str(child)); time.sleep(30)"
    )
    task = asyncio.create_task(
        Bash().invoke(Params(command=command(source)), context(tmp_path))
    )
    async with asyncio.timeout(5):
        while True:
            try:
                pid = int(pidfile.read_text())
                break
            except (OSError, ValueError):
                await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with asyncio.timeout(5):
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
    assert not list(tmp_path.rglob(".pending-*"))
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_timeout_artifact_error_is_typed_unknown(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(ArtifactStore, "put_stream", fail)
    result = await Bash().invoke(
        Params(
            command=command("import os,time; os.write(1,b'X'*20000); time.sleep(30)"),
            timeout=1,
        ),
        context(tmp_path),
    )
    assert result.is_error and "disk full" in result.output
    assert result.details["delivery_state"] == "delivery_unknown"
    assert result.details["business_outcome"] == "unverified"


def test_stream_import_rejects_missing_bytes_without_registering_artifact(tmp_path):
    class Broken:
        def read(self, n):
            return None

    store = ArtifactStore(tmp_path / "s")
    with pytest.raises(TypeError):
        store.put_stream(Broken())
    assert store.plan_gc() == []
    assert not list((tmp_path / "s").rglob(".pending-*"))

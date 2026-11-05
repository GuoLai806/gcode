import asyncio
import os
from pathlib import Path
import pytest
from gcode.cache import FileCache
from gcode.runtime.context import ToolExecutionContext
from gcode.tools.file_state_cache import FileStateCache
from gcode.tools.read_file import ReadFile, Params as ReadParams
from gcode.tools.write_file import WriteFile, Params as WriteParams
from gcode.permissions.rules import RuleEngine, ScopedRuleView


def ctx(path, run):
    return ToolExecutionContext(
        run_id=run, session_id="session", cwd=path, artifact_dir=path
    )


@pytest.mark.asyncio
async def test_external_change_with_same_mtime_never_uses_stale_cache(tmp_path):
    path = tmp_path / "file"
    path.write_text("old")
    state = FileStateCache()
    cache = FileCache()
    reader = ReadFile(cache, state)
    writer = WriteFile(cache, file_state_cache=state)
    context = ctx(tmp_path, "a")
    assert "old" in (await reader.invoke(ReadParams(file_path="file"), context)).output
    before = path.stat()
    path.write_text("new")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert cache.get(str(path.resolve())) is None
    assert (
        await writer.invoke(WriteParams(file_path="file", content="unsafe"), context)
    ).is_error
    assert "new" in (await reader.invoke(ReadParams(file_path="file"), context)).output
    assert not (
        await writer.invoke(WriteParams(file_path="file", content="safe"), context)
    ).is_error


@pytest.mark.asyncio
async def test_read_permission_is_run_scoped_even_concurrently(tmp_path):
    path = tmp_path / "file"
    path.write_text("old")
    state = FileStateCache()
    reader = ReadFile(file_state_cache=state)
    writer = WriteFile(file_state_cache=state)
    a, b = ctx(tmp_path, "a"), ctx(tmp_path, "b")
    read = await reader.invoke(ReadParams(file_path="file"), a)
    assert not read.is_error
    blocked, allowed = await asyncio.gather(
        writer.invoke(WriteParams(file_path="file", content="bad"), b),
        writer.invoke(WriteParams(file_path="file", content="good"), a),
    )
    assert blocked.is_error and not allowed.is_error and path.read_text() == "good"
    # A direct legacy read is deliberately a separate scope from invoked tools.
    other = tmp_path / "other"
    other.write_text("base")
    await reader.execute(ReadParams(file_path=str(other)))
    assert (
        await writer.invoke(WriteParams(file_path="other", content="bad"), a)
    ).is_error


@pytest.mark.asyncio
async def test_change_during_read_fails_and_does_not_authorize_write(
    tmp_path, monkeypatch
):
    import builtins

    path = tmp_path / "file"
    path.write_text("old")
    state = FileStateCache()
    reader = ReadFile(file_state_cache=state)
    writer = WriteFile(file_state_cache=state)
    original = Path.open

    class Wrapper:
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            self.inner.__enter__()
            return self

        def __exit__(self, *args):
            return self.inner.__exit__(*args)

        def fileno(self):
            return self.inner.fileno()

        def read(self):
            data = self.inner.read()
            with builtins.open(path, "wb") as stream:
                stream.write(b"modified")
            return data

    def opened(self, *args, **kwargs):
        stream = original(self, *args, **kwargs)
        return Wrapper(stream) if self == path and args and args[0] == "rb" else stream

    monkeypatch.setattr(Path, "open", opened)
    result = await reader.invoke(ReadParams(file_path="file"), ctx(tmp_path, "a"))
    assert result.is_error and "changed while" in result.output
    monkeypatch.setattr(Path, "open", original)
    assert (
        await writer.invoke(
            WriteParams(file_path="file", content="bad"), ctx(tmp_path, "a")
        )
    ).is_error
    assert path.read_text() == "modified"


def test_nested_rule_view_applies_original_and_rebased_denies(tmp_path):
    parent = tmp_path / "parent"
    child = tmp_path / "child"
    grandchild = tmp_path / "grandchild"
    for p in (parent, child, grandchild):
        p.mkdir()
    rule = tmp_path / "rules.yaml"
    rule.write_text(f'- rule: "WriteFile({parent / "secret"})"\n  effect: deny\n')
    base = RuleEngine(project_rules_path=rule)
    first = ScopedRuleView(base, child, parent)
    second = ScopedRuleView(first, grandchild, child)
    assert second.evaluate("WriteFile", str(grandchild / "secret")) == "deny"
    assert second.evaluate("WriteFile", str(grandchild / "normal")) is None


@pytest.mark.asyncio
async def test_same_mtime_same_normalized_text_but_changed_raw_bytes_rejected(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"a\r\nb\n")
    state = FileStateCache()
    reader = ReadFile(file_state_cache=state)
    writer = WriteFile(file_state_cache=state)
    context = ctx(tmp_path, "a")
    assert not (await reader.invoke(ReadParams(file_path="file"), context)).is_error
    before = path.stat()
    path.write_bytes(b"a\nb\r\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert (
        await writer.invoke(WriteParams(file_path="file", content="unsafe"), context)
    ).is_error
    assert path.read_bytes() == b"a\nb\r\n"


@pytest.mark.asyncio
async def test_legacy_cache_and_state_stubs_keep_three_argument_contract(tmp_path):
    path = tmp_path / "file"
    path.write_text("fresh")

    class Cache:
        def __init__(self):
            self.writes = []

        def get(self, path):
            return "stale"

        def put(self, path, text):
            self.writes.append((path, text))

    class State:
        def __init__(self):
            self.records = []

        def record(self, path, text, mtime):
            self.records.append((path, text, mtime))

    cache = Cache()
    state = State()
    result = await ReadFile(cache, state).execute(ReadParams(file_path=str(path)))
    assert (
        not result.is_error
        and "fresh" in result.output
        and "stale" not in result.output
    )
    assert cache.writes[0][1] == "fresh" and state.records[0][1] == "fresh"

from dataclasses import dataclass
from types import SimpleNamespace
import sys
import pytest
from gcode.tools.base import ToolResult
from gcode.tools.desktop import DesktopParams, DesktopTool


class FakeTransport:
    def __init__(self):
        self.calls = []

    async def call(self, method, params, **kw):
        self.calls.append((method, params, kw))
        return {
            "ok": True,
            "content": [{"type": "text", "text": "receipt"}],
            "details": {"raw": 42},
            "delivery_state": "delivered_unverified",
        }


@pytest.mark.asyncio
async def test_context_denies_child_and_missing_write_authority(monkeypatch):
    ctx = SimpleNamespace(
        run_id="run", session_id="session", parent_run_id="parent", allow_cu_write=True
    )
    fake_module = SimpleNamespace(current_tool_context=lambda: ctx)
    monkeypatch.setitem(sys.modules, "gcode.runtime.context", fake_module)
    t = FakeTransport()
    tool = DesktopTool(t, "ax_action", {"type": "object"}, "action")
    assert (await tool.execute(DesktopParams())).is_error and not t.calls
    ctx.parent_run_id = None
    ctx.allow_cu_write = False
    assert (await tool.execute(DesktopParams())).is_error and not t.calls


@pytest.mark.asyncio
async def test_reads_preserve_receipt_and_context(monkeypatch):
    ctx = SimpleNamespace(
        run_id="run", session_id="session", parent_run_id="parent", allow_cu_write=False
    )
    monkeypatch.setitem(
        sys.modules,
        "gcode.runtime.context",
        SimpleNamespace(current_tool_context=lambda: ctx),
    )
    t = FakeTransport()
    tool = DesktopTool(t, "ax_query", {"type": "object"}, "query")
    result = await tool.execute(DesktopParams(role="button"))
    assert result.output == "receipt"
    assert (
        result.details["details"]["raw"] == 42
        and result.content[0]["text"] == "receipt"
    )
    assert t.calls[0][2]["run_id"] == "run"


@pytest.mark.asyncio
async def test_large_receipt_retained_in_context_artifact_dir(monkeypatch, tmp_path):
    import hashlib

    raw = b'{"content":[{"type":"text","text":"original receipt"}]}'
    digest = hashlib.sha256(raw).hexdigest()
    state = tmp_path / "transport"
    (state / "artifacts").mkdir(parents=True)
    source = state / "artifacts" / f"{digest}.json"
    source.write_bytes(raw)
    ctx = SimpleNamespace(
        run_id="run",
        session_id="session",
        parent_run_id=None,
        allow_cu_write=True,
        artifact_dir=tmp_path / "artifacts",
    )
    monkeypatch.setitem(
        sys.modules,
        "gcode.runtime.context",
        SimpleNamespace(current_tool_context=lambda: ctx),
    )

    class Large:
        state_dir = state

        async def call(self, *args, **kwargs):
            return {
                "ok": True,
                "artifact_reference": {"path": str(source), "sha256": digest},
                "delivery_state": "delivered_unverified",
            }

    result = await DesktopTool(
        Large(), "ax_action", {"type": "object"}, "action"
    ).execute(DesktopParams())
    assert (ctx.artifact_dir / f"cu-{digest}.json").read_bytes() == raw
    assert result.details["artifact_reference"]["sha256"] == digest
    assert len(result.output) < 300 and result.content[1]["type"] == "artifact"


def test_capability_registration_is_allowlisted_and_writes_opt_in():
    from gcode.tools.desktop import desktop_tools_from_hello

    caps = [
        {"name": name, "input_schema": {"type": "object"}, "description": name}
        for name in ("ax_observe", "ax_action", "untrusted")
    ]
    t = FakeTransport()
    assert [
        v.name for v in desktop_tools_from_hello(t, {"ok": True, "capabilities": caps})
    ] == ["ax_observe"]
    assert [
        v.name
        for v in desktop_tools_from_hello(
            t, {"ok": True, "capabilities": caps}, allow_write=True
        )
    ] == ["ax_observe", "ax_action"]
    with pytest.raises(ValueError):
        desktop_tools_from_hello(t, {"ok": True, "capabilities": [caps[0], caps[0]]})

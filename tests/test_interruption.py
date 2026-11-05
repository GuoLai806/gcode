"""Interrupted-turn regressions. No external API calls in this test module."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import shlex
from pathlib import Path

import pytest
from pydantic import BaseModel

from gcode.agent import Agent, PermissionRequest, ToolResultEvent
from gcode.client import LLMClient
from gcode.conversation import (
    ConversationManager,
    Message,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from gcode.memory.session import (
    SessionManager,
    SessionRecord,
    records_to_messages,
    validate_message_chain,
)
from gcode.tools import ToolRegistry
from gcode.tools.base import StreamEnd, TextDelta, Tool, ToolCallComplete, ToolResult
from gcode.tools.bash import Bash, Params as BashParams


def assert_closed(conv):
    """Independently check exact adjacency, not just repair's return value."""
    for index, message in enumerate(conv.history):
        if message.tool_uses:
            assert index + 1 < len(conv.history)
            following = conv.history[index + 1]
            assert following.role == "user"
            expected = [tu.tool_use_id for tu in message.tool_uses]
            actual = [tr.tool_use_id for tr in following.tool_results]
            assert set(expected) == set(actual)
            assert len(actual) == len(set(actual)) == len(expected)
        if message.tool_results:
            assert index > 0 and conv.history[index - 1].tool_uses
    records = [rec for msg in conv.history for rec in SessionRecord.from_message(msg)]
    assert validate_message_chain(records) == len(records)


class ScriptClient(LLMClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = 0
        self.closed = 0

    async def stream(self, conversation, system="", tools=None):
        assert_closed(conversation)
        self.requests += 1
        events = self.responses.pop(0)
        try:
            if isinstance(events, Exception):
                raise events
            for event in events:
                yield event
        finally:
            self.closed += 1


class GatedParams(BaseModel):
    value: str


class GatedTool(Tool):
    name = "GatedTool"
    description = "Controlled test tool"
    params_model = GatedParams

    def __init__(self, concurrent=False):
        self.is_concurrency_safe = concurrent
        self.started = asyncio.Event()
        self.finished = []
        self.cancelled = asyncio.Event()

    async def execute(self, params):
        if params.value == "slow":
            self.started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise
        self.finished.append(params.value)
        return ToolResult(output="completed:" + params.value)


async def consume(agent, conv):
    stream = agent.run(conv)
    try:
        return [event async for event in stream]
    finally:
        await stream.aclose()


def make_agent(tmp_path, tool, responses):
    registry = ToolRegistry()
    registry.register(tool)
    client = ScriptClient(responses)
    return Agent(client, registry, "anthropic", work_dir=str(tmp_path)), client


def calls(*values):
    return [
        ToolCallComplete(f"t{i}", "GatedTool", {"value": value})
        for i, value in enumerate(values)
    ] + [StreamEnd("tool_use")]


def reconcile_fake_provider_usage(agent):
    # This deterministic in-process provider never sends an API request. Its
    # absent trailer has known zero additional usage, unlike a real outage.
    snapshot = agent.token_budget.snapshot()
    while snapshot["usage_unknown"]:
        snapshot = agent.token_budget.resolve_unknown(
            "scripted-provider-zero-usage-" + str(snapshot["revision"]),
            snapshot["revision"],
            0,
            0,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent", [False, True])
async def test_cancel_preserves_success_and_continues(tmp_path, concurrent):
    tool = GatedTool(concurrent)
    agent, client = make_agent(
        tmp_path,
        tool,
        [
            calls("fast", "slow", "queued"),
            [TextDelta("continued"), StreamEnd("end_turn")],
        ],
    )
    conv = ConversationManager()
    conv.add_user_message("first")
    task = asyncio.create_task(consume(agent, conv))
    await asyncio.wait_for(tool.started.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert_closed(conv)
    results = {tr.tool_use_id: tr for msg in conv.history for tr in msg.tool_results}
    assert results["t0"].content == "completed:fast"
    assert not results["t0"].is_error
    assert results["t1"].is_error and "outcome is unknown" in results["t1"].content
    assert results["t2"].is_error is (not concurrent)
    assert tool.cancelled.is_set()
    conv.add_user_message("continue, do not repeat tools")
    await consume(agent, conv)
    assert conv.history[-1].content == "continued"
    assert client.requests == client.closed == 2
    assert tool.finished == (["fast", "queued"] if concurrent else ["fast"])


@pytest.mark.asyncio
async def test_generator_close_at_result_event(tmp_path):
    tool = GatedTool()
    agent, _ = make_agent(tmp_path, tool, [calls("fast", "slow")])
    conv = ConversationManager()
    conv.add_user_message("first")
    stream = agent.run(conv)
    async for event in stream:
        if isinstance(event, ToolResultEvent):
            break
    await stream.aclose()
    assert_closed(conv)
    assert not tool.started.is_set()
    assert conv.history[-1].tool_results[0].content == "completed:fast"
    assert conv.history[-1].tool_results[1].is_error


@pytest.mark.asyncio
async def test_close_during_model_stream_does_not_execute_incomplete_batch(tmp_path):
    tool = GatedTool()
    agent, client = make_agent(
        tmp_path,
        tool,
        [calls("fast", "slow"), [TextDelta("continued"), StreamEnd("end_turn")]],
    )
    conv = ConversationManager()
    conv.add_user_message("first")
    stream = agent.run(conv)
    await anext(stream)  # Complete tool block received, but stream has not finished.
    await stream.aclose()
    assert client.closed == 1
    assert not tool.finished and not tool.started.is_set()
    assert_closed(conv)
    assert not agent.token_budget.snapshot()["usage_complete"]
    reconcile_fake_provider_usage(agent)
    conv.add_user_message("continue")
    await consume(agent, conv)
    assert conv.history[-1].content == "continued"


@pytest.mark.asyncio
async def test_noninteractive_cancel_closes_chain(tmp_path):
    tool = GatedTool()
    agent, _ = make_agent(
        tmp_path,
        tool,
        [calls("fast", "slow"), [TextDelta("continued"), StreamEnd("end_turn")]],
    )
    conv = ConversationManager()
    task = asyncio.create_task(agent.run_to_completion("first", conv))
    await asyncio.wait_for(tool.started.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert_closed(conv)
    assert await agent.run_to_completion("continue", conv) == "continued"


@pytest.mark.asyncio
async def test_unknown_tool_termination_is_closed(tmp_path):
    agent, _ = make_agent(
        tmp_path,
        GatedTool(),
        [
            [ToolCallComplete(str(i), "missing", {}) for i in range(3)]
            + [StreamEnd("tool_use")]
        ],
    )
    conv = ConversationManager()
    conv.add_user_message("first")
    await consume(agent, conv)
    assert_closed(conv)
    assert all(tr.is_error for tr in conv.history[-1].tool_results)


def test_repair_old_history_preserves_text_thinking_and_partial_results():
    conv = ConversationManager(
        history=[
            Message(
                "assistant",
                "checking",
                tool_uses=[ToolUseBlock("a", "X", {}), ToolUseBlock("b", "X", {})],
                thinking_blocks=[
                    ThinkingBlock("original thinking", "original signature")
                ],
            ),
            Message(
                "user",
                "attached text",
                tool_results=[ToolResultBlock("a", "real output")],
            ),
            Message("user", "new user request"),
            Message("user", "", tool_results=[ToolResultBlock("b", "late output")]),
        ]
    )
    conv.record_usage_anchor(123)
    assert conv.repair_tool_chain() == 2
    assert_closed(conv)
    assert conv.history[0].thinking_blocks[0].signature == "original signature"
    assert conv.history[1].tool_results[0].content == "real output"
    assert conv.history[1].content == "attached text"
    assert conv.history[2].content == "new user request"
    assert "late output" in conv.history[3].content
    assert conv.baseline_tokens == 0
    before = copy.deepcopy(conv.history)
    assert conv.repair_tool_chain() == 0
    assert conv.history == before


def test_duplicate_result_kept_as_text():
    conv = ConversationManager(
        history=[
            Message("assistant", "", tool_uses=[ToolUseBlock("a", "X", {})]),
            Message(
                "user",
                "",
                tool_results=[
                    ToolResultBlock("a", "first"),
                    ToolResultBlock("a", "second"),
                ],
            ),
        ]
    )
    assert conv.repair_tool_chain() == 1
    assert_closed(conv)
    assert "second" in conv.history[1].content


def test_resume_repair_is_append_only_and_stable(tmp_path):
    manager = SessionManager(str(tmp_path))
    session = manager.create()
    session.append(Message("user", "first"))
    session.append(
        Message(
            "assistant",
            "",
            tool_uses=[ToolUseBlock("a", "X", {}), ToolUseBlock("b", "X", {})],
            thinking_blocks=[ThinkingBlock("thinking", "signature")],
        )
    )
    session.append(Message("user", "", tool_results=[ToolResultBlock("a", "real")]))
    session.append(Message("user", "last request, must survive"))
    sid = session.session_id
    session.close()
    path = tmp_path / ".gcode" / "sessions" / (sid + ".jsonl")
    original = path.read_bytes()
    resumed = manager.resume(sid)
    assert resumed is not None
    conv = ConversationManager(history=resumed.messages)
    assert_closed(conv)
    assert conv.history[-1].content == "last request, must survive"
    assert conv.history[1].thinking_blocks[0].signature == "signature"
    assert conv.history[2].tool_results[0].content == "real"
    resumed.session.close()
    assert path.read_bytes().startswith(original)
    once = path.read_bytes()
    twice = manager.resume(sid)
    assert twice is not None
    assert twice.messages == resumed.messages
    twice.session.close()
    assert path.read_bytes() == once


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_name,builder",
    [
        ("AnthropicClient", "build_anthropic_messages"),
        ("OpenAIClient", "build_openai_input"),
        ("OpenAICompatClient", "build_chat_completion_messages"),
    ],
)
async def test_each_client_repairs_before_serialization(
    monkeypatch, client_name, builder
):
    import gcode.client as clients
    from gcode.config import ProviderConfig

    client = getattr(clients, client_name)(
        ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")
    )
    conv = ConversationManager(
        history=[Message("assistant", "", tool_uses=[ToolUseBlock("a", "X", {})])]
    )

    class StopBeforeNetwork(Exception):
        pass

    def checked(messages):
        assert_closed(ConversationManager(history=messages))
        raise StopBeforeNetwork()

    monkeypatch.setattr(clients, builder, checked)
    with pytest.raises(StopBeforeNetwork):
        await anext(client.stream(conv))
    await client._client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="Real POSIX process-group acceptance")
@pytest.mark.parametrize("mode", ["cancel", "timeout", "double_cancel"])
async def test_bash_cleans_real_child_tree(tmp_path, mode):
    # A child ignores TERM to exercise escalation; all side effects stay in tmp_path.
    marker = tmp_path / "child.pid"
    output = tmp_path / "must_not_exist"
    python = shlex.quote(os.sys.executable)
    source = (
        "import os,signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(4); "
        f"pathlib.Path({str(output)!r}).write_text('leaked')"
    )
    task = asyncio.create_task(
        Bash().execute(
            BashParams(command=python + " -c " + shlex.quote(source), timeout=1)
        )
    )
    async with asyncio.timeout(3):
        while not marker.exists():
            await asyncio.sleep(0.01)
    if mode != "timeout":
        task.cancel()
        if mode == "double_cancel":
            await asyncio.sleep(0.1)
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.is_error and "timed out" in result.output
    pid = int(marker.read_text())
    async with asyncio.timeout(3):
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
    assert not output.exists()


@pytest.mark.asyncio
async def test_textual_enter_interrupt_and_disk_resume(tmp_path, monkeypatch):
    from gcode.app import ChatInput, GCodeApp
    from gcode.config import ProviderConfig
    import gcode.app as app_module

    tool = GatedTool()
    client = ScriptClient(
        [calls("fast", "slow"), [TextDelta("continued"), StreamEnd("end_turn")]]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "create_client", lambda provider: client)
    app = GCodeApp(
        [ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")]
    )
    async with app.run_test(size=(100, 35)) as pilot:
        app.registry.register(tool)
        widget = app.query_one("#chat-input", ChatInput)
        widget.insert("first")
        await pilot.press("enter")
        await asyncio.wait_for(tool.started.wait(), 5)
        widget.insert("continue")
        await pilot.press("enter")
        async with asyncio.timeout(5):
            while app._streaming or not any(
                m.content == "continued" for m in app.conversation.history
            ):
                await pilot.pause(0.02)
        assert_closed(app.conversation)
        sid = app.session.session_id
        app.session.close()
        resumed = app.session_manager.resume(sid)
        assert resumed is not None
        assert_closed(ConversationManager(history=resumed.messages))
        results = [tr for m in resumed.messages for tr in m.tool_results]
        assert results[0].content == "completed:fast"
        assert results[1].is_error
        assert resumed.messages[-1].content == "continued"
        assert sum(m.content == "first" for m in resumed.messages) == 1
        assert sum(m.content == "continue" for m in resumed.messages) == 1
        assert sum(m.content == "continued" for m in resumed.messages) == 1
        resumed.session.close()


@pytest.mark.asyncio
async def test_completed_answers_do_not_make_background_summary_calls(
    tmp_path, monkeypatch
):
    from gcode.app import ChatInput, GCodeApp
    from gcode.config import ProviderConfig
    import gcode.app as app_module

    client = ScriptClient(
        [
            [
                TextDelta(f"answer {i}"),
                StreamEnd("end_turn", input_tokens=10, output_tokens=5),
            ]
            for i in range(3)
        ]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "create_client", lambda provider: client)
    app = GCodeApp(
        [ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")]
    )
    async with app.run_test(size=(100, 35)) as pilot:
        app.agent.memory_manager = None  # unrelated long-term memory not under test
        widget = app.query_one("#chat-input", ChatInput)
        for i in range(3):
            widget.insert(f"question {i}")
            await pilot.press("enter")
            async with asyncio.timeout(5):
                while app._streaming or not any(
                    m.content == f"answer {i}" for m in app.conversation.history
                ):
                    await pilot.pause(0.02)
            await pilot.pause(0.1)  # give unintended background callbacks time to run
            assert client.requests == i + 1
        assert app.session.meta.summary == ""
        from gcode.memory.session import SessionMeta

        persisted = SessionMeta.load(
            tmp_path / ".gcode" / "sessions" / f"{app.session.session_id}.meta"
        )
        assert persisted.total_tokens == 45
        assert_closed(app.conversation)
        app.session.close()


def test_session_synopsis_implementation_removed():
    import gcode.memory as memory
    import gcode.memory.session as session
    from gcode.app import GCodeApp

    assert not hasattr(memory, "generate_session_summary")
    assert not hasattr(session, "generate_session_summary")
    assert not hasattr(session, "SESSION_SUMMARY_PROMPT")
    assert not hasattr(GCodeApp, "_update_session_summary")


@pytest.mark.asyncio
async def test_escape_during_permission_restores_input(tmp_path, monkeypatch):
    from gcode.app import ChatInput, GCodeApp
    from gcode.config import ProviderConfig
    from gcode.permission_dialog import InlinePermissionWidget
    from gcode.agent import PermissionResponse
    import gcode.app as app_module

    tool = GatedTool()
    tool.category = "command"
    client = ScriptClient(
        [calls("fast"), [TextDelta("continued"), StreamEnd("end_turn")]]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "create_client", lambda provider: client)
    app = GCodeApp(
        [ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")]
    )
    async with app.run_test(size=(100, 40)) as pilot:
        app.registry.register(tool)
        app.agent.memory_manager = None
        widget = app.query_one("#chat-input", ChatInput)
        widget.insert("first")
        await pilot.press("enter")
        async with asyncio.timeout(5):
            while not getattr(app, "_pending_perm_request", None):
                await pilot.pause(0.02)
        pending = app._pending_perm_request
        await pilot.press("escape")
        async with asyncio.timeout(5):
            while app._streaming:
                await pilot.pause(0.02)
        await pilot.pause(0.05)
        assert pending.future.cancelled()
        assert not widget.disabled
        assert not app.query("#perm-inline")
        assert not tool.finished  # cancellation is never approval
        assert_closed(app.conversation)
        # A late UI response must not set_result on a cancelled Future.
        app._pending_perm_request = pending
        app.on_inline_permission_widget_responded(
            InlinePermissionWidget.Responded(PermissionResponse.ALLOW)
        )
        widget.insert("continue")
        await pilot.press("enter")
        async with asyncio.timeout(5):
            while app._streaming or not any(
                m.content == "continued" for m in app.conversation.history
            ):
                await pilot.pause(0.02)
        assert_closed(app.conversation)
        app.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "unexpected"])
async def test_failed_turn_can_continue_without_repeating_completed_tool(
    tmp_path, monkeypatch, failure
):
    from gcode.app import ChatInput, GCodeApp
    from gcode.config import ProviderConfig
    from gcode.client import NetworkError
    import gcode.app as app_module

    error = (
        NetworkError("test disconnected")
        if failure == "network"
        else RuntimeError("test failure")
    )
    client = ScriptClient(
        [calls("fast"), error, [TextDelta("continued"), StreamEnd("end_turn")]]
    )
    tool = GatedTool()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "create_client", lambda provider: client)
    app = GCodeApp(
        [ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")]
    )
    errors = []
    original_show_error = app._show_error

    def record_error(message):
        errors.append(message)
        original_show_error(message)

    app._show_error = record_error
    async with app.run_test(size=(100, 40)) as pilot:
        app.registry.register(tool)
        app.agent.memory_manager = None
        widget = app.query_one("#chat-input", ChatInput)
        widget.insert("first")
        await pilot.press("enter")
        async with asyncio.timeout(5):
            while app._streaming or not errors:
                await pilot.pause(0.02)
        assert_closed(app.conversation)
        assert not app.agent.token_budget.snapshot()["usage_complete"]
        reconcile_fake_provider_usage(app.agent)
        widget.insert("continue")
        await pilot.press("enter")
        async with asyncio.timeout(5):
            while app._streaming or not any(
                m.content == "continued" for m in app.conversation.history
            ):
                await pilot.pause(0.02)
        assert tool.finished == ["fast"]
        assert client.requests == 3
        assert_closed(app.conversation)
        app.session.close()


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != "posix", reason="Real POSIX subprocess acceptance")
async def test_cancel_during_subprocess_creation_is_reaped(monkeypatch):
    import gcode.tools.bash as bash_module

    original_create = asyncio.create_subprocess_shell
    spawned = asyncio.Event()
    release = asyncio.Event()
    processes = []

    async def delayed_create(*args, **kwargs):
        proc = await original_create(*args, **kwargs)
        processes.append(proc)
        spawned.set()
        await release.wait()
        return proc

    monkeypatch.setattr(bash_module.asyncio, "create_subprocess_shell", delayed_create)
    task = asyncio.create_task(Bash().execute(BashParams(command="sleep 10")))
    await asyncio.wait_for(spawned.wait(), 3)
    task.cancel()
    await asyncio.sleep(0.05)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert processes[0].returncode is not None


@pytest.mark.asyncio
async def test_app_shutdown_cancels_and_persists_pending_tools(tmp_path, monkeypatch):
    from gcode.app import ChatInput, GCodeApp
    from gcode.config import ProviderConfig
    import gcode.app as app_module

    client = ScriptClient([calls("fast", "slow", "queued")])
    tool = GatedTool()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "create_client", lambda provider: client)
    app = GCodeApp(
        [ProviderConfig("test", "anthropic", "https://example.invalid", "test", "test")]
    )
    async with app.run_test(size=(100, 40)) as pilot:
        app.registry.register(tool)
        app.agent.memory_manager = None
        widget = app.query_one("#chat-input", ChatInput)
        widget.insert("first")
        await pilot.press("enter")
        await asyncio.wait_for(tool.started.wait(), 5)
        sid = app.session.session_id
    assert tool.cancelled.is_set()
    assert not app._turn_tasks
    assert_closed(app.conversation)
    resumed = app.session_manager.resume(sid)
    assert resumed is not None
    assert_closed(ConversationManager(history=resumed.messages))
    results = [tr for m in resumed.messages for tr in m.tool_results]
    assert results[0].content == "completed:fast"
    assert all(tr.is_error for tr in results[1:])
    resumed.session.close()

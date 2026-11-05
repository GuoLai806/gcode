from __future__ import annotations

import asyncio
import os

import pytest
from pydantic import BaseModel

from gcode.agent import Agent
from gcode.client import LLMClient
from gcode.conversation import ConversationManager, Message
from gcode.memory.session import SessionManager
from gcode.tools import ToolRegistry, create_default_registry
from gcode.tools.base import Tool, ToolResult, ToolCallComplete, StreamEnd, TextDelta
from gcode.tools.write_file import WriteFile, Params as WriteParams


class Empty(BaseModel):
    pass


class Script(LLMClient):
    def __init__(self, events):
        self.events = iter(events)

    async def stream(self, conversation, system="", tools=None):
        for event in next(self.events):
            yield event


def new_agent(path, client=None, registry=None):
    return Agent(
        client or Script([]),
        registry or create_default_registry(),
        "anthropic",
        str(path),
    )


def test_acked_notification_survives_newer_jsonl_and_repeated_resume(tmp_path):
    manager = SessionManager(str(tmp_path))
    session = manager.create()
    agent = new_agent(tmp_path)
    agent.session_id = session.session_id
    conversation = ConversationManager()
    agent.persist_notification(
        conversation, "child result: preserve this durable result"
    )
    session.append(Message("user", "newer user input", origin="user"))
    runtime = agent.session_dir / "runtime-checkpoint.json"
    # Exercise the precise race: the UI JSONL is newer but never included the
    # notification in its incremental persistence cursor.
    os.utime(
        manager._sessions_dir / (session.session_id + ".jsonl"),
        ns=(
            runtime.stat().st_mtime_ns + 1_000_000,
            runtime.stat().st_mtime_ns + 1_000_000,
        ),
    )
    session.close()
    for _ in range(2):
        resumed = manager.resume(session.session_id)
        assert resumed is not None
        texts = [message.content for message in resumed.messages]
        assert any("newer user input" in text for text in texts)
        assert sum("preserve this durable result" in text for text in texts) == 1
        resumed.session.close()


@pytest.mark.asyncio
async def test_unknown_write_cannot_replay_or_report_completed_without_checker(
    tmp_path,
):
    class EffectThenFail(Tool):
        name, description, params_model, category = (
            "EffectThenFail",
            "fixture",
            Empty,
            "write",
        )

        async def execute(self, params):
            with (tmp_path / "effects").open("a") as stream:
                stream.write("effect\n")
            raise RuntimeError("lost receipt after side effect")

    registry = ToolRegistry()
    registry.register(EffectThenFail())
    call = ToolCallComplete("same-call", "EffectThenFail", {})
    agent = new_agent(
        tmp_path,
        Script(
            [
                [call, StreamEnd("tool_use")],
                [call, StreamEnd("tool_use")],
                [TextDelta("done"), StreamEnd("end_turn")],
            ]
        ),
        registry,
    )
    result = await agent.run_to_completion("perform fixture")
    assert (tmp_path / "effects").read_text().splitlines() == ["effect"]
    assert agent.last_stop_reason == "delivery_unknown"
    assert "待核查" in result
    assert agent.recovery_writes_stopped


@pytest.mark.asyncio
async def test_production_session_resume_keeps_fence_across_second_save(tmp_path):
    manager = SessionManager(str(tmp_path))
    session = manager.create()
    agent = new_agent(tmp_path)
    agent.session_id = session.session_id
    agent._pending_calls = {"unknown": "write"}
    agent.recovery_writes_stopped = True
    agent._save_checkpoint(ConversationManager())
    session.close()
    for _ in range(2):
        resumed = manager.resume(session.session_id)
        assert resumed and resumed.recovery_writes_stopped
        restored = new_agent(tmp_path)
        restored.session_id = session.session_id
        restored._pending_calls = resumed.pending_calls
        restored._unknown_call_ids = set(resumed.unknown_call_ids)
        restored.recovery_writes_stopped = resumed.recovery_writes_stopped
        result = await restored._execute_tool_noninteractive(
            ToolCallComplete(
                "new", "WriteFile", {"file_path": "blocked", "content": "x"}
            )
        )
        assert result.is_error and not (tmp_path / "blocked").exists()
        restored._save_checkpoint(ConversationManager(history=resumed.messages))
        resumed.session.close()

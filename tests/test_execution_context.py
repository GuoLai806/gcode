"""Behavioral regression contracts for scoped I/O, permissions and run recovery."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from gcode.agent import Agent
from gcode.client import LLMClient
from gcode.conversation import (
    ConversationManager,
    Message,
    ToolResultBlock,
    ToolUseBlock,
)
from gcode.hooks.executors import execute_command
from gcode.hooks.models import Action, HookContext
from gcode.permissions import (
    DangerousCommandDetector,
    PathSandbox,
    PermissionChecker,
    PermissionMode,
    RuleEngine,
)
from gcode.runtime.context import ToolExecutionContext
from gcode.runtime.journal import load_checkpoint, save_checkpoint
from gcode.tools import create_default_registry
from gcode.tools.base import StreamEnd, TextDelta, ToolCallComplete
from gcode.tools.bash import Bash, Params as BashParams
from gcode.tools.read_file import ReadFile, Params as ReadParams
from gcode.tools.write_file import WriteFile, Params as WriteParams
from gcode.tools.grep import Grep
from gcode.tools.glob import Glob


class ScriptedClient(LLMClient):
    def __init__(self, script):
        self.script = iter(script)

    async def stream(self, conversation, system="", tools=None):
        for event in next(self.script):
            await asyncio.sleep(0)
            yield event


def context(path, name="run"):
    return ToolExecutionContext(name, name, path, path / "artifacts")


def checker(path, mode=PermissionMode.BYPASS):
    return PermissionChecker(
        DangerousCommandDetector(), PathSandbox(str(path)), RuleEngine(), mode
    )


@pytest.mark.asyncio
async def test_concurrent_read_write_and_shell_use_each_task_directory(tmp_path):
    before = Path.cwd()
    dirs = [tmp_path / "one", tmp_path / "two"]
    for directory in dirs:
        directory.mkdir()
    write, read, shell = WriteFile(), ReadFile(), Bash()

    async def run(directory):
        ctx = context(directory, directory.name)
        assert not (
            await write.invoke(
                WriteParams(file_path="same.txt", content=directory.name), ctx
            )
        ).is_error
        text = await read.invoke(ReadParams(file_path="same.txt"), ctx)
        pwd = await shell.invoke(BashParams(command="pwd"), ctx)
        return text.output, pwd.output

    results = await asyncio.gather(*(run(directory) for directory in dirs))
    assert "one" in results[0][0] and str(dirs[0]) in results[0][1]
    assert "two" in results[1][0] and str(dirs[1]) in results[1][1]
    assert Path.cwd() == before


@pytest.mark.asyncio
async def test_headless_agent_uses_same_loop_and_relative_path(tmp_path):
    (tmp_path / "target.txt").write_text("child value")
    client = ScriptedClient(
        [
            [
                ToolCallComplete("r", "ReadFile", {"file_path": "target.txt"}),
                StreamEnd("tool_use"),
            ],
            [TextDelta("verified child value"), StreamEnd("end_turn")],
        ]
    )
    agent = Agent(client, create_default_registry(), "anthropic", str(tmp_path))
    conv = ConversationManager()
    assert await agent.run_to_completion("read target", conv) == "verified child value"
    results = [r for m in conv.history for r in m.tool_results]
    assert "child value" in results[0].content
    assert agent.last_stop_reason == "completed"
    assert (agent.session_dir / "runtime-checkpoint.json").is_file()


@pytest.mark.asyncio
async def test_iteration_limit_does_not_return_old_fork_answer(tmp_path):
    conv = ConversationManager(history=[Message("assistant", "old parent's answer")])
    agent = Agent(
        ScriptedClient(
            [
                [
                    ToolCallComplete("r", "ReadFile", {"file_path": "missing"}),
                    StreamEnd("tool_use"),
                ]
            ]
        ),
        create_default_registry(),
        "anthropic",
        str(tmp_path),
        max_iterations=1,
    )
    result = await agent.run_to_completion("new task", conv)
    assert agent.last_stop_reason == "limit_reached"
    assert result != "old parent's answer"


@pytest.mark.asyncio
async def test_parent_approval_ceiling_cannot_be_overridden_by_child(tmp_path):
    child = Agent(
        ScriptedClient([]),
        create_default_registry(),
        "anthropic",
        str(tmp_path),
        permission_checker=checker(tmp_path),
    )
    child.permission_ceilings = [checker(tmp_path, PermissionMode.DEFAULT)]
    result = await child._execute_tool_noninteractive(
        ToolCallComplete(
            "w", "WriteFile", {"file_path": "forbidden.txt", "content": "x"}
        )
    )
    assert result.is_error
    assert not (tmp_path / "forbidden.txt").exists()


@pytest.mark.parametrize("tool", [Grep(), Glob()])
def test_search_checks_actual_path_not_pattern(tmp_path, tool):
    project = tmp_path / "project"
    project.mkdir()
    boundary = checker(project)
    # /dev is outside both the project and the allowed OS temporary directory.
    decision = boundary.check(tool, {"pattern": "innocent", "path": "/dev"})
    assert decision.effect == "deny"


@pytest.mark.asyncio
async def test_parallel_reads_do_not_bypass_parent_path_check(tmp_path):
    agent = Agent(
        ScriptedClient([]),
        create_default_registry(),
        "anthropic",
        str(tmp_path),
        permission_checker=checker(tmp_path),
    )
    result = await agent._execute_single_tool_direct(
        ToolCallComplete("r", "ReadFile", {"file_path": "/etc/hosts"})
    )
    assert result.result.is_error
    assert "Permission denied" in result.result.output


@pytest.mark.asyncio
async def test_hook_command_uses_declared_worktree(tmp_path):
    result = await execute_command(
        Action("command", command="pwd"), HookContext(cwd=str(tmp_path))
    )
    assert result.success
    assert Path(result.output).resolve() == tmp_path.resolve()


def test_artifacts_are_session_scoped_and_not_silently_truncated(tmp_path):
    agent = Agent(
        ScriptedClient([]), create_default_registry(), "anthropic", str(tmp_path)
    )
    sibling = Agent(
        ScriptedClient([]), create_default_registry(), "anthropic", str(tmp_path)
    )
    assert agent.session_dir != sibling.session_dir
    text = "完整证据" * 4000
    projected = agent._maybe_persist_or_truncate("result", text)
    assert "persisted-output" in projected
    assert (agent.session_dir / "result.txt").read_text() == text


def test_checkpoint_retains_structured_tool_receipt(tmp_path):
    receipt = {"delivery_state": "delivery_unknown", "scope": {"window": "test"}}
    conv = ConversationManager(
        history=[
            Message("assistant", "", tool_uses=[ToolUseBlock("call", "ax_action", {})]),
            Message(
                "user",
                "",
                tool_results=[
                    ToolResultBlock("call", "outcome unknown", True, receipt)
                ],
            ),
        ]
    )
    save_checkpoint(tmp_path / "checkpoint.json", conv, pending_calls={"call": "write"})
    restored, state = load_checkpoint(tmp_path / "checkpoint.json")
    assert restored.history[-1].tool_results[0].details == receipt
    assert state["pending_calls"] == {"call": "write"}


def test_restore_unknown_write_stops_new_mutations(tmp_path):
    agent = Agent(
        ScriptedClient([]),
        create_default_registry(),
        "anthropic",
        str(tmp_path),
        permission_checker=checker(tmp_path),
    )
    agent._pending_calls = {"old": "write"}
    agent._save_checkpoint(ConversationManager())
    agent.restore_checkpoint()
    decision = agent._permission_decision(
        WriteFile(), {"file_path": str(tmp_path / "x")}
    )
    assert decision.effect == "deny"


def test_raw_content_blocks_cannot_bypass_model_projection_budget():
    from gcode.serialization import (
        build_anthropic_messages,
        build_openai_input,
        build_chat_completion_messages,
    )

    block = ToolResultBlock(
        "c",
        "<persisted-output>bounded pointer</persisted-output>",
        details={"delivery_state": "delivery_unknown"},
        content_blocks=[{"type": "text", "text": "secret raw" * 10000}],
    )
    message = Message("user", "", tool_results=[block])
    for renderer in [
        build_anthropic_messages,
        build_openai_input,
        build_chat_completion_messages,
    ]:
        output = json.dumps(renderer([message]))
        assert "secret raw" not in output
        assert "delivery_unknown" in output
        assert len(output) < 1000


def test_session_and_team_roundtrip_preserve_receipts(tmp_path):
    from gcode.memory.session import SessionRecord, records_to_messages
    from gcode.teams.transcript import (
        _serialize_conversation,
        _deserialize_conversation,
    )

    detail = {"delivery_state": "not_dispatched"}
    conv = ConversationManager(
        history=[
            Message(
                "user",
                "",
                tool_results=[
                    ToolResultBlock(
                        "c",
                        "output",
                        details=detail,
                        content_blocks=[{"type": "text", "text": "output"}],
                    )
                ],
            )
        ]
    )
    records = [
        SessionRecord.from_jsonl(record.to_jsonl())
        for record in SessionRecord.from_message(conv.history[0])
    ]
    assert records_to_messages(records)[0].tool_results[0].details == detail
    restored = _deserialize_conversation(_serialize_conversation(conv))
    assert restored.history[0].tool_results[0].details == detail


@pytest.mark.asyncio
async def test_search_never_reads_symlink_outside_base(tmp_path):
    from gcode.tools.grep import Params as GrepParams
    from gcode.tools.glob import Params as GlobParams

    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("sensitive needle")
    (base / "link.txt").symlink_to(outside)
    ctx = context(base)
    result = await Grep().invoke(GrepParams(pattern="needle"), ctx)
    assert "sensitive" not in result.output
    result = await Glob().invoke(GlobParams(pattern="**/*"), ctx)
    assert "link.txt" not in result.output
    assert (await Glob().invoke(GlobParams(pattern="../*"), ctx)).is_error


def test_plan_exception_requires_exact_current_plan_path(tmp_path):
    mode = checker(tmp_path, PermissionMode.PLAN)
    plan = tmp_path / ".gcode" / "plans" / "plan.md"
    mode.plan_file_path = str(plan)
    assert (
        mode.check(WriteFile(), {"file_path": str(plan), "content": "plan"}).effect
        == "allow"
    )
    assert (
        mode.check(
            WriteFile(), {"file_path": "/etc/.gcode/plans/plan.md", "content": "bad"}
        ).effect
        == "deny"
    )
    assert (
        mode.check(
            WriteFile(),
            {"file_path": str(tmp_path / "other" / "plan.md"), "content": "bad"},
        ).effect
        == "deny"
    )

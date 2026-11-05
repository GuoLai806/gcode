from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from gcode.context.manager import CompactEvent, auto_compact
from gcode.conversation import (
    ConversationManager,
    Message,
    ToolResultBlock,
    ToolUseBlock,
)
from gcode.tools.base import StreamEnd, TextDelta


def long_conversation():
    return ConversationManager(
        history=[
            Message(
                "user" if i % 2 == 0 else "assistant",
                f"constraint {i}: " + "内容" * (100 if i % 2 == 0 else 5000),
            )
            for i in range(16)
        ]
    )


class SummaryClient:
    def __init__(self, text, reason):
        self.text, self.reason = text, reason

    async def stream(self, conversation, system="", tools=None):
        yield TextDelta(self.text)
        if self.reason is not None:
            yield StreamEnd(self.reason)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,reason",
    [
        ("", "end_turn"),
        ("partial", "max_tokens"),
        ("partial", "length"),
        ("partial", None),
        ("I cannot provide a summary for this content.", "end_turn"),
        ("</summary>wrong order<summary>", "end_turn"),
        ("<summary>All good.</summary>", "end_turn"),
    ],
)
async def test_incomplete_summary_never_replaces_history(tmp_path, text, reason):
    conv = long_conversation()
    before = list(conv.history)
    result = await auto_compact(
        conv, SummaryClient(text, reason), 50000, tmp_path, manual=True
    )
    assert isinstance(result, str)
    assert conv.history == before
    assert not (tmp_path / "compact-checkpoints.jsonl").exists()


@pytest.mark.asyncio
async def test_literal_constraint_survives_three_compactions_and_disk_roundtrip(
    tmp_path,
):
    from gcode.memory.session import make_compact_boundary, records_to_messages

    conv = long_conversation()
    literal = "不要删除原始数据；只允许创建新版本。"
    conv.history.insert(0, Message("user", literal, origin="user"))
    for _ in range(3):
        result = await auto_compact(
            conv,
            SummaryClient(
                "<summary>All good.\n1. 主要请求和意图：测试任务\n2. 关键技术概念：无\n3. 文件和代码段：无\n4. 错误和修复：无\n5. 问题解决过程：无\n6. 所有用户消息：原文由运行时另行保存\n7. 待办任务：无\n8. 当前工作：测试压缩\n9. 可能的下一步：无</summary>",
                "end_turn",
            ),
            50000,
            tmp_path,
            manual=True,
        )
        assert isinstance(result, CompactEvent)
        record = make_compact_boundary(
            result.boundary.summary,
            result.boundary.keep,
            result.boundary.preserved_constraints,
            result.boundary.notification_ids,
        )
        restored = records_to_messages([record])
        assert any(literal in message.content for message in restored)
        assert literal in restored[0].preserved_constraints
        conv = ConversationManager(history=restored)
        conv.history += [
            Message("user", "later " + "后续" * 100),
            Message("assistant", "work " * 2000),
        ] * 8
    assert len((tmp_path / "compact-checkpoints.jsonl").read_text().splitlines()) == 3


@pytest.mark.asyncio
async def test_compact_retains_artifact_and_commits_before_projection(tmp_path):
    conv = long_conversation()
    artifact = tmp_path / "call.txt"
    artifact.write_text("original evidence")
    conv.history.extend(
        [
            Message("assistant", "", tool_uses=[ToolUseBlock("call", "ReadFile", {})]),
            Message(
                "user",
                "",
                tool_results=[
                    ToolResultBlock(
                        "call", f"<persisted-output>{artifact}</persisted-output>"
                    )
                ],
            ),
        ]
    )
    result = await auto_compact(
        conv,
        SummaryClient(
            "<summary>constraints retained\n1. 主要请求和意图：测试任务\n2. 关键技术概念：无\n3. 文件和代码段：无\n4. 错误和修复：无\n5. 问题解决过程：无\n6. 所有用户消息：原文由运行时另行保存\n7. 待办任务：无\n8. 当前工作：测试压缩\n9. 可能的下一步：无</summary>",
            "end_turn",
        ),
        50000,
        tmp_path,
        manual=True,
    )
    assert isinstance(result, CompactEvent)
    checkpoint = json.loads(
        (tmp_path / "compact-checkpoints.jsonl").read_text().splitlines()[-1]
    )
    assert checkpoint["summary"].startswith("constraints retained")
    assert checkpoint["source_history"] and any(
        "constraint 0" in m["content"] for m in checkpoint["source_history"]
    )
    assert conv.history[0].preserved_constraints == checkpoint["preserved_constraints"]
    assert artifact.read_text() == "original evidence"
    assert any(
        str(artifact) in tr.content for msg in conv.history for tr in msg.tool_results
    )


@pytest.mark.asyncio
async def test_checkpoint_write_failure_preserves_original_history(
    tmp_path, monkeypatch
):
    conv = long_conversation()
    before = list(conv.history)
    monkeypatch.setattr(
        "gcode.context.manager.os.fsync", MagicMock(side_effect=OSError("disk full"))
    )
    result = await auto_compact(
        conv,
        SummaryClient(
            "<summary>valid summary\n1. 主要请求和意图：测试任务\n2. 关键技术概念：无\n3. 文件和代码段：无\n4. 错误和修复：无\n5. 问题解决过程：无\n6. 所有用户消息：原文由运行时另行保存\n7. 待办任务：无\n8. 当前工作：测试压缩\n9. 可能的下一步：无</summary>",
            "end_turn",
        ),
        50000,
        tmp_path,
        manual=True,
    )
    assert isinstance(result, str)
    assert conv.history == before


@pytest.mark.asyncio
async def test_user_prose_over_cap_refuses_compaction_without_call_or_mutation(
    tmp_path,
):
    conv = long_conversation()
    conv.history.insert(
        0, Message("user", "请勿上传。" + "资料" * 16000, origin="user")
    )
    before = list(conv.history)

    class MustNotCall:
        async def stream(self, *args, **kwargs):
            raise AssertionError("provider must not be called over preservation cap")
            yield

    result = await auto_compact(conv, MustNotCall(), 50000, tmp_path, manual=True)
    assert isinstance(result, str) and "30000" in result
    assert conv.history == before
    assert not (tmp_path / "compact-checkpoints.jsonl").exists()

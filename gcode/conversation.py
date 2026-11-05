from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Iterator


@dataclass
class ToolUseBlock:
    tool_use_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str
    is_error: bool = False
    details: dict[str, Any] | None = None
    content_blocks: list[dict[str, Any]] | None = None


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str
    tool_uses: list[ToolUseBlock] = field(default_factory=list)
    tool_results: list[ToolResultBlock] = field(default_factory=list)
    thinking_blocks: list[ThinkingBlock] = field(default_factory=list)
    origin: str = ""
    preserved_constraints: list[str] = field(default_factory=list)
    notification_ids: list[str] = field(default_factory=list)


# 估算最后一次 API 用量锚点之后追加的消息 token 开销时使用的字符/token 比率。
# 与 context.manager 中的恢复状态启发值保持一致，全代码库统一使用同一比率。
_CHARS_PER_TOKEN = 3.5

INTERRUPTED_TOOL_RESULT = (
    "Tool execution interrupted before a result was recorded. Its outcome is unknown: "
    "it may have started or produced side effects. Check the current state before retrying; "
    "do not assume it succeeded or automatically repeat a non-idempotent action."
)


def _message_chars(m: Message) -> int:
    n = len(m.content)
    for tb in m.thinking_blocks:
        n += len(tb.thinking)
    for tu in m.tool_uses:
        n += len(tu.tool_name) + len(json.dumps(tu.arguments, ensure_ascii=False))
    for tr in m.tool_results:
        from gcode.serialization import tool_result_text

        n += len(tool_result_text(tr))
        n += 4800 * sum(
            block.get("type") == "image" for block in tr.content_blocks or []
        )
    return n


def estimate_tokens(messages: list[Message]) -> int:
    """基于字符数对一组消息做 token 估算。

    刻意做得粗略——它只覆盖那些尚未锚定到真实 API 用量数值的消息，这部分的
    精确度本就无关紧要。统计内容包括消息正文、thinking、工具调用参数以及
    工具结果内容。
    """
    total = sum(_message_chars(m) for m in messages)
    return int(total / _CHARS_PER_TOKEN)


@dataclass
class ConversationManager:
    history: list[Message] = field(default_factory=list)
    env_injected: bool = field(default=False, init=False)
    ltm_injected: bool = field(default=False, init=False)
    # API 报告的每轮真实 prompt 大小，保留用于向后兼容。
    # 现在与 baseline_tokens 一致（input + cache_read + cache_creation + output）。
    last_input_tokens: int = field(default=0, init=False)
    # 真实用量锚点。baseline_tokens 是上一轮 API 计费的完整 prompt+output 大小；
    # anchor_count 是记录该数值时的消息数量。两者配合让 current_tokens() 在
    # anchor_count 以内信任 API 数据，只对之后追加的消息做字符估算。
    # baseline_tokens == 0 表示"尚无锚点"（冷启动），此时退化为纯字符估算。
    baseline_tokens: int = field(default=0, init=False)
    anchor_count: int = field(default=0, init=False)

    def record_usage_anchor(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> None:
        """根据一次 API 响应钉下一个真实用量锚点。

        baseline = input + cache_read + cache_creation + output。各家服务商
        返回的 input_tokens 已经排除了命中缓存的 token，所以这三个 input 分量
        是相加关系，合起来才是真正的 prompt 大小；之所以再加上 output，是因为
        assistant 的回复此刻已成为历史的一部分。anchor_count 对齐到当前的消息
        数量，这样后续新追加的消息就成了唯一需要估算的部分。
        """
        self.baseline_tokens = (
            input_tokens + cache_read + cache_creation + output_tokens
        )
        self.anchor_count = len(self.history)
        # 保持旧字段同步，兼容仍在使用它的读取方。
        self.last_input_tokens = self.baseline_tokens

    def current_tokens(self) -> int:
        """对当前对话中的 token 数量做出最佳估算。

        有锚点时：baseline（真实用量）+ 仅对锚点之后追加的那些消息做字符估算。
        没有锚点时（冷启动，或刚经历一次压缩重置）：对整个历史做字符估算，
        这样在第一次 API 响应到来之前阈值检查依然能正常工作。
        """
        if self.baseline_tokens <= 0:
            return estimate_tokens(self.history)
        tail = self.history[self.anchor_count :]
        return self.baseline_tokens + estimate_tokens(tail)

    def add_user_message(self, content: str, origin: str = "user") -> None:
        self.history.append(Message(role="user", content=content, origin=origin))

    def add_assistant_message(
        self,
        content: str,
        tool_uses: list[ToolUseBlock] | None = None,
        thinking_blocks: list[ThinkingBlock] | None = None,
    ) -> None:
        self.history.append(
            Message(
                role="assistant",
                content=content,
                tool_uses=tool_uses or [],
                thinking_blocks=thinking_blocks or [],
            )
        )

    def add_system_reminder(self, content: str) -> None:
        self.history.append(
            Message(
                role="user",
                content=f"<system-reminder>\n{content}\n</system-reminder>",
                origin="reminder",
            )
        )

    def add_tool_results_message(self, tool_results: list[ToolResultBlock]) -> None:
        self.history.append(Message(role="user", content="", tool_results=tool_results))

    @contextmanager
    def tool_result_transaction(self) -> Iterator[list[ToolResultBlock]]:
        """Record completed results immediately; close missing pairs on every exit.

        This also runs on CancelledError, GeneratorExit and hook failures. The caller
        must close its async generator when abandoning iteration at a UI event.
        """
        results: list[ToolResultBlock] = []
        self.add_tool_results_message(results)
        try:
            yield results
        finally:
            self.repair_tool_chain()

    def repair_tool_chain(self, interruption: str = INTERRUPTED_TOOL_RESULT) -> int:
        """Make tool pairs adjacent, without replaying tools or inventing success.

        Completed results and all ordinary text/thinking are preserved. Orphan or
        duplicate results are retained as plain diagnostic text, not sent as invalid
        tool_result blocks. Repair is idempotent and shared by all entry points.
        """
        repaired: list[Message] = []
        changes = 0
        index = 0
        while index < len(self.history):
            message = self.history[index]
            index += 1
            if message.role == "assistant" and message.tool_uses:
                repaired.append(message)
                expected = {tu.tool_use_id for tu in message.tool_uses}
                result_message = None
                results: list[ToolResultBlock] = []
                texts: list[str] = []
                seen: set[str] = set()
                # Old JSONL stores one record per result; tolerate split messages.
                while index < len(self.history):
                    candidate = self.history[index]
                    if candidate.role != "user" or (
                        not candidate.tool_results
                        and not (result_message is None and not candidate.content)
                    ):
                        break
                    index += 1
                    if result_message is None:
                        result_message = candidate
                    else:
                        changes += 1
                    if candidate.content:
                        texts.append(candidate.content)
                    for result in candidate.tool_results:
                        if (
                            result.tool_use_id in expected
                            and result.tool_use_id not in seen
                        ):
                            results.append(result)
                            seen.add(result.tool_use_id)
                        else:
                            texts.append(
                                f"[Unpaired tool output {result.tool_use_id}]\n{result.content}"
                            )
                            changes += 1
                for tool_use in message.tool_uses:
                    if tool_use.tool_use_id not in seen:
                        results.append(
                            ToolResultBlock(tool_use.tool_use_id, interruption, True)
                        )
                        seen.add(tool_use.tool_use_id)
                        changes += 1
                if result_message is None:
                    result_message = Message(role="user", content="")
                result_message.tool_results = results
                result_message.content = "\n\n".join(texts)
                repaired.append(result_message)
            elif message.tool_results:
                message.content = (
                    "\n\n".join([message.content] if message.content else [])
                    + ("\n\n" if message.content else "")
                    + "\n\n".join(
                        f"[Unpaired tool output {tr.tool_use_id}]\n{tr.content}"
                        for tr in message.tool_results
                    )
                )
                message.tool_results = []
                repaired.append(message)
                changes += 1
            else:
                repaired.append(message)
        if changes:
            self.history = repaired
            # Inserting into an anchored prefix invalidates the old usage offset.
            self.baseline_tokens = self.anchor_count = self.last_input_tokens = 0
        return changes

    def inject_environment(self, context: str) -> None:
        if not self.env_injected:
            self.history.insert(
                0, Message(role="user", content=context, origin="environment")
            )
            self.env_injected = True

    def inject_long_term_memory(self, instructions: str, memories: str) -> None:
        if self.ltm_injected:
            return
        sections: list[str] = []
        if instructions:
            sections.append(
                "# GCodeMd\n"
                "Codebase and user instructions are shown below. "
                "Be sure to adhere to these instructions. "
                "IMPORTANT: These instructions OVERRIDE any default behavior "
                "and you MUST follow them exactly as written.\n\n" + instructions
            )
        if memories:
            sections.append("# autoMemory\n" + memories)
        if not sections:
            return
        from datetime import date

        sections.append(f"# currentDate\nToday's date is {date.today().isoformat()}.")
        body = "\n\n".join(sections)
        wrapped = (
            "<system-reminder>\n"
            "As you answer the user's questions, you can use the following context:\n"
            + body
            + "\n\n      IMPORTANT: this context may or may not be relevant to your tasks."
            " You should not respond to this context unless it is highly relevant to your task.\n"
            "</system-reminder>"
        )
        pos = 1 if self.env_injected else 0
        self.history.insert(
            pos, Message(role="user", content=wrapped, origin="instructions")
        )
        self.ltm_injected = True

    def replace_history(self, new_messages: list[Message]) -> None:
        self.history = new_messages
        self.env_injected = False
        self.ltm_injected = False
        # 旧的用量锚点描述的是压缩前的对话记录，这里清除它，
        # 使 current_tokens() 退化为字符估算，直到下次 API 响应
        # 基于摘要后的历史重新建立锚点。
        self.baseline_tokens = 0
        self.anchor_count = 0
        self.last_input_tokens = 0

    def get_messages(self) -> list[Message]:
        return list(self.history)

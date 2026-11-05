from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from pydantic import ValidationError

from gcode.client import LLMClient
from gcode.runtime.context import ToolExecutionContext
from gcode.runtime.budget import TokenBudget
from gcode.runtime.tool_ledger import ToolLedger
from gcode.context import (
    CompactBoundary,
    CompactCircuitBreaker,
    CompactEvent,
    ContentReplacementRecord,
    ContentReplacementState,
    RecoveryState,
    append_replacement_records,
    apply_tool_result_budget,
    auto_compact,
    create_replacement_state,
    ensure_session_dir,
    load_replacement_records,
    reconstruct_replacement_state,
)
from gcode.conversation import ConversationManager, ToolResultBlock, ToolUseBlock
from gcode.conversation import ThinkingBlock as ConvThinkingBlock
from gcode.memory.auto_memory import MemoryManager
from gcode.permissions import (
    Decision,
    PermissionChecker,
    PermissionMode,
)
from gcode.hooks import HookContext, HookEngine, ToolRejectedError
from gcode.hooks.engine import HookNotification
from gcode.prompts import (
    build_environment_context,
    build_plan_mode_reminder,
    build_system_prompt,
)
from gcode.tools import ToolRegistry
from gcode.tools.base import (
    MAX_OUTPUT_CHARS,
    StreamEnd,
    StreamEvent,
    TextDelta,
    ThinkingComplete,
    ThinkingDelta,
    ToolCallComplete,
    ToolCallDelta,
    ToolCallStart,
    ToolResult,
)

log = logging.getLogger(__name__)

MEMORY_EXTRACTION_INTERVAL = 5
MAX_TOKENS_CEILING = 64000
MAX_OUTPUT_TOKENS_RECOVERIES = 3


# ---------------------------------------------------------------------------
# AgentEvent 事件类型
# ---------------------------------------------------------------------------


@dataclass
class StreamText:
    text: str


@dataclass
class ThinkingText:
    text: str


@dataclass
class RetryEvent:
    reason: str
    wait: float = 0.0


@dataclass
class ToolUseEvent:
    tool_name: str
    tool_id: str
    arguments: dict[str, Any]


@dataclass
class ToolResultEvent:
    tool_id: str
    tool_name: str
    output: str
    is_error: bool
    elapsed: float


@dataclass
class TurnComplete:
    turn: int


@dataclass
class LoopComplete:
    total_turns: int
    stop_reason: str = "completed"


@dataclass
class UsageEvent:
    input_tokens: int
    output_tokens: int


@dataclass
class ErrorEvent:
    message: str


@dataclass
class CompactNotification:
    before_tokens: int
    message: str
    # 结构化 boundary（摘要 + 原文保留尾部），UI/session 层用它持久化 compact_boundary 记录。
    # 失败路径下为 None。
    boundary: "CompactBoundary | None" = None


@dataclass
class HookEvent:
    hook_id: str
    event: str
    output: str
    success: bool


class PermissionResponse(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ALLOW_ALWAYS = "allow_always"


@dataclass
class PermissionRequest:
    tool_name: str
    description: str
    future: asyncio.Future[PermissionResponse]


AgentEvent = (
    StreamText
    | ThinkingText
    | RetryEvent
    | ToolUseEvent
    | ToolResultEvent
    | TurnComplete
    | LoopComplete
    | UsageEvent
    | ErrorEvent
    | PermissionRequest
    | CompactNotification
    | HookEvent
)


# ---------------------------------------------------------------------------
# LLM 响应收集器
# ---------------------------------------------------------------------------


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCallComplete] = field(default_factory=list)
    thinking_blocks: list[ThinkingBlock] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    usage_valid: bool = False


class StreamCollector:
    def __init__(self) -> None:
        self.response = LLMResponse()

    async def consume(
        self, stream: AsyncIterator[StreamEvent]
    ) -> AsyncIterator[AgentEvent]:
        async for event in stream:
            if isinstance(event, TextDelta):
                self.response.text += event.text
                yield StreamText(text=event.text)
            elif isinstance(event, ThinkingDelta):
                yield ThinkingText(text=event.text)
            elif isinstance(event, ThinkingComplete):
                self.response.thinking_blocks.append(
                    ThinkingBlock(thinking=event.thinking, signature=event.signature)
                )
            elif isinstance(event, ToolCallStart):
                pass
            elif isinstance(event, ToolCallDelta):
                pass
            elif isinstance(event, ToolCallComplete):
                self.response.tool_calls.append(event)
                yield ToolUseEvent(
                    tool_name=event.tool_name,
                    tool_id=event.tool_id,
                    arguments=event.arguments,
                )
            elif isinstance(event, StreamEnd):
                self.response.stop_reason = event.stop_reason
                self.response.input_tokens = event.input_tokens
                self.response.output_tokens = event.output_tokens
                self.response.cache_read = event.cache_read
                self.response.cache_creation = event.cache_creation
                self.response.usage_valid = event.usage_valid


# ---------------------------------------------------------------------------
# tool 批量执行
# ---------------------------------------------------------------------------


@dataclass
class ToolBatch:
    concurrent: bool
    calls: list[ToolCallComplete]


def partition_tool_calls(
    tool_calls: list[ToolCallComplete],
    registry: ToolRegistry,
) -> list[ToolBatch]:
    batches: list[ToolBatch] = []
    for tc in tool_calls:
        tool = registry.get(tc.tool_name)
        safe = (
            tool is not None
            and tool.is_concurrency_safe
            and registry.is_enabled(tc.tool_name)
        )

        if safe and batches and batches[-1].concurrent:
            batches[-1].calls.append(tc)
        else:
            batches.append(ToolBatch(concurrent=safe, calls=[tc]))
    return batches


# ---------------------------------------------------------------------------
# streaming 执行器 — 在 LLM streaming 期间启动 tool 执行
# ---------------------------------------------------------------------------


@dataclass
class _ToolExecResult:
    tool_id: str
    tool_name: str
    result: ToolResult
    elapsed: float
    is_unknown: bool


class StreamingExecutor:
    def __init__(self) -> None:
        self._tasks: list[tuple[int, asyncio.Task[_ToolExecResult]]] = []
        self._order = 0

    def submit(
        self,
        coro: Any,
    ) -> None:
        task = asyncio.create_task(coro)
        self._tasks.append((self._order, task))
        self._order += 1

    async def collect_results(self) -> list[_ToolExecResult]:
        if not self._tasks:
            return []
        tasks = [t for _, t in sorted(self._tasks, key=lambda x: x[0])]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[_ToolExecResult] = []
        for r in results:
            if isinstance(r, Exception):
                out.append(
                    _ToolExecResult(
                        tool_id="",
                        tool_name="",
                        result=ToolResult(
                            output=f"Tool execution error: {r}", is_error=True
                        ),
                        elapsed=0.0,
                        is_unknown=False,
                    )
                )
            else:
                out.append(r)
        return out


# ---------------------------------------------------------------------------
# Agent 主循环
# ---------------------------------------------------------------------------


class Agent:
    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        protocol: str,
        work_dir: str = ".",
        max_iterations: int = 50,
        permission_checker: PermissionChecker | None = None,
        context_window: int = 200_000,
        instructions_content: str = "",
        memory_manager: MemoryManager | None = None,
        hook_engine: HookEngine | None = None,
        max_total_tokens: int = 1_000_000,
    ) -> None:
        self.client = (
            client.with_output_limit(client.max_output_tokens)
            if (hasattr(client, "_client") and hasattr(client, "max_output_tokens"))
            else client
        )
        self.registry = registry
        self.protocol = protocol
        self.work_dir = work_dir
        self.max_iterations = max_iterations
        self.permission_checker = permission_checker
        self.permission_ceilings: list[PermissionChecker] = []
        self.permission_mode: PermissionMode = (
            permission_checker.mode if permission_checker else PermissionMode.DEFAULT
        )
        self.context_window = context_window
        self._artifact_scope = uuid.uuid4().hex
        self.token_budget = TokenBudget(
            Path(work_dir) / ".gcode" / "runtime" / "token-budget.sqlite3",
            self._artifact_scope,
            max_total_tokens,
        )
        self.session_dir = ensure_session_dir(work_dir, self._artifact_scope)
        self.last_stop_reason = "not_started"
        self.allow_cu_write = False
        self._pending_calls: dict[str, str] = {}
        self.recovery_writes_stopped = False
        self._unknown_call_ids: set[str] = set()
        self.tool_ledger = ToolLedger(
            Path(work_dir) / ".gcode" / "runtime" / "tool-calls.sqlite3"
        )
        self.compact_breaker = CompactCircuitBreaker()
        self.replacement_state: ContentReplacementState = create_replacement_state()
        # 保存重建工作上下文所需的快照，在 Layer 2 压缩对话后使用：
        # 最近的文件读取和 skill 调用。每次 ReadFile / skill 调用时记录，
        # auto_compact 触发阈值时消费。
        self.recovery_state: RecoveryState = RecoveryState()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.instructions_content = instructions_content
        self.memory_manager = memory_manager
        self.hook_engine = hook_engine
        self._loop_count = 0
        self._extracting = False
        self._session_id: str = ""
        self.active_skills: dict[str, str] = {}
        self._skill_catalog: str = ""
        self._agent_catalog: str = ""
        self._agent_catalog_list: list[tuple[str, str]] = []
        self.agent_id: str = uuid.uuid4().hex[:12]
        self.parent_id: str | None = None
        self.trace_id: str | None = None
        self.coordinator_mode: bool = False
        self.team_name: str = ""
        self._team_manager: Any = None
        self.notification_fn: Callable[[], list[str]] | None = None
        self.file_history: Any = None

    @property
    def session_id(self) -> str:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._session_id = value
        self.session_dir = ensure_session_dir(
            self.work_dir, value or self._artifact_scope
        )
        if value and self.parent_id is None:
            self.token_budget = TokenBudget(
                Path(self.work_dir) / ".gcode" / "runtime" / "token-budget.sqlite3",
                value,
                self.token_budget.max_total_tokens,
            )
        self.recovery_writes_stopped = self.tool_ledger.has_unknown_mutation(
            value or self._artifact_scope
        )

    def _record_usage(
        self,
        prompt_uncached: int,
        output: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> None:
        self.token_budget.record_usage(prompt_uncached, output, cache_read, cache_write)
        self.total_input_tokens += prompt_uncached + cache_read + cache_write
        self.total_output_tokens += output

    def budgeted_side_client(self, client: LLMClient) -> LLMClient:
        from gcode.runtime.client_budget import BudgetedSideClient

        return BudgetedSideClient(client, self)

    def execution_context(self) -> ToolExecutionContext:
        return ToolExecutionContext(
            run_id=self.agent_id,
            session_id=self.session_id or self._artifact_scope,
            cwd=Path(self.work_dir).expanduser().resolve(),
            artifact_dir=self.session_dir,
            parent_run_id=self.parent_id,
            trace_id=self.trace_id or self.agent_id,
            allow_cu_write=self.allow_cu_write and self.parent_id is None,
        )

    def _normalize_tool_call(self, call: ToolCallComplete) -> ToolCallComplete:
        return ToolCallComplete(
            call.tool_id,
            call.tool_name,
            self.execution_context().normalize_arguments(
                call.tool_name, call.arguments
            ),
        )

    def _permission_decision(self, tool: Any, arguments: dict[str, Any]) -> Decision:
        if tool.category == "write" and tool.name in {"WriteFile", "EditFile"}:
            target = self.execution_context().resolve_path(
                arguments.get("file_path", ".")
            )
            protected = [
                self.session_dir.resolve(),
                (Path(self.work_dir) / ".gcode" / "runtime").resolve(),
                (Path(self.work_dir) / ".gcode" / "sessions").resolve(),
            ]
            if any(target.is_relative_to(directory) for directory in protected):
                return Decision(
                    effect="deny",
                    reason="Runtime receipts and artifacts are not editable through file tools",
                )
        if self.recovery_writes_stopped and tool.category != "read":
            return Decision(
                effect="deny",
                reason="Recovered action outcome unknown; inspect before explicit recovery",
            )
        decisions = [
            checker.check(tool, arguments)
            for checker in (
                [self.permission_checker] if self.permission_checker else []
            )
            + self.permission_ceilings
        ]
        for effect in ("deny", "ask"):
            for decision in decisions:
                if decision.effect == effect:
                    return decision
        return Decision(
            effect="allow", reason="All run permission scopes allow this call"
        )

    def persist_notification(
        self, conversation: ConversationManager, note: str
    ) -> None:
        from gcode.runtime.notifications import NotificationStore

        scope = self.session_id or self._artifact_scope
        store = NotificationStore(
            Path(self.work_dir) / ".gcode" / "runtime" / "notifications.sqlite3"
        )
        identifier = store.put(scope, note)
        if not any(
            identifier in message.notification_ids for message in conversation.history
        ):
            conversation.add_system_reminder(note)
            conversation.history[-1].notification_ids = [identifier]
        self._save_checkpoint(conversation)

    def _save_checkpoint(self, conversation: ConversationManager) -> None:
        from gcode.runtime.journal import save_checkpoint

        save_checkpoint(
            self.session_dir / "runtime-checkpoint.json",
            conversation,
            run_id=self.agent_id,
            session_id=self.session_id,
            pending_calls=self._pending_calls,
            stop_reason=self.last_stop_reason,
            recovery_writes_stopped=self.recovery_writes_stopped,
            unknown_call_ids=sorted(self._unknown_call_ids),
        )

    def restore_checkpoint(self) -> ConversationManager:
        from gcode.runtime.journal import load_checkpoint, recovery_state

        conversation, state = load_checkpoint(
            self.session_dir / "runtime-checkpoint.json"
        )
        recovered = recovery_state(
            self.tool_ledger, self.session_id or self._artifact_scope, state
        )
        self._pending_calls = recovered["pending_calls"]
        self._unknown_call_ids = set(recovered["unknown_call_ids"])
        self.recovery_writes_stopped = recovered["recovery_writes_stopped"]
        return conversation

    async def _invoke_journaled(
        self, tool: Any, params: Any, call: ToolCallComplete
    ) -> ToolResult:
        scope = self.session_id or self._artifact_scope
        try:
            prior = self.tool_ledger.begin(
                scope, call.tool_id, call.tool_name, call.arguments, tool.category
            )
        except ValueError as error:
            return ToolResult(str(error), True, {"delivery_state": "not_dispatched"})
        if prior is not None:
            if (prior.details or {}).get(
                "delivery_state"
            ) == "delivery_unknown" and tool.category != "read":
                self.recovery_writes_stopped = True
                self._unknown_call_ids.add(call.tool_id)
            return prior
        try:
            from dataclasses import replace

            result = await tool.invoke(
                params, replace(self.execution_context(), tool_call_id=call.tool_id)
            )
        except asyncio.CancelledError:
            if tool.category != "read":
                self.recovery_writes_stopped = True
                self._unknown_call_ids.add(call.tool_id)
            raise
        except Exception as error:
            result = ToolResult(
                f"Tool invocation failed after dispatch: {error}",
                True,
                {
                    "delivery_state": "delivery_unknown"
                    if tool.category != "read"
                    else "not_delivered"
                },
            )
        if (
            tool.category != "read"
            and result.is_error
            and not (result.details or {}).get("delivery_state")
        ):
            result.details = {
                **(result.details or {}),
                "delivery_state": "delivery_unknown",
            }
        if (result.details or {}).get(
            "delivery_state"
        ) == "delivery_unknown" and tool.category != "read":
            self.recovery_writes_stopped = True
            self._unknown_call_ids.add(call.tool_id)
        self.tool_ledger.finish(scope, call.tool_id, result)
        return result

    @property
    def _transcript_path(self) -> str:
        if self.session_id:
            return str(
                Path(self.work_dir) / ".gcode" / "sessions" / f"{self.session_id}.jsonl"
            )
        return ""

    @property
    def plan_mode(self) -> bool:
        return self.permission_mode == PermissionMode.PLAN

    _plan_path_cache: Path | None = None

    def _get_plan_path(self) -> Path:
        if self._plan_path_cache is not None:
            return self._plan_path_cache
        import random
        import datetime

        _ADJECTIVES = [
            "bold",
            "bright",
            "calm",
            "cool",
            "deep",
            "fair",
            "fast",
            "fine",
            "glad",
            "keen",
            "kind",
            "lean",
            "mild",
            "neat",
            "pure",
            "safe",
            "slim",
            "soft",
            "tall",
            "warm",
            "wise",
            "grand",
            "swift",
            "vivid",
        ]
        _NOUNS = [
            "sketch",
            "draft",
            "spark",
            "bloom",
            "trail",
            "ridge",
            "creek",
            "grove",
            "cliff",
            "cloud",
            "field",
            "forge",
            "frost",
            "haven",
            "pearl",
            "stone",
            "storm",
            "river",
            "tower",
            "delta",
            "flame",
            "orbit",
            "pulse",
            "shore",
        ]
        plans_dir = Path(self.work_dir) / ".gcode" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%m%d-%H%M")
        slug = f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}-{ts}"
        self._plan_path_cache = plans_dir / f"{slug}.md"
        return self._plan_path_cache

    def set_permission_mode(self, mode: PermissionMode) -> None:
        self.permission_mode = mode
        if self.permission_checker:
            self.permission_checker.mode = mode

    def activate_skill(self, name: str, prompt_body: str) -> None:
        self.active_skills[name] = prompt_body

    def clear_active_skills(self) -> None:
        self.active_skills.clear()

    def set_skill_catalog(self, catalog: str) -> None:
        self._skill_catalog = catalog

    def set_agent_catalog(
        self, catalog: str, catalog_list: list[tuple[str, str]] | None = None
    ) -> None:
        self._agent_catalog = catalog
        if catalog_list is not None:
            self._agent_catalog_list = catalog_list

    def _build_hook_context(self, event: str, **kwargs: str | dict) -> HookContext:
        return HookContext(
            event_name=event,
            tool_name=str(kwargs.get("tool_name", "")),
            tool_args=kwargs.get("tool_args", {}),
            file_path=str(kwargs.get("file_path", "")),
            message=str(kwargs.get("message", "")),
            error=str(kwargs.get("error", "")),
            cwd=str(self.execution_context().cwd),
            run_id=self.agent_id,
        )

    def _infer_file_path(self, args: dict) -> str:
        return str(args.get("file_path", args.get("path", "")))

    def _drain_hook_events(self) -> list[HookEvent]:
        if not self.hook_engine:
            return []
        return [
            HookEvent(
                hook_id=n.hook_id,
                event=n.event,
                output=n.output,
                success=n.success,
            )
            for n in self.hook_engine.drain_notifications()
        ]

    async def run(self, conversation: ConversationManager) -> AsyncIterator[AgentEvent]:
        conversation.repair_tool_chain()
        self.last_stop_reason = "running"
        stream = self._run(conversation)
        try:
            async for event in stream:
                if isinstance(event, ToolResultEvent):
                    self._pending_calls.pop(event.tool_id, None)
                if isinstance(
                    event,
                    (ToolResultEvent, TurnComplete, LoopComplete, CompactNotification),
                ):
                    self._save_checkpoint(conversation)
                yield event
        finally:
            try:
                await stream.aclose()
            finally:
                conversation.repair_tool_chain()
                self._save_checkpoint(conversation)

    def prepare_conversation(self, conversation: ConversationManager) -> str:
        """Inject the initial context before the UI takes its persistence cursor."""
        conversation.repair_tool_chain()
        env_context = (
            conversation.history[0].content
            if conversation.env_injected and conversation.history
            else build_environment_context(
                self.work_dir,
                self.active_skills,
                self._skill_catalog,
                self._agent_catalog,
            )
        )
        conversation.inject_environment(env_context)

        memory_content = self.memory_manager.load() if self.memory_manager else ""
        conversation.inject_long_term_memory(self.instructions_content, memory_content)
        return env_context

    async def _run(
        self, conversation: ConversationManager
    ) -> AsyncIterator[AgentEvent]:
        self._current_conversation = conversation
        env_context = self.prepare_conversation(conversation)

        if self.hook_engine:
            ctx = self._build_hook_context("session_start")
            await self.hook_engine.run_hooks("session_start", ctx)
            for he in self._drain_hook_events():
                yield he

        iteration = 0
        consecutive_unknown = 0
        max_tokens_escalated = False
        output_recoveries = 0

        while True:
            iteration += 1
            if not self.token_budget.before_request():
                self.last_stop_reason = "budget_exhausted"
                yield ErrorEvent(
                    message="Shared run token budget exhausted; no further model request sent"
                )
                break

            if iteration > self.max_iterations:
                self.last_stop_reason = "limit_reached"
                yield ErrorEvent(
                    message=f"Agent reached maximum iterations ({self.max_iterations})"
                )
                break

            if self.hook_engine:
                ctx = self._build_hook_context("turn_start")
                await self.hook_engine.run_hooks("turn_start", ctx)
                for he in self._drain_hook_events():
                    yield he

            self._consume_mailbox(conversation)
            if self.notification_fn:
                for note in self.notification_fn():
                    conversation.add_system_reminder(note)

            # Layer 2: 接近 context window 上限时自动 compact（操作原始对话）
            compact_result = await auto_compact(
                conversation,
                self.client,
                self.context_window,
                self.session_dir,
                protocol=self.protocol,
                breaker=self.compact_breaker,
                recovery=self.recovery_state,
                tool_schemas=self.registry.get_all_schemas(self.protocol),
                transcript_path=self._transcript_path,
                usage_recorder=self._record_usage,
                usage_unknown_recorder=self.token_budget.mark_usage_unknown,
            )
            if isinstance(compact_result, CompactEvent):
                yield CompactNotification(
                    before_tokens=compact_result.before_tokens,
                    message=f"上下文已压缩（压缩前 {compact_result.before_tokens:,} tokens）",
                    boundary=compact_result.boundary,
                )
                conversation.inject_environment(env_context)
                mem = self.memory_manager.load() if self.memory_manager else ""
                conversation.inject_long_term_memory(self.instructions_content, mem)
            elif isinstance(compact_result, str):
                yield ErrorEvent(message=compact_result)

            if self.hook_engine:
                ctx = self._build_hook_context("pre_send")
                await self.hook_engine.run_hooks("pre_send", ctx)
                for he in self._drain_hook_events():
                    yield he

            hook_prompts = (
                self.hook_engine.get_prompt_messages() if self.hook_engine else None
            )
            system = build_system_prompt(
                hook_prompts=hook_prompts,
                coordinator_mode=self.coordinator_mode,
                agent_catalog=self._agent_catalog_list or None,
            )

            if self.plan_mode:
                plan_path = str(self._get_plan_path())
                if self.permission_checker:
                    self.permission_checker.plan_file_path = plan_path
                plan_exists = self._get_plan_path().exists()
                plan_reminder = build_plan_mode_reminder(
                    plan_path, plan_exists, iteration
                )
                conversation.add_system_reminder(plan_reminder)

            if self.hook_engine:
                for note in self.hook_engine.drain_notifications():
                    conversation.add_system_reminder(
                        f"Hook [{note.hook_id}] {note.event}: {note.output}"
                    )

            deferred_names = self.registry.get_deferred_tool_names()
            if deferred_names:
                conversation.add_system_reminder(
                    "The following deferred tools are available via ToolSearch. "
                    "Their schemas are NOT loaded - use ToolSearch with "
                    'query "select:<name>[,<name>...]" to load tool schemas before calling them:\n'
                    + "\n".join(deferred_names)
                )

            tools = self.registry.get_all_schemas(self.protocol)

            # Layer 1: 在 LLM 调用前应用 tool-result budget，确保 api_conv 反映
            # 本轮迭代中所有已发生的写入（system reminders、hook 通知等）。
            # 原始 conversation 不会被修改；替换决策保存在 self.replacement_state 中。
            api_conv, _new_records = apply_tool_result_budget(
                conversation, self.session_dir, self.replacement_state
            )
            if _new_records:
                append_replacement_records(self.session_dir, _new_records)

            collector = StreamCollector()
            if not self.token_budget.before_request():
                self.last_stop_reason = "budget_exhausted"
                yield ErrorEvent(
                    message="Shared budget exhausted after compaction; no main request sent"
                )
                break
            llm_stream = self.client.stream(api_conv, system=system, tools=tools)
            collected_stream = collector.consume(llm_stream)
            try:
                async for event in collected_stream:
                    yield event
            except BaseException:
                self.token_budget.mark_usage_unknown()
                self.last_stop_reason = "failed"
                raise
            finally:
                await collected_stream.aclose()
                await llm_stream.aclose()

            response = collector.response
            if response.usage_valid:
                self._record_usage(
                    response.input_tokens,
                    response.output_tokens,
                    response.cache_read,
                    response.cache_creation,
                )
            else:
                self.token_budget.mark_usage_unknown()
            if response.stop_reason in {"", "error", "aborted"}:
                self.last_stop_reason = "failed"
                yield ErrorEvent(
                    message="Model stream ended without a complete response; no tools dispatched"
                )
                break

            if self.hook_engine:
                ctx = self._build_hook_context("post_receive", message=response.text)
                await self.hook_engine.run_hooks("post_receive", ctx)
                for he in self._drain_hook_events():
                    yield he

            yield UsageEvent(
                input_tokens=self.total_input_tokens,
                output_tokens=self.total_output_tokens,
            )

            conv_thinking = [
                ConvThinkingBlock(thinking=tb.thinking, signature=tb.signature)
                for tb in response.thinking_blocks
            ]

            if response.stop_reason == "max_tokens":
                if not max_tokens_escalated:
                    self.client.set_max_output_tokens(MAX_TOKENS_CEILING)
                    max_tokens_escalated = True
                    if response.text:
                        conversation.add_assistant_message(
                            response.text, thinking_blocks=conv_thinking
                        )
                        conversation.add_user_message(
                            "Output token limit hit. Resume directly from where you stopped. "
                            "Do not apologize or repeat previous content. Pick up mid-thought if needed."
                        )
                    yield RetryEvent(reason="max_tokens escalation")
                    continue
                elif output_recoveries < MAX_OUTPUT_TOKENS_RECOVERIES:
                    output_recoveries += 1
                    conversation.add_assistant_message(
                        response.text, thinking_blocks=conv_thinking
                    )
                    conversation.add_user_message(
                        "Output token limit hit. Resume directly from where you stopped. "
                        "Break remaining work into smaller pieces."
                    )
                    yield RetryEvent(
                        reason=f"max_tokens recovery {output_recoveries}/{MAX_OUTPUT_TOKENS_RECOVERIES}"
                    )
                    continue
                else:
                    self.last_stop_reason = "limit_reached"
                    yield ErrorEvent(
                        message="Model output remained truncated after bounded recovery"
                    )
                    break
            else:
                output_recoveries = 0

            if not response.tool_calls:
                outcome = (
                    "delivery_unknown" if self.recovery_writes_stopped else "completed"
                )
                if self.recovery_writes_stopped:
                    warning = (
                        "\n\n执行结果待核查：此前有工具副作用未知，不能确认任务完成。"
                    )
                    response.text += warning
                    yield StreamText(text=warning)
                conversation.add_assistant_message(
                    response.text, thinking_blocks=conv_thinking
                )
                self._loop_count += 1
                if (
                    self._loop_count % MEMORY_EXTRACTION_INTERVAL == 0
                    and self.memory_manager
                ):
                    asyncio.ensure_future(self._extract_memories(conversation))
                if self.hook_engine:
                    ctx = self._build_hook_context("turn_end")
                    await self.hook_engine.run_hooks("turn_end", ctx)
                    ctx = self._build_hook_context("session_end")
                    await self.hook_engine.run_hooks("session_end", ctx)
                    for he in self._drain_hook_events():
                        yield he
                if self.file_history is not None:
                    summary = (
                        response.text[:60] + "..."
                        if len(response.text) > 60
                        else response.text
                    )
                    self.file_history.make_snapshot(len(conversation.history), summary)
                self.last_stop_reason = outcome
                yield LoopComplete(total_turns=iteration, stop_reason=outcome)
                break

            tool_uses = [
                ToolUseBlock(
                    tool_use_id=tc.tool_id,
                    tool_name=tc.tool_name,
                    arguments=tc.arguments,
                )
                for tc in response.tool_calls
            ]
            conversation.add_assistant_message(
                response.text, tool_uses, thinking_blocks=conv_thinking
            )
            # 在 assistant 回复加入历史后锚定实际用量：基线（input + cache + output）
            # 覆盖到当前位置，因此下一轮迭代顶部的 auto-compact 检查只需对
            # 接下来追加的 tool results 做字符估算。
            conversation.record_usage_anchor(
                response.input_tokens,
                response.output_tokens,
                response.cache_read,
                response.cache_creation,
            )

            tool_results: list[ToolResultBlock] = []
            # Keep partial successes in history even if a later call is cancelled.
            conversation.add_tool_results_message(tool_results)
            calls = [self._normalize_tool_call(call) for call in response.tool_calls]
            batches = partition_tool_calls(calls, self.registry)
            if self.permission_checker:
                for batch in batches:
                    if batch.concurrent and any(
                        self._permission_decision(
                            self.registry.get(call.tool_name),
                            self._normalize_tool_call(call).arguments,
                        ).effect
                        != "allow"
                        for call in batch.calls
                    ):
                        batch.concurrent = False

            def record_parallel_result(br: _ToolExecResult) -> None:
                tool_results.append(
                    ToolResultBlock(
                        tool_use_id=br.tool_id,
                        content=self._maybe_persist_or_truncate(
                            br.tool_id, br.result.output
                        ),
                        is_error=br.result.is_error,
                        details=br.result.details,
                        content_blocks=br.result.content,
                    )
                )

            for batch in batches:
                if batch.concurrent and len(batch.calls) > 1:
                    batch_results = await self._execute_batch_parallel(
                        batch.calls, on_result=record_parallel_result
                    )
                    for br in batch_results:
                        if br.is_unknown:
                            consecutive_unknown += 1
                        else:
                            consecutive_unknown = 0
                        yield ToolResultEvent(
                            tool_id=br.tool_id,
                            tool_name=br.tool_name,
                            output=br.result.output,
                            is_error=br.result.is_error,
                            elapsed=br.elapsed,
                        )
                else:
                    for tc in batch.calls:
                        result: ToolResult | None = None
                        elapsed = 0.0
                        is_unknown = False

                        if self.hook_engine:
                            file_path = self._infer_file_path(tc.arguments)
                            hook_ctx = self._build_hook_context(
                                "pre_tool_use",
                                tool_name=tc.tool_name,
                                tool_args=tc.arguments,
                                file_path=file_path,
                            )
                            rejection = await self.hook_engine.run_pre_tool_hooks(
                                hook_ctx
                            )
                            for he in self._drain_hook_events():
                                yield he
                            if rejection is not None:
                                result = ToolResult(
                                    output=f"Hook rejected: {rejection.reason}",
                                    is_error=True,
                                )
                                content = self._maybe_persist_or_truncate(
                                    tc.tool_id, result.output
                                )
                                tool_results.append(
                                    ToolResultBlock(
                                        tool_use_id=tc.tool_id,
                                        content=content,
                                        is_error=True,
                                    )
                                )
                                yield ToolResultEvent(
                                    tool_id=tc.tool_id,
                                    tool_name=tc.tool_name,
                                    output=result.output,
                                    is_error=True,
                                    elapsed=0.0,
                                )
                                continue

                        async for item in self._execute_tool(tc):
                            if isinstance(item, PermissionRequest):
                                yield item
                            else:
                                result, elapsed, is_unknown = item

                        if result is None:
                            result = ToolResult(
                                output="Error: no result from tool", is_error=True
                            )

                        if is_unknown:
                            consecutive_unknown += 1
                        else:
                            consecutive_unknown = 0

                        content = self._maybe_persist_or_truncate(
                            tc.tool_id, result.output
                        )
                        tool_results.append(
                            ToolResultBlock(
                                tool_use_id=tc.tool_id,
                                content=content,
                                is_error=result.is_error,
                                details=result.details,
                                content_blocks=result.content,
                            )
                        )
                        if self.hook_engine:
                            file_path = self._infer_file_path(tc.arguments)
                            hook_ctx = self._build_hook_context(
                                "post_tool_use",
                                tool_name=tc.tool_name,
                                tool_args=tc.arguments,
                                file_path=file_path,
                            )
                            await self.hook_engine.run_hooks("post_tool_use", hook_ctx)
                            for he in self._drain_hook_events():
                                yield he
                        yield ToolResultEvent(
                            tool_id=tc.tool_id,
                            tool_name=tc.tool_name,
                            output=result.output,
                            is_error=result.is_error,
                            elapsed=elapsed,
                        )

            if consecutive_unknown >= 3:
                self.last_stop_reason = "failed"
                yield ErrorEvent(
                    message="Agent terminated: too many consecutive unknown tool calls"
                )
                break

            exit_plan_called = any(
                tc.tool_name == "ExitPlanMode" for tc in response.tool_calls
            )
            if exit_plan_called:
                yield TurnComplete(turn=iteration)
                self.last_stop_reason = (
                    "delivery_unknown" if self.recovery_writes_stopped else "completed"
                )
                yield LoopComplete(
                    total_turns=iteration, stop_reason=self.last_stop_reason
                )
                break

            if self.hook_engine:
                ctx = self._build_hook_context("turn_end")
                await self.hook_engine.run_hooks("turn_end", ctx)
                for he in self._drain_hook_events():
                    yield he
            yield TurnComplete(turn=iteration)

    def _consume_mailbox(self, conversation: ConversationManager) -> None:
        if not self.team_name or not self._team_manager:
            return
        try:
            mailbox = self._team_manager.get_mailbox(self.team_name)
            if mailbox is None:
                return
            owner = self.agent_id + ":inbox"
            messages = mailbox.claim(self.agent_id, owner)
            for msg in messages:
                prefix = f"[Message from {msg.from_agent}]"
                if msg.message_type != "text":
                    prefix = f"[{msg.message_type} from {msg.from_agent}]"
                content = f"[mailbox:{msg.id}] {prefix} {msg.content}"
                self.persist_notification(conversation, content)
                mailbox.ack(self.agent_id, msg.id, owner)
        except Exception as e:
            log.debug("Mailbox consumption failed: %s", e)

    def _build_permission_description(self, tc: ToolCallComplete) -> str:
        if tc.tool_name == "Bash":
            return tc.arguments.get("command", tc.tool_name)
        if tc.tool_name in ("ReadFile", "WriteFile", "EditFile"):
            return tc.arguments.get("file_path", tc.tool_name)
        return str(tc.arguments)

    async def _execute_single_tool_direct(
        self, tc: ToolCallComplete
    ) -> _ToolExecResult:
        tc = self._normalize_tool_call(tc)
        tool = self.registry.get(tc.tool_name)
        start = time.monotonic()

        if tool is None:
            return _ToolExecResult(
                tool_id=tc.tool_id,
                tool_name=tc.tool_name,
                result=ToolResult(
                    output=f"Error: unknown tool '{tc.tool_name}'", is_error=True
                ),
                elapsed=time.monotonic() - start,
                is_unknown=True,
            )

        if not self.registry.is_enabled(tc.tool_name):
            return _ToolExecResult(
                tool_id=tc.tool_id,
                tool_name=tc.tool_name,
                result=ToolResult(
                    output=f"Error: tool '{tc.tool_name}' is disabled", is_error=True
                ),
                elapsed=time.monotonic() - start,
                is_unknown=False,
            )

        result = await self._execute_tool_noninteractive(tc)

        self._snapshot_for_recovery(tc, result)

        return _ToolExecResult(
            tool_id=tc.tool_id,
            tool_name=tc.tool_name,
            result=result,
            elapsed=time.monotonic() - start,
            is_unknown=False,
        )

    async def _execute_batch_parallel(
        self,
        calls: list[ToolCallComplete],
        on_result: Callable[[_ToolExecResult], None] | None = None,
    ) -> list[_ToolExecResult]:
        async def execute(tc: ToolCallComplete) -> _ToolExecResult:
            result = await self._execute_single_tool_direct(tc)
            if on_result is not None:
                on_result(result)
            return result

        tasks = [asyncio.create_task(execute(tc)) for tc in calls]
        try:
            return list(await asyncio.gather(*tasks))
        finally:
            # gather may raise before siblings finish (or be cancelled itself).
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_tool(
        self, tc: ToolCallComplete
    ) -> AsyncIterator[tuple[ToolResult, float, bool]]:
        tc = self._normalize_tool_call(tc)
        tool = self.registry.get(tc.tool_name)
        start = time.monotonic()
        is_unknown = False

        if tool is None:
            result = ToolResult(
                output=f"Error: unknown tool '{tc.tool_name}'", is_error=True
            )
            is_unknown = True
            elapsed = time.monotonic() - start
            yield result, elapsed, is_unknown
            return

        if not self.registry.is_enabled(tc.tool_name):
            result = ToolResult(
                output=f"Error: tool '{tc.tool_name}' is disabled in current mode",
                is_error=True,
            )
            elapsed = time.monotonic() - start
            yield result, elapsed, is_unknown
            return

        # 权限检查
        if (
            self.permission_checker
            or self.permission_ceilings
            or self.recovery_writes_stopped
        ):
            decision = self._permission_decision(tool, tc.arguments)

            if decision.effect == "deny":
                result = ToolResult(
                    output=f"Permission denied: {decision.reason}",
                    is_error=True,
                )
                elapsed = time.monotonic() - start
                yield result, elapsed, is_unknown
                return

            if decision.effect == "ask":
                loop = asyncio.get_running_loop()
                future: asyncio.Future[PermissionResponse] = loop.create_future()
                desc = self._build_permission_description(tc)
                # 向调用方 yield 权限请求事件，由调用方处理
                yield PermissionRequest(
                    tool_name=tc.tool_name,
                    description=desc,
                    future=future,
                )
                response = await future

                if response == PermissionResponse.DENY:
                    result = ToolResult(
                        output="Permission denied: 用户拒绝了此操作",
                        is_error=True,
                    )
                    elapsed = time.monotonic() - start
                    yield result, elapsed, is_unknown
                    return

                if response == PermissionResponse.ALLOW_ALWAYS:
                    from gcode.permissions.rules import Rule, extract_content

                    content = extract_content(tc.tool_name, tc.arguments)
                    pattern = f"{content[:60]}*" if len(content) > 60 else f"{content}*"
                    rule = Rule(tool_name=tc.tool_name, pattern=pattern, effect="allow")
                    self.permission_checker.rule_engine.append_local_rule(rule)

        try:
            params = tool.params_model.model_validate(tc.arguments)
            self._pending_calls[tc.tool_id] = tool.category
            if hasattr(self, "_current_conversation"):
                self._save_checkpoint(self._current_conversation)
            result = await self._invoke_journaled(tool, params, tc)
        except ValidationError as e:
            result = ToolResult(
                output=f"Parameter validation error: {e}", is_error=True
            )
        except Exception as e:
            result = ToolResult(output=f"Tool execution error: {e}", is_error=True)

        self._snapshot_for_recovery(tc, result)

        elapsed = time.monotonic() - start
        yield result, elapsed, is_unknown

    def _snapshot_for_recovery(self, tc: ToolCallComplete, result: ToolResult) -> None:
        """捕获 ReadFile 刚交给模型的内容，以便 Layer 2 压缩对话后
        auto_compact 能重新附加这些数据。每次 ReadFile 多一次磁盘读取，
        比从 tool 输出中反向解析行号要划算。
        """
        if result.is_error or tc.tool_name != "ReadFile":
            return
        path = tc.arguments.get("file_path") if isinstance(tc.arguments, dict) else None
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            return
        self.recovery_state.record_file_read(path, content)

    async def _extract_memories(self, conversation: ConversationManager) -> None:
        if self._extracting or not self.memory_manager:
            return
        self._extracting = True
        try:
            await self.memory_manager.extract(
                self.budgeted_side_client(self.client), conversation, self.protocol
            )
        except Exception as e:
            log.debug("Memory extraction failed: %s", e)
        finally:
            self._extracting = False

    async def manual_compact(
        self, conversation: ConversationManager
    ) -> CompactNotification | ErrorEvent:
        # auto_compact 会用摘要替换 conversation.history，所有 tool-result 内容
        # （原始或已替换的）都将被丢弃。这里跳过 apply_tool_result_budget —
        # 它在主循环中的唯一目的是为 LLM 调用生成 api_conv，而本路径不需要
        # 发起看到替换结果的 LLM 调用（auto_compact 内部的摘要调用操作的是原始对话）。
        if not self.token_budget.before_request():
            return ErrorEvent(
                message="Shared run token budget exhausted; summary not dispatched"
            )
        result = await auto_compact(
            conversation,
            self.client,
            self.context_window,
            self.session_dir,
            protocol=self.protocol,
            manual=True,
            breaker=self.compact_breaker,
            recovery=self.recovery_state,
            tool_schemas=self.registry.get_all_schemas(self.protocol),
            transcript_path=self._transcript_path,
            usage_recorder=self._record_usage,
            usage_unknown_recorder=self.token_budget.mark_usage_unknown,
        )
        if isinstance(result, CompactEvent):
            env_context = build_environment_context(
                self.work_dir,
                self.active_skills,
                self._skill_catalog,
                self._agent_catalog,
            )
            conversation.inject_environment(env_context)
            memory_content = self.memory_manager.load() if self.memory_manager else ""
            conversation.inject_long_term_memory(
                self.instructions_content, memory_content
            )
            return CompactNotification(
                before_tokens=result.before_tokens,
                message=f"上下文已压缩（压缩前 {result.before_tokens:,} tokens）",
                boundary=result.boundary,
            )
        return ErrorEvent(message=result or "压缩失败：对话历史为空或未达到压缩条件")

    async def run_to_completion(
        self,
        task: str,
        conversation: ConversationManager | None = None,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        conversation = (
            conversation if conversation is not None else ConversationManager()
        )
        original_messages = {id(message) for message in conversation.history}
        if task:
            conversation.add_user_message(task)
        chunks: list[str] = []
        try:
            async for event in self.run(conversation):
                if isinstance(event, PermissionRequest):
                    if not event.future.done():
                        event.future.set_result(PermissionResponse.DENY)
                elif isinstance(event, StreamText):
                    chunks.append(event.text)
                    if event_callback:
                        event_callback({"type": "stream_text", "text": event.text})
                elif isinstance(event, ToolUseEvent) and event_callback:
                    event_callback(
                        {
                            "type": "tool_use",
                            "toolName": event.tool_name,
                            "args": event.arguments,
                        }
                    )
                elif isinstance(event, UsageEvent) and event_callback:
                    event_callback(
                        {
                            "type": "usage",
                            "usage": {
                                "inputTokens": event.input_tokens,
                                "outputTokens": event.output_tokens,
                                "cumulative": True,
                            },
                        }
                    )
        except asyncio.CancelledError:
            self.last_stop_reason = "cancelled"
            raise
        except Exception:
            self.last_stop_reason = "failed"
            raise
        # Return the actual final answer, not intermediate model deliberation.
        for message in reversed(conversation.history):
            if (
                id(message) not in original_messages
                and message.role == "assistant"
                and not message.tool_uses
            ):
                return message.content
        return "".join(chunks)

    async def _execute_tool_noninteractive(self, tc: ToolCallComplete) -> ToolResult:
        tc = self._normalize_tool_call(tc)
        tool = self.registry.get(tc.tool_name)

        if tool is None:
            return ToolResult(
                output=f"Error: unknown tool '{tc.tool_name}'", is_error=True
            )

        if not self.registry.is_enabled(tc.tool_name):
            return ToolResult(
                output=f"Error: tool '{tc.tool_name}' is disabled",
                is_error=True,
            )

        if self.hook_engine:
            file_path = self._infer_file_path(tc.arguments)
            hook_ctx = self._build_hook_context(
                "pre_tool_use",
                tool_name=tc.tool_name,
                tool_args=tc.arguments,
                file_path=file_path,
            )
            rejection = await self.hook_engine.run_pre_tool_hooks(hook_ctx)
            if rejection is not None:
                return ToolResult(
                    output=f"Hook rejected: {rejection.reason}",
                    is_error=True,
                )

        if (
            self.permission_checker
            or self.permission_ceilings
            or self.recovery_writes_stopped
        ):
            decision = self._permission_decision(tool, tc.arguments)
            if decision.effect == "deny":
                return ToolResult(
                    output=f"Permission denied: {decision.reason}",
                    is_error=True,
                )
            if decision.effect == "ask":
                return ToolResult(
                    output="Permission denied: non-interactive agent cannot prompt user",
                    is_error=True,
                )

        try:
            params = tool.params_model.model_validate(tc.arguments)
            self._pending_calls[tc.tool_id] = tool.category
            if hasattr(self, "_current_conversation"):
                self._save_checkpoint(self._current_conversation)
            result = await self._invoke_journaled(tool, params, tc)
        except ValidationError as e:
            result = ToolResult(
                output=f"Parameter validation error: {e}", is_error=True
            )
        except Exception as e:
            result = ToolResult(output=f"Tool execution error: {e}", is_error=True)

        if self.hook_engine:
            file_path = self._infer_file_path(tc.arguments)
            hook_ctx = self._build_hook_context(
                "post_tool_use",
                tool_name=tc.tool_name,
                tool_args=tc.arguments,
                file_path=file_path,
            )
            await self.hook_engine.run_hooks("post_tool_use", hook_ctx)

        return result

    def _maybe_persist_or_truncate(self, tool_use_id: str, text: str) -> str:
        from gcode.context.manager import (
            SINGLE_RESULT_CHAR_LIMIT,
            make_persisted_preview,
            persist_tool_result,
        )

        if len(text) > MAX_OUTPUT_CHARS:
            fp = persist_tool_result(tool_use_id, text, self.session_dir)
            return make_persisted_preview(text, fp)
        return text

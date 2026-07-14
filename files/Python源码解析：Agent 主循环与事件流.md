## 模块概览

把 Agent Loop 的所有代码集中在一个文件里：

| 文件                 | 职责                                                                  |
| ------------------ | ------------------------------------------------------------------- |
| `gcode/agent.py` | 全部。事件类型定义、Agent 类、StreamCollector 流消费、StreamingExecutor 并行执行、工具分批逻辑 |

单文件，集中度很高。事件定义、流收集器、执行器都内聚到同一个模块里，不需要跳文件。

## 核心类型

### Agent 类

```python
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
    ) -> None:
```

驱动循环的核心三件套是 `client` 、 `registry` 、 `protocol` 。构造函数直接把所有可选能力都用关键字参数传进来，一次性配好。关键字参数自带命名和默认值，调用方只需要指定想改的参数，其余全用默认值。

`max_iterations` 默认 50，比较保守，防止 Agent 失控运行。

额外几个字段值得注意： `compact_breaker` 是上下文压缩的熔断器，防止压缩反复失败时陷入死循环； `_loop_count` 追踪循环完成次数，用于触发定期记忆提取； `recovery_state` 保存文件读取快照，压缩对话后可以重新附加这些数据。

### AgentEvent：用 Union 模拟代数类型

用 `dataclass` + `Union` 类型别名定义事件类型：

```python
@dataclass
class StreamText:
    text: str

@dataclass
class ToolResultEvent:
    tool_id: str
    tool_name: str
    output: str
    is_error: bool
    elapsed: float
```

12 种事件用 Union 类型别名汇总：

```python
AgentEvent = (
    StreamText | ThinkingText | RetryEvent
    | ToolUseEvent | ToolResultEvent | TurnComplete
    | LoopComplete | UsageEvent | ErrorEvent
    | PermissionRequest | CompactNotification | HookEvent
)
```

12 种事件覆盖 Agent Loop 的所有通知场景。 `CompactNotification` 额外携带了 `boundary` 字段（摘要 + 原文保留尾部），UI/session 层用它持久化压缩边界记录。 `HookEvent` 包含 Hook 的执行结果和成功状态，让 UI 可以精确展示 Hook 触发情况。

权限请求事件用 `asyncio.Future` 实现反向通信：

```python
@dataclass
class PermissionRequest:
    tool_name: str
    description: str
    future: asyncio.Future[PermissionResponse]
```

Agent 创建一个 Future，通过事件交给 UI，然后 `await future` 阻塞等待。UI 调 `future.set_result()` 写入用户选择。Future 只能 set 一次，语义上非常精确：一个权限请求就该只有一次回应。

Agent 和 UI 完全通过事件流解耦。Agent 不知道 UI 长什么样，UI 不知道 Agent 内部跑了几轮循环。

### StreamCollector：流消费器

抽出了一个专门的收集器来消费 LLM 流事件：

```python
class StreamCollector:
    def __init__(self) -> None:
        self.response = LLMResponse()

    async def consume(self, stream: AsyncIterator[StreamEvent]) -> AsyncIterator[AgentEvent]:
        async for event in stream:
            if isinstance(event, TextDelta):
                self.response.text += event.text
                yield StreamText(text=event.text)
            elif isinstance(event, ToolCallComplete):
                self.response.tool_calls.append(event)
                yield ToolUseEvent(...)
            elif isinstance(event, StreamEnd):
                self.response.stop_reason = event.stop_reason
```

`consume()` 是 async generator：接收 LLM 流式事件，内部做汇总（累积文本、收集工具调用），同时把转换后的 `AgentEvent` 往外 yield。主循环只需要 `async for event in collector.consume(llm_stream): yield event` 一行，流的读取逻辑和主循环彻底解耦。

## 主循环走读

### 入口：run()

```python
async def run(
    self, conversation: ConversationManager
) -> AsyncIterator[AgentEvent]:
    env_context = build_environment_context(
        self.work_dir, self.active_skills, ...)
    conversation.inject_environment(env_context)

    memory_content = (self.memory_manager.load()
        if self.memory_manager else "")
    conversation.inject_long_term_memory(
        self.instructions_content, memory_content)
```

`run()` 本身就是一个 async generator，调用方直接 `async for event in agent.run(conv)` 消费。async generator 天然就是惰性推送：消费者拉一个，生产者才产一个。不需要缓冲区管理，不需要操心生产和消费的速度差异。

进入循环之前，先做两件准备工作：把环境上下文和长期记忆注入对话，然后触发 session\_start Hook。

### 循环骨架

```python
while True:
    iteration += 1
    if iteration > self.max_iterations:
        yield ErrorEvent(...)
        break
    # 1. turn_start hook
    # 2. 消费通知队列
    # 3. 自动上下文压缩
    # 4. pre_send hook
    # 5. 构建系统提示词
    # 6. Plan Mode 注入
    # 7. 获取工具 schema，调 LLM
    # 8. 消费流式响应
    # 9. max_tokens 恢复
    # 10. 没有工具调用 → 结束
    # 11. 分批执行工具
    # 12. 连续未知工具检查
    # 13. turn_end hook
```

步骤不少，因为 在每个关键节点都穿插了 Hook 调用。turn\_start/turn\_end/pre\_send/post\_receive 四个事件点覆盖了 Agent Loop 的完整生命周期。

### 调用 LLM 和消费流式响应

```python
collector = StreamCollector()
llm_stream = self.client.stream(
    api_conv, system=system, tools=tools)
async for event in collector.consume(llm_stream):
    yield event

response = collector.response
```

只有四行。 `client.stream()` 返回 async iterator， `collector.consume()` 包装成另一个 async iterator，主循环 `async for` 消费并 yield 出去。整个流处理链是懒的：LLM 产一个 token → collector 收集 + 转换 → 主循环 yield → UI 消费。

流消费结束后， `collector.response` 里汇总好了完整的文本、工具调用列表、Token 用量。

在流消费完毕后再统一执行工具，而不是在流式阶段就提交。这让控制流更清晰：先完整消费 LLM 输出，汇总所有工具调用，然后一次性分批执行。牺牲了一些延迟（工具执行不能和 LLM 输出重叠），换来了更可预测的执行顺序和更简单的调试体验。

### 终止判断

```python
if not response.tool_calls:
    conversation.add_assistant_message(
        response.text, thinking_blocks=conv_thinking)
    self._loop_count += 1
    if (self._loop_count % MEMORY_EXTRACTION_INTERVAL == 0
        and self.memory_manager):
        asyncio.ensure_future(
            self._extract_memories(conversation))
    yield LoopComplete(total_turns=iteration)
    break
```

没有工具调用就结束循环。 `_loop_count` 每次循环正常结束时加 1，每 5 次（ `MEMORY_EXTRACTION_INTERVAL` ）触发一次异步记忆提取。 `asyncio.ensure_future` 是 fire-and-forget 方式，启动后台 coroutine 不等它完成，不阻塞主循环退出。

### 工具结果收集

```python
tool_uses = [
    ToolUseBlock(
        tool_use_id=tc.tool_id,
        tool_name=tc.tool_name,
        arguments=tc.arguments,
    )
    for tc in response.tool_calls
]
conversation.add_assistant_message(
    response.text, tool_uses, thinking_blocks=conv_thinking)

tool_results: list[ToolResultBlock] = []
batches = partition_tool_calls(response.tool_calls, self.registry)
```

先把 assistant 消息（包含工具调用声明）写入对话历史，然后把工具调用分批执行。截断策略分三级：

```python
def _maybe_persist_or_truncate(self, tool_use_id, text):
    if len(text) > SINGLE_RESULT_CHAR_LIMIT:
        fp = persist_tool_result(tool_use_id, text, self.session_dir)
        return make_persisted_preview(text, fp)
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n… (output truncated)"
    return text
```

特别大的输出持久化到磁盘文件，对话里只保留预览和文件路径。中等大小的截断。小输出原样保留。三级策略让上下文管理非常精细：超大输出不丢失（用 ReadFile 可以读回来），中等输出减负，小输出无损。

## 四个停止条件

### LLM 不再调用工具

就是上面那个 `if not response.tool_calls` 判断。async generator 走到 `break` ， `run()` 方法自然结束，调用方的 `async for` 也随之退出。

### 迭代次数上限

```python
if iteration > self.max_iterations:
    yield ErrorEvent(
        message=f"Agent reached maximum iterations "
                f"({self.max_iterations})")
    break
```

在循环最开头检查。默认 50 次。

### 连续未知工具

```python
if br.is_unknown:
    consecutive_unknown += 1
else:
    consecutive_unknown = 0
# ...
if consecutive_unknown >= 3:
    yield ErrorEvent(
        message="Agent terminated: "
            "too many consecutive unknown tool calls")
    break
```

连续 3 次调用不存在的工具就终止。中间有一次正常调用就重置计数。

### 用户取消

没有显式的 context 取消检查。async generator 有天然的取消机制：调用方只要停止迭代（break 出 `async for` 循环），generator 就会被垃圾回收，里面的循环自动终止。如果需要更主动的取消，上层代码可以 cancel 掉运行 `run()` 的 task。

## 工具执行

### 分批策略

在执行工具之前有一个显式的分批步骤：

```python
def partition_tool_calls(tool_calls, registry) -> list[ToolBatch]:
    batches: list[ToolBatch] = []
    for tc in tool_calls:
        tool = registry.get(tc.tool_name)
        safe = tool is not None and tool.is_concurrency_safe and registry.is_enabled(tc.tool_name)
        if safe and batches and batches[-1].concurrent:
            batches[-1].calls.append(tc)
        else:
            batches.append(ToolBatch(concurrent=safe, calls=[tc]))
    return batches
```

这个函数把工具调用序列切分成多个 batch。连续的「并发安全」工具合并成一个并发 batch，其他工具各自成为独立 batch。

比如 LLM 返回 `[Read, Read, Edit, Read, Read]` ，会被切成三个 batch： `[Read, Read]` （并发执行）→ `[Edit]` （串行执行）→ `[Read, Read]` （并发执行）。写操作不会和其他操作并行，避免竞态条件。读操作尽可能并行提速，写操作严格串行保安全。

### 并行执行

并发 batch 用 `asyncio.gather` 一次性并发执行：

```python
async def _execute_batch_parallel(
    self, calls: list[ToolCallComplete]
) -> list[_ToolExecResult]:
    tasks = [self._execute_single_tool_direct(tc)
             for tc in calls]
    return list(await asyncio.gather(*tasks))
```

`asyncio.gather` 同时启动所有 coroutine，等全部完成后一起返回。5 个 Read 调用在同一个事件循环里并发执行，IO 等待时间重叠。

主循环里的分派逻辑：

```python
for batch in batches:
    if batch.concurrent and len(batch.calls) > 1:
        batch_results = await self._execute_batch_parallel(
            batch.calls)
    else:
        for tc in batch.calls:
            async for item in self._execute_tool(tc):
                if isinstance(item, PermissionRequest):
                    yield item
                else:
                    result, elapsed, is_unknown = item
```

并发 batch 和串行 batch 走不同代码路径。并发路径调 `_execute_single_tool_direct` （直接执行），串行路径调 `_execute_tool` （完整的四关流程，包含权限检查和 Hook）。

### 单工具执行流程

`_execute_tool` 是一个 async generator，走完整的四关。

**第一关：查找工具**

```python
tool = self.registry.get(tc.tool_name)
if tool is None:
    result = ToolResult(
        output=f"Error: unknown tool '{tc.tool_name}'",
        is_error=True)
    is_unknown = True
    yield result, elapsed, is_unknown
    return
```

找不到就标记 `is_unknown` ，为连续未知工具检测提供依据。

**第二关：权限检查**

```python
if self.permission_checker:
    decision = self.permission_checker.check(tool, tc.arguments)
    if decision.effect == "deny":
        yield result, elapsed, is_unknown
        return
    if decision.effect == "ask":
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        yield PermissionRequest(
            tool_name=tc.tool_name,
            description=desc, future=future)
        response = await future
```

精妙之处在于 `_execute_tool` 是 async generator。需要请求权限时，它 yield 一个 `PermissionRequest` 出去，然后 `await future` 阻塞自己。主循环收到 yield 后再 yield 给 UI，UI 让用户选择，选完 `future.set_result()` 写回结果。Generator 恢复执行，继续后面的逻辑。

这种设计让控制流看起来像是线性的：yield 出权限请求 → await 用户回应 → 继续执行。async generator 天然支持「暂停等待外部输入后继续」的模式。

**第三关：Pre-tool Hook**

Hook 检查在主循环里，在调 `_execute_tool` 之前完成：

```python
if self.hook_engine:
    rejection = await self.hook_engine.run_pre_tool_hooks(hook_ctx)
    if rejection is not None:
        result = ToolResult(
            output=f"Hook rejected: {rejection.reason}",
            is_error=True)
```

把 Hook 拦截放在了 `_execute_tool` 的外面。 `_execute_tool` 只关心权限 + 执行，Hook 逻辑由主循环管理。

**第四关：真正执行**

```python
params = tool.params_model.model_validate(tc.arguments)
result = await tool.execute(params)
```

执行前做了一步显式参数校验：Pydantic 的 `model_validate` 校验 LLM 传来的参数是否符合工具定义的 schema。比起隐式的 JSON 反序列化，Pydantic 能给出更友好的错误信息，比如「参数 file\_path 缺失」而不是笼统的反序列化失败。

执行完后触发 post-tool Hook，计算执行耗时。

## 错误恢复与自愈

### 上下文过长恢复

上下文压缩集成在 `auto_compact` 函数里，每轮迭代开头调用：

```python
compact_result = await auto_compact(
    conversation, self.client, self.context_window,
    self.session_dir, protocol=self.protocol,
    breaker=self.compact_breaker,
    recovery=self.recovery_state,
    tool_schemas=self.registry.get_all_schemas(self.protocol),
    transcript_path=self._transcript_path)
if isinstance(compact_result, CompactEvent):
    yield CompactNotification(
        before_tokens=compact_result.before_tokens,
        message=f"上下文已压缩（压缩前 {compact_result.before_tokens:,} tokens）",
        boundary=compact_result.boundary)
```

当对话接近上下文窗口上限时， `auto_compact` 会把历史消息摘要化。 `compact_breaker` 是个熔断器，防止压缩反复失败时无限重试。压缩成功后需要重新注入环境上下文和长期记忆，因为它们可能在压缩过程中被摘要掉。

### 限流等待重试

限流处理隐含在 LLM 客户端层面。客户端内部检测到 429 状态码后会自动等待并重试。主循环不需要显式处理限流错误。

### 输出截断恢复（max\_tokens）

```python
if response.stop_reason == "max_tokens":
    if not max_tokens_escalated:
        self.client.set_max_output_tokens(MAX_TOKENS_CEILING)
        max_tokens_escalated = True
        if response.text:
            conversation.add_assistant_message(response.text, thinking_blocks=conv_thinking)
            conversation.add_user_message("Output token limit hit. Resume directly...")
        yield RetryEvent(reason="max_tokens escalation")
        continue
    elif output_recoveries < MAX_OUTPUT_TOKENS_RECOVERIES:
        output_recoveries += 1
        conversation.add_user_message("Break remaining work into smaller pieces.")
        yield RetryEvent(reason=f"max_tokens recovery {output_recoveries}/{MAX_OUTPUT_TOKENS_RECOVERIES}")
        continue
```

两阶段恢复。第一次截断：提升到 64000 上限，注入续写指令，重试。还不够就进入第二阶段：最多再重试 3 次，每次告诉 LLM 拆小。成功完成一轮（非 max\_tokens 停止）后 `output_recoveries` 重置为 0。

## Plan Mode

```python
if self.plan_mode:
    plan_path = str(self._get_plan_path())
    if self.permission_checker:
        self.permission_checker.plan_file_path = plan_path
    plan_exists = self._get_plan_path().exists()
    plan_reminder = build_plan_mode_reminder(
        plan_path, plan_exists, iteration)
    conversation.add_system_reminder(plan_reminder)
```

`plan_mode` 是一个 property，直接读权限模式的状态：

```python
@property
def plan_mode(self) -> bool:
    return self.permission_mode == PermissionMode.PLAN
```

核心思路是不改变循环结构，只在每轮注入一段 system-reminder。Plan 文件路径同步到权限检查器，让写 Plan 文件成为例外。提示词引导 LLM 自觉只做探索和规划，权限系统作为兜底拦截不听话的写操作。两层保障。

## 小结

| 设计决策      | 实现方式                                                                        |
| --------- | --------------------------------------------------------------------------- |
| 异步事件流     | async generator， `yield` 推送事件，调用方 `async for` 消费                            |
| 主循环       | `while True` + `break` 出口                                                   |
| 工具并行      | `partition_tool_calls` 分批 + `asyncio.gather` 并发执行读操作                        |
| 权限交互      | `asyncio.Future` ，generator yield 出 `PermissionRequest` ， `await future` 等待 |
| 流消费       | `StreamCollector` async generator，读 LLM 流同时 yield AgentEvent                |
| Plan Mode | 注入 system-reminder + 权限层拦截                                                  |
| 上下文保护     | 三级策略：磁盘持久化 / 截断 / 原样保留                                                      |
| 错误恢复      | 上下文接近上限时 auto\_compact + 熔断器防止死循环                                           |
| 输出截断恢复    | 两阶段：先提升上限到 64000，再分段续写（最多 3 次）                                              |
| 取消机制      | async generator 天然支持：调用方停止迭代即可                                              |
| 记忆提取      | `asyncio.ensure_future` fire-and-forget，每 5 次循环触发                           |
| 参数校验      | Pydantic `model_validate` ，显式校验每个字段                                         |


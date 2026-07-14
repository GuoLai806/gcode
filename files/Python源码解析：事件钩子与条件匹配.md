## 模块概览

Hook 系统的代码集中在 `gcode/hooks/` 目录下，按职责拆成了六个文件：

| 文件              | 职责                                               |
| --------------- | ------------------------------------------------ |
| `engine.py`     | 核心引擎。Hook 匹配、分发、pre-tool 拦截、通知收集                 |
| `models.py`     | 数据类型定义。Hook、Action、HookContext、ToolRejectedError |
| `loader.py`     | 配置加载与校验。把 YAML 原始数据转换成 Hook 对象                   |
| `executors.py`  | 四种动作执行器。command、prompt、http、agent                |
| `conditions.py` | 条件表达式解析和匹配。支持四种运算符和逻辑组合                          |
| `events.py`     | 生命周期事件枚举。StrEnum 定义所有合法的事件名                      |

模块划分很干净：models 定义数据结构，conditions 负责条件匹配，executors 负责动作执行，loader 负责配置校验，engine 把所有东西串起来。

## 核心类型

### 事件枚举

```python
class LifecycleEvent(StrEnum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    PRE_SEND = "pre_send"
    POST_RECEIVE = "post_receive"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ERROR = "error"
    COMPACT = "compact"
    PERMISSION_REQUEST = "permission_request"
    FILE_CHANGE = "file_change"
    COMMAND_EXECUTE = "command_execute"
```

定义了 15 种事件，分成五个层级。会话级的 `session_start` 和 `session_end` 。轮次级的 `turn_start` 和 `turn_end` 。工具级的 `pre_tool_use` 和 `post_tool_use` 。消息级的 `pre_send` 和 `post_receive` 。系统级的 `startup` 、 `shutdown` 、 `error` 、 `compact` 、 `permission_request` 、 `file_change` 、 `command_execute` 。

其中 `pre_tool_use` 最特殊，它是唯一能拦截工具执行的事件。

使用 `StrEnum` 而不是普通字符串常量，让 loader 在校验时可以用集合操作快速判断事件名是否合法：

```python
_VALID_EVENTS = {e.value for e in LifecycleEvent}
```

### 动作类型

通过执行器映射表定义了四种动作类型：

```python
_VALID_ACTION_TYPES = {"command", "prompt", "http", "agent"}
```

`command` 执行 shell 命令， `prompt` 注入提示词， `http` 发 HTTP 请求， `agent` 启动子 Agent。四种都有执行器实现，其中 `agent` 目前是占位 stub。

### Hook 结构体

```python
@dataclass
class Hook:
    id: str
    event: str
    action: Action
    condition: ConditionGroup | None = None
    reject: bool = False
    once: bool = False
    async_exec: bool = False
    executed: bool = False
```

一个 Hook 就是一条规则：在什么事件、满足什么条件时、执行什么动作。

`reject` 表示这个 Hook 触发后要拦截工具执行，只能用在 `pre_tool_use` 上。 `once` 表示只执行一次。 `async_exec` 表示异步执行不阻塞主流程（用 `async_exec` 而不是 `async` 是因为后者是 Python 关键字）。 `executed` 是运行时状态标记，配合 `once` 使用。

`should_run` 和 `mark_executed` 配合实现了「只跑一次」的语义：

```python
def should_run(self) -> bool:
    if self.once and self.executed:
        return False
    return True

def mark_executed(self) -> None:
    self.executed = True
```

`condition` 的类型是预解析好的 `ConditionGroup` ，不是原始字符串。这意味着条件解析只在配置加载时做一次，运行时直接求值，不需要每次都重新解析。

### Action 结构体

```python
@dataclass
class Action:
    type: str
    command: str = ""
    message: str = ""
    url: str = ""
    method: str = "POST"
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    timeout: int = 30
```

典型的「大 union」设计，不同 `type` 只用到部分字段。 `command` 类型用 `command` 字段， `prompt` 类型用 `message` ， `http` 类型用 `url` 、 `method` 、 `body` 、 `headers` ， `agent` 类型用 `prompt` 。 `timeout` 默认 30 秒，被 command 和 http 共用。

### HookContext：事件上下文

```python
@dataclass
class HookContext:
    event_name: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    file_path: str = ""
    message: str = ""
    error: str = ""
```

每次触发事件时，调用方把当前上下文打包成 HookContext。它有两个核心方法。

`get_field` 是条件匹配的入口，把字段名映射到具体的值：

```python
def get_field(self, name: str) -> str:
    if name == "tool":
        return self.tool_name
    if name == "event":
        return self.event_name
    if name.startswith("args."):
        key = name[5:]
        value = self.tool_args.get(key, "")
        return str(value) if value else ""
    return ""
```

`args.` 前缀让条件表达式能深入到工具参数层级，比如 `args.command` 能拿到 Bash 工具的具体命令内容。未知字段返回空字符串，不报错。

`expand` 做模板变量替换，把命令或消息模板里的 `$TOOL_NAME` 、 `$FILE_PATH` 替换成真实值：

```python
def expand(self, template: str) -> str:
    result = template
    result = result.replace("$EVENT", self.event_name)
    result = result.replace("$TOOL_NAME", self.tool_name)
    result = result.replace("$FILE_PATH", self.file_path)
    result = result.replace("$MESSAGE", self.message)
    result = result.replace("$ERROR", self.error)
    for key, value in self.tool_args.items():
        result = result.replace(
            f"$TOOL_ARGS.{key}", str(value))
    return result
```

用户配置 command 时写 `echo "$TOOL_NAME was called"` ，执行时会自动替换成真实的工具名。未定义的变量会被替换成空字符串，不会报错。

### HookResult 和 ToolRejectedError

```python
@dataclass
class ActionResult:
    output: str = ""
    success: bool = True
```

`ActionResult` 是动作执行器的返回值， `output` 是输出文本， `success` 标记是否成功。

```python
class ToolRejectedError(Exception):
    def __init__(self, tool: str, reason: str, hook_id: str):
        self.tool = tool
        self.reason = reason
        self.hook_id = hook_id
```

`ToolRejectedError` 是 Hook 系统唯一向外「冒泡」的异常。当 pre-tool Hook 拒绝了一个工具调用时，引擎构造这个错误返回给 Agent Loop，Agent Loop 把拒绝原因作为工具结果返回给 LLM。

## Engine：Hook 引擎

```python
class HookEngine:
    def __init__(self, hooks: list[Hook] | None = None):
        self.hooks: list[Hook] = hooks or []
        self._prompt_messages: list[str] = []
        self._notifications: list[HookNotification] = []
```

引擎维护三个列表。 `hooks` 存所有注册的规则。 `_prompt_messages` 收集 prompt 类型 Hook 的输出，等外部来取走注入到对话上下文。 `_notifications` 是通知队列，记录每条 Hook 的执行结果。

没有做并发保护（没有锁），因为 asyncio 是单线程事件循环，同一时刻只有一个协程在操作引擎状态。异步 Hook 虽然用 `ensure_future` 扔到后台，但最终也是在同一个事件循环里执行，不会产生竞态。

## 主流程走读：两条执行路径

### RunHooks：通用的 fire-and-forget

```python
async def run_hooks(self, event: str, ctx: HookContext):
    matched = self.find_matching_hooks(event, ctx)
    for hook in matched:
        hook.mark_executed()
        if hook.async_exec:
            asyncio.ensure_future(self._run_single(hook, ctx))
        else:
            await self._run_single(hook, ctx)
```

先用 `find_matching_hooks` 找到所有匹配的 Hook，然后逐个执行。标记了 `async_exec` 的用 `asyncio.ensure_future` 扔到后台，不等它跑完就继续下一个。

`find_matching_hooks` 有三层过滤：

```python
def find_matching_hooks(self, event: str, ctx: HookContext):
    matched: list[Hook] = []
    for hook in self.hooks:
        if hook.event != event:
            continue
        if not hook.should_run():
            continue
        if hook.condition is not None \
                and not hook.condition.evaluate(ctx):
            continue
        matched.append(hook)
    return matched
```

第一层按事件名过滤，第二层检查 `once` 标记（通过 `should_run` ），第三层做条件表达式求值。三层都通过才算匹配。

`_run_single` 负责执行单个 Hook 并收集结果：

```python
async def _run_single(self, hook: Hook, ctx: HookContext):
    try:
        result = await execute_action(hook.action, ctx)
        if hook.action.type == "prompt" and result.success:
            self._prompt_messages.append(result.output)
        self._notifications.append(HookNotification(...))
        if not result.success:
            log.warning("Hook '%s' action failed: %s",
                        hook.id, result.output)
    except Exception as e:
        log.warning("Hook '%s' execution error: %s",
                    hook.id, e)
```

如果 action 类型是 `prompt` 且执行成功，输出会被收集到 `_prompt_messages` 队列里。这是 prompt 类型 Hook 的特殊处理。

错误只记日志不中断，这体现了理论篇说的设计原则：Hook 是辅助机制，格式化失败了代码还在，通知没发出去工作成果不受影响。

### RunPreToolHooks：唯一能阻断执行的入口

```python
async def run_pre_tool_hooks(self, ctx: HookContext
) -> ToolRejectedError | None:
    matched = self.find_matching_hooks("pre_tool_use", ctx)
    for hook in matched:
        hook.mark_executed()
        try:
            result = await execute_action(hook.action, ctx)
            self._notifications.append(...)
            if hook.reject:
                return ToolRejectedError(tool=ctx.tool_name,
                    reason=result.output, hook_id=hook.id)
        except Exception as e:
            log.warning(...)
    return None
```

返回类型是 `ToolRejectedError | None` 。和 `run_hooks` 最大的区别在于：一旦某个 Hook 的 `reject` 为 true，立即构造 `ToolRejectedError` 返回，后续 Hook 不再执行。

注意 `reject` 判断放在 action 执行之后。也就是说，即使最终要拒绝工具调用，也会先跑一下 Hook 的动作（比如记录日志），然后用动作的输出作为拒绝原因传回给 LLM。

这里没有异步分支。pre\_tool\_use 必须同步等结果，否则工具调用已经开始了再拒绝没有意义。

## 条件匹配

### 条件解析

条件表达式在配置加载阶段就被解析成 `ConditionGroup` 结构，不是每次匹配时实时解析：

```python
def parse_condition(expr: str) -> ConditionGroup | None:
    if not expr or not expr.strip():
        return None
    has_and = "&&" in expr
    has_or = "||" in expr
    if has_and and has_or:
        raise ConditionParseError(
            "Cannot mix '&&' and '||'...")
    if has_and:
        parts, logic = expr.split("&&"), "and"
    elif has_or:
        parts, logic = expr.split("||"), "or"
    else:
        parts, logic = [expr], "and"
    conditions = [_parse_single(p) for p in parts]
    return ConditionGroup(conditions=conditions, logic=logic)
```

先检查是否混用了 `&&` 和 `||` ，混用直接报错。这是有意为之：一旦允许混用就要处理优先级和括号，解析器的复杂度会飙升。Hook 条件不是编程语言，简单的逻辑组合够用了。如果真需要复杂条件，拆成多个 Hook 更清晰。

然后按 `&&` 或 `||` 拆分成多个子条件，每个子条件解析成 `Condition` 对象。

### 叶子条件求值

```python
_OPERATORS = ("==", "!=", "=~", "~=")

def _parse_single(expr: str) -> Condition:
    expr = expr.strip()
    for op in _OPERATORS:
        idx = expr.find(op)
        if idx == -1:
            continue
        field_part = expr[:idx].strip()
        value_part = expr[idx + len(op):].strip()
        if value_part.startswith('"') and value_part.endswith('"'):
            value_part = value_part[1:-1]
        return Condition(field=field_part, operator=op, value=value_part)
    raise ConditionParseError(...)
```

遍历四种运算符找到第一个匹配的，然后按运算符位置拆分成左值（字段名）和右值（比较值）。

求值逻辑在 `Condition.evaluate` 里：

```python
def evaluate(self, ctx: HookContext) -> bool:
    field_value = ctx.get_field(self.field)
    if self.operator == "==":
        return field_value == self.value
    if self.operator == "!=":
        return field_value != self.value
    if self.operator == "=~":
        pattern = self.value
        if pattern.startswith("/") and pattern.endswith("/"):
            pattern = pattern[1:-1]
        return bool(re.search(pattern, field_value))
    if self.operator == "~=":
        return fnmatch.fnmatch(field_value, self.value)
    return False
```

四种运算符各走一条分支。 `=~` 正则匹配支持 `/pattern/` 写法，解析前去掉斜杠。正则语法错误时默认返回 `False` ，防御性编程。 `~=` 用标准库的 `fnmatch` 做 glob 匹配。

组合条件的求值在 `ConditionGroup` 里：

```python
@dataclass
class ConditionGroup:
    conditions: list[Condition] = field(default_factory=list)
    logic: str = "and"

    def evaluate(self, ctx: HookContext) -> bool:
        if not self.conditions:
            return True
        if self.logic == "and":
            return all(c.evaluate(ctx) for c in self.conditions)
        return any(c.evaluate(ctx) for c in self.conditions)
```

`and` 模式要求所有子条件通过， `or` 模式任一通过即可。用 `all` 和 `any` 一行搞定，表达力在这里体现得很好。

## 四种动作执行器

四种动作类型通过一个分发表路由：

```python
_EXECUTOR_MAP = {
    "command": execute_command,
    "prompt": execute_prompt,
    "http": execute_http,
    "agent": execute_agent,
}

async def execute_action(action: Action, ctx: HookContext):
    executor = _EXECUTOR_MAP.get(action.type)
    if executor is None:
        return ActionResult(
            output=f"Unknown action type: {action.type}",
            success=False)
    return await executor(action, ctx)
```

字典映射做分发，策略模式。添加新的动作类型只需要往表里加一行。

### command：执行 shell 命令

```python
async def execute_command(action: Action, ctx: HookContext):
    command = ctx.expand(action.command)
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=action.timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ActionResult(
            output=f"Command timed out after {action.timeout}s",
            success=False)
```

先用 `ctx.expand` 做模板变量替换，然后用 `asyncio.create_subprocess_shell` 启动子进程。stderr 合并到 stdout（ `STDOUT` 参数），只需要处理一个输出流。

超时处理是亮点：用 `asyncio.wait_for` 包装 `communicate()` ，超时后先 `proc.kill()` 再 `await proc.wait()` 确保进程真的退出了。如果只 kill 不 wait，可能留下僵尸进程。

返回码判断成功失败： `proc.returncode == 0` 为成功。

### prompt：注入提示词

```python
async def execute_prompt(action: Action, ctx: HookContext):
    message = ctx.expand(action.message)
    return ActionResult(output=message, success=True)
```

最简单的执行器。只做模板展开，返回消息文本。这个消息会被引擎收集到 `_prompt_messages` 里，后续以 system reminder 的形式注入到对话上下文中。

### http：发 HTTP 请求

```python
async def execute_http(action: Action, ctx: HookContext):
    url = ctx.expand(action.url)
    body = ctx.expand(action.body) if action.body else None

    def _do_request() -> ActionResult:
        req = Request(url, data=data, headers=headers,
                      method=method)
        with urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode(
                errors="replace")[:500]
            return ActionResult(
                output=f"HTTP {resp.status}: {resp_body}",
                success=200 <= resp.status < 300)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_request)
```

用标准库的 `urllib` 发请求。因为 `urlopen` 是阻塞调用，用 `run_in_executor` 丢到线程池里执行，不会阻塞事件循环。响应体截断到 500 字符，防止超大响应撑爆内存。

如果用户没设 `Content-Type` ，有 body 时自动加 `application/json` 。header 里的值也会做模板展开。

### agent：启动子 Agent（预留）

```python
async def execute_agent(action: Action, ctx: HookContext):
    log.info("Agent executor stub called with prompt: %s",
             prompt[:100])
    return ActionResult(
        output="agent executor not yet implemented",
        success=True)
```

目前只是占位 stub。接口已经定义好了，等下一章 SubAgent 实现后再对接真正的运行时。返回 `success=True` 是为了不触发错误日志。

## 通知机制

引擎有两个队列分别服务不同的消费场景：

```python
def get_prompt_messages(self) -> list[str]:
    messages = list(self._prompt_messages)
    self._prompt_messages.clear()
    return messages

def drain_notifications(self) -> list[HookNotification]:
    notifications = list(self._notifications)
    self._notifications.clear()
    return notifications
```

`_prompt_messages` 专门收集 prompt 类型 Hook 的输出，Agent Loop 每轮迭代前取走这些消息，注入到 system prompt 区域。 `_notifications` 收集所有 Hook 的执行结果，用于日志、调试、状态展示。

两个队列都是「取走就清空」的一次性消费模式。Hook 执行的时机和模型感知时机是解耦的： `post_tool_use` 的 Hook 在工具执行后立刻跑，但 prompt 输出要等到下一轮对话开始时模型才能读到。

## 配置加载与校验

`loader.py` 负责把 YAML 原始数据转换成 Hook 对象，过程中做严格的校验：

```python
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "command": ["command"],
    "prompt": ["message"],
    "http": ["url"],
    "agent": ["prompt"],
}
```

每种 action 类型有不同的必填字段，用映射表驱动校验，不需要写一堆 if-else。

有两条关键的互斥约束：

```python
if reject and event != "pre_tool_use":
    raise HookConfigError(
        f"{label}: 'reject' can only be used with "
        f"'pre_tool_use' event")

if async_exec and event == "pre_tool_use":
    raise HookConfigError(
        f"{label}: 'async' cannot be used with "
        f"'pre_tool_use' event")
```

`reject` 只能用在 `pre_tool_use` 上，因为只有工具执行前才有「拦截」的语义。 `async` 不能和 `pre_tool_use` 一起用，因为拦截必须等结果。这两条规则在加载阶段就校验，fail-fast，不等到运行时才报错。

条件表达式也在加载时预解析成 `ConditionGroup` ：

```python
if raw_if:
    try:
        condition = parse_condition(str(raw_if))
    except ConditionParseError as e:
        raise HookConfigError(
            f"{label}: condition error: {e}") from e
```

解析失败直接抛异常，带上 hook ID 定位问题。

## 与 Agent Loop 的集成

Agent Loop 在关键位置调用引擎的方法：

`session_start` 和 `session_end` 在会话的开始和结束时触发。 `turn_start` 和 `turn_end` 在每轮对话的开始和结束时触发。 `pre_send` 在消息发送给 LLM 之前， `post_receive` 在收到 LLM 响应之后。

工具执行前调用 `run_pre_tool_hooks` ：

```python
err = await self.hooks.run_pre_tool_hooks(ctx)
if isinstance(err, ToolRejectedError):
    # 跳过工具执行，把拒绝原因作为 tool_result 返回给 LLM
```

返回 `ToolRejectedError` 则跳过工具执行，拒绝原因作为错误结果返回。LLM 看到后可以调整策略。返回 `None` 则正常执行工具。

每轮对话开始前，取走 prompt 消息注入上下文：

```python
for msg in self.hooks.get_prompt_messages():
    # 作为 system reminder 注入
```

## 小结

| 设计决策    | 实现方式                                                 |
| ------- | ---------------------------------------------------- |
| 事件系统    | StrEnum 定义 15 种生命周期事件                                |
| 条件语法    | 预解析成 ConditionGroup，四种运算符， `&&` /\`                  |
| 动作分发    | 字典映射 `_EXECUTOR_MAP` ，策略模式                           |
| 阻断能力    | `run_pre_tool_hooks` 返回 `ToolRejectedError`          |
| 异步执行    | `asyncio.ensure_future` 扔到后台                         |
| once 追踪 | `should_run` + `mark_executed` ，dataclass 内部布尔标记     |
| 命令超时    | `asyncio.wait_for` + `proc.kill()` + `proc.wait()`   |
| HTTP 请求 | `run_in_executor` 包装阻塞的 `urlopen`                    |
| 通知机制    | 双队列： `_prompt_messages` 和 `_notifications` ，取走即清空    |
| 模板展开    | `HookContext.expand` 做 `$EVENT` 、 `$TOOL_NAME` 等变量替换 |
| 配置校验    | Loader 层 fail-fast， `reject` / `async` 互斥校验，条件预解析    |
| 依赖隔离    | agent executor 为 stub，等 SubAgent 实现后对接               |


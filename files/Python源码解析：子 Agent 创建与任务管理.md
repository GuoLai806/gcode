## 模块概览

SubAgent 系统的代码按职责拆成了以下文件：

| 文件                       | 职责                                          |
| ------------------------ | ------------------------------------------- |
| `agents/parser.py`       | AgentDef dataclass、YAML frontmatter 解析、字段校验 |
| `agents/loader.py`       | AgentLoader，三级加载 + 热重载                      |
| `agents/tool_filter.py`  | 工具过滤，含 teammate 和 coordinator 过滤            |
| `agents/fork.py`         | Fork 对话构建、嵌套检测                              |
| `agents/task_manager.py` | TaskManager，asyncio.Task 驱动的后台任务管理          |
| `agents/notification.py` | 任务完成通知格式化和注入                                |
| `agents/trace.py`        | TraceManager，父子 Agent 调用链追踪                 |
| `tools/agent_tool.py`    | AgentTool，execute 入口、路径分发、模型选择、worktree 隔离  |

拆分粒度比较细，Fork、通知、追踪各自独立成文件，职责清晰。

## 核心类型

### AgentDef：Agent 蓝图

用 `@dataclass` 定义 Agent 的元信息，在 `parser.py` 里：

```python
@dataclass
class AgentDef:
    agent_type: str          # YAML 里的 name
    when_to_use: str         # YAML 里的 description
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)        # 白名单
    disallowed_tools: list[str] = field(default_factory=list)  # 黑名单
    model: str = "inherit"
    max_turns: int = 200     # 未指定时默认 200
    permission_mode: str = "default"
    background: bool = False
    isolation: str = ""      # 空字符串或 "worktree"
    file_path: Path | None = None
    source: str = "builtin"
```

字段名用 snake\_case 风格。YAML frontmatter 里写的 `name` 和 `description` ，解析后映射成 `agent_type` 和 `when_to_use` 。 `tools` 和 `disallowed_tools` 分别是白名单和黑名单，两者配合使用：先用黑名单排除，再用白名单取交集。 `model` 默认 `"inherit"` ，不指定就继承父 Agent。

### SubAgentSpec / 运行时配置

没有单独的「运行时配置」结构。 `AgentDef` 既是加载产物也是运行时配置，简化了代码。代价是 `file_path` 、 `source` 这些加载时元信息会一直跟着走。

### 内置 Agent 常量

内置 Agent 做成了真正的 Markdown 文件，放在 `gcode/agents/builtins/` 目录下，用 `importlib.resources` 从 package 里加载，格式和用户自定义 Agent 完全一致。

三个核心内置 Agent 的配置差异：

* **general-purpose&#x20;**：不限制工具（ `disallowedTools` 为空），默认模型 inherit，是「全能选手」。

* **Plan&#x20;**：禁用 `Agent` 、 `EditFile` 、 `WriteFile` 、 `NotebookEdit` 四个工具，加上 `maxTurns: 15` 。system prompt 里也写了「严禁：创建文件、修改文件」，工具黑名单和提示词双重保障。

* **Explore&#x20;**：禁用 `EditFile` 、 `WriteFile` ，指定 `model: haiku` 用小模型跑，降低搜索成本。

还有一个 Verification Agent，通过 `enable_verification` 参数控制是否加载。

### TaskManager / 后台任务管理

后台任务管理在 `task_manager.py` ，用 asyncio 原生能力驱动：

```python
@dataclass
class BackgroundTask:
    id: str
    name: str
    agent: Agent
    task: str
    status: str = "running"  # running → completed / failed / cancelled
    result: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    cancel: Callable[[], None] | None = None
    progress: ProgressInfo = field(default_factory=ProgressInfo)
```

状态机很直白：创建时就是 `running` ，正常完成变 `completed` ，异常变 `failed` ，被取消变 `cancelled` 。

`TaskManager` 用 `asyncio.Queue` 做通知队列。子 Agent 完成后 `await self._notify_queue.put(task_id)` 把 ID 推进队列，父 Agent 在主循环里通过 `poll_completed` 非阻塞地取走。 `asyncio.Queue` 本身是协程安全的，不需要额外加锁。通知格式化逻辑在 `notification.py` ，用 `<task-notification>` 标签包裹结果、耗时和 token 统计，超过 5000 字符会截断。

取消用 `asyncio.Task.cancel()` ，后台协程收到 `CancelledError` 后在 except 分支里设状态为 `cancelled` 。

## Agent 定义的加载

### 三级加载优先级

`load_all` 按「项目 → 用户 → 内置」的顺序扫描，用「先到先得」的去重：

```python
def load_all(self) -> dict[str, AgentDef]:
    seen: dict[str, AgentDef] = {}
    # 优先级 1：项目级（最高）
    for agent_def in self._scan_directory(project_path, "project"):
        if agent_def.agent_type not in seen:
            seen[agent_def.agent_type] = agent_def
    # 优先级 2：用户级
    for agent_def in self._scan_directory(user_path, "user"):
        if agent_def.agent_type not in seen:
            seen[agent_def.agent_type] = agent_def
    # 优先级 3：内置
    for agent_def in self._load_builtins():
        if agent_def.agent_type not in seen:
            seen[agent_def.agent_type] = agent_def
```

先扫项目目录，已存在的名字不再覆盖，效果是项目级优先级最高。你在项目里放一个同名的 `plan.md` ，就能覆盖内置的 Plan Agent。

### 定义文件的解析

`parse_agent_file` 先调 `parse_frontmatter` 拆分 YAML 和 body，再调 `_validate_agent_meta` 校验。解析流程：检测开头 `---` → 找到结束 `---` → 中间部分用 `yaml.safe_load` 解析 → 剩余部分作为 `system_prompt` 。

校验逻辑： `name` 和 `description` 是必填字段，缺了直接报错。 `permissionMode` 只允许 `default` 、 `acceptEdits` 、 `bypassPermissions` 。 `maxTurns` 必须是正整数。 `isolation` 只允许空字符串和 `worktree` 。model 字段不做白名单限制，第三方模型名称可以直通，只做 `inherit` 的大小写归一化。

没有 frontmatter 的文件直接报错： `Missing YAML frontmatter` ，要求比较严格。

body 部分还会调 `process_includes` 展开 `@include` 指令，支持从外部文件引入 system prompt 片段。

### 热重载（如果实现了）

`get` 方法里实现了热重载。每次获取定义时，如果文件路径存在，就重新解析：

```python
def get(self, agent_type: str) -> AgentDef | None:
    cached = self._agents.get(agent_type)
    if cached is None:
        return None
    if cached.file_path is not None and cached.file_path.exists():
        try:
            reloaded = parse_agent_file(cached.file_path)
            reloaded.source = cached.source
            self._agents[agent_type] = reloaded
            return reloaded
        except AgentParseError:
            log.warning("Hot reload failed, using cached")
    return cached
```

粒度是单个 Agent 定义。热重载失败时回退到缓存版本，不影响系统运行。内置 Agent 的 `file_path` 是 `None` ，不会触发热重载。

## 两种创建模式

### Definition-based：预定义专家

定义式路径在 `agent_tool.py` 的 `execute` 方法里。通过 `AgentLoader.get` 获取定义，创建全新的 `ConversationManager` ，注入 system prompt 和任务描述，再用 `resolve_agent_tools` 过滤工具，最后创建子 Agent 实例。子 Agent 从空白对话开始，不知道父 Agent 之前在做什么。

### Fork-based：继承上下文的临时助手

Fork 逻辑独立在 `fork.py` 。 `build_forked_messages` 负责构建 Fork 对话：

```python
def build_forked_messages(
    conversation: ConversationManager, task: str,
) -> ConversationManager:
    # 嵌套检测：扫描历史消息中的标签
    for msg in conversation.history:
        if FORK_BOILERPLATE_TAG in msg.content:
            raise ForkError("Cannot fork from a forked agent.")
    # 深拷贝父对话
    fork_conv = ConversationManager()
    fork_conv.history = copy.deepcopy(conversation.history)
```

嵌套检测通过扫描消息里的 `<fork_boilerplate>` 标签实现。深拷贝用 `copy.deepcopy` ，保证子 Agent 的修改不会影响父对话。

未完成的 tool\_use 会补上占位 `ToolResultBlock` ，内容是简短的 `"interrupted"` 。最后注入 Fork Boilerplate 和任务描述。Boilerplate 约束了五条规则：不能再 Fork、不要对话提问、直接用工具、限定范围、报告控制在 500 字以内。

在 `execute` 方法里，Fork 会创建一个 `permission_mode="bypassPermissions"` 的临时 AgentDef，并且 Fork 总是后台运行。

## 工具过滤

### 多层过滤模型

`resolve_agent_tools` 在 `tool_filter.py` 里，实现了五层过滤：

```python
def resolve_agent_tools(parent_registry, definition, is_background=False):
    # 第 0 层：MCP 工具直通（mcp__ 前缀跳过所有过滤）
    mcp_tools = {n: t for n, t in all_tools.items() if _is_mcp_tool(n)}
    all_tools = {n: t for n, t in all_tools.items() if not _is_mcp_tool(n)}
    # 第 1 层：全局禁用（7 个工具）
    for name in ALL_AGENT_DISALLOWED_TOOLS:
        all_tools.pop(name, None)
    # 第 2 层：自定义 agent 额外限制
    if definition.source in ("project", "user", "plugin"):
        for name in CUSTOM_AGENT_DISALLOWED_TOOLS:
            all_tools.pop(name, None)
```

全局禁用的 7 个工具是： `TaskOutput` 、 `ExitPlanMode` 、 `EnterPlanMode` 、 `Agent` 、 `AskUserQuestion` 、 `TaskStop` 、 `Workflow` 。禁 `Agent` 是为了防止子 Agent 无限嵌套。

第 3 层是后台任务白名单， `ASYNC_AGENT_ALLOWED_TOOLS` 包含 16 个工具，涵盖文件读写、搜索、编辑、Bash 等基础能力。第 4 层是定义级黑名单和白名单，先从剩余工具里去掉 `disallowedTools` ，再用 `tools` 白名单取交集。

每层只能缩小工具集，不能扩大。MCP 工具在最开始就被分离出来，最后原样合并回去，不受任何过滤层影响。

还有 `build_teammate_tools` 给团队成员构建工具集，会额外注入 `SendMessage` 、 `TaskCreate` 等协调工具。 `IN_PROCESS_TEAMMATE_ALLOWED_TOOLS` 在异步白名单基础上加了协调工具和 Cron 工具。

## 执行路径

### execute 入口的分发逻辑

`AgentTool.execute` 是所有 SubAgent 请求的入口，分发优先级：

```python
async def execute(self, params: BaseModel) -> ToolResult:
    p: AgentToolParams = params
    # 路径 1：team_name 存在 → 走 teammate 路径
    if p.team_name:
        return await self._execute_as_teammate(p)
    # 路径 2：定义里有 worktree 隔离 → 走 worktree 路径
    if isolation == "worktree":
        return await self._execute_with_worktree(p)
    # 路径 3：subagent_type 为空 → 走 Fork
    # 路径 4：subagent_type 存在 → 走定义式（sync/async）
```

四条路径按优先级：team\_name → worktree 隔离 → subagent\_type 为空走 Fork → 定义式 sync/async。

### 前台同步执行

前台同步是最简单的路径，直接 `await` 子 Agent 的 `run_to_completion` ：

```python
# 前台同步执行
try:
    if is_fork:
        result_text = await sub_agent.run_to_completion("", conversation)
    else:
        result_text = await sub_agent.run_to_completion(p.prompt)
except Exception as e:
    self._trace_manager.complete(trace_node.agent_id, "failed")
    return ToolResult(output=f"Sub-agent failed: {e}", is_error=True)
```

完成后更新 trace 节点的 token 统计，标记为 `completed` 。

### 后台异步执行

`TaskManager.launch` 用 `asyncio.create_task` 启动后台协程：

```python
def launch(self, agent, task, name="", fork_conversation=None):
    task_id = uuid.uuid4().hex[:8]
    bg = BackgroundTask(id=task_id, name=name or task_id,
                        agent=agent, task=task)
    self._tasks[task_id] = bg
    async_task = asyncio.create_task(
        self._run_background(task_id, fork_conversation))
    self._async_tasks[task_id] = async_task
    bg.cancel = async_task.cancel
    return task_id
```

立即返回 task ID，不等待完成。 `_run_background` 是后台协程主体，完成后把 token 统计写入 `progress` ，再通过 `_notify_queue.put` 推送通知。

还有 `adopt_running` 方法处理前台到后台的切换，把已有的 Agent 实例包装成 `BackgroundTask` ，启动新的 asyncio task 继续执行。

### Fork 执行

Fork 调用 `build_forked_messages` 构建对话后，把 `fork_conversation` 传给 `TaskManager.launch` 。Fork 总是后台运行，因为在 execute 方法里，检测到 `enable_fork` 时会强制设 `is_background = True` 。Fork 构建的临时 AgentDef 的 `permission_mode` 设为 `bypassPermissions` ，跳过权限确认。

### Worktree 隔离执行

`_execute_with_worktree` 的流程：创建 worktree → 构建 worktree 上下文通知 → 设置工作目录为 worktree 路径 → 同步执行子 Agent → 自动清理。

```python
wt = await self._worktree_manager.create(wt_name, "HEAD")
notice = build_worktree_notice(self._parent_agent.work_dir, wt.path)
task = notice + "\n\n" + p.prompt
# ... 创建子 agent，work_dir 设为 wt.path ...
result_text = await sub_agent.run_to_completion(task)
cleanup = await self._worktree_manager.auto_cleanup(wt_name, wt.head_commit)
if cleanup.kept:
    result_text += f"\n[Worktree preserved at {cleanup.path}]"
```

自动清理策略：如果 worktree 里没有新提交（HEAD 没变），就删掉；有变更则保留，把分支名附在结果里返回。权限沙箱也会限定到 worktree 路径。

## 模型选择

`_select_llm` 方法实现三级优先级：

```python
def _select_llm(self, params, definition):
    model_override = params.model or (
        definition.model if definition.model != "inherit" else None
    )
    if model_override and model_override != "inherit":
        client = self._create_client_for_model(model_override)
        if client is not None:
            return client
    return self._parent_agent.client  # 继承父 Agent
```

调用参数级 > 定义级 > 继承父 Agent。 `"inherit"` 的语义是不做覆盖，直接用父 Agent 的客户端。 `_create_client_for_model` 维护了一个别名映射表， `haiku` 、 `sonnet` 、 `opus` 会映射到具体的模型 ID，其他字符串直通。

## 动态 Schema 生成

`AgentTool` 的 schema 里 `subagent_type` 字段的 enum 列表从 `AgentLoader.list_agents()` 动态获取，LLM 看到的可选值会随着用户自定义 Agent 的增减而变化。Agent 工具默认通过 deferred 机制延迟加载，不会出现在初始工具列表里，等 LLM 明确需要时才展开完整 schema。

## 小结

| 设计决策        | 实现方式                                                       |
| ----------- | ---------------------------------------------------------- |
| Agent 定义格式  | Markdown + YAML frontmatter， `parse_agent_file` 解析         |
| 定义类型        | 单一 `AgentDef` dataclass，加载产物和运行时配置不分离                      |
| 三层加载        | 项目 → 用户 → 内置（先到先得），项目级优先级最高                                |
| 内置 Agent 存储 | Markdown 文件（ `builtins/*.md` ），通过 `importlib.resources` 加载 |
| 上下文隔离       | Definition 模式全新对话，Fork 模式 `deepcopy` + 补占位 result          |
| 工具过滤层数      | 五层（MCP 直通 → 全局禁用 → 自定义禁用 → 异步白名单 → 定义级黑白名单）                |
| 后台任务机制      | TaskManager + `asyncio.Queue` 推模式通知                        |
| 异步并发        | `asyncio.create_task`                                      |
| 热重载         | `get` 时重新解析文件，失败回退缓存                                       |
| 执行分发路径      | team → worktree → fork → 定义式 sync/async                    |
| 文件隔离        | 可选 worktree，无变更自动清理，有变更保留分支                                |


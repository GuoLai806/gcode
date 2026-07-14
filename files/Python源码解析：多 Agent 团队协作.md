## 模块概览

| 文件                   | 职责                                            |
| -------------------- | --------------------------------------------- |
| `models.py`          | TeammateInfo / AgentTeam 数据类，团队目录解析，配置持久化     |
| `manager.py`         | TeamManager：团队生命周期、成员注册、Lead 邮箱消费             |
| `mailbox.py`         | Mailbox：单文件 JSON 存储 + 文件锁并发控制                 |
| `backend_detect.py`  | 后端自动检测                                        |
| `spawn_inprocess.py` | In-process 后端：asyncio.create\_task 启动 + 队友主循环 |
| `spawn_tmux.py`      | Tmux 后端：new-window 启动，CLI 命令构建                |
| `spawn_iterm2.py`    | iTerm2 后端：it2 CLI                             |
| `coordinator.py`     | Coordinator 模式系统提示词 + 激活条件                    |
| `registry.py`        | AgentNameRegistry 全局单例，name ↔ agent\_id 映射    |
| `shared_task.py`     | 共享任务存储，含依赖关系                                  |
| `transcript.py`      | 对话记录序列化/反序列化                                  |
| `progress.py`        | 队友进度追踪：工具使用计数、token 消耗、spinner 动词             |

架构分层清晰： `models.py` 定义数据结构， `manager.py` 做生命周期管理， `mailbox.py` 管通信， `spawn_*.py` 做后端适配， `coordinator.py` 管 Lead 的权限约束。

## 核心类型

### TeammateInfo

```python
@dataclass
class TeammateInfo:
    name: str
    agent_id: str
    agent_type: str
    model: str
    worktree_path: str
    backend_type: str        # BackendType 的值
    is_active: bool | None = None
    progress: Optional[TeammateProgress] = None
```

`is_active` 是三态： `None` 表示刚注册还没开始工作， `True` 表示活跃， `False` 表示空闲。 `progress` 是运行时字段，不参与序列化， `to_dict` 方法里手动排除了它。In-process 模式下 `progress` 会被赋值，pane 模式下为 None。

### AgentTeam

```python
@dataclass
class AgentTeam:
    name: str
    lead_agent_id: str
    members: list[TeammateInfo] = field(default_factory=list)
    config_path: str = ""
    description: str = ""
```

`members` 用列表存储，查找通过 `get_member` 遍历匹配 name 或 agent\_id。团队配置持久化到 `~/.gcode/teams/{name}/config.json` ， `save` 直接写 JSON， `load` 从磁盘恢复。mailbox 目录在同级的 `mailbox/` 子目录下。

### TeamManager

```python
class TeamManager:
    def __init__(self, worktree_manager=None, trace_manager=None):
        self._teams: dict[str, AgentTeam] = {}
        self._task_stores: dict[str, SharedTaskStore] = {}
        self._mailboxes: dict[str, Mailbox] = {}
        self._inprocess_handles: dict[str, InProcessTeammateHandle] = {}
        self._pane_ids: dict[str, str] = {}
        self._teammate_team_map: dict[str, str] = {}
```

多个字典管理不同维度的状态。 `_inprocess_handles` 和 `_pane_ids` 按 agent\_id 索引运行时句柄，分别对应两种后端。 `_teammate_team_map` 维护 agent\_id → team\_name 的反向映射，让 `on_teammate_completed` 能快速定位队友所在的团队。

## 三种执行后端

### detectBackend：自动选择

```python
def detect_backend(teammate_mode="", is_interactive=True):
    return BackendType.IN_PROCESS  # 默认 in-process

def detect_pane_backend(teammate_mode="", is_interactive=True):
    if teammate_mode == "in-process" or not is_interactive:
        return BackendType.IN_PROCESS
    if _in_tmux_session(): return BackendType.TMUX
    if _in_iterm2() and _it2_available(): return BackendType.ITERM2
    if _tmux_installed(): return BackendType.TMUX
    return BackendType.IN_PROCESS  # 兜底
```

两个函数，两套策略。 `detect_backend` 无条件返回 in-process，因为它能实时追踪进度。 `detect_pane_backend` 是需要外部终端时的检测逻辑：先查 `TMUX` 环境变量，再查 `TERM_PROGRAM` 是否为 iTerm.app 且 `it2` 可执行，再看 tmux 是否已安装。都不满足就静默回退到 in-process，不抛异常。

### Tmux 后端

```python
def spawn_tmux_teammate(team_name, teammate_name, worktree_path, prompt, ...):
    window_name = f"{team_name}-{teammate_name}"
    cli_cmd = build_cli_command(
        team_name=team_name, teammate_name=teammate_name,
        worktree_path=worktree_path, prompt=prompt, ...
    )
    # -d 后台创建不切焦点，-n 设置窗口名
    _run_tmux("new-window", "-d", "-n", window_name, cli_cmd)
    return TmuxPaneInfo(pane_id=window_name, session=team_name)
```

每个队友一个独立 tmux window，窗口名是 `{teamName}-{memberName}` ，方便后续 `kill-pane -t` 定位清理。CLI 命令通过 `build_cli_command` 构建，用环境变量注入团队名和队友名，prompt 里的单引号用 `'\\''` 转义。

### iTerm2 后端

```python
def spawn_iterm2_teammate(team_name, teammate_name, ...):
    cli_cmd = build_cli_command(...)  # 复用 tmux 的命令构建
    session_id = _run_it2("split-pane", "--command",
                          f"/bin/zsh -c '{cli_cmd}'")
```

用 `it2` CLI 而非 AppleScript。命令构建逻辑直接复用 `spawn_tmux.build_cli_command` ，只是启动方式换成 `it2 split-pane` 。

### In-process 后端

```python
def spawn_inprocess_teammate(agent, prompt, name, ...):
    progress = TeammateProgress(name=name, team_name=team_name,
                                spinner_verb=random_verb())
    async def _run():
        # 队友主循环在这里，后面单独讲
        ...
    task = asyncio.create_task(_run(), name=f"teammate-{name}")
    return InProcessTeammateHandle(agent=agent, task=task, ...)
```

用 `asyncio.create_task` 启动后台协程。 `InProcessTeammateHandle` 包装 asyncio Task，提供 `done` 、 `result` 、 `cancel` 属性。和外部后端的关键区别：共享进程，生命周期绑定在 Lead 上。但通信仍然走 Mailbox 文件，保持和外部后端一致的接口。

## FileMailBox：跨进程通信

### 数据结构

```python
@dataclass
class MailboxMessage:
    id: str
    from_agent: str
    to_agent: str
    content: str
    summary: str = ""
    message_type: str = "text"  # text | shutdown_request | shutdown_response
    timestamp: float = 0.0
    read: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
```

`message_type` 支持三种：普通文本、关闭请求、关闭响应。 `summary` 用于 UI 预览。 `read` 标记已读状态。

### 存储格式

每个收件人一个 JSON 文件 `{agent_id}.json` ，内容是消息数组。写入时追加到数组末尾，消费时标记 `read = True` 。这和「每消息一文件」不同，选择了单文件方案，需要文件锁来保证并发安全。

### 文件锁机制

```python
def _with_lock(self, agent_id, fn):
    lock_file = self._lock_path(agent_id)
    for _ in range(10):  # 最多重试 10 次
        try:
            # O_CREAT | O_EXCL 原子创建，文件已存在则失败
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            # 超过 10 秒的锁视为 stale，强制删除
            if time.time() - lock_file.stat().st_mtime > 10:
                lock_file.unlink(missing_ok=True)
            sleep_ms = 5 + random.randint(0, 95)  # 5~100ms 随机退避
            time.sleep(sleep_ms / 1000)
    try:
        messages = fn(self._read_inbox(agent_id))
        self._write_inbox(agent_id, messages)
    finally:
        lock_file.unlink(missing_ok=True)
```

`O_CREAT | O_EXCL` 保证原子创建，两个进程不可能同时拿到锁。随机退避（5\~100ms）避免活锁。过期锁检测（10 秒）处理进程崩溃后遗留的锁文件。为什么用文件锁而不是内存锁？因为 tmux/iTerm 后端跑在独立进程里，内存锁无法跨进程。

### 读写操作

`write` 在锁内追加消息。 `consume` 在锁内把所有未读消息标记为 `read = True` 并返回。 `broadcast` 遍历所有成员分别 `write` ，跳过 `exclude` （通常是发送者自己）。每个收件人一个独立文件，写不同收件人不冲突。

## 队友的主循环（In-process 模式）

```python
async def _run():
    next_prompt = prompt
    while True:
        # 1. 注入本轮开始前邮箱里堆积的消息
        if mailbox is not None:
            reminder = _inject_pending_messages(mailbox, name)
            if reminder:
                conv.add_system_reminder(reminder)
        # 2. 执行一个完整的 agent turn
        result = await agent.run_to_completion(
            next_prompt, conv, event_callback=_on_event)
        # 3. 没有 mailbox 时退化为单次执行
        if mailbox is None:
            return result
        # 4. 发 idle 通知给 lead
        mailbox.write(LEAD_NAME, _create_idle_notification(name, reason))
        # 5. 轮询等待新任务或 shutdown
        new_prompt, shutdown = await _wait_for_next_prompt_or_shutdown(
            mailbox, name)
        if shutdown: return result
        next_prompt = new_prompt
```

循环的完整流程：检查邮箱中的未读消息并注入为 system-reminder，然后把 prompt 交给 agent 执行一轮，执行完毕后发 idle 通知给 Lead，接着进入空闲轮询。 `_wait_for_next_prompt_or_shutdown` 每 500ms 检查一次邮箱，收到 `[shutdown]` 前缀的消息就退出，收到普通消息就拼成下一轮的 user prompt 继续循环。没有 mailbox 时退化为单次执行，向后兼容旧的调用方式。

## 协调工具

### SendMessage

```python
async def execute(self, params):
    registry = AgentNameRegistry.instance()
    if p.to == "*":
        # 广播：给所有队友（排除自己）各写一份
        member_ids = [m.agent_id for m in team.members
                      if m.agent_id != self._from_agent_id]
        mailbox.broadcast(member_ids, msg, exclude=self._from_agent_id)
        return ToolResult(output=f"Message broadcast to {len(member_ids)} teammates.")
    # 单播：通过注册表解析名称 → agent_id
    target_id = registry.resolve(p.to)
    if target_id is None:
        return ToolResult(output=f"Cannot resolve recipient '{p.to}'.", is_error=True)
    mailbox.write(target_id, msg)
```

`to` 参数支持名称和 agent\_id 两种输入，通过 `AgentNameRegistry.resolve` 统一解析。 `to="*"` 触发广播。文本消息要求带 `summary` ，缺了会报错。 `message_type` 支持 `text` 、 `shutdown_request` 、 `shutdown_response` 三种结构化类型。发送到 pane 后端的队友时，还会调用 `_wake_pane` 通过 `tmux send-keys` 唤醒。

### TeamCreate

```python
async def execute(self, params):
    backend = self._team_manager.detect_backend(...)
    team = self._team_manager.create_team(
        name=p.team_name, lead_agent_id=self._parent_agent.agent_id, ...)
    # Coordinator 模式激活
    if is_coordinator_mode(self._enable_coordinator_mode):
        self._parent_agent.coordinator_mode = True
        self._parent_agent.registry = apply_coordinator_filter(...)
```

创建流程：检测后端 → `unique_team_name` 生成不冲突的名称（重名自动加数字后缀）→ 创建团队目录 → 初始化 config.json、tasks.json 和 mailbox 目录。如果 Coordinator 模式激活，还会把 Lead 的工具注册表收窄为只读+调度工具。

### TeamDelete

```python
async def execute(self, params):
    self._team_manager.delete_team(p.team_name)
    # 退出 Coordinator 模式，恢复完整工具集
    if self._parent_agent and self._parent_agent.coordinator_mode:
        self._parent_agent.registry = self._parent_agent._full_registry
        self._parent_agent.coordinator_mode = False
```

`delete_team` 内部的清理流程：检查是否有活跃成员（有就报错）→ 注销所有成员名称 → cancel in-process handle / kill pane → 清理 worktree → 删除邮箱 → 删除团队目录。如果之前激活了 Coordinator 模式，这里会恢复 Lead 的完整工具集。

## Lead 感知队友状态

```python
def drain_lead_mailbox(self) -> list[str]:
    notes: list[str] = []
    for team_name in list(self._teams.keys()):
        msgs = mailbox.consume(team.lead_agent_id)
        if not msgs: continue
        parts = [f'<team-notification team="{team_name}">']
        for m in msgs:
            parts.append(f"from={m.from_agent}: {m.content}")
        parts.append("</team-notification>")
        notes.append("\n".join(parts))
    return notes
```

遍历所有团队，用 `consume` （读并标记已读）的方式拉取发给 Lead 的消息。格式化成 `<team-notification>` XML 标签，注入到 Lead 的 agent 循环中作为 system-reminder。Lead 看到 idle 通知后决定是派新任务还是收工。

## 队友 spawn 流程

spawn 的完整流程在 `AgentTool._execute_as_teammate` 里实现，分六步：

1. **加载 Agent 定义&#x20;**：有 `subagent_type` 就从 AgentLoader 拿，没有就构造默认的 `teammate` 定义。如果启用了 fork，会从父 agent 的对话构建分叉。

2. **创建 Worktree&#x20;**：命名规则是 `team-{teamName}/{memberName}` ，给队友一个独立的文件系统。

3) **注入协调工具&#x20;**： `build_teammate_tools` 根据后端类型过滤工具集，in-process 模式用白名单（ `IN_PROCESS_TEAMMATE_ALLOWED_TOOLS` ），pane 模式保留全部工具但移除 TeamCreate/TeamDelete。然后注入五个协调工具：TaskCreate、TaskGet、TaskList、TaskUpdate、SendMessage。

4) **按后端分发启动&#x20;**：tmux/iTerm 走 `_spawn_pane_teammate` ，in-process 走 `task_manager.launch` 。

5. **注册名称&#x20;**： `AgentNameRegistry.instance().register(teammate_name, agent_id)` ，让 SendMessage 能按名称寻址。

6. **注册成员信息&#x20;**：构造 `TeammateInfo` 注册到 `team.members` ，并持久化到 config.json。

团队附录（ `TEAMMATE_ADDENDUM` ）会追加到队友的 system prompt 里，告诉队员：文本回复对队友不可见，必须用 SendMessage 工具通信；在 worktree 里工作，所有路径必须用相对路径。

## 协调者模式（Coordinator Mode）

### 激活条件

```python
def is_coordinator_mode(enable_flag=False):
    if not enable_flag: return False
    val = os.environ.get("GCODE_COORDINATOR_MODE", "").lower()
    return val in ("1", "true", "yes")
```

双重锁定：feature flag 参数 + `GCODE_COORDINATOR_MODE` 环境变量，两个都满足才激活。

### 工具白名单

```python
COORDINATOR_MODE_ALLOWED_TOOLS: frozenset[str] = frozenset({
    "Agent", "TaskStop", "SendMessage",
    "SyntheticOutput", "TeamCreate", "TeamDelete",
})
```

白名单里只有调度和协调工具，EditFile、WriteFile 这些写操作不在里面。设计意图：Lead 只调度不动手，实际修改交给队友完成。MCP 工具不在白名单内，但 `apply_coordinator_filter` 只保留白名单内的工具，所以 MCP 工具也会被过滤掉。

### 四阶段工作流

`get_coordinator_system_prompt` 生成约 3000 字的系统提示词，定义了 Research → Synthesis → Implementation → Verification 四个阶段。Synthesis 是 Lead 的核心职责：读取队友的研究结果，理解问题，然后写出具体的实现指令。提示词里明确列了反模式（lazy delegation，比如「Based on your findings, fix the bug」）和正确做法（包含具体文件路径、行号、改什么）。

## 共享任务管理（如有 SharedTaskStore）

```python
@dataclass
class SharedTask:
    id: str
    title: str
    status: str = "pending"  # pending | in_progress | completed | blocked
    assignee: str = ""
    blocks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
```

JSON 持久化到 `tasks.json` 。 `blocks` 和 `blocked_by` 描述任务间的依赖关系。 `update` 方法支持增量更新： `None` 参数跳过，非 `None` 才覆盖。 `add_blocks` 和 `add_blocked_by` 是追加语义并做去重，不替换已有依赖。

## 对话记录持久化（如有 Transcript）

```python
def save_transcript(team_name, agent_id, conversation):
    path = resolve_team_dir(team_name) / "transcripts" / f"{agent_id}.json"
    data = _serialize_conversation(conversation)
    path.write_text(json.dumps(data, indent=2))
```

序列化保留完整结构，每条消息包含 `role` 、 `content` 、 `tool_uses` 、 `tool_results` 。反序列化后标记 `env_injected = True` 和 `ltm_injected = True` ，避免重复注入系统环境和长期记忆。按 agent\_id 命名文件，一个队友一份对话记录。

## 小结

| 设计决策           | 实现方式                                                  |
| -------------- | ----------------------------------------------------- |
| 后端选择           | 默认 in-process， `detect_pane_backend` 逐级检测后兜底          |
| In-process 执行  | `asyncio.create_task` + `InProcessTeammateHandle` 包装  |
| 外部进程执行         | Tmux `new-window` / iTerm2 `it2 split-pane`           |
| 跨进程通信          | Mailbox 单文件 JSON + `O_CREAT\|O_EXCL` 文件锁              |
| 队友主循环          | while 循环：执行 → idle 通知 → 500ms 轮询等待                    |
| Lead 感知        | `drain_lead_mailbox` ，consume 语义 + XML 格式             |
| 工具暴露           | in-process 白名单 + 五个协调工具注入                             |
| Coordinator 模式 | 双重激活条件，工具收窄为调度集，四阶段系统提示词                              |
| 优雅关闭           | `delete_team` 检查活跃成员 → cancel/kill → 清 worktree → 删目录 |


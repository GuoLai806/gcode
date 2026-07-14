## 模块概览

命令系统的代码在 `gcode/commands/` 目录下：

| 文件/目录                        | 职责                                                   |
| ---------------------------- | ---------------------------------------------------- |
| `registry.py`                | 核心：类型定义、UIController 协议、CommandContext、Registry 注册中心 |
| `parser.py`                  | 命令解析 + 前缀补全                                          |
| `completion.py`              | TUI 补全弹窗组件（Textual Widget）                           |
| `loader.py`                  | 文件命令加载器：双路径扫描、Markdown 解析、 `$ARGUMENTS` 替换           |
| `handlers/__init__.py`       | 聚合所有内置命令，批量注册                                        |
| `handlers/help.py`           | /help 命令                                             |
| `handlers/status.py`         | /status 命令                                           |
| `handlers/compact.py`        | /compact 命令                                          |
| `handlers/clear.py`          | /clear 命令                                            |
| `handlers/plan.py`           | /plan 命令                                             |
| `handlers/session.py`        | /session 命令（含 list/resume/new/delete 子命令）            |
| `handlers/memory.py`         | /memory 命令                                           |
| `handlers/permission.py`     | /permission 命令（含 mode/rules/add/reset 子命令）           |
| `handlers/review.py`         | /review 命令                                           |
| `handlers/skill.py`          | /skill 命令                                            |
| `handlers/skill_register.py` | Skill 动态注册为斜杠命令                                      |
| `handlers/rewind.py`         | /rewind 命令                                           |
| `handlers/mcp.py`            | /mcp 命令                                              |

一个 handler 一个文件，改一个命令不需要翻几百行找位置。

## 核心类型

### CommandType：命令分类

```python
class CommandType(str, Enum):
    LOCAL = "local"
    LOCAL_UI = "local_ui"
    PROMPT = "prompt"
```

继承 `str` 让枚举值可以直接参与字符串比较。三种类型对应三条执行路径： `LOCAL` 是纯本地逻辑，handler 执行完直接展示结果； `LOCAL_UI` 需要操作 TUI 状态（清屏、切模式）； `PROMPT` 生成提示词发给 LLM，handler 的产出不是结果而是问题。

### Command：命令定义

```python
@dataclass
class Command:
    name: str
    description: str
    type: CommandType
    handler: CommandHandler
    aliases: list[str] = field(default_factory=list)
    usage: str = ""
    arg_prompt: str = ""
    hidden: bool = False
```

`handler` 的类型是 `Callable[[CommandContext], Awaitable[None]]` ，所有命令 handler 都是 async 的，即使有些命令不需要异步操作。统一用 async 避免了在分发层区分同步和异步的复杂度。

handler 不返回字符串，而是直接通过 `ctx.ui.add_system_message()` 输出结果。这意味着命令可以在中间做异步操作，也可以输出多条消息，灵活度比「返回一个字符串」更高。handler 绑定在 Command 上，定义和行为放在一起。

### CommandContext：执行上下文

```python
@dataclass
class CommandContext:
    args: str
    agent: Any
    conversation: Any
    session: Any
    session_manager: Any
    memory_manager: Any
    ui: UIController
    config: Any
```

一个命令执行时能拿到整个系统的几乎所有组件。 `args` 是命令名后面的参数， `agent` 是 Agent 实例， `session` 是当前会话， `memory_manager` 是记忆管理器， `ui` 是界面控制器。

依赖注入是直接传对象的方式。handler 可以直接调用 `ctx.agent.manual_compact()` ，不需要通过函数字段间接访问。好处是写 handler 非常方便，坏处是命令系统对 Agent 内部实现有感知。

`config` 是一个字典，用来传递不好放进固定字段的东西，比如 `set_session` 、 `set_conversation` 、 `clear_chat` 这类回调函数。灵活但类型安全性差，是一个实用主义的折衷。

`UIController` 用 `Protocol` 定义接口：

```python
class UIController(Protocol):
    def add_system_message(self, text: str) -> None: ...
    def send_user_message(self, text: str) -> None: ...
    def set_plan_mode(self, enabled: bool) -> None: ...
    def get_token_count(self) -> tuple[int, int]: ...
    def refresh_status(self) -> None: ...
```

命令 handler 只依赖这五个方法，不知道 TUI 的具体实现。测试时传入一个 mock 对象就行，不用启动真正的 Textual 界面。

### Registry：注册中心

```python
class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._alias_map: dict[str, str] = {}
        self._lock = asyncio.Lock()
```

两张 dict 加一把 asyncio 锁。 `_commands` 按主名称索引， `_alias_map` 把别名映射到主名称。锁是为 Skill 动态注册准备的，Skill 加载在后台异步进行，和用户操作可能同时发生。

注册方法有两个版本。 `register_sync` 用于启动阶段批量注册内置命令，不用 await。 `register` 是 async 版本，加锁保护并发安全：

```python
async def register(self, command: Command) -> None:
    async with self._lock:
        if command.name in self._commands or command.name in self._alias_map:
            raise ValueError(...)
        for alias in command.aliases:
            if alias in self._alias_map or alias in self._commands:
                raise ValueError(...)
        self._commands[command.name] = command
        for alias in command.aliases:
            self._alias_map[alias] = command.name
```

冲突检测是双向的：命令名不能和已有别名冲突，别名也不能和已有命令名冲突。冲突时抛 `ValueError` ，在注册阶段就暴露问题。

查找方法是先查主名称再查别名的两层查找：

```python
def find(self, name: str) -> Command | None:
    if name in self._commands:
        return self._commands[name]
    canon = self._alias_map.get(name)
    if canon:
        return self._commands.get(canon)
    return None
```

用户输入 `/h` ，主名称表里没有 `h` ，但别名表里 `h` 映射到 `help` ，最终返回 `/help` 命令。找不到返回 `None` 。

## 主流程走读

### 第一步：Parse 解析输入

```python
def parse_command(text: str) -> tuple[str, str, bool]:
    text = text.strip()
    if not text.startswith("/"):
        return "", "", False
    text = text[1:]
    if not text:
        return "", "", True
    parts = text.split(None, 1)
    name = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return name, args, True
```

返回值是三元组 `(命令名, 参数, 是否是命令)` 。第三个布尔值很关键：不是 `/` 开头的返回 `False` ，调用方就知道该走 Agent Loop。只输入了 `/` 没有命令名的情况，返回 `("", "", True)` ，调用方会列出所有可用命令。

`split(None, 1)` 是一个技巧： `None` 表示按任意空白分割， `1` 表示只分割一次。这样 `/review fix the bug` 会被分成 `["review", "fix the bug"]` ，参数部分保持完整。

### 第二步：Find 查找命令

查找逻辑上一节已经讲过，先在主命令表里精确匹配，再去别名表里查。两次 dict 查找，O(1) 时间复杂度。

### 第三步：按类型分发执行

分发逻辑在 TUI 层完成，命令模块只管定义和查找。TUI 拿到 Command 对象后根据 `type` 走不同路径：

* `LOCAL` ：直接 await handler，handler 内部通过 `ctx.ui.add_system_message()` 展示结果

* `LOCAL_UI` ：也走 handler，但 handler 里会调用 `ctx.ui.set_plan_mode()` 或 `ctx.config["clear_chat"]()` 等 UI 操作

* `PROMPT` ：handler 通过 `ctx.ui.send_user_message()` 把构造好的提示词发给 LLM

还有几个特殊情况：只输入 `/` 没有命令名时，列出所有可用命令；命令找不到时，提示用户输入 `/help` 查看可用命令；命令需要参数但用户没给，显示 `arg_prompt` 提示。

## 别名系统

别名在命令定义时声明，注册时存到独立的 `_alias_map` 字典里。查找时先查主名称再查别名，保证 `/help` 和 `/h` 找到同一个命令。

冲突检测在注册阶段完成， `register` 和 `register_sync` 都做了双向检查：命令名不能和已有别名冲突，别名不能和已有命令名或别名冲突。冲突时抛异常，不会把不确定的行为留给运行时。

## 自动补全

```python
def complete(registry, prefix):
    prefix = prefix.lstrip("/")
    seen: set[str] = set()
    matches: list[tuple[str, str]] = []
    for cmd in registry.list_commands():
        if cmd.name in seen:
            continue
        # 命令名或任一别名以 prefix 开头即匹配
        if cmd.name.startswith(prefix) or \
           any(a.startswith(prefix) for a in cmd.aliases):
            seen.add(cmd.name)
            display = f"/{cmd.name:<16} — {cmd.description[:28]}"
            matches.append((display, "/" + cmd.name))
    matches.sort(key=lambda x: x[1])
    return matches[:8]
```

返回值是 `(display_text, command_value)` 元组列表。display\_text 用于弹窗展示（命令名加描述），command\_value 用于填入输入框。 `seen` 集合防止同一个命令因为多个别名匹配而重复出现。结果最多返回 8 条，按命令名排序。

TUI 侧用 Textual 的 `CompletionPopup` 组件展示候选项，支持上下键选择、回车确认、点击选中。没有使用频率追踪机制，纯字母序排列。

## 内置命令速览

| 命令            | 别名          | 类型        | 职责                             |
| ------------- | ----------- | --------- | ------------------------------ |
| `/help`       | `/h` , `/?` | LOCAL     | 显示帮助信息，支持 `/help <cmd>` 查看单个命令 |
| `/status`     | `/s`        | LOCAL     | 显示模式、Token、工具数、记忆数、版本          |
| `/compact`    | `/c`        | LOCAL     | 手动触发上下文压缩                      |
| `/clear`      |             | LOCAL\_UI | 清除对话，创建新会话                     |
| `/plan`       | `/p`        | LOCAL\_UI | 切换到 Plan 只读模式                  |
| `/session`    |             | LOCAL     | 会话管理（list/resume/new/delete）   |
| `/memory`     |             | LOCAL     | 记忆管理（list/clear/edit）          |
| `/permission` |             | LOCAL     | 权限管理（mode/rules/add/reset）     |
| `/review`     |             | PROMPT    | 审查 git diff                    |
| `/skill`      | `/skills`   | LOCAL     | 管理 Skill 技能包（list/info/reload） |
| `/rewind`     |             | LOCAL     | 回退到之前的检查点                      |
| `/mcp`        |             | LOCAL     | 显示 MCP 服务器状态                   |

## 典型命令实现走读

### /help：最基础的 LOCAL 命令

```python
async def handle_help(ctx: CommandContext) -> None:
    registry = ctx.config["registry"]
    if ctx.args:
        cmd = registry.find(ctx.args.lower())
        if cmd is None:
            ctx.ui.add_system_message(
                f"未知命令：{ctx.args}，输入 /help 查看可用命令")
            return
        # 显示单个命令的名称、别名、描述、用法
        ctx.ui.add_system_message("\n".join(lines))
        return
    # 无参数：列出所有可见命令
    for cmd in registry.list_commands():
        lines.append(f"  /{_format_aliases(cmd):<24} {cmd.description}")
    ctx.ui.add_system_message("\n".join(lines))
```

不带参数列出所有非隐藏命令，带参数用 `find` 查找单个命令的详情。 `list_commands()` 过滤掉了 `hidden=True` 的命令，但 `find` 不过滤，所以隐藏命令虽然不在列表里，但可以用 `/help hidden_cmd` 查到。

### /status：展示状态信息

```python
async def handle_status(ctx: CommandContext) -> None:
    mode = ctx.agent.permission_mode.value
    input_tokens, output_tokens = ctx.ui.get_token_count()
    pct = int(input_tokens / context_window * 100)
    enabled = [t for t in ctx.agent.registry.list_tools()
               if ctx.agent.registry.is_enabled(t.name)]
    mem_entries = ctx.memory_manager.get_memories()
```

直接访问 `ctx.agent.permission_mode` 、 `ctx.memory_manager.get_memories()` ，把 Agent、MemoryManager 的属性当场读出来。没有函数字段做惰性求值，写法更直白，代价是命令对业务对象的内部结构有依赖。

### /compact：带前置检查的命令

```python
async def handle_compact(ctx: CommandContext) -> None:
    input_tokens, _ = ctx.ui.get_token_count()
    if input_tokens < 5000:
        ctx.ui.add_system_message(
            f"当前 token 数 {input_tokens:,}，无需压缩")
        return
    result = await ctx.agent.manual_compact(ctx.conversation)
```

调用 Agent 的压缩方法之前，先检查 token 数量。低于 5000 时直接返回，避免无效的 LLM 调用。压缩成功后还会把 compact boundary 持久化到会话记录里，这样 `/session resume` 恢复会话时能重建压缩后的状态。

### /session：带子命令的复杂命令

```python
async def handle_session(ctx: CommandContext) -> None:
    parts = ctx.args.split(None, 1)
    sub = parts[0] if parts else ""
    if sub == "":      # 显示当前会话信息
    elif sub == "list":  # 列出最近 10 个会话
    elif sub == "resume": # 恢复指定会话
    elif sub == "new":   # 创建新会话
    elif sub == "delete": # 删除指定会话
```

五个子命令，用 `split(None, 1)` 二次切分参数，拿出子命令名。其中 `resume` 最有看头：

```python
result = sm.resume(session_id)
ctx.config["set_session"](result.session)
conv = ConversationManager()
for msg in result.messages:
    conv.history.append(msg)
ctx.config["set_conversation"](conv)
```

恢复会话时通过 `config` 字典里的回调函数 `set_session` 和 `set_conversation` 替换全局状态。这些回调由 TUI 层注入，命令 handler 不需要直接引用 TUI 的内部状态。

`resume` 还支持按序号选择：先 `/session resume` 不带参数列出候选列表，然后 `/session resume 3` 按序号恢复。候选列表暂存在 `config["_resume_candidates"]` 里。

### /plan 和 /do：LocalUI 模式切换

```python
async def handle_plan(ctx: CommandContext) -> None:
    ctx.ui.set_plan_mode(True)
    ctx.ui.add_system_message(
        "已切换到 Plan 模式 — 只读，禁止写入和命令执行")
    if ctx.args:
        ctx.ui.send_user_message(ctx.args)
```

切换模式后，如果带了参数（比如 `/plan 分析一下目录结构` ），会立即把参数作为用户消息发出去。一步完成模式切换和任务下达。还有重入检测逻辑：如果本次会话曾退出过 Plan Mode 且 plan 文件已存在，会注入提醒。

### /review：PROMPT 类型命令

```python
REVIEW_PROMPT = (
    "请审查当前 git diff 中的代码变更。重点关注：\n"
    "1. 逻辑错误\n2. 安全问题\n3. 性能问题\n4. 代码风格"
)

async def handle_review(ctx: CommandContext) -> None:
    prompt = REVIEW_PROMPT
    if ctx.args:
        prompt += f"\n\n额外关注：{ctx.args}"
    ctx.ui.send_user_message(prompt)
```

PROMPT 类型命令不直接产出结果，而是通过 `send_user_message()` 把构造好的 prompt 发给 LLM。用户看到的效果就像自己输入了这段话然后按了回车。用户参数追加在预设 prompt 后面，不会覆盖原有的审查要点。

## 文件命令加载（如果有）

### 路径扫描与合并

```python
def load_user_commands(work_dir: str) -> list[Command]:
    dirs: list[str] = []
    dirs.append(str(home / ".gcode" / "commands"))
    dirs.append(str(Path(work_dir) / ".gcode" / "commands"))
    merged: dict[str, Command] = {}
    order: list[str] = []
    for d in dirs:
        for cmd in load_dir(d):
            if cmd.name not in merged:
                order.append(cmd.name)
            merged[cmd.name] = cmd
    return [merged[n] for n in order]
```

两个路径按优先级排列： `~/.gcode/commands/` （用户全局）和 `$work_dir/.gcode/commands/` （项目级）。后者覆盖前者，用 dict 去重保证同名命令只保留优先级最高的版本。 `order` 列表保持了首次发现的顺序。

子目录转命名空间： `git/log.md` 变成 `/git:log` ，路径各段用冒号连接，全部转小写。

### Markdown 解析

```python
def _split_frontmatter(content: str) -> tuple[dict, str]:
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return {}, content
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}, content
    return meta, parts[2]
```

frontmatter 里可以写 `description` 、 `argument-hint` 、 `aliases` 。没有 frontmatter 也没关系，Description 会回退到正文的第一个非标题行。解析失败静默降级，一个坏文件不会让整个命令系统崩溃。

### $ARGUMENTS 替换

```python
async def handler(ctx: CommandContext) -> None:
    if "$ARGUMENTS" in body:
        result = body.replace("$ARGUMENTS", ctx.args)
    elif ctx.args.strip():
        # 无占位符时追加用户请求段落
        result = body + "\n\n## User Request\n\n" + ctx.args
    else:
        result = body
    ctx.ui.send_user_message(result)
```

文件命令统一注册为 `PROMPT` 类型。如果模板里有 `$ARGUMENTS` 占位符就直接替换；没有占位符但用户传了参数，就追加一个 `## User Request` 段落。handler 最终调用 `send_user_message` 把内容发给 LLM。

### Skill 动态注册

Skill 系统可以把自己注册为斜杠命令，由 `skill_register.py` 实现：

```python
_REGISTERED_SKILL_NAMES: set[str] = set()  # 追踪哪些命令来自 Skill

def register_skill_commands(registry, loader, executor=None):
    # 清理旧的 Skill 命令
    for name in list(_REGISTERED_SKILL_NAMES):
        registry._commands.pop(name, None)
        registry._alias_map = {
            k: v for k, v in registry._alias_map.items() if v != name}
        _REGISTERED_SKILL_NAMES.discard(name)
    # 遍历 Skill 目录，注册新命令
    for skill_name, skill_desc in loader.get_catalog():
        if registry.find(skill_name) is not None:
            continue  # 同名内置命令已存在，跳过
        registry.register_sync(Command(name=skill_name, ...))
        _REGISTERED_SKILL_NAMES.add(skill_name)
```

每次 `/skill reload` 时先清除旧的 Skill 命令再重新注册。 `_REGISTERED_SKILL_NAMES` 这个模块级集合追踪了哪些命令是 Skill 注册的，清理时只动这些，不会误删内置命令。已存在同名命令的 Skill 会被跳过，注册失败也只是 warning 日志，不影响系统运行。

Skill 命令的 handler 用工厂函数 `make_handler` 生成，根据 Skill 的 `mode` 决定执行方式： `fork` 模式用 `asyncio.create_task` 在后台异步执行， `inline` 模式把 Skill 内容注入上下文然后触发 LLM。

## 小结

| 设计决策       | 实现方式                                                           |
| ---------- | -------------------------------------------------------------- |
| 命令类型体系     | 三种 `CommandType` （LOCAL / LOCAL\_UI / PROMPT）， `str` 继承支持字符串比较 |
| Handler 签名 | 统一 `async` ，接收 `CommandContext` ，不返回值而直接操作 UI                  |
| 上下文依赖注入    | 直接传业务对象（Agent、MemoryManager），config 字典传回调函数                    |
| UI 解耦      | `Protocol` 定义接口，handler 不依赖具体 TUI 实现                           |
| 别名系统       | 双 dict（\_commands + \_alias\_map），双向冲突检测                       |
| 文件命令加载     | Markdown + YAML frontmatter，双路径按优先级合并                          |
| 参数传递       | `$ARGUMENTS` 占位符替换，无占位符时自动追加                                   |
| 补全排序       | 前缀匹配 + 按命令名字母序排序，最多返回 8 条                                      |
| 并发安全       | `asyncio.Lock()` 保护动态注册，为 Skill 系统预留                           |
| 动态扩展       | Skill 可注册为命令，reload 时清理重建， `_REGISTERED_SKILL_NAMES` 追踪来源      |
| 文件组织       | 一个命令一个文件， `__init__.py` 聚合注册                                   |
| 容错策略       | 注册冲突抛 ValueError，Markdown 解析失败静默降级                             |


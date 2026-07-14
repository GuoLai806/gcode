## 模块概览

工具系统的代码集中在 `gcode/tools/` 包下，外加一个独立的缓存模块：

| 文件                    | 职责                                                           |
| --------------------- | ------------------------------------------------------------ |
| `base.py`             | 核心基础设施：Tool 抽象基类、ToolResult、ToolCategory、流事件类型、SKIP\_DIRS 常量 |
| `__init__.py`         | ToolRegistry 注册中心、带评分的延迟搜索、 `create_default_registry` 工厂     |
| `file_state_cache.py` | FileStateCache，读写门控：先读后写、修改检测                                |
| `read_file.py`        | ReadFile，offset/limit 分页加缓存                                  |
| `write_file.py`       | WriteFile，自动创建父目录                                            |
| `edit_file.py`        | EditFile，唯一性校验加缓存失效                                          |
| `bash.py`             | Bash，asyncio 子进程加超时，退出码语义判断                                  |
| `glob.py`             | Glob，模式匹配加修改时间排序                                             |
| `grep.py`             | Grep，正则搜索加文件名过滤                                              |
| `impl/tool_search.py` | ToolSearch，延迟工具的检索和加载                                        |
| `cache.py`            | FileCache，文件内容缓存（在 `gcode/` 根目录）                           |

靠 Pydantic 做参数校验、asyncio 做异步执行，代码相当紧凑。

## 核心类型

### Tool 接口

```python
class Tool(ABC):
    name: str
    description: str
    params_model: type[BaseModel]
    category: ToolCategory = "read"
    is_concurrency_safe: bool = False
    is_system_tool: bool = False
    should_defer: bool = False

    @abstractmethod
    async def execute(self, params: BaseModel) -> ToolResult: ...
```

工具的抽象用 ABC 抽象基类，所有工具继承它，基类带默认值，子类只覆盖要改的。

这些元字段不是摆设，每一个都有人消费： `category` 经 `is_read_only` 给权限系统判断要不要拦截， `is_concurrency_safe` 给执行引擎决定能不能并发， `should_defer` 给注册中心判断要不要默认隐藏。元信息集中在基类上声明，不同子系统各取所需，这是后面权限、调度自动运转的基础。

最关键的设计在 `params_model` 。挂一个 Pydantic 模型上去，Schema 就能自动生成：

```python
def get_schema(self) -> dict[str, Any]:
    schema = self.params_model.model_json_schema()
    schema.pop("title", None)
    return {
        "name": self.name,
        "description": self.description,
        "input_schema": schema,
    }
```

`model_json_schema()` 把模型字段直接转成标准 JSON Schema， `pop("title")` 去掉自动塞的标题字段。每个工具只要定义一个 Params 类，Schema 就有了，不会出现手写 Schema 和实际参数对不上的问题。

### ToolResult

```python
@dataclass
class ToolResult:
    output: str
    is_error: bool = False
```

只有两个字段。用 dataclass 而不是 Pydantic 的 BaseModel 是有意的：ToolResult 是内部数据结构，不需要序列化和校验的开销。

`is_error` 不是程序异常，而是告诉模型「这次没成功」。模型收到 `is_error=True` 会重新判断再试。比如 EditFile 找不到要替换的字符串，返回 `is_error=True` ，模型就知道该先 ReadFile 确认内容再改。工具执行失败对模型来说是有价值的反馈，只有真正的系统级错误才该作为程序异常上报。

### ToolCategory

```python
ToolCategory = Literal["read", "write", "command"]
```

用 `Literal` 把三个合法值写死，类型检查器在静态检查阶段就能拦下非法分类，运行时不需要额外校验。 `read` 只读、 `write` 写文件、 `command` 执行命令，权限系统按这个分类决定检查策略。

### Registry 注册中心

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._disabled: set[str] = set()
        self._discovered: set[str] = set()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
```

底层是一个字典，key 是工具名，value 是工具实例。字典保持插入顺序，所以注册顺序就是呈现顺序。 `_disabled` 集合负责运行时屏蔽， `_discovered` 跟踪哪些延迟工具已经被 ToolSearch 激活。

查找靠 `get(name)` 返回 `Tool | None` ，Schema 生成靠 `get_all_schemas(protocol)` 。后者做两层过滤加一层协议适配：先跳过 `_disabled` 里的，再跳过还没被发现的延迟工具，最后按 protocol 把同一份 Schema 适配成 Anthropic 的 `input_schema` 格式或 OpenAI 的 `parameters` 格式：

```python
def get_all_schemas(self, protocol: str = "anthropic") -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for name, tool in self._tools.items():
        if name in self._disabled:
            continue
        if getattr(tool, "should_defer", False) and name not in self._discovered:
            continue
        base = tool.get_schema()
        # 按协议适配输出格式
        if protocol in ("openai", "openai-compat"):
            schemas.append({"type": "function", "name": base["name"],
                "description": base["description"], "parameters": base["input_schema"]})
        else:
            schemas.append(base)
    return schemas
```

## 主流程走读

工具系统的主线分三步：注册、生成 Schema、执行。

### 第一步：注册

启动入口是 `create_default_registry` ，注册六个内置工具：

```python
def create_default_registry(file_cache=None, file_history=None):
    file_state_cache = FileStateCache()
    registry = ToolRegistry()
    registry.register(ReadFile(file_cache=file_cache, file_state_cache=file_state_cache))
    registry.register(WriteFile(file_cache=file_cache, file_history=file_history,
                                file_state_cache=file_state_cache))
    registry.register(EditFile(file_cache=file_cache, file_history=file_history,
                                file_state_cache=file_state_cache))
    registry.register(Bash())
    registry.register(Glob())
    registry.register(Grep())
    return registry
```

两个细节。第一，所有 import 写在函数体内，是延迟导入，避免工具模块反过来引用 registry 造成循环依赖。第二， `file_cache` 、 `file_history` 和 `file_state_cache` 通过依赖注入只传给需要的工具，Bash、Glob、Grep 不碰文件缓存就不传。

### 第二步：生成 Schema

每轮迭代，Agent Loop 调用 `registry.get_all_schemas(protocol)` 拿到工具描述，作为 LLM API 的 `tools` 参数发出去。Schema 从 Pydantic 模型自动生成，以 EditFile 的参数为例：

```python
class Params(BaseModel):
    file_path: str = Field(description="Path to the file to edit")
    old_string: str = Field(description="The exact string to find and replace (must be unique in file)")
    new_string: str = Field(description="The replacement string")
```

`Field` 的 `description` 会进到 Schema 里，成为模型看到的参数说明。描述写在离代码最近的地方，这也是「描述最值得打磨」在工程上的落点。

### 第三步：执行

Agent Loop 里收到 `ToolCallComplete` 事件后，走这条路径执行工具：

```python
tool = self.registry.get(tc.tool_name)
# ...
params = tool.params_model.model_validate(tc.arguments)
result = await tool.execute(params)
# ...
except ValidationError as e:
    result = ToolResult(output=f"Parameter validation error: {e}", is_error=True)
```

从 `tool_use` 拿到 name 和 input，Registry 查工具，Pydantic 校验参数， `await execute` 执行，结果包装成 `tool_result` 发回模型。校验失败不抛异常中断循环，而是包装成 `is_error=True` 的 ToolResult 还给模型，让它调整参数重试。

模型一次可能返回多个工具调用，执行引擎按 `is_concurrency_safe` 分批。只读的 ReadFile、Glob、Grep 标了 `True` ，能并到同一批用 `asyncio.gather` 并发跑；WriteFile、EditFile、Bash 是默认的 `False` ，各自串行。读可以并行，写一定排队。

## 内置工具

六个工具形成一套完整的代码操作链：Glob 和 Grep 找到文件位置，ReadFile 读取内容，EditFile 精确修改，WriteFile 整体写入，Bash 编译测试验证。接下来逐个看重点。

### ReadFile

```python
resolved = str(path.resolve())
text = self._cache.get(resolved) if self._cache else None
if text is None:
    text = path.read_text(encoding="utf-8")
    if self._cache:
        self._cache.put(resolved, text)

lines = text.splitlines()
selected = lines[params.offset : params.offset + params.limit]
numbered = [f"{i + params.offset + 1}\t{line}" for i, line in enumerate(selected)]
```

用 `path.resolve()` 把路径归一成绝对路径作缓存 key，相对路径和绝对路径都能命中同一条目。缓存有就用，没有就读盘再存。分页用 slice，输出 `行号<tab>内容` 、行号从 1 开始，方便模型后续用 EditFile 精确定位。大文件可以指定 offset 和 limit 分段读取。

读取成功后还会记录到 `FileStateCache` ，存下文件内容和修改时间戳，为后面的「先读后写」门控做准备。

### WriteFile

```python
if self._state_cache and path.exists():
    resolved = str(path.resolve())
    ok, err_msg = self._state_cache.check(resolved)
    if not ok:
        return ToolResult(output=err_msg, is_error=True)

path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(params.content, encoding="utf-8")
if self._cache:
    self._cache.invalidate(str(path.resolve()))
if self._state_cache:
    self._state_cache.update(str(path.resolve()))
```

如果文件已存在，先查 `FileStateCache` 确认模型读过这个文件，且读了之后没被其他地方改过。这个门控防止模型凭空覆盖一个它没看过的文件。新文件不需要先读， `path.exists()` 的判断放行了创建场景。 `mkdir(parents=True)` 自动创建不存在的父目录。写完后同时失效 FileCache 的内容缓存，并更新 FileStateCache 的时间戳。

### EditFile

EditFile 最能体现工具的设计哲学。核心是唯一性校验：

```python
count = content.count(params.old_string)
if count == 0:
    return ToolResult(output="Error: old_string not found in file", is_error=True)
if count > 1:
    return ToolResult(
        output=f"Error: old_string found {count} times, must be unique",
        is_error=True,
    )
```

`str.count()` 做全文计数：0 次报找不到，多于 1 次报不唯一。这个约束解决的是「模型给了一个太短、文件里出现多次的字符串，你不知道它想改哪个」的问题。报错信息会引导模型给出更长、更有区分度的 old\_string。校验通过后替换并失效缓存：

```python
new_content = content.replace(params.old_string, params.new_string, 1)
path.write_text(new_content, encoding="utf-8")
if self._cache:
    self._cache.invalidate(str(path.resolve()))
```

`replace` 的第三个参数 `1` 确保只替换一次，虽然前面已校验唯一，这里再加一层保险。和 WriteFile 一样，编辑前也有 FileStateCache 的门控检查，编辑后也要更新状态缓存。

### Bash

Bash 是唯一分类为 `command` 的工具，也是唯一直接和操作系统交互的：

```python
async def execute(self, params: Params) -> ToolResult:
    timeout = min(params.timeout, MAX_TIMEOUT)  # MAX_TIMEOUT = 600
    try:
        proc = await asyncio.create_subprocess_shell(
            params.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ToolResult(output=f"Error: command timed out after {timeout}s", is_error=True)
```

默认超时 120 秒、上限 600 秒。 `create_subprocess_shell` 启动子进程， `wait_for` 包住 `communicate()` 做超时控制。超时后先 `kill()` 再 `await proc.wait()` 等它真正退出，避免僵尸进程。输出用 `decode(errors='replace')` 处理非 UTF-8 字节。

退出码判断有一套语义映射表，不是简单的「非零就报错」：

```python
_COMMAND_ERROR_THRESHOLDS: dict[str, int] = {
    "grep": 2,   # exit 1 = 没有匹配到内容
    "diff": 2,   # exit 1 = 文件内容有差异
    "find": 2,   # exit 1 = 部分成功
    "test": 2,   # exit 1 = 条件为假
}
```

`grep` 返回 1 只是「没找到匹配行」，不是执行出错，只有退出码 >= 2 才算真正的错误。对于管道命令，会提取最后一段的命令名来查表，因为管道的退出码由最后一个命令决定。

### Glob

```python
found = [
    p for p in base.glob(params.pattern)
    if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
]
found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
matches = [str(p.relative_to(base)) for p in found]
```

用标准库 `Path.glob` 做递归匹配（支持 `**` ），过滤掉非文件和 SKIP\_DIRS 里的目录（ `.git` 、 `.venv` 、 `node_modules` 、 `__pycache__` 等），结果按修改时间倒序排列，最近改过的排前面，让模型优先关注活跃文件。

### Grep

```python
regex = re.compile(params.pattern)
# ...
for file_path in sorted(base.glob(glob_pattern)):
    # 跳过 SKIP_DIRS 和非文件
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    for line_num, line in enumerate(text.splitlines(), 1):
        if regex.search(line):
            rel = file_path.relative_to(base)
            results.append(f"{rel}:{line_num}:{line}")
```

先编译正则，再逐文件逐行匹配，输出 `文件路径:行号:内容` 。支持 `include` 参数做文件名过滤（如 `*.py` ）。读文件用 `errors="ignore"` 跳过无法解码的内容，遇到二进制文件不会崩溃。两个搜索工具共用 `base.py` 里的 `SKIP_DIRS` 常量，遍历时跳过无意义的目录。

## ToolSearch 与延迟加载

ToolRegistry 里还有一套延迟加载机制。工具类声明 `should_defer = True` ，注册中心就默认不把它暴露给模型。 `search_deferred` 按查询做打分检索：名字命中加 10 分、描述命中加 5 分、单词级匹配再加分，结果按分数倒序返回。 `find_deferred_by_names` 则是按名字精确拉取，对应 `select:<name>` 语法。

ToolSearch 工具自身的 `should_defer` 设为 `False` ，它永远在工具列表里，否则就没人能触发搜索了。模型搜到延迟工具后调用 `mark_discovered` ，下一轮 `get_all_schemas` 就会包含它的完整 Schema。

六个内置工具都没有设 `should_defer` ，这套机制在本章不会触发。它真正发挥作用是引入 MCP 之后：MCP 工具数量不可控，全塞进上下文既费 token 又干扰模型选择。

## 流式 tool\_use 解析

工具参数在流式响应里是一段段 JSON 碎片到的，要拼起来再解析，这是这部分最需要小心的地方。 `AnthropicClient.stream` 里的事件序列是： `content_block_start` 开头给 id 和 name，一串 `content_block_delta` 给 JSON 碎片， `content_block_stop` 收尾。

处理逻辑就是一个字符串缓冲区加三个分支：

```python
# current_tool_name / current_tool_id / json_accum 三个变量做状态跟踪
if event.type == "content_block_start":
    if block.type == "tool_use":
        current_tool_name = block.name
        current_tool_id = block.id
        json_accum = ""  # 清空缓冲
        yield ToolCallStart(tool_name=current_tool_name, tool_id=current_tool_id)
elif event.type == "content_block_delta":
    if delta.type == "input_json_delta":
        json_accum += delta.partial_json  # 累积碎片
elif event.type == "content_block_stop":
    if current_tool_name:
        args = json.loads(json_accum) if json_accum else {}
        yield ToolCallComplete(tool_id=current_tool_id,
            tool_name=current_tool_name, arguments=args)
```

收到 tool\_use 的 start 就记下 id、name、清空缓冲；每个 `input_json_delta` 把 `partial_json` 追加进缓冲；stop 时一次性 `json.loads` 。 `except json.JSONDecodeError: args = {}` 是关键的优雅降级：碎片拼不成合法 JSON 也不崩溃，退化成空参数让流程继续。

整个过程对外只发 `ToolCallStart` 、 `ToolCallDelta` 、 `ToolCallComplete` 三种流事件（定义在 base.py），上层 Agent 消费这些事件，不用关心底层协议。OpenAI 兼容协议的分片机制不同，用 `tool_calls` 的 index 累积 arguments 字符串，但拼完同样是一次 `json.loads` ，思路一致。

## 消息管道的变化

工具调用让对话不再是简单的 user 和 assistant 交替。 `build_anthropic_messages` 把内部历史转成 API 要的消息格式：

```python
# 带 tool_use 的助手消息：文本块和 tool_use 块放在同一个 content 列表
for tu in m.tool_uses:
    content.append({"type": "tool_use", "id": tu.tool_use_id,
                     "name": tu.tool_name, "input": tu.arguments})
result.append({"role": "assistant", "content": content})

# 工具结果消息：以 user 角色发送，配对靠 tool_use_id
for tr in m.tool_results:
    content.append({"type": "tool_result", "tool_use_id": tr.tool_use_id,
                     "content": tr.content, "is_error": tr.is_error})
result.append({"role": "user", "content": content})
```

三个要点都在这段里。第一， `tool_result` 以 user 角色发送，user 和 assistant 交替的惯例依然成立，只是 user 消息的内容变成了 tool\_result 列表。第二，一条 assistant 消息的 content 是个列表，文本块和 tool\_use 块放在一起，不拆成两条。第三，配对靠 id：tool\_use 带 `id` ，tool\_result 带 `tool_use_id` ，模型据此知道哪个结果对应哪次调用。工具返回的 `is_error` 也透过 tool\_result 一路带到 API，模型才能区分成功和失败。

## 小结

| 设计决策         | 实现方式                                                                             |
| ------------ | -------------------------------------------------------------------------------- |
| 工具抽象         | ABC 抽象基类，类属性加一个 async 抽象方法                                                       |
| 参数校验         | Pydantic 模型， `model_json_schema()` 自动生成 Schema， `model_validate` 校验失败转 is\_error |
| 工具分类         | `Literal["read", "write", "command"]` ，静态类型检查                                    |
| 结果传递         | `ToolResult` dataclass， `is_error` 让模型自行处理失败                                     |
| 注册机制         | `ToolRegistry` 用字典存储，运行时 disable/enable 屏蔽                                       |
| 并发控制         | `is_concurrency_safe` 标记，由调度分批，只读并行、写串行                                          |
| 文件缓存         | `FileCache` 字典加锁，关键在写后 invalidate； `FileStateCache` 做先读后写门控                      |
| 异步执行         | 所有 `execute` 都是 async，Bash 用 `asyncio.create_subprocess_shell`                   |
| 流式 tool\_use | 缓冲区累积 `input_json_delta` ， `content_block_stop` 时 `json.loads` ，失败降级为空参数         |
| 协议适配         | `get_all_schemas(protocol)` 与序列化层抹平 Anthropic 与 OpenAI 的格式差异                     |

读这一章的源码，最该带走的是：元信息（category、is\_concurrency\_safe 这些）怎么被权限和调度消费，这是后面几章自动化的基础；以及 Schema 生成和协议适配怎么把工具定义和具体 API 格式解耦。

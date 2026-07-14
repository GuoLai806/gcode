

## 模块概览

MCP 的代码分布在 `gcode/mcp/` 目录下，按职责拆成了三个文件：

| 文件                | 职责                                |
| ----------------- | --------------------------------- |
| `client.py`       | 单个 MCP 连接的建立、维护和销毁                |
| `manager.py`      | 管理多个 MCP 服务器的生命周期，统一注册和关闭         |
| `tool_wrapper.py` | 把 MCP 工具定义适配成 GCode 内部的 Tool 接口 |

各自内聚。 `manager.py` 不关心连接细节， `client.py` 不关心工具注册， `tool_wrapper.py` 不关心连接管理。每个模块只需要理解自己那一层的逻辑。

依赖官方 `mcp` SDK，传输层和会话管理都由 SDK 封装。GCode 只需要创建 transport、把 `read` / `write` 通道传给 `ClientSession` ，再调 `session.initialize()` 完成握手。

## 核心类型

### MCPServerConfig：服务器配置

```python
@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    @property
    def is_stdio(self) -> bool:
        return self.command is not None
```

用 `@dataclass` 定义，六个字段。 `command` 和 `url` 二选一，有 `command` 就走 stdio，有 `url` 就走 HTTP。 `is_stdio` 是只读属性，封装了判断逻辑。

环境变量展开用 `resolve_env_vars` 函数，正则匹配 `${VAR}` 替换成实际值：

```python
def resolve_env_vars(value: str) -> str:
    return _ENV_VAR_RE.sub(
        lambda m: os.environ.get(
            m.group(1), m.group(0)),
        value)
```

### MCPClient：单个 MCP 连接

```python
class MCPClient:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.name = config.name
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._alive = False
```

三个状态字段。 `_session` 是 MCP SDK 提供的会话对象，所有协议操作都走它。 `_stack` 是 `AsyncExitStack` ，Python 特有的异步资源管理器。 `_alive` 是布尔标志位，用来快速判断连接是否存活。

`is_alive` 暴露为只读属性：

```python
@property
def is_alive(self) -> bool:
    return self._alive
```

用 `@property` 而不是普通方法，表示这是一个状态查询，不是一个会触发副作用的操作。

### MCPManager：多连接管理器

```python
class MCPManager:
    def __init__(self) -> None:
        self._configs: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
```

两个字典，一个存配置，一个存已连接的客户端。用服务器名做 key，天然去重。前缀下划线标记「这是内部状态，外面不要直接碰」，是 Python 社区的封装约定。

### MCPToolWrapper：协议适配器

```python
class MCPToolWrapper(Tool):
    def __init__(self, server_name, tool_def, client):
        self._server_name = server_name
        self._tool_def = tool_def
        self._client = client
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self.description = tool_def.description or tool_def.name
        self.category = "command"
        self.should_defer = True
```

继承自 GCode 的 `Tool` 基类，在构造函数里直接设置所有必需属性。 `should_defer = True` 表示延迟加载，不会在初始化时塞进 system prompt。名字格式 `mcp_<server>_<tool>` 用单下划线分隔，能反向定位到是哪个服务器的哪个工具。

## 主流程走读

### 第一步：connect，建连接

```python
async def connect(self) -> None:
    if self._alive:
        return
    self._stack = AsyncExitStack()
    await self._stack.__aenter__()
```

开头的 `if self._alive: return` 是幂等保护，重复调用不会创建多余连接。 `AsyncExitStack` 像一个栈，资源按进入顺序压栈，关闭时按 LIFO 顺序弹出。

接下来根据配置选择传输层，建立会话：

```python
    try:
        if self.config.is_stdio:
            read, write = await self._connect_stdio()
        else:
            read, write = await self._connect_http()
        session = await self._stack.enter_async_context(
            ClientSession(read, write))
        await session.initialize()
        self._session = session
        self._alive = True
    except Exception:
        await self._cleanup_stack()
        raise
```

SDK 的 `session.initialize()` 内部完成了 `initialize` 请求和 `notifications/initialized` 通知的发送。异常时清理已分配的资源，不会泄漏。

### 第二步：list\_tools，发现工具

```python
async def list_tools(self) -> list[types.Tool]:
    assert self._session is not None
    result = await self._session.list_tools()
    return list(result.tools)
```

一行调用，SDK 发送 `tools/list` 请求。 `list()` 是防御性复制，调用方拿到的是独立拷贝。

### 第三步：call\_tool，执行工具

```python
async def call_tool(
    self, name: str, arguments: dict[str, Any]
) -> types.CallToolResult:
    assert self._session is not None
    return await self._session.call_tool(name, arguments)
```

返回 `CallToolResult` 对象，里面的 `content` 是多态内容列表， `isError` 标记业务层面是否失败。这两个信息的拆解交给 `MCPToolWrapper` 去做。

## 传输层选择

### stdio 传输

```python
async def _connect_stdio(self):
    params = StdioServerParameters(
        command=self.config.command,
        args=self.config.args,
        env=build_child_env(self.config.env),
    )
    devnull = open(os.devnull, "w")
    self._stack.callback(devnull.close)
    read, write = await self._stack.enter_async_context(
        stdio_client(params, errlog=devnull))
    return read, write
```

`StdioServerParameters` 来自 MCP SDK，它启动子进程并通过 stdin/stdout 通信。 `build_child_env` 负责把配置里的环境变量注入到子进程环境中，同时做 `${VAR}` 的展开。

stderr 处理值得注意： `errlog=devnull` 把 stderr 输出重定向到 `/dev/null` 。stderr 不参与协议通信，但如果不消费，缓冲区满了子进程会阻塞。 `self._stack.callback(devnull.close)` 确保 stack 关闭时文件句柄也会被释放。

### HTTP 传输（Streamable HTTP）

```python
async def _connect_http(self):
    resolved_headers = {
        k: resolve_env_vars(v)
        for k, v in self.config.headers.items()
    }
    http_client = httpx.AsyncClient(
        headers=resolved_headers,
        follow_redirects=True,
    )
    await self._stack.enter_async_context(http_client)
    result = await self._stack.enter_async_context(
        streamable_http_client(
            self.config.url, http_client=http_client))
    read, write = result[0], result[1]
    return read, write
```

用 `httpx.AsyncClient` 做 HTTP 请求。自定义 Headers 经过环境变量展开后注入。 `streamable_http_client` 是 SDK 提供的 Streamable HTTP 传输实现，Accept 头、Session ID 管理、SSE 解析这些协议细节都由 SDK 内部处理。

`http_client` 和 `streamable_http_client` 都通过 `enter_async_context` 注册到 `AsyncExitStack` ，关闭时会按 LIFO 顺序释放。

### 传输层抽象

两种传输方式返回的都是 `(read, write)` 通道对，传给 `ClientSession(read, write)` 后，上层的 `initialize()` 、 `list_tools()` 、 `call_tool()` 完全不关心底层是管道还是 HTTP。

## 工具适配器

### 名称包装

名字在构造函数里直接用 f-string 拼接： `f"mcp_{server_name}_{tool_def.name}"` 。用下划线分隔服务器名和工具名，不同 Server 可能有同名工具，加前缀避免冲突。

### Schema 透传

```python
def get_schema(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "input_schema": self._tool_def.inputSchema,
    }
```

直接把 MCP 工具的 `inputSchema` 透传给 LLM，不做任何转换。

### 参数处理（Python 特有）

用 Pydantic 动态生成参数验证模型：

```python
def _build_params_model(tool_name, input_schema):
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    field_definitions = {}
    for name, prop in properties.items():
        py_type = _json_type_to_python(
            prop.get("type", "string"))
        if name in required:
            field_definitions[name] = (py_type, ...)
        else:
            field_definitions[name] = (py_type | None, None)
    return create_model(
        f"{tool_name}Params", **field_definitions)
```

`create_model` 是 Pydantic 提供的动态模型生成器。它根据 MCP 工具的 JSON Schema 在运行时创建一个 Python 类。 `(py_type, ...)` 表示必填字段， `(py_type | None, None)` 表示可选字段默认值为 `None` 。

JSON 类型到 Python 类型的映射很直接：

```python
def _json_type_to_python(json_type: str) -> type:
    mapping = {
        "string": str, "integer": int,
        "number": float, "boolean": bool,
        "object": dict, "array": list,
    }
    return mapping.get(json_type, str)
```

遇到不认识的类型就回退到 `str` ，是防御性设计。MCP 服务器可能返回非标准类型，与其报错不如按字符串处理。

### 执行桥接

`execute` 是适配器最核心的部分，处理了三层问题：

```python
async def execute(self, params: BaseModel) -> ToolResult:
    if not self._client.is_alive:
        try:
            await self._client.connect()
        except Exception as e:
            return ToolResult(
                output=f"reconnect failed: {e}",
                is_error=True)
```

第一层，检查连接是否存活。如果断了就尝试重连，重连失败返回错误结果，不抛异常。这是 独有的「执行前保活」逻辑。

```python
    try:
        result = await self._client.call_tool(
            self._tool_def.name,
            params.model_dump(exclude_none=True))
    except Exception as e:
        self._client._alive = False
        return ToolResult(
            output=f"MCP tool call failed: {e}",
            is_error=True)
```

第二层，调用工具。 `params.model_dump(exclude_none=True)` 把 Pydantic 模型转回字典，同时排除值为 `None` 的可选字段。传给 `call_tool` 的是 `self._tool_def.name` （原始工具名），不是 `self.name` （带前缀的名字）。调用失败时把 `_alive` 设为 `False` ，下次再调就会触发重连。

第三层，提取文本内容：

```python
def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if isinstance(block, mcp_types.TextContent):
            parts.append(block.text)
        elif isinstance(block, mcp_types.ImageContent):
            parts.append(f"[image: {block.mimeType}]")
        elif isinstance(block, mcp_types.EmbeddedResource):
            resource = block.resource
            if hasattr(resource, "text"):
                parts.append(resource.text)
            else:
                parts.append(
                    f"[binary resource: {resource.uri}]")
    return "\n".join(parts) if parts else "(no output)"
```

文本直接取 `text` ，图片和二进制资源保留一个占位描述。除了 `TextContent` ，还处理了 `ImageContent` 和 `EmbeddedResource` 两种类型。空结果返回 `"(no output)"` 。

## 延迟加载：ToolSearch 与 DeferrableTool

MCPToolWrapper 构造时设置了 `self.should_defer = True` ，所有 MCP 工具默认不进工具列表。 `get_all_schemas()` 构建每轮发给 LLM 的工具列表时，跳过未发现的延迟工具：

```python
if getattr(tool, "should_defer", False) \
   and name not in self._discovered:
    continue
```

`get_deferred_tool_names()` 返回未发现的延迟工具名称列表，Agent Loop 把这些名字注入 system-reminder。

LLM 需要某个延迟工具时，调用 ToolSearchTool。它支持两种查询模式：

```python
if query.startswith("select:"):
    names = [n.strip() for n in query[7:].split(",")]
    schemas = self._registry.find_deferred_by_names(
        names, self._protocol)
else:
    schemas = self._registry.search_deferred(
        query, max_results, self._protocol)
```

`select:` 前缀走精确查找。不带前缀走 独有的评分搜索机制：

```python
score = 0
if query_lower in name_lower:
    score += 10
if query_lower in desc_lower:
    score += 5
for word in query_lower.split():
    if word in name_lower:
        score += 3
    if word in desc_lower:
        score += 1
```

完整查询串匹配工具名得 10 分，匹配描述得 5 分。然后把查询拆成单词，每个词匹配工具名得 3 分，匹配描述得 1 分。最后按总分降序排列，取前 `max_results` 个。名称匹配比描述匹配权重高，完整匹配比单词匹配权重高。比如搜索「notebook edit」时，名字里包含完整「notebook edit」的工具排最前面。

相比简单的包含匹配，评分搜索在工具数量较多时能给出更相关的结果。

找到后标记为已发现：

```python
for s in schemas:
    if "name" in s:
        self._registry.mark_discovered(s["name"])
```

`mark_discovered` 把工具名加入 `_discovered` 集合，下一轮 `get_all_schemas()` 就会包含完整 schema。

ToolSearchTool 自身的 `should_defer = False` 。如果 ToolSearch 也被延迟加载，LLM 连发现工具的工具都找不到了。

## 连接管理

### register\_all\_tools 启动时全量注册

```python
async def register_all_tools(self, registry: ToolRegistry) -> list[str]:
    errors: list[str] = []
    for name, config in self._configs.items():
        try:
            client = MCPClient(config)
            await client.connect()
            self._clients[name] = client
            for td in await client.list_tools():
                registry.register(MCPToolWrapper(name, td, client))
        except Exception as e:
            errors.append(f"MCP server '{name}': {e}")
    return errors
```

逐个连接 MCP 服务器，拉取工具列表，包装成 MCPToolWrapper 注册到全局工具注册表。一个服务器失败不影响其他服务器，错误收集到列表里统一返回。

### 延迟获取与自动重连

`get_client` 带延迟初始化和重连能力：

```python
async def get_client(self, name):
    client = self._clients.get(name)
    if client is None:
        config = self._configs.get(name)
        if config is None: return None
        client = MCPClient(config)
        await client.connect()
        self._clients[name] = client
        return client
    if not client.is_alive:
        await client.close()
        client = MCPClient(self._configs[name])
        await client.connect()
        self._clients[name] = client
    return client
```

客户端不在缓存里就看有没有配置，有就现场创建。如果在缓存里但连接断了，先关旧的，重新创建。每次重连都创建新的 `MCPClient` 实例，避免旧的 `AsyncExitStack` 状态混乱。

### 优雅关闭

```python
async def shutdown(self) -> None:
    for name, client in self._clients.items():
        try:
            await client.close()
        except Exception:
            logger.debug("Error closing MCP server '%s'",
                         name, exc_info=True)
    self._clients.clear()
```

遍历关闭所有客户端。关闭失败只记 debug 日志，不抛异常。 `self._clients.clear()` 清空字典。

`client.close()` 内部的资源释放通过 `AsyncExitStack` 完成：

```python
async def close(self) -> None:
    self._alive = False
    self._session = None
    await self._cleanup_stack()
```

先标记死亡，再释放资源。顺序不能反，否则在资源释放过程中如果有并发调用检查 `is_alive` ，可能误判为存活。 `_cleanup_stack()` 调 `__aexit__` 触发 LIFO 资源释放，子进程、HTTP 客户端、MCP 会话按注册的反序关闭。

## 小结

| 设计决策   | 实现方式                                                                      |
| ------ | ------------------------------------------------------------------------- |
| SDK 依赖 | 官方 `mcp` SDK，不手写 JSON-RPC                                                 |
| 传输层选择  | `config.is_stdio` 分派到 `_connect_stdio` / `_connect_http`                  |
| 资源管理   | `AsyncExitStack` 统一管理子进程、HTTP 客户端、MCP 会话                                  |
| 参数验证   | Pydantic `create_model` 动态生成参数模型                                          |
| 工具调用   | `MCPToolWrapper.execute()` → `client.call_tool()` → `session.call_tool()` |
| 名称隔离   | `mcp_<server>_<tool>` ，f-string 直接拼接                                      |
| 延迟加载   | `should_defer = True` ，评分搜索（10/5/3/1 分制）+ `mark_discovered` 激活            |
| 连接保活   | `is_alive` 属性 + execute 前自动重连                                             |
| 容错     | 单个服务器失败不阻断，错误收集统一返回                                                       |


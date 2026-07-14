**架构定位&#x20;**：本章扩展 ④ 工具层，通过 MCP 协议让工具从「内置」变成「开放生态」。

***

## 你迟早会遇到这个问题

上一章给 GCode 装上了安全刹车，现在工具可以放心用了。但工具系统本身有一个扩展性瓶颈。

如果用户想让 GCode 帮忙查一下 GitHub 上的 Issue 呢？

你得写一个 GitHubIssueTool，实现 Tool 接口，调 GitHub API，处理 OAuth 认证、分页、rate limit、各种错误码。好不容易搞定了，用户又来了：「能不能查询阿里云SLS日志」「能不能操作 MySQL 数据库？」「能不能发 Slack 消息通知团队？」

每个需求都是同一个流程：写代码，实现接口，处理第三方 API 的认证和错误格式，注册到 ToolRegistry，重新编译，发布新版本。GCode 的代码库越来越胖，但你永远追不上用户的需求。一个人想要 GitHub 集成，另一个想要 GitLab，第三个想要 Bitbucket。你不可能把全世界的 API 都实现一遍。

问题出在哪？

出在 **工具的供给和 Agent 的核心是耦合的&#x20;**。Agent 想用新工具，必须由 Agent 的开发者来写代码、编译、发布。第三方开发者没有办法独立地给 GCode 添加工具。

![]()

换个角度想：有没有一种方式，让别人独立开发工具，GCode 动态地接入这些工具，不需要改一行代码，不需要重新编译？

有。这就是 MCP。

***

## USB 的故事

MCP（Model Context Protocol）是一个开放协议，定义了 AI 应用如何和外部能力进行标准化通信。

光看名字可能觉得很抽象。我们用一个你一定熟悉的东西来类比：USB。

回忆一下 USB 出现之前的世界。键盘用 PS/2 接口，打印机用并口，鼠标用串口，扫描仪用 SCSI，每种外设都有自己专用的接口和驱动。你买了一台新电脑，光是接线就能让人头疼半天。更麻烦的是，假设有 M 种电脑接口和 N 种外设，总共需要 M x N 个适配器。这个数字增长得很恐怖。

USB 出现后呢？所有外设统一用一个接口。键盘插 USB，鼠标插 USB，打印机也插 USB。电脑厂商只需要支持 USB 标准，外设厂商也只需要支持 USB 标准。M + N 就搞定了。

![]()

MCP 做的是同样的事情。在 MCP 之前，每个 Agent 想接入每个工具，都需要写专门的对接代码：

```plain&#x20;text
之前：M x N 对接

Agent A ──专用代码──→ GitHub Tool
Agent A ──专用代码──→ MySQL Tool
Agent B ──专用代码──→ GitHub Tool
Agent B ──专用代码──→ MySQL Tool
```

有了 MCP 之后，Agent 只需要实现一次 MCP 客户端，工具只需要实现一次 MCP 服务端，双方就能通信：

```plain&#x20;text
之后：M + N 对接

Agent A ──MCP──→ MCP Server (GitHub)
Agent B ──MCP──→ MCP Server (GitHub)
Agent A ──MCP──→ MCP Server (MySQL)
Agent B ──MCP──→ MCP Server (MySQL)
```

对 GCode 来说，我们只需要实现一次 MCP Client。社区里有人写了 GitHub 的 MCP Server？直接接进来。有人写了数据库的 MCP Server？也直接接进来。不需要改 GCode 的任何代码。

这就是标准化协议的威力。

![]()

***

## MCP 到底由哪些部分构成

很多文章一讲 MCP，就直接开始列 Tools、Resources、Prompts。但如果你只记住这三个词，很容易产生一个误解：MCP 好像只是「Server 提供几个接口给 Agent 调用」。这不完整。

MCP 至少要从两个角度看： **运行时角色&#x20;**&#x548C; **协议层次&#x20;**。

先看运行时角色。官方文档把 MCP 的参与者拆成三个：

* **Host&#x20;**：真正的 AI 应用本体。比如 Claude Desktop、Codex、IDE 插件，或者我们正在构建的 GCode。

* **Client&#x20;**：Host 里的一个连接组件。它负责和某一个 MCP Server 建立连接、发送请求、接收响应。

* **Server&#x20;**：对外暴露能力的程序。它可能运行在本地，也可能运行在远程。

注意这里有个非常容易混淆的点： **GCode 本身是 Host，不是 Client&#x20;**。更准确地说，GCode 这个 Host 内部会创建一个或多个 MCP Client，每个 Client 对应一个 Server。

```plain&#x20;text
GCode（Host）
   │
   ├── MCP Client A ──→ GitHub MCP Server
   ├── MCP Client B ──→ MySQL MCP Server
   └── MCP Client C ──→ Browser MCP Server
```

为什么要这样拆？因为一个 Host 往往要同时连多个 Server。每个连接都有自己的能力协商、生命周期、请求 ID、连接状态。把它们都塞进一个大而全的对象里会很混乱。拆成一个 Host 管多个 Client，结构就清楚了。

![]()

再看协议层次。MCP 可以理解成两层：

* **Data Layer（数据层）&#x20;**：定义消息长什么样、初始化怎么握手、有哪些能力、怎么列工具、怎么调工具。这里的核心是 JSON-RPC 2.0，加上 lifecycle、tools/resources/prompts/notifications 这些语义。

* **Transport Layer（传输层）&#x20;**：定义消息怎么在两边之间传过去。是走 `stdio` ，还是走 `Streamable HTTP` ，属于这一层。

你可以把它想成「信件内容」和「送信方式」的区别。Data Layer 规定信里写什么、格式是什么；Transport Layer 决定是快递送，还是自己跑腿送。内容不变，运输方式可以换。

![]()

这一章我们实现的是 GCode 里的 **MCP Client&#x20;**，重点放在两件事：

1. 理解 Data Layer：握手、工具发现、工具调用。

2. 理解 Transport Layer 如何按 server 类型选择不同接法，并先用 `stdio` 把主流程讲透。

***

## MCP 里双方各提供什么

MCP 最常被提到的是 Server 暴露的三种核心原语（primitives）， 也就是前面说的 **Tools、Resources、Prompts&#x20;**。但如果只讲 Server 这一侧，学生很容易误以为 MCP 是单向的。实际上，Client 这一侧也有自己的能力声明。

先看 Server 这一侧。

第一种是 **Tools&#x20;**，也是最核心的能力。一个 MCP Server 可以暴露一组工具，每个工具有名称、描述和参数的 JSON Schema 定义。比如一个 GitHub MCP Server 可能提供 `search_issues` 、 `create_issue` 、 `list_pull_requests` 这些工具。

```plain&#x20;text
{
  "name": "search_issues",
  "description": "搜索 GitHub Issue",
  "inputSchema": {
    "type": "object",
    "properties": {
      "repo": { "type": "string", "description": "仓库名，格式 owner/repo" },
      "query": { "type": "string", "description": "搜索关键词" },
      "state": { "type": "string", "enum": ["open", "closed", "all"] }
    },
    "required": ["repo"]
  }
}
```

看着眼熟吗？这和我们之前实现的 Tool 接口定义几乎一模一样。名称、描述、参数 Schema，结构完全对得上。唯一的区别是：我们的工具在 GCode 进程内执行，MCP 的工具在一个外部进程里执行。

第二种是 **Resources&#x20;**，可以理解为可读取的数据源。比如一个数据库 MCP Server 可以暴露表结构作为 Resource，Agent 读取它就能了解有哪些表、哪些字段，不用自己去猜：

```plain&#x20;text
{
  "uri": "db://myapp/schema",
  "name": "数据库表结构",
  "mimeType": "application/json"
}
```

Agent 通过 `resources/read` 请求这个 URI，Server 就会返回对应的数据。这有点像 RAG 里的上下文源，用来给 Agent 补充背景信息。

第三种是 **Prompts&#x20;**，是 MCP Server 提供的预定义提示词模板。比如一个 SQL MCP Server 可以提供一个引导 Agent 按正确格式生成查询的 Prompt：

```plain&#x20;text
{
  "name": "generate_query",
  "description": "根据自然语言生成 SQL 查询",
  "arguments": [
    { "name": "table", "description": "目标表名", "required": true },
    { "name": "intent", "description": "查询意图的自然语言描述" }
  ]
}
```

Agent 调用这个 Prompt 时传入参数，Server 返回一段组装好的提示词文本，Agent 拿着这段文本去生成 SQL。这和后面要做的 Skill 系统有异曲同工之处，只不过 Prompt 是由工具提供方定义的，而不是用户自己定义的。

再看 Client 这一侧。MCP 规范里，Client 也可以声明自己支持什么能力。比如：

* **Roots&#x20;**：告诉 Server 当前项目的根目录或工作区边界。

* **Sampling&#x20;**：允许 Server 反过来请求 Host 帮它调用 LLM。

* **Elicitation&#x20;**：允许 Server 请求 Host 向用户追问额外信息。

这说明 MCP 不是一个“Server 只会被动挨打”的协议。它本质上是一个双向的、带能力协商的连接。只是对我们这一章来说，最有教学价值的仍然是 Server 暴露的 **Tools&#x20;**。

为什么？因为 Tools 最直接对应到 Coding Agent 的”手”。Agent 想查 Issue、查数据库、操作浏览器，最后都落在”调用一个外部能力”这件事上。

所以本章的聚焦顺序是：

1. 先把 `Tools` 跑通。

2. 建立对 `Resources` 和 `Prompts` 的概念理解。

3. 知道 `Roots / Sampling / Elicitation` 这些 Client 能力存在，但不在本章展开实现。

***

## 传输层：stdio 和 Streamable HTTP

MCP 的 Data Layer 规定了消息语义，但消息总得有个地方传。这个“怎么传”，就是 Transport Layer 的职责。

截至 `2025-11-25` 版规范，MCP 当前定义的 **标准传输只有两种&#x20;**：

1. `stdio`

2. `Streamable HTTP`

这里有一个特别容易踩坑的历史问题：你在很多旧资料里会看到 `HTTP+SSE` 、 `SSE transport` 这样的说法。那是旧版本协议里的表述。 **在新规范里，HTTP+SSE 已经被 Streamable HTTP 取代了。&#x20;**&#x53;SE 在新规范里已经降级为 `Streamable HTTP` 内部可选的流式机制，不再作为独立的标准传输存在。

那 WebSocket 呢？规范允许实现自定义 transport，但 **WebSocket 不是当前标准传输的一部分&#x20;**。所以讲课时不要把它和 `stdio` 、 `Streamable HTTP` 并列成“官方标准的三四种传输”。

这两个标准传输的区别在于 **Host 和 Server 进程之间怎么通信&#x20;**：

* **stdio&#x20;**：Host 把 MCP Server 作为子进程启动，通过 stdin/stdout 管道读写消息。Server 本身可以访问任何远程服务，比如 GitHub API、数据库、云平台，管道只管 Host 和 Server 之间那一段通信。

* **Streamable HTTP&#x20;**：MCP Server 是一个独立运行的 HTTP 服务，Host 用 HTTP `POST` / `GET` 和它通信，必要时用 SSE 做流式消息。Server 可能在本机，也可能在远端。

注意 stdio 并不意味着「只能做本地的事」。GitHub MCP Server 就是用 stdio 启动的，但它背后调的全是 GitHub 的远程 API。stdio 描述的是 Host 到 Server 的通信方式，跟 Server 自己访问什么资源无关。

真实产品里，这两种通常都要支持。官方 SDK 已经把这层接线封装得比较完整了，所以工程上真正要注意的就一点： **别把 transport 选择和后面的 MCP 主流程耦死&#x20;**。

换句话说，如果你直接使用 MCP SDK，接 `stdio` server 和接 `Streamable HTTP` server，最大的区别通常只是”构造不同的 transport 对象”；后面的 `connect` 、能力协商、 `tools/list` 、 `tools/call` ，走的还是同一套 Client 流程。

***

## stdio 传输：没有网络，没有端口

在 Coding Agent 这个场景下， `stdio` 依然非常值得先讲，因为它最适合第一次把 MCP Client 的骨架讲清楚。产品里 HTTP 同样重要，但 stdio 没有网络、认证、部署这些额外复杂度，能让你专注于协议本身。

stdio 传输是怎么工作的？非常简单：GCode 启动一个子进程来运行 MCP Server，然后通过这个子进程的 stdin 和 stdout 管道来通信。GCode 往子进程的 stdin 写请求，从子进程的 stdout 读响应。就这样。

```plain&#x20;text
GCode 进程
    │
    ├── stdin  ──写入请求──→  MCP Server 子进程的 stdin
    │                              │
    │                              ▼
    │                        MCP Server 处理请求
    │                              │
    └── stdout ←──读取响应──  MCP Server 子进程的 stdout
```

为什么说它巧妙？因为 **不需要网络，不需要端口，不需要服务发现&#x20;**。

你想想传统的 RPC 通信是怎么做的。服务端得监听一个端口，比如 `localhost:8080` ，客户端连接过去。这带来一堆麻烦：端口可能被占用，得处理冲突。防火墙可能阻拦本地连接，得配置规则。如果同时跑多个 MCP Server，每个都要占一个端口，还得管理端口分配。进程挂了端口可能不会立即释放，下次启动会报「address already in use」。

stdio 传输把这些问题全部消除了。MCP Server 就是一个普通的命令行程序，GCode 启动它，通过操作系统的管道通信。不需要额外的网络配置，不需要担心端口占用，不需要服务发现机制。进程启动即可用，退出即清理。进程的生命周期管理是操作系统最擅长的事情。

还有一个小细节：MCP Server 的 stderr 不参与协议通信，它被用来输出日志和调试信息。这个设计很聪明，开发者调试 MCP Server 的时候可以随便往 stderr 打日志，不会干扰协议的正常通信。

另外，根据官方规范，stdio 里的消息是 **UTF-8 编码的 JSON-RPC 消息&#x20;**，通常以换行分隔。Server 的 stdout 上 **不能混入任何非协议内容&#x20;**，否则 Client 就会解析失败。这也是为什么日志一定要走 stderr，而不是 stdout。

所以这章先展开 `stdio` ，更准确的说法是： **先用最短路径把 transport 抽象、子进程生命周期、stdout/stderr 边界、请求响应匹配这些共性问题讲透&#x20;**。

***

## Streamable HTTP 传输：远程 Server 怎么接

理解了 stdio，再看 Streamable HTTP 就容易很多了。两者最大的区别在于：stdio 靠子进程的 stdin/stdout 管道收发消息，Streamable HTTP 靠 HTTP 请求收发消息。

具体来说，Client 把 JSON-RPC 消息通过 HTTP `POST` 发给 Server 的固定端点。Server 处理完后，有两种回复方式：如果结果已经准备好了，直接返回 `application/json` 响应；如果需要流式推送（比如长时间运行的工具），可以返回 `text/event-stream` ，用 SSE 逐步发送结果。

所以 Client 发请求的时候， `Accept` 头必须同时声明这两种：

```plain&#x20;text
Accept: application/json, text/event-stream
```

这样 Server 可以根据情况选择最合适的响应方式。

另一个区别是认证。stdio 的 Server 是本地子进程，天然信任，不需要额外认证。远程 Server 通常需要 API Key 或者 OAuth Token。所以 HTTP transport 要支持自定义请求头，让用户在配置里声明认证信息。

两种 transport 的配置放在一起对比就很清楚了：

```plain&#x20;text
mcp_servers:
  # stdio：有 command 字段 → 启动子进程，走管道
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"

  # Streamable HTTP：有 url 字段 → 发 HTTP 请求
  remote-tool:
    url: "https://api.example.com/mcp"
    headers:
      Authorization: "Bearer ${API_TOKEN}"
```

Manager 看到 `command` 就创建 StdioTransport，看到 `url` 就创建 HTTPTransport。后面的 MCP Client 流程完全一样。

实现上，HTTP transport 比 stdio 简单：不用管子进程生命周期、不用管管道、不用管 stderr。就是发 HTTP 请求、收 HTTP 响应。但它带来了 stdio 没有的问题：网络超时、重试、TLS 证书、认证刷新。这些是工程细节，不影响 MCP 协议本身的理解。

关键设计原则是： **transport 只负责消息的收发，上层的 initialize、tools/list、tools/call 完全不关心底层用的是管道还是 HTTP。&#x20;**&#x628A;这个边界守好，后面加新的 transport 类型就是一个文件的事。

***

## JSON-RPC 2.0：消息格式

不管用什么传输方式，MCP 的消息格式统一使用 **JSON-RPC 2.0&#x20;**。这是一个非常成熟的远程过程调用协议，成熟到有些「无聊」，但正是这种无聊让它变得好用。

JSON-RPC 2.0 只有三种消息类型。

**请求（Request）&#x20;**：有 `id` ，有 `method` ，有 `params` 。Client 发给 Server，期望得到响应。

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_issues",
    "arguments": {
      "repo": "golang/go",
      "query": "generics"
    }
  }
}
```

**响应（Response）&#x20;**：有 `id` （和请求对应），有 `result` 或 `error` 。Server 发给 Client。

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Found 42 issues matching 'generics'..."
      }
    ]
  }
}
```

**通知（Notification）&#x20;**：有 `method` ，但 **没有 id&#x20;**。通知不需要响应，发出去就完了。

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "abc",
    "progress": 0.5,
    "total": 1.0
  }
}
```

通知和请求的区别就看有没有 `id` 字段。有 `id` 就是请求（期望响应），没 `id` 就是通知（不期望响应）。就这么简单。

JSON-RPC 的好处在于它极其简单。任何语言都能生成和解析 JSON，不需要像 gRPC 那样先定义 `.proto` 文件再生成代码。一个 MCP Server 可以用 Python、Node.js、Rust，甚至 Bash 来写，只要它能读写 JSON 就行。这大大降低了生态参与的门槛。

在代码里，我们这样定义 JSON-RPC 消息结构（伪代码）：

```plain&#x20;text
JSONRPCMessage:
    jsonrpc: string          // 固定 "2.0"
    id: optional<integer>    // 请求/响应有，通知无
    method: string           // 请求/通知有
    params: optional<any>    // 请求/通知有
    result: optional<any>    // 成功响应有
    error: optional<RPCError> // 错误响应有

RPCError:
    code: integer
    message: string
    data: optional<any>
```

注意 `id` 是可选的。为什么？因为通知消息没有 `id` 字段，我们需要区分「没有 id」和「id 为 0」这两种情况。在你的语言里，根据类型系统的不同可以用指针、Optional 类型、或者 nullable 来表示。序列化时如果 id 为空，就不输出这个字段。

***

## 一次完整的 MCP 会话长什么样

理解了消息格式，我们来看一个完整的 MCP 会话是怎么进行的。整个过程分三个阶段。

### 第一阶段：初始化握手

GCode（Client）启动 MCP Server 子进程后，第一件事是发送 `initialize` 请求，声明自己的身份和能力。Server 回应自己的身份和能力。就像两个人第一次见面，先自我介绍一下。

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": { "roots": {} },
    "clientInfo": { "name": "GCode", "version": "0.1.0" }
  }
}
```

Client 声明自己的协议版本、支持的能力和身份信息。Server 收到后回应自己的身份和能力：

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": { "tools": {}, "resources": {} },
    "serverInfo": { "name": "github-mcp", "version": "1.0.0" }
  }
}
```

响应里的 `capabilities` 字段告诉 Client 这个 Server 支持哪些能力。比如这里支持 `tools` 和 `resources` ，但不支持 `prompts` 。Client 可以根据这个信息决定后续调用哪些 API。

握手成功后，Client 还要发一个 `notifications/initialized` 通知，告诉 Server「我这边准备好了，可以开始工作了」。注意这是一个通知（没有 id），不需要等待响应。

这里还有两个容易忽略的规范细节。

第一，初始化完成之前，双方不应该乱发普通业务请求。先 `initialize` ，再 `notifications/initialized` ，后面才进入正常会话阶段。否则有些 Server 会直接拒绝请求。

第二，如果底层 transport 不是 stdio，而是 `Streamable HTTP` ，那后续 HTTP 请求还需要带上 `MCP-Protocol-Version` 这样的版本头，明确双方正在说哪一版协议。stdio 没有 HTTP header 这个层，所以这件事只发生在 HTTP transport 里。

### 第二阶段：工具发现

接下来，Client 发送 `tools/list` 请求，获取 Server 提供的所有工具定义。

```plain&#x20;text
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list" }
```

请求很简单，不需要额外参数。Server 返回它提供的所有工具定义：

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      { "name": "search_issues", "description": "搜索 GitHub Issue", "inputSchema": { ... } },
      { "name": "create_issue", "description": "创建 GitHub Issue", "inputSchema": { ... } }
    ]
  }
}
```

拿到工具列表后，GCode 就知道这个 Server 有哪些工具可用了。这些工具定义会被包装成 GCode 内部的 Tool 接口，注册到 ToolRegistry 里。Agent 在下一轮对话中就能看到它们。

### 第三阶段：工具调用

当 Agent 决定使用某个 MCP 工具时，Client 发送 `tools/call` 请求。

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_issues",
    "arguments": { "repo": "golang/go", "query": "generics" }
  }
}
```

Server 执行完工具后返回结果：

```plain&#x20;text
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "text", "text": "Found 42 issues matching 'generics'..." }
    ]
  }
}
```

返回的 `content` 是一个数组，每个元素是一个内容块（Content Block），可以是文本、图片等。对于大多数工具来说，返回的就是一段文本。

整个流程串起来就是： **initialize → notifications/initialized → tools/list → (tools/call) x N&#x20;**。前两步只做一次，后面的工具调用可以重复多次。

***

## 请求-响应的异步匹配

你可能注意到了一个细节：每个请求都有一个 `id` ，响应里也有对应的 `id` 。这不是巧合，这是 JSON-RPC 的核心机制。

在 stdio 传输中，Client 和 Server 通过同一对管道通信。如果 Client 连续发了两个请求（id=1 和 id=2），Server 可能先回复 id=2 再回复 id=1（取决于哪个处理得快）。Client 怎么知道哪个响应对应哪个请求？就靠这个 `id` 。

在实现上，我们用一个字典（map）来管理等待中的请求。发请求时，创建一个等待通道放进字典；收到响应时，根据 id 找到对应的通道把消息发过去。

用伪代码表示核心逻辑：

```plain&#x20;text
function sendRequest(method, params):
    id = nextID++
    responseChan = newChannel()
    pending[id] = responseChan

    writeLine(stdin, serialize({jsonrpc: "2.0", id, method, params}))

    response = waitForEither(responseChan, timeout)
    delete(pending, id)
    if response.error: throw MCPError(response.error)
    return response
```

另一边有一个读取循环，持续从子进程的 stdout 读消息，根据 id 分发到对应的通道：

```plain&#x20;text
// 持续读取子进程 stdout
function readLoop():
    while line = readLine(stdout):
        msg = deserialize(line)

        if msg.id != null:
            // 这是一个响应，分发到等待的通道
            if pending[msg.id] exists:
                pending[msg.id].send(msg)
        // 通知类消息暂不处理

    // 读取循环结束，说明 Server 退出了
    alive = false
```

注意最后一行：当读取循环退出时（说明子进程的 stdout 关闭了），把 `alive` 标记设为 false。后面连接管理器会用到这个标记来判断是否需要重连。

***

## 工具包装器：让 MCP 工具融入 GCode

到这里你可能会想：MCP Server 返回的工具定义和 GCode 内部的 Tool 接口不是一回事，怎么让 Agent 统一使用？

答案是 **适配器模式&#x20;**。我们写一个 MCPToolWrapper，把 MCP 工具「包装」成 GCode 的 Tool 接口。这是一个经典的设计模式：两个接口不兼容，用一个中间层做转换。

用伪代码看看核心部分：

```plain&#x20;text
class MCPToolWrapper implements Tool:
    function name():
        return "mcp_" + serverName + "_" + toolDef.name

    function execute(params):
        result = client.callTool(toolDef.name, params)
        if result.isError: return errorResult(extractText(result))
        return extractText(result)
```

`description()` 和 `parameters()` 直接透传 `toolDef` 里的原始值。 `extractText` 从 Server 返回的 `content` 数组中提取所有 `text` 类型的块，拼接成一个字符串返回。

工具名加了 `mcp_` 前缀和 Server 名称，比如 `mcp_github_search_issues` 。为什么要这么做？因为不同的 MCP Server 可能提供同名的工具。一个 GitHub Server 有 `search` 工具，一个 Jira Server 也有 `search` 工具，不加前缀就冲突了。

包装完成后，MCP 工具和内置工具在 Agent 看来没有任何区别。都实现了 Tool 接口，都可以被 ToolRegistry 管理，都出现在 system prompt 的工具列表中。Agent 不需要知道一个工具是本地代码实现的，还是通过 MCP 协议调用了一个 Python 写的外部程序。这就是抽象的力量。

***

## 配置：让用户告诉 GCode 该连哪些 Server

MCP Server 需要用户来配置。你总不能让 GCode 自己去猜用户想连哪些 Server 吧？配置也遵循我们之前建立的多级作用域模式。

项目级配置放在 `.gcode.yaml` 里，只在当前项目生效：

```plain&#x20;text
# 项目级 .gcode.yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"

  database:
    command: "python"
    args: ["-m", "mcp_server_sqlite", "--db", "./data.db"]
```

用户级配置放在 `~/.gcode/config.yaml` 里，在所有项目生效：

```plain&#x20;text
# 用户级 ~/.gcode/config.yaml
mcp_servers:
  slack:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-slack"]
    env:
      SLACK_TOKEN: "${SLACK_TOKEN}"
```

合并策略很直觉：项目级优先，同名 Server 项目级覆盖用户级。这和 Git 配置的 `--local` 优先于 `--global` 是同一个思路。GitHub Server 你可能每个项目配不同的 Token，所以放项目级。Slack 是通用的，放用户级。

注意 `env` 里的 `${GITHUB_TOKEN}` 语法。它引用的是当前环境变量的值，而不是把 Token 明文写在配置文件里。这样你可以安全地把配置文件提交到 Git，Token 通过环境变量注入。

配置的解析和合并逻辑用伪代码表示：

```plain&#x20;text
MCPConfig:
    command: string
    args: list<string>
    env: map<string, string>

function mergeConfigs(projectConfigs, userConfigs):
    merged = copy(userConfigs)
    for name, config in projectConfigs:
        merged[name] = config  // 项目级覆盖用户级
    return merged
```

***

## 完整流程：从配置到调用

现在把所有组件串起来，看看一个 MCP 工具从发现到被使用的完整流程：

1. **启动&#x20;**：读取配置文件，获取 MCP Server 列表

2. **选择 transport&#x20;**：根据 Server 配置选择 `stdio` 或 `Streamable HTTP`

3. **后台连接&#x20;**：启动时异步连接所有配置的 Server

4. **初始化&#x20;**：发送 initialize + notifications/initialized

5. **工具发现&#x20;**：发送 tools/list，获取工具定义

6. **包装注册&#x20;**：为每个工具创建 MCPToolWrapper，注册到 ToolRegistry

7. **Agent 使用&#x20;**：Agent 在工具列表中看到 MCP 工具，决定是否调用

8. **工具调用&#x20;**：Agent 调用 → MCPToolWrapper.execute → MCP Client → MCP Server

9. **结果返回&#x20;**：MCP Server 返回结果 → MCPToolWrapper 转换 → Agent 处理

关于步骤 2 和步骤 3 有两个设计选择。

第一个是：transport 要不要先抽象出来？答案是最好要。因为真实产品通常同时接本地 `stdio` server 和远程 `Streamable HTTP` server。

如果你一开始就把“连接建立”和“协议收发”完全写死在子进程逻辑里，后面就很难并列接入 HTTP。

比较合理的做法是： **先把 transport interface 立住，再用 stdio 作为本章的完整示例实现。**

第二个是：什么时候连接 MCP Server？MCP 协议要求调用 `tools/list` 才能拿到工具定义，而 `tools/list` 必须在连接建立之后才能发。

也就是说， **不连接就不可能知道 Server 有哪些工具&#x20;**。

如果等到 Agent 第一次尝试调用时才连接（懒加载），Agent 根本不知道有这些工具存在，也就不会去调用它们——这是一个鸡生蛋的死循环。

所以实践中，包括 Claude Code 在内的主流 Coding Agent，都采用 **启动时后台连接所有 Server&#x20;**&#x7684;策略：启动后立即异步连接，拿到工具列表注册到 ToolRegistry。

这样 Agent 第一轮（或前几轮）对话就能在 system prompt 中看到 MCP 工具。连接缓存住，后续复用；部分 Server 连接失败不阻止启动，只打警告。

在应用初始化代码里集成 MCP 大概是这样（伪代码）：

```plain&#x20;text
function setupMCP(config, registry):
    manager = new MCPManager()
    manager.loadConfigs(config)

    err = manager.registerAllTools(registry)
    if err != null:
        log.warn("some MCP servers failed to connect: " + err)
        // 不要抛异常，部分 Server 失败不应阻止启动

    return manager
```

注意这里即使某些 MCP Server 连接失败，我们也只是打个警告日志，不阻止 GCode 启动。用户配置了 5 个 Server，其中一个因为 Token 过期连不上，不应该影响其他 4 个的正常使用。

***

## 工具延迟加载：80 个工具塞不进上下文

上一节解决了 MCP Server 的连接时机：不连就不知道有哪些工具，所以必须启动时主动连接。但连上之后，新的问题来了。

假设用户配置了 4 个 MCP Server，每个提供 15-20 个工具，加上 GCode 自己的 6 个内置工具，工具列表一下子膨胀到 80 个。每个工具的完整 schema 包含名称、描述、参数定义和类型约束，平均占 100 到 300 个 token。80 个工具就是 8,000 到 24,000 个 token 的工具定义，每一轮对话都要带着。还没开始干正事，上下文窗口就被工具定义吃掉了一大块。

token 浪费只是表面问题。更深层的影响是模型的选择质量。当工具列表里挤满了几十个名字相似的工具（比如 Grafana 下面有 query\_prometheus、query\_prometheus\_histogram、query\_loki\_logs、query\_loki\_stats），模型需要在这些选项里做决策。Anthropic 在工程博客 Advanced Tool Use 中公布了量化数据：50 个以上工具的场景下，启用延迟加载后 token 开销降低约 85%，Opus 4 的工具选择准确率从 49% 提升到 74%。工具太多确实会干扰模型判断。

解决思路是：不需要每轮都把所有工具的完整 schema 塞给模型。大部分 MCP 工具在一次对话里可能根本用不到，为什么要让它们占着上下文窗口？

延迟加载的机制分四步。第一步，MCP 工具在注册时标记自己为「延迟工具」。MCPToolWrapper 的 ShouldDefer() 固定返回 true，意思是「我的完整 schema 默认不进模型的工具列表」。第二步，Agent Loop 每轮生成工具列表时，跳过这些延迟工具的完整 schema，只在 system-reminder 里列出它们的名字。第三步，模型看到名字列表，判断需要某个工具时，先调用 ToolSearch 拉取它的完整定义。第四步，ToolSearch 在客户端的 Registry 里找到工具、返回完整 schema、标记为「已发现」，从下一轮开始这个工具就会出现在正常的工具列表里。

用伪代码描述这个流程：

```plain&#x20;text
// 每轮 Agent Loop 构建工具列表
function buildToolList(registry):
    tools = []
    deferredNames = []
    for tool in registry.allTools():
        if tool.shouldDefer() and not registry.isDiscovered(tool.name):
            deferredNames.append(tool.name)    // 只记名字
        else:
            tools.append(tool.fullSchema())    // 完整 schema

    if deferredNames is not empty:
        systemReminder += "以下工具可通过 ToolSearch 加载：\n"
                       + join(deferredNames, "\n")
    return tools

// ToolSearch 被模型调用时
function toolSearchExecute(query, registry):
    if query.startsWith("select:"):
        schemas = registry.findByNames(query)      // 精确查找
    else:
        schemas = registry.searchByKeyword(query)   // 关键词搜索

    for schema in schemas:
        registry.markDiscovered(schema.name)        // 标记为已发现
    return schemas
```

ToolSearch 支持两种查询模式。 `select:mcp__grafana__query_prometheus` 按名称精确拉取，适合模型已经知道要用哪个工具的场景。直接输入关键词（比如「prometheus」）则在所有延迟工具的名称和描述里做搜索，适合模型不确定具体工具名的场景。

这套机制完全在客户端实现，不依赖任何 LLM 厂商的专有协议。Anthropic 的 API 提供了原生的 defer\_loading 字段，但这是专有特性，智谱 GLM、OpenAI GPT 系列都不支持（发过去会被静默忽略）。客户端自实现 ToolSearch 是唯一的跨厂商方案，Claude Code 自身也是在客户端层做延迟加载管理。

所以 GCode 的默认策略是：第三章的 6 个内置工具始终可见，数量少、使用频率高，没必要延迟。本章引入的所有 MCP 工具全部延迟，因为 MCP 工具数量不可控，用户加一个 Server 就可能多出几十个工具。这个「内置常驻、MCP 延迟」的分界，也是 Claude Code 采用的做法。

***

## 安全考量：信任边界

在本章的 `stdio` 实现里，MCP Server 是外部程序， 运行在 GCode 的子进程中 。这里有一个重要的信任边界需要考虑。

第一， **工具审批&#x20;**。MCP 工具和内置工具一样，受权限系统管控。Agent 想调用 MCP 工具时，一样需要经过权限检查。你可以按工具名配置权限规则：

```plain&#x20;text
# 允许所有 GitHub MCP 工具
- rule: mcp_github_*(*)
  effect: allow

# 禁止所有 MCP 的删除操作
- rule: mcp_*_delete_*(*)
  effect: deny
```

第三， **命令白名单&#x20;**。理论上配置文件里可以写任意命令。如果你的团队对安全要求比较高，可以考虑限制允许运行的 MCP Server 命令，防止配置文件中的恶意命令。不过这个在我们目前的实现中暂不做，先留个口子。

***

## 本章小结

这一章我们让 GCode 从「封闭工具集」变成了「开放工具生态」。

核心思路其实很简单：定义一个标准化的协议（MCP），让 Host、Client、Server 按统一规则协作。Host 是 GCode 本体，Client 是它内部负责连接某个 Server 的组件，Server 则提供 Tools、Resources、Prompts 这些能力。Data Layer 负责规定消息语义，Transport Layer 负责规定消息怎么传。

在当前官方规范里，标准 transport 主要是 `stdio` 和 `Streamable HTTP` 。真实的 Coding Agent 往往两种都要支持，只是接法上通常由 SDK 负责大部分细节：你按 server 配置选对 transport，后面照常 `connect` 、发现工具、调用工具就行。消息格式用 JSON-RPC 2.0，工具包装器把 MCP 工具适配成内部的 Tool 接口，对 Agent 完全透明，连接管理器则负责缓存和生命周期。

MCP 的引入是一个架构上的质变。在此之前，GCode 的能力边界由你这个开发者决定，你实现了什么工具，Agent 就能用什么工具。在此之后，能力边界由整个生态决定，任何人都可以开发 MCP Server，GCode 都能接入。 从「产品」到「平台」，就差这一步。GCode 现在工具够多了，但对话越长，上下文窗口越紧张。下一章讲上下文管理，解决 token 持续增长的问题。

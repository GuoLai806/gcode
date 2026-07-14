# 第7章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装上了权限系统， 五层权限拦截 让工具调用变得安全可控。但你有没有发现一个问题：GCode 能用的工具，全部是你亲手写的。ReadFile、WriteFile、Bash、Grep、Glob，每一个都编译进二进制，想加新工具就得改代码、重新发版。

这一章要让 GCode 从「封闭工具集」变成「开放工具生态」。做完之后，用户在配置文件里声明一个 MCP Server，GCode 就能自动接入它提供的工具，不用改一行代码。GitHub Issue 查询、数据库操作、Slack 消息，社区写好了 MCP Server，直接接进来就能用。

具体要新增这些东西：

* **JSON-RPC 2.0 协议类型&#x20;**：请求、响应、通知三种消息的编解码

* **Transport 抽象 + 两种实现&#x20;**：stdio（子进程管道通信）和 Streamable HTTP（远程 Server）

* **MCP Client&#x20;**：初始化握手、工具发现、工具调用、请求-响应异步匹配

* **MCPToolWrapper&#x20;**：适配器，把 MCP 工具包装成 GCode 内部的 Tool 接口

* **MCP Manager&#x20;**：连接缓存、配置合并、生命周期管理

* **环境变量隔离&#x20;**：子进程只拿到 PATH + 显式声明的变量，不泄露敏感信息

这章 **不做&#x20;**：SSE 流式推送、Resources/Prompts 消费、Sampling/Elicitation 等 Client 侧高级能力。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：实现一个 MCP 客户端，让 GCode 在启动时自动发现并注册外部 MCP Server 提供的工具。用户在配置文件里声明 Server 列表，GCode 就能通过标准化的 MCP 协议把这些工具无缝接进工具中心，Agent 使用时完全无感。

技术要求：

- 支持两种传输：本地子进程走 stdio 管道，远程走 Streamable HTTP
- 按 JSON-RPC 2.0 收发消息，处理请求和响应的异步配对（请求带 id，回包按 id 关联）
- 一次会话分三步：初始化握手、列出工具、调用工具
- 用适配层把发现到的远端工具包装成 GCode 已有的 Tool 接口注册进去，Agent 调用时无感
- 多个 Server 的连接做缓存和生命周期管理，单个 Server 挂了不影响其他
- 从配置文件读取 Server 列表，支持用户级、项目级两层合并

这一步先不做 MCP 的资源、提示词、采样这些非工具能力，也不做 Server 健康检查和自动重连。

配置格式：

- 在配置文件里用一个 map 声明 Server 列表，每个 key 是 Server 名字
- stdio 类型填 command、args、env（env 的值支持 ${VAR} 展开）
- HTTP 类型填 url 和 headers（值同样支持 ${VAR} 展开）
- 同样按用户级、项目级两层合并，后面的盖前面的
```

然后 AI 就会开始问你问题，进行需求澄清。

![]()

你根据理论篇学到的内容回答这些问题，一直这样反复循环对齐需求，最后就能生成四份文档了。



### 正式开发

四份文档有了之后，就相当于施工图纸已经定好了，然后让 Claude Code 根据这四份文档进行开发

![]()

经过一段时间后，开发完成。

![]()

### 功能验证过程

来验收一下结果，现在配置里加上我们的context7 mcp，



config里配置如下

![]()

然后启动GCode，如果连接正常的话，ui会显示连接正常，以及注册的工具

![]()



跟它说

我们可以看到模型决定调用 MCP 工具，GCode 通过 MCP 协议把请求转给外部 Server，Server 执行后返回结果，模型基于结果回答。



![]()



整个过程对模型来说，MCP 工具和内置工具没有任何区别。



要说内部Function Calling和MCP的一个大差别就是MCP更像是外部生态的一个工具注册中心，对于互联网上的系统而言，是打破生态孤岛的一个重要手段，将一个个生态链接起来，形成更加庞大强大的大生态。



验收没问题，那么本章的主要任务就完成了。下一章，我们给 GCode 加上上下文管理能力。

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

```markdown
# MCP 客户端 Spec## 背景ch01–ch06 已经把 gcode 砌成了一个能自主多轮干活、且有五层安全护栏的 coding agent。但**工具集是写死的 6 个内置工具**（读 / 写 / 改文件、命令执行、按模式找文件、搜内容）——想让它会用 GitHub、查数据库、调内部服务，只能改源码、重新编译，能力边界锁死在编译期。

MCP（Model Context Protocol）是一套开放标准，用统一的 JSON-RPC 协议把"提供工具的一方（server）"与"使用工具的一方（client）"解耦，社区已有大量现成 server（GitHub、Slack、SQLite、文件系统……）。ch07 给 gcode 装上 **MCP 客户端**：启动时按配置自动发现并连接外部 server，把它们的工具包装成 gcode 已有的工具抽象、注册进工具中心，Agent 调用时与内置工具**完全无感**，并自动复用 ch06 的权限护栏。这是从"工具集固定"到"工具生态可插拔"的一跃——给 gcode 装上扩展坞。

## 目标- **配置驱动的自动发现**：启动时从配置声明的 server 列表自动连接、列出工具、注册进工具中心，无需改代码。
- **两种传输**：本地 server 走子进程标准输入输出管道（stdio）；远程 server 走 Streamable HTTP。
- **标准三步会话**：每个 server 一次连接经过 初始化握手 → 列出工具 → 按需调用工具（协议细节由官方 Go SDK `github.com/modelcontextprotocol/go-sdk/mcp` 承载，不自研协议栈）。
- **无感适配**：发现到的远端工具包装成与内置工具一致的抽象，Agent 编排层与 provider 适配层均无需感知其来自远端。
- **命名空间隔离**：远端工具统一加 `mcp__<server>__<tool>` 前缀，杜绝与内置工具及多 server 间的重名冲突，并保留来源可追溯。
- **多 server 生命周期管理**：每个连接各自独立缓存与管理；单个 server 连接 / 初始化 / 列工具失败只跳过它自身，不影响其它 server、不影响启动；程序退出时统一、干净地关闭全部连接（含终止 stdio 子进程）。
- **两层配置合并**：server 列表从 **用户级** 与 **项目级** 两个配置文件读取合并，项目级覆盖用户级同名 server。
- **凭据不落盘**：配置中环境变量与请求头的值支持从宿主环境变量展开（`${VAR}`），密钥不写进配置文件。
- **复用权限**：MCP 工具天然走 ch06 的「规则 → 模式兜底 → 人在回路」链路，默认按命令执行类每次确认，自报只读（`readOnlyHint`）的按只读类放行并可并发；权限包**零改动**。
- **不破坏既有能力**：ch01–ch06 的会话、Loop、流式、缓存、规划、权限五层等行为不退化。

## 功能需求- **F1: 两层 YAML 配置加载与合并**
  从**用户级** `~/.gcode/config.yaml` 与**项目级** `<root>/.gcode.yaml` 两个文件读取 `mcp_servers` 段（map：key 为 server 名，value 为 server 定义）；按 server 名合并，**项目级同名 server 完整覆盖用户级**（不做字段级合并，避免半合并出畸形 server）。文件缺失视为空 `mcp_servers`；文件格式非法时**跳过该文件并 stderr 告警**，绝不致启动失败、不 panic。`mcp_servers` 顶层不存在或为空，视为零个 MCP server，正常进 TUI。

- **F2: server 类型与必填字段**
  每个 server 定义自带 `type` 字段（**显式**：`stdio` 或 `http`），不靠字段嗅探判定类型。
  - `stdio` 类型必填 `command`（字符串）；可选 `args`（字符串数组）、`env`（字符串 map）。
  - `http` 类型必填 `url`（字符串）；可选 `headers`（字符串 map）。
  字段缺失或 `type` 非法时**跳过该 server 并 stderr 告警**，不影响其它 server 加载。

- **F3: 环境变量展开**
  `env` 与 `headers` 的**值**支持 `${VAR}` 形式从宿主环境变量取值；展开发生在配置加载阶段、不污染原始配置文件。**未定义的 `${VAR}` 展开为空串并 stderr 告警**，但不阻断该 server 启动（让 server 自行决定无凭据时是否报错）。`command` / `args` 与 server 名、工具名**不做展开**（避免命令/名字被环境间接影响产生隐性歧义）。

- **F4: stdio 传输**
  对 `stdio` 类型 server，以 `command` + `args` 启动子进程；通过子进程的标准输入输出按 JSON-RPC 帧通信（由 SDK 完成）。`env` 与宿主进程环境合并后注入子进程（同名宿主变量被 `env` 覆盖，便于按 server 配置注入凭据）。`stderr` 透传给宿主 stderr 便于排查。子进程在 gcode 退出时一并干净终止（关闭其 stdin → 等待 → 必要时发信号；由 SDK 承载）。

- **F5: Streamable HTTP 传输**
  对 `http` 类型 server，以 `url` 为 endpoint 走 Streamable HTTP；配置中的 `headers` 注入每次 HTTP 请求（用于 `Authorization` 等鉴权头）。**不订阅服务器推送的独立 SSE 通道**（本章只用请求-响应式工具调用，无需 server 主动推送），减少长连接维护成本。

- **F6: 标准三步会话**
  每个 server 建立后依次完成 **initialize 握手**（交换 protocolVersion 与 capabilities）→ **`tools/list` 列出工具** → 进入按需 **`tools/call` 调用**阶段。整个协议层（JSON-RPC 编解码、请求/响应 id 配对、握手细节、传输细节）**由官方 Go SDK 承载**，不自研协议栈。本章只覆盖工具能力，**不订阅 / 不实现** MCP 的资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）等其它能力。

- **F7: 工具适配（远端工具 ↔ 内置 Tool 抽象）**
  把 server 返回的每个远端工具包装成一个实现 gcode `Tool` 接口的对象，注册进工具中心：
  - **名字**：`mcp__<server>__<tool>`（见 F8）。
  - **描述**：直接取远端 `description`（空则给一个含 server 名的兜底说明）。
  - **参数 schema**：把远端 `inputSchema` 转成 gcode 的 `map[string]any` 形式（透传 JSON Schema），不二次裁剪。
  - **只读性**：远端 `annotations.readOnlyHint==true` → `ReadOnly()==true`；其余（含字段缺失/非法）→ `false`（安全默认按有副作用处理）。
  - **执行**：调用时通过该 server 的会话发 `tools/call`；远端返回的 `content` 中 `type=text` 的文本块按顺序拼成 gcode `Result.Content`，远端 `isError==true` 映射为 `Result.IsError==true`；非 text 块（image / audio / resource_link / embedded_resource 等）静默丢弃并 stderr 告警一次；调用过程中协议错误（连接断、超时、传输错）也转成 `IsError==true` 的结构化错误**回灌给模型**（不抛 Go error 给 Agent Loop，复用 ch04/ch05 不中断会话的契约）。Agent 与 provider 适配层不感知"该工具来自远端"。

- **F8: 工具命名空间**
  所有 MCP 工具统一以 `mcp__<server>__<tool>` 命名（`server` 与 `tool` 名按配置/远端原样保留）。命名空间用途双重：
  - **避免冲突**：同名远端工具在不同 server 互不干扰；与 6 个内置工具天然不重名。
  - **可追溯**：单看工具名能识别来源 server，便于日志、人在回路弹窗、权限规则书写。
  注册时若仍发生同名（同 server 自报多个同名工具的边界情形）则后注册者保留并 stderr 告警；若工具名经前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`），**跳过该工具并 stderr 告警**。

- **F9: 启动同步连接 + 单 server 30s 超时 + 失败隔离**
  在进入 TUI 之前**同步**对所有配置中的 server 发起连接 + 握手 + 列工具（实现可并发以缩短总时延）；**每个 server 的整个启动序列受 30s 超时约束**（内置不可配）。任一 server 的连接 / 握手 / 列工具失败或超时**只跳过它自身**：gcode 启动不被阻断、其它 server 与内置工具集照常注册可用、stderr 给出该 server 的失败原因。所有 server 连接尝试结束后才进入 TUI；进入 TUI 时工具中心呈现的就是"内置 6 工具 + 成功连上的 server 工具"全集，Agent 在任意一轮看到的工具集稳定不变。

- **F10: 工具调用超时**
  每次 `tools/call` 复用 30s 超时（与连接超时同值，**内置不可配**）；超时按 F7 转成 `IsError==true` 的结构化错误回灌给模型，Agent Loop 继续。

- **F11: 退出时统一关闭**
  gcode 正常退出（用户主动退出、致命错收尾）时，对所有已建立的会话统一调用关闭逻辑：stdio server 的子进程被干净终止（先关 stdin、给 server 自然退出窗口、必要时发信号），HTTP server 的会话用 DELETE 通知 server 释放（由 SDK 处理）。退出**不**强行等待所有连接关闭完成超过若干秒（整体兜底 5s，避免某 server 卡住拖死整个程序退出）。

- **F12: ch06 权限链路无感复用**
  MCP 工具走 ch06 现有判定链路：
  - 黑名单仅作用于内置 `bash` 命令串，对 MCP 工具不命中（`extractTarget` 对未知工具返回 target=""，自动跳过）。
  - 沙箱仅作用于内置文件类工具，对 MCP 工具不适用（`extractTarget` 对未知工具返回 `isFile=false`，自动跳过）。
  - 规则引擎按 `mcp__<server>__<tool>` 作为友好名匹配（`friendlyName` 对未知名原样返回）；用户可用精确名 `mcp__github__create_issue` 或带 `*` 的 `mcp__github__*` 写 allow/deny 规则。
  - 模式兜底：`ReadOnly()==true` 的 MCP 工具归 `CategoryRead`，default 下直接放行、可并发；其余归 `CategoryExec`，default 与 acceptEdits 下每次触发人在回路 Ask；bypass 下放行。
  **permission 包源码零修改**，只通过既有公共行为承载。

## 非功能需求

- N1: 失败隔离不阻塞——单 server 任意阶段（连接 / 握手 / 列工具 / 调用）失败或卡住，只跳过它自身、不阻塞 gcode 启动、不影响其它 server 与内置工具；连接卡住时 30s 超时强制收尾，绝不死锁。
- N2: 安全默认——`readOnlyHint` 缺失或非法 → 非只读（默认走 Ask）；`${VAR}` 未定义 → 空串（不替 server 拍板）；type 非法 / 字段缺失 → 跳过该 server（不静默放行未定义 server）。
- N3: 跨协议一致——MCP 工具行为与 provider（Anthropic / OpenAI）无关；provider 适配层零修改。
- N4: ch06 权限零改动——permission 包源码零修改；MCP 工具走既有判定链路。
- N5: 不破坏 ch01–ch06——会话、Loop、流式、缓存、规划、人在回路、并发、用户取消、保序回灌等既有能力不退化。
- N6: 凭据不落盘——api_key / token 不出现在配置文件；env / headers 通过 `${VAR}` 引用宿主环境；敏感值在日志/状态栏/任何输出中不回显。
- N7: 退出干净——程序退出时不泄漏子进程、不泄漏 goroutine、不死锁；某 server 关闭卡住不阻塞整体退出（整体退出关闭兜底超时 5s）。
- N8: 代码规范——gofmt / goimports / go vet / go test ./... 全过（本项目为 Go，遵循 CLAUDE.md）。

## 不做的事- **MCP 资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）**——本章只覆盖工具能力。
- **tools/list 变更通知 / 调用进度通知**——不订阅独立 SSE 通道（SDK 默认开，本章显式关闭），工具集快照固定在启动时。
- **健康检查 / 自动重连 / 退避**——单连接挂掉就挂掉，留待后续章节。
- **配置热加载 / 运行时增减 server**——重启 gcode 才能应用新配置。
- **本地级 mcp_servers 配置层**——仅两层（用户级 + 项目级）。
- **mcp_servers 字段级合并**——按 server 名维度合并，同名项目级完整覆盖用户级。
- **`command` / `args` / 工具名 / server 名 的变量展开**——仅 env / headers 的值展开 `${VAR}`。
- **OAuth 完整鉴权流程**——仅支持 `headers` 直传静态 token；需要 OAuth 的 server 让用户自行预换 token 写入 headers。
- **自定义连接 / 调用超时**——30s 硬编码，不暴露配置项。
- **MCP 工具的黑名单与路径沙箱扩展**——这两层只对内置工具有意义，MCP 工具仅走规则 + 模式兜底 + 人在回路。
- **非文本内容块的回灌**——仅收集 `type=text` 的内容块拼成 Result；image / audio / resource_link / embedded_resource 等静默丢弃并 stderr 告警一次。
- **资源配额 / 速率限制 / 审计日志**——与 ch06 不做事项一致。
- **MCP server 端的实现**——gcode 仅作 client。

## 验收标准

- AC1: 配置加载与两层合并——`~/.gcode/config.yaml` 与 `<root>/.gcode.yaml` 都存在时，按 server 名合并；同名 server 项目级完整覆盖用户级；任一文件缺失或非法时跳过该文件、不致启动失败、其它正常加载。（F1/N1）
- AC2: 字段校验——stdio 类型缺 command、http 类型缺 url、type 非法或缺失时，该 server 被跳过并 stderr 告警，其它 server 不受影响。（F2/N2）
- AC3: 变量展开——env / headers 的值 `${VAR}` 从宿主环境取值；未定义变量展开为空串并告警；command / args / 工具名 / server 名不展开。（F3/N2/N6）
- AC4: stdio 启动 + 子进程终止——能拉起一个 stdio MCP server 子进程，握手 + 列工具成功；env 注入生效；gcode 退出时子进程被终止、无僵尸。（F4/F6/F11/N7）
- AC5: HTTP 连接 + 自定义 headers——能对一个 HTTP MCP server 完成握手 + 列工具；`headers` 注入到 HTTP 请求中。（F5/F6/N6）
- AC6: 工具适配与命名——同一 server 的工具列出后注册进 registry，名字符合 `mcp__<server>__<tool>`，描述非空，参数 schema 透传；调用时远端 text content 拼接为 Result.Content，远端 isError 映射到 Result.IsError；非 text 块静默丢弃。（F6/F7/F8）
- AC7: 命名空间隔离——同名工具来自不同 server 不互相覆盖；与 6 个内置工具天然不重名；前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）的工具被跳过并告警。（F8）
- AC8: 启动失败隔离 + 30s 超时——单 server 连接 / 握手 / 列工具失败或超时，只跳过它自身，其它 server 与内置工具集照常注册；失败原因 stderr 可见；启动总时延上界受 30s 约束（并发实现）。（F9/N1）
- AC9: 调用超时与错误回灌——`tools/call` 30s 超时或协议错误转为 `IsError==true` 的结构化错误结果回灌给模型，Agent Loop 不中断，可在后续轮调整。（F7/F10/N5）
- AC10: 退出干净——程序退出时所有 stdio 子进程被终止、HTTP 会话被关闭；关闭过程不泄漏 goroutine、不卡死（总超时 5s 兜底）。（F11/N7）
- AC11: 权限链路自然命中——`mcp__<server>__*` 形式的 allow / deny 规则正确作用到对应 MCP 工具；未写规则时 `readOnlyHint==true` 的 MCP 工具按只读类放行并可并发，其余按命令执行类触发人在回路 Ask；bypass 模式下放行（黑名单 / 沙箱对 MCP 工具不命中，自动跳过）。（F12/N4）
- AC12: 跨协议一致——同一 MCP server 在 Anthropic 与 OpenAI 两种 provider 下行为一致；provider 适配层零 diff。（N3）
- AC13: 不破坏 ch01–ch06——既有所有测试通过；多轮连环、用户取消、流出错恢复、历史一致、缓存命中、规划按轮次注入、ch06 五层权限等行为不退化。（N5）
- AC14: 凭据不落盘——配置示例与说明均用 `${VAR}` 引用密钥；`git grep` 在配置文件中无 token 明文命中。（N6）
- AC15: 代码规范——`gofmt -l .` 无输出；`go vet ./...` 无告警；`go test ./...` 与 `go test -race ./internal/mcp/...` 通过。（N8）
```

````markdown
# MCP 客户端 Plan> 技术栈：Go（go 1.25.8）；使用 **官方 SDK** `github.com/modelcontextprotocol/go-sdk/mcp` 承载协议层（JSON-RPC 编解码、initialize 握手、stdio 与 Streamable HTTP 传输）。本章新增 **mcp 包** 与 main 装配，**不改 tool / agent / tui / permission / llm / config / conversation / prompt**。

## 架构概览- **mcp 包（新增）**：承载 MCP 客户端的全部职责——配置加载与两层合并、`${VAR}` 展开、字段校验、调用 SDK 建立 stdio / HTTP 会话、把远端工具适配成内置 `tool.Tool`、统一管理生命周期。仅依赖 `tool`、SDK 与标准库；不依赖 agent / tui / permission / conversation。
- **main（改造）**：在 `tool.NewDefaultRegistry()` 之后、`permission.NewEngine` 与 `tui.New` 之前，加载 mcp 配置 → 启动 Manager → 把 Manager 产出的工具注册进 registry → 退出时 `defer mgr.Close()`。
- **tool 包（零改）**：`Registry.Register` 与 `Tool` 接口本就是开放抽象，直接吃 mcpTool 实例；`IsReadOnly` 对 MCP 工具返回正确值。
- **agent / tui 包（零改）**：工具流转链路对工具来源透明。
- **permission 包（零改）**：`friendlyName` 对未知名原样返回 → 规则可写 `mcp__<server>__<tool>`；`categorize` 在 `readOnly==true` 时走 CategoryRead、否则归 CategoryExec → 模式兜底矩阵自然命中；`extractTarget` 对未知工具返回 `("", false, false)`，黑名单与沙箱自动跳过。
- **llm / provider（零改）**：工具定义透传，协议无关。

数据流（单次调用）：
```
agent.executeBatched(calls, mode)
  └→ eng.Check(...)  → Allow → registry.Execute(name, args)
       └→ mcpTool.Execute(ctx, args)              [本章新增工具实现]
            ├→ ctx2 = context.WithTimeout(ctx, 30s)
            ├→ session.CallTool(ctx2, {Name: remoteName, Arguments: map})
            └→ 拼接 text content / 映射 isError / 协议错转 IsError
       └→ tool.Result{Content, IsError}            ── 回灌 conv
```

## 核心数据结构### mcp.Config / mcp.ServerConfig（对外）
```go
// Config 是 mcp_servers 在内存中的归一化形式（已展开 ${VAR}、已合并、已校验）。
type Config struct {
    Servers map[string]ServerConfig // key = server 名
}

// ServerConfig 是单个 MCP server 的完整定义。
type ServerConfig struct {
    Type    string            // "stdio" | "http"
    Command string            // stdio 必填
    Args    []string          // stdio 可选
    Env     map[string]string // stdio 可选（已展开）
    URL     string            // http 必填
    Headers map[string]string // http 可选（已展开）
}
```

### mcp.Manager（对外不透明）
```go
type Manager struct {
    mu       sync.Mutex
    sessions []*session  // 已建立成功的 server 会话（用于 Close）
    tools    []tool.Tool // 已适配好的工具（供 main 注册进 registry）
}

type session struct {
    name string
    cs   *sdkmcp.ClientSession
}
```

### 工具适配（包内私有）
```go
// mcpTool 实现 tool.Tool。
type mcpTool struct {
    fullName   string         // "mcp__<server>__<tool>"
    remoteName string         // server 上的原始工具名
    descr      string
    schema     map[string]any // JSON Schema 透传
    readOnly   bool           // 仅来自远端 annotations.readOnlyHint==true
    cs         callerSession  // 接口形式持有，便于单测注入 stub
}

// callerSession 是 mcpTool 依赖的最小会话能力（生产实现是 *sdkmcp.ClientSession）。
type callerSession interface {
    CallTool(ctx context.Context, params *sdkmcp.CallToolParams) (*sdkmcp.CallToolResult, error)
}
```

## 核心接口

```go
// 加载并合并两层配置；返回归一化的 Config。
// - root: 项目根（用来定位 <root>/.gcode.yaml）
// - 文件不存在 → 视为空层；格式非法 → 跳过该层 + stderr 告警（降级，N1）
// - 内部完成 ${VAR} 展开与字段校验（非法 server 直接剔除，N2）
// - 永不返回 error；签名留 error 仅为未来扩展（当前实现恒为 nil）
func LoadConfig(root string) (Config, error)

// 启动 Manager：并发连接所有 server，每个 server 30s 超时，失败仅跳过 + 告警。
// 阻塞直到所有 server 的尝试结束（成功 / 失败 / 超时）。
// version 透传到 Implementation.Version（便于 server 端识别 gcode 版本）。
func NewManager(ctx context.Context, cfg Config, version string) *Manager

// 返回适配好的工具列表（按 server 名 → 工具名 稳定排序）。
func (m *Manager) Tools() []tool.Tool

// 关闭所有会话（stdio 子进程终止、HTTP DELETE）；总超时 5s 兜底，绝不阻塞退出。
func (m *Manager) Close()
```

## 模块设计### internal/mcp/config.go
**职责：** 加载两层 YAML、合并、展开 `${VAR}`、校验。
**关键点：**
- 内部 `rawConfig { McpServers map[string]rawServer `yaml:"mcp_servers"` }`；`rawServer` 含全部可能字段（Type/Command/Args/Env/URL/Headers）。
- `loadFile(path) (rawConfig, error)`：文件不存在 → 空 + nil err；`yaml.Unmarshal` 失败 → 零值 + err（调用方降级）。
- `expandVars(s string) (out string, undefined []string)`：正则 `\$\{([A-Za-z_][A-Za-z0-9_]*)\}`，未定义变量记录到 undefined（供告警）。**仅作用于 env/headers 的值**。
- `applyExpansion(name string, srv *rawServer)`：对 env/headers 的每个值跑 expandVars；未定义变量在 stderr 输出 `[mcp] warn: undefined env var ${X} referenced by server <name>`。
- `mergeServers(user, project map[string]rawServer)`：遍历 user；遍历 project，同名直接整对象覆盖。
- `validateServer(name string, srv rawServer) (ServerConfig, bool)`：
  - `Type` 必为 `"stdio"` 或 `"http"`，否则跳过；
  - `stdio` 必填 `Command`；`http` 必填 `URL`；缺失则跳过；
  - 违规时 stderr 告警 `[mcp] warn: skip server <name>: <reason>`。
- `LoadConfig(root string)`：
  - 用户级 = `os.UserHomeDir() + "/.gcode/config.yaml"`；项目级 = `<root>/.gcode.yaml`。
  - 两层各自 `loadFile` + `applyExpansion`；任一层解析失败 stderr 一行告警并跳过（该层视为空）。
  - `mergeServers` 后逐个 `validateServer`，组装 `Config`。

### internal/mcp/manager.go
**职责：** 连接 server、缓存会话、关闭。
**关键点：**
- `NewManager(ctx, cfg, version)`：
  - 对每个 server 起 goroutine 并发连接；`sync.WaitGroup` 等齐。
  - 每个 goroutine：`ctx2, cancel := context.WithTimeout(ctx, 30*time.Second); defer cancel()`。
  - 按 type 构造 transport：
    - **stdio**：`cmd := exec.CommandContext(ctx2, srv.Command, srv.Args...)`；`cmd.Env = mergeOSEnv(srv.Env)`；`cmd.Stderr = os.Stderr`；`transport := &sdkmcp.CommandTransport{Command: cmd}`。
    - **http**：`hc := &http.Client{Transport: &headerRoundTripper{base: http.DefaultTransport, headers: srv.Headers}}`；`transport := &sdkmcp.StreamableClientTransport{Endpoint: srv.URL, HTTPClient: hc, DisableStandaloneSSE: true}`。
  - `client := sdkmcp.NewClient(&sdkmcp.Implementation{Name: "gcode", Version: version}, nil)`。
  - `cs, err := client.Connect(ctx2, transport, nil)` ← 自动完成 initialize 握手。
  - `lst, err := cs.ListTools(ctx2, nil)`；err → 一行 stderr 告警，**调 `cs.Close()` 释放连接**（避免连了但列工具失败时的连接泄漏），return。
  - 对每个返回工具调 `adaptTool(serverName, t, cs)`，成功的 push 到 manager 切片。
  - 所有写共享状态走 `manager.mu`。
- `mergeOSEnv(extra map[string]string)`：把 `os.Environ()` 转成 map，再用 `extra` 覆盖，最后还原为 `KEY=VAL` 切片返回。同名宿主变量被 extra 覆盖（让 server 配置注入的凭据生效）。
- `headerRoundTripper{ base http.RoundTripper; headers map[string]string }`：`RoundTrip(req)` 中 `for k,v := range headers { req.Header.Set(k, v) }`，再 `base.RoundTrip(req)`。
- `Tools()`：稳定排序（先 server 名再 tool 名）。
- `Close()`：对每个 session 起 goroutine 调 `cs.Close()`；`select { case <-allDone: case <-time.After(5*time.Second): }` 兜底。

### internal/mcp/tool.go
**职责：** 把 SDK 返回的 `*sdkmcp.Tool` 适配为 `tool.Tool`。
**关键点：**
- `adaptTool(serverName string, t *sdkmcp.Tool, cs callerSession) (*mcpTool, bool)`：
  - `fullName = "mcp__" + serverName + "__" + t.Name`。
  - **禁用字符校验**：用正则 `^[A-Za-z0-9_-]+$` 校验 `fullName`，否则返回 `(nil, false)` + stderr 告警 `[mcp] warn: skip tool <fullName>: contains illegal characters`。
  - `descr`：`t.Description` 为空时兜底 `"来自 MCP server " + serverName + " 的工具 " + t.Name`。
  - `schema`：`b, _ := json.Marshal(t.InputSchema); var m map[string]any; json.Unmarshal(b, &m)`；解出空 map 时给 `{"type":"object"}` 兜底（避免 provider 拒收空 schema）。
  - `readOnly`：`t.Annotations != nil && t.Annotations.ReadOnlyHint`（nil-safe）。
- `(*mcpTool).Name() string { return m.fullName }`、`Description/Parameters/ReadOnly` 同理。
- `(*mcpTool).Execute(ctx, args)`：
  - `ctx2, cancel := context.WithTimeout(ctx, 30*time.Second); defer cancel()`。
  - 把 `json.RawMessage` 解到 `map[string]any`（空参数视为 `nil`）；解析失败 → `Result{Content: "参数解析失败: ...", IsError: true}`。
  - `res, err := m.cs.CallTool(ctx2, &sdkmcp.CallToolParams{Name: m.remoteName, Arguments: argMap})`。
  - `err != nil` → `Result{Content: "MCP 工具调用失败: " + err.Error(), IsError: true}`（含 ctx 超时）。
  - 否则：遍历 `res.Content`，把 `*sdkmcp.TextContent` 的 `.Text` 拼接；非 text 块计数，首次出现时 stderr 一行告警（per fullName 限一次，用包级 `sync.Map` + `LoadOrStore`）。
  - 返回 `tool.Result{Content: collected, IsError: res.IsError}`。

### cmd/gcode/main.go（改造）
位置：在 `registry := tool.NewDefaultRegistry()` 之后、`permission.NewEngine` 之前插入：
```go
mcpCfg, _ := mcp.LoadConfig(root)
mgr := mcp.NewManager(context.Background(), mcpCfg, version)
defer mgr.Close()
for _, t := range mgr.Tools() {
    registry.Register(t)
}
```
（`root` 复用现有的 `os.Getwd()` 结果；version 复用 `const version`。）

### cmd/smoke/main.go（不改）
smoke 用 `NewDefaultRegistry` 不接 MCP，保持非交互简单。

## 文件组织

```
gcode/
├── internal/mcp/
│   ├── config.go        — 新：Config/ServerConfig、LoadConfig、loadFile、expandVars、mergeServers、validateServer
│   ├── config_test.go   — 新：两层合并 / 变量展开 / 字段校验 / 降级 单测
│   ├── manager.go       — 新：Manager、NewManager（并发+30s 超时）、Close（5s 兜底）、Tools、headerRoundTripper、mergeOSEnv
│   ├── manager_test.go  — 新：连接成功/失败/超时、Close 不死锁、共享状态并发安全
│   ├── tool.go          — 新：mcpTool、callerSession、adaptTool、Execute
│   └── tool_test.go     — 新：命名拼接、禁用字符跳过、Execute 各分支（成功/远端 IsError/超时/协议错/非 text 块）
├── cmd/gcode/main.go  — 改：装配 mcp.Manager，注册 MCP 工具，defer Close
├── go.mod               — 改：添加 github.com/modelcontextprotocol/go-sdk
├── go.sum               — 改：依赖校验和
├── docs/ch07/
│   ├── spec.md / plan.md / task.md / checklist.md
│   └── mcp-servers.example.yaml — 新：配置示例（用 ${VAR}）
└── （其它包零改）
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 协议层实现 | 官方 Go SDK（`github.com/modelcontextprotocol/go-sdk`） | 用户拍板；避免自研 JSON-RPC/握手/帧；SDK 已处理 stdio 与 Streamable HTTP |
| 配置文件位置 | 项目级 `<root>/.gcode.yaml` + 用户级 `~/.gcode/config.yaml` | 用户拍板；项目级 dotfile 一眼可见、与现有 `.gcode/config.yaml`（providers 凭据）分离 |
| 配置层数 | 仅两层，无本地级 | 用户拍板；`${VAR}` 已让密钥不入配置，本地层冗余 |
| 合并语义 | server 名维度，项目级完整覆盖 | 避免字段级半合并出畸形 server |
| server 类型字段 | 显式 `type: stdio\|http` | 不靠字段嗅探（防止误判）；未来扩展易加（如 sse） |
| 变量展开范围 | 仅 env/headers 的值 | 避免 command/args/server 名/工具名被环境间接影响；凭据走 env/headers 已足够 |
| 未定义变量 | 空串 + 一次性告警（不阻断） | server 自决无凭据时是否能跑；gcode 不替它拍板 |
| 工具命名 | `mcp__<server>__<tool>` | 用户拍板；Claude Code 风格；LLM 工具名安全字符；一眼识别来源 |
| 启动连接策略 | 同步进 TUI 前完成 + 并发每 server 30s 超时 + 失败跳过 | 进 TUI 时工具集稳定；并发缩短总时延；隔离避免单 server 拖死启动 |
| 调用超时 | 30s 硬编码，转 IsError | 与连接同值；不中断 Loop；避免长卡 |
| readOnly 适配 | 严格只信 `annotations.readOnlyHint==true` | 默认走 Ask，最严；声明只读才放行 |
| 资源/提示词/采样/roots | 不实现 | 本章只覆盖工具能力 |
| 独立 SSE 通道 | `DisableStandaloneSSE: true` | 只用请求-响应；省一条长连接；减少复杂度 |
| 非 text 内容块 | 静默丢弃 + 一次性告警 | 模型只能消费文本；丢弃比假装回灌更诚实 |
| 错误回灌 | 协议错/超时均转 IsError | 与 ch04/ch05 不中断 Loop 契约一致 |
| 退出关闭 | 每 session.Close 并发 + 5s 总超时兜底 | 避免某 server 卡死阻塞退出 |
| permission 接入方式 | 零改动；靠 `friendlyName` 原样 + `categorize` 按 readOnly 优先 | 复用现成链路；权限规则可写 `mcp__server__tool` 与 `mcp__server__*` |
| HTTP 自定义 headers | `http.RoundTripper` 包装注入 | SDK 暴露 `HTTPClient` 字段；RoundTripper 是标准 Go 做法；不引入额外抽象 |
| OAuth | 不实现完整流程 | 用户预换 token 写 headers；本章范围最小化 |
| Execute 接口注入 | mcpTool 持 `callerSession` 接口而非具体 `*ClientSession` | 单测可注入 stub；生产代码无运行时开销 |

## 模块交互

```
main.main()
  ├─ tool.NewDefaultRegistry()                    // 6 内置工具
  ├─ mcp.LoadConfig(root)                         // 读两层 yaml + ${VAR} 展开 + 校验
  ├─ mcp.NewManager(ctx, cfg, version)            // 并发连接所有 server，30s/各
  │     └─ 对每个 server：
  │         ├─ 构造 transport（stdio:CommandTransport / http:StreamableClientTransport）
  │         ├─ NewClient + Connect（自动 initialize 握手）
  │         ├─ ListTools
  │         └─ adaptTool 包装成 mcpTool
  ├─ for t in mgr.Tools(): registry.Register(t)
  ├─ permission.NewEngine(root)
  ├─ tui.New(...) ; m.Run()
  └─ defer mgr.Close()                            // stdio 终止子进程，HTTP DELETE 会话；5s 总超时兜底
```

调用链（Agent 视角，工具来源透明）：
```
agent.executeBatched(calls, mode)
  └ permission.Check(mode, call, registry.IsReadOnly(call.Name))
       (MCP 工具：friendlyName 原样；categorize：readOnly==true→Read, 否则→Exec；
        extractTarget(未知工具)→isFile=false,target="" → 黑名单/沙箱自动跳过)
  └ Allow → registry.Execute(name, args)
       └ mcpTool.Execute(ctx, args)
            ├ context.WithTimeout(ctx, 30s)
            └ cs.CallTool → 拼接 text / 映射 IsError / 协议错转 IsError
  └ tool.Result 回灌 conv
```

依赖方向（无环）：`main → mcp → {tool, llm, SDK, 标准库}`；`mcp` 不依赖 agent / tui / permission / conversation。
````

````markdown
# MCP 客户端 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改   | `go.mod` / `go.sum` | 添加 `github.com/modelcontextprotocol/go-sdk` 依赖 |
| 新建 | `internal/mcp/config.go` | `Config`/`ServerConfig`、`LoadConfig`、`loadFile`、`expandVars`、`applyExpansion`、`mergeServers`、`validateServer` |
| 新建 | `internal/mcp/config_test.go` | 两层合并 / `${VAR}` 展开 / 字段校验 / 降级 单测 |
| 新建 | `internal/mcp/tool.go` | `callerSession` 接口、`mcpTool`、`adaptTool`、`Execute`、非 text 块告警 once 池 |
| 新建 | `internal/mcp/tool_test.go` | 命名拼接 / 禁用字符 / Execute 成功 / 远端 IsError / 超时 / 协议错 / 非 text 块跳过 单测 |
| 新建 | `internal/mcp/manager.go` | `Manager`、`session`、`NewManager`（并发 + 30s 超时）、`Close`（5s 兜底）、`Tools`、`headerRoundTripper`、`mergeOSEnv` |
| 新建 | `internal/mcp/manager_test.go` | 连接成功/失败/超时、Close 不死锁、并发写共享状态安全 单测 |
| 改   | `cmd/gcode/main.go` | 装配 `mcp.LoadConfig`、`mcp.NewManager`、注册 MCP 工具、`defer Close` |
| 新建 | `docs/ch07/mcp-servers.example.yaml` | 配置示例（含 stdio / http 各一个，用 `${VAR}`） |

---

## T1: 添加 MCP Go SDK 依赖**文件：** `go.mod`、`go.sum`
**依赖：** 无
**步骤：**
1. 在仓库根执行 `go get github.com/modelcontextprotocol/go-sdk/mcp@latest`。
2. `go mod tidy` 整理依赖；查看 `go.mod` 确认 `github.com/modelcontextprotocol/go-sdk vX.Y.Z` 出现在 `require` 区块。
3. 写一段最小试编（可直接放进后续 `tool.go` 的 import 中）：`import sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"` 并使用一次 `sdkmcp.NewClient`，验证可用。

**验证：** `go build ./...` 编译通过；`go.mod` 内出现 SDK 依赖行。

## T2: 配置类型与加载（含两层合并 + 变量展开 + 字段校验）**文件：** `internal/mcp/config.go`、`internal/mcp/config_test.go`
**依赖：** T1
**步骤：**
1. 定义对外类型 `Config`、`ServerConfig`（见 plan.md「核心数据结构」）。
2. 定义内部 `rawConfig { McpServers map[string]rawServer ``yaml:"mcp_servers"`` }`；`rawServer` 含全部字段。
3. `loadFile(path string) (rawConfig, error)`：
   - 文件不存在 → `(rawConfig{}, nil)`；
   - `os.ReadFile` 出错（非 NotExist）→ `(rawConfig{}, err)`；
   - `yaml.Unmarshal` 失败 → `(rawConfig{}, err)`（调用方降级）。
4. `expandVars(s string) (out string, undefined []string)`：
   - 正则 `\$\{([A-Za-z_][A-Za-z0-9_]*)\}` 匹配；用 `os.LookupEnv` 取值；未定义记录变量名到 `undefined`。
5. `applyExpansion(name string, srv *rawServer)`：
   - 对 `srv.Env`、`srv.Headers` 的每个值跑 `expandVars`，原地替换；
   - 收集所有 undefined 变量名，去重；首次出现时 `fmt.Fprintf(os.Stderr, "[mcp] warn: undefined env var ${%s} referenced by server %s\n", v, name)`。
6. `mergeServers(user, project map[string]rawServer) map[string]rawServer`：
   - 新建 map，复制 user；
   - 遍历 project，直接整对象覆盖同名 key。
7. `validateServer(name string, srv rawServer) (ServerConfig, bool)`：
   - `srv.Type` 必为 `"stdio"` 或 `"http"`，否则跳过；
   - `stdio` 必填 `Command`；`http` 必填 `URL`；缺失则跳过；
   - 违规时 `fmt.Fprintf(os.Stderr, "[mcp] warn: skip server %s: %s\n", name, reason)`；返回 `(zero, false)`。
8. `LoadConfig(root string) (Config, error)`：
   - 用户级 = `filepath.Join(home, ".gcode", "config.yaml")`（`os.UserHomeDir` 失败时跳过用户层不致错）；项目级 = `filepath.Join(root, ".gcode.yaml")`。
   - 两层各自 `loadFile`；err（非 NotExist）→ 一行 stderr 告警 + 该层视为空。
   - 对每层各 server 跑 `applyExpansion`。
   - `mergeServers` 后逐个 `validateServer`，收齐合法 server 组装 `Config`。
   - 永不返回 error（签名留 error 仅为未来扩展，当前实现恒为 `nil`）。

**验证：** `go build ./internal/mcp/...`；`go test ./internal/mcp/...` 覆盖：
- 两文件缺失 → `Config.Servers` 为空、无 err；
- 仅用户级 / 仅项目级 / 都有（同名 server 项目级胜出，断言字段为项目级值）；
- 文件格式非法 → 跳过该层、其它正常加载、stderr 有告警（可在测试中重定向 stderr 断言）；
- `${VAR}` 已定义 → 展开为环境值；未定义 → 空串 + 告警；`command`/`args` 中含 `${VAR}` → 不展开（保留字面量）；
- type 缺失 / type 非法 / stdio 缺 command / http 缺 url → 该 server 被跳过，其它 server 不受影响。

## T3: 工具适配（mcpTool）**文件：** `internal/mcp/tool.go`、`internal/mcp/tool_test.go`
**依赖：** T1
**步骤：**
1. `import sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"`；`import "gcode/internal/tool"`。
2. 定义最小接口 `callerSession` 与 `mcpTool` 结构体（见 plan.md「核心数据结构」）。
3. 实现 `tool.Tool` 接口的 5 个方法（`Name`/`Description`/`Parameters`/`ReadOnly` 均返回字段；`Execute` 见下）。
4. `adaptTool(serverName string, t *sdkmcp.Tool, cs callerSession) (*mcpTool, bool)`：
   - `fullName := "mcp__" + serverName + "__" + t.Name`；
   - 用包级编译好的 `var validName = regexp.MustCompile(``^[A-Za-z0-9_-]+$``)` 校验 `fullName`，不通过 → `(nil, false)` + stderr 告警 `[mcp] warn: skip tool <fullName>: name contains illegal characters`。
   - `descr := t.Description`；空则兜底 `"来自 MCP server " + serverName + " 的工具 " + t.Name`。
   - `schema`：`b, _ := json.Marshal(t.InputSchema)`；`var m map[string]any`；`json.Unmarshal(b, &m)`；若 `m == nil || len(m) == 0` → 用 `map[string]any{"type": "object"}` 兜底。
   - `readOnly := t.Annotations != nil && t.Annotations.ReadOnlyHint`。
5. `Execute(ctx context.Context, args json.RawMessage) tool.Result`：
   - `ctx2, cancel := context.WithTimeout(ctx, 30*time.Second); defer cancel()`。
   - 把 `args` 解到 `map[string]any`：空 / 全空白 → `nil`；否则 `json.Unmarshal`，失败 → `tool.Result{Content: "参数解析失败: " + err.Error(), IsError: true}`。
   - `res, err := m.cs.CallTool(ctx2, &sdkmcp.CallToolParams{Name: m.remoteName, Arguments: argMap})`。
   - `err != nil` → `tool.Result{Content: "MCP 工具调用失败: " + err.Error(), IsError: true}`。
   - 否则遍历 `res.Content`：
     - 类型断言 `*sdkmcp.TextContent`：把 `.Text` 拼到 strings.Builder（块间用 `"\n"` 分隔）；
     - 非 text 块：计数 + 通过包级 `var nonTextWarnOnce sync.Map` 对 `fullName` `LoadOrStore` 一次 stderr 告警 `[mcp] warn: tool <fullName> returned non-text content blocks (dropped)`。
   - 返回 `tool.Result{Content: collected, IsError: res.IsError}`。

**验证：** `go test ./internal/mcp/...` 覆盖：
- 合法 server 名 + 工具名 → adaptTool 返回成功；含 `.` / `@` 等非法字符 → 跳过 + 告警；
- description 空 → 兜底文案出现；schema nil → `{"type":"object"}`；schema 透传成功；
- `t.Annotations == nil` → readOnly=false（不 panic）；`ReadOnlyHint=true` → readOnly=true；
- Execute：注入 stub `callerSession`，覆盖：成功（多 text 块拼接） / 远端 `IsError=true` 映射 / `CallTool` 返回 err 转 `IsError=true` / ctx 超时（用 stub 阻塞 + 短超时单测覆盖，或直接断 `errors.Is(err, context.DeadlineExceeded)` 转 IsError） / 非 text 块跳过 + collected 仅含 text。

## T4: 连接管理器（Manager）**文件：** `internal/mcp/manager.go`、`internal/mcp/manager_test.go`
**依赖：** T2、T3
**步骤：**
1. 定义 `Manager` 与 `session` 结构（见 plan.md）。
2. `headerRoundTripper` 与 `RoundTrip` 实现：
   ```go
   type headerRoundTripper struct {
       base    http.RoundTripper
       headers map[string]string
   }
   func (h *headerRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
       req = req.Clone(req.Context())
       for k, v := range h.headers {
           req.Header.Set(k, v)
       }
       return h.base.RoundTrip(req)
   }
   ```
3. `mergeOSEnv(extra map[string]string) []string`：把 `os.Environ()` 转 map，用 extra 覆盖同名键，再还原为 `KEY=VAL` 切片。
4. `NewManager(ctx context.Context, cfg Config, version string) *Manager`：
   - 内部 `mgr := &Manager{}`；`var wg sync.WaitGroup`。
   - 对 `cfg.Servers` 中每个 `(name, srv)`，`wg.Add(1)` 起 goroutine。
   - goroutine 内：
     - `ctx2, cancel := context.WithTimeout(ctx, 30*time.Second); defer cancel(); defer wg.Done()`。
     - 按 srv.Type 构造 transport。
     - `client := sdkmcp.NewClient(&sdkmcp.Implementation{Name: "gcode", Version: version}, nil)`。
     - `cs, err := client.Connect(ctx2, transport, nil)`；err → 告警 `[mcp] warn: connect server <name> failed: <err>` + return。
     - `lst, err := cs.ListTools(ctx2, nil)`；err → 告警 + `cs.Close()` + return。
     - 对每个 tool 调 `adaptTool`；成功的入临时 slice。
     - 取 `mgr.mu`：`mgr.sessions = append(...)`、`mgr.tools = append(mgr.tools, adapted...)`。
   - `wg.Wait()` 后稳定排序 `mgr.tools`（先 server 名再 tool 名；用 `sort.Slice` + `mcpTool.fullName` 即可，因为 fullName 已带 server 前缀）。
   - 返回 `mgr`。
5. `Tools() []tool.Tool`：返回 `m.tools` 的拷贝（防外部修改）。
6. `Close()`：
   - 对每个 `session` 起 goroutine 调 `cs.Close()`；`WaitGroup` 等齐。
   - 用 `done := make(chan struct{})` + `time.After(5*time.Second)` 实现总超时兜底；超时即 return 不等。

**验证：** `go test ./internal/mcp/...` 覆盖：
- 空 `cfg` → Manager 无 sessions、`Tools()` 空、`Close()` 立即返回；
- 失败隔离：构造一个 stdio server 指向不存在的 command + 一个用单测注入 stub 的成功"server"，断言 stub 工具被注册、失败 server 仅产生告警；
- 超时收尾：注入一个会卡住的连接 stub（接口替身把 SDK 调用替换成手写阻塞），把 30s 在测试中通过 `var connectTimeout = 30*time.Second` 包级变量改为短值（如 200ms），断言超时窗口内被跳过；
- Close 兜底：注入一个 Close 阻塞的 session，断言 `Close()` 在 5s 内（测试中改为短值）返回；
- 并发安全：`go test -race` 通过。

实现注释：把 30s 与 5s 改成包级 `var` 而非 `const`，便于单测在 setup 中临时改小，结束 restore。

## T5: main 接线**文件：** `cmd/gcode/main.go`
**依赖：** T2、T3、T4
**步骤：**
1. import `gcode/internal/mcp` 与 `context`（若没有）。
2. 在 `registry := tool.NewDefaultRegistry()` 行之后、`permission.NewEngine` 之前插入：
   ```go
   mcpCfg, _ := mcp.LoadConfig(root)
   mgr := mcp.NewManager(context.Background(), mcpCfg, version)
   defer mgr.Close()
   for _, t := range mgr.Tools() {
       registry.Register(t)
   }
   ```
3. `root` 复用现有 `os.Getwd()` 结果（已在 main 中）；`version` 复用 `const version`。

**验证：** `go build ./...`；无 MCP 配置时 `go run ./cmd/gcode` 能正常进 TUI、内置 6 工具可用；配置一个 command 不存在的 stdio server 时进 TUI 不阻塞、stderr 显示连接失败告警。

## T6: 配置示例**文件：** `docs/ch07/mcp-servers.example.yaml`
**依赖：** 无（可与 T2 并行）
**步骤：**
1. 内容（用 YAML 注释说明放置位置与覆盖语义）：
   ```yaml
   # 项目级放 <root>/.gcode.yaml；用户级放 ~/.gcode/config.yaml。
   # 同名 server 项目级完整覆盖用户级。
   # env / headers 的值支持 ${VAR} 从宿主环境变量展开；command/args 不展开。
   mcp_servers:
     github:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-github"]
       env:
         GITHUB_TOKEN: "${GITHUB_TOKEN}"
     local-sqlite:
       type: stdio
       command: python
       args: ["-m", "mcp_server_sqlite", "--db", "./data.db"]
     example-http:
       type: http
       url: "https://mcp.example.com/mcp"
       headers:
         Authorization: "Bearer ${EXAMPLE_TOKEN}"
   ```

**验证：** 在 `config_test.go` 增加一个用例，读取此示例文件断言三个 server 都被解析成功。

## T7: tmux 端到端实跑（CLAUDE.md 开发原则）**文件：** —
**依赖：** T1–T6
**步骤：**
1. 准备一个真实可用的 stdio MCP server。优先用 `npx -y @modelcontextprotocol/server-everything`（官方示例 server，自带 echo / add 等基础工具）；若无 npx，可临时用一个最小 Python/JS server。
2. 在项目根写一个临时 `.gcode.yaml` 指向它：
   ```yaml
   mcp_servers:
     demo:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-everything"]
   ```
3. `tmux` 起 gcode：
   - 启动日志（stderr）显示 server 连接成功 + 工具数；TUI 状态栏正常；
   - 让模型调用 `mcp__demo__echo` 一类工具：default 模式下弹人在回路 → 允许本次 → 工具结果回灌 → 模型续答；
   - 选"永久允许"后，本地权限规则被写入；重启 gcode 后再调同工具不再弹窗（验证永久规则与 ch07 命名空间联动）；
   - 切到 bypassPermissions：调用不弹窗；但让模型跑 `rm -rf /` 仍被内置黑名单拦下（MCP 工具不绕过黑名单的内置作用域）；
   - Esc 取消弹窗：干净回到 idle，不退出程序；
   - `q` 退出 gcode 后 `ps -ef | grep server-everything` 确认子进程已终止；
4. 配置一个 command 不存在的 server + 一个能跑的 server：启动 stderr 有失败告警，能跑的 server 工具仍可用。

**验证：** 上述全部观察通过；删除临时 `.gcode.yaml`，恢复项目根干净。

## T8: 全量编译测试与规范**文件：** —
**依赖：** T1–T7
**步骤：**
1. `gofmt -l .`（应无输出）；goimports 分组检查（`gcode/internal/mcp` 应在本地包组）。
2. `go vet ./...`（应无告警）。
3. `go build ./...`；`go test ./...`；`go test -race ./internal/mcp/... ./internal/agent/... ./internal/tui/...`。
4. `git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'`（应无命中：凭据不落盘）。
5. `git check-ignore -q docs/ch07/mcp-servers.example.yaml` 不需要忽略（示例只含 `${VAR}`）。

**验证：** 全部通过。

## 执行顺序

```
T1(SDK 依赖) ─┬─→ T2(config) ─┐
              │                ├─→ T4(manager) ─→ T5(main 接线) ─→ T7(tmux 实跑) ─→ T8(规范)
              └─→ T3(tool)   ─┘
                                 └─→ T6(配置示例)（可与 T2 并行）
```
依赖：T2,T3 ← T1；T4 ← {T2,T3}；T5 ← {T2,T3,T4}；T6 独立于 T3、T4（可在 T2 完成后做）；T7 ← T1–T5；T8 ← 全部。
````

```markdown
# MCP 客户端 Checklist

> 每一项通过运行代码或观察行为来验证；函数 / 类型名仅作定位提示，核验断言本身不依赖其命名（重命名实现而行为不变时本清单仍适用）。

## 实现完整性
- [ ] 加载两层配置：两文件存在时按 server 名合并、同名 server 项目级完整覆盖用户级（验证：单测构造两层文件断言合并结果与字段来源）。(AC1/F1)
- [ ] 配置降级：任一文件缺失视为空、格式非法跳过该文件 + stderr 告警 + 其它正常加载，不致启动失败（验证：单测分别投喂缺失与非法 YAML，断言 `LoadConfig` 不返回致命 err 且其它层 server 仍在）。(AC1/N1)
- [ ] 字段校验：stdio 缺 command、http 缺 url、`type` 非法或缺失，均跳过该 server + stderr 给出原因，其它 server 不受影响（验证：单测分别构造各非法 server）。(AC2/N2)
- [ ] `${VAR}` 展开：env / headers 的值被展开；未定义变量展开为空串 + 一次性告警；command / args / 工具名 / server 名不展开（验证：单测覆盖各分支，含 `command: ${X}` 应保留字面量）。(AC3/F3)
- [ ] stdio 连接 + 握手 + 列工具：能拉起一个 MCP server 子进程并由 SDK 完成 initialize 握手 + ListTools；`env` 被注入到子进程环境（验证：用单测脚本启动一个最小 echo MCP server 或 tmux 实跑 `@modelcontextprotocol/server-everything`）。(AC4/F4/F6)
- [ ] HTTP 连接 + 自定义 headers：能对 HTTP MCP server 完成握手 + 列工具；`headers` 真正出现在每个 HTTP 请求中（验证：用 `httptest.NewServer` 起一个最小 SSE 端点 + 注入 `Authorization` 头，断言 server 端收到该头）。(AC5/F5/F6/N6)
- [ ] 工具命名：所有 MCP 工具的 `Name()` 形如 `mcp__<server>__<tool>`；前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）的工具被跳过并告警（验证：单测构造含 `.` 的 server 名 / 工具名，断言 `adaptTool` 返回 `(nil, false)`）。(AC6/AC7/F8)
- [ ] 命名空间隔离：同一 tool 名在不同 server 互不覆盖；与 6 个内置工具天然不重名（验证：registry 注册后断言全名集合无重复）。(AC7/F8)
- [ ] 工具适配字段：description 空 → 兜底文案；schema 透传为 `map[string]any`、空 schema 兜底 `{"type":"object"}`；`annotations.readOnlyHint==true` → `ReadOnly()==true`，其它（含 nil / false）→ `false`（验证：单测覆盖各分支，含 `Annotations==nil` nil-safe）。(AC6/F7)
- [ ] 调用结果聚合：Execute 把远端多个 text content 块按顺序拼成 `Content`；非 text 块（image/audio/resource_link/embedded_resource）静默丢弃 + 单 tool 限一次告警（验证：tool_test 注入 stub 返回混合内容块，断言 collected 仅含 text 且告警计数为 1）。(AC6/F7)
- [ ] 远端错误映射：远端 `isError==true` 时 `Result.IsError==true`，`Content` 仍为远端 text（验证：tool_test 注入 stub 返回 `isError=true` + text 块）。(AC6/F7)
- [ ] 协议错与超时回灌：`CallTool` 返回 err 或 30s 超时 → `Result.IsError==true` 且 `Content` 含可读错因，Agent Loop 不中断（验证：tool_test 注入 stub 返回 err / 阻塞至超时，断言 IsError 与文案）。(AC9/F7/F10/N5)
- [ ] 启动失败隔离：有 server 连接 / 握手 / 列工具失败时，只跳过它自身，其它 server 与内置工具集照常注册可用（验证：manager_test 用一个失败 server + 一个 stub 成功 server，断言成功 server 工具被注册）。(AC8/F9/N1)
- [ ] 30s 启动超时：模拟连接卡住的 server 在（测试中缩短的）超时窗口结束后被跳过，启动不阻塞超过该窗口（验证：manager_test 注入连接 stub 阻塞 + 短超时配置，断言 `NewManager` 在超时窗口附近返回）。(AC8/F9/N1)
- [ ] 退出干净：`Manager.Close()` 终止所有 stdio 子进程、断开 HTTP 会话；某 session 关闭卡住时 5s 兜底返回不阻塞（验证：manager_test 注入卡住的 Close stub + 短兜底，断言 `Close()` 在兜底时间内返回；tmux 实跑 `q` 退出后 `ps` 无残留子进程）。(AC10/F11/N7)

## 集成
- [ ] 权限链路自然命中：无规则时 `readOnlyHint=true` 的 MCP 工具走 Read 兜底（default 直接放行）、其余走 Exec 兜底（default Ask）；allow 规则 `mcp__<server>__*` 命中时直接放行；bypass 模式放行（验证：用 `permission.NewEngine` 对 mcp 全名调用断言裁决；tmux 实跑见场景 4）。(AC11/F12/N4)
- [ ] permission 包零改动：`git diff internal/permission/` 在 ch07 期间无任何修改（验证：本章结束时核对 diff 范围）。(N4)
- [ ] provider 适配层零改动：`internal/llm/anthropic.go`、`internal/llm/openai.go` 无修改（验证：核对 diff）。(AC12/N3)
- [ ] 黑名单 / 沙箱对 MCP 工具自动跳过：MCP 工具调用`extractTarget` 返回 `("", false, false)` → 黑名单层因 `target==""` 不命中、沙箱层因 `isFile==false` 不进入（验证：用 permission 的 `Check` 对一次 mcp 全名调用断言不被黑名单/沙箱直接 Deny）。(AC11/F12)
- [ ] ch01–ch06 不退化：`go test ./...` 全过，既有用例不需要适配（验证：运行测试套件）。(AC13/N5)

## 编译与测试
- [ ] `go build ./...` 无错误。
- [ ] `go vet ./...` 无告警。
- [ ] `go test ./...` 通过（config、conversation、tool、agent、prompt、permission、tui、**mcp** 单测）。
- [ ] `go test -race ./internal/mcp/... ./internal/agent/... ./internal/tui/...` 无竞争、无超时（重点守护 Manager 并发连接、共享状态、Close 兜底）。(N7/N8)
- [ ] `gofmt -l .` 无输出（`internal/mcp` 在 goimports 本地包组）。(AC15/N8)
- [ ] 凭据不落盘：配置示例 / 文档 / 测试 fixture 全用 `${VAR}`；`git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'` 在 ch07 期间无命中。(AC14/N6)

## 端到端场景（tmux 实跑）
- [ ] 场景 1（无 MCP 配置）：仓库内不存在 `.gcode.yaml` 与 `~/.gcode/config.yaml` 时，gcode 正常进 TUI；registry 仅含 6 个内置工具；stderr 无 mcp 相关告警。(AC1)
- [ ] 场景 2（stdio server 接入）：在 `.gcode.yaml` 配置 `@modelcontextprotocol/server-everything` 一类真实 server，启动后日志显示 server 连接成功 + 工具数；TUI 中让模型调用其中一个工具（如 echo），default 模式弹人在回路 → 「允许本次」→ 工具结果回灌 → 模型续答。(AC4/AC6/AC11)
- [ ] 场景 3（失败隔离）：配置一个不存在 command 的 server + 一个能跑的 server，启动 stderr 有第一个 server 的失败告警；能跑的 server 工具仍可用、能正常调用。(AC8)
- [ ] 场景 4（永久放行 + 重启）：场景 2 中选「永久允许」→ `.gcode/settings.local.yaml` 出现对应 `mcp__<server>__<tool>` allow 规则；重启 gcode 后再调该工具不再弹窗直接执行。(AC11)
- [ ] 场景 5（凭据展开）：配置 `env: { GITHUB_TOKEN: "${GITHUB_TOKEN}" }`；`unset GITHUB_TOKEN` 启动时 stderr 有 undefined 告警但 server 仍尝试启动（server 自决报错与否）；`export GITHUB_TOKEN=...` 后正常工作。(AC3/AC14)
- [ ] 场景 6（退出干净）：`q` 退出 gcode 后 `ps -ef | grep server-everything`（或对应 server 进程名）确认子进程无残留。(AC10)
- [ ] 场景 7（bypass + 黑名单兜底）：Shift+Tab 切到 bypassPermissions，MCP 工具调用不弹窗；让模型跑内置 `bash` 工具 `rm -rf /` 仍被黑名单拦下、回灌被拒。(AC11/N4)
- [ ] 场景 8（HTTP server，可选）：本地起一个最小 HTTP MCP server 或用 `httptest`，配置 http 类型 + `headers: { Authorization: "Bearer ${TOKEN}" }`；启动后工具被注册；调用时 server 端日志可见 Authorization 头。(AC5)
```

### Python

```markdown
# MCP 客户端 Spec## 背景ch01–ch06 已经把 gcode 砌成了一个能自主多轮干活、且有五层安全护栏的 coding agent。但**工具集是写死的 6 个内置工具**（读 / 写 / 改文件、命令执行、按模式找文件、搜内容）——想让它会用 GitHub、查数据库、调内部服务，只能改源码、重新打包，能力边界锁死在编译期。

MCP（Model Context Protocol）是一套开放标准，用统一的 JSON-RPC 协议把"提供工具的一方（server）"与"使用工具的一方（client）"解耦，社区已有大量现成 server（GitHub、Slack、SQLite、文件系统……）。ch07 给 gcode 装上 **MCP 客户端**：启动时按配置自动发现并连接外部 server，把它们的工具包装成 gcode 已有的工具抽象、注册进工具中心，Agent 调用时与内置工具**完全无感**，并自动复用 ch06 的权限护栏。这是从"工具集固定"到"工具生态可插拔"的一跃——给 gcode 装上扩展坞。

## 目标- **配置驱动的自动发现**：启动时从配置声明的 server 列表自动连接、列出工具、注册进工具中心，无需改代码。
- **两种传输**：本地 server 走子进程标准输入输出管道（stdio）；远程 server 走 Streamable HTTP。
- **标准三步会话**：每个 server 一次连接经过 初始化握手 → 列出工具 → 按需调用工具（协议细节由官方 Python SDK `mcp`（`pip install mcp`）承载，不自研协议栈）。
- **无感适配**：发现到的远端工具包装成与内置工具一致的抽象，Agent 编排层与 provider 适配层均无需感知其来自远端。
- **命名空间隔离**：远端工具统一加 `mcp__<server>__<tool>` 前缀，杜绝与内置工具及多 server 间的重名冲突，并保留来源可追溯。
- **多 server 生命周期管理**：每个连接各自独立缓存与管理；单个 server 连接 / 初始化 / 列工具失败只跳过它自身，不影响其它 server、不影响启动；程序退出时统一、干净地关闭全部连接（含终止 stdio 子进程）。
- **两层配置合并**：server 列表从 **用户级** 与 **项目级** 两个配置文件读取合并，项目级覆盖用户级同名 server。
- **凭据不落盘**：配置中环境变量与请求头的值支持从宿主环境变量展开（`${VAR}`），密钥不写进配置文件。
- **复用权限**：MCP 工具天然走 ch06 的「规则 → 模式兜底 → 人在回路」链路，默认按命令执行类每次确认，自报只读（`readOnlyHint`）的按只读类放行并可并发；权限包**零改动**。
- **不破坏既有能力**：ch01–ch06 的会话、Loop、流式、缓存、规划、权限五层等行为不退化。

## 功能需求- **F1: 两层 YAML 配置加载与合并**
  从**用户级** `~/.gcode/config.yaml` 与**项目级** `<root>/.gcode.yaml` 两个文件读取 `mcp_servers` 段（map：key 为 server 名，value 为 server 定义）；按 server 名合并，**项目级同名 server 完整覆盖用户级**（不做字段级合并，避免半合并出畸形 server）。文件缺失视为空 `mcp_servers`；文件格式非法时**跳过该文件并 stderr 告警**，绝不致启动失败、不抛未捕获异常。`mcp_servers` 顶层不存在或为空，视为零个 MCP server，正常进 TUI。

- **F2: server 类型与必填字段**
  每个 server 定义自带 `type` 字段（**显式**：`stdio` 或 `http`），不靠字段嗅探判定类型。
  - `stdio` 类型必填 `command`（字符串）；可选 `args`（字符串数组）、`env`（字符串 map）。
  - `http` 类型必填 `url`（字符串）；可选 `headers`（字符串 map）。
  字段缺失或 `type` 非法时**跳过该 server 并 stderr 告警**，不影响其它 server 加载。

- **F3: 环境变量展开**
  `env` 与 `headers` 的**值**支持 `${VAR}` 形式从宿主环境变量取值；展开发生在配置加载阶段、不污染原始配置文件。**未定义的 `${VAR}` 展开为空串并 stderr 告警**，但不阻断该 server 启动（让 server 自行决定无凭据时是否报错）。`command` / `args` 与 server 名、工具名**不做展开**（避免命令/名字被环境间接影响产生隐性歧义）。

- **F4: stdio 传输**
  对 `stdio` 类型 server，以 `command` + `args` 启动子进程；通过子进程的标准输入输出按 JSON-RPC 帧通信（由 SDK 的 `stdio_client` + `StdioServerParameters` 完成）。`env` 与宿主进程环境合并后注入子进程（同名宿主变量被 `env` 覆盖，便于按 server 配置注入凭据）。子进程 `stderr` 透传给宿主 stderr 便于排查。子进程在 gcode 退出时一并干净终止（关闭其 stdin → 等待 → 必要时发信号；由 SDK 的 `async with` 上下文管理器承载）。

- **F5: Streamable HTTP 传输**
  对 `http` 类型 server，以 `url` 为 endpoint 走 Streamable HTTP（由 SDK 的 `streamablehttp_client` 完成）；配置中的 `headers` 注入每次 HTTP 请求（用于 `Authorization` 等鉴权头）。**不订阅服务器推送的独立 SSE 通道**（本章只用请求-响应式工具调用，无需 server 主动推送），减少长连接维护成本。

- **F6: 标准三步会话**
  每个 server 建立后依次完成 **`session.initialize()` 握手**（交换 protocolVersion 与 capabilities）→ **`session.list_tools()` 列出工具** → 进入按需 **`session.call_tool()` 调用**阶段。整个协议层（JSON-RPC 编解码、请求/响应 id 配对、握手细节、传输细节）**由官方 Python SDK 承载**，不自研协议栈。本章只覆盖工具能力，**不订阅 / 不实现** MCP 的资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）等其它能力。

- **F7: 工具适配（远端工具 ↔ 内置 Tool 抽象）**
  把 server 返回的每个远端工具包装成一个实现 gcode `Tool` 协议的对象，注册进工具中心：
  - **名字**：`mcp__<server>__<tool>`（见 F8）。
  - **描述**：直接取远端 `description`（空则给一个含 server 名的兜底说明）。
  - **参数 schema**：把远端 `inputSchema` 转成 gcode 的 `dict[str, Any]` 形式（透传 JSON Schema），不二次裁剪。
  - **只读性**：远端 `annotations.readOnlyHint==True` → `read_only==True`；其余（含字段缺失/非法）→ `False`（安全默认按有副作用处理）。
  - **执行**：调用时通过该 server 的会话发 `call_tool`；远端返回的 `content` 中文本块（`TextContent`）的文本按顺序拼成 gcode `ToolResult.content`，远端 `isError==True` 映射为 `ToolResult.is_error==True`；非 text 块（image / audio / resource_link / embedded_resource 等）静默丢弃并 stderr 告警一次；调用过程中协议错误（连接断、超时、传输错）也转成 `is_error==True` 的结构化错误**回灌给模型**（不向 Agent Loop 抛 Python 异常，复用 ch04/ch05 不中断会话的契约）。Agent 与 provider 适配层不感知"该工具来自远端"。

- **F8: 工具命名空间**
  所有 MCP 工具统一以 `mcp__<server>__<tool>` 命名（`server` 与 `tool` 名按配置/远端原样保留）。命名空间用途双重：
  - **避免冲突**：同名远端工具在不同 server 互不干扰；与 6 个内置工具天然不重名。
  - **可追溯**：单看工具名能识别来源 server，便于日志、人在回路弹窗、权限规则书写。
  注册时若仍发生同名（同 server 自报多个同名工具的边界情形）则后注册者保留并 stderr 告警；若工具名经前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`），**跳过该工具并 stderr 告警**。

- **F9: 启动同步连接 + 单 server 30s 超时 + 失败隔离**
  在进入 TUI 之前**同步**对所有配置中的 server 发起连接 + 握手 + 列工具（实现并发用 `asyncio.gather` 缩短总时延）；**每个 server 的整个启动序列受 30s 超时约束**（内置不可配，用 `asyncio.wait_for`）。任一 server 的连接 / 握手 / 列工具失败或超时**只跳过它自身**：gcode 启动不被阻断、其它 server 与内置工具集照常注册可用、stderr 给出该 server 的失败原因。所有 server 连接尝试结束后才进入 TUI；进入 TUI 时工具中心呈现的就是"内置 6 工具 + 成功连上的 server 工具"全集，Agent 在任意一轮看到的工具集稳定不变。

- **F10: 工具调用超时**
  每次 `call_tool` 复用 30s 超时（与连接超时同值，**内置不可配**，用 `asyncio.wait_for`）；超时按 F7 转成 `is_error==True` 的结构化错误回灌给模型，Agent Loop 继续。

- **F11: 退出时统一关闭**
  gcode 正常退出（用户主动退出、致命错收尾）时，对所有已建立的会话统一调用关闭逻辑：stdio server 的子进程被干净终止（先关 stdin、给 server 自然退出窗口、必要时发信号），HTTP server 的会话用 DELETE 通知 server 释放（由 SDK 处理）。退出**不**强行等待所有连接关闭完成超过若干秒（整体兜底 5s，避免某 server 卡住拖死整个程序退出）。

- **F12: ch06 权限链路无感复用**
  MCP 工具走 ch06 现有判定链路：
  - 黑名单仅作用于内置 `bash` 命令串，对 MCP 工具不命中（`extract_target` 对未知工具返回 target=""，自动跳过）。
  - 沙箱仅作用于内置文件类工具，对 MCP 工具不适用（`extract_target` 对未知工具返回 `is_file=False`，自动跳过）。
  - 规则引擎按 `mcp__<server>__<tool>` 作为友好名匹配（`friendly_name` 对未知名原样返回）；用户可用精确名 `mcp__github__create_issue` 或带 `*` 的 `mcp__github__*` 写 allow/deny 规则。
  - 模式兜底：`read_only==True` 的 MCP 工具归 `CategoryRead`，default 下直接放行、可并发；其余归 `CategoryExec`，default 与 acceptEdits 下每次触发人在回路 Ask；bypass 下放行。
  **permission 包源码零修改**，只通过既有公共行为承载。

## 非功能需求

- N1: 失败隔离不阻塞——单 server 任意阶段（连接 / 握手 / 列工具 / 调用）失败或卡住，只跳过它自身、不阻塞 gcode 启动、不影响其它 server 与内置工具；连接卡住时 30s 超时强制收尾，绝不死锁。
- N2: 安全默认——`readOnlyHint` 缺失或非法 → 非只读（默认走 Ask）；`${VAR}` 未定义 → 空串（不替 server 拍板）；type 非法 / 字段缺失 → 跳过该 server（不静默放行未定义 server）。
- N3: 跨协议一致——MCP 工具行为与 provider（Anthropic / OpenAI）无关；provider 适配层零修改。
- N4: ch06 权限零改动——permission 包源码零修改；MCP 工具走既有判定链路。
- N5: 不破坏 ch01–ch06——会话、Loop、流式、缓存、规划、人在回路、并发、用户取消、保序回灌等既有能力不退化。
- N6: 凭据不落盘——api_key / token 不出现在配置文件；env / headers 通过 `${VAR}` 引用宿主环境；敏感值在日志/状态栏/任何输出中不回显。
- N7: 退出干净——程序退出时不泄漏子进程、不泄漏 asyncio task、不死锁；某 server 关闭卡住不阻塞整体退出（整体退出关闭兜底超时 5s）。
- N8: 代码规范——`ruff check` / `ruff format --check` / `mypy`（可选 strict 子集）/ `pytest` 全过（本项目为 Python，遵循 CLAUDE.md 等价规范）。

## 不做的事- **MCP 资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）**——本章只覆盖工具能力。
- **tools/list 变更通知 / 调用进度通知**——不订阅独立 SSE 通道（SDK 默认开，本章显式关闭或不消费），工具集快照固定在启动时。
- **健康检查 / 自动重连 / 退避**——单连接挂掉就挂掉，留待后续章节。
- **配置热加载 / 运行时增减 server**——重启 gcode 才能应用新配置。
- **本地级 mcp_servers 配置层**——仅两层（用户级 + 项目级）。
- **mcp_servers 字段级合并**——按 server 名维度合并，同名项目级完整覆盖用户级。
- **`command` / `args` / 工具名 / server 名 的变量展开**——仅 env / headers 的值展开 `${VAR}`。
- **OAuth 完整鉴权流程**——仅支持 `headers` 直传静态 token；需要 OAuth 的 server 让用户自行预换 token 写入 headers。
- **自定义连接 / 调用超时**——30s 硬编码，不暴露配置项。
- **MCP 工具的黑名单与路径沙箱扩展**——这两层只对内置工具有意义，MCP 工具仅走规则 + 模式兜底 + 人在回路。
- **非文本内容块的回灌**——仅收集 `TextContent` 的内容块拼成 ToolResult；image / audio / resource_link / embedded_resource 等静默丢弃并 stderr 告警一次。
- **资源配额 / 速率限制 / 审计日志**——与 ch06 不做事项一致。
- **MCP server 端的实现**——gcode 仅作 client。

## 验收标准

- AC1: 配置加载与两层合并——`~/.gcode/config.yaml` 与 `<root>/.gcode.yaml` 都存在时，按 server 名合并；同名 server 项目级完整覆盖用户级；任一文件缺失或非法时跳过该文件、不致启动失败、其它正常加载。（F1/N1）
- AC2: 字段校验——stdio 类型缺 command、http 类型缺 url、type 非法或缺失时，该 server 被跳过并 stderr 告警，其它 server 不受影响。（F2/N2）
- AC3: 变量展开——env / headers 的值 `${VAR}` 从宿主环境取值；未定义变量展开为空串并告警；command / args / 工具名 / server 名不展开。（F3/N2/N6）
- AC4: stdio 启动 + 子进程终止——能拉起一个 stdio MCP server 子进程，握手 + 列工具成功；env 注入生效；gcode 退出时子进程被终止、无僵尸。（F4/F6/F11/N7）
- AC5: HTTP 连接 + 自定义 headers——能对一个 HTTP MCP server 完成握手 + 列工具；`headers` 注入到 HTTP 请求中。（F5/F6/N6）
- AC6: 工具适配与命名——同一 server 的工具列出后注册进 registry，名字符合 `mcp__<server>__<tool>`，描述非空，参数 schema 透传；调用时远端 text content 拼接为 `ToolResult.content`，远端 isError 映射到 `ToolResult.is_error`；非 text 块静默丢弃。（F6/F7/F8）
- AC7: 命名空间隔离——同名工具来自不同 server 不互相覆盖；与 6 个内置工具天然不重名；前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）的工具被跳过并告警。（F8）
- AC8: 启动失败隔离 + 30s 超时——单 server 连接 / 握手 / 列工具失败或超时，只跳过它自身，其它 server 与内置工具集照常注册；失败原因 stderr 可见；启动总时延上界受 30s 约束（并发实现）。（F9/N1）
- AC9: 调用超时与错误回灌——`call_tool` 30s 超时或协议错误转为 `is_error==True` 的结构化错误结果回灌给模型，Agent Loop 不中断，可在后续轮调整。（F7/F10/N5）
- AC10: 退出干净——程序退出时所有 stdio 子进程被终止、HTTP 会话被关闭；关闭过程不泄漏 task、不卡死（总超时 5s 兜底）。（F11/N7）
- AC11: 权限链路自然命中——`mcp__<server>__*` 形式的 allow / deny 规则正确作用到对应 MCP 工具；未写规则时 `readOnlyHint==True` 的 MCP 工具按只读类放行并可并发，其余按命令执行类触发人在回路 Ask；bypass 模式下放行（黑名单 / 沙箱对 MCP 工具不命中，自动跳过）。（F12/N4）
- AC12: 跨协议一致——同一 MCP server 在 Anthropic 与 OpenAI 两种 provider 下行为一致；provider 适配层零 diff。（N3）
- AC13: 不破坏 ch01–ch06——既有所有测试通过；多轮连环、用户取消、流出错恢复、历史一致、缓存命中、规划按轮次注入、ch06 五层权限等行为不退化。（N5）
- AC14: 凭据不落盘——配置示例与说明均用 `${VAR}` 引用密钥；`git grep` 在配置文件中无 token 明文命中。（N6）
- AC15: 代码规范——`ruff format --check .` 无 diff；`ruff check .` 无告警；`pytest`（含 `tests/test_mcp_*.py`）通过；`pytest -m "asyncio"` 在 `tests/test_mcp_*.py` 下无悬挂 task / 死锁。（N8）
```

````markdown
# MCP 客户端 Plan> 技术栈：Python 3.12+；使用 **官方 SDK** `mcp`（`pip install mcp` / `uv add mcp`，import 名 `mcp`）承载协议层（JSON-RPC 编解码、`initialize` 握手、stdio 与 Streamable HTTP 传输）。本章新增 **`gcode.mcp` 子包** 与入口装配，**不改 tool / agent / tui / permission / llm / config / conversation / prompt**。

## 架构概览- **`gcode.mcp` 子包（新增）**：承载 MCP 客户端的全部职责——配置加载与两层合并、`${VAR}` 展开、字段校验、调用 SDK 建立 stdio / HTTP 会话、把远端工具适配成内置 `Tool` 协议、统一管理生命周期。仅依赖 `gcode.tool`、SDK 与标准库；不依赖 agent / tui / permission / conversation。
- **`gcode.cli`（改造）**：在 `tool.default_registry()` 之后、`permission.PermissionEngine(...)` 与 `GCodeApp(...).run()` 之前，加载 mcp 配置 → 启动 Manager → 把 Manager 产出的工具注册进 registry → 退出时 `await manager.close()`（包在 `try/finally` 中）。
- **`gcode.tool` 包（零改）**：`Registry.register` 与 `Tool` 协议本就是开放抽象，直接吃 `McpTool` 实例；`is_read_only` 对 MCP 工具返回正确值。
- **agent / tui 包（零改）**：工具流转链路对工具来源透明。
- **permission 包（零改）**：`friendly_name` 对未知名原样返回 → 规则可写 `mcp__<server>__<tool>`；`categorize` 在 `read_only==True` 时走 CategoryRead、否则归 CategoryExec → 模式兜底矩阵自然命中；`extract_target` 对未知工具返回 `("", False, False)`，黑名单与沙箱自动跳过。
- **llm / provider（零改）**：工具定义透传，协议无关。

数据流（单次调用）：
```
agent.execute_batched(calls, mode)
  └→ engine.check(...)  → Allow → registry.execute(name, args)
       └→ McpTool.execute(args)                        [本章新增工具实现]
            ├→ await asyncio.wait_for(..., timeout=30)
            ├→ session.call_tool(remote_name, arguments=map)
            └→ 拼接 text content / 映射 is_error / 协议错转 is_error
       └→ ToolResult(content, is_error)                ── 回灌 conv
```

## 核心数据结构### `gcode.mcp.Config` / `gcode.mcp.ServerConfig`（对外）
```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ServerConfig:
    """单个 MCP server 的完整定义（已展开 ${VAR}、已校验）。"""
    type: Literal["stdio", "http"]
    command: str = ""                       # stdio 必填
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""                           # http 必填
    headers: dict[str, str] = field(default_factory=dict)

@dataclass
class Config:
    """mcp_servers 在内存中的归一化形式（已合并）。"""
    servers: dict[str, ServerConfig] = field(default_factory=dict)
```

### `gcode.mcp.Manager`（对外不透明）
```python
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession

class Manager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: list[_Session] = []        # 成功建立的会话（供 close）
        self._tools: list[McpTool] = []            # 适配好的工具（供 cli 注册）
        self._stack = AsyncExitStack()             # 持有 stdio / http 上下文，close 时统一退栈

@dataclass
class _Session:
    name: str
    session: ClientSession
```

### 工具适配（包内私有）
```python
# McpTool 实现 gcode.tool.Tool 协议。
@dataclass
class McpTool:
    full_name: str                    # "mcp__<server>__<tool>"
    remote_name: str                  # server 上的原始工具名
    description: str
    parameters: dict[str, Any]        # JSON Schema 透传
    read_only: bool                   # 仅来自远端 annotations.readOnlyHint==True
    caller: CallerSession             # 协议形式持有，便于单测注入 stub

class CallerSession(Protocol):
    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None
    ) -> CallToolResult: ...
```

## 核心接口

```python
# 加载并合并两层配置；返回归一化的 Config。
# - root: 项目根（用来定位 <root>/.gcode.yaml）
# - 文件不存在 → 视为空层；格式非法 → 跳过该层 + stderr 告警（降级，N1）
# - 内部完成 ${VAR} 展开与字段校验（非法 server 直接剔除，N2）
# - 永不抛出（签名只返 Config）
def load_config(root: str) -> Config: ...

# 启动 Manager：并发连接所有 server，每个 server 30s 超时，失败仅跳过 + 告警。
# 阻塞直到所有 server 的尝试结束（成功 / 失败 / 超时）。
# version 透传到 Implementation.version（便于 server 端识别 gcode 版本）。
async def new_manager(cfg: Config, version: str) -> Manager: ...

# 返回适配好的工具列表（按 server 名 → 工具名 稳定排序）。
def Manager.tools(self) -> list[McpTool]: ...

# 关闭所有会话（stdio 子进程终止、HTTP DELETE）；总超时 5s 兜底，绝不阻塞退出。
async def Manager.close(self) -> None: ...
```

## 模块设计### `src/gcode/mcp/config.py`
**职责：** 加载两层 YAML、合并、展开 `${VAR}`、校验。
**关键点：**
- 内部 `@dataclass class _RawServer`（含全部可能字段：type / command / args / env / url / headers，可选）。
- `_load_file(path: Path) -> dict[str, _RawServer]`：
  - 文件不存在 → 返回空 `{}`；
  - 读 / `yaml.safe_load` 失败 → stderr 告警一行 + 返回空 `{}`（调用方降级）；
  - 取 `mcp_servers` 段，缺失视为空。
- `_expand_vars(s: str) -> tuple[str, list[str]]`：正则 `\$\{([A-Za-z_][A-Za-z0-9_]*)\}`，用 `os.environ.get` 取值；未定义变量名记录到 `undefined`（供告警）。**仅作用于 env / headers 的值**。
- `_apply_expansion(name: str, srv: _RawServer) -> None`：对 `srv.env`、`srv.headers` 每个值跑 `_expand_vars`；未定义变量在 stderr 输出 `[mcp] warn: undefined env var ${X} referenced by server <name>`（同 server 同变量限一次，用局部 `set` 去重）。
- `_merge_servers(user: dict, project: dict) -> dict`：复制 user，遍历 project，同名直接整对象覆盖。
- `_validate_server(name: str, srv: _RawServer) -> ServerConfig | None`：
  - `srv.type` 必为 `"stdio"` 或 `"http"`，否则跳过；
  - `stdio` 必填 `command`；`http` 必填 `url`；缺失则跳过；
  - 违规时 stderr 告警 `[mcp] warn: skip server <name>: <reason>`。
- `load_config(root: str) -> Config`：
  - 用户级 = `Path.home() / ".gcode" / "config.yaml"`；项目级 = `Path(root) / ".gcode.yaml"`。
  - 两层各自 `_load_file` + `_apply_expansion`；任一层解析失败 stderr 一行告警并跳过（该层视为空）。
  - `_merge_servers` 后逐个 `_validate_server`，组装 `Config`。

### `src/gcode/mcp/manager.py`
**职责：** 连接 server、缓存会话、关闭。
**关键点：**
- `connect_timeout`、`close_timeout` 作为模块级变量（非常量），便于单测临时改小，结束 restore。生产值 30s / 5s。
- `async def new_manager(cfg: Config, version: str) -> Manager`：
  - 内部 `mgr = Manager()`；为每个 `(name, srv)` 起一个 task：`asyncio.create_task(_connect_one(mgr, name, srv, version))`。
  - `await asyncio.gather(*tasks, return_exceptions=True)`（异常吸收，单 server 出错不影响其它）；
  - 全部完成后稳定排序 `mgr._tools`（按 `full_name`）。
- `async def _connect_one(mgr, name, srv, version)`：
  - `try: await asyncio.wait_for(_do_connect(mgr, name, srv, version), timeout=connect_timeout)`；
  - `except asyncio.TimeoutError`: stderr 告警 `[mcp] warn: connect server <name> timeout after 30s` 并 return；
  - `except Exception as e`: stderr 告警 `[mcp] warn: connect server <name> failed: <e>` 并 return。
- `async def _do_connect(mgr, name, srv, version)`：
  - 按 `srv.type` 构造 transport 上下文：
    - **stdio**：
      ```python
      from mcp import StdioServerParameters
      from mcp.client.stdio import stdio_client
      params = StdioServerParameters(
          command=srv.command,
          args=srv.args,
          env={**os.environ, **srv.env},   # 同名宿主变量被覆盖
      )
      ctx = stdio_client(params)
      ```
    - **http**：
      ```python
      from mcp.client.streamable_http import streamablehttp_client
      ctx = streamablehttp_client(srv.url, headers=srv.headers or None)
      ```
  - 用一个**包级 `AsyncExitStack`**（挂在 `Manager._stack`）持有 transport 与 `ClientSession` 上下文：
    ```python
    transport = await mgr._stack.enter_async_context(ctx)
    read, write = transport[0], transport[1]    # http 返回 3 元组，第三个是 metadata
    session = await mgr._stack.enter_async_context(
        ClientSession(read, write, client_info=Implementation(name="gcode", version=version))
    )
    await session.initialize()                  # 握手
    listed = await session.list_tools()
    ```
  - 对 `listed.tools` 中每个 `Tool` 调 `adapt_tool(name, t, session)`；成功的入临时 list。
  - 在 `async with mgr._lock:` 内统一 append `_sessions` / `_tools`。
- `async def Manager.close(self)`：
  - 用 `asyncio.wait_for(self._stack.aclose(), timeout=close_timeout)` 包裹；
  - `TimeoutError` → stderr 告警 `[mcp] warn: close timeout (5s), some sessions may leak`，不再等。
- `Manager.tools()`：返回 `list(self._tools)` 副本（防外部修改）。

### `src/gcode/mcp/tool.py`
**职责：** 把 SDK 返回的 `mcp.types.Tool` 适配为 gcode `Tool` 协议。
**关键点：**
- 包级 `_VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")`。
- 包级 `_non_text_warn_once: set[str] = set()`，配 `asyncio.Lock`（或在单线程 asyncio 中直接用 set）记录已告警的 `full_name`。
- `def adapt_tool(server_name: str, t: mcp.types.Tool, session: CallerSession) -> McpTool | None`：
  - `full_name = f"mcp__{server_name}__{t.name}"`。
  - **禁用字符校验**：`_VALID_NAME.fullmatch(full_name)` 不通过 → 返回 `None` + stderr 告警 `[mcp] warn: skip tool <full_name>: name contains illegal characters`。
  - `description`：`t.description` 为空时兜底 `f"来自 MCP server {server_name} 的工具 {t.name}"`。
  - `parameters`：`t.inputSchema` 转 `dict[str, Any]`（已是 dict 则 `dict(...)` 浅拷贝；为空时给 `{"type": "object"}` 兜底，避免 provider 拒收）。
  - `read_only`：`bool(t.annotations and t.annotations.readOnlyHint)`（None-safe）。
- `McpTool.name / description / parameters / read_only`：通过 dataclass 字段直接暴露（gcode `Tool` 协议要求的属性/方法返回字段值）。
- `async def McpTool.execute(self, args: dict[str, Any] | None) -> ToolResult`：
  - `arg_map = args if args else None`（空 dict / None 视作无参数）；
  - ```python
    try:
        result = await asyncio.wait_for(
            self.caller.call_tool(self.remote_name, arg_map),
            timeout=30,
        )
    except asyncio.TimeoutError:
        return ToolResult(content="MCP 工具调用超时 (30s)", is_error=True)
    except Exception as e:
        return ToolResult(content=f"MCP 工具调用失败: {e}", is_error=True)
    ```
  - 遍历 `result.content`：`isinstance(block, mcp.types.TextContent)` → 收集 `block.text`；其余块计数，首次出现时 stderr 告警 `[mcp] warn: tool <full_name> returned non-text content blocks (dropped)`（per `full_name` 限一次）。
  - 用 `"\n".join(texts)` 拼出 `content`；返回 `ToolResult(content=content, is_error=bool(result.isError))`。

### `src/gcode/cli.py`（改造）
位置：在 `registry = tool.default_registry()` 之后、`PermissionEngine(...)` 之前插入：
```python
import asyncio
from gcode import mcp as mcp_client

async def _amain() -> int:
    ...
    registry = tool.default_registry()
    mcp_cfg = mcp_client.load_config(root)
    mcp_mgr = await mcp_client.new_manager(mcp_cfg, version=__version__)
    try:
        for t in mcp_mgr.tools():
            registry.register(t)
        engine = PermissionEngine(root)
        app = GCodeApp(cfg.providers, registry=registry, engine=engine)
        await app.run_async()
    finally:
        await mcp_mgr.close()
    return 0

def main() -> None:
    raise SystemExit(asyncio.run(_amain()))
```
（`root` 复用现有 `os.getcwd()` 结果；version 复用 `__version__`。）

## 文件组织

```
gcode/
├── pyproject.toml                       — 改：dependencies 增加 "mcp>=1.0"
├── src/gcode/
│   ├── mcp/
│   │   ├── __init__.py                  — 新：暴露 Config / ServerConfig / Manager / load_config / new_manager
│   │   ├── config.py                    — 新：Config / ServerConfig、load_config、_load_file、_expand_vars、_merge_servers、_validate_server
│   │   ├── manager.py                   — 新：Manager、new_manager（并发 + 30s 超时）、close（5s 兜底）、tools；模块级 connect_timeout / close_timeout
│   │   └── tool.py                      — 新：CallerSession Protocol、McpTool、adapt_tool、execute
│   └── cli.py                           — 改：装配 Manager，注册 MCP 工具，finally 关闭
├── tests/
│   ├── test_mcp_config.py               — 新：两层合并 / 变量展开 / 字段校验 / 降级 单测
│   ├── test_mcp_tool.py                 — 新：命名拼接 / 禁用字符 / Execute 各分支（成功/远端 IsError/超时/协议错/非 text 块）
│   └── test_mcp_manager.py              — 新：连接成功/失败/超时、close 不死锁、共享状态并发安全
├── docs/ch07/
│   ├── spec.md / plan.md / task.md / checklist.md
│   └── mcp-servers.example.yaml         — 新：配置示例（用 ${VAR}）
└── （其它包零改）
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 协议层实现 | 官方 Python SDK（`mcp`，PyPI 包名 `mcp`） | 用户拍板；避免自研 JSON-RPC / 握手 / 帧；SDK 已处理 stdio (`stdio_client`) 与 Streamable HTTP (`streamablehttp_client`) |
| 配置文件位置 | 项目级 `<root>/.gcode.yaml` + 用户级 `~/.gcode/config.yaml` | 用户拍板；项目级 dotfile 一眼可见、与现有 `.gcode/config.yaml`（providers 凭据）分离 |
| 配置层数 | 仅两层，无本地级 | 用户拍板；`${VAR}` 已让密钥不入配置，本地层冗余 |
| 合并语义 | server 名维度，项目级完整覆盖 | 避免字段级半合并出畸形 server |
| server 类型字段 | 显式 `type: stdio\|http` | 不靠字段嗅探（防止误判）；未来扩展易加（如 sse） |
| 变量展开范围 | 仅 env / headers 的值 | 避免 command / args / server 名 / 工具名被环境间接影响；凭据走 env / headers 已足够 |
| 未定义变量 | 空串 + 一次性告警（不阻断） | server 自决无凭据时是否能跑；gcode 不替它拍板 |
| 工具命名 | `mcp__<server>__<tool>` | 用户拍板；Claude Code 风格；LLM 工具名安全字符；一眼识别来源 |
| 启动连接策略 | 同步进 TUI 前完成 + `asyncio.gather` 并发每 server `asyncio.wait_for(30s)` 超时 + 失败跳过 | 进 TUI 时工具集稳定；asyncio 并发缩短总时延；隔离避免单 server 拖死启动 |
| 调用超时 | 30s 硬编码 `asyncio.wait_for`，转 is_error | 与连接同值；不中断 Loop；避免长卡 |
| readOnly 适配 | 严格只信 `annotations.readOnlyHint==True` | 默认走 Ask，最严；声明只读才放行 |
| 资源 / 提示词 / 采样 / roots | 不实现 | 本章只覆盖工具能力 |
| 独立 SSE 通道 | 不订阅（不消费 `streamablehttp_client` 返回的服务端推送流） | 只用请求-响应；省一条长连接；减少复杂度 |
| 非 text 内容块 | 静默丢弃 + 一次性告警 | 模型只能消费文本；丢弃比假装回灌更诚实 |
| 错误回灌 | 协议错 / 超时均转 is_error | 与 ch04 / ch05 不中断 Loop 契约一致 |
| 退出关闭 | 单一 `AsyncExitStack.aclose()` + 5s `wait_for` 兜底 | 让 SDK 的 async context 管理器统一收尾；避免某 server 卡死阻塞退出 |
| permission 接入方式 | 零改动；靠 `friendly_name` 原样 + `categorize` 按 read_only 优先 | 复用现成链路；权限规则可写 `mcp__server__tool` 与 `mcp__server__*` |
| HTTP 自定义 headers | SDK 的 `streamablehttp_client(url, headers=...)` 原生支持 | 不引入额外抽象 |
| OAuth | 不实现完整流程 | 用户预换 token 写 headers；本章范围最小化 |
| execute 接口注入 | `McpTool` 持 `CallerSession` Protocol 而非具体 `ClientSession` | 单测可注入 stub；生产代码无运行时开销 |

## 模块交互

```
cli._amain()
  ├─ tool.default_registry()                       # 6 内置工具
  ├─ mcp.load_config(root)                         # 读两层 yaml + ${VAR} 展开 + 校验
  ├─ await mcp.new_manager(cfg, version)           # asyncio.gather 并发连接所有 server，30s/各
  │     └─ 对每个 server：
  │         ├─ 构造 transport（stdio: stdio_client / http: streamablehttp_client）
  │         ├─ 进入 ClientSession 上下文
  │         ├─ await session.initialize()          # 握手
  │         ├─ await session.list_tools()
  │         └─ adapt_tool 包装成 McpTool
  ├─ for t in mgr.tools(): registry.register(t)
  ├─ PermissionEngine(root)
  ├─ await GCodeApp(...).run_async()
  └─ finally: await mgr.close()                    # AsyncExitStack.aclose() + 5s 兜底
```

调用链（Agent 视角，工具来源透明）：
```
agent.execute_batched(calls, mode)
  └ engine.check(mode, call, registry.is_read_only(call.name))
       (MCP 工具：friendly_name 原样；categorize：read_only==True→Read, 否则→Exec；
        extract_target(未知工具)→is_file=False, target="" → 黑名单/沙箱自动跳过)
  └ Allow → registry.execute(name, args)
       └ McpTool.execute(args)
            ├ asyncio.wait_for(..., timeout=30)
            └ session.call_tool → 拼接 text / 映射 is_error / 协议错转 is_error
  └ ToolResult 回灌 conv
```

依赖方向（无环）：`gcode.cli → gcode.mcp → {gcode.tool, mcp(SDK), 标准库}`；`gcode.mcp` 不依赖 agent / tui / permission / conversation。
````

````markdown
# MCP 客户端 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改   | `pyproject.toml` | `dependencies` 增加 `"mcp>=1.0"`；`uv sync` / `pip install -e .` 同步 |
| 新建 | `src/gcode/mcp/__init__.py` | 暴露 `Config` / `ServerConfig` / `Manager` / `load_config` / `new_manager` |
| 新建 | `src/gcode/mcp/config.py` | `Config` / `ServerConfig`、`load_config`、`_load_file`、`_expand_vars`、`_apply_expansion`、`_merge_servers`、`_validate_server` |
| 新建 | `tests/test_mcp_config.py` | 两层合并 / `${VAR}` 展开 / 字段校验 / 降级 单测 |
| 新建 | `src/gcode/mcp/tool.py` | `CallerSession` Protocol、`McpTool`、`adapt_tool`、`execute`、非 text 块告警 once set |
| 新建 | `tests/test_mcp_tool.py` | 命名拼接 / 禁用字符 / Execute 成功 / 远端 IsError / 超时 / 协议错 / 非 text 块跳过 单测 |
| 新建 | `src/gcode/mcp/manager.py` | `Manager`、`_Session`、`new_manager`（`asyncio.gather` 并发 + 30s 超时）、`close`（5s 兜底）、`tools`；模块级 `connect_timeout` / `close_timeout` |
| 新建 | `tests/test_mcp_manager.py` | 连接成功 / 失败 / 超时、`close` 不死锁、并发写共享状态安全 单测 |
| 改   | `src/gcode/cli.py` | 装配 `load_config`、`new_manager`、注册 MCP 工具、`finally: await mgr.close()` |
| 新建 | `docs/ch07/mcp-servers.example.yaml` | 配置示例（含 stdio / http 各一个，用 `${VAR}`） |

---

## T1: 添加 MCP Python SDK 依赖**文件：** `pyproject.toml`、`uv.lock`（自动生成）
**依赖：** 无
**步骤：**
1. 在 `[project]` 的 `dependencies` 列表追加 `"mcp>=1.0"`。
2. 在仓库根执行 `uv sync`（或 `pip install -e .`）；查看 `uv.lock` 或 `pip list` 确认 `mcp` 与其传递依赖（`pydantic` 等）已装好。
3. 写一段最小试导入（可直接放进后续 `tool.py` 的 import 中）：
   ```python
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client
   from mcp.client.streamable_http import streamablehttp_client
   import mcp.types as mtypes
   ```
   并在 Python REPL 跑一次 `import gcode.mcp` 雏形，验证可用。

**验证：** `python -c "import mcp; print(mcp.__version__ if hasattr(mcp,'__version__') else 'ok')"` 输出非错误；`uv pip list | grep mcp` 看到包名。

## T2: 配置类型与加载（含两层合并 + 变量展开 + 字段校验）**文件：** `src/gcode/mcp/config.py`、`src/gcode/mcp/__init__.py`、`tests/test_mcp_config.py`
**依赖：** T1
**步骤：**
1. 定义对外类型 `ServerConfig`、`Config`（见 plan.md「核心数据结构」），用 `@dataclass`。
2. 定义内部 `@dataclass class _RawServer`（含全部字段：`type` / `command` / `args` / `env` / `url` / `headers`，全部 Optional 或带默认值）。
3. `_load_file(path: Path) -> dict[str, _RawServer]`：
   - `path.exists() is False` → 返回 `{}`；
   - `yaml.safe_load(path.read_text())` 失败（含 IOError / `yaml.YAMLError`）→ stderr 告警 `[mcp] warn: load <path> failed: <err>` + 返回 `{}`（调用方降级）；
   - 取 `data.get("mcp_servers") or {}`，逐项映射到 `_RawServer`（缺字段用默认）。
4. `_expand_vars(s: str) -> tuple[str, list[str]]`：
   - 正则 `re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")` 匹配；
   - 用 `os.environ.get(var, "")` 取值；找不到（即 `var not in os.environ`）则记录到 `undefined`。
5. `_apply_expansion(name: str, srv: _RawServer) -> None`：
   - 对 `srv.env`、`srv.headers` 的每个值跑 `_expand_vars`，原地替换；
   - 收集所有 undefined 变量名，去重；首次出现时 `print(f"[mcp] warn: undefined env var ${{{v}}} referenced by server {name}", file=sys.stderr)`。
6. `_merge_servers(user: dict[str, _RawServer], project: dict[str, _RawServer]) -> dict[str, _RawServer]`：
   - 新建 dict，先 `update(user)`，再 `update(project)`（同名直接整对象覆盖）。
7. `_validate_server(name: str, srv: _RawServer) -> ServerConfig | None`：
   - `srv.type` 必为 `"stdio"` 或 `"http"`，否则跳过；
   - `stdio` 必填 `command`；`http` 必填 `url`；缺失则跳过；
   - 违规时 `print(f"[mcp] warn: skip server {name}: {reason}", file=sys.stderr)`；返回 `None`。
8. `load_config(root: str) -> Config`：
   - 用户级 = `Path.home() / ".gcode" / "config.yaml"`（`Path.home()` 失败时跳过用户层不致错，用 `try/except` 兜底）；项目级 = `Path(root) / ".gcode.yaml"`。
   - 两层各自 `_load_file`；返回空 dict 即视为该层为空。
   - 对每层各 server 跑 `_apply_expansion`。
   - `_merge_servers` 后逐个 `_validate_server`，收齐合法 server 组装 `Config`。
   - 永不抛出。
9. `src/gcode/mcp/__init__.py` 中 `from .config import Config, ServerConfig, load_config`。

**验证：** `python -c "from gcode.mcp import load_config, Config"` 不报错；`pytest tests/test_mcp_config.py` 覆盖：
- 两文件缺失 → `Config.servers` 为空字典、无异常；
- 仅用户级 / 仅项目级 / 都有（同名 server 项目级胜出，断言字段为项目级值）；
- 文件格式非法 → 跳过该层、其它正常加载、`capsys.readouterr().err` 中包含告警；
- `${VAR}` 已定义（用 `monkeypatch.setenv`）→ 展开为环境值；未定义 → 空串 + 告警；`command` / `args` 中含 `${VAR}` → 不展开（保留字面量）；
- type 缺失 / type 非法 / stdio 缺 command / http 缺 url → 该 server 被跳过，其它 server 不受影响。

## T3: 工具适配（McpTool）**文件：** `src/gcode/mcp/tool.py`、`tests/test_mcp_tool.py`
**依赖：** T1
**步骤：**
1. `import mcp.types as mtypes`；`from gcode.tool import Tool, ToolResult`（或对应内置工具协议路径，按现有命名为准）。
2. 定义最小 Protocol `CallerSession` 与 `@dataclass class McpTool`（见 plan.md「核心数据结构」）。
3. 实现 gcode `Tool` 协议要求的属性 / 方法：`name`（返回 `full_name`）、`description`、`parameters`、`read_only`、`async def execute(args)`。
4. `def adapt_tool(server_name: str, t: mtypes.Tool, session: CallerSession) -> McpTool | None`：
   - `full_name = f"mcp__{server_name}__{t.name}"`；
   - 用包级 `_VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")` 校验 `full_name`，不通过 → 返回 `None` + stderr 告警 `[mcp] warn: skip tool <full_name>: name contains illegal characters`。
   - `description = t.description or f"来自 MCP server {server_name} 的工具 {t.name}"`。
   - `parameters`：`t.inputSchema` 已是 `dict[str, Any]`，做浅拷贝 `dict(t.inputSchema)`；若空 / None → `{"type": "object"}` 兜底。
   - `read_only = bool(getattr(t, "annotations", None) and t.annotations.readOnlyHint)`。
5. `async def McpTool.execute(self, args: dict[str, Any] | None) -> ToolResult`：
   - `arg_map = args or None`（空 dict 视作无参数）；不再 try/except 解析 JSON——上层已经传 dict。
   - ```python
     try:
         result = await asyncio.wait_for(
             self.caller.call_tool(self.remote_name, arg_map),
             timeout=30,
         )
     except asyncio.TimeoutError:
         return ToolResult(content="MCP 工具调用超时 (30s)", is_error=True)
     except Exception as e:
         return ToolResult(content=f"MCP 工具调用失败: {e}", is_error=True)
     ```
   - 遍历 `result.content`：
     - `isinstance(block, mtypes.TextContent)` → `texts.append(block.text)`；
     - 非 text 块：通过包级 `_non_text_warn_once: set[str]` 对 `full_name` 做 `if full_name not in _non_text_warn_once: _non_text_warn_once.add(full_name); print("[mcp] warn: tool ... returned non-text content blocks (dropped)", file=sys.stderr)`。
   - 返回 `ToolResult(content="\n".join(texts), is_error=bool(result.isError))`。

**验证：** `pytest tests/test_mcp_tool.py` 覆盖：
- 合法 server 名 + 工具名 → `adapt_tool` 返回 `McpTool` 实例；含 `.` / `@` 等非法字符 → 返回 `None` + `capsys` 告警；
- description 空 → 兜底文案出现；schema None → `{"type": "object"}`；schema 透传成功；
- `t.annotations is None` → `read_only is False`（不报错）；`readOnlyHint=True` → `read_only is True`；
- Execute：注入 stub `CallerSession`（用 `class StubSession:` + `async def call_tool(...)` 返回构造好的 `CallToolResult`），覆盖：
  - 成功（多 text 块拼接，断言 `"\n".join` 顺序）；
  - 远端 `isError=True` 映射；
  - `call_tool` 抛异常 → `is_error=True`，content 含 `MCP 工具调用失败`；
  - 阻塞至超时（stub `await asyncio.Event().wait()` + 模块级 timeout `monkeypatch` 改 200ms）→ `is_error=True`，content 含 `超时`；
  - 非 text 块跳过 + `texts` 仅含 text + `_non_text_warn_once` 同 `full_name` 多次调用只告警一次。

## T4: 连接管理器（Manager）**文件：** `src/gcode/mcp/manager.py`、`src/gcode/mcp/__init__.py`（追加导出）、`tests/test_mcp_manager.py`
**依赖：** T2、T3
**步骤：**
1. 模块级变量（非常量，便于单测改）：
   ```python
   connect_timeout: float = 30.0
   close_timeout: float = 5.0
   ```
2. 定义 `@dataclass class _Session(name: str, session: ClientSession)` 与 `class Manager`（见 plan.md「核心数据结构」，含 `_stack: AsyncExitStack`、`_lock: asyncio.Lock`）。
3. `async def new_manager(cfg: Config, version: str) -> Manager`：
   - `mgr = Manager()`；`mgr._stack = AsyncExitStack(); await mgr._stack.__aenter__()`（或在内部封装，让 `close` 调 `aclose`）。
   - `tasks = [asyncio.create_task(_connect_one(mgr, name, srv, version)) for name, srv in cfg.servers.items()]`；
   - `await asyncio.gather(*tasks, return_exceptions=True)`（异常吸收：`_connect_one` 内部已捕获，不应传出，但 `return_exceptions=True` 多一层保险）；
   - `mgr._tools.sort(key=lambda t: t.full_name)`；
   - 返回 `mgr`。
4. `async def _connect_one(mgr, name, srv, version)`：
   ```python
   try:
       await asyncio.wait_for(_do_connect(mgr, name, srv, version), timeout=connect_timeout)
   except asyncio.TimeoutError:
       print(f"[mcp] warn: connect server {name} timeout after {connect_timeout}s", file=sys.stderr)
   except Exception as e:
       print(f"[mcp] warn: connect server {name} failed: {e}", file=sys.stderr)
   ```
5. `async def _do_connect(mgr, name, srv, version)`：
   - 按 `srv.type` 构造 transport 上下文（`stdio_client` / `streamablehttp_client`）；
   - 通过 `mgr._stack.enter_async_context(...)` 进入 transport 上下文，拿到 `(read, write)` 或 `(read, write, _metadata)`；
   - 再进入 `ClientSession(read, write, client_info=mtypes.Implementation(name="gcode", version=version))` 上下文；
   - `await session.initialize()`；
   - `listed = await session.list_tools()`；
   - 对 `listed.tools` 调 `adapt_tool(name, t, session)`，收齐 list；
   - `async with mgr._lock:` 内 `mgr._sessions.append(_Session(name, session)); mgr._tools.extend(adapted)`。
6. `def Manager.tools(self) -> list[McpTool]`：返回 `list(self._tools)` 副本。
7. `async def Manager.close(self)`：
   ```python
   try:
       await asyncio.wait_for(self._stack.aclose(), timeout=close_timeout)
   except asyncio.TimeoutError:
       print(f"[mcp] warn: close timeout ({close_timeout}s), some sessions may leak", file=sys.stderr)
   ```
8. `src/gcode/mcp/__init__.py` 追加 `from .manager import Manager, new_manager`、`from .tool import McpTool`。

**验证：** `pytest tests/test_mcp_manager.py`（`pytest-asyncio` `@pytest.mark.asyncio`）覆盖：
- 空 `cfg` → `Manager.tools()` 为空、`close()` 立即返回；
- 失败隔离：构造一个 stdio server 指向不存在的 command（`command="/no/such/bin"`）+ 一个用单测注入 stub 的成功"server"（通过 monkeypatch `_do_connect` 让某 name 走 stub 路径），断言 stub 工具被注册、失败 server 仅产生告警；
- 超时收尾：注入一个会卡住的连接 stub（`async def stub_connect(...): await asyncio.Event().wait()`），把 `connect_timeout` 临时改为 0.2，断言 `new_manager` 在 ~0.2s 内返回且 stderr 有 timeout 告警；
- close 兜底：注入一个 close 阻塞的 fake context manager（`__aexit__` 内 `await asyncio.Event().wait()`），把 `close_timeout` 改 0.2，断言 `close()` 在 0.2s 内返回；
- 并发安全：`pytest --asyncio-mode=auto` 默认就跑在单线程 event loop；额外检查 `_tools` 顺序由 `sort` 决定而非 task 完成顺序。

## T5: cli 接线**文件：** `src/gcode/cli.py`
**依赖：** T2、T3、T4
**步骤：**
1. import `asyncio`、`gcode.mcp as mcp_client`。
2. 把现有 `main()` 拆为 `async def _amain() -> int` + `def main() -> None: raise SystemExit(asyncio.run(_amain()))`（若已是 async 结构则直接接线）。
3. 在 `registry = tool.default_registry()` 之后插入：
   ```python
   mcp_cfg = mcp_client.load_config(root)
   mgr = await mcp_client.new_manager(mcp_cfg, version=__version__)
   try:
       for t in mgr.tools():
           registry.register(t)
       # 既有：构造 PermissionEngine、GCodeApp，await app.run_async()
       ...
   finally:
       await mgr.close()
   ```
4. `root` 复用 `os.getcwd()`；`version` 复用 `__version__`。

**验证：** `python -m gcode` 无 MCP 配置时进 TUI、内置 6 工具可用；配一个 command 不存在的 stdio server 时进 TUI 不阻塞、stderr 显示连接失败告警。

## T6: 配置示例**文件：** `docs/ch07/mcp-servers.example.yaml`
**依赖：** 无（可与 T2 并行）
**步骤：**
1. 内容（用 YAML 注释说明放置位置与覆盖语义）：
   ```yaml
   # 项目级放 <root>/.gcode.yaml；用户级放 ~/.gcode/config.yaml。
   # 同名 server 项目级完整覆盖用户级。
   # env / headers 的值支持 ${VAR} 从宿主环境变量展开；command/args 不展开。
   mcp_servers:
     github:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-github"]
       env:
         GITHUB_TOKEN: "${GITHUB_TOKEN}"
     local-sqlite:
       type: stdio
       command: python
       args: ["-m", "mcp_server_sqlite", "--db", "./data.db"]
     example-http:
       type: http
       url: "https://mcp.example.com/mcp"
       headers:
         Authorization: "Bearer ${EXAMPLE_TOKEN}"
   ```

**验证：** 在 `tests/test_mcp_config.py` 增加一个用例，读取此示例文件断言三个 server 都被解析成功（`monkeypatch.setenv("GITHUB_TOKEN", "x")` 等避免 undefined 噪音）。

## T7: tmux 端到端实跑（CLAUDE.md 开发原则）**文件：** —
**依赖：** T1–T6
**步骤：**
1. 准备一个真实可用的 stdio MCP server。优先用 `npx -y @modelcontextprotocol/server-everything`（官方示例 server，自带 echo / add 等基础工具）；若无 npx，可临时用一个最小 Python server（`uv run mcp dev examples/...` 风格）。
2. 在项目根写一个临时 `.gcode.yaml` 指向它：
   ```yaml
   mcp_servers:
     demo:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-everything"]
   ```
3. `tmux` 起 gcode：
   - 启动日志（stderr）显示 server 连接成功 + 工具数；TUI 状态栏正常；
   - 让模型调用 `mcp__demo__echo` 一类工具：default 模式下弹人在回路 → 允许本次 → 工具结果回灌 → 模型续答；
   - 选"永久允许"后，本地权限规则被写入；重启 gcode 后再调同工具不再弹窗（验证永久规则与 ch07 命名空间联动）；
   - 切到 bypassPermissions：调用不弹窗；但让模型跑 `rm -rf /` 仍被内置黑名单拦下（MCP 工具不绕过黑名单的内置作用域）；
   - Esc 取消弹窗：干净回到 idle，不退出程序；
   - 退出 gcode（`/exit` 或 Ctrl+C）后 `ps -ef | grep server-everything` 确认子进程已终止；
4. 配置一个 command 不存在的 server + 一个能跑的 server：启动 stderr 有失败告警，能跑的 server 工具仍可用。

**验证：** 上述全部观察通过；删除临时 `.gcode.yaml`，恢复项目根干净。

## T8: 全量编译测试与规范**文件：** —
**依赖：** T1–T7
**步骤：**
1. `ruff format --check .`（应无 diff）；`ruff check .`（应无告警）。
2. （可选）`mypy src/gcode/mcp`（启用 strict 子集亦可）。
3. `pytest`（含新增的 `tests/test_mcp_*.py`）。
4. `pytest --asyncio-mode=auto tests/test_mcp_manager.py tests/test_agent/` 之类——重点守护 Manager 并发连接、共享状态、close 兜底无悬挂 task / 死锁。
5. `git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'`（应无命中：凭据不落盘）。
6. `git check-ignore -q docs/ch07/mcp-servers.example.yaml` 不需要忽略（示例只含 `${VAR}`）。

**验证：** 全部通过。

## 执行顺序

```
T1(SDK 依赖) ─┬─→ T2(config) ─┐
              │                ├─→ T4(manager) ─→ T5(cli 接线) ─→ T7(tmux 实跑) ─→ T8(规范)
              └─→ T3(tool)   ─┘
                                 └─→ T6(配置示例)（可与 T2 并行）
```
依赖：T2,T3 ← T1；T4 ← {T2,T3}；T5 ← {T2,T3,T4}；T6 独立于 T3、T4（可在 T2 完成后做）；T7 ← T1–T5；T8 ← 全部。
````

```markdown
# MCP 客户端 Checklist

> 每一项通过运行代码或观察行为来验证；函数 / 类型名仅作定位提示，核验断言本身不依赖其命名（重命名实现而行为不变时本清单仍适用）。

## 实现完整性
- [ ] 加载两层配置：两文件存在时按 server 名合并、同名 server 项目级完整覆盖用户级（验证：单测构造两层文件断言合并结果与字段来源）。(AC1/F1)
- [ ] 配置降级：任一文件缺失视为空、格式非法跳过该文件 + stderr 告警 + 其它正常加载，不致启动失败（验证：单测分别投喂缺失与非法 YAML，断言 `load_config` 不抛异常且其它层 server 仍在）。(AC1/N1)
- [ ] 字段校验：stdio 缺 command、http 缺 url、`type` 非法或缺失，均跳过该 server + stderr 给出原因，其它 server 不受影响（验证：单测分别构造各非法 server）。(AC2/N2)
- [ ] `${VAR}` 展开：env / headers 的值被展开；未定义变量展开为空串 + 一次性告警；command / args / 工具名 / server 名不展开（验证：单测覆盖各分支，含 `command: ${X}` 应保留字面量）。(AC3/F3)
- [ ] stdio 连接 + 握手 + 列工具：能拉起一个 MCP server 子进程并由 SDK 完成 `session.initialize()` + `session.list_tools()`；`env` 被注入到子进程环境（验证：用单测脚本启动一个最小 echo MCP server 或 tmux 实跑 `@modelcontextprotocol/server-everything`）。(AC4/F4/F6)
- [ ] HTTP 连接 + 自定义 headers：能对 HTTP MCP server 完成握手 + 列工具；`headers` 真正出现在每个 HTTP 请求中（验证：用 `pytest-httpx` 或 `httpx.MockTransport` 起一个最小 HTTP 端点 + 注入 `Authorization` 头，断言 server 端收到该头）。(AC5/F5/F6/N6)
- [ ] 工具命名：所有 MCP 工具的 `name` 形如 `mcp__<server>__<tool>`；前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）的工具被跳过并告警（验证：单测构造含 `.` 的 server 名 / 工具名，断言 `adapt_tool` 返回 `None`）。(AC6/AC7/F8)
- [ ] 命名空间隔离：同一 tool 名在不同 server 互不覆盖；与 6 个内置工具天然不重名（验证：registry 注册后断言全名集合无重复）。(AC7/F8)
- [ ] 工具适配字段：description 空 → 兜底文案；schema 透传为 `dict[str, Any]`、空 schema 兜底 `{"type": "object"}`；`annotations.readOnlyHint==True` → `read_only is True`，其它（含 None / False）→ `False`（验证：单测覆盖各分支，含 `annotations is None` None-safe）。(AC6/F7)
- [ ] 调用结果聚合：`execute` 把远端多个 text content 块按顺序拼成 `content`；非 text 块（image/audio/resource_link/embedded_resource）静默丢弃 + 单 tool 限一次告警（验证：`test_mcp_tool` 注入 stub 返回混合内容块，断言 collected 仅含 text 且告警计数为 1）。(AC6/F7)
- [ ] 远端错误映射：远端 `isError==True` 时 `ToolResult.is_error is True`，`content` 仍为远端 text（验证：`test_mcp_tool` 注入 stub 返回 `isError=True` + text 块）。(AC6/F7)
- [ ] 协议错与超时回灌：`call_tool` 抛异常或 30s `asyncio.wait_for` 超时 → `is_error is True` 且 `content` 含可读错因，Agent Loop 不中断（验证：`test_mcp_tool` 注入 stub 抛异常 / 阻塞至超时，断言 `is_error` 与文案）。(AC9/F7/F10/N5)
- [ ] 启动失败隔离：有 server 连接 / 握手 / 列工具失败时，只跳过它自身，其它 server 与内置工具集照常注册可用（验证：`test_mcp_manager` 用一个失败 server + 一个 stub 成功 server，断言成功 server 工具被注册）。(AC8/F9/N1)
- [ ] 30s 启动超时：模拟连接卡住的 server 在（测试中缩短的）超时窗口结束后被跳过，启动不阻塞超过该窗口（验证：`test_mcp_manager` 注入连接 stub `await asyncio.Event().wait()` + `monkeypatch.setattr(manager, "connect_timeout", 0.2)`，断言 `new_manager` 在超时窗口附近返回）。(AC8/F9/N1)
- [ ] 退出干净：`Manager.close()` 通过 `AsyncExitStack.aclose()` 终止所有 stdio 子进程、断开 HTTP 会话；某 session 关闭卡住时 5s 兜底返回不阻塞（验证：`test_mcp_manager` 注入 `__aexit__` 阻塞的 fake 上下文 + 短兜底，断言 `close()` 在兜底时间内返回；tmux 实跑退出后 `ps` 无残留子进程）。(AC10/F11/N7)

## 集成
- [ ] 权限链路自然命中：无规则时 `readOnlyHint=True` 的 MCP 工具走 Read 兜底（default 直接放行）、其余走 Exec 兜底（default Ask）；allow 规则 `mcp__<server>__*` 命中时直接放行；bypass 模式放行（验证：用 `PermissionEngine` 对 mcp 全名调用断言裁决；tmux 实跑见场景 4）。(AC11/F12/N4)
- [ ] permission 包零改动：`git diff src/gcode/permission/` 在 ch07 期间无任何修改（验证：本章结束时核对 diff 范围）。(N4)
- [ ] provider 适配层零改动：`src/gcode/llm/anthropic_provider.py`、`src/gcode/llm/openai_provider.py` 无修改（验证：核对 diff）。(AC12/N3)
- [ ] 黑名单 / 沙箱对 MCP 工具自动跳过：MCP 工具调用 `extract_target` 返回 `("", False, False)` → 黑名单层因 `target==""` 不命中、沙箱层因 `is_file is False` 不进入（验证：用 permission 的 `check` 对一次 mcp 全名调用断言不被黑名单/沙箱直接 Deny）。(AC11/F12)
- [ ] ch01–ch06 不退化：`pytest` 全过，既有用例不需要适配（验证：运行测试套件）。(AC13/N5)

## 编译与测试
- [ ] `python -m gcode` 在合法配置下能进 TUI（含 / 不含 mcp 配置两种）。
- [ ] `ruff format --check .` 无 diff。
- [ ] `ruff check .` 无告警。
- [ ] `pytest` 通过（含 `tests/test_mcp_config.py` / `tests/test_mcp_tool.py` / `tests/test_mcp_manager.py`，以及既有 config / conversation / tool / agent / prompt / permission / tui 单测）。
- [ ] `pytest --asyncio-mode=auto tests/test_mcp_manager.py` 无悬挂 task / 死锁、无 `RuntimeWarning: coroutine ... was never awaited`（重点守护 Manager 并发连接、共享状态、close 兜底）。(N7/N8)
- [ ] （可选）`mypy src/gcode/mcp` 通过。
- [ ] 凭据不落盘：配置示例 / 文档 / 测试 fixture 全用 `${VAR}`；`git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'` 在 ch07 期间无命中。(AC14/N6)

## 端到端场景（tmux 实跑）
- [ ] 场景 1（无 MCP 配置）：仓库内不存在 `.gcode.yaml` 与 `~/.gcode/config.yaml` 时，gcode 正常进 TUI；registry 仅含 6 个内置工具；stderr 无 mcp 相关告警。(AC1)
- [ ] 场景 2（stdio server 接入）：在 `.gcode.yaml` 配置 `@modelcontextprotocol/server-everything` 一类真实 server，启动后日志显示 server 连接成功 + 工具数；TUI 中让模型调用其中一个工具（如 echo），default 模式弹人在回路 → 「允许本次」→ 工具结果回灌 → 模型续答。(AC4/AC6/AC11)
- [ ] 场景 3（失败隔离）：配置一个不存在 command 的 server + 一个能跑的 server，启动 stderr 有第一个 server 的失败告警；能跑的 server 工具仍可用、能正常调用。(AC8)
- [ ] 场景 4（永久放行 + 重启）：场景 2 中选「永久允许」→ `.gcode/settings.local.yaml` 出现对应 `mcp__<server>__<tool>` allow 规则；重启 gcode 后再调该工具不再弹窗直接执行。(AC11)
- [ ] 场景 5（凭据展开）：配置 `env: { GITHUB_TOKEN: "${GITHUB_TOKEN}" }`；`unset GITHUB_TOKEN` 启动时 stderr 有 undefined 告警但 server 仍尝试启动（server 自决报错与否）；`export GITHUB_TOKEN=...` 后正常工作。(AC3/AC14)
- [ ] 场景 6（退出干净）：退出 gcode（`/exit` 或 Ctrl+C）后 `ps -ef | grep server-everything`（或对应 server 进程名）确认子进程无残留。(AC10)
- [ ] 场景 7（bypass + 黑名单兜底）：Shift+Tab 切到 bypassPermissions，MCP 工具调用不弹窗；让模型跑内置 `bash` 工具 `rm -rf /` 仍被黑名单拦下、回灌被拒。(AC11/N4)
- [ ] 场景 8（HTTP server，可选）：本地起一个最小 HTTP MCP server 或用 `pytest-httpx` mock，配置 http 类型 + `headers: { Authorization: "Bearer ${TOKEN}" }`；启动后工具被注册；调用时 server 端日志可见 Authorization 头。(AC5)
```

### Java

```markdown
# MCP 客户端 Spec## 背景ch01–ch06 已经把 gcode 砌成了一个能自主多轮干活、且有五层安全护栏的 coding agent。但**工具集是写死的 6 个内置工具**（读 / 写 / 改文件、命令执行、按模式找文件、搜内容）——想让它会用 GitHub、查数据库、调内部服务，只能改源码、重新编译，能力边界锁死在编译期。

MCP（Model Context Protocol）是一套开放标准，用统一的 JSON-RPC 协议把"提供工具的一方（server）"与"使用工具的一方（client）"解耦，社区已有大量现成 server（GitHub、Slack、SQLite、文件系统……）。ch07 给 gcode 装上 **MCP 客户端**：启动时按配置自动发现并连接外部 server，把它们的工具包装成 gcode 已有的工具抽象、注册进工具中心，Agent 调用时与内置工具**完全无感**，并自动复用 ch06 的权限护栏。这是从"工具集固定"到"工具生态可插拔"的一跃——给 gcode 装上扩展坞。

## 目标- **配置驱动的自动发现**：启动时从配置声明的 server 列表自动连接、列出工具、注册进工具中心，无需改代码。
- **两种传输**：本地 server 走子进程标准输入输出管道（stdio）；远程 server 走 Streamable HTTP。
- **标准三步会话**：每个 server 一次连接经过 初始化握手 → 列出工具 → 按需调用工具（协议细节由官方 Java SDK `com.anthropic:anthropic-java` 同源的 MCP Java SDK 承载,不自研协议栈）。
- **无感适配**：发现到的远端工具包装成与内置工具一致的抽象,Agent 编排层与 provider 适配层均无需感知其来自远端。
- **命名空间隔离**：远端工具统一加 `mcp__<server>__<tool>` 前缀,杜绝与内置工具及多 server 间的重名冲突,并保留来源可追溯。
- **多 server 生命周期管理**：每个连接各自独立缓存与管理；单个 server 连接 / 初始化 / 列工具失败只跳过它自身,不影响其它 server、不影响启动；程序退出时统一、干净地关闭全部连接（含终止 stdio 子进程）。
- **两层配置合并**：server 列表从 **用户级** 与 **项目级** 两个配置文件读取合并,项目级覆盖用户级同名 server。
- **凭据不落盘**：配置中环境变量与请求头的值支持从宿主环境变量展开（`${VAR}`）,密钥不写进配置文件。
- **复用权限**：MCP 工具天然走 ch06 的「规则 → 模式兜底 → 人在回路」链路,默认按命令执行类每次确认,自报只读（`readOnlyHint`）的按只读类放行并可并发；权限包**零改动**。
- **不破坏既有能力**：ch01–ch06 的会话、Loop、流式、缓存、规划、权限五层等行为不退化。

## 功能需求- **F1: 两层 YAML 配置加载与合并**
  从**用户级** `~/.gcode/config.yaml` 与**项目级** `<root>/.gcode.yaml` 两个文件读取 `mcp_servers` 段（map：key 为 server 名,value 为 server 定义）；按 server 名合并,**项目级同名 server 完整覆盖用户级**（不做字段级合并,避免半合并出畸形 server）。文件缺失视为空 `mcp_servers`；文件格式非法时**跳过该文件并 stderr 告警**,绝不致启动失败、不抛未捕获异常。`mcp_servers` 顶层不存在或为空,视为零个 MCP server,正常进 TUI。

- **F2: server 类型与必填字段**
  每个 server 定义自带 `type` 字段（**显式**：`stdio` 或 `http`）,不靠字段嗅探判定类型。
  - `stdio` 类型必填 `command`（字符串）；可选 `args`（字符串数组）、`env`（字符串 map）。
  - `http` 类型必填 `url`（字符串）；可选 `headers`（字符串 map）。
  字段缺失或 `type` 非法时**跳过该 server 并 stderr 告警**,不影响其它 server 加载。

- **F3: 环境变量展开**
  `env` 与 `headers` 的**值**支持 `${VAR}` 形式从宿主环境变量取值；展开发生在配置加载阶段、不污染原始配置文件。**未定义的 `${VAR}` 展开为空串并 stderr 告警**,但不阻断该 server 启动（让 server 自行决定无凭据时是否报错）。`command` / `args` 与 server 名、工具名**不做展开**（避免命令/名字被环境间接影响产生隐性歧义）。

- **F4: stdio 传输**
  对 `stdio` 类型 server,以 `command` + `args` 启动子进程；通过子进程的标准输入输出按 JSON-RPC 帧通信（由 SDK 完成）。`env` 与宿主进程环境合并后注入子进程（同名宿主变量被 `env` 覆盖,便于按 server 配置注入凭据）。`stderr` 透传给宿主 stderr 便于排查。子进程在 gcode 退出时一并干净终止（关闭其 stdin → 等待 → 必要时发信号；由 SDK 承载）。

- **F5: Streamable HTTP 传输**
  对 `http` 类型 server,以 `url` 为 endpoint 走 Streamable HTTP；配置中的 `headers` 注入每次 HTTP 请求（用于 `Authorization` 等鉴权头）。**不订阅服务器推送的独立 SSE 通道**（本章只用请求-响应式工具调用,无需 server 主动推送）,减少长连接维护成本。

- **F6: 标准三步会话**
  每个 server 建立后依次完成 **initialize 握手**（交换 protocolVersion 与 capabilities）→ **`tools/list` 列出工具** → 进入按需 **`tools/call` 调用**阶段。整个协议层（JSON-RPC 编解码、请求/响应 id 配对、握手细节、传输细节）**由官方 Java SDK 承载**,不自研协议栈。本章只覆盖工具能力,**不订阅 / 不实现** MCP 的资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）等其它能力。

- **F7: 工具适配（远端工具 ↔ 内置 Tool 抽象）**
  把 server 返回的每个远端工具包装成一个实现 gcode `Tool` 接口的对象,注册进工具中心：
  - **名字**：`mcp__<server>__<tool>`（见 F8）。
  - **描述**：直接取远端 `description`（空则给一个含 server 名的兜底说明）。
  - **参数 schema**：把远端 `inputSchema` 转成 gcode 的 `Map<String, Object>` 形式（透传 JSON Schema）,不二次裁剪。
  - **只读性**：远端 `annotations.readOnlyHint==true` → `readOnly()==true`；其余（含字段缺失/非法）→ `false`（安全默认按有副作用处理）。
  - **执行**：调用时通过该 server 的会话发 `tools/call`；远端返回的 `content` 中 `type=text` 的文本块按顺序拼成 gcode `Result.content`,远端 `isError==true` 映射为 `Result.isError==true`；非 text 块（image / audio / resource_link / embedded_resource 等）静默丢弃并 stderr 告警一次；调用过程中协议错误（连接断、超时、传输错）也转成 `isError==true` 的结构化错误**回灌给模型**(不抛 Java 异常给 Agent Loop,复用 ch04/ch05 不中断会话的契约)。Agent 与 provider 适配层不感知"该工具来自远端"。

- **F8: 工具命名空间**
  所有 MCP 工具统一以 `mcp__<server>__<tool>` 命名（`server` 与 `tool` 名按配置/远端原样保留）。命名空间用途双重：
  - **避免冲突**：同名远端工具在不同 server 互不干扰；与 6 个内置工具天然不重名。
  - **可追溯**：单看工具名能识别来源 server,便于日志、人在回路弹窗、权限规则书写。
  注册时若仍发生同名（同 server 自报多个同名工具的边界情形）则后注册者保留并 stderr 告警；若工具名经前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）,**跳过该工具并 stderr 告警**。

- **F9: 启动同步连接 + 单 server 30s 超时 + 失败隔离**
  在进入 TUI 之前**同步**对所有配置中的 server 发起连接 + 握手 + 列工具（实现可并发以缩短总时延）；**每个 server 的整个启动序列受 30s 超时约束**（内置不可配）。任一 server 的连接 / 握手 / 列工具失败或超时**只跳过它自身**：gcode 启动不被阻断、其它 server 与内置工具集照常注册可用、stderr 给出该 server 的失败原因。所有 server 连接尝试结束后才进入 TUI；进入 TUI 时工具中心呈现的就是"内置 6 工具 + 成功连上的 server 工具"全集,Agent 在任意一轮看到的工具集稳定不变。

- **F10: 工具调用超时**
  每次 `tools/call` 复用 30s 超时（与连接超时同值,**内置不可配**）；超时按 F7 转成 `isError==true` 的结构化错误回灌给模型,Agent Loop 继续。

- **F11: 退出时统一关闭**
  gcode 正常退出（用户主动退出、致命错收尾）时,对所有已建立的会话统一调用关闭逻辑：stdio server 的子进程被干净终止（先关 stdin、给 server 自然退出窗口、必要时发信号）,HTTP server 的会话用 DELETE 通知 server 释放（由 SDK 处理）。退出**不**强行等待所有连接关闭完成超过若干秒（整体兜底 5s,避免某 server 卡住拖死整个程序退出）。

- **F12: ch06 权限链路无感复用**
  MCP 工具走 ch06 现有判定链路：
  - 黑名单仅作用于内置 `bash` 命令串,对 MCP 工具不命中（`extractTarget` 对未知工具返回 target=""，自动跳过）。
  - 沙箱仅作用于内置文件类工具,对 MCP 工具不适用（`extractTarget` 对未知工具返回 `isFile=false`,自动跳过）。
  - 规则引擎按 `mcp__<server>__<tool>` 作为友好名匹配（`friendlyName` 对未知名原样返回）；用户可用精确名 `mcp__github__create_issue` 或带 `*` 的 `mcp__github__*` 写 allow/deny 规则。
  - 模式兜底：`readOnly()==true` 的 MCP 工具归 `CategoryRead`,default 下直接放行、可并发；其余归 `CategoryExec`,default 与 acceptEdits 下每次触发人在回路 Ask；bypass 下放行。
  **permission 包源码零修改**,只通过既有公共行为承载。

## 非功能需求

- N1: 失败隔离不阻塞——单 server 任意阶段（连接 / 握手 / 列工具 / 调用）失败或卡住,只跳过它自身、不阻塞 gcode 启动、不影响其它 server 与内置工具；连接卡住时 30s 超时强制收尾,绝不死锁。
- N2: 安全默认——`readOnlyHint` 缺失或非法 → 非只读（默认走 Ask）；`${VAR}` 未定义 → 空串（不替 server 拍板）；type 非法 / 字段缺失 → 跳过该 server（不静默放行未定义 server）。
- N3: 跨协议一致——MCP 工具行为与 provider（Anthropic / OpenAI）无关；provider 适配层零修改。
- N4: ch06 权限零改动——permission 包源码零修改；MCP 工具走既有判定链路。
- N5: 不破坏 ch01–ch06——会话、Loop、流式、缓存、规划、人在回路、并发、用户取消、保序回灌等既有能力不退化。
- N6: 凭据不落盘——api_key / token 不出现在配置文件；env / headers 通过 `${VAR}` 引用宿主环境；敏感值在日志/状态栏/任何输出中不回显。
- N7: 退出干净——程序退出时不泄漏子进程、不泄漏 virtual thread、不死锁；某 server 关闭卡住不阻塞整体退出（整体退出关闭兜底超时 5s）。
- N8: 代码规范——`mvn spotless:check`（google-java-format）、`mvn -q -DskipTests package`、`mvn test` 全过（本项目为 Java 21,遵循 CLAUDE.md）。

## 不做的事- **MCP 资源（resources）、提示词（prompts）、采样（sampling）、引导（roots）**——本章只覆盖工具能力。
- **tools/list 变更通知 / 调用进度通知**——不订阅独立 SSE 通道（SDK 默认开,本章显式关闭）,工具集快照固定在启动时。
- **健康检查 / 自动重连 / 退避**——单连接挂掉就挂掉,留待后续章节。
- **配置热加载 / 运行时增减 server**——重启 gcode 才能应用新配置。
- **本地级 mcp_servers 配置层**——仅两层（用户级 + 项目级）。
- **mcp_servers 字段级合并**——按 server 名维度合并,同名项目级完整覆盖用户级。
- **`command` / `args` / 工具名 / server 名 的变量展开**——仅 env / headers 的值展开 `${VAR}`。
- **OAuth 完整鉴权流程**——仅支持 `headers` 直传静态 token；需要 OAuth 的 server 让用户自行预换 token 写入 headers。
- **自定义连接 / 调用超时**——30s 硬编码,不暴露配置项。
- **MCP 工具的黑名单与路径沙箱扩展**——这两层只对内置工具有意义,MCP 工具仅走规则 + 模式兜底 + 人在回路。
- **非文本内容块的回灌**——仅收集 `type=text` 的内容块拼成 Result；image / audio / resource_link / embedded_resource 等静默丢弃并 stderr 告警一次。
- **资源配额 / 速率限制 / 审计日志**——与 ch06 不做事项一致。
- **MCP server 端的实现**——gcode 仅作 client。

## 验收标准

- AC1: 配置加载与两层合并——`~/.gcode/config.yaml` 与 `<root>/.gcode.yaml` 都存在时,按 server 名合并；同名 server 项目级完整覆盖用户级；任一文件缺失或非法时跳过该文件、不致启动失败、其它正常加载。（F1/N1）
- AC2: 字段校验——stdio 类型缺 command、http 类型缺 url、type 非法或缺失时,该 server 被跳过并 stderr 告警,其它 server 不受影响。（F2/N2）
- AC3: 变量展开——env / headers 的值 `${VAR}` 从宿主环境取值；未定义变量展开为空串并告警；command / args / 工具名 / server 名不展开。（F3/N2/N6）
- AC4: stdio 启动 + 子进程终止——能拉起一个 stdio MCP server 子进程,握手 + 列工具成功；env 注入生效；gcode 退出时子进程被终止、无僵尸。（F4/F6/F11/N7）
- AC5: HTTP 连接 + 自定义 headers——能对一个 HTTP MCP server 完成握手 + 列工具；`headers` 注入到 HTTP 请求中。（F5/F6/N6）
- AC6: 工具适配与命名——同一 server 的工具列出后注册进 registry,名字符合 `mcp__<server>__<tool>`,描述非空,参数 schema 透传；调用时远端 text content 拼接为 Result.content,远端 isError 映射到 Result.isError；非 text 块静默丢弃。（F6/F7/F8）
- AC7: 命名空间隔离——同名工具来自不同 server 不互相覆盖；与 6 个内置工具天然不重名；前缀拼接后含 LLM 工具名禁用字符（非 `[A-Za-z0-9_-]`）的工具被跳过并告警。（F8）
- AC8: 启动失败隔离 + 30s 超时——单 server 连接 / 握手 / 列工具失败或超时,只跳过它自身,其它 server 与内置工具集照常注册；失败原因 stderr 可见；启动总时延上界受 30s 约束（并发实现）。（F9/N1）
- AC9: 调用超时与错误回灌——`tools/call` 30s 超时或协议错误转为 `isError==true` 的结构化错误结果回灌给模型,Agent Loop 不中断,可在后续轮调整。（F7/F10/N5）
- AC10: 退出干净——程序退出时所有 stdio 子进程被终止、HTTP 会话被关闭；关闭过程不泄漏 virtual thread、不卡死（总超时 5s 兜底）。（F11/N7）
- AC11: 权限链路自然命中——`mcp__<server>__*` 形式的 allow / deny 规则正确作用到对应 MCP 工具；未写规则时 `readOnlyHint==true` 的 MCP 工具按只读类放行并可并发,其余按命令执行类触发人在回路 Ask；bypass 模式下放行（黑名单 / 沙箱对 MCP 工具不命中,自动跳过）。（F12/N4）
- AC12: 跨协议一致——同一 MCP server 在 Anthropic 与 OpenAI 两种 provider 下行为一致；provider 适配层零 diff。（N3）
- AC13: 不破坏 ch01–ch06——既有所有测试通过；多轮连环、用户取消、流出错恢复、历史一致、缓存命中、规划按轮次注入、ch06 五层权限等行为不退化。（N5）
- AC14: 凭据不落盘——配置示例与说明均用 `${VAR}` 引用密钥；`git grep` 在配置文件中无 token 明文命中。（N6）
- AC15: 代码规范——`mvn spotless:check` 无输出（google-java-format）；`mvn -q -DskipTests package` 通过；`mvn test` 与 mcp 包并发用例（virtual thread + `SubmissionPublisher`）通过。（N8）
```

````markdown
# MCP 客户端 Plan> 技术栈：Java 21（LTS；virtual thread + `Flow.Publisher`）+ Maven；使用 **官方 Java SDK** `io.modelcontextprotocol.sdk:mcp` 承载协议层（JSON-RPC 编解码、initialize 握手、stdio 与 Streamable HTTP 传输）。本章新增 **`dev.gcode.mcp` 包** 与 `Main` 装配,**不改 tool / agent / tui / permission / llm / config / conversation / prompt**。

## 架构概览- **`dev.gcode.mcp` 包（新增）**：承载 MCP 客户端的全部职责——配置加载与两层合并、`${VAR}` 展开、字段校验、调用 SDK 建立 stdio / HTTP 会话、把远端工具适配成内置 `Tool`、统一管理生命周期。仅依赖 `dev.gcode.tool`、SDK 与 JDK 标准库；不依赖 agent / tui / permission / conversation。
- **`Main`（改造）**：在 `ToolRegistry.defaults()` 之后、`PermissionEngine` 与 `TuiApp` 之前,加载 mcp 配置 → 启动 `McpManager` → 把 Manager 产出的工具注册进 registry → 退出时通过 `Runtime.getRuntime().addShutdownHook(...)`（或 try-with-resources）触发 `manager.close()`。
- **`tool` 包（零改）**：`ToolRegistry.register(...)` 与 `Tool` 接口本就是开放抽象,直接吃 `McpTool` 实例；`isReadOnly(...)` 对 MCP 工具返回正确值。
- **`agent` / `tui` 包（零改）**：工具流转链路对工具来源透明。
- **`permission` 包（零改）**：`friendlyName(...)` 对未知名原样返回 → 规则可写 `mcp__<server>__<tool>`；`categorize(...)` 在 `readOnly==true` 时走 `CategoryRead`、否则归 `CategoryExec` → 模式兜底矩阵自然命中；`extractTarget(...)` 对未知工具返回 `("", false, false)`,黑名单与沙箱自动跳过。
- **`llm` / provider（零改）**：工具定义透传,协议无关。

数据流（单次调用）：
```
agent.executeBatched(calls, mode)
  └→ engine.check(...)  → Allow → registry.execute(name, args)
       └→ McpTool.execute(args)                        [本章新增工具实现]
            ├→ CompletableFuture.orTimeout(30, SECONDS)
            ├→ session.callTool({ name: remoteName, arguments: map })
            └→ 拼接 text content / 映射 isError / 协议错转 isError
       └→ ToolResult{ content, isError }                ── 回灌 conv
```

## 核心数据结构### `McpConfig` / `ServerConfig`（对外）
```java
package dev.gcode.mcp;

// McpConfig 是 mcp_servers 在内存中的归一化形式（已展开 ${VAR}、已合并、已校验）。
public record McpConfig(java.util.Map<String, ServerConfig> servers) {}

// ServerConfig 是单个 MCP server 的完整定义。
public record ServerConfig(
        String type,                              // "stdio" | "http"
        String command,                           // stdio 必填
        java.util.List<String> args,              // stdio 可选
        java.util.Map<String, String> env,        // stdio 可选(已展开)
        String url,                               // http 必填
        java.util.Map<String, String> headers     // http 可选(已展开)
) {}
```

### `McpManager`（对外不透明）
```java
public final class McpManager implements AutoCloseable {
    private final Object lock = new Object();
    private final java.util.List<Session> sessions = new java.util.ArrayList<>();  // 已建立成功的 server 会话
    private final java.util.List<Tool>    tools    = new java.util.ArrayList<>();  // 已适配好的工具

    record Session(String name, McpClientSession cs) {}
}
```

`McpClientSession` 是官方 SDK 的客户端会话类型（包名以 SDK 实际为准,`io.modelcontextprotocol.client.McpAsyncClient` 一类）。

### 工具适配（包内私有）
```java
// McpTool 实现 dev.gcode.tool.Tool。
final class McpTool implements dev.gcode.tool.Tool {
    private final String  fullName;                        // "mcp__<server>__<tool>"
    private final String  remoteName;                      // server 上的原始工具名
    private final String  description;
    private final java.util.Map<String, Object> schema;    // JSON Schema 透传
    private final boolean readOnly;                        // 仅来自远端 annotations.readOnlyHint==true
    private final CallerSession session;                   // 接口形式持有,便于单测注入 stub
}

// CallerSession 是 McpTool 依赖的最小会话能力(生产实现包装 SDK 的 async client)。
interface CallerSession {
    CallToolResult callTool(String name, java.util.Map<String, Object> arguments)
            throws Exception;  // 同步阻塞;超时由调用方包 CompletableFuture.orTimeout 实现
}
```

## 核心接口

```java
// 加载并合并两层配置;返回归一化的 McpConfig。
// - root: 项目根(用来定位 <root>/.gcode.yaml)
// - 文件不存在 → 视为空层;格式非法 → 跳过该层 + stderr 告警(降级,N1)
// - 内部完成 ${VAR} 展开与字段校验(非法 server 直接剔除,N2)
// - 永不抛出 checked 异常;签名仅声明运行时降级行为
public static McpConfig loadConfig(java.nio.file.Path root);

// 启动 McpManager:并发连接所有 server,每个 server 30s 超时,失败仅跳过 + 告警。
// 阻塞直到所有 server 的尝试结束(成功 / 失败 / 超时)。
// version 透传到 implementation.version(便于 server 端识别 gcode 版本)。
public static McpManager start(McpConfig cfg, String version);

// 返回适配好的工具列表(按 server 名 → 工具名 稳定排序)。
public java.util.List<dev.gcode.tool.Tool> tools();

// 关闭所有会话(stdio 子进程终止、HTTP DELETE);总超时 5s 兜底,绝不阻塞退出。
@Override public void close();
```

## 模块设计### `dev/gcode/mcp/ConfigLoader.java`
**职责：** 加载两层 YAML、合并、展开 `${VAR}`、校验。
**关键点：**
- 内部 record `RawServer(String type, String command, List<String> args, Map<String,String> env, String url, Map<String,String> headers)`。
- 用 `org.snakeyaml.engine.v2.api.Load` 把文件解析成 `Map<String, Object>`,读 `mcp_servers` 段后逐项手动绑定到 `RawServer`。
- `loadFile(Path path) -> Map<String, RawServer>`:文件不存在 → 空 map;解析失败 → 空 map + stderr 告警(降级)。
- `expandVars(String s) -> Expansion(String out, List<String> undefined)`:正则 `\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}` 匹配,用 `System.getenv(name)` 取值,未定义变量名记录到 undefined(供告警)。**仅作用于 env / headers 的值**。
- `applyExpansion(String name, RawServer srv)`:对 env / headers 的每个 value 跑 `expandVars`,原地替换;未定义变量在 stderr 输出 `[mcp] warn: undefined env var ${X} referenced by server <name>`。
- `mergeServers(Map<String,RawServer> user, Map<String,RawServer> project)`:新建 `LinkedHashMap`,复制 user,遍历 project 直接整对象覆盖同名 key。
- `validateServer(String name, RawServer srv) -> Optional<ServerConfig>`:
  - `type` 必为 `"stdio"` 或 `"http"`,否则跳过；
  - `stdio` 必填 `command`;`http` 必填 `url`;缺失则跳过；
  - 违规时 stderr 告警 `[mcp] warn: skip server <name>: <reason>`。
- `loadConfig(Path root)`:
  - 用户级 = `System.getProperty("user.home")` 取家目录 + `/.gcode/config.yaml`;项目级 = `root.resolve(".gcode.yaml")`。
  - 两层各自 `loadFile` + `applyExpansion`;任一层解析失败 stderr 一行告警并跳过(该层视为空)。
  - `mergeServers` 后逐个 `validateServer`,组装 `McpConfig`。

### `dev/gcode/mcp/McpManager.java`
**职责：** 连接 server、缓存会话、关闭。
**关键点：**
- `start(cfg, version)`:
  - 内部 `McpManager mgr = new McpManager();`
  - 对每个 server 用 `Thread.startVirtualThread(() -> connectOne(name, srv, version, mgr));` 并发起 virtual thread;`CountDownLatch` 等齐。
  - `connectOne(...)` 内:
    - `CompletableFuture<Void> deadline = new CompletableFuture<>();`
    - 调度器 `ScheduledExecutorService.schedule(() -> deadline.completeExceptionally(new TimeoutException()), 30, SECONDS)`。
    - 按 `type` 构造 transport:
      - **stdio**:`ServerParameters params = ServerParameters.builder(srv.command()).args(srv.args()).env(mergeOsEnv(srv.env())).build();` → `transport = new StdioClientTransport(params);`(SDK 内部启动子进程,stderr 透传到宿主 stderr)。
      - **http**:`HttpClient hc = HttpClient.newBuilder().build();` → `transport = HttpClientStreamableHttpTransport.builder(srv.url()).httpClient(hc).customizeRequest(rb -> srv.headers().forEach(rb::header)).disableServerSentEvents(true).build();`(SDK 暴露的 `customizeRequest` 钩子在每次请求前注入 headers)。
    - `McpAsyncClient client = McpClient.async(transport).clientInfo(new Implementation("gcode", version)).build();`
    - `client.initialize().block(Duration.ofSeconds(30));` ← SDK 自动完成 initialize 握手;超时抛 `RuntimeException`,异常 → stderr 一行告警 + return。
    - `ListToolsResult lst = client.listTools().block(Duration.ofSeconds(30));`;异常 → stderr 告警 + `client.closeGracefully().block(Duration.ofSeconds(5))`(避免连了但列工具失败的连接泄漏) + return。
    - 对每个返回工具调 `adaptTool(name, t, new AsyncCallerSession(client))`;成功的 push 到临时列表。
    - `synchronized (mgr.lock)`:`mgr.sessions.add(...)`;`mgr.tools.addAll(adapted)`。
  - `latch.await()` 后稳定排序 `mgr.tools`(先 server 名再 tool 名;`fullName` 已含 server 前缀,按 `Comparator.comparing(Tool::name)`)。
  - 返回 `mgr`。
- `mergeOsEnv(Map<String,String> extra)`:`new HashMap<>(System.getenv())` 后用 `extra.forEach(map::put)` 覆盖,返回。
- `customizeRequest`:SDK 暴露的 `Consumer<HttpRequest.Builder>` 钩子;`headers.forEach(builder::header)` 即把每个 header 注入到每次请求。
- `tools()`:返回 `List.copyOf(this.tools)`(防外部修改)。
- `close()`:
  - 每个 session 起 virtual thread `Thread.startVirtualThread(() -> session.cs().closeGracefully().block())`;
  - `CountDownLatch` + `latch.await(5, SECONDS)` 兜底;超过 5s 直接 return,不再等。

### `dev/gcode/mcp/McpTool.java`
**职责：** 把 SDK 返回的 `McpSchema.Tool` 适配为 `dev.gcode.tool.Tool`。
**关键点：**
- `adaptTool(String serverName, McpSchema.Tool t, CallerSession cs) -> Optional<McpTool>`:
  - `String fullName = "mcp__" + serverName + "__" + t.name();`
  - **禁用字符校验**:`private static final java.util.regex.Pattern VALID_NAME = java.util.regex.Pattern.compile("^[A-Za-z0-9_-]+$");`;不通过 → `Optional.empty()` + stderr 告警 `[mcp] warn: skip tool <fullName>: name contains illegal characters`。
  - `String descr = t.description();` 为空时兜底 `"来自 MCP server " + serverName + " 的工具 " + t.name()`。
  - `Map<String,Object> schema`:把 `t.inputSchema()` 通过 SDK 自带的 Jackson `ObjectMapper` 序列化为 `Map<String,Object>`;解出 null 或空 map 时给 `Map.of("type", "object")` 兜底(避免 provider 拒收空 schema)。
  - `boolean readOnly = t.annotations() != null && Boolean.TRUE.equals(t.annotations().readOnlyHint());`(null-safe)。
- 实现 `Tool` 接口的 5 个方法(`name()` / `description()` / `parameters()` / `readOnly()` 直接返回字段;`execute(args)` 见下)。
- `execute(JsonNode args)`(返回 `ToolResult`):
  - `Map<String,Object> argMap = (args == null || args.isNull()) ? Map.of() : MAPPER.convertValue(args, new TypeReference<>(){});` 失败 → `new ToolResult("参数解析失败: " + e.getMessage(), true)`。
  - `try { CallToolResult res = CompletableFuture.supplyAsync(() -> session.callTool(remoteName, argMap), VIRTUAL_EXEC).orTimeout(30, TimeUnit.SECONDS).get(); ... }` 失败/超时 → `new ToolResult("MCP 工具调用失败: " + cause.getMessage(), true)`(含 `TimeoutException`)。
  - 否则遍历 `res.content()`:对 `TextContent` 把 `.text()` 追加到 `StringBuilder`(块间 `"\n"` 分隔);非 text 块计数,首次出现时通过包级 `ConcurrentHashMap<String, Boolean>` `putIfAbsent(fullName, Boolean.TRUE)` 限一次,stderr 告警 `[mcp] warn: tool <fullName> returned non-text content blocks (dropped)`。
  - 返回 `new ToolResult(collected, res.isError() != null && res.isError())`。

### `dev/gcode/Main.java`(改造)
位置:在 `ToolRegistry registry = ToolRegistry.defaults();` 之后、`PermissionEngine engine = new PermissionEngine(root);` 之前插入:
```java
McpConfig mcpCfg = ConfigLoader.loadConfig(root);
McpManager mgr   = McpManager.start(mcpCfg, version);
Runtime.getRuntime().addShutdownHook(new Thread(mgr::close, "mcp-shutdown"));
for (Tool t : mgr.tools()) {
    registry.register(t);
}
```
(`root` 复用现有的 `Path.of("").toAbsolutePath()`;`version` 复用 `Main.VERSION` 常量。)

### `dev/gcode/SmokeMain.java`(不改)
smoke 用 `ToolRegistry.defaults()` 不接 MCP,保持非交互简单。

## 文件组织

```
gcode/
├── src/main/java/dev/gcode/mcp/
│   ├── McpConfig.java       — 新:McpConfig / ServerConfig record
│   ├── ConfigLoader.java    — 新:loadConfig、loadFile、expandVars、mergeServers、validateServer
│   ├── McpManager.java      — 新:McpManager、Session、start(并发+30s 超时)、close(5s 兜底)、tools、mergeOsEnv、headers 注入
│   └── McpTool.java         — 新:McpTool、CallerSession、AsyncCallerSession、adaptTool、execute
├── src/test/java/dev/gcode/mcp/
│   ├── ConfigLoaderTest.java — 新:两层合并 / 变量展开 / 字段校验 / 降级 单测
│   ├── McpManagerTest.java   — 新:连接成功/失败/超时、close 不死锁、共享状态并发安全
│   └── McpToolTest.java      — 新:命名拼接、禁用字符跳过、execute 各分支(成功/远端 isError/超时/协议错/非 text 块)
├── src/main/java/dev/gcode/Main.java — 改:装配 McpManager,注册 MCP 工具,addShutdownHook(mgr::close)
├── pom.xml                  — 改:添加 io.modelcontextprotocol.sdk:mcp 依赖
├── docs/ch07/
│   ├── spec.md / plan.md / task.md / checklist.md
│   └── mcp-servers.example.yaml — 新:配置示例(用 ${VAR})
└── (其它包零改)
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 协议层实现 | 官方 Java SDK(`io.modelcontextprotocol.sdk:mcp`) | 用户拍板;避免自研 JSON-RPC/握手/帧;SDK 已处理 stdio 与 Streamable HTTP |
| 配置文件位置 | 项目级 `<root>/.gcode.yaml` + 用户级 `~/.gcode/config.yaml` | 用户拍板;项目级 dotfile 一眼可见、与现有 `.gcode/config.yaml`(providers 凭据)分离 |
| 配置层数 | 仅两层,无本地级 | 用户拍板;`${VAR}` 已让密钥不入配置,本地层冗余 |
| 合并语义 | server 名维度,项目级完整覆盖 | 避免字段级半合并出畸形 server |
| server 类型字段 | 显式 `type: stdio\|http` | 不靠字段嗅探(防止误判);未来扩展易加(如 sse) |
| 变量展开范围 | 仅 env/headers 的值 | 避免 command/args/server 名/工具名被环境间接影响;凭据走 env/headers 已足够 |
| 未定义变量 | 空串 + 一次性告警(不阻断) | server 自决无凭据时是否能跑;gcode 不替它拍板 |
| 工具命名 | `mcp__<server>__<tool>` | 用户拍板;Claude Code 风格;LLM 工具名安全字符;一眼识别来源 |
| 启动连接策略 | 同步进 TUI 前完成 + virtual thread 并发 + 每 server 30s 超时 + 失败跳过 | 进 TUI 时工具集稳定;virtual thread 极廉价,N 个 server 并发不耗资源;隔离避免单 server 拖死启动 |
| 调用超时 | 30s 硬编码,转 isError | 与连接同值;不中断 Loop;避免长卡 |
| readOnly 适配 | 严格只信 `annotations.readOnlyHint==true` | 默认走 Ask,最严;声明只读才放行 |
| 资源/提示词/采样/roots | 不实现 | 本章只覆盖工具能力 |
| 独立 SSE 通道 | `disableServerSentEvents(true)` | 只用请求-响应;省一条长连接;减少复杂度 |
| 非 text 内容块 | 静默丢弃 + 一次性告警 | 模型只能消费文本;丢弃比假装回灌更诚实 |
| 错误回灌 | 协议错/超时均转 isError | 与 ch04/ch05 不中断 Loop 契约一致 |
| 退出关闭 | 每 session.closeGracefully 并发 virtual thread + 5s 总超时兜底 | 避免某 server 卡死阻塞退出 |
| permission 接入方式 | 零改动;靠 `friendlyName` 原样 + `categorize` 按 readOnly 优先 | 复用现成链路;权限规则可写 `mcp__server__tool` 与 `mcp__server__*` |
| HTTP 自定义 headers | SDK 暴露的 `customizeRequest(Consumer<HttpRequest.Builder>)` 钩子注入 | SDK 原生支持,不需要包一层 `HttpClient.Interceptor` |
| OAuth | 不实现完整流程 | 用户预换 token 写 headers;本章范围最小化 |
| execute 接口注入 | McpTool 持 `CallerSession` 接口而非具体 SDK client | 单测可注入 stub;生产代码无运行时开销 |
| 异步桥接 | SDK 的 `Mono<T>` 一律 `.block(Duration.ofSeconds(30))` 转同步;调用层用 `CompletableFuture.orTimeout` 二次兜底 | gcode 内部以同步阻塞为主线(virtual thread 顶替线程池);避免把 Reactor 类型外泄到 mcp 包之外 |

## 模块交互

```
Main.main()
  ├─ ToolRegistry registry = ToolRegistry.defaults();           // 6 内置工具
  ├─ McpConfig cfg = ConfigLoader.loadConfig(root);             // 读两层 yaml + ${VAR} 展开 + 校验
  ├─ McpManager mgr = McpManager.start(cfg, version);           // virtual thread 并发连接所有 server,30s/各
  │     └─ 对每个 server:
  │         ├─ 构造 transport(stdio: StdioClientTransport / http: HttpClientStreamableHttpTransport)
  │         ├─ McpClient.async(transport).clientInfo(...).build() + .initialize().block()(自动 initialize 握手)
  │         ├─ .listTools().block()
  │         └─ adaptTool 包装成 McpTool
  ├─ for (Tool t : mgr.tools()) registry.register(t);
  ├─ PermissionEngine engine = new PermissionEngine(root);
  ├─ TuiApp.builder().registry(registry).engine(engine).build().run();
  └─ Runtime.getRuntime().addShutdownHook(new Thread(mgr::close)); // stdio 终止子进程,HTTP DELETE 会话;5s 总超时兜底
```

调用链(Agent 视角,工具来源透明):
```
agent.executeBatched(calls, mode)
  └ engine.check(mode, call, registry.isReadOnly(call.name()))
       (MCP 工具:friendlyName 原样;categorize:readOnly==true→Read, 否则→Exec;
        extractTarget(未知工具)→isFile=false,target="" → 黑名单/沙箱自动跳过)
  └ Allow → registry.execute(name, args)
       └ McpTool.execute(args)
            ├ CompletableFuture.orTimeout(30, SECONDS)
            └ session.callTool → 拼接 text / 映射 isError / 协议错转 isError
  └ ToolResult 回灌 conv
```

依赖方向(无环):`Main → mcp → { tool, llm, SDK, JDK 标准库 }`;`mcp` 不依赖 `agent / tui / permission / conversation`。
````

````markdown
# MCP 客户端 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改   | `pom.xml` | 添加 `io.modelcontextprotocol.sdk:mcp` 依赖 |
| 新建 | `src/main/java/dev/gcode/mcp/McpConfig.java` | `McpConfig` / `ServerConfig` record |
| 新建 | `src/main/java/dev/gcode/mcp/ConfigLoader.java` | `loadConfig`、`loadFile`、`expandVars`、`applyExpansion`、`mergeServers`、`validateServer` |
| 新建 | `src/test/java/dev/gcode/mcp/ConfigLoaderTest.java` | 两层合并 / `${VAR}` 展开 / 字段校验 / 降级 单测 |
| 新建 | `src/main/java/dev/gcode/mcp/McpTool.java` | `CallerSession` 接口、`McpTool`、`AsyncCallerSession`、`adaptTool`、`execute`、非 text 块告警 once 池 |
| 新建 | `src/test/java/dev/gcode/mcp/McpToolTest.java` | 命名拼接 / 禁用字符 / `execute` 成功 / 远端 isError / 超时 / 协议错 / 非 text 块跳过 单测 |
| 新建 | `src/main/java/dev/gcode/mcp/McpManager.java` | `McpManager`、`Session`、`start`(并发 + 30s 超时)、`close`(5s 兜底)、`tools`、`mergeOsEnv`、headers 注入 |
| 新建 | `src/test/java/dev/gcode/mcp/McpManagerTest.java` | 连接成功/失败/超时、`close` 不死锁、并发写共享状态安全 单测 |
| 改   | `src/main/java/dev/gcode/Main.java` | 装配 `ConfigLoader.loadConfig`、`McpManager.start`、注册 MCP 工具、`addShutdownHook(mgr::close)` |
| 新建 | `docs/ch07/mcp-servers.example.yaml` | 配置示例(含 stdio / http 各一个,用 `${VAR}`) |

---

## T1: 添加 MCP Java SDK 依赖**文件：** `pom.xml`
**依赖：** 无
**步骤：**
1. 在 `<dependencies>` 节加入：
   ```xml
   <dependency>
     <groupId>io.modelcontextprotocol.sdk</groupId>
     <artifactId>mcp</artifactId>
     <version>0.10.0</version>  <!-- 以 Maven Central 上最新稳定为准 -->
   </dependency>
   ```
2. `mvn -q dependency:resolve` 拉取依赖；查看本地仓库确认 `mcp-<ver>.jar` 出现。
3. 写一段最小试编(可直接放进后续 `McpTool.java` 的 import 中)：`import io.modelcontextprotocol.client.McpClient;` 并 `McpClient.async(/* dummy transport */)`,验证可用。

**验证：** `mvn -q -DskipTests package` 编译通过；`mvn dependency:tree | grep modelcontextprotocol` 有命中。

## T2: 配置类型与加载(含两层合并 + 变量展开 + 字段校验)**文件：** `src/main/java/dev/gcode/mcp/{McpConfig,ConfigLoader}.java`、`src/test/java/dev/gcode/mcp/ConfigLoaderTest.java`
**依赖：** T1
**步骤：**
1. 定义对外 record `McpConfig(Map<String, ServerConfig> servers)`、`ServerConfig(String type, String command, List<String> args, Map<String,String> env, String url, Map<String,String> headers)`(见 plan.md「核心数据结构」)。
2. 定义包内 record `RawServer(...)`,字段同 `ServerConfig`(但全部可变成 null,代表"未填")。
3. `static Map<String, RawServer> loadFile(Path path)`：
   - 文件不存在 → 空 `Map`；
   - 用 `org.snakeyaml.engine.v2.api.Load(LoadSettings.builder().build())` 解析为 `Map<String, Object>`；
   - 读取 `mcp_servers` 字段,逐项手动绑定到 `RawServer`(字段 `base_url` 不在此处,但 `args` / `env` / `headers` 注意类型 cast 检查)；
   - `YamlEngineException` / `ClassCastException` → 空 `Map` + stderr 一行告警(降级)。
4. `static record Expansion(String out, List<String> undefined) {}`,`static Expansion expandVars(String s)`：
   - 正则 `Pattern.compile("\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}")` 匹配；用 `System.getenv(name)` 取值；未定义记录变量名到 `undefined`。
5. `static void applyExpansion(String name, RawServer srv)`(返回新 `RawServer` 或就地修改 map,实现自选)：
   - 对 `srv.env()`、`srv.headers()` 的每个值跑 `expandVars`,原地替换；
   - 收集所有 undefined 变量名,去重；首次出现时 `System.err.printf("[mcp] warn: undefined env var ${%s} referenced by server %s%n", v, name);`。
6. `static Map<String, RawServer> mergeServers(Map<String, RawServer> user, Map<String, RawServer> project)`：
   - 新建 `LinkedHashMap`,复制 user；
   - 遍历 project,直接整对象覆盖同名 key。
7. `static Optional<ServerConfig> validateServer(String name, RawServer srv)`：
   - `srv.type()` 必为 `"stdio"` 或 `"http"`,否则跳过；
   - `stdio` 必填 `command`；`http` 必填 `url`；缺失则跳过；
   - 违规时 `System.err.printf("[mcp] warn: skip server %s: %s%n", name, reason);`；返回 `Optional.empty()`。
8. `public static McpConfig loadConfig(Path root)`：
   - 用户级 = `Path.of(System.getProperty("user.home"), ".gcode", "config.yaml")`(取家目录失败时跳过用户层不致错)；项目级 = `root.resolve(".gcode.yaml")`。
   - 两层各自 `loadFile`；解析失败(非"文件不存在") → 一行 stderr 告警 + 该层视为空。
   - 对每层各 server 跑 `applyExpansion`。
   - `mergeServers` 后逐个 `validateServer`,收齐合法 server 组装 `McpConfig`。
   - 永不抛出 checked 异常(签名也不声明)。

**验证：** `mvn -q -DskipTests package`；`mvn test -Dtest=ConfigLoaderTest` 覆盖：
- 两文件缺失 → `McpConfig.servers()` 为空、无异常；
- 仅用户级 / 仅项目级 / 都有(同名 server 项目级胜出,断言字段为项目级值)；
- 文件格式非法 → 跳过该层、其它正常加载、stderr 有告警(测试中用 `System.setErr(...)` 重定向断言)；
- `${VAR}` 已定义 → 展开为环境值；未定义 → 空串 + 告警；`command` / `args` 中含 `${VAR}` → 不展开(保留字面量)；
- `type` 缺失 / `type` 非法 / stdio 缺 command / http 缺 url → 该 server 被跳过,其它 server 不受影响。

## T3: 工具适配(McpTool)**文件：** `src/main/java/dev/gcode/mcp/McpTool.java`、`src/test/java/dev/gcode/mcp/McpToolTest.java`
**依赖：** T1
**步骤：**
1. `import io.modelcontextprotocol.spec.McpSchema;` `import io.modelcontextprotocol.spec.McpSchema.CallToolResult;` `import dev.gcode.tool.Tool;` `import dev.gcode.tool.ToolResult;`。
2. 定义包内最小接口 `interface CallerSession { CallToolResult callTool(String name, Map<String,Object> arguments) throws Exception; }`,与 `final class McpTool implements Tool`(见 plan.md「核心数据结构」)。
3. 包级常量：
   ```java
   private static final java.util.regex.Pattern VALID_NAME =
           java.util.regex.Pattern.compile("^[A-Za-z0-9_-]+$");
   private static final com.fasterxml.jackson.databind.ObjectMapper MAPPER =
           new com.fasterxml.jackson.databind.ObjectMapper();
   private static final java.util.concurrent.ConcurrentHashMap<String, Boolean> NON_TEXT_WARNED =
           new java.util.concurrent.ConcurrentHashMap<>();
   ```
4. 实现 `Tool` 接口的 4 个 getter（`name()` / `description()` / `parameters()` / `readOnly()`,均直接返回字段）。
5. `static Optional<McpTool> adaptTool(String serverName, McpSchema.Tool t, CallerSession cs)`：
   - `String fullName = "mcp__" + serverName + "__" + t.name();`
   - `if (!VALID_NAME.matcher(fullName).matches()) { System.err.printf("[mcp] warn: skip tool %s: name contains illegal characters%n", fullName); return Optional.empty(); }`
   - `String descr = (t.description() == null || t.description().isBlank()) ? "来自 MCP server " + serverName + " 的工具 " + t.name() : t.description();`
   - `Map<String, Object> schema = MAPPER.convertValue(t.inputSchema(), new TypeReference<Map<String, Object>>(){});` 若 `schema == null || schema.isEmpty()` → `schema = Map.of("type", "object");`。
   - `boolean readOnly = t.annotations() != null && Boolean.TRUE.equals(t.annotations().readOnlyHint());`
   - 返回 `Optional.of(new McpTool(fullName, t.name(), descr, schema, readOnly, cs));`。
6. `public ToolResult execute(com.fasterxml.jackson.databind.JsonNode args)`：
   - `Map<String, Object> argMap;`
   - `if (args == null || args.isNull()) { argMap = Map.of(); } else { try { argMap = MAPPER.convertValue(args, new TypeReference<>(){}); } catch (IllegalArgumentException e) { return new ToolResult("参数解析失败: " + e.getMessage(), true); } }`
   - 调用 + 30s 超时：
     ```java
     CallToolResult res;
     try {
         res = java.util.concurrent.CompletableFuture
                 .supplyAsync(() -> { try { return session.callTool(remoteName, argMap); } catch (Exception e) { throw new java.util.concurrent.CompletionException(e); } },
                              java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor())
                 .orTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
                 .get();
     } catch (Exception e) {
         Throwable cause = (e.getCause() != null) ? e.getCause() : e;
         return new ToolResult("MCP 工具调用失败: " + cause.getMessage(), true);
     }
     ```
   - 遍历 `res.content()`：
     - `instanceof McpSchema.TextContent tc` → `sb.append(tc.text()).append('\n');`
     - 其余分支 → 计数 + `NON_TEXT_WARNED.putIfAbsent(fullName, Boolean.TRUE)` 限一次,触发时 stderr 告警 `[mcp] warn: tool <fullName> returned non-text content blocks (dropped)`。
   - 返回 `new ToolResult(sb.toString().stripTrailing(), Boolean.TRUE.equals(res.isError()));`。

**验证：** `mvn test -Dtest=McpToolTest` 覆盖：
- 合法 server 名 + 工具名 → `adaptTool` 返回非空；含 `.` / `@` 等非法字符 → 返回空 + 告警；
- description 空 → 兜底文案出现；schema null → `{"type":"object"}`；schema 透传成功；
- `t.annotations() == null` → `readOnly==false`(不抛 NPE)；`readOnlyHint==true` → `readOnly==true`；
- `execute`：注入 stub `CallerSession`,覆盖：成功(多 text 块拼接) / 远端 `isError=true` 映射 / `callTool` 抛异常转 `isError=true` / 阻塞至超时(用 stub `Thread.sleep(60_000)` + 测试中把超时改成 200ms,断言 `TimeoutException` 转 isError) / 非 text 块跳过 + collected 仅含 text。

## T4: 连接管理器(McpManager)**文件：** `src/main/java/dev/gcode/mcp/McpManager.java`、`src/test/java/dev/gcode/mcp/McpManagerTest.java`
**依赖：** T2、T3
**步骤：**
1. 定义 `public final class McpManager implements AutoCloseable` 与内嵌 `record Session(String name, McpAsyncClient client) {}`(见 plan.md)。
2. headers 注入：SDK 的 `HttpClientStreamableHttpTransport.builder(...).customizeRequest(rb -> ...)` 钩子已足够,不需要自行包 `HttpClient`。若 SDK 没有该钩子(版本差异),退一步用：
   ```java
   HttpClient hc = HttpClient.newBuilder()
           .executor(java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor())
           .build();
   // 然后构造一个 `HttpRequest.Builder` Consumer 钩子注入 headers
   ```
3. `static List<String> mergeOsEnv(Map<String,String> extra)`：把 `System.getenv()` 转 `LinkedHashMap`,用 `extra.forEach(map::put)` 覆盖同名键,再 `map.entrySet().stream().map(e -> e.getKey() + "=" + e.getValue()).toList()`(若 SDK 期望 `Map<String,String>`,直接还原为新 map)。
4. `public static McpManager start(McpConfig cfg, String version)`：
   - 内部 `McpManager mgr = new McpManager();`
   - 对 `cfg.servers().entrySet()` 每个 `(name, srv)`,`Thread.startVirtualThread(() -> connectOne(mgr, name, srv, version, latch));`。
   - 用 `CountDownLatch latch = new CountDownLatch(cfg.servers().size());` 等齐。
   - `latch.await();` 后稳定排序 `mgr.tools`(`Comparator.comparing(Tool::name)`,因为 `fullName` 已带 `mcp__<server>__` 前缀)。
   - 返回 `mgr`。
5. `static void connectOne(McpManager mgr, String name, ServerConfig srv, String version, CountDownLatch latch)`：
   - `try { ... } finally { latch.countDown(); }`。
   - 按 `srv.type()` 构造 transport：
     - **stdio**：`StdioClientTransport transport = new StdioClientTransport(ServerParameters.builder(srv.command()).args(srv.args()).env(mergeOsEnv(srv.env())).build());`
     - **http**：`HttpClient hc = HttpClient.newBuilder().build();` `var transport = HttpClientStreamableHttpTransport.builder(srv.url()).httpClient(hc).customizeRequest(rb -> srv.headers().forEach(rb::header)).disableServerSentEvents(true).build();`
   - `McpAsyncClient client = McpClient.async(transport).clientInfo(new McpSchema.Implementation("gcode", version)).build();`
   - `client.initialize().block(Duration.ofSeconds(connectTimeoutSec));` 异常 → stderr 告警 `[mcp] warn: connect server <name> failed: <err>` + return。
   - `ListToolsResult lst = client.listTools().block(Duration.ofSeconds(connectTimeoutSec));` 异常 → stderr 告警 + `client.closeGracefully().block(Duration.ofSeconds(5));` + return。
   - 对每个 `t : lst.tools()` 调 `McpTool.adaptTool(name, t, new AsyncCallerSession(client))`；成功的入临时 `List<Tool>`。
   - `synchronized (mgr.lock) { mgr.sessions.add(new Session(name, client)); mgr.tools.addAll(adapted); }`。
6. `public List<Tool> tools()`：返回 `List.copyOf(this.tools)`(防外部修改)。
7. `@Override public void close()`：
   - 对每个 `session` 起 `Thread.startVirtualThread(() -> { try { session.client().closeGracefully().block(Duration.ofSeconds(2)); } catch (Exception ignored) {} done.countDown(); });`
   - `done.await(closeTimeoutSec, SECONDS);` 兜底；超时即 return 不等。
8. 把 30s 与 5s 实现成包级 `static volatile long connectTimeoutSec = 30L;` / `static volatile long closeTimeoutSec = 5L;`,便于单测 setup 中临时改小,结束 restore。

**验证：** `mvn test -Dtest=McpManagerTest` 覆盖：
- 空 `cfg` → `McpManager` 无 sessions、`tools()` 空、`close()` 立即返回；
- 失败隔离：构造一个 stdio server 指向不存在的 command + 一个用单测注入的 stub"server"(借助接口替身把 SDK 调用替换),断言 stub 工具被注册、失败 server 仅产生告警；
- 超时收尾：注入一个会卡住的连接 stub(让 `initialize().block(...)` 阻塞),把超时改为 200ms,断言超时窗口内被跳过；
- close 兜底：注入一个 closeGracefully 阻塞的 session,断言 `close()` 在(测试中改短的)兜底时间内返回；
- 并发安全：用 `mvn test`(JUnit 5)的多线程用例 + `@RepeatedTest(50)` 反复跑 10+ server 并发,无 `ConcurrentModificationException`、无丢工具。

## T5: Main 接线**文件：** `src/main/java/dev/gcode/Main.java`
**依赖：** T2、T3、T4
**步骤：**
1. import `dev.gcode.mcp.{ConfigLoader, McpConfig, McpManager};` 与 `dev.gcode.tool.Tool;`(若没有)。
2. 在 `ToolRegistry registry = ToolRegistry.defaults();` 行之后、`PermissionEngine engine = new PermissionEngine(root);` 之前插入：
   ```java
   McpConfig mcpCfg = ConfigLoader.loadConfig(root);
   McpManager mgr   = McpManager.start(mcpCfg, VERSION);
   Runtime.getRuntime().addShutdownHook(new Thread(mgr::close, "mcp-shutdown"));
   for (Tool t : mgr.tools()) {
       registry.register(t);
   }
   ```
3. `root` 复用现有 `Path.of("").toAbsolutePath()` 结果(已在 `Main` 中)；`VERSION` 复用 `public static final String VERSION` 常量。

**验证：** `mvn -q -DskipTests package`；无 MCP 配置时 `java -jar target/gcode-*.jar` 能正常进 TUI、内置 6 工具可用；配置一个 command 不存在的 stdio server 时进 TUI 不阻塞、stderr 显示连接失败告警。

## T6: 配置示例**文件：** `docs/ch07/mcp-servers.example.yaml`
**依赖：** 无(可与 T2 并行)
**步骤：**
1. 内容(用 YAML 注释说明放置位置与覆盖语义)：
   ```yaml
   # 项目级放 <root>/.gcode.yaml；用户级放 ~/.gcode/config.yaml。
   # 同名 server 项目级完整覆盖用户级。
   # env / headers 的值支持 ${VAR} 从宿主环境变量展开；command/args 不展开。
   mcp_servers:
     github:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-github"]
       env:
         GITHUB_TOKEN: "${GITHUB_TOKEN}"
     local-sqlite:
       type: stdio
       command: python
       args: ["-m", "mcp_server_sqlite", "--db", "./data.db"]
     example-http:
       type: http
       url: "https://mcp.example.com/mcp"
       headers:
         Authorization: "Bearer ${EXAMPLE_TOKEN}"
   ```

**验证：** 在 `ConfigLoaderTest` 增加一个用例,读取此示例文件断言三个 server 都被解析成功。

## T7: tmux 端到端实跑(CLAUDE.md 开发原则)**文件：** —
**依赖：** T1–T6
**步骤：**
1. 准备一个真实可用的 stdio MCP server。优先用 `npx -y @modelcontextprotocol/server-everything`(官方示例 server,自带 echo / add 等基础工具)；若无 npx,可临时用一个最小 Python/JS server。
2. 在项目根写一个临时 `.gcode.yaml` 指向它：
   ```yaml
   mcp_servers:
     demo:
       type: stdio
       command: npx
       args: ["-y", "@modelcontextprotocol/server-everything"]
   ```
3. `tmux` 起 gcode：
   - 启动日志(stderr)显示 server 连接成功 + 工具数；TUI 状态栏正常；
   - 让模型调用 `mcp__demo__echo` 一类工具：default 模式下弹人在回路 → 允许本次 → 工具结果回灌 → 模型续答；
   - 选"永久允许"后,本地权限规则被写入；重启 gcode 后再调同工具不再弹窗(验证永久规则与 ch07 命名空间联动)；
   - 切到 bypassPermissions：调用不弹窗；但让模型跑 `rm -rf /` 仍被内置黑名单拦下(MCP 工具不绕过黑名单的内置作用域)；
   - Esc 取消弹窗：干净回到 idle,不退出程序；
   - `q` 退出 gcode 后 `ps -ef | grep server-everything` 确认子进程已终止；
4. 配置一个 command 不存在的 server + 一个能跑的 server：启动 stderr 有失败告警,能跑的 server 工具仍可用。

**验证：** 上述全部观察通过；删除临时 `.gcode.yaml`,恢复项目根干净。

## T8: 全量编译测试与规范**文件：** —
**依赖：** T1–T7
**步骤：**
1. `mvn spotless:check`(google-java-format 应无差异；如有则 `mvn spotless:apply`)。
2. `mvn -q -DskipTests package`(应无错误、无未使用 import 告警)。
3. `mvn test`(覆盖 config、conversation、tool、agent、prompt、permission、tui、**mcp** 三组单测)。
4. 重点跑 `mvn test -Dtest='dev.gcode.mcp.*'` 多次(`-Dsurefire.rerunFailingTestsCount=3`),确认 virtual thread 并发无偶发失败。
5. `git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'`(应无命中：凭据不落盘)。
6. `git check-ignore -q docs/ch07/mcp-servers.example.yaml` 不需要忽略(示例只含 `${VAR}`)。

**验证：** 全部通过。

## 执行顺序

```
T1(SDK 依赖) ─┬─→ T2(config) ─┐
              │                ├─→ T4(manager) ─→ T5(Main 接线) ─→ T7(tmux 实跑) ─→ T8(规范)
              └─→ T3(tool)   ─┘
                                 └─→ T6(配置示例)(可与 T2 并行)
```
依赖：T2,T3 ← T1；T4 ← {T2,T3}；T5 ← {T2,T3,T4}；T6 独立于 T3、T4(可在 T2 完成后做)；T7 ← T1–T5；T8 ← 全部。
````

```markdown
# MCP 客户端 Checklist

> 每一项通过运行代码或观察行为来验证；类型 / 方法名仅作定位提示,核验断言本身不依赖其命名(重命名实现而行为不变时本清单仍适用)。

## 实现完整性
- [ ] 加载两层配置：两文件存在时按 server 名合并、同名 server 项目级完整覆盖用户级(验证：单测构造两层文件断言合并结果与字段来源)。(AC1/F1)
- [ ] 配置降级：任一文件缺失视为空、格式非法跳过该文件 + stderr 告警 + 其它正常加载,不致启动失败(验证：单测分别投喂缺失与非法 YAML,断言 `ConfigLoader.loadConfig` 不抛异常且其它层 server 仍在)。(AC1/N1)
- [ ] 字段校验：stdio 缺 command、http 缺 url、`type` 非法或缺失,均跳过该 server + stderr 给出原因,其它 server 不受影响(验证：单测分别构造各非法 server)。(AC2/N2)
- [ ] `${VAR}` 展开：env / headers 的值被展开；未定义变量展开为空串 + 一次性告警；command / args / 工具名 / server 名不展开(验证：单测覆盖各分支,含 `command: ${X}` 应保留字面量)。(AC3/F3)
- [ ] stdio 连接 + 握手 + 列工具：能拉起一个 MCP server 子进程并由 SDK 完成 initialize 握手 + listTools；`env` 被注入到子进程环境(验证：用单测脚本启动一个最小 echo MCP server 或 tmux 实跑 `@modelcontextprotocol/server-everything`)。(AC4/F4/F6)
- [ ] HTTP 连接 + 自定义 headers：能对 HTTP MCP server 完成握手 + 列工具；`headers` 真正出现在每个 HTTP 请求中(验证：用 JDK `HttpServer.create(...)` 起一个最小端点 + 注入 `Authorization` 头,断言 server 端收到该头)。(AC5/F5/F6/N6)
- [ ] 工具命名：所有 MCP 工具的 `name()` 形如 `mcp__<server>__<tool>`；前缀拼接后含 LLM 工具名禁用字符(非 `[A-Za-z0-9_-]`)的工具被跳过并告警(验证：单测构造含 `.` 的 server 名 / 工具名,断言 `McpTool.adaptTool` 返回 `Optional.empty()`)。(AC6/AC7/F8)
- [ ] 命名空间隔离：同一 tool 名在不同 server 互不覆盖；与 6 个内置工具天然不重名(验证：registry 注册后断言全名集合无重复)。(AC7/F8)
- [ ] 工具适配字段：description 空 → 兜底文案；schema 透传为 `Map<String, Object>`、空 schema 兜底 `Map.of("type","object")`；`annotations.readOnlyHint==true` → `readOnly()==true`,其它(含 null / false)→ `false`(验证：单测覆盖各分支,含 `annotations()==null` null-safe)。(AC6/F7)
- [ ] 调用结果聚合：`execute` 把远端多个 text content 块按顺序拼成 `content`；非 text 块(image / audio / resource_link / embedded_resource)静默丢弃 + 单 tool 限一次告警(验证：`McpToolTest` 注入 stub 返回混合内容块,断言 collected 仅含 text 且告警计数为 1)。(AC6/F7)
- [ ] 远端错误映射：远端 `isError==true` 时 `ToolResult.isError==true`,`content` 仍为远端 text(验证：`McpToolTest` 注入 stub 返回 `isError=true` + text 块)。(AC6/F7)
- [ ] 协议错与超时回灌：`callTool` 抛异常或 30s 超时 → `ToolResult.isError==true` 且 `content` 含可读错因,Agent Loop 不中断(验证：`McpToolTest` 注入 stub 抛异常 / `Thread.sleep` 至超时,断言 isError 与文案)。(AC9/F7/F10/N5)
- [ ] 启动失败隔离：有 server 连接 / 握手 / 列工具失败时,只跳过它自身,其它 server 与内置工具集照常注册可用(验证：`McpManagerTest` 用一个失败 server + 一个 stub 成功 server,断言成功 server 工具被注册)。(AC8/F9/N1)
- [ ] 30s 启动超时：模拟连接卡住的 server 在(测试中缩短的)超时窗口结束后被跳过,启动不阻塞超过该窗口(验证：`McpManagerTest` 注入连接 stub 阻塞 + 短超时配置,断言 `McpManager.start` 在超时窗口附近返回)。(AC8/F9/N1)
- [ ] 退出干净：`McpManager.close()` 终止所有 stdio 子进程、断开 HTTP 会话；某 session 关闭卡住时 5s 兜底返回不阻塞(验证：`McpManagerTest` 注入卡住的 close stub + 短兜底,断言 `close()` 在兜底时间内返回；tmux 实跑 `q` 退出后 `ps` 无残留子进程)。(AC10/F11/N7)

## 集成
- [ ] 权限链路自然命中：无规则时 `readOnlyHint=true` 的 MCP 工具走 Read 兜底(default 直接放行)、其余走 Exec 兜底(default Ask)；allow 规则 `mcp__<server>__*` 命中时直接放行；bypass 模式放行(验证：用 `new PermissionEngine(root)` 对 mcp 全名调用断言裁决；tmux 实跑见场景 4)。(AC11/F12/N4)
- [ ] permission 包零改动：`git diff src/main/java/dev/gcode/permission/` 在 ch07 期间无任何修改(验证：本章结束时核对 diff 范围)。(N4)
- [ ] provider 适配层零改动：`src/main/java/dev/gcode/llm/AnthropicProvider.java`、`src/main/java/dev/gcode/llm/OpenAIProvider.java` 无修改(验证：核对 diff)。(AC12/N3)
- [ ] 黑名单 / 沙箱对 MCP 工具自动跳过：MCP 工具调用 `extractTarget` 返回 `("", false, false)` → 黑名单层因 `target.isEmpty()` 不命中、沙箱层因 `isFile==false` 不进入(验证：用 permission 的 `check` 对一次 mcp 全名调用断言不被黑名单/沙箱直接 Deny)。(AC11/F12)
- [ ] ch01–ch06 不退化：`mvn test` 全过,既有用例不需要适配(验证：运行测试套件)。(AC13/N5)

## 编译与测试
- [ ] `mvn -q -DskipTests package` 无错误(fat jar 可启动)。
- [ ] `mvn spotless:check` 无差异(google-java-format)。(AC15/N8)
- [ ] `mvn test` 通过(config、conversation、tool、agent、prompt、permission、tui、**mcp** 三组单测)。
- [ ] `mvn test -Dtest='dev.gcode.mcp.*' -Dsurefire.rerunFailingTestsCount=3` 反复跑 3 轮无偶发失败(重点守护 `McpManager` 并发连接、共享状态、`close` 兜底)。(N7/N8)
- [ ] 凭据不落盘：配置示例 / 文档 / 测试 fixture 全用 `${VAR}`；`git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'` 在 ch07 期间无命中。(AC14/N6)

## 端到端场景(tmux 实跑)
- [ ] 场景 1(无 MCP 配置)：仓库内不存在 `.gcode.yaml` 与 `~/.gcode/config.yaml` 时,gcode 正常进 TUI；registry 仅含 6 个内置工具；stderr 无 mcp 相关告警。(AC1)
- [ ] 场景 2(stdio server 接入)：在 `.gcode.yaml` 配置 `@modelcontextprotocol/server-everything` 一类真实 server,启动后日志显示 server 连接成功 + 工具数；TUI 中让模型调用其中一个工具(如 echo),default 模式弹人在回路 → 「允许本次」→ 工具结果回灌 → 模型续答。(AC4/AC6/AC11)
- [ ] 场景 3(失败隔离)：配置一个不存在 command 的 server + 一个能跑的 server,启动 stderr 有第一个 server 的失败告警；能跑的 server 工具仍可用、能正常调用。(AC8)
- [ ] 场景 4(永久放行 + 重启)：场景 2 中选「永久允许」→ `.gcode/settings.local.yaml` 出现对应 `mcp__<server>__<tool>` allow 规则；重启 gcode 后再调该工具不再弹窗直接执行。(AC11)
- [ ] 场景 5(凭据展开)：配置 `env: { GITHUB_TOKEN: "${GITHUB_TOKEN}" }`；`unset GITHUB_TOKEN` 启动时 stderr 有 undefined 告警但 server 仍尝试启动(server 自决报错与否)；`export GITHUB_TOKEN=...` 后正常工作。(AC3/AC14)
- [ ] 场景 6(退出干净)：`q` 退出 gcode 后 `ps -ef | grep server-everything`(或对应 server 进程名)确认子进程无残留。(AC10)
- [ ] 场景 7(bypass + 黑名单兜底)：Shift+Tab 切到 bypassPermissions,MCP 工具调用不弹窗；让模型跑内置 `bash` 工具 `rm -rf /` 仍被黑名单拦下、回灌被拒。(AC11/N4)
- [ ] 场景 8(HTTP server,可选)：用 JDK `HttpServer.create(...)` 起一个最小 HTTP MCP server 或对接现有 server,配置 http 类型 + `headers: { Authorization: "Bearer ${TOKEN}" }`；启动后工具被注册；调用时 server 端日志可见 Authorization 头。(AC5)
```

### TypeScript

```markdown
# MCP 客户端 Spec## 背景

ch01–ch06 已经把 gcode 砌成了一个能自主多轮干活、有完整权限护栏的 TUI Coding Agent。但内置工具集是写死的（读 / 写 / 改文件、命令执行、按模式找文件、搜内容、规划、子代理……）——想让它会用 GitHub、查数据库、连内部服务，只能改源码、重新打包，能力边界锁死在打包期。

MCP（Model Context Protocol）是一套开放标准，用统一协议把"提供工具的一方（server）"与"使用工具的一方（client）"解耦，社区已有大量现成 server（GitHub、Slack、SQLite、文件系统……）。ch07 给 gcode 装上 **MCP 客户端**：启动时按配置自动发现并连接外部 server，把它们的工具包装成 gcode 已有的工具抽象、注册进工具中心，Agent 调用时与内置工具**完全无感**，并自动复用 ch06 的权限护栏。这是从"工具集固定"到"工具生态可插拔"的一跃——给 gcode 装上扩展坞。

## 目标- **配置驱动的自动发现**：启动时从配置声明的 server 列表自动连接、列出工具、注册进工具中心，无需改源码。
- **三种传输方式**：本地 server 走子进程标准输入输出管道；远程 server 默认走流式 HTTP；显式声明时可走服务器推送式长连接。
- **标准三步会话**：每个 server 一次连接经过 初始化握手 → 列出工具 → 按需调用工具，整个协议层由官方协议库承载，不自研协议栈。
- **无感适配**：发现到的远端工具包装成与内置工具一致的抽象，Agent 编排层与协议适配层均无需感知其来自远端。
- **命名空间隔离**：远端工具统一加 `mcp__<server>__<tool>` 前缀，server / tool 名中不合法字符替换为 `_`，杜绝与内置工具及多 server 间的重名冲突，并保留来源可追溯。
- **延迟加载**：MCP 工具默认不进入系统提示词，避免远端 schema 把上下文撑爆；模型通过专用检索工具按关键词或精确名找到并"激活"目标工具后再调用。
- **三层配置合并**：server 列表从用户级、项目级、本地覆盖三层来源读取并合并，后层同名 server 完整覆盖前层。
- **凭据不落盘**：配置中环境变量与请求头的值支持从宿主环境变量展开，密钥不写进配置文件。
- **server 使用说明注入**：连接成功后把 server 在握手阶段提供的使用说明作为系统提醒注入会话历史，让模型知道该 server 的工具使用约定。
- **失败隔离**：单个 server 连接 / 列工具 / 调用失败只跳过它自身、不影响其它 server、不阻断启动，错误以系统消息展示给用户。
- **状态可观察**：提供专门指令查看已连接 server 与工具总数，并在整体状态指令中展示 MCP 概览。
- **复用权限**：MCP 工具天然走 ch06 的判定链路，默认按命令执行类每次确认；权限组件**零改动**。
- **不破坏既有能力**：会话、流式、内置工具、权限、规划、子代理等行为不退化。

## 功能需求- **F1: 三层配置合并**
  在用户未显式指定配置路径时，依次从**用户级**、**项目级**、**本地覆盖**三层配置文件读取并合并 server 列表；不存在的层自动跳过；按 server 名去重，后层同名 server 完整覆盖前层对象（不做字段级合并，避免半合并出畸形 server），新增 server 追加到末尾。任一层配置文件存在但解析失败时，按整个配置加载失败处理并以非零退出码退出进程（不与 MCP 行为耦合，体现"配置坏即整个进程退"）。

- **F2: server 类型与必填字段**
  每个 server 定义至少携带一个名字，以及二选一的连接方式标识：
  - 声明本地命令的 server 必填命令本体，可选启动参数、可选环境变量；
  - 声明远程地址的 server 必填地址，可选自定义请求头，可选明确指定的传输方式标识。
  连接方式两项均缺失时，连接阶段抛错并落入失败结果集，不影响其它 server。

- **F3: 环境变量展开**
  环境变量与请求头的**值**支持引用宿主环境变量；展开在连接阶段进行，不污染原始配置文件。未定义变量展开为空串、不告警、不阻断（让 server 自行决定无凭据时如何处理）。命令、参数、server 名、工具名**不做展开**（避免命令/名字被环境间接影响产生隐性歧义）。

- **F4: 本地子进程传输**
  对声明本地命令的 server，启动子进程，通过子进程的标准输入输出与之通信；配置中的环境变量与宿主进程环境合并后注入子进程（同名宿主变量被配置覆盖，便于按 server 注入凭据）；子进程的标准错误流不输出到 TUI 的错误通道，避免污染界面。子进程生命周期随宿主进程退出而结束。

- **F5: 远程传输**
  对声明远程地址的 server：
  - 默认采用**流式 HTTP**传输；
  - 显式指定走服务器推送式长连接时采用**长连接传输**。
  自定义请求头注入每次 HTTP 请求（用于鉴权头等）；地址在连接前先做格式校验，非法地址早期失败。

- **F6: 标准三步会话**
  每个 server 建立后依次完成 **初始化握手**（交换协议版本与能力清单）→ **列出工具** → 进入按需 **调用工具**阶段。整个协议层（消息编解码、请求/响应配对、握手细节、传输细节）由官方协议库承载，不自研协议栈。本章只覆盖工具能力，**不订阅 / 不实现** MCP 的资源、提示词、采样、引导等其它能力。

- **F7: 工具适配（远端工具 ↔ gcode 工具抽象）**
  把 server 返回的每个远端工具包装成一个统一工具对象，注册进工具中心：
  - **名字**：`mcp__<server>__<tool>`（见 F8）。
  - **描述**：透传远端描述（远端为空则原样保留为空，由远端自行兜底）。
  - **分类**：固定按"命令执行类"处理（保守默认按有副作用对待）。
  - **延迟加载标记**：固定开启，默认不进系统提示词（见 F9）。
  - **参数 schema**：透传远端原始 schema，不做二次裁剪。
  - **执行**：调用时通过该 server 的会话发起工具调用；远端返回内容按顺序拼接——文本块取其文本，其它块序列化为 JSON 文本，块间换行分隔；调用过程中任何异常被捕获并转成"出错"的结构化结果回灌给模型，不抛异常给 Agent Loop（复用既有"不中断会话"的契约）。Agent 与协议适配层不感知"该工具来自远端"。

- **F8: 工具命名空间**
  所有 MCP 工具统一以 `mcp__<server>__<tool>` 命名；server 与 tool 名中不属于字母数字、下划线、连字符的字符在拼接前被替换为下划线。命名空间用途三重：
  - **避免冲突**：同名远端工具在不同 server 互不干扰；与内置工具天然不重名；
  - **可追溯**：单看工具名能识别来源 server，便于日志、人在回路提示、权限规则书写；
  - **权限规则书写**：用户可针对完整工具名做精确放行或拒绝。
  注册阶段同名后注册者覆盖前者（由调用方负责 server 名唯一性）。

- **F9: 延迟加载与按需检索**
  - **默认不入提示词**：MCP 工具被注册后，工具中心在返回给模型的工具清单中默认跳过它们，避免远端 schema 把上下文撑爆；同时把未激活的 MCP 工具名列表通过系统提示告知模型可通过检索激活。
  - **检索工具**：系统提供一个只读的内置检索工具：
    - 输入查询关键词与可选返回上限；
    - 当查询以"精确选择"前缀开头并附带工具名时，按名拿到对应工具并标记为已激活，把每个工具的 schema 序列化后返回，使下一轮系统提示词带上这些工具；
    - 否则在所有未激活的 MCP 工具的名字与描述上做关键词检索，返回名称与简短描述列表（仅展示，不激活）。
  - **激活后持续可见**：一旦某个 MCP 工具被标记为已激活，本次会话内后续轮次的工具清单持续包含它，直到会话结束。

- **F10: server 使用说明注入**
  连接成功后，从 server 在握手阶段返回的使用说明文本中提取非空内容；管理器把每条说明连同 server 名一起回传给上层，上层将其作为系统提醒注入会话历史，让模型在后续轮次中能看到该 server 关于工具使用约定的提示。

- **F11: 失败隔离与错误展示**
  对每个 server 顺序尝试连接 + 列工具；任一步骤抛错均落入失败结果集并继续下一个 server。连接发生在进入会话视图之后异步进行，连接失败不阻断进入会话；管理器把失败原因汇总返回，上层以一条系统消息展示给用户，标明哪些 server 失败以及原因。

- **F12: 状态查询指令**
  - 专用 MCP 查询指令：无 server 时回"未连接任何 MCP server"；否则列出已连接 server 名及工具总数；
  - 总体状态指令：包含一行 MCP 概览，显示连接的 server 数量与工具总数。

- **F13: 协议无关**
  工具中心在向模型暴露工具清单时按当前对话所用协议自动适配格式（不同协议的工具描述结构不同）；MCP 工具走的是同一份抽象，无需在协议适配层做任何感知，行为在不同协议下保持一致。

- **F14: 权限链路自然命中**
  MCP 工具走 ch06 现有判定链路：
  - 命令黑名单仅作用于内置命令执行工具，对 MCP 工具不命中；
  - 文件沙箱仅作用于内置文件类工具，对 MCP 工具不适用；
  - 规则引擎按完整工具名 `mcp__<server>__<tool>` 匹配；用户可用精确名或带通配的形式书写放行/拒绝规则；
  - 模式兜底：MCP 工具按"命令执行类"处理，默认与编辑模式下每次触发人在回路确认；旁路模式下放行。
  权限组件源码**零修改**，仅通过既有公共行为承载。

## 非功能需求

- N1: 失败隔离不阻塞——单 server 任意阶段（连接 / 列工具 / 调用）失败只跳过它自身、不阻塞会话启动、不影响其它 server 与内置工具；错误以系统消息提示用户。
- N2: 凭据不落盘——所有配置示例与文档均用环境变量引用密钥；敏感值在配置文件与日志中不以明文形式出现。
- N3: 默认保守——MCP 工具按"命令执行类"对待，权限链路默认按有副作用处理（除非显式规则放行）；延迟加载默认不进提示词，避免远端工具污染上下文。
- N4: 协议无关——同一 MCP server 在不同对话协议下行为一致；协议适配层零修改。
- N5: 不破坏 ch01–ch06——会话、流式、内置工具、权限、规划、子代理、teams、hooks、skills 等行为不退化。
- N6: 代码规范——类型检查与单元测试全过，不引入运行时错误。

## 不做的事- **MCP 资源、提示词、采样、引导**——本章只覆盖工具能力。
- **工具列表变更通知 / 调用进度通知 / 完整 OAuth 鉴权流程**——保持最小可用面。
- **健康检查 / 自动重连 / 退避策略 / 单 server 启动超时包装**——server 卡住由协议库自身的承诺机制兜底；本章不主动给每 server 加超时。
- **配置热加载 / 运行时增减 server**——重启 gcode 才能应用新配置。
- **未定义环境变量告警**——展开为空串静默放行，由 server 自行决定无凭据时是否报错。
- **非文本内容块的转写降级**——非文本块直接序列化为 JSON 文本，让模型自行决定如何理解；不做特殊裁剪。
- **MCP 工具的命令黑名单与路径沙箱扩展**——这两层只对内置工具有意义，MCP 工具仅走规则 + 模式兜底 + 人在回路。
- **MCP server 端的实现**——gcode 仅作 client。

## 验收标准

- AC1: 三层配置合并——用户级、项目级、本地覆盖三层配置都存在时，按 server 名合并；同名 server 后层完整覆盖前层；任一文件缺失时被自动跳过。（F1）
- AC2: 三种传输——声明本地命令的 server 走子进程传输；声明远程地址的 server 默认走流式 HTTP；显式指定推送式长连接时走对应传输；三种 server 各起一个均能完成握手并列出工具。（F2/F4/F5）
- AC3: 环境变量展开——环境变量与请求头中引用宿主变量在连接阶段被注入；未定义变量展开为空串、不告警；命令、参数、名字不展开。（F3/N2）
- AC4: 工具命名与字符净化——server 名或工具名含不合法字符时，注册到工具中心的最终名字中这些字符被替换为下划线，整体形如 `mcp__<server>__<tool>`。（F7/F8）
- AC5: schema 透传——远端工具的参数 schema 原样进入注册后的工具描述；面向模型暴露工具清单时按当前协议自动适配外层结构。（F7/F13）
- AC6: 延迟加载默认不进提示词——MCP 工具注册后，立即获取工具清单时不包含它；标记为已激活后，下一次获取工具清单时包含它。（F9）
- AC7: 检索工具行为——以关键词检索时返回匹配的 MCP 工具名与简短描述（不激活）；以"精确选择"前缀附工具名时返回该工具的 schema 并把它标记为已激活。（F9）
- AC8: 调用结果聚合——远端返回内容数组按顺序拼接：文本块取文本，其它块序列化为 JSON 文本，块间换行分隔；调用抛错转为"出错"的结构化结果回灌给模型。（F7）
- AC9: 失败隔离——配置中一个无效 server 与一个可用 server 同时存在时，进入会话后失败结果集含失败 server、工具集含可用 server 的工具；TUI 用一条系统消息提示用户。（F11/N1）
- AC10: server 使用说明注入——server 在握手阶段提供非空使用说明时，会话历史中可看到一条形如"# MCP Server: <name>\n<text>"的系统提醒。（F10）
- AC11: 状态查询指令——专用 MCP 指令输出 server 列表与工具总数；总体状态指令包含 MCP server 数与工具数一行。（F12）
- AC12: 协议无感——切换到另一种对话协议后，MCP 工具的描述仍正确按该协议结构出现在工具清单中，模型可调用并拿到结果。（F13/N4）
- AC13: 权限链路自然命中——针对 `mcp__<server>__*` 形式的放行 / 拒绝规则正确作用到对应 MCP 工具；未写规则时所有 MCP 工具按命令执行类触发人在回路确认；旁路模式下放行（命令黑名单 / 文件沙箱对 MCP 工具不命中，自动跳过）。（F14）
- AC14: 不破坏 ch01–ch06——既有测试全过；既有用例不需要适配；多轮会话、流式、规划、子代理、teams、hooks、skills 等行为不退化。（N5）
- AC15: 凭据不落盘——配置示例与文档全用环境变量引用密钥；配置文件中无明文凭据命中。（N2）
- AC16: 代码规范——类型检查通过；单元测试通过；无 MCP 配置时正常进入会话。（N6）
```

````markdown
# MCP 客户端 Plan> 技术栈：bun + TypeScript 5.x；MCP 协议层使用官方 SDK `@modelcontextprotocol/sdk`（含 `Client`、`StdioClientTransport`、`StreamableHTTPClientTransport`、`SSEClientTransport`）；TUI 基于 Ink；yaml 解析用 `js-yaml`。本章新增 `src/mcp/` 三个文件 + `src/tools/tool-search.ts`，并在 `src/config/config.ts`、`src/tools/registry.ts`、`src/tui/app.tsx` 上接线，**不改** llm 协议适配层、agent 执行循环、permission 引擎本体。

## 技术栈

- 运行时：bun（`bun run src/main.tsx`、`bun test`）。
- 语言：TypeScript 5.x（`"type": "module"`，全部使用 ESM）。
- TUI：Ink（React 渲染到终端）、`ink-spinner`、`ink-text-input`。
- MCP SDK：`@modelcontextprotocol/sdk ^1.29.0`（`client/index.js`、`client/stdio.js`、`client/streamableHttp.js`、`client/sse.js` 四个子模块）。
- LLM SDK：`@anthropic-ai/sdk`、`openai`（不感知 MCP）。
- YAML：`js-yaml`（用 `yaml.load` 解析）。
- 类型检查：`tsc --noEmit`。
- 测试：`bun test`。

## 架构概览

分层（自下而上）：

- **传输层（SDK 内置，零自研）**：`StdioClientTransport` / `StreamableHTTPClientTransport` / `SSEClientTransport` 直接吃 server 配置。
- **会话层（`src/mcp/client.ts`）**：`MCPClient` 是单个 server 的"连接 + 三步会话"门面，持有一个 `Client` 与 `AnyTransport` 实例，对外暴露 `connect()` / `listTools()` / `callTool()` / `getInstructions()` / `disconnect()`。
- **管理层（`src/mcp/manager.ts`）**：`MCPManager` 持有 `Map<string, MCPClient>`，提供 `connectAll(configs)` 串行尝试连接所有 server 并收集 `{ tools, servers, errors, instructions }` 四个数组，提供 `getClient(name)` 让 wrapper 持有具体 client。
- **工具包装层（`src/mcp/tool-wrapper.ts`）**：`MCPToolWrapper implements Tool`，把单个 `MCPTool` 包成 deferred 工具，注册进 `ToolRegistry`。
- **注册表与延迟加载（`src/tools/registry.ts` + `src/tools/tool-search.ts`）**：`ToolRegistry.getAllSchemas` 在 `tool.deferred && !discovered` 时跳过；`ToolSearchTool` 提供 `select:` 与关键词检索两种激活方式。
- **接线层（`src/tui/app.tsx`）**：在 `initClient` 内部 `useEffect` 里 fire-and-forget 调 `MCPManager.connectAll`，回调中注册 wrapper、注入 instructions、推 `system` 消息、更新 `mcpInfo`。

数据流（启动 + 单次调用）：

```
启动：
loadConfig() ──→ AppConfig.mcp_servers
                       │
                       ▼
              <App mcpServers={...}>
                       │
                useEffect → initClient
                       │
                       ▼
            new MCPManager().connectAll(cfgs)
                       │
        ┌──────────────┴──────────────────────┐
        │              │              │       │
   stdio server   http server    sse server  失败
        │              │              │       │
   client.connect (SDK initialize) → result.servers/tools/instructions/errors
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
 registry.register                 setMessages([{role:'system'},...])
 (MCPToolWrapper, deferred=true)   setMcpInfo({servers,toolCount})
                                  convRef.addSystemReminder(<MCP Server: name>)

单次调用：
模型 → ToolSearch(query="github") → registry.searchDeferred → list
模型 → ToolSearch(query="select:mcp__github__create_issue") → registry.markDiscovered + 返回 schema JSON
模型 → tools[mcp__github__create_issue] 出现在下一轮 getAllSchemas → 模型发起 tool_use
Agent.executeTools → registry.get(name).execute(args, ctx)
   └ MCPToolWrapper.execute → MCPClient.callTool → SDK tools/call
                              ↓
        result.content[] → text 取 .text，其余 JSON.stringify，\n 拼接
                              ↓
        { output, isError } → 回灌 conversation
```

## 核心数据结构与接口### `MCPServerConfig`（`src/config/config.ts`）

```ts
export interface MCPServerConfig {
  name: string;
  command?: string;              // stdio：必填
  args?: string[];               // stdio：可选
  url?: string;                  // http / sse：必填
  transport?: string;            // "sse" 选 SSE，其余/缺省走 Streamable HTTP
  headers?: Record<string, string>; // 值支持 ${VAR} / $VAR
  env?: Record<string, string>;     // 值支持 ${VAR} / $VAR
}
```

### `AppConfig.mcp_servers`（`src/config/config.ts`）

```ts
export interface AppConfig {
  providers: ProviderConfig[];
  permission_mode?: string;
  mcp_servers: MCPServerConfig[]; // 三层 yaml 合并后的最终数组
  hooks: HookConfig[];
}
```

合并语义在 `mergeConfig(base, override)` 中实现：`override.mcp_servers` 非空时按 `name` 字段做"同名覆盖、新名追加"。

### `MCPTool`（`src/mcp/client.ts`）

```ts
export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}
```

### `AnyTransport`（`src/mcp/client.ts`）

```ts
type AnyTransport =
  | StdioClientTransport
  | StreamableHTTPClientTransport
  | SSEClientTransport;
```

### `MCPClient`（`src/mcp/client.ts`）

```ts
export class MCPClient {
  name: string;
  constructor(config: MCPServerConfig);
  connect(): Promise<void>;
  getInstructions(): string;
  listTools(): Promise<MCPTool[]>;
  callTool(name: string, args: Record<string, unknown>): Promise<string>;
  disconnect(): Promise<void>;
}
```

### `ConnectResult` 与 `MCPManager`（`src/mcp/manager.ts`）

```ts
export interface ConnectResult {
  tools: { serverName: string; tool: MCPTool }[];
  servers: string[];
  errors: { serverName: string; error: string }[];
  instructions: { serverName: string; text: string }[];
}

export class MCPManager {
  connectAll(configs: MCPServerConfig[]): Promise<ConnectResult>;
  getClient(name: string): MCPClient | undefined;
  disconnectAll(): Promise<void>;
}
```

### `MCPToolWrapper`（`src/mcp/tool-wrapper.ts`）

```ts
export class MCPToolWrapper implements Tool {
  name: string;
  description: string;
  category: "command";
  deferred: true;

  constructor(client: MCPClient, serverName: string, tool: MCPTool);
  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}
```

### `ToolRegistry`（`src/tools/registry.ts`，本章扩展点）

```ts
export class ToolRegistry {
  register(tool: Tool): void;
  get(name: string): Tool | undefined;
  listTools(): Tool[];

  // 关键：deferred + !discovered 时跳过
  getAllSchemas(protocol: "anthropic" | "openai" | "openai-compat"): Record<string, unknown>[];

  // 本章新增能力
  getDeferredToolNames(): string[];
  getDeferredTools(): Tool[];
  searchDeferred(query: string, maxResults?: number): Tool[];
  findDeferredByNames(names: string[]): Tool[];
  markDiscovered(name: string): void;
  isDiscovered(name: string): boolean;
}
```

### `ToolSearchTool`（`src/tools/tool-search.ts`）

```ts
export class ToolSearchTool implements Tool {
  name = "ToolSearch";
  description = "Search for and load deferred tools by name or keyword.";
  category = "read" as const;
  system = true;
  constructor(registry: ToolRegistry);
  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}
```

## 模块设计### `src/mcp/client.ts`**职责：** 单个 server 的连接 + 三步会话门面。

**关键点：**
- `expandEnv(value)` 用正则 `/\$\{(\w+)\}|\$(\w+)/g` 同时支持 `${VAR}` 与 `$VAR`，未定义变量替换为空串。
- `connect()` 内按 `config.command` / `config.url` 二选一构造 transport：
  - **stdio**：浅合并 `process.env` 与 `config.env`（`env` 后覆盖），构造 `StdioClientTransport({ command, args, env, stderr: "ignore" })`；
  - **http / sse**：先 `new URL(config.url)` 校验；`opts = { requestInit: { headers } }`；`config.transport === "sse"` → `SSEClientTransport(url, opts)`，否则 → `StreamableHTTPClientTransport(url, opts)`；
  - 两者全无 → 抛 `Error("MCP server '<name>': needs either 'command' (stdio) or 'url' (http/sse)")`。
- `new Client({ name: "gcode", version: "0.1.0" }, {})` 后 `await this.client.connect(this.transport)`（SDK 内部完成 initialize 握手 + 能力协商）。
- `getInstructions()` 直接读 SDK `Client.getInstructions()`，无则返回 `""`。
- `listTools()` 调 `Client.listTools()`，把 `result.tools` 映射为 `MCPTool[]`。
- `callTool(name, args)` 调 `Client.callTool({ name, arguments: args })`，对返回 `content` 数组用 `map → join("\n")`，`type === "text"` 取 `.text ?? ""`，其它块 `JSON.stringify(c)`；返回拼接好的字符串。无 `content` 时退化为 `JSON.stringify(result)`。
- `disconnect()` 调 `this.client?.close()`，吞掉任何异常；置空 `client` / `transport`。

### `src/mcp/manager.ts`**职责：** 串行连接所有 server、缓存 `MCPClient`、收集 `ConnectResult`。

**关键点：**
- `connectAll(configs)` 用 `for...of` 串行（不是 `Promise.all`）遍历 configs。串行的代价是总时延等于各 server 之和；好处是与 ink 的 `useEffect` async then 链路简单，错误隔离单点清晰。
- 每个 server `try { client.connect(); clients.set(name, client); servers.push(name); listTools() → tools.push({serverName, tool}); instructions = client.getInstructions(); 非空 → instructions.push } catch (err) { errors.push({serverName, error: err.message}) }`。
- 注意：`getInstructions()` 在 `connect()` 之后调用（initialize 已完成），返回为空串时不入 `result.instructions`。
- `getClient(name)` 直接 `this.clients.get(name)`，给 `MCPToolWrapper` 拿。
- `disconnectAll()` 对每个 client `await disconnect()`，清空 map。当前未在 App 退出时主动调用——子进程随 Node 退出自然终止；HTTP 会话由 SDK 自身的清理负责。

### `src/mcp/tool-wrapper.ts`**职责：** 把 `MCPTool` 包成 `Tool`，让 registry / agent / provider 适配层无感。

**关键点：**
- `sanitizeName(serverName, toolName)`：`(s) => s.replace(/[^a-zA-Z0-9_-]/g, "_")`，对两段分别清洗，最终拼成 `mcp__<a>__<b>`。
- 字段：`name`（清洗后）、`description`（远端 `description`）、`category: "command"`、`deferred: true`。
- 私有 `originalName` 保留远端原始 tool 名，`callTool` 时用它而非清洗后的 `name`。
- `schema()`：返回 `{ name, description, input_schema: this.inputSchema }`。在 `getAllSchemas("anthropic")` 下直接透传；在 `getAllSchemas("openai" | "openai-compat")` 下被 registry 包成 `{ type: "function", function: { name, description, parameters: input_schema } }`。
- `execute(args, _ctx)`：`try { output = await this.client.callTool(this.originalName, args); return { output, isError: false } } catch (err) { return { output: "MCP tool error: " + err.message, isError: true } }`。

### `src/tools/tool-search.ts`**职责：** 让模型按名或关键词把 deferred 工具激活进 prompt。

**关键点：**
- `schema()`：`input_schema` 含 `query: string`（必填）与 `max_results: integer`（默认 5）。
- `execute()`：
  - 空 `query` → `{ output: "Error: query is required", isError: true }`；
  - `"select:..."` 前缀 → `slice(7).split(",").map(trim)` → `registry.findDeferredByNames(names)` → 逐个 `registry.markDiscovered(name)` → 把每个 tool 的 `schema()` 用 `JSON.stringify(_, null, 2)` 序列化，块间 `\n\n` 拼接返回；无命中时返回提示文本（不报错）；
  - 否则关键词检索 `registry.searchDeferred(query, maxResults)`，返回 `- <name>: <description.slice(0,100)>` 多行。

### `src/tools/registry.ts`（本章扩展点）**职责：** 内置工具与 MCP 工具统一注册；按 `deferred` 决定是否进 prompt；提供 `ToolSearch` 所需的检索 API。

**关键点：**
- `tools: Map<string, Tool>`、`discovered: Set<string>`；
- `getAllSchemas(protocol)`：迭代 `tools.values()`，若 `tool.deferred && !discovered.has(tool.name)` 则 `continue`，跳过 deferred 未激活工具；其余按 protocol 分支返回原始或 OpenAI function 形式；
- `searchDeferred(query, maxResults=5)`：lowercase 子串匹配 `name` 与 `description`，最多 `maxResults` 条；
- `findDeferredByNames(names)`：精确 `Map.get`，过滤 `deferred === true`；
- `markDiscovered(name)` / `isDiscovered(name)`：维护 set。

### `src/config/config.ts`（本章扩展点）**职责：** 支持 `mcp_servers` 字段的三层 yaml 合并。

**关键点：**
- `loadSingleFile(path)` 把 `raw.mcp_servers` 直接当作 `MCPServerConfig[]` 取出（如缺失为 `[]`）。
- `mergeConfig(base, override)`：当 `override.mcp_servers.length > 0` 时，用 `byName: Map<string, number>` 把 base 现有 server 索引化；遍历 override：同名 → 整对象覆盖；新名 → 追加。
- `loadConfig()` 在缺省路径下按 `~/.gcode/config.yaml` → `<cwd>/.gcode/config.yaml` → `<cwd>/.gcode/config.local.yaml` 三层尝试，`existsSync` 跳过缺失层，依次 `mergeConfig` 累积。

### `src/tui/app.tsx`（本章接线）**职责：** 在 chat 启动时异步连 MCP、注册 wrapper、注入 instructions、推 system 消息。

**关键点：**
- `Props.mcpServers: MCPServerConfig[]`；
- `mcpManagerRef: useRef<MCPManager | null>(null)`；
- `mcpInfo: useState<{servers, toolCount} | null>(null)`；
- 在 `initClient` 内部，连完 LLM client 后若 `mcpServers.length > 0`：
  ```ts
  const mgr = new MCPManager();
  mcpManagerRef.current = mgr;
  mgr.connectAll(mcpServers).then((result) => {
    for (const { serverName, tool } of result.tools) {
      const client = mgr.getClient(serverName);
      if (client) {
        registryRef.current.register(new MCPToolWrapper(client, serverName, tool));
      }
    }
    if (result.errors.length > 0) setMessages(prev => [...prev, { role: "system", content: "MCP errors: ..." }]);
    if (result.servers.length > 0) setMcpInfo({ servers, toolCount: result.tools.length });
    for (const { serverName, text } of result.instructions) {
      convRef.current.addSystemReminder(`# MCP Server: ${serverName}\n${text}`);
    }
  });
  ```
- `/mcp` 命令：读 `mcpInfo` 渲染状态行；
- `/status` 命令：含 `MCP: ${mcpInfo?.servers.length ?? 0} server(s), ${mcpInfo?.toolCount ?? 0} tool(s)`。

## 模块交互

```
main.tsx
  └─ loadConfig() ──→ AppConfig{ providers, mcp_servers, hooks }
                                 │
                                 ▼
                        <App mcpServers={...}>
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
        createToolRegistry()           useEffect: initClient
          (内置 6+ Tool)                          │
                  │                              ▼
                  │             new MCPManager().connectAll(cfgs)
                  │                              │
                  │                  for cfg of cfgs (串行)
                  │                   ├─ new MCPClient(cfg)
                  │                   ├─ client.connect()  ─ SDK initialize
                  │                   ├─ client.listTools() ─ tools/list
                  │                   └─ client.getInstructions()
                  ▼                              │
        registryRef.current ◄──── register(MCPToolWrapper)
                  │                              │
                  ▼                              ▼
   getAllSchemas(protocol)              setMcpInfo / setMessages
   (deferred 且未激活 → 跳过)             convRef.addSystemReminder
                  │
                  ▼
            LLMClient.tools[]
                  │
   ┌──────────────┴──────────────┐
   ▼                             ▼
  Agent.loop 中模型用       Agent.loop 中模型用具体
  ToolSearch 检索/激活      mcp__server__tool 调用
                                 │
                                 ▼
                       MCPToolWrapper.execute
                            │
                            ▼
                    MCPClient.callTool ─ tools/call
                            │
                            ▼
                       text content 拼接 / 异常包装
                            │
                            ▼
                    { output, isError } 回灌 conversation
```

依赖方向（无环）：

- `main.tsx` → `config/config.ts`、`tui/app.tsx`；
- `tui/app.tsx` → `mcp/manager.ts`、`mcp/tool-wrapper.ts`、`tools/registry.ts`、`tools/tool-search.ts`；
- `mcp/manager.ts` → `mcp/client.ts`；
- `mcp/tool-wrapper.ts` → `mcp/client.ts`、`tools/types.ts`；
- `mcp/client.ts` → `@modelcontextprotocol/sdk` + `config/config.ts`（仅类型）；
- `tools/tool-search.ts` → `tools/registry.ts`、`tools/types.ts`；
- `tools/registry.ts` 完全独立，不反向依赖任何 mcp 模块。

## 文件组织

```text
gcode/
├── src/
│   ├── mcp/
│   │   ├── client.ts          ─ 新：MCPClient + expandEnv + AnyTransport
│   │   ├── manager.ts         ─ 新：MCPManager + ConnectResult
│   │   └── tool-wrapper.ts    ─ 新：MCPToolWrapper + sanitizeName
│   ├── tools/
│   │   ├── registry.ts        ─ 改：deferred / discovered / searchDeferred 等 API
│   │   ├── tool-search.ts     ─ 新：ToolSearchTool
│   │   └── types.ts           ─ 改：Tool.deferred / Tool.system 字段
│   ├── config/
│   │   └── config.ts          ─ 改：MCPServerConfig + AppConfig.mcp_servers + 三层合并
│   ├── tui/
│   │   └── app.tsx            ─ 改：mcpServers prop / MCPManager 接线 / /mcp / /status
│   └── main.tsx               ─ 改：把 cfg.mcp_servers 透传给 <App>
├── package.json                ─ 改：dependencies + "@modelcontextprotocol/sdk"
├── tsconfig.json
└── docs/typescript/ch07/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 协议层实现 | 官方 `@modelcontextprotocol/sdk` | 避免自研 JSON-RPC / 握手 / 帧；SDK 已含 stdio / Streamable HTTP / SSE 三套 transport |
| 配置文件位置 | 三层 yaml：`~/.gcode/config.yaml`、`<cwd>/.gcode/config.yaml`、`<cwd>/.gcode/config.local.yaml` | 与 providers / hooks 共享配置文件；`.local.yaml` 走 gitignore 放本地凭据 |
| 合并语义 | `mcp_servers` 按 `name` 字段，同名后层完整覆盖前层；新名追加 | 避免字段级半合并出畸形 server；保留新增能力 |
| server 类型判定 | 看 `command` / `url` / `transport` 字段；二者都无 → 抛错 | 不引入额外 `type` 字段；字段名本身已表达意图 |
| 变量展开范围 | `env` / `headers` 的值；同时支持 `${VAR}` 与 `$VAR` | 凭据走环境变量；两种语法兼顾 shell 习惯 |
| 未定义变量 | 静默替换为空串 | 不替 server 拍板；server 自行决定如何处理无凭据 |
| 工具命名 | `mcp__<sanitize(server)>__<sanitize(tool)>`，非 `[a-zA-Z0-9_-]` → `_` | LLM 工具名安全字符；一眼识别来源 |
| deferred 默认值 | MCP 工具 `deferred = true` | 远端工具数量 / schema 长度不可控，默认不进 prompt 避免污染上下文 |
| ToolSearch 检索策略 | 子串关键词 + `select:` 精确加载 | 简单可控；子串匹配对工具 `name` / `description` 即可覆盖大多数场景；无需引入 `fuse.js` |
| 启动连接方式 | `useEffect` 内 fire-and-forget `connectAll().then(...)` | 不阻塞 chat 进入；result 回来时再注册 + 推 system 消息提示用户 |
| 连接并行度 | 串行（`for...of`） | 实现简单 + 错误隔离单点清晰；MCP server 数量通常很少（< 5），串行总时延可接受 |
| 启动超时 | 不主动加 timeout 包装 | SDK transport 自身的连接 promise 在传输错误时会 reject；不引入额外的超时复杂度 |
| 调用错误 | catch 后转 `{ output: "MCP tool error: <msg>", isError: true }` | 与 ch04/ch05 不中断 Agent loop 的契约一致 |
| 非 text 内容块 | `JSON.stringify(c)` 拼入 output | 不丢信息；让模型自行决定如何理解；不引入额外抽象 |
| stderr | `stderr: "ignore"` | 避免 stdio server 的子进程 stderr 污染 TUI 输出 |
| disconnect 时机 | 不在 App 退出时显式调用 | 子进程随 Node 主进程退出由 OS 终止；HTTP / SSE 会话由 SDK 自身在 Node teardown 时清理 |
| provider 适配方式 | `ToolRegistry.getAllSchemas(protocol)` 统一分支 | MCP 工具与内置工具复用同一 `schema()`；provider 适配层零修改 |
| instructions 注入 | `convRef.addSystemReminder("# MCP Server: <name>\n<text>")` | 与 skill / memory / plan 等模块的注入方式一致，统一走 `<system-reminder>` |
| 失败展示 | `setMessages([...prev, { role: "system", content: "MCP errors: ..." }])` | 让用户在 chat 第一屏就能看到失败，不只在 stderr |
| `/mcp` 命令 | 读 `mcpInfo` state 渲染纯文本块 | 与 `/status` 风格一致；无需独立面板 |
````

````markdown
# MCP 客户端 Tasks

> 模块路径：`src/mcp/*.ts`、`src/tools/tool-search.ts`、`src/tools/registry.ts`、`src/config/config.ts`、`src/tui/app.tsx`；运行时 bun + TypeScript 5.x；MCP 协议层 `@modelcontextprotocol/sdk`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 改   | `package.json` | 添加 `@modelcontextprotocol/sdk ^1.29.0` 依赖；保持 `bun test` / `tsc --noEmit` 脚本 |
| 改   | `src/config/config.ts` | 新增 `MCPServerConfig` 接口；`AppConfig.mcp_servers` 字段；`loadSingleFile` 提取 `mcp_servers`；`mergeConfig` 按 `name` 合并；`loadConfig` 三层文件累积 |
| 改   | `src/tools/types.ts` | `Tool` 接口加 `deferred?: boolean` / `system?: boolean` 字段 |
| 改   | `src/tools/registry.ts` | 加 `discovered: Set<string>`、`getDeferredToolNames`、`getDeferredTools`、`searchDeferred`、`findDeferredByNames`、`markDiscovered`、`isDiscovered`；`getAllSchemas` 跳过 deferred 未激活工具，并支持 `openai` / `openai-compat` 协议 |
| 新建 | `src/tools/tool-search.ts` | `ToolSearchTool implements Tool`（`system: true`、`category: "read"`）；`select:` 精确激活 / 关键词检索两种模式 |
| 新建 | `src/mcp/client.ts` | `MCPClient` + `expandEnv` + `AnyTransport`；三种 transport 构造；五个公共方法 |
| 新建 | `src/mcp/manager.ts` | `MCPManager` + `ConnectResult`；`connectAll` 串行 + 失败隔离 |
| 新建 | `src/mcp/tool-wrapper.ts` | `MCPToolWrapper implements Tool` + `sanitizeName` |
| 改   | `src/tui/app.tsx` | `Props.mcpServers` / `mcpManagerRef` / `mcpInfo` / `createToolRegistry` 中注册 `ToolSearchTool`；`initClient` 内 `MCPManager.connectAll().then(...)`；`/mcp` 与 `/status` 输出 |
| 改   | `src/main.tsx` | 把 `cfg.mcp_servers` 透传给 `<App mcpServers={cfg.mcp_servers}>` |

---

## T1: 安装 SDK 依赖**文件：** `package.json`
**依赖：** 无
**步骤：**
1. 在 `dependencies` 中加 `"@modelcontextprotocol/sdk": "^1.29.0"`。
2. `bun install` 拉依赖；确认 `node_modules/@modelcontextprotocol/sdk/dist/esm/client/` 下存在 `index.js`、`stdio.js`、`streamableHttp.js`、`sse.js` 四个入口。
3. 写一个最小试编：
   ```ts
   import { Client } from "@modelcontextprotocol/sdk/client/index.js";
   const c = new Client({ name: "smoke", version: "0.0.0" }, {});
   ```
   `tsc --noEmit` 通过。

**验证：** `bun install` 成功；`tsc --noEmit` 无错误。

## T2: 配置类型与三层合并**文件：** `src/config/config.ts`
**依赖：** 无（可与 T1 并行）
**步骤：**
1. 新增 `MCPServerConfig` 接口（见 plan.md「核心数据结构」）。
2. `AppConfig` 加 `mcp_servers: MCPServerConfig[]` 字段（非可选；空时为 `[]`）。
3. `loadSingleFile(path)` 解析后取 `(raw.mcp_servers as MCPServerConfig[]) ?? []` 入 `AppConfig`。
4. `mergeConfig(base, override)`：当 `override.mcp_servers.length > 0` 时：
   - `const byName = new Map<string, number>(); base.mcp_servers.forEach((s, i) => byName.set(s.name, i));`
   - 遍历 `override.mcp_servers`：同名 `byName.get(s.name) !== undefined` → `base.mcp_servers[idx] = s`；不同名 → `push`，并把新索引塞回 `byName`。
5. `loadConfig()` 缺省路径走三层文件：`~/.gcode/config.yaml` → `<cwd>/.gcode/config.yaml` → `<cwd>/.gcode/config.local.yaml`，每层 `existsSync` 跳过缺失，存在则 `loadSingleFile` 后用 `mergeConfig` 累积。三个都不存在则抛 `ConfigError("No config file found...")`。

**验证：** 增补 `tests/config.test.ts` 用例：
- 仅用户层 / 仅项目层 / 三层都有同名 server → 最终值来自最后存在的那层；
- 三层都不存在 → 抛 `ConfigError`；
- `loadSingleFile` 对 yaml 解析失败抛错 → main 退出。

## T3: Tool 接口扩展与 Registry 改造**文件：** `src/tools/types.ts`、`src/tools/registry.ts`
**依赖：** 无
**步骤：**
1. `Tool` 接口加 `deferred?: boolean` / `system?: boolean`。
2. `ToolRegistry` 加私有 `discovered = new Set<string>()`。
3. `getAllSchemas(protocol)` 改为带 `protocol: "anthropic" | "openai" | "openai-compat"` 参数（默认 `"anthropic"`）：
   - 跳过 `tool.deferred && !this.discovered.has(tool.name)`；
   - anthropic 协议：直接 `push(tool.schema())`；
   - openai / openai-compat 协议：`push({ type: "function", function: { name, description, parameters: base.input_schema } })`。
4. 新增 API：`getDeferredToolNames(): string[]`、`getDeferredTools(): Tool[]`、`searchDeferred(query, maxResults=5): Tool[]`（lowercase 子串匹配 `name` 与 `description`）、`findDeferredByNames(names): Tool[]`（精确 `Map.get` + 过滤 `deferred === true`）、`markDiscovered(name): void`、`isDiscovered(name): boolean`。

**验证：** 单测覆盖：
- 注册一个 `deferred: true` 工具 → `getAllSchemas("anthropic")` 不含它；
- `markDiscovered(name)` 后再调 `getAllSchemas` → 含它；
- `searchDeferred("hub")` 返回名/描述含 "hub" 的 deferred 工具；
- `findDeferredByNames(["x", "y"])` 过滤掉非 deferred 与不存在的名字。

## T4: MCP 客户端（MCPClient）**文件：** `src/mcp/client.ts`
**依赖：** T1、T2
**步骤：**
1. 导入：
   ```ts
   import { Client } from "@modelcontextprotocol/sdk/client/index.js";
   import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
   import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
   import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
   import type { MCPServerConfig } from "../config/config.js";
   ```
2. 定义并导出 `MCPTool` 接口、`AnyTransport` 联合类型。
3. 实现 `expandEnv(value)`：正则 `/\$\{(\w+)\}|\$(\w+)/g`，回调用 `process.env[a ?? b] ?? ""`。
4. `MCPClient` 类：
   - 字段：`name`（来自 `config.name`）、`private config`、`private client: Client | null`、`private transport: AnyTransport | null`。
   - `connect()`：按 `config.command` / `config.url` 二选一构造 transport，详见 plan.md；构造完后 `new Client({ name: "gcode", version: "0.1.0" }, {})` + `await this.client.connect(this.transport)`。
   - `getInstructions(): string`：`return this.client?.getInstructions() ?? ""`。
   - `listTools(): Promise<MCPTool[]>`：未连接抛错；调 `client.listTools()` 后映射 `result.tools` 为 `MCPTool[]`。
   - `callTool(name, args): Promise<string>`：未连接抛错；调 `client.callTool({ name, arguments: args })`；对 `result.content` 数组：`type === "text"` 取 `.text ?? ""`，否则 `JSON.stringify(c)`；用 `\n` 拼接；无 `content` 时 `JSON.stringify(result)`。
   - `disconnect()`：`try { await this.client?.close() } catch {}`；置空字段。

**验证：**
- `tsc --noEmit` 无错误；
- 手写最小单测/烟雾脚本：用 `npx -y @modelcontextprotocol/server-everything` 起 stdio server，断言 `connect` + `listTools` 返回非空数组；`callTool("echo", { message: "hi" })` 返回字符串含 "hi"；
- 仅有 `url` + `transport: "sse"` 时构造的是 `SSEClientTransport`，无 `command` 也无 `url` 时 `connect()` 抛 `needs either 'command' (stdio) or 'url' (http/sse)`。

## T5: 连接管理器（MCPManager）**文件：** `src/mcp/manager.ts`
**依赖：** T4
**步骤：**
1. 导入：
   ```ts
   import type { MCPServerConfig } from "../config/config.js";
   import { MCPClient } from "./client.js";
   import type { MCPTool } from "./client.js";
   ```
2. 导出 `ConnectResult` 接口（`tools` / `servers` / `errors` / `instructions` 四个数组）。
3. `MCPManager` 类：
   - 私有 `clients = new Map<string, MCPClient>()`；
   - `async connectAll(configs)`：
     - 初始化 `const result: ConnectResult = { tools: [], servers: [], errors: [], instructions: [] }`；
     - `for (const cfg of configs) { const client = new MCPClient(cfg); try { await client.connect(); this.clients.set(cfg.name, client); result.servers.push(cfg.name); const tools = await client.listTools(); for (const tool of tools) result.tools.push({ serverName: cfg.name, tool }); const instr = client.getInstructions(); if (instr) result.instructions.push({ serverName: cfg.name, text: instr }); } catch (err) { result.errors.push({ serverName: cfg.name, error: (err as Error).message }); } }`；
     - return result。
   - `getClient(name)` → `this.clients.get(name)`；
   - `disconnectAll()` → `for (const c of this.clients.values()) await c.disconnect(); this.clients.clear()`。

**验证：**
- 单测：构造两个 stub MCPServerConfig：一个 command 不存在、一个真实可用 server；`connectAll` 返回 `errors.length === 1 && tools.length > 0`；
- 单测：`disconnectAll` 后 `getClient("any")` 返回 `undefined`。

## T6: 工具包装（MCPToolWrapper）**文件：** `src/mcp/tool-wrapper.ts`
**依赖：** T4、T3
**步骤：**
1. 导入：
   ```ts
   import type { Tool, ToolResult, ToolContext } from "../tools/types.js";
   import type { MCPClient, MCPTool } from "./client.js";
   ```
2. `function sanitizeName(serverName, toolName)`：
   ```ts
   const clean = (s: string) => s.replace(/[^a-zA-Z0-9_-]/g, "_");
   return `mcp__${clean(serverName)}__${clean(toolName)}`;
   ```
3. `MCPToolWrapper implements Tool`：
   - 字段：`name`（`sanitizeName` 结果）、`description`（远端 `tool.description`）、`category = "command" as const`、`deferred = true`、私有 `client` / `originalName`（远端原始名）/ `inputSchema`。
   - 构造函数 `(client: MCPClient, serverName: string, tool: MCPTool)`：组装上述字段。
   - `schema()`：`{ name: this.name, description: this.description, input_schema: this.inputSchema }`。
   - `async execute(args, _ctx)`：`try { const output = await this.client.callTool(this.originalName, args); return { output, isError: false } } catch (err) { return { output: "MCP tool error: " + (err as Error).message, isError: true } }`。

**验证：**
- 单测：构造一个 `MCPTool { name: "create.issue", description: "..", inputSchema: {...} }` + 一个 stub `MCPClient`（其 `callTool` 用 sinon 风格手写 stub）→ wrapper.name 为 `mcp__github__create_issue`；`execute({ title: "x" }, ctx)` 返回 `{ output: <stub 返回值>, isError: false }`；stub 抛错时返回 `{ output: /^MCP tool error: /, isError: true }`。

## T7: ToolSearch 内置工具**文件：** `src/tools/tool-search.ts`
**依赖：** T3
**步骤：**
1. 导入：
   ```ts
   import type { Tool, ToolResult, ToolContext } from "./types.js";
   import { strArg, intArg } from "./types.js";
   import type { ToolRegistry } from "./registry.js";
   ```
2. `ToolSearchTool implements Tool`：
   - 字段：`name = "ToolSearch"`、`description = "Search for and load deferred tools by name or keyword."`、`category = "read" as const`、`system = true`；私有 `registry`。
   - 构造函数 `(registry: ToolRegistry)`：存 `registry`。
   - `schema()`：返回带 `query: string`（required）与 `max_results: integer`（default 5）的 input_schema。
   - `async execute(args, _ctx)`：
     - `const query = strArg(args, "query"); const maxResults = intArg(args, "max_results", 5);`
     - `if (!query) return { output: "Error: query is required", isError: true };`
     - 若 `query.startsWith("select:")`：`const names = query.slice(7).split(",").map(n => n.trim()); const tools = this.registry.findDeferredByNames(names); for (const t of tools) this.registry.markDiscovered(t.name); if (tools.length === 0) return { output: "No deferred tools found matching: " + names.join(", "), isError: false }; const schemas = tools.map(t => JSON.stringify(t.schema(), null, 2)); return { output: schemas.join("\n\n"), isError: false };`
     - 否则：`const tools = this.registry.searchDeferred(query, maxResults); if (tools.length === 0) return { output: "No deferred tools matched the query.", isError: false }; const lines = tools.map(t => "- " + t.name + ": " + t.description.slice(0, 100)); return { output: lines.join("\n"), isError: false };`

**验证：** 单测：
- 空 query → `isError: true`；
- 关键词命中 deferred 工具 → 输出含 `- <name>: <desc>` 行 + 未 `markDiscovered`；
- `select:name1,name2` → 返回 schema JSON + `isDiscovered(name1) === true`；
- `select:not-exist` → 输出 "No deferred tools found matching: not-exist"，`isError: false`。

## T8: TUI 接线（App）**文件：** `src/tui/app.tsx`
**依赖：** T2、T5、T6、T7
**步骤：**
1. `Props` 加 `mcpServers: MCPServerConfig[]`。
2. `createToolRegistry(workDir, taskList)` 中加 `registry.register(new ToolSearchTool(registry))`（已在源码里）。
3. 加 `const [mcpInfo, setMcpInfo] = useState<{ servers: string[]; toolCount: number } | null>(null);`、`const mcpManagerRef = useRef<MCPManager | null>(null);`。
4. 在 `initClient` 内部连完 LLM 客户端后：
   ```ts
   if (mcpServers.length > 0) {
     const mgr = new MCPManager();
     mcpManagerRef.current = mgr;
     mgr.connectAll(mcpServers).then((result) => {
       for (const { serverName, tool } of result.tools) {
         const client = mgr.getClient(serverName);
         if (client) {
           registryRef.current.register(new MCPToolWrapper(client, serverName, tool));
         }
       }
       if (result.errors.length > 0) {
         setMessages(prev => [...prev, { role: "system", content: "MCP errors: " + result.errors.map(e => e.serverName + ": " + e.error).join("; ") }]);
       }
       if (result.servers.length > 0) {
         setMcpInfo({ servers: result.servers, toolCount: result.tools.length });
       }
       for (const { serverName, text } of result.instructions) {
         convRef.current.addSystemReminder("# MCP Server: " + serverName + "\n" + text);
       }
     });
   }
   ```
5. `handleSlashCommand` 中加 `/mcp` 处理：
   - 无 `mcpInfo` 或 `servers.length === 0` → `setMessages(prev => [...prev, { role: "system", content: "No MCP servers connected." }])`；
   - 否则按 plan.md 文案输出。
6. `/status` 命令的输出加一行 `"MCP:       " + (mcpInfo?.servers.length ?? 0) + " server(s), " + (mcpInfo?.toolCount ?? 0) + " tool(s)"`。
7. `useEffect` 依赖数组加 `mcpServers`。

**验证：** `tsc --noEmit` 无错误；`bun test` 不退化。

## T9: main.tsx 透传配置**文件：** `src/main.tsx`
**依赖：** T2
**步骤：**
1. 把 `cfg.mcp_servers` 加进 `<App>` 的 props：
   ```tsx
   <App
     providers={cfg.providers}
     mcpServers={cfg.mcp_servers}
     hooks={cfg.hooks}
   />
   ```

**验证：** `bun run src/main.tsx` 在 `~/.gcode/config.yaml` 仅有 providers、无 `mcp_servers` 字段时正常进 chat（`mcp_servers` 缺省为 `[]`）。

## T10: 端到端实跑（tmux）**文件：** —
**依赖：** T1–T9
**步骤：**
1. 在 `~/.gcode/config.yaml`（或 `.gcode/config.local.yaml`）追加：
   ```yaml
   mcp_servers:
     - name: everything
       command: npx
       args: ["-y", "@modelcontextprotocol/server-everything"]
   ```
2. `tmux new -s gcode-ch07` 起 `bun run src/main.tsx`：
   - 启动后 chat 第一屏没有 `MCP errors:` 消息；
   - `/status` 输出含 `MCP: 1 server(s), N tool(s)`；
   - `/mcp` 输出 `· everything`、`Tools: N total`；
   - 输入 `请用 ToolSearch 查 echo 工具并调用它`：模型应先发起 `ToolSearch` 调用 → 拿到 `mcp__everything__echo` 的 schema → 下一轮发起 tool_use 调用 → 拿到 echo 结果回灌。
3. 把 `command: "npx"` 改成 `command: "no-such-binary"` 再起一次：chat 第一屏出现 system 消息 `MCP errors: everything: ...`，其它功能正常；`/mcp` 输出 `No MCP servers connected.`。
4. 配两个 server（一个 stdio 一个不存在）：成功 server 的工具被注册，失败 server 进 errors。
5. `q` 退出 gcode：`ps -ef | grep server-everything` 确认子进程已被 OS 终止（Node 主进程退出连带）。

**验证：** 上述 5 步全部观察通过。

## T11: 全量检查**文件：** —
**依赖：** T1–T10
**步骤：**
1. `tsc --noEmit` 无错误；
2. `bun test` 通过（含本章新增单测）；
3. `bun test tests/config.test.ts`（重点回归三层合并）；
4. `git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'` 无命中（凭据不落盘）。

**验证：** 全部通过。

## 执行顺序

```text
T1(SDK 依赖) ──┬──→ T4(client) ──→ T5(manager) ──┐
               │                                  ├──→ T8(app 接线) ──→ T9(main 透传) ──→ T10(tmux 实跑) ──→ T11(全量检查)
T2(config)  ──┴──→ T3(types+registry) ──→ T6(wrapper) ┘
                                       └─→ T7(tool-search) ┘
```

依赖：T4 ← {T1, T2}；T5 ← T4；T3 ← 无；T6 ← {T3, T4}；T7 ← T3；T8 ← {T2, T5, T6, T7}；T9 ← T2；T10 ← T1–T9；T11 ← 全部。
````

```markdown
# MCP 客户端 Checklist

> 通过运行代码与观察 chat / `/mcp` / `/status` 输出来验证；类型 / 函数名仅作定位提示，断言本身不依赖具体命名（重命名实现而行为不变时本清单仍适用）。

## 实现完整性

- [ ] 三层 yaml 合并：`~/.gcode/config.yaml`、`<cwd>/.gcode/config.yaml`、`<cwd>/.gcode/config.local.yaml` 三层都存在时按 `mcp_servers[].name` 合并，同名后层完整覆盖前层；任一文件缺失被 `existsSync` 跳过（验证：单测构造三层文件断言合并结果与字段来源）。(AC1)
- [ ] `MCPServerConfig` 字段：`name` 必填；`command + args + env` 配置 stdio；`url + headers` 配置 http；`url + transport: "sse" + headers` 配置 sse；二者全无时 `MCPClient.connect()` 抛错并进 `ConnectResult.errors`（验证：单测覆盖三种 transport 选择，外加一个空配置抛错）。(AC2)
- [ ] 环境变量展开：`env` / `headers` 的值在 `MCPClient.connect()` 中通过 `expandEnv` 同时支持 `${VAR}` 与 `$VAR`；未定义变量替换为空串（验证：单测设置 `process.env.TOKEN` 后断言 `${TOKEN}` 与 `$TOKEN` 都被替换为该值；删除后变成 ""）。(AC3)
- [ ] stdio transport：`StdioClientTransport` 用 `command + args` 启动子进程；`env` 与 `process.env` 浅合并后注入；`stderr: "ignore"`（验证：tmux 实跑用 `npx -y @modelcontextprotocol/server-everything` 起 stdio server，断言 `connect` + `listTools` 成功；TUI 的 stderr 通道无被子进程污染）。(AC2)
- [ ] HTTP / SSE transport：`config.url` + 默认 → `StreamableHTTPClientTransport`；`config.transport === "sse"` → `SSEClientTransport`；`headers` 通过 `{ requestInit: { headers } }` 注入每次 HTTP 请求（验证：起 `httptest`-style 的最小 HTTP 服务断言 `Authorization` 头到达 server 端）。(AC2)
- [ ] 工具命名与 sanitize：`sanitizeName(serverName, toolName)` 把非 `[a-zA-Z0-9_-]` 字符替换为 `_`，最终拼成 `mcp__<a>__<b>`（验证：单测 `sanitizeName("git.hub", "create.issue")` → `mcp__git_hub__create_issue`）。(AC4)
- [ ] schema 透传：`MCPToolWrapper.schema()` 返回 `{ name, description, input_schema: inputSchema }`；anthropic 协议下原样透传；openai / openai-compat 协议下被 `ToolRegistry.getAllSchemas` 包成 `{ type: "function", function: { name, description, parameters } }`（验证：单测覆盖三种 protocol 输出结构）。(AC5/AC12)
- [ ] deferred 默认不进 prompt：`MCPToolWrapper` 字段 `deferred = true`；`ToolRegistry.getAllSchemas` 跳过 `deferred && !discovered`；`markDiscovered(name)` 后再调一次 `getAllSchemas` 包含该工具（验证：单测构造一个 deferred 工具，断言注册后立即 schemas 不含它，调 `markDiscovered` 后含它）。(AC6)
- [ ] ToolSearch 关键词检索：`query: "github"` → 返回 `- mcp__github__*: <desc>` 行，**不**激活工具（验证：单测断言 `isDiscovered("mcp__github__create_issue") === false`）。(AC7)
- [ ] ToolSearch 精确激活：`query: "select:mcp__github__create_issue,mcp__github__list_issues"` → 返回两个 schema 的 JSON 串 + 把两者 `markDiscovered`；`select:not-exist` → 返回 `"No deferred tools found matching: not-exist"`，`isError: false`（验证：单测断言 `isDiscovered === true` 与无命中文案）。(AC7)
- [ ] 调用结果聚合：`MCPClient.callTool` 把 `content` 数组按顺序处理：`type === "text"` 取 `.text ?? ""`，其它 `JSON.stringify(c)`，用 `\n` 连接（验证：单测注入 stub `Client.callTool` 返回 `[text, image, text]` 三块 content，断言输出含两段 text 与一段 JSON 字符串）。(AC8)
- [ ] 异常包装：`MCPToolWrapper.execute` 在 `client.callTool` 抛错时返回 `{ output: "MCP tool error: <msg>", isError: true }`；Agent loop 不中断（验证：单测注入 throw 的 stub client，断言返回结构）。(AC9)
- [ ] 失败隔离：`MCPManager.connectAll` 对每个 server 独立 `try/catch`，失败进 `result.errors`，不影响其它 server 与启动（验证：配置两个 server 其一 `command: "no-such-binary"`，启动后 chat 第一屏出现 `MCP errors: <name>: ...` 系统消息，另一个 server 工具仍可用）。(AC9)
- [ ] server instructions 注入：`Client.getInstructions()` 在 initialize 成功后返回非空字符串时，App 调用 `convRef.current.addSystemReminder("# MCP Server: <name>\n<text>")` 注入会话历史（验证：起一个返回 instructions 的 server，发送一条用户消息后观察 conversation 历史包含该 system-reminder）。(AC10)
- [ ] `/mcp` 命令：无连接时输出 `"No MCP servers connected."`；有连接时输出 `"MCP servers (N):"` + `"  · <name>"` 多行 + `"Tools: M total"`（验证：tmux 实跑覆盖两种状态）。(AC11)
- [ ] `/status` 命令含 MCP 行：`MCP: <N> server(s), <M> tool(s)`（验证：tmux 实跑 `/status`）。(AC11)
- [ ] provider 无感：切到 protocol 为 `openai-compat` 的 provider，`tools[]` 中 MCP 工具被自动包成 `function` 形式，模型能正常调用并拿到 `output`（验证：tmux 实跑切换 provider 后 `mcp__everything__echo` 仍可被调用）。(AC12)

## 集成

- [ ] 内置工具不受影响：6 个内置工具（`Read`、`Bash`、`Glob`、`Grep`、`Write`、`Edit`）+ 任务工具（`Task*`）+ `ExitPlanMode` + 子代理 `Task` 等在 chat 中正常调用；`ToolSearch` 注册后不影响这些（验证：tmux 实跑触发 `Read`、`Bash` 等）。
- [ ] 权限链路无变化：`PermissionChecker` 对 `mcp__*` 名按 `category: "command"` 的常规分支处理；用户用 `permission +allow mcp__github__*` 写规则后命中放行；`bypassPermissions` 模式下直接放行（验证：tmux 实跑覆盖三种 mode）。
- [ ] hooks / skills / teams / memory 不退化：`bun test` 整套通过；既有用例不需要适配（验证：`bun test`）。
- [ ] 凭据不落盘：示例 yaml 全用 `${VAR}` / `$VAR`；`git grep -E '(Bearer|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}'` 在 ch07 期间无命中（验证：本章结束时 git grep）。

## 编译与测试

- [ ] `tsc --noEmit` 无错误。
- [ ] `bun test` 通过（含本章新增的 config / registry / tool-search / mcp 相关单测）。
- [ ] `bun test tests/config.test.ts` 通过（重点守护三层合并 / `mcp_servers` 字段提取）。
- [ ] `bun install` 拉到的 `@modelcontextprotocol/sdk` 版本 ≥ `1.29.0`，且 `node_modules/@modelcontextprotocol/sdk/dist/esm/client/{index,stdio,streamableHttp,sse}.js` 四个入口均存在。
- [ ] `bun run src/main.tsx` 在 `mcp_servers: []` 配置下正常进 chat；`registry.listTools()` 返回内置 + `ToolSearch`；`getAllSchemas("anthropic")` 不含任何 `mcp__*` 工具。

## 端到端场景（tmux 实跑）

- [ ] 场景 1（无 MCP 配置）：三层 yaml 都不含 `mcp_servers` 字段时，gcode 正常进 chat；`/mcp` 输出 `No MCP servers connected.`；`/status` MCP 行显示 `0 server(s), 0 tool(s)`。(AC1)
- [ ] 场景 2（stdio server 接入）：在 `.gcode/config.local.yaml` 配 `@modelcontextprotocol/server-everything` 一类真实 server，chat 第一屏无错误消息；`/mcp` 列出该 server 与工具总数；让模型先 `ToolSearch` 检索 `echo` → 再 `select:mcp__everything__echo` 激活 → 再发起 tool_use 调用 → 拿到结果回灌后续答。(AC2/AC6/AC7)
- [ ] 场景 3（失败隔离）：配两个 server，一个 `command: "no-such-binary"` + 一个能跑的；启动后第一屏出现 `MCP errors: <name>: ...` 系统消息；能跑的 server 工具仍可正常被 `ToolSearch` 检索到并调用。(AC9)
- [ ] 场景 4（凭据展开）：配 `env: { GITHUB_TOKEN: "${GITHUB_TOKEN}" }`；`unset GITHUB_TOKEN` 后启动 server 仍尝试启动（无凭据由 server 自决报错）；`export GITHUB_TOKEN=...` 后正常工作。(AC3)
- [ ] 场景 5（HTTP server）：起一个最小 HTTP MCP server（或 SDK 的示例 echo server），配 `url` + `headers: { Authorization: "Bearer ${TOKEN}" }`；启动后工具被注册；调用时 server 端收到带 `Authorization` 头的请求。(AC2)
- [ ] 场景 6（SSE server，可选）：起一个 SSE MCP server，配 `url` + `transport: "sse"`；启动后工具被注册并可调用。(AC2)
- [ ] 场景 7（退出干净）：`q` 退出 gcode 后 `ps -ef | grep server-everything` 确认 stdio server 子进程随主 Node 进程退出而被 OS 终止，无残留。(AC9)
- [ ] 场景 8（provider 切换）：先用 anthropic protocol 跑通 echo，`/permission mode bypassPermissions` 后 `bun run src/main.tsx` 重连一个 `openai-compat` provider，仍能 `ToolSearch` + 调用同一 MCP 工具，结果一致。(AC12)
```


# 第4章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装了六个工具，实现了 Function Calling，它能读文件、写文件、搜代码、执行命令。但每次只能做一步——模型返回一个 tool\_ use，你执行完返回结果，模型给个最终回复，结束。你得一步步催它。

这一章要给 GCode 装上 Agent Loop。做完之后，模型能自主循环执行多步操作：自己读代码、自己写代码、自己跑命令、自己根据结果决定下一步，直到任务完成。它从「一步一停的工具调用」变成了真正能自主干活的 Agent。

具体要新增这些东西：

* **Agent 组件&#x20;**：持有 LLM 客户端、工具注册中心和配置，驱动核心循环

* **Agent Loop 循环逻辑&#x20;**：ReAct 模式的 while 循环，五种停止条件

* **AgentEvent 事件流&#x20;**：让 Agent 和 UI 完全解耦

* **流式收集器&#x20;**：实时透传文本，积攒完整响应

* **工具分批执行&#x20;**：partitionToolCalls，安全的并发、不安全的串行

* **Plan Mode&#x20;**：/plan 只启用读工具输出计划，/do 切换回正常模式

这章 **不做&#x20;**：权限系统、上下文压缩、用户确认机制（后续章节）。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：上一章工具齐了，但模型只能一步一停，得我一直催。这一章给 GCode 装上 Agent Loop，让它自主循环：先想，再调工具，看结果，边做边调整，直到任务完成，从被动应答变成真正能自主干活的 Agent。

技术要求：

- ReAct 模式的循环：一轮轮调 LLM、执行工具、结果回血，直到模型不再要工具
- 几种停止条件都得有（模型说完、到迭代上限、用户取消、连续调到未知工具、流出错），迭代上限是兜底安全网
- 一套异步事件流（文本、工具调用、工具结果、Token 用量、进度），让 Agent 和界面彻底解耦
- 流式收集器走双路：一边实时把文本推给界面，一边攒出完整响应供后续判断
- 一次返回多个工具调用时按安全性分批，能并发的并发跑，有副作用的串行跑
- Plan Mode 两段式：/plan 只放开读类工具让模型先出计划，/do 再切回全工具去执行

这一步先不做权限系统、上下文压缩、用户交互式确认，这些留给后续章节。
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

来验收一下结果



启动 GCode，给它一个需要多步完成的任务，比如「帮我创建一个 hello.txt 文件，写入 Hello World，然后读出来确认内容正确」。



如果 Agent Loop 正常工作，你会看到模型自主循环：先调 WriteFile 创建文件，再调 ReadFile 读取确认，最后给你一个总结回复，这就是典型的ReAct模式啦。

![]()



接着看看plan mode，我们切换到plan mode后，就会变成了只读，只能写Plan文件

![]()



这时可以看到只有可读工具，我们如果让他写入文件，是做不到的

![]()

那我们再给它一个plan任务试试，我说

![]()

可以看到，它会开始触发AskUserQuestion工具，来进行需求澄清，我们根据问题，一步步澄清需求

![]()

之后，会生成一个Plan文件，里面是我们的开发计划

![]()

可以看到，其中它遇到了一些麻烦，写入失败了，但是模型立刻就根据错误，来调整策略，然后成功写入了，这就是再一次的ReAct的体现之一



Plan计划在放在.gcode/plans下面，我们可以看看这个计划的内容

![]()



然后我们就可以去让GCode根据这个Plan去开发了

![]()

验收没问题，那么本章的主要任务就完成了。下一章，我们给它加上安全边界，让它在帮你干活的同时守护了你项目的边疆。

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

```markdown
# Agent Loop Spec## 背景ch03 给 GCode 装上了工具系统：模型能读写改文件、执行命令、按模式找文件、搜代码内容。但编排是**单轮闭环**——请求#1 拿到一批工具调用 → 执行 → 结果回灌 → 请求#2 出最终答复就停，且续答里模型再次请求的工具被**直接丢弃**。模型只能「一步一停」，复杂任务（读完 A 才知道要改 B）得用户反复催。

ch04 给 GCode 装上 **Agent Loop**：模型自主循环——想 → 调工具 → 看结果 → 边做边调整，直到任务完成。从被动应答变成能自主干活的 Agent。这是从「能用工具」到「会自己干」的关键一跃。

## 目标- **ReAct 循环**：一轮轮调 LLM、执行工具、结果回血，直到模型不再请求工具。
- **多种停止条件**：自然完成、迭代上限（兜底安全网）、用户取消、连续请求未知工具、流出错。
- **异步事件流**：Agent 吐出文本 / 工具调用 / 工具结果 / Token 用量 / 迭代进度等事件，让 Agent 与界面彻底解耦。
- **流式收集双路**：一边实时把文本增量推给界面，一边攒出完整响应（含工具调用）供循环判断。
- **保序分批并发**：一次回复的多个工具调用按安全性分批——连续只读并发执行，有副作用串行执行，保持模型给出的相对顺序。
- **Plan Mode 两段式**：`/plan` 只放开只读工具让模型先出计划；`/do` 切回全工具并立即按计划执行。

## 功能需求

- F1: ReAct 主循环编排
  替换 ch03 的单轮闭环。每一轮：带工具定义发起请求 → 流式收集本轮响应 → 若模型请求了工具则执行并把结果回灌进历史，进入下一轮；若模型给出无工具调用的纯文本，则该文本即最终答复，循环结束。不再丢弃续答里的工具调用。

- F2: 多种停止条件
  循环在以下任一条件下停止，每种都干净收尾（对话历史保持合法 + 给界面明确信号）：
  1. 自然完成——模型回复不含工具调用，纯文本即最终答复。
  2. 迭代上限——达到内置上限兜底，避免失控；触顶时给出提示并停。
  3. 用户取消——见 F7。
  4. 连续未知工具——模型连续多轮只请求注册中心不存在的工具达阈值即停，避免对幻觉工具空转。
  5. 流出错——provider 流返回错误，停止本轮并提示，不崩溃、不中断会话。

- F3: 异步事件流（Agent ↔ 界面解耦）
  Agent 对外只吐事件，界面只消费事件、不感知循环内部细节。事件涵盖：文本增量、工具调用开始、工具调用结束（结果摘要 + 是否错误）、Token 用量、迭代进度、本轮结束、错误。

- F4: 流式收集双路
  每轮请求的流式响应走双路：一路把文本增量实时推给事件流（界面即时显示），一路累积完整文本并拼接出完整工具调用（含分片到达的 JSON 参数），供循环判断下一步。

- F5: 保序分批并发执行
  工具区分「只读 / 有副作用」两类。一次回复的多个工具调用按模型给出的顺序扫描：连续的只读调用合并为一个并发批并行执行，遇到有副作用调用则单独串行执行，保持整体相对顺序。批内并发完成后，结果按原始调用顺序回灌。每个工具仍受 per-tool 超时约束（沿用 ch03）。

- F6: 结果回灌与历史一致
  每轮的 assistant 回合（含工具调用）与工具结果回合按序写入对话历史，下一轮请求携带完整历史。任何提前终止（取消 / 上限 / 未知工具 / 出错）后，对话历史都保持合法——工具调用与结果配对、角色交替不被破坏，会话可继续。被取消时为已发起但未完成的工具调用补「已取消」结构化结果。

- F7: 用户取消本轮
  流式态下 Esc 或 Ctrl+C 中断当前 Loop：停止后续迭代、回到空闲态、不退出程序；空闲态 Ctrl+C 退出程序。中断后历史保持合法（见 F6），可继续对话。

- F8: Token 用量统计
  从 provider 流式响应中提取每轮的 token 用量（输入 / 输出），跨轮累加为会话累计量，在状态栏展示。

- F9: 迭代进度展示
  流式态动态区展示当前迭代轮次，让用户感知 Agent 正在多轮推进。

- F10: Plan Mode 两段式
  `/plan` 进入计划模式：仅注入只读工具定义 + 计划态系统提示（让模型先产出计划、不动手改动）；`/do` 切回全工具模式并立即用一条内置提示触发模型按上文计划执行。模式跨轮保持，直到再次切换。

- F11: 跨协议一致
  Anthropic 与 OpenAI（含兼容 base_url）两协议都跑通完整 Loop——多轮工具调用、用量提取、取消行为一致。

## 非功能需求

- N1: 工具执行超时——每个工具执行仍受 per-tool 超时约束（沿用 ch03 内置 30s，不可配）；超时以结构化结果回灌，不中断循环。
- N2: 界面不阻塞——多轮循环、工具执行（含并发批）期间界面持续响应，spinner、迭代进度、计时正常刷新，不冻结。
- N3: scrollback 顺序正确——跨多轮的 preamble 文本、工具行、结果摘要、最终答复按真实发生顺序提交到 scrollback；并发批的工具行按模型给出的调用顺序排列，整体不交错。
- N4: 结果体量受控——工具结果沿用 ch03 工具级截断（行 / 字符上限 + `[truncated]`）；多轮累积下上下文与界面均不被撑爆。
- N5: 取消及时、无泄漏——Esc / Ctrl+C 后尽快停止后续迭代（正在执行的工具靠 ctx 取消尽力而为）；循环退出后不残留挂起的 goroutine 或未关闭的 channel。
- N6: 并发安全——并发批内的工具执行与结果收集无数据竞争（`go test -race ./...` 通过）。
- N7: 密钥不回显——沿用 ch03，对话区与任何输出均不出现 api_key。
- N8: 代码规范——gofmt / goimports 合规（分组正确）、`go vet ./...` 无告警（遵循项目 CLAUDE.md）。

## 不做的事

- 权限系统 / 交互式确认——工具执行（含写文件、执行命令）前不做授权确认（留待专门章节）。
- 上下文压缩 / 历史裁剪——多轮累积的历史不压缩、不裁剪，超长会话可能触及上下文上限（留待后续）。
- 工具执行沙箱 / 路径白名单——沿用 ch03，不限制工具只能在工作目录内操作。
- 工具调用与结果持久化——沿用 ch02/ch03，退出即丢。
- 迭代上限 / 超时配置化——均为内置常量，本章不通过配置调整。
- 跨批重排并发——只在「连续只读」批内并发；不把读写调用重排以追求最大并行度。
- 子 Agent / 任务分解工具（如 Task 工具）——不做。
- Plan Mode 的计划落盘 / 审批门工具（如 ExitPlanMode）——`/plan`、`/do` 为简单手动切换，不引入计划审批工具或计划持久化。
- Token 预算限制 / 按用量自动停止——只统计与展示用量，不按预算自动截断。
- 多模态——工具结果与对话均为文本。
- 流式工具结果——工具结果一次性回灌，不做流式产出。

## 验收标准

- AC1: 多轮自动连环——给需要连续两步工具的任务（如「读 `docs/ch03/spec.md`，再据其内容新建一个摘要文件」），Agent 自动多轮执行工具调用并回灌结果；当某轮模型不再请求工具、只输出纯文本时循环停止、该文本即最终答复，全程无需用户中途催。(F1)
- AC2: 自然完成——模型给出无工具调用的纯文本时循环立即停止，该文本即最终答复。(F2)
- AC3: 迭代上限兜底——构造模型反复调工具不收手的情形（或将上限调低），达到上限即停并提示，不无限循环。(F2)
- AC4: 连续未知工具停止——模型连续请求注册中心不存在的工具达阈值时，循环停止并提示。(F2)
- AC5: 流出错恢复——provider 流出错时停止本轮、给出错误提示、程序不退出，之后可继续正常对话。(F2)
- AC6: 事件流完备——Agent 对外事件涵盖文本、工具调用开始/结束、Token 用量、迭代进度、结束、错误；界面仅靠这些事件渲染。(F3)
- AC7: 流式收集双路——文本实时显示的同时，模型一次回复中完整的工具调用（含拼齐的 JSON 参数）被正确收集用于下一轮。(F4)
- AC8: 保序分批并发——一次回复含多个工具调用时，连续只读并发执行、有副作用串行执行，保持相对顺序；结果按原始顺序回灌。(F5)
- AC9: 历史一致——多轮的 assistant 与工具结果回合按序入历史；取消 / 上限 / 出错终止后历史仍配对合法，可继续对话（不出现连续同角色或悬空工具调用导致下一轮请求 400）。(F6)
- AC10: 用户取消——流式态 Esc 或 Ctrl+C 中断本轮、回空闲态、不退出；空闲态 Ctrl+C 退出程序。(F7)
- AC11: 用量展示——状态栏显示会话累计 token 用量（输入 / 输出），随轮次增长更新。(F8)
- AC12: 进度展示——流式态动态区显示当前迭代轮次。(F9)
- AC13: Plan Mode——`/plan` 后模型仅用只读工具产出计划、不产生写/执行类调用；`/do` 切回全工具并立即按上文计划执行（产生写/执行类工具调用）。(F10)
- AC14: 跨协议一致——anthropic 与 openai（兼容端点）两种配置都跑通完整多轮 Loop，触发 / 执行 / 回灌 / 用量 / 取消行为一致。(F11)
```

````markdown
# Agent Loop Plan

> 基于已批准的 spec.md。本文档与语言相关（Go）。SDK 类型已对 anthropic-sdk-go v1.46.0、openai-go/v3 v3.37.0 核对（grounding 实测）。

## 架构概览ch04 不新增包，在 ch03「tool / agent / llm / conversation / prompt / tui」之上**扩展**：

- **internal/agent（重写 Run）**：把 ch03 的「请求#1 → 执行 → 请求#2 → 停」改为真正的 ReAct 循环——`for` 迭代直到自然完成 / 上限 / 取消 / 连续未知工具 / 出错。新增保序分批并发执行、迭代进度与用量事件、终止时的历史一致性收尾、Plan/Normal 两种模式。
- **internal/llm（扩展）**：`StreamEvent` 增 `Usage` 字段；`Provider.Stream` 增 `systemSuffix string` 形参（Plan Mode 系统提示后缀）；两适配器在流结束后上抛本轮 token 用量、把 `systemSuffix` 拼到内置系统提示后；OpenAI 打开 `StreamOptions.IncludeUsage`。
- **internal/tool（扩展）**：`Tool` 接口增 `ReadOnly() bool`；6 个工具各实现；`Registry` 增 `ReadOnlyDefinitions()` 与 `IsReadOnly(name)`。
- **internal/conversation（扩展）**：增 `LastRole()`（终止收尾判断角色尾巴）。
- **internal/prompt（扩展）**：增 `PlanModeReminder`（计划态系统后缀）与 `ExecuteDirective`（`/do` 触发执行的用户消息）；`SystemPrompt` 增补「持续工作直到任务完成」的 Agent 循环约定。
- **internal/tui（扩展）**：`submit` 识别 `/plan`、`/do`；引入 per-turn 取消上下文；事件泵处理用量 / 进度 / 通知 / 多个并发工具；按键处理拆分 Esc / Ctrl+C；状态栏显示模式与累计用量、动态区显示迭代轮次。

依赖方向不变、无环：`tool → llm`；`conversation → llm`；`agent → {llm, tool, conversation}`；`tui → {agent, tool, conversation, llm, prompt}`；`llm → {config, prompt}`。

## 核心数据结构### llm 包（provider.go 扩展）

```go
// Usage 协议无关地承载一轮请求的 token 用量。
type Usage struct {
  InputTokens  int64 // 本轮请求输入（含完整历史）token 数
  OutputTokens int64 // 本轮响应输出 token 数
}

// StreamEvent 扩展：在 Text/ToolCalls/Done/Err 之外，turn 结束时一次性上抛 Usage。
type StreamEvent struct {
  Text      string
  ToolCalls []ToolCall
  Usage     *Usage // 非空：本轮 token 用量（Done 之前一次性发出）
  Done      bool
  Err       error
}
```

`Provider.Stream` 签名变更（新增第 4 形参）：

```go
// systemSuffix 非空时拼接到内置 system prompt 之后（Plan Mode 计划态约束）；为空即普通模式。
Stream(ctx context.Context, msgs []Message, tools []ToolDefinition, systemSuffix string) <-chan StreamEvent
```

`Message`/`ToolCall`/`ToolResult`/`ToolDefinition` 与 `RoleTool` 沿用 ch03，不变。

### tool 包（接口扩展）

```go
// Tool 接口新增 ReadOnly：true=只读工具（可并发执行 & Plan Mode 放行）。
type Tool interface {
  Name() string
  Description() string
  Parameters() map[string]any
  ReadOnly() bool // 新增
  Execute(ctx context.Context, args json.RawMessage) Result
}
```

只读分类（依据语义）：`read_file`/`glob`/`grep` → `true`；`write_file`/`edit_file`/`bash` → `false`（`bash` 可执行任意副作用命令，保守归为有副作用、串行执行）。

`Registry` 新增：

```go
func (r *Registry) ReadOnlyDefinitions() []llm.ToolDefinition // Plan Mode：只导出 ReadOnly()==true 的工具定义
func (r *Registry) IsReadOnly(name string) bool               // 分批判定；未知工具返回 false（按串行处理）
```

### agent 包（事件模型扩展 + Run 重写）

```go
// Usage 一轮请求的 token 用量（透传 llm.Usage 的语义）。
type Usage struct {
  Input  int64
  Output int64
}

// Event 对外事件流元素，消费者据非零字段分派渲染。
type Event struct {
  Text   string     // 模型文本增量（preamble 或最终答复）
  Tool   *ToolEvent // 工具调用开始/结束（沿用 ch03）
  Usage  *Usage     // 本轮 token 用量（每轮 stream 结束后一次）
  Iter   int        // >0：进入第 Iter 轮迭代（进度提示）
  Notice string     // 系统提示（停止原因等），仅用于 UI 展示，不入对话历史
  Done   bool       // 本轮（整个 Loop）结束
  Err    error      // 出错（不中断会话）
}

// Mode 区分普通模式与计划模式。
type Mode int

const (
  ModeNormal Mode = iota
  ModePlan
)

// Run 执行 Agent Loop，返回事件 channel；mode 决定工具集与系统后缀。
func (a *Agent) Run(ctx context.Context, conv *conversation.Conversation, mode Mode) <-chan Event
```

`ToolEvent`、`Phase`(PhaseStart/PhaseEnd)、`Agent`、`New` 沿用 ch03。`Run` 签名新增 `mode` 形参。

`New` 沿用 ch03：`func New(p llm.Provider, r *tool.Registry) *Agent`。`mode` 为 `Run` 的每次调用入参，不写入 `Agent` 状态（同一 `Agent` 可被不同 mode 复用）。

迭代、停止常量与提示文案（内置，不可配）：

```go
const (
  maxIterations = 25 // 迭代上限兜底（F2）
  maxUnknownRun = 3  // 连续「整轮只产生未知工具调用」的迭代数上限（F2）
)

// 停止/收尾提示文案——既作为 Event{Notice} 推给 UI，也作为 ensureAssistantTail 写入历史的兜底文本。
const (
  noticeMaxIter      = "（已达最大迭代轮数 25，自动停止；可继续发消息推进。）"
  noticeUnknownTools = "（连续多轮只请求到未注册的工具，自动停止。）"
  noticeStreamErr    = "（请求出错，本轮已中断。）"
  noticeCancelled    = "（已取消。）"
)
```

## 模块设计### internal/agent（核心：Run 重写）**职责：** ReAct 循环编排（F1/F2）、保序分批并发执行（F5）、事件流（F3/F8/F9）、终止历史一致性（F6）、Plan/Normal 模式（F10）。
**对外接口：** `Agent`、`New`、`Run(ctx, conv, mode)`、`Event`、`ToolEvent`、`Phase`、`Mode`、`Usage`。
**依赖：** `llm`、`tool`、`conversation`、`context`、`sync`（并发批 WaitGroup）。

**Run 算法（goroutine 内，`defer close(ch)`）：**

1. 按 `mode` 取工具集与系统后缀：
   - `ModePlan` → `defs = registry.ReadOnlyDefinitions()`、`suffix = prompt.PlanModeReminder`。
   - `ModeNormal` → `defs = registry.Definitions()`、`suffix = ""`。
2. `unknownRun := 0`。
3. `for iter := 1; iter <= maxIterations; iter++`：
   1. `emit(Event{Iter: iter})`（进度，F9）；emit 返回 false（ctx 取消）→ `finishCancelled(conv)`、return。
   2. `text, calls, usage, ok := streamOnce(ctx, conv, defs, suffix, ch)`。
      - `!ok` 且 `ctx.Err()!=nil`（取消）→ `finishCancelled(conv)`、return。
      - `!ok` 且 `ctx.Err()==nil`（流出错，Err 已在 streamOnce 内发出）→ `ensureAssistantTail(conv, noticeStreamErr)`、return。
   3. `if usage != nil { emit(Event{Usage:&Usage{usage.InputTokens, usage.OutputTokens}}) }`（F8）。
   4. **无工具** `len(calls)==0`：`conv.AddAssistant(ensureFinal(ch, text))`；`emit(Event{Done:true})`；return（自然完成，F2-1）。
   5. **有工具**：`conv.AddAssistantWithToolCalls(text, calls)`。
   6. 统计未知工具：`if allUnknown(calls) { unknownRun++ } else { unknownRun = 0 }`。
   7. `results, completed := executeBatched(ctx, calls, ch)`（保序分批并发，F5）。
   8. `conv.AddToolResults(results)`（无论是否取消都回灌，含已取消占位，F6）。
   9. `if !completed`（执行中被取消）→ `ensureAssistantTail(conv, "（已取消）")`、return。
   10. `if unknownRun >= maxUnknownRun` → `emit(Event{Notice: noticeUnknownTools})`；`ensureAssistantTail(conv, noticeUnknownTools)`；`emit(Event{Done:true})`；return（F2-4）。
4. 循环正常走完（触达上限）：`emit(Event{Notice: noticeMaxIter})`；`ensureAssistantTail(conv, noticeMaxIter)`；`emit(Event{Done:true})`（F2-2）。

**streamOnce(ctx, conv, defs, suffix, ch) → (text string, calls []llm.ToolCall, usage *llm.Usage, ok bool)：**
遍历 `provider.Stream(ctx, conv.Messages(), defs, suffix)`：
- `ev.Err != nil` → `emit(Event{Err: ev.Err})`、`return "", nil, nil, false`。
- `ev.Usage != nil` → 记录 `usage = ev.Usage`（不立即 emit，由 Run 在拿到后统一 emit）。
- `len(ev.ToolCalls) > 0` → `calls = append(calls, ev.ToolCalls...)`。
- `ev.Text != ""` → 累积 `text` 并 `emit(Event{Text: ev.Text})`；emit 失败→`return ...,false`。
循环后 `if ctx.Err()!=nil { return "",nil,nil,false }`；否则 `return text, calls, usage, true`。

**executeBatched(ctx, calls, ch) → (results []llm.ToolResult, completed bool)：**
保序分批（F5）。`results := make([]llm.ToolResult, len(calls))`；从 `i=0` 逐段扫描：
- 当前 `calls[i]` 只读 → 向前吃连续只读得最长区间 `[i,j)`（`j` 为首个非只读或末尾），**并发**执行该批：每个调用一个 goroutine，goroutine 内 `tctx, cancel := context.WithTimeout(ctx, tool.DefaultTimeout)` 后 `registry.Execute(tctx, ...)`，结果写入**自己下标** `results[k]`（互不重叠，无锁）；`sync.WaitGroup` 汇合。`i = j`。
- 当前 `calls[i]` 非只读 → **串行**执行单个 `calls[i]`（同样 `context.WithTimeout(ctx, tool.DefaultTimeout)`），写 `results[i]`。`i++`。
- 每段开始执行前先判 `ctx.Err()!=nil`（取消）：给区间内尚未执行的 call 填「已取消」结果（`Result{IsError:true, Content:noticeCancelled}`），其余沿用已得结果，`return results, false`。
- 全部完成 `return results, true`。

> 超时口径：每个工具各拿一个 `DefaultTimeout`（30s）子 ctx，互不相加——并发批的整体上限仍是单个 30s（N1）。子 ctx 都派生自 per-turn `ctx`，用户取消时一并 Done，工具尽快返回。

事件与顺序（满足 N3 顺序、N2 不阻塞、N6 无竞争）：
- 单个串行工具：`emit(Tool{Start})` → 执行 → `emit(Tool{End})`（沿用 ch03 时序，动态区显示该工具 Running）。
- 并发批：**先**按序 `emit(Tool{Start})` 区间内每个工具（动态区列出多个在执行的工具行）→ 并发执行 → **再**按原始顺序 `emit(Tool{End})` 每个工具（逐个把工具行 + 结果摘要提交 scrollback）。即「开始事件按序、结束事件按序」，并发只发生在执行环节，事件顺序始终是调用序，scrollback 不交错。
- 并发安全：每个 goroutine 只写自己下标的 `results[k]`（不同下标互不重叠），不触碰 `conv`；`conv.AddToolResults` 由 Run 主流程在 WaitGroup 汇合后串行调用。Token 用量累计在 TUI 侧串行处理。

**辅助函数：**
- `emit(ctx, ch, e) bool`：沿用 ch03——`select { case ch<-e: return true; case <-ctx.Done(): return false }`。即**返回 false 当且仅当 per-turn ctx 被取消**（channel 由 Run 自己持有且 `defer close`，不会在发送中被关）。调用方据 false 提前收尾。
- `allUnknown(calls)`：对每个 call 用 `registry.Get(call.Name)` 判断，**全部** `ok==false` 才返回 true；任一已注册即 false（混入已知工具视为有进展，计数重置）。不能用 `IsReadOnly`（未知工具它也返回 false，会与有副作用工具混淆）。
- `ensureFinal(ch, text)`：沿用 ch03——`text` 非空原样返回；为空则 emit 占位提示并返回占位文本（避免空 assistant 回合破坏下一轮请求）。
- `ensureAssistantTail(conv, fallback)`：若 `conv.LastRole() != llm.RoleAssistant`（含空历史、末尾为 user 或 RoleTool），`conv.AddAssistant(fallback)`，保证历史以 assistant 文本回合收尾（F6：取消/出错/上限后角色仍交替，下一轮请求不报 400）。
- `finishCancelled(conv)`：取消路径统一收尾——`ensureAssistantTail(conv, noticeCancelled)`、return（**不 emit**，因 ctx 已取消 emit 必失败；channel 经 `defer close` 关闭，TUI 由 `waitForEvent` 收到关闭即视为结束）。

> 终止优先级：执行中取消（`completed==false`）是**最高优先级**终止——立即 `ensureAssistantTail` 并 return，**跳过**未知工具计数与迭代上限检查。

### internal/llm（扩展）**职责：** 协议无关请求/响应 + 两协议工具调用全流程（沿用 ch03）+ 本轮用量上抛（F8）+ 系统后缀（F10）。

**provider.go：** 新增 `Usage` 类型；`StreamEvent` 增 `Usage *Usage`；`Provider.Stream` 增 `systemSuffix string` 形参（更新接口文档）。

**anthropic.go：**
- 系统提示：`params.System` 由硬编码 `prompt.SystemPrompt` 改为 `effectiveSystem(suffix)`——`suffix==""` 时单块 `prompt.SystemPrompt`；非空时拼成 `prompt.SystemPrompt + "\n\n" + suffix`（单 `TextBlockParam`，避免多块边界差异）。
- 用量：流正常结束（`stream.Err()==nil`、`acc.Accumulate` 完成）后，在上抛 `ToolCalls` / `Done` 之前 `ch <- StreamEvent{Usage: &Usage{InputTokens: acc.Usage.InputTokens, OutputTokens: acc.Usage.OutputTokens}}`（`acc.Usage` 仅在流结束后完整）。
- 历史含工具交互时 thinking 已自动关闭（ch03 既有逻辑，line 52），多轮续答沿用，无需改动。

**openai.go：**
- 请求构造增 `params.StreamOptions = openai.ChatCompletionStreamOptionsParam{IncludeUsage: openai.Bool(true)}`（不开则流式 Usage 为空）。
- 系统提示：`toOpenAIMessages` 接收 `suffix`，把首条 system 消息文本由 `prompt.SystemPrompt` 改为拼接 `suffix`（非空时 `+"\n\n"+suffix`）。
- 用量：流结束后读 `acc.Usage`（`CompletionUsage`），`ch <- StreamEvent{Usage: &Usage{InputTokens: acc.Usage.PromptTokens, OutputTokens: acc.Usage.CompletionTokens}}`。

### internal/tool（扩展）

- `Tool` 接口加 `ReadOnly() bool`；6 个工具各加一行实现（read/glob/grep 返回 true，write/edit/bash 返回 false）。
- `Registry.ReadOnlyDefinitions()`：仿 `Definitions()`，仅收 `tools[name].ReadOnly()==true` 的项，保持注册顺序。
- `Registry.IsReadOnly(name)`：`t, ok := Get(name); return ok && t.ReadOnly()`（未知工具 false）。
- `Execute`、`DefaultTimeout`、6 工具的执行逻辑均不变。

### internal/conversation（扩展）

```go
// LastRole 返回最后一条消息的角色；空历史返回 ""。
func (c *Conversation) LastRole() string
```
其余沿用 ch03。

### internal/prompt（扩展）

```go
// PlanModeReminder：Plan Mode 系统提示后缀，拼接到 SystemPrompt 之后。
const PlanModeReminder = "You are currently in PLAN MODE. You may use ONLY the read-only tools " +
  "(read_file, glob, grep) to investigate the codebase. You must NOT write files, edit files, " +
  "or run shell commands. Produce a clear, step-by-step plan for the task, then stop and wait for " +
  "the user to approve it with /do before doing any work."

// ExecuteDirective：/do 注入的用户消息——指示模型按上文已确认的计划开始执行，可使用全部工具。
const ExecuteDirective = "请按上面的计划开始执行。"
```
`SystemPrompt` 增补一句 Agent 循环约定（追加到现有文案）：`"Keep using tools across multiple steps to make progress, and only give your final concise answer once the task is complete."`（中文项目里保持英文 system prompt 风格，与 ch03 现有 `SystemPrompt` 一致）。

### internal/tui（扩展）**Model 新增字段（tui.go）：**
- `mode agent.Mode`——当前模式（默认 `ModeNormal`），`/plan`、`/do` 切换，跨轮保持。
- `iter int`——当前迭代轮次（进度显示），每轮 `Iter` 事件更新，`finishTurn` 归零。
- `usageIn, usageOut int64`——会话累计 token 用量，每个 `Usage` 事件累加。
- `curTools []toolDisplay`——替换 ch03 的单个 `curTool *toolDisplay`，支持并发批多个在执行的工具行。
- `turnCancel context.CancelFunc`——本轮取消函数（派生自 `m.ctx`），Esc / Ctrl+C 触发；`m.ctx`/`m.cancel` 仍为程序级。

**submit（stream.go）：**
1. `/exit` → 退出（沿用）。
2. `/plan` → `m.mode = agent.ModePlan`；提交一行提示块到 scrollback（如「已进入计划模式（只读工具）」）；回空闲态。
3. `/do` → `m.mode = agent.ModeNormal`；`m.conv.AddUser(prompt.ExecuteDirective)`；走与普通提交相同的启动流程（不把 `/do` 本身入历史）。
4. 普通文本 → `m.conv.AddUser(text)`。
5. 启动：`turnCtx, m.turnCancel = context.WithCancel(m.ctx)`；`m.events = agent.New(m.provider, m.registry).Run(turnCtx, m.conv, m.mode)`；`m.state = stateStreaming`；`m.iter = 0`。用户输入块先 `tea.Println` 再泵事件（沿用 ch03 `tea.Sequence`）。

**updateStreaming（stream.go）分派顺序：**
`Err` → `Tool` → `Usage`（累加 `usageIn/usageOut`，重挂泵）→ `Notice`（`tea.Println` 一行灰色系统提示块，重挂泵）→ `Iter>0`（`m.iter = Iter`，重挂泵）→ `Done` → `Text`（累积 `curReply`，重挂泵）。
- `Tool.PhaseStart`：若 `curReply` 非空先把 preamble 提交 scrollback 并清空；`m.curTools = append(m.curTools, toolDisplay{name,args})`；重挂泵。
- `Tool.PhaseEnd`：**FIFO 弹出队首** `curTools[0]`（因 agent 保证 PhaseStart 与 PhaseEnd 都按调用序发出，结束序 == 入队序，弹首即对应工具，无需按 name 匹配，重名工具也不会错位）；用其 args 定型工具行，`tea.Sequence(tea.Println(toolLine), tea.Println(toolResultSummary), waitForEvent)`。

**按键（tui.go Update，全局优先）：**
- `ctrl+c`：`stateStreaming` → `m.turnCancel()`（取消本轮，不退出），重挂泵等 Done；否则 `m.cancel(); tea.Quit`（退出）。
- `esc`：`stateStreaming` → `m.turnCancel()`；其余忽略。

**view.go：**
- `statusBar`：左侧在 provider 名后附模式标记（`ModePlan` 显示「PLAN」徽标）；右侧在 model 名旁附累计用量 `↑{in} ↓{out} tok`（数值用紧凑格式，如 `1.2k`）。保持单行。
- 流式动态区：`curTools` 非空时逐行渲染 `● name(args)` + Running…（多个并发工具多行）；否则渲染「Imagining… (Ns · 第 N 轮)」（`m.iter>0` 时附轮次）。
- `toolLine` / `toolResultSummary` 沿用 ch03。

**finishTurn（stream.go）：** 清 `curReply`、`curTools=nil`、`events=nil`、`iter=0`、`turnCancel=nil`，回 `stateIdle`（`mode`、`usageIn/usageOut` 不清——跨轮保持）。

## 模块交互

```
用户提交 /do 或普通文本
  └─ tui.submit:
       ├─ /plan → mode=Plan，回 idle
       ├─ /do   → mode=Normal; conv.AddUser(ExecuteDirective)
       ├─ 文本  → conv.AddUser(text)
       └─ turnCtx,turnCancel = WithCancel(ctx); events = agent.New(...).Run(turnCtx, conv, mode)
            └─ agent.Run (goroutine, ReAct 循环):
                 for iter:
                   ├─ emit Iter
                   ├─ 请求: provider.Stream(turnCtx, conv.Messages(), defs(mode), suffix(mode))
                   │     └─ 适配器: 注入 tools + (SystemPrompt+suffix) → 流式拼接
                   │          → StreamEvent{Text…}/{ToolCalls}/{Usage}/{Done|Err}
                   │     → agent 转发 Text(preamble)、收集 calls、记录 usage
                   ├─ emit Usage
                   ├─ 无 calls → conv.AddAssistant(final); emit Done; 停
                   └─ 有 calls:
                        ├─ conv.AddAssistantWithToolCalls(preamble, calls)
                        ├─ executeBatched: 连续只读并发 / 有副作用串行
                        │     （Start 事件按序 → 执行 → End 事件按序）
                        ├─ conv.AddToolResults(results)
                        └─ 下一轮 iter
  └─ tui.updateStreaming: Text→curReply；Tool→curTools/scrollback；Usage→累加；
       Iter→m.iter；Notice→灰提示；Done→提交最终答复+finishTurn
  └─ Ctrl+C / Esc（streaming）→ turnCancel() → Run 收尾历史 → 关 channel → finishTurn → idle
```

并发模型：`conv` 任一时刻只被 `Run` 的主 goroutine 触碰（`submit` 在交给 `Run` 前 `AddUser`，之后不再触碰；执行批的工作 goroutine 只写各自 `results[k]`，不碰 `conv`）。`Messages()` 返回副本。TUI 仅按事件渲染。满足 N2/N6。

## 文件组织

```
gcode/
├── internal/
│   ├── llm/
│   │   ├── provider.go     — 修改：新增 Usage；StreamEvent 加 Usage；Stream 加 systemSuffix 形参
│   │   ├── anthropic.go    — 修改：effectiveSystem(suffix)；流结束上抛 acc.Usage
│   │   └── openai.go       — 修改：StreamOptions.IncludeUsage；toOpenAIMessages 拼 suffix；上抛 acc.Usage
│   ├── tool/
│   │   ├── tool.go         — 修改：Tool 接口加 ReadOnly()
│   │   ├── registry.go     — 修改：ReadOnlyDefinitions、IsReadOnly
│   │   └── {read_file,write_file,edit_file,bash,glob,grep}.go — 修改：各加 ReadOnly()
│   ├── agent/
│   │   ├── agent.go        — 重写：ReAct 循环、Mode、executeBatched、Usage/Iter/Notice 事件、历史收尾
│   │   └── agent_test.go   — 扩展：多轮 fake provider（[][]StreamEvent 多次 Stream）、并发分批、停止条件、Plan 工具集
│   ├── conversation/
│   │   ├── conversation.go — 修改：LastRole()
│   │   └── conversation_test.go — 扩展：LastRole 断言
│   ├── prompt/
│   │   └── prompt.go       — 修改：PlanModeReminder、ExecuteDirective；SystemPrompt 增循环约定
│   └── tui/
│       ├── tui.go          — 修改：Model 增 mode/iter/usage/curTools/turnCancel；按键拆分 Esc/Ctrl+C
│       ├── stream.go       — 修改：submit 识别 /plan /do + per-turn ctx；updateStreaming 处理 Usage/Iter/Notice/多工具
│       └── view.go         — 修改：状态栏模式徽标+累计用量；动态区迭代轮次+多并发工具行
└── cmd/smoke/main.go       — 修改：调用 agent.Run 处补 mode 实参（agent.ModeNormal）
```

> 注：`cmd/gcode/main.go` 已在 ch03 注入 registry，ch04 无需改动；`mode` 状态存于 TUI，不经 main。

### 签名变更的调用方清单（实测核对，确保编译不漏）

ch04 改了两个签名，必须同步所有调用方/实现方，否则编译断：

- **`Provider.Stream` 增 `systemSuffix string`（第 4 形参）**：
  - 实现方：`internal/llm/anthropic.go`、`internal/llm/openai.go`。
  - 调用方：`internal/agent/agent.go` 的 `streamOnce`（唯一直接调用方）。
  - 测试实现方：`internal/agent/agent_test.go` 的 `fakeProvider.Stream`（也实现该接口，签名须同步）。
  - **`cmd/smoke/main.go` 不直接调 `Stream`**（它走 `agent.Run`），无需为 systemSuffix 改动。
- **`Agent.Run` 增 `mode Mode`（第 3 形参）**：
  - 调用方：`internal/tui/stream.go`（`submit` 内）、`cmd/smoke/main.go`（line 25 `a.Run(ctx, conv)`）、`internal/agent/agent_test.go`（各用例）。三者都要补 `mode` 实参（smoke / 旧用例传 `agent.ModeNormal`）。

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Loop 放哪 | 重写 `agent.Run` 为循环，签名加 `mode` | 循环编排天然属 agent 包；TUI 维持纯渲染器。Run 已返回事件 channel，循环只是把单轮的两次 `streamOnce` 推广为 `for`，改动收敛在一个包。 |
| 不用 SDK 内置 tool-runner | 坚持手写循环 + stable streaming | 沿用 ch03 决策；自写循环才能精确控制停止条件、保序分批、取消与历史收尾，SDK 的自动 runner 把这些黑盒化。 |
| 停止条件之「连续未知工具」 | 连续 `maxUnknownRun=3` 轮「整轮只产生未知工具调用」即停 | 单次未知工具靠 registry 的「未知工具」结构化错误回灌即可让模型纠偏；只有连续多轮全错才说明在对幻觉工具空转，需兜底。混入任一已注册工具即重置计数（视为有进展）。 |
| 迭代上限值 | `maxIterations=25`，内置常量 | 兜底安全网，避免失控烧 token；25 足够覆盖正常多步任务。spec 明确不配置化，与 ch03 超时不配化一致。 |
| 并发分批粒度 | 「连续只读」合批并发，有副作用单个串行，保持调用序 | 用户选定的「保序分批」：read 之后的 write 不会被提前；相邻只读才并发加速。`bash` 保守归有副作用（可含任意写操作）。 |
| 并发的事件顺序 | 开始事件按序、结束事件按序，并发只在执行环节 | 满足 N3（scrollback 不交错）：UI 看到的工具行顺序始终是模型调用序；并发对用户透明，只体现为更快。每个 worker 只写自己下标的 `results[k]`，无竞争（N6）。 |
| 取消机制 | per-turn `context.WithCancel(m.ctx)`；Esc / Ctrl+C(streaming) 取消，Ctrl+C(idle) 退出 | 程序级 `m.ctx` 不动，新增每轮子 ctx 才能「取消本轮但不退程序」。取消即触发 streamOnce/工具 ctx 的 Done，自然停。 |
| 取消后历史一致 | 已发起工具补「已取消」结果 + `ensureAssistantTail` 收尾 | F6：取消可能停在「assistant 含 tool_use 但缺 tool_result」或「user 之后无 assistant」处；补齐工具结果 + 保证 assistant 文本尾巴，下一轮请求才不会因悬空 tool_use / 连续同角色被 API 拒（400）。 |
| 用量提取位置 | 适配器在流结束后从累加器读 `acc.Usage` 并经 `StreamEvent{Usage}` 上抛 | 两 SDK 的流式 usage 都只在流结束的累加器里完整（Anthropic `acc.Usage`、OpenAI 需 `IncludeUsage` 后读 `acc.Usage`）；逐 delta 不含。统一在 Done 前发一次。 |
| 累计用量口径 | 状态栏显示「会话累计计费 token」= 每轮 input+output 之和 | 多轮 Loop 每轮都重发完整历史，各轮 input 重复计费；按轮累加正是实际消耗/成本口径，对用户最有意义。 |
| Plan Mode 系统提示注入 | `Provider.Stream` 加 `systemSuffix string` 形参 | 系统提示在适配器内注入，要让计划态约束生效必须穿过 Stream。加一个字符串形参最小且显式；备选「请求 options struct」更可扩展但改动面更大，YAGNI 下不引入。 |
| Plan Mode 工具集 | 计划态只注入 `ReadOnlyDefinitions()` | 物理上不给模型写/执行工具，即便提示被忽略也无法改动；只读分类靠 `Tool.ReadOnly()`。 |
| `/do` 语义 | 切回 Normal + 注入 `ExecuteDirective` 用户消息 + 立即启动 Loop | 用户选定「切回全工具并立即执行」；复用已在历史里的计划，`/do` 不入历史，只把执行指令作为用户消息驱动模型开干。 |
| 模式状态存放 | 存于 TUI `Model`，不进 `Conversation` | `Conversation` 是历史、`Messages()` 返回副本，放不住可变模式；模式是会话级 UI 状态，跨轮保持，归 TUI 最自然。 |
| 多并发工具的 UI | `curTools []toolDisplay` 取代单个 `curTool` | 并发批同时有多个工具在跑，动态区需多行展示；结束事件按序逐个落 scrollback。 |
| 进度事件 | 每轮起始 emit `Event{Iter:n}`，UI 显示「第 N 轮」 | F9 让用户感知多轮推进；用非零 `Iter` 字段分派，与 ch03 的零值分派惯例一致。 |
| 通知 vs 历史 | 上限/未知工具的提示同时 emit `Notice`（UI 灰字）并写入 assistant 历史 | UI 要让用户看到为何停；写入历史是为满足 `ensureAssistantTail`（角色交替），二者用同一文案，避免历史里留空 assistant 回合。 |
````

````markdown
# Agent Loop Tasks

> 基于已批准的 spec.md + plan.md。任务有序，每步留绿编译。验证一律「先跑命令看输出，再下结论」。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `internal/llm/provider.go` | 新增 Usage 类型；StreamEvent 加 Usage；Stream 加 systemSuffix 形参 |
| 修改 | `internal/llm/anthropic.go` | effectiveSystem(suffix)；流结束上抛 acc.Usage |
| 修改 | `internal/llm/openai.go` | StreamOptions.IncludeUsage；toOpenAIMessages 拼 suffix；上抛 acc.Usage |
| 修改 | `internal/tool/tool.go` | Tool 接口加 ReadOnly() |
| 修改 | `internal/tool/registry.go` | ReadOnlyDefinitions、IsReadOnly |
| 修改 | `internal/tool/{read_file,write_file,edit_file,bash,glob,grep}.go` | 各加 ReadOnly() |
| 修改 | `internal/conversation/conversation.go` | LastRole() |
| 修改 | `internal/prompt/prompt.go` | PlanModeReminder、ExecuteDirective；SystemPrompt 增循环约定 |
| 重写 | `internal/agent/agent.go` | ReAct 循环、Mode、executeBatched、Usage/Iter/Notice 事件、历史收尾 |
| 重写 | `internal/agent/agent_test.go` | 多轮 fake provider、并发分批、停止条件、Plan 工具集 |
| 修改 | `internal/conversation/conversation_test.go` | LastRole 断言 |
| 修改 | `internal/tui/{tui,stream,view}.go` | mode、per-turn ctx、Esc/Ctrl+C、/plan /do、Usage/Iter/Notice/多工具、状态栏、动态区 |
| 修改 | `cmd/smoke/main.go` | agent.Run 调用处补 mode 实参（ModeNormal）|

## T1: llm 新增 Usage 类型（纯增量）**文件：** `internal/llm/provider.go`
**依赖：** 无
**步骤：**
1. 新增类型 `Usage{InputTokens, OutputTokens int64}`（带中文注释：本轮输入/输出 token 数）。
2. 给 `StreamEvent` 增字段 `Usage *Usage`（指针，非空即本轮用量），更新 `StreamEvent` 文档注释补「Usage 非空：本轮 token 用量，Done 之前一次性发出」。

**验证：** `go build ./...` 通过（纯增字段，向后兼容，不改签名）。

## T2: tool 只读分类**文件：** `internal/tool/tool.go`、`internal/tool/registry.go`、`internal/tool/{read_file,write_file,edit_file,bash,glob,grep}.go`
**依赖：** 无
**步骤：**
1. `tool.go`：`Tool` 接口加 `ReadOnly() bool`（注释：true=只读，可并发执行 & Plan Mode 放行）。
2. 6 个工具各加一行方法：`read_file`/`glob`/`grep` → `func (t xxxTool) ReadOnly() bool { return true }`；`write_file`/`edit_file`/`bash` → `return false`。
3. `registry.go`：
   - `ReadOnlyDefinitions() []llm.ToolDefinition`：仿 `Definitions()` 按 order 遍历，仅收 `r.tools[name].ReadOnly()==true` 的项。
   - `IsReadOnly(name string) bool`：`t, ok := r.Get(name); return ok && t.ReadOnly()`。

**验证：** `go build ./internal/tool/...` 通过；`go test ./internal/tool/...` 不回归（接口加方法后 6 工具均实现，编译即证明完整）。

## T3: conversation.LastRole**文件：** `internal/conversation/conversation.go`、`internal/conversation/conversation_test.go`
**依赖：** 无
**步骤：**
1. `conversation.go`：新增 `LastRole() string`——空历史返回 `""`，否则返回 `c.messages[len-1].Role`。
2. `conversation_test.go`：补一条断言——空会话 `LastRole()==""`；`AddUser` 后 `==RoleUser`；`AddToolResults` 后 `==RoleTool`；`AddAssistant` 后 `==RoleAssistant`。

**验证：** `go test ./internal/conversation/...` 通过。

## T4: prompt 计划态提示与循环约定**文件：** `internal/prompt/prompt.go`
**依赖：** 无
**步骤：**
1. `SystemPrompt` 增补一句 Agent 循环约定：持续调用工具推进任务，直到任务完成后再给出最终简洁答复（不要每步都停下来等用户）。
2. 新增 `const PlanModeReminder`：计划模式系统后缀——当前为计划模式，只能用只读工具（读文件 / 按模式找文件 / 搜内容）调研并产出一份分步执行计划；不得写文件、改文件或执行命令；计划写完即停，等用户用 `/do` 批准后再执行。
3. 新增 `const ExecuteDirective = "请按上面的计划开始执行。"`。
4. （可选）`ReadyHint` 增提 `/plan`、`/do`。

**验证：** `go build ./internal/prompt/...`；`go test ./...` 不回归。

## T5: llm Stream 加 systemSuffix + 用量上抛**文件：** `internal/llm/provider.go`、`internal/llm/anthropic.go`、`internal/llm/openai.go`、`internal/agent/agent.go`（临时补参）
**依赖：** T1
**步骤：**
1. `provider.go`：`Provider.Stream` 签名改为 `Stream(ctx, msgs []Message, tools []ToolDefinition, systemSuffix string) <-chan StreamEvent`，更新接口注释说明 systemSuffix 语义（非空时拼到内置 SystemPrompt 之后）。
2. `anthropic.go`：
   - `Stream` 加 `systemSuffix` 形参；`params.System` 由硬编码改为 `effectiveSystem(systemSuffix)`——`suffix==""` 单块 `prompt.SystemPrompt`；非空时单块 `prompt.SystemPrompt+"\n\n"+suffix`。
   - 流正常结束（`stream.Err()==nil`）后、上抛 ToolCalls 与关闭 channel 前：`ch <- StreamEvent{Usage:&Usage{InputTokens:acc.Usage.InputTokens, OutputTokens:acc.Usage.OutputTokens}}`。
3. `openai.go`：
   - `Stream` 加 `systemSuffix`；`params.StreamOptions = openai.ChatCompletionStreamOptionsParam{IncludeUsage: openai.Bool(true)}`。
   - `toOpenAIMessages(msgs, systemSuffix)`：首条 system 消息文本 `prompt.SystemPrompt`，suffix 非空时 `+"\n\n"+suffix`（其调用处同步加实参）。
   - 流结束后：`ch <- StreamEvent{Usage:&Usage{InputTokens:acc.Usage.PromptTokens, OutputTokens:acc.Usage.CompletionTokens}}`。
4. `internal/agent/agent.go`：把现有 `streamOnce` 里唯一的 `provider.Stream(ctx, conv.Messages(), defs)` 调用补成 `..., defs, "")` 以匹配新签名——本步即让**非测试构建**保持绿（T6 会整体重写 agent.go）。

> 说明：`cmd/smoke/main.go` 走 `agent.Run`、不直接调 `Stream`，本步不动它（其 Run 调用在 T7 随 mode 形参一并更新）。`internal/agent/agent_test.go` 的 `fakeProvider.Stream` 也实现该接口，本步之后它会编译失败——这是预期的，T6 重写 agent_test 时一并补 `systemSuffix` 形参；因此本步**不要**跑 `go test ./internal/agent/...`。

**验证：** `go build ./...` 通过（不含测试文件，绿）；`go vet ./internal/llm/...` 无告警；`go run ./cmd/gcode` 发一条纯文本回复正常（用量已随流上抛，旧 agent 暂未消费）。

## T6: agent ReAct 循环重写**文件：** `internal/agent/agent.go`、`internal/agent/agent_test.go`
**依赖：** T1, T2, T3, T4, T5
**步骤：**
1. `agent.go`：
   - 包注释改为「ReAct 循环编排」。
   - 类型：保留 `Phase`/`ToolEvent`/`Agent`/`New`；新增 `Usage{Input,Output int64}`、`Mode`(`const (ModeNormal Mode = iota; ModePlan)`）；`Event` 增字段 `Usage *Usage`、`Iter int`、`Notice string`。
   - 常量：按 plan「迭代、停止常量与提示文案」原样落 `maxIterations`/`maxUnknownRun` 与 `noticeMaxIter`/`noticeUnknownTools`/`noticeStreamErr`/`noticeCancelled`（文案以 plan 为准，T8 端到端按这些文案核对）。
   - `Run(ctx, conv, mode)`：按 plan「Run 算法」实现 `for iter` 循环——按 mode 取 `defs`(`Definitions`/`ReadOnlyDefinitions`) 与 `suffix`(`""`/`prompt.PlanModeReminder`)；emit Iter → streamOnce → emit Usage → 无工具自然完成 / 有工具 `AddAssistantWithToolCalls` → 统计 `unknownRun` → `executeBatched` → `AddToolResults`（无条件）→ **取消（!completed）最高优先级收尾** → 未知工具上限收尾 → 循环走完触达迭代上限收尾。
   - `streamOnce(ctx, conv, defs, suffix, ch) → (text, calls, usage, ok)`：`suffix` 为 ch04 新增形参，透传给 `provider.Stream`；转发 Text、收集 calls、记录 `ev.Usage`、Err 即发 `Event{Err}` 返回 `ok=false`。
   - `executeBatched(ctx, calls, ch) → (results, completed)`：保序分批——从 `i=0` 扫描，`IsReadOnly(calls[i])` 为真则吃最长连续只读区间 `[i,j)` 用 `sync.WaitGroup` **并发**（每 goroutine 内 `context.WithTimeout(ctx, tool.DefaultTimeout)` 后 `Execute`，只写自己下标 `results[k]`），否则**串行**单个；每段执行前判 `ctx.Err()` 取消则填 `noticeCancelled` 结果返 `completed=false`；事件「Start 按序、End 按序」（见 plan）。
   - 辅助：`allUnknown(calls)`（每个 call 用 `registry.Get` 判，全未注册才 true）、`ensureFinal`（沿用 ch03）、`ensureAssistantTail(conv, fallback)`、`finishCancelled(conv)`、`emit`/`argsPreview`（沿用 ch03）。
2. `agent_test.go`（**替换** ch03 的 `TestSingleRoundReadAndAnswer`/`TestSingleRoundLimit`——后者断言单轮已与 ch04 多轮矛盾）。`fakeProvider.Stream` 签名补 `systemSuffix string`（并在某用例里记录收到的 `tools`/`suffix` 供断言）；多轮靠 `scripts [][]StreamEvent` 逐次返回：
   - 场景 A（多轮链路 AC1）：脚本①返回 1 个 read_file 工具调用、脚本②返回纯文本 → 断言事件序列含 Iter=1、ToolStart/End、Iter=2、最终 Text、Done；`conv` 末尾为 assistant 文本，中间含 tool_use 回合 + RoleTool 回合。
   - 场景 B（迭代上限 AC3）：用「每次 Stream 都返回一个工具调用」的 fake（忽略脚本耗尽，恒返工具）→ 断言恰好 `maxIterations` 次请求后停（`fp.calls==maxIterations`）、收到 `Notice`(noticeMaxIter)、`conv.LastRole()==RoleAssistant`。
   - 场景 C（连续未知工具 AC4）：脚本连续返回未注册工具名 → 断言 `maxUnknownRun` 轮后停并 Notice(noticeUnknownTools)；另一用例在其间混入一个 read_file，断言计数重置、不提前停。
   - 场景 D（保序分批 AC8）：构造**自定义 registry**注册两个插桩工具——一个只读工具（`ReadOnly()==true`，Execute 内 `atomic` 记录「同时在跑的并发数」峰值、并 sleep 制造重叠）与一个有副作用工具（`ReadOnly()==false`，记录开始时刻）。脚本一轮返回 `[ro, ro, rw]` → 断言：两只读的并发峰值 ≥2（确实并发）、rw 的开始时刻晚于两只读完成、`AddToolResults` 写入历史的结果顺序与调用序一致（按结果内容/ID 比对，不依赖具体方法名）。
   - 场景 E（取消历史一致 AC9）：插桩工具在 Execute 中阻塞，测试侧在执行期间 `cancel()` per-turn ctx → 断言 `conv` 末尾配对合法（含 tool_results、最后是 assistant 文本 noticeCancelled），无悬空 tool_use；随后再追加一轮纯文本脚本能正常跑（角色交替未坏）。
   - 场景 F（Plan 工具集 AC13）：`Run(ctx, conv, ModePlan)` → 断言 fake 收到的 `tools` 仅含只读工具定义、`suffix==prompt.PlanModeReminder`。

**验证：** `go test ./internal/agent/...` 全通过；`go test -race ./internal/agent/...` 无竞争告警（覆盖并发分批，N6）。

## T7: tui 接入 Agent Loop + 收尾 Run 调用方**文件：** `internal/tui/tui.go`、`internal/tui/stream.go`、`internal/tui/view.go`、`cmd/smoke/main.go`
**依赖：** T4, T6
**说明：** T6 改了 `Agent.Run` 签名（加 `mode`），其调用方 `tui/stream.go` 与 `cmd/smoke/main.go` 在此步同步更新——本步完成后 `go build ./...` 才在**仓库级**重新转绿（T6 后只保证 agent 包及其测试绿）。
**步骤：**
1. `tui.go`：
   - `Model` 新增字段：`mode agent.Mode`、`iter int`、`usageIn int64`、`usageOut int64`、`curTools []toolDisplay`（移除单个 `curTool`）、`turnCancel context.CancelFunc`。
   - `Update` 按键拆分：`ctrl+c` → `stateStreaming` 时 `m.turnCancel()`（不退出，重挂泵等结束）/ 否则 `m.cancel(); tea.Quit`；新增 `esc` → `stateStreaming` 时 `m.turnCancel()`。
2. `stream.go`：
   - `submit`：识别 `/exit`（退出）、`/plan`（`mode=ModePlan`、提示块、回 idle）、`/do`（`mode=ModeNormal`、`conv.AddUser(prompt.ExecuteDirective)`、走启动流程）、普通文本（`conv.AddUser`）。启动处：`turnCtx, m.turnCancel = context.WithCancel(m.ctx)`；`m.events = agent.New(m.provider,m.registry).Run(turnCtx, m.conv, m.mode)`；`m.iter=0`；`m.state=stateStreaming`。
   - `updateStreaming` 按 plan 分派顺序处理 `Err`/`Tool`/`Usage`(累加 usageIn/usageOut)/`Notice`(灰提示块)/`Iter`(set m.iter)/`Done`/`Text`；`Tool.PhaseStart` 追加 `curTools`（首个工具前先提交 preamble）、`PhaseEnd` 从 `curTools` 移除队首匹配并 `tea.Sequence` 提交工具行+结果摘要。
   - `finishTurn`：清 `curReply`/`curTools`/`events`/`iter`/`turnCancel`，回 `stateIdle`（保留 `mode`、`usageIn/usageOut`）。
3. `view.go`：
   - `statusBar`：左侧 provider 名后在 `ModePlan` 时附「PLAN」徽标；右侧 model 名旁附 `↑{in} ↓{out} tok`（紧凑数字，如 `1.2k`）。
   - 流式动态区：`curTools` 非空逐行渲染 `● name(args)` Running…；否则「Imagining… (Ns · 第 N 轮)」（`m.iter>0` 附轮次）。
4. `cmd/smoke/main.go`：`a.Run(ctx, conv)` 调用补 mode 实参 → `a.Run(ctx, conv, agent.ModeNormal)`（保持其调试用途，不需感知 plan/取消）。

**验证：** `go build ./...`（仓库级转绿）；`go vet ./...` 无告警；`gofmt -l internal/tui cmd/smoke` 无输出。

## T8: 全量验证与端到端冒烟**文件：** 无（验证）
**依赖：** T1–T7
**步骤：**
1. `gofmt -l .`（goimports 分组正确）；`go vet ./...`；`go test ./...`；`go test -race ./internal/agent/... ./internal/tool/...`。
2. 端到端（openai 兼容端点，用 `.gcode/config.yaml`）：
   - 多轮（AC1）：问「读 `docs/ch03/spec.md`，再据其内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ 观察 read_file → write_file 跨多轮自动连环、状态栏用量增长、动态区轮次递增、最终答复。
   - 取消（AC10）：发一个会跑多步的任务，中途按 Esc / Ctrl+C → 回空闲态不退出 → 再正常发一条继续对话（验证历史未坏）。
   - 流出错（AC5）：临时改坏 base_url 或断网发一条 → 错误提示、程序不退出、改回后继续。
   - Plan Mode（AC13）：`/plan` → 问「给登录功能加单测的方案」→ 观察只出现 read/glob/grep 类工具与计划文本、无写/执行 → `/do` → 切回全工具按计划执行。
3. （可选）若有 anthropic 配置，重复多轮场景验证跨协议一致（AC14）。

**验证：** 全部命令通过、端到端各场景符合预期；密钥不回显（通读输出，AC/N7）。

## 执行顺序

```
T1 ─┬─ T5 ─┐
T2 ─┤      │
T3 ─┼──────┼─ T6 ─┬─ T7 ─┐
T4 ─┘      │      │      │
           └──────┘      └─ T8
```
（T1–T4 互相独立可并行；T5 依赖 T1；T6 依赖 T1/T2/T3/T4/T5；T7 依赖 T4/T6；T8 收尾全部。）
````

```markdown
# Agent Loop Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为；括号内为验证方式与对应需求。

## 实现完整性
- [ ] 多轮自动连环：需要连续两步工具的任务，Agent 无需中途催促即自动多轮执行工具直到给出最终答复（验证：`go run` 跑「读 A 文件 → 据内容新建 B 文件」，观察 read_file 与 write_file 跨多轮依次出现、最终答复）。(AC1/F1)
- [ ] 自然完成停止：模型给出无工具调用的纯文本即停（验证：agent_test 场景 A 断言收到最终 Text + Done，循环不再发起请求）。(AC2/F2)
- [ ] 迭代上限兜底：模型反复调工具时达到 `maxIterations` 即停并提示，不无限循环（验证：agent_test 场景 B 断言恰好上限轮后停 + Notice(noticeMaxIter)）。(AC3/F2)
- [ ] 连续未知工具停止：连续 `maxUnknownRun` 轮只产生未知工具调用即停；混入已注册工具则计数重置（验证：agent_test 场景 C 两路断言）。(AC4/F2)
- [ ] 流出错恢复：provider 流出错时停止本轮、发 Err、程序不退出（验证：端到端临时改坏 base_url 发一条，观察错误块 + 仍可继续；agent_test 注入 Err 脚本断言收到 Err 后停）。(AC5/F2)
- [ ] 事件流完备：Agent 对外事件含文本 / 工具开始 / 工具结束 / Usage / Iter / Notice / Done / Err（验证：agent_test 断言一次多轮运行收集到的事件类型集合覆盖上述各类；端到端跑多轮任务，界面实时显示文本增量、工具进度、轮次、用量、最终答复，证明界面所需信息均来自事件流）。(AC6/F3)
- [ ] 流式收集双路：文本实时显示的同时，完整工具调用（拼齐 JSON 参数）被收集用于下一轮（验证：agent_test 断言 ToolCall.Input 完整可解析；端到端工具行参数与请求一致）。(AC7/F4)
- [ ] 保序分批并发：一次回复含多个工具时，连续只读并发执行、有副作用串行，结果按原序回灌（验证：agent_test 场景 D 用插桩工具断言两只读的执行时间窗重叠（并发峰值≥2）、有副作用工具在其后开始、最终写入历史的工具结果顺序与模型调用序一致——按结果内容/ID 比对，与函数名无关）。(AC8/F5/N6)
- [ ] 取消历史一致：执行中取消后历史配对合法（有 tool_results、末尾 assistant 文本、无悬空 tool_use）（验证：agent_test 场景 E 断言 conv 序列；端到端取消后再发一条不报 400）。(AC9/F6)
- [ ] 用户取消：流式态 Esc 或 Ctrl+C 中断本轮回空闲态、不退出；空闲态 Ctrl+C 退出（验证：端到端各按一次观察行为）。(AC10/F7)
- [ ] 用量展示：状态栏显示会话累计 token（输入/输出），随轮次增长更新（验证：端到端跑多轮观察状态栏数值递增）。(AC11/F8)
- [ ] 进度展示：流式态动态区显示当前迭代轮次（验证：端到端跑多轮任务观察「第 N 轮」递增）。(AC12/F9)
- [ ] Plan Mode：`/plan` 后只出现只读工具与计划文本、无写/执行；`/do` 切回全工具并立即按计划执行（验证：端到端 Plan Mode 场景；agent_test 场景 F 断言 ModePlan 下 fake 收到的 tools 仅只读）。(AC13/F10)

## 集成
- [ ] 跨协议一致：anthropic 与 openai（含兼容 base_url）跑同一多轮任务，触发/执行/回灌/用量/取消行为一致（验证：两种配置各跑多轮场景）。(AC14/F11/N3)
- [ ] 多轮历史正确携带：每轮 assistant(tool_use) 回合 + tool_result 回合按序入历史并被下一轮请求携带（验证：agent_test 断言 conv 末尾序列；或抓请求体见历史增长）。(F6)
- [ ] 界面不阻塞：多轮循环与工具执行（含并发批）期间 spinner / 轮次 / 计时持续刷新（验证：跑含稍慢 bash 的任务，观察界面不冻结）。(N2)
- [ ] scrollback 顺序正确：跨多轮 preamble → 工具行 → 结果摘要 → 最终答复按序出现不交错，并发批的工具行按模型调用序排列（验证：跑一个含并发只读批 + 后续写的多轮任务，回滚 scrollback 肉眼核对各块严格按发生顺序连续、无交错、并发工具行顺序==调用序）。(N3)
- [ ] 结果体量受控：大文件 / 长输出 / 海量命中被工具级上限截断标注 `[truncated]`，多轮累积不撑爆（验证：多轮中读大文件 / 跑长输出命令观察截断）。(N4)
- [ ] 取消无泄漏：取消后无挂起 goroutine / 无阻塞 channel（验证：`go test -race ./internal/agent/...` 含取消用例（场景 E）通过；端到端反复触发取消后继续对话多次，进程内存/句柄稳定不增长）。(N5/N6)
- [ ] 系统提示体现 Agent 循环：问「你能做什么」答复体现可多步使用工具完成任务（验证：发一条询问观察答复）。(F3)

## 编译与测试
- [ ] `go build ./...` 无错误。
- [ ] `go vet ./...` 无告警。
- [ ] `go test ./...` 通过（config、conversation、tool、agent 单测）。
- [ ] `go test -race ./internal/agent/... ./internal/tool/...` 无竞争告警。(N6)
- [ ] `gofmt -l .` 无输出（格式合规，goimports 分组正确）。(N8)
- [ ] 密钥不回显：对话区与任何输出均不出现 api_key（验证：通读运行输出、检索无明文 key）。(N7)

## 端到端场景
- [ ] 场景 1（多轮连环）：openai 兼容端点 → 「读 `docs/ch03/spec.md`，再据内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ read_file → write_file 跨多轮自动出现 → 状态栏用量增长、动态区轮次递增 → 最终答复 → /exit 无残留。
- [ ] 场景 2（用户取消）：发一个多步任务，中途按 Esc（再试 Ctrl+C）→ 回空闲态不退出 → 再正常发一条继续对话（历史未坏，无 400）。
- [ ] 场景 3（流出错恢复）：临时改坏 base_url 发一条 → 错误块 + 程序不退出 → 改回后继续正常对话。
- [ ] 场景 4（Plan Mode）：`/plan` → 问一个改动类需求 → 只出现 read/glob/grep + 计划文本、无写/执行 → `/do` → 切回全工具并按计划执行（出现 write/edit/bash）。
- [ ] 场景 5（跨协议，若有 anthropic 配置）：切到 anthropic 配置重跑场景 1 → 多轮行为与 openai 一致。
- [ ] 场景 6（迭代上限）：主要由 agent_test 场景 B 确定性验证；可选手动复现——临时把 `maxIterations` 改小（如 3）跑一个会多步调工具的任务，观察第 3 轮后停并显示 `noticeMaxIter`、之后仍可继续对话。
- [ ] 场景 7（连续未知工具）：主要由 agent_test 场景 C 确定性验证；可选手动复现——在 system prompt 临时引导模型调用一个不存在的工具名，观察连续 `maxUnknownRun` 轮后停并显示 `noticeUnknownTools`、之后仍可继续对话。
```



### Python

```markdown
# Agent Loop Spec## 背景ch03 给 GCode 装上了工具系统：模型能读写改文件、执行命令、按模式找文件、搜代码内容。但编排是**单轮闭环**——请求#1 拿到一批工具调用 → 执行 → 结果回灌 → 请求#2 出最终答复就停，且续答里模型再次请求的工具被**直接丢弃**。模型只能「一步一停」，复杂任务（读完 A 才知道要改 B）得用户反复催。

ch04 给 GCode 装上 **Agent Loop**：模型自主循环——想 → 调工具 → 看结果 → 边做边调整，直到任务完成。从被动应答变成能自主干活的 Agent。这是从「能用工具」到「会自己干」的关键一跃。

## 目标- **ReAct 循环**：一轮轮调 LLM、执行工具、结果回血，直到模型不再请求工具。
- **多种停止条件**：自然完成、迭代上限（兜底安全网）、用户取消、连续请求未知工具、流出错。
- **异步事件流**：Agent 吐出文本 / 工具调用 / 工具结果 / Token 用量 / 迭代进度等事件，让 Agent 与界面彻底解耦。
- **流式收集双路**：一边实时把文本增量推给界面，一边攒出完整响应（含工具调用）供循环判断。
- **保序分批并发**：一次回复的多个工具调用按安全性分批——连续只读并发执行，有副作用串行执行，保持模型给出的相对顺序。
- **Plan Mode 两段式**：`/plan` 只放开只读工具让模型先出计划；`/do` 切回全工具并立即按计划执行。

## 功能需求

- F1: ReAct 主循环编排
  替换 ch03 的单轮闭环。每一轮：带工具定义发起请求 → 流式收集本轮响应 → 若模型请求了工具则执行并把结果回灌进历史，进入下一轮；若模型给出无工具调用的纯文本，则该文本即最终答复，循环结束。不再丢弃续答里的工具调用。

- F2: 多种停止条件
  循环在以下任一条件下停止，每种都干净收尾（对话历史保持合法 + 给界面明确信号）：
  1. 自然完成——模型回复不含工具调用，纯文本即最终答复。
  2. 迭代上限——达到内置上限兜底，避免失控；触顶时给出提示并停。
  3. 用户取消——见 F7。
  4. 连续未知工具——模型连续多轮只请求注册中心不存在的工具达阈值即停，避免对幻觉工具空转。
  5. 流出错——provider 流返回错误，停止本轮并提示，不崩溃、不中断会话。

- F3: 异步事件流（Agent ↔ 界面解耦）
  Agent 对外只吐事件，界面只消费事件、不感知循环内部细节。事件涵盖：文本增量、工具调用开始、工具调用结束（结果摘要 + 是否错误）、Token 用量、迭代进度、本轮结束、错误。

- F4: 流式收集双路
  每轮请求的流式响应走双路：一路把文本增量实时推给事件流（界面即时显示），一路累积完整文本并拼接出完整工具调用（含分片到达的 JSON 参数），供循环判断下一步。

- F5: 保序分批并发执行
  工具区分「只读 / 有副作用」两类。一次回复的多个工具调用按模型给出的顺序扫描：连续的只读调用合并为一个并发批并行执行，遇到有副作用调用则单独串行执行，保持整体相对顺序。批内并发完成后，结果按原始调用顺序回灌。每个工具仍受 per-tool 超时约束（沿用 ch03）。

- F6: 结果回灌与历史一致
  每轮的 assistant 回合（含工具调用）与工具结果回合按序写入对话历史，下一轮请求携带完整历史。任何提前终止（取消 / 上限 / 未知工具 / 出错）后，对话历史都保持合法——工具调用与结果配对、角色交替不被破坏，会话可继续。被取消时为已发起但未完成的工具调用补「已取消」结构化结果。

- F7: 用户取消本轮
  流式态下 Esc 或 Ctrl+C 中断当前 Loop：停止后续迭代、回到空闲态、不退出程序；空闲态 Ctrl+C 退出程序。中断后历史保持合法（见 F6），可继续对话。

- F8: Token 用量统计
  从 provider 流式响应中提取每轮的 token 用量（输入 / 输出），跨轮累加为会话累计量，在状态栏展示。

- F9: 迭代进度展示
  流式态动态区展示当前迭代轮次，让用户感知 Agent 正在多轮推进。

- F10: Plan Mode 两段式
  `/plan` 进入计划模式：仅注入只读工具定义 + 计划态系统提示（让模型先产出计划、不动手改动）；`/do` 切回全工具模式并立即用一条内置提示触发模型按上文计划执行。模式跨轮保持，直到再次切换。

- F11: 跨协议一致
  Anthropic 与 OpenAI（含兼容 base_url）两协议都跑通完整 Loop——多轮工具调用、用量提取、取消行为一致。

## 非功能需求

- N1: 工具执行超时——每个工具执行仍受 per-tool 超时约束（沿用 ch03 内置 30s，不可配）；超时以结构化结果回灌，不中断循环。
- N2: 界面不阻塞——多轮循环、工具执行（含并发批）期间界面持续响应，spinner、迭代进度、计时正常刷新，不冻结。
- N3: scrollback 顺序正确——跨多轮的 preamble 文本、工具行、结果摘要、最终答复按真实发生顺序提交到 scrollback；并发批的工具行按模型给出的调用顺序排列，整体不交错。
- N4: 结果体量受控——工具结果沿用 ch03 工具级截断（行 / 字符上限 + `[truncated]`）；多轮累积下上下文与界面均不被撑爆。
- N5: 取消及时、无泄漏——Esc / Ctrl+C 后尽快停止后续迭代（正在执行的工具靠 cancellation 取消尽力而为）；循环退出后不残留挂起的 asyncio task 或未关闭的 queue。
- N6: 并发安全——并发批内的工具执行与结果收集无数据竞争（asyncio 单线程模型下确保 `await` 切换点不破坏共享状态；并发执行使用 `asyncio.gather` 写入独立下标即可）。
- N7: 密钥不回显——沿用 ch03，对话区与任何输出均不出现 api_key。
- N8: 代码规范——`ruff format` 已格式化、`ruff check` 无告警、可选 `mypy` 通过（遵循项目 CLAUDE.md）。

## 不做的事

- 权限系统 / 交互式确认——工具执行（含写文件、执行命令）前不做授权确认（留待专门章节）。
- 上下文压缩 / 历史裁剪——多轮累积的历史不压缩、不裁剪，超长会话可能触及上下文上限（留待后续）。
- 工具执行沙箱 / 路径白名单——沿用 ch03，不限制工具只能在工作目录内操作。
- 工具调用与结果持久化——沿用 ch02/ch03，退出即丢。
- 迭代上限 / 超时配置化——均为内置常量，本章不通过配置调整。
- 跨批重排并发——只在「连续只读」批内并发；不把读写调用重排以追求最大并行度。
- 子 Agent / 任务分解工具（如 Task 工具）——不做。
- Plan Mode 的计划落盘 / 审批门工具（如 ExitPlanMode）——`/plan`、`/do` 为简单手动切换，不引入计划审批工具或计划持久化。
- Token 预算限制 / 按用量自动停止——只统计与展示用量，不按预算自动截断。
- 多模态——工具结果与对话均为文本。
- 流式工具结果——工具结果一次性回灌，不做流式产出。

## 验收标准

- AC1: 多轮自动连环——给需要连续两步工具的任务（如「读 `docs/ch03/spec.md`，再据其内容新建一个摘要文件」），Agent 自动多轮执行工具调用并回灌结果；当某轮模型不再请求工具、只输出纯文本时循环停止、该文本即最终答复，全程无需用户中途催。(F1)
- AC2: 自然完成——模型给出无工具调用的纯文本时循环立即停止，该文本即最终答复。(F2)
- AC3: 迭代上限兜底——构造模型反复调工具不收手的情形（或将上限调低），达到上限即停并提示，不无限循环。(F2)
- AC4: 连续未知工具停止——模型连续请求注册中心不存在的工具达阈值时，循环停止并提示。(F2)
- AC5: 流出错恢复——provider 流出错时停止本轮、给出错误提示、程序不退出，之后可继续正常对话。(F2)
- AC6: 事件流完备——Agent 对外事件涵盖文本、工具调用开始/结束、Token 用量、迭代进度、结束、错误；界面仅靠这些事件渲染。(F3)
- AC7: 流式收集双路——文本实时显示的同时，模型一次回复中完整的工具调用（含拼齐的 JSON 参数）被正确收集用于下一轮。(F4)
- AC8: 保序分批并发——一次回复含多个工具调用时，连续只读并发执行、有副作用串行执行，保持相对顺序；结果按原始顺序回灌。(F5)
- AC9: 历史一致——多轮的 assistant 与工具结果回合按序入历史；取消 / 上限 / 出错终止后历史仍配对合法，可继续对话（不出现连续同角色或悬空工具调用导致下一轮请求 400）。(F6)
- AC10: 用户取消——流式态 Esc 或 Ctrl+C 中断本轮、回空闲态、不退出；空闲态 Ctrl+C 退出程序。(F7)
- AC11: 用量展示——状态栏显示会话累计 token 用量（输入 / 输出），随轮次增长更新。(F8)
- AC12: 进度展示——流式态动态区显示当前迭代轮次。(F9)
- AC13: Plan Mode——`/plan` 后模型仅用只读工具产出计划、不产生写/执行类调用；`/do` 切回全工具并立即按上文计划执行（产生写/执行类工具调用）。(F10)
- AC14: 跨协议一致——anthropic 与 openai（兼容端点）两种配置都跑通完整多轮 Loop，触发 / 执行 / 回灌 / 用量 / 取消行为一致。(F11)
```

````markdown
# Agent Loop Plan

> 基于已批准的 spec.md。本文档与语言相关（Python 3.12+）。SDK 类型已对 `anthropic`（AsyncAnthropic）、`openai`（AsyncOpenAI）的官方 Python SDK 核对。

## 架构概览ch04 不新增包，在 ch03「tool / agent / llm / conversation / prompt / tui」之上**扩展**：

- **`gcode.agent`（重写 run）**：把 ch03 的「请求#1 → 执行 → 请求#2 → 停」改为真正的 ReAct 循环——`for` 迭代直到自然完成 / 上限 / 取消 / 连续未知工具 / 出错。新增保序分批并发执行、迭代进度与用量事件、终止时的历史一致性收尾、Plan/Normal 两种模式。
- **`gcode.llm`（扩展）**：`StreamEvent` 增 `usage` 字段；`Provider.stream` 增 `system_suffix: str` 形参（Plan Mode 系统提示后缀）；两适配器在流结束后上抛本轮 token 用量、把 `system_suffix` 拼到内置系统提示后；OpenAI 打开 `stream_options={"include_usage": True}`。
- **`gcode.tool`（扩展）**：`Tool` Protocol 增 `read_only: bool` 属性；6 个工具各实现；`Registry` 增 `read_only_definitions()` 与 `is_read_only(name)`。
- **`gcode.conversation`（扩展）**：增 `last_role()`（终止收尾判断角色尾巴）。
- **`gcode.prompt`（扩展）**：增 `PLAN_MODE_REMINDER`（计划态系统后缀）与 `EXECUTE_DIRECTIVE`（`/do` 触发执行的用户消息）；`SYSTEM_PROMPT` 增补「持续工作直到任务完成」的 Agent 循环约定。
- **`gcode.tui`（扩展）**：`submit` 识别 `/plan`、`/do`；引入 per-turn 取消事件；事件泵处理用量 / 进度 / 通知 / 多个并发工具；按键处理拆分 Esc / Ctrl+C；状态栏显示模式与累计用量、动态区显示迭代轮次。

依赖方向不变、无环：`tool → llm`；`conversation → llm`；`agent → {llm, tool, conversation}`；`tui → {agent, tool, conversation, llm, prompt}`；`llm → {config, prompt}`。

## 核心数据结构### `gcode.llm`（扩展）

```python
from dataclasses import dataclass
from typing import AsyncIterator, Literal, Protocol

# Usage 协议无关地承载一轮请求的 token 用量。
@dataclass
class Usage:
    input_tokens: int = 0   # 本轮请求输入（含完整历史）token 数
    output_tokens: int = 0  # 本轮响应输出 token 数

# StreamEvent 扩展：在 text / tool_calls / done / err 之外，turn 结束时一次性上抛 usage。
@dataclass
class StreamEvent:
    text: str = ""
    tool_calls: list["ToolCall"] | None = None
    usage: Usage | None = None       # 非空：本轮 token 用量（done 之前一次性发出）
    done: bool = False
    err: Exception | None = None

class Provider(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def model(self) -> str: ...
    # system_suffix 非空时拼接到内置 SYSTEM_PROMPT 之后（Plan Mode 计划态约束）；
    # 为空即普通模式。
    def stream(
        self,
        msgs: list["Message"],
        tools: list["ToolDefinition"],
        system_suffix: str = "",
    ) -> AsyncIterator[StreamEvent]: ...
```

`Message`/`ToolCall`/`ToolResult`/`ToolDefinition` 与 role 常量沿用 ch03，不变。

### `gcode.tool`（接口扩展）

```python
# Tool Protocol 新增 read_only：True=只读工具（可并发执行 & Plan Mode 放行）。
class Tool(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def parameters(self) -> dict[str, object]: ...
    @property
    def read_only(self) -> bool: ...   # 新增
    async def execute(self, args: dict[str, object]) -> "ToolResult": ...
```

只读分类（依据语义）：`read_file` / `glob` / `grep` → `True`；`write_file` / `edit_file` / `bash` → `False`（`bash` 可执行任意副作用命令，保守归为有副作用、串行执行）。

`Registry` 新增：

```python
def read_only_definitions(self) -> list[ToolDefinition]:
    """Plan Mode：只导出 read_only==True 的工具定义，保留注册顺序。"""

def is_read_only(self, name: str) -> bool:
    """分批判定；未知工具返回 False（按串行处理）。"""
```

### `gcode.agent`（事件模型扩展 + run 重写）

```python
from dataclasses import dataclass
from enum import IntEnum
from typing import AsyncIterator

# Usage 一轮请求的 token 用量（透传 llm.Usage 的语义）。
@dataclass
class Usage:
    input: int = 0
    output: int = 0

# Event 对外事件流元素，消费者据非默认字段分派渲染。
@dataclass
class Event:
    text: str = ""                # 模型文本增量（preamble 或最终答复）
    tool: "ToolEvent | None" = None   # 工具调用开始/结束（沿用 ch03）
    usage: Usage | None = None    # 本轮 token 用量（每轮 stream 结束后一次）
    iter: int = 0                 # >0：进入第 iter 轮迭代（进度提示）
    notice: str = ""              # 系统提示（停止原因等），仅用于 UI 展示，不入对话历史
    done: bool = False            # 本轮（整个 Loop）结束
    err: Exception | None = None  # 出错（不中断会话）

# Mode 区分普通模式与计划模式。
class Mode(IntEnum):
    NORMAL = 0
    PLAN = 1

class Agent:
    def __init__(self, provider: "Provider", registry: "Registry") -> None: ...
    # run 执行 Agent Loop，返回事件 async generator；mode 决定工具集与系统后缀。
    def run(
        self,
        conv: "Conversation",
        mode: Mode,
        cancel: "asyncio.Event",
    ) -> AsyncIterator[Event]: ...
```

`ToolEvent`、`Phase`（`PHASE_START` / `PHASE_END`）、`Agent`、构造器沿用 ch03。`run` 签名新增 `mode` 与 `cancel` 形参。

> `cancel` 替代 Go 版 `context.WithCancel`：调用方持有 `asyncio.Event`，触发 `cancel.set()` 即中断本轮；`Agent` 把该事件穿透给 streamOnce 与工具执行点。

`Agent.__init__` 沿用 ch03：注入 `provider` 与 `registry`。`mode` 为 `run` 的每次调用入参，不写入 `Agent` 状态（同一 `Agent` 可被不同 mode 复用）。

迭代、停止常量与提示文案（内置，不可配）：

```python
MAX_ITERATIONS: int = 25   # 迭代上限兜底（F2）
MAX_UNKNOWN_RUN: int = 3   # 连续「整轮只产生未知工具调用」的迭代数上限（F2）

# 停止/收尾提示文案——既作为 Event(notice=...) 推给 UI，也作为 ensure_assistant_tail 写入历史的兜底文本。
NOTICE_MAX_ITER       = "（已达最大迭代轮数 25，自动停止；可继续发消息推进。）"
NOTICE_UNKNOWN_TOOLS  = "（连续多轮只请求到未注册的工具，自动停止。）"
NOTICE_STREAM_ERR     = "（请求出错，本轮已中断。）"
NOTICE_CANCELLED      = "（已取消。）"
```

## 模块设计### `gcode.agent`（核心：run 重写）**职责：** ReAct 循环编排（F1/F2）、保序分批并发执行（F5）、事件流（F3/F8/F9）、终止历史一致性（F6）、Plan/Normal 模式（F10）。
**对外接口：** `Agent`、`Agent.run(conv, mode, cancel)`、`Event`、`ToolEvent`、`Phase`、`Mode`、`Usage`。
**依赖：** `llm`、`tool`、`conversation`、`asyncio`（并发批 `asyncio.gather`）。

**run 算法（async generator）：**

1. 按 `mode` 取工具集与系统后缀：
   - `Mode.PLAN` → `defs = registry.read_only_definitions()`、`suffix = prompt.PLAN_MODE_REMINDER`。
   - `Mode.NORMAL` → `defs = registry.definitions()`、`suffix = ""`。
2. `unknown_run = 0`。
3. `for it in range(1, MAX_ITERATIONS + 1):`
   1. `yield Event(iter=it)`（进度，F9）；若 `cancel.is_set()` → `finish_cancelled(conv)`；return。
   2. `text, calls, usage, ok = await stream_once(conv, defs, suffix, cancel, push)`。
      - `not ok` 且 `cancel.is_set()`（取消）→ `finish_cancelled(conv)`、return。
      - `not ok` 且 `not cancel.is_set()`（流出错，err 已在 stream_once 内 yield）→ `ensure_assistant_tail(conv, NOTICE_STREAM_ERR)`、return。
   3. `if usage is not None: yield Event(usage=Usage(usage.input_tokens, usage.output_tokens))`（F8）。
   4. **无工具** `not calls`：`conv.add_assistant(ensure_final(text))`；`yield Event(done=True)`；return（自然完成，F2-1）。
   5. **有工具**：`conv.add_assistant_with_tool_calls(text, calls)`。
   6. 统计未知工具：`unknown_run = unknown_run + 1 if all_unknown(calls) else 0`。
   7. `results, completed = await execute_batched(calls, cancel, push)`（保序分批并发，F5）。
   8. `conv.add_tool_results(results)`（无论是否取消都回灌，含已取消占位，F6）。
   9. `if not completed`（执行中被取消）→ `ensure_assistant_tail(conv, "（已取消）")`、return。
   10. `if unknown_run >= MAX_UNKNOWN_RUN` → `yield Event(notice=NOTICE_UNKNOWN_TOOLS)`；`ensure_assistant_tail(conv, NOTICE_UNKNOWN_TOOLS)`；`yield Event(done=True)`；return（F2-4）。
4. 循环正常走完（触达上限）：`yield Event(notice=NOTICE_MAX_ITER)`；`ensure_assistant_tail(conv, NOTICE_MAX_ITER)`；`yield Event(done=True)`（F2-2）。

> 实际实现里 `yield` 直接由 `run` 自己完成，`stream_once` / `execute_batched` 通过把 `push: Callable[[Event], Awaitable[None]]` 注入实现「子流程往同一个 generator 推事件」的效果——Python 等价于 Go 版的 channel emit。最简洁的写法是把 `stream_once` / `execute_batched` 都改为 async generator，再用 `async for` 转发。

**stream_once(conv, defs, suffix, cancel) → (text, calls, usage, ok)：**
`async for ev in provider.stream(conv.messages(), defs, suffix):`
- `ev.err is not None` → `yield Event(err=ev.err)`、`return "", [], None, False`。
- `ev.usage is not None` → 记录 `usage = ev.usage`（不立即 yield，由 run 在拿到后统一 yield）。
- `ev.tool_calls` → `calls.extend(ev.tool_calls)`。
- `ev.text` → 累积 `text` 并 `yield Event(text=ev.text)`。
- 每次循环前后判 `cancel.is_set()`：True 即 `return "", [], None, False`。

循环后 `if cancel.is_set(): return "", [], None, False`；否则 `return text, calls, usage, True`。

**execute_batched(calls, cancel) → (results, completed)：**
保序分批（F5）。`results = [None] * len(calls)`；从 `i=0` 逐段扫描：

- 当前 `calls[i]` 只读 → 向前吃连续只读得最长区间 `[i, j)`（`j` 为首个非只读或末尾），**并发**执行该批：用 `asyncio.gather(*[run_one(k) for k in range(i, j)])`；`run_one(k)` 内 `try: result = await asyncio.wait_for(registry.execute(call.name, call.args), tool.DEFAULT_TIMEOUT)`（超时回灌结构化结果），把结果写入**自己下标** `results[k]`（互不重叠，单线程模型下无需锁）。`i = j`。
- 当前 `calls[i]` 非只读 → **串行**执行单个 `calls[i]`（同样 `asyncio.wait_for(..., tool.DEFAULT_TIMEOUT)`），写 `results[i]`。`i += 1`。
- 每段开始执行前先判 `cancel.is_set()`（取消）：给区间内尚未执行的 call 填「已取消」结果（`ToolResult(is_error=True, content=NOTICE_CANCELLED)`），其余沿用已得结果，`return results, False`。
- 全部完成 `return results, True`。

> 超时口径：每个工具各拿一个 `DEFAULT_TIMEOUT`（30s）`wait_for` 包装，互不相加——并发批的整体上限仍是单个 30s（N1）。`cancel` 在每个等待点被监听（通过 `asyncio.wait` 的多路等待或工具内自行 `cancel.is_set()` 早退），用户取消时尽快返回。

事件与顺序（满足 N3 顺序、N2 不阻塞、N6 无竞争）：
- 单个串行工具：`yield Event(tool=ToolEvent(PHASE_START, ...))` → 执行 → `yield Event(tool=ToolEvent(PHASE_END, ...))`（沿用 ch03 时序，动态区显示该工具 Running）。
- 并发批：**先**按序 `yield` 区间内每个工具的 PHASE_START（动态区列出多个在执行的工具行）→ 并发执行 → **再**按原始顺序 `yield` 每个工具的 PHASE_END（逐个把工具行 + 结果摘要提交 scrollback）。即「开始事件按序、结束事件按序」，并发只发生在执行环节，事件顺序始终是调用序，scrollback 不交错。
- 并发安全：asyncio 单线程模型下，`await` 切换点是唯一的并发边界；每个并发 task 只写自己下标的 `results[k]`（不同下标互不重叠），不触碰 `conv`；`conv.add_tool_results` 由 run 主流程在 `gather` 汇合后串行调用。Token 用量累计在 TUI 侧串行处理。

**辅助函数：**
- `all_unknown(calls)`：对每个 call 用 `registry.get(call.name)` 判断，**全部** `None` 才返回 True；任一已注册即 False（混入已知工具视为有进展，计数重置）。不能用 `is_read_only`（未知工具它也返回 False，会与有副作用工具混淆）。
- `ensure_final(text)`：沿用 ch03——`text` 非空原样返回；为空则 yield 占位提示并返回占位文本（避免空 assistant 回合破坏下一轮请求）。
- `ensure_assistant_tail(conv, fallback)`：若 `conv.last_role() != "assistant"`（含空历史、末尾为 user 或 tool 角色），`conv.add_assistant(fallback)`，保证历史以 assistant 文本回合收尾（F6：取消/出错/上限后角色仍交替，下一轮请求不报 400）。
- `finish_cancelled(conv)`：取消路径统一收尾——`ensure_assistant_tail(conv, NOTICE_CANCELLED)`、return（**不 yield notice**，因 cancel 已被消费方感知；generator 终结即视为本轮结束）。

> 终止优先级：执行中取消（`completed is False`）是**最高优先级**终止——立即 `ensure_assistant_tail` 并 return，**跳过**未知工具计数与迭代上限检查。

### `gcode.llm`（扩展）**职责：** 协议无关请求/响应 + 两协议工具调用全流程（沿用 ch03）+ 本轮用量上抛（F8）+ 系统后缀（F10）。

**`__init__.py`：** 新增 `Usage` 类型；`StreamEvent` 增 `usage: Usage | None`；`Provider.stream` 增 `system_suffix: str = ""` 形参（更新接口文档）。

**`anthropic_provider.py`：**
- 系统提示：`params["system"]` 由硬编码 `prompt.SYSTEM_PROMPT` 改为 `_effective_system(suffix)`——`suffix == ""` 时单段 `SYSTEM_PROMPT`；非空时拼成 `SYSTEM_PROMPT + "\n\n" + suffix`（保持单段字符串，避免多块边界差异）。
- 用量：流正常结束（`async with client.messages.stream(...)` 上下文退出且未异常）后，在 `yield StreamEvent(done=True)` 之前先 `yield StreamEvent(usage=Usage(input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens))`——`final = await stream.get_final_message()` 或直接读流上下文的 `usage` 累加器（SDK 在流结束后聚合可用）。
- 历史含工具交互时 thinking 已自动关闭（ch03 既有逻辑），多轮续答沿用，无需改动。

**`openai_provider.py`：**
- 请求构造增 `stream_options={"include_usage": True}`（不开则流式 usage 块为空）。
- 系统提示：`_to_openai_messages` 接收 `suffix`，把首条 system 消息文本由 `SYSTEM_PROMPT` 改为拼接 `suffix`（非空时 `+ "\n\n" + suffix`）。
- 用量：流末尾会出现一个 `choices == []` 但带 `chunk.usage` 的 chunk（启用 `include_usage` 后由 SDK 透传），读 `chunk.usage.prompt_tokens` / `chunk.usage.completion_tokens` → `yield StreamEvent(usage=Usage(...))`。

### `gcode.tool`（扩展）

- `Tool` Protocol 加 `read_only: bool` 属性；6 个工具各加一行实现（read/glob/grep 返回 True，write/edit/bash 返回 False）。
- `Registry.read_only_definitions()`：仿 `definitions()`，仅收 `tools[name].read_only is True` 的项，保持注册顺序。
- `Registry.is_read_only(name)`：`t = self.get(name); return t is not None and t.read_only`（未知工具 False）。
- `execute`、`DEFAULT_TIMEOUT`、6 工具的执行逻辑均不变。

### `gcode.conversation`（扩展）

```python
def last_role(self) -> str:
    """返回最后一条消息的 role；空历史返回 ""。"""
    return self._messages[-1].role if self._messages else ""
```

其余沿用 ch03。

### `gcode.prompt`（扩展）

```python
# PLAN_MODE_REMINDER：Plan Mode 系统提示后缀，拼接到 SYSTEM_PROMPT 之后。
PLAN_MODE_REMINDER = (
    "You are currently in PLAN MODE. You may use ONLY the read-only tools "
    "(read_file, glob, grep) to investigate the codebase. You must NOT write files, "
    "edit files, or run shell commands. Produce a clear, step-by-step plan for the task, "
    "then stop and wait for the user to approve it with /do before doing any work."
)

# EXECUTE_DIRECTIVE：/do 注入的用户消息——指示模型按上文已确认的计划开始执行，可使用全部工具。
EXECUTE_DIRECTIVE = "请按上面的计划开始执行。"
```

`SYSTEM_PROMPT` 增补一句 Agent 循环约定（追加到现有文案）：`"Keep using tools across multiple steps to make progress, and only give your final concise answer once the task is complete."`（中文项目里保持英文 system prompt 风格，与 ch03 现有 `SYSTEM_PROMPT` 一致）。

### `gcode.tui`（扩展）**`GCodeApp` 新增字段（`tui/app.py`）：**
- `mode: agent.Mode`——当前模式（默认 `Mode.NORMAL`），`/plan`、`/do` 切换，跨轮保持。
- `iter: int`——当前迭代轮次（进度显示），每轮 `iter` 事件更新，`finish_turn` 归零。
- `usage_in: int`、`usage_out: int`——会话累计 token 用量，每个 `usage` 事件累加。
- `cur_tools: list[ToolDisplay]`——替换 ch03 的单个 `cur_tool`，支持并发批多个在执行的工具行。
- `turn_cancel: asyncio.Event | None`——本轮取消事件，Esc / Ctrl+C 触发 `set()`；程序级退出仍由 `App.exit()`。

**`submit`（`tui/stream.py`）：**
1. `/exit` → 退出（沿用）。
2. `/plan` → `self.mode = Mode.PLAN`；写一行提示块到 `RichLog`（如「已进入计划模式（只读工具）」）；回 IDLE。
3. `/do` → `self.mode = Mode.NORMAL`；`self.conv.add_user(prompt.EXECUTE_DIRECTIVE)`；走与普通提交相同的启动流程（不把 `/do` 本身入历史）。
4. 普通文本 → `self.conv.add_user(text)`。
5. 启动：`self.turn_cancel = asyncio.Event()`；`self._stream_task = asyncio.create_task(self._consume_events(self.agent.run(self.conv, self.mode, self.turn_cancel)))`；`self.state = STREAMING`；`self.iter = 0`。用户输入块先 `RichLog.write` 再消费事件。

**`_consume_events`（`tui/stream.py`）分派顺序：**
对每个 `ev`：`err` → `tool` → `usage`（累加 `usage_in/usage_out`）→ `notice`（在 `RichLog` 写一行灰色系统提示块）→ `iter > 0`（`self.iter = ev.iter`）→ `done` → `text`（累积 `cur_reply`）。

- `ToolEvent.PHASE_START`：若 `cur_reply` 非空先把 preamble 提交 `RichLog` 并清空；`self.cur_tools.append(ToolDisplay(name, args))`。
- `ToolEvent.PHASE_END`：**FIFO 弹出队首** `self.cur_tools.pop(0)`（因 agent 保证 PHASE_START 与 PHASE_END 都按调用序发出，结束序 == 入队序，弹首即对应工具，无需按 name 匹配，重名工具也不会错位）；用其 args 定型工具行 → `RichLog.write(tool_line)` → `RichLog.write(tool_result_summary)`。

**按键（`GCodeApp.on_key` 或 `BINDINGS`，全局优先）：**
- `ctrl+c`：`STREAMING` → `self.turn_cancel.set()`（取消本轮，不退出）；否则 `self.exit()`。
- `escape`：`STREAMING` → `self.turn_cancel.set()`；其余忽略。

**`view.py`：**
- `status_bar`：左侧在 provider 名后附模式标记（`Mode.PLAN` 显示「PLAN」徽标）；右侧在 model 名旁附累计用量 `↑{in} ↓{out} tok`（数值用紧凑格式，如 `1.2k`）。保持单行。
- 流式动态区：`cur_tools` 非空时逐行渲染 `● name(args)` + Running…（多个并发工具多行）；否则渲染「Imagining… (Ns · 第 N 轮)」（`self.iter > 0` 时附轮次）。
- `tool_line` / `tool_result_summary` 沿用 ch03。

**`finish_turn`（`tui/stream.py`）：** 清 `cur_reply`、`cur_tools = []`、`_stream_task = None`、`iter = 0`、`turn_cancel = None`，回 IDLE（`mode`、`usage_in/usage_out` 不清——跨轮保持）。

## 模块交互

```
用户提交 /do 或普通文本
  └─ tui.submit:
       ├─ /plan → mode=PLAN，回 IDLE
       ├─ /do   → mode=NORMAL; conv.add_user(EXECUTE_DIRECTIVE)
       ├─ 文本  → conv.add_user(text)
       └─ turn_cancel = asyncio.Event()
          stream_task = create_task(_consume_events(agent.run(conv, mode, turn_cancel)))
            └─ agent.run (async generator, ReAct 循环):
                 for it in range(1, MAX_ITERATIONS+1):
                   ├─ yield iter
                   ├─ 请求: provider.stream(conv.messages(), defs(mode), suffix(mode))
                   │     └─ 适配器: 注入 tools + (SYSTEM_PROMPT+suffix) → 流式拼接
                   │          → StreamEvent(text=...) / (tool_calls=...) / (usage=...) / (done|err)
                   │     → agent 转发 text(preamble)、收集 calls、记录 usage
                   ├─ yield usage
                   ├─ 无 calls → conv.add_assistant(final); yield done; 停
                   └─ 有 calls:
                        ├─ conv.add_assistant_with_tool_calls(preamble, calls)
                        ├─ execute_batched: 连续只读 asyncio.gather / 有副作用 await 单个
                        │     （PHASE_START 按序 → 执行 → PHASE_END 按序）
                        ├─ conv.add_tool_results(results)
                        └─ 下一轮 it
  └─ tui._consume_events: text→cur_reply；tool→cur_tools/RichLog；usage→累加；
       iter→self.iter；notice→灰提示；done→提交最终答复+finish_turn
  └─ Ctrl+C / Esc（streaming）→ turn_cancel.set() → agent.run 收尾历史 → generator 结束 → finish_turn → IDLE
```

并发模型：`conv` 任一时刻只被 `run` 的主协程触碰（`submit` 在交给 `run` 前 `add_user`，之后不再触碰；执行批的并发 task 只写各自 `results[k]`，不碰 `conv`）。`messages()` 返回副本。asyncio 单线程模型下 `await` 之间无中断，配合独立下标写入即可保证 N6。

## 文件组织

```
gcode/
├── src/gcode/
│   ├── llm/
│   │   ├── __init__.py            — 修改：新增 Usage；StreamEvent 加 usage；Provider.stream 加 system_suffix 形参
│   │   ├── anthropic_provider.py  — 修改：_effective_system(suffix)；流结束上抛 usage
│   │   └── openai_provider.py     — 修改：stream_options={"include_usage": True}；_to_openai_messages 拼 suffix；上抛 usage
│   ├── tool/
│   │   ├── __init__.py            — 修改：Tool Protocol 加 read_only
│   │   ├── registry.py            — 修改：read_only_definitions、is_read_only
│   │   └── {read_file,write_file,edit_file,bash,glob,grep}.py — 修改：各加 read_only 属性
│   ├── agent/
│   │   ├── __init__.py            — 重写：ReAct 循环、Mode、execute_batched、usage/iter/notice 事件、历史收尾
│   │   └── 单测见 tests/test_agent.py
│   ├── conversation.py            — 修改：last_role()
│   ├── prompt.py                  — 修改：PLAN_MODE_REMINDER、EXECUTE_DIRECTIVE；SYSTEM_PROMPT 增循环约定
│   └── tui/
│       ├── app.py                 — 修改：状态字段 mode/iter/usage/cur_tools/turn_cancel；按键拆分 Esc/Ctrl+C
│       ├── stream.py              — 修改：submit 识别 /plan /do + per-turn cancel；_consume_events 处理 usage/iter/notice/多工具
│       └── view.py                — 修改：状态栏模式徽标+累计用量；动态区迭代轮次+多并发工具行
└── tests/
    ├── test_agent.py              — 扩展：多轮 fake provider、并发分批、停止条件、Plan 工具集
    ├── test_conversation.py       — 扩展：last_role 断言
    └── test_tool.py               — 扩展：read_only_definitions、is_read_only（如已存在则补断言）
```

> 注：`cli.py` 已在 ch03 注入 registry，ch04 无需改动；`mode` 状态存于 TUI，不经 cli。

### 签名变更的调用方清单

ch04 改了两个签名，必须同步所有调用方/实现方，否则导入即报错：

- **`Provider.stream` 增 `system_suffix: str = ""`（第 3 形参，给默认值方便逐步迁移）**：
  - 实现方：`gcode/llm/anthropic_provider.py`、`gcode/llm/openai_provider.py`。
  - 调用方：`gcode/agent/__init__.py` 的 `stream_once`（唯一直接调用方）。
  - 测试实现方：`tests/test_agent.py` 的 `FakeProvider.stream`（也实现该 Protocol，签名须同步）。
- **`Agent.run` 增 `mode: Mode` 与 `cancel: asyncio.Event`**：
  - 调用方：`gcode/tui/stream.py`（`submit` 内）、`tests/test_agent.py`（各用例）。两者都要补 `mode` 与 `cancel` 实参（旧用例传 `Mode.NORMAL` + 一个未触发的 `asyncio.Event()`）。

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Loop 放哪 | 重写 `Agent.run` 为循环，签名加 `mode` / `cancel` | 循环编排天然属 agent 模块；TUI 维持纯渲染器。run 已是 async generator，循环只是把单轮的两次 `stream_once` 推广为 `for`，改动收敛在一个模块。 |
| 不用 SDK 内置 tool-runner | 坚持手写循环 + stable streaming | 沿用 ch03 决策；自写循环才能精确控制停止条件、保序分批、取消与历史收尾，SDK 的自动 runner 把这些黑盒化。 |
| 停止条件之「连续未知工具」 | 连续 `MAX_UNKNOWN_RUN=3` 轮「整轮只产生未知工具调用」即停 | 单次未知工具靠 registry 的「未知工具」结构化错误回灌即可让模型纠偏；只有连续多轮全错才说明在对幻觉工具空转，需兜底。混入任一已注册工具即重置计数（视为有进展）。 |
| 迭代上限值 | `MAX_ITERATIONS=25`，内置常量 | 兜底安全网，避免失控烧 token；25 足够覆盖正常多步任务。spec 明确不配置化，与 ch03 超时不配化一致。 |
| 并发分批粒度 | 「连续只读」合批并发，有副作用单个串行，保持调用序 | 用户选定的「保序分批」：read 之后的 write 不会被提前；相邻只读才并发加速。`bash` 保守归有副作用（可含任意写操作）。 |
| 并发的事件顺序 | 开始事件按序、结束事件按序，并发只在执行环节 | 满足 N3（scrollback 不交错）：UI 看到的工具行顺序始终是模型调用序；并发对用户透明，只体现为更快。每个 task 只写自己下标的 `results[k]`，asyncio 单线程模型下无锁亦无竞争（N6）。 |
| 取消机制 | per-turn `asyncio.Event`，TUI 持有；Esc / Ctrl+C(streaming) 触发 `set()`，Ctrl+C(idle) 退出 | 程序级 App 退出不动，新增每轮事件才能「取消本轮但不退程序」。`cancel.is_set()` 在 stream 循环与每个工具等待点被检查，自然停。 |
| 取消后历史一致 | 已发起工具补「已取消」结果 + `ensure_assistant_tail` 收尾 | F6：取消可能停在「assistant 含 tool_use 但缺 tool_result」或「user 之后无 assistant」处；补齐工具结果 + 保证 assistant 文本尾巴，下一轮请求才不会因悬空 tool_use / 连续同角色被 API 拒（400）。 |
| 用量提取位置 | 适配器在流结束后从 SDK 累加器/末尾 chunk 读 usage 并经 `StreamEvent(usage=...)` 上抛 | 两 SDK 的流式 usage 都只在流结束后完整可用（Anthropic 上下文退出后的 `get_final_message()` 或累加器；OpenAI 需 `include_usage=True` 后在末尾 chunk 读 `chunk.usage`）；逐 delta 不含。统一在 done 前发一次。 |
| 累计用量口径 | 状态栏显示「会话累计计费 token」= 每轮 input+output 之和 | 多轮 Loop 每轮都重发完整历史，各轮 input 重复计费；按轮累加正是实际消耗/成本口径，对用户最有意义。 |
| Plan Mode 系统提示注入 | `Provider.stream` 加 `system_suffix: str = ""` 形参 | 系统提示在适配器内注入，要让计划态约束生效必须穿过 stream。加一个字符串形参最小且显式；备选「请求 options dataclass」更可扩展但改动面更大，YAGNI 下不引入。 |
| Plan Mode 工具集 | 计划态只注入 `read_only_definitions()` | 物理上不给模型写/执行工具，即便提示被忽略也无法改动；只读分类靠 `Tool.read_only`。 |
| `/do` 语义 | 切回 Normal + 注入 `EXECUTE_DIRECTIVE` 用户消息 + 立即启动 Loop | 用户选定「切回全工具并立即执行」；复用已在历史里的计划，`/do` 不入历史，只把执行指令作为用户消息驱动模型开干。 |
| 模式状态存放 | 存于 TUI `GCodeApp`，不进 `Conversation` | `Conversation` 是历史、`messages()` 返回副本，放不住可变模式；模式是会话级 UI 状态，跨轮保持，归 TUI 最自然。 |
| 多并发工具的 UI | `cur_tools: list[ToolDisplay]` 取代单个 `cur_tool` | 并发批同时有多个工具在跑，动态区需多行展示；结束事件按序逐个落 `RichLog`。 |
| 进度事件 | 每轮起始 `yield Event(iter=n)`，UI 显示「第 N 轮」 | F9 让用户感知多轮推进；用非零 `iter` 字段分派，与 ch03 的零值分派惯例一致。 |
| 通知 vs 历史 | 上限/未知工具的提示同时 yield `notice`（UI 灰字）并写入 assistant 历史 | UI 要让用户看到为何停；写入历史是为满足 `ensure_assistant_tail`（角色交替），二者用同一文案，避免历史里留空 assistant 回合。 |
````

````markdown
# Agent Loop Tasks

> 基于已批准的 spec.md + plan.md。任务有序，每步留绿编译。验证一律「先跑命令看输出，再下结论」。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `src/gcode/llm/__init__.py` | 新增 `Usage` 类型；`StreamEvent` 加 `usage`；`Provider.stream` 加 `system_suffix` 形参 |
| 修改 | `src/gcode/llm/anthropic_provider.py` | `_effective_system(suffix)`；流结束上抛 usage |
| 修改 | `src/gcode/llm/openai_provider.py` | `stream_options={"include_usage": True}`；`_to_openai_messages` 拼 suffix；上抛 usage |
| 修改 | `src/gcode/tool/__init__.py` | `Tool` Protocol 加 `read_only` 属性 |
| 修改 | `src/gcode/tool/registry.py` | `read_only_definitions`、`is_read_only` |
| 修改 | `src/gcode/tool/{read_file,write_file,edit_file,bash,glob,grep}.py` | 各加 `read_only` 属性 |
| 修改 | `src/gcode/conversation.py` | `last_role()` |
| 修改 | `src/gcode/prompt.py` | `PLAN_MODE_REMINDER`、`EXECUTE_DIRECTIVE`；`SYSTEM_PROMPT` 增循环约定 |
| 重写 | `src/gcode/agent/__init__.py` | ReAct 循环、`Mode`、`execute_batched`、`usage/iter/notice` 事件、历史收尾 |
| 重写 | `tests/test_agent.py` | 多轮 fake provider、并发分批、停止条件、Plan 工具集 |
| 修改 | `tests/test_conversation.py` | `last_role` 断言 |
| 修改 | `src/gcode/tui/{app,stream,view}.py` | `mode`、per-turn cancel、Esc/Ctrl+C、`/plan` `/do`、`usage/iter/notice`/多工具、状态栏、动态区 |

## T1: llm 新增 Usage 类型（纯增量）**文件：** `src/gcode/llm/__init__.py`
**依赖：** 无
**步骤：**
1. 新增 `@dataclass class Usage(input_tokens: int = 0, output_tokens: int = 0)`（带中文注释：本轮输入/输出 token 数）。
2. 给 `StreamEvent` 增字段 `usage: Usage | None = None`（非空即本轮用量），更新 `StreamEvent` 文档注释补「`usage` 非空：本轮 token 用量，`done` 之前一次性发出」。

**验证：** `python -c "from gcode.llm import Usage, StreamEvent; print(StreamEvent(usage=Usage(1,2)))"` 通过；`ruff check src/gcode/llm/__init__.py` 无告警（纯增字段，向后兼容，不改 Protocol 签名）。

## T2: tool 只读分类**文件：** `src/gcode/tool/__init__.py`、`src/gcode/tool/registry.py`、`src/gcode/tool/{read_file,write_file,edit_file,bash,glob,grep}.py`
**依赖：** 无
**步骤：**
1. `__init__.py`：`Tool` Protocol 加 `read_only: bool` 属性（注释：True=只读，可并发执行 & Plan Mode 放行）。
2. 6 个工具各加一行属性：`read_file` / `glob` / `grep` → `read_only = True`；`write_file` / `edit_file` / `bash` → `read_only = False`。
3. `registry.py`：
   - `read_only_definitions() -> list[ToolDefinition]`：仿 `definitions()` 按注册顺序遍历，仅收 `self._tools[name].read_only is True` 的项。
   - `is_read_only(name: str) -> bool`：`t = self.get(name); return t is not None and t.read_only`。

**验证：** `pytest tests/test_tool.py`（若已存在）不回归；`python -c "from gcode.tool.registry import Registry"` 不报错；`ruff check src/gcode/tool` 无告警。

## T3: conversation.last_role**文件：** `src/gcode/conversation.py`、`tests/test_conversation.py`
**依赖：** 无
**步骤：**
1. `conversation.py`：新增 `def last_role(self) -> str`——空历史返回 `""`，否则返回 `self._messages[-1].role`。
2. `test_conversation.py`：补一组断言——空会话 `last_role() == ""`；`add_user` 后 `== "user"`；`add_tool_results` 后 `== "tool"`；`add_assistant` 后 `== "assistant"`。

**验证：** `pytest tests/test_conversation.py` 通过。

## T4: prompt 计划态提示与循环约定**文件：** `src/gcode/prompt.py`
**依赖：** 无
**步骤：**
1. `SYSTEM_PROMPT` 增补一句 Agent 循环约定：持续调用工具推进任务，直到任务完成后再给出最终简洁答复（不要每步都停下来等用户）。
2. 新增 `PLAN_MODE_REMINDER`：计划模式系统后缀——当前为计划模式，只能用只读工具（读文件 / 按模式找文件 / 搜内容）调研并产出一份分步执行计划；不得写文件、改文件或执行命令；计划写完即停，等用户用 `/do` 批准后再执行。
3. 新增 `EXECUTE_DIRECTIVE = "请按上面的计划开始执行。"`。
4. （可选）`READY_HINT` 增提 `/plan`、`/do`。

**验证：** `python -c "from gcode.prompt import PLAN_MODE_REMINDER, EXECUTE_DIRECTIVE; print(EXECUTE_DIRECTIVE)"` 通过；`pytest` 全量不回归。

## T5: llm Provider.stream 加 system_suffix + 用量上抛**文件：** `src/gcode/llm/__init__.py`、`src/gcode/llm/anthropic_provider.py`、`src/gcode/llm/openai_provider.py`、`src/gcode/agent/__init__.py`（临时补参）
**依赖：** T1
**步骤：**
1. `llm/__init__.py`：`Provider.stream` 签名改为 `def stream(self, msgs, tools, system_suffix: str = "") -> AsyncIterator[StreamEvent]`，更新 Protocol 文档说明 `system_suffix` 语义（非空时拼到内置 `SYSTEM_PROMPT` 之后）。
2. `anthropic_provider.py`：
   - `stream` 加 `system_suffix` 形参；`params["system"]` 由硬编码改为 `_effective_system(system_suffix)`——`suffix == ""` 单段 `SYSTEM_PROMPT`；非空时单段 `SYSTEM_PROMPT + "\n\n" + suffix`。
   - 流正常结束（`async with client.messages.stream(...) as stream:` 上下文退出且未异常）后、`yield StreamEvent(done=True)` 之前：`final = await stream.get_final_message()`；`yield StreamEvent(usage=Usage(input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens))`。
3. `openai_provider.py`：
   - `stream` 加 `system_suffix`；请求参数加 `stream_options={"include_usage": True}`。
   - `_to_openai_messages(msgs, system_suffix)`：首条 system 消息文本 `SYSTEM_PROMPT`，`system_suffix` 非空时 `+ "\n\n" + system_suffix`（其调用处同步加实参）。
   - 流末尾会出现一个 `chunk.choices == []` 但带 `chunk.usage` 的 chunk：检测到则 `yield StreamEvent(usage=Usage(input_tokens=chunk.usage.prompt_tokens, output_tokens=chunk.usage.completion_tokens))`，跳过该 chunk 的 text 分支。
4. `src/gcode/agent/__init__.py`：把现有 `stream_once` 里唯一的 `provider.stream(conv.messages(), defs)` 调用补成 `provider.stream(conv.messages(), defs, "")` 以匹配新签名——本步即让**非测试构建**保持绿（T6 会整体重写 agent）。

> 说明：`cli.py` 走 `agent.run`、不直接调 `stream`，本步不动它（其 `run` 调用在 T7 随 `mode` / `cancel` 形参一并更新）。`tests/test_agent.py` 的 `FakeProvider.stream` 也实现该 Protocol，本步之后它可能因签名不匹配让用例失败——这是预期的，T6 重写 `test_agent.py` 时一并补 `system_suffix` 形参；因此本步**不要**跑 `pytest tests/test_agent.py`。

**验证：** `python -c "from gcode.llm.anthropic_provider import AnthropicProvider; from gcode.llm.openai_provider import OpenAIProvider"` 不报错；`ruff check src/gcode/llm` 无告警；`python -m gcode` 发一条纯文本回复正常（用量已随流上抛，旧 agent 暂未消费）。

## T6: agent ReAct 循环重写**文件：** `src/gcode/agent/__init__.py`、`tests/test_agent.py`
**依赖：** T1, T2, T3, T4, T5
**步骤：**
1. `agent/__init__.py`：
   - 模块 docstring 改为「ReAct 循环编排」。
   - 类型：保留 `Phase` / `ToolEvent` / `Agent`；新增 `@dataclass class Usage(input: int = 0, output: int = 0)`、`class Mode(IntEnum): NORMAL = 0; PLAN = 1`；`Event` 增字段 `usage: Usage | None`、`iter: int = 0`、`notice: str = ""`。
   - 常量：按 plan「迭代、停止常量与提示文案」原样落 `MAX_ITERATIONS` / `MAX_UNKNOWN_RUN` 与 `NOTICE_MAX_ITER` / `NOTICE_UNKNOWN_TOOLS` / `NOTICE_STREAM_ERR` / `NOTICE_CANCELLED`（文案以 plan 为准，T8 端到端按这些文案核对）。
   - `Agent.run(conv, mode, cancel)`：按 plan「run 算法」实现 async generator——按 `mode` 取 `defs`(`definitions` / `read_only_definitions`) 与 `suffix`(`""` / `prompt.PLAN_MODE_REMINDER`)；`yield iter` → `stream_once` → `yield usage` → 无工具自然完成 / 有工具 `add_assistant_with_tool_calls` → 统计 `unknown_run` → `execute_batched` → `add_tool_results`（无条件）→ **取消（`not completed`）最高优先级收尾** → 未知工具上限收尾 → 循环走完触达迭代上限收尾。
   - `stream_once(conv, defs, suffix, cancel) → (text, calls, usage, ok)`：`suffix` 为 ch04 新增形参，透传给 `provider.stream`；转发 text、收集 calls、记录 `ev.usage`、`err` 即 `yield Event(err=...)` 返回 `ok=False`。
   - `execute_batched(calls, cancel) → (results, completed)`：保序分批——从 `i=0` 扫描，`is_read_only(calls[i])` 为真则吃最长连续只读区间 `[i, j)` 用 `asyncio.gather` **并发**（每 task 内 `asyncio.wait_for(registry.execute(...), DEFAULT_TIMEOUT)`，只写自己下标 `results[k]`），否则**串行**单个；每段执行前判 `cancel.is_set()` 取消则填 `NOTICE_CANCELLED` 结果返 `completed=False`；事件「PHASE_START 按序、PHASE_END 按序」（见 plan）。
   - 辅助：`all_unknown(calls)`（每个 call 用 `registry.get` 判，全 `None` 才 True）、`ensure_final`（沿用 ch03）、`ensure_assistant_tail(conv, fallback)`、`finish_cancelled(conv)`、`args_preview`（沿用 ch03）。
2. `tests/test_agent.py`（**替换** ch03 的「单轮读再答」「单轮上限」用例——后者断言单轮已与 ch04 多轮矛盾）。`FakeProvider.stream` 签名补 `system_suffix: str = ""`（并在某用例里记录收到的 `tools` / `system_suffix` 供断言）；多轮靠 `scripts: list[list[StreamEvent]]` 逐次返回：
   - 场景 A（多轮链路 AC1）：脚本①返回 1 个 `read_file` 工具调用、脚本②返回纯文本 → 断言事件序列含 `iter=1`、`tool` start/end、`iter=2`、最终 `text`、`done=True`；`conv` 末尾为 assistant 文本，中间含 tool_use 回合 + tool 角色回合。
   - 场景 B（迭代上限 AC3）：用「每次 stream 都返回一个工具调用」的 fake（忽略脚本耗尽，恒返工具）→ 断言恰好 `MAX_ITERATIONS` 次请求后停（`fp.calls == MAX_ITERATIONS`）、收到 `notice == NOTICE_MAX_ITER`、`conv.last_role() == "assistant"`。
   - 场景 C（连续未知工具 AC4）：脚本连续返回未注册工具名 → 断言 `MAX_UNKNOWN_RUN` 轮后停并 `notice == NOTICE_UNKNOWN_TOOLS`；另一用例在其间混入一个 `read_file`，断言计数重置、不提前停。
   - 场景 D（保序分批 AC8）：构造**自定义 registry** 注册两个插桩工具——一个只读工具（`read_only=True`，`execute` 内用 `asyncio.Lock` / `atomic counter` 记录「同时在跑的并发数」峰值、并 `await asyncio.sleep(...)` 制造重叠）与一个有副作用工具（`read_only=False`，记录开始时刻）。脚本一轮返回 `[ro, ro, rw]` → 断言：两只读的并发峰值 ≥2（确实并发）、`rw` 的开始时刻晚于两只读完成、`add_tool_results` 写入历史的结果顺序与调用序一致（按结果内容/ID 比对，不依赖具体方法名）。
   - 场景 E（取消历史一致 AC9）：插桩工具在 `execute` 中 `await asyncio.sleep(...)` 阻塞，测试侧在执行期间 `cancel.set()` → 断言 `conv` 末尾配对合法（含 tool_results、最后是 assistant 文本 `NOTICE_CANCELLED`），无悬空 tool_use；随后再追加一轮纯文本脚本能正常跑（角色交替未坏）。
   - 场景 F（Plan 工具集 AC13）：`Agent.run(conv, Mode.PLAN, cancel)` → 断言 fake 收到的 `tools` 仅含只读工具定义、`system_suffix == prompt.PLAN_MODE_REMINDER`。

**验证：** `pytest tests/test_agent.py` 全通过；`pytest -p no:randomly tests/test_agent.py` 顺序稳定；并发分批用例多跑几次（如 `pytest --count=5 tests/test_agent.py::test_concurrent_batch`，需 `pytest-repeat`）无偶发失败（覆盖并发分批，N6）。

## T7: tui 接入 Agent Loop + 收尾 run 调用方**文件：** `src/gcode/tui/app.py`、`src/gcode/tui/stream.py`、`src/gcode/tui/view.py`
**依赖：** T4, T6
**说明：** T6 改了 `Agent.run` 签名（加 `mode` 与 `cancel`），其调用方 `tui/stream.py` 在此步同步更新——本步完成后 `python -m gcode` 才在**仓库级**重新可启动（T6 后只保证 agent 模块及其测试绿）。
**步骤：**
1. `app.py`：
   - `GCodeApp` 新增字段：`mode: agent.Mode = Mode.NORMAL`、`iter: int = 0`、`usage_in: int = 0`、`usage_out: int = 0`、`cur_tools: list[ToolDisplay] = []`（移除单个 `cur_tool`）、`turn_cancel: asyncio.Event | None = None`。
   - 按键拆分：`ctrl+c` → `STREAMING` 时 `self.turn_cancel.set()`（不退出，等 generator 收尾）/ 否则 `self.exit()`；新增 `escape` → `STREAMING` 时 `self.turn_cancel.set()`。
2. `stream.py`：
   - `submit`：识别 `/exit`（退出）、`/plan`（`mode = Mode.PLAN`、提示块、回 IDLE）、`/do`（`mode = Mode.NORMAL`、`conv.add_user(prompt.EXECUTE_DIRECTIVE)`、走启动流程）、普通文本（`conv.add_user`）。启动处：`self.turn_cancel = asyncio.Event()`；`self._stream_task = asyncio.create_task(self._consume_events(self.agent.run(self.conv, self.mode, self.turn_cancel)))`；`self.iter = 0`；`self.state = STREAMING`。
   - `_consume_events` 按 plan 分派顺序处理 `err` / `tool` / `usage`(累加 `usage_in/usage_out`) / `notice`(灰提示块) / `iter`(set `self.iter`) / `done` / `text`；`tool.phase == PHASE_START` 追加 `cur_tools`（首个工具前先提交 preamble）、`PHASE_END` 从 `cur_tools` 弹首并 `RichLog.write(tool_line)` + `RichLog.write(tool_result_summary)`。
   - `finish_turn`：清 `cur_reply` / `cur_tools` / `_stream_task` / `iter` / `turn_cancel`，回 IDLE（保留 `mode`、`usage_in/usage_out`）。
3. `view.py`：
   - `status_bar`：左侧 provider 名后在 `Mode.PLAN` 时附「PLAN」徽标；右侧 model 名旁附 `↑{in} ↓{out} tok`（紧凑数字，如 `1.2k`）。
   - 流式动态区：`cur_tools` 非空逐行渲染 `● name(args)` Running…；否则「Imagining… (Ns · 第 N 轮)」（`self.iter > 0` 附轮次）。

**验证：** `python -m gcode`（仓库级可启动）；`ruff format --check src/gcode/tui`、`ruff check src/gcode/tui` 无告警。

## T8: 全量验证与端到端冒烟**文件：** 无（验证）
**依赖：** T1–T7
**步骤：**
1. `ruff format --check .`、`ruff check .`、`pytest`、（可选）`mypy src/gcode`。
2. 端到端（openai 兼容端点，用 `.gcode/config.yaml`）：
   - 多轮（AC1）：问「读 `docs/ch03/spec.md`，再据其内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ 观察 `read_file` → `write_file` 跨多轮自动连环、状态栏用量增长、动态区轮次递增、最终答复。
   - 取消（AC10）：发一个会跑多步的任务，中途按 Esc / Ctrl+C → 回空闲态不退出 → 再正常发一条继续对话（验证历史未坏）。
   - 流出错（AC5）：临时改坏 `base_url` 或断网发一条 → 错误提示、程序不退出、改回后继续。
   - Plan Mode（AC13）：`/plan` → 问「给登录功能加单测的方案」→ 观察只出现 read/glob/grep 类工具与计划文本、无写/执行 → `/do` → 切回全工具按计划执行。
3. （可选）若有 anthropic 配置，重复多轮场景验证跨协议一致（AC14）。

**验证：** 全部命令通过、端到端各场景符合预期；密钥不回显（通读输出，AC/N7）。

## 执行顺序

```
T1 ─┬─ T5 ─┐
T2 ─┤      │
T3 ─┼──────┼─ T6 ─┬─ T7 ─┐
T4 ─┘      │      │      │
           └──────┘      └─ T8
```
（T1–T4 互相独立可并行；T5 依赖 T1；T6 依赖 T1/T2/T3/T4/T5；T7 依赖 T4/T6；T8 收尾全部。）
````

```markdown
# Agent Loop Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为；括号内为验证方式与对应需求。

## 实现完整性
- [ ] 多轮自动连环：需要连续两步工具的任务，Agent 无需中途催促即自动多轮执行工具直到给出最终答复（验证：`python -m gcode` 跑「读 A 文件 → 据内容新建 B 文件」，观察 `read_file` 与 `write_file` 跨多轮依次出现、最终答复）。(AC1/F1)
- [ ] 自然完成停止：模型给出无工具调用的纯文本即停（验证：`tests/test_agent.py` 场景 A 断言收到最终 `text` + `done=True`，循环不再发起请求）。(AC2/F2)
- [ ] 迭代上限兜底：模型反复调工具时达到 `MAX_ITERATIONS` 即停并提示，不无限循环（验证：`tests/test_agent.py` 场景 B 断言恰好上限轮后停 + `notice == NOTICE_MAX_ITER`）。(AC3/F2)
- [ ] 连续未知工具停止：连续 `MAX_UNKNOWN_RUN` 轮只产生未知工具调用即停；混入已注册工具则计数重置（验证：`tests/test_agent.py` 场景 C 两路断言）。(AC4/F2)
- [ ] 流出错恢复：provider 流出错时停止本轮、发 `err`、程序不退出（验证：端到端临时改坏 `base_url` 发一条，观察错误块 + 仍可继续；`tests/test_agent.py` 注入 err 脚本断言收到 err 后停）。(AC5/F2)
- [ ] 事件流完备：Agent 对外事件含文本 / 工具开始 / 工具结束 / `usage` / `iter` / `notice` / `done` / `err`（验证：`tests/test_agent.py` 断言一次多轮运行收集到的事件类型集合覆盖上述各类；端到端跑多轮任务，界面实时显示文本增量、工具进度、轮次、用量、最终答复，证明界面所需信息均来自事件流）。(AC6/F3)
- [ ] 流式收集双路：文本实时显示的同时，完整工具调用（拼齐 JSON 参数）被收集用于下一轮（验证：`tests/test_agent.py` 断言 `ToolCall.input`/`args` 完整可解析；端到端工具行参数与请求一致）。(AC7/F4)
- [ ] 保序分批并发：一次回复含多个工具时，连续只读并发执行、有副作用串行，结果按原序回灌（验证：`tests/test_agent.py` 场景 D 用插桩工具断言两只读的执行时间窗重叠（并发峰值 ≥2）、有副作用工具在其后开始、最终写入历史的工具结果顺序与模型调用序一致——按结果内容/ID 比对，与函数名无关）。(AC8/F5/N6)
- [ ] 取消历史一致：执行中取消后历史配对合法（有 tool_results、末尾 assistant 文本、无悬空 tool_use）（验证：`tests/test_agent.py` 场景 E 断言 `conv` 序列；端到端取消后再发一条不报 400）。(AC9/F6)
- [ ] 用户取消：流式态 Esc 或 Ctrl+C 中断本轮回空闲态、不退出；空闲态 Ctrl+C 退出（验证：端到端各按一次观察行为）。(AC10/F7)
- [ ] 用量展示：状态栏显示会话累计 token（输入/输出），随轮次增长更新（验证：端到端跑多轮观察状态栏数值递增）。(AC11/F8)
- [ ] 进度展示：流式态动态区显示当前迭代轮次（验证：端到端跑多轮任务观察「第 N 轮」递增）。(AC12/F9)
- [ ] Plan Mode：`/plan` 后只出现只读工具与计划文本、无写/执行；`/do` 切回全工具并立即按计划执行（验证：端到端 Plan Mode 场景；`tests/test_agent.py` 场景 F 断言 `Mode.PLAN` 下 fake 收到的 `tools` 仅只读）。(AC13/F10)

## 集成
- [ ] 跨协议一致：anthropic 与 openai（含兼容 `base_url`）跑同一多轮任务，触发/执行/回灌/用量/取消行为一致（验证：两种配置各跑多轮场景）。(AC14/F11/N3)
- [ ] 多轮历史正确携带：每轮 `assistant(tool_use)` 回合 + `tool_result` 回合按序入历史并被下一轮请求携带（验证：`tests/test_agent.py` 断言 `conv` 末尾序列；或抓请求体见历史增长）。(F6)
- [ ] 界面不阻塞：多轮循环与工具执行（含并发批）期间 spinner / 轮次 / 计时持续刷新（验证：跑含稍慢 `bash` 的任务，观察界面不冻结）。(N2)
- [ ] scrollback 顺序正确：跨多轮 preamble → 工具行 → 结果摘要 → 最终答复按序出现不交错，并发批的工具行按模型调用序排列（验证：跑一个含并发只读批 + 后续写的多轮任务，回滚 `RichLog` 肉眼核对各块严格按发生顺序连续、无交错、并发工具行顺序==调用序）。(N3)
- [ ] 结果体量受控：大文件 / 长输出 / 海量命中被工具级上限截断标注 `[truncated]`，多轮累积不撑爆（验证：多轮中读大文件 / 跑长输出命令观察截断）。(N4)
- [ ] 取消无泄漏：取消后无挂起 asyncio task / 无未关闭 queue（验证：`pytest tests/test_agent.py` 含取消用例（场景 E）通过；端到端反复触发取消后继续对话多次，进程内存/句柄稳定不增长）。(N5/N6)
- [ ] 系统提示体现 Agent 循环：问「你能做什么」答复体现可多步使用工具完成任务（验证：发一条询问观察答复）。(F3)

## 编译与测试
- [ ] `python -m gcode` 能正常启动（在合法配置下进入 TUI）。
- [ ] `ruff check .` 无告警。
- [ ] `ruff format --check .` 通过（或本地 `ruff format .` 已统一格式）。
- [ ] `pytest` 通过（`test_config`、`test_conversation`、`test_tool`、`test_agent` 等单测）。
- [ ] （可选）`mypy src/gcode` 通过。
- [ ] 密钥不回显：对话区与任何输出均不出现 `api_key`（验证：通读运行输出、检索无明文 key）。(N7)

## 端到端场景
- [ ] 场景 1（多轮连环）：openai 兼容端点 → 「读 `docs/ch03/spec.md`，再据内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ `read_file` → `write_file` 跨多轮自动出现 → 状态栏用量增长、动态区轮次递增 → 最终答复 → `/exit` 无残留。
- [ ] 场景 2（用户取消）：发一个多步任务，中途按 Esc（再试 Ctrl+C）→ 回空闲态不退出 → 再正常发一条继续对话（历史未坏，无 400）。
- [ ] 场景 3（流出错恢复）：临时改坏 `base_url` 发一条 → 错误块 + 程序不退出 → 改回后继续正常对话。
- [ ] 场景 4（Plan Mode）：`/plan` → 问一个改动类需求 → 只出现 read/glob/grep + 计划文本、无写/执行 → `/do` → 切回全工具并按计划执行（出现 write/edit/bash）。
- [ ] 场景 5（跨协议，若有 anthropic 配置）：切到 anthropic 配置重跑场景 1 → 多轮行为与 openai 一致。
- [ ] 场景 6（迭代上限）：主要由 `tests/test_agent.py` 场景 B 确定性验证；可选手动复现——临时把 `MAX_ITERATIONS` 改小（如 3）跑一个会多步调工具的任务，观察第 3 轮后停并显示 `NOTICE_MAX_ITER`、之后仍可继续对话。
- [ ] 场景 7（连续未知工具）：主要由 `tests/test_agent.py` 场景 C 确定性验证；可选手动复现——在 system prompt 临时引导模型调用一个不存在的工具名，观察连续 `MAX_UNKNOWN_RUN` 轮后停并显示 `NOTICE_UNKNOWN_TOOLS`、之后仍可继续对话。
```

### Java

```markdown
# Agent Loop Spec## 背景ch03 给 GCode 装上了工具系统：模型能读写改文件、执行命令、按模式找文件、搜代码内容。但编排是**单轮闭环**——请求#1 拿到一批工具调用 → 执行 → 结果回灌 → 请求#2 出最终答复就停，且续答里模型再次请求的工具被**直接丢弃**。模型只能「一步一停」，复杂任务（读完 A 才知道要改 B）得用户反复催。

ch04 给 GCode 装上 **Agent Loop**：模型自主循环——想 → 调工具 → 看结果 → 边做边调整，直到任务完成。从被动应答变成能自主干活的 Agent。这是从「能用工具」到「会自己干」的关键一跃。

## 目标- **ReAct 循环**：一轮轮调 LLM、执行工具、结果回血,直到模型不再请求工具。
- **多种停止条件**：自然完成、迭代上限（兜底安全网）、用户取消、连续请求未知工具、流出错。
- **异步事件流**：Agent 吐出文本 / 工具调用 / 工具结果 / Token 用量 / 迭代进度等事件，让 Agent 与界面彻底解耦。
- **流式收集双路**：一边实时把文本增量推给界面，一边攒出完整响应（含工具调用）供循环判断。
- **保序分批并发**：一次回复的多个工具调用按安全性分批——连续只读并发执行，有副作用串行执行，保持模型给出的相对顺序。
- **Plan Mode 两段式**：`/plan` 只放开只读工具让模型先出计划；`/do` 切回全工具并立即按计划执行。

## 功能需求

- F1: ReAct 主循环编排
  替换 ch03 的单轮闭环。每一轮：带工具定义发起请求 → 流式收集本轮响应 → 若模型请求了工具则执行并把结果回灌进历史，进入下一轮；若模型给出无工具调用的纯文本，则该文本即最终答复，循环结束。不再丢弃续答里的工具调用。

- F2: 多种停止条件
  循环在以下任一条件下停止，每种都干净收尾（对话历史保持合法 + 给界面明确信号）：
  1. 自然完成——模型回复不含工具调用，纯文本即最终答复。
  2. 迭代上限——达到内置上限兜底，避免失控；触顶时给出提示并停。
  3. 用户取消——见 F7。
  4. 连续未知工具——模型连续多轮只请求注册中心不存在的工具达阈值即停，避免对幻觉工具空转。
  5. 流出错——provider 流返回错误，停止本轮并提示，不崩溃、不中断会话。

- F3: 异步事件流（Agent ↔ 界面解耦）
  Agent 对外只吐事件，界面只消费事件、不感知循环内部细节。事件涵盖：文本增量、工具调用开始、工具调用结束（结果摘要 + 是否错误）、Token 用量、迭代进度、本轮结束、错误。

- F4: 流式收集双路
  每轮请求的流式响应走双路：一路把文本增量实时推给事件流（界面即时显示），一路累积完整文本并拼接出完整工具调用（含分片到达的 JSON 参数），供循环判断下一步。

- F5: 保序分批并发执行
  工具区分「只读 / 有副作用」两类。一次回复的多个工具调用按模型给出的顺序扫描：连续的只读调用合并为一个并发批并行执行，遇到有副作用调用则单独串行执行，保持整体相对顺序。批内并发完成后，结果按原始调用顺序回灌。每个工具仍受 per-tool 超时约束（沿用 ch03）。

- F6: 结果回灌与历史一致
  每轮的 assistant 回合（含工具调用）与工具结果回合按序写入对话历史，下一轮请求携带完整历史。任何提前终止（取消 / 上限 / 未知工具 / 出错）后，对话历史都保持合法——工具调用与结果配对、角色交替不被破坏，会话可继续。被取消时为已发起但未完成的工具调用补「已取消」结构化结果。

- F7: 用户取消本轮
  流式态下 Esc 或 Ctrl+C 中断当前 Loop：停止后续迭代、回到空闲态、不退出程序；空闲态 Ctrl+C 退出程序。中断后历史保持合法（见 F6），可继续对话。

- F8: Token 用量统计
  从 provider 流式响应中提取每轮的 token 用量（输入 / 输出），跨轮累加为会话累计量，在状态栏展示。

- F9: 迭代进度展示
  流式态动态区展示当前迭代轮次，让用户感知 Agent 正在多轮推进。

- F10: Plan Mode 两段式
  `/plan` 进入计划模式：仅注入只读工具定义 + 计划态系统提示（让模型先产出计划、不动手改动）；`/do` 切回全工具模式并立即用一条内置提示触发模型按上文计划执行。模式跨轮保持，直到再次切换。

- F11: 跨协议一致
  Anthropic 与 OpenAI（含兼容 base_url）两协议都跑通完整 Loop——多轮工具调用、用量提取、取消行为一致。

## 非功能需求

- N1: 工具执行超时——每个工具执行仍受 per-tool 超时约束（沿用 ch03 内置 30s，不可配）；超时以结构化结果回灌，不中断循环。
- N2: 界面不阻塞——多轮循环、工具执行（含并发批）期间界面持续响应，spinner、迭代进度、计时正常刷新，不冻结。
- N3: scrollback 顺序正确——跨多轮的 preamble 文本、工具行、结果摘要、最终答复按真实发生顺序提交到 scrollback；并发批的工具行按模型给出的调用顺序排列，整体不交错。
- N4: 结果体量受控——工具结果沿用 ch03 工具级截断（行 / 字符上限 + `[truncated]`）；多轮累积下上下文与界面均不被撑爆。
- N5: 取消及时、无泄漏——Esc / Ctrl+C 后尽快停止后续迭代（正在执行的工具靠 cancel flag / interrupt 尽力而为）；循环退出后不残留挂起的 virtual thread 或未关闭的 `SubmissionPublisher`。
- N6: 并发安全——并发批内的工具执行与结果收集无数据竞争（JUnit 并发用例通过；不依赖共享可变状态）。
- N7: 密钥不回显——沿用 ch03，对话区与任何输出均不出现 api_key。
- N8: 代码规范——`mvn spotless:check` 通过（google-java-format）、`mvn -q compile` 无告警（遵循项目 CLAUDE.md）。

## 不做的事

- 权限系统 / 交互式确认——工具执行（含写文件、执行命令）前不做授权确认（留待专门章节）。
- 上下文压缩 / 历史裁剪——多轮累积的历史不压缩、不裁剪，超长会话可能触及上下文上限（留待后续）。
- 工具执行沙箱 / 路径白名单——沿用 ch03，不限制工具只能在工作目录内操作。
- 工具调用与结果持久化——沿用 ch02/ch03，退出即丢。
- 迭代上限 / 超时配置化——均为内置常量，本章不通过配置调整。
- 跨批重排并发——只在「连续只读」批内并发；不把读写调用重排以追求最大并行度。
- 子 Agent / 任务分解工具（如 Task 工具）——不做。
- Plan Mode 的计划落盘 / 审批门工具（如 ExitPlanMode）——`/plan`、`/do` 为简单手动切换，不引入计划审批工具或计划持久化。
- Token 预算限制 / 按用量自动停止——只统计与展示用量，不按预算自动截断。
- 多模态——工具结果与对话均为文本。
- 流式工具结果——工具结果一次性回灌，不做流式产出。

## 验收标准

- AC1: 多轮自动连环——给需要连续两步工具的任务（如「读 `docs/ch03/spec.md`，再据其内容新建一个摘要文件」），Agent 自动多轮执行工具调用并回灌结果；当某轮模型不再请求工具、只输出纯文本时循环停止、该文本即最终答复，全程无需用户中途催。(F1)
- AC2: 自然完成——模型给出无工具调用的纯文本时循环立即停止，该文本即最终答复。(F2)
- AC3: 迭代上限兜底——构造模型反复调工具不收手的情形（或将上限调低），达到上限即停并提示，不无限循环。(F2)
- AC4: 连续未知工具停止——模型连续请求注册中心不存在的工具达阈值时，循环停止并提示。(F2)
- AC5: 流出错恢复——provider 流出错时停止本轮、给出错误提示、程序不退出，之后可继续正常对话。(F2)
- AC6: 事件流完备——Agent 对外事件涵盖文本、工具调用开始/结束、Token 用量、迭代进度、结束、错误；界面仅靠这些事件渲染。(F3)
- AC7: 流式收集双路——文本实时显示的同时，模型一次回复中完整的工具调用（含拼齐的 JSON 参数）被正确收集用于下一轮。(F4)
- AC8: 保序分批并发——一次回复含多个工具调用时，连续只读并发执行、有副作用串行执行，保持相对顺序；结果按原始顺序回灌。(F5)
- AC9: 历史一致——多轮的 assistant 与工具结果回合按序入历史；取消 / 上限 / 出错终止后历史仍配对合法，可继续对话（不出现连续同角色或悬空工具调用导致下一轮请求 400）。(F6)
- AC10: 用户取消——流式态 Esc 或 Ctrl+C 中断本轮、回空闲态、不退出；空闲态 Ctrl+C 退出程序。(F7)
- AC11: 用量展示——状态栏显示会话累计 token 用量（输入 / 输出），随轮次增长更新。(F8)
- AC12: 进度展示——流式态动态区显示当前迭代轮次。(F9)
- AC13: Plan Mode——`/plan` 后模型仅用只读工具产出计划、不产生写/执行类调用；`/do` 切回全工具并立即按上文计划执行（产生写/执行类工具调用）。(F10)
- AC14: 跨协议一致——anthropic 与 openai（兼容端点）两种配置都跑通完整多轮 Loop，触发 / 执行 / 回灌 / 用量 / 取消行为一致。(F11)
```

````markdown
# Agent Loop Plan

> 基于已批准的 spec.md。本文档与语言相关（Java 21）。SDK 类型已对 `com.anthropic:anthropic-java` 2.x、`com.openai:openai-java` 4.x 核对（grounding 实测）。

## 架构概览ch04 不新增包，在 ch03「tool / agent / llm / conversation / prompt / tui」之上**扩展**：

- **dev.gcode.agent（重写 `Agent.run`）**：把 ch03 的「请求#1 → 执行 → 请求#2 → 停」改为真正的 ReAct 循环——`for` 迭代直到自然完成 / 上限 / 取消 / 连续未知工具 / 出错。新增保序分批并发执行、迭代进度与用量事件、终止时的历史一致性收尾、Plan/Normal 两种模式。
- **dev.gcode.llm（扩展）**：`StreamEvent` 新增 `Usage` 子类型；`Provider.stream` 增 `String systemSuffix` 形参（Plan Mode 系统提示后缀）；两适配器在流结束后上抛本轮 token 用量、把 `systemSuffix` 拼到内置系统提示后；OpenAI 打开 `ChatCompletionStreamOptions.includeUsage`。
- **dev.gcode.tool（扩展）**：`Tool` 接口增 `boolean readOnly()`；6 个工具各实现；`Registry` 增 `readOnlyDefinitions()` 与 `isReadOnly(name)`。
- **dev.gcode.conversation（扩展）**：增 `Optional<Role> lastRole()`（终止收尾判断角色尾巴）。
- **dev.gcode.prompt（扩展）**：增 `PLAN_MODE_REMINDER`（计划态系统后缀）与 `EXECUTE_DIRECTIVE`（`/do` 触发执行的用户消息）；`SYSTEM_PROMPT` 增补「持续工作直到任务完成」的 Agent 循环约定。
- **dev.gcode.tui（扩展）**：`submit` 识别 `/plan`、`/do`；引入 per-turn 取消标志位与 cancel 钩子；事件订阅器处理用量 / 进度 / 通知 / 多个并发工具；按键处理拆分 Esc / Ctrl+C；状态栏显示模式与累计用量、动态区显示迭代轮次。

依赖方向不变、无环：`tool → llm`；`conversation → llm`；`agent → {llm, tool, conversation}`；`tui → {agent, tool, conversation, llm, prompt}`；`llm → {config, prompt}`。

## 核心数据结构### llm 包（`StreamEvent` 扩展）

```java
package dev.gcode.llm;

// Usage 协议无关地承载一轮请求的 token 用量。
public record Usage(long inputTokens, long outputTokens) {}

// StreamEvent 扩展：在 TextDelta / ToolCalls / Done / Failed 之外，
// turn 结束时一次性上抛 UsageEvent（Done 之前发出）。
public sealed interface StreamEvent
        permits StreamEvent.TextDelta,
                StreamEvent.ToolCalls,
                StreamEvent.UsageEvent,
                StreamEvent.Done,
                StreamEvent.Failed {

    record TextDelta(String text) implements StreamEvent {}
    record ToolCalls(java.util.List<ToolCall> calls) implements StreamEvent {}
    record UsageEvent(Usage usage) implements StreamEvent {} // 新增
    record Done() implements StreamEvent {}
    record Failed(Throwable error) implements StreamEvent {}
}
```

`Provider.stream` 签名变更（新增第 3 形参）：

```java
// systemSuffix 非空时拼接到内置 system prompt 之后（Plan Mode 计划态约束）；为空即普通模式。
java.util.concurrent.Flow.Publisher<StreamEvent> stream(
        java.util.List<Message> messages,
        java.util.List<ToolDefinition> tools,
        String systemSuffix);
```

`Message`/`ToolCall`/`ToolResult`/`ToolDefinition` 与 `Role.TOOL` 沿用 ch03，不变。

### tool 包（接口扩展）

```java
// Tool 接口新增 readOnly：true=只读工具（可并发执行 & Plan Mode 放行）。
public interface Tool {
    String name();
    String description();
    java.util.Map<String, Object> parameters();
    boolean readOnly(); // 新增
    Result execute(CancelToken cancel, com.fasterxml.jackson.databind.JsonNode args);
}
```

只读分类（依据语义）：`ReadFileTool` / `GlobTool` / `GrepTool` → `true`；`WriteFileTool` / `EditFileTool` / `BashTool` → `false`（`BashTool` 可执行任意副作用命令，保守归为有副作用、串行执行）。

`Registry` 新增：

```java
// Plan Mode：只导出 readOnly()==true 的工具定义。
public java.util.List<ToolDefinition> readOnlyDefinitions();

// 分批判定；未知工具返回 false（按串行处理）。
public boolean isReadOnly(String name);
```

### agent 包（事件模型扩展 + `run` 重写）

```java
package dev.gcode.agent;

// Usage 一轮请求的 token 用量（透传 llm.Usage 的语义）。
public record Usage(long input, long output) {}

// Mode 区分普通模式与计划模式。
public enum Mode { NORMAL, PLAN }

// Event 对外事件流元素，消费者据子类型分派渲染（sealed + pattern matching）。
public sealed interface Event
        permits Event.TextDelta,
                Event.Tool,
                Event.UsageReport,
                Event.Iter,
                Event.Notice,
                Event.Done,
                Event.Failed {

    record TextDelta(String text) implements Event {}              // 模型文本增量（preamble 或最终答复）
    record Tool(ToolEvent toolEvent) implements Event {}           // 工具调用开始/结束（沿用 ch03）
    record UsageReport(Usage usage) implements Event {}            // 本轮 token 用量（每轮 stream 结束后一次）
    record Iter(int iter) implements Event {}                      // 进入第 iter 轮迭代（进度提示）
    record Notice(String message) implements Event {}              // 系统提示（停止原因等）；仅 UI 展示，不入历史
    record Done() implements Event {}                              // 本轮（整个 Loop）结束
    record Failed(Throwable error) implements Event {}             // 出错（不中断会话）
}

// Agent.run 执行 Agent Loop，返回事件 Publisher；mode 决定工具集与系统后缀。
public java.util.concurrent.Flow.Publisher<Event> run(
        dev.gcode.conversation.Conversation conv,
        Mode mode,
        CancelToken cancel);
```

`ToolEvent`、`Phase`(START/END)、`Agent`、`Agent(provider, registry)` 构造沿用 ch03。`run` 签名新增 `mode` 形参与 per-turn `CancelToken`。

`Agent` 构造沿用 ch03：`public Agent(Provider provider, Registry registry)`。`mode` 为 `run` 的每次调用入参，不写入 `Agent` 状态（同一 `Agent` 可被不同 mode 复用）。

迭代、停止常量与提示文案（内置，不可配）：

```java
final class AgentConstants {
    static final int MAX_ITERATIONS  = 25; // 迭代上限兜底（F2）
    static final int MAX_UNKNOWN_RUN = 3;  // 连续「整轮只产生未知工具调用」的迭代数上限（F2）

    // 停止/收尾提示文案——既作为 Event.Notice 推给 UI，
    // 也作为 ensureAssistantTail 写入历史的兜底文本。
    static final String NOTICE_MAX_ITER       = "(已达最大迭代轮数 25,自动停止;可继续发消息推进。)";
    static final String NOTICE_UNKNOWN_TOOLS  = "(连续多轮只请求到未注册的工具,自动停止。)";
    static final String NOTICE_STREAM_ERR     = "(请求出错,本轮已中断。)";
    static final String NOTICE_CANCELLED      = "(已取消。)";
}
```

`CancelToken` 为本章引入的轻量取消句柄（`volatile boolean cancelled` + `cancel()` 方法 + 可选回调），取代 Go 的 `ctx.Done()`；适配器内的虚拟线程在每个流事件回调里轮询 `cancel.isCancelled()`，工具执行同样接收 `CancelToken` 并在阻塞处定期检查。

## 模块设计### dev.gcode.agent（核心：`run` 重写）**职责：** ReAct 循环编排（F1/F2）、保序分批并发执行（F5）、事件流（F3/F8/F9）、终止历史一致性（F6）、Plan/Normal 模式（F10）。
**对外接口：** `Agent`、构造函数、`run(conv, mode, cancel)`、`Event` sealed 接口、`ToolEvent`、`Phase`、`Mode`、`Usage`、`CancelToken`。
**依赖：** `llm`、`tool`、`conversation`、`java.util.concurrent.Flow`、`java.util.concurrent.SubmissionPublisher`、`java.util.concurrent.StructuredTaskScope`（或 `CompletableFuture` 集合，二选一，见技术决策）。

**`run` 算法（virtual thread 内执行，try-with-resources 关 `SubmissionPublisher<Event> bus`）：**

1. 按 `mode` 取工具集与系统后缀：
   - `Mode.PLAN`   → `defs = registry.readOnlyDefinitions()`；`suffix = Prompt.PLAN_MODE_REMINDER`。
   - `Mode.NORMAL` → `defs = registry.definitions()`；`suffix = ""`。
2. `int unknownRun = 0;`
3. `for (int iter = 1; iter <= MAX_ITERATIONS; iter++)`：
   1. `emit(new Event.Iter(iter))`（进度，F9）；emit 返回 false（已取消）→ `finishCancelled(conv)`、`return`。
   2. `StreamOutcome out = streamOnce(conv, defs, suffix, cancel, bus);`
      - `out.failed()` 且 `cancel.isCancelled()` → `finishCancelled(conv)`、`return`。
      - `out.failed()` 且未取消（流出错，`Event.Failed` 已在 `streamOnce` 内发出）→ `ensureAssistantTail(conv, NOTICE_STREAM_ERR)`、`return`。
   3. `if (out.usage() != null) emit(new Event.UsageReport(new Usage(out.usage().inputTokens(), out.usage().outputTokens())))`（F8）。
   4. **无工具** `out.calls().isEmpty()`：`conv.addAssistant(ensureFinal(bus, out.text()))`；`emit(new Event.Done())`；`return`（自然完成，F2-1）。
   5. **有工具**：`conv.addAssistantWithToolCalls(out.text(), out.calls())`。
   6. 统计未知工具：`if (allUnknown(out.calls())) unknownRun++; else unknownRun = 0;`
   7. `BatchOutcome batch = executeBatched(out.calls(), cancel, bus);`（保序分批并发，F5）。
   8. `conv.addToolResults(batch.results())`（无论是否取消都回灌，含已取消占位，F6）。
   9. `if (!batch.completed())`（执行中被取消）→ `ensureAssistantTail(conv, NOTICE_CANCELLED)`、`return`。
   10. `if (unknownRun >= MAX_UNKNOWN_RUN)` → `emit(new Event.Notice(NOTICE_UNKNOWN_TOOLS))`；`ensureAssistantTail(conv, NOTICE_UNKNOWN_TOOLS)`；`emit(new Event.Done())`；`return`（F2-4）。
4. 循环正常走完（触达上限）：`emit(new Event.Notice(NOTICE_MAX_ITER))`；`ensureAssistantTail(conv, NOTICE_MAX_ITER)`；`emit(new Event.Done())`（F2-2）。

**`streamOnce(conv, defs, suffix, cancel, bus) → StreamOutcome(text, calls, usage, failed)`：**
订阅 `provider.stream(conv.messages(), defs, suffix)`（`Flow.Publisher<llm.StreamEvent>`），用一个内部 `Flow.Subscriber` 同步消费：
- `StreamEvent.Failed f` → `emit(new Event.Failed(f.error()))`、返回 `failed=true`。
- `StreamEvent.UsageEvent u` → 记录 `usage = u.usage()`（不立即 emit，由 `run` 在拿到后统一 emit）。
- `StreamEvent.ToolCalls tc` → `calls.addAll(tc.calls())`。
- `StreamEvent.TextDelta d` → 累积 `text` 并 `emit(new Event.TextDelta(d.text()))`；emit 失败→标记 `failed=true`。
- `StreamEvent.Done` → 结束订阅。
循环结束后若 `cancel.isCancelled()` 即视为失败；否则返回 `new StreamOutcome(text.toString(), calls, usage, false)`。

**`executeBatched(calls, cancel, bus) → BatchOutcome(results, completed)`：**
保序分批（F5）。`ToolResult[] results = new ToolResult[calls.size()];` 从 `i=0` 逐段扫描：
- 当前 `calls.get(i)` 只读 → 向前吃连续只读得最长区间 `[i, j)`（`j` 为首个非只读或末尾），**并发**执行该批：用 `Thread.ofVirtual().start(() -> ...)` 为每个调用起一个虚拟线程，线程内 `var toolCancel = cancel.withTimeout(Tool.DEFAULT_TIMEOUT)`（基于 `ScheduledExecutorService` 调度的派生 token）后 `registry.execute(toolCancel, ...)`，结果写入**自己下标** `results[k]`（互不重叠，无锁）；用 `CountDownLatch(j - i)` 等齐所有线程。`i = j`。
- 当前 `calls.get(i)` 非只读 → **串行**执行单个 `calls.get(i)`（同样 `cancel.withTimeout(Tool.DEFAULT_TIMEOUT)`），写 `results[i]`。`i++`。
- 每段开始执行前先判 `cancel.isCancelled()`：给区间内尚未执行的 call 填「已取消」结果（`new ToolResult(callId, NOTICE_CANCELLED, true)`），其余沿用已得结果，`return new BatchOutcome(List.of(results), false)`。
- 全部完成 `return new BatchOutcome(List.of(results), true)`。

> 超时口径：每个工具各拿一个 `DEFAULT_TIMEOUT`（30s）派生 cancel token，互不相加——并发批的整体上限仍是单个 30s（N1）。派生 token 都挂在 per-turn `cancel` 下，用户取消时一并触发，工具尽快返回。

事件与顺序（满足 N3 顺序、N2 不阻塞、N6 无竞争）：
- 单个串行工具：`emit(Event.Tool{Start})` → 执行 → `emit(Event.Tool{End})`（沿用 ch03 时序，动态区显示该工具 Running）。
- 并发批：**先**按序 `emit(Event.Tool{Start})` 区间内每个工具（动态区列出多个在执行的工具行）→ 并发执行 → **再**按原始顺序 `emit(Event.Tool{End})` 每个工具（逐个把工具行 + 结果摘要提交 scrollback）。即「开始事件按序、结束事件按序」，并发只发生在执行环节，事件顺序始终是调用序，scrollback 不交错。
- 并发安全：每个虚拟线程只写自己下标的 `results[k]`（不同下标互不重叠），不触碰 `conv`；`conv.addToolResults` 由 `run` 主流程在 `CountDownLatch.await()` 后串行调用。Token 用量累计在 TUI 侧串行处理。

**辅助函数：**
- `emit(bus, event) → boolean`：沿用 ch03——`if (cancel.isCancelled()) return false; bus.submit(event); return true;`。返回 false 当且仅当 per-turn cancel 被触发（`SubmissionPublisher` 由 `run` 自己持有并 try-with-resources 关闭，不会在提交中被外部关）。调用方据 false 提前收尾。
- `allUnknown(calls)`：对每个 call 用 `registry.get(call.name())` 判断，**全部** `Optional.isEmpty()` 才返回 true；任一已注册即 false（混入已知工具视为有进展，计数重置）。不能用 `isReadOnly`（未知工具它也返回 false，会与有副作用工具混淆）。
- `ensureFinal(bus, text)`：沿用 ch03——`text` 非空原样返回；为空则 emit 占位提示并返回占位文本（避免空 assistant 回合破坏下一轮请求）。
- `ensureAssistantTail(conv, fallback)`：若 `conv.lastRole().orElse(null) != Role.ASSISTANT`（含空历史、末尾为 user 或 `Role.TOOL`），调 `conv.addAssistant(fallback)`，保证历史以 assistant 文本回合收尾（F6：取消/出错/上限后角色仍交替，下一轮请求不报 400）。
- `finishCancelled(conv)`：取消路径统一收尾——`ensureAssistantTail(conv, NOTICE_CANCELLED)`、`return`（**不 emit**，因 cancel 已触发 emit 必失败；`bus` 经 try-with-resources 关闭，TUI 由订阅器收到 `onComplete()` 即视为结束）。

> 终止优先级：执行中取消（`batch.completed()==false`）是**最高优先级**终止——立即 `ensureAssistantTail` 并 `return`，**跳过**未知工具计数与迭代上限检查。

### dev.gcode.llm（扩展）**职责：** 协议无关请求/响应 + 两协议工具调用全流程（沿用 ch03）+ 本轮用量上抛（F8）+ 系统后缀（F10）。

**`StreamEvent.java`：** sealed 接口新增 `UsageEvent(Usage usage)` 子类型；新增 `Usage` record。

**`Provider.java`：** `stream` 增 `String systemSuffix` 形参（更新接口 Javadoc 说明 systemSuffix 语义）。

**`AnthropicProvider.java`：**
- 系统提示：`MessageCreateParams.system(...)` 由硬编码 `Prompt.SYSTEM_PROMPT` 改为 `effectiveSystem(suffix)`——`suffix==""` 时单块 `Prompt.SYSTEM_PROMPT`；非空时拼成 `Prompt.SYSTEM_PROMPT + "\n\n" + suffix`（单 `TextBlockParam`，避免多块边界差异）。
- 用量：SDK 的异步流式订阅 `onCompleteFuture` 完成且无异常后，在上抛 `ToolCalls` / `Done` 之前从累加器 `MessageAccumulator` 读 `accumulator.message().usage()`：`pub.submit(new StreamEvent.UsageEvent(new Usage(usage.inputTokens(), usage.outputTokens())))`（usage 仅在流结束后完整）。
- 历史含工具交互时 thinking 已自动关闭（ch03 既有逻辑），多轮续答沿用，无需改动。

**`OpenAIProvider.java`：**
- 请求构造增 `params.streamOptions(ChatCompletionStreamOptions.builder().includeUsage(true).build())`（不开则流式 usage 为空）。
- 系统提示：`toOpenAIMessages` 接收 `suffix`，把首条 system 消息文本由 `Prompt.SYSTEM_PROMPT` 改为拼接 `suffix`（非空时 `+"\n\n"+suffix`）。
- 用量：流结束后从累加器读 `CompletionUsage`：`pub.submit(new StreamEvent.UsageEvent(new Usage(usage.promptTokens(), usage.completionTokens())))`。

### dev.gcode.tool（扩展）

- `Tool` 接口加 `boolean readOnly()`；6 个工具各加一行实现（read/glob/grep 返回 true，write/edit/bash 返回 false）。
- `Registry.readOnlyDefinitions()`：仿 `definitions()`，仅收 `tools.get(name).readOnly()==true` 的项，保持注册顺序。
- `Registry.isReadOnly(name)`：`Optional<Tool> t = get(name); return t.isPresent() && t.get().readOnly();`（未知工具 false）。
- `execute`、`Tool.DEFAULT_TIMEOUT`、6 工具的执行逻辑均不变。

### dev.gcode.conversation（扩展）

```java
// lastRole 返回最后一条消息的角色;空历史返回 Optional.empty()。
public java.util.Optional<Role> lastRole();
```
其余沿用 ch03。

### dev.gcode.prompt（扩展）

```java
// PLAN_MODE_REMINDER:Plan Mode 系统提示后缀,拼接到 SYSTEM_PROMPT 之后。
public static final String PLAN_MODE_REMINDER =
        "You are currently in PLAN MODE. You may use ONLY the read-only tools "
        + "(read_file, glob, grep) to investigate the codebase. You must NOT write files, edit files, "
        + "or run shell commands. Produce a clear, step-by-step plan for the task, then stop and wait for "
        + "the user to approve it with /do before doing any work.";

// EXECUTE_DIRECTIVE:/do 注入的用户消息——指示模型按上文已确认的计划开始执行,可使用全部工具。
public static final String EXECUTE_DIRECTIVE = "请按上面的计划开始执行。";
```

`SYSTEM_PROMPT` 增补一句 Agent 循环约定（追加到现有文案）：`"Keep using tools across multiple steps to make progress, and only give your final concise answer once the task is complete."`（中文项目里保持英文 system prompt 风格，与 ch03 现有 `SYSTEM_PROMPT` 一致）。

### dev.gcode.tui（扩展）**`TuiApp` 新增字段：**
- `Mode mode`——当前模式（默认 `Mode.NORMAL`），`/plan`、`/do` 切换，跨轮保持。
- `int iter`——当前迭代轮次（进度显示），每 `Event.Iter` 更新，`finishTurn` 归零。
- `long usageIn`、`long usageOut`——会话累计 token 用量，每个 `Event.UsageReport` 累加。
- `List<ToolDisplay> curTools`——替换 ch03 的单个 `ToolDisplay curTool`，支持并发批多个在执行的工具行。
- `CancelToken turnCancel`——本轮取消句柄（每次 `submit` 重新建），Esc / Ctrl+C 触发；程序级退出走全局 shutdown hook。

**`submit`（`StreamPump.java` 或 `TuiApp.onSubmit`）：**
1. `/exit` → 退出（沿用）。
2. `/plan` → `this.mode = Mode.PLAN`；提交一行提示块到 scrollback（如「已进入计划模式（只读工具）」）；回空闲态。
3. `/do` → `this.mode = Mode.NORMAL`；`conv.addUser(Prompt.EXECUTE_DIRECTIVE)`；走与普通提交相同的启动流程（不把 `/do` 本身入历史）。
4. 普通文本 → `conv.addUser(text)`。
5. 启动：`this.turnCancel = new CancelToken()`；`Flow.Publisher<Event> events = new Agent(provider, registry).run(conv, this.mode, this.turnCancel)`；`state = SessionState.STREAMING`；`iter = 0`；用 `events.subscribe(new StreamPump(this))` 接管事件。

**`StreamPump.onNext` 分派（用 switch pattern matching）：**
按事件子类型分派——
- `Event.Failed f` → 红色错误块入 scrollback、回 IDLE。
- `Event.Tool t` →
  - `Phase.START`：若 `curReply` 非空先把 preamble 提交 scrollback 并清空；`curTools.add(new ToolDisplay(name, args))`。
  - `Phase.END`：**FIFO 弹出队首** `curTools.remove(0)`（因 agent 保证 START 与 END 都按调用序发出，结束序 == 入队序，弹首即对应工具，无需按 name 匹配，重名工具也不会错位）；用其 args 定型工具行，按序 append toolLine + toolResultSummary 到 scrollback。
- `Event.UsageReport u` → `usageIn += u.usage().input(); usageOut += u.usage().output();`
- `Event.Notice n` → 灰色系统提示块入 scrollback。
- `Event.Iter i` → `this.iter = i.iter();`
- `Event.Done` → 把 `curReply` 用 flexmark 渲染落 scrollback；`finishTurn()`。
- `Event.TextDelta d` → 累积 `curReply`，刷新 streamingLabel。

> Lanterna UI 线程切换：每个 onNext 内部都用 `gui.getGUIThread().invokeLater(() -> ...)` 把 UI 改动切回 GUI 线程，业务态字段（`iter`、`usageIn/usageOut`、`curTools`）也在 GUI 线程内变更——避免与渲染竞争（N6）。

**按键（Lanterna `KeyStroke` 全局过滤）：**
- `Ctrl+C`：`SessionState.STREAMING` → `turnCancel.cancel()`（取消本轮，不退出），继续等 onComplete；其余状态 → `screen.stopScreen(); System.exit(0)`（退出）。
- `Esc`：`SessionState.STREAMING` → `turnCancel.cancel()`；其余忽略。

**`View.java`：**
- `statusBar`：左侧在 provider 名后附模式标记（`Mode.PLAN` 显示「PLAN」徽标）；右侧在 model 名旁附累计用量 `↑{in} ↓{out} tok`（数值用紧凑格式，如 `1.2k`）。保持单行。
- 流式动态区：`curTools` 非空时逐行渲染 `● name(args)` + Running…（多个并发工具多行）；否则渲染「Imagining… (Ns · 第 N 轮)」（`iter>0` 时附轮次）。
- `toolLine` / `toolResultSummary` 沿用 ch03。

**`finishTurn`：** 清 `curReply`、`curTools.clear()`、`iter=0`、`turnCancel=null`，回 `SessionState.IDLE`（`mode`、`usageIn/usageOut` 不清——跨轮保持）。

## 模块交互

```
用户提交 /do 或普通文本
  └─ TuiApp.onSubmit:
       ├─ /plan → mode=PLAN,回 IDLE
       ├─ /do   → mode=NORMAL; conv.addUser(EXECUTE_DIRECTIVE)
       ├─ 文本  → conv.addUser(text)
       └─ turnCancel = new CancelToken();
          events = new Agent(provider, registry).run(conv, mode, turnCancel)
            └─ Agent.run (virtual thread, ReAct 循环):
                 for iter:
                   ├─ emit Iter
                   ├─ 请求: provider.stream(conv.messages(), defs(mode), suffix(mode))
                   │     └─ 适配器: 注入 tools + (SYSTEM_PROMPT+suffix) → 流式拼接
                   │          → StreamEvent.TextDelta / ToolCalls / UsageEvent / Done|Failed
                   │     → agent 转发 TextDelta(preamble)、收集 calls、记录 usage
                   ├─ emit UsageReport
                   ├─ 无 calls → conv.addAssistant(final); emit Done; 停
                   └─ 有 calls:
                        ├─ conv.addAssistantWithToolCalls(preamble, calls)
                        ├─ executeBatched: 连续只读并发 / 有副作用串行
                        │     (Start 事件按序 → 执行 → End 事件按序)
                        ├─ conv.addToolResults(results)
                        └─ 下一轮 iter
  └─ StreamPump.onNext (pattern match):
       TextDelta→curReply;Tool→curTools/scrollback;UsageReport→累加;
       Iter→this.iter;Notice→灰提示;Done→提交最终答复+finishTurn
  └─ Ctrl+C / Esc(streaming) → turnCancel.cancel() → run 收尾历史 → bus.close()
       → StreamPump.onComplete → finishTurn → IDLE
```

并发模型：`conv` 任一时刻只被 `run` 的主虚拟线程触碰（`onSubmit` 在交给 `run` 前 `addUser`，之后不再触碰；执行批的工作线程只写各自 `results[k]`，不碰 `conv`）。`messages()` 返回不可变副本。TUI 仅按事件渲染。满足 N2/N6。

## 文件组织

```
gcode/
├── pom.xml                         — 修改：新增 JUnit `assertj`（可选）以便并发断言；其余依赖沿用
├── src/main/java/dev/gcode/
│   ├── llm/
│   │   ├── StreamEvent.java        — 修改:sealed 新增 UsageEvent;新增 Usage record
│   │   ├── Provider.java           — 修改:stream 加 systemSuffix 形参
│   │   ├── AnthropicProvider.java  — 修改:effectiveSystem(suffix);流结束上抛 Usage
│   │   └── OpenAIProvider.java     — 修改:streamOptions.includeUsage;toOpenAIMessages 拼 suffix;上抛 Usage
│   ├── tool/
│   │   ├── Tool.java               — 修改:接口加 readOnly()
│   │   ├── Registry.java           — 修改:readOnlyDefinitions、isReadOnly
│   │   └── {ReadFileTool,WriteFileTool,EditFileTool,BashTool,GlobTool,GrepTool}.java
│   │                               — 修改:各加 readOnly() 实现
│   ├── agent/
│   │   ├── Agent.java              — 重写:ReAct 循环、Mode、executeBatched、UsageReport/Iter/Notice 事件、历史收尾
│   │   ├── Event.java              — 修改:sealed 接口新增 UsageReport、Iter、Notice 子类型(以及 Usage record)
│   │   ├── Mode.java               — 新增:enum {NORMAL, PLAN}
│   │   └── CancelToken.java        — 新增:per-turn 取消句柄(volatile + 派生 timeout)
│   ├── conversation/
│   │   └── Conversation.java       — 修改:lastRole()
│   ├── prompt/
│   │   └── Prompt.java             — 修改:PLAN_MODE_REMINDER、EXECUTE_DIRECTIVE;SYSTEM_PROMPT 增循环约定
│   └── tui/
│       ├── TuiApp.java             — 修改:字段增 mode/iter/usage/curTools/turnCancel;按键拆分 Esc/Ctrl+C
│       ├── StreamPump.java         — 修改:onNext 用 switch pattern match 分派 UsageReport/Iter/Notice/Tool/Text
│       └── View.java               — 修改:状态栏模式徽标+累计用量;动态区迭代轮次+多并发工具行
├── src/test/java/dev/gcode/
│   ├── agent/AgentTest.java        — 扩展:多轮 fake provider(`List<List<StreamEvent>>` 多次 stream)、并发分批、停止条件、Plan 工具集
│   └── conversation/ConversationTest.java
│                                   — 扩展:lastRole 断言
└── src/test/java/dev/gcode/smoke/SmokeMain.java
                                    — 修改:Agent.run 调用处补 mode 实参(Mode.NORMAL)
```

> 注：`Main.java` 已在 ch03 注入 `Registry`，ch04 无需改动；`mode` 状态存于 `TuiApp`，不经 `Main`。

### 签名变更的调用方清单（实测核对，确保编译不漏）

ch04 改了两个签名，必须同步所有调用方/实现方，否则编译断：

- **`Provider.stream` 增 `String systemSuffix`（第 3 形参）**：
  - 实现方：`AnthropicProvider`、`OpenAIProvider`。
  - 调用方：`Agent.streamOnce`（唯一直接调用方）。
  - 测试实现方：`AgentTest.FakeProvider#stream`（也实现该接口，签名须同步）。
  - **`SmokeMain` 不直接调 `stream`**（它走 `Agent.run`），无需为 `systemSuffix` 改动。
- **`Agent.run` 增 `Mode mode` 与 `CancelToken cancel`（新增第 2、3 形参）**：
  - 调用方：`TuiApp` / `StreamPump` 内（`onSubmit`）、`SmokeMain`（旧调用 `agent.run(conv)`）、`AgentTest`（各用例）。三者都要补 `mode` / `cancel` 实参（smoke / 旧用例传 `Mode.NORMAL` + `new CancelToken()`）。

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Loop 放哪 | 重写 `Agent.run` 为循环，签名加 `mode` 与 `CancelToken` | 循环编排天然属 agent 包；TUI 维持纯渲染器。`run` 已返回事件 `Flow.Publisher`，循环只是把单轮的两次 `streamOnce` 推广为 `for`，改动收敛在一个包。 |
| 不用 SDK 内置 tool-runner | 坚持手写循环 + stable streaming | 沿用 ch03 决策；自写循环才能精确控制停止条件、保序分批、取消与历史收尾，SDK 的自动 runner 把这些黑盒化。 |
| 停止条件之「连续未知工具」 | 连续 `MAX_UNKNOWN_RUN=3` 轮「整轮只产生未知工具调用」即停 | 单次未知工具靠 registry 的「未知工具」结构化错误回灌即可让模型纠偏；只有连续多轮全错才说明在对幻觉工具空转，需兜底。混入任一已注册工具即重置计数（视为有进展）。 |
| 迭代上限值 | `MAX_ITERATIONS=25`，内置常量 | 兜底安全网，避免失控烧 token；25 足够覆盖正常多步任务。spec 明确不配置化，与 ch03 超时不配化一致。 |
| 并发分批粒度 | 「连续只读」合批并发，有副作用单个串行，保持调用序 | 用户选定的「保序分批」：read 之后的 write 不会被提前；相邻只读才并发加速。`BashTool` 保守归有副作用（可含任意写操作）。 |
| 并发原语 | virtual thread + `CountDownLatch` + 每个 worker 独占下标 | virtual thread 起停成本极低、阻塞工具调用天然受益；只写自己下标的 `results[k]` 无需锁；`CountDownLatch` 在主流程汇合。备选 `StructuredTaskScope` 仍为 incubator，先不用。 |
| 并发的事件顺序 | 开始事件按序、结束事件按序，并发只在执行环节 | 满足 N3（scrollback 不交错）：UI 看到的工具行顺序始终是模型调用序；并发对用户透明，只体现为更快。每个 worker 只写自己下标的 `results[k]`，无竞争（N6）。 |
| 取消机制 | per-turn `CancelToken`；Esc / Ctrl+C(streaming) 取消，Ctrl+C(idle) 退出 | Java 没有 Go 的 ctx 树，自定义轻量 token（`volatile boolean cancelled` + 派生 timeout + 可选回调）即可表达「取消本轮但不退程序」语义。工具与 SDK 订阅在阻塞处轮询 / 调 `subscription.cancel()`。 |
| 取消后历史一致 | 已发起工具补「已取消」结果 + `ensureAssistantTail` 收尾 | F6：取消可能停在「assistant 含 tool_use 但缺 tool_result」或「user 之后无 assistant」处；补齐工具结果 + 保证 assistant 文本尾巴，下一轮请求才不会因悬空 tool_use / 连续同角色被 API 拒（400）。 |
| 用量提取位置 | 适配器在流结束后从累加器读 usage 并经 `StreamEvent.UsageEvent` 上抛 | 两 SDK 的流式 usage 都只在流结束的累加器里完整（Anthropic `MessageAccumulator.message().usage()`、OpenAI 需 `includeUsage=true` 后读累加器 `CompletionUsage`）；逐 delta 不含。统一在 Done 前发一次。 |
| 累计用量口径 | 状态栏显示「会话累计计费 token」= 每轮 input+output 之和 | 多轮 Loop 每轮都重发完整历史，各轮 input 重复计费；按轮累加正是实际消耗/成本口径，对用户最有意义。 |
| Plan Mode 系统提示注入 | `Provider.stream` 加 `String systemSuffix` 形参 | 系统提示在适配器内注入，要让计划态约束生效必须穿过 `stream`。加一个字符串形参最小且显式；备选「请求 options record」更可扩展但改动面更大，YAGNI 下不引入。 |
| Plan Mode 工具集 | 计划态只注入 `readOnlyDefinitions()` | 物理上不给模型写/执行工具，即便提示被忽略也无法改动；只读分类靠 `Tool.readOnly()`。 |
| `/do` 语义 | 切回 Normal + 注入 `EXECUTE_DIRECTIVE` 用户消息 + 立即启动 Loop | 用户选定「切回全工具并立即执行」；复用已在历史里的计划，`/do` 不入历史，只把执行指令作为用户消息驱动模型开干。 |
| 模式状态存放 | 存于 `TuiApp`，不进 `Conversation` | `Conversation` 是历史、`messages()` 返回副本，放不住可变模式；模式是会话级 UI 状态，跨轮保持，归 TUI 最自然。 |
| 多并发工具的 UI | `List<ToolDisplay> curTools` 取代单个 `ToolDisplay` | 并发批同时有多个工具在跑，动态区需多行展示；结束事件按序逐个落 scrollback。 |
| 进度事件 | 每轮起始 emit `Event.Iter(n)`，UI 显示「第 N 轮」 | F9 让用户感知多轮推进；用 sealed 子类型分派，与 ch03 的事件惯例一致。 |
| 通知 vs 历史 | 上限/未知工具的提示同时 emit `Event.Notice` 与 `ensureAssistantTail` 写入 assistant 历史 | UI 要让用户看到为何停；写入历史是为满足 `ensureAssistantTail`（角色交替），二者用同一文案，避免历史里留空 assistant 回合。 |
````

````markdown
# Agent Loop Tasks

> 基于已批准的 spec.md + plan.md。任务有序，每步留绿编译。验证一律「先跑命令看输出，再下结论」。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `src/main/java/dev/gcode/llm/StreamEvent.java` | sealed 新增 `UsageEvent`；新增 `Usage` record |
| 修改 | `src/main/java/dev/gcode/llm/Provider.java` | `stream` 加 `String systemSuffix` 形参 |
| 修改 | `src/main/java/dev/gcode/llm/AnthropicProvider.java` | `effectiveSystem(suffix)`；流结束上抛 `UsageEvent` |
| 修改 | `src/main/java/dev/gcode/llm/OpenAIProvider.java` | `streamOptions.includeUsage(true)`；`toOpenAIMessages` 拼 `suffix`；上抛 `UsageEvent` |
| 修改 | `src/main/java/dev/gcode/tool/Tool.java` | 接口加 `boolean readOnly()` |
| 修改 | `src/main/java/dev/gcode/tool/Registry.java` | `readOnlyDefinitions`、`isReadOnly` |
| 修改 | `src/main/java/dev/gcode/tool/{ReadFileTool,WriteFileTool,EditFileTool,BashTool,GlobTool,GrepTool}.java` | 各加 `readOnly()` |
| 修改 | `src/main/java/dev/gcode/conversation/Conversation.java` | `lastRole()` |
| 修改 | `src/main/java/dev/gcode/prompt/Prompt.java` | `PLAN_MODE_REMINDER`、`EXECUTE_DIRECTIVE`；`SYSTEM_PROMPT` 增循环约定 |
| 重写 | `src/main/java/dev/gcode/agent/Agent.java` | ReAct 循环、`Mode`、`executeBatched`、`UsageReport`/`Iter`/`Notice` 事件、历史收尾 |
| 修改 | `src/main/java/dev/gcode/agent/Event.java` | sealed 新增 `UsageReport`、`Iter`、`Notice` 子类型；新增 `Usage` record |
| 新建 | `src/main/java/dev/gcode/agent/Mode.java` | `enum Mode { NORMAL, PLAN }` |
| 新建 | `src/main/java/dev/gcode/agent/CancelToken.java` | per-turn 取消句柄（volatile + 派生 timeout + 可选回调） |
| 重写 | `src/test/java/dev/gcode/agent/AgentTest.java` | 多轮 fake provider、并发分批、停止条件、Plan 工具集 |
| 修改 | `src/test/java/dev/gcode/conversation/ConversationTest.java` | `lastRole` 断言 |
| 修改 | `src/main/java/dev/gcode/tui/{TuiApp,StreamPump,View}.java` | `mode`、per-turn cancel、Esc/Ctrl+C、`/plan /do`、`UsageReport`/`Iter`/`Notice`/多工具、状态栏、动态区 |
| 修改 | `src/test/java/dev/gcode/smoke/SmokeMain.java` | `Agent.run` 调用处补 `Mode` 与 `CancelToken` 实参（`Mode.NORMAL`） |

## T1: llm 新增 Usage record + UsageEvent（纯增量）**文件：** `src/main/java/dev/gcode/llm/StreamEvent.java`、`src/main/java/dev/gcode/llm/Usage.java`
**依赖：** 无
**步骤：**
1. 新建 `Usage.java`：`public record Usage(long inputTokens, long outputTokens) {}`（带中文 Javadoc：本轮输入/输出 token 数）。
2. `StreamEvent.java`：sealed 接口 `permits` 列表增 `UsageEvent`；新增嵌套 `record UsageEvent(Usage usage) implements StreamEvent {}`，并补 Javadoc「`UsageEvent` 在 `Done` 之前一次性发出」。

**验证：** `mvn -q -DskipTests compile` 通过（纯增子类型 + record，向后兼容现有 `switch` 表达式时会触发完备性告警——T5 / T6 落地后会消失）。

## T2: tool 只读分类**文件：** `src/main/java/dev/gcode/tool/Tool.java`、`src/main/java/dev/gcode/tool/Registry.java`、`src/main/java/dev/gcode/tool/{ReadFileTool,WriteFileTool,EditFileTool,BashTool,GlobTool,GrepTool}.java`
**依赖：** 无
**步骤：**
1. `Tool.java`：接口加 `boolean readOnly();`（Javadoc：true=只读，可并发执行 & Plan Mode 放行）。
2. 6 个工具各加一行实现：`ReadFileTool`/`GlobTool`/`GrepTool` → `@Override public boolean readOnly() { return true; }`；`WriteFileTool`/`EditFileTool`/`BashTool` → `return false;`。
3. `Registry.java`：
   - `public List<ToolDefinition> readOnlyDefinitions()`：仿 `definitions()` 按注册顺序遍历，仅收 `tools.get(name).readOnly()==true` 的项。
   - `public boolean isReadOnly(String name)`：`Optional<Tool> t = get(name); return t.isPresent() && t.get().readOnly();`。

**验证：** `mvn -q compile`；`mvn -q test -Dtest='dev.gcode.tool.*'` 不回归（接口加方法后 6 工具均实现，编译即证明完整）。

## T3: Conversation.lastRole**文件：** `src/main/java/dev/gcode/conversation/Conversation.java`、`src/test/java/dev/gcode/conversation/ConversationTest.java`
**依赖：** 无
**步骤：**
1. `Conversation.java`：新增 `public Optional<Role> lastRole()`——空历史返回 `Optional.empty()`，否则返回 `Optional.of(messages.get(messages.size()-1).role())`。
2. `ConversationTest.java`：补一条 `@Test`——空会话 `lastRole().isEmpty()`；`addUser` 后 `lastRole().get() == Role.USER`；`addToolResults` 后 `== Role.TOOL`；`addAssistant` 后 `== Role.ASSISTANT`。

**验证：** `mvn -q test -Dtest=ConversationTest` 通过。

## T4: prompt 计划态提示与循环约定**文件：** `src/main/java/dev/gcode/prompt/Prompt.java`
**依赖：** 无
**步骤：**
1. `SYSTEM_PROMPT` 增补一句 Agent 循环约定：持续调用工具推进任务，直到任务完成后再给出最终简洁答复（不要每步都停下来等用户）。
2. 新增 `public static final String PLAN_MODE_REMINDER = "..."`：计划模式系统后缀——当前为计划模式，只能用只读工具（读文件 / 按模式找文件 / 搜内容）调研并产出一份分步执行计划；不得写文件、改文件或执行命令；计划写完即停，等用户用 `/do` 批准后再执行。
3. 新增 `public static final String EXECUTE_DIRECTIVE = "请按上面的计划开始执行。"`。
4. （可选）启动 banner 的就绪提示增提 `/plan`、`/do`。

**验证：** `mvn -q compile`；`mvn -q test` 不回归。

## T5: llm stream 加 systemSuffix + 用量上抛**文件：** `src/main/java/dev/gcode/llm/Provider.java`、`src/main/java/dev/gcode/llm/AnthropicProvider.java`、`src/main/java/dev/gcode/llm/OpenAIProvider.java`、`src/main/java/dev/gcode/agent/Agent.java`（临时补参）
**依赖：** T1
**步骤：**
1. `Provider.java`：接口签名改为 `Flow.Publisher<StreamEvent> stream(List<Message> messages, List<ToolDefinition> tools, String systemSuffix);`，更新 Javadoc 说明 `systemSuffix` 语义（非空时拼到内置 `SYSTEM_PROMPT` 之后）。
2. `AnthropicProvider.java`：
   - `stream` 加 `systemSuffix` 形参；`MessageCreateParams.system(...)` 改为 `effectiveSystem(systemSuffix)`——`suffix==null||suffix.isEmpty()` 单块 `Prompt.SYSTEM_PROMPT`；非空时单块 `Prompt.SYSTEM_PROMPT + "\n\n" + suffix`。
   - SDK 异步流式订阅的 `onCompleteFuture`/`get()` 完成（无异常）后、上抛 `ToolCalls` 与 `pub.close()` 前：从 `MessageAccumulator` 取 `var u = accumulator.message().usage();`，`pub.submit(new StreamEvent.UsageEvent(new Usage(u.inputTokens(), u.outputTokens())))`。
3. `OpenAIProvider.java`：
   - `stream` 加 `systemSuffix`；构造请求时 `params.streamOptions(ChatCompletionStreamOptions.builder().includeUsage(true).build())`。
   - `toOpenAIMessages(messages, systemSuffix)`：首条 system 消息文本 `Prompt.SYSTEM_PROMPT`，`suffix` 非空时 `+"\n\n"+suffix`（其调用处同步加实参）。
   - 流结束后：从累加器取 `CompletionUsage u`，`pub.submit(new StreamEvent.UsageEvent(new Usage(u.promptTokens(), u.completionTokens())))`。
4. `Agent.java`：把现有 `streamOnce` 里唯一的 `provider.stream(conv.messages(), defs)` 调用补成 `provider.stream(conv.messages(), defs, "")` 以匹配新签名——本步即让**非测试构建**保持绿（T6 会整体重写 `Agent.java`）。

> 说明：`SmokeMain` 走 `Agent.run`、不直接调 `stream`，本步不动它（其 `run` 调用在 T7 随 `mode` / `cancel` 形参一并更新）。`AgentTest.FakeProvider#stream` 也实现该接口，本步之后它会编译失败——这是预期的，T6 重写 `AgentTest` 时一并补 `systemSuffix` 形参；因此本步**不要**跑 `mvn -q test -Dtest=AgentTest`。

**验证：** `mvn -q -DskipTests compile` 通过（主源码绿）；`mvn -q test -Dtest='dev.gcode.llm.*'` 不回归；用 `mvn exec:java -Dexec.mainClass=dev.gcode.Main` 发一条纯文本回复正常（用量已随流上抛，旧 agent 暂未消费）。

## T6: agent ReAct 循环重写**文件：** `src/main/java/dev/gcode/agent/Agent.java`、`src/main/java/dev/gcode/agent/Event.java`、`src/main/java/dev/gcode/agent/Mode.java`、`src/main/java/dev/gcode/agent/CancelToken.java`、`src/test/java/dev/gcode/agent/AgentTest.java`
**依赖：** T1, T2, T3, T4, T5
**步骤：**
1. `Mode.java`（新增）：`public enum Mode { NORMAL, PLAN }`。
2. `CancelToken.java`（新增）：`volatile boolean cancelled` + `cancel()` 方法 + `isCancelled()` + 可选 `Runnable onCancel` 列表 + `withTimeout(Duration)` 派生（用 `ScheduledExecutorService` 定时触发 `cancel()`，可被父 token 提前触发）。
3. `Event.java`：sealed `permits` 列表新增 `UsageReport`、`Iter`、`Notice` 子类型；新增 `Usage(long input, long output)` record（注意与 `llm.Usage` 同义但解耦在 agent 包内）。
4. `Agent.java`：
   - 类 Javadoc 改为「ReAct 循环编排」。
   - 类型：保留 `Phase`/`ToolEvent`/构造函数；新增 `Usage` record（或复用 `agent.Usage`）、`Mode` enum；`Event` sealed 增 `UsageReport`/`Iter`/`Notice` 子类型。
   - 常量：按 plan「迭代、停止常量与提示文案」原样落 `MAX_ITERATIONS` / `MAX_UNKNOWN_RUN` 与 `NOTICE_MAX_ITER` / `NOTICE_UNKNOWN_TOOLS` / `NOTICE_STREAM_ERR` / `NOTICE_CANCELLED`（文案以 plan 为准，T8 端到端按这些文案核对）。
   - `run(conv, mode, cancel) → Flow.Publisher<Event>`：按 plan「`run` 算法」实现 `for iter` 循环——按 `mode` 取 `defs`（`definitions` / `readOnlyDefinitions`）与 `suffix`（`""` / `Prompt.PLAN_MODE_REMINDER`）；emit Iter → `streamOnce` → emit `UsageReport` → 无工具自然完成 / 有工具 `addAssistantWithToolCalls` → 统计 `unknownRun` → `executeBatched` → `addToolResults`（无条件）→ **取消（`!batch.completed()`）最高优先级收尾** → 未知工具上限收尾 → 循环走完触达迭代上限收尾。内部用 `SubmissionPublisher<Event> bus`，整个循环跑在 `Thread.ofVirtual().start(...)` 内，`try (bus)` 关闭。
   - `streamOnce(conv, defs, suffix, cancel, bus) → StreamOutcome`：`suffix` 为 ch04 新增形参，透传给 `provider.stream`；订阅 `Flow.Publisher<llm.StreamEvent>` 同步消费——`switch` pattern match 处理 `TextDelta` / `ToolCalls` / `UsageEvent` / `Done` / `Failed`；记录 `usage`、收集 `calls`、转发 Text，`Failed` 即发 `Event.Failed` 返回 `failed=true`。
   - `executeBatched(calls, cancel, bus) → BatchOutcome`：保序分批——从 `i=0` 扫描，`registry.isReadOnly(calls.get(i).name())` 为真则吃最长连续只读区间 `[i, j)` 用 `CountDownLatch(j-i)` + `Thread.ofVirtual().start(...)` **并发**（每虚拟线程内 `var sub = cancel.withTimeout(Tool.DEFAULT_TIMEOUT)` 后 `registry.execute(sub, ...)`，只写自己下标 `results[k]`），否则**串行**单个；每段执行前判 `cancel.isCancelled()` 取消则填 `NOTICE_CANCELLED` 结果返 `completed=false`；事件「Start 按序、End 按序」（见 plan）。
   - 辅助：`allUnknown(calls)`（每个 call 用 `registry.get` 判，全未注册才 true）、`ensureFinal`（沿用 ch03）、`ensureAssistantTail(conv, fallback)`、`finishCancelled(conv)`、`emit` / `argsPreview`（沿用 ch03）。
5. `AgentTest.java`（**替换** ch03 的 `testSingleRoundReadAndAnswer` / `testSingleRoundLimit`——后者断言单轮已与 ch04 多轮矛盾）。`FakeProvider#stream` 签名补 `String systemSuffix`（并在某用例里记录收到的 `tools` / `suffix` 供断言）；多轮靠 `List<List<StreamEvent>> scripts` 逐次返回：
   - 场景 A（多轮链路 AC1）：脚本①返回 1 个 read_file 工具调用、脚本②返回纯文本 → 断言事件序列含 `Iter(1)`、`Tool(Start/End)`、`Iter(2)`、最终 `TextDelta`、`Done`；`conv` 末尾为 assistant 文本，中间含 tool_use 回合 + `Role.TOOL` 回合。
   - 场景 B（迭代上限 AC3）：用「每次 stream 都返回一个工具调用」的 fake（忽略脚本耗尽，恒返工具）→ 断言恰好 `MAX_ITERATIONS` 次请求后停（`fake.calls == MAX_ITERATIONS`）、收到 `Notice(NOTICE_MAX_ITER)`、`conv.lastRole().get() == Role.ASSISTANT`。
   - 场景 C（连续未知工具 AC4）：脚本连续返回未注册工具名 → 断言 `MAX_UNKNOWN_RUN` 轮后停并 `Notice(NOTICE_UNKNOWN_TOOLS)`；另一用例在其间混入一个 read_file，断言计数重置、不提前停。
   - 场景 D（保序分批 AC8）：构造**自定义 `Registry`** 注册两个插桩工具——一个只读工具（`readOnly()==true`，`execute` 内 `AtomicInteger` 记录「同时在跑的并发数」峰值、并 `Thread.sleep` 制造重叠）与一个有副作用工具（`readOnly()==false`，记录开始时刻）。脚本一轮返回 `[ro, ro, rw]` → 断言：两只读的并发峰值 ≥2（确实并发）、rw 的开始时刻晚于两只读完成、`addToolResults` 写入历史的结果顺序与调用序一致（按结果内容 / id 比对，不依赖具体方法名）。
   - 场景 E（取消历史一致 AC9）：插桩工具在 `execute` 中阻塞，测试侧在执行期间调 `cancel.cancel()` per-turn token → 断言 `conv` 末尾配对合法（含 tool_results、最后是 assistant 文本 `NOTICE_CANCELLED`），无悬空 tool_use；随后再追加一轮纯文本脚本能正常跑（角色交替未坏）。
   - 场景 F（Plan 工具集 AC13）：`agent.run(conv, Mode.PLAN, new CancelToken())` → 断言 fake 收到的 `tools` 仅含只读工具定义、`suffix == Prompt.PLAN_MODE_REMINDER`。

**验证：** `mvn -q test -Dtest=AgentTest` 全通过；用 `-DargLine="-Xss2m"` 或 `mvn -q -Dtest=AgentTest test` 加压跑多遍（覆盖并发分批，N6）；可选 `mvn -q dependency:tree | grep junit` 确认 JUnit 5 启用。

## T7: tui 接入 Agent Loop + 收尾 `run` 调用方**文件：** `src/main/java/dev/gcode/tui/TuiApp.java`、`src/main/java/dev/gcode/tui/StreamPump.java`、`src/main/java/dev/gcode/tui/View.java`、`src/test/java/dev/gcode/smoke/SmokeMain.java`
**依赖：** T4, T6
**说明：** T6 改了 `Agent.run` 签名（加 `mode` 与 `cancel`），其调用方 `tui/StreamPump`（或 `TuiApp.onSubmit`）与 `SmokeMain` 在此步同步更新——本步完成后 `mvn -q -DskipTests package` 才在**仓库级**重新转绿（T6 后只保证 agent 包及其测试绿）。
**步骤：**
1. `TuiApp.java`：
   - 新增字段：`Mode mode = Mode.NORMAL;`、`int iter;`、`long usageIn;`、`long usageOut;`、`List<ToolDisplay> curTools = new ArrayList<>();`（移除单个 `curTool`）、`CancelToken turnCancel;`。
   - Lanterna `KeyStroke` 拦截：`Ctrl+C` → `SessionState.STREAMING` 时 `turnCancel.cancel()`（不退出，等 onComplete）/ 否则 `screen.stopScreen(); System.exit(0);`；新增 `Esc` → `SessionState.STREAMING` 时 `turnCancel.cancel()`。
2. `StreamPump.java`（兼 `TuiApp.onSubmit`）：
   - `onSubmit`：识别 `/exit`（退出）、`/plan`（`mode=Mode.PLAN`、提示块、回 IDLE）、`/do`（`mode=Mode.NORMAL`、`conv.addUser(Prompt.EXECUTE_DIRECTIVE)`、走启动流程）、普通文本（`conv.addUser`）。启动处：`turnCancel = new CancelToken()`；`Flow.Publisher<Event> events = new Agent(provider, registry).run(conv, mode, turnCancel)`；`events.subscribe(this)`；`iter=0`；`state=SessionState.STREAMING`。
   - `onNext(event)`：通过 `gui.getGUIThread().invokeLater(...)` 切回 GUI 线程，按 plan 分派顺序处理（switch pattern match）`Failed` / `Tool` / `UsageReport`（累加 `usageIn`/`usageOut`）/ `Notice`（灰提示块）/ `Iter`（set `this.iter`）/ `Done` / `TextDelta`；`Tool.Phase.START` 追加 `curTools`（首个工具前先提交 preamble）、`Phase.END` 从 `curTools` 移除队首并按序 append 工具行 + 结果摘要到 scrollback。
   - `onComplete` / `onError`：兜底 `finishTurn()`。
   - `finishTurn`：清 `curReply` / `curTools.clear()` / `iter=0` / `turnCancel=null`，回 `SessionState.IDLE`（保留 `mode`、`usageIn`/`usageOut`）。
3. `View.java`：
   - `statusBar`：左侧 provider 名后在 `Mode.PLAN` 时附「PLAN」徽标；右侧 model 名旁附 `↑{in} ↓{out} tok`（紧凑数字，如 `1.2k`）。
   - 流式动态区：`curTools` 非空逐行渲染 `● name(args)` Running…；否则「Imagining… (Ns · 第 N 轮)」（`iter>0` 附轮次）。
4. `SmokeMain.java`：`new Agent(provider, registry).run(conv)` 调用补 `mode` 与 `cancel` 实参 → `agent.run(conv, Mode.NORMAL, new CancelToken())`（保持其调试用途，不需感知 plan / 取消）。

**验证：** `mvn -q -DskipTests package`（仓库级转绿）；`mvn -q test`（无新增测试，但需保证未回归）；`mvn spotless:check` 通过（如启用）。

## T8: 全量验证与端到端冒烟**文件：** 无（验证）
**依赖：** T1–T7
**步骤：**
1. `mvn spotless:check`（google-java-format 合规）；`mvn -q -DskipTests package`；`mvn -q test`；`mvn -q test -Dtest='dev.gcode.agent.*,dev.gcode.tool.*'`（再跑一次锁住 N6 关键包）。
2. 端到端（openai 兼容端点，用 `.gcode/config.yaml`）：
   - 多轮（AC1）：问「读 `docs/ch03/spec.md`，再据其内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ 观察 read_file → write_file 跨多轮自动连环、状态栏用量增长、动态区轮次递增、最终答复。
   - 取消（AC10）：发一个会跑多步的任务，中途按 Esc / Ctrl+C → 回空闲态不退出 → 再正常发一条继续对话（验证历史未坏）。
   - 流出错（AC5）：临时改坏 `base_url` 或断网发一条 → 错误提示、程序不退出、改回后继续。
   - Plan Mode（AC13）：`/plan` → 问「给登录功能加单测的方案」→ 观察只出现 read/glob/grep 类工具与计划文本、无写/执行 → `/do` → 切回全工具按计划执行。
3. （可选）若有 anthropic 配置，重复多轮场景验证跨协议一致（AC14）。

**验证：** 全部命令通过、端到端各场景符合预期；密钥不回显（通读输出，AC/N7）。

## 执行顺序

```
T1 ─┬─ T5 ─┐
T2 ─┤      │
T3 ─┼──────┼─ T6 ─┬─ T7 ─┐
T4 ─┘      │      │      │
           └──────┘      └─ T8
```
（T1–T4 互相独立可并行；T5 依赖 T1；T6 依赖 T1/T2/T3/T4/T5；T7 依赖 T4/T6；T8 收尾全部。）
````

```markdown
# Agent Loop Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为；括号内为验证方式与对应需求。

## 实现完整性
- [ ] 多轮自动连环：需要连续两步工具的任务，Agent 无需中途催促即自动多轮执行工具直到给出最终答复（验证：`mvn -q exec:java -Dexec.mainClass=dev.gcode.Main` 或 `java -jar target/gcode-*.jar` 跑「读 A 文件 → 据内容新建 B 文件」，观察 read_file 与 write_file 跨多轮依次出现、最终答复）。(AC1/F1)
- [ ] 自然完成停止：模型给出无工具调用的纯文本即停（验证：`AgentTest` 场景 A 断言收到最终 `TextDelta` + `Done`，循环不再发起请求）。(AC2/F2)
- [ ] 迭代上限兜底：模型反复调工具时达到 `MAX_ITERATIONS` 即停并提示，不无限循环（验证：`AgentTest` 场景 B 断言恰好上限轮后停 + `Notice(NOTICE_MAX_ITER)`）。(AC3/F2)
- [ ] 连续未知工具停止：连续 `MAX_UNKNOWN_RUN` 轮只产生未知工具调用即停；混入已注册工具则计数重置（验证：`AgentTest` 场景 C 两路断言）。(AC4/F2)
- [ ] 流出错恢复：provider 流出错时停止本轮、发 `Failed`、程序不退出（验证：端到端临时改坏 `base_url` 发一条，观察错误块 + 仍可继续；`AgentTest` 注入 `Failed` 脚本断言收到 `Failed` 后停）。(AC5/F2)
- [ ] 事件流完备：Agent 对外事件含 `TextDelta` / 工具 Start / 工具 End / `UsageReport` / `Iter` / `Notice` / `Done` / `Failed`（验证：`AgentTest` 断言一次多轮运行收集到的事件子类型集合覆盖上述各类；端到端跑多轮任务，界面实时显示文本增量、工具进度、轮次、用量、最终答复，证明界面所需信息均来自事件流）。(AC6/F3)
- [ ] 流式收集双路：文本实时显示的同时，完整工具调用（拼齐 JSON 参数）被收集用于下一轮（验证：`AgentTest` 断言 `ToolCall.input` 完整可解析；端到端工具行参数与请求一致）。(AC7/F4)
- [ ] 保序分批并发：一次回复含多个工具时，连续只读并发执行、有副作用串行，结果按原序回灌（验证：`AgentTest` 场景 D 用插桩工具断言两只读的执行时间窗重叠（并发峰值≥2）、有副作用工具在其后开始、最终写入历史的工具结果顺序与模型调用序一致——按结果内容 / id 比对，与函数名无关）。(AC8/F5/N6)
- [ ] 取消历史一致：执行中取消后历史配对合法（有 tool_results、末尾 assistant 文本、无悬空 tool_use）（验证：`AgentTest` 场景 E 断言 `conv` 序列；端到端取消后再发一条不报 400）。(AC9/F6)
- [ ] 用户取消：流式态 Esc 或 Ctrl+C 中断本轮回空闲态、不退出；空闲态 Ctrl+C 退出（验证：端到端各按一次观察行为）。(AC10/F7)
- [ ] 用量展示：状态栏显示会话累计 token（输入/输出），随轮次增长更新（验证：端到端跑多轮观察状态栏数值递增）。(AC11/F8)
- [ ] 进度展示：流式态动态区显示当前迭代轮次（验证：端到端跑多轮任务观察「第 N 轮」递增）。(AC12/F9)
- [ ] Plan Mode：`/plan` 后只出现只读工具与计划文本、无写/执行；`/do` 切回全工具并立即按计划执行（验证：端到端 Plan Mode 场景；`AgentTest` 场景 F 断言 `Mode.PLAN` 下 fake 收到的 tools 仅只读）。(AC13/F10)

## 集成
- [ ] 跨协议一致：anthropic 与 openai（含兼容 `base_url`）跑同一多轮任务，触发/执行/回灌/用量/取消行为一致（验证：两种配置各跑多轮场景）。(AC14/F11/N3)
- [ ] 多轮历史正确携带：每轮 assistant(tool_use) 回合 + tool_result 回合按序入历史并被下一轮请求携带（验证：`AgentTest` 断言 `conv` 末尾序列；或抓请求体见历史增长）。(F6)
- [ ] 界面不阻塞：多轮循环与工具执行（含并发批）期间 spinner / 轮次 / 计时持续刷新（验证：跑含稍慢 bash 的任务，观察界面不冻结；virtual thread 跑工具与 SDK 流，UI 线程通过 `invokeLater` 更新）。(N2)
- [ ] scrollback 顺序正确：跨多轮 preamble → 工具行 → 结果摘要 → 最终答复按序出现不交错，并发批的工具行按模型调用序排列（验证：跑一个含并发只读批 + 后续写的多轮任务，回滚 scrollback 肉眼核对各块严格按发生顺序连续、无交错、并发工具行顺序==调用序）。(N3)
- [ ] 结果体量受控：大文件 / 长输出 / 海量命中被工具级上限截断标注 `[truncated]`，多轮累积不撑爆（验证：多轮中读大文件 / 跑长输出命令观察截断）。(N4)
- [ ] 取消无泄漏：取消后无挂起 virtual thread / 无未关闭 `SubmissionPublisher`（验证：`mvn -q test -Dtest=AgentTest` 含取消用例（场景 E）通过；端到端反复触发取消后继续对话多次，进程内存 / 句柄稳定不增长，可用 `jcmd <pid> Thread.print | grep "Virtual"` 抽查）。(N5/N6)
- [ ] 系统提示体现 Agent 循环：问「你能做什么」答复体现可多步使用工具完成任务（验证：发一条询问观察答复）。(F3)

## 编译与测试
- [ ] `mvn -q -DskipTests package` 无错误（fat jar 可启动）。
- [ ] `mvn -q test` 通过（`ConfigLoaderTest`、`ConversationTest`、`AgentTest`、`tool` 相关用例）。
- [ ] `mvn -q test -Dtest='dev.gcode.agent.*,dev.gcode.tool.*'` 无失败（覆盖 N6 关键包，含并发场景 D / 取消场景 E）。
- [ ] `mvn spotless:check` 通过（google-java-format 合规）。(N8)
- [ ] 密钥不回显：对话区与任何输出均不出现 `api_key`（验证：通读运行输出、检索无明文 key）。(N7)

## 端到端场景
- [ ] 场景 1（多轮连环）：openai 兼容端点 → 「读 `docs/ch03/spec.md`，再据内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ read_file → write_file 跨多轮自动出现 → 状态栏用量增长、动态区轮次递增 → 最终答复 → `/exit` 无残留。
- [ ] 场景 2（用户取消）：发一个多步任务，中途按 Esc（再试 Ctrl+C）→ 回空闲态不退出 → 再正常发一条继续对话（历史未坏，无 400）。
- [ ] 场景 3（流出错恢复）：临时改坏 `base_url` 发一条 → 错误块 + 程序不退出 → 改回后继续正常对话。
- [ ] 场景 4（Plan Mode）：`/plan` → 问一个改动类需求 → 只出现 read/glob/grep + 计划文本、无写/执行 → `/do` → 切回全工具并按计划执行（出现 write/edit/bash）。
- [ ] 场景 5（跨协议，若有 anthropic 配置）：切到 anthropic 配置重跑场景 1 → 多轮行为与 openai 一致。
- [ ] 场景 6（迭代上限）：主要由 `AgentTest` 场景 B 确定性验证；可选手动复现——临时把 `MAX_ITERATIONS` 改小（如 3）跑一个会多步调工具的任务，观察第 3 轮后停并显示 `NOTICE_MAX_ITER`、之后仍可继续对话。
- [ ] 场景 7（连续未知工具）：主要由 `AgentTest` 场景 C 确定性验证；可选手动复现——在 system prompt 临时引导模型调用一个不存在的工具名，观察连续 `MAX_UNKNOWN_RUN` 轮后停并显示 `NOTICE_UNKNOWN_TOOLS`、之后仍可继续对话。
```

### TypeScript

```markdown
# Agent Loop Spec## 背景ch03 给 GCode 装上了工具系统：模型能读写改文件、执行命令、按模式找文件、搜代码内容。但编排是**单轮闭环**——请求#1 拿到一批工具调用 → 执行 → 结果回灌 → 请求#2 出最终答复就停，且续答里模型再次请求的工具被**直接丢弃**。模型只能「一步一停」，复杂任务（读完 A 才知道要改 B）得用户反复催。

ch04 给 GCode 装上 **Agent Loop**：模型自主循环——想 → 调工具 → 看结果 → 边做边调整，直到任务完成。从被动应答变成能自主干活的 Agent。这是从「能用工具」到「会自己干」的关键一跃。

## 目标- **ReAct 循环**：一轮轮调模型、执行工具、结果回血，直到模型不再请求工具。
- **多种停止条件**：自然完成、迭代上限（兜底安全网）、用户取消、连续请求未知工具、流出错。
- **异步事件流**：Agent 吐出文本 / 工具调用 / 工具结果 / Token 用量 / 迭代进度等事件，让 Agent 与界面彻底解耦。
- **流式收集双路**：一边实时把文本增量推给界面，一边攒出完整响应（含工具调用）供循环判断。
- **保序分批并发**：一次回复的多个工具调用按安全性分批——连续只读并发执行，有副作用串行执行，保持模型给出的相对顺序。
- **Plan Mode 两段式**：进入计划模式时仅放开只读工具并注入计划态系统提醒，让模型先出计划；模型主动声明计划完成后切回全工具模式并按计划执行。

## 功能需求

- F1: ReAct 主循环编排
  替换 ch03 的单轮闭环。每一轮：带工具定义发起请求 → 流式收集本轮响应 → 若模型请求了工具则执行并把结果回灌进历史，进入下一轮；若模型给出无工具调用的纯文本，则该文本即最终答复，循环结束。不再丢弃续答里的工具调用。

- F2: 多种停止条件
  循环在以下任一条件下停止，每种都干净收尾（对话历史保持合法 + 给界面明确信号）：
  1. 自然完成——模型回复不含工具调用，纯文本即最终答复。
  2. 迭代上限——达到内置上限兜底，避免失控；触顶时给出提示并停。
  3. 用户取消——见 F7。
  4. 连续未知工具——模型连续多轮只请求注册中心不存在的工具达阈值即停，避免对幻觉工具空转。
  5. 流出错——模型流返回错误时停止本轮并提示，不崩溃、不中断会话。

- F3: 异步事件流（Agent ↔ 界面解耦）
  Agent 对外只吐事件，界面只消费事件、不感知循环内部细节。事件涵盖：文本增量、思考增量、工具调用开始、工具调用结束（结果摘要 + 是否错误）、Token 用量、迭代进度、本轮结束、错误、权限请求。

- F4: 流式收集双路
  每轮请求的流式响应走双路：一路把文本增量实时推给事件流（界面即时显示），一路累积完整文本并拼接出完整工具调用（含分片到达的参数 JSON），供循环判断下一步。

- F5: 保序分批并发执行
  工具按安全性区分为「只读 / 写入 / 命令」三类。一次回复的多个工具调用按模型给出的顺序扫描：连续的只读调用合并为一个并发批并行执行，遇到写入或命令调用则单独串行执行，保持整体相对顺序。批内并发完成后，结果按原始调用顺序回灌。每个工具仍受自身实现的超时/取消约束（沿用 ch03）。

- F6: 结果回灌与历史一致
  每轮的 assistant 回合（含工具调用）与工具结果回合按序写入对话历史，下一轮请求携带完整历史。任何提前终止（取消 / 上限 / 未知工具 / 出错）后，对话历史都保持合法——工具调用与结果配对、角色交替不被破坏，会话可继续。被取消时仍把已收集的文本写入历史，避免悬空的工具调用。

- F7: 用户取消本轮
  流式态下 Esc 或 Ctrl+C 中断当前 Loop：停止后续迭代、回到空闲态、不退出程序；空闲态 Ctrl+C 退出程序。中断后历史保持合法（见 F6），可继续对话。

- F8: Token 用量统计
  从模型的流式响应中提取每轮的 token 用量（输入 / 输出，含缓存读 / 缓存写），跨轮累加为会话累计量，在状态栏展示。

- F9: 迭代进度展示
  流式态动态区展示当前迭代轮次，让用户感知 Agent 正在多轮推进。

- F10: Plan Mode 两段式
  进入计划模式：仅注入只读工具定义 + 计划态系统提醒（让模型先产出计划、不动手改动），同时通过权限检查物理拦截写入与命令类工具；模型显式声明「计划完成」时，循环停止并把计划交回界面，由界面切回全工具模式并立即按计划执行。模式跨轮保持，直到再次切换。

- F11: 跨协议一致
  系统抽象出统一的模型客户端接口，按配置选择对应协议适配器；Anthropic 协议、OpenAI 协议、以及 OpenAI 兼容端点都跑通完整 Loop——多轮工具调用、用量提取、取消行为一致。

## 非功能需求

- N1: 工具执行超时——每个工具实现自行控制 I/O 超时（沿用 ch03），循环层不再兜底；超时以结构化错误结果回灌，不中断循环。
- N2: 界面不阻塞——多轮循环、工具执行（含并发批）期间界面持续响应，spinner、迭代进度、计时正常刷新，不冻结。
- N3: scrollback 顺序正确——跨多轮的文本增量、工具行、结果摘要、最终答复按真实发生顺序提交到 scrollback；并发批的工具行按模型给出的调用顺序排列，整体不交错。
- N4: 结果体量受控——写入历史前对单条工具输出做字符上限截断（超出加截断提示）；多轮累积下上下文与界面均不被撑爆。
- N5: 取消及时、无泄漏——取消信号被模型流、工具执行器、可中断等待共同观察；循环退出后不残留挂起的异步任务或未关闭的事件流。
- N6: 事件类型安全——事件流是受判别字段约束的联合类型，所有事件消费方都按事件类型分派，编译期保证每条分支字段访问合法。
- N7: 密钥不回显——沿用 ch03，对话区与任何输出均不出现 api_key。
- N8: 代码规范——遵循项目既定的格式化、类型检查与测试规范，无错误、无告警。

## 不做的事

- 上下文压缩 / 历史裁剪——多轮累积的历史不压缩、不裁剪，超长会话可能触及上下文上限（留待后续章节）。
- 权限系统 / 交互式确认——本章保留权限检查的占位接口，默认全部放行；真正的 ask/deny 交互对话留待专门章节。
- 工具执行沙箱 / 路径白名单——沿用 ch03，不限制工具只能在工作目录内操作。
- 工具调用与结果持久化——沿用 ch02/ch03，退出即丢。
- 迭代上限 / 取消阈值配置化——迭代上限通过 Agent 配置传入但默认不限制；「连续未知工具」阈值为内置常量。
- 跨批重排并发——只在「连续只读」批内并发；不把读写调用重排以追求最大并行度。
- 子 Agent / 任务分解工具——不做。
- Plan Mode 的计划文件完整工作流——本章接通计划态系统提醒与「计划完成」声明，但计划文件的多阶段流转留待后续章节细化。
- Token 预算限制 / 按用量自动停止——只统计与展示用量，不按预算自动截断。
- 多模态——工具结果与对话均为文本。
- 流式工具结果——工具结果一次性回灌，不做流式产出。

## 验收标准

- AC1: 多轮自动连环——给需要连续两步工具的任务（如「读 `docs/ch03/spec.md`，再据其内容新建一个摘要文件」），Agent 自动多轮执行工具调用并回灌结果；当某轮模型不再请求工具、只输出纯文本时循环停止、该文本即最终答复，全程无需用户中途催。(F1)
- AC2: 自然完成——模型给出无工具调用的纯文本时循环立即停止，该文本即最终答复。(F2)
- AC3: 迭代上限兜底——把上限调低构造模型反复调工具不收手的情形，达到上限即停并提示，不无限循环。(F2)
- AC4: 连续未知工具停止——模型连续请求注册中心不存在的工具达阈值时，循环停止并提示。(F2)
- AC5: 流出错恢复——模型流出错时停止本轮、给出错误提示、程序不退出，之后可继续正常对话。(F2)
- AC6: 事件流完备——Agent 对外事件涵盖文本、工具调用开始/结束、Token 用量、迭代进度、结束、错误；界面仅靠这些事件渲染。(F3)
- AC7: 流式收集双路——文本实时显示的同时，模型一次回复中完整的工具调用（含拼齐的参数 JSON）被正确收集用于下一轮。(F4)
- AC8: 保序分批并发——一次回复含多个工具调用时，连续只读并发执行、写入/命令串行执行，保持相对顺序；结果按原始顺序回灌。(F5)
- AC9: 历史一致——多轮的 assistant 与工具结果回合按序入历史；取消 / 上限 / 出错终止后历史仍配对合法，可继续对话（不出现连续同角色或悬空工具调用导致下一轮请求被服务端拒绝）。(F6)
- AC10: 用户取消——流式态 Esc 或 Ctrl+C 中断本轮、回空闲态、不退出；空闲态 Ctrl+C 退出程序。(F7)
- AC11: 用量展示——状态栏显示会话累计 token 用量（输入 / 输出），随轮次增长更新。(F8)
- AC12: 进度展示——流式态动态区显示当前迭代轮次。(F9)
- AC13: Plan Mode——进入计划模式后模型仅用只读工具产出计划、不产生写/执行类调用；模型显式声明计划完成后切回全工具模式并立即按上文计划执行（产生写/执行类工具调用）。(F10)
- AC14: 跨协议一致——Anthropic 与 OpenAI（含兼容端点）配置都跑通完整多轮 Loop，触发 / 执行 / 回灌 / 用量 / 取消行为一致。(F11)
```

````markdown
# Agent Loop Plan

> 基于已批准的 spec.md。本文档与语言相关（TypeScript 5.x，运行时 bun）。SDK 类型已对 `@anthropic-ai/sdk` ^0.99.0、`openai` ^6.39.0、`ink` ^5.2.0 核对。

## 技术栈- **运行时**：bun
- **语言**：TypeScript 5.x，ES module（`"type": "module"`），编译用 `tsc --noEmit`
- **TUI**：Ink ^5.2.0（React 18 渲染到终端）、ink-spinner、ink-text-input
- **LLM SDK**：`@anthropic-ai/sdk` ^0.99.0、`openai` ^6.39.0
- **MCP**：`@modelcontextprotocol/sdk`（占位，本章 Agent 不直接依赖）
- **markdown 渲染**：marked + marked-terminal
- **配置**：js-yaml（读 `.gcode/config.yaml`）
- **终端样式**：chalk
- **测试**：`bun test`

## 架构概览ch04 不新增包，在 ch03「tools / llm / conversation / prompt / tui」之上**扩展**：

- **src/agent/**（新增）：`Agent` 类承载 ReAct 循环；`AgentEvent` discriminated union 定义对外事件；`StreamingExecutor` 跑工具批。
- **src/llm/**（扩展）：`StreamEvent` 增 `stream_end` 携带 `UsageInfo`；`LLMClient.stream()` 接受 `AbortSignal` 形参。
- **src/tools/**（扩展）：`Tool` 接口增 `category: "read" | "write" | "command"` 字段；`ToolRegistry` 仅暴露 `get()` / `getAllSchemas(protocol)` / `listTools()`。
- **src/conversation/**（扩展）：`ConversationManager.addAssistantFull()` 支持携带 `thinkingBlocks` 与 `toolUses`；`addToolResultsMessage()` 一次性写一组 `ToolResultBlock`；`addSystemReminder()` 写 `<system-reminder>` 包裹的 user 消息。
- **src/prompt/**（扩展）：`buildPlanModeReminder()` 按 iteration 切换完整/精简提示；常量 `planModeFullReminder` / `planModeSparseReminder` 定义在 `src/prompt/plan-mode.ts`。
- **src/permissions/**（占位）：`PermissionChecker.check()` 接口本章默认放行所有调用，仅 `mode` 字段被 `Agent.run()` 读取来决定是否注入 plan 提醒。
- **src/tui/**（扩展）：`<App>` 组件 `useEffect` 启动 `agent.run()`、`useInput` 捕获 Esc / Ctrl+C、`useState` 维护事件累积；`<Static>` 渲染历史消息、动态 `<Box>` 渲染当前流。

依赖方向：`tools → llm`（共享类型）、`agent → { llm, tools, conversation, permissions, prompt }`、`tui → { agent, tools, conversation, llm, prompt, permissions }`、`llm → { config, conversation }`。

## 数据流

```
用户输入 (Ink <TextInput>)
  └─ conversation.addUserMessage(text)
  └─ const agent = new Agent({ client, registry, ... })
  └─ for await (const ev of agent.run()):       # AsyncGenerator
       ├─ stream_text  → setCurrentReply()       # 累积界面文本
       ├─ tool_use     → 追加进行中工具到状态
       ├─ tool_result  → 把工具行 + 摘要提交 <Static>
       ├─ usage        → 状态栏累加
       ├─ turn_complete→ iteration++
       ├─ loop_complete→ 把最终答复提交 <Static>，停泵
       └─ error        → 灰色错误块，停泵

# 被 Esc / Ctrl+C 时
abortController.abort() → abortSignal.aborted 为真
  → client.stream() 内 SDK fetch 抛 AbortError
  → Agent 捕获 → yield { type: "loop_complete", stopReason: "interrupted" } → return
```

## 核心数据结构与接口### `src/agent/events.ts`

```ts
// AgentEvent 是 Agent.run() AsyncGenerator 唯一的对外事件类型。
// 所有消费方都得 switch (event.type) 分派；新增事件类型时编译期会提示遗漏。
export type AgentEvent =
  | { type: "stream_text"; text: string }
  | { type: "thinking_text"; text: string }
  | { type: "thinking_complete"; thinking: string; signature: string }
  | { type: "tool_use"; toolName: string; toolId: string; args: Record<string, unknown> }
  | { type: "tool_result"; toolName: string; toolId: string; output: string; isError: boolean; elapsed: number }
  | { type: "turn_complete" }
  | { type: "loop_complete"; stopReason: string }
  | { type: "usage"; usage: UsageInfo }
  | { type: "error"; error: Error }
  | { type: "retry"; reason: string; delay: number }
  | { type: "permission_request"; toolName: string; args: Record<string, unknown> };
```

### `src/agent/agent.ts`

```ts
export interface AgentConfig {
  client: LLMClient;
  registry: ToolRegistry;
  checker: PermissionChecker;
  conversation: ConversationManager;
  workDir: string;
  abortSignal?: AbortSignal;
  maxIterations?: number;       // 0 表示不限
  onPermissionRequest?: (
    toolName: string,
    args: Record<string, unknown>,
    decision: Decision
  ) => Promise<"allow" | "deny" | "allowAlways">;
}

export class Agent {
  constructor(config: AgentConfig);
  async *run(): AsyncGenerator<AgentEvent>;
}
```

### `src/agent/streaming-executor.ts`

```ts
interface PendingCall {
  toolId: string;
  toolName: string;
  arguments: Record<string, unknown>;
}

interface ExecutionResult {
  toolId: string;
  toolName: string;
  result: ToolResult;
  elapsed: number;
}

export class StreamingExecutor {
  constructor(registry: ToolRegistry, ctx: ToolContext);
  submit(toolId: string, toolName: string, args: Record<string, unknown>): void;
  async collectResults(): Promise<ExecutionResult[]>;   // Promise.all 一次性收
  hasPending(): boolean;
}
```

### `src/llm/events.ts` 与 `src/llm/client.ts`

```ts
export interface UsageInfo {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
}

export type StreamEvent =
  | { type: "text_delta"; text: string }
  | { type: "thinking_delta"; text: string }
  | { type: "thinking_complete"; thinking: string; signature: string }
  | { type: "tool_call_start"; toolName: string; toolId: string }
  | { type: "tool_call_delta"; text: string }
  | {
      type: "tool_call_complete";
      toolId: string;
      toolName: string;
      arguments: Record<string, unknown>;
    }
  | { type: "stream_end"; stopReason: string; usage: UsageInfo };

export interface LLMClient {
  stream(
    conv: ConversationManager,
    tools: Record<string, unknown>[],
    abortSignal?: AbortSignal
  ): AsyncGenerator<StreamEvent>;
}
```

### `src/tools/types.ts`

```ts
export type ToolCategory = "read" | "write" | "command";

export interface ToolResult {
  output: string;
  isError: boolean;
}

export interface Tool {
  name: string;
  description: string;
  category: ToolCategory;       // ch04 新增：分批依据
  deferred?: boolean;
  system?: boolean;
  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}
```

### `src/conversation/conversation.ts`

```ts
export class ConversationManager {
  addUserMessage(content: string): void;
  addAssistantFull(
    text: string,
    thinking: ThinkingBlock[],
    toolUses: ToolUseBlock[]
  ): void;
  addToolResultsMessage(results: ToolResultBlock[]): void;
  addSystemReminder(content: string): void;     // ch04 新增：plan 提醒
  getMessages(): Message[];
  len(): number;
}
```

## 模块设计### src/agent/agent.ts（核心：`Agent.run()` ReAct 循环）**职责：** ReAct 循环编排（F1/F2）、保序分批并发执行（F5）、事件流（F3/F8/F9）、终止历史一致性（F6）、Plan Mode 提醒注入（F10）。

**对外接口：** `Agent`、`AgentConfig`。

**依赖：** `LLMClient`、`ToolRegistry`、`ConversationManager`、`PermissionChecker`、`buildPlanModeReminder`、`StreamingExecutor`。

**`run()` 算法（AsyncGenerator，`finally` 块兜底 lifecycle hook）：**

1. 取工具 schema：`toolSchemas = this.registry.getAllSchemas()`。
2. `let iteration = 0`, `let consecutiveUnknown = 0`, `let looping = true`。
3. `while (looping)`：
   1. `iteration++`；若 `maxIterations > 0 && iteration > maxIterations` → `yield { type: "error" }`、`return`。
   2. 若 `checker.mode === "plan"`：`conversation.addSystemReminder(buildPlanModeReminder(planPath, planExists, iteration))` 注入计划态提醒。
   3. 启流：`const stream = this.client.stream(this.conversation, toolSchemas, this.abortSignal)`。
   4. `for await (const event of stream)` 收集本轮：
      - `text_delta` → 累加 `fullText` 并 `yield { type: "stream_text", text }`。
      - `thinking_delta` → `yield { type: "thinking_text" }`。
      - `thinking_complete` → push 进 `thinkingBlocks`、`yield { type: "thinking_complete" }`。
      - `tool_call_complete` → push 进 `toolUses` 数组、`yield { type: "tool_use" }`。
      - `stream_end` → 记录 `stopReason`、`yield { type: "usage", usage }`。
   5. `catch` 流异常：检查 `abortSignal.aborted`（取消路径见步骤 7）；否则 `yield { type: "error", error }` 并 `return`。
   6. 取消检测：`if (this.abortSignal?.aborted)` → 若 `fullText` 非空则 `conversation.addAssistantFull(fullText, [], [])`、`yield { type: "loop_complete", stopReason: "interrupted" }`、`return`。
   7. 写历史：`conversation.addAssistantFull(fullText, thinkingBlocks, toolUses)`。
   8. **有工具调用** `toolUses.length > 0`：
      1. `const results = await this.executeTools(toolUses)`（保序分批，下述）。
      2. `for (const r of results) yield r`（按 push 顺序逐个吐 `tool_result`）。
      3. 未知工具统计：`for (const tu of toolUses)` 用 `this.registry.get(tu.toolName)` 判断；任一已注册即 `consecutiveUnknown = 0`，否则递增。`if (consecutiveUnknown >= 3)` → `yield { type: "error" }` + `return`。
      4. 把 `results` 转成 `ToolResultBlock[]`（对 `output.length > MAX_OUTPUT_CHARS` 做 10000 字符截断 + `"\n… (output truncated)"`）。
      5. `conversation.addToolResultsMessage(toolResults)`。
      6. 检查是否调用了 `ExitPlanMode`：若是则 `yield { type: "turn_complete" }`、`yield { type: "loop_complete", stopReason: "end_turn" }`、`return`（Plan Mode 退出由 TUI 后续处理）。
      7. `yield { type: "turn_complete" }`，下一轮继续。
   9. **无工具调用**：`looping = false`；`yield { type: "loop_complete", stopReason }`。

**`executeTools(toolUses)` 算法：**

```ts
private async executeTools(toolUses: ToolUseBlock[]): Promise<AgentEvent[]> {
  const events: AgentEvent[] = [];
  const readSafe: ToolUseBlock[] = [];
  const writeDangerous: ToolUseBlock[] = [];

  for (const tu of toolUses) {
    const category = this.registry.get(tu.toolName)?.category ?? "command";
    if (category === "read") readSafe.push(tu);
    else writeDangerous.push(tu);
  }

  if (readSafe.length > 0) {
    events.push(...await this.executeBatch(readSafe, /*parallel=*/ true));
  }
  for (const tu of writeDangerous) {
    events.push(...await this.executeBatch([tu], /*parallel=*/ false));
  }
  return events;
}
```

`executeBatch(toolUses, parallel)` 内部用 `StreamingExecutor`：

- 对每个 `tu` 先过 `PermissionChecker.check()`：`deny` → push `tool_result { isError: true }`；`ask` 且配了 `onPermissionRequest` → `await` 用户决定（本章仅占位）。
- 通过 → `executor.submit(toolId, toolName, args)`。
- `parallel=true`：循环结束后 `await executor.collectResults()`（`Promise.all`，并发）。
- `parallel=false`：每个 submit 后立即 `await executor.collectResults()`（一个一个跑）。

每个 result 经 `processToolResult` 转成 `{ type: "tool_result" }` 事件 push 进 `events`。

### src/agent/streaming-executor.ts（工具批执行器）**职责：** 提交工具调用、统一并发跑、捕获 throw、记录 elapsed（毫秒级，按秒数）。
**对外接口：** `submit()` / `collectResults()` / `hasPending()`。
**依赖：** `ToolRegistry`、`ToolContext`（`workDir` + 可选 `abortSignal` / `fileHistory` / `fileStateCache`）。

`collectResults()` 用 `[...this.pending]` 复制队列、清空 `this.pending`，对每个调用 `Promise.all` 跑 `tool.execute(args, ctx)`；未注册工具直接返回 `{ output: "Error: unknown tool '...'", isError: true }`，`execute()` throw 时返回 `{ output: "Error executing ...: ...", isError: true }`。

### src/llm/anthropic.ts、src/llm/openai.ts（扩展）**职责：** 把 ch03 的同步消息收集改为 `AsyncGenerator<StreamEvent>`，在 `stream_end` 上抛 `usage`。

- `AnthropicClient.stream(conv, tools, abortSignal)`：用 `this.client.messages.stream({ ..., tools, system: this.systemPrompt, signal: abortSignal })`；按 SDK 的 `inputJsonDelta` / `contentBlockStop` 拼出 `tool_call_complete.arguments`；流结束读 `acc.usage` 上抛 `stream_end`。
- `OpenAIClient.stream(conv, tools, abortSignal)`：用 `this.client.chat.completions.create({ ..., stream: true, stream_options: { include_usage: true }, signal: abortSignal })`；拼分片 `tool_calls[i].function.arguments`；流结束读 `chunk.usage` 上抛 `stream_end`。
- 错误归一化：`ContextTooLongError`、`RateLimitError`、`AuthenticationError`、`NetworkError`、`LLMError`（`src/llm/errors.ts`）。

### src/tools/registry.ts、src/tools/types.ts（扩展）

```ts
export class ToolRegistry {
  register(tool: Tool): void;
  get(name: string): Tool | undefined;
  listTools(): Tool[];
  getAllSchemas(protocol?: "anthropic" | "openai" | "openai-compat"): Record<string, unknown>[];
}
```

`getAllSchemas("openai")` 把每个 `tool.schema()` 包成 `{ type: "function", function: { name, description, parameters } }`；默认 `"anthropic"` 直接返回 schema。

6 个工具（ReadFile / Glob / Grep / WriteFile / EditFile / Bash）按语义打 `category`：
- `category: "read"` → ReadFile / Glob / Grep。
- `category: "write"` → WriteFile / EditFile。
- `category: "command"` → Bash。

### src/conversation/conversation.ts（扩展）

新增 `addAssistantFull(text, thinking, toolUses)`：把 assistant 回合的文本、推理块、工具调用一次性写入历史（`thinkingBlocks` / `toolUses` 为空数组时不挂字段，节省内存）。

新增 `addToolResultsMessage(results)`：把一组 `ToolResultBlock` 作为一条 user 回合写入（`content: ""`，`toolResults: results`），保证多工具结果合并在同一条消息里。

新增 `addSystemReminder(content)`：包成 `<system-reminder>\n${content}\n</system-reminder>` 写入 user 回合。

### src/prompt/plan-mode.ts（新增）

```ts
export function buildPlanModeReminder(
  planPath: string,
  planExist: boolean,
  iteration: number
): string;
```

`iteration === 1` 返回完整 `planModeFullReminder`，包含 5 阶段工作流（理解 / 设计 / 评审 / 出稿 / `ExitPlanMode`）；中间迭代每隔 `reminderInterval = 5` 轮重复完整提示，其余返回 `planModeSparseReminder` 节省 token。

### src/permissions/checker.ts（占位）

```ts
export type PermissionMode = "default" | "plan" | "bypass";

export interface Decision {
  effect: "allow" | "ask" | "deny";
  reason?: string;
}

export class PermissionChecker {
  mode: PermissionMode;
  planFilePath?: string;
  check(toolName: string, category: ToolCategory, args: Record<string, unknown>): Decision;
  allowAlways(toolName: string, args: Record<string, unknown>): void;
}
```

本章 `check()` 在 `mode === "plan"` 时对非 `"read"` 工具返回 `deny`，否则 `allow`；具体策略与 ask 流程后续章节细化。

### src/tui/app.tsx（扩展）

```tsx
function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [iteration, setIteration] = useState(0);
  const [usage, setUsage] = useState({ in: 0, out: 0 });
  const abortRef = useRef<AbortController | null>(null);

  useInput((input, key) => {
    if (key.ctrl && input === "c") {
      if (streaming) abortRef.current?.abort();
      else exit();
    } else if (key.escape && streaming) {
      abortRef.current?.abort();
    }
  });

  const submit = async (text: string) => {
    conversation.addUserMessage(text);
    setStreaming(true);
    abortRef.current = new AbortController();
    const agent = new Agent({ ...config, abortSignal: abortRef.current.signal });
    try {
      for await (const ev of agent.run()) {
        switch (ev.type) {
          case "stream_text":   /* 累积 currentReply */ break;
          case "tool_use":      /* 工具行追加到 messages */ break;
          case "tool_result":   /* 工具结果摘要追加 */ break;
          case "usage":         setUsage(u => ({ in: u.in + ev.usage.inputTokens, out: u.out + ev.usage.outputTokens })); break;
          case "turn_complete": setIteration(i => i + 1); break;
          case "loop_complete": /* 最终答复提交 */ break;
          case "error":         /* 灰色错误块 */ break;
        }
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };
  // ... Ink 组件树
}
```

## 模块交互

```
用户提交文本
  └─ App.submit:
       ├─ conversation.addUserMessage(text)
       ├─ abortController = new AbortController()
       ├─ agent = new Agent({ ..., abortSignal: abortController.signal })
       └─ for await (ev of agent.run()):
            └─ Agent.run (AsyncGenerator, ReAct 循环):
                 while looping:
                   ├─ iteration++; (若 plan 模式) conversation.addSystemReminder(buildPlanModeReminder(...))
                   ├─ stream = client.stream(conversation, toolSchemas, abortSignal)
                   │    └─ 适配器：把 SDK 流式 chunk 翻译为 StreamEvent
                   │         text_delta / tool_call_complete / stream_end{ usage }
                   │    → Agent 转发 stream_text、累积 toolUses、记录 usage、stopReason
                   ├─ yield usage
                   ├─ if abortSignal.aborted:
                   │    conversation.addAssistantFull(fullText, [], [])
                   │    yield loop_complete{ stopReason: "interrupted" }; return
                   ├─ conversation.addAssistantFull(fullText, thinkingBlocks, toolUses)
                   ├─ 有 toolUses:
                   │    ├─ executeTools:
                   │    │     readSafe (category==="read") 并发批 (Promise.all)
                   │    │     writeDangerous 串行批 (await 单个)
                   │    │     PermissionChecker.check → allow/ask/deny
                   │    │     StreamingExecutor.collectResults
                   │    ├─ yield tool_result × N (按 events.push 顺序)
                   │    ├─ 未知工具计数 >= 3 → yield error; return
                   │    ├─ 截断 output 写入 toolResults
                   │    ├─ conversation.addToolResultsMessage(toolResults)
                   │    ├─ ExitPlanMode 检测 → yield turn_complete + loop_complete; return
                   │    └─ yield turn_complete
                   └─ 无 toolUses:
                        looping = false
                        yield loop_complete{ stopReason }
  └─ App: 按事件 setState，Ink 自动重渲染

# Esc / Ctrl+C(streaming) → abortController.abort()
#   → SDK fetch 抛 AbortError → Agent 在 catch / abortSignal.aborted 分支收尾
```

并发模型：`conversation` 在 `Agent.run()` 的单 AsyncGenerator 内串行操作；`Promise.all` 跑的只读批由 `StreamingExecutor` 各自调用独立 `Tool.execute()`，互不写 `conversation`；result 收集回主流程后再批量 `addToolResultsMessage`。满足 N2/N6。

## 文件组织

```text
gcode/
├── src/
│   ├── agent/
│   │   ├── agent.ts                  — 新增：Agent 类、AgentConfig，承载 run() AsyncGenerator
│   │   ├── events.ts                 — 新增：AgentEvent discriminated union
│   │   └── streaming-executor.ts     — 新增：StreamingExecutor，工具批执行器
│   ├── llm/
│   │   ├── client.ts                 — 扩展：LLMClient.stream(conv, tools, abortSignal)；createClient 工厂
│   │   ├── events.ts                 — 扩展：StreamEvent + UsageInfo
│   │   ├── anthropic.ts              — 扩展：AsyncGenerator<StreamEvent>、stream_end 携带 usage
│   │   ├── openai.ts                 — 扩展：stream_options: { include_usage: true }
│   │   └── errors.ts                 — 新增：ContextTooLongError 等错误类（占位）
│   ├── tools/
│   │   ├── types.ts                  — 扩展：Tool 接口加 category
│   │   ├── registry.ts               — 扩展：getAllSchemas(protocol) 按协议输出 schema
│   │   ├── read-file.ts              — 修改：category = "read"
│   │   ├── glob.ts                   — 修改：category = "read"
│   │   ├── grep.ts                   — 修改：category = "read"
│   │   ├── write-file.ts             — 修改：category = "write"
│   │   ├── edit-file.ts              — 修改：category = "write"
│   │   └── bash.ts                   — 修改：category = "command"
│   ├── conversation/
│   │   └── conversation.ts           — 扩展：addAssistantFull / addToolResultsMessage / addSystemReminder
│   ├── prompt/
│   │   └── plan-mode.ts              — 新增：buildPlanModeReminder + 完整/精简模板
│   ├── permissions/
│   │   └── checker.ts                — 占位：PermissionChecker 接口与默认实现
│   └── tui/
│       └── app.tsx                   — 扩展：useEffect 消费 agent.run()、useInput 取消
├── package.json                      — 已有 dependencies
└── tsconfig.json                     — strict: true
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Loop 放哪 | `Agent.run()` 返回 `AsyncGenerator<AgentEvent>` | AsyncGenerator 天然把「事件流 + 取消传播」收敛在一个抽象里，Ink 端 `for await` 就能消费；改成回调或 EventEmitter 都得手动管 unsubscribe。 |
| 事件分派类型 | `AgentEvent` 用 discriminated union（按 `type` 字段） | TS 编译器对 `switch (ev.type)` 做穷尽性检查，新增事件类型时所有 `default` 分支编译报错，避免漏处理。 |
| 取消机制 | 标准 `AbortController` / `AbortSignal` | SDK（`@anthropic-ai/sdk`、`openai`、`fetch`）原生支持 `signal`，无需自造 token；Esc / Ctrl+C 调 `controller.abort()` 即可一路传播到 SDK 内部 fetch。 |
| 工具批结构 | 一次回复内：所有 `category === "read"` 并发一批、其余串行 | 用户选定的「保序分批」：read 之后的 write 不会被提前；只读才并发加速。`bash` 保守归 `"command"`，可执行任意副作用，按串行处理。 |
| 并发实现 | `Promise.all` 在 `StreamingExecutor.collectResults()` 内 | 标准 JS 并发原语；每个 `Tool.execute()` 自己返回 `Promise<ToolResult>`，错误用 try/catch 包成 `{ isError: true }`，不会让 `Promise.all` reject 整批。 |
| 用量统计 | 适配器在 `stream_end` 携带 `UsageInfo`，Agent `yield { type: "usage" }` 透传 | 两 SDK 的流式 usage 都在流尾才完整（Anthropic 在 `message_stop` event、OpenAI 需 `stream_options.include_usage` 后读最后一个 chunk）；统一在 `stream_end` 发一次。 |
| 工具结果截断 | `Agent.run()` 写入历史前对 `output` 做 10000 字符截断 + `"\n… (output truncated)"` 追加 | 兜底安全网：工具内部已截行/截字符，但 `bash` 可能产出未截过的大输出；二次截断防上下文炸掉。 |
| Plan Mode 注入方式 | 每轮 `conversation.addSystemReminder(buildPlanModeReminder(...))` | 把提醒作为 user 回合的 `<system-reminder>` 标签注入，避免单独维护 system prompt 后缀字段；首轮完整提示、之后精简，节省 token。 |
| 未知工具阈值 | 内置 `consecutiveUnknown >= 3` | 单次未知工具靠 `StreamingExecutor` 的 `"Error: unknown tool '...'"` 结构化错误回灌即可让模型纠偏；只有连续多次才说明在对幻觉工具空转。混入任一已注册即重置。 |
| `maxIterations` 配置化 | `AgentConfig.maxIterations` 可传，默认 0（不限） | TUI 默认放开，自动化场景（cron / 脚本）可传一个上限当兜底；本章默认 0 与 ch03 「单轮闭环」语义平滑过渡。 |
| `ExitPlanMode` 工具特判 | `Agent.run()` 检测 `toolUses` 含 `"ExitPlanMode"` 即 `yield loop_complete` 退出 | Plan 模式的语义出口是工具调用而非 LLM 自动停；不特判则模型会继续下一轮触发计划态约束反复。 |
| 工具 schema 多协议 | `ToolRegistry.getAllSchemas(protocol)` 内联协议适配 | anthropic 与 openai 工具 schema 字段名不同（前者 `input_schema`、后者 `function.parameters`）；让 registry 统一暴露，client 只需传 `protocol`。 |
| 文件后缀 | 全部 `.ts` / `.tsx`（TUI 组件） | bun 原生跑 TS/JSX，无构建步骤；测试用 `bun test` 直接吃 `.test.ts`。 |
````

````markdown
# Agent Loop Tasks

> 模块路径 `src/agent/*`、`src/llm/*`、`src/tools/*`、`src/conversation/*`、`src/prompt/*`、`src/permissions/*`、`src/tui/*`，运行时 bun + TypeScript 5.x。任务有序，每步留绿 `tsc --noEmit`。验证一律「先跑命令看输出，再下结论」。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `src/agent/events.ts` | `AgentEvent` discriminated union |
| 新增 | `src/agent/streaming-executor.ts` | `StreamingExecutor` 工具批执行器 |
| 新增 | `src/agent/agent.ts` | `Agent` 类与 `run()` AsyncGenerator |
| 修改 | `src/llm/events.ts` | `StreamEvent` 增 `stream_end`、`UsageInfo` 类型 |
| 修改 | `src/llm/client.ts` | `LLMClient.stream(conv, tools, abortSignal)` 签名 |
| 修改 | `src/llm/anthropic.ts` | `AsyncGenerator<StreamEvent>`，`stream_end` 携带 usage |
| 修改 | `src/llm/openai.ts` | `stream_options.include_usage`，OpenAICompat 同步 |
| 新增 | `src/llm/errors.ts` | `ContextTooLongError`、`RateLimitError` 等错误类 |
| 修改 | `src/tools/types.ts` | `Tool` 接口加 `category: ToolCategory` |
| 修改 | `src/tools/registry.ts` | `getAllSchemas(protocol)` 协议适配 |
| 修改 | `src/tools/{read-file,glob,grep,write-file,edit-file,bash}.ts` | 各打 `category` |
| 修改 | `src/conversation/conversation.ts` | `addAssistantFull` / `addToolResultsMessage` / `addSystemReminder` |
| 新增 | `src/prompt/plan-mode.ts` | `buildPlanModeReminder` + 完整/精简模板 |
| 新增 | `src/permissions/checker.ts` | `PermissionChecker` 占位实现 |
| 修改 | `src/tui/app.tsx` | `useEffect` 消费 `agent.run()`、`useInput` 取消 |
| 新增 | `src/agent/agent.test.ts` | 多轮 fake client、并发分批、停止条件、Plan 工具集 |

## T1: 定义 `AgentEvent` 与 `UsageInfo`（纯新增，向后兼容）**文件：** `src/agent/events.ts`、`src/llm/events.ts`
**依赖：** 无
**步骤：**
1. `src/llm/events.ts`：新增 `interface UsageInfo { inputTokens; outputTokens; cacheReadInputTokens; cacheCreationInputTokens }`；扩展 `StreamEvent` 联合类型加 `tool_call_start` / `tool_call_delta` / `tool_call_complete` / `stream_end { stopReason, usage }`。
2. `src/agent/events.ts`：定义 `AgentEvent` discriminated union（spec 列出的全部 9 个 `type` 分支）。

**验证：** `tsc --noEmit` 通过（纯新增类型）。

## T2: 工具 `category` 分类与多协议 schema**文件：** `src/tools/types.ts`、`src/tools/registry.ts`、`src/tools/{read-file,glob,grep,write-file,edit-file,bash}.ts`
**依赖：** 无
**步骤：**
1. `types.ts`：`export type ToolCategory = "read" | "write" | "command"`；`Tool` 接口加 `category: ToolCategory` 字段（必填，编译器会强制每个工具实现都补上）。
2. 6 个工具实现里各加一行 `category = "read" as const` 或 `"write"` / `"command"`：
   - `read-file.ts` / `glob.ts` / `grep.ts` → `"read"`
   - `write-file.ts` / `edit-file.ts` → `"write"`
   - `bash.ts` → `"command"`
3. `registry.ts`：`getAllSchemas(protocol: "anthropic" | "openai" | "openai-compat" = "anthropic")`——`"anthropic"` 直返 `tool.schema()`；`"openai"` / `"openai-compat"` 包装成 `{ type: "function", function: { name, description, parameters: base.input_schema } }`。

**验证：** `bun test` 全通过（接口加必填字段后 6 工具均实现，编译即证明完整）；`tsc --noEmit` 通过。

## T3: `ConversationManager` 三个新方法**文件：** `src/conversation/conversation.ts`、`src/conversation/conversation.test.ts`（已有）
**依赖：** 无
**步骤：**
1. `addAssistantFull(text, thinkingBlocks, toolUses)`：push `{ role: "assistant", content: text, thinkingBlocks: thinking.length > 0 ? thinking : undefined, toolUses: toolUses.length > 0 ? toolUses : undefined }`。
2. `addToolResultsMessage(results: ToolResultBlock[])`：push `{ role: "user", content: "", toolResults: results }`。
3. `addSystemReminder(content: string)`：push `{ role: "user", content: \`<system-reminder>\n${content}\n</system-reminder>\` }`。
4. 测试：每个新方法补 1 条单测——`getMessages()` 返回的最后一条结构正确（含 `toolResults` 数组、`toolUses` 数组、`<system-reminder>` 包裹标签）。

**验证：** `bun test src/conversation` 通过。

## T4: `buildPlanModeReminder` 与 plan 模板**文件：** `src/prompt/plan-mode.ts`
**依赖：** 无
**步骤：**
1. 定义两个模板常量：`planModeFullReminder`（含 5 阶段 Workflow：Initial Understanding / Design / Review / Final Plan / `ExitPlanMode`）、`planModeSparseReminder`（只剩关键规则）。
2. `buildPlanModeReminder(planPath, planExist, iteration)`：
   - 构造 `planFileInfo`：`"Plan file: ${planPath}"` + （存在则提示「可继续编辑」 / 不存在则提示「用 WriteFile 创建」）。
   - `iteration === 1` 返回 `planModeFullReminder.replace("%PLAN_FILE_INFO%", planFileInfo)`。
   - 其余按 `reminderInterval = 5` 切换完整/精简（精简版替换 `%PLAN_PATH%`）。
3. 顺便补 `buildPlanModeExitReminder` / `buildPlanModeReentryReminder`（TUI 切换 plan/normal 时用）。

**验证：** `bun test src/prompt` 通过；`tsc --noEmit` 无错误。

## T5: `LLMClient.stream()` 签名升级与适配器扩展**文件：** `src/llm/client.ts`、`src/llm/anthropic.ts`、`src/llm/openai.ts`、`src/llm/errors.ts`
**依赖：** T1
**步骤：**
1. `src/llm/errors.ts`：导出错误类——`LLMError`（基类）、`AuthenticationError`、`ContextTooLongError`、`RateLimitError`（带 `retryAfter?: string` 字段）、`NetworkError`。
2. `client.ts`：`LLMClient.stream(conv, tools, abortSignal?)` 返回 `AsyncGenerator<StreamEvent>`；保留 `MaxTokensSetter` 副接口（占位，后续章节用）；`createClient(cfg, systemPrompt)` 工厂按 `cfg.protocol` 动态 `await import("./anthropic.js")` / `await import("./openai.js")`。
3. `anthropic.ts`：`async *stream(...)`——
   - 构造 `params`：`model`、`max_tokens`、`system: this.systemPrompt`、`tools`、`messages: toAnthropicMessages(conv.getMessages())`、`signal: abortSignal`。
   - 用 `for await (const event of this.client.messages.stream(params))` 翻译事件：`content_block_delta.text_delta` → `text_delta`、`content_block_delta.input_json_delta` 拼到该 tool 的 args buffer、`content_block_stop` 把 buffer JSON.parse 后 yield `tool_call_complete`、`message_stop` 读 `event.message.stop_reason` 与 `event.message.usage` yield `stream_end`。
   - 把 SDK 错误归一化为 `ContextTooLongError` / `RateLimitError` / `AuthenticationError` / `NetworkError` 再 throw。
4. `openai.ts`：同结构——
   - 构造请求：`stream: true`、`stream_options: { include_usage: true }`、`tools`、`signal: abortSignal`。
   - 翻译 `chunk.choices[0].delta.content` → `text_delta`；`delta.tool_calls[i].function.arguments` 拼分片；末尾 `finish_reason` + `chunk.usage` yield `stream_end`。

**验证：** `tsc --noEmit` 通过；`bun test src/llm` 通过（含 fake provider 用 `AsyncGenerator` 模拟流的单测）。

## T6: `Agent` ReAct 循环主体（核心）**文件：** `src/agent/agent.ts`、`src/agent/streaming-executor.ts`、`src/permissions/checker.ts`、`src/agent/agent.test.ts`
**依赖：** T1, T2, T3, T4, T5
**步骤：**
1. `streaming-executor.ts`：按 plan 给出的签名实现 `submit()` / `collectResults()`——`Promise.all` 跑工具，未注册返回 `"Error: unknown tool '...'"`、`execute` throw 时返回 `"Error executing ${name}: ${err.message}"`，记录 `elapsed = (Date.now() - start) / 1000`。
2. `checker.ts`：定义 `PermissionMode` / `Decision` 类型；`PermissionChecker` 类含 `mode` 字段与 `check()` 方法，本章 `"plan"` 模式 deny 非 read 工具、其余 `allow`；保留 `allowAlways()` 占位。
3. `agent.ts`：
   - 导入 `AgentEvent`、`LLMClient`、`ConversationManager`、`ToolRegistry`、`PermissionChecker`、`StreamingExecutor`、`buildPlanModeReminder`。
   - 定义 `AgentConfig` 接口 + `Agent` 类（按 plan 给出的字段列表）。
   - `MAX_OUTPUT_CHARS = 10000` 常量。
   - `async *run(): AsyncGenerator<AgentEvent>`：按 plan 「`run()` 算法」逐步实现：
     1. 取 `toolSchemas = this.registry.getAllSchemas()`。
     2. `iteration`、`consecutiveUnknown`、`looping` 状态变量。
     3. `while (looping)` 内：iteration 上限检查 → plan 模式 `addSystemReminder` → 创建 `stream` → `for await` 收集 → `catch` 错误（区分 `aborted` / 其他错误 / `ContextTooLongError`：本章只把 `ContextTooLongError` 当普通 error 处理，留 ch07 接 `forceCompact`）→ 取消检测 → `addAssistantFull` → 有工具走 `executeTools` 路径、无工具 yield `loop_complete`。
   - `executeTools(toolUses)`：按 `category` 切两组、只读批 `executeBatch(readSafe, true)`、写入批 `executeBatch([tu], false)`。
   - `executeBatch(toolUses, parallel)`：循环 submit；`parallel === true` 末尾 `await executor.collectResults()`，否则每次 submit 后立即 collect；每个 result 经 `processToolResult` 转成 `AgentEvent.tool_result` push 进 `events`。
   - `processToolResult(r, toolUses, events)`：本章只做 push（后续章节接 file snapshot / hooks）。
4. `agent.test.ts`：写 6 个场景用例（用 `mock` 的 `LLMClient` 与自定义工具）。
   - **场景 A（多轮 AC1）**：`fakeClient` 维护 `scripts: StreamEvent[][]`，第一次 yield 一个 `tool_call_complete` (ReadFile) + `stream_end`，第二次 yield `text_delta` + `stream_end`；断言事件序列含 `tool_use`、`tool_result`、`turn_complete`、`stream_text`、`loop_complete`；`conversation.getMessages()` 末尾是 assistant 文本。
   - **场景 B（上限 AC3）**：`fakeClient` 恒返工具调用；`new Agent({ maxIterations: 5, ... })`；断言收到 `{ type: "error" }`、`fakeClient.callCount === 5`。
   - **场景 C（未知工具 AC4）**：`fakeClient` 连续返回未注册工具名 3 次；断言第 3 轮后 yield `error`；另一用例第 2 轮混入一个 ReadFile 调用、断言计数重置、不提前停。
   - **场景 D（保序分批 AC8）**：自定义 registry 注册两个插桩工具：`SlowRead`（`category: "read"`，execute 内记录开始时间并 sleep 50ms）、`SlowWrite`（`category: "write"`，记录开始时间并 sleep 50ms）。脚本一轮返回 `[SlowRead, SlowRead, SlowWrite]`；断言两 SlowRead 的执行时间窗重叠（`endA > startB && endB > startA`）、SlowWrite 的 `startTime` 晚于两个 SlowRead 的 `endTime`、`events` 内 `tool_result` 顺序匹配调用序。
   - **场景 E（取消 AC9 AC10）**：插桩工具 execute 中阻塞 1s；测试侧在 100ms 后调 `abortController.abort()`；断言 generator 最终 yield `{ type: "loop_complete", stopReason: "interrupted" }`、`conversation.getMessages()` 末尾配对合法（最后一条是 assistant 文本，无悬空 tool_use）。
   - **场景 F（Plan Mode AC13）**：`checker.mode = "plan"`；`fakeClient` 把收到的 `messages` 记录下来；断言最后一条 message 的 content 含 `"<system-reminder>"` + `"Plan mode is active"`；模拟模型调用 `ExitPlanMode` → 断言下一轮不再继续，yield `loop_complete`。

**验证：** `bun test src/agent` 全通过；`tsc --noEmit` 无错误。

## T7: TUI 接入 `agent.run()` 事件流**文件：** `src/tui/app.tsx`
**依赖：** T6
**步骤：**
1. `useState` 维护：`messages: ChatMessage[]`、`currentReply: string`、`currentTools: ToolBlockInfo[]`、`streaming: boolean`、`iteration: number`、`usage: { in: number; out: number }`。
2. `useRef<AbortController | null>(null)` 持本轮 controller。
3. `useInput((input, key) => { ... })`：
   - `key.ctrl && input === "c"`：`streaming` 为真则 `abortRef.current?.abort()`（不退应用）；否则 `exit()`（退应用）。
   - `key.escape && streaming`：`abortRef.current?.abort()`。
4. `submit(text)` 异步函数：
   - `conversation.addUserMessage(text)`；`setStreaming(true)`；新建 `AbortController`。
   - `const agent = new Agent({ client, registry, checker, conversation, workDir, abortSignal })`。
   - `for await (const ev of agent.run())` 按 `switch (ev.type)` 分派：
     - `stream_text` → `setCurrentReply(s => s + ev.text)`。
     - `tool_use` → `setCurrentTools(ts => [...ts, { name: ev.toolName, id: ev.toolId, args: ev.args, status: "running" }])`；若 `currentReply` 非空先把 preamble 提交 messages 并清空。
     - `tool_result` → 把队首匹配 `ev.toolId` 的工具标 done 并提交一条 `messages` 行；`setCurrentTools` 移除该条。
     - `usage` → `setUsage(u => ({ in: u.in + ev.usage.inputTokens, out: u.out + ev.usage.outputTokens }))`。
     - `turn_complete` → `setIteration(i => i + 1)`。
     - `loop_complete` → `setMessages([..., { role: "assistant", content: currentReply, stopReason: ev.stopReason }])`、清 `currentReply` / `currentTools` / `iteration`。
     - `error` → push 一条灰色错误 message。
   - `finally` 块：`setStreaming(false)`、`abortRef.current = null`。
5. 渲染：`<Static items={messages}>` 历史区不重渲染；动态区里 `currentTools.map(t => <ToolDisplay ... />)`；状态栏组件接收 `usage`、`iteration` 作为 props 显示。

**验证：** `bun run src/main.tsx`（需 `.gcode/config.yaml` 配好 provider）启动 Ink 应用、跑一条多轮任务、Esc 中断、再发一条继续；`tsc --noEmit` 无错误。

## T8: 全量验证与端到端冒烟**文件：** 无（验证）
**依赖：** T1–T7
**步骤：**
1. `tsc --noEmit`（编译期类型检查）。
2. `bun test`（全量单测，含 agent / llm / tools / conversation）。
3. 端到端（openai-compat 端点，用 `.gcode/config.yaml`）：
   - 多轮（AC1）：问「读 `docs/ch03/spec.md`，再据其内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ 观察 ReadFile → WriteFile 跨多轮自动连环、状态栏用量增长、动态区轮次递增、最终答复。
   - 取消（AC10）：发一个会跑多步的任务，中途按 Esc / Ctrl+C → 回空闲态不退出 → 再正常发一条继续对话（验证历史未坏）。
   - 流出错（AC5）：临时改坏 `base_url` 或断网发一条 → 错误提示、Ink 应用不退出、改回后继续。
   - Plan Mode（AC13）：把 `checker.mode` 切到 `"plan"` → 问「给登录功能加单测的方案」→ 观察只出现 Read/Glob/Grep + 计划文本、无 Write/Bash → 模拟 `ExitPlanMode` 工具 → 切回正常模式。
4. （可选）若有 anthropic 配置，重复多轮场景验证跨协议一致（AC14）。

**验证：** 全部命令通过、端到端各场景符合预期；密钥不回显（通读输出，AC/N7）。

## 执行顺序

```text
T1 ─┬─ T5 ─┐
T2 ─┤      │
T3 ─┼──────┼─ T6 ─┬─ T7 ─┐
T4 ─┘      │      │      │
           └──────┘      └─ T8
```

（T1–T4 互相独立可并行；T5 依赖 T1；T6 依赖 T1/T2/T3/T4/T5；T7 依赖 T6；T8 收尾全部。）
````

```javascript
# Agent Loop Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为；括号内为验证方式与对应需求。

## 实现完整性

- [ ] 多轮自动连环：需要连续两步工具的任务，Agent 无需中途催促即自动多轮执行工具直到给出最终答复（验证：`bun run src/main.tsx` 跑「读 A 文件 → 据内容新建 B 文件」，观察 ReadFile 与 WriteFile 跨多轮依次出现、最终答复）。(AC1/F1)
- [ ] 自然完成停止：模型给出无工具调用的纯文本即停，`yield { type: "loop_complete" }` 后 AsyncGenerator 结束（验证：agent.test.ts 场景 A 断言收到最终 `stream_text` + `loop_complete`，`fakeClient.callCount` 不再增长）。(AC2/F2)
- [ ] 迭代上限兜底：`AgentConfig.maxIterations = 5` 时第 5 轮后 `yield { type: "error" }` 退出，不无限循环（验证：agent.test.ts 场景 B 断言 error 事件 + `callCount === 5`）。(AC3/F2)
- [ ] 连续未知工具停止：连续 3 轮只产生未注册工具调用即停；混入已注册工具则计数重置（验证：agent.test.ts 场景 C 两路断言）。(AC4/F2)
- [ ] 流出错恢复：`client.stream()` throw 非 `RateLimitError` 异常时 `yield { type: "error" }`、Ink 应用不退出（验证：端到端临时改坏 base_url 发一条，观察错误块 + 仍可继续；agent.test.ts 注入 throw 脚本断言收到 `error` 后 generator 结束）。(AC5/F2)
- [ ] 事件流完备：`AgentEvent` 联合类型覆盖 `stream_text` / `tool_use` / `tool_result` / `usage` / `turn_complete` / `loop_complete` / `error` / `retry` / `permission_request` / `thinking_*` / `compact`（验证：agent.test.ts 收集事件后断言 `new Set(events.map(e => e.type))` 包含上述类型；TypeScript `switch (ev.type)` 全分支编译期穷尽性检查）。(AC6/F3/N6)
- [ ] 流式收集双路：`text_delta` 实时显示的同时，`tool_call_complete.arguments` 拼齐为可用对象（验证：agent.test.ts 断言 `toolUses[0].arguments` 是 JS Object 且字段完整；端到端工具行参数与请求体一致）。(AC7/F4)
- [ ] 保序分批并发：一次回复含多个工具时，`category === "read"` 的工具用 `Promise.all` 并发执行、`"write"` / `"command"` 串行，结果按 `events.push` 顺序回灌（验证：agent.test.ts 场景 D 用插桩工具断言两只读时间窗重叠、写入工具开始时刻晚于两只读完成、`events` 内 `tool_result` 顺序匹配调用序）。(AC8/F5)
- [ ] 取消历史一致：`abortController.abort()` 后 generator 在下一个 `await` 点退出、`fullText` 写入历史保证 assistant 文本回合存在、无悬空 `tool_use`（验证：agent.test.ts 场景 E 断言 `conversation.getMessages()` 最后一条是 assistant、`toolUses` 字段不残留；端到端取消后再发一条不报 400）。(AC9/F6)
- [ ] 用户取消：流式态 Esc 或 Ctrl+C 触发 `AbortController.abort()`、Agent 收尾、Ink 应用不退出；空闲态 Ctrl+C 走 `exit()` 退应用（验证：端到端各按一次观察行为）。(AC10/F7)
- [ ] 用量展示：状态栏显示会话累计 token（输入/输出），随 `usage` 事件递增（验证：端到端跑多轮观察状态栏数值递增；agent.test.ts 断言每轮 yield 一次 `usage` 事件）。(AC11/F8)
- [ ] 进度展示：流式态动态区显示当前迭代轮次（验证：端到端跑多轮任务观察「第 N 轮」递增；TUI 状态由 `turn_complete` 事件驱动）。(AC12/F9)
- [ ] Plan Mode：`checker.mode === "plan"` 时每轮通过 `addSystemReminder(buildPlanModeReminder(...))` 注入计划态提醒；模型调用 `ExitPlanMode` 即停（验证：agent.test.ts 场景 F 断言 message 含 `"<system-reminder>"` + `"Plan mode is active"`、`ExitPlanMode` 后 generator 结束）。(AC13/F10)

## 集成

- [ ] 跨协议一致：anthropic 与 openai（含 openai-compat base_url）跑同一多轮任务，触发/执行/回灌/用量/取消行为一致（验证：两种 `cfg.protocol` 配置各跑多轮场景；`createClient` 工厂动态 import 正确适配器）。(AC14/F11)
- [ ] 多轮历史正确携带：每轮 `addAssistantFull`（含 `toolUses`） + `addToolResultsMessage` 按序入历史并被下一轮 `client.stream()` 读到（验证：agent.test.ts 断言 `conversation.getMessages()` 序列；或在 fakeClient 内记录每轮收到的 messages 数组并断言增长）。(F6)
- [ ] 界面不阻塞：多轮循环与工具执行（含并发批）期间 Ink spinner / 轮次 / 计时持续刷新（验证：跑含稍慢 bash 的任务，观察界面不冻结；`Agent.run()` 是 AsyncGenerator，每个 `yield` 让出事件循环）。(N2)
- [ ] scrollback 顺序正确：跨多轮 preamble → 工具行 → 结果摘要 → 最终答复按序提交到 `<Static>` 区域不交错，并发批的工具行按模型调用序排列（验证：跑一个含并发只读批 + 后续写的多轮任务，回滚 scrollback 肉眼核对各块严格按发生顺序连续）。(N3)
- [ ] 结果体量受控：大文件 / 长输出 / 海量命中被 `Agent.run()` 内 `MAX_OUTPUT_CHARS = 10000` 截断标注 `"\n… (output truncated)"`，多轮累积不撑爆（验证：多轮中读大文件 / 跑长输出命令观察截断）。(N4)
- [ ] 取消无泄漏：取消后无挂起 Promise / 无残留 AsyncGenerator（验证：`bun test` 含取消用例（场景 E）通过、不报 "Worker did not exit"；端到端反复触发取消后继续对话多次，进程内存稳定不增长）。(N5)
- [ ] 类型安全：所有 `switch (ev.type)` 经穷尽性检查（验证：在 `switch` 内加 `default` 返回 `never`，TypeScript 编译期对漏分支报错；`tsc --noEmit` 通过）。(N6)

## 编译与测试

- [ ] `tsc --noEmit` 无错误。
- [ ] `bun test` 全部通过（agent、llm、tools、conversation、prompt 单测）。
- [ ] `bun test src/agent` 通过——含 6 个场景（A 多轮 / B 上限 / C 未知工具 / D 保序分批 / E 取消 / F Plan Mode）。
- [ ] `bun run src/main.tsx` 能正常启动 Ink 应用、提示输入。
- [ ] 密钥不回显：对话区与任何输出均不出现 api_key（验证：通读运行输出、`grep -ri "sk-" .gcode/` 无明文 key）。(N7)
- [ ] ES module 导入路径全部以 `.js` 后缀写（bun + Node ESM 规则，源码是 `.ts` 但 import 时写 `.js`）；`tsc --noEmit` 不报模块解析错。(N8)

## 端到端场景

- [ ] 场景 1（多轮连环）：openai-compat 端点 → 「读 `docs/ch03/spec.md`，再据内容新建 `docs/ch03/summary.txt` 写一句话摘要」→ ReadFile → WriteFile 跨多轮自动出现 → 状态栏 `usage` 增长、动态区轮次递增 → 最终答复 → Ctrl+C(空闲态) 退应用无残留进程。
- [ ] 场景 2（用户取消）：发一个多步任务，中途按 Esc（再试 Ctrl+C）→ 回空闲态不退出 → 再正常发一条继续对话（`conversation.getMessages()` 末尾配对合法、下一轮 API 请求不报 400）。
- [ ] 场景 3（流出错恢复）：临时改坏 `base_url` 发一条 → 错误块 + Ink 应用不退出 → 改回 `.gcode/config.yaml` 后继续正常对话。
- [ ] 场景 4（Plan Mode）：把 `checker.mode = "plan"` → 问一个改动类需求 → 只出现 Read/Glob/Grep + 计划文本、无 Write/Bash → 模拟 `ExitPlanMode` 工具调用 → 切回正常模式重新提交可执行 Write/Bash。
- [ ] 场景 5（跨协议，若有 anthropic 配置）：切到 `cfg.protocol: "anthropic"` 重跑场景 1 → 多轮行为与 openai-compat 一致。
- [ ] 场景 6（迭代上限）：主要由 agent.test.ts 场景 B 确定性验证；可选手动复现——`new Agent({ maxIterations: 3, ... })` 跑一个会多步调工具的任务，观察第 3 轮后 yield `error`、Ink 应用仍可继续。
- [ ] 场景 7（连续未知工具）：主要由 agent.test.ts 场景 C 确定性验证；可选手动复现——在 system prompt 临时引导模型调用一个不存在的工具名，观察连续 3 轮后 yield `error`、Ink 应用仍可继续。
```


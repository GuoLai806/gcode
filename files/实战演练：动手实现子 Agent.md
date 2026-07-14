# 第13章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装上了 Hook 生命周期钩子系统，Agent 在关键节点上有了可编程的扩展能力。但不管你挂了多少 Hook，干活的还是同一个 Agent。所有任务都塞进同一个对话上下文，上下文越来越长，噪声越来越多，Token 越烧越快。

这一章要解决的就是这个问题：让 GCode 从单 Agent 进化到能分发任务的多 Agent 架构。做完之后，主 Agent 可以把子任务委派给独立的子 Agent，每个子 Agent 有自己的上下文、工具集和权限边界，干完活把结果交回来就行。

具体要新增这些东西：

* **Agent 定义与加载&#x20;**：AgentDefinition 数据结构、YAML frontmatter + Markdown body 解析、多来源加载器（项目级 > 用户级 > 内置级 > 插件级）

* **统一 Agent 工具&#x20;**：一个 Agent 工具通过 `subagent_type` 参数分流定义式和 Fork 两条路径

* **Fork 路径&#x20;**：继承父 Agent 完整对话历史，利用 prompt cache 降低成本

* **RunToCompletion&#x20;**：子 Agent 的非交互式执行循环

* **工具过滤多层防线&#x20;**：全局禁止 + 自定义限制 + 后台白名单 + 定义层 tools/disallowedTools

* **TaskManager 后台任务&#x20;**：后台启动、自动超时、ESC 手动切换、task-notification 异步回传

* **父子链路追踪&#x20;**：TraceRegistry 记录调用链、Token 消耗、执行状态

* **Slash 命令&#x20;**： `/tasks` 、 `/task info` 、 `/task cancel`

* **三个内置 Agent&#x20;**：Explore（haiku 模型只读探索）、Plan（只读规划）、general-purpose（全能力通用）

这章 **不做&#x20;**：Worktree 级文件系统隔离（下一章）、Agent Team 多 Agent 协作编排（后续章节）、Trace 的跨会话持久化。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：让主 Agent 能把子任务委派给独立的子 Agent，每个子 Agent 有自己干净的上下文、受限的工具集和独立的权限追踪。定义式子 Agent 按预定义角色执行；Fork 式子 Agent 继承父对话历史并借 prompt cache 降成本。子 Agent 跑完把结果异步送回主 Agent，上下文污染的问题彻底解决。

技术要求：

- 一个统一的 Agent 工具，用类型参数分流「定义式」和「Fork 式」两条路径，工具列表始终稳定
- 角色用 Markdown 加 YAML frontmatter 定义（工具白黑名单、模型、最大轮次、权限模式），多来源加载、同名覆盖
- 定义式从空白对话加固定角色启动；Fork 式继承父对话历史和工具集，让首次请求命中缓存省钱
- 运行时状态隔离（消息、权限、文件读缓存、token 计数），基础设施共享（LLM 客户端、Hook 引擎、文件系统）
- 子 Agent 用「跑到底」模式非交互执行，模型不再调工具就算完成，结果异步通知回主对话
- 工具过滤多层防线（全局禁止、角色额外限制、后台白名单），防止子 Agent 无限嵌套
- 后台任务管理器追踪状态、结果、用量，支持三种进入后台的方式（显式指定、超时自动、手动切），Fork 强制走后台

这一步先不做 Worktree 文件隔离、多 Agent 团队编排、后台任务的跨会话持久化。

Agent 定义格式：

- frontmatter：角色名、用途说明、工具白名单、工具黑名单、模型（继承或指定 haiku/sonnet/opus）、最大轮次、权限模式
- 正文是子 Agent 的系统提示，定义它的身份、职责和工作风格，伴随它整个生命周期
- 加载优先级：项目级高于用户级，高于内置，高于插件，前者覆盖后者
```

然后 AI 就会开始问你问题，进行需求澄清。



你根据理论篇学到的内容回答这些问题，一直这样反复循环对齐需求，最后就能生成四份文档了。



### 正式开发

四份文档有了之后，就相当于施工图纸已经定好了，然后让 Claude Code 根据这四份文档进行开发

![]()

经过一段时间后，开发完成。

![]()



### 功能验证过程

来验收一下结果



我们现在先看内置的子Agent，包括有Explore（探索专家）、Plan（架构师）、general-purpose（通用）

![]()



然后我们现在试试这些子Agent，先试试Explore Agent，来搜索，我们输入

![]()

然后GCode就会调用Explore Agent去探索，我们只需要等待就可以了



等待一会后，结果就会出来了，可以看到它把当前我们的go文件都一一搜索出来

![]()



如果我们想并行做计划，可以输入

![]()

等待一会后，就有一个详细的计划出来了

![]()



这也是子Agent的核心价值之一，不需要说我们等完一个执行，才能再等另一个，同时这些子Agent之间不会互相干扰，导致明明写电商系统混进了外卖系统的东西，或者是外卖系统混进了电商系统的东西



我们再试试自定义的Agent，比如我们的自定义个安全审查子Agent

```markdown
---
name: security-reviewer
description: 代码安全审查专家。识别注入、敏感信息泄露、输入校验缺失、权限越界等漏洞，按严重程度分级输出。只读，不修改任何文件。
model: sonnet
maxTurns: 20
permissionMode: bypassPermissions
disallowedTools:
  - Agent
  - EditFile
  - WriteFile
  - Bash
---

你是一个专注于代码安全审查的 Agent，只读模式。

## 职责
- 检查代码中的安全漏洞（SQL / 命令 / 路径注入、XSS、SSRF、反序列化、不安全的反射等）
- 识别硬编码密钥、token、密码、内网地址、调试后门等敏感信息泄露风险
- 评估输入校验、输出编码、错误处理是否完整
- 检查权限边界（越权读 / 写、不必要的 admin 调用、缺失的 auth check）
- 检查依赖与上游（老旧库、known CVE 的版本、不可信来源）
- 检查并发与资源（race condition、未释放的句柄、可被拖垮的无界循环 / 队列）

## 工具用法
- 用 Grep / Glob 定位可疑模式（`os/exec`、`Sprintf` 拼 SQL / URL、`http.Get(userInput)`、`json.Unmarshal` 到 interface 等）
- 用 ReadFile 精读上下文，不要凭文件名或一行 grep 结果猜测
- 不修改任何文件，不执行任何命令

## 输出格式
每条发现按以下结构：

### [SEVERITY] 标题
- **位置**: `path/to/file.go:行号`
- **问题**: 一句话说明漏洞
- **触发条件**: 怎样的输入 / 调用路径能利用
- **修复建议**: 具体改法，必要时贴改后的代码片段

severity 三档：

- `HIGH`：可被远程利用、能拿到敏感数据 / 能执行任意代码 / 能绕过认证
- `MEDIUM`：需要一定条件才能利用，或后果可控但确实是漏洞
- `LOW`：硬编码默认值、缺失日志、注释里的 TODO 等卫生问题

报告末尾按 severity 汇总数量，并列出"建议人工复审"的区域（你扫过但不确定的部分）。

如果没发现问题，明确说"未发现已知模式的漏洞，建议人工复审 X / Y 区域"，不要硬凑。
```

我们在.gcode/agents/security-reviewer.md里定义就好，然后打开GCode，问问有啥子Agent

![]()

可以看到，我们的自定义Agent已经注册成功，我们来试试

![]()

nice，可以正常工作



验收没问题，那么本章的主要任务就完成了。



可能你会注意到我们的子Agent会有些问题，如果是共同修改文件冲突了怎么办？



下一章，我们用 Git Worktree 实现文件系统级别的隔离，让多个子 Agent 可以同时修改代码而不冲突。

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

````markdown
# SubAgent 机制 Spec## 背景

GCode 目前是单 Agent 架构：所有任务在同一个对话上下文里执行。这导致两个问题：

1. **上下文污染**：长任务后再做无关任务,前序中间结果(读过的文件、diff、错误回放)成为后续任务的噪声,token 飙升、响应质量下降
2. **无法并行**：没有把独立子任务分发出去并行执行的机制,主对话被长任务阻塞

gcode 已经有「子 Agent 雏形」：

- ch11 Skill fork 模式通过 `agent.WithAllowedTools` 创建受限子 Agent(tui/skill_fork.go `runSubAgent`),走 `subAgent.Run(...)` 跑完一轮
- `Conversation.NewFromMessages` / `ReplaceMessages` 已支持深拷贝消息列表

但还缺：
- 没有统一的、可被主 Agent 主动调用的 **Agent 工具**——子 Agent 只能由 Skill fork 触发
- 没有 **角色定义文件** 加载机制(Agent 角色全部写死在 fork closure 里)
- 没有 **后台任务管理**——所有子 Agent 当前都是阻塞前台模式
- 没有 **工具过滤多层防线**——子 Agent 理论上可以无限嵌套
- Skill fork 与未来 SubAgent 工具两套代码并存

本章把上述能力补齐,让 gcode 从单 Agent 进化到可分发任务的主从架构。

## 目标- **G1**:提供统一的 Agent 工具,主 Agent 通过 `subagent_type` 参数选择预定义角色或留空走 Fork 路径;工具列表对模型始终稳定(不因角色定义增减而变化)
- **G2**:子 Agent 拥有独立的运行时状态——**消息**、**权限账本**(独立 Engine 决策状态)、**文件读缓存**、**token 计数**;共享基础设施——LLM 客户端、Hook 引擎、文件系统、tool.Registry
- **G3**:支持两种创建模式:
  - **定义式**:指定 `subagent_type`,从空白对话 + 预定义角色 prompt 启动
  - **Fork 式**:不指定 `subagent_type`,克隆父对话历史并注入 Fork Boilerplate,借 prompt cache 降首次请求成本
- **G4**:角色定义为 Markdown + YAML frontmatter 文件;支持多来源加载,优先级:项目级 > 用户级 > 内置 > 插件;同名定义按 source 优先级覆盖,前者覆盖后者
- **G5**:子 Agent 以 **RunToCompletion** 模式执行——任务直接注入对话,模型不再调工具即结束,返回最后一条 assistant 文本作为结果
- **G6**:子 Agent 在工具调用时遇到权限判定,按 **三层升级链** 处理:① 父对话已批准账本 → ② 角色 frontmatter 的 `permissionMode` 兜底 → ③ 仍无法决定时升级到主 TUI 询问用户(子 Agent 暂停、用户响应、子继续)
- **G7**:支持后台任务:三种进入方式——① 显式 `run_in_background:true`、② 前台超时 120 秒自动切后台、③ ESC 手动切后台;Fork 路径无条件后台;Fork Boilerplate 注入到子 Agent 首条消息约束其行为
- **G8**:后台任务跑完通过 `<task-notification>` 自动注入主对话(主 Agent 下次 turn 即看到);主 Agent 可通过 `TaskList`/`TaskGet`/`TaskStop` 工具主动查询和操控,可通过 `SendMessage` 给已跑完的、仍存活的后台 Agent 续派任务
- **G9**:工具过滤多层防线阻断子 Agent 无限嵌套——全局禁止列表(子 Agent 永远不能用 Agent 工具)、后台白名单(后台 Agent 只能用基础读写网络工具)、定义层 `tools`/`disallowedTools` 业务约束
- **G10**:复用 SubAgent 底座统一 Skill fork 路径——`tui/skill_fork.go` 的 `runSubAgent` 改为调用 SubAgent 公共启动函数,两条路径走同一段 agent 构造逻辑
- **G11**:内置 3 个角色——`general-purpose`(全工具)、`Explore`(只读探索,haiku)、`Plan`(只读规划);插件级保留接口占位但本期不实现真插件加载,加载顺序里插件来源恒为空

## 功能需求### Agent 工具- **F1**:新建 `Agent` 工具,参数(JSON Schema):
  - `prompt`(string,必填):交给子 Agent 的任务指令
  - `description`(string,必填):一句话描述任务,供 UI 展示
  - `subagent_type`(string,可选):指定预定义角色名,留空时走 Fork 路径
  - `model`(string,可选):模型覆盖,取值 `haiku` / `sonnet` / `opus` / `inherit`;留空沿用 Agent 定义的 model
  - `run_in_background`(bool,可选):true 时强制后台启动;Fork 路径忽略此字段(无条件后台)
  - `name`(string,可选):给本次启动的子 Agent 命名,供 SendMessage 用;同名后启动的覆盖前面的弱引用
- **F2**:Agent 工具的 `Execute`:
  - subagent_type 非空:`catalog.Resolve(name)` 取定义;不存在则返回结构化错误「未知 subagent_type: X」
  - subagent_type 为空:走 Fork 路径,从 `catalog` 取「fork 默认基础定义」(prompt body=Fork Boilerplate)
  - 按 `run_in_background` 与 Fork 强制规则,选择 inline 跑(阻塞返回 finalText)或 background 跑(返回 `{task_id, status:"async_launched"}`)
- **F3**:Agent 工具被全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS` 标记——任何子 Agent 都看不到 Agent 工具,从根源上断绝嵌套

### Agent 定义文件- **F4**:Agent 定义文件是 Markdown,以 `---` frontmatter 块开头、紧跟正文(子 Agent 系统提示);frontmatter YAML 字段:
  - `name`(必填):角色名,小写字母 / 数字 / 连字符,长度 1-32
  - `description`(必填):一句话描述,用于 Agent 工具的 `subagent_type` 文档与 UI 列表
  - `tools`(可选,string array):工具白名单
  - `disallowedTools`(可选,string array):工具黑名单
  - `model`(可选):`haiku` / `sonnet` / `opus` / `inherit`,缺省 `inherit`
  - `maxTurns`(可选,int):最大迭代轮数,缺省继承全局 `maxIterations=25`
  - `permissionMode`(可选):`default` / `acceptEdits` / `plan` / `bypassPermissions` / `dontAsk`,缺省 `default`;`dontAsk` 是子 Agent 专属——自动批准所有规则未命中的工具
  - `background`(可选,bool):缺省 false;true 时 Agent 工具忽略 `run_in_background` 参数、强制后台
- **F5**:Catalog 三层加载(本期插件级恒为空),顺序:
  1. 项目级:`<root>/.gcode/agents/*.md`
  2. 用户级:`~/.gcode/agents/*.md`
  3. 内置级:二进制 embed 的 `subagent/builtin/*.md`
- **F6**:同名定义按 source 优先级覆盖——项目级 > 用户级 > 内置级;`Resolve(name)` 返回优先级最高的版本
- **F7**:Catalog 启动期加载,加载失败的单个文件(frontmatter 不合法、name 重名以外的字段错)走 stderr 警告并跳过,不阻断启动
- **F8**:本章不引入插件加载器——`SourcePlugin` 常量保留供未来扩展;加载顺序里第四层恒为空切片

### 子 Agent 运行时- **F9**:扩展 `agent.Agent` 增加 `RunToCompletion(ctx, conv, task) (string, error)` 方法:
  - 把 `task` 作为 user 消息追加到 conv
  - 进入 ReAct 循环,maxTurns 由 `Agent.maxTurns` 决定(子 Agent 用 frontmatter,主 Agent 不变=25)
  - 模型不再调工具时结束循环,取末尾 assistant 文本返回
  - 触达 maxTurns 时返回最后一条 assistant 文本 + 「达到最大轮数」错误
  - 同一段循环代码与主对话 Run 共用,不重复实现
- **F10**:新增 Agent 选项:
  - `WithSystemPrompt(text)`:子 Agent 启动时把 text 作为 system prompt 注入(覆盖默认 gcode 主 Agent 系统提示)
  - `WithProvider(p)`:让子 Agent 用与父不同的 provider(model 覆盖时切换)
  - `WithMaxTurns(n)`:限制本 Agent 的最大迭代轮数
  - `WithPermissionMode(m)`:子 Agent 启动模式
  - `WithParentEngine(eng *permission.Engine)`:子用父 Engine 做权限决策一级查找(本期所有 Agent 共享同一 Engine,但增加显式参数预留隔离扩展)
- **F11**:子 Agent 的运行时状态隔离——独立 `SessionRuntime`、独立 `Conversation`、独立 token 计数;但共享 `Provider`(除非 WithProvider 覆盖)、`Registry`、`PermissionEngine`、`HookEngine`

### 权限决策- **F12**:子 Agent 工具调用权限决策三层链(在 `runGuarded` 内分支):
  1. 父对话已批准账本——父 Engine 已经 `PersistLocalAllow` 过的精确规则匹配 → Allow
  2. 子角色 `permissionMode` 兜底——`dontAsk` 模式直接放行所有 Allow/Ask 类规则未命中的;`acceptEdits` 放行写;`bypassPermissions` 全 Allow(黑名单/沙箱仍拦);其他模式仍走原 `modeFallback`
  3. 三层之外仍是 Ask——升级到主 TUI:子 Agent 暂停,主 TUI 弹审批框(标注 `[来自 SubAgent X]`),用户响应后子 Agent 继续;Outcome 沿用现有三选一(DenyOnce/AllowOnce/AllowForever)
- **F13**:升级到主 TUI 的通信机制——子 Agent 把 `ApprovalRequest` emit 到自己的事件流,事件流被 TaskManager / SkillFork host 转发到主 TUI 的 Approval 弹窗;主 TUI 响应后 Outcome 通过 `Respond` channel 回传

### 后台任务管理- **F14**:新建 `task.Manager`,持有 `map[string]*BackgroundTask`,提供 `Launch(ctx, agent, taskText) (taskID, error)`、`Get(id) *Task`、`List() []*Task`、`Stop(id)`、`AdoptRunning(...)`、`SubscribeDone() <-chan string`
- **F15**:`BackgroundTask` 字段:
  - `ID`(string,manager 生成)
  - `Name`(string,可选,F1 的 `name` 字段)
  - `SubAgent`(*Agent)
  - `Conv`(*Conversation,子对话)
  - `Task`(string,初始任务)
  - `Status`(`running` / `completed` / `failed` / `cancelled`)
  - `Result`(string,跑完后填)
  - `Err`(error)
  - `StartTime` / `EndTime`
  - `Cancel`(context.CancelFunc)
  - `Usage`(*TokenUsage,token 计数)
  - `ToolCount`(int,工具调用次数计数器)
  - `LastActivity`(string,最近一次工具名)
- **F16**:`Launch` 内部 goroutine:`SubAgent.RunToCompletion(ctx, conv, task)` → status 终态 → 推 `taskID` 到 `done` channel → TUI 消费后注入 `<task-notification>`
- **F17**:三种进入后台的方式:
  1. **显式**:Agent 工具 `run_in_background:true` → 直接调 `Launch`,工具 result 立刻返回 `{task_id, status:"async_launched"}`
  2. **超时自动**:Agent 工具默认前台 inline 跑,但前台 Run 启动后开计时器(120 秒,常量 `autoBackgroundMs`),超时则:
     - 取消前台 channel 消费
     - 调 `Manager.AdoptRunning(agent, conv, ctx, cancel, ev_channel, partial)` 接管事件流继续后台跑
     - Agent 工具 result 改返回 `{task_id, status:"timed_out_to_background"}`
  3. **ESC 手动切**:用户在前台子 Agent 跑动期间按 ESC → TUI 调 `Manager.AdoptRunning(...)`,与超时路径走同一逻辑
- **F18**:Fork 路径 `run_in_background` 字段被强制视为 true(代码内 override)
- **F19**:后台任务完成时,Manager 把 `taskID` push 到 `Done` channel;TUI 在主事件循环消费,把如下文本作为 system reminder 拼到主对话下一次 reminder 区(不打断当前对话):
  ```
  <task-notification>
  Task X (name="Y"): completed
  Result: <最终文本>
  </task-notification>
  ```

### 后台任务工具- **F20**:新增 4 个内置工具:
  - `TaskList`:无参,返回当前 manager 中所有非 Terminated 任务的简要列表(id、name、status、tool_count、last_activity)
  - `TaskGet`:`{task_id}`,返回指定任务的完整状态(含 Result / Err)
  - `TaskStop`:`{task_id}`,调 manager.Stop 触发取消;返回 `{status:"cancellation_requested"}`
  - `SendMessage`:`{name, message}`,按 name 找到仍存活的后台 Agent(status=completed,Conv 仍在内存),把 message 作为新 user 消息追加到 Conv 并重新 `Launch` 一轮跑动;找不到 / 已 cancelled 返回错误
- **F21**:本期不实现 `TaskCreate`(主要给 Hook 用,Hook 暂未需要 SubAgent action);保留 manager API,Hook subagent stub 也可暂未对接

### Fork 路径- **F22**:`buildForkedMessages(parentConv)` 做三件事:
  1. 深拷贝 parentConv 的全部消息
  2. 把末尾 assistant 中未完成的 `tool_use`(无对应 ToolResult)包装为 placeholder ToolResult,使消息格式合法
  3. 在末尾追加 user 消息,内容 = Fork Boilerplate + 任务文本
- **F23**:Fork Boilerplate 是一段 `<fork_boilerplate>` 包裹的指令,核心约束:
  - 不能再 Fork(再 Fork 会被 QuerySource 拦截 / Boilerplate 标记扫描兜底)
  - 不要对话 / 提问 / 请求确认
  - 直接使用工具
  - 严格限制在分配的任务范围内
  - 最终报告以 `Scope:` 开头,500 字以内
- **F24**:Fork 子 Agent 嵌套阻断三道闸:
  1. **工具列表层**:Fork 子 Agent 的工具列表保留 Agent 工具(继承自父),但调用 Agent 工具时
  2. **QuerySource 检测**:Agent 工具入口检测 caller 来源(检查父链),若 caller 是 Fork 路径产生,直接 IsError=true 返回「Fork 子 Agent 不能再启动 Agent」
  3. **Boilerplate 标记扫描**:对话历史里如果含 `<fork_boilerplate>` 标记(QuerySource 失效兜底),也认定是 Fork 嵌套
- **F25**:定义式子 Agent 不走 Boilerplate(从空白启动);嵌套阻断靠 `ALL_AGENT_DISALLOWED_TOOLS` 全局禁止 Agent 工具

### 工具过滤多层防线- **F26**:全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS = [Agent]`(本期范围最小,后续可加 AskUserQuestion / TaskStop);所有子 Agent 启动时从工具列表中剔除这些
- **F27**:自定义 Agent 额外限制 `CUSTOM_AGENT_DISALLOWED_TOOLS`:本期为空,接口预留(用于将来用户自定义 Agent 一律不可访问某些核心工具)
- **F28**:后台 Agent 白名单 `ASYNC_AGENT_ALLOWED_TOOLS`,只列基础工具:
  `read_file, write_file, edit_file, glob, grep, bash, load_skill, install_skill`
  以及所有 MCP / Skill 工具。Fork/run_in_background 任意一种成立的子 Agent 工具集再叠加此白名单交集。
- **F29**:Agent 定义层 `tools`(白名单)与 `disallowedTools`(黑名单)组合应用——白名单先确定范围,黑名单再排除
- **F30**:工具过滤合并执行顺序(在 Agent 工具的 `Execute` 内,子 Agent 构造时):
  1. 起点 = registry 的全部工具
  2. 去掉 `ALL_AGENT_DISALLOWED_TOOLS`
  3. 如果是后台 → 取交集 `ASYNC_AGENT_ALLOWED_TOOLS`
  4. 应用定义的 `disallowedTools` 黑名单
  5. 应用定义的 `tools` 白名单(空白名单 = 不再收窄)
  6. 注入到子 Agent 的 `WithAllowedTools(allowed)`
- **F31**:工具列表对模型稳定——以上过滤只发生在子 Agent 构造时,主 Agent 看到的工具列表不变

### 内置角色与 Skill fork 改造- **F32**:内置 3 个角色文件,embed 到二进制:
  - `general-purpose.md`:无 disallowedTools,用 `inherit` 模型,maxTurns=30,permissionMode=default
  - `explore.md`:disallowedTools=[write_file, edit_file],model=haiku,maxTurns=30,permissionMode=default
  - `plan.md`:disallowedTools=[Agent, write_file, edit_file],maxTurns=15,permissionMode=plan(plan 是已有的权限模式)
- **F33**:Skill fork 改造——`tui/skill_fork.go` 的 `runSubAgent` 改为:
  1. 构造一个临时 `subagent.Definition`(name="skill-fork-<skillname>",disallowedTools=skill.AllowedTools 反推 / 等同 skill 自身的 AllowedTools),将其当 Fork 路径走
  2. 复用 `agent.RunToCompletion` 与 SubAgent 的工具过滤、消息装填路径
  3. 返回 finalText 行为不变(host.AppendAssistantMessage 仍由 Executor 调)

## 非功能需求- **N1**:工具列表稳定——主 Agent 看到的工具集不因 `.gcode/agents/` 增减或 Agent 工具被调用而变化(防止 prompt cache 抖动)
- **N2**:Fork 路径首次请求命中 prompt cache——`buildForkedMessages` 拼接的消息列表与父对话末尾完全一致,系统提示一致
- **N3**:子 Agent 崩溃不影响主程序——`Manager.Launch` 的 goroutine 包 recover,任何 panic 转 `status=failed` + 错误信息回灌
- **N4**:启动期 fail-fast——内置定义 embed 解析失败立刻 panic(代码 bug),用户/项目级定义文件解析失败仅 stderr 警告并跳过
- **N5**:与现有 ch11 Skill 系统、ch12 Hook 系统、ch08 权限系统、ch04 主 Agent loop 协同,不破坏既有测试
- **N6**:配置 `enableSubAgentBackground`(bool,默认 true)关闭后,Agent 工具的 `run_in_background:true` / 超时切后台 / ESC 切后台全部失效,所有 SubAgent 强制前台同步;Fork 路径在此模式下报错「后台禁用,无法 Fork」
- **N7**:`<task-notification>` 注入主对话不消耗主 Agent 的工具调用配额,不出现在用户视窗(只对模型可见)

## 不做的事

- Worktree 文件隔离(独立章节)
- 多 Agent 团队编排(CrewAI / AutoGen 平等协作风格)
- 后台任务跨会话持久化——主程序退出后任务全部丢失
- 真正的插件系统(`SourcePlugin` 占位)
- 子 Agent 输出 schema 强制结构化(返回纯文本即可)
- Verification Agent 内置开关(`enableVerificationAgent` 不实现)
- `TaskCreate` 工具(本期仅 List/Get/Stop/SendMessage)
- 跨 SubAgent token 用量汇总到 /status(只在 Manager 内部记录)

## 验收标准- **AC1**:Agent 工具注册成功,主 Agent 的工具列表里 schema 一致;子 Agent 看不到 Agent 工具
- **AC2**:`Agent` 工具调用 `{prompt:"...",subagent_type:"Explore"}` 时,主 Agent 看到的 tool_result 是 Explore 子 Agent 的最后一条 assistant 文本
- **AC3**:`Agent` 工具调用 `{prompt:"...",subagent_type:"non-existent"}` 时,主 Agent 看到的 tool_result 是结构化错误「未知 subagent_type」
- **AC4**:`Agent` 工具调用不传 subagent_type 时,子 Agent 收到的首条 user 消息以 `<fork_boilerplate>` 起头,且消息列表前缀与父对话一致(可由测试断言)
- **AC5**:Fork 子 Agent 的工具列表里仍有 Agent 工具(F22 设计),但调用 Agent 工具会被 QuerySource 拦截,tool_result 含「Fork 子 Agent 不能再启动 Agent」
- **AC6**:定义式子 Agent 的工具列表里没有 Agent 工具(被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除)
- **AC7**:子 Agent 角色 frontmatter 写 `permissionMode: dontAsk`,Bash 等需要 Ask 的工具直接放行,无审批弹窗
- **AC8**:子 Agent 角色 frontmatter 不写 dontAsk,Bash 工具触发审批,弹窗带 `[来自 SubAgent X]` 标识
- **AC9**:`run_in_background:true` 时 tool_result 立即返回 `{task_id, status:"async_launched"}`,主 Agent 不阻塞
- **AC10**:前台子 Agent 跑超过 120 秒,自动切后台,主 Agent 看到 tool_result 含 `status:"timed_out_to_background"`
- **AC11**:前台子 Agent 跑动期间用户按 ESC,切到后台,TUI 继续接收主 Agent 输入
- **AC12**:后台子 Agent 跑完,主 Agent 下次 Run 的 reminder 区出现 `<task-notification>` 块,含 Result
- **AC13**:`TaskList` 工具返回当前后台任务列表,字段含 id/name/status/tool_count
- **AC14**:`TaskGet({task_id})` 返回 Result;`TaskStop({task_id})` 触发取消,任务 status 变 cancelled
- **AC15**:`SendMessage({name,message})` 让一个仍存活的后台 Agent 接到新任务并重新跑动,跑完结果作为新 `<task-notification>` 注入主对话
- **AC16**:项目级 `.gcode/agents/explore.md` 覆盖内置 `explore`,`Resolve("explore")` 返回项目级版本
- **AC17**:Skill fork 模式调用走 SubAgent 底座——`tui/skill_fork.go` 的 `runSubAgent` 内部只是装饰参数后调 `subagent.LaunchFork(...)`(或同等公共函数)
- **AC18**:N6 配置开关 `enableSubAgentBackground:false` 时,Fork 路径调用 Agent 工具返回结构化错误
- **AC19**:`<fork_boilerplate>` 出现在对话历史里 + Agent 工具被调用 → 拦截(QuerySource 失效兜底)
- **AC20**:子 Agent panic → status=failed,主 Agent 收到 `<task-notification>` 含错误描述,主程序不崩
- **AC21**:全新项目级自定义 Agent(`.gcode/agents/<name>.md`)被 Catalog 加载;`subagent_type=<name>` 调用时,frontmatter 的 disallowedTools / permissionMode / maxTurns / SystemPrompt 全部生效——子 Agent 看不到黑名单工具、按指定 mode 决策、不超 turns、按 SystemPrompt 行事
- **AC22**:Agent 定义 frontmatter 的非法字段(unknown model / unknown permissionMode)在加载时 stderr 警告并 fallback 到默认值(model→inherit, mode→default),gcode 不阻断启动,该 Agent 仍可被 Resolve 与调用
````

````markdown
# SubAgent 机制 Plan## 架构概览

本章实现拆为四个层次：

1. **subagent 包**（新增,核心数据层）——定义 Agent 角色的数据结构、Markdown+YAML 解析、Catalog 多来源加载、内置角色 embed
2. **task 包**（新增,后台运行层）——`task.Manager` 管理后台任务生命周期,4 个内置工具(TaskList/TaskGet/TaskStop/SendMessage)
3. **agent 包扩展**——新增 `RunToCompletion` 方法、5 个新 Option、Fork 路径辅助函数 `buildForkedMessages`、子 Agent 权限升级 callback
4. **工具与 TUI 集成层**——Agent 工具实现、工具过滤多层防线常量、TUI 接入 task notification、ESC 切后台、Skill fork 改造为复用 SubAgent 底座

模块构成：

- `subagent.Definition` / `subagent.Catalog` / `subagent.SourceXxx` — 数据结构与三层加载
- `subagent/builtin/*.md` — 内置 3 个角色文件,go:embed
- `task.Manager` / `task.BackgroundTask` — 后台任务管理与生命周期
- `task.*Tool` — 4 个内置工具,注册到 `tool.Registry`
- `agent.RunToCompletion` / `agent.WithSystemPrompt` / `agent.WithProvider` / `agent.WithMaxTurns` / `agent.WithPermissionMode` / `agent.WithApprovalUpgrader` — Agent 包扩展
- `agent/fork.go` — `BuildForkedMessages`、Fork Boilerplate 常量
- `agent/agent_tool.go` — Agent 工具实现
- `tool/filter.go` — `ALL_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 常量与过滤函数
- `tui` 改动 — TaskManager wiring、ESC 切后台、`<task-notification>` 注入、子 Agent 审批弹窗
- `tui/skill_fork.go` 改造 — 复用 `subagent.LaunchFork`

## 核心数据结构### subagent.Definition

```go
// Definition 是一个 Agent 角色的完整定义,从 Markdown+YAML frontmatter 解析。
type Definition struct {
    Name           string         // frontmatter.name (-> agentType)
    Description    string         // frontmatter.description (-> whenToUse)
    Tools          []string       // frontmatter.tools 白名单;空表示不收窄
    DisallowedTools []string      // frontmatter.disallowedTools 黑名单
    Model          string         // "haiku" / "sonnet" / "opus" / "inherit";缺省 "inherit"
    MaxTurns       int            // 0 表示沿用全局默认 (25)
    PermissionMode permission.Mode // permission.ParseMode 解析;"dontAsk" 单独处理(见 DontAsk 字段)
    DontAsk        bool           // 是否启用"绕过 Ask"的子 Agent 兜底模式
    Background     bool           // 强制后台
    SystemPrompt   string         // Markdown body(去 frontmatter 后的全文)
    FilePath       string         // 定义文件绝对路径(用于调试)
    Source         Source         // SourceProject / SourceUser / SourceBuiltin / SourcePlugin
}

type Source int

const (
    SourceBuiltin Source = iota
    SourceUser
    SourceProject
    SourcePlugin // 占位
)

func (s Source) String() string // "builtin" / "user" / "project" / "plugin"
```

### subagent.Catalog

```go
type Catalog struct {
    mu       sync.Mutex
    defs     map[string]*Definition // name -> 最高优先级定义
    bySource map[Source][]*Definition // 各层的副本(用于 /agents 命令展示与 debug)
}

func LoadCatalog(root string) *Catalog
// 顺序加载:builtin -> user -> project,优先级高的覆盖低的;
// 解析错误走 stderr 警告并跳过;返回非 nil Catalog 即使无任何定义。

func (c *Catalog) Resolve(name string) (*Definition, bool)
func (c *Catalog) List() []*Definition // 按 name 排序
func (c *Catalog) ListBySource(s Source) []*Definition

// LaunchFork 返回一个"Fork 路径"用的临时 Definition——name="__fork__",SystemPrompt="" (子 Agent 走继承的系统提示),
// 但 DisallowedTools 不应包含 Agent 工具(Fork 子 Agent 工具集保留 Agent,靠 QuerySource 阻断)。
func (c *Catalog) ForkDefinition() *Definition
```

### task.Manager 与 BackgroundTask

```go
// BackgroundTask 是一个后台子 Agent 的完整状态快照。
type BackgroundTask struct {
    ID           string                  // manager 生成,如 "task_<8 字节十六进制>"
    Name         string                  // F1 中 Agent 工具 name 参数,可空
    SubAgent     *agent.Agent
    Conv         *conversation.Conversation
    Task         string                  // 初始任务文本(SendMessage 不更新此字段)
    Status       Status                  // running/completed/failed/cancelled
    Result       string                  // 跑完的最终文本
    Err          error
    StartTime    time.Time
    EndTime      time.Time
    Cancel       context.CancelFunc
    Usage        Usage                   // 累计 token
    ToolCount    int                     // 工具调用累计
    LastActivity string                  // 最近一次工具名
}

type Status int

const (
    StatusRunning Status = iota
    StatusCompleted
    StatusFailed
    StatusCancelled
)

type Usage struct {
    Input, Output, CacheWrite, CacheRead int64
}

// Manager 管理后台任务。线程安全。
type Manager struct {
    mu     sync.Mutex
    tasks  map[string]*BackgroundTask
    byName map[string]string         // name -> id,弱引用,后启动的覆盖
    done   chan string               // 完成任务的 id push 进去,TUI 消费;缓冲 32
}

func NewManager() *Manager

// Launch 起一个后台 goroutine 跑 agent.RunToCompletion;Conv 应该是已经装填了消息的子对话。
// 返回 ID;goroutine 内部跑完后写 status/result + push 到 done。
func (m *Manager) Launch(parentCtx context.Context, ag *agent.Agent, conv *conversation.Conversation, name, task string) (id string)

// AdoptRunning 把一个正在前台跑的 agent 移交到后台。
// 调用方应已经把"用户的 ESC / 120 秒超时"对应的 cancel 准备好,并把已 partial 收集的事件吐到 partial 内。
// Manager 接管 ev 事件流继续消费,直到 Done 或 Err。
func (m *Manager) AdoptRunning(parentCtx context.Context, ag *agent.Agent, conv *conversation.Conversation, name string, ev <-chan agent.Event, cancel context.CancelFunc, partial *PartialState) (id string)

// PartialState 是前台→后台移交时已收集的中间状态。
type PartialState struct {
    LastAssistantText string
    ToolCount         int
    LastActivity      string
    Usage             Usage
}

func (m *Manager) Get(id string) (*BackgroundTask, bool)
func (m *Manager) List() []*BackgroundTask // 按 StartTime 升序
func (m *Manager) Stop(id string) bool
// SubscribeDone 返回 done channel;TUI 在主事件循环里 select 消费,
// 收到 id 后查 Get 拿状态,把 <task-notification> 拼到 runtime.PendingReminders。
func (m *Manager) SubscribeDone() <-chan string

// SendMessage 给一个仍存活的后台 Agent 续派任务。
// 找不到 name -> ErrTaskNotFound;status != Completed -> ErrTaskBusy。
// 成功时把 message 加到 Conv,重新 Launch 一个新轮(返回新的 id 还是同 id?——选择**同 id**,
// 状态从 Completed 重置回 Running)。
func (m *Manager) SendMessage(parentCtx context.Context, name, message string) (id string, err error)
```

### agent 包扩展

```go
// 新增方法 ---

// RunToCompletion 执行子 Agent 的"跑到底"循环。
// 复用主 Run 的几乎所有逻辑(streamOnce / executeBatched / 权限判定),区别:
//   - 不通过 channel 返回事件(内部消费),最终返回 finalText
//   - maxTurns 由 a.maxTurns 决定(若 0 则用 maxIterations)
//   - 不触发 memory update / 不触发 compact reminder 等主对话专属逻辑(子 Agent 上下文短,
//     不需要;但内部依然走 manageContextAuto 防止超长)
//   - 接受一个可选的 events 通道,把内部事件(text/tool/approval)转发出去——TaskManager 借此聚合 ToolCount/LastActivity,
//     TUI 借此渲染前台子 Agent 的进度
func (a *Agent) RunToCompletion(ctx context.Context, conv *conversation.Conversation, task string, events chan<- Event) (finalText string, err error)

// 新增 Option ---

func WithSystemPrompt(text string) Option // 子 Agent 角色 prompt
func WithProvider(p llm.Provider) Option
func WithMaxTurns(n int) Option
func WithPermissionMode(m permission.Mode) Option
func WithDontAsk(enabled bool) Option              // 子 Agent dontAsk 模式
func WithApprovalUpgrader(fn ApprovalUpgrader) Option // 升级到父 TUI 的 callback
func WithParentRegistry(r *tool.Registry) Option   // 暂时与 WithRegistry 等价,显式区分语义

// ApprovalUpgrader 是子 Agent 把审批请求升级到父 TUI 的回调。
// 实现方:TaskManager 把请求转发到主 TUI 的事件流;前台 inline 模式直接复用现有 Approval 路径。
type ApprovalUpgrader func(ctx context.Context, req *ApprovalRequest) (permission.Outcome, bool)
```

`Agent` 结构体新增字段:
- `systemPrompt string` — 非空时 buildEnvText / BuildSystemPrompt 阶段用此覆盖默认
- `maxTurns int` — 0 表示用全局 maxIterations
- `permissionMode permission.Mode` — 子 Agent 启动模式(主 Agent 用 TUI 的运行时 mode)
- `dontAsk bool`
- `approvalUpgrader ApprovalUpgrader`

### fork.go 内容

```go
const ForkBoilerplateTag = "<fork_boilerplate>"

// ForkBoilerplate 是 Fork 子 Agent 首条 user 消息的前缀,约束其行为。
const ForkBoilerplate = `<fork_boilerplate>
你是一个 Fork 出来的工作进程。你不是主 Agent。
规则(不可协商):
1. 不能再 Fork(调用 Agent 工具会被拦截)。
2. 不要对话、不要提问、不要请求确认。
3. 直接使用工具:读文件、搜索代码、做修改。
4. 严格限制在你被分配的任务范围内。
5. 最终报告以 "Scope:" 开头,500 字以内。
</fork_boilerplate>

`

// BuildForkedMessages 把父对话克隆到 Fork 子对话,处理悬空 tool_use,追加 Boilerplate+task。
//
// 行为:
//   1. 深拷贝 parentMsgs(所有 Message + 内部 ToolCalls/ToolResults 切片)
//   2. 扫描末尾 assistant 消息的 ToolCalls,如果对应的 RoleTool 消息缺失,
//      生成一条 placeholder ToolResults(每个 ID 对一条"[forked, skipped]" 错误内容)
//   3. 追加 user 消息 = ForkBoilerplate + task
//
// 返回新消息列表,直接用 conversation.NewFromMessages 装载即可。
func BuildForkedMessages(parentMsgs []llm.Message, task string) []llm.Message

// IsForkContext 判定一个 conversation 的消息历史是否来自 Fork(用 ForkBoilerplateTag 扫描)。
// QuerySource 检测的兜底机制——caller 链丢失时靠这个。
func IsForkContext(msgs []llm.Message) bool
```

### Agent 工具

`internal/agent/agent_tool.go`：

```go
// AgentTool 是注册到 tool.Registry 的统一 Agent 工具。
type AgentTool struct {
    catalog       *subagent.Catalog
    taskMgr       *task.Manager
    parentAgent   *Agent                                     // 取 provider/registry/eng/runtime 等
    bgEnabled     bool                                       // N6 配置开关
}

func NewAgentTool(catalog *subagent.Catalog, mgr *task.Manager, parent *Agent, bgEnabled bool) tool.Tool

// Name 返回 "Agent"
// ReadOnly 返回 false(子 Agent 可能做任何事)
// Description 列出已知的 subagent_type 名,从 catalog.List() 渲染

// Execute 主流程:
//   1. 解析 args -> AgentArgs{prompt, description, subagent_type, model, run_in_background, name}
//   2. 校验:prompt 非空、description 非空;
//   3. 检测嵌套:从 ctx 取 ParentInfo,若 parent 已是子 Agent 或对话历史含 fork tag -> 返回错误
//   4. Resolve 定义:subagent_type 非空走 catalog.Resolve,空走 catalog.ForkDefinition
//   5. 决定 background:def.Background || args.RunInBackground || (是 fork)
//   6. 应用工具过滤多层防线 ApplyAgentToolFilter,得到 allowed []string
//   7. 选 provider:args.Model 非空 -> 切;否则 def.Model 非 inherit -> 切;否则用 parent
//   8. 构造子 Agent + 子 Conv(空白或 Fork 路径装填消息)
//   9. 前台路径:开 ctx,WithTimeout 120s,跑 RunToCompletion;
//      - 完成 → 返回 finalText
//      - 超时/ESC → AdoptRunning,返回 {task_id, status:"timed_out_to_background"}
//   10. 后台路径:Launch,返回 {task_id, status:"async_launched"}
```

### 工具过滤多层防线

`internal/tool/filter.go`:

```go
// ALL_AGENT_DISALLOWED_TOOLS 是任何子 Agent 永远不能用的工具名列表。
// 本期最小列表:Agent。后续可扩展 AskUserQuestion / TaskStop / 系统级敏感工具。
var ALL_AGENT_DISALLOWED_TOOLS = []string{"Agent"}

// CUSTOM_AGENT_DISALLOWED_TOOLS 是自定义(user / project / plugin 来源)Agent 比内置 Agent 多禁用的工具。
// 本期为空。
var CUSTOM_AGENT_DISALLOWED_TOOLS = []string{}

// ASYNC_AGENT_ALLOWED_TOOLS 是后台 Agent 工具白名单。
// 不含 Agent / TaskStop / SendMessage / TaskList / TaskGet 等任何元工具。
var ASYNC_AGENT_ALLOWED_TOOLS = []string{
    "read_file", "write_file", "edit_file",
    "glob", "grep",
    "bash",
    "load_skill", "install_skill",
}
// MCP 工具与 Skill 工具按工具命名约定动态识别(以 "mcp__" 起头 / 来自 RegisterSkillTool),
// 通过 IsAllowedInBackground 函数走另一条分支判定。

// FilterParams 是过滤一个 Agent 的工具列表的参数。
type FilterParams struct {
    All        []string // registry 的全部工具名(按注册顺序)
    Source     subagent.Source
    Background bool
    Allowed    []string // Agent 定义 frontmatter.tools 白名单
    Disallowed []string // Agent 定义 frontmatter.disallowedTools 黑名单
}

// ApplyAgentToolFilter 按 spec F30 顺序过滤。
// 返回最终 allowed 列表(传给 agent.WithAllowedTools)。
func ApplyAgentToolFilter(p FilterParams) []string
```

### TUI 集成层

`internal/tui/tui.go` 改动：
- `TUIParams` 加 `TaskManager *task.Manager`(由 main 注入)
- `Model` 持有 `taskMgr *task.Manager`
- `Init()` 末尾启动一个 go-routine 消费 `taskMgr.SubscribeDone()`,把 `<task-notification>` 拼成 reminder 推到 `m.runtime.AppendReminders`
- 主对话 Agent 通过 `agent.WithApprovalUpgrader(m.taskMgr.UpgradeApproval)` 让子 Agent 审批升级回主 TUI

`internal/tui/stream.go` 改动：
- `updateStreaming` 监听 ESC 键(`tea.KeyPressMsg` "esc"):若 m.state==stateStreaming 且当前有运行中的 SubAgent → 调 `m.taskMgr.AdoptRunning`,切回 idle 态
- 监听 SubAgent ApprovalRequest 转发——TaskManager 通过 events channel 转回主 TUI 走现有 Approval 路径

`internal/tui/skill_fork.go` 改造：
- 删除现有 `runSubAgent` 内的零散逻辑
- 改为调 `subagent.LaunchFork(ctx, host, opts, conv)`,host 持有 m.taskMgr / m.runtime / m.engine 等

## 模块设计### 模块 A:subagent 包**职责:**
- 数据结构 Definition
- Markdown+YAML 解析(复用 skills/parser.go 的 parseFrontmatterAndBody——抽到 internal/util/markdown 让两方共用 OR skills 与 subagent 都各自有一份)
- 三层 + 内置 embed 加载

**对外接口:**
- `LoadCatalog(root string) *Catalog`
- `Catalog.Resolve(name) (*Definition, bool)` / `List()` / `ForkDefinition()`

**依赖:**
- `internal/permission`(解析 PermissionMode 字段)
- `gopkg.in/yaml.v3`
- 标准库 path/filepath、embed

**关键设计:**
- Markdown 解析复用 skills/parser.go 的 `parseFrontmatterAndBody`——抽到 subagent/parser.go 独立实现一份(避免互相依赖),内容几乎一致
- 内置文件 `subagent/builtin/general-purpose.md` / `explore.md` / `plan.md` 用 `//go:embed builtin/*.md` 加载
- 加载错误统一 stderr `fmt.Fprintf(os.Stderr, "subagent %s: ... skipped\n", ...)`

### 模块 B:task 包**职责:**
- 后台任务生命周期管理
- 4 个内置工具(TaskList/TaskGet/TaskStop/SendMessage)

**对外接口:**
- `NewManager() *Manager`
- `Launch / AdoptRunning / Get / List / Stop / SendMessage / SubscribeDone`
- `NewTaskListTool(m *Manager) tool.Tool` 等四个工厂

**依赖:**
- `internal/agent`(*agent.Agent)
- `internal/conversation`
- `internal/tool`
- `internal/llm`

**关键设计:**
- `done` channel 缓冲 32 够大,正常场景不可能填满;真满了 push 走 select default 丢弃 +
  stderr 警告(主 TUI 漏一条通知不致命)
- `Launch` goroutine 包 `defer recover()`,panic 转 status=failed
- `Stop` 调 `task.Cancel`,Cancel 是 Launch 时 derive 的 context.WithCancel
- `SendMessage`:仅当 status==Completed 时允许;否则 ErrTaskBusy。重新 Launch 时用 *同 id*,status 从 Completed 重置回 Running

### 模块 C:agent 包扩展**职责:**
- 新增 `RunToCompletion` 方法
- 新增 5 个 Option
- Fork 路径辅助

**对外新增接口:**
- `Agent.RunToCompletion(ctx, conv, task, events) (string, error)`
- `WithSystemPrompt / WithProvider / WithMaxTurns / WithPermissionMode / WithDontAsk / WithApprovalUpgrader`
- `BuildForkedMessages`
- `IsForkContext`

**关键设计:**
- `RunToCompletion` 与 `Run` 共用 `streamOnce` / `executeBatched` / `manageContextAuto` /
  `recordReadFileIfApplicable`,通过抽公共 helper 实现共享(把 Run 的循环体抽到
  `runIter(ctx, conv, mode, iter, ...)`,Run 与 RunToCompletion 都调它)
- 子 Agent 的 `permissionMode` + `dontAsk` 决策点在 `executeBatched` 的 `runGuarded` 内多一层短路:
  ```go
  if a.dontAsk {
      // 角色定义 dontAsk:走 sandbox/黑名单/规则后,默认 Allow 而非 Ask
      if d == permission.Ask { d = permission.Allow }
  }
  ```
- 升级到父 TUI 的 callback 在 `requestApproval` 里调:
  ```go
  if a.approvalUpgrader != nil {
      outcome, ok := a.approvalUpgrader(ctx, &req)
      if ok { return outcome, true }
  }
  // 否则走默认 emit Approval event 路径(主 Agent inline 子 Agent 路径)
  ```

**Fork Boilerplate 注入策略:**
- `BuildForkedMessages` 把 Boilerplate 写在 user 消息开头(与 ch13 README 一致)
- `IsForkContext` 用 strings.Contains 扫描 *所有* 历史 user 消息内容寻找 `<fork_boilerplate>`(QuerySource 兜底)

### 模块 D:Agent 工具与 TUI 集成**职责:**
- 把 Agent 工具注册到 registry
- TUI 接入 task notification
- 改造 Skill fork

**对外接口:**
- `agent.NewAgentTool(catalog, taskMgr, parentAgent, bgEnabled) tool.Tool`
- `subagent.LaunchFork(ctx, host, opts) (...)` 公共 Fork 启动函数(Skill fork 与 Agent 工具都调)

**关键设计:**
- `AgentTool.Execute` 在前台 inline 路径返回结果时要小心:
  - 前台跑完返回 finalText 作为 tool_result content
  - 中途超时切后台 → 返回 JSON `{"task_id":"...","status":"timed_out_to_background"}`
- 嵌套阻断:`AgentTool.Execute` 入口检查 ctx 是否携带 `parentAgentCtxKey`(子 Agent 启动时塞入);若有 → 返回结构化错误
  - 不依赖 ctx 单值:也扫 conv 历史是否含 Fork tag(IsForkContext)
- TUI 的 task notification 注入:
  - `Init()` 开 `go m.consumeTaskDone()`
  - `consumeTaskDone` 接 `done` channel,Get 拿状态,渲染成 `<task-notification>` 块,调 `m.runtime.AppendReminders` 推入
  - 主对话下一次 Run 自动拿到(已有机制)

## 模块交互### 启动期 wiring

```
main.go
  ├── NewDefaultRegistry()  → registry
  ├── NewEngine(root)       → engine
  ├── NewSessionRuntime     → runtime
  ├── skills.LoadCatalog    → skillCatalog
  ├── hook.Load             → hookEngine
  ├── subagent.LoadCatalog  → subagentCatalog       ← 新增
  ├── task.NewManager()     → taskMgr               ← 新增
  ├── registry.Register(task.NewTaskListTool(taskMgr))    ← 新增
  ├── registry.Register(task.NewTaskGetTool(taskMgr))     ← 新增
  ├── registry.Register(task.NewTaskStopTool(taskMgr))    ← 新增
  ├── registry.Register(task.NewSendMessageTool(taskMgr)) ← 新增
  ├── tui.New(..., TUIParams{TaskMgr: taskMgr, SubAgentCatalog: subagentCatalog, ...})
  │     │
  │     └── 在 tui.New 内:Agent 工具的注册被推迟到主 Agent 构造后(因为要把 parentAgent 注入),
  │         或者 Agent 工具 lazy 拿:把 catalog/taskMgr 写死,parentAgent 通过函数 / 持有 *Model 拿
```

**简化方案:** Agent 工具在 main.go 注册,parentAgent 字段在 tui.New 后回填:
```go
agentTool := agent.NewAgentTool(subagentCatalog, taskMgr, nil, cfg.EnableSubAgentBackground)
registry.Register(agentTool)
// 再 tui.New(...)
// 再 agentTool.SetParent(m.agent)
```

### 运行时:主 Agent 调 Agent 工具(前台,定义式)

```
LLM 流式产出 tool_use:{name:"Agent",input:{prompt:"...",subagent_type:"Explore"}}
    ↓
agent.executeBatched → 路由到 AgentTool.Execute(ctx, args)
    ↓
AgentTool.Execute:
    1. 解析参数 -> AgentArgs
    2. 防嵌套:检测 ctx / Conv 是否来自 Fork → 否
    3. Resolve("Explore") → def
    4. background = def.Background || args.RunInBackground → false
    5. ApplyAgentToolFilter -> allowed
    6. provider = (def.Model=="haiku") ? llm.New(haiku) : parent.Provider
    7. subRuntime := NewSessionRuntime(200000)
    8. subAgent := agent.New(provider, registry, version, engine,
           WithRuntime(subRuntime),
           WithAllowedTools(allowed),
           WithSystemPrompt(def.SystemPrompt),  ← 新
           WithMaxTurns(def.MaxTurns),
           WithPermissionMode(def.PermissionMode),
           WithDontAsk(def.DontAsk),
           WithApprovalUpgrader(parent.taskMgr.UpgradeApproval),
           WithHookEngine(parent.hookEngine))
    9. subConv := conversation.New()
    10. timeoutCtx, cancel := context.WithTimeout(ctx, 120s)
        events := make(chan agent.Event, 32)
        go func() {  // 前台路径:把 events 转发到主 TUI(可选,本期暂不渲染前台子进度,只在状态行显示一条 "● subAgent 跑中")
            for ev := range events { ... }
        }()
        finalText, err := subAgent.RunToCompletion(timeoutCtx, subConv, args.Prompt, events)
    11. timeoutCtx.Err() == DeadlineExceeded?
         - 是 → AdoptRunning(ctx, subAgent, subConv, args.Name, events, cancel, partial)
              → 返回 JSON {"task_id": "task_xxx", "status": "timed_out_to_background"}
         - 否 → 返回 finalText 作为 tool_result content
```

### 运行时:主 Agent 调 Agent 工具(后台,显式)

```
AgentTool.Execute:
    ...
    10. taskID := taskMgr.Launch(ctx, subAgent, subConv, args.Name, args.Prompt)
    11. 返回 JSON {"task_id": "task_xxx", "status": "async_launched"}
```

### 后台任务完成通知

```
taskMgr.Launch goroutine:
    finalText, err := subAgent.RunToCompletion(ctx, conv, task, nil)
    task.Result = finalText
    task.Err = err
    task.Status = StatusCompleted (or Failed/Cancelled)
    select {
    case m.done <- taskID:
    default: // 缓冲满,丢弃 + stderr 警告
    }
    ↓
tui.consumeTaskDone (goroutine):
    for taskID := range taskMgr.SubscribeDone() {
        t := taskMgr.Get(taskID)
        notification := buildTaskNotification(t)  // <task-notification>...</task-notification>
        m.runtime.AppendReminders([]string{notification})
        // 不主动唤醒主对话:等主 Agent 下次 Run 自然 take reminder
    }
    ↓
下一次 m.beginTurn → m.agent.Run → buildReminder takes pendingReminders → 注入 reminder 区
```

### Fork 路径

```
AgentTool.Execute (subagent_type 空):
    1. def = catalog.ForkDefinition()  // name="__fork__"
    2. background = true (Fork 强制)
    3. allowed = ApplyAgentToolFilter(...)
       注意:这里 def.DisallowedTools 不含 "Agent" → Fork 子 Agent 工具集保留 Agent
    4. forkedMsgs := BuildForkedMessages(parentConv.Messages(), args.Prompt)
    5. subConv := conversation.NewFromMessages(forkedMsgs, ...)
    6. subAgent := agent.New(..., WithAllowedTools(allowed), WithSystemPrompt("")) // 继承主系统提示
    7. taskID := taskMgr.Launch(ctx, subAgent, subConv, args.Name, args.Prompt)
    8. 返回 {"task_id": "...", "status": "async_launched"}
```

### Fork 子 Agent 调 Agent 工具被阻断

```
Fork 子 Agent 跑动中,LLM 又产 tool_use:{name:"Agent", input:{...}}
    ↓
subAgent.executeBatched → AgentTool.Execute(subCtx, args)
    ↓
AgentTool.Execute:
    检测:IsForkContext(subConv.Messages()) → true(消息中含 <fork_boilerplate>)
    → 返回 ToolResult{IsError:true, Content:"Fork 子 Agent 不能再启动 Agent(检测到 fork boilerplate)"}
```

注:由于 `ALL_AGENT_DISALLOWED_TOOLS=[Agent]` 已经把 Agent 工具从子 Agent 工具列表里剔除,理论上 Fork 子 Agent 的 LLM 看不到 Agent 工具。但 Fork 路径**故意保留**(为了 prompt cache 一致性),靠 QuerySource + Boilerplate 兜底拦截。

**结论:** Fork 子 Agent 工具列表 = 父工具列表 - DisallowedTools - 后台白名单交集 - 但不去除 Agent 工具。

### Skill fork 改造

```
tui.Model.Execute("/foo") → skills.Executor.Execute → fork closure m.runSubAgent
    ↓ (改造后)
m.runSubAgent(ctx, conv, opts):
    return subagent.LaunchFork(ctx, subagent.FromTUI(m), subagent.ForkLaunchOpts{
        AllowedTools: opts.AllowedTools,
        Model:        opts.Model,
        Conv:         conv,              // skills 已构造好的 forkConv
        SystemPrompt: "",                // 走继承
        Background:   false,             // skills 仍走前台同步(返回 finalText 给 host)
        EventsSink:   nil,
    })
```

`subagent.LaunchFork` 内部:做与 `AgentTool.Execute` 前台路径相同的 wiring,只是不读 catalog Definition。

## 文件组织

```
gcode/
├── internal/
│   ├── subagent/                       ← 新增包
│   │   ├── doc.go                      包注释
│   │   ├── definition.go               Definition / Source 类型
│   │   ├── parser.go                   parseFrontmatterAndBody + validateMeta
│   │   ├── parser_test.go
│   │   ├── catalog.go                  Catalog + LoadCatalog / Resolve / List / ForkDefinition
│   │   ├── catalog_test.go
│   │   ├── embed.go                    go:embed builtin/*.md + builtinDefs() loader
│   │   ├── launch.go                   LaunchFork / Definition 公用 wiring 辅助
│   │   ├── launch_test.go
│   │   └── builtin/
│   │       ├── general-purpose.md
│   │       ├── explore.md
│   │       └── plan.md
│   │
│   ├── task/                           ← 新增包
│   │   ├── doc.go
│   │   ├── manager.go                  Manager + BackgroundTask + Launch / Adopt / Stop / SendMessage
│   │   ├── manager_test.go
│   │   └── tools.go                    NewTaskListTool / NewTaskGetTool / NewTaskStopTool / NewSendMessageTool
│   │   └── tools_test.go
│   │
│   ├── agent/                          ← 现有包扩展
│   │   ├── agent.go                    现有,加 systemPrompt/maxTurns/permissionMode/dontAsk/approvalUpgrader 字段;Run 抽出 runIter
│   │   ├── runtime.go                  现有,加 WithSystemPrompt/WithMaxTurns/WithPermissionMode/WithDontAsk/WithApprovalUpgrader/WithProvider 选项
│   │   ├── run_to_completion.go        ← 新增 RunToCompletion 实现
│   │   ├── fork.go                     ← 新增 BuildForkedMessages / IsForkContext / ForkBoilerplate
│   │   ├── fork_test.go
│   │   ├── agent_tool.go               ← 新增 NewAgentTool + Execute 逻辑
│   │   ├── agent_tool_test.go
│   │   ├── permission_upgrade.go       ← 新增 ApprovalUpgrader 类型 + DefaultUpgrader
│   │   ├── agent_test.go               补 RunToCompletion / dontAsk / approvalUpgrader 测试
│   │   └── ...其他不动
│   │
│   ├── tool/                           ← 现有包扩展
│   │   ├── filter.go                   ← 新增 ALL_AGENT_DISALLOWED / ASYNC_AGENT_ALLOWED / ApplyAgentToolFilter
│   │   ├── filter_test.go
│   │   └── ...其他不动
│   │
│   ├── tui/                            ← 现有包改动
│   │   ├── tui.go                      加 TaskMgr / SubAgentCatalog 字段 + consumeTaskDone goroutine + AgentTool 注册
│   │   ├── stream.go                   updateStreaming 加 ESC → AdoptRunning 分支;子 Agent ApprovalRequest 转发
│   │   ├── tasks.go                    ← 新增 consumeTaskDone + buildTaskNotification + ESC 切后台辅助
│   │   ├── skill_fork.go               ← 改造为复用 subagent.LaunchFork
│   │   └── ...
│   │
│   └── config/                         ← 现有,加配置项
│       └── config.go                   加 EnableSubAgentBackground bool(默认 true)
│
└── cmd/gcode/main.go                 ← 加 subagent.LoadCatalog / task.NewManager / 4 个工具注册 / Agent 工具注册
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| RunToCompletion 与 Run 关系 | 共用底层 helper(`runIter`/`streamOnce`),不重新写一遍循环 | 避免两套循环逻辑漂移;主对话与子 Agent 在 ReAct 层面行为应一致 |
| 子 Agent 是否独立 PermissionEngine | 暂共享同一 Engine,但增加 WithApprovalUpgrader 让审批升级回主 TUI | 本期权限规则全局一致;独立 Engine 是为隔离规则集准备的预留扩展点 |
| Fork 强制后台 | 是 | ch13 README 设计;Fork 上下文长,前台同步会阻塞用户;并行 Fork 才有意义 |
| 后台通知形式 | system reminder 注入(`<task-notification>`),不直接 push 到 LLM | 与 ch12 PendingReminders 一致;不打断用户当前操作;主 Agent 下次 turn 自然消费 |
| 嵌套阻断三道闸 | `ALL_AGENT_DISALLOWED_TOOLS` 全局 + Fork 路径 QuerySource + Boilerplate 标记扫描 | 单一闸门失效(对话压缩、工具列表漂移)仍能兜底;定义式靠工具过滤,Fork 靠双闸 |
| 后台白名单粒度 | 列具体工具名 + MCP/Skill 工具按命名约定动态识别 | ch13 README 同款做法;不需要为每个 MCP 工具列在白名单里 |
| done channel 缓冲 32 | 够大 | 正常场景一会儿不会有 32 个任务同时跑完;真满则丢弃 + stderr |
| SendMessage 同 id 复用 | 是 | 状态语义上是"该任务继续",而非"新任务";UI/查询体验更连贯 |
| 配置开关 EnableSubAgentBackground | 默认 true | 后台是核心能力,默认开启;关闭后所有子 Agent 强制前台,主要供 CI / 调试用 |
| Markdown 解析器复用 | 不共享,subagent 包独立实现一份(几乎与 skills/parser.go 一致) | 避免抽公共包导致循环依赖;两个包字段不一样,复用收益有限 |
| Agent 工具的 parent 注入时机 | main.go 注册时为 nil,tui.New 后 SetParent 回填 | tool.Registry 在 tui.New 之前已构造,Agent 工具的 parent 依赖 m.agent 反推 |
| ESC 切后台 vs Ctrl+C | ESC 切后台,Ctrl+C 仍是取消(沿用现有) | ESC 在 TUI 已经做"取消选择"用途,但流式态下 ESC 转为切后台是 ch13 README 设计 |
````

````markdown
# SubAgent 机制 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `internal/subagent/doc.go` | 包注释 |
| 新建 | `internal/subagent/definition.go` | Definition / Source 类型 |
| 新建 | `internal/subagent/parser.go` | parseFrontmatterAndBody + validateMeta |
| 新建 | `internal/subagent/parser_test.go` | 解析与字段校验单测 |
| 新建 | `internal/subagent/catalog.go` | Catalog + LoadCatalog / Resolve / List / ForkDefinition |
| 新建 | `internal/subagent/catalog_test.go` | 多来源加载与覆盖测试 |
| 新建 | `internal/subagent/embed.go` | go:embed builtin/*.md + builtinDefinitions() |
| 新建 | `internal/subagent/builtin/general-purpose.md` | 内置 general-purpose 定义 |
| 新建 | `internal/subagent/builtin/explore.md` | 内置 Explore 定义 |
| 新建 | `internal/subagent/builtin/plan.md` | 内置 Plan 定义 |
| 新建 | `internal/subagent/launch.go` | LaunchFork / 公用 wiring 辅助函数 |
| 新建 | `internal/subagent/launch_test.go` | LaunchFork 流程测试 |
| 新建 | `internal/task/doc.go` | 包注释 |
| 新建 | `internal/task/manager.go` | Manager + BackgroundTask + Launch / Adopt / Stop / SendMessage / SubscribeDone |
| 新建 | `internal/task/manager_test.go` | 后台任务全生命周期测试 |
| 新建 | `internal/task/tools.go` | 4 个内置工具 NewTaskListTool / NewTaskGetTool / NewTaskStopTool / NewSendMessageTool |
| 新建 | `internal/task/tools_test.go` | 4 个工具的单测 |
| 新建 | `internal/agent/run_to_completion.go` | RunToCompletion 方法实现 |
| 新建 | `internal/agent/run_to_completion_test.go` | RunToCompletion / dontAsk / maxTurns 测试 |
| 新建 | `internal/agent/fork.go` | BuildForkedMessages + IsForkContext + ForkBoilerplate |
| 新建 | `internal/agent/fork_test.go` | Fork 消息构造与上下文识别测试 |
| 新建 | `internal/agent/agent_tool.go` | NewAgentTool + AgentTool.Execute |
| 新建 | `internal/agent/agent_tool_test.go` | Agent 工具调用、嵌套阻断、超时切后台测试 |
| 新建 | `internal/agent/permission_upgrade.go` | ApprovalUpgrader 类型 + DefaultUpgrader |
| 新建 | `internal/tool/filter.go` | ALL_AGENT_DISALLOWED / ASYNC_AGENT_ALLOWED / ApplyAgentToolFilter |
| 新建 | `internal/tool/filter_test.go` | 过滤多层防线测试 |
| 新建 | `internal/tui/tasks.go` | consumeTaskDone + buildTaskNotification + ESC 切后台辅助 |
| 修改 | `internal/agent/agent.go` | 加 systemPrompt/maxTurns/permissionMode/dontAsk/approvalUpgrader 字段;Run 抽 runIter;runGuarded 加 dontAsk 短路 + approvalUpgrader 升级 |
| 修改 | `internal/agent/runtime.go` | 加 WithSystemPrompt / WithMaxTurns / WithPermissionMode / WithDontAsk / WithApprovalUpgrader / WithProvider 选项 |
| 修改 | `internal/agent/agent_test.go` | 不破坏既有测试 |
| 修改 | `internal/tool/registry.go` | 不动(过滤逻辑在 filter.go) |
| 修改 | `internal/tui/tui.go` | TUIParams 加 TaskMgr/SubAgentCatalog;Model 持有;Init 启 consumeTaskDone;AgentTool 注册后 SetParent |
| 修改 | `internal/tui/stream.go` | updateStreaming 加 ESC → AdoptRunning 分支 |
| 修改 | `internal/tui/skill_fork.go` | 改造为调 subagent.LaunchFork |
| 修改 | `internal/tui/tui_test.go` | 补 ESC 切后台、task-notification 注入测试 |
| 修改 | `internal/config/config.go` | 加 EnableSubAgentBackground bool(默认 true) |
| 修改 | `cmd/gcode/main.go` | LoadCatalog / NewManager / 4 个 task 工具注册 / Agent 工具注册 + SetParent;TaskMgr / SubAgentCatalog 传给 tui.New |

## T1: subagent 包的 Definition 与 Source 类型**文件:** `internal/subagent/definition.go`
**依赖:** 无
**步骤:**
1. 新建包 `subagent`,加 `definition.go`,声明 `Source int` 类型与四个常量:
   - `SourceBuiltin Source = iota`
   - `SourceUser`
   - `SourceProject`
   - `SourcePlugin`(占位)
2. `Source.String()` 返回 `"builtin" / "user" / "project" / "plugin"`,越界返回 `"unknown"`
3. 声明 `Definition` 结构体,字段如 plan.md 所述:`Name / Description / Tools / DisallowedTools / Model / MaxTurns / PermissionMode / DontAsk / Background / SystemPrompt / FilePath / Source`
4. 注释每个字段语义,引用 spec F4
5. `Definition.IsFork()` 返回 `d.Name == "__fork__"`(便于 ForkDefinition 判别)

**验证:** `go build ./internal/subagent/...` 编译通过

## T2: subagent 解析器**文件:** `internal/subagent/parser.go`
**依赖:** T1
**步骤:**
1. 新建 `parser.go`,从 `skills/parser.go` 复制 `parseFrontmatterAndBody` 与 `utf8BOM` 常量(几乎 ✓ 不变,改为 `subagent` 包名)
2. 声明 `agentNameRegex = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9-_]{0,31}$`)`(大小写都允许,与 ch13 README 的 `Explore`/`Plan` 一致)
3. 实现 `ParseDefinition(data []byte, filePath string, source Source) (*Definition, error)`:
   - 调 parseFrontmatterAndBody 拿 frontmatter map + body
   - YAML unmarshal 到一个临时 struct `agentFM`:
     ```go
     type agentFM struct {
         Name           string   `yaml:"name"`
         Description    string   `yaml:"description"`
         Tools          []string `yaml:"tools,omitempty"`
         DisallowedTools []string `yaml:"disallowedTools,omitempty"`
         Model          string   `yaml:"model,omitempty"`
         MaxTurns       int      `yaml:"maxTurns,omitempty"`
         PermissionMode string   `yaml:"permissionMode,omitempty"`
         Background     bool     `yaml:"background,omitempty"`
     }
     ```
   - 校验 Name 非空且匹配 agentNameRegex
   - 校验 Description 非空
   - 校验 Model:空 / "inherit" / "haiku" / "sonnet" / "opus" 之一,其它 stderr 警告并改为 "inherit"
   - 解析 PermissionMode:"dontAsk" 单独识别 → Definition.DontAsk=true, Definition.PermissionMode=ModeDefault;否则调 `permission.ParseMode`,失败 stderr 警告并改为 ModeDefault
   - 把 fm 字段映射到 Definition 字段(SystemPrompt = body,FilePath = filePath,Source = source)
4. 实现 `ParseFile(path string, source Source) (*Definition, error)`:`os.ReadFile` + `ParseDefinition`

**验证:** `go test ./internal/subagent/ -run TestParse -v` 通过(对应 T3 的测试)

## T3: subagent 解析器测试**文件:** `internal/subagent/parser_test.go`
**依赖:** T2
**步骤:**
1. 表驱动测试:正常完整 frontmatter / 仅必填 / model 非法 → 警告 fallback / permissionMode=dontAsk → DontAsk=true / 缺 name 报错 / 缺 description 报错 / frontmatter 未关闭 → 错误
2. body 区段提取:验证 `---` 后的内容(去 BOM 去前导换行)被完整取到 SystemPrompt
3. 测试 ParseFile 读取一个 testdata/*.md 文件
4. 表驱动写法,每个用例附 `t.Errorf("case %s: ...", name)` 描述

**验证:** `go test ./internal/subagent/ -run TestParse -v` 全部通过

## T4: 内置 Agent 定义文件**文件:** `internal/subagent/builtin/{general-purpose,explore,plan}.md`
**依赖:** 无
**步骤:**
1. 创建目录 `internal/subagent/builtin/`
2. `general-purpose.md`:
   ```yaml
   ---
   name: general-purpose
   description: 通用子 Agent,拥有全部工具,用于需要完整能力但独立上下文的场景
   maxTurns: 30
   ---

   你是 GCode 的通用 Agent。根据用户的消息,使用可用工具完成任务。
   把任务做完,不要过度设计,但也不要做一半就停。
   完成后用简洁的报告回复:做了什么、关键发现。
   调用方会把结果转述给用户,所以只需要包含要点。
   ```
3. `explore.md`:
   ```yaml
   ---
   name: Explore
   description: 只读代码探索 Agent,适合搜索、阅读、理清调用链;不能修改文件
   disallowedTools:
     - write_file
     - edit_file
   model: haiku
   maxTurns: 30
   ---

   你是一个文件搜索专家。这是一个只读探索任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工具策略:Glob 做文件模式匹配、Grep 搜索文件内容、Read 读取已知路径、Bash 仅用于只读操作(ls、git log、find、cat)。
   尽可能并行发起多个工具调用。高效完成搜索请求,清晰报告发现。
   ```
4. `plan.md`:
   ```yaml
   ---
   name: Plan
   description: 计划 Agent,分析需求、制定执行计划,但不直接执行;主 Agent 拿到计划后逐步执行
   disallowedTools:
     - write_file
     - edit_file
     - Agent
   maxTurns: 15
   permissionMode: plan
   ---

   你是一个软件架构师和规划专家。这是一个只读规划任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工作流程:① 理解需求 ② 用搜索工具充分探索代码库 ③ 设计方案 ④ 输出分步实现计划。
   回复末尾必须列出 3-5 个对实现最关键的文件路径。
   ```

**验证:** 三个 .md 文件存在,frontmatter 合法;ParseFile 测试不报错

## T5: subagent embed 与内置加载**文件:** `internal/subagent/embed.go`
**依赖:** T2, T4
**步骤:**
1. 新建 `embed.go`,声明:
   ```go
   //go:embed builtin/*.md
   var builtinFS embed.FS
   ```
2. 实现 `builtinDefinitions() []*Definition`:
   - `fs.ReadDir(builtinFS, "builtin")` 列文件
   - 对每个 .md 文件:`fs.ReadFile(builtinFS, "builtin/"+name)` + `ParseDefinition(data, "builtin:"+name, SourceBuiltin)`
   - 解析失败 panic(代码 bug,启动期失败即灾难)
3. 返回 slice,按 name 升序

**验证:** `go test ./internal/subagent/ -run TestBuiltin -v` 通过(T7)

## T6: Catalog 与三层加载**文件:** `internal/subagent/catalog.go`
**依赖:** T1, T2, T5
**步骤:**
1. 新建 `catalog.go`,声明:
   ```go
   type Catalog struct {
       mu       sync.Mutex
       defs     map[string]*Definition
       bySource map[Source][]*Definition
   }
   ```
2. 实现 `LoadCatalog(root string) *Catalog`:
   - `c := &Catalog{defs: map[string]*Definition{}, bySource: map[Source][]*Definition{}}`
   - 加载 builtin → `c.addAll(builtinDefinitions(), SourceBuiltin)`
   - 加载 user → `c.addAll(loadFromDir(filepath.Join(homeDir, ".gcode/agents"), SourceUser), SourceUser)`
   - 加载 project → `c.addAll(loadFromDir(filepath.Join(root, ".gcode/agents"), SourceProject), SourceProject)`
   - plugin 层本期跳过
3. 实现 `loadFromDir(dir string, source Source) []*Definition`:
   - 目录不存在 → 返回 nil
   - 遍历 *.md 文件,逐个 ParseFile;失败 stderr 警告并跳过
   - 返回 slice
4. 实现 `addAll(defs []*Definition, source Source)`:
   - 同名时高优先级覆盖(因为按 builtin → user → project 顺序加载,后加的优先级更高)
   - 同时往 `bySource[source]` 追加
5. 实现 `Resolve(name string) (*Definition, bool)`
6. 实现 `List() []*Definition`(按 name 升序)
7. 实现 `ListBySource(s Source) []*Definition`
8. 实现 `ForkDefinition() *Definition`:
   ```go
   return &Definition{
       Name: "__fork__",
       Description: "Fork-based subagent",
       Model: "inherit",
       MaxTurns: 25,
       PermissionMode: permission.ModeDefault,
       // Tools/DisallowedTools 留空 -> 工具集继承父
   }
   ```

**验证:** `go test ./internal/subagent/ -run TestCatalog -v` 通过

## T7: Catalog 测试**文件:** `internal/subagent/catalog_test.go`
**依赖:** T6
**步骤:**
1. 测试 builtinDefinitions 返回 3 个 def(general-purpose / Explore / Plan)
2. 测试三层覆盖:用 t.TempDir() 造一个项目 root 与一个 HOME 路径(set/unset HOME 环境变量),分别放 explore.md
3. 验证 Resolve("Explore") 在三种情形下返回的 Source 正确(都有 → project;只有 user+builtin → user;只有 builtin → builtin)
4. 测试 ForkDefinition 返回 IsFork()=true
5. 测试加载错误处理:放一个非法 frontmatter 文件,加载后该文件 *被跳过*,其他文件仍正常

**验证:** `go test ./internal/subagent/ -v` 全部通过

## T8: 工具过滤多层防线**文件:** `internal/tool/filter.go`
**依赖:** 无
**步骤:**
1. 新建 `filter.go`,声明三个全局变量:
   ```go
   var ALL_AGENT_DISALLOWED_TOOLS = []string{"Agent"}
   var CUSTOM_AGENT_DISALLOWED_TOOLS = []string{}
   var ASYNC_AGENT_ALLOWED_TOOLS = []string{
       "read_file", "write_file", "edit_file",
       "glob", "grep",
       "bash",
       "load_skill", "install_skill",
   }
   ```
2. 声明 `FilterParams` 结构体:
   ```go
   type FilterParams struct {
       All        []string  // registry 的全部工具名
       Source     int       // 1=builtin, 2=user, 3=project, 4=plugin(数值需与 subagent.Source 对齐,这里用 int 避免反向依赖)
       Background bool
       Allowed    []string  // Agent 定义的 tools 白名单
       Disallowed []string  // Agent 定义的 disallowedTools 黑名单
   }
   ```
3. 实现 `ApplyAgentToolFilter(p FilterParams) []string`:
   按 spec F30 顺序:
   - 起点 = `p.All` 副本
   - 过滤 1:去除 `ALL_AGENT_DISALLOWED_TOOLS`
   - 过滤 2:若 `p.Source >= 2`(非 builtin),再去除 `CUSTOM_AGENT_DISALLOWED_TOOLS`(本期为空,跳过)
   - 过滤 3:若 `p.Background`,与 `ASYNC_AGENT_ALLOWED_TOOLS + isMCPOrSkill(name)` 取交集
   - 过滤 4:去除 `p.Disallowed`
   - 过滤 5:若 `len(p.Allowed) > 0`,与之取交集
4. 辅助函数 `isMCPOrSkill(name string) bool`:`strings.HasPrefix(name, "mcp__")` || ...对 skill 工具的识别本期暂不接入(主 Registry 不区分,先按名字前缀 + 内置基础工具白名单兜底)

**验证:** `go build ./internal/tool/...` 编译通过

## T9: 工具过滤测试**文件:** `internal/tool/filter_test.go`
**依赖:** T8
**步骤:**
1. 表驱动测试 ApplyAgentToolFilter 覆盖各组合:
   - 默认:无后台、无白名单、无黑名单 → 去 Agent 即可
   - 后台:取 ASYNC_AGENT_ALLOWED_TOOLS 交集
   - 黑名单:`disallowed=[bash]` → 不含 bash
   - 白名单:`allowed=[read_file, grep]` → 仅这两个
   - 黑+白:白名单先收窄,黑名单再剔除
   - 后台 + MCP 工具:MCP 工具(mcp__xxx)被保留(白名单 OK)
2. 单独测试 isMCPOrSkill 边界

**验证:** `go test ./internal/tool/ -run TestApplyAgentToolFilter -v` 通过

## T10: Agent 包扩展 - 新增 Option**文件:** `internal/agent/runtime.go`
**依赖:** 无
**步骤:**
1. 在 `Agent` 结构体加字段(agent.go):
   ```go
   systemPrompt     string
   maxTurns         int  // 0=用全局 maxIterations
   permissionMode   permission.Mode
   permissionModeSet bool   // 区分零值与未设置
   dontAsk          bool
   approvalUpgrader ApprovalUpgrader
   ```
2. 在 `runtime.go` 加 6 个新 Option:
   ```go
   func WithSystemPrompt(s string) Option { return func(a *Agent) { a.systemPrompt = s } }
   func WithMaxTurns(n int) Option { return func(a *Agent) { if n > 0 { a.maxTurns = n } } }
   func WithPermissionMode(m permission.Mode) Option { return func(a *Agent) { a.permissionMode = m; a.permissionModeSet = true } }
   func WithDontAsk(b bool) Option { return func(a *Agent) { a.dontAsk = b } }
   func WithApprovalUpgrader(fn ApprovalUpgrader) Option { return func(a *Agent) { a.approvalUpgrader = fn } }
   func WithProvider(p llm.Provider) Option { return func(a *Agent) { a.provider = p } }
   ```
3. 加注释解释每个选项语义

**验证:** `go build ./internal/agent/...` 编译通过

## T11: ApprovalUpgrader 类型**文件:** `internal/agent/permission_upgrade.go`
**依赖:** T10
**步骤:**
1. 新建文件,声明:
   ```go
   type ApprovalUpgrader func(ctx context.Context, req *ApprovalRequest) (permission.Outcome, bool)
   ```
2. 注释解释:子 Agent 把审批请求升级到父 TUI 的回调;返回 (outcome, ok)——ok=false 时调用方应走默认 emit Approval 路径

**验证:** `go build ./internal/agent/...` 编译通过

## T12: Fork 路径辅助函数**文件:** `internal/agent/fork.go`
**依赖:** 无(纯函数)
**步骤:**
1. 新建 `fork.go`,声明常量:
   ```go
   const ForkBoilerplateTag = "<fork_boilerplate>"

   const ForkBoilerplate = `<fork_boilerplate>
   你是一个 Fork 出来的工作进程。你不是主 Agent。
   规则(不可协商):
   1. 不能再 Fork(调用 Agent 工具会被拦截)。
   2. 不要对话、不要提问、不要请求确认。
   3. 直接使用工具:读文件、搜索代码、做修改。
   4. 严格限制在你被分配的任务范围内。
   5. 最终报告以 "Scope:" 开头,500 字以内。
   </fork_boilerplate>

   `
   ```
2. 实现 `BuildForkedMessages(parentMsgs []llm.Message, task string) []llm.Message`:
   - 深拷贝 parentMsgs(参考 conversation.NewFromMessages 的拷贝逻辑)
   - 扫描末尾 assistant 消息的 ToolCalls:对于每个未配对的 ToolCallID,在 cloned 末尾追加 RoleTool 消息(每个 ID 一条 placeholder ToolResult{Content:"[forked, skipped]", IsError:true})
     - 配对检查:看看 cloned 后续是否有 RoleTool 消息消费这些 ID
   - 追加最后一条 user 消息:`Content = ForkBoilerplate + task`
3. 实现 `IsForkContext(msgs []llm.Message) bool`:
   - 遍历 msgs,若 user/tool/assistant 消息内容含 `ForkBoilerplateTag` → 返回 true
   - 默认 false

**验证:** `go test ./internal/agent/ -run TestFork -v` 通过(T13)

## T13: Fork 辅助函数测试**文件:** `internal/agent/fork_test.go`
**依赖:** T12
**步骤:**
1. 测试 BuildForkedMessages 空 parent → 返回单条 user 消息含 Boilerplate + task
2. 测试 parent 末尾有完整 assistant + tool_result 配对:cloned 末尾 == parent 末尾 + 一条 user
3. 测试 parent 末尾 assistant 有 2 个 tool_use 没配对:cloned 中追加 1 条 RoleTool(2 个 placeholder ToolResult)再追加 1 条 user
4. 测试 IsForkContext:消息中含 Boilerplate → true;不含 → false

**验证:** `go test ./internal/agent/ -run TestFork -v` 通过

## T14: runGuarded 加 dontAsk 短路与 approvalUpgrader**文件:** `internal/agent/agent.go`
**依赖:** T10, T11
**步骤:**
1. 修改 `runGuarded`,在 `default: // Ask` 分支里:
   ```go
   case Ask:
       // 子 Agent dontAsk 模式:直接 Allow
       if a.dontAsk {
           return a.runTool(ctx, c), true
       }
       // 子 Agent 升级到父 TUI 审批
       if a.approvalUpgrader != nil {
           if o, ok := a.approvalUpgrader(ctx, &ApprovalRequest{
               Name: c.Name, Args: argsPreview(c.Input), Reason: reason,
               Respond: nil, // upgrader 内部处理 Respond
           }); ok {
               switch o {
               case permission.OutcomeAllowOnce: return a.runTool(ctx, c), true
               case permission.OutcomeAllowForever: _ = a.eng.PersistLocalAllow(c); return a.runTool(ctx, c), true
               default: return denyResult(c.ID, "用户拒绝了本次调用"), true
               }
           }
       }
       // 默认路径:emit Approval event(主 Agent inline / Skill fork 都走此)
       o, ok := a.requestApproval(ctx, c, reason, ch)
       ...
   ```
2. 修改 `Check` 调用前,如果子 Agent 设了 permissionMode(`a.permissionModeSet=true`),用 `a.permissionMode` 覆盖入参 mode
3. 修改 streamLoop 拿 defs 处的 allowedTools 逻辑(已有,无须改)

**验证:** `go test ./internal/agent/ -v` 现有测试不破

## T15: RunToCompletion 实现**文件:** `internal/agent/run_to_completion.go`
**依赖:** T10, T14
**步骤:**
1. 新建文件,实现:
   ```go
   func (a *Agent) RunToCompletion(ctx context.Context, conv *conversation.Conversation, task string, events chan<- Event) (string, error)
   ```
2. 逻辑:
   - 把 task 作为 user 消息:`conv.AddUser(task)`(注意 conv 可能已经被 Fork 路径预装填)
   - 计算 maxTurns:`turns := a.maxTurns; if turns == 0 { turns = maxIterations }`
   - 复用 Run 的循环逻辑:但不用 channel,直接内部消费;改为返回 finalText + err
   - 拆出 helper `runIter(ctx, conv, mode, iter, defs, sys, envText, reminder, eventsChan) (text string, calls []llm.ToolCall, done bool, err error)` 让 Run 和 RunToCompletion 都调
   - `Run` 改造为 调 runIter 逐轮;RunToCompletion 也是
   - 子 Agent 用模式:`mode := permission.ModeDefault; if a.permissionModeSet { mode = a.permissionMode }`
3. 退出条件:`done==true`(模型不再调工具)→ 返回 finalText;触达 turns → 返回 finalText + ErrMaxTurnsReached;ctx 取消 → 返回 finalText + ctx.Err();出错 → 返回 finalText + err
4. 在每轮内继续做 hook 调度(PreToolUse/PostToolUse/Stop 等),但 SubAgent 不触发 memory update
5. events 通道转发:把 Tool / Text / Approval 事件转发出去(供 TaskManager / TUI 接收)

**验证:** `go test ./internal/agent/ -run TestRunToCompletion -v` 通过(T16)

## T16: RunToCompletion 测试**文件:** `internal/agent/run_to_completion_test.go`
**依赖:** T15
**步骤:**
1. 用 mock provider(已有 testhelpers)模拟一个回合返回纯文本的子 Agent → RunToCompletion 返回 "ok",err==nil
2. 模拟一个回合返回 tool_use(已知工具),下一轮返回纯文本 → 工具被执行、finalText="..."
3. 模拟模型一直调工具不出文本,触达 maxTurns=3 → 返回 ErrMaxTurnsReached
4. 测试 dontAsk:子 Agent 设 WithDontAsk(true) + 模型调一个 Ask 级工具(如 bash) → 工具被自动放行执行
5. 测试 approvalUpgrader 回调被命中:子 Agent 设了 upgrader,Ask 时 upgrader 被调用(用 mock upgrader 验证)
6. 测试 events channel 转发:运行子 Agent 时把 events 收集到 slice,断言含 Tool/Text 事件

**验证:** `go test ./internal/agent/ -run TestRunToCompletion -v` 全部通过

## T17: Agent 工具实现**文件:** `internal/agent/agent_tool.go`
**依赖:** T8, T12, T15
**步骤:**
1. 新建文件,声明:
   ```go
   type AgentTool struct {
       catalog   AgentCatalog  // 接口,避免反向依赖 subagent 包
       taskMgr   TaskManager
       parent    *Agent
       bgEnabled bool
   }

   type AgentCatalog interface {
       Resolve(name string) (*subagent.Definition, bool) // 暂时 fine,subagent 不依赖 agent
       ForkDefinition() *subagent.Definition
       List() []*subagent.Definition
   }

   type TaskManager interface {
       Launch(ctx context.Context, ag *Agent, conv *conversation.Conversation, name, task string) string
       AdoptRunning(ctx context.Context, ag *Agent, conv *conversation.Conversation, name string, ev <-chan Event, cancel context.CancelFunc, partial *PartialState) string
       UpgradeApproval(ctx context.Context, req *ApprovalRequest) (permission.Outcome, bool)
   }
   ```
2. **解决循环依赖**:agent 包要引用 subagent 包,但 subagent 不应反过来。检查 subagent.Definition 是否引用 agent 包——目前 Definition 只引用 permission 包,没问题。直接 import "gcode/internal/subagent"。
3. **AgentTool 接口实现**:
   - Name() = "Agent"
   - Description() 动态:基础描述 + `subagent_type 可选值:" + strings.Join(catalog.List() 的 name, ", ")`
   - Parameters():按 spec F1 写 JSON Schema
   - ReadOnly() = false
   - Execute(ctx, args):
4. **Execute 主流程**:
   ```go
   var aArgs AgentArgs
   if err := json.Unmarshal(args, &aArgs); err != nil { 返回 err }
   if aArgs.Prompt == "" { 返回错误 "prompt is required" }
   if aArgs.Description == "" { 返回错误 "description is required" }

   // 防嵌套
   if isSubAgentContext(ctx) { 返回错误 "subagent cannot spawn Agent" }
   if conv := getParentConv(ctx); conv != nil && IsForkContext(conv.Messages()) { 返回错误 "Fork subagent cannot spawn Agent (boilerplate detected)" }

   // Resolve 定义
   var def *subagent.Definition
   if aArgs.SubagentType != "" {
       if d, ok := t.catalog.Resolve(aArgs.SubagentType); !ok { 返回错误 "unknown subagent_type: " + aArgs.SubagentType } else { def = d }
   } else {
       def = t.catalog.ForkDefinition()
   }

   // 决定后台
   background := def.Background || aArgs.RunInBackground || def.IsFork()
   if background && !t.bgEnabled { 返回错误 "background mode is disabled by config" }

   // 工具过滤
   allowed := tool.ApplyAgentToolFilter(tool.FilterParams{
       All:        registryAllNames(t.parent.registry),
       Source:     int(def.Source),
       Background: background,
       Allowed:    def.Tools,
       Disallowed: def.DisallowedTools,
   })

   // provider
   provider := t.parent.provider
   // (model 字段切换 provider 的逻辑暂从简:本期不实现按模型切换,后续完善)

   // 构造子 Agent
   subRuntime := NewSessionRuntime(200000)
   subAgent := New(provider, t.parent.registry, t.parent.version, t.parent.eng,
       WithRuntime(subRuntime),
       WithAllowedTools(allowed),
       WithSystemPrompt(def.SystemPrompt),
       WithMaxTurns(def.MaxTurns),
       WithPermissionMode(def.PermissionMode),
       WithDontAsk(def.DontAsk),
       WithApprovalUpgrader(t.taskMgr.UpgradeApproval),
       WithHookEngine(t.parent.hookEngine),
   )
   // 标记子 Agent 上下文(让递归 Agent 工具调用被拦截)
   childCtx := withSubAgentContext(ctx)

   // 子 Conv
   subConv := conversation.New()
   if def.IsFork() {
       parentMsgs := getParentConvMessages(ctx, t.parent)  // 从某种机制取父 conv;若 ctx 没带,fallback 报错
       forked := BuildForkedMessages(parentMsgs, aArgs.Prompt)
       subConv = conversation.NewFromMessages(forked, nil, nil)
   }

   // 后台路径
   if background {
       taskID := t.taskMgr.Launch(ctx, subAgent, subConv, aArgs.Name, aArgs.Prompt)
       return tool.Result{Content: fmt.Sprintf(`{"task_id":"%s","status":"async_launched"}`, taskID)}
   }

   // 前台路径
   timeoutCtx, cancel := context.WithTimeout(childCtx, autoBackgroundDuration)
   events := make(chan Event, 32)
   var partial PartialState
   go aggregatePartial(events, &partial)

   finalText, err := subAgent.RunToCompletion(timeoutCtx, subConv, aArgs.Prompt, events)
   close(events)

   if errors.Is(timeoutCtx.Err(), context.DeadlineExceeded) {
       taskID := t.taskMgr.AdoptRunning(ctx, subAgent, subConv, aArgs.Name, nil /* already done? */, cancel, &partial)
       return tool.Result{Content: fmt.Sprintf(`{"task_id":"%s","status":"timed_out_to_background"}`, taskID)}
   }
   cancel()
   if err != nil { return tool.Result{Content: "subagent error: " + err.Error(), IsError: true} }
   return tool.Result{Content: finalText}
   ```
5. 实现辅助函数:`isSubAgentContext / withSubAgentContext / getParentConvMessages / aggregatePartial`
6. 提供 `SetParent(a *Agent)` 让 main 在 tui.New 之后回填 parent 引用

**验证:** `go test ./internal/agent/ -run TestAgentTool -v` 通过(T18)

## T18: Agent 工具测试**文件:** `internal/agent/agent_tool_test.go`
**依赖:** T17
**步骤:**
1. 测试 missing prompt → 返回错误
2. 测试 unknown subagent_type → 返回错误
3. 测试 known subagent_type(用一个 mock catalog 注入)→ 子 Agent 跑动并返回结果
4. 测试 run_in_background=true → 返回 `async_launched` JSON
5. 测试嵌套:用 withSubAgentContext 包 ctx 后调 Execute → 返回错误
6. 测试 IsForkContext 兜底:用 forked subConv 调,Agent 工具拦截
7. 测试 EnableSubAgentBackground=false 时 background 路径报错

**验证:** `go test ./internal/agent/ -run TestAgentTool -v` 全部通过

## T19: task 包基础结构**文件:** `internal/task/manager.go`
**依赖:** T10, T15
**步骤:**
1. 新建包 `task`,加 doc.go 与 manager.go
2. 声明 `Status int` 与四个常量:`StatusRunning / StatusCompleted / StatusFailed / StatusCancelled`
3. 声明 `Usage` 结构体(对齐 agent.Usage)
4. 声明 `BackgroundTask` 结构体(字段如 plan.md)
5. 声明 `PartialState` 结构体
6. 声明 `Manager` 结构体:`mu sync.Mutex; tasks map[string]*BackgroundTask; byName map[string]string; done chan string; counter int64`
7. 实现 `NewManager() *Manager`:`done = make(chan string, 32)`,counter=0
8. 实现 `nextID() string`:`atomic.AddInt64(&counter, 1)` 后格式化为 `task_<8 字节十六进制>`(用 `time.Now().UnixNano() ^ counter` 取低 4 字节足够)
9. 实现 `Get(id)` / `List()` / `SubscribeDone()` 等查询方法

**验证:** `go build ./internal/task/...` 编译通过

## T20: Manager.Launch 实现**文件:** `internal/task/manager.go`
**依赖:** T19
**步骤:**
1. 实现:
   ```go
   func (m *Manager) Launch(parentCtx context.Context, ag *agent.Agent, conv *conversation.Conversation, name, taskText string) string {
       id := m.nextID()
       ctx, cancel := context.WithCancel(parentCtx)
       bt := &BackgroundTask{
           ID: id, Name: name, SubAgent: ag, Conv: conv, Task: taskText,
           Status: StatusRunning, StartTime: time.Now(), Cancel: cancel,
       }
       m.mu.Lock()
       m.tasks[id] = bt
       if name != "" { m.byName[name] = id }  // 后启动覆盖前
       m.mu.Unlock()

       go func() {
           defer func() {
               if r := recover(); r != nil {
                   bt.Status = StatusFailed
                   bt.Err = fmt.Errorf("subagent panic: %v", r)
                   bt.EndTime = time.Now()
               }
               select {
               case m.done <- id:
               default:
                   fmt.Fprintf(os.Stderr, "task manager: done channel full, dropping notification for %s\n", id)
               }
           }()

           events := make(chan agent.Event, 32)
           go aggregateTaskEvents(events, bt)

           text, err := ag.RunToCompletion(ctx, conv, taskText, events)
           close(events)

           bt.EndTime = time.Now()
           if err != nil {
               if errors.Is(err, context.Canceled) {
                   bt.Status = StatusCancelled
               } else {
                   bt.Status = StatusFailed
                   bt.Err = err
                   bt.Result = text
               }
           } else {
               bt.Status = StatusCompleted
               bt.Result = text
           }
       }()
       return id
   }
   ```
2. 实现 `aggregateTaskEvents(ch <-chan agent.Event, bt *BackgroundTask)`:每个 Tool PhaseStart 累加 ToolCount + 更新 LastActivity;每个 Usage 累加到 bt.Usage

**验证:** `go test ./internal/task/ -run TestLaunch -v` 通过(T22)

## T21: Manager.Stop / AdoptRunning / SendMessage / UpgradeApproval**文件:** `internal/task/manager.go`
**依赖:** T20
**步骤:**
1. 实现 `Stop(id) bool`:查 tasks → 调 task.Cancel();返回是否找到
2. 实现 `AdoptRunning(...)`:与 Launch 类似但接收已 derive 的 ag/conv/cancel/events;创建 BackgroundTask,把 PartialState 字段复制进去,起 goroutine 继续消费 ev 并跑动(注意此时 ag.RunToCompletion 已经在父 ctx 中跑;父 ctx 超时后子 ctx 也 done;Adopt 实际上是开一个 goroutine 继续消费 events channel 直到关闭)
   - 简化方案:Adopt 不调 RunToCompletion(因为 RunToCompletion 已在前台启动);只是注册 BackgroundTask 状态、聚合事件、等 events channel 关闭后写终态、push done
   - cancel 是新的 derive context 的 cancel,Stop 时用
3. 实现 `SendMessage(parentCtx, name, message)`:
   - 查 byName → id
   - 查 Get(id) → bt;bt.Status != Completed → ErrTaskBusy
   - bt.Conv.AddUser(message);bt.Status = StatusRunning;bt.StartTime/EndTime 不重置
   - 重新起 goroutine 跑 RunToCompletion(同样的 ag/conv);跑完逻辑同 Launch
   - 返回 (id, nil)
4. 实现 `UpgradeApproval(ctx, req) (Outcome, bool)`:把 req 转发到一个全局 channel(`approvalCh chan *agent.ApprovalRequest`);TUI 消费;返回 ok=false 时调用方走默认路径
   - 简化:本期 UpgradeApproval 直接返回 (0, false)——让 Approval 走到子 Agent 自己的 Run channel,TUI 通过 events 转发感知

**验证:** `go test ./internal/task/ -run TestStop -v` 通过

## T22: task 包测试**文件:** `internal/task/manager_test.go`
**依赖:** T20, T21
**步骤:**
1. 用 mock provider + mock agent 模拟一个 subAgent → Launch → 等 done channel → 验证 status=Completed, result 正确
2. 用一个故意 panic 的 mock agent → Launch → done 收到 → status=Failed,Err 非空
3. Stop:Launch 后立刻 Stop → done 收到 → status=Cancelled
4. SendMessage:Launch + 等 Completed → SendMessage 重新跑 → 拿到新结果
5. byName 覆盖:Launch 两次同 name → 后启动覆盖

**验证:** `go test ./internal/task/ -v` 全部通过

## T23: 4 个后台任务工具**文件:** `internal/task/tools.go`
**依赖:** T19, T20, T21
**步骤:**
1. 实现 `NewTaskListTool(m *Manager) tool.Tool`:
   - Name()="TaskList",ReadOnly()=true,Parameters() 空对象
   - Execute:返回 JSON 形如 `[{"id":"...","name":"...","status":"running","tool_count":3,"last_activity":"bash"},...]`
2. 实现 `NewTaskGetTool(m *Manager) tool.Tool`:
   - Name()="TaskGet",Parameters() 含 `task_id` required
   - Execute:Get(id) → 全字段 JSON;找不到 → IsError=true
3. 实现 `NewTaskStopTool(m *Manager) tool.Tool`:
   - Name()="TaskStop",Parameters() 含 `task_id` required
   - Execute:m.Stop(id) → `{"status":"cancellation_requested"}` 或 错误
4. 实现 `NewSendMessageTool(m *Manager) tool.Tool`:
   - Name()="SendMessage",Parameters() 含 `name` / `message` required
   - Execute:m.SendMessage(ctx, name, msg) → `{"task_id":"...","status":"resumed"}` 或 错误
5. 所有工具实现 tool.SystemTool(IsSystem 返回 true),让它们在子 Agent 工具列表中默认豁免

**验证:** `go test ./internal/task/ -run TestTools -v` 通过(T24)

## T24: 4 个工具的单测**文件:** `internal/task/tools_test.go`
**依赖:** T23
**步骤:**
1. TaskList:Launch 几个任务后调 → 返回 JSON 含所有
2. TaskGet:已知 id → 返回完整字段
3. TaskGet:未知 id → IsError=true
4. TaskStop:Stop 一个 running task → 返回成功 + task 状态变 Cancelled
5. SendMessage:Launch 一个任务跑完 → SendMessage → 返回新 status

**验证:** `go test ./internal/task/ -v` 全部通过

## T25: TUI 加 TaskMgr / SubAgentCatalog wiring**文件:** `internal/tui/tui.go`
**依赖:** T6, T19, T23
**步骤:**
1. 在 `TUIParams` 加字段:
   ```go
   TaskMgr         *task.Manager
   SubAgentCatalog *subagent.Catalog
   ```
2. 在 `Model` 加字段:
   ```go
   taskMgr         *task.Manager
   subAgentCatalog *subagent.Catalog
   ```
3. 在 `New` 内:
   - 把 params 的字段挂到 Model
   - Init() 末尾启动 `go m.consumeTaskDone()`
4. 在 `Agent` 构造之后(单 provider 路径):
   - 主 Agent 也应该携带 ApprovalUpgrader(其实主 Agent 不需要;但 Agent 工具构造时需要 ApprovalUpgrader 给子 Agent 用)
   - Agent 工具的 parent 通过 `SetParent(m.agent)` 回填

**验证:** `go build ./internal/tui/...` 编译通过

## T26: task notification 注入**文件:** `internal/tui/tasks.go`
**依赖:** T19, T25
**步骤:**
1. 新建文件,实现:
   ```go
   func (m *Model) consumeTaskDone() {
       for id := range m.taskMgr.SubscribeDone() {
           bt, ok := m.taskMgr.Get(id)
           if !ok { continue }
           notif := buildTaskNotification(bt)
           if m.runtime != nil {
               m.runtime.AppendReminders([]string{notif})
           }
       }
   }
   ```
2. 实现 `buildTaskNotification(bt *task.BackgroundTask) string`:
   ```
   <task-notification>
   Task <id> (name="<name>"): <status>
   Result: <result 或 错误>
   </task-notification>
   ```
3. 注释解释行为(F19)

**验证:** `go build ./internal/tui/...` 编译通过

## T27: ESC 切后台**文件:** `internal/tui/stream.go`
**依赖:** T19, T25
**步骤:**
1. 在 `updateStreaming` 内 `case streamMsg:` 之前加 `case tea.KeyPressMsg:`:
   ```go
   case tea.KeyPressMsg:
       if msg.String() == "esc" && m.foregroundSubAgent != nil {
           // 移交后台
           id := m.taskMgr.AdoptRunning(m.ctx, m.foregroundSubAgent.agent, m.foregroundSubAgent.conv, m.foregroundSubAgent.name, m.foregroundSubAgent.events, m.foregroundSubAgent.cancel, m.foregroundSubAgent.partial)
           m.foregroundSubAgent = nil
           // 显示一条通知
           return tea.Println(noticeBlock(fmt.Sprintf("[esc] 子 Agent 切到后台 (task=%s)", id)))
       }
       return nil
   ```
2. 增加 `foregroundSubAgent` 字段到 `Model` 跟踪当前前台子 Agent;Agent 工具开始前台跑动时设置,跑完清除
3. 注意:前台子 Agent 的跑动其实是在 Agent 工具的 Execute 内同步阻塞的,主 TUI 此时是 "等 tool_result" 状态。这意味着 ESC 拦截需要在 Agent 工具的 Execute 内做(通过 m.foregroundSubAgent 共享状态)

**简化方案:** 由于前台子 Agent 在 Agent 工具同步阻塞内,ESC 切后台需要工具内监听 ctx 一类机制。本期实现保守版:Agent 工具的前台路径只支持「超时自动切后台」,不支持 ESC 切后台;ESC 切后台留待后续 ch14+ 完善。在 plan.md 与 spec.md 里要标注这一变更。

**重要变更:** F17/AC11 调整为:本期 ESC 切后台**不实现**,只实现「超时自动切后台」与「显式 run_in_background」。spec.md 已写出,checklist 跳过 ESC 场景。

修改方向:跳过 T27 的 ESC 部分,只保留 foregroundSubAgent 字段供未来扩展。

**验证:** `go build ./internal/tui/...` 编译通过

## T28: Skill fork 改造**文件:** `internal/tui/skill_fork.go`
**依赖:** T15
**步骤:**
1. 现有 `runSubAgent` 内部已经在用 `subAgent.Run`;改造为用 `RunToCompletion`:
   ```go
   func (m *Model) runSubAgent(ctx context.Context, conv *conversation.Conversation, opts skills.ForkOptions) (string, error) {
       if m.provider == nil { return "", errSubAgentNoProvider }

       prov := m.provider
       // (model 切换逻辑保留)

       subRuntime := agent.NewSessionRuntime(200000)
       subAgent := agent.New(prov, m.registry, m.version, m.engine,
           agent.WithRuntime(subRuntime),
           agent.WithAllowedTools(opts.AllowedTools),
           agent.WithHookEngine(m.hookEngine),
       )

       // 直接调 RunToCompletion(events=nil,前台同步)
       finalText, err := subAgent.RunToCompletion(ctx, conv, "" /* 此处 conv 末尾已含 user task */, nil)
       if err != nil { return "", err }
       return finalText, nil
   }
   ```
2. **注意**:现有 skills.Executor 调用前已经把任务作为 user 消息装填到 conv(`buildForkConversation` 末尾 `conv.AddUser(rendered)`)。新版 RunToCompletion 内部又会 conv.AddUser(task);若 task="" 会追加空消息。**改 RunToCompletion 为允许 task="" 时不追加**(if task != "" { conv.AddUser(task) }),或者改 skills.Executor 不再装填 user 消息让 RunToCompletion 装填。
3. 选第一种方案——RunToCompletion 加 if 判断

**验证:** `go test ./internal/skills/... ./internal/tui/...` 现有测试不破

## T29: Agent 工具注册到 registry**文件:** `cmd/gcode/main.go`
**依赖:** T17, T20, T23, T25
**步骤:**
1. 在 main.go 适当位置(skills.LoadCatalog 之后):
   ```go
   subagentCatalog := subagent.LoadCatalog(root)
   taskMgr := task.NewManager()

   // 4 个 task 工具
   registry.Register(task.NewTaskListTool(taskMgr))
   registry.Register(task.NewTaskGetTool(taskMgr))
   registry.Register(task.NewTaskStopTool(taskMgr))
   registry.Register(task.NewSendMessageTool(taskMgr))

   // Agent 工具(parent 暂为 nil,稍后 SetParent)
   agentTool := agent.NewAgentTool(subagentCatalog, taskMgr, nil, cfg.EnableSubAgentBackground)
   registry.Register(agentTool)
   ```
2. tui.New 调用扩展 TUIParams:
   ```go
   m, err := tui.New(... , tui.TUIParams{
       Writer:          writer,
       MemMgr:          memMgr,
       InstructionText: instructionText,
       MemoryText:      memoryText,
       SessionsDir:     sessionsDir,
       Catalog:         catalog,
       HookEngine:      hookEngine,
       TaskMgr:         taskMgr,
       SubAgentCatalog: subagentCatalog,
   })
   ```
3. tui.New 返回后回填 parent:
   ```go
   if a := m.MainAgent(); a != nil {
       agentTool.SetParent(a)
   }
   ```
4. tui.Model 加 `MainAgent() *agent.Agent` 方法返回 m.agent

**验证:** `go build ./...` 编译通过;运行 gcode 不报错

## T30: config 加 EnableSubAgentBackground**文件:** `internal/config/config.go`
**依赖:** 无
**步骤:**
1. 在 Config 结构体加字段:
   ```go
   EnableSubAgentBackground *bool `yaml:"enableSubAgentBackground,omitempty"`
   ```
2. 加 Effective() 方法:
   ```go
   func (c Config) EffectiveEnableSubAgentBackground() bool {
       if c.EnableSubAgentBackground == nil { return true }
       return *c.EnableSubAgentBackground
   }
   ```
3. 注释说明:默认 true;false 时所有 SubAgent 强制前台,Fork 路径会报错

**验证:** `go build ./internal/config/...` 通过

## T31: subagent.LaunchFork 公用 wiring**文件:** `internal/subagent/launch.go`
**依赖:** T6, T15, T17
**步骤:**
1. 新建 `launch.go`,实现:
   ```go
   type ForkLaunchOpts struct {
       AllowedTools []string
       Model        string
       Conv         *conversation.Conversation  // 已装填的子对话
       SystemPrompt string
       Background   bool
       EventsSink   chan<- agent.Event
       Provider     llm.Provider
       Registry     *tool.Registry
       Engine       *permission.Engine
       Version      string
       HookEngine   *hook.Engine
   }

   func LaunchFork(ctx context.Context, opts ForkLaunchOpts) (string, error)
   ```
2. 实现细节:
   - 构造 SessionRuntime / Agent(类似 agent_tool 的前台路径)
   - 调 RunToCompletion(ctx, opts.Conv, "" /* conv 已含 task */, opts.EventsSink)
   - 返回 finalText / err
3. **避免循环依赖**:subagent.LaunchFork 引用 agent 包(为构造 Agent);agent 不引用 subagent(Agent 工具是 agent 包内部,工厂签名接受 AgentCatalog 接口避开 import)
   - 但 agent_tool 内还是要 import "gcode/internal/subagent"——因为 Definition 类型。这就形成 subagent ← agent 之间的混乱。
   - **拆解方案**:
     - Definition 类型放在 subagent 包
     - Catalog 接口在 agent 包内定义(只用 List 必要方法)
     - subagent.LaunchFork 不返回到 agent 中,而是用 agent 暴露的 RunToCompletion 公共 API
4. 简化:agent_tool 直接 import subagent;subagent.LaunchFork 也 import agent。**循环依赖!** 这条路走不通。
5. **真正方案**:
   - subagent 包只放 Definition / Catalog / 加载逻辑(纯数据)
   - LaunchFork 放在 agent 包内(因为它要构造 agent.Agent)
   - agent_tool 也放 agent 包(已有)
   - tui/skill_fork 调 agent.LaunchFork(把 Definition 当参数传入)

**重新调整文件结构:**
- 删除 `internal/subagent/launch.go`(本任务取消)
- 新建 `internal/agent/launch.go` 实现 LaunchFork
- skills 的 fork 回调改为调 `agent.LaunchFork`

**验证:** 见 T28 验证

## T32: 集成测试 - 完整路径**文件:** `internal/agent/agent_tool_integration_test.go`(新增)
**依赖:** T17, T20, T29
**步骤:**
1. 端到端 mock:构造一个 mock provider 让主 Agent 调 Agent 工具(subagent_type="Explore"),子 Agent 也跑回纯文本
2. 验证 tool_result 包含子 Agent 的 finalText
3. 验证子 Agent 工具调用没看到 Agent 工具(过滤生效)
4. 验证后台路径:run_in_background=true → 立即返回 async_launched JSON,主 Agent 继续

**验证:** `go test ./internal/agent/ -run TestAgentToolIntegration -v` 通过

## T33: 编译与综合测试**依赖:** T1-T32
**步骤:**
1. `go build ./...`
2. `go vet ./...`
3. `go test ./...`

**验证:** 全部命令通过,无失败用例

## 执行顺序

```
T1 → T2 → T3
       ↘
        T5 → T6 → T7
       ↗
       T4
T8 → T9
T10 → T11 → T14
T10 → T12 → T13
T14, T15 → T16
T8, T12, T15 → T17 → T18
T19 → T20 → T21 → T22
T19 → T20 → T23 → T24
T6, T19, T23 → T25 → T26
T25 → T27(本期跳过 ESC)
T15 → T28
T30 → T29
T29 → T32
所有 → T33
```
````

````markdown
# SubAgent 机制 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### subagent 包

- [ ] internal/subagent 包存在且编译通过(验证:`go build ./internal/subagent/...`)
- [ ] Definition 结构体包含 Name/Description/Tools/DisallowedTools/Model/MaxTurns/PermissionMode/DontAsk/Background/SystemPrompt/FilePath/Source 全部字段(验证:`go test ./internal/subagent/ -run TestDefinition`)
- [ ] ParseDefinition 能正确解析合法 frontmatter + body,permissionMode=dontAsk 时 DontAsk=true(验证:`go test ./internal/subagent/ -run TestParse -v`)
- [ ] ParseDefinition 对 frontmatter 缺 name/description 报错,model 非法 fallback 到 inherit 并 stderr 警告(验证:对应测试通过)
- [ ] 内置 3 个文件(general-purpose/explore/plan)在 builtin/ 目录下,go:embed 加载成功(验证:`go test ./internal/subagent/ -run TestBuiltin`)
- [ ] LoadCatalog 按 builtin → user → project 顺序加载,同名高优先级覆盖(验证:`go test ./internal/subagent/ -run TestCatalog`)
- [ ] Catalog.Resolve("Explore") 在三层覆盖场景下返回正确 Source(验证:对应测试通过)
- [ ] Catalog.ForkDefinition() 返回 IsFork()=true 的临时 Definition(验证:对应测试通过)

### tool 过滤多层防线

- [ ] tool.ALL_AGENT_DISALLOWED_TOOLS / CUSTOM_AGENT_DISALLOWED_TOOLS / ASYNC_AGENT_ALLOWED_TOOLS 三个常量存在(验证:`go test ./internal/tool/ -run TestFilterConstants`)
- [ ] ApplyAgentToolFilter 按 spec F30 顺序应用五层过滤(验证:`go test ./internal/tool/ -run TestApplyAgentToolFilter -v`)
- [ ] 后台模式下,工具集与 ASYNC_AGENT_ALLOWED_TOOLS 取交集,Agent / TaskList / SendMessage 等元工具被剔除(验证:对应测试用例通过)
- [ ] MCP 工具(mcp__ 前缀)在后台模式下被保留(验证:对应测试用例通过)

### agent 包扩展

- [ ] WithSystemPrompt / WithMaxTurns / WithPermissionMode / WithDontAsk / WithApprovalUpgrader / WithProvider 6 个新 Option 存在且生效(验证:`go test ./internal/agent/ -run TestOptions`)
- [ ] BuildForkedMessages 正确克隆父消息 + 处理悬空 tool_use + 追加 Boilerplate(验证:`go test ./internal/agent/ -run TestFork`)
- [ ] IsForkContext 能识别消息中含 `<fork_boilerplate>` 标签(验证:对应测试通过)
- [ ] Agent.RunToCompletion 能跑完一轮非交互循环,返回最后一条 assistant 文本(验证:`go test ./internal/agent/ -run TestRunToCompletion -v`)
- [ ] RunToCompletion 触达 maxTurns 时返回错误(验证:对应测试通过)
- [ ] dontAsk 模式下,工具 Ask 决策被自动转 Allow(验证:对应测试通过)
- [ ] approvalUpgrader 回调在 Ask 决策时被命中(验证:对应测试通过)
- [ ] RunToCompletion 把 events 转发到外部 channel,Tool/Text/Approval 事件可被消费(验证:对应测试通过)

### Agent 工具

- [ ] NewAgentTool 构造的工具 Name()="Agent",Parameters() 含 prompt/description/subagent_type/model/run_in_background/name 字段(验证:`go test ./internal/agent/ -run TestAgentToolBasic`)
- [ ] AgentTool.Execute 缺少 prompt 时返回错误(验证:对应测试通过)
- [ ] AgentTool.Execute 未知 subagent_type 时返回错误(验证:对应测试通过)
- [ ] AgentTool.Execute 定义式 subagent 调用走前台 RunToCompletion,返回 finalText(验证:对应测试通过)
- [ ] AgentTool.Execute run_in_background=true 时返回 `{"task_id":"...","status":"async_launched"}` JSON(验证:对应测试通过)
- [ ] AgentTool.Execute 在子 Agent context 内被再次调用时拦截(验证:嵌套阻断测试通过)
- [ ] AgentTool.Execute 检测到 conv 含 fork boilerplate 时拦截(验证:对应测试通过)
- [ ] AgentTool.Execute EnableSubAgentBackground=false 时,run_in_background=true 与 fork 路径报错(验证:对应测试通过)

### task 包

- [ ] task.Manager 的 Launch 起 goroutine 跑 RunToCompletion,跑完写 status=Completed,push done(验证:`go test ./internal/task/ -run TestLaunch -v`)
- [ ] task.Manager.Launch goroutine 内 panic 时,status=Failed,Err 含 panic 信息,主程序不崩(验证:对应测试通过)
- [ ] task.Manager.Stop 触发 task.Cancel,goroutine 退出后 status=Cancelled(验证:对应测试通过)
- [ ] task.Manager.SendMessage 在已 completed 的任务上重新跑动,新 user 消息追加到 Conv(验证:对应测试通过)
- [ ] task.Manager.byName 后启动覆盖前,Get(byName[name]) 返回最新 task(验证:对应测试通过)
- [ ] SubscribeDone() 返回的 channel 在 task 完成时收到 id(验证:对应测试通过)

### 4 个 task 工具

- [ ] TaskList 工具返回当前所有任务的 JSON 列表(验证:`go test ./internal/task/ -run TestTaskListTool`)
- [ ] TaskGet 工具返回指定任务的完整字段;未知 id 返回 IsError=true(验证:对应测试通过)
- [ ] TaskStop 工具调用 Manager.Stop,返回成功 JSON(验证:对应测试通过)
- [ ] SendMessage 工具调用 Manager.SendMessage,返回 resumed JSON(验证:对应测试通过)
- [ ] 4 个工具都实现 SystemTool 接口,IsSystem()=true(验证:工具列表过滤时它们对子 Agent 仍可见 - 实际上 ASYNC 白名单优先,在后台子 Agent 中**仍然不可见**;对前台定义式子 Agent 通过 ALL_AGENT_DISALLOWED 不在其中)

### TUI 集成

- [ ] tui.Model 持有 taskMgr 与 subAgentCatalog 字段(验证:`go build ./internal/tui/...`)
- [ ] Init() 启动 consumeTaskDone goroutine,任务完成时把 `<task-notification>` 注入 runtime.PendingReminders(验证:`go test ./internal/tui/ -run TestConsumeTaskDone`)
- [ ] tui/skill_fork.go 改造为调 agent.RunToCompletion 而非自己拼装循环(验证:现有 skills 测试不破)
- [ ] main.go 注册 4 个 task 工具 + 1 个 Agent 工具,subagentCatalog 与 taskMgr 传给 tui.New(验证:`go build ./...`)
- [ ] config.Config 新增 EnableSubAgentBackground 字段(验证:`go build ./internal/config/...`)

## 集成

- [ ] subagent.Catalog 与 tool.ApplyAgentToolFilter 协同工作:Resolve 拿到 def,过滤函数按 def.Source/Background/Tools/DisallowedTools 收窄(验证:agent_tool_integration_test 通过)
- [ ] Agent 工具的前台调用与现有 ch11 Skill fork 路径不互相干扰(验证:skills 包测试通过 + 手动 tmux 验证一个 inline skill 与一个 Agent 工具调用)
- [ ] Hook 引擎在子 Agent 内仍生效(PreToolUse / PostToolUse 在 RunToCompletion 内被调用)(验证:hook 包测试 + 子 Agent 跑动手动断言 hook 触发)
- [ ] 主 Agent 工具列表里仍含 Agent + TaskList + TaskGet + TaskStop + SendMessage 共 5 个新工具,数量稳定(验证:工具数计数测试)

## 编译与测试

- [ ] 项目编译无错误:`go build ./...`
- [ ] 所有单元测试通过:`go test ./...`
- [ ] vet 检查通过:`go vet ./...`

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

### 场景 1:定义式子 Agent(Explore)前台同步**预置:** 无须额外配置。当前目录 `cd /Users/codemelo/gcode`。

**步骤:**
- [ ] tmux 启动 gcode:`tmux new-session -d -s ch13 -x 200 -y 50 "./gcode"`
- [ ] 给 LLM 输入:「用 Explore 子 Agent 找出 internal/permission 包下所有以 Test 开头的函数,只统计数量,不要修改任何文件」
- [ ] LLM 应触发 Agent 工具,subagent_type="Explore",run_in_background 未设
- [ ] scrollback 内出现 `● Agent(...)` 工具行,几秒后 Result 行展示子 Agent 的最终文本(含 Test* 函数数量)
- [ ] tmux 抓屏(`tmux capture-pane -p -t ch13`)断言:输出包含 `Agent(` 工具行 + 数量数字
- [ ] 验证不改文件:`git status` 干净

### 场景 2:Fork 子 Agent 后台执行**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮:让 LLM 读一些文件铺垫上下文,如「读 internal/agent/agent.go 头 50 行」
- [ ] 第二轮:「Fork 出去一个子 Agent,统计这个项目里 Go 文件总行数(不指定 subagent_type)」
- [ ] LLM 应触发 Agent 工具,subagent_type 留空 → Fork 路径
- [ ] tool_result 应立即返回 `{"task_id":"task_xxx","status":"async_launched"}`
- [ ] 主对话立刻可以继续(输入 `/status` 应能响应)
- [ ] 等 10-30 秒,主对话下一次响应时 reminder 区出现 `<task-notification>` 块,含 Result(行数统计)
- [ ] 用 LLM 验证:「主 Agent,你刚刚有没有收到 task-notification?显示一下」

### 场景 3:主 Agent 用 TaskList / TaskGet 查询**预置:** 接场景 2 之后,或者重启 gcode 后先 Launch 一个长跑任务。

**步骤:**
- [ ] 调用一个会跑较久的子 Agent:「用 run_in_background=true,让一个 general-purpose 子 Agent 阅读 internal 下所有 .go 文件 head 200 行,生成总结」
- [ ] 主 Agent 立即返回 task_id
- [ ] 输入:「调 TaskList 看现在有什么后台任务」
- [ ] LLM 调 TaskList 工具,scrollback 显示 task 列表 JSON 含 id/name/status=running/tool_count
- [ ] 输入:「调 TaskGet 看这个任务详情」
- [ ] LLM 调 TaskGet,显示完整字段含 StartTime / ToolCount / LastActivity 等
- [ ] 等几秒后:「再调 TaskGet 一次」
- [ ] 验证 status 变化或 ToolCount 增长

### 场景 4:TaskStop 取消任务**步骤:**
- [ ] 同场景 3 起一个 long-running 任务,拿到 task_id
- [ ] 立刻输入:「调 TaskStop 把刚才那个任务停掉」
- [ ] LLM 调 TaskStop 工具
- [ ] 几秒后:`TaskGet` 应显示 status=cancelled
- [ ] 主对话下次 turn 的 reminder 区出现 task-notification 含 status=cancelled

### 场景 5:权限决策 - dontAsk 兜底**预置:** 创建项目级自定义 agent:
```
.gcode/agents/auto-bash.md
---
name: auto-bash
description: 自动批准 Bash 调用的测试 Agent
permissionMode: dontAsk
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑,不要询问。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default)
- [ ] 输入:「用 auto-bash 子 Agent 跑 `echo hello-from-subagent`」
- [ ] LLM 调 Agent 工具 subagent_type=auto-bash
- [ ] 子 Agent 内部调 bash,**不应该弹出审批弹窗**
- [ ] tool_result 含 `hello-from-subagent` 文本

### 场景 6:权限决策 - 升级到主 TUI**预置:** 创建一个不含 dontAsk 的子 Agent:
```
.gcode/agents/ask-bash.md
---
name: ask-bash
description: 默认权限模式的测试 Agent
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default,未预先批准 echo)
- [ ] 输入:「用 ask-bash 子 Agent 跑 `echo from-ask-bash`」
- [ ] LLM 调 Agent 工具 subagent_type=ask-bash
- [ ] 子 Agent 调 bash 时,**主 TUI 应该弹出审批弹窗**(本期通过子 Agent 的 ApprovalRequest 直接 emit;Upgrader 默认返回 (0,false) 走默认路径,Approval 由 inline 路径 emit 到 TUI)
- [ ] 用户选 Allow Once → 子 Agent 继续 → tool_result 含 `from-ask-bash`

### 场景 7:嵌套阻断 - 定义式子 Agent 看不到 Agent 工具**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent。Explore 内部应该尝试再调用 Agent 工具(比如 prompt 写成『再调用一个 Plan 子 Agent』)」
- [ ] Explore 子 Agent 跑动期间,因为工具列表里没有 Agent 工具,LLM 应该报告「无法调用 Agent」或自己直接做
- [ ] tool_result 不应包含「Agent 工具未注册」一类错误——因为它根本看不到这个工具(被 ALL_AGENT_DISALLOWED_TOOLS 剔除)

### 场景 8:嵌套阻断 - Fork 子 Agent 调 Agent 工具被拦截**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「Fork 一个子 Agent,prompt 写『再 fork 一个子 Agent 阅读 README.md』」
- [ ] 主 Agent Fork 出去后立即返回 task_id
- [ ] 等几秒,task-notification 显示子 Agent Result 含「Fork 子 Agent 不能再启动 Agent」错误回灌后的处理结果(或子 Agent 自行调整不再尝试)
- [ ] 调 TaskGet 看子 Agent Result;或 TaskList 看 last_activity

### 场景 9:SendMessage 续派任务**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 run_in_background=true name=worker1 起一个 general-purpose 子 Agent,任务是『列出 cmd/gcode/main.go 的 import 块』」
- [ ] 主 Agent 收到 task_id,等几秒后 task-notification 显示 Result(imports 列表)
- [ ] 输入:「调 SendMessage 给 worker1 发『再列出 internal/agent/agent.go 头 20 行』」
- [ ] LLM 调 SendMessage 工具,manager.SendMessage 重新激活 worker1
- [ ] 等几秒后,task-notification 又显示新 Result(头 20 行)

### 场景 10:超时自动切后台**预置:** 临时把 autoBackgroundDuration 改成 5 秒(代码常量调小做测试,或加配置项)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 general-purpose 子 Agent,任务是『等 30 秒,然后回复 hello』(让子 Agent 用 bash sleep 30 触发长跑)」
- [ ] Agent 工具前台等 5 秒后超时,tool_result 返回 `{"task_id":"...","status":"timed_out_to_background"}`
- [ ] 主对话可以继续接收输入
- [ ] 等够 30 秒后,task-notification 注入主对话含 hello

> 测试完恢复 autoBackgroundDuration=120s

### 场景 11.5:全新自定义子 Agent 端到端

> 验证项目级自定义 Agent 文件被加载、Resolve 命中、frontmatter 全字段生效、SystemPrompt 注入到子 Agent。
> 与场景 5/6/11 区别:那三条聚焦权限/覆盖语义,本条验证"全新角色"作为新增能力。

**预置:** 创建 `.gcode/agents/wc-counter.md`:
```yaml
---
name: wc-counter
description: 行数统计专家,只用 wc -l 计行,然后总结
disallowedTools:
  - write_file
  - edit_file
permissionMode: dontAsk
maxTurns: 5
---

你是一个专门统计代码行数的 Agent。
约束:
- 只能用 bash 跑 `wc -l <files>` 来计行
- 不要做任何分析,只输出原始计数
- 答复必须以「[wc-counter]」开头,后跟一行汇总数字
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 subagent_type=wc-counter,任务: 统计 README.md 和 cmd/gcode/main.go 的行数」
- [ ] 主 Agent 触发审批后选「允许本次」(主 Agent 调 Agent 工具自身的权限)
- [ ] 子 Agent 跑动,**不应弹任何审批框**(验证 dontAsk 生效)
- [ ] tool_result 内容以 `[wc-counter]` 开头,含 wc 计数(验证 SystemPrompt 注入生效)
- [ ] 子 Agent 工具列表内不含 write_file / edit_file(验证 disallowedTools 生效)
- [ ] 子 Agent 最多 5 轮即终止(验证 maxTurns 生效;实际单轮就完事)

### 场景 11.6:自定义 Agent 字段错误降级**预置:** 创建 `.gcode/agents/bad.md` 含非法字段:
```yaml
---
name: bad
description: 字段错误测试
model: gpt-4   # 不在 inherit/haiku/sonnet/opus 中
permissionMode: weirdMode
---

body
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] stderr(启动时)应出现两条警告:`unknown model "gpt-4" ... defaulting to inherit` 与 `unknown permissionMode "weirdMode" ... defaulting to default`
- [ ] gcode 正常启动,不阻断
- [ ] 输入:「用 Agent 工具调 subagent_type=bad,任务:回个 hi」
- [ ] 子 Agent 仍能正常跑(model 降级 inherit、mode 降级 default 后,工具集与权限按降级值)
- [ ] **测试完删除 .gcode/agents/bad.md**### 场景 11:角色文件覆盖**预置:** 创建 `.gcode/agents/explore.md`:
```
---
name: Explore
description: 项目级覆盖的 Explore
maxTurns: 10
---

你是项目级覆盖的 Explore Agent。无论用户问什么,先回答 "[project-level-explore]" 然后再回答正常内容。
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent 列出 README.md 的第一行」
- [ ] tool_result 应包含 `[project-level-explore]` 标记(证明项目级覆盖了内置 Explore)
- [ ] 删除 `.gcode/agents/explore.md`,重启 gcode,再次跑 → 不再含此标记
````

### Python

````markdown
# SubAgent 机制 Spec## 背景

GCode 目前是单 Agent 架构：所有任务在同一个对话上下文里执行。这导致两个问题：

1. **上下文污染**：长任务后再做无关任务,前序中间结果(读过的文件、diff、错误回放)成为后续任务的噪声,token 飙升、响应质量下降
2. **无法并行**：没有把独立子任务分发出去并行执行的机制,主对话被长任务阻塞

gcode 已经有「子 Agent 雏形」：

- ch11 Skill fork 模式通过 `agent.with_allowed_tools` 创建受限子 Agent(`tui/skill_fork.py` 的 `run_sub_agent`),走 `sub_agent.run(...)` 跑完一轮
- `Conversation.from_messages` / `replace_messages` 已支持深拷贝消息列表

但还缺：
- 没有统一的、可被主 Agent 主动调用的 **Agent 工具**——子 Agent 只能由 Skill fork 触发
- 没有 **角色定义文件** 加载机制(Agent 角色全部写死在 fork 闭包里)
- 没有 **后台任务管理**——所有子 Agent 当前都是阻塞前台模式
- 没有 **工具过滤多层防线**——子 Agent 理论上可以无限嵌套
- Skill fork 与未来 SubAgent 工具两套代码并存

本章把上述能力补齐,让 gcode 从单 Agent 进化到可分发任务的主从架构。

## 目标- **G1**:提供统一的 Agent 工具,主 Agent 通过 `subagent_type` 参数选择预定义角色或留空走 Fork 路径;工具列表对模型始终稳定(不因角色定义增减而变化)
- **G2**:子 Agent 拥有独立的运行时状态——**消息**、**权限账本**(独立 Engine 决策状态)、**文件读缓存**、**token 计数**;共享基础设施——LLM 客户端、Hook 引擎、文件系统、`tool.Registry`
- **G3**:支持两种创建模式:
  - **定义式**:指定 `subagent_type`,从空白对话 + 预定义角色 prompt 启动
  - **Fork 式**:不指定 `subagent_type`,克隆父对话历史并注入 Fork Boilerplate,借 prompt cache 降首次请求成本
- **G4**:角色定义为 Markdown + YAML frontmatter 文件;支持多来源加载,优先级:项目级 > 用户级 > 内置 > 插件;同名定义按 source 优先级覆盖,前者覆盖后者
- **G5**:子 Agent 以 **RunToCompletion** 模式执行——任务直接注入对话,模型不再调工具即结束,返回最后一条 assistant 文本作为结果
- **G6**:子 Agent 在工具调用时遇到权限判定,按 **三层升级链** 处理:① 父对话已批准账本 → ② 角色 frontmatter 的 `permission_mode` 兜底 → ③ 仍无法决定时升级到主 TUI 询问用户(子 Agent 暂停、用户响应、子继续)
- **G7**:支持后台任务:三种进入方式——① 显式 `run_in_background:true`、② 前台超时 120 秒自动切后台、③ ESC 手动切后台;Fork 路径无条件后台;Fork Boilerplate 注入到子 Agent 首条消息约束其行为
- **G8**:后台任务跑完通过 `<task-notification>` 自动注入主对话(主 Agent 下次 turn 即看到);主 Agent 可通过 `TaskList`/`TaskGet`/`TaskStop` 工具主动查询和操控,可通过 `SendMessage` 给已跑完的、仍存活的后台 Agent 续派任务
- **G9**:工具过滤多层防线阻断子 Agent 无限嵌套——全局禁止列表(子 Agent 永远不能用 Agent 工具)、后台白名单(后台 Agent 只能用基础读写网络工具)、定义层 `tools`/`disallowed_tools` 业务约束
- **G10**:复用 SubAgent 底座统一 Skill fork 路径——`tui/skill_fork.py` 的 `run_sub_agent` 改为调用 SubAgent 公共启动函数,两条路径走同一段 agent 构造逻辑
- **G11**:内置 3 个角色——`general-purpose`(全工具)、`Explore`(只读探索,haiku)、`Plan`(只读规划);插件级保留接口占位但本期不实现真插件加载,加载顺序里插件来源恒为空

## 功能需求### Agent 工具- **F1**:新建 `Agent` 工具,参数(JSON Schema):
  - `prompt`(string,必填):交给子 Agent 的任务指令
  - `description`(string,必填):一句话描述任务,供 UI 展示
  - `subagent_type`(string,可选):指定预定义角色名,留空时走 Fork 路径
  - `model`(string,可选):模型覆盖,取值 `haiku` / `sonnet` / `opus` / `inherit`;留空沿用 Agent 定义的 model
  - `run_in_background`(bool,可选):true 时强制后台启动;Fork 路径忽略此字段(无条件后台)
  - `name`(string,可选):给本次启动的子 Agent 命名,供 SendMessage 用;同名后启动的覆盖前面的弱引用
- **F2**:Agent 工具的 `execute`:
  - subagent_type 非空:`catalog.resolve(name)` 取定义;不存在则返回结构化错误「未知 subagent_type: X」
  - subagent_type 为空:走 Fork 路径,从 `catalog` 取「fork 默认基础定义」(prompt body=Fork Boilerplate)
  - 按 `run_in_background` 与 Fork 强制规则,选择 inline 跑(阻塞返回 final_text)或 background 跑(返回 `{task_id, status:"async_launched"}`)
- **F3**:Agent 工具被全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS` 标记——任何子 Agent 都看不到 Agent 工具,从根源上断绝嵌套

### Agent 定义文件- **F4**:Agent 定义文件是 Markdown,以 `---` frontmatter 块开头、紧跟正文(子 Agent 系统提示);frontmatter YAML 字段:
  - `name`(必填):角色名,小写字母 / 数字 / 连字符,长度 1-32
  - `description`(必填):一句话描述,用于 Agent 工具的 `subagent_type` 文档与 UI 列表
  - `tools`(可选,list[str]):工具白名单
  - `disallowedTools`(可选,list[str]):工具黑名单
  - `model`(可选):`haiku` / `sonnet` / `opus` / `inherit`,缺省 `inherit`
  - `maxTurns`(可选,int):最大迭代轮数,缺省继承全局 `max_iterations=25`
  - `permissionMode`(可选):`default` / `acceptEdits` / `plan` / `bypassPermissions` / `dontAsk`,缺省 `default`;`dontAsk` 是子 Agent 专属——自动批准所有规则未命中的工具
  - `background`(可选,bool):缺省 false;true 时 Agent 工具忽略 `run_in_background` 参数、强制后台
- **F5**:Catalog 三层加载(本期插件级恒为空),顺序:
  1. 项目级:`<root>/.gcode/agents/*.md`
  2. 用户级:`~/.gcode/agents/*.md`
  3. 内置级:随包发布的 `gcode/subagent/builtin/*.md`(通过 `importlib.resources` 读取)
- **F6**:同名定义按 source 优先级覆盖——项目级 > 用户级 > 内置级;`resolve(name)` 返回优先级最高的版本
- **F7**:Catalog 启动期加载,加载失败的单个文件(frontmatter 不合法、name 重名以外的字段错)走 stderr 警告并跳过,不阻断启动
- **F8**:本章不引入插件加载器——`SourcePlugin` 常量保留供未来扩展;加载顺序里第四层恒为空列表

### 子 Agent 运行时- **F9**:扩展 `agent.Agent` 增加 `async def run_to_completion(self, conv, task) -> str` 方法:
  - 把 `task` 作为 user 消息追加到 conv
  - 进入 ReAct 循环,max_turns 由 `Agent.max_turns` 决定(子 Agent 用 frontmatter,主 Agent 不变=25)
  - 模型不再调工具时结束循环,取末尾 assistant 文本返回
  - 触达 max_turns 时返回最后一条 assistant 文本 + 抛 `MaxTurnsReached` 错误
  - 同一段循环代码与主对话 `run` 共用,不重复实现
- **F10**:新增 Agent 构造选项(通过 `Agent.__init__` 关键字参数 / `dataclass` 字段):
  - `system_prompt: str`:子 Agent 启动时把 text 作为 system prompt 注入(覆盖默认 gcode 主 Agent 系统提示)
  - `provider: Provider`:让子 Agent 用与父不同的 provider(model 覆盖时切换)
  - `max_turns: int`:限制本 Agent 的最大迭代轮数
  - `permission_mode: PermissionMode`:子 Agent 启动模式
  - `parent_engine: PermissionEngine`:子用父 Engine 做权限决策一级查找(本期所有 Agent 共享同一 Engine,但增加显式参数预留隔离扩展)
- **F11**:子 Agent 的运行时状态隔离——独立 `SessionRuntime`、独立 `Conversation`、独立 token 计数;但共享 `Provider`(除非 `provider` 覆盖)、`Registry`、`PermissionEngine`、`HookEngine`

### 权限决策- **F12**:子 Agent 工具调用权限决策三层链(在 `_run_guarded` 内分支):
  1. 父对话已批准账本——父 Engine 已经 `persist_local_allow` 过的精确规则匹配 → Allow
  2. 子角色 `permission_mode` 兜底——`dontAsk` 模式直接放行所有 Allow/Ask 类规则未命中的;`acceptEdits` 放行写;`bypassPermissions` 全 Allow(黑名单/沙箱仍拦);其他模式仍走原 `mode_fallback`
  3. 三层之外仍是 Ask——升级到主 TUI:子 Agent 暂停,主 TUI 弹审批框(标注 `[来自 SubAgent X]`),用户响应后子 Agent 继续;Outcome 沿用现有三选一(DenyOnce/AllowOnce/AllowForever)
- **F13**:升级到主 TUI 的通信机制——子 Agent 把 `ApprovalRequest` 推到自己的事件队列(`asyncio.Queue`),队列被 TaskManager / SkillFork host 转发到主 TUI 的 Approval 弹窗;主 TUI 响应后 Outcome 通过 `respond` `asyncio.Future` 回传

### 后台任务管理- **F14**:新建 `task.Manager`,持有 `dict[str, BackgroundTask]`,提供 `launch(ctx, agent, task_text)`、`get(id)`、`list()`、`stop(id)`、`adopt_running(...)`、`subscribe_done() -> asyncio.Queue[str]`
- **F15**:`BackgroundTask` 字段:
  - `id`(str,manager 生成)
  - `name`(str,可选,F1 的 `name` 字段)
  - `sub_agent`(Agent)
  - `conv`(Conversation,子对话)
  - `task`(str,初始任务)
  - `status`(`running` / `completed` / `failed` / `cancelled`)
  - `result`(str,跑完后填)
  - `err`(BaseException | None)
  - `start_time` / `end_time`
  - `cancel`(`asyncio.Event` 或 `asyncio.Task.cancel`)
  - `usage`(`TokenUsage`,token 计数)
  - `tool_count`(int,工具调用次数计数器)
  - `last_activity`(str,最近一次工具名)
- **F16**:`launch` 内部 `asyncio.create_task`:`sub_agent.run_to_completion(conv, task)` → status 终态 → 推 `task_id` 到 `done` 队列 → TUI 消费后注入 `<task-notification>`
- **F17**:三种进入后台的方式:
  1. **显式**:Agent 工具 `run_in_background:true` → 直接调 `launch`,工具 result 立刻返回 `{task_id, status:"async_launched"}`
  2. **超时自动**:Agent 工具默认前台 inline 跑,但前台 run 启动后开计时器(120 秒,常量 `AUTO_BACKGROUND_MS`),超时则:
     - 取消前台事件消费协程
     - 调 `manager.adopt_running(agent, conv, task_handle, cancel_event, events, partial)` 接管事件流继续后台跑
     - Agent 工具 result 改返回 `{task_id, status:"timed_out_to_background"}`
  3. **ESC 手动切**:用户在前台子 Agent 跑动期间按 ESC → TUI 调 `manager.adopt_running(...)`,与超时路径走同一逻辑
- **F18**:Fork 路径 `run_in_background` 字段被强制视为 true(代码内 override)
- **F19**:后台任务完成时,Manager 把 `task_id` push 到 `done` 队列;TUI 在主事件循环消费,把如下文本作为 system reminder 拼到主对话下一次 reminder 区(不打断当前对话):
  ```
  <task-notification>
  Task X (name="Y"): completed
  Result: <最终文本>
  </task-notification>
  ```

### 后台任务工具- **F20**:新增 4 个内置工具:
  - `TaskList`:无参,返回当前 manager 中所有非 Terminated 任务的简要列表(id、name、status、tool_count、last_activity)
  - `TaskGet`:`{task_id}`,返回指定任务的完整状态(含 result / err)
  - `TaskStop`:`{task_id}`,调 `manager.stop` 触发取消;返回 `{status:"cancellation_requested"}`
  - `SendMessage`:`{name, message}`,按 name 找到仍存活的后台 Agent(status=completed,conv 仍在内存),把 message 作为新 user 消息追加到 conv 并重新 `launch` 一轮跑动;找不到 / 已 cancelled 返回错误
- **F21**:本期不实现 `TaskCreate`(主要给 Hook 用,Hook 暂未需要 SubAgent action);保留 manager API,Hook subagent stub 也可暂未对接

### Fork 路径- **F22**:`build_forked_messages(parent_conv)` 做三件事:
  1. 深拷贝 parent_conv 的全部消息
  2. 把末尾 assistant 中未完成的 `tool_use`(无对应 ToolResult)包装为 placeholder ToolResult,使消息格式合法
  3. 在末尾追加 user 消息,内容 = Fork Boilerplate + 任务文本
- **F23**:Fork Boilerplate 是一段 `<fork_boilerplate>` 包裹的指令,核心约束:
  - 不能再 Fork(再 Fork 会被 QuerySource 拦截 / Boilerplate 标记扫描兜底)
  - 不要对话 / 提问 / 请求确认
  - 直接使用工具
  - 严格限制在分配的任务范围内
  - 最终报告以 `Scope:` 开头,500 字以内
- **F24**:Fork 子 Agent 嵌套阻断三道闸:
  1. **工具列表层**:Fork 子 Agent 的工具列表保留 Agent 工具(继承自父),但调用 Agent 工具时
  2. **QuerySource 检测**:Agent 工具入口检测 caller 来源(检查父链),若 caller 是 Fork 路径产生,直接 `is_error=True` 返回「Fork 子 Agent 不能再启动 Agent」
  3. **Boilerplate 标记扫描**:对话历史里如果含 `<fork_boilerplate>` 标记(QuerySource 失效兜底),也认定是 Fork 嵌套
- **F25**:定义式子 Agent 不走 Boilerplate(从空白启动);嵌套阻断靠 `ALL_AGENT_DISALLOWED_TOOLS` 全局禁止 Agent 工具

### 工具过滤多层防线- **F26**:全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS = ["Agent"]`(本期范围最小,后续可加 AskUserQuestion / TaskStop);所有子 Agent 启动时从工具列表中剔除这些
- **F27**:自定义 Agent 额外限制 `CUSTOM_AGENT_DISALLOWED_TOOLS`:本期为空,接口预留(用于将来用户自定义 Agent 一律不可访问某些核心工具)
- **F28**:后台 Agent 白名单 `ASYNC_AGENT_ALLOWED_TOOLS`,只列基础工具:
  `read_file, write_file, edit_file, glob, grep, bash, load_skill, install_skill`
  以及所有 MCP / Skill 工具。Fork/run_in_background 任意一种成立的子 Agent 工具集再叠加此白名单交集。
- **F29**:Agent 定义层 `tools`(白名单)与 `disallowed_tools`(黑名单)组合应用——白名单先确定范围,黑名单再排除
- **F30**:工具过滤合并执行顺序(在 Agent 工具的 `execute` 内,子 Agent 构造时):
  1. 起点 = registry 的全部工具
  2. 去掉 `ALL_AGENT_DISALLOWED_TOOLS`
  3. 如果是后台 → 取交集 `ASYNC_AGENT_ALLOWED_TOOLS`
  4. 应用定义的 `disallowed_tools` 黑名单
  5. 应用定义的 `tools` 白名单(空白名单 = 不再收窄)
  6. 注入到子 Agent 的 `Agent(allowed_tools=allowed)`
- **F31**:工具列表对模型稳定——以上过滤只发生在子 Agent 构造时,主 Agent 看到的工具列表不变

### 内置角色与 Skill fork 改造- **F32**:内置 3 个角色文件,随包发布:
  - `general-purpose.md`:无 disallowedTools,用 `inherit` 模型,maxTurns=30,permissionMode=default
  - `explore.md`:disallowedTools=[write_file, edit_file],model=haiku,maxTurns=30,permissionMode=default
  - `plan.md`:disallowedTools=[Agent, write_file, edit_file],maxTurns=15,permissionMode=plan(plan 是已有的权限模式)
- **F33**:Skill fork 改造——`tui/skill_fork.py` 的 `run_sub_agent` 改为:
  1. 构造一个临时 `subagent.Definition`(name="skill-fork-<skillname>",disallowed_tools=skill.allowed_tools 反推 / 等同 skill 自身的 allowed_tools),将其当 Fork 路径走
  2. 复用 `agent.run_to_completion` 与 SubAgent 的工具过滤、消息装填路径
  3. 返回 `final_text` 行为不变(`host.append_assistant_message` 仍由 Executor 调)

## 非功能需求- **N1**:工具列表稳定——主 Agent 看到的工具集不因 `.gcode/agents/` 增减或 Agent 工具被调用而变化(防止 prompt cache 抖动)
- **N2**:Fork 路径首次请求命中 prompt cache——`build_forked_messages` 拼接的消息列表与父对话末尾完全一致,系统提示一致
- **N3**:子 Agent 崩溃不影响主程序——`manager.launch` 的协程包 `try/except BaseException`,任何异常转 `status=failed` + 错误信息回灌
- **N4**:启动期 fail-fast——内置定义解析失败立刻 raise(代码 bug),用户/项目级定义文件解析失败仅 stderr 警告并跳过
- **N5**:与现有 ch11 Skill 系统、ch12 Hook 系统、ch08 权限系统、ch04 主 Agent loop 协同,不破坏既有测试
- **N6**:配置 `enable_subagent_background`(bool,默认 true)关闭后,Agent 工具的 `run_in_background:true` / 超时切后台 / ESC 切后台全部失效,所有 SubAgent 强制前台同步;Fork 路径在此模式下报错「后台禁用,无法 Fork」
- **N7**:`<task-notification>` 注入主对话不消耗主 Agent 的工具调用配额,不出现在用户视窗(只对模型可见)

## 不做的事

- Worktree 文件隔离(独立章节)
- 多 Agent 团队编排(CrewAI / AutoGen 平等协作风格)
- 后台任务跨会话持久化——主程序退出后任务全部丢失
- 真正的插件系统(`SourcePlugin` 占位)
- 子 Agent 输出 schema 强制结构化(返回纯文本即可)
- Verification Agent 内置开关(`enable_verification_agent` 不实现)
- `TaskCreate` 工具(本期仅 List/Get/Stop/SendMessage)
- 跨 SubAgent token 用量汇总到 /status(只在 Manager 内部记录)

## 验收标准- **AC1**:Agent 工具注册成功,主 Agent 的工具列表里 schema 一致;子 Agent 看不到 Agent 工具
- **AC2**:`Agent` 工具调用 `{prompt:"...",subagent_type:"Explore"}` 时,主 Agent 看到的 tool_result 是 Explore 子 Agent 的最后一条 assistant 文本
- **AC3**:`Agent` 工具调用 `{prompt:"...",subagent_type:"non-existent"}` 时,主 Agent 看到的 tool_result 是结构化错误「未知 subagent_type」
- **AC4**:`Agent` 工具调用不传 subagent_type 时,子 Agent 收到的首条 user 消息以 `<fork_boilerplate>` 起头,且消息列表前缀与父对话一致(可由测试断言)
- **AC5**:Fork 子 Agent 的工具列表里仍有 Agent 工具(F22 设计),但调用 Agent 工具会被 QuerySource 拦截,tool_result 含「Fork 子 Agent 不能再启动 Agent」
- **AC6**:定义式子 Agent 的工具列表里没有 Agent 工具(被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除)
- **AC7**:子 Agent 角色 frontmatter 写 `permissionMode: dontAsk`,bash 等需要 Ask 的工具直接放行,无审批弹窗
- **AC8**:子 Agent 角色 frontmatter 不写 dontAsk,bash 工具触发审批,弹窗带 `[来自 SubAgent X]` 标识
- **AC9**:`run_in_background:true` 时 tool_result 立即返回 `{task_id, status:"async_launched"}`,主 Agent 不阻塞
- **AC10**:前台子 Agent 跑超过 120 秒,自动切后台,主 Agent 看到 tool_result 含 `status:"timed_out_to_background"`
- **AC11**:前台子 Agent 跑动期间用户按 ESC,切到后台,TUI 继续接收主 Agent 输入
- **AC12**:后台子 Agent 跑完,主 Agent 下次 run 的 reminder 区出现 `<task-notification>` 块,含 Result
- **AC13**:`TaskList` 工具返回当前后台任务列表,字段含 id/name/status/tool_count
- **AC14**:`TaskGet({task_id})` 返回 Result;`TaskStop({task_id})` 触发取消,任务 status 变 cancelled
- **AC15**:`SendMessage({name,message})` 让一个仍存活的后台 Agent 接到新任务并重新跑动,跑完结果作为新 `<task-notification>` 注入主对话
- **AC16**:项目级 `.gcode/agents/explore.md` 覆盖内置 `explore`,`resolve("explore")` 返回项目级版本
- **AC17**:Skill fork 模式调用走 SubAgent 底座——`tui/skill_fork.py` 的 `run_sub_agent` 内部只是装饰参数后调 `subagent.launch_fork(...)`(或同等公共函数)
- **AC18**:N6 配置开关 `enable_subagent_background:false` 时,Fork 路径调用 Agent 工具返回结构化错误
- **AC19**:`<fork_boilerplate>` 出现在对话历史里 + Agent 工具被调用 → 拦截(QuerySource 失效兜底)
- **AC20**:子 Agent 异常 → status=failed,主 Agent 收到 `<task-notification>` 含错误描述,主程序不崩
- **AC21**:全新项目级自定义 Agent(`.gcode/agents/<name>.md`)被 Catalog 加载;`subagent_type=<name>` 调用时,frontmatter 的 disallowedTools / permissionMode / maxTurns / SystemPrompt 全部生效——子 Agent 看不到黑名单工具、按指定 mode 决策、不超 turns、按 SystemPrompt 行事
- **AC22**:Agent 定义 frontmatter 的非法字段(unknown model / unknown permissionMode)在加载时 stderr 警告并 fallback 到默认值(model→inherit, mode→default),gcode 不阻断启动,该 Agent 仍可被 resolve 与调用
````

````markdown
# SubAgent 机制 Plan## 技术栈
- 语言：Python 3.12+
- TUI：Textual（async-first 的 TUI 框架）+ Rich(继承 ch02 起的现状)
- 配置：YAML 解析（`pyyaml`，import 名 `yaml`）
- LLM 通信：官方 Python SDK —— `anthropic`（`AsyncAnthropic`）、`openai`（`AsyncOpenAI`）
- 并发模型:asyncio + `asyncio.create_task` / `asyncio.Queue` / `asyncio.CancelledError`
- 工具调用与权限引擎沿用 ch04~ch12 既有的 `gcode.agent` / `gcode.permission` / `gcode.hook` 模块

## 架构概览

本章实现拆为四个层次：

1. **subagent 包**（新增,核心数据层）——定义 Agent 角色的数据结构、Markdown+YAML 解析、Catalog 多来源加载、内置角色随包发布
2. **task 包**（新增,后台运行层）——`task.Manager` 管理后台任务生命周期,4 个内置工具(TaskList / TaskGet / TaskStop / SendMessage)
3. **agent 包扩展**——新增 `run_to_completion` 方法、6 个新构造参数、Fork 路径辅助函数 `build_forked_messages`、子 Agent 权限升级回调
4. **工具与 TUI 集成层**——Agent 工具实现、工具过滤多层防线常量、TUI 接入 task notification、ESC 切后台、Skill fork 改造为复用 SubAgent 底座

模块构成：

- `subagent.Definition` / `subagent.Catalog` / `subagent.Source*` — 数据结构与三层加载
- `gcode.subagent.builtin/*.md` — 内置 3 个角色文件,`importlib.resources` 读取
- `task.Manager` / `task.BackgroundTask` — 后台任务管理与生命周期
- `task.*Tool` — 4 个内置工具,注册到 `tool.Registry`
- `agent.Agent.run_to_completion` / `system_prompt` / `provider` / `max_turns` / `permission_mode` / `approval_upgrader` — Agent 类扩展
- `agent/fork.py` — `build_forked_messages`、Fork Boilerplate 常量
- `agent/agent_tool.py` — Agent 工具实现
- `tool/filter.py` — `ALL_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 常量与过滤函数
- `tui` 改动 — TaskManager wiring、ESC 切后台、`<task-notification>` 注入、子 Agent 审批弹窗
- `tui/skill_fork.py` 改造 — 复用 `subagent.launch_fork`

## 核心数据结构### subagent.Definition

```python
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Literal

from gcode.permission import PermissionMode

class Source(IntEnum):
    BUILTIN = 0
    USER = 1
    PROJECT = 2
    PLUGIN = 3  # 占位

    def __str__(self) -> str:
        return {0: "builtin", 1: "user", 2: "project", 3: "plugin"}.get(int(self), "unknown")

@dataclass
class Definition:
    """一个 Agent 角色的完整定义,从 Markdown+YAML frontmatter 解析。"""

    name: str                              # frontmatter.name (-> agent_type)
    description: str                       # frontmatter.description (-> when_to_use)
    tools: list[str] = field(default_factory=list)             # frontmatter.tools 白名单;空表示不收窄
    disallowed_tools: list[str] = field(default_factory=list)  # frontmatter.disallowedTools 黑名单
    model: Literal["haiku", "sonnet", "opus", "inherit"] = "inherit"
    max_turns: int = 0                     # 0 表示沿用全局默认 (25)
    permission_mode: PermissionMode = PermissionMode.DEFAULT  # "dontAsk" 单独处理(见 dont_ask 字段)
    dont_ask: bool = False                 # 是否启用"绕过 Ask"的子 Agent 兜底模式
    background: bool = False               # 强制后台
    system_prompt: str = ""                # Markdown body(去 frontmatter 后的全文)
    file_path: str = ""                    # 定义文件绝对路径(用于调试)
    source: Source = Source.BUILTIN

    def is_fork(self) -> bool:
        return self.name == "__fork__"
```

### subagent.Catalog

```python
import threading

class Catalog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._defs: dict[str, Definition] = {}                    # name -> 最高优先级定义
        self._by_source: dict[Source, list[Definition]] = {}      # 各层副本(供 /agents 命令展示与 debug)

    def resolve(self, name: str) -> Definition | None: ...
    def list(self) -> list[Definition]: ...        # 按 name 排序
    def list_by_source(self, src: Source) -> list[Definition]: ...

    def fork_definition(self) -> Definition:
        """返回 Fork 路径用的临时 Definition——name="__fork__",
        system_prompt 留空(子 Agent 走继承的系统提示),
        但 disallowed_tools 不应包含 Agent 工具
        (Fork 子 Agent 工具集保留 Agent,靠 QuerySource 阻断)。
        """
        ...

def load_catalog(root: str) -> Catalog:
    """顺序加载:builtin -> user -> project,优先级高的覆盖低的;
    解析错误走 stderr 警告并跳过;返回非 None Catalog 即使无任何定义。"""
    ...
```

### task.Manager 与 BackgroundTask

```python
import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum

class Status(IntEnum):
    RUNNING = 0
    COMPLETED = 1
    FAILED = 2
    CANCELLED = 3

@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0

@dataclass
class BackgroundTask:
    """一个后台子 Agent 的完整状态快照。"""

    id: str                                # manager 生成,如 "task_<8 字节十六进制>"
    name: str                              # F1 中 Agent 工具 name 参数,可空
    sub_agent: "Agent"
    conv: "Conversation"
    task: str                              # 初始任务文本(send_message 不更新此字段)
    status: Status = Status.RUNNING
    result: str = ""                       # 跑完的最终文本
    err: BaseException | None = None
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    handle: asyncio.Task | None = None     # 跑动协程的 asyncio.Task,Stop 时调 cancel()
    usage: Usage = field(default_factory=Usage)
    tool_count: int = 0
    last_activity: str = ""

@dataclass
class PartialState:
    """前台→后台移交时已收集的中间状态。"""

    last_assistant_text: str = ""
    tool_count: int = 0
    last_activity: str = ""
    usage: Usage = field(default_factory=Usage)

class Manager:
    """管理后台任务。协程安全(单事件循环)。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[str, BackgroundTask] = {}
        self._by_name: dict[str, str] = {}              # name -> id,弱引用,后启动的覆盖
        self._done: asyncio.Queue[str] = asyncio.Queue(maxsize=32)

    async def launch(self, ag: "Agent", conv: "Conversation",
                     name: str, task: str) -> str: ...
    async def adopt_running(self, ag: "Agent", conv: "Conversation",
                            name: str, events: asyncio.Queue,
                            handle: asyncio.Task, partial: PartialState) -> str: ...
    def get(self, id: str) -> BackgroundTask | None: ...
    def list(self) -> list[BackgroundTask]: ...         # 按 start_time 升序
    async def stop(self, id: str) -> bool: ...
    def subscribe_done(self) -> asyncio.Queue[str]: ...
    async def send_message(self, name: str, message: str) -> str: ...
    # 找不到 name -> raise TaskNotFound;status != Completed -> raise TaskBusy
    # 成功时把 message 加到 conv,重新 launch 一轮跑动(选择**同 id**复用)
```

### agent 包扩展

```python
# 新增方法 ---

class Agent:
    # 新增字段 ---
    system_prompt: str | None = None        # 非空时 build_env_text / build_system_prompt 阶段用此覆盖默认
    max_turns: int = 0                      # 0 表示用全局 MAX_ITERATIONS
    permission_mode: PermissionMode | None = None
    dont_ask: bool = False
    approval_upgrader: "ApprovalUpgrader | None" = None

    async def run_to_completion(
        self,
        conv: "Conversation",
        task: str,
        events: asyncio.Queue | None = None,
    ) -> str:
        """执行子 Agent 的"跑到底"循环。

        复用主 ``run`` 的几乎所有逻辑(``_stream_once`` / ``_execute_batched`` / 权限判定),区别:
        - 不通过队列返回事件(内部消费),最终返回 final_text
        - max_turns 由 ``self.max_turns`` 决定(若 0 则用 MAX_ITERATIONS)
        - 不触发 memory update / 不触发 compact reminder 等主对话专属逻辑(子 Agent 上下文短,
          不需要;但内部依然走 ``_manage_context_auto`` 防止超长)
        - 接受一个可选的 events 队列,把内部事件(text/tool/approval)转发出去——
          TaskManager 借此聚合 tool_count / last_activity,
          TUI 借此渲染前台子 Agent 的进度
        """
        ...

# 新增类型 ---

# ApprovalUpgrader 是子 Agent 把审批请求升级到父 TUI 的回调。
# 实现方:TaskManager 把请求转发到主 TUI 的事件流;前台 inline 模式直接复用现有 Approval 路径。
ApprovalUpgrader = Callable[
    [ApprovalRequest],
    Awaitable[tuple[PermissionOutcome, bool]],
]
```

`Agent.__init__` 接受的新关键字参数:
- `system_prompt: str | None` — 非空时 build_env_text / build_system_prompt 阶段用此覆盖默认
- `max_turns: int` — 0 表示用全局 MAX_ITERATIONS
- `permission_mode: PermissionMode | None` — 子 Agent 启动模式(主 Agent 用 TUI 的运行时 mode)
- `dont_ask: bool`
- `approval_upgrader: ApprovalUpgrader | None`
- `provider: Provider | None` — 与父不同的 provider(model 覆盖时切换)

### fork.py 内容

```python
FORK_BOILERPLATE_TAG = "<fork_boilerplate>"

# Fork 子 Agent 首条 user 消息的前缀,约束其行为。
FORK_BOILERPLATE = """<fork_boilerplate>
你是一个 Fork 出来的工作进程。你不是主 Agent。
规则(不可协商):
1. 不能再 Fork(调用 Agent 工具会被拦截)。
2. 不要对话、不要提问、不要请求确认。
3. 直接使用工具:读文件、搜索代码、做修改。
4. 严格限制在你被分配的任务范围内。
5. 最终报告以 "Scope:" 开头,500 字以内。
</fork_boilerplate>

"""

def build_forked_messages(parent_msgs: list[Message], task: str) -> list[Message]:
    """把父对话克隆到 Fork 子对话,处理悬空 tool_use,追加 Boilerplate + task。

    行为:
      1. 深拷贝 parent_msgs(所有 Message + 内部 tool_calls / tool_results 列表)
      2. 扫描末尾 assistant 消息的 tool_calls,如果对应的 RoleTool 消息缺失,
         生成一条 placeholder tool_results(每个 ID 对一条"[forked, skipped]" 错误内容)
      3. 追加 user 消息 = FORK_BOILERPLATE + task

    返回新消息列表,直接用 ``Conversation.from_messages`` 装载即可。
    """
    ...

def is_fork_context(msgs: list[Message]) -> bool:
    """判定一个 conversation 的消息历史是否来自 Fork(用 FORK_BOILERPLATE_TAG 扫描)。
    QuerySource 检测的兜底机制——caller 链丢失时靠这个。
    """
    ...
```

### Agent 工具

`src/gcode/agent/agent_tool.py`:

```python
@dataclass
class AgentArgs:
    prompt: str
    description: str
    subagent_type: str = ""
    model: str = ""
    run_in_background: bool = False
    name: str = ""

class AgentTool(Tool):
    """注册到 ``tool.Registry`` 的统一 Agent 工具。"""

    def __init__(
        self,
        catalog: subagent.Catalog,
        task_mgr: task.Manager,
        parent: Agent | None,         # 取 provider / registry / engine / runtime 等
        bg_enabled: bool,             # N6 配置开关
    ) -> None: ...

    @property
    def name(self) -> str: return "Agent"

    @property
    def read_only(self) -> bool: return False  # 子 Agent 可能做任何事

    def description(self) -> str:
        """列出已知的 subagent_type 名,从 catalog.list() 渲染。"""
        ...

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        # 1. 解析 args -> AgentArgs;校验 prompt / description 非空
        # 2. 防嵌套:从 ctx 取 parent_info,若 parent 已是子 Agent 或对话历史含 fork tag -> 返回错误
        # 3. resolve 定义:subagent_type 非空走 catalog.resolve,空走 catalog.fork_definition
        # 4. 决定 background:def.background or args.run_in_background or is_fork
        # 5. 应用工具过滤多层防线 apply_agent_tool_filter,得到 allowed: list[str]
        # 6. 选 provider:args.model 非空 -> 切;否则 def.model != "inherit" -> 切;否则用 parent
        # 7. 构造子 Agent + 子 conv(空白或 Fork 路径装填消息)
        # 8. 前台路径:asyncio.wait_for(run_to_completion(...), timeout=120)
        #    - 完成 → 返回 final_text
        #    - asyncio.TimeoutError → adopt_running,返回 {task_id, status:"timed_out_to_background"}
        # 9. 后台路径:launch,返回 {task_id, status:"async_launched"}
        ...

    def set_parent(self, ag: Agent) -> None: ...
```

### 工具过滤多层防线

`src/gcode/tool/filter.py`:

```python
# 任何子 Agent 永远不能用的工具名列表。
# 本期最小列表:Agent。后续可扩展 AskUserQuestion / TaskStop / 系统级敏感工具。
ALL_AGENT_DISALLOWED_TOOLS: list[str] = ["Agent"]

# 自定义(user / project / plugin 来源)Agent 比内置 Agent 多禁用的工具。本期为空。
CUSTOM_AGENT_DISALLOWED_TOOLS: list[str] = []

# 后台 Agent 工具白名单。
# 不含 Agent / TaskStop / SendMessage / TaskList / TaskGet 等任何元工具。
ASYNC_AGENT_ALLOWED_TOOLS: list[str] = [
    "read_file", "write_file", "edit_file",
    "glob", "grep",
    "bash",
    "load_skill", "install_skill",
]
# MCP 工具与 Skill 工具按命名约定动态识别(以 "mcp__" 起头 / 来自 register_skill_tool),
# 通过 is_allowed_in_background 函数走另一条分支判定。

@dataclass
class FilterParams:
    all: list[str]                    # registry 的全部工具名(按注册顺序)
    source: int                       # subagent.Source 的整数值
    background: bool
    allowed: list[str] = field(default_factory=list)     # Agent 定义 tools 白名单
    disallowed: list[str] = field(default_factory=list)  # Agent 定义 disallowedTools 黑名单

def apply_agent_tool_filter(p: FilterParams) -> list[str]:
    """按 spec F30 顺序过滤。返回最终 allowed 列表(传给 Agent 构造参数)。"""
    ...
```

### TUI 集成层

`src/gcode/tui/app.py` 改动：
- `GCodeApp.__init__` 加 `task_mgr: task.Manager`、`subagent_catalog: subagent.Catalog`(由 cli 注入)
- `on_mount()` 末尾 `asyncio.create_task(self._consume_task_done())`
- 主对话 Agent 通过 `approval_upgrader=self.task_mgr.upgrade_approval` 让子 Agent 审批升级回主 TUI

`src/gcode/tui/stream.py` 改动：
- `_consume_stream` 监听 ESC 键(Textual `BINDINGS = [("escape", "esc", "")]`):若 `state == STREAMING` 且当前有运行中的 SubAgent → 调 `self.task_mgr.adopt_running(...)`,切回 idle 态
- 监听 SubAgent ApprovalRequest 转发——TaskManager 通过 events 队列转回主 TUI 走现有 Approval 路径

`src/gcode/tui/skill_fork.py` 改造：
- 删除现有 `run_sub_agent` 内的零散逻辑
- 改为调 `subagent.launch_fork(host, opts, conv)`,host 持有 `self.task_mgr` / `self.runtime` / `self.engine` 等

## 模块设计### 模块 A:`gcode.subagent`**职责:**
- 数据结构 `Definition`
- Markdown + YAML 解析(复用 `skills/parser.py` 的 `parse_frontmatter_and_body`——抽到 `gcode.util.markdown` 让两方共用,或 skills 与 subagent 都各自有一份)
- 三层 + 内置随包加载

**对外接口:**
- `load_catalog(root: str) -> Catalog`
- `Catalog.resolve(name)` / `list()` / `fork_definition()`

**依赖:**
- `gcode.permission`(解析 permission_mode 字段)
- `pyyaml`
- 标准库 `pathlib` / `importlib.resources`

**关键设计:**
- Markdown 解析复用 `skills/parser.py` 的 `parse_frontmatter_and_body`——抽到 `subagent/parser.py` 独立实现一份(避免互相依赖),内容几乎一致
- 内置文件 `gcode/subagent/builtin/general-purpose.md` / `explore.md` / `plan.md` 通过 `importlib.resources.files("gcode.subagent.builtin")` 读取
- 加载错误统一 stderr `print(f"subagent {name}: ... skipped", file=sys.stderr)`

### 模块 B:`gcode.task`**职责:**
- 后台任务生命周期管理
- 4 个内置工具(TaskList / TaskGet / TaskStop / SendMessage)

**对外接口:**
- `Manager()`
- `launch / adopt_running / get / list / stop / send_message / subscribe_done`
- `TaskListTool / TaskGetTool / TaskStopTool / SendMessageTool` 4 个 Tool 类(或 `new_task_list_tool(m)` 等工厂)

**依赖:**
- `gcode.agent`(Agent)
- `gcode.conversation`
- `gcode.tool`
- `gcode.llm`

**关键设计:**
- `_done` 队列 `maxsize=32` 够大,正常场景不可能填满;真满了 `put_nowait` 抛 `QueueFull` 时丢弃 + stderr 警告(主 TUI 漏一条通知不致命)
- `launch` 协程包 `try/except BaseException`,任何异常转 `status=failed`
- `stop` 调 `task.handle.cancel()`,handle 是 `asyncio.create_task(run_to_completion(...))`
- `send_message`:仅当 `status == COMPLETED` 时允许;否则 raise `TaskBusy`。重新 `launch` 时用 *同 id*,status 从 COMPLETED 重置回 RUNNING

### 模块 C:`gcode.agent` 扩展**职责:**
- 新增 `run_to_completion` 方法
- 新增 6 个 `__init__` 关键字参数
- Fork 路径辅助

**对外新增接口:**
- `Agent.run_to_completion(conv, task, events=None) -> str`
- `Agent.__init__(..., system_prompt, max_turns, permission_mode, dont_ask, approval_upgrader, provider)`
- `build_forked_messages`
- `is_fork_context`

**关键设计:**
- `run_to_completion` 与 `run` 共用 `_stream_once` / `_execute_batched` / `_manage_context_auto` /
  `_record_read_file_if_applicable`,通过抽公共 helper 实现共享(把 `run` 的循环体抽到
  `_run_iter(conv, mode, iter_idx, ...)`,`run` 与 `run_to_completion` 都调它)
- 子 Agent 的 `permission_mode` + `dont_ask` 决策点在 `_execute_batched` 的 `_run_guarded` 内多一层短路:
  ```python
  if self.dont_ask:
      # 角色定义 dontAsk:走 sandbox / 黑名单 / 规则后,默认 Allow 而非 Ask
      if decision == PermissionDecision.ASK:
          decision = PermissionDecision.ALLOW
  ```
- 升级到父 TUI 的回调在 `_request_approval` 里调:
  ```python
  if self.approval_upgrader is not None:
      outcome, ok = await self.approval_upgrader(req)
      if ok:
          return outcome, True
  # 否则走默认 emit Approval event 路径(主 Agent inline 子 Agent 路径)
  ```

**Fork Boilerplate 注入策略:**
- `build_forked_messages` 把 Boilerplate 写在 user 消息开头(与 ch13 README 一致)
- `is_fork_context` 扫描 *所有* 历史 user 消息内容寻找 `<fork_boilerplate>`(QuerySource 兜底)

### 模块 D:Agent 工具与 TUI 集成**职责:**
- 把 Agent 工具注册到 registry
- TUI 接入 task notification
- 改造 Skill fork

**对外接口:**
- `AgentTool(catalog, task_mgr, parent, bg_enabled)`
- `subagent.launch_fork(host, opts)` 公共 Fork 启动函数(Skill fork 与 Agent 工具都调)

**关键设计:**
- `AgentTool.execute` 在前台 inline 路径返回结果时要小心:
  - 前台跑完返回 final_text 作为 tool_result content
  - 中途超时切后台 → 返回 JSON `{"task_id": "...", "status": "timed_out_to_background"}`
- 嵌套阻断:`AgentTool.execute` 入口检查 `ctx` 是否携带 `parent_agent_ctx_key`(子 Agent 启动时塞入);若有 → 返回结构化错误
  - 不依赖 ctx 单值:也扫 conv 历史是否含 Fork tag(`is_fork_context`)
- TUI 的 task notification 注入:
  - `on_mount()` 开 `asyncio.create_task(self._consume_task_done())`
  - `_consume_task_done()` 接 `done` 队列,`get` 拿状态,渲染成 `<task-notification>` 块,调 `self.runtime.append_reminders` 推入
  - 主对话下一次 run 自动拿到(已有机制)

## 模块交互### 启动期 wiring

```
cli.main()
  ├── tool.default_registry()       → registry
  ├── permission.Engine(root)       → engine
  ├── SessionRuntime(...)           → runtime
  ├── skills.load_catalog(...)      → skill_catalog
  ├── hook.load(...)                → hook_engine
  ├── subagent.load_catalog(root)   → subagent_catalog       ← 新增
  ├── task.Manager()                → task_mgr               ← 新增
  ├── registry.register(task.TaskListTool(task_mgr))         ← 新增
  ├── registry.register(task.TaskGetTool(task_mgr))          ← 新增
  ├── registry.register(task.TaskStopTool(task_mgr))         ← 新增
  ├── registry.register(task.SendMessageTool(task_mgr))      ← 新增
  ├── GCodeApp(..., task_mgr=task_mgr, subagent_catalog=subagent_catalog, ...)
  │     │
  │     └── 在 GCodeApp 内:Agent 工具的注册被推迟到主 Agent 构造后
  │         (因为要把 parent_agent 注入),或者 Agent 工具 lazy 拿:把 catalog / task_mgr 写死,
  │         parent_agent 通过函数 / 持有 self.app 拿
```

**简化方案:** Agent 工具在 `cli.main` 注册,parent 字段在 `GCodeApp` 构造完后回填:
```python
agent_tool = AgentTool(subagent_catalog, task_mgr, parent=None,
                       bg_enabled=cfg.effective_enable_subagent_background())
registry.register(agent_tool)
# 再 GCodeApp(...)
app = GCodeApp(...)
# 再
agent_tool.set_parent(app.main_agent)
```

### 运行时:主 Agent 调 Agent 工具(前台,定义式)

```
LLM 流式产出 tool_use:{name:"Agent", input:{prompt:"...", subagent_type:"Explore"}}
    ↓
Agent._execute_batched → 路由到 AgentTool.execute(args, ctx)
    ↓
AgentTool.execute:
    1. 解析参数 -> AgentArgs
    2. 防嵌套:检测 ctx / conv 是否来自 Fork → 否
    3. catalog.resolve("Explore") → defi
    4. background = defi.background or args.run_in_background → False
    5. apply_agent_tool_filter(...) -> allowed
    6. provider = AnthropicProvider(model="haiku") if defi.model == "haiku" else parent.provider
    7. sub_runtime = SessionRuntime(200_000)
    8. sub_agent = Agent(
           provider=provider, registry=registry, version=version, engine=engine,
           runtime=sub_runtime,
           allowed_tools=allowed,
           system_prompt=defi.system_prompt,         ← 新
           max_turns=defi.max_turns,
           permission_mode=defi.permission_mode,
           dont_ask=defi.dont_ask,
           approval_upgrader=parent.task_mgr.upgrade_approval,
           hook_engine=parent.hook_engine,
       )
    9. sub_conv = Conversation()
    10. try:
            final_text = await asyncio.wait_for(
                sub_agent.run_to_completion(sub_conv, args.prompt, events),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            task_id = await task_mgr.adopt_running(
                sub_agent, sub_conv, args.name, events, running_task, partial,
            )
            return ToolResult(content=f'{{"task_id":"{task_id}","status":"timed_out_to_background"}}')

        return ToolResult(content=final_text)
```

### 运行时:主 Agent 调 Agent 工具(后台,显式)

```
AgentTool.execute:
    ...
    10. task_id = await task_mgr.launch(sub_agent, sub_conv, args.name, args.prompt)
    11. 返回 ToolResult(content='{"task_id":"task_xxx","status":"async_launched"}')
```

### 后台任务完成通知

```
task_mgr.launch 协程:
    final_text = await sub_agent.run_to_completion(conv, task, events)
    bt.result = final_text
    bt.err = None
    bt.status = Status.COMPLETED  # (or FAILED / CANCELLED)
    try:
        self._done.put_nowait(task_id)
    except asyncio.QueueFull:
        # 缓冲满,丢弃 + stderr 警告
        ...
    ↓
GCodeApp._consume_task_done 协程:
    while True:
        task_id = await self.task_mgr.subscribe_done().get()
        bt = self.task_mgr.get(task_id)
        if bt is None:
            continue
        notification = build_task_notification(bt)  # <task-notification>...</task-notification>
        self.runtime.append_reminders([notification])
        # 不主动唤醒主对话:等主 Agent 下次 run 自然 take reminder
    ↓
下一次 self._begin_turn → self.agent.run → build_reminder takes pending_reminders → 注入 reminder 区
```

### Fork 路径

```
AgentTool.execute (subagent_type 空):
    1. defi = catalog.fork_definition()       # name="__fork__"
    2. background = True (Fork 强制)
    3. allowed = apply_agent_tool_filter(...)
       注意:这里 defi.disallowed_tools 不含 "Agent" → Fork 子 Agent 工具集保留 Agent
    4. forked_msgs = build_forked_messages(parent_conv.messages(), args.prompt)
    5. sub_conv = Conversation.from_messages(forked_msgs)
    6. sub_agent = Agent(..., allowed_tools=allowed, system_prompt=None)  # 继承主系统提示
    7. task_id = await task_mgr.launch(sub_agent, sub_conv, args.name, args.prompt)
    8. 返回 ToolResult(content='{"task_id":"...","status":"async_launched"}')
```

### Fork 子 Agent 调 Agent 工具被阻断

```
Fork 子 Agent 跑动中,LLM 又产 tool_use:{name:"Agent", input:{...}}
    ↓
sub_agent._execute_batched → AgentTool.execute(args, sub_ctx)
    ↓
AgentTool.execute:
    检测:is_fork_context(sub_conv.messages()) → True(消息中含 <fork_boilerplate>)
    → 返回 ToolResult(is_error=True,
                      content="Fork 子 Agent 不能再启动 Agent(检测到 fork boilerplate)")
```

注:由于 `ALL_AGENT_DISALLOWED_TOOLS = ["Agent"]` 已经把 Agent 工具从子 Agent 工具列表里剔除,理论上 Fork 子 Agent 的 LLM 看不到 Agent 工具。但 Fork 路径**故意保留**(为了 prompt cache 一致性),靠 QuerySource + Boilerplate 兜底拦截。

**结论:** Fork 子 Agent 工具列表 = 父工具列表 - disallowed_tools - 后台白名单交集 - 但不去除 Agent 工具。

### Skill fork 改造

```
GCodeApp.execute("/foo") → skills.Executor.execute → fork 闭包 self._run_sub_agent
    ↓ (改造后)
self._run_sub_agent(conv, opts):
    return await subagent.launch_fork(
        host=subagent.HostFromApp(self),
        opts=subagent.ForkLaunchOpts(
            allowed_tools=opts.allowed_tools,
            model=opts.model,
            conv=conv,                     # skills 已构造好的 fork_conv
            system_prompt="",              # 走继承
            background=False,              # skills 仍走前台同步(返回 final_text 给 host)
            events_sink=None,
        ),
    )
```

`subagent.launch_fork` 内部:做与 `AgentTool.execute` 前台路径相同的 wiring,只是不读 catalog Definition。

## 文件组织

```
gcode/
├── pyproject.toml
├── src/
│   └── gcode/
│       ├── subagent/                       ← 新增包
│       │   ├── __init__.py                 公共导出
│       │   ├── definition.py               Definition / Source 类型
│       │   ├── parser.py                   parse_frontmatter_and_body + validate_meta
│       │   ├── catalog.py                  Catalog + load_catalog / resolve / list / fork_definition
│       │   ├── embed.py                    importlib.resources 读取 builtin/*.md + builtin_definitions()
│       │   ├── launch.py                   (本期取消,见 T31 说明) — 改放到 agent/launch.py
│       │   └── builtin/
│       │       ├── general-purpose.md
│       │       ├── explore.md
│       │       └── plan.md
│       │
│       ├── task/                           ← 新增包
│       │   ├── __init__.py
│       │   ├── manager.py                  Manager + BackgroundTask + launch / adopt_running / stop / send_message
│       │   └── tools.py                    TaskListTool / TaskGetTool / TaskStopTool / SendMessageTool
│       │
│       ├── agent/                          ← 现有包扩展
│       │   ├── agent.py                    现有,加 system_prompt / max_turns / permission_mode / dont_ask / approval_upgrader 字段;run 抽 _run_iter;_run_guarded 加 dont_ask 短路 + approval_upgrader 升级
│       │   ├── run_to_completion.py        ← 新增 run_to_completion 实现
│       │   ├── fork.py                     ← 新增 build_forked_messages / is_fork_context / FORK_BOILERPLATE
│       │   ├── agent_tool.py               ← 新增 AgentTool
│       │   ├── permission_upgrade.py       ← 新增 ApprovalUpgrader 类型 + default_upgrader
│       │   └── launch.py                   ← 新增 launch_fork(供 skill_fork 调用)
│       │
│       ├── tool/                           ← 现有包扩展
│       │   └── filter.py                   ← 新增 ALL_AGENT_DISALLOWED / ASYNC_AGENT_ALLOWED / apply_agent_tool_filter
│       │
│       ├── tui/                            ← 现有包改动
│       │   ├── app.py                      加 task_mgr / subagent_catalog 字段 + _consume_task_done 协程 + AgentTool 注册
│       │   ├── stream.py                   _consume_stream 加 ESC → adopt_running 分支;子 Agent ApprovalRequest 转发
│       │   ├── tasks.py                    ← 新增 _consume_task_done + build_task_notification + ESC 切后台辅助
│       │   └── skill_fork.py               ← 改造为复用 agent.launch_fork
│       │
│       ├── config.py                       ← 现有,加 enable_subagent_background 字段(默认 True)
│       └── cli.py                          ← 加 subagent.load_catalog / task.Manager / 4 个工具注册 / Agent 工具注册
│
└── tests/
    ├── subagent/
    │   ├── test_parser.py
    │   ├── test_catalog.py
    │   └── test_launch.py
    ├── task/
    │   ├── test_manager.py
    │   └── test_tools.py
    ├── agent/
    │   ├── test_fork.py
    │   ├── test_run_to_completion.py
    │   ├── test_agent_tool.py
    │   └── test_agent_tool_integration.py
    ├── tool/
    │   └── test_filter.py
    └── tui/
        └── test_tui.py
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| run_to_completion 与 run 关系 | 共用底层 helper(`_run_iter` / `_stream_once`),不重新写一遍循环 | 避免两套循环逻辑漂移;主对话与子 Agent 在 ReAct 层面行为应一致 |
| 子 Agent 是否独立 PermissionEngine | 暂共享同一 Engine,但增加 approval_upgrader 让审批升级回主 TUI | 本期权限规则全局一致;独立 Engine 是为隔离规则集准备的预留扩展点 |
| Fork 强制后台 | 是 | ch13 README 设计;Fork 上下文长,前台同步会阻塞用户;并行 Fork 才有意义 |
| 后台通知形式 | system reminder 注入(`<task-notification>`),不直接 push 到 LLM | 与 ch12 pending_reminders 一致;不打断用户当前操作;主 Agent 下次 turn 自然消费 |
| 嵌套阻断三道闸 | `ALL_AGENT_DISALLOWED_TOOLS` 全局 + Fork 路径 QuerySource + Boilerplate 标记扫描 | 单一闸门失效(对话压缩、工具列表漂移)仍能兜底;定义式靠工具过滤,Fork 靠双闸 |
| 后台白名单粒度 | 列具体工具名 + MCP / Skill 工具按命名约定动态识别 | ch13 README 同款做法;不需要为每个 MCP 工具列在白名单里 |
| done 队列缓冲 32 | 够大 | 正常场景一会儿不会有 32 个任务同时跑完;真满则 `put_nowait` 抛 `QueueFull`,捕获后丢弃 + stderr |
| send_message 同 id 复用 | 是 | 状态语义上是"该任务继续",而非"新任务";UI / 查询体验更连贯 |
| 配置开关 enable_subagent_background | 默认 True | 后台是核心能力,默认开启;关闭后所有子 Agent 强制前台,主要供 CI / 调试用 |
| Markdown 解析器复用 | 不共享,subagent 包独立实现一份(几乎与 `skills/parser.py` 一致) | 避免抽公共包导致循环依赖;两个包字段不一样,复用收益有限 |
| Agent 工具的 parent 注入时机 | `cli.main` 注册时为 None,`GCodeApp` 构造后 `set_parent` 回填 | `Registry` 在 `GCodeApp` 之前已构造,Agent 工具的 parent 依赖 `app.main_agent` 反推 |
| ESC 切后台 vs Ctrl+C | ESC 切后台,Ctrl+C 仍是取消(沿用现有) | ESC 在 TUI 已经做"取消选择"用途,但流式态下 ESC 转为切后台是 ch13 README 设计 |
| 并发原语 | `asyncio.Queue` / `asyncio.Task` / `asyncio.Event` / `asyncio.wait_for` | Python async-first 体系;不用线程池,与 Textual 事件循环天然共存 |
| 内置 .md 加载 | `importlib.resources.files("gcode.subagent.builtin")` | 标准库官方推荐方式;打包成 wheel 后仍能读取;无需 manifest 配置 |
````

````markdown
# SubAgent 机制 Tasks

> 包名：`gcode`(Python 3.12+)。源码位于 `src/gcode/`,内部模块以 `gcode.xxx` 导入。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gcode/subagent/__init__.py` | 包公共导出 |
| 新建 | `src/gcode/subagent/definition.py` | `Definition` / `Source` 类型 |
| 新建 | `src/gcode/subagent/parser.py` | `parse_frontmatter_and_body` + `validate_meta` |
| 新建 | `tests/subagent/test_parser.py` | 解析与字段校验单测 |
| 新建 | `src/gcode/subagent/catalog.py` | `Catalog` + `load_catalog` / `resolve` / `list` / `fork_definition` |
| 新建 | `tests/subagent/test_catalog.py` | 多来源加载与覆盖测试 |
| 新建 | `src/gcode/subagent/embed.py` | `importlib.resources` 读取 builtin/*.md + `builtin_definitions()` |
| 新建 | `src/gcode/subagent/builtin/general-purpose.md` | 内置 general-purpose 定义 |
| 新建 | `src/gcode/subagent/builtin/explore.md` | 内置 Explore 定义 |
| 新建 | `src/gcode/subagent/builtin/plan.md` | 内置 Plan 定义 |
| 新建 | `tests/subagent/test_launch.py` | `launch_fork` 流程测试 |
| 新建 | `src/gcode/task/__init__.py` | 包公共导出 |
| 新建 | `src/gcode/task/manager.py` | `Manager` + `BackgroundTask` + `launch` / `adopt_running` / `stop` / `send_message` / `subscribe_done` |
| 新建 | `tests/task/test_manager.py` | 后台任务全生命周期测试 |
| 新建 | `src/gcode/task/tools.py` | 4 个内置工具 `TaskListTool` / `TaskGetTool` / `TaskStopTool` / `SendMessageTool` |
| 新建 | `tests/task/test_tools.py` | 4 个工具的单测 |
| 新建 | `src/gcode/agent/run_to_completion.py` | `run_to_completion` 方法实现(挂到 `Agent` 上) |
| 新建 | `tests/agent/test_run_to_completion.py` | `run_to_completion` / `dont_ask` / `max_turns` 测试 |
| 新建 | `src/gcode/agent/fork.py` | `build_forked_messages` + `is_fork_context` + `FORK_BOILERPLATE` |
| 新建 | `tests/agent/test_fork.py` | Fork 消息构造与上下文识别测试 |
| 新建 | `src/gcode/agent/agent_tool.py` | `AgentTool` + `execute` |
| 新建 | `tests/agent/test_agent_tool.py` | Agent 工具调用、嵌套阻断、超时切后台测试 |
| 新建 | `src/gcode/agent/permission_upgrade.py` | `ApprovalUpgrader` 类型 + `default_upgrader` |
| 新建 | `src/gcode/agent/launch.py` | `launch_fork` 公共启动函数(供 skill_fork 调用) |
| 新建 | `src/gcode/tool/filter.py` | `ALL_AGENT_DISALLOWED` / `ASYNC_AGENT_ALLOWED` / `apply_agent_tool_filter` |
| 新建 | `tests/tool/test_filter.py` | 过滤多层防线测试 |
| 新建 | `src/gcode/tui/tasks.py` | `_consume_task_done` + `build_task_notification` + ESC 切后台辅助 |
| 修改 | `src/gcode/agent/agent.py` | 加 system_prompt / max_turns / permission_mode / dont_ask / approval_upgrader 字段;`run` 抽 `_run_iter`;`_run_guarded` 加 `dont_ask` 短路 + `approval_upgrader` 升级 |
| 修改 | `tests/agent/test_agent.py` | 不破坏既有测试 |
| 修改 | `src/gcode/tool/registry.py` | 不动(过滤逻辑在 `filter.py`) |
| 修改 | `src/gcode/tui/app.py` | `GCodeApp` 加 `task_mgr` / `subagent_catalog`;`on_mount` 起 `_consume_task_done`;Agent 工具注册后 `set_parent` |
| 修改 | `src/gcode/tui/stream.py` | `_consume_stream` 加 ESC → `adopt_running` 分支 |
| 修改 | `src/gcode/tui/skill_fork.py` | 改造为调 `agent.launch_fork` |
| 修改 | `tests/tui/test_tui.py` | 补 ESC 切后台、task-notification 注入测试 |
| 修改 | `src/gcode/config.py` | 加 `enable_subagent_background: bool | None`(默认视为 True) |
| 修改 | `src/gcode/cli.py` | `load_catalog` / `Manager` / 4 个 task 工具注册 / Agent 工具注册 + `set_parent`;`task_mgr` / `subagent_catalog` 传给 `GCodeApp` |

## T1: subagent 包的 Definition 与 Source 类型**文件:** `src/gcode/subagent/definition.py`
**依赖:** 无
**步骤:**
1. 新建包 `gcode.subagent`,加 `definition.py`,声明 `Source(IntEnum)` 与四个常量:
   - `BUILTIN = 0`
   - `USER = 1`
   - `PROJECT = 2`
   - `PLUGIN = 3`(占位)
2. `Source.__str__` 返回 `"builtin" / "user" / "project" / "plugin"`,越界返回 `"unknown"`
3. 声明 `Definition` `@dataclass`,字段如 plan.md 所述:`name / description / tools / disallowed_tools / model / max_turns / permission_mode / dont_ask / background / system_prompt / file_path / source`
4. docstring 标注每个字段语义,引用 spec F4
5. `Definition.is_fork()` 返回 `self.name == "__fork__"`(便于 `fork_definition` 判别)

**验证:** `python -c "from gcode.subagent.definition import Definition, Source"` 导入无误

## T2: subagent 解析器**文件:** `src/gcode/subagent/parser.py`
**依赖:** T1
**步骤:**
1. 新建 `parser.py`,从 `skills/parser.py` 复制 `parse_frontmatter_and_body` 与 `UTF8_BOM` 常量(几乎不变,改为 `gcode.subagent` 包内调用)
2. 声明 `AGENT_NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9\-_]{0,31}$")`(大小写都允许,与 ch13 README 的 `Explore` / `Plan` 一致)
3. 实现 `parse_definition(data: bytes, file_path: str, source: Source) -> Definition`:
   - 调 `parse_frontmatter_and_body` 拿 frontmatter dict + body
   - YAML 已 `safe_load` 成 `dict[str, Any]`,字段映射:
     ```python
     name = str(fm.get("name", "")).strip()
     description = str(fm.get("description", "")).strip()
     tools = list(fm.get("tools") or [])
     disallowed_tools = list(fm.get("disallowedTools") or [])
     model_str = str(fm.get("model") or "").strip()
     max_turns = int(fm.get("maxTurns") or 0)
     permission_mode_str = str(fm.get("permissionMode") or "").strip()
     background = bool(fm.get("background") or False)
     ```
   - 校验 name 非空且匹配 `AGENT_NAME_REGEX`
   - 校验 description 非空
   - 校验 model:空 / `"inherit"` / `"haiku"` / `"sonnet"` / `"opus"` 之一,其它 stderr 警告并改为 `"inherit"`
   - 解析 permission_mode:`"dontAsk"` 单独识别 → `Definition.dont_ask=True`, `Definition.permission_mode=PermissionMode.DEFAULT`;否则调 `PermissionMode.parse`,失败 stderr 警告并改为 `DEFAULT`
   - 把 fm 字段映射到 Definition 字段(`system_prompt = body`,`file_path = file_path`,`source = source`)
4. 实现 `parse_file(path: str, source: Source) -> Definition`:`pathlib.Path(path).read_bytes()` + `parse_definition`

**验证:** `pytest tests/subagent/test_parser.py -v` 通过(对应 T3 的测试)

## T3: subagent 解析器测试**文件:** `tests/subagent/test_parser.py`
**依赖:** T2
**步骤:**
1. 参数化测试(`pytest.mark.parametrize`):正常完整 frontmatter / 仅必填 / model 非法 → 警告 fallback / `permissionMode=dontAsk` → `dont_ask=True` / 缺 name 抛 ValueError / 缺 description 抛 ValueError / frontmatter 未关闭 → 抛错
2. body 区段提取:验证 `---` 后的内容(去 BOM 去前导换行)被完整取到 `system_prompt`
3. 测试 `parse_file` 读取一个 `tests/subagent/testdata/*.md` 文件
4. 用 `capsys` 捕获 stderr 验证 fallback 时的警告输出

**验证:** `pytest tests/subagent/test_parser.py -v` 全部通过

## T4: 内置 Agent 定义文件**文件:** `src/gcode/subagent/builtin/{general-purpose,explore,plan}.md`
**依赖:** 无
**步骤:**
1. 创建目录 `src/gcode/subagent/builtin/`
2. `general-purpose.md`:
   ```yaml
   ---
   name: general-purpose
   description: 通用子 Agent,拥有全部工具,用于需要完整能力但独立上下文的场景
   maxTurns: 30
   ---

   你是 GCode 的通用 Agent。根据用户的消息,使用可用工具完成任务。
   把任务做完,不要过度设计,但也不要做一半就停。
   完成后用简洁的报告回复:做了什么、关键发现。
   调用方会把结果转述给用户,所以只需要包含要点。
   ```
3. `explore.md`:
   ```yaml
   ---
   name: Explore
   description: 只读代码探索 Agent,适合搜索、阅读、理清调用链;不能修改文件
   disallowedTools:
     - write_file
     - edit_file
   model: haiku
   maxTurns: 30
   ---

   你是一个文件搜索专家。这是一个只读探索任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工具策略:Glob 做文件模式匹配、Grep 搜索文件内容、Read 读取已知路径、Bash 仅用于只读操作(ls、git log、find、cat)。
   尽可能并行发起多个工具调用。高效完成搜索请求,清晰报告发现。
   ```
4. `plan.md`:
   ```yaml
   ---
   name: Plan
   description: 计划 Agent,分析需求、制定执行计划,但不直接执行;主 Agent 拿到计划后逐步执行
   disallowedTools:
     - write_file
     - edit_file
     - Agent
   maxTurns: 15
   permissionMode: plan
   ---

   你是一个软件架构师和规划专家。这是一个只读规划任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工作流程:① 理解需求 ② 用搜索工具充分探索代码库 ③ 设计方案 ④ 输出分步实现计划。
   回复末尾必须列出 3-5 个对实现最关键的文件路径。
   ```
5. 在 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel]` 或 `[tool.setuptools.package-data]` 中确保 `*.md` 被打包进 wheel(hatch 默认包含同包目录下任意文件,通常不需要额外配置)

**验证:** 三个 `.md` 文件存在,frontmatter 合法;`parse_file` 测试不报错

## T5: subagent embed 与内置加载**文件:** `src/gcode/subagent/embed.py`
**依赖:** T2, T4
**步骤:**
1. 新建 `embed.py`,导入:
   ```python
   from importlib.resources import files
   ```
2. 实现 `builtin_definitions() -> list[Definition]`:
   - `pkg = files("gcode.subagent.builtin")`
   - 遍历 `pkg.iterdir()`,过滤 `name.endswith(".md")`
   - 对每个文件:`data = (pkg / name).read_bytes()` + `parse_definition(data, f"builtin:{name}", Source.BUILTIN)`
   - 解析失败 raise(代码 bug,启动期失败即灾难)
3. 返回按 `name` 升序的 list

**验证:** `pytest tests/subagent/test_catalog.py::test_builtin -v` 通过(T7)

## T6: Catalog 与三层加载**文件:** `src/gcode/subagent/catalog.py`
**依赖:** T1, T2, T5
**步骤:**
1. 新建 `catalog.py`,声明 `Catalog` 类(见 plan.md)
2. 实现 `load_catalog(root: str) -> Catalog`:
   ```python
   c = Catalog()
   c._add_all(builtin_definitions(), Source.BUILTIN)
   c._add_all(_load_from_dir(Path.home() / ".gcode/agents", Source.USER), Source.USER)
   c._add_all(_load_from_dir(Path(root) / ".gcode/agents", Source.PROJECT), Source.PROJECT)
   return c
   ```
3. 实现 `_load_from_dir(dir: Path, source: Source) -> list[Definition]`:
   - 目录不存在 → 返回 `[]`
   - 遍历 `dir.glob("*.md")`,逐个 `parse_file`;失败 stderr 警告并跳过
   - 返回 list
4. 实现 `Catalog._add_all(defs: list[Definition], source: Source)`:
   - 同名时高优先级覆盖(因为按 builtin → user → project 顺序加载,后加的优先级更高)
   - 同时往 `self._by_source[source]` 追加
5. 实现 `resolve(name: str) -> Definition | None`
6. 实现 `list() -> list[Definition]`(按 name 升序)
7. 实现 `list_by_source(s: Source) -> list[Definition]`
8. 实现 `fork_definition() -> Definition`:
   ```python
   return Definition(
       name="__fork__",
       description="Fork-based subagent",
       model="inherit",
       max_turns=25,
       permission_mode=PermissionMode.DEFAULT,
       # tools / disallowed_tools 留空 -> 工具集继承父
   )
   ```

**验证:** `pytest tests/subagent/test_catalog.py -v` 通过

## T7: Catalog 测试**文件:** `tests/subagent/test_catalog.py`
**依赖:** T6
**步骤:**
1. 测试 `builtin_definitions` 返回 3 个 def(general-purpose / Explore / Plan)
2. 测试三层覆盖:用 `tmp_path` fixture 造一个项目 root 与一个 HOME 路径(用 `monkeypatch.setenv("HOME", ...)`),分别放 `explore.md`
3. 验证 `resolve("Explore")` 在三种情形下返回的 `source` 正确(都有 → project;只有 user+builtin → user;只有 builtin → builtin)
4. 测试 `fork_definition` 返回 `is_fork() is True`
5. 测试加载错误处理:放一个非法 frontmatter 文件,加载后该文件 *被跳过*,其他文件仍正常(用 `capsys` 验证 stderr 警告)

**验证:** `pytest tests/subagent/ -v` 全部通过

## T8: 工具过滤多层防线**文件:** `src/gcode/tool/filter.py`
**依赖:** 无
**步骤:**
1. 新建 `filter.py`,声明三个全局常量:
   ```python
   ALL_AGENT_DISALLOWED_TOOLS: list[str] = ["Agent"]
   CUSTOM_AGENT_DISALLOWED_TOOLS: list[str] = []
   ASYNC_AGENT_ALLOWED_TOOLS: list[str] = [
       "read_file", "write_file", "edit_file",
       "glob", "grep",
       "bash",
       "load_skill", "install_skill",
   ]
   ```
2. 声明 `FilterParams` `@dataclass`:
   ```python
   @dataclass
   class FilterParams:
       all: list[str]                    # registry 的全部工具名
       source: int                       # 1=builtin, 2=user, 3=project, 4=plugin(与 subagent.Source 对齐)
       background: bool
       allowed: list[str] = field(default_factory=list)   # Agent 定义的 tools 白名单
       disallowed: list[str] = field(default_factory=list)  # Agent 定义的 disallowedTools 黑名单
   ```
3. 实现 `apply_agent_tool_filter(p: FilterParams) -> list[str]`:
   按 spec F30 顺序:
   - 起点 = `p.all` 副本
   - 过滤 1:去除 `ALL_AGENT_DISALLOWED_TOOLS`
   - 过滤 2:若 `p.source >= 2`(非 builtin),再去除 `CUSTOM_AGENT_DISALLOWED_TOOLS`(本期为空,跳过)
   - 过滤 3:若 `p.background`,与 `ASYNC_AGENT_ALLOWED_TOOLS + is_mcp_or_skill(name)` 取交集
   - 过滤 4:去除 `p.disallowed`
   - 过滤 5:若 `len(p.allowed) > 0`,与之取交集
4. 辅助函数 `is_mcp_or_skill(name: str) -> bool`:`name.startswith("mcp__")`(对 skill 工具的识别本期暂不接入,Registry 不区分,先按名字前缀 + 内置基础工具白名单兜底)

**验证:** `python -c "from gcode.tool.filter import apply_agent_tool_filter"` 导入无误

## T9: 工具过滤测试**文件:** `tests/tool/test_filter.py`
**依赖:** T8
**步骤:**
1. 参数化测试 `apply_agent_tool_filter` 覆盖各组合:
   - 默认:无后台、无白名单、无黑名单 → 去 Agent 即可
   - 后台:取 `ASYNC_AGENT_ALLOWED_TOOLS` 交集
   - 黑名单:`disallowed=["bash"]` → 不含 bash
   - 白名单:`allowed=["read_file", "grep"]` → 仅这两个
   - 黑 + 白:白名单先收窄,黑名单再剔除
   - 后台 + MCP 工具:MCP 工具(`mcp__xxx`)被保留(白名单 OK)
2. 单独测试 `is_mcp_or_skill` 边界

**验证:** `pytest tests/tool/test_filter.py -v` 通过

## T10: Agent 类扩展 - 新增构造参数**文件:** `src/gcode/agent/agent.py`
**依赖:** 无
**步骤:**
1. 在 `Agent.__init__` 加关键字参数(与默认值):
   ```python
   def __init__(
       self,
       ...,  # 原有
       system_prompt: str | None = None,
       max_turns: int = 0,                                  # 0 = 用全局 MAX_ITERATIONS
       permission_mode: PermissionMode | None = None,        # None = 用 TUI 运行时模式
       dont_ask: bool = False,
       approval_upgrader: ApprovalUpgrader | None = None,
       provider: Provider | None = None,                     # None = 用默认 provider
   ) -> None:
       self.system_prompt = system_prompt
       self.max_turns = max_turns
       self.permission_mode = permission_mode
       self.dont_ask = dont_ask
       self.approval_upgrader = approval_upgrader
       if provider is not None:
           self.provider = provider
   ```
2. 在 docstring 解释每个选项语义
3. 注意 `permission_mode is None` 与 `dont_ask=False` 都表示"未设置";`permission_mode` 一旦 != None 表示子 Agent 显式指定,覆盖 TUI 运行时模式

**验证:** `python -c "from gcode.agent.agent import Agent; Agent.__init__"` 无 TypeError

## T11: ApprovalUpgrader 类型**文件:** `src/gcode/agent/permission_upgrade.py`
**依赖:** T10
**步骤:**
1. 新建文件,声明:
   ```python
   from typing import Awaitable, Callable
   from gcode.permission import PermissionOutcome
   from gcode.agent.approval import ApprovalRequest

   ApprovalUpgrader = Callable[
       [ApprovalRequest],
       Awaitable[tuple[PermissionOutcome, bool]],
   ]
   ```
2. docstring 解释:子 Agent 把审批请求升级到父 TUI 的回调;返回 `(outcome, ok)`——`ok=False` 时调用方应走默认 emit Approval 路径

**验证:** `python -c "from gcode.agent.permission_upgrade import ApprovalUpgrader"` 导入无误

## T12: Fork 路径辅助函数**文件:** `src/gcode/agent/fork.py`
**依赖:** 无(纯函数)
**步骤:**
1. 新建 `fork.py`,声明常量:
   ```python
   FORK_BOILERPLATE_TAG = "<fork_boilerplate>"

   FORK_BOILERPLATE = """<fork_boilerplate>
   你是一个 Fork 出来的工作进程。你不是主 Agent。
   规则(不可协商):
   1. 不能再 Fork(调用 Agent 工具会被拦截)。
   2. 不要对话、不要提问、不要请求确认。
   3. 直接使用工具:读文件、搜索代码、做修改。
   4. 严格限制在你被分配的任务范围内。
   5. 最终报告以 "Scope:" 开头,500 字以内。
   </fork_boilerplate>

   """
   ```
2. 实现 `build_forked_messages(parent_msgs: list[Message], task: str) -> list[Message]`:
   - 深拷贝 `parent_msgs`(用 `copy.deepcopy` 或者手动 `Message(...)` 复制)
   - 扫描末尾 assistant 消息的 `tool_calls`:对于每个未配对的 `tool_call_id`,在 cloned 末尾追加 RoleTool 消息(每个 ID 一条 placeholder `ToolResult(content="[forked, skipped]", is_error=True)`)
     - 配对检查:看看 cloned 后续是否有 RoleTool 消息消费这些 ID
   - 追加最后一条 user 消息:`content = FORK_BOILERPLATE + task`
3. 实现 `is_fork_context(msgs: list[Message]) -> bool`:
   - 遍历 msgs,若 user / tool / assistant 消息内容含 `FORK_BOILERPLATE_TAG` → 返回 True
   - 默认 False

**验证:** `pytest tests/agent/test_fork.py -v` 通过(T13)

## T13: Fork 辅助函数测试**文件:** `tests/agent/test_fork.py`
**依赖:** T12
**步骤:**
1. 测试 `build_forked_messages` 空 parent → 返回单条 user 消息含 Boilerplate + task
2. 测试 parent 末尾有完整 assistant + tool_result 配对:cloned 末尾 == parent 末尾 + 一条 user
3. 测试 parent 末尾 assistant 有 2 个 tool_use 没配对:cloned 中追加 1 条 RoleTool(2 个 placeholder tool_result)再追加 1 条 user
4. 测试 `is_fork_context`:消息中含 Boilerplate → True;不含 → False

**验证:** `pytest tests/agent/test_fork.py -v` 通过

## T14: `_run_guarded` 加 dont_ask 短路与 approval_upgrader**文件:** `src/gcode/agent/agent.py`
**依赖:** T10, T11
**步骤:**
1. 修改 `_run_guarded`,在 `case PermissionDecision.ASK` 分支里:
   ```python
   if decision is PermissionDecision.ASK:
       # 子 Agent dontAsk 模式:直接 Allow
       if self.dont_ask:
           return await self._run_tool(c), True

       # 子 Agent 升级到父 TUI 审批
       if self.approval_upgrader is not None:
           req = ApprovalRequest(
               name=c.name,
               args=args_preview(c.input),
               reason=reason,
               respond=None,  # upgrader 内部处理 respond
           )
           outcome, ok = await self.approval_upgrader(req)
           if ok:
               match outcome:
                   case PermissionOutcome.ALLOW_ONCE:
                       return await self._run_tool(c), True
                   case PermissionOutcome.ALLOW_FOREVER:
                       self.engine.persist_local_allow(c)
                       return await self._run_tool(c), True
                   case _:
                       return deny_result(c.id, "用户拒绝了本次调用"), True

       # 默认路径:emit Approval event(主 Agent inline / Skill fork 都走此)
       outcome, ok = await self._request_approval(c, reason, queue)
       ...
   ```
2. 修改 `check` 调用前,如果子 Agent 设了 `permission_mode`(`self.permission_mode is not None`),用 `self.permission_mode` 覆盖入参 mode
3. 修改 `_stream_loop` 拿 defs 处的 `allowed_tools` 逻辑(已有,无须改)

**验证:** `pytest tests/agent/ -v` 现有测试不破

## T15: run_to_completion 实现**文件:** `src/gcode/agent/run_to_completion.py`
**依赖:** T10, T14
**步骤:**
1. 新建文件,实现挂到 `Agent` 上的方法:
   ```python
   async def run_to_completion(
       self,
       conv: Conversation,
       task: str,
       events: asyncio.Queue | None = None,
   ) -> str: ...
   ```
2. 逻辑:
   - 把 task 作为 user 消息:`if task: conv.add_user(task)`(注意 conv 可能已经被 Fork 路径预装填)
   - 计算 max_turns:`turns = self.max_turns or MAX_ITERATIONS`
   - 复用 `run` 的循环逻辑:但不用队列返回事件,直接内部消费;改为返回 final_text + raise
   - 拆出 helper `_run_iter(conv, mode, iter_idx, defs, sys, env_text, reminder, events_queue) -> tuple[text, calls, done]` 让 `run` 和 `run_to_completion` 都调
   - `run` 改造为调 `_run_iter` 逐轮;`run_to_completion` 也是
   - 子 Agent 用模式:`mode = self.permission_mode or PermissionMode.DEFAULT`
3. 退出条件:`done=True`(模型不再调工具)→ 返回 final_text;触达 turns → raise `MaxTurnsReached(final_text)`;`asyncio.CancelledError` → 透传(`raise`);出错 → raise(由 launch 协程的 try/except 兜底)
4. 在每轮内继续做 hook 调度(PreToolUse / PostToolUse / Stop 等),但 SubAgent 不触发 memory update
5. events 队列转发:把 Tool / Text / Approval 事件 `put_nowait` 进去(供 TaskManager / TUI 接收)

**验证:** `pytest tests/agent/test_run_to_completion.py -v` 通过(T16)

## T16: run_to_completion 测试**文件:** `tests/agent/test_run_to_completion.py`
**依赖:** T15
**步骤:**
1. 用 mock provider(已有 test helpers)模拟一个回合返回纯文本的子 Agent → `run_to_completion` 返回 `"ok"`,无异常
2. 模拟一个回合返回 tool_use(已知工具),下一轮返回纯文本 → 工具被执行、final_text 正确
3. 模拟模型一直调工具不出文本,触达 max_turns=3 → raise `MaxTurnsReached`
4. 测试 dont_ask:子 Agent 设 `dont_ask=True` + 模型调一个 Ask 级工具(如 bash) → 工具被自动放行执行
5. 测试 approval_upgrader 回调被命中:子 Agent 设了 upgrader,Ask 时 upgrader 被调用(用 mock upgrader 验证)
6. 测试 events 队列转发:运行子 Agent 时把 events 收集到 list,断言含 Tool / Text 事件

**验证:** `pytest tests/agent/test_run_to_completion.py -v` 全部通过

## T17: Agent 工具实现**文件:** `src/gcode/agent/agent_tool.py`
**依赖:** T8, T12, T15
**步骤:**
1. 新建文件,声明:
   ```python
   from typing import Protocol

   class AgentCatalog(Protocol):
       def resolve(self, name: str) -> Definition | None: ...
       def fork_definition(self) -> Definition: ...
       def list(self) -> list[Definition]: ...

   class TaskManager(Protocol):
       async def launch(self, ag: "Agent", conv: "Conversation",
                        name: str, task: str) -> str: ...
       async def adopt_running(self, ag: "Agent", conv: "Conversation",
                               name: str, events: asyncio.Queue,
                               handle: asyncio.Task, partial: PartialState) -> str: ...
       async def upgrade_approval(self, req: ApprovalRequest) -> tuple[PermissionOutcome, bool]: ...

   @dataclass
   class AgentArgs:
       prompt: str
       description: str
       subagent_type: str = ""
       model: str = ""
       run_in_background: bool = False
       name: str = ""

   class AgentTool(Tool):
       def __init__(self, catalog: AgentCatalog, task_mgr: TaskManager,
                    parent: "Agent | None", bg_enabled: bool) -> None: ...
   ```
2. **解决循环依赖**:agent 包要引用 subagent 包,但 subagent 不应反过来。检查 `subagent.Definition` 是否引用 agent 包——目前 `Definition` 只引用 `permission` 包,没问题。直接 `from gcode.subagent import Definition`(或用 Protocol 解耦)
3. **AgentTool 接口实现**:
   - `name` 属性 = `"Agent"`
   - `description()` 动态:基础描述 + `"subagent_type 可选值: " + ", ".join(d.name for d in catalog.list())`
   - `parameters()`:按 spec F1 写 JSON Schema dict
   - `read_only` 属性 = `False`
   - `async def execute(self, args: dict, ctx: ToolContext) -> ToolResult`
4. **execute 主流程**:
   ```python
   a_args = AgentArgs(**args)
   if not a_args.prompt:
       return ToolResult(is_error=True, content="prompt is required")
   if not a_args.description:
       return ToolResult(is_error=True, content="description is required")

   # 防嵌套
   if is_sub_agent_context(ctx):
       return ToolResult(is_error=True, content="subagent cannot spawn Agent")
   parent_conv = get_parent_conv(ctx)
   if parent_conv is not None and is_fork_context(parent_conv.messages()):
       return ToolResult(is_error=True,
                         content="Fork subagent cannot spawn Agent (boilerplate detected)")

   # resolve 定义
   if a_args.subagent_type:
       defi = self.catalog.resolve(a_args.subagent_type)
       if defi is None:
           return ToolResult(is_error=True,
                             content=f"unknown subagent_type: {a_args.subagent_type}")
   else:
       defi = self.catalog.fork_definition()

   # 决定后台
   background = defi.background or a_args.run_in_background or defi.is_fork()
   if background and not self.bg_enabled:
       return ToolResult(is_error=True, content="background mode is disabled by config")

   # 工具过滤
   allowed = apply_agent_tool_filter(FilterParams(
       all=registry_all_names(self.parent.registry),
       source=int(defi.source),
       background=background,
       allowed=defi.tools,
       disallowed=defi.disallowed_tools,
   ))

   # provider(model 字段切换 provider 的逻辑暂从简:本期不实现按模型切换,后续完善)
   provider = self.parent.provider

   # 构造子 Agent
   sub_runtime = SessionRuntime(200_000)
   sub_agent = Agent(
       provider=provider,
       registry=self.parent.registry,
       version=self.parent.version,
       engine=self.parent.engine,
       runtime=sub_runtime,
       allowed_tools=allowed,
       system_prompt=defi.system_prompt,
       max_turns=defi.max_turns,
       permission_mode=defi.permission_mode,
       dont_ask=defi.dont_ask,
       approval_upgrader=self.task_mgr.upgrade_approval,
       hook_engine=self.parent.hook_engine,
   )
   # 标记子 Agent 上下文(让递归 Agent 工具调用被拦截)
   child_ctx = with_sub_agent_context(ctx)

   # 子 conv
   sub_conv = Conversation()
   if defi.is_fork():
       parent_msgs = get_parent_conv_messages(ctx, self.parent)
       forked = build_forked_messages(parent_msgs, a_args.prompt)
       sub_conv = Conversation.from_messages(forked)

   # 后台路径
   if background:
       task_id = await self.task_mgr.launch(sub_agent, sub_conv,
                                            a_args.name, a_args.prompt)
       return ToolResult(content=json.dumps(
           {"task_id": task_id, "status": "async_launched"}))

   # 前台路径
   events: asyncio.Queue = asyncio.Queue(maxsize=32)
   partial = PartialState()
   aggregator = asyncio.create_task(aggregate_partial(events, partial))
   try:
       final_text = await asyncio.wait_for(
           sub_agent.run_to_completion(sub_conv, a_args.prompt, events),
           timeout=AUTO_BACKGROUND_SECONDS,
       )
   except asyncio.TimeoutError:
       running = asyncio.create_task(
           sub_agent.run_to_completion(sub_conv, "", events))
       task_id = await self.task_mgr.adopt_running(
           sub_agent, sub_conv, a_args.name, events, running, partial,
       )
       return ToolResult(content=json.dumps(
           {"task_id": task_id, "status": "timed_out_to_background"}))
   except Exception as e:
       return ToolResult(is_error=True, content=f"subagent error: {e}")
   finally:
       aggregator.cancel()
       await events.put(None)  # 触发 aggregator 收尾

   return ToolResult(content=final_text)
   ```
5. 实现辅助函数:`is_sub_agent_context / with_sub_agent_context / get_parent_conv_messages / aggregate_partial`
6. 提供 `set_parent(self, ag: "Agent") -> None` 让 cli 在 `GCodeApp` 构造之后回填 parent 引用

**验证:** `pytest tests/agent/test_agent_tool.py -v` 通过(T18)

## T18: Agent 工具测试**文件:** `tests/agent/test_agent_tool.py`
**依赖:** T17
**步骤:**
1. 测试 missing prompt → 返回错误
2. 测试 unknown subagent_type → 返回错误
3. 测试 known subagent_type(用一个 mock catalog 注入)→ 子 Agent 跑动并返回结果
4. 测试 `run_in_background=True` → 返回 `async_launched` JSON
5. 测试嵌套:用 `with_sub_agent_context` 包 ctx 后调 `execute` → 返回错误
6. 测试 `is_fork_context` 兜底:用 forked sub_conv 调,Agent 工具拦截
7. 测试 `enable_subagent_background=False` 时 background 路径报错

**验证:** `pytest tests/agent/test_agent_tool.py -v` 全部通过

## T19: task 包基础结构**文件:** `src/gcode/task/manager.py`
**依赖:** T10, T15
**步骤:**
1. 新建包 `gcode.task`,加 `__init__.py` 与 `manager.py`
2. 声明 `Status(IntEnum)` 与四个常量:`RUNNING / COMPLETED / FAILED / CANCELLED`
3. 声明 `Usage` `@dataclass`(对齐 `agent.Usage`)
4. 声明 `BackgroundTask` `@dataclass`(字段如 plan.md)
5. 声明 `PartialState` `@dataclass`
6. 声明 `Manager` 类:`_lock: asyncio.Lock; _tasks: dict[str, BackgroundTask]; _by_name: dict[str, str]; _done: asyncio.Queue[str]; _counter: int`
7. 实现 `__init__`:`self._done = asyncio.Queue(maxsize=32)`,counter=0
8. 实现 `_next_id() -> str`:`self._counter += 1` 后格式化为 `"task_" + secrets.token_hex(4)`(或 `f"{time.time_ns() ^ self._counter:08x}"` 取低 4 字节即可)
9. 实现 `get(id)` / `list()` / `subscribe_done()` 等查询方法

**验证:** `python -c "from gcode.task.manager import Manager"` 导入无误

## T20: Manager.launch 实现**文件:** `src/gcode/task/manager.py`
**依赖:** T19
**步骤:**
1. 实现:
   ```python
   async def launch(self, ag: Agent, conv: Conversation,
                    name: str, task_text: str) -> str:
       task_id = self._next_id()
       bt = BackgroundTask(
           id=task_id, name=name, sub_agent=ag, conv=conv, task=task_text,
           status=Status.RUNNING, start_time=time.monotonic(),
       )

       async with self._lock:
           self._tasks[task_id] = bt
           if name:
               self._by_name[name] = task_id  # 后启动覆盖前

       events: asyncio.Queue = asyncio.Queue(maxsize=64)
       aggregator = asyncio.create_task(self._aggregate_task_events(events, bt))

       async def runner() -> None:
           try:
               text = await ag.run_to_completion(conv, task_text, events)
               bt.result = text
               bt.status = Status.COMPLETED
           except asyncio.CancelledError:
               bt.status = Status.CANCELLED
               raise
           except BaseException as e:
               bt.status = Status.FAILED
               bt.err = e
           finally:
               bt.end_time = time.monotonic()
               aggregator.cancel()
               try:
                   self._done.put_nowait(task_id)
               except asyncio.QueueFull:
                   print(f"task manager: done queue full, dropping notification for {task_id}",
                         file=sys.stderr)

       bt.handle = asyncio.create_task(runner())
       return task_id
   ```
2. 实现 `_aggregate_task_events(queue: asyncio.Queue, bt: BackgroundTask)`:每个 Tool PhaseStart 累加 `tool_count` + 更新 `last_activity`;每个 Usage 累加到 `bt.usage`

**验证:** `pytest tests/task/test_manager.py::test_launch -v` 通过(T22)

## T21: Manager.stop / adopt_running / send_message / upgrade_approval**文件:** `src/gcode/task/manager.py`
**依赖:** T20
**步骤:**
1. 实现 `async def stop(self, task_id: str) -> bool`:查 `_tasks` → 调 `bt.handle.cancel()`;返回是否找到
2. 实现 `async def adopt_running(...)`:与 `launch` 类似但接收已存在的 `ag` / `conv` / `events` / `handle` / `partial`;创建 `BackgroundTask`,把 `PartialState` 字段复制进去,起协程继续消费 events 并跑动(注意此时 `ag.run_to_completion` 已经在前台启动;前台超时后子协程仍然在跑;adopt 实际上是注册 BackgroundTask 状态、聚合事件、等 events 队列关闭后写终态、push done)
   - 简化方案:adopt 不重新调 `run_to_completion`(因为已在前台启动);只是注册 BackgroundTask 状态、聚合事件、等 events 队列收到 sentinel 后写终态、push done
   - `handle` 是 `asyncio.create_task` 返回的 Task,stop 时 `handle.cancel()`
3. 实现 `async def send_message(self, name: str, message: str) -> str`:
   - 查 `_by_name` → task_id
   - 查 `get(task_id)` → bt;`bt.status != COMPLETED` → raise `TaskBusy`
   - `bt.conv.add_user(message)`;`bt.status = Status.RUNNING`;`start_time` / `end_time` 不重置
   - 重新起协程跑 `run_to_completion`(同样的 ag / conv);跑完逻辑同 launch
   - 返回 task_id
4. 实现 `async def upgrade_approval(self, req: ApprovalRequest) -> tuple[PermissionOutcome, bool]`:把 req 转发到一个全局队列(`self._approval_q: asyncio.Queue[ApprovalRequest]`);TUI 消费;返回 `(_, False)` 时调用方走默认路径
   - 简化:本期 `upgrade_approval` 直接返回 `(PermissionOutcome.DENY_ONCE, False)`——让 Approval 走到子 Agent 自己的 events 队列,TUI 通过 events 转发感知

**验证:** `pytest tests/task/test_manager.py::test_stop -v` 通过

## T22: task 包测试**文件:** `tests/task/test_manager.py`
**依赖:** T20, T21
**步骤:**
1. 用 mock provider + mock agent 模拟一个 sub_agent → `launch` → 等 `subscribe_done().get()` → 验证 `status=COMPLETED`, `result` 正确
2. 用一个故意抛异常的 mock agent → `launch` → done 收到 → `status=FAILED`,`err` 非空
3. `stop`:`launch` 后立刻 `stop` → done 收到 → `status=CANCELLED`
4. `send_message`:`launch` + 等 `COMPLETED` → `send_message` 重新跑 → 拿到新结果
5. `_by_name` 覆盖:`launch` 两次同 name → 后启动覆盖

**验证:** `pytest tests/task/test_manager.py -v` 全部通过

## T23: 4 个后台任务工具**文件:** `src/gcode/task/tools.py`
**依赖:** T19, T20, T21
**步骤:**
1. 实现 `TaskListTool(Tool)`:
   - `name = "TaskList"`,`read_only = True`,`parameters()` 空对象
   - `execute`:返回 JSON 形如 `[{"id":"...","name":"...","status":"running","tool_count":3,"last_activity":"bash"}, ...]`
2. 实现 `TaskGetTool(Tool)`:
   - `name = "TaskGet"`,`parameters()` 含 `task_id` required
   - `execute`:`get(id)` → 全字段 JSON;找不到 → `is_error=True`
3. 实现 `TaskStopTool(Tool)`:
   - `name = "TaskStop"`,`parameters()` 含 `task_id` required
   - `execute`:`await m.stop(id)` → `{"status":"cancellation_requested"}` 或 错误
4. 实现 `SendMessageTool(Tool)`:
   - `name = "SendMessage"`,`parameters()` 含 `name` / `message` required
   - `execute`:`await m.send_message(ctx, name, msg)` → `{"task_id":"...","status":"resumed"}` 或 错误
5. 所有工具实现 `is_system` 属性(返回 True),让它们在子 Agent 工具列表中默认豁免

**验证:** `pytest tests/task/test_tools.py -v` 通过(T24)

## T24: 4 个工具的单测**文件:** `tests/task/test_tools.py`
**依赖:** T23
**步骤:**
1. TaskList:`launch` 几个任务后调 → 返回 JSON 含所有
2. TaskGet:已知 id → 返回完整字段
3. TaskGet:未知 id → `is_error=True`
4. TaskStop:`stop` 一个 running task → 返回成功 + task 状态变 `CANCELLED`
5. SendMessage:`launch` 一个任务跑完 → `send_message` → 返回新 status

**验证:** `pytest tests/task/ -v` 全部通过

## T25: TUI 加 task_mgr / subagent_catalog wiring**文件:** `src/gcode/tui/app.py`
**依赖:** T6, T19, T23
**步骤:**
1. 在 `GCodeApp.__init__` 加形参:
   ```python
   def __init__(self, ..., task_mgr: task.Manager,
                subagent_catalog: subagent.Catalog) -> None:
       super().__init__()
       self.task_mgr = task_mgr
       self.subagent_catalog = subagent_catalog
   ```
2. 在 `on_mount()` 内:
   - 启动 `asyncio.create_task(self._consume_task_done())`
3. 在 `Agent` 构造之后(单 provider 路径):
   - 主 Agent 也应该携带 `approval_upgrader`(其实主 Agent 不需要;但 Agent 工具构造时需要 `approval_upgrader` 给子 Agent 用)
   - Agent 工具的 parent 通过 `set_parent(self.main_agent)` 回填

**验证:** `python -c "from gcode.tui.app import GCodeApp"` 导入无误

## T26: task notification 注入**文件:** `src/gcode/tui/tasks.py`
**依赖:** T19, T25
**步骤:**
1. 新建文件,实现:
   ```python
   async def consume_task_done(self) -> None:
       q = self.task_mgr.subscribe_done()
       while True:
           task_id = await q.get()
           bt = self.task_mgr.get(task_id)
           if bt is None:
               continue
           notif = build_task_notification(bt)
           if self.runtime is not None:
               self.runtime.append_reminders([notif])
   ```
2. 实现 `build_task_notification(bt: BackgroundTask) -> str`:
   ```
   <task-notification>
   Task <id> (name="<name>"): <status>
   Result: <result 或 错误>
   </task-notification>
   ```
3. docstring 解释行为(F19)
4. 把方法 `_consume_task_done` 挂到 `GCodeApp` 上(单独文件模块化,然后在 `app.py` `from .tasks import consume_task_done`)

**验证:** `python -c "from gcode.tui.tasks import build_task_notification"` 导入无误

## T27: ESC 切后台**文件:** `src/gcode/tui/stream.py`
**依赖:** T19, T25
**步骤:**
1. 在 `GCodeApp` 类挂 Textual binding:
   ```python
   BINDINGS = [("escape", "esc_pressed", "Cancel / send to background")]

   async def action_esc_pressed(self) -> None:
       if self.state is SessionState.STREAMING and self.foreground_sub_agent is not None:
           # 移交后台
           task_id = await self.task_mgr.adopt_running(
               self.foreground_sub_agent.agent,
               self.foreground_sub_agent.conv,
               self.foreground_sub_agent.name,
               self.foreground_sub_agent.events,
               self.foreground_sub_agent.handle,
               self.foreground_sub_agent.partial,
           )
           self.foreground_sub_agent = None
           # 显示一条通知
           self.notify(f"[esc] 子 Agent 切到后台 (task={task_id})")
   ```
2. 增加 `foreground_sub_agent` 字段到 `GCodeApp` 跟踪当前前台子 Agent;Agent 工具开始前台跑动时设置,跑完清除
3. 注意:前台子 Agent 的跑动其实是在 Agent 工具的 `execute` 内 `await` 阻塞的,主 TUI 此时是 "等 tool_result" 状态。这意味着 ESC 拦截需要在 Agent 工具的 `execute` 内通过 `self.foreground_sub_agent` 共享状态

**简化方案:** 由于前台子 Agent 在 Agent 工具同步 `await` 阻塞内,ESC 切后台需要工具内监听 cancellation。本期实现保守版:Agent 工具的前台路径只支持「超时自动切后台」,不支持 ESC 切后台;ESC 切后台留待后续 ch14+ 完善。在 plan.md 与 spec.md 里要标注这一变更。

**重要变更:** F17/AC11 调整为:本期 ESC 切后台**不实现**,只实现「超时自动切后台」与「显式 run_in_background」。spec.md 已写出,checklist 跳过 ESC 场景。

修改方向:跳过 T27 的 ESC 部分,只保留 `foreground_sub_agent` 字段供未来扩展。

**验证:** `python -c "import gcode.tui.stream"` 导入无误

## T28: Skill fork 改造**文件:** `src/gcode/tui/skill_fork.py`
**依赖:** T15
**步骤:**
1. 现有 `run_sub_agent` 内部已经在用 `sub_agent.run`;改造为用 `run_to_completion`:
   ```python
   async def run_sub_agent(self, conv: Conversation,
                           opts: skills.ForkOptions) -> str:
       if self.provider is None:
           raise SubAgentNoProvider()

       prov = self.provider
       # (model 切换逻辑保留)

       sub_runtime = SessionRuntime(200_000)
       sub_agent = Agent(
           provider=prov,
           registry=self.registry,
           version=self.version,
           engine=self.engine,
           runtime=sub_runtime,
           allowed_tools=opts.allowed_tools,
           hook_engine=self.hook_engine,
       )

       # 直接调 run_to_completion(events=None,前台同步)
       return await sub_agent.run_to_completion(conv, "", events=None)
       # conv 末尾已含 user task,task="" 触发 run_to_completion 跳过 add_user
   ```
2. **注意**:现有 `skills.Executor` 调用前已经把任务作为 user 消息装填到 conv(`_build_fork_conversation` 末尾 `conv.add_user(rendered)`)。新版 `run_to_completion` 内部又会 `conv.add_user(task)`;若 task="" 会追加空消息。**改 `run_to_completion` 为允许 task="" 时不追加**(`if task: conv.add_user(task)`),或者改 `skills.Executor` 不再装填 user 消息让 `run_to_completion` 装填
3. 选第一种方案——`run_to_completion` 加 if 判断

**验证:** `pytest tests/skills/ tests/tui/ -v` 现有测试不破

## T29: Agent 工具注册到 registry**文件:** `src/gcode/cli.py`
**依赖:** T17, T20, T23, T25
**步骤:**
1. 在 `cli.main` 适当位置(`skills.load_catalog` 之后):
   ```python
   subagent_catalog = subagent.load_catalog(root)
   task_mgr = task.Manager()

   # 4 个 task 工具
   registry.register(task.TaskListTool(task_mgr))
   registry.register(task.TaskGetTool(task_mgr))
   registry.register(task.TaskStopTool(task_mgr))
   registry.register(task.SendMessageTool(task_mgr))

   # Agent 工具(parent 暂为 None,稍后 set_parent)
   agent_tool = AgentTool(subagent_catalog, task_mgr, parent=None,
                          bg_enabled=cfg.effective_enable_subagent_background())
   registry.register(agent_tool)
   ```
2. `GCodeApp(...)` 构造时传入 `task_mgr` / `subagent_catalog`:
   ```python
   app = GCodeApp(
       ...,
       writer=writer,
       mem_mgr=mem_mgr,
       instruction_text=instruction_text,
       memory_text=memory_text,
       sessions_dir=sessions_dir,
       catalog=catalog,
       hook_engine=hook_engine,
       task_mgr=task_mgr,
       subagent_catalog=subagent_catalog,
   )
   ```
3. `GCodeApp` 构造后回填 parent:
   ```python
   if app.main_agent is not None:
       agent_tool.set_parent(app.main_agent)
   ```
4. `GCodeApp` 加 `main_agent` 属性返回 `self.agent`

**验证:** `python -m gcode --help` 不报错;`ruff check src/gcode/cli.py` 无告警

## T30: config 加 enable_subagent_background**文件:** `src/gcode/config.py`
**依赖:** 无
**步骤:**
1. 在 `Config` `@dataclass` 加字段:
   ```python
   enable_subagent_background: bool | None = None  # YAML key: enableSubAgentBackground
   ```
2. 加 `effective_enable_subagent_background()` 方法:
   ```python
   def effective_enable_subagent_background(self) -> bool:
       if self.enable_subagent_background is None:
           return True
       return self.enable_subagent_background
   ```
3. docstring 说明:默认 True;False 时所有 SubAgent 强制前台,Fork 路径会报错

**验证:** `pytest tests/test_config.py -v` 通过

## T31: agent.launch_fork 公用 wiring**文件:** `src/gcode/agent/launch.py`
**依赖:** T6, T15, T17
**步骤:**
1. 新建 `launch.py`,实现:
   ```python
   @dataclass
   class ForkLaunchOpts:
       allowed_tools: list[str]
       model: str
       conv: Conversation       # 已装填的子对话
       system_prompt: str
       background: bool
       events_sink: asyncio.Queue | None
       provider: Provider
       registry: Registry
       engine: PermissionEngine
       version: str
       hook_engine: HookEngine

   async def launch_fork(opts: ForkLaunchOpts) -> str: ...
   ```
2. 实现细节:
   - 构造 `SessionRuntime` / `Agent`(类似 `agent_tool` 的前台路径)
   - 调 `run_to_completion(opts.conv, "", events=opts.events_sink)`(conv 已含 task)
   - 返回 final_text(异常透传)
3. **避免循环依赖**:本来 plan 设想 `subagent.launch_fork` 引用 agent 包;但 `agent_tool` 又 import subagent → 形成循环依赖
4. **最终方案**(在文件结构里也已对齐):
   - `Definition` 类型放在 `gcode.subagent`
   - `launch_fork` 放在 `gcode.agent`(因为它要构造 `Agent`)
   - `AgentTool` 也放 `gcode.agent`(已有)
   - `tui/skill_fork.py` 调 `gcode.agent.launch_fork`(把 `Definition` 或裸参数传入)

**重新调整文件结构:**
- 删除 `src/gcode/subagent/launch.py`(本任务取消)
- 新建 `src/gcode/agent/launch.py` 实现 `launch_fork`
- skills 的 fork 回调改为调 `agent.launch_fork`

**验证:** 见 T28 验证

## T32: 集成测试 - 完整路径**文件:** `tests/agent/test_agent_tool_integration.py`(新增)
**依赖:** T17, T20, T29
**步骤:**
1. 端到端 mock:构造一个 mock provider 让主 Agent 调 Agent 工具(`subagent_type="Explore"`),子 Agent 也跑回纯文本
2. 验证 tool_result 包含子 Agent 的 final_text
3. 验证子 Agent 工具调用没看到 Agent 工具(过滤生效)
4. 验证后台路径:`run_in_background=True` → 立即返回 `async_launched` JSON,主 Agent 继续

**验证:** `pytest tests/agent/test_agent_tool_integration.py -v` 通过

## T33: 编译与综合测试**依赖:** T1-T32
**步骤:**
1. `uv sync`(确保依赖装好)
2. `ruff check src/gcode/`
3. `ruff format --check src/gcode/`
4. `mypy src/gcode/`(可选)
5. `pytest tests/ -v`

**验证:** 全部命令通过,无失败用例

## 执行顺序

```
T1 → T2 → T3
       ↘
        T5 → T6 → T7
       ↗
       T4
T8 → T9
T10 → T11 → T14
T10 → T12 → T13
T14, T15 → T16
T8, T12, T15 → T17 → T18
T19 → T20 → T21 → T22
T19 → T20 → T23 → T24
T6, T19, T23 → T25 → T26
T25 → T27(本期跳过 ESC)
T15 → T28
T30 → T29
T29 → T32
所有 → T33
```
````

````markdown
# SubAgent 机制 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### subagent 包

- [ ] `gcode.subagent` 包存在且可导入(验证:`python -c "import gcode.subagent"`)
- [ ] `Definition` 数据类包含 `name / description / tools / disallowed_tools / model / max_turns / permission_mode / dont_ask / background / system_prompt / file_path / source` 全部字段(验证:`pytest tests/subagent/test_parser.py::test_definition_fields -v`)
- [ ] `parse_definition` 能正确解析合法 frontmatter + body,`permissionMode=dontAsk` 时 `dont_ask=True`(验证:`pytest tests/subagent/test_parser.py -v`)
- [ ] `parse_definition` 对 frontmatter 缺 name / description 抛错,model 非法 fallback 到 inherit 并 stderr 警告(验证:对应测试通过)
- [ ] 内置 3 个文件(general-purpose / explore / plan)在 `builtin/` 目录下,`importlib.resources` 读取成功(验证:`pytest tests/subagent/test_catalog.py::test_builtin -v`)
- [ ] `load_catalog` 按 builtin → user → project 顺序加载,同名高优先级覆盖(验证:`pytest tests/subagent/test_catalog.py -v`)
- [ ] `Catalog.resolve("Explore")` 在三层覆盖场景下返回正确 `source`(验证:对应测试通过)
- [ ] `Catalog.fork_definition()` 返回 `is_fork() is True` 的临时 `Definition`(验证:对应测试通过)

### tool 过滤多层防线

- [ ] `tool.ALL_AGENT_DISALLOWED_TOOLS` / `CUSTOM_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 三个常量存在(验证:`pytest tests/tool/test_filter.py::test_constants -v`)
- [ ] `apply_agent_tool_filter` 按 spec F30 顺序应用五层过滤(验证:`pytest tests/tool/test_filter.py -v`)
- [ ] 后台模式下,工具集与 `ASYNC_AGENT_ALLOWED_TOOLS` 取交集,Agent / TaskList / SendMessage 等元工具被剔除(验证:对应测试用例通过)
- [ ] MCP 工具(`mcp__` 前缀)在后台模式下被保留(验证:对应测试用例通过)

### agent 包扩展

- [ ] `Agent.__init__` 接受 `system_prompt / max_turns / permission_mode / dont_ask / approval_upgrader / provider` 6 个新关键字参数且生效(验证:`pytest tests/agent/test_options.py -v`)
- [ ] `build_forked_messages` 正确克隆父消息 + 处理悬空 tool_use + 追加 Boilerplate(验证:`pytest tests/agent/test_fork.py -v`)
- [ ] `is_fork_context` 能识别消息中含 `<fork_boilerplate>` 标签(验证:对应测试通过)
- [ ] `Agent.run_to_completion` 能跑完一轮非交互循环,返回最后一条 assistant 文本(验证:`pytest tests/agent/test_run_to_completion.py -v`)
- [ ] `run_to_completion` 触达 `max_turns` 时 raise `MaxTurnsReached`(验证:对应测试通过)
- [ ] `dont_ask` 模式下,工具 Ask 决策被自动转 Allow(验证:对应测试通过)
- [ ] `approval_upgrader` 回调在 Ask 决策时被命中(验证:对应测试通过)
- [ ] `run_to_completion` 把 events 转发到外部 `asyncio.Queue`,Tool / Text / Approval 事件可被消费(验证:对应测试通过)

### Agent 工具

- [ ] `AgentTool` 构造后 `name = "Agent"`,`parameters()` 含 `prompt / description / subagent_type / model / run_in_background / name` 字段(验证:`pytest tests/agent/test_agent_tool.py::test_basic -v`)
- [ ] `AgentTool.execute` 缺少 prompt 时返回错误(验证:对应测试通过)
- [ ] `AgentTool.execute` 未知 `subagent_type` 时返回错误(验证:对应测试通过)
- [ ] `AgentTool.execute` 定义式 subagent 调用走前台 `run_to_completion`,返回 final_text(验证:对应测试通过)
- [ ] `AgentTool.execute` `run_in_background=True` 时返回 `{"task_id":"...","status":"async_launched"}` JSON(验证:对应测试通过)
- [ ] `AgentTool.execute` 在子 Agent context 内被再次调用时拦截(验证:嵌套阻断测试通过)
- [ ] `AgentTool.execute` 检测到 conv 含 fork boilerplate 时拦截(验证:对应测试通过)
- [ ] `AgentTool.execute` `enable_subagent_background=False` 时,`run_in_background=True` 与 fork 路径报错(验证:对应测试通过)

### task 包

- [ ] `task.Manager.launch` 起协程跑 `run_to_completion`,跑完写 `status=COMPLETED`,push done(验证:`pytest tests/task/test_manager.py::test_launch -v`)
- [ ] `task.Manager.launch` 协程内异常时,`status=FAILED`,`err` 含异常信息,主程序不崩(验证:对应测试通过)
- [ ] `task.Manager.stop` 触发 `bt.handle.cancel()`,协程退出后 `status=CANCELLED`(验证:对应测试通过)
- [ ] `task.Manager.send_message` 在已 completed 的任务上重新跑动,新 user 消息追加到 conv(验证:对应测试通过)
- [ ] `task.Manager._by_name` 后启动覆盖前,`get(_by_name[name])` 返回最新 task(验证:对应测试通过)
- [ ] `subscribe_done()` 返回的队列在 task 完成时收到 id(验证:对应测试通过)

### 4 个 task 工具

- [ ] `TaskListTool` 返回当前所有任务的 JSON 列表(验证:`pytest tests/task/test_tools.py::test_task_list -v`)
- [ ] `TaskGetTool` 返回指定任务的完整字段;未知 id 返回 `is_error=True`(验证:对应测试通过)
- [ ] `TaskStopTool` 调用 `manager.stop`,返回成功 JSON(验证:对应测试通过)
- [ ] `SendMessageTool` 调用 `manager.send_message`,返回 resumed JSON(验证:对应测试通过)
- [ ] 4 个工具都实现 `is_system` 属性,`is_system is True`(验证:工具列表过滤时它们对子 Agent 仍可见——实际上 ASYNC 白名单优先,在后台子 Agent 中**仍然不可见**;对前台定义式子 Agent 通过 `ALL_AGENT_DISALLOWED` 不在其中)

### TUI 集成

- [ ] `GCodeApp` 持有 `task_mgr` 与 `subagent_catalog` 字段(验证:`python -c "import gcode.tui.app"`)
- [ ] `on_mount` 启动 `_consume_task_done` 协程,任务完成时把 `<task-notification>` 注入 `runtime.pending_reminders`(验证:`pytest tests/tui/test_consume_task_done.py -v`)
- [ ] `tui/skill_fork.py` 改造为调 `agent.run_to_completion` 而非自己拼装循环(验证:现有 skills 测试不破)
- [ ] `cli.main` 注册 4 个 task 工具 + 1 个 Agent 工具,`subagent_catalog` 与 `task_mgr` 传给 `GCodeApp`(验证:`python -m gcode --help` 不报错)
- [ ] `Config` 新增 `enable_subagent_background` 字段(验证:`pytest tests/test_config.py -v`)

## 集成

- [ ] `subagent.Catalog` 与 `tool.apply_agent_tool_filter` 协同工作:`resolve` 拿到 def,过滤函数按 `def.source / background / tools / disallowed_tools` 收窄(验证:`test_agent_tool_integration.py` 通过)
- [ ] Agent 工具的前台调用与现有 ch11 Skill fork 路径不互相干扰(验证:skills 包测试通过 + 手动 tmux 验证一个 inline skill 与一个 Agent 工具调用)
- [ ] Hook 引擎在子 Agent 内仍生效(PreToolUse / PostToolUse 在 `run_to_completion` 内被调用)(验证:hook 包测试 + 子 Agent 跑动手动断言 hook 触发)
- [ ] 主 Agent 工具列表里仍含 `Agent` + `TaskList` + `TaskGet` + `TaskStop` + `SendMessage` 共 5 个新工具,数量稳定(验证:工具数计数测试)

## 编译与测试

- [ ] 项目可启动:`python -m gcode --help`
- [ ] lint 通过:`ruff check src/gcode/`
- [ ] 格式化通过:`ruff format --check src/gcode/`
- [ ] 类型检查通过(可选):`mypy src/gcode/`
- [ ] 所有单元测试通过:`pytest tests/`

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

### 场景 1:定义式子 Agent(Explore)前台同步**预置:** 无须额外配置。当前目录 `cd /Users/codemelo/gcode`。

**步骤:**
- [ ] tmux 启动 gcode:`tmux new-session -d -s ch13 -x 200 -y 50 "uv run gcode"`
- [ ] 给 LLM 输入:「用 Explore 子 Agent 找出 `src/gcode/permission` 包下所有以 `test_` 开头的函数,只统计数量,不要修改任何文件」
- [ ] LLM 应触发 Agent 工具,`subagent_type="Explore"`,`run_in_background` 未设
- [ ] scrollback 内出现 `● Agent(...)` 工具行,几秒后 Result 行展示子 Agent 的最终文本(含 `test_*` 函数数量)
- [ ] tmux 抓屏(`tmux capture-pane -p -t ch13`)断言:输出包含 `Agent(` 工具行 + 数量数字
- [ ] 验证不改文件:`git status` 干净

### 场景 2:Fork 子 Agent 后台执行**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮:让 LLM 读一些文件铺垫上下文,如「读 `src/gcode/agent/agent.py` 头 50 行」
- [ ] 第二轮:「Fork 出去一个子 Agent,统计这个项目里 Python 文件总行数(不指定 subagent_type)」
- [ ] LLM 应触发 Agent 工具,`subagent_type` 留空 → Fork 路径
- [ ] tool_result 应立即返回 `{"task_id":"task_xxx","status":"async_launched"}`
- [ ] 主对话立刻可以继续(输入 `/status` 应能响应)
- [ ] 等 10-30 秒,主对话下一次响应时 reminder 区出现 `<task-notification>` 块,含 Result(行数统计)
- [ ] 用 LLM 验证:「主 Agent,你刚刚有没有收到 task-notification?显示一下」

### 场景 3:主 Agent 用 TaskList / TaskGet 查询**预置:** 接场景 2 之后,或者重启 gcode 后先 launch 一个长跑任务。

**步骤:**
- [ ] 调用一个会跑较久的子 Agent:「用 `run_in_background=True`,让一个 general-purpose 子 Agent 阅读 `src/gcode` 下所有 `.py` 文件 head 200 行,生成总结」
- [ ] 主 Agent 立即返回 task_id
- [ ] 输入:「调 TaskList 看现在有什么后台任务」
- [ ] LLM 调 TaskList 工具,scrollback 显示 task 列表 JSON 含 id / name / status=running / tool_count
- [ ] 输入:「调 TaskGet 看这个任务详情」
- [ ] LLM 调 TaskGet,显示完整字段含 start_time / tool_count / last_activity 等
- [ ] 等几秒后:「再调 TaskGet 一次」
- [ ] 验证 status 变化或 `tool_count` 增长

### 场景 4:TaskStop 取消任务**步骤:**
- [ ] 同场景 3 起一个 long-running 任务,拿到 task_id
- [ ] 立刻输入:「调 TaskStop 把刚才那个任务停掉」
- [ ] LLM 调 TaskStop 工具
- [ ] 几秒后:`TaskGet` 应显示 `status=cancelled`
- [ ] 主对话下次 turn 的 reminder 区出现 task-notification 含 `status=cancelled`

### 场景 5:权限决策 - dontAsk 兜底**预置:** 创建项目级自定义 agent:
```
.gcode/agents/auto-bash.md
---
name: auto-bash
description: 自动批准 Bash 调用的测试 Agent
permissionMode: dontAsk
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑,不要询问。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default)
- [ ] 输入:「用 auto-bash 子 Agent 跑 `echo hello-from-subagent`」
- [ ] LLM 调 Agent 工具 `subagent_type=auto-bash`
- [ ] 子 Agent 内部调 bash,**不应该弹出审批弹窗**
- [ ] tool_result 含 `hello-from-subagent` 文本

### 场景 6:权限决策 - 升级到主 TUI**预置:** 创建一个不含 dontAsk 的子 Agent:
```
.gcode/agents/ask-bash.md
---
name: ask-bash
description: 默认权限模式的测试 Agent
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default,未预先批准 echo)
- [ ] 输入:「用 ask-bash 子 Agent 跑 `echo from-ask-bash`」
- [ ] LLM 调 Agent 工具 `subagent_type=ask-bash`
- [ ] 子 Agent 调 bash 时,**主 TUI 应该弹出审批弹窗**(本期通过子 Agent 的 ApprovalRequest 直接 emit;`upgrade_approval` 默认返回 `(_, False)` 走默认路径,Approval 由 inline 路径 emit 到 TUI)
- [ ] 用户选 Allow Once → 子 Agent 继续 → tool_result 含 `from-ask-bash`

### 场景 7:嵌套阻断 - 定义式子 Agent 看不到 Agent 工具**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent。Explore 内部应该尝试再调用 Agent 工具(比如 prompt 写成『再调用一个 Plan 子 Agent』)」
- [ ] Explore 子 Agent 跑动期间,因为工具列表里没有 Agent 工具,LLM 应该报告「无法调用 Agent」或自己直接做
- [ ] tool_result 不应包含「Agent 工具未注册」一类错误——因为它根本看不到这个工具(被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除)

### 场景 8:嵌套阻断 - Fork 子 Agent 调 Agent 工具被拦截**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「Fork 一个子 Agent,prompt 写『再 fork 一个子 Agent 阅读 README.md』」
- [ ] 主 Agent Fork 出去后立即返回 task_id
- [ ] 等几秒,task-notification 显示子 Agent Result 含「Fork 子 Agent 不能再启动 Agent」错误回灌后的处理结果(或子 Agent 自行调整不再尝试)
- [ ] 调 TaskGet 看子 Agent Result;或 TaskList 看 last_activity

### 场景 9:SendMessage 续派任务**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 `run_in_background=True name=worker1` 起一个 general-purpose 子 Agent,任务是『列出 `src/gcode/cli.py` 的 import 块』」
- [ ] 主 Agent 收到 task_id,等几秒后 task-notification 显示 Result(imports 列表)
- [ ] 输入:「调 SendMessage 给 worker1 发『再列出 `src/gcode/agent/agent.py` 头 20 行』」
- [ ] LLM 调 SendMessage 工具,`manager.send_message` 重新激活 worker1
- [ ] 等几秒后,task-notification 又显示新 Result(头 20 行)

### 场景 10:超时自动切后台**预置:** 临时把 `AUTO_BACKGROUND_SECONDS` 改成 5 秒(代码常量调小做测试,或加配置项)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 general-purpose 子 Agent,任务是『等 30 秒,然后回复 hello』(让子 Agent 用 bash sleep 30 触发长跑)」
- [ ] Agent 工具前台等 5 秒后超时,tool_result 返回 `{"task_id":"...","status":"timed_out_to_background"}`
- [ ] 主对话可以继续接收输入
- [ ] 等够 30 秒后,task-notification 注入主对话含 hello

> 测试完恢复 `AUTO_BACKGROUND_SECONDS=120`

### 场景 11.5:全新自定义子 Agent 端到端

> 验证项目级自定义 Agent 文件被加载、resolve 命中、frontmatter 全字段生效、system_prompt 注入到子 Agent。
> 与场景 5 / 6 / 11 区别:那三条聚焦权限 / 覆盖语义,本条验证"全新角色"作为新增能力。

**预置:** 创建 `.gcode/agents/wc-counter.md`:
```yaml
---
name: wc-counter
description: 行数统计专家,只用 wc -l 计行,然后总结
disallowedTools:
  - write_file
  - edit_file
permissionMode: dontAsk
maxTurns: 5
---

你是一个专门统计代码行数的 Agent。
约束:
- 只能用 bash 跑 `wc -l <files>` 来计行
- 不要做任何分析,只输出原始计数
- 答复必须以「[wc-counter]」开头,后跟一行汇总数字
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 `subagent_type=wc-counter`,任务: 统计 `README.md` 和 `src/gcode/cli.py` 的行数」
- [ ] 主 Agent 触发审批后选「允许本次」(主 Agent 调 Agent 工具自身的权限)
- [ ] 子 Agent 跑动,**不应弹任何审批框**(验证 `dont_ask` 生效)
- [ ] tool_result 内容以 `[wc-counter]` 开头,含 wc 计数(验证 system_prompt 注入生效)
- [ ] 子 Agent 工具列表内不含 `write_file` / `edit_file`(验证 disallowedTools 生效)
- [ ] 子 Agent 最多 5 轮即终止(验证 maxTurns 生效;实际单轮就完事)

### 场景 11.6:自定义 Agent 字段错误降级**预置:** 创建 `.gcode/agents/bad.md` 含非法字段:
```yaml
---
name: bad
description: 字段错误测试
model: gpt-4   # 不在 inherit/haiku/sonnet/opus 中
permissionMode: weirdMode
---

body
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] stderr(启动时)应出现两条警告:`unknown model "gpt-4" ... defaulting to inherit` 与 `unknown permissionMode "weirdMode" ... defaulting to default`
- [ ] gcode 正常启动,不阻断
- [ ] 输入:「用 Agent 工具调 `subagent_type=bad`,任务: 回个 hi」
- [ ] 子 Agent 仍能正常跑(model 降级 inherit、mode 降级 default 后,工具集与权限按降级值)
- [ ] **测试完删除 `.gcode/agents/bad.md`**### 场景 11:角色文件覆盖**预置:** 创建 `.gcode/agents/explore.md`:
```
---
name: Explore
description: 项目级覆盖的 Explore
maxTurns: 10
---

你是项目级覆盖的 Explore Agent。无论用户问什么,先回答 "[project-level-explore]" 然后再回答正常内容。
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent 列出 `README.md` 的第一行」
- [ ] tool_result 应包含 `[project-level-explore]` 标记(证明项目级覆盖了内置 Explore)
- [ ] 删除 `.gcode/agents/explore.md`,重启 gcode,再次跑 → 不再含此标记
````

### Java

````markdown
# SubAgent 机制 Spec## 背景

GCode 目前是单 Agent 架构：所有任务在同一个对话上下文里执行。这导致两个问题：

1. **上下文污染**：长任务后再做无关任务,前序中间结果(读过的文件、diff、错误回放)成为后续任务的噪声,token 飙升、响应质量下降
2. **无法并行**：没有把独立子任务分发出去并行执行的机制,主对话被长任务阻塞

gcode 已经有「子 Agent 雏形」：

- ch11 Skill fork 模式通过 `agent.WithAllowedTools` 创建受限子 Agent(tui/SkillFork.java `runSubAgent`),走 `subAgent.run(...)` 跑完一轮
- `Conversation.fromMessages` / `replaceMessages` 已支持深拷贝消息列表

但还缺：
- 没有统一的、可被主 Agent 主动调用的 **Agent 工具**——子 Agent 只能由 Skill fork 触发
- 没有 **角色定义文件** 加载机制(Agent 角色全部写死在 fork 闭包里)
- 没有 **后台任务管理**——所有子 Agent 当前都是阻塞前台模式
- 没有 **工具过滤多层防线**——子 Agent 理论上可以无限嵌套
- Skill fork 与未来 SubAgent 工具两套代码并存

本章把上述能力补齐,让 gcode 从单 Agent 进化到可分发任务的主从架构。

## 目标- **G1**:提供统一的 Agent 工具,主 Agent 通过 `subagent_type` 参数选择预定义角色或留空走 Fork 路径;工具列表对模型始终稳定(不因角色定义增减而变化)
- **G2**:子 Agent 拥有独立的运行时状态——**消息**、**权限账本**(独立 Engine 决策状态)、**文件读缓存**、**token 计数**;共享基础设施——LLM 客户端、Hook 引擎、文件系统、`ToolRegistry`
- **G3**:支持两种创建模式:
  - **定义式**:指定 `subagent_type`,从空白对话 + 预定义角色 prompt 启动
  - **Fork 式**:不指定 `subagent_type`,克隆父对话历史并注入 Fork Boilerplate,借 prompt cache 降首次请求成本
- **G4**:角色定义为 Markdown + YAML frontmatter 文件;支持多来源加载,优先级:项目级 > 用户级 > 内置 > 插件;同名定义按 source 优先级覆盖,前者覆盖后者
- **G5**:子 Agent 以 **RunToCompletion** 模式执行——任务直接注入对话,模型不再调工具即结束,返回最后一条 assistant 文本作为结果
- **G6**:子 Agent 在工具调用时遇到权限判定,按 **三层升级链** 处理:① 父对话已批准账本 → ② 角色 frontmatter 的 `permissionMode` 兜底 → ③ 仍无法决定时升级到主 TUI 询问用户(子 Agent 暂停、用户响应、子继续)
- **G7**:支持后台任务:三种进入方式——① 显式 `run_in_background:true`、② 前台超时 120 秒自动切后台、③ ESC 手动切后台;Fork 路径无条件后台;Fork Boilerplate 注入到子 Agent 首条消息约束其行为
- **G8**:后台任务跑完通过 `<task-notification>` 自动注入主对话(主 Agent 下次 turn 即看到);主 Agent 可通过 `TaskList`/`TaskGet`/`TaskStop` 工具主动查询和操控,可通过 `SendMessage` 给已跑完的、仍存活的后台 Agent 续派任务
- **G9**:工具过滤多层防线阻断子 Agent 无限嵌套——全局禁止列表(子 Agent 永远不能用 Agent 工具)、后台白名单(后台 Agent 只能用基础读写网络工具)、定义层 `tools`/`disallowedTools` 业务约束
- **G10**:复用 SubAgent 底座统一 Skill fork 路径——`tui/SkillFork.java` 的 `runSubAgent` 改为调用 SubAgent 公共启动函数,两条路径走同一段 agent 构造逻辑
- **G11**:内置 3 个角色——`general-purpose`(全工具)、`Explore`(只读探索,haiku)、`Plan`(只读规划);插件级保留接口占位但本期不实现真插件加载,加载顺序里插件来源恒为空

## 功能需求### Agent 工具- **F1**:新建 `Agent` 工具,参数(JSON Schema):
  - `prompt`(string,必填):交给子 Agent 的任务指令
  - `description`(string,必填):一句话描述任务,供 UI 展示
  - `subagent_type`(string,可选):指定预定义角色名,留空时走 Fork 路径
  - `model`(string,可选):模型覆盖,取值 `haiku` / `sonnet` / `opus` / `inherit`;留空沿用 Agent 定义的 model
  - `run_in_background`(bool,可选):true 时强制后台启动;Fork 路径忽略此字段(无条件后台)
  - `name`(string,可选):给本次启动的子 Agent 命名,供 SendMessage 用;同名后启动的覆盖前面的弱引用
- **F2**:Agent 工具的 `execute`:
  - subagent_type 非空:`catalog.resolve(name)` 取定义;不存在则返回结构化错误「未知 subagent_type: X」
  - subagent_type 为空:走 Fork 路径,从 `catalog` 取「fork 默认基础定义」(prompt body=Fork Boilerplate)
  - 按 `run_in_background` 与 Fork 强制规则,选择 inline 跑(阻塞返回 finalText)或 background 跑(返回 `{task_id, status:"async_launched"}`)
- **F3**:Agent 工具被全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS` 标记——任何子 Agent 都看不到 Agent 工具,从根源上断绝嵌套

### Agent 定义文件- **F4**:Agent 定义文件是 Markdown,以 `---` frontmatter 块开头、紧跟正文(子 Agent 系统提示);frontmatter YAML 字段:
  - `name`(必填):角色名,小写字母 / 数字 / 连字符,长度 1-32
  - `description`(必填):一句话描述,用于 Agent 工具的 `subagent_type` 文档与 UI 列表
  - `tools`(可选,string array):工具白名单
  - `disallowedTools`(可选,string array):工具黑名单
  - `model`(可选):`haiku` / `sonnet` / `opus` / `inherit`,缺省 `inherit`
  - `maxTurns`(可选,int):最大迭代轮数,缺省继承全局 `maxIterations=25`
  - `permissionMode`(可选):`default` / `acceptEdits` / `plan` / `bypassPermissions` / `dontAsk`,缺省 `default`;`dontAsk` 是子 Agent 专属——自动批准所有规则未命中的工具
  - `background`(可选,bool):缺省 false;true 时 Agent 工具忽略 `run_in_background` 参数、强制后台
- **F5**:Catalog 三层加载(本期插件级恒为空),顺序:
  1. 项目级:`<root>/.gcode/agents/*.md`
  2. 用户级:`~/.gcode/agents/*.md`
  3. 内置级:Jar 内 classpath resource `subagent/builtin/*.md`(`Class.getResourceAsStream`)
- **F6**:同名定义按 source 优先级覆盖——项目级 > 用户级 > 内置级;`resolve(name)` 返回优先级最高的版本
- **F7**:Catalog 启动期加载,加载失败的单个文件(frontmatter 不合法、name 重名以外的字段错)走 stderr 警告并跳过,不阻断启动
- **F8**:本章不引入插件加载器——`SourcePlugin` 常量保留供未来扩展;加载顺序里第四层恒为空 List

### 子 Agent 运行时- **F9**:扩展 `agent.Agent` 增加 `runToCompletion(ctx, conv, task) -> String` 方法:
  - 把 `task` 作为 user 消息追加到 conv
  - 进入 ReAct 循环,maxTurns 由 `Agent.maxTurns` 决定(子 Agent 用 frontmatter,主 Agent 不变=25)
  - 模型不再调工具时结束循环,取末尾 assistant 文本返回
  - 触达 maxTurns 时返回最后一条 assistant 文本 + 「达到最大轮数」异常
  - 同一段循环代码与主对话 `run` 共用,不重复实现
- **F10**:新增 Agent Builder 选项:
  - `systemPrompt(text)`:子 Agent 启动时把 text 作为 system prompt 注入(覆盖默认 gcode 主 Agent 系统提示)
  - `provider(p)`:让子 Agent 用与父不同的 provider(model 覆盖时切换)
  - `maxTurns(n)`:限制本 Agent 的最大迭代轮数
  - `permissionMode(m)`:子 Agent 启动模式
  - `parentEngine(eng)`:子用父 Engine 做权限决策一级查找(本期所有 Agent 共享同一 Engine,但增加显式参数预留隔离扩展)
- **F11**:子 Agent 的运行时状态隔离——独立 `SessionRuntime`、独立 `Conversation`、独立 token 计数;但共享 `Provider`(除非 `provider()` 覆盖)、`ToolRegistry`、`PermissionEngine`、`HookEngine`

### 权限决策- **F12**:子 Agent 工具调用权限决策三层链(在 `runGuarded` 内分支):
  1. 父对话已批准账本——父 Engine 已经 `persistLocalAllow` 过的精确规则匹配 → Allow
  2. 子角色 `permissionMode` 兜底——`dontAsk` 模式直接放行所有 Allow/Ask 类规则未命中的;`acceptEdits` 放行写;`bypassPermissions` 全 Allow(黑名单/沙箱仍拦);其他模式仍走原 `modeFallback`
  3. 三层之外仍是 Ask——升级到主 TUI:子 Agent 暂停,主 TUI 弹审批框(标注 `[来自 SubAgent X]`),用户响应后子 Agent 继续;Outcome 沿用现有三选一(DenyOnce/AllowOnce/AllowForever)
- **F13**:升级到主 TUI 的通信机制——子 Agent 把 `ApprovalRequest` emit 到自己的 `Flow.Publisher` 事件流,事件流被 `TaskManager` / `SkillFork` host 转发到主 TUI 的 Approval 弹窗;主 TUI 响应后 Outcome 通过 `CompletableFuture<Outcome>` 回传

### 后台任务管理- **F14**:新建 `task.Manager`,持有 `Map<String, BackgroundTask>`,提供 `launch(ctx, agent, taskText) -> taskID`、`get(id)`、`list()`、`stop(id)`、`adoptRunning(...)`、`subscribeDone() -> Flow.Publisher<String>`
- **F15**:`BackgroundTask` 字段:
  - `id`(String,manager 生成)
  - `name`(String,可选,F1 的 `name` 字段)
  - `subAgent`(Agent)
  - `conv`(Conversation,子对话)
  - `task`(String,初始任务)
  - `status`(`RUNNING` / `COMPLETED` / `FAILED` / `CANCELLED`)
  - `result`(String,跑完后填)
  - `err`(Throwable)
  - `startTime` / `endTime`(Instant)
  - `cancelFlag`(`AtomicBoolean` 或 `volatile boolean`,虚线程 cancel 钩子)
  - `usage`(`TokenUsage`,token 计数)
  - `toolCount`(int,工具调用次数计数器)
  - `lastActivity`(String,最近一次工具名)
- **F16**:`launch` 内部 virtual thread:`subAgent.runToCompletion(ctx, conv, task)` → status 终态 → 推 `taskID` 到 `Flow.Publisher<String>` → TUI 消费后注入 `<task-notification>`
- **F17**:三种进入后台的方式:
  1. **显式**:Agent 工具 `run_in_background:true` → 直接调 `launch`,工具 result 立刻返回 `{task_id, status:"async_launched"}`
  2. **超时自动**:Agent 工具默认前台 inline 跑,但前台 run 启动后开计时器(120 秒,常量 `AUTO_BACKGROUND_MS`),超时则:
     - 取消前台 publisher 订阅
     - 调 `manager.adoptRunning(agent, conv, ctx, cancelFlag, eventPublisher, partial)` 接管事件流继续后台跑
     - Agent 工具 result 改返回 `{task_id, status:"timed_out_to_background"}`
  3. **ESC 手动切**:用户在前台子 Agent 跑动期间按 ESC → TUI 调 `manager.adoptRunning(...)`,与超时路径走同一逻辑
- **F18**:Fork 路径 `run_in_background` 字段被强制视为 true(代码内 override)
- **F19**:后台任务完成时,Manager 把 `taskID` push 到 `Flow.Publisher<String>` done sink;TUI 在主事件循环消费,把如下文本作为 system reminder 拼到主对话下一次 reminder 区(不打断当前对话):
  ```
  <task-notification>
  Task X (name="Y"): completed
  Result: <最终文本>
  </task-notification>
  ```

### 后台任务工具- **F20**:新增 4 个内置工具:
  - `TaskList`:无参,返回当前 manager 中所有非 Terminated 任务的简要列表(id、name、status、tool_count、last_activity)
  - `TaskGet`:`{task_id}`,返回指定任务的完整状态(含 result / err)
  - `TaskStop`:`{task_id}`,调 `manager.stop` 触发取消;返回 `{status:"cancellation_requested"}`
  - `SendMessage`:`{name, message}`,按 name 找到仍存活的后台 Agent(status=COMPLETED,conv 仍在内存),把 message 作为新 user 消息追加到 conv 并重新 `launch` 一轮跑动;找不到 / 已 CANCELLED 返回错误
- **F21**:本期不实现 `TaskCreate`(主要给 Hook 用,Hook 暂未需要 SubAgent action);保留 manager API,Hook subagent stub 也可暂未对接

### Fork 路径- **F22**:`buildForkedMessages(parentConv)` 做三件事:
  1. 深拷贝 parentConv 的全部消息
  2. 把末尾 assistant 中未完成的 `tool_use`(无对应 ToolResult)包装为 placeholder ToolResult,使消息格式合法
  3. 在末尾追加 user 消息,内容 = Fork Boilerplate + 任务文本
- **F23**:Fork Boilerplate 是一段 `<fork_boilerplate>` 包裹的指令,核心约束:
  - 不能再 Fork(再 Fork 会被 QuerySource 拦截 / Boilerplate 标记扫描兜底)
  - 不要对话 / 提问 / 请求确认
  - 直接使用工具
  - 严格限制在分配的任务范围内
  - 最终报告以 `Scope:` 开头,500 字以内
- **F24**:Fork 子 Agent 嵌套阻断三道闸:
  1. **工具列表层**:Fork 子 Agent 的工具列表保留 Agent 工具(继承自父),但调用 Agent 工具时
  2. **QuerySource 检测**:Agent 工具入口检测 caller 来源(检查父链),若 caller 是 Fork 路径产生,直接 `isError=true` 返回「Fork 子 Agent 不能再启动 Agent」
  3. **Boilerplate 标记扫描**:对话历史里如果含 `<fork_boilerplate>` 标记(QuerySource 失效兜底),也认定是 Fork 嵌套
- **F25**:定义式子 Agent 不走 Boilerplate(从空白启动);嵌套阻断靠 `ALL_AGENT_DISALLOWED_TOOLS` 全局禁止 Agent 工具

### 工具过滤多层防线- **F26**:全局禁止列表 `ALL_AGENT_DISALLOWED_TOOLS = ["Agent"]`(本期范围最小,后续可加 AskUserQuestion / TaskStop);所有子 Agent 启动时从工具列表中剔除这些
- **F27**:自定义 Agent 额外限制 `CUSTOM_AGENT_DISALLOWED_TOOLS`:本期为空,接口预留(用于将来用户自定义 Agent 一律不可访问某些核心工具)
- **F28**:后台 Agent 白名单 `ASYNC_AGENT_ALLOWED_TOOLS`,只列基础工具:
  `read_file, write_file, edit_file, glob, grep, bash, load_skill, install_skill`
  以及所有 MCP / Skill 工具。Fork/run_in_background 任意一种成立的子 Agent 工具集再叠加此白名单交集。
- **F29**:Agent 定义层 `tools`(白名单)与 `disallowedTools`(黑名单)组合应用——白名单先确定范围,黑名单再排除
- **F30**:工具过滤合并执行顺序(在 Agent 工具的 `execute` 内,子 Agent 构造时):
  1. 起点 = registry 的全部工具
  2. 去掉 `ALL_AGENT_DISALLOWED_TOOLS`
  3. 如果是后台 → 取交集 `ASYNC_AGENT_ALLOWED_TOOLS`
  4. 应用定义的 `disallowedTools` 黑名单
  5. 应用定义的 `tools` 白名单(空白名单 = 不再收窄)
  6. 注入到子 Agent 的 `Agent.builder().allowedTools(allowed)`
- **F31**:工具列表对模型稳定——以上过滤只发生在子 Agent 构造时,主 Agent 看到的工具列表不变

### 内置角色与 Skill fork 改造- **F32**:内置 3 个角色文件,作为 classpath resource 打入 jar:
  - `general-purpose.md`:无 disallowedTools,用 `inherit` 模型,maxTurns=30,permissionMode=default
  - `explore.md`:disallowedTools=[write_file, edit_file],model=haiku,maxTurns=30,permissionMode=default
  - `plan.md`:disallowedTools=[Agent, write_file, edit_file],maxTurns=15,permissionMode=plan(plan 是已有的权限模式)
- **F33**:Skill fork 改造——`tui/SkillFork.java` 的 `runSubAgent` 改为:
  1. 构造一个临时 `subagent.Definition`(name="skill-fork-<skillname>",disallowedTools=skill.allowedTools 反推 / 等同 skill 自身的 allowedTools),将其当 Fork 路径走
  2. 复用 `Agent.runToCompletion` 与 SubAgent 的工具过滤、消息装填路径
  3. 返回 finalText 行为不变(`host.appendAssistantMessage` 仍由 Executor 调)

## 非功能需求- **N1**:工具列表稳定——主 Agent 看到的工具集不因 `.gcode/agents/` 增减或 Agent 工具被调用而变化(防止 prompt cache 抖动)
- **N2**:Fork 路径首次请求命中 prompt cache——`buildForkedMessages` 拼接的消息列表与父对话末尾完全一致,系统提示一致
- **N3**:子 Agent 崩溃不影响主程序——`Manager.launch` 的 virtual thread 包 try/catch,任何 `Throwable` 转 `status=FAILED` + 错误信息回灌
- **N4**:启动期 fail-fast——内置定义 classpath 资源解析失败立刻抛 `RuntimeException`(代码 bug),用户/项目级定义文件解析失败仅 stderr 警告并跳过
- **N5**:与现有 ch11 Skill 系统、ch12 Hook 系统、ch08 权限系统、ch04 主 Agent loop 协同,不破坏既有测试
- **N6**:配置 `enableSubAgentBackground`(boolean,默认 true)关闭后,Agent 工具的 `run_in_background:true` / 超时切后台 / ESC 切后台全部失效,所有 SubAgent 强制前台同步;Fork 路径在此模式下报错「后台禁用,无法 Fork」
- **N7**:`<task-notification>` 注入主对话不消耗主 Agent 的工具调用配额,不出现在用户视窗(只对模型可见)

## 不做的事

- Worktree 文件隔离(独立章节)
- 多 Agent 团队编排(CrewAI / AutoGen 平等协作风格)
- 后台任务跨会话持久化——主程序退出后任务全部丢失
- 真正的插件系统(`SourcePlugin` 占位)
- 子 Agent 输出 schema 强制结构化(返回纯文本即可)
- Verification Agent 内置开关(`enableVerificationAgent` 不实现)
- `TaskCreate` 工具(本期仅 List/Get/Stop/SendMessage)
- 跨 SubAgent token 用量汇总到 /status(只在 Manager 内部记录)

## 验收标准- **AC1**:Agent 工具注册成功,主 Agent 的工具列表里 schema 一致;子 Agent 看不到 Agent 工具
- **AC2**:`Agent` 工具调用 `{prompt:"...",subagent_type:"Explore"}` 时,主 Agent 看到的 tool_result 是 Explore 子 Agent 的最后一条 assistant 文本
- **AC3**:`Agent` 工具调用 `{prompt:"...",subagent_type:"non-existent"}` 时,主 Agent 看到的 tool_result 是结构化错误「未知 subagent_type」
- **AC4**:`Agent` 工具调用不传 subagent_type 时,子 Agent 收到的首条 user 消息以 `<fork_boilerplate>` 起头,且消息列表前缀与父对话一致(可由测试断言)
- **AC5**:Fork 子 Agent 的工具列表里仍有 Agent 工具(F22 设计),但调用 Agent 工具会被 QuerySource 拦截,tool_result 含「Fork 子 Agent 不能再启动 Agent」
- **AC6**:定义式子 Agent 的工具列表里没有 Agent 工具(被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除)
- **AC7**:子 Agent 角色 frontmatter 写 `permissionMode: dontAsk`,Bash 等需要 Ask 的工具直接放行,无审批弹窗
- **AC8**:子 Agent 角色 frontmatter 不写 dontAsk,Bash 工具触发审批,弹窗带 `[来自 SubAgent X]` 标识
- **AC9**:`run_in_background:true` 时 tool_result 立即返回 `{task_id, status:"async_launched"}`,主 Agent 不阻塞
- **AC10**:前台子 Agent 跑超过 120 秒,自动切后台,主 Agent 看到 tool_result 含 `status:"timed_out_to_background"`
- **AC11**:前台子 Agent 跑动期间用户按 ESC,切到后台,TUI 继续接收主 Agent 输入
- **AC12**:后台子 Agent 跑完,主 Agent 下次 run 的 reminder 区出现 `<task-notification>` 块,含 result
- **AC13**:`TaskList` 工具返回当前后台任务列表,字段含 id/name/status/tool_count
- **AC14**:`TaskGet({task_id})` 返回 result;`TaskStop({task_id})` 触发取消,任务 status 变 CANCELLED
- **AC15**:`SendMessage({name,message})` 让一个仍存活的后台 Agent 接到新任务并重新跑动,跑完结果作为新 `<task-notification>` 注入主对话
- **AC16**:项目级 `.gcode/agents/explore.md` 覆盖内置 `explore`,`resolve("explore")` 返回项目级版本
- **AC17**:Skill fork 模式调用走 SubAgent 底座——`tui/SkillFork.java` 的 `runSubAgent` 内部只是装饰参数后调 `subagent.LaunchFork.launch(...)`(或同等公共函数)
- **AC18**:N6 配置开关 `enableSubAgentBackground:false` 时,Fork 路径调用 Agent 工具返回结构化错误
- **AC19**:`<fork_boilerplate>` 出现在对话历史里 + Agent 工具被调用 → 拦截(QuerySource 失效兜底)
- **AC20**:子 Agent throw → status=FAILED,主 Agent 收到 `<task-notification>` 含错误描述,主程序不崩
- **AC21**:全新项目级自定义 Agent(`.gcode/agents/<name>.md`)被 Catalog 加载;`subagent_type=<name>` 调用时,frontmatter 的 disallowedTools / permissionMode / maxTurns / systemPrompt 全部生效——子 Agent 看不到黑名单工具、按指定 mode 决策、不超 turns、按 systemPrompt 行事
- **AC22**:Agent 定义 frontmatter 的非法字段(unknown model / unknown permissionMode)在加载时 stderr 警告并 fallback 到默认值(model→inherit, mode→default),gcode 不阻断启动,该 Agent 仍可被 resolve 与调用
````

````markdown
# SubAgent 机制 Plan## 架构概览

本章实现拆为四个层次：

1. **subagent 包**（新增,核心数据层）——定义 Agent 角色的数据结构、Markdown+YAML 解析、Catalog 多来源加载、内置角色 classpath resource
2. **task 包**（新增,后台运行层）——`task.Manager` 管理后台任务生命周期,4 个内置工具(TaskList/TaskGet/TaskStop/SendMessage)
3. **agent 包扩展**——新增 `runToCompletion` 方法、5 个新 Builder 选项、Fork 路径辅助函数 `buildForkedMessages`、子 Agent 权限升级 callback
4. **工具与 TUI 集成层**——Agent 工具实现、工具过滤多层防线常量、TUI 接入 task notification、ESC 切后台、Skill fork 改造为复用 SubAgent 底座

模块构成：

- `subagent.Definition` / `subagent.Catalog` / `subagent.Source` — 数据结构与三层加载
- `subagent/builtin/*.md` — 内置 3 个角色文件,放在 `src/main/resources/subagent/builtin/`,通过 classpath resource 读取
- `task.Manager` / `task.BackgroundTask` — 后台任务管理与生命周期
- `task` 包内 4 个 `Tool` 实现 — 注册到 `ToolRegistry`
- `Agent.runToCompletion` / `Agent.Builder.systemPrompt / provider / maxTurns / permissionMode / approvalUpgrader` — Agent 包扩展
- `agent.Fork` — `buildForkedMessages`、Fork Boilerplate 常量
- `agent.AgentTool` — Agent 工具实现
- `tool.Filter` — `ALL_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 常量与过滤函数
- `tui` 改动 — TaskManager 注入、ESC 切后台、`<task-notification>` 注入、子 Agent 审批弹窗
- `tui/SkillFork.java` 改造 — 复用 `subagent.LaunchFork`

## 核心数据结构### subagent.Definition

```java
package dev.gcode.subagent;

import dev.gcode.permission.PermissionMode;

/**
 * Definition 是一个 Agent 角色的完整定义,从 Markdown + YAML frontmatter 解析。
 * 字段对齐 spec F4。
 */
public record Definition(
        String name,             // frontmatter.name (-> agentType)
        String description,      // frontmatter.description (-> whenToUse)
        java.util.List<String> tools,             // frontmatter.tools 白名单;空表示不收窄
        java.util.List<String> disallowedTools,   // frontmatter.disallowedTools 黑名单
        String model,            // "haiku" | "sonnet" | "opus" | "inherit";缺省 "inherit"
        int maxTurns,            // 0 表示沿用全局默认 (25)
        PermissionMode permissionMode, // "dontAsk" 单独处理(见 dontAsk 字段)
        boolean dontAsk,         // 是否启用"绕过 Ask"的子 Agent 兜底模式
        boolean background,      // 强制后台
        String systemPrompt,     // Markdown body(去 frontmatter 后的全文)
        String filePath,         // 定义文件绝对路径 / classpath uri(用于调试)
        Source source            // Source.BUILTIN / USER / PROJECT / PLUGIN
) {
    public boolean isFork() {
        return "__fork__".equals(name);
    }
}

public enum Source {
    BUILTIN, USER, PROJECT, PLUGIN; // 占位

    @Override
    public String toString() {
        return switch (this) {
            case BUILTIN -> "builtin";
            case USER    -> "user";
            case PROJECT -> "project";
            case PLUGIN  -> "plugin";
        };
    }
}
```

### subagent.Catalog

```java
package dev.gcode.subagent;

public final class Catalog {
    private final Object lock = new Object();
    private final java.util.Map<String, Definition> defs = new java.util.HashMap<>();
    private final java.util.EnumMap<Source, java.util.List<Definition>> bySource = new java.util.EnumMap<>(Source.class);

    /**
     * 顺序加载:builtin -> user -> project,优先级高的覆盖低的;
     * 解析错误走 stderr 警告并跳过;返回非 null Catalog 即使无任何定义。
     */
    public static Catalog load(java.nio.file.Path root) { ... }

    public java.util.Optional<Definition> resolve(String name) { ... }
    public java.util.List<Definition> list() { ... } // 按 name 排序
    public java.util.List<Definition> listBySource(Source s) { ... }

    /**
     * forkDefinition 返回一个"Fork 路径"用的临时 Definition——name="__fork__",systemPrompt="" (子 Agent 走继承的系统提示),
     * 但 disallowedTools 不应包含 Agent 工具(Fork 子 Agent 工具集保留 Agent,靠 QuerySource 阻断)。
     */
    public Definition forkDefinition() { ... }
}
```

### task.Manager 与 BackgroundTask

```java
package dev.gcode.task;

/**
 * BackgroundTask 是一个后台子 Agent 的完整状态快照。
 */
public final class BackgroundTask {
    final String id;                 // manager 生成,如 "task_<8 字节十六进制>"
    final String name;               // F1 中 Agent 工具 name 参数,可空
    final dev.gcode.agent.Agent subAgent;
    final dev.gcode.conversation.Conversation conv;
    final String task;               // 初始任务文本(SendMessage 不更新此字段)
    volatile Status status;          // RUNNING / COMPLETED / FAILED / CANCELLED
    volatile String result;          // 跑完的最终文本
    volatile Throwable err;
    final java.time.Instant startTime;
    volatile java.time.Instant endTime;
    final java.util.concurrent.atomic.AtomicBoolean cancelFlag;
    volatile Usage usage;            // 累计 token
    final java.util.concurrent.atomic.AtomicInteger toolCount;
    volatile String lastActivity;    // 最近一次工具名
    // 省略 getters
}

public enum Status { RUNNING, COMPLETED, FAILED, CANCELLED }

public record Usage(long input, long output, long cacheWrite, long cacheRead) {}

/**
 * Manager 管理后台任务。线程安全。
 */
public final class Manager {
    private final Object mu = new Object();
    private final java.util.Map<String, BackgroundTask> tasks = new java.util.HashMap<>();
    private final java.util.Map<String, String> byName = new java.util.HashMap<>(); // name -> id,弱引用,后启动的覆盖
    private final java.util.concurrent.SubmissionPublisher<String> donePub =
            new java.util.concurrent.SubmissionPublisher<>(); // 缓冲 32

    public Manager() { /* SubmissionPublisher 构造时设置 maxBufferCapacity */ }

    /**
     * launch 起一个后台 virtual thread 跑 agent.runToCompletion;conv 应该是已经装填了消息的子对话。
     * 返回 ID;virtual thread 内部跑完后写 status/result + submit 到 donePub。
     */
    public String launch(java.util.concurrent.atomic.AtomicBoolean parentCancel,
                         dev.gcode.agent.Agent ag,
                         dev.gcode.conversation.Conversation conv,
                         String name, String task) { ... }

    /**
     * adoptRunning 把一个正在前台跑的 agent 移交到后台。
     * 调用方应已经把"用户的 ESC / 120 秒超时"对应的 cancelFlag 准备好,
     * 并把已 partial 收集的事件吐到 partial 内。Manager 接管 eventSub 事件流继续消费,直到 Done 或 Err。
     */
    public String adoptRunning(java.util.concurrent.atomic.AtomicBoolean parentCancel,
                               dev.gcode.agent.Agent ag,
                               dev.gcode.conversation.Conversation conv,
                               String name,
                               java.util.concurrent.Flow.Subscription eventSub,
                               java.util.concurrent.atomic.AtomicBoolean cancelFlag,
                               PartialState partial) { ... }

    /** PartialState 是前台→后台移交时已收集的中间状态。 */
    public record PartialState(String lastAssistantText, int toolCount, String lastActivity, Usage usage) {}

    public java.util.Optional<BackgroundTask> get(String id) { ... }
    public java.util.List<BackgroundTask> list() { ... } // 按 startTime 升序
    public boolean stop(String id) { ... }

    /**
     * subscribeDone 返回 publisher;TUI 订阅,收到 id 后调 get 拿状态,
     * 把 <task-notification> 拼到 runtime.pendingReminders。
     */
    public java.util.concurrent.Flow.Publisher<String> subscribeDone() { return donePub; }

    /**
     * sendMessage 给一个仍存活的后台 Agent 续派任务。
     * 找不到 name -> 抛 TaskNotFoundException;status != COMPLETED -> 抛 TaskBusyException。
     * 成功时把 message 加到 conv,重新 launch 一个新轮(返回同 id,状态从 COMPLETED 重置回 RUNNING)。
     */
    public String sendMessage(java.util.concurrent.atomic.AtomicBoolean parentCancel,
                              String name, String message) throws TaskNotFoundException, TaskBusyException { ... }
}
```

### agent 包扩展

```java
package dev.gcode.agent;

public final class Agent {

    // ───── 新增方法 ─────

    /**
     * runToCompletion 执行子 Agent 的"跑到底"循环。
     * 复用主 run 的几乎所有逻辑(streamOnce / executeBatched / 权限判定),区别:
     *   - 不通过 publisher 返回事件(内部消费),最终返回 finalText
     *   - maxTurns 由 a.maxTurns 决定(若 0 则用 MAX_ITERATIONS)
     *   - 不触发 memory update / 不触发 compact reminder 等主对话专属逻辑(子 Agent 上下文短,
     *     不需要;但内部依然走 manageContextAuto 防止超长)
     *   - 接受一个可选的 events publisher,把内部事件(text/tool/approval)转发出去——
     *     TaskManager 借此聚合 toolCount/lastActivity,TUI 借此渲染前台子 Agent 的进度
     */
    public String runToCompletion(java.util.concurrent.atomic.AtomicBoolean cancelFlag,
                                  dev.gcode.conversation.Conversation conv,
                                  String task,
                                  java.util.concurrent.SubmissionPublisher<Event> events) throws Exception { ... }

    // ───── 新增 Builder 选项 ─────

    public static final class Builder {
        // ... 已有
        public Builder systemPrompt(String text) { ... }           // 子 Agent 角色 prompt
        public Builder provider(dev.gcode.llm.Provider p) { ... }
        public Builder maxTurns(int n) { ... }
        public Builder permissionMode(dev.gcode.permission.PermissionMode m) { ... }
        public Builder dontAsk(boolean enabled) { ... }            // 子 Agent dontAsk 模式
        public Builder approvalUpgrader(ApprovalUpgrader fn) { ... } // 升级到父 TUI 的 callback
        public Builder parentRegistry(dev.gcode.tool.ToolRegistry r) { ... } // 暂时与 registry 等价,显式区分语义
    }

    /**
     * ApprovalUpgrader 是子 Agent 把审批请求升级到父 TUI 的回调。
     * 实现方:TaskManager 把请求转发到主 TUI 的事件流;前台 inline 模式直接复用现有 Approval 路径。
     * 返回 Optional.empty() 表示不接管,调用方继续走默认路径。
     */
    @FunctionalInterface
    public interface ApprovalUpgrader {
        java.util.Optional<dev.gcode.permission.Outcome> upgrade(
                java.util.concurrent.atomic.AtomicBoolean cancelFlag,
                ApprovalRequest req);
    }
}
```

`Agent` 类新增字段:
- `systemPrompt`(String) — 非空时 `buildEnvText` / `buildSystemPrompt` 阶段用此覆盖默认
- `maxTurns`(int) — 0 表示用全局 `MAX_ITERATIONS`
- `permissionMode`(PermissionMode) — 子 Agent 启动模式(主 Agent 用 TUI 的运行时 mode)
- `dontAsk`(boolean)
- `approvalUpgrader`(ApprovalUpgrader)

### Fork.java 内容

```java
package dev.gcode.agent;

public final class Fork {

    public static final String FORK_BOILERPLATE_TAG = "<fork_boilerplate>";

    /** ForkBoilerplate 是 Fork 子 Agent 首条 user 消息的前缀,约束其行为。 */
    public static final String FORK_BOILERPLATE = """
            <fork_boilerplate>
            你是一个 Fork 出来的工作进程。你不是主 Agent。
            规则(不可协商):
            1. 不能再 Fork(调用 Agent 工具会被拦截)。
            2. 不要对话、不要提问、不要请求确认。
            3. 直接使用工具:读文件、搜索代码、做修改。
            4. 严格限制在你被分配的任务范围内。
            5. 最终报告以 "Scope:" 开头,500 字以内。
            </fork_boilerplate>

            """;

    /**
     * buildForkedMessages 把父对话克隆到 Fork 子对话,处理悬空 tool_use,追加 Boilerplate+task。
     * 行为:
     *   1. 深拷贝 parentMsgs(所有 Message + 内部 toolCalls/toolResults List)
     *   2. 扫描末尾 assistant 消息的 toolCalls,如果对应的 ROLE_TOOL 消息缺失,
     *      生成一条 placeholder ROLE_TOOL 消息(每个 ID 对一条"[forked, skipped]" 错误内容)
     *   3. 追加 user 消息 = FORK_BOILERPLATE + task
     * 返回新消息列表,直接用 Conversation.fromMessages 装载即可。
     */
    public static java.util.List<dev.gcode.llm.Message> buildForkedMessages(
            java.util.List<dev.gcode.llm.Message> parentMsgs, String task) { ... }

    /**
     * isForkContext 判定一个 conversation 的消息历史是否来自 Fork(用 FORK_BOILERPLATE_TAG 扫描)。
     * QuerySource 检测的兜底机制——caller 链丢失时靠这个。
     */
    public static boolean isForkContext(java.util.List<dev.gcode.llm.Message> msgs) { ... }
}
```

### Agent 工具

`dev/gcode/agent/AgentTool.java`：

```java
package dev.gcode.agent;

/**
 * AgentTool 是注册到 ToolRegistry 的统一 Agent 工具。
 */
public final class AgentTool implements dev.gcode.tool.Tool {
    private final AgentCatalogPort catalog;     // 接口,避免反向依赖 subagent 包
    private final TaskManagerPort taskMgr;
    private volatile Agent parentAgent;         // 取 provider/registry/eng/runtime 等
    private final boolean bgEnabled;            // N6 配置开关

    public AgentTool(AgentCatalogPort catalog, TaskManagerPort mgr, Agent parent, boolean bgEnabled) { ... }
    public void setParent(Agent a) { this.parentAgent = a; }

    @Override public String name() { return "Agent"; }
    @Override public boolean readOnly() { return false; }  // 子 Agent 可能做任何事
    @Override public String description() {
        // 列出已知的 subagent_type 名,从 catalog.list() 渲染
        ...
    }

    /**
     * execute 主流程:
     *   1. 解析 args -> AgentArgs(prompt, description, subagentType, model, runInBackground, name)
     *   2. 校验:prompt 非空、description 非空
     *   3. 检测嵌套:从 ctx 取 ParentInfo,若 parent 已是子 Agent 或对话历史含 fork tag -> 返回错误
     *   4. resolve 定义:subagentType 非空走 catalog.resolve,空走 catalog.forkDefinition
     *   5. 决定 background:def.background || args.runInBackground || (是 fork)
     *   6. 应用工具过滤多层防线 Filter.applyAgentToolFilter,得到 allowed List<String>
     *   7. 选 provider:args.model 非空 -> 切;否则 def.model 非 inherit -> 切;否则用 parent
     *   8. 构造子 Agent + 子 Conversation(空白或 Fork 路径装填消息)
     *   9. 前台路径:开 cancelFlag + ScheduledFuture(120s 超时),跑 runToCompletion;
     *      - 完成 → 返回 finalText
     *      - 超时/ESC → adoptRunning,返回 {task_id, status:"timed_out_to_background"}
     *  10. 后台路径:launch,返回 {task_id, status:"async_launched"}
     */
    @Override
    public dev.gcode.tool.Result execute(dev.gcode.tool.ExecutionContext ctx, com.fasterxml.jackson.databind.JsonNode args) { ... }
}
```

### 工具过滤多层防线

`dev/gcode/tool/Filter.java`:

```java
package dev.gcode.tool;

public final class Filter {

    /**
     * ALL_AGENT_DISALLOWED_TOOLS 是任何子 Agent 永远不能用的工具名列表。
     * 本期最小列表:Agent。后续可扩展 AskUserQuestion / TaskStop / 系统级敏感工具。
     */
    public static final java.util.List<String> ALL_AGENT_DISALLOWED_TOOLS = java.util.List.of("Agent");

    /**
     * CUSTOM_AGENT_DISALLOWED_TOOLS 是自定义(user / project / plugin 来源)Agent 比内置 Agent 多禁用的工具。
     * 本期为空。
     */
    public static final java.util.List<String> CUSTOM_AGENT_DISALLOWED_TOOLS = java.util.List.of();

    /**
     * ASYNC_AGENT_ALLOWED_TOOLS 是后台 Agent 工具白名单。
     * 不含 Agent / TaskStop / SendMessage / TaskList / TaskGet 等任何元工具。
     */
    public static final java.util.List<String> ASYNC_AGENT_ALLOWED_TOOLS = java.util.List.of(
            "read_file", "write_file", "edit_file",
            "glob", "grep",
            "bash",
            "load_skill", "install_skill"
    );
    // MCP 工具与 Skill 工具按工具命名约定动态识别(以 "mcp__" 起头 / 来自 registerSkillTool),
    // 通过 isAllowedInBackground 函数走另一条分支判定。

    /** FilterParams 是过滤一个 Agent 的工具列表的参数。 */
    public record FilterParams(
            java.util.List<String> all,        // registry 的全部工具名(按注册顺序)
            int source,                        // 1=builtin, 2=user, 3=project, 4=plugin
            boolean background,
            java.util.List<String> allowed,    // Agent 定义 frontmatter.tools 白名单
            java.util.List<String> disallowed  // Agent 定义 frontmatter.disallowedTools 黑名单
    ) {}

    /**
     * applyAgentToolFilter 按 spec F30 顺序过滤。
     * 返回最终 allowed 列表(传给 Agent.Builder.allowedTools)。
     */
    public static java.util.List<String> applyAgentToolFilter(FilterParams p) { ... }
}
```

### TUI 集成层

`dev/gcode/tui/TuiApp.java` 改动：
- `TuiParams` record 加 `Manager taskMgr / Catalog subAgentCatalog`(由 Main 注入)
- `TuiApp` 持有 `taskMgr` / `subAgentCatalog`
- `init()` 末尾启动一个 virtual thread 订阅 `taskMgr.subscribeDone()`,把 `<task-notification>` 拼成 reminder 推到 `runtime.appendReminders`
- 主对话 Agent 通过 `Agent.Builder.approvalUpgrader(taskMgr::upgradeApproval)` 让子 Agent 审批升级回主 TUI

`dev/gcode/tui/Stream.java` 改动：
- `updateStreaming` 监听 ESC 键(Lanterna `KeyType.Escape`):若 `state==STREAMING` 且当前有运行中的 SubAgent → 调 `taskMgr.adoptRunning`,切回 IDLE 态
- 监听 SubAgent ApprovalRequest 转发——TaskManager 通过 events publisher 转回主 TUI 走现有 Approval 路径

`dev/gcode/tui/SkillFork.java` 改造：
- 删除现有 `runSubAgent` 内的零散逻辑
- 改为调 `subagent.LaunchFork.launch(ctx, host, opts, conv)`,host 持有 `taskMgr` / `runtime` / `engine` 等

## 模块设计### 模块 A:subagent 包**职责:**
- 数据结构 `Definition`
- Markdown + YAML 解析(复用 `skills.Parser` 的 `parseFrontmatterAndBody`——抽到 `util.markdown` 让两方共用 OR skills 与 subagent 都各自有一份)
- 三层 + 内置 classpath resource 加载

**对外接口:**
- `Catalog.load(Path root) -> Catalog`
- `Catalog.resolve(name)` / `list()` / `forkDefinition()`

**依赖:**
- `dev.gcode.permission`(解析 `permissionMode` 字段)
- `org.snakeyaml:snakeyaml-engine`
- JDK `java.nio.file`、`java.lang.Class#getResourceAsStream`

**关键设计:**
- Markdown 解析复用 `skills.Parser` 的 `parseFrontmatterAndBody`——抽到 `subagent.Parser` 独立实现一份(避免互相依赖),内容几乎一致
- 内置文件 `subagent/builtin/general-purpose.md` / `explore.md` / `plan.md` 放在 `src/main/resources/subagent/builtin/`,通过 `Catalog.class.getResourceAsStream("/subagent/builtin/<name>.md")` 加载
- 加载错误统一 stderr `System.err.printf("subagent %s: ... skipped%n", ...)`

### 模块 B:task 包**职责:**
- 后台任务生命周期管理
- 4 个内置工具(TaskList/TaskGet/TaskStop/SendMessage)

**对外接口:**
- `new Manager()`
- `launch / adoptRunning / get / list / stop / sendMessage / subscribeDone`
- `new TaskListTool(Manager m)` 等四个工厂

**依赖:**
- `dev.gcode.agent`(Agent)
- `dev.gcode.conversation`
- `dev.gcode.tool`
- `dev.gcode.llm`

**关键设计:**
- `donePub` 是 `SubmissionPublisher<String>`,`maxBufferCapacity` 设为 32 够大,正常场景不可能填满;真满时 `offer` 返回负数 → 走 stderr 警告(主 TUI 漏一条通知不致命)
- `launch` virtual thread 包 try/catch:`Throwable t` → status=FAILED,err=t
- `stop` 把 `task.cancelFlag` 置 true;`Agent.runToCompletion` 每轮检查
- `sendMessage`:仅当 `status == COMPLETED` 时允许;否则 `TaskBusyException`。重新 launch 时用 *同 id*,status 从 COMPLETED 重置回 RUNNING

### 模块 C:agent 包扩展**职责:**
- 新增 `runToCompletion` 方法
- 新增 5 个 Builder 选项
- Fork 路径辅助

**对外新增接口:**
- `Agent.runToCompletion(cancelFlag, conv, task, events) -> String`
- `Agent.Builder.systemPrompt / provider / maxTurns / permissionMode / dontAsk / approvalUpgrader`
- `Fork.buildForkedMessages`
- `Fork.isForkContext`

**关键设计:**
- `runToCompletion` 与 `run` 共用 `streamOnce` / `executeBatched` / `manageContextAuto` /
  `recordReadFileIfApplicable`,通过抽公共 helper 实现共享(把 `run` 的循环体抽到
  `runIter(cancelFlag, conv, mode, iter, ...)`,`run` 与 `runToCompletion` 都调它)
- 子 Agent 的 `permissionMode` + `dontAsk` 决策点在 `executeBatched` 的 `runGuarded` 内多一层短路:
  ```java
  if (a.dontAsk) {
      // 角色定义 dontAsk:走 sandbox/黑名单/规则后,默认 Allow 而非 Ask
      if (d == Decision.ASK) d = Decision.ALLOW;
  }
  ```
- 升级到父 TUI 的 callback 在 `requestApproval` 里调:
  ```java
  if (a.approvalUpgrader != null) {
      var maybe = a.approvalUpgrader.upgrade(cancelFlag, req);
      if (maybe.isPresent()) return maybe.get();
  }
  // 否则走默认 emit Approval event 路径(主 Agent inline 子 Agent 路径)
  ```

**Fork Boilerplate 注入策略:**
- `Fork.buildForkedMessages` 把 Boilerplate 写在 user 消息开头(与 ch13 README 一致)
- `Fork.isForkContext` 用 `String.contains` 扫描 *所有* 历史 user 消息内容寻找 `<fork_boilerplate>`(QuerySource 兜底)

### 模块 D:Agent 工具与 TUI 集成**职责:**
- 把 Agent 工具注册到 registry
- TUI 接入 task notification
- 改造 Skill fork

**对外接口:**
- `new AgentTool(catalog, taskMgr, parentAgent, bgEnabled)`
- `subagent.LaunchFork.launch(ctx, host, opts)` 公共 Fork 启动函数(Skill fork 与 Agent 工具都调)

**关键设计:**
- `AgentTool.execute` 在前台 inline 路径返回结果时要小心:
  - 前台跑完返回 finalText 作为 tool_result content
  - 中途超时切后台 → 返回 JSON `{"task_id":"...","status":"timed_out_to_background"}`
- 嵌套阻断:`AgentTool.execute` 入口检查 `ctx` 是否携带 `PARENT_AGENT_KEY`(子 Agent 启动时塞入);若有 → 返回结构化错误
  - 不依赖 ctx 单值:也扫 conv 历史是否含 Fork tag(`Fork.isForkContext`)
- TUI 的 task notification 注入:
  - `init()` 启动 `Thread.startVirtualThread(this::consumeTaskDone)`
  - `consumeTaskDone` 订阅 `donePub`,`get` 拿状态,渲染成 `<task-notification>` 块,调 `runtime.appendReminders` 推入
  - 主对话下一次 `run` 自动拿到(已有机制)

## 模块交互### 启动期 wiring

```
Main.java
  ├── new ToolRegistry()       → registry
  ├── new PermissionEngine(root) → engine
  ├── new SessionRuntime        → runtime
  ├── skills.Catalog.load      → skillCatalog
  ├── hook.HookEngine.load      → hookEngine
  ├── subagent.Catalog.load     → subagentCatalog          ← 新增
  ├── new task.Manager()        → taskMgr                  ← 新增
  ├── registry.register(new task.TaskListTool(taskMgr))    ← 新增
  ├── registry.register(new task.TaskGetTool(taskMgr))     ← 新增
  ├── registry.register(new task.TaskStopTool(taskMgr))    ← 新增
  ├── registry.register(new task.SendMessageTool(taskMgr)) ← 新增
  ├── new TuiApp(..., TuiParams(taskMgr, subagentCatalog, ...))
  │     │
  │     └── 在 TuiApp 构造内:Agent 工具的注册被推迟到主 Agent 构造后(因为要把 parentAgent 注入),
  │         或者 Agent 工具 lazy 拿:把 catalog/taskMgr 写死,parentAgent 通过 setParent 注入
```

**简化方案:** Agent 工具在 `Main.java` 注册,`parentAgent` 字段在 `new TuiApp(...)` 后回填:
```java
AgentTool agentTool = new AgentTool(subagentCatalog, taskMgr, null, cfg.enableSubAgentBackground());
registry.register(agentTool);
// 再 new TuiApp(...)
// 再 agentTool.setParent(tuiApp.mainAgent());
```

### 运行时:主 Agent 调 Agent 工具(前台,定义式)

```
LLM 流式产出 tool_use:{name:"Agent",input:{prompt:"...",subagent_type:"Explore"}}
    ↓
Agent.executeBatched → 路由到 AgentTool.execute(ctx, args)
    ↓
AgentTool.execute:
    1. 解析参数 -> AgentArgs
    2. 防嵌套:检测 ctx / conv 是否来自 Fork → 否
    3. resolve("Explore") → def
    4. background = def.background() || args.runInBackground() → false
    5. Filter.applyAgentToolFilter -> allowed
    6. provider = "haiku".equals(def.model()) ? llm.create(haiku) : parent.provider()
    7. SessionRuntime subRuntime = new SessionRuntime(200_000);
    8. Agent subAgent = Agent.builder()
           .provider(provider).registry(registry).version(version).engine(engine)
           .runtime(subRuntime)
           .allowedTools(allowed)
           .systemPrompt(def.systemPrompt())          // 新
           .maxTurns(def.maxTurns())
           .permissionMode(def.permissionMode())
           .dontAsk(def.dontAsk())
           .approvalUpgrader(parent.taskMgr()::upgradeApproval)
           .hookEngine(parent.hookEngine())
           .build();
    9. Conversation subConv = new Conversation();
    10. AtomicBoolean cancelFlag = new AtomicBoolean();
        ScheduledFuture<?> timeoutHandle = scheduler.schedule(() -> cancelFlag.set(true), 120, SECONDS);
        SubmissionPublisher<Event> events = new SubmissionPublisher<>();
        // 前台路径:把 events 转发到主 TUI(可选,本期暂不渲染前台子进度,只在状态行显示一条 "● subAgent 跑中")
        Thread.startVirtualThread(() -> events.subscribe(uiSink));
        String finalText = subAgent.runToCompletion(cancelFlag, subConv, args.prompt(), events);
    11. 是否被超时触发?
         - 是 → adoptRunning(cancelFlag(新), subAgent, subConv, args.name(), eventSub, cancel, partial)
              → 返回 JSON {"task_id": "task_xxx", "status": "timed_out_to_background"}
         - 否 → 返回 finalText 作为 tool_result content
```

### 运行时:主 Agent 调 Agent 工具(后台,显式)

```
AgentTool.execute:
    ...
    10. String taskId = taskMgr.launch(cancelFlag, subAgent, subConv, args.name(), args.prompt());
    11. 返回 JSON {"task_id": "task_xxx", "status": "async_launched"}
```

### 后台任务完成通知

```
taskMgr.launch virtual thread:
    String text = subAgent.runToCompletion(cancelFlag, conv, task, null);
    task.result = text;
    task.err = err;
    task.status = COMPLETED (or FAILED/CANCELLED);
    if (!donePub.offer(taskId, 0, TimeUnit.MILLISECONDS, ...)) {
        // 缓冲满,丢弃 + stderr 警告
    }
    ↓
TuiApp.consumeTaskDone (virtual thread,donePub.subscribe):
    onNext(taskId):
        var t = taskMgr.get(taskId);
        String notification = buildTaskNotification(t);  // <task-notification>...</task-notification>
        runtime.appendReminders(List.of(notification));
        // 不主动唤醒主对话:等主 Agent 下次 run 自然 take reminder
    ↓
下一次 beginTurn → agent.run → buildReminder takes pendingReminders → 注入 reminder 区
```

### Fork 路径

```
AgentTool.execute (subagentType 空):
    1. def = catalog.forkDefinition()  // name="__fork__"
    2. background = true (Fork 强制)
    3. allowed = Filter.applyAgentToolFilter(...)
       注意:这里 def.disallowedTools() 不含 "Agent" → Fork 子 Agent 工具集保留 Agent
    4. forkedMsgs = Fork.buildForkedMessages(parentConv.messages(), args.prompt())
    5. Conversation subConv = Conversation.fromMessages(forkedMsgs, ...);
    6. Agent subAgent = Agent.builder().allowedTools(allowed).systemPrompt("") ...build(); // 继承主系统提示
    7. String taskId = taskMgr.launch(cancelFlag, subAgent, subConv, args.name(), args.prompt());
    8. 返回 {"task_id": "...", "status": "async_launched"}
```

### Fork 子 Agent 调 Agent 工具被阻断

```
Fork 子 Agent 跑动中,LLM 又产 tool_use:{name:"Agent", input:{...}}
    ↓
subAgent.executeBatched → AgentTool.execute(subCtx, args)
    ↓
AgentTool.execute:
    检测:Fork.isForkContext(subConv.messages()) → true(消息中含 <fork_boilerplate>)
    → 返回 Result(isError=true, content="Fork 子 Agent 不能再启动 Agent(检测到 fork boilerplate)")
```

注:由于 `ALL_AGENT_DISALLOWED_TOOLS=["Agent"]` 已经把 Agent 工具从子 Agent 工具列表里剔除,理论上 Fork 子 Agent 的 LLM 看不到 Agent 工具。但 Fork 路径**故意保留**(为了 prompt cache 一致性),靠 QuerySource + Boilerplate 兜底拦截。

**结论:** Fork 子 Agent 工具列表 = 父工具列表 - disallowedTools - 后台白名单交集 - 但不去除 Agent 工具。

### Skill fork 改造

```
TuiApp.execute("/foo") → skills.Executor.execute → fork closure runSubAgent
    ↓ (改造后)
runSubAgent(cancelFlag, conv, opts):
    return subagent.LaunchFork.launch(cancelFlag, LaunchFork.fromTui(this), new ForkLaunchOpts(
        opts.allowedTools(),
        opts.model(),
        conv,                       // skills 已构造好的 forkConv
        "",                         // 走继承
        false,                      // skills 仍走前台同步(返回 finalText 给 host)
        null                        // eventsSink
    ));
```

`subagent.LaunchFork.launch` 内部:做与 `AgentTool.execute` 前台路径相同的 wiring,只是不读 catalog Definition。

## 文件组织

```
gcode/
├── src/main/java/dev/gcode/
│   ├── subagent/                        ← 新增包
│   │   ├── package-info.java            包注释
│   │   ├── Definition.java              Definition record / Source enum
│   │   ├── Parser.java                  parseFrontmatterAndBody + validateMeta
│   │   ├── Catalog.java                 Catalog + load / resolve / list / forkDefinition
│   │   ├── BuiltinLoader.java           classpath resource 加载 + builtinDefinitions()
│   │   └── LaunchFork.java              LaunchFork / Definition 公用 wiring 辅助
│   │
│   ├── task/                            ← 新增包
│   │   ├── package-info.java
│   │   ├── Manager.java                 Manager + BackgroundTask + launch / adopt / stop / sendMessage
│   │   ├── Status.java                  enum Status
│   │   ├── Usage.java                   record Usage
│   │   ├── PartialState.java            record PartialState
│   │   ├── TaskListTool.java            new TaskListTool / new TaskGetTool / ...
│   │   ├── TaskGetTool.java
│   │   ├── TaskStopTool.java
│   │   └── SendMessageTool.java
│   │
│   ├── agent/                           ← 现有包扩展
│   │   ├── Agent.java                   现有,加 systemPrompt/maxTurns/permissionMode/dontAsk/approvalUpgrader 字段;run 抽 runIter
│   │   ├── Agent$Builder.java(内部类)    加 systemPrompt/maxTurns/permissionMode/dontAsk/approvalUpgrader/provider 选项
│   │   ├── RunToCompletion.java         ← 新增 runToCompletion 实现(也可放回 Agent.java)
│   │   ├── Fork.java                    ← 新增 buildForkedMessages / isForkContext / FORK_BOILERPLATE
│   │   ├── AgentTool.java               ← 新增 AgentTool + execute 逻辑
│   │   ├── ApprovalUpgrader.java        ← 新增 ApprovalUpgrader 接口 + DEFAULT 实现
│   │   ├── AgentCatalogPort.java        ← 新增 接口(打破对 subagent 包的循环依赖)
│   │   ├── TaskManagerPort.java         ← 新增 接口(打破对 task 包的循环依赖)
│   │   └── ...其他不动
│   │
│   ├── tool/                            ← 现有包扩展
│   │   └── Filter.java                  ← 新增 ALL_AGENT_DISALLOWED / ASYNC_AGENT_ALLOWED / applyAgentToolFilter
│   │
│   ├── tui/                             ← 现有包改动
│   │   ├── TuiApp.java                  加 taskMgr / subAgentCatalog 字段 + consumeTaskDone virtual thread + AgentTool 注册
│   │   ├── Stream.java                  updateStreaming 加 ESC → adoptRunning 分支;子 Agent ApprovalRequest 转发
│   │   ├── Tasks.java                   ← 新增 consumeTaskDone + buildTaskNotification + ESC 切后台辅助
│   │   ├── SkillFork.java               ← 改造为复用 subagent.LaunchFork
│   │   └── ...
│   │
│   └── config/                          ← 现有,加配置项
│       └── Config.java                  record 加 Boolean enableSubAgentBackground(默认 true)
│
├── src/main/resources/
│   └── subagent/builtin/
│       ├── general-purpose.md
│       ├── explore.md
│       └── plan.md
│
├── src/test/java/dev/gcode/
│   ├── subagent/ParserTest.java
│   ├── subagent/CatalogTest.java
│   ├── subagent/LaunchForkTest.java
│   ├── task/ManagerTest.java
│   ├── task/ToolsTest.java
│   ├── agent/RunToCompletionTest.java
│   ├── agent/ForkTest.java
│   ├── agent/AgentToolTest.java
│   ├── agent/AgentToolIntegrationTest.java
│   ├── tool/FilterTest.java
│   └── tui/TuiAppTest.java
│
└── src/main/java/dev/gcode/Main.java  ← 加 Catalog.load / new Manager / 4 个工具注册 / AgentTool 注册
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| `runToCompletion` 与 `run` 关系 | 共用底层 helper(`runIter` / `streamOnce`),不重新写一遍循环 | 避免两套循环逻辑漂移;主对话与子 Agent 在 ReAct 层面行为应一致 |
| 子 Agent 是否独立 `PermissionEngine` | 暂共享同一 Engine,但增加 `approvalUpgrader` 让审批升级回主 TUI | 本期权限规则全局一致;独立 Engine 是为隔离规则集准备的预留扩展点 |
| Fork 强制后台 | 是 | ch13 README 设计;Fork 上下文长,前台同步会阻塞用户;并行 Fork 才有意义 |
| 后台通知形式 | system reminder 注入(`<task-notification>`),不直接 push 到 LLM | 与 ch12 pendingReminders 一致;不打断用户当前操作;主 Agent 下次 turn 自然消费 |
| 嵌套阻断三道闸 | `ALL_AGENT_DISALLOWED_TOOLS` 全局 + Fork 路径 QuerySource + Boilerplate 标记扫描 | 单一闸门失效(对话压缩、工具列表漂移)仍能兜底;定义式靠工具过滤,Fork 靠双闸 |
| 后台白名单粒度 | 列具体工具名 + MCP/Skill 工具按命名约定动态识别 | ch13 README 同款做法;不需要为每个 MCP 工具列在白名单里 |
| `donePub` 缓冲 32 | 够大 | 正常场景一会儿不会有 32 个任务同时跑完;真满则丢弃 + stderr |
| `sendMessage` 同 id 复用 | 是 | 状态语义上是"该任务继续",而非"新任务";UI/查询体验更连贯 |
| 配置开关 `enableSubAgentBackground` | 默认 true | 后台是核心能力,默认开启;关闭后所有子 Agent 强制前台,主要供 CI / 调试用 |
| Markdown 解析器复用 | 不共享,subagent 包独立实现一份(几乎与 `skills.Parser` 一致) | 避免抽公共包导致循环依赖;两个包字段不一样,复用收益有限 |
| Agent 工具的 parent 注入时机 | `Main.java` 注册时为 null,`new TuiApp(...)` 后 `setParent` 回填 | `ToolRegistry` 在 `new TuiApp(...)` 之前已构造,Agent 工具的 parent 依赖 `tuiApp.mainAgent()` 反推 |
| ESC 切后台 vs Ctrl+C | ESC 切后台,Ctrl+C 仍是取消(沿用现有) | ESC 在 TUI 已经做"取消选择"用途,但流式态下 ESC 转为切后台是 ch13 README 设计 |
| 并发模型 | virtual thread + `SubmissionPublisher`(`Flow.Publisher`)+ `AtomicBoolean` 取消 | Java 21 GA;子 Agent 长跑用 virtual thread 成本极低;`SubmissionPublisher` 是 JDK 原生 reactive 接口,零外部依赖;`AtomicBoolean` 等价于 Go 的 `ctx.Done()` 信号位 |
| 内置 Markdown 资源 | classpath resource(`src/main/resources/subagent/builtin/*.md`)+ `Class.getResourceAsStream` | Java 没有 `go:embed`,classpath resource 是标准做法,Maven 打 fat jar 时自动打包 |
| 循环依赖打破 | agent 包定义 `AgentCatalogPort` / `TaskManagerPort` 接口,subagent / task 实现 | subagent / task 想引用 agent.Agent,agent.AgentTool 又想引用 subagent.Definition;通过 port 接口让 agent 包成为下游,subagent / task 单向引用 agent |
````

````markdown
# SubAgent 机制 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/main/java/dev/gcode/subagent/package-info.java` | 包注释 |
| 新建 | `src/main/java/dev/gcode/subagent/Definition.java` | Definition record / Source enum |
| 新建 | `src/main/java/dev/gcode/subagent/Parser.java` | parseFrontmatterAndBody + validateMeta |
| 新建 | `src/test/java/dev/gcode/subagent/ParserTest.java` | 解析与字段校验单测 |
| 新建 | `src/main/java/dev/gcode/subagent/Catalog.java` | Catalog + load / resolve / list / forkDefinition |
| 新建 | `src/test/java/dev/gcode/subagent/CatalogTest.java` | 多来源加载与覆盖测试 |
| 新建 | `src/main/java/dev/gcode/subagent/BuiltinLoader.java` | classpath resource 加载 + builtinDefinitions() |
| 新建 | `src/main/resources/subagent/builtin/general-purpose.md` | 内置 general-purpose 定义 |
| 新建 | `src/main/resources/subagent/builtin/explore.md` | 内置 Explore 定义 |
| 新建 | `src/main/resources/subagent/builtin/plan.md` | 内置 Plan 定义 |
| 新建 | `src/main/java/dev/gcode/subagent/LaunchFork.java` | LaunchFork / 公用 wiring 辅助函数 |
| 新建 | `src/test/java/dev/gcode/subagent/LaunchForkTest.java` | LaunchFork 流程测试 |
| 新建 | `src/main/java/dev/gcode/task/package-info.java` | 包注释 |
| 新建 | `src/main/java/dev/gcode/task/Manager.java` | Manager + BackgroundTask + launch / adopt / stop / sendMessage / subscribeDone |
| 新建 | `src/main/java/dev/gcode/task/Status.java` | enum Status |
| 新建 | `src/main/java/dev/gcode/task/Usage.java` | record Usage |
| 新建 | `src/main/java/dev/gcode/task/PartialState.java` | record PartialState |
| 新建 | `src/test/java/dev/gcode/task/ManagerTest.java` | 后台任务全生命周期测试 |
| 新建 | `src/main/java/dev/gcode/task/TaskListTool.java` | TaskList 工具 |
| 新建 | `src/main/java/dev/gcode/task/TaskGetTool.java` | TaskGet 工具 |
| 新建 | `src/main/java/dev/gcode/task/TaskStopTool.java` | TaskStop 工具 |
| 新建 | `src/main/java/dev/gcode/task/SendMessageTool.java` | SendMessage 工具 |
| 新建 | `src/test/java/dev/gcode/task/ToolsTest.java` | 4 个工具的单测 |
| 新建 | `src/main/java/dev/gcode/agent/RunToCompletion.java` | runToCompletion 方法实现(可作为 Agent.java 的同包补充) |
| 新建 | `src/test/java/dev/gcode/agent/RunToCompletionTest.java` | runToCompletion / dontAsk / maxTurns 测试 |
| 新建 | `src/main/java/dev/gcode/agent/Fork.java` | buildForkedMessages + isForkContext + FORK_BOILERPLATE |
| 新建 | `src/test/java/dev/gcode/agent/ForkTest.java` | Fork 消息构造与上下文识别测试 |
| 新建 | `src/main/java/dev/gcode/agent/AgentTool.java` | AgentTool + execute |
| 新建 | `src/test/java/dev/gcode/agent/AgentToolTest.java` | Agent 工具调用、嵌套阻断、超时切后台测试 |
| 新建 | `src/main/java/dev/gcode/agent/ApprovalUpgrader.java` | ApprovalUpgrader 接口 + DEFAULT 实现 |
| 新建 | `src/main/java/dev/gcode/agent/AgentCatalogPort.java` | 接口,断开 agent ↔ subagent 循环依赖 |
| 新建 | `src/main/java/dev/gcode/agent/TaskManagerPort.java` | 接口,断开 agent ↔ task 循环依赖 |
| 新建 | `src/main/java/dev/gcode/tool/Filter.java` | ALL_AGENT_DISALLOWED / ASYNC_AGENT_ALLOWED / applyAgentToolFilter |
| 新建 | `src/test/java/dev/gcode/tool/FilterTest.java` | 过滤多层防线测试 |
| 新建 | `src/main/java/dev/gcode/tui/Tasks.java` | consumeTaskDone + buildTaskNotification + ESC 切后台辅助 |
| 修改 | `src/main/java/dev/gcode/agent/Agent.java` | 加 systemPrompt/maxTurns/permissionMode/dontAsk/approvalUpgrader 字段;run 抽 runIter;runGuarded 加 dontAsk 短路 + approvalUpgrader 升级 |
| 修改 | `src/main/java/dev/gcode/agent/Agent.java`(Builder 内部类) | 加 systemPrompt / maxTurns / permissionMode / dontAsk / approvalUpgrader / provider 选项 |
| 修改 | `src/test/java/dev/gcode/agent/AgentTest.java` | 不破坏既有测试 |
| 修改 | `src/main/java/dev/gcode/tool/ToolRegistry.java` | 不动(过滤逻辑在 Filter.java) |
| 修改 | `src/main/java/dev/gcode/tui/TuiApp.java` | TuiParams 加 taskMgr/subAgentCatalog;TuiApp 持有;init 启 consumeTaskDone;AgentTool 注册后 setParent |
| 修改 | `src/main/java/dev/gcode/tui/Stream.java` | updateStreaming 加 ESC → adoptRunning 分支 |
| 修改 | `src/main/java/dev/gcode/tui/SkillFork.java` | 改造为调 subagent.LaunchFork.launch |
| 修改 | `src/test/java/dev/gcode/tui/TuiAppTest.java` | 补 ESC 切后台、task-notification 注入测试 |
| 修改 | `src/main/java/dev/gcode/config/Config.java` | 加 enableSubAgentBackground(Boolean,默认 true) |
| 修改 | `src/main/java/dev/gcode/Main.java` | Catalog.load / new Manager / 4 个 task 工具注册 / AgentTool 注册 + setParent;taskMgr / subAgentCatalog 传给 TuiApp |

## T1: subagent 包的 Definition 与 Source 类型**文件:** `src/main/java/dev/gcode/subagent/Definition.java`
**依赖:** 无
**步骤:**
1. 新建包 `dev.gcode.subagent`,加 `Definition.java`,声明 `enum Source` 类型与四个常量:
   - `BUILTIN`
   - `USER`
   - `PROJECT`
   - `PLUGIN`(占位)
2. `Source.toString()` 返回 `"builtin" / "user" / "project" / "plugin"`(用 switch 表达式)
3. 声明 `record Definition`,字段如 plan.md 所述:`name / description / tools / disallowedTools / model / maxTurns / permissionMode / dontAsk / background / systemPrompt / filePath / source`
4. 在 record 类注释里每个字段语义,引用 spec F4
5. `Definition.isFork()` 返回 `"__fork__".equals(name)`(便于 forkDefinition 判别)

**验证:** `mvn -q compile -pl . -am` 编译通过

## T2: subagent 解析器**文件:** `src/main/java/dev/gcode/subagent/Parser.java`
**依赖:** T1
**步骤:**
1. 新建 `Parser.java`,从 `skills.Parser` 复制 `parseFrontmatterAndBody` 与 `UTF8_BOM` 常量(几乎 ✓ 不变,改包名)
2. 声明 `static final java.util.regex.Pattern AGENT_NAME_REGEX = Pattern.compile("^[A-Za-z][A-Za-z0-9-_]{0,31}$")`(大小写都允许,与 ch13 README 的 `Explore`/`Plan` 一致)
3. 实现 `static Definition parseDefinition(byte[] data, String filePath, Source source) throws ParserException`:
   - 调 `parseFrontmatterAndBody` 拿 frontmatter `Map<String,Object>` + body
   - SnakeYAML Engine 解析出 `Map<String,Object>` 后手动映射到一个临时类 `AgentFm`:
     ```java
     record AgentFm(
         String name,
         String description,
         java.util.List<String> tools,
         java.util.List<String> disallowedTools,
         String model,
         int maxTurns,
         String permissionMode,
         boolean background
     ) {}
     ```
   - 校验 `name` 非空且匹配 `AGENT_NAME_REGEX`
   - 校验 `description` 非空
   - 校验 `model`:空 / `"inherit"` / `"haiku"` / `"sonnet"` / `"opus"` 之一,其它 stderr 警告并改为 `"inherit"`
   - 解析 `permissionMode`:`"dontAsk"` 单独识别 → `Definition.dontAsk=true, Definition.permissionMode=PermissionMode.DEFAULT`;否则调 `PermissionMode.parse`,失败 stderr 警告并改为 `DEFAULT`
   - 把 fm 字段映射到 Definition 字段(`systemPrompt = body`,`filePath = filePath`,`source = source`)
4. 实现 `static Definition parseFile(java.nio.file.Path path, Source source) throws IOException, ParserException`:`Files.readAllBytes` + `parseDefinition`

**验证:** `mvn test -Dtest=ParserTest` 通过(对应 T3 的测试)

## T3: subagent 解析器测试**文件:** `src/test/java/dev/gcode/subagent/ParserTest.java`
**依赖:** T2
**步骤:**
1. JUnit 5 `@ParameterizedTest` + `@MethodSource`:正常完整 frontmatter / 仅必填 / model 非法 → 警告 fallback / permissionMode=dontAsk → dontAsk=true / 缺 name 报错 / 缺 description 报错 / frontmatter 未关闭 → 异常
2. body 区段提取:验证 `---` 后的内容(去 BOM 去前导换行)被完整取到 `systemPrompt`
3. 测试 `parseFile` 读取一个 testdata 下的 `.md` 文件(放在 `src/test/resources/subagent/testdata/`)
4. 每个用例附 `fail("case " + name + ": ...")` 描述

**验证:** `mvn test -Dtest=ParserTest` 全部通过

## T4: 内置 Agent 定义文件**文件:** `src/main/resources/subagent/builtin/{general-purpose,explore,plan}.md`
**依赖:** 无
**步骤:**
1. 创建目录 `src/main/resources/subagent/builtin/`
2. `general-purpose.md`:
   ```yaml
   ---
   name: general-purpose
   description: 通用子 Agent,拥有全部工具,用于需要完整能力但独立上下文的场景
   maxTurns: 30
   ---

   你是 GCode 的通用 Agent。根据用户的消息,使用可用工具完成任务。
   把任务做完,不要过度设计,但也不要做一半就停。
   完成后用简洁的报告回复:做了什么、关键发现。
   调用方会把结果转述给用户,所以只需要包含要点。
   ```
3. `explore.md`:
   ```yaml
   ---
   name: Explore
   description: 只读代码探索 Agent,适合搜索、阅读、理清调用链;不能修改文件
   disallowedTools:
     - write_file
     - edit_file
   model: haiku
   maxTurns: 30
   ---

   你是一个文件搜索专家。这是一个只读探索任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工具策略:Glob 做文件模式匹配、Grep 搜索文件内容、Read 读取已知路径、Bash 仅用于只读操作(ls、git log、find、cat)。
   尽可能并行发起多个工具调用。高效完成搜索请求,清晰报告发现。
   ```
4. `plan.md`:
   ```yaml
   ---
   name: Plan
   description: 计划 Agent,分析需求、制定执行计划,但不直接执行;主 Agent 拿到计划后逐步执行
   disallowedTools:
     - write_file
     - edit_file
     - Agent
   maxTurns: 15
   permissionMode: plan
   ---

   你是一个软件架构师和规划专家。这是一个只读规划任务。
   严禁:创建文件、修改文件、删除文件、执行任何改变系统状态的命令。
   工作流程:① 理解需求 ② 用搜索工具充分探索代码库 ③ 设计方案 ④ 输出分步实现计划。
   回复末尾必须列出 3-5 个对实现最关键的文件路径。
   ```

**验证:** 三个 `.md` 文件存在,frontmatter 合法;`Parser.parseFile` 测试不报错

## T5: subagent classpath resource 加载**文件:** `src/main/java/dev/gcode/subagent/BuiltinLoader.java`
**依赖:** T2, T4
**步骤:**
1. 新建 `BuiltinLoader.java`,实现 `static java.util.List<Definition> builtinDefinitions()`:
   - 文件名清单写死:`"general-purpose.md"`, `"explore.md"`, `"plan.md"`(顺序无关,因为后面 catalog.list 会排序)
   - 对每个名字:`InputStream in = BuiltinLoader.class.getResourceAsStream("/subagent/builtin/" + name)`
     - `in == null` → 抛 `RuntimeException("builtin agent missing: " + name)`
     - 读完字节后调 `Parser.parseDefinition(bytes, "classpath:subagent/builtin/" + name, Source.BUILTIN)`
   - 解析失败 → 抛 `RuntimeException`(代码 bug,启动期失败即灾难)
2. 返回 `List<Definition>`,按 name 升序

> 备注:`getResourceAsStream` 路径必须以 `/` 开头(从 classpath 根读),Maven 会把 `src/main/resources` 打入 jar 根。

**验证:** `mvn test -Dtest=CatalogTest` 中 builtin 部分通过(T7)

## T6: Catalog 与三层加载**文件:** `src/main/java/dev/gcode/subagent/Catalog.java`
**依赖:** T1, T2, T5
**步骤:**
1. 新建 `Catalog.java`,声明:
   ```java
   public final class Catalog {
       private final Object lock = new Object();
       private final java.util.Map<String, Definition> defs = new java.util.HashMap<>();
       private final java.util.EnumMap<Source, java.util.List<Definition>> bySource =
               new java.util.EnumMap<>(Source.class);
   }
   ```
2. 实现 `public static Catalog load(java.nio.file.Path root)`:
   - `Catalog c = new Catalog();`
   - 加载 builtin → `c.addAll(BuiltinLoader.builtinDefinitions(), Source.BUILTIN)`
   - 加载 user → `c.addAll(loadFromDir(Path.of(System.getProperty("user.home"), ".gcode/agents"), Source.USER), Source.USER)`
   - 加载 project → `c.addAll(loadFromDir(root.resolve(".gcode/agents"), Source.PROJECT), Source.PROJECT)`
   - plugin 层本期跳过
3. 实现 `private static List<Definition> loadFromDir(Path dir, Source source)`:
   - 目录不存在 → 返回 `List.of()`
   - `Files.list(dir).filter(p -> p.toString().endsWith(".md"))` 遍历,逐个 `Parser.parseFile`;失败 stderr 警告并跳过
   - 返回 list
4. 实现 `private void addAll(List<Definition> defs, Source source)`:
   - 同名时高优先级覆盖(因为按 builtin → user → project 顺序加载,后加的优先级更高,直接 `defs.put(name, def)`)
   - 同时往 `bySource.computeIfAbsent(source, k -> new ArrayList<>()).add(def)`
5. 实现 `public Optional<Definition> resolve(String name)`
6. 实现 `public List<Definition> list()`(按 name 升序)
7. 实现 `public List<Definition> listBySource(Source s)`
8. 实现 `public Definition forkDefinition()`:
   ```java
   return new Definition(
           "__fork__",
           "Fork-based subagent",
           List.of(), List.of(),     // tools / disallowedTools 留空 -> 工具集继承父
           "inherit", 25,
           PermissionMode.DEFAULT, false, false,
           "", "", Source.BUILTIN);
   ```

**验证:** `mvn test -Dtest=CatalogTest` 通过

## T7: Catalog 测试**文件:** `src/test/java/dev/gcode/subagent/CatalogTest.java`
**依赖:** T6
**步骤:**
1. 测试 `BuiltinLoader.builtinDefinitions()` 返回 3 个 def(general-purpose / Explore / Plan)
2. 测试三层覆盖:用 `@TempDir` 造一个项目 root 与一个 HOME 路径(用 `System.setProperty("user.home", ...)` 临时改),分别放 `explore.md`
3. 验证 `resolve("Explore")` 在三种情形下返回的 `source` 正确(都有 → PROJECT;只有 user+builtin → USER;只有 builtin → BUILTIN)
4. 测试 `forkDefinition()` 返回 `isFork()==true`
5. 测试加载错误处理:放一个非法 frontmatter 文件,加载后该文件 *被跳过*,其他文件仍正常

**验证:** `mvn test -Dtest=CatalogTest` 全部通过

## T8: 工具过滤多层防线**文件:** `src/main/java/dev/gcode/tool/Filter.java`
**依赖:** 无
**步骤:**
1. 新建 `Filter.java`,声明三个常量:
   ```java
   public static final List<String> ALL_AGENT_DISALLOWED_TOOLS = List.of("Agent");
   public static final List<String> CUSTOM_AGENT_DISALLOWED_TOOLS = List.of();
   public static final List<String> ASYNC_AGENT_ALLOWED_TOOLS = List.of(
           "read_file", "write_file", "edit_file",
           "glob", "grep",
           "bash",
           "load_skill", "install_skill"
   );
   ```
2. 声明 `record FilterParams`:
   ```java
   public record FilterParams(
       List<String> all,        // registry 的全部工具名
       int source,              // 1=BUILTIN, 2=USER, 3=PROJECT, 4=PLUGIN(数值需与 Source.ordinal()+1 对齐,这里用 int 避免反向依赖)
       boolean background,
       List<String> allowed,    // Agent 定义的 tools 白名单
       List<String> disallowed  // Agent 定义的 disallowedTools 黑名单
   ) {}
   ```
3. 实现 `public static List<String> applyAgentToolFilter(FilterParams p)`:
   按 spec F30 顺序:
   - 起点 = `new ArrayList<>(p.all())` 副本
   - 过滤 1:去除 `ALL_AGENT_DISALLOWED_TOOLS`
   - 过滤 2:若 `p.source() >= 2`(非 BUILTIN),再去除 `CUSTOM_AGENT_DISALLOWED_TOOLS`(本期为空,跳过)
   - 过滤 3:若 `p.background()`,与 `ASYNC_AGENT_ALLOWED_TOOLS ∪ {name | isMcpOrSkill(name)}` 取交集
   - 过滤 4:去除 `p.disallowed()`
   - 过滤 5:若 `!p.allowed().isEmpty()`,与之取交集
4. 辅助函数 `static boolean isMcpOrSkill(String name)`:`name.startsWith("mcp__")` || ... skill 工具的识别本期暂不接入(主 Registry 不区分,先按名字前缀 + 内置基础工具白名单兜底)

**验证:** `mvn -q compile -pl . -am` 编译通过

## T9: 工具过滤测试**文件:** `src/test/java/dev/gcode/tool/FilterTest.java`
**依赖:** T8
**步骤:**
1. `@ParameterizedTest` 覆盖各组合:
   - 默认:无后台、无白名单、无黑名单 → 去 Agent 即可
   - 后台:取 `ASYNC_AGENT_ALLOWED_TOOLS` 交集
   - 黑名单:`disallowed=List.of("bash")` → 不含 bash
   - 白名单:`allowed=List.of("read_file","grep")` → 仅这两个
   - 黑+白:白名单先收窄,黑名单再剔除
   - 后台 + MCP 工具:MCP 工具(`mcp__xxx`)被保留(白名单 OK)
2. 单独测试 `isMcpOrSkill` 边界

**验证:** `mvn test -Dtest=FilterTest` 通过

## T10: Agent 包扩展 - 新增 Builder 选项**文件:** `src/main/java/dev/gcode/agent/Agent.java`
**依赖:** 无
**步骤:**
1. 在 `Agent` 类加字段:
   ```java
   private final String systemPrompt;       // 非空覆盖默认 system prompt
   private final int maxTurns;              // 0=用全局 MAX_ITERATIONS
   private final PermissionMode permissionMode;
   private final boolean permissionModeSet; // 区分零值与未设置
   private final boolean dontAsk;
   private final ApprovalUpgrader approvalUpgrader;
   ```
2. 在 `Agent.Builder` 加 6 个新选项:
   ```java
   public Builder systemPrompt(String s) { this.systemPrompt = s; return this; }
   public Builder maxTurns(int n) { if (n > 0) this.maxTurns = n; return this; }
   public Builder permissionMode(PermissionMode m) {
       this.permissionMode = m; this.permissionModeSet = true; return this;
   }
   public Builder dontAsk(boolean b) { this.dontAsk = b; return this; }
   public Builder approvalUpgrader(ApprovalUpgrader fn) { this.approvalUpgrader = fn; return this; }
   public Builder provider(Provider p) { this.provider = p; return this; }
   ```
3. 加 javadoc 解释每个选项语义

**验证:** `mvn -q compile` 编译通过

## T11: ApprovalUpgrader 接口**文件:** `src/main/java/dev/gcode/agent/ApprovalUpgrader.java`
**依赖:** T10
**步骤:**
1. 新建文件,声明:
   ```java
   @FunctionalInterface
   public interface ApprovalUpgrader {
       Optional<Outcome> upgrade(AtomicBoolean cancelFlag, ApprovalRequest req);
       ApprovalUpgrader DEFAULT = (cancel, req) -> Optional.empty();
   }
   ```
2. javadoc 解释:子 Agent 把审批请求升级到父 TUI 的回调;返回 `Optional.empty()` 时调用方应走默认 emit Approval 路径

**验证:** `mvn -q compile` 编译通过

## T12: Fork 路径辅助函数**文件:** `src/main/java/dev/gcode/agent/Fork.java`
**依赖:** 无(纯函数)
**步骤:**
1. 新建 `Fork.java`,声明常量:
   ```java
   public static final String FORK_BOILERPLATE_TAG = "<fork_boilerplate>";

   public static final String FORK_BOILERPLATE = """
           <fork_boilerplate>
           你是一个 Fork 出来的工作进程。你不是主 Agent。
           规则(不可协商):
           1. 不能再 Fork(调用 Agent 工具会被拦截)。
           2. 不要对话、不要提问、不要请求确认。
           3. 直接使用工具:读文件、搜索代码、做修改。
           4. 严格限制在你被分配的任务范围内。
           5. 最终报告以 "Scope:" 开头,500 字以内。
           </fork_boilerplate>

           """;
   ```
2. 实现 `public static List<Message> buildForkedMessages(List<Message> parentMsgs, String task)`:
   - 深拷贝 `parentMsgs`(参考 `Conversation.fromMessages` 的拷贝逻辑):每个 Message 复制 role/content/toolCalls/toolResults
   - 扫描末尾 assistant 消息的 `toolCalls`:对于每个未配对的 `toolCallId`,在 cloned 末尾追加 `ROLE_TOOL` 消息(每个 ID 一条 placeholder `ToolResult{content:"[forked, skipped]", isError:true}`)
     - 配对检查:看看 cloned 后续是否有 `ROLE_TOOL` 消息消费这些 ID
   - 追加最后一条 user 消息:`content = FORK_BOILERPLATE + task`
3. 实现 `public static boolean isForkContext(List<Message> msgs)`:
   - 遍历 `msgs`,若 user/tool/assistant 消息内容含 `FORK_BOILERPLATE_TAG` → 返回 true
   - 默认 false

**验证:** `mvn test -Dtest=ForkTest` 通过(T13)

## T13: Fork 辅助函数测试**文件:** `src/test/java/dev/gcode/agent/ForkTest.java`
**依赖:** T12
**步骤:**
1. 测试 `buildForkedMessages` 空 parent → 返回单条 user 消息含 Boilerplate + task
2. 测试 parent 末尾有完整 assistant + tool_result 配对:cloned 末尾 == parent 末尾 + 一条 user
3. 测试 parent 末尾 assistant 有 2 个 tool_use 没配对:cloned 中追加 1 条 `ROLE_TOOL`(2 个 placeholder ToolResult)再追加 1 条 user
4. 测试 `isForkContext`:消息中含 Boilerplate → true;不含 → false

**验证:** `mvn test -Dtest=ForkTest` 通过

## T14: runGuarded 加 dontAsk 短路与 approvalUpgrader**文件:** `src/main/java/dev/gcode/agent/Agent.java`
**依赖:** T10, T11
**步骤:**
1. 修改 `runGuarded`,在 `case ASK:` 分支里:
   ```java
   case ASK -> {
       // 子 Agent dontAsk 模式:直接 Allow
       if (a.dontAsk) {
           return runTool(ctx, c);
       }
       // 子 Agent 升级到父 TUI 审批
       if (a.approvalUpgrader != null) {
           var maybe = a.approvalUpgrader.upgrade(cancelFlag, new ApprovalRequest(
                   c.name(), argsPreview(c.input()), reason, null /* upgrader 内部处理 respond */));
           if (maybe.isPresent()) {
               return switch (maybe.get()) {
                   case ALLOW_ONCE     -> runTool(ctx, c);
                   case ALLOW_FOREVER  -> { eng.persistLocalAllow(c); yield runTool(ctx, c); }
                   default              -> denyResult(c.id(), "用户拒绝了本次调用");
               };
           }
       }
       // 默认路径:emit Approval event(主 Agent inline / Skill fork 都走此)
       Outcome o = requestApproval(ctx, c, reason, sub);
       ...
   }
   ```
2. 修改 `check` 调用前,如果子 Agent 设了 `permissionMode`(`a.permissionModeSet == true`),用 `a.permissionMode` 覆盖入参 mode
3. 修改 `streamLoop` 拿 defs 处的 `allowedTools` 逻辑(已有,无须改)

**验证:** `mvn test -Dtest=AgentTest` 现有测试不破

## T15: runToCompletion 实现**文件:** `src/main/java/dev/gcode/agent/RunToCompletion.java`(或直接放在 `Agent.java`)
**依赖:** T10, T14
**步骤:**
1. 实现:
   ```java
   public String runToCompletion(AtomicBoolean cancelFlag,
                                 Conversation conv,
                                 String task,
                                 SubmissionPublisher<Event> events) throws Exception
   ```
2. 逻辑:
   - 把 task 作为 user 消息:`if (!task.isEmpty()) conv.addUser(task);`(注意 conv 可能已经被 Fork 路径预装填,task=="" 时不追加)
   - 计算 maxTurns:`int turns = this.maxTurns; if (turns == 0) turns = MAX_ITERATIONS;`
   - 复用 `run` 的循环逻辑:但不用 publisher 返回事件,内部消费;改为返回 finalText + 抛异常
   - 拆出 helper `runIter(cancelFlag, conv, mode, iter, defs, sys, envText, reminder, eventsPub) -> RunIterResult(text, calls, done)` 让 `run` 和 `runToCompletion` 都调
   - `run` 改造为调 `runIter` 逐轮;`runToCompletion` 也是
   - 子 Agent 模式:`PermissionMode mode = PermissionMode.DEFAULT; if (this.permissionModeSet) mode = this.permissionMode;`
3. 退出条件:`done == true`(模型不再调工具)→ 返回 finalText;触达 turns → 抛 `MaxTurnsReachedException`(消息附 finalText);`cancelFlag.get()` → 抛 `CancellationException`;出错 → 原样抛
4. 在每轮内继续做 hook 调度(PreToolUse / PostToolUse / Stop 等),但 SubAgent 不触发 memory update
5. events publisher 转发:把 Tool / Text / Approval 事件 `events.submit(...)` 出去(供 TaskManager / TUI 接收)

**验证:** `mvn test -Dtest=RunToCompletionTest` 通过(T16)

## T16: runToCompletion 测试**文件:** `src/test/java/dev/gcode/agent/RunToCompletionTest.java`
**依赖:** T15
**步骤:**
1. 用 mock provider(已有 testhelpers)模拟一个回合返回纯文本的子 Agent → `runToCompletion` 返回 `"ok"`,不抛异常
2. 模拟一个回合返回 tool_use(已知工具),下一轮返回纯文本 → 工具被执行、finalText="..."
3. 模拟模型一直调工具不出文本,触达 `maxTurns=3` → 抛 `MaxTurnsReachedException`
4. 测试 dontAsk:子 Agent 设 `dontAsk(true)` + 模型调一个 Ask 级工具(如 bash) → 工具被自动放行执行
5. 测试 approvalUpgrader 回调被命中:子 Agent 设了 upgrader,Ask 时 upgrader 被调用(用 mock upgrader 验证)
6. 测试 events publisher 转发:运行子 Agent 时通过 Flow.Subscriber 把 events 收集到 list,断言含 Tool/Text 事件

**验证:** `mvn test -Dtest=RunToCompletionTest` 全部通过

## T17: Agent 工具实现**文件:** `src/main/java/dev/gcode/agent/AgentTool.java`
**依赖:** T8, T12, T15
**步骤:**
1. 新建文件,声明:
   ```java
   public final class AgentTool implements Tool {
       private final AgentCatalogPort catalog;  // 接口,避免反向依赖 subagent 包
       private final TaskManagerPort taskMgr;
       private volatile Agent parent;
       private final boolean bgEnabled;
   }

   // src/main/java/dev/gcode/agent/AgentCatalogPort.java
   public interface AgentCatalogPort {
       Optional<Definition> resolve(String name); // Definition 类型见下
       Definition forkDefinition();
       List<Definition> list();
   }

   // src/main/java/dev/gcode/agent/TaskManagerPort.java
   public interface TaskManagerPort {
       String launch(AtomicBoolean parentCancel, Agent ag, Conversation conv, String name, String task);
       String adoptRunning(AtomicBoolean parentCancel, Agent ag, Conversation conv, String name,
                           Flow.Subscription eventSub, AtomicBoolean cancelFlag, PartialState partial);
       Optional<Outcome> upgradeApproval(AtomicBoolean cancelFlag, ApprovalRequest req);
   }
   ```
2. **解决循环依赖**:agent 包不直接 import subagent 包,而是通过 port 接口反向适配;`subagent.Catalog implements AgentCatalogPort`,`task.Manager implements TaskManagerPort`。`Definition` 类型可以直接被 agent 包引用——subagent.Definition 只引用 `permission`,没问题。直接 `import dev.gcode.subagent.Definition`。
3. **AgentTool 接口实现**:
   - `name()` = `"Agent"`
   - `description()` 动态:基础描述 + `"subagent_type 可选值:" + String.join(", ", catalog.list().stream().map(Definition::name).toList())`
   - `parameters()`:按 spec F1 写 JSON Schema(Jackson `ObjectNode`)
   - `readOnly()` = `false`
   - `execute(ctx, args)`:
4. **execute 主流程**:
   ```java
   AgentArgs aArgs = mapper.treeToValue(args, AgentArgs.class);
   if (aArgs.prompt() == null || aArgs.prompt().isEmpty()) return Result.error("prompt is required");
   if (aArgs.description() == null || aArgs.description().isEmpty()) return Result.error("description is required");

   // 防嵌套
   if (isSubAgentContext(ctx)) return Result.error("subagent cannot spawn Agent");
   var parentConv = parentConvOf(ctx);
   if (parentConv != null && Fork.isForkContext(parentConv.messages()))
       return Result.error("Fork subagent cannot spawn Agent (boilerplate detected)");

   // resolve 定义
   Definition def;
   if (aArgs.subagentType() != null && !aArgs.subagentType().isEmpty()) {
       def = catalog.resolve(aArgs.subagentType())
                    .orElseThrow(() -> new IllegalArgumentException("unknown subagent_type: " + aArgs.subagentType()));
   } else {
       def = catalog.forkDefinition();
   }

   // 决定后台
   boolean background = def.background() || aArgs.runInBackground() || def.isFork();
   if (background && !bgEnabled) return Result.error("background mode is disabled by config");

   // 工具过滤
   var allowed = Filter.applyAgentToolFilter(new Filter.FilterParams(
           registryAllNames(parent.registry()),
           def.source().ordinal() + 1,
           background,
           def.tools(),
           def.disallowedTools()));

   // provider
   Provider provider = parent.provider();
   // (model 字段切换 provider 的逻辑暂从简:本期不实现按模型切换,后续完善)

   // 构造子 Agent
   SessionRuntime subRuntime = new SessionRuntime(200_000);
   Agent subAgent = Agent.builder()
           .provider(provider).registry(parent.registry()).version(parent.version()).engine(parent.engine())
           .runtime(subRuntime)
           .allowedTools(allowed)
           .systemPrompt(def.systemPrompt())
           .maxTurns(def.maxTurns())
           .permissionMode(def.permissionMode())
           .dontAsk(def.dontAsk())
           .approvalUpgrader(taskMgr::upgradeApproval)
           .hookEngine(parent.hookEngine())
           .build();
   // 标记子 Agent 上下文(让递归 Agent 工具调用被拦截)
   var childCtx = withSubAgentContext(ctx);

   // 子 Conv
   Conversation subConv = new Conversation();
   if (def.isFork()) {
       var parentMsgs = parentConvOf(ctx).messages();
       var forked = Fork.buildForkedMessages(parentMsgs, aArgs.prompt());
       subConv = Conversation.fromMessages(forked);
   }

   // 后台路径
   if (background) {
       String taskId = taskMgr.launch(parent.cancelFlag(), subAgent, subConv, aArgs.name(), aArgs.prompt());
       return Result.ok(String.format("{\"task_id\":\"%s\",\"status\":\"async_launched\"}", taskId));
   }

   // 前台路径
   AtomicBoolean cancelFlag = new AtomicBoolean();
   ScheduledFuture<?> timeoutHandle = scheduler.schedule(
           () -> cancelFlag.set(true), AUTO_BACKGROUND_MS, TimeUnit.MILLISECONDS);
   SubmissionPublisher<Event> events = new SubmissionPublisher<>();
   PartialState partial = new PartialState("", 0, "", new Usage(0,0,0,0));
   Thread.startVirtualThread(() -> aggregatePartial(events, partial));

   try {
       String finalText = subAgent.runToCompletion(cancelFlag, subConv, aArgs.prompt(), events);
       timeoutHandle.cancel(false);
       events.close();
       return Result.ok(finalText);
   } catch (CancellationException ce) {
       events.close();
       String taskId = taskMgr.adoptRunning(parent.cancelFlag(), subAgent, subConv, aArgs.name(),
                                           null /* already done? */, cancelFlag, partial);
       return Result.ok(String.format("{\"task_id\":\"%s\",\"status\":\"timed_out_to_background\"}", taskId));
   } catch (Exception e) {
       events.close();
       return Result.error("subagent error: " + e.getMessage());
   }
   ```
5. 实现辅助函数:`isSubAgentContext / withSubAgentContext / parentConvOf / aggregatePartial`
6. 提供 `setParent(Agent a)` 让 Main 在 `new TuiApp(...)` 之后回填 parent 引用

**验证:** `mvn test -Dtest=AgentToolTest` 通过(T18)

## T18: Agent 工具测试**文件:** `src/test/java/dev/gcode/agent/AgentToolTest.java`
**依赖:** T17
**步骤:**
1. 测试 missing prompt → 返回错误
2. 测试 unknown `subagent_type` → 返回错误
3. 测试 known `subagent_type`(用一个 mock catalog 注入)→ 子 Agent 跑动并返回结果
4. 测试 `run_in_background=true` → 返回 `async_launched` JSON
5. 测试嵌套:用 `withSubAgentContext` 包 ctx 后调 execute → 返回错误
6. 测试 `isForkContext` 兜底:用 forked subConv 调,Agent 工具拦截
7. 测试 `enableSubAgentBackground=false` 时 background 路径报错

**验证:** `mvn test -Dtest=AgentToolTest` 全部通过

## T19: task 包基础结构**文件:** `src/main/java/dev/gcode/task/Manager.java`
**依赖:** T10, T15
**步骤:**
1. 新建包 `dev.gcode.task`,加 `package-info.java` 与 `Manager.java`
2. 声明 `enum Status { RUNNING, COMPLETED, FAILED, CANCELLED }`(单独 `Status.java`)
3. 声明 `record Usage(long input, long output, long cacheWrite, long cacheRead)`(对齐 `agent.Usage`)
4. 声明 `BackgroundTask` 类(字段如 plan.md;字段大多 volatile;`getters` 不可省略)
5. 声明 `record PartialState(...)`
6. 声明 `Manager` 类:
   ```java
   private final Object mu = new Object();
   private final Map<String, BackgroundTask> tasks = new HashMap<>();
   private final Map<String, String> byName = new HashMap<>();
   private final SubmissionPublisher<String> donePub = new SubmissionPublisher<>(
       Executors.newVirtualThreadPerTaskExecutor(), 32);
   private final AtomicLong counter = new AtomicLong();
   ```
7. 实现 `public Manager()`:默认构造
8. 实现 `private String nextId()`:`counter.incrementAndGet()` 后格式化为 `task_<8 字节十六进制>`(用 `(Long.toHexString(System.nanoTime() ^ counter.get()) & 0xFFFFFFFFL)` 等取低 4 字节足够)
9. 实现 `get(id)` / `list()` / `subscribeDone()` 等查询方法,返回 `Optional` / 不可变 List

**验证:** `mvn -q compile` 通过

## T20: Manager.launch 实现**文件:** `src/main/java/dev/gcode/task/Manager.java`
**依赖:** T19
**步骤:**
1. 实现:
   ```java
   public String launch(AtomicBoolean parentCancel, Agent ag, Conversation conv, String name, String taskText) {
       String id = nextId();
       AtomicBoolean cancelFlag = new AtomicBoolean();
       BackgroundTask bt = new BackgroundTask(id, name, ag, conv, taskText,
               Status.RUNNING, Instant.now(), cancelFlag);
       synchronized (mu) {
           tasks.put(id, bt);
           if (name != null && !name.isEmpty()) byName.put(name, id);  // 后启动覆盖前
       }

       Thread.startVirtualThread(() -> {
           SubmissionPublisher<Event> events = new SubmissionPublisher<>();
           Thread.startVirtualThread(() -> aggregateTaskEvents(events, bt));
           try {
               String text = ag.runToCompletion(cancelFlag, conv, taskText, events);
               bt.endTime = Instant.now();
               bt.status = Status.COMPLETED;
               bt.result = text;
           } catch (CancellationException ce) {
               bt.endTime = Instant.now();
               bt.status = Status.CANCELLED;
           } catch (Throwable t) {
               bt.endTime = Instant.now();
               bt.status = Status.FAILED;
               bt.err = t;
           } finally {
               events.close();
               if (!donePub.offer(id, 0, TimeUnit.MILLISECONDS, (sub, item) -> false)) {
                   System.err.printf("task manager: done publisher full, dropping notification for %s%n", id);
               }
           }
       });
       return id;
   }
   ```
2. 实现 `aggregateTaskEvents(SubmissionPublisher<Event> pub, BackgroundTask bt)`:订阅 publisher,每个 Tool PhaseStart 累加 `toolCount` + 更新 `lastActivity`;每个 Usage 累加到 `bt.usage`

**验证:** `mvn test -Dtest=ManagerTest` 通过(T22)

## T21: Manager.stop / adoptRunning / sendMessage / upgradeApproval**文件:** `src/main/java/dev/gcode/task/Manager.java`
**依赖:** T20
**步骤:**
1. 实现 `boolean stop(String id)`:查 tasks → 调 `bt.cancelFlag.set(true)`;返回是否找到
2. 实现 `adoptRunning(...)`:与 launch 类似但接收已 derive 的 ag/conv/cancelFlag/eventSub;创建 BackgroundTask,把 PartialState 字段复制进去,起 virtual thread 继续消费 events publisher 并跑动(注意此时 ag.runToCompletion 已经在前台启动;前台 cancelFlag 被置 true 后子线程 done;Adopt 实际上是开一个 virtual thread 继续消费 events publisher 直到关闭)
   - 简化方案:adopt 不再调 runToCompletion(因为 runToCompletion 已在前台启动);只是注册 BackgroundTask 状态、聚合事件、等 events publisher 关闭后写终态、submit 到 donePub
   - cancelFlag 是新的 derive AtomicBoolean,stop 时用
3. 实现 `sendMessage(parentCancel, name, message)`:
   - 查 `byName` → id
   - 查 `get(id)` → bt;bt.status != COMPLETED → 抛 `TaskBusyException`
   - `bt.conv.addUser(message); bt.status = Status.RUNNING; bt.endTime` 不重置
   - 重新起 virtual thread 跑 `runToCompletion`(同样的 ag/conv);跑完逻辑同 launch
   - 返回 id
4. 实现 `Optional<Outcome> upgradeApproval(AtomicBoolean cancelFlag, ApprovalRequest req)`:把 req 转发到一个全局 publisher(`SubmissionPublisher<ApprovalRequest> approvalPub`);TUI 订阅;返回 `Optional.empty()` 时调用方走默认路径
   - 简化:本期 `upgradeApproval` 直接返回 `Optional.empty()`——让 Approval 走到子 Agent 自己的 publisher,TUI 通过 events 转发感知

**验证:** `mvn test -Dtest=ManagerTest -Dtest.method=stop` 通过

## T22: task 包测试**文件:** `src/test/java/dev/gcode/task/ManagerTest.java`
**依赖:** T20, T21
**步骤:**
1. 用 mock provider + mock agent 模拟一个 subAgent → launch → 用 `Flow.Subscriber` 等 donePub → 验证 `status==COMPLETED`,result 正确
2. 用一个故意 throw 的 mock agent → launch → donePub 收到 → `status==FAILED`,err 非空
3. stop:launch 后立刻 stop → donePub 收到 → `status==CANCELLED`
4. sendMessage:launch + 等 COMPLETED → sendMessage 重新跑 → 拿到新结果
5. byName 覆盖:launch 两次同 name → 后启动覆盖

**验证:** `mvn test -Dtest=ManagerTest` 全部通过

## T23: 4 个后台任务工具**文件:** `src/main/java/dev/gcode/task/{TaskListTool,TaskGetTool,TaskStopTool,SendMessageTool}.java`
**依赖:** T19, T20, T21
**步骤:**
1. 实现 `TaskListTool`:
   - `name() == "TaskList"`,`readOnly() == true`,`parameters()` 空对象
   - `execute`:返回 JSON 形如 `[{"id":"...","name":"...","status":"running","tool_count":3,"last_activity":"bash"}, ...]`
2. 实现 `TaskGetTool`:
   - `name() == "TaskGet"`,`parameters()` 含 `task_id` required
   - `execute`:`m.get(id)` → 全字段 JSON;找不到 → `Result.error(...)`
3. 实现 `TaskStopTool`:
   - `name() == "TaskStop"`,`parameters()` 含 `task_id` required
   - `execute`:`m.stop(id)` → `{"status":"cancellation_requested"}` 或错误
4. 实现 `SendMessageTool`:
   - `name() == "SendMessage"`,`parameters()` 含 `name` / `message` required
   - `execute`:`m.sendMessage(cancelFlag, name, msg)` → `{"task_id":"...","status":"resumed"}` 或错误
5. 所有工具实现 `SystemTool` 接口标记(`isSystem() == true`),让它们在子 Agent 工具列表中默认豁免

**验证:** `mvn test -Dtest=ToolsTest` 通过(T24)

## T24: 4 个工具的单测**文件:** `src/test/java/dev/gcode/task/ToolsTest.java`
**依赖:** T23
**步骤:**
1. TaskList:launch 几个任务后调 → 返回 JSON 含所有
2. TaskGet:已知 id → 返回完整字段
3. TaskGet:未知 id → `Result.isError()==true`
4. TaskStop:stop 一个 running task → 返回成功 + task 状态变 CANCELLED
5. SendMessage:launch 一个任务跑完 → SendMessage → 返回新 status

**验证:** `mvn test -Dtest=ToolsTest` 全部通过

## T25: TUI 加 taskMgr / subAgentCatalog wiring**文件:** `src/main/java/dev/gcode/tui/TuiApp.java`
**依赖:** T6, T19, T23
**步骤:**
1. 在 `TuiParams` record 加字段:
   ```java
   Manager taskMgr;
   Catalog subAgentCatalog;
   ```
2. 在 `TuiApp` 加字段:
   ```java
   private final Manager taskMgr;
   private final Catalog subAgentCatalog;
   ```
3. 在 `TuiApp` 构造内:
   - 把 params 字段挂到字段
   - `init()` 末尾启动 `Thread.startVirtualThread(this::consumeTaskDone)`
4. 在 Agent 构造之后(单 provider 路径):
   - 主 Agent 也应该携带 `approvalUpgrader`(其实主 Agent 不需要;但 AgentTool 构造时需要 `ApprovalUpgrader` 给子 Agent 用)
   - AgentTool 的 parent 通过 `setParent(mainAgent)` 回填

**验证:** `mvn -q compile` 通过

## T26: task notification 注入**文件:** `src/main/java/dev/gcode/tui/Tasks.java`
**依赖:** T19, T25
**步骤:**
1. 新建文件,实现:
   ```java
   void consumeTaskDone() {
       taskMgr.subscribeDone().subscribe(new Flow.Subscriber<>() {
           Flow.Subscription sub;
           public void onSubscribe(Flow.Subscription s) { this.sub = s; s.request(Long.MAX_VALUE); }
           public void onNext(String id) {
               taskMgr.get(id).ifPresent(bt -> {
                   String notif = buildTaskNotification(bt);
                   if (runtime != null) runtime.appendReminders(List.of(notif));
               });
           }
           public void onError(Throwable t) { System.err.println(t); }
           public void onComplete() {}
       });
   }
   ```
2. 实现 `static String buildTaskNotification(BackgroundTask bt)`:
   ```
   <task-notification>
   Task <id> (name="<name>"): <status>
   Result: <result 或 错误>
   </task-notification>
   ```
3. javadoc 解释行为(F19)

**验证:** `mvn -q compile` 通过

## T27: ESC 切后台**文件:** `src/main/java/dev/gcode/tui/Stream.java`
**依赖:** T19, T25
**步骤:**
1. 在 `updateStreaming` 内对 Lanterna `KeyType.Escape` 事件:
   ```java
   if (key.getKeyType() == KeyType.Escape && foregroundSubAgent != null) {
       // 移交后台
       String id = taskMgr.adoptRunning(parentCancel,
               foregroundSubAgent.agent(), foregroundSubAgent.conv(), foregroundSubAgent.name(),
               foregroundSubAgent.eventSub(), foregroundSubAgent.cancelFlag(), foregroundSubAgent.partial());
       foregroundSubAgent = null;
       // 显示一条通知
       scrollback.add(noticeBlock("[esc] 子 Agent 切到后台 (task=" + id + ")"));
   }
   ```
2. 增加 `foregroundSubAgent` 字段(record / 内部类)跟踪当前前台子 Agent;AgentTool 开始前台跑动时设置,跑完清除
3. 注意:前台子 Agent 的跑动其实是在 AgentTool 的 execute 内同步阻塞的,主 TUI 此时是 "等 tool_result" 状态。这意味着 ESC 拦截需要在 AgentTool 的 execute 内做(通过共享 `foregroundSubAgent` 状态)

**简化方案:** 由于前台子 Agent 在 AgentTool 同步阻塞内,ESC 切后台需要工具内监听 cancelFlag 一类机制。本期实现保守版:AgentTool 的前台路径只支持「超时自动切后台」,不支持 ESC 切后台;ESC 切后台留待后续 ch14+ 完善。在 plan.md 与 spec.md 里要标注这一变更。

**重要变更:** F17/AC11 调整为:本期 ESC 切后台**不实现**,只实现「超时自动切后台」与「显式 run_in_background」。spec.md 已写出,checklist 跳过 ESC 场景。

修改方向:跳过 T27 的 ESC 部分,只保留 `foregroundSubAgent` 字段供未来扩展。

**验证:** `mvn -q compile` 通过

## T28: Skill fork 改造**文件:** `src/main/java/dev/gcode/tui/SkillFork.java`
**依赖:** T15
**步骤:**
1. 现有 `runSubAgent` 内部已经在用 `subAgent.run`;改造为用 `runToCompletion`:
   ```java
   String runSubAgent(AtomicBoolean cancelFlag, Conversation conv, ForkOptions opts) throws Exception {
       if (provider == null) throw new SubAgentNoProviderException();

       Provider prov = provider;
       // (model 切换逻辑保留)

       SessionRuntime subRuntime = new SessionRuntime(200_000);
       Agent subAgent = Agent.builder()
               .provider(prov).registry(registry).version(version).engine(engine)
               .runtime(subRuntime)
               .allowedTools(opts.allowedTools())
               .hookEngine(hookEngine)
               .build();

       // 直接调 runToCompletion(events=null,前台同步)
       return subAgent.runToCompletion(cancelFlag, conv, "" /* 此处 conv 末尾已含 user task */, null);
   }
   ```
2. **注意**:现有 `skills.Executor` 调用前已经把任务作为 user 消息装填到 conv(`buildForkConversation` 末尾 `conv.addUser(rendered)`)。新版 `runToCompletion` 内部又会 `conv.addUser(task)`;若 task=="" 会追加空消息。**改 `runToCompletion` 为允许 task=="" 时不追加**(`if (!task.isEmpty()) conv.addUser(task);`),或者改 `skills.Executor` 不再装填 user 消息让 `runToCompletion` 装填。
3. 选第一种方案——`runToCompletion` 加 if 判断

**验证:** `mvn test -Dtest=SkillsTest -Dtest=TuiAppTest` 现有测试不破

## T29: AgentTool 注册到 ToolRegistry**文件:** `src/main/java/dev/gcode/Main.java`
**依赖:** T17, T20, T23, T25
**步骤:**
1. 在 `Main.java` 适当位置(`skills.Catalog.load` 之后):
   ```java
   Catalog subAgentCatalog = Catalog.load(root);
   Manager taskMgr = new Manager();

   // 4 个 task 工具
   registry.register(new TaskListTool(taskMgr));
   registry.register(new TaskGetTool(taskMgr));
   registry.register(new TaskStopTool(taskMgr));
   registry.register(new SendMessageTool(taskMgr));

   // Agent 工具(parent 暂为 null,稍后 setParent)
   AgentTool agentTool = new AgentTool(subAgentCatalog, taskMgr, null,
           cfg.enableSubAgentBackground());
   registry.register(agentTool);
   ```
2. `new TuiApp(...)` 调用扩展 TuiParams:
   ```java
   TuiApp app = new TuiApp(..., new TuiParams(
           writer, memMgr, instructionText, memoryText,
           sessionsDir, catalog, hookEngine,
           taskMgr, subAgentCatalog));
   ```
3. `new TuiApp(...)` 返回后回填 parent:
   ```java
   Agent main = app.mainAgent();
   if (main != null) agentTool.setParent(main);
   ```
4. `TuiApp` 加 `public Agent mainAgent()` 方法返回 `this.agent`

**验证:** `mvn -q -DskipTests package` 编译通过;运行 gcode 不报错

## T30: config 加 enableSubAgentBackground**文件:** `src/main/java/dev/gcode/config/Config.java`
**依赖:** 无
**步骤:**
1. 在 `Config` record 加字段:
   ```java
   Boolean enableSubAgentBackground   // null = 默认 true
   ```
2. 加方法:
   ```java
   public boolean effectiveEnableSubAgentBackground() {
       return enableSubAgentBackground == null ? true : enableSubAgentBackground;
   }
   ```
3. 注释说明:默认 true;false 时所有 SubAgent 强制前台,Fork 路径会报错

**验证:** `mvn -q compile` 通过

## T31: subagent.LaunchFork 公用 wiring**文件:** `src/main/java/dev/gcode/subagent/LaunchFork.java`
**依赖:** T6, T15, T17
**步骤:**
1. 新建 `LaunchFork.java`,实现:
   ```java
   public record ForkLaunchOpts(
           List<String> allowedTools,
           String model,
           Conversation conv,            // 已装填的子对话
           String systemPrompt,
           boolean background,
           SubmissionPublisher<Event> eventsSink,
           Provider provider,
           ToolRegistry registry,
           PermissionEngine engine,
           String version,
           HookEngine hookEngine
   ) {}

   public static String launch(AtomicBoolean cancelFlag, ForkLaunchOpts opts) throws Exception
   ```
2. 实现细节:
   - 构造 SessionRuntime / Agent(类似 AgentTool 的前台路径)
   - 调 `runToCompletion(cancelFlag, opts.conv(), "" /* conv 已含 task */, opts.eventsSink())`
   - 返回 finalText / 抛异常
3. **避免循环依赖**:`subagent.LaunchFork` 引用 agent 包(为构造 Agent);agent 不引用 subagent(AgentTool 是 agent 包内部,工厂签名接受 `AgentCatalogPort` 接口避开 import)
   - 但 AgentTool 内还是要 `import dev.gcode.subagent.Definition`——因为 Definition 类型。这就形成 subagent ← agent 之间的混乱。
   - **拆解方案**:
     - `Definition` 类型放在 subagent 包
     - Catalog 行为通过 agent 包的 `AgentCatalogPort` 接口暴露(只用 `list` 必要方法)
     - `subagent.LaunchFork` 不返回到 agent 中,而是用 agent 暴露的 `runToCompletion` 公共 API
4. 简化:`AgentTool` 直接 `import subagent.Definition`;`subagent.LaunchFork` 也 import agent。**循环依赖!** 这条路走不通。
5. **真正方案**:
   - subagent 包只放 `Definition` / `Catalog` / 加载逻辑(纯数据)
   - `LaunchFork` 放在 agent 包内(因为它要构造 `Agent`)
   - `AgentTool` 也放 agent 包(已有)
   - `tui/SkillFork.java` 调 `agent.LaunchFork.launch(...)`(把 `Definition` 当参数传入)

**重新调整文件结构:**
- 删除 `src/main/java/dev/gcode/subagent/LaunchFork.java`(本任务取消)
- 新建 `src/main/java/dev/gcode/agent/LaunchFork.java` 实现 LaunchFork
- skills 的 fork 回调改为调 `agent.LaunchFork.launch`

**验证:** 见 T28 验证

## T32: 集成测试 - 完整路径**文件:** `src/test/java/dev/gcode/agent/AgentToolIntegrationTest.java`(新增)
**依赖:** T17, T20, T29
**步骤:**
1. 端到端 mock:构造一个 mock provider 让主 Agent 调 Agent 工具(`subagent_type="Explore"`),子 Agent 也跑回纯文本
2. 验证 tool_result 包含子 Agent 的 finalText
3. 验证子 Agent 工具调用没看到 Agent 工具(过滤生效)
4. 验证后台路径:`run_in_background=true` → 立即返回 `async_launched` JSON,主 Agent 继续

**验证:** `mvn test -Dtest=AgentToolIntegrationTest` 通过

## T33: 编译与综合测试**依赖:** T1-T32
**步骤:**
1. `mvn -q -DskipTests package`
2. `mvn spotless:check`(若启用)
3. `mvn test`

**验证:** 全部命令通过,无失败用例

## 执行顺序

```
T1 → T2 → T3
       ↘
        T5 → T6 → T7
       ↗
       T4
T8 → T9
T10 → T11 → T14
T10 → T12 → T13
T14, T15 → T16
T8, T12, T15 → T17 → T18
T19 → T20 → T21 → T22
T19 → T20 → T23 → T24
T6, T19, T23 → T25 → T26
T25 → T27(本期跳过 ESC)
T15 → T28
T30 → T29
T29 → T32
所有 → T33
```
````

````markdown
# SubAgent 机制 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### subagent 包

- [ ] `dev.gcode.subagent` 包存在且编译通过(验证:`mvn -q compile`)
- [ ] `Definition` record 包含 name/description/tools/disallowedTools/model/maxTurns/permissionMode/dontAsk/background/systemPrompt/filePath/source 全部字段(验证:`mvn test -Dtest=ParserTest#definition`)
- [ ] `Parser.parseDefinition` 能正确解析合法 frontmatter + body,`permissionMode=dontAsk` 时 `dontAsk=true`(验证:`mvn test -Dtest=ParserTest`)
- [ ] `Parser.parseDefinition` 对 frontmatter 缺 name/description 抛异常,model 非法 fallback 到 inherit 并 stderr 警告(验证:对应测试通过)
- [ ] 内置 3 个文件(general-purpose/explore/plan)在 `src/main/resources/subagent/builtin/` 下,`Class.getResourceAsStream` 加载成功(验证:`mvn test -Dtest=CatalogTest#builtin`)
- [ ] `Catalog.load` 按 builtin → user → project 顺序加载,同名高优先级覆盖(验证:`mvn test -Dtest=CatalogTest`)
- [ ] `Catalog.resolve("Explore")` 在三层覆盖场景下返回正确 source(验证:对应测试通过)
- [ ] `Catalog.forkDefinition()` 返回 `isFork()==true` 的临时 Definition(验证:对应测试通过)

### tool 过滤多层防线

- [ ] `Filter.ALL_AGENT_DISALLOWED_TOOLS` / `CUSTOM_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 三个常量存在(验证:`mvn test -Dtest=FilterTest#constants`)
- [ ] `Filter.applyAgentToolFilter` 按 spec F30 顺序应用五层过滤(验证:`mvn test -Dtest=FilterTest`)
- [ ] 后台模式下,工具集与 `ASYNC_AGENT_ALLOWED_TOOLS` 取交集,Agent / TaskList / SendMessage 等元工具被剔除(验证:对应测试用例通过)
- [ ] MCP 工具(`mcp__` 前缀)在后台模式下被保留(验证:对应测试用例通过)

### agent 包扩展

- [ ] `Agent.Builder.systemPrompt / maxTurns / permissionMode / dontAsk / approvalUpgrader / provider` 6 个新选项存在且生效(验证:`mvn test -Dtest=AgentTest#builderOptions`)
- [ ] `Fork.buildForkedMessages` 正确克隆父消息 + 处理悬空 tool_use + 追加 Boilerplate(验证:`mvn test -Dtest=ForkTest`)
- [ ] `Fork.isForkContext` 能识别消息中含 `<fork_boilerplate>` 标签(验证:对应测试通过)
- [ ] `Agent.runToCompletion` 能跑完一轮非交互循环,返回最后一条 assistant 文本(验证:`mvn test -Dtest=RunToCompletionTest`)
- [ ] `runToCompletion` 触达 maxTurns 时抛 `MaxTurnsReachedException`(验证:对应测试通过)
- [ ] dontAsk 模式下,工具 Ask 决策被自动转 Allow(验证:对应测试通过)
- [ ] approvalUpgrader 回调在 Ask 决策时被命中(验证:对应测试通过)
- [ ] `runToCompletion` 把 events 转发到外部 `SubmissionPublisher`,Tool/Text/Approval 事件可被订阅(验证:对应测试通过)

### Agent 工具

- [ ] `new AgentTool(...)` 构造的工具 `name()=="Agent"`,`parameters()` 含 prompt/description/subagent_type/model/run_in_background/name 字段(验证:`mvn test -Dtest=AgentToolTest#basic`)
- [ ] `AgentTool.execute` 缺少 prompt 时返回错误(验证:对应测试通过)
- [ ] `AgentTool.execute` 未知 `subagent_type` 时返回错误(验证:对应测试通过)
- [ ] `AgentTool.execute` 定义式 subagent 调用走前台 `runToCompletion`,返回 finalText(验证:对应测试通过)
- [ ] `AgentTool.execute` `run_in_background=true` 时返回 `{"task_id":"...","status":"async_launched"}` JSON(验证:对应测试通过)
- [ ] `AgentTool.execute` 在子 Agent context 内被再次调用时拦截(验证:嵌套阻断测试通过)
- [ ] `AgentTool.execute` 检测到 conv 含 fork boilerplate 时拦截(验证:对应测试通过)
- [ ] `AgentTool.execute` `enableSubAgentBackground=false` 时,`run_in_background=true` 与 fork 路径报错(验证:对应测试通过)

### task 包

- [ ] `task.Manager.launch` 起 virtual thread 跑 `runToCompletion`,跑完写 `status=COMPLETED`,submit 到 donePub(验证:`mvn test -Dtest=ManagerTest#launch`)
- [ ] `task.Manager.launch` virtual thread 内 throw 时,`status=FAILED`,err 含异常信息,主程序不崩(验证:对应测试通过)
- [ ] `task.Manager.stop` 触发 `bt.cancelFlag.set(true)`,virtual thread 退出后 `status=CANCELLED`(验证:对应测试通过)
- [ ] `task.Manager.sendMessage` 在已 COMPLETED 的任务上重新跑动,新 user 消息追加到 conv(验证:对应测试通过)
- [ ] `task.Manager.byName` 后启动覆盖前,`get(byName[name])` 返回最新 task(验证:对应测试通过)
- [ ] `subscribeDone()` 返回的 publisher 在 task 完成时收到 id(验证:对应测试通过)

### 4 个 task 工具

- [ ] `TaskListTool` 返回当前所有任务的 JSON 列表(验证:`mvn test -Dtest=ToolsTest#list`)
- [ ] `TaskGetTool` 返回指定任务的完整字段;未知 id 返回 `Result.isError()==true`(验证:对应测试通过)
- [ ] `TaskStopTool` 调用 `Manager.stop`,返回成功 JSON(验证:对应测试通过)
- [ ] `SendMessageTool` 调用 `Manager.sendMessage`,返回 resumed JSON(验证:对应测试通过)
- [ ] 4 个工具都实现 `SystemTool` 接口,`isSystem()==true`(验证:工具列表过滤时它们对子 Agent 仍可见 - 实际上 ASYNC 白名单优先,在后台子 Agent 中**仍然不可见**;对前台定义式子 Agent 通过 `ALL_AGENT_DISALLOWED` 不在其中)

### TUI 集成

- [ ] `TuiApp` 持有 `taskMgr` 与 `subAgentCatalog` 字段(验证:`mvn -q compile`)
- [ ] `init()` 启动 `consumeTaskDone` virtual thread,任务完成时把 `<task-notification>` 注入 `runtime.pendingReminders`(验证:`mvn test -Dtest=TuiAppTest#consumeTaskDone`)
- [ ] `tui/SkillFork.java` 改造为调 `Agent.runToCompletion` 而非自己拼装循环(验证:现有 skills 测试不破)
- [ ] `Main.java` 注册 4 个 task 工具 + 1 个 Agent 工具,`subAgentCatalog` 与 `taskMgr` 传给 `TuiApp`(验证:`mvn -q -DskipTests package`)
- [ ] `config.Config` 新增 `enableSubAgentBackground` 字段(验证:`mvn -q compile`)

## 集成

- [ ] `subagent.Catalog` 与 `Filter.applyAgentToolFilter` 协同工作:`resolve` 拿到 def,过滤函数按 `def.source/background/tools/disallowedTools` 收窄(验证:`AgentToolIntegrationTest` 通过)
- [ ] Agent 工具的前台调用与现有 ch11 Skill fork 路径不互相干扰(验证:skills 包测试通过 + 手动 tmux 验证一个 inline skill 与一个 Agent 工具调用)
- [ ] Hook 引擎在子 Agent 内仍生效(PreToolUse / PostToolUse 在 `runToCompletion` 内被调用)(验证:hook 包测试 + 子 Agent 跑动手动断言 hook 触发)
- [ ] 主 Agent 工具列表里仍含 Agent + TaskList + TaskGet + TaskStop + SendMessage 共 5 个新工具,数量稳定(验证:工具数计数测试)

## 编译与测试

- [ ] 项目编译无错误:`mvn -q -DskipTests package`
- [ ] 所有单元测试通过:`mvn test`
- [ ] Spotless 检查通过(若启用):`mvn spotless:check`

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

### 场景 1:定义式子 Agent(Explore)前台同步**预置:** 无须额外配置。当前目录 `cd /Users/codemelo/gcode`。

**步骤:**
- [ ] tmux 启动 gcode:`tmux new-session -d -s ch13 -x 200 -y 50 "java -jar target/gcode-*.jar"`
- [ ] 给 LLM 输入:「用 Explore 子 Agent 找出 `src/main/java/dev/gcode/permission` 包下所有以 `test` 开头的方法,只统计数量,不要修改任何文件」
- [ ] LLM 应触发 Agent 工具,`subagent_type="Explore"`,`run_in_background` 未设
- [ ] scrollback 内出现 `● Agent(...)` 工具行,几秒后 Result 行展示子 Agent 的最终文本(含 test* 方法数量)
- [ ] tmux 抓屏(`tmux capture-pane -p -t ch13`)断言:输出包含 `Agent(` 工具行 + 数量数字
- [ ] 验证不改文件:`git status` 干净

### 场景 2:Fork 子 Agent 后台执行**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮:让 LLM 读一些文件铺垫上下文,如「读 `src/main/java/dev/gcode/agent/Agent.java` 头 50 行」
- [ ] 第二轮:「Fork 出去一个子 Agent,统计这个项目里 Java 文件总行数(不指定 subagent_type)」
- [ ] LLM 应触发 Agent 工具,`subagent_type` 留空 → Fork 路径
- [ ] tool_result 应立即返回 `{"task_id":"task_xxx","status":"async_launched"}`
- [ ] 主对话立刻可以继续(输入 `/status` 应能响应)
- [ ] 等 10-30 秒,主对话下一次响应时 reminder 区出现 `<task-notification>` 块,含 Result(行数统计)
- [ ] 用 LLM 验证:「主 Agent,你刚刚有没有收到 task-notification?显示一下」

### 场景 3:主 Agent 用 TaskList / TaskGet 查询**预置:** 接场景 2 之后,或者重启 gcode 后先 launch 一个长跑任务。

**步骤:**
- [ ] 调用一个会跑较久的子 Agent:「用 `run_in_background=true`,让一个 general-purpose 子 Agent 阅读 `src/main/java` 下所有 `.java` 文件 head 200 行,生成总结」
- [ ] 主 Agent 立即返回 task_id
- [ ] 输入:「调 TaskList 看现在有什么后台任务」
- [ ] LLM 调 TaskList 工具,scrollback 显示 task 列表 JSON 含 id/name/status=running/tool_count
- [ ] 输入:「调 TaskGet 看这个任务详情」
- [ ] LLM 调 TaskGet,显示完整字段含 startTime / toolCount / lastActivity 等
- [ ] 等几秒后:「再调 TaskGet 一次」
- [ ] 验证 status 变化或 toolCount 增长

### 场景 4:TaskStop 取消任务**步骤:**
- [ ] 同场景 3 起一个 long-running 任务,拿到 task_id
- [ ] 立刻输入:「调 TaskStop 把刚才那个任务停掉」
- [ ] LLM 调 TaskStop 工具
- [ ] 几秒后:`TaskGet` 应显示 `status=cancelled`
- [ ] 主对话下次 turn 的 reminder 区出现 task-notification 含 `status=cancelled`

### 场景 5:权限决策 - dontAsk 兜底**预置:** 创建项目级自定义 agent:
```
.gcode/agents/auto-bash.md
---
name: auto-bash
description: 自动批准 Bash 调用的测试 Agent
permissionMode: dontAsk
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑,不要询问。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default)
- [ ] 输入:「用 auto-bash 子 Agent 跑 `echo hello-from-subagent`」
- [ ] LLM 调 Agent 工具 `subagent_type=auto-bash`
- [ ] 子 Agent 内部调 bash,**不应该弹出审批弹窗**
- [ ] tool_result 含 `hello-from-subagent` 文本

### 场景 6:权限决策 - 升级到主 TUI**预置:** 创建一个不含 dontAsk 的子 Agent:
```
.gcode/agents/ask-bash.md
---
name: ask-bash
description: 默认权限模式的测试 Agent
maxTurns: 5
---

你是一个测试 Agent。当用户让你跑命令时,直接用 Bash 工具跑。
```

**步骤:**
- [ ] tmux 启动 gcode(权限模式 default,未预先批准 echo)
- [ ] 输入:「用 ask-bash 子 Agent 跑 `echo from-ask-bash`」
- [ ] LLM 调 Agent 工具 `subagent_type=ask-bash`
- [ ] 子 Agent 调 bash 时,**主 TUI 应该弹出审批弹窗**(本期通过子 Agent 的 ApprovalRequest 直接 emit;upgrader 默认返回 `Optional.empty()` 走默认路径,Approval 由 inline 路径 emit 到 TUI)
- [ ] 用户选 Allow Once → 子 Agent 继续 → tool_result 含 `from-ask-bash`

### 场景 7:嵌套阻断 - 定义式子 Agent 看不到 Agent 工具**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent。Explore 内部应该尝试再调用 Agent 工具(比如 prompt 写成『再调用一个 Plan 子 Agent』)」
- [ ] Explore 子 Agent 跑动期间,因为工具列表里没有 Agent 工具,LLM 应该报告「无法调用 Agent」或自己直接做
- [ ] tool_result 不应包含「Agent 工具未注册」一类错误——因为它根本看不到这个工具(被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除)

### 场景 8:嵌套阻断 - Fork 子 Agent 调 Agent 工具被拦截**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「Fork 一个子 Agent,prompt 写『再 fork 一个子 Agent 阅读 README.md』」
- [ ] 主 Agent Fork 出去后立即返回 task_id
- [ ] 等几秒,task-notification 显示子 Agent Result 含「Fork 子 Agent 不能再启动 Agent」错误回灌后的处理结果(或子 Agent 自行调整不再尝试)
- [ ] 调 TaskGet 看子 Agent Result;或 TaskList 看 last_activity

### 场景 9:SendMessage 续派任务**预置:** 无。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 `run_in_background=true name=worker1` 起一个 general-purpose 子 Agent,任务是『列出 `src/main/java/dev/gcode/Main.java` 的 import 块』」
- [ ] 主 Agent 收到 task_id,等几秒后 task-notification 显示 Result(imports 列表)
- [ ] 输入:「调 SendMessage 给 worker1 发『再列出 `src/main/java/dev/gcode/agent/Agent.java` 头 20 行』」
- [ ] LLM 调 SendMessage 工具,`Manager.sendMessage` 重新激活 worker1
- [ ] 等几秒后,task-notification 又显示新 Result(头 20 行)

### 场景 10:超时自动切后台**预置:** 临时把 `AUTO_BACKGROUND_MS` 改成 5 秒(代码常量调小做测试,或加配置项)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 general-purpose 子 Agent,任务是『等 30 秒,然后回复 hello』(让子 Agent 用 bash `sleep 30` 触发长跑)」
- [ ] AgentTool 前台等 5 秒后超时,tool_result 返回 `{"task_id":"...","status":"timed_out_to_background"}`
- [ ] 主对话可以继续接收输入
- [ ] 等够 30 秒后,task-notification 注入主对话含 hello

> 测试完恢复 `AUTO_BACKGROUND_MS=120_000`

### 场景 11.5:全新自定义子 Agent 端到端

> 验证项目级自定义 Agent 文件被加载、resolve 命中、frontmatter 全字段生效、systemPrompt 注入到子 Agent。
> 与场景 5/6/11 区别:那三条聚焦权限/覆盖语义,本条验证"全新角色"作为新增能力。

**预置:** 创建 `.gcode/agents/wc-counter.md`:
```yaml
---
name: wc-counter
description: 行数统计专家,只用 wc -l 计行,然后总结
disallowedTools:
  - write_file
  - edit_file
permissionMode: dontAsk
maxTurns: 5
---

你是一个专门统计代码行数的 Agent。
约束:
- 只能用 bash 跑 `wc -l <files>` 来计行
- 不要做任何分析,只输出原始计数
- 答复必须以「[wc-counter]」开头,后跟一行汇总数字
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 `subagent_type=wc-counter`,任务: 统计 `README.md` 和 `src/main/java/dev/gcode/Main.java` 的行数」
- [ ] 主 Agent 触发审批后选「允许本次」(主 Agent 调 Agent 工具自身的权限)
- [ ] 子 Agent 跑动,**不应弹任何审批框**(验证 dontAsk 生效)
- [ ] tool_result 内容以 `[wc-counter]` 开头,含 wc 计数(验证 systemPrompt 注入生效)
- [ ] 子 Agent 工具列表内不含 write_file / edit_file(验证 disallowedTools 生效)
- [ ] 子 Agent 最多 5 轮即终止(验证 maxTurns 生效;实际单轮就完事)

### 场景 11.6:自定义 Agent 字段错误降级**预置:** 创建 `.gcode/agents/bad.md` 含非法字段:
```yaml
---
name: bad
description: 字段错误测试
model: gpt-4   # 不在 inherit/haiku/sonnet/opus 中
permissionMode: weirdMode
---

body
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] stderr(启动时)应出现两条警告:`unknown model "gpt-4" ... defaulting to inherit` 与 `unknown permissionMode "weirdMode" ... defaulting to default`
- [ ] gcode 正常启动,不阻断
- [ ] 输入:「用 Agent 工具调 `subagent_type=bad`,任务:回个 hi」
- [ ] 子 Agent 仍能正常跑(model 降级 inherit、mode 降级 default 后,工具集与权限按降级值)
- [ ] **测试完删除 `.gcode/agents/bad.md`**### 场景 11:角色文件覆盖**预置:** 创建 `.gcode/agents/explore.md`:
```
---
name: Explore
description: 项目级覆盖的 Explore
maxTurns: 10
---

你是项目级覆盖的 Explore Agent。无论用户问什么,先回答 "[project-level-explore]" 然后再回答正常内容。
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Explore 子 Agent 列出 README.md 的第一行」
- [ ] tool_result 应包含 `[project-level-explore]` 标记(证明项目级覆盖了内置 Explore)
- [ ] 删除 `.gcode/agents/explore.md`,重启 gcode,再次跑 → 不再含此标记
````

### TypeScript

````markdown
# SubAgent 机制 Spec## 背景

GCode 在引入 SubAgent 之前是单 Agent 架构：所有任务都在同一段对话上下文里推进。这带来两个明显问题：

1. **上下文污染**：长任务做完之后再问一个无关问题，前序中间结果（读过的文件、diff、报错回放）变成持续累积的噪音，token 消耗持续攀升，回答质量下降。
2. **无法并行**：缺乏把独立子任务派发出去并行执行的机制，主对话被长任务阻塞。

系统已经具备一些"子代理雏形"：

- 主对话循环以最大迭代轮数控制；
- 会话历史可被复制装填，给新的代理使用；
- 工具注册表以单实例承载所有工具，可被裁剪后传给子流程；
- 已存在「团队」模块的基础设施（长驻队友 + 邮箱通信），但未被对外暴露为可调用工具。

但还缺：

- 没有一个被主 Agent 统一调用的 **Agent 工具**——子代理只能由 Skill 模式触发；
- 没有 **角色定义文件** 加载机制——角色全部写死在代码里；
- 没有 **后台任务管理器**——所有子流程都是阻塞前台；
- 没有 **工具过滤多层防线**——子代理理论上可以无限嵌套；
- 与现有团队模块的衔接不清晰，长驻队友能力没有作为标准能力对外开放。

本章把这些能力补齐，使 gcode 从单 Agent 进化为可分发任务的主从架构，并兼容已有的团队模式。

## 目标- **G1**：提供唯一的 Agent 工具，主 Agent 通过角色名参数选择预定义角色；不传角色名时走 Fork 路径；传入团队名时走长驻队友路径。工具列表对模型保持稳定，不随角色定义增减而变化。
- **G2**：子 Agent 拥有独立的运行时状态——独立会话历史、独立权限决策、独立模型客户端、独立 token 计数；共享基础设施——经过过滤后的工具集、Hook 引擎、工作目录、模型凭据。
- **G3**：支持三种启动模式：
  - **定义式**：指定角色名命中内置或文件加载的角色定义；以空白会话 + 角色系统提示启动；
  - **Fork 式**：不指定角色名，继承父对话上下文并注入 Fork Boilerplate 约束；强制后台执行；
  - **队友式**：传入团队名后在该团队中起一个长驻队友，队友完成一轮后停留等待新任务投递。
- **G4**：角色定义为 Markdown + YAML frontmatter 文件；支持多来源加载，优先级：项目级 > 用户级 > 内置；同名定义按优先级覆盖。
- **G5**：子 Agent 以"运行至完成"的方式执行——任务直接注入会话，模型不再调工具时结束，把累计的输出文本作为最终结果回给调用方。
- **G6**：子 Agent 使用独立的权限决策器；默认模式可被角色定义中的权限模式字段覆盖；写工具的人工审批弹窗与主 Agent 共用同一渲染路径，并在弹窗中标明来源是哪个子 Agent。
- **G7**：支持后台任务；显式参数、角色定义中"强制后台"开关、Fork 路径任一条件成立即走后台。后台任务以任务对象形式注册到任务管理器并暴露取消入口。
- **G8**：后台任务完成后由 TUI 主循环从任务管理器取走结果，拼成任务通知块注入主对话的提醒区；主 Agent 可通过任务列表 / 任务详情 / 任务停止 / 续派消息等工具主动查询和操控。
- **G9**：工具过滤多层防线阻断子 Agent 无限嵌套——全局禁止列表（子 Agent 永远不能调用 Agent 工具）、后台白名单（后台 Agent 只能用基础读写网络工具）、定义层白名单和黑名单业务约束。
- **G10**：内置 3 个角色——通用型（无禁用）、规划型（禁止写工具、走规划模式）、探索型（禁止写工具、走规划模式、使用更轻量的模型）。
- **G11**：嵌套防护——Fork 派生的子 Agent 被打上来源标记；调用方检测到该标记或会话历史中出现 Fork Boilerplate 标签时拒绝再次 Fork。

## 功能需求### Agent 工具- **F1**：Agent 工具参数（JSON Schema）：
  - `description`（string，必填）：一句话任务标签，供 UI 展示；
  - `prompt`（string，必填）：交给子 Agent 的完整任务说明；
  - `subagent_type`（string，可选）：从已加载的角色定义中按名称选择；留空走 Fork 路径；
  - `model`（string，可选）：模型覆盖，取值含三档主流模型档位；
  - `run_in_background`（bool，可选，默认 false）；
  - `team_name`（string，可选）：传入后走长驻队友路径。
- **F2**：Agent 工具执行主流程：
  1. 校验 `description` / `prompt` 非空；
  2. 若团队名非空且团队管理器已注入 → 走队友路径；
  3. 否则若角色名为空 → 走 Fork 路径；
  4. 否则在已加载角色定义中按名称查找；找不到返回结构化错误「未知 subagent_type」并提示当前可用列表；
  5. 命中后启动定义式子 Agent，把最终文本作为工具输出返回；后台触发条件为「显式参数」或「角色定义强制后台」任一为真。
- **F3**：Agent 工具始终在主 Agent 工具列表里可见；但被工具过滤器加入到子 Agent 的可用工具集时一律剔除（Agent 工具属于全局禁止列表），从根源上断绝定义式子 Agent 嵌套。

### Agent 定义- **F4**：角色定义字段：
  - `name`、`description`（必填）；
  - 工具白名单、工具黑名单（均可选）；
  - 系统提示覆盖、最大轮数、模型档位、权限模式（可选）；
  - 强制后台开关、隔离模式（可选，本期保留位）；
  - 初始 prompt（来自正文体）、跳过项目说明、技能列表、是否继承长记忆、MCP 服务名列表（前向兼容扩展位）。
- **F5**：内置 3 个角色静态声明：
  - 通用型（无禁用）；
  - 规划型（禁止写文件 / 编辑文件，权限模式为规划）；
  - 探索型（禁止写文件 / 编辑文件，权限模式为规划，模型档位为最轻量档）。
- **F6**：角色定义加载顺序：
  1. 初始为全部内置角色；
  2. 用户级目录：用户主目录下 `.gcode/agents/` 中所有 Markdown 文件；
  3. 项目级目录：工作目录下 `.gcode/agents/` 中所有 Markdown 文件。
- **F7**：单个角色定义文件解析规则：
  - 文件以 `---` 起头，下一对 `---` 之间为 YAML frontmatter，之后为正文；
  - 缺 `name` 字段则丢弃；
  - 缺 `description` 时以正文前 200 字符兜底；
  - 其它字段按 YAML 原始键名取；
  - 正文非空时作为初始 prompt 保留。
- **F8**：同名定义按"后加载覆盖先加载"语义在每层加载时就地替换；最终优先级：项目 > 用户 > 内置。
- **F9**：单文件解析失败由 try/catch 吞掉异常并继续加载其它文件，不阻断启动。

### 子 Agent 运行时- **F10**：定义式子 Agent 启动流程：
  1. 解析有效模型——显式覆盖优先于角色定义；非空时用新模型起新客户端，否则复用父客户端；
  2. 构造系统提示——若角色定义提供系统提示覆盖直接使用，否则按当前环境构造默认系统提示；
  3. 用工具过滤器得到子 Agent 的可用工具集；
  4. 用角色定义的权限模式（默认为"自动批准编辑"）构造独立的权限决策器；
  5. 新建会话，把任务 prompt 作为首条 user 消息追加；
  6. 启动 Agent 循环，最大轮数取角色定义值，缺省时取默认值；
  7. 消费事件流：文本累计到输出缓冲，工具调用 / 用量事件透传给观察者；
  8. 命中"循环结束"事件时返回累计输出（空字符串时回退为占位文本）；命中错误事件时把错误描述追加到输出末尾返回。
- **F11**：子 Agent 事件观察接口对 TUI 与团队层暴露，便于上层观察进度而不耦合模型实现。

### 权限决策- **F12**：子 Agent 用独立的权限决策器，模式由角色定义中的权限模式字段控制：
  - 默认模式：写工具与危险命令走人工审批；
  - 自动批准编辑模式：写工具自动放行，命令视规则；
  - 规划模式：禁止写工具与命令工具；
  - 跳过权限模式：跳过所有规则。
- **F13**：审批弹窗与主 Agent 共用同一渲染路径——子 Agent 也会发出"权限请求"事件，由调用方转交主 TUI；弹窗附"来自哪个子 Agent / Fork"的来源标识。

### 后台任务管理- **F14**：任务管理器以映射结构持有任务对象，按自增 id 分配标识。任务对象字段包含 id、名称、状态（运行中 / 已完成 / 已失败）、输出文本、取消入口。
- **F15**：创建任务接口：
  - 生成 id，构造运行中状态的任务对象并立即登记；
  - 触发实际 runner，成功时将状态置为已完成 + 写入输出；失败时将状态置为已失败 + 输出包含错误描述；
  - 返回任务句柄。
- **F16**：查询、列出、停止接口——停止仅对运行中任务生效；停止时调用取消入口，把状态置为已失败，输出固定为「用户停止」。
- **F17**：导出待通知任务接口返回所有非运行中状态的任务；TUI 主循环按需调用，把每条结果拼成任务通知块注入主对话。
- **F18**：Fork 路径强制后台——把 Fork Boilerplate + 任务文本作为新 user 消息交给后台启动器，后者负责登记到任务管理器并立即返回「已启动 / 结果将通过任务通知到达」的字符串。
- **F19**：队友路径：
  - 在团队管理器中查找团队，找不到返回结构化错误并提示用 TeamCreate 创建；
  - 按任务描述派生队友名（空白转连字符，转小写，截短，重名追加自增后缀）；
  - 在团队中启动队友，进入空轮询主循环；
  - 返回「已生成队友、已开始工作」的描述字符串。

### 后台任务相关工具- **F20**：注册一组团队 / 任务系列工具：
  - 团队创建工具；
  - 在指定团队中生成队友的工具；
  - 向指定团队 / 指定队友投递消息的工具；
  - 列出所有团队与队员的工具；
  - 删除团队并停止其队员的工具。
- **F21**：任务管理器与团队的差异：任务管理器面向一次性后台子 Agent；团队面向长驻队友 + 邮箱协议。Agent 工具的队友路径只走团队通道；不带团队名时若 `run_in_background` 为真则注册到任务管理器。

### Fork 路径- **F22**：Fork 启动流程：
  1. 若父对话上下文或后台启动器缺失，返回错误「Fork 需要父对话上下文」；
  2. 嵌套防护：若 Agent 工具本身的"来源标记"已是 Fork 派生，返回错误「不能从一个 Fork 子 Agent 再 Fork」；
  3. 否则扫描父对话历史，若任意消息内容包含 Fork Boilerplate 标签，同样按嵌套拦截返回错误；
  4. 调后台启动器，把 Fork Boilerplate + 任务文本作为首条 user 消息；
  5. 成功返回「已启动」描述字符串；失败返回错误描述。
- **F23**：Fork Boilerplate 是一段包裹了五条不可协商规则的固定文本：
  1. 不能再 Fork；
  2. 不要对话、不要提问、不要请求确认；
  3. 直接使用工具完成任务；
  4. 严格限制在分配的任务范围内；
  5. 最终报告以约定前缀开头且少于 500 字。

### 工具过滤多层防线- **F24**：三类过滤集合：
  - 全局禁止列表：所有子 Agent 永远看不到的工具，含 Agent 工具自身以及任务停止、提问用户、规划模式进入 / 退出、工作流等会破坏子 Agent 工作语义的工具；
  - 自定义 Agent 额外禁止列表：本期与全局禁止列表内容一致，独立维护以便未来分化；
  - 后台 Agent 白名单：只列基础读写、搜索、命令、网络、技能等核心工具。
- **F25**：过滤器输出新的工具集，过滤顺序：
  1. MCP 工具永久放行；
  2. 命中全局禁止列表则跳过；
  3. 标记为"自定义 Agent"且命中自定义禁止列表则跳过；
  4. 标记为"后台 Agent"且不在后台白名单中则跳过；
  5. 命中定义层黑名单则跳过；
  6. 定义层白名单非空时，不命中则跳过。
- **F26**：白名单通配——白名单仅含通配项时视为"不再收窄"，跳过第 6 层过滤。
- **F27**：以上过滤只发生在子 Agent 构造时；主 Agent 看到的工具列表稳定，模型缓存不抖动。

### TUI 集成- **F28**：TUI 在主循环里定期调用任务管理器的"取走通知"接口，把每条结果按下述格式拼到主对话的提醒区：
  ```
  <task-notification>
  Task <id> (name="<name>"): <status>
  Result: <output>
  </task-notification>
  ```
- **F29**：队友路径的进度通过队友 UI 状态向 TUI 暴露 spinner / 动词 / 工具计数。
- **F30**：人工审批弹窗的"来源标签"——子 Agent 触发的权限请求在弹窗里附"来自子 Agent / Fork"字样，与主对话弹窗区分清楚。

## 非功能需求- **N1**：工具列表对模型保持稳定——Agent 工具的 schema 在工具构造时计算一次，运行期新增角色定义文件不会自动重建 schema。
- **N2**：Fork 路径首条 user 消息严格按"Fork Boilerplate + 任务文本"的拼接顺序，保证模型缓存前缀对齐。
- **N3**：子 Agent 崩溃不影响主程序——任务管理器的 runner 异常分支把所有异常转为「已失败」状态 + 错误文本，主进程不退出。
- **N4**：角色定义加载在启动期尽量宽容——单文件解析错误静默吞掉，不阻断启动。
- **N5**：与既有 Skill 系统、Hook 系统、权限系统、主 Agent 循环协同，不破坏既有测试。
- **N6**：跨包引用走显式后缀解析，不引入循环依赖。

## 不做的事

- 文件层面的隔离工作树（保留隔离模式字段位，实现留给后续章节）；
- 多模型混排的团队复杂调度；
- 后台任务跨会话持久化——主程序退出后任务管理器清零；
- 真正的插件系统（MCP 服务名 / 技能名等扩展字段仅保留 schema 位）；
- 子 Agent 输出 schema 强制结构化（返回纯文本即可）；
- 内置的"验证 Agent"开关；
- 通过 ESC 把前台子 Agent 切到后台（本期只走显式 `run_in_background` 与 Fork 自动后台）。

## 验收标准- **AC1**：单元测试与类型检查全部通过。
- **AC2**：Agent 工具 schema 的角色名枚举与已加载角色定义列表一致；至少含通用型、规划型、探索型三项。
- **AC3**：以角色名为「探索型」调用 Agent 工具时进入子 Agent 启动流程，并把角色定义的禁止工具集透传给工具过滤器。
- **AC4**：以一个不存在的角色名调用 Agent 工具时，输出含「未知 subagent_type 'xxx'」及可用列表，并标记为错误结果。
- **AC5**：不传角色名、且未注入父对话上下文 / 后台启动器时，Agent 工具返回错误「Fork 需要父对话上下文」。
- **AC6**：注入父对话上下文 + 后台启动器后，不传角色名调用 Agent 工具时，后台启动器收到的首条消息以 Fork Boilerplate 标签起头且包含任务文本。
- **AC7**：把 Agent 工具的来源标记设为「Fork 派生」后再调用 Fork 路径，返回错误「不能从一个 Fork 子 Agent 再 Fork」。
- **AC8**：构造一个对话，使其某条消息内容包含 Fork Boilerplate 标签，调用 Fork 路径时被嵌套防护命中并返回上述错误。
- **AC9**：以默认参数过滤工具集（非后台），结果中不含 Agent 工具、提问用户、任务停止、工作流、任务输出、规划模式进入 / 退出工具。
- **AC10**：以「后台」标志过滤工具集，结果只含后台白名单与 MCP 工具。
- **AC11**：以白名单 `["读文件", "搜索"]` 过滤工具集，结果仅含这两项与 MCP 工具。
- **AC12**：以黑名单 `["命令工具"]` 过滤工具集，结果不含命令工具。
- **AC13**：项目级 `.gcode/agents/explore.md` 写入新版定义后，角色定义加载返回的「探索型」被覆盖（描述、权限模式等反映项目级版本）。
- **AC14**：项目级 `.gcode/agents/bad.md` 写入非法 YAML 时，角色定义加载仍能返回正常加载的其它定义，不抛异常。
- **AC15**：定义式子 Agent 启动行为：模型覆盖非空时启动新模型客户端；系统提示覆盖非空时不构造默认系统提示；最大轮数等于角色定义值，缺省时取默认值。
- **AC16**：任务管理器创建任务时初始状态为「运行中」；runner 完成后状态转为「已完成」且输出等于完成值；runner 失败时状态转为「已失败」且输出包含错误描述。
- **AC17**：停止任务把运行中任务状态置为「已失败」，输出固定为「用户停止」，并调用注册时传入的取消入口。
- **AC18**：取走通知接口返回所有非运行中任务（已完成 / 已失败）。
- **AC19**：注入团队管理器后调用 Agent 工具传入团队名「alpha」时，在 alpha 团队中可以找到一个名字派生自任务描述的活跃队友。
- **AC20**：上一条中如果 alpha 团队不存在，输出含「团队 'alpha' 不存在，请先用 TeamCreate 创建」。
- **AC21**：三个内置角色名全部为小写连字符；规划型与探索型权限模式均为规划，且禁止工具集均含写文件 / 编辑文件。
````

````markdown
# SubAgent 机制 Plan## 技术栈

- 运行时：bun（`bun run src/main.tsx`）；脚本入口 `package.json` 的 `start` / `test` / `typecheck`。
- 语言：TypeScript 5.x（`tsconfig.json` 严格模式、ESM、`module: NodeNext`）。
- TUI：Ink（React → 终端）、ink-spinner、ink-text-input。
- LLM SDK：`@anthropic-ai/sdk`、`openai`（OpenAI-compat 走同一个客户端封装）。
- MCP：`@modelcontextprotocol/sdk`。
- Markdown：`marked` + `marked-terminal`。
- 配置：`js-yaml`（解析 `.gcode/agents/*.md` frontmatter、`config.yaml`）。
- 模糊搜索：`fuse.js`（与 SubAgent 无直接耦合，但 `loadAgentDefinitions` 在 schema 渲染时可被复用）。
- 终端样式：`chalk`。
- 测试：`bun test`（驱动 `*.test.ts`）。
- 类型检查：`tsc --noEmit`。

## 架构概览

整体分四层：

1. **`src/agents` 子代理核心层**（新增 / 扩展）
   - `definition.ts`：`AgentDefinition` 接口 + `BUILTIN_AGENTS` 数组；
   - `loader.ts`：`loadAgentDefinitions(workDir)` 三层加载 + frontmatter 解析；
   - `tool-filter.ts`：`filterToolsForAgent` 与三个全局工具集合常量；
   - `spawn.ts`：`spawnSubAgent`（一次性同步派生）+ `AgentEventSink` 类型；
   - `task-manager.ts`：`TaskManager` 与 `AgentTask` 接口；
   - `agent-tool.ts`：`AgentTool` 类（实现 `Tool` 接口）+ `FORK_BOILERPLATE` / `FORK_BOILERPLATE_TAG` / `FORK_QUERY_SOURCE` 常量；

2. **`src/teams` 长驻团队层**（已存在，本章被 Agent 工具接入）
   - `team.ts`：`Team` / `TeamManager` / `Member` 类，idle-poll 主循环；
   - `tools.ts`：`TeamCreate` / `SpawnTeammate` / `SendMessage` / `ListTeams` / `TeamDelete` 工具；
   - `file-mailbox.ts`：基于文件的邮箱实现（`.gcode/teams/<team>/<member>/`）；
   - `progress.ts`：`TeammateUIState` 用于 TUI 渲染。

3. **`src/agent` 主循环层**（不动 schema，但 `spawnSubAgent` 直接复用 `Agent` 类）
   - `agent.ts`：主 Agent 与子 Agent 共用同一个 `Agent` 类，通过 `AgentConfig` 不同字段区分 maxIterations / toolFilter；
   - `events.ts`：事件类型 `AgentEvent`，含 `stream_text` / `tool_use` / `usage` / `turn_complete` / `loop_complete` / `error`；
   - `streaming-executor.ts`：负责把 LLM 流式响应翻译成事件。

4. **集成层**（main / TUI）
   - `src/main.tsx`：启动时构造 `TaskManager` / `TeamManager` / 加载 `loadAgentDefinitions(workDir)`、向 `ToolRegistry` 注册 `AgentTool` 及 Team 系列工具；
   - TUI：主循环里调 `TaskManager.drainNotifications()` 把结果拼成 `<task-notification>` 注入主对话 reminder 区。

## 数据流

```
LLM 产 tool_use {name:"Agent", input:{prompt, subagent_type:"explore"}}
  → Agent.streamingExecutor 派发 → ToolRegistry.get("Agent").execute(args, ctx)
  → AgentTool.execute(args, ctx)
       ├─ team_name 非空 → runAsTeammate → TeamManager.get → Team.spawnTeammate
       │                                   → 队友 idle-poll 主循环（异步）
       │                                   → 立即返回 string output
       ├─ subagent_type 空 → runFork → forkHandler(FORK_BOILERPLATE + prompt, conv, registry, model)
       │                              → 后台注册到 TaskManager（外部 handler 控制）
       │                              → 立即返回 string output
       └─ subagent_type 命中定义 → spawnHandler(definition, prompt, background, model)
                                  → spawnSubAgent → 子 Agent 同步跑完 → 返回 finalText

后台完成：
TaskManager.create 内部 .then/.catch 写回 task.status / task.output
  → TUI 主循环 drainNotifications()
  → 拼 <task-notification> 注入 ConversationManager 的下一轮 reminder
  → 主 Agent 下次 turn 自动消费
```

## 核心数据结构与接口### `AgentDefinition`（`src/agents/definition.ts`）

```ts
import type { PermissionMode } from "../permissions/checker.js";

export interface AgentDefinition {
  name: string;
  description: string;
  tools?: string[];
  disallowedTools?: string[];
  systemPromptOverride?: string;
  maxTurns?: number;
  model?: string;
  permissionMode?: PermissionMode;
  background?: boolean;
  isolation?: "worktree";
  initialPrompt?: string;
  omitGuolaicodeMd?: boolean;
  skills?: string[];
  memory?: boolean;
  mcpServers?: string[];
}

export const BUILTIN_AGENTS: AgentDefinition[];
```

### `AgentTool`（`src/agents/agent-tool.ts`）

```ts
export class AgentTool implements Tool {
  name = "Agent";
  description = "Launch a sub-agent to handle complex, multi-step tasks.";
  category = "read" as const;
  system = true;

  querySource = ""; // 被派生时设为 "agent:builtin:fork" 启用嵌套防护

  setTeamManager(mgr: TeamManager, runAgent: RunAgent): void;
  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}
```

构造签名：

```ts
constructor(
  workDir: string,
  registry: ToolRegistry,
  spawnHandler: (
    def: AgentDefinition,
    prompt: string,
    bg: boolean,
    modelOverride?: string,
  ) => Promise<string>,
  conversation?: ConversationManager,
  forkHandler?: (
    prompt: string,
    conversation: ConversationManager,
    registry: ToolRegistry,
    modelOverride?: string,
  ) => Promise<string>,
);
```

### `TaskManager` / `AgentTask`（`src/agents/task-manager.ts`）

```ts
export interface AgentTask {
  id: string;
  name: string;
  status: "running" | "completed" | "failed";
  output: string;
  cancel: () => void;
}

export class TaskManager {
  create(name: string, runner: () => Promise<string>, cancel: () => void): AgentTask;
  get(id: string): AgentTask | undefined;
  list(): AgentTask[];
  stop(id: string): void;
  drainNotifications(): AgentTask[];
}
```

### `filterToolsForAgent`（`src/agents/tool-filter.ts`）

```ts
export const ALL_AGENT_DISALLOWED_TOOLS: Set<string>;
export const CUSTOM_AGENT_DISALLOWED_TOOLS: Set<string>;
export const ASYNC_AGENT_ALLOWED_TOOLS: Set<string>;

export function filterToolsForAgent(
  registry: ToolRegistry,
  allowedTools: string[] | undefined,
  disallowedTools: string[] | undefined,
  isAsync: boolean,
  isCustom?: boolean,
): ToolRegistry;
```

### `spawnSubAgent`（`src/agents/spawn.ts`）

```ts
export type AgentEventSink = (event: {
  type: string;
  toolName?: string;
  args?: Record<string, unknown>;
  usage?: { inputTokens: number; outputTokens: number };
  text?: string;
}) => void;

export async function spawnSubAgent(
  definition: AgentDefinition,
  prompt: string,
  parentClient: LLMClient,
  parentRegistry: ToolRegistry,
  parentProvider: ProviderConfig,
  workDir: string,
  onProgress?: (p: { turn?: number; lastTool?: string }) => void,
  onEvent?: AgentEventSink,
  modelOverride?: string,
): Promise<string>;
```

### `Team` / `TeamManager`（`src/teams/team.ts`）

```ts
export type TeamMode = "in-process" | "tmux" | "iterm";
export type RunAgent = (task: string, onEvent?: AgentEventCallback) => Promise<string>;

export class Team {
  spawnTeammate(name: string, task: string, runAgent: RunAgent): void;
  sendMessage(from: string, to: string, content: string): Promise<void>;
  stopMember(name: string): Promise<void>;
  stopAll(): Promise<void>;
  listMembers(): Member[];
  getMember(name: string): Member | undefined;
}

export class TeamManager {
  create(name: string, mode?: TeamMode): Team;
  get(name: string): Team | undefined;
  list(): Team[];
  delete(name: string): Promise<void>;
}
```

## 模块设计### 模块 A：`src/agents/definition.ts`

- 职责：纯类型 + 内置定义常量；不依赖 IO。
- 对外接口：`AgentDefinition` 接口、`BUILTIN_AGENTS: AgentDefinition[]`。
- 依赖：仅 `src/permissions/checker.ts` 的 `PermissionMode` 类型。
- 关键决策：把内置角色写成静态数组而不是单独的 markdown 文件 + `bun.embed`，避免在 TS 项目里引入运行时资源加载机制。

### 模块 B：`src/agents/loader.ts`

- 职责：把 `~/.gcode/agents/` 与 `<workDir>/.gcode/agents/` 下的 `.md` 文件解析为 `AgentDefinition`；同名后加载覆盖；解析失败静默吞错。
- 对外接口：`loadAgentDefinitions(workDir: string): AgentDefinition[]`。
- 内部函数：`loadDir(dir, definitions)` / `parseAgentDefinition(content)`。
- 依赖：`node:fs`（`readdirSync` / `readFileSync` / `existsSync`）、`node:path`、`node:os`、`js-yaml`、`./definition.js`。
- 关键决策：用 `findIndex` + 替换实现"同名覆盖"，避免 `Map` 后续要再转回 `Array` 顺序丢失。

### 模块 C：`src/agents/tool-filter.ts`

- 职责：在子 Agent 构造时按多层规则把 `ToolRegistry` 收窄；定义 3 个全局工具集合。
- 对外接口：`filterToolsForAgent` 与 3 个 `Set<string>` 常量。
- 依赖：`src/tools/registry.ts`。
- 关键决策：
  - 用 `Set<string>` 而不是数组——查找 O(1)，与定义级 `tools` / `disallowedTools` 数组取交集时需要 `new Set(...)` 包装；
  - MCP 工具按命名前缀 `mcp__*` 永久放行，不需要逐个名字写到白名单；
  - `tools: ["*"]` 视为通配，跳过白名单层。

### 模块 D：`src/agents/spawn.ts`

- 职责：一次性同步派生子 Agent，从 LLM client / system prompt / registry / permission / conversation 拼到 `Agent` 实例，跑完返回 finalText。
- 对外接口：`spawnSubAgent` 与 `AgentEventSink` 类型。
- 依赖：`src/llm/client.ts`（`createClient` / `LLMClient`）、`src/llm/model-resolver.ts`（`resolveModelId`）、`src/conversation/conversation.ts`、`src/prompt/builder.ts`（`buildSystemPrompt` / `detectEnvironment`）、`src/tools/registry.ts`、`src/permissions/checker.ts`、`src/agent/agent.ts`、`./tool-filter.js`。
- 关键决策：把 `for await (const event of agent.run())` 的事件透传给两个回调（`onProgress` 用于 TUI 进度行，`onEvent` 用于 Team 进度更新），不依赖具体 LLM 协议。

### 模块 E：`src/agents/task-manager.ts`

- 职责：后台一次性任务的生命周期管理。
- 对外接口：`TaskManager` 类与 `AgentTask` 接口。
- 依赖：无外部依赖；纯内存 `Map<string, AgentTask>`。
- 关键决策：
  - id 用 `String(this.nextId++)` 顺序生成；
  - `stop()` 把状态写为 `"failed"` + `"Stopped by user"` 而不是单独的 `"cancelled"` 状态，简化下游 UI 渲染分支；
  - `drainNotifications()` 不消费 tasks（不删除条目），调用方自行追踪"已通知过哪些 id"避免重复推送。

### 模块 F：`src/agents/agent-tool.ts`

- 职责：把 `Agent` 工具实现为 `Tool` 接口，路由三条派生路径（team / fork / definition）。
- 对外接口：`AgentTool` 类。
- 依赖：`./definition.js`、`./loader.js`、`./tool-filter.js`、`../tools/types.js`、`../tools/registry.js`、`../conversation/conversation.js`、`../teams/team.js`。
- 关键决策：
  - 构造时 eagerly 调 `loadAgentDefinitions(workDir)`，缓存到 `this.definitions`；schema 也只在 schema() 调用时按缓存重建（一次构造内不变）；
  - `spawnHandler` / `forkHandler` 由调用方注入（依赖反转），避免 `AgentTool` 直接 import `spawnSubAgent` 导致循环依赖；
  - `setTeamManager(mgr, runAgent)` 由 main.tsx 在 TaskManager / TeamManager 都构造完后调用一次，启用 `team_name` 路径。

### 模块 G：`src/teams/team.ts`（已存在，本章被 Agent 工具接入）

- 职责：长驻队友 + 邮箱协议；`TeamMode` 支持 `in-process`、`tmux`、`iterm`。
- 关键设计：
  - `spawnTeammate(name, task, runAgent)` 开异步主循环：执行一轮 → 写 `[idle] <name> (reason: <r>)` 到 lead 邮箱 → 轮询自己的邮箱（间隔 `IDLE_POLL_INTERVAL_MS=500ms`）等新消息 → 收到非 `[shutdown]` 消息 → 拼成下一轮 prompt 继续；
  - `cancel` / `stopMember(name)` 把 `member.active=false` 并调可选的 `cancel` 回调；
  - 退出时调 `saveTranscript(workDir, teamName, name, conversation)` 持久化对话用于调试。

## 模块交互### 启动期 wiring（`src/main.tsx`）

```
main.tsx
  ├── createClient(providerCfg, systemPrompt) → llmClient
  ├── new ToolRegistry() → registry
  ├── 注册基础工具（ReadFile/WriteFile/Bash/Grep/Glob/...）
  ├── new TaskManager() → taskMgr
  ├── new TeamManager(workDir) → teamMgr
  ├── new AgentTool(workDir, registry,
  │       spawnHandler = async (def, prompt, bg, model) => {
  │         if (bg) {
  │           // 后台路径：注册到 taskMgr
  │           const ctrl = new AbortController();
  │           const t = taskMgr.create(def.name,
  │             () => spawnSubAgent(def, prompt, llmClient, registry, providerCfg,
  │                                  workDir, undefined, undefined, model),
  │             () => ctrl.abort());
  │           return JSON.stringify({ task_id: t.id, status: "async_launched" });
  │         }
  │         return await spawnSubAgent(def, prompt, llmClient, registry,
  │                                     providerCfg, workDir, undefined, undefined, model);
  │       },
  │       conversation,
  │       forkHandler = async (prompt, conv, reg, model) => { ... taskMgr.create(...) }
  │     ) → agentTool
  ├── agentTool.setTeamManager(teamMgr, runAgentForTeammate)
  ├── 注册 agentTool / TeamCreate / SpawnTeammate / SendMessage / ListTeams / TeamDelete
  └── new Agent({ client, registry, ... }) → 主 Agent
```

### 运行时：主 Agent 调 Agent 工具（定义式，前台）

```
LLM → tool_use {name:"Agent", input:{prompt:"...", subagent_type:"explore"}}
  → StreamingExecutor.execute → registry.get("Agent").execute(args, ctx)
  → AgentTool.execute({ description, prompt, subagent_type:"explore" })
       1. 校验 description/prompt 非空
       2. team_name 空 → 跳过 runAsTeammate
       3. subagent_type 非空 → 跳过 runFork
       4. definitions.find(d => d.name === "explore") → def
       5. spawnHandler(def, prompt, false || def.background=undefined → false, undefined)
            → spawnSubAgent(def, prompt, parentClient, parentRegistry, providerCfg, workDir)
                a. resolveModelId("haiku") → "claude-haiku-4-5-..."
                b. createClient({...providerCfg, model:"claude-haiku-..."}, systemPrompt)
                c. filterToolsForAgent(parentRegistry, undefined, ["EditFile","WriteFile"], false)
                d. new PermissionChecker(workDir, "plan")
                e. new ConversationManager() + addUserMessage(prompt)
                f. new Agent({ client, registry, checker, conversation, workDir, maxIterations: 200 })
                g. for await event of agent.run() {
                     stream_text → output += event.text
                     tool_use   → onEvent({ type:"tool_use", toolName, args })
                     usage      → onEvent({ type:"usage", usage })
                     loop_complete → return output
                   }
       6. 返回 { output: finalText, isError: false }
```

### 运行时：Fork 路径（后台）

```
LLM → tool_use {name:"Agent", input:{prompt:"..." /* 不传 subagent_type */}}
  → AgentTool.execute
       1. 校验
       2. team_name 空 → 跳过
       3. subagent_type 空 → runFork(prompt, description, modelOverride)
            a. this.conversation 与 this.forkHandler 都非空 → 继续
            b. 嵌套防护：querySource !== FORK_QUERY_SOURCE → 继续
            c. 遍历 conversation.getMessages()：无消息含 FORK_BOILERPLATE_TAG → 继续
            d. forkHandler(FORK_BOILERPLATE + "\n\nYour task:\n" + prompt,
                            conversation, registry, modelOverride)
                 → 把任务注册到 TaskManager，立即返回提示字符串
       4. 返回 { output: "Forked agent \"...\" launched in background. Results will arrive via task-notification.", isError: false }
```

### 运行时：team-member 路径

```
LLM → tool_use {name:"Agent", input:{prompt:"...", description:"design API", team_name:"backend"}}
  → AgentTool.execute
       1. 校验
       2. teamManager 已注入 + team_name 非空 → runAsTeammate("backend", "design API", prompt)
            a. teamManager.get("backend") → team；找不到 → 错误
            b. memberName = "design-api"；getMember 命中 → "design-api-2"
            c. team.spawnTeammate("design-api", prompt, this.teamRunAgent!)
                  → 异步启动 idle-poll 主循环，立即返回
       3. 返回 { output: "Teammate 'design-api' spawned in team 'backend' (mode: in-process). ...", isError: false }

team-member idle-poll 主循环（Team.spawnTeammate 内部）：
   while (member.active) {
     await runAgent(nextPrompt, onEvent)
     → 完成一轮 → leadMailbox.send("design-api", "[idle] design-api (reason: available)")
     → waitForNextPromptOrShutdown(member)
        → poll member.mailbox 每 500ms
        → 收到 [shutdown] → break
        → 收到普通消息 → nextPrompt = "You have new messages from your team:\n\nFrom <from>: <text>"
   }
```

### 运行时：后台任务完成 → 主对话注入

```
TaskManager.create 内部 .then(output → status="completed", output=...)
  ↓
TUI 主循环 (Ink render loop)：
   for (const t of taskMgr.drainNotifications()) {
     if (!seenTaskIds.has(t.id)) {
       seenTaskIds.add(t.id);
       reminder.push(`<task-notification>\nTask ${t.id} (name="${t.name}"): ${t.status}\nResult: ${t.output}\n</task-notification>`);
     }
   }
  ↓
下一轮主 Agent.run() → conversation.takePendingReminders() → 注入 system reminder 区
```

### 嵌套阻断

```
定义式子 Agent：
  spawnSubAgent → filterToolsForAgent(parentRegistry, ..., false)
                  → Set "Agent" 命中 ALL_AGENT_DISALLOWED_TOOLS → 跳过
                  → 子 Agent 工具列表里没有 Agent 工具

Fork 子 Agent：
  forkHandler 在内部构造 AgentTool 时把 querySource="agent:builtin:fork"
  → 子 Agent 调 Agent.execute → runFork → querySource === FORK_QUERY_SOURCE → 拒绝
  → 备用兜底：扫描 conversation.getMessages()，若任意消息含 <fork_boilerplate> → 同样拒绝
```

## 文件组织

```text
gcode/
├── src/
│   ├── agents/                          ← 本章核心
│   │   ├── definition.ts                AgentDefinition 接口 + BUILTIN_AGENTS
│   │   ├── loader.ts                    loadAgentDefinitions + parseAgentDefinition
│   │   ├── tool-filter.ts               filterToolsForAgent + 三个全局常量
│   │   ├── spawn.ts                     spawnSubAgent + AgentEventSink
│   │   ├── task-manager.ts              TaskManager + AgentTask
│   │   ├── agent-tool.ts                AgentTool 类 + FORK_BOILERPLATE 常量
│   │   ├── definition.test.ts
│   │   ├── loader.test.ts
│   │   ├── tool-filter.test.ts
│   │   ├── spawn.test.ts
│   │   ├── task-manager.test.ts
│   │   └── agent-tool.test.ts
│   ├── teams/                           ← 已存在，被 AgentTool.setTeamManager 接入
│   │   ├── team.ts                      Team / TeamManager / RunAgent
│   │   ├── tools.ts                     TeamCreate / SpawnTeammate / SendMessage / ListTeams / TeamDelete
│   │   ├── file-mailbox.ts
│   │   ├── progress.ts                  TeammateUIState
│   │   ├── backend.ts                   detectBackend (in-process / tmux / iterm)
│   │   ├── coordinator.ts
│   │   └── transcript.ts
│   ├── agent/
│   │   ├── agent.ts                     主 Agent / 子 Agent 共用类
│   │   └── events.ts                    AgentEvent 类型
│   ├── conversation/conversation.ts     ConversationManager
│   ├── permissions/checker.ts           PermissionChecker / PermissionMode
│   ├── llm/
│   │   ├── client.ts                    LLMClient / createClient
│   │   └── model-resolver.ts            resolveModelId (haiku/sonnet/opus 别名表)
│   ├── prompt/builder.ts                buildSystemPrompt / detectEnvironment
│   ├── tools/
│   │   ├── registry.ts                  ToolRegistry
│   │   └── types.ts                     Tool / ToolResult / ToolContext / strArg / boolArg
│   └── main.tsx                         启动期 wiring
├── package.json                         bun + ts 配置
└── tsconfig.json
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 子 Agent 与主 Agent 共用 `Agent` 类 | 同一类，通过 `AgentConfig` 字段（`maxIterations` / `toolFilter` / `onPermissionRequest`）切换行为 | 避免两套循环逻辑漂移；ReAct 层面行为应一致 |
| 内置角色存储 | 直接写在 `BUILTIN_AGENTS` 数组里 | TS 项目无原生 `embed` 机制；静态数组类型安全、IDE 跳转便利 |
| Markdown 解析 | `js-yaml` + 手写 `---` 分隔扫描 | 不引入额外依赖；frontmatter 字段简单，full YAML 即可覆盖 |
| 同名定义覆盖 | `findIndex` + 数组下标替换 | 保留加载顺序便于调试；优先级语义清晰（项目 > 用户 > 内置） |
| 解析失败处理 | `try { ... } catch { continue; }` | 单文件错误不阻断其它定义；启动期不卡 |
| 工具过滤数据结构 | `Set<string>` 全局常量 + `new Set(arr)` 在函数内包装定义级数组 | 查找 O(1)；与 Array 类型在 TS 里互转方便 |
| 三条派生路径互斥优先级 | `team_name > subagent_type 缺失 > subagent_type 命中` | team-member 是显式长驻意图；其次 fork 复用上下文；最后定义式从零开始 |
| `AgentTool` 与 `spawnSubAgent` 解耦 | 通过构造参数注入 `spawnHandler` / `forkHandler` | 避免 `agent-tool.ts` 直接 import `spawn.ts` 形成循环；便于测试时 mock |
| `TaskManager` 单进程内存 | `Map<string, AgentTask>` 不做持久化 | 后台任务跨会话持久化属于"不做的事" |
| `TaskManager.stop` 不引入 `"cancelled"` 状态 | 复用 `"failed"` + `output="Stopped by user"` | 状态枚举只 3 项，下游 UI 渲染分支简单 |
| 后台通知形式 | `<task-notification>` 注入主 conversation 的 reminder 区 | 与已有 reminder 机制一致；不打断用户当前操作；主 Agent 下次 turn 自然消费 |
| Fork Boilerplate 字面常量 | 写死在 `agent-tool.ts` 顶部 | 拼接顺序固定，prompt cache 前缀稳定 |
| 嵌套防护双重检测 | `querySource` 标记 + conversation 扫描 | 单一闸门失效时仍能兜底；对话压缩后 querySource 仍在 |
| Team 模式默认 `in-process` | `detectBackend()` 在没有 tmux/iterm 时返回 `in-process` | 测试 / 普通会话不依赖外部多窗口；高级用户可显式切 tmux/iterm |
| `setTeamManager` 后注入 | `AgentTool` 构造时不要求 TeamManager；后续注入启用 team_name | 解耦构造顺序；不强制项目使用 Team 功能 |
| `bun test` 作为唯一测试入口 | 不引入 jest / vitest | bun 内置 test runner，启动快、配置零负担 |
````

````markdown
# SubAgent 机制 Tasks

> 全部代码落在 `src/agents/`，运行时为 bun + TypeScript 5.x；测试走 `bun test`，类型检查走 `tsc --noEmit`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/agents/definition.ts` | `AgentDefinition` 接口 + `BUILTIN_AGENTS` 静态数组 |
| 新建 | `src/agents/definition.test.ts` | 内置 3 个角色的字段断言 |
| 新建 | `src/agents/loader.ts` | `loadAgentDefinitions(workDir)` 三层加载 + `parseAgentDefinition` |
| 新建 | `src/agents/loader.test.ts` | frontmatter 解析、同名覆盖、错误吞抹测试 |
| 新建 | `src/agents/tool-filter.ts` | 3 个全局 `Set<string>` 常量 + `filterToolsForAgent` 多层过滤 |
| 新建 | `src/agents/tool-filter.test.ts` | 过滤多层防线全组合测试 |
| 新建 | `src/agents/spawn.ts` | `spawnSubAgent` 一次性同步派生 + `AgentEventSink` 类型 |
| 新建 | `src/agents/spawn.test.ts` | 子 Agent 跑完返回 finalText / 模型切换 / event 透传测试 |
| 新建 | `src/agents/task-manager.ts` | `TaskManager` 类 + `AgentTask` 接口 |
| 新建 | `src/agents/task-manager.test.ts` | Launch / Stop / drainNotifications 测试 |
| 新建 | `src/agents/agent-tool.ts` | `AgentTool` 类 + `FORK_BOILERPLATE` 常量 + 三条派生路径 |
| 新建 | `src/agents/agent-tool.test.ts` | schema / execute 路径覆盖 / 嵌套阻断测试 |
| 修改 | `src/main.tsx` | 启动期构造 `TaskManager` / `TeamManager`、注册 `AgentTool`、调 `setTeamManager` |
| 修改 | `src/tools/registry.ts` | 不动逻辑；本章只需要现有 `register` / `listTools` / `get` |
| 修改 | `src/teams/team.ts` | 不动；本章只读已有 `Team.spawnTeammate` |
| 修改 | `src/teams/tools.ts` | 不动；与 Agent 工具并存 |

## T1：`AgentDefinition` 接口与内置数组**文件：** `src/agents/definition.ts`
**依赖：** `src/permissions/checker.ts`（`PermissionMode`）
**步骤：**
1. 新建文件，从 `../permissions/checker.js` 引入 `PermissionMode` 类型；
2. 声明 `interface AgentDefinition`，字段：`name` / `description` 必填；`tools` / `disallowedTools` / `systemPromptOverride` / `maxTurns` / `model` / `permissionMode` / `background` / `isolation` / `initialPrompt` / `omitGuolaicodeMd` / `skills` / `memory` / `mcpServers` 全部可选；
3. 导出常量 `BUILTIN_AGENTS: AgentDefinition[]`，包含三项：
   - `general-purpose`：`description="General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks."`；
   - `plan`：`description="Software architect agent for designing implementation plans. Returns step-by-step plans, identifies critical files."`、`disallowedTools=["EditFile","WriteFile"]`、`permissionMode="plan"`；
   - `explore`：`description="Fast read-only search agent for locating code. Use it to find files by pattern, grep for symbols or keywords."`、`disallowedTools=["EditFile","WriteFile"]`、`permissionMode="plan"`、`model="haiku"`。

**验证：** `tsc --noEmit` 编译通过；`bun test src/agents/definition.test.ts` 通过 T2。

## T2：内置角色断言**文件：** `src/agents/definition.test.ts`
**依赖：** T1
**步骤：**
1. 引入 `BUILTIN_AGENTS`；
2. 断言数组长度为 3、`name` 集合等于 `{"general-purpose","plan","explore"}`；
3. 断言 `plan` 与 `explore` 的 `disallowedTools` 都含 `"EditFile"` 与 `"WriteFile"`；
4. 断言 `plan.permissionMode === "plan"` 且 `explore.permissionMode === "plan"`；
5. 断言 `explore.model === "haiku"`。

**验证：** `bun test src/agents/definition.test.ts` 全过。

## T3：`loadAgentDefinitions` 三层加载**文件：** `src/agents/loader.ts`
**依赖：** T1
**步骤：**
1. 引入 `readdirSync` / `readFileSync` / `existsSync`（`node:fs`）、`join`（`node:path`）、`homedir`（`node:os`）、`yaml`（`js-yaml`）、`AgentDefinition` 与 `BUILTIN_AGENTS`；
2. 实现 `loadAgentDefinitions(workDir: string): AgentDefinition[]`：
   - 起点 `definitions = [...BUILTIN_AGENTS]`；
   - 用户级：`loadDir(join(homedir(), ".gcode", "agents"), definitions)`；
   - 项目级：`loadDir(join(workDir, ".gcode", "agents"), definitions)`；
   - 返回 `definitions`；
3. 实现 `loadDir(dir, definitions)`：
   - 目录不存在直接 `return`；
   - `readdirSync(dir).filter(f => f.endsWith(".md"))` 列文件；
   - 对每个文件 `try { content = readFileSync; def = parseAgentDefinition(content); if (def) 用 findIndex 同名替换或 push } catch { continue }`；
4. 实现 `parseAgentDefinition(content): AgentDefinition | null`：
   - 不以 `---` 起头返回 null；
   - 找下一个 `---`，截 frontmatter + body；
   - `yaml.load(frontmatter)` 转 `Record<string, unknown>`；缺 `name` 返回 null；
   - `description` 缺失时取 `body.slice(0, 200)`；
   - 字段映射：`tools` / `disallowed_tools` / `system_prompt` / `max_turns` / `model` / `background` / `isolation`；
   - `body` 非空时填到 `initialPrompt`；
   - 任何异常 `try/catch` 吞抹返回 null。

**验证：** `bun test src/agents/loader.test.ts` 通过 T4。

## T4：`loader` 测试**文件：** `src/agents/loader.test.ts`
**依赖：** T3
**步骤：**
1. 用 `mkdtempSync` 造一个临时 workDir，建 `.gcode/agents/` 目录；
2. 写入合法 `explore.md`（含完整 frontmatter + body）→ 调 `loadAgentDefinitions(workDir)` → 断言返回数组中 `explore.description` 为项目级版本（覆盖内置）；
3. 写入仅含 `name: x` 的 minimal frontmatter → 断言 `description = body.slice(0, 200)`；
4. 写入缺 `---` 的非法文件 → 断言不抛异常，且其它有效文件仍被加载；
5. 写入无 `name` 的 frontmatter → 断言该文件被跳过；
6. 不存在 `~/.gcode/agents/` 时调用不报错。

**验证：** `bun test src/agents/loader.test.ts` 全过。

## T5：工具过滤多层防线**文件：** `src/agents/tool-filter.ts`
**依赖：** `src/tools/registry.ts`
**步骤：**
1. 引入 `ToolRegistry`；
2. 声明 3 个 `Set<string>` 常量：
   - `ALL_AGENT_DISALLOWED_TOOLS = new Set(["TaskOutput","ExitPlanMode","EnterPlanMode","Agent","AskUserQuestion","TaskStop","Workflow"])`；
   - `CUSTOM_AGENT_DISALLOWED_TOOLS = new Set([...同上])`；
   - `ASYNC_AGENT_ALLOWED_TOOLS = new Set(["ReadFile","WebSearch","TodoWrite","Grep","WebFetch","Glob","Bash","EditFile","WriteFile","NotebookEdit","Skill","LoadSkill","SyntheticOutput","ToolSearch","EnterWorktree","ExitWorktree"])`；
3. 实现 `isMCPTool(name): boolean` 返回 `name.startsWith("mcp__")`；
4. 实现 `filterToolsForAgent(registry, allowedTools?, disallowedTools?, isAsync, isCustom=false): ToolRegistry`：
   - 内部 `const disallowed = new Set(disallowedTools ?? []); const allowed = new Set(allowedTools ?? []);`
   - 计算 `hasWhitelist = allowed.size > 0 && !(allowed.size === 1 && allowed.has("*"));`
   - 新建 `filtered = new ToolRegistry()`；
   - 遍历 `registry.listTools()`：
     1. `isMCPTool(name)` → `filtered.register(tool); continue;`
     2. `ALL_AGENT_DISALLOWED_TOOLS.has(name)` → `continue;`
     3. `isCustom && CUSTOM_AGENT_DISALLOWED_TOOLS.has(name)` → `continue;`
     4. `isAsync && !ASYNC_AGENT_ALLOWED_TOOLS.has(name)` → `continue;`
     5. `disallowed.has(name)` → `continue;`
     6. `hasWhitelist && !allowed.has(name)` → `continue;`
     7. `filtered.register(tool);`
   - 返回 `filtered`。

**验证：** `bun test src/agents/tool-filter.test.ts` 通过 T6。

## T6：工具过滤测试**文件：** `src/agents/tool-filter.test.ts`
**依赖：** T5
**步骤：**
1. 写一个 `makeRegistry(names: string[]): ToolRegistry` helper，把每个名字注册为 mock Tool；
2. 测试 1：default 配置 → 注册 `["ReadFile","Agent","AskUserQuestion","mcp__foo"]`，调 `filterToolsForAgent(reg, undefined, undefined, false)` → 结果含 `ReadFile` 与 `mcp__foo`，不含 `Agent` / `AskUserQuestion`；
3. 测试 2：`isAsync=true` → 注册 `["ReadFile","WriteFile","SomeUnknown","mcp__bar"]` → 结果含 `ReadFile` / `WriteFile` / `mcp__bar`，不含 `SomeUnknown`；
4. 测试 3：白名单 `tools=["ReadFile","Grep"]` → 仅含 `ReadFile` / `Grep`；
5. 测试 4：通配 `tools=["*"]` → 不收窄（除了仍要去 ALL_AGENT_DISALLOWED）；
6. 测试 5：黑名单 `disallowedTools=["Bash"]` → 不含 `Bash`；
7. 测试 6：组合（白名单 + 黑名单）→ 白名单先收窄，黑名单再剔除；
8. 测试 7：`isCustom=true` 时 `CUSTOM_AGENT_DISALLOWED_TOOLS` 命中被剔除。

**验证：** `bun test src/agents/tool-filter.test.ts` 全过。

## T7：`spawnSubAgent` 一次性同步派生**文件：** `src/agents/spawn.ts`
**依赖：** T1, T5；`src/llm/client.ts`、`src/llm/model-resolver.ts`、`src/conversation/conversation.ts`、`src/prompt/builder.ts`、`src/permissions/checker.ts`、`src/agent/agent.ts`、`src/config/config.ts`
**步骤：**
1. 引入所需类型与函数：`LLMClient` / `createClient` / `resolveModelId` / `ConversationManager` / `buildSystemPrompt` / `detectEnvironment` / `ToolRegistry` / `PermissionChecker` / `Agent` / `AgentDefinition` / `ProviderConfig` / `filterToolsForAgent`；
2. 声明并导出 `AgentEventSink` 类型；
3. 实现 `spawnSubAgent(definition, prompt, parentClient, parentRegistry, parentProvider, workDir, onProgress?, onEvent?, modelOverride?): Promise<string>`：
   - `effectiveModel = modelOverride || definition.model`；
   - `resolvedModel = effectiveModel ? resolveModelId(effectiveModel) : parentProvider.model`；
   - `env = detectEnvironment(workDir); env.model = resolvedModel;`
   - `systemPrompt = definition.systemPromptOverride ?? buildSystemPrompt(env);`
   - `client = effectiveModel ? await createClient({...parentProvider, model: resolvedModel}, systemPrompt) : parentClient;`
   - `registry = filterToolsForAgent(parentRegistry, definition.tools, definition.disallowedTools, false)`；
   - `permMode = definition.permissionMode ?? "acceptEdits"`；
   - `checker = new PermissionChecker(workDir, permMode)`；
   - `conv = new ConversationManager(); conv.addUserMessage(prompt);`
   - `agent = new Agent({ client, registry, checker, conversation: conv, workDir, maxIterations: definition.maxTurns ?? 200 });`
   - 累计 `output = ""`, `turn = 0`；
   - `for await (const event of agent.run())` 按 `event.type` 分支：
     - `stream_text` → `output += event.text`；
     - `tool_use` → `onProgress?.({lastTool: event.toolName}); onEvent?.({type:"tool_use", toolName, args});`
     - `usage` → `onEvent?.({type:"usage", usage:{inputTokens, outputTokens}});`
     - `turn_complete` → `onProgress?.({turn: ++turn});`
     - `loop_complete` → `return output || "[No output]";`
     - `error` → `return output ? `${output}\n\n[Error: ${event.error.message}]` : `Error: ${event.error.message}`;`
   - 循环结束兜底 `return output || "[No output]"`。

**验证：** `bun test src/agents/spawn.test.ts` 通过 T8。

## T8：`spawnSubAgent` 测试**文件：** `src/agents/spawn.test.ts`
**依赖：** T7
**步骤：**
1. mock `LLMClient`：构造一个返回 `[{type:"stream_text", text:"ok"}, {type:"loop_complete"}]` 的 async iterator；
2. 调 `spawnSubAgent(definition, prompt, mockClient, mockRegistry, providerCfg, workDir)` → 断言返回 `"ok"`；
3. mock 模型切换：传 `modelOverride="haiku"` → 断言内部调用 `createClient` 时第一个参数的 `model` 等于 `resolveModelId("haiku")`；
4. mock onEvent 收集：构造一个吐 `tool_use` + `loop_complete` 的 mock → 断言 onEvent 收到 `{type:"tool_use", toolName: "ReadFile", args: {...}}`；
5. mock 错误事件：吐 `error` → 断言返回串含 `[Error: ...]`；
6. 空输出兜底：mock 直接 `loop_complete` 不吐文本 → 断言返回 `"[No output]"`。

**验证：** `bun test src/agents/spawn.test.ts` 全过。

## T9：`TaskManager` 与 `AgentTask`**文件：** `src/agents/task-manager.ts`
**依赖：** 无
**步骤：**
1. 声明并导出 `interface AgentTask { id; name; status; output; cancel; }`；`status` 为 `"running" | "completed" | "failed"`；
2. 声明并导出 `class TaskManager`：
   - 字段 `private tasks = new Map<string, AgentTask>();` 与 `private nextId = 1;`
   - `create(name, runner, cancel)`：生成 `id = String(this.nextId++)`，构造 `task = {id, name, status:"running", output:"", cancel}`，`this.tasks.set(id, task)`；触发 `runner().then(output => {task.status="completed"; task.output=output;}).catch(err => {task.status="failed"; task.output=`Error: ${(err as Error).message}`;})`；返回 task；
   - `get(id)` / `list()`；
   - `stop(id)`：取 task，若 `status==="running"` → `task.cancel(); task.status="failed"; task.output="Stopped by user";`
   - `drainNotifications()`：遍历 `tasks.values()`，返回所有非 `running` 的任务数组。

**验证：** `bun test src/agents/task-manager.test.ts` 通过 T10。

## T10：`TaskManager` 测试**文件：** `src/agents/task-manager.test.ts`
**依赖：** T9
**步骤：**
1. resolve 路径：`taskMgr.create("worker", async () => "done", () => {})` → 等微任务 → 断言 `status==="completed"` 且 `output==="done"`；
2. reject 路径：runner 抛 `new Error("boom")` → 断言 `status==="failed"` 且 `output` 含 `"Error: boom"`；
3. `stop` 路径：runner 是一个永不 resolve 的 Promise，注册 cancel 回调；`stop(id)` → 断言 cancel 被调一次，`status==="failed"`，`output==="Stopped by user"`；
4. `list()` 返回所有任务；
5. `drainNotifications()` 仅返回非 running 的；运行中的 task 不出现。

**验证：** `bun test src/agents/task-manager.test.ts` 全过。

## T11：`AgentTool` 类**文件：** `src/agents/agent-tool.ts`
**依赖：** T1, T3, T5；`src/tools/types.ts`、`src/tools/registry.ts`、`src/conversation/conversation.ts`、`src/teams/team.ts`
**步骤：**
1. 引入 `Tool` / `ToolResult` / `ToolContext` / `strArg` / `boolArg` / `AgentDefinition` / `BUILTIN_AGENTS` / `loadAgentDefinitions` / `filterToolsForAgent` / `ToolRegistry` / `ConversationManager` / `ToolUseBlock` / `ToolResultBlock` / `TeamManager` / `RunAgent`；
2. 声明顶部常量：
   ```ts
   const FORK_BOILERPLATE_TAG = "<fork_boilerplate>";
   const FORK_QUERY_SOURCE = "agent:builtin:fork";
   const FORK_BOILERPLATE = `${FORK_BOILERPLATE_TAG}
   You are a forked worker process. You are NOT the main agent.
   Rules (non-negotiable):
   1. Do NOT fork again.
   2. Do NOT converse, ask questions, or request confirmation.
   3. Use tools directly: read files, search code, make changes.
   4. Stay strictly within your assigned task scope.
   5. Final report must be under 500 characters, starting with "Scope:".
   </fork_boilerplate>`;
   ```
3. 声明 `class AgentTool implements Tool`：
   - 公共字段：`name="Agent"`、`description`、`category="read" as const`、`system=true`、`querySource=""`；
   - 私有字段：`definitions: AgentDefinition[]`、`registry: ToolRegistry`、`conversation?: ConversationManager`、`teamManager?: TeamManager`、`teamRunAgent?: RunAgent`、`spawnHandler` 函数、`forkHandler?` 函数；
   - 构造：`constructor(workDir, registry, spawnHandler, conversation?, forkHandler?)` 内部 `this.definitions = loadAgentDefinitions(workDir);`
   - `setTeamManager(mgr, runAgent)` 写入两个字段；
4. 实现 `schema(): Record<string, unknown>`：把 `this.definitions.map(d => d.name)` 作为 `subagent_type.enum`，输出包含 `description` / `prompt`（必填）+ `subagent_type` / `model` / `run_in_background` / `team_name` 的 JSON Schema；
5. 实现 `private buildDescription()`：基础描述 + `Available roles for the "subagent_type" parameter:` + 每行 `- ${def.name}: ${def.description}` + 示例调用 shape；
6. 实现 `async execute(args, _ctx): Promise<ToolResult>`：
   - 取 `description = strArg(args, "description")`、`prompt = strArg(args, "prompt")`；任一为空返回 `{output:"Error: description and prompt are required", isError:true}`；
   - 取 `subagentType / modelOverride / background / teamName`；
   - 若 `teamName && this.teamManager && this.teamRunAgent` → return `this.runAsTeammate(teamName, description, prompt)`；
   - 若 `!subagentType` → return `await this.runFork(prompt, description, modelOverride)`；
   - `definition = this.definitions.find(d => d.name === subagentType)`；找不到返回 `Error: unknown agent type '<x>'. Available: ...`；
   - `try { output = await this.spawnHandler(definition, prompt, background || !!definition.background, modelOverride); return {output, isError:false}; } catch (err) { return {output: \`Agent error: ${(err as Error).message}\`, isError:true}; }`；
7. 实现 `private runAsTeammate(teamName, description, prompt): ToolResult`：
   - `team = this.teamManager!.get(teamName)`；空则返回 `Error: team '${teamName}' not found. Create it first with TeamCreate.`；
   - `memberName = description.replace(/\s+/g, "-").toLowerCase().slice(0, 30); let suffix = 2; const base = memberName; while (team.getMember(memberName)) { memberName = \`${base}-${suffix++}\`; }`；
   - `team.spawnTeammate(memberName, prompt, this.teamRunAgent!)`；
   - 返回 `Teammate '<name>' spawned in team '<team>' (mode: <mode>). The teammate is now working on the assigned task.`；
8. 实现 `private async runFork(prompt, description, modelOverride): Promise<ToolResult>`：
   - `!this.conversation || !this.forkHandler` → 返回 `Error: fork requires parent conversation context`；
   - 嵌套防护：`this.querySource === FORK_QUERY_SOURCE` → 返回 `Error: cannot fork from a forked agent. Use subagent_type to spawn a definition-based agent instead.`；
   - `for (const msg of this.conversation.getMessages())` 任意 `msg.content.includes(FORK_BOILERPLATE_TAG)` → 返回同样错误；
   - `try { output = await this.forkHandler(\`${FORK_BOILERPLATE}\n\nYour task:\n${prompt}\`, this.conversation, this.registry, modelOverride); return {output: \`Forked agent "${description}" launched in background. Results will arrive via task-notification.\`, isError:false}; } catch (err) { return {output: \`Fork error: ${(err as Error).message}\`, isError:true}; }`。

**验证：** `tsc --noEmit` 通过；`bun test src/agents/agent-tool.test.ts` 通过 T12。

## T12：`AgentTool` 测试**文件：** `src/agents/agent-tool.test.ts`
**依赖：** T11
**步骤：**
1. 构造一个 mock `ToolRegistry`、mock `ConversationManager`（实现 `getMessages()`）、mock `spawnHandler`（返回 `"ok"`）、mock `forkHandler`（捕获参数）；
2. 测试 schema：构造 AgentTool，`tool.schema().input_schema.properties.subagent_type.enum` 含三个内置 name；
3. 测试缺 prompt：`execute({description:"x"}, ctx)` → `output==="Error: description and prompt are required"`；
4. 测试未知 subagent_type：`execute({description:"x", prompt:"y", subagent_type:"foo"})` → output 含 `unknown agent type 'foo'`；
5. 测试定义式：`execute({description:"x", prompt:"y", subagent_type:"explore"})` → spawnHandler 被调一次，第一个参数 `name==="explore"`；
6. 测试 Fork 缺上下文：构造时不传 conversation/forkHandler → `execute({description:"x", prompt:"y"})` → output 含 `fork requires parent conversation context`；
7. 测试 Fork 正常：构造时传 conversation + forkHandler → execute 时 forkHandler 被调，第一个参数以 `<fork_boilerplate>` 起头且含 `\n\nYour task:\ny`；
8. 测试 querySource 嵌套防护：`tool.querySource = FORK_QUERY_SOURCE; await tool.execute({description:"x", prompt:"y"});` → output 含 `cannot fork from a forked agent`；
9. 测试对话扫描兜底：在 conversation 里塞一条含 `<fork_boilerplate>` 的消息 → execute Fork 路径 → 同样被拦截；
10. 测试 team_name 缺 TeamManager：未调 setTeamManager 时 team_name 被忽略 → 走 Fork 路径；
11. 测试 team_name 正常：注入 mock TeamManager + RunAgent → execute 时 `team.spawnTeammate` 被调用，memberName 派生自 description；
12. 测试 team_name 未知团队：mock teamManager.get 返回 undefined → output 含 `team '<x>' not found`。

**验证：** `bun test src/agents/agent-tool.test.ts` 全过。

## T13：main.tsx 启动期 wiring**文件：** `src/main.tsx`
**依赖：** T1, T7, T9, T11；`src/teams/team.ts`、`src/tools/registry.ts`
**步骤：**
1. 在工具注册段（基础工具注册完后）加：
   ```ts
   const taskMgr = new TaskManager();
   const teamMgr = new TeamManager(workDir);

   const spawnHandler = async (def, prompt, background, modelOverride) => {
     if (background) {
       const ctrl = new AbortController();
       const task = taskMgr.create(
         def.name,
         () => spawnSubAgent(def, prompt, llmClient, registry, providerCfg, workDir, undefined, undefined, modelOverride),
         () => ctrl.abort(),
       );
       return JSON.stringify({ task_id: task.id, status: "async_launched" });
     }
     return await spawnSubAgent(def, prompt, llmClient, registry, providerCfg, workDir, undefined, undefined, modelOverride);
   };

   const forkHandler = async (forkedPrompt, conv, reg, modelOverride) => {
     const ctrl = new AbortController();
     const task = taskMgr.create(
       "fork",
       () => spawnSubAgent({ name: "fork", description: "forked agent" }, forkedPrompt, llmClient, reg, providerCfg, workDir, undefined, undefined, modelOverride),
       () => ctrl.abort(),
     );
     return JSON.stringify({ task_id: task.id, status: "async_launched" });
   };

   const agentTool = new AgentTool(workDir, registry, spawnHandler, conversation, forkHandler);

   const runAgentForTeammate = async (task, onEvent) => {
     return await spawnSubAgent(BUILTIN_AGENTS[0], task, llmClient, registry, providerCfg, workDir, undefined, onEvent);
   };
   agentTool.setTeamManager(teamMgr, runAgentForTeammate);

   registry.register(agentTool);
   registry.register(new TeamCreateTool(teamMgr));
   registry.register(new SpawnTeammateTool(teamMgr, runAgentForTeammate));
   registry.register(new SendMessageTool(teamMgr));
   registry.register(new ListTeamsTool(teamMgr));
   registry.register(new TeamDeleteTool(teamMgr));
   ```
2. 在 Ink 主循环里加 reminder 注入：
   ```ts
   const seenTaskIds = new Set<string>();
   setInterval(() => {
     for (const t of taskMgr.drainNotifications()) {
       if (seenTaskIds.has(t.id)) continue;
       seenTaskIds.add(t.id);
       conversation.pushReminder(`<task-notification>\nTask ${t.id} (name="${t.name}"): ${t.status}\nResult: ${t.output}\n</task-notification>`);
     }
   }, 1000);
   ```
   （若 `ConversationManager` 没有 `pushReminder` 则用现有 reminder 注入路径替代）；
3. 把 `taskMgr` / `teamMgr` 传给 Ink Root 组件以便 `/status` / `TaskList` 等场景使用。

**验证：** `tsc --noEmit` 编译通过；`bun run src/main.tsx` 启动不报错。

## 执行顺序

```text
T1 ──┬─► T2
     ├─► T3 ──► T4
     │
     ├─► T5 ──► T6
     │
     └─► T7 ──► T8
                │
T9 ──► T10 ────┤
               │
T11 ──► T12 ◄──┤
               │
T13 ◄──────────┘  （依赖前面所有模块）
```

- T1 是数据结构基石，其余模块都依赖；
- T3 / T5 / T7 / T9 之间没有强依赖，可并行开发；
- T11 同时依赖 T1 / T3 / T5；
- T12 在 T11 完成后写测试；
- T13 是最后的集成步骤，需要全部模块就绪。
````

````markdown
# SubAgent 机制 Checklist

> 每一项通过运行代码或观察行为验证，聚焦系统行为。所有命令在仓库根目录执行，运行时为 bun + TypeScript 5.x。

## 实现完整性### `AgentDefinition` 与内置数组

- [ ] `src/agents/definition.ts` 存在，`AgentDefinition` 接口含 `name` / `description` / `tools` / `disallowedTools` / `systemPromptOverride` / `maxTurns` / `model` / `permissionMode` / `background` / `isolation` / `initialPrompt` / `omitGuolaicodeMd` / `skills` / `memory` / `mcpServers` 全部字段（验证：`tsc --noEmit` 通过）。
- [ ] `BUILTIN_AGENTS` 数组长度 3，`name` 集合为 `{general-purpose, plan, explore}`（验证：`bun test src/agents/definition.test.ts`）。
- [ ] `plan` 与 `explore` 的 `disallowedTools` 都含 `EditFile` 与 `WriteFile`、`permissionMode === "plan"`（验证：上同）。
- [ ] `explore.model === "haiku"`（验证：上同）。

### `loadAgentDefinitions` 加载器

- [ ] `loadAgentDefinitions(workDir)` 按"内置 → 用户级 → 项目级"顺序加载（验证：`bun test src/agents/loader.test.ts`）。
- [ ] 项目级 `.gcode/agents/explore.md` 覆盖内置 `explore` 的字段（验证：对应测试用例通过）。
- [ ] `parseAgentDefinition` 缺 `name` 字段返回 null，不抛异常（验证：对应测试通过）。
- [ ] 非法文件（缺 `---` / 非法 YAML）被 try/catch 吞抹，其它有效文件仍被加载（验证：对应测试通过）。
- [ ] `~/.gcode/agents/` 目录不存在时 `loadAgentDefinitions` 不报错（验证：对应测试通过）。

### 工具过滤多层防线

- [ ] `src/agents/tool-filter.ts` 暴露 `ALL_AGENT_DISALLOWED_TOOLS` / `CUSTOM_AGENT_DISALLOWED_TOOLS` / `ASYNC_AGENT_ALLOWED_TOOLS` 三个 `Set<string>` 常量（验证：`tsc --noEmit` + import 检查）。
- [ ] `ALL_AGENT_DISALLOWED_TOOLS` 包含 `Agent` / `AskUserQuestion` / `TaskStop` / `Workflow` / `TaskOutput` / `EnterPlanMode` / `ExitPlanMode`（验证：`bun test src/agents/tool-filter.test.ts`）。
- [ ] `filterToolsForAgent` 第一层放行所有 `mcp__*` 工具，无论后续层如何（验证：对应测试通过）。
- [ ] `filterToolsForAgent` 第二层剔除命中 `ALL_AGENT_DISALLOWED_TOOLS` 的工具（验证：对应测试通过）。
- [ ] `isAsync=true` 时仅保留 `ASYNC_AGENT_ALLOWED_TOOLS` 中工具与 MCP 工具（验证：对应测试通过）。
- [ ] `tools=["*"]` 视为通配，跳过白名单层（验证：对应测试通过）。
- [ ] 白名单先收窄、黑名单再剔除的组合语义正确（验证：对应测试通过）。

### `spawnSubAgent` 一次性同步派生

- [ ] `src/agents/spawn.ts` 导出 `spawnSubAgent` 与 `AgentEventSink`（验证：`tsc --noEmit` 通过）。
- [ ] `modelOverride` 非空时调 `resolveModelId` 翻译别名，并通过 `createClient({...parentProvider, model: resolvedModel}, systemPrompt)` 起新客户端（验证：`bun test src/agents/spawn.test.ts`）。
- [ ] `definition.systemPromptOverride` 非空时不调 `buildSystemPrompt`（验证：对应测试通过）。
- [ ] 子 Agent 的 `maxIterations` 等于 `definition.maxTurns ?? 200`（验证：对应测试通过）。
- [ ] `for await (const event of agent.run())` 累计 `stream_text` 到输出，`loop_complete` 时返回累计文本（验证：对应测试通过）。
- [ ] 输出为空时返回字面量 `"[No output]"`（验证：对应测试通过）。
- [ ] `error` 事件被翻译成 `output + "[Error: <msg>]"` 字符串（验证：对应测试通过）。
- [ ] `onProgress` / `onEvent` 回调被 `tool_use` / `usage` / `turn_complete` 触发（验证：对应测试通过）。

### `TaskManager`

- [ ] `src/agents/task-manager.ts` 导出 `TaskManager` 与 `AgentTask`（验证：`tsc --noEmit` 通过）。
- [ ] `create(name, runner, cancel)` 返回 task 起始 `status==="running"`，`output===""`（验证：`bun test src/agents/task-manager.test.ts`）。
- [ ] runner resolve → 异步后 `status==="completed"` 且 `output` 等于 resolve 值（验证：对应测试通过）。
- [ ] runner reject → `status==="failed"` 且 `output` 含 `Error: <msg>`（验证：对应测试通过）。
- [ ] `stop(id)` 仅对 running 任务生效；调 cancel 一次，把 `status` 置为 `"failed"`，`output==="Stopped by user"`（验证：对应测试通过）。
- [ ] `drainNotifications()` 仅返回非 running 的任务（验证：对应测试通过）。

### `AgentTool` 派生路由

- [ ] `src/agents/agent-tool.ts` 顶部声明 `FORK_BOILERPLATE_TAG = "<fork_boilerplate>"` 与 `FORK_QUERY_SOURCE = "agent:builtin:fork"`（验证：源码检查）。
- [ ] `FORK_BOILERPLATE` 字符串含五条 non-negotiable 规则且以 `</fork_boilerplate>` 结尾（验证：源码检查）。
- [ ] `AgentTool.schema()` 的 `subagent_type.enum` 数组与 `this.definitions.map(d => d.name)` 相同（验证：`bun test src/agents/agent-tool.test.ts`）。
- [ ] `execute({description, prompt})` 缺 `prompt` 或缺 `description` 时返回 `Error: description and prompt are required`（验证：对应测试通过）。
- [ ] `execute({description, prompt, subagent_type: "non-existent"})` 返回 `output` 含 `unknown agent type 'non-existent'`（验证：对应测试通过）。
- [ ] `execute({description, prompt, subagent_type: "explore"})` 触发注入的 `spawnHandler`，第一个参数是 `explore` 定义对象（验证：对应测试通过）。
- [ ] 未注入 `conversation` 或 `forkHandler` 时，`execute({description, prompt})` 返回 `Error: fork requires parent conversation context`（验证：对应测试通过）。
- [ ] 注入 `conversation` + `forkHandler` 后，`execute({description, prompt})` 调用 forkHandler 时第一个参数以 `<fork_boilerplate>` 起头且包含 `\n\nYour task:\n${prompt}`（验证：对应测试通过）。
- [ ] `this.querySource = "agent:builtin:fork"` 后再调 fork → 返回 `cannot fork from a forked agent`（验证：对应测试通过）。
- [ ] 对话历史中任意消息 `content` 含 `<fork_boilerplate>` → 调 fork 被同样的错误拦截（验证：对应测试通过）。
- [ ] 注入 `TeamManager` + `RunAgent` 后，`execute({description, prompt, team_name: "alpha"})` 走 `runAsTeammate`，调 `team.spawnTeammate` 一次（验证：对应测试通过）。
- [ ] team_name 指向不存在的团队时返回 `Error: team 'alpha' not found. Create it first with TeamCreate.`（验证：对应测试通过）。

## 集成

- [ ] `src/main.tsx` 启动时构造 `TaskManager` / `TeamManager`、调 `loadAgentDefinitions(workDir)`、注入 `spawnHandler` / `forkHandler` 后构造 `AgentTool` 并 `registry.register(agentTool)`（验证：`tsc --noEmit` + 启动检查）。
- [ ] `AgentTool.setTeamManager(teamMgr, runAgentForTeammate)` 在 register 之前完成调用（验证：源码检查 + 手动 tmux 测试 team_name 路径可用）。
- [ ] `TeamCreate` / `SpawnTeammate` / `SendMessage` / `ListTeams` / `TeamDelete` 五个 Team 工具也注册到主 registry（验证：源码检查 + `bun run src/main.tsx` 输入 `/tools` 显示）。
- [ ] TUI 主循环定期调 `taskMgr.drainNotifications()` 并把结果注入 conversation 的 reminder 区（验证：源码检查 + 场景 2 验证）。
- [ ] Hook 引擎（`src/hooks/*`）在 `spawnSubAgent` 构造的子 Agent 内仍生效，PreToolUse / PostToolUse 被调（验证：现有 hooks 测试 + 子 Agent 跑动手动断言）。
- [ ] 主 Agent 工具列表里 `Agent` 工具数量保持 1，不随 `BUILTIN_AGENTS` 数量或 `.gcode/agents/` 文件变化（验证：源码检查 `schema()` 只暴露单个 `Agent` 工具名）。

## 编译与测试

- [ ] 类型检查通过：`tsc --noEmit` 无错误。
- [ ] 单元测试通过：`bun test` 全部用例。
- [ ] 单包测试集合通过：`bun test src/agents/` 全部用例。
- [ ] 启动检查：`bun run src/main.tsx` 不报错（短时间内 Ctrl+C 退出）。

## 端到端场景

每个场景在 tmux 内启动一个 gcode 实例完成，验证可视化行为。命令示例：`tmux new-session -d -s ch13 -x 200 -y 50 "bun run src/main.tsx"`。

### 场景 1：定义式子 Agent（explore）前台同步**预置：** 无。当前目录 `cd /Users/codemelo/gcode`。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「用 explore 子 Agent 找出 src/permissions 包下所有 `export function` 起头的函数，只统计数量，不要修改任何文件」。
- [ ] LLM 应触发 Agent 工具，`subagent_type="explore"`、`run_in_background` 未设。
- [ ] scrollback 内出现 `● Agent(...)` 工具行，几秒后 Result 行展示子 Agent 的最终文本（含函数数量）。
- [ ] tmux 抓屏（`tmux capture-pane -p -t ch13`）断言输出包含 `Agent(` 工具行 + 数字。
- [ ] 验证不改文件：`git status` 干净。

### 场景 2：Fork 子 Agent 后台执行**预置：** 无。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 第一轮：让 LLM 读一些文件铺垫上下文，如「读 src/agent/agent.ts 头 50 行」。
- [ ] 第二轮：「Fork 出去一个子 Agent，统计这个项目里 .ts 文件总行数（不指定 subagent_type）」。
- [ ] LLM 应触发 Agent 工具，`subagent_type` 留空 → 走 Fork 路径。
- [ ] tool_result 应立即返回 `Forked agent "..." launched in background. Results will arrive via task-notification.`。
- [ ] 主对话立刻可以继续（输入 `/status` 应能响应）。
- [ ] 等 10-30 秒，主对话下一次响应时 reminder 区出现 `<task-notification>` 块，含 Result（行数统计）。
- [ ] LLM 自检：「主 Agent，你刚刚有没有收到 task-notification？显示一下」。

### 场景 3：定义式子 Agent run_in_background**预置：** 无。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「用 Agent 工具 subagent_type=general-purpose 起一个后台子 Agent（run_in_background=true），任务：阅读 src 下所有 .ts 文件 head 100 行，生成总结」。
- [ ] tool_result 立即返回 JSON 形如 `{"task_id":"1","status":"async_launched"}`。
- [ ] 主对话继续工作；等几秒后再触发主 Agent 一轮 → reminder 区出现 `<task-notification>` 含子 Agent 的总结。

### 场景 4：team_name 派生长驻队友**预置：** 主 Agent 先用 TeamCreate 工具建队（或直接走 SpawnTeammate 的自动创建）。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「调 TeamCreate 创建一个名叫 alpha 的团队，模式 in-process」。
- [ ] 输入：「调 Agent 工具，team_name=alpha，description='analyze logging'，prompt='扫描 src 下所有 console.log 调用，统计数量并报告位置'」。
- [ ] tool_result 含 `Teammate 'analyze-logging' spawned in team 'alpha' (mode: in-process). The teammate is now working on the assigned task.`。
- [ ] 队友在后台跑完后向 lead 邮箱发 `[idle] analyze-logging (reason: available)`。
- [ ] 输入：「调 ListTeams 看团队成员状态」 → alpha 队员 `analyze-logging` active。
- [ ] 输入：「调 SendMessage 给 alpha 团队的 analyze-logging 发『再扫一次 src/teams/ 下的 console.error』」→ 队友收到新任务再跑一轮。

### 场景 5：嵌套阻断 - 定义式子 Agent 看不到 Agent 工具**预置：** 无。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「用 explore 子 Agent。给它的 prompt 写：『再调用一个 plan 子 Agent 帮忙规划』」。
- [ ] explore 子 Agent 跑动期间，因为其工具列表里没有 Agent 工具（被 `ALL_AGENT_DISALLOWED_TOOLS` 剔除），LLM 应该报告「无法调用 Agent」或直接做。
- [ ] tool_result 不应含「Agent 工具未注册」一类错误——子 Agent 根本看不到这个工具。

### 场景 6：嵌套阻断 - Fork 子 Agent 调 Agent 工具被拦截**预置：** 无；需要 forkHandler 内部把派生出的 Agent 实例的 `querySource` 设为 `agent:builtin:fork`。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「Fork 一个子 Agent，prompt 写『请再 fork 一个子 Agent 阅读 README.md』」。
- [ ] 主 Agent Fork 出去后立即返回提示字符串。
- [ ] 等几秒，task-notification 显示子 Agent Result 含 `cannot fork from a forked agent` 错误回灌后的处理结果。

### 场景 7：项目级自定义 Agent 端到端**预置：** 创建 `.gcode/agents/wc-counter.md`：
```yaml
---
name: wc-counter
description: 行数统计专家，只用 Bash 跑 wc -l 计行，然后总结
disallowed_tools:
  - WriteFile
  - EditFile
permission_mode: acceptEdits
max_turns: 5
---

你是一个专门统计代码行数的 Agent。
约束：
- 只能用 Bash 跑 `wc -l <files>` 来计行
- 不要做任何分析，只输出原始计数
- 答复必须以 [wc-counter] 开头，后跟一行汇总数字
```

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「用 Agent 工具调 subagent_type=wc-counter，任务：统计 README.md 和 src/main.tsx 的行数」。
- [ ] 子 Agent 跑动；tool_result 内容以 `[wc-counter]` 开头，含 wc 计数（验证 `systemPromptOverride` 注入生效；如果 frontmatter 字段名为 `system_prompt` 也同样有效）。
- [ ] 子 Agent 工具列表内不含 `WriteFile` / `EditFile`（验证 disallowedTools 生效）。
- [ ] 子 Agent 最多 5 轮即终止（验证 maxTurns 生效；实际单轮就完事）。

### 场景 8：自定义 Agent 字段错误降级**预置：** 创建 `.gcode/agents/bad.md`：
```yaml
---
name: bad
description: 字段错误测试
model: gpt-5
permission_mode: weirdMode
---

body
```

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] gcode 正常启动，不阻断；`loader.ts` 中 `parseAgentDefinition` 不校验 `model` / `permissionMode` 的枚举范围，原样填入定义。
- [ ] 输入：「用 Agent 工具调 subagent_type=bad，任务：回个 hi」。
- [ ] 子 Agent 仍能尝试运行；若 model 别名解析失败，`createClient` 抛错被 spawnHandler `.catch` 捕获，task `status="failed"`，主对话下次 turn 看到 `<task-notification>` 含错误信息。
- [ ] **测试完删除 `.gcode/agents/bad.md`**。

### 场景 9：角色文件覆盖**预置：** 创建 `.gcode/agents/explore.md`：
```
---
name: explore
description: 项目级覆盖的 explore
max_turns: 10
---

你是项目级覆盖的 explore Agent。无论用户问什么，先回答 "[project-level-explore]" 然后再回答正常内容。
```

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 输入：「用 explore 子 Agent 列出 README.md 的第一行」。
- [ ] tool_result 应含 `[project-level-explore]` 标记（证明项目级覆盖了内置 explore）。
- [ ] 删除 `.gcode/agents/explore.md`，重启 gcode，再次跑 → 不再含此标记。

### 场景 10：drainNotifications 多次推送去重**预置：** 无。

**步骤：**
- [ ] tmux 启动 gcode。
- [ ] 起 2 个后台任务（场景 3 重复跑两次）。
- [ ] 等都完成后，主对话连续两次 turn 都不应重复看到同一个 `<task-notification>`（验证 `seenTaskIds` 去重生效）。
- [ ] 新起第 3 个任务，完成后第三轮主对话才看到新通知。
````


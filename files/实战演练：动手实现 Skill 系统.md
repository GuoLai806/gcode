# 第11章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装上了 Slash Command 内置命令框架，用户可以通过 `/help` 、 `/clear` 、 `/compact` 这些命令快速操作， `/review` 则走 `prompt` 类型把预设 prompt 转发给 Agent 处理。



这一章要给 GCode 实现 Skill 技能包系统。做完之后，可复用的 AI 操作变成独立的 Markdown 文件，随时可编辑，不需要编译。

两阶段加载让 Agent 平时只看到 Skill 的名字和描述，按需才加载完整指令和专属工具。用户既能用 `/commit` 显式调用，也能说「帮我提交一下」让 Agent 自己匹配。

具体要新增这些东西：

* **Skill 定义与解析&#x20;**：YAML frontmatter 存元信息，Markdown body 存 prompt，解析器负责分离和校验

* **Skill 加载器&#x20;**：三级搜索路径（项目级 > 用户级 > 内置级）、同名覆盖、热加载、自动注册为 Slash Command

* **Skill 执行器&#x20;**：inline / fork 两种执行模式、 `$ARGUMENTS` 参数替换、 `allowedTools` 工具白名单过滤、fail-fast 依赖检查

* **LoadSkill 内置工具&#x20;**：Agent 意图识别后按需加载完整 SOP 和专属工具，通过 ActivateSkill 钉到环境上下文

* **两阶段加载&#x20;**：启动时只注入摘要到 messages，LoadSkill 调用后激活完整内容

* **Agent 侧改动&#x20;**：activeSkills 列表、环境上下文每轮重建、系统工具豁免 allowedTools 过滤（支持 Skill 嵌套）

* **三个内置 Skill&#x20;**：commit（inline）、review（fork）、test（inline）

* **目录型 Skill 支持&#x20;**：SKILL.md + tool.json + references/ 自包含能力包

* **/skill 管理命令&#x20;**：list / info / reload

这章 **不做&#x20;**：Skill 市场和分发、Skill 版本管理。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：让用户不用反复输入同样的提示词。把可复用的 AI 操作封装成独立的 Markdown 文件，打上元信息，支持两阶段加载和两种执行模式。启动时 Agent 只看到 Skill 的名字和说明，要用时再通过一个工具按需把完整指令和专属工具加载进来，同时用工具白名单提升模型选对工具的准确率。

技术要求：

- 单个 Skill 用 YAML frontmatter 加 Markdown 正文描述，frontmatter 放元信息，正文是发给模型的 SOP 指令
- 三级存放（项目目录高于用户目录高于内置），同名按优先级覆盖，解析失败的单个文件跳过不阻断整体
- 两阶段加载：启动时只把名字和一句说明注入对话，要用时再由一个内置工具加载完整指令和专属工具
- 激活后的完整指令钉在环境上下文最显眼的位置，每轮重建都在，多个 Skill 可以同时激活
- 两种执行模式：一种共享当前对话，结果留在主历史里；另一种开独立对话跑完再把摘要回流，还能选带多少历史进去
- 工具白名单收窄当前可用工具，启动时白名单里出现不存在的工具就立刻报错；加载 Skill 的那个工具是系统级，不受白名单约束
- 加载完自动注册成斜杠短命令、支持热更新，清空对话时顺带清掉已激活的 Skill；内置 commit、review、test 三个样板

这一步先不做 Skill 的市场分发和版本管理，留给后续章节。

Skill 定义格式：

- frontmatter 字段：唯一名字、一句话说明、可见工具白名单、执行模式（共享 / 独立）、独立模式带多少历史、可选的指定模型
- 正文是 SOP 指令，支持参数占位符替换用户传入的内容
- 目录型 Skill：一个目录里放入口 Markdown、专属工具的 schema 和实现脚本，整套作为一个能力包分发
```

然后 AI 就会开始问你问题，进行需求澄清。

![]()

你根据理论篇学到的内容回答这些问题，反复循环对齐需求，最后生成四份文档。



### 正式开发

四份文档有了之后，施工图纸定好了，让 Claude Code 根据这四份文档开发

![]()

经过一段时间后，开发完成。

![]()



### 功能验证过程

来验收一下结果



先来试试让GCode直接帮我们安装一个skill

![]()



然后输入

我们可以看到我们有所有我们的目前拥有的skill

![]()



其中，backend- interview会携带新的自己的工具parseResume，那么我们就需要refernces和tool的json了

![]()

然后我们输入

![]()

可以看到，它能根据我们的用户画像，去解析简历，然后进行面试



再试试测试的skill，在ui输入

![]()

会根据SOP去测试



我们输入

![]()



然后我们输入

![]()

会去走我们的commit skill



如果我们是想在Agent任务中自动通过意图识别加载对应的skill，也是可以的，以我们一开始安装的那个forntend-design为例子

![]()

可以看到Agent会自动意图识别和加载对应的skill的文档，然后跟随步骤开发完成后，就有了我们的一个页面展示了

![]()



验收没问题，那么本章的主要任务就完成了。下一章，我们来实现Hook来增加更完整的任务管理和编排能力。

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手（在 `[你的语言]` 处填入你使用的编程语言）：

### Go

````markdown
# Skill 技能包系统 Spec## 背景

ch10 给 GCode 装上了 Slash Command 注册中心和 12 条内置命令，其中 `/review` 是 KindPrompt 类型——把硬编码在源码里的代码审查 prompt 注入对话并触发 LLM。这种"写死在源码里"的 prompt 暴露出几个问题：

- 调整 prompt 必须重新编译，用户没办法在不动源码的前提下定制
- 只有开发者能新增 prompt 类命令，普通用户无法贡献
- prompt 命令拿到的工具集与普通对话完全一致，没法在执行 SOP 时收窄注意力或限制权限
- prompt 是孤零零的字符串，无法捎带专属工具、参考资料、辅助脚本

与此同时,GCode 接入 MCP 之后工具数量从 6 个膨胀到二十多个,模型选错工具的概率随之上升,需要一种机制把"完成某类任务时只看哪些工具"的范围收窄。

Skill 技能包系统在 ch10 命令体系之上解决这两个问题：把可复用的 AI 操作搬出源码、放进可编辑的 Markdown 文件；通过两阶段加载和工具白名单把每次任务的注意力收窄到最小工具子集。

## 目标- **G1**：让可复用的 AI 操作变成独立的 Markdown 文件（每个 Skill 一个目录），增/删/改一个 Skill 不需要重新编译 gcode
- **G2**：自动把已加载的 Skill 注册成 `/<name>` 形式的 Slash Command，沿用 ch10 的 KindPrompt 分支
- **G3**：实现两阶段加载——启动时只把 Skill 的 `name + description` 注入系统提示；Agent 通过 LoadSkill 工具按需把完整 SOP 钉到环境上下文，从而让 Agent 既能被显式命令调用，也能通过自然语言意图自动触发
- **G4**：实现两种执行模式：`inline`（默认，注入主对话）与 `fork`（在 Go 端起子 Agent，跑完返回 finalText 作为 assistant 消息回流主对话），覆盖"需要继承上下文"和"需要客观隔离"两类任务
- **G5**：通过 `allowedTools` 工具白名单做 fail-fast 依赖检查与 SOP 顶部"建议工具"提示，提高模型工具选择准确率
- **G6**：支持目录型 Skill：`SKILL.md` + 可选 `tool.json`（声明专属工具，调用时 exec `references/` 下的可执行脚本）+ `references/`，整套作为自包含能力包
- **G7**：内置 `commit`、`review`、`test` 三个 Skill 通过 Go embed 编译进二进制；同时提供 `InstallSkill` 内置工具从 URL/zip 拉取第三方 Skill 到 `~/.gcode/skills/`
- **G8**：`/clear` 时清空已激活 Skill 列表，保证新会话从干净状态开始

## 功能需求### Skill 定义与解析- **F1**：每个 Skill 是一个目录。目录内必须含一个 `SKILL.md` 文件；其它附属物（`tool.json`、`references/` 子目录）均为可选
- **F2**：`SKILL.md` 由 YAML frontmatter（被两行 `---` 包围）+ Markdown 正文构成。Frontmatter 必填字段为 `name`、`description`；可选字段为 `allowed_tools`、`mode`、`fork_context`、`model`
- **F3**：`name` 必须满足正则 `^[a-z][a-z0-9-]*$`，长度 1-32；`name` 同时作为 Slash Command 命令名
- **F4**：`description` 为一句话描述（建议 ≤120 字符），用于 system prompt 第一阶段注入与 `/help`、`/skill` 输出
- **F5**：`allowed_tools` 为字符串数组；缺省视为空（不限制）
- **F6**：`mode` 取值为 `inline` 或 `fork`；缺省视为 `inline`，未知值按 `inline` 处理并 warning
- **F7**：`fork_context` 取值为 `none` / `recent` / `full`；缺省视为 `none`；仅在 `mode: fork` 时生效，inline 模式下忽略
- **F8**：`model` 为可选字符串，覆盖该 Skill 执行时使用的 LLM 模型；缺省沿用主对话当前模型
- **F9**：Markdown 正文中的 `$ARGUMENTS` 占位符在执行期替换为用户传入的参数文本；如未包含该占位符且参数非空，则在正文末尾以 `\n\n## User Request\n\n<args>` 形式追加；参数为空时按空字符串处理
- **F10**：目录可包含 `tool.json` 文件，描述该 Skill 专属工具数组。每个工具元素包含 `name`（与 frontmatter `allowed_tools` 一致的命名规则）、`description`、`input_schema`（标准 function calling JSON Schema）、`command`（数组：argv 形式，首元素为相对 `references/` 的可执行文件路径或绝对路径）
- **F11**：单个 Skill 解析失败时跳过该 Skill 并打 warning，不阻断其它 Skill 加载

### Skill 加载器（Catalog）- **F12**：启动期按以下顺序扫描，每个位置下的"子目录"视为一个 Skill 候选：
  1. 内置 Skill（Go embed 嵌入 `internal/skills/builtin/<name>/SKILL.md`）
  2. 用户级：`~/.gcode/skills/<name>/`
  3. 项目级：`<projectRoot>/.gcode/skills/<name>/`
- **F13**：同名覆盖按上述顺序依次进行——后扫描的同名 Skill 替换前者。最终优先级为：项目级 > 用户级 > 内置
- **F14**：扫描目录不存在时静默跳过；无 `SKILL.md` 的子目录跳过且打 warning
- **F15**：加载阶段对所有 Skill 的 `allowed_tools` 做 fail-fast 依赖检查——引用的工具名必须存在于主工具注册中心（含 MCP 注入的工具，及 Skill 自己 `tool.json` 注册进来的专属工具）；任一未找到则在启动 banner 后立即打印 error 并跳过该 Skill 加载
- **F16**：Skill 的 `name` 与 ch10 已有内置 Slash Command 命令名（含别名）冲突时，跳过加载该 Skill 并打 warning（理由：内置命令保护）
- **F17**：Catalog 提供 `Reload(workDir)` 方法用于重新扫描三层路径，重新注册所有 Skill 命令；现有命令注册中心提供 `RemoveSkillCommands()` 入口让 Reload 清掉旧的 skill 类命令再重新注册

### Slash Command 自动注册- **F18**：每个加载成功的 Skill 在 ch10 命令注册中心注册一条 `KindPrompt` 命令：
  - 命令名 = Skill 的 `name`
  - 描述 = Skill 的 `description` 末尾追加 `[skill]` 标记
  - 别名为空
  - Hidden = false
- **F19**：用户输入 `/<name>` 等价于显式调用该 Skill（不带参数）；命令 handler 负责调用 Skill 执行器并按执行模式注入对话或起子 Agent
- **F20**：Skill 命令支持 ch10 的自动补全菜单，与内置命令共享同一前缀匹配逻辑

### 两阶段加载与 LoadSkill- **F21**：Prompt 模块新增一段 `skills-catalog`（priority 介于现有 long-term-memory 与 environment 之间），内容为：
  ```
  ## Available Skills
  
  - <name>: <description>
  - <name>: <description>
  ...
  
  Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
  ```
  Catalog 为空时该模块为空字符串，被 prompt assembler 跳过
- **F22**：环境上下文新增一段 `active-skills` 区块，按激活顺序拼接每个已激活 Skill 的 `SKILL.md` 正文（前置一行 `### Skill: <name>` 标题），每轮 Agent loop 重建 env context 时重新装配
- **F23**：注册一个新的内置工具 `LoadSkill`：
  - 输入参数：`{"name": "string"}`
  - 行为：从 Catalog 取 Skill；从磁盘重新读取 `SKILL.md` 拿到最新 body；调用 Agent 提供的 `ActivateSkill(name, body)` 把 Skill 钉到 Active 列表；若该 Skill 有 `tool.json`，把其中的专属工具登记进主工具注册中心（重复登记的工具名静默覆盖）
  - 返回：`Skill <name> activated. SOP pinned to env context. <N> specialized tools registered.`
  - 标记为 read-only（不被权限系统拦截），并在工具过滤逻辑中标记为系统工具（永远可见，不受 allowed_tools 约束）
- **F24**：Agent 侧新增 `ActiveSkills` 列表（基于 SessionRuntime），提供 `ActivateSkill(name, body)`、`ClearActiveSkills()`、`ListActive()` 方法
- **F25**：`/clear` 命令在新建会话前调用 `Agent.ClearActiveSkills()`，确保下一会话的 env context 不再含上一对话激活的 SOP

### Skill 执行器- **F26**：Skill 执行器入口 `Execute(ctx, name, args)`：从 Catalog 取定义；从磁盘重读最新 `SKILL.md`（重读失败回退缓存版本并打 warning）；按 `mode` 走两条分支
- **F27**：`inline` 分支：完成 `$ARGUMENTS` 替换；在正文顶部前插一段"建议工具"提示行（当 `allowed_tools` 非空时）；通过 UI.InjectAndSend 把最终文本作为 user 消息注入主对话并触发回合
- **F28**：`fork` 分支：完成 `$ARGUMENTS` 替换；按 `fork_context` 构造子 Agent 的初始 Conversation（`none`：仅一条 user 消息为 Skill 文本；`recent`：复制主对话末尾最近 5 条消息再追加 Skill 文本；`full`：先用主对话历史调一次 LLM 摘要，再把摘要 + Skill 文本作为初始 user 消息）；按 Skill 的 `model`（若指定）切 provider；按 `allowed_tools` 过滤工具集（LoadSkill 系统工具豁免）；新起子 Agent 跑一轮 Run 拿到 finalText；把 finalText 作为一条 assistant 消息插入主对话历史
- **F29**：fork 分支跑完后主对话沿用主 Agent 继续，不影响主对话的运行时模式/Conversation 长度估算外的其它状态

### InstallSkill 内置工具- **F30**：注册内置工具 `InstallSkill`，输入参数：`{"source": "string"}`。`source` 支持两种形式：
  - HTTP(S) URL 指向单个 `.zip` 文件（按 zip 解压）
  - HTTP(S) URL 指向"目录索引"（页面包含可下载文件列表，本期仅识别 .zip）
- **F31**：InstallSkill 解压目标固定为 `~/.gcode/skills/`。zip 内顶层目录名即为 Skill 名，需满足 F3 命名规范；不满足或 zip 结构非法则报错
- **F32**：InstallSkill 安装成功后调用 Catalog.Reload，自动让新 Skill 的 `/<name>` 命令与 system prompt 第一阶段列表立即可见
- **F33**：InstallSkill 不是系统工具，受权限模式约束（具有外部副作用——写磁盘/网络请求），需要走 ch08 权限系统的用户授权

### /skill 命令- **F34**：注册新的内置 Slash Command `/skill`，KindLocal，零参数：输出已加载 Skill 的精简列表——首行 `Available skills (N):`，随后每条一行 `  /name  description`（按字典序、固定列宽对齐），末行追加 `Type /<skill-name> to invoke a skill.` 引导。来源（builtin/user/project）与模式（inline/fork）等元信息本期不在 `/skill` 输出中展示，开发者需要时直接读 SKILL.md
- **F35**：Catalog 为空时输出一行提示 `No skills loaded.`

## 非功能需求- **N1**：Skill 加载、命令注册全部在 gcode 启动期完成；启动期任何 fail-fast 错误（命名冲突、依赖工具缺失、zip 解压失败之外的解析错误）必须把错误消息打到 stderr 后继续启动但跳过出错 Skill，不阻断 gcode 进程
- **N2**：第一阶段 system prompt 注入的 Skill 列表落在 prompt cache 的稳定前缀区（与 ch07 prompt cache 设计一致），Skill 数量 ≤30 时单轮 cache 命中开销可忽略
- **N3**：第二阶段 active-skills 块每轮重新装配 env context，不通过 user 消息历史维持 SOP 可见性
- **N4**：LoadSkill 是 read-only + 系统工具，跨任意 allowed_tools 白名单都可见；权限系统不拦截
- **N5**：Skill 执行时的 `SKILL.md` 重读路径必须容错——磁盘读失败回退到内存缓存的上一版本并打 warning，不让一次磁盘错误中断已激活的 Skill
- **N6**：fork 模式起子 Agent 跑完后必须把子 Agent 的 token 用量计入主对话的 SessionRuntime.usageAnchor，使后续上下文压缩仍能感知到 fork 烧掉的 token
- **N7**：fork 模式子 Agent 异常退出（超时、ctx 取消、LLM 错）时返回主对话的 assistant 消息为 `[skill <name> failed: <reason>]`，不让主对话卡死
- **N8**：InstallSkill 解压前严格校验 zip 内路径（拒绝 `..`、绝对路径、符号链接），防止 zip-slip
- **N9**：`/clear` 清空 Active Skills 的动作发生在新建 session writer 前，确保新会话首条 env context 已剔除旧 SOP
- **N10**：所有 Skill 文件路径、URL、name 等用户输入在错误信息中保持原样回显，便于排查
- **N11**：UI 抽象层新增 `ActivateSkill / ClearActiveSkills / ListActiveSkills / ListCatalogSkills` 等查询/修改方法，与 ch10 已有 UI 接口风格一致；NopUI 对所有新方法提供零值实现
- **N12**：tool.json 的专属工具 exec 时使用 30 秒固定超时（与现有 bash 工具一致），stdin 传入 JSON 序列化后的工具调用参数，stdout 作为 tool_result 文本回传；exit code 非 0 视为工具失败

## 不做的事

- 不做 Skill 市场分发与版本管理（不实现 `skill.lock`、不做语义化版本依赖）
- 不做 Skill 沙箱隔离（专属工具 exec 直接信任本地脚本，不做 chroot/namespace）
- 不做 Skill 间显式 `canDelegateTo` 类型约束；嵌套调用通过 LoadSkill 系统工具自然实现
- 不做 fork 模式的"参考资料附件传递"——子 Agent 不预读 `references/` 下任何文件，由 SOP 自行通过 ReadFile 取
- 不修改 ch10 状态栏、自动补全菜单的视觉行为
- 不修改 ch10 已有 11 条内置命令的外部行为（除删除 `/review`）
- 不支持 SKILL.md 之外的格式（不接受 `skill.yaml` 单独定义元数据）
- 不支持单文件 Skill（必须是目录形态，方便后续扩展 tool.json 与 references/）
- 不做 Skill 启用/禁用开关命令（要禁用就直接删目录）
- 不在 TUI 里渲染 Skill 详情面板（`/skill` 仅文本输出列表）
- 不为 Skill 提供独立日志文件（与主进程共享 stderr）

## 验收标准- **AC1**：项目根目录与用户目录下都未放 Skill 时，启动 gcode 显示三个内置 Skill：`commit / review / test`；`/skill` 首行输出 `Available skills (3):`，随后三行 `  /<name>  <description>`，末行 `Type /<skill-name> to invoke a skill.`
- **AC2**：内置 `/review` 已从 ch10 命令注册中心移除；启动后 `/help` 不再单独列出 `/review` 而是出现 `/review [skill]`
- **AC3**：用户键入 `/review` 回车，触发 fork 模式 Skill；状态栏进入流式态、AI 输出审查报告后回流到主对话；主对话历史新增一条 assistant 消息（用户角度看不出是 fork）
- **AC4**：用户键入 `/commit` 回车，触发 inline 模式 Skill；主对话注入一条 user 消息（含 commit SOP 文本），LLM 按 SOP 调用 git status / diff / add / commit
- **AC5**：用户键入 `/test` 回车，触发 inline 模式 Skill；主对话注入测试相关的 SOP，LLM 按 SOP 检测项目类型并跑测试
- **AC6**：用户键入"帮我做个后端面试准备"等自然语言；当存在意图匹配的 Skill 时，LLM 主动调用 LoadSkill 工具激活它；下一轮 env context 中能看到该 Skill 的 SOP 钉在 active-skills 块
- **AC7**：LoadSkill 在权限模式为 PlanMode 下也可调用（read-only 标记生效，不被拦截）
- **AC8**：键入 `/clear`，新会话开始后 env context 的 active-skills 块为空，已激活 Skill 全部清掉
- **AC9**：在 `~/.gcode/skills/` 与 `<workDir>/.gcode/skills/` 都放一个 `name: commit` 的 Skill，启动后 `/skill` 中 commit 一行的 description 取自项目级目录的版本（用户级被覆盖；source 信息不在 `/skill` 输出中展示，可通过描述差异区分）
- **AC10**：在 `<workDir>/.gcode/skills/foo/SKILL.md` 中声明 `allowed_tools: [NotExist]`，启动时 stderr 打印 `skill foo: allowed_tool "NotExist" not registered, skipped`，进程继续启动，`/skill` 中不出现 foo
- **AC11**：在某 Skill 目录添加合法 `tool.json` 声明一个 `parse_resume` 工具（command 指向 references/parse_resume.sh，echo "ok"）；执行 LoadSkill 该 Skill 后，主工具注册中心新增 `parse_resume` 工具且 LLM 可调用并得到 `ok` 输出
- **AC12**：使用 LoadSkill 工具调用一个 `name: foo` 但 Catalog 中不存在的 Skill 时，tool_result 返回 `unknown skill: foo`，主对话不被中断
- **AC13**：InstallSkill 工具接受一个 zip URL（本地起 http server 模拟），下载并解压到 `~/.gcode/skills/<name>/`；解压完成后 `/skill` 列表立即包含该 Skill，无需重启
- **AC14**：在受 PlanMode 限制时调用 InstallSkill 工具，被权限系统拦截，提示需要切回默认模式
- **AC15**：恶意 zip 内含 `../../etc/passwd` 路径条目时，InstallSkill 拒绝解压并返回 `unsafe path in zip` 错误
- **AC16**：fork 模式跑完后 SessionRuntime 的 token 锚点已计入子 Agent 用量（用 `/status` 观察累计 token in/out 比 fork 前增加）
- **AC17**：在 tmux 内启动 gcode，依次执行 `/skill → /commit → /review → /test → 自然语言触发 LoadSkill → /clear → /skill`，全程不卡顿、无 panic（端到端场景见 checklist）
````

````markdown
# Skill 技能包系统 Plan## 架构概览

新增一个 `internal/skills` 包承载所有 Skill 相关的"数据 + 加载 + 执行 + 激活态"逻辑，与现有 `internal/command`、`internal/tool`、`internal/prompt`、`internal/agent` 通过细窄接口交互。

按职责拆解：

- **internal/skills**：核心包。包含数据结构（`Skill`、`SkillMeta`、`ToolSpec`、`ActiveEntry`）、`SKILL.md` 解析、`tool.json` 解析、Catalog 三层路径扫描与覆盖、Skill 执行器（inline / fork 分支）、`ActiveSkills` 跨轮列表、`$ARGUMENTS` 渲染、InstallSkill zip 解压（zip-slip 防护），以及通过 Go embed 嵌入的三个内置 Skill 资源
- **internal/tool/load_skill.go**：新增 LoadSkill 工具实现。是系统工具，永远可见，受不带权限拦截
- **internal/tool/install_skill.go**：新增 InstallSkill 工具实现。普通工具，受权限模式约束
- **internal/tool/registry.go**：扩展—增加"系统工具"标记与 `FilterByAllowed(allowed []string)` 切片导出能力；增加"动态注册专属工具"入口（Skill 加载时把 tool.json 工具注册进来）
- **internal/command**：扩展—`RegisterSkillsAsCommands(reg, catalog, executor)` 把 Catalog 中每个 Skill 注册为 KindPrompt 命令；新增 `/skill` 命令（KindLocal，列出 Catalog）；删除 `handleReview` / `/review` 内置命令；UI 接口扩展 `ListCatalogSkills / ListActiveSkills / ClearActiveSkills`
- **internal/prompt**：扩展—`OptionalModules` 中现有的"active-skills"槽位重命名为"skills-catalog"，承载第一阶段名字+描述列表；新增 `RenderActiveSkillsBlock(entries) string` 函数供 env context 拼装
- **internal/agent**：扩展—`SessionRuntime` 新增 `ActiveSkills *skills.ActiveSkills` 字段；`Agent` 新增 `WithCatalog` / `WithSkillExecutor` 选项；`Run` 每轮重建 `sys` 时把 Catalog 列表传入 `BuildSystemPrompt`、`envText` 拼接时调用 `RenderActiveSkillsBlock`；新增 `ClearActiveSkills() / ActivateSkill / ListActive` 入口供 UI 与工具调用
- **internal/tui**：扩展—Model 持有 catalog 引用与执行器；`handleClear` 路径在 `ClearAndNewSession` 后调 `ActiveSkills.Clear`；UI 接口对应新增方法实现

## 核心数据结构### SkillMeta

```go
package skills

type SkillMeta struct {
    Name         string   `yaml:"name"`
    Description  string   `yaml:"description"`
    AllowedTools []string `yaml:"allowed_tools,omitempty"`
    Mode         string   `yaml:"mode,omitempty"`         // "inline" / "fork"
    ForkContext  string   `yaml:"fork_context,omitempty"` // "none" / "recent" / "full"
    Model        string   `yaml:"model,omitempty"`
}
```

约定：`Mode` 为空或 "inline" 视作 inline；`Mode == "fork"` 视作 fork；其它值打 warning 后按 inline 处理。`ForkContext` 仅 fork 时生效，缺省 "none"。

### Skill

```go
type Skill struct {
    Meta       SkillMeta
    PromptBody string      // SKILL.md 去 frontmatter 后的正文（启动时缓存，执行时重读覆盖）
    SourceDir  string      // 绝对路径，重读 SKILL.md / 解析 tool.json 时用
    Source     SkillSource // Builtin / User / Project
    ToolSpecs  []ToolSpec  // tool.json 解析结果（可为空）
}

type SkillSource int

const (
    SourceBuiltin SkillSource = iota
    SourceUser
    SourceProject
)

func (s SkillSource) String() string // "builtin" / "user" / "project"
```

### ToolSpec

```go
type ToolSpec struct {
    Name        string          // 工具名（与 frontmatter allowed_tools 用名一致）
    Description string
    InputSchema json.RawMessage // 标准 function calling JSON Schema
    Command     []string        // argv，首元素相对 SourceDir 解析（或绝对路径）
    BaseDir     string          // 工作目录（exec 时的 cwd），固定为 SourceDir
}
```

### Catalog

```go
type Catalog struct {
    mu     sync.RWMutex
    byName map[string]*Skill
    order  []string // 按 name 排序的稳定迭代序
}

func LoadCatalog(workDir string) *Catalog
func (c *Catalog) Reload(workDir string)            // 内部锁保护，原子替换
func (c *Catalog) Get(name string) (*Skill, bool)
func (c *Catalog) List() []*Skill                   // 按 order
func (c *Catalog) Names() []string
func (c *Catalog) ValidateTools(reg *tool.Registry) []ValidationIssue // fail-fast 检查
```

`LoadCatalog` 按顺序扫描：
1. 通过 embed.FS 列出内置 Skill 目录并解析（`source=builtin`）
2. `~/.gcode/skills/*` 子目录（`source=user`）
3. `<workDir>/.gcode/skills/*` 子目录（`source=project`）

后扫到的同名 `name` 覆盖前者。

### ActiveSkills

```go
type ActiveEntry struct {
    Name string
    Body string // 激活那一刻磁盘上的 SKILL.md 正文
}

type ActiveSkills struct {
    mu      sync.Mutex
    entries []ActiveEntry // 保持激活顺序
    names   map[string]int // 重复激活的话覆盖原位置内容
}

func (a *ActiveSkills) Activate(name, body string)
func (a *ActiveSkills) Clear()
func (a *ActiveSkills) Snapshot() []ActiveEntry // 拷贝出当前列表（env 装配用）
```

### Executor

```go
type Executor struct {
    catalog  *Catalog
    runtime  *agent.SessionRuntime // 持有 ActiveSkills 等跨轮状态
    registry *tool.Registry
    provider llm.Provider          // 默认 provider；fork 时可用 Skill.Model 切换
    eng      *permission.Engine
    version  string
}

func NewExecutor(...) *Executor

// 入口：被 Slash 命令 handler 调用
func (e *Executor) Execute(ctx context.Context, ui command.UI, name, args string) error

// inline 路径直接通过 ui.InjectAndSend
// fork 路径起子 Agent 跑完后通过 ui.AppendAssistantNotice 写回主对话
```

## 模块设计### internal/skills/parser.go
**职责**：解析单个 Skill 目录 → `*Skill`
**对外接口**：`func parseSkillDir(dir string, source SkillSource) (*Skill, error)`
**依赖**：`gopkg.in/yaml.v3`（已在 go.mod 中）

解析流程：
1. 读 `<dir>/SKILL.md`，分离 frontmatter（两行 `---` 之间）与 body
2. yaml.Unmarshal frontmatter → SkillMeta；校验 name 合法性、mode / fork_context 取值
3. 读 `<dir>/tool.json`（不存在则跳过）→ `[]ToolSpec`，校验 command 数组非空、首元素可解析为路径
4. 组装 Skill 返回

### internal/skills/catalog.go
**职责**：三层路径扫描与覆盖管理
**对外接口**：`LoadCatalog / Reload / Get / List / Names / ValidateTools`
**依赖**：`internal/skills/parser`, `embed`

`embed`：
```go
//go:embed builtin/*/SKILL.md builtin/*/tool.json builtin/*/references/*
var builtinFS embed.FS
```

启动时把内置目录解压到一个临时位置或者直接以 fs.FS 抽象传给 parser；为统一处理（专属工具 exec 需要真实文件路径），首启时把内置 Skill 解压到 `$XDG_CACHE_HOME/gcode/builtin-skills/`（或 `os.TempDir`）下，再走与文件系统目录一致的扫描逻辑。

`ValidateTools`：遍历 Catalog 中所有 Skill 的 `Meta.AllowedTools`，确认每个名字都能在传入的 `*tool.Registry` 里 Get 到；记录所有不通过项返回。

### internal/skills/render.go
**职责**：把 Skill body 渲染为最终注入文本（inline 和 fork 路径都先经过这一层）
**对外接口**：`RenderBody(skill *Skill, args string) string`

逻辑：
- 替换所有 `$ARGUMENTS` 出现
- 若无占位符且 args 非空，在末尾追加 `\n\n## User Request\n\n<args>`
- 若 `AllowedTools` 非空，在 body 顶部插一段 ```\nThis skill is designed to use only these tools: <list>. Prefer them over other tools when possible.\n\n---\n\n```

### internal/skills/executor.go
**职责**：inline / fork 分发与执行
**对外接口**：`NewExecutor / Execute`

inline 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`（失败回退缓存）
3. RenderBody
4. `ui.InjectAndSend(displayLabel, body)` —— displayLabel 例如 `/<name>`

fork 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`
3. RenderBody
4. 按 `ForkContext` 构造初始 Conversation：
   - none：仅一条 user 消息（renderedBody）
   - recent：从主 conversation 拷最近 5 条原始消息，再追加 renderedBody
   - full：先用 `compact.SummarizeForFork(ctx, mainConv)`（基于 ch09 现成的摘要管道）产出摘要文本，作为一条 system 或 user 消息插入，再追加 renderedBody
5. 选 provider：默认主 provider；`Skill.Model` 非空时调 `llm.NewProvider(skillModel)` 重新构造
6. 构造子 Agent：复用 `agent.New(provider, registry, version, eng, agent.WithRuntime(forkRuntime))`，子 runtime 是独立 NewSessionRuntime
7. 子 Agent.Run → 消费 channel 直到 Done；累计 token 用量
8. 把累计 token 写回主 runtime 的 anchor（usage += sub）
9. 取子对话的最后一条 assistant 文本作为 finalText
10. `ui.AppendAssistantMessage(finalText)`（新增 UI 方法）—— 主对话历史新增一条 assistant 消息

任一步骤出错：返回 finalText = `[skill <name> failed: <reason>]`，仍以 assistant 消息写入主对话。

### internal/skills/install.go
**职责**：InstallSkill 的核心逻辑——下载 zip、校验路径、解压到 ~/.gcode/skills/
**对外接口**：`InstallFromURL(ctx context.Context, source string, catalog *Catalog) (skillName string, err error)`

流程：
1. 通过 net/http 下载 source 到临时文件（限时 60s、限大小 50MB）
2. 用 archive/zip 打开
3. 严格校验：所有路径必须以 `<topDir>/` 起头、`<topDir>` 满足 F3 命名、内部不含 `..`、不含绝对路径、不含符号链接
4. 解压到 `~/.gcode/skills/<topDir>/`
5. 调用 `catalog.Reload(workDir)` 触发热重载
6. 返回 `<topDir>` 作为 skillName

### internal/skills/builtin/*
**职责**：内置三个 Skill 的资源文件
**结构**：

```
builtin/
├── commit/SKILL.md
├── review/SKILL.md
└── test/SKILL.md
```

每个 SKILL.md 都是完整的目录型 Skill（本期三个 builtin 不需要 tool.json，因为只用现有工具）。

内容要点（详见 task.md 中的步骤）：
- commit: mode=inline, allowed_tools=[bash, read_file, grep]
- review: mode=fork, fork_context=none, allowed_tools=[read_file, grep, glob, bash]
- test: mode=inline, allowed_tools=[bash, read_file, grep, glob]

### internal/tool/load_skill.go
**职责**：LoadSkill 工具实现
**对外接口**：实现 `tool.Tool` 接口

```go
type LoadSkillTool struct {
    catalog  *skills.Catalog
    active   *skills.ActiveSkills
    registry *tool.Registry
}

// Name/Description/Parameters/ReadOnly/IsSystem/Execute
```

`IsSystem() bool { return true }`——新加在 Tool 接口（或者通过 type assertion 探测）。`Execute` 流程：
1. 解析 args.name
2. catalog.Get(name) → 不存在返回 `unknown skill: <name>`
3. 重读 SKILL.md 获取最新 body
4. `active.Activate(name, body)`
5. 把 skill.ToolSpecs 注册进 registry（重复名静默覆盖，仅当前进程生效）
6. 返回 `Skill <name> activated. SOP pinned to env context. N specialized tools registered.`

### internal/tool/install_skill.go
**职责**：InstallSkill 工具实现
**对外接口**：实现 `tool.Tool`

```go
type InstallSkillTool struct {
    catalog *skills.Catalog
    workDir string
}
```

`ReadOnly() bool { return false }`（写盘 + 网络），`IsSystem() bool { return false }`。Execute 直接调 `skills.InstallFromURL`，返回成功消息或错误。

### internal/tool/registry.go
**修改**：
- Tool 接口新增 `IsSystem() bool` 方法（默认 false）；现有 6 个工具与 MCP 工具默认实现返回 false
- LoadSkill 工具 IsSystem 返回 true
- 新增 `Registry.RegisterSkillTool(spec skills.ToolSpec)` 方法（动态注册专属工具）
- 新增 `Registry.SystemDefinitions() []llm.ToolDefinition`（仅返回系统工具）
- 新增 `Registry.DefinitionsFiltered(allowed []string) []llm.ToolDefinition`（按白名单 + 系统工具豁免过滤）

注：本期不在主 agent loop 里用 `DefinitionsFiltered` 改主对话工具集——按 spec F27 决议，inline 模式不真过滤。但 fork 模式子 Agent 用该方法构造工具集。

### internal/prompt/modules.go
**修改**：
- `OptionalModules(instructions, memory string)` 改为 `OptionalModules(instructions, memory, skillsCatalog string)`
- 原 priority 90 槽位由 "active-skills" 重命名为 "skills-catalog"，内容由调用方传入
- 增加常量 `prioSkillsCatalog = 90`，删除 `prioActiveSkills`

### internal/prompt/prompt.go
**修改**：
- `BuildSystemPrompt(instructions, memory string)` 改为 `BuildSystemPrompt(instructions, memory, skillsCatalog string)`
- 增加 `RenderActiveSkillsBlock(entries []skills.ActiveEntry) string`，输出形如：
  ```
  ## Active Skills
  
  ### Skill: commit
  
  <body>
  
  ### Skill: review
  
  <body>
  ```
  entries 空时返回空字符串
- 增加 `RenderSkillsCatalog(items []SkillCatalogItem) string`，输出 skills-catalog 模块内容；items 空时返回空字符串

为避免 prompt 包反向依赖 skills 包，新增类型：
```go
type SkillCatalogItem struct {
    Name        string
    Description string
}
type ActiveSkillEntry struct {
    Name string
    Body string
}
```

skills.Catalog 和 skills.ActiveSkills 提供两个适配方法 `ToPromptItems()` / `ToPromptEntries()` 把内部类型转换到 prompt 包的类型上。

### internal/agent/runtime.go
**修改**：
- `SessionRuntime` 新增字段 `ActiveSkills *skills.ActiveSkills`
- `NewSessionRuntime` 初始化空 `ActiveSkills`
- `ResetForNewSession` 同时 `r.ActiveSkills.Clear()`

### internal/agent/agent.go
**修改**：
- 新增 `WithCatalog(c *skills.Catalog) Option`：注入 catalog 引用（用于第一阶段列表与 ClearActiveSkills 入口）
- 新增 `Agent.ActivateSkill(name, body)` / `ClearActiveSkills()` 方法，转发到 `runtime.ActiveSkills`
- Run 内每轮重建 sys 时：
  ```go
  sys := prompt.BuildSystemPrompt(a.instructionText, a.memoryText,
      prompt.RenderSkillsCatalog(a.catalog.ToPromptItems()))
  envText := prompt.GatherEnvironment(...).Render() + "\n\n" +
      prompt.RenderActiveSkillsBlock(a.runtime.ActiveSkills.ToPromptEntries())
  ```
  （`a.catalog` 为 nil 时跳过；进度提示放在 sub-tasks）

### internal/command/registry.go + skills.go (新建)
**职责**：把 Catalog 注册为 KindPrompt 命令；新增 /skill 命令；UI 接口扩展
**对外接口**：
- `RegisterSkillsAsCommands(reg *Registry, catalog *skills.Catalog, exec *skills.Executor)`
- 提供给 reload 路径调用的 `RemoveSkillCommands(reg *Registry)`
- 新增内置 `/skill` 命令（KindLocal）

reg.Register 时给每个 Skill 添加 Hidden=false 的 Command；命令的 Handler 闭包捕获 skill.Name 与 executor，调用 `exec.Execute(ctx, ui, name, "")`（本期不支持参数；future 在 dispatcher 加参数后填）。

注：当前 ch10 的 Slash dispatch 是零参数，Skill 显式调用本期也走零参数。`$ARGUMENTS` 替换仅在 LoadSkill + 后续 user message 的隐式场景下被替换为空——这是合理的简化（参数交互通过 Skill 后续轮次的对话进行）。

为了支持 Reload 时清理旧命令，Registry 新增 `RemoveAll(filter func(*Command) bool)` 或 `RemoveSkillCommands()` 入口。

### internal/command/ui.go
**修改**：
- UI 接口新增方法：
  - `ListCatalogSkills() []SkillSummary`（每条含 name/description/source/mode）
  - `ListActiveSkills() []string`
  - `ClearActiveSkills()`
  - `AppendAssistantMessage(text string)`（fork 路径用，把子 Agent 的 finalText 写入主对话历史）
- NopUI 提供零值实现

### internal/command/builtins.go
**修改**：
- 删除 `Name: "review"` 的注册块（让 Skill 接管）
- 修改 `handleClear`：在调 `ui.ClearAndNewSession()` 后追加 `ui.ClearActiveSkills()`
- 新增 `Name: "skill"`、KindLocal、Handler = handleSkill 的注册块

### internal/tui/*
**修改**：
- Model 持有 `*skills.Catalog`、`*skills.Executor`
- 实现新增的 UI 方法：`ListCatalogSkills` / `ListActiveSkills` / `ClearActiveSkills` / `AppendAssistantMessage`
- `tui.New` 接受新参数并接入

### cmd/gcode/main.go
**修改**：
- 启动时构造 `*skills.Catalog`、`*skills.ActiveSkills` 并注入到 SessionRuntime
- 注册 LoadSkill / InstallSkill 内置工具
- 在工具注册完成后调 `catalog.ValidateTools(registry)`；对每条 issue 打 warning 并把该 Skill 从 Catalog 中移除（保留其它）
- 调 `command.RegisterSkillsAsCommands` 完成自动注册
- 把 catalog/executor 传给 tui

## 模块交互### 启动期

```
main:
  ├─ tool.NewDefaultRegistry()
  ├─ mcp.AttachServers(registry)              // 已有
  ├─ skills.LoadCatalog(workDir)              // 三层路径扫描
  ├─ tool.Register(LoadSkillTool)             // 系统工具
  ├─ tool.Register(InstallSkillTool)
  ├─ catalog.ValidateTools(registry)          // fail-fast 检查
  │     不通过项 → 打 warning + 从 catalog 移除
  ├─ skills.NewExecutor(catalog, registry, ...)
  ├─ command.RegisterBuiltins(cmdReg)         // ch10 11 条（review 已删）
  ├─ command.RegisterSkillsAsCommands(cmdReg, catalog, executor)
  ├─ command.RegisterSkillCmd(cmdReg)         // /skill (新)
  └─ tui.New(... catalog, executor, ...)
```

### Skill 显式调用（/commit）

```
user → submit → command.Dispatch(/commit)
       → handler 调 executor.Execute(ctx, ui, "commit", "")
                 ├ inline: render → ui.InjectAndSend → agent.Run 注入主对话
                 └ fork: render → 子 Agent.Run → finalText → ui.AppendAssistantMessage
```

### Skill 意图触发（自然语言）

```
user 输入"帮我提交一下" → agent.Run loop
   └ streamOnce 拿到 LLM 调 LoadSkill({name:"commit"})
        → tool.Execute → LoadSkillTool.Execute
              ├ catalog.Get → 重读 SKILL.md
              ├ active.Activate("commit", body)
              └ 返回 tool_result
   下一轮迭代:
        sys = BuildSystemPrompt(...catalog清单不变)
        envText = ... + RenderActiveSkillsBlock(["commit" -> body])
        ↑ Agent 现在看得到完整 SOP
```

### /clear

```
/clear handler → ui.ClearAndNewSession() (ch10) → ui.ClearActiveSkills()
                                                       └ runtime.ActiveSkills.Clear()
下轮 envText 中 active-skills 块为空字符串
```

### Reload (InstallSkill 后或者未来 /skill reload)

```
InstallSkill.Execute → skills.InstallFromURL
   └ 解压完毕 → catalog.Reload(workDir)
                ├ 重新扫描三层路径
                ├ 通过 mu 锁原子替换 byName / order
                └ command 端不会立刻感知—但 dispatcher 每轮按命令名查找 reg，
                   Reload 完成后下次 /<name> 即可命中新 Skill。然而启动时已注册的
                   旧命令仍在 registry 中。为简化，提供下面策略：
```

进一步：`catalog.Reload` 返回 (added, removed []string)，InstallSkill 工具拿到结果后调 cmdReg `RemoveSkillCommands` + `RegisterSkillsAsCommands`，确保 /help 和补全菜单立即同步。

### Fork 模式

```
executor.Execute (fork) →
   ┌──────────────────── 子 Agent ────────────────────┐
   │ 新 Conversation 按 fork_context 初始化            │
   │ Agent.New(provider, registry, version, eng,       │
   │           WithRuntime(forkRuntime))               │
   │ run.Run(ctx, conv, defaultMode)                   │
   │ 累计 token, 取末尾 assistant text                  │
   └───────────────────────────────────────────────────┘
   将 finalText 作为一条 assistant 消息插入主 conv
```

注：fork 模式下子 Agent 的 registry 是用 `Registry.DefinitionsFiltered(allowed)` 构造的临时 registry（共享底层 Tool 实例），系统工具豁免列入。

## 文件组织

```
gcode/
├── cmd/gcode/main.go                # 接线：构造 catalog / executor / 注册工具与命令
├── internal/
│   ├── skills/                        # 新包
│   │   ├── types.go                   # SkillMeta / Skill / SkillSource / ToolSpec / ActiveEntry
│   │   ├── parser.go                  # parseSkillDir, parseSkillMD, parseToolJSON
│   │   ├── catalog.go                 # Catalog: LoadCatalog / Reload / Get / List / Names / ValidateTools
│   │   ├── active.go                  # ActiveSkills
│   │   ├── render.go                  # RenderBody, $ARGUMENTS 替换, allowed_tools 顶部提示
│   │   ├── executor.go                # Executor.Execute (inline / fork)
│   │   ├── install.go                 # InstallFromURL（zip 下载与 zip-slip 防护）
│   │   ├── adapter.go                 # ToPromptItems / ToPromptEntries 桥接到 prompt 包
│   │   └── builtin/                   # Go embed 资源
│   │       ├── commit/SKILL.md
│   │       ├── review/SKILL.md
│   │       └── test/SKILL.md
│   ├── tool/
│   │   ├── registry.go                # 修改：IsSystem 标记 + DefinitionsFiltered + RegisterSkillTool
│   │   ├── load_skill.go              # 新：LoadSkill 工具
│   │   ├── install_skill.go           # 新：InstallSkill 工具
│   │   └── skill_tool.go              # 新：把 ToolSpec 适配为 tool.Tool 实现（exec command）
│   ├── command/
│   │   ├── builtins.go                # 修改：删 /review、改 handleClear、加 /skill
│   │   ├── builtin_skill.go           # 新：handleSkill (KindLocal 列表)
│   │   ├── skills.go                  # 新：RegisterSkillsAsCommands / RemoveSkillCommands
│   │   └── ui.go                      # 修改：新增 4 个 UI 方法 + NopUI 兜底
│   ├── prompt/
│   │   ├── modules.go                 # 修改：active-skills → skills-catalog
│   │   ├── prompt.go                  # 修改：BuildSystemPrompt 增 catalog 参数
│   │   ├── skills_block.go            # 新：RenderActiveSkillsBlock / RenderSkillsCatalog / 类型
│   │   └── environment.go             # 不动
│   ├── agent/
│   │   ├── runtime.go                 # 修改：SessionRuntime.ActiveSkills 字段
│   │   ├── agent.go                   # 修改：WithCatalog / Run 内构造 sys 与 env 拼接
│   │   └── runtime_test.go            # 修改（如需）
│   └── tui/
│       ├── tui.go                     # 修改：持有 catalog/executor + 实现新 UI 方法
│       └── ...
└── docs/ch11/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 数据格式 | 仅 SKILL.md（frontmatter+body） | 与 README 一致；解析路径单一；不引入 yaml/md 分离的认知负担 |
| Skill 形态 | 必须是目录 | 与 tool.json/references 自然契合；将来扩展空间大 |
| 优先级覆盖 | 内置 < 用户 < 项目 | 与 npm/git 习惯一致 |
| 内置 Skill 分发 | Go embed | 与二进制一起走；新机器不依赖外部文件 |
| 内置 Skill 落地 | 启动期解压到 cache 目录后按文件系统统一处理 | tool.json + references/ 需要真实路径才能 exec 脚本 |
| 第一阶段注入位置 | system prompt 模块（priority 90） | 享受 prompt cache 稳定前缀 |
| 第二阶段注入位置 | env context（每轮重建） | 多 Skill 同激活、嵌套场景下 SOP 永远靠前；prompt cache 失效是设计意图 |
| LoadSkill 入参 | 仅 name | 与"意图识别"语义一致；参数走后续 user message 更自然 |
| LoadSkill 权限 | read-only + 系统工具 | 没有外部副作用；为支持嵌套必须豁免 allowed_tools |
| InstallSkill 权限 | 普通工具，受权限模式约束 | 写盘+网络，必须走授权 |
| fork 模式实现 | Go 端起子 Agent | 直接复用现成 Agent.Run，不依赖将来 SubAgent 章节 |
| fork_context 默认 | none | "隔离"才是 fork 本意；需要带上下文的显式声明 |
| allowed_tools 在 inline 模式 | 仅 fail-fast + SOP 提示 | 避免 inline 期间动态切换工具集的生命周期复杂度；安全靠 ch08 权限引擎兜底 |
| Skill 与已有命令冲突 | 跳过加载 + warning | 保护内置命令的可靠性；Skill 想替换内置命令需要用户主动改源码 |
| 解析失败 | 跳过单个 Skill，warning，不阻断 | 与 instructions loader 一致的容错策略 |
| 热加载 | InstallSkill 后主动 Reload；Execute 时重读 body | 用户改 SKILL.md 下次执行立即生效；新装 Skill 不需要重启 |
| Skill 列表数据流 | adapter 桥接，prompt 包不依赖 skills 包 | 避免循环依赖 |
| UI 接口扩展 | 4 个新方法 + NopUI 全量实现 | 与 ch10 风格一致 |
| 闭包循环变量 | 显式 `name := skill.Name` 拷贝再用 | Go 1.22+ 已修，仍显式拷贝为可读性 |
| Skill 自身参数 | 本期 /<name> 仅零参数；后续轮次对话补 | 与 ch10 F7 一致，不破坏 dispatcher |
````

````markdown
# Skill 技能包系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `internal/skills/types.go` | SkillMeta / Skill / SkillSource / ToolSpec / ActiveEntry |
| 新建 | `internal/skills/parser.go` | parseSkillDir, parseFrontmatter, parseToolJSON |
| 新建 | `internal/skills/parser_test.go` | 解析路径单测 |
| 新建 | `internal/skills/catalog.go` | Catalog: LoadCatalog / Reload / Get / List / Names / ValidateTools |
| 新建 | `internal/skills/catalog_test.go` | 三层覆盖单测 |
| 新建 | `internal/skills/active.go` | ActiveSkills 列表 |
| 新建 | `internal/skills/render.go` | RenderBody（$ARGUMENTS + allowed_tools 提示） |
| 新建 | `internal/skills/adapter.go` | ToPromptItems / ToPromptEntries |
| 新建 | `internal/skills/install.go` | InstallFromURL + zip-slip 防护 |
| 新建 | `internal/skills/install_test.go` | zip-slip / 正常 zip 解压单测 |
| 新建 | `internal/skills/executor.go` | Executor.Execute（inline / fork 分支） |
| 新建 | `internal/skills/builtin/commit/SKILL.md` | 内置 commit Skill |
| 新建 | `internal/skills/builtin/review/SKILL.md` | 内置 review Skill |
| 新建 | `internal/skills/builtin/test/SKILL.md` | 内置 test Skill |
| 修改 | `internal/tool/registry.go` | IsSystem 标记 + DefinitionsFiltered + RegisterSkillTool |
| 新建 | `internal/tool/skill_tool.go` | ToolSpec 适配为 tool.Tool（exec command） |
| 新建 | `internal/tool/load_skill.go` | LoadSkill 工具实现 |
| 新建 | `internal/tool/install_skill.go` | InstallSkill 工具实现 |
| 修改 | `internal/prompt/modules.go` | active-skills → skills-catalog 槽位 |
| 修改 | `internal/prompt/prompt.go` | BuildSystemPrompt 增 catalog 参数 |
| 新建 | `internal/prompt/skills_block.go` | RenderSkillsCatalog / RenderActiveSkillsBlock + 桥接类型 |
| 修改 | `internal/prompt/prompt_test.go` | 同步 BuildSystemPrompt 签名变更 |
| 修改 | `internal/command/ui.go` | UI 接口新增 4 方法 + NopUI 实现 |
| 修改 | `internal/command/builtins.go` | 删 /review、改 handleClear、加 /skill 注册 |
| 新建 | `internal/command/builtin_skill.go` | handleSkill（KindLocal 列表输出） |
| 新建 | `internal/command/skills.go` | RegisterSkillsAsCommands / RemoveSkillCommands |
| 修改 | `internal/command/registry.go` | 按命令标记筛选移除入口 |
| 修改 | `internal/agent/runtime.go` | SessionRuntime.ActiveSkills 字段 |
| 修改 | `internal/agent/agent.go` | WithCatalog + Run 拼装 sys/env + ActivateSkill/ClearActiveSkills |
| 修改 | `internal/tui/tui.go` | Model 持有 catalog/executor + 4 个 UI 方法实现 |
| 修改 | `cmd/gcode/main.go` | 启动期接线 |

## T1: skills 包数据结构**文件**：`internal/skills/types.go`
**依赖**：无
**步骤**：
1. 定义 `SkillSource int` 枚举：`SourceBuiltin / SourceUser / SourceProject`，附 `String()` 方法返回 "builtin"/"user"/"project"
2. 定义 `SkillMeta` 结构体，含 yaml tag 的 7 个字段（Name/Description/AllowedTools/Mode/ForkContext/Model）
3. 添加 `IsFork() bool` 方法（Mode == "fork"）
4. 定义 `ToolSpec` 结构体（Name/Description/InputSchema/Command/BaseDir）
5. 定义 `Skill` 结构体（Meta/PromptBody/SourceDir/Source/ToolSpecs）
6. 定义 `ActiveEntry` 结构体（Name/Body）

**验证**：`go build ./internal/skills/...` 编译通过。

## T2: SKILL.md 与 tool.json 解析**文件**：`internal/skills/parser.go`
**依赖**：T1，需要 `gopkg.in/yaml.v3`（已在 go.mod）
**步骤**：
1. `parseSkillDir(dir string, source SkillSource) (*Skill, error)`：
   - 读 `<dir>/SKILL.md`，找不到返回错误 `no SKILL.md in <dir>`
   - 调 `parseFrontmatterAndBody(data)` → (meta, body, err)
   - 校验 meta.Name 满足正则 `^[a-z][a-z0-9-]*$` 且长度 1-32
   - 校验 meta.Description 非空
   - 校验 meta.Mode 为空/"inline"/"fork"；其它值改 inline 并打 warning（暂用 fmt.Fprintln(os.Stderr)）
   - 校验 meta.ForkContext 为空/"none"/"recent"/"full"
   - 读 `<dir>/tool.json`（不存在则跳过），调 `parseToolJSON` 解析 → `[]ToolSpec`，BaseDir = absDir
   - 返回 `&Skill{Meta, PromptBody, SourceDir, Source, ToolSpecs}`
2. `parseFrontmatterAndBody(data []byte) (SkillMeta, string, error)`：
   - 校验起始是 `---\n`
   - 找下一个 `---\n`，frontmatter = 两者之间，body = 之后
   - yaml.Unmarshal frontmatter → SkillMeta
3. `parseToolJSON(data []byte) ([]ToolSpec, error)`：
   - JSON unmarshal 一个 `{"tools": [{name, description, input_schema, command}, ...]}` 结构
   - 校验每条 name 满足命名规则、command 非空

**验证**：`go build ./internal/skills/...` 编译通过。

## T3: 解析单测**文件**：`internal/skills/parser_test.go`
**依赖**：T2
**步骤**：
1. `TestParseSkillDir_Minimal`：写一个临时目录含最简 SKILL.md（name+description），expect 解析成功
2. `TestParseSkillDir_InvalidName`：name 含大写字母 expect error
3. `TestParseSkillDir_WithToolJSON`：含合法 tool.json，expect ToolSpecs 解析到位
4. `TestParseSkillDir_NoSkillMD`：缺 SKILL.md 返回 error

**验证**：`go test ./internal/skills/ -run TestParseSkillDir -v`，所有用例通过。

## T4: Catalog 三层加载与覆盖**文件**：`internal/skills/catalog.go`
**依赖**：T1, T2
**步骤**：
1. 定义 `Catalog struct { mu sync.RWMutex; byName map[string]*Skill; order []string }`
2. `NewCatalog() *Catalog` 构造空
3. `(c *Catalog) Register(s *Skill)` 加锁覆盖、维护 order 不重复（覆盖时 order 不变；新增时按 name 字典序插入或追加后排序）
4. `(c *Catalog) Get(name) (*Skill, bool)` 读锁
5. `(c *Catalog) List() []*Skill` 读锁，按 order 输出
6. `(c *Catalog) Names() []string` 读锁
7. `LoadCatalog(workDir string) *Catalog`：
   - 新 catalog
   - loadBuiltinInto(catalog) → 通过 embed.FS 加载（T5 完成 builtin 后接入；本任务先留一个 TODO 桩，跳过 builtin）
   - loadDirInto(catalog, ~/.gcode/skills, SourceUser)
   - loadDirInto(catalog, <workDir>/.gcode/skills, SourceProject)
8. `loadDirInto(c *Catalog, baseDir string, source SkillSource)`：
   - baseDir 不存在静默跳过
   - 遍历直接子目录，每个调 `parseSkillDir` 后 `c.Register`；解析失败打 warning 跳过
9. `(c *Catalog) Reload(workDir string)`：构造新 catalog，原子替换内部 byName/order
10. `ValidationIssue struct { SkillName string; ToolName string }`
11. `(c *Catalog) ValidateTools(reg *tool.Registry) []ValidationIssue`：遍历所有 skill 的 AllowedTools，逐项查 reg.Get；未找到记录并 issue。**注意**：把 `LoadSkill` 与 `InstallSkill` 视为允许引用（与系统工具豁免逻辑一致）

**验证**：`go build ./internal/skills/...` 编译通过；先不要在 LoadCatalog 中接入 builtin。

## T5: 内置三个 Skill 的资源文件与 embed**文件**：
- `internal/skills/builtin/commit/SKILL.md`
- `internal/skills/builtin/review/SKILL.md`
- `internal/skills/builtin/test/SKILL.md`
- `internal/skills/embed_builtin.go`

**依赖**：T4
**步骤**：
1. 写三个 SKILL.md，frontmatter 内容：
   - commit: name=commit, description=分析 git diff 并生成规范的 commit, allowed_tools=[bash, read_file, grep], mode=inline
   - review: name=review, description=客观审查代码变更与潜在问题, allowed_tools=[read_file, grep, glob, bash], mode=fork, fork_context=none
   - test: name=test, description=运行项目测试并分析失败原因, allowed_tools=[bash, read_file, grep, glob], mode=inline
   正文按 README 描述的 SOP 写：步骤、注意事项、$ARGUMENTS 占位符
2. 新建 `embed_builtin.go`，包含：
   ```go
   //go:embed builtin/*/SKILL.md
   var builtinFS embed.FS
   ```
3. 实现 `loadBuiltinInto(c *Catalog)`：
   - 遍历 builtinFS 下 `builtin/<name>/SKILL.md` 文件
   - 对每个把数据写到 `$XDG_CACHE_HOME/gcode/builtin-skills/<name>/SKILL.md`（或 `os.UserCacheDir() + /gcode/builtin-skills/<name>/`）
   - 解压完后调 `parseSkillDir(<cache_dir>, SourceBuiltin)` 加载
4. 在 `catalog.LoadCatalog` 中调 `loadBuiltinInto`

**验证**：
- `go build ./internal/skills/...` 编译通过
- 写个临时 main：`c := skills.LoadCatalog(os.TempDir()); fmt.Println(c.Names())` 输出 `[commit review test]` （字典序）

## T6: Catalog 单测**文件**：`internal/skills/catalog_test.go`
**依赖**：T4, T5
**步骤**：
1. `TestLoadCatalog_BuiltinOnly`：用空临时 workDir 跑 LoadCatalog，期望 Names() == [commit, review, test]
2. `TestLoadCatalog_UserOverride`：在 tmp HOME 下放 commit 目录，期望该目录的 description 覆盖 builtin（用 t.Setenv 设置 HOME）
3. `TestLoadCatalog_ProjectOverride`：在 tmp workDir/.gcode/skills 放 commit 目录，期望覆盖 user
4. `TestValidateTools_MissingTool`：定义一个 skill 用 NotExist 工具，期望返回 1 个 issue

**验证**：`go test ./internal/skills/ -v`，全部通过。

## T7: ActiveSkills 列表**文件**：`internal/skills/active.go`
**依赖**：T1
**步骤**：
1. 定义 `ActiveSkills struct { mu sync.Mutex; entries []ActiveEntry; index map[string]int }`
2. `NewActiveSkills() *ActiveSkills`
3. `(a *ActiveSkills) Activate(name, body string)`：加锁；如 name 已存在则更新 body（保持位置不变）；否则追加
4. `(a *ActiveSkills) Clear()`：加锁清空两个字段
5. `(a *ActiveSkills) Snapshot() []ActiveEntry`：加锁拷贝（slice + 元素）
6. `(a *ActiveSkills) Names() []string`

**验证**：写一个简单单测覆盖 Activate/Clear/Snapshot 路径，`go test ./internal/skills/` 通过。

## T8: Render 渲染**文件**：`internal/skills/render.go`
**依赖**：T1
**步骤**：
1. `RenderBody(s *Skill, args string) string`：
   - body := s.PromptBody
   - 若 len(s.Meta.AllowedTools) > 0：在 body 前插入"建议工具"提示行（格式见 plan.md F27），用 `\n\n---\n\n` 分隔
   - 若 strings.Contains(body, "$ARGUMENTS"): body = strings.ReplaceAll(body, "$ARGUMENTS", args)
   - 否则如 strings.TrimSpace(args) != "": body += "\n\n## User Request\n\n" + args
   - 返回 body
2. 单测：覆盖 4 种组合（有/无 placeholder × 有/无 args）

**验证**：`go test ./internal/skills/ -run TestRenderBody -v` 通过。

## T9: prompt 包适配器**文件**：`internal/skills/adapter.go`
**依赖**：T4, T7
**步骤**：
1. 在 skills 包定义 `PromptItem struct { Name, Description string }` 与 `PromptEntry struct { Name, Body string }`（避免反向依赖 prompt 包）
2. `(c *Catalog) ToPromptItems() []PromptItem`：按 order 输出
3. `(a *ActiveSkills) ToPromptEntries() []PromptEntry`：按 Snapshot 顺序输出

**验证**：`go build ./internal/skills/...` 通过。

## T10: prompt 模块槽位重命名**文件**：`internal/prompt/modules.go`
**依赖**：无
**步骤**：
1. 把 `prioActiveSkills = 90` 重命名为 `prioSkillsCatalog = 90`
2. `OptionalModules(instructions, memory string)` 改签名为 `OptionalModules(instructions, memory, skillsCatalog string)`
3. 模块名由 `active-skills` 改为 `skills-catalog`，Content 取 skillsCatalog 参数

**验证**：`go build ./internal/prompt/...` 报错只该出现在 prompt.go 上（它还用着旧签名），下一任务修复。

## T11: prompt 新增 Skill 渲染函数**文件**：`internal/prompt/skills_block.go`
**依赖**：T10
**步骤**：
1. 定义 `SkillCatalogItem struct { Name, Description string }` 与 `ActiveSkillEntry struct { Name, Body string }`
2. `RenderSkillsCatalog(items []SkillCatalogItem) string`：items 空返回 ""；否则输出：
   ```
   ## Available Skills
   
   - <name>: <description>
   ...
   
   Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
   ```
3. `RenderActiveSkillsBlock(entries []ActiveSkillEntry) string`：entries 空返回 ""；否则输出：
   ```
   ## Active Skills
   
   ### Skill: <name>
   
   <body>
   
   ### Skill: <name>
   
   <body>
   ```

**验证**：`go build ./internal/prompt/...` 通过 skills_block.go；prompt.go 仍待修。

## T12: BuildSystemPrompt 签名更新**文件**：`internal/prompt/prompt.go`
**依赖**：T10, T11
**步骤**：
1. `BuildSystemPrompt(instructions, memory string)` 改为 `BuildSystemPrompt(instructions, memory, skillsCatalog string)`
2. 内部把第三参数传给 `OptionalModules`

**验证**：`go build ./internal/prompt/...` 全包编译通过。

## T13: prompt 单测同步**文件**：`internal/prompt/prompt_test.go`
**依赖**：T12
**步骤**：
1. 所有 `BuildSystemPrompt(X, Y)` 调用替换为 `BuildSystemPrompt(X, Y, "")`（或必要场景传入非空 catalog 文本，新增 1 个用例覆盖）
2. 新增 `TestRenderSkillsCatalog_NonEmpty / _Empty` 与 `TestRenderActiveSkillsBlock_NonEmpty / _Empty`

**验证**：`go test ./internal/prompt/ -v`，全部通过。

## T14: tool.Registry 系统工具支持**文件**：`internal/tool/registry.go` + 内置 6 工具与 MCP 工具
**依赖**：无
**步骤**：
1. Tool 接口新增 `IsSystem() bool`；6 个内置工具与 MCP 适配器各加一行 `func (X) IsSystem() bool { return false }`
2. `Registry.DefinitionsFiltered(allowed []string) []llm.ToolDefinition`：按 order 遍历，name 在 allowed 集合内 OR `tool.IsSystem()` 为 true 时纳入
3. `Registry.RegisterSkillTool(t Tool)` —— 重复名静默覆盖（不维护 order 中重名）

**验证**：`go build ./...`，原 6 个工具与 mcp 适配编译通过。`go test ./internal/tool/`（如已有）通过。

## T15: ToolSpec 适配为 tool.Tool**文件**：`internal/tool/skill_tool.go`
**依赖**：T1, T14
**步骤**：
1. 定义 `SkillToolFromSpec(spec skills.ToolSpec) tool.Tool`：
   - 返回一个实现了 Tool 接口的结构体
   - Name/Description/Parameters/ReadOnly(false)/IsSystem(false)/Execute
   - Execute：把 args 序列化成 JSON 写入子进程 stdin；exec.CommandContext 起 `command[0] command[1:]...`，cwd = BaseDir；30 秒超时；读 stdout 当结果文本；exit code 非 0 视失败
2. 因 tool 包不应反向依赖 skills 包，这里把 ToolSpec 字段直接打散到工厂函数参数：`func NewSkillTool(name, desc string, schema json.RawMessage, command []string, baseDir string) tool.Tool`

**验证**：写最小单测，模拟一个 `echo "ok"` 的 shell 脚本，验证 Execute 返回 "ok"。

## T16: LoadSkill 工具**文件**：`internal/tool/load_skill.go`
**依赖**：T4, T7, T14, T15
**步骤**：
1. 定义 `type LoadSkillTool struct { catalog *skills.Catalog; active *skills.ActiveSkills; registry *tool.Registry }`
2. Name = "load_skill"，Description 写明用途
3. Parameters 返回 `{"type":"object","properties":{"name":{"type":"string","description":"Skill name to activate"}},"required":["name"]}`
4. ReadOnly() = true（只动 Agent 自己状态，无外部副作用）；IsSystem() = true
5. Execute(ctx, args)：
   - json.Unmarshal args → struct{Name string}
   - skill, ok := catalog.Get(name)；不存在返回结构化错误 `unknown skill: <name>`
   - 从磁盘 `<skill.SourceDir>/SKILL.md` 重读，更新 body；失败回退到 skill.PromptBody 并打 warning
   - active.Activate(skill.Meta.Name, freshBody)
   - 注册 skill.ToolSpecs：`registry.RegisterSkillTool(NewSkillTool(...))`
   - 返回 Result{Text: fmt.Sprintf("Skill %s activated. SOP pinned to env context. %d specialized tools registered.", name, len(skill.ToolSpecs))}

**验证**：`go build ./...` 通过。

## T17: InstallSkill 工具**文件**：`internal/tool/install_skill.go`
**依赖**：T18（一般 install_skill 工具薄壳，调 install.go）
**步骤**：
1. 定义 `type InstallSkillTool struct { catalog *skills.Catalog; workDir string }`
2. Name = "install_skill"，Description 写明用途与限制
3. Parameters：`{"type":"object","properties":{"source":{"type":"string","description":"URL of a Skill zip"}},"required":["source"]}`
4. ReadOnly() = false；IsSystem() = false（受权限模式约束）
5. Execute：调 `skills.InstallFromURL(ctx, source, catalog, workDir)`，返回成功消息 `Skill <name> installed to ~/.gcode/skills/<name>.`

**验证**：`go build ./...` 通过。本工具的功能在 T18 跑完后再做集成测试。

## T18: InstallFromURL 与 zip-slip 防护**文件**：`internal/skills/install.go`
**依赖**：T4
**步骤**：
1. `InstallFromURL(ctx context.Context, source string, catalog *Catalog, workDir string) (string, error)`：
   - http.NewRequestWithContext + Client.Timeout=60s，下载到 io.LimitReader(50MB) 的临时文件
   - archive/zip 打开
   - 计算顶层目录名 = 所有条目共同前缀的第一段；校验满足 `^[a-z][a-z0-9-]*$`
   - 遍历条目：拒绝 `..`、`/` 开头、`filepath.IsAbs`、symlinks（Mode().Type()&fs.ModeSymlink!=0）
   - 解压到 `~/.gcode/skills/<topDir>/`
   - 调 `catalog.Reload(workDir)`
   - 返回 topDir
2. 单测 `TestInstallFromURL_ZipSlip`：构造恶意 zip 含 `../../bad`，期望 error 含 "unsafe path"
3. 单测 `TestInstallFromURL_Happy`：用 httptest.NewServer 起一个返回正常 zip 的 server，期望 `catalog.Get(topDir)` 在调用后能拿到

**验证**：`go test ./internal/skills/ -run TestInstall -v` 通过。

## T19: Skill Executor (inline + fork)**文件**：`internal/skills/executor.go`
**依赖**：T7, T8, T14
**步骤**：
1. 定义 `Executor struct { catalog *Catalog; active *ActiveSkills; registry *tool.Registry; provider llm.Provider; eng *permission.Engine; version string; runtime *agent.SessionRuntime }`
2. `NewExecutor(...)` 构造
3. `Execute(ctx context.Context, ui command.UI, name, args string) error`：
   - skill, ok := catalog.Get(name)；ok 为 false → `ui.Error("skill not found: "+name)`，返回 nil
   - 重读 SKILL.md 更新 body（失败回退）
   - rendered := RenderBody(skill, args)
   - if !skill.Meta.IsFork(): `ui.InjectAndSend("/"+name, rendered)`；返回 nil
   - else (fork)：
     - 构造子 Conversation：按 ForkContext("none" / "recent" / "full")
       - none: 仅 user 消息 = rendered
       - recent: 调 ui.RecentMessages(5)（新增 UI 方法）拷贝再追加 user 消息
       - full: 暂用 recent 行为 + warning（fork_context=full 留个 TODO 后续 compact 摘要管道接入）。或本期实现简单版：复制 ui.AllMessages() 用 ch09 现成的 compactor 压缩（如果改动太大，按 recent 行为兜底，并 stderr warning 提示用户）。**本期决议**：full 与 recent 等价处理，并打 warning，留待 ch12+ 真正接入
     - 选 provider：默认 e.provider；skill.Meta.Model 非空时 `llm.NewProvider(model)` 重新构造（main 已有相同代码可复用）
     - 子 registry 通过 e.registry.DefinitionsFiltered(skill.Meta.AllowedTools) → 但 Run 内部用的还是 e.registry；我们把过滤前置：用 `agent.WithRegistryFilter(allowed []string)` 选项（新增）让子 Agent 在选 defs 时调 Filtered
     - **简化方案**：本期 fork Agent 直接 `agent.New(prov, e.registry, e.version, e.eng, WithRuntime(forkRuntime))`，不做工具过滤（与 inline 模式一致，靠 SOP 提示约束）。这与 spec F28 中"按 allowed_tools 过滤工具集"相违；选简单实现并在 plan/spec 中记录此简化项
     - **回到决议**：本期 fork Agent 用 e.registry.DefinitionsFiltered(...) 的封装版（通过 agent.WithFilteredRegistry 选项），保持 fork 模式真过滤的 spec 承诺
     - 起子 Conversation：`forkConv := conversation.New()`；填入构造好的初始消息
     - forkAgent := agent.New(provider, e.registry, e.version, e.eng, agent.WithRuntime(forkRuntime), agent.WithFilteredRegistry(skill.Meta.AllowedTools))
     - 起一条 `forkAgent.Run(ctx, forkConv, permission.ModeDefault)`，遍历 channel；累积 usage、提取最终 assistant text；最大 25 轮兜底
     - usage 累加到主 runtime
     - finalText := 末尾 assistant 文本；若失败：`[skill %s failed: %s]`
     - `ui.AppendAssistantMessage(finalText)`
4. 新增 `agent.WithFilteredRegistry(allowed []string)` 选项；在 Run 的 defs 选取处，若 allowed 非空，调 a.registry.DefinitionsFiltered(allowed) 代替 a.registry.Definitions()

**验证**：`go build ./...` 通过；后续端到端 tmux 跑通 /review。

## T20: command UI 接口扩展**文件**：`internal/command/ui.go`
**依赖**：无（在 T19 前可独立完成）
**步骤**：
1. UI 接口新增 4 个方法：
   ```go
   ListCatalogSkills() []SkillSummary
   ListActiveSkills() []string
   ClearActiveSkills()
   AppendAssistantMessage(text string)
   RecentMessages(n int) []llm.Message  // fork ForkContext=recent 用
   AllMessages() []llm.Message          // fork ForkContext=full 用
   ```
2. 定义 `SkillSummary struct { Name, Description, Source, Mode string }`（放在 command 包，避免 skills 依赖 command）
3. NopUI 提供零值实现：ListCatalogSkills→nil；ListActiveSkills→nil；ClearActiveSkills→no-op；AppendAssistantMessage→no-op；RecentMessages→nil；AllMessages→nil

**验证**：`go build ./internal/command/...` 通过。

## T21: command/builtins.go 改动**文件**：`internal/command/builtins.go`
**依赖**：T20
**步骤**：
1. 删除 `Name: "review"` 的整段 reg.Register 块（与对应的 handleReview 函数文件——如有，标记 TODO 或一并清理）
2. 修改 `handleClear`：在 `ui.ClearAndNewSession()` 之后追加一行 `ui.ClearActiveSkills()`
3. 新增 reg.Register 块：
   ```
   Name: "skill", Description: "列出已加载的 Skill", Kind: KindLocal, Handler: handleSkill
   ```

**验证**：`go build ./internal/command/...` 通过；如果有 review 单测，要么更新要么删除。

## T22: handleSkill 实现**文件**：`internal/command/builtin_skill.go`
**依赖**：T20
**步骤**：
1. `func handleSkill(ctx context.Context, ui UI) error`：
   - skills := ui.ListCatalogSkills()
   - 空时输出 `No skills loaded.`
   - 否则：
     - 先 `ui.Println(fmt.Sprintf("Available skills (%d):", len(skills)))`
     - 再按 name 字典序逐条 `ui.Println(fmt.Sprintf("  /%-20s %s", name, description))`（每条独立 Println 避免 noticeBlock 多行渲染产生空白）
     - 末尾 `ui.Println("Type /<skill-name> to invoke a skill.")`
   - 不展示 source / mode 元信息——本期保持精简，开发者需要时直接读 SKILL.md

**验证**：`go test ./internal/command/...` （如果新增了相应单测）。

## T23: RegisterSkillsAsCommands**文件**：`internal/command/skills.go`
**依赖**：T20, T22
**步骤**：
1. 定义命令的 Meta 标记机制：在 `Command` 结构体新增字段 `IsSkill bool`（也可单独维护一个 set，但加字段最简）。修改 ch10 `command.go` 中 Command 结构体增加这个字段
2. `RegisterSkillsAsCommands(reg *Registry, items []SkillSummary, executor SkillRunner)`：
   - SkillRunner 接口：`Execute(ctx context.Context, ui UI, name, args string) error`
   - 遍历 items，每个 register 一个 `&Command{Name: item.Name, Description: item.Description + " [skill]", Kind: KindPrompt, IsSkill: true, Handler: func(ctx, ui) error { name := item.Name; return executor.Execute(ctx, ui, name, "") }}`
3. `RemoveSkillCommands(reg *Registry)`：遍历 reg 内部 map，删除 IsSkill=true 的条目

注：Registry 内部存储要支持 Range/Delete 操作；可能需要扩展 ch10 的 registry.go（T24）。

**验证**：`go build ./internal/command/...` 通过。

## T24: command.Registry 删除 API**文件**：`internal/command/registry.go`
**依赖**：T23
**步骤**：
1. 检查 ch10 现有 Registry 是否暴露足够 API；如未提供按条件删除，新增：
   - `func (r *Registry) RemoveIf(pred func(*Command) bool)`：按谓词删除（同时清 byName + byAlias + List 序）
2. 在 `RemoveSkillCommands` 中调 `reg.RemoveIf(func(c *Command) bool { return c.IsSkill })`

**验证**：`go test ./internal/command/...` 通过。

## T25: SessionRuntime ActiveSkills 字段**文件**：`internal/agent/runtime.go`
**依赖**：T7
**步骤**：
1. SessionRuntime 增加字段 `ActiveSkills *skills.ActiveSkills`
2. NewSessionRuntime 初始化 `ActiveSkills: skills.NewActiveSkills()`
3. ResetForNewSession 增加一行 `if r.ActiveSkills != nil { r.ActiveSkills.Clear() }`
4. 由于 agent 包反向引入 skills 包会有依赖循环（skills.Executor 依赖 agent.SessionRuntime）；解决方法：把 ActiveSkills 类型放到 agent 包下；或定义在 skills 包，agent 包 import 它（agent 已可以 import skills 包，没有循环——只要 skills 包不 import agent 包）。为简单起见，Executor 需要的 runtime 字段单独通过函数参数传递，不直接 import agent.SessionRuntime；让 skills.Executor 持有 `*skills.ActiveSkills` 而非 *SessionRuntime

**重新设计**：
- skills 包不 import agent
- agent.SessionRuntime 持有 `*skills.ActiveSkills` 字段
- skills.Executor 通过 `*skills.ActiveSkills` 操作激活态（不直接持有 SessionRuntime）

**验证**：`go build ./internal/agent/...` 编译通过。

## T26: Agent 拼装 sys / env 改动**文件**：`internal/agent/agent.go`
**依赖**：T9, T12, T25
**步骤**：
1. 新增 `WithCatalog(c *skills.Catalog) Option`：设置 a.catalog
2. 新增 `WithFilteredRegistry(allowed []string) Option`：设置 a.allowedTools
3. Agent 增加字段：`catalog *skills.Catalog`、`allowedTools []string`
4. 新增方法 `ActivateSkill(name, body string)`，调 `a.runtime.ActiveSkills.Activate(...)`
5. 新增方法 `ClearActiveSkills()`
6. Run 内每轮重建：
   ```go
   var catalogText string
   if a.catalog != nil {
       items := toPromptItems(a.catalog.ToPromptItems())
       catalogText = prompt.RenderSkillsCatalog(items)
   }
   sys := prompt.BuildSystemPrompt(a.instructionText, a.memoryText, catalogText)
   
   envBase := prompt.GatherEnvironment(...).Render()
   var envSkills string
   if a.runtime != nil && a.runtime.ActiveSkills != nil {
       envSkills = prompt.RenderActiveSkillsBlock(toPromptEntries(a.runtime.ActiveSkills.ToPromptEntries()))
   }
   envText := envBase
   if envSkills != "" { envText += "\n\n" + envSkills }
   ```
7. defs 选择：
   ```go
   defs := a.registry.Definitions()
   if mode == permission.ModePlan { defs = a.registry.ReadOnlyDefinitions() }
   if len(a.allowedTools) > 0 { defs = a.registry.DefinitionsFiltered(a.allowedTools) }
   ```

**验证**：`go build ./internal/agent/...` 通过；既有单测通过（`go test ./internal/agent/`）。

## T27: TUI Model 与 UI 实现**文件**：`internal/tui/tui.go` + 相关
**依赖**：T20, T25
**步骤**：
1. Model 持有 `catalog *skills.Catalog`、`executor *skills.Executor`
2. tui.New 接受 catalog/executor 参数
3. 实现 UI 接口的 5 个新方法：
   - `ListCatalogSkills()`：从 catalog 转换
   - `ListActiveSkills()`：从 runtime.ActiveSkills.Names()
   - `ClearActiveSkills()`：runtime.ActiveSkills.Clear()
   - `AppendAssistantMessage(text)`：追加到当前 conversation 与会话存档
   - `RecentMessages(n) / AllMessages()`：从当前 conversation 取
4. 注意：UI.InjectAndSend 已有，不重写

**验证**：`go build ./internal/tui/...` 通过；既有 tui 单测通过。

## T28: cmd/gcode/main.go 接线**文件**：`cmd/gcode/main.go`
**依赖**：T1-T27
**步骤**：
1. import skills 包
2. 构造 `catalog := skills.LoadCatalog(workDir)`
3. 构造 ActiveSkills 后 attach 到 SessionRuntime
4. 注册 LoadSkillTool / InstallSkillTool 到 tool.Registry
5. 调 `issues := catalog.ValidateTools(toolReg)`；遍历 issues 打 stderr 并把不合格 skill 从 catalog 移除
6. 构造 `executor := skills.NewExecutor(catalog, activeSkills, toolReg, provider, eng, version, ...)`
7. 调 `command.RegisterBuiltins(cmdReg)`（已有，删 /review 后内置 11 条）
8. 调 `command.RegisterSkillsAsCommands(cmdReg, catalog 转换的 summary, executor)`
9. tui.New 传 catalog/executor
10. Agent 构造时附 `agent.WithCatalog(catalog)`

**验证**：`go build ./...` 全包编译通过；`go vet ./...` 无新增警告。

## T29: 启动冒烟**文件**：无
**依赖**：T28
**步骤**：
1. 在 tmux 内：`./gcode`，期望启动 banner 正常、状态栏正常
2. 键入 `/help`，期望输出含 `/skill` 行、不含独立 `/review` 行、含 `/commit [skill]` `/review [skill]` `/test [skill]` 三行
3. 键入 `/skill`，期望输出三行（commit/review/test，source=builtin）
4. ctrl+c 退出

**验证**：观察输出符合上述期望；任何 panic 或缺失都修正后重测。

## T30: 端到端验证场景

按 checklist.md 中端到端场景章节，在 tmux 里实跑全套流程。

## 执行顺序

```
T1 → T2 → T3
  → T4 (依赖 T1,T2) → T5 (依赖 T4) → T6 (依赖 T4,T5)
  → T7 (依赖 T1) → T8 (依赖 T1) → T9 (依赖 T4,T7)

T10 → T11 (依赖 T10) → T12 (依赖 T10,T11) → T13 (依赖 T12)

T14 → T15 (依赖 T1,T14) → T16 (依赖 T4,T7,T14,T15) → T17 (依赖 T18)
T18 (依赖 T4)

T20 → T21 (依赖 T20) → T22 (依赖 T20) → T23 (依赖 T20,T22) → T24 (依赖 T23)

T25 (依赖 T7) → T26 (依赖 T9,T12,T25) → T27 (依赖 T20,T25)

T19 (依赖 T7,T8,T14) → T28 (依赖 T1-T27)

T29 (依赖 T28) → T30
```

可并行：T1-T9 内部链；T10-T13 链；T14-T18 链；T20-T24 链 —— 这四条链彼此独立直到 T25 起开始合流。但本期由单一会话顺序执行，避免合并冲突。
````

````markdown
# Skill 技能包系统 Checklist

> 每一项通过运行代码或观察行为来验证。最后一节"端到端场景（tmux 实跑）"必须在 tmux 内实际跑过。

## 实现完整性

- [ ] `internal/skills` 包编译通过（验证：`go build ./internal/skills/...`）
- [ ] `internal/tool/load_skill.go` 与 `internal/tool/install_skill.go` 编译通过（验证：`go build ./internal/tool/...`）
- [ ] `internal/prompt` 改造后编译通过且单测通过（验证：`go test ./internal/prompt/...`）
- [ ] `internal/command` 改造后编译通过且单测通过（验证：`go test ./internal/command/...`）
- [ ] `internal/agent` 改造后编译通过且单测通过（验证：`go test ./internal/agent/...`）
- [ ] 全项目编译通过（验证：`go build ./...`）
- [ ] `go vet ./...` 无新增警告
- [ ] 内置三个 Skill（commit / review / test）的 SKILL.md 通过 frontmatter 与 body 双重校验（验证：启动后 `/skill` 输出三行）

## Skill 定义与解析

- [ ] 一个最简的合法 SKILL.md（仅 name + description）能被 parser 解析成功（验证：parser_test.go 中 `TestParseSkillDir_Minimal` 通过）
- [ ] 非法 name（大写、空格、超长）被 parser 拒绝（验证：parser_test.go 中 `TestParseSkillDir_InvalidName` 通过）
- [ ] tool.json 合法时解析为 ToolSpec 列表（验证：parser_test.go 中 `TestParseSkillDir_WithToolJSON` 通过）
- [ ] 缺 SKILL.md 时返回 error（验证：parser_test.go 中 `TestParseSkillDir_NoSkillMD` 通过）

## Catalog 加载

- [ ] 空 workDir + 空 HOME 启动时 Catalog 仅含三个内置 Skill（验证：catalog_test.go `TestLoadCatalog_BuiltinOnly` 通过）
- [ ] 用户目录下同名 Skill 覆盖内置（验证：`TestLoadCatalog_UserOverride` 通过）
- [ ] 项目目录下同名 Skill 覆盖用户（验证：`TestLoadCatalog_ProjectOverride` 通过）
- [ ] 单个 Skill 解析失败（损坏 SKILL.md）只跳过它本身，其它 Skill 仍能加载（验证：写一个临时 user 目录含损坏 + 合法两个 Skill，启动后只看到合法那一个）
- [ ] Skill 名字与 ch10 已有命令冲突时跳过加载（验证：临时建一个 name=help 的 Skill 放 user 目录，启动 stderr 打 warning 且 /help 仍为内置命令）

## fail-fast 依赖检查

- [ ] Skill 的 allowed_tools 引用不存在的工具时，启动 stderr 输出对应错误并把该 Skill 从 Catalog 中剔除（验证：建一个含 `allowed_tools: [NotExist]` 的 Skill，启动 stderr 含 `allowed_tool "NotExist" not registered`，`/skill` 中不出现该 Skill）
- [ ] load_skill / install_skill 在 fail-fast 检查中被视为允许引用（验证：建一个 `allowed_tools: [load_skill]` 的 Skill，启动正常加载，不报错）

## Slash Command 自动注册

- [ ] 启动后 `/help` 包含 `/commit [skill]`、`/review [skill]`、`/test [skill]` 三行且不再有独立 `/review`（验证：tmux 启动后键入 /help）
- [ ] `/help` 包含 `/skill` 一行（验证：同上）
- [ ] 用 Tab 补全输入 `/comm`，菜单展示 `/commit [skill]` 候选（验证：tmux 实跑）

## 两阶段加载

- [ ] System prompt 中含 `## Available Skills` 区块，列出全部 Catalog Skill 的 `- name: description`（验证：在 agent.Run 前打日志或加一个 dump-prompt 测试用例）
- [ ] 未激活任何 Skill 时 env context 不含 `## Active Skills` 区块（验证：单测 `RenderActiveSkillsBlock([]) == ""`）
- [ ] 激活一个 Skill 后下一轮 env context 含 `## Active Skills` 区块包含该 Skill 的 body（验证：用单测覆盖 RenderActiveSkillsBlock；端到端见 tmux 场景）

## LoadSkill 工具

- [ ] 调用 LoadSkill({name:"commit"}) 后 active.Names() 包含 "commit"（验证：单测）
- [ ] 调用 LoadSkill 不存在的 name 时返回 `unknown skill: <name>`，对话不中断（验证：tmux 实跑触发）
- [ ] LoadSkill 调用时即便 allowed_tools 是空白名单也可见（验证：单测 `Registry.DefinitionsFiltered([], 系统工具)` 输出包含 load_skill）
- [ ] LoadSkill 在 Plan Mode 下可调用，不被权限拦截（验证：tmux 实跑 `/plan` 后让 LLM 触发 LoadSkill）

## /clear

- [ ] /clear 之后 active.Names() 为空（验证：tmux 实跑：先触发 LoadSkill 激活某 Skill，再 /clear，下一轮观察 env context 无 Active Skills 块）
- [ ] /clear 之后新会话可在 /resume 列表中看到旧会话条目（验证：与 ch10 N9 一致，回归现有行为）

## Skill 执行器

- [ ] inline Skill 执行后主对话历史新增一条 user 消息（验证：tmux 触发 /commit 后 `/session` 显示路径，查看会话 JSONL）
- [ ] inline Skill 的 SOP 顶部含 "This skill is designed to use only these tools: ..." 提示（验证：单测覆盖 RenderBody）
- [ ] fork Skill 跑完后主对话新增一条 assistant 消息（验证：tmux 触发 /review 后会话 JSONL 末尾是 assistant 角色消息）
- [ ] fork Skill 失败（如子 Agent 报错或超时）时返回的 assistant 消息为 `[skill <name> failed: ...]` 文本（验证：mock provider 出错的执行器单测）

## tool.json 专属工具

- [ ] 一个含 tool.json 的 Skill 被 LoadSkill 激活后，主工具注册中心新增对应的工具名（验证：tmux 实跑：放一个测试 Skill 含 echo 的 tool.json，激活后让 LLM 调那个工具，观察输出）
- [ ] 专属工具 exec 超时 30 秒（验证：tool/skill_tool_test.go：脚本 sleep 100 时返回超时错误）
- [ ] 专属工具 exit code 非 0 视为失败，stderr 内容并入 Result 文本（验证：单测）

## InstallSkill

- [ ] 合法 zip 安装后 `~/.gcode/skills/<topDir>/` 出现 SKILL.md（验证：单测 + tmux 实跑）
- [ ] 合法 zip 安装后 `/skill` 立即列出新 Skill 且 `/<name>` 可调用（验证：端到端）
- [ ] zip-slip（含 `..` 路径）被拒绝，~/.gcode/skills/ 无副作用（验证：单测 `TestInstallFromURL_ZipSlip`）
- [ ] zip 内顶层目录命名违规时拒绝（验证：单测）
- [ ] InstallSkill 工具在 Plan Mode 下被权限引擎拦截，需要切回默认模式才能装（验证：tmux 实跑 /plan → 自然语言让 Agent 装 Skill → 看到权限被拦截）

## /skill 命令

- [ ] `/skill` 首行输出 `Available skills (N):`，随后每条一行 `  /<name>  <description>`（按字典序、固定列宽对齐），末行输出 `Type /<skill-name> to invoke a skill.`（验证：tmux 实跑）
- [ ] Catalog 为空时 `/skill` 输出 `No skills loaded.`（验证：清空内置 Skill 资源后启动）

## 编译与测试

- [ ] `go build ./...` 通过
- [ ] `go test ./...` 通过（含新增的 skills/parser/catalog/install/render/active/executor 单测）
- [ ] `go vet ./...` 无新增警告
- [ ] gofmt/goimports 格式正确

## 端到端场景（tmux 实跑）

> 在 tmux 内启动 gcode，按下面流程一步步操作；每步附"观察"项。

**前置**：
- 用 `tmux new -s mew-ch11 -x 200 -y 50` 起一个固定大小的 tmux session
- `cd /Users/codemelo/gcode && go build -o gcode ./cmd/gcode && ./gcode`

**步骤**：

1. **启动与就绪**
   - 操作：进程启动
   - 观察：banner 正常显示；状态栏底部含 "Type a message and press Enter..."；进程不 panic；stderr 无 "skipped" 类错误（如果用户/项目目录干净）

2. **`/help`**
   - 操作：键入 `/help` 回车
   - 观察：输出含 11 条 ch10 命令（已无独立 `/review`）+ `/skill` + `/commit [skill]` + `/review [skill]` + `/test [skill]`，共 15 行

3. **`/skill`**
   - 操作：键入 `/skill` 回车
   - 观察：首行 `Available skills (3):`，随后三行 `  /commit ...` / `  /review ...` / `  /test ...`，末行 `Type /<skill-name> to invoke a skill.`

4. **显式调用 inline Skill `/commit`**
   - 操作：键入 `/commit` 回车
   - 观察：状态栏立即进入流式；AI 开始按 commit SOP 走（应该会调 git status / diff）；本步骤是真实操作，按 q/esc 可中断；目的是验证 inline 路径联通

5. **显式调用 fork Skill `/review`**
   - 操作：在主对话先随便说一句 "I just edited some files."（让主对话有上下文），然后键入 `/review`
   - 观察：状态栏进入流式；AI 输出审查报告；最后主对话新增一条 assistant 消息（含审查结果）；ForkContext=none 意味着子 Agent 看不到 "I just edited..." 那条 user 消息

6. **意图触发 LoadSkill**
   - 操作：键入自然语言 "我想做后端面试准备"（或类似能匹配 backend-interview-like description 的 Skill；如果当前 Catalog 只有 commit/review/test，需要先放一个 user-level Skill，name=backend-interview）
   - 观察：LLM 调用 LoadSkill 工具，工具结果为 "Skill backend-interview activated..."；下一轮起 env context 中出现该 Skill 的 SOP body

7. **`/clear` 清空激活**
   - 操作：键入 `/clear` 回车
   - 观察：对话区清空、session 新建；接着说一句任意话题，env context 中不再含上一轮激活的 SOP（可通过让 Agent 复述"现在你激活了什么 Skill"间接验证，或开启 debug 日志）

8. **InstallSkill 安装第三方 Skill**
   - 操作：用 `python3 -m http.server` 在本地 8080 端口托管一个写好的 `test-skill.zip`（含 `myskill/SKILL.md`），切到 gcode 输入 "把这个 skill 装下：http://localhost:8080/test-skill.zip"
   - 观察：Agent 调 install_skill 工具；安装成功后 `/skill` 列表立即出现 myskill；`/myskill` 可调用

9. **/clear → 新会话不残留**
   - 操作：先激活 myskill，再 /clear，再 /skill
   - 观察：/skill 仍能看到 myskill（Catalog 与 Active 列表是两个概念，Catalog 不清）；env context 已无 Active Skills 块

10. **退出**
    - 操作：`/exit` 回车
    - 观察：进程优雅退出，无错误日志

## 验收报告模板

```
## 验收报告

### 通过
- [x] 实现完整性 — 全包编译通过：go build ./... 输出 ...
- [x] /help 列表正确：含 /skill, /commit [skill] ...
- [x] /skill 输出三行内置 Skill ...

### 未通过
- [ ] 第 X 项 — 预期：...，实际：...，修复方案：...

### 端到端
- [x] 启动与就绪 — 结果：banner 正常
- [x] /help — 结果：15 行命令
- [x] /skill — 结果：commit/review/test 三行
- ...（按上面 10 步逐条列出）
```
````

### Python

````markdown
# Skill 技能包系统 Spec## 背景

ch10 给 GCode 装上了 Slash Command 注册中心和 12 条内置命令，其中 `/review` 是 KindPrompt 类型——把硬编码在源码里的代码审查 prompt 注入对话并触发 LLM。这种"写死在源码里"的 prompt 暴露出几个问题：

- 调整 prompt 必须重新安装包/重启，用户没办法在不动源码的前提下定制
- 只有开发者能新增 prompt 类命令，普通用户无法贡献
- prompt 命令拿到的工具集与普通对话完全一致，没法在执行 SOP 时收窄注意力或限制权限
- prompt 是孤零零的字符串，无法捎带专属工具、参考资料、辅助脚本

与此同时,GCode 接入 MCP 之后工具数量从 6 个膨胀到二十多个,模型选错工具的概率随之上升,需要一种机制把"完成某类任务时只看哪些工具"的范围收窄。

Skill 技能包系统在 ch10 命令体系之上解决这两个问题：把可复用的 AI 操作搬出源码、放进可编辑的 Markdown 文件；通过两阶段加载和工具白名单把每次任务的注意力收窄到最小工具子集。

## 目标- **G1**：让可复用的 AI 操作变成独立的 Markdown 文件（每个 Skill 一个目录），增/删/改一个 Skill 不需要重装 gcode 包
- **G2**：自动把已加载的 Skill 注册成 `/<name>` 形式的 Slash Command，沿用 ch10 的 KindPrompt 分支
- **G3**：实现两阶段加载——启动时只把 Skill 的 `name + description` 注入系统提示；Agent 通过 LoadSkill 工具按需把完整 SOP 钉到环境上下文，从而让 Agent 既能被显式命令调用，也能通过自然语言意图自动触发
- **G4**：实现两种执行模式：`inline`（默认，注入主对话）与 `fork`（在 Python 端起子 Agent，跑完返回 final_text 作为 assistant 消息回流主对话），覆盖"需要继承上下文"和"需要客观隔离"两类任务
- **G5**：通过 `allowed_tools` 工具白名单做 fail-fast 依赖检查与 SOP 顶部"建议工具"提示，提高模型工具选择准确率
- **G6**：支持目录型 Skill：`SKILL.md` + 可选 `tool.json`（声明专属工具，调用时通过 `asyncio.create_subprocess_exec` 起 `references/` 下的可执行脚本）+ `references/`，整套作为自包含能力包
- **G7**：内置 `commit`、`review`、`test` 三个 Skill 通过 `importlib.resources` 随包分发；同时提供 `InstallSkill` 内置工具从 URL/zip 拉取第三方 Skill 到 `~/.gcode/skills/`
- **G8**：`/clear` 时清空已激活 Skill 列表，保证新会话从干净状态开始

## 功能需求### Skill 定义与解析- **F1**：每个 Skill 是一个目录。目录内必须含一个 `SKILL.md` 文件；其它附属物（`tool.json`、`references/` 子目录）均为可选
- **F2**：`SKILL.md` 由 YAML frontmatter（被两行 `---` 包围）+ Markdown 正文构成。Frontmatter 必填字段为 `name`、`description`；可选字段为 `allowed_tools`、`mode`、`fork_context`、`model`
- **F3**：`name` 必须满足正则 `^[a-z][a-z0-9-]*$`，长度 1-32；`name` 同时作为 Slash Command 命令名
- **F4**：`description` 为一句话描述（建议 ≤120 字符），用于 system prompt 第一阶段注入与 `/help`、`/skill` 输出
- **F5**：`allowed_tools` 为字符串数组；缺省视为空（不限制）
- **F6**：`mode` 取值为 `inline` 或 `fork`；缺省视为 `inline`，未知值按 `inline` 处理并 warning
- **F7**：`fork_context` 取值为 `none` / `recent` / `full`；缺省视为 `none`；仅在 `mode: fork` 时生效，inline 模式下忽略
- **F8**：`model` 为可选字符串，覆盖该 Skill 执行时使用的 LLM 模型；缺省沿用主对话当前模型
- **F9**：Markdown 正文中的 `$ARGUMENTS` 占位符在执行期替换为用户传入的参数文本；如未包含该占位符且参数非空，则在正文末尾以 `\n\n## User Request\n\n<args>` 形式追加；参数为空时按空字符串处理
- **F10**：目录可包含 `tool.json` 文件，描述该 Skill 专属工具数组。每个工具元素包含 `name`（与 frontmatter `allowed_tools` 一致的命名规则）、`description`、`input_schema`（标准 function calling JSON Schema）、`command`（数组：argv 形式，首元素为相对 `references/` 的可执行文件路径或绝对路径）
- **F11**：单个 Skill 解析失败时跳过该 Skill 并打 warning，不阻断其它 Skill 加载

### Skill 加载器（Catalog）- **F12**：启动期按以下顺序扫描，每个位置下的"子目录"视为一个 Skill 候选：
  1. 内置 Skill（通过 `importlib.resources` 从 `gcode.skills.builtin` 包资源读取 `<name>/SKILL.md`）
  2. 用户级：`~/.gcode/skills/<name>/`
  3. 项目级：`<project_root>/.gcode/skills/<name>/`
- **F13**：同名覆盖按上述顺序依次进行——后扫描的同名 Skill 替换前者。最终优先级为：项目级 > 用户级 > 内置
- **F14**：扫描目录不存在时静默跳过；无 `SKILL.md` 的子目录跳过且打 warning
- **F15**：加载阶段对所有 Skill 的 `allowed_tools` 做 fail-fast 依赖检查——引用的工具名必须存在于主工具注册中心（含 MCP 注入的工具，及 Skill 自己 `tool.json` 注册进来的专属工具）；任一未找到则在启动 banner 后立即打印 error 并跳过该 Skill 加载
- **F16**：Skill 的 `name` 与 ch10 已有内置 Slash Command 命令名（含别名）冲突时，跳过加载该 Skill 并打 warning（理由：内置命令保护）
- **F17**：Catalog 提供 `reload(work_dir)` 方法用于重新扫描三层路径，重新注册所有 Skill 命令；现有命令注册中心提供 `remove_skill_commands()` 入口让 reload 清掉旧的 skill 类命令再重新注册

### Slash Command 自动注册- **F18**：每个加载成功的 Skill 在 ch10 命令注册中心注册一条 `KindPrompt` 命令：
  - 命令名 = Skill 的 `name`
  - 描述 = Skill 的 `description` 末尾追加 `[skill]` 标记
  - 别名为空
  - hidden = False
- **F19**：用户输入 `/<name>` 等价于显式调用该 Skill（不带参数）；命令 handler 负责调用 Skill 执行器并按执行模式注入对话或起子 Agent
- **F20**：Skill 命令支持 ch10 的自动补全菜单，与内置命令共享同一前缀匹配逻辑

### 两阶段加载与 LoadSkill- **F21**：Prompt 模块新增一段 `skills-catalog`（priority 介于现有 long-term-memory 与 environment 之间），内容为：
  ```
  ## Available Skills

  - <name>: <description>
  - <name>: <description>
  ...

  Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
  ```
  Catalog 为空时该模块为空字符串，被 prompt assembler 跳过
- **F22**：环境上下文新增一段 `active-skills` 区块，按激活顺序拼接每个已激活 Skill 的 `SKILL.md` 正文（前置一行 `### Skill: <name>` 标题），每轮 Agent loop 重建 env context 时重新装配
- **F23**：注册一个新的内置工具 `LoadSkill`：
  - 输入参数：`{"name": "string"}`
  - 行为：从 Catalog 取 Skill；从磁盘重新读取 `SKILL.md` 拿到最新 body；调用 Agent 提供的 `activate_skill(name, body)` 把 Skill 钉到 Active 列表；若该 Skill 有 `tool.json`，把其中的专属工具登记进主工具注册中心（重复登记的工具名静默覆盖）
  - 返回：`Skill <name> activated. SOP pinned to env context. <N> specialized tools registered.`
  - 标记为 read-only（不被权限系统拦截），并在工具过滤逻辑中标记为系统工具（永远可见，不受 allowed_tools 约束）
- **F24**：Agent 侧新增 `ActiveSkills` 列表（基于 SessionRuntime），提供 `activate_skill(name, body)`、`clear_active_skills()`、`list_active()` 方法
- **F25**：`/clear` 命令在新建会话前调用 `Agent.clear_active_skills()`，确保下一会话的 env context 不再含上一对话激活的 SOP

### Skill 执行器- **F26**：Skill 执行器入口 `execute(ctx, name, args)`（async 方法）：从 Catalog 取定义；从磁盘重读最新 `SKILL.md`（重读失败回退缓存版本并打 warning）；按 `mode` 走两条分支
- **F27**：`inline` 分支：完成 `$ARGUMENTS` 替换；在正文顶部前插一段"建议工具"提示行（当 `allowed_tools` 非空时）；通过 `UI.inject_and_send` 把最终文本作为 user 消息注入主对话并触发回合
- **F28**：`fork` 分支：完成 `$ARGUMENTS` 替换；按 `fork_context` 构造子 Agent 的初始 Conversation（`none`：仅一条 user 消息为 Skill 文本；`recent`：复制主对话末尾最近 5 条消息再追加 Skill 文本；`full`：先用主对话历史调一次 LLM 摘要，再把摘要 + Skill 文本作为初始 user 消息）；按 Skill 的 `model`（若指定）切 provider；按 `allowed_tools` 过滤工具集（LoadSkill 系统工具豁免）；新起子 Agent 跑一轮 `run()` 拿到 final_text；把 final_text 作为一条 assistant 消息插入主对话历史
- **F29**：fork 分支跑完后主对话沿用主 Agent 继续，不影响主对话的运行时模式/Conversation 长度估算外的其它状态

### InstallSkill 内置工具- **F30**：注册内置工具 `InstallSkill`，输入参数：`{"source": "string"}`。`source` 支持两种形式：
  - HTTP(S) URL 指向单个 `.zip` 文件（按 zip 解压）
  - HTTP(S) URL 指向"目录索引"（页面包含可下载文件列表，本期仅识别 .zip）
- **F31**：InstallSkill 解压目标固定为 `~/.gcode/skills/`。zip 内顶层目录名即为 Skill 名，需满足 F3 命名规范；不满足或 zip 结构非法则报错
- **F32**：InstallSkill 安装成功后调用 `Catalog.reload`，自动让新 Skill 的 `/<name>` 命令与 system prompt 第一阶段列表立即可见
- **F33**：InstallSkill 不是系统工具，受权限模式约束（具有外部副作用——写磁盘/网络请求），需要走 ch08 权限系统的用户授权

### /skill 命令- **F34**：注册新的内置 Slash Command `/skill`，KindLocal，零参数：输出已加载 Skill 的精简列表——首行 `Available skills (N):`，随后每条一行 `  /name  description`（按字典序、固定列宽对齐），末行追加 `Type /<skill-name> to invoke a skill.` 引导。来源（builtin/user/project）与模式（inline/fork）等元信息本期不在 `/skill` 输出中展示，开发者需要时直接读 SKILL.md
- **F35**：Catalog 为空时输出一行提示 `No skills loaded.`

## 非功能需求- **N1**：Skill 加载、命令注册全部在 gcode 启动期完成；启动期任何 fail-fast 错误（命名冲突、依赖工具缺失、zip 解压失败之外的解析错误）必须把错误消息打到 stderr 后继续启动但跳过出错 Skill，不阻断 gcode 进程
- **N2**：第一阶段 system prompt 注入的 Skill 列表落在 prompt cache 的稳定前缀区（与 ch07 prompt cache 设计一致），Skill 数量 ≤30 时单轮 cache 命中开销可忽略
- **N3**：第二阶段 active-skills 块每轮重新装配 env context，不通过 user 消息历史维持 SOP 可见性
- **N4**：LoadSkill 是 read-only + 系统工具，跨任意 allowed_tools 白名单都可见；权限系统不拦截
- **N5**：Skill 执行时的 `SKILL.md` 重读路径必须容错——磁盘读失败回退到内存缓存的上一版本并打 warning，不让一次磁盘错误中断已激活的 Skill
- **N6**：fork 模式起子 Agent 跑完后必须把子 Agent 的 token 用量计入主对话的 `SessionRuntime.usage_anchor`，使后续上下文压缩仍能感知到 fork 烧掉的 token
- **N7**：fork 模式子 Agent 异常退出（超时、`CancelledError`、LLM 错）时返回主对话的 assistant 消息为 `[skill <name> failed: <reason>]`，不让主对话卡死
- **N8**：InstallSkill 解压前严格校验 zip 内路径（拒绝 `..`、绝对路径、符号链接），防止 zip-slip
- **N9**：`/clear` 清空 Active Skills 的动作发生在新建 session writer 前，确保新会话首条 env context 已剔除旧 SOP
- **N10**：所有 Skill 文件路径、URL、name 等用户输入在错误信息中保持原样回显，便于排查
- **N11**：UI 抽象层新增 `activate_skill / clear_active_skills / list_active_skills / list_catalog_skills` 等查询/修改方法，与 ch10 已有 UI 接口风格一致；NopUI 对所有新方法提供零值实现
- **N12**：`tool.json` 的专属工具 exec 时使用 30 秒固定超时（与现有 bash 工具一致），stdin 传入 JSON 序列化后的工具调用参数，stdout 作为 tool_result 文本回传；returncode 非 0 视为工具失败

## 不做的事

- 不做 Skill 市场分发与版本管理（不实现 `skill.lock`、不做语义化版本依赖）
- 不做 Skill 沙箱隔离（专属工具 exec 直接信任本地脚本，不做 chroot/namespace）
- 不做 Skill 间显式 `can_delegate_to` 类型约束；嵌套调用通过 LoadSkill 系统工具自然实现
- 不做 fork 模式的"参考资料附件传递"——子 Agent 不预读 `references/` 下任何文件，由 SOP 自行通过 ReadFile 取
- 不修改 ch10 状态栏、自动补全菜单的视觉行为
- 不修改 ch10 已有 11 条内置命令的外部行为（除删除 `/review`）
- 不支持 SKILL.md 之外的格式（不接受 `skill.yaml` 单独定义元数据）
- 不支持单文件 Skill（必须是目录形态，方便后续扩展 tool.json 与 references/）
- 不做 Skill 启用/禁用开关命令（要禁用就直接删目录）
- 不在 TUI 里渲染 Skill 详情面板（`/skill` 仅文本输出列表）
- 不为 Skill 提供独立日志文件（与主进程共享 stderr）

## 验收标准- **AC1**：项目根目录与用户目录下都未放 Skill 时，启动 gcode 显示三个内置 Skill：`commit / review / test`；`/skill` 首行输出 `Available skills (3):`，随后三行 `  /<name>  <description>`，末行 `Type /<skill-name> to invoke a skill.`
- **AC2**：内置 `/review` 已从 ch10 命令注册中心移除；启动后 `/help` 不再单独列出 `/review` 而是出现 `/review [skill]`
- **AC3**：用户键入 `/review` 回车，触发 fork 模式 Skill；状态栏进入流式态、AI 输出审查报告后回流到主对话；主对话历史新增一条 assistant 消息（用户角度看不出是 fork）
- **AC4**：用户键入 `/commit` 回车，触发 inline 模式 Skill；主对话注入一条 user 消息（含 commit SOP 文本），LLM 按 SOP 调用 git status / diff / add / commit
- **AC5**：用户键入 `/test` 回车，触发 inline 模式 Skill；主对话注入测试相关的 SOP，LLM 按 SOP 检测项目类型并跑测试
- **AC6**：用户键入"帮我做个后端面试准备"等自然语言；当存在意图匹配的 Skill 时，LLM 主动调用 LoadSkill 工具激活它；下一轮 env context 中能看到该 Skill 的 SOP 钉在 active-skills 块
- **AC7**：LoadSkill 在权限模式为 PlanMode 下也可调用（read-only 标记生效，不被拦截）
- **AC8**：键入 `/clear`，新会话开始后 env context 的 active-skills 块为空，已激活 Skill 全部清掉
- **AC9**：在 `~/.gcode/skills/` 与 `<work_dir>/.gcode/skills/` 都放一个 `name: commit` 的 Skill，启动后 `/skill` 中 commit 一行的 description 取自项目级目录的版本（用户级被覆盖；source 信息不在 `/skill` 输出中展示，可通过描述差异区分）
- **AC10**：在 `<work_dir>/.gcode/skills/foo/SKILL.md` 中声明 `allowed_tools: [NotExist]`，启动时 stderr 打印 `skill foo: allowed_tool "NotExist" not registered, skipped`，进程继续启动，`/skill` 中不出现 foo
- **AC11**：在某 Skill 目录添加合法 `tool.json` 声明一个 `parse_resume` 工具（command 指向 references/parse_resume.sh，echo "ok"）；执行 LoadSkill 该 Skill 后，主工具注册中心新增 `parse_resume` 工具且 LLM 可调用并得到 `ok` 输出
- **AC12**：使用 LoadSkill 工具调用一个 `name: foo` 但 Catalog 中不存在的 Skill 时，tool_result 返回 `unknown skill: foo`，主对话不被中断
- **AC13**：InstallSkill 工具接受一个 zip URL（本地起 http server 模拟），下载并解压到 `~/.gcode/skills/<name>/`；解压完成后 `/skill` 列表立即包含该 Skill，无需重启
- **AC14**：在受 PlanMode 限制时调用 InstallSkill 工具，被权限系统拦截，提示需要切回默认模式
- **AC15**：恶意 zip 内含 `../../etc/passwd` 路径条目时，InstallSkill 拒绝解压并返回 `unsafe path in zip` 错误
- **AC16**：fork 模式跑完后 SessionRuntime 的 token 锚点已计入子 Agent 用量（用 `/status` 观察累计 token in/out 比 fork 前增加）
- **AC17**：在 tmux 内启动 gcode，依次执行 `/skill → /commit → /review → /test → 自然语言触发 LoadSkill → /clear → /skill`，全程不卡顿、无异常（端到端场景见 checklist）
````

````markdown
# Skill 技能包系统 Plan## 架构概览

新增一个 `gcode.skills` 包承载所有 Skill 相关的"数据 + 加载 + 执行 + 激活态"逻辑，与现有 `gcode.command`、`gcode.tool`、`gcode.prompt`、`gcode.agent` 通过细窄接口交互。

按职责拆解：

- **gcode.skills**：核心包。包含数据结构（`Skill`、`SkillMeta`、`ToolSpec`、`ActiveEntry`）、`SKILL.md` 解析、`tool.json` 解析、Catalog 三层路径扫描与覆盖、Skill 执行器（inline / fork 分支）、`ActiveSkills` 跨轮列表、`$ARGUMENTS` 渲染、`InstallSkill` zip 解压（zip-slip 防护），以及通过 `importlib.resources` 随包分发的三个内置 Skill 资源
- **gcode.tool.load_skill**：新增 LoadSkill 工具实现。是系统工具，永远可见，受不带权限拦截
- **gcode.tool.install_skill**：新增 InstallSkill 工具实现。普通工具，受权限模式约束
- **gcode.tool.registry**：扩展—增加"系统工具"标记与 `filter_by_allowed(allowed: list[str])` 切片导出能力；增加"动态注册专属工具"入口（Skill 加载时把 `tool.json` 工具注册进来）
- **gcode.command**：扩展—`register_skills_as_commands(reg, catalog, executor)` 把 Catalog 中每个 Skill 注册为 KindPrompt 命令；新增 `/skill` 命令（KindLocal，列出 Catalog）；删除 `handle_review` / `/review` 内置命令；UI 协议扩展 `list_catalog_skills / list_active_skills / clear_active_skills`
- **gcode.prompt**：扩展—`optional_modules` 中现有的 "active-skills" 槽位重命名为 "skills-catalog"，承载第一阶段名字+描述列表；新增 `render_active_skills_block(entries) -> str` 函数供 env context 拼装
- **gcode.agent**：扩展—`SessionRuntime` 新增 `active_skills: ActiveSkills` 字段；`Agent` 新增 `with_catalog` / `with_skill_executor` 配置项；`run()` 每轮重建 `sys` 时把 Catalog 列表传入 `build_system_prompt`、`env_text` 拼接时调用 `render_active_skills_block`；新增 `clear_active_skills() / activate_skill / list_active` 入口供 UI 与工具调用
- **gcode.tui**：扩展—`App` 持有 catalog 引用与执行器；`handle_clear` 路径在 `clear_and_new_session` 后调 `active_skills.clear()`；UI 协议对应新增方法实现

## 核心数据结构### SkillMeta

```python
# gcode/skills/types.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class SkillMeta:
    name: str
    description: str
    allowed_tools: list[str] = field(default_factory=list)
    mode: Literal["inline", "fork"] = "inline"
    fork_context: Literal["none", "recent", "full"] = "none"
    model: str | None = None

    def is_fork(self) -> bool:
        return self.mode == "fork"
```

约定：`mode` 为空或 "inline" 视作 inline；`mode == "fork"` 视作 fork；其它值打 warning 后按 inline 处理。`fork_context` 仅 fork 时生效，缺省 "none"。

### Skill

```python
from enum import Enum
from pathlib import Path

class SkillSource(Enum):
    BUILTIN = "builtin"
    USER = "user"
    PROJECT = "project"

@dataclass
class Skill:
    meta: SkillMeta
    prompt_body: str           # SKILL.md 去 frontmatter 后的正文（启动时缓存，执行时重读覆盖）
    source_dir: Path           # 绝对路径，重读 SKILL.md / 解析 tool.json 时用
    source: SkillSource        # BUILTIN / USER / PROJECT
    tool_specs: list["ToolSpec"] = field(default_factory=list)
```

### ToolSpec

```python
@dataclass
class ToolSpec:
    name: str                    # 工具名（与 frontmatter allowed_tools 用名一致）
    description: str
    input_schema: dict           # 标准 function calling JSON Schema
    command: list[str]           # argv，首元素相对 source_dir 解析（或绝对路径）
    base_dir: Path               # 工作目录（exec 时的 cwd），固定为 source_dir
```

### Catalog

```python
import asyncio

class Catalog:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()       # 用 threading.RLock 亦可（启动期无并发，此处主要给 reload 用）
        self._by_name: dict[str, Skill] = {}
        self._order: list[str] = []       # 按 name 排序的稳定迭代序

    @classmethod
    def load(cls, work_dir: Path) -> "Catalog": ...
    def reload(self, work_dir: Path) -> None: ...
    def get(self, name: str) -> Skill | None: ...
    def list(self) -> list[Skill]: ...      # 按 order
    def names(self) -> list[str]: ...
    def validate_tools(self, reg: "ToolRegistry") -> list["ValidationIssue"]: ...
```

`Catalog.load` 按顺序扫描：
1. 通过 `importlib.resources.files("gcode.skills.builtin")` 列出内置 Skill 目录并解析（`source=BUILTIN`）
2. `~/.gcode/skills/*` 子目录（`source=USER`）
3. `<work_dir>/.gcode/skills/*` 子目录（`source=PROJECT`）

后扫到的同名 `name` 覆盖前者。

### ActiveSkills

```python
import threading

@dataclass
class ActiveEntry:
    name: str
    body: str                    # 激活那一刻磁盘上的 SKILL.md 正文

class ActiveSkills:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[ActiveEntry] = []   # 保持激活顺序
        self._index: dict[str, int] = {}        # 重复激活的话覆盖原位置内容

    def activate(self, name: str, body: str) -> None: ...
    def clear(self) -> None: ...
    def snapshot(self) -> list[ActiveEntry]: ...  # 拷贝出当前列表（env 装配用）
    def names(self) -> list[str]: ...
```

### Executor

```python
class Executor:
    def __init__(
        self,
        catalog: Catalog,
        runtime: "SessionRuntime",
        registry: "ToolRegistry",
        provider: "Provider",
        eng: "PermissionEngine",
        version: str,
    ) -> None: ...

    # 入口：被 Slash 命令 handler 调用
    async def execute(
        self,
        ctx: "RunContext",
        ui: "UI",
        name: str,
        args: str,
    ) -> None: ...

    # inline 路径直接通过 ui.inject_and_send
    # fork 路径起子 Agent 跑完后通过 ui.append_assistant_message 写回主对话
```

## 模块设计### gcode/skills/parser.py
**职责**：解析单个 Skill 目录 → `Skill`
**对外接口**：`def parse_skill_dir(dir_path: Path, source: SkillSource) -> Skill`
**依赖**：`pyyaml`（已在 pyproject 依赖中）

解析流程：
1. 读 `<dir>/SKILL.md`，分离 frontmatter（两行 `---` 之间）与 body
2. `yaml.safe_load(frontmatter)` → `SkillMeta`；校验 name 合法性、mode / fork_context 取值
3. 读 `<dir>/tool.json`（不存在则跳过）→ `list[ToolSpec]`，校验 command 数组非空、首元素可解析为路径
4. 组装 `Skill` 返回

### gcode/skills/catalog.py
**职责**：三层路径扫描与覆盖管理
**对外接口**：`load / reload / get / list / names / validate_tools`
**依赖**：`gcode.skills.parser`, `importlib.resources`

`importlib.resources`：
```python
from importlib.resources import files

def _iter_builtin_skill_dirs():
    base = files("gcode.skills.builtin")
    for entry in base.iterdir():
        if entry.is_dir() and entry.joinpath("SKILL.md").is_file():
            yield entry
```

启动时把内置目录解压到一个临时位置或者直接以 traversable 抽象传给 parser；为统一处理（专属工具 exec 需要真实文件路径），首启时把内置 Skill 解压到 `$XDG_CACHE_HOME/gcode/builtin-skills/`（或 `pathlib.Path(tempfile.gettempdir()) / "gcode-builtin-skills"`）下，再走与文件系统目录一致的扫描逻辑。

`validate_tools`：遍历 Catalog 中所有 Skill 的 `meta.allowed_tools`，确认每个名字都能在传入的 `ToolRegistry` 里 `get` 到；记录所有不通过项返回。

### gcode/skills/render.py
**职责**：把 Skill body 渲染为最终注入文本（inline 和 fork 路径都先经过这一层）
**对外接口**：`def render_body(skill: Skill, args: str) -> str`

逻辑：
- 替换所有 `$ARGUMENTS` 出现
- 若无占位符且 args 非空，在末尾追加 `\n\n## User Request\n\n<args>`
- 若 `allowed_tools` 非空，在 body 顶部插一段 ``This skill is designed to use only these tools: <list>. Prefer them over other tools when possible.\n\n---\n\n``

### gcode/skills/executor.py
**职责**：inline / fork 分发与执行
**对外接口**：`Executor` 类（含 `execute(...)` async 方法）

inline 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`（失败回退缓存）
3. `render_body`
4. `await ui.inject_and_send(display_label, body)` —— `display_label` 例如 `/<name>`

fork 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`
3. `render_body`
4. 按 `fork_context` 构造初始 Conversation：
   - none：仅一条 user 消息（rendered_body）
   - recent：从主 conversation 拷最近 5 条原始消息，再追加 rendered_body
   - full：先用 `compact.summarize_for_fork(ctx, main_conv)`（基于 ch09 现成的摘要管道）产出摘要文本，作为一条 system 或 user 消息插入，再追加 rendered_body
5. 选 provider：默认主 provider；`skill.meta.model` 非空时调 `llm.new_provider(skill_model)` 重新构造
6. 构造子 Agent：复用 `agent.create(provider, registry, version, eng, runtime=fork_runtime)`，子 runtime 是独立 `new_session_runtime()`
7. 子 `await agent.run(...)` → 异步消费事件直到 done；累计 token 用量
8. 把累计 token 写回主 runtime 的 anchor（`usage += sub`）
9. 取子对话的最后一条 assistant 文本作为 final_text
10. `ui.append_assistant_message(final_text)`（新增 UI 方法）—— 主对话历史新增一条 assistant 消息

任一步骤出错（异常或 `asyncio.CancelledError`）：返回 `final_text = "[skill <name> failed: <reason>]"`，仍以 assistant 消息写入主对话。

### gcode/skills/install.py
**职责**：InstallSkill 的核心逻辑——下载 zip、校验路径、解压到 `~/.gcode/skills/`
**对外接口**：`async def install_from_url(source: str, catalog: Catalog, work_dir: Path) -> str`

流程：
1. 通过 `httpx.AsyncClient` 下载 source 到临时文件（限时 60s、限大小 50MB）
2. 用 `zipfile.ZipFile` 打开
3. 严格校验：所有路径必须以 `<top_dir>/` 起头、`<top_dir>` 满足 F3 命名、内部不含 `..`、不含绝对路径、不含符号链接（`ZipInfo.external_attr` 高位判定 symlink）
4. 解压到 `~/.gcode/skills/<top_dir>/`
5. 调用 `catalog.reload(work_dir)` 触发热重载
6. 返回 `<top_dir>` 作为 skill_name

### gcode/skills/builtin/*
**职责**：内置三个 Skill 的资源文件
**结构**：

```
gcode/skills/builtin/
├── __init__.py             — 空文件，使 builtin 成为可被 importlib.resources 寻址的包
├── commit/SKILL.md
├── review/SKILL.md
└── test/SKILL.md
```

每个 SKILL.md 都是完整的目录型 Skill（本期三个 builtin 不需要 tool.json，因为只用现有工具）。

内容要点（详见 task.md 中的步骤）：
- commit: `mode=inline`, `allowed_tools=[bash, read_file, grep]`
- review: `mode=fork`, `fork_context=none`, `allowed_tools=[read_file, grep, glob, bash]`
- test: `mode=inline`, `allowed_tools=[bash, read_file, grep, glob]`

注：`pyproject.toml` 中需配 `[tool.hatch.build.targets.wheel.force-include]`（或 hatch 的 `include` 配置）确保 `**/SKILL.md` 资源随 wheel 打包。

### gcode/tool/load_skill.py
**职责**：LoadSkill 工具实现
**对外接口**：实现 `Tool` 协议

```python
class LoadSkillTool:
    def __init__(self, catalog: Catalog, active: ActiveSkills, registry: ToolRegistry) -> None: ...

    # name / description / parameters / read_only / is_system / execute
```

`is_system` 返回 `True`——新加在 `Tool` Protocol（默认实现 `False`）。`execute` 流程：
1. 解析 `args["name"]`
2. `catalog.get(name)` → 不存在返回 `unknown skill: <name>`
3. 重读 `SKILL.md` 获取最新 body
4. `active.activate(name, body)`
5. 把 `skill.tool_specs` 注册进 `registry`（重复名静默覆盖，仅当前进程生效）
6. 返回 `Skill <name> activated. SOP pinned to env context. N specialized tools registered.`

### gcode/tool/install_skill.py
**职责**：InstallSkill 工具实现
**对外接口**：实现 `Tool` 协议

```python
class InstallSkillTool:
    def __init__(self, catalog: Catalog, work_dir: Path) -> None: ...
```

`read_only` 返回 `False`（写盘 + 网络），`is_system` 返回 `False`。`execute` 直接 `await install_from_url(...)`，返回成功消息或错误。

### gcode/tool/registry.py
**修改**：
- `Tool` Protocol 新增 `is_system: bool` 属性（默认 False）；现有 6 个工具与 MCP 工具默认实现返回 False
- LoadSkill 工具 `is_system` 返回 True
- 新增 `Registry.register_skill_tool(spec: ToolSpec)` 方法（动态注册专属工具）
- 新增 `Registry.system_definitions() -> list[ToolDefinition]`（仅返回系统工具）
- 新增 `Registry.definitions_filtered(allowed: list[str]) -> list[ToolDefinition]`（按白名单 + 系统工具豁免过滤）

注：本期不在主 agent loop 里用 `definitions_filtered` 改主对话工具集——按 spec F27 决议，inline 模式不真过滤。但 fork 模式子 Agent 用该方法构造工具集。

### gcode/prompt/modules.py
**修改**：
- `optional_modules(instructions, memory)` 改为 `optional_modules(instructions, memory, skills_catalog)`
- 原 priority 90 槽位由 "active-skills" 重命名为 "skills-catalog"，内容由调用方传入
- 增加常量 `PRIO_SKILLS_CATALOG = 90`，删除 `PRIO_ACTIVE_SKILLS`

### gcode/prompt/prompt.py
**修改**：
- `build_system_prompt(instructions, memory)` 改为 `build_system_prompt(instructions, memory, skills_catalog)`
- 增加 `render_active_skills_block(entries: list[ActiveSkillEntry]) -> str`，输出形如：
  ```
  ## Active Skills

  ### Skill: commit

  <body>

  ### Skill: review

  <body>
  ```
  entries 为空时返回空字符串
- 增加 `render_skills_catalog(items: list[SkillCatalogItem]) -> str`，输出 skills-catalog 模块内容；items 为空时返回空字符串

为避免 prompt 包反向依赖 skills 包，新增 dataclass 类型：
```python
@dataclass(frozen=True)
class SkillCatalogItem:
    name: str
    description: str

@dataclass(frozen=True)
class ActiveSkillEntry:
    name: str
    body: str
```

`skills.Catalog` 和 `skills.ActiveSkills` 提供两个适配方法 `to_prompt_items()` / `to_prompt_entries()` 把内部类型转换到 prompt 包的类型上。

### gcode/agent/runtime.py
**修改**：
- `SessionRuntime` 新增字段 `active_skills: ActiveSkills`
- `new_session_runtime()` 初始化空 `ActiveSkills`
- `reset_for_new_session` 同时 `r.active_skills.clear()`

### gcode/agent/agent.py
**修改**：
- 新增 `with_catalog(c: Catalog) -> AgentOption`：注入 catalog 引用（用于第一阶段列表与 clear_active_skills 入口）
- 新增 `Agent.activate_skill(name, body)` / `clear_active_skills()` 方法，转发到 `runtime.active_skills`
- `run()` 内每轮重建 sys 时：
  ```python
  sys = prompt.build_system_prompt(
      self._instruction_text,
      self._memory_text,
      prompt.render_skills_catalog(self._catalog.to_prompt_items()),
  )
  env_text = prompt.gather_environment(...).render() + "\n\n" + \
             prompt.render_active_skills_block(self._runtime.active_skills.to_prompt_entries())
  ```
  （`self._catalog` 为 None 时跳过；进度提示放在 sub-tasks）

### gcode/command/registry.py + skills.py (新建)
**职责**：把 Catalog 注册为 KindPrompt 命令；新增 `/skill` 命令；UI 协议扩展
**对外接口**：
- `def register_skills_as_commands(reg: Registry, catalog: Catalog, exec: Executor) -> None`
- 提供给 reload 路径调用的 `def remove_skill_commands(reg: Registry) -> None`
- 新增内置 `/skill` 命令（KindLocal）

`reg.register` 时给每个 Skill 添加 `hidden=False` 的 Command；命令的 handler 闭包捕获 `skill.name` 与 `executor`，调用 `await exec.execute(ctx, ui, name, "")`（本期不支持参数；后续在 dispatcher 加参数后填）。

注：当前 ch10 的 Slash dispatch 是零参数，Skill 显式调用本期也走零参数。`$ARGUMENTS` 替换仅在 LoadSkill + 后续 user message 的隐式场景下被替换为空——这是合理的简化（参数交互通过 Skill 后续轮次的对话进行）。

为了支持 reload 时清理旧命令，Registry 新增 `remove_all(filter: Callable[[Command], bool])` 或 `remove_skill_commands()` 入口。

### gcode/command/ui.py
**修改**：
- UI Protocol 新增方法：
  - `list_catalog_skills() -> list[SkillSummary]`（每条含 name/description/source/mode）
  - `list_active_skills() -> list[str]`
  - `clear_active_skills() -> None`
  - `append_assistant_message(text: str) -> None`（fork 路径用，把子 Agent 的 final_text 写入主对话历史）
- `NopUI` 提供零值实现

### gcode/command/builtins.py
**修改**：
- 删除 `name="review"` 的注册块（让 Skill 接管）
- 修改 `handle_clear`：在调 `ui.clear_and_new_session()` 后追加 `ui.clear_active_skills()`
- 新增 `name="skill"`、kind=KindLocal、handler=`handle_skill` 的注册块

### gcode/tui/*
**修改**：
- `App` 持有 `catalog: Catalog`、`executor: Executor`
- 实现新增的 UI 方法：`list_catalog_skills` / `list_active_skills` / `clear_active_skills` / `append_assistant_message`
- `tui.create_app` 接受新参数并接入

### src/gcode/cli.py
**修改**：
- 启动时构造 `catalog: Catalog`、`active_skills: ActiveSkills` 并注入到 `SessionRuntime`
- 注册 LoadSkill / InstallSkill 内置工具
- 在工具注册完成后调 `catalog.validate_tools(registry)`；对每条 issue 打 warning 并把该 Skill 从 Catalog 中移除（保留其它）
- 调 `command.register_skills_as_commands` 完成自动注册
- 把 catalog/executor 传给 tui

## 模块交互### 启动期

```
cli.main:
  ├─ tool.create_default_registry()
  ├─ mcp.attach_servers(registry)              # 已有
  ├─ skills.Catalog.load(work_dir)             # 三层路径扫描
  ├─ registry.register(LoadSkillTool(...))     # 系统工具
  ├─ registry.register(InstallSkillTool(...))
  ├─ catalog.validate_tools(registry)          # fail-fast 检查
  │     不通过项 → 打 warning + 从 catalog 移除
  ├─ skills.Executor(catalog, registry, ...)
  ├─ command.register_builtins(cmd_reg)        # ch10 11 条（review 已删）
  ├─ command.register_skills_as_commands(cmd_reg, catalog, executor)
  ├─ command.register_skill_cmd(cmd_reg)       # /skill (新)
  └─ tui.create_app(... catalog, executor, ...)
```

### Skill 显式调用（/commit）

```
user → submit → command.dispatch("/commit")
       → handler 调 await executor.execute(ctx, ui, "commit", "")
                 ├ inline: render → ui.inject_and_send → agent.run 注入主对话
                 └ fork: render → 子 Agent.run → final_text → ui.append_assistant_message
```

### Skill 意图触发（自然语言）

```
user 输入"帮我提交一下" → agent.run loop
   └ stream_once 拿到 LLM 调 LoadSkill({"name":"commit"})
        → registry.execute → LoadSkillTool.execute
              ├ catalog.get → 重读 SKILL.md
              ├ active.activate("commit", body)
              └ 返回 tool_result
   下一轮迭代:
        sys = build_system_prompt(... catalog 清单不变)
        env_text = ... + render_active_skills_block([("commit", body)])
        ↑ Agent 现在看得到完整 SOP
```

### /clear

```
/clear handler → ui.clear_and_new_session() (ch10) → ui.clear_active_skills()
                                                          └ runtime.active_skills.clear()
下轮 env_text 中 active-skills 块为空字符串
```

### Reload（InstallSkill 后或者未来 /skill reload）

```
InstallSkillTool.execute → await skills.install_from_url(...)
   └ 解压完毕 → catalog.reload(work_dir)
                ├ 重新扫描三层路径
                ├ 通过 lock 原子替换 _by_name / _order
                └ command 端不会立刻感知—但 dispatcher 每轮按命令名查找 reg，
                   reload 完成后下次 /<name> 即可命中新 Skill。然而启动时已注册的
                   旧命令仍在 registry 中。为简化，提供下面策略：
```

进一步：`catalog.reload` 返回 `(added, removed)`，InstallSkill 工具拿到结果后调 `cmd_reg.remove_skill_commands` + `register_skills_as_commands`，确保 `/help` 和补全菜单立即同步。

### Fork 模式

```
executor.execute (fork) →
   ┌──────────────────── 子 Agent ────────────────────┐
   │ 新 Conversation 按 fork_context 初始化            │
   │ agent.create(provider, registry, version, eng,    │
   │              runtime=fork_runtime)                │
   │ await agent.run(ctx, conv, default_mode)          │
   │ 累计 token, 取末尾 assistant text                  │
   └───────────────────────────────────────────────────┘
   将 final_text 作为一条 assistant 消息插入主 conv
```

注：fork 模式下子 Agent 的 registry 是用 `Registry.definitions_filtered(allowed)` 构造的临时视图（共享底层 `Tool` 实例），系统工具豁免列入。

## 文件组织

```
gcode/
├── pyproject.toml                    # 接线：dependencies 增 httpx；hatch include SKILL.md 资源
├── src/gcode/
│   ├── cli.py                        # 启动期接线
│   ├── skills/                       # 新包
│   │   ├── __init__.py               # 对外导出 Catalog / ActiveSkills / Executor / SkillSource ...
│   │   ├── types.py                  # SkillMeta / Skill / SkillSource / ToolSpec / ActiveEntry
│   │   ├── parser.py                 # parse_skill_dir, parse_frontmatter_and_body, parse_tool_json
│   │   ├── catalog.py                # Catalog: load / reload / get / list / names / validate_tools
│   │   ├── active.py                 # ActiveSkills
│   │   ├── render.py                 # render_body, $ARGUMENTS 替换, allowed_tools 顶部提示
│   │   ├── executor.py               # Executor.execute (inline / fork)
│   │   ├── install.py                # install_from_url（zip 下载与 zip-slip 防护）
│   │   ├── adapter.py                # to_prompt_items / to_prompt_entries 桥接到 prompt 包
│   │   └── builtin/                  # importlib.resources 资源
│   │       ├── __init__.py
│   │       ├── commit/SKILL.md
│   │       ├── review/SKILL.md
│   │       └── test/SKILL.md
│   ├── tool/
│   │   ├── registry.py               # 修改：is_system 标记 + definitions_filtered + register_skill_tool
│   │   ├── load_skill.py             # 新：LoadSkill 工具
│   │   ├── install_skill.py          # 新：InstallSkill 工具
│   │   └── skill_tool.py             # 新：把 ToolSpec 适配为 Tool 实现（asyncio.subprocess exec）
│   ├── command/
│   │   ├── builtins.py               # 修改：删 /review、改 handle_clear、加 /skill
│   │   ├── builtin_skill.py          # 新：handle_skill (KindLocal 列表)
│   │   ├── skills.py                 # 新：register_skills_as_commands / remove_skill_commands
│   │   └── ui.py                     # 修改：新增 4 个 UI 方法 + NopUI 兜底
│   ├── prompt/
│   │   ├── modules.py                # 修改：active-skills → skills-catalog
│   │   ├── prompt.py                 # 修改：build_system_prompt 增 catalog 参数
│   │   ├── skills_block.py           # 新：render_active_skills_block / render_skills_catalog / 类型
│   │   └── environment.py            # 不动
│   ├── agent/
│   │   ├── runtime.py                # 修改：SessionRuntime.active_skills 字段
│   │   ├── agent.py                  # 修改：with_catalog / run 内构造 sys 与 env 拼接
│   │   └── ...
│   └── tui/
│       ├── app.py                    # 修改：持有 catalog/executor + 实现新 UI 方法
│       └── ...
├── tests/
│   ├── test_skills_parser.py
│   ├── test_skills_catalog.py
│   ├── test_skills_render.py
│   ├── test_skills_install.py
│   ├── test_prompt_skills.py
│   └── test_command_skill.py
└── docs/python/ch11/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 数据格式 | 仅 SKILL.md（frontmatter+body） | 与 README 一致；解析路径单一；不引入 yaml/md 分离的认知负担 |
| Skill 形态 | 必须是目录 | 与 tool.json/references 自然契合；将来扩展空间大 |
| 优先级覆盖 | 内置 < 用户 < 项目 | 与 npm/git 习惯一致 |
| 内置 Skill 分发 | `importlib.resources` 随 wheel 走 | 与包一起分发；新机器装 gcode 即附带，不依赖外部文件 |
| 内置 Skill 落地 | 启动期解压到 cache 目录后按文件系统统一处理 | tool.json + references/ 需要真实路径才能 exec 脚本 |
| 第一阶段注入位置 | system prompt 模块（priority 90） | 享受 prompt cache 稳定前缀 |
| 第二阶段注入位置 | env context（每轮重建） | 多 Skill 同激活、嵌套场景下 SOP 永远靠前；prompt cache 失效是设计意图 |
| LoadSkill 入参 | 仅 name | 与"意图识别"语义一致；参数走后续 user message 更自然 |
| LoadSkill 权限 | read-only + 系统工具 | 没有外部副作用；为支持嵌套必须豁免 allowed_tools |
| InstallSkill 权限 | 普通工具，受权限模式约束 | 写盘+网络，必须走授权 |
| fork 模式实现 | Python 端起子 Agent（同进程 asyncio task） | 直接复用现成 `agent.run`，不依赖将来 SubAgent 章节 |
| fork_context 默认 | none | "隔离"才是 fork 本意；需要带上下文的显式声明 |
| allowed_tools 在 inline 模式 | 仅 fail-fast + SOP 提示 | 避免 inline 期间动态切换工具集的生命周期复杂度；安全靠 ch08 权限引擎兜底 |
| Skill 与已有命令冲突 | 跳过加载 + warning | 保护内置命令的可靠性；Skill 想替换内置命令需要用户主动改源码 |
| 解析失败 | 跳过单个 Skill，warning，不阻断 | 与 instructions loader 一致的容错策略 |
| 热加载 | InstallSkill 后主动 reload；execute 时重读 body | 用户改 SKILL.md 下次执行立即生效；新装 Skill 不需要重启 |
| Skill 列表数据流 | adapter 桥接，prompt 包不依赖 skills 包 | 避免循环依赖 |
| UI 接口扩展 | 4 个新方法 + NopUI 全量实现 | 与 ch10 风格一致 |
| 闭包循环变量 | 用 `functools.partial(handler, name=skill.name)` 或显式默认参数 `def f(ctx, ui, _name=skill.name)` | Python 闭包按引用绑定，循环里必须显式拷贝 |
| zip 下载 | `httpx.AsyncClient` | 已有 async stack；流式读取易做 `LimitReader` 限大小 |
| 子进程 exec | `asyncio.create_subprocess_exec` + `asyncio.wait_for(..., timeout=30)` | 不阻塞 event loop；与 ch05 bash 工具实现一致 |
| Skill 自身参数 | 本期 /<name> 仅零参数；后续轮次对话补 | 与 ch10 F7 一致，不破坏 dispatcher |
````

````markdown
# Skill 技能包系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gcode/skills/__init__.py` | 导出 `Catalog` / `ActiveSkills` / `Executor` / `SkillSource` 等 |
| 新建 | `src/gcode/skills/types.py` | `SkillMeta` / `Skill` / `SkillSource` / `ToolSpec` / `ActiveEntry` |
| 新建 | `src/gcode/skills/parser.py` | `parse_skill_dir`, `parse_frontmatter_and_body`, `parse_tool_json` |
| 新建 | `tests/test_skills_parser.py` | 解析路径单测 |
| 新建 | `src/gcode/skills/catalog.py` | `Catalog`: `load / reload / get / list / names / validate_tools` |
| 新建 | `tests/test_skills_catalog.py` | 三层覆盖单测 |
| 新建 | `src/gcode/skills/active.py` | `ActiveSkills` 列表 |
| 新建 | `src/gcode/skills/render.py` | `render_body`（`$ARGUMENTS` + allowed_tools 提示） |
| 新建 | `src/gcode/skills/adapter.py` | `to_prompt_items` / `to_prompt_entries` |
| 新建 | `src/gcode/skills/install.py` | `install_from_url` + zip-slip 防护 |
| 新建 | `tests/test_skills_install.py` | zip-slip / 正常 zip 解压单测 |
| 新建 | `src/gcode/skills/executor.py` | `Executor.execute`（inline / fork 分支） |
| 新建 | `src/gcode/skills/builtin/__init__.py` | 空包标识，供 `importlib.resources` 寻址 |
| 新建 | `src/gcode/skills/builtin/commit/SKILL.md` | 内置 commit Skill |
| 新建 | `src/gcode/skills/builtin/review/SKILL.md` | 内置 review Skill |
| 新建 | `src/gcode/skills/builtin/test/SKILL.md` | 内置 test Skill |
| 修改 | `src/gcode/tool/registry.py` | `is_system` 标记 + `definitions_filtered` + `register_skill_tool` |
| 新建 | `src/gcode/tool/skill_tool.py` | `ToolSpec` 适配为 Tool 实现（asyncio subprocess） |
| 新建 | `src/gcode/tool/load_skill.py` | LoadSkill 工具实现 |
| 新建 | `src/gcode/tool/install_skill.py` | InstallSkill 工具实现 |
| 修改 | `src/gcode/prompt/modules.py` | active-skills → skills-catalog 槽位 |
| 修改 | `src/gcode/prompt/prompt.py` | `build_system_prompt` 增 catalog 参数 |
| 新建 | `src/gcode/prompt/skills_block.py` | `render_skills_catalog` / `render_active_skills_block` + 桥接类型 |
| 修改 | `tests/test_prompt.py` | 同步 `build_system_prompt` 签名变更 |
| 修改 | `src/gcode/command/ui.py` | UI Protocol 新增 4 方法 + NopUI 实现 |
| 修改 | `src/gcode/command/builtins.py` | 删 /review、改 `handle_clear`、加 /skill 注册 |
| 新建 | `src/gcode/command/builtin_skill.py` | `handle_skill`（KindLocal 列表输出） |
| 新建 | `src/gcode/command/skills.py` | `register_skills_as_commands` / `remove_skill_commands` |
| 修改 | `src/gcode/command/registry.py` | 按命令标记筛选移除入口 |
| 修改 | `src/gcode/agent/runtime.py` | `SessionRuntime.active_skills` 字段 |
| 修改 | `src/gcode/agent/agent.py` | `with_catalog` + `run()` 拼装 sys/env + `activate_skill`/`clear_active_skills` |
| 修改 | `src/gcode/tui/app.py` | App 持有 catalog/executor + 4 个 UI 方法实现 |
| 修改 | `src/gcode/cli.py` | 启动期接线 |
| 修改 | `pyproject.toml` | 增 `httpx` 依赖；hatch include `**/SKILL.md` 资源 |

## T1: skills 包数据结构**文件**：`src/gcode/skills/types.py`、`src/gcode/skills/__init__.py`
**依赖**：无
**步骤**：
1. 定义 `SkillSource(Enum)` 枚举：`BUILTIN / USER / PROJECT`，`value` 分别为 `"builtin" / "user" / "project"`，`__str__` 返回 `self.value`
2. 定义 `@dataclass class SkillMeta` 含 6 个字段（`name`、`description`、`allowed_tools: list[str]=field(default_factory=list)`、`mode: Literal["inline","fork"]="inline"`、`fork_context: Literal["none","recent","full"]="none"`、`model: str | None = None`）
3. 添加 `is_fork(self) -> bool` 方法（`self.mode == "fork"`）
4. 定义 `@dataclass class ToolSpec`（`name`、`description`、`input_schema: dict`、`command: list[str]`、`base_dir: Path`）
5. 定义 `@dataclass class Skill`（`meta`、`prompt_body`、`source_dir: Path`、`source: SkillSource`、`tool_specs: list[ToolSpec]`）
6. 定义 `@dataclass class ActiveEntry`（`name`、`body`）
7. `__init__.py` 暴露上述类型与后续 `Catalog` / `ActiveSkills` / `Executor`（占位 import，后续任务填充）

**验证**：`python -c "from gcode.skills import SkillMeta, Skill, SkillSource"` 能 import；`ruff check src/gcode/skills/` 无告警。

## T2: SKILL.md 与 tool.json 解析**文件**：`src/gcode/skills/parser.py`
**依赖**：T1，需要 `pyyaml`（已在 pyproject 依赖）
**步骤**：
1. `def parse_skill_dir(dir_path: Path, source: SkillSource) -> Skill`：
   - 读 `<dir>/SKILL.md`，找不到抛 `FileNotFoundError(f"no SKILL.md in {dir_path}")`
   - 调 `_parse_frontmatter_and_body(data)` → `(meta_dict, body)`
   - `meta = SkillMeta(**meta_dict)`（用 `dataclasses.fields` 过滤未知键，或显式提取已知键）
   - 校验 `meta.name` 匹配正则 `^[a-z][a-z0-9-]*$` 且长度 1-32
   - 校验 `meta.description` 非空
   - 校验 `meta.mode` 为 `""/"inline"/"fork"`；其它值改 `"inline"` 并 `warnings.warn(...)` 或 `print(..., file=sys.stderr)`
   - 校验 `meta.fork_context` 为 `""/"none"/"recent"/"full"`
   - 读 `<dir>/tool.json`（不存在则跳过），调 `_parse_tool_json` 解析 → `list[ToolSpec]`，`base_dir = dir_path.resolve()`
   - 返回 `Skill(meta, body, dir_path.resolve(), source, tool_specs)`
2. `def _parse_frontmatter_and_body(data: str) -> tuple[dict, str]`：
   - 校验起始是 `---\n`
   - 找下一个 `---\n`，frontmatter = 两者之间，body = 之后
   - `yaml.safe_load(frontmatter)` → dict
3. `def _parse_tool_json(data: bytes, base_dir: Path) -> list[ToolSpec]`：
   - `json.loads` 一个 `{"tools": [{name, description, input_schema, command}, ...]}` 结构
   - 校验每条 name 满足命名规则、command 非空

**验证**：`python -c "from gcode.skills.parser import parse_skill_dir"` 通过；`ruff check` 无告警。

## T3: 解析单测**文件**：`tests/test_skills_parser.py`
**依赖**：T2
**步骤**：
1. `test_parse_skill_dir_minimal`：用 `tmp_path` 写一个最简 SKILL.md（name+description），expect 解析成功
2. `test_parse_skill_dir_invalid_name`：name 含大写字母 expect `pytest.raises(ValueError)`
3. `test_parse_skill_dir_with_tool_json`：含合法 tool.json，expect `tool_specs` 解析到位
4. `test_parse_skill_dir_no_skill_md`：缺 SKILL.md 抛 `FileNotFoundError`

**验证**：`pytest tests/test_skills_parser.py -v`，所有用例通过。

## T4: Catalog 三层加载与覆盖**文件**：`src/gcode/skills/catalog.py`
**依赖**：T1, T2
**步骤**：
1. 定义 `class Catalog`，成员：`_lock = threading.RLock()`、`_by_name: dict[str, Skill]`、`_order: list[str]`
2. `def __init__(self)` 构造空
3. `def register(self, s: Skill)`：加锁覆盖、维护 `_order` 不重复（覆盖时位置不变；新增时按 name 字典序插入或追加后排序）
4. `def get(self, name) -> Skill | None`：读锁
5. `def list(self) -> list[Skill]`：读锁，按 `_order` 输出
6. `def names(self) -> list[str]`：读锁
7. `@classmethod def load(cls, work_dir: Path) -> "Catalog"`：
   - 构造空 catalog
   - `_load_builtin_into(catalog)` → 通过 `importlib.resources` 加载（T5 完成 builtin 后接入；本任务先留一个 TODO 桩，跳过 builtin）
   - `_load_dir_into(catalog, Path.home() / ".gcode" / "skills", SkillSource.USER)`
   - `_load_dir_into(catalog, work_dir / ".gcode" / "skills", SkillSource.PROJECT)`
8. `def _load_dir_into(c: Catalog, base_dir: Path, source: SkillSource)`：
   - `base_dir.is_dir() is False` 静默跳过
   - 遍历直接子目录，每个调 `parse_skill_dir` 后 `c.register`；解析失败 `print(..., file=sys.stderr)` 跳过
9. `def reload(self, work_dir: Path) -> None`：构造新 catalog，原子替换内部 `_by_name`/`_order`
10. `@dataclass class ValidationIssue { skill_name: str; tool_name: str }`
11. `def validate_tools(self, reg: "ToolRegistry") -> list[ValidationIssue]`：遍历所有 skill 的 `allowed_tools`，逐项查 `reg.get`；未找到记录并 issue。**注意**：把 `load_skill` 与 `install_skill` 视为允许引用（与系统工具豁免逻辑一致）

**验证**：`python -c "from gcode.skills.catalog import Catalog; print(Catalog().names())"` 通过；先不要在 `load` 中接入 builtin。

## T5: 内置三个 Skill 的资源文件与 importlib.resources**文件**：
- `src/gcode/skills/builtin/__init__.py`
- `src/gcode/skills/builtin/commit/SKILL.md`
- `src/gcode/skills/builtin/review/SKILL.md`
- `src/gcode/skills/builtin/test/SKILL.md`
- `src/gcode/skills/embed_builtin.py`
- `pyproject.toml`（增 hatch include）

**依赖**：T4
**步骤**：
1. 写三个 SKILL.md，frontmatter 内容：
   - commit: `name=commit`, `description=分析 git diff 并生成规范的 commit`, `allowed_tools=[bash, read_file, grep]`, `mode=inline`
   - review: `name=review`, `description=客观审查代码变更与潜在问题`, `allowed_tools=[read_file, grep, glob, bash]`, `mode=fork`, `fork_context=none`
   - test: `name=test`, `description=运行项目测试并分析失败原因`, `allowed_tools=[bash, read_file, grep, glob]`, `mode=inline`
   正文按 README 描述的 SOP 写：步骤、注意事项、`$ARGUMENTS` 占位符
2. 新建 `embed_builtin.py`：
   ```python
   from importlib.resources import files
   def _iter_builtin_skill_dirs():
       base = files("gcode.skills.builtin")
       for entry in base.iterdir():
           if entry.is_dir() and entry.joinpath("SKILL.md").is_file():
               yield entry
   ```
3. 实现 `def _load_builtin_into(c: Catalog) -> None`：
   - 遍历 `_iter_builtin_skill_dirs()`
   - 对每个把资源内容（SKILL.md，如有 `tool.json` / `references/`）写到 `Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "gcode" / "builtin-skills" / <name>/`
   - 解压完后调 `parse_skill_dir(<cache_dir>, SkillSource.BUILTIN)` 加载
4. 在 `Catalog.load` 中调 `_load_builtin_into`
5. `pyproject.toml` 增加（hatch 后端）：
   ```toml
   [tool.hatch.build.targets.wheel.force-include]
   "src/gcode/skills/builtin" = "gcode/skills/builtin"
   ```
   或在 `[tool.hatch.build]` 段配 `include = ["src/gcode/skills/builtin/**/SKILL.md", ...]` 保证资源进 wheel

**验证**：
- `python -c "from gcode.skills.catalog import Catalog; from pathlib import Path; print(Catalog.load(Path('.')).names())"` 输出 `['commit', 'review', 'test']`（字典序）
- `uv build` 后 `unzip -l dist/gcode-*.whl | grep SKILL.md` 能看到三条

## T6: Catalog 单测**文件**：`tests/test_skills_catalog.py`
**依赖**：T4, T5
**步骤**：
1. `test_load_catalog_builtin_only`：用空 `tmp_path` 当 work_dir 跑 `Catalog.load`，期望 `names() == ['commit', 'review', 'test']`
2. `test_load_catalog_user_override`：在 `monkeypatch.setenv('HOME', str(tmp_home))` 下放 `commit` 目录，期望该目录的 description 覆盖 builtin
3. `test_load_catalog_project_override`：在 `tmp_work_dir/.gcode/skills` 放 `commit` 目录，期望覆盖 user
4. `test_validate_tools_missing_tool`：定义一个 skill 用 `NotExist` 工具，期望返回 1 个 issue

**验证**：`pytest tests/test_skills_catalog.py -v`，全部通过。

## T7: ActiveSkills 列表**文件**：`src/gcode/skills/active.py`
**依赖**：T1
**步骤**：
1. 定义 `class ActiveSkills`，成员 `_lock = threading.Lock()`、`_entries: list[ActiveEntry]`、`_index: dict[str, int]`
2. `def __init__(self)` 初始化空
3. `def activate(self, name: str, body: str) -> None`：加锁；若 name 已存在则更新 body（保持位置不变）；否则追加
4. `def clear(self) -> None`：加锁清空两个字段
5. `def snapshot(self) -> list[ActiveEntry]`：加锁拷贝（list + 元素）
6. `def names(self) -> list[str]`

**验证**：写一个简单单测覆盖 `activate/clear/snapshot` 路径，`pytest tests/test_skills_active.py` 通过。

## T8: Render 渲染**文件**：`src/gcode/skills/render.py`
**依赖**：T1
**步骤**：
1. `def render_body(s: Skill, args: str) -> str`：
   - `body = s.prompt_body`
   - 若 `len(s.meta.allowed_tools) > 0`：在 body 前插入"建议工具"提示行（格式见 plan.md F27），用 `\n\n---\n\n` 分隔
   - 若 `"$ARGUMENTS" in body`: `body = body.replace("$ARGUMENTS", args)`
   - 否则若 `args.strip() != ""`: `body += "\n\n## User Request\n\n" + args`
   - 返回 body
2. 单测：覆盖 4 种组合（有/无 placeholder × 有/无 args）

**验证**：`pytest tests/test_skills_render.py -v` 通过。

## T9: prompt 包适配器**文件**：`src/gcode/skills/adapter.py`
**依赖**：T4, T7
**步骤**：
1. 在 skills 包定义 `@dataclass(frozen=True) class PromptItem(name, description)` 与 `@dataclass(frozen=True) class PromptEntry(name, body)`（避免反向依赖 prompt 包）
2. `def catalog_to_prompt_items(c: Catalog) -> list[PromptItem]`：按 `_order` 输出
3. `def active_to_prompt_entries(a: ActiveSkills) -> list[PromptEntry]`：按 `snapshot` 顺序输出

**验证**：`ruff check src/gcode/skills/` 无告警。

## T10: prompt 模块槽位重命名**文件**：`src/gcode/prompt/modules.py`
**依赖**：无
**步骤**：
1. 把 `PRIO_ACTIVE_SKILLS = 90` 重命名为 `PRIO_SKILLS_CATALOG = 90`
2. `optional_modules(instructions, memory)` 改签名为 `optional_modules(instructions, memory, skills_catalog)`
3. 模块名由 `"active-skills"` 改为 `"skills-catalog"`，content 取 `skills_catalog` 参数

**验证**：`ruff check src/gcode/prompt/modules.py` 通过；`prompt.py` 调用处的报错留到 T12 修复。

## T11: prompt 新增 Skill 渲染函数**文件**：`src/gcode/prompt/skills_block.py`
**依赖**：T10
**步骤**：
1. 定义 `@dataclass(frozen=True) class SkillCatalogItem(name, description)` 与 `@dataclass(frozen=True) class ActiveSkillEntry(name, body)`
2. `def render_skills_catalog(items: list[SkillCatalogItem]) -> str`：items 空返回 `""`；否则输出：
   ```
   ## Available Skills

   - <name>: <description>
   ...

   Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
   ```
3. `def render_active_skills_block(entries: list[ActiveSkillEntry]) -> str`：entries 空返回 `""`；否则输出：
   ```
   ## Active Skills

   ### Skill: <name>

   <body>

   ### Skill: <name>

   <body>
   ```

**验证**：`python -c "from gcode.prompt.skills_block import render_skills_catalog; print(render_skills_catalog([]))"` 输出空串。

## T12: build_system_prompt 签名更新**文件**：`src/gcode/prompt/prompt.py`
**依赖**：T10, T11
**步骤**：
1. `build_system_prompt(instructions, memory)` 改为 `build_system_prompt(instructions, memory, skills_catalog)`
2. 内部把第三参数传给 `optional_modules`

**验证**：`python -c "import gcode.prompt"` 通过；`ruff check src/gcode/prompt/` 通过。

## T13: prompt 单测同步**文件**：`tests/test_prompt.py`
**依赖**：T12
**步骤**：
1. 所有 `build_system_prompt(X, Y)` 调用替换为 `build_system_prompt(X, Y, "")`（或必要场景传入非空 catalog 文本，新增 1 个用例覆盖）
2. 新增 `test_render_skills_catalog_non_empty / _empty` 与 `test_render_active_skills_block_non_empty / _empty`

**验证**：`pytest tests/test_prompt.py -v`，全部通过。

## T14: ToolRegistry 系统工具支持**文件**：`src/gcode/tool/registry.py` + 内置 6 工具与 MCP 工具
**依赖**：无
**步骤**：
1. `Tool` Protocol 新增 `is_system: bool` 属性（也可用 `@property`，默认 False）；6 个内置工具与 MCP 适配器各加一行 `is_system: bool = False`（dataclass 字段）或 `@property def is_system(self): return False`
2. `Registry.definitions_filtered(allowed: list[str]) -> list[ToolDefinition]`：按 order 遍历，name 在 allowed 集合内 OR `tool.is_system` 为 True 时纳入
3. `Registry.register_skill_tool(t: Tool) -> None` —— 重复名静默覆盖（不维护 order 中重名）

**验证**：`pytest tests/test_tool_registry.py -v`（如已有）通过；原 6 个工具与 MCP 适配编译通过。

## T15: ToolSpec 适配为 Tool**文件**：`src/gcode/tool/skill_tool.py`
**依赖**：T1, T14
**步骤**：
1. 定义 `def new_skill_tool(name: str, description: str, input_schema: dict, command: list[str], base_dir: Path) -> Tool`：
   - 返回一个实现了 Tool 协议的对象
   - `name / description / parameters / read_only(False) / is_system(False)` / `async def execute(...)`
   - `execute`：用 `json.dumps(args).encode()` 作为 stdin；`asyncio.create_subprocess_exec(*command, cwd=base_dir, stdin=PIPE, stdout=PIPE, stderr=PIPE)`；`asyncio.wait_for(proc.communicate(input=...), timeout=30)`；读 stdout 当结果文本；`returncode != 0` 视失败
2. 因 tool 包不应反向依赖 skills 包，这里把 `ToolSpec` 字段直接打散到工厂函数参数

**验证**：写最小单测，模拟一个 `echo "ok"` 的 shell 脚本，验证 `await execute(...)` 返回 "ok"。

## T16: LoadSkill 工具**文件**：`src/gcode/tool/load_skill.py`
**依赖**：T4, T7, T14, T15
**步骤**：
1. 定义 `class LoadSkillTool` 接受 `catalog`、`active`、`registry` 三个字段
2. `name = "load_skill"`，`description` 写明用途
3. `parameters` 返回 `{"type":"object","properties":{"name":{"type":"string","description":"Skill name to activate"}},"required":["name"]}`
4. `read_only` 属性返回 `True`（只动 Agent 自己状态，无外部副作用）；`is_system` 返回 `True`
5. `async def execute(self, ctx, args: dict) -> ToolResult`：
   - `name = args["name"]`
   - `skill = self.catalog.get(name)`；不存在返回 `ToolResult(text=f"unknown skill: {name}", is_error=True)`
   - 从磁盘 `<skill.source_dir>/SKILL.md` 重读，更新 body；失败回退到 `skill.prompt_body` 并打 warning
   - `self.active.activate(skill.meta.name, fresh_body)`
   - 注册 `skill.tool_specs`：`self.registry.register_skill_tool(new_skill_tool(...))`
   - 返回 `ToolResult(text=f"Skill {name} activated. SOP pinned to env context. {len(skill.tool_specs)} specialized tools registered.")`

**验证**：`ruff check src/gcode/tool/load_skill.py` 无告警；`pytest tests/test_tool_load_skill.py` 通过基础用例。

## T17: InstallSkill 工具**文件**：`src/gcode/tool/install_skill.py`
**依赖**：T18
**步骤**：
1. 定义 `class InstallSkillTool` 接受 `catalog`、`work_dir` 两个字段
2. `name = "install_skill"`，`description` 写明用途与限制
3. `parameters`：`{"type":"object","properties":{"source":{"type":"string","description":"URL of a Skill zip"}},"required":["source"]}`
4. `read_only = False`；`is_system = False`（受权限模式约束）
5. `async def execute(...)`：`await install_from_url(args["source"], self.catalog, self.work_dir)`，返回成功消息 `Skill <name> installed to ~/.gcode/skills/<name>.`

**验证**：`ruff check` 通过；本工具的功能在 T18 跑完后再做集成测试。

## T18: install_from_url 与 zip-slip 防护**文件**：`src/gcode/skills/install.py`
**依赖**：T4
**步骤**：
1. `async def install_from_url(source: str, catalog: Catalog, work_dir: Path) -> str`：
   - `async with httpx.AsyncClient(timeout=60.0) as client:` 流式下载到 `tempfile.NamedTemporaryFile`，累计 byte 数 >50MB 抛 `ValueError("zip too large")`
   - `zipfile.ZipFile(tmp.name)` 打开
   - 计算顶层目录名 = 所有条目共同前缀的第一段；校验匹配 `^[a-z][a-z0-9-]*$`
   - 遍历条目：
     - 拒绝 `..` in `Path(name).parts`
     - 拒绝 `Path(name).is_absolute()`
     - 拒绝 symlink：`zip_info.external_attr >> 16 & 0o170000 == 0o120000`
   - 解压到 `Path.home() / ".gcode" / "skills" / <top_dir>/`（用 `ZipFile.extract`，但要事先校验绝对路径未逃逸）
   - 调 `catalog.reload(work_dir)`
   - 返回 `top_dir`
2. 单测 `test_install_from_url_zip_slip`：构造恶意 zip 含 `../../bad`，期望 `ValueError` 含 "unsafe path"
3. 单测 `test_install_from_url_happy`：用 `pytest-httpserver` 或 `aiohttp.test_utils` 起一个返回正常 zip 的 server，期望 `catalog.get(top_dir)` 在调用后能拿到

**验证**：`pytest tests/test_skills_install.py -v` 通过。

## T19: Skill Executor (inline + fork)**文件**：`src/gcode/skills/executor.py`
**依赖**：T7, T8, T14
**步骤**：
1. 定义 `class Executor` 持有 `catalog`、`active`、`registry`、`provider`、`eng`、`version`、`runtime`
2. `def __init__(...)` 构造
3. `async def execute(self, ctx, ui, name: str, args: str) -> None`：
   - `skill = self.catalog.get(name)`；为 None → `ui.error(f"skill not found: {name}")`，返回
   - 重读 SKILL.md 更新 body（失败回退）
   - `rendered = render_body(skill, args)`
   - if `not skill.meta.is_fork()`: `await ui.inject_and_send(f"/{name}", rendered)`；返回
   - else (fork)：
     - 构造子 Conversation：按 `fork_context`（`"none"` / `"recent"` / `"full"`）
       - none: 仅 user 消息 = rendered
       - recent: 调 `ui.recent_messages(5)`（新增 UI 方法）拷贝再追加 user 消息
       - full: 暂用 recent 行为 + warning（`fork_context=full` 留个 TODO 后续 compact 摘要管道接入）。或本期实现简单版：复制 `ui.all_messages()` 用 ch09 现成的 compactor 压缩（如果改动太大，按 recent 行为兜底，并 stderr warning 提示用户）。**本期决议**：full 与 recent 等价处理，并打 warning，留待 ch12+ 真正接入
     - 选 provider：默认 `self.provider`；`skill.meta.model` 非空时 `llm.new_provider(model)` 重新构造（cli 已有相同代码可复用）
     - 子 registry 通过 `self.registry.definitions_filtered(skill.meta.allowed_tools)` → 但 `run()` 内部用的还是 `self.registry`；我们把过滤前置：用 `agent.with_filtered_registry(allowed: list[str])` 选项（新增）让子 Agent 在选 defs 时调 filtered
     - **简化方案**：本期 fork Agent 直接 `agent.create(prov, self.registry, self.version, self.eng, runtime=fork_runtime)`，不做工具过滤（与 inline 模式一致，靠 SOP 提示约束）。这与 spec F28 中"按 allowed_tools 过滤工具集"相违；选简单实现并在 plan/spec 中记录此简化项
     - **回到决议**：本期 fork Agent 用 `self.registry.definitions_filtered(...)` 的封装版（通过 `agent.with_filtered_registry` 选项），保持 fork 模式真过滤的 spec 承诺
     - 起子 Conversation：`fork_conv = Conversation.new()`；填入构造好的初始消息
     - `fork_agent = agent.create(provider, self.registry, self.version, self.eng, runtime=fork_runtime, allowed_tools=skill.meta.allowed_tools)`
     - 起一条 `await fork_agent.run(ctx, fork_conv, permission.Mode.DEFAULT)`，遍历异步事件流；累积 usage、提取最终 assistant text；最大 25 轮兜底
     - usage 累加到主 runtime
     - `final_text = 末尾 assistant 文本`；若失败：`f"[skill {name} failed: {reason}]"`
     - `await ui.append_assistant_message(final_text)`
4. 新增 `agent.with_filtered_registry(allowed: list[str])` 选项；在 `run()` 的 defs 选取处，若 allowed 非空，调 `self.registry.definitions_filtered(allowed)` 代替 `self.registry.definitions()`

**验证**：`pytest tests/test_skills_executor.py -v`（mock provider + ui）；后续端到端 tmux 跑通 `/review`。

## T20: command UI Protocol 扩展**文件**：`src/gcode/command/ui.py`
**依赖**：无（在 T19 前可独立完成）
**步骤**：
1. UI Protocol 新增 5 个方法：
   ```python
   def list_catalog_skills(self) -> list[SkillSummary]: ...
   def list_active_skills(self) -> list[str]: ...
   def clear_active_skills(self) -> None: ...
   async def append_assistant_message(self, text: str) -> None: ...
   def recent_messages(self, n: int) -> list[Message]: ...   # fork ForkContext=recent 用
   def all_messages(self) -> list[Message]: ...              # fork ForkContext=full 用
   ```
2. 定义 `@dataclass class SkillSummary(name, description, source, mode)`（放在 command 包，避免 skills 依赖 command）
3. `NopUI` 提供零值实现：`list_catalog_skills→[]`；`list_active_skills→[]`；`clear_active_skills→no-op`；`append_assistant_message→no-op`；`recent_messages→[]`；`all_messages→[]`

**验证**：`ruff check src/gcode/command/` 通过；`pytest tests/test_command_ui.py` 通过。

## T21: command/builtins.py 改动**文件**：`src/gcode/command/builtins.py`
**依赖**：T20
**步骤**：
1. 删除 `name="review"` 的整段 `reg.register` 块（与对应的 `handle_review` 函数文件——如有，标记 TODO 或一并清理）
2. 修改 `handle_clear`：在 `await ui.clear_and_new_session()` 之后追加一行 `ui.clear_active_skills()`
3. 新增 `reg.register` 块：
   ```python
   reg.register(Command(
       name="skill", description="列出已加载的 Skill",
       kind=CommandKind.LOCAL, handler=handle_skill,
   ))
   ```

**验证**：`pytest tests/test_command.py -v` 通过；如果有 review 单测，要么更新要么删除。

## T22: handle_skill 实现**文件**：`src/gcode/command/builtin_skill.py`
**依赖**：T20
**步骤**：
1. `async def handle_skill(ctx, ui) -> None`：
   - `skills = ui.list_catalog_skills()`
   - 空时 `ui.println("No skills loaded.")`
   - 否则：
     - 先 `ui.println(f"Available skills ({len(skills)}):")`
     - 再按 name 字典序逐条 `ui.println(f"  /{name:<20} {description}")`（每条独立 println 避免 notice_block 多行渲染产生空白）
     - 末尾 `ui.println("Type /<skill-name> to invoke a skill.")`
   - 不展示 source / mode 元信息——本期保持精简，开发者需要时直接读 SKILL.md

**验证**：`pytest tests/test_command_builtin_skill.py`（如果新增了相应单测）。

## T23: register_skills_as_commands**文件**：`src/gcode/command/skills.py`
**依赖**：T20, T22
**步骤**：
1. 定义命令的 meta 标记机制：在 `Command` dataclass 新增字段 `is_skill: bool = False`（也可单独维护一个 set，但加字段最简）。修改 ch10 `command.py` 中 `Command` 数据类增加这个字段
2. `def register_skills_as_commands(reg, items: list[SkillSummary], executor: SkillRunner)`：
   - `SkillRunner` Protocol：`async def execute(ctx, ui, name, args) -> None`
   - 遍历 items，每个 register 一个 `Command(name=item.name, description=item.description + " [skill]", kind=CommandKind.PROMPT, is_skill=True, handler=...)`
   - 用 `functools.partial(_run_skill, executor=executor, name=item.name)` 或 `lambda _ctx, _ui, _name=item.name: executor.execute(_ctx, _ui, _name, "")` **显式绑定 name**（Python 闭包变量是后期绑定，循环里必须用默认参数或 partial 拷贝）
3. `def remove_skill_commands(reg) -> None`：遍历 reg 内部 dict，删除 `is_skill=True` 的条目

注：Registry 内部存储要支持 iter/del 操作；可能需要扩展 ch10 的 `registry.py`（T24）。

**验证**：`pytest tests/test_command_skills.py` 通过。

## T24: command.Registry 删除 API**文件**：`src/gcode/command/registry.py`
**依赖**：T23
**步骤**：
1. 检查 ch10 现有 Registry 是否暴露足够 API；如未提供按条件删除，新增：
   - `def remove_if(self, pred: Callable[[Command], bool]) -> None`：按谓词删除（同时清 `_by_name` + `_by_alias` + list 序）
2. 在 `remove_skill_commands` 中调 `reg.remove_if(lambda c: c.is_skill)`

**验证**：`pytest tests/test_command_registry.py -v` 通过。

## T25: SessionRuntime active_skills 字段**文件**：`src/gcode/agent/runtime.py`
**依赖**：T7
**步骤**：
1. `SessionRuntime` 增加字段 `active_skills: ActiveSkills`
2. `new_session_runtime()` 初始化 `active_skills=ActiveSkills()`
3. `reset_for_new_session` 增加一行 `if self.active_skills is not None: self.active_skills.clear()`
4. 由于 agent 包反向引入 skills 包会有依赖循环（`skills.Executor` 依赖 `agent.SessionRuntime`）；解决方法：把 `ActiveSkills` 类型放到 agent 包下；或定义在 skills 包，agent 包 import 它（agent 已可以 import skills 包，没有循环——只要 skills 包不 import agent 包）。为简单起见，`Executor` 需要的 runtime 字段单独通过函数参数传递，不直接 import `agent.SessionRuntime`；让 `skills.Executor` 持有 `ActiveSkills` 而非 `SessionRuntime`

**重新设计**：
- skills 包不 import agent
- `agent.SessionRuntime` 持有 `active_skills: ActiveSkills` 字段
- `skills.Executor` 通过 `ActiveSkills` 操作激活态（不直接持有 `SessionRuntime`）

**验证**：`python -c "from gcode.agent.runtime import SessionRuntime"` 通过。

## T26: Agent 拼装 sys / env 改动**文件**：`src/gcode/agent/agent.py`
**依赖**：T9, T12, T25
**步骤**：
1. 新增 `with_catalog(c: Catalog) -> AgentOption`：设置 `self._catalog`
2. 新增 `with_filtered_registry(allowed: list[str]) -> AgentOption`：设置 `self._allowed_tools`
3. Agent 增加字段：`_catalog: Catalog | None`、`_allowed_tools: list[str] | None`
4. 新增方法 `def activate_skill(self, name, body)`，调 `self._runtime.active_skills.activate(...)`
5. 新增方法 `def clear_active_skills(self)`
6. `run()` 内每轮重建：
   ```python
   catalog_text = ""
   if self._catalog is not None:
       items = [SkillCatalogItem(p.name, p.description) for p in catalog_to_prompt_items(self._catalog)]
       catalog_text = prompt.render_skills_catalog(items)
   sys = prompt.build_system_prompt(self._instruction_text, self._memory_text, catalog_text)

   env_base = prompt.gather_environment(...).render()
   env_skills = ""
   if self._runtime is not None and self._runtime.active_skills is not None:
       entries = [ActiveSkillEntry(e.name, e.body) for e in active_to_prompt_entries(self._runtime.active_skills)]
       env_skills = prompt.render_active_skills_block(entries)
   env_text = env_base
   if env_skills:
       env_text += "\n\n" + env_skills
   ```
7. defs 选择：
   ```python
   defs = self._registry.definitions()
   if mode == permission.Mode.PLAN:
       defs = self._registry.read_only_definitions()
   if self._allowed_tools:
       defs = self._registry.definitions_filtered(self._allowed_tools)
   ```

**验证**：`pytest tests/test_agent.py -v` 通过；既有单测通过。

## T27: TUI App 与 UI 实现**文件**：`src/gcode/tui/app.py` + 相关
**依赖**：T20, T25
**步骤**：
1. `App` 持有 `catalog: Catalog`、`executor: Executor`
2. `create_app` 工厂接受 catalog/executor 参数
3. 实现 UI Protocol 的新方法：
   - `list_catalog_skills()`：从 catalog 转换
   - `list_active_skills()`：从 `runtime.active_skills.names()`
   - `clear_active_skills()`：`runtime.active_skills.clear()`
   - `append_assistant_message(text)`：追加到当前 conversation 与会话存档
   - `recent_messages(n) / all_messages()`：从当前 conversation 取
4. 注意：`UI.inject_and_send` 已有，不重写

**验证**：`pytest tests/test_tui.py` 通过；`python -m gcode` 能起来。

## T28: src/gcode/cli.py 接线**文件**：`src/gcode/cli.py`
**依赖**：T1-T27
**步骤**：
1. `from gcode.skills import Catalog, ActiveSkills, Executor`
2. 构造 `catalog = Catalog.load(work_dir)`
3. 构造 `ActiveSkills` 后 attach 到 `SessionRuntime`
4. 注册 `LoadSkillTool` / `InstallSkillTool` 到 `ToolRegistry`
5. 调 `issues = catalog.validate_tools(tool_reg)`；遍历 issues 打 stderr 并把不合格 skill 从 catalog 移除
6. 构造 `executor = Executor(catalog, active_skills, tool_reg, provider, eng, version, ...)`
7. 调 `command.register_builtins(cmd_reg)`（已有，删 `/review` 后内置 11 条）
8. 调 `command.register_skills_as_commands(cmd_reg, catalog 转换的 summary, executor)`
9. `tui.create_app(... catalog, executor)`
10. Agent 构造时附 `agent.with_catalog(catalog)`

**验证**：`python -m gcode` 全包跑起来；`ruff check src/gcode/` 无新增告警。

## T29: 启动冒烟**文件**：无
**依赖**：T28
**步骤**：
1. 在 tmux 内：`python -m gcode`，期望启动 banner 正常、状态栏正常
2. 键入 `/help`，期望输出含 `/skill` 行、不含独立 `/review` 行、含 `/commit [skill]` `/review [skill]` `/test [skill]` 三行
3. 键入 `/skill`，期望输出三行（commit/review/test，source=builtin）
4. ctrl+c 退出

**验证**：观察输出符合上述期望；任何异常或缺失都修正后重测。

## T30: 端到端验证场景

按 checklist.md 中端到端场景章节，在 tmux 里实跑全套流程。

## 执行顺序

```
T1 → T2 → T3
  → T4 (依赖 T1,T2) → T5 (依赖 T4) → T6 (依赖 T4,T5)
  → T7 (依赖 T1) → T8 (依赖 T1) → T9 (依赖 T4,T7)

T10 → T11 (依赖 T10) → T12 (依赖 T10,T11) → T13 (依赖 T12)

T14 → T15 (依赖 T1,T14) → T16 (依赖 T4,T7,T14,T15) → T17 (依赖 T18)
T18 (依赖 T4)

T20 → T21 (依赖 T20) → T22 (依赖 T20) → T23 (依赖 T20,T22) → T24 (依赖 T23)

T25 (依赖 T7) → T26 (依赖 T9,T12,T25) → T27 (依赖 T20,T25)

T19 (依赖 T7,T8,T14) → T28 (依赖 T1-T27)

T29 (依赖 T28) → T30
```

可并行：T1-T9 内部链；T10-T13 链；T14-T18 链；T20-T24 链 —— 这四条链彼此独立直到 T25 起开始合流。但本期由单一会话顺序执行，避免合并冲突。
````

````markdown
# Skill 技能包系统 Checklist

> 每一项通过运行代码或观察行为来验证。最后一节"端到端场景（tmux 实跑）"必须在 tmux 内实际跑过。

## 实现完整性

- [ ] `gcode.skills` 包可正常 import（验证：`python -c "import gcode.skills"` 无错）
- [ ] `gcode.tool.load_skill` 与 `gcode.tool.install_skill` 可正常 import（验证：`python -c "from gcode.tool import load_skill, install_skill"`）
- [ ] `gcode.prompt` 改造后单测通过（验证：`pytest tests/test_prompt.py`）
- [ ] `gcode.command` 改造后单测通过（验证：`pytest tests/test_command*.py`）
- [ ] `gcode.agent` 改造后单测通过（验证：`pytest tests/test_agent*.py`）
- [ ] 整包可启动（验证：`python -m gcode` 不报错）
- [ ] `ruff check .` 无新增告警
- [ ] `ruff format --check .` 通过
- [ ] 内置三个 Skill（commit / review / test）的 SKILL.md 通过 frontmatter 与 body 双重校验（验证：启动后 `/skill` 输出三行）

## Skill 定义与解析

- [ ] 一个最简的合法 SKILL.md（仅 name + description）能被 parser 解析成功（验证：`tests/test_skills_parser.py` 中 `test_parse_skill_dir_minimal` 通过）
- [ ] 非法 name（大写、空格、超长）被 parser 拒绝（验证：`tests/test_skills_parser.py` 中 `test_parse_skill_dir_invalid_name` 通过）
- [ ] `tool.json` 合法时解析为 ToolSpec 列表（验证：`tests/test_skills_parser.py` 中 `test_parse_skill_dir_with_tool_json` 通过）
- [ ] 缺 SKILL.md 时抛 `FileNotFoundError`（验证：`tests/test_skills_parser.py` 中 `test_parse_skill_dir_no_skill_md` 通过）

## Catalog 加载

- [ ] 空 work_dir + 空 HOME 启动时 Catalog 仅含三个内置 Skill（验证：`tests/test_skills_catalog.py` `test_load_catalog_builtin_only` 通过）
- [ ] 用户目录下同名 Skill 覆盖内置（验证：`test_load_catalog_user_override` 通过）
- [ ] 项目目录下同名 Skill 覆盖用户（验证：`test_load_catalog_project_override` 通过）
- [ ] 单个 Skill 解析失败（损坏 SKILL.md）只跳过它本身，其它 Skill 仍能加载（验证：写一个临时 user 目录含损坏 + 合法两个 Skill，启动后只看到合法那一个）
- [ ] Skill 名字与 ch10 已有命令冲突时跳过加载（验证：临时建一个 name=help 的 Skill 放 user 目录，启动 stderr 打 warning 且 `/help` 仍为内置命令）

## fail-fast 依赖检查

- [ ] Skill 的 `allowed_tools` 引用不存在的工具时，启动 stderr 输出对应错误并把该 Skill 从 Catalog 中剔除（验证：建一个含 `allowed_tools: [NotExist]` 的 Skill，启动 stderr 含 `allowed_tool "NotExist" not registered`，`/skill` 中不出现该 Skill）
- [ ] `load_skill` / `install_skill` 在 fail-fast 检查中被视为允许引用（验证：建一个 `allowed_tools: [load_skill]` 的 Skill，启动正常加载，不报错）

## Slash Command 自动注册

- [ ] 启动后 `/help` 包含 `/commit [skill]`、`/review [skill]`、`/test [skill]` 三行且不再有独立 `/review`（验证：tmux 启动后键入 `/help`）
- [ ] `/help` 包含 `/skill` 一行（验证：同上）
- [ ] 用 Tab 补全输入 `/comm`，菜单展示 `/commit [skill]` 候选（验证：tmux 实跑）

## 两阶段加载

- [ ] System prompt 中含 `## Available Skills` 区块，列出全部 Catalog Skill 的 `- name: description`（验证：在 `agent.run` 前打日志或加一个 dump-prompt 测试用例）
- [ ] 未激活任何 Skill 时 env context 不含 `## Active Skills` 区块（验证：单测 `render_active_skills_block([]) == ""`）
- [ ] 激活一个 Skill 后下一轮 env context 含 `## Active Skills` 区块包含该 Skill 的 body（验证：用单测覆盖 `render_active_skills_block`；端到端见 tmux 场景）

## LoadSkill 工具

- [ ] 调用 LoadSkill({"name":"commit"}) 后 `active.names()` 包含 `"commit"`（验证：单测）
- [ ] 调用 LoadSkill 不存在的 name 时返回 `unknown skill: <name>`，对话不中断（验证：tmux 实跑触发）
- [ ] LoadSkill 调用时即便 `allowed_tools` 是空白名单也可见（验证：单测 `Registry.definitions_filtered([])` 输出包含 `load_skill`）
- [ ] LoadSkill 在 Plan Mode 下可调用，不被权限拦截（验证：tmux 实跑 `/plan` 后让 LLM 触发 LoadSkill）

## /clear

- [ ] `/clear` 之后 `active.names()` 为空（验证：tmux 实跑：先触发 LoadSkill 激活某 Skill，再 `/clear`，下一轮观察 env context 无 Active Skills 块）
- [ ] `/clear` 之后新会话可在 `/resume` 列表中看到旧会话条目（验证：与 ch10 N9 一致，回归现有行为）

## Skill 执行器

- [ ] inline Skill 执行后主对话历史新增一条 user 消息（验证：tmux 触发 `/commit` 后 `/session` 显示路径，查看会话 JSONL）
- [ ] inline Skill 的 SOP 顶部含 "This skill is designed to use only these tools: ..." 提示（验证：单测覆盖 `render_body`）
- [ ] fork Skill 跑完后主对话新增一条 assistant 消息（验证：tmux 触发 `/review` 后会话 JSONL 末尾是 assistant 角色消息）
- [ ] fork Skill 失败（如子 Agent 报错或超时）时返回的 assistant 消息为 `[skill <name> failed: ...]` 文本（验证：mock provider 出错的执行器单测）

## tool.json 专属工具

- [ ] 一个含 `tool.json` 的 Skill 被 LoadSkill 激活后，主工具注册中心新增对应的工具名（验证：tmux 实跑：放一个测试 Skill 含 echo 的 `tool.json`，激活后让 LLM 调那个工具，观察输出）
- [ ] 专属工具 exec 超时 30 秒（验证：`tests/test_tool_skill_tool.py`：脚本 `sleep 100` 时返回 `asyncio.TimeoutError` 触发的错误结果）
- [ ] 专属工具 `returncode != 0` 视为失败，stderr 内容并入 result 文本（验证：单测）

## InstallSkill

- [ ] 合法 zip 安装后 `~/.gcode/skills/<top_dir>/` 出现 SKILL.md（验证：单测 + tmux 实跑）
- [ ] 合法 zip 安装后 `/skill` 立即列出新 Skill 且 `/<name>` 可调用（验证：端到端）
- [ ] zip-slip（含 `..` 路径）被拒绝，`~/.gcode/skills/` 无副作用（验证：单测 `test_install_from_url_zip_slip`）
- [ ] zip 内顶层目录命名违规时拒绝（验证：单测）
- [ ] InstallSkill 工具在 Plan Mode 下被权限引擎拦截，需要切回默认模式才能装（验证：tmux 实跑 `/plan` → 自然语言让 Agent 装 Skill → 看到权限被拦截）

## /skill 命令

- [ ] `/skill` 首行输出 `Available skills (N):`，随后每条一行 `  /<name>  <description>`（按字典序、固定列宽对齐），末行输出 `Type /<skill-name> to invoke a skill.`（验证：tmux 实跑）
- [ ] Catalog 为空时 `/skill` 输出 `No skills loaded.`（验证：清空内置 Skill 资源后启动）

## 编译与测试

- [ ] `python -m gcode` 能正常启动（在合法配置下进入 TUI）
- [ ] `pytest` 通过（含新增的 `tests/test_skills_*.py` 与 `tests/test_command_skill*.py`）
- [ ] `ruff check .` 无新增告警
- [ ] `ruff format --check .` 通过
- [ ] （可选）`mypy src/gcode` 通过

## 端到端场景（tmux 实跑）

> 在 tmux 内启动 gcode，按下面流程一步步操作；每步附"观察"项。

**前置**：
- 用 `tmux new -s mew-ch11 -x 200 -y 50` 起一个固定大小的 tmux session
- `cd /Users/codemelo/gcode && uv sync && python -m gcode`

**步骤**：

1. **启动与就绪**
   - 操作：进程启动
   - 观察：banner 正常显示；状态栏底部含 "Type a message and press Enter..."；进程不抛异常；stderr 无 "skipped" 类错误（如果用户/项目目录干净）

2. **`/help`**
   - 操作：键入 `/help` 回车
   - 观察：输出含 11 条 ch10 命令（已无独立 `/review`）+ `/skill` + `/commit [skill]` + `/review [skill]` + `/test [skill]`，共 15 行

3. **`/skill`**
   - 操作：键入 `/skill` 回车
   - 观察：首行 `Available skills (3):`，随后三行 `  /commit ...` / `  /review ...` / `  /test ...`，末行 `Type /<skill-name> to invoke a skill.`

4. **显式调用 inline Skill `/commit`**
   - 操作：键入 `/commit` 回车
   - 观察：状态栏立即进入流式；AI 开始按 commit SOP 走（应该会调 git status / diff）；本步骤是真实操作，按 q/esc 可中断；目的是验证 inline 路径联通

5. **显式调用 fork Skill `/review`**
   - 操作：在主对话先随便说一句 "I just edited some files."（让主对话有上下文），然后键入 `/review`
   - 观察：状态栏进入流式；AI 输出审查报告；最后主对话新增一条 assistant 消息（含审查结果）；`fork_context=none` 意味着子 Agent 看不到 "I just edited..." 那条 user 消息

6. **意图触发 LoadSkill**
   - 操作：键入自然语言 "我想做后端面试准备"（或类似能匹配 backend-interview-like description 的 Skill；如果当前 Catalog 只有 commit/review/test，需要先放一个 user-level Skill，name=backend-interview）
   - 观察：LLM 调用 LoadSkill 工具，工具结果为 "Skill backend-interview activated..."；下一轮起 env context 中出现该 Skill 的 SOP body

7. **`/clear` 清空激活**
   - 操作：键入 `/clear` 回车
   - 观察：对话区清空、session 新建；接着说一句任意话题，env context 中不再含上一轮激活的 SOP（可通过让 Agent 复述"现在你激活了什么 Skill"间接验证，或开启 debug 日志）

8. **InstallSkill 安装第三方 Skill**
   - 操作：用 `python3 -m http.server 8080` 在本地 8080 端口托管一个写好的 `test-skill.zip`（含 `myskill/SKILL.md`），切到 gcode 输入 "把这个 skill 装下：http://localhost:8080/test-skill.zip"
   - 观察：Agent 调 install_skill 工具；安装成功后 `/skill` 列表立即出现 myskill；`/myskill` 可调用

9. **`/clear` → 新会话不残留**
   - 操作：先激活 myskill，再 `/clear`，再 `/skill`
   - 观察：`/skill` 仍能看到 myskill（Catalog 与 Active 列表是两个概念，Catalog 不清）；env context 已无 Active Skills 块

10. **退出**
    - 操作：`/exit` 回车
    - 观察：进程优雅退出，无错误日志

## 验收报告模板

```
## 验收报告

### 通过
- [x] 实现完整性 — 全包启动：python -m gcode 输出 ...
- [x] /help 列表正确：含 /skill, /commit [skill] ...
- [x] /skill 输出三行内置 Skill ...

### 未通过
- [ ] 第 X 项 — 预期：...，实际：...，修复方案：...

### 端到端
- [x] 启动与就绪 — 结果：banner 正常
- [x] /help — 结果：15 行命令
- [x] /skill — 结果：commit/review/test 三行
- ...（按上面 10 步逐条列出）
```
````

### Java

````markdown
# Skill 技能包系统 Spec## 背景

ch10 给 GCode 装上了 Slash Command 注册中心和 12 条内置命令，其中 `/review` 是 KindPrompt 类型——把硬编码在源码里的代码审查 prompt 注入对话并触发 LLM。这种"写死在源码里"的 prompt 暴露出几个问题：

- 调整 prompt 必须重新编译，用户没办法在不动源码的前提下定制
- 只有开发者能新增 prompt 类命令，普通用户无法贡献
- prompt 命令拿到的工具集与普通对话完全一致，没法在执行 SOP 时收窄注意力或限制权限
- prompt 是孤零零的字符串，无法捎带专属工具、参考资料、辅助脚本

与此同时,GCode 接入 MCP 之后工具数量从 6 个膨胀到二十多个,模型选错工具的概率随之上升,需要一种机制把"完成某类任务时只看哪些工具"的范围收窄。

Skill 技能包系统在 ch10 命令体系之上解决这两个问题：把可复用的 AI 操作搬出源码、放进可编辑的 Markdown 文件；通过两阶段加载和工具白名单把每次任务的注意力收窄到最小工具子集。

## 目标- **G1**：让可复用的 AI 操作变成独立的 Markdown 文件（每个 Skill 一个目录），增/删/改一个 Skill 不需要重新编译 gcode
- **G2**：自动把已加载的 Skill 注册成 `/<name>` 形式的 Slash Command，沿用 ch10 的 KindPrompt 分支
- **G3**：实现两阶段加载——启动时只把 Skill 的 `name + description` 注入系统提示；Agent 通过 LoadSkill 工具按需把完整 SOP 钉到环境上下文，从而让 Agent 既能被显式命令调用，也能通过自然语言意图自动触发
- **G4**：实现两种执行模式：`inline`（默认，注入主对话）与 `fork`（在 Java 端起子 Agent，跑完返回 finalText 作为 assistant 消息回流主对话），覆盖"需要继承上下文"和"需要客观隔离"两类任务
- **G5**：通过 `allowedTools` 工具白名单做 fail-fast 依赖检查与 SOP 顶部"建议工具"提示，提高模型工具选择准确率
- **G6**：支持目录型 Skill：`SKILL.md` + 可选 `tool.json`（声明专属工具，调用时 exec `references/` 下的可执行脚本）+ `references/`，整套作为自包含能力包
- **G7**：内置 `commit`、`review`、`test` 三个 Skill 通过 Java classpath 资源（`src/main/resources/skills/builtin/`）打进 jar；同时提供 `InstallSkill` 内置工具从 URL/zip 拉取第三方 Skill 到 `~/.gcode/skills/`
- **G8**：`/clear` 时清空已激活 Skill 列表，保证新会话从干净状态开始

## 功能需求### Skill 定义与解析- **F1**：每个 Skill 是一个目录。目录内必须含一个 `SKILL.md` 文件；其它附属物（`tool.json`、`references/` 子目录）均为可选
- **F2**：`SKILL.md` 由 YAML frontmatter（被两行 `---` 包围）+ Markdown 正文构成。Frontmatter 必填字段为 `name`、`description`；可选字段为 `allowed_tools`、`mode`、`fork_context`、`model`
- **F3**：`name` 必须满足正则 `^[a-z][a-z0-9-]*$`，长度 1-32；`name` 同时作为 Slash Command 命令名
- **F4**：`description` 为一句话描述（建议 ≤120 字符），用于 system prompt 第一阶段注入与 `/help`、`/skill` 输出
- **F5**：`allowed_tools` 为字符串数组；缺省视为空（不限制）
- **F6**：`mode` 取值为 `inline` 或 `fork`；缺省视为 `inline`，未知值按 `inline` 处理并 warning
- **F7**：`fork_context` 取值为 `none` / `recent` / `full`；缺省视为 `none`；仅在 `mode: fork` 时生效，inline 模式下忽略
- **F8**：`model` 为可选字符串，覆盖该 Skill 执行时使用的 LLM 模型；缺省沿用主对话当前模型
- **F9**：Markdown 正文中的 `$ARGUMENTS` 占位符在执行期替换为用户传入的参数文本；如未包含该占位符且参数非空，则在正文末尾以 `\n\n## User Request\n\n<args>` 形式追加；参数为空时按空字符串处理
- **F10**：目录可包含 `tool.json` 文件，描述该 Skill 专属工具数组。每个工具元素包含 `name`（与 frontmatter `allowed_tools` 一致的命名规则）、`description`、`input_schema`（标准 function calling JSON Schema）、`command`（数组：argv 形式，首元素为相对 `references/` 的可执行文件路径或绝对路径）
- **F11**：单个 Skill 解析失败时跳过该 Skill 并打 warning，不阻断其它 Skill 加载

### Skill 加载器（Catalog）- **F12**：启动期按以下顺序扫描，每个位置下的"子目录"视为一个 Skill 候选：
  1. 内置 Skill（classpath 资源 `skills/builtin/<name>/SKILL.md`，启动期解压到本地 cache 目录）
  2. 用户级：`~/.gcode/skills/<name>/`
  3. 项目级：`<projectRoot>/.gcode/skills/<name>/`
- **F13**：同名覆盖按上述顺序依次进行——后扫描的同名 Skill 替换前者。最终优先级为：项目级 > 用户级 > 内置
- **F14**：扫描目录不存在时静默跳过；无 `SKILL.md` 的子目录跳过且打 warning
- **F15**：加载阶段对所有 Skill 的 `allowed_tools` 做 fail-fast 依赖检查——引用的工具名必须存在于主工具注册中心（含 MCP 注入的工具，及 Skill 自己 `tool.json` 注册进来的专属工具）；任一未找到则在启动 banner 后立即打印 error 并跳过该 Skill 加载
- **F16**：Skill 的 `name` 与 ch10 已有内置 Slash Command 命令名（含别名）冲突时，跳过加载该 Skill 并打 warning（理由：内置命令保护）
- **F17**：Catalog 提供 `reload(workDir)` 方法用于重新扫描三层路径，重新注册所有 Skill 命令；现有命令注册中心提供 `removeSkillCommands()` 入口让 reload 清掉旧的 skill 类命令再重新注册

### Slash Command 自动注册- **F18**：每个加载成功的 Skill 在 ch10 命令注册中心注册一条 `KindPrompt` 命令：
  - 命令名 = Skill 的 `name`
  - 描述 = Skill 的 `description` 末尾追加 `[skill]` 标记
  - 别名为空
  - hidden = false
- **F19**：用户输入 `/<name>` 等价于显式调用该 Skill（不带参数）；命令 handler 负责调用 Skill 执行器并按执行模式注入对话或起子 Agent
- **F20**：Skill 命令支持 ch10 的自动补全菜单，与内置命令共享同一前缀匹配逻辑

### 两阶段加载与 LoadSkill- **F21**：Prompt 模块新增一段 `skills-catalog`（priority 介于现有 long-term-memory 与 environment 之间），内容为：
  ```
  ## Available Skills

  - <name>: <description>
  - <name>: <description>
  ...

  Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
  ```
  Catalog 为空时该模块为空字符串，被 prompt assembler 跳过
- **F22**：环境上下文新增一段 `active-skills` 区块，按激活顺序拼接每个已激活 Skill 的 `SKILL.md` 正文（前置一行 `### Skill: <name>` 标题），每轮 Agent loop 重建 env context 时重新装配
- **F23**：注册一个新的内置工具 `LoadSkill`：
  - 输入参数：`{"name": "string"}`
  - 行为：从 Catalog 取 Skill；从磁盘重新读取 `SKILL.md` 拿到最新 body；调用 Agent 提供的 `activateSkill(name, body)` 把 Skill 钉到 Active 列表；若该 Skill 有 `tool.json`，把其中的专属工具登记进主工具注册中心（重复登记的工具名静默覆盖）
  - 返回：`Skill <name> activated. SOP pinned to env context. <N> specialized tools registered.`
  - 标记为 read-only（不被权限系统拦截），并在工具过滤逻辑中标记为系统工具（永远可见，不受 allowed_tools 约束）
- **F24**：Agent 侧新增 `activeSkills` 列表（基于 SessionRuntime），提供 `activateSkill(name, body)`、`clearActiveSkills()`、`listActive()` 方法
- **F25**：`/clear` 命令在新建会话前调用 `Agent.clearActiveSkills()`，确保下一会话的 env context 不再含上一对话激活的 SOP

### Skill 执行器- **F26**：Skill 执行器入口 `execute(ctx, name, args)`：从 Catalog 取定义；从磁盘重读最新 `SKILL.md`（重读失败回退缓存版本并打 warning）；按 `mode` 走两条分支
- **F27**：`inline` 分支：完成 `$ARGUMENTS` 替换；在正文顶部前插一段"建议工具"提示行（当 `allowed_tools` 非空时）；通过 `UI.injectAndSend` 把最终文本作为 user 消息注入主对话并触发回合
- **F28**：`fork` 分支：完成 `$ARGUMENTS` 替换；按 `fork_context` 构造子 Agent 的初始 Conversation（`none`：仅一条 user 消息为 Skill 文本；`recent`：复制主对话末尾最近 5 条消息再追加 Skill 文本；`full`：先用主对话历史调一次 LLM 摘要，再把摘要 + Skill 文本作为初始 user 消息）；按 Skill 的 `model`（若指定）切 provider；按 `allowed_tools` 过滤工具集（LoadSkill 系统工具豁免）；新起子 Agent 跑一轮 `run` 拿到 finalText；把 finalText 作为一条 assistant 消息插入主对话历史
- **F29**：fork 分支跑完后主对话沿用主 Agent 继续，不影响主对话的运行时模式/Conversation 长度估算外的其它状态

### InstallSkill 内置工具- **F30**：注册内置工具 `InstallSkill`，输入参数：`{"source": "string"}`。`source` 支持两种形式：
  - HTTP(S) URL 指向单个 `.zip` 文件（按 zip 解压）
  - HTTP(S) URL 指向"目录索引"（页面包含可下载文件列表，本期仅识别 .zip）
- **F31**：InstallSkill 解压目标固定为 `~/.gcode/skills/`。zip 内顶层目录名即为 Skill 名，需满足 F3 命名规范；不满足或 zip 结构非法则报错
- **F32**：InstallSkill 安装成功后调用 `catalog.reload`，自动让新 Skill 的 `/<name>` 命令与 system prompt 第一阶段列表立即可见
- **F33**：InstallSkill 不是系统工具，受权限模式约束（具有外部副作用——写磁盘/网络请求），需要走 ch08 权限系统的用户授权

### /skill 命令- **F34**：注册新的内置 Slash Command `/skill`，KindLocal，零参数：输出已加载 Skill 的精简列表——首行 `Available skills (N):`，随后每条一行 `  /name  description`（按字典序、固定列宽对齐），末行追加 `Type /<skill-name> to invoke a skill.` 引导。来源（builtin/user/project）与模式（inline/fork）等元信息本期不在 `/skill` 输出中展示，开发者需要时直接读 SKILL.md
- **F35**：Catalog 为空时输出一行提示 `No skills loaded.`

## 非功能需求- **N1**：Skill 加载、命令注册全部在 gcode 启动期完成；启动期任何 fail-fast 错误（命名冲突、依赖工具缺失、zip 解压失败之外的解析错误）必须把错误消息打到 stderr 后继续启动但跳过出错 Skill，不阻断 gcode 进程
- **N2**：第一阶段 system prompt 注入的 Skill 列表落在 prompt cache 的稳定前缀区（与 ch07 prompt cache 设计一致），Skill 数量 ≤30 时单轮 cache 命中开销可忽略
- **N3**：第二阶段 active-skills 块每轮重新装配 env context，不通过 user 消息历史维持 SOP 可见性
- **N4**：LoadSkill 是 read-only + 系统工具，跨任意 allowed_tools 白名单都可见；权限系统不拦截
- **N5**：Skill 执行时的 `SKILL.md` 重读路径必须容错——磁盘读失败回退到内存缓存的上一版本并打 warning，不让一次磁盘错误中断已激活的 Skill
- **N6**：fork 模式起子 Agent 跑完后必须把子 Agent 的 token 用量计入主对话的 `SessionRuntime.usageAnchor`，使后续上下文压缩仍能感知到 fork 烧掉的 token
- **N7**：fork 模式子 Agent 异常退出（超时、ctx 取消、LLM 错）时返回主对话的 assistant 消息为 `[skill <name> failed: <reason>]`，不让主对话卡死
- **N8**：InstallSkill 解压前严格校验 zip 内路径（拒绝 `..`、绝对路径、符号链接），防止 zip-slip
- **N9**：`/clear` 清空 Active Skills 的动作发生在新建 session writer 前，确保新会话首条 env context 已剔除旧 SOP
- **N10**：所有 Skill 文件路径、URL、name 等用户输入在错误信息中保持原样回显，便于排查
- **N11**：UI 抽象层新增 `activateSkill / clearActiveSkills / listActiveSkills / listCatalogSkills` 等查询/修改方法，与 ch10 已有 UI 接口风格一致；`NopUI` 对所有新方法提供零值实现
- **N12**：tool.json 的专属工具 exec 时使用 30 秒固定超时（与现有 bash 工具一致），stdin 传入 JSON 序列化后的工具调用参数，stdout 作为 tool_result 文本回传；exit code 非 0 视为工具失败

## 不做的事

- 不做 Skill 市场分发与版本管理（不实现 `skill.lock`、不做语义化版本依赖）
- 不做 Skill 沙箱隔离（专属工具 exec 直接信任本地脚本，不做 chroot/namespace）
- 不做 Skill 间显式 `canDelegateTo` 类型约束；嵌套调用通过 LoadSkill 系统工具自然实现
- 不做 fork 模式的"参考资料附件传递"——子 Agent 不预读 `references/` 下任何文件，由 SOP 自行通过 ReadFile 取
- 不修改 ch10 状态栏、自动补全菜单的视觉行为
- 不修改 ch10 已有 11 条内置命令的外部行为（除删除 `/review`）
- 不支持 SKILL.md 之外的格式（不接受 `skill.yaml` 单独定义元数据）
- 不支持单文件 Skill（必须是目录形态，方便后续扩展 tool.json 与 references/）
- 不做 Skill 启用/禁用开关命令（要禁用就直接删目录）
- 不在 TUI 里渲染 Skill 详情面板（`/skill` 仅文本输出列表）
- 不为 Skill 提供独立日志文件（与主进程共享 stderr）

## 验收标准- **AC1**：项目根目录与用户目录下都未放 Skill 时，启动 gcode 显示三个内置 Skill：`commit / review / test`；`/skill` 首行输出 `Available skills (3):`，随后三行 `  /<name>  <description>`，末行 `Type /<skill-name> to invoke a skill.`
- **AC2**：内置 `/review` 已从 ch10 命令注册中心移除；启动后 `/help` 不再单独列出 `/review` 而是出现 `/review [skill]`
- **AC3**：用户键入 `/review` 回车，触发 fork 模式 Skill；状态栏进入流式态、AI 输出审查报告后回流到主对话；主对话历史新增一条 assistant 消息（用户角度看不出是 fork）
- **AC4**：用户键入 `/commit` 回车，触发 inline 模式 Skill；主对话注入一条 user 消息（含 commit SOP 文本），LLM 按 SOP 调用 git status / diff / add / commit
- **AC5**：用户键入 `/test` 回车，触发 inline 模式 Skill；主对话注入测试相关的 SOP，LLM 按 SOP 检测项目类型并跑测试
- **AC6**：用户键入"帮我做个后端面试准备"等自然语言；当存在意图匹配的 Skill 时，LLM 主动调用 LoadSkill 工具激活它；下一轮 env context 中能看到该 Skill 的 SOP 钉在 active-skills 块
- **AC7**：LoadSkill 在权限模式为 PlanMode 下也可调用（read-only 标记生效，不被拦截）
- **AC8**：键入 `/clear`，新会话开始后 env context 的 active-skills 块为空，已激活 Skill 全部清掉
- **AC9**：在 `~/.gcode/skills/` 与 `<workDir>/.gcode/skills/` 都放一个 `name: commit` 的 Skill，启动后 `/skill` 中 commit 一行的 description 取自项目级目录的版本（用户级被覆盖；source 信息不在 `/skill` 输出中展示，可通过描述差异区分）
- **AC10**：在 `<workDir>/.gcode/skills/foo/SKILL.md` 中声明 `allowed_tools: [NotExist]`，启动时 stderr 打印 `skill foo: allowed_tool "NotExist" not registered, skipped`，进程继续启动，`/skill` 中不出现 foo
- **AC11**：在某 Skill 目录添加合法 `tool.json` 声明一个 `parse_resume` 工具（command 指向 references/parse_resume.sh，echo "ok"）；执行 LoadSkill 该 Skill 后，主工具注册中心新增 `parse_resume` 工具且 LLM 可调用并得到 `ok` 输出
- **AC12**：使用 LoadSkill 工具调用一个 `name: foo` 但 Catalog 中不存在的 Skill 时，tool_result 返回 `unknown skill: foo`，主对话不被中断
- **AC13**：InstallSkill 工具接受一个 zip URL（本地起 http server 模拟），下载并解压到 `~/.gcode/skills/<name>/`；解压完成后 `/skill` 列表立即包含该 Skill，无需重启
- **AC14**：在受 PlanMode 限制时调用 InstallSkill 工具，被权限系统拦截，提示需要切回默认模式
- **AC15**：恶意 zip 内含 `../../etc/passwd` 路径条目时，InstallSkill 拒绝解压并返回 `unsafe path in zip` 错误
- **AC16**：fork 模式跑完后 SessionRuntime 的 token 锚点已计入子 Agent 用量（用 `/status` 观察累计 token in/out 比 fork 前增加）
- **AC17**：在 tmux 内启动 gcode，依次执行 `/skill → /commit → /review → /test → 自然语言触发 LoadSkill → /clear → /skill`，全程不卡顿、无 panic（端到端场景见 checklist）
````

````markdown
# Skill 技能包系统 Plan## 架构概览

新增一个 `dev.gcode.skills` 包承载所有 Skill 相关的"数据 + 加载 + 执行 + 激活态"逻辑，与现有 `dev.gcode.command`、`dev.gcode.tool`、`dev.gcode.prompt`、`dev.gcode.agent` 通过细窄接口交互。

按职责拆解：

- **dev.gcode.skills**：核心包。包含数据结构（`Skill`、`SkillMeta`、`ToolSpec`、`ActiveEntry`）、`SKILL.md` 解析、`tool.json` 解析、`Catalog` 三层路径扫描与覆盖、Skill 执行器（inline / fork 分支）、`ActiveSkills` 跨轮列表、`$ARGUMENTS` 渲染、`InstallSkill` zip 解压（zip-slip 防护），以及通过 classpath 资源（`src/main/resources/skills/builtin/`）嵌入的三个内置 Skill 资源
- **dev.gcode.tool.LoadSkillTool**：新增 LoadSkill 工具实现。是系统工具，永远可见，不带权限拦截
- **dev.gcode.tool.InstallSkillTool**：新增 InstallSkill 工具实现。普通工具，受权限模式约束
- **dev.gcode.tool.ToolRegistry**：扩展——增加"系统工具"标记与 `filterByAllowed(List<String> allowed)` 切片导出能力；增加"动态注册专属工具"入口（Skill 加载时把 tool.json 工具注册进来）
- **dev.gcode.command**：扩展——`registerSkillsAsCommands(registry, catalog, executor)` 把 Catalog 中每个 Skill 注册为 KindPrompt 命令；新增 `/skill` 命令（KindLocal，列出 Catalog）；删除 `handleReview` / `/review` 内置命令；`UI` 接口扩展 `listCatalogSkills / listActiveSkills / clearActiveSkills`
- **dev.gcode.prompt**：扩展——`OptionalModules` 中现有的"active-skills"槽位重命名为"skills-catalog"，承载第一阶段名字+描述列表；新增 `renderActiveSkillsBlock(entries)` 函数供 env context 拼装
- **dev.gcode.agent**：扩展——`SessionRuntime` 新增 `ActiveSkills activeSkills` 字段；`Agent` 新增 `withCatalog` / `withSkillExecutor` 构造选项；`run` 每轮重建 `sys` 时把 Catalog 列表传入 `buildSystemPrompt`、`envText` 拼接时调用 `renderActiveSkillsBlock`；新增 `clearActiveSkills() / activateSkill / listActive` 入口供 UI 与工具调用
- **dev.gcode.tui**：扩展——Model 持有 catalog 引用与执行器；`handleClear` 路径在 `clearAndNewSession` 后调 `activeSkills.clear`；UI 接口对应新增方法实现

## 核心数据结构### SkillMeta

```java
package dev.gcode.skills;

import java.util.List;

public record SkillMeta(
        String name,
        String description,
        List<String> allowedTools,
        String mode,         // "inline" / "fork"
        String forkContext,  // "none" / "recent" / "full"
        String model
) {
    public boolean isFork() {
        return "fork".equals(mode);
    }
}
```

约定：`mode` 为 null 或 `"inline"` 视作 inline；`mode == "fork"` 视作 fork；其它值打 warning 后按 inline 处理。`forkContext` 仅 fork 时生效，缺省 `"none"`。

YAML → record 由 SnakeYAML Engine 解析成 `Map<String,Object>` 后手动绑定（`allowed_tools` 下划线键映射到 record 字段）。

### Skill

```java
public record Skill(
        SkillMeta meta,
        String promptBody,        // SKILL.md 去 frontmatter 后的正文（启动时缓存，执行时重读覆盖）
        java.nio.file.Path sourceDir,  // 绝对路径，重读 SKILL.md / 解析 tool.json 时用
        SkillSource source,       // BUILTIN / USER / PROJECT
        List<ToolSpec> toolSpecs  // tool.json 解析结果（可为空）
) {}

public enum SkillSource {
    BUILTIN, USER, PROJECT;

    @Override
    public String toString() {
        return name().toLowerCase();  // "builtin" / "user" / "project"
    }
}
```

由于 `Skill` 字段在执行期需要被 `promptBody` 重读覆盖，实际实现把它声明为带 setter 的普通类（或用 `AtomicReference<String>` 包装可变正文）。

### ToolSpec

```java
public record ToolSpec(
        String name,              // 工具名（与 frontmatter allowed_tools 用名一致）
        String description,
        String inputSchemaJson,   // 标准 function calling JSON Schema（保留为原始 JSON 字符串）
        List<String> command,     // argv，首元素相对 sourceDir 解析（或绝对路径）
        java.nio.file.Path baseDir  // 工作目录（exec 时的 cwd），固定为 sourceDir
) {}
```

### Catalog

```java
public final class Catalog {
    private final java.util.concurrent.locks.ReadWriteLock lock =
            new java.util.concurrent.locks.ReentrantReadWriteLock();
    private final java.util.Map<String, Skill> byName = new java.util.HashMap<>();
    private final java.util.List<String> order = new java.util.ArrayList<>();  // 按 name 字典序

    public static Catalog load(java.nio.file.Path workDir);
    public void reload(java.nio.file.Path workDir);              // 内部锁保护，原子替换
    public java.util.Optional<Skill> get(String name);
    public java.util.List<Skill> list();                          // 按 order
    public java.util.List<String> names();
    public java.util.List<ValidationIssue> validateTools(ToolRegistry registry);
}
```

`Catalog.load` 按顺序扫描：
1. 通过 classpath 资源（`getResourceAsStream("skills/builtin/<name>/SKILL.md")`）列出内置 Skill 并解析（`source=BUILTIN`）
2. `~/.gcode/skills/*` 子目录（`source=USER`）
3. `<workDir>/.gcode/skills/*` 子目录（`source=PROJECT`）

后扫到的同名 `name` 覆盖前者。

### ActiveSkills

```java
public record ActiveEntry(String name, String body) {}

public final class ActiveSkills {
    private final Object lock = new Object();
    private final java.util.List<ActiveEntry> entries = new java.util.ArrayList<>();
    private final java.util.Map<String, Integer> index = new java.util.HashMap<>();

    public void activate(String name, String body);
    public void clear();
    public java.util.List<ActiveEntry> snapshot();  // 拷贝出当前列表（env 装配用）
    public java.util.List<String> names();
}
```

### Executor

```java
public final class Executor {
    private final Catalog catalog;
    private final SessionRuntime runtime;  // 持有 ActiveSkills 等跨轮状态
    private final ToolRegistry registry;
    private final Provider provider;        // 默认 provider；fork 时可用 Skill.model 切换
    private final PermissionEngine engine;
    private final String version;

    public Executor(...) { ... }

    // 入口：被 Slash 命令 handler 调用
    public void execute(java.util.concurrent.CancellationException ctx /* 或自定义 CancelToken */,
                        UI ui, String name, String args);

    // inline 路径直接通过 ui.injectAndSend
    // fork 路径起子 Agent 跑完后通过 ui.appendAssistantNotice 写回主对话
}
```

实际取消用 `volatile boolean cancelled` + `Thread.interrupt()`，签名里以一个轻量级 `CancelToken` 类传递。

## 模块设计### dev.gcode.skills.SkillParser
**职责**：解析单个 Skill 目录 → `Skill`
**对外接口**：`static Skill parseSkillDir(Path dir, SkillSource source) throws SkillParseException`
**依赖**：`org.snakeyaml:snakeyaml-engine`（已在 pom.xml 中）+ Jackson（解析 tool.json）

解析流程：
1. 读 `<dir>/SKILL.md`，分离 frontmatter（两行 `---` 之间）与 body
2. SnakeYAML `Load.loadFromString(frontmatter)` → `Map<String,Object>` → 手动绑定 `SkillMeta`；校验 name 合法性、mode / fork_context 取值
3. 读 `<dir>/tool.json`（不存在则跳过）→ Jackson `ObjectMapper.readValue(...)` → `List<ToolSpec>`，校验 command 数组非空、首元素可解析为路径
4. 组装 `Skill` 返回

### dev.gcode.skills.Catalog
**职责**：三层路径扫描与覆盖管理
**对外接口**：`load / reload / get / list / names / validateTools`
**依赖**：`dev.gcode.skills.SkillParser`、JDK `java.nio.file`

classpath 资源加载：
```java
// 启动时把内置目录解压到 cache 目录
URL root = GCode.class.getResource("/skills/builtin");
// 通过 jar URL 或本地文件系统列出条目，逐个复制到
// $XDG_CACHE_HOME/gcode/builtin-skills/<name>/（或 System.getProperty("user.home") + "/.cache/gcode/builtin-skills/"）
```

为统一处理（专属工具 exec 需要真实文件路径），首启时把内置 Skill 解压到 `~/.cache/gcode/builtin-skills/` 下，再走与文件系统目录一致的扫描逻辑。

`validateTools`：遍历 Catalog 中所有 Skill 的 `meta.allowedTools`，确认每个名字都能在传入的 `ToolRegistry` 里 `get` 到；记录所有不通过项返回。

### dev.gcode.skills.Render
**职责**：把 Skill body 渲染为最终注入文本（inline 和 fork 路径都先经过这一层）
**对外接口**：`static String renderBody(Skill skill, String args)`

逻辑：
- 替换所有 `$ARGUMENTS` 出现
- 若无占位符且 args 非空（trim 后非空），在末尾追加 `\n\n## User Request\n\n<args>`
- 若 `meta.allowedTools` 非空，在 body 顶部插一段 `This skill is designed to use only these tools: <list>. Prefer them over other tools when possible.\n\n---\n\n`

### dev.gcode.skills.Executor
**职责**：inline / fork 分发与执行
**对外接口**：`Executor` 构造 / `execute`

inline 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`（失败回退缓存）
3. `Render.renderBody`
4. `ui.injectAndSend(displayLabel, body)` —— displayLabel 例如 `/<name>`

fork 分支：
1. 从 Catalog 取 Skill
2. 从磁盘重读 `SKILL.md`
3. `Render.renderBody`
4. 按 `forkContext` 构造初始 Conversation：
   - none：仅一条 user 消息（renderedBody）
   - recent：从主 conversation 拷最近 5 条原始消息，再追加 renderedBody
   - full：先用 `Compact.summarizeForFork(ctx, mainConv)`（基于 ch09 现成的摘要管道）产出摘要文本，作为一条 system 或 user 消息插入，再追加 renderedBody
5. 选 provider：默认主 provider；`skill.meta().model()` 非空时调 `ProviderFactory.create(...)` 重新构造
6. 构造子 Agent：复用 `Agent.builder().provider(...).registry(...).version(...).engine(...).runtime(forkRuntime).build()`，子 runtime 是独立 `new SessionRuntime()`
7. `forkAgent.run` → 消费 `Flow.Publisher<RunEvent>` 直到 `Done`；累计 token 用量
8. 把累计 token 写回主 runtime 的 anchor（usage += sub）
9. 取子对话的最后一条 assistant 文本作为 finalText
10. `ui.appendAssistantMessage(finalText)`（新增 UI 方法）—— 主对话历史新增一条 assistant 消息

任一步骤出错：返回 `finalText = "[skill <name> failed: <reason>]"`，仍以 assistant 消息写入主对话。

### dev.gcode.skills.Install
**职责**：InstallSkill 的核心逻辑——下载 zip、校验路径、解压到 ~/.gcode/skills/
**对外接口**：`static String installFromUrl(CancelToken ctx, String source, Catalog catalog, Path workDir) throws IOException`

流程：
1. 通过 `java.net.http.HttpClient`（`newHttpClient()`，`Duration.ofSeconds(60)`）下载 source 到临时文件（大小限制 50 MB，超出关闭 stream）
2. 用 `java.util.zip.ZipInputStream` / `ZipFile` 打开
3. 严格校验：所有路径必须以 `<topDir>/` 起头、`<topDir>` 满足 F3 命名、内部不含 `..`、不含绝对路径、不含符号链接（zip 条目通常不含符号链接位，但若 entry 的 unix-attr 标识为 symlink 则拒绝）
4. 解压到 `~/.gcode/skills/<topDir>/`
5. 调用 `catalog.reload(workDir)` 触发热重载
6. 返回 `<topDir>` 作为 skillName

### src/main/resources/skills/builtin/*
**职责**：内置三个 Skill 的资源文件
**结构**：

```
src/main/resources/skills/builtin/
├── commit/SKILL.md
├── review/SKILL.md
└── test/SKILL.md
```

每个 SKILL.md 都是完整的目录型 Skill（本期三个 builtin 不需要 tool.json，因为只用现有工具）。

内容要点（详见 task.md 中的步骤）：
- commit: mode=inline, allowed_tools=[bash, read_file, grep]
- review: mode=fork, fork_context=none, allowed_tools=[read_file, grep, glob, bash]
- test: mode=inline, allowed_tools=[bash, read_file, grep, glob]

### dev.gcode.tool.LoadSkillTool
**职责**：LoadSkill 工具实现
**对外接口**：实现 `Tool` 接口

```java
public final class LoadSkillTool implements Tool {
    private final Catalog catalog;
    private final ActiveSkills active;
    private final ToolRegistry registry;

    // name / description / parameters / readOnly() / isSystem() / execute(...)
}
```

`isSystem() { return true; }`——新加在 `Tool` 接口（默认 default 方法返回 false，LoadSkill 覆盖为 true）。`execute` 流程：
1. 解析 `args.name`（Jackson `readTree` 取字段）
2. `catalog.get(name)` → 不存在返回 `unknown skill: <name>`
3. 重读 SKILL.md 获取最新 body
4. `active.activate(name, body)`
5. 把 `skill.toolSpecs()` 注册进 registry（重复名静默覆盖，仅当前进程生效）
6. 返回 `Skill <name> activated. SOP pinned to env context. N specialized tools registered.`

### dev.gcode.tool.InstallSkillTool
**职责**：InstallSkill 工具实现
**对外接口**：实现 `Tool`

```java
public final class InstallSkillTool implements Tool {
    private final Catalog catalog;
    private final Path workDir;
}
```

`readOnly() { return false; }`（写盘 + 网络），`isSystem() { return false; }`。`execute` 直接调 `Install.installFromUrl`，返回成功消息或错误。

### dev.gcode.tool.ToolRegistry
**修改**：
- `Tool` 接口新增 `default boolean isSystem() { return false; }` 方法；现有 6 个工具与 MCP 工具沿用默认实现
- `LoadSkillTool.isSystem()` 返回 true
- 新增 `ToolRegistry.registerSkillTool(ToolSpec spec)` 方法（动态注册专属工具）
- 新增 `ToolRegistry.systemDefinitions(): List<ToolDefinition>`（仅返回系统工具）
- 新增 `ToolRegistry.definitionsFiltered(List<String> allowed): List<ToolDefinition>`（按白名单 + 系统工具豁免过滤）

注：本期不在主 agent loop 里用 `definitionsFiltered` 改主对话工具集——按 spec F27 决议，inline 模式不真过滤。但 fork 模式子 Agent 用该方法构造工具集。

### dev.gcode.prompt.Modules
**修改**：
- `optionalModules(String instructions, String memory)` 改为 `optionalModules(String instructions, String memory, String skillsCatalog)`
- 原 priority 90 槽位由 `"active-skills"` 重命名为 `"skills-catalog"`，内容由调用方传入
- 增加常量 `PRIO_SKILLS_CATALOG = 90`，删除 `PRIO_ACTIVE_SKILLS`

### dev.gcode.prompt.Prompt
**修改**：
- `buildSystemPrompt(String instructions, String memory)` 改为 `buildSystemPrompt(String instructions, String memory, String skillsCatalog)`
- 增加 `static String renderActiveSkillsBlock(List<ActiveSkillEntry> entries)`，输出形如：
  ```
  ## Active Skills

  ### Skill: commit

  <body>

  ### Skill: review

  <body>
  ```
  entries 空时返回空字符串
- 增加 `static String renderSkillsCatalog(List<SkillCatalogItem> items)`，输出 skills-catalog 模块内容；items 空时返回空字符串

为避免 prompt 包反向依赖 skills 包，新增类型：
```java
public record SkillCatalogItem(String name, String description) {}
public record ActiveSkillEntry(String name, String body) {}
```

`skills.Catalog` 和 `skills.ActiveSkills` 提供两个适配方法 `toPromptItems()` / `toPromptEntries()` 把内部类型转换到 prompt 包的类型上。

### dev.gcode.agent.SessionRuntime
**修改**：
- `SessionRuntime` 新增字段 `ActiveSkills activeSkills`
- 构造函数初始化空 `new ActiveSkills()`
- `resetForNewSession` 同时 `this.activeSkills.clear()`

### dev.gcode.agent.Agent
**修改**：
- 新增 `Builder.catalog(Catalog c)`：注入 catalog 引用（用于第一阶段列表与 clearActiveSkills 入口）
- 新增 `Agent.activateSkill(name, body)` / `clearActiveSkills()` 方法，转发到 `runtime.activeSkills`
- `run` 内每轮重建 sys 时：
  ```java
  String catalogText = catalog != null
      ? Prompt.renderSkillsCatalog(catalog.toPromptItems())
      : "";
  String sys = Prompt.buildSystemPrompt(instructionText, memoryText, catalogText);
  String envText = Environment.gather(...).render()
      + "\n\n" + Prompt.renderActiveSkillsBlock(runtime.activeSkills().toPromptEntries());
  ```
  （`catalog` 为 null 时跳过；进度提示放在 sub-tasks）

### dev.gcode.command.Registry + Skills (新建)
**职责**：把 Catalog 注册为 KindPrompt 命令；新增 /skill 命令；UI 接口扩展
**对外接口**：
- `registerSkillsAsCommands(Registry reg, Catalog catalog, Executor exec)`
- 提供给 reload 路径调用的 `removeSkillCommands(Registry reg)`
- 新增内置 `/skill` 命令（KindLocal）

`reg.register` 时给每个 Skill 添加 `hidden=false` 的 `Command`；命令的 `Handler` 是一个 lambda（`(ctx, ui) -> exec.execute(ctx, ui, skillName, "")`），其中 `skillName` 是局部 final 变量以避免闭包捕获后被覆盖。

注：当前 ch10 的 Slash dispatch 是零参数，Skill 显式调用本期也走零参数。`$ARGUMENTS` 替换仅在 LoadSkill + 后续 user message 的隐式场景下被替换为空——这是合理的简化（参数交互通过 Skill 后续轮次的对话进行）。

为了支持 reload 时清理旧命令，`Registry` 新增 `removeIf(Predicate<Command>)` 或 `removeSkillCommands()` 入口。

### dev.gcode.command.UI
**修改**：
- UI 接口新增方法：
  - `List<SkillSummary> listCatalogSkills()`（每条含 name/description/source/mode）
  - `List<String> listActiveSkills()`
  - `void clearActiveSkills()`
  - `void appendAssistantMessage(String text)`（fork 路径用，把子 Agent 的 finalText 写入主对话历史）
- `NopUI` 提供零值实现

### dev.gcode.command.Builtins
**修改**：
- 删除 `name = "review"` 的注册块（让 Skill 接管）
- 修改 `handleClear`：在调 `ui.clearAndNewSession()` 后追加 `ui.clearActiveSkills()`
- 新增 `name = "skill"`、kind = KindLocal、handler = `handleSkill` 的注册块

### dev.gcode.tui.*
**修改**：
- Model 持有 `Catalog`、`Executor` 字段
- 实现新增的 UI 方法：`listCatalogSkills` / `listActiveSkills` / `clearActiveSkills` / `appendAssistantMessage`
- `TuiApp` 的 builder 接受新参数并接入

### dev.gcode.Main
**修改**：
- 启动时构造 `Catalog`、`ActiveSkills` 并注入到 `SessionRuntime`
- 注册 `LoadSkillTool` / `InstallSkillTool` 内置工具
- 在工具注册完成后调 `catalog.validateTools(registry)`；对每条 issue 打 warning 并把该 Skill 从 Catalog 中移除（保留其它）
- 调 `Commands.registerSkillsAsCommands` 完成自动注册
- 把 catalog/executor 传给 TUI

## 模块交互### 启动期

```
Main.main:
  ├─ ToolRegistry.defaultRegistry()
  ├─ Mcp.attachServers(registry)              // 已有
  ├─ Catalog.load(workDir)                    // 三层路径扫描
  ├─ registry.register(new LoadSkillTool(...))// 系统工具
  ├─ registry.register(new InstallSkillTool(...))
  ├─ catalog.validateTools(registry)          // fail-fast 检查
  │     不通过项 → 打 warning + 从 catalog 移除
  ├─ new Executor(catalog, registry, ...)
  ├─ Commands.registerBuiltins(cmdReg)        // ch10 11 条（review 已删）
  ├─ Commands.registerSkillsAsCommands(cmdReg, catalog, executor)
  ├─ Commands.registerSkillCmd(cmdReg)        // /skill (新)
  └─ TuiApp.builder().catalog(catalog).executor(executor)...build().run()
```

### Skill 显式调用（/commit）

```
user → submit → Commands.dispatch(/commit)
       → handler 调 executor.execute(ctx, ui, "commit", "")
                 ├ inline: render → ui.injectAndSend → agent.run 注入主对话
                 └ fork: render → 子 Agent.run → finalText → ui.appendAssistantMessage
```

### Skill 意图触发（自然语言）

```
user 输入"帮我提交一下" → agent.run loop
   └ streamOnce 拿到 LLM 调 LoadSkill({name:"commit"})
        → tool.execute → LoadSkillTool.execute
              ├ catalog.get → 重读 SKILL.md
              ├ active.activate("commit", body)
              └ 返回 toolResult
   下一轮迭代:
        sys = buildSystemPrompt(...catalog清单不变)
        envText = ... + renderActiveSkillsBlock(["commit" -> body])
        ↑ Agent 现在看得到完整 SOP
```

### /clear

```
/clear handler → ui.clearAndNewSession() (ch10) → ui.clearActiveSkills()
                                                       └ runtime.activeSkills.clear()
下轮 envText 中 active-skills 块为空字符串
```

### reload (InstallSkill 后或者未来 /skill reload)

```
InstallSkillTool.execute → Install.installFromUrl
   └ 解压完毕 → catalog.reload(workDir)
                ├ 重新扫描三层路径
                ├ 通过读写锁原子替换 byName / order
                └ command 端不会立刻感知—但 dispatcher 每轮按命令名查找 reg，
                   reload 完成后下次 /<name> 即可命中新 Skill。然而启动时已注册的
                   旧命令仍在 registry 中。为简化，提供下面策略：
```

进一步：`catalog.reload` 返回 `(added, removed)` 两个列表，`InstallSkillTool` 拿到结果后调 cmdReg `removeSkillCommands` + `registerSkillsAsCommands`，确保 /help 和补全菜单立即同步。

### Fork 模式

```
executor.execute (fork) →
   ┌──────────────────── 子 Agent ────────────────────┐
   │ 新 Conversation 按 forkContext 初始化             │
   │ Agent.builder().provider(provider).registry(...) │
   │   .version(version).engine(eng)                   │
   │   .runtime(forkRuntime).build()                   │
   │ forkAgent.run(ctx, conv, defaultMode)             │
   │ 累计 token, 取末尾 assistant text                  │
   └───────────────────────────────────────────────────┘
   将 finalText 作为一条 assistant 消息插入主 conv
```

注：fork 模式下子 Agent 的 registry 是用 `ToolRegistry.definitionsFiltered(allowed)` 构造的临时视图（共享底层 `Tool` 实例），系统工具豁免列入。

## 文件组织

```
gcode/
├── src/main/java/dev/gcode/
│   ├── Main.java                       # 接线：构造 catalog / executor / 注册工具与命令
│   ├── skills/                         # 新包
│   │   ├── SkillMeta.java              # record
│   │   ├── SkillSource.java            # enum BUILTIN / USER / PROJECT
│   │   ├── Skill.java                  # 持有 promptBody（可变）
│   │   ├── ToolSpec.java               # record
│   │   ├── ActiveEntry.java            # record
│   │   ├── SkillParser.java            # parseSkillDir / parseFrontmatter / parseToolJson
│   │   ├── Catalog.java                # load / reload / get / list / names / validateTools
│   │   ├── ActiveSkills.java
│   │   ├── Render.java                 # renderBody, $ARGUMENTS 替换, allowed_tools 顶部提示
│   │   ├── Executor.java               # execute(inline / fork)
│   │   ├── Install.java                # installFromUrl（zip 下载与 zip-slip 防护）
│   │   └── Adapter.java                # toPromptItems / toPromptEntries 桥接到 prompt 包
│   ├── tool/
│   │   ├── ToolRegistry.java           # 修改：isSystem 标记 + definitionsFiltered + registerSkillTool
│   │   ├── LoadSkillTool.java          # 新：LoadSkill 工具
│   │   ├── InstallSkillTool.java       # 新：InstallSkill 工具
│   │   └── SkillTool.java              # 新：把 ToolSpec 适配为 Tool 实现（exec command）
│   ├── command/
│   │   ├── Builtins.java               # 修改：删 /review、改 handleClear、加 /skill
│   │   ├── BuiltinSkill.java           # 新：handleSkill (KindLocal 列表)
│   │   ├── Skills.java                 # 新：registerSkillsAsCommands / removeSkillCommands
│   │   └── UI.java                     # 修改：新增 4 个 UI 方法 + NopUI 兜底
│   ├── prompt/
│   │   ├── Modules.java                # 修改：active-skills → skills-catalog
│   │   ├── Prompt.java                 # 修改：buildSystemPrompt 增 catalog 参数
│   │   ├── SkillsBlock.java            # 新：renderActiveSkillsBlock / renderSkillsCatalog / 类型
│   │   └── Environment.java            # 不动
│   ├── agent/
│   │   ├── SessionRuntime.java         # 修改：activeSkills 字段
│   │   └── Agent.java                  # 修改：catalog 选项 / run 内构造 sys 与 env 拼接
│   └── tui/
│       ├── TuiApp.java                 # 修改：持有 catalog/executor + 实现新 UI 方法
│       └── ...
├── src/main/resources/skills/builtin/
│   ├── commit/SKILL.md
│   ├── review/SKILL.md
│   └── test/SKILL.md
├── src/test/java/dev/gcode/
│   ├── skills/SkillParserTest.java
│   ├── skills/CatalogTest.java
│   ├── skills/InstallTest.java
│   ├── prompt/PromptTest.java
│   └── agent/AgentRuntimeTest.java
└── docs/ch11/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 数据格式 | 仅 SKILL.md（frontmatter+body） | 与 README 一致；解析路径单一；不引入 yaml/md 分离的认知负担 |
| Skill 形态 | 必须是目录 | 与 tool.json/references 自然契合；将来扩展空间大 |
| 优先级覆盖 | 内置 < 用户 < 项目 | 与 npm/git 习惯一致 |
| 内置 Skill 分发 | Java classpath 资源（jar 内嵌） | 与 fat jar 一起走；新机器不依赖外部文件 |
| 内置 Skill 落地 | 启动期解压到 cache 目录后按文件系统统一处理 | tool.json + references/ 需要真实路径才能 exec 脚本 |
| 第一阶段注入位置 | system prompt 模块（priority 90） | 享受 prompt cache 稳定前缀 |
| 第二阶段注入位置 | env context（每轮重建） | 多 Skill 同激活、嵌套场景下 SOP 永远靠前；prompt cache 失效是设计意图 |
| LoadSkill 入参 | 仅 name | 与"意图识别"语义一致；参数走后续 user message 更自然 |
| LoadSkill 权限 | read-only + 系统工具 | 没有外部副作用；为支持嵌套必须豁免 allowed_tools |
| InstallSkill 权限 | 普通工具，受权限模式约束 | 写盘+网络，必须走授权 |
| fork 模式实现 | Java 端起子 Agent | 直接复用现成 `Agent.run`，不依赖将来 SubAgent 章节 |
| fork_context 默认 | none | "隔离"才是 fork 本意；需要带上下文的显式声明 |
| allowed_tools 在 inline 模式 | 仅 fail-fast + SOP 提示 | 避免 inline 期间动态切换工具集的生命周期复杂度；安全靠 ch08 权限引擎兜底 |
| Skill 与已有命令冲突 | 跳过加载 + warning | 保护内置命令的可靠性；Skill 想替换内置命令需要用户主动改源码 |
| 解析失败 | 跳过单个 Skill，warning，不阻断 | 与 instructions loader 一致的容错策略 |
| 热加载 | InstallSkill 后主动 reload；execute 时重读 body | 用户改 SKILL.md 下次执行立即生效；新装 Skill 不需要重启 |
| Skill 列表数据流 | adapter 桥接，prompt 包不依赖 skills 包 | 避免循环依赖 |
| UI 接口扩展 | 4 个新方法 + NopUI 全量实现 | 与 ch10 风格一致 |
| 闭包变量捕获 | 显式 `final String name = skill.name();` 拷贝再用 | Java lambda 仅能捕获 effectively final 变量，显式拷贝可读性更佳 |
| Skill 自身参数 | 本期 /<name> 仅零参数；后续轮次对话补 | 与 ch10 F7 一致，不破坏 dispatcher |
| 专属工具 exec | `ProcessBuilder` + 30 秒超时（`Process.waitFor(30, TimeUnit.SECONDS)`） | 与现有 bash 工具一致；零外部依赖 |
| zip 下载 | JDK `java.net.http.HttpClient` + `java.util.zip.ZipInputStream` | 标准库；无需第三方依赖 |
| YAML / JSON 解析 | SnakeYAML Engine（已用）+ Jackson `ObjectMapper`（tool.json） | 项目既有依赖，避免引新栈 |
````

````markdown
# Skill 技能包系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/main/java/dev/gcode/skills/SkillMeta.java` | record SkillMeta |
| 新建 | `src/main/java/dev/gcode/skills/SkillSource.java` | enum BUILTIN / USER / PROJECT |
| 新建 | `src/main/java/dev/gcode/skills/Skill.java` | Skill 类（promptBody 可变） |
| 新建 | `src/main/java/dev/gcode/skills/ToolSpec.java` | record ToolSpec |
| 新建 | `src/main/java/dev/gcode/skills/ActiveEntry.java` | record ActiveEntry |
| 新建 | `src/main/java/dev/gcode/skills/SkillParser.java` | parseSkillDir / parseFrontmatter / parseToolJson |
| 新建 | `src/test/java/dev/gcode/skills/SkillParserTest.java` | 解析路径单测 |
| 新建 | `src/main/java/dev/gcode/skills/Catalog.java` | load / reload / get / list / names / validateTools |
| 新建 | `src/test/java/dev/gcode/skills/CatalogTest.java` | 三层覆盖单测 |
| 新建 | `src/main/java/dev/gcode/skills/ActiveSkills.java` | ActiveSkills 列表 |
| 新建 | `src/main/java/dev/gcode/skills/Render.java` | renderBody（$ARGUMENTS + allowed_tools 提示） |
| 新建 | `src/main/java/dev/gcode/skills/Adapter.java` | toPromptItems / toPromptEntries |
| 新建 | `src/main/java/dev/gcode/skills/Install.java` | installFromUrl + zip-slip 防护 |
| 新建 | `src/test/java/dev/gcode/skills/InstallTest.java` | zip-slip / 正常 zip 解压单测 |
| 新建 | `src/main/java/dev/gcode/skills/Executor.java` | execute（inline / fork 分支） |
| 新建 | `src/main/resources/skills/builtin/commit/SKILL.md` | 内置 commit Skill |
| 新建 | `src/main/resources/skills/builtin/review/SKILL.md` | 内置 review Skill |
| 新建 | `src/main/resources/skills/builtin/test/SKILL.md` | 内置 test Skill |
| 修改 | `src/main/java/dev/gcode/tool/ToolRegistry.java` | isSystem 标记 + definitionsFiltered + registerSkillTool |
| 新建 | `src/main/java/dev/gcode/tool/SkillTool.java` | ToolSpec 适配为 Tool（exec command） |
| 新建 | `src/main/java/dev/gcode/tool/LoadSkillTool.java` | LoadSkill 工具实现 |
| 新建 | `src/main/java/dev/gcode/tool/InstallSkillTool.java` | InstallSkill 工具实现 |
| 修改 | `src/main/java/dev/gcode/prompt/Modules.java` | active-skills → skills-catalog 槽位 |
| 修改 | `src/main/java/dev/gcode/prompt/Prompt.java` | buildSystemPrompt 增 catalog 参数 |
| 新建 | `src/main/java/dev/gcode/prompt/SkillsBlock.java` | renderSkillsCatalog / renderActiveSkillsBlock + 桥接类型 |
| 修改 | `src/test/java/dev/gcode/prompt/PromptTest.java` | 同步 buildSystemPrompt 签名变更 |
| 修改 | `src/main/java/dev/gcode/command/UI.java` | UI 接口新增 4 方法 + NopUI 实现 |
| 修改 | `src/main/java/dev/gcode/command/Builtins.java` | 删 /review、改 handleClear、加 /skill 注册 |
| 新建 | `src/main/java/dev/gcode/command/BuiltinSkill.java` | handleSkill（KindLocal 列表输出） |
| 新建 | `src/main/java/dev/gcode/command/Skills.java` | registerSkillsAsCommands / removeSkillCommands |
| 修改 | `src/main/java/dev/gcode/command/Registry.java` | 按命令标记筛选移除入口 |
| 修改 | `src/main/java/dev/gcode/agent/SessionRuntime.java` | activeSkills 字段 |
| 修改 | `src/main/java/dev/gcode/agent/Agent.java` | catalog 选项 + run 拼装 sys/env + activateSkill/clearActiveSkills |
| 修改 | `src/main/java/dev/gcode/tui/TuiApp.java` | Model 持有 catalog/executor + 4 个 UI 方法实现 |
| 修改 | `src/main/java/dev/gcode/Main.java` | 启动期接线 |

## T1: skills 包数据结构**文件**：`SkillMeta.java` / `SkillSource.java` / `Skill.java` / `ToolSpec.java` / `ActiveEntry.java`
**依赖**：无
**步骤**：
1. 定义 `enum SkillSource { BUILTIN, USER, PROJECT }`，`toString()` 返回 lowercase（`"builtin"`/`"user"`/`"project"`）
2. 定义 `record SkillMeta(String name, String description, List<String> allowedTools, String mode, String forkContext, String model)`，加 `default boolean isFork() { return "fork".equals(mode); }`
3. 定义 `record ToolSpec(String name, String description, String inputSchemaJson, List<String> command, Path baseDir)`
4. 定义 `final class Skill { final SkillMeta meta; volatile String promptBody; final Path sourceDir; final SkillSource source; final List<ToolSpec> toolSpecs; ... 构造 + getter }`（`promptBody` 用 `volatile` 因为执行时被重读覆盖）
5. 定义 `record ActiveEntry(String name, String body)`

**验证**：`mvn -q compile` 编译通过。

## T2: SKILL.md 与 tool.json 解析**文件**：`SkillParser.java`
**依赖**：T1，需要 SnakeYAML Engine（已在 pom.xml）与 Jackson（如未在 pom，需要加 `com.fasterxml.jackson.core:jackson-databind`）
**步骤**：
1. `static Skill parseSkillDir(Path dir, SkillSource source) throws SkillParseException`：
   - 读 `<dir>/SKILL.md`（`Files.readString`），找不到抛 `SkillParseException("no SKILL.md in " + dir)`
   - 调 `parseFrontmatterAndBody(data)` → `record FrontmatterResult(SkillMeta meta, String body)`
   - 校验 meta.name 满足正则 `^[a-z][a-z0-9-]*$` 且长度 1-32
   - 校验 meta.description 非空
   - 校验 meta.mode 为 null/"inline"/"fork"；其它值改 inline 并打 warning（`System.err.println(...)`）
   - 校验 meta.forkContext 为 null/"none"/"recent"/"full"
   - 读 `<dir>/tool.json`（不存在则跳过），调 `parseToolJson` 解析 → `List<ToolSpec>`，`baseDir = dir.toAbsolutePath()`
   - 返回 `new Skill(meta, body, dir.toAbsolutePath(), source, toolSpecs)`
2. `static FrontmatterResult parseFrontmatterAndBody(String data)`：
   - 校验起始是 `---\n`
   - 找下一个 `---\n`，frontmatter = 两者之间，body = 之后
   - SnakeYAML Engine `Load.loadFromString(frontmatter)` → `Map<String,Object>`
   - 手动从 Map 提取字段（注意 `allowed_tools` 是下划线键 → `allowedTools`）→ 构造 `SkillMeta`
3. `static List<ToolSpec> parseToolJson(String data, Path baseDir)`：
   - Jackson `ObjectMapper.readTree(data)` 取 `tools` 字段（`{"tools": [...]}`）
   - 遍历每条，取 `name` / `description` / `input_schema`（保存为原始 JSON 字符串）/ `command`（List<String>）
   - 校验每条 name 满足命名规则、command 非空
   - 返回 `List<ToolSpec>`

**验证**：`mvn -q compile` 通过。

## T3: 解析单测**文件**：`SkillParserTest.java`
**依赖**：T2
**步骤**：
1. `testParseSkillDir_Minimal`：在 `@TempDir Path tmp` 下写一个最简 SKILL.md（name+description），断言解析成功
2. `testParseSkillDir_InvalidName`：name 含大写字母，期望抛 `SkillParseException`
3. `testParseSkillDir_WithToolJson`：含合法 tool.json，断言 toolSpecs 解析到位（name/command/baseDir）
4. `testParseSkillDir_NoSkillMD`：缺 SKILL.md 期望抛 `SkillParseException`

**验证**：`mvn -Dtest=SkillParserTest test` 通过。

## T4: Catalog 三层加载与覆盖**文件**：`Catalog.java`
**依赖**：T1, T2
**步骤**：
1. 定义 `class Catalog { ReadWriteLock lock; Map<String, Skill> byName; List<String> order; }`
2. `Catalog()` 构造空
3. `void register(Skill s)`：写锁覆盖、维护 `order` 不重复（覆盖时 order 不变；新增时按 name 字典序插入或追加后 `Collections.sort`）
4. `Optional<Skill> get(String name)`：读锁
5. `List<Skill> list()`：读锁，按 order 输出
6. `List<String> names()`：读锁
7. `static Catalog load(Path workDir)`：
   - 新 catalog
   - `loadBuiltinInto(catalog)` → 通过 classpath 资源加载（T5 完成 builtin 后接入；本任务先留 TODO 桩跳过 builtin）
   - `loadDirInto(catalog, Paths.get(System.getProperty("user.home"), ".gcode/skills"), USER)`
   - `loadDirInto(catalog, workDir.resolve(".gcode/skills"), PROJECT)`
8. `static void loadDirInto(Catalog c, Path baseDir, SkillSource source)`：
   - baseDir 不存在静默跳过（`Files.exists` 检查）
   - 用 `Files.list(baseDir)` 遍历直接子目录，每个调 `SkillParser.parseSkillDir` 后 `c.register`；解析失败打 warning 跳过
9. `void reload(Path workDir)`：构造新 catalog（局部变量），加锁原子替换内部 byName/order
10. `record ValidationIssue(String skillName, String toolName) {}`
11. `List<ValidationIssue> validateTools(ToolRegistry registry)`：遍历所有 skill 的 allowedTools，逐项查 `registry.get(name)`；未找到记录并返回。**注意**：把 `load_skill` 与 `install_skill` 视为允许引用（与系统工具豁免逻辑一致）

**验证**：`mvn -q compile` 通过；先不要在 load 中接入 builtin。

## T5: 内置三个 Skill 的资源文件与 classpath 加载**文件**：
- `src/main/resources/skills/builtin/commit/SKILL.md`
- `src/main/resources/skills/builtin/review/SKILL.md`
- `src/main/resources/skills/builtin/test/SKILL.md`
- `src/main/java/dev/gcode/skills/BuiltinLoader.java`

**依赖**：T4
**步骤**：
1. 写三个 SKILL.md，frontmatter 内容：
   - commit: name=commit, description=分析 git diff 并生成规范的 commit, allowed_tools=[bash, read_file, grep], mode=inline
   - review: name=review, description=客观审查代码变更与潜在问题, allowed_tools=[read_file, grep, glob, bash], mode=fork, fork_context=none
   - test: name=test, description=运行项目测试并分析失败原因, allowed_tools=[bash, read_file, grep, glob], mode=inline
   正文按 README 描述的 SOP 写：步骤、注意事项、`$ARGUMENTS` 占位符
2. 新建 `BuiltinLoader.java`：
   ```java
   public static void loadBuiltinInto(Catalog c) throws IOException {
       Path cacheRoot = Path.of(System.getProperty("user.home"), ".cache/gcode/builtin-skills");
       Files.createDirectories(cacheRoot);
       for (String name : List.of("commit", "review", "test")) {
           Path skillDir = cacheRoot.resolve(name);
           Files.createDirectories(skillDir);
           try (InputStream in = BuiltinLoader.class.getResourceAsStream(
                   "/skills/builtin/" + name + "/SKILL.md")) {
               if (in == null) continue;
               Files.copy(in, skillDir.resolve("SKILL.md"), StandardCopyOption.REPLACE_EXISTING);
           }
           try {
               c.register(SkillParser.parseSkillDir(skillDir, SkillSource.BUILTIN));
           } catch (Exception e) {
               System.err.println("builtin skill " + name + " load failed: " + e.getMessage());
           }
       }
   }
   ```
3. 在 `Catalog.load` 中调 `BuiltinLoader.loadBuiltinInto`

**验证**：
- `mvn -q compile` 通过
- 写个临时 `main`：`Catalog c = Catalog.load(Path.of(System.getProperty("java.io.tmpdir"))); System.out.println(c.names());` 输出 `[commit, review, test]` （字典序）

## T6: Catalog 单测**文件**：`CatalogTest.java`
**依赖**：T4, T5
**步骤**：
1. `testLoadCatalog_BuiltinOnly`：用 `@TempDir Path tmp` 当 workDir 跑 `Catalog.load(tmp)`，期望 `names()` 等于 `[commit, review, test]`
2. `testLoadCatalog_UserOverride`：用 `System.setProperty("user.home", tmpHome.toString())` 在测试中临时覆盖 HOME，放一个 commit 目录，期望该目录的 description 覆盖 builtin（测后恢复 user.home）
3. `testLoadCatalog_ProjectOverride`：在 `tmp/.gcode/skills` 放一个 commit 目录，期望覆盖 user
4. `testValidateTools_MissingTool`：定义一个 skill 用 `NotExist` 工具，期望返回 1 个 issue

**验证**：`mvn -Dtest=CatalogTest test` 通过。

## T7: ActiveSkills 列表**文件**：`ActiveSkills.java`
**依赖**：T1
**步骤**：
1. 定义 `final class ActiveSkills { Object lock; List<ActiveEntry> entries; Map<String,Integer> index; }`
2. 默认构造空
3. `void activate(String name, String body)`：`synchronized(lock)`；若 name 已在 index 中则更新对应 entry 的 body（保持位置不变）；否则追加并写入 index
4. `void clear()`：`synchronized(lock)` 清空两个字段
5. `List<ActiveEntry> snapshot()`：`synchronized(lock)` 拷贝（`new ArrayList<>(entries)`）
6. `List<String> names()`：`synchronized(lock)` 输出顺序快照

**验证**：写一个简单 JUnit 单测覆盖 activate/clear/snapshot 路径，`mvn test` 通过。

## T8: Render 渲染**文件**：`Render.java`
**依赖**：T1
**步骤**：
1. `static String renderBody(Skill s, String args)`：
   - `String body = s.promptBody();`
   - 若 `s.meta().allowedTools()` 非 null 且非空：在 body 前插入提示行（格式见 plan.md F27），用 `\n\n---\n\n` 分隔
   - 若 `body.contains("$ARGUMENTS")`：`body = body.replace("$ARGUMENTS", args)`
   - 否则若 `args != null && !args.isBlank()`：`body += "\n\n## User Request\n\n" + args`
   - 返回 body
2. 单测 `RenderTest`：覆盖 4 种组合（有/无 placeholder × 有/无 args）

**验证**：`mvn -Dtest=RenderTest test` 通过。

## T9: prompt 包适配器**文件**：`Adapter.java`
**依赖**：T4, T7
**步骤**：
1. 在 skills 包定义 `record PromptItem(String name, String description) {}` 与 `record PromptEntry(String name, String body) {}`（避免反向依赖 prompt 包）
2. 在 `Catalog` 加 `List<PromptItem> toPromptItems()`：按 order 输出
3. 在 `ActiveSkills` 加 `List<PromptEntry> toPromptEntries()`：按 snapshot 顺序输出

**验证**：`mvn -q compile` 通过。

## T10: prompt 模块槽位重命名**文件**：`Modules.java`
**依赖**：无
**步骤**：
1. 把 `PRIO_ACTIVE_SKILLS = 90` 重命名为 `PRIO_SKILLS_CATALOG = 90`
2. `optionalModules(String instructions, String memory)` 改签名为 `optionalModules(String instructions, String memory, String skillsCatalog)`
3. 模块名由 `"active-skills"` 改为 `"skills-catalog"`，content 取 `skillsCatalog` 参数

**验证**：`mvn -q compile`——错误应只出现在 `Prompt.java` 上（它还用着旧签名），下一任务修复。

## T11: prompt 新增 Skill 渲染函数**文件**：`SkillsBlock.java`
**依赖**：T10
**步骤**：
1. 定义 `record SkillCatalogItem(String name, String description) {}` 与 `record ActiveSkillEntry(String name, String body) {}`
2. `static String renderSkillsCatalog(List<SkillCatalogItem> items)`：items 空返回 `""`；否则输出：
   ```
   ## Available Skills

   - <name>: <description>
   ...

   Call the LoadSkill tool with {"name": "<skill_name>"} to activate a skill's full SOP and specialized tools before executing it.
   ```
3. `static String renderActiveSkillsBlock(List<ActiveSkillEntry> entries)`：entries 空返回 `""`；否则输出：
   ```
   ## Active Skills

   ### Skill: <name>

   <body>

   ### Skill: <name>

   <body>
   ```

**验证**：`mvn -q compile` 通过 `SkillsBlock.java`；`Prompt.java` 仍待修。

## T12: buildSystemPrompt 签名更新**文件**：`Prompt.java`
**依赖**：T10, T11
**步骤**：
1. `buildSystemPrompt(String instructions, String memory)` 改为 `buildSystemPrompt(String instructions, String memory, String skillsCatalog)`
2. 内部把第三参数传给 `Modules.optionalModules`

**验证**：`mvn -q compile` 全包通过。

## T13: prompt 单测同步**文件**：`PromptTest.java`
**依赖**：T12
**步骤**：
1. 所有 `buildSystemPrompt(X, Y)` 调用替换为 `buildSystemPrompt(X, Y, "")`（或必要场景传入非空 catalog 文本，新增 1 个用例覆盖）
2. 新增 `testRenderSkillsCatalog_NonEmpty / _Empty` 与 `testRenderActiveSkillsBlock_NonEmpty / _Empty`

**验证**：`mvn -Dtest=PromptTest test` 全部通过。

## T14: ToolRegistry 系统工具支持**文件**：`ToolRegistry.java` + 6 个内置工具 + MCP 适配
**依赖**：无
**步骤**：
1. `Tool` 接口新增 `default boolean isSystem() { return false; }`；6 个内置工具与 MCP 适配器无需改动（沿用默认）
2. `ToolRegistry.definitionsFiltered(List<String> allowed): List<ToolDefinition>`：按 order 遍历，name 在 allowed 集合内 OR `tool.isSystem()` 为 true 时纳入
3. `ToolRegistry.registerSkillTool(Tool t)` —— 重复名静默覆盖（不维护 order 中重名）

**验证**：`mvn -q compile`，原 6 个工具与 mcp 适配编译通过。`mvn -Dtest=ToolRegistryTest test`（如已有）通过。

## T15: ToolSpec 适配为 Tool**文件**：`SkillTool.java`
**依赖**：T1, T14
**步骤**：
1. 定义 `final class SkillTool implements Tool`，构造接受 name / description / inputSchemaJson / command / baseDir
2. Name/Description/Parameters/readOnly(false)/isSystem(false)/execute
3. `execute(JsonNode args)`：
   - 把 args 序列化成 JSON 写入子进程 stdin（`process.getOutputStream()`）
   - `ProcessBuilder pb = new ProcessBuilder(command).directory(baseDir.toFile()).redirectErrorStream(true);`
   - `Process p = pb.start();` 写入 stdin → `p.waitFor(30, TimeUnit.SECONDS)`，超时调 `p.destroyForcibly()`
   - 读 stdout 全部字节当作结果文本；exit code 非 0 视为失败（结果文本前缀 `[exit %d]`）
4. 因 tool 包不应反向依赖 skills 包，工厂方法接收原始字段：`public static Tool fromSpec(String name, String desc, String schemaJson, List<String> command, Path baseDir)`

**验证**：写一个最小单测，模拟一个 `echo "ok"` 的 shell 脚本，断言 `execute` 返回 `"ok"`。

## T16: LoadSkill 工具**文件**：`LoadSkillTool.java`
**依赖**：T4, T7, T14, T15
**步骤**：
1. 定义 `final class LoadSkillTool implements Tool` 持有 `Catalog catalog`、`ActiveSkills active`、`ToolRegistry registry`
2. `name() = "load_skill"`；`description()` 写明用途
3. `parameters()` 返回 `{"type":"object","properties":{"name":{"type":"string","description":"Skill name to activate"}},"required":["name"]}`（字符串字面量或 Jackson 构造）
4. `readOnly() = true`（只动 Agent 自己状态，无外部副作用）；`isSystem() = true`
5. `execute(JsonNode args)`：
   - 取 `args.get("name").asText()`
   - `Optional<Skill> opt = catalog.get(name);` 空返回结构化错误 `unknown skill: <name>`
   - 从磁盘 `<skill.sourceDir>/SKILL.md` 重读，更新 body；失败回退到 `skill.promptBody()` 并打 warning
   - `active.activate(skill.meta().name(), freshBody)`
   - 注册 `skill.toolSpecs()`：`registry.registerSkillTool(SkillTool.fromSpec(...))`
   - 返回 `new Result("Skill " + name + " activated. SOP pinned to env context. " + n + " specialized tools registered.")`

**验证**：`mvn -q compile` 通过。

## T17: InstallSkill 工具**文件**：`InstallSkillTool.java`
**依赖**：T18（InstallSkillTool 是薄壳，调 Install）
**步骤**：
1. 定义 `final class InstallSkillTool implements Tool` 持有 `Catalog catalog`、`Path workDir`
2. `name() = "install_skill"`；`description()` 写明用途与限制
3. `parameters()`：`{"type":"object","properties":{"source":{"type":"string","description":"URL of a Skill zip"}},"required":["source"]}`
4. `readOnly() = false`；`isSystem() = false`（受权限模式约束）
5. `execute(JsonNode args)`：调 `Install.installFromUrl(ctx, source, catalog, workDir)`，返回成功消息 `Skill <name> installed to ~/.gcode/skills/<name>.`

**验证**：`mvn -q compile` 通过。本工具的功能在 T18 跑完后再做集成测试。

## T18: installFromUrl 与 zip-slip 防护**文件**：`Install.java`
**依赖**：T4
**步骤**：
1. `static String installFromUrl(CancelToken ctx, String source, Catalog catalog, Path workDir) throws IOException`：
   - `HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(60)).build();`
   - `HttpRequest req = HttpRequest.newBuilder(URI.create(source)).GET().build();`
   - `HttpResponse<InputStream> resp = client.send(req, BodyHandlers.ofInputStream());`
   - 读取流到临时文件，限制 50 MB（超出 close stream 报错）
   - `try (ZipFile zip = new ZipFile(tempFile.toFile())) { ... }`
   - 计算顶层目录名 = 所有条目共同前缀的第一段；校验满足 `^[a-z][a-z0-9-]*$`
   - 遍历条目：拒绝 `..`、`/` 开头、绝对路径（`Path.of(entry.getName()).isAbsolute()`）、symlinks（zip ExternalAttributes 中 unix-mode 含 symlink 位则拒绝）
   - 解压到 `~/.gcode/skills/<topDir>/`
   - 调 `catalog.reload(workDir)`
   - 返回 `topDir`
2. 单测 `testInstallFromUrl_ZipSlip`：构造恶意 zip 含 `../../bad`，期望抛 `IOException` 且 message 含 `"unsafe path"`
3. 单测 `testInstallFromUrl_Happy`：用 `com.sun.net.httpserver.HttpServer`（JDK 自带）起一个返回正常 zip 的 server，断言 `catalog.get(topDir).isPresent()` 在调用后成立

**验证**：`mvn -Dtest=InstallTest test` 通过。

## T19: Skill Executor (inline + fork)**文件**：`Executor.java`
**依赖**：T7, T8, T14
**步骤**：
1. 定义 `final class Executor { Catalog catalog; ActiveSkills active; ToolRegistry registry; Provider provider; PermissionEngine engine; String version; SessionRuntime runtime; }`
2. 构造函数注入所有依赖
3. `void execute(CancelToken ctx, UI ui, String name, String args)`：
   - `Optional<Skill> opt = catalog.get(name);` 为空 → `ui.error("skill not found: " + name)`，返回
   - 重读 SKILL.md 更新 body（失败回退）
   - `String rendered = Render.renderBody(skill, args);`
   - if `!skill.meta().isFork()`: `ui.injectAndSend("/" + name, rendered);` 返回
   - else (fork)：
     - 构造子 Conversation：按 forkContext (`"none"` / `"recent"` / `"full"`)
       - none: 仅 user 消息 = rendered
       - recent: 调 `ui.recentMessages(5)`（新增 UI 方法）拷贝再追加 user 消息
       - full: **本期决议**：与 recent 等价处理并 `System.err.println` warning 提示，留待 ch12+ 真正接入 compact 摘要管道
     - 选 provider：默认 `e.provider`；`skill.meta().model()` 非空时 `ProviderFactory.create(...)` 重新构造（Main 已有相同代码可复用）
     - 子 registry：通过 `agent.Agent.builder().filteredAllowedTools(skill.meta().allowedTools())` 选项让子 Agent 在选 defs 时调 `registry.definitionsFiltered`
     - 子 Conversation：`Conversation forkConv = new Conversation();` 填入构造好的初始消息
     - `Agent forkAgent = Agent.builder().provider(provider).registry(e.registry).version(e.version).engine(e.engine).runtime(forkRuntime).filteredAllowedTools(skill.meta().allowedTools()).build();`
     - 起一条 `forkAgent.run(ctx, forkConv, PermissionMode.DEFAULT)`，遍历 `Flow.Publisher<RunEvent>`；累积 usage、提取最终 assistant text；最大 25 轮兜底
     - usage 累加到主 runtime
     - `String finalText = ...`；若失败：`String.format("[skill %s failed: %s]", name, reason)`
     - `ui.appendAssistantMessage(finalText)`
4. 新增 `Agent.Builder.filteredAllowedTools(List<String> allowed)` 选项；在 `run` 的 defs 选取处，若 allowed 非空，调 `registry.definitionsFiltered(allowed)` 代替 `registry.definitions()`

**验证**：`mvn -q compile` 通过；后续端到端 tmux 跑通 /review。

## T20: command UI 接口扩展**文件**：`UI.java`
**依赖**：无（在 T19 前可独立完成）
**步骤**：
1. UI 接口新增 6 个方法：
   ```java
   List<SkillSummary> listCatalogSkills();
   List<String> listActiveSkills();
   void clearActiveSkills();
   void appendAssistantMessage(String text);
   List<Message> recentMessages(int n);  // fork forkContext=recent 用
   List<Message> allMessages();          // fork forkContext=full 用
   ```
2. 定义 `record SkillSummary(String name, String description, String source, String mode)`（放在 command 包，避免 skills 依赖 command）
3. `NopUI` 提供零值实现：`listCatalogSkills` → `List.of()`；`listActiveSkills` → `List.of()`；`clearActiveSkills` → 空实现；`appendAssistantMessage` → 空实现；`recentMessages` / `allMessages` → `List.of()`

**验证**：`mvn -q compile` 通过 command 包。

## T21: command/Builtins.java 改动**文件**：`Builtins.java`
**依赖**：T20
**步骤**：
1. 删除 `Command.builder().name("review")...` 整段注册块（与对应的 `handleReview` 函数文件——如有，标记 TODO 或一并清理）
2. 修改 `handleClear`：在 `ui.clearAndNewSession()` 之后追加一行 `ui.clearActiveSkills();`
3. 新增 register 块：
   ```java
   Command.builder().name("skill").description("列出已加载的 Skill")
          .kind(Kind.LOCAL).handler(BuiltinSkill::handleSkill).build()
   ```

**验证**：`mvn -q compile` 通过；如果有 review 单测，要么更新要么删除。

## T22: handleSkill 实现**文件**：`BuiltinSkill.java`
**依赖**：T20
**步骤**：
1. `static void handleSkill(CancelToken ctx, UI ui)`：
   - `List<SkillSummary> skills = ui.listCatalogSkills();`
   - 空时 `ui.println("No skills loaded.");`
   - 否则：
     - 先 `ui.println(String.format("Available skills (%d):", skills.size()));`
     - 按 name 字典序逐条 `ui.println(String.format("  /%-20s %s", s.name(), s.description()));`（每条独立 println 避免 noticeBlock 多行渲染产生空白）
     - 末尾 `ui.println("Type /<skill-name> to invoke a skill.");`
   - 不展示 source / mode 元信息——本期保持精简，开发者需要时直接读 SKILL.md

**验证**：`mvn test`（如果新增了相应单测）。

## T23: registerSkillsAsCommands**文件**：`Skills.java`
**依赖**：T20, T22
**步骤**：
1. 命令标记机制：在 `Command` record / 类新增字段 `boolean isSkill`（或单独维护 set，加字段最简）。修改 ch10 `Command.java` 增加该字段（默认 false）
2. 定义 `interface SkillRunner { void execute(CancelToken ctx, UI ui, String name, String args); }`
3. `static void registerSkillsAsCommands(Registry reg, List<SkillSummary> items, SkillRunner executor)`：
   - 遍历 items，每个 register 一条：
     ```java
     final String skillName = item.name();
     reg.register(Command.builder()
         .name(skillName)
         .description(item.description() + " [skill]")
         .kind(Kind.PROMPT)
         .isSkill(true)
         .handler((ctx, ui) -> executor.execute(ctx, ui, skillName, ""))
         .build());
     ```
4. `static void removeSkillCommands(Registry reg)`：遍历 reg 内部 map，删除 `isSkill == true` 的条目

注：Registry 内部存储要支持 range/delete 操作；可能需要扩展 ch10 的 Registry.java（T24）。

**验证**：`mvn -q compile` 通过。

## T24: command.Registry 删除 API**文件**：`Registry.java`
**依赖**：T23
**步骤**：
1. 检查 ch10 现有 Registry 是否暴露足够 API；如未提供按条件删除，新增：
   - `void removeIf(Predicate<Command> pred)`：按谓词删除（同时清 byName + byAlias + list 序）
2. 在 `Skills.removeSkillCommands` 中调 `reg.removeIf(Command::isSkill)`

**验证**：`mvn -Dtest=RegistryTest test` 通过。

## T25: SessionRuntime activeSkills 字段**文件**：`SessionRuntime.java`
**依赖**：T7
**步骤**：
1. SessionRuntime 增加字段 `ActiveSkills activeSkills`
2. 构造函数初始化 `this.activeSkills = new ActiveSkills();`
3. `resetForNewSession` 增加：`if (activeSkills != null) activeSkills.clear();`
4. 由于 agent 包反向引入 skills 包会有依赖循环（`skills.Executor` 依赖 `agent.SessionRuntime`）；解决方法：把 `ActiveSkills` 类型放到 agent 包下；或定义在 skills 包，agent 包 import 它（agent 已可以 import skills 包，没有循环——只要 skills 包不 import agent 包）。为简单起见，`Executor` 需要的 runtime 字段单独通过函数参数传递，不直接 import `agent.SessionRuntime`；让 `skills.Executor` 持有 `ActiveSkills` 而非 `SessionRuntime`

**重新设计**：
- skills 包不 import agent
- `agent.SessionRuntime` 持有 `ActiveSkills` 字段
- `skills.Executor` 通过 `ActiveSkills` 操作激活态（不直接持有 `SessionRuntime`）

**验证**：`mvn -q compile` 通过 agent 包。

## T26: Agent 拼装 sys / env 改动**文件**：`Agent.java`
**依赖**：T9, T12, T25
**步骤**：
1. 新增 `Builder.catalog(Catalog c)`：设置 `agent.catalog`
2. 新增 `Builder.filteredAllowedTools(List<String> allowed)`：设置 `agent.allowedTools`
3. Agent 增加字段：`Catalog catalog`、`List<String> allowedTools`
4. 新增方法 `activateSkill(String name, String body)`，调 `runtime.activeSkills().activate(...)`
5. 新增方法 `clearActiveSkills()`
6. `run` 内每轮重建：
   ```java
   String catalogText = "";
   if (catalog != null) {
       List<SkillCatalogItem> items = catalog.toPromptItems().stream()
           .map(it -> new SkillCatalogItem(it.name(), it.description()))
           .toList();
       catalogText = Prompt.renderSkillsCatalog(items);
   }
   String sys = Prompt.buildSystemPrompt(instructionText, memoryText, catalogText);

   String envBase = Environment.gather(...).render();
   String envSkills = "";
   if (runtime != null && runtime.activeSkills() != null) {
       List<ActiveSkillEntry> entries = runtime.activeSkills().toPromptEntries().stream()
           .map(e -> new ActiveSkillEntry(e.name(), e.body()))
           .toList();
       envSkills = Prompt.renderActiveSkillsBlock(entries);
   }
   String envText = envBase;
   if (!envSkills.isEmpty()) envText += "\n\n" + envSkills;
   ```
7. defs 选择：
   ```java
   List<ToolDefinition> defs = registry.definitions();
   if (mode == PermissionMode.PLAN) defs = registry.readOnlyDefinitions();
   if (allowedTools != null && !allowedTools.isEmpty())
       defs = registry.definitionsFiltered(allowedTools);
   ```

**验证**：`mvn -q compile` 通过；既有单测通过（`mvn -Dtest=AgentRuntimeTest test`）。

## T27: TUI Model 与 UI 实现**文件**：`TuiApp.java` + 相关
**依赖**：T20, T25
**步骤**：
1. Model 持有 `Catalog catalog`、`Executor executor`
2. `TuiApp.builder()` 接受 catalog/executor 参数
3. 实现 UI 接口的 6 个新方法：
   - `listCatalogSkills()`：从 catalog 转换
   - `listActiveSkills()`：从 `runtime.activeSkills().names()`
   - `clearActiveSkills()`：`runtime.activeSkills().clear()`
   - `appendAssistantMessage(text)`：追加到当前 conversation 与会话存档
   - `recentMessages(n)` / `allMessages()`：从当前 conversation 取
4. 注意：`UI.injectAndSend` 已有，不重写

**验证**：`mvn -q compile` 通过 tui 包；既有 tui 单测通过。

## T28: Main.java 接线**文件**：`Main.java`
**依赖**：T1-T27
**步骤**：
1. import skills 包
2. 构造 `Catalog catalog = Catalog.load(workDir);`
3. 构造 `ActiveSkills activeSkills` 后 attach 到 `SessionRuntime`
4. 注册 `LoadSkillTool` / `InstallSkillTool` 到 `ToolRegistry`
5. 调 `List<ValidationIssue> issues = catalog.validateTools(toolReg);`；遍历 issues 打 stderr 并把不合格 skill 从 catalog 移除
6. 构造 `Executor executor = new Executor(catalog, activeSkills, toolReg, provider, eng, version, ...);`
7. 调 `Commands.registerBuiltins(cmdReg)`（已有，删 /review 后内置 11 条）
8. 调 `Skills.registerSkillsAsCommands(cmdReg, catalog 转换的 summary, executor)`
9. `TuiApp.builder()` 传 catalog/executor
10. Agent builder 附 `.catalog(catalog)`

**验证**：`mvn -q -DskipTests package` 全包编译通过；`mvn spotless:check` 无新增警告。

## T29: 启动冒烟**文件**：无
**依赖**：T28
**步骤**：
1. 在 tmux 内：`mvn -q -DskipTests package && java -jar target/gcode-*.jar`，期望启动 banner 正常、状态栏正常
2. 键入 `/help`，期望输出含 `/skill` 行、不含独立 `/review` 行、含 `/commit [skill]` `/review [skill]` `/test [skill]` 三行
3. 键入 `/skill`，期望输出三行（commit/review/test，source=builtin）
4. ctrl+c 退出

**验证**：观察输出符合上述期望；任何 panic / 未捕获异常或缺失都修正后重测。

## T30: 端到端验证场景

按 checklist.md 中端到端场景章节，在 tmux 里实跑全套流程。

## 执行顺序

```
T1 → T2 → T3
  → T4 (依赖 T1,T2) → T5 (依赖 T4) → T6 (依赖 T4,T5)
  → T7 (依赖 T1) → T8 (依赖 T1) → T9 (依赖 T4,T7)

T10 → T11 (依赖 T10) → T12 (依赖 T10,T11) → T13 (依赖 T12)

T14 → T15 (依赖 T1,T14) → T16 (依赖 T4,T7,T14,T15) → T17 (依赖 T18)
T18 (依赖 T4)

T20 → T21 (依赖 T20) → T22 (依赖 T20) → T23 (依赖 T20,T22) → T24 (依赖 T23)

T25 (依赖 T7) → T26 (依赖 T9,T12,T25) → T27 (依赖 T20,T25)

T19 (依赖 T7,T8,T14) → T28 (依赖 T1-T27)

T29 (依赖 T28) → T30
```

可并行：T1-T9 内部链；T10-T13 链；T14-T18 链；T20-T24 链 —— 这四条链彼此独立直到 T25 起开始合流。但本期由单一会话顺序执行，避免合并冲突。
````

````markdown
# Skill 技能包系统 Checklist

> 每一项通过运行代码或观察行为来验证。最后一节"端到端场景（tmux 实跑）"必须在 tmux 内实际跑过。

## 实现完整性

- [ ] `dev.gcode.skills` 包编译通过（验证：`mvn -q compile`）
- [ ] `dev.gcode.tool.LoadSkillTool` 与 `dev.gcode.tool.InstallSkillTool` 编译通过（验证：`mvn -q compile`）
- [ ] `dev.gcode.prompt` 改造后编译通过且单测通过（验证：`mvn -Dtest=PromptTest test`）
- [ ] `dev.gcode.command` 改造后编译通过且单测通过（验证：`mvn -Dtest='dev.gcode.command.*' test`）
- [ ] `dev.gcode.agent` 改造后编译通过且单测通过（验证：`mvn -Dtest='dev.gcode.agent.*' test`）
- [ ] 全项目构建通过（验证：`mvn -q -DskipTests package`）
- [ ] `mvn spotless:check` 无新增警告（如启用 google-java-format）
- [ ] 内置三个 Skill（commit / review / test）的 SKILL.md 通过 frontmatter 与 body 双重校验（验证：启动后 `/skill` 输出三行）

## Skill 定义与解析

- [ ] 一个最简的合法 SKILL.md（仅 name + description）能被 parser 解析成功（验证：`SkillParserTest.testParseSkillDir_Minimal` 通过）
- [ ] 非法 name（大写、空格、超长）被 parser 拒绝（验证：`SkillParserTest.testParseSkillDir_InvalidName` 通过）
- [ ] tool.json 合法时解析为 `ToolSpec` 列表（验证：`SkillParserTest.testParseSkillDir_WithToolJson` 通过）
- [ ] 缺 SKILL.md 时抛 `SkillParseException`（验证：`SkillParserTest.testParseSkillDir_NoSkillMD` 通过）

## Catalog 加载

- [ ] 空 workDir + 空 HOME 启动时 Catalog 仅含三个内置 Skill（验证：`CatalogTest.testLoadCatalog_BuiltinOnly` 通过）
- [ ] 用户目录下同名 Skill 覆盖内置（验证：`testLoadCatalog_UserOverride` 通过）
- [ ] 项目目录下同名 Skill 覆盖用户（验证：`testLoadCatalog_ProjectOverride` 通过）
- [ ] 单个 Skill 解析失败（损坏 SKILL.md）只跳过它本身，其它 Skill 仍能加载（验证：写一个临时 user 目录含损坏 + 合法两个 Skill，启动后只看到合法那一个）
- [ ] Skill 名字与 ch10 已有命令冲突时跳过加载（验证：临时建一个 name=help 的 Skill 放 user 目录，启动 stderr 打 warning 且 `/help` 仍为内置命令）

## fail-fast 依赖检查

- [ ] Skill 的 allowed_tools 引用不存在的工具时，启动 stderr 输出对应错误并把该 Skill 从 Catalog 中剔除（验证：建一个含 `allowed_tools: [NotExist]` 的 Skill，启动 stderr 含 `allowed_tool "NotExist" not registered`，`/skill` 中不出现该 Skill）
- [ ] `load_skill` / `install_skill` 在 fail-fast 检查中被视为允许引用（验证：建一个 `allowed_tools: [load_skill]` 的 Skill，启动正常加载，不报错）

## Slash Command 自动注册

- [ ] 启动后 `/help` 包含 `/commit [skill]`、`/review [skill]`、`/test [skill]` 三行且不再有独立 `/review`（验证：tmux 启动后键入 `/help`）
- [ ] `/help` 包含 `/skill` 一行（验证：同上）
- [ ] 用 Tab 补全输入 `/comm`，菜单展示 `/commit [skill]` 候选（验证：tmux 实跑）

## 两阶段加载

- [ ] System prompt 中含 `## Available Skills` 区块，列出全部 Catalog Skill 的 `- name: description`（验证：在 `agent.run` 前打日志或加一个 dump-prompt 测试用例）
- [ ] 未激活任何 Skill 时 env context 不含 `## Active Skills` 区块（验证：单测 `renderActiveSkillsBlock(List.of()).isEmpty()`）
- [ ] 激活一个 Skill 后下一轮 env context 含 `## Active Skills` 区块包含该 Skill 的 body（验证：单测覆盖 `renderActiveSkillsBlock`；端到端见 tmux 场景）

## LoadSkill 工具

- [ ] 调用 `LoadSkill({name:"commit"})` 后 `active.names()` 包含 `"commit"`（验证：单测）
- [ ] 调用 LoadSkill 不存在的 name 时返回 `unknown skill: <name>`，对话不中断（验证：tmux 实跑触发）
- [ ] LoadSkill 调用时即便 allowed_tools 是空白名单也可见（验证：单测 `ToolRegistry.definitionsFiltered(List.of(), 系统工具)` 输出包含 `load_skill`）
- [ ] LoadSkill 在 Plan Mode 下可调用，不被权限拦截（验证：tmux 实跑 `/plan` 后让 LLM 触发 LoadSkill）

## /clear

- [ ] `/clear` 之后 `active.names()` 为空（验证：tmux 实跑：先触发 LoadSkill 激活某 Skill，再 `/clear`，下一轮观察 env context 无 Active Skills 块）
- [ ] `/clear` 之后新会话可在 `/resume` 列表中看到旧会话条目（验证：与 ch10 N9 一致，回归现有行为）

## Skill 执行器

- [ ] inline Skill 执行后主对话历史新增一条 user 消息（验证：tmux 触发 `/commit` 后 `/session` 显示路径，查看会话 JSONL）
- [ ] inline Skill 的 SOP 顶部含 `This skill is designed to use only these tools: ...` 提示（验证：单测覆盖 `Render.renderBody`）
- [ ] fork Skill 跑完后主对话新增一条 assistant 消息（验证：tmux 触发 `/review` 后会话 JSONL 末尾是 assistant 角色消息）
- [ ] fork Skill 失败（如子 Agent 报错或超时）时返回的 assistant 消息为 `[skill <name> failed: ...]` 文本（验证：mock provider 出错的执行器单测）

## tool.json 专属工具

- [ ] 一个含 tool.json 的 Skill 被 LoadSkill 激活后，主工具注册中心新增对应的工具名（验证：tmux 实跑：放一个测试 Skill 含 echo 的 tool.json，激活后让 LLM 调那个工具，观察输出）
- [ ] 专属工具 exec 超时 30 秒（验证：`SkillToolTest`：脚本 sleep 100 时 `process.waitFor(30, SECONDS)` 返回 false，调 `destroyForcibly` 后返回超时错误）
- [ ] 专属工具 exit code 非 0 视为失败，stderr 内容并入 Result 文本（验证：单测，`redirectErrorStream(true)` 合并 stderr）

## InstallSkill

- [ ] 合法 zip 安装后 `~/.gcode/skills/<topDir>/` 出现 SKILL.md（验证：单测 + tmux 实跑）
- [ ] 合法 zip 安装后 `/skill` 立即列出新 Skill 且 `/<name>` 可调用（验证：端到端）
- [ ] zip-slip（含 `..` 路径）被拒绝，`~/.gcode/skills/` 无副作用（验证：单测 `testInstallFromUrl_ZipSlip`）
- [ ] zip 内顶层目录命名违规时拒绝（验证：单测）
- [ ] InstallSkill 工具在 Plan Mode 下被权限引擎拦截，需要切回默认模式才能装（验证：tmux 实跑 `/plan` → 自然语言让 Agent 装 Skill → 看到权限被拦截）

## /skill 命令

- [ ] `/skill` 首行输出 `Available skills (N):`，随后每条一行 `  /<name>  <description>`（按字典序、固定列宽对齐），末行输出 `Type /<skill-name> to invoke a skill.`（验证：tmux 实跑）
- [ ] Catalog 为空时 `/skill` 输出 `No skills loaded.`（验证：清空内置 Skill 资源后启动）

## 编译与测试

- [ ] `mvn -q -DskipTests package` 通过
- [ ] `mvn test` 通过（含新增的 skills/parser/catalog/install/render/active/executor 单测）
- [ ] `mvn spotless:check` 通过
- [ ] 代码风格符合 google-java-format（统一通过 Spotless 强制）

## 端到端场景（tmux 实跑）

> 在 tmux 内启动 gcode，按下面流程一步步操作；每步附"观察"项。

**前置**：
- 用 `tmux new -s mew-ch11 -x 200 -y 50` 起一个固定大小的 tmux session
- `cd /Users/codemelo/gcode && mvn -q -DskipTests package && java -jar target/gcode-*.jar`

**步骤**：

1. **启动与就绪**
   - 操作：进程启动
   - 观察：banner 正常显示；状态栏底部含 "Type a message and press Enter..."；进程不抛未捕获异常；stderr 无 "skipped" 类错误（如果用户/项目目录干净）

2. **`/help`**
   - 操作：键入 `/help` 回车
   - 观察：输出含 11 条 ch10 命令（已无独立 `/review`）+ `/skill` + `/commit [skill]` + `/review [skill]` + `/test [skill]`，共 15 行

3. **`/skill`**
   - 操作：键入 `/skill` 回车
   - 观察：首行 `Available skills (3):`，随后三行 `  /commit ...` / `  /review ...` / `  /test ...`，末行 `Type /<skill-name> to invoke a skill.`

4. **显式调用 inline Skill `/commit`**
   - 操作：键入 `/commit` 回车
   - 观察：状态栏立即进入流式；AI 开始按 commit SOP 走（应该会调 git status / diff）；本步骤是真实操作，按 q/esc 可中断；目的是验证 inline 路径联通

5. **显式调用 fork Skill `/review`**
   - 操作：在主对话先随便说一句 "I just edited some files."（让主对话有上下文），然后键入 `/review`
   - 观察：状态栏进入流式；AI 输出审查报告；最后主对话新增一条 assistant 消息（含审查结果）；ForkContext=none 意味着子 Agent 看不到 "I just edited..." 那条 user 消息

6. **意图触发 LoadSkill**
   - 操作：键入自然语言 "我想做后端面试准备"（或类似能匹配 backend-interview-like description 的 Skill；如果当前 Catalog 只有 commit/review/test，需要先放一个 user-level Skill，name=backend-interview）
   - 观察：LLM 调用 LoadSkill 工具，工具结果为 "Skill backend-interview activated..."；下一轮起 env context 中出现该 Skill 的 SOP body

7. **`/clear` 清空激活**
   - 操作：键入 `/clear` 回车
   - 观察：对话区清空、session 新建；接着说一句任意话题，env context 中不再含上一轮激活的 SOP（可通过让 Agent 复述"现在你激活了什么 Skill"间接验证，或开启 debug 日志）

8. **InstallSkill 安装第三方 Skill**
   - 操作：用 `python3 -m http.server` 在本地 8080 端口托管一个写好的 `test-skill.zip`（含 `myskill/SKILL.md`），切到 gcode 输入 "把这个 skill 装下：http://localhost:8080/test-skill.zip"
   - 观察：Agent 调 `install_skill` 工具；安装成功后 `/skill` 列表立即出现 myskill；`/myskill` 可调用

9. **`/clear` → 新会话不残留**
   - 操作：先激活 myskill，再 `/clear`，再 `/skill`
   - 观察：`/skill` 仍能看到 myskill（Catalog 与 Active 列表是两个概念，Catalog 不清）；env context 已无 Active Skills 块

10. **退出**
    - 操作：`/exit` 回车
    - 观察：进程优雅退出，screen 还原终端、无错误日志

## 验收报告模板

```
## 验收报告

### 通过
- [x] 实现完整性 — 全包构建通过：mvn -q -DskipTests package 输出 ...
- [x] /help 列表正确：含 /skill, /commit [skill] ...
- [x] /skill 输出三行内置 Skill ...

### 未通过
- [ ] 第 X 项 — 预期：...，实际：...，修复方案：...

### 端到端
- [x] 启动与就绪 — 结果：banner 正常
- [x] /help — 结果：15 行命令
- [x] /skill — 结果：commit/review/test 三行
- ...（按上面 10 步逐条列出）
```
````

### TypeScript

```markdown
# Skill 技能包系统 Spec## 背景

ch10 给 gcode 装上了 Slash Command 注册中心和一组内置命令，其中 `/review` 是 prompt 类型——把硬编码在源码里的代码审查 prompt 注入对话并触发大模型。这种"写死在源码里"的 prompt 暴露出几个问题：

- 调整 prompt 必须重新打包再发布，用户没办法在不动源码的前提下定制
- 只有开发者能新增 prompt 类命令，普通用户无法贡献
- prompt 命令拿到的工具集与普通对话完全一致，没法在执行 SOP 时收窄注意力或限制权限
- prompt 是孤零零的字符串，无法捎带专属资料或辅助脚本

与此同时，gcode 接入 MCP 之后工具数量从 6 个膨胀到二十多个，模型选错工具的概率随之上升，需要一种机制把"完成某类任务时只看哪些工具"的范围收窄。

Skill 技能包系统在 ch10 命令体系之上解决这两个问题：把可复用的 AI 操作搬出源码、放进可编辑的 Markdown 文件；通过两阶段加载与工具白名单把每次任务的注意力收窄到最小工具子集。

## 目标- **G1**：让可复用的 AI 操作变成独立的 Markdown 文件，增/删/改一个 Skill 不需要重新构建 gcode
- **G2**：自动把已加载的 Skill 注册成 `/<name>` 形式的 Slash Command，沿用 ch10 prompt 命令体系并新增一种"派生子 Agent"的命令类型
- **G3**：实现两阶段加载——启动期把 Skill 的名称和描述暴露给模型，由"激活 Skill"工具按需把完整 SOP 钉到环境上下文
- **G4**：实现两种执行模式：内联模式（默认，注入主对话并安装工具过滤器）与派生模式（起一个子 Agent 跑完 SOP，把最终输出作为助手消息回流主对话），覆盖"需要继承上下文"和"需要客观隔离"两类任务
- **G5**：通过工具白名单做 fail-fast 依赖检查与子 Agent 工具集裁剪，提高模型工具选择准确率
- **G6**：支持两种 Skill 形态：目录型（目录内放 `SKILL.md` 与附属资料）与单文件型（一个 `.md` 文件）
- **G7**：提供"安装 Skill"内置工具，从本地路径或 HTTPS URL 拉取一份 Skill 定义文件落到项目目录下，安装后立即可用、无需重启
- **G8**：Skill 激活状态绑定在会话运行时上，随进程生命周期持有

## 功能需求### Skill 定义与解析- **F1**：每个 Skill 可以是目录（目录内放置 `SKILL.md`），也可以是单个 `.md` 文件；目录型同时允许放附属资料供 SOP 自行引用
- **F2**：Skill 定义文件由 YAML frontmatter（被两行 `---` 包围）与 Markdown 正文构成。Frontmatter 必填字段为名称；可选字段包含描述、允许的工具列表、执行模式、派生上下文级别、模型覆盖
- **F3**：名称用于注册 Slash Command 命令名，并作为激活与列表查询时的唯一标识
- **F4**：描述用于在帮助菜单、Skill 列表与"激活 Skill"工具的"未找到"提示中展示，并作为命令注册时的描述文本，末尾追加一个标记以表明该命令来自 Skill
- **F5**：允许的工具列表为字符串数组；缺省视为空（不限制）；非空时在内联模式下安装工具可见性过滤器，在派生模式下作为子 Agent 的工具集裁剪条件
- **F6**：执行模式取值为内联或派生；缺省视为内联
- **F7**：派生上下文级别取值为"无"、"最近若干条"、"较长历史"三档；缺省为"无"；仅在派生模式下生效，由 Skill 执行器从主对话历史中取相应条数的消息作为子 Agent prompt 的上下文前缀
- **F8**：模型覆盖为可选字符串，用于在派生模式下覆盖子 Agent 使用的模型；内联模式下忽略
- **F9**：Markdown 正文中的 `$ARGUMENTS` 占位符在执行期被替换为用户传入的参数文本；如未包含该占位符且参数非空，则在正文末尾追加一段"用户请求"块附带参数文本
- **F10**：单个 Skill 解析失败（frontmatter 缺失、格式不合法、名称为空等）时静默跳过，不抛错、不打 warning，保证扫描鲁棒

### Skill 加载器- **F11**：启动期按以下顺序扫描两个位置，每个位置下的目录或 `.md` 文件视为一个 Skill 候选：
  1. 用户级目录（用户主目录下的 gcode 配置目录）
  2. 项目级目录（当前工作目录下的 gcode 配置目录）
- **F12**：同名覆盖按上述顺序——后扫描的同名 Skill 替换前者。最终优先级为：项目级 > 用户级
- **F13**：扫描目录不存在时静默跳过；目录子项判断顺序为：若是子目录则查找其内 `SKILL.md`，否则识别以 `.md` 结尾的单文件
- **F14**：加载器内部为每个 Skill 缓存文件路径与文件修改时间锚点，为热重载留出依据
- **F15**：通过名称取 Skill 时检查文件修改时间是否大于上次加载时间，若文件被修改则重新读取并更新缓存；读盘或解析失败时保留已缓存版本，不让一次磁盘错误抹掉激活态

### Slash Command 自动注册- **F16**：每个加载成功的 Skill 在 ch10 命令注册中心注册一条命令：
  - 命令名等于 Skill 名称
  - 描述为 Skill 的描述末尾追加来自 Skill 的标记
  - 别名为空
  - 命令类型按执行模式区分：内联模式映射为 prompt 类型，派生模式映射为新增的"派生子 Agent"类型
- **F17**：注册时若命令名已与内置或用户自定义命令重名，跳过该 Skill，保护已有命令
- **F18**：prompt 类型的 handler 调用 Skill 执行器的内联入口完成渲染与激活；派生类型的 handler 由主循环按命令类型分支接管，调用执行器的派生入口
- **F19**：用户输入 `/<name>`（带或不带参数）等价于显式调用该 Skill

### 两阶段加载与激活 Skill 工具- **F20**：系统提示装配层预留一个"可用 Skill 清单"段落字段用于注入名称与描述列表；本期未在启动期主动填充该段落，列表信息由"激活 Skill"工具在"未找到"路径动态返回，留给后续扩展按需启用
- **F21**：会话运行时持有"已激活 Skill"映射。Agent 每轮迭代时若该映射非空，把所有已激活 Skill 的正文拼成一段提醒，通过系统提醒通道注入下一次模型调用的系统提示前
- **F22**：注册一个内置工具用于激活 Skill：
  - 输入参数为 Skill 名称
  - 标记为只读、属系统工具（不受工具过滤器与权限模式约束，始终可见）
  - 行为：从加载器取 Skill（自动触发热重载读盘），不存在时返回"未找到"错误结果并附带可用 Skill 列表；存在时调用内联执行器把 SOP 钉到已激活映射并按需安装工具过滤器；返回包含 SOP 正文的成功文本
- **F23**：Agent 需要从 TUI 拿到三个能力：把 SOP 钉到已激活映射、安装/清除工具可见性过滤器、查询主工具注册中心；这三个能力以稳定引用方式由 TUI 提供
- **F24**：工具 schema 投递前先经过过滤器，再叠加"系统工具一律保留"规则，使激活 Skill 等内置系统工具不会被白名单卡掉

### Skill 执行器- **F25**：内联执行入口（同步）：
  1. 对允许的工具列表做 fail-fast 检查——若有任一工具未在主工具注册中心注册，抛错并中止激活
  2. 渲染正文：若包含 `$ARGUMENTS` 占位符则替换；否则若参数非空则在末尾追加用户请求段
  3. 把渲染后的正文钉到已激活 Skill 映射
  4. 允许的工具列表非空时安装工具可见性过滤器，仅放行白名单内的工具；为空时不安装过滤器
  5. 返回渲染后的正文
- **F26**：派生执行入口（异步）：
  1. 同样先做 fail-fast 工具依赖检查
  2. 渲染 prompt：以正文为基础，参数非空时在末尾以"参数"段附加
  3. 按派生上下文级别从主对话历史取最近若干条消息，非"无"级别时把"父对话上下文"段拼到 prompt 头部
  4. 启动子 Agent 跑一轮，按允许的工具列表收窄子 Agent 可见的工具集，按可选的模型覆盖切换模型，返回最终文本
- **F27**：派生执行需要的两个额外能力——派生子 Agent 与抓取父对话最近若干条消息——由 TUI 提供并叠加在内联所需的三能力之上
- **F28**：派生分支跑完后把子 Agent 输出作为一条助手消息追加到 UI 显示，不写入主对话的模型历史，避免子 Agent 的 SOP 文本污染主对话；失败时降级为一条系统提示消息附带错误信息

### 安装 Skill 内置工具- **F29**：注册一个内置工具用于安装 Skill：
  - 输入参数：来源（本地文件路径或 `https://`、`http://` URL，必填）、名称（可选，用于覆盖 frontmatter 中的名称）
  - 标记为只读、属系统工具
- **F30**：来源是 HTTPS/HTTP URL 时通过 HTTP GET 拉取；响应非成功状态码时返回"拉取失败"错误并带状态码；网络异常返回带原始错误信息的失败结果
- **F31**：来源是本地路径时支持绝对路径或相对当前工作目录的路径；文件不存在时返回失败；读取为 UTF-8 文本
- **F32**：解析拉取到的内容（frontmatter + 正文）；最终 Skill 名称优先级：显式传入参数 > frontmatter 中的名称 > 来源文件名去掉扩展名
- **F33**：写入目标固定为当前工作目录下的项目级 Skill 目录，文件名为 `<name>/SKILL.md`；中间目录按需创建
- **F34**：写盘成功后立即触发加载器重新扫描，并回调命令注册流程，使新的 `/<name>` 命令立即可用、无需重启
- **F35**：返回包含写入路径的成功消息

### Skill 列表命令- **F36**：ch10 内置一条用于列出 Skill 的命令（命令名为 skills，类型为 UI 本地命令），由主循环按其 action 分支调用加载器的列表方法渲染输出：
  - 加载器未初始化：输出"未加载 Skill 目录"提示
  - 列表为空：输出"未在项目/用户 Skill 目录中找到任何 Skill"
  - 否则：首行输出"可用 Skill："，随后每行 `  /<name> — <description>`

## 非功能需求- **N1**：Skill 加载、命令注册全部在客户端就绪之后的初始化阶段完成；任何解析失败由静默跳过保证不阻断 gcode 启动
- **N2**：已激活 Skill 的提醒文本通过系统提醒通道注入到每轮模型调用前，落在 system reminder 区而非 user/assistant 历史，避免 SOP 在历史压缩时被摘要掉
- **N3**：激活 Skill 工具属系统工具且只读，跨任意工具过滤器都可见；权限系统不拦截
- **N4**：Skill 热重载基于文件修改时间：磁盘版本更新时自动重读；读盘或解析失败时回退已缓存版本，不让一次磁盘错误抹掉激活态
- **N5**：派生模式起子 Agent 时复用主 Agent 的工具实现、模型配置与工作目录，但按允许的工具列表派生出独立的工具可见集合，使 schema 投递与权限校验在子 Agent 内独立
- **N6**：派生模式输出仅在 UI 端追加显示，不写入主对话的模型历史，避免污染上下文
- **N7**：安装 Skill 在远程拉取时本期未设超时与响应体大小上限，处于"可信链路"假设；后续扩展需补充
- **N8**：TUI 与执行器之间的能力对象用稳定引用持有，避免组件重渲染导致工具过滤器抖动
- **N9**：已激活 Skill 映射在会话状态中持有；执行 `/clear` 时只重置消息与对话引用，不显式清除已激活映射——这是本期的明确简化，激活态随进程生命周期持有
- **N10**：所有 Skill 文件路径、URL、名称在错误返回中原样回显，方便排查

## 不做的事

- 不做 Skill 市场分发与版本管理
- 不做 Skill 沙箱隔离；本期 Skill 只能借用已注册工具，不支持声明自带的专属可执行工具
- 不做 Skill 间显式委派约束；嵌套调用通过激活 Skill 工具自然实现
- 不做派生模式下附属资料的预读——子 Agent 不预读任何附件，由 SOP 自行通过读文件工具取
- 不做压缩包安装；安装 Skill 当前只接受单份定义文件
- 不在 TUI 渲染 Skill 详情面板；列表命令仅文本输出
- 不在启动期主动注入"可用 Skill 清单"段落（系统提示装配层保留该字段但未填充）；模型按需通过激活 Skill 工具拉取
- 不为 Skill 提供独立日志文件（与主进程共享标准错误流）
- `/clear` 不显式清除已激活 Skill 映射；如需重置须重启进程

## 验收标准- **AC1**：用户级与项目级目录都不放 Skill 时，启动 gcode 后 Skill 列表命令输出"未在 Skill 目录中找到任何 Skill"；帮助菜单中不含来自 Skill 的命令
- **AC2**：在用户级目录放一份内联模式的 Skill，启动后 Skill 列表命令列出 `  /<name> — <description>`；帮助菜单含 `/<name>` 条目，描述末尾带来自 Skill 的标记
- **AC3**：用户键入 `/<name>` 回车，触发内联模式 Skill：主对话注入一条用户消息（含渲染后的 SOP 文本），模型在工具 schema 中只看到白名单工具与系统工具
- **AC4**：在项目级目录放一份派生模式、派生上下文为"无"、限定一组只读工具的 Skill，键入对应命令：UI 显示"派生模式运行中"提示，跑完后消息列表追加一条助手消息
- **AC5**：派生模式 Skill 的子 Agent 工具集被收窄到白名单内；试图调用白名单外的工具时被工具过滤层拒绝
- **AC6**：项目级与用户级同时存在同名 Skill 时，重新启动后 Skill 列表显示的描述取自项目级版本
- **AC7**：编辑用户级目录下的某 Skill 文件、把描述改掉但不重启 gcode；下一次模型调用激活 Skill 工具时取到的正文已是新内容（基于文件修改时间的热重载）
- **AC8**：声明白名单中含未注册工具名的 Skill 在用户键入命令触发内联执行时抛错，UI 走 prompt 命令的错误分支展示报错，不激活该 Skill
- **AC9**：模型在自然语言对话中调用激活 Skill 工具但传入未存在的名称：工具结果为错误并附带可用 Skill 列表，对话不中断
- **AC10**：模型成功调用激活 Skill 工具激活某 Skill：下一轮 Agent 迭代时构造出的提醒包含该 Skill 的完整 SOP 正文，并通过系统提醒通道注入下一次模型调用
- **AC11**：调用安装 Skill 工具传入本地路径，把单份定义文件装到项目级目录下；返回成功消息后对应命令立即可用，无需重启
- **AC12**：调用安装 Skill 工具传入 HTTPS URL，HTTP 200 时写盘并热加载；非成功状态码时返回"拉取失败"错误并附带状态码，不修改本地目录
- **AC13**：执行器内联入口在不同入参组合下行为正确：包含 `$ARGUMENTS` 占位符时被替换、不含占位符时把"用户请求"附加到末尾、白名单为空时不安装过滤器、白名单非空时安装的过滤器对放行/阻拦工具的判定与预期一致
- **AC14**：安装 Skill 工具的不同入参组合行为正确：本地路径安装成功后目标文件落到项目级目录、加载器立即识别到新 Skill；缺失来源参数返回错误；显式传入名称时使用覆盖名而非 frontmatter 中的名称
- **AC15**：单元测试与类型检查全部通过
```

````markdown
# Skill 技能包系统 Plan## 技术栈

- 运行时：bun（package.json `"type": "module"`，bin 直接执行 `src/main.tsx`）
- 语言：TypeScript 5.x，严格模式，`tsc --noEmit` 静态检查
- TUI：Ink 5 + React 18，`ink-spinner` / `ink-text-input` 提供输入与等待态
- LLM SDK：`@anthropic-ai/sdk`、`openai`，统一通过 `src/llm/client.ts` 包装
- MCP：`@modelcontextprotocol/sdk`，由 `src/mcp/manager.ts` 注入工具
- 解析：`js-yaml` 处理 SKILL.md frontmatter，`marked` + `marked-terminal` 渲染消息
- 测试：bun 自带 `bun:test`（`bun test`），所有 skill 单测落在 `tests/*.test.ts`

## 架构概览

新增一个 `src/skills/` 目录承载所有 Skill 相关的"数据 + 加载 + 执行 + 激活态"逻辑，与现有 `src/commands/`、`src/tools/`、`src/prompt/`、`src/agent/`、`src/tui/` 通过细窄接口交互。

按职责拆解：

- **src/skills/skill.ts**：类型定义。`SkillMeta` / `Skill` / `SkillHost` / `SkillForkHost` 接口
- **src/skills/catalog.ts**：`SkillCatalog` 类。`load()` 扫描用户/项目两层目录、`get()` 带 mtime 热重载、`list()` / `has()` 暴露给上层
- **src/skills/executor.ts**：纯函数 `runInline` 与 `runFork`，加上私有 `assertAllowedToolsExist` 做 fail-fast 依赖检查
- **src/skills/load-skill-tool.ts**：`LoadSkillTool` 类实现 `Tool` 接口，`system: true` 标记，模型按需激活
- **src/skills/install-tool.ts**：`InstallSkillTool` 类实现 `Tool` 接口，从本地路径或 https URL 安装单个 SKILL.md
- **src/prompt/builder.ts**：扩展 `BuildOptions.skillSection` 字段（priority 90 落到 `PromptBuilder`）
- **src/agent/agent.ts**：构造参数新增 `activeSkills?: Map<string, string>` 与 `toolFilter?: (name: string) => boolean`；`run()` 每轮调用 `buildActiveSkillsReminder` 注入 SOP；工具 schema 投递前应用 `toolFilter` 过滤
- **src/commands/commands.ts**：`CommandType` 新增 `"skill_fork"` 联合类型成员；内置一条 `name: "skills"` 的 `local_ui` 命令（handler 返回 action 字符串 `"skills"`）
- **src/tui/app.tsx**：构造 `SkillCatalog`、`activeSkillsRef`、`toolFilterRef`、`skillHostRef`；定义 `wireSkillsToRegistry` 把 catalog 项注册为 `prompt` / `skill_fork` 命令；`executeCommand` 内识别 `skill_fork` 类型走 `runFork + spawnSubAgent` 路径

## 数据流### 启动期

```
initClient (in App component):
  ├─ new SkillCatalog()
  ├─ catalog.load(workDir)        // 扫描 ~/.gcode/skills + workDir/.gcode/skills
  ├─ registry.register(new LoadSkillTool(catalog, skillHostRef.current))
  ├─ registry.register(new InstallSkillTool(workDir, catalog, onInstalled))
  ├─ loadUserCommands(workDir) → cmdRegistry.register(...)
  └─ wireSkillsToRegistry(catalog, cmdRegistry, skillHostRef.current)
        其中 onInstalled = () => wireSkillsToRegistry(catalog, cmdRegistry, skillHostRef.current)
```

### Skill 显式调用：`/foo`（inline）

```
input → parse → cmdRegistry.find("foo")
  cmd.type === "prompt"
  → promptText = cmd.handler({workDir, args}) === runInline(skill, args, skillHost)
        ├ assertAllowedToolsExist(skill, host)
        ├ render body ($ARGUMENTS / User Request fallback)
        ├ host.activateSkill(name, body)   // activeSkillsRef.current.set
        └ host.setToolFilter(name => allowed.has(name))   // toolFilterRef.current
  → conv.addUserMessage(promptText) + setMessages
  → runAgentLoop()
        Agent.run() 每轮 buildActiveSkillsReminder 把 SOP 重新钉回 system reminder
```

### Skill 显式调用：`/review`（fork）

```
input → parse → cmdRegistry.find("review")
  cmd.type === "skill_fork"
  → executeCommand 命中 skill_fork 分支
  → forkHost = { ...skillHostRef.current, runSubAgent, snapshotParentMessages }
  → runSkillFork(skill, args, forkHost)
        ├ assertAllowedToolsExist(skill, host)
        ├ build prompt: body + "\n\nARGUMENTS: <args>"（若有）
        ├ forkContext = "recent" / "full" → 取 5 / 100 条父消息拼到 prompt 前
        └ host.runSubAgent(prompt, allowedTools)
              → spawnSubAgent({ name, description, tools, model }, prompt, client, registry, provider, workDir)
        → resolve(result)
  → setMessages([..., { role: "assistant", content: result }])
```

### Skill 意图触发（自然语言 → LoadSkill）

```
user 输入 "帮我写个 commit message"
  → runAgentLoop → agent.run() → LLM stream → tool_use: LoadSkill({name:"commit"})
  → LoadSkillTool.execute
        ├ catalog.get("commit") (hot-reload by mtime)
        ├ runInline(skill, "", skillHost)
        │     activateSkillsRef.current.set("commit", body)
        │     toolFilterRef.current = name => allowed.has(name)
        └ return { output: "Skill 'commit' activated.\n\n<body>" }
  → 下一轮迭代：
        buildActiveSkillsReminder(activeSkills) 渲染出 "# Active Skills..."
        conv.addSystemReminder(...) 注入到下次 LLM 调用前
        agent.run() 内部 toolSchemas = registry.getAllSchemas().filter(toolFilter || system)
```

### `/clear`

```
/clear handler (local_ui, action="clear")
  → setMessages([])
  → committedIndexRef.current = 0
  → convRef.current = new ConversationManager()
  (注：activeSkillsRef 与 toolFilterRef 当前实现下未在 /clear 时显式重置)
```

### `InstallSkill` 安装

```
InstallSkillTool.execute({ source, name? }):
  ├ source ~ /^https?:/  → fetch(source) → resp.text()
  │   else                → readFileSync(absolute or join(workDir, source))
  ├ name = arg.name || nameFromFrontmatter(content) || basename(source).replace(/\.md$/, "")
  ├ writeFileSync(workDir/.gcode/skills/<name>/SKILL.md, content)
  ├ catalog.load(workDir)               // 重新扫描
  └ onInstalled?.()                     // app.tsx 重新 wireSkillsToRegistry
```

## 核心数据结构与接口### `SkillMeta` / `Skill`

```ts
// src/skills/skill.ts
export interface SkillMeta {
  name: string;
  description: string;
  allowedTools?: string[];
  mode?: "inline" | "fork";
  model?: string;
  forkContext?: "full" | "recent" | "none";
}

export interface Skill {
  meta: SkillMeta;
  body: string;          // SKILL.md 去掉 frontmatter 后的正文
  sourceDir: string;     // 目录型时是目录路径；单文件时是上层目录
  isDirectory: boolean;  // 用于后续区分目录型与单文件 Skill
}
```

约定：

- 解析时 `mode` 缺省映射为 `"inline"`：`(raw.mode as "inline" | "fork") ?? "inline"`
- `forkContext` 缺省为 `undefined`，`runFork` 内 `?? "none"`

### `SkillHost` / `SkillForkHost`

```ts
export interface SkillHost {
  activateSkill(name: string, body: string): void;
  setToolFilter(filter: ((name: string) => boolean) | null): void;
  toolRegistry(): ToolRegistry;
}

export interface SkillForkHost extends SkillHost {
  runSubAgent(prompt: string, toolFilter?: string[]): Promise<string>;
  snapshotParentMessages(count: number): string;
}
```

TUI 端通过 `useRef<SkillHost>` 持有稳定的 host 对象，闭包捕获 `activeSkillsRef` / `toolFilterRef` / `registryRef`。

### `SkillCatalog`

```ts
// src/skills/catalog.ts
interface CatalogEntry {
  skill: Skill;
  filePath: string;       // SKILL.md 绝对路径，热重载用
  loadedMtimeMs: number;  // 上次加载时的 mtime
}

export class SkillCatalog {
  private entries = new Map<string, CatalogEntry>();

  load(workDir: string): void;            // 顺序扫描 ~/.gcode/skills 与 workDir/.gcode/skills
  private scanDirectory(dir: string): void;
  private loadSkill(filePath: string, sourceDir: string, isDirectory: boolean): void;

  list(): SkillMeta[];
  get(name: string): Skill | undefined;   // mtime 热重载入口
  has(name: string): boolean;
}
```

### `Tool` 接口与系统标记

```ts
// src/tools/types.ts
export interface Tool {
  name: string;
  description: string;
  category: ToolCategory;   // "read" | "write" | "command"
  deferred?: boolean;
  system?: boolean;         // ← LoadSkill / InstallSkill 在工具过滤时永久豁免

  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>;
}
```

### `LoadSkillTool` / `InstallSkillTool`

```ts
// src/skills/load-skill-tool.ts
export class LoadSkillTool implements Tool {
  name = "LoadSkill";
  category = "read" as const;
  system = true;

  constructor(private catalog: SkillCatalog, private host: SkillHost) {}

  schema(): Record<string, unknown>;
  execute(args: Record<string, unknown>): Promise<ToolResult>;
}

// src/skills/install-tool.ts
export class InstallSkillTool implements Tool {
  name = "InstallSkill";
  category = "read" as const;
  system = true;

  constructor(
    private workDir: string,
    private catalog: SkillCatalog,
    private onInstalled?: () => void
  ) {}
}
```

### 执行器函数

```ts
// src/skills/executor.ts
function assertAllowedToolsExist(skill: Skill, host: SkillHost): void;

export function runInline(
  skill: Skill,
  args: string,
  host: SkillHost
): string;          // 同步返回渲染后的 body

export async function runFork(
  skill: Skill,
  args: string,
  host: SkillForkHost
): Promise<string>; // 子 Agent 的最终输出
```

### `Command` 与 `CommandType`

```ts
// src/commands/commands.ts
export type CommandType = "local" | "local_ui" | "prompt" | "skill_fork";

export interface Command {
  name: string;
  aliases: string[];
  type: CommandType;
  description: string;
  handler: (ctx: CommandContext) => string;
}
```

### `Agent` 配置新增字段

```ts
// src/agent/agent.ts
export interface AgentConfig {
  // ...既有字段...
  activeSkills?: Map<string, string>;
  toolFilter?: (name: string) => boolean;
}

export class Agent {
  // ...
  activeSkills: Map<string, string>;
  private toolFilter?: (name: string) => boolean;
}
```

## 模块设计### `src/skills/skill.ts`**职责**：类型与接口契约

**对外接口**：`SkillMeta` / `Skill` / `SkillHost` / `SkillForkHost`

**依赖**：仅 `../tools/registry.js`（类型用）

### `src/skills/catalog.ts`**职责**：扫描磁盘 → `Map<name, CatalogEntry>`；按 mtime 热重载

**对外接口**：`SkillCatalog` 类

**依赖**：`node:fs`（`readdirSync` / `readFileSync` / `existsSync` / `statSync`）、`node:path` 的 `join`、`node:os` 的 `homedir`、`js-yaml`

**关键函数**：`parseSkillFile(content)` 私有，返回 `{ meta, body } | null`；frontmatter 解析失败、缺 `name` 字段时返回 null

### `src/skills/executor.ts`**职责**：把 Skill 渲染并钉到上下文（inline）或转交子 Agent（fork）

**对外接口**：`runInline` / `runFork`

**依赖**：`./skill.js` 接口；不依赖任何具体 UI 或 Agent 实现

`runInline` 是纯同步函数：先 fail-fast 检查 `allowedTools`，再渲染 body，再回调 host 两次（`activateSkill` + 条件 `setToolFilter`）；返回的 body 字符串供命令 handler 作为 prompt 使用。

`runFork` 是 async 函数：渲染 prompt，按 `forkContext` 取父对话片段，最后 await `host.runSubAgent`。

### `src/skills/load-skill-tool.ts`**职责**：把 catalog 中的 Skill 按需激活的工具实现

**对外接口**：`LoadSkillTool` 类

**依赖**：`../tools/types.js` 的 `Tool` / `ToolResult` / `strArg`、`./catalog.js`、`./skill.js`、`./executor.js`

`execute()` 流程：

1. `strArg(args, "name")` 解析
2. `catalog.get(name)` —— 触发热重载
3. 不存在：列出 `catalog.list().map(s => s.name).join(", ")` 返回 isError
4. 存在：`runInline(skill, "", this.host)`
5. 返回 `Skill '<name>' activated.\n\n<body>`

### `src/skills/install-tool.ts`**职责**：从本地路径或 https URL 拉单个 SKILL.md 落到 `.gcode/skills/<name>/SKILL.md`

**对外接口**：`InstallSkillTool` 类

**依赖**：`node:fs` 的 `mkdirSync` / `writeFileSync` / `readFileSync` / `existsSync`、`node:path` 的 `join` / `isAbsolute` / `basename`、`../tools/types.js`、`./catalog.js`

`execute()` 流程：

1. 取 `source` 必填
2. https URL → fetch；本地路径 → `isAbsolute` 后 `join(workDir, source)`，存在性检查后 `readFileSync`
3. 解析 `name`：优先用户传参；次选 frontmatter；兜底 `basename(source).replace(/\.md$/, "")`
4. `mkdirSync(targetDir, { recursive: true })` + `writeFileSync(SKILL.md, content)`
5. `catalog.load(workDir)` 重扫
6. `this.onInstalled?.()` 通知上层重新 wire 命令

### `src/agent/agent.ts`**修改**：

- `AgentConfig` 接口新增 `activeSkills?: Map<string, string>` 与 `toolFilter?: (name: string) => boolean`
- 类成员 `activeSkills: Map<string, string>` / `private toolFilter`
- `run()` 入口先取 `let toolSchemas = this.registry.getAllSchemas()`；若有 `toolFilter`，按 `s => registry.get(s.name)?.system === true || this.toolFilter!(s.name)` 过滤
- 每轮迭代调 `buildActiveSkillsReminder(this.activeSkills)`，非空时 `this.conversation.addSystemReminder(reminder)`

`buildActiveSkillsReminder` 内部实现：

```ts
function buildActiveSkillsReminder(active: Map<string, string>): string {
  if (active.size === 0) return "";
  let out = "# Active Skills\n\nThe following Skill SOPs are pinned to the environment context. Follow each SOP when its triggering condition applies.\n\n";
  for (const [name, body] of active) {
    out += `## Active Skill: ${name}\n\n${body}\n\n`;
  }
  return out;
}
```

### `src/prompt/builder.ts`**修改**：`BuildOptions` 新增可选字段 `skillSection?: string`；`buildSystemPrompt` 中：

```ts
if (opts.skillSection) {
  b.add({ name: "Skills", priority: 90, content: opts.skillSection });
}
```

priority 90 位于 `CustomInstructions`(95) 与 `Memory`(100) 之前、`Environment`(80) 之后。

### `src/commands/commands.ts`**修改**：

- `CommandType` 联合追加 `"skill_fork"` 成员
- `createDefaultRegistry` 中新增 `name: "skills"` 内置命令：

```ts
registry.register({
  name: "skills",
  aliases: [],
  type: "local_ui",
  description: "List available skills",
  handler: () => "skills",
});
```

handler 返回 action 字符串 `"skills"`，由 `app.tsx` 的 `local_ui` 分支按 action 处理实际渲染。

### `src/tui/app.tsx`**修改**：

- 顶部 import `SkillCatalog` / `runInline as runSkillInline` / `runFork as runSkillFork` / `LoadSkillTool` / `InstallSkillTool` / `SkillHost` / `SkillForkHost`
- 新增 module-level 函数 `wireSkillsToRegistry(catalog, cmdRegistry, skillHost)`：遍历 `catalog.list()`，对每个 `meta` 拿到 `skill = catalog.get(meta.name)`，按 `mode === "fork"` 注册 `skill_fork` 类型，否则注册 `prompt` 类型；handler 闭包捕获 `skill` 与 `skillHost`
- 在 `App` 内新增 refs：
  - `skillCatalogRef = useRef<SkillCatalog | null>(null)`
  - `activeSkillsRef = useRef(new Map<string, string>())`
  - `toolFilterRef = useRef<((name: string) => boolean) | null>(null)`
  - `skillHostRef = useRef<SkillHost>({ activateSkill, setToolFilter, toolRegistry })`
- `initClient` 中：构造 `catalog`、调 `catalog.load(workDir)`、把 catalog 存到 `skillCatalogRef`、注册两个工具、`wireSkillsToRegistry(...)` 兜底
- `executeCommand` 中追加 `if (cmd.type === "skill_fork") { ... }` 分支：构造 `SkillForkHost`（带 `runSubAgent: spawnSubAgent(...)` 与 `snapshotParentMessages: getMessages().slice(-count).map([role] content).join("\n")`），调 `runSkillFork(skill, parsed.args, forkHost)`，then 后 push assistant 消息，catch 后 push system 错误
- `local_ui` 分支识别 `"skills"` action，按 `catalog.list()` 渲染列表
- `runAgentLoop` 内构造 `Agent` 时传 `activeSkills: activeSkillsRef.current` 与 `toolFilter: buildComposedToolFilter(coordinatorToolFilter(teamManagerRef.current), toolFilterRef.current)`
- `/skill <name> [args]` 短句重写：在 `executeCommand` 顶部 `if (parsed.name === "skill" && parsed.args.trim())` 时把 `parsed` 改写为 `{ name: parts[0], args: parts.slice(1).join(" ") }`

## 模块交互### 启动期时序

```
App.useEffect → initClient(provider)
  ├ createClient(provider, systemPrompt)
  ├ new SkillCatalog() → catalog.load(workDir)
  ├ registry.register(new LoadSkillTool(catalog, skillHost))
  ├ registry.register(new InstallSkillTool(workDir, catalog, onInstalled))
  ├ loadUserCommands(workDir).forEach(cmdRegistry.register)
  └ wireSkillsToRegistry(catalog, cmdRegistry, skillHost)
        for meta in catalog.list():
          if (!cmdRegistry.find(meta.name))
            cmdRegistry.register({ name, type: isFork ? "skill_fork" : "prompt", ... })
```

### 显式调用 inline Skill 的调用链

```
input.tsx onSubmit
  → App.onUserInput
     → executeCommand(parsed)
        → cmd.type === "prompt"
        → promptText = cmd.handler({workDir, args})
              = runSkillInline(skill, args, skillHost)
                    → assertAllowedToolsExist
                    → render body
                    → skillHost.activateSkill (Map.set)
                    → skillHost.setToolFilter (when allowedTools)
                    → return body
        → conv.addUserMessage(promptText)
        → setMessages
        → runAgentLoop()
              → new Agent({ activeSkills: activeSkillsRef.current,
                             toolFilter: composedFilter, ... })
              → agent.run() 每轮：
                  ├ toolSchemas = filter by toolFilter
                  ├ buildActiveSkillsReminder → addSystemReminder
                  └ streamLLM
```

### 显式调用 fork Skill 的调用链

```
executeCommand → cmd.type === "skill_fork" 分支
  ├ skill = skillCatalogRef.current?.get(parsed.name)
  ├ forkHost = {
  │     activateSkill, setToolFilter, toolRegistry,
  │     runSubAgent: (prompt, tools) => spawnSubAgent(
  │         { name, description, tools, model },
  │         prompt, client, registry, provider, workDir),
  │     snapshotParentMessages: count =>
  │         convRef.getMessages().slice(-count).map(...).join("\n"),
  │ }
  └ runSkillFork(skill, parsed.args, forkHost)
        ├ assertAllowedToolsExist
        ├ render prompt + fork_context snapshot
        └ host.runSubAgent(prompt, allowedTools)
              → spawnSubAgent → new Agent (sub) → agent.run()
              → 收集子 Agent stream_text 拼成 output → resolve(output)
        .then(result => setMessages([..., { role: "assistant", content: result }]))
        .catch(err => setMessages([..., { role: "system", content: "Skill fork error: ..." }]))
```

### LoadSkill 工具调用时序

```
agent.run() → LLM 返回 tool_use { name: "LoadSkill", input: { name: "commit" } }
  → permission check (LoadSkill 是 read 类，且 system=true → 自动放行)
  → tool.execute(args, ctx)
        ├ catalog.get("commit")  // 触发 mtime 热重载
        ├ runInline(skill, "", host) 同步执行
        │     → activeSkillsRef.set("commit", body)
        │     → toolFilterRef = name => allowed.has(name)
        └ return { output: "Skill 'commit' activated.\n\n<body>", isError: false }
  → 下一轮迭代：
        toolSchemas = registry.getAllSchemas().filter(s =>
          registry.get(s.name).system === true || toolFilter(s.name))
        buildActiveSkillsReminder 渲染 # Active Skills... → addSystemReminder
        模型在 system reminder 中看到完整 SOP，且工具集已收窄
```

## 文件组织

```text
gcode/
├── src/
│   ├── skills/                          # 新增包
│   │   ├── skill.ts                     # SkillMeta / Skill / SkillHost / SkillForkHost
│   │   ├── catalog.ts                   # SkillCatalog: load / get (mtime 热重载) / list / has
│   │   ├── executor.ts                  # runInline / runFork / assertAllowedToolsExist
│   │   ├── load-skill-tool.ts           # LoadSkillTool 实现 Tool 接口
│   │   └── install-tool.ts              # InstallSkillTool 实现 Tool 接口
│   ├── agent/
│   │   └── agent.ts                     # 修改：activeSkills + toolFilter + buildActiveSkillsReminder
│   ├── prompt/
│   │   └── builder.ts                   # 修改：BuildOptions.skillSection 槽位 (priority 90)
│   ├── commands/
│   │   └── commands.ts                  # 修改：CommandType += "skill_fork" + 内置 /skills
│   └── tui/
│       └── app.tsx                      # 修改：wireSkillsToRegistry + refs + skill_fork dispatch
└── tests/
    ├── skills.test.ts                   # runInline 单测：$ARGUMENTS / fallback / toolFilter
    └── install-skill.test.ts            # InstallSkillTool 单测：本地路径 / 缺失 source / name override
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 数据格式 | 仅 SKILL.md（frontmatter+body） | 与 README 一致；解析路径单一；不引入 yaml/md 分离的认知负担 |
| Skill 形态 | 支持目录 + 单文件 `.md` | 单文件 Skill 上手成本极低；目录型为附属资料留位 |
| 优先级覆盖 | 用户级 < 项目级 | 与 npm/git 配置惯例一致；项目级最贴近当前任务 |
| 内置 Skill 分发 | 暂不内置 | 当前 ts 实现把 `/review` 保留为 ch10 内置 `prompt` 命令；Skill 由用户自定义 |
| 第一阶段注入位置 | `BuildOptions.skillSection` 预留槽 (priority 90) | 享受 prompt cache 稳定前缀；初版可不主动填充 |
| 第二阶段注入位置 | `conversation.addSystemReminder` (每轮 reminder) | 多 Skill 同激活、嵌套场景下 SOP 始终靠前；system reminder 区域不被 compact 摘要 |
| LoadSkill 入参 | 仅 `name` | 与"意图识别"语义一致；参数走后续 user message 更自然 |
| LoadSkill 权限 | `category: "read" + system: true` | 没有外部副作用；为支持嵌套必须豁免 toolFilter |
| InstallSkill 权限 | `category: "read" + system: true` | 当前实现选择把"安装"也当作系统工具，模型可在任意场景调用；签名上仍是写盘+网络，后续可降级为受限 |
| fork 模式实现 | 复用 `spawnSubAgent` | 不再造子 Agent；TUI 层直接复用现成 sub-agent 通道 |
| fork_context 默认 | `"none"` | "隔离"才是 fork 本意；需要带上下文走 `"recent"` / `"full"` 显式声明 |
| allowed_tools 在 inline 模式 | `setToolFilter` 真正动态收窄 | TUI ref 持有过滤器，下一轮 agent 立即生效 |
| Skill 与已有命令冲突 | 跳过加载（`wireSkillsToRegistry` 内 `cmdRegistry.find` 短路） | 保护内置命令；用户级 `.gcode/commands/*.md` 先于 skill 加载，自动获得优先权 |
| 解析失败 | `parseSkillFile` 返回 null，调用方静默跳过 | 与 instructions loader 一致的容错策略 |
| 热加载 | `SkillCatalog.get` 按 mtime 检测；`InstallSkillTool.onInstalled` 重新 wire 命令 | 用户改 SKILL.md 下次 `LoadSkill` 立即生效；新装 Skill 不需要重启 |
| host 抽象 | `SkillHost` 接口由 TUI 用 `useRef` 实现 | 让 `runInline` 保持纯函数；不直接耦合 React 状态 |
| 工具过滤器存放位置 | `useRef<((name: string) => boolean) | null>` | 跨 render 稳定；`buildComposedToolFilter` 与 team coordinator 过滤器合成 |
| `activeSkills` 存放位置 | `useRef<Map<string, string>>` | 比 state 更适合频繁写入；Agent 拿到的是同一 Map 引用 |
| TS 类型策略 | strict + `Record<string, unknown>` 取 tool args | 与既有 Tool 接口风格一致；通过 `strArg` 辅助函数取值 |
| `bun test` 替代 jest | 直接用 bun 内置 test runner | 与 monorepo 无需额外配置；启动快 |
````

````markdown
# Skill 技能包系统 Tasks

> 本章模块位于 `src/skills/`，运行时是 bun + TypeScript 5.x；测试通过 `bun test`，类型检查通过 `tsc --noEmit`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/skills/skill.ts` | `SkillMeta` / `Skill` / `SkillHost` / `SkillForkHost` 接口 |
| 新建 | `src/skills/catalog.ts` | `SkillCatalog` 类：扫描两层目录、按 mtime 热重载 |
| 新建 | `src/skills/executor.ts` | `runInline` / `runFork` / `assertAllowedToolsExist` |
| 新建 | `src/skills/load-skill-tool.ts` | `LoadSkillTool` 实现 `Tool` 接口 |
| 新建 | `src/skills/install-tool.ts` | `InstallSkillTool` 实现 `Tool` 接口 |
| 修改 | `src/tools/types.ts` | `Tool` 接口新增 `system?: boolean` 标记 |
| 修改 | `src/agent/agent.ts` | `AgentConfig.activeSkills` / `.toolFilter`；`run()` 每轮 reminder + 工具 schema 过滤 |
| 修改 | `src/prompt/builder.ts` | `BuildOptions.skillSection` 槽（priority 90） |
| 修改 | `src/commands/commands.ts` | `CommandType += "skill_fork"`；内置 `/skills` 命令 |
| 修改 | `src/tui/app.tsx` | refs + `skillHostRef` + `wireSkillsToRegistry` + `skill_fork` 分发 |
| 新建 | `tests/skills.test.ts` | `runInline` 单测：`$ARGUMENTS` / fallback / 工具过滤器 |
| 新建 | `tests/install-skill.test.ts` | `InstallSkillTool` 单测：本地路径、错误、`name` 覆盖 |

## T1: skills 类型定义**文件：** `src/skills/skill.ts`

**依赖：** `src/tools/registry.ts`

**步骤：**

1. 定义 `SkillMeta`：`name`（必填）、`description`、`allowedTools?: string[]`、`mode?: "inline" | "fork"`、`model?: string`、`forkContext?: "full" | "recent" | "none"`
2. 定义 `Skill`：`meta` / `body` / `sourceDir` / `isDirectory`
3. 定义 `SkillHost`：`activateSkill(name, body)` / `setToolFilter(filter | null)` / `toolRegistry(): ToolRegistry`
4. 定义 `SkillForkHost extends SkillHost`：`runSubAgent(prompt, toolFilter?): Promise<string>` / `snapshotParentMessages(count): string`
5. import 路径用 `.js` 后缀（ESM `"type": "module"` 要求）：`from "../tools/registry.js"`

**验证：** `tsc --noEmit` 通过。

## T2: SkillCatalog 扫描与热重载**文件：** `src/skills/catalog.ts`

**依赖：** T1

**步骤：**

1. 引入 `readdirSync` / `readFileSync` / `existsSync` / `statSync`、`join`、`homedir`、`yaml`
2. 定义内部 `CatalogEntry`：`skill`、`filePath`、`loadedMtimeMs`
3. 定义 `SkillCatalog` 类，私有字段 `entries = new Map<string, CatalogEntry>()`
4. `load(workDir: string)`：按 `[~/.gcode/skills, workDir/.gcode/skills]` 顺序调 `scanDirectory`
5. `scanDirectory(dir)`：try/catch 读 `readdirSync`；对每个子项 `statSync`：
   - 是目录 → 寻找 `<sub>/SKILL.md`，存在则 `loadSkill(file, fullPath, true)`
   - 不是目录、文件名 `.md` 结尾且不等于 `SKILL.md` → `loadSkill(file, dir, false)`
6. `loadSkill(filePath, sourceDir, isDirectory)`：读 UTF-8、`parseSkillFile(raw)`、为 null 跳过；构造 `Skill` 对象；try/catch `statSync(filePath).mtimeMs` 取 mtime；写入 `entries`；全程 try/catch 包住，不抛
7. `get(name)`：取 entry；若 `filePath && loadedMtimeMs > 0` 且 `statSync.mtimeMs > loadedMtimeMs`，则 `readFileSync` + `parseSkillFile` 重新填充 `entry.skill` 与 `loadedMtimeMs`；解析或读盘失败时保留缓存
8. `list()` / `has()` 简单实现
9. 私有 `parseSkillFile(content)`：校验起始 `---`、找下一个 `---`、`yaml.load(frontmatter)`、`raw?.name` 必填；映射下划线键到驼峰字段：`raw.allowed_tools → allowedTools`、`raw.fork_context → forkContext`；解析失败返回 null

**验证：** `tsc --noEmit` 通过；写一个临时脚本 `bun run -e 'import {SkillCatalog} from "./src/skills/catalog.ts"; const c = new SkillCatalog(); c.load("."); console.log(c.list())'` 不报错。

## T3: executor 渲染与 fail-fast**文件：** `src/skills/executor.ts`

**依赖：** T1

**步骤：**

1. 私有 `assertAllowedToolsExist(skill, host)`：若 `allowedTools` 为 `undefined` 或长度 0 直接返回；否则遍历，每项 `host.toolRegistry().get(toolName)` 不存在时抛 `Error('skill "<name>" declares allowed tool "<tool>" which is not registered')`
2. `export function runInline(skill, args, host): string`：
   - 先 `assertAllowedToolsExist`
   - `body = skill.body`
   - 若 `body.includes("$ARGUMENTS")` → `body = body.replaceAll("$ARGUMENTS", args)`
   - 否则若 `args` 非空 → `body += "\n\nUser Request: " + args`
   - `host.activateSkill(skill.meta.name, body)`
   - 若 `skill.meta.allowedTools` 存在（即便长度 0 也算"非 undefined"，按现实现 `if (skill.meta.allowedTools)` 走真分支）→ 构造 `Set` + `host.setToolFilter(name => allowed.has(name))`
   - 返回 body
3. `export async function runFork(skill, args, host): Promise<string>`：
   - 先 `assertAllowedToolsExist`
   - `prompt = skill.body; if (args) prompt += "\n\nARGUMENTS: " + args`
   - `contextMode = skill.meta.forkContext ?? "none"`
   - `"recent"` → `host.snapshotParentMessages(5)`，`prompt = 'Context from parent conversation:\n<snap>\n\n' + prompt`
   - `"full"` → 同样语法，count=100
   - 调 `host.runSubAgent(prompt, skill.meta.allowedTools)` 并返回

**验证：** `tsc --noEmit` 通过；T11 单测会进一步覆盖。

## T4: LoadSkillTool**文件：** `src/skills/load-skill-tool.ts`

**依赖：** T1, T2, T3

**步骤：**

1. import `Tool` / `ToolResult` / `strArg` from `../tools/types.js`
2. 定义 `LoadSkillTool implements Tool`：
   - `name = "LoadSkill"`
   - `description` 字符串
   - `category = "read" as const`
   - `system = true`
   - 构造函数 `(private catalog, private host)`
3. `schema()` 返回 `{ name, description, input_schema: { type: "object", properties: { name: { type: "string", description: "..." } }, required: ["name"] } }`
4. `async execute(args)`：
   - `name = strArg(args, "name")`
   - `skill = catalog.get(name)`，不存在时构造 available 列表（`catalog.list().map(s => s.name).join(", ") || "(none)"`），返回 `{ output: \`Skill '${name}' not found. Available skills: ${available}\`, isError: true }`
   - 存在时 `body = runInline(skill, "", host)`
   - 返回 `{ output: \`Skill '${name}' activated.\n\n${body}\`, isError: false }`

**验证：** `tsc --noEmit` 通过。

## T5: InstallSkillTool**文件：** `src/skills/install-tool.ts`

**依赖：** T2

**步骤：**

1. 引入 `mkdirSync` / `writeFileSync` / `readFileSync` / `existsSync`、`join` / `isAbsolute` / `basename`、`Tool` / `ToolResult` / `strArg`
2. 私有函数 `nameFromFrontmatter(content)`：若不以 `---` 起头返回空串；找下一个 `---`；正则 `(?:^|\n)\s*name:\s*(.+)` 抽 name；trim
3. `InstallSkillTool implements Tool`：
   - `name = "InstallSkill"`
   - `category = "read" as const`、`system = true`
   - 构造函数 `(private workDir, private catalog, private onInstalled?)`
4. `schema()`：properties 含 `source`(required) 与 `name`(optional)
5. `async execute(args)`：
   - 取 `source = strArg(args, "source")`，为空返回 isError `Error: source is required`
   - 若 `/^https?:\/\//.test(source)`：
     - `try { resp = await fetch(source); if (!resp.ok) return { output: \`Error: fetch failed (\${resp.status})\`, isError: true }; content = await resp.text(); } catch (e) { return { output: \`Error fetching skill: \${e.message}\`, isError: true }; }`
   - 否则：`p = isAbsolute(source) ? source : join(workDir, source)`；`existsSync` 不通过返回 isError；`readFileSync(p, "utf-8")`
   - `name = strArg(args, "name") || nameFromFrontmatter(content) || basename(source).replace(/\.md$/, "")`
   - name 为空返回 isError
   - `dir = join(workDir, ".gcode", "skills", name)`；`mkdirSync(dir, { recursive: true })`；`writeFileSync(join(dir, "SKILL.md"), content, "utf-8")`
   - `catalog.load(workDir)`；`onInstalled?.()`
   - 返回 `{ output: \`Skill '${name}' installed to .gcode/skills/${name}/SKILL.md\`, isError: false }`

**验证：** `tsc --noEmit` 通过。

## T6: Tool 接口新增 system 标记**文件：** `src/tools/types.ts`

**依赖：** 无

**步骤：**

1. 在 `Tool` 接口新增 `system?: boolean`
2. 既有工具实现可以不显式设置（默认 falsy）

**验证：** `tsc --noEmit` 通过。

## T7: prompt builder 加 skillSection 槽**文件：** `src/prompt/builder.ts`

**依赖：** 无

**步骤：**

1. `BuildOptions` 接口新增 `skillSection?: string;`
2. `buildSystemPrompt` 内：

```ts
if (opts.skillSection) {
  b.add({ name: "Skills", priority: 90, content: opts.skillSection });
}
```

3. 顺序保证：环境 80 → Skills 90 → CustomInstructions 95 → Memory 100

**验证：** `tsc --noEmit` 通过；既有 prompt 单测仍跑过。

## T8: Agent 接入 activeSkills 与 toolFilter**文件：** `src/agent/agent.ts`

**依赖：** T1, T6

**步骤：**

1. `AgentConfig` 接口新增：
   - `activeSkills?: Map<string, string>`
   - `toolFilter?: (name: string) => boolean`
2. `Agent` 类新增成员：
   - `activeSkills: Map<string, string>`
   - `private toolFilter?: (name: string) => boolean`
3. 构造函数赋值：`this.activeSkills = config.activeSkills ?? new Map()`；`this.toolFilter = config.toolFilter`
4. `run()` 入口处理 toolSchemas：

```ts
let toolSchemas = this.registry.getAllSchemas();
if (this.toolFilter) {
  toolSchemas = toolSchemas.filter((s) => {
    const n = s.name as string;
    return this.registry.get(n)?.system === true || this.toolFilter!(n);
  });
}
```

5. 在每轮迭代体内（已有 `manageContext` 调用之后），添加：

```ts
const skillReminder = buildActiveSkillsReminder(this.activeSkills);
if (skillReminder) {
  this.conversation.addSystemReminder(skillReminder);
}
```

6. 文件底部追加私有函数 `buildActiveSkillsReminder(active: Map<string, string>): string`：空 Map 返回 `""`；否则拼出 `# Active Skills\n\n...\n\n## Active Skill: <name>\n\n<body>\n\n`

**验证：** `tsc --noEmit` 通过；`bun test tests/agent.test.ts` 通过（既有测试无 toolFilter / activeSkills 时行为不变）。

## T9: 命令类型新增 skill_fork + /skills 命令**文件：** `src/commands/commands.ts`

**依赖：** 无

**步骤：**

1. `CommandType` 联合追加 `"skill_fork"`
2. `createDefaultRegistry()` 内 register 一条：

```ts
registry.register({
  name: "skills",
  aliases: [],
  type: "local_ui",
  description: "List available skills",
  handler: () => "skills",
});
```

3. ch10 `/review` 内置 prompt 命令保留不动；Skill 用户若定义同名 `/review`，会被 `wireSkillsToRegistry` 的 `cmdRegistry.find` 短路掉

**验证：** `tsc --noEmit` 通过；`bun test tests/command-loader.test.ts` 通过。

## T10: TUI 接入 — refs / host / wireSkillsToRegistry / dispatch**文件：** `src/tui/app.tsx`

**依赖：** T1-T9

**步骤：**

1. 文件顶部 import：
   - `import { SkillCatalog } from "../skills/catalog.js"`
   - `import { runInline as runSkillInline, runFork as runSkillFork } from "../skills/executor.js"`
   - `import { LoadSkillTool } from "../skills/load-skill-tool.js"`
   - `import { InstallSkillTool } from "../skills/install-tool.js"`
   - `import type { SkillHost, SkillForkHost } from "../skills/skill.js"`
   - 既有 `Command` / `CommandRegistry` 类型若没暴露则补 import
2. 新增 module-level 函数 `wireSkillsToRegistry(catalog, cmdRegistry, skillHost)`：

```ts
function wireSkillsToRegistry(
  catalog: SkillCatalog,
  cmdRegistry: CommandRegistry,
  skillHost: SkillHost,
): void {
  for (const meta of catalog.list()) {
    if (cmdRegistry.find(meta.name)) continue;
    const skill = catalog.get(meta.name);
    if (!skill) continue;
    const isFork = skill.meta.mode === "fork";
    const cmd: Command = {
      name: meta.name,
      aliases: [],
      type: isFork ? "skill_fork" : "prompt",
      description: `${meta.description} [skill]`,
      handler: isFork
        ? () => ""
        : (ctx) => runSkillInline(skill, ctx.args, skillHost),
    };
    try { cmdRegistry.register(cmd); } catch { /* name clash */ }
  }
}
```

3. `App` 函数体内新增 refs：
   - `skillCatalogRef = useRef<SkillCatalog | null>(null)`
   - `activeSkillsRef = useRef(new Map<string, string>())`
   - `toolFilterRef = useRef<((name: string) => boolean) | null>(null)`
   - `skillHostRef = useRef<SkillHost>({ activateSkill: (n, b) => activeSkillsRef.current.set(n, b), setToolFilter: (f) => { toolFilterRef.current = f }, toolRegistry: () => registryRef.current })`
4. `initClient` 内（在 user commands 加载之前/之后均可，按 ts 当前实现是 catalog 先于 user 命令）：
   - `const catalog = new SkillCatalog(); catalog.load(workDir); skillCatalogRef.current = catalog`
   - `registryRef.current.register(new LoadSkillTool(catalog, skillHostRef.current))`
   - `registryRef.current.register(new InstallSkillTool(workDir, catalog, () => wireSkillsToRegistry(catalog, cmdRegistryRef.current, skillHostRef.current)))`
   - 加载 user commands 完毕后调 `wireSkillsToRegistry(catalog, cmdRegistryRef.current, skillHostRef.current)`
5. `executeCommand` 顶部 `/skill <name> [args]` 短句重写：

```ts
if (parsed.name === "skill" && parsed.args.trim()) {
  const parts = parsed.args.trim().split(/\s+/);
  parsed = { name: parts[0], args: parts.slice(1).join(" ") };
}
```

6. `executeCommand` 的 `local_ui` 分支新增 `case "skills":` action 处理：从 `skillCatalogRef.current?.list()` 渲染清单
7. `executeCommand` 末尾新增 `if (cmd.type === "skill_fork") { ... }` 分支：

```ts
if (cmd.type === "skill_fork") {
  const skill = skillCatalogRef.current?.get(parsed.name);
  if (!skill) { setMessages(prev => [...prev, { role: "system", content: `Skill not found: ${parsed.name}` }]); return true; }
  const client = clientRef.current;
  if (!client) { setMessages(prev => [...prev, { role: "system", content: "Client not ready." }]); return true; }
  setMessages(prev => [...prev, { role: "system", content: `Running skill "${parsed.name}" in fork mode…` }]);
  const forkHost: SkillForkHost = {
    ...skillHostRef.current,
    runSubAgent: (prompt, tools) => spawnSubAgent(
      { name: skill.meta.name, description: skill.meta.description, tools, model: skill.meta.model },
      prompt, client, registryRef.current, selectedProvider, workDir
    ),
    snapshotParentMessages: (count) => convRef.current.getMessages()
      .slice(-count)
      .map(m => `[${m.role}] ${m.content}`)
      .join("\n"),
  };
  runSkillFork(skill, parsed.args, forkHost)
    .then(result => setMessages(prev => [...prev, { role: "assistant", content: result }]))
    .catch(err => setMessages(prev => [...prev, { role: "system", content: `Skill fork error: ${(err as Error).message}` }]));
  return true;
}
```

8. `runAgentLoop` 内构造 `new Agent({...})` 时新增字段：

```ts
activeSkills: activeSkillsRef.current,
toolFilter: buildComposedToolFilter(coordinatorToolFilter(teamManagerRef.current), toolFilterRef.current),
```

**验证：** `tsc --noEmit` 通过；`bun run src/main.tsx` 能启动到 TUI。

## T11: runInline 单测**文件：** `tests/skills.test.ts`

**依赖：** T2-T4

**步骤：**

1. 引入 `describe / it / expect` from `"bun:test"`；`runInline` from `"../src/skills/executor.js"`；`ToolRegistry` from `"../src/tools/registry.js"`；类型 `Skill / SkillHost` from skill.ts
2. 工厂 `makeHost()`：创建 `activated: [string, string][]`、`filter`；构造 `ToolRegistry` 并 register 两个 stub：`ReadFile` / `Grep`（`schema()` 返回 `{ name, description, input_schema: {} }`；`execute` 返回 `{ output: "", isError: false }`）；返回 `{ host, activated, getFilter: () => filter }`
3. 工厂 `skill(body, allowedTools?)` 构造 `Skill` 对象
4. 用例 1 "substitutes $ARGUMENTS and pins the SOP + tool filter"：
   - `body = runInline(skill("Do $ARGUMENTS now.", ["ReadFile", "Grep"]), "the thing", host)`
   - `expect(body).toBe("Do the thing now.")`
   - `expect(activated[0][0]).toBe("demo"); expect(activated[0][1]).toBe("Do the thing now.")`
   - `filter("ReadFile") === true`，`filter("Bash") === false`
5. 用例 2 "appends a User Request fallback when there is no placeholder"：
   - `runInline(skill("SOP body"), "extra context", host)`
   - body 含 `"SOP body"` 与 `"User Request: extra context"`
6. 用例 3 "does not set a tool filter when the skill allows all tools"：
   - `runInline(skill("body"), "", host)`
   - `getFilter() === null`

**验证：** `bun test tests/skills.test.ts` 三个 case 全过。

## T12: InstallSkillTool 单测**文件：** `tests/install-skill.test.ts`

**依赖：** T5

**步骤：**

1. 引入 bun:test API 与 `mkdtempSync / writeFileSync / existsSync / readFileSync / tmpdir / join`
2. 准备 fixture SKILL.md 字符串：

```
const SKILL = `---
name: commit-helper
description: Helps write commits
allowed_tools: [Bash, ReadFile]
---
Write a conventional-commit message for the staged changes.`;
```

3. 用例 1 "installs a skill from a local path and loads it into the catalog"：
   - `workDir = mkdtempSync(...)`；写 `srcPath = workDir/src-skill.md`
   - `catalog = new SkillCatalog()`
   - `r = await new InstallSkillTool(workDir, catalog).execute({ source: srcPath })`
   - 断言 `r.isError === false`、`r.output` 含 `"commit-helper"`、`<workDir>/.gcode/skills/commit-helper/SKILL.md` 存在、内容含 `"conventional-commit"`、`catalog.has("commit-helper")` 为 true
4. 用例 2 "errors on a missing local source"：调 `execute({ source: "nope.md" })`，`r.isError === true`
5. 用例 3 "honors an explicit name override"：传 `{ source: srcPath, name: "renamed" }`，最终落到 `.gcode/skills/renamed/SKILL.md`

**验证：** `bun test tests/install-skill.test.ts` 三个 case 全过。

## T13: 启动期联调**文件：** 无（运行验证）

**依赖：** T1-T12

**步骤：**

1. `bun run src/main.tsx` 启动 TUI
2. 在 `.gcode/skills/foo/SKILL.md` 放一个最简 Skill（仅 frontmatter `name`, `description`），重启
3. 键入 `/skills` 回车，预期输出 `Available skills:` 后跟一行 `  /foo — <description>`
4. 键入 `/help`，预期含 `/foo` 行且描述末尾带 `[skill]`
5. 键入 `/foo` 回车，inline 路径走通，conversation 多一条 user 消息

**验证：** TUI 行为符合预期，进程不 panic。

## T14: 端到端验证

按 checklist.md 中端到端场景章节，在终端里把所有路径跑一遍（含 fork 模式、`LoadSkill` 工具调用、`InstallSkill` 安装、热重载）。

## 执行顺序

```text
T1 → T2 → T3
  ├─ T4 (LoadSkillTool, 依赖 T1-T3)
  └─ T5 (InstallSkillTool, 依赖 T2)

T6 (Tool 接口扩 system) — 独立可早做

T7 (prompt builder) — 独立

T8 (Agent activeSkills + toolFilter, 依赖 T1, T6)

T9 (CommandType + /skills 内置, 独立)

T10 (TUI 接入, 依赖 T1-T9)

T11 (runInline 单测, 依赖 T2-T4)
T12 (InstallSkillTool 单测, 依赖 T5)

T13 (启动联调, 依赖 T1-T12)
T14 (端到端验证, 依赖 T13)
```

可并行：T6 / T7 / T9 之间彼此独立；T11 / T12 单测彼此独立；其余按线性依赖推进。
````

````markdown
# Skill 技能包系统 Checklist

> 每一项通过运行代码或观察行为来验证。最后一节"端到端场景（终端实跑）"必须在真实终端里跑过；其它项靠 `bun test` 与 `tsc --noEmit` 自动覆盖。

## 实现完整性

- [ ] `src/skills/skill.ts` 导出 `SkillMeta` / `Skill` / `SkillHost` / `SkillForkHost`（验证：`tsc --noEmit`）
- [ ] `src/skills/catalog.ts` 导出 `SkillCatalog`，含 `load` / `get` / `list` / `has`（验证：`tsc --noEmit`，`bun run -e 'import {SkillCatalog} from "./src/skills/catalog.ts"; new SkillCatalog().load(".")'` 不报错）
- [ ] `src/skills/executor.ts` 导出 `runInline` / `runFork`（验证：`tsc --noEmit`）
- [ ] `src/skills/load-skill-tool.ts` 导出 `LoadSkillTool` 实现 `Tool` 接口（验证：`tsc --noEmit`）
- [ ] `src/skills/install-tool.ts` 导出 `InstallSkillTool` 实现 `Tool` 接口（验证：`tsc --noEmit`）
- [ ] `src/tools/types.ts` 中 `Tool` 接口含 `system?: boolean`（验证：grep `system\\?:` 命中）
- [ ] `src/agent/agent.ts` 含 `activeSkills` 字段、`toolFilter` 私有字段、`buildActiveSkillsReminder` 私有函数（验证：grep 命中三处）
- [ ] `src/prompt/builder.ts` 的 `BuildOptions` 含 `skillSection?: string`，且 priority 90 槽位被启用（验证：grep `skillSection` 与 `priority: 90`）
- [ ] `src/commands/commands.ts` 的 `CommandType` 含 `"skill_fork"`；内置 `name: "skills"` 命令存在（验证：grep `"skill_fork"` 与 `name: "skills"`）
- [ ] `src/tui/app.tsx` 含 `wireSkillsToRegistry` 函数、`skillHostRef` / `skillCatalogRef` / `activeSkillsRef` / `toolFilterRef` 四个 ref（验证：grep）

## Skill 定义与解析

- [ ] 一个最简的合法 SKILL.md（仅 frontmatter `name` + body）能被 `SkillCatalog.load` 收录（验证：临时 fixture + `bun test`）
- [ ] frontmatter 缺 `name` 字段时 `parseSkillFile` 返回 null，对应 Skill 不进 catalog（验证：tests/skills.test.ts 扩展 / 临时手动）
- [ ] frontmatter 含 `allowed_tools: [Bash, ReadFile]` 时 `SkillMeta.allowedTools` 拿到 `["Bash", "ReadFile"]`（驼峰映射成立）
- [ ] frontmatter 含 `mode: fork` + `fork_context: recent` 时 `SkillMeta.mode === "fork"` 且 `forkContext === "recent"`

## Catalog 加载与覆盖

- [ ] 空 workDir + 空 HOME 启动后 `catalog.list()` 为空（验证：`bun test` 临时 mkdtempSync 验证 / 终端启动后 `/skills` 输出 `No skills found in .gcode/skills/.`）
- [ ] 用户级目录 `~/.gcode/skills/foo/` 与项目级 `<workDir>/.gcode/skills/foo/` 同名 Skill 时，`catalog.get("foo")` 返回项目级版本（验证：手动 fixture 测试，比较 description）
- [ ] 单文件 Skill `<dir>/foo.md` 与目录 Skill `<dir>/foo/SKILL.md` 都能被收录（验证：手动 fixture + `catalog.has("foo")`）
- [ ] 编辑某个 SKILL.md 后不重启，下次 `catalog.get(name)` 取到的 body 是新内容（mtime 热重载，验证：单测 + 手动）
- [ ] 损坏的 SKILL.md（缺第二个 `---`）被 `parseSkillFile` 返回 null 静默跳过，不阻断其它 Skill 加载

## fail-fast 依赖检查

- [ ] `runInline` 在 `allowedTools` 含未注册工具时抛 `Error('skill "<name>" declares allowed tool "<tool>" which is not registered')`（验证：`bun test tests/skills.test.ts` 可补一个用例覆盖；当前必过路径在 wireSkillsToRegistry 调用时延迟到 `/<name>` 触发那刻）
- [ ] `LoadSkill` / `InstallSkill` 标记 `system = true`，工具过滤时 schema 仍出现在子集中（验证：单测构造 `toolFilter` 后用 `Agent.run` 内逻辑断言）

## Slash Command 自动注册

- [ ] `wireSkillsToRegistry` 把 inline 模式 Skill 注册为 `type: "prompt"`，fork 模式注册为 `type: "skill_fork"`（验证：单测可手动构造）
- [ ] 命令的 `description` 末尾带 ` [skill]` 标记（验证：`/help` 输出含 `[skill]`）
- [ ] 名字与已有命令冲突时跳过注册（验证：建一个 `name: help` 的 Skill，`/help` 仍为内置；catalog 中条目存在）
- [ ] `/skill <name> [args]` 输入被改写为 `/<name> [args]` 走标准命令路径（验证：终端实跑）

## 两阶段加载

- [ ] `buildActiveSkillsReminder(new Map())` 返回空字符串（验证：单测 + grep `if (active.size === 0) return ""`）
- [ ] `buildActiveSkillsReminder(map)` 非空时返回 `# Active Skills\n\n...\n\n## Active Skill: <name>\n\n<body>\n\n` 形式（验证：单测）
- [ ] `Agent.run` 每轮迭代调 `buildActiveSkillsReminder` 并通过 `conversation.addSystemReminder` 注入（验证：grep `buildActiveSkillsReminder` 在 `run()` 体内被调用）
- [ ] 工具 schema 过滤遵守 `toolFilter` + `system === true` 双条件（验证：grep `system === true` 在 agent.ts 中出现）

## LoadSkill 工具

- [ ] 调 `LoadSkill({name: "<exists>"})` 返回 `{ output: "Skill '<name>' activated.\n\n<body>", isError: false }` 且 `activeSkills` Map 包含该 name
- [ ] 调 `LoadSkill({name: "<missing>"})` 返回 isError 的 `Skill '<name>' not found. Available skills: ...`
- [ ] 没有 `allowed_tools` 的 Skill 被 LoadSkill 激活后 `toolFilterRef.current` 仍为 null（不安装过滤器）
- [ ] 有 `allowed_tools` 的 Skill 被 LoadSkill 激活后 `toolFilterRef.current` 是函数，下一轮 `Agent.run` 工具 schema 收窄到 `allowed ∪ system`

## /clear

- [ ] `/clear` action 走 `setMessages([]) + new ConversationManager()`；当前实现下不显式重置 `activeSkillsRef` 与 `toolFilterRef`（验证：grep `case "clear"`，确认未触发 reset）

## Skill 执行器

- [ ] `runInline` 替换 `$ARGUMENTS` 占位符（验证：tests/skills.test.ts 第一个用例）
- [ ] `runInline` 无占位符时追加 `User Request: <args>`（验证：tests/skills.test.ts 第二个用例）
- [ ] `runInline` 当 `allowedTools` 为空时不安装 toolFilter（验证：tests/skills.test.ts 第三个用例）
- [ ] `runFork` 按 `forkContext` 取 0 / 5 / 100 条父消息拼到 prompt 前（验证：可补单测 mock host）
- [ ] fork 模式跑完后主对话新增一条 `role: "assistant"` 消息（验证：终端实跑）

## InstallSkill

- [ ] 本地路径安装：`InstallSkillTool.execute({source: "/tmp/test-skill.md"})` 后 `<workDir>/.gcode/skills/<name>/SKILL.md` 存在且 `catalog.has(name)` 为 true（验证：tests/install-skill.test.ts 第一个用例）
- [ ] 缺失 source：`execute({source: "nope.md"})` 返回 `isError: true`（验证：tests/install-skill.test.ts 第二个用例）
- [ ] name 覆盖：`execute({source, name: "renamed"})` 写到 `.gcode/skills/renamed/SKILL.md`（验证：tests/install-skill.test.ts 第三个用例）
- [ ] https URL 安装：`execute({source: "https://example.com/skill.md"})` HTTP 200 时写盘成功；非 200 时返回 `Error: fetch failed (<status>)`（验证：手动或扩展单测 mock fetch）
- [ ] 安装完成后 `onInstalled` 回调被调；TUI 端立刻调用 `wireSkillsToRegistry` 让新命令可见（验证：终端实跑 install 后 `/skills` 立即列出）

## /skills 命令

- [ ] catalog 为空时 `/skills` 输出 `No skills found in .gcode/skills/.`
- [ ] catalog 非空时输出 `Available skills:` 后跟 `  /<name> — <description>` 列表（验证：终端实跑）

## 编译与测试

- [ ] `tsc --noEmit` 无错误
- [ ] `bun test` 全部通过（含 tests/skills.test.ts 三例与 tests/install-skill.test.ts 三例）
- [ ] `bun run src/main.tsx` 能启动 TUI 不报错

## 端到端场景

> 在终端里启动 gcode，按下面流程一步步操作；每步附"观察"项。

**前置**：

- `cd /Users/codemelo/gcode && bun install && bun run src/main.tsx`
- 准备两个测试 Skill：
  - `~/.gcode/skills/echoer/echoer.md`（单文件 inline）：

    ```
    ---
    name: echoer
    description: 把用户输入按 SOP 回显
    allowed_tools: [Bash]
    ---
    Run `echo $ARGUMENTS` and report stdout.
    ```

  - `<workDir>/.gcode/skills/reviewer/SKILL.md`（目录 fork）：

    ```
    ---
    name: reviewer
    description: 对当前 git diff 给出客观审查
    mode: fork
    fork_context: none
    allowed_tools: [Bash, ReadFile, Grep]
    ---
    Run `git diff` and report concrete findings.
    ```

**步骤**：

1. **启动与就绪**
   - 操作：进程启动
   - 观察：TUI 主面板出现，状态栏底部含 "Type a message and press Enter..."；无类型/运行时错误

2. **`/help`**
   - 操作：键入 `/help` 回车
   - 观察：输出含内置命令 + `/skills` 行 + `/echoer ... [skill]` + `/reviewer ... [skill]`

3. **`/skills`**
   - 操作：键入 `/skills` 回车
   - 观察：首行 `Available skills:`，两行 `  /echoer — 把用户输入按 SOP 回显` / `  /reviewer — 对当前 git diff 给出客观审查`

4. **inline 模式 `/echoer hello`**
   - 操作：键入 `/echoer hello` 回车
   - 观察：UI 显示 user 消息（含 `Run \`echo hello\` and report stdout.`），LLM 调 Bash 工具 echo 出 `hello`；`/status` 显示 `Skills: 2`

5. **fork 模式 `/reviewer`**
   - 操作：在主对话先说 "I'm reviewing my diff now."，再键入 `/reviewer`
   - 观察：UI 显示 `Running skill "reviewer" in fork mode…`；之后追加一条 assistant 消息（含审查报告）；主 conversation 没有用户 SOP 文本，只有最终 assistant 文本

6. **意图触发 LoadSkill**
   - 操作：键入自然语言 "帮我把 README 里所有 echo 操作整理一下"（让 LLM 想到调 echoer）
   - 观察：LLM 调 `LoadSkill({name: "echoer"})`，工具结果 `Skill 'echoer' activated. ...`；下一轮迭代 conversation 中能通过 `addSystemReminder` 看到 `# Active Skills` 块（用 debug 日志或 `/status` 间接验证）

7. **`/skill echoer hello world` 短句**
   - 操作：键入 `/skill echoer hello world` 回车
   - 观察：被改写为 `/echoer hello world`，行为与第 4 步一致

8. **`InstallSkill` 安装第三方 Skill**
   - 操作：先 `echo '---\nname: greeter\ndescription: greet\n---\nSay hi to $ARGUMENTS.' > /tmp/greeter.md`；切到 gcode 输入 "把 /tmp/greeter.md 装成 skill"
   - 观察：LLM 调 `InstallSkill({source: "/tmp/greeter.md"})`，工具返回 `Skill 'greeter' installed ...`；`/skills` 立即多出 `  /greeter — greet`；`/greeter alice` 可调用

9. **热重载**
   - 操作：在另一个终端 `echo '---\nname: echoer\ndescription: 新描述\n---\nNew body $ARGUMENTS' >> ~/.gcode/skills/echoer/echoer.md`（追加内容并触发 mtime 更新），然后在 gcode 中再次说自然语言让 LLM `LoadSkill({name:"echoer"})`
   - 观察：工具返回的 body 反映新内容

10. **`/clear` 与退出**
    - 操作：键入 `/clear` 回车，再键入 `/quit`
    - 观察：对话清空、新 sessionId；`/quit` 后进程优雅退出

## 验收报告模板

```
## 验收报告

### 通过
- [x] `tsc --noEmit` 无错误：tsc 0 error
- [x] `bun test` — tests/skills.test.ts 3 pass, tests/install-skill.test.ts 3 pass
- [x] /skills 输出两条 Skill ...
- ...

### 未通过
- [ ] 第 X 项 — 预期：...，实际：...，修复方案：...

### 端到端
- [x] 启动与就绪 — 结果：TUI 正常加载
- [x] /help — 结果：含 [skill] 行
- [x] /skills — 结果：echoer + reviewer
- ...（按上面 10 步逐条列出）
```
````


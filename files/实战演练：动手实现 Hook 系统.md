# 第12章：实战篇

## 本章需要做什么

上一章我们给 GCode 装上了 Skill 技能包系统，让 Agent 能通过 Slash Command 加载预定义的提示词和工具集合。但每次 Agent 写完文件你还是要手动跑格式化，每次看到危险命令你还是得自己盯着审批弹窗，每次开始新对话你还是要手动说「先读一下 ARCHITECTURE.md」。

这些事情触发条件明确、执行动作固定，完全不需要你来做。这一章要给 GCode 装上 Hook 系统，让你在 Agent 的生命周期事件上挂载自动化动作。做完之后，格式化、拦截、上下文注入全部自动化，你不用再当人肉 CI。

具体要新增这些东西：

* **事件常量&#x20;**：15 个生命周期事件（session\_ start/session\_ end、turn\_ start/turn\_ end、pre\_ tool\_ use/post\_ tool\_ use、pre\_ send/post\_ receive、startup/shutdown/error/compact/permission\_ request/file\_ change/command\_ execute）

* **核心数据结构&#x20;**：Hook、Action、HookContext、ConditionGroup、Condition、ToolRejectedError

* **条件表达式&#x20;**：解析与求值，支持 ==/!=/=\~/ \~= 四种操作符，&&/|| 组合（不可混用）

* **四种执行器&#x20;**：command（shell 命令）、prompt（注入提示词）、http（HTTP 请求）、agent（子 Agent，先占位）

* **上下文变量替换&#x20;**：$EVENT、$TOOL\_ NAME、$FILE\_ PATH、$MESSAGE、$ERROR、$TOOL\_ ARGS.xxx

* **执行控制&#x20;**：once（只执行一次）、async（后台执行）、command 的 timeout 超时

* **拦截机制&#x20;**：pre\_ tool\_ use + reject 返回 ToolRejectedError，LLM 看到拒绝原因后调整策略

* **HookEngine 核心&#x20;**：runHooks（非拦截事件）+ runPreToolHooks（pre\_ tool\_ use 专用）

* **Agent Loop 集成&#x20;**：在会话、轮次、消息、工具的生命周期节点插入 Hook 调用

* **配置加载与校验&#x20;**：从 YAML 加载，校验事件名、action 类型、reject/async 约束、必填字段

这章 **不做&#x20;**：once 标记的持久化（只做运行时标记，重启即重置）、Hook 执行顺序的显式优先级字段、agent 执行器的真实实现（留给后续的 SubAgent 章节）。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：在 Agent 生命周期的关键节点上挂自动化动作，让触发条件明确、动作固定的重复工作从人工变成机器来做。格式化、拦截、上下文注入都不用再手动盯，GCode 自动在合适的时刻做该做的事。

技术要求：

- 用「事件 + 条件 + 动作」三要素描述一条规则，条件可以省略表示无条件触发，事件和动作必须有
- 生命周期事件覆盖四层：会话级、轮次级、消息级、工具级，再加少量系统级事件
- 工具执行前的事件能拦截，可基于工具参数做细粒度安全策略，拦下后把拒绝原因当工具结果反馈给模型，让它调整
- 条件表达式复用权限规则的匹配语法（精确、反向、正则、glob），逻辑组合用「全部满足」或「任一满足」二选一，不混用
- 四种动作：执行 shell 命令、注入提示词、发 HTTP 请求、启动子 Agent（先占位）
- 执行控制有只跑一次、后台异步、命令超时三种，拦截类事件不允许异步
- Hook 自身失败只记日志，绝不中断 Agent 主流程；规则从 YAML 声明式加载并集中校验

这一步先不做子 Agent 动作的真实运行（等 SubAgent 章节对接）、只跑一次标记的持久化，以及 Hook 执行顺序的显式优先级。

三要素格式：

- event：触发时刻（会话开始、轮次开始、工具执行前、工具执行后等）
- if：条件表达式，复用权限规则的匹配和逻辑组合，可省略表示无条件
- action：动作类型（命令 / 提示词 / HTTP / 子 Agent）加上各自的字段
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



写一个测试用的 `hooks` 配置

```yaml
# Hooks
hooks:

  # pre_tool_use 拦截写 *.json（reject + on_error 兜底）
  # 注意：LLM 给的 file_path 通常是绝对路径，glob 的 * 不跨 / 分隔符，
  # 所以这里用正则按后缀匹配（=~ /\.json$/）而不是 =* "*.json"
  - id: block-json-write
    event: pre_tool_use
    if: 'tool == "WriteFile" && args.file_path =~ /\.json$/'
    action:
      type: command
      command: 'echo "禁止直接写入 JSON 文件，请使用专用工具"'
    reject: true
```



然后我们打开GCode，去试试这个hooks，我们输入



![]()



Agent 调用 WriteFille工具时会被 hook 拦截，收到"禁止写入Json文件"的错误，工具不会真正执行，然后Agent 会根据拒绝原因调整策略，用更合法的方式达到目的



现在对于我们单体的Agent来说，其实已经比较完整成体系了，但是不知道有没有感觉到，有的时候我们的GCode任务一多，一件件处理会处理得好慢，好像我们得给它找点帮手，比如是不是搞多几个Agent。



下一章，我们就来讲讲怎么实现 SubAgent 和任务编排。

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

````markdown
# Hook 生命周期挂钩系统 Spec## 背景ch11 把可复用 SOP 搬出源码做成 Skill 包之后,GCode 在"用户怎么扩展行为"这条路径上还差最后一环:**在 Agent 生命周期的固定时刻自动跑一段用户配置的动作**。当前的扩展点都是显式触发——Skill 要 `/<name>` 唤起、Slash 命令要用户手敲。如果想做这种"触发条件明确、动作固定"的重复事,只能每次手动来:

- 写完文件想立刻 `gofmt`,得手动跑或写监听脚本
- 想阻止 Agent 跑 `rm -rf` 之类的命令,权限规则要逐个加 deny
- 想在每轮用户提交前提醒 Agent "记得用 zh-CN",没现成机制
- 想在 Agent 长跑结束后给自己发个 IM 通知,要自己起进程

ch08 的权限引擎覆盖了"该不该允许工具调用",但**只在工具调用前判定一次、动作仅 Allow/Deny/Ask**,做不了命令格式化、上下文注入、外部通知这些副作用。Hook 系统补的是这条缝:在 Agent 生命周期的 11 个固定时刻挂自动化动作,把"触发条件明确、动作固定"的重复工作从人工变成机器。

设计上沿用 ch08 已有的权限匹配器做条件表达式底层——但需先把单一通配匹配扩展成"精确/反向/正则/glob"四种,让 Hook 条件、未来的权限规则共用同一套匹配语义。

## 目标- **G1**:把 Agent 生命周期上的 11 个固定时刻抽象成事件总线,事件 emit 时同步驱动 Hook 引擎;现有内部事件(工具 Start/End、Compact、Approval)继续走 Event channel,不受影响
- **G2**:用户用 YAML 文件声明式配置 Hook 规则,启动期一次性加载并校验,**配置错误立即报到 stderr 并跳过出错规则,不阻断进程**
- **G3**:每条 Hook 是"事件 + 条件 + 动作"三要素,条件可省略表示无条件触发
- **G4**:把 ch08 权限规则的匹配语法从单一通配扩展成"精确 exact / 反向 not / 正则 regex / glob"四种;Hook 条件表达式与扩展后的权限规则共用同一套匹配器
- **G5**:条件表达式支持嵌套字段访问,多条件用 `all_of` / `any_of` 二选一组合,**不允许嵌套混用**
- **G6**:在 PreToolUse 时刻,Hook 的 shell 动作通过 `exit code 2` 表达拦截、stderr 作为拒绝原因——被拒原因当 tool_result 回灌让模型调整;在 UserPromptSubmit 时刻同理拦截用户提交、原因回显到对话
- **G7**:四种动作类型——执行 shell 命令、注入提示词、发 HTTP 请求、启动子 Agent(**子 Agent 本期占位不实现,等后续章节对接**)
- **G8**:三种执行控制——only_once(同一会话内只跑一次)、async(异步后台执行不阻塞主流程)、timeout(命令最大执行时长);**拦截类事件(PreToolUse / UserPromptSubmit)不允许 async,加载期校验出错**
- **G9**:Hook 自身失败(命令非零退出、HTTP 超时、HTTP 解析错等)**只记日志、不中断 Agent 主流程**——除非该 hook 是同步拦截类且通过约定方式表达拦截信号

## 功能需求### 权限匹配语法扩展(前置基础)- **F1**:把权限规则 Pattern 形态从单一字符串扩展成结构化匹配类型 `{type, value}`,type 取 `exact`、`not`、`regex`、`glob` 之一;缺省类型沿用现有 glob 语义,保证向后兼容
- **F2**:规则 YAML 串语法升级——除 `Bash(rm *)` 这种"工具(简洁串)"写法保留代表 glob 类型外,新增显式类型前缀:
  - `Bash(=value)` 精确(整串相等)
  - `Bash(!inner)` 反向(对 inner 取反,inner 自身仍按规则解析,支持 `!=value`、`!~regex`、`!glob`)
  - `Bash(~regex)` 正则
  - `Bash(value)` 不带前缀沿用 glob 语义
- **F3**:精确匹配做整串相等比较;glob 沿用现有 wildcard / matchPath 实现;正则在加载期编译并缓存,编译失败按 F4 处理;反向是"任意其它类型的取反包装",支持嵌套(如 `Bash(!=value)`)
- **F4**:扩展后权限引擎的 Allow/Deny 判定语义不变,但规则解析失败原本静默跳过,现在改为"stderr 打印失败规则与原因、其余规则正常加载"
- **F5**:现有 ch08 的所有权限测试、既有的 `.gcode/permissions.yaml` 用户配置(仅写 `Bash(git *)` 这种)必须继续工作,不破坏向后兼容

### Hook 配置文件- **F6**:YAML 配置文件位置按以下顺序扫描,找到就加载、找不到就跳过:
  - 项目级:`<projectRoot>/.gcode/hooks.yaml`
  - 用户级:`~/.gcode/hooks.yaml`
- **F7**:两层规则**叠加合并**——所有规则共同参与事件分派;不存在"覆盖同名"概念,hook 的 name 仅用于日志和 only_once 跟踪;两层中出现同名 hook 时,加载期 stderr 提示冲突并跳过后到者
- **F8**:YAML 顶层结构:`hooks:` 数组,每条 hook 为对象,字段如下:
  - `name`(必填):字符串,用于日志、only_once 跟踪、冲突检测
  - `event`(必填):事件名,11 选 1(见 F9)
  - `if`(可选):条件表达式对象,省略表示无条件
  - `action`(必填):动作对象,含 `type` 与各类型独有字段
  - `only_once`(可选 bool,默认 false):会话内只跑一次
  - `async`(可选 bool,默认 false):是否后台异步执行
  - `timeout`(可选时长字符串如 `30s`,默认 30s):命令 / HTTP 最大执行时长

### 生命周期事件- **F9**:11 个事件名及触发时机:
  - **SessionStart**:gcode 启动初次进入会话或 `/clear` 新建会话后、env context 装配完毕、首条 user 消息进入对话历史**之前**
  - **SessionEnd**:进程关闭前、`/clear` 关闭旧会话前、`/resume` 切换离开旧会话前
  - **SessionResume**:`/resume` 选中历史会话、恢复完成、首条 user 消息进入**之前**
  - **UserPromptSubmit**:TUI 提交一条非 Slash 命令的 user 消息、写入对话历史**之前**——可拦截
  - **Stop**:Agent.Run 自然停止后、`Done: true` 事件 emit 之前;取消、出错路径不触发
  - **PreUserMessage**:每轮 streamOnce 调 `provider.Stream` 之前;payload 含当前 conversation 末尾的 user 消息
  - **PreToolUse**:executeBatched 对每条 tool call 准备执行**之前**、权限引擎 Check 之**前**——可拦截
  - **PostToolUse**:单条 tool call 拿到 result 之后、emit PhaseEnd 之前;权限被 Deny 的也触发,payload.is_error=true
  - **PreCompact**:`compact.ManageContext` 调用之前(自动/紧急/手动三路径合并)
  - **PostCompact**:`compact.ManageContext` 返回后
  - **Notification**:权限 Ask 弹出审批时、Stream 返回 Err 时
- **F10**:每个事件对应一份固定的 payload schema,作为 Hook 条件表达式与动作输入的数据源
  ```
  # 通用字段(每个事件都有)
  event: <事件名>
  session_id: <当前会话 ID>
  cwd: <项目工作目录>
  mode: <permission.Mode 名,default / plan>

  # 事件特化字段
  PreToolUse / PostToolUse:
    tool_name: <内部工具名,如 read_file>
    tool_input: <工具参数 JSON 对象>
    tool_result: <仅 PostToolUse,工具结果摘要文本>
    is_error: <仅 PostToolUse,bool>
  UserPromptSubmit / PreUserMessage:
    prompt: <用户输入文本>
  Notification:
    kind: approval | stream_error
    detail: <approval 含工具名;stream_error 含错误摘要>
  PreCompact / PostCompact:
    trigger: auto | emergency | manual
    before_tokens: <int,仅 PostCompact>
    after_tokens: <int,仅 PostCompact>
  SessionStart / SessionEnd / SessionResume:
    (仅通用字段)
  Stop:
    iter: <本轮 Run 走完的迭代数>
  ```

### 条件表达式- **F11**:条件表达式 `if:` 是一个对象,顶层只能出现 `all_of` 或 `any_of` 中**一个**——两个同时出现按加载错误处理;缺省 `if:` 视为无条件触发
- **F12**:`all_of` / `any_of` 的值是一个原子条件数组,每个原子条件包含 `field` 与 `match` 两个字段
  ```yaml
  if:
    all_of:
      - field: tool_name
        match: { type: exact, value: write_file }
      - field: tool_input.path
        match: { type: glob, value: "**/*.go" }
  ```
- **F13**:`field` 取 payload 中的字段路径,用 `.` 分隔嵌套(如 `tool_input.command`、`tool_input.path`);路径不存在按空字符串处理,不报错
- **F14**:`match` 取四种类型之一——
  - `{type: exact, value: "..."}`
  - `{type: glob, value: "..."}`
  - `{type: regex, value: "..."}`
  - `{type: not, inner: {type: ..., value/inner: ...}}`

  正则编译失败、`not` 缺少 `inner`、`inner` 自身非法均视为加载错误,跳过该 hook
- **F15**:条件求值在事件 emit 时实时进行,匹配器实例在加载期一次构造、运行期复用

### 动作类型- **F16**:`action.type` 取 `shell` / `prompt` / `http` / `subagent` 之一,各自的字段:

#### shell 动作- **F17**:`shell` 动作字段:`command`(字符串,由 `sh -c` 解释执行);执行时把事件 payload 序列化成单行 JSON 通过 stdin 传给命令——脚本侧可用 `jq` 取字段
- **F18**:`timeout` 默认 30 秒,超时按命令失败处理(记日志);async 时由后台 goroutine 异步执行,超时同样按失败处理
- **F19**:拦截事件(PreToolUse / UserPromptSubmit)下的 shell 同步执行:
  - `exit code == 2` 视为拦截命中,`stderr || stdout` 合并去尾换行后作为拒绝原因
  - `exit code == 0` 视为放行
  - 其它非零 exit code 视为 hook 失败但**不拦截**(记日志、Agent 继续)

#### prompt 动作- **F20**:`prompt` 动作字段:`text`(字符串);执行时把 `text` 加入"下一次 LLM 请求的 reminder 区"队列——所有 hook 注入的 prompt 按 hook 在 yaml 中的声明顺序拼接,置于现有 plan reminder 之后
- **F21**:reminder 队列仅本轮有效,下一轮重新装配;不入持久对话历史、不影响压缩
- **F22**:prompt 动作永不表达拦截——即使位于拦截类事件,动作执行后视为放行,仅做副作用注入

#### http 动作- **F23**:`http` 动作字段:`url`(必填)、`method`(默认 POST)、`headers`(可选键值对)、`body`(可选字符串模板,支持 `{{.field}}` Go text/template 取 payload 字段);缺省 `body` 时把事件 payload 序列化成 JSON 作为请求体
- **F24**:`timeout` 同 F18 默认 30 秒;async 时由后台 goroutine 异步执行
- **F25**:拦截事件下的 http 同步执行:
  - 响应 status 2xx 且 body 解析成 `{"decision":"block","reason":"..."}` 时视为拦截命中,reason 作为拒绝原因
  - 其它情况(非 2xx、body 缺 `decision` 字段、`decision` 非 `block`)视为放行
  - 网络错误、超时、JSON 解析失败按 hook 失败但**不拦截**#### subagent 动作- **F26**:`subagent` 动作字段:`agent_name`(必填)、`prompt`(必填字符串模板);**本期占位实现**——加载时校验字段完整、执行时仅记一行 stderr 日志 `[hook subagent] not yet implemented, skipped: <name>`、不报错也不拦截;后续章节对接子 Agent 后再补完整逻辑

### 执行控制- **F27**:`only_once: true` 标记的 hook 在同一会话内首次匹配成功并执行后被记录到 SessionRuntime 的内存集合(key = hook.name),后续相同事件再次匹配时直接跳过;`/clear`、`/resume` 进新会话时集合清空;**进程退出不写盘**——本期不做跨进程持久化
- **F28**:`async: true` 标记的 hook 在新 goroutine 中执行;加载期校验:若 hook.event ∈ {PreToolUse, UserPromptSubmit} 且 async=true,加载层报错并跳过该 hook(拦截类不允许异步——异步无法表达拦截信号)
- **F29**:所有 hook 失败(命令非 0 exit 但非拦截信号、HTTP 错误、超时等)写一行 stderr `[hook <name>] <event> failed: <reason>`;不写日志文件、不弹 UI 通知;async 失败同上、不重试

### 集成点- **F30**:Hook 系统由独立模块承载,内部至少包含规则加载器、引擎(事件分派 + 集合状态)、四类动作执行器、匹配器;Agent 在构造期通过选项注入 Hook 引擎
- **F31**:Agent.Run 等关键路径在 11 个事件时刻调用引擎的事件分派接口,接口返回拦截判定与待注入 prompt 集合
- **F32**:拦截结果整合:
  - **PreToolUse 拦截**:把 reason 拼成 `[hook <name>] <reason>` 形式当 tool_result 回灌,跳过权限引擎与真实工具执行;PhaseStart/PhaseEnd 事件按当前实现继续 emit,PhaseEnd 的 IsError=true
  - **UserPromptSubmit 拦截**:阻止该 user 消息写入对话历史,TUI 在输入框下方显示 `[hook <name>] <reason>`,焦点返回输入框等用户重新编辑
- **F33**:InjectedPrompts 集合在下一次 streamOnce 时拼到 reminder 串末尾,置于现有 plan reminder 之后;本轮无可拦截语义的事件(SessionStart 等)触发的 prompt 注入也走 reminder 队列

### Slash 命令- **F34**:新增内置 Slash 命令 `/hooks`,KindLocal,零参数:输出当前已加载的所有 hook 的精简列表,按 `event` 分组、每条一行 `  <name>  <event>  <action.type>  <flags>`,flags 含 `[once]` / `[async]` 标志;末尾追加 `Loaded from: <加载来源文件列表>`
- **F35**:无任何 hook 时输出 `No hooks loaded.`

## 非功能需求- **N1**:Hook 加载在进程启动期一次性完成;YAML 解析错误、字段缺失、event 未知、name 冲突、async + 拦截事件冲突、regex 编译失败等所有加载错误**一律 stderr 输出后继续启动**,不阻断 gcode 进程
- **N2**:事件分派接口必须支持 ctx 取消——拦截事件下同步等待、async 后台执行中 ctx 取消都应及时退出,避免卡死 Agent.Run
- **N3**:拦截事件下的同步 hook 串行执行,以单条 hook 的 timeout 累加;命令自身超时按 F18 处理,不再设全局上限
- **N4**:注入的 reminder 文本不入序列化对话历史、不参与 token 估算的"历史增长部分"(与 plan reminder 同语义)
- **N5**:only_once 内存集合放在 SessionRuntime 上,与 ActiveSkills 同生命周期;`/clear` 与 `/resume` 切换时清空
- **N6**:Hook payload JSON 序列化必须稳定字段顺序——key 按字母序,方便用户脚本对 JSON 直接 `grep`
- **N7**:扩展后的匹配器对权限规则与 Hook 条件共用同一实现,单元测试覆盖四种 type × 边界条件(空串、转义、嵌套 not、空 path)
- **N8**:subagent 占位日志输出固定格式 `[hook subagent] not yet implemented, skipped: <name>`,方便后续章节对接时文本搜索替换
- **N9**:hooks.yaml 文件不存在不报错;文件存在但整体 YAML 解析失败、顶层结构非法时打 stderr 但保持 gcode 启动
- **N10**:HTTP 动作的请求体模板渲染失败按 hook 失败处理;模板默认只支持 Go text/template 最基本字段访问,不开放函数

## 不做的事

- 不实现 subagent 动作的真实执行(仅占位日志),等后续章节对接 SubAgent 系统
- 不做 only_once 标记的跨进程持久化(重启进程后集合清空,hook 会重新触发一次)
- 不引入 hook 执行的显式优先级 / order 字段——加载层按 yaml 声明顺序自然有序
- 不做 hook 文件的热更新——加载在启动期一次完成,编辑文件后需重启 gcode 才生效
- 不在 TUI 渲染 hook 触发的可视化轨迹(仅 stderr 日志)
- 不实现 hook 之间的依赖 / 互斥关系
- 不为 hook 提供独立日志文件、专属环境变量配置入口
- 不做 hook 失败的重试机制
- 不支持 hook 配置文件的 @include 或继承

## 验收标准- **AC1**:写一份只含 `Bash(=git status)` 的精确规则到 `.gcode/permissions.yaml`,启动后调用 `git status` 被该规则命中、调用 `git status -s` 不命中
- **AC2**:写一份 `Bash(~^npm (install|test)$)` 的正则规则,启动后调用 `npm install` 命中、`npm run dev` 不命中;写法非法(如未闭合括号、正则编译失败)启动期 stderr 打印 `rule "Bash(~..." parse failed: ...` 并跳过该条规则
- **AC3**:写一份 `Bash(!~^rm)` 的反向正则规则,调用 `rm -rf .` 不命中(以 rm 起头)、调用 `ls -lh` 命中(不以 rm 起头)
- **AC4**:在 `<projectRoot>/.gcode/hooks.yaml` 写一条 PreToolUse hook——条件 `tool_name = write_file`,动作 `shell: "echo blocked >&2; exit 2"`;启动后 LLM 调用 write_file 工具时被拦截,tool_result 显示 `[hook <name>] blocked`,文件未被写入
- **AC5**:上面 AC4 的 hook 把动作命令改成 `exit 0`,再调用 write_file,hook 触发但放行,文件成功写入
- **AC6**:写一条 SessionStart hook——动作 `prompt: "用 zh-CN 回复"`;重启 gcode 后首轮对话中 LLM reminder 区能看到该文本(通过调试通道观察),后续轮不再注入
- **AC7**:写一条 PostToolUse hook——条件工具名为 write_file 且 `is_error=false`,动作 `shell: "gofmt -w \"$(jq -r .tool_input.path)\""`、async=true、timeout=5s;LLM 写一个 Go 文件后 gofmt 异步在后台执行,主对话流不暂停;命令失败时 stderr 打印失败日志、Agent 不中断
- **AC8**:写一条 async + PreToolUse 的 hook,启动 gcode 时 stderr 打印 `hook "<name>": async not allowed for blocking events, skipped` 并跳过该条
- **AC9**:写一条 only_once + PreUserMessage 的 hook,动作 `shell: "echo first-turn >&2"`;第一轮 PreUserMessage 时 stderr 出现 `first-turn`,后续轮不再出现;执行 `/clear` 进入新会话后下一轮再次出现 `first-turn`
- **AC10**:写一条 UserPromptSubmit hook——条件 prompt 正则匹配 `(?i)delete`,动作 `shell: "echo \"prompt contains delete keyword\" >&2; exit 2"`;用户在 TUI 输入"请帮我 delete 那个文件"时被拦截,输入框下方提示 `[hook <name>] prompt contains delete keyword`,消息未进入对话历史
- **AC11**:在 hooks.yaml 中写 `event: UnknownEvent`,启动后 stderr 打印 `hook "<name>": unknown event "UnknownEvent", skipped`,其余 hook 正常加载
- **AC12**:同时在用户级与项目级 hooks.yaml 各写一条 hook,启动后 `/hooks` 命令输出两条合并列表,末尾显示两个加载来源文件路径
- **AC13**:写一条 Stop hook——动作 `http: POST http://localhost:9999/done`;本地起一个 echo server,Agent.Run 自然停止后该 server 收到一次 POST 请求且 body 含 `"event":"Stop"`
- **AC14**:写一条 PreToolUse hook——动作 `http: POST http://localhost:9999/check`;本地 server 对 Bash 工具返回 `{"decision":"block","reason":"network policy"}`,Bash 调用被拦截、其它工具不受影响
- **AC15**:写一条 SessionStart hook——动作 `subagent: agent_name=foo, prompt=test`;启动后 stderr 出现 `[hook subagent] not yet implemented, skipped: <name>`,Agent 主流程不受影响
- **AC16**:在 hook 的 `if` 中同时写 `all_of` 与 `any_of` 两个键,启动 stderr 报错跳过该条,其余 hook 加载正常
- **AC17**:tmux 内启动 gcode,按 AC4 → AC6 → AC7 → AC10 顺序触发,整个过程不卡顿、无 panic(端到端见 checklist)
````

````markdown
# Hook 生命周期挂钩系统 Plan## 架构概览

本章拆为两个层次实现：

1. **权限匹配器升级层（permission 包内改造）**——把 Pattern 形态从字符串升级到结构化 Matcher 接口；新增 exact/regex/not 三种实现，glob 保留作为缺省类型。改造对外仅暴露语法升级和 stderr 错误回退,运行时 Allow/Deny 语义不变。

2. **Hook 主体层（新建 `internal/hook` 包）**——加载 YAML 规则、提供事件分派引擎、四类动作执行器；通过 11 个事件 emit 点接入 agent / tui。

模块构成：

- `permission.Matcher`(新)：匹配接口 + 四种实现的工厂
- `hook.Loader`(新)：YAML 解析 / 字段校验 / matcher 编译 / 双层文件合并
- `hook.Engine`(新)：事件分派、only_once 集合、动作执行器协调
- `hook.Executor`(新)：四类动作的执行入口（shell / prompt / http / subagent stub）
- `hook.Matcher`(薄包装)：复用 permission.Matcher，做字段路径取值与匹配组合
- `agent`/`tui` 改动：在生命周期 11 个时刻调 Engine.Dispatch
- `command`：新增 `/hooks` 内置命令

## 核心数据结构### permission.Matcher

```go
// Matcher 是规则匹配的统一接口；四种实现：matcherExact / matcherGlob / matcherRegex / matcherNot
type Matcher interface {
    Match(s string) bool
    String() string // 调试 / /hooks 输出用
}

// CompileMatcher 解析单条匹配描述串，返回 Matcher 或 error。
// 描述串规则：
//   "=value"  -> exact
//   "~regex"  -> regex
//   "!inner"  -> not(CompileMatcher("inner"))
//   "value"   -> glob（缺省，沿用现有 wildcard / matchPath 语义）
//
// Bash 工具沿用整串通配（matchCommand），其它沿用 matchPath。
// 调用方在 RuleSet 那侧通过 friendly 名分流到对应底层匹配函数；matcher 这边只关心模式串。
func CompileMatcher(pattern string) (Matcher, error)
```

### permission.Rule(改造)

```go
type Rule struct {
    Tool    string  // 不变
    Matcher Matcher // 替换原 Pattern 字符串；nil 表示「该工具全匹配」
    Allow   bool
    raw     string  // 原始模式串，仅供错误日志与调试
}
```

`parseRule` 升级：识别前缀，调用 `CompileMatcher` 构造 matcher。失败时返回 `(Rule{}, false, err)`；调用方（`toRuleSet`）记录 err 到 stderr 后跳过。

### hook.Rule

```go
type Rule struct {
    Name     string
    Event    Event           // 枚举 11 个事件
    If       *Condition      // nil 表示无条件
    Action   Action
    OnlyOnce bool
    Async    bool
    Timeout  time.Duration   // 0 用默认 30s

    source   string          // 来源文件路径，供 /hooks 显示
}

type Event string // const Event = "SessionStart" / "PreToolUse" / ...
```

### hook.Condition

```go
type Condition struct {
    Mode    CombineMode      // CombineAllOf 或 CombineAnyOf；二选一不混用
    Atoms   []AtomCondition
}

type AtomCondition struct {
    Field   string             // 形如 "tool_input.path"
    Matcher permission.Matcher // 复用四种匹配类型
}
```

### hook.Action

```go
type Action struct {
    Type     ActionType // "shell" | "prompt" | "http" | "subagent"
    Shell    *ShellAction
    Prompt   *PromptAction
    Http     *HttpAction
    Subagent *SubagentAction
}

type ShellAction    struct { Command string }
type PromptAction   struct { Text string }
type HttpAction     struct { URL, Method string; Headers map[string]string; Body string /* template */ }
type SubagentAction struct { AgentName, Prompt string }
```

### hook.Payload

```go
// Payload 是事件分派时携带的上下文数据；条件求值与动作输入都用它。
// 序列化为 JSON 时保证 key 字典序（N6）。
type Payload map[string]any
```

通用字段约定：`event`、`session_id`、`cwd`、`mode`，加上各事件特化字段。`GetByPath(payload, "tool_input.command")` 函数支持嵌套字段访问。

### hook.Engine

```go
type Engine struct {
    rules   []Rule                  // 按加载顺序
    sources []string                // 加载来源文件，供 /hooks 显示

    mu       sync.Mutex
    onceFired map[string]bool        // only_once 已触发的 hook name；ResetForNewSession 时清空
}

type DispatchResult struct {
    Blocked          bool
    Reason           string
    BlockingHookName string
    InjectedPrompts  []string // prompt 动作产生的文本，按声明序
}

func (e *Engine) Dispatch(ctx context.Context, event Event, payload Payload) DispatchResult
func (e *Engine) ResetForNewSession()
func (e *Engine) Sources() []string
func (e *Engine) Rules() []Rule
```

Dispatch 内部流程：
1. 过滤匹配 event 的 rule
2. 跳过 onceFired 中已触发的 only_once rule
3. 串行求值 if 条件
4. 命中条件后按 action.type 分发到 Executor
5. Async rule 起 goroutine、立即往下走
6. 同步 rule 等结果，拦截类事件下若 result 表达 block，累加到 DispatchResult，跳过后续同事件 rule
7. prompt 类 rule 把 text 累加到 InjectedPrompts

### Executor

```go
type Executor struct {
    httpClient *http.Client // 默认 timeout=30s，可被 rule 的 Timeout 覆盖
}

type ExecutionResult struct {
    Blocked bool
    Reason  string
    Prompt  string // 仅 prompt 动作非空
    Err     error  // hook 自身失败（不拦截）
}

func (x *Executor) Run(ctx context.Context, rule Rule, payload Payload, blocking bool) ExecutionResult
```

Run 内按 rule.Action.Type 调对应的私有 runShell / runPrompt / runHttp / runSubagent。

## 模块设计### 模块 A：permission.Matcher**职责：** 提供四种匹配类型的统一接口；CompileMatcher 解析前缀。
**对外接口：** `Matcher` 接口、`CompileMatcher(pattern string) (Matcher, error)`。
**依赖：** Go 标准库 `regexp`。
**改动文件：** `internal/permission/rule.go`(扩展 parseRule / matchRule)、新增 `internal/permission/matcher.go`。

### 模块 B：permission 错误日志**职责：** parseRule 失败时 stderr 打印失败规则与原因，原本静默跳过改为有声跳过。
**对外接口：** toRuleSet 内部行为变化，外部 API 不变。
**依赖：** 模块 A。

### 模块 C：hook.Loader**职责：** 扫描两层 YAML 文件、解析顶层 `hooks:` 数组、字段校验、Matcher 编译、合并去重。
**对外接口：** `Load(projectRoot string) (*Engine, []string)`——返回引擎与加载来源文件列表；所有错误走 stderr 不返回 error。
**依赖：** 模块 A、`gopkg.in/yaml.v3`、`hook.Engine`。
**校验项：** name 必填 + 跨文件冲突、event 枚举、if 顶层 all_of/any_of 互斥、action.type 枚举与子字段、async + 拦截事件冲突、Matcher 编译失败。

### 模块 D：hook.Engine**职责：** Dispatch 流程编排、only_once 集合管理、ResetForNewSession。
**对外接口：** 见上一节 Engine 结构体。
**依赖：** 模块 E。

### 模块 E：hook.Executor**职责：** 四类动作的执行——shell（sh -c + stdin JSON + exit code 2 拦截）、prompt（直接返回 InjectedPrompt）、http（POST JSON + decision=block 解析）、subagent（stub 占位日志）。
**对外接口：** `Run(ctx, rule, payload, blocking) ExecutionResult`。
**依赖：** Go 标准库 `os/exec`、`net/http`、`text/template`。

### 模块 F：hook.Matcher 包装**职责：** 把 permission.Matcher 应用到 payload 的字段路径上。
**对外接口：** `EvalCondition(cond *Condition, payload Payload) bool`、`GetByPath(payload Payload, path string) string`。
**依赖：** 模块 A。

### 模块 G：agent 接入**职责：** 在 agent.Run 等关键路径调 Engine.Dispatch；处理 PreToolUse 拦截、注入 reminder。
**对外接口：** `agent.WithHookEngine(*hook.Engine) Option`；agent 私有方法 `dispatchHook(ctx, event, payload) hook.DispatchResult`。
**依赖：** 模块 D。
**改动文件：** `internal/agent/agent.go`、`internal/agent/runtime.go`(SessionRuntime 加 `PendingReminders []string`、ResetForNewSession 清空)。

### 模块 H：tui 接入**职责：** SessionStart / SessionEnd / SessionResume / UserPromptSubmit / Notification 五个事件在 TUI 侧 emit；UserPromptSubmit 拦截集成到 submit() 流程。
**对外接口：** `*Model` 上私有方法 `dispatchSessionStart` / `dispatchSessionEnd` 等。
**依赖：** 模块 D。
**改动文件：** `internal/tui/tui.go`、`internal/tui/stream.go`、`internal/tui/commands.go`(/clear、/resume 触发 SessionEnd + SessionStart/Resume)。

### 模块 I：/hooks 命令**职责：** 输出已加载 hook 列表 + 加载来源文件。
**对外接口：** 注册到 `command.RegisterBuiltins`。
**依赖：** Model 实现 UI 接口暴露 `HookSources()` / `HookRules()` 查询方法。

### 模块 J：main wiring**职责：** 在 main.go 中调 `hook.Load(projectRoot)`，把 Engine 注入 agent 与 Model。
**改动文件：** `cmd/gcode/main.go`、`internal/tui/tui.go`(TUIParams 加 HookEngine 字段)。

## 模块交互**启动期数据流：**

```
main.go
  ├─ permission.NewEngine(root)             # 用升级后的 parseRule（stderr 报错）
  ├─ hook.Load(root)                        # 扫描两层 YAML、构造 Engine
  └─ tui.New(..., HookEngine=engine)
        ├─ agent.New(..., WithHookEngine(engine))
        └─ Model.hookEngine = engine
```

**SessionStart emit 时机：**

```
main.go 完成 wiring → tui.New 返回 Model → m.Run() → Init() 渲染 banner
                                                         │
                                                         └─ 首条 user 输入到达前
                                                            Init() 末尾派发 SessionStart 事件（cmd 队列）
```

实际接入：`Model.Init()` 返回的 tea.Cmd 中追加一个 `dispatchSessionStartCmd()`，该 cmd 同步调 Engine.Dispatch、收集 InjectedPrompts 注入到 runtime.PendingReminders、然后返回 nil。

**UserPromptSubmit 路径：**

```
submit() {
    text := trim(textarea.Value())
    if isSlash(text) { 走 dispatchSlash }
    result := hookEngine.Dispatch(ctx, "UserPromptSubmit", {prompt: text, ...})
    if result.Blocked {
        // 输入框下方显示 [hook <name>] reason，不消费输入
        return tea.Println(errorBlock(reason))
    }
    runtime.PendingReminders = append(runtime.PendingReminders, result.InjectedPrompts...)
    conv.AddUser(text)
    return beginTurn(...)
}
```

**PreToolUse 拦截路径：**

```
executeBatched(calls, mode, ch) {
    for each call {
        result := hookEngine.Dispatch(ctx, "PreToolUse", {tool_name, tool_input, ...})
        if result.Blocked {
            emit PhaseStart  // 用户仍能看到工具被尝试
            results[k] = hookBlockedResult(call.ID, result.BlockingHookName, result.Reason)
            emit PhaseEnd(IsError=true)
            continue
        }
        runtime.PendingReminders = append(runtime.PendingReminders, result.InjectedPrompts...)
        // ... 原有的权限 Check + 执行流程
        runtime.PendingReminders = append after PostToolUse Dispatch
    }
}
```

**Reminder 注入路径：**

```
Agent.Run() 第 iter 轮 streamOnce 之前：
    reminder := planReminder
    reminder += joinPendingReminders(runtime)  // 取出并清空 runtime.PendingReminders
    streamOnce(..., reminder, ...)
```

## 文件组织

```
gcode/
├── internal/
│   ├── permission/
│   │   ├── matcher.go        # 新增：Matcher 接口与四种实现
│   │   ├── matcher_test.go   # 新增：四种 type 覆盖
│   │   ├── rule.go           # 改造：parseRule 识别前缀、Rule 持有 Matcher
│   │   ├── rule_test.go      # 扩展：覆盖新语法
│   │   └── settings.go       # 改造：toRuleSet 报 stderr
│   ├── hook/                 # 全新包
│   │   ├── event.go          # 11 个 Event 常量 + 拦截类列表
│   │   ├── rule.go           # Rule / Condition / Action / Payload 数据结构
│   │   ├── matcher.go        # EvalCondition / GetByPath（复用 permission.Matcher）
│   │   ├── loader.go         # YAML 解析、字段校验、双层合并
│   │   ├── loader_test.go    # 校验项覆盖
│   │   ├── engine.go         # Engine + Dispatch 主流程 + only_once 集合
│   │   ├── engine_test.go    # 各事件 dispatch + 拦截 + reminder + once 覆盖
│   │   ├── executor.go       # 四类 action 执行器
│   │   ├── executor_test.go  # shell exit2 / http block / prompt / subagent stub 覆盖
│   │   └── doc.go            # 包注释
│   ├── agent/
│   │   ├── agent.go          # 增 dispatchHook 与 PreToolUse/PostToolUse/Stop/PreCompact 等 emit
│   │   ├── runtime.go        # SessionRuntime 加 PendingReminders、HookEngine 字段
│   │   └── runtime_test.go   # PendingReminders 覆盖
│   ├── command/
│   │   └── builtins.go       # 加 /hooks 命令
│   ├── tui/
│   │   ├── tui.go            # TUIParams 加 HookEngine、Model 持有
│   │   ├── stream.go         # submit() 内拦截 + SessionStart emit
│   │   ├── commands.go       # /clear / /resume 触发 SessionEnd + SessionStart/Resume
│   │   └── hooks.go          # 新增：/hooks handler、Model 的 hook 查询方法
│   └── ...
├── cmd/gcode/
│   └── main.go               # 加 hook.Load(root) 与 wiring
└── docs/ch12/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 匹配前缀语法 | `=` 精确、`!` 反向、`~` 正则、无前缀=glob | 单字符前缀让既有 `Bash(git *)` 这种写法继续 work；用户写新形式时直观（=foo 一眼就是精确） |
| 反向类型嵌套 | `!=value`、`!~regex`、`!glob` 都合法 | 反向是一元运算，对内层 matcher 取反；嵌套写法直接，不需要 `not()` 函数语法 |
| Matcher 接口而非 enum | Go interface | enum + switch 在 Match 时每次 type-assert；interface 更符合 Go 习惯，便于扩展（后续可加 `is_dir` 之类） |
| Hook 包独立 | `internal/hook/` | 与 `permission` 平级；hook 依赖 permission.Matcher，但 permission 不依赖 hook，无循环 |
| Event 用 string 常量而非 int | `type Event string` | YAML 直接对应、调试日志可读、加新事件不破坏已有 yaml 配置 |
| Payload 用 map[string]any | 而非结构体 | 11 个事件字段差异大；map + GetByPath 灵活；JSON 序列化时排序简单（json.Marshal 默认按 key 字母序） |
| Reminder 注入用 SessionRuntime 而非 Engine 状态 | `runtime.PendingReminders` | 与现有 plan reminder 同一注入点；下一轮自动清空；不污染 Engine |
| PreToolUse 拦截位置 | 权限 Check 之前 | 让用户能用 hook 早于权限引擎做安全策略；hook 拦截后甚至不调权限 Check |
| shell 用 sh -c | 而非 exec.Command 数组 | 用户写 hook 时常用 `\|`、`>` 这种 shell 语法；与 ch08 bash 工具一致 |
| HTTP 默认 POST + JSON body | 而非 GET | hook 多是「事件通知」语义，POST 更合理；用户需要 GET 时显式声明 method |
| HTTP body 用 Go text/template | 不开放函数 | template 已经够覆盖字段插值；开放函数容易出注入风险 |
| subagent 占位仅打日志 | 不报错也不阻塞 | spec 明确本期不实现，但配置应能加载——避免用户写早期配置后续章节直接生效 |
| only_once 用内存 map | 不写盘 | spec N5 明确本期不持久化；map 在 runtime 里，与 ActiveSkills 同生命周期 |
| 事件分派同步串行 | 多 hook 不并发 | 拦截语义需要顺序；同步 stderr 日志顺序也确定；async hook 单独起 goroutine 但 dispatch 不等 |
| 拦截类 sync timeout 不全局上限 | 单条 hook timeout 累加 | 用户配的 timeout 自己负责；全局上限会引入复杂语义 |
| /hooks 命令风格 | 与 /skill 对齐 | 已加载条目按事件分组、每条一行；末尾标加载来源 |
| 加载来源记录 | engine.sources []string | YAML 文件路径列表，/hooks 命令展示 |
````

````markdown
# Hook 生命周期挂钩系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `internal/permission/matcher.go` | Matcher 接口、四种实现、CompileMatcher 工厂 |
| 新建 | `internal/permission/matcher_test.go` | 四种 type × 边界条件覆盖 |
| 修改 | `internal/permission/rule.go` | parseRule 识别前缀、Rule 持有 Matcher 替代 Pattern 字符串、hitAny/matchRule 改造 |
| 修改 | `internal/permission/rule_test.go` | 扩展用例覆盖新语法 |
| 修改 | `internal/permission/settings.go` | toRuleSet 改造：失败 rule 走 stderr |
| 修改 | `internal/permission/settings_test.go` | 验证 stderr 报错与跳过逻辑 |
| 新建 | `internal/hook/doc.go` | 包注释 |
| 新建 | `internal/hook/event.go` | 11 个 Event 常量 + 拦截类列表 + IsBlocking 判定 |
| 新建 | `internal/hook/rule.go` | Rule / Condition / Action / Payload 数据结构 |
| 新建 | `internal/hook/matcher.go` | EvalCondition / GetByPath |
| 新建 | `internal/hook/loader.go` | YAML 解析、双层合并、字段校验 |
| 新建 | `internal/hook/loader_test.go` | 字段校验、加载错误、合并测试 |
| 新建 | `internal/hook/engine.go` | Engine + Dispatch 主流程 + only_once |
| 新建 | `internal/hook/engine_test.go` | 各事件 dispatch、拦截、reminder、once 覆盖 |
| 新建 | `internal/hook/executor.go` | 四类 action 执行器 |
| 新建 | `internal/hook/executor_test.go` | shell exit2、http block、prompt、subagent stub |
| 修改 | `internal/agent/runtime.go` | SessionRuntime 加 PendingReminders + HookEngine 字段 + ResetForNewSession 清空 |
| 修改 | `internal/agent/runtime_test.go` | 验证 PendingReminders 行为 |
| 修改 | `internal/agent/agent.go` | WithHookEngine 选项、11 个 emit 点（部分由 tui 触发，agent 负责 PreUserMessage/PreToolUse/PostToolUse/PreCompact/PostCompact/Stop/Notification） |
| 修改 | `internal/agent/agent_test.go` | 拦截路径测试 |
| 新建 | `internal/tui/hooks.go` | /hooks 命令 handler、Model 的 hook 查询方法 |
| 修改 | `internal/tui/tui.go` | TUIParams 加 HookEngine、Model 持有；Init 触发 SessionStart |
| 修改 | `internal/tui/stream.go` | submit() 内 UserPromptSubmit dispatch + 拦截集成 |
| 修改 | `internal/tui/commands.go` | /clear、/resume 触发 SessionEnd + SessionStart/Resume |
| 修改 | `internal/command/builtins.go` | 加 /hooks 内置命令 |
| 修改 | `internal/command/ui.go` | UI 接口加 hook 查询方法 |
| 修改 | `cmd/gcode/main.go` | 加 hook.Load(root) 与 wiring；SessionEnd defer |

## T1: 实现 permission.Matcher 接口与四种类型**文件：** `internal/permission/matcher.go`
**依赖：** 无
**步骤：**
1. 新建 `matcher.go`，声明接口 `type Matcher interface { Match(s string) bool; String() string }`
2. 实现 4 个类型：
   - `matcherExact{value string}`：`Match` 返回 `s == value`
   - `matcherGlob{pattern string, isCommand bool}`：command 模式用 wildcard，否则用 matchPath；通过 `String()` 返回 `pattern`
   - `matcherRegex{re *regexp.Regexp, src string}`：`Match` 返回 `re.MatchString(s)`
   - `matcherNot{inner Matcher}`：`Match` 返回 `!inner.Match(s)`
3. 实现工厂 `CompileMatcher(pattern string, isCommand bool) (Matcher, error)`：
   - 空串 → 错误 `"empty matcher pattern"`
   - `=value` → `matcherExact{value}`
   - `~regex` → `regexp.Compile`，错误透传
   - `!inner` → 递归 `CompileMatcher(inner, isCommand)` 包装
   - 其它 → `matcherGlob{pattern, isCommand}`
4. matcherGlob 的 Match 内部调 `matchCommand(pattern, s)`(isCommand=true) 或 `matchPath(pattern, s)`(false)
5. 写 doc comment 解释每个 Matcher 类型的语义

**验证：** `go build ./internal/permission/...` 编译通过

## T2: matcher 单元测试**文件：** `internal/permission/matcher_test.go`
**依赖：** T1
**步骤：**
1. 覆盖 4 种类型各自的命中/不命中用例
2. `=git status` 命中 `git status`、不命中 `git status -s`
3. `~^npm (install|test)$` 命中 `npm install`、不命中 `npm run dev`
4. `!=foo` 不命中 `foo`、命中 `bar`
5. `!~^rm` 命中 `ls -lh`、不命中 `rm -rf .`
6. `!git *` 命中 `npm install`、不命中 `git status`（嵌套 not + glob）
7. 编译失败：`~[invalid` 应返回 error
8. 空串：`""` 应返回 error
9. 表驱动写法，每个用例附 `t.Errorf` 描述

**验证：** `go test ./internal/permission/ -run TestMatcher -v` 通过

## T3: 升级 permission.Rule 与 parseRule**文件：** `internal/permission/rule.go`
**依赖：** T1
**步骤：**
1. Rule 结构体改：去 Pattern 字段、加 Matcher（Matcher 类型）和 raw（string，原始描述）
2. parseRule 签名改：`func parseRule(s string) (Rule, bool, error)`——返回 err 让 toRuleSet 写日志
3. parseRule 内部：剥出 tool 与 pattern 后调 `CompileMatcher(pattern, tool == "Bash")`；空 pattern 仍按 nil matcher 表示"全匹配"
4. 改造 `matchRule(r Rule, target string)`：r.Matcher == nil 返回 true（全匹配），否则 `r.Matcher.Match(target)`
5. `escapeGlob` 保留不变，仅供 ch08 自动生成的精确规则使用
6. doc comment 更新说明四种语法

**验证：** `go build ./internal/permission/...` 编译通过

## T4: 升级 toRuleSet 错误日志**文件：** `internal/permission/settings.go`
**依赖：** T3
**步骤：**
1. toRuleSet 改造：parseRule 失败时调 `fmt.Fprintf(os.Stderr, "rule %q parse failed: %s\n", str, err)`
2. 加 `import "fmt"` `import "os"`（os 可能已在）
3. 加注释说明：失败的 rule 不进入 RuleSet，但其它 rule 不受影响

**验证：** `go build ./internal/permission/...` 编译通过

## T5: 扩展 rule_test 与 settings_test**文件：** `internal/permission/rule_test.go`、`internal/permission/settings_test.go`
**依赖：** T3、T4
**步骤：**
1. rule_test：补充用例
   - `Bash(=git status)` 精确匹配
   - `Bash(~^npm.*)` 正则匹配
   - `Bash(!~^rm)` 反向正则
   - `Write(**/*.go)` glob 沿用（确认向后兼容）
2. settings_test：构造一份含非法 rule 的 yaml，验证 toRuleSet 返回的 RuleSet 不含该 rule（用 stderr 输出 capture 不重要，验证 RuleSet.allow/deny 长度即可）
3. 旧测试 TestMatchCommand / TestMatchPath 改成调用 matcher 的形式或保留底层函数测试

**验证：** `go test ./internal/permission/... -v` 全部通过

## T6: hook 包基础数据结构**文件：** `internal/hook/doc.go`、`internal/hook/event.go`、`internal/hook/rule.go`
**依赖：** 无
**步骤：**
1. `doc.go`：包注释，描述本包职责
2. `event.go`：
   - `type Event string`
   - 11 个常量 EventSessionStart / EventSessionEnd / EventSessionResume / EventUserPromptSubmit / EventStop / EventPreUserMessage / EventPreToolUse / EventPostToolUse / EventPreCompact / EventPostCompact / EventNotification
   - `var allEvents = []Event{...}` 用于枚举校验
   - `var blockingEvents = map[Event]bool{EventPreToolUse: true, EventUserPromptSubmit: true}`
   - 函数 `IsBlocking(e Event) bool`、`ParseEvent(s string) (Event, bool)`
3. `rule.go`：
   - `Rule`、`Condition`、`AtomCondition`、`Action`、`ShellAction`、`PromptAction`、`HttpAction`、`SubagentAction`、`ActionType`、`CombineMode` 等结构与常量
   - `Payload` 类型别名 `type Payload map[string]any`

**验证：** `go build ./internal/hook/...` 编译通过

## T7: hook.Matcher 字段路径求值**文件：** `internal/hook/matcher.go`
**依赖：** T6、T1
**步骤：**
1. `GetByPath(p Payload, path string) string`：按 `.` 分隔；递归取值；中途遇 nil/非 map 返回空串
2. 字段值非字符串时：bool/数字转字符串（`fmt.Sprint`）；嵌套对象转 JSON（json.Marshal）
3. `EvalCondition(c *Condition, p Payload) bool`：
   - c == nil → true
   - 遍历 c.Atoms，每条用 GetByPath + AtomCondition.Matcher.Match
   - CombineAllOf 要求全部 true、CombineAnyOf 要求至少一个 true

**验证：** `go build ./internal/hook/...` 编译通过

## T8: hook.Loader YAML 解析**文件：** `internal/hook/loader.go`
**依赖：** T6、T7、T1
**步骤：**
1. 定义 YAML 中间结构 `fileSchema`：`Hooks []hookYAML`，hookYAML 含 Name/Event/If/Action/OnlyOnce/Async/Timeout 字符串/对象字段
2. `Load(projectRoot string) (*Engine, []string)` 主入口：
   - 计算两个候选路径：`<projectRoot>/.gcode/hooks.yaml`、`<home>/.gcode/hooks.yaml`
   - 文件不存在跳过；存在但解析失败 stderr 输出后跳过
   - 对每个 hookYAML 调 `compileRule(src, idx, raw) (Rule, error)`
   - 累积成功的 rule、stderr 输出失败的 rule
   - 跨文件 name 冲突时跳过后者
3. `compileRule` 内做字段校验：
   - name 非空
   - event 枚举（ParseEvent）
   - action.type 枚举与子字段必填（shell.command、prompt.text、http.url、subagent.agent_name+prompt）
   - if 顶层 all_of / any_of 互斥
   - 每个 AtomCondition 的 match.type ∈ {exact,glob,regex,not} 且 value/inner 字段完整
   - async + IsBlocking(event) → 报错跳过
   - timeout 解析为 time.Duration（go time.ParseDuration），缺省 30s
4. Matcher 编译用 permission.CompileMatcher；命令类匹配（即工具是 Bash）这里不区分——hook 上下文都是 payload 字段值，统一按非 command 形式（matchPath 的 glob 语义）；正则不变；exact 不变；not 不变。
   - **决策修正**：hook 的 matcher 在初始化时统一传 `isCommand=false`，使 glob 走 `matchPath`（段内 `*` 不跨 `/`，与文件 glob 一致；这对 tool_input.command 这种字段是有点限制——但用户可以改用 regex 表达 shell 字符串匹配，文档需说清）

**验证：** `go build ./internal/hook/...` 编译通过

## T9: hook.Loader 测试**文件：** `internal/hook/loader_test.go`
**依赖：** T8
**步骤：**
1. 临时目录场景：写一份合法 hooks.yaml（含 2 条 hook），Load 返回 Engine 含 2 条 rule
2. 字段缺失：name 空、event 不存在、action.type 无效 → 跳过该条但其它通过
3. all_of + any_of 同时存在 → 跳过该条
4. async + PreToolUse → 跳过该条且 stderr 含 `async not allowed for blocking events`
5. 跨文件同名冲突 → 项目级保留、用户级跳过
6. matcher 编译失败（非法正则） → 跳过该条

**验证：** `go test ./internal/hook/ -run TestLoader -v` 通过

## T10: hook.Engine 与 Dispatch 主流程**文件：** `internal/hook/engine.go`
**依赖：** T6、T7
**步骤：**
1. Engine 结构体：rules、sources、mu、onceFired
2. `NewEngine(rules []Rule, sources []string) *Engine`
3. `Dispatch(ctx, event, payload) DispatchResult`：
   - 遍历 rules，跳过非本事件
   - 加锁查 onceFired，命中跳过；ResetForNewSession 清空
   - EvalCondition；不通过跳过
   - 命中后：
     - async=true 起 goroutine 调 executor.Run，立即继续（不等结果、不进入 InjectedPrompts 与 Blocked 判定）
     - 同步：调 executor.Run，blocking 参数 = IsBlocking(event)
   - 同步结果处理：
     - result.Err 非 nil → stderr 日志 `[hook <name>] <event> failed: <reason>`，继续下一个 rule（不拦截）
     - result.Prompt 非空 → 加入 InjectedPrompts
     - result.Blocked 且 IsBlocking(event) → 设置 DispatchResult.Blocked + Reason + BlockingHookName，break 退出循环
   - 命中且执行无 fatal err 的 rule，若 OnlyOnce → 加入 onceFired
4. `ResetForNewSession()`：加锁清空 onceFired
5. `Sources() []string`、`Rules() []Rule`

**验证：** `go build ./internal/hook/...` 编译通过

## T11: hook.Executor 四类动作执行**文件：** `internal/hook/executor.go`
**依赖：** T6
**步骤：**
1. `Executor` 结构体（无字段或仅 httpClient）
2. `NewExecutor() *Executor`
3. `Run(ctx, rule, payload, blocking) ExecutionResult` 分发到下面四个内部方法
4. `runShell(ctx, sa *ShellAction, payload, blocking, timeout) ExecutionResult`：
   - 调 `exec.CommandContext(ctx, "sh", "-c", sa.Command)`
   - stdin 写入 `json.Marshal(payload)` 单行
   - 等 cmd 完成；超时按失败处理
   - blocking && exit code 2 → Blocked=true、Reason=stderr/stdout 合并去尾
   - exit code 0 → 不拦截不报错
   - 其它非 0 exit → Err=fmt.Errorf("exit %d: %s", code, stderr)
5. `runPrompt(pa *PromptAction)` → ExecutionResult{Prompt: pa.Text}
6. `runHttp(ctx, ha *HttpAction, payload, blocking, timeout)`：
   - 默认 method=POST
   - body：缺省时 `json.Marshal(payload)`；否则 Go text/template 渲染 payload
   - 用 http.Client{Timeout: timeout} POST
   - status 2xx 且 body 含 `{"decision":"block","reason":"..."}` → Blocked=true
   - 网络错/超时/JSON 解析失败 → Err
7. `runSubagent(sa *SubagentAction)`：仅 `fmt.Fprintf(os.Stderr, "[hook subagent] not yet implemented, skipped: %s\n", sa.AgentName)`，返回空 ExecutionResult
8. payload JSON 序列化用一个共享辅助 `marshalSorted(p Payload) []byte`，保证 key 字典序

**验证：** `go build ./internal/hook/...` 编译通过

## T12: executor 单元测试**文件：** `internal/hook/executor_test.go`
**依赖：** T11
**步骤：**
1. shell exit 2 with stderr → Blocked + Reason 含 stderr
2. shell exit 0 → 放行不报错
3. shell exit 1 → Err 非 nil 不拦截
4. shell stdin JSON 解析：脚本读 stdin 后 echo 出来，验证 key 字典序
5. shell timeout：sleep 2s + timeout 100ms → Err 含 "timed out" 或 context.DeadlineExceeded
6. prompt → Prompt 字段非空
7. http with httptest.Server 返回 `{"decision":"block","reason":"x"}` → Blocked=true
8. http with 5xx → Err 非 nil
9. http 模板 body 含 `{{.event}}` → server 收到正确字段
10. subagent → stderr 含占位文本

**验证：** `go test ./internal/hook/ -run TestExecutor -v` 通过

## T13: hook.Engine 测试**文件：** `internal/hook/engine_test.go`
**依赖：** T10、T11
**步骤：**
1. 多 rule 同事件按声明序执行
2. 拦截类事件下首个 Blocked 的 rule 中断后续
3. 非拦截类事件下 Blocked 字段不传递（fake exit code 2 但 IsBlocking=false 也不 set Blocked）
4. prompt rule 的 Prompt 累加到 InjectedPrompts
5. only_once 在首次执行后被加入 onceFired，第二次 Dispatch 跳过
6. ResetForNewSession 后 only_once 重置
7. async rule 不进入 Blocked 判定（用 wait group 验证 goroutine 已起）

**验证：** `go test ./internal/hook/ -run TestEngine -v` 通过

## T14: agent SessionRuntime 扩展**文件：** `internal/agent/runtime.go`、`internal/agent/runtime_test.go`
**依赖：** T6
**步骤：**
1. SessionRuntime 加字段：`PendingReminders []string`、`HookEngine *hook.Engine`
2. `NewSessionRuntime` 初始化空 slice
3. `ResetForNewSession` 清空 PendingReminders、若 HookEngine 非 nil 调 HookEngine.ResetForNewSession()
4. 新增 `AppendReminders(prompts []string)` 加锁追加
5. 新增 `TakeReminders() []string` 加锁取出并清空
6. 测试覆盖：AppendReminders + TakeReminders 单线程行为；ResetForNewSession 清空

**验证：** `go test ./internal/agent/ -run TestSessionRuntime -v` 通过

## T15: agent.WithHookEngine 选项与 emit 框架**文件：** `internal/agent/runtime.go`、`internal/agent/agent.go`
**依赖：** T14
**步骤：**
1. runtime.go：加 `WithHookEngine(e *hook.Engine) Option`，赋值到 `a.hookEngine`
2. agent.go：Agent 结构体加字段 `hookEngine *hook.Engine`
3. 私有方法 `(a *Agent) dispatchHook(ctx, event, payload) hook.DispatchResult`：
   - hookEngine == nil → 返回空 DispatchResult
   - 调 hookEngine.Dispatch
   - 把 InjectedPrompts 调 runtime.AppendReminders
   - 返回结果（保留 Blocked + Reason 供 PreToolUse 用）
4. 私有方法 `(a *Agent) buildReminder(mode permission.Mode, iter int) string`：
   - 原 planReminder + runtime.TakeReminders() join("\n\n")

**验证：** `go build ./internal/agent/...` 编译通过

## T16: agent 各事件 emit 接入**文件：** `internal/agent/agent.go`
**依赖：** T15
**步骤：**
1. Run 开始处补 `dispatchHook(ctx, EventStop, ...)` 入口准备——实际 Stop 在 `Done: true` emit 前调用
2. 每轮 iter 顶部、manageContextAuto 之前调 `dispatchHook(ctx, EventPreCompact, payload{trigger:"auto"})`；ManageContext 返回后 emit `EventPostCompact` 带 before/after tokens
3. emergencyCompactAndDecide：同样 PreCompact/PostCompact，trigger="emergency"
4. streamOnce 调 provider.Stream 之前 emit `EventPreUserMessage`，payload 含 conversation 末尾 user 消息
5. 把 reminder 串改造：取 `a.buildReminder(mode, iter)` 替代原裸的 `prompt.PlanReminder(full)`
6. executeBatched 改造：
   - 单工具循环开始处 emit PreToolUse，payload 含 tool_name、tool_input；Blocked=true 时构造 hookBlockedResult、emit PhaseStart/PhaseEnd（IsError=true），continue
   - tool 拿到 result 后、emit PhaseEnd 之前 emit PostToolUse，payload 含 tool_name、tool_input、tool_result、is_error
7. emit Done 之前调 `EventStop`，payload{iter}
8. emit Approval 之前调 `EventNotification`，payload{kind:"approval", detail: tool_name}
9. emit Err 之前调 `EventNotification`，payload{kind:"stream_error", detail: err.Error()}
10. 拦截结果整合：定义 `hookBlockedResult(callID, hookName, reason) llm.ToolResult`：Content=`[hook <name>] <reason>`、IsError=true

**验证：** `go build ./internal/agent/...` 编译通过

## T17: agent_test 拦截路径与 emit 覆盖**文件：** `internal/agent/agent_test.go`、`internal/agent/runtime_test.go`
**依赖：** T16
**步骤：**
1. 构造一个 fake provider + 注入 fake hook.Engine（mockEngine 实现相同接口）
2. 测试：PreToolUse 拦截时工具结果是 hookBlockedResult 形式、PhaseStart/PhaseEnd 仍 emit
3. 测试：PreUserMessage 注入的 prompt 在下一次 streamOnce 的 reminder 串中可见
4. 测试：Stop 事件在 Done 前一刻被 emit
5. 由于 Engine 类型不是接口，可能需要重构成接口或用 nil Engine 路径（更简单：在测试里直接 New 真实 Engine，注入合成 rules）

**验证：** `go test ./internal/agent/ -run TestHook -v` 通过

## T18: tui Model 持有 HookEngine**文件：** `internal/tui/tui.go`
**依赖：** T15
**步骤：**
1. TUIParams 加 `HookEngine *hook.Engine`
2. Model 加字段 `hookEngine *hook.Engine`
3. New 内：
   - 把 params.HookEngine 赋给 m.hookEngine 与 runtime.HookEngine
   - 构造 agent 时加 `agent.WithHookEngine(params.HookEngine)`
4. Init 末尾添加 `cmd := dispatchSessionStart(m)` 拼到 batch

**验证：** `go build ./internal/tui/...` 编译通过

## T19: tui UserPromptSubmit 拦截集成**文件：** `internal/tui/stream.go`
**依赖：** T18
**步骤：**
1. submit() 重写：
   - 现有的 trim 与 slash 分发保留
   - 非 slash 路径进入 Hook 拦截判定前
   - 构造 payload：`hook.Payload{"event": "UserPromptSubmit", "session_id": ..., "cwd": m.cwd, "mode": m.mode.String(), "prompt": text}`
   - 调 m.hookEngine.Dispatch(m.ctx, EventUserPromptSubmit, payload)
   - Blocked=true：返回 tea.Println(errorBlock(fmt.Errorf("[hook %s] %s", result.BlockingHookName, result.Reason))) 不消费 textarea
   - 否则：把 InjectedPrompts 经 runtime.AppendReminders；conv.AddUser(text)；beginTurn
2. 提供辅助函数 `(m *Model) basePayload(event hook.Event) hook.Payload` 构造通用字段

**验证：** `go build ./internal/tui/...` 编译通过

## T20: tui SessionStart / End / Resume**文件：** `internal/tui/tui.go`、`internal/tui/commands.go`、`internal/tui/stream.go`
**依赖：** T18、T19
**步骤：**
1. 新增 `dispatchSessionStart(m *Model) tea.Cmd`：构造 payload + 调 Engine.Dispatch + InjectedPrompts 写入 runtime + 返回 nil cmd
2. 新增 `dispatchSessionEnd(m *Model)`：仅同步调 Dispatch，不返回 cmd
3. 新增 `dispatchSessionResume(m *Model) tea.Cmd`：同 SessionStart 流程，event 改为 SessionResume
4. Init 末尾 batch 中调 dispatchSessionStart
5. /clear handler 内：先 dispatchSessionEnd，再 ResetForNewSession，最后 dispatchSessionStart
6. /resume handler 选中会话恢复完毕后：先 dispatchSessionEnd（旧），切到新会话后 dispatchSessionResume
7. handleExit 内：dispatchSessionEnd 后再退出
8. tui.Model.Run 退出前：在 main.go 的 defer 中 dispatchSessionEnd？或者 handleExit 即可
   - 简化：仅 /clear、/resume、/exit、ctrl+c 退出几条路径调；main.go defer 兜底（确保 ctrl+c 一退出也 emit）
   - 实际：在 tui.Run() 返回后由 main 调一次 hookEngine.Dispatch(EventSessionEnd)；tui 内的 /clear、/resume 自己控制

**验证：** `go build ./internal/tui/...` 编译通过

## T21: /hooks 命令**文件：** `internal/tui/hooks.go`、`internal/command/builtins.go`、`internal/command/ui.go`
**依赖：** T6、T10、T18
**步骤：**
1. UI 接口加方法 `HookSources() []string`、`HookRules() []hook.Rule`
2. Model 实现这两个方法（读 m.hookEngine 字段）
3. 新增 `internal/tui/hooks.go`，实现 handleHooks(ctx, ui)：
   - 取 rules 与 sources
   - 空时 println `No hooks loaded.`
   - 否则按 event 分组（保留 yaml 声明顺序）、每条一行 `  <name>  <event>  <action.type>  [once] [async]`
   - 末尾 `Loaded from: file1, file2`
4. builtins.go 注册新命令 `/hooks`，KindLocal，描述「列出已加载的 hook 列表」

**验证：** `go build ./...` 编译通过

## T22: main.go wiring**文件：** `cmd/gcode/main.go`
**依赖：** T8、T18
**步骤：**
1. 在 permission.NewEngine 之后调 `hookEngine := hook.Load(root)`
2. tui.New 传 HookEngine
3. m.Run() 之后调 `if hookEngine != nil { _ = hookEngine.Dispatch(context.Background(), hook.EventSessionEnd, basePayload) }` 兜底 SessionEnd
4. import 加 `gcode/internal/hook`

**验证：** `go build ./cmd/gcode/...` 编译通过

## T23: 整体编译与测试**文件：** —
**依赖：** T1-T22 全部
**步骤：**
1. `go build ./...` 通过
2. `go test ./...` 通过——hooks 相关测试 + 既有测试都得过

**验证：** 上述两条命令本地通过

## T24: 修复回归**文件：** 根据测试输出决定
**依赖：** T23
**步骤：**
1. 修复 ch08 / ch11 等老测试因 Matcher 改造而失败的用例
2. 修复 ch10 / ch11 测试因 /hooks 命令加入而影响排序或数量的用例
3. 重新跑全套测试

**验证：** `go test ./...` 通过

## T25: tmux 端到端实跑（验收 AC17 与 checklist 端到端场景）**文件：** `.gcode/hooks.yaml` 临时测试配置
**依赖：** T23、T24
**步骤：**
1. 写测试 hooks.yaml：包含 AC4-AC15 各典型场景的 hook
2. tmux 新建 session 启动 gcode
3. 依次触发：write_file 工具调用、含 delete 关键字的用户输入、git 命令、Stop 事件
4. 观察 stderr 日志、tool_result 内容、reminder 注入是否符合预期
5. 全程不 panic、不卡顿

**验证：** 见 checklist.md

## 执行顺序

```
T1 → T2 → T3 → T4 → T5            # permission Matcher 扩展
T6 → T7 → T8 → T9                 # hook 基础结构 + Loader
T10 → T13                         # Engine
T11 → T12                         # Executor（与 Engine 并行）
T14 → T15 → T16 → T17             # agent 接入
T18 → T19 → T20                   # tui 接入
T21                               # /hooks 命令
T22                               # main wiring
T23 → T24                         # 整体编译测试
T25                               # tmux 实跑验收
```

并行机会：
- T11/T12 与 T10/T13 互不依赖,可并行
- T11 与 T8 在 T6 完成后可并行
- T17 必须在 T16 之后
- T19 之前 T18 必须先完成
````

````markdown
# Hook 生命周期挂钩系统 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### 权限匹配器扩展

- [ ] permission.Matcher 接口存在,四种实现(exact / glob / regex / not)各自可单独编译并运行(验证：`go test ./internal/permission/ -run TestMatcher -v` 通过)
- [ ] permission.Rule 已替换 Pattern 为 Matcher 字段,parseRule 能识别 `=` / `~` / `!` 前缀(验证：`go test ./internal/permission/ -run TestParseRule -v` 通过)
- [ ] toRuleSet 在 parseRule 失败时输出 stderr 错误日志(验证：单测构造非法 rule 串,捕获 os.Stderr 输出含 `parse failed`)

### Hook 包

- [ ] internal/hook 包存在且编译通过(验证:`go build ./internal/hook/...`)
- [ ] 11 个 Event 常量全部声明且 IsBlocking 仅对 PreToolUse / UserPromptSubmit 返回 true(验证:`go test ./internal/hook/ -run TestEvent -v`)
- [ ] Loader 能解析合法 YAML 并构造 Engine(验证:loader_test 全部通过)
- [ ] Loader 对字段缺失 / 枚举错 / async+拦截事件冲突 / matcher 编译失败均报 stderr 并跳过该条(验证:对应 loader_test 子用例通过)
- [ ] Engine.Dispatch 按声明顺序执行 rule 且拦截后中断后续(验证:engine_test TestDispatchBlocking 通过)
- [ ] Executor 的 shell exit 2 触发 Blocked、exit 0 放行、其它非 0 视为失败不拦截(验证:executor_test TestRunShell* 通过)
- [ ] Executor 的 HTTP 在 body 含 `{"decision":"block","reason":"..."}` 时触发 Blocked(验证:executor_test TestRunHttp* 通过)
- [ ] Executor 的 prompt 动作通过 ExecutionResult.Prompt 字段返回文本(验证:executor_test TestRunPrompt 通过)
- [ ] Executor 的 subagent 动作仅 stderr 输出占位日志、不阻塞(验证:executor_test TestRunSubagent 通过)
- [ ] only_once 状态在 SessionRuntime 上,/clear 与 /resume 时被 ResetForNewSession 清空(验证:runtime_test TestResetForNewSession 通过)

### agent / tui 集成

- [ ] agent.WithHookEngine 选项存在,agent 内部 dispatchHook 在 11 个 emit 点全部调用(验证:agent_test TestHookEmit 覆盖每个事件)
- [ ] tui submit() 在 UserPromptSubmit 拦截时不消费 textarea、显示 errorBlock(验证:tui_test TestSubmitBlocked 通过)
- [ ] tui Init() 末尾派发 SessionStart 事件(验证:tui_test TestInitDispatchSessionStart 或集成测试)
- [ ] /clear / /resume / /exit 触发 SessionEnd(验证:tui_test TestClearDispatchSessionEnd 等)
- [ ] main.go 退出前兜底 SessionEnd(验证:main 调用链审查)
- [ ] /hooks 命令注册到命令表(验证:tui_test 中 /hooks 命令存在 + 输出格式正确)
- [ ] PendingReminders 在 Agent.Run 取出后被清空(验证:runtime_test TestTakeReminders 通过)

## 集成

- [ ] hook.Engine 与 permission.Matcher 共用同一套匹配实现(验证:hook 包不重复实现 exact/regex/glob)
- [ ] hook.Engine 接入 agent.Run 后所有现有 agent_test 不破坏(验证:`go test ./internal/agent/...` 全过)
- [ ] hook.Engine 接入 tui 后所有现有 tui_test 不破坏(验证:`go test ./internal/tui/...` 全过)
- [ ] PreToolUse 拦截结果当 tool_result 回灌后,LLM 视角看到的是 `IsError=true` 的 ToolResult,Content 含 `[hook <name>] <reason>`(验证:agent_test 检查 results[k] 字段)
- [ ] reminder 注入路径与 plan reminder 协同——同一轮 LLM 请求的 reminder 串同时含两类(验证:agent_test 中构造 plan 模式 + hook prompt 注入,断言 reminder 串包含两段)

## 编译与测试

- [ ] 项目编译无错误:`go build ./...`
- [ ] 所有单元测试通过:`go test ./...`
- [ ] vet 检查通过:`go vet ./...`(无配置 lint 则跳过)

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证人工/可视化行为。

### 场景 1:PreToolUse shell 拦截 write_file**预置:** 在 `.gcode/hooks.yaml` 写一条 hook:
```yaml
hooks:
  - name: block-write
    event: PreToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
    action:
      type: shell
      command: "echo blocked by hook >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 给 LLM 输入"创建一个文件 hello.txt 内容是 hi"
- [ ] LLM 应触发 write_file,工具被拦截
- [ ] scrollback 内 tool_result 显示 `[hook block-write] blocked by hook`、文件未创建
- [ ] LLM 收到反馈后调整回应,不死循环

### 场景 2:SessionStart prompt 注入**预置:**
```yaml
hooks:
  - name: zh-cn-default
    event: SessionStart
    action:
      type: prompt
      text: "默认用 zh-CN 回复"
```

**步骤:**
- [ ] tmux 重启 gcode
- [ ] 立刻发一句英文输入"hi there"
- [ ] LLM 应该用中文回复(因为 reminder 区注入了 zh-CN 指令)

### 场景 3:PostToolUse async shell 后台 gofmt**预置:**
```yaml
hooks:
  - name: gofmt-after-write
    event: PostToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
        - field: tool_input.path
          match: { type: glob, value: "**/*.go" }
        - field: is_error
          match: { type: exact, value: "false" }
    action:
      type: shell
      command: "gofmt -w \"$(jq -r .tool_input.path)\""
    async: true
    timeout: 5s
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 写一个故意排版不整齐的 Go 文件(如缩进错乱)
- [ ] LLM 完成写入后主对话立即进入下一轮,不停顿
- [ ] 验证文件被 gofmt 格式化(可手动 `cat` 该文件)

### 场景 4:UserPromptSubmit 拦截 delete 关键字**预置:**
```yaml
hooks:
  - name: warn-delete
    event: UserPromptSubmit
    if:
      all_of:
        - field: prompt
          match: { type: regex, value: "(?i)delete" }
    action:
      type: shell
      command: "echo \"用户消息含 delete 关键字\" >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入"请帮我 delete 那个文件"
- [ ] 输入被拦截,scrollback 内显示 `[hook warn-delete] 用户消息含 delete 关键字`
- [ ] 输入框内容仍在(被退回用户重新编辑)
- [ ] LLM 端未收到这条 user 消息(不发起请求)

### 场景 5:Stop HTTP 通知**预置:**
- 本地起 echo server:`python3 -m http.server 9999 --bind 127.0.0.1` 或 nc -l
```yaml
hooks:
  - name: notify-stop
    event: Stop
    action:
      type: http
      url: "http://127.0.0.1:9999/done"
      method: POST
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 简单回答一个问题后停止
- [ ] echo server 收到一次 POST,body 含 `"event":"Stop"`

### 场景 6:only_once + PreUserMessage**预置:**
```yaml
hooks:
  - name: first-turn
    event: PreUserMessage
    only_once: true
    action:
      type: shell
      command: "echo first-turn-fired >&2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮发任意消息,stderr 出现 `first-turn-fired`
- [ ] 第二轮发消息,stderr 没有再次出现
- [ ] 执行 `/clear` 进新会话,再发消息,stderr 重新出现 `first-turn-fired`

### 场景 7:错误配置不阻断启动**预置:** hooks.yaml 含一条非法 hook:
```yaml
hooks:
  - name: bad-async
    event: PreToolUse
    async: true
    action:
      type: shell
      command: "echo x"
  - name: good-hook
    event: SessionStart
    action:
      type: shell
      command: "echo ok"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] gcode 启动期 stderr 打印 `hook "bad-async": async not allowed for blocking events, skipped`
- [ ] gcode 仍然成功进入 idle 状态
- [ ] `/hooks` 命令仅列出 good-hook、未列 bad-async

### 场景 8:/hooks 命令**预置:** 一份包含 3 条合法 hook 的 hooks.yaml(任意 event 组合)

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入 `/hooks` 回车
- [ ] 输出按 event 分组,每条一行 `  <name>  <event>  <action.type>  [flags]`
- [ ] 末尾显示 `Loaded from: .../hooks.yaml`

### 场景 9:端到端组合(AC17)**预置:** hooks.yaml 包含场景 1、2、3、4 全部 hook

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 首轮:SessionStart 注入 zh-CN(场景 2),Agent 准备就绪
- [ ] 输入"帮我创建 hello.go,然后 gofmt 一下"
- [ ] LLM 调 write_file 创建文件 → 被场景 1 的 hook 拦截 →LLM 重试(可能换 edit_file)或换 bash 调 gofmt
- [ ] 整个过程不卡顿、无 panic
- [ ] /hooks 命令仍可工作显示 4 条 hook
````

### Python

````markdown
# Hook 生命周期挂钩系统 Spec## 背景把可复用 SOP 搬出源码做成 Skill 包之后,GCode 在"用户怎么扩展行为"这条路径上还差最后一环:**在 Agent 生命周期的固定时刻自动跑一段用户配置的动作**。当前的扩展点都是显式触发——Skill 要 `/<name>` 唤起、Slash 命令要用户手敲。如果想做这种"触发条件明确、动作固定"的重复事,只能每次手动来:

- 写完文件想立刻 `ruff format`,得手动跑或写监听脚本
- 想阻止 Agent 跑 `rm -rf` 之类的命令,权限规则要逐个加 deny
- 想在每轮用户提交前提醒 Agent "记得用 zh-CN",没现成机制
- 想在 Agent 长跑结束后给自己发个 IM 通知,要自己起进程

ch08 的权限引擎覆盖了"该不该允许工具调用",但**只在工具调用前判定一次、动作仅 Allow/Deny/Ask**,做不了命令格式化、上下文注入、外部通知这些副作用。Hook 系统补的是这条缝:在 Agent 生命周期的 11 个固定时刻挂自动化动作,把"触发条件明确、动作固定"的重复工作从人工变成机器。

设计上沿用 ch08 已有的权限匹配器做条件表达式底层——但需先把单一通配匹配扩展成"精确/反向/正则/glob"四种,让 Hook 条件、未来的权限规则共用同一套匹配语义。

## 目标- **G1**:把 Agent 生命周期上的 11 个固定时刻抽象成事件总线,事件 emit 时同步驱动 Hook 引擎;现有内部事件(工具 Start/End、Compact、Approval)继续走 asyncio 事件流,不受影响
- **G2**:用户用 YAML 文件声明式配置 Hook 规则,启动期一次性加载并校验,**配置错误立即报到 stderr 并跳过出错规则,不阻断进程**
- **G3**:每条 Hook 是"事件 + 条件 + 动作"三要素,条件可省略表示无条件触发
- **G4**:把 ch08 权限规则的匹配语法从单一通配扩展成"精确 exact / 反向 not / 正则 regex / glob"四种;Hook 条件表达式与扩展后的权限规则共用同一套匹配器
- **G5**:条件表达式支持嵌套字段访问,多条件用 `all_of` / `any_of` 二选一组合,**不允许嵌套混用**
- **G6**:在 PreToolUse 时刻,Hook 的 shell 动作通过 `exit code 2` 表达拦截、stderr 作为拒绝原因——被拒原因当 tool_result 回灌让模型调整;在 UserPromptSubmit 时刻同理拦截用户提交、原因回显到对话
- **G7**:四种动作类型——执行 shell 命令、注入提示词、发 HTTP 请求、启动子 Agent(**子 Agent 本期占位不实现,等后续章节对接**)
- **G8**:三种执行控制——only_once(同一会话内只跑一次)、async(异步后台执行不阻塞主流程)、timeout(命令最大执行时长);**拦截类事件(PreToolUse / UserPromptSubmit)不允许 async,加载期校验出错**
- **G9**:Hook 自身失败(命令非零退出、HTTP 超时、HTTP 解析错等)**只记日志、不中断 Agent 主流程**——除非该 hook 是同步拦截类且通过约定方式表达拦截信号

## 功能需求### 权限匹配语法扩展(前置基础)- **F1**:把权限规则 Pattern 形态从单一字符串扩展成结构化匹配类型 `{type, value}`,type 取 `exact`、`not`、`regex`、`glob` 之一;缺省类型沿用现有 glob 语义,保证向后兼容
- **F2**:规则 YAML 串语法升级——除 `Bash(rm *)` 这种"工具(简洁串)"写法保留代表 glob 类型外,新增显式类型前缀:
  - `Bash(=value)` 精确(整串相等)
  - `Bash(!inner)` 反向(对 inner 取反,inner 自身仍按规则解析,支持 `!=value`、`!~regex`、`!glob`)
  - `Bash(~regex)` 正则
  - `Bash(value)` 不带前缀沿用 glob 语义
- **F3**:精确匹配做整串相等比较;glob 沿用现有 `fnmatch` / `Path.match` 实现;正则在加载期 `re.compile` 并缓存,编译失败按 F4 处理;反向是"任意其它类型的取反包装",支持嵌套(如 `Bash(!=value)`)
- **F4**:扩展后权限引擎的 Allow/Deny 判定语义不变,但规则解析失败原本静默跳过,现在改为"stderr 打印失败规则与原因、其余规则正常加载"
- **F5**:现有 ch08 的所有权限测试、既有的 `.gcode/permissions.yaml` 用户配置(仅写 `Bash(git *)` 这种)必须继续工作,不破坏向后兼容

### Hook 配置文件- **F6**:YAML 配置文件位置按以下顺序扫描,找到就加载、找不到就跳过:
  - 项目级:`<projectRoot>/.gcode/hooks.yaml`
  - 用户级:`~/.gcode/hooks.yaml`
- **F7**:两层规则**叠加合并**——所有规则共同参与事件分派;不存在"覆盖同名"概念,hook 的 name 仅用于日志和 only_once 跟踪;两层中出现同名 hook 时,加载期 stderr 提示冲突并跳过后到者
- **F8**:YAML 顶层结构:`hooks:` 数组,每条 hook 为对象,字段如下:
  - `name`(必填):字符串,用于日志、only_once 跟踪、冲突检测
  - `event`(必填):事件名,11 选 1(见 F9)
  - `if`(可选):条件表达式对象,省略表示无条件
  - `action`(必填):动作对象,含 `type` 与各类型独有字段
  - `only_once`(可选 bool,默认 False):会话内只跑一次
  - `async`(可选 bool,默认 False):是否后台异步执行
  - `timeout`(可选时长字符串如 `30s`,默认 30s):命令 / HTTP 最大执行时长

### 生命周期事件- **F9**:11 个事件名及触发时机:
  - **SessionStart**:gcode 启动初次进入会话或 `/clear` 新建会话后、env context 装配完毕、首条 user 消息进入对话历史**之前**
  - **SessionEnd**:进程关闭前、`/clear` 关闭旧会话前、`/resume` 切换离开旧会话前
  - **SessionResume**:`/resume` 选中历史会话、恢复完成、首条 user 消息进入**之前**
  - **UserPromptSubmit**:TUI 提交一条非 Slash 命令的 user 消息、写入对话历史**之前**——可拦截
  - **Stop**:Agent.run 自然停止后、`Done: true` 事件 emit 之前;取消、出错路径不触发
  - **PreUserMessage**:每轮 `stream_once` 调 `provider.stream` 之前;payload 含当前 conversation 末尾的 user 消息
  - **PreToolUse**:`execute_batched` 对每条 tool call 准备执行**之前**、权限引擎 `check` 之**前**——可拦截
  - **PostToolUse**:单条 tool call 拿到 result 之后、emit PhaseEnd 之前;权限被 Deny 的也触发,payload.is_error=True
  - **PreCompact**:`compact.manage_context` 调用之前(自动/紧急/手动三路径合并)
  - **PostCompact**:`compact.manage_context` 返回后
  - **Notification**:权限 Ask 弹出审批时、Stream 返回 Err 时
- **F10**:每个事件对应一份固定的 payload schema,作为 Hook 条件表达式与动作输入的数据源
  ```
  # 通用字段(每个事件都有)
  event: <事件名>
  session_id: <当前会话 ID>
  cwd: <项目工作目录>
  mode: <permission.Mode 名,default / plan>

  # 事件特化字段
  PreToolUse / PostToolUse:
    tool_name: <内部工具名,如 read_file>
    tool_input: <工具参数 dict>
    tool_result: <仅 PostToolUse,工具结果摘要文本>
    is_error: <仅 PostToolUse,bool>
  UserPromptSubmit / PreUserMessage:
    prompt: <用户输入文本>
  Notification:
    kind: approval | stream_error
    detail: <approval 含工具名;stream_error 含错误摘要>
  PreCompact / PostCompact:
    trigger: auto | emergency | manual
    before_tokens: <int,仅 PostCompact>
    after_tokens: <int,仅 PostCompact>
  SessionStart / SessionEnd / SessionResume:
    (仅通用字段)
  Stop:
    iter: <本轮 run 走完的迭代数>
  ```

### 条件表达式- **F11**:条件表达式 `if:` 是一个对象,顶层只能出现 `all_of` 或 `any_of` 中**一个**——两个同时出现按加载错误处理;缺省 `if:` 视为无条件触发
- **F12**:`all_of` / `any_of` 的值是一个原子条件数组,每个原子条件包含 `field` 与 `match` 两个字段
  ```yaml
  if:
    all_of:
      - field: tool_name
        match: { type: exact, value: write_file }
      - field: tool_input.path
        match: { type: glob, value: "**/*.py" }
  ```
- **F13**:`field` 取 payload 中的字段路径,用 `.` 分隔嵌套(如 `tool_input.command`、`tool_input.path`);路径不存在按空字符串处理,不报错
- **F14**:`match` 取四种类型之一——
  - `{type: exact, value: "..."}`
  - `{type: glob, value: "..."}`
  - `{type: regex, value: "..."}`
  - `{type: not, inner: {type: ..., value/inner: ...}}`

  正则编译失败、`not` 缺少 `inner`、`inner` 自身非法均视为加载错误,跳过该 hook
- **F15**:条件求值在事件 emit 时实时进行,匹配器实例在加载期一次构造、运行期复用

### 动作类型- **F16**:`action.type` 取 `shell` / `prompt` / `http` / `subagent` 之一,各自的字段:

#### shell 动作- **F17**:`shell` 动作字段:`command`(字符串,由 `sh -c` 解释执行,使用 `asyncio.create_subprocess_shell` 启动);执行时把事件 payload 序列化成单行 JSON 通过 stdin 传给命令——脚本侧可用 `jq` 取字段
- **F18**:`timeout` 默认 30 秒,超时按命令失败处理(记日志);async 时由后台 asyncio task 异步执行,超时同样按失败处理
- **F19**:拦截事件(PreToolUse / UserPromptSubmit)下的 shell 同步执行:
  - `returncode == 2` 视为拦截命中,`stderr or stdout` 合并去尾换行后作为拒绝原因
  - `returncode == 0` 视为放行
  - 其它非零 returncode 视为 hook 失败但**不拦截**(记日志、Agent 继续)

#### prompt 动作- **F20**:`prompt` 动作字段:`text`(字符串);执行时把 `text` 加入"下一次 LLM 请求的 reminder 区"队列——所有 hook 注入的 prompt 按 hook 在 yaml 中的声明顺序拼接,置于现有 plan reminder 之后
- **F21**:reminder 队列仅本轮有效,下一轮重新装配;不入持久对话历史、不影响压缩
- **F22**:prompt 动作永不表达拦截——即使位于拦截类事件,动作执行后视为放行,仅做副作用注入

#### http 动作- **F23**:`http` 动作字段:`url`(必填)、`method`(默认 POST)、`headers`(可选键值对)、`body`(可选字符串模板,支持 `{field}` Python `str.format_map` 取 payload 字段);缺省 `body` 时把事件 payload 序列化成 JSON 作为请求体
- **F24**:`timeout` 同 F18 默认 30 秒;async 时由后台 asyncio task 异步执行
- **F25**:拦截事件下的 http 同步执行:
  - 响应 status 2xx 且 body 解析成 `{"decision":"block","reason":"..."}` 时视为拦截命中,reason 作为拒绝原因
  - 其它情况(非 2xx、body 缺 `decision` 字段、`decision` 非 `block`)视为放行
  - 网络错误、超时、JSON 解析失败按 hook 失败但**不拦截**#### subagent 动作- **F26**:`subagent` 动作字段:`agent_name`(必填)、`prompt`(必填字符串模板);**本期占位实现**——加载时校验字段完整、执行时仅记一行 stderr 日志 `[hook subagent] not yet implemented, skipped: <name>`、不报错也不拦截;后续章节对接子 Agent 后再补完整逻辑

### 执行控制- **F27**:`only_once: true` 标记的 hook 在同一会话内首次匹配成功并执行后被记录到 `SessionRuntime` 的内存集合(key = hook.name),后续相同事件再次匹配时直接跳过;`/clear`、`/resume` 进新会话时集合清空;**进程退出不写盘**——本期不做跨进程持久化
- **F28**:`async: true` 标记的 hook 在新 asyncio task 中执行;加载期校验:若 hook.event ∈ {PreToolUse, UserPromptSubmit} 且 async=True,加载层报错并跳过该 hook(拦截类不允许异步——异步无法表达拦截信号)
- **F29**:所有 hook 失败(命令非 0 returncode 但非拦截信号、HTTP 错误、超时等)写一行 stderr `[hook <name>] <event> failed: <reason>`;不写日志文件、不弹 UI 通知;async 失败同上、不重试

### 集成点- **F30**:Hook 系统由独立模块承载,内部至少包含规则加载器、引擎(事件分派 + 集合状态)、四类动作执行器、匹配器;Agent 在构造期通过参数注入 Hook 引擎
- **F31**:`Agent.run` 等关键路径在 11 个事件时刻调用引擎的事件分派接口,接口返回拦截判定与待注入 prompt 集合
- **F32**:拦截结果整合:
  - **PreToolUse 拦截**:把 reason 拼成 `[hook <name>] <reason>` 形式当 tool_result 回灌,跳过权限引擎与真实工具执行;PhaseStart/PhaseEnd 事件按当前实现继续 emit,PhaseEnd 的 is_error=True
  - **UserPromptSubmit 拦截**:阻止该 user 消息写入对话历史,TUI 在输入框下方显示 `[hook <name>] <reason>`,焦点返回输入框等用户重新编辑
- **F33**:`injected_prompts` 集合在下一次 `stream_once` 时拼到 reminder 串末尾,置于现有 plan reminder 之后;本轮无可拦截语义的事件(SessionStart 等)触发的 prompt 注入也走 reminder 队列

### Slash 命令- **F34**:新增内置 Slash 命令 `/hooks`,KindLocal,零参数:输出当前已加载的所有 hook 的精简列表,按 `event` 分组、每条一行 `  <name>  <event>  <action.type>  <flags>`,flags 含 `[once]` / `[async]` 标志;末尾追加 `Loaded from: <加载来源文件列表>`
- **F35**:无任何 hook 时输出 `No hooks loaded.`

## 非功能需求- **N1**:Hook 加载在进程启动期一次性完成;YAML 解析错误、字段缺失、event 未知、name 冲突、async + 拦截事件冲突、regex 编译失败等所有加载错误**一律 stderr 输出后继续启动**,不阻断 gcode 进程
- **N2**:事件分派接口必须支持 `asyncio.CancelledError` 传播——拦截事件下同步等待、async 后台执行中被取消都应及时退出,避免卡死 `Agent.run`
- **N3**:拦截事件下的同步 hook 串行执行,以单条 hook 的 timeout 累加;命令自身超时按 F18 处理,不再设全局上限
- **N4**:注入的 reminder 文本不入序列化对话历史、不参与 token 估算的"历史增长部分"(与 plan reminder 同语义)
- **N5**:only_once 内存集合放在 `SessionRuntime` 上,与 `ActiveSkills` 同生命周期;`/clear` 与 `/resume` 切换时清空
- **N6**:Hook payload JSON 序列化必须稳定字段顺序——`json.dumps(payload, sort_keys=True)`,方便用户脚本对 JSON 直接 `grep`
- **N7**:扩展后的匹配器对权限规则与 Hook 条件共用同一实现,单元测试覆盖四种 type × 边界条件(空串、转义、嵌套 not、空 path)
- **N8**:subagent 占位日志输出固定格式 `[hook subagent] not yet implemented, skipped: <name>`,方便后续章节对接时文本搜索替换
- **N9**:`hooks.yaml` 文件不存在不报错;文件存在但整体 YAML 解析失败、顶层结构非法时打 stderr 但保持 gcode 启动
- **N10**:HTTP 动作的请求体模板渲染失败按 hook 失败处理;模板默认只支持 `str.format_map` 最基本字段插值,不开放函数调用

## 不做的事

- 不实现 subagent 动作的真实执行(仅占位日志),等后续章节对接 SubAgent 系统
- 不做 only_once 标记的跨进程持久化(重启进程后集合清空,hook 会重新触发一次)
- 不引入 hook 执行的显式优先级 / order 字段——加载层按 yaml 声明顺序自然有序
- 不做 hook 文件的热更新——加载在启动期一次完成,编辑文件后需重启 gcode 才生效
- 不在 TUI 渲染 hook 触发的可视化轨迹(仅 stderr 日志)
- 不实现 hook 之间的依赖 / 互斥关系
- 不为 hook 提供独立日志文件、专属环境变量配置入口
- 不做 hook 失败的重试机制
- 不支持 hook 配置文件的 @include 或继承

## 验收标准- **AC1**:写一份只含 `Bash(=git status)` 的精确规则到 `.gcode/permissions.yaml`,启动后调用 `git status` 被该规则命中、调用 `git status -s` 不命中
- **AC2**:写一份 `Bash(~^npm (install|test)$)` 的正则规则,启动后调用 `npm install` 命中、`npm run dev` 不命中;写法非法(如未闭合括号、正则编译失败)启动期 stderr 打印 `rule "Bash(~..." parse failed: ...` 并跳过该条规则
- **AC3**:写一份 `Bash(!~^rm)` 的反向正则规则,调用 `rm -rf .` 不命中(以 rm 起头)、调用 `ls -lh` 命中(不以 rm 起头)
- **AC4**:在 `<projectRoot>/.gcode/hooks.yaml` 写一条 PreToolUse hook——条件 `tool_name = write_file`,动作 `shell: "echo blocked >&2; exit 2"`;启动后 LLM 调用 write_file 工具时被拦截,tool_result 显示 `[hook <name>] blocked`,文件未被写入
- **AC5**:上面 AC4 的 hook 把动作命令改成 `exit 0`,再调用 write_file,hook 触发但放行,文件成功写入
- **AC6**:写一条 SessionStart hook——动作 `prompt: "用 zh-CN 回复"`;重启 gcode 后首轮对话中 LLM reminder 区能看到该文本(通过调试通道观察),后续轮不再注入
- **AC7**:写一条 PostToolUse hook——条件工具名为 write_file 且 `is_error=False`,动作 `shell: "ruff format \"$(jq -r .tool_input.path)\""`、async=True、timeout=5s;LLM 写一个 Python 文件后 ruff 异步在后台执行,主对话流不暂停;命令失败时 stderr 打印失败日志、Agent 不中断
- **AC8**:写一条 async + PreToolUse 的 hook,启动 gcode 时 stderr 打印 `hook "<name>": async not allowed for blocking events, skipped` 并跳过该条
- **AC9**:写一条 only_once + PreUserMessage 的 hook,动作 `shell: "echo first-turn >&2"`;第一轮 PreUserMessage 时 stderr 出现 `first-turn`,后续轮不再出现;执行 `/clear` 进入新会话后下一轮再次出现 `first-turn`
- **AC10**:写一条 UserPromptSubmit hook——条件 prompt 正则匹配 `(?i)delete`,动作 `shell: "echo \"prompt contains delete keyword\" >&2; exit 2"`;用户在 TUI 输入"请帮我 delete 那个文件"时被拦截,输入框下方提示 `[hook <name>] prompt contains delete keyword`,消息未进入对话历史
- **AC11**:在 hooks.yaml 中写 `event: UnknownEvent`,启动后 stderr 打印 `hook "<name>": unknown event "UnknownEvent", skipped`,其余 hook 正常加载
- **AC12**:同时在用户级与项目级 hooks.yaml 各写一条 hook,启动后 `/hooks` 命令输出两条合并列表,末尾显示两个加载来源文件路径
- **AC13**:写一条 Stop hook——动作 `http: POST http://localhost:9999/done`;本地起一个 echo server,Agent.run 自然停止后该 server 收到一次 POST 请求且 body 含 `"event":"Stop"`
- **AC14**:写一条 PreToolUse hook——动作 `http: POST http://localhost:9999/check`;本地 server 对 Bash 工具返回 `{"decision":"block","reason":"network policy"}`,Bash 调用被拦截、其它工具不受影响
- **AC15**:写一条 SessionStart hook——动作 `subagent: agent_name=foo, prompt=test`;启动后 stderr 出现 `[hook subagent] not yet implemented, skipped: <name>`,Agent 主流程不受影响
- **AC16**:在 hook 的 `if` 中同时写 `all_of` 与 `any_of` 两个键,启动 stderr 报错跳过该条,其余 hook 加载正常
- **AC17**:tmux 内启动 gcode,按 AC4 → AC6 → AC7 → AC10 顺序触发,整个过程不卡顿、无异常栈(端到端见 checklist)
````

````markdown
# Hook 生命周期挂钩系统 Plan## 技术栈

- 语言:Python 3.12+
- TUI:Textual(async-first)+ Rich
- 配置:YAML 解析(`pyyaml`,import 名 `yaml`,用 `yaml.safe_load`)
- HTTP 客户端:`httpx`(原生支持 async,与 Textual 事件循环天然融合)
- 异步进程:`asyncio.create_subprocess_shell` + `asyncio.wait_for` 超时
- 模板:Python 标准库 `str.format_map`(不开放函数调用)
- 测试:`pytest` + `pytest-asyncio`(async 测试)、临时目录用 `tmp_path`、HTTP 桩用 `pytest-httpserver` 或自起 `aiohttp` 桩

## 架构概览

本章拆为两个层次实现:

1. **权限匹配器升级层(`gcode.permission` 包内改造)**——把 Pattern 形态从字符串升级到结构化 `Matcher` Protocol;新增 exact/regex/not 三种实现,glob 保留作为缺省类型。改造对外仅暴露语法升级和 stderr 错误回退,运行时 Allow/Deny 语义不变。

2. **Hook 主体层(新建 `gcode.hook` 包)**——加载 YAML 规则、提供事件分派引擎、四类动作执行器;通过 11 个事件 emit 点接入 agent / tui。

模块构成:

- `permission.Matcher`(新):匹配 Protocol + 四种实现的工厂
- `hook.Loader`(新):YAML 解析 / 字段校验 / matcher 编译 / 双层文件合并
- `hook.Engine`(新):事件分派、only_once 集合、动作执行器协调
- `hook.Executor`(新):四类动作的执行入口(shell / prompt / http / subagent stub)
- `hook.matcher`(薄包装):复用 `permission.Matcher`,做字段路径取值与匹配组合
- `agent`/`tui` 改动:在生命周期 11 个时刻调 `Engine.dispatch`
- `command`:新增 `/hooks` 内置命令

## 数据流**启动期:**

```
cli.main
  ├─ permission.new_engine(root)         # 用升级后的 parse_rule(stderr 报错)
  ├─ hook.load(root)                     # 扫描两层 YAML、构造 Engine
  └─ tui.create_app(..., hook_engine=engine)
        ├─ agent.create(..., hook_engine=engine)
        └─ app.hook_engine = engine
```

**SessionStart emit 时机:**

```
cli.main 完成 wiring → tui.create_app 返回 GCodeApp → app.run_async()
                                                         │
                                                         └─ Textual on_mount() 末尾
                                                            首条 user 输入到达前
                                                            派发 SessionStart 事件
```

实际接入:`GCodeApp.on_mount()` 末尾 `await self._dispatch_session_start()`,该协程同步调 `Engine.dispatch`、收集 `injected_prompts` 注入到 `runtime.pending_reminders`、然后返回。

**UserPromptSubmit 路径:**

```python
async def _submit(self, text: str) -> None:
    text = text.strip()
    if text.startswith("/"):
        await self._dispatch_slash(text)
        return
    result = await self.hook_engine.dispatch(
        Event.USER_PROMPT_SUBMIT,
        self._base_payload() | {"prompt": text},
    )
    if result.blocked:
        # 输入框下方显示 [hook <name>] reason,不消费输入
        self._show_error_block(f"[hook {result.blocking_hook_name}] {result.reason}")
        return
    self.runtime.append_reminders(result.injected_prompts)
    self.conv.add_user(text)
    await self._begin_turn()
```

**PreToolUse 拦截路径:**

```python
async def execute_batched(calls, mode, queue):
    for call in calls:
        result = await self.hook_engine.dispatch(
            Event.PRE_TOOL_USE,
            {"tool_name": call.name, "tool_input": call.input, ...},
        )
        if result.blocked:
            await queue.put(PhaseStart(call_id=call.id))   # 用户仍能看到工具被尝试
            results[call.id] = hook_blocked_result(call.id, result.blocking_hook_name, result.reason)
            await queue.put(PhaseEnd(call_id=call.id, is_error=True))
            continue
        self.runtime.append_reminders(result.injected_prompts)
        # ... 原有的权限 check + 执行流程
        # PostToolUse dispatch 后再 append 一次 reminder
```

**Reminder 注入路径:**

```python
# Agent.run() 第 iter 轮 stream_once 之前:
reminder = plan_reminder
reminder += join_pending_reminders(self.runtime)  # 取出并清空 runtime.pending_reminders
await self._stream_once(..., reminder=reminder, ...)
```

## 核心数据结构与接口### `permission.Matcher`

```python
# gcode/permission/matcher.py
from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol

class Matcher(Protocol):
    """规则匹配的统一接口;四种实现:ExactMatcher / GlobMatcher / RegexMatcher / NotMatcher。"""

    def match(self, s: str) -> bool: ...
    def __str__(self) -> str: ...   # 调试 / /hooks 输出用

@dataclass(frozen=True)
class ExactMatcher:
    value: str

    def match(self, s: str) -> bool:
        return s == self.value

    def __str__(self) -> str:
        return f"={self.value}"

@dataclass(frozen=True)
class GlobMatcher:
    pattern: str
    is_command: bool          # True 走 match_command(整串通配),False 走 match_path

    def match(self, s: str) -> bool:
        if self.is_command:
            return match_command(self.pattern, s)
        return match_path(self.pattern, s)

    def __str__(self) -> str:
        return self.pattern

@dataclass(frozen=True)
class RegexMatcher:
    src: str
    compiled: re.Pattern[str]

    def match(self, s: str) -> bool:
        return self.compiled.search(s) is not None

    def __str__(self) -> str:
        return f"~{self.src}"

@dataclass(frozen=True)
class NotMatcher:
    inner: Matcher

    def match(self, s: str) -> bool:
        return not self.inner.match(s)

    def __str__(self) -> str:
        return f"!{self.inner}"

def compile_matcher(pattern: str, *, is_command: bool) -> Matcher:
    """
    解析单条匹配描述串,返回 Matcher。失败抛 ValueError。
    描述串规则:
      "=value"  -> ExactMatcher
      "~regex"  -> RegexMatcher
      "!inner"  -> NotMatcher(compile_matcher(inner))
      "value"   -> GlobMatcher(沿用现有 wildcard / match_path 语义)
    Bash 工具沿用整串通配(is_command=True),其它沿用 match_path。
    """
    if not pattern:
        raise ValueError("empty matcher pattern")
    head, rest = pattern[0], pattern[1:]
    if head == "=":
        return ExactMatcher(rest)
    if head == "~":
        try:
            return RegexMatcher(rest, re.compile(rest))
        except re.error as e:
            raise ValueError(f"invalid regex: {e}") from e
    if head == "!":
        return NotMatcher(compile_matcher(rest, is_command=is_command))
    return GlobMatcher(pattern, is_command)
```

### `permission.Rule`(改造)

```python
@dataclass
class Rule:
    tool: str                    # 不变
    matcher: Matcher | None      # 替换原 pattern 字符串;None 表示"该工具全匹配"
    allow: bool
    raw: str                     # 原始模式串,仅供错误日志与调试
```

`parse_rule` 升级:识别前缀,调用 `compile_matcher` 构造 matcher。失败时返回 `(None, error_str)`;调用方 `to_rule_set` 把错误打到 stderr 后跳过。

### `hook.Rule`

```python
# gcode/hook/rule.py
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

class Event(str, enum.Enum):
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    SESSION_RESUME = "SessionResume"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    PRE_USER_MESSAGE = "PreUserMessage"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    NOTIFICATION = "Notification"

BLOCKING_EVENTS: frozenset[Event] = frozenset({Event.PRE_TOOL_USE, Event.USER_PROMPT_SUBMIT})

def is_blocking(e: Event) -> bool:
    return e in BLOCKING_EVENTS

class CombineMode(str, enum.Enum):
    ALL_OF = "all_of"
    ANY_OF = "any_of"

class ActionType(str, enum.Enum):
    SHELL = "shell"
    PROMPT = "prompt"
    HTTP = "http"
    SUBAGENT = "subagent"

@dataclass
class AtomCondition:
    field: str                   # 形如 "tool_input.path"
    matcher: "Matcher"           # 复用 permission.Matcher

@dataclass
class Condition:
    mode: CombineMode            # CombineMode.ALL_OF 或 ANY_OF;二选一不混用
    atoms: list[AtomCondition]

@dataclass
class ShellAction:
    command: str

@dataclass
class PromptAction:
    text: str

@dataclass
class HttpAction:
    url: str
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None      # 模板字符串,None 表示用 payload JSON

@dataclass
class SubagentAction:
    agent_name: str
    prompt: str

@dataclass
class Action:
    type: ActionType
    shell: ShellAction | None = None
    prompt: PromptAction | None = None
    http: HttpAction | None = None
    subagent: SubagentAction | None = None

@dataclass
class Rule:
    name: str
    event: Event
    action: Action
    condition: Condition | None = None      # None 表示无条件
    only_once: bool = False
    asyncio_mode: bool = False               # 对应 YAML 的 `async`(避免与关键字冲突)
    timeout_s: float = 30.0
    source: str = ""                         # 来源文件路径,供 /hooks 显示

# Payload 是事件分派时携带的上下文数据;条件求值与动作输入都用它。
# 序列化为 JSON 时保证 key 字典序(N6)用 json.dumps(payload, sort_keys=True)。
Payload = dict[str, Any]
```

### `hook.Engine`

```python
# gcode/hook/engine.py
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

@dataclass
class DispatchResult:
    blocked: bool = False
    reason: str = ""
    blocking_hook_name: str = ""
    injected_prompts: list[str] = field(default_factory=list)

class Engine:
    def __init__(self, rules: list[Rule], sources: list[str]) -> None:
        self._rules = rules                       # 按加载顺序
        self._sources = sources                   # 加载来源文件列表,供 /hooks 显示
        self._once_fired: set[str] = set()        # only_once 已触发的 hook name
        self._lock = asyncio.Lock()
        self._executor = Executor()

    async def dispatch(self, event: Event, payload: Payload) -> DispatchResult:
        result = DispatchResult()
        for rule in self._rules:
            if rule.event is not event:
                continue
            async with self._lock:
                if rule.only_once and rule.name in self._once_fired:
                    continue
            if not eval_condition(rule.condition, payload):
                continue

            if rule.asyncio_mode:
                # async hook:起 task 后立即继续,不参与 Blocked / InjectedPrompts
                asyncio.create_task(self._executor.run(rule, payload, blocking=False))
                if rule.only_once:
                    async with self._lock:
                        self._once_fired.add(rule.name)
                continue

            outcome = await self._executor.run(rule, payload, blocking=is_blocking(event))
            if outcome.err is not None:
                print(
                    f"[hook {rule.name}] {event.value} failed: {outcome.err}",
                    file=sys.stderr,
                )
                continue
            if outcome.prompt:
                result.injected_prompts.append(outcome.prompt)
            if rule.only_once:
                async with self._lock:
                    self._once_fired.add(rule.name)
            if outcome.blocked and is_blocking(event):
                result.blocked = True
                result.reason = outcome.reason
                result.blocking_hook_name = rule.name
                break
        return result

    async def reset_for_new_session(self) -> None:
        async with self._lock:
            self._once_fired.clear()

    @property
    def sources(self) -> list[str]:
        return list(self._sources)

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)
```

Dispatch 内部流程:
1. 过滤匹配 event 的 rule
2. 跳过 `_once_fired` 中已触发的 only_once rule
3. 串行求值 if 条件
4. 命中条件后按 action.type 分发到 Executor
5. async rule 起 asyncio task、立即往下走
6. 同步 rule 等结果,拦截类事件下若 outcome 表达 block,累加到 DispatchResult,跳过后续同事件 rule
7. prompt 类 rule 把 text 累加到 `injected_prompts`

### `hook.Executor`

```python
# gcode/hook/executor.py
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

import httpx

@dataclass
class ExecutionResult:
    blocked: bool = False
    reason: str = ""
    prompt: str = ""              # 仅 prompt 动作非空
    err: Exception | None = None  # hook 自身失败(不拦截)

class Executor:
    def __init__(self) -> None:
        # 默认 timeout=30s,可被 rule.timeout_s 覆盖
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def run(self, rule: Rule, payload: Payload, *, blocking: bool) -> ExecutionResult:
        action = rule.action
        if action.type is ActionType.SHELL:
            return await self._run_shell(action.shell, payload, blocking, rule.timeout_s)
        if action.type is ActionType.PROMPT:
            return ExecutionResult(prompt=action.prompt.text)
        if action.type is ActionType.HTTP:
            return await self._run_http(action.http, payload, blocking, rule.timeout_s)
        if action.type is ActionType.SUBAGENT:
            print(
                f"[hook subagent] not yet implemented, skipped: {action.subagent.agent_name}",
                file=sys.stderr,
            )
            return ExecutionResult()
        return ExecutionResult(err=RuntimeError(f"unknown action type: {action.type}"))
```

`_run_shell` 关键点:
- 调 `asyncio.create_subprocess_shell(sa.command, stdin=PIPE, stdout=PIPE, stderr=PIPE)`
- `payload_json = json.dumps(payload, sort_keys=True).encode()` 写到 stdin
- `await asyncio.wait_for(proc.communicate(input=...), timeout=timeout_s)`,超时 → 杀子进程并按失败处理
- `blocking and proc.returncode == 2` → `blocked=True`、`reason=(stderr or stdout).decode().rstrip("\n")`
- `proc.returncode == 0` → 不拦截不报错
- 其它非 0 returncode → `err=RuntimeError(f"exit {code}: {stderr.decode()}")`

`_run_http` 关键点:
- 默认 method=POST
- body:缺省时 `json.dumps(payload, sort_keys=True)`;否则 `ha.body.format_map(payload)`
- 用 `httpx.AsyncClient.request(method, url, content=body, headers=headers, timeout=timeout_s)`
- status 2xx 且 body 含 `{"decision":"block","reason":"..."}` → `blocked=True`
- 网络错/超时/JSON 解析失败 → `err`

## 模块设计### 模块 A:`permission.Matcher`**职责:** 提供四种匹配类型的统一接口;`compile_matcher` 解析前缀。
**对外接口:** `Matcher` Protocol、`compile_matcher(pattern: str, *, is_command: bool) -> Matcher`。
**依赖:** Python 标准库 `re`、`fnmatch`。
**改动文件:** `src/gcode/permission/rule.py`(扩展 `parse_rule` / `match_rule`)、新增 `src/gcode/permission/matcher.py`。

### 模块 B:permission 错误日志**职责:** `parse_rule` 失败时 stderr 打印失败规则与原因,原本静默跳过改为有声跳过。
**对外接口:** `to_rule_set` 内部行为变化,外部 API 不变。
**依赖:** 模块 A。

### 模块 C:`hook.Loader`**职责:** 扫描两层 YAML 文件、解析顶层 `hooks:` 数组、字段校验、Matcher 编译、合并去重。
**对外接口:** `load(project_root: str | Path) -> Engine`——返回引擎(内部已含来源文件列表);所有错误走 stderr 不抛异常。
**依赖:** 模块 A、`pyyaml`、`hook.Engine`。
**校验项:** name 必填 + 跨文件冲突、event 枚举、if 顶层 all_of/any_of 互斥、action.type 枚举与子字段、async + 拦截事件冲突、Matcher 编译失败、timeout 字符串格式合法。

### 模块 D:`hook.Engine`**职责:** Dispatch 流程编排、only_once 集合管理、`reset_for_new_session`。
**对外接口:** 见上一节 Engine 类。
**依赖:** 模块 E。

### 模块 E:`hook.Executor`**职责:** 四类动作的执行——shell(`asyncio.create_subprocess_shell` + stdin JSON + returncode 2 拦截)、prompt(直接返回 `injected_prompt`)、http(POST JSON + decision=block 解析)、subagent(stub 占位日志)。
**对外接口:** `run(rule, payload, *, blocking) -> ExecutionResult`。
**依赖:** `asyncio`、`httpx`、`json`、`str.format_map`。

### 模块 F:`hook.matcher` 包装**职责:** 把 `permission.Matcher` 应用到 payload 的字段路径上。
**对外接口:** `eval_condition(cond: Condition | None, payload: Payload) -> bool`、`get_by_path(payload: Payload, path: str) -> str`。
**依赖:** 模块 A。

### 模块 G:agent 接入**职责:** 在 `Agent.run` 等关键路径调 `Engine.dispatch`;处理 PreToolUse 拦截、注入 reminder。
**对外接口:** `Agent.__init__(..., hook_engine: Engine | None = None)`;`Agent._dispatch_hook(event, payload) -> DispatchResult` 私有方法。
**依赖:** 模块 D。
**改动文件:** `src/gcode/agent/agent.py`、`src/gcode/agent/runtime.py`(`SessionRuntime` 加 `pending_reminders: list[str]`、`reset_for_new_session` 清空)。

### 模块 H:tui 接入**职责:** SessionStart / SessionEnd / SessionResume / UserPromptSubmit / Notification 五个事件在 TUI 侧 emit;UserPromptSubmit 拦截集成到 `_submit()` 流程。
**对外接口:** `GCodeApp` 私有方法 `_dispatch_session_start` / `_dispatch_session_end` 等。
**依赖:** 模块 D。
**改动文件:** `src/gcode/tui/app.py`、`src/gcode/tui/stream.py`、`src/gcode/tui/commands.py`(/clear、/resume 触发 SessionEnd + SessionStart/Resume)。

### 模块 I:`/hooks` 命令**职责:** 输出已加载 hook 列表 + 加载来源文件。
**对外接口:** 注册到 `command.register_builtins`。
**依赖:** `GCodeApp` 实现 UI 接口暴露 `hook_sources()` / `hook_rules()` 查询方法。

### 模块 J:cli wiring**职责:** 在 `cli.main` 中调 `hook.load(project_root)`,把 Engine 注入 agent 与 App。
**改动文件:** `src/gcode/cli.py`、`src/gcode/tui/app.py`(`AppParams` 加 `hook_engine` 字段)。

## 文件组织

```
gcode/
├── pyproject.toml
├── src/gcode/
│   ├── permission/
│   │   ├── __init__.py
│   │   ├── matcher.py            # 新增:Matcher Protocol 与四种实现
│   │   ├── rule.py               # 改造:parse_rule 识别前缀、Rule 持有 matcher
│   │   ├── settings.py           # 改造:to_rule_set 报 stderr
│   │   └── ...
│   ├── hook/                     # 全新包
│   │   ├── __init__.py           # 暴露 Engine / Event / load / DispatchResult
│   │   ├── event.py              # 11 个 Event 枚举 + 拦截类列表 + is_blocking
│   │   ├── rule.py               # Rule / Condition / Action / Payload 数据结构
│   │   ├── matcher.py            # eval_condition / get_by_path(复用 permission.Matcher)
│   │   ├── loader.py             # YAML 解析、字段校验、双层合并
│   │   ├── engine.py             # Engine + dispatch 主流程 + only_once 集合
│   │   └── executor.py           # 四类 action 执行器
│   ├── agent/
│   │   ├── agent.py              # 增 _dispatch_hook 与 PreToolUse/PostToolUse/Stop/PreCompact 等 emit
│   │   ├── runtime.py            # SessionRuntime 加 pending_reminders、hook_engine 字段
│   │   └── ...
│   ├── command/
│   │   └── builtins.py           # 加 /hooks 命令
│   ├── tui/
│   │   ├── app.py                # AppParams 加 hook_engine、App 持有
│   │   ├── stream.py             # _submit() 内拦截 + SessionStart emit
│   │   ├── commands.py           # /clear / /resume 触发 SessionEnd + SessionStart/Resume
│   │   └── hooks.py              # 新增:/hooks handler、App 的 hook 查询方法
│   └── cli.py                    # 加 hook.load(root) 与 wiring
├── tests/
│   ├── permission/
│   │   ├── test_matcher.py       # 四种 type 覆盖
│   │   └── test_rule.py          # parse_rule 新语法
│   ├── hook/
│   │   ├── test_loader.py        # 校验项覆盖
│   │   ├── test_engine.py        # 各事件 dispatch + 拦截 + reminder + once 覆盖
│   │   └── test_executor.py      # shell exit2 / http block / prompt / subagent stub 覆盖
│   ├── agent/
│   │   └── test_runtime.py       # pending_reminders 覆盖
│   └── tui/
│       └── test_stream.py        # _submit 拦截覆盖
└── docs/python/ch12/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 匹配前缀语法 | `=` 精确、`!` 反向、`~` 正则、无前缀=glob | 单字符前缀让既有 `Bash(git *)` 这种写法继续 work;用户写新形式时直观(=foo 一眼就是精确) |
| 反向类型嵌套 | `!=value`、`!~regex`、`!glob` 都合法 | 反向是一元运算,对内层 matcher 取反;嵌套写法直接,不需要 `not()` 函数语法 |
| Matcher 用 Protocol + dataclass | 而非 enum + match-case | Protocol 与 frozen dataclass 组合贴合 Python 习惯,Matcher 不可变;新增类型时只要实现 `match` / `__str__` 即可 |
| Hook 包独立 | `gcode.hook` | 与 `gcode.permission` 平级;hook 依赖 `permission.Matcher`,但 permission 不依赖 hook,无循环 |
| Event 用 `str` 枚举 | `class Event(str, enum.Enum)` | YAML 字面量(SessionStart 等)与 enum value 直接对应;`Event("SessionStart")` 反查方便;日志可读 |
| Payload 用 dict[str, Any] | 而非 dataclass | 11 个事件字段差异大;dict + `get_by_path` 灵活;`json.dumps(..., sort_keys=True)` 天然有序 |
| Reminder 注入用 SessionRuntime 而非 Engine 状态 | `runtime.pending_reminders` | 与现有 plan reminder 同一注入点;下一轮自动清空;不污染 Engine |
| PreToolUse 拦截位置 | 权限 check 之前 | 让用户能用 hook 早于权限引擎做安全策略;hook 拦截后甚至不调权限 check |
| shell 用 sh -c | 而非 list 形式 `["sh", "-c", ...]` 直接给 exec | 用户写 hook 时常用 `\|`、`>` 这种 shell 语法;`create_subprocess_shell` 直接交给 sh 解释 |
| HTTP 默认 POST + JSON body | 而非 GET | hook 多是"事件通知"语义,POST 更合理;用户需要 GET 时显式声明 method |
| HTTP body 用 `str.format_map` | 不开放 Jinja2 等函数 | `format_map` 已经够覆盖字段插值;不引入额外依赖,也避免模板注入风险 |
| HTTP 客户端用 httpx | 而非标准库 urllib | httpx 原生 async,与 Textual 事件循环兼容;`httpx.AsyncClient` 复用连接池 |
| subagent 占位仅打日志 | 不抛异常也不阻塞 | spec 明确本期不实现,但配置应能加载——避免用户写早期配置后续章节直接生效 |
| only_once 用内存 set | 不写盘 | spec N5 明确本期不持久化;set 在 runtime 里,与 ActiveSkills 同生命周期 |
| 事件分派同步串行 | 多 hook 不并发 | 拦截语义需要顺序;同步 stderr 日志顺序也确定;async hook 单独起 task 但 dispatch 不等 |
| 拦截类 sync timeout 不全局上限 | 单条 hook timeout 累加 | 用户配的 timeout 自己负责;全局上限会引入复杂语义 |
| 字段名 `asyncio_mode` 替代 `async` | 避免与 Python 关键字冲突 | YAML 里仍写 `async: true`,Loader 内部映射到 `Rule.asyncio_mode`;dataclass 字段名要合法 |
| `/hooks` 命令风格 | 与 `/skill` 对齐 | 已加载条目按事件分组、每条一行;末尾标加载来源 |
| 加载来源记录 | `engine._sources: list[str]` | YAML 文件路径列表,`/hooks` 命令通过 `engine.sources` 取出展示 |
````

````markdown
# Hook 生命周期挂钩系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gcode/permission/matcher.py` | Matcher Protocol、四种实现、`compile_matcher` 工厂 |
| 新建 | `tests/permission/test_matcher.py` | 四种 type × 边界条件覆盖 |
| 修改 | `src/gcode/permission/rule.py` | `parse_rule` 识别前缀、`Rule` 持有 `matcher` 替代 pattern 字符串、`hit_any` / `match_rule` 改造 |
| 修改 | `tests/permission/test_rule.py` | 扩展用例覆盖新语法 |
| 修改 | `src/gcode/permission/settings.py` | `to_rule_set` 改造:失败 rule 走 stderr |
| 修改 | `tests/permission/test_settings.py` | 验证 stderr 报错与跳过逻辑 |
| 新建 | `src/gcode/hook/__init__.py` | 包标识 + 暴露 `Engine` / `Event` / `load` / `DispatchResult` |
| 新建 | `src/gcode/hook/event.py` | 11 个 `Event` 枚举 + 拦截类列表 + `is_blocking` 判定 |
| 新建 | `src/gcode/hook/rule.py` | `Rule` / `Condition` / `Action` / `Payload` 数据结构 |
| 新建 | `src/gcode/hook/matcher.py` | `eval_condition` / `get_by_path` |
| 新建 | `src/gcode/hook/loader.py` | YAML 解析、双层合并、字段校验 |
| 新建 | `tests/hook/test_loader.py` | 字段校验、加载错误、合并测试 |
| 新建 | `src/gcode/hook/engine.py` | `Engine` + dispatch 主流程 + only_once |
| 新建 | `tests/hook/test_engine.py` | 各事件 dispatch、拦截、reminder、once 覆盖 |
| 新建 | `src/gcode/hook/executor.py` | 四类 action 执行器 |
| 新建 | `tests/hook/test_executor.py` | shell exit2、http block、prompt、subagent stub |
| 修改 | `src/gcode/agent/runtime.py` | `SessionRuntime` 加 `pending_reminders` + `hook_engine` 字段 + `reset_for_new_session` 清空 |
| 修改 | `tests/agent/test_runtime.py` | 验证 `pending_reminders` 行为 |
| 修改 | `src/gcode/agent/agent.py` | `Agent.__init__(..., hook_engine=...)` 参数、11 个 emit 点(部分由 tui 触发,agent 负责 PreUserMessage/PreToolUse/PostToolUse/PreCompact/PostCompact/Stop/Notification) |
| 修改 | `tests/agent/test_agent.py` | 拦截路径测试 |
| 新建 | `src/gcode/tui/hooks.py` | `/hooks` 命令 handler、App 的 hook 查询方法 |
| 修改 | `src/gcode/tui/app.py` | `AppParams` 加 `hook_engine`、App 持有;`on_mount` 触发 SessionStart |
| 修改 | `src/gcode/tui/stream.py` | `_submit()` 内 UserPromptSubmit dispatch + 拦截集成 |
| 修改 | `src/gcode/tui/commands.py` | `/clear`、`/resume` 触发 SessionEnd + SessionStart/Resume |
| 修改 | `src/gcode/command/builtins.py` | 加 `/hooks` 内置命令 |
| 修改 | `src/gcode/command/ui.py` | UI 接口加 hook 查询方法 |
| 修改 | `src/gcode/cli.py` | 加 `hook.load(root)` 与 wiring;SessionEnd 兜底 |
| 修改 | `pyproject.toml` | 新增依赖 `httpx`(若未引入) |

## T1: 实现 `permission.Matcher` 接口与四种类型**文件:** `src/gcode/permission/matcher.py`
**依赖:** 无
**步骤:**
1. 新建 `matcher.py`,声明 `Matcher(Protocol)`,要求 `match(s: str) -> bool` 与 `__str__`
2. 实现 4 个 frozen dataclass:
   - `ExactMatcher(value: str)`:`match` 返回 `s == value`
   - `GlobMatcher(pattern: str, is_command: bool)`:command 模式调 `match_command`,否则 `match_path`;`__str__` 返回 `pattern`
   - `RegexMatcher(src: str, compiled: re.Pattern[str])`:`match` 返回 `compiled.search(s) is not None`
   - `NotMatcher(inner: Matcher)`:`match` 返回 `not inner.match(s)`
3. 实现工厂 `compile_matcher(pattern: str, *, is_command: bool) -> Matcher`:
   - 空串 → `raise ValueError("empty matcher pattern")`
   - 以 `=` 起头 → `ExactMatcher(rest)`
   - 以 `~` 起头 → `re.compile(rest)`,失败转 `ValueError`
   - 以 `!` 起头 → 递归 `compile_matcher(rest, is_command=is_command)` 包装为 `NotMatcher`
   - 其它 → `GlobMatcher(pattern, is_command)`
4. `match_command` / `match_path` 沿用 `permission` 包已有实现(若未抽出可在本模块内重用 `fnmatchcase`)
5. 写 docstring 解释每个 Matcher 类型的语义

**验证:** `python -c "from gcode.permission.matcher import compile_matcher; print(compile_matcher('=foo', is_command=False))"` 输出 `=foo`

## T2: matcher 单元测试**文件:** `tests/permission/test_matcher.py`
**依赖:** T1
**步骤:**
1. 覆盖 4 种类型各自的命中/不命中用例
2. `=git status` 命中 `git status`、不命中 `git status -s`
3. `~^npm (install|test)$` 命中 `npm install`、不命中 `npm run dev`
4. `!=foo` 不命中 `foo`、命中 `bar`
5. `!~^rm` 命中 `ls -lh`、不命中 `rm -rf .`
6. `!git *` 命中 `npm install`、不命中 `git status`(嵌套 not + glob)
7. 编译失败:`~[invalid` 应抛 `ValueError`
8. 空串:`""` 应抛 `ValueError`
9. 用 `pytest.mark.parametrize` 表驱动,每条用例附 `id=...` 描述

**验证:** `pytest tests/permission/test_matcher.py -v` 通过

## T3: 升级 `permission.Rule` 与 `parse_rule`**文件:** `src/gcode/permission/rule.py`
**依赖:** T1
**步骤:**
1. `Rule` dataclass 改:去 `pattern` 字段、加 `matcher: Matcher | None`(`None` 表示该工具全匹配)与 `raw: str`(原始描述)
2. `parse_rule` 签名改:`def parse_rule(s: str) -> tuple[Rule | None, str | None]`——返回错误描述让 `to_rule_set` 写日志
3. `parse_rule` 内部:剥出 `tool` 与 `pattern` 后调 `compile_matcher(pattern, is_command=(tool == "Bash"))`;空 pattern 仍按 `None` matcher 表示"全匹配"
4. 改造 `match_rule(r: Rule, target: str)`:`r.matcher is None` 返回 True(全匹配),否则 `r.matcher.match(target)`
5. `escape_glob` 保留不变,仅供 ch08 自动生成的精确规则使用
6. docstring 更新说明四种语法

**验证:** `pytest tests/permission/ -k rule` 不出现导入错误

## T4: 升级 `to_rule_set` 错误日志**文件:** `src/gcode/permission/settings.py`
**依赖:** T3
**步骤:**
1. `to_rule_set` 改造:`parse_rule` 失败时 `print(f'rule {raw!r} parse failed: {err}', file=sys.stderr)`
2. 顶部 `import sys`
3. 加注释说明:失败的 rule 不进入 RuleSet,但其它 rule 不受影响

**验证:** `python -c "from gcode.permission.settings import to_rule_set; print('ok')"` 不报错

## T5: 扩展 `test_rule` 与 `test_settings`**文件:** `tests/permission/test_rule.py`、`tests/permission/test_settings.py`
**依赖:** T3、T4
**步骤:**
1. `test_rule`:补充用例
   - `Bash(=git status)` 精确匹配
   - `Bash(~^npm.*)` 正则匹配
   - `Bash(!~^rm)` 反向正则
   - `Write(**/*.py)` glob 沿用(确认向后兼容)
2. `test_settings`:用 `capsys` fixture 捕获 stderr,构造一份含非法 rule 的 yaml,验证 `to_rule_set` 返回的 RuleSet 不含该 rule(检查 `rule_set.allow` / `deny` 长度即可),且 stderr 含 `parse failed`
3. 旧测试 `test_match_command` / `test_match_path` 改成调用 matcher 的形式或保留底层函数测试

**验证:** `pytest tests/permission/ -v` 全部通过

## T6: hook 包基础数据结构**文件:** `src/gcode/hook/__init__.py`、`src/gcode/hook/event.py`、`src/gcode/hook/rule.py`
**依赖:** 无
**步骤:**
1. `__init__.py`:包标识,re-export `Engine` / `Event` / `load` / `DispatchResult`
2. `event.py`:
   - `class Event(str, enum.Enum)`,11 个成员对应 YAML 字面量(`SESSION_START = "SessionStart"` 等)
   - `BLOCKING_EVENTS: frozenset[Event] = frozenset({Event.PRE_TOOL_USE, Event.USER_PROMPT_SUBMIT})`
   - `def is_blocking(e: Event) -> bool: return e in BLOCKING_EVENTS`
   - `def parse_event(s: str) -> Event | None`:`Event(s)` 包 try/except `ValueError`
3. `rule.py`:
   - `Rule`、`Condition`、`AtomCondition`、`Action`、`ShellAction`、`PromptAction`、`HttpAction`、`SubagentAction`、`ActionType`、`CombineMode` 等 dataclass / 枚举
   - 类型别名 `Payload = dict[str, Any]`
   - 注意:`Rule.asyncio_mode` 字段替代 YAML 的 `async`(Python 关键字)

**验证:** `python -c "from gcode.hook import Event; print(Event.PRE_TOOL_USE.value)"` 输出 `PreToolUse`

## T7: `hook.matcher` 字段路径求值**文件:** `src/gcode/hook/matcher.py`
**依赖:** T6、T1
**步骤:**
1. `get_by_path(p: Payload, path: str) -> str`:按 `.` 分隔;递归取值;中途遇 `None` 或非 dict 返回空串
2. 字段值非字符串时:`bool` / `int` / `float` 用 `str(value)`(`True` → `"True"`,与 N6 输出保持一致);嵌套对象转 `json.dumps(value, sort_keys=True)`
3. `eval_condition(c: Condition | None, p: Payload) -> bool`:
   - `c is None` → True
   - 遍历 `c.atoms`,每条用 `get_by_path` + `AtomCondition.matcher.match`
   - `CombineMode.ALL_OF` 要求全部 True、`CombineMode.ANY_OF` 要求至少一个 True

**验证:** `pytest tests/hook/test_matcher.py`(若新增独立测试)通过;或在 `test_engine.py` 间接覆盖

## T8: `hook.Loader` YAML 解析**文件:** `src/gcode/hook/loader.py`
**依赖:** T6、T7、T1
**步骤:**
1. 定义 `def load(project_root: str | Path) -> Engine`:
   - 计算两个候选路径:`<project_root>/.gcode/hooks.yaml`、`Path.home() / ".gcode" / "hooks.yaml"`
   - 文件不存在跳过;存在但 `yaml.safe_load` 失败时 `print(..., file=sys.stderr)` 后跳过整文件
   - 顶层结构必须含 `hooks: list`;不合法整文件跳过并打 stderr
   - 对每条 dict 调内部 `_compile_rule(source, idx, raw) -> Rule | None`
   - 累积成功的 rule、stderr 输出失败的 rule
   - 跨文件 name 冲突时跳过后者,stderr 打提示
2. `_compile_rule` 内做字段校验:
   - `name` 必填且非空
   - `event` 枚举(用 `parse_event`,失败 → `hook "<name>": unknown event "<value>", skipped`)
   - `action.type` 枚举与子字段必填(`shell.command`、`prompt.text`、`http.url`、`subagent.agent_name` + `subagent.prompt`)
   - `if` 顶层 `all_of` / `any_of` 互斥
   - 每个原子条件的 `match.type` ∈ `{exact, glob, regex, not}` 且 `value` / `inner` 字段完整
   - `async` + `is_blocking(event)` → 报错 `hook "<name>": async not allowed for blocking events, skipped` 跳过
   - `timeout` 字符串解析:支持 `30s` / `5m` / 浮点秒;用一个小函数 `_parse_duration(s) -> float`(用 `re` 匹配 `\d+(\.\d+)?([smh]?)`),失败 → 报错跳过;缺省 30.0
3. Matcher 编译用 `permission.compile_matcher`;hook 上下文中的 matcher 都作用于 payload 字段值,统一传 `is_command=False`(glob 走 `match_path`,段内 `*` 不跨 `/`)
   - **决策修正**:tool_input.command 这类 shell 字符串字段如果想做整串通配,用户应改用 regex 表达;文档中注明此约束

**验证:** `python -c "from gcode.hook.loader import load; print(load('.'))"` 不抛异常

## T9: `hook.Loader` 测试**文件:** `tests/hook/test_loader.py`
**依赖:** T8
**步骤:**
1. `tmp_path` fixture 场景:写一份合法 `hooks.yaml`(含 2 条 hook),`load` 返回 Engine 含 2 条 rule
2. 字段缺失:name 空、event 不存在、action.type 无效 → 跳过该条但其它通过
3. `all_of` + `any_of` 同时存在 → 跳过该条
4. async + PreToolUse → 跳过该条且 capsys 捕获 stderr 含 `async not allowed for blocking events`
5. 跨文件同名冲突 → 项目级保留、用户级跳过(monkeypatch `Path.home` 指向 tmp_path)
6. matcher 编译失败(非法正则) → 跳过该条

**验证:** `pytest tests/hook/test_loader.py -v` 通过

## T10: `hook.Engine` 与 dispatch 主流程**文件:** `src/gcode/hook/engine.py`
**依赖:** T6、T7
**步骤:**
1. `Engine` 类:`_rules`、`_sources`、`_lock: asyncio.Lock`、`_once_fired: set[str]`、`_executor`
2. `__init__(self, rules: list[Rule], sources: list[str])`
3. `async def dispatch(self, event: Event, payload: Payload) -> DispatchResult`:
   - 遍历 rules,跳过非本事件
   - 加锁查 `_once_fired`,命中跳过;`reset_for_new_session` 清空
   - `eval_condition`;不通过跳过
   - 命中后:
     - `rule.asyncio_mode` 为 True → `asyncio.create_task(self._executor.run(rule, payload, blocking=False))`,立即继续(不等结果、不进入 `injected_prompts` 与 `blocked` 判定);若 only_once,标记 fired
     - 同步:`await self._executor.run(rule, payload, blocking=is_blocking(event))`
   - 同步结果处理:
     - `outcome.err is not None` → stderr 日志 `[hook <name>] <event.value> failed: <reason>`,继续下一个 rule(不拦截)
     - `outcome.prompt` 非空 → 加入 `injected_prompts`
     - `outcome.blocked and is_blocking(event)` → 设置 `result.blocked` + `reason` + `blocking_hook_name`,break
   - 命中且执行无 fatal err 的 rule,若 `only_once` → 加入 `_once_fired`
4. `async def reset_for_new_session(self)`:加锁清空 `_once_fired`
5. property `sources` 与 `rules` 返回副本

**验证:** `python -c "import asyncio; from gcode.hook.engine import Engine; asyncio.run(Engine([], []).dispatch('Stop', {}))"` 通过(传字面量会失败,改用 Event.STOP)

## T11: `hook.Executor` 四类动作执行**文件:** `src/gcode/hook/executor.py`
**依赖:** T6
**步骤:**
1. `Executor` 类(可空字段或仅 `_http_client: httpx.AsyncClient`)
2. `__init__(self)`:`self._http_client = httpx.AsyncClient()`(单实例复用连接池)
3. `async def run(self, rule, payload, *, blocking) -> ExecutionResult` 分发到下面四个内部方法
4. `async def _run_shell(self, sa, payload, blocking, timeout)`:
   - `proc = await asyncio.create_subprocess_shell(sa.command, stdin=PIPE, stdout=PIPE, stderr=PIPE)`
   - `payload_json = json.dumps(payload, sort_keys=True).encode()`
   - `stdout, stderr = await asyncio.wait_for(proc.communicate(payload_json), timeout=timeout)`
   - 超时 `asyncio.TimeoutError`:`proc.kill(); await proc.wait()`,返回 `err=TimeoutError(...)`
   - `blocking and proc.returncode == 2` → `blocked=True, reason=(stderr or stdout).decode().rstrip("\n")`
   - `proc.returncode == 0` → 不拦截不报错
   - 其它非 0 returncode → `err=RuntimeError(f"exit {code}: {stderr.decode()}")`
5. `def _run_prompt(self, pa) -> ExecutionResult`:返回 `ExecutionResult(prompt=pa.text)`
6. `async def _run_http(self, ha, payload, blocking, timeout)`:
   - 默认 `method = ha.method or "POST"`
   - body:`ha.body is None` 时 `json.dumps(payload, sort_keys=True)`;否则 `ha.body.format_map(payload)`,渲染异常按 `err` 处理
   - `resp = await self._http_client.request(method, ha.url, content=body, headers=ha.headers, timeout=timeout)`
   - status 2xx 且 `json.loads(resp.text)` 含 `{"decision":"block","reason":"..."}` → `blocked=True`
   - 网络错(`httpx.HTTPError`) / 超时(`httpx.TimeoutException`) / JSON 解析失败 → `err`
7. `def _run_subagent(self, sa) -> ExecutionResult`:仅 `print(f"[hook subagent] not yet implemented, skipped: {sa.agent_name}", file=sys.stderr)`,返回空 `ExecutionResult()`
8. payload JSON 序列化用共享辅助 `_marshal_sorted(p) -> bytes`,保证 key 字典序

**验证:** `python -c "from gcode.hook.executor import Executor; print(Executor())"` 通过

## T12: executor 单元测试**文件:** `tests/hook/test_executor.py`
**依赖:** T11
**步骤:**
1. shell exit 2 with stderr → blocked=True + reason 含 stderr
2. shell exit 0 → 放行不报错
3. shell exit 1 → err 非 None 不拦截
4. shell stdin JSON 解析:脚本读 stdin 后 echo 出来,验证 key 字典序(`sh -c "cat"` + 比对输出)
5. shell timeout:`sleep 2 && echo done` + timeout 0.1s → err 类型为 `TimeoutError`
6. prompt → result.prompt 字段非空
7. http with `pytest-httpserver` 或自起 `aiohttp` 桩返回 `{"decision":"block","reason":"x"}` → blocked=True
8. http with 5xx → err 非 None
9. http 模板 body 含 `{event}` → server 收到正确字段
10. subagent → capsys 捕获 stderr 含占位文本

**验证:** `pytest tests/hook/test_executor.py -v` 通过

## T13: `hook.Engine` 测试**文件:** `tests/hook/test_engine.py`
**依赖:** T10、T11
**步骤:**
1. 多 rule 同事件按声明序执行
2. 拦截类事件下首个 blocked 的 rule 中断后续
3. 非拦截类事件下 blocked 字段不传递(fake exit code 2 但 `is_blocking(event)=False` 也不 set `blocked`)
4. prompt rule 的 prompt 累加到 `injected_prompts`
5. only_once 在首次执行后被加入 `_once_fired`,第二次 dispatch 跳过
6. `reset_for_new_session` 后 only_once 重置
7. async rule 不进入 blocked 判定(用 `asyncio.Event` 验证 task 已起)

**验证:** `pytest tests/hook/test_engine.py -v` 通过

## T14: agent `SessionRuntime` 扩展**文件:** `src/gcode/agent/runtime.py`、`tests/agent/test_runtime.py`
**依赖:** T6
**步骤:**
1. `SessionRuntime` 加字段:`pending_reminders: list[str]`、`hook_engine: Engine | None`
2. `__init__` 初始化空 list 与 None
3. `async def reset_for_new_session(self)`:清空 `pending_reminders`、若 `hook_engine is not None` 调 `await hook_engine.reset_for_new_session()`
4. 新增 `def append_reminders(self, prompts: list[str]) -> None`:加锁(`threading.Lock` 或 `asyncio.Lock`)追加
5. 新增 `def take_reminders(self) -> list[str]`:加锁取出并清空
6. 测试覆盖:`append_reminders` + `take_reminders` 单线程行为;`reset_for_new_session` 清空

**验证:** `pytest tests/agent/test_runtime.py -v` 通过

## T15: `Agent.__init__` 加 hook_engine 与 emit 框架**文件:** `src/gcode/agent/runtime.py`、`src/gcode/agent/agent.py`
**依赖:** T14
**步骤:**
1. `Agent.__init__` 新增 `hook_engine: Engine | None = None` 参数,赋给 `self._hook_engine`
2. 私有方法 `async def _dispatch_hook(self, event: Event, payload: Payload) -> DispatchResult`:
   - `self._hook_engine is None` → 返回空 `DispatchResult`
   - `await self._hook_engine.dispatch(event, payload)`
   - 把 `injected_prompts` 调 `self._runtime.append_reminders`
   - 返回结果(保留 `blocked` + `reason` 供 PreToolUse 用)
3. 私有方法 `def _build_reminder(self, mode, iter) -> str`:
   - 原 `plan_reminder` + `"\n\n".join(self._runtime.take_reminders())`

**验证:** `python -c "from gcode.agent.agent import Agent; print(Agent)"` 通过

## T16: agent 各事件 emit 接入**文件:** `src/gcode/agent/agent.py`
**依赖:** T15
**步骤:**
1. 每轮 iter 顶部、`_manage_context_auto` 之前 `await self._dispatch_hook(Event.PRE_COMPACT, {"trigger":"auto"})`;`manage_context` 返回后 emit `Event.POST_COMPACT` 带 before/after tokens
2. `_emergency_compact_and_decide`:同样 PreCompact/PostCompact,trigger="emergency"
3. `_stream_once` 调 `provider.stream` 之前 emit `Event.PRE_USER_MESSAGE`,payload 含 conversation 末尾 user 消息
4. 把 reminder 串改造:取 `self._build_reminder(mode, iter)` 替代原裸的 `plan_reminder(full)`
5. `_execute_batched` 改造:
   - 单工具循环开始处 emit PreToolUse,payload 含 `tool_name`、`tool_input`;`blocked=True` 时构造 `_hook_blocked_result`、emit PhaseStart/PhaseEnd(is_error=True),continue
   - tool 拿到 result 后、emit PhaseEnd 之前 emit PostToolUse,payload 含 `tool_name`、`tool_input`、`tool_result`、`is_error`
6. emit Done 之前调 `Event.STOP`,payload `{"iter": iter}`
7. emit Approval 之前调 `Event.NOTIFICATION`,payload `{"kind":"approval", "detail": tool_name}`
8. emit Err 之前调 `Event.NOTIFICATION`,payload `{"kind":"stream_error", "detail": str(err)}`
9. 拦截结果整合:定义 `_hook_blocked_result(call_id, hook_name, reason) -> ToolResult`:`content=f"[hook {hook_name}] {reason}"`、`is_error=True`

**验证:** `python -c "from gcode.agent.agent import Agent; print('ok')"` 通过

## T17: `test_agent` 拦截路径与 emit 覆盖**文件:** `tests/agent/test_agent.py`、`tests/agent/test_runtime.py`
**依赖:** T16
**步骤:**
1. 构造一个 fake provider + 真实 `hook.Engine` 注入合成 rules
2. 测试:PreToolUse 拦截时工具结果是 `_hook_blocked_result` 形式、PhaseStart/PhaseEnd 仍 emit
3. 测试:PreUserMessage 注入的 prompt 在下一次 `_stream_once` 的 reminder 串中可见
4. 测试:Stop 事件在 Done 前一刻被 emit
5. 用 `pytest-asyncio` 跑 async 测试函数

**验证:** `pytest tests/agent/ -k hook -v` 通过

## T18: tui `GCodeApp` 持有 `hook_engine`**文件:** `src/gcode/tui/app.py`
**依赖:** T15
**步骤:**
1. `AppParams` dataclass 加 `hook_engine: Engine | None`
2. `GCodeApp` 类加属性 `self.hook_engine: Engine | None`
3. `__init__` 内:
   - 把 `params.hook_engine` 赋给 `self.hook_engine` 与 `self.runtime.hook_engine`
   - 构造 agent 时传 `hook_engine=params.hook_engine`
4. `on_mount()` 末尾 `await self._dispatch_session_start()`

**验证:** `python -c "from gcode.tui.app import GCodeApp; print(GCodeApp)"` 通过

## T19: tui `UserPromptSubmit` 拦截集成**文件:** `src/gcode/tui/stream.py`
**依赖:** T18
**步骤:**
1. `_submit()` 重写:
   - 现有的 strip 与 slash 分发保留
   - 非 slash 路径:构造 payload `self._base_payload() | {"prompt": text}`
   - `result = await self.hook_engine.dispatch(Event.USER_PROMPT_SUBMIT, payload)`
   - `result.blocked` → `self._show_error_block(f"[hook {result.blocking_hook_name}] {result.reason}")`,不消费 `Input`
   - 否则:`self.runtime.append_reminders(result.injected_prompts)`;`self.conv.add_user(text)`;`await self._begin_turn()`
2. 提供辅助方法 `def _base_payload(self) -> Payload`:返回 `{"event": event.value, "session_id": ..., "cwd": str(self.cwd), "mode": self.mode.name.lower()}` 通用字段(event 由 caller 设置)

**验证:** `python -c "from gcode.tui.stream import ..."` 通过

## T20: tui SessionStart / End / Resume**文件:** `src/gcode/tui/app.py`、`src/gcode/tui/commands.py`、`src/gcode/tui/stream.py`
**依赖:** T18、T19
**步骤:**
1. 新增 `async def _dispatch_session_start(self)`:构造 payload + 调 `Engine.dispatch` + `injected_prompts` 写入 runtime
2. 新增 `async def _dispatch_session_end(self)`:仅同步调 dispatch
3. 新增 `async def _dispatch_session_resume(self)`:同 SessionStart 流程,event 改为 `Event.SESSION_RESUME`
4. `on_mount()` 末尾 await `_dispatch_session_start`
5. `/clear` handler 内:先 `await self._dispatch_session_end()`,再 `await self.runtime.reset_for_new_session()`,最后 `await self._dispatch_session_start()`
6. `/resume` handler 选中会话恢复完毕后:先 `await self._dispatch_session_end()`(旧),切到新会话后 `await self._dispatch_session_resume()`
7. `handle_exit` 内:`await self._dispatch_session_end()` 后再退出
8. App 退出前由 `cli.main` 兜底:`await hook_engine.dispatch(Event.SESSION_END, base_payload)`(确保 Ctrl+C 退出也 emit)
   - 实际:`cli.main` 在 `app.run_async()` 返回后调一次 `dispatch`;tui 内的 `/clear`、`/resume` 自己控制

**验证:** `python -c "from gcode.tui.app import GCodeApp; print('ok')"` 通过

## T21: `/hooks` 命令**文件:** `src/gcode/tui/hooks.py`、`src/gcode/command/builtins.py`、`src/gcode/command/ui.py`
**依赖:** T6、T10、T18
**步骤:**
1. UI Protocol 加方法 `hook_sources() -> list[str]`、`hook_rules() -> list[Rule]`
2. `GCodeApp` 实现这两个方法(读 `self.hook_engine` 属性,None 时返回空)
3. 新增 `src/gcode/tui/hooks.py`,实现 `async def handle_hooks(ctx, ui)`:
   - 取 rules 与 sources
   - 空时 `await ui.write_line("No hooks loaded.")`
   - 否则按 event 分组(保留 yaml 声明顺序)、每条一行 `  <name>  <event>  <action.type>  [once] [async]`
   - 末尾 `Loaded from: file1, file2`
4. `builtins.py` 注册新命令 `/hooks`,KindLocal,描述"列出已加载的 hook 列表"

**验证:** `pytest -k hooks_command -v` 通过(或手动启动后输入 `/hooks`)

## T22: `cli.main` wiring**文件:** `src/gcode/cli.py`
**依赖:** T8、T18
**步骤:**
1. 在 `permission.new_engine` 之后调 `hook_engine = hook.load(root)`
2. `tui.create_app` 传 `hook_engine=hook_engine`
3. `await app.run_async()` 之后调:
   ```python
   if hook_engine is not None:
       await hook_engine.dispatch(Event.SESSION_END, base_payload)
   ```
   兜底 SessionEnd
4. 顶部 `from gcode import hook`、`from gcode.hook import Event`

**验证:** `python -m gcode --help` 启动不报错

## T23: 整体编译与测试**文件:** —
**依赖:** T1-T22 全部
**步骤:**
1. `ruff check src tests` 通过
2. `pytest` 通过——hooks 相关测试 + 既有测试都得过

**验证:** 上述两条命令本地通过

## T24: 修复回归**文件:** 根据测试输出决定
**依赖:** T23
**步骤:**
1. 修复 ch08 / ch11 等老测试因 Matcher 改造而失败的用例
2. 修复 ch10 / ch11 测试因 `/hooks` 命令加入而影响排序或数量的用例
3. 重新跑全套测试

**验证:** `pytest` 全过

## T25: tmux 端到端实跑(验收 AC17 与 checklist 端到端场景)**文件:** `.gcode/hooks.yaml` 临时测试配置
**依赖:** T23、T24
**步骤:**
1. 写测试 `hooks.yaml`:包含 AC4-AC15 各典型场景的 hook
2. tmux 新建 session 启动 `python -m gcode` 或安装后的 `gcode`
3. 依次触发:`write_file` 工具调用、含 delete 关键字的用户输入、git 命令、Stop 事件
4. 观察 stderr 日志、tool_result 内容、reminder 注入是否符合预期
5. 全程不卡顿、无未捕获异常栈

**验证:** 见 checklist.md

## 执行顺序

```
T1 → T2 → T3 → T4 → T5            # permission Matcher 扩展
T6 → T7 → T8 → T9                 # hook 基础结构 + Loader
T10 → T13                         # Engine
T11 → T12                         # Executor(与 Engine 并行)
T14 → T15 → T16 → T17             # agent 接入
T18 → T19 → T20                   # tui 接入
T21                               # /hooks 命令
T22                               # cli wiring
T23 → T24                         # 整体编译测试
T25                               # tmux 实跑验收
```

并行机会:
- T11/T12 与 T10/T13 互不依赖,可并行
- T11 与 T8 在 T6 完成后可并行
- T17 必须在 T16 之后
- T19 之前 T18 必须先完成
````

````javascript
# Hook 生命周期挂钩系统 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### 权限匹配器扩展

- [ ] `permission.Matcher` Protocol 存在,四种实现(`ExactMatcher` / `GlobMatcher` / `RegexMatcher` / `NotMatcher`)各自可单独导入并运行(验证:`pytest tests/permission/test_matcher.py -v` 通过)
- [ ] `permission.Rule` 已替换 pattern 为 `matcher` 字段,`parse_rule` 能识别 `=` / `~` / `!` 前缀(验证:`pytest tests/permission/test_rule.py -v` 通过)
- [ ] `to_rule_set` 在 `parse_rule` 失败时输出 stderr 错误日志(验证:单测用 `capsys` 捕获含 `parse failed`)

### Hook 包

- [ ] `gcode.hook` 包存在且可导入(验证:`python -c "import gcode.hook"` 不抛 ImportError)
- [ ] 11 个 `Event` 成员全部声明且 `is_blocking` 仅对 `PRE_TOOL_USE` / `USER_PROMPT_SUBMIT` 返回 True(验证:`pytest tests/hook/test_event.py` 或集成在 `test_engine.py`)
- [ ] `load(...)` 能解析合法 YAML 并构造 Engine(验证:`test_loader.py` 全部通过)
- [ ] Loader 对字段缺失 / 枚举错 / async + 拦截事件冲突 / matcher 编译失败均报 stderr 并跳过该条(验证:对应 `test_loader.py` 子用例通过)
- [ ] `Engine.dispatch` 按声明顺序执行 rule 且拦截后中断后续(验证:`test_engine.py::test_dispatch_blocking` 通过)
- [ ] Executor 的 shell `returncode == 2` 触发 blocked、`returncode == 0` 放行、其它非 0 视为失败不拦截(验证:`test_executor.py::test_run_shell_*` 通过)
- [ ] Executor 的 HTTP 在 body 含 `{"decision":"block","reason":"..."}` 时触发 blocked(验证:`test_executor.py::test_run_http_*` 通过)
- [ ] Executor 的 prompt 动作通过 `ExecutionResult.prompt` 字段返回文本(验证:`test_executor.py::test_run_prompt` 通过)
- [ ] Executor 的 subagent 动作仅 stderr 输出占位日志、不阻塞(验证:`test_executor.py::test_run_subagent` 通过)
- [ ] only_once 状态在 `SessionRuntime` 上,`/clear` 与 `/resume` 时被 `reset_for_new_session` 清空(验证:`test_runtime.py::test_reset_for_new_session` 通过)

### agent / tui 集成

- [ ] `Agent.__init__` 接受 `hook_engine` 参数,agent 内部 `_dispatch_hook` 在 11 个 emit 点全部调用(验证:`test_agent.py::test_hook_emit_*` 覆盖每个事件)
- [ ] tui `_submit()` 在 UserPromptSubmit 拦截时不消费输入框、显示错误块(验证:`test_stream.py::test_submit_blocked` 通过)
- [ ] tui `on_mount()` 末尾派发 SessionStart 事件(验证:`test_app.py::test_init_dispatch_session_start` 或集成测试)
- [ ] `/clear` / `/resume` / `/exit` 触发 SessionEnd(验证:`test_commands.py::test_clear_dispatch_session_end` 等)
- [ ] `cli.main` 退出前兜底 SessionEnd(验证:cli 调用链审查)
- [ ] `/hooks` 命令注册到命令表(验证:`test_hooks_command.py` 中 `/hooks` 命令存在 + 输出格式正确)
- [ ] `pending_reminders` 在 `Agent.run` 取出后被清空(验证:`test_runtime.py::test_take_reminders` 通过)

## 集成

- [ ] `hook.Engine` 与 `permission.Matcher` 共用同一套匹配实现(验证:`gcode.hook` 包不重复实现 exact/regex/glob)
- [ ] `hook.Engine` 接入 `Agent.run` 后所有现有 agent 测试不破坏(验证:`pytest tests/agent/ -v` 全过)
- [ ] `hook.Engine` 接入 tui 后所有现有 tui 测试不破坏(验证:`pytest tests/tui/ -v` 全过)
- [ ] PreToolUse 拦截结果当 tool_result 回灌后,LLM 视角看到的是 `is_error=True` 的 `ToolResult`,`content` 含 `[hook <name>] <reason>`(验证:`test_agent.py` 检查 `results[call_id]` 字段)
- [ ] reminder 注入路径与 plan reminder 协同——同一轮 LLM 请求的 reminder 串同时含两类(验证:`test_agent.py` 中构造 plan 模式 + hook prompt 注入,断言 reminder 串包含两段)

## 编译与测试

- [ ] 项目可导入无错误:`python -c "import gcode"`
- [ ] 入口可启动:`python -m gcode --help` 正常输出
- [ ] 所有单元测试通过:`pytest`
- [ ] ruff 检查通过:`ruff check src tests`
- [ ] (可选)类型检查:`mypy src/gcode/hook` 无 error

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证人工/可视化行为。

### 场景 1:PreToolUse shell 拦截 write_file**预置:** 在 `.gcode/hooks.yaml` 写一条 hook:
```yaml
hooks:
  - name: block-write
    event: PreToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
    action:
      type: shell
      command: "echo blocked by hook >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 `python -m gcode`
- [ ] 给 LLM 输入"创建一个文件 hello.txt 内容是 hi"
- [ ] LLM 应触发 write_file,工具被拦截
- [ ] scrollback 内 tool_result 显示 `[hook block-write] blocked by hook`、文件未创建
- [ ] LLM 收到反馈后调整回应,不死循环

### 场景 2:SessionStart prompt 注入**预置:**
```yaml
hooks:
  - name: zh-cn-default
    event: SessionStart
    action:
      type: prompt
      text: "默认用 zh-CN 回复"
```

**步骤:**
- [ ] tmux 重启 gcode
- [ ] 立刻发一句英文输入"hi there"
- [ ] LLM 应该用中文回复(因为 reminder 区注入了 zh-CN 指令)

### 场景 3:PostToolUse async shell 后台 ruff format**预置:**
```yaml
hooks:
  - name: ruff-after-write
    event: PostToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
        - field: tool_input.path
          match: { type: glob, value: "**/*.py" }
        - field: is_error
          match: { type: exact, value: "False" }
    action:
      type: shell
      command: "ruff format \"$(jq -r .tool_input.path)\""
    async: true
    timeout: 5s
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 写一个故意排版不整齐的 Python 文件(如缩进错乱)
- [ ] LLM 完成写入后主对话立即进入下一轮,不停顿
- [ ] 验证文件被 `ruff format` 格式化(可手动 `cat` 该文件)

### 场景 4:UserPromptSubmit 拦截 delete 关键字**预置:**
```yaml
hooks:
  - name: warn-delete
    event: UserPromptSubmit
    if:
      all_of:
        - field: prompt
          match: { type: regex, value: "(?i)delete" }
    action:
      type: shell
      command: "echo \"用户消息含 delete 关键字\" >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入"请帮我 delete 那个文件"
- [ ] 输入被拦截,scrollback 内显示 `[hook warn-delete] 用户消息含 delete 关键字`
- [ ] 输入框内容仍在(被退回用户重新编辑)
- [ ] LLM 端未收到这条 user 消息(不发起请求)

### 场景 5:Stop HTTP 通知**预置:**
- 本地起 echo server:`python3 -m http.server 9999 --bind 127.0.0.1` 或 `nc -l 9999`
```yaml
hooks:
  - name: notify-stop
    event: Stop
    action:
      type: http
      url: "http://127.0.0.1:9999/done"
      method: POST
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 简单回答一个问题后停止
- [ ] echo server 收到一次 POST,body 含 `"event":"Stop"`

### 场景 6:only_once + PreUserMessage**预置:**
```yaml
hooks:
  - name: first-turn
    event: PreUserMessage
    only_once: true
    action:
      type: shell
      command: "echo first-turn-fired >&2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮发任意消息,stderr 出现 `first-turn-fired`
- [ ] 第二轮发消息,stderr 没有再次出现
- [ ] 执行 `/clear` 进新会话,再发消息,stderr 重新出现 `first-turn-fired`

### 场景 7:错误配置不阻断启动**预置:** `hooks.yaml` 含一条非法 hook:
```yaml
hooks:
  - name: bad-async
    event: PreToolUse
    async: true
    action:
      type: shell
      command: "echo x"
  - name: good-hook
    event: SessionStart
    action:
      type: shell
      command: "echo ok"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] gcode 启动期 stderr 打印 `hook "bad-async": async not allowed for blocking events, skipped`
- [ ] gcode 仍然成功进入 idle 状态
- [ ] `/hooks` 命令仅列出 `good-hook`、未列 `bad-async`

### 场景 8:`/hooks` 命令**预置:** 一份包含 3 条合法 hook 的 `hooks.yaml`(任意 event 组合)

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入 `/hooks` 回车
- [ ] 输出按 event 分组,每条一行 `  <name>  <event>  <action.type>  [flags]`
- [ ] 末尾显示 `Loaded from: .../hooks.yaml`

### 场景 9:端到端组合(AC17)**预置:** `hooks.yaml` 包含场景 1、2、3、4 全部 hook

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 首轮:SessionStart 注入 zh-CN(场景 2),Agent 准备就绪
- [ ] 输入"帮我创建 hello.py,然后 ruff format 一下"
- [ ] LLM 调 write_file 创建文件 → 被场景 1 的 hook 拦截 → LLM 重试(可能换 edit_file)或换 bash 调 ruff
- [ ] 整个过程不卡顿、无未捕获异常栈
- [ ] `/hooks` 命令仍可工作显示 4 条 hook
````

### Java

````markdown
# Hook 生命周期挂钩系统 Spec## 背景把可复用 SOP 搬出源码做成 Skill 包之后,GCode 在"用户怎么扩展行为"这条路径上还差最后一环:**在 Agent 生命周期的固定时刻自动跑一段用户配置的动作**。当前的扩展点都是显式触发——Skill 要 `/<name>` 唤起、Slash 命令要用户手敲。如果想做这种"触发条件明确、动作固定"的重复事,只能每次手动来:

- 写完文件想立刻 `mvn spotless:apply`,得手动跑或写监听脚本
- 想阻止 Agent 跑 `rm -rf` 之类的命令,权限规则要逐个加 deny
- 想在每轮用户提交前提醒 Agent "记得用 zh-CN",没现成机制
- 想在 Agent 长跑结束后给自己发个 IM 通知,要自己起进程

ch08 的权限引擎覆盖了"该不该允许工具调用",但**只在工具调用前判定一次、动作仅 Allow/Deny/Ask**,做不了命令格式化、上下文注入、外部通知这些副作用。Hook 系统补的是这条缝:在 Agent 生命周期的 11 个固定时刻挂自动化动作,把"触发条件明确、动作固定"的重复工作从人工变成机器。

设计上沿用 ch08 已有的权限匹配器做条件表达式底层——但需先把单一通配匹配扩展成"精确/反向/正则/glob"四种,让 Hook 条件、未来的权限规则共用同一套匹配语义。

## 目标- **G1**:把 Agent 生命周期上的 11 个固定时刻抽象成事件总线,事件 emit 时同步驱动 Hook 引擎;现有内部事件(工具 Start/End、Compact、Approval)继续走 `Flow.Publisher<AgentEvent>` 主流,不受影响
- **G2**:用户用 YAML 文件声明式配置 Hook 规则,启动期一次性加载并校验,**配置错误立即报到 stderr 并跳过出错规则,不阻断进程**
- **G3**:每条 Hook 是"事件 + 条件 + 动作"三要素,条件可省略表示无条件触发
- **G4**:把 ch08 权限规则的匹配语法从单一通配扩展成"精确 exact / 反向 not / 正则 regex / glob"四种;Hook 条件表达式与扩展后的权限规则共用同一套匹配器
- **G5**:条件表达式支持嵌套字段访问,多条件用 `all_of` / `any_of` 二选一组合,**不允许嵌套混用**
- **G6**:在 PreToolUse 时刻,Hook 的 shell 动作通过 `exit code 2` 表达拦截、stderr 作为拒绝原因——被拒原因当 tool_result 回灌让模型调整;在 UserPromptSubmit 时刻同理拦截用户提交、原因回显到对话
- **G7**:四种动作类型——执行 shell 命令、注入提示词、发 HTTP 请求、启动子 Agent(**子 Agent 本期占位不实现,等后续章节对接**)
- **G8**:三种执行控制——only_once(同一会话内只跑一次)、async(异步后台执行不阻塞主流程)、timeout(命令最大执行时长);**拦截类事件(PreToolUse / UserPromptSubmit)不允许 async,加载期校验出错**
- **G9**:Hook 自身失败(命令非零退出、HTTP 超时、HTTP 解析错等)**只记日志、不中断 Agent 主流程**——除非该 hook 是同步拦截类且通过约定方式表达拦截信号

## 功能需求### 权限匹配语法扩展(前置基础)- **F1**:把权限规则 Pattern 形态从单一字符串扩展成结构化匹配类型 `{type, value}`,type 取 `exact`、`not`、`regex`、`glob` 之一;缺省类型沿用现有 glob 语义,保证向后兼容
- **F2**:规则 YAML 串语法升级——除 `Bash(rm *)` 这种"工具(简洁串)"写法保留代表 glob 类型外,新增显式类型前缀:
  - `Bash(=value)` 精确(整串相等)
  - `Bash(!inner)` 反向(对 inner 取反,inner 自身仍按规则解析,支持 `!=value`、`!~regex`、`!glob`)
  - `Bash(~regex)` 正则
  - `Bash(value)` 不带前缀沿用 glob 语义
- **F3**:精确匹配做整串相等比较;glob 沿用现有 wildcard / matchPath 实现;正则在加载期编译并缓存,编译失败按 F4 处理;反向是"任意其它类型的取反包装",支持嵌套(如 `Bash(!=value)`)
- **F4**:扩展后权限引擎的 Allow/Deny 判定语义不变,但规则解析失败原本静默跳过,现在改为"stderr 打印失败规则与原因、其余规则正常加载"
- **F5**:现有 ch08 的所有权限测试、既有的 `.gcode/permissions.yaml` 用户配置(仅写 `Bash(git *)` 这种)必须继续工作,不破坏向后兼容

### Hook 配置文件- **F6**:YAML 配置文件位置按以下顺序扫描,找到就加载、找不到就跳过:
  - 项目级:`<projectRoot>/.gcode/hooks.yaml`
  - 用户级:`~/.gcode/hooks.yaml`
- **F7**:两层规则**叠加合并**——所有规则共同参与事件分派;不存在"覆盖同名"概念,hook 的 name 仅用于日志和 only_once 跟踪;两层中出现同名 hook 时,加载期 stderr 提示冲突并跳过后到者
- **F8**:YAML 顶层结构:`hooks:` 数组,每条 hook 为对象,字段如下:
  - `name`(必填):字符串,用于日志、only_once 跟踪、冲突检测
  - `event`(必填):事件名,11 选 1(见 F9)
  - `if`(可选):条件表达式对象,省略表示无条件
  - `action`(必填):动作对象,含 `type` 与各类型独有字段
  - `only_once`(可选 bool,默认 false):会话内只跑一次
  - `async`(可选 bool,默认 false):是否后台异步执行
  - `timeout`(可选时长字符串如 `30s`,默认 30s):命令 / HTTP 最大执行时长

### 生命周期事件- **F9**:11 个事件名及触发时机:
  - **SessionStart**:gcode 启动初次进入会话或 `/clear` 新建会话后、env context 装配完毕、首条 user 消息进入对话历史**之前**
  - **SessionEnd**:进程关闭前、`/clear` 关闭旧会话前、`/resume` 切换离开旧会话前
  - **SessionResume**:`/resume` 选中历史会话、恢复完成、首条 user 消息进入**之前**
  - **UserPromptSubmit**:TUI 提交一条非 Slash 命令的 user 消息、写入对话历史**之前**——可拦截
  - **Stop**:Agent.run 自然停止后、`Done: true` 事件 emit 之前;取消、出错路径不触发
  - **PreUserMessage**:每轮 streamOnce 调 `provider.stream` 之前;payload 含当前 conversation 末尾的 user 消息
  - **PreToolUse**:executeBatched 对每条 tool call 准备执行**之前**、权限引擎 check 之**前**——可拦截
  - **PostToolUse**:单条 tool call 拿到 result 之后、emit PhaseEnd 之前;权限被 Deny 的也触发,payload.is_error=true
  - **PreCompact**:`CompactManager.manageContext` 调用之前(自动/紧急/手动三路径合并)
  - **PostCompact**:`CompactManager.manageContext` 返回后
  - **Notification**:权限 Ask 弹出审批时、Stream 返回 Failed 事件时
- **F10**:每个事件对应一份固定的 payload schema,作为 Hook 条件表达式与动作输入的数据源
  ```
  # 通用字段(每个事件都有)
  event: <事件名>
  session_id: <当前会话 ID>
  cwd: <项目工作目录>
  mode: <PermissionMode 名,default / plan>

  # 事件特化字段
  PreToolUse / PostToolUse:
    tool_name: <内部工具名,如 read_file>
    tool_input: <工具参数 JSON 对象>
    tool_result: <仅 PostToolUse,工具结果摘要文本>
    is_error: <仅 PostToolUse,bool>
  UserPromptSubmit / PreUserMessage:
    prompt: <用户输入文本>
  Notification:
    kind: approval | stream_error
    detail: <approval 含工具名;stream_error 含错误摘要>
  PreCompact / PostCompact:
    trigger: auto | emergency | manual
    before_tokens: <int,仅 PostCompact>
    after_tokens: <int,仅 PostCompact>
  SessionStart / SessionEnd / SessionResume:
    (仅通用字段)
  Stop:
    iter: <本轮 run 走完的迭代数>
  ```

### 条件表达式- **F11**:条件表达式 `if:` 是一个对象,顶层只能出现 `all_of` 或 `any_of` 中**一个**——两个同时出现按加载错误处理;缺省 `if:` 视为无条件触发
- **F12**:`all_of` / `any_of` 的值是一个原子条件数组,每个原子条件包含 `field` 与 `match` 两个字段
  ```yaml
  if:
    all_of:
      - field: tool_name
        match: { type: exact, value: write_file }
      - field: tool_input.path
        match: { type: glob, value: "**/*.java" }
  ```
- **F13**:`field` 取 payload 中的字段路径,用 `.` 分隔嵌套(如 `tool_input.command`、`tool_input.path`);路径不存在按空字符串处理,不报错
- **F14**:`match` 取四种类型之一——
  - `{type: exact, value: "..."}`
  - `{type: glob, value: "..."}`
  - `{type: regex, value: "..."}`
  - `{type: not, inner: {type: ..., value/inner: ...}}`

  正则编译失败、`not` 缺少 `inner`、`inner` 自身非法均视为加载错误,跳过该 hook
- **F15**:条件求值在事件 emit 时实时进行,匹配器实例在加载期一次构造、运行期复用

### 动作类型- **F16**:`action.type` 取 `shell` / `prompt` / `http` / `subagent` 之一,各自的字段:

#### shell 动作- **F17**:`shell` 动作字段:`command`(字符串,由 `sh -c` 解释执行);执行时把事件 payload 序列化成单行 JSON 通过 stdin 传给命令——脚本侧可用 `jq` 取字段
- **F18**:`timeout` 默认 30 秒,超时按命令失败处理(记日志);async 时由后台 virtual thread 异步执行,超时同样按失败处理
- **F19**:拦截事件(PreToolUse / UserPromptSubmit)下的 shell 同步执行:
  - `exit code == 2` 视为拦截命中,`stderr || stdout` 合并去尾换行后作为拒绝原因
  - `exit code == 0` 视为放行
  - 其它非零 exit code 视为 hook 失败但**不拦截**(记日志、Agent 继续)

#### prompt 动作- **F20**:`prompt` 动作字段:`text`(字符串);执行时把 `text` 加入"下一次 LLM 请求的 reminder 区"队列——所有 hook 注入的 prompt 按 hook 在 yaml 中的声明顺序拼接,置于现有 plan reminder 之后
- **F21**:reminder 队列仅本轮有效,下一轮重新装配;不入持久对话历史、不影响压缩
- **F22**:prompt 动作永不表达拦截——即使位于拦截类事件,动作执行后视为放行,仅做副作用注入

#### http 动作- **F23**:`http` 动作字段:`url`(必填)、`method`(默认 POST)、`headers`(可选键值对)、`body`(可选字符串模板,支持 `${field}` 占位符渲染 payload 字段);缺省 `body` 时把事件 payload 序列化成 JSON 作为请求体
- **F24**:`timeout` 同 F18 默认 30 秒;async 时由后台 virtual thread 异步执行
- **F25**:拦截事件下的 http 同步执行:
  - 响应 status 2xx 且 body 解析成 `{"decision":"block","reason":"..."}` 时视为拦截命中,reason 作为拒绝原因
  - 其它情况(非 2xx、body 缺 `decision` 字段、`decision` 非 `block`)视为放行
  - 网络错误、超时、JSON 解析失败按 hook 失败但**不拦截**#### subagent 动作- **F26**:`subagent` 动作字段:`agent_name`(必填)、`prompt`(必填字符串模板);**本期占位实现**——加载时校验字段完整、执行时仅记一行 stderr 日志 `[hook subagent] not yet implemented, skipped: <name>`、不报错也不拦截;后续章节对接子 Agent 后再补完整逻辑

### 执行控制- **F27**:`only_once: true` 标记的 hook 在同一会话内首次匹配成功并执行后被记录到 SessionRuntime 的内存集合(key = hook.name),后续相同事件再次匹配时直接跳过;`/clear`、`/resume` 进新会话时集合清空;**进程退出不写盘**——本期不做跨进程持久化
- **F28**:`async: true` 标记的 hook 在新 virtual thread 中执行;加载期校验:若 hook.event ∈ {PreToolUse, UserPromptSubmit} 且 async=true,加载层报错并跳过该 hook(拦截类不允许异步——异步无法表达拦截信号)
- **F29**:所有 hook 失败(命令非 0 exit 但非拦截信号、HTTP 错误、超时等)写一行 stderr `[hook <name>] <event> failed: <reason>`;不写日志文件、不弹 UI 通知;async 失败同上、不重试

### 集成点- **F30**:Hook 系统由独立模块承载,内部至少包含规则加载器、引擎(事件分派 + 集合状态)、四类动作执行器、匹配器;Agent 在构造期通过构造器/Builder 注入 Hook 引擎
- **F31**:Agent.run 等关键路径在 11 个事件时刻调用引擎的事件分派接口,接口返回拦截判定与待注入 prompt 集合
- **F32**:拦截结果整合:
  - **PreToolUse 拦截**:把 reason 拼成 `[hook <name>] <reason>` 形式当 tool_result 回灌,跳过权限引擎与真实工具执行;PhaseStart/PhaseEnd 事件按当前实现继续 emit,PhaseEnd 的 isError=true
  - **UserPromptSubmit 拦截**:阻止该 user 消息写入对话历史,TUI 在输入框下方显示 `[hook <name>] <reason>`,焦点返回输入框等用户重新编辑
- **F33**:InjectedPrompts 集合在下一次 streamOnce 时拼到 reminder 串末尾,置于现有 plan reminder 之后;本轮无可拦截语义的事件(SessionStart 等)触发的 prompt 注入也走 reminder 队列

### Slash 命令- **F34**:新增内置 Slash 命令 `/hooks`,KindLocal,零参数:输出当前已加载的所有 hook 的精简列表,按 `event` 分组、每条一行 `  <name>  <event>  <action.type>  <flags>`,flags 含 `[once]` / `[async]` 标志;末尾追加 `Loaded from: <加载来源文件列表>`
- **F35**:无任何 hook 时输出 `No hooks loaded.`

## 非功能需求- **N1**:Hook 加载在进程启动期一次性完成;YAML 解析错误、字段缺失、event 未知、name 冲突、async + 拦截事件冲突、regex 编译失败等所有加载错误**一律 stderr 输出后继续启动**,不阻断 gcode 进程
- **N2**:事件分派接口必须支持取消信号——拦截事件下同步等待、async 后台执行中线程中断都应及时退出,避免卡死 Agent.run
- **N3**:拦截事件下的同步 hook 串行执行,以单条 hook 的 timeout 累加;命令自身超时按 F18 处理,不再设全局上限
- **N4**:注入的 reminder 文本不入序列化对话历史、不参与 token 估算的"历史增长部分"(与 plan reminder 同语义)
- **N5**:only_once 内存集合放在 SessionRuntime 上,与 ActiveSkills 同生命周期;`/clear` 与 `/resume` 切换时清空
- **N6**:Hook payload JSON 序列化必须稳定字段顺序——key 按字母序,方便用户脚本对 JSON 直接 `grep`
- **N7**:扩展后的匹配器对权限规则与 Hook 条件共用同一实现,单元测试覆盖四种 type × 边界条件(空串、转义、嵌套 not、空 path)
- **N8**:subagent 占位日志输出固定格式 `[hook subagent] not yet implemented, skipped: <name>`,方便后续章节对接时文本搜索替换
- **N9**:hooks.yaml 文件不存在不报错;文件存在但整体 YAML 解析失败、顶层结构非法时打 stderr 但保持 gcode 启动
- **N10**:HTTP 动作的请求体模板渲染失败按 hook 失败处理;模板默认只支持 `${field}` / `${nested.path}` 最基本字段访问,不开放函数调用

## 不做的事

- 不实现 subagent 动作的真实执行(仅占位日志),等后续章节对接 SubAgent 系统
- 不做 only_once 标记的跨进程持久化(重启进程后集合清空,hook 会重新触发一次)
- 不引入 hook 执行的显式优先级 / order 字段——加载层按 yaml 声明顺序自然有序
- 不做 hook 文件的热更新——加载在启动期一次完成,编辑文件后需重启 gcode 才生效
- 不在 TUI 渲染 hook 触发的可视化轨迹(仅 stderr 日志)
- 不实现 hook 之间的依赖 / 互斥关系
- 不为 hook 提供独立日志文件、专属环境变量配置入口
- 不做 hook 失败的重试机制
- 不支持 hook 配置文件的 @include 或继承

## 验收标准- **AC1**:写一份只含 `Bash(=git status)` 的精确规则到 `.gcode/permissions.yaml`,启动后调用 `git status` 被该规则命中、调用 `git status -s` 不命中
- **AC2**:写一份 `Bash(~^npm (install|test)$)` 的正则规则,启动后调用 `npm install` 命中、`npm run dev` 不命中;写法非法(如未闭合括号、正则编译失败)启动期 stderr 打印 `rule "Bash(~..." parse failed: ...` 并跳过该条规则
- **AC3**:写一份 `Bash(!~^rm)` 的反向正则规则,调用 `rm -rf .` 不命中(以 rm 起头)、调用 `ls -lh` 命中(不以 rm 起头)
- **AC4**:在 `<projectRoot>/.gcode/hooks.yaml` 写一条 PreToolUse hook——条件 `tool_name = write_file`,动作 `shell: "echo blocked >&2; exit 2"`;启动后 LLM 调用 write_file 工具时被拦截,tool_result 显示 `[hook <name>] blocked`,文件未被写入
- **AC5**:上面 AC4 的 hook 把动作命令改成 `exit 0`,再调用 write_file,hook 触发但放行,文件成功写入
- **AC6**:写一条 SessionStart hook——动作 `prompt: "用 zh-CN 回复"`;重启 gcode 后首轮对话中 LLM reminder 区能看到该文本(通过调试通道观察),后续轮不再注入
- **AC7**:写一条 PostToolUse hook——条件工具名为 write_file 且 `is_error=false`,动作 `shell: "mvn -q spotless:apply -DspotlessFiles=\"$(jq -r .tool_input.path)\""`、async=true、timeout=5s;LLM 写一个 Java 文件后 spotless 异步在后台执行,主对话流不暂停;命令失败时 stderr 打印失败日志、Agent 不中断
- **AC8**:写一条 async + PreToolUse 的 hook,启动 gcode 时 stderr 打印 `hook "<name>": async not allowed for blocking events, skipped` 并跳过该条
- **AC9**:写一条 only_once + PreUserMessage 的 hook,动作 `shell: "echo first-turn >&2"`;第一轮 PreUserMessage 时 stderr 出现 `first-turn`,后续轮不再出现;执行 `/clear` 进入新会话后下一轮再次出现 `first-turn`
- **AC10**:写一条 UserPromptSubmit hook——条件 prompt 正则匹配 `(?i)delete`,动作 `shell: "echo \"prompt contains delete keyword\" >&2; exit 2"`;用户在 TUI 输入"请帮我 delete 那个文件"时被拦截,输入框下方提示 `[hook <name>] prompt contains delete keyword`,消息未进入对话历史
- **AC11**:在 hooks.yaml 中写 `event: UnknownEvent`,启动后 stderr 打印 `hook "<name>": unknown event "UnknownEvent", skipped`,其余 hook 正常加载
- **AC12**:同时在用户级与项目级 hooks.yaml 各写一条 hook,启动后 `/hooks` 命令输出两条合并列表,末尾显示两个加载来源文件路径
- **AC13**:写一条 Stop hook——动作 `http: POST http://localhost:9999/done`;本地起一个 echo server,Agent.run 自然停止后该 server 收到一次 POST 请求且 body 含 `"event":"Stop"`
- **AC14**:写一条 PreToolUse hook——动作 `http: POST http://localhost:9999/check`;本地 server 对 Bash 工具返回 `{"decision":"block","reason":"network policy"}`,Bash 调用被拦截、其它工具不受影响
- **AC15**:写一条 SessionStart hook——动作 `subagent: agent_name=foo, prompt=test`;启动后 stderr 出现 `[hook subagent] not yet implemented, skipped: <name>`,Agent 主流程不受影响
- **AC16**:在 hook 的 `if` 中同时写 `all_of` 与 `any_of` 两个键,启动 stderr 报错跳过该条,其余 hook 加载正常
- **AC17**:tmux 内启动 gcode,按 AC4 → AC6 → AC7 → AC10 顺序触发,整个过程不卡顿、无 panic(端到端见 checklist)
````

````markdown
# Hook 生命周期挂钩系统 Plan## 架构概览

本章拆为两个层次实现：

1. **权限匹配器升级层（permission 包内改造）**——把 Pattern 形态从字符串升级到结构化 Matcher 接口；新增 exact/regex/not 三种实现，glob 保留作为缺省类型。改造对外仅暴露语法升级和 stderr 错误回退,运行时 Allow/Deny 语义不变。

2. **Hook 主体层（新建 `dev.gcode.hook` 包）**——加载 YAML 规则、提供事件分派引擎、四类动作执行器；通过 11 个事件 emit 点接入 agent / tui。

模块构成：

- `permission.Matcher`(新)：匹配接口 + 四种实现的工厂（sealed interface + records）
- `hook.HookLoader`(新)：YAML 解析 / 字段校验 / matcher 编译 / 双层文件合并
- `hook.HookEngine`(新)：事件分派、only_once 集合、动作执行器协调
- `hook.HookExecutor`(新)：四类动作的执行入口（shell / prompt / http / subagent stub）
- `hook.ConditionEvaluator`(薄包装)：复用 `permission.Matcher`，做字段路径取值与匹配组合
- `agent`/`tui` 改动：在生命周期 11 个时刻调 `HookEngine.dispatch`
- `command`：新增 `/hooks` 内置命令

## 核心数据结构### permission.Matcher

```java
// Matcher 是规则匹配的统一接口；四种实现都是 record，sealed permits 限制扩展。
package dev.gcode.permission;

public sealed interface Matcher permits ExactMatcher, GlobMatcher, RegexMatcher, NotMatcher {
    boolean match(String s);
    String describe(); // 调试 / /hooks 输出用
}

public record ExactMatcher(String value) implements Matcher {
    public boolean match(String s) { return s.equals(value); }
    public String describe() { return "=" + value; }
}

public record GlobMatcher(String pattern, boolean command) implements Matcher {
    public boolean match(String s) {
        return command ? GlobMatch.matchCommand(pattern, s) : GlobMatch.matchPath(pattern, s);
    }
    public String describe() { return pattern; }
}

public record RegexMatcher(java.util.regex.Pattern compiled, String source) implements Matcher {
    public boolean match(String s) { return compiled.matcher(s).find(); }
    public String describe() { return "~" + source; }
}

public record NotMatcher(Matcher inner) implements Matcher {
    public boolean match(String s) { return !inner.match(s); }
    public String describe() { return "!" + inner.describe(); }
}

// 工厂：解析单条匹配描述串，返回 Matcher 或抛出 MatcherCompileException。
// 描述串规则：
//   "=value"  -> ExactMatcher
//   "~regex"  -> RegexMatcher
//   "!inner"  -> NotMatcher(compile(inner))
//   "value"   -> GlobMatcher（缺省，沿用现有 GlobMatch.matchPath/matchCommand 语义）
// Bash 工具沿用整串通配（matchCommand），其它沿用 matchPath。
// 调用方在 RuleSet 那侧通过 friendly 名分流到对应底层匹配函数；matcher 这边只关心模式串。
public final class Matchers {
    public static Matcher compile(String pattern, boolean command) throws MatcherCompileException { ... }
}
```

### permission.PermissionRule(改造)

```java
public record PermissionRule(
        String tool,    // 不变
        Matcher matcher, // 替换原 String pattern；null 表示「该工具全匹配」
        boolean allow,
        String raw      // 原始模式串，仅供错误日志与调试
) {}
```

`PermissionRule.parse(String)` 升级：识别前缀，调用 `Matchers.compile` 构造 matcher。失败时抛 `RuleParseException`；调用方（`SettingsLoader.toRuleSet`）捕获后写 stderr 并跳过。

### hook.HookRule

```java
package dev.gcode.hook;

import java.time.Duration;

public record HookRule(
        String name,
        Event event,           // 11 选 1 枚举
        Condition condition,   // null 表示无条件
        Action action,
        boolean onlyOnce,
        boolean async,
        Duration timeout,      // null 用默认 30s
        String source          // 来源文件路径，供 /hooks 显示
) {}

public enum Event {
    SESSION_START, SESSION_END, SESSION_RESUME,
    USER_PROMPT_SUBMIT, STOP, PRE_USER_MESSAGE,
    PRE_TOOL_USE, POST_TOOL_USE,
    PRE_COMPACT, POST_COMPACT,
    NOTIFICATION;

    public boolean isBlocking() { return this == PRE_TOOL_USE || this == USER_PROMPT_SUBMIT; }
    public static java.util.Optional<Event> parse(String s) { ... } // 大小写不敏感、连接符宽松
    public String wireName() { ... } // 序列化成 "SessionStart" / "PreToolUse" 等驼峰
}
```

### hook.Condition

```java
public record Condition(CombineMode mode, java.util.List<AtomCondition> atoms) {}

public enum CombineMode { ALL_OF, ANY_OF } // 二选一不混用

public record AtomCondition(
        String field,             // 形如 "tool_input.path"
        dev.gcode.permission.Matcher matcher // 复用四种匹配类型
) {}
```

### hook.Action

```java
public sealed interface Action permits Action.Shell, Action.Prompt, Action.Http, Action.Subagent {
    record Shell(String command) implements Action {}
    record Prompt(String text) implements Action {}
    record Http(
            String url,
            String method,                    // 默认 POST
            java.util.Map<String, String> headers,
            String bodyTemplate               // null 时序列化 payload 为 JSON
    ) implements Action {}
    record Subagent(String agentName, String prompt) implements Action {}
}
```

### hook.Payload

```java
// Payload 是事件分派时携带的上下文数据；条件求值与动作输入都用它。
// 用 LinkedHashMap 装载，JSON 序列化时按 key 字典序排序（N6）。
public final class Payload {
    private final java.util.Map<String, Object> data;
    public Payload(java.util.Map<String, Object> data) { this.data = data; }
    public String getByPath(String path) { ... } // "tool_input.command" 拆分递归取值
    public String toSortedJson() { ... }         // 字典序键的 JSON 字符串
}
```

通用字段约定：`event`、`session_id`、`cwd`、`mode`，加上各事件特化字段。`getByPath("tool_input.command")` 支持嵌套字段访问。

### hook.HookEngine

```java
public final class HookEngine {
    private final java.util.List<HookRule> rules;          // 按加载顺序
    private final java.util.List<String> sources;          // 加载来源文件，供 /hooks 显示

    private final java.util.concurrent.locks.ReentrantLock lock = new java.util.concurrent.locks.ReentrantLock();
    private final java.util.HashSet<String> onceFired = new java.util.HashSet<>();

    private final HookExecutor executor;

    public HookEngine(java.util.List<HookRule> rules, java.util.List<String> sources, HookExecutor executor) { ... }

    public DispatchResult dispatch(java.util.concurrent.CancellationException ctxCanceller, Event event, Payload payload) { ... }
    public void resetForNewSession() { ... }
    public java.util.List<String> sources() { ... }
    public java.util.List<HookRule> rules() { ... }
}

public record DispatchResult(
        boolean blocked,
        String reason,
        String blockingHookName,
        java.util.List<String> injectedPrompts // prompt 动作产生的文本，按声明序
) {
    public static DispatchResult empty() { ... }
}
```

`dispatch` 内部流程：
1. 过滤匹配 event 的 rule
2. 跳过 onceFired 中已触发的 only_once rule
3. 串行求值 condition
4. 命中条件后按 action 类型分发到 `HookExecutor`
5. async rule 起 virtual thread、立即往下走
6. 同步 rule 等结果，拦截类事件下若 result 表达 block，累加到 DispatchResult，跳过后续同事件 rule
7. prompt 类 rule 把 text 累加到 injectedPrompts

### HookExecutor

```java
public final class HookExecutor {
    private final java.net.http.HttpClient httpClient; // 默认 timeout=30s，可被 rule 的 timeout 覆盖

    public HookExecutor() { ... }

    public ExecutionResult run(HookRule rule, Payload payload, boolean blocking, java.time.Duration deadline) { ... }
}

public record ExecutionResult(
        boolean blocked,
        String reason,
        String prompt,           // 仅 prompt 动作非空
        Throwable error          // hook 自身失败（不拦截）
) {
    public static ExecutionResult empty() { ... }
}
```

`run` 内按 `rule.action()` 模式匹配（`switch`）调对应的 private `runShell` / `runPrompt` / `runHttp` / `runSubagent`。

## 模块设计### 模块 A：permission.Matcher**职责：** 提供四种匹配类型的统一接口；`Matchers.compile` 解析前缀。
**对外接口：** `Matcher` sealed interface、`Matchers.compile(String pattern, boolean command)`。
**依赖：** Java 标准库 `java.util.regex`。
**改动文件：** `src/main/java/dev/gcode/permission/PermissionRule.java`(扩展 parse / match)、新增 `src/main/java/dev/gcode/permission/Matcher.java` 及四个 record 实现、新增 `Matchers.java` 工厂。

### 模块 B：permission 错误日志**职责：** `PermissionRule.parse` 失败时 stderr 打印失败规则与原因，原本静默跳过改为有声跳过。
**对外接口：** `SettingsLoader.toRuleSet` 内部行为变化，外部 API 不变。
**依赖：** 模块 A。

### 模块 C：hook.HookLoader**职责：** 扫描两层 YAML 文件、解析顶层 `hooks:` 数组、字段校验、Matcher 编译、合并去重。
**对外接口：** `HookEngine load(Path projectRoot)`——返回引擎；所有错误走 stderr 不抛出。
**依赖：** 模块 A、`org.snakeyaml:snakeyaml-engine`、`hook.HookEngine`。
**校验项：** name 必填 + 跨文件冲突、event 枚举、condition 顶层 all_of/any_of 互斥、action 类型枚举与子字段、async + 拦截事件冲突、Matcher 编译失败。

### 模块 D：hook.HookEngine**职责：** dispatch 流程编排、only_once 集合管理、resetForNewSession。
**对外接口：** 见上一节 HookEngine 结构。
**依赖：** 模块 E。

### 模块 E：hook.HookExecutor**职责：** 四类动作的执行——shell（`ProcessBuilder` + stdin JSON + exit code 2 拦截）、prompt（直接返回 InjectedPrompt）、http（`java.net.http.HttpClient` POST JSON + decision=block 解析）、subagent（stub 占位日志）。
**对外接口：** `run(rule, payload, blocking, deadline) ExecutionResult`。
**依赖：** Java 标准库 `java.lang.ProcessBuilder`、`java.net.http.HttpClient`、`com.fasterxml.jackson` 或手写 JSON（与项目其它处一致）；模板渲染用简易 `${field}` 替换。

### 模块 F：hook.ConditionEvaluator**职责：** 把 `permission.Matcher` 应用到 payload 的字段路径上。
**对外接口：** `boolean evaluate(Condition cond, Payload payload)`、`String getByPath(Payload payload, String path)`。
**依赖：** 模块 A。

### 模块 G：agent 接入**职责：** 在 `Agent.run` 等关键路径调 `HookEngine.dispatch`；处理 PreToolUse 拦截、注入 reminder。
**对外接口：** `Agent.Builder.hookEngine(HookEngine)`；agent 私有方法 `dispatchHook(Event event, Payload payload) DispatchResult`。
**依赖：** 模块 D。
**改动文件：** `src/main/java/dev/gcode/agent/Agent.java`、`src/main/java/dev/gcode/agent/SessionRuntime.java`(加 `List<String> pendingReminders`、resetForNewSession 清空)。

### 模块 H：tui 接入**职责：** SessionStart / SessionEnd / SessionResume / UserPromptSubmit / Notification 五个事件在 TUI 侧 emit；UserPromptSubmit 拦截集成到 `TuiApp.submit()` 流程。
**对外接口：** `TuiApp` 上私有方法 `dispatchSessionStart` / `dispatchSessionEnd` 等。
**依赖：** 模块 D。
**改动文件：** `src/main/java/dev/gcode/tui/TuiApp.java`、`src/main/java/dev/gcode/tui/StreamPump.java`、`src/main/java/dev/gcode/tui/Commands.java`(/clear、/resume 触发 SessionEnd + SessionStart/Resume)。

### 模块 I：/hooks 命令**职责：** 输出已加载 hook 列表 + 加载来源文件。
**对外接口：** 注册到 `command.BuiltinCommands.register`。
**依赖：** `TuiApp` 暴露 `hookSources()` / `hookRules()` 查询方法（通过 `CommandUi` 接口）。

### 模块 J：Main wiring**职责：** 在 `Main.java` 中调 `HookLoader.load(projectRoot)`，把 HookEngine 注入 agent 与 `TuiApp`。
**改动文件：** `src/main/java/dev/gcode/Main.java`、`src/main/java/dev/gcode/tui/TuiApp.Params`(Builder 加 hookEngine 字段)。

## 模块交互**启动期数据流：**

```
Main.main()
  ├─ PermissionEngine.create(root)          # 用升级后的 PermissionRule.parse（stderr 报错）
  ├─ HookEngine engine = HookLoader.load(root)  # 扫描两层 YAML、构造 HookEngine
  └─ new TuiApp.Builder()
          .hookEngine(engine)
          .agent(Agent.builder()...hookEngine(engine).build())
          .build()
```

**SessionStart emit 时机：**

```
Main 完成 wiring → new TuiApp(params) → app.run() → init() 渲染 banner
                                                       │
                                                       └─ 首条 user 输入到达前
                                                          init() 末尾调 dispatchSessionStart()
```

实际接入：`TuiApp.init()` 末尾调 `dispatchSessionStart()`，该方法同步调 `HookEngine.dispatch`、收集 `injectedPrompts` 注入到 `runtime.pendingReminders`、然后返回。

**UserPromptSubmit 路径：**

```java
void submit() {
    String text = textBox.getText().strip();
    if (isSlash(text)) { dispatchSlash(text); return; }
    DispatchResult result = hookEngine.dispatch(null, Event.USER_PROMPT_SUBMIT,
            basePayload(Event.USER_PROMPT_SUBMIT, Map.of("prompt", text)));
    if (result.blocked()) {
        // 输入框下方显示 [hook <name>] reason，不消费输入
        view.appendError("[hook " + result.blockingHookName() + "] " + result.reason());
        return;
    }
    runtime.appendReminders(result.injectedPrompts());
    conversation.addUser(text);
    beginTurn();
}
```

**PreToolUse 拦截路径：**

```java
void executeBatched(List<ToolCall> calls, PermissionMode mode, BlockingQueue<AgentEvent> events) {
    for (ToolCall call : calls) {
        DispatchResult result = hookEngine.dispatch(null, Event.PRE_TOOL_USE,
                basePayload(Event.PRE_TOOL_USE, Map.of("tool_name", call.name(), "tool_input", call.input())));
        if (result.blocked()) {
            emit(events, new PhaseStart(call.id()));  // 用户仍能看到工具被尝试
            results.put(call.id(), hookBlockedResult(call.id(), result.blockingHookName(), result.reason()));
            emit(events, new PhaseEnd(call.id(), /*isError=*/true));
            continue;
        }
        runtime.appendReminders(result.injectedPrompts());
        // ... 原有的权限 check + 执行流程
        runtime.appendReminders(postToolUseDispatch.injectedPrompts());
    }
}
```

**Reminder 注入路径：**

```
Agent.run() 第 iter 轮 streamOnce 之前：
    String reminder = planReminder
                    + String.join("\n\n", runtime.takeReminders());  // 取出并清空 runtime.pendingReminders
    streamOnce(..., reminder, ...);
```

## 文件组织

```
gcode/
├── pom.xml
├── src/main/java/dev/gcode/
│   ├── permission/
│   │   ├── Matcher.java               # 新增：sealed interface
│   │   ├── ExactMatcher.java          # 新增：record
│   │   ├── GlobMatcher.java           # 新增：record
│   │   ├── RegexMatcher.java          # 新增：record
│   │   ├── NotMatcher.java            # 新增：record
│   │   ├── Matchers.java              # 新增：compile 工厂 + 异常
│   │   ├── PermissionRule.java        # 改造：parse 识别前缀、record 持有 Matcher
│   │   ├── SettingsLoader.java        # 改造：toRuleSet 报 stderr
│   │   └── ...
│   ├── hook/                          # 全新包
│   │   ├── package-info.java          # 包注释
│   │   ├── Event.java                 # 11 个枚举值 + isBlocking + parse
│   │   ├── HookRule.java              # record
│   │   ├── Condition.java             # record
│   │   ├── AtomCondition.java         # record
│   │   ├── CombineMode.java           # enum
│   │   ├── Action.java                # sealed interface + 4 个 record
│   │   ├── Payload.java               # 字典序 JSON + getByPath
│   │   ├── ConditionEvaluator.java    # evaluate + getByPath
│   │   ├── HookLoader.java            # YAML 解析、字段校验、双层合并
│   │   ├── HookEngine.java            # dispatch 主流程 + only_once 集合
│   │   ├── HookExecutor.java          # 四类 action 执行器
│   │   └── DispatchResult.java        # record
│   ├── agent/
│   │   ├── Agent.java                 # 增 dispatchHook 与 PreToolUse/PostToolUse/Stop/PreCompact 等 emit
│   │   ├── Agent$Builder.java         # Builder.hookEngine(...)
│   │   ├── SessionRuntime.java        # 加 pendingReminders、hookEngine 字段
│   │   └── ...
│   ├── command/
│   │   ├── BuiltinCommands.java       # 加 /hooks 命令注册
│   │   └── CommandUi.java             # 接口加 hookSources/hookRules
│   ├── tui/
│   │   ├── TuiApp.java                # Params 加 hookEngine、持有；init 触发 SessionStart
│   │   ├── StreamPump.java            # 不直接动，由 TuiApp 触发
│   │   ├── Commands.java              # /clear / /resume 触发 SessionEnd + SessionStart/Resume
│   │   └── HooksCommand.java          # 新增：/hooks handler、Model 的 hook 查询方法
│   └── Main.java                      # 加 HookLoader.load(root) 与 wiring
└── src/test/java/dev/gcode/
    ├── permission/
    │   ├── MatchersTest.java
    │   └── PermissionRuleTest.java
    └── hook/
        ├── HookLoaderTest.java
        ├── HookEngineTest.java
        └── HookExecutorTest.java
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 匹配前缀语法 | `=` 精确、`!` 反向、`~` 正则、无前缀=glob | 单字符前缀让既有 `Bash(git *)` 这种写法继续 work；用户写新形式时直观（=foo 一眼就是精确） |
| 反向类型嵌套 | `!=value`、`!~regex`、`!glob` 都合法 | 反向是一元运算，对内层 matcher 取反；嵌套写法直接，不需要 `not()` 函数语法 |
| Matcher 用 sealed interface + record | 而非 enum + switch | record 自动实现 equals/hashCode/toString；sealed 让 switch 模式匹配能穷尽四种类型；新增类型时编译器强制处理 |
| Hook 包独立 | `dev.gcode.hook` | 与 `dev.gcode.permission` 平级；hook 依赖 permission.Matcher，但 permission 不依赖 hook，无循环 |
| Event 用 enum + wireName | 而非 String 常量 | enum 享受类型安全与穷尽 switch；YAML 写的字符串通过 `Event.parse` 转换；JSON 序列化用 `wireName()` 输出 "PreToolUse" 这种 |
| Payload 内部 Map\<String, Object\> | 而非具体 record | 11 个事件字段差异大；Map + getByPath 灵活；JSON 序列化时按 key 字典序排序便于脚本 grep |
| Reminder 注入用 SessionRuntime 而非 HookEngine 状态 | `runtime.pendingReminders` | 与现有 plan reminder 同一注入点；下一轮自动清空；不污染 HookEngine |
| PreToolUse 拦截位置 | 权限 check 之前 | 让用户能用 hook 早于权限引擎做安全策略；hook 拦截后甚至不调权限 check |
| shell 用 `sh -c` | 而非 `ProcessBuilder` 直接 args 数组 | 用户写 hook 时常用 `\|`、`>` 这种 shell 语法；与 ch08 bash 工具一致；用 `ProcessBuilder("sh", "-c", command).redirectErrorStream(false)` 包装 |
| HTTP 默认 POST + JSON body | 而非 GET | hook 多是「事件通知」语义，POST 更合理；用户需要 GET 时显式声明 method |
| HTTP body 用 `${field}` 占位符 | 不开放函数 | 简易模板已经够覆盖字段插值；开放函数容易出注入风险；用正则替换或 `StringSubstitutor` 实现 |
| subagent 占位仅打日志 | 不报错也不阻塞 | spec 明确本期不实现，但配置应能加载——避免用户写早期配置后续章节直接生效 |
| only_once 用内存 HashSet | 不写盘 | spec N5 明确本期不持久化；HashSet 在 runtime 里，与 ActiveSkills 同生命周期 |
| 事件分派同步串行 | 多 hook 不并发 | 拦截语义需要顺序；同步 stderr 日志顺序也确定；async hook 单独起 virtual thread 但 dispatch 不等 |
| 拦截类 sync timeout 不全局上限 | 单条 hook timeout 累加 | 用户配的 timeout 自己负责；全局上限会引入复杂语义 |
| `/hooks` 命令风格 | 与 `/skill` 对齐 | 已加载条目按事件分组、每条一行；末尾标加载来源 |
| 加载来源记录 | `HookEngine.sources : List<String>` | YAML 文件路径列表，`/hooks` 命令展示 |
| async hook 用 virtual thread | 而非平台线程池 | Java 21 virtual thread 启停开销低、适合"起一发就忘"语义；与项目其它地方一致 |
| HttpClient 选 `java.net.http.HttpClient` | 而非 OkHttp 等三方 | JDK 内置、零额外依赖；天然支持 `Duration` timeout 与 sendAsync |
| JSON 序列化 | 与项目其它处共用同一 ObjectMapper（Jackson）或简易手写 | 保持依赖一致；key 字典序通过 `SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS` 或 TreeMap 实现 |
````

````markdown
# Hook 生命周期挂钩系统 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/main/java/dev/gcode/permission/Matcher.java` | sealed Matcher 接口 |
| 新建 | `src/main/java/dev/gcode/permission/ExactMatcher.java` | record 实现 |
| 新建 | `src/main/java/dev/gcode/permission/GlobMatcher.java` | record 实现 |
| 新建 | `src/main/java/dev/gcode/permission/RegexMatcher.java` | record 实现 |
| 新建 | `src/main/java/dev/gcode/permission/NotMatcher.java` | record 实现 |
| 新建 | `src/main/java/dev/gcode/permission/Matchers.java` | `compile` 工厂 + `MatcherCompileException` |
| 新建 | `src/test/java/dev/gcode/permission/MatchersTest.java` | 四种 type × 边界条件覆盖 |
| 修改 | `src/main/java/dev/gcode/permission/PermissionRule.java` | `parse` 识别前缀、record 持有 Matcher 替代 String pattern、`match` 改造 |
| 修改 | `src/test/java/dev/gcode/permission/PermissionRuleTest.java` | 扩展用例覆盖新语法 |
| 修改 | `src/main/java/dev/gcode/permission/SettingsLoader.java` | `toRuleSet` 改造：失败 rule 走 stderr |
| 修改 | `src/test/java/dev/gcode/permission/SettingsLoaderTest.java` | 验证 stderr 报错与跳过逻辑 |
| 新建 | `src/main/java/dev/gcode/hook/package-info.java` | 包注释 |
| 新建 | `src/main/java/dev/gcode/hook/Event.java` | 11 个枚举 + `isBlocking` + `parse` |
| 新建 | `src/main/java/dev/gcode/hook/CombineMode.java` | enum |
| 新建 | `src/main/java/dev/gcode/hook/AtomCondition.java` | record |
| 新建 | `src/main/java/dev/gcode/hook/Condition.java` | record |
| 新建 | `src/main/java/dev/gcode/hook/Action.java` | sealed Action + 4 个嵌套 record |
| 新建 | `src/main/java/dev/gcode/hook/HookRule.java` | record |
| 新建 | `src/main/java/dev/gcode/hook/Payload.java` | 字典序 JSON + `getByPath` |
| 新建 | `src/main/java/dev/gcode/hook/ConditionEvaluator.java` | `evaluate` / `getByPath` |
| 新建 | `src/main/java/dev/gcode/hook/HookLoader.java` | YAML 解析、双层合并、字段校验 |
| 新建 | `src/test/java/dev/gcode/hook/HookLoaderTest.java` | 字段校验、加载错误、合并测试 |
| 新建 | `src/main/java/dev/gcode/hook/HookEngine.java` | HookEngine + dispatch 主流程 + only_once |
| 新建 | `src/main/java/dev/gcode/hook/DispatchResult.java` | record |
| 新建 | `src/test/java/dev/gcode/hook/HookEngineTest.java` | 各事件 dispatch、拦截、reminder、once 覆盖 |
| 新建 | `src/main/java/dev/gcode/hook/HookExecutor.java` | 四类 action 执行器 |
| 新建 | `src/main/java/dev/gcode/hook/ExecutionResult.java` | record |
| 新建 | `src/test/java/dev/gcode/hook/HookExecutorTest.java` | shell exit2、http block、prompt、subagent stub |
| 修改 | `src/main/java/dev/gcode/agent/SessionRuntime.java` | 加 `pendingReminders` + `hookEngine` 字段 + `resetForNewSession` 清空 |
| 修改 | `src/test/java/dev/gcode/agent/SessionRuntimeTest.java` | 验证 `pendingReminders` 行为 |
| 修改 | `src/main/java/dev/gcode/agent/Agent.java` | `Builder.hookEngine`、11 个 emit 点（部分由 tui 触发，agent 负责 PreUserMessage/PreToolUse/PostToolUse/PreCompact/PostCompact/Stop/Notification） |
| 修改 | `src/test/java/dev/gcode/agent/AgentTest.java` | 拦截路径测试 |
| 新建 | `src/main/java/dev/gcode/tui/HooksCommand.java` | `/hooks` 命令 handler、TuiApp 的 hook 查询方法 |
| 修改 | `src/main/java/dev/gcode/tui/TuiApp.java` | `Params/Builder` 加 hookEngine、持有；`init` 触发 SessionStart |
| 修改 | `src/main/java/dev/gcode/tui/StreamPump.java` | `submit()` 内 UserPromptSubmit dispatch + 拦截集成 |
| 修改 | `src/main/java/dev/gcode/tui/Commands.java` | `/clear`、`/resume` 触发 SessionEnd + SessionStart/Resume |
| 修改 | `src/main/java/dev/gcode/command/BuiltinCommands.java` | 加 `/hooks` 内置命令 |
| 修改 | `src/main/java/dev/gcode/command/CommandUi.java` | UI 接口加 hook 查询方法 |
| 修改 | `src/main/java/dev/gcode/Main.java` | 加 `HookLoader.load(root)` 与 wiring；SessionEnd 兜底 |
| 修改 | `pom.xml` | 如尚未引入 snakeyaml-engine 与 jackson-databind，需补齐（多半已有） |

## T1: 实现 permission.Matcher 接口与四种类型**文件：** `src/main/java/dev/gcode/permission/Matcher.java`、`ExactMatcher.java`、`GlobMatcher.java`、`RegexMatcher.java`、`NotMatcher.java`、`Matchers.java`
**依赖：** 无
**步骤：**
1. 新建 `Matcher.java`，声明 `public sealed interface Matcher permits ExactMatcher, GlobMatcher, RegexMatcher, NotMatcher { boolean match(String s); String describe(); }`
2. 实现 4 个 record：
   - `ExactMatcher(String value)`：`match` 返回 `s.equals(value)`
   - `GlobMatcher(String pattern, boolean command)`：`command` 为 true 调 `GlobMatch.matchCommand`，否则 `GlobMatch.matchPath`；`describe` 返回 `pattern`
   - `RegexMatcher(Pattern compiled, String source)`：`match` 返回 `compiled.matcher(s).find()`
   - `NotMatcher(Matcher inner)`：`match` 返回 `!inner.match(s)`
3. 实现工厂 `Matchers.compile(String pattern, boolean command)`：
   - 空串 → 抛 `MatcherCompileException("empty matcher pattern")`
   - `=value` → `new ExactMatcher(value)`
   - `~regex` → `Pattern.compile(regex)`，`PatternSyntaxException` 包装抛出
   - `!inner` → 递归 `compile(inner, command)` 包装成 `NotMatcher`
   - 其它 → `new GlobMatcher(pattern, command)`
4. `GlobMatch` 工具类如已存在则直接复用；不存在则把现有 wildcard / matchPath 逻辑迁入 `GlobMatch`
5. 写 Javadoc 解释每个 Matcher 类型的语义

**验证：** `mvn -q -DskipTests compile` 编译通过

## T2: matcher 单元测试**文件：** `src/test/java/dev/gcode/permission/MatchersTest.java`
**依赖：** T1
**步骤：**
1. JUnit 5；`@ParameterizedTest` + `@MethodSource` 覆盖 4 种类型各自的命中/不命中用例
2. `=git status` 命中 `git status`、不命中 `git status -s`
3. `~^npm (install|test)$` 命中 `npm install`、不命中 `npm run dev`
4. `!=foo` 不命中 `foo`、命中 `bar`
5. `!~^rm` 命中 `ls -lh`、不命中 `rm -rf .`
6. `!git *` 命中 `npm install`、不命中 `git status`（嵌套 not + glob）
7. 编译失败：`~[invalid` 应抛 `MatcherCompileException`
8. 空串：`""` 应抛异常
9. 每个用例附 `assertAll` 描述

**验证：** `mvn test -Dtest=MatchersTest` 通过

## T3: 升级 permission.PermissionRule 与 parse**文件：** `src/main/java/dev/gcode/permission/PermissionRule.java`
**依赖：** T1
**步骤：**
1. `PermissionRule` 改为 record：`record PermissionRule(String tool, Matcher matcher, boolean allow, String raw)`
2. 静态 `parse(String s)` 签名改：抛 `RuleParseException`——返回受检异常让 `SettingsLoader.toRuleSet` 写日志
3. parse 内部：剥出 tool 与 pattern 后调 `Matchers.compile(pattern, "Bash".equals(tool))`；空 pattern 仍按 null matcher 表示"全匹配"
4. 改造 `matches(String target)` 实例方法：`matcher == null` 返回 true（全匹配），否则 `matcher.match(target)`
5. `RuleSet` 内部对 `PermissionRule` 集合的处理保持原行为，仅调用点改为 `matches`
6. 旧的 `escapeGlob` 等辅助方法保留不变（供 ch08 自动生成的精确规则使用）
7. Javadoc 更新说明四种语法

**验证：** `mvn -q -DskipTests compile` 编译通过

## T4: 升级 SettingsLoader 错误日志**文件：** `src/main/java/dev/gcode/permission/SettingsLoader.java`
**依赖：** T3
**步骤：**
1. `toRuleSet` 改造：`PermissionRule.parse` 抛 `RuleParseException` 时调
   `System.err.printf("rule %s parse failed: %s%n", quoted(str), ex.getMessage());`
2. 失败的 rule 不进入 RuleSet，其它 rule 不受影响——加注释说明
3. 复用项目里已有的日志辅助；若无则直接 `System.err`

**验证：** `mvn -q -DskipTests compile` 编译通过

## T5: 扩展 PermissionRuleTest 与 SettingsLoaderTest**文件：** `src/test/java/dev/gcode/permission/PermissionRuleTest.java`、`SettingsLoaderTest.java`
**依赖：** T3、T4
**步骤：**
1. PermissionRuleTest：补充用例
   - `Bash(=git status)` 精确匹配
   - `Bash(~^npm.*)` 正则匹配
   - `Bash(!~^rm)` 反向正则
   - `Write(**/*.java)` glob 沿用（确认向后兼容）
2. SettingsLoaderTest：构造一份含非法 rule 的 yaml 临时文件，验证 `toRuleSet` 返回的 RuleSet 不含该 rule（用 `System.setErr(new PrintStream(buf))` 捕获 stderr 验证含 `parse failed`，再断言 allow/deny 列表长度）
3. 旧的 `GlobMatchTest`（如存在）保持调用底层函数测试，或改造成调用 Matcher 形式

**验证：** `mvn test -Dtest=PermissionRuleTest,SettingsLoaderTest` 全部通过

## T6: hook 包基础数据结构**文件：** `src/main/java/dev/gcode/hook/package-info.java`、`Event.java`、`CombineMode.java`、`AtomCondition.java`、`Condition.java`、`Action.java`、`HookRule.java`、`Payload.java`
**依赖：** 无
**步骤：**
1. `package-info.java`：包级 Javadoc，描述本包职责
2. `Event.java`：
   - `public enum Event { SESSION_START, SESSION_END, SESSION_RESUME, USER_PROMPT_SUBMIT, STOP, PRE_USER_MESSAGE, PRE_TOOL_USE, POST_TOOL_USE, PRE_COMPACT, POST_COMPACT, NOTIFICATION; }`
   - `boolean isBlocking()` 返回 `this == PRE_TOOL_USE || this == USER_PROMPT_SUBMIT`
   - 静态 `Optional<Event> parse(String s)` 用字符串到枚举的映射表（含 "SessionStart" 等驼峰写法）
   - 实例 `String wireName()` 返回驼峰名（"SessionStart" 等），供 JSON 序列化与 stderr 日志
3. `CombineMode.java`：`enum CombineMode { ALL_OF, ANY_OF }`
4. `AtomCondition.java`：`record AtomCondition(String field, Matcher matcher)`
5. `Condition.java`：`record Condition(CombineMode mode, List<AtomCondition> atoms)`
6. `Action.java`：`sealed interface Action permits Action.Shell, Action.Prompt, Action.Http, Action.Subagent` + 4 个嵌套 record
7. `HookRule.java`：`record HookRule(String name, Event event, Condition condition, Action action, boolean onlyOnce, boolean async, Duration timeout, String source)`
8. `Payload.java`：内部 `Map<String, Object> data`；构造器接受 `Map`；`String getByPath(String path)` 与 `String toSortedJson()`

**验证：** `mvn -q -DskipTests compile` 编译通过

## T7: hook.ConditionEvaluator 字段路径求值**文件：** `src/main/java/dev/gcode/hook/ConditionEvaluator.java`
**依赖：** T6、T1
**步骤：**
1. `static String getByPath(Payload p, String path)`：按 `.` 分隔；递归从 Map 取值；中途遇 null/非 Map 返回空串
2. 字段值非字符串时：boolean/数字转字符串（`String.valueOf`）；嵌套对象转 JSON（用项目内 ObjectMapper 或 Payload 自带的 sorted JSON 序列化器）
3. `static boolean evaluate(Condition c, Payload p)`：
   - `c == null` → true
   - 遍历 `c.atoms()`，每条用 `getByPath` + `atom.matcher().match(...)`
   - `ALL_OF` 要求全部 true、`ANY_OF` 要求至少一个 true

**验证：** `mvn -q -DskipTests compile` 编译通过

## T8: hook.HookLoader YAML 解析**文件：** `src/main/java/dev/gcode/hook/HookLoader.java`
**依赖：** T6、T7、T1
**步骤：**
1. 定义 YAML 中间结构：直接用 SnakeYAML Engine 解析成 `Map<String, Object>`，再手动绑定到 `HookRule`
2. `static HookEngine load(Path projectRoot)` 主入口：
   - 计算两个候选路径：`projectRoot.resolve(".gcode/hooks.yaml")`、`Path.of(System.getProperty("user.home"), ".gcode/hooks.yaml")`
   - 文件不存在跳过；存在但解析失败 stderr 输出后跳过
   - 对每个 hook 对象调 `compileRule(source, idx, rawMap)`，返回 `HookRule` 或抛 `HookCompileException`
   - 累积成功的 rule、stderr 输出失败的 rule
   - 跨文件 name 冲突时跳过后者，stderr 提示冲突
3. `compileRule` 内做字段校验：
   - `name` 非空字符串
   - `event` 枚举（`Event.parse`）
   - `action.type` ∈ {shell, prompt, http, subagent}，对应子字段必填（`shell.command`、`prompt.text`、`http.url`、`subagent.agent_name` + `subagent.prompt`）
   - `if` 顶层 `all_of` / `any_of` 互斥
   - 每个 atom 的 `match.type` ∈ {exact, glob, regex, not} 且 `value`/`inner` 字段完整
   - `async` + `event.isBlocking()` → 抛错跳过，stderr 含 `async not allowed for blocking events`
   - `timeout` 字符串解析为 `Duration`：支持 `30s`、`500ms`、`2m` 等；缺省 30s
4. Matcher 编译用 `Matchers.compile`；hook 上下文都是 payload 字段值，统一传 `command=false`（让 glob 走 `matchPath` 语义：段内 `*` 不跨 `/`）
   - **决策修正**：hook 的 matcher 在初始化时统一传 `command=false`；这对 `tool_input.command` 这种字段是有点限制——但用户可以改用 regex 表达 shell 字符串匹配，文档需说清
5. 返回的 `HookEngine` 由 `new HookEngine(rules, sources, new HookExecutor())` 构造（执行器实例延后到 T11 实现完整）

**验证：** `mvn -q -DskipTests compile` 编译通过

## T9: hook.HookLoader 测试**文件：** `src/test/java/dev/gcode/hook/HookLoaderTest.java`
**依赖：** T8
**步骤：**
1. 用 `@TempDir` 场景：写一份合法 hooks.yaml（含 2 条 hook），`HookLoader.load` 返回的 HookEngine 含 2 条 rule
2. 字段缺失：name 空、event 不存在、action.type 无效 → 跳过该条但其它通过
3. all_of + any_of 同时存在 → 跳过该条
4. async + PreToolUse → 跳过该条且 stderr 含 `async not allowed for blocking events`
5. 跨文件同名冲突 → 项目级保留、用户级跳过
6. matcher 编译失败（非法正则） → 跳过该条
7. 用 `tapSystemErr(...)`（System.Lambda 或手写 `setErr` 包装）验证 stderr 输出

**验证：** `mvn test -Dtest=HookLoaderTest` 通过

## T10: hook.HookEngine 与 dispatch 主流程**文件：** `src/main/java/dev/gcode/hook/HookEngine.java`、`DispatchResult.java`
**依赖：** T6、T7
**步骤：**
1. `DispatchResult` record：`(boolean blocked, String reason, String blockingHookName, List<String> injectedPrompts)`；静态 `empty()`
2. `HookEngine` 字段：`rules`、`sources`、`ReentrantLock`、`HashSet<String> onceFired`、`HookExecutor executor`
3. `HookEngine(List<HookRule> rules, List<String> sources, HookExecutor executor)` 构造器
4. `DispatchResult dispatch(Event event, Payload payload)`：
   - 遍历 rules，跳过非本事件
   - 加锁查 `onceFired`，命中跳过
   - `ConditionEvaluator.evaluate`；不通过跳过
   - 命中后：
     - `async=true` 起 virtual thread (`Thread.startVirtualThread(() -> executor.run(...))`)，立即继续（不等结果、不进入 injectedPrompts 与 blocked 判定）
     - 同步：调 `executor.run(rule, payload, event.isBlocking(), rule.timeout())`
   - 同步结果处理：
     - `result.error()` 非 null → stderr 日志 `[hook <name>] <event> failed: <reason>`，继续下一个 rule（不拦截）
     - `result.prompt()` 非空 → 加入 injectedPrompts
     - `result.blocked() && event.isBlocking()` → 设置 DispatchResult.blocked + reason + blockingHookName，break 退出循环
   - 命中且执行无 fatal err 的 rule，若 `onlyOnce` → 加入 `onceFired`
5. `resetForNewSession()`：加锁清空 `onceFired`
6. `sources() / rules()` getter

**验证：** `mvn -q -DskipTests compile` 编译通过

## T11: hook.HookExecutor 四类动作执行**文件：** `src/main/java/dev/gcode/hook/HookExecutor.java`、`ExecutionResult.java`
**依赖：** T6
**步骤：**
1. `ExecutionResult` record：`(boolean blocked, String reason, String prompt, Throwable error)`；静态 `empty()`
2. `HookExecutor` 字段：`HttpClient httpClient`（`HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build()`）
3. `ExecutionResult run(HookRule rule, Payload payload, boolean blocking, Duration deadline)` 用 `switch (rule.action())` 模式匹配分发到下面四个内部方法
4. `runShell(Action.Shell sa, Payload payload, boolean blocking, Duration timeout)`：
   - `ProcessBuilder pb = new ProcessBuilder("sh", "-c", sa.command())`
   - `pb.redirectErrorStream(false)`，从 stdin 写入 `payload.toSortedJson()` 单行
   - 启动后用 virtual thread 读 stdout / stderr；`process.waitFor(timeout)`；超时 → `process.destroyForcibly()`、返回 `error=TimeoutException`
   - `blocking && exitCode == 2` → `blocked=true、reason=合并 stderr/stdout 去尾`
   - `exitCode == 0` → 空 ExecutionResult
   - 其它非 0 exit → `error=new RuntimeException("exit " + code + ": " + stderr)`
5. `runPrompt(Action.Prompt pa)` → `new ExecutionResult(false, null, pa.text(), null)`
6. `runHttp(Action.Http ha, Payload payload, boolean blocking, Duration timeout)`：
   - method 默认 POST
   - body：缺省时 `payload.toSortedJson()`；否则用 `${field}` 占位符替换 `payload.getByPath(field)`
   - 构造 `HttpRequest`，加 headers，`.timeout(timeout)`
   - `httpClient.send(req, BodyHandlers.ofString())`
   - status 2xx 且 body 解析成 `{"decision":"block","reason":"..."}` → `blocked=true`
   - 网络错/超时/JSON 解析失败 → `error=ex`
7. `runSubagent(Action.Subagent sa)`：仅 `System.err.printf("[hook subagent] not yet implemented, skipped: %s%n", sa.agentName())`，返回 `ExecutionResult.empty()`
8. JSON 解析复用项目里已有的 ObjectMapper；模板替换写一个简单 `String renderTemplate(String tpl, Payload p)` 用正则 `\\$\\{([^}]+)\\}` 匹配并调 `getByPath`

**验证：** `mvn -q -DskipTests compile` 编译通过

## T12: executor 单元测试**文件：** `src/test/java/dev/gcode/hook/HookExecutorTest.java`
**依赖：** T11
**步骤：**
1. shell exit 2 with stderr → `blocked=true` + reason 含 stderr
2. shell exit 0 → 放行不报错
3. shell exit 1 → `error` 非 null 不拦截
4. shell stdin JSON 解析：脚本读 stdin 后 `echo` 出来（用 cat），验证 key 字典序
5. shell timeout：`sleep 2` + timeout 100ms → `error` 含 `TimeoutException` 或类似
6. prompt → `prompt` 字段非空
7. http with `com.sun.net.httpserver.HttpServer` 起本地 server，返回 `{"decision":"block","reason":"x"}` → `blocked=true`
8. http with 5xx → `error` 非 null
9. http 模板 body 含 `${event}` → server 收到正确字段
10. subagent → 用 `tapSystemErr` 验证 stderr 含占位文本

**验证：** `mvn test -Dtest=HookExecutorTest` 通过

## T13: hook.HookEngine 测试**文件：** `src/test/java/dev/gcode/hook/HookEngineTest.java`
**依赖：** T10、T11
**步骤：**
1. 多 rule 同事件按声明序执行
2. 拦截类事件下首个 `blocked=true` 的 rule 中断后续
3. 非拦截类事件下 `blocked` 字段不传递（fake exit code 2 但 `isBlocking=false` 也不 set `blocked`）
4. prompt rule 的 prompt 累加到 `injectedPrompts`
5. `onlyOnce` 在首次执行后被加入 `onceFired`，第二次 dispatch 跳过
6. `resetForNewSession` 后 `onlyOnce` 重置
7. async rule 不进入 `blocked` 判定（用 `CountDownLatch` 验证 virtual thread 已起）

**验证：** `mvn test -Dtest=HookEngineTest` 通过

## T14: agent SessionRuntime 扩展**文件：** `src/main/java/dev/gcode/agent/SessionRuntime.java`、`src/test/java/dev/gcode/agent/SessionRuntimeTest.java`
**依赖：** T6、T10
**步骤：**
1. `SessionRuntime` 加字段：`final List<String> pendingReminders`（用 `Collections.synchronizedList(new ArrayList<>())` 或加锁包装）、`HookEngine hookEngine`
2. 构造器初始化空 list
3. `resetForNewSession()` 清空 `pendingReminders`、若 `hookEngine != null` 调 `hookEngine.resetForNewSession()`
4. 新增 `appendReminders(List<String> prompts)` 加锁追加
5. 新增 `List<String> takeReminders()` 加锁取出并清空
6. 测试覆盖：`appendReminders` + `takeReminders` 单线程行为；`resetForNewSession` 清空

**验证：** `mvn test -Dtest=SessionRuntimeTest` 通过

## T15: agent.Builder.hookEngine 与 emit 框架**文件：** `src/main/java/dev/gcode/agent/Agent.java`、`Agent.Builder` 内嵌类
**依赖：** T14
**步骤：**
1. `Agent.Builder` 加方法 `Builder hookEngine(HookEngine e)`，赋值到 `Builder.hookEngine`
2. `Agent` 字段加 `HookEngine hookEngine`，构造时从 Builder 拷贝；同时把 hookEngine 写入 `SessionRuntime`
3. 私有方法 `DispatchResult dispatchHook(Event event, Payload payload)`：
   - `hookEngine == null` → 返回 `DispatchResult.empty()`
   - 调 `hookEngine.dispatch(event, payload)`
   - 把 `injectedPrompts` 调 `runtime.appendReminders`
   - 返回结果（保留 blocked + reason 供 PreToolUse 用）
4. 私有方法 `String buildReminder(PermissionMode mode, int iter)`：
   - 原 planReminder + `String.join("\n\n", runtime.takeReminders())`

**验证：** `mvn -q -DskipTests compile` 编译通过

## T16: agent 各事件 emit 接入**文件：** `src/main/java/dev/gcode/agent/Agent.java`
**依赖：** T15
**步骤：**
1. `run` 开始处准备 Stop emit 入口——实际 Stop 在 `Done` 事件 publish 前调用
2. 每轮 iter 顶部、`compactManager.manageContext` 之前调 `dispatchHook(Event.PRE_COMPACT, payload(Map.of("trigger", "auto")))`；`manageContext` 返回后 emit `POST_COMPACT` 带 before/after tokens
3. `emergencyCompactAndDecide`：同样 PRE_COMPACT/POST_COMPACT，`trigger="emergency"`
4. `streamOnce` 调 `provider.stream` 之前 emit `PRE_USER_MESSAGE`，payload 含 conversation 末尾 user 消息
5. 把 reminder 串改造：取 `buildReminder(mode, iter)` 替代原裸的 `Prompts.planReminder(full)`
6. `executeBatched` 改造：
   - 单工具循环开始处 emit `PRE_TOOL_USE`，payload 含 `tool_name`、`tool_input`；`blocked=true` 时构造 `hookBlockedResult`、publish `PhaseStart`/`PhaseEnd`（isError=true），continue
   - tool 拿到 result 后、publish `PhaseEnd` 之前 emit `POST_TOOL_USE`，payload 含 `tool_name`、`tool_input`、`tool_result`、`is_error`
7. publish `Done` 之前调 `STOP`，payload(`Map.of("iter", iter)`)
8. publish `Approval` 之前调 `NOTIFICATION`，payload(`Map.of("kind", "approval", "detail", toolName)`)
9. publish `Failed` 之前调 `NOTIFICATION`，payload(`Map.of("kind", "stream_error", "detail", err.toString())`)
10. 拦截结果整合：私有 `ToolResult hookBlockedResult(String callId, String hookName, String reason)`：content=`[hook <name>] <reason>`、isError=true

**验证：** `mvn -q -DskipTests compile` 编译通过

## T17: AgentTest 拦截路径与 emit 覆盖**文件：** `src/test/java/dev/gcode/agent/AgentTest.java`、`SessionRuntimeTest.java`
**依赖：** T16
**步骤：**
1. 构造一个 fake `Provider` + 注入真实 `HookEngine`（合成 rules 注入）
2. 测试：PreToolUse 拦截时工具结果是 `hookBlockedResult` 形式、`PhaseStart`/`PhaseEnd` 仍 publish
3. 测试：PreUserMessage 注入的 prompt 在下一次 `streamOnce` 的 reminder 串中可见
4. 测试：Stop 事件在 `Done` 前一刻被 emit
5. 由于 HookEngine 不是接口，直接 new 真实 HookEngine 注入合成 rules（更简单）；或写一个 `TestHookEngine extends HookEngine` 子类覆盖 dispatch

**验证：** `mvn test -Dtest=AgentTest -Dtest.method=*Hook*` 通过

## T18: tui TuiApp 持有 HookEngine**文件：** `src/main/java/dev/gcode/tui/TuiApp.java`
**依赖：** T15
**步骤：**
1. `TuiApp.Params` 加 `HookEngine hookEngine`
2. `TuiApp` 加字段 `HookEngine hookEngine`
3. 构造器内：
   - 把 `params.hookEngine` 赋给 `this.hookEngine` 与 `runtime.hookEngine`
   - 构造 agent 时加 `.hookEngine(params.hookEngine)`
4. `init()` 末尾调 `dispatchSessionStart()`

**验证：** `mvn -q -DskipTests compile` 编译通过

## T19: tui UserPromptSubmit 拦截集成**文件：** `src/main/java/dev/gcode/tui/StreamPump.java` 或 `TuiApp` 的 submit 方法所在文件
**依赖：** T18
**步骤：**
1. `submit()` 重写：
   - 现有的 trim 与 slash 分发保留
   - 非 slash 路径进入 hook 拦截判定
   - 构造 payload：`new Payload(Map.of("event", "UserPromptSubmit", "session_id", sessionId, "cwd", cwd, "mode", mode.name().toLowerCase(), "prompt", text))`
   - 调 `hookEngine.dispatch(Event.USER_PROMPT_SUBMIT, payload)`
   - `blocked=true`：在 scrollback 追加 `errorLabel(String.format("[hook %s] %s", result.blockingHookName(), result.reason()))`，不消费 textBox
   - 否则：把 `injectedPrompts` 经 `runtime.appendReminders`；`conversation.addUser(text)`；`beginTurn`
2. 提供辅助方法 `Payload basePayload(Event event, Map<String, Object> extras)` 构造通用字段
3. UI 更新统一通过 `textGUI.getGUIThread().invokeLater(...)` 切回 GUI 线程

**验证：** `mvn -q -DskipTests compile` 编译通过

## T20: tui SessionStart / End / Resume**文件：** `src/main/java/dev/gcode/tui/TuiApp.java`、`Commands.java`、`StreamPump.java`
**依赖：** T18、T19
**步骤：**
1. 新增 `void dispatchSessionStart()`：构造 payload + 调 `HookEngine.dispatch` + `injectedPrompts` 写入 runtime
2. 新增 `void dispatchSessionEnd()`：仅同步调 dispatch
3. 新增 `void dispatchSessionResume()`：同 SessionStart 流程，event 改为 `SESSION_RESUME`
4. `init()` 末尾调 `dispatchSessionStart`
5. `/clear` handler 内：先 `dispatchSessionEnd`，再 `runtime.resetForNewSession`，最后 `dispatchSessionStart`
6. `/resume` handler 选中会话恢复完毕后：先 `dispatchSessionEnd`（旧），切到新会话后 `dispatchSessionResume`
7. `handleExit` 内：`dispatchSessionEnd` 后再退出
8. `Main` 中 `app.run()` 返回后由 main 调一次 `hookEngine.dispatch(Event.SESSION_END, ...)` 兜底（ctrl+c 一退出也 emit）；tui 内的 `/clear`、`/resume` 自己控制

**验证：** `mvn -q -DskipTests compile` 编译通过

## T21: /hooks 命令**文件：** `src/main/java/dev/gcode/tui/HooksCommand.java`、`command/BuiltinCommands.java`、`command/CommandUi.java`
**依赖：** T6、T10、T18
**步骤：**
1. `CommandUi` 接口加方法 `List<String> hookSources()`、`List<HookRule> hookRules()`
2. `TuiApp` 实现这两个方法（读 `this.hookEngine` 字段）
3. 新增 `HooksCommand`，实现 `Command` 接口或注册成 lambda：
   - 取 rules 与 sources
   - 空时 `view.append("No hooks loaded.")`
   - 否则按 event 分组（保留 yaml 声明顺序）、每条一行 `  <name>  <event>  <action.type>  [once] [async]`
   - 末尾 `Loaded from: file1, file2`
4. `BuiltinCommands.register` 加 `/hooks` 命令，KindLocal，描述「列出已加载的 hook 列表」

**验证：** `mvn -q -DskipTests compile` 编译通过

## T22: Main wiring**文件：** `src/main/java/dev/gcode/Main.java`
**依赖：** T8、T18
**步骤：**
1. 在 `PermissionEngine.create(root)` 之后调 `HookEngine hookEngine = HookLoader.load(root)`
2. `TuiApp.Params` 设置 `.hookEngine(hookEngine)`
3. `app.run()` 返回后调
   ```java
   if (hookEngine != null) {
       hookEngine.dispatch(Event.SESSION_END, basePayload(...));
   }
   ```
   兜底 SessionEnd
4. import 加 `dev.gcode.hook.*`

**验证：** `mvn -q -DskipTests package` 编译通过、`java -jar target/gcode-*.jar` 能启动

## T23: 整体编译与测试**文件：** —
**依赖：** T1-T22 全部
**步骤：**
1. `mvn -q -DskipTests package` 通过
2. `mvn test` 通过——hooks 相关测试 + 既有测试都得过
3. `mvn spotless:check`（若启用）通过

**验证：** 上述命令本地通过

## T24: 修复回归**文件：** 根据测试输出决定
**依赖：** T23
**步骤：**
1. 修复 ch08 / ch11 等老测试因 Matcher 改造而失败的用例
2. 修复 ch10 / ch11 测试因 `/hooks` 命令加入而影响排序或数量的用例
3. 重新跑全套测试

**验证：** `mvn test` 通过

## T25: tmux 端到端实跑（验收 AC17 与 checklist 端到端场景）**文件：** `.gcode/hooks.yaml` 临时测试配置
**依赖：** T23、T24
**步骤：**
1. 写测试 hooks.yaml：包含 AC4-AC15 各典型场景的 hook
2. tmux 新建 session 启动 gcode（`java -jar target/gcode-*.jar` 或 `mvn -q exec:java`）
3. 依次触发：write_file 工具调用、含 delete 关键字的用户输入、git 命令、Stop 事件
4. 观察 stderr 日志、tool_result 内容、reminder 注入是否符合预期
5. 全程无异常堆栈、不卡顿

**验证：** 见 checklist.md

## 执行顺序

```
T1 → T2 → T3 → T4 → T5            # permission Matcher 扩展
T6 → T7 → T8 → T9                 # hook 基础结构 + Loader
T10 → T13                         # HookEngine
T11 → T12                         # HookExecutor（与 HookEngine 并行）
T14 → T15 → T16 → T17             # agent 接入
T18 → T19 → T20                   # tui 接入
T21                               # /hooks 命令
T22                               # Main wiring
T23 → T24                         # 整体编译测试
T25                               # tmux 实跑验收
```

并行机会：
- T11/T12 与 T10/T13 互不依赖,可并行
- T11 与 T8 在 T6 完成后可并行
- T17 必须在 T16 之后
- T19 之前 T18 必须先完成
````

````markdown
# Hook 生命周期挂钩系统 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### 权限匹配器扩展

- [ ] `permission.Matcher` sealed interface 存在,四种 record 实现(ExactMatcher / GlobMatcher / RegexMatcher / NotMatcher)各自可单独编译并运行(验证：`mvn test -Dtest=MatchersTest` 通过)
- [ ] `permission.PermissionRule` 已替换 pattern 为 matcher 字段,`parse` 能识别 `=` / `~` / `!` 前缀(验证：`mvn test -Dtest=PermissionRuleTest` 通过)
- [ ] `SettingsLoader.toRuleSet` 在 `PermissionRule.parse` 抛 `RuleParseException` 时输出 stderr 错误日志(验证：单测构造非法 rule 串,捕获 `System.err` 输出含 `parse failed`)

### Hook 包

- [ ] `dev.gcode.hook` 包存在且编译通过(验证：`mvn -q -DskipTests compile`)
- [ ] 11 个 `Event` 枚举值全部声明且 `isBlocking()` 仅对 PRE_TOOL_USE / USER_PROMPT_SUBMIT 返回 true(验证：`mvn test -Dtest=EventTest` 或单测覆盖)
- [ ] `HookLoader` 能解析合法 YAML 并构造 HookEngine(验证：`HookLoaderTest` 全部通过)
- [ ] `HookLoader` 对字段缺失 / 枚举错 / async+拦截事件冲突 / matcher 编译失败均报 stderr 并跳过该条(验证：对应 `HookLoaderTest` 子用例通过)
- [ ] `HookEngine.dispatch` 按声明顺序执行 rule 且拦截后中断后续(验证：`HookEngineTest.testDispatchBlocking` 通过)
- [ ] `HookExecutor` 的 shell exit 2 触发 `blocked=true`、exit 0 放行、其它非 0 视为失败不拦截(验证：`HookExecutorTest.testRunShell*` 通过)
- [ ] `HookExecutor` 的 HTTP 在 body 含 `{"decision":"block","reason":"..."}` 时触发 `blocked=true`(验证：`HookExecutorTest.testRunHttp*` 通过)
- [ ] `HookExecutor` 的 prompt 动作通过 `ExecutionResult.prompt` 字段返回文本(验证：`HookExecutorTest.testRunPrompt` 通过)
- [ ] `HookExecutor` 的 subagent 动作仅 stderr 输出占位日志、不阻塞(验证：`HookExecutorTest.testRunSubagent` 通过)
- [ ] `onlyOnce` 状态在 `SessionRuntime` 上,/clear 与 /resume 时被 `resetForNewSession` 清空(验证：`SessionRuntimeTest.testResetForNewSession` 通过)

### agent / tui 集成

- [ ] `Agent.Builder.hookEngine` 方法存在,agent 内部 `dispatchHook` 在 11 个 emit 点全部调用(验证：`AgentTest.testHookEmit*` 覆盖每个事件)
- [ ] tui `submit()` 在 UserPromptSubmit 拦截时不消费 textBox、显示 errorBlock(验证：`TuiAppTest.testSubmitBlocked` 通过)
- [ ] `TuiApp.init()` 末尾调 `dispatchSessionStart`(验证：`TuiAppTest.testInitDispatchSessionStart` 或集成测试)
- [ ] `/clear` / `/resume` / `/exit` 触发 SessionEnd(验证：`TuiAppTest.testClearDispatchSessionEnd` 等)
- [ ] `Main` 退出前兜底 SessionEnd(验证：`Main` 调用链审查)
- [ ] `/hooks` 命令注册到命令表(验证：`BuiltinCommandsTest` 中 `/hooks` 命令存在 + 输出格式正确)
- [ ] `pendingReminders` 在 `Agent.run` `takeReminders` 后被清空(验证：`SessionRuntimeTest.testTakeReminders` 通过)

## 集成

- [ ] `HookEngine` 与 `permission.Matcher` 共用同一套匹配实现(验证：hook 包不重复实现 exact/regex/glob)
- [ ] `HookEngine` 接入 `Agent.run` 后所有现有 agent 测试不破坏(验证：`mvn test -Dtest='dev.gcode.agent.*Test'` 全过)
- [ ] `HookEngine` 接入 tui 后所有现有 tui 测试不破坏(验证：`mvn test -Dtest='dev.gcode.tui.*Test'` 全过)
- [ ] PreToolUse 拦截结果当 tool_result 回灌后,LLM 视角看到的是 `isError=true` 的 ToolResult,content 含 `[hook <name>] <reason>`(验证：`AgentTest` 检查 results map 字段)
- [ ] reminder 注入路径与 plan reminder 协同——同一轮 LLM 请求的 reminder 串同时含两类(验证：`AgentTest` 中构造 plan 模式 + hook prompt 注入,断言 reminder 串包含两段)

## 编译与测试

- [ ] 项目编译无错误:`mvn -q -DskipTests package`
- [ ] 所有单元测试通过:`mvn test`
- [ ] 格式化检查通过:`mvn spotless:check`(无配置则跳过)

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证人工/可视化行为。

### 场景 1:PreToolUse shell 拦截 write_file**预置:** 在 `.gcode/hooks.yaml` 写一条 hook:
```yaml
hooks:
  - name: block-write
    event: PreToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
    action:
      type: shell
      command: "echo blocked by hook >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 gcode（`java -jar target/gcode-*.jar`）
- [ ] 给 LLM 输入"创建一个文件 hello.txt 内容是 hi"
- [ ] LLM 应触发 write_file,工具被拦截
- [ ] scrollback 内 tool_result 显示 `[hook block-write] blocked by hook`、文件未创建
- [ ] LLM 收到反馈后调整回应,不死循环

### 场景 2:SessionStart prompt 注入**预置:**
```yaml
hooks:
  - name: zh-cn-default
    event: SessionStart
    action:
      type: prompt
      text: "默认用 zh-CN 回复"
```

**步骤:**
- [ ] tmux 重启 gcode
- [ ] 立刻发一句英文输入"hi there"
- [ ] LLM 应该用中文回复(因为 reminder 区注入了 zh-CN 指令)

### 场景 3:PostToolUse async shell 后台格式化**预置:**
```yaml
hooks:
  - name: spotless-after-write
    event: PostToolUse
    if:
      all_of:
        - field: tool_name
          match: { type: exact, value: write_file }
        - field: tool_input.path
          match: { type: glob, value: "**/*.java" }
        - field: is_error
          match: { type: exact, value: "false" }
    action:
      type: shell
      command: "mvn -q spotless:apply -DspotlessFiles=\"$(jq -r .tool_input.path)\""
    async: true
    timeout: 30s
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 写一个故意排版不整齐的 Java 文件(如缩进错乱)
- [ ] LLM 完成写入后主对话立即进入下一轮,不停顿
- [ ] 验证文件被 spotless 格式化(可手动 `cat` 该文件)

### 场景 4:UserPromptSubmit 拦截 delete 关键字**预置:**
```yaml
hooks:
  - name: warn-delete
    event: UserPromptSubmit
    if:
      all_of:
        - field: prompt
          match: { type: regex, value: "(?i)delete" }
    action:
      type: shell
      command: "echo \"用户消息含 delete 关键字\" >&2; exit 2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入"请帮我 delete 那个文件"
- [ ] 输入被拦截,scrollback 内显示 `[hook warn-delete] 用户消息含 delete 关键字`
- [ ] 输入框内容仍在(被退回用户重新编辑)
- [ ] LLM 端未收到这条 user 消息(不发起请求)

### 场景 5:Stop HTTP 通知**预置:**
- 本地起 echo server:`python3 -m http.server 9999 --bind 127.0.0.1` 或 nc -l
```yaml
hooks:
  - name: notify-stop
    event: Stop
    action:
      type: http
      url: "http://127.0.0.1:9999/done"
      method: POST
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 简单回答一个问题后停止
- [ ] echo server 收到一次 POST,body 含 `"event":"Stop"`

### 场景 6:only_once + PreUserMessage**预置:**
```yaml
hooks:
  - name: first-turn
    event: PreUserMessage
    only_once: true
    action:
      type: shell
      command: "echo first-turn-fired >&2"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 第一轮发任意消息,stderr 出现 `first-turn-fired`
- [ ] 第二轮发消息,stderr 没有再次出现
- [ ] 执行 `/clear` 进新会话,再发消息,stderr 重新出现 `first-turn-fired`

### 场景 7:错误配置不阻断启动**预置:** hooks.yaml 含一条非法 hook:
```yaml
hooks:
  - name: bad-async
    event: PreToolUse
    async: true
    action:
      type: shell
      command: "echo x"
  - name: good-hook
    event: SessionStart
    action:
      type: shell
      command: "echo ok"
```

**步骤:**
- [ ] tmux 启动 gcode
- [ ] gcode 启动期 stderr 打印 `hook "bad-async": async not allowed for blocking events, skipped`
- [ ] gcode 仍然成功进入 idle 状态
- [ ] `/hooks` 命令仅列出 good-hook、未列 bad-async

### 场景 8:/hooks 命令**预置:** 一份包含 3 条合法 hook 的 hooks.yaml(任意 event 组合)

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入 `/hooks` 回车
- [ ] 输出按 event 分组,每条一行 `  <name>  <event>  <action.type>  [flags]`
- [ ] 末尾显示 `Loaded from: .../hooks.yaml`

### 场景 9:端到端组合(AC17)**预置:** hooks.yaml 包含场景 1、2、3、4 全部 hook

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 首轮:SessionStart 注入 zh-CN(场景 2),Agent 准备就绪
- [ ] 输入"帮我创建 hello.java,然后用 spotless 格式化一下"
- [ ] LLM 调 write_file 创建文件 → 被场景 1 的 hook 拦截 → LLM 重试(可能换 edit_file)或换 bash 调 spotless
- [ ] 整个过程不卡顿、无异常堆栈
- [ ] `/hooks` 命令仍可工作显示 4 条 hook
````

### TypeScript

```markdown
# Hook 生命周期挂钩系统 Spec## 背景

gcode 已经具备大模型流式回复、工具调用、权限校验、技能装载等能力，但用户在"想让某个动作在 Agent 跑到某个时刻自动发生"这条路径上仍然没有抽象：

- 写完文件想立刻跑一遍格式化命令，得手动去敲
- 想阻止模型对某条 `rm -rf` 命令的尝试，只能等权限弹窗里手动 ask
- 想在每轮开头给模型贴一条"用中文回复"的提示，没有现成入口
- 想在 Agent 长跑结束后给本地服务发一个通知，得自己另起进程

权限引擎只在工具调用前做 Allow / Deny / Ask 判定，做不了"在事件发生时跑一段命令、发一个请求、注入一段提示词"这种带副作用的扩展。Hook 系统补上的就是这一缝：把 Agent 生命周期的若干固定时刻抽象成事件，让用户通过配置声明"事件 + 条件 + 动作"三要素，把"触发条件明确、动作固定"的重复操作交给配置而不是手工。

## 目标- **G1**：把 Agent 的若干关键生命周期时刻抽象成事件枚举，事件触发即同步派发到 Hook 引擎；现有的对话流和工具流不被改写成事件总线，保持线性可读
- **G2**：用户通过 YAML 配置声明式描述 Hook 规则；启动期一次性加载、合并多层配置，并在首次挂载时统一校验
- **G3**：每条 Hook 由"事件 + 可选条件 + 动作"三要素构成；条件缺省视为无条件触发
- **G4**：条件用一种简洁的单行表达式描述，支持精确等于、不等、正则、glob 四种二元算子，以及取反前缀与"与/或"组合
- **G5**：动作分四类——执行 shell 命令、注入提示词到下一轮、发 HTTP 请求、唤起子 Agent；子 Agent 动作需要外部注入执行器才能真正运行
- **G6**：在"工具调用前"事件下，Hook 可表达拦截语义——拦截命中即停止后续 Hook，并把拒绝原因作为工具结果回灌给模型；其它事件下 Hook 仅做副作用
- **G7**：Hook 支持后台异步执行标记，异步执行不阻塞主流程；异步与拦截语义互斥，配置层校验冲突
- **G8**：Hook 支持"仅触发一次"标记，引擎实例内首次触发后被记录，后续相同事件再次匹配时直接跳过
- **G9**：Hook 的输出（命令标准输出、注入文本、HTTP 响应体）统一进入一个通知队列，在下一轮对话装配时被取出并以系统提醒形式注入到本轮上下文；命令异常的处理由"错误策略"字段决定
- **G10**：配置校验失败不阻塞启动——所有错误聚合后通过会话内的系统提示信息呈现给用户，其余合法配置继续生效

## 功能需求### 配置- **F1**：Hook 配置位于全局应用配置的 `hooks` 顶层数组下，由配置加载流程在以下三层来源中按顺序扫描：
  - 用户全局配置
  - 项目级配置
  - 项目本地覆盖配置

  Hook 数组采用**叠加合并**——后层的 hooks 直接追加到前层之后，不存在按 id 覆盖的语义
- **F2**：单条 Hook 配置含以下字段：
  - 标识符（可选）：用于日志与"仅触发一次"跟踪
  - 事件名（必填）：取自固定枚举
  - 条件表达式（可选）：单行字符串
  - 动作（必填）：含动作类型与该类型所需的字段（命令、URL、HTTP 方法、提示词等）
  - 拦截标记（可选）：仅在"工具调用前"事件下有意义
  - 仅触发一次标记（可选）
  - 异步标记（可选）
  - 错误策略（可选）：`ignore` / `fail` / `reject`，默认 `ignore`
- **F3**：YAML 解析、字段缺失、枚举非法等问题由统一的校验阶段聚合成提示信息呈现，不在加载阶段抛错中断启动

### 生命周期事件- **F4**：Hook 引擎对外暴露的事件枚举共 9 个：
  - **会话开始**：Agent 进入主循环之前
  - **会话结束**：Agent 主循环结束的收尾位置，确保异常路径也能触发
  - **轮次开始**：主循环每轮开头，已经把通知队列内容写入本轮系统提醒之后
  - **请求大模型之前**：同一轮中"轮次开始"之后、向大模型发请求之前
  - **接收大模型回复之后**：流式响应完整接收完毕之后
  - **轮次结束**：本轮工具结果写回对话、对话轮次完成事件已发出之后
  - **工具调用之前**：单条工具调用进入权限检查之前（批量工具按顺序触发）
  - **工具调用之后**：单条工具调用拿到结果、工具结果事件已发出之后
  - **进程退出**：保留枚举位，本期不在主流程上触发，为后续进程退出钩子预留
- **F5**：事件分派对外提供两个入口——一个专供"工具调用前"使用，返回是否拦截与拒绝原因；另一个供其它事件使用，返回每条 Hook 的执行结果列表
- **F6**：派发时携带的上下文字段包含：事件名、工具名（可选）、工具入参（可选）、文件路径（可选）、消息文本（可选）；"工具调用前"事件会从工具入参里自动提取文件路径

### 条件表达式- **F7**：条件为单行字符串，用"与"与"或"算子分割成多个原子条件，左结合，不支持括号优先级
- **F8**：原子条件支持五种形态：
  - 字段精确等于字面量
  - 字段精确不等于字面量
  - 字段正则匹配（正则编译失败视为不匹配）
  - 字段 glob 匹配（支持 `**` / `*` / `?` 通配）
  - 任一原子条件前加取反前缀
- **F9**：条件中能引用的字段取自调度上下文，包括："工具名"、"事件名"、"文件路径"、"消息文本"，以及任意工具入参字段（按名取值并转字符串）；未命中字段统一返回空字符串
- **F10**：条件解析与求值在每次事件派发时实时进行，单次成本可忽略

### 动作执行- **F11**：shell 命令动作同步执行所配置的命令；执行时向命令环境注入三个固定环境变量：当前事件名、当前工具名、当前文件路径；命令执行有固定超时上限；标准输出经去除尾部空白后作为本条 Hook 的输出
- **F12**：提示词动作的输出即所配置的提示词文本本身，不涉及外部进程
- **F13**：HTTP 动作发起一次 HTTP 请求；方法默认 POST；请求体强制为上下文对象的 JSON 序列化，内容类型固定为 JSON；响应体文本作为本条 Hook 的输出；HTTP 响应是否成功决定本条 Hook 的成功标志
- **F14**：子 Agent 动作需要外部注入一个执行器才能真正运行；未注入时本条 Hook 标记为执行失败，输出固定提示信息说明未注册执行器，但仍按拦截标记决定是否拦截
- **F15**：所有动作的执行结果统一包装为含"输出文本、成功标志、是否拦截"三要素的结构

### 拦截语义- **F16**：在"工具调用前"事件下，遇到拦截命中即立即中断该批后续 Hook 的执行；命中工具不进入权限检查、不进入实际工具执行，直接生成一条带错误标记的工具结果事件，其文本带有形如"被 Hook 拒绝：<原因>"的前缀
- **F17**：其它事件下即便结果中带有拦截标记，主流程也不消费它——只有"工具调用前"路径会读取拦截信号
- **F18**：异步执行的 Hook 视为放行，无法表达同步拦截；配置层把"拦截 + 异步"组合视为非法

### 执行控制与错误处理- **F19**：标记为"仅触发一次"的 Hook，以其标识符（缺省时退化为"事件名 + 动作类型"组合）作为去重键，首次触发后被加入引擎内存集合，后续相同事件再次匹配时直接跳过
- **F20**：仅触发一次的状态绑定到引擎实例生命周期；gcode 重启或重新挂载会话时清空；本期不做跨进程持久化
- **F21**：异步 Hook 在后台执行，执行完毕后把输出写入通知队列，异常时把错误信息以特定前缀写入通知队列
- **F22**：同步命令或 HTTP 动作抛错时由错误策略决定行为：
  - `ignore`（默认）：不进入结果列表，不影响主流程
  - `fail`：结果列表追加一条不成功、不拦截的记录，输出带错误信息
  - `reject`：结果列表追加一条不成功、拦截的记录，仅在"工具调用前"事件下产生拦截效果

### 通知队列- **F23**：Hook 引擎内部维护一个通知队列，提供"追加"与"取出全部"两种操作
- **F24**：同步路径下，每条 Hook 的非空输出会主动写入通知队列；工具调用后事件的输出同样进入该队列
- **F25**：主循环每轮顶部在已经写入技能提醒后取出通知队列内容，逐条以系统提醒形式注入本轮上下文；取出后队列清空
- **F26**：异步 Hook 的输出与错误信息也通过该队列回流到模型——异步完成时机不定，由下一次能够消费的轮次开始装载

### 校验- **F27**：校验阶段在会话首次挂载时执行一次，所有错误聚合后通过会话内的"系统提示"消息呈现给用户，前缀固定形如"Hook 配置警告：..."
- **F28**：校验覆盖项至少包括：
  - 事件名必填且取自合法枚举
  - 动作类型必填且取自合法枚举
  - shell 命令动作必须配置非空命令
  - 提示词动作必须配置非空提示词
  - HTTP 动作必须配置非空 URL
  - 子 Agent 动作必须配置非空提示词或命令
  - 拦截标记与异步标记互斥
- **F29**：单条 Hook 出错不阻塞其它 Hook——引擎构造时接收完整 Hook 数组，运行时逐条评估

## 非功能需求- **N1**：引擎实例化开销恒定；事件派发按声明顺序遍历，单事件 1~3 条 Hook 时整体调度延迟可忽略（命令自身耗时除外）
- **N2**：同步命令动作会阻塞主流程，使用者应自行评估是否需要标记为异步把耗时操作转后台
- **N3**：引擎实例在整个应用生命周期内共享，多轮对话共享"已触发一次"集合与通知队列；常规清空对话的会话操作不重置引擎
- **N4**：通知队列对超大输出不做截断，使用者应在 Hook 命令里自行截断或落盘
- **N5**：条件表达式不预编译；运行时正则非法时被静默视为不匹配，不向上抛错
- **N6**：环境变量注入只设置三个固定键（事件名、工具名、文件路径），不传完整工具入参，避免污染脚本可见环境
- **N7**：HTTP 动作的请求体当前固定为上下文的 JSON 序列化，不支持模板；用户需要自定义请求体时可改走 shell 命令配合外部 HTTP 工具

## 不做的事

- 不实现基于命令退出码的拦截协议——"工具调用前"事件的拦截仅走配置层的拦截标记字段，不解析退出码
- 不做配置文件的热更新——加载在启动期一次完成，编辑后需重启
- 不为 Hook 提供专属日志文件——所有输出走通知队列、错误走会话系统消息
- 不实现 Hook 之间的依赖、优先级、互斥；声明顺序即执行顺序
- 不做 Hook 执行的重试机制
- 不支持条件表达式的括号优先级与完整语法树解析
- 不引入额外内置命令查看 Hook 列表——校验失败时通过系统消息暴露
- 进程退出事件保留枚举位但本期不在主流程上触发；后续可在退出钩子上挂载

## 验收标准- **AC1**：配置一条"轮次开始 + 注入提示词「请用中文回答」"的 Hook，重启 gcode 后第一次发英文输入，下一轮请求里能看到对应的系统提醒，模型用中文回复
- **AC2**：配置一条"工具调用前 + 条件匹配写文件工具 + shell 命令打印 blocked 并返回失败 + 拦截标记打开"的 Hook；模型尝试调用写文件工具时拿到形如"被 Hook 拒绝：..."的工具结果，文件没有被写
- **AC3**：配置一条"工具调用之后 + 异步 + shell 命令写入临时日志文件"的 Hook；模型执行任意工具后，主对话立即进入下一轮不停顿，后台日志文件被异步写入
- **AC4**：配置一条"会话开始 + 仅触发一次 + 注入提示词"的 Hook；启动后第一次 Agent 运行被注入到下一轮系统提醒，同一进程内第二次 Agent 运行时不再注入
- **AC5**：在配置里写一条事件名非法的 Hook；gcode 启动并进入会话后，屏幕上出现一条系统消息"Hook 配置警告：第 N 条 Hook 事件名非法 ..."，其它合法 Hook 照常加载
- **AC6**：在配置里写一条"拦截标记 + 异步标记"同时存在的 Hook；启动后系统消息显示拦截与异步互斥的告警，引擎仍可工作
- **AC7**：配置一条"工具调用前 + 条件 glob 匹配 `**/*.txt` 文件路径 + shell 命令打印失败 + 拦截标记 + 错误策略 reject"的 Hook；模型写 `.txt` 文件时被拦截，写 `.md` 文件正常通过
- **AC8**：配置一条"接收大模型回复之后 + HTTP 动作 POST 到本地服务"的 Hook；本地起一个回显服务，每轮回复完成后该服务收到一次 POST，请求体为 JSON 含事件名与消息字段
- **AC9**：配置一条"轮次开始 + 条件引用未在该事件上下文中传递的字段"的 Hook；该 Hook 不命中——验证条件求值对未传字段返回空字符串、不抛错
- **AC10**：在 tmux 内启动 gcode，按 AC1 → AC2 → AC4 顺序触发，整个过程不卡顿、无 panic
```

````markdown
# Hook 生命周期挂钩系统 Plan## 技术栈

- 运行时：bun（包管理 + 启动 + 测试一体）
- 语言：TypeScript 5.x（`tsc --noEmit` 类型检查）
- TUI：Ink（React 渲染到终端）、ink-spinner、ink-text-input
- LLM SDK：@anthropic-ai/sdk、openai
- MCP：@modelcontextprotocol/sdk
- 配置解析：js-yaml
- 终端样式：chalk
- 模糊搜索：fuse.js
- 命令执行：Node.js 内建 `child_process.execSync`（同步） + 全局 `fetch`（HTTP）
- 测试：bun test

## 架构概览（分层）

Hook 系统横跨配置、引擎、Agent 接入三层：

1. **配置层（`src/config/config.ts`）**
   - `HookConfig` 接口约束单条 hook 的字段形态
   - `loadConfig` 在三个候选路径里读 YAML 并 `mergeConfig`，把 `hooks` 数组叠加合并
   - 不做语义校验，留给 `validate`

2. **引擎层（`src/hooks/hooks.ts`）**
   - `HookEngine` 类持有 `hooks: HookConfig[]`、`firedOnce: Set<string>`、`notifications: string[]`、可选 `agentRunner`
   - 公开方法：`fire(event, ctx)`、`firePreToolHooks(toolName, args)`、`recordNotification(msg)`、`drainNotifications()`
   - 私有方法：`executeAction(hook, ctx)` 按 action.type 派发四类执行器
   - 自由函数：`evaluateCondition` / `evaluateSingleCondition` / `getContextValue`、模块级 `validate(hooks)`

3. **Agent / TUI 接入层**
   - `App` 组件（`src/tui/app.tsx`）首次 mount 时调 `validateHooks(hooks)`，错误以 system 消息上屏，成功后用 `useRef` 持有 `HookEngine` 实例
   - 构造 `Agent` 时把 `hookEngine` 通过 `AgentConfig` 注入
   - `Agent.run`（`src/agent/agent.ts`）在 6 个生命周期点调 `fireLifecycle`、在 `executeBatch` 顶部调 `firePreToolHooks`、在 `processToolResult` 末尾调 `fire("post_tool_use")`
   - 主循环每轮顶部 `drainNotifications()` 把 hook 输出经 `addSystemReminder` 写回对话

## 数据流

```
YAML 配置文件 ──loadConfig──> AppConfig.hooks
                                  │
                                  v
                           App({hooks}) (props)
                                  │
                                  ├──> validateHooks  -> Error? -> system 消息上屏
                                  v
                          new HookEngine(hooks)  (useRef 持有)
                                  │
                                  v
                      AgentConfig.hookEngine = engineRef
                                  │
                                  v
              Agent.run 主循环：
                ├ session_start ──> fireLifecycle("session_start")
                ├ 每轮顶部：
                │   ├ drainNotifications() -> addSystemReminder
                │   ├ fireLifecycle("turn_start")
                │   └ fireLifecycle("pre_send")
                ├ client.stream(...)
                ├ fireLifecycle("post_receive", fullText)
                ├ 工具循环（executeBatch）：
                │   ├ firePreToolHooks(name, args) -> rejected? -> 生成 isError tool_result
                │   ├ 权限检查 / executor 运行
                │   └ processToolResult: fire("post_tool_use")  → notification
                ├ fireLifecycle("turn_end")
                └ finally: fireLifecycle("session_end")
```

## 核心数据结构与接口

```typescript
// src/hooks/hooks.ts
export type EventName =
  | "session_start"
  | "session_end"
  | "turn_start"
  | "turn_end"
  | "pre_send"
  | "post_receive"
  | "pre_tool_use"
  | "post_tool_use"
  | "shutdown";

export interface HookContext {
  event: EventName;
  toolName?: string;
  args?: Record<string, unknown>;
  filePath?: string;
  message?: string;
}

export interface HookResult {
  output: string;
  success: boolean;
  reject: boolean;
}

export class HookEngine {
  private hooks: HookConfig[];
  private firedOnce: Set<string>;
  private notifications: string[];
  agentRunner?: (prompt: string, ctx: HookContext) => Promise<string>;

  constructor(hooks: HookConfig[]);

  recordNotification(message: string): void;
  drainNotifications(): string[];

  fire(event: EventName, context: HookContext): Promise<HookResult[]>;
  firePreToolHooks(
    toolName: string,
    args: Record<string, unknown>
  ): Promise<{ rejected: boolean; reason: string }>;

  private executeAction(hook: HookConfig, ctx: HookContext): Promise<HookResult>;
}

export function validate(hooks: HookConfig[]): Error | null;
```

```typescript
// src/config/config.ts
export interface HookConfig {
  id?: string;
  event: string;
  condition?: string;
  action: {
    type: string;
    command?: string;
    url?: string;
    method?: string;
    prompt?: string;
  };
  reject?: boolean;
  once?: boolean;
  async?: boolean;
  on_error?: string;
}

export interface AppConfig {
  providers: ProviderConfig[];
  permission_mode?: string;
  mcp_servers: MCPServerConfig[];
  hooks: HookConfig[];
}
```

```typescript
// src/agent/agent.ts
export interface AgentConfig {
  client: LLMClient;
  registry: ToolRegistry;
  checker: PermissionChecker;
  conversation: ConversationManager;
  workDir: string;
  hookEngine?: HookEngine;
  // ... 其它字段
}

export class Agent {
  private hookEngine?: HookEngine;
  async *run(): AsyncGenerator<AgentEvent>;
  private async fireLifecycle(event: EventName, message?: string): Promise<void>;
  private async executeBatch(toolUses: ToolUseBlock[], parallel: boolean): Promise<AgentEvent[]>;
  private async processToolResult(...): Promise<void>;
}
```

## 模块设计### 模块 A：HookConfig（`src/config/config.ts`）**职责：** 定义 hook YAML 字段映射，由 `loadConfig` 解析 / `mergeConfig` 合并。

**对外接口：** `HookConfig` interface、`AppConfig.hooks: HookConfig[]`。

**依赖：** js-yaml。

**实现要点：** 三层 YAML 文件按顺序加载、hooks 字段叠加合并；不做语义校验。

### 模块 B：HookEngine（`src/hooks/hooks.ts`）**职责：** 持有 hook 列表、提供 `fire` / `firePreToolHooks` 派发入口、维护 once 集合与 notification 队列、协调四类动作执行。

**对外接口：** `HookEngine` 类、`HookContext` / `HookResult` 类型、`EventName` 类型、模块级 `validate` 函数。

**依赖：** Node.js `child_process.execSync`、全局 `fetch`、`HookConfig`。

### 模块 C：condition 求值（同文件）**职责：** `evaluateCondition` 把表达式按 `&&` / `||` 切分、`evaluateSingleCondition` 处理 `!` 取反与四种二元算子、`getContextValue` 实现字段路径取值。

**对外接口：** 模块内部使用，不导出。

**依赖：** JavaScript 内置 `RegExp`。

### 模块 D：动作执行器（同文件，私有方法）

- `command`：`execSync` 同步运行命令、注入三个环境变量、30s 固定 timeout
- `prompt`：直接把 `action.prompt` 当作 output
- `http`：`fetch` POST + JSON body=context
- `agent`：调用 `this.agentRunner(prompt, ctx)`，未注入时返回失败结果

### 模块 E：Agent 接入（`src/agent/agent.ts`）**职责：**
- `AgentConfig` 多一个 `hookEngine?: HookEngine` 字段
- `Agent` 类持有 `private hookEngine?: HookEngine`
- `private async fireLifecycle(event: EventName, message?: string)` 把单事件 fire 包成一句话，把输出存入 notification
- `run()` 在 session_start / turn_start / pre_send / post_receive / turn_end / session_end 各调一次 `fireLifecycle`，且 turn_start 之前调 `drainNotifications()` 把上轮 hook 输出注入 `addSystemReminder`
- `executeBatch` 顶部调 `firePreToolHooks`，rejected 时构造 `isError=true` 的 tool_result
- `processToolResult` 末尾调 `fire("post_tool_use", ctx)`，把 output 写入 notification

**对外接口：** 仅扩展构造器签名。

**依赖：** 模块 B。

### 模块 F：TUI 接入（`src/tui/app.tsx`）**职责：**
- `App` 接收 `hooks: HookConfig[]` props
- mount 时 `validate(hooks)` 一次，错误以 system 消息显示
- `useRef<HookEngine>` 持有引擎，整个 App 生命周期共享
- 在 `runAgentLoop` 里把 `hookEngineRef.current ?? undefined` 注入 `Agent` 构造

**对外接口：** App 组件 props 扩展。

**依赖：** 模块 B、Ink。

### 模块 G：入口装配（`src/main.tsx`）**职责：** 从 `loadConfig()` 拿到 `cfg.hooks`，作为 prop 传给 `<App>`。

**对外接口：** 无新增。

**依赖：** 模块 A、模块 F。

## 模块交互（调用链/时序）**启动期：**

```
main.tsx
  loadConfig()                  # 读 ~/.gcode/config.yaml & .gcode/config.yaml & .gcode/config.local.yaml
    └ mergeConfig 把 hooks 数组 append 合并
  render(<App hooks={cfg.hooks} ... />)
        │
        v
  App useEffect (首次 mount)
    validateHooks(hooks)        # 聚合错误返回 Error | null
       ├ Error 非 null → setMessages(prev => [..., {role: "system", content: `Hook warning: ${err.message}`}])
       └ null         → 无提示
    hookEngineRef.current = new HookEngine(hooks)
```

**单轮 Agent 主循环：**

```
runAgentLoop()
  new Agent({ hookEngine: hookEngineRef.current, ... })
  for await ev of agent.run():
     ├ session_start         ──> fireLifecycle("session_start")
     │
     ├ 主循环 iteration++：
     │   ├ manageContext(...)
     │   ├ skillReminder 注入
     │   ├ HookEngine.drainNotifications() → for note: addSystemReminder(note)
     │   ├ fireLifecycle("turn_start")
     │   ├ fireLifecycle("pre_send")
     │   ├ client.stream(apiConv, toolSchemas)
     │   ├ fireLifecycle("post_receive", fullText)
     │   ├ tool calls? → executeBatch(toolUses, parallel)
     │   │     for tu of toolUses:
     │   │        ├ firePreToolHooks(tu.toolName, tu.arguments)
     │   │        │     ├ rejected → push isError tool_result, continue
     │   │        │     └ ok      → 权限检查 → executor.submit
     │   │        └ processToolResult(r, ...)
     │   │              ├ tool_result event
     │   │              └ fire("post_tool_use", ctx) → notification 入队
     │   └ fireLifecycle("turn_end")
     │
     └ finally: fireLifecycle("session_end")
```

**Hook 内部派发：**

```
fire(event, ctx):
   for hook of this.hooks:
     ├ hook.event !== event → continue
     ├ hook.once && firedOnce.has(key) → continue
     │   else firedOnce.add(key)
     ├ hook.condition && !evaluate(cond, ctx) → continue
     ├ hook.async:
     │   executeAction(hook, ctx)
     │      .then(r => recordNotification(r.output))
     │      .catch(err => recordNotification(`Async hook error: ${err.message}`))
     │   results.push({output: "(async)", success: true, reject: false})
     │   continue
     └ try:
         result = await executeAction(hook, ctx)
         results.push(result)
         if result.reject && event === "pre_tool_use" → break
       catch err:
         on_error 决定是否往 results push fail / reject 标记
```

## 文件组织

```text
gcode/
├── src/
│   ├── config/
│   │   └── config.ts           # HookConfig 接口、loadConfig 加载 hooks 字段
│   ├── hooks/
│   │   └── hooks.ts            # HookEngine、validate、condition 求值、动作执行器
│   ├── agent/
│   │   ├── agent.ts            # AgentConfig.hookEngine、fireLifecycle、executeBatch hook 钩子
│   │   ├── events.ts           # AgentEvent 联合类型
│   │   └── streaming-executor.ts
│   ├── tui/
│   │   └── app.tsx             # 持有 HookEngine、validateHooks 警告、注入到 Agent
│   └── main.tsx                # loadConfig 后把 hooks 作为 props 传给 App
├── tests/
│   ├── agent.test.ts           # surfaces lifecycle-hook output as a system reminder
│   └── config.test.ts          # mergeConfig 合并 hooks 数组
├── package.json                # bun test / tsc --noEmit 脚本
└── docs/typescript/ch12/
    ├── spec.md
    ├── plan.md
    ├── task.md
    └── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| HookEngine 形态 | 单 class，方法直接挂在实例上 | 简单直接；hook 数量小且 Agent 内只构造一次 |
| 配置入口 | 复用 `AppConfig.hooks` 字段 | 已有 `loadConfig` 多层合并，不再单独维护 hooks.yaml；用户配置面统一 |
| 校验时机 | App mount 时一次性 | 启动期立刻反馈；不阻塞主流程；TUI 显示 system 消息便于用户看到 |
| 错误聚合策略 | 所有错误 `;` 拼成一个 Error | 一次性给用户全部问题列表，不打断启动 |
| condition 解析 | 字符串切片 + `match` 正则 | 简洁单行表达式无需 AST；切片成本可忽略 |
| condition 字段取值 | 固定 5 个保留 key + args 兜底 | hook 场景关心的字段有限；字段穿透到 args 满足扩展性 |
| 命令执行方式 | `execSync` 同步阻塞 | 与 `pre_tool_use` 拦截语义一致——同步等结果才能 reject |
| 命令 timeout | 写死 30 秒 | 用户无法对单条 hook 设 timeout；耗时任务应走 `async: true` |
| HTTP 客户端 | 全局 `fetch` | Bun/Node 18+ 自带，无需额外依赖 |
| HTTP body | `JSON.stringify(context)` 固定 | 简单可预测；用户要灵活 body 时改用 command + curl |
| async hook | `Promise` 不 await、结果进 notification | 不阻塞主流程；与 reject 互斥避免语义混乱 |
| once 跟踪 key | `id ?? "${event}-${actionType}"` | 用户未显式给 id 也能去重；冲突由用户负责 |
| once 状态生命周期 | 跟随 HookEngine 实例 | 当前 App 整生命周期共享一个 HookEngine；`/clear` 不重置 |
| notification 注入位置 | turn_start 之前、`drainNotifications` → `addSystemReminder` | 与 skillReminder / 外部 notification 同位置；保证下一轮 LLM 请求能看到 |
| Hook 输出回灌为 system_reminder | 而非 user 消息 | 不污染对话历史的用户视角；与 plan / skill / memory 提醒同语义 |
| pre_tool_use 拦截语义 | `reject: true` 字段，不依赖退出码 | YAML 字段一眼可读；exit code 协议对 prompt/http/agent 等动作无法统一 |
| `shutdown` 事件 | 保留 EventName 联合但当前不 fire | 预留扩展位；不在主流程上引入未使用的调用 |
| agent 动作 | 通过外部注入 `agentRunner` | 子 Agent 调用链未与 hooks 直接耦合；未注入时返回明确失败信息 |
| 校验失败提示通道 | system 角色 ChatMessage | TUI 已有此渲染路径；避免 stderr 在 Ink 渲染下错位 |
````

````markdown
# Hook 生命周期挂钩系统 Tasks

> 模块根路径 `src/hooks/`、`src/config/`、`src/agent/`、`src/tui/`、`src/main.tsx`；运行时为 bun + TypeScript 5.x；测试统一走 `bun test`、类型校验走 `tsc --noEmit`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `src/config/config.ts` | 新增 `HookConfig` 接口、`AppConfig.hooks` 字段、`mergeConfig` 把 hooks 数组叠加合并 |
| 新建 | `src/hooks/hooks.ts` | `HookEngine` 类、`EventName` / `HookContext` / `HookResult` 类型、condition 求值、四类动作执行器、模块级 `validate` |
| 修改 | `src/agent/agent.ts` | `AgentConfig.hookEngine`、`Agent` 持有引擎；`run()` 主循环 6 个生命周期点 `fireLifecycle`、turn_start 之前 `drainNotifications`；`executeBatch` 顶部 `firePreToolHooks`、`processToolResult` 末尾 `fire("post_tool_use")` |
| 修改 | `src/tui/app.tsx` | `App` 接收 `hooks` props、mount 时 `validateHooks` 并把错误以 system 消息显示；`useRef<HookEngine>` 持有引擎；`runAgentLoop` 注入到 `Agent` 构造 |
| 修改 | `src/main.tsx` | `loadConfig()` 之后把 `cfg.hooks` 作为 props 传给 `<App>` |
| 修改 | `tests/config.test.ts` | 覆盖 `mergeConfig` 把 hooks 数组 append 合并的语义 |
| 修改 | `tests/agent.test.ts` | 覆盖"lifecycle hook 输出作为下一轮 system_reminder"路径 |

## T1：定义 HookConfig 与 AppConfig 字段**文件：** `src/config/config.ts`

**依赖：** 无

**步骤：**
1. 新增 `interface HookConfig`，字段：`id?`、`event`、`condition?`、`action: { type, command?, url?, method?, prompt? }`、`reject?`、`once?`、`async?`、`on_error?`
2. `AppConfig` 接口加 `hooks: HookConfig[]` 字段
3. `loadSingleFile` 把 `raw.hooks` 转成 `HookConfig[]`（缺省 `[]`）
4. `mergeConfig` 把 `override.hooks` 直接 append 到 `base.hooks`（不去重）
5. `validateProviders` 不动；hooks 校验留给 hook 模块

**验证：** `tsc --noEmit` 通过、`bun test tests/config.test.ts` 通过

## T2：写 HookEngine 主体（类型与 fire 流程）**文件：** `src/hooks/hooks.ts`

**依赖：** T1

**步骤：**
1. 顶部 `import { execSync } from "node:child_process"` 与 `import type { HookConfig } from "../config/config.js"`
2. 导出 `type EventName = "session_start" | "session_end" | "turn_start" | "turn_end" | "pre_send" | "post_receive" | "pre_tool_use" | "post_tool_use" | "shutdown"`
3. 导出接口 `HookContext`、`HookResult`
4. 导出 `class HookEngine`：
   - 私有字段：`hooks: HookConfig[]`、`firedOnce = new Set<string>()`、`notifications: string[] = []`
   - 公开字段：`agentRunner?: (prompt, ctx) => Promise<string>`
   - 构造接收 `hooks: HookConfig[]`
   - `recordNotification(msg: string)`：trim 后非空入队
   - `drainNotifications(): string[]`：取出并清空
5. `async fire(event: EventName, ctx: HookContext): Promise<HookResult[]>`：
   - 遍历 `hooks`、`hook.event !== event` 跳过
   - `hook.once`：用 `id ?? "<event>-<actionType>"` 作 key，命中 `firedOnce` 跳过，否则 add
   - `hook.condition` 存在 → `evaluateCondition` 不通过跳过
   - `hook.async=true`：`executeAction` 返回 Promise，`.then` 把 output 写 `recordNotification`、`.catch` 把 `Async hook error: <msg>` 写 notification；results 推 `{output: "(async)", success: true, reject: false}`、continue
   - 否则 `await this.executeAction(hook, ctx)`，把 result push 到 results；如果 `result.reject && event === "pre_tool_use"` → break
   - 命令抛错时按 `hook.on_error ?? "ignore"` 决定是否往 results push 失败记录（`fail` / `reject`）

**验证：** `tsc --noEmit` 通过

## T3：实现 executeAction 四类动作**文件：** `src/hooks/hooks.ts`

**依赖：** T2

**步骤：**
1. 私有方法 `executeAction(hook: HookConfig, ctx: HookContext): Promise<HookResult>` 按 `hook.action.type` 分发：
2. `case "command"`：
   - `execSync(action.command, { encoding: "utf-8", timeout: 30000, env: {...process.env, GCODE_EVENT: ctx.event, GCODE_TOOL: ctx.toolName ?? "", GCODE_FILE_PATH: ctx.filePath ?? ""} })`
   - 返回 `{output: output.trim(), success: true, reject: hook.reject ?? false}`
   - 抛错时 `throw err`（交给上层 `try/catch` 路由到 `on_error`）
3. `case "prompt"`：直接返回 `{output: action.prompt ?? "", success: true, reject: false}`
4. `case "http"`：
   - `fetch(action.url, { method: action.method ?? "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(ctx) })`
   - 读 `resp.text()` 作为 output
   - 返回 `{output, success: resp.ok, reject: hook.reject ?? false}`
   - 抛错时 throw
5. `case "agent"`：
   - 若 `!this.agentRunner` → 返回 `{output: "agent-type hook configured but no AgentRunner registered", success: false, reject: hook.reject ?? false}`
   - 否则 `await this.agentRunner(action.prompt ?? action.command ?? "", ctx)`，返回 `{output, success: true, reject}`
   - 异常 catch 后返回 `{output: err.message, success: false, reject: hook.reject ?? false}`
6. 默认 `default` 分支返回空 result

**验证：** `tsc --noEmit` 通过

## T4：实现 firePreToolHooks 包装**文件：** `src/hooks/hooks.ts`

**依赖：** T2、T3

**步骤：**
1. `async firePreToolHooks(toolName: string, args: Record<string, unknown>): Promise<{rejected: boolean; reason: string}>`
2. 构造 `ctx: HookContext = { event: "pre_tool_use", toolName, args, filePath: String(args.file_path ?? args.path ?? "") }`
3. `const results = await this.fire("pre_tool_use", ctx)`
4. 遍历 results 找到第一条 `reject=true` 返回 `{rejected: true, reason: r.output}`
5. 没有被拦截返回 `{rejected: false, reason: ""}`

**验证：** `tsc --noEmit` 通过

## T5：实现 condition 求值**文件：** `src/hooks/hooks.ts`

**依赖：** T2

**步骤：**
1. 自由函数 `evaluateCondition(condition: string, ctx: HookContext): boolean`：
   - `condition.split(/\s*(&&|\|\|)\s*/)` 切成 token 数组
   - 用第 0 项调 `evaluateSingleCondition` 得到初始结果
   - 从 i=1 步进 2，按 op (`&&` / `||`) 与下一原子求值短路 / 累积
2. 自由函数 `evaluateSingleCondition(expr: string, ctx: HookContext): boolean`：
   - trim 后判 `startsWith("!")` → 递归求反
   - `^(\w+)\s*==\s*"([^"]*)"$` → 精确相等
   - `^(\w+)\s*!=\s*"([^"]*)"$` → 精确不等
   - `^(\w+)\s*=~\s*"([^"]*)"$` → `new RegExp(value).test(left)`，编译失败 catch 返回 false
   - `^(\w+)\s*=\*\s*"([^"]*)"$` → 把 `**` / `*` / `?` 翻译成正则后测试
   - 未命中所有规则返回 false
3. `getContextValue(key: string, ctx: HookContext): string`：
   - 5 个保留 key：`tool` / `event` / `file_path` / `message` / 其它走 `ctx.args?.[key]`
   - 不存在时返回空串

**验证：** `tsc --noEmit` 通过

## T6：实现模块级 validate**文件：** `src/hooks/hooks.ts`

**依赖：** T2

**步骤：**
1. 导出 `function validate(hooks: HookConfig[]): Error | null`
2. 维护 `validEvents = new Set<string>([9 个事件名])`、`validActions = new Set(["command", "prompt", "http", "agent"])`
3. 逐条 hook 检查：
   - `event` 必填 + 枚举
   - `action.type` 必填 + 枚举
   - 按 action.type 分支校验 `command` / `prompt` / `url` / `prompt|command` 必填非空
   - `reject && async` 互斥
4. 标签格式：`hook[i]` 或 `hook[i] (id="<id>")`
5. 错误数组用 `; ` join 成单条 Error message；空数组返回 null

**验证：** `tsc --noEmit` 通过

## T7：在 Agent 上引入 hookEngine 字段与 fireLifecycle**文件：** `src/agent/agent.ts`

**依赖：** T2

**步骤：**
1. 顶部 `import type { HookEngine, EventName } from "../hooks/hooks.js"`
2. `AgentConfig` 接口加 `hookEngine?: HookEngine`
3. `Agent` 类加私有字段 `private hookEngine?: HookEngine`
4. 构造里 `this.hookEngine = config.hookEngine`
5. 新增 `private async fireLifecycle(event: EventName, message?: string): Promise<void>`：
   - 引擎为 undefined 直接返回
   - `await this.hookEngine.fire(event, { event, message })`
   - 遍历 results：`r.output` 非空 → `this.hookEngine.recordNotification(r.output)`

**验证：** `tsc --noEmit` 通过

## T8：Agent.run 6 个生命周期点 fireLifecycle**文件：** `src/agent/agent.ts`

**依赖：** T7

**步骤：**
1. `run()` 入口（iteration 初始化之后、`try` 之前）：`await this.fireLifecycle("session_start")`
2. 主 `while (looping)` 入口 + 写完 `skillReminder`、外部 `notificationFn` 之后：
   - `if (this.hookEngine) for (const note of this.hookEngine.drainNotifications()) this.conversation.addSystemReminder(note)`
   - `await this.fireLifecycle("turn_start")`
   - `await this.fireLifecycle("pre_send")`
3. `client.stream` 接收完毕、abort 检查之后：`await this.fireLifecycle("post_receive", fullText)`
4. 工具循环末尾、写完 `addToolResultsMessage` 之后、`yield "turn_complete"` 之后：`await this.fireLifecycle("turn_end")`
5. 整个 `try` 用 `finally` 包住，`finally { await this.fireLifecycle("session_end") }`

**验证：** `tsc --noEmit` 通过

## T9：executeBatch 与 processToolResult 接入 hooks**文件：** `src/agent/agent.ts`

**依赖：** T7

**步骤：**
1. `executeBatch(toolUses, parallel)` 单工具循环顶部：
   - `if (this.hookEngine) { const hookResult = await this.hookEngine.firePreToolHooks(tu.toolName, tu.arguments); if (hookResult.rejected) { events.push({ type: "tool_result", toolName, toolId, output: `Rejected by hook: ${hookResult.reason}`, isError: true, elapsed: 0 }); continue; } }`
2. `processToolResult(r, toolUses, events)` 末尾 `events.push tool_result` 之后：
   - `if (this.hookEngine) { const hookResults = await this.hookEngine.fire("post_tool_use", { event: "post_tool_use", toolName: r.toolName, message: r.result.output }); for (const hr of hookResults) if (hr.output) this.hookEngine.recordNotification(hr.output); }`

**验证：** `tsc --noEmit` 通过

## T10：在 App 组件中持有 HookEngine 并校验**文件：** `src/tui/app.tsx`

**依赖：** T2、T6

**步骤：**
1. 顶部 `import { HookEngine, validate as validateHooks } from "../hooks/hooks.js"` 与 `import type { HookConfig } from "../config/config.js"`
2. `Props` 接口加 `hooks: HookConfig[]`
3. `App` 函数签名解构 `hooks` props
4. `const hookEngineRef = useRef<HookEngine | null>(null)`
5. 首次 mount 的 `useEffect` 内（init providers / memory 之后）：
   - `const hookErr = validateHooks(hooks); if (hookErr) setMessages(prev => [...prev, { role: "system", content: \`Hook warning: ${hookErr.message}\` }]);`
   - `hookEngineRef.current = new HookEngine(hooks)`
6. `runAgentLoop` 构造 `new Agent({...})` 时加 `hookEngine: hookEngineRef.current ?? undefined`

**验证：** `tsc --noEmit` 通过

## T11：main.tsx 把 hooks 透传给 App**文件：** `src/main.tsx`

**依赖：** T1、T10

**步骤：**
1. `const cfg = loadConfig()` 已存在
2. `render(<App providers={cfg.providers} mcpServers={cfg.mcp_servers} hooks={cfg.hooks} />)` 加 `hooks` props

**验证：** `bun run src/main.tsx --help` 或直接 `bun run src/main.tsx`（如果有 provider）启动不报错

## T12：tests/config.test.ts 覆盖 mergeConfig hooks 合并**文件：** `tests/config.test.ts`

**依赖：** T1

**步骤：**
1. 新 `it("appends hooks", ...)` 用例
2. 构造 base、override 两个 `AppConfig`，分别含一条 hook
3. `const result = mergeConfig(base, override)`
4. `expect(result.hooks).toHaveLength(2)`

**验证：** `bun test tests/config.test.ts` 通过

## T13：tests/agent.test.ts 覆盖 lifecycle hook 注入 system reminder**文件：** `tests/agent.test.ts`

**依赖：** T7、T8

**步骤：**
1. import `HookEngine`
2. `runAgent(client, opts)` 辅助函数把 `opts.hookEngine` 透传到 `new Agent({ hookEngine })`
3. 新 `it("surfaces lifecycle-hook output as a system reminder on the next turn", ...)`：
   - 构造 `new HookEngine([{ event: "turn_start", action: { type: "prompt", prompt: "REMINDER_NOTE" } }])`
   - 用 MockClient 触发两轮（一次 tool_use → 一次 end）
   - 跑完 `expect(conv.getMessages().some(m => m.content.includes("REMINDER_NOTE"))).toBe(true)`

**验证：** `bun test tests/agent.test.ts` 通过

## T14：整体编译与测试**文件：** —

**依赖：** T1-T13

**步骤：**
1. `tsc --noEmit`
2. `bun test`
3. 若有失败定位到具体 ch12 改动；其它历史测试不应被破坏

**验证：** 两条命令都通过

## T15：tmux 端到端实跑**文件：** 临时 `.gcode/config.yaml`

**依赖：** T14

**步骤：**
1. 写一份测试 config.yaml：含 turn_start prompt hook、pre_tool_use command hook（reject + WriteFile 拦截）、post_tool_use async hook
2. tmux 新建 session：`bun run src/main.tsx`
3. 触发：
   - 让模型用中文回答（验证 prompt hook 注入）
   - 让模型尝试 WriteFile（验证拦截）
   - 让模型执行普通工具（验证 async hook 不阻塞）
4. 全程无 panic、Ink 渲染不错位

**验证：** 见 checklist 端到端场景

## 执行顺序

```text
T1                                # config.ts 字段
  └ T2 → T3 → T4 → T5 → T6        # hook 引擎主体（类型 / 动作 / 拦截包装 / 条件求值 / 校验）
T2 → T7 → T8                       # Agent 字段与 6 个生命周期点
       └ T9                        # executeBatch / processToolResult 钩入
T2/T6 → T10                        # App 持有引擎 + 校验提示
T1/T10 → T11                       # main.tsx 透传
T1 → T12                           # config 合并测试
T7/T8 → T13                        # agent 测试
T1-T13 → T14                       # 全量编译测试
T14 → T15                          # tmux 实跑
```

并行机会：
- T3 / T4 / T5 / T6 在 T2 完成后可并行
- T9 必须在 T7 之后但可与 T8 并行
- T12 / T13 在各自依赖项完成后可并行
````

````markdown
# Hook 生命周期挂钩系统 Checklist

> 每一项通过运行代码或观察行为验证，聚焦系统真实行为；编译走 `tsc --noEmit`、测试走 `bun test`、端到端走 `bun run src/main.tsx`。

## 实现完整性### 配置层

- [ ] `src/config/config.ts` 中 `HookConfig` 接口字段完整（id?/event/condition?/action/reject?/once?/async?/on_error?）（验证：`tsc --noEmit` 通过；`tests/config.test.ts` 中相关用例通过）
- [ ] `AppConfig.hooks` 在 `loadSingleFile` 缺省回退为 `[]`、`mergeConfig` 把两侧 hooks 数组叠加 append（验证：`bun test tests/config.test.ts -t "appends hooks"` 通过）
- [ ] 三层 YAML 文件 (`~/.gcode/config.yaml`、`<cwd>/.gcode/config.yaml`、`<cwd>/.gcode/config.local.yaml`) 同时存在时 hooks 全部生效（验证：本地建三个文件各放一条 hook，启动后总 hook 数 = 三条之和）

### HookEngine 主体

- [ ] `src/hooks/hooks.ts` 暴露 `HookEngine` 类、`EventName` 类型、`HookContext` / `HookResult` 接口、模块级 `validate`（验证：`tsc --noEmit` 通过）
- [ ] `EventName` 联合类型包含 9 个事件名（session_start / session_end / turn_start / turn_end / pre_send / post_receive / pre_tool_use / post_tool_use / shutdown）（验证：源码 grep 确认）
- [ ] `HookEngine.fire(event, ctx)` 按声明顺序遍历，event 不匹配跳过、once 跳过、condition 不通过跳过（验证：单元测试覆盖三个分支）
- [ ] `HookEngine.firePreToolHooks(name, args)` 自动从 args 拼 `filePath`（取 `args.file_path ?? args.path`），返回 `{rejected, reason}`（验证：单元测试用 `WriteFile` 工具入参确认 filePath 命中）
- [ ] `recordNotification` / `drainNotifications` 一进一出，drain 后清空（验证：单元测试 push 两条、drain 拿到长度 2、再 drain 拿到长度 0）

### 动作执行器

- [ ] `command` 动作通过 `execSync` 同步执行，注入 `GCODE_EVENT` / `GCODE_TOOL` / `GCODE_FILE_PATH` 三个环境变量，timeout 30s（验证：单元测试用 `printenv GCODE_EVENT` 命令，stdout 含事件名）
- [ ] `prompt` 动作直接把 `action.prompt` 当 output 返回（验证：单元测试断言 result.output 等于 action.prompt）
- [ ] `http` 动作走 `fetch`，默认 POST、Content-Type=application/json、body=`JSON.stringify(ctx)`（验证：临时 `Bun.serve` 拉一个 echo server，验证收到的 body JSON 含 `"event":"<name>"`）
- [ ] `agent` 动作未注入 `agentRunner` 时返回 `{success:false, output:"agent-type hook configured but no AgentRunner registered"}`（验证：单元测试构造一条 agent 类型 hook + 未注入 runner，fire 后 results[0].success === false）

### 条件求值

- [ ] `condition: tool == "WriteFile"` 在 toolName=WriteFile 时返回 true、否则 false（验证：单元测试覆盖）
- [ ] `condition: file_path =* "**/*.txt"` 对 `.txt` 路径命中、对 `.md` 路径不命中（验证：单元测试覆盖）
- [ ] `condition: event =~ "^pre_"` 对 `pre_tool_use` 命中（验证：单元测试覆盖）
- [ ] `condition: !tool == "Bash"` 对 toolName=WriteFile 命中、对 Bash 不命中（验证：单元测试覆盖）
- [ ] `condition: tool == "WriteFile" && file_path =* "**/*.go"` 两个原子都命中时 true（验证：单元测试覆盖）
- [ ] `=~` 表达式正则编译失败时（如 `=~ "["`）返回 false 而不抛错（验证：单元测试覆盖）

### 拦截与异步

- [ ] `pre_tool_use` 事件下 hook `reject=true` 后 `firePreToolHooks` 返回 `rejected=true, reason=hook.output`，且 `fire` 循环 break 跳过后续 hook（验证：构造两条 hook，第一条 reject、第二条 noop，断言第二条未执行）
- [ ] 其它事件下 hook `reject=true` 不产生拦截（`fire` 不 break；调用方也不消费 reject 字段）（验证：单元测试覆盖 turn_start 场景下两条 hook 都执行）
- [ ] `async: true` 的 hook 立即返回 `(async)` 占位 result，不阻塞主调用（验证：单元测试用 sleep 命令 + Date.now 差值断言 < 100ms）
- [ ] `async` 命令完成后 output 进 notification 队列；命令异常时 `Async hook error: <msg>` 进 notification（验证：单元测试 await 短延迟后 drainNotifications 拿到对应字符串）

### once 与错误策略

- [ ] `once: true` 的 hook 首次命中后被加入 `firedOnce`、第二次 fire 同事件不再执行（验证：单元测试两次 fire 后 results 长度 1）
- [ ] `id` 缺省时 once key 为 `<event>-<actionType>`（验证：构造无 id 的两条 once hook，断言它们用同一 key 时第二条被去重；事件或 actionType 不同时各自独立）
- [ ] `on_error: "ignore"`（默认）：命令抛错时 results 不追加失败记录、主流程不变（验证：单元测试用 `false` 命令、断言 results.length=0）
- [ ] `on_error: "fail"`：命令抛错时 results 追加 `success=false, reject=false`（验证：单元测试覆盖）
- [ ] `on_error: "reject"`：命令抛错时 results 追加 `success=false, reject=true`，在 `pre_tool_use` 下导致 rejected=true（验证：单元测试覆盖）

### 校验

- [ ] `validate([])` 返回 `null`（验证：单元测试覆盖）
- [ ] `validate` 对每条非法 hook 生成形如 `hook[i] (id="<id>"): <msg>` 的错误片段，用 `; ` join（验证：单元测试覆盖）
- [ ] `event` 缺失 → `event is required`；非 9 个枚举之一 → `invalid event '<x>'`（验证：单元测试覆盖）
- [ ] `action.type` 缺失 / 非法 → 相应错误（验证：单元测试覆盖）
- [ ] `command` 类型缺少 `action.command` → 错误；prompt / http / agent 同理（验证：单元测试覆盖）
- [ ] `reject && async` 同时为 true → `reject and async are mutually exclusive`（验证：单元测试覆盖）

### Agent 接入

- [ ] `AgentConfig.hookEngine?: HookEngine` 字段存在，`Agent` 构造时赋值（验证：`tsc --noEmit` 通过 + 源码 grep）
- [ ] `Agent.run` 入口调 `fireLifecycle("session_start")`、`finally` 中调 `fireLifecycle("session_end")`（验证：源码 grep + agent.test 覆盖 session_end 触发）
- [ ] 主循环每轮顶部 `drainNotifications()` 把每条经 `addSystemReminder` 写回对话（验证：`tests/agent.test.ts` 中"surfaces lifecycle-hook output as a system reminder on the next turn" 通过）
- [ ] 主循环每轮 `fireLifecycle("turn_start")`、`fireLifecycle("pre_send")`、流式接完 `fireLifecycle("post_receive", fullText)`、工具结果写回后 `fireLifecycle("turn_end")` 均存在（验证：源码 grep 5 处 `fireLifecycle`）
- [ ] `executeBatch` 单工具循环顶部调 `firePreToolHooks`，rejected 时生成 `isError=true`、`output="Rejected by hook: <reason>"` 的 tool_result，跳过权限检查与 executor.submit（验证：单元测试 mock `hookEngine.firePreToolHooks` 返回 rejected，断言权限 checker 未被调）
- [ ] `processToolResult` 末尾调 `fire("post_tool_use", {event, toolName, message})`，把每条非空 output 入 notification 队列（验证：单元测试覆盖）

### TUI / 入口接入

- [ ] `src/tui/app.tsx` 的 `Props` 接口含 `hooks: HookConfig[]`，`App` 函数签名解构（验证：源码 grep + `tsc --noEmit` 通过）
- [ ] 首次 mount 的 `useEffect` 内调 `validateHooks(hooks)`，非 null 时 `setMessages` 追加一条 `role: "system"`、content 形如 `Hook warning: <msg>` 的消息（验证：源码 grep + 启动配置错 hook 后屏幕能看到）
- [ ] `useRef<HookEngine | null>(null)` 在同一 useEffect 内被 `new HookEngine(hooks)` 赋值（验证：源码 grep）
- [ ] `runAgentLoop` 构造 `new Agent({...})` 时传入 `hookEngine: hookEngineRef.current ?? undefined`（验证：源码 grep）
- [ ] `src/main.tsx` 把 `cfg.hooks` 作为 props 传给 `<App>`（验证：源码 grep）

## 集成

- [ ] HookEngine 不在 Agent 之外被复用（验证：`grep -rn "new HookEngine" src/` 仅有 `src/tui/app.tsx` 一处命中）
- [ ] `validateHooks` 返回非 null 时 gcode 仍能正常进入 chat 状态（验证：写一条非法 hook、`bun run src/main.tsx` 启动后 TUI 渲染出 `Hook warning: ...` 并可继续输入）
- [ ] pre_tool_use 拦截的 tool_result 在下一轮 LLM 请求中可见（验证：`tests/agent.test.ts` 增补一条覆盖 rejected 路径的用例，断言 `events.some(e => e.type === "tool_result" && e.output.startsWith("Rejected by hook:"))` 为 true）
- [ ] notification 队列 drain 出来的字符串通过 `addSystemReminder` 写入对话，下一轮 `conversation.getMessages()` 能匹配到内容（验证：`tests/agent.test.ts` 中现有 REMINDER_NOTE 用例通过）

## 编译与测试

- [ ] 类型检查无错误：`tsc --noEmit`
- [ ] 全量单元测试通过：`bun test`
- [ ] `bun test tests/config.test.ts` 单独通过
- [ ] `bun test tests/agent.test.ts` 单独通过
- [ ] `bun run src/main.tsx` 启动后不抛错、TUI 渲染正常

## 端到端场景（tmux 实跑）

每个场景在 tmux 内启动一个 gcode 实例完成，验证人工/可视化行为。

### 场景 1：turn_start prompt 注入**预置 `.gcode/config.yaml`：**
```yaml
providers:
  - name: default
    protocol: anthropic
    base_url: https://api.anthropic.com
    model: claude-3-5-sonnet-latest
hooks:
  - id: zh-default
    event: turn_start
    action:
      type: prompt
      prompt: "请用中文回答"
```

**步骤：**
- [ ] tmux 启动 `bun run src/main.tsx`
- [ ] 输入英文消息 "hi there"
- [ ] LLM 回复使用中文（next turn 的 system_reminder 注入生效）
- [ ] 再发一条 "tell me about TypeScript"，仍然中文回复（每轮都注入）

### 场景 2：pre_tool_use command 拦截 WriteFile**预置：**
```yaml
hooks:
  - id: block-write
    event: pre_tool_use
    condition: tool == "WriteFile"
    reject: true
    on_error: reject
    action:
      type: command
      command: "echo 'blocked by hook policy' >&2; false"
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 输入"创建一个 hello.txt 内容是 hi"
- [ ] LLM 调 WriteFile 时被拦截
- [ ] 对话流中工具结果显示 `Rejected by hook: Hook error (rejecting): ...`
- [ ] 文件未被创建（手动 `ls hello.txt` 不存在）

### 场景 3：post_tool_use async 后台命令**预置：**
```yaml
hooks:
  - id: bg-log
    event: post_tool_use
    async: true
    action:
      type: command
      command: "echo \"$(date) tool_done\" >> /tmp/gcode-hook.log"
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 让 LLM 执行一个 ReadFile 或 Glob 工具
- [ ] 主对话立即进入下一轮、不停顿
- [ ] `cat /tmp/gcode-hook.log` 看到时间戳条目

### 场景 4：once + session_start prompt**预置：**
```yaml
hooks:
  - id: first-session-note
    event: session_start
    once: true
    action:
      type: prompt
      prompt: "first-session-only-note"
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 发任意消息——下一轮 LLM 请求里有 `first-session-only-note` 系统提醒
- [ ] 再发一条消息——第二次 Agent.run 时 session_start 不再 fire（once 命中）
- [ ] 重启 gcode 进程后又会出现一次

### 场景 5：非法 hook 不阻塞启动**预置：**
```yaml
hooks:
  - id: bad-event
    event: not_a_real_event
    action:
      type: command
      command: "echo x"
  - id: good
    event: turn_start
    action:
      type: prompt
      prompt: "ok"
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] TUI 顶部出现 system 消息 `Hook warning: hook[0] (id="bad-event"): invalid event 'not_a_real_event'`
- [ ] 仍能正常输入与对话
- [ ] 合法 hook（good）仍然生效（下一轮里能看到 "ok" 注入）

### 场景 6：http 通知（post_receive）**预置：**
- 另起终端：`python3 -m http.server 9999 --bind 127.0.0.1`（或任意 echo server）
```yaml
hooks:
  - id: notify-receive
    event: post_receive
    action:
      type: http
      url: "http://127.0.0.1:9999/recv"
      method: POST
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 发任意消息触发一轮回复
- [ ] echo server 控制台看到 POST 请求（如 `python3 -m http.server` 日志里的 `POST /recv`）

### 场景 7：reject + async 互斥校验**预置：**
```yaml
hooks:
  - id: bad-combo
    event: pre_tool_use
    reject: true
    async: true
    action:
      type: command
      command: "echo x"
```

**步骤：**
- [ ] tmux 启动 gcode
- [ ] TUI 顶部出现 system 消息 `Hook warning: hook[0] (id="bad-combo"): reject and async are mutually exclusive`
- [ ] gcode 仍能进入聊天

### 场景 8：端到端组合**预置：** 把场景 1、2、3 的 hook 合并到一份 config.yaml

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 首轮触发 turn_start prompt 注入、模型中文回答
- [ ] 输入"帮我写 hello.txt 并跑一遍 ls"
- [ ] LLM 调 WriteFile 被拦截 → 改用 Bash 创建文件 → 触发 post_tool_use async log
- [ ] 整个过程不卡顿、`tsc --noEmit` 与 `bun test` 全过、无 panic
````


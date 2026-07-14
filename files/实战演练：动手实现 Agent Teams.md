# 第15章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装上了 Worktree，让每个子 Agent 拥有独立的文件系统，彻底消除了并行修改的冲突。但那套模型还是「星型」的：主 Agent 在中心，子 Agent 在周围，所有通信都要经过主 Agent，而且主Agent还得自己下场干活，一旦任务复杂，可能就力不从心

这一章要给 GCode 装上 Agent Team 机制。Lead 还可以开启 Coordinator Mode 专注调度，从而应对更复杂的任务

具体要新增这些东西：

* **AgentTeam 核心结构&#x20;**：团队数据模型、队员花名册、团队配置持久化

* **三种执行后端&#x20;**：tmux pane、iTerm2 pane（独立进程隔离）、in-process（同进程轻量运行）+ 自动检测

* **协调工具集&#x20;**：复用已有 Task 工具 + 新增 SendMessage，注入到队员工具池

* **Mailbox 消息系统&#x20;**：按 agentID 分文件存储，tmux 后端额外 send-keys 唤醒

* **团队生命周期管理&#x20;**：TeamCreate / TeamDelete 顶层工具，队员 spawn、收敛合并、清理

* **队员空闲与续写&#x20;**：磁盘 transcript 持久化，Lead 可通过 SendMessage 恢复已停止的队员

* **Coordinator Mode&#x20;**：双锁激活、工具集收窄、四阶段工作流提示词注入

这章 **不做&#x20;**：跨机器的分布式 Agent Team、队员之间的实时流式通信。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法

这一步的目标是：把主 Agent 升级为 Team Lead，让它能创建长期团队，派生多个队员并行干活。队员之间通过共享任务列表和邮箱直接协作，而不是所有信息都得经过 Lead 中转。Lead 还能开启 coordinator 模式，专注派人和决策，把代码修改交给队员。

技术要求：

- 抽象一个长期存在的「小组」对象，记名称、负责人、成员花名册和持久化位置，成员记角色、工作目录、运行后端、是否要审批
- 支持几种成员运行后端：独立终端窗格里跑完整实例做强隔离（终端复用工具或终端本身的分屏能力都行），或同进程协程轻量跑；按环境优先级自动选，不静默降级
- 给成员发一组协作工具：共享任务的增删查改（带依赖字段）和点对点发消息；主入口和普通子 Agent 看不到这些工具；需要审批的队员先把计划发给 Lead，Lead 用一种特定结构的回复批准或驳回再开干
- 点对点消息走「名称注册表加邮箱文件」两段式，独立进程后端还要额外唤醒目标窗格，支持广播和几种结构化协议消息
- 发起方设计成 Lead：把用户目标拆成带依赖的任务写进共享清单、派生成员，全部完成后用 git 合并各人目录，能解决的冲突就解决、搞不定就回滚上报
- 成员干完自然停下后标记空闲并通知 Lead，之后 Lead 发消息就能从磁盘恢复它的上下文继续指派，不用重头再 spawn
- 单独给一个 coordinator 开关：需要在配置里先开能力开关，再由用户用环境变量主动启用，两把锁都打开才生效；开启后剥夺发起方的写文件工具，保留读类工具和 shell（还要靠 shell 跑 git 合并），只留派人、终止、发消息、合并代码这些事

这一步先不做跨机器的分布式团队、成员间实时流式通信，以及更复杂的任务依赖约束。

持久化与消息格式：

- 小组配置持久化到用户目录下按小组名分的文件夹，里面放各成员的邮箱和元数据
- 一条消息带发件人、正文、时间戳、是否已读、摘要，落盘时自动补时间戳、默认未读
- 邮箱文件用锁文件保证并发安全，拿不到锁就重试，锁太旧视为过期
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

来验收一下结果：



我们主要是看coordinatoe mode，生产基本使用这个，单纯对等的team是十分不稳定的



启动GCode，输入：

![]()

然后主Agent，会去进行队伍的创建，创建后，会去开始启动队员，我们能在.gcode/teams这里有一个叫read-demo的一个队伍信息

![]()

里面分别是我们的lead和我们的alice，然后过一段时间后，alice就会完成任务，传达给lead，然后lead会汇总这个结果

![]()

然后我们测测队员之间的worktree的隔离，我们先搞个测试文件，内容如下

![]()



然后，我们输入

![]()

可以看到，lead会知道需要开worktree去并行修改，我们也能在.gcode/worktrees看到它们的worktree



![]()

等两个队员完成后，会让lead去审阅和合并

![]()

我们可以看看目前的Demo.md的内容

![]()

并行修改是成功的，无冲突，然后完成后会清除team和汇总

![]()

这就是我们的coordinatoe模式的team的样子，lead就是lead，专注于决策，不会下一线干活，下属去干活，然后向上汇报，就像我们的公司协作分工结构一样

![]()



到这里，GCode 的核心能力已经全部搭建完毕。



恭喜你！从终端原型，到工具系统、Agent 循环、权限管理、上下文压缩、Hook 系统、SubAgent、Worktree，再到现在的 Agent Team，你亲手完成了一个完整的 Coding Agent！

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

````markdown
# Agent Team Spec## 背景

ch13 SubAgent 把任务从单 Agent 委派给子 Agent,实现了消息、权限账本、文件读缓存与 token 计数的隔离;ch14 Worktree 给每个子 Agent 配上独立工作目录,文件系统层并发也安全。但这两章合起来仍是「星型」拓扑——所有子 Agent 只能与主 Agent 通信,子 Agent 之间没有横向通道;主 Agent 既要决策、又要中转,既是大脑也是邮局。对「同时重构四个模块」「三个角度查同一个 bug」这类持续性、需要互相交流的工作,星型结构的瓶颈很明显。

本章把 gcode 从星型升级到「网状」:

- 主 Agent 创建 **Team** 后升任 **Lead**,Team 是一个长期存在的小组对象,记名称、负责人、成员花名册、持久化位置
- 每个 **队员**(Teammate)是一个独立的 Agent 实例,有自己的 Conversation、自己的 Worktree
- 三种执行后端 `tmux` / `iterm2` / `in-process` 覆盖不同环境;按优先级一次性自动检测,启动后不静默回退
- 队员之间通过**共享任务列表**与**邮箱**直接通信,不必经过 Lead 中转;协作工具仅在 Team 上下文出现
- 队员可暂停可续写,自然停下后 session 留盘,Lead 调 `SendMessage` 会从磁盘恢复后继续指派
- Lead 可选启用 **Coordinator Mode**(独立于 Team,但典型场景一起用),双锁机制下剥夺 Write/Edit 工具,只保留调度、读类操作与 shell(用于 git merge)
- 收敛阶段由 Lead 用 Bash 跑 `git merge` 逐个合各队员的 worktree 分支,冲突由 LLM 推理解决,搞不定就 `git merge --abort` 保留 worktree 上报用户

gcode 现有相关基础设施:
- ch13 `task.Manager` 已支持后台任务管理 + `SendMessage` 续派 + `agentNameRegistry` (`byName` 字段已是 name → id 映射);本章扩展为多 Team 寻址
- ch13 `agent.AgentTool.Execute` 已是子 Agent 启动入口,本章新增 `team_name` 参数走 Team spawn 分支
- ch13 工具过滤 `tool.ApplyAgentToolFilter` 已支持多层防线;本章新增 Team 专属白名单(协作工具)与 Coordinator Mode 白名单
- ch14 `worktree.Manager` 已支持嵌套 slug(`team/alice` → `.gcode/worktrees/team+alice/`),本章直接复用做队员 worktree(slug 形式 `team-<teamName>/<member>`)
- ch12 session 持久化(`.gcode/sessions/<id>/conversation.jsonl`)按对话粒度落盘;本章给每个队员单独申请一个 session,队员 stop 不删 session,SendMessage 续派时通过 session 反序列化 Conversation
- ch10 `internal/command` slash 命令系统,本章新增 `/team` 系列
- ch07 `permission` 已支持 `plan` 模式,本章给 `planModeRequired` 队员的 Plan 提交-Lead 审批工作流套用同一引擎

本章**只做**到「Lead 多人协作 + Plan 审批 + Coordinator 收敛」。跨进程跨机器分布式团队、队员之间实时流式通信、复杂任务依赖约束(优先级 / deadline)、Windows 平台 iTerm2 适配均不在范围内。

## 目标- **G1**: 提供 `team.Team` 与 `team.Manager`——Team 封装小组生命周期(name、leadAgentID、members、configPath);Manager 在单 gcode 进程内管理多个 Team(典型场景同时只有一个活跃 Team)
- **G2**: 提供 `TeamCreate` 工具——主 Agent 调用即创建 Team、调 `detectBackend` 确定后端、写 `~/.gcode/teams/<sanitizedName>/config.json`、把 Lead 注册成第一个成员;同名团队自动后缀 `-2` / `-3` 避免冲突
- **G3**: 扩展 `Agent` 工具——增加 `team_name` 可选参数,非空时走 Team spawn 分支:加载定义 → 创建队员 Worktree → 注入协作工具 → 按后端分流 spawn → 注册到 `agentNameRegistry` → 写入 `team.members`
- **G4**: 提供 `TeamDelete` 工具——确认所有成员 `isActive=false` 后,删队员 worktree + 删 team 目录,Lead 退出团队;有活跃成员时拒绝删除
- **G5**: 三种执行后端 `tmux` / `iterm2` / `in-process`,统一抽象 `team.Backend` 接口;`detectBackend` 按 `$TMUX → $TERM_PROGRAM=iTerm.app && command -v it2 → command -v tmux → in-process` 优先级一次性决定,不做运行时回退
- **G6**: 队员注入 5 个协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate`(后者支持 `addBlocks` / `addBlockedBy` 依赖字段) / `SendMessage`;主 Agent 与普通 SubAgent 看不到这些工具
- **G7**: `SendMessage` 寻址支持 `to="<name>"`、`to="<agentID>"`、`to="*"` 广播三种;通过 `agentNameRegistry` 解析 name → agentID,写邮箱;Tmux/iTerm2 后端额外通过 `send-keys` 唤醒目标 pane
- **G8**: 邮箱文件并发安全——每个收件人独占一个 lock 文件(`O_CREATE|O_EXCL`),抢锁失败按 5-100ms 随机抖动重试,最多 10 次;持锁超过 10 秒视为 stale 直接清掉;消息文件 read-modify-write,走 `os.WriteFile` 原子替换
- **G9**: 三种结构化消息——纯文本(必带 5-10 词 `summary`)、`shutdown_request` / `shutdown_response`(优雅退出协商)、`plan_approval_response`(Plan 审批回复,只允许 Lead 发送);全部走同一 SendMessage 入口,以 `type` 字段分流
- **G10**: 队员收到的未读消息在下一轮 Agent Loop 开头被读出,以 `<incoming-messages>` system reminder 形式注入到 LLM 输入;读后批量标记为 read
- **G11**: 队员 spawn 两种路径——指定 `subagent_type` 走定义式(从空白对话起步)、留空走 Fork 路径(继承 Lead 完整对话历史);Fork 路径受 `FORK_TEAMMATE` feature flag 控制,默认关闭
- **G12**: 队员 `runToCompletion` 结束后自动通知 Lead——团队 config 里把该成员 `isActive=false`、Lead 邮箱收到 `idle_notification`;队员的 Conversation 已通过 ch12 Writer 实时写入 session 文件
- **G13**: 队员续写——Lead 调 `SendMessage(to="alice", message="…")`,系统检测 alice 已 stop 时,从 ch12 session 反序列化 Conversation、新建一个 goroutine 走 `RunToCompletion(initialMessage=newMessage)`;Conv 沿用历史
- **G14**: `planModeRequired:true` 的队员被 spawn 时强制以 plan 模式起步——计划生成后通过 SendMessage 发给 Lead,Lead 用 `plan_approval_response` 回复 approve 或 reject;approve 时队员权限模式切到 Lead 的当前模式继续执行,reject 时队员按 feedback 调整后重新提交
- **G15**: Coordinator Mode 独立于 Team——`isCoordinatorMode() = feature(COORDINATOR_MODE) && envTruthy(GCODE_COORDINATOR_MODE)`,两把锁全开才生效;开启后 Lead 工具集收窄到 `Agent / TeamCreate / TeamDelete / TaskCreate / TaskGet / TaskList / TaskUpdate / SendMessage / read_file / glob / grep / bash`(剥夺 `write_file` / `edit_file`),并注入 coordinator 系统提示词引导 Research / Synthesis / Implementation / Verification 四阶段
- **G16**: 收敛全部由 LLM 推理驱动——Lead 用 Bash 跑 `git merge worktree-team-<team>+<member> --no-ff -m "merge: <member>"` 逐个合,冲突由 Lead 用 Read / Edit / Bash 自行解决;搞不定就 `git merge --abort`,保留队员 worktree,把冲突上下文上报给用户
- **G17**: 提供 TUI slash 命令 `/team list` / `/team info <name>` / `/team delete <name>` / `/team kill <member>`,辅助用户人工介入
- **G18**: 与 ch04~ch14 既有功能协同——主 Agent 平时(未 TeamCreate)看到的工具列表不变;协作工具仅在 Team 上下文出现;ch13 后台任务 / AdoptRunning / SendMessage 续派路径保留,Team 队员的续派复用同一套底层 `task.Manager`

## 功能需求### Team 数据结构与 Manager- **F1**: `team.Team` 字段——`Name`(原始名)、`SanitizedName`(经 `sanitize` 处理后用于路径)、`LeadAgentID`、`Members []*TeammateInfo`、`ConfigDir`(`<homeDir>/.gcode/teams/<sanitizedName>/`)、`ConfigPath`(`<ConfigDir>/config.json`)、`CreatedAt time.Time`、`Backend BackendType`
- **F2**: `team.TeammateInfo` 字段——`Name`(Lead 分配的队员名,Team 内唯一)、`AgentID`(对应 `task.BackgroundTask.ID`)、`AgentType`(使用的 subagent 定义名;Fork 路径下为 `""`)、`Model`(覆盖,空表 inherit)、`WorktreePath`(绝对路径)、`Branch`(对应 worktree 分支名)、`BackendType`(可 per-member 不同)、`PaneID`(tmux pane / iterm2 split id,in-process 为空)、`IsActive *bool`(`nil` 或 `true` 表活跃,`false` 表空闲;终止后直接从 `Members` 移除)、`PlanModeRequired bool`、`SessionDir`(队员独立 session 目录绝对路径)
- **F3**: `team.Manager` 字段——`mu sync.Mutex`、`teams map[string]*Team`(按 `SanitizedName` 索引)、`homeDir`(`os.UserHomeDir`)、`wtMgr *worktree.Manager`、`taskMgr *task.Manager`、`registry *AgentNameRegistry`
- **F4**: `team.NewManager(homeDir string, wtMgr *worktree.Manager, taskMgr *task.Manager, reg *AgentNameRegistry) (*Manager, error)`——校验 `<homeDir>/.gcode/teams/` 可写;扫描该目录还原 `teams` map(每个子目录读一次 `config.json`,跳过解析失败的并 stderr 警告)
- **F5**: `Manager.Create(ctx, name, agentType string) (*Team, error)`——
  1. `sanitized = sanitize(name)`(只保留 `[a-zA-Z0-9._-]`,其他替换为 `-`,首尾去 `-`,空字符串拒绝)
  2. 同名冲突时在 `sanitized` 后追加 `-2` / `-3` 直到唯一
  3. 创建 `ConfigDir`,落 `config.json`(原子写)
  4. 调 `detectBackend()` 写入 `team.Backend`
  5. 取当前 Lead Agent ID(从 ctx 取,本期 Lead = 主 Agent,固定 `"lead"`)
  6. 把 Lead 注册成第一个成员(`TeammateInfo{Name:"lead", AgentID:"lead", IsActive:nil}`)
  7. 加入 `teams` map,返回 Team
- **F6**: `Manager.Get(name string) (*Team, bool)`——按 sanitized name 查询
- **F7**: `Manager.Delete(ctx, name string, force bool) error`——
  1. 取 Team;不存在 error
  2. 非 force 时若有 `member.IsActive != false`(包括 nil 和 true)返回 `ErrTeamHasActiveMembers`
  3. 逐个删队员 Worktree(调 `wtMgr.Remove(name, {DiscardChanges:true})`,失败只警告不中断)
  4. 删队员 session 目录(`os.RemoveAll(member.SessionDir)`,失败只警告)
  5. 删 `ConfigDir`(`os.RemoveAll`)
  6. 从 `teams` map 移除
- **F8**: `Team.AddMember(info *TeammateInfo) error`——校验 Name 在 Team 内唯一;加入 `Members`;持久化 `config.json`(原子写——先写 `.tmp` 再 `os.Rename`)
- **F9**: `Team.SetMemberActive(name string, active bool) error`——更新 `IsActive`,持久化
- **F10**: `Team.RemoveMember(name string) error`——从 `Members` 移除,持久化

### 后端检测与抽象- **F11**: `team.BackendType` 字符串枚举,取值 `"tmux"` / `"iterm2"` / `"in-process"`
- **F12**: `team.Backend` 接口——
  ```go
  type Backend interface {
      Type() BackendType
      // Spawn 在后端启动一个新队员;返回 PaneID(in-process 返回空)。
      // 对 Pane 后端,Spawn 会执行 split-window / it2 split + send-keys 启动 CLI。
      // 对 in-process 后端,Spawn 在同进程起一个 goroutine 跑 RunToCompletion。
      Spawn(ctx context.Context, req SpawnRequest) (paneID string, err error)
      // Wake 用于消息到达时唤醒目标 pane。in-process 后端为 no-op。
      Wake(ctx context.Context, paneID string) error
      // Kill 终止 pane(Pane 后端)或 cancel goroutine(in-process)。
      Kill(ctx context.Context, paneID string) error
  }
  ```
- **F13**: `team.SpawnRequest` 字段——`TeamName`、`MemberName`、`AgentID`、`WorktreePath`、`SessionDir`、`AgentType`、`Model`、`InitialPrompt`、`PlanModeRequired`、`SubAgent *agent.Agent`(in-process 用)、`Conv *conversation.Conversation`(in-process 用)、`TaskMgr *task.Manager`(in-process 用)、`AgentIDOverride *string`(in-process 用,把 task id 回写给调用方)
  - 对 Pane 后端(tmux / iterm2),`InitialPrompt` **不**走命令行——在 `Backend.Spawn` 调用前由 `team.SpawnTeammate` 预写入 alice 的 mailbox(类型 `text`,from `lead`),子进程启动后读 mailbox 自然拿到。这样避免长 prompt 在命令行里 shell-quote 的边界问题。
- **F14**: `team.DetectBackend() BackendType`——按以下优先级一次性决定:
  1. `os.Getenv("TMUX") != ""` → `tmux`
  2. `os.Getenv("TERM_PROGRAM") == "iTerm.app"` && `exec.LookPath("it2") == nil` → `iterm2`
  3. `exec.LookPath("tmux") == nil` → `tmux`(外部 spawn 新 session)
  4. 否则 → `in-process`

### tmux 后端- **F15**: `tmux.Backend` 实现 `Backend` 接口
  - `Spawn`:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`(横向 split,-P 打印 pane id,-F 指定格式);`cmd` 为 `gcode --team-member --team <teamName> --member <memberName> --agent-id <agentID> --session-dir <sessionDir> --worktree <worktreePath> [--agent-type <type>] [--model <model>] [--plan-mode]`
  - `--agent-id` 是关键:Lead spawn 时已生成的 agentID 直接传给子进程,子进程不需要读 Lead 还没写完的 `config.json` 找自己
  - `Wake`:`tmux send-keys -t <paneID> "" Enter`(回车触发子进程 stdin scanner 读到一行,立刻去 mailbox 轮询;in-process 后端无此动作)
  - `Kill`:`tmux kill-pane -t <paneID>`(忽略 pane 不存在错误)
- **F16**: 若当前在 tmux 会话外但本机有 tmux,Spawn 走 `tmux new-session -d`(detached 新 session);若失败回落到错误而非 in-process(不静默回退)

### iterm2 后端- **F17**: `iterm2.Backend` 实现 `Backend` 接口
  - `Spawn`:`it2 split --new-pane --command "<cmd>"`,`<cmd>` 与 F15 同构(含 `--agent-id`);通过 `it2` CLI 解析输出取 pane id
  - `Wake`:`it2 send-text --pane <paneID> ""`(空文本即唤醒)
  - `Kill`:`it2 close-pane --pane <paneID>`

### in-process 后端- **F18**: `inprocess.Backend` 实现 `Backend` 接口
  - `Spawn`:复用 `task.Manager.Launch`——创建带 `WithCwd(worktreePath)` 的子 Agent,在 goroutine 里跑 `RunToCompletion`;返回空 `paneID`,内部用 `task.BackgroundTask.ID` 关联
  - `Wake`:no-op(同进程,下一轮 Loop 自动读邮箱)
  - `Kill`:调 `task.Manager.Stop(agentID)`
- **F19**: in-process 后端的队员**只允许同步子 Agent**——其 `Agent` 工具看不到 `team_name` 参数(`team_name` 被拦截);后台子 Agent 也禁用(过滤 `run_in_background=true`)

### Pane 后端子进程的 team-member 模式- **F19a**: `gcode --team-member` 在 Pane 后端被 spawn 的 gcode 子进程**不启动 TUI**,而是跑一个自治循环(`cmd/gcode/team_member.go` 的 `runTeamMember`):
  1. 从 CLI 解析 `--team / --member / --agent-id / --session-dir / --worktree / --agent-type / --model / --plan-mode`
  2. `os.Chdir(--worktree)`,让该进程的 `os.Getwd()` 与权限沙箱根都指到 worktree
  3. 构造**单独的** `team.Manager`、provider、registry、permission engine、hook engine(完整复用 Lead wire 代码,但不构造 TUI)
  4. 构造队员 `*agent.Agent`,设 `WithDontAsk(true)`(子进程无 TUI 接 ApprovalRequest)、注入 `<team-context>` reminder、用 `SetCtxDecorator` 注入 `TeammateContext`(含 mailbox client)
  5. 启动 stdin scanner goroutine:任何来自 tmux send-keys 的回车都推到 `wakeCh`,触发立刻去 mailbox 轮询(0~2s 内响应)
  6. 进入主循环:
     - 读 `mailbox.ReadUnread(agentID)`
     - 空 → 阻塞等 `wakeCh` 或 2s 兜底轮询
     - 有未读:`text` 拼成 task,`plan_approval_response(approve=true)` 触发 `SetPermissionMode(default)` + 续派 prompt,`shutdown_request` 触发优雅退出
     - 调 `agent.RunToCompletion(ctx, conv, task, events)` 让队员跑到底
     - 完成后:写 `summary="<name> idle"` 到 Lead mailbox,再 `Team.SetMemberActive(name, false)`
     - 检测到 mailbox 目录已被删除(Lead 调用 `/team delete`)→ 优雅退出
- **F19b**: 该自治循环的最小事件转 stdout 打印:`Text` 直接 print、`ToolEvent` 打 `● tool(args)` 行、`Done` 打分隔横线、错误打 stderr。pane 内 UX 是只读的"日志流",不接受用户输入(任何回车都被 stdin scanner 消费做 Wake 信号)
- **F19c**: 跨进程 `config.json` 写入并发:Lead 与子进程是不同进程,各持一份内存中的 Team 对象。`Team.AddMember` 与 `Team.SetMemberActive` 在加锁后**先从磁盘 reload `Members` 字段**再修改+原子 save(`reloadFromDiskLocked`)。否则会出现"子进程内存看不到自己,SetMemberActive 静默 no-op"的丢更新问题

### TeamCreate 工具- **F20**: 工具名 `TeamCreate`,参数 schema:
  - `team_name`(string,必填):团队名,经 sanitize 后做 `Team.SanitizedName`
  - `description`(string,可选):团队描述,写入 `config.json` 的 `description` 字段
  - `agent_type`(string,可选):本期保留位,实际不使用
- **F21**: `TeamCreate.Execute`——
  1. 解析参数
  2. 调 `Manager.Create(ctx, name, agentType)` 创建 Team
  3. 返回 JSON `{"team_name":"<sanitized>","backend":"<type>","config_path":"<path>"}`
  4. Lead 创建 Team 后保持原有工具集(非 Coordinator Mode 下不剥夺工具)

### TeamDelete 工具- **F22**: 工具名 `TeamDelete`,参数 `team_name`(必填)、`force`(可选 bool)
- **F23**: `TeamDelete.Execute`——调 `Manager.Delete(ctx, name, force)`,返回成功/失败消息

### Agent 工具扩展 (team_name)- **F24**: `Agent` 工具参数 schema 新增字段:
  - `team_name`(string,可选):非空时走 Team spawn 分支
- **F25**: 当 `team_name` 非空,`Agent.Execute` 走 Team 分支:
  1. 校验 `team_name` 对应的 Team 存在(`Manager.Get`),否则 error
  2. 校验当前调用者权限:
     - 主 Agent / Lead → 允许
     - in-process 队员调 Team spawn → 拒绝(`ErrInProcessTeammateNoSpawn`)
     - Pane 队员可以调(README:Pane 队员拥有完整 Agent 工具),但 `team_name` 参数被屏蔽(队员不能往 Team 加人,只 Lead 在 Coordinator Mode 或普通 Lead 调用时可以)
  3. 加载 `subagent.Definition`(指定 `subagent_type` 走 Catalog;留空且 `FORK_TEAMMATE` 开启走 Fork 定义;留空且 flag 关闭则用 `general-purpose`)
  4. 调 `wtMgr.Create(ctx, "team-"+sanitized+"/"+memberName, "HEAD", false)` 创建 Worktree
  5. 申请新 session 目录(复用 `session` 包接口),作为 `SessionDir`
  6. 构造 in-process 子 Agent(若后端为 in-process)或仅构造 SpawnRequest(若 Pane 后端);把协作工具注入到子 Agent 的 allowed tools 集合
  7. 注入队员系统提示词附录(F39)
  8. 注入 `<team-context>` initial system reminder 到子 Agent Conv
  9. **若是 Pane 后端**,在 `Backend.Spawn` 之前把 `InitialPrompt` 作为 `text` 消息(`from=lead, summary=initial task`)预写入 alice 的 mailbox(F13);in-process 后端不需要,`InitialPrompt` 直接作为 `task.Manager.Launch` 的 task 参数
  10. 调 `team.Backend.Spawn(ctx, req)` spawn,记 `paneID`
  11. 注册到 `agentNameRegistry`:`memberName → agentID`
  12. 构造 `TeammateInfo` 加入 `Team.Members`,持久化(F19c 的 reload-before-modify 兜底)
  13. 返回 JSON `{"member_name":"<name>","agent_id":"<id>","worktree":"<path>","backend":"<type>","pane_id":"<id 或空>"}`

### 协作工具- **F26**: `TaskCreate` 工具——参数 `title`(必填)、`description`(可选)、`assignee`(可选,队员名)、`blocked_by`(可选 []string,任务 id);返回新建 `task_id`(`task_<6位 hex>`);写入 Team 的 `tasks.json`(原子)
- **F27**: `TaskGet` 工具——参数 `task_id`,返回任务详情
- **F28**: `TaskList` 工具——参数可选 `status` 过滤(`pending`/`in_progress`/`completed`/`blocked`);返回任务数组,带依赖关系标注(`blocked_by`、`blocks`、是否 `is_ready`(无未完成 blocker))
- **F29**: `TaskUpdate` 工具——参数 `task_id`(必填)、`title`(可选)、`description`(可选)、`status`(可选)、`assignee`(可选)、`addBlocks`(可选 []string)、`addBlockedBy`(可选 []string)、`removeBlocks` / `removeBlockedBy`(可选 []string);更新后持久化
- **F30**: `tasks.json` 结构:
  ```json
  {
    "tasks": [
      {
        "id": "task_a1b2c3",
        "title": "...",
        "description": "...",
        "status": "pending",
        "assignee": "alice",
        "blocked_by": ["task_xxx"],
        "blocks": ["task_yyy"],
        "created_at": 1234567890,
        "updated_at": 1234567890
      }
    ]
  }
  ```
  写入走 `<TeamConfigDir>/tasks.json`,read-modify-write,文件锁 `tasks.lock`(同邮箱 lock 机制)

### SendMessage 工具与邮箱- **F31**: `SendMessage` 工具——参数:
  - `to`(string,必填):队员名 / agentID / `"*"` 广播
  - `summary`(string,纯文本消息时必填,5-10 词)
  - `message`(string,可选,纯文本消息体)
  - `type`(string,可选,默认 `"text"`):取值 `"text"` / `"shutdown_request"` / `"shutdown_response"` / `"plan_approval_response"`
  - `payload`(object,可选):结构化消息的载荷(如 `shutdown_response` 的 `{approve, reason}`)
- **F32**: 邮箱文件路径——`<TeamConfigDir>/mailbox/<agentID>.json`,结构:
  ```json
  {
    "messages": [
      {
        "from": "lead",
        "to": "alice",
        "type": "text",
        "summary": "interface change",
        "content": "...",
        "payload": null,
        "timestamp": 1234567890,
        "read": false
      }
    ]
  }
  ```
- **F33**: `team.Mailbox` 提供 `Write(agentID, msg)` / `Read(agentID) ([]Message, error)` / `MarkRead(agentID, []int)` 接口
  - `Write`:抢 `<TeamConfigDir>/mailbox/<agentID>.lock`(`O_CREATE|O_EXCL`),失败 5-100ms 随机抖动重试 10 次;持锁超 10 秒视为 stale(`Stat().ModTime` 判定)直接删 lock 重试;成功后 read-modify-write,`os.WriteFile` 原子替换
  - 广播 `to="*"` 时,Write 对 Team 内除发件人外所有成员的 mailbox 各 Write 一次
- **F34**: `SendMessage.Execute`——
  1. 校验调用者在 Team 内
  2. 解析 `to`:若 `"*"` 走广播;否则通过 `agentNameRegistry.Resolve(to)` 取 agentID(name 优先,失败按 agentID 直查);解析不到 error
  3. `plan_approval_response` 仅 Lead 可发,否则 error
  4. `shutdown_response` 只能发给 Lead,否则 error
  5. 调 `Mailbox.Write`
  6. 取目标的 `BackendType` 与 `PaneID`,若是 Pane 后端调 `backend.Wake(paneID)`
  7. 若目标 agentID 已 stop(in-process 后端):触发续写(F45)
  8. 返回 `{"delivered_to":["<agentID>"],"timestamp":<ts>}`

### Agent 名称注册表- **F35**: `team.AgentNameRegistry` 字段——`mu sync.Mutex`、`byName map[string]string`(name → agentID)、`byID map[string]string`(agentID → name,反查)
- **F36**: 接口 `Register(name, agentID string)`、`Unregister(name string)`、`Resolve(nameOrID string) (agentID string, ok bool)`、`NameOf(agentID string) (name string, ok bool)`
- **F37**: 注册时机——`Agent` 工具 spawn 队员时(F25 step 10);`AgentTool` 的 `name` 参数非空时(ch13 已有,本章统一这套 registry,替换 `task.Manager.byName` 的内部 map)
- **F38**: 命名冲突——后注册的覆盖前注册的(README 称「弱引用,后启动覆盖前面的弱引用」)

### 队员系统提示词附录- **F39**: 在子 Agent 的 SystemPrompt 后追加(若 spawn 进 Team)以下文本(无变量):
  ```
  IMPORTANT: You are running as an agent in a team.
  Just writing a response in text is not visible to others
  on your team - you MUST use the SendMessage tool.
  The user interacts primarily with the team lead.
  Your work is coordinated through the task system
  and teammate messaging.
  ```
- **F39a**: 所有 Team 队员(三种后端共有)一律以 `DontAsk=true` 启动,**覆盖角色定义里的 `permissionMode`**。理由:队员没有可交互的 TUI 接 `ApprovalRequest`(in-process 走 task.Manager 聚合事件不响应、Pane 子进程更没有 TUI),Ask 工具会无人应答地永远阻塞。队员的安全边界由 allowed 工具集 + Worktree 隔离 + Plan 模式控制,不靠逐次 ask 弹窗(子进程没人在看)。
- **F40**: 在 spawn 时把 `<team-context>` 注入子 Conv 的首条 system reminder:
  ```
  <team-context>
  team: <teamName>
  你的成员名: <memberName>
  你的 agent_id: <agentID>
  worktree 目录: <worktreePath>
  当前团队成员: <name1>(<role1>), <name2>(<role2>) ...
  </team-context>
  ```

### 邮箱读取与消息注入- **F41**: 子 Agent 的 Loop 在每轮请求 LLM **之前**先调 `Mailbox.Read(agentID)`;若有未读消息,构造 `<incoming-messages>` system reminder 追加到本轮请求的 systemReminders,然后调 `MarkRead`
- **F41a**: Lead 侧不通过 ctx hook 自动读 mailbox(Lead 没有 `TeammateContext`),而是由 TUI 在 Init 启动后台 goroutine `consumeLeadMail`(实现于 `internal/tui/tasks.go`):
  - 每秒调 `Manager.PollLeadMailboxes()`,遍历所有 Team 的 `<configDir>/mailbox/lead.json` 读未读消息,标 read,返回 `[]LeadMessage`
  - 把这批消息渲染成 `<team-update>` reminder(与 `<incoming-messages>` 不同,Lead 视角语义更清晰;消息内容截断上限 8000 字符,允许队员的完整报告完整透传),调 `runtime.AppendReminders(...)` 推到 `PendingReminders`
  - **同时**往 `m.leadMailCh` 推一个信号(non-blocking,buffer=1 合并掉重复)
  - Lead 下一轮 Run 迭代头部 `buildReminder` 自动取出。**Lead 即便正在长 Run 中也能中途惊醒**——下一个 LLM 调用前就会看到队员更新
  - 这是 Pane 后端队员通知 Lead 的关键路径:in-process 队员还有 `task.Manager.SubscribeDone` → TUI `<task-notification>` 的额外路径,但 Pane 队员只能靠 mailbox + 本机制
- **F41b**: Lead idle 时的自动续推。TUI 通过 `waitForLeadMail(ch)` Cmd 阻塞在 `leadMailCh` 上,收到信号后转 `leadMailMsg` 给 Update:
  - 若 `m.state == stateIdle`,调 `beginAutonomousTurn`:合成一条 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."` 加入对话历史(用户在 scrollback 也看得见,清楚是系统通知触发而非自己输入),然后走 `beginTurn` 启 Run
  - 若 `m.state` 非 idle(stateStreaming/stateApproving):reminder 已经在 PendingReminders 里,Lead 当前 Run 的下一轮迭代头部自然取出,不需要主动 wake
  - 末尾 re-arm `waitForLeadMail(ch)` 让后续信号也能接住
  - 这避免了"队员都 idle 了,Lead 在 stateIdle 等用户输入,reminder 静默积累没人取"的卡死场景——这正是 ch15 协作 UX 的关键
- **F42**: `<incoming-messages>` 格式:
  ```
  <incoming-messages>
  收到 N 条新消息:
  [1] 来自 <from>(type=<type>,ts=<时间>): <summary>
      <content 前 200 字>
  [2] ...
  </incoming-messages>
  ```
- **F43**: 收到 `shutdown_request` 时,队员可在下一轮自主选择回复 `shutdown_response(approve=true)` 然后停止,或 `approve=false` 拒绝并附 reason(LLM 决策,不强制)
- **F44**: 收到 `plan_approval_response(approve=true)` 时,队员的权限模式自动切换到 Lead 当前模式(从 Team config 取);`approve=false` 时队员根据 `feedback` 调整重新发 Plan

### 队员空闲与续写- **F45**: 队员 `RunToCompletion` 自然结束时(`task.Manager.runTask` 完成路径):
  1. 调 `Team.SetMemberActive(memberName, false)`
  2. 给 Lead 邮箱写一条 `idle_notification`(`type="text", summary="<member> idle", content="agent <id> finished work, available for new tasks"`)
- **F46**: SendMessage 检测到目标 agentID 已 stop 且为 in-process 队员(`task.BackgroundTask.Status` 不是 `Running`):
  1. 从 `TeammateInfo.SessionDir` 反序列化 Conversation(`session.Load`)
  2. 调 `task.Manager.SendMessage(parentCtx, name, message)` 复用 ch13 已有续派接口
  3. `task.Manager.SendMessage` 重置 `Status=Running`,起新 goroutine 跑 `RunToCompletion(newMessage)`
  4. 续派前调 `Team.SetMemberActive(memberName, true)`
- **F47**: Pane 后端队员的续写——SendMessage 写邮箱后,目标 pane 内的 gcode 实例下一轮 Loop 自然读到消息;若 pane 已死(`tmux list-panes` 查不到 `paneID`),报错让 Lead 决定是否重新 spawn

### Plan 审批工作流- **F48**: `Agent` 工具 spawn 队员时,若 `planModeRequired=true`(来自 subagent.Definition 的新字段或 spawn 参数),把子 Agent 的初始 `permission.Mode` 设为 `plan`
- **F49**: 队员在 plan 模式下生成 Plan 后(通过常规 LLM 推理),用 `SendMessage(to="lead", type="text", summary="plan ready", content="<plan text>")` 发给 Lead——本期不强制结构化 Plan 类型(Lead 自行识别)
- **F50**: Lead 用 `SendMessage(to="<member>", type="plan_approval_response", payload={"approve":true|false,"feedback":"..."})` 回复
- **F51**: 队员收到 `plan_approval_response`:
  - `approve=true`:从 Team config 读 Lead 当前 `PermissionMode`(本期固定 `default`),切到该模式继续执行 plan
  - `approve=false`:把 `feedback` 当作新的用户消息加入对话,重新进入 plan 模式

### Coordinator Mode- **F52**: 提供 `coordinator.IsEnabled() bool` 函数:
  ```go
  func IsEnabled() bool {
      if !feature.Has("COORDINATOR_MODE") {
          return false
      }
      return envTruthy(os.Getenv("GCODE_COORDINATOR_MODE"))
  }
  ```
  `feature.Has` 通过 `internal/config` 读 `features.coordinatorMode` 字段;`envTruthy` 接受 `"1"` / `"true"` / `"yes"`(大小写不敏感)
- **F53**: Coordinator Mode 允许工具白名单常量:
  ```go
  var COORDINATOR_ALLOWED_TOOLS = []string{
      "Agent", "TeamCreate", "TeamDelete",
      "TaskCreate", "TaskGet", "TaskList", "TaskUpdate",
      "SendMessage",
      "read_file", "glob", "grep", "bash",
  }
  ```
- **F54**: Lead 启动时(`tui` 主循环创建 Agent 后),若 `coordinator.IsEnabled()`:
  1. 把 Lead 的 allowed tools 设为 `COORDINATOR_ALLOWED_TOOLS`(调 `Agent.SetAllowedTools` 已有接口)
  2. 在 SystemPrompt 后追加 coordinator 提示词(F55)
  3. TUI 状态栏显示 `[COORDINATOR]` 模式标签
- **F55**: Coordinator 系统提示词追加在 SystemPrompt 末尾,核心是"四阶段 + 派完不许自己干"纪律。最终文案见 [internal/coordinator/coordinator.go:SystemPromptSuffix](../../internal/coordinator/coordinator.go),关键约束:
  - **派完队员就停手等汇报**:派出 Agent / SendMessage 后**禁止**立刻调 read_file / glob / grep / bash 自己探索;**禁止**用 sleep / TaskList 轮询凑时间。`task.Manager` 完成时自然推送 `<task-notification>` reminder,Lead 下一轮被唤醒后再继续
  - 唯一该做的事:发一行总结"已派 N 名队员探索 X,等结果",让本轮结束
  - 允许自己用 read_file/glob/grep 的场景仅限:Research 第一次目标定位;Synthesis 阶段读**队员产出的报告文件**;Verification 阶段 git diff / git status 等收敛操作

  这段纪律是为了对抗"LLM 派完队员后等不及自己 glob 代码库重复劳动"的常见行为——纯 prompt 引导,不强制(LLM 偶尔仍会越线,弱模型尤甚)。

### 收敛阶段- **F56**: 收敛由 LLM 推理驱动,**不提供专门的 merge 工具**——Lead(无论是否 Coordinator Mode)在所有任务 `completed` 后,自主用 Bash 跑:
  ```bash
  git merge worktree-team-<sanitizedTeam>+<member> --no-ff -m "merge: <member>"
  ```
- **F57**: 冲突解决也由 Lead 推理——Lead 用 `read_file` 看冲突文件、`edit_file`(非 Coordinator Mode)或 `bash`(Coordinator Mode)写入解决方案、`bash` 跑 `git add` + `git commit`
- **F58**: 回滚——Lead 判断搞不定时,自主调 `bash` 跑 `git merge --abort`,然后给用户报告冲突文件 + 队员 worktree 路径;**不删队员 worktree**### TUI Slash 命令- **F59**: `/team list`——遍历 `Manager.teams`,每行 `<name>  <backend>  <member_count> 成员  [<active>/<total>] 活跃`
- **F60**: `/team info <name>`——展示 Team 详情:配置路径、各成员的 name/agentID/backend/worktreePath/IsActive/任务计数
- **F61**: `/team delete <name> [--force]`——调 `Manager.Delete(name, force)`
- **F62**: `/team kill <member>`——查到 member 所属 Team,调对应 backend.Kill,然后 `RemoveMember`

### 持久化与恢复- **F63**: `~/.gcode/teams/<sanitizedName>/config.json` 结构:
  ```json
  {
    "name": "...",
    "sanitized_name": "...",
    "lead_agent_id": "lead",
    "backend": "tmux",
    "description": "",
    "created_at": 1234567890,
    "members": [
      {
        "name": "alice",
        "agent_id": "agent-a1b2c3d",
        "agent_type": "worker",
        "model": "",
        "worktree_path": "/abs/path/.gcode/worktrees/team-foo+alice",
        "branch": "worktree-team-foo+alice",
        "backend_type": "tmux",
        "pane_id": "%5",
        "is_active": null,
        "plan_mode_required": false,
        "session_dir": "/abs/path/.gcode/sessions/<id>"
      }
    ]
  }
  ```
  所有写操作原子(先写 `.tmp` 再 `Rename`),受 `Team.mu` 保护。**跨进程**(Pane 后端)下,Lead 与子进程是不同进程的不同 Team 内存对象——`AddMember` 与 `SetMemberActive` 在加锁后**先 `reloadFromDiskLocked` 重读 disk Members**再改写+ atomic save(F19c)
- **F64**: gcode 启动时(`team.NewManager`)扫描所有 Team 目录:
  - 解析 `config.json`,失败的目录跳过并 stderr 警告
  - **不**自动恢复 in-process 队员(进程重启后 in-process 队员状态丢失,IsActive 视为 false)
  - Pane 队员根据 `pane_id` 探测后端是否仍在(`tmux has-session` / `it2 list-panes`),不在的 IsActive 标 false
- **F65**: 队员 session 沿用 ch12 session 持久化机制,路径 `<projectRoot>/.gcode/sessions/<id>/conversation.jsonl`;Team 删除时一并删除
- **F66**: `Manager.Delete(name, force=true)` 步骤(顺序重要):
  1. 持锁,校验 `force` 或全员 IsActive=false
  2. 对每个非 lead 成员:用 `BackendNew` 解析其 `BackendType` 拿 `Backend` 实例,调 `Backend.Kill(paneID, agentID)` 杀掉 pane(tmux/iterm2)或 cancel goroutine(in-process);Pane 子进程检测到 mailbox 目录消失会自行优雅退出兜底
  3. 调 `cleanupMemberResources` 删 session 目录与 worktree
  4. `os.RemoveAll(team.ConfigDir)` 删整个 Team 目录
  5. 从 Manager 的 in-memory map 移除

## 非功能需求- **N1**: 主 Agent 平时(未 TeamCreate)看到的工具列表保持稳定——`TeamCreate` / `TeamDelete` 总是可见;`Agent` 工具的 `team_name` 参数对模型可见但仅在调用时校验
- **N2**: 协作工具(TaskCreate 等)仅在队员上下文出现,主 Agent 与普通 SubAgent 看不到——通过 `ApplyAgentToolFilter` 在 spawn 时收窄
- **N3**: 邮箱写入对所有后端共用一套并发安全机制(文件锁);in-process 多 goroutine 写同一 mailbox 也由文件锁串行
- **N4**: 所有 Team 状态变更受 `Team.mu` 保护;Team 之间互不相关,各自一把锁;`Manager.mu` 仅保护 `teams` map
- **N5**: 后端 Spawn / Kill 调用不持 `Team.mu`(避免长锁);只在更新 `Members` 时短暂持锁
- **N6**: 与 ch04~ch14 既有测试零破坏——`go test ./...` 全绿
- **N7**: 中文友好——错误消息、TUI 输出、coordinator 提示词全部中文(对齐 gcode 其他模块风格);代码注释中文
- **N8**: Coordinator Mode 一旦启用,Lead 不可在运行时解锁(避免 LLM 被注入后自行解锁);取消的唯一方式是退出 gcode 重启
- **N9**: 权限沙箱(`internal/permission/sandbox.go`)允许写入项目根**之外**的 `/tmp` 与 macOS 真实路径 `/private/tmp` 作为系统临时目录白名单。理由:工具脚本和队员经常需要 `/tmp` 做中转文件,严格限定在项目根内会导致大量正常用法被沙箱误杀。这一开放对 file-class 工具(read_file / write_file / edit_file)生效;bash 走 exec-class 权限,本来就不受沙箱约束

## 不做的事

- 跨 gcode 进程的 Team 共享(同一仓库同一时刻只支持一个 gcode 实例操作活跃 Team)
- 跨机器分布式 Team
- 队员之间实时流式通信(走 mailbox 文件 + 轮询/Wake,不走 socket)
- 复杂任务依赖约束(优先级、deadline、SLA)
- 任务自动分配(Lead 与队员都靠 LLM 推理领任务,系统不做调度)
- 队员的细粒度资源限额(token 上限、超时硬限制)
- Plan 审批的结构化 Plan 类型(本期 Plan 文本就是 SendMessage content,Lead 自行识别)
- Windows 平台特殊适配(iTerm2 后端仅 macOS;tmux 在 WSL 可用但不保证;本期以 macOS / Linux 为主)
- Coordinator Mode 的运行时解锁与重新进入
- 跨 Team 寻址(SendMessage 只能在同一 Team 内寻址)
- 插件来源的 Team 后端

## 验收标准- **AC1**: `team.NewManager` 在 `~/.gcode/teams/` 不存在时自动创建;已有时正确扫描子目录还原 `teams` map
- **AC2**: `Manager.Create("refactor auth", "")` 把 `"refactor auth"` sanitize 为 `"refactor-auth"`,在 `~/.gcode/teams/refactor-auth/config.json` 落地,`backend` 字段反映 `detectBackend` 结果
- **AC3**: 同名 Team 二次 Create 自动后缀 `-2`,目录与 sanitized_name 都生效
- **AC4**: `Manager.Delete(name, false)` 在有 `IsActive!=false` 成员时返回 `ErrTeamHasActiveMembers`,目录仍在
- **AC5**: `Manager.Delete(name, true)` 删 Worktree、删 session 目录、删 ConfigDir
- **AC6**: `detectBackend()` 在 `$TMUX` 设置时返回 `tmux`;未设但 `$TERM_PROGRAM==iTerm.app` 且 `it2` 可执行返回 `iterm2`;都无但 `tmux` 二进制在 PATH 返回 `tmux`;否则 `in-process`
- **AC7**: `Agent` 工具带 `team_name="<existing>"` 时,在 `.gcode/worktrees/team-<sanitized>+<member>/` 落地 Worktree、调对应 Backend.Spawn 并在 `team.members` 里出现该成员;不带 `team_name` 时维持 ch13 原行为
- **AC8**: in-process 后端队员的 `Agent` 工具调用 `team_name` 参数被拦截,返回 `ErrInProcessTeammateNoSpawn`
- **AC9**: 协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage` 在主 Agent 工具列表里**不**可见;在 Team 队员的工具列表里**可见**
- **AC10**: `TaskCreate` 落 `<TeamConfigDir>/tasks.json`,`TaskUpdate(taskID, addBlockedBy=[id])` 正确更新双向 `blocked_by` / `blocks` 关系
- **AC11**: `TaskList(status="pending")` 返回的任务带 `is_ready` 字段,反映其 `blocked_by` 是否全部 `completed`
- **AC12**: `SendMessage(to="alice", summary="hi", message="hello")` 在 `<TeamConfigDir>/mailbox/<aliceAgentID>.json` 追加一条 unread 消息
- **AC13**: `SendMessage(to="*", ...)` 广播给 Team 内除发件人外所有成员;每人邮箱各得一条
- **AC14**: 并发 10 个 goroutine 同时向同一 mailbox `Write`,最终 10 条消息全部落盘且无丢失/无截断(集成测试)
- **AC15**: mailbox lock 文件 `Stat().ModTime()` 超过 10 秒时,新的 Write 会清掉旧 lock 并继续(集成测试)
- **AC16**: 队员 LLM 调用前,未读消息以 `<incoming-messages>` reminder 注入 systemReminders;调用后标记 read(单测断言)
- **AC17**: 队员 `RunToCompletion` 自然结束后,`Team.config.json` 里该成员 `is_active=false`,Lead mailbox 收到 `summary="<member> idle"` 消息
- **AC18**: `SendMessage(to="alice", message="new task")` 当 alice 已 stop 时,从其 SessionDir 恢复 Conv 并续派(in-process 后端,task.Manager 状态从 Cancelled/Completed 回到 Running)
- **AC19**: `Agent(team_name="t", subagent_type="planner", planModeRequired=true, ...)` spawn 后,该队员初始权限模式为 `plan`
- **AC20**: Lead 发 `SendMessage(to="planner", type="plan_approval_response", payload={"approve":true})` 后,planner 队员下一轮权限模式切回 `default`
- **AC21**: `feature.Has("COORDINATOR_MODE")=true` 且 `GCODE_COORDINATOR_MODE=1` 时,Lead 的 allowed tools 收窄为 `COORDINATOR_ALLOWED_TOOLS`,`write_file` / `edit_file` 不在其中;TUI 状态栏显示 `[COORDINATOR]`
- **AC22**: Coordinator Mode 关闭时,Lead 工具列表与 ch13 一致(`write_file` / `edit_file` 可见)
- **AC23**: tmux 后端 spawn 后,`tmux list-panes` 看到新 pane,pane 内 gcode 实例启动并连接到该 Team
- **AC24**: tmux 后端 `Wake(paneID)` 通过 `tmux send-keys` 触发目标 pane 输入(集成测试可观察 pane 内容)
- **AC25**: in-process 后端队员与主 Agent 在同一进程内运行,共享 `task.Manager`,但有独立 `WithCwd(worktreePath)`
- **AC26**: `/team list` slash 命令输出含所有 Team 摘要;`/team info <name>` 输出成员详情;`/team delete <name>` 调 Manager.Delete
- **AC27**: 项目编译无错误 `go build ./...`、所有单元测试通过 `go test ./...`、`go vet ./...` 通过
- **AC28**: tmux 实跑(端到端):
  - 步骤 1:在 tmux 会话内启动 `gcode`
  - 步骤 2:输入 prompt 让主 Agent 调 `TeamCreate(team_name="demo")`,看到状态栏出现 team 标识,`~/.gcode/teams/demo/config.json` 落地
  - 步骤 3:Agent 调 `Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="在 worktree 里 echo hello > /tmp/test_alice.txt")`
  - 步骤 4:观察 tmux 新增 pane,pane 内出现 gcode 子实例;`.gcode/worktrees/team-demo+alice/` 目录创建;`/tmp/test_alice.txt` 文件创建,内容 `hello`
  - 步骤 5:`/team info demo` 显示 alice 成员
  - 步骤 6:Lead 调 `SendMessage(to="alice", summary="ping", message="再写一行 world 到 /tmp/test_alice.txt")`,观察 alice pane 被唤醒(send-keys 触发)、`/tmp/test_alice.txt` 多一行 `world`
  - 步骤 7:`/team delete demo --force`,worktree 和 team 目录清空
- **AC29**: in-process 后端实跑(端到端,不依赖 tmux):
  - 步骤 1:`unset TMUX TERM_PROGRAM`,启动 `gcode`(自动 fallback in-process)
  - 步骤 2:主 Agent 调 `TeamCreate("inproc")`,创建后端为 `in-process`
  - 步骤 3:`Agent(team_name="inproc", name="bob", prompt="...")` 在同进程 goroutine 启动 bob
  - 步骤 4:bob 完成后 `Team.config.json` 标记 `is_active=false`、Lead mailbox 收到 idle 消息
  - 步骤 5:Lead 调 `SendMessage(to="bob", message="再做一件事")`,bob 从 SessionDir 恢复对话上下文继续
- **AC30**: Coordinator Mode 实跑——`GCODE_COORDINATOR_MODE=1` 启动 gcode,主 Agent 的 `write_file` 工具调用被拒绝(IsError=true);`bash git merge` 调用允许
````

````markdown
# Agent Team Plan## 架构概览

本章引入 `internal/team` 顶层包,把 ch13 SubAgent 的「子 Agent」扩展为「Team 队员」。整体分四层:

1. **数据模型层**(`team/types.go` + `team/manager.go` + `team/persistence.go`)——Team、TeammateInfo 数据结构与持久化
2. **后端层**(`team/backend/`)——`Backend` 接口与三种实现 tmux / iterm2 / inprocess,屏蔽 spawn 差异
3. **协作层**(`team/mailbox/`、`team/registry/`、`team/tasks/`)——邮箱(含文件锁)、AgentNameRegistry、共享任务列表
4. **工具与集成层**(`team/tools/` + `agent` 包扩展 + `coordinator` 包)——5 个协作工具 + `Agent` 工具的 `team_name` 分支 + Coordinator Mode

Lead 仍是 `tui.Model.MainAgent()`——本期 Lead 没有独立类型,通过 `coordinator.IsEnabled()` 在启动时收窄其工具集即可。

依赖方向(单向):
```
tui  ──→  agent  ──→  team  ──→  team/{backend,mailbox,registry,tasks,tools}
                       └──→  worktree(ch14)、task(ch13)、session(ch12)、subagent(ch13)
```
`team` 不反向依赖 `agent` 包(避免环);`agent` 通过新增的 `TeamHook` 接口注入 team 行为。

## 核心数据结构### `team.Team`

```go
type Team struct {
    mu sync.Mutex

    Name          string         // 用户给的原始名
    SanitizedName string         // 经 sanitize 后用于路径,Team 主键
    LeadAgentID   string         // 固定 "lead"(本期 Lead = 主 Agent)
    Backend       BackendType    // 全 team 默认后端;可被 member 覆盖
    Description   string
    CreatedAt     time.Time
    Members       []*TeammateInfo

    // 派生路径(不持久化)
    ConfigDir  string
    ConfigPath string  // <ConfigDir>/config.json
    TasksPath  string  // <ConfigDir>/tasks.json
    MailboxDir string  // <ConfigDir>/mailbox/
}
```

### `team.TeammateInfo`

```go
type TeammateInfo struct {
    Name             string     `json:"name"`
    AgentID          string     `json:"agent_id"`
    AgentType        string     `json:"agent_type"`        // "" 表 Fork
    Model            string     `json:"model"`             // "" 表 inherit
    WorktreePath     string     `json:"worktree_path"`     // 绝对路径
    Branch           string     `json:"branch"`
    BackendType      BackendType `json:"backend_type"`
    PaneID           string     `json:"pane_id"`           // tmux pane id / iterm2 split id / "" for in-process
    IsActive         *bool      `json:"is_active"`         // nil/true 活跃,false 空闲;不存在视为终止
    PlanModeRequired bool       `json:"plan_mode_required"`
    SessionDir       string     `json:"session_dir"`       // 绝对路径
}
```

### `team.Manager`

```go
type Manager struct {
    mu       sync.Mutex
    teams    map[string]*Team   // 按 SanitizedName 索引
    homeDir  string
    wtMgr    *worktree.Manager
    taskMgr  *task.Manager
    registry *registry.AgentNameRegistry
}
```

### `team.BackendType`

```go
type BackendType string

const (
    BackendTmux      BackendType = "tmux"
    BackendIterm2    BackendType = "iterm2"
    BackendInProcess BackendType = "in-process"
)
```

### `team/backend.Backend`

```go
type Backend interface {
    Type() team.BackendType
    Spawn(ctx context.Context, req SpawnRequest) (paneID string, err error)
    Wake(ctx context.Context, paneID string) error
    Kill(ctx context.Context, paneID string) error
}

type SpawnRequest struct {
    TeamName         string
    MemberName       string
    AgentID          string
    WorktreePath     string
    SessionDir       string
    AgentType        string
    Model            string
    InitialPrompt    string
    PlanModeRequired bool

    // in-process 专用——同进程后端直接复用这两个对象
    SubAgent *agent.Agent
    Conv     *conversation.Conversation
    TaskMgr  *task.Manager
}
```

### `team/mailbox.Message` / `Box`

```go
type MessageType string

const (
    TypeText                MessageType = "text"
    TypeShutdownRequest     MessageType = "shutdown_request"
    TypeShutdownResponse    MessageType = "shutdown_response"
    TypePlanApprovalResponse MessageType = "plan_approval_response"
)

type Message struct {
    From      string                 `json:"from"`
    To        string                 `json:"to"`
    Type      MessageType            `json:"type"`
    Summary   string                 `json:"summary"`
    Content   string                 `json:"content"`
    Payload   map[string]interface{} `json:"payload,omitempty"`
    Timestamp int64                  `json:"timestamp"`
    Read      bool                   `json:"read"`
}

type Box struct {
    dir string // <TeamConfigDir>/mailbox/
}

func (b *Box) Write(agentID string, msg Message) error
func (b *Box) Read(agentID string) ([]Message, error)
func (b *Box) MarkRead(agentID string, indices []int) error
```

文件锁机制内置在 `Box` 内,所有公开方法都走锁。

### `team/registry.AgentNameRegistry`

```go
type AgentNameRegistry struct {
    mu     sync.Mutex
    byName map[string]string  // name → agentID
    byID   map[string]string  // agentID → name
}

func (r *AgentNameRegistry) Register(name, agentID string)
func (r *AgentNameRegistry) Unregister(name string)
func (r *AgentNameRegistry) Resolve(nameOrID string) (string, bool)
func (r *AgentNameRegistry) NameOf(agentID string) (string, bool)
```

注意:本章把 `task.Manager.byName` 替换/委托给这套 registry——`task.Manager` 改为持一个 `*AgentNameRegistry` 引用。

### `team/tasks.Store`

```go
type Status string

const (
    StatusPending    Status = "pending"
    StatusInProgress Status = "in_progress"
    StatusCompleted  Status = "completed"
    StatusBlocked    Status = "blocked"
)

type Task struct {
    ID          string   `json:"id"`
    Title       string   `json:"title"`
    Description string   `json:"description"`
    Status      Status   `json:"status"`
    Assignee    string   `json:"assignee"`
    BlockedBy   []string `json:"blocked_by"`
    Blocks      []string `json:"blocks"`
    CreatedAt   int64    `json:"created_at"`
    UpdatedAt   int64    `json:"updated_at"`
}

type Store struct {
    path string
    mu   sync.Mutex
}

func (s *Store) Create(t Task) (string, error)
func (s *Store) Get(id string) (Task, error)
func (s *Store) List(filter Filter) ([]Task, error)
func (s *Store) Update(id string, patch Patch) error
```

### `coordinator` 包

```go
package coordinator

func IsEnabled() bool
func AllowedTools() []string
func SystemPromptSuffix() string
```

仅 3 个纯函数,无状态。

## 模块设计### `internal/team`(顶层)**职责:** Team / TeammateInfo / Manager 数据结构与持久化,跨子包的协调入口。
**对外接口:** `NewManager(...) (*Manager, error)`、`Manager.Create/Get/Delete`、`Team.AddMember/SetMemberActive/RemoveMember`
**依赖:** `worktree`、`task`、`session`、`team/backend`、`team/mailbox`、`team/registry`、`team/tasks`

### `internal/team/backend`**职责:** 屏蔽 tmux / iterm2 / in-process spawn 差异。
**对外接口:** `Backend` 接口、`DetectBackend() team.BackendType`、`NewBackend(t team.BackendType, deps) Backend`
**依赖:** `team`(取常量)、`agent` 与 `task`(in-process 实现用)

注意:`backend` 包反向依赖 `agent` 会成环。解决:`in-process` 实现走「接口适配」——`backend.Spawn` 接收 `SpawnRequest` 中的 `SubAgent any`(interface{}),由调用方(`team` 包)预先构造好;`backend` 包只做调度,不知道 `agent.Agent` 类型。或者把 `in-process` 实现单独提到 `team/backend/inprocess`,允许它依赖 `agent`,而 `team/backend/tmux` / `iterm2` 不依赖。

**采用方案:** 三种后端各一个子包(`tmux/` / `iterm2/` / `inprocess/`),每个独立实现 `Backend` 接口,工厂函数 `New(...)` 接收所需依赖。`inprocess` 子包依赖 `agent` 包没问题(`agent` 在更低层)。

### `internal/team/mailbox`**职责:** 邮箱文件 + 文件锁的读写。
**对外接口:** `Box.Write/Read/MarkRead`、`Message` 类型
**依赖:** 仅 stdlib(`os`、`encoding/json`、`sync`)

### `internal/team/registry`**职责:** Agent name ↔ agentID 双向映射。
**对外接口:** `Register/Unregister/Resolve/NameOf`
**依赖:** 仅 stdlib

### `internal/team/tasks`**职责:** 共享任务列表的 CRUD + 依赖图维护。
**对外接口:** `Store.Create/Get/List/Update`、`Task`、`Filter`、`Patch` 类型
**依赖:** 仅 stdlib

### `internal/team/tools`**职责:** 5 个协作工具实现(TaskCreate、TaskGet、TaskList、TaskUpdate、SendMessage)+ 2 个 Team 管理工具(TeamCreate、TeamDelete)。
**对外接口:** 每个工具一个构造函数 `NewXxxTool(mgr *team.Manager) tool.Tool`
**依赖:** `tool`、`team`、`team/{mailbox,registry,tasks}`

### `internal/coordinator`**职责:** Coordinator Mode 的开关检测、工具白名单、系统提示词。
**对外接口:** `IsEnabled() bool`、`AllowedTools() []string`、`SystemPromptSuffix() string`
**依赖:** `config`(读 feature flag)

### `agent` 包扩展

- 新增 `agent.TeamHook` 接口:
  ```go
  type TeamHook interface {
      // SpawnTeammate 让 Agent 工具委托给 Team Manager 处理 team_name 分支。
      // 返回 finalText(立即返回 task_id JSON 描述)。
      SpawnTeammate(ctx context.Context, req TeamSpawnRequest) (string, error)
      // IsTeammateContext 判断 ctx 是否在某队员的执行上下文中(用于拦截嵌套 spawn)。
      IsTeammateContext(ctx context.Context) (memberName, teamName string, ok bool)
  }
  ```
- `AgentTool` 持一个 `teamHook TeamHook` 字段(可选,nil 时降级为 ch13 行为)
- `Agent.Execute` 在 `team_name != ""` 时调 `teamHook.SpawnTeammate`

### `task` 包扩展

- `task.Manager` 持一个 `*registry.AgentNameRegistry` 引用(原 `byName` 字段废弃,改委托)
- `task.Manager.SendMessage` 复用——Team 模块续派直接调它

### `tui` 包扩展

- `tui.Model` 新增字段 `teamMgr *team.Manager`
- 注入 `/team` 系列 slash 命令(`internal/command/builtin_team.go`)
- 状态栏新增 `[COORDINATOR]` 标签(若 `coordinator.IsEnabled()`)

## 模块交互### TeamCreate 调用路径

```
LLM 调 TeamCreate(team_name="demo")
  ↓
tools.TeamCreate.Execute
  ↓
team.Manager.Create(ctx, "demo", "")
  ↓
1. sanitize("demo") → "demo"
2. detectBackend() → "tmux"
3. mkdir ~/.gcode/teams/demo/
4. mkdir ~/.gcode/teams/demo/mailbox/
5. 写 config.json(原子)
6. team.Members = [{Name:"lead",AgentID:"lead",IsActive:nil}]
7. teams["demo"] = team
  ↓
返回 {"team_name":"demo","backend":"tmux","config_path":"..."}
```

### Agent(team_name=...) spawn 路径

```
LLM 调 Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="...")
  ↓
agent.AgentTool.Execute
  ↓
判断 team_name != "" → 委托给 teamHook.SpawnTeammate
  ↓
team.SpawnTeammate(req)
  ↓
1. Manager.Get("demo") 取 Team
2. 校验调用者权限(in-process 队员不许 spawn,Pane 队员可以但 team_name 屏蔽)
3. catalog.Resolve(agentType) 取 subagent.Definition
4. memberName = req.Name(或自动 alice/agent-a1b2c3)
5. wtMgr.Create(ctx, "team-demo/"+memberName, "HEAD", false) → worktree
6. 申请 sessionDir(util 函数,沿用 ch12 格式)
7. 构造 SpawnRequest
8. 若 backend=in-process:
   - 构造 subAgent(NewSessionRuntime + WithCwd + WithAllowedTools 含协作工具)
   - 构造 subConv(NewFromMessages 走 Fork 路径,或空 Conv 走定义式)
   - 注入 <team-context> reminder
   - 注入 SystemPrompt 附录(F39)
   - SpawnRequest.SubAgent / Conv / TaskMgr 填好
9. backend.Spawn(ctx, req) → paneID
10. registry.Register(memberName, agentID)
11. team.AddMember(TeammateInfo{...})
  ↓
返回 {"member_name":"alice","agent_id":"...","worktree":"...","backend":"tmux"}
```

### SendMessage 调用路径

```
LLM 调 SendMessage(to="alice", summary="hi", message="hello")
  ↓
tools.SendMessage.Execute
  ↓
1. 取调用者所属 Team(从 ctx 中 TeammateContext 取,或主 Agent 走 active team)
2. resolve to:
   - "*" → 广播
   - 否则 registry.Resolve(to) → agentID
3. 校验消息类型权限(plan_approval_response 仅 Lead,shutdown_response 仅发给 Lead)
4. 对每个目标 agentID:
   - mailbox.Write(agentID, msg)
   - 取 TeammateInfo.PaneID 与 BackendType
   - 若 Pane 后端:backend.Wake(paneID)
   - 若目标已 stop(in-process,task.Manager.Get(agentID).Status != Running):
     - 从 SessionDir 恢复 Conv
     - taskMgr.SendMessage(parentCtx, name, message) 续派
5. 返回 {"delivered_to":["agent-xxx"],"timestamp":...}
```

### 队员 Loop 内邮箱注入

```
队员的 agent.Agent.Run 每轮迭代开头(在调 LLM 前):
  ↓
读 ctx 中的 TeammateContext(包含 *Mailbox、AgentID)
  ↓
unread := mailbox.Read(agentID)
  ↓
若 len(unread) > 0:
  reminder := buildIncomingMessagesReminder(unread)
  把 reminder 加入本轮 systemReminders
  mailbox.MarkRead(agentID, indices)
```

`agent.Agent` 已有 systemReminders 注入机制(ch05 / ch07 plan reminder 走同一通道);新增一种 reminder 来源即可。

### 队员 RunToCompletion 结束的通知

```
task.Manager.runTask goroutine 结束(完成 / 失败 / 取消)
  ↓
若该 task 关联到 Team 队员(通过 registry.NameOf(agentID) 反查 name → 查 team)
  ↓
team.SetMemberActive(memberName, false)
mailbox.Write(leadAgentID, Message{type:"text", summary:"<name> idle", ...})
backend.Wake(leadPaneID)  // 若 Lead 是 Pane 后端
```

需要在 `task.Manager.runTask` 的 defer 中加 hook,或者在 `team` 包注册一个回调到 task 包(走依赖反转)。**采用方案:** 在 `task.Manager` 新增 `OnTaskDone(func(taskID string))` 回调注册接口,`team` 包初始化时注册。

### Coordinator Mode 启用路径

```
main.go 启动时,在构造主 Agent 后:
  ↓
if coordinator.IsEnabled() {
  mainAgent.SetAllowedTools(coordinator.AllowedTools())
  mainAgent.AppendSystemPrompt(coordinator.SystemPromptSuffix())
  tui.Model.coordinatorMode = true
}
```

TUI 渲染 statusbar 时检测 `coordinatorMode` 添加 `[COORDINATOR]` 标签。

## 文件组织

```
internal/team/
├── doc.go                         — 包文档
├── types.go                       — Team / TeammateInfo / BackendType 等类型
├── manager.go                     — Manager(Create/Get/Delete/AddMember/SetMemberActive/RemoveMember)
├── persistence.go                 — 原子写 config.json,sanitize 函数
├── manager_test.go
├── spawn.go                       — SpawnTeammate 主流程(被 agent.TeamHook 调用)
├── spawn_test.go
├── feature.go                     — FORK_TEAMMATE feature flag 读取
├── backend/
│   ├── doc.go
│   ├── backend.go                 — Backend 接口、SpawnRequest 类型
│   ├── detect.go                  — DetectBackend()
│   ├── detect_test.go
│   ├── tmux/
│   │   ├── tmux.go                — Tmux Backend 实现
│   │   └── tmux_test.go
│   ├── iterm2/
│   │   ├── iterm2.go              — iTerm2 Backend 实现
│   │   └── iterm2_test.go
│   └── inprocess/
│       ├── inprocess.go           — InProcess Backend 实现
│       └── inprocess_test.go
├── mailbox/
│   ├── doc.go
│   ├── mailbox.go                 — Box 类型与 Read/Write/MarkRead
│   ├── lock.go                    — 文件锁机制(抢锁、重试、stale 处理)
│   └── mailbox_test.go
├── registry/
│   ├── registry.go                — AgentNameRegistry
│   └── registry_test.go
├── tasks/
│   ├── tasks.go                   — Task / Store
│   ├── filter.go                  — Filter/Patch + is_ready 计算
│   └── tasks_test.go
└── tools/
    ├── doc.go
    ├── team_create.go             — TeamCreate 工具
    ├── team_delete.go             — TeamDelete 工具
    ├── task_create.go
    ├── task_get.go
    ├── task_list.go
    ├── task_update.go
    ├── send_message.go
    ├── teammate_filter.go         — 队员专属工具白名单(注入到 ApplyAgentToolFilter)
    └── tools_test.go

internal/coordinator/
├── coordinator.go                 — IsEnabled/AllowedTools/SystemPromptSuffix
└── coordinator_test.go

internal/agent/
├── agent_tool.go                  — 修改:增加 team_name 参数与 TeamHook 委托
├── team_hook.go                   — 新建:TeamHook 接口定义、TeammateContext key
├── reminder.go                    — 修改(若需):新增 incoming-messages reminder 注入

internal/task/
├── manager.go                     — 修改:OnTaskDone 回调注册;改用 registry.AgentNameRegistry

internal/command/
└── builtin_team.go                — 新建:/team list/info/delete/kill 4 个命令

internal/tui/
├── tui.go                         — 修改:接收 teamMgr 参数;启动时检测 coordinator.IsEnabled
└── statusbar.go(若存在)          — 修改:渲染 [COORDINATOR] 标签

internal/config/
└── config.go                      — 修改:新增 Features.CoordinatorMode 字段、FORK_TEAMMATE 字段

cmd/gcode/
└── main.go                        — 修改:wire team.Manager,注册 7 个新工具,接入 coordinator
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Team 包归属 | `internal/team` 顶层 | 与 ch13 `subagent`、ch14 `worktree` 平级,职责清晰 |
| 后端三选一时机 | `DetectBackend` 在 `TeamCreate` 时一次性决定 | 与 README 一致:不做运行时回退,行为可预测 |
| 后端实现拆分 | 各一个子包 `tmux/iterm2/inprocess` | `inprocess` 需要依赖 `agent` 包,拆开避免污染其他 backend |
| Backend 接口 | 三方法 `Spawn/Wake/Kill` | 最小集;not Pause/Resume(本期不做) |
| Lead 表示 | 不引入独立类型,Lead = `tui.Model.MainAgent()` | 收窄改动;Coordinator Mode 在工具集层面区分 |
| 邮箱实现 | `<TeamConfigDir>/mailbox/<agentID>.json` + 同名 `.lock` | 跨进程通信现成方案;in-process 与 Pane 共用一套 |
| 锁文件参数 | `O_CREATE\|O_EXCL`,5-100ms 抖动 10 次,>10s 视 stale | README 明定;避免雪崩 |
| 任务存储 | `<TeamConfigDir>/tasks.json` 单文件 | Team 内任务量小(几十条),无需 DB;原子写 + 文件锁 |
| AgentNameRegistry 归属 | 独立 `team/registry` 包,`task.Manager` 委托 | 解耦;消除 ch13 `task.Manager.byName` 的局部状态 |
| `task.Manager` 改造 | 加 `OnTaskDone` 回调,Team 注册 | 依赖反转,避免 task 包反向依赖 team |
| Team 持久化原子性 | `<file>.tmp` + `os.Rename` | 与 ch14 worktree session、ch12 session 一致 |
| Worktree 命名 | `team-<sanitizedTeam>/<member>`(嵌套 slug,`/` → `+`) | 复用 ch14 嵌套 slug 能力;不污染顶层 worktree 命名空间 |
| Member SessionDir | 沿用 ch12 `<root>/.gcode/sessions/<id>/` 格式 | 复用 `session.NewWriter`,无需新机制;Team 删除时一并清理 |
| Coordinator 开启检测 | `feature.Has("COORDINATOR_MODE") && envTruthy(env)` | README 明定双锁;一次决定不允许运行时改 |
| Coordinator 工具白名单 | 硬编码常量,启动时直接 `SetAllowedTools` | LLM 无法解锁,安全边界清晰 |
| Plan 审批本期形态 | 文本 Plan + Lead 用 `plan_approval_response` 回复 | 不强制结构化 Plan 类型,降低实现成本 |
| Fork 队员 | 受 `FORK_TEAMMATE` flag 控制,默认关 | README 明定;避免默认带满上下文 |
| 收敛 merge | 不提供专用工具,Lead 用 Bash 自主跑 git | README 明定;LLM 解冲突 = 语义理解,这是 LLM 优势 |
| `Agent` 工具的 `team_name` 在 in-process 队员处可见性 | 参数对模型可见,但调用时拦截返回 error | 与其在 schema 层动态裁剪不如统一 schema + 运行时校验,缓存友好 |
| 队员 Loop 邮箱注入 | 复用 `agent.Agent` 既有 systemReminders 通道,新增一种 reminder 来源 | 不改 Loop 主流程,改动最小 |
| TUI Coordinator 标签 | 状态栏静态渲染 | 视觉提示,运行时不可改 |
| 多 Team 并存 | `Manager.teams` map 支持,但 spawn 时按 `team_name` 显式选 | 灵活;典型场景同一时刻一个活跃 Team |
| Team 删除时 Worktree 处理 | 调 `wtMgr.Remove(name, DiscardChanges:true)`,失败只警告 | 与 ch14 退出语义一致;`force=true` 才放行,无 force 时有活跃成员就拒删,有变更也保留(自动 cleanup 已处理) |
| 错误命名 | 自定义错误变量 `ErrTeamHasActiveMembers` / `ErrInProcessTeammateNoSpawn` 等 | 调用方可 `errors.Is` 判别 |
````

````markdown
# Agent Team Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `internal/team/doc.go` | 包文档 |
| 新建 | `internal/team/types.go` | Team / TeammateInfo / BackendType 等类型 |
| 新建 | `internal/team/persistence.go` | sanitize、原子写 |
| 新建 | `internal/team/manager.go` | Manager.Create/Get/Delete/AddMember/SetMemberActive/RemoveMember |
| 新建 | `internal/team/manager_test.go` | Manager 单测 |
| 新建 | `internal/team/spawn.go` | SpawnTeammate 主流程 |
| 新建 | `internal/team/spawn_test.go` | spawn 单测(in-process 路径) |
| 新建 | `internal/team/feature.go` | FORK_TEAMMATE flag 读取 |
| 新建 | `internal/team/mailbox/mailbox.go` | Box.Read/Write/MarkRead + Message 类型 |
| 新建 | `internal/team/mailbox/lock.go` | 文件锁机制 |
| 新建 | `internal/team/mailbox/mailbox_test.go` | 并发与 stale 锁测试 |
| 新建 | `internal/team/registry/registry.go` | AgentNameRegistry |
| 新建 | `internal/team/registry/registry_test.go` | 注册/解析/反查测试 |
| 新建 | `internal/team/tasks/tasks.go` | Task / Store / Filter / Patch |
| 新建 | `internal/team/tasks/tasks_test.go` | CRUD + 依赖关系测试 |
| 新建 | `internal/team/backend/backend.go` | Backend 接口 + SpawnRequest 类型 |
| 新建 | `internal/team/backend/detect.go` | DetectBackend |
| 新建 | `internal/team/backend/detect_test.go` | 检测逻辑测试 |
| 新建 | `internal/team/backend/tmux/tmux.go` | Tmux Backend |
| 新建 | `internal/team/backend/tmux/tmux_test.go` | tmux 命令构造测试 |
| 新建 | `internal/team/backend/iterm2/iterm2.go` | iTerm2 Backend |
| 新建 | `internal/team/backend/iterm2/iterm2_test.go` | iterm2 命令构造测试 |
| 新建 | `internal/team/backend/inprocess/inprocess.go` | InProcess Backend |
| 新建 | `internal/team/backend/inprocess/inprocess_test.go` | in-process spawn 集成测试 |
| 新建 | `internal/team/tools/team_create.go` | TeamCreate 工具 |
| 新建 | `internal/team/tools/team_delete.go` | TeamDelete 工具 |
| 新建 | `internal/team/tools/task_create.go` | TaskCreate 工具 |
| 新建 | `internal/team/tools/task_get.go` | TaskGet 工具 |
| 新建 | `internal/team/tools/task_list.go` | TaskList 工具 |
| 新建 | `internal/team/tools/task_update.go` | TaskUpdate 工具 |
| 新建 | `internal/team/tools/send_message.go` | SendMessage 工具 |
| 新建 | `internal/team/tools/teammate_filter.go` | 队员专属工具白名单 |
| 新建 | `internal/team/tools/tools_test.go` | 工具单测 |
| 新建 | `internal/coordinator/coordinator.go` | IsEnabled/AllowedTools/SystemPromptSuffix |
| 新建 | `internal/coordinator/coordinator_test.go` | 双锁测试 |
| 新建 | `internal/agent/team_hook.go` | TeamHook 接口 + TeammateContext key |
| 修改 | `internal/agent/agent_tool.go` | 增加 team_name 参数 + TeamHook 委托 + WithTeamHook 构造选项 |
| 修改 | `internal/agent/run_to_completion.go` 或 `agent.go` | Loop 头部注入 incoming-messages reminder |
| 修改 | `internal/task/manager.go` | 加 OnTaskDone 回调;改用 registry.AgentNameRegistry |
| 修改 | `internal/tool/filter.go` | 新增 TEAMMATE_ALLOWED_TOOLS,扩展 FilterParams 加 Teammate bool |
| 新建 | `internal/command/builtin_team.go` | /team list/info/delete/kill 4 个命令 |
| 修改 | `internal/tui/tui.go` 与相关文件 | 接收 teamMgr、coordinator 标签 |
| 修改 | `internal/config/config.go` | Features 字段新增 CoordinatorMode 与 ForkTeammate |
| 修改 | `cmd/gcode/main.go` | wire team.Manager / coordinator,注册 7 个工具 |
| 修改 | `.gcode/config.yaml` 示例 | 加示例 features 段(可选,不强制) |

## T1: 基础类型 — `internal/team/types.go`**文件:** `internal/team/types.go`
**依赖:** 无
**步骤:**
1. 定义 `package team`
2. 定义 `BackendType` 字符串类型与常量 `BackendTmux` / `BackendIterm2` / `BackendInProcess`
3. 定义 `Team` 结构体(F1):字段含 `mu sync.Mutex`、Name、SanitizedName、LeadAgentID、Backend、Description、CreatedAt、Members、派生路径字段(ConfigDir/ConfigPath/TasksPath/MailboxDir,有 json:"-")
4. 定义 `TeammateInfo` 结构体(F2),字段带 json tag
5. 定义包级错误变量 `ErrTeamNotFound` / `ErrTeamHasActiveMembers` / `ErrMemberExists` / `ErrMemberNotFound` / `ErrInProcessTeammateNoSpawn`

**验证:** `go build ./internal/team/...` 编译通过

## T2: sanitize 与原子写 — `internal/team/persistence.go`**文件:** `internal/team/persistence.go`
**依赖:** T1
**步骤:**
1. 实现 `Sanitize(name string) string`——只保留 `[a-zA-Z0-9._-]`,其他字符替换为 `-`,首尾去 `-`,空字符串返回 `""`
2. 实现 `atomicWriteJSON(path string, v any) error`——`marshalIndent` → 写 `<path>.tmp` → `os.Rename`
3. 实现 `readJSON(path string, v any) error`——`os.ReadFile` + `json.Unmarshal`,文件不存在返回 `os.IsNotExist` 兼容的 error

**验证:** 写一个简单 sanitize 测试断言 `Sanitize("foo bar/baz")=="foo-bar-baz"`

## T3: Manager 与持久化 — `internal/team/manager.go`**文件:** `internal/team/manager.go`
**依赖:** T1, T2
**步骤:**
1. 定义 `Manager` 结构体(F3)
2. 实现 `NewManager(homeDir, projectRoot string, wtMgr *worktree.Manager, taskMgr *task.Manager, reg *registry.AgentNameRegistry) (*Manager, error)`(F4)
   - 创建 `<homeDir>/.gcode/teams/` 目录
   - 扫描子目录,逐个读 `config.json`(失败 stderr 警告并跳过)
   - 反序列化后填充派生路径字段
3. 实现 `Manager.Get(name string) (*Team, bool)`
4. 实现 `Manager.List() []*Team`(按创建时间排序)
5. 实现 `Manager.Create(ctx, name, description string) (*Team, error)`(F5)
   - sanitize + 同名冲突 `-2`/`-3` 后缀
   - 取 `DetectBackend()`(暂时硬编码 `BackendInProcess`,后面 T11 接 detect)
   - 创建 ConfigDir、MailboxDir
   - 注册 Lead 成员
   - atomicWriteJSON
6. 实现 `Manager.Delete(ctx, name string, force bool) error`(F7 + F66):
   - 持锁、找到 Team、(force=false 时)校验全员 IsActive=false
   - 对每个非 lead 成员:用 `SpawnDeps.BackendNew(mem.BackendType)` 解析后端,调 `Backend.Kill(ctx, mem.PaneID, mem.AgentID)` 杀 pane(tmux/iterm2)或 cancel goroutine(in-process)
   - 调 `cleanupMemberResources` 删 session 目录与 worktree(best-effort)
   - `os.RemoveAll(team.ConfigDir)` 删整个 Team 目录
   - 从 in-memory map 移除
   - 没注入 SpawnDeps 的测试场景跳过 Kill,fallback 只清磁盘资源

**验证:** 写单测覆盖 Create/Get/Delete 基本流程;`go test ./internal/team/...` 通过;tmux 实跑后 `/team delete --force` 看 pane 真的被杀(`tmux list-panes` 只剩 Lead)

## T3b: Team.Manager 跨进程并发兜底 — 继续 `internal/team/manager.go` + `internal/team/persistence.go`**文件:** `internal/team/manager.go`(为 AddMember / SetMemberActive 加 reload-before-modify)、`internal/team/persistence.go`(增加 `reloadFromDiskLocked`)
**依赖:** T3
**步骤:**
1. `persistence.go` 增 `(t *Team) reloadFromDiskLocked()`——调用方持锁;从 `t.ConfigPath` readJSON,把 `Members` 字段覆盖到 in-memory(失败静默回退到内存现状)
2. `Team.AddMember` 与 `Team.SetMemberActive`(以及任何会修改 Members 后 save 的方法)在加锁后**先**调 `reloadFromDiskLocked()` 再操作内存 + save
3. 不是为了多线程并发——in-process 早就有 mu 保护;**是为了跨进程**:Pane 后端的 Lead 与子进程是两个独立进程,各持一份内存中的 Team。如果不 reload,会出现"子进程读 config 时 Lead 的 AddMember 还没写入,子进程修改自己内存 Team 没看见自己,SetMemberActive 静默 no-op"的丢更新

**验证:** 单测构造时序:t1 = readJSON 得到无 alice 的 Team A;t2 在 disk 上写带 alice 的 Team B;t3 调 t.SetMemberActive("alice", false) 应该成功(走 reload 路径)而非静默 no-op

## T4: Team 成员操作 — 继续 `internal/team/manager.go`**文件:** `internal/team/manager.go`(同 T3)
**依赖:** T3
**步骤:**
1. 实现 `Team.AddMember(info *TeammateInfo) error`(F8)——加锁后**先 reloadFromDiskLocked**(见 T3b),检查重名;加入 Members;持久化
2. 实现 `Team.SetMemberActive(name string, active bool) error`(F9)——加锁后**先 reloadFromDiskLocked**;遍历 Members 找到 name 改 IsActive 字段;持久化
3. 实现 `Team.RemoveMember(name string) error`(F10)
4. 实现 `Team.MemberByName(name string) (*TeammateInfo, bool)` / `Team.MemberByAgentID(id string) (*TeammateInfo, bool)` 工具方法

**验证:** 单测覆盖 Add → SetActive → Remove 三步流程,读回 config.json 校验字段

## T5: mailbox 文件锁 — `internal/team/mailbox/lock.go`**文件:** `internal/team/mailbox/lock.go`
**依赖:** 无
**步骤:**
1. 定义 `package mailbox`
2. 实现 `acquireLock(lockPath string) (release func(), err error)`——
   - 循环 10 次:`os.OpenFile(lockPath, O_CREATE|O_EXCL|O_WRONLY, 0644)` 抢锁
   - 失败时 `os.Stat(lockPath)`,若 `Now() - ModTime > 10*time.Second` 则 `os.Remove` 后立即重试一次
   - 失败时 sleep 5-100ms 随机抖动后继续
   - release 函数:`os.Remove(lockPath)`
3. 内部常量 `lockMaxRetries = 10` / `lockStaleAfter = 10*time.Second` / `lockBackoffMin = 5*time.Millisecond` / `lockBackoffMax = 100*time.Millisecond`

**验证:** 单测 `TestAcquireLockSerial`(两次抢锁,中间 release)、`TestAcquireLockStale`(故意创建 11 秒前的锁,断言能拿到)

## T6: mailbox Message 与 Box — `internal/team/mailbox/mailbox.go`**文件:** `internal/team/mailbox/mailbox.go`
**依赖:** T5
**步骤:**
1. 定义 `MessageType` 与 4 个常量(F32)
2. 定义 `Message` 结构体(F32),字段带 json tag
3. 定义 `Box` 结构体,字段 `dir string`
4. 实现 `New(dir string) (*Box, error)`——`MkdirAll`
5. 实现 `Box.Write(agentID string, msg Message) error`(F33)
   - lockPath = `<dir>/<agentID>.lock`
   - acquireLock
   - 读 `<dir>/<agentID>.json`(不存在视为 `{"messages":[]}`)
   - 追加 msg(若 Timestamp=0 设为 now)
   - atomic write
6. 实现 `Box.Read(agentID string) ([]Message, error)`
7. 实现 `Box.ReadUnread(agentID string) ([]int, []Message, error)`——返回 unread 消息的 indices 与消息本身
8. 实现 `Box.MarkRead(agentID string, indices []int) error`——按 indices 把对应消息 Read=true

**验证:** 单测覆盖 Write/Read/MarkRead;并发测试 10 个 goroutine 写同一 agentID,断言读回 10 条无丢失

## T7: AgentNameRegistry — `internal/team/registry/registry.go`**文件:** `internal/team/registry/registry.go`
**依赖:** 无
**步骤:**
1. 定义 `package registry`
2. 定义 `AgentNameRegistry` 结构体
3. 实现 `New() *AgentNameRegistry`
4. 实现 `Register(name, agentID string)`——若 name 已存在覆盖(取出旧 agentID,从 byID 删旧映射);若 agentID 已有其他 name,先反向 unregister
5. 实现 `Unregister(name string)`
6. 实现 `UnregisterByAgentID(agentID string)`
7. 实现 `Resolve(nameOrID string) (agentID string, ok bool)`——先按 name 查,再按 agentID 反向查
8. 实现 `NameOf(agentID string) (string, bool)`
9. 实现 `List() map[string]string`

**验证:** 单测覆盖 Register/Unregister/Resolve/NameOf;包括「同名覆盖」和「不同名指向同一 agentID」边界

## T8: tasks Store — `internal/team/tasks/tasks.go`**文件:** `internal/team/tasks/tasks.go`
**依赖:** T5(用 mailbox 的 lock)
**步骤:**
1. 定义 `package tasks`
2. 定义 `Status` / `Task` / `Filter` / `Patch` 类型(F30)
3. 定义 `Store` 结构体,字段 `path string`, `mu sync.Mutex`
4. 实现 `New(path string) *Store`
5. 实现 `Store.Create(t Task) (string, error)`——生成 `task_<6位 hex>` ID;read-modify-write `tasks.json`(用 lock 文件,路径 `<path>.lock`,复用 mailbox.acquireLock——把 acquireLock 提到 `team/internal/filelock` 共用包,或直接在 tasks 包内复制小段实现)
6. 实现 `Store.Get(id string) (Task, error)`
7. 实现 `Store.List(f Filter) ([]Task, error)`——按 `status` 过滤,返回时附加 `is_ready` 字段(检查 BlockedBy 中所有任务是否 completed);为简化可在 List 输出时计算 ready 标记,不存盘
8. 实现 `Store.Update(id string, p Patch) error`——支持 title/description/status/assignee/addBlocks/addBlockedBy/removeBlocks/removeBlockedBy 字段
9. `addBlockedBy=[X]` 同时给 X 任务 `Blocks` 加上当前任务 id(双向维护)

**注意:** 为减小循环依赖,把 `acquireLock` 提到独立 `internal/team/filelock` 包,mailbox 与 tasks 共用。

**验证:** 单测覆盖 Create/Get/Update;特别测 addBlockedBy 的双向更新

## T9: 共用 filelock 包(从 mailbox 抽出)**文件:** `internal/team/filelock/filelock.go`(把 T5 实现迁过来)
**依赖:** 无
**步骤:**
1. 把 T5 的 `acquireLock` 实现迁到 `package filelock`,改名 `Acquire(lockPath string) (release func(), err error)`
2. 在 mailbox/lock.go 改为 import filelock 包,删除本地实现
3. 在 tasks 包里也 import filelock

**验证:** `go test ./internal/team/...` 全过

## T10: backend 接口 — `internal/team/backend/backend.go`**文件:** `internal/team/backend/backend.go`
**依赖:** T1
**步骤:**
1. 定义 `package backend`
2. 定义 `SpawnRequest` 结构体(F13)——其中 `SubAgent` / `Conv` / `TaskMgr` 字段类型为 `any`,避免 backend 反向依赖 agent 包
3. 定义 `Backend` 接口(F12)
4. 定义 `New(t team.BackendType, deps Dependencies) (Backend, error)` 工厂——按类型分发(暂时只占位,具体实现在 T12-T14)

**验证:** `go build` 通过

## T11: DetectBackend — `internal/team/backend/detect.go`**文件:** `internal/team/backend/detect.go`
**依赖:** T10
**步骤:**
1. 实现 `Detect() team.BackendType`(F14):
   - `os.Getenv("TMUX") != ""` → tmux
   - `os.Getenv("TERM_PROGRAM") == "iTerm.app"` 且 `exec.LookPath("it2") == nil` → iterm2
   - `exec.LookPath("tmux") == nil` → tmux
   - 否则 in-process

**验证:** 写 test 用 `t.Setenv` 控制环境变量,断言不同组合的返回值;PATH 检测难单测,跳过或用接口注入 lookPath

## T12: tmux backend — `internal/team/backend/tmux/tmux.go`**文件:** `internal/team/backend/tmux/tmux.go`
**依赖:** T10
**步骤:**
1. 定义 `Backend` 结构体
2. 实现 `New() backend.Backend`
3. 实现 `Type()` 返回 `team.BackendTmux`
4. 实现 `Spawn(ctx, req)`(F15):
   - 在 `$TMUX` 内:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`
   - 在 `$TMUX` 外但 `tmux` 二进制可用:`tmux new-session -d`(detached 新会话)走外部 session(F16)
   - `cmd` 构造:`gcode --team-member --team <teamName> --member <memberName> --agent-id <agentID> --session-dir <sessionDir> --worktree <wtPath> [--agent-type <type>] [--model <model>] [--plan-mode]`
   - `--agent-id` 必须传——子进程不需要读 Lead 还没写完的 `config.json` 找自己
   - `InitialPrompt` **不**走命令行,由 `team.SpawnTeammate`(T18)在 Backend.Spawn 之前预写入 alice mailbox
   - 用 `exec.CommandContext` 跑 tmux,捕获 stdout 作为 paneID
5. 实现 `Wake(ctx, paneID)`:`tmux send-keys -t <paneID> "" Enter`(子进程 stdin scanner 读到回车,立刻去 mailbox 轮询)
6. 实现 `Kill(ctx, paneID)`:`tmux kill-pane -t <paneID>`,忽略 pane not found 错误

**注意:** Spawn 启动的 gcode CLI 需要支持 `--team-member` flag;这部分留给 T21(main.go 改造)

**验证:** 单测断言命令字符串构造正确(用 `exec.Command` mock 或直接构造 *exec.Cmd 检查 Args);集成测试在 CI 跳过(需要 tmux)

## T13: iterm2 backend — `internal/team/backend/iterm2/iterm2.go`**文件:** `internal/team/backend/iterm2/iterm2.go`
**依赖:** T10
**步骤:**
1. 实现 `Backend.Spawn`:`it2 split --new-pane --command "<cmd>"`(实际 it2 CLI 命令以官方为准;先按 README 描述实现,实测可能要调);`<cmd>` 同 T12 格式,含 `--agent-id`,`InitialPrompt` 走 mailbox 预写
2. 实现 `Wake`:`it2 send-text --pane <paneID> ""`
3. 实现 `Kill`:`it2 close-pane --pane <paneID>`

**注意:** iterm2 后端无法在 CI 中实跑,实现以构造正确的命令字符串为准

**验证:** 单测断言命令构造正确

## T14: in-process backend — `internal/team/backend/inprocess/inprocess.go`**文件:** `internal/team/backend/inprocess/inprocess.go`
**依赖:** T10,需要 `agent`、`task`、`conversation` 包
**步骤:**
1. 定义 `Backend` 结构体,字段 `taskMgr *task.Manager`
2. 实现 `Spawn(ctx, req)`(F18):
   - 从 `req.SubAgent` / `req.Conv` 取已构造好的对象(类型断言)
   - 调 `taskMgr.Launch(ctx, subAgent, conv, req.MemberName, req.InitialPrompt)` 起 goroutine
   - 把 task id 写入 `req.AgentID` 引用(用 `*string`,或者通过返回值传)——本期改为 Backend.Spawn 返回 `(paneID, agentID string, err error)` 也行;**采用** `agentID` 是调用方先生成(`task.nextID` 直接暴露,或调用方生成 uuid),Spawn 不返回 agentID,只用调用方传入的
   - 调用方调 Spawn 前需要先决定 agentID;但 `task.Manager.Launch` 内部生成 ID 并返回——本期改为:in-process Spawn 调 `Launch` 拿到 task id,再让调用方把它写回 TeammateInfo.AgentID;Spawn 返回 (paneID="", err=nil),agentID 通过 SpawnRequest 中的 `AgentIDCallback func(string)` 回调
   - **简化:** Backend 接口改成 `Spawn(...) (paneID, agentID string, err error)`,统一三个后端
3. 实现 `Wake`:no-op,返回 nil
4. 实现 `Kill`:`taskMgr.Stop(paneID)`(其实 paneID 此时存 agentID,但用 agentID 字段更直观)

**重构 Backend 接口签名**(回 T10 调整):
```go
type Backend interface {
    Type() team.BackendType
    Spawn(ctx context.Context, req SpawnRequest) (paneID, agentID string, err error)
    Wake(ctx context.Context, paneID, agentID string) error
    Kill(ctx context.Context, paneID, agentID string) error
}
```
Pane 后端用 paneID,in-process 用 agentID;接口统一传两者,各自取需要的。

**验证:** 单测:构造 fake taskMgr,Spawn 一个 noop 子 Agent,断言 goroutine 启动

## T15: feature flag — `internal/team/feature.go`**文件:** `internal/team/feature.go`
**依赖:** 无
**步骤:**
1. 实现 `ForkTeammateEnabled(cfg *config.Config) bool`——读 `cfg.Features.ForkTeammate`

**验证:** 单测覆盖 true/false 两种 cfg

## T16: TeammateContext — `internal/agent/team_hook.go`**文件:** `internal/agent/team_hook.go`
**依赖:** 无
**步骤:**
1. 定义 `TeamHook` 接口(plan.md 已给签名)
2. 定义 `TeamSpawnRequest` 结构体(把 Agent 工具参数传过去)
3. 定义 `TeammateContext` 结构体——`TeamName`、`MemberName`、`AgentID`、`MailboxDir`、`SendMessageWake func(target)` 等
4. 提供 ctx key + `WithTeammateContext(ctx, tc) context.Context` + `TeammateContextFromCtx(ctx) (*TeammateContext, bool)`

**验证:** `go build` 通过

## T17: 队员专属工具白名单 — `internal/tool/filter.go` 扩展**文件:** `internal/tool/filter.go`(修改)
**依赖:** 无
**步骤:**
1. 新增常量:
   ```go
   var TEAMMATE_EXTRA_TOOLS = []string{
       "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "SendMessage",
   }
   ```
2. 扩展 `FilterParams` 结构体加 `Teammate bool` 字段
3. 在 `ApplyAgentToolFilter` 中:若 `Teammate=true`,把 `TEAMMATE_EXTRA_TOOLS` 加到允许集合(在 disallowed 删除之前);非 Teammate 时排除这些工具(主 Agent 看不到)
4. 同时增加常量 `TEAM_LEAD_DISALLOWED_TEAMMATE_TOOLS`——避免主 Agent 直接看到 TaskCreate 等(应该走 Teammate=true 才能加上)

**简化策略:** TEAMMATE_EXTRA_TOOLS 不进默认 registry(由 main.go 注册到 registry,但默认从 ALL 过滤集移除);Teammate=true 时把它们加回。

**采用:**
- main.go 把 5 个协作工具注册到 registry
- 修改默认 filter:`ALL_AGENT_DISALLOWED_TOOLS` 加上这 5 个工具(子 Agent 默认看不到)
- 新增 `TEAMMATE_ALLOWED_TOOLS = ALL_AGENT_DISALLOWED_TOOLS 中的协作工具`
- 修改 `ApplyAgentToolFilter`:`Teammate=true` 时,这 5 个工具不被 ALL 过滤

**验证:** 单测覆盖 Teammate=true / false,断言 TaskCreate 等可见性

## T18: SpawnTeammate 主流程 — `internal/team/spawn.go`**文件:** `internal/team/spawn.go`
**依赖:** T1-T17
**步骤:**
1. 定义 `Manager.SpawnTeammate(ctx, req agent.TeamSpawnRequest) (string, error)`
2. 实现 plan.md 中描述的 步骤流程:
   - 取 Team
   - 校验调用者权限(看 ctx 是否有 TeammateContext,且 BackendType=in-process 时拒绝)
   - 解析 subagent.Definition
   - wtMgr.Create(`.gcode/worktrees/team-<sanitized>+<member>`)
   - 申请 sessionDir(本期复用 ch12 格式,自己生成新 id)
   - 预生成 agentID(`agent-<14位hex>`),构造 SpawnRequest 含 AgentID 字段
   - 计算 allowed = `tool.ApplyAgentToolFilter(Teammate=true, ...)`、systemPrompt = `def.SystemPrompt + teamSystemPromptSuffix()`
   - 若 BackendType=in-process:构造 subAgent(**强制 `DontAsk=true`** F39a)+ subConv,注入 `<team-context>` reminder + `SetCtxDecorator` 装 `TeammateContext{Mailbox: mc}`
   - 若 BackendType=tmux/iterm2:`mailbox.New(t.MailboxDir).Write(agentID, {From:lead, Type:text, Summary:..., Content:req.Prompt})` 预写初始任务(F13)
   - backend.Spawn 取 paneID
   - registry.Register(memberName → agentID)
   - team.AddMember (调用时 `reloadFromDiskLocked` 保护跨进程并发)
   - 返回 JSON `{member_name, agent_id, worktree, backend, pane_id}`
3. 提供 helper `buildTeamContextReminder(team, member, agentID)` 构造 `<team-context>` reminder
4. 提供 helper `teamSystemPromptSuffix() string` 返回 F39 附录;`truncateForSummary(prompt)` 给初始任务 mailbox 消息生成 summary

**验证:** 单测覆盖 in-process 后端的 spawn 全流程;Pane 后端的 spawn 用 mock backend

## T19: Agent 工具集成 — `internal/agent/agent_tool.go` 修改**文件:** `internal/agent/agent_tool.go`(修改)
**依赖:** T16, T18
**步骤:**
1. `agentToolArgs` 加 `TeamName string \`json:"team_name,omitempty"\``
2. `AgentTool` 加字段 `teamHook TeamHook`
3. `NewAgentTool` 加参数 `teamHook TeamHook`
4. `Description()` 中说明 `team_name` 参数(可选,非空时走 Team spawn)
5. `Parameters()` 加 `team_name` 字段
6. `Execute` 在 `a.TeamName != ""` 时:
   - 校验 `teamHook != nil`,否则错
   - 校验 ctx 不在 in-process 队员中(`teamHook.IsTeammateContext(ctx)`,若是且 BackendType=in-process,返回 ErrInProcessTeammateNoSpawn)
   - 调 `teamHook.SpawnTeammate(ctx, TeamSpawnRequest{TeamName:..., MemberName:a.Name, ...})`
   - 返回 SpawnTeammate 的结果

**验证:** 单测:不带 team_name 走 ch13 老路径;带 team_name 调 mock teamHook,断言 SpawnTeammate 被调

## T20: 队员 Loop incoming-messages 注入 — `internal/agent/...`**文件:** `internal/agent/agent.go` 或对应文件
**依赖:** T16, T6
**步骤:**
1. 在 `agent.Agent.Run` / `RunToCompletion` 的迭代头部(调 LLM 前),检查 ctx 中是否有 TeammateContext;实现位于 `internal/agent/team_mailbox.go::ingestTeamMailbox`
2. 若有,调 `tc.Mailbox.ReadUnread()`
3. 若有未读消息,构造 `<incoming-messages>` reminder 字符串(F42),加到 runtime.PendingReminders(下一轮 buildReminder 取出)
4. 调 `tc.Mailbox.MarkRead(indices)`
5. 若收到 `plan_approval_response(approve=true)`,调 `Agent.SetPermissionMode(permission.ModeDefault)` 切回 default(reminder 文本也会反映这一切换)。**注意:** Pane 后端子进程的 plan_approval 由 `runTeamMember` 主循环额外处理一份——它读到 plan_approval_response 时同样切模式 + 合成续派 prompt 让 RunToCompletion 接着跑(F19a)

**注意:** Agent 包不直接 import mailbox(避免循环);通过 `TeammateContext` 中的 `*mailbox.Box` 字段访问;或通过接口抽象(`type MailboxReader interface{ ReadUnread...; MarkRead...}`)

**采用接口:**
```go
// agent/team_hook.go
type Mailbox interface {
    ReadUnread(agentID string) ([]int, []mailbox.Message, error)
    MarkRead(agentID string, indices []int) error
}
```
import 还是会成环——把 Message 类型也抽象成接口或 any。**简化:** TeammateContext 持 `func() ([]Message, error)` 闭包,由 spawn 时由 team 包注入。Message 在 agent 包定义一个轻量结构,只取需要的字段。

**采用最简方案:** 在 `agent` 包内定义 `IncomingMessage` 结构(独立于 mailbox.Message),TeammateContext 携带 `ReadUnread func() (indices []int, msgs []IncomingMessage, err error)` 和 `MarkRead func(indices []int) error` 闭包;由 team 包在 spawn 时构造闭包注入。

**验证:** 单测覆盖:fake Mailbox 写入 1 条消息,启动子 Agent.Run,断言 reminder 含 `<incoming-messages>`

## T21: task.Manager 改造 — `internal/task/manager.go` 修改**文件:** `internal/task/manager.go`(修改)
**依赖:** T7
**步骤:**
1. `Manager` 持一个 `nameReg *registry.AgentNameRegistry` 引用(可选 nil 兜底)
2. `Launch` 时:若 nameReg 非 nil 且 name 非空,调 `nameReg.Register(name, id)`;同时保持本地 `byName` 兜底(避免破坏 ch13 既有调用)
3. `GetByName` 优先用 nameReg.Resolve 查
4. `SendMessage(parentCtx, name, message)` 优先 nameReg.Resolve
5. 新增 `OnTaskDone(fn func(taskID string))` 注册接口,可注册多个回调
6. `runTask` 的 defer 末尾(在 notifyDone 后)逐个调 OnTaskDone 回调
7. 加 `SetNameRegistry(reg *registry.AgentNameRegistry)` setter

**验证:** 单测:注册 OnTaskDone,Launch 一个 noop task,等完成,断言回调被触发

## T22: 协作工具实现 — `internal/team/tools/`**文件:** `team_create.go` / `team_delete.go` / `task_create.go` / `task_get.go` / `task_list.go` / `task_update.go` / `send_message.go`
**依赖:** T3, T6, T7, T8
**步骤:**
1. 每个工具实现 `tool.Tool` 接口(Name/Description/Parameters/ReadOnly/Execute)
2. `TeamCreate`(F21):参数 team_name + description;Execute 调 `Manager.Create`,返回 JSON
3. `TeamDelete`(F23):参数 team_name + force;Execute 调 `Manager.Delete`
4. `TaskCreate`(F26):参数 title/description/assignee/blocked_by;从 ctx 取 TeammateContext 找当前 Team;Execute 调 `Store.Create`
5. `TaskGet`(F27):参数 task_id
6. `TaskList`(F28):参数 status 过滤;返回带 is_ready 字段的 JSON 数组
7. `TaskUpdate`(F29):参数 task_id + 各 Patch 字段
8. `SendMessage`(F34):参数 to/summary/message/type/payload;Execute 调 Mailbox.Write + Backend.Wake + 续派检测
9. 每个工具 ReadOnly() 返回:TeamCreate/Delete/TaskCreate/Update/SendMessage 返回 false;TaskGet/TaskList 返回 true

**验证:** 每个工具一个单测覆盖正常路径与错误路径

## T23: 协作工具白名单生效 — 验证**文件:** `internal/tool/filter_test.go`(修改)
**依赖:** T17, T22
**步骤:**
1. 在 ApplyAgentToolFilter 测试中加用例:
   - 主 Agent(`Teammate=false`)调用:看不到 TaskCreate / SendMessage 等
   - 队员(`Teammate=true`)调用:看到这 5 个

**验证:** 测试通过

## T24: coordinator 包 — `internal/coordinator/coordinator.go`**文件:** `internal/coordinator/coordinator.go`
**依赖:** 无
**步骤:**
1. 实现 `IsEnabled(cfg *config.Config) bool`——`cfg.Features.CoordinatorMode && envTruthy(os.Getenv("GCODE_COORDINATOR_MODE"))`
2. 实现 `AllowedTools() []string`(F53)
3. 实现 `SystemPromptSuffix() string`(F55)——除四阶段框架外,**必须**包含"派完队员就停手等汇报"的纪律段:派出 Agent/SendMessage 后禁止立刻 read_file/glob/grep/bash 自己探索;禁止 sleep/TaskList 凑时间;只在 Research 首次定位 / Synthesis 读队员产出 / Verification 收敛 时才允许自己用读类工具
4. 实现 `envTruthy(v string) bool`——`"1"`/`"true"`/`"yes"`(大小写不敏感)

**验证:** 单测覆盖双锁的 4 种组合(00/01/10/11),只有 11 返回 true;tmux 实跑观察 Lead 派完队员后不立刻 glob/read_file 而是"等待汇报"

## T25: config 加 Features — `internal/config/config.go` 修改**文件:** `internal/config/config.go`(修改)
**依赖:** 无
**步骤:**
1. 加结构体 `FeaturesConfig`,字段 `CoordinatorMode bool` + `ForkTeammate bool`,带 yaml tag
2. `Config` 加字段 `Features FeaturesConfig`
3. 默认值都为 false

**验证:** 单测加载 yaml 含 features 段,断言字段被读出

## T26: TUI 集成 — `internal/tui/tui.go` 修改**文件:** `internal/tui/tui.go` 与可能的 statusbar 文件(修改)
**依赖:** T3, T24
**步骤:**
1. `TUIParams` 加 `TeamMgr *team.Manager`、`CoordinatorMode bool`
2. Model 加字段 `coordinatorMode bool` 与 `leadMailCh chan struct{}`(buffer=1);New 时 `leadMailCh = make(chan struct{}, 1)`
3. coordinator 应用迁到 `cmd/gcode/main.go` 中的 mainAgent 上(SetAllowedTools + AppendSystemPrompt)——tui 自身只负责状态栏渲染
4. 状态栏渲染时若 `m.coordinatorMode==true` 在 mode label 后追加 ` [COORDINATOR]`(参见 `internal/tui/view.go statusBar()`)
5. config 字段名是 **snake_case**:`features.coordinator_mode`(不是 camelCase)

**验证:** 在 config.yaml 加 `features:\n  coordinator_mode: true`,启动时设环境变量 `GCODE_COORDINATOR_MODE=1`,观察状态栏出现 `[COORDINATOR]`

## T27: /team slash 命令 — `internal/command/builtin_team.go`**文件:** `internal/command/builtin_team.go`
**依赖:** T3
**步骤:**
1. 注册 4 个本地命令(KindLocal):
   - `/team list`(F59)
   - `/team info <name>`(F60)
   - `/team delete <name> [--force]`(F61)
   - `/team kill <member>`(F62)
2. 在 `RegisterBuiltins` 或对应注册入口加入

**验证:** `/team list` 在 TUI 输出含已创建 Team

## T28: main.go wire — `cmd/gcode/main.go` 修改**文件:** `cmd/gcode/main.go`(修改)
**依赖:** T1-T27
**步骤:**
1. 构造 `nameReg := registry.New()`
2. `taskMgr.SetNameRegistry(nameReg)`
3. 构造 `teamMgr, err := team.NewManager(home, root, worktreeMgr, taskMgr, nameReg)`
4. 注册 7 个新工具到 registry(TeamCreate/TeamDelete/TaskCreate/TaskGet/TaskList/TaskUpdate/SendMessage)
5. `agentTool := agent.NewAgentTool(..., teamMgr)`(把 teamMgr 作为 TeamHook 注入)
6. TUIParams 加 `TeamMgr: teamMgr`、`Coordinator: coordinator.IsEnabled(cfg)`
7. 若 `--team-member` flag 出现:**所有依赖 wire 完成后**直接调 `runTeamMember(ctx, teamMemberArgs{...})` 并 `return`,**不**构造 TUI(F19a);否则继续走 TUI 路径
8. Lead 启动时(TUI 路径)若 `coordinator.IsEnabled(cfg)`:`mainAgent.SetAllowedTools(coordinator.AllowedTools())` + `mainAgent.AppendSystemPrompt(coordinator.SystemPromptSuffix())`

**验证:** `go build ./cmd/gcode/...` 通过;启动 gcode 主流程正常

## T29: --team-member 自治循环 — `cmd/gcode/team_member.go`(新文件)**文件:** `cmd/gcode/team_member.go`(新建)
**依赖:** T28
**步骤:**
1. 解析新增 CLI flags:`--team-member` / `--team` / `--member` / `--agent-id` / `--session-dir` / `--worktree` / `--agent-type` / `--model` / `--plan-mode`
2. main.go 中在 `--team-member` 分支先 `os.Chdir(--worktree)`,再 wire 完所有依赖
3. 实现 `runTeamMember(ctx, teamMemberArgs)`:
   - 从 `args.teamMgr.Get(teamName)` 拿 Team(已含 Lead 写入的 alice 条目,reload-from-disk 兜底)
   - 解析角色定义(`subagent.Catalog.Resolve(agentType)`),拿 SystemPrompt / MaxTurns / Plan 等
   - 用 `tool.ApplyAgentToolFilter(Teammate=true, ...)` 算 allowed tools
   - 构造 provider(`llm.New`)+ `*agent.Agent`,**强制 `WithDontAsk(true)`**(F39a)
   - 注入 `<team-context>` reminder(F40) + `SetCtxDecorator` 把 `TeammateContext{Mailbox: mc}` 装进 ctx
   - 起一个 stdin scanner goroutine:每读一行就推 `wakeCh`,触发 mailbox 即时轮询
   - 进主循环(F19a):read unread → 分流消息(text 拼 task / plan_approval / shutdown_request)→ `RunToCompletion` → 通知 Lead idle → `SetMemberActive(false)` → 等下一条
   - 检测 mailbox 目录消失 → 优雅退出
4. 把 agent.Event 流转 stdout 打印(`printAgentEvent`),pane 内呈现只读日志

**验证:** 见 AC28 步骤 4 端到端实跑——alice pane 内显示 task 执行流,`/tmp/test_alice.txt` 落地,SendMessage 后 alice 能续派

## T30: 队员空闲通知 hook 注入**文件:** `cmd/gcode/main.go`(修改)+ `internal/team/manager.go`(加 helper)
**依赖:** T21, T3
**步骤:**
1. 在 main.go wire 后,注册 OnTaskDone 回调到 taskMgr:
   ```go
   taskMgr.OnTaskDone(func(taskID string) {
       teamMgr.HandleTaskDone(taskID)
   })
   ```
2. 实现 `Manager.HandleTaskDone(agentID string)`:
   - 查 registry.NameOf(agentID) → name
   - 遍历 teams 找到该成员所属 Team
   - SetMemberActive(name, false)
   - mailbox.Write(leadAgentID, Message{type:"text", summary:"<name> idle"})

**验证:** 集成测试:in-process 后端 spawn 队员→ 自然结束 → 断言 Team.config 中 IsActive=false、Lead mailbox 有 idle 消息

## T30b: Lead mailbox 轮询 + 自动唤醒 — `internal/team/manager.go` + `internal/tui/tasks.go` + `internal/tui/tui.go` + `internal/tui/stream.go`**文件:**
- `internal/team/manager.go`(增加 `PollLeadMailboxes` + `LeadMessage`)
- `internal/tui/tasks.go`(增加 `consumeLeadMail` / `waitForLeadMail` / `buildTeamUpdateReminder` / `leadMailMsg`)
- `internal/tui/tui.go`(Init 启动 watcher + 监听 Cmd;Update 处理 `leadMailMsg`)
- `internal/tui/stream.go`(增加 `beginAutonomousTurn`)
**依赖:** T28(main.go 已 wire teamMgr 进 TUIParams)
**步骤:**
1. `team.Manager.PollLeadMailboxes()`:遍历 `m.List()`,对每个 Team 用 `mailbox.New(t.MailboxDir).ReadUnread(t.LeadAgentID)` 读未读,标 read,返回 `[]LeadMessage{TeamName, From, Type, Summary, Content, Time}`
2. TUI Model 加字段 `leadMailCh chan struct{}`(buffer=1,New 时初始化)
3. `consumeLeadMail`(TUI Init 启动 goroutine):1 秒 ticker → PollLeadMailboxes → 非空时调 `buildTeamUpdateReminder`(列消息条目 + content 截断 8000 字)→ `runtime.AppendReminders` → 非阻塞推 leadMailCh
4. `waitForLeadMail(ch)`:tea.Cmd,阻塞读 ch,转 `leadMailMsg` 给 Update;Init 把这条 Cmd 也 Batch 进去
5. Update 处理 `leadMailMsg`:
   - re-arm `waitForLeadMail(ch)` 让后续信号也能接住
   - 若 `m.state == stateIdle`,调 `beginAutonomousTurn` 自动开新轮
   - 否则 reminder 已在 PendingReminders 里,等当前 Run 下一轮迭代自然取出
6. `beginAutonomousTurn`:合成 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."`,`conv.AddUser` + 调 `beginTurn(userBlock(...))`——保证 LLM 调用满足"对话末尾必须 user"约束,用户在 scrollback 也能看见是自动触发

**验证:** tmux 实跑——Lead 派 alice + bob;30 秒内队员 RunToCompletion idle 后 mailbox.unread 1 秒内归零(watcher 消费);若 Lead 当时空闲,屏幕上自动出现 `● [team-update] 队员发来新消息...` 用户文本块 + Lead 紧接着的 Synthesis 回复——内容包含队员报告里的真实文件名(如 `agent.go`、`team_mailbox.go`),证明完整 content 通过 reminder 传到 Lead 视野

## T31: 续写检测 — `internal/team/tools/send_message.go`**文件:** `internal/team/tools/send_message.go`(同 T22)
**依赖:** T22, T21
**步骤:**
1. SendMessage.Execute 写完邮箱后:
   - 取目标 TeammateInfo.BackendType
   - 若 BackendType=in-process:
     - 查 taskMgr.Get(agentID),若 Status != Running:
       - Team.SetMemberActive(name, true)
       - taskMgr.SendMessage(ctx, name, content) 走 ch13 续派接口
   - 若 Pane 后端:已通过 Wake 唤醒,无需续派

**验证:** 单测:先 spawn → 等结束 → SendMessage → 断言 task 重新 Running

## T32: Plan 审批权限切换 — `internal/agent/...`**文件:** `internal/agent/team_hook.go`(修改)或 `internal/agent/agent.go`
**依赖:** T20
**步骤:**
1. 在 incoming-messages 注入逻辑中:若有 `plan_approval_response(approve=true)` 消息:
   - 调 `Agent.SetPermissionMode(permission.ModeDefault)`(或 Lead 当前模式,本期固定 default)
   - reminder 加文案:「Lead 已批准计划,权限模式已切到 default,可执行计划」
2. 若 approve=false:reminder 加文案:「Lead 驳回了计划,反馈:<feedback>。请调整后重新提交」

**验证:** 集成测试:队员以 plan 模式起步 → 收到 plan_approval_response(true) → Agent.permissionMode 切换

## T33: 单元测试集 — 各包 *_test.go**依赖:** T1-T32
**步骤:**
1. 跑 `go test ./...`,补失败用例
2. 跑 `go vet ./...`,修警告
3. 跑 `gofmt -l .` 看无未格式化文件

**验证:** 全绿

## T34: tmux 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. 启动 tmux:`tmux new-session -s ch15-test`
2. 在内层跑 `cd /Users/codemelo/gcode && go run ./cmd/gcode/`
3. 在 TUI 输入:「创建一个名为 demo 的团队」
4. 观察:
   - Agent 调 TeamCreate
   - `~/.gcode/teams/demo/config.json` 落地
   - 状态栏 / 输出确认成功
5. 在 TUI 输入:「派 alice 用 general-purpose,在 worktree 里 echo hello > /tmp/test_alice.txt」
6. 观察:
   - tmux split 出新 pane
   - alice pane 内 gcode 子实例启动
   - `.gcode/worktrees/team-demo+alice/` 创建
   - `/tmp/test_alice.txt` 文件内容为 `hello`
7. 在 TUI 输入:`/team info demo`,确认 alice 出现
8. 在 TUI 输入:「给 alice 发消息,让她再写一行 world」(Agent 调 SendMessage)
9. 观察:alice pane 被唤醒,`/tmp/test_alice.txt` 多一行 `world`
10. `/team delete demo --force`,清理

**验证:** 步骤全部成功

## T35: in-process 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. `unset TMUX TERM_PROGRAM`
2. `cd /Users/codemelo/gcode && go run ./cmd/gcode/`
3. Agent 调 TeamCreate("inproc") → backend 为 in-process
4. Agent 派 bob(后端 in-process)
5. bob 在同进程跑完
6. 观察 `team.config.json` 中 bob 的 `is_active=false`
7. Lead 调 SendMessage(to="bob", message="再做一件事"),bob 从 session 恢复继续

**验证:** 全部成功

## 执行顺序

```
T1 → T2 → T3 → T4
              ↘
T5 → T6        T8 ── T9(把 lock 抽出,T6/T8 改 import)
T7            
T10 → T11
   → T12,T13,T14(并行)
T15
T16 → T17 → T18 → T19
                → T20 → T32
T21
T22 → T23 → T31
T24 → T25 → T26
T27
T28 → T29 → T30
T33(收尾测试)
T34, T35(实跑验收)
```

并行机会:T5/T7/T8 互不依赖;T12/T13/T14 互不依赖;T22 中 7 个工具可分批。
````

```markdown
# Agent Team Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为而非实现细节。

## 实现完整性

- [ ] `team.Manager` 可被实例化:`team.NewManager(home, root, wtMgr, taskMgr, nameReg)` 返回非 nil(验证:`go build ./internal/team/...`、跑单测)
- [ ] `team.Manager.Create("demo", "")` 在 `~/.gcode/teams/demo/config.json` 落地(验证:运行单测后检查文件存在)
- [ ] `team.Manager.Create("foo bar/baz", "")` sanitize 后路径为 `~/.gcode/teams/foo-bar-baz/`(验证:单测)
- [ ] 同名 Team 第二次 Create 自动后缀 `-2`(验证:单测)
- [ ] `team.BackendType` 三个值齐全:`tmux` / `iterm2` / `in-process`(验证:`go vet` 通过 + 单测枚举)
- [ ] `backend.Detect()` 在 `$TMUX` 设置时返回 `tmux`;两环境变量都清空时返回 `in-process`(验证:`t.Setenv` 单测)
- [ ] `mailbox.Box.Write` + `mailbox.Box.Read` 一进一出消息字段一致(验证:单测)
- [ ] `mailbox` 文件锁在 stale 10 秒后能被新 writer 抢占(验证:单测制造 11 秒前的锁,断言能拿到)
- [ ] `registry.AgentNameRegistry.Register("alice", "agent-123")` 后 `Resolve("alice")` 返回 `("agent-123", true)`,`NameOf("agent-123")` 返回 `("alice", true)`(验证:单测)
- [ ] `tasks.Store.Create` 返回的 task id 形如 `task_<6位 hex>`(验证:单测)
- [ ] `tasks.Store.Update(id, Patch{AddBlockedBy:[other]})` 同时给 other 任务的 `Blocks` 加上 id(验证:单测断言双向)
- [ ] `tasks.Store.List(Filter{Status:pending})` 返回结果带 `is_ready` 字段,反映 BlockedBy 是否全 completed(验证:单测)
- [ ] `coordinator.IsEnabled` 在 feature flag 关 + 环境变量开时返回 false(验证:单测 4 种组合)
- [ ] `coordinator.AllowedTools()` 含 `bash` 不含 `write_file` / `edit_file`(验证:单测)
- [ ] `tool.ApplyAgentToolFilter(FilterParams{Teammate:true, ...})` 返回值含 `TaskCreate` / `SendMessage` 等 5 个协作工具(验证:单测)
- [ ] `tool.ApplyAgentToolFilter(FilterParams{Teammate:false, ...})` 不含这 5 个工具(验证:单测)
- [ ] 7 个新工具注册到 registry 后,`registry.Definitions()` 输出含 `TeamCreate` / `TeamDelete` / `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage`(验证:单测或启动后 `/status`)
- [ ] `Team.AddMember` 与 `Team.SetMemberActive` 调用前先 `reloadFromDiskLocked` 重读 disk(验证:跨进程并发写 disk 时不丢更新——单测制造"Lead 在 alice 子进程读完 config 之后才 AddMember"的时序,alice 走 SetMemberActive(false) 后回读 disk 应看到 is_active=false)

## 集成

- [ ] `Agent` 工具不带 `team_name` 时走 ch13 原路径,行为不变(验证:`go test ./internal/agent/...` 全过)
- [ ] `Agent` 工具带 `team_name="demo"` 时调 `teamHook.SpawnTeammate`(验证:单测 mock teamHook,断言被调用)
- [ ] `SpawnTeammate` 创建 worktree 路径为 `.gcode/worktrees/team-demo+alice`(验证:单测/集成测试)
- [ ] `SpawnTeammate` 后 `team.Members` 含 alice,持久化到 `config.json`(验证:单测)
- [ ] in-process 后端的队员 ctx 含 TeammateContext,其 BackendType=in-process;该队员调用 `Agent(team_name=...)` 被拒绝并返回 `ErrInProcessTeammateNoSpawn`(验证:集成测试)
- [ ] 队员 Agent.Run 头部读取 mailbox 未读消息,以 `<incoming-messages>` reminder 注入到 LLM 输入(验证:单测,fake mailbox 写消息,捕获 Agent 构造的 prompt)
- [ ] 队员收到 `plan_approval_response(approve=true)` 后 `Agent.permissionMode` 切换到 default(验证:单测 + tmux 实跑——见场景 4)
- [ ] 队员 `RunToCompletion` 结束触发 `OnTaskDone` 回调,Team config 中该成员 `is_active=false`(验证:单测注册回调 + Launch noop task)
- [ ] 队员 idle 后 Lead mailbox 收到 `summary="<name> idle"` 消息(验证:单测/集成)
- [ ] `SendMessage(to="alice", ...)` 在 alice 已 stop 且为 in-process 后端时,通过 `taskMgr.SendMessage` 续派(验证:集成测试,断言 task Status 回到 Running);Pane 后端时通过 `backend.Wake` 让子进程读 mailbox 自然续派
- [ ] 所有 Team 队员一律 `DontAsk=true`(覆盖角色 frontmatter 的 permissionMode),子进程没人能应答 ApprovalRequest 不会卡死(验证:用 `permissionMode: default` 的角色派队员让她调 bash,实跑断言任务正常完成,而不是卡在 Ask)
- [ ] Pane 后端 spawn 时 `InitialPrompt` 通过预写入 mailbox(type=text, from=lead)送达,子进程不需要走 CLI 参数(验证:tmux 实跑,在 spawn 完检查 alice mailbox 已有一条 from=lead 的初始任务)
- [ ] Pane 后端子进程命令行含 `--agent-id <id>` 参数(验证:看 `buildMemberCmd` 单测;tmux 实跑后 `ps auxww | grep team-member` 看实际命令)
- [ ] Pane 后端的 `gcode --team-member` 子进程**不启动 TUI**,跑 `runTeamMember` 自治循环——读 mailbox → RunToCompletion → 通知 Lead idle → stdin Wake 等下一轮(验证:tmux 实跑看 alice pane 显示纯文本日志流而非 gcode TUI 框)
- [ ] Lead mailbox watcher 每秒轮询所有 Team 的 lead.json,把未读消息转 `<team-update>` reminder 推 PendingReminders + 给 `leadMailCh` 发信号(验证:tmux 实跑后看 alice 发完 idle 通知 1 秒内 mailbox 的 unread 归零、read 累加)
- [ ] Lead 在 `stateIdle` 时收到 `leadMailMsg`,TUI 调 `beginAutonomousTurn` 合成 user 消息自动开新轮(验证:tmux 实跑——派完队员等他完成,Lead 不需要用户输入就自动出现 `[team-update]...` 行 + Synthesis 回复)
- [ ] `/team list` 输出含 `~/.gcode/teams/` 下所有 Team(验证:TUI 实跑)
- [ ] `/team delete demo --force` 调 `backend.Kill` 杀 pane(tmux/iterm2)+ 清 worktree + 清 team 目录(验证:TUI 实跑后 `tmux list-panes` 只剩 Lead,worktree 与 team 目录都消失)
- [ ] 沙箱开放 `/tmp` 与 `/private/tmp`(macOS 真实路径)作为白名单——write_file/edit_file 可写 `/tmp/foo.txt`,但 `/etc/passwd` 仍拒(验证:单测 TestSandboxContains 含两组用例)

## 编译与测试

- [ ] `go build ./...` 无错误(验证:命令退出码 0)
- [ ] `go vet ./...` 无警告(验证:命令退出码 0)
- [ ] `go test ./...` 全部通过(验证:命令退出码 0)
- [ ] `gofmt -l .` 无输出(验证:无未格式化文件)

## 端到端场景(tmux 实跑)

> 这是本章的核心验收场景,必须在真实 tmux 会话内手动跑一遍。

**场景 1:tmux 后端,Team 全生命周期**

环境准备:
- macOS / Linux
- tmux 已安装
- 当前不在 gcode 进程内,准备开新 tmux 会话

步骤:
- [ ] `tmux new-session -s ch15-test` 进入新 tmux 会话
- [ ] `cd /Users/codemelo/gcode && go build -o /tmp/gcode ./cmd/gcode/`(预编译,加快冷启动)
- [ ] `/tmp/gcode` 启动 TUI;启动消息显示一切正常,无 ch15 相关 error
- [ ] 在 TUI 输入:「创建一个名为 demo 的团队」
  - 预期:Agent 调 `TeamCreate(team_name="demo")`;返回 `{"team_name":"demo","backend":"tmux","config_path":"..."}`
  - 验证:`ls ~/.gcode/teams/demo/config.json` 存在;`cat config.json` 中 `backend` 字段为 `tmux`
- [ ] 在 TUI 输入:「派 alice 用 general-purpose 角色,在 worktree 里跑 `echo hello > /tmp/test_alice.txt && pwd > /tmp/test_alice_pwd.txt`」
  - 预期:Agent 调 `Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="...")`
  - 验证 a:tmux 自动 split 出右侧 pane(`tmux list-panes -F "#{pane_id} #{pane_current_command}"` 看到新 pane)
  - 验证 b:新 pane 内**显示自治循环日志流**(`[team-member] alice · team=demo · agent=... · cwd=...` 起始行 + Agent 工具调用打印,**不是** gcode TUI 框)
  - 验证 c:`ls /Users/codemelo/gcode/.gcode/worktrees/team-demo+alice/` 目录存在
  - 验证 d:等待 30 秒,`cat /tmp/test_alice.txt` 内容为 `hello`
  - 验证 e:`cat /tmp/test_alice_pwd.txt` 内容为 worktree 路径(`.../team-demo+alice`)
  - 验证 f:`cat ~/.gcode/teams/demo/config.json` 中 `members` 数组含 alice,`backend_type="tmux"`,`pane_id` 非空
  - 验证 g:`~/.gcode/teams/demo/mailbox/<aliceAgentID>.json` 中应已含一条 from=lead 的 text 消息——Pane 后端的 InitialPrompt 预写入证据
- [ ] 在 TUI 输入 `/team info demo`
  - 预期:输出含 alice 行,显示 worktree、pane_id、is_active 状态
- [ ] 在 TUI 输入:「给 alice 发消息,让她再写一行 world 到 /tmp/test_alice.txt」
  - 预期:Agent 调 `SendMessage(to="alice", summary="append world", message="...")`
  - 验证 a:alice pane 被唤醒(`tmux send-keys` 触发,pane 显示新内容)
  - 验证 b:30 秒内,`cat /tmp/test_alice.txt` 看到第二行 `world`
- [ ] 等待 alice 任务自然结束(或在 TUI 输入 `/team kill alice` 终止)
  - 验证 a:`cat ~/.gcode/teams/demo/config.json` 中 alice 的 `is_active` 为 `false`(跨进程 reload 修复——alice 子进程的 `SetMemberActive(false)` 必须真的反映到 disk;早期 bug 是静默 no-op)
  - 验证 b:Lead 的 mailbox(`cat ~/.gcode/teams/demo/mailbox/lead.json`)含一条 `summary` 含 `idle` 的消息,且 1-2 秒后该消息 `read=true`(watcher 已消费)
  - 验证 c:Lead 屏幕**不需要用户输入**自动出现 `● [team-update] 队员发来新消息...` 文本块 + 紧接的 Synthesis 回复(自动唤醒)
- [ ] 在 TUI 输入 `/team delete demo --force`
  - 验证 a:`ls ~/.gcode/teams/` 无 `demo` 目录
  - 验证 b:`ls /Users/codemelo/gcode/.gcode/worktrees/` 无 `team-demo+alice`
  - 验证 c:`tmux list-panes` 只剩 Lead pane,alice 的 `%1` 被 backend.Kill 干掉了

**场景 2:in-process 后端实跑**

环境准备:
- `unset TMUX TERM_PROGRAM`(确保 detectBackend 选 in-process)
- 在非 tmux 终端窗口内

步骤:
- [ ] 启动 `/tmp/gcode`(同会话已 unset 上述变量)
- [ ] 在 TUI 输入:「创建 inproc 团队」
  - 验证:`cat ~/.gcode/teams/inproc/config.json` 中 `backend` 为 `in-process`
- [ ] 在 TUI 输入:「派 bob 用 general-purpose,在 worktree 里 `echo step1 > /tmp/bob.txt`」
  - 验证:无新终端窗口/pane 出现(同进程 goroutine)
  - 验证:`/tmp/bob.txt` 内容 `step1`
- [ ] 等 bob 结束(`/team info inproc` 看 IsActive=false)
- [ ] 在 TUI 输入:「给 bob 发消息让他再加一行 step2」
  - 验证:`/tmp/bob.txt` 多一行 `step2`
  - 验证:`/team info inproc` 看 bob 在 active → idle 反复变化
- [ ] `/team delete inproc --force` 清理

**场景 3:Coordinator Mode 实跑**

环境准备:
- `.gcode/config.yaml` 加 `features:\n  coordinator_mode: true`(snake_case,不是 camelCase)
- 设环境变量 `GCODE_COORDINATOR_MODE=1`

步骤:
- [ ] `GCODE_COORDINATOR_MODE=1 /tmp/gcode`
- [ ] 观察 TUI 状态栏出现 `[COORDINATOR]` 标签
- [ ] 在 TUI 输入:「写一个 hello world 到 /tmp/coord_test.txt」
  - 预期:`write_file` **不在 Lead 工具集**(被 SetAllowedTools 剥夺),LLM 应该说"我没有 write_file 工具"并尝试用 bash 转写
  - 验证:`cat /tmp/coord_test.txt` 文件不存在(若用户拒掉 bash 的话)
- [ ] 在 TUI 输入:「跑 `git status`」
  - 预期:Agent 调 `bash`,工具正常执行(bash 在 Coordinator 白名单中)
  - 验证:输出含 git 状态信息
- [ ] 在 TUI 输入:「派几个队员探索 gcode 的 internal/agent 和 internal/team」
  - 预期:Lead 调 Agent + SendMessage 派出队员后,**不**立刻调 read_file/glob/bash 自己探索(被 Coordinator system prompt 中的纪律段约束)
  - 验证:Lead 派完队员的回复应该是"等待汇报中" 类似措辞;在队员发完 idle 消息前 Lead 屏幕没新工具调用

**场景 4:Plan 审批工作流**

环境准备:无特殊

步骤:
- [ ] 准备一个角色定义 `~/.gcode/agents/planner.md`,frontmatter 含 `permissionMode: plan`,body 简述「先制定计划」
- [ ] 启动 gcode,创建 team `plan-test`
- [ ] 在 TUI 输入:「派 planner 用 planner 角色,在 worktree 制定 hello world 程序的实现计划」
  - 预期:planner 队员以 plan 模式起步,生成计划后通过 SendMessage 发给 Lead
  - 验证:Lead mailbox 含计划消息
- [ ] 在 TUI 输入:「批准 planner 的计划」
  - 预期:Lead 调 `SendMessage(to="planner", type="plan_approval_response", payload={approve:true})`
  - 验证:planner 收到后切换权限模式,继续执行计划

## 失败回归

- [ ] gcode 启动时 `~/.gcode/teams/` 不存在,自动创建,不报错
- [ ] `~/.gcode/teams/<somename>/config.json` 内容损坏时,启动只 stderr 警告,跳过该 Team
- [ ] 创建 Team 时若 disk 写失败(可手动 chmod 模拟),返回 error,不留半成品目录
- [ ] mailbox 文件锁抢占冲突 10 次仍失败时,SendMessage 返回 error,不丢消息
- [ ] tmux 后端在 `tmux split-window` 失败时(非 tmux 会话),返回错误,Team.Members 不留半成品
- [ ] 协作工具被主 Agent 误调用(主 Agent 工具列表本应不含)时,工具自己也返回 error 兜底
```

### Python

````markdown
# Agent Team Spec## 背景

ch13 SubAgent 把任务从单 Agent 委派给子 Agent,实现了消息、权限账本、文件读缓存与 token 计数的隔离;ch14 Worktree 给每个子 Agent 配上独立工作目录,文件系统层并发也安全。但这两章合起来仍是「星型」拓扑——所有子 Agent 只能与主 Agent 通信,子 Agent 之间没有横向通道;主 Agent 既要决策、又要中转,既是大脑也是邮局。对「同时重构四个模块」「三个角度查同一个 bug」这类持续性、需要互相交流的工作,星型结构的瓶颈很明显。

本章把 gcode 从星型升级到「网状」:

- 主 Agent 创建 **Team** 后升任 **Lead**,Team 是一个长期存在的小组对象,记名称、负责人、成员花名册、持久化位置
- 每个 **队员**(Teammate)是一个独立的 Agent 实例,有自己的 Conversation、自己的 Worktree
- 三种执行后端 `tmux` / `iterm2` / `in-process` 覆盖不同环境;按优先级一次性自动检测,启动后不静默回退
- 队员之间通过**共享任务列表**与**邮箱**直接通信,不必经过 Lead 中转;协作工具仅在 Team 上下文出现
- 队员可暂停可续写,自然停下后 session 留盘,Lead 调 `SendMessage` 会从磁盘恢复后继续指派
- Lead 可选启用 **Coordinator Mode**(独立于 Team,但典型场景一起用),双锁机制下剥夺 write_file/edit_file 工具,只保留调度、读类操作与 shell(用于 git merge)
- 收敛阶段由 Lead 用 Bash 跑 `git merge` 逐个合各队员的 worktree 分支,冲突由 LLM 推理解决,搞不定就 `git merge --abort` 保留 worktree 上报用户

gcode 现有相关基础设施:
- ch13 `task.Manager` 已支持后台任务管理 + `send_message` 续派 + `AgentNameRegistry` (`by_name` 字段已是 name → id 映射);本章扩展为多 Team 寻址
- ch13 `AgentTool.execute` 已是子 Agent 启动入口,本章新增 `team_name` 参数走 Team spawn 分支
- ch13 工具过滤 `tool.apply_agent_tool_filter` 已支持多层防线;本章新增 Team 专属白名单(协作工具)与 Coordinator Mode 白名单
- ch14 `worktree.Manager` 已支持嵌套 slug(`team/alice` → `.gcode/worktrees/team+alice/`),本章直接复用做队员 worktree(slug 形式 `team-<team_name>/<member>`)
- ch12 session 持久化(`.gcode/sessions/<id>/conversation.jsonl`)按对话粒度落盘;本章给每个队员单独申请一个 session,队员 stop 不删 session,SendMessage 续派时通过 session 反序列化 Conversation
- ch10 `gcode.command` slash 命令系统,本章新增 `/team` 系列
- ch07 `permission` 已支持 `plan` 模式,本章给 `plan_mode_required` 队员的 Plan 提交-Lead 审批工作流套用同一引擎

本章**只做**到「Lead 多人协作 + Plan 审批 + Coordinator 收敛」。跨进程跨机器分布式团队、队员之间实时流式通信、复杂任务依赖约束(优先级 / deadline)、Windows 平台 iTerm2 适配均不在范围内。

## 目标- **G1**: 提供 `team.Team` 与 `team.Manager`——Team 封装小组生命周期(name、lead_agent_id、members、config_path);Manager 在单 gcode 进程内管理多个 Team(典型场景同时只有一个活跃 Team)
- **G2**: 提供 `TeamCreate` 工具——主 Agent 调用即创建 Team、调 `detect_backend` 确定后端、写 `~/.gcode/teams/<sanitized_name>/config.json`、把 Lead 注册成第一个成员;同名团队自动后缀 `-2` / `-3` 避免冲突
- **G3**: 扩展 `Agent` 工具——增加 `team_name` 可选参数,非空时走 Team spawn 分支:加载定义 → 创建队员 Worktree → 注入协作工具 → 按后端分流 spawn → 注册到 `AgentNameRegistry` → 写入 `team.members`
- **G4**: 提供 `TeamDelete` 工具——确认所有成员 `is_active=False` 后,删队员 worktree + 删 team 目录,Lead 退出团队;有活跃成员时拒绝删除
- **G5**: 三种执行后端 `tmux` / `iterm2` / `in-process`,统一抽象 `team.Backend` Protocol;`detect_backend` 按 `$TMUX → $TERM_PROGRAM=iTerm.app && shutil.which("it2") → shutil.which("tmux") → in-process` 优先级一次性决定,不做运行时回退
- **G6**: 队员注入 5 个协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate`(后者支持 `add_blocks` / `add_blocked_by` 依赖字段) / `SendMessage`;主 Agent 与普通 SubAgent 看不到这些工具
- **G7**: `SendMessage` 寻址支持 `to="<name>"`、`to="<agent_id>"`、`to="*"` 广播三种;通过 `AgentNameRegistry` 解析 name → agent_id,写邮箱;Tmux/iTerm2 后端额外通过 `send-keys` 唤醒目标 pane
- **G8**: 邮箱文件并发安全——每个收件人独占一个 lock 文件(`os.open(O_CREAT|O_EXCL)`),抢锁失败按 5-100ms 随机抖动重试,最多 10 次;持锁超过 10 秒视为 stale 直接清掉;消息文件 read-modify-write,走 `os.replace` 原子替换
- **G9**: 三种结构化消息——纯文本(必带 5-10 词 `summary`)、`shutdown_request` / `shutdown_response`(优雅退出协商)、`plan_approval_response`(Plan 审批回复,只允许 Lead 发送);全部走同一 SendMessage 入口,以 `type` 字段分流
- **G10**: 队员收到的未读消息在下一轮 Agent Loop 开头被读出,以 `<incoming-messages>` system reminder 形式注入到 LLM 输入;读后批量标记为 read
- **G11**: 队员 spawn 两种路径——指定 `subagent_type` 走定义式(从空白对话起步)、留空走 Fork 路径(继承 Lead 完整对话历史);Fork 路径受 `FORK_TEAMMATE` feature flag 控制,默认关闭
- **G12**: 队员 `run_to_completion` 结束后自动通知 Lead——团队 config 里把该成员 `is_active=False`、Lead 邮箱收到 `idle_notification`;队员的 Conversation 已通过 ch12 Writer 实时写入 session 文件
- **G13**: 队员续写——Lead 调 `SendMessage(to="alice", message="…")`,系统检测 alice 已 stop 时,从 ch12 session 反序列化 Conversation、新建一个 asyncio task 走 `run_to_completion(initial_message=new_message)`;Conv 沿用历史
- **G14**: `plan_mode_required=True` 的队员被 spawn 时强制以 plan 模式起步——计划生成后通过 SendMessage 发给 Lead,Lead 用 `plan_approval_response` 回复 approve 或 reject;approve 时队员权限模式切到 Lead 的当前模式继续执行,reject 时队员按 feedback 调整后重新提交
- **G15**: Coordinator Mode 独立于 Team——`is_coordinator_mode() = feature("COORDINATOR_MODE") and env_truthy(GCODE_COORDINATOR_MODE)`,两把锁全开才生效;开启后 Lead 工具集收窄到 `Agent / TeamCreate / TeamDelete / TaskCreate / TaskGet / TaskList / TaskUpdate / SendMessage / read_file / glob / grep / bash`(剥夺 `write_file` / `edit_file`),并注入 coordinator 系统提示词引导 Research / Synthesis / Implementation / Verification 四阶段
- **G16**: 收敛全部由 LLM 推理驱动——Lead 用 Bash 跑 `git merge worktree-team-<team>+<member> --no-ff -m "merge: <member>"` 逐个合,冲突由 Lead 用 read_file / edit_file / bash 自行解决;搞不定就 `git merge --abort`,保留队员 worktree,把冲突上下文上报给用户
- **G17**: 提供 TUI slash 命令 `/team list` / `/team info <name>` / `/team delete <name>` / `/team kill <member>`,辅助用户人工介入
- **G18**: 与 ch04~ch14 既有功能协同——主 Agent 平时(未 TeamCreate)看到的工具列表不变;协作工具仅在 Team 上下文出现;ch13 后台任务 / AdoptRunning / SendMessage 续派路径保留,Team 队员的续派复用同一套底层 `task.Manager`

## 功能需求### Team 数据结构与 Manager- **F1**: `team.Team` 字段——`name`(原始名)、`sanitized_name`(经 `sanitize` 处理后用于路径)、`lead_agent_id`、`members: list[TeammateInfo]`、`config_dir`(`<home_dir>/.gcode/teams/<sanitized_name>/`)、`config_path`(`<config_dir>/config.json`)、`created_at: datetime`、`backend: BackendType`
- **F2**: `team.TeammateInfo` 字段——`name`(Lead 分配的队员名,Team 内唯一)、`agent_id`(对应 `task.BackgroundTask.id`)、`agent_type`(使用的 subagent 定义名;Fork 路径下为 `""`)、`model`(覆盖,空表 inherit)、`worktree_path`(绝对路径)、`branch`(对应 worktree 分支名)、`backend_type`(可 per-member 不同)、`pane_id`(tmux pane / iterm2 split id,in-process 为空)、`is_active: bool | None`(`None` 或 `True` 表活跃,`False` 表空闲;终止后直接从 `members` 移除)、`plan_mode_required: bool`、`session_dir`(队员独立 session 目录绝对路径)
- **F3**: `team.Manager` 字段——`_lock: asyncio.Lock`、`teams: dict[str, Team]`(按 `sanitized_name` 索引)、`home_dir`(`Path.home()`)、`wt_mgr: worktree.Manager`、`task_mgr: task.Manager`、`registry: AgentNameRegistry`
- **F4**: `team.Manager(home_dir: Path, wt_mgr, task_mgr, reg) -> Manager`——校验 `<home_dir>/.gcode/teams/` 可写;扫描该目录还原 `teams` dict(每个子目录读一次 `config.json`,跳过解析失败的并 stderr 警告)
- **F5**: `await Manager.create(name: str, agent_type: str) -> Team`——
  1. `sanitized = sanitize(name)`(只保留 `[a-zA-Z0-9._-]`,其他替换为 `-`,首尾去 `-`,空字符串拒绝)
  2. 同名冲突时在 `sanitized` 后追加 `-2` / `-3` 直到唯一
  3. 创建 `config_dir`,落 `config.json`(原子写)
  4. 调 `detect_backend()` 写入 `team.backend`
  5. 取当前 Lead Agent ID(从调用上下文取,本期 Lead = 主 Agent,固定 `"lead"`)
  6. 把 Lead 注册成第一个成员(`TeammateInfo(name="lead", agent_id="lead", is_active=None)`)
  7. 加入 `teams` dict,返回 Team
- **F6**: `Manager.get(name: str) -> Team | None`——按 sanitized name 查询
- **F7**: `await Manager.delete(name: str, force: bool) -> None`——
  1. 取 Team;不存在抛 `TeamNotFoundError`
  2. 非 force 时若有 `member.is_active != False`(包括 None 和 True)抛 `TeamHasActiveMembersError`
  3. 逐个删队员 Worktree(调 `wt_mgr.remove(name, discard_changes=True)`,失败只警告不中断)
  4. 删队员 session 目录(`shutil.rmtree(member.session_dir, ignore_errors=True)`)
  5. 删 `config_dir`(`shutil.rmtree`)
  6. 从 `teams` dict 移除
- **F8**: `await Team.add_member(info: TeammateInfo) -> None`——校验 name 在 Team 内唯一;加入 `members`;持久化 `config.json`(原子写——先写 `.tmp` 再 `os.replace`)
- **F9**: `await Team.set_member_active(name: str, active: bool) -> None`——更新 `is_active`,持久化
- **F10**: `await Team.remove_member(name: str) -> None`——从 `members` 移除,持久化

### 后端检测与抽象- **F11**: `team.BackendType` 字符串枚举,取值 `"tmux"` / `"iterm2"` / `"in-process"`(用 `enum.StrEnum`)
- **F12**: `team.Backend` Protocol——
  ```python
  class Backend(Protocol):
      def type(self) -> BackendType: ...
      # spawn 在后端启动一个新队员;返回 (pane_id, agent_id)。
      # 对 Pane 后端,spawn 会执行 split-window / it2 split + send-keys 启动 CLI。
      # 对 in-process 后端,spawn 在事件循环里起一个 asyncio task 跑 run_to_completion。
      async def spawn(self, req: SpawnRequest) -> tuple[str, str]: ...
      # wake 用于消息到达时唤醒目标 pane。in-process 后端为 no-op。
      async def wake(self, pane_id: str, agent_id: str) -> None: ...
      # kill 终止 pane(Pane 后端)或 cancel task(in-process)。
      async def kill(self, pane_id: str, agent_id: str) -> None: ...
  ```
- **F13**: `team.SpawnRequest` 字段——`team_name`、`member_name`、`agent_id`、`worktree_path`、`session_dir`、`agent_type`、`model`、`initial_prompt`、`plan_mode_required`、`sub_agent: Any`(in-process 用,实际是 `agent.Agent`)、`conv: Any`(in-process 用,实际是 `conversation.Conversation`)、`task_mgr: Any`(in-process 用)
  - 对 Pane 后端(tmux / iterm2),`initial_prompt` **不**走命令行——在 `Backend.spawn` 调用前由 `team.spawn_teammate` 预写入 alice 的 mailbox(类型 `text`,from `lead`),子进程启动后读 mailbox 自然拿到。这样避免长 prompt 在命令行里 shell-quote 的边界问题。
- **F14**: `team.detect_backend() -> BackendType`——按以下优先级一次性决定:
  1. `os.environ.get("TMUX")` → `tmux`
  2. `os.environ.get("TERM_PROGRAM") == "iTerm.app"` && `shutil.which("it2")` → `iterm2`
  3. `shutil.which("tmux")` → `tmux`(外部 spawn 新 session)
  4. 否则 → `in-process`

### tmux 后端- **F15**: `gcode.team.backend.tmux.TmuxBackend` 实现 `Backend` Protocol
  - `spawn`:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`(横向 split,-P 打印 pane id,-F 指定格式);`cmd` 为 `python -m gcode --team-member --team <team_name> --member <member_name> --agent-id <agent_id> --session-dir <session_dir> --worktree <worktree_path> [--agent-type <type>] [--model <model>] [--plan-mode]`
  - `--agent-id` 是关键:Lead spawn 时已生成的 agent_id 直接传给子进程,子进程不需要读 Lead 还没写完的 `config.json` 找自己
  - 用 `asyncio.create_subprocess_exec` 跑 tmux,捕获 stdout 作为 pane_id
  - `wake`:`tmux send-keys -t <pane_id> "" Enter`(回车触发子进程 stdin reader 读到一行,立刻去 mailbox 轮询;in-process 后端无此动作)
  - `kill`:`tmux kill-pane -t <pane_id>`(忽略 pane 不存在错误)
- **F16**: 若当前在 tmux 会话外但本机有 tmux,spawn 走 `tmux new-session -d`(detached 新 session);若失败回落到错误而非 in-process(不静默回退)

### iterm2 后端- **F17**: `gcode.team.backend.iterm2.Iterm2Backend` 实现 `Backend` Protocol
  - `spawn`:`it2 split --new-pane --command "<cmd>"`,`<cmd>` 与 F15 同构(含 `--agent-id`);通过 `it2` CLI 解析输出取 pane id
  - `wake`:`it2 send-text --pane <pane_id> ""`(空文本即唤醒)
  - `kill`:`it2 close-pane --pane <pane_id>`

### in-process 后端- **F18**: `gcode.team.backend.inprocess.InProcessBackend` 实现 `Backend` Protocol
  - `spawn`:复用 `task.Manager.launch`——创建带 `cwd=worktree_path` 的子 Agent,在 asyncio task 里跑 `run_to_completion`;返回 `(pane_id="", agent_id=<task_id>)`,内部用 `task.BackgroundTask.id` 关联
  - `wake`:no-op(同进程,下一轮 Loop 自动读邮箱)
  - `kill`:调 `await task.Manager.stop(agent_id)`
- **F19**: in-process 后端的队员**只允许同步子 Agent**——其 `Agent` 工具看不到 `team_name` 参数(`team_name` 被拦截);后台子 Agent 也禁用(过滤 `run_in_background=True`)

### Pane 后端子进程的 team-member 模式- **F19a**: `python -m gcode --team-member` 在 Pane 后端被 spawn 的 gcode 子进程**不启动 TUI**(不构造 Textual App),而是跑一个自治协程(`src/gcode/cli/team_member.py` 的 `run_team_member`):
  1. 从 CLI 解析 `--team / --member / --agent-id / --session-dir / --worktree / --agent-type / --model / --plan-mode`
  2. `os.chdir(--worktree)`,让该进程的 `Path.cwd()` 与权限沙箱根都指到 worktree
  3. 构造**单独的** `team.Manager`、provider、registry、permission engine、hook engine(完整复用 Lead wire 代码,但不构造 TUI)
  4. 构造队员 `agent.Agent`,设 `dont_ask=True`(子进程无 TUI 接 ApprovalRequest)、注入 `<team-context>` reminder、用 `set_ctx_decorator` 注入 `TeammateContext`(含 mailbox client)
  5. 启动 stdin reader asyncio task:任何来自 tmux send-keys 的回车都推到 `wake_event`(`asyncio.Event`),触发立刻去 mailbox 轮询(0~2s 内响应)
  6. 进入主循环:
     - 读 `mailbox.read_unread(agent_id)`
     - 空 → `await asyncio.wait_for(wake_event.wait(), timeout=2.0)` 兜底轮询
     - 有未读:`text` 拼成 task,`plan_approval_response(approve=True)` 触发 `set_permission_mode(default)` + 续派 prompt,`shutdown_request` 触发优雅退出
     - 调 `await agent.run_to_completion(conv, task, events)` 让队员跑到底
     - 完成后:写 `summary="<name> idle"` 到 Lead mailbox,再 `await Team.set_member_active(name, False)`
     - 检测到 mailbox 目录已被删除(Lead 调用 `/team delete`)→ 优雅退出
- **F19b**: 该自治协程的最小事件转 stdout 打印:`Text` 直接 `print`、`ToolEvent` 打 `● tool(args)` 行、`Done` 打分隔横线、错误打 stderr。pane 内 UX 是只读的"日志流",不接受用户输入(任何回车都被 stdin reader 消费做 Wake 信号)
- **F19c**: 跨进程 `config.json` 写入并发:Lead 与子进程是不同进程,各持一份内存中的 Team 对象。`Team.add_member` 与 `Team.set_member_active` 在加锁后**先从磁盘 reload `members` 字段**再修改+原子 save(`_reload_from_disk_locked`)。否则会出现"子进程内存看不到自己,set_member_active 静默 no-op"的丢更新问题

### TeamCreate 工具- **F20**: 工具名 `TeamCreate`,参数 schema:
  - `team_name`(string,必填):团队名,经 sanitize 后做 `Team.sanitized_name`
  - `description`(string,可选):团队描述,写入 `config.json` 的 `description` 字段
  - `agent_type`(string,可选):本期保留位,实际不使用
- **F21**: `TeamCreate.execute`——
  1. 解析参数
  2. 调 `await manager.create(name, agent_type)` 创建 Team
  3. 返回 JSON `{"team_name":"<sanitized>","backend":"<type>","config_path":"<path>"}`
  4. Lead 创建 Team 后保持原有工具集(非 Coordinator Mode 下不剥夺工具)

### TeamDelete 工具- **F22**: 工具名 `TeamDelete`,参数 `team_name`(必填)、`force`(可选 bool)
- **F23**: `TeamDelete.execute`——调 `await manager.delete(name, force)`,返回成功/失败消息

### Agent 工具扩展 (team_name)- **F24**: `Agent` 工具参数 schema 新增字段:
  - `team_name`(string,可选):非空时走 Team spawn 分支
- **F25**: 当 `team_name` 非空,`Agent.execute` 走 Team 分支:
  1. 校验 `team_name` 对应的 Team 存在(`manager.get`),否则抛错
  2. 校验当前调用者权限:
     - 主 Agent / Lead → 允许
     - in-process 队员调 Team spawn → 拒绝(`InProcessTeammateNoSpawnError`)
     - Pane 队员可以调(README:Pane 队员拥有完整 Agent 工具),但 `team_name` 参数被屏蔽(队员不能往 Team 加人,只 Lead 在 Coordinator Mode 或普通 Lead 调用时可以)
  3. 加载 `SubAgentDefinition`(指定 `subagent_type` 走 Catalog;留空且 `FORK_TEAMMATE` 开启走 Fork 定义;留空且 flag 关闭则用 `general-purpose`)
  4. 调 `await wt_mgr.create(f"team-{sanitized}/{member_name}", "HEAD", False)` 创建 Worktree
  5. 申请新 session 目录(复用 `session` 包接口),作为 `session_dir`
  6. 构造 in-process 子 Agent(若后端为 in-process)或仅构造 SpawnRequest(若 Pane 后端);把协作工具注入到子 Agent 的 allowed tools 集合
  7. 注入队员系统提示词附录(F39)
  8. 注入 `<team-context>` initial system reminder 到子 Agent Conv
  9. **若是 Pane 后端**,在 `backend.spawn` 之前把 `initial_prompt` 作为 `text` 消息(`from=lead, summary=initial task`)预写入 alice 的 mailbox(F13);in-process 后端不需要,`initial_prompt` 直接作为 `task.Manager.launch` 的 task 参数
  10. 调 `await team.Backend.spawn(req)` spawn,记 `pane_id`
  11. 注册到 `AgentNameRegistry`:`member_name → agent_id`
  12. 构造 `TeammateInfo` 加入 `team.members`,持久化(F19c 的 reload-before-modify 兜底)
  13. 返回 JSON `{"member_name":"<name>","agent_id":"<id>","worktree":"<path>","backend":"<type>","pane_id":"<id 或空>"}`

### 协作工具- **F26**: `TaskCreate` 工具——参数 `title`(必填)、`description`(可选)、`assignee`(可选,队员名)、`blocked_by`(可选 list[str],任务 id);返回新建 `task_id`(`task_<6位 hex>`);写入 Team 的 `tasks.json`(原子)
- **F27**: `TaskGet` 工具——参数 `task_id`,返回任务详情
- **F28**: `TaskList` 工具——参数可选 `status` 过滤(`pending`/`in_progress`/`completed`/`blocked`);返回任务数组,带依赖关系标注(`blocked_by`、`blocks`、是否 `is_ready`(无未完成 blocker))
- **F29**: `TaskUpdate` 工具——参数 `task_id`(必填)、`title`(可选)、`description`(可选)、`status`(可选)、`assignee`(可选)、`add_blocks`(可选 list[str])、`add_blocked_by`(可选 list[str])、`remove_blocks` / `remove_blocked_by`(可选 list[str]);更新后持久化
- **F30**: `tasks.json` 结构:
  ```json
  {
    "tasks": [
      {
        "id": "task_a1b2c3",
        "title": "...",
        "description": "...",
        "status": "pending",
        "assignee": "alice",
        "blocked_by": ["task_xxx"],
        "blocks": ["task_yyy"],
        "created_at": 1234567890,
        "updated_at": 1234567890
      }
    ]
  }
  ```
  写入走 `<team_config_dir>/tasks.json`,read-modify-write,文件锁 `tasks.lock`(同邮箱 lock 机制)

### SendMessage 工具与邮箱- **F31**: `SendMessage` 工具——参数:
  - `to`(string,必填):队员名 / agent_id / `"*"` 广播
  - `summary`(string,纯文本消息时必填,5-10 词)
  - `message`(string,可选,纯文本消息体)
  - `type`(string,可选,默认 `"text"`):取值 `"text"` / `"shutdown_request"` / `"shutdown_response"` / `"plan_approval_response"`
  - `payload`(object,可选):结构化消息的载荷(如 `shutdown_response` 的 `{approve, reason}`)
- **F32**: 邮箱文件路径——`<team_config_dir>/mailbox/<agent_id>.json`,结构:
  ```json
  {
    "messages": [
      {
        "from": "lead",
        "to": "alice",
        "type": "text",
        "summary": "interface change",
        "content": "...",
        "payload": null,
        "timestamp": 1234567890,
        "read": false
      }
    ]
  }
  ```
- **F33**: `team.mailbox.Box` 提供 `await write(agent_id, msg)` / `await read(agent_id) -> list[Message]` / `await mark_read(agent_id, indices)` 接口
  - `write`:抢 `<team_config_dir>/mailbox/<agent_id>.lock`(`os.open(O_CREAT|O_EXCL|O_WRONLY)`),失败 5-100ms 随机抖动重试 10 次;持锁超 10 秒视为 stale(`Path.stat().st_mtime` 判定)直接删 lock 重试;成功后 read-modify-write,`os.replace` 原子替换
  - 广播 `to="*"` 时,write 对 Team 内除发件人外所有成员的 mailbox 各 write 一次
- **F34**: `SendMessage.execute`——
  1. 校验调用者在 Team 内
  2. 解析 `to`:若 `"*"` 走广播;否则通过 `registry.resolve(to)` 取 agent_id(name 优先,失败按 agent_id 直查);解析不到抛错
  3. `plan_approval_response` 仅 Lead 可发,否则抛错
  4. `shutdown_response` 只能发给 Lead,否则抛错
  5. 调 `await mailbox.write`
  6. 取目标的 `backend_type` 与 `pane_id`,若是 Pane 后端调 `await backend.wake(pane_id, agent_id)`
  7. 若目标 agent_id 已 stop(in-process 后端):触发续写(F45)
  8. 返回 `{"delivered_to":["<agent_id>"],"timestamp":<ts>}`

### Agent 名称注册表- **F35**: `team.AgentNameRegistry` 字段——`_lock: threading.Lock`、`by_name: dict[str, str]`(name → agent_id)、`by_id: dict[str, str]`(agent_id → name,反查)
- **F36**: 接口 `register(name, agent_id)`、`unregister(name)`、`resolve(name_or_id) -> str | None`、`name_of(agent_id) -> str | None`
- **F37**: 注册时机——`Agent` 工具 spawn 队员时(F25 step 10);`AgentTool` 的 `name` 参数非空时(ch13 已有,本章统一这套 registry,替换 `task.Manager.by_name` 的内部 dict)
- **F38**: 命名冲突——后注册的覆盖前注册的(README 称「弱引用,后启动覆盖前面的弱引用」)

### 队员系统提示词附录- **F39**: 在子 Agent 的 system_prompt 后追加(若 spawn 进 Team)以下文本(无变量):
  ```
  IMPORTANT: You are running as an agent in a team.
  Just writing a response in text is not visible to others
  on your team - you MUST use the SendMessage tool.
  The user interacts primarily with the team lead.
  Your work is coordinated through the task system
  and teammate messaging.
  ```
- **F39a**: 所有 Team 队员(三种后端共有)一律以 `dont_ask=True` 启动,**覆盖角色定义里的 `permission_mode`**。理由:队员没有可交互的 TUI 接 `ApprovalRequest`(in-process 走 task.Manager 聚合事件不响应、Pane 子进程更没有 TUI),Ask 工具会无人应答地永远阻塞。队员的安全边界由 allowed 工具集 + Worktree 隔离 + Plan 模式控制,不靠逐次 ask 弹窗(子进程没人在看)。
- **F40**: 在 spawn 时把 `<team-context>` 注入子 Conv 的首条 system reminder:
  ```
  <team-context>
  team: <team_name>
  你的成员名: <member_name>
  你的 agent_id: <agent_id>
  worktree 目录: <worktree_path>
  当前团队成员: <name1>(<role1>), <name2>(<role2>) ...
  </team-context>
  ```

### 邮箱读取与消息注入- **F41**: 子 Agent 的 Loop 在每轮请求 LLM **之前**先调 `await mailbox.read(agent_id)`;若有未读消息,构造 `<incoming-messages>` system reminder 追加到本轮请求的 system_reminders,然后调 `mark_read`
- **F41a**: Lead 侧不通过 ctx hook 自动读 mailbox(Lead 没有 `TeammateContext`),而是由 TUI 在 `on_mount` 启动后台 asyncio task `consume_lead_mail`(实现于 `src/gcode/tui/tasks.py`):
  - 每秒调 `await manager.poll_lead_mailboxes()`,遍历所有 Team 的 `<config_dir>/mailbox/lead.json` 读未读消息,标 read,返回 `list[LeadMessage]`
  - 把这批消息渲染成 `<team-update>` reminder(与 `<incoming-messages>` 不同,Lead 视角语义更清晰;消息内容截断上限 8000 字符,允许队员的完整报告完整透传),调 `runtime.append_reminders(...)` 推到 `pending_reminders`
  - **同时**往 `lead_mail_event: asyncio.Event` `set()` 一个信号
  - Lead 下一轮 Run 迭代头部 `build_reminder` 自动取出。**Lead 即便正在长 Run 中也能中途惊醒**——下一个 LLM 调用前就会看到队员更新
  - 这是 Pane 后端队员通知 Lead 的关键路径:in-process 队员还有 `task.Manager.subscribe_done` → TUI `<task-notification>` 的额外路径,但 Pane 队员只能靠 mailbox + 本机制
- **F41b**: Lead idle 时的自动续推。TUI 通过 `await wait_for_lead_mail(event)` 协程阻塞在 `lead_mail_event` 上,收到信号后触发 message handler:
  - 若 `app.state == SessionState.IDLE`,调 `await begin_autonomous_turn`:合成一条 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."` 加入对话历史(用户在 RichLog scrollback 也看得见,清楚是系统通知触发而非自己输入),然后走 `begin_turn` 启 Run
  - 若 `app.state` 非 idle(STREAMING/APPROVING):reminder 已经在 pending_reminders 里,Lead 当前 Run 的下一轮迭代头部自然取出,不需要主动 wake
  - 末尾 `event.clear()` 让后续信号也能接住
  - 这避免了"队员都 idle 了,Lead 在 idle 等用户输入,reminder 静默积累没人取"的卡死场景——这正是 ch15 协作 UX 的关键
- **F42**: `<incoming-messages>` 格式:
  ```
  <incoming-messages>
  收到 N 条新消息:
  [1] 来自 <from>(type=<type>,ts=<时间>): <summary>
      <content 前 200 字>
  [2] ...
  </incoming-messages>
  ```
- **F43**: 收到 `shutdown_request` 时,队员可在下一轮自主选择回复 `shutdown_response(approve=True)` 然后停止,或 `approve=False` 拒绝并附 reason(LLM 决策,不强制)
- **F44**: 收到 `plan_approval_response(approve=True)` 时,队员的权限模式自动切换到 Lead 当前模式(从 Team config 取);`approve=False` 时队员根据 `feedback` 调整重新发 Plan

### 队员空闲与续写- **F45**: 队员 `run_to_completion` 自然结束时(`task.Manager._run_task` 完成路径):
  1. 调 `await Team.set_member_active(member_name, False)`
  2. 给 Lead 邮箱写一条 `idle_notification`(`type="text", summary="<member> idle", content="agent <id> finished work, available for new tasks"`)
- **F46**: SendMessage 检测到目标 agent_id 已 stop 且为 in-process 队员(`task.BackgroundTask.status` 不是 `Running`):
  1. 从 `TeammateInfo.session_dir` 反序列化 Conversation(`session.load`)
  2. 调 `await task.Manager.send_message(parent_ctx, name, message)` 复用 ch13 已有续派接口
  3. `task.Manager.send_message` 重置 `status=Running`,起新 asyncio task 跑 `run_to_completion(new_message)`
  4. 续派前调 `await Team.set_member_active(member_name, True)`
- **F47**: Pane 后端队员的续写——SendMessage 写邮箱后,目标 pane 内的 gcode 实例下一轮 Loop 自然读到消息;若 pane 已死(`tmux list-panes` 查不到 `pane_id`),报错让 Lead 决定是否重新 spawn

### Plan 审批工作流- **F48**: `Agent` 工具 spawn 队员时,若 `plan_mode_required=True`(来自 `SubAgentDefinition` 的新字段或 spawn 参数),把子 Agent 的初始 `permission.Mode` 设为 `plan`
- **F49**: 队员在 plan 模式下生成 Plan 后(通过常规 LLM 推理),用 `SendMessage(to="lead", type="text", summary="plan ready", content="<plan text>")` 发给 Lead——本期不强制结构化 Plan 类型(Lead 自行识别)
- **F50**: Lead 用 `SendMessage(to="<member>", type="plan_approval_response", payload={"approve":True|False,"feedback":"..."})` 回复
- **F51**: 队员收到 `plan_approval_response`:
  - `approve=True`:从 Team config 读 Lead 当前 `permission_mode`(本期固定 `default`),切到该模式继续执行 plan
  - `approve=False`:把 `feedback` 当作新的用户消息加入对话,重新进入 plan 模式

### Coordinator Mode- **F52**: 提供 `coordinator.is_enabled() -> bool` 函数:
  ```python
  def is_enabled(cfg: Config) -> bool:
      if not feature_has(cfg, "COORDINATOR_MODE"):
          return False
      return env_truthy(os.environ.get("GCODE_COORDINATOR_MODE", ""))
  ```
  `feature_has` 通过 `gcode.config` 读 `features.coordinator_mode` 字段;`env_truthy` 接受 `"1"` / `"true"` / `"yes"`(大小写不敏感)
- **F53**: Coordinator Mode 允许工具白名单常量:
  ```python
  COORDINATOR_ALLOWED_TOOLS: list[str] = [
      "Agent", "TeamCreate", "TeamDelete",
      "TaskCreate", "TaskGet", "TaskList", "TaskUpdate",
      "SendMessage",
      "read_file", "glob", "grep", "bash",
  ]
  ```
- **F54**: Lead 启动时(`tui` 主流程构造 Agent 后),若 `coordinator.is_enabled()`:
  1. 把 Lead 的 allowed tools 设为 `COORDINATOR_ALLOWED_TOOLS`(调 `agent.set_allowed_tools` 已有接口)
  2. 在 system_prompt 后追加 coordinator 提示词(F55)
  3. TUI 状态栏显示 `[COORDINATOR]` 模式标签
- **F55**: Coordinator 系统提示词追加在 system_prompt 末尾,核心是"四阶段 + 派完不许自己干"纪律。最终文案见 `src/gcode/coordinator/coordinator.py:SYSTEM_PROMPT_SUFFIX`,关键约束:
  - **派完队员就停手等汇报**:派出 Agent / SendMessage 后**禁止**立刻调 read_file / glob / grep / bash 自己探索;**禁止**用 sleep / TaskList 轮询凑时间。`task.Manager` 完成时自然推送 `<task-notification>` reminder,Lead 下一轮被唤醒后再继续
  - 唯一该做的事:发一行总结"已派 N 名队员探索 X,等结果",让本轮结束
  - 允许自己用 read_file/glob/grep 的场景仅限:Research 第一次目标定位;Synthesis 阶段读**队员产出的报告文件**;Verification 阶段 git diff / git status 等收敛操作

  这段纪律是为了对抗"LLM 派完队员后等不及自己 glob 代码库重复劳动"的常见行为——纯 prompt 引导,不强制(LLM 偶尔仍会越线,弱模型尤甚)。

### 收敛阶段- **F56**: 收敛由 LLM 推理驱动,**不提供专门的 merge 工具**——Lead(无论是否 Coordinator Mode)在所有任务 `completed` 后,自主用 Bash 跑:
  ```bash
  git merge worktree-team-<sanitized_team>+<member> --no-ff -m "merge: <member>"
  ```
- **F57**: 冲突解决也由 Lead 推理——Lead 用 `read_file` 看冲突文件、`edit_file`(非 Coordinator Mode)或 `bash`(Coordinator Mode)写入解决方案、`bash` 跑 `git add` + `git commit`
- **F58**: 回滚——Lead 判断搞不定时,自主调 `bash` 跑 `git merge --abort`,然后给用户报告冲突文件 + 队员 worktree 路径;**不删队员 worktree**### TUI Slash 命令- **F59**: `/team list`——遍历 `manager.teams`,每行 `<name>  <backend>  <member_count> 成员  [<active>/<total>] 活跃`
- **F60**: `/team info <name>`——展示 Team 详情:配置路径、各成员的 name/agent_id/backend/worktree_path/is_active/任务计数
- **F61**: `/team delete <name> [--force]`——调 `await manager.delete(name, force)`
- **F62**: `/team kill <member>`——查到 member 所属 Team,调对应 backend.kill,然后 `remove_member`

### 持久化与恢复- **F63**: `~/.gcode/teams/<sanitized_name>/config.json` 结构:
  ```json
  {
    "name": "...",
    "sanitized_name": "...",
    "lead_agent_id": "lead",
    "backend": "tmux",
    "description": "",
    "created_at": 1234567890,
    "members": [
      {
        "name": "alice",
        "agent_id": "agent-a1b2c3d",
        "agent_type": "worker",
        "model": "",
        "worktree_path": "/abs/path/.gcode/worktrees/team-foo+alice",
        "branch": "worktree-team-foo+alice",
        "backend_type": "tmux",
        "pane_id": "%5",
        "is_active": null,
        "plan_mode_required": false,
        "session_dir": "/abs/path/.gcode/sessions/<id>"
      }
    ]
  }
  ```
  所有写操作原子(先写 `.tmp` 再 `os.replace`),受 `Team._lock` 保护。**跨进程**(Pane 后端)下,Lead 与子进程是不同进程的不同 Team 内存对象——`add_member` 与 `set_member_active` 在加锁后**先 `_reload_from_disk_locked` 重读 disk members**再改写+ atomic save(F19c)
- **F64**: gcode 启动时(`team.Manager` 构造)扫描所有 Team 目录:
  - 解析 `config.json`,失败的目录跳过并 stderr 警告
  - **不**自动恢复 in-process 队员(进程重启后 in-process 队员状态丢失,is_active 视为 False)
  - Pane 队员根据 `pane_id` 探测后端是否仍在(`tmux has-session` / `it2 list-panes`),不在的 is_active 标 False
- **F65**: 队员 session 沿用 ch12 session 持久化机制,路径 `<project_root>/.gcode/sessions/<id>/conversation.jsonl`;Team 删除时一并删除
- **F66**: `Manager.delete(name, force=True)` 步骤(顺序重要):
  1. 持锁,校验 `force` 或全员 is_active=False
  2. 对每个非 lead 成员:用 `backend.new` 解析其 `backend_type` 拿 `Backend` 实例,调 `await backend.kill(pane_id, agent_id)` 杀掉 pane(tmux/iterm2)或 cancel asyncio task(in-process);Pane 子进程检测到 mailbox 目录消失会自行优雅退出兜底
  3. 调 `await _cleanup_member_resources` 删 session 目录与 worktree
  4. `shutil.rmtree(team.config_dir)` 删整个 Team 目录
  5. 从 Manager 的 in-memory dict 移除

## 非功能需求- **N1**: 主 Agent 平时(未 TeamCreate)看到的工具列表保持稳定——`TeamCreate` / `TeamDelete` 总是可见;`Agent` 工具的 `team_name` 参数对模型可见但仅在调用时校验
- **N2**: 协作工具(TaskCreate 等)仅在队员上下文出现,主 Agent 与普通 SubAgent 看不到——通过 `apply_agent_tool_filter` 在 spawn 时收窄
- **N3**: 邮箱写入对所有后端共用一套并发安全机制(文件锁);in-process 多 asyncio task 写同一 mailbox 也由文件锁串行
- **N4**: 所有 Team 状态变更受 `Team._lock`(`asyncio.Lock`)保护;Team 之间互不相关,各自一把锁;`Manager._lock` 仅保护 `teams` dict
- **N5**: 后端 spawn / kill 调用不持 `Team._lock`(避免长锁);只在更新 `members` 时短暂持锁
- **N6**: 与 ch04~ch14 既有测试零破坏——`pytest` 全绿
- **N7**: 中文友好——错误消息、TUI 输出、coordinator 提示词全部中文(对齐 gcode 其他模块风格);代码注释中文
- **N8**: Coordinator Mode 一旦启用,Lead 不可在运行时解锁(避免 LLM 被注入后自行解锁);取消的唯一方式是退出 gcode 重启
- **N9**: 权限沙箱(`src/gcode/permission/sandbox.py`)允许写入项目根**之外**的 `/tmp` 与 macOS 真实路径 `/private/tmp` 作为系统临时目录白名单。理由:工具脚本和队员经常需要 `/tmp` 做中转文件,严格限定在项目根内会导致大量正常用法被沙箱误杀。这一开放对 file-class 工具(read_file / write_file / edit_file)生效;bash 走 exec-class 权限,本来就不受沙箱约束

## 不做的事

- 跨 gcode 进程的 Team 共享(同一仓库同一时刻只支持一个 gcode 实例操作活跃 Team)
- 跨机器分布式 Team
- 队员之间实时流式通信(走 mailbox 文件 + 轮询/Wake,不走 socket)
- 复杂任务依赖约束(优先级、deadline、SLA)
- 任务自动分配(Lead 与队员都靠 LLM 推理领任务,系统不做调度)
- 队员的细粒度资源限额(token 上限、超时硬限制)
- Plan 审批的结构化 Plan 类型(本期 Plan 文本就是 SendMessage content,Lead 自行识别)
- Windows 平台特殊适配(iTerm2 后端仅 macOS;tmux 在 WSL 可用但不保证;本期以 macOS / Linux 为主)
- Coordinator Mode 的运行时解锁与重新进入
- 跨 Team 寻址(SendMessage 只能在同一 Team 内寻址)
- 插件来源的 Team 后端

## 验收标准- **AC1**: `team.Manager(...)` 在 `~/.gcode/teams/` 不存在时自动创建;已有时正确扫描子目录还原 `teams` dict
- **AC2**: `await manager.create("refactor auth", "")` 把 `"refactor auth"` sanitize 为 `"refactor-auth"`,在 `~/.gcode/teams/refactor-auth/config.json` 落地,`backend` 字段反映 `detect_backend` 结果
- **AC3**: 同名 Team 二次 create 自动后缀 `-2`,目录与 sanitized_name 都生效
- **AC4**: `await manager.delete(name, False)` 在有 `is_active!=False` 成员时抛 `TeamHasActiveMembersError`,目录仍在
- **AC5**: `await manager.delete(name, True)` 删 Worktree、删 session 目录、删 config_dir
- **AC6**: `detect_backend()` 在 `$TMUX` 设置时返回 `tmux`;未设但 `$TERM_PROGRAM==iTerm.app` 且 `it2` 可执行返回 `iterm2`;都无但 `tmux` 二进制在 PATH 返回 `tmux`;否则 `in-process`
- **AC7**: `Agent` 工具带 `team_name="<existing>"` 时,在 `.gcode/worktrees/team-<sanitized>+<member>/` 落地 Worktree、调对应 backend.spawn 并在 `team.members` 里出现该成员;不带 `team_name` 时维持 ch13 原行为
- **AC8**: in-process 后端队员的 `Agent` 工具调用 `team_name` 参数被拦截,抛 `InProcessTeammateNoSpawnError`
- **AC9**: 协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage` 在主 Agent 工具列表里**不**可见;在 Team 队员的工具列表里**可见**
- **AC10**: `TaskCreate` 落 `<team_config_dir>/tasks.json`,`TaskUpdate(task_id, add_blocked_by=[id])` 正确更新双向 `blocked_by` / `blocks` 关系
- **AC11**: `TaskList(status="pending")` 返回的任务带 `is_ready` 字段,反映其 `blocked_by` 是否全部 `completed`
- **AC12**: `SendMessage(to="alice", summary="hi", message="hello")` 在 `<team_config_dir>/mailbox/<alice_agent_id>.json` 追加一条 unread 消息
- **AC13**: `SendMessage(to="*", ...)` 广播给 Team 内除发件人外所有成员;每人邮箱各得一条
- **AC14**: 并发 10 个 asyncio task 同时向同一 mailbox `write`,最终 10 条消息全部落盘且无丢失/无截断(集成测试)
- **AC15**: mailbox lock 文件 `Path.stat().st_mtime` 超过 10 秒时,新的 write 会清掉旧 lock 并继续(集成测试)
- **AC16**: 队员 LLM 调用前,未读消息以 `<incoming-messages>` reminder 注入 system_reminders;调用后标记 read(单测断言)
- **AC17**: 队员 `run_to_completion` 自然结束后,`team.config.json` 里该成员 `is_active=False`,Lead mailbox 收到 `summary="<member> idle"` 消息
- **AC18**: `SendMessage(to="alice", message="new task")` 当 alice 已 stop 时,从其 session_dir 恢复 Conv 并续派(in-process 后端,task.Manager 状态从 Cancelled/Completed 回到 Running)
- **AC19**: `Agent(team_name="t", subagent_type="planner", plan_mode_required=True, ...)` spawn 后,该队员初始权限模式为 `plan`
- **AC20**: Lead 发 `SendMessage(to="planner", type="plan_approval_response", payload={"approve":True})` 后,planner 队员下一轮权限模式切回 `default`
- **AC21**: `feature_has(cfg, "COORDINATOR_MODE")=True` 且 `GCODE_COORDINATOR_MODE=1` 时,Lead 的 allowed tools 收窄为 `COORDINATOR_ALLOWED_TOOLS`,`write_file` / `edit_file` 不在其中;TUI 状态栏显示 `[COORDINATOR]`
- **AC22**: Coordinator Mode 关闭时,Lead 工具列表与 ch13 一致(`write_file` / `edit_file` 可见)
- **AC23**: tmux 后端 spawn 后,`tmux list-panes` 看到新 pane,pane 内 gcode 实例启动并连接到该 Team
- **AC24**: tmux 后端 `wake(pane_id, agent_id)` 通过 `tmux send-keys` 触发目标 pane 输入(集成测试可观察 pane 内容)
- **AC25**: in-process 后端队员与主 Agent 在同一进程内运行,共享 `task.Manager`,但有独立 `cwd=worktree_path`
- **AC26**: `/team list` slash 命令输出含所有 Team 摘要;`/team info <name>` 输出成员详情;`/team delete <name>` 调 `manager.delete`
- **AC27**: 项目能正常启动 `python -m gcode`;`ruff check src/` 通过;`pytest` 全部通过
- **AC28**: tmux 实跑(端到端):
  - 步骤 1:在 tmux 会话内启动 `gcode`
  - 步骤 2:输入 prompt 让主 Agent 调 `TeamCreate(team_name="demo")`,看到状态栏出现 team 标识,`~/.gcode/teams/demo/config.json` 落地
  - 步骤 3:Agent 调 `Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="在 worktree 里 echo hello > /tmp/test_alice.txt")`
  - 步骤 4:观察 tmux 新增 pane,pane 内出现 gcode 子实例;`.gcode/worktrees/team-demo+alice/` 目录创建;`/tmp/test_alice.txt` 文件创建,内容 `hello`
  - 步骤 5:`/team info demo` 显示 alice 成员
  - 步骤 6:Lead 调 `SendMessage(to="alice", summary="ping", message="再写一行 world 到 /tmp/test_alice.txt")`,观察 alice pane 被唤醒(send-keys 触发)、`/tmp/test_alice.txt` 多一行 `world`
  - 步骤 7:`/team delete demo --force`,worktree 和 team 目录清空
- **AC29**: in-process 后端实跑(端到端,不依赖 tmux):
  - 步骤 1:`unset TMUX TERM_PROGRAM`,启动 `gcode`(自动 fallback in-process)
  - 步骤 2:主 Agent 调 `TeamCreate("inproc")`,创建后端为 `in-process`
  - 步骤 3:`Agent(team_name="inproc", name="bob", prompt="...")` 在同进程 asyncio task 启动 bob
  - 步骤 4:bob 完成后 `team.config.json` 标记 `is_active=False`、Lead mailbox 收到 idle 消息
  - 步骤 5:Lead 调 `SendMessage(to="bob", message="再做一件事")`,bob 从 session_dir 恢复对话上下文继续
- **AC30**: Coordinator Mode 实跑——`GCODE_COORDINATOR_MODE=1` 启动 gcode,主 Agent 的 `write_file` 工具调用被拒绝(is_error=True);`bash git merge` 调用允许
````

````markdown
# Agent Team Plan## 架构概览

本章引入 `gcode.team` 顶层包,把 ch13 SubAgent 的「子 Agent」扩展为「Team 队员」。整体分四层:

1. **数据模型层**(`team/types.py` + `team/manager.py` + `team/persistence.py`)——Team、TeammateInfo 数据结构与持久化
2. **后端层**(`team/backend/`)——`Backend` Protocol 与三种实现 tmux / iterm2 / inprocess,屏蔽 spawn 差异
3. **协作层**(`team/mailbox/`、`team/registry/`、`team/tasks/`)——邮箱(含文件锁)、AgentNameRegistry、共享任务列表
4. **工具与集成层**(`team/tools/` + `agent` 包扩展 + `coordinator` 包)——5 个协作工具 + `Agent` 工具的 `team_name` 分支 + Coordinator Mode

Lead 仍是 `tui.GCodeApp.main_agent`——本期 Lead 没有独立类型,通过 `coordinator.is_enabled()` 在启动时收窄其工具集即可。

依赖方向(单向):
```
tui  ──→  agent  ──→  team  ──→  team/{backend,mailbox,registry,tasks,tools}
                       └──→  worktree(ch14)、task(ch13)、session(ch12)、subagent(ch13)
```
`team` 不反向依赖 `agent` 包(避免环);`agent` 通过新增的 `TeamHook` Protocol 注入 team 行为。

## 核心数据结构### `team.Team`

```python
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

@dataclass
class Team:
    name: str                       # 用户给的原始名
    sanitized_name: str             # 经 sanitize 后用于路径,Team 主键
    lead_agent_id: str              # 固定 "lead"(本期 Lead = 主 Agent)
    backend: "BackendType"          # 全 team 默认后端;可被 member 覆盖
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    members: list["TeammateInfo"] = field(default_factory=list)

    # 派生路径(不持久化)
    config_dir: str = ""
    config_path: str = ""           # <config_dir>/config.json
    tasks_path: str = ""            # <config_dir>/tasks.json
    mailbox_dir: str = ""           # <config_dir>/mailbox/

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)
```

### `team.TeammateInfo`

```python
@dataclass
class TeammateInfo:
    name: str
    agent_id: str
    agent_type: str = ""             # "" 表 Fork
    model: str = ""                  # "" 表 inherit
    worktree_path: str = ""          # 绝对路径
    branch: str = ""
    backend_type: "BackendType" = "in-process"
    pane_id: str = ""                # tmux pane id / iterm2 split id / "" for in-process
    is_active: bool | None = None    # None/True 活跃,False 空闲;不存在视为终止
    plan_mode_required: bool = False
    session_dir: str = ""            # 绝对路径
```

序列化通过手写 `to_dict` / `from_dict` 完成(F19c 的 reload 流程需要细粒度控制 `is_active` 的 None 语义)。

### `team.Manager`

```python
@dataclass
class Manager:
    teams: dict[str, Team] = field(default_factory=dict)   # 按 sanitized_name 索引
    home_dir: str = ""
    wt_mgr: "worktree.Manager" = None
    task_mgr: "task.Manager" = None
    registry: "AgentNameRegistry" = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)
```

### `team.BackendType`

```python
from enum import StrEnum

class BackendType(StrEnum):
    TMUX = "tmux"
    ITERM2 = "iterm2"
    IN_PROCESS = "in-process"
```

### `team/backend.Backend`

```python
from typing import Protocol, Any
from dataclasses import dataclass

class Backend(Protocol):
    def type(self) -> BackendType: ...
    async def spawn(self, req: "SpawnRequest") -> tuple[str, str]: ...   # (pane_id, agent_id)
    async def wake(self, pane_id: str, agent_id: str) -> None: ...
    async def kill(self, pane_id: str, agent_id: str) -> None: ...

@dataclass
class SpawnRequest:
    team_name: str
    member_name: str
    agent_id: str
    worktree_path: str
    session_dir: str
    agent_type: str
    model: str
    initial_prompt: str
    plan_mode_required: bool

    # in-process 专用——同进程后端直接复用这三个对象
    sub_agent: Any = None       # agent.Agent
    conv: Any = None            # conversation.Conversation
    task_mgr: Any = None        # task.Manager
```

### `team/mailbox.Message` / `Box`

```python
from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any

class MessageType(StrEnum):
    TEXT = "text"
    SHUTDOWN_REQUEST = "shutdown_request"
    SHUTDOWN_RESPONSE = "shutdown_response"
    PLAN_APPROVAL_RESPONSE = "plan_approval_response"

@dataclass
class Message:
    from_: str                       # json key "from"
    to: str
    type: MessageType
    summary: str
    content: str
    payload: dict[str, Any] | None = None
    timestamp: int = 0
    read: bool = False

class Box:
    def __init__(self, dir_: str) -> None:
        self._dir = dir_             # <team_config_dir>/mailbox/

    async def write(self, agent_id: str, msg: Message) -> None: ...
    async def read(self, agent_id: str) -> list[Message]: ...
    async def read_unread(self, agent_id: str) -> tuple[list[int], list[Message]]: ...
    async def mark_read(self, agent_id: str, indices: list[int]) -> None: ...
```

文件锁机制内置在 `Box` 内,所有公开方法都走锁。

### `team/registry.AgentNameRegistry`

```python
import threading

class AgentNameRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_name: dict[str, str] = {}   # name → agent_id
        self._by_id: dict[str, str] = {}     # agent_id → name

    def register(self, name: str, agent_id: str) -> None: ...
    def unregister(self, name: str) -> None: ...
    def resolve(self, name_or_id: str) -> str | None: ...
    def name_of(self, agent_id: str) -> str | None: ...
```

注意:本章把 `task.Manager._by_name` 替换/委托给这套 registry——`task.Manager` 改为持一个 `AgentNameRegistry` 引用。

### `team/tasks.Store`

```python
from enum import StrEnum
from dataclasses import dataclass, field

class Status(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    status: Status = Status.PENDING
    assignee: str = ""
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0

class Store:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def create(self, t: Task) -> str: ...
    async def get(self, id_: str) -> Task: ...
    async def list_(self, filter_: "Filter") -> list[Task]: ...
    async def update(self, id_: str, patch: "Patch") -> None: ...
```

### `coordinator` 包

```python
# src/gcode/coordinator/__init__.py
def is_enabled(cfg) -> bool: ...
def allowed_tools() -> list[str]: ...
def system_prompt_suffix() -> str: ...
```

仅 3 个纯函数,无状态。

## 模块设计### `gcode.team`(顶层)**职责:** Team / TeammateInfo / Manager 数据结构与持久化,跨子包的协调入口。
**对外接口:** `Manager(...)`、`Manager.create/get/delete`、`Team.add_member/set_member_active/remove_member`
**依赖:** `worktree`、`task`、`session`、`team.backend`、`team.mailbox`、`team.registry`、`team.tasks`

### `gcode.team.backend`**职责:** 屏蔽 tmux / iterm2 / in-process spawn 差异。
**对外接口:** `Backend` Protocol、`detect() -> BackendType`、`new_backend(t: BackendType, **deps) -> Backend`
**依赖:** `team`(取常量)、`agent` 与 `task`(in-process 实现用)

注意:`backend` 包反向依赖 `agent` 会成环。解决:`in-process` 实现走「接口适配」——`backend.spawn` 接收 `SpawnRequest` 中的 `sub_agent: Any`,由调用方(`team` 包)预先构造好;`backend` 包只做调度,不知道 `agent.Agent` 类型。或者把 `in-process` 实现单独提到 `team.backend.inprocess`,允许它依赖 `agent`,而 `team.backend.tmux` / `iterm2` 不依赖。

**采用方案:** 三种后端各一个子模块(`tmux.py` / `iterm2.py` / `inprocess.py`),每个独立实现 `Backend` Protocol,工厂函数 `new_backend(...)` 接收所需依赖。`inprocess` 子模块依赖 `agent` 包没问题(`agent` 在更低层)。

### `gcode.team.mailbox`**职责:** 邮箱文件 + 文件锁的读写。
**对外接口:** `Box.write/read/mark_read`、`Message` 类型
**依赖:** 仅 stdlib(`os`、`json`、`asyncio`、`pathlib`)

### `gcode.team.registry`**职责:** Agent name ↔ agent_id 双向映射。
**对外接口:** `register/unregister/resolve/name_of`
**依赖:** 仅 stdlib

### `gcode.team.tasks`**职责:** 共享任务列表的 CRUD + 依赖图维护。
**对外接口:** `Store.create/get/list_/update`、`Task`、`Filter`、`Patch` 类型
**依赖:** 仅 stdlib

### `gcode.team.tools`**职责:** 5 个协作工具实现(TaskCreate、TaskGet、TaskList、TaskUpdate、SendMessage)+ 2 个 Team 管理工具(TeamCreate、TeamDelete)。
**对外接口:** 每个工具一个工厂函数 `new_xxx_tool(mgr: team.Manager) -> tool.Tool`
**依赖:** `tool`、`team`、`team.{mailbox,registry,tasks}`

### `gcode.coordinator`**职责:** Coordinator Mode 的开关检测、工具白名单、系统提示词。
**对外接口:** `is_enabled() -> bool`、`allowed_tools() -> list[str]`、`system_prompt_suffix() -> str`
**依赖:** `config`(读 feature flag)

### `agent` 包扩展

- 新增 `agent.TeamHook` Protocol:
  ```python
  class TeamHook(Protocol):
      # spawn_teammate 让 Agent 工具委托给 Team Manager 处理 team_name 分支。
      # 返回 final_text(立即返回 task_id JSON 描述)。
      async def spawn_teammate(self, req: "TeamSpawnRequest") -> str: ...
      # is_teammate_context 判断当前上下文是否在某队员的执行上下文中(用于拦截嵌套 spawn)。
      def is_teammate_context(self, ctx) -> tuple[str, str, bool]: ...
  ```
- `AgentTool` 持一个 `team_hook: TeamHook | None` 字段(可选,None 时降级为 ch13 行为)
- `Agent.execute` 在 `team_name != ""` 时调 `team_hook.spawn_teammate`

### `task` 包扩展

- `task.Manager` 持一个 `name_reg: AgentNameRegistry` 引用(原 `_by_name` 字段废弃,改委托)
- `task.Manager.send_message` 复用——Team 模块续派直接调它

### `tui` 包扩展

- `GCodeApp` 新增字段 `team_mgr: team.Manager`
- 注入 `/team` 系列 slash 命令(`src/gcode/command/builtin_team.py`)
- 状态栏新增 `[COORDINATOR]` 标签(若 `coordinator.is_enabled()`)

## 模块交互### TeamCreate 调用路径

```
LLM 调 TeamCreate(team_name="demo")
  ↓
tools.TeamCreate.execute
  ↓
await team.Manager.create("demo", "")
  ↓
1. sanitize("demo") → "demo"
2. detect_backend() → "tmux"
3. mkdir ~/.gcode/teams/demo/
4. mkdir ~/.gcode/teams/demo/mailbox/
5. 写 config.json(原子)
6. team.members = [TeammateInfo(name="lead", agent_id="lead", is_active=None)]
7. teams["demo"] = team
  ↓
返回 {"team_name":"demo","backend":"tmux","config_path":"..."}
```

### Agent(team_name=...) spawn 路径

```
LLM 调 Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="...")
  ↓
agent.AgentTool.execute
  ↓
判断 team_name != "" → 委托给 team_hook.spawn_teammate
  ↓
await team.spawn_teammate(req)
  ↓
1. manager.get("demo") 取 Team
2. 校验调用者权限(in-process 队员不许 spawn,Pane 队员可以但 team_name 屏蔽)
3. catalog.resolve(agent_type) 取 SubAgentDefinition
4. member_name = req.name(或自动 alice/agent-a1b2c3)
5. await wt_mgr.create("team-demo/"+member_name, "HEAD", False) → worktree
6. 申请 session_dir(util 函数,沿用 ch12 格式)
7. 构造 SpawnRequest
8. 若 backend=in-process:
   - 构造 sub_agent(new_session_runtime + cwd + allowed_tools 含协作工具)
   - 构造 sub_conv(new_from_messages 走 Fork 路径,或空 Conv 走定义式)
   - 注入 <team-context> reminder
   - 注入 system_prompt 附录(F39)
   - SpawnRequest.sub_agent / conv / task_mgr 填好
9. await backend.spawn(req) → (pane_id, agent_id)
10. registry.register(member_name, agent_id)
11. await team.add_member(TeammateInfo(...))
  ↓
返回 {"member_name":"alice","agent_id":"...","worktree":"...","backend":"tmux"}
```

### SendMessage 调用路径

```
LLM 调 SendMessage(to="alice", summary="hi", message="hello")
  ↓
tools.SendMessage.execute
  ↓
1. 取调用者所属 Team(从 ctx 中 TeammateContext 取,或主 Agent 走 active team)
2. resolve to:
   - "*" → 广播
   - 否则 registry.resolve(to) → agent_id
3. 校验消息类型权限(plan_approval_response 仅 Lead,shutdown_response 仅发给 Lead)
4. 对每个目标 agent_id:
   - await mailbox.write(agent_id, msg)
   - 取 TeammateInfo.pane_id 与 backend_type
   - 若 Pane 后端:await backend.wake(pane_id, agent_id)
   - 若目标已 stop(in-process,task.Manager.get(agent_id).status != Running):
     - 从 session_dir 恢复 Conv
     - await task_mgr.send_message(parent_ctx, name, message) 续派
5. 返回 {"delivered_to":["agent-xxx"],"timestamp":...}
```

### 队员 Loop 内邮箱注入

```
队员的 agent.Agent.run 每轮迭代开头(在调 LLM 前):
  ↓
读 ctx 中的 TeammateContext(包含 Box、agent_id)
  ↓
indices, unread = await mailbox.read_unread(agent_id)
  ↓
若 len(unread) > 0:
  reminder = build_incoming_messages_reminder(unread)
  把 reminder 加入本轮 system_reminders
  await mailbox.mark_read(agent_id, indices)
```

`agent.Agent` 已有 system_reminders 注入机制(ch05 / ch07 plan reminder 走同一通道);新增一种 reminder 来源即可。

### 队员 run_to_completion 结束的通知

```
task.Manager._run_task asyncio task 结束(完成 / 失败 / 取消)
  ↓
若该 task 关联到 Team 队员(通过 registry.name_of(agent_id) 反查 name → 查 team)
  ↓
await team.set_member_active(member_name, False)
await mailbox.write(lead_agent_id, Message(type="text", summary="<name> idle", ...))
await backend.wake(lead_pane_id, lead_agent_id)   # 若 Lead 是 Pane 后端
```

需要在 `task.Manager._run_task` 的 try/finally 中加 hook,或者在 `team` 包注册一个回调到 task 包(走依赖反转)。**采用方案:** 在 `task.Manager` 新增 `on_task_done(fn: Callable[[str], Awaitable[None]])` 回调注册接口,`team` 包初始化时注册。

### Coordinator Mode 启用路径

```
cli.main 启动时,在构造主 Agent 后:
  ↓
if coordinator.is_enabled(cfg):
    main_agent.set_allowed_tools(coordinator.allowed_tools())
    main_agent.append_system_prompt(coordinator.system_prompt_suffix())
    app.coordinator_mode = True
```

TUI 渲染 statusbar 时检测 `coordinator_mode` 添加 `[COORDINATOR]` 标签。

## 文件组织

```
src/gcode/team/
├── __init__.py                    — 包导出
├── types.py                       — Team / TeammateInfo / BackendType 等类型
├── manager.py                     — Manager(create/get/delete/add_member/set_member_active/remove_member)
├── persistence.py                 — 原子写 config.json,sanitize 函数,reload_from_disk_locked
├── spawn.py                       — spawn_teammate 主流程(被 agent.TeamHook 调用)
├── feature.py                     — FORK_TEAMMATE feature flag 读取
├── backend/
│   ├── __init__.py                — Backend Protocol、SpawnRequest、new_backend 工厂
│   ├── detect.py                  — detect()
│   ├── tmux.py                    — Tmux Backend 实现
│   ├── iterm2.py                  — iTerm2 Backend 实现
│   └── inprocess.py               — InProcess Backend 实现
├── mailbox/
│   ├── __init__.py                — Box 类型与 read/write/mark_read
│   ├── lock.py                    — 文件锁机制(抢锁、重试、stale 处理)
│   └── message.py                 — Message / MessageType
├── registry/
│   └── __init__.py                — AgentNameRegistry
├── tasks/
│   ├── __init__.py                — Task / Store
│   └── filter.py                  — Filter/Patch + is_ready 计算
└── tools/
    ├── __init__.py
    ├── team_create.py             — TeamCreate 工具
    ├── team_delete.py             — TeamDelete 工具
    ├── task_create.py
    ├── task_get.py
    ├── task_list.py
    ├── task_update.py
    ├── send_message.py
    └── teammate_filter.py         — 队员专属工具白名单(注入到 apply_agent_tool_filter)

tests/
├── test_team_manager.py
├── test_team_spawn.py
├── test_team_mailbox.py           — 并发与 stale 锁测试
├── test_team_registry.py
├── test_team_tasks.py
├── test_team_backend_detect.py
├── test_team_backend_tmux.py
├── test_team_backend_inprocess.py
├── test_team_tools.py
└── test_coordinator.py

src/gcode/coordinator/
└── __init__.py                    — is_enabled / allowed_tools / system_prompt_suffix

src/gcode/agent/
├── agent_tool.py                  — 修改:增加 team_name 参数与 TeamHook 委托
├── team_hook.py                   — 新建:TeamHook Protocol、TeammateContext
└── team_mailbox.py                — 新建:Loop 头部注入 incoming-messages reminder

src/gcode/task/
└── manager.py                     — 修改:on_task_done 回调注册;改用 registry.AgentNameRegistry

src/gcode/command/
└── builtin_team.py                — 新建:/team list/info/delete/kill 4 个命令

src/gcode/tui/
├── app.py                         — 修改:接收 team_mgr;启动时检测 coordinator.is_enabled
├── tasks.py                       — 修改:consume_lead_mail / wait_for_lead_mail 后台 task
├── stream.py                      — 修改:begin_autonomous_turn
└── view.py                        — 修改:渲染 [COORDINATOR] 标签

src/gcode/config/
└── __init__.py                    — 修改:新增 FeaturesConfig.coordinator_mode / fork_teammate

src/gcode/cli/
├── __init__.py                    — 修改:wire team.Manager,注册 7 个新工具,接入 coordinator
└── team_member.py                 — 新建:--team-member 自治循环
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Team 包归属 | `gcode.team` 顶层包 | 与 ch13 `subagent`、ch14 `worktree` 平级,职责清晰 |
| 后端三选一时机 | `detect()` 在 `TeamCreate` 时一次性决定 | 与 README 一致:不做运行时回退,行为可预测 |
| 后端实现拆分 | 各一个子模块 `tmux.py / iterm2.py / inprocess.py` | `inprocess` 需要依赖 `agent` 包,拆开避免污染其他 backend |
| Backend Protocol | 三方法 `spawn/wake/kill` | 最小集;not pause/resume(本期不做) |
| Lead 表示 | 不引入独立类型,Lead = `GCodeApp.main_agent` | 收窄改动;Coordinator Mode 在工具集层面区分 |
| 邮箱实现 | `<team_config_dir>/mailbox/<agent_id>.json` + 同名 `.lock` | 跨进程通信现成方案;in-process 与 Pane 共用一套 |
| 锁文件参数 | `os.open(O_CREAT\|O_EXCL\|O_WRONLY)`,5-100ms 抖动 10 次,>10s 视 stale | README 明定;避免雪崩;Python 没有 Go 的 `syscall.Flock` 跨平台等价,所以走 EEXIST 抢占 |
| 任务存储 | `<team_config_dir>/tasks.json` 单文件 | Team 内任务量小(几十条),无需 DB;原子写 + 文件锁 |
| AgentNameRegistry 归属 | 独立 `team.registry` 子包,`task.Manager` 委托 | 解耦;消除 ch13 `task.Manager._by_name` 的局部状态 |
| `task.Manager` 改造 | 加 `on_task_done` 回调,Team 注册 | 依赖反转,避免 task 包反向依赖 team |
| Team 持久化原子性 | `<file>.tmp` + `os.replace` | 与 ch14 worktree session、ch12 session 一致;Python `os.replace` 跨平台原子 |
| Worktree 命名 | `team-<sanitized_team>/<member>`(嵌套 slug,`/` → `+`) | 复用 ch14 嵌套 slug 能力;不污染顶层 worktree 命名空间 |
| Member session_dir | 沿用 ch12 `<root>/.gcode/sessions/<id>/` 格式 | 复用 `session.Writer`,无需新机制;Team 删除时一并清理 |
| Coordinator 开启检测 | `feature_has(cfg, "COORDINATOR_MODE") and env_truthy(env)` | README 明定双锁;一次决定不允许运行时改 |
| Coordinator 工具白名单 | 硬编码常量,启动时直接 `set_allowed_tools` | LLM 无法解锁,安全边界清晰 |
| Plan 审批本期形态 | 文本 Plan + Lead 用 `plan_approval_response` 回复 | 不强制结构化 Plan 类型,降低实现成本 |
| Fork 队员 | 受 `FORK_TEAMMATE` flag 控制,默认关 | README 明定;避免默认带满上下文 |
| 收敛 merge | 不提供专用工具,Lead 用 Bash 自主跑 git | README 明定;LLM 解冲突 = 语义理解,这是 LLM 优势 |
| `Agent` 工具的 `team_name` 在 in-process 队员处可见性 | 参数对模型可见,但调用时拦截抛错 | 与其在 schema 层动态裁剪不如统一 schema + 运行时校验,缓存友好 |
| 队员 Loop 邮箱注入 | 复用 `agent.Agent` 既有 system_reminders 通道,新增一种 reminder 来源 | 不改 Loop 主流程,改动最小 |
| TUI Coordinator 标签 | 状态栏静态渲染 | 视觉提示,运行时不可改 |
| 多 Team 并存 | `Manager.teams` dict 支持,但 spawn 时按 `team_name` 显式选 | 灵活;典型场景同一时刻一个活跃 Team |
| Team 删除时 Worktree 处理 | 调 `wt_mgr.remove(name, discard_changes=True)`,失败只警告 | 与 ch14 退出语义一致;`force=True` 才放行,无 force 时有活跃成员就拒删,有变更也保留(自动 cleanup 已处理) |
| 错误命名 | 自定义异常类 `TeamHasActiveMembersError` / `InProcessTeammateNoSpawnError` 等 | 调用方可 `except` 判别 |
| 并发模型 | `asyncio.Lock` 保护 Team / Manager 状态;mailbox 文件锁跨进程 | 与 Textual 的 asyncio event loop 天然契合;不引入 threading 池 |
| 子进程模型 | `python -m gcode --team-member` + `asyncio.create_subprocess_exec` | 标准 Python 启动方式,跨平台 |
````

````markdown
# Agent Team Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gcode/team/__init__.py` | 包导出 |
| 新建 | `src/gcode/team/types.py` | Team / TeammateInfo / BackendType 等类型 |
| 新建 | `src/gcode/team/persistence.py` | sanitize、原子写、reload_from_disk_locked |
| 新建 | `src/gcode/team/manager.py` | Manager.create/get/delete/add_member/set_member_active/remove_member |
| 新建 | `tests/test_team_manager.py` | Manager 单测 |
| 新建 | `src/gcode/team/spawn.py` | spawn_teammate 主流程 |
| 新建 | `tests/test_team_spawn.py` | spawn 单测(in-process 路径) |
| 新建 | `src/gcode/team/feature.py` | FORK_TEAMMATE flag 读取 |
| 新建 | `src/gcode/team/mailbox/__init__.py` | Box.read/write/mark_read + Message 类型 |
| 新建 | `src/gcode/team/mailbox/lock.py` | 文件锁机制 |
| 新建 | `src/gcode/team/mailbox/message.py` | Message / MessageType |
| 新建 | `tests/test_team_mailbox.py` | 并发与 stale 锁测试 |
| 新建 | `src/gcode/team/registry/__init__.py` | AgentNameRegistry |
| 新建 | `tests/test_team_registry.py` | 注册/解析/反查测试 |
| 新建 | `src/gcode/team/tasks/__init__.py` | Task / Store / Filter / Patch |
| 新建 | `tests/test_team_tasks.py` | CRUD + 依赖关系测试 |
| 新建 | `src/gcode/team/backend/__init__.py` | Backend Protocol + SpawnRequest + new_backend |
| 新建 | `src/gcode/team/backend/detect.py` | detect() |
| 新建 | `tests/test_team_backend_detect.py` | 检测逻辑测试 |
| 新建 | `src/gcode/team/backend/tmux.py` | Tmux Backend |
| 新建 | `tests/test_team_backend_tmux.py` | tmux 命令构造测试 |
| 新建 | `src/gcode/team/backend/iterm2.py` | iTerm2 Backend |
| 新建 | `tests/test_team_backend_iterm2.py` | iterm2 命令构造测试 |
| 新建 | `src/gcode/team/backend/inprocess.py` | InProcess Backend |
| 新建 | `tests/test_team_backend_inprocess.py` | in-process spawn 集成测试 |
| 新建 | `src/gcode/team/tools/team_create.py` | TeamCreate 工具 |
| 新建 | `src/gcode/team/tools/team_delete.py` | TeamDelete 工具 |
| 新建 | `src/gcode/team/tools/task_create.py` | TaskCreate 工具 |
| 新建 | `src/gcode/team/tools/task_get.py` | TaskGet 工具 |
| 新建 | `src/gcode/team/tools/task_list.py` | TaskList 工具 |
| 新建 | `src/gcode/team/tools/task_update.py` | TaskUpdate 工具 |
| 新建 | `src/gcode/team/tools/send_message.py` | SendMessage 工具 |
| 新建 | `src/gcode/team/tools/teammate_filter.py` | 队员专属工具白名单 |
| 新建 | `tests/test_team_tools.py` | 工具单测 |
| 新建 | `src/gcode/coordinator/__init__.py` | is_enabled/allowed_tools/system_prompt_suffix |
| 新建 | `tests/test_coordinator.py` | 双锁测试 |
| 新建 | `src/gcode/agent/team_hook.py` | TeamHook Protocol + TeammateContext |
| 修改 | `src/gcode/agent/agent_tool.py` | 增加 team_name 参数 + TeamHook 委托 + with_team_hook 构造选项 |
| 新建 | `src/gcode/agent/team_mailbox.py` | Loop 头部注入 incoming-messages reminder |
| 修改 | `src/gcode/task/manager.py` | 加 on_task_done 回调;改用 registry.AgentNameRegistry |
| 修改 | `src/gcode/tool/filter.py` | 新增 TEAMMATE_ALLOWED_TOOLS,扩展 FilterParams 加 teammate bool |
| 新建 | `src/gcode/command/builtin_team.py` | /team list/info/delete/kill 4 个命令 |
| 修改 | `src/gcode/tui/app.py` 与相关文件 | 接收 team_mgr、coordinator 标签 |
| 修改 | `src/gcode/config/__init__.py` | Features 字段新增 coordinator_mode 与 fork_teammate |
| 修改 | `src/gcode/cli/__init__.py` | wire team.Manager / coordinator,注册 7 个工具 |
| 新建 | `src/gcode/cli/team_member.py` | --team-member 自治循环 |
| 修改 | `.gcode/config.yaml.example` | 加示例 features 段(可选,不强制) |

## T1: 基础类型 — `src/gcode/team/types.py`**文件:** `src/gcode/team/types.py`
**依赖:** 无
**步骤:**
1. 定义 `BackendType(StrEnum)` 含 `TMUX` / `ITERM2` / `IN_PROCESS`
2. 定义 `@dataclass class Team`(F1):字段含 `_lock: asyncio.Lock`、`name`、`sanitized_name`、`lead_agent_id`、`backend`、`description`、`created_at`、`members`、派生路径字段(`config_dir`/`config_path`/`tasks_path`/`mailbox_dir`,序列化时跳过)
3. 定义 `@dataclass class TeammateInfo`(F2),字段对应 json key(下划线命名)
4. 定义异常类 `TeamNotFoundError` / `TeamHasActiveMembersError` / `MemberExistsError` / `MemberNotFoundError` / `InProcessTeammateNoSpawnError`,统一基类 `TeamError`

**验证:** `python -c "from gcode.team.types import Team, TeammateInfo, BackendType"` 不报错;`ruff check src/gcode/team/types.py` 通过

## T2: sanitize 与原子写 — `src/gcode/team/persistence.py`**文件:** `src/gcode/team/persistence.py`
**依赖:** T1
**步骤:**
1. 实现 `sanitize(name: str) -> str`——只保留 `[a-zA-Z0-9._-]`,其他字符替换为 `-`,首尾去 `-`,空字符串返回 `""`(用 `re.sub`)
2. 实现 `atomic_write_json(path: str | Path, value: Any) -> None`——`json.dumps(indent=2)` → 写 `<path>.tmp` → `os.replace`
3. 实现 `read_json(path: str | Path) -> Any`——`Path.read_text()` + `json.loads`,文件不存在抛 `FileNotFoundError`

**验证:** 单测断言 `sanitize("foo bar/baz")=="foo-bar-baz"`;`atomic_write_json` 写入后 `read_json` 取回相等

## T3: Manager 与持久化 — `src/gcode/team/manager.py`**文件:** `src/gcode/team/manager.py`
**依赖:** T1, T2
**步骤:**
1. 定义 `class Manager`(F3)
2. 实现 `Manager.__init__(home_dir, project_root, wt_mgr, task_mgr, reg)`(F4)
   - 创建 `<home_dir>/.gcode/teams/` 目录
   - 扫描子目录,逐个读 `config.json`(失败 stderr 警告并跳过)
   - 反序列化后填充派生路径字段
3. 实现 `Manager.get(name: str) -> Team | None`
4. 实现 `Manager.list_() -> list[Team]`(按创建时间排序)
5. 实现 `async Manager.create(name, description)`(F5)
   - sanitize + 同名冲突 `-2`/`-3` 后缀
   - 取 `detect()`(暂时硬编码 `BackendType.IN_PROCESS`,后面 T11 接 detect)
   - 创建 `config_dir`、`mailbox_dir`
   - 注册 Lead 成员
   - `atomic_write_json`
6. 实现 `async Manager.delete(name, force)`(F7 + F66):
   - 持锁、找到 Team、(force=False 时)校验全员 is_active=False
   - 对每个非 lead 成员:用 `backend.new_backend(mem.backend_type)` 解析后端,调 `await backend.kill(mem.pane_id, mem.agent_id)` 杀 pane(tmux/iterm2)或 cancel asyncio task(in-process)
   - 调 `_cleanup_member_resources` 删 session 目录与 worktree(best-effort)
   - `shutil.rmtree(team.config_dir)` 删整个 Team 目录
   - 从 in-memory dict 移除
   - 没注入 backend deps 的测试场景跳过 kill,fallback 只清磁盘资源

**验证:** 写单测覆盖 create/get/delete 基本流程;`pytest tests/test_team_manager.py` 通过;tmux 实跑后 `/team delete --force` 看 pane 真的被杀(`tmux list-panes` 只剩 Lead)

## T3b: Team.Manager 跨进程并发兜底 — 继续 `src/gcode/team/manager.py` + `src/gcode/team/persistence.py`**文件:** `src/gcode/team/manager.py`(为 add_member / set_member_active 加 reload-before-modify)、`src/gcode/team/persistence.py`(增加 `reload_from_disk_locked`)
**依赖:** T3
**步骤:**
1. `persistence.py` 增 `async def reload_from_disk_locked(team: Team) -> None`——调用方持锁;从 `team.config_path` `read_json`,把 `members` 字段覆盖到 in-memory(失败静默回退到内存现状)
2. `Team.add_member` 与 `Team.set_member_active`(以及任何会修改 members 后 save 的方法)在加锁后**先**调 `await reload_from_disk_locked(self)` 再操作内存 + save
3. 不是为了 asyncio 内的并发——in-process 早就有 `_lock` 保护;**是为了跨进程**:Pane 后端的 Lead 与子进程是两个独立进程,各持一份内存中的 Team。如果不 reload,会出现"子进程读 config 时 Lead 的 add_member 还没写入,子进程修改自己内存 Team 没看见自己,set_member_active 静默 no-op"的丢更新

**验证:** 单测构造时序:t1 = read_json 得到无 alice 的 Team A;t2 在 disk 上写带 alice 的 Team B;t3 调 `await team.set_member_active("alice", False)` 应该成功(走 reload 路径)而非静默 no-op

## T4: Team 成员操作 — 继续 `src/gcode/team/manager.py`**文件:** `src/gcode/team/manager.py`(同 T3)
**依赖:** T3
**步骤:**
1. 实现 `async Team.add_member(info)`(F8)——加锁后**先 reload_from_disk_locked**(见 T3b),检查重名;加入 members;持久化
2. 实现 `async Team.set_member_active(name, active)`(F9)——加锁后**先 reload_from_disk_locked**;遍历 members 找到 name 改 is_active 字段;持久化
3. 实现 `async Team.remove_member(name)`(F10)
4. 实现 `Team.member_by_name(name) -> TeammateInfo | None` / `Team.member_by_agent_id(id_) -> TeammateInfo | None` 工具方法

**验证:** 单测覆盖 add → set_active → remove 三步流程,读回 config.json 校验字段

## T5: mailbox 文件锁 — `src/gcode/team/mailbox/lock.py`**文件:** `src/gcode/team/mailbox/lock.py`
**依赖:** 无
**步骤:**
1. 实现 `async def acquire_lock(lock_path: str) -> AsyncContextManager[None]`——
   - 循环 10 次:`os.open(lock_path, O_CREAT|O_EXCL|O_WRONLY, 0o644)` 抢锁
   - 失败时 `Path(lock_path).stat()`,若 `time.time() - st_mtime > 10` 则 `os.unlink(lock_path)` 后立即重试一次
   - 失败时 `await asyncio.sleep(random.uniform(0.005, 0.1))` 抖动后继续
   - context manager 退出时:`os.unlink(lock_path)`
2. 内部常量 `LOCK_MAX_RETRIES = 10` / `LOCK_STALE_AFTER = 10.0` / `LOCK_BACKOFF_MIN = 0.005` / `LOCK_BACKOFF_MAX = 0.1`

**验证:** 单测 `test_acquire_lock_serial`(两次抢锁,中间 release)、`test_acquire_lock_stale`(故意创建 11 秒前的锁——`os.utime(lock_path, (now-11, now-11))`,断言能拿到)

## T6: mailbox Message 与 Box — `src/gcode/team/mailbox/__init__.py` + `message.py`**文件:** `src/gcode/team/mailbox/__init__.py`、`src/gcode/team/mailbox/message.py`
**依赖:** T5
**步骤:**
1. `message.py` 定义 `MessageType(StrEnum)` 与 4 个常量(F32)
2. `message.py` 定义 `@dataclass class Message`(F32),提供 `to_dict()` / `from_dict()`(注意 `from_` 字段对应 json key `"from"`)
3. `__init__.py` 定义 `class Box`,字段 `_dir: str`
4. 实现 `Box.__init__(dir_)`——`Path(dir_).mkdir(parents=True, exist_ok=True)`
5. 实现 `async Box.write(agent_id, msg)`(F33)
   - `lock_path = f"{self._dir}/{agent_id}.lock"`
   - `async with acquire_lock(lock_path):`
   - 读 `<dir>/<agent_id>.json`(不存在视为 `{"messages":[]}`)
   - 追加 msg(若 timestamp=0 设为 `int(time.time())`)
   - `atomic_write_json`
6. 实现 `async Box.read(agent_id) -> list[Message]`
7. 实现 `async Box.read_unread(agent_id) -> tuple[list[int], list[Message]]`——返回 unread 消息的 indices 与消息本身
8. 实现 `async Box.mark_read(agent_id, indices)`——按 indices 把对应消息 `read=True`

**验证:** 单测覆盖 write/read/mark_read;并发测试 10 个 asyncio task 写同一 agent_id,断言读回 10 条无丢失

## T7: AgentNameRegistry — `src/gcode/team/registry/__init__.py`**文件:** `src/gcode/team/registry/__init__.py`
**依赖:** 无
**步骤:**
1. 定义 `class AgentNameRegistry`
2. 实现 `__init__()`
3. 实现 `register(name, agent_id)`——若 name 已存在覆盖(取出旧 agent_id,从 `_by_id` 删旧映射);若 agent_id 已有其他 name,先反向 unregister
4. 实现 `unregister(name)`
5. 实现 `unregister_by_agent_id(agent_id)`
6. 实现 `resolve(name_or_id) -> str | None`——先按 name 查,再按 agent_id 反向查
7. 实现 `name_of(agent_id) -> str | None`
8. 实现 `list_() -> dict[str, str]`

**验证:** 单测覆盖 register/unregister/resolve/name_of;包括「同名覆盖」和「不同名指向同一 agent_id」边界

## T8: tasks Store — `src/gcode/team/tasks/__init__.py`**文件:** `src/gcode/team/tasks/__init__.py`
**依赖:** T5(用 mailbox 的 lock)
**步骤:**
1. 定义 `Status(StrEnum)` / `Task` / `Filter` / `Patch` 类型(F30)
2. 定义 `class Store`,字段 `_path: str`, `_lock: asyncio.Lock`
3. 实现 `__init__(path)`
4. 实现 `async create(t) -> str`——生成 `task_<6 位 hex>` ID(`secrets.token_hex(3)`);read-modify-write `tasks.json`(用 lock 文件,路径 `<path>.lock`,复用 mailbox 的 `acquire_lock`——把它提到 `gcode.team.filelock` 共用包,或直接在 tasks 包内复制小段实现)
5. 实现 `async get(id_) -> Task`
6. 实现 `async list_(f: Filter) -> list[Task]`——按 `status` 过滤,返回时附加 `is_ready` 字段(检查 blocked_by 中所有任务是否 completed);为简化可在 list_ 输出时计算 ready 标记,不存盘
7. 实现 `async update(id_, p: Patch)`——支持 title/description/status/assignee/add_blocks/add_blocked_by/remove_blocks/remove_blocked_by 字段
8. `add_blocked_by=[X]` 同时给 X 任务 `blocks` 加上当前任务 id(双向维护)

**注意:** 为减小循环依赖,把 `acquire_lock` 提到独立 `gcode.team.filelock` 模块,mailbox 与 tasks 共用。

**验证:** 单测覆盖 create/get/update;特别测 add_blocked_by 的双向更新

## T9: 共用 filelock 模块(从 mailbox 抽出)**文件:** `src/gcode/team/filelock.py`(把 T5 实现迁过来)
**依赖:** 无
**步骤:**
1. 把 T5 的 `acquire_lock` 实现迁到 `gcode.team.filelock`,签名保持 `async def acquire(lock_path) -> AsyncContextManager[None]`
2. 在 `mailbox/lock.py` 改为 `from gcode.team.filelock import acquire`,删除本地实现
3. 在 `tasks/__init__.py` 也 import `filelock`

**验证:** `pytest tests/test_team_*.py` 全过

## T10: backend Protocol — `src/gcode/team/backend/__init__.py`**文件:** `src/gcode/team/backend/__init__.py`
**依赖:** T1
**步骤:**
1. 定义 `@dataclass class SpawnRequest`(F13)——其中 `sub_agent` / `conv` / `task_mgr` 字段类型为 `Any`,避免 backend 反向依赖 agent 包
2. 定义 `Backend` Protocol(F12):`type() -> BackendType`、`async spawn(req) -> tuple[str, str]`(返回 `(pane_id, agent_id)`)、`async wake(pane_id, agent_id) -> None`、`async kill(pane_id, agent_id) -> None`
3. 定义 `def new_backend(t: BackendType, **deps) -> Backend` 工厂——按类型分发(暂时只占位,具体实现在 T12-T14)

**验证:** `python -c "from gcode.team.backend import Backend, SpawnRequest, new_backend"` 通过

## T11: detect_backend — `src/gcode/team/backend/detect.py`**文件:** `src/gcode/team/backend/detect.py`
**依赖:** T10
**步骤:**
1. 实现 `def detect() -> BackendType`(F14):
   - `os.environ.get("TMUX")` → `TMUX`
   - `os.environ.get("TERM_PROGRAM") == "iTerm.app"` 且 `shutil.which("it2")` → `ITERM2`
   - `shutil.which("tmux")` → `TMUX`
   - 否则 `IN_PROCESS`

**验证:** 写 test 用 `monkeypatch.setenv` 控制环境变量 + monkeypatch.setattr 替换 `shutil.which`,断言不同组合的返回值

## T12: tmux backend — `src/gcode/team/backend/tmux.py`**文件:** `src/gcode/team/backend/tmux.py`
**依赖:** T10
**步骤:**
1. 定义 `class TmuxBackend`
2. 实现 `__init__()` 与 `type()` 返回 `BackendType.TMUX`
3. 实现 `async spawn(req)`(F15):
   - 在 `$TMUX` 内:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`
   - 在 `$TMUX` 外但 `tmux` 二进制可用:`tmux new-session -d`(detached 新会话)走外部 session(F16)
   - `cmd` 构造:`python -m gcode --team-member --team <team_name> --member <member_name> --agent-id <agent_id> --session-dir <session_dir> --worktree <wt_path> [--agent-type <type>] [--model <model>] [--plan-mode]`(可用 `shlex.quote` 转义)
   - `--agent-id` 必须传——子进程不需要读 Lead 还没写完的 `config.json` 找自己
   - `initial_prompt` **不**走命令行,由 `team.spawn_teammate`(T18)在 `backend.spawn` 之前预写入 alice mailbox
   - 用 `await asyncio.create_subprocess_exec("tmux", ...)` 跑 tmux,捕获 stdout 作为 pane_id
4. 实现 `async wake(pane_id, agent_id)`:`tmux send-keys -t <pane_id> "" Enter`(子进程 stdin reader 读到回车,立刻去 mailbox 轮询)
5. 实现 `async kill(pane_id, agent_id)`:`tmux kill-pane -t <pane_id>`,忽略 pane not found 错误

**注意:** spawn 启动的 gcode CLI 需要支持 `--team-member` flag;这部分留给 T21(cli/__init__.py 改造)+ T29(team_member.py 新建)

**验证:** 单测断言命令字符串构造正确(用 monkeypatch.setattr 替换 `asyncio.create_subprocess_exec` 收 args);集成测试在 CI 跳过(需要 tmux)

## T13: iterm2 backend — `src/gcode/team/backend/iterm2.py`**文件:** `src/gcode/team/backend/iterm2.py`
**依赖:** T10
**步骤:**
1. 实现 `Iterm2Backend.spawn`:`it2 split --new-pane --command "<cmd>"`(实际 it2 CLI 命令以官方为准;先按 README 描述实现,实测可能要调);`<cmd>` 同 T12 格式,含 `--agent-id`,`initial_prompt` 走 mailbox 预写
2. 实现 `wake`:`it2 send-text --pane <pane_id> ""`
3. 实现 `kill`:`it2 close-pane --pane <pane_id>`

**注意:** iterm2 后端无法在 CI 中实跑,实现以构造正确的命令字符串为准

**验证:** 单测断言命令构造正确

## T14: in-process backend — `src/gcode/team/backend/inprocess.py`**文件:** `src/gcode/team/backend/inprocess.py`
**依赖:** T10,需要 `agent`、`task`、`conversation` 包
**步骤:**
1. 定义 `class InProcessBackend`,字段 `_task_mgr: task.Manager`
2. 实现 `async spawn(req)`(F18):
   - 从 `req.sub_agent` / `req.conv` 取已构造好的对象
   - 调 `await task_mgr.launch(sub_agent, conv, req.member_name, req.initial_prompt)` 起 asyncio task
   - 返回 `("", task_id)`——in-process 用 agent_id 作为目标 id,pane_id 为空
3. 实现 `async wake(pane_id, agent_id)`:no-op,直接 return
4. 实现 `async kill(pane_id, agent_id)`:`await task_mgr.stop(agent_id)`

**Backend Protocol 签名统一**(回 T10 调整):
```python
class Backend(Protocol):
    def type(self) -> BackendType: ...
    async def spawn(self, req: SpawnRequest) -> tuple[str, str]: ...   # (pane_id, agent_id)
    async def wake(self, pane_id: str, agent_id: str) -> None: ...
    async def kill(self, pane_id: str, agent_id: str) -> None: ...
```
Pane 后端用 pane_id,in-process 用 agent_id;Protocol 统一传两者,各自取需要的。

**验证:** 单测:构造 fake task_mgr,spawn 一个 noop 子 Agent,断言 asyncio task 启动

## T15: feature flag — `src/gcode/team/feature.py`**文件:** `src/gcode/team/feature.py`
**依赖:** 无
**步骤:**
1. 实现 `def fork_teammate_enabled(cfg: Config) -> bool`——读 `cfg.features.fork_teammate`

**验证:** 单测覆盖 True/False 两种 cfg

## T16: TeammateContext — `src/gcode/agent/team_hook.py`**文件:** `src/gcode/agent/team_hook.py`
**依赖:** 无
**步骤:**
1. 定义 `TeamHook` Protocol(plan.md 已给签名)
2. 定义 `@dataclass class TeamSpawnRequest`(把 Agent 工具参数传过去)
3. 定义 `@dataclass class TeammateContext`——`team_name`、`member_name`、`agent_id`、`mailbox_dir`、`send_message_wake: Callable[[str], Awaitable[None]]` 等
4. 提供 `WITH_TEAMMATE_KEY = "teammate"` + `with_teammate_context(ctx, tc) -> dict` + `teammate_context_from_ctx(ctx) -> TeammateContext | None`(用 dict 作为 ctx 容器或 `contextvars.ContextVar` 也行)

**验证:** `python -c "from gcode.agent.team_hook import TeamHook, TeammateContext"` 通过

## T17: 队员专属工具白名单 — `src/gcode/tool/filter.py` 扩展**文件:** `src/gcode/tool/filter.py`(修改)
**依赖:** 无
**步骤:**
1. 新增常量:
   ```python
   TEAMMATE_EXTRA_TOOLS: list[str] = [
       "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "SendMessage",
   ]
   ```
2. 扩展 `FilterParams` dataclass 加 `teammate: bool = False` 字段
3. 在 `apply_agent_tool_filter` 中:若 `teammate=True`,把 `TEAMMATE_EXTRA_TOOLS` 加到允许集合(在 disallowed 删除之前);非 teammate 时排除这些工具(主 Agent 看不到)
4. 同时增加常量 `TEAM_LEAD_DISALLOWED_TEAMMATE_TOOLS`——避免主 Agent 直接看到 TaskCreate 等(应该走 `teammate=True` 才能加上)

**简化策略:** `TEAMMATE_EXTRA_TOOLS` 不进默认 registry(由 `cli/__init__.py` 注册到 registry,但默认从 ALL 过滤集移除);`teammate=True` 时把它们加回。

**采用:**
- `cli/__init__.py` 把 5 个协作工具注册到 registry
- 修改默认 filter:`ALL_AGENT_DISALLOWED_TOOLS` 加上这 5 个工具(子 Agent 默认看不到)
- 新增 `TEAMMATE_ALLOWED_TOOLS = ALL_AGENT_DISALLOWED_TOOLS 中的协作工具`
- 修改 `apply_agent_tool_filter`:`teammate=True` 时,这 5 个工具不被 ALL 过滤

**验证:** 单测覆盖 `teammate=True / False`,断言 TaskCreate 等可见性

## T18: spawn_teammate 主流程 — `src/gcode/team/spawn.py`**文件:** `src/gcode/team/spawn.py`
**依赖:** T1-T17
**步骤:**
1. 定义 `async Manager.spawn_teammate(req: TeamSpawnRequest) -> str`
2. 实现 plan.md 中描述的步骤流程:
   - 取 Team
   - 校验调用者权限(看 ctx 是否有 TeammateContext,且 backend_type=in-process 时拒绝)
   - 解析 `SubAgentDefinition`
   - `await wt_mgr.create(f".gcode/worktrees/team-{sanitized}+{member}")`
   - 申请 session_dir(本期复用 ch12 格式,自己生成新 id)
   - 预生成 agent_id(`f"agent-{secrets.token_hex(7)}"`),构造 SpawnRequest 含 agent_id 字段
   - 计算 allowed = `apply_agent_tool_filter(FilterParams(teammate=True, ...))`、system_prompt = `def.system_prompt + team_system_prompt_suffix()`
   - 若 backend_type=in-process:构造 sub_agent(**强制 `dont_ask=True`** F39a)+ sub_conv,注入 `<team-context>` reminder + ctx 装 `TeammateContext(mailbox=mc)`
   - 若 backend_type=tmux/iterm2:`await Box(t.mailbox_dir).write(agent_id, Message(from_="lead", type=TEXT, summary=..., content=req.prompt))` 预写初始任务(F13)
   - `await backend.spawn(req)` 取 `(pane_id, agent_id)`
   - `registry.register(member_name, agent_id)`
   - `await team.add_member(...)` (调用时 `reload_from_disk_locked` 保护跨进程并发)
   - 返回 JSON `{"member_name", "agent_id", "worktree", "backend", "pane_id"}`
3. 提供 helper `build_team_context_reminder(team, member, agent_id)` 构造 `<team-context>` reminder
4. 提供 helper `team_system_prompt_suffix() -> str` 返回 F39 附录;`truncate_for_summary(prompt)` 给初始任务 mailbox 消息生成 summary

**验证:** 单测覆盖 in-process 后端的 spawn 全流程;Pane 后端的 spawn 用 mock backend

## T19: Agent 工具集成 — `src/gcode/agent/agent_tool.py` 修改**文件:** `src/gcode/agent/agent_tool.py`(修改)
**依赖:** T16, T18
**步骤:**
1. `AgentToolArgs` dataclass 加 `team_name: str = ""`
2. `AgentTool` 加字段 `team_hook: TeamHook | None = None`
3. `AgentTool.__init__` 加参数 `team_hook`
4. `description()` 中说明 `team_name` 参数(可选,非空时走 Team spawn)
5. `parameters()` 加 `team_name` 字段
6. `execute` 在 `args.team_name != ""` 时:
   - 校验 `self.team_hook is not None`,否则抛错
   - 校验 ctx 不在 in-process 队员中(`self.team_hook.is_teammate_context(ctx)`,若是且 backend_type=in-process,抛 `InProcessTeammateNoSpawnError`)
   - 调 `await self.team_hook.spawn_teammate(TeamSpawnRequest(team_name=..., member_name=args.name, ...))`
   - 返回 spawn_teammate 的结果

**验证:** 单测:不带 team_name 走 ch13 老路径;带 team_name 调 mock team_hook,断言 spawn_teammate 被调

## T20: 队员 Loop incoming-messages 注入 — `src/gcode/agent/team_mailbox.py`**文件:** `src/gcode/agent/team_mailbox.py`
**依赖:** T16, T6
**步骤:**
1. 在 `agent.Agent.run` / `run_to_completion` 的迭代头部(调 LLM 前),检查 ctx 中是否有 TeammateContext;实现位于 `gcode.agent.team_mailbox.ingest_team_mailbox`
2. 若有,调 `await tc.read_unread()`
3. 若有未读消息,构造 `<incoming-messages>` reminder 字符串(F42),加到 `runtime.pending_reminders`(下一轮 `build_reminder` 取出)
4. 调 `await tc.mark_read(indices)`
5. 若收到 `plan_approval_response(approve=True)`,调 `agent.set_permission_mode(PermissionMode.DEFAULT)` 切回 default(reminder 文本也会反映这一切换)。**注意:** Pane 后端子进程的 plan_approval 由 `run_team_member` 主循环额外处理一份——它读到 plan_approval_response 时同样切模式 + 合成续派 prompt 让 `run_to_completion` 接着跑(F19a)

**注意:** `agent` 包不直接 import `mailbox`(避免循环);通过 `TeammateContext` 中的 `Box` 字段访问;或通过 Protocol 抽象(`class MailboxReader(Protocol): async def read_unread(...); async def mark_read(...)`)。

**采用 Protocol:**
```python
# agent/team_hook.py
class MailboxReader(Protocol):
    async def read_unread(self, agent_id: str) -> tuple[list[int], list[Any]]: ...
    async def mark_read(self, agent_id: str, indices: list[int]) -> None: ...
```
import 还是会成环——把 Message 类型也抽象成 Protocol 或 `dict[str, Any]`。**简化:** TeammateContext 持 `read_unread: Callable[[], Awaitable[tuple[list[int], list[IncomingMessage]]]]` 闭包,由 spawn 时由 team 包注入。Message 在 agent 包定义一个轻量 dataclass `IncomingMessage`,只取需要的字段。

**采用最简方案:** 在 `agent` 包内定义 `@dataclass class IncomingMessage`(独立于 `mailbox.Message`),`TeammateContext` 携带 `read_unread`/`mark_read` 闭包;由 team 包在 spawn 时构造闭包注入。

**验证:** 单测覆盖:fake mailbox 写入 1 条消息,启动子 Agent.run,断言 reminder 含 `<incoming-messages>`

## T21: task.Manager 改造 — `src/gcode/task/manager.py` 修改**文件:** `src/gcode/task/manager.py`(修改)
**依赖:** T7
**步骤:**
1. `Manager` 持一个 `name_reg: AgentNameRegistry | None` 引用(可选 None 兜底)
2. `launch` 时:若 `name_reg` 非 None 且 name 非空,调 `name_reg.register(name, id_)`;同时保持本地 `_by_name` 兜底(避免破坏 ch13 既有调用)
3. `get_by_name` 优先用 `name_reg.resolve` 查
4. `send_message(parent_ctx, name, message)` 优先 `name_reg.resolve`
5. 新增 `on_task_done(fn: Callable[[str], Awaitable[None]])` 注册接口,可注册多个回调
6. `_run_task` 的 try/finally 末尾(在 `notify_done` 后)逐个 `await` 调 `on_task_done` 回调
7. 加 `set_name_registry(reg)` setter

**验证:** 单测:注册 `on_task_done`,`launch` 一个 noop task,等完成,断言回调被触发

## T22: 协作工具实现 — `src/gcode/team/tools/`**文件:** `team_create.py` / `team_delete.py` / `task_create.py` / `task_get.py` / `task_list.py` / `task_update.py` / `send_message.py`
**依赖:** T3, T6, T7, T8
**步骤:**
1. 每个工具实现 `tool.Tool` Protocol(`name`/`description`/`parameters`/`read_only`/`execute`)
2. `TeamCreate`(F21):参数 `team_name` + `description`;`execute` 调 `await manager.create`,返回 JSON
3. `TeamDelete`(F23):参数 `team_name` + `force`;`execute` 调 `await manager.delete`
4. `TaskCreate`(F26):参数 `title`/`description`/`assignee`/`blocked_by`;从 ctx 取 TeammateContext 找当前 Team;`execute` 调 `await store.create`
5. `TaskGet`(F27):参数 `task_id`
6. `TaskList`(F28):参数 `status` 过滤;返回带 `is_ready` 字段的 JSON 数组
7. `TaskUpdate`(F29):参数 `task_id` + 各 Patch 字段
8. `SendMessage`(F34):参数 `to`/`summary`/`message`/`type`/`payload`;`execute` 调 `await mailbox.write` + `await backend.wake` + 续派检测
9. 每个工具 `read_only` 返回:TeamCreate/Delete/TaskCreate/Update/SendMessage 返回 False;TaskGet/TaskList 返回 True

**验证:** 每个工具一个单测覆盖正常路径与错误路径

## T23: 协作工具白名单生效 — 验证**文件:** `tests/test_tool_filter.py`(修改)
**依赖:** T17, T22
**步骤:**
1. 在 `apply_agent_tool_filter` 测试中加用例:
   - 主 Agent(`teammate=False`)调用:看不到 TaskCreate / SendMessage 等
   - 队员(`teammate=True`)调用:看到这 5 个

**验证:** 测试通过

## T24: coordinator 包 — `src/gcode/coordinator/__init__.py`**文件:** `src/gcode/coordinator/__init__.py`
**依赖:** 无
**步骤:**
1. 实现 `def is_enabled(cfg: Config) -> bool`——`cfg.features.coordinator_mode and env_truthy(os.environ.get("GCODE_COORDINATOR_MODE", ""))`
2. 实现 `def allowed_tools() -> list[str]`(F53)
3. 实现 `def system_prompt_suffix() -> str`(F55)——除四阶段框架外,**必须**包含"派完队员就停手等汇报"的纪律段:派出 Agent/SendMessage 后禁止立刻 read_file/glob/grep/bash 自己探索;禁止 sleep/TaskList 凑时间;只在 Research 首次定位 / Synthesis 读队员产出 / Verification 收敛 时才允许自己用读类工具
4. 实现 `def env_truthy(v: str) -> bool`——`v.lower() in {"1", "true", "yes"}`

**验证:** 单测覆盖双锁的 4 种组合(00/01/10/11),只有 11 返回 True;tmux 实跑观察 Lead 派完队员后不立刻 glob/read_file 而是"等待汇报"

## T25: config 加 features — `src/gcode/config/__init__.py` 修改**文件:** `src/gcode/config/__init__.py`(修改)
**依赖:** 无
**步骤:**
1. 加 `@dataclass class FeaturesConfig`,字段 `coordinator_mode: bool = False` + `fork_teammate: bool = False`
2. `Config` 加字段 `features: FeaturesConfig = field(default_factory=FeaturesConfig)`
3. `load` 时若 yaml 含 `features:` 段,用 `FeaturesConfig(**raw["features"])` 解析

**验证:** 单测加载 yaml 含 `features:` 段,断言字段被读出

## T26: TUI 集成 — `src/gcode/tui/app.py` 修改**文件:** `src/gcode/tui/app.py` 与可能的 view 文件(修改)
**依赖:** T3, T24
**步骤:**
1. `GCodeApp.__init__` 加 `team_mgr: team.Manager`、`coordinator_mode: bool = False`
2. `GCodeApp` 加字段 `coordinator_mode: bool` 与 `lead_mail_event: asyncio.Event`;`__init__` 时 `lead_mail_event = asyncio.Event()`
3. coordinator 应用迁到 `src/gcode/cli/__init__.py` 中的 main_agent 上(`set_allowed_tools` + `append_system_prompt`)——tui 自身只负责状态栏渲染
4. 状态栏渲染时若 `app.coordinator_mode is True` 在 mode label 后追加 ` [COORDINATOR]`(参见 `src/gcode/tui/view.py status_bar()`)
5. config 字段名是 **snake_case**:`features.coordinator_mode`

**验证:** 在 config.yaml 加 `features:\n  coordinator_mode: true`,启动时设环境变量 `GCODE_COORDINATOR_MODE=1`,观察状态栏出现 `[COORDINATOR]`

## T27: /team slash 命令 — `src/gcode/command/builtin_team.py`**文件:** `src/gcode/command/builtin_team.py`
**依赖:** T3
**步骤:**
1. 注册 4 个本地命令(`Kind.LOCAL`):
   - `/team list`(F59)
   - `/team info <name>`(F60)
   - `/team delete <name> [--force]`(F61)
   - `/team kill <member>`(F62)
2. 在 `register_builtins` 或对应注册入口加入

**验证:** `/team list` 在 TUI 输出含已创建 Team

## T28: cli wire — `src/gcode/cli/__init__.py` 修改**文件:** `src/gcode/cli/__init__.py`(修改)
**依赖:** T1-T27
**步骤:**
1. 构造 `name_reg = AgentNameRegistry()`
2. `task_mgr.set_name_registry(name_reg)`
3. 构造 `team_mgr = team.Manager(home, root, worktree_mgr, task_mgr, name_reg)`
4. 注册 7 个新工具到 registry(TeamCreate/TeamDelete/TaskCreate/TaskGet/TaskList/TaskUpdate/SendMessage)
5. `agent_tool = AgentTool(..., team_hook=team_mgr)`(把 team_mgr 作为 TeamHook 注入)
6. 构造 `GCodeApp(..., team_mgr=team_mgr, coordinator_mode=coordinator.is_enabled(cfg))`
7. 若 `--team-member` flag 出现:**所有依赖 wire 完成后**直接调 `await run_team_member(team_member_args)` 并 `return`,**不**构造 TUI(F19a);否则继续走 TUI 路径
8. Lead 启动时(TUI 路径)若 `coordinator.is_enabled(cfg)`:`main_agent.set_allowed_tools(coordinator.allowed_tools())` + `main_agent.append_system_prompt(coordinator.system_prompt_suffix())`

**验证:** `python -m gcode` 主流程能启动 TUI;`ruff check src/gcode/cli/` 通过

## T29: --team-member 自治循环 — `src/gcode/cli/team_member.py`(新文件)**文件:** `src/gcode/cli/team_member.py`(新建)
**依赖:** T28
**步骤:**
1. 解析新增 CLI flags:`--team-member` / `--team` / `--member` / `--agent-id` / `--session-dir` / `--worktree` / `--agent-type` / `--model` / `--plan-mode`(用 `argparse` 或 `click`)
2. `cli/__init__.py` 中在 `--team-member` 分支先 `os.chdir(args.worktree)`,再 wire 完所有依赖
3. 实现 `async def run_team_member(args)`:
   - 从 `args.team_mgr.get(team_name)` 拿 Team(已含 Lead 写入的 alice 条目,reload-from-disk 兜底)
   - 解析角色定义(`subagent.catalog.resolve(agent_type)`),拿 system_prompt / max_turns / plan 等
   - 用 `apply_agent_tool_filter(FilterParams(teammate=True, ...))` 算 allowed tools
   - 构造 provider(`llm.new_provider`)+ `agent.Agent`,**强制 `dont_ask=True`**(F39a)
   - 注入 `<team-context>` reminder(F40) + ctx 装 `TeammateContext(mailbox=mc)`
   - 起一个 stdin reader asyncio task(`loop.add_reader(sys.stdin.fileno(), ...)` 或 `asyncio.StreamReader` over stdin):每读一行就 `wake_event.set()`,触发 mailbox 即时轮询
   - 进主循环(F19a):read unread → 分流消息(text 拼 task / plan_approval / shutdown_request)→ `run_to_completion` → 通知 Lead idle → `set_member_active(False)` → 等下一条
   - 检测 mailbox 目录消失 → 优雅退出
4. 把 `agent.Event` 流转 stdout 打印(`print_agent_event`),pane 内呈现只读日志

**验证:** 见 AC28 步骤 4 端到端实跑——alice pane 内显示 task 执行流,`/tmp/test_alice.txt` 落地,SendMessage 后 alice 能续派

## T30: 队员空闲通知 hook 注入**文件:** `src/gcode/cli/__init__.py`(修改)+ `src/gcode/team/manager.py`(加 helper)
**依赖:** T21, T3
**步骤:**
1. 在 `cli/__init__.py` wire 后,注册 `on_task_done` 回调到 `task_mgr`:
   ```python
   async def _on_done(task_id: str) -> None:
       await team_mgr.handle_task_done(task_id)
   task_mgr.on_task_done(_on_done)
   ```
2. 实现 `async Manager.handle_task_done(agent_id)`:
   - 查 `registry.name_of(agent_id) → name`
   - 遍历 teams 找到该成员所属 Team
   - `await set_member_active(name, False)`
   - `await mailbox.write(lead_agent_id, Message(type=TEXT, summary=f"{name} idle"))`

**验证:** 集成测试:in-process 后端 spawn 队员 → 自然结束 → 断言 Team.config 中 `is_active=False`、Lead mailbox 有 idle 消息

## T30b: Lead mailbox 轮询 + 自动唤醒 — `src/gcode/team/manager.py` + `src/gcode/tui/tasks.py` + `src/gcode/tui/app.py` + `src/gcode/tui/stream.py`**文件:**
- `src/gcode/team/manager.py`(增加 `poll_lead_mailboxes` + `LeadMessage`)
- `src/gcode/tui/tasks.py`(增加 `consume_lead_mail` / `wait_for_lead_mail` / `build_team_update_reminder` / `lead_mail_message`)
- `src/gcode/tui/app.py`(`on_mount` 启动 watcher;`on_message` 处理 `LeadMailMessage`)
- `src/gcode/tui/stream.py`(增加 `begin_autonomous_turn`)
**依赖:** T28(cli 已 wire team_mgr 进 TUI 参数)
**步骤:**
1. `team.Manager.poll_lead_mailboxes()`:遍历 `m.list_()`,对每个 Team 用 `Box(t.mailbox_dir).read_unread(t.lead_agent_id)` 读未读,标 read,返回 `list[LeadMessage(team_name, from_, type, summary, content, time)]`
2. TUI App 加字段 `lead_mail_event: asyncio.Event`(`__init__` 时初始化)
3. `consume_lead_mail`(TUI `on_mount` 启动 asyncio task):1 秒 sleep ticker → `poll_lead_mailboxes` → 非空时调 `build_team_update_reminder`(列消息条目 + content 截断 8000 字)→ `runtime.append_reminders` → `lead_mail_event.set()`
4. `wait_for_lead_mail(event)`:asyncio task,`await event.wait()` 后 `event.clear()`,通过 `app.post_message(LeadMailMessage())` 转给 Update handler;`on_mount` 同时启动这条 task
5. App 处理 `on_lead_mail_message`:
   - 重新 `asyncio.create_task(wait_for_lead_mail(event))` 让后续信号也能接住
   - 若 `app.state == SessionState.IDLE`,调 `await begin_autonomous_turn` 自动开新轮
   - 否则 reminder 已在 `pending_reminders` 里,等当前 Run 下一轮迭代自然取出
6. `begin_autonomous_turn`:合成 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."`,`conv.add_user(...)` + 调 `begin_turn(user_block(...))`——保证 LLM 调用满足"对话末尾必须 user"约束,用户在 RichLog scrollback 也能看见是自动触发

**验证:** tmux 实跑——Lead 派 alice + bob;30 秒内队员 run_to_completion idle 后 mailbox.unread 1 秒内归零(watcher 消费);若 Lead 当时空闲,屏幕上自动出现 `● [team-update] 队员发来新消息...` 用户文本块 + Lead 紧接着的 Synthesis 回复——内容包含队员报告里的真实文件名(如 `agent.py`、`team_mailbox.py`),证明完整 content 通过 reminder 传到 Lead 视野

## T31: 续写检测 — `src/gcode/team/tools/send_message.py`**文件:** `src/gcode/team/tools/send_message.py`(同 T22)
**依赖:** T22, T21
**步骤:**
1. `SendMessage.execute` 写完邮箱后:
   - 取目标 TeammateInfo.backend_type
   - 若 backend_type=in-process:
     - 查 `task_mgr.get(agent_id)`,若 `status != Running`:
       - `await Team.set_member_active(name, True)`
       - `await task_mgr.send_message(ctx, name, content)` 走 ch13 续派接口
   - 若 Pane 后端:已通过 wake 唤醒,无需续派

**验证:** 单测:先 spawn → 等结束 → SendMessage → 断言 task 重新 Running

## T32: Plan 审批权限切换 — `src/gcode/agent/team_mailbox.py`**文件:** `src/gcode/agent/team_mailbox.py`(修改)
**依赖:** T20
**步骤:**
1. 在 incoming-messages 注入逻辑中:若有 `plan_approval_response(approve=True)` 消息:
   - 调 `agent.set_permission_mode(PermissionMode.DEFAULT)`(或 Lead 当前模式,本期固定 default)
   - reminder 加文案:「Lead 已批准计划,权限模式已切到 default,可执行计划」
2. 若 `approve=False`:reminder 加文案:「Lead 驳回了计划,反馈:<feedback>。请调整后重新提交」

**验证:** 集成测试:队员以 plan 模式起步 → 收到 plan_approval_response(true) → `agent.permission_mode` 切换

## T33: 单元测试集 — 各模块 test_*.py**依赖:** T1-T32
**步骤:**
1. 跑 `pytest`,补失败用例
2. 跑 `ruff check src/`,修警告
3. 跑 `ruff format --check src/` 看无未格式化文件
4. 可选:`mypy src/gcode/team/` 全绿

**验证:** 全绿

## T34: tmux 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. 启动 tmux:`tmux new-session -s ch15-test`
2. 在内层跑 `cd /path/to/gcode && uv run python -m gcode`(或 `gcode` 装好的入口)
3. 在 TUI 输入:「创建一个名为 demo 的团队」
4. 观察:
   - Agent 调 TeamCreate
   - `~/.gcode/teams/demo/config.json` 落地
   - 状态栏 / 输出确认成功
5. 在 TUI 输入:「派 alice 用 general-purpose,在 worktree 里 echo hello > /tmp/test_alice.txt」
6. 观察:
   - tmux split 出新 pane
   - alice pane 内 gcode 子实例启动
   - `.gcode/worktrees/team-demo+alice/` 创建
   - `/tmp/test_alice.txt` 文件内容为 `hello`
7. 在 TUI 输入:`/team info demo`,确认 alice 出现
8. 在 TUI 输入:「给 alice 发消息,让她再写一行 world」(Agent 调 SendMessage)
9. 观察:alice pane 被唤醒,`/tmp/test_alice.txt` 多一行 `world`
10. `/team delete demo --force`,清理

**验证:** 步骤全部成功

## T35: in-process 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. `unset TMUX TERM_PROGRAM`
2. `cd /path/to/gcode && uv run python -m gcode`
3. Agent 调 TeamCreate("inproc") → backend 为 in-process
4. Agent 派 bob(后端 in-process)
5. bob 在同进程跑完
6. 观察 `team.config.json` 中 bob 的 `is_active=False`
7. Lead 调 SendMessage(to="bob", message="再做一件事"),bob 从 session 恢复继续

**验证:** 全部成功

## 执行顺序

```
T1 → T2 → T3 → T4
              ↘
T5 → T6        T8 ── T9(把 lock 抽出,T6/T8 改 import)
T7
T10 → T11
   → T12,T13,T14(并行)
T15
T16 → T17 → T18 → T19
                → T20 → T32
T21
T22 → T23 → T31
T24 → T25 → T26
T27
T28 → T29 → T30
T33(收尾测试)
T34, T35(实跑验收)
```

并行机会:T5/T7/T8 互不依赖;T12/T13/T14 互不依赖;T22 中 7 个工具可分批。
````

```markdown
# Agent Team Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为而非实现细节。

## 实现完整性

- [ ] `team.Manager` 可被实例化:`team.Manager(home, root, wt_mgr, task_mgr, name_reg)` 返回非 None(验证:`python -c "from gcode.team import Manager"`、跑单测)
- [ ] `await team.Manager.create("demo", "")` 在 `~/.gcode/teams/demo/config.json` 落地(验证:运行单测后检查文件存在)
- [ ] `await team.Manager.create("foo bar/baz", "")` sanitize 后路径为 `~/.gcode/teams/foo-bar-baz/`(验证:单测)
- [ ] 同名 Team 第二次 create 自动后缀 `-2`(验证:单测)
- [ ] `team.BackendType` 三个值齐全:`TMUX` / `ITERM2` / `IN_PROCESS`(验证:`ruff check` 通过 + 单测枚举)
- [ ] `backend.detect()` 在 `$TMUX` 设置时返回 `TMUX`;两环境变量都清空时返回 `IN_PROCESS`(验证:`monkeypatch.setenv` 单测)
- [ ] `mailbox.Box.write` + `mailbox.Box.read` 一进一出消息字段一致(验证:单测)
- [ ] `mailbox` 文件锁在 stale 10 秒后能被新 writer 抢占(验证:单测制造 11 秒前的锁,断言能拿到)
- [ ] `registry.AgentNameRegistry.register("alice", "agent-123")` 后 `resolve("alice")` 返回 `"agent-123"`,`name_of("agent-123")` 返回 `"alice"`(验证:单测)
- [ ] `tasks.Store.create` 返回的 task id 形如 `task_<6 位 hex>`(验证:单测)
- [ ] `await tasks.Store.update(id_, Patch(add_blocked_by=[other]))` 同时给 other 任务的 `blocks` 加上 id(验证:单测断言双向)
- [ ] `await tasks.Store.list_(Filter(status=PENDING))` 返回结果带 `is_ready` 字段,反映 blocked_by 是否全 completed(验证:单测)
- [ ] `coordinator.is_enabled` 在 feature flag 关 + 环境变量开时返回 False(验证:单测 4 种组合)
- [ ] `coordinator.allowed_tools()` 含 `bash` 不含 `write_file` / `edit_file`(验证:单测)
- [ ] `tool.apply_agent_tool_filter(FilterParams(teammate=True, ...))` 返回值含 `TaskCreate` / `SendMessage` 等 5 个协作工具(验证:单测)
- [ ] `tool.apply_agent_tool_filter(FilterParams(teammate=False, ...))` 不含这 5 个工具(验证:单测)
- [ ] 7 个新工具注册到 registry 后,`registry.definitions()` 输出含 `TeamCreate` / `TeamDelete` / `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage`(验证:单测或启动后 `/status`)
- [ ] `Team.add_member` 与 `Team.set_member_active` 调用前先 `reload_from_disk_locked` 重读 disk(验证:跨进程并发写 disk 时不丢更新——单测制造"Lead 在 alice 子进程读完 config 之后才 add_member"的时序,alice 走 `set_member_active(False)` 后回读 disk 应看到 `is_active=False`)

## 集成

- [ ] `Agent` 工具不带 `team_name` 时走 ch13 原路径,行为不变(验证:`pytest tests/test_agent_tool.py` 全过)
- [ ] `Agent` 工具带 `team_name="demo"` 时调 `team_hook.spawn_teammate`(验证:单测 mock team_hook,断言被调用)
- [ ] `spawn_teammate` 创建 worktree 路径为 `.gcode/worktrees/team-demo+alice`(验证:单测/集成测试)
- [ ] `spawn_teammate` 后 `team.members` 含 alice,持久化到 `config.json`(验证:单测)
- [ ] in-process 后端的队员 ctx 含 TeammateContext,其 backend_type=in-process;该队员调用 `Agent(team_name=...)` 被拒绝并抛 `InProcessTeammateNoSpawnError`(验证:集成测试)
- [ ] 队员 `Agent.run` 头部读取 mailbox 未读消息,以 `<incoming-messages>` reminder 注入到 LLM 输入(验证:单测,fake mailbox 写消息,捕获 Agent 构造的 prompt)
- [ ] 队员收到 `plan_approval_response(approve=True)` 后 `Agent.permission_mode` 切换到 default(验证:单测 + tmux 实跑——见场景 4)
- [ ] 队员 `run_to_completion` 结束触发 `on_task_done` 回调,Team config 中该成员 `is_active=False`(验证:单测注册回调 + launch noop task)
- [ ] 队员 idle 后 Lead mailbox 收到 `summary="<name> idle"` 消息(验证:单测/集成)
- [ ] `SendMessage(to="alice", ...)` 在 alice 已 stop 且为 in-process 后端时,通过 `task_mgr.send_message` 续派(验证:集成测试,断言 task status 回到 Running);Pane 后端时通过 `backend.wake` 让子进程读 mailbox 自然续派
- [ ] 所有 Team 队员一律 `dont_ask=True`(覆盖角色 frontmatter 的 `permission_mode`),子进程没人能应答 ApprovalRequest 不会卡死(验证:用 `permission_mode: default` 的角色派队员让她调 bash,实跑断言任务正常完成,而不是卡在 Ask)
- [ ] Pane 后端 spawn 时 `initial_prompt` 通过预写入 mailbox(type=text, from=lead)送达,子进程不需要走 CLI 参数(验证:tmux 实跑,在 spawn 完检查 alice mailbox 已有一条 from=lead 的初始任务)
- [ ] Pane 后端子进程命令行含 `--agent-id <id>` 参数(验证:看 `build_member_cmd` 单测;tmux 实跑后 `ps auxww | grep team-member` 看实际命令)
- [ ] Pane 后端的 `python -m gcode --team-member` 子进程**不启动 TUI**(不构造 Textual App),跑 `run_team_member` 自治协程——读 mailbox → run_to_completion → 通知 Lead idle → stdin Wake 等下一轮(验证:tmux 实跑看 alice pane 显示纯文本日志流而非 Textual TUI 框)
- [ ] Lead mailbox watcher 每秒轮询所有 Team 的 lead.json,把未读消息转 `<team-update>` reminder 推 `pending_reminders` + 给 `lead_mail_event` `set()`(验证:tmux 实跑后看 alice 发完 idle 通知 1 秒内 mailbox 的 unread 归零、read 累加)
- [ ] Lead 在 `SessionState.IDLE` 时收到 `LeadMailMessage`,TUI 调 `begin_autonomous_turn` 合成 user 消息自动开新轮(验证:tmux 实跑——派完队员等他完成,Lead 不需要用户输入就自动出现 `[team-update]...` 行 + Synthesis 回复)
- [ ] `/team list` 输出含 `~/.gcode/teams/` 下所有 Team(验证:TUI 实跑)
- [ ] `/team delete demo --force` 调 `backend.kill` 杀 pane(tmux/iterm2)+ 清 worktree + 清 team 目录(验证:TUI 实跑后 `tmux list-panes` 只剩 Lead,worktree 与 team 目录都消失)
- [ ] 沙箱开放 `/tmp` 与 `/private/tmp`(macOS 真实路径)作为白名单——write_file/edit_file 可写 `/tmp/foo.txt`,但 `/etc/passwd` 仍拒(验证:单测 `test_sandbox_contains` 含两组用例)

## 编译与测试

- [ ] `python -m gcode --help` 能正常启动且打印帮助(验证:命令退出码 0)
- [ ] `ruff check src/` 无警告(验证:命令退出码 0)
- [ ] `ruff format --check src/` 无未格式化文件(验证:命令退出码 0)
- [ ] `pytest` 全部通过(验证:命令退出码 0)
- [ ] 可选:`mypy src/gcode/team/` 全绿

## 端到端场景(tmux 实跑)

> 这是本章的核心验收场景,必须在真实 tmux 会话内手动跑一遍。

**场景 1:tmux 后端,Team 全生命周期**

环境准备:
- macOS / Linux
- tmux 已安装
- 当前不在 gcode 进程内,准备开新 tmux 会话

步骤:
- [ ] `tmux new-session -s ch15-test` 进入新 tmux 会话
- [ ] `cd /path/to/gcode && uv sync`(预装依赖,加快冷启动)
- [ ] `uv run python -m gcode`(或装好的 `gcode` 入口)启动 TUI;启动消息显示一切正常,无 ch15 相关 error
- [ ] 在 TUI 输入:「创建一个名为 demo 的团队」
  - 预期:Agent 调 `TeamCreate(team_name="demo")`;返回 `{"team_name":"demo","backend":"tmux","config_path":"..."}`
  - 验证:`ls ~/.gcode/teams/demo/config.json` 存在;`cat config.json` 中 `backend` 字段为 `tmux`
- [ ] 在 TUI 输入:「派 alice 用 general-purpose 角色,在 worktree 里跑 `echo hello > /tmp/test_alice.txt && pwd > /tmp/test_alice_pwd.txt`」
  - 预期:Agent 调 `Agent(team_name="demo", subagent_type="general-purpose", name="alice", prompt="...")`
  - 验证 a:tmux 自动 split 出右侧 pane(`tmux list-panes -F "#{pane_id} #{pane_current_command}"` 看到新 pane)
  - 验证 b:新 pane 内**显示自治循环日志流**(`[team-member] alice · team=demo · agent=... · cwd=...` 起始行 + Agent 工具调用打印,**不是** Textual TUI 框)
  - 验证 c:`ls /path/to/gcode/.gcode/worktrees/team-demo+alice/` 目录存在
  - 验证 d:等待 30 秒,`cat /tmp/test_alice.txt` 内容为 `hello`
  - 验证 e:`cat /tmp/test_alice_pwd.txt` 内容为 worktree 路径(`.../team-demo+alice`)
  - 验证 f:`cat ~/.gcode/teams/demo/config.json` 中 `members` 数组含 alice,`backend_type="tmux"`,`pane_id` 非空
  - 验证 g:`~/.gcode/teams/demo/mailbox/<alice_agent_id>.json` 中应已含一条 `from=lead` 的 text 消息——Pane 后端的 initial_prompt 预写入证据
- [ ] 在 TUI 输入 `/team info demo`
  - 预期:输出含 alice 行,显示 worktree、pane_id、is_active 状态
- [ ] 在 TUI 输入:「给 alice 发消息,让她再写一行 world 到 /tmp/test_alice.txt」
  - 预期:Agent 调 `SendMessage(to="alice", summary="append world", message="...")`
  - 验证 a:alice pane 被唤醒(`tmux send-keys` 触发,pane 显示新内容)
  - 验证 b:30 秒内,`cat /tmp/test_alice.txt` 看到第二行 `world`
- [ ] 等待 alice 任务自然结束(或在 TUI 输入 `/team kill alice` 终止)
  - 验证 a:`cat ~/.gcode/teams/demo/config.json` 中 alice 的 `is_active` 为 `false`(跨进程 reload 修复——alice 子进程的 `set_member_active(False)` 必须真的反映到 disk;早期 bug 是静默 no-op)
  - 验证 b:Lead 的 mailbox(`cat ~/.gcode/teams/demo/mailbox/lead.json`)含一条 `summary` 含 `idle` 的消息,且 1-2 秒后该消息 `read=true`(watcher 已消费)
  - 验证 c:Lead 屏幕**不需要用户输入**自动出现 `● [team-update] 队员发来新消息...` 文本块 + 紧接的 Synthesis 回复(自动唤醒)
- [ ] 在 TUI 输入 `/team delete demo --force`
  - 验证 a:`ls ~/.gcode/teams/` 无 `demo` 目录
  - 验证 b:`ls /path/to/gcode/.gcode/worktrees/` 无 `team-demo+alice`
  - 验证 c:`tmux list-panes` 只剩 Lead pane,alice 的 `%1` 被 `backend.kill` 干掉了

**场景 2:in-process 后端实跑**

环境准备:
- `unset TMUX TERM_PROGRAM`(确保 detect_backend 选 in-process)
- 在非 tmux 终端窗口内

步骤:
- [ ] 启动 `uv run python -m gcode`(同会话已 unset 上述变量)
- [ ] 在 TUI 输入:「创建 inproc 团队」
  - 验证:`cat ~/.gcode/teams/inproc/config.json` 中 `backend` 为 `in-process`
- [ ] 在 TUI 输入:「派 bob 用 general-purpose,在 worktree 里 `echo step1 > /tmp/bob.txt`」
  - 验证:无新终端窗口/pane 出现(同进程 asyncio task)
  - 验证:`/tmp/bob.txt` 内容 `step1`
- [ ] 等 bob 结束(`/team info inproc` 看 `is_active=False`)
- [ ] 在 TUI 输入:「给 bob 发消息让他再加一行 step2」
  - 验证:`/tmp/bob.txt` 多一行 `step2`
  - 验证:`/team info inproc` 看 bob 在 active → idle 反复变化
- [ ] `/team delete inproc --force` 清理

**场景 3:Coordinator Mode 实跑**

环境准备:
- `.gcode/config.yaml` 加 `features:\n  coordinator_mode: true`(snake_case)
- 设环境变量 `GCODE_COORDINATOR_MODE=1`

步骤:
- [ ] `GCODE_COORDINATOR_MODE=1 uv run python -m gcode`
- [ ] 观察 TUI 状态栏出现 `[COORDINATOR]` 标签
- [ ] 在 TUI 输入:「写一个 hello world 到 /tmp/coord_test.txt」
  - 预期:`write_file` **不在 Lead 工具集**(被 `set_allowed_tools` 剥夺),LLM 应该说"我没有 write_file 工具"并尝试用 bash 转写
  - 验证:`cat /tmp/coord_test.txt` 文件不存在(若用户拒掉 bash 的话)
- [ ] 在 TUI 输入:「跑 `git status`」
  - 预期:Agent 调 `bash`,工具正常执行(bash 在 Coordinator 白名单中)
  - 验证:输出含 git 状态信息
- [ ] 在 TUI 输入:「派几个队员探索 gcode 的 src/gcode/agent 和 src/gcode/team」
  - 预期:Lead 调 Agent + SendMessage 派出队员后,**不**立刻调 read_file/glob/bash 自己探索(被 Coordinator system prompt 中的纪律段约束)
  - 验证:Lead 派完队员的回复应该是"等待汇报中"类似措辞;在队员发完 idle 消息前 Lead 屏幕没新工具调用

**场景 4:Plan 审批工作流**

环境准备:无特殊

步骤:
- [ ] 准备一个角色定义 `~/.gcode/agents/planner.md`,frontmatter 含 `permission_mode: plan`,body 简述「先制定计划」
- [ ] 启动 gcode,创建 team `plan-test`
- [ ] 在 TUI 输入:「派 planner 用 planner 角色,在 worktree 制定 hello world 程序的实现计划」
  - 预期:planner 队员以 plan 模式起步,生成计划后通过 SendMessage 发给 Lead
  - 验证:Lead mailbox 含计划消息
- [ ] 在 TUI 输入:「批准 planner 的计划」
  - 预期:Lead 调 `SendMessage(to="planner", type="plan_approval_response", payload={approve:True})`
  - 验证:planner 收到后切换权限模式,继续执行计划

## 失败回归

- [ ] gcode 启动时 `~/.gcode/teams/` 不存在,自动创建,不报错
- [ ] `~/.gcode/teams/<somename>/config.json` 内容损坏时,启动只 stderr 警告,跳过该 Team
- [ ] 创建 Team 时若 disk 写失败(可手动 chmod 模拟),抛错,不留半成品目录
- [ ] mailbox 文件锁抢占冲突 10 次仍失败时,SendMessage 抛错,不丢消息
- [ ] tmux 后端在 `tmux split-window` 失败时(非 tmux 会话),抛错,Team.members 不留半成品
- [ ] 协作工具被主 Agent 误调用(主 Agent 工具列表本应不含)时,工具自己也抛错兜底
```

### Java

````markdown
# Agent Team Spec## 背景

ch13 SubAgent 把任务从单 Agent 委派给子 Agent,实现了消息、权限账本、文件读缓存与 token 计数的隔离;ch14 Worktree 给每个子 Agent 配上独立工作目录,文件系统层并发也安全。但这两章合起来仍是「星型」拓扑——所有子 Agent 只能与主 Agent 通信,子 Agent 之间没有横向通道;主 Agent 既要决策、又要中转,既是大脑也是邮局。对「同时重构四个模块」「三个角度查同一个 bug」这类持续性、需要互相交流的工作,星型结构的瓶颈很明显。

本章把 gcode 从星型升级到「网状」:

- 主 Agent 创建 **Team** 后升任 **Lead**,Team 是一个长期存在的小组对象,记名称、负责人、成员花名册、持久化位置
- 每个 **队员**(Teammate)是一个独立的 Agent 实例,有自己的 Conversation、自己的 Worktree
- 三种执行后端 `tmux` / `iterm2` / `in-process` 覆盖不同环境;按优先级一次性自动检测,启动后不静默回退
- 队员之间通过**共享任务列表**与**邮箱**直接通信,不必经过 Lead 中转;协作工具仅在 Team 上下文出现
- 队员可暂停可续写,自然停下后 session 留盘,Lead 调 `SendMessage` 会从磁盘恢复后继续指派
- Lead 可选启用 **Coordinator Mode**(独立于 Team,但典型场景一起用),双锁机制下剥夺 Write/Edit 工具,只保留调度、读类操作与 shell(用于 git merge)
- 收敛阶段由 Lead 用 Bash 跑 `git merge` 逐个合各队员的 worktree 分支,冲突由 LLM 推理解决,搞不定就 `git merge --abort` 保留 worktree 上报用户

gcode 现有相关基础设施:
- ch13 `task.Manager` 已支持后台任务管理 + `sendMessage` 续派 + `AgentNameRegistry` (`byName` 字段已是 name → id 映射);本章扩展为多 Team 寻址
- ch13 `agent.AgentTool.execute` 已是子 Agent 启动入口,本章新增 `teamName` 参数走 Team spawn 分支
- ch13 工具过滤 `tool.applyAgentToolFilter` 已支持多层防线;本章新增 Team 专属白名单(协作工具)与 Coordinator Mode 白名单
- ch14 `worktree.Manager` 已支持嵌套 slug(`team/alice` → `.gcode/worktrees/team+alice/`),本章直接复用做队员 worktree(slug 形式 `team-<teamName>/<member>`)
- ch12 session 持久化(`.gcode/sessions/<id>/conversation.jsonl`)按对话粒度落盘;本章给每个队员单独申请一个 session,队员 stop 不删 session,SendMessage 续派时通过 session 反序列化 Conversation
- ch10 `dev.gcode.command` slash 命令系统,本章新增 `/team` 系列
- ch07 `permission` 已支持 `plan` 模式,本章给 `planModeRequired` 队员的 Plan 提交-Lead 审批工作流套用同一引擎

本章**只做**到「Lead 多人协作 + Plan 审批 + Coordinator 收敛」。跨进程跨机器分布式团队、队员之间实时流式通信、复杂任务依赖约束(优先级 / deadline)、Windows 平台 iTerm2 适配均不在范围内。

## 目标- **G1**: 提供 `Team` 与 `TeamManager`——Team 封装小组生命周期(name、leadAgentId、members、configPath);Manager 在单 gcode 进程内管理多个 Team(典型场景同时只有一个活跃 Team)
- **G2**: 提供 `TeamCreate` 工具——主 Agent 调用即创建 Team、调 `detectBackend` 确定后端、写 `~/.gcode/teams/<sanitizedName>/config.json`、把 Lead 注册成第一个成员;同名团队自动后缀 `-2` / `-3` 避免冲突
- **G3**: 扩展 `Agent` 工具——增加 `teamName` 可选参数,非空时走 Team spawn 分支:加载定义 → 创建队员 Worktree → 注入协作工具 → 按后端分流 spawn → 注册到 `AgentNameRegistry` → 写入 `team.members`
- **G4**: 提供 `TeamDelete` 工具——确认所有成员 `isActive=false` 后,删队员 worktree + 删 team 目录,Lead 退出团队;有活跃成员时拒绝删除
- **G5**: 三种执行后端 `tmux` / `iterm2` / `in-process`,统一抽象 `Backend` 接口;`detectBackend` 按 `$TMUX → $TERM_PROGRAM=iTerm.app && which it2 → which tmux → in-process` 优先级一次性决定,不做运行时回退
- **G6**: 队员注入 5 个协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate`(后者支持 `addBlocks` / `addBlockedBy` 依赖字段) / `SendMessage`;主 Agent 与普通 SubAgent 看不到这些工具
- **G7**: `SendMessage` 寻址支持 `to="<name>"`、`to="<agentId>"`、`to="*"` 广播三种;通过 `AgentNameRegistry` 解析 name → agentId,写邮箱;Tmux/iTerm2 后端额外通过 `send-keys` 唤醒目标 pane
- **G8**: 邮箱文件并发安全——每个收件人独占一个 lock 文件(`StandardOpenOption.CREATE_NEW`),抢锁失败按 5-100ms 随机抖动重试,最多 10 次;持锁超过 10 秒视为 stale 直接清掉;消息文件 read-modify-write,走 `Files.move(...,ATOMIC_MOVE)` 原子替换
- **G9**: 三种结构化消息——纯文本(必带 5-10 词 `summary`)、`shutdown_request` / `shutdown_response`(优雅退出协商)、`plan_approval_response`(Plan 审批回复,只允许 Lead 发送);全部走同一 SendMessage 入口,以 `type` 字段分流
- **G10**: 队员收到的未读消息在下一轮 Agent Loop 开头被读出,以 `<incoming-messages>` system reminder 形式注入到 LLM 输入;读后批量标记为 read
- **G11**: 队员 spawn 两种路径——指定 `subagentType` 走定义式(从空白对话起步)、留空走 Fork 路径(继承 Lead 完整对话历史);Fork 路径受 `FORK_TEAMMATE` feature flag 控制,默认关闭
- **G12**: 队员 `runToCompletion` 结束后自动通知 Lead——团队 config 里把该成员 `isActive=false`、Lead 邮箱收到 `idle_notification`;队员的 Conversation 已通过 ch12 Writer 实时写入 session 文件
- **G13**: 队员续写——Lead 调 `SendMessage(to="alice", message="…")`,系统检测 alice 已 stop 时,从 ch12 session 反序列化 Conversation、新建一条 virtual thread 走 `runToCompletion(initialMessage=newMessage)`;Conv 沿用历史
- **G14**: `planModeRequired:true` 的队员被 spawn 时强制以 plan 模式起步——计划生成后通过 SendMessage 发给 Lead,Lead 用 `plan_approval_response` 回复 approve 或 reject;approve 时队员权限模式切到 Lead 的当前模式继续执行,reject 时队员按 feedback 调整后重新提交
- **G15**: Coordinator Mode 独立于 Team——`Coordinator.isEnabled() = feature(COORDINATOR_MODE) && envTruthy(GCODE_COORDINATOR_MODE)`,两把锁全开才生效;开启后 Lead 工具集收窄到 `Agent / TeamCreate / TeamDelete / TaskCreate / TaskGet / TaskList / TaskUpdate / SendMessage / read_file / glob / grep / bash`(剥夺 `write_file` / `edit_file`),并注入 coordinator 系统提示词引导 Research / Synthesis / Implementation / Verification 四阶段
- **G16**: 收敛全部由 LLM 推理驱动——Lead 用 Bash 跑 `git merge worktree-team-<team>+<member> --no-ff -m "merge: <member>"` 逐个合,冲突由 Lead 用 Read / Edit / Bash 自行解决;搞不定就 `git merge --abort`,保留队员 worktree,把冲突上下文上报给用户
- **G17**: 提供 TUI slash 命令 `/team list` / `/team info <name>` / `/team delete <name>` / `/team kill <member>`,辅助用户人工介入
- **G18**: 与 ch04~ch14 既有功能协同——主 Agent 平时(未 TeamCreate)看到的工具列表不变;协作工具仅在 Team 上下文出现;ch13 后台任务 / AdoptRunning / SendMessage 续派路径保留,Team 队员的续派复用同一套底层 `TaskManager`

## 功能需求### Team 数据结构与 Manager- **F1**: `Team` 字段——`name`(原始名)、`sanitizedName`(经 `sanitize` 处理后用于路径)、`leadAgentId`、`members List<TeammateInfo>`、`configDir`(`<homeDir>/.gcode/teams/<sanitizedName>/`)、`configPath`(`<configDir>/config.json`)、`createdAt Instant`、`backend BackendType`
- **F2**: `TeammateInfo` 字段——`name`(Lead 分配的队员名,Team 内唯一)、`agentId`(对应 `BackgroundTask.id`)、`agentType`(使用的 subagent 定义名;Fork 路径下为 `""`)、`model`(覆盖,空表 inherit)、`worktreePath`(绝对路径)、`branch`(对应 worktree 分支名)、`backendType`(可 per-member 不同)、`paneId`(tmux pane / iterm2 split id,in-process 为空)、`isActive Boolean`(`null` 或 `true` 表活跃,`false` 表空闲;终止后直接从 `members` 移除)、`planModeRequired boolean`、`sessionDir`(队员独立 session 目录绝对路径)
- **F3**: `TeamManager` 字段——`lock ReentrantLock`、`teams Map<String,Team>`(按 `sanitizedName` 索引)、`homeDir`(`System.getProperty("user.home")`)、`worktreeManager`、`taskManager`、`registry AgentNameRegistry`
- **F4**: `TeamManager(Path homeDir, WorktreeManager wt, TaskManager taskMgr, AgentNameRegistry reg)`——校验 `<homeDir>/.gcode/teams/` 可写;扫描该目录还原 `teams` map(每个子目录读一次 `config.json`,跳过解析失败的并 stderr 警告)
- **F5**: `TeamManager.create(name, agentType)`——
  1. `sanitized = sanitize(name)`(只保留 `[a-zA-Z0-9._-]`,其他替换为 `-`,首尾去 `-`,空字符串拒绝)
  2. 同名冲突时在 `sanitized` 后追加 `-2` / `-3` 直到唯一
  3. 创建 `configDir`,落 `config.json`(原子写)
  4. 调 `detectBackend()` 写入 `team.backend`
  5. 取当前 Lead Agent id(本期 Lead = 主 Agent,固定 `"lead"`)
  6. 把 Lead 注册成第一个成员(`new TeammateInfo("lead","lead", null, ...)`,`isActive=null`)
  7. 加入 `teams` map,返回 Team
- **F6**: `TeamManager.get(name)`——按 sanitized name 查询,返回 `Optional<Team>`
- **F7**: `TeamManager.delete(name, force)`——
  1. 取 Team;不存在抛 `TeamNotFoundException`
  2. 非 force 时若有 `member.isActive != Boolean.FALSE`(包括 null 和 true)抛 `TeamHasActiveMembersException`
  3. 逐个删队员 Worktree(调 `worktreeManager.remove(name, new RemoveOptions(true))`,失败只警告不中断)
  4. 删队员 session 目录(`Files.walk(...).forEach(Files::delete)`,失败只警告)
  5. 删 `configDir`
  6. 从 `teams` map 移除
- **F8**: `Team.addMember(TeammateInfo info)`——校验 name 在 Team 内唯一;加入 `members`;持久化 `config.json`(原子写——先写 `.tmp` 再 `Files.move(...,ATOMIC_MOVE)`)
- **F9**: `Team.setMemberActive(name, active)`——更新 `isActive`,持久化
- **F10**: `Team.removeMember(name)`——从 `members` 移除,持久化

### 后端检测与抽象- **F11**: `BackendType` 枚举,取值 `TMUX` / `ITERM2` / `IN_PROCESS`,带 `wireValue()` 返回 `"tmux"` / `"iterm2"` / `"in-process"`
- **F12**: `Backend` 接口——
  ```java
  public interface Backend {
      BackendType type();
      // spawn 在后端启动一个新队员;返回 PaneID(in-process 返回空)。
      // 对 Pane 后端,spawn 会执行 split-window / it2 split + send-keys 启动 CLI。
      // 对 in-process 后端,spawn 在同进程起一条 virtual thread 跑 runToCompletion。
      SpawnResult spawn(SpawnRequest req) throws IOException;
      // wake 用于消息到达时唤醒目标 pane。in-process 后端为 no-op。
      void wake(String paneId, String agentId) throws IOException;
      // kill 终止 pane(Pane 后端)或 cancel virtual thread(in-process)。
      void kill(String paneId, String agentId) throws IOException;
  }

  public record SpawnResult(String paneId, String agentId) {}
  ```
- **F13**: `SpawnRequest`(record)字段——`teamName`、`memberName`、`agentId`、`worktreePath`、`sessionDir`、`agentType`、`model`、`initialPrompt`、`planModeRequired`、`subAgent Object`(in-process 用,实际类型 `Agent`,用 Object 避免反向依赖)、`conv Object`(`Conversation`)、`taskManager Object`(`TaskManager`)
  - 对 Pane 后端(tmux / iterm2),`initialPrompt` **不**走命令行——在 `backend.spawn` 调用前由 `TeamManager.spawnTeammate` 预写入 alice 的 mailbox(类型 `text`,from `lead`),子进程启动后读 mailbox 自然拿到。这样避免长 prompt 在命令行里 shell-quote 的边界问题。
- **F14**: `Backend.detect()`——按以下优先级一次性决定:
  1. `System.getenv("TMUX") != null` → `TMUX`
  2. `"iTerm.app".equals(System.getenv("TERM_PROGRAM"))` && PATH 中存在 `it2` → `ITERM2`
  3. PATH 中存在 `tmux` → `TMUX`(外部 spawn 新 session)
  4. 否则 → `IN_PROCESS`

### tmux 后端- **F15**: `TmuxBackend` 实现 `Backend` 接口
  - `spawn`:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`(横向 split,-P 打印 pane id,-F 指定格式);`cmd` 为 `gcode --team-member --team <teamName> --member <memberName> --agent-id <agentId> --session-dir <sessionDir> --worktree <worktreePath> [--agent-type <type>] [--model <model>] [--plan-mode]`
  - `--agent-id` 是关键:Lead spawn 时已生成的 agentId 直接传给子进程,子进程不需要读 Lead 还没写完的 `config.json` 找自己
  - `wake`:`tmux send-keys -t <paneId> "" Enter`(回车触发子进程 stdin scanner 读到一行,立刻去 mailbox 轮询;in-process 后端无此动作)
  - `kill`:`tmux kill-pane -t <paneId>`(忽略 pane 不存在错误)
- **F16**: 若当前在 tmux 会话外但本机有 tmux,spawn 走 `tmux new-session -d`(detached 新 session);若失败回落到错误而非 in-process(不静默回退)

### iterm2 后端- **F17**: `Iterm2Backend` 实现 `Backend` 接口
  - `spawn`:`it2 split --new-pane --command "<cmd>"`,`<cmd>` 与 F15 同构(含 `--agent-id`);通过 `it2` CLI 解析输出取 pane id
  - `wake`:`it2 send-text --pane <paneId> ""`(空文本即唤醒)
  - `kill`:`it2 close-pane --pane <paneId>`

### in-process 后端- **F18**: `InProcessBackend` 实现 `Backend` 接口
  - `spawn`:复用 `TaskManager.launch`——创建带 `withCwd(worktreePath)` 的子 Agent,在 virtual thread 里跑 `runToCompletion`;返回空 `paneId`,内部用 `BackgroundTask.id` 关联
  - `wake`:no-op(同进程,下一轮 Loop 自动读邮箱)
  - `kill`:调 `TaskManager.stop(agentId)`
- **F19**: in-process 后端的队员**只允许同步子 Agent**——其 `Agent` 工具看不到 `teamName` 参数(`teamName` 被拦截);后台子 Agent 也禁用(过滤 `runInBackground=true`)

### Pane 后端子进程的 team-member 模式- **F19a**: `gcode --team-member` 在 Pane 后端被 spawn 的 gcode 子进程**不启动 TUI**,而是跑一个自治循环(`dev.gcode.cli.TeamMemberRunner` 的 `run` 方法):
  1. 从 CLI 解析 `--team / --member / --agent-id / --session-dir / --worktree / --agent-type / --model / --plan-mode`(用 picocli 或 Apache Commons CLI 解析,本项目选 picocli `info.picocli:picocli`)
  2. `System.setProperty("user.dir", workTree)` + `Path.of(workTree).toAbsolutePath()` 作为后续所有 IO 的根;让该进程的 `Path.of("").toAbsolutePath()` 与权限沙箱根都指到 worktree
  3. 构造**单独的** `TeamManager`、provider、registry、permission engine、hook engine(完整复用 Lead wire 代码,但不构造 TUI)
  4. 构造队员 `Agent`,设 `dontAsk=true`(子进程无 TUI 接 ApprovalRequest)、注入 `<team-context>` reminder、用 `setCtxDecorator` 注入 `TeammateContext`(含 mailbox client)
  5. 启动 stdin scanner virtual thread:任何来自 tmux send-keys 的回车都推到 `wakeQueue`(`SynchronousQueue<Object>` 或 `BlockingQueue` size=1),触发立刻去 mailbox 轮询(0~2s 内响应)
  6. 进入主循环:
     - 读 `mailbox.readUnread(agentId)`
     - 空 → 阻塞 `wakeQueue.poll(2, SECONDS)` 兜底轮询
     - 有未读:`text` 拼成 task,`plan_approval_response(approve=true)` 触发 `setPermissionMode(DEFAULT)` + 续派 prompt,`shutdown_request` 触发优雅退出
     - 调 `agent.runToCompletion(conv, task, eventConsumer)` 让队员跑到底
     - 完成后:写 `summary="<name> idle"` 到 Lead mailbox,再 `Team.setMemberActive(name, false)`
     - 检测到 mailbox 目录已被删除(Lead 调用 `/team delete`)→ 优雅退出
- **F19b**: 该自治循环的最小事件转 stdout 打印:`TextEvent` 直接 `System.out.println`、`ToolEvent` 打 `● tool(args)` 行、`DoneEvent` 打分隔横线、错误打 stderr。pane 内 UX 是只读的「日志流」,不接受用户输入(任何回车都被 stdin scanner 消费做 Wake 信号)
- **F19c**: 跨进程 `config.json` 写入并发:Lead 与子进程是不同进程,各持一份内存中的 Team 对象。`Team.addMember` 与 `Team.setMemberActive` 在持锁后**先从磁盘 reload `members` 字段**再修改+原子 save(`reloadFromDiskLocked`)。否则会出现「子进程内存看不到自己,setMemberActive 静默 no-op」的丢更新问题

### TeamCreate 工具- **F20**: 工具名 `TeamCreate`,参数 schema:
  - `teamName`(string,必填):团队名,经 sanitize 后做 `Team.sanitizedName`
  - `description`(string,可选):团队描述,写入 `config.json` 的 `description` 字段
  - `agentType`(string,可选):本期保留位,实际不使用
- **F21**: `TeamCreate.execute`——
  1. 解析参数
  2. 调 `TeamManager.create(name, agentType)` 创建 Team
  3. 返回 JSON `{"teamName":"<sanitized>","backend":"<type>","configPath":"<path>"}`
  4. Lead 创建 Team 后保持原有工具集(非 Coordinator Mode 下不剥夺工具)

### TeamDelete 工具- **F22**: 工具名 `TeamDelete`,参数 `teamName`(必填)、`force`(可选 boolean)
- **F23**: `TeamDelete.execute`——调 `TeamManager.delete(name, force)`,返回成功/失败消息

### Agent 工具扩展 (teamName)- **F24**: `Agent` 工具参数 schema 新增字段:
  - `teamName`(string,可选):非空时走 Team spawn 分支
- **F25**: 当 `teamName` 非空,`Agent.execute` 走 Team 分支:
  1. 校验 `teamName` 对应的 Team 存在(`TeamManager.get`),否则报错
  2. 校验当前调用者权限:
     - 主 Agent / Lead → 允许
     - in-process 队员调 Team spawn → 拒绝(抛 `InProcessTeammateNoSpawnException`)
     - Pane 队员可以调(README:Pane 队员拥有完整 Agent 工具),但 `teamName` 参数被屏蔽(队员不能往 Team 加人,只 Lead 在 Coordinator Mode 或普通 Lead 调用时可以)
  3. 加载 `SubAgentDefinition`(指定 `subagentType` 走 Catalog;留空且 `FORK_TEAMMATE` 开启走 Fork 定义;留空且 flag 关闭则用 `general-purpose`)
  4. 调 `worktreeManager.create("team-"+sanitized+"/"+memberName, "HEAD", false)` 创建 Worktree
  5. 申请新 session 目录(复用 `session` 包接口),作为 `sessionDir`
  6. 构造 in-process 子 Agent(若后端为 in-process)或仅构造 SpawnRequest(若 Pane 后端);把协作工具注入到子 Agent 的 allowed tools 集合
  7. 注入队员系统提示词附录(F39)
  8. 注入 `<team-context>` initial system reminder 到子 Agent Conv
  9. **若是 Pane 后端**,在 `backend.spawn` 之前把 `initialPrompt` 作为 `text` 消息(`from=lead, summary=initial task`)预写入 alice 的 mailbox(F13);in-process 后端不需要,`initialPrompt` 直接作为 `TaskManager.launch` 的 task 参数
  10. 调 `Backend.spawn(req)` spawn,记 `paneId`
  11. 注册到 `AgentNameRegistry`:`memberName → agentId`
  12. 构造 `TeammateInfo` 加入 `team.members`,持久化(F19c 的 reload-before-modify 兜底)
  13. 返回 JSON `{"memberName":"<name>","agentId":"<id>","worktree":"<path>","backend":"<type>","paneId":"<id 或空>"}`

### 协作工具- **F26**: `TaskCreate` 工具——参数 `title`(必填)、`description`(可选)、`assignee`(可选,队员名)、`blockedBy`(可选 `List<String>`,任务 id);返回新建 `taskId`(`task_<6位 hex>`);写入 Team 的 `tasks.json`(原子)
- **F27**: `TaskGet` 工具——参数 `taskId`,返回任务详情
- **F28**: `TaskList` 工具——参数可选 `status` 过滤(`pending`/`in_progress`/`completed`/`blocked`);返回任务数组,带依赖关系标注(`blockedBy`、`blocks`、是否 `isReady`(无未完成 blocker))
- **F29**: `TaskUpdate` 工具——参数 `taskId`(必填)、`title`(可选)、`description`(可选)、`status`(可选)、`assignee`(可选)、`addBlocks`(可选 `List<String>`)、`addBlockedBy`(可选 `List<String>`)、`removeBlocks` / `removeBlockedBy`(可选 `List<String>`);更新后持久化
- **F30**: `tasks.json` 结构:
  ```json
  {
    "tasks": [
      {
        "id": "task_a1b2c3",
        "title": "...",
        "description": "...",
        "status": "pending",
        "assignee": "alice",
        "blockedBy": ["task_xxx"],
        "blocks": ["task_yyy"],
        "createdAt": 1234567890,
        "updatedAt": 1234567890
      }
    ]
  }
  ```
  写入走 `<teamConfigDir>/tasks.json`,read-modify-write,文件锁 `tasks.lock`(同邮箱 lock 机制)

### SendMessage 工具与邮箱- **F31**: `SendMessage` 工具——参数:
  - `to`(string,必填):队员名 / agentId / `"*"` 广播
  - `summary`(string,纯文本消息时必填,5-10 词)
  - `message`(string,可选,纯文本消息体)
  - `type`(string,可选,默认 `"text"`):取值 `"text"` / `"shutdown_request"` / `"shutdown_response"` / `"plan_approval_response"`
  - `payload`(object,可选):结构化消息的载荷(如 `shutdown_response` 的 `{approve, reason}`)
- **F32**: 邮箱文件路径——`<teamConfigDir>/mailbox/<agentId>.json`,结构:
  ```json
  {
    "messages": [
      {
        "from": "lead",
        "to": "alice",
        "type": "text",
        "summary": "interface change",
        "content": "...",
        "payload": null,
        "timestamp": 1234567890,
        "read": false
      }
    ]
  }
  ```
- **F33**: `Mailbox` 提供 `write(agentId, msg)` / `read(agentId)` / `markRead(agentId, indices)` 接口
  - `write`:抢 `<teamConfigDir>/mailbox/<agentId>.lock`(`Files.newOutputStream(..., StandardOpenOption.CREATE_NEW)`),失败 5-100ms 随机抖动重试 10 次;持锁超 10 秒视为 stale(`Files.getLastModifiedTime` 判定)直接删 lock 重试;成功后 read-modify-write,`Files.move(tmp, target, ATOMIC_MOVE)` 原子替换
  - 广播 `to="*"` 时,write 对 Team 内除发件人外所有成员的 mailbox 各 write 一次
- **F34**: `SendMessage.execute`——
  1. 校验调用者在 Team 内
  2. 解析 `to`:若 `"*"` 走广播;否则通过 `AgentNameRegistry.resolve(to)` 取 agentId(name 优先,失败按 agentId 直查);解析不到报错
  3. `plan_approval_response` 仅 Lead 可发,否则报错
  4. `shutdown_response` 只能发给 Lead,否则报错
  5. 调 `Mailbox.write`
  6. 取目标的 `backendType` 与 `paneId`,若是 Pane 后端调 `backend.wake(paneId, agentId)`
  7. 若目标 agentId 已 stop(in-process 后端):触发续写(F45)
  8. 返回 `{"deliveredTo":["<agentId>"],"timestamp":<ts>}`

### Agent 名称注册表- **F35**: `AgentNameRegistry` 字段——`lock ReentrantLock`、`byName Map<String,String>`(name → agentId)、`byId Map<String,String>`(agentId → name,反查)
- **F36**: 接口 `register(name, agentId)`、`unregister(name)`、`resolve(nameOrId)` 返回 `Optional<String>`、`nameOf(agentId)` 返回 `Optional<String>`
- **F37**: 注册时机——`Agent` 工具 spawn 队员时(F25 step 11);`AgentTool` 的 `name` 参数非空时(ch13 已有,本章统一这套 registry,替换 `TaskManager.byName` 的内部 map)
- **F38**: 命名冲突——后注册的覆盖前注册的(README 称「弱引用,后启动覆盖前面的弱引用」)

### 队员系统提示词附录- **F39**: 在子 Agent 的 systemPrompt 后追加(若 spawn 进 Team)以下文本(无变量):
  ```
  IMPORTANT: You are running as an agent in a team.
  Just writing a response in text is not visible to others
  on your team - you MUST use the SendMessage tool.
  The user interacts primarily with the team lead.
  Your work is coordinated through the task system
  and teammate messaging.
  ```
- **F39a**: 所有 Team 队员(三种后端共有)一律以 `dontAsk=true` 启动,**覆盖角色定义里的 `permissionMode`**。理由:队员没有可交互的 TUI 接 `ApprovalRequest`(in-process 走 TaskManager 聚合事件不响应、Pane 子进程更没有 TUI),Ask 工具会无人应答地永远阻塞。队员的安全边界由 allowed 工具集 + Worktree 隔离 + Plan 模式控制,不靠逐次 ask 弹窗(子进程没人在看)。
- **F40**: 在 spawn 时把 `<team-context>` 注入子 Conv 的首条 system reminder:
  ```
  <team-context>
  team: <teamName>
  你的成员名: <memberName>
  你的 agentId: <agentId>
  worktree 目录: <worktreePath>
  当前团队成员: <name1>(<role1>), <name2>(<role2>) ...
  </team-context>
  ```

### 邮箱读取与消息注入- **F41**: 子 Agent 的 Loop 在每轮请求 LLM **之前**先调 `Mailbox.read(agentId)`;若有未读消息,构造 `<incoming-messages>` system reminder 追加到本轮请求的 systemReminders,然后调 `markRead`
- **F41a**: Lead 侧不通过 ctx hook 自动读 mailbox(Lead 没有 `TeammateContext`),而是由 TUI 在初始化时启动后台 virtual thread `consumeLeadMail`(实现于 `dev.gcode.tui.LeadMailWatcher`):
  - 每秒调 `TeamManager.pollLeadMailboxes()`,遍历所有 Team 的 `<configDir>/mailbox/lead.json` 读未读消息,标 read,返回 `List<LeadMessage>`
  - 把这批消息渲染成 `<team-update>` reminder(与 `<incoming-messages>` 不同,Lead 视角语义更清晰;消息内容截断上限 8000 字符,允许队员的完整报告完整透传),调 `runtime.appendReminders(...)` 推到 `pendingReminders`
  - **同时**往 `leadMailQueue`(`LinkedBlockingQueue` capacity=1)`offer` 一个信号(非阻塞,buffer=1 合并掉重复)
  - Lead 下一轮 Run 迭代头部 `buildReminder` 自动取出。**Lead 即便正在长 Run 中也能中途惊醒**——下一个 LLM 调用前就会看到队员更新
  - 这是 Pane 后端队员通知 Lead 的关键路径:in-process 队员还有 `TaskManager.subscribeDone` → TUI `<task-notification>` 的额外路径,但 Pane 队员只能靠 mailbox + 本机制
- **F41b**: Lead idle 时的自动续推。TUI 通过 `LeadMailWaiter`(订阅 `Flow.Publisher`)阻塞在 `leadMailQueue` 上,收到信号后通过 GUI thread 提交 `LeadMailEvent`:
  - 若 `model.state == SessionState.IDLE`,调 `beginAutonomousTurn`:合成一条 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."` 加入对话历史(用户在 scrollback 也看得见,清楚是系统通知触发而非自己输入),然后走 `beginTurn` 启 Run
  - 若 `model.state` 非 idle(`STREAMING`/`APPROVING`):reminder 已经在 `pendingReminders` 里,Lead 当前 Run 的下一轮迭代头部自然取出,不需要主动 wake
  - 末尾 re-arm `LeadMailWaiter` 让后续信号也能接住
  - 这避免了「队员都 idle 了,Lead 在 IDLE 等用户输入,reminder 静默积累没人取」的卡死场景——这正是 ch15 协作 UX 的关键
- **F42**: `<incoming-messages>` 格式:
  ```
  <incoming-messages>
  收到 N 条新消息:
  [1] 来自 <from>(type=<type>,ts=<时间>): <summary>
      <content 前 200 字>
  [2] ...
  </incoming-messages>
  ```
- **F43**: 收到 `shutdown_request` 时,队员可在下一轮自主选择回复 `shutdown_response(approve=true)` 然后停止,或 `approve=false` 拒绝并附 reason(LLM 决策,不强制)
- **F44**: 收到 `plan_approval_response(approve=true)` 时,队员的权限模式自动切换到 Lead 当前模式(从 Team config 取);`approve=false` 时队员根据 `feedback` 调整重新发 Plan

### 队员空闲与续写- **F45**: 队员 `runToCompletion` 自然结束时(`TaskManager.runTask` 完成路径):
  1. 调 `Team.setMemberActive(memberName, false)`
  2. 给 Lead 邮箱写一条 `idleNotification`(`type="text", summary="<member> idle", content="agent <id> finished work, available for new tasks"`)
- **F46**: SendMessage 检测到目标 agentId 已 stop 且为 in-process 队员(`BackgroundTask.status` 不是 `RUNNING`):
  1. 从 `TeammateInfo.sessionDir` 反序列化 Conversation(`Session.load`)
  2. 调 `TaskManager.sendMessage(parentCtx, name, message)` 复用 ch13 已有续派接口
  3. `TaskManager.sendMessage` 重置 `status=RUNNING`,起新 virtual thread 跑 `runToCompletion(newMessage)`
  4. 续派前调 `Team.setMemberActive(memberName, true)`
- **F47**: Pane 后端队员的续写——SendMessage 写邮箱后,目标 pane 内的 gcode 实例下一轮 Loop 自然读到消息;若 pane 已死(`tmux list-panes` 查不到 `paneId`),报错让 Lead 决定是否重新 spawn

### Plan 审批工作流- **F48**: `Agent` 工具 spawn 队员时,若 `planModeRequired=true`(来自 SubAgentDefinition 的新字段或 spawn 参数),把子 Agent 的初始 `Permission.Mode` 设为 `PLAN`
- **F49**: 队员在 plan 模式下生成 Plan 后(通过常规 LLM 推理),用 `SendMessage(to="lead", type="text", summary="plan ready", content="<plan text>")` 发给 Lead——本期不强制结构化 Plan 类型(Lead 自行识别)
- **F50**: Lead 用 `SendMessage(to="<member>", type="plan_approval_response", payload={"approve":true|false,"feedback":"..."})` 回复
- **F51**: 队员收到 `plan_approval_response`:
  - `approve=true`:从 Team config 读 Lead 当前 `permissionMode`(本期固定 `DEFAULT`),切到该模式继续执行 plan
  - `approve=false`:把 `feedback` 当作新的用户消息加入对话,重新进入 plan 模式

### Coordinator Mode- **F52**: 提供 `Coordinator.isEnabled()` 静态方法:
  ```java
  public static boolean isEnabled(AppConfig cfg) {
      if (!Feature.has("COORDINATOR_MODE", cfg)) {
          return false;
      }
      return envTruthy(System.getenv("GCODE_COORDINATOR_MODE"));
  }
  ```
  `Feature.has` 通过 `dev.gcode.config` 读 `features.coordinatorMode` 字段;`envTruthy` 接受 `"1"` / `"true"` / `"yes"`(大小写不敏感)
- **F53**: Coordinator Mode 允许工具白名单常量:
  ```java
  public static final List<String> ALLOWED_TOOLS = List.of(
      "Agent", "TeamCreate", "TeamDelete",
      "TaskCreate", "TaskGet", "TaskList", "TaskUpdate",
      "SendMessage",
      "read_file", "glob", "grep", "bash"
  );
  ```
- **F54**: Lead 启动时(`tui` 主循环创建 Agent 后),若 `Coordinator.isEnabled(cfg)`:
  1. 把 Lead 的 allowed tools 设为 `Coordinator.ALLOWED_TOOLS`(调 `Agent.setAllowedTools` 已有接口)
  2. 在 systemPrompt 后追加 coordinator 提示词(F55)
  3. TUI 状态栏显示 `[COORDINATOR]` 模式标签
- **F55**: Coordinator 系统提示词追加在 systemPrompt 末尾,核心是「四阶段 + 派完不许自己干」纪律。最终文案见 [src/main/java/dev/gcode/coordinator/Coordinator.java:SYSTEM_PROMPT_SUFFIX](../../src/main/java/dev/gcode/coordinator/Coordinator.java),关键约束:
  - **派完队员就停手等汇报**:派出 Agent / SendMessage 后**禁止**立刻调 read_file / glob / grep / bash 自己探索;**禁止**用 sleep / TaskList 轮询凑时间。`TaskManager` 完成时自然推送 `<task-notification>` reminder,Lead 下一轮被唤醒后再继续
  - 唯一该做的事:发一行总结「已派 N 名队员探索 X,等结果」,让本轮结束
  - 允许自己用 read_file/glob/grep 的场景仅限:Research 第一次目标定位;Synthesis 阶段读**队员产出的报告文件**;Verification 阶段 git diff / git status 等收敛操作

  这段纪律是为了对抗「LLM 派完队员后等不及自己 glob 代码库重复劳动」的常见行为——纯 prompt 引导,不强制(LLM 偶尔仍会越线,弱模型尤甚)。

### 收敛阶段- **F56**: 收敛由 LLM 推理驱动,**不提供专门的 merge 工具**——Lead(无论是否 Coordinator Mode)在所有任务 `completed` 后,自主用 Bash 跑:
  ```bash
  git merge worktree-team-<sanitizedTeam>+<member> --no-ff -m "merge: <member>"
  ```
- **F57**: 冲突解决也由 Lead 推理——Lead 用 `read_file` 看冲突文件、`edit_file`(非 Coordinator Mode)或 `bash`(Coordinator Mode)写入解决方案、`bash` 跑 `git add` + `git commit`
- **F58**: 回滚——Lead 判断搞不定时,自主调 `bash` 跑 `git merge --abort`,然后给用户报告冲突文件 + 队员 worktree 路径;**不删队员 worktree**### TUI Slash 命令- **F59**: `/team list`——遍历 `TeamManager.teams`,每行 `<name>  <backend>  <memberCount> 成员  [<active>/<total>] 活跃`
- **F60**: `/team info <name>`——展示 Team 详情:配置路径、各成员的 name/agentId/backend/worktreePath/isActive/任务计数
- **F61**: `/team delete <name> [--force]`——调 `TeamManager.delete(name, force)`
- **F62**: `/team kill <member>`——查到 member 所属 Team,调对应 backend.kill,然后 `removeMember`

### 持久化与恢复- **F63**: `~/.gcode/teams/<sanitizedName>/config.json` 结构:
  ```json
  {
    "name": "...",
    "sanitizedName": "...",
    "leadAgentId": "lead",
    "backend": "tmux",
    "description": "",
    "createdAt": 1234567890,
    "members": [
      {
        "name": "alice",
        "agentId": "agent-a1b2c3d",
        "agentType": "worker",
        "model": "",
        "worktreePath": "/abs/path/.gcode/worktrees/team-foo+alice",
        "branch": "worktree-team-foo+alice",
        "backendType": "tmux",
        "paneId": "%5",
        "isActive": null,
        "planModeRequired": false,
        "sessionDir": "/abs/path/.gcode/sessions/<id>"
      }
    ]
  }
  ```
  所有写操作原子(先写 `.tmp` 再 `Files.move(..., ATOMIC_MOVE)`),受 `Team.lock` 保护。**跨进程**(Pane 后端)下,Lead 与子进程是不同进程的不同 Team 内存对象——`addMember` 与 `setMemberActive` 在持锁后**先 `reloadFromDiskLocked` 重读 disk members**再改写+ atomic save(F19c)
- **F64**: gcode 启动时(`new TeamManager(...)`)扫描所有 Team 目录:
  - 解析 `config.json`,失败的目录跳过并 stderr 警告
  - **不**自动恢复 in-process 队员(进程重启后 in-process 队员状态丢失,isActive 视为 false)
  - Pane 队员根据 `paneId` 探测后端是否仍在(`tmux has-session` / `it2 list-panes`),不在的 isActive 标 false
- **F65**: 队员 session 沿用 ch12 session 持久化机制,路径 `<projectRoot>/.gcode/sessions/<id>/conversation.jsonl`;Team 删除时一并删除
- **F66**: `TeamManager.delete(name, force=true)` 步骤(顺序重要):
  1. 持锁,校验 `force` 或全员 isActive=false
  2. 对每个非 lead 成员:用 `BackendFactory.create` 解析其 `backendType` 拿 `Backend` 实例,调 `backend.kill(paneId, agentId)` 杀掉 pane(tmux/iterm2)或 cancel virtual thread(in-process);Pane 子进程检测到 mailbox 目录消失会自行优雅退出兜底
  3. 调 `cleanupMemberResources` 删 session 目录与 worktree
  4. 递归删 `team.configDir` 整个 Team 目录
  5. 从 Manager 的 in-memory map 移除

## 非功能需求- **N1**: 主 Agent 平时(未 TeamCreate)看到的工具列表保持稳定——`TeamCreate` / `TeamDelete` 总是可见;`Agent` 工具的 `teamName` 参数对模型可见但仅在调用时校验
- **N2**: 协作工具(TaskCreate 等)仅在队员上下文出现,主 Agent 与普通 SubAgent 看不到——通过 `applyAgentToolFilter` 在 spawn 时收窄
- **N3**: 邮箱写入对所有后端共用一套并发安全机制(文件锁);in-process 多 virtual thread 写同一 mailbox 也由文件锁串行
- **N4**: 所有 Team 状态变更受 `Team.lock` 保护;Team 之间互不相关,各自一把锁;`TeamManager.lock` 仅保护 `teams` map
- **N5**: 后端 spawn / kill 调用不持 `Team.lock`(避免长锁);只在更新 `members` 时短暂持锁
- **N6**: 与 ch04~ch14 既有测试零破坏——`mvn test` 全绿
- **N7**: 中文友好——错误消息、TUI 输出、coordinator 提示词全部中文(对齐 gcode 其他模块风格);代码注释中文
- **N8**: Coordinator Mode 一旦启用,Lead 不可在运行时解锁(避免 LLM 被注入后自行解锁);取消的唯一方式是退出 gcode 重启
- **N9**: 权限沙箱(`dev.gcode.permission.Sandbox`)允许写入项目根**之外**的 `/tmp` 与 macOS 真实路径 `/private/tmp` 作为系统临时目录白名单。理由:工具脚本和队员经常需要 `/tmp` 做中转文件,严格限定在项目根内会导致大量正常用法被沙箱误杀。这一开放对 file-class 工具(read_file / write_file / edit_file)生效;bash 走 exec-class 权限,本来就不受沙箱约束

## 不做的事

- 跨 gcode 进程的 Team 共享(同一仓库同一时刻只支持一个 gcode 实例操作活跃 Team)
- 跨机器分布式 Team
- 队员之间实时流式通信(走 mailbox 文件 + 轮询/Wake,不走 socket)
- 复杂任务依赖约束(优先级、deadline、SLA)
- 任务自动分配(Lead 与队员都靠 LLM 推理领任务,系统不做调度)
- 队员的细粒度资源限额(token 上限、超时硬限制)
- Plan 审批的结构化 Plan 类型(本期 Plan 文本就是 SendMessage content,Lead 自行识别)
- Windows 平台特殊适配(iTerm2 后端仅 macOS;tmux 在 WSL 可用但不保证;本期以 macOS / Linux 为主)
- Coordinator Mode 的运行时解锁与重新进入
- 跨 Team 寻址(SendMessage 只能在同一 Team 内寻址)
- 插件来源的 Team 后端

## 验收标准- **AC1**: `new TeamManager(...)` 在 `~/.gcode/teams/` 不存在时自动创建;已有时正确扫描子目录还原 `teams` map
- **AC2**: `TeamManager.create("refactor auth", "")` 把 `"refactor auth"` sanitize 为 `"refactor-auth"`,在 `~/.gcode/teams/refactor-auth/config.json` 落地,`backend` 字段反映 `detectBackend` 结果
- **AC3**: 同名 Team 二次 create 自动后缀 `-2`,目录与 sanitizedName 都生效
- **AC4**: `TeamManager.delete(name, false)` 在有 `isActive != Boolean.FALSE` 成员时抛 `TeamHasActiveMembersException`,目录仍在
- **AC5**: `TeamManager.delete(name, true)` 删 Worktree、删 session 目录、删 configDir
- **AC6**: `Backend.detect()` 在 `$TMUX` 设置时返回 `TMUX`;未设但 `$TERM_PROGRAM=="iTerm.app"` 且 `it2` 可执行返回 `ITERM2`;都无但 `tmux` 二进制在 PATH 返回 `TMUX`;否则 `IN_PROCESS`
- **AC7**: `Agent` 工具带 `teamName="<existing>"` 时,在 `.gcode/worktrees/team-<sanitized>+<member>/` 落地 Worktree、调对应 `Backend.spawn` 并在 `team.members` 里出现该成员;不带 `teamName` 时维持 ch13 原行为
- **AC8**: in-process 后端队员的 `Agent` 工具调用 `teamName` 参数被拦截,抛 `InProcessTeammateNoSpawnException`
- **AC9**: 协作工具 `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage` 在主 Agent 工具列表里**不**可见;在 Team 队员的工具列表里**可见**
- **AC10**: `TaskCreate` 落 `<teamConfigDir>/tasks.json`,`TaskUpdate(taskId, addBlockedBy=[id])` 正确更新双向 `blockedBy` / `blocks` 关系
- **AC11**: `TaskList(status="pending")` 返回的任务带 `isReady` 字段,反映其 `blockedBy` 是否全部 `completed`
- **AC12**: `SendMessage(to="alice", summary="hi", message="hello")` 在 `<teamConfigDir>/mailbox/<aliceAgentId>.json` 追加一条 unread 消息
- **AC13**: `SendMessage(to="*", ...)` 广播给 Team 内除发件人外所有成员;每人邮箱各得一条
- **AC14**: 并发 10 条 virtual thread 同时向同一 mailbox `write`,最终 10 条消息全部落盘且无丢失/无截断(集成测试)
- **AC15**: mailbox lock 文件 `Files.getLastModifiedTime` 超过 10 秒时,新的 write 会清掉旧 lock 并继续(集成测试)
- **AC16**: 队员 LLM 调用前,未读消息以 `<incoming-messages>` reminder 注入 systemReminders;调用后标记 read(单测断言)
- **AC17**: 队员 `runToCompletion` 自然结束后,`Team.config.json` 里该成员 `isActive=false`,Lead mailbox 收到 `summary="<member> idle"` 消息
- **AC18**: `SendMessage(to="alice", message="new task")` 当 alice 已 stop 时,从其 sessionDir 恢复 Conv 并续派(in-process 后端,`TaskManager` 状态从 CANCELLED/COMPLETED 回到 RUNNING)
- **AC19**: `Agent(teamName="t", subagentType="planner", planModeRequired=true, ...)` spawn 后,该队员初始权限模式为 `PLAN`
- **AC20**: Lead 发 `SendMessage(to="planner", type="plan_approval_response", payload={"approve":true})` 后,planner 队员下一轮权限模式切回 `DEFAULT`
- **AC21**: `Feature.has("COORDINATOR_MODE")=true` 且 `GCODE_COORDINATOR_MODE=1` 时,Lead 的 allowed tools 收窄为 `Coordinator.ALLOWED_TOOLS`,`write_file` / `edit_file` 不在其中;TUI 状态栏显示 `[COORDINATOR]`
- **AC22**: Coordinator Mode 关闭时,Lead 工具列表与 ch13 一致(`write_file` / `edit_file` 可见)
- **AC23**: tmux 后端 spawn 后,`tmux list-panes` 看到新 pane,pane 内 gcode 实例启动并连接到该 Team
- **AC24**: tmux 后端 `wake(paneId)` 通过 `tmux send-keys` 触发目标 pane 输入(集成测试可观察 pane 内容)
- **AC25**: in-process 后端队员与主 Agent 在同一进程内运行,共享 `TaskManager`,但有独立 `withCwd(worktreePath)`
- **AC26**: `/team list` slash 命令输出含所有 Team 摘要;`/team info <name>` 输出成员详情;`/team delete <name>` 调 `TeamManager.delete`
- **AC27**: 项目编译无错误 `mvn -q -DskipTests package`、所有单元测试通过 `mvn test`、`mvn spotbugs:check` 通过
- **AC28**: tmux 实跑(端到端):
  - 步骤 1:在 tmux 会话内启动 `gcode`
  - 步骤 2:输入 prompt 让主 Agent 调 `TeamCreate(teamName="demo")`,看到状态栏出现 team 标识,`~/.gcode/teams/demo/config.json` 落地
  - 步骤 3:Agent 调 `Agent(teamName="demo", subagentType="general-purpose", name="alice", prompt="在 worktree 里 echo hello > /tmp/test_alice.txt")`
  - 步骤 4:观察 tmux 新增 pane,pane 内出现 gcode 子实例;`.gcode/worktrees/team-demo+alice/` 目录创建;`/tmp/test_alice.txt` 文件创建,内容 `hello`
  - 步骤 5:`/team info demo` 显示 alice 成员
  - 步骤 6:Lead 调 `SendMessage(to="alice", summary="ping", message="再写一行 world 到 /tmp/test_alice.txt")`,观察 alice pane 被唤醒(send-keys 触发)、`/tmp/test_alice.txt` 多一行 `world`
  - 步骤 7:`/team delete demo --force`,worktree 和 team 目录清空
- **AC29**: in-process 后端实跑(端到端,不依赖 tmux):
  - 步骤 1:`unset TMUX TERM_PROGRAM`,启动 `gcode`(自动 fallback in-process)
  - 步骤 2:主 Agent 调 `TeamCreate("inproc")`,创建后端为 `in-process`
  - 步骤 3:`Agent(teamName="inproc", name="bob", prompt="...")` 在同进程 virtual thread 启动 bob
  - 步骤 4:bob 完成后 `Team.config.json` 标记 `isActive=false`、Lead mailbox 收到 idle 消息
  - 步骤 5:Lead 调 `SendMessage(to="bob", message="再做一件事")`,bob 从 sessionDir 恢复对话上下文继续
- **AC30**: Coordinator Mode 实跑——`GCODE_COORDINATOR_MODE=1` 启动 gcode,主 Agent 的 `write_file` 工具调用被拒绝(`isError=true`);`bash git merge` 调用允许
````

````markdown
# Agent Team Plan## 技术栈

- 语言:Java 21(LTS;virtual thread、record、sealed interface、pattern matching)
- 构建:Maven(`pom.xml`,目标 JDK 21)
- TUI:Lanterna(`com.googlecode.lanterna:lanterna`)沿用 ch02 风格
- LLM SDK:`com.anthropic:anthropic-java` + `com.openai:openai-java`(沿用 ch02 / ch13)
- 配置解析:SnakeYAML Engine(`org.snakeyaml:snakeyaml-engine`)
- JSON:Jackson Databind(`com.fasterxml.jackson.core:jackson-databind`)做 `config.json` / `tasks.json` / mailbox 的序列化反序列化
- 进程间唤醒:`Runtime.exec(["tmux", ...])` / `Runtime.exec(["it2", ...])` 调 CLI;Pane 子进程内置 stdin scanner virtual thread
- CLI 解析:`info.picocli:picocli`(用于 `--team-member` 子进程命令行)
- 并发:Java 21 virtual thread + `ReentrantLock` + `LinkedBlockingQueue`;mailbox / tasks 文件锁用 `Files.newOutputStream(..., StandardOpenOption.CREATE_NEW)` 实现 `O_EXCL` 语义

## 架构概览

本章引入 `dev.gcode.team` 顶层包,把 ch13 SubAgent 的「子 Agent」扩展为「Team 队员」。整体分四层:

1. **数据模型层**(`team/Team.java` + `team/TeamManager.java` + `team/persistence/`)——Team、TeammateInfo 数据结构与持久化
2. **后端层**(`team/backend/`)——`Backend` 接口与三种实现 tmux / iterm2 / inprocess,屏蔽 spawn 差异
3. **协作层**(`team/mailbox/`、`team/registry/`、`team/tasks/`)——邮箱(含文件锁)、AgentNameRegistry、共享任务列表
4. **工具与集成层**(`team/tools/` + `agent` 包扩展 + `coordinator` 包)——5 个协作工具 + `Agent` 工具的 `teamName` 分支 + Coordinator Mode

Lead 仍是 `TuiApp.mainAgent()`——本期 Lead 没有独立类型,通过 `Coordinator.isEnabled(cfg)` 在启动时收窄其工具集即可。

依赖方向(单向):
```
tui  ──→  agent  ──→  team  ──→  team/{backend,mailbox,registry,tasks,tools}
                       └──→  worktree(ch14)、task(ch13)、session(ch12)、subagent(ch13)
```
`team` 不反向依赖 `agent` 包(避免环);`agent` 通过新增的 `TeamHook` 接口注入 team 行为。

## 核心数据结构### `dev.gcode.team.Team`

```java
package dev.gcode.team;

public final class Team {
    private final ReentrantLock lock = new ReentrantLock();

    private final String name;          // 用户给的原始名
    private final String sanitizedName; // 经 sanitize 后用于路径,Team 主键
    private final String leadAgentId;   // 固定 "lead"(本期 Lead = 主 Agent)
    private BackendType backend;        // 全 team 默认后端;可被 member 覆盖
    private String description;
    private final Instant createdAt;
    private final List<TeammateInfo> members = new ArrayList<>();

    // 派生路径(不持久化)
    private final Path configDir;
    private final Path configPath;   // <configDir>/config.json
    private final Path tasksPath;    // <configDir>/tasks.json
    private final Path mailboxDir;   // <configDir>/mailbox/

    public boolean addMember(TeammateInfo info);
    public boolean setMemberActive(String name, boolean active);
    public boolean removeMember(String name);
    public Optional<TeammateInfo> memberByName(String name);
    public Optional<TeammateInfo> memberByAgentId(String id);
    // ... getters
}
```

### `dev.gcode.team.TeammateInfo`

```java
package dev.gcode.team;

public record TeammateInfo(
    @JsonProperty("name")             String name,
    @JsonProperty("agentId")          String agentId,
    @JsonProperty("agentType")        String agentType,   // "" 表 Fork
    @JsonProperty("model")            String model,       // "" 表 inherit
    @JsonProperty("worktreePath")     String worktreePath,// 绝对路径
    @JsonProperty("branch")           String branch,
    @JsonProperty("backendType")      BackendType backendType,
    @JsonProperty("paneId")           String paneId,      // tmux pane id / iterm2 split id / "" for in-process
    @JsonProperty("isActive")         Boolean isActive,   // null/true 活跃,false 空闲;不存在视为终止
    @JsonProperty("planModeRequired") boolean planModeRequired,
    @JsonProperty("sessionDir")       String sessionDir   // 绝对路径
) {}
```

### `dev.gcode.team.TeamManager`

```java
package dev.gcode.team;

public final class TeamManager {
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, Team> teams = new HashMap<>();  // 按 sanitizedName 索引
    private final Path homeDir;
    private final WorktreeManager worktreeManager;
    private final TaskManager taskManager;
    private final AgentNameRegistry registry;

    public TeamManager(Path homeDir, WorktreeManager wt, TaskManager taskMgr, AgentNameRegistry reg) throws IOException;
    public Team create(String name, String description) throws IOException;
    public Optional<Team> get(String name);
    public List<Team> list();
    public void delete(String name, boolean force) throws IOException;
}
```

### `dev.gcode.team.BackendType`

```java
public enum BackendType {
    TMUX("tmux"), ITERM2("iterm2"), IN_PROCESS("in-process");
    private final String wire;
    BackendType(String w) { this.wire = w; }
    public String wireValue() { return wire; }
    @JsonCreator public static BackendType fromWire(String s) { ... }
}
```

### `dev.gcode.team.backend.Backend`

```java
package dev.gcode.team.backend;

public interface Backend {
    BackendType type();
    SpawnResult spawn(SpawnRequest req) throws IOException;
    void wake(String paneId, String agentId) throws IOException;
    void kill(String paneId, String agentId) throws IOException;
}

public record SpawnResult(String paneId, String agentId) {}

public record SpawnRequest(
    String teamName,
    String memberName,
    String agentId,
    String worktreePath,
    String sessionDir,
    String agentType,
    String model,
    String initialPrompt,
    boolean planModeRequired,
    // in-process 专用——同进程后端直接复用这三个对象;用 Object 避免 backend 反向依赖 agent 包
    Object subAgent,
    Object conv,
    Object taskManager
) {}
```

### `dev.gcode.team.mailbox.Message` / `Mailbox`

```java
package dev.gcode.team.mailbox;

public enum MessageType {
    TEXT("text"),
    SHUTDOWN_REQUEST("shutdown_request"),
    SHUTDOWN_RESPONSE("shutdown_response"),
    PLAN_APPROVAL_RESPONSE("plan_approval_response");
    // wireValue + @JsonCreator 同 BackendType
}

public record Message(
    @JsonProperty("from")      String from,
    @JsonProperty("to")        String to,
    @JsonProperty("type")      MessageType type,
    @JsonProperty("summary")   String summary,
    @JsonProperty("content")   String content,
    @JsonProperty("payload")   Map<String, Object> payload,
    @JsonProperty("timestamp") long timestamp,
    @JsonProperty("read")      boolean read
) {}

public final class Mailbox {
    private final Path dir;  // <teamConfigDir>/mailbox/

    public Mailbox(Path dir) throws IOException { ... }
    public void write(String agentId, Message msg) throws IOException;
    public List<Message> read(String agentId) throws IOException;
    public ReadUnreadResult readUnread(String agentId) throws IOException; // record { List<Integer> indices, List<Message> msgs }
    public void markRead(String agentId, List<Integer> indices) throws IOException;
}
```

文件锁机制由 `dev.gcode.team.filelock.FileLock` 提供,所有公开方法都走锁。

### `dev.gcode.team.registry.AgentNameRegistry`

```java
package dev.gcode.team.registry;

public final class AgentNameRegistry {
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, String> byName = new HashMap<>();  // name → agentId
    private final Map<String, String> byId   = new HashMap<>();  // agentId → name

    public void register(String name, String agentId);
    public void unregister(String name);
    public void unregisterByAgentId(String agentId);
    public Optional<String> resolve(String nameOrId);
    public Optional<String> nameOf(String agentId);
    public Map<String, String> snapshot();
}
```

注意:本章把 `TaskManager.byName` 替换/委托给这套 registry——`TaskManager` 改为持一个 `AgentNameRegistry` 引用。

### `dev.gcode.team.tasks.Store`

```java
package dev.gcode.team.tasks;

public enum Status {
    PENDING("pending"), IN_PROGRESS("in_progress"),
    COMPLETED("completed"), BLOCKED("blocked");
    // wireValue + @JsonCreator 同上
}

public record Task(
    @JsonProperty("id")          String id,
    @JsonProperty("title")       String title,
    @JsonProperty("description") String description,
    @JsonProperty("status")      Status status,
    @JsonProperty("assignee")    String assignee,
    @JsonProperty("blockedBy")   List<String> blockedBy,
    @JsonProperty("blocks")      List<String> blocks,
    @JsonProperty("createdAt")   long createdAt,
    @JsonProperty("updatedAt")   long updatedAt
) {}

public record Filter(Optional<Status> status) {}
public record Patch(
    Optional<String> title,
    Optional<String> description,
    Optional<Status> status,
    Optional<String> assignee,
    List<String> addBlocks,
    List<String> addBlockedBy,
    List<String> removeBlocks,
    List<String> removeBlockedBy
) {}

public final class Store {
    private final Path path;
    private final ReentrantLock lock = new ReentrantLock();

    public Store(Path path);
    public String create(Task t) throws IOException;
    public Optional<Task> get(String id) throws IOException;
    public List<Task> list(Filter f) throws IOException;
    public void update(String id, Patch p) throws IOException;
}
```

### `dev.gcode.coordinator` 包

```java
package dev.gcode.coordinator;

public final class Coordinator {
    public static boolean isEnabled(AppConfig cfg);
    public static List<String> allowedTools();
    public static String systemPromptSuffix();
}
```

仅 3 个纯静态方法,无状态。

## 模块设计### `dev.gcode.team`(顶层)**职责:** Team / TeammateInfo / TeamManager 数据结构与持久化,跨子包的协调入口。
**对外接口:** `new TeamManager(...)`、`TeamManager.create/get/list/delete`、`Team.addMember/setMemberActive/removeMember`
**依赖:** `worktree`、`task`、`session`、`team.backend`、`team.mailbox`、`team.registry`、`team.tasks`

### `dev.gcode.team.backend`**职责:** 屏蔽 tmux / iterm2 / in-process spawn 差异。
**对外接口:** `Backend` 接口、`Backend.detect()`、`BackendFactory.create(BackendType, Deps)`
**依赖:** `team`(取常量)、`agent` 与 `task`(in-process 实现用)

注意:`backend` 包反向依赖 `agent` 会成环。解决:`in-process` 实现走「接口适配」——`backend.spawn` 接收 `SpawnRequest` 中的 `subAgent Object`(声明为 `Object`),由调用方(`team` 包)预先构造好;`backend` 包只做调度,不知道 `Agent` 类型。或者把 `in-process` 实现单独提到 `team.backend.inprocess` 子包,允许它依赖 `agent`,而 `team.backend.tmux` / `iterm2` 不依赖。

**采用方案:** 三种后端各一个子包(`tmux/` / `iterm2/` / `inprocess/`),每个独立实现 `Backend` 接口,工厂方法 `create(...)` 接收所需依赖。`inprocess` 子包依赖 `agent` 包没问题(`agent` 在更低层)。

### `dev.gcode.team.mailbox`**职责:** 邮箱文件 + 文件锁的读写。
**对外接口:** `Mailbox.write/read/readUnread/markRead`、`Message` 类型
**依赖:** 仅 JDK + Jackson(`java.nio.file`、`com.fasterxml.jackson.databind`)

### `dev.gcode.team.registry`**职责:** Agent name ↔ agentId 双向映射。
**对外接口:** `register/unregister/resolve/nameOf`
**依赖:** 仅 JDK

### `dev.gcode.team.tasks`**职责:** 共享任务列表的 CRUD + 依赖图维护。
**对外接口:** `Store.create/get/list/update`、`Task`、`Filter`、`Patch` 类型
**依赖:** 仅 JDK + Jackson + `team.filelock`

### `dev.gcode.team.tools`**职责:** 5 个协作工具实现(TaskCreate、TaskGet、TaskList、TaskUpdate、SendMessage)+ 2 个 Team 管理工具(TeamCreate、TeamDelete)。
**对外接口:** 每个工具一个构造函数 `new XxxTool(teamManager)` 实现 `Tool` 接口
**依赖:** `tool`、`team`、`team.{mailbox,registry,tasks}`

### `dev.gcode.coordinator`**职责:** Coordinator Mode 的开关检测、工具白名单、系统提示词。
**对外接口:** `isEnabled(cfg)`、`allowedTools()`、`systemPromptSuffix()`
**依赖:** `config`(读 feature flag)

### `agent` 包扩展

- 新增 `agent.TeamHook` 接口:
  ```java
  public interface TeamHook {
      // spawnTeammate 让 Agent 工具委托给 TeamManager 处理 teamName 分支。
      // 返回 finalText(立即返回 taskId JSON 描述)。
      String spawnTeammate(TeamSpawnRequest req) throws IOException;
      // teammateContextOf 判断当前调用 ctx 是否在某队员的执行上下文中(用于拦截嵌套 spawn)。
      Optional<TeammateContextInfo> teammateContextOf(InvocationContext ctx);

      record TeammateContextInfo(String memberName, String teamName, BackendType backendType) {}
  }
  ```
- `AgentTool` 持一个 `TeamHook teamHook` 字段(可选,null 时降级为 ch13 行为)
- `Agent.execute` 在 `teamName != null && !teamName.isBlank()` 时调 `teamHook.spawnTeammate`

### `task` 包扩展

- `TaskManager` 持一个 `AgentNameRegistry` 引用(原 `byName` 字段废弃,改委托)
- `TaskManager.sendMessage` 复用——Team 模块续派直接调它

### `tui` 包扩展

- `TuiApp` 新增字段 `TeamManager teamManager`
- 注入 `/team` 系列 slash 命令(`dev.gcode.command.builtin.BuiltinTeam`)
- 状态栏新增 `[COORDINATOR]` 标签(若 `Coordinator.isEnabled(cfg)`)

## 模块交互### TeamCreate 调用路径

```
LLM 调 TeamCreate(teamName="demo")
  ↓
TeamCreateTool.execute
  ↓
TeamManager.create("demo", "")
  ↓
1. sanitize("demo") → "demo"
2. Backend.detect() → TMUX
3. Files.createDirectories(~/.gcode/teams/demo/)
4. Files.createDirectories(~/.gcode/teams/demo/mailbox/)
5. 写 config.json(原子;.tmp + ATOMIC_MOVE)
6. team.members = [new TeammateInfo("lead","lead", ..., null)]
7. teams.put("demo", team)
  ↓
返回 {"teamName":"demo","backend":"tmux","configPath":"..."}
```

### Agent(teamName=...) spawn 路径

```
LLM 调 Agent(teamName="demo", subagentType="general-purpose", name="alice", prompt="...")
  ↓
agent.AgentTool.execute
  ↓
判断 teamName != null → 委托给 teamHook.spawnTeammate
  ↓
TeamManager.spawnTeammate(req)
  ↓
1. TeamManager.get("demo") 取 Team
2. 校验调用者权限(in-process 队员不许 spawn,Pane 队员可以但 teamName 屏蔽)
3. Catalog.resolve(agentType) 取 SubAgentDefinition
4. memberName = req.name()(或自动 alice/agent-a1b2c3)
5. worktreeManager.create("team-demo/"+memberName, "HEAD", false) → worktree
6. 申请 sessionDir(util 方法,沿用 ch12 格式)
7. 构造 SpawnRequest
8. 若 backend=IN_PROCESS:
   - 构造 subAgent(SessionRuntime + withCwd + withAllowedTools 含协作工具)
   - 构造 subConv(NewFromMessages 走 Fork 路径,或空 Conv 走定义式)
   - 注入 <team-context> reminder
   - 注入 systemPrompt 附录(F39)
   - SpawnRequest 的 subAgent / conv / taskManager 填好
9. backend.spawn(req) → SpawnResult(paneId, agentId)
10. registry.register(memberName, agentId)
11. team.addMember(new TeammateInfo(...))
  ↓
返回 {"memberName":"alice","agentId":"...","worktree":"...","backend":"tmux"}
```

### SendMessage 调用路径

```
LLM 调 SendMessage(to="alice", summary="hi", message="hello")
  ↓
SendMessageTool.execute
  ↓
1. 取调用者所属 Team(从 invocation ctx 中的 TeammateContext 取,或主 Agent 走 active team)
2. resolve to:
   - "*" → 广播
   - 否则 registry.resolve(to) → agentId
3. 校验消息类型权限(plan_approval_response 仅 Lead,shutdown_response 仅发给 Lead)
4. 对每个目标 agentId:
   - mailbox.write(agentId, msg)
   - 取 TeammateInfo.paneId 与 backendType
   - 若 Pane 后端:backend.wake(paneId, agentId)
   - 若目标已 stop(in-process,taskManager.get(agentId).status() != RUNNING):
     - 从 sessionDir 恢复 Conv
     - taskManager.sendMessage(parentCtx, name, message) 续派
5. 返回 {"deliveredTo":["agent-xxx"],"timestamp":...}
```

### 队员 Loop 内邮箱注入

```
队员的 Agent.run 每轮迭代开头(在调 LLM 前):
  ↓
读 invocation ctx 中的 TeammateContext(包含 Mailbox 闭包、agentId)
  ↓
ReadUnreadResult ur = mailbox.readUnread(agentId)
  ↓
若 !ur.indices().isEmpty():
  reminder = buildIncomingMessagesReminder(ur.msgs())
  把 reminder 加入本轮 systemReminders
  mailbox.markRead(agentId, ur.indices())
```

`Agent` 已有 systemReminders 注入机制(ch05 / ch07 plan reminder 走同一通道);新增一种 reminder 来源即可。

### 队员 runToCompletion 结束的通知

```
TaskManager.runTask virtual thread 结束(完成 / 失败 / 取消)
  ↓
若该 task 关联到 Team 队员(通过 registry.nameOf(agentId) 反查 name → 查 team)
  ↓
team.setMemberActive(memberName, false)
mailbox.write(leadAgentId, new Message("...idle", ...))
backend.wake(leadPaneId, leadAgentId)  // 若 Lead 是 Pane 后端
```

需要在 `TaskManager.runTask` 的 finally 中加 hook,或者在 `team` 包注册一个回调到 task 包(走依赖反转)。**采用方案:** 在 `TaskManager` 新增 `onTaskDone(Consumer<String> cb)` 回调注册接口,`team` 包初始化时注册。

### Coordinator Mode 启用路径

```
Main.java 启动时,在构造主 Agent 后:
  ↓
if (Coordinator.isEnabled(cfg)) {
    mainAgent.setAllowedTools(Coordinator.allowedTools());
    mainAgent.appendSystemPrompt(Coordinator.systemPromptSuffix());
    tuiParams.coordinatorMode(true);
}
```

TUI 渲染 statusbar 时检测 `coordinatorMode` 添加 `[COORDINATOR]` 标签。

## 文件组织

```
src/main/java/dev/gcode/
├── team/
│   ├── package-info.java                 — 包文档
│   ├── Team.java                         — Team 类
│   ├── TeammateInfo.java                 — record
│   ├── TeamManager.java                  — create/get/delete/...
│   ├── BackendType.java                  — 枚举
│   ├── Persistence.java                  — sanitize + atomicWriteJson + readJson
│   ├── SpawnTeammate.java                — TeamManager.spawnTeammate 主流程拆分
│   ├── Feature.java                      — FORK_TEAMMATE flag 读取
│   ├── exceptions/
│   │   ├── TeamNotFoundException.java
│   │   ├── TeamHasActiveMembersException.java
│   │   ├── MemberExistsException.java
│   │   ├── MemberNotFoundException.java
│   │   └── InProcessTeammateNoSpawnException.java
│   ├── filelock/
│   │   └── FileLock.java                 — 共用文件锁(O_EXCL + 抖动 + stale)
│   ├── backend/
│   │   ├── Backend.java                  — 接口 + SpawnRequest / SpawnResult
│   │   ├── BackendFactory.java
│   │   ├── BackendDetector.java          — Backend.detect()
│   │   ├── tmux/TmuxBackend.java
│   │   ├── iterm2/Iterm2Backend.java
│   │   └── inprocess/InProcessBackend.java
│   ├── mailbox/
│   │   ├── MessageType.java
│   │   ├── Message.java                  — record
│   │   ├── Mailbox.java                  — write/read/readUnread/markRead
│   │   └── ReadUnreadResult.java         — record
│   ├── registry/
│   │   └── AgentNameRegistry.java
│   ├── tasks/
│   │   ├── Status.java
│   │   ├── Task.java                     — record
│   │   ├── Filter.java                   — record
│   │   ├── Patch.java                    — record
│   │   └── Store.java
│   └── tools/
│       ├── TeamCreateTool.java
│       ├── TeamDeleteTool.java
│       ├── TaskCreateTool.java
│       ├── TaskGetTool.java
│       ├── TaskListTool.java
│       ├── TaskUpdateTool.java
│       ├── SendMessageTool.java
│       └── TeammateToolFilter.java       — 队员专属工具白名单(注入到 applyAgentToolFilter)
│
├── coordinator/
│   └── Coordinator.java                  — isEnabled/allowedTools/systemPromptSuffix
│
├── agent/
│   ├── AgentTool.java                    — 修改:增加 teamName 参数与 TeamHook 委托
│   ├── TeamHook.java                     — 新建:接口 + TeammateContext
│   ├── TeammateContext.java              — 新建:闭包式 Mailbox + agentId 等
│   ├── TeamMailboxIngestor.java          — 新建:Loop 头部读 mailbox 注入 reminder
│   └── ... (其他 ch13 文件)
│
├── task/
│   └── TaskManager.java                  — 修改:onTaskDone 回调;改用 AgentNameRegistry
│
├── command/builtin/
│   └── BuiltinTeam.java                  — 新建:/team list/info/delete/kill 4 个命令
│
├── tui/
│   ├── TuiApp.java                       — 修改:接收 teamManager;启动时检测 Coordinator
│   ├── Statusbar.java                    — 修改:渲染 [COORDINATOR] 标签
│   ├── LeadMailWatcher.java              — 新建:每秒轮询 lead mailbox
│   └── LeadMailWaiter.java               — 新建:阻塞等 leadMailQueue 信号
│
├── config/
│   └── AppConfig.java                    — 修改:新增 FeaturesConfig(coordinatorMode + forkTeammate)
│
├── cli/
│   └── TeamMemberRunner.java             — 新建:--team-member 子进程自治循环入口
│
└── Main.java                             — 修改:wire TeamManager,注册 7 个新工具,接入 Coordinator,
                                            --team-member 分支
```

测试目录镜像 `src/test/java/dev/gcode/team/...`,所有公开类都有 JUnit 5 测试。

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Team 包归属 | `dev.gcode.team` 顶层 | 与 ch13 `subagent`、ch14 `worktree` 平级,职责清晰 |
| 后端三选一时机 | `Backend.detect()` 在 `TeamCreate` 时一次性决定 | 与 README 一致:不做运行时回退,行为可预测 |
| 后端实现拆分 | 各一个子包 `tmux/iterm2/inprocess` | `inprocess` 需要依赖 `agent` 包,拆开避免污染其他 backend |
| Backend 接口 | 三方法 `spawn/wake/kill` | 最小集;不引入 pause/resume(本期不做) |
| Lead 表示 | 不引入独立类型,Lead = `TuiApp.mainAgent()` | 收窄改动;Coordinator Mode 在工具集层面区分 |
| 邮箱实现 | `<teamConfigDir>/mailbox/<agentId>.json` + 同名 `.lock` | 跨进程通信现成方案;in-process 与 Pane 共用一套 |
| 锁文件参数 | `StandardOpenOption.CREATE_NEW`,5-100ms 抖动 10 次,>10s 视 stale | README 明定;避免雪崩 |
| 任务存储 | `<teamConfigDir>/tasks.json` 单文件 | Team 内任务量小(几十条),无需 DB;原子写 + 文件锁 |
| AgentNameRegistry 归属 | 独立 `team.registry` 包,`TaskManager` 委托 | 解耦;消除 ch13 `TaskManager.byName` 的局部状态 |
| `TaskManager` 改造 | 加 `onTaskDone` 回调,Team 注册 | 依赖反转,避免 task 包反向依赖 team |
| Team 持久化原子性 | `<file>.tmp` + `Files.move(...,ATOMIC_MOVE)` | 与 ch14 worktree session、ch12 session 一致 |
| Worktree 命名 | `team-<sanitizedTeam>/<member>`(嵌套 slug,`/` → `+`) | 复用 ch14 嵌套 slug 能力;不污染顶层 worktree 命名空间 |
| Member sessionDir | 沿用 ch12 `<root>/.gcode/sessions/<id>/` 格式 | 复用 `session.Writer`,无需新机制;Team 删除时一并清理 |
| Coordinator 开启检测 | `Feature.has("COORDINATOR_MODE", cfg) && envTruthy(env)` | README 明定双锁;一次决定不允许运行时改 |
| Coordinator 工具白名单 | 硬编码常量,启动时直接 `setAllowedTools` | LLM 无法解锁,安全边界清晰 |
| Plan 审批本期形态 | 文本 Plan + Lead 用 `plan_approval_response` 回复 | 不强制结构化 Plan 类型,降低实现成本 |
| Fork 队员 | 受 `FORK_TEAMMATE` flag 控制,默认关 | README 明定;避免默认带满上下文 |
| 收敛 merge | 不提供专用工具,Lead 用 Bash 自主跑 git | README 明定;LLM 解冲突 = 语义理解,这是 LLM 优势 |
| `Agent` 工具的 `teamName` 在 in-process 队员处可见性 | 参数对模型可见,但调用时拦截抛 exception | 与其在 schema 层动态裁剪不如统一 schema + 运行时校验,缓存友好 |
| 队员 Loop 邮箱注入 | 复用 `Agent` 既有 systemReminders 通道,新增一种 reminder 来源 | 不改 Loop 主流程,改动最小 |
| TUI Coordinator 标签 | 状态栏静态渲染 | 视觉提示,运行时不可改 |
| 多 Team 并存 | `TeamManager.teams` map 支持,但 spawn 时按 `teamName` 显式选 | 灵活;典型场景同一时刻一个活跃 Team |
| Team 删除时 Worktree 处理 | 调 `worktreeManager.remove(name, new RemoveOptions(true))`,失败只警告 | 与 ch14 退出语义一致;`force=true` 才放行,无 force 时有活跃成员就拒删,有变更也保留(自动 cleanup 已处理) |
| 错误命名 | 自定义异常类 `TeamHasActiveMembersException` / `InProcessTeammateNoSpawnException` 等 | 调用方可 `catch` 判别;Java 用受检异常或 RuntimeException 子类按场景选 |
| Pane 子进程 CLI 解析 | picocli(`info.picocli:picocli`) | 注解式声明 flag,生成 usage 友好;比 commons-cli 更现代 |
| JSON 库 | Jackson Databind | 与 ch04 ConfigLoader 之外的 JSON 全部统一;`@JsonCreator` / `@JsonProperty` 直接读写 record |
| virtual thread vs platform thread | 邮箱 watcher、stdin scanner、in-process spawn 全部 `Thread.startVirtualThread` | I/O 密集,virtual thread 调度成本极低;不阻塞 carrier thread |
````

````markdown
# Agent Team Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/main/java/dev/gcode/team/package-info.java` | 包文档 |
| 新建 | `src/main/java/dev/gcode/team/BackendType.java` | 枚举 + wireValue |
| 新建 | `src/main/java/dev/gcode/team/TeammateInfo.java` | record |
| 新建 | `src/main/java/dev/gcode/team/Team.java` | Team 类(含 addMember/setMemberActive/removeMember) |
| 新建 | `src/main/java/dev/gcode/team/Persistence.java` | sanitize、原子写、readJson、reloadFromDiskLocked |
| 新建 | `src/main/java/dev/gcode/team/TeamManager.java` | create/get/list/delete |
| 新建 | `src/main/java/dev/gcode/team/exceptions/*.java` | 5 个异常类 |
| 新建 | `src/test/java/dev/gcode/team/TeamManagerTest.java` | Manager 单测 |
| 新建 | `src/main/java/dev/gcode/team/SpawnTeammate.java` | SpawnTeammate 主流程 |
| 新建 | `src/test/java/dev/gcode/team/SpawnTeammateTest.java` | spawn 单测(in-process 路径) |
| 新建 | `src/main/java/dev/gcode/team/Feature.java` | FORK_TEAMMATE flag 读取 |
| 新建 | `src/main/java/dev/gcode/team/mailbox/Message.java` | record + MessageType 枚举 |
| 新建 | `src/main/java/dev/gcode/team/mailbox/Mailbox.java` | write/read/readUnread/markRead |
| 新建 | `src/main/java/dev/gcode/team/mailbox/ReadUnreadResult.java` | record |
| 新建 | `src/main/java/dev/gcode/team/mailbox/MailboxLock.java` | mailbox 内部文件锁(T5 落地;T9 抽到 filelock 后委托或删除) |
| 新建 | `src/test/java/dev/gcode/team/mailbox/MailboxTest.java` | 并发与 stale 锁测试 |
| 新建 | `src/main/java/dev/gcode/team/filelock/FileLock.java` | 共用文件锁(T9 从 mailbox 抽出;O_EXCL + 抖动 + stale) |
| 新建 | `src/test/java/dev/gcode/team/filelock/FileLockTest.java` | 锁单测 |
| 新建 | `src/main/java/dev/gcode/team/registry/AgentNameRegistry.java` | 命名注册表 |
| 新建 | `src/test/java/dev/gcode/team/registry/AgentNameRegistryTest.java` | 注册/解析/反查测试 |
| 新建 | `src/main/java/dev/gcode/team/tasks/Status.java` | 枚举 |
| 新建 | `src/main/java/dev/gcode/team/tasks/Task.java` | record |
| 新建 | `src/main/java/dev/gcode/team/tasks/Filter.java` | record |
| 新建 | `src/main/java/dev/gcode/team/tasks/Patch.java` | record |
| 新建 | `src/main/java/dev/gcode/team/tasks/Store.java` | CRUD + 依赖图 |
| 新建 | `src/test/java/dev/gcode/team/tasks/StoreTest.java` | CRUD + 依赖关系测试 |
| 新建 | `src/main/java/dev/gcode/team/backend/Backend.java` | 接口 + SpawnRequest / SpawnResult |
| 新建 | `src/main/java/dev/gcode/team/backend/BackendFactory.java` | 按类型分发 |
| 新建 | `src/main/java/dev/gcode/team/backend/BackendDetector.java` | Backend.detect() |
| 新建 | `src/test/java/dev/gcode/team/backend/BackendDetectorTest.java` | 检测逻辑测试 |
| 新建 | `src/main/java/dev/gcode/team/backend/tmux/TmuxBackend.java` | Tmux Backend |
| 新建 | `src/test/java/dev/gcode/team/backend/tmux/TmuxBackendTest.java` | tmux 命令构造测试 |
| 新建 | `src/main/java/dev/gcode/team/backend/iterm2/Iterm2Backend.java` | iTerm2 Backend |
| 新建 | `src/test/java/dev/gcode/team/backend/iterm2/Iterm2BackendTest.java` | iterm2 命令构造测试 |
| 新建 | `src/main/java/dev/gcode/team/backend/inprocess/InProcessBackend.java` | InProcess Backend |
| 新建 | `src/test/java/dev/gcode/team/backend/inprocess/InProcessBackendTest.java` | in-process spawn 集成测试 |
| 新建 | `src/main/java/dev/gcode/team/tools/TeamCreateTool.java` | TeamCreate 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TeamDeleteTool.java` | TeamDelete 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TaskCreateTool.java` | TaskCreate 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TaskGetTool.java` | TaskGet 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TaskListTool.java` | TaskList 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TaskUpdateTool.java` | TaskUpdate 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/SendMessageTool.java` | SendMessage 工具 |
| 新建 | `src/main/java/dev/gcode/team/tools/TeammateToolFilter.java` | 队员专属工具白名单 |
| 新建 | `src/test/java/dev/gcode/team/tools/ToolsTest.java` | 工具单测 |
| 新建 | `src/main/java/dev/gcode/coordinator/Coordinator.java` | isEnabled/allowedTools/systemPromptSuffix |
| 新建 | `src/test/java/dev/gcode/coordinator/CoordinatorTest.java` | 双锁测试 |
| 新建 | `src/main/java/dev/gcode/agent/TeamHook.java` | 接口 + TeammateContext 嵌套 record |
| 新建 | `src/main/java/dev/gcode/agent/TeammateContext.java` | 闭包式 Mailbox + agentId |
| 修改 | `src/main/java/dev/gcode/agent/AgentTool.java` | 增加 teamName 参数 + TeamHook 委托 + withTeamHook 构造器 |
| 新建 | `src/main/java/dev/gcode/agent/TeamMailboxIngestor.java` | Loop 头部注入 incoming-messages reminder |
| 修改 | `src/main/java/dev/gcode/task/TaskManager.java` | 加 onTaskDone 回调;改用 AgentNameRegistry |
| 修改 | `src/main/java/dev/gcode/tool/Filter.java` | 新增 TEAMMATE_ALLOWED_TOOLS,扩展 FilterParams 加 teammate boolean |
| 新建 | `src/main/java/dev/gcode/command/builtin/BuiltinTeam.java` | /team list/info/delete/kill 4 个命令 |
| 修改 | `src/main/java/dev/gcode/tui/TuiApp.java` 与相关文件 | 接收 teamManager、coordinator 标签 |
| 修改 | `src/main/java/dev/gcode/config/AppConfig.java` | FeaturesConfig 字段新增 coordinatorMode 与 forkTeammate |
| 修改 | `src/main/java/dev/gcode/Main.java` | wire TeamManager / Coordinator,注册 7 个工具 |
| 新建 | `src/main/java/dev/gcode/cli/TeamMemberRunner.java` | --team-member 子进程自治循环 |
| 修改 | `.gcode/config.yaml` 示例 | 加示例 features 段(可选,不强制) |
| 修改 | `pom.xml` | 加 `info.picocli:picocli` 依赖(Pane 子进程 CLI 解析) |

## T1: 基础类型 — `dev/gcode/team/BackendType.java` + `TeammateInfo.java`**文件:** `src/main/java/dev/gcode/team/BackendType.java`、`TeammateInfo.java`、`exceptions/*.java`
**依赖:** 无
**步骤:**
1. 定义 `BackendType` 枚举:`TMUX("tmux")`、`ITERM2("iterm2")`、`IN_PROCESS("in-process")`;带 `wireValue()` + `@JsonCreator` + `@JsonValue`
2. 定义 `TeammateInfo` record(F2),所有字段带 `@JsonProperty`
3. 定义 5 个异常:`TeamNotFoundException` / `TeamHasActiveMembersException` / `MemberExistsException` / `MemberNotFoundException` / `InProcessTeammateNoSpawnException`(全部继承 `RuntimeException` 或自定义 `TeamException` 基类)

**验证:** `mvn -q -DskipTests compile` 编译通过

## T2: sanitize 与原子写 — `dev/gcode/team/Persistence.java`**文件:** `src/main/java/dev/gcode/team/Persistence.java`
**依赖:** T1
**步骤:**
1. 实现 `static String sanitize(String name)`——只保留 `[a-zA-Z0-9._-]`,其他字符替换为 `-`,首尾去 `-`,空字符串返回 `""`(用 `Pattern.compile("[^a-zA-Z0-9._-]+").matcher(name).replaceAll("-")`)
2. 实现 `static void atomicWriteJson(Path path, Object v)`——`ObjectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(v)` → 写 `<path>.tmp` → `Files.move(tmp, path, ATOMIC_MOVE, REPLACE_EXISTING)`
3. 实现 `static <T> Optional<T> readJson(Path path, Class<T> type)`——`Files.readAllBytes` + `mapper.readValue`,文件不存在返回 `Optional.empty()`

**验证:** 单测断言 `Persistence.sanitize("foo bar/baz").equals("foo-bar-baz")`

## T3: TeamManager 与持久化 — `dev/gcode/team/TeamManager.java`**文件:** `src/main/java/dev/gcode/team/TeamManager.java`
**依赖:** T1, T2
**步骤:**
1. 定义 `TeamManager` 类(F3)
2. 实现构造器 `new TeamManager(Path homeDir, Path projectRoot, WorktreeManager wt, TaskManager taskMgr, AgentNameRegistry reg)`(F4)
   - 创建 `<homeDir>/.gcode/teams/` 目录(`Files.createDirectories`)
   - `Files.list` 扫描子目录,逐个 `Persistence.readJson(configPath, TeamSnapshot.class)`(失败 `System.err` 警告并跳过)
   - 反序列化后填充派生路径字段
3. 实现 `Optional<Team> get(String name)`
4. 实现 `List<Team> list()`(按 `createdAt` 排序)
5. 实现 `Team create(String name, String description)`(F5)
   - sanitize + 同名冲突 `-2`/`-3` 后缀
   - 取 `BackendDetector.detect()`(暂时硬编码 `IN_PROCESS`,后面 T12 接 detect)
   - 创建 configDir、mailboxDir
   - 注册 Lead 成员
   - `Persistence.atomicWriteJson`
6. 实现 `void delete(String name, boolean force)`(F7 + F66):
   - 持锁、找到 Team、(force=false 时)校验全员 isActive=false
   - 对每个非 lead 成员:用 `BackendFactory.create(mem.backendType(), deps)` 解析后端,调 `backend.kill(mem.paneId(), mem.agentId())`
   - 调 `cleanupMemberResources` 删 session 目录与 worktree(best-effort)
   - 递归删 `team.configDir()` 整个 Team 目录
   - 从 in-memory map 移除
   - 没注入 BackendFactory 的测试场景跳过 kill,fallback 只清磁盘资源

**验证:** 写单测覆盖 create/get/delete 基本流程;`mvn test -Dtest=TeamManagerTest`;tmux 实跑后 `/team delete --force` 看 pane 真的被杀(`tmux list-panes` 只剩 Lead)

## T3b: Team.Manager 跨进程并发兜底 — 继续 `TeamManager.java` + `Persistence.java`**文件:** `Team.java` / `Persistence.java`
**依赖:** T3
**步骤:**
1. `Persistence` 增 `static void reloadFromDiskLocked(Team t)`——调用方持锁;从 `t.configPath()` `readJson`,把 `members` 字段覆盖到 in-memory(失败静默回退到内存现状)
2. `Team.addMember` 与 `Team.setMemberActive`(以及任何会修改 members 后 save 的方法)在持锁后**先**调 `Persistence.reloadFromDiskLocked(this)` 再操作内存 + save
3. 不是为了多线程并发——in-process 早就有 `lock` 保护;**是为了跨进程**:Pane 后端的 Lead 与子进程是两个独立进程,各持一份内存中的 Team。如果不 reload,会出现「子进程读 config 时 Lead 的 addMember 还没写入,子进程修改自己内存 Team 没看见自己,setMemberActive 静默 no-op」的丢更新

**验证:** 单测构造时序:t1 = readJson 得到无 alice 的 Team A;t2 在 disk 上写带 alice 的 Team B;t3 调 `team.setMemberActive("alice", false)` 应该成功(走 reload 路径)而非静默 no-op

## T4: Team 成员操作 — 继续 `Team.java`**文件:** `Team.java`
**依赖:** T3, T3b
**步骤:**
1. 实现 `boolean addMember(TeammateInfo info)`(F8)——持锁后**先 reloadFromDiskLocked**(见 T3b),检查重名;加入 members;持久化
2. 实现 `boolean setMemberActive(String name, boolean active)`(F9)——持锁后**先 reloadFromDiskLocked**;遍历 members 找到 name 改 isActive 字段;持久化
3. 实现 `boolean removeMember(String name)`(F10)
4. 实现 `Optional<TeammateInfo> memberByName(String name)` / `memberByAgentId(String id)` 工具方法

**验证:** 单测覆盖 add → setActive → remove 三步流程,读回 config.json 校验字段

## T5: mailbox 文件锁 — `dev/gcode/team/mailbox/MailboxLock.java`**文件:** `src/main/java/dev/gcode/team/mailbox/MailboxLock.java`
**依赖:** 无
**步骤:**
1. 定义 `package dev.gcode.team.mailbox;`
2. 实现 `static AutoCloseable acquire(Path lockPath) throws IOException`——
   - 循环 10 次:`Files.newOutputStream(lockPath, CREATE_NEW, WRITE).close()` 抢锁
   - 失败时 `Files.getLastModifiedTime(lockPath)`,若 `Instant.now().minus(...).toEpochMilli() - mtime > 10000` 则 `Files.deleteIfExists(lockPath)` 后立即重试一次
   - 失败时 `Thread.sleep(ThreadLocalRandom.current().nextLong(5, 101))` 后继续
   - 返回 `AutoCloseable` 闭包:`Files.deleteIfExists(lockPath)`(配合 try-with-resources)
3. 内部常量 `LOCK_MAX_RETRIES = 10` / `LOCK_STALE_AFTER = Duration.ofSeconds(10)` / `LOCK_BACKOFF_MIN_MS = 5` / `LOCK_BACKOFF_MAX_MS = 100`

**验证:** 单测 `testAcquireLockSerial`(两次抢锁,中间 close)、`testAcquireLockStale`(故意创建 11 秒前的锁,断言能拿到)

## T6: mailbox Message 与 Mailbox — `dev/gcode/team/mailbox/Mailbox.java`**文件:** `src/main/java/dev/gcode/team/mailbox/Mailbox.java`、`Message.java`、`MessageType.java`、`ReadUnreadResult.java`
**依赖:** T5
**步骤:**
1. 定义 `MessageType` 枚举 + 4 个常量(F32)
2. 定义 `Message` record(F32),字段带 `@JsonProperty`
3. 定义 `ReadUnreadResult` record:`(List<Integer> indices, List<Message> messages)`
4. 定义 `Mailbox` 类,字段 `Path dir`
5. 实现构造器 `new Mailbox(Path dir)`——`Files.createDirectories(dir)`
6. 实现 `void write(String agentId, Message msg)`(F33)
   - lockPath = `dir.resolve(agentId + ".lock")`
   - try-with-resources `MailboxLock.acquire(lockPath)`(T9 抽到 filelock 后,这里改为 `FileLock.acquire(...)`)
   - 读 `dir.resolve(agentId + ".json")`(不存在视为 `{"messages":[]}`)
   - 追加 msg(若 `timestamp==0` 设为 `Instant.now().getEpochSecond()`)
   - atomic write(用 `Persistence.atomicWriteJson`)
7. 实现 `List<Message> read(String agentId)`
8. 实现 `ReadUnreadResult readUnread(String agentId)`——返回 unread 消息的 indices 与消息本身
9. 实现 `void markRead(String agentId, List<Integer> indices)`——按 indices 把对应消息 `read=true`

**验证:** 单测覆盖 write/read/markRead;并发测试 10 个 virtual thread 写同一 agentId,断言读回 10 条无丢失

## T7: AgentNameRegistry — `dev/gcode/team/registry/AgentNameRegistry.java`**文件:** `src/main/java/dev/gcode/team/registry/AgentNameRegistry.java`
**依赖:** 无
**步骤:**
1. 定义 `AgentNameRegistry` 类
2. 实现 `void register(String name, String agentId)`——若 name 已存在覆盖(取出旧 agentId,从 byId 删旧映射);若 agentId 已有其他 name,先反向 unregister
3. 实现 `void unregister(String name)`
4. 实现 `void unregisterByAgentId(String agentId)`
5. 实现 `Optional<String> resolve(String nameOrId)`——先按 name 查,再按 agentId 反向查
6. 实现 `Optional<String> nameOf(String agentId)`
7. 实现 `Map<String,String> snapshot()`

**验证:** 单测覆盖 register/unregister/resolve/nameOf;包括「同名覆盖」和「不同名指向同一 agentId」边界

## T8: tasks Store — `dev/gcode/team/tasks/Store.java`**文件:** `src/main/java/dev/gcode/team/tasks/Store.java`、`Status.java`、`Task.java`、`Filter.java`、`Patch.java`
**依赖:** T5(用 mailbox lock)
**步骤:**
1. 定义 `Status` 枚举 + 4 常量
2. 定义 `Task`、`Filter`、`Patch` record(F30)
3. 定义 `Store` 类,字段 `Path path`、`ReentrantLock lock`
4. 实现构造器 `new Store(Path path)`
5. 实现 `String create(Task t)`——生成 `task_<6位 hex>` ID(`String.format("task_%06x", ThreadLocalRandom.current().nextInt(0x1000000))`);read-modify-write `tasks.json`(用 lock 文件,路径 `path.resolveSibling(path.getFileName() + ".lock")`,复用 `MailboxLock.acquire`——下一步 T9 会把这部分抽到独立 `dev.gcode.team.filelock` 包,mailbox 与 tasks 共用)
6. 实现 `Optional<Task> get(String id)`
7. 实现 `List<Task> list(Filter f)`——按 `status` 过滤,返回时附加 `isReady` 字段(检查 blockedBy 中所有任务是否 completed);为简化可在 list 输出时计算 ready 标记,不存盘
8. 实现 `void update(String id, Patch p)`——支持 title/description/status/assignee/addBlocks/addBlockedBy/removeBlocks/removeBlockedBy 字段
9. `addBlockedBy=[X]` 同时给 X 任务 `blocks` 加上当前任务 id(双向维护)

**注意:** isReady 在 list 输出时通过 `TaskView` record 封装(`record TaskView(Task task, boolean isReady)`),不污染 disk 上的 Task。为减小循环依赖,把锁实现提到独立 `dev.gcode.team.filelock` 包(见 T9),mailbox 与 tasks 共用。

**验证:** 单测覆盖 create/get/update;特别测 addBlockedBy 的双向更新

## T9: 共用 filelock 包(从 mailbox 抽出)**文件:** `src/main/java/dev/gcode/team/filelock/FileLock.java`(把 T5 实现迁过来)
**依赖:** 无
**步骤:**
1. 把 T5 的 `MailboxLock.acquire` 实现迁到 `package dev.gcode.team.filelock;`,类名改为 `FileLock`,方法签名保持 `static AutoCloseable acquire(Path lockPath) throws IOException`
2. 在 `dev/gcode/team/mailbox/MailboxLock.java` 改为 `import dev.gcode.team.filelock.FileLock;` 后委托给 `FileLock.acquire(...)`,或直接删 `MailboxLock` 类、把 mailbox 内调用改为 `FileLock.acquire(...)`
3. 在 `dev/gcode/team/tasks/Store.java` 也 `import dev.gcode.team.filelock.FileLock;`,T8 中的 `MailboxLock.acquire(...)` 改为 `FileLock.acquire(...)`

**验证:** `mvn -q -DskipTests -pl . test-compile` 通过;`mvn -q test -Dtest='dev.gcode.team.**'` 全过(覆盖 mailbox 与 tasks 包)

## T10: backend 接口 — `dev/gcode/team/backend/Backend.java`**文件:** `src/main/java/dev/gcode/team/backend/Backend.java`、`SpawnRequest.java`、`SpawnResult.java`、`BackendFactory.java`
**依赖:** T1
**步骤:**
1. 定义 `Backend` 接口(F12)
2. 定义 `SpawnRequest` record(F13)——`subAgent` / `conv` / `taskManager` 字段类型为 `Object`,避免 backend 反向依赖 agent 包
3. 定义 `SpawnResult` record `(String paneId, String agentId)`
4. 定义 `BackendFactory.create(BackendType t, Deps deps)` 工厂——按类型分发(暂时只占位,具体实现在 T12-T14)

**验证:** `mvn -q -DskipTests compile` 通过

## T11: BackendDetector — `dev/gcode/team/backend/BackendDetector.java`**文件:** `src/main/java/dev/gcode/team/backend/BackendDetector.java`
**依赖:** T10
**步骤:**
1. 实现 `static BackendType detect()`(F14):
   - `System.getenv("TMUX") != null` → TMUX
   - `"iTerm.app".equals(System.getenv("TERM_PROGRAM"))` 且 `findOnPath("it2").isPresent()` → ITERM2
   - `findOnPath("tmux").isPresent()` → TMUX
   - 否则 IN_PROCESS
2. 内部 `findOnPath(String binary)` 用 `System.getenv("PATH").split(File.pathSeparator)` 遍历检查

**验证:** 写 test 用 `Mockito.mockStatic` 或自己注入 `EnvProvider` 接口控制环境变量,断言不同组合的返回值

## T12: tmux backend — `dev/gcode/team/backend/tmux/TmuxBackend.java`**文件:** `src/main/java/dev/gcode/team/backend/tmux/TmuxBackend.java`
**依赖:** T10
**步骤:**
1. 定义 `TmuxBackend` 类实现 `Backend`
2. 实现 `BackendType type()` 返回 `BackendType.TMUX`
3. 实现 `SpawnResult spawn(SpawnRequest req)`(F15):
   - 在 `$TMUX` 内:`tmux split-window -h -P -F "#{pane_id}" -- <cmd>`
   - 在 `$TMUX` 外但 `tmux` 二进制可用:`tmux new-session -d`(detached 新会话)走外部 session(F16)
   - `cmd` 构造:`gcode --team-member --team <teamName> --member <memberName> --agent-id <agentId> --session-dir <sessionDir> --worktree <wtPath> [--agent-type <type>] [--model <model>] [--plan-mode]`
   - `--agent-id` 必须传——子进程不需要读 Lead 还没写完的 `config.json` 找自己
   - `initialPrompt` **不**走命令行,由 `SpawnTeammate`(T18)在 backend.spawn 之前预写入 alice mailbox
   - 用 `new ProcessBuilder(...).start()` 跑 tmux,捕获 stdout 作为 paneId
4. 实现 `void wake(String paneId, String agentId)`:`tmux send-keys -t <paneId> "" Enter`(子进程 stdin scanner 读到回车,立刻去 mailbox 轮询)
5. 实现 `void kill(String paneId, String agentId)`:`tmux kill-pane -t <paneId>`,忽略 pane not found 错误

**注意:** spawn 启动的 gcode CLI 需要支持 `--team-member` flag;这部分留给 T21(Main.java 改造)与 T29(TeamMemberRunner)

**验证:** 单测断言命令字符串构造正确(注入一个 `Function<List<String>, ProcessOutput>` 命令执行器 fake,断言 args list);集成测试在 CI 跳过(需要 tmux)

## T13: iterm2 backend — `dev/gcode/team/backend/iterm2/Iterm2Backend.java`**文件:** `src/main/java/dev/gcode/team/backend/iterm2/Iterm2Backend.java`
**依赖:** T10
**步骤:**
1. 实现 `spawn`:`it2 split --new-pane --command "<cmd>"`(实际 it2 CLI 命令以官方为准;先按 README 描述实现,实测可能要调);`<cmd>` 同 T12 格式,含 `--agent-id`,`initialPrompt` 走 mailbox 预写
2. 实现 `wake`:`it2 send-text --pane <paneId> ""`
3. 实现 `kill`:`it2 close-pane --pane <paneId>`

**注意:** iterm2 后端无法在 CI 中实跑,实现以构造正确的命令字符串为准

**验证:** 单测断言命令构造正确

## T14: in-process backend — `dev/gcode/team/backend/inprocess/InProcessBackend.java`**文件:** `src/main/java/dev/gcode/team/backend/inprocess/InProcessBackend.java`
**依赖:** T10,需要 `agent`、`task`、`conversation` 包
**步骤:**
1. 定义 `InProcessBackend` 类,字段 `TaskManager taskManager`
2. 实现 `spawn(SpawnRequest req)`(F18):
   - 从 `req.subAgent()` / `req.conv()` 取已构造好的对象((Agent) 强转)
   - 调 `taskManager.launch(subAgent, conv, req.memberName(), req.initialPrompt())` 起 virtual thread,返回 taskId(即 agentId)
   - 返回 `new SpawnResult("", agentId)`(paneId 为空)
3. 实现 `wake`:no-op,返回 void
4. 实现 `kill`:`taskManager.stop(agentId)`

**Backend 接口签名统一为**(回 T10 调整):
```java
public interface Backend {
    BackendType type();
    SpawnResult spawn(SpawnRequest req) throws IOException;
    void wake(String paneId, String agentId) throws IOException;
    void kill(String paneId, String agentId) throws IOException;
}

public record SpawnResult(String paneId, String agentId) {}
```
Pane 后端用 paneId,in-process 用 agentId;接口统一传两者,各自取需要的。

**验证:** 单测:构造 fake TaskManager,spawn 一个 noop 子 Agent,断言 virtual thread 启动

## T15: feature flag — `dev/gcode/team/Feature.java`**文件:** `src/main/java/dev/gcode/team/Feature.java`
**依赖:** 无
**步骤:**
1. 实现 `static boolean forkTeammateEnabled(AppConfig cfg)`——读 `cfg.features().forkTeammate()`
2. 实现 `static boolean has(String key, AppConfig cfg)`——按 key 名查 features

**验证:** 单测覆盖 true/false 两种 cfg

## T16: TeammateContext — `dev/gcode/agent/TeamHook.java` + `TeammateContext.java`**文件:** `src/main/java/dev/gcode/agent/TeamHook.java`、`TeammateContext.java`
**依赖:** 无
**步骤:**
1. 定义 `TeamHook` 接口(plan.md 已给签名)
2. 定义 `TeamSpawnRequest` record(把 Agent 工具参数传过去)
3. 定义 `TeammateContext` 类——`teamName`、`memberName`、`agentId`、`mailboxDir`、`Function<String, ReadUnreadResult> readUnread` 闭包等
4. 提供 `InvocationContext.withTeammateContext(tc)` + `static Optional<TeammateContext> teammateContextFrom(InvocationContext ctx)`(用 ThreadLocal 或 invocation ctx 的 attribute map)

**验证:** `mvn -q -DskipTests compile` 通过

## T17: 队员专属工具白名单 — `dev/gcode/tool/Filter.java` 扩展**文件:** `src/main/java/dev/gcode/tool/Filter.java`(修改)
**依赖:** 无
**步骤:**
1. 新增常量:
   ```java
   public static final List<String> TEAMMATE_EXTRA_TOOLS = List.of(
       "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "SendMessage"
   );
   ```
2. 扩展 `FilterParams` record 加 `boolean teammate` 字段
3. 在 `applyAgentToolFilter` 中:若 `teammate=true`,把 `TEAMMATE_EXTRA_TOOLS` 加到允许集合(在 disallowed 删除之前);非 teammate 时排除这些工具(主 Agent 看不到)
4. 同时增加常量 `TEAM_LEAD_DISALLOWED_TEAMMATE_TOOLS`——避免主 Agent 直接看到 TaskCreate 等(应该走 teammate=true 才能加上)

**简化策略:** TEAMMATE_EXTRA_TOOLS 不进默认 registry(由 Main 注册到 registry,但默认从 ALL 过滤集移除);teammate=true 时把它们加回。

**采用:**
- Main 把 5 个协作工具注册到 registry
- 修改默认 filter:`ALL_AGENT_DISALLOWED_TOOLS` 加上这 5 个工具(子 Agent 默认看不到)
- 新增 `TEAMMATE_ALLOWED_TOOLS = ALL_AGENT_DISALLOWED_TOOLS 中的协作工具`
- 修改 `applyAgentToolFilter`:`teammate=true` 时,这 5 个工具不被 ALL 过滤

**验证:** 单测覆盖 teammate=true / false,断言 TaskCreate 等可见性

## T18: SpawnTeammate 主流程 — `dev/gcode/team/SpawnTeammate.java`**文件:** `src/main/java/dev/gcode/team/SpawnTeammate.java`
**依赖:** T1-T17
**步骤:**
1. 定义 `TeamManager.spawnTeammate(TeamSpawnRequest req)`(也可拆到 `SpawnTeammate.java`,在 TeamManager 内委托)
2. 实现 plan.md 中描述的步骤流程:
   - 取 Team
   - 校验调用者权限(看 ctx 是否有 TeammateContext,且 backendType=IN_PROCESS 时拒绝)
   - 解析 `SubAgentDefinition`
   - `worktreeManager.create(".gcode/worktrees/team-<sanitized>+<member>", "HEAD", false)`
   - 申请 sessionDir(本期复用 ch12 格式,自己生成新 id)
   - 预生成 agentId(`String.format("agent-%014x", ThreadLocalRandom.current().nextLong())`),构造 SpawnRequest 含 agentId 字段
   - 计算 allowed = `Filter.applyAgentToolFilter(new FilterParams(true, ...))`、systemPrompt = `def.systemPrompt() + teamSystemPromptSuffix()`
   - 若 backendType=IN_PROCESS:构造 subAgent(**强制 `dontAsk=true`** F39a)+ subConv,注入 `<team-context>` reminder + `setCtxDecorator` 装 `TeammateContext{mailbox: mc}`
   - 若 backendType=TMUX/ITERM2:`new Mailbox(t.mailboxDir()).write(agentId, new Message("lead", agentId, TEXT, summary, req.prompt(), null, 0, false))` 预写初始任务(F13)
   - `backend.spawn(req)` 取 paneId
   - `registry.register(memberName, agentId)`
   - `team.addMember(...)`(调用时 `reloadFromDiskLocked` 保护跨进程并发)
   - 返回 JSON `{memberName, agentId, worktree, backend, paneId}`
3. 提供 helper `buildTeamContextReminder(team, member, agentId)` 构造 `<team-context>` reminder
4. 提供 helper `teamSystemPromptSuffix()` 返回 F39 附录;`truncateForSummary(prompt)` 给初始任务 mailbox 消息生成 summary

**验证:** 单测覆盖 in-process 后端的 spawn 全流程;Pane 后端的 spawn 用 mock backend

## T19: Agent 工具集成 — `dev/gcode/agent/AgentTool.java` 修改**文件:** `src/main/java/dev/gcode/agent/AgentTool.java`(修改)
**依赖:** T16, T18
**步骤:**
1. `AgentToolArgs` record 加 `@JsonProperty("teamName") String teamName`(可空)
2. `AgentTool` 加字段 `TeamHook teamHook`
3. 构造器加参数 `TeamHook teamHook`
4. `description()` 中说明 `teamName` 参数(可选,非空时走 Team spawn)
5. `parametersSchema()` 加 `teamName` 字段
6. `execute` 在 `args.teamName() != null && !args.teamName().isBlank()` 时:
   - 校验 `teamHook != null`,否则报错
   - 校验 ctx 不在 in-process 队员中(`teamHook.teammateContextOf(ctx)`,若是且 backendType=IN_PROCESS,抛 `InProcessTeammateNoSpawnException`)
   - 调 `teamHook.spawnTeammate(new TeamSpawnRequest(...))`
   - 返回 spawnTeammate 的结果

**验证:** 单测:不带 teamName 走 ch13 老路径;带 teamName 调 mock teamHook,断言 spawnTeammate 被调

## T20: 队员 Loop incoming-messages 注入 — `dev/gcode/agent/TeamMailboxIngestor.java`**文件:** `src/main/java/dev/gcode/agent/TeamMailboxIngestor.java`(新建)
**依赖:** T16, T6
**步骤:**
1. 在 `Agent.run` / `runToCompletion` 的迭代头部(调 LLM 前),检查 invocation ctx 中是否有 TeammateContext;实现位于 `TeamMailboxIngestor.ingest(ctx, runtime)`
2. 若有,调 `tc.readUnread()` 闭包(由 spawn 时由 team 包注入,封装 `Mailbox.readUnread(agentId)`)
3. 若有未读消息,构造 `<incoming-messages>` reminder 字符串(F42),加到 `runtime.pendingReminders`(下一轮 buildReminder 取出)
4. 调 `tc.markRead(indices)` 闭包
5. 若收到 `plan_approval_response(approve=true)`,调 `agent.setPermissionMode(Permission.Mode.DEFAULT)` 切回 default(reminder 文本也会反映这一切换)。**注意:** Pane 后端子进程的 plan_approval 由 `TeamMemberRunner` 主循环额外处理一份——它读到 plan_approval_response 时同样切模式 + 合成续派 prompt 让 runToCompletion 接着跑(F19a)

**注意:** Agent 包不直接 import mailbox(避免循环);通过 `TeammateContext` 中的闭包访问;Message 在 agent 包定义一个轻量 record `IncomingMessage(String from, String type, long timestamp, String summary, String content)`,只取需要的字段。

**采用方案:** TeammateContext 携带闭包:
```java
public record TeammateContext(
    String teamName, String memberName, String agentId,
    Supplier<ReadUnreadView> readUnread,
    Consumer<List<Integer>> markRead
) {}
public record ReadUnreadView(List<Integer> indices, List<IncomingMessage> messages) {}
```
由 team 包在 spawn 时构造闭包注入。

**验证:** 单测覆盖:fake mailbox 写入 1 条消息,启动子 `Agent.run`,断言 reminder 含 `<incoming-messages>`

## T21: TaskManager 改造 — `dev/gcode/task/TaskManager.java` 修改**文件:** `src/main/java/dev/gcode/task/TaskManager.java`(修改)
**依赖:** T7
**步骤:**
1. `TaskManager` 持一个 `AgentNameRegistry nameReg` 引用(可选 null 兜底)
2. `launch` 时:若 nameReg 非 null 且 name 非空,调 `nameReg.register(name, id)`;同时保持本地 `byName` 兜底(避免破坏 ch13 既有调用)
3. `getByName` 优先用 `nameReg.resolve` 查
4. `sendMessage(parentCtx, name, message)` 优先 `nameReg.resolve`
5. 新增 `onTaskDone(Consumer<String> cb)` 注册接口,可注册多个回调(`List<Consumer<String>> taskDoneCallbacks`)
6. `runTask` 的 finally 末尾(在 notifyDone 后)逐个调 onTaskDone 回调
7. 加 `setNameRegistry(AgentNameRegistry reg)` setter

**验证:** 单测:注册 onTaskDone,launch 一个 noop task,等完成,断言回调被触发

## T22: 协作工具实现 — `dev/gcode/team/tools/*Tool.java`**文件:** `TeamCreateTool.java` / `TeamDeleteTool.java` / `TaskCreateTool.java` / `TaskGetTool.java` / `TaskListTool.java` / `TaskUpdateTool.java` / `SendMessageTool.java`
**依赖:** T3, T6, T7, T8
**步骤:**
1. 每个工具实现 `Tool` 接口(`name()` / `description()` / `parametersSchema()` / `readOnly()` / `execute(args, ctx)`)
2. `TeamCreateTool`(F21):参数 teamName + description;`execute` 调 `TeamManager.create`,返回 JSON
3. `TeamDeleteTool`(F23):参数 teamName + force;`execute` 调 `TeamManager.delete`
4. `TaskCreateTool`(F26):参数 title/description/assignee/blockedBy;从 ctx 取 TeammateContext 找当前 Team;`execute` 调 `Store.create`
5. `TaskGetTool`(F27):参数 taskId
6. `TaskListTool`(F28):参数 status 过滤;返回带 isReady 字段的 JSON 数组
7. `TaskUpdateTool`(F29):参数 taskId + 各 Patch 字段
8. `SendMessageTool`(F34):参数 to/summary/message/type/payload;`execute` 调 `Mailbox.write` + `Backend.wake` + 续派检测
9. 每个工具 `readOnly()` 返回:TeamCreate/Delete/TaskCreate/Update/SendMessage 返回 false;TaskGet/TaskList 返回 true

**验证:** 每个工具一个单测覆盖正常路径与错误路径

## T23: 协作工具白名单生效 — 验证**文件:** `src/test/java/dev/gcode/tool/FilterTest.java`(修改)
**依赖:** T17, T22
**步骤:**
1. 在 `applyAgentToolFilter` 测试中加用例:
   - 主 Agent(`teammate=false`)调用:看不到 TaskCreate / SendMessage 等
   - 队员(`teammate=true`)调用:看到这 5 个

**验证:** 测试通过

## T24: coordinator 包 — `dev/gcode/coordinator/Coordinator.java`**文件:** `src/main/java/dev/gcode/coordinator/Coordinator.java`
**依赖:** 无
**步骤:**
1. 实现 `static boolean isEnabled(AppConfig cfg)`——`cfg.features().coordinatorMode() && envTruthy(System.getenv("GCODE_COORDINATOR_MODE"))`
2. 实现 `static List<String> allowedTools()`(F53)
3. 实现 `static String systemPromptSuffix()`(F55)——除四阶段框架外,**必须**包含「派完队员就停手等汇报」的纪律段:派出 Agent/SendMessage 后禁止立刻 read_file/glob/grep/bash 自己探索;禁止 sleep/TaskList 凑时间;只在 Research 首次定位 / Synthesis 读队员产出 / Verification 收敛 时才允许自己用读类工具
4. 实现 `private static boolean envTruthy(String v)`——`"1"`/`"true"`/`"yes"`(大小写不敏感)

**验证:** 单测覆盖双锁的 4 种组合(00/01/10/11),只有 11 返回 true;tmux 实跑观察 Lead 派完队员后不立刻 glob/read_file 而是「等待汇报」

## T25: config 加 Features — `dev/gcode/config/AppConfig.java` 修改**文件:** `src/main/java/dev/gcode/config/AppConfig.java`(修改)
**依赖:** 无
**步骤:**
1. 加 record `FeaturesConfig(boolean coordinatorMode, boolean forkTeammate)`,SnakeYAML 解析时手动绑定
2. `AppConfig` record 加字段 `FeaturesConfig features`
3. 默认值都为 false(`ConfigLoader` 中若 yaml 无 `features` 段,构造 `new FeaturesConfig(false, false)`)

**验证:** 单测加载 yaml 含 features 段(`features:\n  coordinator_mode: true\n  fork_teammate: false`),断言字段被读出

## T26: TUI 集成 — `dev/gcode/tui/TuiApp.java` 修改**文件:** `TuiApp.java` 与 `Statusbar.java`(修改)、`LeadMailWatcher.java`、`LeadMailWaiter.java`(新建)
**依赖:** T3, T24
**步骤:**
1. `TuiParams` record 加 `TeamManager teamManager`、`boolean coordinatorMode`
2. `TuiApp` 加字段 `boolean coordinatorMode` 与 `LinkedBlockingQueue<Object> leadMailQueue`(capacity=1);构造时初始化 `leadMailQueue = new LinkedBlockingQueue<>(1)`
3. coordinator 应用迁到 `Main.java` 中的 mainAgent 上(`setAllowedTools` + `appendSystemPrompt`)——TUI 自身只负责状态栏渲染
4. 状态栏渲染时若 `coordinatorMode==true` 在 mode label 后追加 ` [COORDINATOR]`(参见 `Statusbar.render()`)
5. config 字段名是 **snake_case**(SnakeYAML 默认):`features.coordinator_mode`(不是 camelCase);TuiApp 拿到的是 record `FeaturesConfig` 的 camelCase getter `features.coordinatorMode()`

**验证:** 在 config.yaml 加 `features:\n  coordinator_mode: true`,启动时设环境变量 `GCODE_COORDINATOR_MODE=1`,观察状态栏出现 `[COORDINATOR]`

## T27: /team slash 命令 — `dev/gcode/command/builtin/BuiltinTeam.java`**文件:** `src/main/java/dev/gcode/command/builtin/BuiltinTeam.java`
**依赖:** T3
**步骤:**
1. 注册 4 个本地命令(`CommandKind.LOCAL`):
   - `/team list`(F59)
   - `/team info <name>`(F60)
   - `/team delete <name> [--force]`(F61)
   - `/team kill <member>`(F62)
2. 在 `BuiltinRegistry.registerAll` 或对应注册入口加入

**验证:** `/team list` 在 TUI 输出含已创建 Team

## T28: Main wire — `dev/gcode/Main.java` 修改**文件:** `src/main/java/dev/gcode/Main.java`(修改)
**依赖:** T1-T27
**步骤:**
1. 构造 `AgentNameRegistry nameReg = new AgentNameRegistry()`
2. `taskMgr.setNameRegistry(nameReg)`
3. 构造 `TeamManager teamMgr = new TeamManager(home, root, worktreeMgr, taskMgr, nameReg)`
4. 注册 7 个新工具到 registry(TeamCreate/TeamDelete/TaskCreate/TaskGet/TaskList/TaskUpdate/SendMessage)
5. `AgentTool agentTool = new AgentTool(..., teamMgr)`(把 teamMgr 作为 TeamHook 注入)
6. `TuiParams` 加 `teamManager(teamMgr)`、`coordinatorMode(Coordinator.isEnabled(cfg))`
7. 若 CLI args 含 `--team-member`:**所有依赖 wire 完成后**直接调 `TeamMemberRunner.run(ctx, teamMemberArgs)` 并 `return`,**不**构造 TUI(F19a);否则继续走 TUI 路径
8. Lead 启动时(TUI 路径)若 `Coordinator.isEnabled(cfg)`:`mainAgent.setAllowedTools(Coordinator.allowedTools())` + `mainAgent.appendSystemPrompt(Coordinator.systemPromptSuffix())`

**验证:** `mvn -q -DskipTests package` 通过;启动 gcode 主流程正常

## T29: --team-member 自治循环 — `dev/gcode/cli/TeamMemberRunner.java`(新文件)**文件:** `src/main/java/dev/gcode/cli/TeamMemberRunner.java`(新建)
**依赖:** T28
**步骤:**
1. 用 picocli 解析新增 CLI flags:`--team-member` / `--team` / `--member` / `--agent-id` / `--session-dir` / `--worktree` / `--agent-type` / `--model` / `--plan-mode`
2. Main 中在 `--team-member` 分支先把 `System.setProperty("user.dir", workTree)` + 后续所有 `Path` 都以 `workTree` 作根,再 wire 完所有依赖
3. 实现 `static void run(Context ctx, TeamMemberArgs args)`:
   - 从 `args.teamManager().get(teamName)` 拿 Team(已含 Lead 写入的 alice 条目,reload-from-disk 兜底)
   - 解析角色定义(`SubAgentCatalog.resolve(agentType)`),拿 systemPrompt / maxTurns / plan 等
   - 用 `Filter.applyAgentToolFilter(new FilterParams(true, ...))` 算 allowed tools
   - 构造 provider(`Providers.create`)+ `Agent`,**强制 `dontAsk(true)`**(F39a)
   - 注入 `<team-context>` reminder(F40) + `setCtxDecorator` 把 `TeammateContext{mailbox: mc}` 装进 ctx
   - 起一条 stdin scanner virtual thread:每读一行就 `wakeQueue.offer(SIGNAL)`,触发 mailbox 即时轮询
   - 进主循环(F19a):read unread → 分流消息(text 拼 task / plan_approval / shutdown_request)→ `runToCompletion` → 通知 Lead idle → `setMemberActive(false)` → 等下一条(`wakeQueue.poll(2, SECONDS)`)
   - 检测 mailbox 目录消失 → 优雅退出
4. 把 `AgentEvent` 流转 stdout 打印(`printAgentEvent`),pane 内呈现只读日志

**验证:** 见 AC28 步骤 4 端到端实跑——alice pane 内显示 task 执行流,`/tmp/test_alice.txt` 落地,SendMessage 后 alice 能续派

## T30: 队员空闲通知 hook 注入**文件:** `Main.java`(修改)+ `TeamManager.java`(加 helper)
**依赖:** T21, T3
**步骤:**
1. 在 Main wire 后,注册 onTaskDone 回调到 taskMgr:
   ```java
   taskMgr.onTaskDone(taskId -> teamMgr.handleTaskDone(taskId));
   ```
2. 实现 `void TeamManager.handleTaskDone(String agentId)`:
   - 查 `registry.nameOf(agentId)` → name
   - 遍历 teams 找到该成员所属 Team
   - `team.setMemberActive(name, false)`
   - `new Mailbox(team.mailboxDir()).write(leadAgentId, idleMessage)`

**验证:** 集成测试:in-process 后端 spawn 队员 → 自然结束 → 断言 Team.config 中 isActive=false、Lead mailbox 有 idle 消息

## T30b: Lead mailbox 轮询 + 自动唤醒 — `TeamManager.java` + `tui/LeadMailWatcher.java` + `tui/TuiApp.java`**文件:**
- `TeamManager.java`(增加 `pollLeadMailboxes()` + `LeadMessage` record)
- `tui/LeadMailWatcher.java`(每秒轮询 virtual thread)
- `tui/LeadMailWaiter.java`(阻塞读 leadMailQueue 把信号转 GUI 事件)
- `tui/TuiApp.java`(Init 启动 watcher + waiter;处理 `LeadMailEvent`)
- `tui/StreamPump.java`(增加 `beginAutonomousTurn`)

**依赖:** T28(Main 已 wire teamMgr 进 TuiParams)
**步骤:**
1. `TeamManager.pollLeadMailboxes()`:遍历 `list()`,对每个 Team 用 `new Mailbox(t.mailboxDir()).readUnread(t.leadAgentId())` 读未读,标 read,返回 `List<LeadMessage(String teamName, String from, MessageType type, String summary, String content, long time)>`
2. `TuiApp` 加字段 `LinkedBlockingQueue<Object> leadMailQueue`(capacity=1,构造时初始化)
3. `LeadMailWatcher`(TUI Init 启动 virtual thread):1 秒 sleep loop → pollLeadMailboxes → 非空时调 `buildTeamUpdateReminder`(列消息条目 + content 截断 8000 字)→ `runtime.appendReminders` → 非阻塞 `leadMailQueue.offer(SIGNAL)`
4. `LeadMailWaiter`:阻塞读 leadMailQueue,通过 `gui.getGUIThread().invokeLater(...)` 提交 `LeadMailEvent` 给 TuiApp
5. `TuiApp.handleLeadMailEvent`:
   - re-arm waiter
   - 若 `state == SessionState.IDLE`,调 `beginAutonomousTurn` 自动开新轮
   - 否则 reminder 已在 pendingReminders 里,等当前 Run 下一轮迭代自然取出
6. `beginAutonomousTurn`:合成 user 消息 `"[team-update] 队员发来新消息,请按 Coordinator 流程处理..."`,`conv.addUser(...)` + 调 `beginTurn(userBlock(...))`——保证 LLM 调用满足「对话末尾必须 user」约束,用户在 scrollback 也能看见是自动触发

**验证:** tmux 实跑——Lead 派 alice + bob;30 秒内队员 runToCompletion idle 后 mailbox.unread 1 秒内归零(watcher 消费);若 Lead 当时空闲,屏幕上自动出现 `● [team-update] 队员发来新消息...` 用户文本块 + Lead 紧接着的 Synthesis 回复——内容包含队员报告里的真实文件名(如 `AgentTool.java`、`TeamMailboxIngestor.java`),证明完整 content 通过 reminder 传到 Lead 视野

## T31: 续写检测 — `dev/gcode/team/tools/SendMessageTool.java`**文件:** `SendMessageTool.java`(同 T22)
**依赖:** T22, T21
**步骤:**
1. `SendMessageTool.execute` 写完邮箱后:
   - 取目标 `TeammateInfo.backendType()`
   - 若 backendType=IN_PROCESS:
     - 查 `taskManager.get(agentId)`,若 `status() != RUNNING`:
       - `team.setMemberActive(name, true)`
       - `taskManager.sendMessage(ctx, name, content)` 走 ch13 续派接口
   - 若 Pane 后端:已通过 wake 唤醒,无需续派

**验证:** 单测:先 spawn → 等结束 → SendMessage → 断言 task 重新 RUNNING

## T32: Plan 审批权限切换 — `dev/gcode/agent/TeamMailboxIngestor.java` 增强**文件:** `TeamMailboxIngestor.java`(修改)或 `Agent.java`
**依赖:** T20
**步骤:**
1. 在 incoming-messages 注入逻辑中:若有 `plan_approval_response(approve=true)` 消息:
   - 调 `agent.setPermissionMode(Permission.Mode.DEFAULT)`(或 Lead 当前模式,本期固定 DEFAULT)
   - reminder 加文案:「Lead 已批准计划,权限模式已切到 default,可执行计划」
2. 若 approve=false:reminder 加文案:「Lead 驳回了计划,反馈:<feedback>。请调整后重新提交」

**验证:** 集成测试:队员以 plan 模式起步 → 收到 plan_approval_response(true) → `agent.permissionMode` 切换

## T33: 单元测试集 — 各包 *Test.java**依赖:** T1-T32
**步骤:**
1. 跑 `mvn test`,补失败用例
2. 跑 `mvn spotless:check`(google-java-format 风格),自动修复用 `mvn spotless:apply`
3. 跑 `mvn -q -DskipTests package` 确保打包通过

**验证:** 全绿

## T34: tmux 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. 启动 tmux:`tmux new-session -s ch15-test`
2. 在内层跑 `cd /path/to/gcode && mvn -q -DskipTests package && java -jar target/gcode.jar`
3. 在 TUI 输入:「创建一个名为 demo 的团队」
4. 观察:
   - Agent 调 `TeamCreate`
   - `~/.gcode/teams/demo/config.json` 落地
   - 状态栏 / 输出确认成功
5. 在 TUI 输入:「派 alice 用 general-purpose,在 worktree 里 echo hello > /tmp/test_alice.txt」
6. 观察:
   - tmux split 出新 pane
   - alice pane 内 gcode 子实例启动
   - `.gcode/worktrees/team-demo+alice/` 创建
   - `/tmp/test_alice.txt` 文件内容为 `hello`
7. 在 TUI 输入:`/team info demo`,确认 alice 出现
8. 在 TUI 输入:「给 alice 发消息,让她再写一行 world」(Agent 调 SendMessage)
9. 观察:alice pane 被唤醒,`/tmp/test_alice.txt` 多一行 `world`
10. `/team delete demo --force`,清理

**验证:** 步骤全部成功

## T35: in-process 实跑端到端验证**依赖:** T1-T33
**步骤:**
1. `unset TMUX TERM_PROGRAM`
2. `java -jar target/gcode.jar`
3. Agent 调 `TeamCreate("inproc")` → backend 为 `in-process`
4. Agent 派 bob(后端 in-process)
5. bob 在同进程跑完
6. 观察 `team.config.json` 中 bob 的 `isActive=false`
7. Lead 调 SendMessage(to="bob", message="再做一件事"),bob 从 session 恢复继续

**验证:** 全部成功

## 执行顺序

```
T1 → T2 → T3 → T3b → T4
              ↘
T5 → T6        T8 ── T9(把 lock 抽出,T6/T8 改 import)
T7
T10 → T11
   → T12,T13,T14(并行)
T15
T16 → T17 → T18 → T19
                → T20 → T32
T21
T22 → T23 → T31
T24 → T25 → T26
T27
T28 → T29 → T30 → T30b
T33(收尾测试)
T34, T35(实跑验收)
```

并行机会:T5/T7/T8 互不依赖;T12/T13/T14 互不依赖;T22 中 7 个工具可分批。
````

```markdown
# Agent Team Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为而非实现细节。

## 实现完整性

- [ ] `TeamManager` 可被实例化:`new TeamManager(home, root, wtMgr, taskMgr, nameReg)` 返回非 null(验证:`mvn -q -DskipTests compile`、跑单测)
- [ ] `TeamManager.create("demo", "")` 在 `~/.gcode/teams/demo/config.json` 落地(验证:运行单测后检查文件存在)
- [ ] `TeamManager.create("foo bar/baz", "")` sanitize 后路径为 `~/.gcode/teams/foo-bar-baz/`(验证:单测)
- [ ] 同名 Team 第二次 create 自动后缀 `-2`(验证:单测)
- [ ] `BackendType` 三个值齐全:`TMUX` / `ITERM2` / `IN_PROCESS`(验证:`mvn spotbugs:check` 通过 + 单测枚举)
- [ ] `BackendDetector.detect()` 在 `$TMUX` 设置时返回 `TMUX`;两环境变量都清空时返回 `IN_PROCESS`(验证:注入 `EnvProvider` 接口的单测)
- [ ] `Mailbox.write` + `Mailbox.read` 一进一出消息字段一致(验证:单测)
- [ ] mailbox 文件锁在 stale 10 秒后能被新 writer 抢占(验证:单测制造 11 秒前的锁,断言能拿到)
- [ ] `AgentNameRegistry.register("alice", "agent-123")` 后 `resolve("alice")` 返回 `Optional.of("agent-123")`,`nameOf("agent-123")` 返回 `Optional.of("alice")`(验证:单测)
- [ ] `Store.create` 返回的 task id 形如 `task_<6位 hex>`(验证:单测)
- [ ] `Store.update(id, new Patch(..., addBlockedBy=[other], ...))` 同时给 other 任务的 `blocks` 加上 id(验证:单测断言双向)
- [ ] `Store.list(new Filter(Optional.of(PENDING)))` 返回结果带 `isReady` 字段,反映 blockedBy 是否全 completed(验证:单测)
- [ ] `Coordinator.isEnabled` 在 feature flag 关 + 环境变量开时返回 false(验证:单测 4 种组合)
- [ ] `Coordinator.allowedTools()` 含 `bash` 不含 `write_file` / `edit_file`(验证:单测)
- [ ] `Filter.applyAgentToolFilter(new FilterParams(true, ...))` 返回值含 `TaskCreate` / `SendMessage` 等 5 个协作工具(验证:单测)
- [ ] `Filter.applyAgentToolFilter(new FilterParams(false, ...))` 不含这 5 个工具(验证:单测)
- [ ] 7 个新工具注册到 registry 后,`ToolRegistry.definitions()` 输出含 `TeamCreate` / `TeamDelete` / `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `SendMessage`(验证:单测或启动后 `/status`)
- [ ] `Team.addMember` 与 `Team.setMemberActive` 调用前先 `Persistence.reloadFromDiskLocked` 重读 disk(验证:跨进程并发写 disk 时不丢更新——单测制造「Lead 在 alice 子进程读完 config 之后才 addMember」的时序,alice 走 setMemberActive(false) 后回读 disk 应看到 isActive=false)

## 集成

- [ ] `Agent` 工具不带 `teamName` 时走 ch13 原路径,行为不变(验证:`mvn test -Dtest=AgentToolTest` 全过)
- [ ] `Agent` 工具带 `teamName="demo"` 时调 `teamHook.spawnTeammate`(验证:单测 mock teamHook,断言被调用)
- [ ] `spawnTeammate` 创建 worktree 路径为 `.gcode/worktrees/team-demo+alice`(验证:单测/集成测试)
- [ ] `spawnTeammate` 后 `team.members` 含 alice,持久化到 `config.json`(验证:单测)
- [ ] in-process 后端的队员 ctx 含 TeammateContext,其 backendType=IN_PROCESS;该队员调用 `Agent(teamName=...)` 被拒绝并抛 `InProcessTeammateNoSpawnException`(验证:集成测试)
- [ ] 队员 `Agent.run` 头部读取 mailbox 未读消息,以 `<incoming-messages>` reminder 注入到 LLM 输入(验证:单测,fake mailbox 写消息,捕获 Agent 构造的 prompt)
- [ ] 队员收到 `plan_approval_response(approve=true)` 后 `agent.permissionMode` 切换到 DEFAULT(验证:单测 + tmux 实跑——见场景 4)
- [ ] 队员 `runToCompletion` 结束触发 `onTaskDone` 回调,Team config 中该成员 `isActive=false`(验证:单测注册回调 + launch noop task)
- [ ] 队员 idle 后 Lead mailbox 收到 `summary="<name> idle"` 消息(验证:单测/集成)
- [ ] `SendMessage(to="alice", ...)` 在 alice 已 stop 且为 in-process 后端时,通过 `taskManager.sendMessage` 续派(验证:集成测试,断言 task status 回到 RUNNING);Pane 后端时通过 `backend.wake` 让子进程读 mailbox 自然续派
- [ ] 所有 Team 队员一律 `dontAsk=true`(覆盖角色 frontmatter 的 permissionMode),子进程没人能应答 ApprovalRequest 不会卡死(验证:用 `permissionMode: default` 的角色派队员让她调 bash,实跑断言任务正常完成,而不是卡在 Ask)
- [ ] Pane 后端 spawn 时 `initialPrompt` 通过预写入 mailbox(type=text, from=lead)送达,子进程不需要走 CLI 参数(验证:tmux 实跑,在 spawn 完检查 alice mailbox 已有一条 from=lead 的初始任务)
- [ ] Pane 后端子进程命令行含 `--agent-id <id>` 参数(验证:看 `TmuxBackend.buildMemberCmd` 单测;tmux 实跑后 `ps auxww | grep team-member` 看实际命令)
- [ ] Pane 后端的 `gcode --team-member` 子进程**不启动 TUI**,跑 `TeamMemberRunner.run` 自治循环——读 mailbox → `runToCompletion` → 通知 Lead idle → stdin wake 等下一轮(验证:tmux 实跑看 alice pane 显示纯文本日志流而非 gcode TUI 框)
- [ ] Lead mailbox watcher 每秒轮询所有 Team 的 lead.json,把未读消息转 `<team-update>` reminder 推 pendingReminders + 给 `leadMailQueue` 发信号(验证:tmux 实跑后看 alice 发完 idle 通知 1 秒内 mailbox 的 unread 归零、read 累加)
- [ ] Lead 在 `SessionState.IDLE` 时收到 `LeadMailEvent`,TUI 调 `beginAutonomousTurn` 合成 user 消息自动开新轮(验证:tmux 实跑——派完队员等他完成,Lead 不需要用户输入就自动出现 `[team-update]...` 行 + Synthesis 回复)
- [ ] `/team list` 输出含 `~/.gcode/teams/` 下所有 Team(验证:TUI 实跑)
- [ ] `/team delete demo --force` 调 `backend.kill` 杀 pane(tmux/iterm2)+ 清 worktree + 清 team 目录(验证:TUI 实跑后 `tmux list-panes` 只剩 Lead,worktree 与 team 目录都消失)
- [ ] 沙箱开放 `/tmp` 与 `/private/tmp`(macOS 真实路径)作为白名单——write_file/edit_file 可写 `/tmp/foo.txt`,但 `/etc/passwd` 仍拒(验证:单测 `SandboxTest.testContains` 含两组用例)

## 编译与测试

- [ ] `mvn -q -DskipTests package` 无错误(验证:命令退出码 0)
- [ ] `mvn spotbugs:check` 无警告(验证:命令退出码 0)
- [ ] `mvn test` 全部通过(验证:命令退出码 0)
- [ ] `mvn spotless:check` 通过——所有源文件符合 google-java-format(验证:无未格式化文件)

## 端到端场景(tmux 实跑)

> 这是本章的核心验收场景,必须在真实 tmux 会话内手动跑一遍。

**场景 1:tmux 后端,Team 全生命周期**

环境准备:
- macOS / Linux
- tmux 已安装
- JDK 21 安装
- 当前不在 gcode 进程内,准备开新 tmux 会话

步骤:
- [ ] `tmux new-session -s ch15-test` 进入新 tmux 会话
- [ ] `cd /path/to/gcode && mvn -q -DskipTests package`(预编译,加快冷启动)
- [ ] `java -jar target/gcode.jar` 启动 TUI;启动消息显示一切正常,无 ch15 相关 error
- [ ] 在 TUI 输入:「创建一个名为 demo 的团队」
  - 预期:Agent 调 `TeamCreate(teamName="demo")`;返回 `{"teamName":"demo","backend":"tmux","configPath":"..."}`
  - 验证:`ls ~/.gcode/teams/demo/config.json` 存在;`cat config.json` 中 `backend` 字段为 `tmux`
- [ ] 在 TUI 输入:「派 alice 用 general-purpose 角色,在 worktree 里跑 `echo hello > /tmp/test_alice.txt && pwd > /tmp/test_alice_pwd.txt`」
  - 预期:Agent 调 `Agent(teamName="demo", subagentType="general-purpose", name="alice", prompt="...")`
  - 验证 a:tmux 自动 split 出右侧 pane(`tmux list-panes -F "#{pane_id} #{pane_current_command}"` 看到新 pane)
  - 验证 b:新 pane 内**显示自治循环日志流**(`[team-member] alice · team=demo · agent=... · cwd=...` 起始行 + Agent 工具调用打印,**不是** gcode TUI 框)
  - 验证 c:`ls /path/to/gcode/.gcode/worktrees/team-demo+alice/` 目录存在
  - 验证 d:等待 30 秒,`cat /tmp/test_alice.txt` 内容为 `hello`
  - 验证 e:`cat /tmp/test_alice_pwd.txt` 内容为 worktree 路径(`.../team-demo+alice`)
  - 验证 f:`cat ~/.gcode/teams/demo/config.json` 中 `members` 数组含 alice,`backendType="tmux"`,`paneId` 非空
  - 验证 g:`~/.gcode/teams/demo/mailbox/<aliceAgentId>.json` 中应已含一条 from=lead 的 text 消息——Pane 后端的 initialPrompt 预写入证据
- [ ] 在 TUI 输入 `/team info demo`
  - 预期:输出含 alice 行,显示 worktree、paneId、isActive 状态
- [ ] 在 TUI 输入:「给 alice 发消息,让她再写一行 world 到 /tmp/test_alice.txt」
  - 预期:Agent 调 `SendMessage(to="alice", summary="append world", message="...")`
  - 验证 a:alice pane 被唤醒(`tmux send-keys` 触发,pane 显示新内容)
  - 验证 b:30 秒内,`cat /tmp/test_alice.txt` 看到第二行 `world`
- [ ] 等待 alice 任务自然结束(或在 TUI 输入 `/team kill alice` 终止)
  - 验证 a:`cat ~/.gcode/teams/demo/config.json` 中 alice 的 `isActive` 为 `false`(跨进程 reload 修复——alice 子进程的 `setMemberActive(false)` 必须真的反映到 disk;早期 bug 是静默 no-op)
  - 验证 b:Lead 的 mailbox(`cat ~/.gcode/teams/demo/mailbox/lead.json`)含一条 `summary` 含 `idle` 的消息,且 1-2 秒后该消息 `read=true`(watcher 已消费)
  - 验证 c:Lead 屏幕**不需要用户输入**自动出现 `● [team-update] 队员发来新消息...` 文本块 + 紧接的 Synthesis 回复(自动唤醒)
- [ ] 在 TUI 输入 `/team delete demo --force`
  - 验证 a:`ls ~/.gcode/teams/` 无 `demo` 目录
  - 验证 b:`ls /path/to/gcode/.gcode/worktrees/` 无 `team-demo+alice`
  - 验证 c:`tmux list-panes` 只剩 Lead pane,alice 的 `%1` 被 `backend.kill` 干掉了

**场景 2:in-process 后端实跑**

环境准备:
- `unset TMUX TERM_PROGRAM`(确保 detect 选 IN_PROCESS)
- 在非 tmux 终端窗口内

步骤:
- [ ] 启动 `java -jar target/gcode.jar`(同会话已 unset 上述变量)
- [ ] 在 TUI 输入:「创建 inproc 团队」
  - 验证:`cat ~/.gcode/teams/inproc/config.json` 中 `backend` 为 `in-process`
- [ ] 在 TUI 输入:「派 bob 用 general-purpose,在 worktree 里 `echo step1 > /tmp/bob.txt`」
  - 验证:无新终端窗口/pane 出现(同进程 virtual thread)
  - 验证:`/tmp/bob.txt` 内容 `step1`
- [ ] 等 bob 结束(`/team info inproc` 看 isActive=false)
- [ ] 在 TUI 输入:「给 bob 发消息让他再加一行 step2」
  - 验证:`/tmp/bob.txt` 多一行 `step2`
  - 验证:`/team info inproc` 看 bob 在 active → idle 反复变化
- [ ] `/team delete inproc --force` 清理

**场景 3:Coordinator Mode 实跑**

环境准备:
- `.gcode/config.yaml` 加 `features:\n  coordinator_mode: true`(snake_case,不是 camelCase)
- 设环境变量 `GCODE_COORDINATOR_MODE=1`

步骤:
- [ ] `GCODE_COORDINATOR_MODE=1 java -jar target/gcode.jar`
- [ ] 观察 TUI 状态栏出现 `[COORDINATOR]` 标签
- [ ] 在 TUI 输入:「写一个 hello world 到 /tmp/coord_test.txt」
  - 预期:`write_file` **不在 Lead 工具集**(被 `setAllowedTools` 剥夺),LLM 应该说「我没有 write_file 工具」并尝试用 bash 转写
  - 验证:`cat /tmp/coord_test.txt` 文件不存在(若用户拒掉 bash 的话)
- [ ] 在 TUI 输入:「跑 `git status`」
  - 预期:Agent 调 `bash`,工具正常执行(bash 在 Coordinator 白名单中)
  - 验证:输出含 git 状态信息
- [ ] 在 TUI 输入:「派几个队员探索 gcode 的 dev/gcode/agent 和 dev/gcode/team」
  - 预期:Lead 调 Agent + SendMessage 派出队员后,**不**立刻调 read_file/glob/bash 自己探索(被 Coordinator system prompt 中的纪律段约束)
  - 验证:Lead 派完队员的回复应该是「等待汇报中」类似措辞;在队员发完 idle 消息前 Lead 屏幕没新工具调用

**场景 4:Plan 审批工作流**

环境准备:无特殊

步骤:
- [ ] 准备一个角色定义 `~/.gcode/agents/planner.md`,frontmatter 含 `permissionMode: plan`,body 简述「先制定计划」
- [ ] 启动 gcode,创建 team `plan-test`
- [ ] 在 TUI 输入:「派 planner 用 planner 角色,在 worktree 制定 hello world 程序的实现计划」
  - 预期:planner 队员以 plan 模式起步,生成计划后通过 SendMessage 发给 Lead
  - 验证:Lead mailbox 含计划消息
- [ ] 在 TUI 输入:「批准 planner 的计划」
  - 预期:Lead 调 `SendMessage(to="planner", type="plan_approval_response", payload={approve:true})`
  - 验证:planner 收到后切换权限模式,继续执行计划

## 失败回归

- [ ] gcode 启动时 `~/.gcode/teams/` 不存在,自动创建,不报错
- [ ] `~/.gcode/teams/<somename>/config.json` 内容损坏时,启动只 stderr 警告,跳过该 Team
- [ ] 创建 Team 时若 disk 写失败(可手动 chmod 模拟),抛 IOException,不留半成品目录
- [ ] mailbox 文件锁抢占冲突 10 次仍失败时,SendMessage 抛 IOException,不丢消息
- [ ] tmux 后端在 `tmux split-window` 失败时(非 tmux 会话),抛错误,Team.members 不留半成品
- [ ] 协作工具被主 Agent 误调用(主 Agent 工具列表本应不含)时,工具自己也返回 error 兜底
```

### TypeScript

```markdown
# Agent Team Spec## 背景

ch13 SubAgent 把任务从单 Agent 委派给子 Agent，实现了消息、权限与文件读缓存的隔离；ch14 Worktree 给每个子 Agent 提供独立工作目录。但这两章合起来仍是「星型」拓扑——所有子 Agent 都从主 Agent 出发，单次跑完即弃；主 Agent 既要决策又要中转，既是大脑又是邮局。对「同时让三个队员探索同一仓库」「让一个 reviewer 队员持续盯着代码合并」这类需要长存活、需要彼此横向通信的场景，星型结构难以表达。

本章把 gcode 从「单次 spawn 即弃」升级到「队员可长期存活、Lead 通过共享信箱与之沟通」：

- 主 Agent 通过专用工具创建 **Team**；同一个 gcode 进程内可同时持有多个 Team
- 每个 **队员** 拥有一个独立的信箱、一份对话历史、一份运行进度状态
- 队员在后台异步执行；跑完一轮任务后向 Lead 信箱发送 idle 通知，然后轮询自己的信箱等待新任务，收到 shutdown 消息后优雅退出
- 队员之间通过**共享信箱**直接通信，不必经过 Lead 中转
- Lead 端在「至少有一个 Team 存在」时自动剥夺写类工具，强制 Lead 派活给队员而不是自己写代码
- TUI 提供 Spinner Tree、队员消息块、Teams Dialog（按快捷键调出）等可视化界面；Lead 主对话循环每轮从信箱抽取 `<team-notification>` 提醒注入到大模型输入

本章还包含一个独立子模块——代码评审协作：在 Team 之上叠加 reviewer / lead / junior / critic 四种角色，配套评审会话管理评论、Critic 评估、最终报告；这一层引用底层 Team 复用同一套信箱基础设施。

本章**只做**：单进程内的多 Team 协作、进程内与终端复用器双后端、基础协作工具与 Coordinator Mode 工具过滤、代码评审场景化封装。跨进程跨机器分布、其他终端窗格后端、Plan 审批结构化协议、复杂任务依赖图均不在范围。

## 目标- **G1**: 提供 Team 与 Team 管理器抽象——Team 管理一个具名小组的成员、信箱目录、运行模式；管理器在单 gcode 进程内同时管理多个 Team
- **G2**: 提供创建 Team 的工具——主 Agent 调用即创建 Team；同名 Team 直接复用，不报冲突
- **G3**: 提供派遣队员的工具——参数为团队名、队员名、初始任务；Team 不存在时自动创建，然后在后台启动队员；返回提示 Lead「继续工作，结果会从团队渠道回来」
- **G4**: 提供发送消息的工具——参数为团队名、收件人、消息体；调用即写入目标队员信箱，队员在下一轮轮询时被唤醒
- **G5**: 提供列出团队与删除团队的工具——列出当前所有 Team 与成员，或删除某个 Team（删除时把成员标记为非活跃并触发取消）
- **G6**: 提供后端检测函数——默认返回进程内后端；另有探测函数在用户显式要求时根据环境探测终端复用器；不做运行时回退
- **G7**: 提供统一的派遣抽象——把后端差异收敛到一个工厂；进程内后端通过子进程启动，终端复用器后端通过新窗口或新会话启动；其他终端窗格后端在本期被显式拒绝
- **G8**: 提供基于文件的信箱实现——追加写消息文件 + 已读游标文件 + 互斥锁文件，支持发送、同步接收、未读计数、全部标记已读、轮询
- **G9**: 信箱文件锁基于「独占创建」原语——最多重试 10 次、每次 5-100ms 随机抖动、锁文件过期时间 10 秒后视为陈旧并强制抢占；锁等待期间使用同步休眠避免事件循环让步导致竞态
- **G10**: 提供队员进度状态抽象——记录工具调用次数、token 计数、最近若干条工具活动、状态机（运行中 / 空闲 / 已完成 / 失败 / 已停止）
- **G11**: 队员执行循环：跑完一轮任务 → 给 Lead 信箱发 idle 通知 → 每 500ms 轮询自己的信箱直到收到新消息或 shutdown 消息 → 把新消息拼成下一轮的提示继续执行；执行抛错时给 Lead 发失败通知
- **G12**: 队员退出（自然结束、收到 shutdown、被外部停止）时，若有对话上下文则自动持久化到团队目录下的归档文件
- **G13**: 提供 Lead 消息抽取接口——遍历所有 Team，把 Lead 信箱里的未读消息拼成结构化提醒字符串数组返回；TUI 在 Lead 主循环中每轮把这批提醒注入大模型上下文
- **G14**: 提供 Coordinator Mode 工具过滤——当系统中至少存在一个 Team 时，自动收窄 Lead 工具集到协作类与只读类工具白名单（剥夺写类工具）；插件来源工具不受过滤；所有 Team 删除后自动恢复
- **G15**: TUI 状态可视化——单个队员的状态行展示名称、状态、最近工具活动、token 计数；多个队员组成树形 spinner；状态栏显示活跃队员计数；Lead 收到的队员消息按发件人前缀渲染（idle 与 shutdown 静默不渲染、completed 渲染绿色完成标）；按快捷键打开 Teams Dialog 列出所有活跃队员，支持进入详情、强杀、请求关停
- **G16**: 提供独立的「队员进程入口」——以专用命令行参数启动时不渲染 TUI，而是在子进程内构造独立的对话与权限上下文跑初始任务，跑完后持续轮询信箱接续新任务，收到 shutdown 消息时优雅退出
- **G17**: 提供代码评审子系统——评审成员含角色（reviewer / lead / junior / critic）、专业领域、活跃标记；评审管理器在工作目录下持久化团队，每次操作同步到底层 Team；评审会话维护评审请求、评论、Critic 评估、最终报告，支持评审请求创建、评论增删改、Critic 评估、最终报告生成
- **G18**: 提供代码评审 slash 命令——子命令覆盖团队增删改查、成员激活停用、评审请求生命周期、评论审核、Critic 评估、报告输出
- **G19**: 与既有功能协同——既有的子 Agent 派遣路径保持不变；派遣队员工具内部复用既有的子 Agent 启动入口，把每个工具调用与 token 用量事件回灌到队员进度状态；主 Agent 工具未引入「团队名参数」分支，spawn 队员的入口本期仅为派遣队员工具

## 功能需求### Team 数据结构与管理器- **F1**: Team 持有团队名、运行模式、成员表、Lead 信箱与信箱目录、工作目录；构造时自动在工作目录下递归创建团队子目录，并初始化 Lead 信箱
- **F2**: 成员对象持有名称、活跃标记、可选的取消回调、独立信箱、可选的 UI 状态、可选的对话历史
- **F3**: 运行模式为枚举类型——进程内、终端复用器、其他终端（其他终端模式仅作为占位，实际使用时直接拒绝）
- **F4**: 团队对象提供两个常量——空闲轮询间隔（500ms）、关停消息前缀（用于队员识别 shutdown 信号）
- **F5**: Team 添加成员——为该名字创建独立信箱，构造成员对象（初始非活跃），加入成员表并返回
- **F6**: Team 派遣队员——
  1. 添加成员并标记为活跃
  2. 构造队员 UI 状态（名称、所属团队、初始为运行中、零值进度、起始时间、随机选择的 spinner 动词）并挂到成员上
  3. 构造事件回调，把工具调用事件计入工具次数与最近活动、把 token 用量事件累加到 token 计数、把流式文本事件赋值给最近消息
  4. 异步启动主循环：循环跑一次执行 → 把结果写入最近消息 → 状态切换为空闲 → 向 Lead 信箱发送 idle 通知 → 轮询自己的信箱等待下一条提示或 shutdown → 收到 shutdown 或被外部置为非活跃时退出循环
  5. 异常路径：捕获后把状态置为失败，向 Lead 发失败通知
  6. 结束路径：把成员置为非活跃；若仍处于运行中则切换为空闲；若有对话上下文则持久化归档
- **F7**: Team 等待下一条提示或关停的私有方法——在成员活跃期间每 500ms 同步读取一次自己的信箱；空就继续；命中以关停前缀开头的消息时返回「关停」标记；否则把所有消息拼接为按发件人分行的文本，包裹在固定引导语前后返回
- **F8**: Team 发送消息——按收件人名在成员表中查找，调用对应成员的信箱写入；找不到时抛出含团队名与收件人名的错误
- **F9**: Team 停止单个成员 / 停止所有成员——把活跃标记置为非活跃；若当前状态为运行中则切换为「已停止」；调用取消回调；停止所有成员遍历整张成员表
- **F10**: Team 提供查询成员列表、按名查询成员、提取所有有 UI 状态的成员快照等接口

### 团队管理器- **F11**: 管理器持有团队表与工作目录
- **F12**: 创建团队——直接构造 Team 实例并放入团队表；不做同名冲突检测，重复创建会覆盖（但调用方在工具层会先查询再决定是否复用）
- **F13**: 按名查询团队 / 列出所有团队
- **F14**: 删除团队——若存在则先停止所有成员再从表中移除
- **F15**: 提取所有 Team 的全部队员 UI 状态——扁平合并返回
- **F16**: 抽取 Lead 信箱消息——遍历所有 Team，对每个 Team 同步读取一次 Lead 信箱；非空时拼成结构化提醒字符串（带团队名、按发件人分行）加入结果数组

### 后端检测与派遣抽象- **F17**: 默认后端检测函数始终返回进程内模式（不做环境探测），让进度事件直接在同进程内流向 Spinner Tree
- **F18**: 显式的窗格后端探测函数——存在终端复用器会话环境变量时返回终端复用器；否则尝试在 PATH 中查找终端复用器二进制；都不行则退回进程内；仅在用户显式选择窗格模式时调用
- **F19**: 派遣配置含运行模式、可执行命令、命令参数、工作目录、可选环境变量
- **F20**: 派遣队员工厂函数——
  - 进程内模式：以子进程方式启动给定命令；取消时发送终止信号
  - 终端复用器模式：先尝试在已有会话中新开一个窗口，失败后回退到以分离模式新建会话；取消时杀掉对应会话；返回的窗格标识为会话名
  - 其他终端模式：直接抛出「本平台不支持」错误

### 文件信箱- **F21**: 信箱消息为发件人、文本内容、时间戳（ISO 字符串）三个字段的简单结构
- **F22**: 信箱实例持有消息文件路径、已读状态文件路径、上次已读行数
- **F23**: 构造时确保信箱目录存在；初始化文件路径；从已读状态文件中读取游标（文件不存在或解析失败时返回 0）
- **F24**: 发送消息——构造含发件人、文本、当前时间戳的消息，在文件锁保护下追加一行 JSON 到消息文件
- **F25**: 同步接收消息——在文件锁保护下读取整个消息文件按行分割；切出上次已读之后的新行；推进游标；持久化游标；逐行解析（解析失败的行直接跳过）；返回新消息数组
- **F26**: 异步接收 = 异步包装同步接收
- **F27**: 未读计数（不消费） / 全部标记已读（在锁内推进游标到当前末尾并持久化）
- **F28**: 轮询接口——异步生成器，循环异步接收 + 逐条产出 + 间隔休眠

### 文件锁- **F29**: 锁参数常量——最大重试次数 10、陈旧阈值 10 秒、随机抖动下限 5ms、上限 100ms
- **F30**: 获取锁——循环 10 次：尝试以「独占创建」模式打开锁文件，成功则关闭并返回；锁已存在时检查文件修改时间是否超过陈旧阈值，是就强制删除并抢占；其他错误直接抛出；每次失败后用同步休眠 5-100ms 随机抖动（同步休眠是为了不让出事件循环以避免协作式调度下多个获取锁的调用同时进入检测阶段的竞态）
- **F31**: 释放锁 / 锁内执行——锁内执行获取锁后用 try/finally 保护回调，确保释放

### 队员进度状态- **F32**: 进度结构持有工具调用次数、token 计数、最近一次活动、最近活动环形缓冲（容量 5）
- **F33**: 工具活动结构持有工具名、入参、活动描述（如"读取某文件"）
- **F34**: 队员 UI 状态持有名称、所属团队、状态（运行中 / 空闲 / 已完成 / 失败 / 已停止）、进度、起始时间、spinner 动词、可选的最近消息
- **F35**: 创建进度——返回零值
- **F36**: 记录工具调用——递增工具次数；按工具名与入参生成活动描述；构造活动并赋给最近活动；推入环形缓冲，超出容量时弹出最早一项
- **F37**: 记录 token 用量——把输入 + 输出 token 累加到 token 计数
- **F38**: 工具活动描述生成——按工具名分支：文件读 / 文件写 / 文件编辑返回"动词 + 文件路径"；shell 类返回"运行 + 截断到 40 字符的命令"；glob 类返回"搜索 + 模式"；grep 类返回"匹配 + 模式"；其他直接返回工具名
- **F39**: 活动汇总返回最后一条活动的描述；token 格式化把数字格式化为带单位的简写（百万级、千级、原值）

### 归档持久化- **F40**: 提供对话序列化函数——遍历对话历史，把每条消息转成含角色、内容、工具调用、工具结果的归档条目；仅在工具调用或工具结果非空时挂对应字段
- **F41**: 保存归档——在团队目录下递归创建归档子目录；写入以队员名为文件名的 JSON 文件；返回写入路径
- **F42**: 加载归档——文件不存在或解析失败时返回空；其他时候返回归档条目数组

### 协作工具- **F43**: 创建团队工具——名称为创建团队、类别为读、系统工具；必填参数团队名；执行时校验非空，若已存在则返回提示「已存在」（不报错），否则创建并返回成功提示
- **F44**: 派遣队员工具——必填团队名、队员名、初始任务；执行时取目标团队（不存在则自动创建），调用 Team 的派遣队员方法，返回提示「队员已派出，结果将从团队渠道回来，继续工作并留意」
- **F45**: 发送消息工具——必填团队名、收件人、消息体；执行时取团队、调用 Team 的发送消息方法（发件人固定为 lead），捕获错误转为 isError；成功返回「消息已送达」
- **F46**: 列出团队工具——无参数；遍历团队列表，每个团队拼成"团队名 [模式]：成员1（活跃）、成员2..."；无团队时返回「无团队」
- **F47**: 删除团队工具——必填团队名；调用管理器删除并返回成功提示
- **F48**: 上述工具统一实现工具接口——含名称、描述、类别、系统标记、入参 schema、执行入口；类别统一为读、系统标记为是

### Coordinator Mode- **F49**: 协作允许工具白名单——含派遣子 Agent、发送消息、任务增删改查、创建 / 删除 / 列出团队、派遣队员、读文件、glob、grep、shell
- **F50**: 判断单个工具是否在白名单内——直接查表
- **F51**: 工具过滤器构造函数——返回一个谓词：若团队列表为空则放行任意工具；插件来源工具始终放行；否则按白名单判断
- **F52**: 谓词组合——若用户额外的工具过滤器为空仅使用 Coordinator 谓词；否则两者取「与」

### 队员进程入口- **F53**: 命令行参数解析——参数中不包含「队员模式」标记时返回空；否则解析团队目录、队员名、初始任务、可选的协议名；三项必填缺一即返回空
- **F54**: 队员主流程——
  1. 加载配置取出协议（按名查找，缺省取首个）
  2. 探测当前工作目录环境并构造系统提示词
  3. 创建客户端
  4. 注册基础工具（读文件、shell、glob、grep、写文件、编辑文件）到一个新的工具注册表
  5. 构造对话历史、权限检查器（默认接受编辑模式）、文件状态缓存、Agent
  6. 把初始任务加入对话历史，循环消费 Agent 产生的事件
  7. 跑完初始任务后构造自己的信箱与 Lead 信箱，向 Lead 发送 idle 通知
  8. 进入轮询循环：收到以关停前缀开头的消息时打印退出提示并跳出；否则把消息加入对话历史，再跑一轮 Agent，结束后再发 idle 通知
- **F55**: 主入口启动时先检查队员模式参数，命中则跑队员主流程后直接返回，不渲染 TUI

### TUI 集成- **F56**: 应用顶层组件持有团队管理器引用、队员 UI 状态数组、Teams Dialog 是否打开等状态
- **F57**: 启动后注册全部协作工具；派遣队员工具的执行闭包内调用既有的子 Agent 启动入口，并把工具调用与 token 用量事件回灌到队员 UI 状态
- **F58**: 启动一个定时器（500ms 间隔）轮询管理器提取最新队员 UI 状态快照并刷新 TUI 状态，驱动 Spinner Tree 实时更新
- **F59**: Lead 主循环传入 Agent.run 的选项中带上工具过滤器组合（Coordinator 谓词与用户工具过滤器的与）与通知函数（每轮调用一次 Lead 消息抽取接口）
- **F60**: 渲染——主对话 spinner 区域在存在队员时渲染队员 Spinner Tree；状态栏底部渲染活跃队员计数；按快捷键打开 Teams Dialog，对话框内支持进入详情、强杀、请求关停
- **F61**: Lead 收到的队员消息提醒在渲染时解析为发件人、内容、类型三段——idle 与 shutdown 类型静默不渲染；completed 类型渲染绿色完成标；纯文本渲染发件人前缀 + 首行 + 缩进剩余行

### 代码评审子系统- **F62**: 评审成员含名称、邮箱、角色（reviewer / lead / junior / critic）、专业领域列表、活跃标记
- **F63**: 评审团队含名称、成员列表、创建时间、最近活跃时间
- **F64**: 评审管理器构造时持工作目录与底层团队管理器引用，配置文件路径位于工作目录下的代码评审团队 JSON；构造时反序列化加载团队
- **F65**: 创建评审团队——把成员标记为活跃后保存，同时调用底层团队管理器创建同名团队并把每个成员加入底层团队（同步信箱）
- **F66**: 评审成员增删与激活停用、评审团队删除——更新最近活跃时间并写回 JSON；删除时同步删除底层团队（失败忽略）
- **F67**: 评审会话持评审请求表、评审管理器引用、工作目录、评论计数器
- **F68**: 创建评审请求——校验目标团队存在、活跃 reviewer 非空；构造评审请求含唯一 ID、标题、描述、作者、分支、文件列表、待处理状态、时间戳、reviewers、空评论数组
- **F69**: 评论增删改——支持新增评论、接受 / 拒绝 / 解决评论，更新评论的已解决标记、解决方案、作者回复、解决时间，刷新请求的更新时间
- **F70**: 添加 Critic 评估——为指定评论追加一条 Critic 评估，含评论 ID、Critic 名、评估结果、推理过程、时间戳
- **F71**: 最终报告生成 / 格式化 / Critic 总结——按文件聚合评论，输出含评论总数、已接受数、已拒绝数、待处理数、结论、关键发现
- **F72**: 代码评审 slash 命令处理器——按第一个 token 分发到所有子命令（创建团队、添加成员、添加 Critic、移除成员、列出团队、查看团队状态、激活 / 停用成员、创建评审请求、列出请求、新增评论、接受评论、拒绝评论、报告输出、批准请求、拒绝请求、Critic 评估、Critic 总结），返回字符串结果；未识别命令返回帮助文本

### 测试- **F73**: 信箱测试——覆盖未读游标推进、跨实例已读状态持久化、全部标记已读不返回
- **F74**: 团队测试——派遣队员跑完任务后 Lead 信箱含 idle 通知；失败队员发失败通知；所有协作工具的正常路径与必填校验
- **F75**: 代码评审测试——评审管理器与评审会话的增删改查、Critic 评估、报告生成

## 非功能需求- **N1**: 主 Agent 平时（未创建 Team）的工具列表与既有行为完全一致；协作工具始终注册到工具表，但 Coordinator 过滤器在无 Team 时不影响其他工具的可见性
- **N2**: 一旦至少存在一个 Team，Lead 工具集自动收窄到协作允许白名单并集插件来源工具；这是「软强制」，所有 Team 删除后自动恢复
- **N3**: 文件信箱跨进程并发安全——基于锁文件 + 独占创建 + 5-100ms 随机抖动 10 次重试 + 10 秒陈旧抢占
- **N4**: 锁等待期间使用同步休眠（不让出事件循环）——避免协作式调度下多个获取锁调用同时进入检测阶段的竞态
- **N5**: 队员事件回灌进度由事件回调闭包驱动；团队抽象与 Agent 抽象之间通过事件接口解耦，团队侧不直接依赖 Agent 实现
- **N6**: 队员 UI 状态采用值类型对象，TUI 每 500ms 拷贝快照刷新，避免渲染层直接持有可变引用导致的更新丢失
- **N7**: 归档持久化仅在对话上下文非空时调用；失败由 try/catch 静默吞掉，best-effort 不影响队员退出
- **N8**: Lead 消息抽取为消耗性读取——每次调用都推进 Lead 信箱的已读游标；TUI 在主循环每轮调一次即可，不需要额外去重
- **N9**: 与既有功能零破坏——全部测试通过、类型检查无错误
- **N10**: 中文友好——关键路径的内嵌注释中文；TUI 文案保留英文（与渲染库主流风格一致）

## 不做的事

- 跨 gcode 进程的 Team 共享（同一仓库同一时刻只支持一个 gcode 实例操作活跃 Team）
- 跨机器分布式 Team
- 进程内与终端复用器之外的窗格后端（其他终端窗格模式被显式拒绝）
- 队员之间的实时流式通信（走文件追加 + 500ms 轮询，不走 socket）
- 复杂任务依赖约束（优先级、deadline、blocked_by 图）
- 任务自动分配（Lead 与队员都靠大模型推理领任务，系统不做调度）
- 队员的细粒度资源限额（token 上限、超时硬限制）
- Plan 审批的结构化协议（本期没有专门的审批消息类型，Plan 文本就是发送消息工具的消息字段）
- Coordinator Mode 的强锁（feature flag + 环境变量双锁）——本期 Coordinator 谓词由「是否存在 Team」自动决定，不引入额外开关
- Windows 平台特殊适配（终端复用器在 WSL 可用但不保证；本期以 macOS / Linux 为主）
- 跨 Team 寻址（发送消息工具只能在同一 Team 内寻址）
- 队员进程入口与进程内队员的 worktree 隔离（本期队员进程直接使用当前工作目录，不切 worktree）

## 验收标准- **AC1**: 新建团队管理器后，工作目录下不存在团队子目录时由 Team 构造函数自动递归创建；多次构造同名 Team 不报错
- **AC2**: 创建名为 demo 的团队后，工作目录下落地对应子目录，Lead 信箱指向该子目录下的消息文件
- **AC3**: 同名团队再次创建会覆盖前一个 Team；创建团队工具在已有时返回「已存在」提示而不是覆盖（验证调用方契约）
- **AC4**: 默认后端检测始终返回进程内模式；显式窗格探测在终端复用器会话环境变量存在时返回终端复用器模式
- **AC5**: 派遣工厂收到「其他终端模式」时抛出「本平台不支持」错误
- **AC6**: 新建信箱后发一条消息再同步接收返回 1 条；再次接收返回空数组（游标推进）
- **AC7**: 新进程构造同名信箱时能从已读状态文件读到上一进程的游标，不会重读已读消息
- **AC8**: 全部标记已读后未读计数为 0、接收返回空
- **AC9**: 文件锁——故意构造修改时间在 11 秒前的锁文件，新写入方能抢占成功
- **AC10**: 派遣队员后短时间内抽取 Lead 消息能拿到含该队员名且含 idle 标记的字符串
- **AC11**: 执行抛错时，抽取的 Lead 消息含「失败」标记
- **AC12**: 创建团队工具缺名时返回 isError；派遣队员工具仅传团队名时返回 isError（必填校验）
- **AC13**: 发送消息工具收到不存在的团队时返回 isError
- **AC14**: 队员收到以关停前缀开头的消息后退出主循环，活跃标记变为非活跃
- **AC15**: 队员退出时若对话上下文存在，团队归档子目录下落地对应队员的归档文件
- **AC16**: Coordinator 工具过滤器在团队列表为空时对任意工具名返回放行；至少一个团队存在时写文件 / 编辑文件返回拒绝，shell / 派遣子 Agent / 插件来源工具返回放行
- **AC17**: 队员状态行渲染——运行中显示 spinner 动词描述；已完成显示绿色完成标签
- **AC18**: 队员消息渲染——idle 或 shutdown 类型静默不渲染；completed 类型显示「发件人 + 完成标」
- **AC19**: 解析「来自团队 alpha 的 alice 的 idle 消息」返回发件人 alice、类型 idle、内容部分
- **AC20**: 解析「来自团队 alpha 的 carol 的纯文本更新」返回发件人 carol、类型 text、内容部分
- **AC21**: 以队员模式启动并传入团队目录、队员名、初始任务后，跑完任务给团队目录下的 Lead 信箱追加一条来自该队员的 idle 消息
- **AC22**: 队员模式在轮询信箱时收到以关停前缀开头的消息立即跳出，进程退出码为 0
- **AC23**: 评审管理器创建评审团队后落地代码评审团队 JSON，同时底层团队管理器也有同名团队
- **AC24**: 创建评审请求时若活跃 reviewer 数为 0 则抛错；否则返回含全部活跃 reviewer 的评审请求
- **AC25**: 通过 slash 命令创建评审团队后再列出输出含该团队及活跃成员计数
- **AC26**: 通过 slash 命令添加 Critic 评估后 Critic 总结包含评估文本
- **AC27**: 全部测试用例通过——信箱、团队、代码评审三组测试全绿
- **AC28**: 类型检查无错误；启动应用 TUI 正常，按指定快捷键弹出 Teams Dialog
- **AC29**: 端到端——启动应用 → 让大模型创建团队 demo → 派遣队员 alice 执行简单命令 → 状态栏出现「1 名队员」→ 主对话区出现 Spinner Tree → 队员跑完后 Lead 主循环下一轮收到带团队名的 idle 提醒
- **AC30**: 同上场景下，由于已存在 Team，Lead 接下来调用写文件会被 Coordinator 过滤器过滤掉（工具列表里看不到）；调用读文件 / shell / 发送消息正常
```

````markdown
# Agent Team Plan## 技术栈

- 运行时：bun
- 语言：TypeScript 5.x（`tsc --noEmit` 校验）
- TUI：Ink（React 渲染到终端）、ink-spinner、ink-text-input
- LLM SDK：@anthropic-ai/sdk、openai
- MCP：@modelcontextprotocol/sdk
- 配置：js-yaml（`.gcode/config.yaml`）
- 模糊搜索：fuse.js
- 终端样式：chalk
- 测试：bun test
- 入口：`bun run src/main.tsx`

## 架构概览

本章在仓库内引入 `src/teams/` 目录与独立子模块 `src/code-review/`，把 ch13 的「子 Agent 一次性 spawn」扩展为「长期存在的队员 + 文件信箱 + 进度可视化」。整体分四层：

1. **数据模型层**（`src/teams/team.ts`）——`Team`、`TeamManager`、`Member`、`TeamMode` 数据结构与生命周期
2. **存储层**（`src/teams/file-mailbox.ts`、`src/teams/transcript.ts`）——`FileMailbox` 与 `.lock` 文件锁、`.read` 游标；`saveTranscript` / `loadTranscript` 持久化队员对话历史
3. **运行时层**（`src/teams/backend.ts`、`src/teams/progress.ts`、`src/teammate.ts`）——后端检测与 spawn 工厂、`TeammateUIState` 进度状态机、`--teammate` CLI 自治循环
4. **集成层**（`src/teams/tools.ts`、`src/teams/coordinator.ts`、`src/tui/*`、`src/code-review/*`）——5 个工具、Coordinator 工具过滤谓词、TUI Spinner Tree / Teams Dialog / 队员消息组件、代码评审场景化封装

依赖方向（单向）：

```
src/tui/app.tsx ──► src/teams/{team, tools, coordinator, progress, backend}
                       └────► src/teams/file-mailbox
                       └────► src/teams/transcript ──► src/conversation/conversation
src/teammate.ts ──► src/teams/file-mailbox + src/agent/agent
src/code-review/* ──► src/teams/{team, backend}
```

`src/teams/team.ts` 不反向依赖 `src/agent/`——所有「跑一轮 Agent」的能力通过外部传入的 `RunAgent` 闭包注入（依赖反转），让 `team.ts` 可单测且不耦合 LLM 协议。

## 数据流1. **创建 Team**：LLM 调 `TeamCreate(name)` → `TeamCreateTool.execute` → `TeamManager.create(name)` → `new Team(name, "in-process", workDir)` → 构造时 `mkdirSync(<workDir>/.gcode/teams/<name>)` + `leadMailbox = new FileMailbox(...)`
2. **spawn 队员**：LLM 调 `SpawnTeammate(team, name, task)` → `SpawnTeammateTool.execute` → `team = mgr.get(team) ?? mgr.create(team)` → `team.spawnTeammate(name, task, runAgent)` → 内部 `addMember` 构造 `Member { mailbox: FileMailbox }` → 异步主循环
3. **队员主循环**：`runAgent(prompt, onEvent)` 跑一轮 → `lastMessage = result` → `leadMailbox.send(name, "[idle] <name> (reason: available)")` → `waitForNextPromptOrShutdown` 每 500ms 轮询自己的信箱 → 收到非 shutdown 消息后拼成 `"From <from>: <text>"` 包在 `"You have new messages from your team:\n\n"` 前后 → 作为下一轮 `nextPrompt` 继续
4. **Lead 发消息**：LLM 调 `SendMessage(team, to, message)` → `team.sendMessage("lead", to, message)` → `member.mailbox.send("lead", message)` → 写入 `<dir>/<member>.jsonl`
5. **Lead 收消息**：TUI Agent 主循环每轮调 `notificationFn = () => teamMgr.drainLeads()` → `TeamManager.drainLeads` 遍历所有 Team 的 `leadMailbox.receiveSync` → 拼成 `<team-notification team="<name>">\nfrom=<from>: <text>\n</team-notification>` 字符串数组 → 注入到 LLM 输入作为 reminder
6. **进度更新**：队员的 `onEvent` 闭包在每个 `tool_use` / `usage` / `stream_text` 事件触发时更新 `uiState.progress`；TUI `setInterval(500ms)` 拷贝 `teamMgr.getAllTeammateStates()` 到 state，Spinner Tree 重渲染
7. **Coordinator 过滤**：每轮 LLM 请求前 `Agent` 取 `toolFilter` 判断每个工具是否可见；`coordinatorToolFilter` 看到 `teamMgr.list().length > 0` 时收窄到白名单 ∪ `mcp__*`
8. **退出与持久化**：`member.active = false` 触发主循环退出 → `finally` 块若 `member.conversation` 非空调 `saveTranscript` 写 JSON
9. **`--teammate` 子进程**（tmux 后端）：`main.tsx` 解析 `parseTeammateFlags` → `runTeammate(args)` → 跑初始 task → `mailbox.poll(2000)` 等后续消息 → 收到 `[shutdown]` 退出

## 核心数据结构与接口### `TeamMode`

```typescript
export type TeamMode = "in-process" | "tmux" | "iterm";
```

### `Member`

```typescript
export interface Member {
  name: string;
  active: boolean;
  cancel?: () => void;
  mailbox: FileMailbox;
  uiState?: TeammateUIState;
  conversation?: ConversationManager;
}
```

### `Team`

```typescript
export class Team {
  name: string;
  mode: TeamMode;
  members = new Map<string, Member>();
  leadMailbox: FileMailbox;
  private mailboxDir: string;
  private workDir: string;

  static readonly IDLE_POLL_INTERVAL_MS = 500;
  static readonly SHUTDOWN_PREFIX = "[shutdown]";

  constructor(name: string, mode: TeamMode, workDir: string);
  addMember(name: string): Member;
  spawnTeammate(name: string, task: string, runAgent: RunAgent): void;
  sendMessage(from: string, to: string, content: string): Promise<void>;
  stopMember(name: string): Promise<void>;
  stopAll(): Promise<void>;
  listMembers(): Member[];
  getMember(name: string): Member | undefined;
  getTeammateStates(): TeammateUIState[];
  private waitForNextPromptOrShutdown(member: Member): Promise<{ prompt: string; shutdown: boolean }>;
}
```

### `TeamManager`

```typescript
export class TeamManager {
  private teams = new Map<string, Team>();
  private workDir: string;

  constructor(workDir: string);
  create(name: string, mode?: TeamMode): Team;
  get(name: string): Team | undefined;
  list(): Team[];
  delete(name: string): Promise<void>;
  getAllTeammateStates(): TeammateUIState[];
  drainLeads(): string[];
}
```

### `RunAgent` / `AgentEventCallback`

```typescript
export type AgentEventCallback = (event: {
  type: string;
  toolName?: string;
  args?: Record<string, unknown>;
  usage?: { inputTokens: number; outputTokens: number };
  text?: string;
}) => void;

export type RunAgent = (task: string, onEvent?: AgentEventCallback) => Promise<string>;
```

`RunAgent` 是依赖反转的关键接口——`Team` 不知道 LLM、Agent、Provider 长什么样，只接收一个「跑任务返回字符串」的闭包；`tui/app.tsx` 在注册 `SpawnTeammateTool` 时把 `spawnSubAgent(BUILTIN_AGENTS[0], task, ...)` 包成闭包传入。

### `FileMailbox`

```typescript
export interface FileMailMessage {
  from: string;
  text: string;
  timestamp: string;
}

export class FileMailbox {
  private filePath: string;
  private readStatePath: string;
  private lastReadLines: number;

  constructor(dir: string, memberName: string);
  send(from: string, text: string): Promise<void>;
  receiveSync(): FileMailMessage[];
  receive(): Promise<FileMailMessage[]>;
  unreadCount(): number;
  markAllRead(): void;
  poll(intervalMs?: number): AsyncGenerator<FileMailMessage>;
}
```

文件结构：

- `<dir>/<member>.jsonl`：消息追加日志，每行一个 `FileMailMessage` JSON
- `<dir>/<member>.read`：游标文件，存 `lastReadLines` 数字
- `<dir>/<member>.jsonl.lock`：写锁，`openSync(..., "wx")` 独占创建

### `AgentProgress` / `TeammateUIState`

```typescript
export interface ToolActivity {
  toolName: string;
  input: Record<string, unknown>;
  activityDescription: string;
}

export interface AgentProgress {
  toolUseCount: number;
  tokenCount: number;
  lastActivity?: ToolActivity;
  recentActivities: ToolActivity[]; // 最多 5 条
}

export interface TeammateUIState {
  name: string;
  teamName: string;
  status: "running" | "idle" | "completed" | "failed" | "stopped";
  progress: AgentProgress;
  startTime: number;
  spinnerVerb: string;
  lastMessage?: string;
}
```

### `SpawnConfig`

```typescript
export interface SpawnConfig {
  mode: TeamMode;
  command: string;
  args: string[];
  cwd: string;
  env?: Record<string, string>;
}

export function spawnTeammate(config: SpawnConfig): { cancel: () => void; paneId?: string };
```

### Coordinator 谓词

```typescript
export function isCoordinatorTool(name: string): boolean;
export function coordinatorToolFilter(teamMgr: TeamManager): (name: string) => boolean;
```

### Code Review

```typescript
export interface CodeReviewMember {
  name: string;
  email: string;
  role: "reviewer" | "lead" | "junior" | "critic";
  expertise: string[];
  active: boolean;
}

export class CodeReviewManager {
  constructor(workDir: string, teamManager: TeamManager);
  createTeam(name: string, members: Omit<CodeReviewMember, "active">[]): CodeReviewTeam;
  addMember(teamName: string, member: Omit<CodeReviewMember, "active">): void;
  removeMember(teamName: string, memberName: string): void;
  activateMember(teamName: string, memberName: string): void;
  deactivateMember(teamName: string, memberName: string): void;
  deleteTeam(name: string): void;
  getTeam(name: string): CodeReviewTeam | undefined;
  listTeams(): CodeReviewTeam[];
  getActiveReviewers(teamName: string): CodeReviewMember[];
  getTeamSummary(teamName: string): string;
}

export class ReviewSession {
  constructor(workDir: string, manager: CodeReviewManager);
  createReviewRequest(teamName, title, description, author, branch, files): ReviewRequest;
  addComment(requestId, reviewer, content, file?, line?): ReviewComment;
  acceptComment(requestId, commentId, authorResponse?): void;
  rejectComment(requestId, commentId, authorResponse?): void;
  addCriticAssessment(requestId, commentId, criticName, evaluation, reasoning): CriticAssessment;
  generateFinalReport(requestId): ReviewSummary;
  formatFinalReport(summary): string;
}
```

## 模块设计### `src/teams/team.ts`**职责：** `Team` / `TeamManager` / `Member` 数据结构与生命周期；定义 `TeamMode` / `RunAgent` / `AgentEventCallback` 接口；实现队员主循环（`spawnTeammate` 内的异步 IIFE）。
**对外接口：** 上面 `Team` / `TeamManager` 类公开方法；`AgentEventCallback`、`RunAgent`、`Member`、`TeamMode` 类型。
**依赖：** `./file-mailbox.js`、`./backend.js`（`detectBackend`）、`./progress.js`、`./transcript.js`、`../tui/verbs.js`（`randomVerb`）、`../conversation/conversation.js`（仅类型）

### `src/teams/file-mailbox.ts`**职责：** 信箱文件 + 文件锁的读写。
**对外接口：** `FileMailbox` 类、`FileMailMessage` 接口。
**依赖：** Node.js stdlib（`node:fs` / `node:path`）。注意 `acquireLock` 内用 `Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)` 做同步 sleep，避免 `setTimeout` 让出事件循环导致多个锁请求同时进入 stat 阶段。

### `src/teams/backend.ts`**职责：** 后端选择与 spawn 工厂。
**对外接口：** `detectBackend()` / `detectPaneBackend()` / `spawnTeammate(config)` / `SpawnConfig` 接口。
**依赖：** `node:child_process`（`spawn`、`execSync`）。

### `src/teams/progress.ts`**职责：** 队员进度状态机与工具描述生成。
**对外接口：** `AgentProgress` / `ToolActivity` / `TeammateUIState` 接口；`createProgress` / `recordToolUse` / `recordTokens` / `summarizeActivities` / `formatTokens` 函数。
**依赖：** 无。

### `src/teams/transcript.ts`**职责：** 队员对话历史的 JSON 持久化与读取。
**对外接口：** `saveTranscript(workDir, teamName, agentId, conv)` → 路径字符串；`loadTranscript(workDir, teamName, agentId)` → `TranscriptEntry[] | null`。
**依赖：** `node:fs` / `node:path` / `../conversation/conversation.js`（仅类型 `ConversationManager` / `Message` / `ToolUseBlock` / `ToolResultBlock`）。

### `src/teams/tools.ts`**职责：** 5 个工具——`TeamCreateTool` / `SpawnTeammateTool` / `SendMessageTool` / `ListTeamsTool` / `TeamDeleteTool`。
**对外接口：** 5 个 class，全部实现 `Tool` 接口（`src/tools/types.ts`）；构造函数接收 `TeamManager`（`SpawnTeammateTool` 额外接收 `RunAgent`）。
**依赖：** `../tools/types.js`（`Tool` / `ToolResult` / `strArg`）、`./team.js`。

### `src/teams/coordinator.ts`**职责：** Coordinator Mode 的工具白名单与谓词。
**对外接口：** `isCoordinatorTool(name)` / `coordinatorToolFilter(teamMgr)`。
**依赖：** `./team.js`（仅类型 `TeamManager`）。

### `src/teammate.ts`**职责：** `--teammate` CLI 模式入口；为 `tmux` 后端子进程提供独立的「跑初始任务 + 轮询信箱」自治循环。
**对外接口：** `parseTeammateFlags(args: string[]): TeammateArgs | null` / `runTeammate(args: TeammateArgs): Promise<void>`。
**依赖：** `./config/config.js`、`./llm/client.js`、`./conversation/conversation.js`、`./prompt/builder.js`、`./tools/*`、`./permissions/checker.js`、`./agent/agent.js`、`./teams/file-mailbox.js`。

### `src/tui/teammate-message.tsx`**职责：** 把 `<team-notification>` reminder 里的单条消息渲染成 `@<from> ❯ <content>` 块。
**对外接口：** `TeammateMessage({ from, content, type })` 组件、`parseTeammateMessage(raw): { from, content, type } | null`。
**依赖：** `ink`（`Box` / `Text`）、`react`。

### `src/tui/teammate-spinner-line.tsx` & `teammate-spinner-tree.tsx`**职责：** Spinner Tree 视图——`TeammateSpinnerLine` 渲染单个队员的 `name` / `status` / 最近活动 / token 计数；`TeammateSpinnerTree` 把 Lead 与所有队员组成树形 spinner。
**对外接口：** `TeammateSpinnerLine({ state, isLast, isSelected })` / `TeammateSpinnerTree({ teammates, leaderVerb, leaderTokens })`。
**依赖：** `ink`、`react`、`../teams/progress.js`。

### `src/tui/team-status.tsx`**职责：** 状态栏底部 `● N teammate(s)` 计数。
**对外接口：** `TeamStatus({ count })` 组件。
**依赖：** `ink`、`react`。

### `src/tui/teams-dialog.tsx`**职责：** `Ctrl+T` 调出的 Teams Dialog——列表视图 + 详情视图，支持 `↑/↓` 选择、`Enter` 进详情、`k` kill、`s` shutdown。
**对外接口：** `TeamsDialog({ teammates, onClose, onKill, onShutdown })` 组件。
**依赖：** `ink`、`react`、`./styles.js`、`../teams/progress.js`。

### `src/tui/app.tsx`（扩展）**职责：** 整体集成入口。
**变更点：**
- `teamManagerRef = useRef(new TeamManager(workDir))`；`teammateStates` state；`teamsDialogOpen` state
- 启动时注册 5 个 Team 工具到 `registryRef.current`；`SpawnTeammateTool` 的 `RunAgent` 闭包内部调 `spawnSubAgent(BUILTIN_AGENTS[0], task, client, registryRef.current, provider, workDir, undefined, onEvent)`
- `setInterval(500ms)` 拷贝 `teamMgr.getAllTeammateStates()`
- Lead 主循环 `agent.run` 的 options 传 `toolFilter: buildComposedToolFilter(coordinatorToolFilter(teamMgr), skillFilter)` + `notificationFn: () => teamMgr.drainLeads()`
- 渲染 `<TeammateSpinnerTree>`、`<TeamStatus>`、`<TeamsDialog>`（条件渲染）；`useInput` 处理 `Ctrl+T` 切换 dialog

### `src/code-review/manager.ts` / `session.ts` / `handler.ts`**职责：** 代码评审场景化封装，构建在 `TeamManager` 之上。
**对外接口：** `CodeReviewManager` / `ReviewSession` / `handleCodeReviewCommand`。
**依赖：** `../teams/team.js`（`TeamManager` / `Team`）、`../teams/backend.js`（`detectBackend`）、`node:fs` / `node:path`。

### `src/main.tsx`（扩展）**变更点：** 启动前调 `parseTeammateFlags(process.argv.slice(2))`，命中走 `runTeammate(teammateArgs)` 后 `return`，不渲染 TUI。

## 模块交互### 创建 Team → spawn 队员 → 队员循环

```
LLM 调 TeamCreate(name="demo")
  └─► TeamCreateTool.execute
        └─► TeamManager.create("demo")
              └─► new Team("demo", "in-process", workDir)
                    ├─► mkdirSync(<workDir>/.gcode/teams/demo)
                    └─► leadMailbox = new FileMailbox(dir, "lead")

LLM 调 SpawnTeammate(team="demo", name="alice", task="探索 src/agent")
  └─► SpawnTeammateTool.execute
        ├─► team = mgr.get("demo") ?? mgr.create("demo")
        └─► team.spawnTeammate("alice", task, runAgent)
              ├─► addMember("alice") → member.mailbox = new FileMailbox(...)
              ├─► uiState = { status: "running", progress: createProgress(), spinnerVerb }
              ├─► onEvent = (event) => recordToolUse / recordTokens / lastMessage
              └─► void (async () => {
                    while (member.active) {
                      uiState.status = "running"
                      result = await runAgent(nextPrompt, onEvent)
                      uiState.lastMessage = result.slice(0, 200) + "..."
                      uiState.status = "idle"
                      await leadMailbox.send("alice", "[idle] alice (reason: available)")
                      pollResult = await waitForNextPromptOrShutdown(member)
                      if (pollResult.shutdown) break
                      nextPrompt = pollResult.prompt
                    }
                  })()
```

### Lead 端 reminder 注入

```
TUI Agent.run 每轮迭代开头
  └─► notificationFn() ─► teamMgr.drainLeads()
        └─► for each team: team.leadMailbox.receiveSync() → 拼成
            <team-notification team="demo">
            from=alice: [idle] alice (reason: available)
            </team-notification>
  └─► reminders.push(...drainResults)
  └─► 注入到 LLM 输入

LLM 看到 reminder → 决定下一步（派新任务 / 调 SendMessage / 等更多结果）
```

### 工具过滤与 Coordinator Mode

```
Agent.run 每轮迭代前构建 tool list
  └─► registry.getAvailableTools()
        └─► filter (name) => toolFilter(name)
              └─► buildComposedToolFilter(coordinatorFilter, skillFilter)
                    └─► coordinatorFilter(name) && skillFilter(name)

coordinatorFilter(name):
  if (teamMgr.list().length === 0) return true     // 没 Team 时全集
  if (name.startsWith("mcp__")) return true        // MCP 总是允许
  return COORDINATOR_ALLOWED_TOOLS.has(name)        // 否则只允许白名单
```

### Spinner Tree 与状态轮询

```
TUI 启动后:
  setInterval(() => {
    setTeammateStates(teamManagerRef.current.getAllTeammateStates())
  }, 500)

队员主循环里 onEvent("tool_use", { toolName: "ReadFile", args: { file_path } })
  └─► recordToolUse(uiState.progress, "ReadFile", args)
        └─► uiState.progress.lastActivity = { toolName, input, activityDescription: "Reading <file_path>" }

500ms 后 TUI setInterval 触发
  └─► getAllTeammateStates() 返回包含更新后的 uiState 快照
  └─► React 重渲染 TeammateSpinnerTree
        └─► TeammateSpinnerLine 显示 "@alice: Reading src/foo.ts... · 5 tools · 1.2k tokens"
```

### TeamsDialog 与队员控制

```
用户按 Ctrl+T → setTeamsDialogOpen(true)
TeamsDialog 接管 useInput:
  ↑/↓ 选择队员
  Enter → 进入详情视图
  k → onKill(name, teamName) → team.stopMember(name)
       └─► member.active = false; uiState.status = "stopped"; member.cancel?.()
  s → onShutdown(name, teamName) → team.sendMessage("lead", name, "[shutdown] Please finish and exit")
       └─► 队员下一轮 waitForNextPromptOrShutdown 检测到 SHUTDOWN_PREFIX 返回 shutdown:true
       └─► 主循环 break → finally 块持久化 transcript
```

### `--teammate` 子进程（tmux 后端）

```
tmux backend.spawnTeammate 启动 gcode 子进程，命令含 --teammate --team-dir <dir> --member-name alice --task "..."
  └─► main.tsx 检测 parseTeammateFlags 命中
  └─► runTeammate(args)
        ├─► loadConfig + createClient + 注册 6 个工具
        ├─► agent.run 跑初始 task → stdout 打印 stream_text
        ├─► leadMailbox.send("alice", "[idle] alice has completed their task and is waiting for new instructions.")
        └─► for await msg of mailbox.poll(2000):
              if (msg.text.startsWith("[shutdown]")) break
              conv.addUserMessage(msg.text)
              agent.run 跑一轮
              leadMailbox.send("alice", "[idle] ...")
```

### Code Review 子系统

```
用户输入 /code-review create review-A
  └─► handleCodeReviewCommand(ctx, manager, session)
        └─► handleCreate(manager, "review-A")
              └─► CodeReviewManager.createTeam("review-A", [reviewer1, reviewer2, reviewer3])
                    ├─► 写 <workDir>/.gcode/code-review-teams.json
                    └─► 调底层 TeamManager.create("review-A", "in-process")
                          + 对每个 reviewer 调 team.addMember(name) 创建信箱

用户输入 /code-review request review-A "fix bug" "details"
  └─► handleCreateRequest(session, "review-A fix bug details")
        └─► session.createReviewRequest("review-A", "fix bug", "details", "current-user", "main", ["src/"])

用户输入 /code-review comment <reqId> "this looks off"
  └─► session.addComment(reqId, "current-user", "this looks off")

用户输入 /code-review critic <reqId> <commentId> reasonable "good catch"
  └─► session.addCriticAssessment(reqId, commentId, "critic-1", "reasonable", "good catch")

用户输入 /code-review report <reqId>
  └─► summary = session.generateFinalReport(reqId)
  └─► session.formatFinalReport(summary) → 字符串
```

## 文件组织

```text
src/
├── main.tsx                            修改：parseTeammateFlags + runTeammate 分支
├── teammate.ts                         新建：--teammate CLI 自治循环
├── teams/
│   ├── team.ts                         新建：Team / TeamManager / Member / RunAgent
│   ├── file-mailbox.ts                 新建：FileMailbox + acquireLock + withLock
│   ├── backend.ts                      新建：detectBackend / detectPaneBackend / spawnTeammate
│   ├── progress.ts                     新建：TeammateUIState / AgentProgress / 工具描述
│   ├── transcript.ts                   新建：saveTranscript / loadTranscript
│   ├── tools.ts                        新建：5 个工具
│   └── coordinator.ts                  新建：COORDINATOR_ALLOWED_TOOLS + coordinatorToolFilter
├── code-review/
│   ├── manager.ts                      新建：CodeReviewManager
│   ├── session.ts                      新建：ReviewSession + ReviewRequest / Comment / CriticAssessment / Summary
│   └── handler.ts                      新建：/code-review slash 命令分发
└── tui/
    ├── app.tsx                         修改：注册 5 工具 + Spinner Tree + TeamStatus + TeamsDialog + 过滤器
    ├── team-status.tsx                 新建：状态栏 ● N teammates
    ├── teams-dialog.tsx                新建：Ctrl+T 弹出的对话框
    ├── teammate-message.tsx            新建：parseTeammateMessage + @name❯ 渲染
    ├── teammate-spinner-line.tsx       新建：单个队员行
    └── teammate-spinner-tree.tsx       新建：Lead + 队员的树形 spinner

tests/
├── file-mailbox.test.ts                新建：游标、跨实例、markAllRead
├── teams.test.ts                       新建：spawnTeammate + 5 工具
└── code-review.test.ts                 新建：Manager / Session CRUD

examples/
├── create-code-review-team.ts          新建：示例脚本
└── create-custom-team.ts               新建：示例脚本
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Team 包归属 | `src/teams/` 顶层目录 | 与 `src/agents/`、`src/worktree/` 平级，职责清晰 |
| 队员生命周期 | 长存活循环（跑完一轮等下条消息）而非一次性 spawn | 让 Lead 可以多轮派任务给同一队员，复用对话上下文 |
| 默认后端 | `detectBackend()` 直接返回 `"in-process"` | 同进程让 `onEvent` 直接更新 Spinner Tree，UX 最佳；tmux 仅在用户显式配置时启用 |
| `RunAgent` 注入 | 用 `(task, onEvent) => Promise<string>` 闭包，由 `app.tsx` 注入 | 让 `team.ts` 与 `Agent` / `LLMClient` 解耦，单测可用假 `runAgent` |
| 信箱协议 | `.jsonl` 追加 + `.read` 游标 + `.lock` 互斥锁 | 跨进程友好；游标持久化让重启的子进程不会重读已读消息 |
| 锁实现 | `openSync(lockFile, "wx")` 独占创建 + `Atomics.wait` 同步 sleep | `wx` 是 fs 原语级原子，无 race；`Atomics.wait` 避免事件循环让步导致多锁同时进入 stat 阶段 |
| 锁参数 | 10 次重试、5-100ms 随机抖动、10 秒 stale | 与同套信箱协议的其他语言实现保持一致，方便混布 |
| Lead 收信 | TUI 主循环每轮调 `drainLeads()` 注入 reminder | 不引入 watcher 线程；`drainLeads` 本身是消耗读，自带游标 |
| Coordinator 触发 | 「存在至少一个 Team」自动启用 | 不引入 feature flag 或环境变量；语义直观：Lead 一旦开始组队，就转入 Coordinator 模式 |
| Coordinator 工具白名单 | 静态 `Set<string>` 常量 | 编辑器可静态分析；新增工具时强制 review |
| MCP 工具豁免 | `name.startsWith("mcp__")` 直接放行 | MCP 服务器由用户配置，应该尊重；不让 Coordinator 谓词把 MCP 全杀 |
| 进度状态轮询 | `setInterval(500ms)` 在 TUI 层快照 | React 状态需要不可变快照；轮询 + 拷贝最简单 |
| Spinner Verb 多样化 | `randomVerb()` 给每个队员配独立动词 | 视觉上区分多个并行队员，UX 借鉴 Claude Code 风格 |
| Transcript 时机 | 队员 `finally` 块持久化，best-effort | 任何退出路径（自然、失败、shutdown、stopMember）都覆盖；持久化失败不阻塞退出 |
| `--teammate` 模式 | `main.tsx` 检测 flag 不构造 TUI，直接跑自治循环 | tmux 子进程没有 TUI 也无法响应；保持单二进制部署 |
| Code Review 复用 Team | `CodeReviewManager` 持有 `TeamManager` 引用并双写 | 评审场景的「评论 / Critic / Report」是上层语义；底层的信箱、状态可视化、`Coordinator` 直接复用 |
| Critic 角色独立枚举 | `role: "critic"` 与 reviewer / lead / junior 并列 | 评审场景需要「评估评审者意见」的元角色；不混入 reviewer |
| 评论与请求 ID | `comment-<ts>-<counter>` / `review-<ts>` | 时间戳 + 计数器够单进程内唯一；不引入 uuid 依赖 |
| `TeamCreateTool` 已存在策略 | 返回提示「already exists」而非报错 | LLM 多次调用 `TeamCreate` 是常见行为；幂等 UX 更友好 |
| `SpawnTeammate` 自动 create Team | `mgr.get(team) ?? mgr.create(team)` | LLM 经常省略 `TeamCreate` 直接 spawn；自动 create 降低交互成本 |
| 队员失败语义 | 仅给 Lead 发 `[idle] <name> (reason: failed)` 通知，不抛出 | LLM 通过 reminder 看到 `failed` 字段决定怎么补救；不打断 Lead 的主循环 |
| 错误命名 | `Error("Member '<x>' not found in team '<y>'")` 等 | 字符串错误信息直接展示给 LLM，便于诊断；不引入自定义错误类 |
````

````markdown
# Agent Team Tasks

> 本章在 `src/teams/`、`src/code-review/`、`src/teammate.ts` 与 `src/tui/*` 落地多 Team 协作能力；运行时为 bun + TypeScript 5.x，构建命令 `bun run src/main.tsx`、测试 `bun test`、类型检查 `tsc --noEmit`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/teams/file-mailbox.ts` | `FileMailbox` 类、`acquireLock` / `withLock` 文件锁 |
| 新建 | `src/teams/progress.ts` | `TeammateUIState` / `AgentProgress` / 工具描述生成 |
| 新建 | `src/teams/transcript.ts` | `saveTranscript` / `loadTranscript` 队员对话历史持久化 |
| 新建 | `src/teams/backend.ts` | `detectBackend` / `detectPaneBackend` / `spawnTeammate(SpawnConfig)` |
| 新建 | `src/teams/team.ts` | `Team` / `TeamManager` / `Member` / `RunAgent` / `AgentEventCallback` |
| 新建 | `src/teams/tools.ts` | `TeamCreateTool` / `SpawnTeammateTool` / `SendMessageTool` / `ListTeamsTool` / `TeamDeleteTool` |
| 新建 | `src/teams/coordinator.ts` | `COORDINATOR_ALLOWED_TOOLS` / `isCoordinatorTool` / `coordinatorToolFilter` |
| 新建 | `src/teammate.ts` | `parseTeammateFlags` / `runTeammate` — `--teammate` CLI 模式 |
| 新建 | `src/tui/team-status.tsx` | 状态栏 `● N teammates` |
| 新建 | `src/tui/teammate-message.tsx` | `parseTeammateMessage` + `TeammateMessage` 组件 |
| 新建 | `src/tui/teammate-spinner-line.tsx` | 单个队员 spinner 行 |
| 新建 | `src/tui/teammate-spinner-tree.tsx` | Lead + 队员的树形 spinner |
| 新建 | `src/tui/teams-dialog.tsx` | `Ctrl+T` 弹出的 Teams Dialog |
| 修改 | `src/tui/app.tsx` | 注册 5 工具、Spinner Tree、TeamStatus、TeamsDialog、Coordinator 过滤器 |
| 修改 | `src/main.tsx` | `parseTeammateFlags` 命中走 `runTeammate` 分支 |
| 新建 | `src/code-review/manager.ts` | `CodeReviewManager` |
| 新建 | `src/code-review/session.ts` | `ReviewSession` / `ReviewRequest` / `ReviewComment` / `CriticAssessment` / `ReviewSummary` |
| 新建 | `src/code-review/handler.ts` | `/code-review` slash 命令分发 |
| 新建 | `tests/file-mailbox.test.ts` | `FileMailbox` 单测 |
| 新建 | `tests/teams.test.ts` | `Team` / `TeamManager` / 5 工具单测 |
| 新建 | `tests/code-review.test.ts` | `CodeReviewManager` / `ReviewSession` 单测 |
| 新建 | `examples/create-code-review-team.ts` | 评审 team 示例脚本 |
| 新建 | `examples/create-custom-team.ts` | 自定义 team 示例脚本 |

## T1: 文件锁基础 — `src/teams/file-mailbox.ts`（锁部分）**文件：** `src/teams/file-mailbox.ts`
**依赖：** Node.js stdlib `node:fs`
**步骤：**
1. 顶部 `import { readFileSync, writeFileSync, mkdirSync, existsSync, unlinkSync, statSync, openSync, closeSync } from "node:fs"; import { join } from "node:path";`
2. 定义常量 `LOCK_MAX_ATTEMPTS = 10` / `LOCK_STALE_MS = 10_000` / `LOCK_RETRY_MIN_MS = 5` / `LOCK_RETRY_MAX_MS = 100`
3. 实现 `sleepSync(ms: number): void`——用 `Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)` 阻塞当前事件循环，避免让出导致多个锁请求同时进入 stat
4. 实现 `acquireLock(lockFile: string): void`：
   - `for (let attempt = 0; attempt < LOCK_MAX_ATTEMPTS; attempt++)`
   - try `openSync(lockFile, "wx")` 成功 → `closeSync(fd)` return
   - catch：若 `code === "EEXIST"`：`statSync(lockFile)` 看 `Date.now() - info.mtimeMs > LOCK_STALE_MS` 则 `unlinkSync(lockFile)`（失败静默）
   - 非 `EEXIST` 错误直接 throw
   - 延迟 `LOCK_RETRY_MIN_MS + Math.floor(Math.random() * (LOCK_RETRY_MAX_MS - LOCK_RETRY_MIN_MS + 1))` 毫秒后重试
   - 10 次都失败 throw `lastErr`
5. 实现 `releaseLock(lockFile: string): void`——`try { unlinkSync(lockFile) } catch {}`
6. 实现 `withLock<T>(filePath: string, fn: () => T): T`——`const lockFile = filePath + ".lock"; acquireLock(lockFile); try { return fn() } finally { releaseLock(lockFile) }`

**验证：** `tsc --noEmit` 通过；锁函数为内部 helper，由 T2 间接覆盖

## T2: `FileMailbox` 主体 — 继续 `src/teams/file-mailbox.ts`**文件：** `src/teams/file-mailbox.ts`
**依赖：** T1
**步骤：**
1. 定义 `export interface FileMailMessage { from: string; text: string; timestamp: string }`
2. 定义 `export class FileMailbox`，私有字段 `filePath` / `readStatePath` / `lastReadLines`
3. 构造函数 `constructor(dir: string, memberName: string)`——`mkdirSync(dir, {recursive:true})`；`filePath = join(dir, memberName + ".jsonl")`；`readStatePath = join(dir, memberName + ".read")`；`lastReadLines = this.loadReadState()`
4. 私有 `loadReadState(): number`——try `parseInt(readFileSync(readStatePath, "utf-8").trim(), 10) || 0`；catch 返回 0
5. 私有 `saveReadState(): void`——try `writeFileSync(readStatePath, String(lastReadLines), "utf-8")`；catch 静默
6. 私有 `allLines(): string[]`——`!existsSync(filePath)` 返回 `[]`；否则 `readFileSync(filePath, "utf-8").trim().split("\n").filter(Boolean)`
7. `async send(from: string, text: string): Promise<void>`——构造 `msg: FileMailMessage = { from, text, timestamp: new Date().toISOString() }`；`withLock(filePath, () => { writeFileSync(filePath, JSON.stringify(msg) + "\n", { flag: "a", encoding: "utf-8" }) })`
8. `receiveSync(): FileMailMessage[]`——在 `withLock(filePath, ...)` 内：`const lines = this.allLines(); const newLines = lines.slice(this.lastReadLines); this.lastReadLines = lines.length; this.saveReadState();`；逐行 `JSON.parse`（catch 静默跳过 malformed 行）；返回结果数组
9. `async receive(): Promise<FileMailMessage[]>` —— 直接 `return this.receiveSync()`
10. `unreadCount(): number` —— `Math.max(0, this.allLines().length - this.lastReadLines)`
11. `markAllRead(): void` —— `withLock(filePath, () => { this.lastReadLines = this.allLines().length; this.saveReadState() })`
12. `async *poll(intervalMs = 1000): AsyncGenerator<FileMailMessage>` —— `while (true) { const msgs = await this.receive(); for (const m of msgs) yield m; await new Promise(r => setTimeout(r, intervalMs)) }`

**验证：** 写一段 ad-hoc 脚本：`new FileMailbox(tmpDir, "alice")` → `send("lead", "hi")` → `receiveSync()` 返回 1 条；再调返回空；新实例的 `unreadCount()` 反映持久化的游标

## T3: 进度状态 — `src/teams/progress.ts`**文件：** `src/teams/progress.ts`
**依赖：** 无
**步骤：**
1. 定义 `export interface ToolActivity { toolName: string; input: Record<string, unknown>; activityDescription: string }`
2. 定义 `export interface AgentProgress { toolUseCount: number; tokenCount: number; lastActivity?: ToolActivity; recentActivities: ToolActivity[] }`
3. 定义 `export interface TeammateUIState { name: string; teamName: string; status: "running" | "idle" | "completed" | "failed" | "stopped"; progress: AgentProgress; startTime: number; spinnerVerb: string; lastMessage?: string }`
4. 实现 `export function createProgress(): AgentProgress` —— 返回零值 `{ toolUseCount: 0, tokenCount: 0, lastActivity: undefined, recentActivities: [] }`
5. 实现 `export function recordToolUse(p: AgentProgress, toolName: string, input: Record<string, unknown>): void`：
   - `p.toolUseCount++`
   - `const desc = describeToolActivity(toolName, input)`
   - `const activity: ToolActivity = { toolName, input, activityDescription: desc }`
   - `p.lastActivity = activity; p.recentActivities.push(activity); if (p.recentActivities.length > 5) p.recentActivities.shift()`
6. 实现 `export function recordTokens(p: AgentProgress, inputTokens: number, outputTokens: number): void` —— `p.tokenCount = inputTokens + outputTokens`
7. 实现私有 `describeToolActivity(toolName, input): string`：
   - `ReadFile` → `"Reading " + (input.file_path ?? "file")`
   - `EditFile` → `"Editing " + (input.file_path ?? "file")`
   - `WriteFile` → `"Writing " + (input.file_path ?? "file")`
   - `Bash` → `const cmd = String(input.command ?? ""); return "Running " + (cmd.length > 40 ? cmd.slice(0, 40) + "..." : cmd)`
   - `Glob` → `"Searching " + (input.pattern ?? "files")`
   - `Grep` → `"Grepping " + (input.pattern ?? "pattern")`
   - default → `toolName`
8. 实现 `export function summarizeActivities(activities: ToolActivity[]): string` —— 空返空；否则 `activities[activities.length - 1]!.activityDescription`
9. 实现 `export function formatTokens(n: number): string`：`>= 1e6` → `(n/1e6).toFixed(1) + "M"`；`>= 1e3` → `(n/1e3).toFixed(1) + "k"`；否则 `String(n)`

**验证：** `tsc --noEmit` 通过

## T4: 后端工厂 — `src/teams/backend.ts`**文件：** `src/teams/backend.ts`
**依赖：** 无（依赖 `node:child_process`）
**步骤：**
1. `import { execSync, spawn } from "node:child_process"; import type { TeamMode } from "./team.js";`（注意：`team.ts` 还没建，先用 type-only import；T5 建完后类型可用）
2. 实现 `export function detectBackend(): TeamMode` —— 直接 `return "in-process"`
3. 实现 `export function detectPaneBackend(): TeamMode`：
   - `process.env.TMUX` 非空 → `return "tmux"`
   - try `execSync("which tmux", { stdio: ["pipe","pipe","pipe"] })` 成功 → `return "tmux"`
   - catch → `return "in-process"`
4. 定义 `export interface SpawnConfig { mode: TeamMode; command: string; args: string[]; cwd: string; env?: Record<string, string> }`
5. 实现 `export function spawnTeammate(config: SpawnConfig): { cancel: () => void; paneId?: string }`：
   - `case "in-process":`
     - `const child = spawn(config.command, config.args, { cwd: config.cwd, stdio: ["pipe","pipe","pipe"], env: {...process.env, ...config.env} })`
     - return `{ cancel: () => child.kill("SIGTERM") }`
   - `case "tmux":`
     - `const sessionName = "gcode-" + Date.now().toString(36)`
     - `const cmd = [config.command, ...config.args].join(" ")`
     - try `execSync(\`tmux new-window -t "${sessionName}" -n teammate "${cmd}"\`, ...)`；catch 回退 `execSync(\`tmux new-session -d -s "${sessionName}" -n teammate "${cmd}"\`, ...)`
     - return `{ cancel: () => { try { execSync(\`tmux kill-session -t "${sessionName}"\`) } catch {} }, paneId: sessionName }`
   - `case "iterm":` throw `Error("iTerm backend not supported on this platform")`
   - default throw `Error(\`Unknown team mode: ${config.mode}\`)`

**验证：** `tsc --noEmit` 通过；`detectBackend()` 应返回 `"in-process"`

## T5: Team / TeamManager — `src/teams/team.ts`**文件：** `src/teams/team.ts`
**依赖：** T1-T4
**步骤：**
1. import `join` from `node:path`、`mkdirSync` from `node:fs`、`FileMailbox` from `./file-mailbox.js`、`detectBackend` from `./backend.js`、`TeammateUIState` / `createProgress` / `recordToolUse` / `recordTokens` from `./progress.js`、`randomVerb` from `../tui/verbs.js`、`ConversationManager` from `../conversation/conversation.js`（type-only）、`saveTranscript` from `./transcript.js`
2. 定义 `export type TeamMode = "in-process" | "tmux" | "iterm"`
3. 定义 `export type AgentEventCallback = (event: { type: string; toolName?: string; args?: Record<string, unknown>; usage?: { inputTokens: number; outputTokens: number }; text?: string }) => void`
4. 定义 `export interface Member { name: string; active: boolean; cancel?: () => void; mailbox: FileMailbox; uiState?: TeammateUIState; conversation?: ConversationManager }`
5. 定义 `export type RunAgent = (task: string, onEvent?: AgentEventCallback) => Promise<string>`
6. 定义 `export class Team`：
   - 字段 `name: string; mode: TeamMode; members = new Map<string, Member>(); leadMailbox: FileMailbox; private mailboxDir: string; private workDir: string`
   - 静态 `static readonly IDLE_POLL_INTERVAL_MS = 500` / `static readonly SHUTDOWN_PREFIX = "[shutdown]"`
   - 构造 `constructor(name, mode, workDir)`——保存字段；`this.mailboxDir = join(workDir, ".gcode", "teams", name)`；`mkdirSync(mailboxDir, {recursive:true})`；`this.leadMailbox = new FileMailbox(mailboxDir, "lead")`
   - `addMember(name): Member` —— `const mailbox = new FileMailbox(this.mailboxDir, name)`；`const member: Member = { name, active: false, mailbox }`；`this.members.set(name, member)`；`return member`
   - `spawnTeammate(name, task, runAgent): void`：
     1. `const member = this.addMember(name); member.active = true`
     2. 构造 `uiState: TeammateUIState`，挂 `member.uiState = uiState`
     3. 构造 `onEvent: AgentEventCallback` —— `switch event.type` 三个 case 更新 progress / lastMessage
     4. `void (async () => { let nextPrompt = task; let idleReason = "available"; try { while (member.active) { uiState.status = "running"; const result = await runAgent(nextPrompt, onEvent); uiState.lastMessage = result.length > 200 ? result.slice(0,200)+"..." : result; uiState.status = "idle"; await this.leadMailbox.send(name, \`[idle] ${name} (reason: ${idleReason})\`); idleReason = "available"; const pollResult = await this.waitForNextPromptOrShutdown(member); if (pollResult.shutdown || !member.active) break; nextPrompt = pollResult.prompt } uiState.status = "completed" } catch (e) { uiState.status = "failed"; uiState.lastMessage = (e as Error).message; await this.leadMailbox.send(name, \`[idle] ${name} (reason: failed)\`) } finally { member.active = false; if (uiState.status === "running") uiState.status = "idle"; if (member.conversation) { try { saveTranscript(this.workDir, this.name, name, member.conversation) } catch {} } } })()`
   - 私有 `async waitForNextPromptOrShutdown(member): Promise<{ prompt: string; shutdown: boolean }>` —— `while (member.active) { await new Promise(r => setTimeout(r, Team.IDLE_POLL_INTERVAL_MS)); const msgs = member.mailbox.receiveSync(); if (msgs.length === 0) continue; const hasShutdown = msgs.some(m => m.text.trimStart().startsWith(Team.SHUTDOWN_PREFIX)); if (hasShutdown) return { prompt: "", shutdown: true }; const prompt = msgs.map(m => \`From ${m.from}: ${m.text}\`).join("\n\n"); return { prompt: \`You have new messages from your team:\n\n${prompt}\`, shutdown: false } } return { prompt: "", shutdown: true }`
   - `getMember(name)` / `async sendMessage(from, to, content)` / `async stopMember(name)` / `async stopAll()` / `listMembers()` / `getTeammateStates()` 按 spec.md F8-F10 实现
7. 定义 `export class TeamManager`：
   - 字段 `private teams = new Map<string, Team>(); private workDir: string`
   - 构造 `constructor(workDir: string)`
   - `create(name, mode = detectBackend()): Team` —— `const team = new Team(name, mode, this.workDir); this.teams.set(name, team); return team`
   - `get(name): Team | undefined` / `list(): Team[]` / `async delete(name): Promise<void>`（先 `team.stopAll()` 再 `teams.delete(name)`）
   - `getAllTeammateStates(): TeammateUIState[]` —— `this.list().flatMap(t => t.getTeammateStates())`
   - `drainLeads(): string[]` —— 遍历所有 team，`msgs = team.leadMailbox.receiveSync()`，非空时拼 `<team-notification team="<name>">\nfrom=<from>: <text>\n...\n</team-notification>` push 到 out 数组

**验证：** `tsc --noEmit` 通过；`new TeamManager(workDir).create("demo")` 在 `<workDir>/.gcode/teams/demo/` 创建目录

## T6: Transcript 持久化 — `src/teams/transcript.ts`**文件：** `src/teams/transcript.ts`
**依赖：** `src/conversation/conversation.ts`（仅类型）
**步骤：**
1. import `mkdirSync` / `readFileSync` / `writeFileSync` / `existsSync` from `node:fs`、`join` from `node:path`、类型 `ConversationManager` / `Message` / `ToolUseBlock` / `ToolResultBlock` from `../conversation/conversation.js`
2. 定义内部接口 `TranscriptToolUse { tool_use_id: string; tool_name: string; arguments?: Record<string, unknown> }` / `TranscriptToolResult { tool_use_id: string; content: string; is_error?: boolean }` / `TranscriptEntry { role: string; content?: string; tool_uses?: TranscriptToolUse[]; tool_results?: TranscriptToolResult[] }`
3. 实现私有 `serializeConversation(conv): TranscriptEntry[]` —— 遍历 `conv.getMessages()`，构造 `entry: TranscriptEntry`；若 `msg.toolUses?.length > 0` 映射成 `tool_uses`；若 `msg.toolResults?.length > 0` 映射成 `tool_results`
4. 实现私有 `transcriptDir(workDir, teamName): string` —— `join(workDir, ".gcode", "teams", teamName, "transcripts")`
5. `export function saveTranscript(workDir, teamName, agentId, conv): string` —— `mkdirSync(dir, {recursive:true})`；`writeFileSync(<dir>/<agentId>.json, JSON.stringify(data, null, 2), "utf-8")`；返回路径
6. `export function loadTranscript(workDir, teamName, agentId): TranscriptEntry[] | null` —— 文件不存在 return null；try `JSON.parse(readFileSync)`；catch return null

**验证：** `tsc --noEmit` 通过

## T7: Coordinator 过滤器 — `src/teams/coordinator.ts`**文件：** `src/teams/coordinator.ts`
**依赖：** T5
**步骤：**
1. import `TeamManager` from `./team.js`（仅类型）
2. 定义 `const COORDINATOR_ALLOWED_TOOLS = new Set([...])` —— 包含 `Agent` / `SendMessage` / `TaskCreate` / `TaskGet` / `TaskList` / `TaskUpdate` / `TeamCreate` / `TeamDelete` / `ListTeams` / `SpawnTeammate` / `ReadFile` / `Glob` / `Grep` / `Bash`
3. `export function isCoordinatorTool(name: string): boolean` —— `COORDINATOR_ALLOWED_TOOLS.has(name)`
4. `export function coordinatorToolFilter(teamMgr: TeamManager): (name: string) => boolean`：
   - 返回 `(name) => { if (teamMgr.list().length === 0) return true; if (name.startsWith("mcp__")) return true; return isCoordinatorTool(name) }`

**验证：** `tsc --noEmit` 通过

## T8: 5 个工具 — `src/teams/tools.ts`**文件：** `src/teams/tools.ts`
**依赖：** T5
**步骤：**
1. import `Tool` / `ToolResult` from `../tools/types.js`、`strArg` from `../tools/types.js`、`TeamManager` / `RunAgent` from `./team.js`
2. 定义 helper `function obj(props, required): Record<string, unknown> { return { type: "object", properties: props, required } }`
3. `TeamCreateTool`：实现 `Tool`；`name = "TeamCreate"` / `description = "Create a team for coordinating multiple agents."` / `category = "read" as const` / `system = true`；构造 `constructor(private mgr: TeamManager)`；`schema()` 返回 `{ name, description, input_schema: obj({ name: { type: "string", description: "Team name" } }, ["name"]) }`；`async execute(args)`：取 `name = strArg(args, "name")`，空返 `isError: true`；`mgr.get(name)` 存在 → `"Team 'X' already exists."`；否则 `mgr.create(name)` → `"Team 'X' created."`
4. `SpawnTeammateTool`：构造 `constructor(private mgr: TeamManager, private runAgent: RunAgent)`；`name = "SpawnTeammate"`；input_schema `{ team, name, task }` 全必填；execute 取三参数，校验非空；`const t = this.mgr.get(team) ?? this.mgr.create(team); t.spawnTeammate(name, task, this.runAgent);` 返回提示「continue working and watch for it」
5. `SendMessageTool`：构造 `constructor(private mgr: TeamManager)`；`name = "SendMessage"`；input_schema `{ team, to, message }` 全必填；execute 取 Team，try `t.sendMessage("lead", to, message)`，catch 转 `isError: true`
6. `ListTeamsTool`：`name = "ListTeams"`；无参数 schema；execute 遍历 `mgr.list()`，每个拼 `<name> [<mode>]: <members>`，空则 `"No teams."`
7. `TeamDeleteTool`：`name = "TeamDelete"`；schema `{ name }` 必填；execute 调 `mgr.delete(name)`，返回 `"Team 'X' deleted."`
8. 所有工具 `category = "read" as const; system = true`

**验证：** `tsc --noEmit` 通过；5 个类都能实例化

## T9: `--teammate` CLI 模式 — `src/teammate.ts`**文件：** `src/teammate.ts`
**依赖：** T2、`src/agent/agent.ts`、`src/conversation/conversation.ts`、`src/tools/*`、`src/llm/client.ts`、`src/prompt/builder.ts`、`src/permissions/checker.ts`、`src/config/config.ts`
**步骤：**
1. import `loadConfig` / `createClient` / `ConversationManager` / `buildSystemPrompt` / `detectEnvironment` / 5 个工具类 / `PermissionChecker` / `Agent` / `FileStateCache` / `FileMailbox` / `FileMailMessage`
2. 定义内部 `interface TeammateArgs { teamDir: string; memberName: string; initialTask: string; providerName?: string }`
3. `export function parseTeammateFlags(args: string[]): TeammateArgs | null`：
   - `if (!args.includes("--teammate")) return null`
   - 循环解析 `--team-dir <dir>` / `--member-name <name>` / `--task <task>` / `--provider <name>`
   - 三必填缺一返回 null
4. 定义常量 `ShutdownPrefix = "[shutdown]"` / `LeadName = "lead"`；helper `isShutdownRequest(msg)` 与 `createIdleNotification(name)`
5. `export async function runTeammate(args)`：
   1. `const cfg = loadConfig()`
   2. `const provider = args.providerName ? cfg.providers.find(p => p.name === args.providerName) ?? cfg.providers[0] : cfg.providers[0]`
   3. `const env = detectEnvironment(process.cwd()); env.model = provider.model; const systemPrompt = buildSystemPrompt(env)`
   4. `const client = await createClient(provider, systemPrompt)`
   5. `const registry = new ToolRegistry()`，注册 `ReadFileTool / BashTool / GlobTool / GrepTool / WriteFileTool / EditFileTool`
   6. `const conv = new ConversationManager(); const checker = new PermissionChecker(process.cwd(), "acceptEdits"); const agent = new Agent({ client, registry, checker, conversation: conv, workDir: process.cwd(), fileStateCache: new FileStateCache() })`
   7. `conv.addUserMessage(args.initialTask)`；`for await (const event of agent.run())` 处理 `stream_text` → stdout / `tool_result` → 简短 log / `loop_complete` / `error`
   8. 跑完构造 `mailbox = new FileMailbox(args.teamDir, args.memberName); leadMailbox = new FileMailbox(args.teamDir, LeadName)`；发 `[idle]` 通知
   9. `for await (const msg of mailbox.poll(2000))`：若 `isShutdownRequest(msg)` 打印「Shutdown requested」并 break；否则 `conv.addUserMessage(msg.text)`，再跑一轮，再发 `[idle]`

**验证：** `tsc --noEmit` 通过；ad-hoc `bun run src/main.tsx --teammate --team-dir /tmp/t --member-name a --task "echo hi"` 启动后能跑完任务

## T10: `main.tsx` 接入 — `src/main.tsx`**文件：** `src/main.tsx`（修改）
**依赖：** T9
**步骤：**
1. 顶部 import `parseTeammateFlags, runTeammate` from `./teammate.js`
2. `main()` 函数开头：`const args = process.argv.slice(2); const teammateArgs = parseTeammateFlags(args); if (teammateArgs) { try { await runTeammate(teammateArgs) } catch (err) { console.error(\`teammate: ${(err as Error).message}\`); process.exit(1) } return }`
3. 之后才走原本的 `loadConfig` + `render(<App ... />)`

**验证：** `bun run src/main.tsx --teammate --team-dir /tmp/t --member-name a --task "echo hi"` 不渲染 TUI 直接跑 teammate 路径

## T11: TUI 队员组件 — `src/tui/team-status.tsx` / `teammate-message.tsx`**文件：** 两个新文件
**依赖：** T3
**步骤：**

`src/tui/team-status.tsx`：
1. import `React`、`Text` from `ink`
2. `export function TeamStatus({ count }: { count: number })` —— `count === 0` 返 null；否则 `<Text dimColor><Text color="magenta">●</Text> {count} {count === 1 ? "teammate" : "teammates"}</Text>`

`src/tui/teammate-message.tsx`：
1. import `React`、`Box` / `Text` from `ink`
2. `export function TeammateMessage({ from, content, type = "text" }: { from: string; content: string; type?: "idle" | "completed" | "text" | "shutdown" })`：
   - `idle` / `shutdown` → `return null`
   - `completed` → 渲染 `<Text color="cyan">@{from}</Text>❯ <Text color="green">✓</Text> Task completed` + 缩进 content
   - `text` → 拆 `lines = content.split("\n")`；`summary = lines[0]`；`rest = lines.slice(1).join("\n").trimStart()`；渲染 `@<from> ❯ <summary>` + 缩进 rest
3. 定义正则 `teamMsgRe = /^\[team\s+\S+\]\s+(\S+):\s+(.*)$/s` / `idleRe = /^\[idle\]\s*/` / `shutdownRe = /^\[shutdown\]\s*/`
4. `export function parseTeammateMessage(raw: string)`：match `teamMsgRe`，不命中 return null；提取 `from` 与 `body`；按 idleRe / shutdownRe 判断 type，剥掉前缀后返回 `{ from, content, type }`

**验证：** `tsc --noEmit` 通过；`parseTeammateMessage("[team alpha] alice: [idle] done")` 返回 `{ from: "alice", type: "idle", content: "done" }`

## T12: Spinner 行与树 — `src/tui/teammate-spinner-line.tsx` / `teammate-spinner-tree.tsx`**文件：** 两个新文件
**依赖：** T3
**步骤：**

`teammate-spinner-line.tsx`：
1. import `React`、`Box` / `Text` from `ink`、`TeammateUIState` / `summarizeActivities` / `formatTokens` from `../teams/progress.js`
2. `export function TeammateSpinnerLine({ state, isLast, isSelected }: Props)`：
   - `const pointer = isSelected ? "❯ " : "  "`；`const connector = isSelected ? (isLast ? "╘═ " : "╞═ ") : (isLast ? "└─ " : "├─ ")`
   - 按 `state.status` 选 `statusNode`：`idle` dimColor / `completed` green / `failed` red / `stopped` yellow / `running` 用 `summarizeActivities` 或 `spinnerVerb`
   - `stats = " · {progress.toolUseCount} tools · {formatTokens(progress.tokenCount)} tokens"`
   - 渲染 `<Box><Text>{pointer}<Text dimColor>{connector}</Text><Text color="cyan">@{name}</Text>: {statusNode}<Text dimColor>{stats}</Text></Text></Box>`

`teammate-spinner-tree.tsx`：
1. import `TeammateSpinnerLine`、`TeammateUIState`、`formatTokens`
2. `export function TeammateSpinnerTree({ teammates, leaderVerb, leaderTokens }: Props)`：
   - `teammates.length === 0` → null
   - `tokenSuffix` 计算 leader 的 token 提示
   - 渲染头部 `<Text color="cyan">  ┌─ team-lead: {leaderVerb ?? "thinking"}...</Text><Text dimColor>{tokenSuffix}</Text>`
   - 遍历 teammates 渲染 `<TeammateSpinnerLine key={tm.name} state={tm} isLast={i === teammates.length - 1} />`

**验证：** `tsc --noEmit` 通过

## T13: Teams Dialog — `src/tui/teams-dialog.tsx`**文件：** `src/tui/teams-dialog.tsx`
**依赖：** T3
**步骤：**
1. import `React`、`useState`、`Box` / `Text` / `useInput` from `ink`、`brand` / `symbols` from `./styles.js`、`TeammateUIState` / `formatTokens` / `summarizeActivities` from `../teams/progress.js`
2. `export function TeamsDialog({ teammates, onClose, onKill?, onShutdown? }: Props)`：
   - `const [selectedIndex, setSelectedIndex] = useState(0)`；`const [view, setView] = useState<"list" | "detail">("list")`；`const [detailName, setDetailName] = useState<string | null>(null)`
   - `useInput((input, key) => { ... })`：detail 视图按 Esc/← 返回 list；list 视图 Esc 关闭、↑/↓ 翻、Enter 进详情、`k`/`s` 触发回调
   - 队员为空时渲染「No active teammates」
   - 否则按 `view` 渲染 `renderList` 或 `renderDetail`
3. helper `formatElapsed(startTime)` / `statusColor(status)`

**验证：** `tsc --noEmit` 通过

## T14: `app.tsx` 集成 — `src/tui/app.tsx`**文件：** `src/tui/app.tsx`（修改）
**依赖：** T1-T13、`src/agents/spawn.ts`（已有）
**步骤：**
1. 顶部 import `TeamManager` from `../teams/team.js`、`coordinatorToolFilter` from `../teams/coordinator.js`、`TeamCreateTool` / `SpawnTeammateTool` / `SendMessageTool` / `ListTeamsTool` / `TeamDeleteTool` from `../teams/tools.js`、`RunAgent` from `../teams/team.js`、`TeammateSpinnerTree`、`TeamStatus`、`TeamsDialog`、`TeammateUIState` from `../teams/progress.js`
2. 在 `App` 组件内：`const teamManagerRef = useRef(new TeamManager(workDir))`；`const [teammateStates, setTeammateStates] = useState<TeammateUIState[]>([])`；`const [teamsDialogOpen, setTeamsDialogOpen] = useState(false)`
3. 在 mount 后启动 `setInterval(() => setTeammateStates(teamManagerRef.current.getAllTeammateStates()), 500)`，clean-up 时 `clearInterval`
4. 在注册工具的代码块：
   ```typescript
   const teamRunAgent: RunAgent = (task, onEvent) =>
     spawnSubAgent(BUILTIN_AGENTS[0], task, client, registryRef.current, provider, workDir, undefined, onEvent);
   registryRef.current.register(new TeamCreateTool(teamManagerRef.current));
   registryRef.current.register(new SpawnTeammateTool(teamManagerRef.current, teamRunAgent));
   registryRef.current.register(new SendMessageTool(teamManagerRef.current));
   registryRef.current.register(new ListTeamsTool(teamManagerRef.current));
   registryRef.current.register(new TeamDeleteTool(teamManagerRef.current));
   ```
5. Lead 主循环 `agent.run` 的 options 加：
   ```typescript
   toolFilter: buildComposedToolFilter(coordinatorToolFilter(teamManagerRef.current), toolFilterRef.current),
   notificationFn: () => teamManagerRef.current.drainLeads(),
   ```
6. 实现 `buildComposedToolFilter(coordinator, skillFilter)` —— `skillFilter == null` 返回 coordinator；否则返回 `(name) => coordinator(name) && skillFilter(name)`
7. 在 `useInput` 中加 `Ctrl+T` 处理：`if (key.ctrl && input === "t") { setTeamsDialogOpen(o => !o); return }`
8. 在主 JSX 渲染区：
   - `{teammateStates.length > 0 && (<TeammateSpinnerTree teammates={teammateStates} leaderVerb={leaderVerb} leaderTokens={leaderTokens} />)}`
   - 状态栏底部 `<TeamStatus count={teammateStates.filter(t => t.status === "running" || t.status === "idle").length} />`
   - `{teamsDialogOpen && (<TeamsDialog teammates={teammateStates} onClose={() => setTeamsDialogOpen(false)} onKill={(name, teamName) => { const team = teamManagerRef.current.get(teamName); if (team) team.stopMember(name) }} onShutdown={(name, teamName) => { const team = teamManagerRef.current.get(teamName); if (team) team.sendMessage("lead", name, "[shutdown] Please finish and exit") }} />)}`

**验证：** `tsc --noEmit` 通过；`bun run src/main.tsx` 启动 TUI 不报错；按 `Ctrl+T` 弹出 Teams Dialog

## T15: Code Review Manager — `src/code-review/manager.ts`**文件：** `src/code-review/manager.ts`
**依赖：** T5
**步骤：**
1. import `join` from `node:path`、`readFileSync` / `writeFileSync` / `existsSync` / `mkdirSync` from `node:fs`、`Team` / `TeamManager` from `../teams/team.js`（类型）、`detectBackend` from `../teams/backend.js`
2. 定义 `export interface CodeReviewMember { name: string; email: string; role: "reviewer" | "lead" | "junior" | "critic"; expertise: string[]; active: boolean }`
3. 定义 `export interface CodeReviewTeam { name: string; members: CodeReviewMember[]; createdAt: string; lastActive: string }`
4. `export class CodeReviewManager`：
   - 字段 `private teams = new Map<string, CodeReviewTeam>(); private configPath: string; private teamManager: TeamManager; private workDir: string`
   - 构造 `constructor(workDir, teamManager)` —— `configPath = join(workDir, ".gcode", "code-review-teams.json")`；`loadTeams()`
   - 私有 `loadTeams()` —— 文件不存在跳过；读 JSON 反序列化，失败静默
   - 私有 `saveTeams()` —— `mkdirSync(<workDir>/.gcode, {recursive:true})`；`writeFileSync(configPath, JSON.stringify(teams, null, 2))`
   - `createTeam(name, members): CodeReviewTeam` —— 构造 team 对象（成员附 `active:true`），保存；调底层 `teamManager.create(name, detectBackend())`；对每个成员 `teamInstance.addMember(member.name)`
   - `getTeam` / `listTeams` / `addMember` / `removeMember` / `activateMember` / `deactivateMember` / `deleteTeam` / `getActiveReviewers` / `getTeamSummary` 按 spec.md F66 实现
5. 导出 `createDefaultCodeReviewTeam()` 工厂——构造 3 人评审组（alice/bob/charlie）

**验证：** `tsc --noEmit` 通过

## T16: Review Session — `src/code-review/session.ts`**文件：** `src/code-review/session.ts`
**依赖：** T15
**步骤：**
1. import `CodeReviewManager` / `CodeReviewTeam` / `CodeReviewMember` from `./manager.js`
2. 定义类型：
   - `ReviewRequest { id; title; description; author; branch; files; status: "pending"|"in-review"|"approved"|"rejected"|"changes-requested"; createdAt; updatedAt; reviewers; comments }`
   - `CommentResolution = "accepted" | "rejected" | "pending" | "resolved"`
   - `CriticEvaluation = "reasonable" | "unreasonable" | "partially-reasonable"`
   - `CriticAssessment { commentId; critic; evaluation; reasoning; timestamp }`
   - `ReviewComment { id; reviewer; file?; line?; content; timestamp; resolved; resolution?; authorResponse?; resolutionTimestamp?; criticAssessments }`
   - `ReviewSummary` / `FileFeedback` / `CommentIssue`
3. `export class ReviewSession`：
   - 字段 `private requests = new Map<string, ReviewRequest>(); private manager; private workDir; private commentCounter = 0`
   - 构造 `constructor(workDir, manager)` —— `loadRequests()`（占位）
   - `createReviewRequest(teamName, title, description, author, branch, files)`：校验 team 存在、`getActiveReviewers` 非空；id = `review-<Date.now()>`；构造对象放入 map
   - `getRequest(id)` / `updateRequestStatus(id, status)`
   - `addComment(requestId, reviewer, content, file?, line?)` —— id = `comment-<ts>-<counter>`，push 到 `request.comments`
   - `resolveComment / acceptComment / rejectComment`：找到 comment 改 `resolved` / `resolution` / `authorResponse` / `resolutionTimestamp`
   - `addCriticAssessment(requestId, commentId, criticName, evaluation, reasoning)` —— push 到 `comment.criticAssessments`
   - `generateFinalReport(requestId): ReviewSummary` —— 按文件聚合评论，统计 accepted/rejected/pending；构造 `ReviewSummary`
   - `formatFinalReport(summary): string` / `getCriticSummary(requestId): string` —— 字符串化输出

**验证：** `tsc --noEmit` 通过

## T17: Code Review Handler — `src/code-review/handler.ts`**文件：** `src/code-review/handler.ts`
**依赖：** T15、T16
**步骤：**
1. import `CommandContext` from `../commands/commands.js`、`CodeReviewManager` from `./manager.js`、`ReviewSession` from `./session.js`
2. `export function handleCodeReviewCommand(ctx, manager, session): string`：
   - `args = ctx.args.trim().split(/\s+/); command = args[0]?.toLowerCase(); params = args.slice(1).join(" ")`
   - `try { switch(command) { case "create": ... case "add": ... ... } } catch (e) { return \`Error: ${msg}\` }`
3. 18 个 handler 函数（`handleCreate` / `handleAddMember` / `handleAddCritic` / `handleRemoveMember` / `handleListTeams` / `handleTeamStatus` / `handleActivateMember` / `handleDeactivateMember` / `handleCreateRequest` / `handleListRequests` / `handleAddComment` / `handleAcceptComment` / `handleRejectComment` / `handleGenerateReport` / `handleApproveRequest` / `handleRejectRequest` / `handleCriticEvaluate` / `handleCriticSummary`），每个 split params、校验必填、调底层方法、返回字符串
4. `showCodeReviewHelp(): string` —— 多行帮助文本

**验证：** `tsc --noEmit` 通过；`handleCodeReviewCommand({args:"create review-A"}, ...)` 返回创建成功提示

## T18: `tests/file-mailbox.test.ts`**文件：** `tests/file-mailbox.test.ts`
**依赖：** T2
**步骤：**
1. import `describe`、`it`、`expect` from `bun:test`、`mkdtempSync` from `node:fs`、`tmpdir` from `node:os`、`join` from `node:path`、`FileMailbox` from `../src/teams/file-mailbox.js`
2. `describe("FileMailbox", () => { ... })`：
   - `it("delivers only unread messages and advances the cursor")` —— send → receive 拿到；再 receive 空；再 send → receive 拿新
   - `it("persists the read cursor across instances (process restart)")` —— writer send 两条，reader1 receive 两条；再 send 第三条；reader2 实例 `unreadCount === 1`，receive 仅第三条
   - `it("markAllRead consumes without returning")` —— send 两条，`markAllRead()`，`unreadCount === 0`，receive 空

**验证：** `bun test tests/file-mailbox.test.ts` 通过

## T19: `tests/teams.test.ts`**文件：** `tests/teams.test.ts`
**依赖：** T5、T8
**步骤：**
1. import `describe`、`it`、`expect`、`TeamManager` from `../src/teams/team.js`、`TeamCreateTool` / `SpawnTeammateTool` / `SendMessageTool` / `ListTeamsTool` from `../src/teams/tools.js`
2. helper `wait(ms)`、`workDir = () => mkdtempSync(join(tmpdir(), "gcode-team-"))`
3. `describe("teams orchestration")`：
   - spawn → drainLeads 含 `[idle]` 与 name
   - 失败队员 → drainLeads 含 `failed`
   - 5 工具 happy path（create → spawn → sendMessage → list）
   - 必填校验（空 args 触发 `isError: true`）

**验证：** `bun test tests/teams.test.ts` 通过

## T20: `tests/code-review.test.ts`**文件：** `tests/code-review.test.ts`
**依赖：** T15、T16
**步骤：**
1. import `describe`、`it`、`expect`、`TeamManager`、`CodeReviewManager`、`ReviewSession`
2. 用例：
   - `createTeam` 后 `listTeams` 含该 team；底层 `teamManager.get(name)` 非空
   - `addMember` / `removeMember` / `activateMember` / `deactivateMember` 更新 `lastActive` 与 `active` 字段
   - `createReviewRequest` 在无活跃 reviewer 时抛错
   - `addComment` + `addCriticAssessment` + `generateFinalReport` 链路

**验证：** `bun test tests/code-review.test.ts` 通过

## T21: 示例脚本 — `examples/create-code-review-team.ts` / `create-custom-team.ts`**文件：** 两个新文件
**依赖：** T15、T5
**步骤：**
1. `create-code-review-team.ts`：构造 `TeamManager` + `CodeReviewManager`，调 `createTeam("demo-review", [...])`，打印团队摘要
2. `create-custom-team.ts`：构造 `TeamManager`，调 `mgr.create("custom")`，`team.addMember("alice")` / `team.addMember("bob")`，打印 `listMembers`

**验证：** `bun run examples/create-code-review-team.ts` 与 `bun run examples/create-custom-team.ts` 跑通

## T22: 全量测试与类型检查**依赖：** T1-T21
**步骤：**
1. `tsc --noEmit` 无错误
2. `bun test` 全绿
3. 手动 `bun run src/main.tsx` 启动 TUI 验证 Ctrl+T、SpawnTeammate 流程

**验证：** 三项全过

## 执行顺序

```text
T1 (lock) ──► T2 (FileMailbox) ──┐
                                 │
T3 (progress) ───────────────────┼──► T5 (Team / TeamManager) ──► T7 (coordinator)
                                 │                            └──► T8 (5 tools)
T4 (backend) ────────────────────┘                                     │
                                                                       │
T6 (transcript) ──► T5 finally 块                                       │
                                                                       │
T9 (teammate.ts) ──► T10 (main.tsx)                                    │
                                                                       │
T11 (team-status, teammate-message) ──┐                                │
T12 (spinner-line/tree) ───────────────┼──► T14 (app.tsx 集成) ◄────────┘
T13 (teams-dialog) ────────────────────┘

T15 (code-review/manager) ──► T16 (code-review/session) ──► T17 (code-review/handler)

T18 (file-mailbox.test) ┐
T19 (teams.test) ───────┼──► T22 (全量验证)
T20 (code-review.test) ─┘

T21 (examples) ─► 可选
```

并行机会：
- T1/T3/T4 互不依赖，可同时铺
- T11/T12/T13 互不依赖（都依赖 T3），可分开实现
- T15 完成后 T16/T17 串行；T18/T19/T20 互不依赖可并行写
````

```markdown
# Agent Team Checklist

> 验证策略：每一项通过 `tsc --noEmit` / `bun test` / 真实启动 `bun run src/main.tsx` 来核实；仅依赖代码与日志，不做主观判断。

## 实现完整性

- [ ] `TeamManager` 可被实例化：`new TeamManager(workDir)` 返回非 null；`mgr.create("demo")` 在 `<workDir>/.gcode/teams/demo/` 落地目录（验证：临时目录 ad-hoc 脚本 + `existsSync` 检查）
- [ ] `Team` 构造函数自动 `mkdirSync(<dir>, {recursive:true})`，多次 `new Team` 同名不抛错（验证：tests/teams.test.ts）
- [ ] `TeamMode` 三个值齐全：`"in-process"` / `"tmux"` / `"iterm"`（验证：`tsc --noEmit` 通过 + 单测枚举）
- [ ] `Team.IDLE_POLL_INTERVAL_MS === 500`、`Team.SHUTDOWN_PREFIX === "[shutdown]"`（验证：单测断言）
- [ ] `detectBackend()` 始终返回 `"in-process"`；`detectPaneBackend()` 在 `process.env.TMUX` 非空时返回 `"tmux"`（验证：单测 + `t.Setenv` 等价的 `process.env.TMUX = "1"`）
- [ ] `spawnTeammate({ mode: "iterm", ... })` 抛 `"iTerm backend not supported on this platform"`（验证：单测 `expect(() => ...).toThrow`）
- [ ] `FileMailbox.send` + `receiveSync` 一进一出消息字段一致（`from` / `text` / `timestamp`）（验证：tests/file-mailbox.test.ts）
- [ ] `FileMailbox` 跨实例游标持久化——writer 写两条、reader1 读两条、再写一条，reader2 新实例 `unreadCount === 1` 仅读到第三条（验证：tests/file-mailbox.test.ts）
- [ ] `FileMailbox.markAllRead` 后 `unreadCount === 0`、`receive` 空数组（验证：tests/file-mailbox.test.ts）
- [ ] `acquireLock` 在 stale 10 秒后能被新 writer 抢占（验证：构造 mtimeMs 在 11 秒前的 .lock 文件，新 send 调用成功）
- [ ] 锁等待使用 `Atomics.wait`，不让出事件循环（验证：代码审查 `src/teams/file-mailbox.ts` 的 `sleepSync` 实现）
- [ ] `createProgress()` 返回零值 `{ toolUseCount: 0, tokenCount: 0, lastActivity: undefined, recentActivities: [] }`（验证：单测）
- [ ] `recordToolUse` 第 6 次调用后 `recentActivities.length === 5`（环形缓冲）（验证：单测）
- [ ] `formatTokens(1500) === "1.5k"`、`formatTokens(1500000) === "1.5M"`、`formatTokens(42) === "42"`（验证：单测）
- [ ] `describeToolActivity("ReadFile", { file_path: "x.ts" }) === "Reading x.ts"`；`Bash` 长命令截断到 40 字符 + "..."（验证：单测）
- [ ] `coordinatorToolFilter(mgr)` 在 `mgr.list().length === 0` 时对任意名字返回 `true`；有 Team 时 `WriteFile` 返回 `false`，`Bash` / `Agent` / `mcp__foo` 返回 `true`（验证：tests/teams.test.ts 或单独 coordinator 单测）
- [ ] `COORDINATOR_ALLOWED_TOOLS` 含 `Bash` 但不含 `WriteFile` / `EditFile`（验证：代码审查 + 单测）
- [ ] `TeamCreateTool.execute({ name: "x" })` 在新 Team 时返回 `"Team 'x' created."`；已存在时返回 `"Team 'x' already exists."`（不报错）（验证：tests/teams.test.ts）
- [ ] `SpawnTeammateTool.execute` 在 Team 不存在时自动 `create`，spawn 后返回提示「continue working and watch for it」（验证：tests/teams.test.ts）
- [ ] `SendMessageTool.execute({ team: "nope", to: "a", message: "m" })` 返回 `isError: true`（验证：tests/teams.test.ts）
- [ ] `ListTeamsTool.execute()` 在无 Team 时返回 `"No teams."`；有 Team 时输出每行 `<name> [<mode>]: <members>`（验证：tests/teams.test.ts）
- [ ] `TeamDeleteTool.execute({ name: "x" })` 调 `mgr.delete(name)`，再 `mgr.get(name)` 返回 undefined（验证：tests/teams.test.ts）
- [ ] `saveTranscript` 在 `<workDir>/.gcode/teams/<team>/transcripts/<agentId>.json` 落地，内容是 `TranscriptEntry[]` JSON（验证：单测/集成）
- [ ] `loadTranscript` 文件不存在或解析失败时返回 null（验证：单测）

## 集成

- [ ] `app.tsx` 启动时把 5 个 Team 工具注册到 `registryRef.current`（验证：代码审查；TUI 启动后 `/status` 或 LLM 调 `ListTeams` 能命中）
- [ ] `SpawnTeammateTool` 的 `RunAgent` 闭包内部调 `spawnSubAgent(BUILTIN_AGENTS[0], task, client, registry, provider, workDir, undefined, onEvent)`（验证：代码审查 `src/tui/app.tsx`）
- [ ] `agent.run` options 含 `toolFilter: buildComposedToolFilter(coordinatorToolFilter(teamMgr), skillFilter)` 与 `notificationFn: () => teamMgr.drainLeads()`（验证：代码审查）
- [ ] `setInterval(500ms)` 把 `teamMgr.getAllTeammateStates()` 写入 `teammateStates` state；TUI 重渲染 Spinner Tree（验证：启动 TUI 后看到 spinner 每 500ms 刷新）
- [ ] 队员主循环跑完一轮后给 Lead 信箱发 `[idle] <name> (reason: available)` 通知（验证：tests/teams.test.ts）
- [ ] 队员 `runAgent` 抛错时 `uiState.status === "failed"`，Lead 信箱收到 `[idle] <name> (reason: failed)`（验证：tests/teams.test.ts）
- [ ] 队员收到以 `[shutdown]` 开头的消息后退出主循环，`member.active === false`（验证：单测：spawn 后 sendMessage `[shutdown] please exit`，等 600ms 看 `member.active`）
- [ ] 队员退出时若 `member.conversation` 非空，自动 `saveTranscript`；写盘失败由 try/catch 静默吞掉（验证：集成测试构造一个 ConversationManager 挂到 member，触发退出后看文件落地）
- [ ] `drainLeads()` 把所有 Team 的 lead 未读消息拼成 `<team-notification team="<name>">\nfrom=<from>: <text>\n...\n</team-notification>` 字符串数组返回；消息被消费（再次调用返回空）（验证：tests/teams.test.ts）
- [ ] `parseTeammateMessage("[team alpha] alice: [idle] alice has completed...")` 返回 `{ from: "alice", type: "idle", content: "alice has completed..." }`；`[shutdown]` 同理；纯文本返回 `type: "text"`（验证：单测）
- [ ] `TeammateMessage` 渲染：`type="idle"` / `"shutdown"` 返回 null；`type="completed"` 渲染绿色 `✓ Task completed`；`type="text"` 渲染 `@<from> ❯ <summary>` + 缩进 rest（验证：组件单测或人工验收）
- [ ] `TeamStatus({ count: 0 })` 返 null；`count === 1` 显示 `● 1 teammate`；`count > 1` 显示 `● N teammates`（验证：组件单测或人工验收）
- [ ] `TeamsDialog` 按 `Esc` 关闭、`↑/↓` 翻、`Enter` 进详情、`k` 调 onKill、`s` 调 onShutdown（验证：人工启动 TUI 按 `Ctrl+T` 体验）
- [ ] `--teammate --team-dir <dir> --member-name alice --task "echo hi"` 跑通：跑完任务后给 `<dir>/lead.jsonl` 追加一条 `from=alice` 的 `[idle]` 消息（验证：手动跑 + `cat <dir>/lead.jsonl`）
- [ ] `parseTeammateFlags(["--teammate"])` 返回 null（缺必填）；`["--teammate", "--team-dir", "/tmp/x", "--member-name", "a", "--task", "echo"]` 返回完整对象（验证：可直接在 `src/teammate.ts` 末尾加临时调试或单测）
- [ ] `runTeammate` 收到 `[shutdown] please exit` 立即 `break` 退出主循环，进程退出码 0（验证：手动启动 `--teammate` 子进程，从另一个终端往 `<dir>/<name>.jsonl` 写入 shutdown 消息）
- [ ] `CodeReviewManager.createTeam("review-X", [...])` 落地 `<workDir>/.gcode/code-review-teams.json`，同时底层 `TeamManager` 也有同名 Team（验证：tests/code-review.test.ts）
- [ ] `CodeReviewManager` 对 `addMember` / `removeMember` / `activateMember` / `deactivateMember` 操作同步更新 `lastActive`（验证：tests/code-review.test.ts）
- [ ] `ReviewSession.createReviewRequest` 在无活跃 reviewer 时抛 `"No active reviewers in team 'X'"`（验证：tests/code-review.test.ts）
- [ ] `ReviewSession.addCriticAssessment(reqId, commentId, criticName, "reasonable", reasoning)` 写入 `comment.criticAssessments`，可通过 `getCriticSummary` 取出（验证：tests/code-review.test.ts）
- [ ] `/code-review create review-A` 等 18 个子命令逐个走通（验证：`handleCodeReviewCommand` 单测覆盖所有 case 与 help 文本）

## 编译与测试

- [ ] `tsc --noEmit` 无错误（验证：命令退出码 0）
- [ ] `bun test` 全部通过：`tests/file-mailbox.test.ts` + `tests/teams.test.ts` + `tests/code-review.test.ts`（验证：命令退出码 0）
- [ ] `bun run src/main.tsx` 启动 TUI 正常，无 ch15 相关 error（验证：人工启动后看 stderr 干净、TUI 渲染正常）
- [ ] `bun run src/main.tsx --teammate --team-dir /tmp/x --member-name a --task "echo hi"` 不渲染 TUI 直接走 teammate 路径，stdout 流出 agent 事件（验证：人工 + 看输出）

## 端到端场景**场景 1：in-process 后端，Team 全生命周期**

- [ ] 启动 `bun run src/main.tsx`，在 TUI 输入「创建一个名为 demo 的团队」
  - 预期：LLM 调 `TeamCreate({name:"demo"})`；返回 `"Team 'demo' created."`
  - 验证：`<workDir>/.gcode/teams/demo/` 目录存在，含 `lead.jsonl`（空）与 `lead.read`（初始 0）
- [ ] 在 TUI 输入「派 alice 去看 src/teams 目录有什么文件」
  - 预期：LLM 调 `SpawnTeammate({team:"demo", name:"alice", task:"..."})`
  - 验证 a：状态栏出现 `● 1 teammate`；spinner tree 出现 `@alice: <verb>...`
  - 验证 b：`<workDir>/.gcode/teams/demo/alice.jsonl` 创建（可能空也可能 Lead 已写入）
  - 验证 c：alice 跑完任务后 `<workDir>/.gcode/teams/demo/lead.jsonl` 多一行 `from: "alice"` 且 `text: "[idle] alice (reason: available)"`
- [ ] 在 TUI 输入「再让 alice 把 src/teams/team.ts 的行数报给我」
  - 预期：LLM 调 `SendMessage({team:"demo", to:"alice", message:"..."})`
  - 验证 a：`<workDir>/.gcode/teams/demo/alice.jsonl` 多一行 `from: "lead"` 的消息
  - 验证 b：500ms 内 alice 主循环 `waitForNextPromptOrShutdown` 收到消息，spinner 状态从 `idle` → `running`
  - 验证 c：alice 再次发 `[idle]` 通知到 lead 信箱
- [ ] LLM 这一轮收到的 reminder 应含 `<team-notification team="demo">\nfrom=alice: [idle] alice (reason: available)\n</team-notification>` 字符串（验证：开启 verbose 日志或读 `drainLeads` 输出）
- [ ] 在 TUI 输入「让 alice 写一个 hello world 文件」
  - 预期：由于 Team 存在，Lead 自身的 `WriteFile` / `EditFile` 工具被 `coordinatorToolFilter` 过滤；Lead 必须派 alice 去写
  - 验证：Lead 的 ToolUse 流里不出现 `WriteFile` 直接被调用（必须经过 SpawnTeammate / SendMessage）
- [ ] 按 `Ctrl+T` 打开 Teams Dialog
  - 验证 a：列表显示 `@alice: idle · 5 tools · 1.2k tokens` 类似行
  - 验证 b：按 `s` 调 onShutdown → `<workDir>/.gcode/teams/demo/alice.jsonl` 新增 `[shutdown] Please finish and exit` 消息
  - 验证 c：alice 主循环检测到 SHUTDOWN_PREFIX，退出循环，`uiState.status` 变 `idle` 或 `stopped`
- [ ] 在 TUI 输入「删除 demo 团队」
  - 预期：LLM 调 `TeamDelete({name:"demo"})` 返回 `"Team 'demo' deleted."`
  - 验证 a：`mgr.get("demo")` 返回 undefined（spinner tree 消失）
  - 验证 b：状态栏 TeamStatus 消失（count === 0）
  - 验证 c：Coordinator 过滤器恢复全集，下一轮 Lead 可见 `WriteFile`

**场景 2：tmux 后端真实子进程**

- [ ] `tmux new-session -s gcode-ch15` 进入新 tmux 会话
- [ ] 在 .gcode/config.yaml 加 `teammateMode: "tmux"`（手动覆盖 `detectBackend` 行为，或在代码里临时把 `mgr.create("demo", "tmux")` 写死）
- [ ] 启动 `bun run src/main.tsx`
- [ ] LLM 调 `TeamCreate("demo")` + `SpawnTeammate("demo", "alice", "ls -la")`
  - 验证 a：`tmux list-sessions` 出现 `gcode-<timestamp>` 新会话
  - 验证 b：新 tmux 会话内运行 `bun src/main.tsx --teammate --team-dir ... --member-name alice --task ...`
  - 验证 c：alice 跑完任务给 lead 信箱发 `[idle]`，主循环切换到 `mailbox.poll(2000)`
- [ ] 在 TUI 调 `SendMessage("demo", "alice", "再列一遍 src/teams")`
  - 验证：alice 在 2 秒内收到（mailbox poll 间隔），再跑一轮 agent
- [ ] 在 TUI 调 `TeamDelete("demo")`
  - 验证：`tmux list-sessions` 不含该 gcode-xxx 会话（`stopAll → cancel → tmux kill-session`）

**场景 3：Code Review 全流程**

- [ ] 启动 `bun run src/main.tsx`，输入 `/code-review create review-A alice bob charlie`
  - 验证 a：`<workDir>/.gcode/code-review-teams.json` 含 `review-A` 三人组
  - 验证 b：底层 `TeamManager.get("review-A")` 非空，三个成员的 `.jsonl` / `.read` 都建好
- [ ] `/code-review request review-A "fix login bug" "session token leaked"`
  - 验证：返回 `Created review request 'review-<ts>'` + 3 reviewers
- [ ] `/code-review comment <reqId> "should sanitize input"`
  - 验证：`session.requests.get(reqId).comments` 含一条 reviewer="current-user"
- [ ] `/code-review critic <reqId> <commentId> reasonable "good catch on input validation"`
  - 验证：`comment.criticAssessments` 含一条 critic="critic-1"、evaluation="reasonable"
- [ ] `/code-review report <reqId>`
  - 验证：输出含 `Total Comments`、`Accepted`、`Rejected`、`File-specific Feedback` 等段
- [ ] `/code-review list`
  - 验证：输出 `review-A (3/3 active)`

## 失败回归

- [ ] gcode 启动时 `<workDir>/.gcode/teams/` 不存在，`new Team` 自动创建，不报错
- [ ] `~/.gcode/code-review-teams.json` 内容损坏（手动写入 `{not-json`）时，`CodeReviewManager.loadTeams` 静默回退到空 map
- [ ] 信箱文件锁抢占冲突 10 次仍失败时，`acquireLock` 抛错；`FileMailbox.send` 的 `withLock` 把错误向上抛（验证：构造长持锁的场景）
- [ ] tmux 后端在非 tmux 终端执行 `tmux new-window` 失败时，回退到 `tmux new-session -d`；两者都失败时抛错（验证：在 tmux 外的终端启动并切到 tmux 模式）
- [ ] 队员在没有 `ConversationManager` 时退出，`saveTranscript` 不被调用（验证：spawn 一个不挂 conversation 的 member）
```


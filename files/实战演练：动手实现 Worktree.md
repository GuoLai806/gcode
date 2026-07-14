# 第14章：实战篇

## 本章需要做什么 ？

上一章我们给 GCode 装上了 SubAgent 系统，主 Agent 可以把任务分派给子 Agent，子 Agent 在隔离的上下文中执行。消息隔离了，权限隔离了，文件缓存也隔离了。但有一样东西还没隔离：文件系统。

两个 Agent 同时改同一个文件，会互相覆盖。Git 分支管不了这个问题，因为分支只是时间维度的快照，同一时刻只有一个工作目录。我们需要的是空间维度的隔离，让同一时间存在多个独立工作区。

这一章要给 GCode 接入 Git Worktree 管理系统。做完之后，每个子 Agent 都可以在独立的工作目录中操作文件，彻底消除并行场景下的文件冲突。

具体要新增这些东西：

* **Slug 安全验证&#x20;**：防止路径遍历攻击，LLM 生成的名称不可信

* **WorktreeManager 生命周期管理&#x20;**：Create / Enter / Exit / AutoCleanup / StaleCleanup / List / Remove，完整覆盖 Worktree 的创建、使用和销毁

* **创建后设置&#x20;**：复制本地配置、配置 git hooks、软链接依赖目录、复制被忽略但需要的文件

* **会话状态持久化&#x20;**：WorktreeSession 存入配置文件，支持 `--resume` 恢复

* **与 SubAgent 集成&#x20;**：AgentDefinition 新增 `isolation` 字段， `executeWithWorktree` 自动创建 Worktree、注入上下文通知、完成后自动清理

* **/worktree 斜杠命令&#x20;**：list / create / enter / exit / remove 五个子命令

这章 **不做&#x20;**：Worktree 之间的合并策略（由上层用户决定 merge 或丢弃）、跨 Worktree 的代码同步工具、多 Agent 并行编排（留给后续的 Agent Teams 系统）。

***

## Vibe Coding 实战

### 生成四份文档

把任务换成本章的内容：

```markdown
# 我的初步想法
这一步的目标是：当子 Agent 和主 Agent 要并行干活时，在同一个 Git 仓库里给每个子 Agent 开一个独立的工作目录（Worktree），让它们能同时改文件而不互相覆盖。做完之后主 Agent 可以放心派活，子 Agent 的所有文件操作都发生在自己隔离的目录里，既不被主 Agent 的改动打扰，也不会干扰主 Agent。

技术要求：

- 用 Git 自带的多工作目录机制做隔离（同一仓库挂多个目录、共享版本库、各自一个分支），目录放在仓库内不被追踪的位置
- 目录名走严格安全校验：限字符集和长度、拒绝 . 和 .. 段、允许斜杠做嵌套，防 LLM 输入触发路径遍历
- 完整生命周期：创建（含快速恢复，目录已存在时只读文件系统不调 git）、进入、退出、删除
- 创建后做环境初始化：复制本地配置、配置子目录的 git hooks、软链大型依赖目录、按规则补上被忽略但运行需要的文件
- 不通过 chdir 切换工作目录，而是把工作目录作为 explicit cwd 参数显式传到每个工具调用里，所有路径相关缓存（文件内容、系统提示词、项目指令、记忆）都用绝对路径做 key，天然按目录隔离，不需要在切换时清缓存
- 子 Agent 隔离模式：在角色定义的 frontmatter 里加 `isolation: worktree` 字段声明隔离需求，进入时自动建目录、注入路径说明，完成后按变更情况决定保留还是清掉
- 退出时变更保护，有未提交修改或未推送 commit 默认拒绝删除；后台定期清理过期的临时目录，三层过滤保证安全

这一步先不做 Worktree 之间的合并策略（交给上层用 git merge 决定）、跨目录代码同步，以及多 Agent 并行编排（留给团队协作那一章）。
```

AI 会开始问你问题，进行需求澄清。

![]()

你根据理论篇学到的内容回答这些问题，一直这样反复循环对齐需求，最后就能生成四份文档了。



### 正式开发

四份文档有了之后，就相当于施工图纸已经定好了，然后让 Claude Code 根据这四份文档进行开发

![]()

经过一段时间后，开发完成。

![]()

### 功能验证过程

来验收一下结果



让 Agent 在 worktree 里创建个文件：

![]()

然后我们再输入

![]()



会看到它是在worktree里创建，不会在主目录里创建文件，能有效避免文件冲突

![]()



这时worktrees有一份witness的文本文件，内容是：modified by isolated worker



而主目录也有一份witness的文本文件，内容是：original content from main agent

![]()



验收没问题，那么本章的主要任务就完成了。



现在虽然文件冲突解决了，但是如果是依赖关系的任务不能盲目并行咋办？如果是需要不同身份去处理任务咋办？如果是需要发散性讨论咋办？如果子Agent间需要协作咋办？



下一章，我们让多个子 Agent组成队伍，真正是一个team！

***

## 参考提示词和代码

如果你在澄清需求的过程中遇到困难，或者生成的四份文件效果不理想，可以直接使用下面的参考版本。

把下面四个文件保存到项目根目录，然后告诉你的 AI 编程助手：

### Go

````markdown
# Worktree 隔离 Spec## 背景ch13 SubAgent 隔离了消息、权限决策状态、文件读缓存和 token 计数,但 **文件系统**仍然共享。主 Agent 和后台子 Agent(以及下一章要做的 Agent Team 队员)会在同一时刻并发读写同一份工作目录的文件,出现读到对方写了一半的文件、互相覆盖修改等并行冲突——本质就是经典的并行开发文件冲突,和两个程序员同时改同一份文件一样。

Git 分支只能做**时间维度**的隔离(切换分支时工作目录被覆盖,同一时刻只有一个工作目录),不能解决并行问题;切分支还会刷被切文件的 mtime,触发依赖追踪型构建工具的链式重编。

需要的是**空间维度**的隔离:同一仓库同时挂多个工作目录、共享版本库、各自一个分支。这就是 Git Worktree (Git 2.5+) 的能力。本章在 gcode 中封装一层 Worktree 管理逻辑,把这块拼图补给 SubAgent,让后台 / 并行场景安全可用。

gcode 现有相关基础设施:
- ch13 SubAgent 已支持 frontmatter (`internal/subagent/parser.go`),解析 `name/description/tools/disallowedTools/model/maxTurns/permissionMode/background` 等字段
- ch13 `agent.AgentTool.Execute` 已是子 Agent 启动入口,本章在此处插桩 isolation 分支
- ch08 文件读缓存以绝对路径作为 key
- ch10 `internal/command` 已有 slash 命令注册系统
- `.gitignore` 已忽略 `.gcode/sessions/` 等子目录,本章扩展把 `.gcode/worktrees/` 也忽略
- Tool 接口 `Execute(ctx, args) Result` 现支持 ctx 携带值(已有 `ctxKeyConv` / `ctxKeySubAgentDepth` 范式),可作为 explicit cwd 的传递通道

本章不引入 Worktree 间合并策略、跨目录代码同步、多 Agent 并行编排,这些属于上层 / 下一章范畴。

## 目标- **G1**: 提供 `WorktreeManager` 封装 Worktree 完整生命周期——创建、快速恢复、进入、退出、删除;并发场景下用单一互斥锁保护内部 `active` 映射
- **G2**: 名字 (slug) 严格安全校验——限字符集 `[a-zA-Z0-9._-]`、总长度上限 64、显式拒绝 `.` 和 `..` 段名、允许 `/` 做嵌套分隔;防 LLM 输入触发路径遍历
- **G3**: Worktree 目录统一落在仓库内不被追踪的位置 `.gcode/worktrees/<flatSlug>/`,分支名前缀 `worktree-<flatSlug>`,嵌套 slug 的 `/` 替换为 `+` 避免 Git D/F 冲突
- **G4**: 创建后做四类环境初始化——A 复制本地配置 (`.gcode/config.yaml` / `.gcode/settings.local.yaml`)、B 配置子目录的 git hooks (`core.hooksPath` 不自动继承)、C 软链 `node_modules` / `.venv` / `vendor` 等大目录、D 按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;均为 best-effort,失败只警告不中断创建
- **G5**: 快速恢复——目录已存在时,仅读 `.git` 指针 + `HEAD` + `refs/` 文件系统读还原 commit SHA,不调任何 git 子进程,毫秒级返回
- **G6**: 进入 Worktree 不调 `os.Chdir`——把 `WorktreePath` 记到会话状态 (`WorktreeSession`) 并通过 ctx 传给工具调用;Bash / Read / Write / Edit / Glob / Grep 工具从 ctx 取 cwd,本次调用显式声明在 Worktree 里跑;进程级 cwd 不变,避免并发组件之间的同步点
- **G7**: 文件读缓存等以绝对路径为 key 的缓存,天然按目录隔离;进入 / 退出 Worktree **不需要清缓存**
- **G8**: 退出时变更保护——`action="remove"` 且未显式 `discardChanges=true` 时,检测到未提交修改或本地多于 base 的 commit 一律拒绝删除;同时切回原 cwd 兜底防 session 期间残留
- **G9**: 自动清理 (`autoCleanup`)——SubAgent 退出时,无变更则直接 remove,有变更则保留 Worktree 路径与分支名追加到 SubAgent 结果文本给主 Agent review
- **G10**: 后台过期 Worktree 清理——按命名模式 (`agent-a[0-9a-f]{7}`) 只识别临时 Worktree,叠加时间过滤(超过 cutoff 才考虑),最后做 fail-closed 变更检查(有未提交修改 / 未推送 commit 都保留)
- **G11**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,gcode 启动时读取并校验目录仍存在;退出时清空文件而不是删文件,确保下次启动不误恢复
- **G12**: 在 `subagent.Definition` 增加 `Isolation` 字段 (`""` / `"worktree"`);SubAgent 启动器检测到 `isolation:worktree` 后,自动 `create → inject worktree notice → set ctx cwd → runToCompletion → autoCleanup`,无需在 prompt / 工具调用里显式指定
- **G13**: 提供 TUI slash 命令 `/worktree create <slug>`、`/worktree list`、`/worktree exit [--remove]`、`/worktree remove <slug> [--discard]`——让用户手动管理;手动创建的 Worktree **不走自动清理**
- **G14**: 与 ch04~ch13 协同——主 Agent 看到的工具列表不变(ctx 注入不改 schema)、prompt cache 不抖动、既有测试不破坏

## 功能需求### Slug 验证- **F1**: `worktree.ValidateSlug(name)` 校验规则——
  - name 非空,总长度 ≤ 64
  - 按 `/` 切段,每段必须匹配正则 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`
  - 不允许出现连续 `//`、首末 `/`
  - 失败时返回带具体原因的 error

### WorktreeManager 与核心数据结构- **F2**: `worktree.Worktree` 记录单个 Worktree 的元信息——`Name`(原始 slug)、`Path`(绝对路径)、`Branch`(`worktree-<flatSlug>`)、`BasedOn`(创建时的 base 引用,如 `HEAD` 或具体 commit)、`HeadCommit`(创建时的 commit SHA)、`Created`(time.Time)、`Manual`(bool,是否用户手动创建,影响 autoCleanup 跳过判断)
- **F3**: `worktree.WorktreeSession` 记录当前活跃的 Worktree 会话——`OriginalCwd`、`WorktreePath`、`WorktreeName`(原 slug)、`OriginalBranch`、`OriginalHeadCommit`、`SessionID`(UUID 字符串)、`HookBased`(bool,预留)
- **F4**: `worktree.Manager` 内部字段——`repoRoot`(绝对路径)、`worktreeDir`(`<repoRoot>/.gcode/worktrees`)、`sessionFile`(`<repoRoot>/.gcode/worktree_session.json`)、`mu sync.Mutex`、`active map[string]*Worktree`、`currentSession *WorktreeSession`
- **F5**: `worktree.NewManager(repoRoot string) (*Manager, error)` 构造时——
  - 校验 `repoRoot` 是 git 仓库根目录(`git rev-parse --show-toplevel` 输出与之等);失败返回错误,gcode 启动允许降级到「Worktree 功能未启用」
  - 创建 `worktreeDir` 目录(如不存在)
  - 从 `sessionFile` 反序列化 `currentSession`(允许文件不存在);若 session 指向的 Worktree 目录已不存在,清空 session 文件并把 `currentSession=nil`
  - 扫描 `worktreeDir` 子目录还原 `active` 映射(name → Worktree),仅按文件系统读填字段(快速恢复路径)
- **F6**: `Manager.Create(ctx, name, baseRef string, manual bool) (*Worktree, error)`——
  - 1. `ValidateSlug(name)` 不通过即 error
  - 2. `mu.Lock()`,若 `active[name]` 已存在,返回 error
  - 3. `flatSlug = strings.ReplaceAll(name, "/", "+")`、`wtPath = filepath.Join(worktreeDir, flatSlug)`、`branchName = "worktree-" + flatSlug`
  - 4. 快速恢复路径:若 `wtPath` 已存在,直接读 `.git` 指针 + `HEAD` + `refs/heads/<branch>` 得 `headSha`,构造 `Worktree{...}` 加入 `active`,返回(不调任何 git 子进程)
  - 5. 否则执行 `git worktree add -B <branch> <wtPath> <baseRef>`,环境变量 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`,stdin 关闭;失败时返回错误并清理可能残留的目录
  - 6. 执行创建后设置 `performPostCreationSetup` (F7-F10),任何子步骤失败仅 stderr 警告,不中断
  - 7. 读出 `headSha`(`git -C <wtPath> rev-parse HEAD`),装填 `Worktree{Name, Path, Branch, BasedOn, HeadCommit, Created, Manual}`
  - 8. 加入 `active`,返回
- **F7**: 创建后设置 A——复制本地配置文件,从 `<repoRoot>/.gcode/config.yaml` 与 `<repoRoot>/.gcode/settings.local.yaml` 复制到 Worktree 同位置(目标目录已存在跳过,文件不存在跳过)
- **F8**: 创建后设置 B——配置 git hooks,检测主仓库 `core.hooksPath` 与 `.husky/` 目录,若有则 `git -C <wtPath> config core.hooksPath <绝对路径>`;无则跳过
- **F9**: 创建后设置 C——按配置软链大目录,默认列表 `["node_modules", ".venv", "vendor"]`,对每个目录若主仓库存在且 Worktree 不存在则创建 symlink (`os.Symlink`);其他失败只警告
- **F10**: 创建后设置 D——按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;读取 `.worktreeinclude` 每行为 glob 模式(支持 `*.env` 这种),用 `git -C <repoRoot> ls-files --others --ignored --exclude-standard --directory` 列出所有忽略文件,匹配模式后逐个复制到 Worktree 对应路径;文件不存在 / 模式无匹配只警告

### 进入与退出- **F11**: `Manager.Enter(ctx, name string) (*WorktreeSession, error)`——
  - 1. `mu.Lock()`,从 `active` 取 wt(不存在 error)
  - 2. 取当前 `os.Getwd()` 与当前 Git HEAD/branch 作为原状态
  - 3. 构造 `WorktreeSession{OriginalCwd, WorktreePath: wt.Path, WorktreeName: name, OriginalBranch, OriginalHeadCommit, SessionID: <uuid>}`
  - 4. 写 `currentSession = &session`,持久化到 `sessionFile`(原子写——先写 tmp 再 rename)
  - 5. 返回 session
  - **不调 `os.Chdir`**
- **F12**: `Manager.Exit(ctx, name string, action ExitAction, opts ExitOptions) (*ExitReport, error)`——`ExitAction` 取 `keep` / `remove`;`ExitOptions{DiscardChanges bool}`
  - 1. `mu.Lock()`,取 `active[name]` 与 `currentSession`(若 currentSession.WorktreeName != name 报错,只能退当前)
  - 2. 若 `action=remove` 且 `!opts.DiscardChanges`,调 `hasWorktreeChanges(wt.Path, wt.HeadCommit)`,有变更则 error 返回(`ErrWorktreeHasChanges`)
  - 3. `os.Chdir(session.OriginalCwd)` 兜底(防 session 期间 Bash 残留)
  - 4. `currentSession = nil`,持久化为 `null`(覆写 sessionFile 为空 JSON `null` 字符串)
  - 5. 若 `action=remove`:`git worktree remove --force <wtPath>` → `sleep 100ms` → `git branch -D <branchName>`;`delete active[name]`
  - 6. 返回 `ExitReport{Removed bool, Path string, Branch string}`
- **F13**: `Manager.Remove(ctx, name string, opts ExitOptions)`——独立 remove 入口,允许删除非当前 session 的 Worktree;变更保护同 F12
- **F14**: `Manager.AutoCleanup(ctx, name string) (*AutoCleanupReport, error)`——
  - 1. 取 `active[name]`,`Manual=true` 直接 `keep`
  - 2. `hasWorktreeChanges(wt.Path, wt.HeadCommit)` 返回 false 走 `Remove(name, ExitOptions{DiscardChanges:true})`,报告 `{Kept:false}`
  - 3. 有变更:`Kept:true, Path:wt.Path, Branch:wt.Branch`
- **F15**: `hasWorktreeChanges(wtPath, baseCommit string) bool`——两件事:`git -C <wtPath> status --porcelain` 非空即有未提交;`git -C <wtPath> rev-list --count <baseCommit>..HEAD` >0 即有新增 commit;任一 git 命令本身出错 fail-closed 返回 true(宁可保留)

### explicit cwd 工具改造- **F16**: 在 `internal/tool` 包定义 ctx key 与帮助函数——
  - `WithCwd(ctx, dir string) context.Context` 把 cwd 注入 ctx
  - `CwdFromCtx(ctx) (string, bool)` 取回
  - `ResolvePath(ctx, p string) string`——若 p 是绝对路径直接返回;否则用 ctx cwd(优先)或进程 cwd 拼相对路径,返回绝对路径
- **F17**: 改造 6 个核心工具支持 ctx cwd——
  - `read_file`、`write_file`、`edit_file`:用 `ResolvePath` 解析 `Path` 参数
  - `glob`:用 `ResolvePath` 解析 `path` 参数
  - `grep`:同 `glob`(参数名可能不同,按现有 schema)
  - `bash`:在 `exec.Cmd` 上设置 `cmd.Dir = ResolvePath(ctx, "")` 即 ctx cwd 或进程 cwd
- **F18**: ctx cwd 注入点——
  - SubAgent isolation:worktree 启动时,在调 `RunToCompletion` 前 `ctx = tool.WithCwd(ctx, wtPath)`
  - TUI `/worktree create` 后用户手动 `Enter` 也注入到主 Agent 的下一次 Run 的 ctx(通过 tui 的 `runOnce` 入口)
- **F19**: 工具 Schema 不变——主 Agent 看到的工具列表与参数与 ch13 完全一致,ctx 注入不暴露 cwd 字段

### SubAgent 集成- **F20**: 扩展 `subagent.Definition` 增加 `Isolation string` 字段;`parser.go` 解析 frontmatter `isolation:` 字段,合法值 `""` / `"worktree"`,非法值 stderr 警告后回落到 `""`
- **F21**: 改造 `agent.AgentTool.Execute`——当 `def.Isolation == "worktree"` 时走 `executeWithWorktree` 分支:
  - 1. 用 `agent-a<7位随机 hex>` 作为 worktree name(规避同类型并发冲突)
  - 2. 调 `worktreeManager.Create(ctx, name, "HEAD", false)` 创建临时 Worktree
  - 3. 构造 `worktreeNotice` 文本(F22)拼到 task 文本前
  - 4. `ctx = tool.WithCwd(ctx, wt.Path)`
  - 5. 调 `subAgent.RunToCompletion(ctx, subConv, taskWithNotice, events)`
  - 6. 跑完后调 `Manager.AutoCleanup(ctx, name)`,Kept=true 时把 `\n[Worktree 保留在 <path>,分支 <branch>]` 追加到 finalText
  - 7. 返回 finalText 给主 Agent
- **F22**: `buildWorktreeNotice(parentCwd, wtPath string) string` 模板(实际内容大致如下,中文友好)——
  ```
  <worktree-context>
  你当前在一个独立的 Git Worktree 副本中工作,与父 Agent 隔离。
  - 父目录: <parentCwd>
  - 你的工作目录: <wtPath>
  - 父 Agent 提到的绝对路径基于父目录,你需要翻译成本地路径(替换前缀)再读写
  - 编辑文件前,必须先在本地 Worktree 重新 `read_file` 一次,避免使用过时内容
  </worktree-context>
  ```
- **F23**: 后台 SubAgent + isolation 协同——若 `background && isolation:worktree`,Worktree 创建在 `task.Launch` goroutine 内进行,AutoCleanup 也在 goroutine 退出前调用;主 Agent 仍立即拿到 `task_id`

### TUI Slash 命令- **F24**: `/worktree create <slug>`——调 `Manager.Create(slug, "HEAD", true)` (`Manual=true`),输出 Worktree path + branch
- **F25**: `/worktree list`——遍历 `Manager.List()`,每行格式 `<name>  <path>  <branch>  [active?]`
- **F26**: `/worktree exit [--remove] [--discard]`——退出当前 session;`--remove` 时调 `Exit(name, "remove", {DiscardChanges:discard})`,`--discard` 跳过变更保护
- **F27**: `/worktree remove <slug> [--discard]`——直接调 `Manager.Remove(slug, {...})`
- **F28**: `/worktree enter <slug>`——调 `Manager.Enter(slug)`,把 ctx cwd 写到 TUI 的 `model.activeCwd` 字段,主 Agent 下次 Run 用这个 cwd 注入 ctx
- **F29**: slash 命令属于 `KindLocal`(只读)或 `KindUI`(改 TUI 状态),不进对话历史;输出走 `ui.Println`

### 持久化与恢复- **F30**: `WorktreeSession` 序列化为 JSON,字段名采用小写下划线;原子写——先写 `<sessionFile>.tmp` 再 `os.Rename`
- **F31**: gcode 启动时(`NewManager` 内),读 `sessionFile` 反序列化;若文件内容为 `null` 或空,`currentSession=nil`;若 `WorktreePath` 不存在,清空文件并 `currentSession=nil`(stderr 警告 "session worktree gone, cleared")
- **F32**: `--resume` (gcode 现有恢复入口)读到已有 session 时,把 `activeCwd` 设置到 session.WorktreePath,主 Agent 后续工具调用都按 explicit cwd 走

### 后台过期清理- **F33**: `Manager.SweepStale(ctx, cutoff time.Time) (removed []string)`——
  - 1. 遍历 `worktreeDir` 子目录
  - 2. **第一层** 名字匹配正则 `^agent-a[0-9a-f]{7}$`(本期只识别 SubAgent 临时模式)
  - 3. **第二层** 目录 mtime > cutoff 跳过;`currentSession.WorktreePath == 子目录` 跳过
  - 4. **第三层** `hasWorktreeChanges(子目录, 该 wt 的 HeadCommit)` 为 true 跳过(fail-closed);额外跑 `git -C <子目录> rev-list --max-count=1 HEAD --not --remotes`,非空跳过(有未推送 commit 也保留)
  - 5. 通过三层的子目录调 `Remove(name, {DiscardChanges:true})`,记入 `removed`
- **F34**: gcode 启动时跑一次 `go SweepStale(time.Now().Add(-24*time.Hour))`(异步、后台执行),不阻塞启动

### .gitignore 更新- **F35**: 在项目根 `.gitignore` 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json` 两行;gcode 启动时若发现 `.gitignore` 不含这两行,**只警告不修改**(尊重用户配置)

## 非功能需求- **N1**: 主 Agent 看到的工具列表稳定——ctx 注入不改 schema,既有缓存不抖动
- **N2**: Worktree 创建后设置失败 (F7-F10) 不阻塞创建;主路径只在 git worktree add 本身失败时返回 error
- **N3**: Manager 所有状态变更受 `mu sync.Mutex` 保护;Worktree 内部 git 操作不持锁,避免长锁
- **N4**: `os.Chdir` 在 gcode 进程内只出现在 `Manager.Exit` 兜底调用;其他地方一律用 explicit cwd
- **N5**: Worktree session 文件被破坏(非法 JSON)启动时只警告并清空,不阻断 gcode 启动
- **N6**: 与 ch04~ch13 既有测试零破坏——`go test ./...` 全绿
- **N7**: 中文友好——错误消息与命令输出全部中文(对齐 gcode 其他模块风格)

## 不做的事

- Worktree 间的合并策略(交给上层 `git merge` / `git cherry-pick`)
- 跨 Worktree 代码同步、文件 watcher
- 多 Agent 并行编排 / Agent Team(下一章)
- 主 Agent 用专用 merge 工具(README 章末已说明)
- Plugin 来源的 Worktree 配置
- Windows 平台特殊支持(symlink 行为在 Windows 上不保证;本期 gcode 以 macOS / Linux 为主)
- 跨 gcode 进程实例的 Worktree 共享(同一仓库同一时刻只支持一个 gcode 实例操作 worktree session)
- Worktree 内部 git 操作的 retry / exponential backoff(用一次性 sleep 100ms 解决 lockfile 竞态即可)

## 验收标准- **AC1**: `worktree.ValidateSlug` 对 `"feature/a"` 通过,对 `"../etc"` / `".."` / `"a//b"` / `"a/b "` 拒绝
- **AC2**: `Manager.Create("alice", "HEAD", true)` 在 `.gcode/worktrees/alice/` 下落地 Worktree,分支为 `worktree-alice`
- **AC3**: `Manager.Create("team/alice", "HEAD", true)` 在 `.gcode/worktrees/team+alice/` 下落地,分支 `worktree-team+alice`
- **AC4**: 已存在 worktree 目录时再调 Create 走快速恢复——不调 `git worktree add`,毫秒级返回(单测可断言 git 子进程未启动)
- **AC5**: 创建后设置 A——主仓库存在 `.gcode/settings.local.yaml` 时,Worktree 内同位置出现该文件
- **AC6**: 创建后设置 B——主仓库 `.husky/` 存在时,Worktree 的 `.git/config` 含 `core.hooksPath`
- **AC7**: 创建后设置 C——主仓库有 `node_modules/` 时,Worktree 内是软链(`Lstat().Mode()&os.ModeSymlink != 0`)
- **AC8**: 创建后设置 D——主仓库有 `.worktreeinclude` 含 `*.env`,且主仓库存在被忽略的 `.env`,Worktree 内出现 `.env`
- **AC9**: `Manager.Enter(name)` **不**改变进程 `os.Getwd()`;返回 session 含正确字段
- **AC10**: `Manager.Exit(name, "remove", {})` 当 Worktree 有未提交修改时,返回 `ErrWorktreeHasChanges`,Worktree 目录仍在
- **AC11**: `Manager.Exit(name, "remove", {DiscardChanges:true})` 显式 discard 时,目录被删,分支被删
- **AC12**: `Manager.AutoCleanup(name)` 对 `Manual=true` 直接 keep;对 `Manual=false` 且无变更直接 remove
- **AC13**: 工具 `read_file` / `write_file` / `edit_file` / `bash` / `glob` / `grep` 在 ctx 注入 cwd 后,以 cwd 为基准解析相对路径(单测断言)
- **AC14**: `bash` 工具在 ctx cwd 注入下,`exec.Cmd.Dir = cwd`(单测 / 集成测试可断言)
- **AC15**: `subagent.Definition.Isolation == "worktree"` 时,`AgentTool.Execute` 创建临时 Worktree、注入 worktree notice、传 ctx cwd、跑完后调 AutoCleanup
- **AC16**: SubAgent + worktree 路径上,子 Agent 写文件不影响主 Agent 工作目录(集成测试或 tmux 实跑可观察)
- **AC17**: `/worktree create alice` slash 命令成功落地 Worktree,`/worktree list` 输出含 alice
- **AC18**: `/worktree exit --remove` 在 Worktree 有未提交修改时报错;加 `--discard` 后成功删除
- **AC19**: `Manager.SweepStale(cutoff)` 只删命名匹配 `agent-a[0-9a-f]{7}` 的目录、跳过当前 session、跳过有变更或有未推送 commit 的目录
- **AC20**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,启动时读取;指向的 Worktree 目录被外部删除后,启动时清空 session 并 stderr 警告
- **AC21**: 项目编译无错误 (`go build ./...`)、所有单元测试通过 (`go test ./...`)、vet 检查通过 (`go vet ./...`)
- **AC22**: tmux 实跑——`gcode` 启动 + 触发 `isolation:worktree` 子 Agent 改文件 + 验证主目录 `server.py`(若改的是 `server.py`)未变,Worktree 副本里 `server.py` 已变;Worktree 留盘 / 自动清理符合预期
````

````markdown
# Worktree 隔离 Plan## 架构概览

新建 `internal/worktree` 包,集中放 Manager、Worktree、WorktreeSession、Slug 校验、创建后设置、自动清理、过期清理。其余包按以下方式接入:

- **`internal/tool`**:新增 `ctx.go`(WithCwd / CwdFromCtx / ResolvePath);改造 6 个核心工具用 ResolvePath
- **`internal/subagent`**:`Definition` 加 `Isolation` 字段,`parser.go` 解析 `isolation:` frontmatter
- **`internal/agent`**:`AgentTool.Execute` 加 `executeWithWorktree` 分支,启动时通过 ctx 注入 cwd
- **`internal/command`**:新增 `builtin_worktree.go`,提供 `/worktree` 一级命令与子命令(create/list/enter/exit/remove)
- **`internal/tui`**:在 model 字段加 `worktreeMgr *worktree.Manager`、`activeCwd string`;主 Agent 每次 `Run` 前用 `tool.WithCwd(ctx, activeCwd)` 注入 ctx
- **`cmd/gcode/main.go`**:`NewManager(root)` 落在 `subagentCatalog := subagent.LoadCatalog(root)` 之后;失败降级为 nil(可选);把 Manager 传给 `tui.New` 和 `agent.NewAgentTool`
- **`.gitignore`**:追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`

## 核心数据结构### worktree.Worktree

```go
type Worktree struct {
    Name       string    // 原始 slug(可能含 /)
    Path       string    // 绝对路径
    Branch     string    // worktree-<flatSlug>
    BasedOn    string    // 创建时的 base 引用(HEAD / SHA)
    HeadCommit string    // 创建时的 commit SHA
    Created    time.Time
    Manual     bool      // true=用户手动创建(/worktree create 路径)
}
```

### worktree.WorktreeSession

```go
type WorktreeSession struct {
    OriginalCwd        string `json:"original_cwd"`
    WorktreePath       string `json:"worktree_path"`
    WorktreeName       string `json:"worktree_name"`
    OriginalBranch     string `json:"original_branch"`
    OriginalHeadCommit string `json:"original_head_commit"`
    SessionID          string `json:"session_id"`
    HookBased          bool   `json:"hook_based"`
}
```

### worktree.Manager

```go
type Manager struct {
    repoRoot       string
    worktreeDir    string
    sessionFile    string
    symlinkDirs    []string  // 默认 [node_modules, .venv, vendor]
    mu             sync.Mutex
    active         map[string]*Worktree
    currentSession *WorktreeSession
}

func NewManager(repoRoot string) (*Manager, error)
func (m *Manager) Create(ctx context.Context, name, baseRef string, manual bool) (*Worktree, error)
func (m *Manager) Enter(ctx context.Context, name string) (*WorktreeSession, error)
func (m *Manager) Exit(ctx context.Context, name string, action ExitAction, opts ExitOptions) (*ExitReport, error)
func (m *Manager) Remove(ctx context.Context, name string, opts ExitOptions) error
func (m *Manager) AutoCleanup(ctx context.Context, name string) (*AutoCleanupReport, error)
func (m *Manager) SweepStale(ctx context.Context, cutoff time.Time) []string
func (m *Manager) List() []*Worktree
func (m *Manager) Get(name string) (*Worktree, bool)
func (m *Manager) CurrentSession() *WorktreeSession
```

### worktree 辅助类型

```go
type ExitAction string
const (
    ExitKeep   ExitAction = "keep"
    ExitRemove ExitAction = "remove"
)

type ExitOptions struct{ DiscardChanges bool }
type ExitReport struct{ Removed bool; Path, Branch string }
type AutoCleanupReport struct{ Kept bool; Path, Branch string }

var ErrWorktreeHasChanges = errors.New("worktree has uncommitted changes or new commits")
```

### tool ctx 帮助函数

```go
// internal/tool/ctx.go
type ctxKey int
const ctxKeyCwd ctxKey = 1

func WithCwd(ctx context.Context, dir string) context.Context
func CwdFromCtx(ctx context.Context) (string, bool)
func ResolvePath(ctx context.Context, p string) string  // 绝对返回自身,相对拼 cwd
```

### subagent.Definition 扩展

```go
type Definition struct {
    // ... 既有字段 ...
    Isolation string  // "" 或 "worktree"
}
```

## 模块设计### `internal/worktree`(新包)**职责:** Worktree 完整生命周期管理 + Slug 校验 + 后台清理。
**对外接口:** Manager (含上面所列方法) + ValidateSlug + ErrWorktreeHasChanges 等导出常量/类型。
**依赖:** 标准库 + `os/exec` 调 git。
**关键内部函数:**
- `validateSlug(name) error`
- `flatSlug(name) string` (`/` → `+`)
- `performPostCreationSetup(repoRoot, wtPath, symlinkDirs []string)`
- `hasWorktreeChanges(wtPath, baseCommit string) bool` (fail-closed)
- `resolveHeadShaFromFS(wtPath string) (string, error)` (快速恢复)
- `readWorktreeInclude(repoRoot string) []string`
- `listIgnoredFiles(repoRoot string) ([]string, error)`
- `gitCmd(workDir string, args ...string) *exec.Cmd` (统一 env: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=""`,stdin 关闭)
- `randomAgentName() string` (用于 SubAgent 临时 worktree 名)

**文件:**
- `manager.go` — Manager 类型 + 主要方法骨架
- `create.go` — Create + 快速恢复 + 创建后设置
- `lifecycle.go` — Enter / Exit / Remove / AutoCleanup
- `sweep.go` — SweepStale
- `slug.go` — ValidateSlug + flatSlug
- `session.go` — WorktreeSession + 持久化(JSON 原子写)
- `git.go` — gitCmd helper、resolveHeadShaFromFS、hasWorktreeChanges
- `*_test.go` — 单元测试

### `internal/tool` 改造**职责:** 增加 ctx cwd 传递机制,改造 6 个工具用 ResolvePath / cmd.Dir。
**对外接口:** WithCwd / CwdFromCtx / ResolvePath(新增);6 个工具 Execute 行为变更但 schema 不变。
**依赖:** 无新增。

**文件改动:**
- `ctx.go` — 新增
- `read_file.go` / `write_file.go` / `edit_file.go` — `os.Stat`/`os.ReadFile`/`os.WriteFile` 前用 `ResolvePath(ctx, a.Path)`
- `glob.go` — root 解析改 `ResolvePath`
- `grep.go` — 同 glob
- `bash.go` — `cmd.Dir = ResolvePath(ctx, "")` (即 cwd 本身,空字符串绝对路径化)

### `internal/subagent` 改造**职责:** Definition 加 Isolation 字段;parser 解析。
**改动:**
- `parser.go` — `agentFM` 加 `Isolation string \`yaml:"isolation,omitempty"\`` 字段,合法值 `""` / `"worktree"`,其他值 stderr 警告回落空
- `definition.go` — `Definition` 加 `Isolation string`

### `internal/agent` 改造**职责:** AgentTool 增加 worktree 分支,接受 Manager。
**改动:**
- `agent_tool.go`:
  - `AgentTool` 加字段 `wtMgr WorktreeManager`(新接口)
  - `NewAgentTool(..., wtMgr WorktreeManager, ...)`(签名末尾追加)
  - `Execute` 内 def.Isolation=="worktree" 时走 `t.executeWithWorktree(...)`
- 新增 `agent_worktree.go`:
  - 接口 `WorktreeManager`(避免 agent → worktree 反向耦合时的导入循环——实际 worktree 包不依赖 agent,可直接导入,这里用接口仅是为了测试 stub)
  - `executeWithWorktree(ctx, def, subAgent, subConv, prompt) (string, error)`
  - `buildWorktreeNotice(parentCwd, wtPath) string`
  - `randomAgentName() string`(走 worktree.RandomAgentName)

### `internal/command` 新增**职责:** `/worktree` 一级命令 + 子命令解析。
**改动:**
- `builtins.go` 增加 `reg.Register(&Command{ Name:"worktree", ... })`
- 新增 `builtin_worktree.go`(handler 内自己 split 子命令 + 参数)
- `ui.go` 加 UI 接口方法 `WorktreeManager() WorktreeAccessor`(返回一个轻量接口,屏蔽 worktree 包反向依赖)

**UI 接口扩展:**

```go
// command/ui.go
type WorktreeAccessor interface {
    Create(ctx context.Context, name string) (path, branch string, err error)
    List() []WorktreeSummary
    Enter(ctx context.Context, name string) error
    Exit(ctx context.Context, action string, discard bool) (removed bool, err error)
    Remove(ctx context.Context, name string, discard bool) error
}

type WorktreeSummary struct{ Name, Path, Branch string; Active, Manual bool }

type UI interface {
    // ... 既有方法 ...
    WorktreeAccessor() WorktreeAccessor
}
```

### `internal/tui` 改造**职责:** 持有 Manager 引用,把 activeCwd 注入主 Agent ctx。
**改动:**
- `tui.go` `Model` 字段加 `worktreeMgr *worktree.Manager`、`activeCwd string`(空表示进程 cwd)
- `tui.New` 接收 `WorktreeMgr *worktree.Manager`(TUIParams 加字段)
- 在 model 的 Run 方法(主 Agent Run 入口)前注入 `ctx = tool.WithCwd(ctx, m.effectiveCwd())`,其中 `effectiveCwd()` 返回 `activeCwd` 或 `os.Getwd()`
- 实现 `WorktreeAccessor()` 接口方法,返回一个适配 worktree.Manager 的实例
- 启动时(`tui.New` 内)若 Manager 的 `CurrentSession()` 非 nil,把 `m.activeCwd = session.WorktreePath`

### `cmd/gcode/main.go` 改造

```go
// 紧跟 subagentCatalog := subagent.LoadCatalog(root) 之后
worktreeMgr, werr := worktree.NewManager(root)
if werr != nil {
    fmt.Fprintln(os.Stderr, "Worktree 管理器降级:", werr)
    // worktreeMgr=nil,后续 AgentTool / TUI 容忍 nil
} else {
    go worktreeMgr.SweepStale(context.Background(), time.Now().Add(-24*time.Hour))
}
agentTool := agent.NewAgentTool(subagentCatalog, taskMgr, nil, cfg.EffectiveEnableSubAgentBackground(), worktreeMgr)

m, err := tui.New(..., tui.TUIParams{
    // ... 既有字段 ...
    WorktreeMgr: worktreeMgr,
})
```

## 模块交互**SubAgent + Worktree 启动链路:**

```
主 Agent 调 Agent 工具
  ↓
AgentTool.Execute
  ↓
def.Isolation == "worktree"?
  ↓ yes
executeWithWorktree:
  1. name = "agent-a" + randomHex(7)
  2. wt, _ = worktreeMgr.Create(ctx, name, "HEAD", manual=false)
  3. notice = buildWorktreeNotice(parentCwd, wt.Path)
  4. taskText = notice + "\n\n" + prompt
  5. ctx = tool.WithCwd(ctx, wt.Path)
  6. finalText, _ = subAgent.RunToCompletion(ctx, subConv, taskText, events)
  7. report = worktreeMgr.AutoCleanup(ctx, name)
  8. if report.Kept: finalText += "\n[Worktree 保留: " + report.Path + "]"
  9. return finalText
```

**工具调用的 cwd 解析链路:**

```
模型调 read_file(path="server.py")
  ↓
agent.execute → registry.Execute(ctx, "read_file", args)
  ↓
readFileTool.Execute(ctx, args)
  ↓
abs = tool.ResolvePath(ctx, "server.py")
  ↓
ctx 有 cwd → abs = cwd + "/server.py"
ctx 无 cwd → abs = 进程 cwd + "/server.py"
  ↓
os.ReadFile(abs)
```

**TUI 主 Agent Run 入口:**

```
TUI.runOnce(ctx):
  if m.activeCwd != "":
      ctx = tool.WithCwd(ctx, m.activeCwd)
  events = m.agent.Run(ctx, conv, mode)
```

## 文件组织

```
internal/worktree/                   — 新包
├── manager.go                       — Manager 类型 + 构造
├── create.go                        — Create + 快速恢复 + post-creation setup
├── lifecycle.go                     — Enter / Exit / Remove / AutoCleanup
├── sweep.go                         — SweepStale
├── slug.go                          — ValidateSlug + flatSlug
├── session.go                       — WorktreeSession + JSON 持久化
├── git.go                           — gitCmd / hasWorktreeChanges / resolveHeadShaFromFS
├── slug_test.go
├── manager_test.go
├── create_test.go
├── lifecycle_test.go
├── sweep_test.go
└── git_test.go

internal/tool/
├── ctx.go                           — 新增 WithCwd/CwdFromCtx/ResolvePath
├── bash.go                          — 改造:cmd.Dir = ResolvePath(ctx, "")
├── read_file.go                     — 改造:用 ResolvePath
├── write_file.go                    — 改造:用 ResolvePath
├── edit_file.go                     — 改造:用 ResolvePath
├── glob.go                          — 改造:用 ResolvePath
├── grep.go                          — 改造:用 ResolvePath
└── ctx_test.go                      — 单测

internal/subagent/
├── definition.go                    — 加 Isolation 字段
├── parser.go                        — 解析 isolation:
└── parser_test.go                   — 新增测试

internal/agent/
├── agent_tool.go                    — Execute 加 isolation 分支
├── agent_worktree.go                — 新增:executeWithWorktree + WorktreeManager interface + notice
└── agent_worktree_test.go

internal/command/
├── builtin_worktree.go              — 新增:/worktree handler
├── builtins.go                      — 增加 reg.Register
└── ui.go                            — 加 WorktreeAccessor 接口

internal/tui/
├── tui.go                           — 加 worktreeMgr / activeCwd / cwd 注入
└── worktree_adapter.go              — 实现 WorktreeAccessor(适配 worktree.Manager)

cmd/gcode/main.go                  — 接入

.gitignore                           — 追加两行
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| cwd 传递方式 | ctx WithValue | 已有 ctxKeyConv/ctxKeySubAgentDepth 范式,Tool 接口签名不变,prompt cache 不抖动 |
| Worktree 目录位置 | `.gcode/worktrees/<flatSlug>/` | README 既定方案;仓库内 + .gitignore 不追踪 |
| 嵌套 slug `/` 处理 | 替换为 `+`(flatSlug)做文件系统/分支名 | Git 分支的 `/` 是命名空间分隔符,会导致 `worktree-team/alice` 与 `worktree-team` 的 D/F 冲突 |
| Manager 构造失败处理 | 返回 error,gcode 降级 worktreeMgr=nil | 不阻塞 gcode 启动;后续 isolation:worktree 调用回错误信息 |
| 快速恢复 | 纯 fs read,不调 git | README 说明大仓库 git fetch 6-8s,fs read 3ms;场景:同一 SubAgent 反复进同 worktree |
| 创建后设置失败处理 | 仅 stderr 警告 | 都是 best-effort,失败 ≠ 不可用 |
| `-B` vs `-b` | `-B`(重置) | 上次残留的孤儿分支不会让 Create 失败 |
| sleep 100ms 在 remove | 保留 | README 指出 git lockfile 竞态;100ms 是经验值 |
| os.Chdir 使用场景 | 仅 Manager.Exit 兜底一次 | 其他全部 explicit cwd;避免进程级 cwd 成为同步点 |
| 后台清理触发时机 | gcode 启动时跑一次,异步 | 不阻塞主流程;ch11 已有 session.CleanExpired 同样做法 |
| `.worktreeinclude` 缺失行为 | 跳过 D 步骤,不报错 | 大多数项目没这文件 |
| `subagent.Isolation` 默认值 | `""`(无隔离) | 不破坏 ch13 既有定义文件 |
| 临时 worktree 命名 | `agent-a<7hex>` | README 既定;SweepStale 正则匹配 |
| Manager 用 mutex 而非 RWMutex | 操作粒度大、争用低,简单 mutex 足够 | 避免读写锁的额外复杂度 |
| `WorktreeAccessor` 接口在 command 包 | 隔离 worktree 包反向依赖 | command 包不应该导入 worktree(已经导入 permission + llm,加 worktree 是技术债) |
| TUI activeCwd 字段 | 字符串,空 = 进程 cwd | 既有 `m.cwd` 已是字符串字段,与之并存避免改 schema |
| `--resume` 与 worktree session | NewManager 内统一处理 | 启动时自动读 session,session 失效自动清空 |
| Linux/macOS 跨平台 | symlink 用 os.Symlink | os.Symlink 跨 POSIX 平台一致;Windows 失败时 best-effort 跳过 |
````

````markdown
# Worktree 隔离 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `internal/worktree/slug.go` | ValidateSlug + flatSlug |
| 新建 | `internal/worktree/slug_test.go` | Slug 校验单测 |
| 新建 | `internal/worktree/session.go` | WorktreeSession + JSON 原子持久化 |
| 新建 | `internal/worktree/git.go` | gitCmd + hasWorktreeChanges + resolveHeadShaFromFS |
| 新建 | `internal/worktree/git_test.go` | git helper 单测 |
| 新建 | `internal/worktree/manager.go` | Manager 类型 + 构造 + List/Get/CurrentSession |
| 新建 | `internal/worktree/create.go` | Create + 快速恢复 + post-creation setup A/B/C/D |
| 新建 | `internal/worktree/create_test.go` | Create + setup 单测 |
| 新建 | `internal/worktree/lifecycle.go` | Enter / Exit / Remove / AutoCleanup |
| 新建 | `internal/worktree/lifecycle_test.go` | 生命周期单测 |
| 新建 | `internal/worktree/sweep.go` | SweepStale + 三层过滤 |
| 新建 | `internal/worktree/sweep_test.go` | SweepStale 单测 |
| 新建 | `internal/worktree/manager_test.go` | NewManager + session 持久化测试 |
| 新建 | `internal/tool/ctx.go` | WithCwd / CwdFromCtx / ResolvePath |
| 新建 | `internal/tool/ctx_test.go` | ResolvePath 单测 |
| 修改 | `internal/tool/read_file.go` | 用 ResolvePath 解析 path |
| 修改 | `internal/tool/write_file.go` | 用 ResolvePath 解析 path |
| 修改 | `internal/tool/edit_file.go` | 用 ResolvePath 解析 path |
| 修改 | `internal/tool/glob.go` | 用 ResolvePath 解析 root |
| 修改 | `internal/tool/grep.go` | 用 ResolvePath 解析 path |
| 修改 | `internal/tool/bash.go` | cmd.Dir = ResolvePath(ctx,"") |
| 修改 | `internal/subagent/definition.go` | Definition 加 Isolation 字段 |
| 修改 | `internal/subagent/parser.go` | 解析 isolation: frontmatter |
| 修改 | `internal/subagent/parser_test.go` | 增加 isolation 单测 |
| 新建 | `internal/agent/agent_worktree.go` | WorktreeManager 接口 + executeWithWorktree + buildWorktreeNotice |
| 修改 | `internal/agent/agent_tool.go` | 增加 wtMgr 字段 + isolation 分支 |
| 新建 | `internal/agent/agent_worktree_test.go` | executeWithWorktree 单测(用 stub Manager) |
| 修改 | `internal/command/ui.go` | 加 WorktreeAccessor 接口 + WorktreeSummary |
| 新建 | `internal/command/builtin_worktree.go` | /worktree handler + 子命令解析 |
| 修改 | `internal/command/builtins.go` | 注册 /worktree |
| 修改 | `internal/command/builtins_test.go` | 加 worktree 注册测试 |
| 新建 | `internal/tui/worktree_adapter.go` | 实现 WorktreeAccessor 适配 worktree.Manager |
| 修改 | `internal/tui/tui.go` | worktreeMgr / activeCwd 字段 + 注入 ctx |
| 修改 | `cmd/gcode/main.go` | 构造 Manager + 注入 AgentTool / TUI + SweepStale |
| 修改 | `.gitignore` | 追加 .gcode/worktrees/ + worktree_session.json |

## T1: Slug 校验**文件:** `internal/worktree/slug.go` + `internal/worktree/slug_test.go`
**依赖:** 无
**步骤:**
1. 创建包 `worktree`,加包注释
2. 实现 `ValidateSlug(name string) error`,规则:非空、长度 ≤ 64、按 `/` 切段后每段匹配 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`、无连续 `//`、无首末 `/`
3. 实现 `FlatSlug(name string) string`:`strings.ReplaceAll(name, "/", "+")`
4. 写测试覆盖合法/非法 case:`alice`、`team/alice`、`v1.0`、`a_b`(合法);空、超长、`..`、`./x`、`a//b`、`/x`、`a/`、`a b`、`a;b`(非法)

**验证:** `go test ./internal/worktree/ -run TestValidateSlug -v`

## T2: WorktreeSession 持久化**文件:** `internal/worktree/session.go`
**依赖:** T1
**步骤:**
1. 定义 `WorktreeSession` 结构,字段按 spec F3,JSON tag 小写下划线
2. 实现 `loadSession(path string) (*WorktreeSession, error)`:文件不存在返回 (nil, nil);内容为 `null` 或空返回 (nil, nil);JSON 解析失败返回 error
3. 实现 `saveSession(path string, s *WorktreeSession) error`:s=nil 时写 `null`;原子写——先写 `path+".tmp"` 再 `os.Rename`
4. 实现 `clearSession(path string)`(等同 `saveSession(path, nil)`)

**验证:** 在 manager_test.go T9 中覆盖

## T3: Git helper**文件:** `internal/worktree/git.go` + `internal/worktree/git_test.go`
**依赖:** 无
**步骤:**
1. 实现 `gitCmd(workDir string, args ...string) *exec.Cmd`:`exec.Command("git", args...)`,设置 `cmd.Dir = workDir`,`cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0", "GIT_ASKPASS=")`,`cmd.Stdin = nil`
2. 实现 `runGit(ctx context.Context, workDir string, args ...string) (string, error)`:`exec.CommandContext`,返回 stdout 字符串(去 trailing 换行)
3. 实现 `hasWorktreeChanges(wtPath, baseCommit string) bool`:① `git -C status --porcelain` 非空 ② `git -C rev-list --count <baseCommit>..HEAD` >0;任一 git 命令本身出错 fail-closed 返回 true
4. 实现 `resolveHeadShaFromFS(wtPath string) (string, bool)`:读 `wtPath/.git` 取 `gitdir: <path>`,读 `<gitdir>/HEAD`,若是 `ref: refs/heads/<name>`,读 `<gitdir>/<refpath>` 拿 SHA;失败返回 ("", false)
5. 测试:用一个临时 git 仓库做真实 Worktree,断言上述函数行为

**验证:** `go test ./internal/worktree/ -run TestGitHelper -v`

## T4: Manager 构造**文件:** `internal/worktree/manager.go` + `internal/worktree/manager_test.go`
**依赖:** T2, T3
**步骤:**
1. 定义 `Manager` 结构(spec F4 字段) + 类型常量 `defaultSymlinkDirs = []string{"node_modules", ".venv", "vendor"}`
2. 实现 `NewManager(repoRoot string) (*Manager, error)`:
   - `repoRoot, _ = filepath.Abs(repoRoot)`
   - 跑 `git -C <repoRoot> rev-parse --show-toplevel`,输出与 repoRoot 不匹配则返回 error
   - 初始化 worktreeDir、sessionFile、active=map
   - `os.MkdirAll(worktreeDir, 0o755)`
   - `loadSession(sessionFile)`;若 session 非 nil 但其 WorktreePath 不存在,清空 session 并 stderr 警告
   - 扫描 worktreeDir 子目录,对每个非空目录用 `resolveHeadShaFromFS` 填 `active`(快速恢复路径,不调 git)
3. 实现 `List() []*Worktree`(按 name 排序)、`Get(name) (*Worktree, bool)`、`CurrentSession() *WorktreeSession`
4. 测试:在临时 git 仓库构造 Manager,断言 worktreeDir 创建、空 session 时 CurrentSession=nil、预放 session 文件能被加载、Worktree 目录不存在时 session 被清空

**验证:** `go test ./internal/worktree/ -run TestManagerConstruct -v`

## T5: Create + 快速恢复 + 创建后设置**文件:** `internal/worktree/create.go` + `internal/worktree/create_test.go`
**依赖:** T4
**步骤:**
1. 实现 `Manager.Create(ctx, name, baseRef string, manual bool) (*Worktree, error)`:
   - `ValidateSlug(name)` 不通过即 error
   - 加锁;`active[name]` 存在即 error
   - 算 `flatSlug`、`wtPath`、`branchName`
   - 若 `wtPath` 存在(`os.Stat` 成功),用 `resolveHeadShaFromFS` 取 sha,构造 Worktree 放 active,**直接返回**(快速恢复,跳过 setup)
   - 否则跑 `git worktree add -B <branch> <wtPath> <baseRef>`,用 `gitCmd`
   - 失败时:删除已创建的目录,返回 error
   - 调 `performPostCreationSetup(repoRoot, wtPath, m.symlinkDirs)`,失败仅 stderr 警告
   - 跑 `git -C <wtPath> rev-parse HEAD` 拿 headSha
   - 构造 Worktree 放 active,返回
2. 实现 `performPostCreationSetup(repoRoot, wtPath string, symlinkDirs []string) error`:四个子函数:
   - `copyLocalConfigs(repoRoot, wtPath)`:对 `.gcode/config.yaml` / `.gcode/settings.local.yaml`,若主仓存在且 Worktree 不存在,`copyFile`
   - `setupGitHooks(repoRoot, wtPath)`:优先 `.husky/`,回退 `git -C <repoRoot> config --get core.hooksPath` 拿主仓配置,若有值跑 `git -C <wtPath> config core.hooksPath <绝对路径>`
   - `symlinkLargeDirs(repoRoot, wtPath, symlinkDirs)`:对每个目录若主仓存在且 Worktree 不存在,`os.Symlink(abs(repoRoot/dir), wtPath/dir)`
   - `copyIncludedIgnored(repoRoot, wtPath)`:读 `.worktreeinclude` 模式;跑 `git -C <repoRoot> ls-files --others --ignored --exclude-standard --directory` 列出忽略文件;每个文件用 `filepath.Match` 对模式;命中则 `copyFile` 到 Worktree
   - 每个子函数失败只往 stderr 写一行 `worktree: setup <step>: <err>` 警告,继续下个步骤
3. 测试:在临时 git 仓库覆盖:Create 成功后目录存在、分支存在、设置 A 复制 settings.local.yaml、设置 C 软链 node_modules、设置 D 按 .worktreeinclude 复制 .env;快速恢复路径不调 git(用 mock 或者断言 wt 已在 active 中再 Create 走 quick path——既有 active 直接 error,这里测试已存在目录但 active 为空时的 quick path)

**验证:** `go test ./internal/worktree/ -run TestCreate -v`

## T6: Enter / Exit / Remove / AutoCleanup**文件:** `internal/worktree/lifecycle.go` + `internal/worktree/lifecycle_test.go`
**依赖:** T5
**步骤:**
1. 实现 `ExitAction`/`ExitOptions`/`ExitReport`/`AutoCleanupReport` 类型与 `ErrWorktreeHasChanges`
2. 实现 `Manager.Enter(ctx, name string) (*WorktreeSession, error)`:
   - 加锁取 active[name]
   - `os.Getwd()` 取原 cwd
   - `git -C <repoRoot> rev-parse --abbrev-ref HEAD` 与 `git -C <repoRoot> rev-parse HEAD` 取原状态(失败用空字符串兜底)
   - 生成 sessionID(`fmt.Sprintf("%x", time.Now().UnixNano())` 或者用 `crypto/rand` 8 字节 hex)——选 `crypto/rand` 保证唯一
   - 写 currentSession 字段,持久化 saveSession
3. 实现 `Manager.Exit(ctx, name, action, opts) (*ExitReport, error)`:
   - 加锁;校验 currentSession 非空且 WorktreeName==name;否则 error
   - 取 active[name];若 nil error
   - action=remove 且 !opts.DiscardChanges:调 hasWorktreeChanges,true 则返回 ErrWorktreeHasChanges
   - `os.Chdir(currentSession.OriginalCwd)` 兜底(忽略错误)
   - currentSession = nil,saveSession(nil)
   - action=remove:`git worktree remove --force <path>`,`time.Sleep(100ms)`,`git branch -D <branch>`,delete active[name]
   - 返回 ExitReport
4. 实现 `Manager.Remove(ctx, name string, opts) error`:类似 Exit 的 remove 分支,但允许非当前 session;变更保护同
5. 实现 `Manager.AutoCleanup(ctx, name) (*AutoCleanupReport, error)`:
   - 取 active[name];Manual=true 直接 Kept=true 返回(带 Path/Branch)
   - hasWorktreeChanges=false 调 Remove(name, {DiscardChanges:true}),返回 Kept=false
   - 有变更:Kept=true,返回 Path/Branch
6. 测试:Enter 不改进程 cwd、Exit 切回 cwd、Exit remove 变更保护、AutoCleanup Manual/无变更/有变更三种分支

**验证:** `go test ./internal/worktree/ -run TestLifecycle -v`

## T7: SweepStale**文件:** `internal/worktree/sweep.go` + `internal/worktree/sweep_test.go`
**依赖:** T6
**步骤:**
1. 在 sweep.go 定义 `var ephemeralPattern = regexp.MustCompile(\`^agent-a[0-9a-f]{7}$\`)`
2. 实现 `Manager.SweepStale(ctx, cutoff time.Time) (removed []string)`:
   - 遍历 `os.ReadDir(worktreeDir)`
   - 对每个目录:不匹配 pattern 跳过;mtime > cutoff 跳过;currentSession.WorktreePath==此路径跳过
   - 跑 `hasWorktreeChanges(子路径, "HEAD")`(base 用 HEAD 比较是否有自己提交的 commit——README 说要查未提交修改 + 未推送 commit;这里 base 用 head 等价于只查 status,unpushed 单独跑)
   - 实际实现:① status --porcelain 非空跳过 ② `git rev-list --max-count=1 HEAD --not --remotes` 非空跳过
   - 通过的:调 Remove(name, {DiscardChanges:true}),记 removed
3. 实现 `RandomAgentName() string`(返回 `"agent-a" + 7位随机 hex`),用 `crypto/rand` 4 字节 → hex 截前 7 位
4. 测试:构造三个目录(匹配模式无变更、匹配模式有变更、不匹配模式),SweepStale 只删第一个

**验证:** `go test ./internal/worktree/ -run TestSweep -v`

## T8: tool ctx**文件:** `internal/tool/ctx.go` + `internal/tool/ctx_test.go`
**依赖:** 无(并行 T1-T7)
**步骤:**
1. 在 internal/tool/ctx.go 定义 `type ctxKey int; const ctxKeyCwd ctxKey = 1`
2. 实现 `WithCwd(ctx, dir string) context.Context`:`dir==""` 时返回 ctx 不变;否则 `context.WithValue(ctx, ctxKeyCwd, dir)`
3. 实现 `CwdFromCtx(ctx) (string, bool)`
4. 实现 `ResolvePath(ctx context.Context, p string) string`:
   - `p` 为空:返回 ctx cwd 或 os.Getwd 兜底
   - `filepath.IsAbs(p)`:返回 p
   - 否则:base = ctx cwd 或 os.Getwd 兜底;`filepath.Join(base, p)`
5. 测试:覆盖三种 path、ctx 无 cwd 时回落到进程 cwd、空字符串返回 cwd 本身

**验证:** `go test ./internal/tool/ -run TestCtx -v`

## T9: 改造 6 个核心工具**文件:** `internal/tool/{bash,read_file,write_file,edit_file,glob,grep}.go`
**依赖:** T8
**步骤:**
1. `read_file.go`:在 `os.Stat(a.Path)` 前 `abs := ResolvePath(ctx, a.Path)`,后续用 abs;`os.ReadFile(abs)` 同
2. `write_file.go`:同样改造 path 参数;若需要 MkdirAll 时也用 abs
3. `edit_file.go`:同样
4. `glob.go`:`root := a.Path`,若空设 `"."`;然后 `root = ResolvePath(ctx, root)`;`filepath.WalkDir(root, ...)` 用 abs root;返回路径仍按相对 root 输出(保持现有行为)
5. `grep.go`:与 glob 同
6. `bash.go`:在 `shellCommand` 返回 cmd 之后,设 `cmd.Dir = ResolvePath(ctx, "")`(空字符串解析为 cwd 本身)
7. 不改 Schema(Parameters() 不变),不改 Description
8. 单测可放 `tool_test.go` / 新增 ctx_test.go——构造 ctx WithCwd 到临时目录,在临时目录里准备文件,调工具断言读到对应内容

**验证:** `go test ./internal/tool/ -v`

## T10: subagent.Definition.Isolation**文件:** `internal/subagent/{definition,parser,parser_test}.go`
**依赖:** 无
**步骤:**
1. `definition.go`:`Definition` 加 `Isolation string` 字段
2. `parser.go`:`agentFM` 加 `Isolation string \`yaml:"isolation,omitempty"\``;解析时校验合法值 `""` / `"worktree"`,非法值 stderr 警告并回落 `""`,把结果填到 `def.Isolation`
3. `parser_test.go`:增加测试覆盖 `isolation: worktree` 解析成功、`isolation: gibberish` 警告并回落空

**验证:** `go test ./internal/subagent/ -run TestParse -v`

## T11: WorktreeManager 接口 + executeWithWorktree**文件:** `internal/agent/agent_worktree.go` + `internal/agent/agent_worktree_test.go`
**依赖:** T6, T8, T10
**步骤:**
1. 新建 `agent_worktree.go`,定义接口:
   ```go
   type WorktreeManager interface {
       Create(ctx context.Context, name, baseRef string, manual bool) (worktreeInfo, error)
       AutoCleanup(ctx context.Context, name string) (autoCleanupReport, error)
   }
   ```
   ——注意 worktreeInfo / autoCleanupReport 是为了避免反向依赖,本包内定义简化结构;实际由 tui 包写适配器把 `*worktree.Manager` 包成这个接口
2. 更简化:直接让 agent 包导入 `gcode/internal/worktree`,接口替换为 `*worktree.Manager`(worktree 包不依赖 agent,无导入循环)——选这个,代码更简单
3. 实现 `buildWorktreeNotice(parentCwd, wtPath string) string`(按 spec F22 模板)
4. 实现 `randomAgentName() string`,委托给 `worktree.RandomAgentName()`
5. 实现 `executeWithWorktree(ctx, parent *Agent, def *subagent.Definition, subAgent *Agent, subConv *conversation.Conversation, prompt string, events chan<- Event) (string, error)`(从 agent_tool 中提取出主体逻辑):
   - 生成 name = randomAgentName()
   - wt, err := m.Create(ctx, name, "HEAD", false);err 处理
   - cwd, _ := os.Getwd()
   - notice = buildWorktreeNotice(cwd, wt.Path)
   - 把 notice 与 prompt 拼:taskText = notice + "\n\n" + prompt
   - ctx = tool.WithCwd(ctx, wt.Path)
   - finalText, err := subAgent.RunToCompletion(ctx, subConv, taskText, events)
   - report, _ := m.AutoCleanup(ctx, name)
   - 若 report.Kept,把保留信息追加到 finalText
   - 返回 finalText, err
6. 单测:用一个真实临时 git 仓库构造 worktree.Manager;subAgent 用 mock provider(返回空文本即结束);断言 wt.Path 被传到 ctx、AutoCleanup 被调用

**验证:** `go test ./internal/agent/ -run TestExecuteWithWorktree -v`

## T12: AgentTool 接入 isolation 分支**文件:** `internal/agent/agent_tool.go`
**依赖:** T11
**步骤:**
1. AgentTool 加字段 `wtMgr *worktree.Manager`
2. `NewAgentTool(catalog, taskMgr, parent, bgEnabled, wtMgr)`——签名末尾追加 wtMgr(允许 nil 表示不启用)
3. 在 Execute 内 `def.Isolation == "worktree"` 时:
   - 若 `t.wtMgr == nil`,返回 IsError "worktree manager not configured"
   - 若 `background == true`,把 worktree 创建/清理放到 task.Manager 的 Launch goroutine 内——目前 task.Manager.Launch 已经 take subAgent + subConv + task,需要让 Launch 支持「跑前做一件事、跑后做一件事」的钩子。本期最小改动:**当 isolation:worktree && background 时,不通过 task.Manager,而是先在 inline 路径下创建 worktree,然后把封装好的 wrapper subAgent 用 Launch 跑**,wrapper subAgent 的 RunToCompletion 包到一个 closure 里调 AutoCleanup
   - 实际更简洁的做法:不支持 isolation + background 组合,首次实现里 isolation+background 强制走 inline 路径(超时仍切后台,但 worktree 创建/清理在 AgentTool 内做)
   - 决策:**本期 isolation:worktree 时强制前台同步**(忽略 background 字段);AgentTool 在 def.Isolation=="worktree" 时即使 background=true 也走 inline 分支;tool_result 返回最终文本
4. 在 inline 路径前,若 `def.Isolation == "worktree"`,调 `executeWithWorktree(ctx, t.parent, def, subAgent, subConv, a.Prompt, events)` 替代直接 RunToCompletion
5. 改 `cmd/gcode/main.go` 的 `NewAgentTool` 调用,传入 wtMgr

**验证:** `go test ./internal/agent/ -v`

## T13: command 包加 WorktreeAccessor + /worktree handler**文件:** `internal/command/ui.go` + `internal/command/builtin_worktree.go` + `internal/command/builtins.go` + `internal/command/builtins_test.go`
**依赖:** T6
**步骤:**
1. `ui.go`:加 `WorktreeSummary` 结构 + `WorktreeAccessor` 接口(spec F24-F28 所列方法);UI 接口加 `WorktreeAccessor() WorktreeAccessor`;nopUI 实现返回 nil
2. `builtin_worktree.go`:实现 `handleWorktree(ctx, ui, args string) error`——args 是 `/worktree` 后面的全部尾随字符串;split:子命令 + 其余参数
   - `create <slug>` → `ui.WorktreeAccessor().Create(ctx, slug)`,输出 `Worktree 已创建: <path> (分支 <branch>)`
   - `list` → 遍历 List(),按格式输出
   - `enter <slug>` → `Enter(ctx, slug)`,输出 `已进入 <slug>: <path>`
   - `exit [--remove] [--discard]` → 解析 flag,调 Exit
   - `remove <slug> [--discard]` → 调 Remove
   - 未知子命令报错
3. `builtins.go`:注册 `&Command{Name:"worktree", Kind:KindLocal, Handler: <wrapper>}`——wrapper 把 ctx + args 传给 handleWorktree(args 通过 Parse 已经被丢弃,这里换个机制——见步骤 4)
4. **注意:** `command.Parse` 当前对 `/worktree create foo` 返回 `("", true)` 因为有参数。需要给 `Command` 加可选 `WantsArgs bool` 字段,Parse 与 dispatch 联动让带参数的命令调 handler 时把 args 传进去。或者改 handler 签名让 worktree 子命令本质上也走 KindPrompt(注入到对话),那太重。**最小改动:在 command 包加 `ParseWithArgs(input string) (name, args string, isSlash bool)`,dispatch 时若命中 WantsArgs=true 的 command,用 ParseWithArgs 取到 args 传给 handler。**
5. 改造方式:`Command` 加可选字段 `ArgsHandler func(ctx, ui, args string) error`;Registry.Lookup 时若命中支持 args 的命令则走 ArgsHandler;dispatcher 在 Lookup 失败时 fall back to 找带参数命令——本期最小:让 Parse 解析时记录 args,handler 通过新增接口拿到;改 dispatch
6. 实际最简单的方式:在 `command.UI` 接口加一个 `LastSlashArgs() string`,TUI 在 dispatchSlash 入口塞;或者改 Parse + dispatchSlash 让带参的命令调一个特殊 handler。**最终决定:重构 Parse 让 `/cmd args` 返回 `(name="cmd", args="args", isSlash=true)`(去掉「带参数 → 让 lookup miss」语义);Command 加 `Args string` 透传方式——但这是个较大改动。**
7. **退一步**:让 `/worktree` 自己作为一级命令接收所有尾随字符——`ParseSlash` 在 dispatch.go 改:命中带参数命令时,把尾随字符串通过 context.Value 传给 handler;handler 通过新增的 `command.ArgsFromCtx(ctx)` 取
8. **最终方案(最小改动):**
   - 修改 `command/dispatch.go`(或 TUI 调 dispatch 的入口):在 dispatchSlash 解析输入时,若命令为 `worktree`(用现有逻辑分 head/tail),把 tail 作为 ctx value(`ctxKeyArgs`)传给 handler
   - 在 command 包加 `WithArgs(ctx, args) / ArgsFromCtx(ctx)`
   - Parse 函数需要更新——让带 head=worktree 时即使有 tail 也返回 head=worktree;通过单独的 Parser 走特例
9. 测试:测试 handleWorktree 分发逻辑(用 stub UI / stub Accessor)

**验证:** `go test ./internal/command/ -run TestWorktree -v`

## T14: TUI 适配 + 注入 ctx**文件:** `internal/tui/worktree_adapter.go` + `internal/tui/tui.go`
**依赖:** T11, T13
**步骤:**
1. `worktree_adapter.go`:实现 `WorktreeAccessor` 接口,内部持 `*worktree.Manager`,把方法转发并组装 `WorktreeSummary` 列表
2. `tui.go`:Model 加字段 `worktreeMgr *worktree.Manager`、`activeCwd string`(空表示进程 cwd)
3. `tui.New` 接收 `WorktreeMgr *worktree.Manager`(TUIParams 加字段);构造时若 manager 的 CurrentSession() 非 nil,设 m.activeCwd = session.WorktreePath
4. 实现 `WorktreeAccessor()` 方法返回 worktree_adapter 实例
5. 在主 Agent Run 调用入口(找 tui.go 里 `agent.Run(ctx, conv, mode)` 调用点),前置 `ctx = tool.WithCwd(ctx, m.effectiveCwd())`
6. `effectiveCwd()`:若 activeCwd 非空返回 activeCwd,否则返回 os.Getwd() 结果
7. WorktreeAccessor.Enter 内部既调 Manager.Enter,又把 activeCwd 更新——这需要 TUI Model 提供 setter;在 adapter 里把 setter 传入

**验证:** `go build ./...` 通过;`/worktree create x` + `/worktree enter x` + Read file(相对路径) 在 worktree 内成功

## T15: 主 main 接入**文件:** `cmd/gcode/main.go` + `.gitignore`
**依赖:** T4-T14 全部
**步骤:**
1. main.go:在 `subagentCatalog := subagent.LoadCatalog(root)` 后加:
   ```go
   worktreeMgr, werr := worktree.NewManager(root)
   if werr != nil {
       fmt.Fprintln(os.Stderr, "Worktree 管理器降级:", werr)
   } else {
       go worktreeMgr.SweepStale(context.Background(), time.Now().Add(-24*time.Hour))
   }
   ```
2. `NewAgentTool` 调用末尾追加 `worktreeMgr` 参数
3. `tui.New` TUIParams 新增 `WorktreeMgr: worktreeMgr`
4. `.gitignore` 追加:
   ```
   # ch14: Worktree 隔离副本(仅供 SubAgent 与手动管理使用)
   .gcode/worktrees/
   .gcode/worktree_session.json
   ```

**验证:** `go build ./...`、`go vet ./...`、`go test ./...` 全过

## T16: 端到端 tmux 验证**文件:** 无代码修改,运行测试
**依赖:** T15
**步骤:**
1. `go build -o ./gcode ./cmd/gcode`
2. 准备项目级自定义 Agent `.gcode/agents/worktree-writer.md`(详见 checklist 场景 1)
3. tmux 启动 gcode,跑 checklist 端到端场景
4. 通过即标记 T16 完成

**验证:** 见 checklist.md 场景 1-6

## 执行顺序

```
T1 (slug)
  ↓
T2 (session) — T3 (git helper) — T8 (tool/ctx)
                                    ↓
T4 (manager construct)          T9 (改造 6 tools)
  ↓
T5 (create + setup)
  ↓
T6 (lifecycle)
  ↓
T7 (sweep)
  ↓
T10 (subagent.Isolation)
  ↓
T11 (agent_worktree + executeWithWorktree)
  ↓
T12 (AgentTool 接入)
  ↓
T13 (/worktree command) — T14 (TUI 接入)
                              ↓
T15 (main.go + .gitignore)
  ↓
T16 (tmux 端到端)
```

T1/T2/T3/T8 之间可并行;其余按依赖顺序。
````

````markdown
# Worktree 隔离 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### worktree 包

- [ ] internal/worktree 包存在且编译通过(验证:`go build ./internal/worktree/...`)
- [ ] `ValidateSlug` 对合法/非法 case 行为符合 spec F1(验证:`go test ./internal/worktree/ -run TestValidateSlug -v`)
- [ ] `FlatSlug("team/alice") == "team+alice"`(验证:同上)
- [ ] `WorktreeSession` JSON 序列化/反序列化字段名为下划线小写(验证:`go test ./internal/worktree/ -run TestSession -v`)
- [ ] `saveSession` 原子写——失败前不破坏既有文件;`saveSession(nil)` 写入 `null`(验证:同上)
- [ ] `gitCmd` 设置 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`、Stdin=nil(验证:`go test ./internal/worktree/ -run TestGitCmd -v`)
- [ ] `hasWorktreeChanges` 在临时 git 仓库内:无修改返回 false;改一个文件返回 true;git 命令出错 fail-closed 返回 true(验证:同上)
- [ ] `resolveHeadShaFromFS` 在真实 worktree 路径下返回 commit SHA(验证:`go test ./internal/worktree/ -run TestResolveHead`)
- [ ] `NewManager` 校验 repoRoot 是 git 仓库;非 git 目录返回 error(验证:`go test ./internal/worktree/ -run TestNewManager -v`)
- [ ] `NewManager` 加载已存在的 session 文件;指向不存在目录的 session 自动清空(验证:同上)
- [ ] `Manager.Create("alice", "HEAD", true)` 在 `.gcode/worktrees/alice/` 下落地 + 分支 `worktree-alice`(验证:`go test ./internal/worktree/ -run TestCreate`)
- [ ] `Manager.Create("team/alice", ...)` 落地 `.gcode/worktrees/team+alice/` + 分支 `worktree-team+alice`(验证:同上)
- [ ] `Manager.Create` 目录已存在时走快速恢复(不调 git;active 立即就绪)(验证:同上)
- [ ] `Manager.Create` 已 active 名字时再 Create 返回错误(验证:同上)
- [ ] 创建后设置 A——`.gcode/settings.local.yaml` 被复制到 Worktree(验证:同上,需在测试 fixture 准备文件)
- [ ] 创建后设置 B——主仓 `.husky/` 存在时 Worktree git config 含 core.hooksPath(验证:`go test ./internal/worktree/ -run TestSetupHooks`)
- [ ] 创建后设置 C——主仓 node_modules 存在时 Worktree 内为软链(`Lstat().Mode()&os.ModeSymlink != 0`)(验证:`go test ./internal/worktree/ -run TestSymlink`)
- [ ] 创建后设置 D——主仓 `.worktreeinclude` 模式命中的 ignored 文件被复制到 Worktree(验证:`go test ./internal/worktree/ -run TestIncludeIgnored`)
- [ ] `Manager.Enter(name)` 不改变进程 `os.Getwd()`,返回 session 含 OriginalCwd/WorktreePath/SessionID 等字段(验证:`go test ./internal/worktree/ -run TestEnter`)
- [ ] `Manager.Enter` 持久化 session 到 `.gcode/worktree_session.json`(验证:同上)
- [ ] `Manager.Exit(name, "remove", {})` 有变更时返回 `ErrWorktreeHasChanges`,Worktree 目录仍在(验证:`go test ./internal/worktree/ -run TestExit`)
- [ ] `Manager.Exit(name, "remove", {DiscardChanges:true})` 成功删除 Worktree + 分支;session 文件被清空(验证:同上)
- [ ] `Manager.Exit` 调用了 `os.Chdir(originalCwd)` 兜底(验证:测试时改进程 cwd 后调 Exit,断言 cwd 回到 original)
- [ ] `Manager.Remove(name, {})` 与 Exit 的 remove 分支一致,但允许非当前 session(验证:同上)
- [ ] `Manager.AutoCleanup` 对 Manual=true 直接 Kept=true(验证:`go test ./internal/worktree/ -run TestAutoCleanup`)
- [ ] `Manager.AutoCleanup` 无变更时 Remove 并返回 Kept=false;有变更返回 Kept=true(验证:同上)
- [ ] `Manager.SweepStale` 第一层只识别 `agent-a[0-9a-f]{7}` 模式;手动命名跳过(验证:`go test ./internal/worktree/ -run TestSweepStale`)
- [ ] `Manager.SweepStale` 跳过当前 session 的目录(验证:同上)
- [ ] `Manager.SweepStale` 有未提交修改 / 未推送 commit 的目录跳过(fail-closed)(验证:同上)
- [ ] `worktree.RandomAgentName` 返回形如 `agent-a[0-9a-f]{7}` 的字符串(验证:`go test ./internal/worktree/ -run TestRandomAgentName`)

### tool 包 ctx 改造

- [ ] `tool.WithCwd` / `CwdFromCtx` / `ResolvePath` 三函数存在(验证:`go test ./internal/tool/ -run TestCtx -v`)
- [ ] `ResolvePath` 对绝对路径直接返回;对相对路径用 ctx cwd 或 os.Getwd 拼接(验证:同上)
- [ ] `read_file(path="a.txt")` 在 ctx WithCwd=tmpDir 下读 tmpDir/a.txt(验证:`go test ./internal/tool/ -run TestReadFileCwd`)
- [ ] `write_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `edit_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `bash(command="pwd")` + ctx cwd 输出 cwd 路径(验证:`go test ./internal/tool/ -run TestBashCwd`)
- [ ] `glob(pattern="*.txt")` + ctx cwd 在 cwd 内搜索(验证:`go test ./internal/tool/ -run TestGlobCwd`)
- [ ] `grep` + ctx cwd 同上(验证:`go test ./internal/tool/ -run TestGrepCwd`)
- [ ] 工具 schema 不变——`Parameters()` 不含新字段(验证:对比 ch13 测试快照,或断言 keys)

### subagent 包扩展

- [ ] `subagent.Definition` 含 `Isolation string` 字段(验证:`go test ./internal/subagent/ -run TestDefinition`)
- [ ] `ParseDefinition` 正确解析 `isolation: worktree`(验证:`go test ./internal/subagent/ -run TestParseIsolation -v`)
- [ ] 非法 `isolation` 值时 stderr 警告并回落 `""`(验证:同上)
- [ ] 既有定义不写 isolation 时 `Isolation==""`(验证:同上)

### agent 包扩展

- [ ] `agent.AgentTool` 含 `wtMgr *worktree.Manager` 字段;`NewAgentTool` 签名末尾接收 wtMgr(验证:`go build ./internal/agent/...`)
- [ ] `agent.executeWithWorktree` 调用 Manager.Create + AutoCleanup,期间通过 ctx 传 wt.Path(验证:`go test ./internal/agent/ -run TestExecuteWithWorktree -v`)
- [ ] `buildWorktreeNotice` 输出含 `<worktree-context>` 标签 + 父目录 + 工作目录(验证:同上)
- [ ] `AgentTool.Execute` 在 `def.Isolation=="worktree"` 时走 worktree 分支(验证:同上)
- [ ] `AgentTool.Execute` 在 `wtMgr==nil` 且 isolation=worktree 时返回 IsError(验证:同上)
- [ ] `AgentTool.Execute` 在 isolation=worktree + background=true 时强制走前台路径(验证:同上)

### command 包扩展

- [ ] `command.WorktreeSummary` 与 `WorktreeAccessor` 接口存在(验证:`go build ./internal/command/...`)
- [ ] `UI` 接口加 `WorktreeAccessor() WorktreeAccessor` 方法;nopUI 返回 nil(验证:同上)
- [ ] `/worktree` 命令被注册,Lookup 命中(验证:`go test ./internal/command/ -run TestBuiltinsRegistered`)
- [ ] `handleWorktree` 分发子命令 create/list/enter/exit/remove(验证:`go test ./internal/command/ -run TestHandleWorktree -v`)
- [ ] `handleWorktree` 在 UI.WorktreeAccessor() 返回 nil 时报错(验证:同上)

### tui 包扩展

- [ ] tui.Model 含 `worktreeMgr *worktree.Manager` 与 `activeCwd string` 字段(验证:`go build ./internal/tui/...`)
- [ ] tui.New 接收 WorktreeMgr 参数;启动时若 Manager.CurrentSession() 非 nil,设 activeCwd=session.WorktreePath(验证:`go test ./internal/tui/`)
- [ ] 主 Agent Run 前 ctx 注入 cwd——可通过日志或 mock provider 断言 tool 调用收到的 cwd(验证:同上)
- [ ] worktree_adapter 实现 WorktreeAccessor 接口(验证:`go build ./...`)

### main 接入

- [ ] cmd/gcode/main.go 构造 Manager,失败 stderr 警告 + 降级(验证:`go build ./...`)
- [ ] NewAgentTool 调用末尾追加 worktreeMgr(验证:同上)
- [ ] tui.New 接收 WorktreeMgr(验证:同上)
- [ ] 启动时异步跑 SweepStale(验证:用 grep 检查代码)
- [ ] .gitignore 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`(验证:`git check-ignore .gcode/worktrees/test`)

## 集成

- [ ] subagent.Definition.Isolation + agent.AgentTool 协同——isolation:worktree 的 SubAgent 启动时自动创建 Worktree(验证:agent_worktree_test 通过)
- [ ] tool ctx WithCwd + AgentTool.executeWithWorktree 协同——SubAgent 在 Worktree 内的工具调用使用 wt.Path 作为 cwd(验证:集成测试,在临时 git repo 跑一个 mock subagent)
- [ ] 主 Agent 工具列表稳定——5 个核心工具 + Agent + TaskList + TaskGet + TaskStop + SendMessage + worktree 不暴露新工具(验证:工具数计数)
- [ ] worktree 包 + subagent 包 + agent 包 + command 包 + tui 包之间无导入循环(验证:`go build ./...`)

## 编译与测试

- [ ] 项目编译无错误:`go build ./...`
- [ ] 所有单元测试通过:`go test ./...`
- [ ] vet 检查通过:`go vet ./...`

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

**通用预置:**
- 当前目录 `cd /Users/codemelo/gcode`
- 已执行 `go build -o ./gcode ./cmd/gcode`

### 场景 1:isolation:worktree 子 Agent 修改文件不影响主目录**预置:** 创建项目级自定义 Agent:

```
.gcode/agents/worktree-writer.md
---
name: worktree-writer
description: 在 Worktree 内写文件的测试 Agent
permissionMode: dontAsk
maxTurns: 5
isolation: worktree
---

你是一个测试 Agent。当用户让你写文件时,直接用 write_file 工具写,不要询问。
```

并准备一个主目录文件 `echo "MAIN" > scratch_ch14.txt`(测试前 git status 干净,这个文件未跟踪)。

**步骤:**
- [ ] tmux 启动:`tmux new-session -d -s ch14 -x 200 -y 50 "./gcode"`
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『把 scratch_ch14.txt 的内容覆盖为 SUBAGENT,只用 write_file 工具』」
- [ ] 子 Agent 跑动,scrollback 出现 `Agent(...)` 行
- [ ] tool_result 中末尾含 `[Worktree 保留: .gcode/worktrees/agent-a... ,分支 worktree-agent-a...]`(因为有未提交修改,AutoCleanup 保留)
- [ ] **主目录** `cat scratch_ch14.txt` 仍为 `MAIN`(验证主目录未被改)
- [ ] **Worktree 副本** `cat .gcode/worktrees/agent-a*/scratch_ch14.txt` 为 `SUBAGENT`
- [ ] tmux 截屏断言:`tmux capture-pane -p -t ch14 | grep -i "worktree"`
- [ ] 清理:`rm scratch_ch14.txt`,删除残留 worktree:`./gcode` 内 `/worktree remove agent-a... --discard`(或 `git worktree remove --force` 手动清)
- [ ] tmux kill-session -t ch14

### 场景 2:isolation:worktree 子 Agent 无变更时自动清理**预置:** 同场景 1 的 worktree-writer.md(已存在)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『用 read_file 读 README.md 头 5 行,然后用 30 字总结』」
- [ ] 子 Agent 跑动,tool_result 是总结文本
- [ ] tool_result **不含**「Worktree 保留」字样(因为读文件不产生修改,AutoCleanup 直接清理)
- [ ] `ls .gcode/worktrees/` 不存在与本次任务对应的 `agent-a*` 目录(已被 AutoCleanup 删除)
- [ ] tmux kill-session

### 场景 3:`/worktree create` + `/worktree list` 手动管理**预置:** 当前在 main 分支,git 工作区干净。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create demo-feature`
- [ ] scrollback 显示 `Worktree 已创建: .gcode/worktrees/demo-feature (分支 worktree-demo-feature)`
- [ ] 输入:`/worktree list`
- [ ] scrollback 显示一行含 `demo-feature` 的列表项,标记 `[manual]`(`Manual=true`)
- [ ] tmux 外验证:`ls .gcode/worktrees/demo-feature/` 含正常 gcode 仓库内容;`git -C .gcode/worktrees/demo-feature branch` 显示在 `worktree-demo-feature`
- [ ] 清理:输入 `/worktree remove demo-feature --discard`
- [ ] 验证 `.gcode/worktrees/demo-feature` 已不存在
- [ ] tmux kill-session

### 场景 4:`/worktree exit` 变更保护**预置:** 同场景 3 创建好 `demo-feature`。

**步骤:**
- [ ] 手动写一个修改:`echo "modified" > .gcode/worktrees/demo-feature/test.txt`
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree enter demo-feature`
- [ ] 输入:`/worktree exit --remove` (不加 --discard)
- [ ] scrollback 显示错误 `worktree has uncommitted changes or new commits`(或对应中文消息)
- [ ] 输入:`/worktree exit --remove --discard`
- [ ] scrollback 显示成功消息,worktree 已被删除
- [ ] tmux kill-session

### 场景 5:explicit cwd——`/worktree enter` 后工具调用用 worktree 路径**预置:** 创建 worktree 并准备测试文件。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create cwd-test`
- [ ] 在 tmux 外:`echo "in-worktree-only" > .gcode/worktrees/cwd-test/probe.txt`(主目录无 probe.txt)
- [ ] tmux 内输入:`/worktree enter cwd-test`
- [ ] 输入:「用 read_file 读 probe.txt」
- [ ] 主 Agent 调 read_file 工具(path=probe.txt 相对路径)
- [ ] tool_result 应为 `in-worktree-only`(证明 cwd 解析到 worktree 路径)
- [ ] 输入:`/worktree exit`,主目录 cwd 恢复
- [ ] 再输入:「用 read_file 读 probe.txt」
- [ ] tool_result 报「无法访问文件 probe.txt」(主目录没这文件)
- [ ] 清理:`/worktree remove cwd-test --discard`
- [ ] tmux kill-session

### 场景 6:Slug 校验阻止路径遍历**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create ../etc`
- [ ] scrollback 显示错误,含「invalid」或「拒绝」(不创建 `.gcode/etc/` 或类似)
- [ ] 输入:`/worktree create ..`
- [ ] 同样错误
- [ ] 输入:`/worktree create normal_one`
- [ ] 成功创建
- [ ] 清理:`/worktree remove normal_one --discard`
- [ ] tmux kill-session
````

### Python

````markdown
# Worktree 隔离 Spec## 背景ch13 SubAgent 隔离了消息、权限决策状态、文件读缓存和 token 计数,但 **文件系统**仍然共享。主 Agent 和后台子 Agent(以及下一章要做的 Agent Team 队员)会在同一时刻并发读写同一份工作目录的文件,出现读到对方写了一半的文件、互相覆盖修改等并行冲突——本质就是经典的并行开发文件冲突,和两个程序员同时改同一份文件一样。

Git 分支只能做**时间维度**的隔离(切换分支时工作目录被覆盖,同一时刻只有一个工作目录),不能解决并行问题;切分支还会刷被切文件的 mtime,触发依赖追踪型构建工具的链式重编。

需要的是**空间维度**的隔离:同一仓库同时挂多个工作目录、共享版本库、各自一个分支。这就是 Git Worktree (Git 2.5+) 的能力。本章在 gcode 中封装一层 Worktree 管理逻辑,把这块拼图补给 SubAgent,让后台 / 并行场景安全可用。

gcode 现有相关基础设施:
- ch13 SubAgent 已支持 frontmatter (`src/gcode/subagent/parser.py`),解析 `name/description/tools/disallowed_tools/model/max_turns/permission_mode/background` 等字段
- ch13 `agent.AgentTool.execute` 已是子 Agent 启动入口,本章在此处插桩 isolation 分支
- ch08 文件读缓存以绝对路径作为 key
- ch10 `src/gcode/command` 已有 slash 命令注册系统
- `.gitignore` 已忽略 `.gcode/sessions/` 等子目录,本章扩展把 `.gcode/worktrees/` 也忽略
- Tool 接口 `execute(ctx, args) -> Result` 现支持 ctx 携带值(已有 `ctx_key_conv` / `ctx_key_subagent_depth` 范式,Python 用 `contextvars.ContextVar` 实现),可作为 explicit cwd 的传递通道

本章不引入 Worktree 间合并策略、跨目录代码同步、多 Agent 并行编排,这些属于上层 / 下一章范畴。

## 目标- **G1**: 提供 `WorktreeManager` 封装 Worktree 完整生命周期——创建、快速恢复、进入、退出、删除;并发场景下用单一 `asyncio.Lock` 保护内部 `active` 映射
- **G2**: 名字 (slug) 严格安全校验——限字符集 `[a-zA-Z0-9._-]`、总长度上限 64、显式拒绝 `.` 和 `..` 段名、允许 `/` 做嵌套分隔;防 LLM 输入触发路径遍历
- **G3**: Worktree 目录统一落在仓库内不被追踪的位置 `.gcode/worktrees/<flat_slug>/`,分支名前缀 `worktree-<flat_slug>`,嵌套 slug 的 `/` 替换为 `+` 避免 Git D/F 冲突
- **G4**: 创建后做四类环境初始化——A 复制本地配置 (`.gcode/config.yaml` / `.gcode/settings.local.yaml`)、B 配置子目录的 git hooks (`core.hooksPath` 不自动继承)、C 软链 `node_modules` / `.venv` / `vendor` 等大目录、D 按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;均为 best-effort,失败只警告不中断创建
- **G5**: 快速恢复——目录已存在时,仅读 `.git` 指针 + `HEAD` + `refs/` 文件系统读还原 commit SHA,不调任何 git 子进程,毫秒级返回
- **G6**: 进入 Worktree 不调 `os.chdir`——把 `WorktreePath` 记到会话状态 (`WorktreeSession`) 并通过 ctx 传给工具调用;Bash / Read / Write / Edit / Glob / Grep 工具从 ctx 取 cwd,本次调用显式声明在 Worktree 里跑;进程级 cwd 不变,避免并发组件之间的同步点
- **G7**: 文件读缓存等以绝对路径为 key 的缓存,天然按目录隔离;进入 / 退出 Worktree **不需要清缓存**
- **G8**: 退出时变更保护——`action="remove"` 且未显式 `discard_changes=True` 时,检测到未提交修改或本地多于 base 的 commit 一律拒绝删除;同时切回原 cwd 兜底防 session 期间残留
- **G9**: 自动清理 (`auto_cleanup`)——SubAgent 退出时,无变更则直接 remove,有变更则保留 Worktree 路径与分支名追加到 SubAgent 结果文本给主 Agent review
- **G10**: 后台过期 Worktree 清理——按命名模式 (`agent-a[0-9a-f]{7}`) 只识别临时 Worktree,叠加时间过滤(超过 cutoff 才考虑),最后做 fail-closed 变更检查(有未提交修改 / 未推送 commit 都保留)
- **G11**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,gcode 启动时读取并校验目录仍存在;退出时清空文件而不是删文件,确保下次启动不误恢复
- **G12**: 在 `subagent.Definition` 增加 `isolation` 字段 (`""` / `"worktree"`);SubAgent 启动器检测到 `isolation:worktree` 后,自动 `create → inject worktree notice → set ctx cwd → run_to_completion → auto_cleanup`,无需在 prompt / 工具调用里显式指定
- **G13**: 提供 TUI slash 命令 `/worktree create <slug>`、`/worktree list`、`/worktree exit [--remove]`、`/worktree remove <slug> [--discard]`——让用户手动管理;手动创建的 Worktree **不走自动清理**
- **G14**: 与 ch04~ch13 协同——主 Agent 看到的工具列表不变(ctx 注入不改 schema)、prompt cache 不抖动、既有测试不破坏

## 功能需求### Slug 验证- **F1**: `worktree.validate_slug(name)` 校验规则——
  - name 非空,总长度 ≤ 64
  - 按 `/` 切段,每段必须匹配正则 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`
  - 不允许出现连续 `//`、首末 `/`
  - 失败时抛 `ValueError` 携带具体原因

### WorktreeManager 与核心数据结构- **F2**: `worktree.Worktree`(dataclass)记录单个 Worktree 的元信息——`name`(原始 slug)、`path`(绝对路径)、`branch`(`worktree-<flat_slug>`)、`based_on`(创建时的 base 引用,如 `HEAD` 或具体 commit)、`head_commit`(创建时的 commit SHA)、`created`(datetime)、`manual`(bool,是否用户手动创建,影响 auto_cleanup 跳过判断)
- **F3**: `worktree.WorktreeSession`(dataclass)记录当前活跃的 Worktree 会话——`original_cwd`、`worktree_path`、`worktree_name`(原 slug)、`original_branch`、`original_head_commit`、`session_id`(UUID 字符串)、`hook_based`(bool,预留)
- **F4**: `worktree.Manager` 内部字段——`repo_root`(绝对路径)、`worktree_dir`(`<repo_root>/.gcode/worktrees`)、`session_file`(`<repo_root>/.gcode/worktree_session.json`)、`lock: asyncio.Lock`、`active: dict[str, Worktree]`、`current_session: WorktreeSession | None`
- **F5**: `worktree.Manager(repo_root: str)` 构造时(或工厂函数 `Manager.create(repo_root)`)——
  - 校验 `repo_root` 是 git 仓库根目录(`git rev-parse --show-toplevel` 输出与之等);失败抛异常,gcode 启动允许降级到「Worktree 功能未启用」
  - 创建 `worktree_dir` 目录(如不存在)
  - 从 `session_file` 反序列化 `current_session`(允许文件不存在);若 session 指向的 Worktree 目录已不存在,清空 session 文件并把 `current_session=None`
  - 扫描 `worktree_dir` 子目录还原 `active` 映射(name → Worktree),仅按文件系统读填字段(快速恢复路径)
- **F6**: `Manager.create(name: str, base_ref: str, manual: bool) -> Worktree`(async)——
  - 1. `validate_slug(name)` 不通过即抛异常
  - 2. `async with self.lock:`,若 `active[name]` 已存在,抛异常
  - 3. `flat_slug = name.replace("/", "+")`、`wt_path = self.worktree_dir / flat_slug`、`branch_name = f"worktree-{flat_slug}"`
  - 4. 快速恢复路径:若 `wt_path` 已存在,直接读 `.git` 指针 + `HEAD` + `refs/heads/<branch>` 得 `head_sha`,构造 `Worktree(...)` 加入 `active`,返回(不调任何 git 子进程)
  - 5. 否则执行 `git worktree add -B <branch> <wt_path> <base_ref>`,环境变量 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`,stdin 关闭;失败时抛异常并清理可能残留的目录
  - 6. 执行创建后设置 `_perform_post_creation_setup` (F7-F10),任何子步骤失败仅 stderr 警告,不中断
  - 7. 读出 `head_sha`(`git -C <wt_path> rev-parse HEAD`),装填 `Worktree(name, path, branch, based_on, head_commit, created, manual)`
  - 8. 加入 `active`,返回
- **F7**: 创建后设置 A——复制本地配置文件,从 `<repo_root>/.gcode/config.yaml` 与 `<repo_root>/.gcode/settings.local.yaml` 复制到 Worktree 同位置(目标目录已存在跳过,文件不存在跳过)
- **F8**: 创建后设置 B——配置 git hooks,检测主仓库 `core.hooksPath` 与 `.husky/` 目录,若有则 `git -C <wt_path> config core.hooksPath <绝对路径>`;无则跳过
- **F9**: 创建后设置 C——按配置软链大目录,默认列表 `["node_modules", ".venv", "vendor"]`,对每个目录若主仓库存在且 Worktree 不存在则创建 symlink (`os.symlink`);其他失败只警告
- **F10**: 创建后设置 D——按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;读取 `.worktreeinclude` 每行为 glob 模式(支持 `*.env` 这种),用 `git -C <repo_root> ls-files --others --ignored --exclude-standard --directory` 列出所有忽略文件,匹配模式后逐个复制到 Worktree 对应路径;文件不存在 / 模式无匹配只警告

### 进入与退出- **F11**: `Manager.enter(name: str) -> WorktreeSession`(async)——
  - 1. `async with self.lock:`,从 `active` 取 wt(不存在抛异常)
  - 2. 取当前 `Path.cwd()` 与当前 Git HEAD/branch 作为原状态
  - 3. 构造 `WorktreeSession(original_cwd, worktree_path=wt.path, worktree_name=name, original_branch, original_head_commit, session_id=uuid)`
  - 4. 写 `self.current_session = session`,持久化到 `session_file`(原子写——先写 tmp 再 rename)
  - 5. 返回 session
  - **不调 `os.chdir`**
- **F12**: `Manager.exit(name: str, action: ExitAction, opts: ExitOptions) -> ExitReport`(async)——`ExitAction` 取 `KEEP` / `REMOVE` 枚举;`ExitOptions(discard_changes: bool)`
  - 1. `async with self.lock:`,取 `active[name]` 与 `current_session`(若 `current_session.worktree_name != name` 抛异常,只能退当前)
  - 2. 若 `action=REMOVE` 且 `not opts.discard_changes`,调 `_has_worktree_changes(wt.path, wt.head_commit)`,有变更则抛 `WorktreeHasChangesError`
  - 3. `os.chdir(session.original_cwd)` 兜底(防 session 期间 Bash 残留)
  - 4. `self.current_session = None`,持久化为 `null`(覆写 session_file 为空 JSON `null` 字符串)
  - 5. 若 `action=REMOVE`:`git worktree remove --force <wt_path>` → `await asyncio.sleep(0.1)` → `git branch -D <branch_name>`;`del active[name]`
  - 6. 返回 `ExitReport(removed: bool, path: str, branch: str)`
- **F13**: `Manager.remove(name: str, opts: ExitOptions)`——独立 remove 入口,允许删除非当前 session 的 Worktree;变更保护同 F12
- **F14**: `Manager.auto_cleanup(name: str) -> AutoCleanupReport`——
  - 1. 取 `active[name]`,`manual=True` 直接 `keep`
  - 2. `_has_worktree_changes(wt.path, wt.head_commit)` 返回 False 走 `remove(name, ExitOptions(discard_changes=True))`,报告 `AutoCleanupReport(kept=False)`
  - 3. 有变更:`AutoCleanupReport(kept=True, path=wt.path, branch=wt.branch)`
- **F15**: `_has_worktree_changes(wt_path, base_commit) -> bool`——两件事:`git -C <wt_path> status --porcelain` 非空即有未提交;`git -C <wt_path> rev-list --count <base_commit>..HEAD` >0 即有新增 commit;任一 git 命令本身出错 fail-closed 返回 True(宁可保留)

### explicit cwd 工具改造- **F16**: 在 `gcode.tool` 包定义 ctx key 与帮助函数——
  - Python 用 `contextvars.ContextVar("cwd", default=None)` 实现 ctx 传递(也可用显式参数,本期统一用 ContextVar 与现有 conv/depth 对齐)
  - `with_cwd(dir: str)` 返回 context manager 设置 ContextVar token
  - `cwd_from_ctx() -> str | None` 取回
  - `resolve_path(p: str) -> str`——若 p 是绝对路径直接返回;否则用 ctx cwd(优先)或进程 cwd 拼相对路径,返回绝对路径
- **F17**: 改造 6 个核心工具支持 ctx cwd——
  - `read_file`、`write_file`、`edit_file`:用 `resolve_path` 解析 `path` 参数
  - `glob`:用 `resolve_path` 解析 `path` 参数
  - `grep`:同 `glob`(参数名可能不同,按现有 schema)
  - `bash`:在 `asyncio.create_subprocess_exec` / `subprocess.Popen` 调用上设置 `cwd=resolve_path("")` 即 ctx cwd 或进程 cwd
- **F18**: ctx cwd 注入点——
  - SubAgent isolation:worktree 启动时,在调 `run_to_completion` 前用 `with_cwd(wt_path)` 包住
  - TUI `/worktree create` 后用户手动 `enter` 也注入到主 Agent 的下一次 Run 的 ctx(通过 tui 的 `run_once` 入口)
- **F19**: 工具 Schema 不变——主 Agent 看到的工具列表与参数与 ch13 完全一致,ctx 注入不暴露 cwd 字段

### SubAgent 集成- **F20**: 扩展 `subagent.Definition` 增加 `isolation: str` 字段;`parser.py` 解析 frontmatter `isolation:` 字段,合法值 `""` / `"worktree"`,非法值 stderr 警告后回落到 `""`
- **F21**: 改造 `agent.AgentTool.execute`——当 `definition.isolation == "worktree"` 时走 `_execute_with_worktree` 分支:
  - 1. 用 `agent-a<7位随机 hex>` 作为 worktree name(规避同类型并发冲突)
  - 2. 调 `worktree_manager.create(name, "HEAD", manual=False)` 创建临时 Worktree
  - 3. 构造 `worktree_notice` 文本(F22)拼到 task 文本前
  - 4. 用 `with_cwd(wt.path)` 包住后续调用
  - 5. 调 `sub_agent.run_to_completion(sub_conv, task_with_notice, events)`
  - 6. 跑完后调 `manager.auto_cleanup(name)`,`kept=True` 时把 `\n[Worktree 保留在 <path>,分支 <branch>]` 追加到 final_text
  - 7. 返回 final_text 给主 Agent
- **F22**: `build_worktree_notice(parent_cwd: str, wt_path: str) -> str` 模板(实际内容大致如下,中文友好)——
  ```
  <worktree-context>
  你当前在一个独立的 Git Worktree 副本中工作,与父 Agent 隔离。
  - 父目录: <parent_cwd>
  - 你的工作目录: <wt_path>
  - 父 Agent 提到的绝对路径基于父目录,你需要翻译成本地路径(替换前缀)再读写
  - 编辑文件前,必须先在本地 Worktree 重新 `read_file` 一次,避免使用过时内容
  </worktree-context>
  ```
- **F23**: 后台 SubAgent + isolation 协同——若 `background and isolation == "worktree"`,Worktree 创建在 `task.launch` 协程内进行,auto_cleanup 也在协程退出前调用;主 Agent 仍立即拿到 `task_id`(本期最小实现:强制走前台,见 plan)

### TUI Slash 命令- **F24**: `/worktree create <slug>`——调 `manager.create(slug, "HEAD", manual=True)`,输出 Worktree path + branch
- **F25**: `/worktree list`——遍历 `manager.list()`,每行格式 `<name>  <path>  <branch>  [active?]`
- **F26**: `/worktree exit [--remove] [--discard]`——退出当前 session;`--remove` 时调 `exit(name, ExitAction.REMOVE, ExitOptions(discard_changes=discard))`,`--discard` 跳过变更保护
- **F27**: `/worktree remove <slug> [--discard]`——直接调 `manager.remove(slug, ...)`
- **F28**: `/worktree enter <slug>`——调 `manager.enter(slug)`,把 ctx cwd 写到 TUI 的 `app.active_cwd` 字段,主 Agent 下次 Run 用这个 cwd 注入 ctx
- **F29**: slash 命令属于 `KindLocal`(只读)或 `KindUI`(改 TUI 状态),不进对话历史;输出走 `ui.println`

### 持久化与恢复- **F30**: `WorktreeSession` 序列化为 JSON,字段名采用小写下划线;原子写——先写 `<session_file>.tmp` 再 `os.replace`
- **F31**: gcode 启动时(`Manager.__init__` 内),读 `session_file` 反序列化;若文件内容为 `null` 或空,`current_session=None`;若 `worktree_path` 不存在,清空文件并 `current_session=None`(stderr 警告 "session worktree gone, cleared")
- **F32**: `--resume` (gcode 现有恢复入口)读到已有 session 时,把 `active_cwd` 设置到 `session.worktree_path`,主 Agent 后续工具调用都按 explicit cwd 走

### 后台过期清理- **F33**: `Manager.sweep_stale(cutoff: datetime) -> list[str]`(async)——
  - 1. 遍历 `worktree_dir.iterdir()`
  - 2. **第一层** 名字匹配正则 `^agent-a[0-9a-f]{7}$`(本期只识别 SubAgent 临时模式)
  - 3. **第二层** 目录 mtime > cutoff 跳过;`current_session.worktree_path == 子目录` 跳过
  - 4. **第三层** `_has_worktree_changes(子目录, 该 wt 的 head_commit)` 为 True 跳过(fail-closed);额外跑 `git -C <子目录> rev-list --max-count=1 HEAD --not --remotes`,非空跳过(有未推送 commit 也保留)
  - 5. 通过三层的子目录调 `remove(name, ExitOptions(discard_changes=True))`,记入 `removed`
- **F34**: gcode 启动时跑一次 `asyncio.create_task(manager.sweep_stale(now - timedelta(hours=24)))`(异步、后台执行),不阻塞启动

### .gitignore 更新- **F35**: 在项目根 `.gitignore` 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json` 两行;gcode 启动时若发现 `.gitignore` 不含这两行,**只警告不修改**(尊重用户配置)

## 非功能需求- **N1**: 主 Agent 看到的工具列表稳定——ctx 注入不改 schema,既有缓存不抖动
- **N2**: Worktree 创建后设置失败 (F7-F10) 不阻塞创建;主路径只在 git worktree add 本身失败时抛异常
- **N3**: Manager 所有状态变更受 `asyncio.Lock` 保护;Worktree 内部 git 操作不持锁,避免长锁
- **N4**: `os.chdir` 在 gcode 进程内只出现在 `Manager.exit` 兜底调用;其他地方一律用 explicit cwd
- **N5**: Worktree session 文件被破坏(非法 JSON)启动时只警告并清空,不阻断 gcode 启动
- **N6**: 与 ch04~ch13 既有测试零破坏——`pytest` 全绿
- **N7**: 中文友好——错误消息与命令输出全部中文(对齐 gcode 其他模块风格)

## 不做的事

- Worktree 间的合并策略(交给上层 `git merge` / `git cherry-pick`)
- 跨 Worktree 代码同步、文件 watcher
- 多 Agent 并行编排 / Agent Team(下一章)
- 主 Agent 用专用 merge 工具(README 章末已说明)
- Plugin 来源的 Worktree 配置
- Windows 平台特殊支持(symlink 行为在 Windows 上不保证;本期 gcode 以 macOS / Linux 为主)
- 跨 gcode 进程实例的 Worktree 共享(同一仓库同一时刻只支持一个 gcode 实例操作 worktree session)
- Worktree 内部 git 操作的 retry / exponential backoff(用一次性 `await asyncio.sleep(0.1)` 解决 lockfile 竞态即可)

## 验收标准- **AC1**: `worktree.validate_slug` 对 `"feature/a"` 通过,对 `"../etc"` / `".."` / `"a//b"` / `"a/b "` 拒绝
- **AC2**: `manager.create("alice", "HEAD", manual=True)` 在 `.gcode/worktrees/alice/` 下落地 Worktree,分支为 `worktree-alice`
- **AC3**: `manager.create("team/alice", "HEAD", manual=True)` 在 `.gcode/worktrees/team+alice/` 下落地,分支 `worktree-team+alice`
- **AC4**: 已存在 worktree 目录时再调 create 走快速恢复——不调 `git worktree add`,毫秒级返回(单测可断言 git 子进程未启动)
- **AC5**: 创建后设置 A——主仓库存在 `.gcode/settings.local.yaml` 时,Worktree 内同位置出现该文件
- **AC6**: 创建后设置 B——主仓库 `.husky/` 存在时,Worktree 的 `.git/config` 含 `core.hooksPath`
- **AC7**: 创建后设置 C——主仓库有 `node_modules/` 时,Worktree 内是软链(`Path.is_symlink()` 为 True)
- **AC8**: 创建后设置 D——主仓库有 `.worktreeinclude` 含 `*.env`,且主仓库存在被忽略的 `.env`,Worktree 内出现 `.env`
- **AC9**: `manager.enter(name)` **不**改变进程 `Path.cwd()`;返回 session 含正确字段
- **AC10**: `manager.exit(name, ExitAction.REMOVE, ExitOptions())` 当 Worktree 有未提交修改时,抛 `WorktreeHasChangesError`,Worktree 目录仍在
- **AC11**: `manager.exit(name, ExitAction.REMOVE, ExitOptions(discard_changes=True))` 显式 discard 时,目录被删,分支被删
- **AC12**: `manager.auto_cleanup(name)` 对 `manual=True` 直接 keep;对 `manual=False` 且无变更直接 remove
- **AC13**: 工具 `read_file` / `write_file` / `edit_file` / `bash` / `glob` / `grep` 在 ctx 注入 cwd 后,以 cwd 为基准解析相对路径(单测断言)
- **AC14**: `bash` 工具在 ctx cwd 注入下,子进程 `cwd=` 参数为 ctx cwd(单测 / 集成测试可断言)
- **AC15**: `subagent.Definition.isolation == "worktree"` 时,`AgentTool.execute` 创建临时 Worktree、注入 worktree notice、传 ctx cwd、跑完后调 auto_cleanup
- **AC16**: SubAgent + worktree 路径上,子 Agent 写文件不影响主 Agent 工作目录(集成测试或 tmux 实跑可观察)
- **AC17**: `/worktree create alice` slash 命令成功落地 Worktree,`/worktree list` 输出含 alice
- **AC18**: `/worktree exit --remove` 在 Worktree 有未提交修改时报错;加 `--discard` 后成功删除
- **AC19**: `manager.sweep_stale(cutoff)` 只删命名匹配 `agent-a[0-9a-f]{7}` 的目录、跳过当前 session、跳过有变更或有未推送 commit 的目录
- **AC20**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,启动时读取;指向的 Worktree 目录被外部删除后,启动时清空 session 并 stderr 警告
- **AC21**: 项目可启动 (`python -m gcode`)、所有单元测试通过 (`pytest`)、lint 通过 (`ruff check`)
- **AC22**: tmux 实跑——`python -m gcode` 启动 + 触发 `isolation:worktree` 子 Agent 改文件 + 验证主目录 `server.py`(若改的是 `server.py`)未变,Worktree 副本里 `server.py` 已变;Worktree 留盘 / 自动清理符合预期
````

````markdown
# Worktree 隔离 Plan## 架构概览

新建 `src/gcode/worktree/` 子包,集中放 Manager、Worktree、WorktreeSession、Slug 校验、创建后设置、自动清理、过期清理。其余包按以下方式接入:

- **`gcode.tool`**:新增 `ctx.py`(with_cwd / cwd_from_ctx / resolve_path);改造 6 个核心工具用 resolve_path
- **`gcode.subagent`**:`Definition` 加 `isolation` 字段,`parser.py` 解析 `isolation:` frontmatter
- **`gcode.agent`**:`AgentTool.execute` 加 `_execute_with_worktree` 分支,启动时通过 ctx 注入 cwd
- **`gcode.command`**:新增 `builtin_worktree.py`,提供 `/worktree` 一级命令与子命令(create/list/enter/exit/remove)
- **`gcode.tui`**:在 App 字段加 `worktree_mgr: worktree.Manager`、`active_cwd: str`;主 Agent 每次 Run 前用 `with_cwd(active_cwd)` 包住
- **`src/gcode/__main__.py` / `cli.py`**:`Manager(root)` 落在 `subagent_catalog = load_subagent_catalog(root)` 之后;失败降级为 None(可选);把 Manager 传给 `GCodeApp` 和 `AgentTool`
- **`.gitignore`**:追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`

## 核心数据结构### worktree.Worktree

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Worktree:
    name: str                # 原始 slug(可能含 /)
    path: str                # 绝对路径
    branch: str              # worktree-<flat_slug>
    based_on: str            # 创建时的 base 引用(HEAD / SHA)
    head_commit: str         # 创建时的 commit SHA
    created: datetime
    manual: bool             # True=用户手动创建(/worktree create 路径)
```

### worktree.WorktreeSession

```python
from dataclasses import dataclass, asdict
import json

@dataclass
class WorktreeSession:
    original_cwd: str
    worktree_path: str
    worktree_name: str
    original_branch: str
    original_head_commit: str
    session_id: str
    hook_based: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "WorktreeSession":
        return cls(**json.loads(raw))
```

### worktree.Manager

```python
import asyncio
from pathlib import Path

class Manager:
    def __init__(self, repo_root: str) -> None: ...
    # repo_root: 绝对路径
    # worktree_dir: <repo_root>/.gcode/worktrees
    # session_file: <repo_root>/.gcode/worktree_session.json
    # symlink_dirs: 默认 ["node_modules", ".venv", "vendor"]
    # lock: asyncio.Lock
    # active: dict[str, Worktree]
    # current_session: WorktreeSession | None

    async def create(self, name: str, base_ref: str, manual: bool) -> Worktree: ...
    async def enter(self, name: str) -> WorktreeSession: ...
    async def exit(self, name: str, action: "ExitAction", opts: "ExitOptions") -> "ExitReport": ...
    async def remove(self, name: str, opts: "ExitOptions") -> None: ...
    async def auto_cleanup(self, name: str) -> "AutoCleanupReport": ...
    async def sweep_stale(self, cutoff: "datetime") -> list[str]: ...
    def list(self) -> list[Worktree]: ...
    def get(self, name: str) -> Worktree | None: ...
    def current_session(self) -> WorktreeSession | None: ...
```

### worktree 辅助类型

```python
from enum import Enum

class ExitAction(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"

@dataclass
class ExitOptions:
    discard_changes: bool = False

@dataclass
class ExitReport:
    removed: bool
    path: str
    branch: str

@dataclass
class AutoCleanupReport:
    kept: bool
    path: str = ""
    branch: str = ""

class WorktreeHasChangesError(Exception):
    """Worktree 有未提交修改或本地多于 base 的 commit。"""
```

### tool ctx 帮助函数

```python
# src/gcode/tool/ctx.py
import contextvars
from contextlib import contextmanager
from pathlib import Path

_ctx_cwd: contextvars.ContextVar[str | None] = contextvars.ContextVar("cwd", default=None)

@contextmanager
def with_cwd(directory: str):
    if not directory:
        yield
        return
    token = _ctx_cwd.set(directory)
    try:
        yield
    finally:
        _ctx_cwd.reset(token)

def cwd_from_ctx() -> str | None:
    return _ctx_cwd.get()

def resolve_path(p: str) -> str:
    base = _ctx_cwd.get() or str(Path.cwd())
    if not p:
        return base
    pp = Path(p)
    if pp.is_absolute():
        return str(pp)
    return str(Path(base) / pp)
```

### subagent.Definition 扩展

```python
@dataclass
class Definition:
    # ... 既有字段 ...
    isolation: str = ""  # "" 或 "worktree"
```

## 模块设计### `gcode.worktree`(新子包)**职责:** Worktree 完整生命周期管理 + Slug 校验 + 后台清理。
**对外接口:** Manager(含上面所列方法)+ validate_slug + WorktreeHasChangesError 等导出常量/类型。
**依赖:** 标准库 + `asyncio.create_subprocess_exec` 调 git。
**关键内部函数:**
- `validate_slug(name: str) -> None` (失败抛 ValueError)
- `flat_slug(name: str) -> str` (`/` → `+`)
- `_perform_post_creation_setup(repo_root, wt_path, symlink_dirs)`
- `_has_worktree_changes(wt_path, base_commit) -> bool` (fail-closed)
- `_resolve_head_sha_from_fs(wt_path) -> str | None` (快速恢复)
- `_read_worktree_include(repo_root) -> list[str]`
- `_list_ignored_files(repo_root) -> list[str]`
- `_run_git(work_dir, *args) -> str` (统一 env: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=""`,stdin 关闭)
- `random_agent_name() -> str` (用于 SubAgent 临时 worktree 名)

**文件:**
- `__init__.py` — 公开导出 Manager / validate_slug / WorktreeHasChangesError 等
- `manager.py` — Manager 类型 + 主要方法骨架
- `create.py` — Create + 快速恢复 + 创建后设置
- `lifecycle.py` — enter / exit / remove / auto_cleanup
- `sweep.py` — sweep_stale
- `slug.py` — validate_slug + flat_slug
- `session.py` — WorktreeSession + 持久化(JSON 原子写)
- `git.py` — `_run_git` helper、`_resolve_head_sha_from_fs`、`_has_worktree_changes`
- 测试统一在 `tests/test_worktree_*.py`

### `gcode.tool` 改造**职责:** 增加 ctx cwd 传递机制,改造 6 个工具用 resolve_path / 子进程 cwd 参数。
**对外接口:** with_cwd / cwd_from_ctx / resolve_path(新增);6 个工具 execute 行为变更但 schema 不变。
**依赖:** 无新增。

**文件改动:**
- `ctx.py` — 新增
- `read_file.py` / `write_file.py` / `edit_file.py` — 在 `Path(...).stat()` / `read_text` / `write_text` 前用 `resolve_path(args.path)`
- `glob.py` — root 解析改 `resolve_path`
- `grep.py` — 同 glob
- `bash.py` — `asyncio.create_subprocess_exec(..., cwd=resolve_path(""))` (即 cwd 本身,空字符串解析为 cwd)

### `gcode.subagent` 改造**职责:** Definition 加 isolation 字段;parser 解析。
**改动:**
- `parser.py` — frontmatter 字典中读 `isolation` 字段,合法值 `""` / `"worktree"`,其他值 stderr 警告回落空
- `definition.py` — `Definition` 加 `isolation: str = ""`

### `gcode.agent` 改造**职责:** AgentTool 增加 worktree 分支,接受 Manager。
**改动:**
- `agent_tool.py`:
  - `AgentTool` 加属性 `worktree_mgr: worktree.Manager | None`
  - `AgentTool.__init__(..., worktree_mgr=None)`(签名末尾追加)
  - `execute` 内 `definition.isolation == "worktree"` 时走 `self._execute_with_worktree(...)`
- 新增 `agent_worktree.py`:
  - `_execute_with_worktree(definition, sub_agent, sub_conv, prompt, events) -> str`(async)
  - `build_worktree_notice(parent_cwd: str, wt_path: str) -> str`
  - 直接 `from gcode.worktree import random_agent_name`(worktree 包不依赖 agent,无导入循环)

### `gcode.command` 新增**职责:** `/worktree` 一级命令 + 子命令解析。
**改动:**
- `builtins.py` 增加 `registry.register(Command(name="worktree", ...))`
- 新增 `builtin_worktree.py`(handler 内自己 split 子命令 + 参数)
- `ui.py` 加 UI 协议方法 `worktree_accessor() -> WorktreeAccessor | None`(返回一个轻量协议,屏蔽 worktree 包反向依赖)

**UI 接口扩展:**

```python
# gcode/command/ui.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class WorktreeSummary:
    name: str
    path: str
    branch: str
    active: bool
    manual: bool

class WorktreeAccessor(Protocol):
    async def create(self, name: str) -> tuple[str, str]: ...   # (path, branch)
    def list(self) -> list[WorktreeSummary]: ...
    async def enter(self, name: str) -> None: ...
    async def exit(self, action: str, discard: bool) -> bool: ...  # removed
    async def remove(self, name: str, discard: bool) -> None: ...

class UI(Protocol):
    # ... 既有方法 ...
    def worktree_accessor(self) -> WorktreeAccessor | None: ...
```

### `gcode.tui` 改造**职责:** 持有 Manager 引用,把 active_cwd 注入主 Agent ctx。
**改动:**
- `app.py` `GCodeApp` 加属性 `worktree_mgr: worktree.Manager | None`、`active_cwd: str = ""`(空表示进程 cwd)
- `GCodeApp.__init__` 接收 `worktree_mgr`(或通过依赖注入)
- 在 App 的 run_once / submit 入口前,用 `with with_cwd(self._effective_cwd()):` 包住主 Agent Run 调用
- `_effective_cwd()` 返回 `self.active_cwd` 或 `str(Path.cwd())`
- 实现 `worktree_accessor()` 方法,返回一个适配 worktree.Manager 的实例
- 启动时(`GCodeApp.__init__` 内)若 Manager 的 `current_session()` 非 None,把 `self.active_cwd = session.worktree_path`

### `src/gcode/cli.py` / `__main__.py` 改造

```python
# 紧跟 subagent_catalog = load_subagent_catalog(root) 之后
try:
    worktree_mgr = worktree.Manager(root)
except Exception as exc:
    print(f"Worktree 管理器降级: {exc}", file=sys.stderr)
    worktree_mgr = None
else:
    # 后台跑过期清理,不阻塞启动
    asyncio.get_event_loop().create_task(
        worktree_mgr.sweep_stale(datetime.now() - timedelta(hours=24))
    )

agent_tool = AgentTool(
    catalog=subagent_catalog,
    task_mgr=task_mgr,
    parent=None,
    bg_enabled=cfg.enable_subagent_background,
    worktree_mgr=worktree_mgr,
)

app = GCodeApp(
    # ... 既有参数 ...
    worktree_mgr=worktree_mgr,
)
```

## 模块交互**SubAgent + Worktree 启动链路:**

```
主 Agent 调 Agent 工具
  ↓
AgentTool.execute
  ↓
definition.isolation == "worktree"?
  ↓ yes
_execute_with_worktree:
  1. name = "agent-a" + random_hex(7)
  2. wt = await worktree_mgr.create(name, "HEAD", manual=False)
  3. notice = build_worktree_notice(parent_cwd, wt.path)
  4. task_text = notice + "\n\n" + prompt
  5. with with_cwd(wt.path):
  6.     final_text = await sub_agent.run_to_completion(sub_conv, task_text, events)
  7. report = await worktree_mgr.auto_cleanup(name)
  8. if report.kept: final_text += f"\n[Worktree 保留: {report.path}]"
  9. return final_text
```

**工具调用的 cwd 解析链路:**

```
模型调 read_file(path="server.py")
  ↓
agent.execute → registry.execute("read_file", args)
  ↓
read_file_tool.execute(args)
  ↓
abs = tool.resolve_path("server.py")
  ↓
ContextVar cwd 非空 → abs = cwd + "/server.py"
ContextVar cwd 为空 → abs = 进程 cwd + "/server.py"
  ↓
Path(abs).read_text()
```

**TUI 主 Agent Run 入口:**

```
async def run_once(self):
    cwd = self.active_cwd or str(Path.cwd())
    with with_cwd(cwd):
        events = self.agent.run(self.conv, mode)
        async for evt in events:
            ...
```

## 文件组织

```
src/gcode/worktree/                — 新子包
├── __init__.py                       — 导出 Manager / validate_slug / 错误类型
├── manager.py                        — Manager 类型 + 构造
├── create.py                         — create + 快速恢复 + post-creation setup
├── lifecycle.py                      — enter / exit / remove / auto_cleanup
├── sweep.py                          — sweep_stale
├── slug.py                           — validate_slug + flat_slug
├── session.py                        — WorktreeSession + JSON 持久化
└── git.py                            — _run_git / _has_worktree_changes / _resolve_head_sha_from_fs

src/gcode/tool/
├── ctx.py                            — 新增 with_cwd/cwd_from_ctx/resolve_path
├── bash.py                           — 改造:子进程 cwd=resolve_path("")
├── read_file.py                      — 改造:用 resolve_path
├── write_file.py                     — 改造:用 resolve_path
├── edit_file.py                      — 改造:用 resolve_path
├── glob.py                           — 改造:用 resolve_path
└── grep.py                           — 改造:用 resolve_path

src/gcode/subagent/
├── definition.py                     — 加 isolation 字段
└── parser.py                         — 解析 isolation:

src/gcode/agent/
├── agent_tool.py                     — execute 加 isolation 分支
└── agent_worktree.py                 — 新增:_execute_with_worktree + notice 构造

src/gcode/command/
├── builtin_worktree.py               — 新增:/worktree handler
├── builtins.py                       — 增加 registry.register
└── ui.py                             — 加 WorktreeAccessor 协议

src/gcode/tui/
├── app.py                            — 加 worktree_mgr / active_cwd / cwd 注入
└── worktree_adapter.py               — 实现 WorktreeAccessor(适配 worktree.Manager)

tests/
├── test_worktree_slug.py
├── test_worktree_manager.py
├── test_worktree_create.py
├── test_worktree_lifecycle.py
├── test_worktree_sweep.py
├── test_worktree_git.py
├── test_tool_ctx.py
├── test_subagent_parser.py           — 新增 isolation case
└── test_agent_worktree.py

src/gcode/cli.py / __main__.py      — 接入

.gitignore                            — 追加两行
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| cwd 传递方式 | `contextvars.ContextVar` + with_cwd 上下文管理器 | 已有 ContextVar 范式承载 conv / subagent_depth,Tool schema 不变,prompt cache 不抖动 |
| Worktree 目录位置 | `.gcode/worktrees/<flat_slug>/` | README 既定方案;仓库内 + .gitignore 不追踪 |
| 嵌套 slug `/` 处理 | 替换为 `+`(flat_slug)做文件系统/分支名 | Git 分支的 `/` 是命名空间分隔符,会导致 `worktree-team/alice` 与 `worktree-team` 的 D/F 冲突 |
| Manager 构造失败处理 | 抛异常,gcode 降级 worktree_mgr=None | 不阻塞 gcode 启动;后续 isolation:worktree 调用回错误信息 |
| 快速恢复 | 纯 fs read,不调 git | README 说明大仓库 git fetch 6-8s,fs read 3ms;场景:同一 SubAgent 反复进同 worktree |
| 创建后设置失败处理 | 仅 stderr 警告 | 都是 best-effort,失败 ≠ 不可用 |
| `-B` vs `-b` | `-B`(重置) | 上次残留的孤儿分支不会让 create 失败 |
| `await asyncio.sleep(0.1)` 在 remove | 保留 | README 指出 git lockfile 竞态;100ms 是经验值 |
| os.chdir 使用场景 | 仅 Manager.exit 兜底一次 | 其他全部 explicit cwd;避免进程级 cwd 成为同步点 |
| 后台清理触发时机 | gcode 启动时跑一次,asyncio.create_task 后台执行 | 不阻塞主流程;ch11 已有 session.clean_expired 同样做法 |
| `.worktreeinclude` 缺失行为 | 跳过 D 步骤,不报错 | 大多数项目没这文件 |
| `subagent.isolation` 默认值 | `""`(无隔离) | 不破坏 ch13 既有定义文件 |
| 临时 worktree 命名 | `agent-a<7hex>` | README 既定;sweep_stale 正则匹配 |
| Manager 用 asyncio.Lock 而非 threading.Lock | 整个项目跑在 asyncio 事件循环上,异步友好 | 子进程调用都是 await,避免线程锁阻塞事件循环 |
| `WorktreeAccessor` 协议在 command 包 | 隔离 worktree 包反向依赖 | command 包不应该导入 worktree(已经导入 permission + llm,加 worktree 是技术债) |
| TUI active_cwd 字段 | 字符串,空 = 进程 cwd | 既有 `self.cwd` 已是字符串字段,与之并存避免改 schema |
| `--resume` 与 worktree session | Manager.__init__ 内统一处理 | 启动时自动读 session,session 失效自动清空 |
| Linux/macOS 跨平台 | symlink 用 os.symlink | 跨 POSIX 平台一致;Windows 失败时 best-effort 跳过 |
| git 子进程调用 | `asyncio.create_subprocess_exec` | 不阻塞事件循环;统一注入 env 与 stdin=DEVNULL |
| 子 Agent 临时名随机源 | `secrets.token_hex(4)[:7]` | 标准库,加密强随机,7 位 hex 与正则一致 |
````

````markdown
# Worktree 隔离 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gcode/worktree/__init__.py` | 公开导出 Manager / validate_slug / 错误类型 |
| 新建 | `src/gcode/worktree/slug.py` | validate_slug + flat_slug |
| 新建 | `tests/test_worktree_slug.py` | Slug 校验单测 |
| 新建 | `src/gcode/worktree/session.py` | WorktreeSession + JSON 原子持久化 |
| 新建 | `src/gcode/worktree/git.py` | _run_git + _has_worktree_changes + _resolve_head_sha_from_fs |
| 新建 | `tests/test_worktree_git.py` | git helper 单测 |
| 新建 | `src/gcode/worktree/manager.py` | Manager 类型 + 构造 + list/get/current_session |
| 新建 | `src/gcode/worktree/create.py` | create + 快速恢复 + post-creation setup A/B/C/D |
| 新建 | `tests/test_worktree_create.py` | create + setup 单测 |
| 新建 | `src/gcode/worktree/lifecycle.py` | enter / exit / remove / auto_cleanup |
| 新建 | `tests/test_worktree_lifecycle.py` | 生命周期单测 |
| 新建 | `src/gcode/worktree/sweep.py` | sweep_stale + 三层过滤 |
| 新建 | `tests/test_worktree_sweep.py` | sweep_stale 单测 |
| 新建 | `tests/test_worktree_manager.py` | Manager 构造 + session 持久化测试 |
| 新建 | `src/gcode/tool/ctx.py` | with_cwd / cwd_from_ctx / resolve_path |
| 新建 | `tests/test_tool_ctx.py` | resolve_path 单测 |
| 修改 | `src/gcode/tool/read_file.py` | 用 resolve_path 解析 path |
| 修改 | `src/gcode/tool/write_file.py` | 用 resolve_path 解析 path |
| 修改 | `src/gcode/tool/edit_file.py` | 用 resolve_path 解析 path |
| 修改 | `src/gcode/tool/glob.py` | 用 resolve_path 解析 root |
| 修改 | `src/gcode/tool/grep.py` | 用 resolve_path 解析 path |
| 修改 | `src/gcode/tool/bash.py` | 子进程 cwd=resolve_path("") |
| 修改 | `src/gcode/subagent/definition.py` | Definition 加 isolation 字段 |
| 修改 | `src/gcode/subagent/parser.py` | 解析 isolation: frontmatter |
| 修改 | `tests/test_subagent_parser.py` | 增加 isolation 单测 |
| 新建 | `src/gcode/agent/agent_worktree.py` | _execute_with_worktree + build_worktree_notice |
| 修改 | `src/gcode/agent/agent_tool.py` | 增加 worktree_mgr 字段 + isolation 分支 |
| 新建 | `tests/test_agent_worktree.py` | _execute_with_worktree 单测(用 stub Manager) |
| 修改 | `src/gcode/command/ui.py` | 加 WorktreeAccessor 协议 + WorktreeSummary |
| 新建 | `src/gcode/command/builtin_worktree.py` | /worktree handler + 子命令解析 |
| 修改 | `src/gcode/command/builtins.py` | 注册 /worktree |
| 修改 | `tests/test_command_builtins.py` | 加 worktree 注册测试 |
| 新建 | `src/gcode/tui/worktree_adapter.py` | 实现 WorktreeAccessor 适配 worktree.Manager |
| 修改 | `src/gcode/tui/app.py` | worktree_mgr / active_cwd 字段 + 注入 ctx |
| 修改 | `src/gcode/cli.py` | 构造 Manager + 注入 AgentTool / App + sweep_stale |
| 修改 | `.gitignore` | 追加 .gcode/worktrees/ + worktree_session.json |

## T1: Slug 校验**文件:** `src/gcode/worktree/slug.py` + `tests/test_worktree_slug.py`
**依赖:** 无
**步骤:**
1. 创建子包 `gcode.worktree`,加 `__init__.py`(暂时空导出,后续 T 步骤补)
2. 实现 `validate_slug(name: str) -> None`,规则:非空、长度 ≤ 64、按 `/` 切段后每段匹配 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`、无连续 `//`、无首末 `/`;失败抛 `ValueError(<具体原因>)`
3. 实现 `flat_slug(name: str) -> str`:`name.replace("/", "+")`
4. 写测试覆盖合法/非法 case:`alice`、`team/alice`、`v1.0`、`a_b`(合法);空、超长、`..`、`./x`、`a//b`、`/x`、`a/`、`a b`、`a;b`(非法,断言 `pytest.raises(ValueError)`)

**验证:** `pytest tests/test_worktree_slug.py -v`

## T2: WorktreeSession 持久化**文件:** `src/gcode/worktree/session.py`
**依赖:** T1
**步骤:**
1. 定义 `WorktreeSession` dataclass,字段按 spec F3,JSON 序列化用 `dataclasses.asdict + json.dumps`
2. 实现 `load_session(path: Path) -> WorktreeSession | None`:文件不存在返回 None;内容为 `null` 或空返回 None;JSON 解析失败抛异常
3. 实现 `save_session(path: Path, session: WorktreeSession | None) -> None`:session=None 时写 `null`;原子写——先写 `path.with_suffix(path.suffix + ".tmp")` 再 `os.replace`
4. 实现 `clear_session(path: Path)`(等同 `save_session(path, None)`)

**验证:** 在 test_worktree_manager.py T9 中覆盖

## T3: Git helper**文件:** `src/gcode/worktree/git.py` + `tests/test_worktree_git.py`
**依赖:** 无
**步骤:**
1. 实现 `async def _run_git(work_dir: str, *args: str) -> str`:用 `asyncio.create_subprocess_exec("git", *args, cwd=work_dir, env=..., stdin=DEVNULL, stdout=PIPE, stderr=PIPE)`,env 注入 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`(在 `os.environ` 副本基础上),`await proc.communicate()`,返回 stdout decode 并 rstrip 换行;失败抛 `RuntimeError(stderr)`
2. 实现 `async def _has_worktree_changes(wt_path: str, base_commit: str) -> bool`:① `git -C status --porcelain` 非空 ② `git -C rev-list --count <base_commit>..HEAD` >0;任一 git 命令本身出错 fail-closed 返回 True
3. 实现 `_resolve_head_sha_from_fs(wt_path: str) -> str | None`:读 `wt_path/.git` 取 `gitdir: <path>`,读 `<gitdir>/HEAD`,若是 `ref: refs/heads/<name>`,读 `<gitdir>/<refpath>` 拿 SHA;失败返回 None
4. 测试:用一个临时 git 仓库做真实 Worktree,断言上述函数行为(可用 `pytest.fixture` + `subprocess.run` 准备 fixture)

**验证:** `pytest tests/test_worktree_git.py -v`

## T4: Manager 构造**文件:** `src/gcode/worktree/manager.py` + `tests/test_worktree_manager.py`
**依赖:** T2, T3
**步骤:**
1. 定义 `Manager` 类(spec F4 字段) + 模块常量 `DEFAULT_SYMLINK_DIRS = ["node_modules", ".venv", "vendor"]`
2. 实现 `Manager.__init__(self, repo_root: str)`:
   - `self.repo_root = str(Path(repo_root).resolve())`
   - 同步跑 `subprocess.run(["git", "-C", repo_root, "rev-parse", "--show-toplevel"], capture_output=True, text=True)`,输出与 repo_root 不匹配则抛 `ValueError("not a git repo root")`
   - 初始化 `worktree_dir`、`session_file`、`active = {}`、`lock = asyncio.Lock()`
   - `Path(worktree_dir).mkdir(parents=True, exist_ok=True)`
   - 调 `load_session(session_file)`;若 session 非 None 但其 worktree_path 不存在,清空 session 并 stderr 警告
   - 扫描 `worktree_dir` 子目录,对每个非空目录用 `_resolve_head_sha_from_fs` 填 `active`(快速恢复路径,不调 git)
3. 实现 `list() -> list[Worktree]`(按 name 排序)、`get(name) -> Worktree | None`、`current_session() -> WorktreeSession | None`
4. 测试:在临时 git 仓库构造 Manager,断言 worktree_dir 创建、空 session 时 current_session()=None、预放 session 文件能被加载、Worktree 目录不存在时 session 被清空

**验证:** `pytest tests/test_worktree_manager.py -v`

## T5: create + 快速恢复 + 创建后设置**文件:** `src/gcode/worktree/create.py` + `tests/test_worktree_create.py`
**依赖:** T4
**步骤:**
1. 实现 `async def create(self, name, base_ref, manual) -> Worktree`(挂在 Manager 上,可用 mixin 或 import 后绑定):
   - `validate_slug(name)` 不通过即抛 ValueError
   - `async with self.lock:`;`active[name]` 存在即抛 ValueError
   - 算 `flat = flat_slug(name)`、`wt_path = self.worktree_dir / flat`、`branch = f"worktree-{flat}"`
   - 若 `wt_path.exists()`,用 `_resolve_head_sha_from_fs` 取 sha,构造 Worktree 放 active,**直接返回**(快速恢复,跳过 setup)
   - 否则跑 `await _run_git(self.repo_root, "worktree", "add", "-B", branch, str(wt_path), base_ref)`
   - 失败时:`shutil.rmtree(wt_path, ignore_errors=True)`,重新抛异常
   - 调 `await _perform_post_creation_setup(self.repo_root, wt_path, self.symlink_dirs)`,内部每个子步骤 try/except 仅 stderr 警告
   - 跑 `head_sha = await _run_git(wt_path, "rev-parse", "HEAD")` 拿 head SHA
   - 构造 Worktree(`name, path=str(wt_path), branch, based_on=base_ref, head_commit=head_sha, created=datetime.now(), manual`)放 active,返回
2. 实现 `async def _perform_post_creation_setup(repo_root, wt_path, symlink_dirs)`:四个子函数:
   - `copy_local_configs(repo_root, wt_path)`:对 `.gcode/config.yaml` / `.gcode/settings.local.yaml`,若主仓存在且 Worktree 不存在,`shutil.copy`
   - `setup_git_hooks(repo_root, wt_path)`:优先 `.husky/`,回退 `git -C <repo_root> config --get core.hooksPath` 拿主仓配置,若有值跑 `git -C <wt_path> config core.hooksPath <绝对路径>`
   - `symlink_large_dirs(repo_root, wt_path, symlink_dirs)`:对每个目录若主仓存在且 Worktree 不存在,`os.symlink(Path(repo_root)/dir, Path(wt_path)/dir)`
   - `copy_included_ignored(repo_root, wt_path)`:读 `.worktreeinclude` 模式;跑 `git -C <repo_root> ls-files --others --ignored --exclude-standard --directory` 列出忽略文件;每个文件用 `fnmatch.fnmatch` 对模式;命中则 `shutil.copy` 到 Worktree
   - 每个子函数 try/except 失败只往 stderr 写一行 `worktree: setup <step>: <err>` 警告,继续下个步骤
3. 测试:在临时 git 仓库覆盖:create 成功后目录存在、分支存在、设置 A 复制 settings.local.yaml、设置 C 软链 node_modules、设置 D 按 .worktreeinclude 复制 .env;快速恢复路径不调 git(可用 monkeypatch 替换 `_run_git` 断言未被调用)

**验证:** `pytest tests/test_worktree_create.py -v`

## T6: enter / exit / remove / auto_cleanup**文件:** `src/gcode/worktree/lifecycle.py` + `tests/test_worktree_lifecycle.py`
**依赖:** T5
**步骤:**
1. 实现 `ExitAction`(str Enum)、`ExitOptions`、`ExitReport`、`AutoCleanupReport` 类型与 `WorktreeHasChangesError`
2. 实现 `async def enter(self, name) -> WorktreeSession`:
   - `async with self.lock:`,取 `active[name]`
   - `original_cwd = str(Path.cwd())`
   - `original_branch = await _run_git(self.repo_root, "rev-parse", "--abbrev-ref", "HEAD")` 与 `original_head = await _run_git(self.repo_root, "rev-parse", "HEAD")`(try/except 失败用空字符串兜底)
   - 生成 `session_id = secrets.token_hex(8)`(保证唯一)
   - 写 `self.current_session` 字段,持久化 `save_session`
3. 实现 `async def exit(self, name, action, opts) -> ExitReport`:
   - `async with self.lock:`;校验 `current_session` 非空且 `worktree_name == name`;否则抛 ValueError
   - 取 `active[name]`;若 None 抛 ValueError
   - `action=REMOVE` 且 `not opts.discard_changes`:调 `_has_worktree_changes`,True 则抛 `WorktreeHasChangesError`
   - `os.chdir(current_session.original_cwd)` 兜底(`contextlib.suppress(OSError)` 包住)
   - `self.current_session = None`,`save_session(session_file, None)`
   - `action=REMOVE`:`await _run_git(self.repo_root, "worktree", "remove", "--force", wt.path)`,`await asyncio.sleep(0.1)`,`await _run_git(self.repo_root, "branch", "-D", wt.branch)`,`del active[name]`
   - 返回 `ExitReport(removed=action==REMOVE, path=wt.path, branch=wt.branch)`
4. 实现 `async def remove(self, name, opts)`:类似 exit 的 remove 分支,但允许非当前 session;变更保护同
5. 实现 `async def auto_cleanup(self, name) -> AutoCleanupReport`:
   - 取 `active[name]`;`manual=True` 直接 `AutoCleanupReport(kept=True, path=wt.path, branch=wt.branch)`
   - `_has_worktree_changes` 为 False 调 `remove(name, ExitOptions(discard_changes=True))`,返回 `AutoCleanupReport(kept=False)`
   - 有变更:`AutoCleanupReport(kept=True, path=wt.path, branch=wt.branch)`
6. 测试:enter 不改进程 cwd、exit 切回 cwd、exit remove 变更保护、auto_cleanup manual/无变更/有变更三种分支(用 `pytest.mark.asyncio`)

**验证:** `pytest tests/test_worktree_lifecycle.py -v`

## T7: sweep_stale**文件:** `src/gcode/worktree/sweep.py` + `tests/test_worktree_sweep.py`
**依赖:** T6
**步骤:**
1. 在 sweep.py 定义 `EPHEMERAL_PATTERN = re.compile(r"^agent-a[0-9a-f]{7}$")`
2. 实现 `async def sweep_stale(self, cutoff: datetime) -> list[str]`:
   - 遍历 `Path(self.worktree_dir).iterdir()`
   - 对每个目录:不匹配 pattern 跳过;`datetime.fromtimestamp(p.stat().st_mtime) > cutoff` 跳过;`current_session.worktree_path == str(p)` 跳过
   - 跑 `await _has_worktree_changes(p, "HEAD")`(base 用 HEAD 比较是否有自己提交的 commit——README 说要查未提交修改 + 未推送 commit;这里 base 用 head 等价于只查 status,unpushed 单独跑)
   - 实际实现:① status --porcelain 非空跳过 ② `git rev-list --max-count=1 HEAD --not --remotes` 非空跳过
   - 通过的:调 `remove(name, ExitOptions(discard_changes=True))`,记 removed.append(name)
3. 实现 `random_agent_name() -> str`(返回 `"agent-a" + secrets.token_hex(4)[:7]`)
4. 测试:构造三个目录(匹配模式无变更、匹配模式有变更、不匹配模式),sweep_stale 只删第一个

**验证:** `pytest tests/test_worktree_sweep.py -v`

## T8: tool ctx**文件:** `src/gcode/tool/ctx.py` + `tests/test_tool_ctx.py`
**依赖:** 无(并行 T1-T7)
**步骤:**
1. 在 `src/gcode/tool/ctx.py` 定义 `_ctx_cwd: ContextVar[str | None] = ContextVar("cwd", default=None)`
2. 实现 `with_cwd(directory: str)` 作为 `@contextmanager`:`directory==""` 时直接 yield 不变;否则 `token = _ctx_cwd.set(directory); try yield finally _ctx_cwd.reset(token)`
3. 实现 `cwd_from_ctx() -> str | None`(返回 `_ctx_cwd.get()`)
4. 实现 `resolve_path(p: str) -> str`:
   - `base = _ctx_cwd.get() or str(Path.cwd())`
   - `p` 为空:返回 base
   - `Path(p).is_absolute()`:返回 `str(Path(p))`
   - 否则:返回 `str(Path(base) / p)`
5. 测试:覆盖三种 path、ctx 无 cwd 时回落到进程 cwd、空字符串返回 cwd 本身

**验证:** `pytest tests/test_tool_ctx.py -v`

## T9: 改造 6 个核心工具**文件:** `src/gcode/tool/{bash,read_file,write_file,edit_file,glob,grep}.py`
**依赖:** T8
**步骤:**
1. `read_file.py`:在 `Path(args.path).stat()` / `read_text()` 前 `abs_path = resolve_path(args.path)`,后续用 `Path(abs_path)`
2. `write_file.py`:同样改造 path 参数;若需要 `mkdir(parents=True)` 时也用 abs
3. `edit_file.py`:同样
4. `glob.py`:`root = args.path or "."`;然后 `root = resolve_path(root)`;`Path(root).rglob(...)` 用 abs root;返回路径仍按相对 root 输出(保持现有行为)
5. `grep.py`:与 glob 同
6. `bash.py`:在 `asyncio.create_subprocess_exec / subprocess.Popen` 调用上设 `cwd=resolve_path("")`(空字符串解析为 cwd 本身)
7. 不改 schema(`Tool.parameters` 不变),不改 description
8. 单测:构造 `with with_cwd(tmp_dir):` 到临时目录,在临时目录里准备文件,调工具断言读到对应内容

**验证:** `pytest tests/test_tool*.py -v`

## T10: subagent.Definition.isolation**文件:** `src/gcode/subagent/{definition,parser}.py` + `tests/test_subagent_parser.py`
**依赖:** 无
**步骤:**
1. `definition.py`:`Definition` dataclass 加 `isolation: str = ""` 字段
2. `parser.py`:frontmatter 字典中 `raw = fm.get("isolation", "")`,合法值 `""` / `"worktree"`,非法值 stderr 警告并回落 `""`,把结果填到 `definition.isolation`
3. `tests/test_subagent_parser.py`:增加测试覆盖 `isolation: worktree` 解析成功、`isolation: gibberish` 警告并回落空(用 `capsys` 断言 stderr 内容)

**验证:** `pytest tests/test_subagent_parser.py -v`

## T11: _execute_with_worktree**文件:** `src/gcode/agent/agent_worktree.py` + `tests/test_agent_worktree.py`
**依赖:** T6, T8, T10
**步骤:**
1. 新建 `agent_worktree.py`,顶部 `from gcode.worktree import Manager, random_agent_name`(worktree 包不依赖 agent,无导入循环)
2. 实现 `build_worktree_notice(parent_cwd: str, wt_path: str) -> str`(按 spec F22 模板)
3. 实现 `async def _execute_with_worktree(manager: Manager, definition, sub_agent, sub_conv, prompt: str, events) -> str`:
   - `name = random_agent_name()`
   - `wt = await manager.create(name, "HEAD", manual=False)`
   - `cwd = str(Path.cwd())`
   - `notice = build_worktree_notice(cwd, wt.path)`
   - `task_text = notice + "\n\n" + prompt`
   - `with with_cwd(wt.path):`
   - `    final_text = await sub_agent.run_to_completion(sub_conv, task_text, events)`
   - `report = await manager.auto_cleanup(name)`
   - 若 `report.kept`,把保留信息追加到 `final_text`
   - 返回 `final_text`
4. 单测:用一个真实临时 git 仓库构造 worktree.Manager;sub_agent 用 mock provider(返回空文本即结束);断言 wt.path 被传到 ctx(可在 run_to_completion 内打桩读 cwd_from_ctx)、auto_cleanup 被调用

**验证:** `pytest tests/test_agent_worktree.py -v`

## T12: AgentTool 接入 isolation 分支**文件:** `src/gcode/agent/agent_tool.py`
**依赖:** T11
**步骤:**
1. AgentTool 加属性 `worktree_mgr: Manager | None`
2. `__init__(self, catalog, task_mgr, parent, bg_enabled, worktree_mgr=None)`——签名末尾追加 worktree_mgr(允许 None 表示不启用)
3. 在 execute 内 `definition.isolation == "worktree"` 时:
   - 若 `self.worktree_mgr is None`,返回 `ToolResult(is_error=True, content="worktree manager not configured")`
   - 若 `background == True`:本期最小实现——**isolation:worktree 时强制前台同步**(忽略 background 字段);AgentTool 在 `definition.isolation == "worktree"` 时即使 background=True 也走 inline 分支;tool_result 返回最终文本
4. 在 inline 路径前,若 `definition.isolation == "worktree"`,调 `_execute_with_worktree(self.worktree_mgr, definition, sub_agent, sub_conv, args.prompt, events)` 替代直接 `run_to_completion`
5. 改 `src/gcode/cli.py` 的 `AgentTool` 构造调用,传入 `worktree_mgr`

**验证:** `pytest tests/test_agent_tool.py tests/test_agent_worktree.py -v`

## T13: command 包加 WorktreeAccessor + /worktree handler**文件:** `src/gcode/command/ui.py` + `src/gcode/command/builtin_worktree.py` + `src/gcode/command/builtins.py` + `tests/test_command_builtins.py`
**依赖:** T6
**步骤:**
1. `ui.py`:加 `WorktreeSummary` dataclass + `WorktreeAccessor` Protocol(spec F24-F28 所列方法);`UI` Protocol 加 `worktree_accessor() -> WorktreeAccessor | None`;`nop_ui` 实现返回 None
2. `builtin_worktree.py`:实现 `async def handle_worktree(ui, args: str) -> None`——args 是 `/worktree` 后面的全部尾随字符串;split 子命令 + 其余参数
   - `create <slug>` → `await ui.worktree_accessor().create(slug)`,输出 `Worktree 已创建: <path> (分支 <branch>)`
   - `list` → 遍历 `list()`,按格式输出
   - `enter <slug>` → `await enter(slug)`,输出 `已进入 <slug>: <path>`
   - `exit [--remove] [--discard]` → 解析 flag,调 `exit`
   - `remove <slug> [--discard]` → 调 `remove`
   - 未知子命令报错
3. `builtins.py`:注册 `Command(name="worktree", kind=KindLocal, args_handler=handle_worktree)`——给 `Command` 加可选字段 `args_handler: Callable[[UI, str], Awaitable[None]] | None`,Registry.dispatch 时若命中支持 args 的命令则走 args_handler;dispatcher 在解析 `/worktree create foo` 时,把 head=`worktree`、tail=`create foo` 传给 args_handler
4. **最小改动机制:** 修改 `command/parse.py`(或 dispatch 入口):在解析输入时,若命令名命中已注册命令,把尾随字符串作为 args 透传;`Command` 区分 `handler` (无参) 与 `args_handler` (带 args)
5. 测试:测试 handle_worktree 分发逻辑(用 stub UI / stub Accessor)

**验证:** `pytest tests/test_command_builtins.py -v -k worktree`

## T14: TUI 适配 + 注入 ctx**文件:** `src/gcode/tui/worktree_adapter.py` + `src/gcode/tui/app.py`
**依赖:** T11, T13
**步骤:**
1. `worktree_adapter.py`:实现 `WorktreeAdapter(WorktreeAccessor)`,内部持 `worktree.Manager` 与一个 `set_active_cwd: Callable[[str], None]` 回调,把方法转发并组装 `WorktreeSummary` 列表;`enter` 内部既调 `Manager.enter`,又调 `set_active_cwd(session.worktree_path)`
2. `app.py`:`GCodeApp` 加属性 `worktree_mgr: worktree.Manager | None`、`active_cwd: str = ""`(空表示进程 cwd)
3. `GCodeApp.__init__` 接收 `worktree_mgr`;构造时若 `manager.current_session()` 非 None,设 `self.active_cwd = session.worktree_path`
4. 实现 `worktree_accessor()` 方法返回 WorktreeAdapter 实例(传 lambda 设置 self.active_cwd)
5. 在主 Agent Run 调用入口(找 app.py 里 `self.agent.run(conv, mode)` 调用点),前置 `with with_cwd(self._effective_cwd()):` 包住整个 run 协程
6. `_effective_cwd()`:若 `self.active_cwd` 非空返回 active_cwd,否则返回 `str(Path.cwd())`

**验证:** `python -m gcode` 可启动;`/worktree create x` + `/worktree enter x` + Read file(相对路径) 在 worktree 内成功

## T15: 主 cli 接入**文件:** `src/gcode/cli.py` + `.gitignore`
**依赖:** T4-T14 全部
**步骤:**
1. `cli.py`:在 `subagent_catalog = load_subagent_catalog(root)` 后加:
   ```python
   try:
       worktree_mgr = worktree.Manager(root)
   except Exception as exc:
       print(f"Worktree 管理器降级: {exc}", file=sys.stderr)
       worktree_mgr = None
   else:
       asyncio.get_event_loop().create_task(
           worktree_mgr.sweep_stale(datetime.now() - timedelta(hours=24))
       )
   ```
2. `AgentTool` 构造末尾追加 `worktree_mgr=worktree_mgr`
3. `GCodeApp` 构造新增 `worktree_mgr=worktree_mgr`
4. `.gitignore` 追加:
   ```
   # ch14: Worktree 隔离副本(仅供 SubAgent 与手动管理使用)
   .gcode/worktrees/
   .gcode/worktree_session.json
   ```

**验证:** `python -m gcode` 可启动、`pytest` 全过、`ruff check` 通过

## T16: 端到端 tmux 验证**文件:** 无代码修改,运行测试
**依赖:** T15
**步骤:**
1. `uv sync` 装好依赖(或 `pip install -e .`)
2. 准备项目级自定义 Agent `.gcode/agents/worktree-writer.md`(详见 checklist 场景 1)
3. tmux 启动 `python -m gcode`,跑 checklist 端到端场景
4. 通过即标记 T16 完成

**验证:** 见 checklist.md 场景 1-6

## 执行顺序

```
T1 (slug)
  ↓
T2 (session) — T3 (git helper) — T8 (tool/ctx)
                                    ↓
T4 (manager construct)          T9 (改造 6 tools)
  ↓
T5 (create + setup)
  ↓
T6 (lifecycle)
  ↓
T7 (sweep)
  ↓
T10 (subagent.isolation)
  ↓
T11 (agent_worktree + _execute_with_worktree)
  ↓
T12 (AgentTool 接入)
  ↓
T13 (/worktree command) — T14 (TUI 接入)
                              ↓
T15 (cli.py + .gitignore)
  ↓
T16 (tmux 端到端)
```

T1/T2/T3/T8 之间可并行;其余按依赖顺序。
````

````markdown
# Worktree 隔离 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### worktree 子包

- [ ] src/gcode/worktree 子包存在且可导入(验证:`python -c "from gcode import worktree"`)
- [ ] `validate_slug` 对合法/非法 case 行为符合 spec F1(验证:`pytest tests/test_worktree_slug.py -v`)
- [ ] `flat_slug("team/alice") == "team+alice"`(验证:同上)
- [ ] `WorktreeSession` JSON 序列化/反序列化字段名为下划线小写(验证:`pytest tests/test_worktree_manager.py -k session -v`)
- [ ] `save_session` 原子写——失败前不破坏既有文件;`save_session(path, None)` 写入 `null`(验证:同上)
- [ ] `_run_git` 设置 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`、stdin=DEVNULL(验证:`pytest tests/test_worktree_git.py -k run_git -v`)
- [ ] `_has_worktree_changes` 在临时 git 仓库内:无修改返回 False;改一个文件返回 True;git 命令出错 fail-closed 返回 True(验证:同上)
- [ ] `_resolve_head_sha_from_fs` 在真实 worktree 路径下返回 commit SHA(验证:`pytest tests/test_worktree_git.py -k resolve_head`)
- [ ] `Manager(repo_root)` 校验 repo_root 是 git 仓库;非 git 目录抛 ValueError(验证:`pytest tests/test_worktree_manager.py -k construct -v`)
- [ ] `Manager` 加载已存在的 session 文件;指向不存在目录的 session 自动清空(验证:同上)
- [ ] `manager.create("alice", "HEAD", manual=True)` 在 `.gcode/worktrees/alice/` 下落地 + 分支 `worktree-alice`(验证:`pytest tests/test_worktree_create.py`)
- [ ] `manager.create("team/alice", ...)` 落地 `.gcode/worktrees/team+alice/` + 分支 `worktree-team+alice`(验证:同上)
- [ ] `manager.create` 目录已存在时走快速恢复(不调 git;active 立即就绪)(验证:同上,可用 monkeypatch 替换 `_run_git` 断言未被调用)
- [ ] `manager.create` 已 active 名字时再 create 抛异常(验证:同上)
- [ ] 创建后设置 A——`.gcode/settings.local.yaml` 被复制到 Worktree(验证:同上,需在测试 fixture 准备文件)
- [ ] 创建后设置 B——主仓 `.husky/` 存在时 Worktree git config 含 core.hooksPath(验证:`pytest tests/test_worktree_create.py -k hooks`)
- [ ] 创建后设置 C——主仓 node_modules 存在时 Worktree 内为软链(`Path.is_symlink()` 为 True)(验证:`pytest tests/test_worktree_create.py -k symlink`)
- [ ] 创建后设置 D——主仓 `.worktreeinclude` 模式命中的 ignored 文件被复制到 Worktree(验证:`pytest tests/test_worktree_create.py -k include_ignored`)
- [ ] `manager.enter(name)` 不改变进程 `Path.cwd()`,返回 session 含 original_cwd/worktree_path/session_id 等字段(验证:`pytest tests/test_worktree_lifecycle.py -k enter`)
- [ ] `manager.enter` 持久化 session 到 `.gcode/worktree_session.json`(验证:同上)
- [ ] `manager.exit(name, REMOVE, ExitOptions())` 有变更时抛 `WorktreeHasChangesError`,Worktree 目录仍在(验证:`pytest tests/test_worktree_lifecycle.py -k exit`)
- [ ] `manager.exit(name, REMOVE, ExitOptions(discard_changes=True))` 成功删除 Worktree + 分支;session 文件被清空(验证:同上)
- [ ] `manager.exit` 调用了 `os.chdir(original_cwd)` 兜底(验证:测试时改进程 cwd 后调 exit,断言 cwd 回到 original)
- [ ] `manager.remove(name, ExitOptions())` 与 exit 的 remove 分支一致,但允许非当前 session(验证:同上)
- [ ] `manager.auto_cleanup` 对 manual=True 直接 kept=True(验证:`pytest tests/test_worktree_lifecycle.py -k auto_cleanup`)
- [ ] `manager.auto_cleanup` 无变更时 remove 并返回 kept=False;有变更返回 kept=True(验证:同上)
- [ ] `manager.sweep_stale` 第一层只识别 `agent-a[0-9a-f]{7}` 模式;手动命名跳过(验证:`pytest tests/test_worktree_sweep.py`)
- [ ] `manager.sweep_stale` 跳过当前 session 的目录(验证:同上)
- [ ] `manager.sweep_stale` 有未提交修改 / 未推送 commit 的目录跳过(fail-closed)(验证:同上)
- [ ] `worktree.random_agent_name` 返回形如 `agent-a[0-9a-f]{7}` 的字符串(验证:`pytest tests/test_worktree_sweep.py -k random_agent_name`)

### tool 包 ctx 改造

- [ ] `tool.with_cwd` / `cwd_from_ctx` / `resolve_path` 三函数存在(验证:`pytest tests/test_tool_ctx.py -v`)
- [ ] `resolve_path` 对绝对路径直接返回;对相对路径用 ctx cwd 或 `Path.cwd()` 拼接(验证:同上)
- [ ] `read_file(path="a.txt")` 在 `with with_cwd(tmp_dir):` 下读 tmp_dir/a.txt(验证:`pytest tests/test_tool_read_file.py -k cwd`)
- [ ] `write_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `edit_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `bash(command="pwd")` + ctx cwd 输出 cwd 路径(验证:`pytest tests/test_tool_bash.py -k cwd`)
- [ ] `glob(pattern="*.txt")` + ctx cwd 在 cwd 内搜索(验证:`pytest tests/test_tool_glob.py -k cwd`)
- [ ] `grep` + ctx cwd 同上(验证:`pytest tests/test_tool_grep.py -k cwd`)
- [ ] 工具 schema 不变——`Tool.parameters` 不含新字段(验证:对比 ch13 测试快照,或断言 keys)

### subagent 包扩展

- [ ] `subagent.Definition` 含 `isolation: str` 字段(验证:`pytest tests/test_subagent_definition.py`)
- [ ] `parse_definition` 正确解析 `isolation: worktree`(验证:`pytest tests/test_subagent_parser.py -k isolation -v`)
- [ ] 非法 `isolation` 值时 stderr 警告并回落 `""`(验证:同上,用 `capsys` 断言)
- [ ] 既有定义不写 isolation 时 `isolation == ""`(验证:同上)

### agent 包扩展

- [ ] `agent.AgentTool` 含 `worktree_mgr: worktree.Manager | None` 字段;`__init__` 签名末尾接收 worktree_mgr(验证:`python -c "from gcode.agent import AgentTool"`)
- [ ] `agent._execute_with_worktree` 调用 `manager.create` + `auto_cleanup`,期间通过 ctx 传 wt.path(验证:`pytest tests/test_agent_worktree.py -v`)
- [ ] `build_worktree_notice` 输出含 `<worktree-context>` 标签 + 父目录 + 工作目录(验证:同上)
- [ ] `AgentTool.execute` 在 `definition.isolation == "worktree"` 时走 worktree 分支(验证:同上)
- [ ] `AgentTool.execute` 在 `worktree_mgr is None` 且 isolation=worktree 时返回 `is_error=True`(验证:同上)
- [ ] `AgentTool.execute` 在 isolation=worktree + background=True 时强制走前台路径(验证:同上)

### command 包扩展

- [ ] `command.WorktreeSummary` 与 `WorktreeAccessor` Protocol 存在(验证:`python -c "from gcode.command.ui import WorktreeAccessor, WorktreeSummary"`)
- [ ] `UI` Protocol 加 `worktree_accessor()` 方法;`nop_ui` 返回 None(验证:同上)
- [ ] `/worktree` 命令被注册,lookup 命中(验证:`pytest tests/test_command_builtins.py -k worktree_registered`)
- [ ] `handle_worktree` 分发子命令 create/list/enter/exit/remove(验证:`pytest tests/test_command_builtins.py -k handle_worktree -v`)
- [ ] `handle_worktree` 在 `ui.worktree_accessor()` 返回 None 时报错(验证:同上)

### tui 包扩展

- [ ] `GCodeApp` 含 `worktree_mgr: worktree.Manager | None` 与 `active_cwd: str` 字段(验证:`python -c "from gcode.tui.app import GCodeApp"`)
- [ ] `GCodeApp.__init__` 接收 `worktree_mgr` 参数;启动时若 `manager.current_session()` 非 None,设 `active_cwd=session.worktree_path`(验证:`pytest tests/test_tui_app.py -k worktree`)
- [ ] 主 Agent Run 前用 `with with_cwd(...):` 包住——可通过 mock provider 断言 tool 调用收到的 cwd(验证:同上)
- [ ] worktree_adapter 实现 WorktreeAccessor 协议(验证:`python -c "from gcode.tui.worktree_adapter import WorktreeAdapter"`)

### cli 接入

- [ ] src/gcode/cli.py 构造 Manager,失败 stderr 警告 + 降级(验证:启动 gcode + 在非 git 目录测试)
- [ ] AgentTool 构造末尾追加 worktree_mgr(验证:同上)
- [ ] GCodeApp 构造接收 worktree_mgr(验证:同上)
- [ ] 启动时异步跑 sweep_stale(验证:`grep -n sweep_stale src/gcode/cli.py`)
- [ ] .gitignore 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`(验证:`git check-ignore .gcode/worktrees/test`)

## 集成

- [ ] subagent.Definition.isolation + agent.AgentTool 协同——isolation:worktree 的 SubAgent 启动时自动创建 Worktree(验证:test_agent_worktree 通过)
- [ ] tool ctx with_cwd + AgentTool._execute_with_worktree 协同——SubAgent 在 Worktree 内的工具调用使用 wt.path 作为 cwd(验证:集成测试,在临时 git repo 跑一个 mock subagent)
- [ ] 主 Agent 工具列表稳定——5 个核心工具 + Agent + TaskList + TaskGet + TaskStop + SendMessage + worktree 不暴露新工具(验证:工具数计数)
- [ ] worktree 包 + subagent 包 + agent 包 + command 包 + tui 包之间无导入循环(验证:`python -c "import gcode.tui.app, gcode.agent.agent_tool, gcode.command.builtins, gcode.worktree"`)

## 编译与测试

- [ ] 项目可启动:`python -m gcode --help`(或正常进 TUI)
- [ ] 所有单元测试通过:`pytest`
- [ ] lint 通过:`ruff check`(可选 `ruff format --check`)

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

**通用预置:**
- 当前目录 `cd /Users/codemelo/gcode`
- 已执行 `uv sync` 或 `pip install -e .`

### 场景 1:isolation:worktree 子 Agent 修改文件不影响主目录**预置:** 创建项目级自定义 Agent:

```
.gcode/agents/worktree-writer.md
---
name: worktree-writer
description: 在 Worktree 内写文件的测试 Agent
permission_mode: dontAsk
max_turns: 5
isolation: worktree
---

你是一个测试 Agent。当用户让你写文件时,直接用 write_file 工具写,不要询问。
```

并准备一个主目录文件 `echo "MAIN" > scratch_ch14.txt`(测试前 git status 干净,这个文件未跟踪)。

**步骤:**
- [ ] tmux 启动:`tmux new-session -d -s ch14 -x 200 -y 50 "python -m gcode"`
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『把 scratch_ch14.txt 的内容覆盖为 SUBAGENT,只用 write_file 工具』」
- [ ] 子 Agent 跑动,scrollback 出现 `Agent(...)` 行
- [ ] tool_result 中末尾含 `[Worktree 保留: .gcode/worktrees/agent-a... ,分支 worktree-agent-a...]`(因为有未提交修改,auto_cleanup 保留)
- [ ] **主目录** `cat scratch_ch14.txt` 仍为 `MAIN`(验证主目录未被改)
- [ ] **Worktree 副本** `cat .gcode/worktrees/agent-a*/scratch_ch14.txt` 为 `SUBAGENT`
- [ ] tmux 截屏断言:`tmux capture-pane -p -t ch14 | grep -i "worktree"`
- [ ] 清理:`rm scratch_ch14.txt`,删除残留 worktree:在 gcode 内 `/worktree remove agent-a... --discard`(或 `git worktree remove --force` 手动清)
- [ ] tmux kill-session -t ch14

### 场景 2:isolation:worktree 子 Agent 无变更时自动清理**预置:** 同场景 1 的 worktree-writer.md(已存在)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『用 read_file 读 README.md 头 5 行,然后用 30 字总结』」
- [ ] 子 Agent 跑动,tool_result 是总结文本
- [ ] tool_result **不含**「Worktree 保留」字样(因为读文件不产生修改,auto_cleanup 直接清理)
- [ ] `ls .gcode/worktrees/` 不存在与本次任务对应的 `agent-a*` 目录(已被 auto_cleanup 删除)
- [ ] tmux kill-session

### 场景 3:`/worktree create` + `/worktree list` 手动管理**预置:** 当前在 main 分支,git 工作区干净。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create demo-feature`
- [ ] scrollback 显示 `Worktree 已创建: .gcode/worktrees/demo-feature (分支 worktree-demo-feature)`
- [ ] 输入:`/worktree list`
- [ ] scrollback 显示一行含 `demo-feature` 的列表项,标记 `[manual]`(`manual=True`)
- [ ] tmux 外验证:`ls .gcode/worktrees/demo-feature/` 含正常 gcode 仓库内容;`git -C .gcode/worktrees/demo-feature branch` 显示在 `worktree-demo-feature`
- [ ] 清理:输入 `/worktree remove demo-feature --discard`
- [ ] 验证 `.gcode/worktrees/demo-feature` 已不存在
- [ ] tmux kill-session

### 场景 4:`/worktree exit` 变更保护**预置:** 同场景 3 创建好 `demo-feature`。

**步骤:**
- [ ] 手动写一个修改:`echo "modified" > .gcode/worktrees/demo-feature/test.txt`
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree enter demo-feature`
- [ ] 输入:`/worktree exit --remove` (不加 --discard)
- [ ] scrollback 显示错误 `worktree has uncommitted changes or new commits`(或对应中文消息)
- [ ] 输入:`/worktree exit --remove --discard`
- [ ] scrollback 显示成功消息,worktree 已被删除
- [ ] tmux kill-session

### 场景 5:explicit cwd——`/worktree enter` 后工具调用用 worktree 路径**预置:** 创建 worktree 并准备测试文件。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create cwd-test`
- [ ] 在 tmux 外:`echo "in-worktree-only" > .gcode/worktrees/cwd-test/probe.txt`(主目录无 probe.txt)
- [ ] tmux 内输入:`/worktree enter cwd-test`
- [ ] 输入:「用 read_file 读 probe.txt」
- [ ] 主 Agent 调 read_file 工具(path=probe.txt 相对路径)
- [ ] tool_result 应为 `in-worktree-only`(证明 cwd 解析到 worktree 路径)
- [ ] 输入:`/worktree exit`,主目录 cwd 恢复
- [ ] 再输入:「用 read_file 读 probe.txt」
- [ ] tool_result 报「无法访问文件 probe.txt」(主目录没这文件)
- [ ] 清理:`/worktree remove cwd-test --discard`
- [ ] tmux kill-session

### 场景 6:Slug 校验阻止路径遍历**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create ../etc`
- [ ] scrollback 显示错误,含「invalid」或「拒绝」(不创建 `.gcode/etc/` 或类似)
- [ ] 输入:`/worktree create ..`
- [ ] 同样错误
- [ ] 输入:`/worktree create normal_one`
- [ ] 成功创建
- [ ] 清理:`/worktree remove normal_one --discard`
- [ ] tmux kill-session
````

### Java

````markdown
# Worktree 隔离 Spec## 背景ch13 SubAgent 隔离了消息、权限决策状态、文件读缓存和 token 计数,但 **文件系统**仍然共享。主 Agent 和后台子 Agent(以及下一章要做的 Agent Team 队员)会在同一时刻并发读写同一份工作目录的文件,出现读到对方写了一半的文件、互相覆盖修改等并行冲突——本质就是经典的并行开发文件冲突,和两个程序员同时改同一份文件一样。

Git 分支只能做**时间维度**的隔离(切换分支时工作目录被覆盖,同一时刻只有一个工作目录),不能解决并行问题;切分支还会刷被切文件的 mtime,触发依赖追踪型构建工具的链式重编。

需要的是**空间维度**的隔离:同一仓库同时挂多个工作目录、共享版本库、各自一个分支。这就是 Git Worktree (Git 2.5+) 的能力。本章在 gcode 中封装一层 Worktree 管理逻辑,把这块拼图补给 SubAgent,让后台 / 并行场景安全可用。

gcode 现有相关基础设施:
- ch13 SubAgent 已支持 frontmatter (`dev.gcode.subagent.Parser`),解析 `name/description/tools/disallowedTools/model/maxTurns/permissionMode/background` 等字段
- ch13 `agent.AgentTool#execute` 已是子 Agent 启动入口,本章在此处插桩 isolation 分支
- ch08 文件读缓存以绝对路径作为 key
- ch10 `dev.gcode.command` 已有 slash 命令注册系统
- `.gitignore` 已忽略 `.gcode/sessions/` 等子目录,本章扩展把 `.gcode/worktrees/` 也忽略
- Tool 接口 `execute(ctx, args) Result` 现支持 ctx 携带值(已有 `CTX_KEY_CONV` / `CTX_KEY_SUBAGENT_DEPTH` 范式),可作为 explicit cwd 的传递通道

本章不引入 Worktree 间合并策略、跨目录代码同步、多 Agent 并行编排,这些属于上层 / 下一章范畴。

## 目标- **G1**: 提供 `WorktreeManager` 封装 Worktree 完整生命周期——创建、快速恢复、进入、退出、删除;并发场景下用单一 `ReentrantLock` 保护内部 `active` 映射
- **G2**: 名字 (slug) 严格安全校验——限字符集 `[a-zA-Z0-9._-]`、总长度上限 64、显式拒绝 `.` 和 `..` 段名、允许 `/` 做嵌套分隔;防 LLM 输入触发路径遍历
- **G3**: Worktree 目录统一落在仓库内不被追踪的位置 `.gcode/worktrees/<flatSlug>/`,分支名前缀 `worktree-<flatSlug>`,嵌套 slug 的 `/` 替换为 `+` 避免 Git D/F 冲突
- **G4**: 创建后做四类环境初始化——A 复制本地配置 (`.gcode/config.yaml` / `.gcode/settings.local.yaml`)、B 配置子目录的 git hooks (`core.hooksPath` 不自动继承)、C 软链 `node_modules` / `.venv` / `vendor` 等大目录、D 按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;均为 best-effort,失败只警告不中断创建
- **G5**: 快速恢复——目录已存在时,仅读 `.git` 指针 + `HEAD` + `refs/` 文件系统读还原 commit SHA,不调任何 git 子进程,毫秒级返回
- **G6**: 进入 Worktree 不调任何进程级 `chdir`——把 `WorktreePath` 记到会话状态 (`WorktreeSession`) 并通过 ctx 传给工具调用;Bash / Read / Write / Edit / Glob / Grep 工具从 ctx 取 cwd,本次调用显式声明在 Worktree 里跑;JVM 进程当前目录不变,避免并发组件之间的同步点
- **G7**: 文件读缓存等以绝对路径为 key 的缓存,天然按目录隔离;进入 / 退出 Worktree **不需要清缓存**
- **G8**: 退出时变更保护——`action="remove"` 且未显式 `discardChanges=true` 时,检测到未提交修改或本地多于 base 的 commit 一律拒绝删除;同时把当前目录信息还原到原 cwd 兜底防 session 期间残留
- **G9**: 自动清理 (`autoCleanup`)——SubAgent 退出时,无变更则直接 remove,有变更则保留 Worktree 路径与分支名追加到 SubAgent 结果文本给主 Agent review
- **G10**: 后台过期 Worktree 清理——按命名模式 (`agent-a[0-9a-f]{7}`) 只识别临时 Worktree,叠加时间过滤(超过 cutoff 才考虑),最后做 fail-closed 变更检查(有未提交修改 / 未推送 commit 都保留)
- **G11**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,gcode 启动时读取并校验目录仍存在;退出时写空 JSON `null` 而不是删文件,确保下次启动不误恢复
- **G12**: 在 `subagent.Definition` 增加 `isolation` 字段 (`""` / `"worktree"`);SubAgent 启动器检测到 `isolation:worktree` 后,自动 `create → inject worktree notice → set ctx cwd → runToCompletion → autoCleanup`,无需在 prompt / 工具调用里显式指定
- **G13**: 提供 TUI slash 命令 `/worktree create <slug>`、`/worktree list`、`/worktree exit [--remove]`、`/worktree remove <slug> [--discard]`——让用户手动管理;手动创建的 Worktree **不走自动清理**
- **G14**: 与 ch04~ch13 协同——主 Agent 看到的工具列表不变(ctx 注入不改 schema)、prompt cache 不抖动、既有测试不破坏

## 功能需求### Slug 验证- **F1**: `WorktreeSlug.validate(name)` 校验规则——
  - name 非空,总长度 ≤ 64
  - 按 `/` 切段,每段必须匹配正则 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`
  - 不允许出现连续 `//`、首末 `/`
  - 失败时抛出带具体原因的 `IllegalArgumentException`

### WorktreeManager 与核心数据结构- **F2**: `Worktree` record 记录单个 Worktree 的元信息——`name`(原始 slug)、`path`(绝对路径)、`branch`(`worktree-<flatSlug>`)、`basedOn`(创建时的 base 引用,如 `HEAD` 或具体 commit)、`headCommit`(创建时的 commit SHA)、`created`(`Instant`)、`manual`(boolean,是否用户手动创建,影响 autoCleanup 跳过判断)
- **F3**: `WorktreeSession` record 记录当前活跃的 Worktree 会话——`originalCwd`、`worktreePath`、`worktreeName`(原 slug)、`originalBranch`、`originalHeadCommit`、`sessionId`(UUID 字符串)、`hookBased`(boolean,预留)
- **F4**: `WorktreeManager` 内部字段——`repoRoot`(绝对路径)、`worktreeDir`(`<repoRoot>/.gcode/worktrees`)、`sessionFile`(`<repoRoot>/.gcode/worktree_session.json`)、`ReentrantLock lock`、`Map<String, Worktree> active`、`WorktreeSession currentSession`
- **F5**: `new WorktreeManager(Path repoRoot)` 构造时——
  - 校验 `repoRoot` 是 git 仓库根目录(`git rev-parse --show-toplevel` 输出与之等);失败抛 `IOException`,gcode 启动允许降级到「Worktree 功能未启用」
  - 创建 `worktreeDir` 目录(如不存在)
  - 从 `sessionFile` 反序列化 `currentSession`(允许文件不存在);若 session 指向的 Worktree 目录已不存在,清空 session 文件并把 `currentSession=null`
  - 扫描 `worktreeDir` 子目录还原 `active` 映射(name → Worktree),仅按文件系统读填字段(快速恢复路径)
- **F6**: `manager.create(name, baseRef, manual)`——
  - 1. `WorktreeSlug.validate(name)` 不通过即抛异常
  - 2. `lock.lock()`,若 `active.get(name)` 已存在,抛异常
  - 3. `flatSlug = name.replace("/", "+")`、`wtPath = worktreeDir.resolve(flatSlug)`、`branchName = "worktree-" + flatSlug`
  - 4. 快速恢复路径:若 `wtPath` 已存在,直接读 `.git` 指针 + `HEAD` + `refs/heads/<branch>` 得 `headSha`,构造 `Worktree` 放入 `active`,返回(不调任何 git 子进程)
  - 5. 否则执行 `git worktree add -B <branch> <wtPath> <baseRef>`,环境变量 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`,stdin 关闭;失败时抛异常并清理可能残留的目录
  - 6. 执行创建后设置 `performPostCreationSetup` (F7-F10),任何子步骤失败仅 stderr 警告,不中断
  - 7. 读出 `headSha`(`git -C <wtPath> rev-parse HEAD`),装填 `Worktree(name, path, branch, basedOn, headCommit, created, manual)`
  - 8. 加入 `active`,返回
- **F7**: 创建后设置 A——复制本地配置文件,从 `<repoRoot>/.gcode/config.yaml` 与 `<repoRoot>/.gcode/settings.local.yaml` 复制到 Worktree 同位置(目标已存在跳过,文件不存在跳过)
- **F8**: 创建后设置 B——配置 git hooks,检测主仓库 `core.hooksPath` 与 `.husky/` 目录,若有则 `git -C <wtPath> config core.hooksPath <绝对路径>`;无则跳过
- **F9**: 创建后设置 C——按配置软链大目录,默认列表 `["node_modules", ".venv", "vendor"]`,对每个目录若主仓库存在且 Worktree 不存在则用 `java.nio.file.Files.createSymbolicLink(...)` 创建;失败只警告
- **F10**: 创建后设置 D——按项目根 `.worktreeinclude` 复制被忽略但运行需要的文件;读取 `.worktreeinclude` 每行为 glob 模式(支持 `*.env` 这种),用 `git -C <repoRoot> ls-files --others --ignored --exclude-standard --directory` 列出所有忽略文件,匹配模式后逐个复制到 Worktree 对应路径;文件不存在 / 模式无匹配只警告

### 进入与退出- **F11**: `manager.enter(name)`——
  - 1. `lock.lock()`,从 `active` 取 wt(不存在抛异常)
  - 2. 取当前 `Path.of("").toAbsolutePath()` 与当前 Git HEAD/branch 作为原状态
  - 3. 构造 `WorktreeSession(originalCwd, wt.path, name, originalBranch, originalHeadCommit, sessionId=UUID.randomUUID().toString(), hookBased=false)`
  - 4. 写 `currentSession = session`,持久化到 `sessionFile`(原子写——先写 tmp 再 `Files.move(..., ATOMIC_MOVE)`)
  - 5. 返回 session
  - **不动 JVM 进程当前目录**
- **F12**: `manager.exit(name, action, opts)`——`ExitAction` 取 `KEEP` / `REMOVE`;`ExitOptions(boolean discardChanges)`
  - 1. `lock.lock()`,取 `active.get(name)` 与 `currentSession`(若 `currentSession.worktreeName().equals(name) == false` 抛异常,只能退当前)
  - 2. 若 `action=REMOVE` 且 `!opts.discardChanges()`,调 `hasWorktreeChanges(wt.path, wt.headCommit)`,有变更则抛 `WorktreeHasChangesException`
  - 3. 记录 `session.originalCwd` 留作上层 UI 还原 cwd 时使用(JVM 进程当前目录本就没变)
  - 4. `currentSession = null`,持久化为 `null`(覆写 sessionFile 为空 JSON `null` 字符串)
  - 5. 若 `action=REMOVE`:`git worktree remove --force <wtPath>` → `Thread.sleep(100)` → `git branch -D <branchName>`;`active.remove(name)`
  - 6. 返回 `ExitReport(boolean removed, String path, String branch)`
- **F13**: `manager.remove(name, opts)`——独立 remove 入口,允许删除非当前 session 的 Worktree;变更保护同 F12
- **F14**: `manager.autoCleanup(name)`——
  - 1. 取 `active.get(name)`,`manual=true` 直接返回 `Kept` 报告
  - 2. `hasWorktreeChanges(wt.path, wt.headCommit)` 返回 false 走 `remove(name, new ExitOptions(true))`,报告 `kept=false`
  - 3. 有变更:`kept=true, path=wt.path, branch=wt.branch`
- **F15**: `hasWorktreeChanges(wtPath, baseCommit)` boolean——两件事:`git -C <wtPath> status --porcelain` 非空即有未提交;`git -C <wtPath> rev-list --count <baseCommit>..HEAD` >0 即有新增 commit;任一 git 命令本身出错 fail-closed 返回 true(宁可保留)

### explicit cwd 工具改造- **F16**: 在 `dev.gcode.tool` 包定义 ctx key 与帮助函数(`ToolContext` 不可变上下文对象封装)——
  - `ToolContext.withCwd(ctx, dir)` 返回新 ctx 含 cwd
  - `ctx.cwd()` 返回 `Optional<Path>`
  - `ctx.resolvePath(p)`——若 p 是绝对路径直接返回;否则用 ctx cwd(优先)或 JVM 当前目录拼相对路径,返回绝对 `Path`
- **F17**: 改造 6 个核心工具支持 ctx cwd——
  - `ReadFileTool`、`WriteFileTool`、`EditFileTool`:用 `ctx.resolvePath` 解析 `path` 参数
  - `GlobTool`:用 `ctx.resolvePath` 解析 `path` 参数
  - `GrepTool`:同 `GlobTool`(参数名可能不同,按现有 schema)
  - `BashTool`:在 `ProcessBuilder` 上 `directory(ctx.resolvePath("").toFile())` 即 ctx cwd 或 JVM 当前目录
- **F18**: ctx cwd 注入点——
  - SubAgent isolation:worktree 启动时,在调 `runToCompletion` 前 `ctx = ctx.withCwd(wt.path())`
  - TUI `/worktree create` 后用户手动 `enter` 也注入到主 Agent 的下一次 Run 的 ctx(通过 tui 的 `runOnce` 入口)
- **F19**: 工具 Schema 不变——主 Agent 看到的工具列表与参数与 ch13 完全一致,ctx 注入不暴露 cwd 字段

### SubAgent 集成- **F20**: 扩展 `subagent.Definition` 增加 `String isolation` 字段;`Parser` 解析 frontmatter `isolation:` 字段,合法值 `""` / `"worktree"`,非法值 stderr 警告后回落到 `""`
- **F21**: 改造 `agent.AgentTool#execute`——当 `def.isolation().equals("worktree")` 时走 `executeWithWorktree` 分支:
  - 1. 用 `agent-a<7位随机 hex>` 作为 worktree name(规避同类型并发冲突)
  - 2. 调 `worktreeManager.create(name, "HEAD", false)` 创建临时 Worktree
  - 3. 构造 `worktreeNotice` 文本(F22)拼到 task 文本前
  - 4. `ctx = ctx.withCwd(wt.path())`
  - 5. 调 `subAgent.runToCompletion(ctx, subConv, taskWithNotice, events)`
  - 6. 跑完后调 `manager.autoCleanup(name)`,kept=true 时把 `\n[Worktree 保留在 <path>,分支 <branch>]` 追加到 finalText
  - 7. 返回 finalText 给主 Agent
- **F22**: `buildWorktreeNotice(parentCwd, wtPath)` 模板(实际内容大致如下,中文友好)——
  ```
  <worktree-context>
  你当前在一个独立的 Git Worktree 副本中工作,与父 Agent 隔离。
  - 父目录: <parentCwd>
  - 你的工作目录: <wtPath>
  - 父 Agent 提到的绝对路径基于父目录,你需要翻译成本地路径(替换前缀)再读写
  - 编辑文件前,必须先在本地 Worktree 重新 `read_file` 一次,避免使用过时内容
  </worktree-context>
  ```
- **F23**: 后台 SubAgent + isolation 协同——若 `background && isolation:worktree`,本期强制走前台路径(忽略 background 标志);后续章节再扩展异步路径

### TUI Slash 命令- **F24**: `/worktree create <slug>`——调 `manager.create(slug, "HEAD", true)` (`manual=true`),输出 Worktree path + branch
- **F25**: `/worktree list`——遍历 `manager.list()`,每行格式 `<name>  <path>  <branch>  [active?]`
- **F26**: `/worktree exit [--remove] [--discard]`——退出当前 session;`--remove` 时调 `exit(name, REMOVE, new ExitOptions(discard))`,`--discard` 跳过变更保护
- **F27**: `/worktree remove <slug> [--discard]`——直接调 `manager.remove(slug, ...)`
- **F28**: `/worktree enter <slug>`——调 `manager.enter(slug)`,把 ctx cwd 写到 TUI 的 `activeCwd` 字段,主 Agent 下次 Run 用这个 cwd 注入 ctx
- **F29**: slash 命令属于 `KindLocal`(只读)或 `KindUI`(改 TUI 状态),不进对话历史;输出走 `ui.println`

### 持久化与恢复- **F30**: `WorktreeSession` 用 Jackson(或同等 JSON 库)序列化,字段名采用小写下划线(`@JsonProperty`);原子写——先写 `<sessionFile>.tmp` 再 `Files.move(..., StandardCopyOption.ATOMIC_MOVE)`
- **F31**: gcode 启动时(`new WorktreeManager` 内),读 `sessionFile` 反序列化;若文件内容为 `null` 或空,`currentSession=null`;若 `worktreePath` 不存在,清空文件并 `currentSession=null`(stderr 警告 "session worktree gone, cleared")
- **F32**: `--resume` (gcode 现有恢复入口)读到已有 session 时,把 `activeCwd` 设置到 `session.worktreePath`,主 Agent 后续工具调用都按 explicit cwd 走

### 后台过期清理- **F33**: `manager.sweepStale(cutoff)` 返回 `List<String> removed`——
  - 1. 遍历 `worktreeDir` 子目录
  - 2. **第一层** 名字匹配正则 `^agent-a[0-9a-f]{7}$`(本期只识别 SubAgent 临时模式)
  - 3. **第二层** 目录 mtime > cutoff 跳过;`currentSession.worktreePath().equals(子目录)` 跳过
  - 4. **第三层** `hasWorktreeChanges(子目录, 该 wt 的 headCommit)` 为 true 跳过(fail-closed);额外跑 `git -C <子目录> rev-list --max-count=1 HEAD --not --remotes`,非空跳过(有未推送 commit 也保留)
  - 5. 通过三层的子目录调 `remove(name, new ExitOptions(true))`,记入 `removed`
- **F34**: gcode 启动时跑一次 `Thread.startVirtualThread(() -> manager.sweepStale(Instant.now().minus(24, HOURS)))`(异步、后台执行),不阻塞启动

### .gitignore 更新- **F35**: 在项目根 `.gitignore` 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json` 两行;gcode 启动时若发现 `.gitignore` 不含这两行,**只警告不修改**(尊重用户配置)

## 非功能需求- **N1**: 主 Agent 看到的工具列表稳定——ctx 注入不改 schema,既有缓存不抖动
- **N2**: Worktree 创建后设置失败 (F7-F10) 不阻塞创建;主路径只在 git worktree add 本身失败时抛异常
- **N3**: Manager 所有状态变更受 `ReentrantLock lock` 保护;Worktree 内部 git 操作不持锁,避免长锁
- **N4**: 不使用 JVM 进程级 `chdir`(JVM 不支持也不应模拟);所有 cwd 行为通过 `ToolContext` 与 `ProcessBuilder.directory(...)` 实现
- **N5**: Worktree session 文件被破坏(非法 JSON)启动时只警告并清空,不阻断 gcode 启动
- **N6**: 与 ch04~ch13 既有测试零破坏——`mvn test` 全绿
- **N7**: 中文友好——错误消息与命令输出全部中文(对齐 gcode 其他模块风格)

## 不做的事

- Worktree 间的合并策略(交给上层 `git merge` / `git cherry-pick`)
- 跨 Worktree 代码同步、文件 watcher
- 多 Agent 并行编排 / Agent Team(下一章)
- 主 Agent 用专用 merge 工具(README 章末已说明)
- Plugin 来源的 Worktree 配置
- Windows 平台特殊支持(symlink 行为在 Windows 上不保证;本期 gcode 以 macOS / Linux 为主)
- 跨 gcode 进程实例的 Worktree 共享(同一仓库同一时刻只支持一个 gcode 实例操作 worktree session)
- Worktree 内部 git 操作的 retry / exponential backoff(用一次性 `Thread.sleep(100)` 解决 lockfile 竞态即可)

## 验收标准- **AC1**: `WorktreeSlug.validate` 对 `"feature/a"` 通过,对 `"../etc"` / `".."` / `"a//b"` / `"a/b "` 拒绝
- **AC2**: `manager.create("alice", "HEAD", true)` 在 `.gcode/worktrees/alice/` 下落地 Worktree,分支为 `worktree-alice`
- **AC3**: `manager.create("team/alice", "HEAD", true)` 在 `.gcode/worktrees/team+alice/` 下落地,分支 `worktree-team+alice`
- **AC4**: 已存在 worktree 目录时再调 create 走快速恢复——不调 `git worktree add`,毫秒级返回(单测可断言 git 子进程未启动)
- **AC5**: 创建后设置 A——主仓库存在 `.gcode/settings.local.yaml` 时,Worktree 内同位置出现该文件
- **AC6**: 创建后设置 B——主仓库 `.husky/` 存在时,Worktree 的 `.git/config` 含 `core.hooksPath`
- **AC7**: 创建后设置 C——主仓库有 `node_modules/` 时,Worktree 内是软链(`Files.isSymbolicLink(...)` 为 true)
- **AC8**: 创建后设置 D——主仓库有 `.worktreeinclude` 含 `*.env`,且主仓库存在被忽略的 `.env`,Worktree 内出现 `.env`
- **AC9**: `manager.enter(name)` **不**改变 JVM 当前目录 `Path.of("").toAbsolutePath()`;返回 session 含正确字段
- **AC10**: `manager.exit(name, REMOVE, new ExitOptions(false))` 当 Worktree 有未提交修改时,抛 `WorktreeHasChangesException`,Worktree 目录仍在
- **AC11**: `manager.exit(name, REMOVE, new ExitOptions(true))` 显式 discard 时,目录被删,分支被删
- **AC12**: `manager.autoCleanup(name)` 对 `manual=true` 直接 keep;对 `manual=false` 且无变更直接 remove
- **AC13**: 工具 `read_file` / `write_file` / `edit_file` / `bash` / `glob` / `grep` 在 ctx 注入 cwd 后,以 cwd 为基准解析相对路径(单测断言)
- **AC14**: `bash` 工具在 ctx cwd 注入下,`ProcessBuilder.directory()` 等于 cwd(单测 / 集成测试可断言)
- **AC15**: `subagent.Definition#isolation()` 为 `"worktree"` 时,`AgentTool#execute` 创建临时 Worktree、注入 worktree notice、传 ctx cwd、跑完后调 autoCleanup
- **AC16**: SubAgent + worktree 路径上,子 Agent 写文件不影响主 Agent 工作目录(集成测试或 tmux 实跑可观察)
- **AC17**: `/worktree create alice` slash 命令成功落地 Worktree,`/worktree list` 输出含 alice
- **AC18**: `/worktree exit --remove` 在 Worktree 有未提交修改时报错;加 `--discard` 后成功删除
- **AC19**: `manager.sweepStale(cutoff)` 只删命名匹配 `agent-a[0-9a-f]{7}` 的目录、跳过当前 session、跳过有变更或有未推送 commit 的目录
- **AC20**: `WorktreeSession` 持久化到 `.gcode/worktree_session.json`,启动时读取;指向的 Worktree 目录被外部删除后,启动时清空 session 并 stderr 警告
- **AC21**: 项目编译无错误 (`mvn -q -DskipTests package`)、所有单元测试通过 (`mvn test`)、Spotless 检查通过 (`mvn spotless:check`)
- **AC22**: tmux 实跑——`gcode` 启动 + 触发 `isolation:worktree` 子 Agent 改文件 + 验证主目录 `server.py`(若改的是 `server.py`)未变,Worktree 副本里 `server.py` 已变;Worktree 留盘 / 自动清理符合预期
````

````markdown
# Worktree 隔离 Plan## 架构概览

新建 `dev.gcode.worktree` 包,集中放 `WorktreeManager`、`Worktree`、`WorktreeSession`、Slug 校验、创建后设置、自动清理、过期清理。其余包按以下方式接入:

- **`dev.gcode.tool`**:新增 `ToolContext`(`withCwd` / `cwd()` / `resolvePath(...)`);改造 6 个核心工具用 `ctx.resolvePath(...)`
- **`dev.gcode.subagent`**:`Definition` 加 `isolation` 字段,`Parser` 解析 `isolation:` frontmatter
- **`dev.gcode.agent`**:`AgentTool#execute` 加 `executeWithWorktree` 分支,启动时通过 ctx 注入 cwd
- **`dev.gcode.command`**:新增 `WorktreeCommand` 内置命令,提供 `/worktree` 一级命令与子命令(create/list/enter/exit/remove)
- **`dev.gcode.tui`**:在 `TuiApp` 字段加 `WorktreeManager worktreeMgr`、`Path activeCwd`;主 Agent 每次 `run` 前用 `ctx.withCwd(activeCwd)` 注入 ctx
- **`dev.gcode.Main`**:`new WorktreeManager(root)` 落在 `subagentCatalog = SubagentCatalog.load(root)` 之后;失败降级为 null(可选);把 manager 传给 `TuiApp` 和 `AgentTool` 构造
- **`.gitignore`**:追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`

## 核心数据结构### `dev.gcode.worktree.Worktree`

```java
public record Worktree(
        String name,         // 原始 slug(可能含 /)
        Path path,           // 绝对路径
        String branch,       // worktree-<flatSlug>
        String basedOn,      // 创建时的 base 引用(HEAD / SHA)
        String headCommit,   // 创建时的 commit SHA
        Instant created,
        boolean manual       // true=用户手动创建(/worktree create 路径)
) {}
```

### `dev.gcode.worktree.WorktreeSession`

```java
public record WorktreeSession(
        @JsonProperty("original_cwd")         String originalCwd,
        @JsonProperty("worktree_path")        String worktreePath,
        @JsonProperty("worktree_name")        String worktreeName,
        @JsonProperty("original_branch")      String originalBranch,
        @JsonProperty("original_head_commit") String originalHeadCommit,
        @JsonProperty("session_id")           String sessionId,
        @JsonProperty("hook_based")           boolean hookBased
) {}
```

### `dev.gcode.worktree.WorktreeManager`

```java
public final class WorktreeManager {
    private final Path repoRoot;
    private final Path worktreeDir;
    private final Path sessionFile;
    private final List<String> symlinkDirs;            // 默认 [node_modules, .venv, vendor]
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, Worktree> active = new HashMap<>();
    private WorktreeSession currentSession;

    public WorktreeManager(Path repoRoot) throws IOException;

    public Worktree create(String name, String baseRef, boolean manual) throws IOException;
    public WorktreeSession enter(String name) throws IOException;
    public ExitReport exit(String name, ExitAction action, ExitOptions opts) throws IOException;
    public void remove(String name, ExitOptions opts) throws IOException;
    public AutoCleanupReport autoCleanup(String name) throws IOException;
    public List<String> sweepStale(Instant cutoff);

    public List<Worktree> list();
    public Optional<Worktree> get(String name);
    public WorktreeSession currentSession();
}
```

### `dev.gcode.worktree` 辅助类型

```java
public enum ExitAction { KEEP, REMOVE }

public record ExitOptions(boolean discardChanges) {}
public record ExitReport(boolean removed, String path, String branch) {}
public record AutoCleanupReport(boolean kept, String path, String branch) {}

public final class WorktreeHasChangesException extends IOException {
    public WorktreeHasChangesException() {
        super("worktree has uncommitted changes or new commits");
    }
}
```

### `dev.gcode.tool.ToolContext`

```java
public record ToolContext(Optional<Path> cwd /* 其他既有 ctx 字段也合并到这里 */) {
    public static ToolContext root() { return new ToolContext(Optional.empty()); }
    public ToolContext withCwd(Path dir) { return new ToolContext(Optional.of(dir.toAbsolutePath())); }
    public Path resolvePath(String p) {
        if (p == null || p.isEmpty()) {
            return cwd.orElseGet(() -> Path.of("").toAbsolutePath());
        }
        Path raw = Path.of(p);
        if (raw.isAbsolute()) return raw;
        Path base = cwd.orElseGet(() -> Path.of("").toAbsolutePath());
        return base.resolve(raw).normalize();
    }
}
```

### `dev.gcode.subagent.Definition` 扩展

```java
public record Definition(
        // ... 既有字段 ...
        String isolation   // "" 或 "worktree"
) {}
```

## 模块设计### `dev.gcode.worktree`(新包)**职责:** Worktree 完整生命周期管理 + Slug 校验 + 后台清理。
**对外接口:** `WorktreeManager` (含上面所列方法) + `WorktreeSlug.validate(...)` + `WorktreeHasChangesException` 等导出类型。
**依赖:** JDK 标准库 + `ProcessBuilder` 调 git;JSON 用 Jackson(项目已通过 SDK 间接引入)。
**关键内部函数:**
- `WorktreeSlug.validate(name)`
- `WorktreeSlug.flatten(name)` (`/` → `+`)
- `PostCreationSetup.run(repoRoot, wtPath, symlinkDirs)`
- `GitHelper.hasWorktreeChanges(wtPath, baseCommit)` (fail-closed)
- `GitHelper.resolveHeadShaFromFS(wtPath)` (快速恢复)
- `WorktreeInclude.read(repoRoot)`
- `GitHelper.listIgnoredFiles(repoRoot)`
- `GitHelper.gitProcess(workDir, args...)` (统一 env: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=""`,stdin closed)
- `WorktreeNaming.randomAgentName()` (用于 SubAgent 临时 worktree 名)

**文件:**
- `WorktreeManager.java` — Manager 类型 + 主要方法骨架
- `WorktreeCreate.java` — `create` + 快速恢复 + 创建后设置(可作为 `WorktreeManager` 内部 helper class)
- `WorktreeLifecycle.java` — `enter` / `exit` / `remove` / `autoCleanup`(同上)
- `WorktreeSweep.java` — `sweepStale`
- `WorktreeSlug.java` — `validate` + `flatten`
- `WorktreeSession.java` — record + JSON 持久化辅助
- `SessionStore.java` — 原子读写 JSON
- `GitHelper.java` — `gitProcess` / `hasWorktreeChanges` / `resolveHeadShaFromFS`
- `WorktreeNaming.java` — 随机命名
- `PostCreationSetup.java` — 创建后 A/B/C/D 步骤
- `Worktree.java` / `WorktreeHasChangesException.java` / `ExitAction.java` / `ExitOptions.java` / `ExitReport.java` / `AutoCleanupReport.java`
- `*Test.java` — JUnit 5 单测

### `dev.gcode.tool` 改造**职责:** 增加 ctx cwd 传递机制,改造 6 个工具用 `ctx.resolvePath` / `ProcessBuilder.directory()`。
**对外接口:** `ToolContext`(`withCwd` / `cwd()` / `resolvePath`)新增;6 个工具 `execute` 行为变更但 schema 不变。
**依赖:** 无新增。

**文件改动:**
- `ToolContext.java` — 新增或扩展既有上下文 record
- `ReadFileTool.java` / `WriteFileTool.java` / `EditFileTool.java` — `Files.readAllBytes`/`Files.write` 前用 `ctx.resolvePath(args.path())`
- `GlobTool.java` — root 解析改 `ctx.resolvePath`
- `GrepTool.java` — 同 `GlobTool`
- `BashTool.java` — `pb.directory(ctx.resolvePath("").toFile())` (即 cwd 本身,空字符串绝对路径化)

### `dev.gcode.subagent` 改造**职责:** `Definition` 加 `isolation` 字段;`Parser` 解析。
**改动:**
- `Parser.java` — frontmatter Map 增加 `isolation` 字段提取,合法值 `""` / `"worktree"`,其他值 stderr 警告回落空
- `Definition.java` — record 加 `String isolation`(放参数末尾)

### `dev.gcode.agent` 改造**职责:** `AgentTool` 增加 worktree 分支,接受 manager。
**改动:**
- `AgentTool.java`:
  - 字段加 `WorktreeManager wtMgr`
  - 构造器 `new AgentTool(..., WorktreeManager wtMgr)`(签名末尾追加)
  - `execute` 内 `def.isolation().equals("worktree")` 时走 `executeWithWorktree(...)`
- 新增 `AgentWorktreeRunner.java`:
  - `executeWithWorktree(ctx, def, subAgent, subConv, prompt, events)` 实现
  - `buildWorktreeNotice(parentCwd, wtPath)` 文案
  - `randomAgentName()` 委托 `WorktreeNaming.randomAgentName()`

### `dev.gcode.command` 新增**职责:** `/worktree` 一级命令 + 子命令解析。
**改动:**
- `Builtins.java` 增加 `register(new WorktreeCommand())`
- 新增 `WorktreeCommand.java`(`handle` 内自己 split 子命令 + 参数)
- `Ui.java` 加 UI 接口方法 `WorktreeAccessor worktreeAccessor()`(返回一个轻量接口,屏蔽 worktree 包反向依赖)

**UI 接口扩展:**

```java
// command/WorktreeAccessor.java
public interface WorktreeAccessor {
    CreateResult create(String name) throws IOException;
    List<WorktreeSummary> list();
    void enter(String name) throws IOException;
    boolean exit(String action, boolean discard) throws IOException;
    void remove(String name, boolean discard) throws IOException;

    record CreateResult(String path, String branch) {}
}

public record WorktreeSummary(String name, String path, String branch, boolean active, boolean manual) {}

public interface Ui {
    // ... 既有方法 ...
    WorktreeAccessor worktreeAccessor();   // 可返回 null 表示未启用
}
```

### `dev.gcode.tui` 改造**职责:** 持有 manager 引用,把 activeCwd 注入主 Agent ctx。
**改动:**
- `TuiApp.java` 字段加 `WorktreeManager worktreeMgr`、`Path activeCwd`(null 表示 JVM 当前目录)
- 构造器接收 `WorktreeManager worktreeMgr`(`TuiApp.Builder` 加方法)
- 在主 Agent `run` 入口前注入 `ctx = ctx.withCwd(effectiveCwd())`,其中 `effectiveCwd()` 返回 `activeCwd` 或 `Path.of("").toAbsolutePath()`
- 实现 `WorktreeAccessor` 接口的适配器类 `TuiWorktreeAccessor`(内部持 `TuiApp` + `WorktreeManager`)
- 启动时若 manager 的 `currentSession()` 非 null,把 `activeCwd = Path.of(session.worktreePath())`

### `dev.gcode.Main` 改造

```java
// 紧跟 var subagentCatalog = SubagentCatalog.load(root); 之后
WorktreeManager worktreeMgr;
try {
    worktreeMgr = new WorktreeManager(root);
    Thread.startVirtualThread(() -> worktreeMgr.sweepStale(Instant.now().minus(24, ChronoUnit.HOURS)));
} catch (IOException werr) {
    System.err.println("Worktree 管理器降级: " + werr.getMessage());
    worktreeMgr = null;      // 后续 AgentTool / TUI 容忍 null
}

var agentTool = new AgentTool(subagentCatalog, taskMgr, null, cfg.effectiveEnableSubAgentBackground(), worktreeMgr);

var tui = TuiApp.builder()
        // ... 既有字段 ...
        .worktreeMgr(worktreeMgr)
        .build();
```

## 模块交互**SubAgent + Worktree 启动链路:**

```
主 Agent 调 Agent 工具
  ↓
AgentTool#execute
  ↓
def.isolation().equals("worktree")?
  ↓ yes
executeWithWorktree:
  1. name = "agent-a" + randomHex(7)
  2. wt = worktreeMgr.create(name, "HEAD", false)
  3. notice = buildWorktreeNotice(parentCwd, wt.path())
  4. taskText = notice + "\n\n" + prompt
  5. ctx = ctx.withCwd(wt.path())
  6. finalText = subAgent.runToCompletion(ctx, subConv, taskText, events)
  7. report = worktreeMgr.autoCleanup(name)
  8. if report.kept(): finalText += "\n[Worktree 保留: " + report.path() + "]"
  9. return finalText
```

**工具调用的 cwd 解析链路:**

```
模型调 read_file(path="server.py")
  ↓
agent.execute → registry.execute(ctx, "read_file", args)
  ↓
ReadFileTool#execute(ctx, args)
  ↓
abs = ctx.resolvePath("server.py")
  ↓
ctx 有 cwd → abs = cwd.resolve("server.py").normalize()
ctx 无 cwd → abs = Path.of("").toAbsolutePath().resolve("server.py").normalize()
  ↓
Files.readAllBytes(abs)
```

**TUI 主 Agent Run 入口:**

```
TuiApp.runOnce(ctx):
  if (activeCwd != null) {
      ctx = ctx.withCwd(activeCwd);
  }
  events = agent.run(ctx, conv, mode);
```

## 文件组织

```
src/main/java/dev/gcode/worktree/   — 新包
├── WorktreeManager.java              — Manager 类型 + 构造
├── WorktreeCreate.java               — create + 快速恢复 + post-creation setup
├── WorktreeLifecycle.java            — enter / exit / remove / autoCleanup
├── WorktreeSweep.java                — sweepStale
├── WorktreeSlug.java                 — validate + flatten
├── WorktreeSession.java              — record + Jackson tag
├── SessionStore.java                 — JSON 原子读写
├── GitHelper.java                    — gitProcess / hasWorktreeChanges / resolveHeadShaFromFS
├── WorktreeNaming.java               — randomAgentName / ephemeral 正则
├── PostCreationSetup.java            — A/B/C/D 子步骤
├── Worktree.java
├── ExitAction.java / ExitOptions.java / ExitReport.java / AutoCleanupReport.java
└── WorktreeHasChangesException.java

src/test/java/dev/gcode/worktree/
├── WorktreeSlugTest.java
├── WorktreeManagerTest.java
├── WorktreeCreateTest.java
├── WorktreeLifecycleTest.java
├── WorktreeSweepTest.java
└── GitHelperTest.java

src/main/java/dev/gcode/tool/
├── ToolContext.java                  — 新增 withCwd/cwd/resolvePath
├── BashTool.java                     — 改造:pb.directory(ctx.resolvePath("").toFile())
├── ReadFileTool.java                 — 改造:用 ctx.resolvePath
├── WriteFileTool.java                — 改造:用 ctx.resolvePath
├── EditFileTool.java                 — 改造:用 ctx.resolvePath
├── GlobTool.java                     — 改造:用 ctx.resolvePath
└── GrepTool.java                     — 改造:用 ctx.resolvePath

src/test/java/dev/gcode/tool/
└── ToolContextTest.java

src/main/java/dev/gcode/subagent/
├── Definition.java                   — 加 isolation 字段
└── Parser.java                       — 解析 isolation:

src/test/java/dev/gcode/subagent/
└── ParserTest.java                   — 增加 isolation 用例

src/main/java/dev/gcode/agent/
├── AgentTool.java                    — execute 加 isolation 分支
└── AgentWorktreeRunner.java          — 新增:executeWithWorktree + notice

src/test/java/dev/gcode/agent/
└── AgentWorktreeRunnerTest.java

src/main/java/dev/gcode/command/
├── WorktreeCommand.java              — 新增:/worktree handler
├── Builtins.java                     — 增加 register
├── Ui.java                           — 加 worktreeAccessor()
└── WorktreeAccessor.java             — 接口 + WorktreeSummary

src/main/java/dev/gcode/tui/
├── TuiApp.java                       — 加 worktreeMgr / activeCwd / cwd 注入
└── TuiWorktreeAccessor.java          — 实现 WorktreeAccessor(适配 WorktreeManager)

src/main/java/dev/gcode/Main.java   — 接入

.gitignore                            — 追加两行
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| cwd 传递方式 | `ToolContext` record 携带 `Optional<Path>` | JVM 没有 per-thread cwd,显式上下文最干净;Tool 接口签名不变,prompt cache 不抖动 |
| Worktree 目录位置 | `.gcode/worktrees/<flatSlug>/` | README 既定方案;仓库内 + .gitignore 不追踪 |
| 嵌套 slug `/` 处理 | 替换为 `+`(flatten)做文件系统/分支名 | Git 分支的 `/` 是命名空间分隔符,会导致 `worktree-team/alice` 与 `worktree-team` 的 D/F 冲突 |
| Manager 构造失败处理 | 抛 `IOException`,Main 降级 `worktreeMgr=null` | 不阻塞 gcode 启动;后续 isolation:worktree 调用回错误信息 |
| 快速恢复 | 纯 fs 读,不调 git | README 说明大仓库 git fetch 6-8s,fs read 3ms;场景:同一 SubAgent 反复进同 worktree |
| 创建后设置失败处理 | 仅 stderr 警告 | 都是 best-effort,失败 ≠ 不可用 |
| `-B` vs `-b` | `-B`(重置) | 上次残留的孤儿分支不会让 create 失败 |
| `Thread.sleep(100)` 在 remove | 保留 | README 指出 git lockfile 竞态;100ms 是经验值 |
| 进程 cwd 处理 | 不使用进程级 chdir,全部 explicit cwd | JVM 标准 API 不支持 chdir;`ProcessBuilder.directory()` 已能解决子进程 cwd,避免进程级 cwd 成为同步点 |
| 后台清理触发时机 | gcode 启动时跑一次,虚拟线程异步 | 不阻塞主流程;ch11 已有 `SessionStore.cleanExpired` 同样做法 |
| `.worktreeinclude` 缺失行为 | 跳过 D 步骤,不报错 | 大多数项目没这文件 |
| `subagent.isolation` 默认值 | `""`(无隔离) | 不破坏 ch13 既有定义文件 |
| 临时 worktree 命名 | `agent-a<7hex>` | README 既定;`sweepStale` 正则匹配 |
| Manager 用 `ReentrantLock` 而非 `ReadWriteLock` | 操作粒度大、争用低,简单互斥足够 | 避免读写锁的额外复杂度 |
| `WorktreeAccessor` 接口在 command 包 | 隔离 worktree 包反向依赖 | command 包不应直接导入 worktree;TUI 提供适配器即可 |
| TUI `activeCwd` 字段 | `Path` 字段,null = JVM 当前目录 | 简单直接,与既有 `cwd` 字段并存避免改 schema |
| `--resume` 与 worktree session | `WorktreeManager` 构造内统一处理 | 启动时自动读 session,session 失效自动清空 |
| Linux/macOS 跨平台 | symlink 用 `Files.createSymbolicLink` | POSIX 平台一致;Windows 失败时 best-effort 跳过 |
| JSON 序列化 | Jackson(已被 anthropic-java / openai-java 间接引入) | 不新增依赖;`@JsonProperty` 完成小写下划线绑定 |
````

````markdown
# Worktree 隔离 Tasks## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/main/java/dev/gcode/worktree/WorktreeSlug.java` | `validate` + `flatten` |
| 新建 | `src/test/java/dev/gcode/worktree/WorktreeSlugTest.java` | Slug 校验单测 |
| 新建 | `src/main/java/dev/gcode/worktree/WorktreeSession.java` | record + JSON tag |
| 新建 | `src/main/java/dev/gcode/worktree/SessionStore.java` | JSON 原子读写 |
| 新建 | `src/main/java/dev/gcode/worktree/GitHelper.java` | `gitProcess` + `hasWorktreeChanges` + `resolveHeadShaFromFS` |
| 新建 | `src/test/java/dev/gcode/worktree/GitHelperTest.java` | git helper 单测 |
| 新建 | `src/main/java/dev/gcode/worktree/WorktreeManager.java` | Manager 类型 + 构造 + list/get/currentSession |
| 新建 | `src/main/java/dev/gcode/worktree/Worktree.java` | record |
| 新建 | `src/main/java/dev/gcode/worktree/ExitAction.java` | enum |
| 新建 | `src/main/java/dev/gcode/worktree/ExitOptions.java` | record |
| 新建 | `src/main/java/dev/gcode/worktree/ExitReport.java` | record |
| 新建 | `src/main/java/dev/gcode/worktree/AutoCleanupReport.java` | record |
| 新建 | `src/main/java/dev/gcode/worktree/WorktreeHasChangesException.java` | 异常 |
| 新建 | `src/main/java/dev/gcode/worktree/PostCreationSetup.java` | A/B/C/D 子步骤 |
| 新建 | `src/main/java/dev/gcode/worktree/WorktreeNaming.java` | randomAgentName + ephemeral 正则 |
| 新建 | `src/test/java/dev/gcode/worktree/WorktreeCreateTest.java` | create + setup 单测 |
| 新建 | `src/test/java/dev/gcode/worktree/WorktreeLifecycleTest.java` | 生命周期单测 |
| 新建 | `src/test/java/dev/gcode/worktree/WorktreeSweepTest.java` | sweepStale 单测 |
| 新建 | `src/test/java/dev/gcode/worktree/WorktreeManagerTest.java` | NewManager + session 持久化测试 |
| 新建 | `src/main/java/dev/gcode/tool/ToolContext.java` | `withCwd` / `cwd` / `resolvePath` |
| 新建 | `src/test/java/dev/gcode/tool/ToolContextTest.java` | resolvePath 单测 |
| 修改 | `src/main/java/dev/gcode/tool/ReadFileTool.java` | 用 `ctx.resolvePath` 解析 path |
| 修改 | `src/main/java/dev/gcode/tool/WriteFileTool.java` | 用 `ctx.resolvePath` 解析 path |
| 修改 | `src/main/java/dev/gcode/tool/EditFileTool.java` | 用 `ctx.resolvePath` 解析 path |
| 修改 | `src/main/java/dev/gcode/tool/GlobTool.java` | 用 `ctx.resolvePath` 解析 root |
| 修改 | `src/main/java/dev/gcode/tool/GrepTool.java` | 用 `ctx.resolvePath` 解析 path |
| 修改 | `src/main/java/dev/gcode/tool/BashTool.java` | `pb.directory(ctx.resolvePath("").toFile())` |
| 修改 | `src/main/java/dev/gcode/subagent/Definition.java` | record 加 `isolation` 字段 |
| 修改 | `src/main/java/dev/gcode/subagent/Parser.java` | 解析 isolation: frontmatter |
| 修改 | `src/test/java/dev/gcode/subagent/ParserTest.java` | 增加 isolation 单测 |
| 新建 | `src/main/java/dev/gcode/agent/AgentWorktreeRunner.java` | `executeWithWorktree` + `buildWorktreeNotice` |
| 修改 | `src/main/java/dev/gcode/agent/AgentTool.java` | 增加 `wtMgr` 字段 + isolation 分支 |
| 新建 | `src/test/java/dev/gcode/agent/AgentWorktreeRunnerTest.java` | 单测(stub Manager) |
| 修改 | `src/main/java/dev/gcode/command/Ui.java` | 加 `worktreeAccessor()` 方法 |
| 新建 | `src/main/java/dev/gcode/command/WorktreeAccessor.java` | 接口 + WorktreeSummary |
| 新建 | `src/main/java/dev/gcode/command/WorktreeCommand.java` | `/worktree` handler + 子命令解析 |
| 修改 | `src/main/java/dev/gcode/command/Builtins.java` | 注册 `/worktree` |
| 修改 | `src/test/java/dev/gcode/command/BuiltinsTest.java` | 加 worktree 注册测试 |
| 新建 | `src/main/java/dev/gcode/tui/TuiWorktreeAccessor.java` | 实现 `WorktreeAccessor` 适配 `WorktreeManager` |
| 修改 | `src/main/java/dev/gcode/tui/TuiApp.java` | `worktreeMgr` / `activeCwd` 字段 + 注入 ctx |
| 修改 | `src/main/java/dev/gcode/Main.java` | 构造 manager + 注入 AgentTool / TUI + sweepStale |
| 修改 | `.gitignore` | 追加 .gcode/worktrees/ + worktree_session.json |

## T1: Slug 校验**文件:** `WorktreeSlug.java` + `WorktreeSlugTest.java`
**依赖:** 无
**步骤:**
1. 新建包 `dev.gcode.worktree`,加 package-info 注释
2. 实现 `public static void validate(String name)`,规则:非空、长度 ≤ 64、按 `/` 切段后每段匹配 `^[a-zA-Z0-9._-]+$` 且不能是 `.` 或 `..`、无连续 `//`、无首末 `/`;失败抛 `IllegalArgumentException` 带具体原因
3. 实现 `public static String flatten(String name)`:`name.replace("/", "+")`
4. 写测试覆盖合法/非法 case:`alice`、`team/alice`、`v1.0`、`a_b`(合法);空、超长、`..`、`./x`、`a//b`、`/x`、`a/`、`a b`、`a;b`(非法)

**验证:** `mvn -q test -Dtest=WorktreeSlugTest`

## T2: WorktreeSession 持久化**文件:** `WorktreeSession.java` + `SessionStore.java`
**依赖:** T1
**步骤:**
1. 定义 `WorktreeSession` record,字段按 spec F3,Jackson `@JsonProperty` 标小写下划线;类型用 `String`(JVM 当前目录用 `Path.of("").toAbsolutePath().toString()` 序列化)
2. 实现 `SessionStore.load(Path path)`:文件不存在返回 `Optional.empty()`;内容为 `null` 或空返回 `Optional.empty()`;JSON 解析失败抛 `IOException`
3. 实现 `SessionStore.save(Path path, WorktreeSession s)`:s=null 时写字符串 `null`;原子写——先写 `path + ".tmp"` 再 `Files.move(..., StandardCopyOption.ATOMIC_MOVE, REPLACE_EXISTING)`
4. 实现 `SessionStore.clear(Path path)`(等同 `save(path, null)`)
5. JSON 用 Jackson(`ObjectMapper`);如项目还未直接依赖,通过 anthropic-java 间接传递,可在 `pom.xml` 显式加 `com.fasterxml.jackson.core:jackson-databind` 锁版本

**验证:** 在 `WorktreeManagerTest` T9 中覆盖

## T3: Git helper**文件:** `GitHelper.java` + `GitHelperTest.java`
**依赖:** 无
**步骤:**
1. 实现 `static ProcessBuilder gitProcess(Path workDir, String... args)`:`new ProcessBuilder` 接收 `git` + args,`directory(workDir.toFile())`,环境 `environment().put("GIT_TERMINAL_PROMPT", "0")` 与 `put("GIT_ASKPASS", "")`,`redirectInput(ProcessBuilder.Redirect.from(new File(System.getProperty("os.name").startsWith("Windows") ? "NUL" : "/dev/null")))`
2. 实现 `static String runGit(Path workDir, String... args) throws IOException`:启动进程,读 stdout(`process.getInputStream()` → `new String(..., UTF_8)`),`waitFor()`;非零退出抛 `IOException` 带 stderr;返回 stdout 去 trailing 换行
3. 实现 `static boolean hasWorktreeChanges(Path wtPath, String baseCommit)`:① `git -C status --porcelain` 非空 ② `git -C rev-list --count <baseCommit>..HEAD` >0;任一 git 命令本身抛异常 fail-closed 返回 true
4. 实现 `static Optional<String> resolveHeadShaFromFS(Path wtPath)`:读 `wtPath/.git` 取 `gitdir: <path>`,读 `<gitdir>/HEAD`,若是 `ref: refs/heads/<name>`,读 `<gitdir>/<refpath>` 拿 SHA;失败返回 `Optional.empty()`
5. 测试:用一个临时 git 仓库(`Files.createTempDirectory` + 调真实 `git init`)做真实 Worktree,断言上述函数行为

**验证:** `mvn -q test -Dtest=GitHelperTest`

## T4: Manager 构造**文件:** `WorktreeManager.java`(主类) + `Worktree.java` + 辅助 record + `WorktreeManagerTest.java`
**依赖:** T2, T3
**步骤:**
1. 定义 `Worktree` record(spec F2 字段) + `WorktreeManager` 字段(spec F4) + 类型常量 `private static final List<String> DEFAULT_SYMLINK_DIRS = List.of("node_modules", ".venv", "vendor");`
2. 实现 `public WorktreeManager(Path repoRoot) throws IOException`:
   - `this.repoRoot = repoRoot.toAbsolutePath().normalize();`
   - 跑 `git -C <repoRoot> rev-parse --show-toplevel`,输出与 repoRoot 不匹配则抛 `IOException`
   - 初始化 `worktreeDir = repoRoot.resolve(".gcode/worktrees");`、`sessionFile = repoRoot.resolve(".gcode/worktree_session.json");`
   - `Files.createDirectories(worktreeDir);`
   - `SessionStore.load(sessionFile)`;若 session 非空但其 `worktreePath` 不存在,清空 session 并 stderr 警告
   - 扫描 `worktreeDir` 子目录,对每个非空目录用 `GitHelper.resolveHeadShaFromFS` 填 `active`(快速恢复路径,不调 git)
3. 实现 `list()` (按 name 排序)、`get(name)`、`currentSession()`
4. 测试:在临时 git 仓库构造 manager,断言 `worktreeDir` 创建、空 session 时 `currentSession()=null`、预放 session 文件能被加载、Worktree 目录不存在时 session 被清空

**验证:** `mvn -q test -Dtest=WorktreeManagerTest`

## T5: Create + 快速恢复 + 创建后设置**文件:** `WorktreeManager.java`(`create` 方法) + `PostCreationSetup.java` + `WorktreeCreateTest.java`
**依赖:** T4
**步骤:**
1. 实现 `public Worktree create(String name, String baseRef, boolean manual) throws IOException`:
   - `WorktreeSlug.validate(name)` 不通过即抛
   - `lock.lock(); try { ... } finally { lock.unlock(); }`;`active.containsKey(name)` 即抛
   - 算 `flatSlug`、`wtPath`、`branchName`
   - 若 `Files.exists(wtPath)`,用 `GitHelper.resolveHeadShaFromFS` 取 sha,构造 `Worktree` 放 `active`,**直接返回**(快速恢复,跳过 setup)
   - 否则跑 `git worktree add -B <branch> <wtPath> <baseRef>`,用 `GitHelper.gitProcess`
   - 失败时:递归删除已创建的目录,重新抛
   - 调 `PostCreationSetup.run(repoRoot, wtPath, symlinkDirs)`,失败仅 stderr 警告
   - 跑 `git -C <wtPath> rev-parse HEAD` 拿 headSha
   - 构造 `Worktree` 放 `active`,返回
2. 实现 `PostCreationSetup.run(...)`,四个 static 子函数:
   - `copyLocalConfigs(repoRoot, wtPath)`:对 `.gcode/config.yaml` / `.gcode/settings.local.yaml`,若主仓存在且 Worktree 不存在,`Files.copy`
   - `setupGitHooks(repoRoot, wtPath)`:优先 `.husky/`,回退 `git -C <repoRoot> config --get core.hooksPath` 拿主仓配置,若有值跑 `git -C <wtPath> config core.hooksPath <绝对路径>`
   - `symlinkLargeDirs(repoRoot, wtPath, symlinkDirs)`:对每个目录若主仓存在且 Worktree 不存在,`Files.createSymbolicLink(wtPath.resolve(dir), repoRoot.resolve(dir).toAbsolutePath())`
   - `copyIncludedIgnored(repoRoot, wtPath)`:读 `.worktreeinclude` 模式;跑 `git -C <repoRoot> ls-files --others --ignored --exclude-standard --directory` 列出忽略文件;每个文件用 `FileSystems.getDefault().getPathMatcher("glob:" + pat)` 匹配;命中则 `Files.copy` 到 Worktree
   - 每个子函数 try/catch,失败只往 stderr 写一行 `worktree: setup <step>: <err>` 警告,继续下个步骤
3. 测试:在临时 git 仓库覆盖:create 成功后目录存在、分支存在、设置 A 复制 settings.local.yaml、设置 C 软链 node_modules、设置 D 按 .worktreeinclude 复制 .env;快速恢复路径不调 git(可观察临时仓库 `git reflog` 或在子进程统计)

**验证:** `mvn -q test -Dtest=WorktreeCreateTest`

## T6: Enter / Exit / Remove / AutoCleanup**文件:** `WorktreeManager.java`(生命周期方法) + `WorktreeLifecycleTest.java`
**依赖:** T5
**步骤:**
1. 在 `WorktreeManager` 上实现 `enter` / `exit` / `remove` / `autoCleanup`
2. `public WorktreeSession enter(String name) throws IOException`:
   - 加锁取 `active.get(name)`
   - `Path.of("").toAbsolutePath()` 取原 cwd 字符串
   - `git -C <repoRoot> rev-parse --abbrev-ref HEAD` 与 `git -C <repoRoot> rev-parse HEAD` 取原状态(失败用空字符串兜底)
   - 生成 `sessionId = UUID.randomUUID().toString()`
   - 写 `currentSession` 字段,`SessionStore.save`
3. `public ExitReport exit(String name, ExitAction action, ExitOptions opts) throws IOException`:
   - 加锁;校验 `currentSession` 非空且 `worktreeName().equals(name)`;否则抛
   - 取 `active.get(name)`;若 null 抛
   - `action == REMOVE && !opts.discardChanges()`:调 `hasWorktreeChanges`,true 则抛 `WorktreeHasChangesException`
   - 记录 `originalCwd`(供上层 TUI 还原 activeCwd)
   - `currentSession = null`,`SessionStore.save(sessionFile, null)`
   - `action == REMOVE`:`git worktree remove --force <path>`,`Thread.sleep(100)`,`git branch -D <branch>`,`active.remove(name)`
   - 返回 `ExitReport`
4. `public void remove(String name, ExitOptions opts) throws IOException`:类似 `exit` 的 REMOVE 分支,但允许非当前 session;变更保护同
5. `public AutoCleanupReport autoCleanup(String name) throws IOException`:
   - 取 `active.get(name)`;`manual=true` 直接 `kept=true` 返回(带 path/branch)
   - `hasWorktreeChanges=false` 调 `remove(name, new ExitOptions(true))`,返回 `kept=false`
   - 有变更:`kept=true`,返回 path/branch
6. 测试:`enter` 不改 JVM cwd、`exit` 后 `activeCwd` 还原由 TUI 接管这里只断言 `currentSession` 已清空、`exit` remove 变更保护、`autoCleanup` manual/无变更/有变更三种分支

**验证:** `mvn -q test -Dtest=WorktreeLifecycleTest`

## T7: SweepStale**文件:** `WorktreeManager.java`(`sweepStale`) + `WorktreeNaming.java` + `WorktreeSweepTest.java`
**依赖:** T6
**步骤:**
1. `WorktreeNaming` 内定义 `public static final Pattern EPHEMERAL_PATTERN = Pattern.compile("^agent-a[0-9a-f]{7}$");`
2. 实现 `public List<String> sweepStale(Instant cutoff)`:
   - `Files.list(worktreeDir)`(try-with-resources)遍历
   - 对每个目录:不匹配 pattern 跳过;`Files.getLastModifiedTime` > cutoff 跳过;`currentSession != null && Path.of(currentSession.worktreePath()).equals(sub)` 跳过
   - 跑 `GitHelper.hasWorktreeChanges(子路径, "HEAD")` true 跳过(fail-closed)
   - 额外:`git -C <子路径> rev-list --max-count=1 HEAD --not --remotes` 非空跳过(有未推送 commit 也保留)
   - 通过的:调 `remove(name, new ExitOptions(true))`,记 `removed`
3. 实现 `public static String randomAgentName()`(返回 `"agent-a" + 7位随机 hex`),用 `SecureRandom` 取 4 字节 → hex 截前 7 位
4. 测试:构造三个目录(匹配模式无变更、匹配模式有变更、不匹配模式),`sweepStale` 只删第一个

**验证:** `mvn -q test -Dtest=WorktreeSweepTest`

## T8: tool ctx**文件:** `ToolContext.java` + `ToolContextTest.java`
**依赖:** 无(并行 T1-T7)
**步骤:**
1. 新建/扩展 `dev.gcode.tool.ToolContext` record,字段 `Optional<Path> cwd`(若已有 ctx record,把 cwd 合并到既有 record 末尾)
2. 实现 `static ToolContext root()` 返回空 ctx;`withCwd(Path dir)` 返回新 ctx
3. 实现 `Path resolvePath(String p)`:
   - `p == null || p.isEmpty()`:返回 ctx cwd 或 `Path.of("").toAbsolutePath()` 兜底
   - `Path.of(p).isAbsolute()`:返回 `Path.of(p).normalize()`
   - 否则:`base = ctx.cwd().orElseGet(() -> Path.of("").toAbsolutePath()); return base.resolve(p).normalize();`
4. 测试:覆盖三种 path、ctx 无 cwd 时回落到 JVM 当前目录、空字符串返回 cwd 本身

**验证:** `mvn -q test -Dtest=ToolContextTest`

## T9: 改造 6 个核心工具**文件:** `BashTool.java` / `ReadFileTool.java` / `WriteFileTool.java` / `EditFileTool.java` / `GlobTool.java` / `GrepTool.java`
**依赖:** T8
**步骤:**
1. `ReadFileTool`:在 `Files.readAllBytes(...)` 前 `Path abs = ctx.resolvePath(args.path());`,后续用 `abs`
2. `WriteFileTool`:同样改造 path;若需要 `Files.createDirectories` 时也用 `abs.getParent()`
3. `EditFileTool`:同样
4. `GlobTool`:`String root = args.path() == null ? "." : args.path();`;然后 `Path absRoot = ctx.resolvePath(root);`;`Files.walk(absRoot)` 用 absRoot;返回路径仍按相对 root 输出(保持现有行为)
5. `GrepTool`:与 `GlobTool` 同
6. `BashTool`:在 `ProcessBuilder pb = ...` 之后,`pb.directory(ctx.resolvePath("").toFile());`(空字符串解析为 cwd 本身)
7. 不改 Schema(`parameters()` 不变),不改 description
8. 单测可放各 tool 测试或新增 `ToolCwdTest`——构造 `ctx.withCwd(tmpDir)`,在 tmpDir 里准备文件,调工具断言读到对应内容

**验证:** `mvn -q test -Dtest='*ToolTest,*ToolCwdTest'`

## T10: subagent.Definition isolation**文件:** `Definition.java` / `Parser.java` / `ParserTest.java`
**依赖:** 无
**步骤:**
1. `Definition.java`:record 加 `String isolation`(末尾参数,默认值通过 `@JsonProperty(defaultValue = "")` 或解析时填空)
2. `Parser.java`:frontmatter Map 取 `isolation` 字段,校验合法值 `""` / `"worktree"`,非法值 stderr 警告并回落 `""`,把结果填到 `Definition`
3. `ParserTest`:增加测试覆盖 `isolation: worktree` 解析成功、`isolation: gibberish` 警告并回落空

**验证:** `mvn -q test -Dtest=ParserTest`

## T11: AgentWorktreeRunner**文件:** `AgentWorktreeRunner.java` + `AgentWorktreeRunnerTest.java`
**依赖:** T6, T8, T10
**步骤:**
1. 新建 `AgentWorktreeRunner`,持 `WorktreeManager wtMgr`(构造器注入);agent 包直接 import `dev.gcode.worktree.*`(worktree 包不依赖 agent,无循环)
2. 实现 `static String buildWorktreeNotice(Path parentCwd, Path wtPath)`(按 spec F22 模板)
3. 实现 `static String randomAgentName()`,委托 `WorktreeNaming.randomAgentName()`
4. 实现 `String executeWithWorktree(ToolContext ctx, Definition def, Agent subAgent, Conversation subConv, String prompt, BlockingQueue<Event> events) throws IOException`:
   - `name = randomAgentName()`
   - `wt = wtMgr.create(name, "HEAD", false)`
   - `Path parentCwd = Path.of("").toAbsolutePath();`
   - `notice = buildWorktreeNotice(parentCwd, wt.path())`
   - `taskText = notice + "\n\n" + prompt`
   - `ctx = ctx.withCwd(wt.path())`
   - `finalText = subAgent.runToCompletion(ctx, subConv, taskText, events)`
   - `report = wtMgr.autoCleanup(name)`
   - 若 `report.kept()`,把保留信息追加到 `finalText`
   - 返回 `finalText`
5. 单测:用真实临时 git 仓库构造 `WorktreeManager`;subAgent 用 mock Provider(返回空文本即结束);断言 `wt.path()` 被传到 ctx、`autoCleanup` 被调用

**验证:** `mvn -q test -Dtest=AgentWorktreeRunnerTest`

## T12: AgentTool 接入 isolation 分支**文件:** `AgentTool.java`
**依赖:** T11
**步骤:**
1. `AgentTool` 加字段 `WorktreeManager wtMgr`(允许 null)
2. 构造器 `new AgentTool(catalog, taskMgr, parent, bgEnabled, wtMgr)`——签名末尾追加 `wtMgr`
3. 在 `execute` 内,若 `def.isolation().equals("worktree")`:
   - `wtMgr == null` → 返回 `ToolResult.error("worktree manager not configured")`
   - `background == true` → 本期 isolation+worktree 强制走前台路径(忽略 background)
   - 调 `new AgentWorktreeRunner(wtMgr).executeWithWorktree(ctx, def, subAgent, subConv, args.prompt(), events)` 替代直接 `runToCompletion`
4. 改 `Main.java` 构造 `AgentTool` 时传入 `wtMgr`

**验证:** `mvn -q test -Dtest='Agent*Test'`

## T13: command 包加 WorktreeAccessor + /worktree handler**文件:** `Ui.java` / `WorktreeAccessor.java` / `WorktreeCommand.java` / `Builtins.java` / `BuiltinsTest.java`
**依赖:** T6
**步骤:**
1. `Ui.java`:加方法 `WorktreeAccessor worktreeAccessor()`(可返回 null);`NopUi` 实现返回 null
2. `WorktreeAccessor.java`:新增接口(spec F24-F28 所列方法) + `WorktreeSummary` record
3. `WorktreeCommand.java`:实现 `Command` 接口(`name()`="worktree"、`kind()`=LOCAL、`handle(ctx, ui, args)`)——`args` 是 `/worktree` 后面的全部尾随字符串;split 子命令 + 其余参数
   - `create <slug>` → `ui.worktreeAccessor().create(slug)`,输出 `Worktree 已创建: <path> (分支 <branch>)`
   - `list` → 遍历 `list()`,按格式输出
   - `enter <slug>` → `enter(slug)`,输出 `已进入 <slug>: <path>`
   - `exit [--remove] [--discard]` → 解析 flag,调 `exit`
   - `remove <slug> [--discard]` → 调 `remove`
   - 未知子命令报错
4. `Builtins.java`:`register(new WorktreeCommand())`——需要 command parser 支持带参数命令把 tail 透传到 handler。若现有 parser 在带参时让 lookup miss,**最小改动**:扩展 `Parse` 使带参命令仍能命中,把 tail 通过 `handle(ctx, ui, args)` 的 args 参数传入
5. 测试:测试 `WorktreeCommand.handle` 分发逻辑(用 stub Ui / stub Accessor)

**验证:** `mvn -q test -Dtest='BuiltinsTest,WorktreeCommandTest'`

## T14: TUI 适配 + 注入 ctx**文件:** `TuiWorktreeAccessor.java` + `TuiApp.java`
**依赖:** T11, T13
**步骤:**
1. `TuiWorktreeAccessor.java`:实现 `WorktreeAccessor` 接口,内部持 `WorktreeManager` + `Consumer<Path> activeCwdSetter`,把方法转发并组装 `WorktreeSummary` 列表;`enter` 内部调 `manager.enter` 后调 setter 把 activeCwd 写到 TUI
2. `TuiApp.java`:字段加 `WorktreeManager worktreeMgr`、`Path activeCwd`(null 表示 JVM 当前目录)
3. `TuiApp.Builder` 加 `worktreeMgr(WorktreeManager)` 方法;构造时若 `manager.currentSession()` 非 null,设 `activeCwd = Path.of(session.worktreePath())`
4. 实现 `worktreeAccessor()` 方法返回 `TuiWorktreeAccessor` 实例
5. 在主 Agent run 调用入口(找 `TuiApp` 里 `agent.run(ctx, conv, mode)` 调用点),前置 `ctx = ctx.withCwd(effectiveCwd());`
6. `effectiveCwd()`:若 `activeCwd != null` 返回 `activeCwd`,否则返回 `Path.of("").toAbsolutePath()`

**验证:** `mvn -q -DskipTests package` 通过;`/worktree create x` + `/worktree enter x` + Read file(相对路径) 在 worktree 内成功

## T15: Main 接入**文件:** `Main.java` + `.gitignore`
**依赖:** T4-T14 全部
**步骤:**
1. `Main.java`:在 `var subagentCatalog = SubagentCatalog.load(root);` 后加:
   ```java
   WorktreeManager worktreeMgr;
   try {
       worktreeMgr = new WorktreeManager(root);
       final var mgr = worktreeMgr;
       Thread.startVirtualThread(() ->
           mgr.sweepStale(Instant.now().minus(24, ChronoUnit.HOURS)));
   } catch (IOException werr) {
       System.err.println("Worktree 管理器降级: " + werr.getMessage());
       worktreeMgr = null;
   }
   ```
2. `new AgentTool(...)` 调用末尾追加 `worktreeMgr` 参数
3. `TuiApp.builder()` 链上新增 `.worktreeMgr(worktreeMgr)`
4. `.gitignore` 追加:
   ```
   # ch14: Worktree 隔离副本(仅供 SubAgent 与手动管理使用)
   .gcode/worktrees/
   .gcode/worktree_session.json
   ```

**验证:** `mvn -q -DskipTests package`、`mvn -q spotless:check`、`mvn -q test` 全过

## T16: 端到端 tmux 验证**文件:** 无代码修改,运行测试
**依赖:** T15
**步骤:**
1. `mvn -q -DskipTests package` 产出 `target/gcode-*.jar`
2. 准备项目级自定义 Agent `.gcode/agents/worktree-writer.md`(详见 checklist 场景 1)
3. tmux 启动 gcode(`java -jar target/gcode-*.jar`),跑 checklist 端到端场景
4. 通过即标记 T16 完成

**验证:** 见 checklist.md 场景 1-6

## 执行顺序

```
T1 (slug)
  ↓
T2 (session) — T3 (git helper) — T8 (tool/ctx)
                                    ↓
T4 (manager construct)          T9 (改造 6 tools)
  ↓
T5 (create + setup)
  ↓
T6 (lifecycle)
  ↓
T7 (sweep)
  ↓
T10 (subagent.isolation)
  ↓
T11 (AgentWorktreeRunner)
  ↓
T12 (AgentTool 接入)
  ↓
T13 (/worktree command) — T14 (TUI 接入)
                              ↓
T15 (Main.java + .gitignore)
  ↓
T16 (tmux 端到端)
```

T1/T2/T3/T8 之间可并行;其余按依赖顺序。
````

````markdown
# Worktree 隔离 Checklist

> 每一项通过运行代码或观察行为来验证,聚焦系统行为。

## 实现完整性### worktree 包

- [ ] `dev.gcode.worktree` 包存在且编译通过(验证:`mvn -q -pl . -am -DskipTests compile`)
- [ ] `WorktreeSlug.validate` 对合法/非法 case 行为符合 spec F1(验证:`mvn -q test -Dtest=WorktreeSlugTest`)
- [ ] `WorktreeSlug.flatten("team/alice").equals("team+alice")`(验证:同上)
- [ ] `WorktreeSession` JSON 序列化/反序列化字段名为下划线小写(`@JsonProperty`)(验证:`mvn -q test -Dtest=SessionStoreTest`)
- [ ] `SessionStore.save` 原子写——失败前不破坏既有文件;`save(path, null)` 写入 `null`(验证:同上)
- [ ] `GitHelper.gitProcess` 设置 `GIT_TERMINAL_PROMPT=0` + `GIT_ASKPASS=""`、stdin redirect 自 `/dev/null`(验证:`mvn -q test -Dtest=GitHelperTest`)
- [ ] `GitHelper.hasWorktreeChanges` 在临时 git 仓库内:无修改返回 false;改一个文件返回 true;git 命令出错 fail-closed 返回 true(验证:同上)
- [ ] `GitHelper.resolveHeadShaFromFS` 在真实 worktree 路径下返回 commit SHA(验证:`mvn -q test -Dtest=GitHelperTest#resolveHead`)
- [ ] `new WorktreeManager(repoRoot)` 校验 repoRoot 是 git 仓库;非 git 目录抛 `IOException`(验证:`mvn -q test -Dtest=WorktreeManagerTest`)
- [ ] `new WorktreeManager` 加载已存在的 session 文件;指向不存在目录的 session 自动清空(验证:同上)
- [ ] `manager.create("alice", "HEAD", true)` 在 `.gcode/worktrees/alice/` 下落地 + 分支 `worktree-alice`(验证:`mvn -q test -Dtest=WorktreeCreateTest`)
- [ ] `manager.create("team/alice", ...)` 落地 `.gcode/worktrees/team+alice/` + 分支 `worktree-team+alice`(验证:同上)
- [ ] `manager.create` 目录已存在时走快速恢复(不调 git;`active` 立即就绪)(验证:同上)
- [ ] `manager.create` 已 active 名字时再 create 抛异常(验证:同上)
- [ ] 创建后设置 A——`.gcode/settings.local.yaml` 被复制到 Worktree(验证:同上,需在测试 fixture 准备文件)
- [ ] 创建后设置 B——主仓 `.husky/` 存在时 Worktree git config 含 core.hooksPath(验证:`mvn -q test -Dtest=PostCreationSetupTest#hooks`)
- [ ] 创建后设置 C——主仓 node_modules 存在时 Worktree 内为软链(`Files.isSymbolicLink(...)` 为 true)(验证:`mvn -q test -Dtest=PostCreationSetupTest#symlink`)
- [ ] 创建后设置 D——主仓 `.worktreeinclude` 模式命中的 ignored 文件被复制到 Worktree(验证:`mvn -q test -Dtest=PostCreationSetupTest#includeIgnored`)
- [ ] `manager.enter(name)` 不改变 JVM 当前目录 `Path.of("").toAbsolutePath()`,返回 session 含 `originalCwd`/`worktreePath`/`sessionId` 等字段(验证:`mvn -q test -Dtest=WorktreeLifecycleTest#enter`)
- [ ] `manager.enter` 持久化 session 到 `.gcode/worktree_session.json`(验证:同上)
- [ ] `manager.exit(name, REMOVE, new ExitOptions(false))` 有变更时抛 `WorktreeHasChangesException`,Worktree 目录仍在(验证:`mvn -q test -Dtest=WorktreeLifecycleTest#exit`)
- [ ] `manager.exit(name, REMOVE, new ExitOptions(true))` 成功删除 Worktree + 分支;session 文件被清空(验证:同上)
- [ ] `manager.exit` 返回的 `ExitReport.path()` 等于原 wt.path()(让上层 UI 还原 activeCwd)(验证:同上)
- [ ] `manager.remove(name, opts)` 与 `exit` 的 REMOVE 分支一致,但允许非当前 session(验证:同上)
- [ ] `manager.autoCleanup` 对 `manual=true` 直接 `kept=true`(验证:`mvn -q test -Dtest=WorktreeLifecycleTest#autoCleanup`)
- [ ] `manager.autoCleanup` 无变更时 remove 并返回 `kept=false`;有变更返回 `kept=true`(验证:同上)
- [ ] `manager.sweepStale` 第一层只识别 `agent-a[0-9a-f]{7}` 模式;手动命名跳过(验证:`mvn -q test -Dtest=WorktreeSweepTest`)
- [ ] `manager.sweepStale` 跳过当前 session 的目录(验证:同上)
- [ ] `manager.sweepStale` 有未提交修改 / 未推送 commit 的目录跳过(fail-closed)(验证:同上)
- [ ] `WorktreeNaming.randomAgentName` 返回形如 `agent-a[0-9a-f]{7}` 的字符串(验证:`mvn -q test -Dtest=WorktreeNamingTest`)

### tool 包 ctx 改造

- [ ] `ToolContext.withCwd` / `cwd()` / `resolvePath` 三方法存在(验证:`mvn -q test -Dtest=ToolContextTest`)
- [ ] `resolvePath` 对绝对路径直接返回;对相对路径用 ctx cwd 或 JVM 当前目录拼接(验证:同上)
- [ ] `read_file(path="a.txt")` 在 `ctx.withCwd(tmpDir)` 下读 `tmpDir/a.txt`(验证:`mvn -q test -Dtest=ReadFileToolCwdTest`)
- [ ] `write_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `edit_file(path="a.txt")` + ctx cwd 同上(验证:同上)
- [ ] `bash(command="pwd")` + ctx cwd 输出 cwd 路径(验证:`mvn -q test -Dtest=BashToolCwdTest`)
- [ ] `glob(pattern="*.txt")` + ctx cwd 在 cwd 内搜索(验证:`mvn -q test -Dtest=GlobToolCwdTest`)
- [ ] `grep` + ctx cwd 同上(验证:`mvn -q test -Dtest=GrepToolCwdTest`)
- [ ] 工具 schema 不变——`parameters()` 不含新字段(验证:对比 ch13 测试快照,或断言 keys)

### subagent 包扩展

- [ ] `subagent.Definition` 含 `String isolation()` accessor(验证:`mvn -q test -Dtest=DefinitionTest`)
- [ ] `Parser` 正确解析 `isolation: worktree`(验证:`mvn -q test -Dtest=ParserTest#isolation`)
- [ ] 非法 `isolation` 值时 stderr 警告并回落 `""`(验证:同上)
- [ ] 既有定义不写 isolation 时 `def.isolation().equals("")`(验证:同上)

### agent 包扩展

- [ ] `AgentTool` 含 `WorktreeManager wtMgr` 字段;构造器签名末尾接收 `wtMgr`(验证:`mvn -q -DskipTests compile`)
- [ ] `AgentWorktreeRunner.executeWithWorktree` 调用 `manager.create` + `autoCleanup`,期间通过 ctx 传 `wt.path()`(验证:`mvn -q test -Dtest=AgentWorktreeRunnerTest`)
- [ ] `AgentWorktreeRunner.buildWorktreeNotice` 输出含 `<worktree-context>` 标签 + 父目录 + 工作目录(验证:同上)
- [ ] `AgentTool#execute` 在 `def.isolation().equals("worktree")` 时走 worktree 分支(验证:同上)
- [ ] `AgentTool#execute` 在 `wtMgr==null` 且 isolation=worktree 时返回 `ToolResult.error`(验证:同上)
- [ ] `AgentTool#execute` 在 isolation=worktree + background=true 时强制走前台路径(验证:同上)

### command 包扩展

- [ ] `command.WorktreeSummary` 与 `WorktreeAccessor` 接口存在(验证:`mvn -q -DskipTests compile`)
- [ ] `Ui` 接口加 `worktreeAccessor()` 方法;`NopUi` 返回 null(验证:同上)
- [ ] `/worktree` 命令被注册,`Builtins.lookup("worktree")` 命中(验证:`mvn -q test -Dtest=BuiltinsTest#registered`)
- [ ] `WorktreeCommand.handle` 分发子命令 create/list/enter/exit/remove(验证:`mvn -q test -Dtest=WorktreeCommandTest`)
- [ ] `WorktreeCommand.handle` 在 `ui.worktreeAccessor()` 返回 null 时报错(验证:同上)

### tui 包扩展

- [ ] `TuiApp` 含 `WorktreeManager worktreeMgr` 与 `Path activeCwd` 字段(验证:`mvn -q -DskipTests compile`)
- [ ] `TuiApp.Builder` 接收 `worktreeMgr` 参数;启动时若 `manager.currentSession()` 非 null,设 `activeCwd = Path.of(session.worktreePath())`(验证:`mvn -q test -Dtest=TuiAppStartupTest`)
- [ ] 主 Agent run 前 ctx 注入 cwd——可通过日志或 mock Provider 断言 tool 调用收到的 cwd(验证:同上)
- [ ] `TuiWorktreeAccessor` 实现 `WorktreeAccessor` 接口(验证:`mvn -q -DskipTests package`)

### main 接入

- [ ] `Main.java` 构造 `WorktreeManager`,失败 stderr 警告 + 降级(验证:`mvn -q -DskipTests package`)
- [ ] `new AgentTool(...)` 调用末尾追加 `worktreeMgr`(验证:同上)
- [ ] `TuiApp.builder()` 链上有 `.worktreeMgr(...)`(验证:同上)
- [ ] 启动时通过 `Thread.startVirtualThread` 跑 `sweepStale`(验证:`grep` 检查代码)
- [ ] `.gitignore` 追加 `.gcode/worktrees/` 与 `.gcode/worktree_session.json`(验证:`git check-ignore .gcode/worktrees/test`)

## 集成

- [ ] `subagent.Definition#isolation` + `agent.AgentTool` 协同——`isolation:worktree` 的 SubAgent 启动时自动创建 Worktree(验证:`AgentWorktreeRunnerTest` 通过)
- [ ] tool ctx `withCwd` + `AgentTool.executeWithWorktree` 协同——SubAgent 在 Worktree 内的工具调用使用 `wt.path()` 作为 cwd(验证:集成测试,在临时 git repo 跑一个 mock subagent)
- [ ] 主 Agent 工具列表稳定——5 个核心工具 + Agent + TaskList + TaskGet + TaskStop + SendMessage + worktree 不暴露新工具(验证:工具数计数)
- [ ] worktree 包 + subagent 包 + agent 包 + command 包 + tui 包之间无导入循环(验证:`mvn -q -DskipTests package`)

## 编译与测试

- [ ] 项目编译无错误:`mvn -q -DskipTests package`
- [ ] 所有单元测试通过:`mvn -q test`
- [ ] Spotless 检查通过:`mvn -q spotless:check`

## 端到端场景(tmux 实跑)

每个场景在 tmux 内启动一个 gcode 实例完成,验证可视化行为。

**通用预置:**
- 当前目录 `cd /Users/codemelo/gcode`
- 已执行 `mvn -q -DskipTests package`

### 场景 1:isolation:worktree 子 Agent 修改文件不影响主目录**预置:** 创建项目级自定义 Agent:

```
.gcode/agents/worktree-writer.md
---
name: worktree-writer
description: 在 Worktree 内写文件的测试 Agent
permissionMode: dontAsk
maxTurns: 5
isolation: worktree
---

你是一个测试 Agent。当用户让你写文件时,直接用 write_file 工具写,不要询问。
```

并准备一个主目录文件 `echo "MAIN" > scratch_ch14.txt`(测试前 git status 干净,这个文件未跟踪)。

**步骤:**
- [ ] tmux 启动:`tmux new-session -d -s ch14 -x 200 -y 50 "java -jar target/gcode-*.jar"`
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『把 scratch_ch14.txt 的内容覆盖为 SUBAGENT,只用 write_file 工具』」
- [ ] 子 Agent 跑动,scrollback 出现 `Agent(...)` 行
- [ ] tool_result 中末尾含 `[Worktree 保留: .gcode/worktrees/agent-a... ,分支 worktree-agent-a...]`(因为有未提交修改,autoCleanup 保留)
- [ ] **主目录** `cat scratch_ch14.txt` 仍为 `MAIN`(验证主目录未被改)
- [ ] **Worktree 副本** `cat .gcode/worktrees/agent-a*/scratch_ch14.txt` 为 `SUBAGENT`
- [ ] tmux 截屏断言:`tmux capture-pane -p -t ch14 | grep -i "worktree"`
- [ ] 清理:`rm scratch_ch14.txt`,删除残留 worktree:gcode 内 `/worktree remove agent-a... --discard`(或 `git worktree remove --force` 手动清)
- [ ] `tmux kill-session -t ch14`

### 场景 2:isolation:worktree 子 Agent 无变更时自动清理**预置:** 同场景 1 的 `worktree-writer.md`(已存在)。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:「用 Agent 工具调 subagent_type=worktree-writer,prompt 是『用 read_file 读 README.md 头 5 行,然后用 30 字总结』」
- [ ] 子 Agent 跑动,tool_result 是总结文本
- [ ] tool_result **不含**「Worktree 保留」字样(因为读文件不产生修改,autoCleanup 直接清理)
- [ ] `ls .gcode/worktrees/` 不存在与本次任务对应的 `agent-a*` 目录(已被 autoCleanup 删除)
- [ ] `tmux kill-session`

### 场景 3:`/worktree create` + `/worktree list` 手动管理**预置:** 当前在 main 分支,git 工作区干净。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create demo-feature`
- [ ] scrollback 显示 `Worktree 已创建: .gcode/worktrees/demo-feature (分支 worktree-demo-feature)`
- [ ] 输入:`/worktree list`
- [ ] scrollback 显示一行含 `demo-feature` 的列表项,标记 `[manual]`(`manual=true`)
- [ ] tmux 外验证:`ls .gcode/worktrees/demo-feature/` 含正常 gcode 仓库内容;`git -C .gcode/worktrees/demo-feature branch` 显示在 `worktree-demo-feature`
- [ ] 清理:输入 `/worktree remove demo-feature --discard`
- [ ] 验证 `.gcode/worktrees/demo-feature` 已不存在
- [ ] `tmux kill-session`

### 场景 4:`/worktree exit` 变更保护**预置:** 同场景 3 创建好 `demo-feature`。

**步骤:**
- [ ] 手动写一个修改:`echo "modified" > .gcode/worktrees/demo-feature/test.txt`
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree enter demo-feature`
- [ ] 输入:`/worktree exit --remove` (不加 `--discard`)
- [ ] scrollback 显示错误 `worktree has uncommitted changes or new commits`(或对应中文消息)
- [ ] 输入:`/worktree exit --remove --discard`
- [ ] scrollback 显示成功消息,worktree 已被删除
- [ ] `tmux kill-session`

### 场景 5:explicit cwd——`/worktree enter` 后工具调用用 worktree 路径**预置:** 创建 worktree 并准备测试文件。

**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create cwd-test`
- [ ] 在 tmux 外:`echo "in-worktree-only" > .gcode/worktrees/cwd-test/probe.txt`(主目录无 probe.txt)
- [ ] tmux 内输入:`/worktree enter cwd-test`
- [ ] 输入:「用 read_file 读 probe.txt」
- [ ] 主 Agent 调 `read_file` 工具(path=probe.txt 相对路径)
- [ ] tool_result 应为 `in-worktree-only`(证明 cwd 解析到 worktree 路径)
- [ ] 输入:`/worktree exit`,activeCwd 恢复为 JVM 当前目录
- [ ] 再输入:「用 read_file 读 probe.txt」
- [ ] tool_result 报「无法访问文件 probe.txt」(主目录没这文件)
- [ ] 清理:`/worktree remove cwd-test --discard`
- [ ] `tmux kill-session`

### 场景 6:Slug 校验阻止路径遍历**步骤:**
- [ ] tmux 启动 gcode
- [ ] 输入:`/worktree create ../etc`
- [ ] scrollback 显示错误,含「invalid」或「拒绝」(不创建 `.gcode/etc/` 或类似)
- [ ] 输入:`/worktree create ..`
- [ ] 同样错误
- [ ] 输入:`/worktree create normal_one`
- [ ] 成功创建
- [ ] 清理:`/worktree remove normal_one --discard`
- [ ] `tmux kill-session`
````

### TypeScript

```markdown
# Worktree 隔离 Spec## 背景上一章 SubAgent 在消息、权限、文件读缓存、token 计数等维度做了隔离，但**文件系统**仍然共享。主 Agent 与后台子 Agent（以及下一章 Agent Team 的队员）在同一时刻并发读写同一份工作目录的文件，会出现读到对方写了一半的文件、互相覆盖修改等并行冲突——本质就是经典的并行开发文件冲突。

Git 分支只能做**时间维度**的隔离（切换分支时工作目录被覆盖，同一时刻只有一个工作目录），不能解决并行问题；切分支还会刷被切文件的 mtime，触发依赖追踪型构建工具的链式重编。

需要的是**空间维度**的隔离：同一仓库同时挂多个工作目录、共享版本库、各自一个分支。这就是 Git Worktree (Git 2.5+) 的能力。本章把 Worktree 能力以**两个工具**的形式暴露给模型，由模型在需要时自行决定何时进入隔离副本、何时退出并清理。

gcode 现有相关基础设施：
- 工具系统支持「按需暴露」标记，配合工具发现机制可以让某些工具默认不出现在工具清单里，只有被显式发现后才可调用
- SubAgent 定义支持 `isolation` 字段，由上一章解析 frontmatter 时透传
- 工具白名单机制决定异步后台 SubAgent 可用的工具集合
- 项目根 `.gcode/worktrees/` 是 Worktree 的落盘目录，应由 `.gitignore` 排除

本章不引入 Worktree 间合并策略、跨目录代码同步、多 Agent 并行编排，这些属于上层 / 下一章范畴。

## 目标- **G1**: 为 Worktree 生命周期提供一组底层能力——按 slug 创建（含快速恢复）、读取当前 HEAD 与分支、检测变更、强制清理目录与分支，覆盖创建、状态读取、变更检测、移除四个核心动作
- **G2**: 读取 Worktree 当前 commit SHA 与所在分支时**不启动 git 子进程**，直接通过文件系统解析 git 的 HEAD 与 ref 文件，避免大仓库下子进程启动开销
- **G3**: 所有进入解析过程的 ref 名称都必须通过严格的安全字符与结构校验，遇到任何不安全的 ref 立即视为空，防止路径遍历与 shell 注入
- **G4**: Worktree 目录统一落在仓库内不被追踪的位置 `.gcode/worktrees/<slug>/`，分支名固定 `worktree-<slug>`；创建时若目录已存在则走快速恢复路径，毫秒级返回
- **G5**: 创建 Worktree 时即便存在同名残留分支也不应失败——分支命名与创建动作应允许覆盖式重建
- **G6**: 创建成功后做四步环境初始化，全部 best-effort，失败只警告不中断：A 把项目级 gcode 配置目录整体复制到 Worktree；B 配置 Worktree 内的 git hooks 路径，优先使用项目维护的 hooks 目录，回退到默认 hooks 目录；C 当主仓存在大型依赖安装目录时在 Worktree 内建软链复用；D 读取项目根 `.worktreeinclude` 中列出的相对路径，把对应被忽略但运行需要的文件或目录复制到 Worktree
- **G7**: Worktree 能力以**两个工具**形式暴露给模型——「进入 Worktree」与「退出 Worktree」；模型在需要长任务隔离时显式调用，拿到 Worktree 路径、分支、HEAD，然后在后续工具调用里把这些信息作为参数显式传入
- **G8**: 这两个工具默认对模型**不可见**——它们不出现在初始工具清单里，模型必须先通过工具发现机制按关键词搜索到、解锁后才能调用；避免在所有上下文里常驻「你可以开 Worktree」的暗示
- **G9**: 「进入 Worktree」工具对 slug 的校验比通用 ref 校验更严格——只接受字母、数字、连字符、下划线组合，禁止任何路径分隔符与点号，让 Worktree 名永远是一段简单标识
- **G10**: 「退出 Worktree」工具接收 Worktree 路径、分支、仓库根目录三个必填参数，以及一个可选的基准 commit 用于变更检测；未传基准 commit 或检测无变更时执行清理；检测到有变更时保留 Worktree 并在输出里告知路径与分支供模型后续合并
- **G11**: 清理动作分两步——先删除 Worktree 目录，再删除对应分支；任一步失败都不应抛错中断，保证幂等（Worktree 或分支可能已被外部清掉）
- **G12**: 变更检测同时考察工作区状态与 HEAD 是否相对基准 commit 前进；任一探测过程出错统一按「有变更」处理，宁可保留也不要误删
- **G13**: SubAgent 定义中的 `isolation` 字段保留并继续被 frontmatter 解析，但本章不在 SubAgent 启动路径里自动包裹 Worktree——隔离能力的触发完全由模型显式调用 Worktree 工具完成，`isolation` 字段为后续章节扩展预留
- **G14**: 异步后台 SubAgent 的工具白名单包含这两个 Worktree 工具，让后台任务也能在需要时进入隔离副本
- **G15**: 与现有工具协同——Worktree 内工作时由模型自己把 Worktree 路径作为绝对路径参数传给后续读写工具，不改动既有工具签名

## 功能需求### 工具暴露- **F1**: 「进入 Worktree」工具——
  - 入参仅一个 `slug`（必填字符串）
  - 缺失或非法时返回错误结果，并在输出中说明 slug 的字符集要求
  - slug 必须只含字母、数字、连字符、下划线；任何其他字符（含路径分隔符与点号）一律拒绝
  - 校验通过后调用底层创建能力，成功时输出 Worktree 路径、分支名、HEAD commit 三项信息
  - 底层抛错时返回错误结果，输出含错误说明
- **F2**: 「退出 Worktree」工具——
  - 入参：Worktree 路径、分支名、仓库根目录三项必填；基准 commit 可选
  - 任一必填缺失时返回错误结果
  - 当传入基准 commit 时跑变更检测；未传入时视为无变更
  - 无变更时执行清理，输出告知已清理及对应路径
  - 清理过程抛错时返回错误结果，输出含错误说明
  - 有变更时不删除任何东西，输出告知 Worktree 路径与分支供模型决定下一步动作

### Worktree 生命周期能力- **F3**: 按 slug 创建 Worktree 的能力——
  - 未指定仓库根目录时自行解析当前所在的 git 仓库根
  - Worktree 目录路径与分支名按统一规则推导（落在 `.gcode/worktrees/<slug>`，分支 `worktree-<slug>`）
  - 目录已存在时走快速恢复路径：优先用纯文件系统方式读 HEAD，失败再回退到 git 子进程；不调用 git worktree 创建命令
  - 目录不存在时调用 git worktree 创建（允许同名残留分支被覆盖），创建完成后跑创建后初始化（F7-F11），最后再读 HEAD
  - 返回 Worktree 路径、分支名、HEAD commit、仓库根目录四项
- **F4**: 清理 Worktree 的能力——分两步执行：先用 git 工具命令强制移除 Worktree 目录，再删除对应分支；两步分别独立容错，任一抛错不传递给调用方
- **F5**: 变更检测的能力——
  - 输入 Worktree 路径与基准 commit
  - 工作区有未提交修改时返回有变更
  - 当前 HEAD commit 不等于基准 commit 时返回有变更
  - 检测过程任何环节抛错统一返回有变更（fail-closed）
- **F6**: 提供一段可拼接到 prompt 的 Worktree 提示文本生成能力，描述「你处于 Worktree 中、父目录在哪里、此处修改与父目录隔离」三类事实；本章不强制使用，供调用方按需拼接

### 纯文件系统读取 git 状态- **F7**: 解析 git 目录位置的能力——
  - 仓库根下的 `.git` 不存在时返回空
  - `.git` 是目录时直接返回该路径
  - `.git` 是文件时按其内容解析（要求以 `gitdir:` 开头），取出的相对路径基于仓库根拼成绝对路径
- **F8**: 直接从文件系统读取 Worktree HEAD commit SHA 的能力——读取 Worktree 自身的 git 目录指针，解析 HEAD，处理「在分支上」（再通过 ref 解析拿 SHA）与「detached」（HEAD 直接是 SHA）两种形态；任何异常返回空字符串
- **F9**: 直接从文件系统读取当前所在分支名的能力——解析 HEAD，处于分支时返回分支名，detached 时返回空字符串
- **F10**: HEAD 文件解析能力——
  - 内容形如 `ref: <ref>` 时取出 ref；ref 落在 `refs/heads/<name>` 区域且 name 通过安全校验时视为「在分支上」并返回分支名
  - 非分支区域的符号 ref（例如 bisect）经过安全校验后再走 ref 解析拿 SHA
  - 裸 SHA（匹配 SHA 字符规则）直接返回 SHA
  - 其余形态视为不可解析
- **F11**: ref 解析能力——先在松散 ref 文件位置查；找不到再扫 packed-refs 文件（跳过注释与对象 peel 行）；当 Worktree 自身的 git 目录里找不到时回退到 commondir 指向的共享 git 目录
- **F12**: ref 名称安全校验规则——非空；不以连字符或路径分隔符开头；不含 `..` 段；按路径分隔符切分每段都非空且不为 `.`；整体字符集限定在安全字符集合内

### 创建后初始化（best-effort）- **F13**: 创建后初始化作为一组独立子步骤依次执行，每个子步骤独立容错，单步失败不影响后续步骤，更不阻塞创建主路径
- **F14**: 复制项目级 gcode 配置目录——把项目根 gcode 配置目录递归复制到 Worktree 同位置
- **F15**: 配置 hooks 路径——依序探测项目内自定义 hooks 目录与默认 hooks 目录，命中第一个存在的目录后把该绝对路径设为 Worktree 的 hooks 路径
- **F16**: 软链大目录——主仓存在大型依赖安装目录且 Worktree 内无同名目录时建立软链复用
- **F17**: 复制 `.worktreeinclude` 列表——逐行读取项目根 `.worktreeinclude`；跳过空行与注释行；含路径遍历段（`..`）的行直接跳过；对每个相对路径：源不存在跳过；目标父目录按需创建；源为目录时整目录递归复制，否则按单文件复制

### 工具注册与可见性- **F18**: 启动时把这两个 Worktree 工具注册进工具系统
- **F19**: 这两个工具被标记为「按需暴露」——初始工具清单不包含它们；模型通过工具发现机制按描述或名称匹配关键词 `worktree` 后，工具才被解锁并出现在后续工具清单里
- **F20**: 异步后台 SubAgent 的工具白名单包含这两个 Worktree 工具

### SubAgent 定义透传- **F21**: SubAgent 定义中保留 `isolation` 字段，frontmatter 解析继续把该字段透传到定义对象
- **F22**: 本章不在 SubAgent 启动路径里消费 `isolation` 字段——是否进入 Worktree 由模型显式调用工具决定；该字段为后续章节扩展预留

## 非功能需求- **N1**: 工具清单稳定——两个 Worktree 工具默认不暴露，模型的初始上下文不会被它们污染，prompt cache 不抖动
- **N2**: 创建后初始化的任一子步骤失败都不阻塞创建主路径，每个子步骤独立容错
- **N3**: 与既有工具调用路径兼容——Worktree 模块对外能力可在工具的执行入口（异步）中无感调用
- **N4**: 直接从文件系统读取 HEAD 与 ref 必须不启动 git 子进程；创建时若目录已存在的快速恢复路径不调用 git worktree 创建命令
- **N5**: ref 安全校验集中在一处实现；任何不安全 ref 出现在 HEAD 或 packed-refs 中都被丢弃为空字符串，绝不参与后续路径拼接或子进程命令构造
- **N6**: 项目类型检查与测试用例必须全部通过
- **N7**: 中文友好——错误消息按现有项目风格，工具内部输出沿用现有读写工具的语言风格

## 不做的事

- Worktree 间的合并策略（交给上层 `git merge` / `git cherry-pick`）
- 跨 Worktree 代码同步、文件 watcher
- 多 Agent 并行编排 / Agent Team（下一章）
- SubAgent 启动路径里的自动 Worktree 包装（`isolation` 字段仅保留，不消费）
- Worktree 会话持久化与跨进程恢复
- 后台过期 Worktree 自动清理
- 用于 Worktree 管理的 TUI slash 命令
- Windows 平台 symlink 行为保证（best-effort 失败时跳过）

## 验收标准- **AC1**: 解析 git 目录位置的能力在普通 git 仓库根上返回 `<root>/.git`，在 Worktree 内返回 commondir 指向的共享 git 目录路径
- **AC2**: 纯文件系统读取 Worktree HEAD SHA 在合法 Worktree 路径下返回 40 或 64 字符的十六进制 SHA
- **AC3**: 读取当前分支的能力在处于分支时返回分支名，detached 时返回空字符串
- **AC4**: ref 安全校验对 `"../etc"` 返回 false，对 `"refs/heads/main"` 返回 true，对 `"-rf"` 返回 false
- **AC5**: 用 slug `alice` 创建 Worktree 后，`.gcode/worktrees/alice/` 下落地 Worktree，分支为 `worktree-alice`，返回的路径、分支、HEAD、仓库根四项均非空
- **AC6**: 已存在 Worktree 目录时再次创建走快速恢复——不调用 git worktree 创建命令，毫秒级返回
- **AC7**: 创建后初始化 A——主仓 gcode 配置目录被整目录复制到 Worktree 同位置
- **AC8**: 创建后初始化 B——主仓存在自定义 hooks 目录时 Worktree 的 hooks 路径被配置为该绝对路径
- **AC9**: 创建后初始化 C——主仓有大型依赖安装目录时 Worktree 内对应路径是软链
- **AC10**: 创建后初始化 D——主仓 `.worktreeinclude` 列出的相对路径被复制到 Worktree
- **AC11**: 变更检测在空 Worktree 且 SHA 匹配基准 commit 时返回无变更；修改任意一个文件后返回有变更；HEAD 已新增 commit 时也返回有变更
- **AC12**: 「进入 Worktree」工具用合法 slug 调用时成功返回多行输出，含 Worktree 路径、分支、HEAD 三项信息
- **AC13**: 「进入 Worktree」工具用非法 slug（含路径遍历）调用时返回错误结果，输出含字符集要求说明
- **AC14**: 「退出 Worktree」工具在无变更时清理 Worktree 并输出已清理；有变更时保留 Worktree 并在输出里告知路径与分支
- **AC15**: 工具清单接口在默认状态下不含这两个 Worktree 工具；通过工具发现机制按 `worktree` 关键词搜索并解锁后，再次获取工具清单时这两个工具出现
- **AC16**: 异步后台 SubAgent 的工具白名单包含这两个 Worktree 工具
- **AC17**: SubAgent 定义解析器在 frontmatter 含 `isolation: worktree` 时能正确把该值透传到定义对象
- **AC18**: 项目类型检查与测试用例全部通过
- **AC19**: 通过 tmux 实跑 gcode：用工具发现机制加载「进入 Worktree」工具并调用后，磁盘上出现 `.gcode/worktrees/<slug>/`；再调用「退出 Worktree」时清理或保留行为符合变更检测结果
```

````markdown
# Worktree 隔离 Plan## 技术栈

- 运行时：bun
- 语言：TypeScript 5.x（`tsc --noEmit` 用于类型检查，bun 直接执行 `.ts` / `.tsx`）
- 子进程：`node:child_process.execSync`（同步，避免 Promise 链路）
- 文件系统：`node:fs`（`cpSync` / `symlinkSync` / `readFileSync` / `statSync` / `existsSync` / `mkdirSync`）
- 路径处理：`node:path`（`join` / `dirname` / `isAbsolute`）
- TUI：Ink + React 18（工具注册入口在 `src/tui/app.tsx`）
- LLM SDK：`@anthropic-ai/sdk` / `openai`（无关本章，但工具 schema 由 `ToolRegistry.getAllSchemas` 喂给它们）
- MCP：`@modelcontextprotocol/sdk`（无关本章，但 ToolRegistry 同时托管 MCP 工具）
- 配置：`js-yaml`（用于解析 Agent definition frontmatter）
- 测试：`bun test`

## 架构概览

新增 `src/worktree/worktree.ts` 单文件模块，集中放：
1. 纯文件系统 git HEAD 读取工具（`resolveGitDir` / `readGitHead` / `resolveRef` / `readWorktreeHeadSha` / `getCurrentBranch`）
2. Worktree 生命周期函数（`createAgentWorktree` / `removeAgentWorktree` / `hasWorktreeChanges` / `buildWorktreeNotice`）
3. 创建后设置内部辅助函数（`performPostCreationSetup` 及四个子函数）

新增两个工具文件，把上述函数包装成 LLM 可调用的 Tool：
- `src/tools/enter-worktree.ts`：`EnterWorktreeTool` — 调 `createAgentWorktree`
- `src/tools/exit-worktree.ts`：`ExitWorktreeTool` — 调 `hasWorktreeChanges` + `removeAgentWorktree`

接入点：
- `src/tui/app.tsx` 的 `createToolRegistry` 注册两个工具
- `src/agents/tool-filter.ts` 的 `ASYNC_AGENT_ALLOWED_TOOLS` 加入两个工具名
- `src/agents/definition.ts` 的 `AgentDefinition` 已声明 `isolation?: "worktree"`，loader 已能解析（无需新增改动）

## 数据流**模型主动开 Worktree：**

```
模型 → ToolSearch({ query: "worktree" })
       ↓
ToolRegistry.searchDeferred → 返回 EnterWorktree/ExitWorktree schema
       ↓
ToolRegistry.markDiscovered("EnterWorktree")
       ↓
模型 → EnterWorktree({ slug: "feature-x" })
       ↓
EnterWorktreeTool.execute → createAgentWorktree(slug)
       ↓
git worktree add -B worktree-feature-x .gcode/worktrees/feature-x
       ↓
performPostCreationSetup:
  - copyGuolaicodeSettings   (cpSync .gcode/)
  - configureHooksPath    (git config core.hooksPath)
  - symlinkNodeModules    (symlinkSync)
  - copyWorktreeIncludeFiles (按 .worktreeinclude 列表 cpSync)
       ↓
readWorktreeHeadSha(wtDir) | fallback execSync git rev-parse HEAD
       ↓
返回 { path, branch, headCommit, gitRoot }
       ↓
工具 output 拼接 "Worktree created at: <path>\nBranch: ...\nHead: ..."
       ↓
模型在后续 Bash/Edit/Write 调用中显式把 <path> 作为绝对路径前缀
```

**模型显式退出 Worktree：**

```
模型 → ExitWorktree({ path, branch, git_root, head_commit })
       ↓
ExitWorktreeTool.execute
       ↓
hasChanges = head_commit ? hasWorktreeChanges(path, head_commit) : false
       ├─ true  → 不删，返回 "Worktree has changes, kept at: ..."
       └─ false → removeAgentWorktree(path, branch, gitRoot)
                  ↓
                  git worktree remove --force <path>
                  git branch -D <branch>
                  ↓
                  返回 "Worktree cleaned up (no changes): ..."
```

**纯文件系统 HEAD 读取链路：**

```
readWorktreeHeadSha(wtPath)
  ↓
readFileSync(<wtPath>/.git) → "gitdir: <relPath>"
  ↓
gitDir = resolve relPath against wtPath
  ↓
readGitHead(gitDir):
  ├─ "ref: refs/heads/<name>"   → { branch: name }
  ├─ "ref: <other symref>"       → { sha: resolveRef(other) }
  └─ "<40 hex SHA>"              → { sha }
  ↓
若 branch → resolveRef(gitDir, "refs/heads/" + branch)
   resolveRefInDir(gitDir) → loose ref file | packed-refs
   失败 → resolveRefInDir(commondir)  (worktree 共享 git 目录的回退)
  ↓
返回 40 / 64 字符 hex SHA 或 ""
```

## 核心数据结构与接口### Worktree 返回类型

```typescript
export interface WorktreeResult {
  path: string;        // .gcode/worktrees/<slug> 的绝对路径
  branch: string;      // worktree-<slug>
  headCommit: string;  // 40 字符 SHA-1（或 SHA-256 64 字符）
  gitRoot: string;     // 主仓 git rev-parse --show-toplevel 输出
}
```

### Worktree 模块导出函数

```typescript
// 纯文件系统读取
export function resolveGitDir(root: string): string;
export function readWorktreeHeadSha(worktreePath: string): string;
export function getCurrentBranch(repoRoot: string): string;

// 生命周期
export function createAgentWorktree(
  slug: string,
  gitRoot?: string
): WorktreeResult;

export function removeAgentWorktree(
  path: string,
  branch: string,
  gitRoot: string
): void;

export function hasWorktreeChanges(
  path: string,
  headCommit: string
): boolean;

export function buildWorktreeNotice(
  parentCwd: string,
  wtPath: string
): string;
```

### 内部 git HEAD 解析类型

```typescript
// 不导出，仅模块内使用
interface GitHead {
  branch?: string;
  sha?: string;
}

function readGitHead(gitDir: string): GitHead | null;
function resolveRef(gitDir: string, ref: string): string;
function resolveRefInDir(dir: string, ref: string): string;
function getCommonDir(gitDir: string): string;
function isSafeRefName(name: string): boolean;

const SAFE_REF_RE = /^[a-zA-Z0-9/._+@-]+$/;
const SHA_RE = /^[0-9a-f]{40}([0-9a-f]{24})?$/;
```

### 工具类签名

```typescript
export class EnterWorktreeTool implements Tool {
  name = "EnterWorktree";
  description = "Create and enter a git worktree for isolated work.";
  category = "write" as const;
  deferred = true;
  schema(): Record<string, unknown>;
  async execute(
    args: Record<string, unknown>,
    _ctx: ToolContext
  ): Promise<ToolResult>;
}

export class ExitWorktreeTool implements Tool {
  name = "ExitWorktree";
  description = "Exit and optionally clean up a git worktree.";
  category = "write" as const;
  deferred = true;
  schema(): Record<string, unknown>;
  async execute(
    args: Record<string, unknown>,
    _ctx: ToolContext
  ): Promise<ToolResult>;
}
```

### AgentDefinition 扩展（已存在）

```typescript
export interface AgentDefinition {
  // ... 既有字段 ...
  isolation?: "worktree";   // 本章不在 spawnSubAgent 内消费，保留语义占位
}
```

## 模块设计### `src/worktree/worktree.ts`（新文件）**职责：** 暴露 Worktree 全部底层能力——HEAD 读取、生命周期、变更检测、创建后设置；不做状态管理。

**对外接口：** `WorktreeResult` 类型 + `createAgentWorktree` / `removeAgentWorktree` / `hasWorktreeChanges` / `buildWorktreeNotice` / `resolveGitDir` / `readWorktreeHeadSha` / `getCurrentBranch` 七个函数。

**依赖：** 纯 Node 标准库 + `git` 可执行（通过 `execSync`）。

**关键内部函数：**
- `readGitHead(gitDir)`：解析 HEAD 文件，支持 `ref:` 与裸 SHA 两种形态
- `resolveRef(gitDir, ref)`：先查 loose ref，再查 packed-refs；worktree 自己的 gitDir 找不到时回退到 commondir
- `resolveRefInDir(dir, ref)`：单个目录内的查找（loose → packed-refs）
- `getCommonDir(gitDir)`：读 worktree gitDir 的 `commondir` 文件
- `isSafeRefName(name)`：校验合法 ref 名（防路径遍历与 shell 注入）
- `performPostCreationSetup(repoRoot, wtPath)`：依次调四个 best-effort 子步骤
  - `copyGuolaicodeSettings(repoRoot, wtPath)`
  - `configureHooksPath(repoRoot, wtPath)`
  - `symlinkNodeModules(repoRoot, wtPath)`
  - `copyWorktreeIncludeFiles(repoRoot, wtPath)`

### `src/tools/enter-worktree.ts`（新文件）**职责：** 把 `createAgentWorktree` 包装成 LLM 可调用工具，加严格 slug 校验。

**对外：** `EnterWorktreeTool` 类。

**依赖：** `../worktree/worktree.js`（`createAgentWorktree`）+ `./types.js`（`Tool` / `ToolResult` / `ToolContext` / `strArg`）。

**关键点：**
- `deferred: true` → 默认不出现在 schema 列表
- slug 校验比 `isSafeRefName` 更严格：`/^[a-zA-Z0-9_-]+$/`，不允许 `/` 与 `.`
- 失败统一返回 `{ output: "Error: ...", isError: true }`

### `src/tools/exit-worktree.ts`（新文件）**职责：** 把 `hasWorktreeChanges` 与 `removeAgentWorktree` 组合成一次工具调用，提供"有变更则保留，否则清理"的策略。

**对外：** `ExitWorktreeTool` 类。

**依赖：** `../worktree/worktree.js`（`removeAgentWorktree` + `hasWorktreeChanges`）+ `./types.js`。

**关键点：**
- `head_commit` 为可选参数；不传时跳过变更检测，直接尝试清理
- 有变更时只输出保留提示，不抛错，让模型自行决定后续合并

### `src/tui/app.tsx` 改动**职责：** 在 `createToolRegistry` 中注册两个新工具。

**改动：**
- 顶部 import：`import { EnterWorktreeTool } from "../tools/enter-worktree.js";` / `import { ExitWorktreeTool } from "../tools/exit-worktree.js";`
- `createToolRegistry` 函数体内 `registry.register(new EnterWorktreeTool());` / `registry.register(new ExitWorktreeTool());`（位置：放在 `ToolSearchTool` 之后、`ExitPlanModeTool` 之前）

### `src/agents/tool-filter.ts` 改动**职责：** 把两个工具加入异步 SubAgent 白名单，让后台 Agent 也能用。

**改动：**
- `ASYNC_AGENT_ALLOWED_TOOLS` 集合追加两条：`"EnterWorktree"` / `"ExitWorktree"`

### `src/agents/definition.ts` / `src/agents/loader.ts`**职责：** `isolation?: "worktree"` 字段已存在（来自 ch13 留出的扩展点）；loader 解析 frontmatter 时已透传，本章不再改动。

### `.gitignore`（已存在）**职责：** 保证 `.gcode/worktrees/` 与 `.gcode/worktree_session.*` 不被纳入版本库。

**改动：** 若未含 `.gcode/worktrees/` 行则追加（gcode 安装时通常已配 `.gcode/`，本章可在文档中提示用户校验）。

## 模块交互**工具发现与首次调用：**

```
TUI app.tsx (createToolRegistry)
  ↓ register
ToolRegistry { EnterWorktree, ExitWorktree, ToolSearch, ... }
  ↓
模型一开始看 getAllSchemas() → 不含 EnterWorktree（deferred）
  ↓
模型调 ToolSearch(query="worktree")
  ↓
ToolRegistry.searchDeferred → 命中两个工具
  ↓
ToolSearch 工具体内调 ToolRegistry.markDiscovered("EnterWorktree")
  ↓
下一轮 getAllSchemas() 把它们包含进去
  ↓
模型调 EnterWorktree({ slug })
```

**Worktree 创建链路：**

```
EnterWorktreeTool.execute(args, ctx)
  ↓ slug 校验
createAgentWorktree(slug)
  ↓ exec git rev-parse --show-toplevel (取 root)
  ↓ check existsSync(.gcode/worktrees/<slug>)
  ├─ 已存在 → readWorktreeHeadSha (FS 快速恢复)
  └─ 不存在 → exec git worktree add -B worktree-<slug> <wtDir>
              ↓
              performPostCreationSetup(root, wtDir)
                ↓
                copyGuolaicodeSettings        (cpSync)
                configureHooksPath         (statSync + exec git config)
                symlinkNodeModules         (symlinkSync)
                copyWorktreeIncludeFiles   (readFileSync + cpSync)
              ↓
              readWorktreeHeadSha (优先) / exec git rev-parse HEAD (回退)
  ↓
返回 WorktreeResult { path, branch, headCommit, gitRoot }
  ↓
output = "Worktree created at: <path>\nBranch: <branch>\nHead: <sha>"
```

**Worktree 退出链路：**

```
ExitWorktreeTool.execute(args, ctx)
  ↓ 校验 path/branch/git_root 三参非空
  ↓ hasChanges = head_commit ? hasWorktreeChanges(path, head_commit) : false
  ├─ hasChanges=true  → output = "Worktree has changes, kept at: <path>\nBranch: <branch>"
  └─ hasChanges=false → removeAgentWorktree(path, branch, gitRoot)
                          ↓
                          exec git worktree remove --force <path>  (try/catch)
                          exec git branch -D <branch>              (try/catch)
                        ↓
                        output = "Worktree cleaned up (no changes): <path>"
```

**异步 SubAgent 使用 Worktree：**

```
spawnSubAgent (isAsync=true)
  ↓
filterToolsForAgent(registry, ..., isAsync=true)
  ↓
ASYNC_AGENT_ALLOWED_TOOLS 含 EnterWorktree/ExitWorktree → 保留在子 Agent registry
  ↓
子 Agent 自己决定何时调 EnterWorktree
```

## 文件组织

```text
src/worktree/
└── worktree.ts                  — 新文件：纯函数模块（HEAD 读取 + 生命周期 + 创建后设置）

src/tools/
├── enter-worktree.ts            — 新文件：EnterWorktreeTool
├── exit-worktree.ts             — 新文件：ExitWorktreeTool
├── types.ts                     — 已有：Tool / ToolContext / ToolResult / strArg / intArg / boolArg
├── registry.ts                  — 已有：ToolRegistry（支持 deferred / markDiscovered）
└── tool-search.ts               — 已有：ToolSearch 工具（按 query 模糊匹配 deferred 工具）

src/tui/
└── app.tsx                      — 改动：createToolRegistry 注册两个新工具

src/agents/
├── tool-filter.ts               — 改动：ASYNC_AGENT_ALLOWED_TOOLS 追加两条
├── definition.ts                — 已有：AgentDefinition.isolation?: "worktree"
└── loader.ts                    — 已有：parseAgentDefinition 透传 isolation 字段

测试位置（按 bun test 约定）：
src/worktree/worktree.test.ts    — 新文件：worktree 模块单测
src/tools/enter-worktree.test.ts — 新文件：EnterWorktreeTool 单测
src/tools/exit-worktree.test.ts  — 新文件：ExitWorktreeTool 单测
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 暴露形态 | LLM 工具（Tool 接口） | 让模型显式决定何时开 / 关 Worktree，无需在 Agent loop 内做自动 wrap；保持模型与隔离能力的可控性 |
| `deferred: true` | 是 | Worktree 不是高频操作，默认在 schema 列表外避免污染 prompt cache；模型用 ToolSearch 按需加载 |
| Worktree 目录位置 | `<root>/.gcode/worktrees/<slug>/` | 仓库内 + `.gitignore` 排除；与其他 gcode 状态文件同级，方便用户清理 |
| Worktree 分支名 | `worktree-<slug>` | 单一前缀便于 `git branch --list "worktree-*"` 检索；slug 简单（无 `/`），不会产生 D/F 冲突 |
| slug 字符集 | `[a-zA-Z0-9_-]` | 比通用 ref 校验更严格，禁掉 `/` 与 `.` 避免任何路径解析歧义；与 LLM 习惯的 kebab-case 一致 |
| `git worktree add -B` | 大写 B | 残留同名分支不会让创建失败；小写 `-b` 在分支已存在时会报错 |
| 快速恢复路径 | 文件系统读 HEAD，子进程回退 | 大仓库 `git rev-parse HEAD` 进程启动 ~15ms；纯文件读 <1ms；失败回退保证正确性 |
| HEAD 解析做安全校验 | 是（`isSafeRefName`） | HEAD 文件可能被外部篡改；任何不安全 ref 立即返回空，绝不传给路径拼接或 shell |
| 创建后设置失败处理 | try/catch 仅 stderr 警告 | 四个子步骤都是 best-effort（hooks / 软链 / 复制），失败 ≠ 不可用 |
| `node_modules` 处理 | symlink（不复制） | `node_modules` 通常巨大，软链共享磁盘与下载缓存；Windows symlink 行为不保证时 try/catch 跳过 |
| `.worktreeinclude` 路径遍历防护 | 含 `..` 立即跳过 | 防止用户提供恶意配置导致写到 Worktree 外部 |
| 退出策略 | 有变更则保留 | 让模型自行决定后续 `git merge` / cherry-pick；gcode 不替模型做合并决策 |
| `removeAgentWorktree` 错误吞掉 | try/catch | Worktree 或分支可能已被外部清理；幂等优先 |
| `hasWorktreeChanges` 失败时返回 true | fail-closed | 宁可保留也不要误删；git 命令异常通常意味着 worktree 处于异常状态 |
| `AgentDefinition.isolation` 字段保留 | 不消费 | loader 已解析，留作未来扩展（自动 wrap 等）；本章模型显式调工具即足 |
| 同步 `execSync` vs 异步 spawn | 同步 | 工具调用本就是阻塞等待结果的语义；execSync 简单且无 await 链 |
| 测试框架 | `bun test` | 与项目其余测试一致；无需额外配置 |
| 类型检查 | `tsc --noEmit` | bun 运行不强制类型检查，CI 需显式 `tsc --noEmit` 把关 |
````

````markdown
# Worktree 隔离 Tasks

> 模块路径：`src/worktree/` + `src/tools/enter-worktree.ts` + `src/tools/exit-worktree.ts`；运行时 bun + TypeScript 5.x；测试用 `bun test`，类型检查用 `tsc --noEmit`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/worktree/worktree.ts` | 纯文件系统 git HEAD 读取 + Worktree 生命周期 + 创建后设置 |
| 新建 | `src/worktree/worktree.test.ts` | worktree 模块单测 |
| 新建 | `src/tools/enter-worktree.ts` | `EnterWorktreeTool` 包装 `createAgentWorktree` |
| 新建 | `src/tools/enter-worktree.test.ts` | EnterWorktreeTool 单测 |
| 新建 | `src/tools/exit-worktree.ts` | `ExitWorktreeTool` 包装 `hasWorktreeChanges` + `removeAgentWorktree` |
| 新建 | `src/tools/exit-worktree.test.ts` | ExitWorktreeTool 单测 |
| 修改 | `src/tui/app.tsx` | `createToolRegistry` 注册 `EnterWorktreeTool` / `ExitWorktreeTool` |
| 修改 | `src/agents/tool-filter.ts` | `ASYNC_AGENT_ALLOWED_TOOLS` 加入两个新工具 |
| 校验 | `src/agents/definition.ts` | 确认 `AgentDefinition.isolation?: "worktree"` 已存在 |
| 校验 | `src/agents/loader.ts` | 确认 `parseAgentDefinition` 已透传 `isolation` 字段 |
| 校验 | `.gitignore` | 确认含 `.gcode/worktrees/` 行，若无则追加 |

## T1: ref 安全校验与 SHA 正则**文件：** `src/worktree/worktree.ts`
**依赖：** 无
**步骤：**
1. 新建 `src/worktree/` 目录与 `worktree.ts` 文件
2. 顶部加文件级注释（"纯文件系统 git HEAD 读取，避免子进程开销"）
3. 在 import 区引入 `execSync` from `node:child_process`、`cpSync` / `existsSync` / `mkdirSync` / `readFileSync` / `statSync` / `symlinkSync` from `node:fs`、`join` / `dirname` / `isAbsolute` from `node:path`
4. 定义两个常量 `const SAFE_REF_RE = /^[a-zA-Z0-9/._+@-]+$/;` 与 `const SHA_RE = /^[0-9a-f]{40}([0-9a-f]{24})?$/;`
5. 实现 `function isSafeRefName(name: string): boolean`：非空、不以 `-` 或 `/` 开头、不含 `..`、按 `/` 切段后每段非空且不为 `.`，最后 `SAFE_REF_RE.test(name)`

**验证：** `bun test src/worktree/worktree.test.ts -t "isSafeRefName"`

## T2: HEAD 解析与 ref 解析**文件：** `src/worktree/worktree.ts`
**依赖：** T1
**步骤：**
1. 定义内部接口 `interface GitHead { branch?: string; sha?: string }`
2. 实现 `export function resolveGitDir(root: string): string`：
   - `<root>/.git` 不存在返回 `""`
   - `statSync().isDirectory()` 直接返回该路径
   - 否则读文件，校验 `gitdir:` 前缀，取剩余部分；绝对路径直接用，相对路径与 root 拼接
3. 实现 `function getCommonDir(gitDir: string): string`：读 `<gitDir>/commondir`，绝对/相对处理；抛错返回 `""`
4. 实现 `function readGitHead(gitDir: string): GitHead | null`：
   - 读 `<gitDir>/HEAD`，抛错返回 null
   - `ref:` 前缀：取剩余 ref；`refs/heads/<name>` 且 name 安全 → `{ branch: name }`；否则若 ref 整体安全 → `{ sha: resolveRef(gitDir, ref) }`（空 sha 返回 null）
   - 裸 SHA 匹配 `SHA_RE` → `{ sha: raw }`
   - 其他 → null
5. 实现 `function resolveRefInDir(dir: string, ref: string): string`：
   - 尝试读 `<dir>/<ref>` loose ref 文件；`ref:` 前缀递归调 `resolveRef`；裸 SHA 直接返回
   - 失败再读 `<dir>/packed-refs`，按行扫，跳过 `#` 注释与 `^` peel，按空格切两段匹配 ref
6. 实现 `function resolveRef(gitDir: string, ref: string): string`：先调 `resolveRefInDir(gitDir, ref)`；空则用 `getCommonDir(gitDir)` 拿共享 git 目录，再尝试一次
7. 实现 `export function readWorktreeHeadSha(worktreePath: string): string`：读 `<wtPath>/.git` 文件 → 取 `gitdir:` 后路径 → `readGitHead` → 分支用 `resolveRef("refs/heads/" + branch)`，detached 直接返 `head.sha`
8. 实现 `export function getCurrentBranch(repoRoot: string): string`：`resolveGitDir` → `readGitHead` → `head.branch ?? ""`

**验证：** `bun test src/worktree/worktree.test.ts -t "readWorktreeHeadSha"` / `"getCurrentBranch"` / `"resolveGitDir"`

## T3: Worktree 生命周期函数**文件：** `src/worktree/worktree.ts`
**依赖：** T2
**步骤：**
1. 定义 `export interface WorktreeResult { path: string; branch: string; headCommit: string; gitRoot: string; }`
2. 实现 `export function createAgentWorktree(slug: string, gitRoot?: string): WorktreeResult`：
   - `root = gitRoot ?? execSync("git rev-parse --show-toplevel", { encoding: "utf-8" }).trim()`
   - `wtDir = join(root, ".gcode", "worktrees", slug)`、`branch = "worktree-" + slug`
   - `existsSync(wtDir)`：先 `readWorktreeHeadSha(wtDir)`，非空直接返；空则 `execSync("git rev-parse HEAD", { cwd: wtDir, encoding: "utf-8" }).trim()` 回退
   - 不存在：`execSync("git worktree add -B \"<branch>\" \"<wtDir>\"", { cwd: root, encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] })`
   - 调 `performPostCreationSetup(root, wtDir)`
   - 读 head（优先 FS，回退子进程）后返回
3. 实现 `export function removeAgentWorktree(path, branch, gitRoot)`：两步 try/catch
   - `execSync("git worktree remove \"<path>\" --force", { cwd: gitRoot, stdio: ["pipe", "pipe", "pipe"] })`
   - `execSync("git branch -D \"<branch>\"", { cwd: gitRoot, stdio: ["pipe", "pipe", "pipe"] })`
4. 实现 `export function hasWorktreeChanges(path, headCommit): boolean`：
   - 外层 try：`git status --porcelain` 非空 → true
   - `currentHead = readWorktreeHeadSha(path) || execSync("git rev-parse HEAD", { cwd: path, encoding: "utf-8" }).trim()`
   - `currentHead !== headCommit` → true，否则 false
   - catch → 返回 true（保守）
5. 实现 `export function buildWorktreeNotice(parentCwd, wtPath): string`：返回三行字符串（详见 spec F6）

**验证：** `bun test src/worktree/worktree.test.ts -t "createAgentWorktree"` / `"removeAgentWorktree"` / `"hasWorktreeChanges"`

## T4: 创建后设置（四步 best-effort）**文件：** `src/worktree/worktree.ts`
**依赖：** T3
**步骤：**
1. 实现 `function performPostCreationSetup(repoRoot, wtPath): void`：顺序调四个子函数
2. 实现 `function copyGuolaicodeSettings(repoRoot, wtPath)`：try 内 `existsSync(join(repoRoot, ".gcode"))` 检查，存在则 `cpSync(src, dst, { recursive: true })`；catch 内 `console.error("Warning: failed to copy .gcode/ to worktree: <msg>")`
3. 实现 `function configureHooksPath(repoRoot, wtPath)`：候选 `[join(repoRoot, ".husky"), join(repoRoot, ".git", "hooks")]`；依序 `statSync().isDirectory()`，命中即记 `hooksPath` 跳出；命中后 `execSync("git config core.hooksPath \"<hooksPath>\"", { cwd: wtPath, stdio: ["pipe", "pipe", "pipe"] })`
4. 实现 `function symlinkNodeModules(repoRoot, wtPath)`：源 `existsSync` 且目标 `!existsSync` 才 `symlinkSync(src, dst)`
5. 实现 `function copyWorktreeIncludeFiles(repoRoot, wtPath)`：
   - `existsSync(includeFile)` 否则 return
   - 读文件、按行 split、trim、过滤空行与 `#` 注释
   - 对每行：`includes("..")` 直接 continue 跳过
   - 内层 try：源不存在 continue；`mkdirSync(dirname(dst), { recursive: true })`；按 `statSync(src).isDirectory()` 二选一调 `cpSync`
   - 外层 catch 同 copyGuolaicodeSettings 风格 stderr

**验证：** `bun test src/worktree/worktree.test.ts -t "performPostCreationSetup"`

## T5: worktree 模块单测**文件：** `src/worktree/worktree.test.ts`
**依赖：** T1-T4
**步骤：**
1. 用 `bun:test` 的 `test` / `expect` / `beforeAll` / `afterAll`
2. 构造临时目录 + `git init` + 一次 `git commit` 的 fixture
3. 覆盖：
   - `isSafeRefName`：合法（`refs/heads/main`、`feature/x.y`）、非法（`"../etc"`、`""`、`"-rf"`、`"a..b"`、`"a/./b"`）
   - `resolveGitDir`：在普通仓库返回 `<root>/.git`
   - `readGitHead`：分支与 detached 两种
   - `readWorktreeHeadSha`：在已创建的 worktree 上返回 40 字符 hex
   - `getCurrentBranch`：分支与 detached HEAD 各一次
   - `createAgentWorktree("alice")`：落地 `.gcode/worktrees/alice/` + 分支 `worktree-alice`
   - 已存在 worktree 时再调返回相同 path 走快速恢复（断言通过 mock execSync 或断言耗时 <50ms）
   - `hasWorktreeChanges`：无变更 false；改文件后 true；HEAD 已变更 true；不存在的 path 返回 true（保守）
   - `removeAgentWorktree`：删除目录与分支
   - 创建后设置：fixture 准备 `.gcode/config.yaml`、`.husky/`、`node_modules/`、`.worktreeinclude`，断言 Worktree 内对应产物

**验证：** `bun test src/worktree/worktree.test.ts`

## T6: EnterWorktreeTool**文件：** `src/tools/enter-worktree.ts`
**依赖：** T3
**步骤：**
1. import `Tool` / `ToolResult` / `ToolContext` from `./types.js` + `strArg`
2. import `createAgentWorktree` from `../worktree/worktree.js`
3. 实现 `class EnterWorktreeTool implements Tool`：
   - 字段：`name = "EnterWorktree"`、`description = "Create and enter a git worktree for isolated work."`、`category = "write" as const`、`deferred = true`
   - `schema()`：input_schema 只声明 `slug: { type: "string", description: "Short identifier for the worktree" }`，`required: ["slug"]`
   - `async execute(args, _ctx)`：
     - `slug = strArg(args, "slug")`；空 → `{ output: "Error: slug is required", isError: true }`
     - `/^[a-zA-Z0-9_-]+$/.test(slug)` 不通过 → `{ output: "Error: slug must contain only alphanumeric, hyphen, underscore", isError: true }`
     - try `createAgentWorktree(slug)` → `{ output: "Worktree created at: <path>\nBranch: <branch>\nHead: <head>", isError: false }`
     - catch → `{ output: "Error creating worktree: <msg>", isError: true }`

**验证：** `bun test src/tools/enter-worktree.test.ts`

## T7: ExitWorktreeTool**文件：** `src/tools/exit-worktree.ts`
**依赖：** T3
**步骤：**
1. import `Tool` / `ToolResult` / `ToolContext` + `strArg`
2. import `removeAgentWorktree` 与 `hasWorktreeChanges` from `../worktree/worktree.js`
3. 实现 `class ExitWorktreeTool implements Tool`：
   - 字段：`name = "ExitWorktree"`、`description = "Exit and optionally clean up a git worktree."`、`category = "write" as const`、`deferred = true`
   - `schema()`：input_schema 含 `path` / `branch` / `git_root` / `head_commit`；前三个 `required`
   - `async execute(args, _ctx)`：
     - 取 `path` / `branch` / `gitRoot` / `headCommit`
     - 三必填任一为空 → `{ output: "Error: path, branch, and git_root are required", isError: true }`
     - `hasChanges = headCommit ? hasWorktreeChanges(path, headCommit) : false`
     - `!hasChanges` 时 try `removeAgentWorktree(path, branch, gitRoot)` → `{ output: "Worktree cleaned up (no changes): <path>", isError: false }`；catch → `"Error cleaning up worktree: <msg>"` 且 `isError: true`
     - `hasChanges` 时 → `{ output: "Worktree has changes, kept at: <path>\nBranch: <branch>", isError: false }`

**验证：** `bun test src/tools/exit-worktree.test.ts`

## T8: 工具单测**文件：** `src/tools/enter-worktree.test.ts` + `src/tools/exit-worktree.test.ts`
**依赖：** T6 + T7
**步骤：**
1. `enter-worktree.test.ts`：构造临时 git 仓库；调 `tool.execute({ slug: "demo" }, ctx)` 断言 output 含 `path` / `branch` / `Head`；调 `{ slug: "../etc" }` 断言 `isError: true` 且 output 含 "alphanumeric"
2. `exit-worktree.test.ts`：
   - 先 `createAgentWorktree("test")` 拿到 result
   - 调 `tool.execute({ path, branch, git_root, head_commit: headCommit })`：无变更走清理路径，断言 output 含 "Worktree cleaned up"
   - 重新创建一个，写一个文件让其变脏，再调 `tool.execute({ ... })`：断言 output 含 "Worktree has changes, kept at"
   - 不传 `head_commit` 时也能清理（默认 hasChanges=false）

**验证：** `bun test src/tools/enter-worktree.test.ts src/tools/exit-worktree.test.ts`

## T9: 注册工具到 ToolRegistry**文件：** `src/tui/app.tsx`
**依赖：** T6 + T7
**步骤：**
1. 顶部 import 加：
   ```ts
   import { EnterWorktreeTool } from "../tools/enter-worktree.js";
   import { ExitWorktreeTool } from "../tools/exit-worktree.js";
   ```
2. `createToolRegistry` 函数体内，在 `registry.register(new ToolSearchTool(registry));` 之后、`registry.register(new ExitPlanModeTool());` 之前插入：
   ```ts
   registry.register(new EnterWorktreeTool());
   registry.register(new ExitWorktreeTool());
   ```
3. 校验 import 路径解析为 `.js` 后缀（项目 `tsconfig` 模块解析要求）

**验证：** `tsc --noEmit` 无错误；`bun run src/main.tsx` 启动不报错

## T10: 后台 SubAgent 白名单**文件：** `src/agents/tool-filter.ts`
**依赖：** T6 + T7
**步骤：**
1. 在 `ASYNC_AGENT_ALLOWED_TOOLS` Set 字面量内追加两条：
   ```ts
   "EnterWorktree",
   "ExitWorktree",
   ```
2. 校验位置：与现有 `"NotebookEdit"` / `"Skill"` 等并列

**验证：** `tsc --noEmit`；增加一个测试在 `src/agents/tool-filter.test.ts`（若已存在则补充用例）：用 `filterToolsForAgent(registry, undefined, undefined, true)`（isAsync=true）跑过后断言 `filtered.get("EnterWorktree")` 不为 undefined

## T11: 确认 AgentDefinition / loader 兼容**文件：** `src/agents/definition.ts` + `src/agents/loader.ts`
**依赖：** 无
**步骤：**
1. 校验 `AgentDefinition` 接口含 `isolation?: "worktree"` 字段（无需新增）
2. 校验 `parseAgentDefinition` 在返回对象中含 `isolation: raw.isolation as "worktree" | undefined`（无需新增）
3. 若任一缺失，按 spec F21 补全

**验证：** `tsc --noEmit`；可写一个测试：parse 一段含 `isolation: worktree` 的 frontmatter，断言结果对象 `isolation === "worktree"`

## T12: .gitignore 校验**文件：** `.gitignore`
**依赖：** 无
**步骤：**
1. 用 `grep -E "^\.gcode/worktrees/$" .gitignore` 检查
2. 不存在则在 `.gcode/` 相关段落后追加 `.gcode/worktrees/`
3. 同时确认 `.gcode/` 整体是否已被忽略（若已是 `.gcode/` 整目录忽略则无需追加子目录条目）

**验证：** `git check-ignore -v .gcode/worktrees/test/`（应命中 .gitignore 中某条规则）

## T13: 类型检查与全量测试**文件：** 无
**依赖：** T1-T12
**步骤：**
1. 跑 `tsc --noEmit`，0 错误
2. 跑 `bun test`，全部通过
3. 跑 `bun run src/main.tsx`，启动到 chat 界面无运行时错误

**验证：** 上述三条命令全部 0 退出

## T14: tmux 端到端验证**文件：** 无代码修改
**依赖：** T13
**步骤：**
1. 在干净的 git 仓库克隆下 `bun install`
2. `tmux new-session -d -s ch14 -x 200 -y 50 "bun run src/main.tsx"`
3. 等待 TUI 起来后输入 prompt 让模型用 `ToolSearch` 发现 `EnterWorktree`，调用 `EnterWorktree({ slug: "demo" })`
4. 验证 `.gcode/worktrees/demo/` 落地 + 分支 `worktree-demo` 存在
5. 让模型在 worktree 内写一个文件，再调 `ExitWorktree({ path, branch, git_root, head_commit })`：断言保留路径输出
6. 再次让模型创建无变更的 worktree，`ExitWorktree`：断言清理成功
7. 清理 tmux session

**验证：** 见 checklist.md 的端到端场景

## 执行顺序

```text
T1 (ref 校验)
  ↓
T2 (HEAD/ref 解析)
  ↓
T3 (生命周期函数)
  ↓
T4 (创建后设置)
  ↓
T5 (worktree 单测) — T6 (EnterWorktreeTool) — T7 (ExitWorktreeTool)
                       ↓                          ↓
                       T8 (工具单测)             T8
  ↓
T9 (TUI 注册) — T10 (异步白名单) — T11 (AgentDefinition 校验) — T12 (.gitignore)
  ↓
T13 (tsc + bun test + bun run)
  ↓
T14 (tmux 端到端)
```

T6/T7 可并行（同时依赖 T3）；T8 等两者完成后再跑；T9-T12 可并行（互不依赖）。
````

```markdown
# Worktree 隔离 Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。验证命令以 `bun test` / `tsc --noEmit` / `bun run src/main.tsx` 为主。

## 实现完整性### worktree 模块

- [ ] `src/worktree/worktree.ts` 存在并可通过 `tsc --noEmit` 类型检查（验证：`tsc --noEmit`）
- [ ] `SAFE_REF_RE` 与 `SHA_RE` 两个常量按 spec 定义；`SHA_RE` 同时接受 40 与 64 字符 hex（验证：`bun test src/worktree/worktree.test.ts -t "SHA_RE"`）
- [ ] `isSafeRefName("refs/heads/main")` 返回 true（验证：`bun test src/worktree/worktree.test.ts -t "isSafeRefName"`）
- [ ] `isSafeRefName("../etc")` / `"-rf"` / `""` / `"a..b"` / `"a/./b"` 都返回 false（验证：同上）
- [ ] `resolveGitDir(repoRoot)` 在普通仓库返回 `<root>/.git`（验证：`bun test ... -t "resolveGitDir"`）
- [ ] `resolveGitDir` 在 worktree 副本内识别 `.git` 文件并返回 `gitdir:` 指向的路径（验证：同上）
- [ ] `resolveGitDir` 在非 git 目录返回 `""`（验证：同上）
- [ ] `readGitHead(gitDir)` 在分支上返回 `{ branch: <name> }`；detached HEAD 返回 `{ sha: <40 hex> }`（验证：`bun test ... -t "readGitHead"`）
- [ ] `readGitHead` 在 HEAD 文件含不安全 ref 时返回 null（验证：同上）
- [ ] `resolveRef` 优先查 loose ref；fallback 查 `packed-refs`（验证：`bun test ... -t "resolveRef"`）
- [ ] `resolveRef` 在 worktree gitDir 找不到时回退到 `commondir`（验证：同上）
- [ ] `readWorktreeHeadSha(wtPath)` 在合法 worktree 路径返回 40 字符 hex SHA（验证：`bun test ... -t "readWorktreeHeadSha"`）
- [ ] `readWorktreeHeadSha` 在非 worktree 路径返回 `""`（验证：同上）
- [ ] `getCurrentBranch(repoRoot)` 在分支上返回分支名；detached HEAD 返回 `""`（验证：`bun test ... -t "getCurrentBranch"`）
- [ ] `createAgentWorktree("alice")` 在 `<root>/.gcode/worktrees/alice/` 落地 + 分支 `worktree-alice`（验证：`bun test ... -t "createAgentWorktree"`）
- [ ] `createAgentWorktree` 返回 `{ path, branch, headCommit, gitRoot }` 四字段均非空（验证：同上）
- [ ] 目录已存在时再调 `createAgentWorktree` 走快速恢复——不会重复执行 `git worktree add`，返回耗时 <50ms（验证：mock `execSync` 或断言不再触发 add）
- [ ] `removeAgentWorktree(path, branch, gitRoot)` 成功删除目录与分支（验证：`bun test ... -t "removeAgentWorktree"`）
- [ ] `removeAgentWorktree` 对已不存在的目录与分支保持幂等不抛错（验证：连续调用两次断言不抛）
- [ ] `hasWorktreeChanges(path, sha)` 在干净 worktree 且 SHA 匹配返回 false（验证：`bun test ... -t "hasWorktreeChanges"`）
- [ ] `hasWorktreeChanges` 修改一个文件后返回 true（验证：同上）
- [ ] `hasWorktreeChanges` HEAD 已变更（新 commit）后返回 true（验证：同上）
- [ ] `hasWorktreeChanges` 对不存在路径 fail-closed 返回 true（验证：同上）
- [ ] `buildWorktreeNotice(parentCwd, wtPath)` 输出三行字符串含 "git worktree at"、"parent project is at"、"isolated from the parent"（验证：`bun test ... -t "buildWorktreeNotice"`）

### 创建后设置

- [ ] `performPostCreationSetup` 在主仓 `.gcode/` 存在时把整目录 `cpSync` 到 Worktree 同位置（验证：`bun test ... -t "copyGuolaicodeSettings"`）
- [ ] 主仓 `.husky/` 存在时 Worktree 的 `git config core.hooksPath` 含其绝对路径（验证：`execSync("git config --get core.hooksPath", { cwd: wtPath })`）
- [ ] 主仓 `.husky/` 不存在但 `.git/hooks/` 存在时回退使用 `.git/hooks/`（验证：删除 `.husky` fixture 后再断言）
- [ ] 主仓 `node_modules/` 存在时 Worktree 内是软链（验证：`lstatSync(join(wtPath, "node_modules")).isSymbolicLink() === true`）
- [ ] 主仓 `.worktreeinclude` 列出的相对路径被复制到 Worktree（文件 + 目录两种）（验证：`bun test ... -t "copyWorktreeIncludeFiles"`）
- [ ] `.worktreeinclude` 含 `..` 的行被跳过（防路径遍历）（验证：同上）
- [ ] 任一子步骤抛错时 catch 仅 stderr 警告，不阻塞主流程（验证：mock 让 `cpSync` 抛错后 `createAgentWorktree` 仍成功返回）

### EnterWorktreeTool

- [ ] `EnterWorktreeTool` 字段：`name === "EnterWorktree"`、`category === "write"`、`deferred === true`（验证：`bun test src/tools/enter-worktree.test.ts -t "schema"`）
- [ ] `schema()` 含 `slug` 且 `required: ["slug"]`（验证：同上）
- [ ] `execute({ slug: "demo" }, ctx)` 成功返回 output 含 `Worktree created at:` + path + branch + Head（验证：`bun test ... -t "execute success"`）
- [ ] `execute({}, ctx)` 缺 slug 返回 `{ isError: true, output: "Error: slug is required" }`（验证：同上）
- [ ] `execute({ slug: "../etc" }, ctx)` 返回 `{ isError: true }` 且 output 含 `"alphanumeric, hyphen, underscore"`（验证：同上）
- [ ] `execute({ slug: "team/alice" }, ctx)` 同样被拒（含 `/`）（验证：同上）
- [ ] 工具默认不在 `ToolRegistry.getAllSchemas()` 返回值中（因 `deferred: true`）（验证：注册到 registry 后断言）

### ExitWorktreeTool

- [ ] `ExitWorktreeTool` 字段：`name === "ExitWorktree"`、`category === "write"`、`deferred === true`（验证：`bun test src/tools/exit-worktree.test.ts -t "schema"`）
- [ ] `schema()` `required` 含 `path` / `branch` / `git_root`；`head_commit` 为可选（验证：同上）
- [ ] 缺三个必填任一时返回 `{ isError: true, output: "Error: path, branch, and git_root are required" }`（验证：同上）
- [ ] 干净 worktree + 正确 `head_commit` 时清理成功，output 含 `"Worktree cleaned up (no changes)"`（验证：`bun test ... -t "execute cleanup"`）
- [ ] worktree 有变更时不清理，output 含 `"Worktree has changes, kept at"` 与 branch 名（验证：同上）
- [ ] 不传 `head_commit` 时 `hasChanges = false` 走清理路径（验证：同上）

### TUI 注册

- [ ] `src/tui/app.tsx` import `EnterWorktreeTool` 与 `ExitWorktreeTool`（验证：`grep -E "EnterWorktreeTool|ExitWorktreeTool" src/tui/app.tsx`）
- [ ] `createToolRegistry` 内 `registry.register(new EnterWorktreeTool())` 与 `registry.register(new ExitWorktreeTool())` 存在（验证：同上）
- [ ] 启动 TUI 后两个工具能被 `ToolSearch` 查询命中（验证：`bun run src/main.tsx` 后输入引导模型调 ToolSearch query=worktree）

### 异步 SubAgent 白名单

- [ ] `ASYNC_AGENT_ALLOWED_TOOLS` 集合含 `"EnterWorktree"` 与 `"ExitWorktree"`（验证：`grep -E "EnterWorktree|ExitWorktree" src/agents/tool-filter.ts`）
- [ ] `filterToolsForAgent(registry, undefined, undefined, true)` 返回的 registry 中 `get("EnterWorktree") !== undefined`（验证：`bun test src/agents/tool-filter.test.ts`，若文件不存在则补一个用例）

### AgentDefinition 透传

- [ ] `AgentDefinition` 接口含 `isolation?: "worktree"` 字段（验证：`grep -E "isolation\\?:" src/agents/definition.ts`）
- [ ] `parseAgentDefinition` 解析含 `isolation: worktree` frontmatter 的 md 后，结果对象 `isolation === "worktree"`（验证：`bun test src/agents/loader.test.ts -t "isolation"`，若文件不存在则补）
- [ ] 不含 `isolation` 字段的定义解析后 `isolation === undefined`（验证：同上）

### .gitignore

- [ ] `.gitignore` 含 `.gcode/worktrees/` 或 `.gcode/`（任一即可让 Worktree 副本不被纳入版本库）（验证：`git check-ignore -v .gcode/worktrees/test/`）

## 集成

- [ ] `EnterWorktreeTool` + `ExitWorktreeTool` 经 `createToolRegistry` 注册后，`ToolRegistry.searchDeferred("worktree", 5)` 同时命中两者（验证：写一个集成测试）
- [ ] `ToolSearch` 工具调 `markDiscovered` 解锁后，下一次 `getAllSchemas()` 返回值含两个 worktree 工具的 schema（验证：同上）
- [ ] 异步 SubAgent 在 `filterToolsForAgent(..., isAsync=true)` 后能拿到这两个工具（验证：`bun test src/agents/tool-filter.test.ts`）
- [ ] `EnterWorktreeTool` → `ExitWorktreeTool` 端到端：在 worktree 内写一个文件后 ExitWorktree 选择"保留"分支输出；不写文件时选择"清理"输出（验证：tmux 场景 1 + 2）
- [ ] 模块间无导入循环——`src/worktree/worktree.ts` 不引用 `src/tools/*`；`src/tools/enter-worktree.ts` 与 `src/tools/exit-worktree.ts` 只引用 `../worktree/worktree.js` 与 `./types.js`（验证：`tsc --noEmit` 通过即可）

## 编译与测试

- [ ] `tsc --noEmit` 无错误
- [ ] `bun test` 全部用例通过（含 `src/worktree/worktree.test.ts` / `src/tools/enter-worktree.test.ts` / `src/tools/exit-worktree.test.ts`）
- [ ] `bun run src/main.tsx` 启动到 chat 界面无运行时错误
- [ ] `git status` 在干净仓库下不出现 `.gcode/worktrees/` 路径（已被 .gitignore 排除）

## 端到端场景（tmux 实跑）

每个场景在 tmux 内启动一个 gcode 实例完成，验证可视化行为。

**通用预置：**
- 当前目录干净 git 仓库
- 已执行 `bun install`
- 启动命令：`tmux new-session -d -s ch14 -x 200 -y 50 "bun run src/main.tsx"`

### 场景 1：模型主动创建 Worktree 并保留有变更的副本**步骤：**
- [ ] tmux 启动 gcode；先选 provider 进入 chat
- [ ] 输入：「请用 ToolSearch 查询 worktree 相关工具，然后用 EnterWorktree 创建一个 slug 为 demo 的 Worktree，并在 worktree 内用 WriteFile 写文件 `<path>/probe.txt` 内容为 SUBAGENT，最后用 ExitWorktree 退出」
- [ ] 观察 scrollback：先出现 ToolSearch tool_use，再 EnterWorktree tool_use（output 含 `Worktree created at: .gcode/worktrees/demo`），随后 WriteFile，最后 ExitWorktree
- [ ] ExitWorktree 的 output 含 `Worktree has changes, kept at:` 与 `worktree-demo` 分支名（因为写了 probe.txt 导致 hasWorktreeChanges=true）
- [ ] tmux 外验证：`cat .gcode/worktrees/demo/probe.txt` 输出 `SUBAGENT`；主目录 `ls probe.txt` 失败（主目录未被影响）
- [ ] 清理：手动 `git worktree remove --force .gcode/worktrees/demo` + `git branch -D worktree-demo`
- [ ] `tmux kill-session -t ch14`

### 场景 2：模型创建 Worktree 后无变更，ExitWorktree 自动清理**步骤：**
- [ ] tmux 启动 gcode
- [ ] 输入：「用 ToolSearch 找 worktree，再用 EnterWorktree slug=tmp 创建一个，不做任何修改，立即用 ExitWorktree 退出（传 head_commit）」
- [ ] scrollback：ExitWorktree 的 output 含 `Worktree cleaned up (no changes): .gcode/worktrees/tmp`
- [ ] tmux 外验证：`ls .gcode/worktrees/tmp` 失败（目录已被删）；`git branch | grep worktree-tmp` 无匹配
- [ ] `tmux kill-session -t ch14`

### 场景 3：Slug 校验阻止路径遍历**步骤：**
- [ ] tmux 启动 gcode
- [ ] 输入：「用 ToolSearch 找 worktree，然后用 EnterWorktree slug 设为 `../etc` 试试」
- [ ] scrollback：EnterWorktree 的 output 含 `Error: slug must contain only alphanumeric, hyphen, underscore`，`isError: true`
- [ ] 输入：「再试 slug=team/alice」
- [ ] 同样被拒（slug 含 `/`）
- [ ] 输入：「再试 slug=feature_x-1」
- [ ] 成功创建（合法字符）
- [ ] 清理：`git worktree remove --force .gcode/worktrees/feature_x-1`、`git branch -D worktree-feature_x-1`
- [ ] `tmux kill-session -t ch14`

### 场景 4：快速恢复路径（重复 EnterWorktree 不重复 git add）**预置：** 手动先创建一个 worktree：`bun run -e "import {createAgentWorktree} from './src/worktree/worktree.ts'; console.log(createAgentWorktree('warm'))"`

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 输入：「用 ToolSearch 找 worktree，再用 EnterWorktree slug=warm（注意这个 slug 的 worktree 已经存在）」
- [ ] scrollback：EnterWorktree 在 1 秒内返回（快速恢复），output 中的 Head SHA 与磁盘上 `.gcode/worktrees/warm` 的 HEAD 一致
- [ ] tmux 外验证：通过 `git -C .gcode/worktrees/warm rev-parse HEAD` 取到 SHA 与 EnterWorktree output 中的 Head 字段相等
- [ ] 清理：`git worktree remove --force .gcode/worktrees/warm`、`git branch -D worktree-warm`
- [ ] `tmux kill-session -t ch14`

### 场景 5：创建后设置 A/B/C/D 全链路**预置：** 在主仓中准备 fixture——
- [ ] `mkdir -p .gcode && echo "ch14: ok" > .gcode/test-marker.txt`
- [ ] `mkdir -p .husky && echo "echo hook" > .husky/pre-commit && chmod +x .husky/pre-commit`
- [ ] `mkdir -p node_modules/.fixture && touch node_modules/.fixture/marker`
- [ ] `echo ".env.local" > .worktreeinclude && echo "SECRET=abc" > .env.local`（`.env.local` 通常被 .gitignore 排除）

**步骤：**
- [ ] tmux 启动 gcode
- [ ] 输入：「用 EnterWorktree slug=setup-check 创建一个 worktree」
- [ ] EnterWorktree 成功返回；tmux 外验证四件事：
  - `cat .gcode/worktrees/setup-check/.gcode/test-marker.txt` 输出 `ch14: ok`（设置 A）
  - `git -C .gcode/worktrees/setup-check config --get core.hooksPath` 含 `.husky` 路径（设置 B）
  - `lstat` 显示 `.gcode/worktrees/setup-check/node_modules` 是符号链接（设置 C，用 `readlink` 验证）
  - `cat .gcode/worktrees/setup-check/.env.local` 输出 `SECRET=abc`（设置 D）
- [ ] 清理：`git worktree remove --force .gcode/worktrees/setup-check`、`git branch -D worktree-setup-check`，删除 fixture 文件
- [ ] `tmux kill-session -t ch14`
```


# 状态、工作树、工件与 Bash：技术决定和验证索引

适用范围是当前 GCode 候选，不包含线上部署，也不是对某项真实用户业务或桌面动作的端到端验收。源码基线 `221c870f8cc0872e6704a0140f1dd9923ac66a5c`；当前为包含本轮未提交改动的工作树，测试结果对应测试时文件而非该基线原样。

## 为什么这样设计

- **SQLite WAL 和短事务**：共享任务、运行、租约、消息、工具回执及预算需要跨进程记录；WAL、`BEGIN IMMEDIATE`、版本比较和唯一键能避免整份 JSON 的竞争覆盖。旧共享任务和邮箱 JSON 只读导入，保留源文件。心跳和租约仅表示记录状态，不能证明操作系统进程或外部业务已经结束。
- **不同身份与未知结果**：运行 ID、工具调用 ID、消息 ID、工件哈希分别记录。工具发出后结果不明会保留未知并停止相关写操作；人工核对以原指纹、结果分类、证据引用与哈希、操作员说明和版本 CAS 写入审计。证据哈希是操作者提供的声明，系统不自动证明业务效果；原调用 ID 不会被重新执行。
- **消息先持久化再确认**：邮箱 `claim` 后，通知正文和 ID 先写持久通知库及会话检查点，成功后才 ACK。进程退出、超时或未知效果不触发自动重放。ACK 是持久运行时收据，不证明模型已经遵循通知。
- **Git 工作树保守保留**：公共 Git 目录 flock 协调本实现的进程，创建不使用会重置分支的 `-B`；未登记、未封存、进程存活、身份不明、忽略/未跟踪/修改内容、Git 失败或计划前提变化均不删除。自动按年龄清理关闭；显式计划必须在应用时重新核对，默认分支保留。flock 不约束不使用同一锁的其他 Git 客户端；进程清单必须由实际启动监管方登记并封存，不能证明不存在未登记的进程。
- **内容寻址工件**：对象名为原始内容 SHA-256，`put_stream` 以 64 KiB 块写私有临时对象、fsync 并以不覆盖链接原子安装；同内容去重，调用 ID 绑定不可覆盖。`retain/release` 以所有者及引用记录；`plan_gc` 仅生成无引用候选，不删除。每次读取验证哈希和大小；旧调用 ID 的 `.txt` 兼容副本与新内容冲突时拒绝，未知文件、损坏对象不自动修复或覆盖。计划只反映查询时刻，不能当作之后执行删除的授权。调用者若通过 `get()` 显式要求完整字节仍会把对象读入内存。
- **Bash 流式输出**：stdout 和 stderr 各由独立 reader 以 64 KiB 块写匿名私有 spool，内存中每流只保留最多 10,000 字节预览；大输出保存完整原始字节到工件库，最终展示最多 10,000 字符，工件详情保留流名、大小和内容哈希。退出码是进程结果，不等于业务完成；超时、读取失败或持久化失败按未知效果处理。取消清理只面向该命令创建的进程组，应用层权限不是 OS 沙箱。单次在途输出和磁盘用量未配置硬上限，磁盘不足会失败并保留未知结果。
- **父子作用域**：读取状态以运行 ID 隔离，读取采用稳定描述符快照和原始字节哈希；子工作树的父级绝对路径拒绝规则映射到对应工作树路径，继承模式、规则和危险命令检查。子任务工具对象、文件状态、文件历史、技能绑定和 Hook once 状态独立；没有可验证授权传递的终端队友拒绝启动。检查文件状态与后续写入仍是两个操作，外部并发写入存在 TOCTOU 窗口；不能宣称是原子文件锁。
- **压缩保留用户原文**：压缩时保留实际用户来源的完整段落并去重；工具结果、系统提醒和生成摘要不提升为用户授权。累计超过 30,000 字符时拒绝压缩并保留原历史，这可能阻止长会话继续，不能误报为压缩成功。
- **模型 token 预算**：不同模型调用共享持久化预算，分项计量未缓存输入、输出、缓存读写，缺失用量时停止下一次请求直至凭证核对。预检发生在请求之间，不是对已在途或并发请求的硬上限；超出量单独记录，成本没有按未知价格推算。

## 实测和证据

2026-11-06 使用隔离环境 Python 3.12.13，命令：

```sh
<WORKSPACE>/work/dev/venv/bin/python -m pytest tests/test_bash_streaming.py tests/test_artifact_store.py tests/test_interruption.py tests/test_execution_context.py -q -s --junitxml=docs/development/reliable-harness-20261105/state-bash-streaming-junit.xml
```

该次 **52/52 通过**，用例覆盖多进程工件去重、两个引用方的保留及释放、坏哈希/符号链接、Bash 两个 5,243,003 字节流的完整 SHA-256、10,000 字符展示上限、20,000 字节超时部分回执、读取/磁盘错误、重复取消以及真实 POSIX 进程组和孙进程清理。stdout 和 stderr 各一份工件，测试中渲染长度 9,984 字符。原始输出在 [state-bash-streaming.log](state-bash-streaming.log)，机器可读结果在 [state-bash-streaming-junit.xml](state-bash-streaming-junit.xml)。

单独用 `/usr/bin/time -l` 测同一大输出测试，pytest 整体进程的最大 RSS 为 **51,740,672 字节**，wall time 0.29 秒，结果在 [state-bash-rss.log](state-bash-rss.log)。这是一次包含 pytest 和运行环境开销的观测，不是 Bash 单独的内存剖析，也不能外推峰值或吞吐量。块大小和预览大小是实现的算法约束，不等同完整运行时 RSS 上限。

团队与工作树旧测试迁移后的结果和逐项原因见 [state-test-migration.md](state-test-migration.md)、[state-migrated.log](state-migrated.log)；旧冻结基线在 [evidence/baseline-bounded.log](evidence/baseline-bounded.log)，不把新旧结果混为同一版本。早期状态、预算和工作树定向记录见 [state-manifest.json](state-manifest.json)、[state-integration.md](state-integration.md)。这些测试覆盖确定性行为及临时 Git/本机进程；不是线上、跨平台、真实 provider 或真实桌面任务验收。

额外集成检查 `tests/test_context.py tests/test_session_recovery_integration.py tests/test_artifact_store.py tests/test_bash_streaming.py` 当前为 61 通过、4 失败：四项旧压缩测试使用超过 30,000 字符的用户输入，现按新规则拒绝压缩。详见 [state-integration-final.log](state-integration-final.log) 和 [state-integration-final-junit.xml](state-integration-final-junit.xml)；主集成方正在调整测试 fixture，不能把这一轮记为全绿。

## 迁移与回退

先停止使用同一状态目录的旧进程和候选进程，保留原 JSON、会话原文、工件、工作树和 Git 分支。备份 SQLite 时使用一致性备份或在关闭写入并完成 WAL 检查后同时保留数据库及关联 WAL/SHM；不要只复制正在写入的主库。新版本从旧 JSON 只读导入，不覆盖源文件。保留候选 manifest、版本及测试证据，运行中会话固定版本，不让旧新程序同时写同一库。

回退前先确认旧程序能否读取新 schema、消息和工件引用；必要时让旧程序只读打开迁移前副本，而不是覆盖当前数据。工具调用或取消效果未确认时保留未知状态和审计记录，先人工核对，不靠回退重放。工作树 owner、进程或 Git 状态不明时继续保留；清理必须经过明确计划和最新前提校验。

最终集成更新：上述61通过4失败是保留的历史记录。短用户加长助手fixture和独立超限测试已补齐；最终完整候选794项通过、源码前后不变，见 evidence/integration-delivery.xml 和 DELIVERY.json。最新摘要原文保留按相同段落最后出现顺序归并；完整事件史保存在 source_history 和会话记录中。

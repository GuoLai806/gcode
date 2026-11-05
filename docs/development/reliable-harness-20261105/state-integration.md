# 集成契约（状态与工作树）

`TaskManager(store_path: str | None = None, max_concurrent: int | None = 4, max_spawns: int = 32, max_depth: int = 2, heartbeat_interval: float = 5.0, scope_id: str | None = None)`。
不传 `store_path` 仍为内存模式，供旧调用兼容。产品入口须传持久库路径；`scope_id` 应是可恢复的父会话 ID，同一 scope 的 spawn 次数在数据库中事务累计，不传时每个 manager 随机 scope，不能跨重启延续配额。活跃容量跨共享 DB 实例统计，未知的历史运行也占额度，避免重复派发。

`launch(agent, task, name="", fork_conversation=None, idempotency_key=None, depth=0, partial_result="", conversation_fingerprint=None, budget_reserved=False) -> str`；旧参数兼容。具备稳定业务幂等键时应显式传入；key 相同且规格不同时拒绝。幂等 fork 必须提供稳定 conversation_fingerprint，否则拒绝，避免不同上下文共用结果。深度必须由上层从不可伪造的父执行上下文传入，默认 0 仅保留旧调用。AgentTool 的共享 SpawnBudget 现覆盖前台、后台、工作树及进程内队友的深度、总量和并发；没有可验证的跨进程授权时终端队友拒绝启动。TokenBudget 持久累计 uncached prompt、output、cache read/write；parent 与 child 共用同一 scope，预检只在请求之间生效，已发出或并发请求可导致 overrun。Agent 主循环、压缩和辅助模型调用已接入该 API；整体候选仍需独立集成回归。父权限不可用时拒绝启动，子工具集合不包含父级已禁用工具；对获批工作树仅重设父权限检查器的文件范围，保留模式、规则与危险命令检测。`adopt_running(...)` 传 Agent 时是新的显式继续请求，入库后才启动；传已有 asyncio.Task 时只观察原任务，不再发起另一轮调用。已有任务在入库前可能已经有外部效果，崩溃后仍须按未知处理，不会自动重放。

`get(id)` 和 `list_tasks()` 返回 `BackgroundTask`，重启后未完成运行呈现 `status="unknown"`，`stop_reason="recovery_unknown"`，`process_state="unknown"`；持久完成结果可读。`cancel(id)` 先持久记录 cancellation_requested；协程确实处理取消后才标记 cancelled，process_state 仍为 unknown，不推断 OS 进程退出。心跳只证明本 manager 更新记录，不能证明工具或子进程存活或退出。

`Mailbox.claim(agent_id, owner, ttl=60) -> list[MailboxMessage]`、`ack(agent_id, message_id, owner) -> bool`、`release(...) -> bool`。claim 是事务化的，owner 是稳定领取令牌。过期不会自动释放：如果外部效果未知，需要人工核对后明确 release；ack 只在消息已安全写入持久会话或结果后执行。`consume` 为兼容性非破坏式读取，集成方须迁移。

`WorktreeManager.reconcile() -> dict[str,str]` 只重新载入路径、分支和基线均可验证的记录；unknown 保留。创建时记录同主机/PID/出生身份/租约。`register_owner_process(name,pid)` 只能由记录中的创建进程调用，需在该进程开始操作工作树前登记（由集成方通过启动门控确保）；未知身份拒绝。`heartbeat_owner(name)` 续租；`seal_process_registry(name)` 冻结进程清单，调用前集成方必须确保此后不会再启动使用该工作树的进程。默认未封存，不能清理；旧缺失清单同样保留。只有清单封存、租约过期，创建进程及所有已登记进程均确认 PID 不存在时，`mark_inactive(name)` 才可成功；PID 复用、权限不足、跨主机或未知均保留。随后 `plan_cleanup(name) -> dict` 和 `await apply_cleanup(plan["id"])` 每次重新核验；计划只覆盖已登记进程，不证明不存在其它未登记进程。自动清理关闭；旧 `exit(..., action="remove")` 拒绝直接清理。分支始终保留。

诊断结果和边界见 state-decisions.md、state-focused.log / state-focused-junit.xml、state-stress.log。上层集成未完成之前，不应宣称所有子任务的预算、进程退出或工具执行恢复已通过验收。

`TokenBudget(store_path, scope_id, max_total_tokens=1_000_000)` 绑定不可增大的 scope 上限；`before_request() -> bool`，`record_usage(prompt_uncached, output, cache_read=0, cache_write=0) -> dict`。调用方必须提供互不重叠的真实 token 数，记录不确定或缺失 usage 时调用 `mark_usage_unknown()`，这会阻止后续请求；已取得真实回执后可使用 `resolve_unknown(evidence_id, expected_revision, ...)` 做 CAS 和幂等对账，不能重放请求。`snapshot()` 提供 observed_total、remaining、overrun，cost_usd=None 表示未计算价格。预检不是对在途请求的硬上限；崩溃与 provider 无 usage 均须在验收中保留不确定性。

根预算可通过 `--max-total-tokens` 指定（默认 1000000），桌面和 headless 入口均传入 Agent；重开相同 session 时必须提供相同上限。测试覆盖 CLI 校验、桌面参数、headless session 及程序配置和重开。

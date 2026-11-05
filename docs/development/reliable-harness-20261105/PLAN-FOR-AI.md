# GCode 执行与验收

目标和范围：可靠编程 Harness + 可选本机 CU；不复制私有 pi 实现，不修改已安装 pi，不宣称跨平台全覆盖或全任务成功率。用户说明见 [PLAN-FOR-YOU.md](PLAN-FOR-YOU.md)。

源码：gcode/agent.py、runtime/、context/、permissions/、agents/、teams/、worktree/、tools/、cu/、sidecar/；基线 221c870f8cc0872e6704a0140f1dd9923ac66a5c。依赖由 pyproject.toml 声明，版本快照记录实际平台，不是带哈希跨平台锁。

接口：工具经 Tool.invoke(params, ToolExecutionContext) 执行；Agent.run_to_completion 消费统一循环。持久 RunStore、ToolLedger、TokenBudget、NotificationStore 使用稳定 scope；CU 经 NDJSON stdio，写操作需 action_id 和原桥权限。新的状态类型和字段通过 session、team transcript 与 SDK serializer 保留。

任务顺序：停止旧写入并备份→安装候选→运行静态和全量 tests→核对状态迁移与恢复→按需只读 CU hello/observe→依授权执行有明确后置条件的动作。无须服务器发布；容器、PyPI 和已安装 pi 不在本次部署范围。主机原生权限由用户现有授权管理。

验收：最终 JUnit、代码 manifest、wheel SHA 指向候选；独立评审复现已复测；真实模型与 GUI 证据不能被 synthetic 代替。原模型读取失败记录保留；同源使用量修复后真实读取完成，CU 只读模型调用成功。大型输出两流各5,243,003B哈希一致、展示限额和取消进程组回归通过。工件GC仅dry-run。

失败恢复：未知效果禁止重放，恢复 CLI 只作审计核对；不删除 ledger、不换机器状态绕 fence。工作树只有进程登记封存、退出身份可证、内容干净且计划CAS重新校验后才可清理。回退保留新库/WAL/工件，使用旧版本兼容副本。不可验证项包括未登记进程、在途预算、TOCTOU、完整模型驱动多应用CU A/B及生产安全隔离。

授权：已允许开发与推代码；仅公开独立代码和脱敏证据；真实账户密钥、本机桥源码、二进制、原生schema及用户界面原文不进入仓库。无待用户决定的常规实现选择，后续实际生产部署与更多GUI业务任务另按具体范围执行。

最终本地验收：794 passed、0 failed，35.82s；源码snapshot和JUnit一致。干净wheel环境CLI通过，参见DELIVERY.json。远程CI与生产部署不由这些本地结果证明。

平台范围：本轮实际验证是macOS Apple Silicon。加固实现使用POSIX文件锁/进程组，Linux需独立验收，Windows需平台适配；不沿用旧README的跨平台支持描述作为本轮证据。

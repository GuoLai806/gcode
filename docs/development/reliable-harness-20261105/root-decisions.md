# 执行内核与集成选择

范围：基线 221c870f8cc0872e6704a0140f1dd9923ac66a5c 上的本轮候选。状态、工作树与工件的更多权衡见 [state-final-engineering.md](state-final-engineering.md)，CU 见 [cu-decisions.md](cu-decisions.md)。

|选择|备选与取舍|验证依据和限度|
|---|---|---|
|任务局部 ToolExecutionContext|替代 os.chdir 或共享对象 cwd；避免并发子任务改变父目录|test_execution_context.py、test_scope_cache.py；不提供 OS 进程沙箱|
|前台和子任务同一 Agent.run|替代复制简化循环，保证权限、预算、journal 和停止状态都经过同一入口|test_agent.py、test_spawn_integration.py、test_interruption.py；真实模型文件读取及只读原生 CU 各一项|
|派发前写 ledger，未知结果停止写入|替代崩溃后自动重试；接受人工核对成本以防重复外部操作|test_tool_recovery.py、test_session_recovery_integration.py；不能提供 exactly-once OS 效果|
|恢复时合并 checkpoint/持久通知/未知 fence|替代仅按 JSONL mtime 选历史；确认前先落盘|test_session_recovery_integration.py 与独立 review 的较新 JSONL/ACK 复现|
|九部分摘要格式+完整原始历史留存|替代把无标签、截断或拒绝当摘要；通过不代表摘要语义无损|test_checkpoint_integrity.py；fsync 失败保留旧历史，source_history 私有文件可核对|
|完整用户段落，按最后重复出现顺序保留|替代中英关键词猜约束，防“请勿”漏检和 A→B→A 撤回被去重|test_constraint_ledger.py；30,000 字符上限会阻止长会话压缩，非完整事件时间线|
|稳定的工具结果投影|替代每次请求重新截断旧结果；完整结果有哈希工件和引用|test_context.py、test_artifact_store.py；没有声称降低多少缓存费用|
|SDK 禁止隐式重试|替代 SDK 默认重试以免实际调用未入预算；网络失败交由上层显式处理|test_provider_finish_integrity.py；timeout 60s，不假设 provider 未处理请求|
|usage 在任意流 packet 读取|兼容 same-choice finish 与独立 usage trailer；缺失真实 usage 进入 unknown|test_provider_finish_integrity.py；第一次真实文件任务失败后保存修复前证据，第二次完成，未把未知费用记为零|
|显式 deny 优先、极小 exact command 自动集合|替代 awk/find/sed/xargs/npx 等危险前缀自动放行；带参数的命令可用显式规则授权|test_permissions.py、test_spawn_integration.py 与真实临时文件复现；不是 shell 语义安全证明|
|Plan 模式只允许准确计划路径写入|替代文件名子串等宽泛例外；显式 deny 仍优先|test_permissions.py、test_context_window.py；/do 由用户命令显式切换|
|CU 作用域与未知投递继承原桥约束|替代只包一层工具名字；验证 schema、身份、manifest，读写与业务完成分开|test_cu_transport.py、test_cu_bootstrap.py、test_desktop_tools.py；原桥 context hooks 未全部等价移植|
|CU 有界退出并清理自己的 POSIX 进程组|替代 SIGTERM 后无界 wait 和遗留 native helper；异常也执行清理|test_cu_transport.py 合成忽略信号父子进程；不终止由系统另行管理的已打开应用，未知动作不会因此变已完成|
|未知情况下的人工对账 CLI|替代删除状态目录或重放操作；持久化指纹、CAS 和证据引用|test_tool_recovery.py；操作员提供证据不构成防篡改认证|

## 测试迁移理由

冻结原基线在当前 Python/SDK 下的有界执行为 35 failed、516 passed、19 errors，保留原日志和 JUnit；原无界等待运行经确认 PID 后停止，不能当作通过。旧测试对 `GCode` 大写模块打补丁，但包实际为 `gcode`；部分对象是无限属性 MagicMock，掩盖权限接口；固定 /tmp 文件跨测试复用、Git 测试缺少真实仓库、异步 Hook 未收尾，都会导致无效失败或挂起。迁移分别改为实际模块、显式 SimpleNamespace/真实临时对象、tmp_path、git init 和 await aclose。旧基线未修改。

纯 user 消息可能合法合并，断言改为内容与顺序而非假设消息数量；压缩后不再插入假 assistant 回答。写前读取测试现在确实通过具有运行作用域的 ReadFile.invoke。新用户原文上限导致旧超长用户 fixture 被拒绝，调整为短用户加长助手历史，同时独立测试超限保留，不删除边界覆盖。合成 provider 的零 usage 只有在测试明确知道实际调用为零时才用审计凭证对账，不把真实未知费用默认为零。

## 复现

安装项目和开发工具后：

```sh
python -m pytest tests -q --timeout=12 --junitxml=report.xml
ruff check gcode tests --select E9,F63,F7,F82
python -m build --wheel
```

最终全量结果以 evidence/integration-delivery.xml 和对应源码 manifest 为准；早期 integration-final.xml 是加上最后摘要完整历史改动之前的 792 项结果，不能混成同一次运行。全部证据中的 fake provider、真实进程/Git、真实模型、真实 GUI 各有范围说明。

最终真实压缩验证补充：最初两次真实模型输出被严格保护拒绝，第二次原生输出实际包含合法外层标签，但在引用控制提示时含有字面标签，旧解析器误计为多块。改为外层完整匹配并拒绝独立第二块，同时移除用户历史中重复注入的控制系统提示。第三次真实调用成功；检查点原始14条消息完整，约束、ALPHA=42和beta.py标记独立回读存在。最初检查脚本只看history[0]（环境消息）造成标记假阴性，保留原诊断并附独立审计纠正。它们都是单次合成历史试验，不是语义保持率。最终全量794项通过，源码测试前后相同；wheel在全新虚拟环境安装并验证CLI和六个sidecar文件。

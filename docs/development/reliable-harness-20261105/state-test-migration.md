# 旧团队和工作树测试迁移记录

冻结基线保存在 `evidence/baseline-bounded.log` 和 `.xml`，未改动。迁移前 `tests/test_teams.py` 和 `tests/test_worktree.py` 的测试日志保存在 `state-existing.log` / `state-existing-junit.xml`；27 个失败或错误 ID 均存在于冻结基线。迁移后在当前候选重新运行，结果见 `state-migrated.log` / `state-migrated-junit.xml`。

- 团队名和 transcript 的三个 mock 路径从不存在的大写 `GCode.teams` 改成实际 Python 包 `gcode.teams`。原有目录选择、保存、读取和不存在返回的断言保留。
- 邮箱 `test_write_and_consume` 原断言读取后立即删除，改为读取后仍保留、领取后显式 ACK 才消失；`test_cleanup` 改为未确认消息在清理请求后仍可恢复。消息内容、发件人以及 ACK 的结果都实际核对，补充领取冲突和持久化失败测试见 `test_durable_teams.py`。
- 后端检测：`detect_backend` 当前始终选择进程内；原 tmux、iTerm2、tmux 安装和不可用四种环境分别同时核对默认选择与 `detect_pane_backend` 的探测结果。新增非交互／显式进程内优先测试；实际 pane 启动仍因授权无法安全传递而拒绝，另由 `test_spawn_integration.py` 验证，探测不代表启动。
- 普通提示词改核对公开的 `IDENTITY_SECTION.content`；协调模式单独核对公开的 `build_plan_mode_reminder` 确有计划提示，协调系统提示不夹带该提示及普通项目指令，而普通系统提示包含项目指令。旧 `plan_mode` 构造参数和两个旧常量不再存在，故不能继续调用。
- Git fixture 删除不存在的 `file_cache` 构造参数，在仓库外使用独立工作树目录，并为每个同步测试显式创建／关闭事件循环；初始化 Git 每步检查退出码。独立 FileCache 的读写、失效、清空测试仍保留。
- `test_fast_recovery` 改为通过持久 manifest 的 `reconcile` 验证路径和原始基线恢复，并额外确认再次创建同名工作树遭拒；不能用重建分支冒充恢复。
- 原“进入即清空 manager.file_cache”没有现行接口，改验证进入时进程全局 cwd 不变、session 指向工作树；FileCache 基础行为依旧单独测试。
- 原清洁目录的直接强制删除改为验证拒绝、目录和会话仍保留；原按清洁状态自动删除改为验证目录被保留。新增真实 Git、独立进程封存所有者的清理计划测试：计划后出现新文件时 CAS 拒绝并保留，再移除该测试文件后按同一计划应用，分支仍存在。已修改目录直接删除仍独立测试拒绝；额外 PID、忽略文件、Git 非零、未封存和进程仍活跃等保护保留在 `test_worktree_safety.py`。
- CLI 预算参数用正整数解析，非法值退出；CLI 单测验证传入桌面应用，headless 集成测试核对实际 Agent 的持久 session scope 和自定义额度。默认值一百万是请求前的观察额度，不声称限制在途请求。

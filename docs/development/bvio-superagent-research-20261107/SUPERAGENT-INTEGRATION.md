# DeepSeek SuperAgent 与 GCode 的结合判断

本轮主目标是用户已确认的 **SuperAgent**。依据官方研究原型 `deepseek-ai/dsh-superagent-prototype@8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；参考 GCode `e480127bc1590efadf505aca4a71f86ed95f6742`。固定代码位置与 SHA256 见[SUPERAGENT-SOURCE-INDEX.md](SUPERAGENT-SOURCE-INDEX.md)、[SuperAgent 来源摘要](evidence/superagent-source-manifest.json)、[GCode 来源摘要](evidence/gcode-source-manifest.json)。本文是研究结论，实际实施以主任务两版权威方案为准；推荐目录统一为 `gcode/orchestrator/`。

## 建议

保留 GCode 的执行内核，参考 SuperAgent 增加持久任务控制层：来源与授权分开、消息去重、长期任务身份、结构化状态、后续补充归属、持久副作用队列、恢复和人工优先调度。先接本地显式用户任务，再根据授权考虑外部来源。当前没有数据支持整体替换内核。

本轮只读源码与文档，未安装、运行、调用模型或修改业务库。没有 SuperAgent 与 GCode 的真实效果、时延、吞吐、资源或成本 benchmark，不认定任何一方性能更好。

## 官方身份与文章边界

原型固定提交日期 2026-10-31，package 0.1.0，MIT。README 明确说明是研究参考、不是正式 DeepSeek 产品，公开版与内部实现及文章《Exploring Super-agent Design》不完全相同，文章某些设计未实现。[S01](SUPERAGENT-SOURCE-INDEX.md#s01)

实际核心是 Source → Trigger/Thread → Eval（deterministic gate + model assessment）→ Decision/Mandate → Ticket → Assignment → DSH worker Session。已读 core/model/ports/engine/executor 和架构文档以这套领域为准，没有可证明已经实现 Council/Tape/独立 Planner 的接口。43 份已取文本中对这些词的有界搜索为零，只作为辅助证据，不外推成全仓库审计。[S03](SUPERAGENT-SOURCE-INDEX.md#s03)[S04](SUPERAGENT-SOURCE-INDEX.md#s04)[S05](SUPERAGENT-SOURCE-INDEX.md#s05)

`src/core/memory.ts` 是测试用 MemoryRepositories。长期任务记录存 SQLite，模型会话/压缩沿用 DSH；不能把 memory 文件名当长期语义记忆能力，也不能声称已复现内部 SuperAgent。[S19](SUPERAGENT-SOURCE-INDEX.md#s19)

## 代码中值得复用的设计

| 行为 | 实际实现 | 对 GCode 的价值 |
| --- | --- | --- |
| 决定与执行分开 | Engine 是领域唯一事务修改入口，Executor/Assessor/Outbox 都通过 ports 排队与回调 | 避免同一任务状态由多个 Agent 随意改写 |
| 任务与一次运行分开 | Ticket 持有 Mandate 和多轮 Assignment，Session idle 与 Ticket ended 分开 | 支持等待审查、补充、重试、恢复，而非一次调用完成就丢身份 |
| 来源与授权分开 | Trigger 正文/引用不授权，Policy gate/revalidate，Mandate 不可变 | 外部信息可以补上下文，不扩大可执行范围 |
| 去重与归属 | Trigger 存一次，Thread 内一个 Eval，Subscriptions 将 follow-up 回原 Ticket | 减少重复开活，保留原讨论上下文 |
| 提交后副作用 | SQLite WAL+FULL，Effects kind/key 去重、generation防旧尝试覆盖新payload | 状态提交与待动作不丢，重启后有可查恢复入口 |
| 背景工作与人工调度 | WorkerSlots await前占槽，background仍运行不释放；人类wake可额外1槽并优先 | 用户补充不会一直排在新任务之后，slot不只看模型turn |
| 失败与恢复 | blocked/failed不接自动输入；中断Assignment带恢复记录，未读输入重投前去重 | 用状态和证据恢复，避免任意CI又拉起失败任务 |

端口定义在 `src/core/ports.ts`：Repositories.atomic、Policy.gate/revalidate/admitsInferred、Assessor.request/release、Executor.start/deliver/stop、Outbox.send/status/withdraw。Core 不负责具体模型、目录、连接器和命令，官方 domain 文档也将这些归为部署相关。[S05](SUPERAGENT-SOURCE-INDEX.md#s05)[S17](SUPERAGENT-SOURCE-INDEX.md#s17)

## 必须保留 GCode 的执行约束

1. **原型不是更严格的默认执行环境。** Sessions.ensure 明确设置 danger-full-access；worker以 operator OS 用户免审批执行。账号 shim、独立Git配置、目录与环境变量解决默认路由，文档明示并非安全边界。[S12](SUPERAGENT-SOURCE-INDEX.md#s12)[S18](SUPERAGENT-SOURCE-INDEX.md#s18)
2. **自动合并是提示词要求。** host 没有 merge-specific decision gate，默认指令条件不能替代当前项目授权或 GitHub 分支保护。[S13](SUPERAGENT-SOURCE-INDEX.md#s13)
3. **队列不等于外部恰好执行一次。** Outbox 的 sources.send 成功后才 settle 本地receipt；两者之间中断，需连接器幂等/外部核对。GCode ToolLedger 和 unknown 写停止不能被普通网络重试取代。[S10](SUPERAGENT-SOURCE-INDEX.md#s10)
4. **所有执行入口要一致。** GCode普通 AgentTool已继承权限上限、shared token/spawn预算、clone/rebind工具和hooks；SkillExecutor fork另建Agent(checker=None)且未复用这些配置。新控制层只能走统一受约束Executor，不能走较弱的技能fork。[E12](SUPERAGENT-SOURCE-INDEX.md#e12)[E13](SUPERAGENT-SOURCE-INDEX.md#e13)[E15](SUPERAGENT-SOURCE-INDEX.md#e15)
5. **工作树由 GCode 管。** WorktreeManager已支持owner、锁、reconcile和reviewed cleanup，dirty/unknown保留；原型prepare使用部署shell，已有目录即视为准备。应以明确prepare回执和基线验收代替“目录存在”。[E17](SUPERAGENT-SOURCE-INDEX.md#e17)[S16](SUPERAGENT-SOURCE-INDEX.md#s16)

GCode已有多 Agent、Team、压缩、工具回执和工作树，本次问题是长期管理与入口一致性，不写成 GCode 完全缺少这些能力。路径/进程分开不是操作系统隔离。

## 三条结合路线

**A，推荐：原生任务控制层 + GCode Executor。** 根据公开 domain 和 ports 实现独立 Python 控制层，复用现有 Agent/Team/CU/权限/预算/worktree/receipt。首版本地显式用户任务，无外部监听/发消息/主动接单/auto merge。任务状态与执行证据互相引用，ready与evidence_verified/awaiting_review分开。相对减少第二套会话和配置的整合成本，但可靠性与成本改善仍未测。

**B，备选：TS core/DSH 独立进程桥接。** 保留原型 Engine，通过 GCodeExecutor 替换 DshExecutor，或 DSH 作为另一 worker backend。必须重建 composition 并解决 start/deliver/stop、回调身份、取消与settlement、权限等价、总预算、双边日志及未知结果。原Runtime/Session/Assessor/UI依赖Cordis/DSH，不能安装一个bundle就自动换成GCode。官方同步SDK可作为后端接入面，但不是完整adapter。

**C，暂不推荐：整体迁移。** 把工具、CU、会话、恢复、权限、worktree和UI迁到DSH/SuperAgent，成本最高。原型还基于alpha依赖，缺少项目真实收益证据，公开版也没有生产成熟承诺。未来若B证明有必须依赖的能力和足够收益，再单独立迁移规格。

## 依赖、验收和收益证据

原型 package 声明 Node ^22.19.0 或 >=24、pnpm11.7.0、DSH ^0.2.1-alpha.2，多项 devDependency固定alpha.2，Cordis/schemastery亦alpha；当前DSH master的fcc0ad4不能自动视作已兼容。未验证npm渠道、安装包、构建和实际运行。[S02](SUPERAGENT-SOURCE-INDEX.md#s02)

下一阶段顺序：统一GCode child执行入口 → 控制层model/store/idempotence → local用户来源与授权 → effects/receipts/recovery → executor/scheduler → 用户状态与后续补充 → 真实安装入口验收 → 数据归档。先完成授权普通开发，再按主方案的终点收尾，不在本轮启动。

独立Agent验收建议固定10个工程场景（RAG评测规模是另一条决策）：去重、follow-up归属、信息不扩权、满并发人工插话、预算耗尽、压缩继续、重启恢复、已成功写的本地确认窗口、叫停、failed不被bot拉起且最终证据交付。组件fake只证明状态；正式验收经过实际GCode用户路径。保存版本、任务/配置、backend、完整事件与receipt、失败、输入延迟、恢复率、重复执行和全树tokens成本。10场景工程通过率不是答案质量或SOTA指标。

原型 Vitest 源码有 MemoryRepositories、fake executor/assessor、fake session/CLI 并发用例；本轮未跑，不引用测试数量作任务效果证明。[S14](SUPERAGENT-SOURCE-INDEX.md#s14)

## 名称附录

Superpowers 是 obra 的开发技能/方法，不是 DeepSeek SuperAgent。原版7.0.2与3个社区DSH移植的初步资料仅作为名字区别保留，本轮不再按其技能接入路线实施；原始初步调研留在本机。用户已经明确主目标，无需再询问 fork。

执行以[用户版](PLAN-FOR-YOU.md)和[AI版](PLAN-FOR-AI.md)为权威。本文及来源只包含可公开材料，远端同步由主任务核实。

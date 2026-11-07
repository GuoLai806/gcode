# bvio OpenViking 与 DeepSeek SuperAgent：只读调研和后续执行依据

[用户版](PLAN-FOR-YOU.md)与本文同一组决定。详细事实见[RAG 对照](RAG-COMPARISON.md)、[SuperAgent 分析](SUPERAGENT-INTEGRATION.md)、[测试协议](BENCHMARK-PROTOCOL.md)、[来源索引](SOURCES.md)。主任务维护一组权威文档，GCode 与 RAG 的仓库文档是同步镜像，不得分别演化成冲突规格。

## 1. 明确需求、交付终点及授权

| ID | 用户要求 | 本轮实现/验收 | 状态与证据 |
| --- | --- | --- | --- |
| R1 | 参考 bvio 实际 OpenViking，与我们的实现比较 | 固定相关快照与个人版本，核对 adapter 和 engine 的实际链 | RAG-COMPARISON、源身份、48文件摘要 |
| R2 | 判断性能；若企业确实更好，测试后再改方案 | 分拆排序、预算、等待、资源、更新；执行隔离纯函数实验，拒绝不公平胜负 | 14场景原始结果；整体胜负未知，替换条件未成立 |
| R3 | 调查 DeepSeek Agent 框架并给结合方案 | 用户两次澄清为 superagent，固定官方 dsh-superagent-prototype | SUPERAGENT-INTEGRATION、公开源码链接与hash |
| R4 | 本轮使用需求技能，只读检查，调研文档之后再开发 | 只读源码、抓取参考、合成组件实验、文档与审阅 | 不改业务代码/配置/索引，不安装运行框架 |
| R5 | 文档详细、易懂且可直接用于开发 | 用户版、AI版、模块/接口/顺序、验收/回退齐备 | 本文与关联报告；下一轮仍需明确进入实施 |
| R6 | 技术选型有理由/数据，记录真实后端和失败 | 历史证据与本轮观察分层，未知收益明确标注 | SOURCES、BENCHMARK-PROTOCOL、原始JSON |
| R7 | 保持公开；只推可公开独立实现和资料 | 公开独立分析与脱敏证据，企业源码/私有脚本留本机 | 文档双版同提交，README入口，远端核对 |

沿用通用 RAG、实际 OpenViking、开发6/正式30、失败进入分母、不可捏造成绩的决定。此前普通开发/推送授权仍有效，但本轮最新指令把开发暂停在调研边界；不因本规格“可执行”就启动实施。普通相关文档同步可直接做，不合并PR、不force、不发布、不改仓库可见性、不发外部消息、不修改简历Word/Pi/企业服务。

## 2. 输入版本和证据等级

- 企业参考：BvioTech/violoop-mem-ov，固定8420a1bd38d8f197aef3b8dafd39de07bc4a363b；48个相关文件的选择性快照，捆绑engine声明0.4.24.dev70、Node24。不是完整安装包、当前部署或可执行企业模型快照。
- 个人RAG：GuoLai806/GuoLai806-law-ai-advisor，dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0；被测实现561ec65292218541b380ff3963d21fb6115e6778，分支feat/versioned-legal-rag-20261105。实际OV0.5.3、SciFact5183篇、BGE-M3、Qwen3-Reranker-4B及30题用户路径已有历史记录，本轮不重跑。
- GCode：GuoLai806/gcode，e480127bc1590efadf505aca4a71f86ed95f6742，分支feat/reliable-harness-cu-20261105。主/普通子任务已有权限上限、共享预算、应用层执行目录、工具回执、恢复和工作树；技能fork为另一未统一路径。
- 主参考：deepseek-ai/dsh-superagent-prototype，8c32a9dc5d72c033816c6a8110b37f40cf94fba4，package0.1.0，MIT。DSH/Cordis bundle、研究原型；不等同官方产品/内部版/文章全部设计。
- 宿主参考：deepseek-ai/deepseek-harness固定fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159。Superpowers原版与社区移植仅为名称纠正附录，不是本次实施来源。
- MyAgent仅参考已存历史快照中的记忆/Curator机制，未刷新完整版本/实际服务，不能宣称它完成本轮集成或验收。

证据分别标为源码事实、本轮组件观察、历史真实系统数据、部署未知、建议/预期。不用版本号、功能数、测试数、源码类名或文章设计推断性能胜负。

## 3. 同一组方案决定

D1：本轮只读研究与文档；业务安装/构建/真实企业A/B/外部自动运行未执行。

D2：保留RAG的真实OpenViking find + BM25 + RRF + Qwen与版本正文。企业当前adapter是预览记忆工具，engine的context assembler未被它调用；14个实验不支持整体替换。先评估共享HTTP客户端，再做可选探索入口，正式回答保持完整证据。类型/时间/来源、后台生命周期之后分开引入；默认不做跨轮证据去重、查询改写/摘要重写。

D3：建议把SuperAgent的持久任务控制层独立实现到GCode，保留现有执行内核；不把DSH bundle当普通Skill安装，不同时运行两个重叠控制器。第一阶段仅本机明确请求；GitHub只读Source、Channel外部写入、主动规则、Feishu后续分别授权和验收。默认不开自动评论/合并/推断接单。

D4：任何新控制层接入前，先统一SkillExecutor fork、LoadSkill与普通AgentTool入口的执行契约；修父权限/工具能力/共享预算/原始上下文传递。工作树是目录隔离，应用权限不是OS沙箱；保留CU仅父任务可获写授权、结果不明操作不得重放的边界。

D5：每项候选先确定实际可测范围，参数冻结后比较。RAG完整主对照两变体各30，开发6；额外机制测试独立计数。所有失败/停止/未知usage与负面结果保留。小样本只能作迭代依据，不能证明稳定前沿。

## 4. RAG 后续任务与接口（均未实施）

### C1 HTTP生命周期，优先低风险单因素

涉及evidence_rag/retrieval.py的OpenViking及API/benchmark服务lifespan。构造器增加可注入AsyncClient和明确owns_client标志；由服务创建共享client，不由每次find关闭共享client。保留trust_env=False、重定向策略、请求deadline、鉴权和scope/revision/profile/serialization/validated校验。客户端与固定服务配置绑定，不用共享可变headers在租户间切换。

提供aclose与服务退出排空；拒绝关闭后新请求，取消请求不关闭其他使用者的连接。benchmark和安装服务走同一生产实现，不能仅优化探针副本。现有外部提供client的单测/transport接口向后兼容。T1测实际find的连接/等待与结果一致性，不能拿MockTransport时间当网络收益；若只减少HTTP阶段，不声称完整回答变快。

### C2 探索与证据分开，不默认改变正式回答

新增可选/api/v2/explore入口与ExploreBundle，保留/api/v2/retrieve、/api/v2/chat/stream既有契约。预览条目字段：unit_id、document_id、revision、content_sha256、locator、preview、preview_truncated、has_more、read_pointer；明确preview不是完整证据。深读返回同revision的完整段落/正文与hash，禁止静默跨版本。

正式生成只能接EvidenceBundle，不能将ExploreBundle转换成“ready”直接生成。完整候选正文参与重排和回答预算；超额段落omit并记录，禁止把任意字符截断当完整证据。T2在相同检索、重排和生成配置下仅比较获取/展示策略，两组使用已验可选grounded_json + grounded_evidence，不改变产品text默认值；本地权重固定、云alias权重不可锁定，实际身份由新manifest记录。SciFact短摘要未必受益，长文6场景只证明机制，另做公开长文正式数据后才能泛化。

### C3/C4 过滤和后台生命周期

可选来源/类型/时间过滤必须在关键词和语义两路同等生效，过滤版本进入trace，缺字段语义明确。只在memory场景另做turn ledger，不从RAG正式证据删除“之前读过”的相关文献。入库accepted、正文对账、向量可见、activated分别记录；未知提交不重试，排空/取消/embedding/rerank队列可观测，退出不杀无关服务。沿用现有delivery_unknown与Semaphore1保护；收益未测，不承诺吞吐改善。

## 5. GCode 后续任务与接口（均未实施）

### G0 统一执行入口，前置依赖

修改候选文件：gcode/skills/executor.py、gcode/tools/load_skill.py、gcode/tools/agent_tool.py、gcode/agent.py、必要的skills/parser.py与commands/handlers/skill_register.py。复用或抽出普通AgentTool的child factory；不要再单独permission_checker=None新建执行器。

所有child构造绑定：parent_run/ticket/assignment身份、父checker与permission_ceilings、受限且独立的registry、共享TokenBudget/SpawnBudget的scope、父hook/instructions/有效约束、任务局部ExecutionContext、原始历史引用、CU能力上限和回执owner。保留权限上限的实际检查，不只把规则拼进prompt。max_total_tokens数值相同不等于共享额度。

LoadSkill与slash入口必须遵守同一mode/allowed-tools契约；拒绝未知/不支持的模式，不能读不到就静默inline。full禁止逐条200字截断和把assistant段落伪装成user授权；recent/none保留其显式语义。结构化transfer manifest存artifacts，原消息角色/出处/约束可回读。动态Python工具导入属于可执行扩展，不因LoadSkill被标read就默认获得新能力，未知扩展在能力校验前不运行其代码。

### G1 控制层：长期Ticket与多次Run分离

建议新模块gcode/orchestrator/{models,store,engine,policy,executor,effects,source,resources}.py；TUI/CLI只读其views并提交Engine命令，不直接写表。使用Python现有SQLite，新增独立orchestrator DB保存领域状态和effects，单一写者/进程锁；原RunStore/TokenBudget/ToolLedger继续保存执行记录，通过稳定ID关联。不承诺两个数据库之间有一个原子事务；跨库启动先记assignment/effect，再按idempotency_key对账已有run。

领域：Source/Trigger/Thread是事件与上下文；Policy/Mandate是版本规则和授权范围；Ticket是用户可持续需求；Assignment绑定一次Executor运行。Ticket的业务完成和Run进程终止分开。至少保存source_cursor、trigger唯一键/原始hash、policy_version、decision、mandate、ticket、assignment、inputs送达/纳入历史状态、attention、effects/receipts。raw上下文和执行约束不能仅存短卡片。

最小接口（建议契约，不宣称现有）：
- Source.poll(cursor)返回immutable Trigger及new_cursor；只有事务存好trigger与cursor才推进。
- Policy.gate(trigger,thread,tickets)返回deny/explicit；第一版无inferred accept。followup是上下文，不授予更宽权限。
- Engine.receive/decide/append_input/report/request_stop/reconcile；命令带expected_revision，拒绝陈旧派工/报告，assignment_id必须匹配当前执行代次。
- Executor.start(ticket,assignment)、deliver(assignment,input_ids)、stop(assignment)、inspect(assignment)；只排队，返回统一事件，实际复用GCode执行链。
- Report包含progress/waiting/ready/blocked/failed/dropped、summary、needs_person结构化问题、result_artifact/hash、tested_commit、evidence_refs、stop_reason和usage_completeness。ready必须可读产物；退出码/LLM自述不能单独结束Ticket。

领域状态与launch/delivery效果同库事务提交，提交后才执行。确定未发送的读请求可以有界重试；发起后结果未知的写入/外部发送标delivery_unknown，先查实际回执/远端结果，不按计时器盲重放。租约过期只触发inspect，不把无人heartbeat自动当可重启。旧执行者未停止时禁止新写者接管。

### G2 第一版使用入口与可见状态

拟增加gcode orchestrator start/status/reconcile/stop命令和TUI任务面板（名称为设计，当前未安装）。默认disabled；local source只接本机明确用户请求，stop只停止指定任务，普通gcode CLI不被接管。每Ticket一个登记的worktree/目录和稳定run关联；跨任务写入、Git索引、桌面操作由单一owner控制。

默认最多2个active Tickets，遵守已有共享spawn上限/预算；不照搬原型“人消息额外加1 slot”的容量超限策略，先确保现有等待任务优先得到下一空槽。数值是首版工程起点，未调优。主控制器不长时间阻塞等待模型/工具；结果驱动刷新，状态查询不启动新模型；沉默需要inspect。

授权撤回停止后续写/派工并核对在途结果，不能仅发prompt通知。权限/来源凭据不写模型上下文；目录/工具检查仍只是应用层约束。后台server必须登记到assignment，ready后是否保留由任务结果明确说明；取消/恢复/归档先确认进程状态，沿用工作树清理计划，不自动删除。

### G3 GitHub与记忆的后续边界

首版不拉取外部事件、不发通知。后续只读GitHubSource按owner/repo与actor名单过滤、自身事件去重，CI/引用/其他作者正文仅上下文；不能让它们扩大Mandate。Outbox外部comment/PR/review动作默认关闭，普通已授权代码/文档push与新增外部发消息分开。Feishu与无人值守规则另立需求。

MyAgent以后可提供只读MemoryProvider.recall(query,scope,limit)，返回出处/版本/可信类别/原文指针；个人偏好与项目事实分开，不能把自动Curator摘要写入Mandate。先不把两库主循环、记忆数据库和事件监听器同时合并。

## 6. 执行顺序、测试、部署与回退

本轮仅完成调研/文档归档。下一轮进入开发后：G0执行入口修复与契约测试 → G1本机领域/崩溃恢复 → G2真实gcode入口端到端 → 获明确授权才G3外部来源。RAG C1可以与G0独立做，但每个仓库Git/服务/索引单一操作者；C2依赖C1基线记录并另冻结。C3/C4不要打包到同一个性能归因实验。

G0验收：parent deny在fork、LoadSkill、slash/普通child均deny；checker/registry/hook/预算共享实际验证；超预算/usage未知停止；上下文角色与原文完整回读；无授权child CU写拒绝。组件测不替代实际CLI模型/工具路径。

G1/G2验收：真实CLI/TUI完成接单→派工→产物/检查→报告→回读；重复trigger不重复ticket/run；崩溃窗口恢复不重复写；新input纳入历史恰一次且来源可审计；stale report拒绝；cancel/stop封存进程后释放slot；工作树不覆盖其他编辑；原gcode入口回归。详细固定10场景及真实模型比较见测试协议，数量不代表可靠率或前沿。

部署：本轮无部署。后续仅本机opt-in安装和正常入口验证，保留现有wheel/配置；DSH原型不自动安装。源码、测试、build、安装模块hash、正常使用入口分别记录。生产发布、OS沙箱、Linux/Windows、并发容量与多领域质量均需独立验收。

回退：C1关闭shared-client选项/回到原生命周期，C2关闭explore不影响原revision；新索引必须新revision验可见后activate并保留旧库。GCode控制层disable即可回原CLI；新增DB备份、schema升级拒绝新版本回开，停止本轮归属进程后回退，不删除任务/原始历史。G0权限修复不作为常规回退候选重新打开缺口，异常时禁用fork而非降为无checker。

## 7. 交接、未知项与完成判断

本轮完成标准是来源明确、实现差异/条件判断可核、两版决策一致、记录保留、公开文档实际远端同步。不是代码实现/系统安装完成。来源、链接、数字、业务文件hash与公开边界由主任务复核。

仍未知：企业实际完整部署/模型/intent/rerank身份、真实A/B速度与质量、长文/跨轮/中文泛化；SuperAgent原型实机运行效果、文章未公开设计、OS隔离与长期存储增长实测。没有等待用户决定的来源问题；superagent已明确。技术选型均为建议，收益只在冻结实际运行后升级为实测结论。以后简历量化引用既有公开证据，本轮未实施的设计不写为成果。

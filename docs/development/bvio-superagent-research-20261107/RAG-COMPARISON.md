# OpenViking 实现差异与证据强度

本文件是本轮可公开的独立实现对照。企业源码、内部文件路径与完整来源表另留本机。两份决策文档见[用户版](PLAN-FOR-YOU.md)和[执行版](PLAN-FOR-AI.md)。

## 1. 不能混为一项的三个比较对象

A 是企业的 Agent 记忆 HTTP 适配器：提供自动 recall、主动 search、原文分页、更新/整理任务、记忆投影；输出预览和继续读取提示。

A-engine 是其固定源码中捆绑的引擎：除了原生 find/search，还存在上下文组装、类型配额、分层正文、跨轮去重、查询扩展、请求内 embedding复用、可选摘要重写。当前 A-client 的请求没有 mode=context，而是直接 search/find，因此这些能力不能全部归给 A 的实际使用链。完整服务器分派文件不在当前48文件快照里，源码能力存在但实际部署/入口未知。

B 是个人通用证据 RAG：OpenViking 承担版本化 resource dense检索，独立关键词与重排模块承担排序，SQLite保存同版本原文/段落/hash，真实回答路径包含生成、引用检查和会话回读。

若只比 A 返回摘要与 B 返回完整证据，本质是工作量不同；若 A 接一个新答案生成桥接，就必须把桥接开销与其新质量一起测。没有同条件完整系统结果时，不能宣布 A/B 整体胜者。

## 2. 检索与排序的实质差异

| 项目 | A：源码事实 | B：源码事实 | 当前证据支持的判断 |
| --- | --- | --- | --- |
| Query入口 | recall=find，search=search，可带session；自动跳过过短/简单话语 | find固定resource scope/L2，无session意图分析 | B路径较确定；A可能多用会话信息。A实际planner开启状态及代价未知 |
| Keywords | caller提供最多8个字面关键词，转义后grep；无关键词不走此路 | BM25计算词项相关排序 | grep擅长精确行定位；不能声称语义/稀疏质量优于BM25 |
| Fusion | 语义池与keyword池各取limit≤10，同URI合并，轮流选后分组展示；keyword score=null | BM25/dense各40，与exact按RRF k60合并，最多60 | A保留检索来源诚实；B利用双路名次，排序机制不同 |
| Total limit | 原函数没有selected.length≤limit约束 | service返回max_units、排序候选最多60 | P05输入limit2、两路各2返回4，不能按请求limit作相同数量比较 |
| Rerank | 适配器没有外置重排，native可选配置；engine候选抽取其abstract标量进行rerank | Qwen/BGE完整段落，文献score为最高段落，附winner part | A当前部署rerank未证实；B实际Qwen在历史同query排序有贡献 |
| 名称“hierarchical” | 固定类说明：一次global search，再可选rerank | 固定L2global find后外置融合与重排 | 不能推断A逐层目录导航、更精准或复杂度更低 |
| Scope | memory/resource/skill、tenant/user/actor与targetUri；filter与grep资格对齐 | 固定resource revision，dense scope/profile/serialization/validated状态强校验 | 对长期Agent A更多功能；对版本证据B更明确。不是质量胜负 |

A的dual-hit预览把语义与关键词两块分配到800单位中，避免语义长摘要盖住关键词命中；P04证实合成否定关键词仍可显示。B的完整段落方式不直接对照这一预览优点，因为B用于后续证据生成。

A混合查询并行语义与grep，但filters触发时，还会按L0/L1/L2分别做filter-only find；includeProvenance还会逐hit并发attrs。源代码并行意味着部分串行等待可重叠，不证明全部请求更少或更快，额外调用都应进入时钟与用量。

## 3. 内容预算与精度

| 阶段 | A | B | 取舍 |
| --- | --- | --- | --- |
| 初次内容 | 800 UTF16单位预览；自动2500、主动8000正文预算 | 选中完整paragraph；正式max4/6000生成预算 | A可能降低首次正文体积，必须补深读才有完整条件 |
| 总预算 | 只计content/abstract的预览正文，不含titles/URIs/notices/JSON | 正常tokenizer模式测chat template；byte模式保留heuristic标识 | A的预览budget不能作模型完整输入保证；B的byte模式也不是精确token保证 |
| 小额预算 | 纯语义先给短项分配，截断预览；混合碰超额项直接结束 | 完整段落不够放则omit并继续；omit影响generation gate | A保证预览总正文单位；B保证不静默截掉段落，却可能缺证据/拒答 |
| 原文 | L0/L1目录摘要，L2文件，line/char分页、next/hasMore | 同revision的unit/part/全文读取，hash验证 | 已有B段落回读，应借鉴调度方式而非重复造库 |
| 可验证语义 | 输出检索来源、时间/版本/metadata，但无统一答案判定 | model判语义，gate验证quotes原文出现、ID/结构合法 | 两者都不能把源文出现自动说成结论正确 |

P02：合成1216单位段落末尾含明确条件，preview800缺该条件且truncated=true。有继续read提示，未做实际Agent继续read，因此不能说A会误答；只能说初次返回不够支持完整结论。

P14：遵守title120上限的合成hit，content budget100，serialized JSON588；不是实际prompt token。P03直接函数输入title1500超过adapter约束，JSON1966仅表示函数不预算title，不作为实际入口负载证据。真实prompt可能使用formatter而非原JSON，必须测实际送入模型的message。

P13：UTF16 slice的3单位可切开两单位emoji。它是合法合成Unicode边界，不是生产错误率或RAG质量分数。

A-engine另有更完善的预算策略：按类别默认tier先覆盖广度，再用剩余预算加深；超过单项cap降级，使用rendered fragment（包括envelope）估计token。其render文件调用estimate_text_tokens，不等于绑定当前generation tokenizer的精确chat计数。memory类别的abstract标量可能是完整body，resource/skill的abstract可能是生成摘要，不能笼统说所有abstract都是压缩摘要。A当前adapter没有用该assembly模式，本轮也未执行它。

## 4. 记忆过滤、生命周期与运行资源

A在类型、相对时间、tags、来源、当前user/actor scope上的接口更丰富。相对时间一次冻结，语义/grep资格检查共用时间；自动事件时间衰减保护默认30d，显式null/0/period优先，aliases冲突拒绝。P09–P12验证输入边界，**没有执行native time-decay公式、数据库过滤或企业实时更新**。

A写入与整理路径有接受回执、task id、terminal状态、恢复轮询、投影更新失败的独立pending状态；停机/待机先拒绝新工作、排空accepted native任务与vectorfollowup，再停embedding。model gateway embedding按local/remote各串行，上限8，取消有signal。这些设计可帮助长期桌面Agent限制资源，但并发1会限制吞吐；实际吞吐、RSS、冷启动、排空时间均未知。

B并不是毫无恢复与背压：入库先持久化delivery_unknown，原文hash对账后content_verified，向量visibility单独校验；没有自动盲重试未知写入。重排共用Semaphore1，超时后台线程仍占位直到完成，防止超时后堆积并行模型工作。模型冷启动在API生命周期同步加载，资源/关闭优化有具体候选。本轮不以A功能较多直接判它“企业级更快”，也不以B通过更多测试直接判整体更可靠。

A-client用Node fetch带deadline和redirect:error，平台可能复用连接；源码没指定自有池/dispatcher，不能写自研高性能连接池。B每次find新建httpx client，这是可明确改进的生命周期点，收益需T1测出来。B显式trust_env=false避免环境proxy参与；C1必须保留。

A图是presentation projection，当前subgraph检索501，不是检索GraphRAG；旧embedding calibration注释和函数没有参与当前默认adapter排序，当前adapter无默认floor。不得搬旧simFloor/pivot作为新RAG通用信心阈值。

## 5. 真正可用的性能证据

以下已有个人成绩来自固定版本历史记录，不是本轮重新跑，也不是与企业对比：

| 个人历史300，同query的检索阶段 | nDCG@10 | Recall@20 |
| --- | ---: | ---: |
| FTS5/BM25 | 0.668898 | 0.836556 |
| OpenViking/BGE-M3 dense | 0.644566 | 0.823556 |
| RRF重排前 | 0.704273 | 0.868556 |
| 最终Qwen融合重排 | 0.794201 | 0.935889 |

最终对BM25 nDCG绝对+0.125303，相对+18.73%，paired bootstrap95%[0.092150,0.159107]。对RRF重排前绝对+0.089927，95%[0.061724,0.120235]。这些是一次实际完整流程里的排名阶段恢复，经TREC复核；不是为每个阶段重新独立生成答案，所以只证明排序贡献。

历史300完整答案与引用/会话流程269/300，label212/300，citation doc+labelF1 .535774。旧wall受主机睡眠影响，不拿旧mono p50/p95作现在生产速度证据。

| 最近固定30，旧→新回答方式 | 旧 | 新 |
| --- | ---: | ---: |
| label正确/30 | 21 | 22 |
| flow完成/30 | 27 | 29 |
| NEI正确/10 | 4 | 6 |
| CONTRADICT正确/10 | 7 | 6 |
| citation正确pairs | 16 | 15 |
| citation doc+labelF1 | .561404 | .714286 |
| citation recall | .800000 | .750000 |
| 完整wall p50 / p95 秒 | 25.911 / 38.002 | 29.396 / 52.712 |

两组real OV ranking完全相同；总体accuracy差95%[-10,+16.667]百分点，3改善2退步，McNemar p=1。小样本不证明稳定更好，新grounded格式还把首字推到结构验证后。因此当前更优先解决证据/语义/生成质量和等待，而不是直接取消已有有用的ranker。

企业validation文档是2026-10-26历史自述：249功能/包装等tests通过、native integration使用deterministic substitutes，明确没测真实model quality/performance。当前选择性快照没有tests与完整日志，本子任务未重复执行。来源声明与独立复跑的证据层次不同。

本轮实际纯函数探针为Node v26.4.0/macOS arm64，企业历史文档/部署要求为Node24系列，不能作其支持平台安装兼容性验收。企业manifest engine0.4.24.dev70与个人实际OpenViking0.5.3不同，企业在线runtime版本未知；也不能因为版本数字新旧判性能优劣。下一轮公平对照必须固定后端/模型/依赖身份，分同引擎组件实验与各自实际栈完整实验。

## 6. 哪些方案结论现在可以成立

| 结论 | 当前等级 | 依据/下一步 |
| --- | --- | --- |
| B的融合+Qwen对本SciFact同题排序有贡献 | 历史实际系统数据支持 | 历史300阶段trace/paired/TREC |
| A短预览可能省初次返回正文 | 设计及纯函数行为支持 | 不涉及模型总tokens/全流程等待，需T2 |
| A比B整体更快/更准 | 未证实 | 缺T3同语料/模型/硬件/完整用户路径 |
| A时间/类型/来源与待机任务管理更丰富 | 源码支持功能差异 | 实际部署能力/稳定性/效果未知 |
| 共享HTTP可减少重复生命周期工作 | 源码理由，收益预期 | T1隔离测真实find与关闭/取消 |
| 摘要探索+完整证据回答值得独立候选 | 目标适配建议 | T2不降低质量/覆盖，测真实read调用 |
| 删BM25/RRF/Qwen、搬企业grep与阈值 | 无支持 | 违反既有证据与public independent边界 |
| A-engine全部上下文能力已在A中使用 | 不成立 | adapter请求未走context mode；完整dispatch/部署未知 |

开发候选见[AI版](PLAN-FOR-AI.md)，公平测试见[测试协议](BENCHMARK-PROTOCOL.md)的T1–T3。正式样本继续30，不放大样本、不对这批公开题继续挑最优参数后宣称前沿。简历可写已实现的OpenViking、版本化证据和固定数据检索成绩；本轮纯函数观察不写成系统速度提升或企业性能对比。

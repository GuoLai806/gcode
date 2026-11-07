# 后续测试协议：测实际用户路径，不把组件观察当性能成绩

状态：本轮只读调研，以下是下一轮的执行依据，未运行这些新benchmark。与[用户版](PLAN-FOR-YOU.md)、[AI版](PLAN-FOR-AI.md)同组决定。现有实际RAG复现方法参见[固定版本的复现说明](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-quality-20261107/REPRODUCTION.md)。

## 1. 本轮已经做的实验

实际导入企业JS纯函数，独立合成输入，Node26.4.0/macOS arm64，v2共14个唯一边界场景。v1的13个重复场景保留但不累加。实际OpenViking网络、embedding、reranker、回答模型、索引、更新与服务生命周期均没有执行；不计算系统成功率、生产延迟、问答质量或前沿排名。Node与企业声明的24不同，只证明该运行环境中的函数行为。

P02只说明预览未含原文末尾条件；有继续读提示，不代表完整Agent会误答。P03使用超过入口上限的1500单位标题，只是纯函数边界，不用于实际入口推断；P14符合120单位标题上限。588个JSON字符单位不是实际模型token。P05的limit是两路候选池上限，不是合并总数。原始结果/hash/source范围见evidence，企业脚本和48文件身份明细只留本机，公开观察不能代替访问授权后的完整复现。

## 2. T1：共享HTTP客户端，先验证一个因素

目的：验证C1是否减少实际find阶段开销，以及取消/并发/退出是否正常。不改变任何排序/生成参数，不用MockTransport计时包装网络收益。

输入：既有公开正式30的题号（不发答案模型）、固定resource revision和同一真实OpenViking服务，query/scope/limit40/level2/read_content false一致。基线每次新建AsyncClient，候选服务生命周期复用；timeout/trust_env/auth/redirect相同。真实service ready、index验证记录和实际版本必须可读。

每query串行运行两变体，按题号hash固定15组AB、15组BA，顺序在开跑前冻结。共享同一实际后端、不额外加载两套embedding/rerank模型，不改云参数或正式索引。记录客户端创建/完整请求/JSON解析耗时、返回URI/score/order、status/失败/取消、实际连接信息可观测时保存，不可观测写unknown。冷启动和正常warm分开；若不重复采样，就只能报告本轮观察，不能解释尾延迟稳定性。

验收：30题结果身份与排序一致（浮点分数比较定义在manifest固定）；无新增失败、取消不关闭其他请求、进程退出共享client确实关闭且不接新请求。分别报告阶段wall p50/p95和全分母，完整回答提速不在本阶段结论范围。若该阶段收益很小，仍可凭生命周期正确性采用，但不得给简历填虚构百分比。

## 3. T2：探索预览与完整证据，在真实RAG上对照

目的：确认C2对用户等待、证据覆盖和答案的影响。预览只是探索，不能代替完整证据。

数据：开发6（支持/反驳/资料不足各2），正式30（各10），保持原抽样和公开已见的事实，不称隐藏未见集。开发可以做合法调试，正式开跑后不按错题改参数、挑题或重跑取高分。新run_id和输出路径不得覆盖历史300/30及本轮记录。

变体A：当前完整段落检索与生成；B：可选探索/深读策略。其他全部同一：完整语料及hash、title-newline-text serialization、OV身份、本地embedding/reranker权重revision/device/dtype、BM25/RRF/Qwen、候选数、最终证据4、预算6000/输出reserve、答案format/gate/生成模型/重试。第一次正式比较只改变获取/展示策略，不能顺便换reranker或回答提示。 两组默认都使用已验过的可选grounded_json + grounded_evidence，不改变产品text默认值；上下文32768、framing512、输出reserve8192、deepseek-v4-pro alias/thinking enabled-low/temperature0沿用已验配置，完整tokenizer/prompt/config由新manifest冻结。云alias并非可锁定权重，保存实际alias/fingerprint与返回身份，不能承诺云权重字节重现。若模型已不可用需记录新配置，不能混作同模型历史提升。

如果比较用户主动探索与一键回答两种不同任务，应各自计完成边界，不能混成一个p95。为测试一键回答，B的所有必要深读、额外检索、摘要/重试都进入同一请求的时间与用量。默认禁用新增query expansion/rewrite；若以后开启，另立变体和冻结，不称单因素改进。

同题两变体各30，逐题串行AB/BA顺序冻结，保持主机唤醒，单一操作者。一份共享真实模型服务或不重叠生命周期，避免双重加载改变内存。真实POST→首个可见正文→SSE结束→版本原文回读→完成会话回读；思考token、预览、状态提示不算正式答案首字。停止和取消另外保存admitted/settled时间。

指标与定义：
- 排序nDCG@10、Recall@10/20、MRR@10；排名长度不足不能补虚构文档。 qrels/标准文本不进入检索输入。
- 预算后最终证据coverage：回答模型真正收到的证据与gold qrels交集/应有证据，不用top20覆盖代替。
- 全30标签正确率、macroF1、三类别切片；citation是文档ID与标签共同命中的micro precision/recall/F1，同时报正确pairs和预测总数。
- 原文hash/版本回读、摘录字面校验与失败；不将字面出现当语义支持，语义错误单列。
- 全30完整wall p50/p95（统一NumPy线性插值）、首字只在有可见正文样本并报n、失败/超时/停止率、额外read/embedding/rerank/generation调用数。
- 所有attempt的输入/输出/reasoning/cache tokens和usage是否齐全；缺报未知不能填0，也不能把总tokens写成实际账单。

来源原文和原始SSE、模型request/response保留本机；公开保留全部数字、query_id、gold、排名、失败、时间、usage和hash，去掉私人路径、语料正文和凭据。公开hash与original hash分别记录；所有失败留分母，runner非零退出不作为重跑理由。

小样本采用paired query bootstrap、固定seed与抽样次数、配对逐题改变、McNemar和各组Wilson；区间跨0时不宣布稳定胜出。参数和选型门槛在开发结束、正式发题前冻结。

采用建议：无新增流程失败、预算后coverage不降、macroF1/citationF1观察不降；反驳或资料不足明显退步需复核。若要称本轮完整提速，预设完整wall p95至少观察改善10%，同时质量条件满足；10%是工程选择，未证实统计/行业门槛。只有阶段改善就只报阶段。候选可opt-in，不因小样本直接替换默认。

SciFact是短文献摘要，不能证明长文导航收益。另6个机制场景固定：末尾否定、跨段条件、重复文档不同revision、预算不足、深读失败、用户中途停止。合成场景不进标准质量分数；以后要宣称长文/中文收益必须另定公开评测，而不是继续扩写旧30题成绩。

## 4. T3：确有必要才比较企业原样系统

本轮不运行：缺企业完整可运行快照/实际模型身份，建新索引/启动服务也超出只读边界。以后先在隔离环境取得合法完整快照，禁止动企业活跃实例、业务语料和用户记忆。

同公开resource corpus、同hash/serialization、同embedding权重/dtype/device、同硬件与资源上限。若企业原流程先进行memory抽取并重写原文，则属于不同系统方案，不能声称同资料检索更优；需要分别报告入库成本/丢失和回答效果。

保留原样find/search、session意图分析、native重排、可选grep、过滤资格/attrs/read调用；记录所有额外云请求和等待。若为归因关掉planner或换模型，叫normalized variant，不冒充企业原样性能。关键词来自冻结的query解析，不得用gold生成；额外模型生成关键词的成本进入用量。

企业只有预览接口时，只能报检索/工具性能；要与我们的完整用户路径比较，接相同生成、引用、原文和session回读的独立桥接，并把桥接成本计入企业候选的完整请求等待与用量，不能藏在计时外。返回数量按实际结果核对，不只统一limit字面值。完整系统A/B沿用T2失败分母与统计，至少达到其同任务完整性才能判性能。

结论分拆为质量、等待、并发/资源、更新可见与恢复；功能更多或正文更少不等于更好。未实际测过的列保持unknown。

## 5. GCode SuperAgent：10个固定工程场景

先完成G0执行入口修复，两组均使用同一修复后基础版本，仅切换控制层；否则把权限补丁收益误算成架构收益。未接入的旧CLI对不支持的长期行为记unsupported，不虚构一次成功运行。工程场景不是RAG30题，也不是代码生成行业榜单。

10场景：重复trigger；原任务followup；引用/CI不扩权；并发满时用户问状态/补充；共享预算耗尽；压缩后原要求可回读；执行中重启恢复；写已发生但本地确认前中断；用户stop；failed任务不被bot唤醒且最终证据/审阅后交付。

开发状态机可用fake Executor，证明事务和幂等契约，但最终从真实gcode CLI/TUI+实际模型+工具路径执行接单、补充、派工、产物检查、状态回读。恢复/写入窗口用授权的隔离本机动作和真实结果核对，不发外部消息或动生产。模拟的远端不能证明真实GitHub恰一次发布。

每场景保存spec/source/config/model/capability/budget/工作树身份，Trigger/Mandate/Ticket/Assignment/Run关联，原请求/回执/状态快照，input持久化/进入request/可见时间，stop admitted→quiescent、重复派工/写数、峰值队列/后台进程、全部执行者总usage、失败及unknown。一个框架的自述DONE不计成功；可读产物、相应功能检查、原文与状态回读都满足才算该场景完成。

首版建议门槛：10个约定场景均达到对应功能，越权/重复写/丢失人工stop为0，原CLI未接管时可正常使用。人工状态查询不启动模型、不突破总slot/spawn/token上限；其实际等待完整报告，不先承诺毫秒SLA。n=10不证明生产可靠率，不写100%自治或行业前沿；语义/代码质量收益另做固定任务集。

## 6. 冻结、证据和收尾

开跑前生成不可覆盖的manifest：实现SHA/源码hash、上游SHA、模型/实际backend身份、参数、数据/query/scope/hash、用户入口、顺序/seed、指标公式、失败规则、预算、OS/硬件/冷暖、time算法和输出路径。基线/候选互相绑定，正式报告或journal已存在禁止重新冻结或重放同名称。

计时保存UTC/ns、wall、monotonic和逐事件快照；独立审计从原始事件重建，时钟反跳/睡眠标flag。正式输出全部保留，独立复算不复用同一评分实现掩盖错误。源码/模型身份前后核对；build/install模块hash与真实入口验收另存，不混进质量样本。

协议预计产物目录为benchmarks或docs/development对应run_id，名称在下一轮记录确定；本文不编造尚未存在的runner命令。复用已有serve_user_flow/run_user_flow/audit/compare工具时先核对它们的参数契约；企业包未拿到时不声称npm test可运行。必需检查通过后完成已授权本机安装/正常入口与文档推送；生产/外部写入需范围授权。每种方案均有disable回退、保留DB/原文/回执/工作树，unknown不重放。

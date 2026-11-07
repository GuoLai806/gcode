# 来源、实测与未知：如何核对本轮结论

[用户版](PLAN-FOR-YOU.md)和[AI版](PLAN-FOR-AI.md)为同组决策；这里给出可核证材料，避免把源码能力、组件实验、历史运行和方案建议混成一个成绩。

## 本轮固定范围

| 对象 | 固定身份 | 本轮实际访问/运行范围 |
| --- | --- | --- |
| bvio OpenViking参考 | violoop-mem-ov@8420a1bd38d8f197aef3b8dafd39de07bc4a363b | 48个相关文件，选择性快照；14个JS纯函数合成场景，无实际服务/模型/索引 |
| 个人通用RAG | dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0，实现561ec65 | 源码与既有真实OV0.5.3/300/30报告，本轮没有重发问答 |
| GCode | e480127bc1590efadf505aca4a71f86ed95f6742 | 现有运行/技能/权限/预算/工作树代码，16份核心来源摘要和只读AST审计 |
| DeepSeek SuperAgent | 8c32a9dc5d72c033816c6a8110b37f40cf94fba4，0.1.0，MIT | 43份公开源码/文档，未安装/构建/启动/调用模型 |
| DeepSeek Harness参考 | fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159 | 固定宿主文档与代码，不能自动推断SuperAgent与当前master已兼容 |

主目标已由用户明确纠正为superagent，原Superpowers/3社区移植仅保留本机历史初查，不属于本轮开发路线。MyAgent只涉及历史记忆快照参考，未完成最新完整实现和运行核查。

## bvio 证据公开边界

企业源码、内部路径清单、两版实际调用脚本与业务配置只留在本机任务草稿，未复制到公开仓库。公开内容是独立描述、合成输出和身份摘要，不足以让无访问权限的读者直接重跑企业代码；需要复跑时先取得合法私有快照。源身份明细文件hash为98094af3743b2470730084c7a6c6490af69a91645dcaa2ad891c72db98383850，不代表当前服务身份。

公开证据：[v1 13场景](evidence/bvio-pure-probe-v1-results.json)、[v2 14场景](evidence/bvio-pure-probe-v2-results.json)、[源文件完整性审计](evidence/bvio-source-integrity-audit.json)。v2原字节SHA256为767691f1ee7f5094be102c7e0540d2db7cf61ddd8208d27ad65f81e70ee0e7e3。48个所选源码文件未改变；不覆盖未下载源码，也不是企业线上身份核验。

主要源码位置已在本机核对：HTTP适配器/原生client的find/search调用；hybrid合并与preview预算；hierarchical类的全局检索；context assembler入口与budget/tier/gather/ledger；入库journal/退出排空。公开[RAG对照](RAG-COMPARISON.md)记录具体行为和取舍，不复制企业实现。

企业验证文档的249测试是2026-10-26历史自述，native integration使用deterministic substitutes且明示未测真实模型质量/性能。本轮未取得其完整tests/运行日志，也未重跑，不能当本轮真实性能证据。engine声明0.4.24.dev70与个人实际OV0.5.3的版本差异不能直接判先进/落后。

## 个人RAG历史证据（本轮只读取）

[历史300题结果](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-user-flow-20261106/RESULTS.md)与[同题排序贡献和区间原始数值](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-user-flow-20261106/evidence/openviking-formal-test-v1.retrieval-paired.json)：BM25 nDCG@10=0.6688975974，最终0.7942005100，差0.1253029126，95%区间[0.0921502525,0.1591068118]；Recall@20=0.9358888889。这是同一真实运行中排名阶段的回顾性比较，不是各阶段单独生成答案，更不是企业A/B。

[30题真实问答结果](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-quality-20261107/RESULTS.md)及[配对原始数字](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-quality-20261107/evidence/paired30-v1.json)：正确21→22/30，流程27→29/30，NEI4→6/10，反驳7→6/10，引用F1 .561404→.714286，但正确引用pairs16→15、recall .8→.75；完整wall p50=25.911→29.396秒，p95=38.002→52.712秒。总体变化区间[-10,+16.667]百分点，不能称稳定胜出；旧300计时跨睡眠，不与本轮实时延迟混用。

[现有选型说明](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/docs/development/openviking-quality-20261107/TECHNOLOGY-DECISIONS.md)与[当前检索源码](https://github.com/GuoLai806/GuoLai806-law-ai-advisor/blob/dc301bef96a76f38e3b7c28cbc1c1ee1a112d0f0/evidence_rag/retrieval.py)支持保留版本检索、完整段落与测量预算。连接复用/渐进读取的收益仍未测。

## SuperAgent与GCode源码身份

[逐项源码索引](SUPERAGENT-SOURCE-INDEX.md)给出S01–S20和相关E编号的固定GitHub提交、行号与文件SHA256。重要依据为：[原型README](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/README.md)、[domain模型](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/docs/001-domain.md)、[Executor ports](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/ports.ts)、[实际架构](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/docs/007-architecture.md)。

[43份原型来源摘要](evidence/superagent-source-manifest.json)、[16份GCode摘要](evidence/gcode-source-manifest.json)、[子任务只读核查记录](evidence/reference-readonly-checks.json)固定实际读取范围。126份hash检查包含DSH、旧Superpowers与社区参考，不等于读了126份SuperAgent实现；43份文本的Council/Tape等关键词零命中仅辅助界定调查范围，不能证明全仓库绝对不存在某设计。

[GCode技能fork](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/skills/executor.py#L97)、[默认许可决策](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/agent.py#L450)、[模型LoadSkill入口](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/tools/load_skill.py#L44)和[只读AST结果](evidence/gcode-skill-contract-v2.json)说明本轮确定的入口不一致。可复算脚本为[evidence/audit-gcode-skill-contract.py](evidence/audit-gcode-skill-contract.py)，命令从GCode根目录执行：python docs/development/bvio-superagent-research-20261107/evidence/audit-gcode-skill-contract.py .；脚本只解析源码，不import GCode、不创建运行账本或执行工具。v1输出保留，v2把“传入总额度数值”与“共享预算对象”分开，避免不准确字段名。

## 公开归档和后续结论

全文无企业源码、业务语料、私人聊天/简历、凭据与本机私有配置。公开哈希摘要没有提供缺失的私有原始文件；完整原始来源与实验脚本已保存本机，复跑访问边界明确。原型MIT支持后续按许可证使用；本轮没有复制其运行实现。企业AGPL代码不复制进个人公开实现，后续按独立设计实现候选。

所有未实施建议、未运行系统、未观测资源指标保留unknown/预期。文档同步与业务源码前后核对见[交付核查](RESEARCH-VALIDATION.md)，远端提交在最终交付回执中核实。

# 本轮交付核查：调研完成范围与未验证项目

[用户版](PLAN-FOR-YOU.md)和[AI版](PLAN-FOR-AI.md)为权威同组决定。本轮交付为只读研究和可执行规格，未进入业务开发。

## 实际完成

已核对企业48个所选文件与个人RAG/GCode固定版本，确认适配器实际find/search/grep路径、未调用context assembler的范围、完整证据与预览差异。14个实际导入企业JS纯函数的合成场景原始输出保留；v1/v2重复不累加，输入超过adapter限制的P03不作为真实入口证据。企业所选文件前后hash一致。

已读取官方SuperAgent43份源码/文档，固定8c32a9d；来源、领域ports、持久状态、worker、权限/目录、outbox窗口和DSH依赖均有固定GitHub链接。主任务独立核对README、domain、architecture、ports、store及executor说明，核实它是研究原型、公开版不等同文章全部设计。没有执行SETUP或任何来源监听器。

已独立解析GCode技能fork/LoadSkill/Agent源码，保存AST脚本和两版输出；没有import Agent、运行工具、建立运行DB或进行越权操作。普通子任务已有约束；缺口是另一技能入口，不能写成全产品没有权限。

主任务从历史300 paired JSON复核BM25/final nDCG、Recall与区间，从固定30结果复核质量/引用/等待范围；这些属于过去的真实系统记录，本轮没有重发题。未使用旧睡眠计时证明本轮速度。

## 分项验证状态

| 项目 | 实际状态 | 不能推出的结论 |
| --- | --- | --- |
| 业务代码 | 本轮不改；前后文件hash/仓库diff核对 | 方案已经实现 |
| 组件实验 | 14合成边界观察 | 企业问答成功率、真实性能胜负 |
| 工程回归 | 本轮没有重跑业务测试 | 本轮新的运行功能已通过 |
| 文档 | 两版、详细对照、来源、测试协议与公开证据齐备；链接/数值/边界审阅 | 新架构已上线 |
| 构建与安装 | 未做 | 可直接安装SuperAgent或跨平台兼容 |
| 正常用户入口 | 本轮未启动/变更/重新验收 | 新控制层/新探索入口已可用 |
| 企业系统A/B | 未运行，缺完整运行/模型身份 | bvio或个人整体更快/更准 |
| 外部写入/监听 | 未启用 | 自动接单/回帖/合并获得授权 |
| GitHub归档 | 本组相关文档与证据按两仓库既有分支同步，完成以远端回读为准 | 本地commit成功就等于同步完成 |

## 源码与公开边界

[evidence/business-source-before.json](evidence/business-source-before.json)记录恢复本轮时的个人业务源码身份（排除docs/README）。最终[evidence/business-source-after.json](evidence/business-source-after.json)逐项核对相同文件；企业范围见[bvio审计](evidence/bvio-source-integrity-audit.json)。这只覆盖记录文件，不把源码hash当线上服务身份或完整文件系统无变化证明。

公开文件仅含独立分析、公开参考来源的hash/链接、合成观察、个人源码hash与文档核查。企业源码/内部路径表、私有实际调用脚本、凭据、语料正文、私人聊天与简历原件未复制。原始私有材料在本机既有任务目录保留，公开读者依靠来源链接和摘要可以核对公开结论，不能无权限复跑企业代码。

独立审阅报告位于[REVIEW.md](REVIEW.md)。主任务核实发现后统一更新双版及相关资料；审阅不代替真实后端运行。文档镜像在两个关联仓库的docs/development/bvio-superagent-research-20261107，README提供入口；两版同组更新同提交，不写无关仓库。提交SHA与远端文件核对结果由最终交付回执保存并在聊天提供。当前Git直连github.com超时，GitHub API可用；同步可通过Git Data API发布完全相同的本地blob/tree/commit，使用force=false更新分支，并逐文件回读，不改变提交语义或业务代码。

## 未完成但不属于本轮交付的工作

C1共享连接实测、C2探索与深读、G0执行入口修复、G1/G2持久任务控制层仍未实施。企业完整A/B、SuperAgent实际运行、长文/中文/多领域、资源/并发、OS沙箱、生产发布均未验证。它们有明确规格和下一轮顺序，但不是本轮提前启动的事项。

当前没有等待用户补材料的来源问题：superagent已确认。后续需明确进入开发，相关范围/边界继续沿用；取得真实运行数据前，候选收益保持预期，简历不提前宣称性能提升或前沿成果。

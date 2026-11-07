# 固定源码依据与只读核查范围

主目标为 DeepSeek SuperAgent；S 编号支持当前两版，E 编号支持 GCode/DSH 对照及旧 Superpowers 附录。所有判断为源码/文档核查，未运行框架或模型。文件 SHA256、长度和原始来源见对应 manifest。GitHub 链接固定提交，避免后续 main 改动造成依据漂移。

<a id="s01"></a>

## S01：官方发布身份、研究原型而非产品、公开版与文章/内部版不完全相同

来源：[deepseek-ai/dsh-superagent-prototype/README.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/README.md#L1-L8)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–8。

文件 SHA256：`737997cf5b7d4129f12ed5485ebbdd5e9d2ce3859a82ded6ac535d222327b713`。


<a id="s02"></a>

## S02：包身份、0.1.0、private、Node/pnpm与alpha运行依赖

来源：[deepseek-ai/dsh-superagent-prototype/package.json](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/package.json#L1-L115)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–115。

文件 SHA256：`f5170d812137dd370c568decb481e19f4da9a3d1fd7bad341a0f07942020a559`。


<a id="s03"></a>

## S03：实际domain流程与实体；Executor属于部署、无已实现Council/Tape断言

来源：[deepseek-ai/dsh-superagent-prototype/docs/001-domain.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/docs/001-domain.md#L5-L53)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 5–53。

文件 SHA256：`cd010379e65cc428ffb335aee46529f2a524b8f573fc72359223060fb5a5111b`。


<a id="s04"></a>

## S04：Trigger不可信正文、Followup归属、Mandate不可变与来源身份

来源：[deepseek-ai/dsh-superagent-prototype/src/core/model.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/model.ts#L1-L170)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–170。

文件 SHA256：`982155fe6a03c887a7ac4475c6d1592d12aa23c5fe3698403c93bbfd6469d44a`。


<a id="s05"></a>

## S05：可复用Policy/Assessor/Executor/Outbox/Repositories端口

来源：[deepseek-ai/dsh-superagent-prototype/src/core/ports.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/ports.ts#L1-L134)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–134。

文件 SHA256：`0b44f1cd716d64776b0e3ea74a158cf0effd92e763b1b13c7705e766e9225a43`。


<a id="s06"></a>

## S06：worker/router能力、普通spawn、后台shell与压缩组合

来源：[deepseek-ai/dsh-superagent-prototype/cordis.patch.yml](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/cordis.patch.yml#L1-L145)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–145。

文件 SHA256：`fc9271cdf9b3d96bcb7febffe194f92cb427a88044168f83b3fb7522ab5c9bce`。


<a id="s07"></a>

## S07：结构化stage与canRetry

来源：[deepseek-ai/dsh-superagent-prototype/src/core/stage.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/stage.ts#L1-L26)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–26。

文件 SHA256：`b935012a654d2a68ca20cb27909ddc8dceafb704b56a16a23a08036a546141df`。


<a id="s08"></a>

## S08：SQLite/WAL+FULL、schema迁移、工作集索引、atomic

来源：[deepseek-ai/dsh-superagent-prototype/src/app/store.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/store.ts#L1-L164)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–164。

文件 SHA256：`c124de893fbe260571b18b0ac4875bc7647e44e72062ba38b02c809e0012d583`。


<a id="s09"></a>

## S09：durable effects去重、generation、并发、退避与排队

来源：[deepseek-ai/dsh-superagent-prototype/src/app/effects.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/effects.ts#L41-L161)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 41–161。

文件 SHA256：`d350590473299398b17c50dd641c72e1995dd95920c5138699491ab77e3ae481`。


<a id="s10"></a>

## S10：send事务、外部发送之后才保存settle；不等于外部exactly once

来源：[deepseek-ai/dsh-superagent-prototype/src/app/outbox.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/outbox.ts#L20-L52)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 20–52。

文件 SHA256：`48d20062dd8c34c2b95e851c78265c9e403d1040894e97c7d9d0fa190d54415e`。


<a id="s11"></a>

## S11：WorkerSlots与人工+1槽的实际实现

来源：[deepseek-ai/dsh-superagent-prototype/src/executor/dsh.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/executor/dsh.ts#L164-L198)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 164–198。

文件 SHA256：`6445a03121fa9bd15fc437736bcc2acc6ab950c5fe732e5b99eb8ee2c8a9476b`。


<a id="s12"></a>

## S12：Sessions.ensure明确设置danger-full-access

来源：[deepseek-ai/dsh-superagent-prototype/src/app/sessions.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/sessions.ts#L137-L155)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 137–155。

文件 SHA256：`ca2b98e57e9f27b2abb0afab59d44ea744a96d8be4cf81d7b3776901b56cd36b`。


<a id="s13"></a>

## S13：背景生命周期、prepare、环境边界、提示词auto merge

来源：[deepseek-ai/dsh-superagent-prototype/docs/003-execution.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/docs/003-execution.md#L23-L90)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 23–90。

文件 SHA256：`049aa22a717f75b9dec4cd6969356db6f736c127de4501c3ce1f6d846217f6eb`。


<a id="s14"></a>

## S14：MemoryRepositories与fake executor/assessor测试；未运行

来源：[deepseek-ai/dsh-superagent-prototype/tests/core-engine.spec.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/tests/core-engine.spec.ts#L1-L74)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–74。

文件 SHA256：`e29358c139a2dbb1a2877e980e043f34cf39bca1905fb10ee14e0b4866bc1a6b`。


<a id="s15"></a>

## S15：Runtime锁stateDir和依赖composition

来源：[deepseek-ai/dsh-superagent-prototype/src/app/runtime.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/runtime.ts#L49-L106)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 49–106。

文件 SHA256：`5befef035b4a70978cd881b32282680260c6d2561679f890dd911214664cf515`。


<a id="s16"></a>

## S16：启动/投递/读入session与重启恢复实际接线

来源：[deepseek-ai/dsh-superagent-prototype/src/executor/dsh.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/executor/dsh.ts#L423-L551)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 423–551。

文件 SHA256：`6445a03121fa9bd15fc437736bcc2acc6ab950c5fe732e5b99eb8ee2c8a9476b`。


<a id="s17"></a>

## S17：Engine唯一事务修改入口与evaluateDue

来源：[deepseek-ai/dsh-superagent-prototype/src/core/engine.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/engine.ts#L18-L91)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 18–91。

文件 SHA256：`bd9a4caff834859877d1a08ccddebc990d0e1ca568674b80f9d59ce5adcac827`。


<a id="s18"></a>

## S18：账号/环境变量隔离只为默认路径guardrail

来源：[deepseek-ai/dsh-superagent-prototype/src/infra/environment.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/infra/environment.ts#L1-L67)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–67。

文件 SHA256：`413680e755ed36b74157f364a38cb5dbe81e4af0db0fa88c8376c682e2282a7c`。


<a id="s19"></a>

## S19：MemoryRepositories测试用状态，不是长期语义记忆

来源：[deepseek-ai/dsh-superagent-prototype/src/core/memory.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/core/memory.ts#L1-L50)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 1–50。

文件 SHA256：`36cefca987a4e533369a414e52e3fb4754945ae942bb021f8e5cf23c186cf536`。


<a id="s20"></a>

## S20：2s定时pass与事件唤醒/合并

来源：[deepseek-ai/dsh-superagent-prototype/src/app/passes.ts](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/8c32a9dc5d72c033816c6a8110b37f40cf94fba4/src/app/passes.ts#L17-L69)；固定提交 `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`；行 17–69。

文件 SHA256：`79688aeb8c43396b9f122b3feba0ce1c422f1bfbca3b32919cd764a217b67ea9`。


<a id="e01"></a>

## E01：DSH插件、profiles与bundles

来源：[deepseek-ai/deepseek-harness/docs/architecture.md](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/architecture.md#L7-L31)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 7–31。

文件 SHA256：`6a04050d8e8af817ee198592b7d1c280a4198252e0948af3bdae4876aebbb591`。


<a id="e02"></a>

## E02：Subagent activation、local/external生命周期和接口

来源：[deepseek-ai/deepseek-harness/docs/subsystems/subagent.md](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/subsystems/subagent.md#L5-L140)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 5–140。

文件 SHA256：`7cd8dc50f5097a83d7ea175da9edbda30c9f52f8efe911da38cebbae20e088b4`。


<a id="e03"></a>

## E03：子任务策略捕获和durable记录

来源：[deepseek-ai/deepseek-harness/packages/subagent/subagent/src/child-agent.ts](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/subagent/subagent/src/child-agent.ts#L239-L279)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 239–279。

文件 SHA256：`f632ef9e600a0508a4112e47f7862a3382ae5080d03353d04ed2449eda6f4fac`。


<a id="e04"></a>

## E04：压缩持久事务、工具pair与pressure/overflow

来源：[deepseek-ai/deepseek-harness/docs/subsystems/compaction.md](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/subsystems/compaction.md#L5-L103)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 5–103。

文件 SHA256：`eeda604d2e3da90ada52ef143cf7807f2f9969174379e5e2182442f763cf16e8`。


<a id="e05"></a>

## E05：experimental默认关闭，不复制源checkout未提交文件

来源：[deepseek-ai/deepseek-harness/docs/subsystems/worktrees.md](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/subsystems/worktrees.md#L5-L17)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 5–17。

文件 SHA256：`996b9a2774edfa087324fc62a0b5711774ee22a495f9a112692fb60a84f79012`。


<a id="e06"></a>

## E06：技能/工具映射/bootstrap与真实会话验收

来源：[obra/superpowers/docs/porting-to-a-new-harness.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/docs/porting-to-a-new-harness.md#L30-L157)；固定提交 `22f0b463e7a5e579904dd6211a520321035526f7`；行 30–157。

文件 SHA256：`562a1436134babc815c11adf0379e2df00c8de0e73c362291faf495448b94f3e`。


<a id="e07"></a>

## E07：pi请求context注入不写session历史

来源：[obra/superpowers/.pi/extensions/superpowers.ts](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/.pi/extensions/superpowers.ts#L19-L51)；固定提交 `22f0b463e7a5e579904dd6211a520321035526f7`；行 19–51。

文件 SHA256：`59774512277ffb41b706f6ed376b27fda83c3a04045a41560f4a2307591e3939`。


<a id="e08"></a>

## E08：fresh tasks、task审查、最终审查及流程

来源：[obra/superpowers/skills/subagent-driven-development/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development/SKILL.md#L1-L75)；固定提交 `22f0b463e7a5e579904dd6211a520321035526f7`；行 1–75。

文件 SHA256：`1baf70e307bde682c462513c86116333f1f066168c6710f45145bf5f0b00828d`。


<a id="e09"></a>

## E09：测试证据先于完成声明

来源：[obra/superpowers/skills/verification-before-completion/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/verification-before-completion/SKILL.md#L1-L54)；固定提交 `22f0b463e7a5e579904dd6211a520321035526f7`；行 1–54。

文件 SHA256：`2befe7fc55bcadaa3d97dd9e8efeb633d2561c0ebe74c5a8b17c4d9e7e4520b3`。


<a id="e10"></a>

## E10：真实workflow能力/取消/后台job适用范围

来源：[deepseek-ai/deepseek-harness/packages/workflow/tool-workflow/README.md](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/workflow/tool-workflow/README.md#L10-L78)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 10–78。

文件 SHA256：`5f83153bbd4b329bcf91d97efd560f30df80f6f9967c87e347787dc3dd2644d5`。


<a id="e11"></a>

## E11：技能发现与来源优先级

来源：[GuoLai806/gcode/gcode/skills/loader.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/skills/loader.py#L1-L142)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 1–142。

文件 SHA256：`d2bd2e448ba2d007c89566bd9ea1e50abe658943a025c7d4918646f8712004fc`。

<a id="e12"></a>

## E12：execution_context和权限决策；无checker时final allow

来源：[GuoLai806/gcode/gcode/agent.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/agent.py#L440-L490)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 440–490。

文件 SHA256：`2e6264593d04bd50aec9ce6d48f0917a6b8d819e3cf0b435336492656aed8e10`。

<a id="e13"></a>

## E13：skill-fork另建Agent(checker=None)、共享工具对象、full截断

来源：[GuoLai806/gcode/gcode/skills/executor.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/skills/executor.py#L21-L153)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 21–153。

文件 SHA256：`1e1d30c42b2d0cdbde4f3386e43bea2f6403a1631c0502ff2b106a1ef6a7367e`。

<a id="e14"></a>

## E14：LoadSkill绑定实例、pin正文、动态工具和仅确认返回

来源：[GuoLai806/gcode/gcode/tools/load_skill.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/tools/load_skill.py#L19-L72)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 19–72。

文件 SHA256：`45661cd170597ed5bdebe5761a460992b3c3075019a53ecc145caec4a9625890`。

<a id="e15"></a>

## E15：普通child继承权限/预算/工具clone/rebind/hooks且parent无policy拒绝

来源：[GuoLai806/gcode/gcode/tools/agent_tool.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/tools/agent_tool.py#L118-L242)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 118–242。

文件 SHA256：`7e798edf030de0e5ceef0148384dbe9808588ee94eb9fd7faa5b31809b7c0d7e`。

<a id="e16"></a>

## E16：RecoveryState记录技能/文件

来源：[GuoLai806/gcode/gcode/context/manager.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/context/manager.py#L634-L666)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 634–666。

文件 SHA256：`eeab6dc62be4dab1ce167828c47b8fe3d8c027186c8624aca696c19c32d04bee`。

<a id="e17"></a>

## E17：owner、reviewed cleanup、未知/dirty保护

来源：[GuoLai806/gcode/gcode/worktree/manager.py](https://github.com/GuoLai806/gcode/blob/e480127bc1590efadf505aca4a71f86ed95f6742/gcode/worktree/manager.py#L458-L564)；固定提交 `e480127bc1590efadf505aca4a71f86ed95f6742`；行 458–564。

文件 SHA256：`2dab220d35cb43683e46bbe2521488d521afa3e06435e852aeeead9d8d1d8b09`。

<a id="e18"></a>

## E18：官方同步SDK config/RunResult；不代表GCode桥接完成

来源：[deepseek-ai/deepseek-harness/python/sdk/src/deepseek_harness/api.py](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/python/sdk/src/deepseek_harness/api.py#L13-L54)；固定提交 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；行 13–54。

文件 SHA256：`9c772909775196fc4070182191738ad227a3bfdccc68d1b6f4e8b90dec08430b`。


## 读取和检验边界

SuperAgent已取43份官方文本（README、package、docs、core、executor、runtime、store/effects/session、代表测试），完整树和来源身份也保存。搜索Council/Tape/Planner只覆盖已取文本，不把阴性搜索外推为未经检查文件的完整审计。主架构已通过core/ports/model/engine/executor的正向证据查明。

原型测试源码包含fake host/session/CLI和MemoryRepositories；本轮没有执行Vitest、模型任务、服务或安装。原型README兼容/测试声明与作者内部效果不计为本次实测。

Superpowers/社区移植仅作名称区别，社区README运行/兼容性宣称均未复现。官方DSH固定提交不等于SuperAgent已在该依赖版本验收。

GCode输入为主任务已固定的本地研究快照，文件哈希留存；本子任务没有操作Git或改业务源码。远端文档推送核实由主Agent负责。

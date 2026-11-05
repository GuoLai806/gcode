# 用户字面 XML 与来源边界：限定补查

## 最新补查：旧摘要前缀

在当前 `constraints.py` SHA-256 `7cbbeae7584ee3be240d29b9c772db8d986ab15916934d11f0a73c96dbb21fdb`，旧摘要前缀过滤仅作用于非明确 user 来源。独立合成中英文前缀测试确认：`origin=user` 的原文保留，`origin=''` 的旧来源与 `origin=runtime` 内容不提升为用户约束；见 `legacy-prefix-proof.json`。`tests/test_constraint_ledger.py` 13 项通过，pytest exit=0，`legacy-prefix-before.sha256` 和 `legacy-prefix-after.sha256` 一致；未调用云端或 GUI。本次限定条件未发现可复现的新缺陷。

以下是上一轮 XML 检查的历史快照，其源码 hash 和测试结果不应混同为本轮测试。

范围只包括用户 XML 原文保留和 runtime/tool/system 来源过滤；本次未修改源码，也未调用云端、GUI 或 native。测试时 `constraints.py` SHA-256 为 `b463c0c4c5e8d994182e1c4e6d649ee2670668f54dcc459e559528c141eaf395`，独立合成 compaction 期间 `manager.py` 为 `eeab6dc62be4dab1ce167828c47b8fe3d8c027186c8624aca696c19c32d04bee`，各自前后相同。

**在本次限定路径中未发现可复现的新缺陷。** 四类标签 `INSTRUCTIONS`、`runtime`、`environment`、`tool_result` 在明确 `origin=user` 时，经 session record 往返和合成 compaction 均保留原文。普通 `origin=runtime`、`origin=reminder`、assistant 文本和 tool-result 文本在上述 compaction 中均没有进入用户约束 ledger。详见 `user-xml-provenance-proof.json` 和 `user-xml-compaction-proof.json`。

`user-xml-tests.xml` 和对应日志记录约束、checkpoint 和 session 恢复相关测试 **26 项通过、pytest exit=0**；测试前后 `constraints.py`、`conversation.py`、`memory/session.py` 三份 hash 一致。

边界：`origin=''` 的历史消息来源有歧义，仍采用保守标签剥离策略，不能据此保证旧版匿名用户 XML 原文全部恢复。`preserved_constraints` 是受信的内部运行时/磁盘会话元数据：直接构造并伪造这个字段，即使附在 runtime origin 消息上也会被当作既有 ledger 合并；本次未发现普通工具或 provider 文本可直接设置该字段的路径，也没有把合成伪造内部字段当成已证实的外部注入缺陷。本机 owner 或会话文件被恶意篡改不在此次检查范围。上述检查不代替真实云模型或完整产品验收。

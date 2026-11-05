# 摘要修复补充评审

范围仅为 `gcode/context/manager.py` 的外层摘要解析和摘要请求构造，测试期间 SHA-256 为 `eeab6dc62be4dab1ce167828c47b8fe3d8c027186c8624aca696c19c32d04bee`，前后相同。本次未修改 GCode，未调用云模型或 GUI。

本次限定范围内未发现可复现的新缺陷。独立合成 provider 检查确认：带字面 `<summary>` / `</summary>` 的用户原文可留在摘要中；两个相邻独立摘要块被拒绝；真实发送给 provider 的 synthetic request 将 `SUMMARY_PROMPT` 仅作为 system 内容，历史用户消息中没有重复的完整 system prompt，末尾恰有一条包含九节模板的摘要控制请求。压缩后通过遍历全部消息确认原用户约束、字面标签和文件标记仍在；没有假设第一条消息必然是摘要。证据为 `summary-inline-review.json`。

既有复现重新运行：无标签拒绝和缺少必需节的摘要均不提交，原历史保持；符合九节结构的摘要可提交且保留约束。对应 `summary-invalid-proof-eeab.json`、`summary-missing-sections-proof-eeab.json`、`summary-valid-proof-eeab.json`。`summary-eeab-tests.xml` 记录 71 项定向测试通过，pytest exit=0，`summary-eeab-before.sha256` 和 `summary-eeab-after.sha256` 一致。

这些证据只覆盖本次合成输入和局部协议；结构检查不等于摘要语义完整，也不单凭此报告确认其他 agent 的真实云调用、token 用量或全套回归结果。

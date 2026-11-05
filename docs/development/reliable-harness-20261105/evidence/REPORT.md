# GCode 独立候选评审

评审基线 `221c870f8cc0872e6704a0140f1dd9923ac66a5c`，对象为其上的未提交工作区；精确源码身份见 `sources-reviewed-before.sha256`。该文件与 `sources-reviewed-after.sha256` 完全相同。评审者未编辑 GCode 源码，复现只使用临时文件、合成 provider 和自有假 Node 进程，没有操作真实 GUI/native、付费模型或外部业务。

## 需求符合性

**在本次核对范围内，最终快照没有剩余可复现的审查缺陷。** 之前发现并交付修复的摘要缺陷已复测：缺失 `<summary>` 或缺少九个有序非空节的摘要均不提交；符合结构的合成摘要能提交，用户自然语言约束仍保留。`summary-invalid-proof-final.json`、`summary-missing-sections-proof-after.json` 和 `summary-valid-proof.json` 分别保留证据。摘要结构正确不证明语义一定完整，用户原文 ledger 也不是完整事件史或新授权。

真实 `/session resume` 的合成复现中，首次和二次恢复均保留未知动作 fence，拒绝写入；ACK 通知和随后更晚的 JSONL 用户消息同时恢复。相同 tool_call_id 在已知成功和未知写入场景均未重放外部副作用，未知时最终 stop_reason 为 `delivery_unknown`。证据为 `checkpoint-proof-final.json`、`session-command-proof-final.json`、`mailbox-proof-final.json` 和 `tool-retry-proof-final.json`。

## 代码质量与安全

原 `Bash(*) deny` 被 awk 安全前缀绕过的复现，在最终 checker/dangerous hash 下已被拒绝且临时哨兵未创建（`permission-safe-prefix-proof-final.json`）。CU 未知投递后的 shutdown 在合成忽略 SIGTERM 的 sidecar 及其同组假子进程场景下有界结束，未知投递状态仍保留（`cu-descendant-proof-final.json`）。没有实际控制设备，也不能据此推断真实 native/OS 应用已停止或任务成功。

`targeted-reviewed.xml` / `targeted-reviewed.log` 记录 268 项通过、pytest exit=0；指定源码测试前后 hash 一致。覆盖上下文、checkpoint、session 恢复、tool ledger、constraints、token budget、子任务、权限、运行状态、CU bootstrap/transport 与 desktop tool 的离线/替身路径。

## 证据边界

测试通过和未发现其他缺陷不等于完整产品验收。真实 provider 请求、未知动作的人工核对、不同平台、真实 native CU、桌面物理动作与用户最终验收均不在上述测试内。当前 token budget 是已观测用量控制，不是并发在途请求的硬上限；摘要结构校验不能证明语义正确；过期 claim 保持未知且不盲目重放。明确这些边界后，由主 agent 集成并继续所需验收。

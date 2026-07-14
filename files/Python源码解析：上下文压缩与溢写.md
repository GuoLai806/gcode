走读 GCode 的上下文管理代码，看「工具结果预算（Layer 1）」和「摘要旧消息、保留近期原文（Layer 2）」这两层压缩怎么实现。

## 模块概览

把两层压缩的所有逻辑集中在一个文件里： `gcode/context/manager.py` 。 Layer 1 的决策冻结、存盘，Layer 2 的阈值计算、摘要生成、恢复块，全在这一个文件中。 `__init__.py` 负责统一导出。

| 文件                    | 职责                                 |
| --------------------- | ---------------------------------- |
| `context/manager.py`  | 全部两层逻辑：决策冻结、预算处理、阈值计算、摘要生成、恢复块、熔断器 |
| `context/__init__.py` | 统一导出所有公开类和函数                       |

辅助模块方面，连续 user 消息的合并放在 `gcode/serialization.py` 的 `build_messages` 函数里。会话持久化（compact boundary）的写入由 auto\_compact 返回 `CompactEvent` ，session 层拿到后自行写盘，manager.py 本身不碰 session 文件。

把所有逻辑平铺在一个模块里，不做目录拆分。好处是不用跨文件找类型定义，坏处是文件会越来越长。

## 核心常量

### Layer 1 常量

```python
SINGLE_RESULT_CHAR_LIMIT = 50_000
AGGREGATE_CHAR_LIMIT     = 200_000

两个常量的含义：50000 是单条工具结果的存盘阈值，200000 是聚合上限。不做基于轮次的过期裁剪——一旦决策冻结，tool result 内容在后续轮次中保持不变，保证 Prompt Cache 前缀稳定。
```

### Layer 2 常量

```python
SUMMARY_OUTPUT_RESERVE      = 20_000
AUTO_COMPACT_SAFETY_MARGIN  = 13_000
MANUAL_COMPACT_SAFETY_MARGIN = 3_000
KEEP_RECENT_TOKENS = 10_000
MIN_KEEP_MESSAGES  = 5
KEEP_MAX_TOKENS    = 40_000
```

阈值公式一样：有效窗口 = 上下文窗口 - 20000，自动触发线 = 有效窗口 - 13000。尾部保留预算 10000 tokens / 5 条消息 / 上限 40000。

额外定义了一个 `MIN_SUMMARIZE_PREFIX_TOKENS = 2000` ：如果待摘要的前缀太短（估算 token 不到 2000），压缩往返的开销比回收的空间还大，直接跳过。

## 核心类型

### ContentReplacementState（决策冻结）

```python
@dataclass
class ContentReplacementState:
    seen_ids: set[str] = field(default_factory=set)
    replacements: dict[str, str] = field(default_factory=dict)
```

用 dataclass 实现，结构极简。 `seen_ids` 是所有见过的 tool\_use\_id 集合， `replacements` 是被替换的 id 到 preview 字符串的映射。

冻结语义：一旦某个 id 进了 `seen_ids` ，决策永远不变。被决定不替换的永远保留原文，被决定替换的永远重放同一个 preview。目的是保持对话前缀逐字节稳定，让 Prompt Cache 持续命中。

`clone_replacement_state` 做浅拷贝： `set(src.seen_ids)` 和 `dict(src.replacements)` 创建独立副本，用于 fork 子 Agent。

### UsageAnchor（Token 锚点）

没有独立的 UsageAnchor 类型。它把锚定信息直接存在 `ConversationManager` 的三个字段上： `baseline_tokens` 、 `anchor_count` 、 `last_input_tokens` 。 `current_tokens()` 方法封装了锚定 + 增量的逻辑。

锚定机制和独立传入 anchor 参数的方式效果一样：有真实 API 用量时用精确基准加增量估算，没有时全量估算。

## 第一层：工具结果预算

### 入口函数

```python
def apply_tool_result_budget(
    conversation: ConversationManager,
    session_dir: Path,
    state: ContentReplacementState,
) -> tuple[ConversationManager, list[ContentReplacementRecord]]:
```

接收原始对话和 state，返回一个新的 `ConversationManager` 。原始 conversation 不被修改。state 的 seen\_ids 和 replacements 会被就地更新。

### Pass 1：单条溢写

先分三类：replacements 里有的用缓存 preview 重放；seen\_ids 里有的保留原文；以 `<persisted-output>` 开头的（外部已打标签）冻结为已替换；剩下的收集为 fresh 候选。

新候选中超过 50000 字符的调用 `persist_tool_result` 存盘：

```python
def persist_tool_result(tool_use_id: str, content: str, session_dir: Path) -> Path:
    file_path = session_dir / f"{tool_use_id}.txt"
    try:
        fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except FileExistsError:
        pass
    return file_path
```

用 `os.O_EXCL` 独占创建，保证只有一个进程能创建成功。文件已存在时捕获 `FileExistsError` 直接返回路径。文件名是 `{tool_use_id}.txt` 。

存盘后生成预览：

```python
def make_persisted_preview(content: str, file_path: Path) -> str:
    size_kb = len(content.encode("utf-8")) // 1024
    preview = content[:PREVIEW_CHARS]
    return (
        f"{PERSISTED_TAG}\n"
        f"输出太大（{size_kb}KB），完整内容已保存到：\n{file_path}\n\n"
        f"预览（前 2KB）：\n{preview}\n</persisted-output>"
    )
```

格式是 `<persisted-output>` 标签包裹，包含大小、路径、前 2KB 内容。注意 用 `len(content.encode("utf-8"))` 计算字节数而不是字符数，对中文内容会有差异，但对大部分 Agent 场景（代码、命令输出）影响不大。

### Pass 2：聚合溢写

Pass 1 没动的新候选收集起来，算总字符数。超过 200000 就按大小降序排，从最大的开始存盘。

```python
if total > AGGREGATE_CHAR_LIMIT:
    ranked = sorted(remaining, key=lambda tr: len(tr.content), reverse=True)
    for tr in ranked:
        if total <= AGGREGATE_CHAR_LIMIT:
            break
        fp = persist_tool_result(tr.tool_use_id, tr.content, session_dir)
        preview = make_persisted_preview(tr.content, fp)
        total -= old_len - len(preview)
```

`sorted` 加 lambda 写法很简洁。

### 原子写入

`persist_tool_result` 已经在 Pass 1 里贴过了。核心就是 `os.O_EXCL` 独占创建，捕获 `FileExistsError` 实现幂等。文件名用 tool\_use\_id，天然幂等。

## 第二层：摘要旧消息、保留近期原文（Auto-Compact）

### 阈值计算

```python
def compute_compact_threshold(context_window: int, manual: bool = False) -> int:
    effective = context_window - SUMMARY_OUTPUT_RESERVE
    margin = MANUAL_COMPACT_SAFETY_MARGIN if manual else AUTO_COMPACT_SAFETY_MARGIN
    return effective - margin
```

公式一样。200K 窗口下自动触发线 167000，手动 177000。

阈值函数没有 `maxOutput` 参数，直接用固定的 `SUMMARY_OUTPUT_RESERVE` ，简化了一步。

### Token 估算：锚定 + 增量

把锚定逻辑封装在 `ConversationManager.current_tokens()` 方法里。有 `baseline_tokens` 和 `anchor_count` 时用锚定值加增量估算；冷启动或刚压缩清空锚点后，退化为整个 history 的全量字符估算。

### ManageContext 入口：软硬双阈值 + 熔断

```python
async def auto_compact(
    conversation, client, context_window, session_dir,
    protocol="anthropic", manual=False, breaker=None,
    recovery=None, tool_schemas=None, transcript_path="",
) -> CompactEvent | str | None:
    threshold = compute_compact_threshold(context_window, manual=manual)
    current = conversation.current_tokens()
    if not manual and current < threshold:
        return None
    if not manual and breaker is not None and breaker.is_open():
        return "自动压缩已熔断（连续失败 3 次），请手动处理或使用 /compact"
```

入口是 `auto_compact` ，是一个 async 函数。它只检查一条阈值线，超了就尝试压缩；熔断器拦住的情况下返回提示字符串。没有区分软阈值和硬阈值两条线。

手动模式（ `manual=True` ）跳过阈值检查和熔断器，直接压缩。

### 拆分前缀与尾部

```python
def _compute_keep_start_index(messages: list[Message]) -> int:
    kept_tokens, kept_count, keep_start = 0, 0, n
    for i in range(n - 1, -1, -1):
        tok = _message_tokens(messages[i])
        if kept_count > 0 and kept_tokens + tok > KEEP_MAX_TOKENS:
            break
        kept_tokens += tok
        kept_count += 1
        keep_start = i
        if kept_tokens >= KEEP_RECENT_TOKENS or kept_count >= MIN_KEEP_MESSAGES:
            break
    return _align_keep_start_to_tool_pair(messages, keep_start)
```

从尾部往回走，累积 token 数。满足 10000 tokens 或 5 条消息任一条件就停，上限 40000 tokens。

把配对保护逻辑抽成了独立函数 `_align_keep_start_to_tool_pair` ：

```python
def _align_keep_start_to_tool_pair(messages, keep_start):
    while 0 < keep_start < len(messages):
        msg = messages[keep_start]
        if msg.role == "user" and msg.tool_results:
            prev = messages[keep_start - 1]
            if prev.role == "assistant" and prev.tool_uses:
                keep_start -= 1
                continue
        break
    return keep_start
```

如果切割点落在 tool\_result 上，往前退到对应的 tool\_use，保证配对完整。拆成独立函数让逻辑更清晰。

Python 还额外加了一个 `_prefix_too_small_to_compact` 检查：如果待摘要的前缀估算 token 不到 2000，认为不值得做摘要直接返回 None。

### 摘要生成

Prompt 是中文的，结构更明确：

```python
SUMMARY_PROMPT = """\
你是一个对话摘要助手。你只能输出纯文本，不能调用任何工具。
请对下面的对话生成一份结构化摘要。
先在 <analysis> 标签中梳理对话中发生了什么（这部分会被丢弃），
然后在 <summary> 标签中输出正式摘要。
<summary> 必须包含以下 9 个部分：...
提醒：不要调用任何工具。工具调用会被拒绝，你会失败。"""
```

9 个部分和理论篇一致：主要请求、关键技术、文件代码、错误修复、解决过程、用户消息、待办任务、当前工作、下一步。

注意 Prompt 开头和结尾两次明确禁止工具调用（「你只能输出纯文本」和「提醒：不要调用任何工具」），两头堵。

还实现了 PTL（Prompt Too Long）重试逻辑：如果摘要请求本身太大，按轮次分组丢弃最旧的 20%，最多重试 3 次：

```python
groups = _group_messages_by_turn(summary_conv.history[1:-1])
drop_count = max(1, len(groups) // 5)
remaining = groups[drop_count:]
```

### 对话重建

```python
new_messages = build_compact_messages(
    summary, attachment=attachment,
    has_keep_tail=bool(keep_tail),
    transcript_path=transcript_path,
)
new_messages = new_messages + list(keep_tail)
conversation.replace_history(new_messages)
```

压缩后的结构：一条 user 消息（摘要 + 近期消息提示 + 会话记录路径 + 恢复块）加上保留的尾部原文。没有 assistant 确认消息。

`replace_history` 替换 history 的同时会清零 `baseline_tokens` 、 `anchor_count` 、 `last_input_tokens` ，因为旧的锚点对应压缩前的消息列表，已经没意义了。下次 API 响应会重新锚定。

### 恢复块（Recovery Attachment）

```python
def build_recovery_attachment(
    state: RecoveryState | None,
    tool_schemas: list[Mapping[str, Any]] | None,
) -> str:
```

三部分：最近读过的文件（最多 5 个，每个 5000 tokens）、已激活的技能（总预算 25000 tokens）、可用工具列表。末尾附加提示段落让模型不要根据摘要猜测代码细节。

标题和提示信息都用中文（「最近读过的文件」「已激活的技能」「可用工具」「内容已截断」），更贴近中文用户体验。

`RecoveryState` 用 `threading.Lock()` 保护并发访问。文件记录按 path 去重，Skill 按 name 去重，都只保留最新的快照。

恢复块和保留的尾部原文是两件不同的事。恢复块是压缩前的关键上下文重新附加回来，尾部原文是近期对话的原始内容。

### 返回值设计

`auto_compact` 返回一个 `CompactEvent` 对象，其中包含 `CompactBoundary` （摘要 + keep tail）。session 层拿到这个 boundary 自行写盘。

```python
@dataclass
class CompactBoundary:
    summary: str
    keep: list[Message]
```

把写操作解耦出去，让 auto\_compact 保持纯粹、不依赖 session。

## 连续 User 消息合并

合并逻辑在 `gcode/serialization.py` 的 `build_messages` 函数里：

```python
if (
    m.role == "user"
    and result
    and result[-1]["role"] == "user"
    and isinstance(result[-1]["content"], str)
):
    result[-1]["content"] = result[-1]["content"] + "\n" + m.content
```

Anthropic API 要求 user/assistant 严格交替。压缩后摘要（user）和 keep tail 的首条消息（可能也是 user）会相邻，这段逻辑把它们合并。合并条件：前一条也是 user，且 content 是字符串（不是 tool\_result 的 list 格式）。只合并纯文本 user 消息。

## 被动自愈：紧急压缩

紧急压缩在 Agent Loop 里，检测到上下文超长时直接调用 `auto_compact` 并传入 `manual=True` ：

```python
compact_result = await auto_compact(
    conversation, self.client, self.context_window,
    self.session_dir, protocol=self.protocol,
    breaker=self.compact_breaker,
    recovery=self.recovery_state,
    tool_schemas=self.registry.get_all_schemas(self.protocol),
    transcript_path=self._transcript_path,
)
```

`manual=True` 跳过阈值检查和熔断器，相当于 ForceCompact。压缩成功后 `replace_history` 已经清零了锚点，下一轮会重新估算。

自动压缩是预防，紧急压缩是治疗。

## 会话边界持久化

`auto_compact` 返回 `CompactEvent` ，其中 `boundary` 字段携带摘要和 keep tail。session 层收到后自行追加 compact\_boundary 记录到 JSONL 文件。

Resume 时找到最后一条 boundary，从它开始重建对话。

这种设计让 context 模块不依赖 session 模块，解耦更干净。

## 小结

| 设计决策     | Python 实现方式                                                         |
| -------- | ------------------------------------------------------------------- |
| 两层架构     | 全部平铺在 context/manager.py 一个文件里                                      |
| 决策冻结     | ContentReplacementState dataclass，seen\_ids set + replacements dict |
| 溢写原子性    | os.O\_EXCL 独占创建，捕获 FileExistsError                                  |
| 阈值公式     | effectiveWindow - safetyMargin，固定值                                  |
| Token 估算 | ConversationManager.current\_tokens() 封装锚定增量                        |
| 对话重建     | build\_compact\_messages + replace\_history，清零锚点                    |
| 连续消息合并   | serialization.py 合并连续纯文本 user 消息                                    |
| 边界持久化    | 返回 CompactBoundary 让 session 层自行写盘（解耦）                              |


走读 GCode 的记忆系统代码，看三类长期记忆（项目指令、会话持久化、自动记忆）是怎么在文件系统上实现的。

## 模块概览

记忆系统的代码集中在 `gcode/memory/` 目录下，四个模块各管一块。会话持久化和自动记忆放在同一个目录里。输入历史放在 `gcode/filehistory/` 下（这个模块实际上是文件快照历史，不是输入历史，没有独立的 prompt history）。

| 文件                       | 职责                                                   |
| ------------------------ | ---------------------------------------------------- |
| `memory/__init__.py`     | 导出汇总                                                 |
| `memory/instructions.py` | 项目指令加载、@include 展开                                   |
| `memory/session.py`      | 会话持久化：Record/Message 转换、消息链校验、Session/SessionManager |
| `memory/auto_memory.py`  | 自动记忆管理：加载、提取、注入、双路径分流                                |
| `memory/recall.py`       | 记忆召回：扫描、manifest、LLM 选择器、过期保护                        |
| `filehistory/history.py` | 文件快照历史（非 prompt history）                             |

## 核心类型

### SessionRecord

```python
class RecordType(str, Enum):
    SYSTEM_PROMPT = "system_prompt"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"
    COMPRESSION = "compression"
    COMPACT_BOUNDARY = "compact_boundary"
```

RecordType 枚举有六种类型。除了常规的 user/assistant/tool\_result，还有 system\_prompt（系统提示）、compression（旧版压缩标记）和 compact\_boundary（新版压缩边界）。

```python
@dataclass
class SessionRecord:
    type: RecordType
    content: Any
    timestamp: datetime
    tool_use_id: str | None = None
    is_error: bool = False
```

SessionRecord 的字段设计很完整。 `tool_use_id` 字段在 tool\_result 类型时有值，用于和对应的工具调用配对。 `is_error` 标记工具执行是否出错。 `content` 用 `Any` 类型，可以是纯字符串也可以是 content blocks 列表。

这个设计直接支撑了消息链校验。有了 tool\_use\_id，恢复时就能追踪每个工具调用是否有对应的结果。

### SessionMeta

```python
@dataclass
class SessionMeta:
    id: str
    title: str = ""
    summary: str = ""
    message_count: int = 0
    total_tokens: int = 0
    created_at: datetime = field(default_factory=...)
    last_active: datetime = field(default_factory=...)
```

有独立的 `.meta` 文件存储元数据。元数据和 JSONL 分开存储。好处是列表展示时只需要读 `.meta` 文件就够了，不用扫描整个 JSONL。 `save()` 方法把元数据序列化成 JSON 写到 `<session_id>.meta` ， `load()` 反序列化回来。

### MemoryHeader（召回用）

```python
@dataclass
class MemoryHeader:
    filename: str
    file_path: str
    scope: str
    mtime_ms: int
    description: str
    type: str
```

扫描记忆目录时产出的元数据，用于召回选择器。

## 第一层记忆：项目指令

### 加载路径与优先级栈

```python
def load_instructions(project_root: str) -> str:
    root = Path(project_root)
    home = Path.home()
    paths = [
        root / "GCODE.md",
        root / ".gcode" / "GCODE.md",
        home / ".gcode" / "GCODE.md",
    ]
    sections: list[str] = []
    for path in paths:
        if path.exists() and path.is_file():
            content = path.read_text(encoding="utf-8")
            processed = process_includes(content, path.parent, root)
            sections.append(processed)
    return "\n---\n".join(sections)
```

三个候选路径：项目根目录、项目 `.gcode/` 目录、用户全局目录。全部扫描，存在就读取，用 `---` 分隔线拼接。策略是「全部拼接」而不是「找到即返回」。

优先级顺序是先加载项目级再加载用户级。多层级内容全部保留，靠位置让 LLM 关注高优先级部分。

没有 git root 逐层扫描和 `AGENTS.md` 支持。

### @include 递归展开

```python
def process_includes(content, base_dir, project_root, depth=0):
    if depth >= MAX_INCLUDE_DEPTH:
        return content
    for line in lines:
        if not stripped.startswith(INCLUDE_PREFIX):
            result.append(line)
            continue
        rel_path = stripped[len(INCLUDE_PREFIX):].strip()
        abs_path = (base_dir / rel_path).resolve()
        try:
            abs_path.relative_to(resolved_root)  # 路径越界检查
        except ValueError:
            result.append("<!-- @include blocked: path outside project -->")
            continue
```

用 `@include` 前缀（带空格）。两道安全防线完整： `MAX_INCLUDE_DEPTH = 5` 防递归太深， `abs_path.relative_to(resolved_root)` 做路径越界检查。

路径越界检查：如果 @include 的路径解析后不在项目根目录内，就插入一条 HTML 注释标记并跳过，防止读取系统文件。

没有循环引用防护（没有 visited/seen 集合），依靠深度限制兜底。也没有代码块内 @include 的跳过处理。

## 第二层记忆：会话持久化

### JSONL 格式选择

选 JSONL 格式：追加写入 O(1)、崩溃安全、增量恢复。序列化方法在 `SessionRecord.to_jsonl()` 里：

```python
def to_jsonl(self) -> str:
    data: dict[str, Any] = {
        "type": self.type.value,
        "content": self.content,
        "timestamp": self.timestamp.isoformat(),
    }
    if self.tool_use_id is not None:
        data["tool_use_id"] = self.tool_use_id
    if self.type == RecordType.TOOL_RESULT:
        data["is_error"] = self.is_error
    return json.dumps(data, ensure_ascii=False)
```

注意几个细节：时间戳用 ISO 格式字符串而不是 Unix 整数。 `ensure_ascii=False` 保证中文内容不被转义。tool\_use\_id 只在有值时才写入，is\_error 只在 tool\_result 时才写入。

### 消息写入

```python
class Session:
    def append(self, message: Message) -> None:
        records = SessionRecord.from_message(message)
        for record in records:
            self._file.write(record.to_jsonl() + "\n")
        self._file.flush()
        self.meta.message_count += 1
        self.meta.last_active = datetime.now(timezone.utc)
        if not self.meta.title and message.role == "user" and message.content:
            self.meta.title = message.content[:TITLE_MAX_LENGTH]
        self.meta.save(self._sessions_dir / f"{self.session_id}.meta")
```

持有文件句柄（ `self._file` ），生命周期和 Session 对象绑定，不是每次写入都重新打开文件。每次写入后立即 `flush()` ，确保数据落盘。

先写文件再更新内存（meta），这是有意的顺序。如果写文件成功但更新 meta 前崩溃，下次恢复时从文件重建就行。

标题自动生成：取第一条 user 消息的前 50 个字符（ `TITLE_MAX_LENGTH` ）作为标题。

### Message 与 Record 的转换

一条 Message 可能变成多条 Record。 `SessionRecord.from_message` 的转换规则：

```python
@classmethod
def from_message(cls, message: Message) -> list[SessionRecord]:
    if message.tool_results:
        # 每个 tool_result 独立一条 Record（保留 tool_use_id）
        for tr in message.tool_results:
            records.append(cls(type=RecordType.TOOL_RESULT,
                content=tr.content, tool_use_id=tr.tool_use_id,
                is_error=tr.is_error))
    elif message.role == "assistant" and message.tool_uses:
        # 文本 + 工具调用打包成 content blocks 数组
        content_blocks = [{"type": "text", "text": message.content}]
        for tu in message.tool_uses:
            content_blocks.append({"type": "tool_use", "id": tu.tool_use_id, ...})
```

tool\_results 拆开，每个单独一条。assistant 消息里的文本和工具调用打包成 content blocks 数组。这样每个 tool\_result 都有独立的 tool\_use\_id，恢复时可以和 assistant 消息里的 tool\_use 配对。

反序列化时 `records_to_messages` 做合并。遇到连续的 TOOL\_RESULT record，用 `pending_tool_results` 缓冲区攒起来，碰到下一条非 TOOL\_RESULT 记录时一起合并成一条 Message。

### 消息链校验

```python
def validate_message_chain(records: list[SessionRecord]) -> int:
    last_valid = 0
    pending_tool_uses: set[str] = set()
    for i, record in enumerate(records):
        if record.type == RecordType.ASSISTANT and isinstance(record.content, list):
            for block in record.content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_id = block.get("id", "")
                    if tool_id:
                        pending_tool_uses.add(tool_id)
        if record.type == RecordType.TOOL_RESULT and record.tool_use_id:
            pending_tool_uses.discard(record.tool_use_id)
        if not pending_tool_uses:
            last_valid = i + 1
    return last_valid
```

这是四个语言中唯一做了消息链校验的。逻辑清晰：维护一个 `pending_tool_uses` 集合，遇到 assistant 消息里的 tool\_use 就把 id 加进去，遇到 tool\_result 就移除。集合为空时记录 `last_valid` 位置。最后截断到 last\_valid，把不完整的尾部丢弃。

### 会话恢复

```python
def resume(self, session_id: str) -> ResumeResult | None:
    # 1. 逐行解析 JSONL，跳过坏行
    records = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            record = SessionRecord.from_jsonl(line.strip())
            if record is not None:
                records.append(record)
    # 2. 找最后一个 compact_boundary，只恢复其后内容
    if last_boundary >= 0:
        records = records[last_boundary:]
    # 3. 消息链校验，截断不完整尾部
    records = records[:validate_message_chain(records)]
    # 4. record 转 message
    messages = records_to_messages(records)
```

恢复流程四步走：逐行解析 JSONL（跳过坏行）、找最后一个 compact\_boundary（只恢复其后内容）、消息链校验（截断不完整尾部）、record 转 message（合并 tool\_results、展开压缩边界）。

压缩边界的处理用 `parse_compact_boundary` ，从 boundary record 里提取 summary 和 keep 尾部。keep 里的 record 会被递归转成 Message，保证 tool\_use 和 tool\_result 的关联关系不丢失。

### 会话管理器

```python
def _generate_session_id() -> str:
    now = datetime.now()
    suffix = "".join(random.choices(
        string.ascii_lowercase + string.digits, k=4))
    return f"session_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}"
```

会话 ID 格式 `session_YYYYMMDD_HHMMSS_xxxx` ，带 `session_` 前缀和 4 位字母数字随机后缀（字母 + 数字共 36 个字符），同秒冲突概率很低。

`list()` 只扫描 `.meta` 文件就够了，不需要打开 JSONL。这是元数据分离的好处：列表页展示快。按 `last_active` 倒序排列。

`cleanup()` 实现了过期清理：

```python
def cleanup(self, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    removed = 0
    for meta_path in list(self._sessions_dir.glob("*.meta")):
        meta = SessionMeta.load(meta_path)
        if meta is not None and meta.last_active < cutoff:
            self.delete(meta.id)
            removed += 1
    return removed
```

超过 30 天未活跃的会话自动删除。

## 第三层记忆：自动记忆

### 存储结构

用 集中式 `memories.md` 文件（不是独立 .md 文件 + 索引的方案）。两个路径：

用户级： `~/.gcode/memories.md` （存用户偏好和纠正反馈） 项目级： `<project>/.gcode/memories.md` （存项目知识和参考资料）

内容就是 Markdown 文本，按 `### 用户偏好` 、 `### 纠正反馈` 、 `### 项目知识` 、 `### 参考资料` 四个标题分段，每条记忆用 `-` 列表项格式。

注意这里的分类标题是中文的（「用户偏好」「纠正反馈」等），提取 prompt 也是全中文的。

同时 在 `recall.py` 里也实现了 MemoryHeader + MemoryScanner 体系（扫描 `.gcode/memory/` 目录下的 .md 文件），供记忆召回使用。两套体系并存：自动提取写 `memories.md` ，召回可以扫描独立 .md 文件。

### 提取时机与触发

用 消息计数做触发判断。 `_last_extraction_msg_count` 记录上次提取时的消息数，下次提取时只处理之后新增的消息。调用方决定什么时候触发提取，没有内置的间隔策略。

提取是异步的（ `async def extract` ），但没有合并策略（没有 inProgress + pendingContext 机制）。

### 提取 prompt 与 LLM 调用

```python
MEMORY_EXTRACTION_PROMPT = """\
你是一个记忆提取助手。分析下面的对话，提取值得长期记忆的信息，更新 memories.md。

分类规则：
- **用户偏好**：用户的编码习惯和风格要求
- **纠正反馈**：用户明确指出的错误和正确做法
- **项目知识**：当前项目的具体技术信息
- **参考资料**：外部链接和文档地址

规则：
1. 已有相同含义的条目不要重复添加
2. 没有值得记忆的内容，该分类下留空
3. 每条记忆用一行 `- ` 开头
4. 输出完整的 memories.md 内容，包含所有四个分类标题
"""
```

提取 prompt 全中文，要求 LLM 输出完整的 memories.md 内容。把当前已有的记忆和最近对话一起发给 LLM，让它输出更新后的完整文件。这是「全量替换」而不是「增量追加」的策略。

去重交给 LLM 处理：已有记忆清单直接放在 prompt 里，LLM 自己判断是否重复。

### 提取结果的解析与持久化

```python
def _write_memories(self, content: str) -> None:
    user_sections: list[str] = []
    project_sections: list[str] = []
    for line in content.split("\n"):
        if line.startswith("### "):
            # 切换分类...
        else:
            current_lines.append(line)
    # ...按分类分流写入
```

解析 LLM 输出时按 `### <分类>` 标题切分段落。然后按标题关键词路由：「用户偏好」和「纠正反馈」写到用户级路径，「项目知识」和「参考资料」写到项目级路径。

有一个细节： `_is_placeholder` 方法过滤掉占位内容（如 `...` 、 `无` 、 `暂无` 、 `N/A` ），防止 LLM 在空分类下生成占位符被当成记忆存下来。

未知的标题（不含四个关键词的）会被静默丢弃。

### 记忆注入

`load()` 读取两个 memories.md 文件的内容拼接起来，调用方把返回的文本注入到对话上下文中。注入方式和指令文件走同一条管线。

### 记忆召回

有完整的记忆召回实现。

```python
SelectorFn = Callable[[str, str], Awaitable[str]]

async def find_relevant_memories(
    query: str,
    user_mem_dir: Path | None,
    project_mem_dir: Path | None,
    recent_tools: list[str] | None,
    already_surfaced: set[str] | None,
    selector: SelectorFn,
) -> list[RelevantMemory]:
```

`SelectorFn` 是异步回调（ `Awaitable[str]` ）。扫描双目录用 `scan_memory_files` ，格式化 manifest，发给选择器，解析 JSON 结果。

过期保护也完整实现： `memory_freshness_text` 超过 1 天附加警告， `render_reminder` 读取记忆全文加上新鲜度标头。

## 输入历史

`filehistory/history.py` 不是 prompt 输入历史，而是文件快照历史（用于 `/rewind` 命令回退文件修改）。没有独立的 prompt history 模块。

`FileHistory` 类追踪文件编辑，每次 `track_edit` 时把文件内容备份到 `.gcode/file-history/<session_id>/` 下，用 SHA256 哈希加版本号命名。 `make_snapshot` 在每个用户消息前记录快照， `rewind` 可以回退到指定快照点。

容量上限 100 个快照（ `MAX_SNAPSHOTS` ），超过从头部淘汰。

## 小结

| 设计决策     | Python 实现方式                               |
| -------- | ----------------------------------------- |
| 指令优先级    | 项目根 → 项目 .gcode/ → 用户级，全部拼接             |
| 会话存储格式   | JSONL，持有文件句柄 + flush                      |
| 会话 ID 生成 | `session_YYYYMMDD_HHMMSS_xxxx` ，4 位字母数字后缀 |
| 消息链校验    | 完整实现（pending\_tool\_uses 集合追踪 + 截断）       |
| 记忆存储结构   | 集中式 memories.md（按 ### 分段），召回扫独立 .md       |
| 提取触发方式   | 消息计数判断，调用方决定时机                            |
| 提取合并策略   | 无合并，异步但无去重                                |
| 记忆召回     | 异步 SelectorFn，LLM 选最多 5 条                 |
| 过期保护     | memory\_freshness\_text，超 1 天附加警告         |
| 输入历史     | 无独立 prompt history，有文件快照历史                |


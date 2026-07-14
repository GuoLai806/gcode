## 模块概览

Skill 系统拆成了四个文件，各管一件事：

| 文件             | 职责                                                    |
| -------------- | ----------------------------------------------------- |
| `parser.py`    | 数据类型 SkillDef（dataclass）、frontmatter 解析、元数据校验、参数替换    |
| `loader.py`    | SkillLoader，三位置扫描（项目 → 用户 → 内置），热重载和缓存兜底              |
| `executor.py`  | SkillExecutor，inline / fork 两种执行模式，工具白名单过滤，fork 上下文构建 |
| `directory.py` | tool.json 解析、动态模块加载、SkillCustomTool 包装器               |

核心链路：解析文件 → 注册到 Loader → 执行时注入 prompt 或启动子 Agent。

## 核心类型

### SkillMeta：Skill 的元信息

```python
@dataclass
class SkillDef:
    name: str
    description: str
    prompt_body: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    mode: Literal["inline", "fork"] = "inline"
    model: str | None = None
    context: Literal["full", "recent", "none"] = "full"
    source_path: Path | None = None
    is_directory: bool = False
```

一个 dataclass 搞定 Skill 的全部信息。 `mode` 决定执行方式： `"inline"` 注入主会话， `"fork"` 启动子 Agent。 `context` 控制 fork 时传递多少上下文给子 Agent： `"full"` 传完整摘要、 `"recent"` 传最近 5 条、 `"none"` 不传。

`allowed_tools` 有双重作用：控制副作用范围（子 Agent 只能用这些工具），也控制信息可见性（看不到的工具等于不存在）。 `model` 可以为空，空的时候沿用主 Agent 的模型。

### Skill：Meta + 可执行体

`prompt_body` 是 SOP 正文，Skill 被触发时这段文本会注入对话。 `source_path` 记录文件来源路径，热重载时从这个路径重新读取。 `is_directory` 标记是否来自包含 `SKILL.md` 的子目录，目录型 Skill 可能还带着 tool.json 和 references/ 等附属资源。

名字校验也很严格：

```python
VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9\-]*$")
VALID_MODES = {"inline", "fork"}
VALID_CONTEXTS = {"full", "recent", "none"}
```

只能小写字母、数字和连字符，必须字母开头。Skill 名字会出现在 `/my-skill` 这样的命令里，允许大写或特殊字符会让用户输入很痛苦。

### SkillLoader：注册中心

```python
class SkillLoader:
    def __init__(self, work_dir: str) -> None:
        self._project_dir = Path(work_dir) / PROJECT_SKILLS_DIR
        self._user_dir = Path(USER_SKILLS_DIR).expanduser()
        self._skills: dict[str, SkillDef] = {}
        self._cache: dict[str, SkillDef] = {}
```

两个字典看着像重复，其实各有用途。 `_skills` 是当前生效的版本， `_cache` 是上一次成功加载的版本。热重载失败时用 `_cache` 做 fallback，保证已经在用的 Skill 不会因为一次手误而消失。

存储结构是普通 `dict` ，插入顺序就是遍历顺序，注入系统提示词时列表顺序保持稳定。核心方法是 `get` （返回完整 SkillDef，带热重载）和 `get_catalog` （返回所有 Skill 的 name + description 列表）。同名 Skill 后注册覆盖先注册，实现优先级。

## 主流程走读

### 第一步：多位置加载

```python
def load_all(self) -> dict[str, SkillDef]:
    seen: dict[str, SkillDef] = {}
    for skill in self._scan_directory(self._project_dir, "project"):
        if skill.name not in seen:
            seen[skill.name] = skill
    for skill in self._scan_directory(self._user_dir, "user"):
        if skill.name not in seen:
            seen[skill.name] = skill
    for skill in self._load_builtins():
        if skill.name not in seen:
            seen[skill.name] = skill
    self._skills = seen
    self._cache = {k: v for k, v in seen.items()}
    return seen
```

三个位置依次扫描：项目 → 用户 → 内置。 `if skill.name not in seen` 是先到先得策略：同名 Skill 只保留先遇到的，后来的被忽略。项目级先扫，优先级最高。

最后一行 `{k: v for k, v in seen.items()}` 做了浅拷贝。不能直接 `self._cache = seen` ，否则两个字典指向同一个对象，修改一个会连带改另一个。

容错设计贯穿始终。 `_scan_directory` 开头 `if not path.is_dir(): return []` ，目录不存在静默跳过。每个 Skill 的解析包在 `try/except SkillParseError` 里，单个文件写坏了只打 warning，不影响其他 Skill。

### 第二步：两种定义格式

支持两种 Skill 定义格式。格式一是 `skill.yaml` + `prompt.md` 分离格式：

```python
skill_yaml = entry / "skill.yaml"
if skill_yaml.is_file():
    skill = self._parse_skill_yaml(skill_yaml, entry)
    if skill is not None:
        results.append(skill)
        continue
```

`_parse_skill_yaml` 从 `skill.yaml` 读元数据，从同目录的 `prompt.md` 读 SOP 正文。如果没有 `description` ，从 prompt body 第一行非空、非标题行推断。名字也有 fallback：yaml 里没写就用目录名。

格式二是 `SKILL.md` 单文件格式，YAML frontmatter + Markdown 正文一体：

```python
def parse_frontmatter(raw: str) -> tuple[dict, str]:
    stripped = raw.lstrip()
    if not stripped.startswith("---"):
        raise SkillParseError("Missing YAML frontmatter")
    end = stripped.find("---", 3)
    if end == -1:
        raise SkillParseError("Unclosed YAML frontmatter")
    yaml_block = stripped[3:end]
    body = stripped[end + 3:].lstrip("\n")
    meta = yaml.safe_load(yaml_block)
    return meta, body
```

用 `yaml.safe_load` 而不是 `yaml.load` ，因为 `yaml.load` 允许在 YAML 里嵌入任意对象（包括执行代码），用在用户提供的文件上有安全风险。frontmatter 是严格模式：没有 `---` 开头直接报错， `name` 和 `description` 也是必填的。

### 第三步：内置 Skill 的嵌入

```python
def _load_builtins(self) -> list[SkillDef]:
    builtins_pkg = importlib.resources.files("gcode.skills.builtins")
    for resource in builtins_pkg.iterdir():
        skill_md = resource / "SKILL.md" if resource.is_dir() else None
        if skill_md is None or not skill_md.is_file():
            continue
        raw = skill_md.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        _validate_meta(meta, f"builtin:{resource.name}")
```

用 `importlib.resources.files()` 读取内置 Skill。这是包资源访问的标准方式，不管包安装在 site-packages、zip 包还是其他形式，都能正确读取，不依赖运行时的文件系统路径。

内置 Skill 放在 `gcode.skills.builtins` 包下，每个子目录一个 Skill（commit/、review/、test/ 等），子目录里有 `SKILL.md` 和可选的附属资源。

## 两种执行模式

### Inline 模式（默认）

```python
def execute_inline(self, skill: SkillDef, args: str) -> None:
    prompt = substitute_arguments(skill.prompt_body, args)
    self.agent.activate_skill(skill.name, prompt)
    if getattr(self.agent, "recovery_state", None) is not None:
        self.agent.recovery_state.record_skill_invocation(
            skill.name, prompt)
```

替换参数后，调 `agent.activate_skill` 记录激活状态（用于 `/skills` 查看和压缩恢复）。inline 不创建新 Agent 实例，SOP 通过 slash command 或 LoadSkill 的 tool\_result 进入主会话对话历史。如果 Agent 有 recovery\_state，也记录一下本次调用。

### Fork 模式

```python
async def execute_fork(self, skill: SkillDef, args: str) -> str:
    prompt = substitute_arguments(skill.prompt_body, args)
    fork_conv = ConversationManager()
    context_messages = self._build_fork_context(skill.context)
    for msg in context_messages:
        if msg.role == "user":
            fork_conv.add_user_message(msg.content)
        else:
            fork_conv.add_assistant_message(msg.content)
    fork_conv.add_user_message(prompt)
```

fork 模式创建全新的 `ConversationManager` ，先注入上下文消息，再把 Skill prompt 作为最后一条用户消息加入。接着创建过滤后的工具注册中心和独立子 Agent， `permission_checker=None` 是有意设计：主 Agent 已经过了权限审核才触发 Skill，子 Agent 的工具范围又被白名单限制住了，再加一层检查多余。

上下文传递策略分三档。 `"none"` 返回空列表，子 Agent 从零开始。 `"recent"` 取最近 5 条对话消息，过滤掉工具结果（ `not m.tool_results` ）只保留用户和 Agent 之间的对话文本。 `"full"` 不是直接搬历史，而是每条消息只保留前 200 字符，加上角色前缀拼成一段摘要，作为单条 user 消息注入子 Agent。

## 参数传递与 $ARGUMENTS 替换

```python
def substitute_arguments(prompt_body: str, args: str) -> str:
    if "$ARGUMENTS" in prompt_body:
        return prompt_body.replace("$ARGUMENTS", args)
    if args.strip():
        return prompt_body + "\n\n## User Request\n\n" + args
    return prompt_body
```

三种情况各有处理：有占位符则替换，无占位符但有参数则追加到末尾（append fallback），两者都没有则原样返回。追加模式用 `## User Request` 标题隔开，让模型能区分 SOP 正文和用户请求。这个设计在简洁性和参数不被静默忽略之间取了一个平衡。

## 工具白名单与系统工具放行

```python
def filter_tool_registry(
    registry: ToolRegistry, allowed: list[str]
) -> ToolRegistry:
    if not allowed:
        return registry
    filtered = ToolRegistry()
    for name in allowed:
        tool = registry.get(name)
        if tool is None:
            raise SkillDependencyError(
                f"Skill requires tool '{name}' but it is not registered")
        filtered.register(tool)
    # 系统工具不受白名单约束，自动放行
    for tool in registry.list_tools():
        if getattr(tool, "is_system_tool", False) \
           and filtered.get(tool.name) is None:
            filtered.register(tool)
    return filtered
```

白名单为空时直接返回原 Registry 不做限制。非空时创建新 Registry，逐个注册白名单里的工具。找不到的工具直接抛 `SkillDependencyError` ，fail-fast。

注册完白名单工具后，还有一轮系统工具的自动放行：遍历原 Registry 里所有工具，如果标记了 `is_system_tool = True` 且不在 filtered 里，自动加进去。这保证了 LoadSkill 这类基础设施工具不受白名单约束，Skill 内部可以嵌套调用其他 Skill。

## 激活状态跟踪

激活的 Skill 怎么变成 Agent 看到的系统提示词？关键在 `build_environment_context` 函数：

```python
def build_environment_context(
    work_dir: str,
    active_skills: dict[str, str] | None = None,
    skill_catalog: str = "",
    agent_catalog: str = "",
) -> str:
    parts = [f"Current working directory: {work_dir}", ...]
    if skill_catalog:
        parts.append(skill_catalog)
    if active_skills:
        parts.append("## Active Skills")
        for name, sop in active_skills.items():
            parts.append(f"\n### Skill: {name}\n")
            parts.append(sop)
    return "\n".join(parts)
```

`active_skills` 是一个 `dict[str, str]` ，key 是 Skill 名字，value 是替换参数后的 SOP 正文。这个字典只用于跟踪： `/skills` 命令查看当前激活了哪些 Skill，上下文压缩后的恢复也靠它。SOP 本身不会被注入到环境上下文，而是通过 slash command（作为 user message）或 LoadSkill 的 tool\_result 一次性进入对话历史。

Agent 侧的配合也很简单。 `activate_skill` 就是往字典里写一条：

```python
def activate_skill(self, name: str, prompt_body: str) -> None:
    self.active_skills[name] = prompt_body
```

`/clear` 清空对话时， `clear_active_skills` 也会把这个字典清掉，新会话不会残留上一轮的激活记录。

## 自定义工具（目录型 Skill）

`tool.json` 支持单个对象或数组，单个对象自动包装成列表统一处理：

```python
def parse_tool_json(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = [raw]
    return raw
```

工具实现的加载用了 `importlib.util` 动态加载模块。约定很简单：实现文件放在 `references/` 目录下，文件名和工具名一致，必须定义一个 `execute` 函数：

```python
def load_tool_implementation(references_dir, tool_name):
    script = references_dir / f"{tool_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"gcode_skill_tool_{tool_name}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "execute", None)
```

`SkillCustomTool` 把 schema 和 execute 函数包装成标准 Tool。 `asyncio.iscoroutinefunction` 自动判断实现是同步还是异步，该 await 就 await。 `_impl` 为 None 时不让整个流程崩掉，返回 `is_error=True` 的结果，Agent 能看到错误信息做出反应。

tool.json 负责注册新工具，allowedTools 负责可见性过滤，两者分工不重叠。

## 热重载（如果实现了）

```python
def get(self, name: str) -> SkillDef | None:
    skill = self._skills.get(name)
    if skill is None:
        return None
    if skill.source_path is not None:
        try:
            fresh = parse_skill_file(skill.source_path)
            fresh.is_directory = skill.is_directory
            self._skills[name] = fresh
            self._cache[name] = fresh
            return fresh
        except SkillParseError as e:
            log.warning("Hot-reload failed for '%s', using cached", name, e)
            return self._cache.get(name, skill)
    return skill
```

每次 `get()` 调用时，如果有 `source_path` 就重新读文件。读成功了同时更新 `_skills` 和 `_cache` 。读失败了返回 `_cache` 里的上次成功版本做兜底。

这就是前面两个字典的用途： `_skills` 随时更新， `_cache` 是安全网。热重载的代价是每次 get 都有一次文件 IO，但 Skill 文件通常几 KB，开销忽略不计。改完 Markdown 保存，下次触发就是新版本，不需要重启。

## 小结

| 设计决策           | 实现方式                                                                              |
| -------------- | --------------------------------------------------------------------------------- |
| 多位置加载          | `load_all` 按项目 → 用户 → 内置顺序，先到先得（ `not in seen` ）                                  |
| 定义格式           | 支持 `skill.yaml` + `prompt.md` 分离格式和 `SKILL.md` 单文件格式（YAML frontmatter + Markdown） |
| Frontmatter 解析 | `yaml.safe_load` 安全解析，严格校验 name/description 必填                                    |
| Inline 执行      | `activate_skill` 记录激活状态，SOP 通过 tool\_result 进入对话                                  |
| Fork 执行        | 创建独立 Agent + 独立 ConversationManager，异步流式执行                                        |
| 上下文传递          | none（空）、recent（最近 5 条）、full（每条截断 200 字符的摘要）                                       |
| 工具白名单          | `filter_tool_registry` 创建新 Registry，系统工具自动放行                                      |
| 自定义工具          | tool.json 声明 + references/xxx.py 动态加载（importlib.util）                             |
| 参数替换           | `str.replace` 占位符替换，无占位符时 append fallback                                         |
| 激活跟踪           | `activate_skill` 记录到 dict，用于 `/skills` 查看和压缩恢复                                    |
| 热重载            | `get()` 每次重读文件，失败时用 `_cache` 兜底                                                   |
| 内置 Skill 嵌入    | `importlib.resources.files()` 读取包内资源                                              |
| 容错策略           | 解析失败打 warning 跳过，热重载失败用缓存兜底                                                       |


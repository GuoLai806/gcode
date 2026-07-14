## 模块概览

把权限系统拆成了五个文件，放在 `gcode/permissions/` 目录下：

| 文件             | 职责                                                                 |
| -------------- | ------------------------------------------------------------------ |
| `checker.py`   | PermissionChecker 主类和 Decision 数据类，六层防御链的编排入口                      |
| `dangerous.py` | DangerousCommandDetector 类和 is\_safe\_command 函数，覆盖危险命令黑名单和安全命令白名单 |
| `modes.py`     | PermissionMode 枚举和模式矩阵                                             |
| `rules.py`     | Rule 数据类、RuleEngine 类、extract\_content 函数、parse\_rule 函数           |
| `sandbox.py`   | PathSandbox 类                                                      |
| `__init__.py`  | 重导出所有公开符号                                                          |

拆分得很细，每个文件各管一件事。这种组织方式的好处是依赖关系清晰： `checker.py` 导入其他四个模块，其他模块之间互不依赖。

## 核心类型

### Decision：权限判定结果

```python
@dataclass
class Decision:
    effect: DecisionEffect
    reason: str
```

用 `dataclass` 定义，两个字段。 `DecisionEffect` 是一个 Literal 类型：

```python
DecisionEffect = Literal["allow", "deny", "ask"]
```

`Literal` 类型在类型检查时能限制取值范围，但运行时没有强制约束。用字符串而不是枚举来表示判定效果，和 YAML 文件里的 `effect` 字段值保持一致，省去了转换步骤。

### PermissionMode：权限模式

```python
class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS = "bypassPermissions"
    CUSTOM = "custom"
    DONT_ASK = "dontAsk"
```

还定义了两种额外模式： `CUSTOM` 和 `DONT_ASK` 。 `CUSTOM` 模式下所有工具分类都返回 `ask` ，适合需要完全手动控制的场景。 `DONT_ASK` 模式和 `BYPASS` 效果一样，所有操作都放行。这两种模式提供了更细粒度的选择。

继承 `str` 让枚举值可以直接当字符串用，比较时不需要 `.value` 。

### 模式矩阵

```python
_MODE_MATRIX: dict[PermissionMode, dict[ToolCategory, DecisionEffect]] = {
    PermissionMode.DEFAULT: {"read": "allow", "write": "ask", "command": "ask"},
    PermissionMode.ACCEPT_EDITS: {"read": "allow", "write": "allow", "command": "ask"},
    PermissionMode.PLAN: {"read": "allow", "write": "ask", "command": "ask"},
    PermissionMode.BYPASS: {"read": "allow", "write": "allow", "command": "allow"},
    PermissionMode.CUSTOM: {"read": "ask", "write": "ask", "command": "ask"},
    PermissionMode.DONT_ASK: {"read": "allow", "write": "allow", "command": "allow"},
}

def mode_decide(mode: PermissionMode, category: ToolCategory) -> DecisionEffect:
    return _MODE_MATRIX[mode][category]
```

用字典嵌套字典实现二维查表。把所有六种模式都显式放进了矩阵里，包括 Plan 模式（和 Default 的值完全相同）。这样 `mode_decide` 函数就是纯粹的一行查表，不需要处理 key 不存在的情况。

`mode_decide` 函数就是一行查表，没有额外逻辑。因为所有六种模式都在矩阵里，不存在 key 不存在的情况。

### 内容提取映射表

```python
_CONTENT_FIELDS: dict[str, str] = {
    "Bash": "command",
    "ReadFile": "file_path",
    "WriteFile": "file_path",
    "EditFile": "file_path",
    "Glob": "pattern",
    "Grep": "pattern",
}

def extract_content(tool_name: str, arguments: dict[str, Any]) -> str:
    field = _CONTENT_FIELDS.get(tool_name)
    if field is None:
        return ""
    return str(arguments.get(field, ""))
```

六个工具对应六条映射规则。 `extract_content` 返回的始终是字符串，找不到映射时返回空字符串。 `str(arguments.get(field, ""))` 确保即使参数值不是字符串类型也会被转换，不会抛异常。

## 主流程走读：check() 方法

### PermissionChecker 的构造

```python
class PermissionChecker:
    def __init__(
        self,
        detector: DangerousCommandDetector,
        sandbox: PathSandbox,
        rule_engine: RuleEngine,
        mode: PermissionMode = PermissionMode.DEFAULT,
    ) -> None:
        self.detector = detector
        self.sandbox = sandbox
        self.rule_engine = rule_engine
        self.mode = mode
        self.plan_file_path: str = ""
```

依赖注入做得很彻底。 `DangerousCommandDetector` 、 `PathSandbox` 、 `RuleEngine` 三个组件都从外部注入，而不是在构造函数里自己创建。这样做的好处是测试时可以轻松替换成 mock 对象，不需要真实的文件系统和项目目录。

三个组件全部从构造函数注入，最接近教科书式的依赖注入。测试时可以轻松替换成 mock 对象，不需要真实的文件系统和项目目录。

### check() 方法概览

```python
def check(self, tool: Tool, arguments: dict[str, Any]) -> Decision:
    content = extract_content(tool.name, arguments)
    # Layer 0 → Layer 1 → Layer 1b → Layer 2 → Layer 3 → Layer 4 → Layer 5
    # ...
```

逐层串行结构：提取内容，然后依次检查每一层。

## 六层防御链

### Layer 0：Plan Mode 例外

```python
_PLAN_MODE_ALLOWED_TOOLS = frozenset({"Agent", "ToolSearch", "AskUserQuestion", "ExitPlanMode"})

if self.mode == PermissionMode.PLAN:
    if tool.name in _PLAN_MODE_ALLOWED_TOOLS:
        return Decision(effect="allow", reason="Plan mode: allowed tool")
    if tool.name in ("WriteFile", "EditFile") and content:
        if self._is_plan_file(content):
            return Decision(effect="allow", reason="Plan mode: plan file write")
```

维护了一个 Plan 模式工具白名单（ `frozenset` 是不可变集合，比普通 set 更安全）。放行逻辑分两步：先检查工具名是否在白名单，再检查文件写入是否指向计划文件。

`_is_plan_file` 的实现做了三级判断：

```python
def _is_plan_file(self, target_path: str) -> bool:
    if not self.plan_file_path or not target_path:
        return ".gcode/plans/" in target_path
    try:
        abs_target = os.path.abspath(target_path)
        abs_plan = os.path.abspath(self.plan_file_path)
        if abs_target == abs_plan:
            return True
    except Exception:
        pass
    if os.path.basename(target_path) == os.path.basename(self.plan_file_path):
        return True
    return ".gcode/plans/" in target_path
```

先尝试绝对路径比较，再尝试文件名比较，最后 fallback 到路径包含检查。注意当 `plan_file_path` 为空时，直接用路径包含检查作为兜底策略。

### Layer 1：安全命令白名单

```python
_SAFE_COMMANDS = frozenset({
    "ls", "dir", "pwd", "echo", "cat", "head", "tail", "wc",
    # ... 共 51 个
    "java -version", "java --version",
})

def is_safe_command(command: str) -> bool:
    trimmed = command.strip()
    if not trimmed:
        return False
    for ch in ("|", ";", "&&", ">", "$(", "`"):
        if ch in trimmed:
            return False
    for safe in _SAFE_COMMANDS:
        if trimmed == safe or trimmed.startswith(safe + " "):
            return True
    return False
```

`frozenset` 确保白名单不可变。元字符检测用元组遍历，一行代码搞定六种字符的检查。前缀匹配只检查空格分隔，没有额外处理 Tab 分隔的情况。

### Layer 2：危险命令黑名单

```python
_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"rm\s+-[a-z]*r[a-z]*f[a-z]*\s+/\s*$"), "递归强制删除根目录"),
    (re.compile(r"mkfs\."), "格式化磁盘"),
    (re.compile(r"dd\s+if=.*of=/dev/"), "直接写磁盘设备"),
    (re.compile(r"chmod\s+-R\s+777\s+/"), "递归修改根目录权限"),
    (re.compile(r":\(\)\{\s*:\|:&\s*\};:"), "fork bomb"),
    (re.compile(r"curl\s+.*\|\s*(ba)?sh"), "管道执行远程脚本"),
    (re.compile(r"wget\s+.*\|\s*(ba)?sh"), "管道执行远程脚本"),
    (re.compile(r">\s*/dev/sd"), "覆盖磁盘设备"),
]
```

8 条正则覆盖了最常见的破坏性操作，拒绝理由用的是中文。在模块加载时就编译好。

把危险命令检测封装成了一个独立的类 `DangerousCommandDetector` ：

```python
class DangerousCommandDetector:
    def __init__(self, extra_patterns: list[tuple[str, str]] | None = None) -> None:
        self._patterns = list(_DANGEROUS_PATTERNS)
        if extra_patterns:
            for regex_str, reason in extra_patterns:
                self._patterns.append((re.compile(regex_str), reason))

    def detect(self, command: str) -> tuple[bool, str]:
        for pattern, reason in self._patterns:
            if pattern.search(command):
                return True, reason
        return False, ""
```

封装成类的好处是支持 `extra_patterns` ，可以在构造时注入额外的危险模式。测试时也更方便，可以构造一个空的 Detector 来跳过黑名单检查。

用 `search` 而不是 `match` ，也就是子串匹配。命中即返回 `(True, reason)` ，不给 Ask 的机会。

### Layer 3：路径沙箱

```python
class PathSandbox:
    def __init__(
        self,
        project_root: str,
        extra_allowed: list[str] | None = None,
    ) -> None:
        root = Path(project_root).resolve()
        self._allowed_roots: list[Path] = [root, Path(tempfile.gettempdir()).resolve()]
        if extra_allowed:
            for p in extra_allowed:
                self._allowed_roots.append(Path(p).resolve())
```

构造时用 `Path.resolve()` 获取绝对路径。 `tempfile.gettempdir()` 获取系统临时目录，平台无关。

```python
def check(self, path: str) -> tuple[bool, str]:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = self.project_root / p
    abs_path = p.absolute()
    try:
        real_path = abs_path.resolve(strict=True)
    except OSError:
        # 文件不存在时，向上找到存在的祖先目录
        ancestor = abs_path
        while not ancestor.exists():
            parent = ancestor.parent
            if parent == ancestor:
                return False, f"无法解析路径: {path}"
            ancestor = parent
        resolved_ancestor = ancestor.resolve(strict=True)
        real_path = resolved_ancestor / abs_path.relative_to(ancestor)
```

路径沙箱做了两件值得注意的事情。

第一， `expanduser()` 处理 `~` 开头的路径，把它展开为用户 home 目录。第二， `resolve(strict=True)` 会解析符号链接。如果一个 symlink 指向项目外的文件，resolve 后的真实路径不在 `allowed_roots` 里，就会被拒绝。这样就堵住了符号链接绕过沙箱的漏洞。

文件不存在时的处理也很精细：从目标路径开始向上遍历，找到第一个存在的祖先目录，resolve 它，然后把剩余的相对路径拼接上去。这样 WriteFile 创建新文件时，只要父目录在沙箱内就放行。

```python
for root in self._allowed_roots:
    try:
        real_path.relative_to(root)
        return True, ""
    except ValueError:
        continue
return False, f"路径 {path} 超出沙箱范围"
```

路径前缀匹配用 `relative_to` ，如果目标路径不是某个 root 的子路径就抛 `ValueError` ，catch 住继续检查下一个 root。这是按路径组件级别比较的，不会把 `/tmp2` 误判为 `/tmp` 的子路径。

### Layer 4：规则引擎

```python
@dataclass(frozen=True)
class Rule:
    tool_name: str
    pattern: str
    effect: Effect

    def matches(self, tool_name: str, content: str) -> bool:
        if self.tool_name != tool_name:
            return False
        return fnmatch(content, self.pattern)
```

`frozen=True` 让 Rule 不可变。glob 匹配用标准库的 `fnmatch` ，简洁直接。

#### 三层规则文件

```python
class RuleEngine:
    def __init__(
        self,
        user_rules_path: Path | None = None,
        project_rules_path: Path | None = None,
        local_rules_path: Path | None = None,
    ) -> None:
        self._user_path = user_rules_path
        self._project_path = project_rules_path
        self._local_path = local_rules_path

    def _load_tiers(self) -> list[list[Rule]]:
        tiers: list[list[Rule]] = []
        for p in (self._user_path, self._project_path, self._local_path):
            tiers.append(_load_rules_file(p) if p else [])
        return tiers
```

三个路径都可以为 None，灵活性很好。 `_load_tiers()` 返回三层规则列表的列表，每层保持独立。

```python
def evaluate(self, tool_name: str, content: str) -> Effect | None:
    for rules in self._load_tiers():
        for rule in reversed(rules):
            if rule.matches(tool_name, content):
                return rule.effect
    return None
```

每次 evaluate 都重新加载文件（ `_load_tiers()` 内部调用 `_load_rules_file` ），没有做缓存。好处是 `append_local_rule` 写入新规则后，下次 check 自动生效。每层内部用 `reversed()` 从后往前扫描，后定义的规则优先。返回 `None` 表示没有匹配的规则，交给下一层处理。

#### 规则文件加载

```python
def _load_rules_file(path: Path) -> list[Rule]:
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    # ... 逐条解析，格式不对就跳过 ...
```

用 `yaml.safe_load` 而不是 `yaml.load` ，避免 YAML 反序列化漏洞。容错策略是：文件不存在、解析失败、格式不对都静默跳过。

规则解析用正则 `^(\w+)\((.+)\)$` ：

```python
_RULE_RE = re.compile(r"^(\w+)\((.+)\)$")

def parse_rule(raw: str, effect: Effect) -> Rule:
    m = _RULE_RE.match(raw.strip())
    if not m:
        raise ValueError(f"无效的规则语法: {raw}")
    return Rule(tool_name=m.group(1), pattern=m.group(2), effect=effect)
```

#### 动态追加规则

```python
def append_local_rule(self, rule: Rule) -> None:
    if self._local_path is None:
        return
    self._local_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_rules_file(self._local_path)
    existing.append(rule)
    entries = [{"rule": f"{r.tool_name}({r.pattern})", "effect": r.effect} for r in existing]
    self._local_path.write_text(yaml.dump(entries, allow_unicode=True), encoding="utf-8")
```

读取已有规则、追加新规则、序列化写回。 `allow_unicode=True` 确保中文等非 ASCII 字符正确写入。因为每次 evaluate 都重新读文件，追加后下次 check 自动生效，不需要缓存刷新。

### Layer 5：模式矩阵兜底

```python
effect = mode_decide(self.mode, tool.category)
if effect == "allow":
    return Decision(effect="allow", reason=f"权限模式 {self.mode.value} 放行")
if effect == "deny":
    return Decision(effect="deny", reason=f"权限模式 {self.mode.value} 拒绝")
return Decision(effect="ask", reason="需要用户确认")
```

最后一层查模式矩阵。如果是 `ask` ，触发 HITL 确认流程。reason 字段带上了具体的模式名称，方便调试。

## Agent Loop 里的集成

权限检查嵌在 agent.py 的工具执行流程里：

```python
if self.permission_checker:
    decision = self.permission_checker.check(tool, tc.arguments)
    if decision.effect == "deny":
        result = ToolResult(
            output=f"Permission denied: {decision.reason}",
            is_error=True,
        )
```

三种决策对应三条路径。 `deny` 返回错误结果但不终止循环。 `ask` 通过 `asyncio.Future` 做同步：

```python
if decision.effect == "ask":
    loop = asyncio.get_running_loop()
    future: asyncio.Future[PermissionResponse] = loop.create_future()
    yield PermissionRequest(
        tool_name=tc.tool_name,
        description=desc,
        future=future,
    )
    response = await future
```

Python 用 `asyncio.Future` 做 Agent 和 UI 之间的异步同步。通过 `yield` 把权限请求事件发给调用方，调用方处理完后 resolve future，Agent 继续执行。

用户选「始终允许」时，构造一个 Rule 追加到本地文件：

```python
if response == PermissionResponse.ALLOW_ALWAYS:
    content = extract_content(tc.tool_name, tc.arguments)
    pattern = f"{content[:60]}*" if len(content) > 60 else f"{content}*"
    rule = Rule(tool_name=tc.tool_name, pattern=pattern, effect="allow")
    self.permission_checker.rule_engine.append_local_rule(rule)
```

pattern 截取前 60 个字符加通配符，这样同类命令（比如 `git commit -m "xxx"` ）下次都能匹配上，不用一条一条确认。

子 Agent 创建时也会构造自己的 PermissionChecker，权限模式可以独立配置。

## 小结

| 设计决策         | 实现方式                                                                        |
| ------------ | --------------------------------------------------------------------------- |
| 判定结果         | `DecisionEffect` Literal 类型 + `Decision` dataclass 携带理由                     |
| 权限模式         | `PermissionMode(str, Enum)` 六种模式，含 CUSTOM 和 DONT\_ASK                       |
| 模式矩阵         | `dict[PermissionMode, dict[ToolCategory, DecisionEffect]]` 二维字典，Plan 显式放入矩阵 |
| 安全命令白名单      | `frozenset` （51 条），前缀匹配 + 元字符检测                                             |
| 危险命令黑名单      | `DangerousCommandDetector` 类，8 条预编译正则 + 可注入额外模式， `search` 子串匹配              |
| 路径沙箱         | `Path.resolve(strict=True)` 解析符号链接 + `relative_to` 组件级前缀匹配，不存在文件向上查找祖先      |
| 规则语法和匹配      | `ToolName(pattern)` 格式， `fnmatch` glob 匹配                                   |
| 规则文件加载       | 每次 evaluate 重新读文件，无缓存                                                       |
| Plan Mode 例外 | `frozenset` 工具白名单 + `_is_plan_file` 三级降级（绝对路径 > 文件名 > 路径包含）                 |
| 防御链串联        | `check()` 六层顺序执行，首个明确判定即返回                                                  |
| 依赖注入         | Detector、Sandbox、RuleEngine 全部从构造函数注入                                       |
| 架构选择         | 五文件拆分，每个文件各管一件事，依赖关系单向                                                      |


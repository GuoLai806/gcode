## 模块概览

| 文件               | 职责                                          |
| ---------------- | ------------------------------------------- |
| `models.py`      | `Worktree` 和 `WorktreeSession` 数据类          |
| `slug.py`        | `validate_slug` 安全校验、 `flatten_slug` 转换     |
| `manager.py`     | `WorktreeManager` ：创建 / 进入 / 退出 / 自动清理，核心调度 |
| `session.py`     | 会话持久化到 `worktree_session.json`              |
| `setup.py`       | 创建后四步初始化                                    |
| `changes.py`     | 变更检测 + 未推送 commit 检查，fail-closed            |
| `cleanup.py`     | 过期 Worktree 后台异步清理                          |
| `integration.py` | 与 SubAgent 集成：生成 worktree 名称和上下文通知          |
| `__init__.py`    | 包级别的导出聚合                                    |

`manager.py` 是中枢，它依赖 `slug.py` 做校验、 `setup.py` 做初始化、 `changes.py` 做变更检测、 `session.py` 做持久化。 `cleanup.py` 用 asyncio task 做后台清理。 `integration.py` 提供 SubAgent 集成的辅助函数。

## 核心类型

### Worktree 和 WorktreeSession

```python
@dataclass
class Worktree:
    name: str
    path: str
    branch: str
    based_on: str
    head_commit: str
    created: datetime = field(default_factory=datetime.now)

@dataclass
class WorktreeSession:
    original_cwd: str
    worktree_path: str
    worktree_name: str
    original_branch: str
    original_head_commit: str
    session_id: str = ""
    hook_based: bool = False
```

`Worktree` 是资源描述， `WorktreeSession` 是一次使用行为的状态。分离设计让一个 worktree 可以被多次进入退出，session 只记录最近一次。

### WorktreeManager

```python
class WorktreeManager:
    def __init__(self, repo_root, symlink_directories=None, worktree_dir=None):
        self.repo_root = repo_root
        self.symlink_directories = symlink_directories or []
        self.worktree_dir = worktree_dir or str(Path(repo_root) / ".gcode" / "worktrees")
        self._lock = asyncio.Lock()
        self.active: dict[str, Worktree] = {}
        self.current_session: WorktreeSession | None = None
```

并发保护用 `asyncio.Lock()` ，因为 整体基于 asyncio。 `active` 字典记录所有活跃的 worktree， `current_session` 是当前的全局会话。

## Slug 安全校验

```python
MAX_SLUG_LENGTH = 64
_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

def validate_slug(name: str) -> str | None:
    if not name: return "name cannot be empty"
    if len(name) > MAX_SLUG_LENGTH: return f"name too long"
    segments = name.split("/")
    for seg in segments:
        if not seg: return "name contains empty segment"
        if seg in (".", ".."): return "name must not contain '.' or '..'"
        if not _SEGMENT_RE.match(seg): return f"invalid segment: {seg!r}"
    return None
```

返回 None 表示校验通过，返回字符串表示错误信息。Python 风格的轻量级验证，不抛异常。校验规则：64 字符上限、per-segment 正则、禁止 `.` 和 `..` 。

`flatten_slug` 把 `/` 替换成 `+` ，用于目录名和分支名。

## 主流程走读：创建 Worktree

### 快速恢复

`WorktreeManager` 实现了纯文件系统读取 HEAD SHA 的静态方法：

```python
@staticmethod
def read_worktree_head_sha(wt_path: str) -> str | None:
    git_file = wt / ".git"
    content = git_file.read_text(encoding="utf-8").strip()
    if not content.startswith("gitdir:"): return None
    gitdir = Path(content.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = (wt / gitdir).resolve()
    # 读 commondir → 读 HEAD → 解析 ref → SHA
```

逻辑是： `.git` 文件 → `gitdir:` 指针 → HEAD → ref 解析 → loose ref 或 packed-refs → SHA。纯文件读取，不启动 git 子进程。

### 创建主流程

```python
async def create(self, name: str, base_branch: str = "HEAD") -> Worktree:
    async with self._lock:
        err = validate_slug(name)
        if err: raise WorktreeError(err)
        if name in self.active:
            raise WorktreeError(f"worktree already exists: {name}")
        flat_slug = flatten_slug(name)
        wt_path = os.path.join(self.worktree_dir, flat_slug)
        branch_name = f"worktree-{flat_slug}"
        # 快速恢复
        head_sha = self.read_worktree_head_sha(wt_path)
        if head_sha is not None:
            wt = Worktree(name=name, path=wt_path, branch=branch_name,
                          based_on=base_branch, head_commit=head_sha)
            self.active[name] = wt
            return wt
```

整个创建操作在 `asyncio.Lock` 内完成。快速恢复路径：如果已有 worktree 的 HEAD SHA 能读到，直接构造 `Worktree` 对象加入 `active` 字典。

全新创建路径：

```python
        result = self._run_git([
            "worktree", "add", "-B", branch_name, wt_path, base_branch,
        ])
        perform_post_creation_setup(
            self.repo_root, wt_path,
            symlink_directories=self.symlink_directories,
        )
```

`-B` （大写）容忍残留分支。 `_run_git` 内部设置了 `GIT_TERMINAL_PROMPT=0` 和 `GIT_ASKPASS=""` 环境变量。

## 创建后初始化

```python
def perform_post_creation_setup(repo_root, wt_path, symlink_directories=None):
    _copy_local_configs(root, wt)
    _setup_git_hooks(root, wt)
    _create_symlinks(root, wt, symlink_directories or [])
    _copy_ignored_files(root, wt)
```

**A. 复制本地配置。&#x20;**&#x989D;外复制了 `.env` 文件（ `LOCAL_CONFIG_FILES` 列表里有 `settings.local.json` 和 `.env` ），用 `shutil.copy2` 保留文件元数据。

**B. 配置 Git Hooks。&#x20;**&#x4F18;先 `.husky/` 回退 `.git/hooks/` ，通过 `subprocess.run(["git", "config", "core.hooksPath", ...])` 设置。

**C. 创建符号链接。&#x20;**&#x904D;历 `symlink_directories` ，源存在且目标不存在才创建。

**D. 复制被忽略的文件。&#x20;**&#x8BFB; `.worktreeinclude` ，用 `git ls-files --others --ignored --exclude-standard --directory` 列出候选，用 `fnmatch.fnmatch` 做模式匹配后复制。

所有步骤都是 best-effort：异常只记 warning 不抛出。

## 进入和退出 Worktree

### 进入

```python
async def enter(self, name: str) -> WorktreeSession:
    wt = self.active.get(name)
    if wt is None: raise WorktreeError(f"worktree not found: {name}")
    session = WorktreeSession(
        original_cwd=os.getcwd(),
        worktree_path=wt.path,
        worktree_name=name,
        original_branch=self._get_current_branch(),
        original_head_commit=self._get_head_commit(),
    )
    self.current_session = session
    save_worktree_session(self._gcode_dir, session)
    return session
```

记录现场、设置全局 session、持久化。没有 `os.chdir` ，走显式 cwd 模式，工具从 session 取当前路径。

### 退出

```python
async def exit(self, name, action="keep", discard_changes=False):
    wt = self.active.get(name)
    if action == "remove" and not discard_changes:
        changes = count_worktree_changes(wt.path, wt.head_commit)
        if changes.uncommitted > 0 or changes.new_commits > 0:
            raise WorktreeError("worktree has changes ... Set discard_changes=True")
    self.current_session = None
    save_worktree_session(self._gcode_dir, None)
    if action == "remove":
        await self._remove_worktree(name, wt)
```

变更保护：删除前检查未提交修改和新 commit，没有显式确认就拒绝。清空 session 并持久化 None（写入空 JSON `{}` ），防止 `--resume` 误恢复。

删除时 `asyncio.sleep(0.1)` 等 lockfile 释放，不会阻塞事件循环。

## 变更检测

```python
def has_worktree_changes(wt_path, head_commit):
    c = count_worktree_changes(wt_path, head_commit)
    return c.uncommitted > 0 or c.new_commits > 0
```

`count_worktree_changes` 内部用 `git status --porcelain` 和 `git rev-list --count` 做两层检测。fail-closed 策略：异常时默认设为 1（有变更）。还有个独立的 `has_unpushed_commits` 函数用于后台清理。

## 自动清理

### 临时 Worktree 识别

```python
EPHEMERAL_PATTERNS = [
    re.compile(r"^agent-a[0-9a-f]{7}$"),
    re.compile(r"^wf_[0-9a-f]{8}-[0-9a-f]{3}-\d+$"),
    re.compile(r"^wf-\d+$"),
    # ...
]
```

五个模式覆盖了所有自动生成的命名格式。

### 清理逻辑

```python
async def cleanup_stale_worktrees(manager, cutoff_hours):
    for entry in worktree_dir.iterdir():
        if not _is_ephemeral(name): continue
        if manager.current_session and manager.current_session.worktree_name == name: continue
        mtime = datetime.fromtimestamp(entry.stat().st_mtime)
        if mtime > cutoff: continue
        if has_worktree_changes(str(entry), head_sha): continue
        if has_unpushed_commits(str(entry)): continue
        # 执行删除
```

层层过滤：ephemeral 模式 → 跳过当前 session → 年龄检查 → 变更检查 → 未推送 commit 检查。

### 后台清理循环

```python
async def start_stale_cleanup_task(manager, interval, cutoff_hours):
    while True:
        await asyncio.sleep(interval)
        count = await cleanup_stale_worktrees(manager, cutoff_hours)
```

用 `asyncio.sleep` 做定时，简单的无限循环。调用方用 `asyncio.create_task` 启动。

## 与 SubAgent 的集成

```python
WORKTREE_NOTICE_TEMPLATE = """\
[WORKTREE CONTEXT]
You have inherited the parent agent's conversation context.
You are currently working in an isolated Git Worktree: {wt_path}
The parent agent's working directory is: {parent_cwd}
...
[/WORKTREE CONTEXT]
"""

def generate_worktree_name() -> str:
    return f"agent-{secrets.token_hex(4)}"
```

`generate_worktree_name` 生成 `agent-` 加 8 位随机 hex。上下文通知用 `[WORKTREE CONTEXT]` 标签包裹，告诉子 Agent 它的位置和注意事项。

## 小结

| 设计决策    | 实现方式                                                               |
| ------- | ------------------------------------------------------------------ |
| Slug 校验 | `validate_slug` 返回 None 或错误字符串                                     |
| 并发保护    | `asyncio.Lock()`                                                   |
| 快速恢复    | `read_worktree_head_sha` 纯文件系统读 `.git` 指针链路                        |
| 分支创建    | `git worktree add -B` ， `subprocess.run` + `GIT_TERMINAL_PROMPT=0` |
| 创建后初始化  | 四步 + `fnmatch.fnmatch` 做模式匹配                                       |
| 变更检测    | `Changes` dataclass + fail-closed 策略                               |
| 过期清理    | 五层过滤 + `asyncio.sleep` 循环                                          |
| 会话持久化   | JSON 文件，清空时写 `{}`                                                  |
| 显式 cwd  | 不 chdir，工具从 session 取路径                                            |


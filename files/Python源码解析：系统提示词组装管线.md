理论篇讲了 System Prompt 的设计理念和分层结构，这篇带你走读 Python 版 GCode 的真实代码，看看一个 300 行的文件是怎么把十几段提示词组装成一份完整 System Prompt 的。

## 模块概览

System Prompt 的代码全部集中在一个文件里：

304 行，一个文件搞定。Python 版没有把段落定义拆分出去，所有常量和逻辑都在同一个文件里，非常紧凑。

## 核心类型

### PromptSection：提示词片段

```plain&#x20;text
@dataclass
class PromptSection:
    name: str
    priority: int
    content: str
```

每个 PromptSection 就是一个提示词片段，带三个字段： `name` 是人类可读的标识， `priority` 是排序权重， `content` 是实际的提示词文本。

这里用 `@dataclass` 而不是普通 class，是因为 PromptSection 本质上就是一个数据容器，不需要自定义的 `init` 或比较逻辑。 `@dataclass` 自动生成构造函数和 `repr` ，省掉样板代码。

`priority` 的设计很关键。它决定了各段落在最终 System Prompt 中出现的顺序。数字越小越靠前，Identity（priority=0）永远排在第一位，Memory（priority=95）排在最后。这不是随意的数字，而是刻意留了间隔，方便后续在两个段落之间插入新内容，不用改动已有的优先级。

### PromptBuilder：组装器

```plain&#x20;text
class PromptBuilder:
    def __init__(self) -> None:
        self._sections: list[PromptSection] = []

    def add(self, section: PromptSection) -> PromptBuilder:
        self._sections.append(section)
        return self

    def build(self) -> str:
        self._sections.sort(key=lambda s: s.priority)
        parts = [s.content.strip() for s in self._sections
                 if s.content.strip()]
        return "\n\n".join(parts)
```

PromptBuilder 的职责就是收集段落、按优先级排序、拼接成字符串。 `add()` 返回 `self` ，支持链式调用。 `build()` 调用时才排序，说明你可以以任意顺序 `add` ，不用关心插入顺序。

排序用的是 `sorted()` 的就地版本 `list.sort()` ， `key=lambda s: s.priority` 提取排序键。排序之后，用列表推导式过滤掉空内容，最后用 `"\n\n".join()` 把所有段落拼在一起，段落之间隔两个换行。

这个 `strip()` 调用出现了两次：一次在过滤条件里，一次在值提取里。看起来像是多余的，但实际上这保证了即使某个段落的 content 只有空白字符，也不会被拼进最终结果。

## 主流程：build\_system\_prompt

### 入口函数签名

```plain&#x20;text
def build_system_prompt(
    hook_prompts: list[str] | None = None,
    coordinator_mode: bool = False,
    agent_catalog: list[tuple[str, str]] | None = None,
    custom_instructions: str = "",
    skill_section: str = "",
    memory_section: str = "",
    work_dir: str = ".",
) -> str:
```

七个参数，全部有默认值，调用方可以只传需要的。这是典型的 Python 风格：用关键字参数 + 默认值代替 Builder 模式，简洁但灵活。

`coordinator_mode` 是一个快速出口。如果是团队模式的协调者，直接走另一套完全不同的 prompt 构建逻辑，跳过下面所有的段落组装。

### 协调者模式的短路

```plain&#x20;text
if coordinator_mode:
    from gcode.teams.coordinator import (
        get_coordinator_system_prompt,
    )
    return get_coordinator_system_prompt(
        agent_catalog=agent_catalog
    )
```

这个 `import` 写在函数体内而不是文件顶部，是为了避免循环导入。 `teams.coordinator` 可能反过来依赖 `prompts` 模块的某些类型，如果在顶层互相 import 就会报错。延迟导入是 Python 处理循环依赖的标准手法。

### 7 个固定段落的装配

```plain&#x20;text
b = PromptBuilder()
b.add(IDENTITY_SECTION)
b.add(SYSTEM_SECTION)
b.add(DOING_TASKS_SECTION)
b.add(EXECUTING_ACTIONS_SECTION)
b.add(USING_TOOLS_SECTION)
b.add(TONE_STYLE_SECTION)
b.add(TEXT_OUTPUT_SECTION)
b.add(environment_section(work_dir))
```

七个全局常量 + 一个动态生成的环境段落，priority 从 0 到 70，间隔为 10。这些段落是每次 System Prompt 构建都会包含的「固定骨架」。

注意 `environment_section(work_dir)` 是一个函数调用而不是全局常量。因为工作目录、平台信息、当前日期这些东西每次都不一样，必须在运行时动态生成。

### 条件段落：80 到 95

```plain&#x20;text
if custom_instructions:
    b.add(PromptSection(
        name="CustomInstructions",
        priority=80,
        content=(
            "# Project Instructions\n\n"
            + custom_instructions
        ),
    ))

if skill_section:
    b.add(PromptSection(
        name="Skills", priority=90,
        content=skill_section,
    ))

if memory_section:
    b.add(PromptSection(
        name="Memory", priority=95,
        content=memory_section,
    ))
```

三个条件段落只有在内容非空时才加入。优先级 80、90、95 放在固定段落之后，是因为它们是用户自定义或运行时注入的内容，应该出现在系统指令之后。

`custom_instructions` 是项目级别的 CLAUDE.md 内容， `skill_section` 是当前激活的技能描述， `memory_section` 是持久化记忆。三者的排序逻辑是：项目指令 → 技能描述 → 记忆。记忆排最后是因为它最接近对话上下文，放在 System Prompt 尾部让 LLM 更容易「记住」。

### Hook 注入：最后的拼接

```plain&#x20;text
result = b.build()

if hook_prompts:
    result += ("\n\n# Hook Injected Context\n"
               + "\n".join(hook_prompts))

return result
```

Hook 注入的内容不走 PromptBuilder，直接字符串拼接在 `build()` 结果之后。这是个有意的设计选择：Hook 是外部系统注入的上下文，不参与优先级排序，永远排在最后。用字符串拼接比再包一层 PromptSection 更直接。

## 固定段落详解

### Identity 段落（priority=0）

```plain&#x20;text
IDENTITY_SECTION = PromptSection(
    name="Identity",
    priority=0,
    content=(
        "You are GCode, an AI programming assistant "
        "running in the terminal. "
        "You help users with software engineering tasks "
        "including writing code, debugging, refactoring, "
        "explaining code, and running commands.\n\n"
        "IMPORTANT: Be careful not to introduce security "
        "vulnerabilities such as command injection, XSS, "
        "SQL injection, and other common vulnerabilities. "
        "Prioritize writing safe, secure, and correct code."
        "\n"
        "IMPORTANT: You must NEVER generate or guess URLs "
        "unless you are confident they help the user with "
        "programming. You may use URLs provided by the user."
    ),
)
```

Identity 排在 priority=0，是 LLM 读到的第一段内容。它做两件事：告诉 LLM 「你是谁」，以及立即设立两条安全红线。安全约束写在 Identity 段落而不是后面的行为段落里，是因为 LLM 对 System Prompt 开头部分的遵从度更高。

Python 这里用括号包裹的字符串拼接代替三引号字符串，是为了控制缩进。如果用 `"""..."""` ，内容的缩进会被带进最终文本，需要额外处理。

### Text Output 段落（priority=60）

```plain&#x20;text
TEXT_OUTPUT_SECTION = PromptSection(
    name="TextOutput",
    priority=60,
    content="""\
# Text output (does not apply to tool calls)

Assume users can't see most tool calls or thinking \
-- only your text output. Before your first tool call, \
state in one sentence what you're about to do. While \
working, give short updates at key moments: when you \
find something, when you change direction, or when you \
hit a blocker. Brief is good -- silent is not. One \
sentence per update is almost always enough.
...""",
)
```

这个段落用了 `"""\` 开头，反斜杠紧跟三引号，目的是避免在内容开头产生一个空行。如果写成 `"""` 然后换行，最终字符串会以 `\n` 开头，拼接后两个段落之间就会出现三个换行而不是两个。

## 环境探测

```plain&#x20;text
def environment_section(work_dir: str) -> PromptSection:
    lines = [
        "# Environment",
        f" - Working directory: {work_dir}",
        f" - Platform: {platform.system()} "
        f"{platform.release()}",
        f" - Date: "
        f"{datetime.now().strftime('%Y-%m-%d')}",
    ]
    return PromptSection(
        name="Environment", priority=70,
        content="\n".join(lines),
    )
```

环境段落用 Python 标准库的 `platform.system()` 和 `platform.release()` 获取操作系统信息，用 `datetime.now()` 获取当前日期。这些信息让 LLM 知道自己运行在什么平台上，从而生成适配当前环境的命令。

比如在 Windows 上，LLM 会用 `dir` 代替 `ls` ；知道日期后，LLM 能正确回答「今天是几号」这类问题，而不是靠训练数据里的过期知识。

f-string 是 Python 3.6+ 的字符串格式化语法，比 `str.format()` 更简洁。 `{work_dir}` 直接嵌入变量值，不需要位置参数或命名参数。

### 环境上下文的补充信息

```plain&#x20;text
def build_environment_context(
    work_dir: str,
    active_skills: dict[str, str] | None = None,
    skill_catalog: str = "",
    agent_catalog: str = "",
) -> str:
    parts = [
        f"Current working directory: {work_dir}",
        f"Operating system: {platform.system()} "
        f"{platform.release()}",
        f"Current time: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    if agent_catalog:
        parts.append("")
        parts.append(agent_catalog)

    if skill_catalog:
        parts.append("")
        parts.append(skill_catalog)

    if active_skills:
        parts.append("")
        parts.append("## Active Skills")
        for name, sop in active_skills.items():
            parts.append(f"\n### Skill: {name}\n")
            parts.append(sop)

    return "\n".join(parts)
```

这个函数和 `environment_section` 不一样。 `environment_section` 生成的是 System Prompt 里的固定段落，而 `build_environment_context` 生成的是动态注入到对话中的环境上下文，包含更多运行时信息，比如当前激活的技能、可用的 Agent 目录。

注意 `active_skills` 的类型是 `dict[str, str] | None` ，键是技能名，值是技能的 SOP 文本。遍历时用 `items()` 解构为 `name, sop` ，然后拼成 Markdown 格式的技能描述。

## Plan Mode 提示词

### 完整版提醒

```plain&#x20;text
_PLAN_MODE_FULL_REMINDER = """\
Plan mode is active. The user indicated that they do \
not want you to execute yet -- you MUST NOT make any \
edits (with the exception of the plan file mentioned \
below), run any non-readonly tools (including changing \
configs or making commits), or otherwise make any \
changes to the system. This supercedes any other \
instructions you have received.

## Plan File Info:
{plan_file_info}
You should build your plan incrementally by writing to \
or editing this file. NOTE that this is the only file \
you are allowed to edit - other than this you are only \
allowed to take READ-ONLY actions.
..."""
```

这是 Plan Mode 的核心提示词。用 `{plan_file_info}` 作为占位符，后续通过 `.format()` 填充。注意开头的强硬措辞「you MUST NOT」和「This supercedes any other instructions」，这是在告诉 LLM：Plan Mode 的约束优先级高于 System Prompt 里的其他所有指令。

### 精简版提醒

```plain&#x20;text
_PLAN_MODE_SPARSE_REMINDER = (
    "Plan mode still active (see full instructions "
    "earlier in conversation). "
    "Read-only except plan file ({plan_path}). "
    "Follow 5-phase workflow."
)
```

精简版只有一行，提醒 LLM「Plan Mode 还在，规则没变」。不需要每轮都重复完整规则，太浪费 Token。

### 提醒频率控制

```plain&#x20;text
_REMINDER_INTERVAL = 5

def build_plan_mode_reminder(
    plan_path: str, plan_exists: bool,
    iteration: int,
) -> str:
    if plan_exists:
        plan_file_info = (
            f"Plan file: {plan_path}\n"
            f"A plan file already exists at {plan_path}. "
            "You can read it and make incremental edits "
            "using the EditFile tool."
        )
    else:
        plan_file_info = (
            f"Plan file: {plan_path}\n"
            f"No plan file exists yet. You should create "
            f"your plan at {plan_path} "
            "using the WriteFile tool."
        )

    if iteration == 1:
        return _PLAN_MODE_FULL_REMINDER.format(
            plan_file_info=plan_file_info
        )

    attachment_index = (iteration - 1) // _REMINDER_INTERVAL
    if attachment_index % _REMINDER_INTERVAL == 0:
        return _PLAN_MODE_FULL_REMINDER.format(
            plan_file_info=plan_file_info
        )

    return _PLAN_MODE_SPARSE_REMINDER.format(
        plan_path=plan_path
    )
```

这个函数根据当前迭代次数决定发完整版还是精简版提醒。第 1 轮一定发完整版；之后每隔 `_REMINDER_INTERVAL` （5 轮）的整数倍发一次完整版，其余轮次发精简版。

频率控制的算法用整数除法 `//` 和取模 `%` 实现。 `(iteration - 1) // 5` 计算当前在第几个 5 轮区间里， `% 5 == 0` 判断是不是区间的起始。这样第 1、6、26 轮会发完整版，其他轮次发精简版。

`plan_exists` 参数决定了提示词里是说「已有 Plan 文件，请编辑」还是「还没有 Plan 文件，请创建」。这个小细节避免了 LLM 试图读取一个不存在的文件，或者在已有 Plan 的情况下从头创建覆盖。

## 小结

